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

import requests

# Default timeouts (seconds)
HTTP_TIMEOUT  = 10

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