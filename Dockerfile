# Infra Pulse — container image
FROM python:3.12-slim

# ping checks shell out to the system `ping` binary, which slim images omit.
# Single RUN layer + cache cleanup keeps the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps before copying code so this layer is cached and only rebuilds
# when requirements.txt changes — not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY infra_pulse/ infra_pulse/

# Run as an unprivileged user that owns the data directory (avoid root).
RUN useradd --create-home appuser \
    && mkdir /data \
    && chown appuser:appuser /data
USER appuser

# Keep all mutable state on the /data volume so the image stays disposable
# and data survives restarts/upgrades. (DB_PATH/CONFIG read these env vars.)
ENV INFRA_PULSE_DB=/data/infra_pulse.db \
    INFRA_PULSE_CONFIG=/data/config.json
WORKDIR /data
VOLUME ["/data"]

# ENTRYPOINT is the program; CMD is the default subcommand (overridable), so
# `docker run infra-pulse report` also works.
ENTRYPOINT ["python", "/app/main.py"]
CMD ["run"]