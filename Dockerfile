FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY threadlens ./threadlens
RUN pip install --no-cache-dir .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    THREADLENS_CONFIG_PATH=/config/config.yaml

RUN useradd --create-home --shell /usr/sbin/nologin threadlens

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/threadlens /usr/local/bin/threadlens
COPY static /app/static

ENV THREADLENS_STATIC_DIR=/app/static

RUN mkdir -p /config /data && chown -R threadlens:threadlens /config /data /app/static

USER threadlens

EXPOSE 8128 8129

# Default CMD runs server mode; healthcheck targets the server API on 8128.
# For agent-only deployments, override CMD and healthcheck (see docs/docker.md).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8128/api/v1/health', timeout=3)"

ENTRYPOINT ["threadlens"]
CMD ["--mode", "server"]
