"""
checks.py — Check logic for each supported target type.

Every public function returns a consistent result dict:
    {
        "status":          "up" | "down" | "error",
        "response_time_ms": float | None,
        "detail":          "human-readable string",
    }
"""

import time
import socket

import requests
import dns.resolver
import dns.exception

# Default timeouts (seconds)
HTTP_TIMEOUT  = 10
DNS_TIMEOUT   = 5
TCP_TIMEOUT   = 5

def _result(status: str, response_time_ms: float | None, detail: str) -> dict:
    return {"status": status, "response_time_ms": response_time_ms, "detail": detail}

# ---------- HTTP / HTTPS ----------

def check_http(url: str) -> dict:
    """
    Perform an HTTP GET request and report status.

    2xx/3xx responses are 'up', 4xx/5xx are 'down'.
    Connection errors and timeouts are also 'down' (the target is unreachable).
    Unexpected request failures are 'error'.
    """
    start = time.perf_counter()
    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "InfraPulse/1.0"},
        )
        ms = round((time.perf_counter() - start) * 1000, 2)

        if response.status_code < 400:
            return _result("up", ms, f"HTTP {response.status_code}")
        else:
            return _result("down", ms, f"HTTP {response.status_code}")

    except requests.exceptions.ConnectionError as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"Connection error: {e}")
    except requests.exceptions.Timeout:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"Timed out after {HTTP_TIMEOUT}s")
    except requests.exceptions.RequestException as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("error", ms, str(e))

# --------- DNS ----------

def check_dns(hostname: str) -> dict:
    """
    Attempt to resolve a hostname using the system resolver.

    Reports 'up' if one or more A records are returned.
    """
    resolver = dns.resolver.Resolver()
    resolver.lifetime = DNS_TIMEOUT

    start = time.perf_counter()
    try:
        answers = resolver.resolve(hostname, "A")
        ms = round((time.perf_counter() - start) * 1000, 2)
        ips = ", ".join(str(r) for r in answers)
        return _result("up", ms, f"Resolved {hostname} → {ips}")
    except dns.resolver.NXDOMAIN:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"{hostname}: domain does not exist")
    except dns.resolver.NoAnswer:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"{hostname}: no A records found")
    except dns.exception.Timeout:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"DNS query timed out after {DNS_TIMEOUT}s")
    except Exception as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("error", ms, str(e))

# ---------- TCP ----------

def check_tcp(host: str, port: int) -> dict:
    """
    Attempt a TCP connection to host:port.

    Target format expected: "hostname:port" (parsing is handled in run_check/dispatcher).
    """
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT):
            ms = round((time.perf_counter() - start) * 1000, 2)
            return _result("up", ms, f"TCP {host}:{port} open")
    except ConnectionRefusedError:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"TCP {host}:{port} refused")
    except socket.timeout:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("down", ms, f"TCP {host}:{port} timed out after {TCP_TIMEOUT}s")
    except socket.gaierror as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("error", ms, f"DNS resolution failed for {host}: {e}")
    except OSError as e:
        ms = round((time.perf_counter() - start) * 1000, 2)
        return _result("error", ms, str(e))

# ---------- Dispatcher ----------

def run_check(check_type: str, target: str) -> dict:
    """
    Dispatch a check by type.

    Accepts:
    http  → full URL, e.g. "https://example.com"
    dns   → hostname, e.g. "example.com"
    tcp   → "host:port", e.g. "example.com:443"
    """
    if check_type == "http":
        return check_http(target)
    elif check_type == "dns":
        return check_dns(target)
    elif check_type == "tcp":
        if ":" not in target:
            return _result("error", None, f"TCP target must be 'host:port', got: {target}")
        host, port_str = target.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return _result("error", None, f"Invalid port: {port_str}")
        return check_tcp(host, port)
    
    return _result("error", None, f"Unknown check type: {check_type}")