FROM node:18-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ARG VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="Personal Learning OS" \
      org.opencontainers.image.description="Private-first Django and Vue study time tracker" \
      org.opencontainers.image.source="https://github.com/zsyeh/time-tracker" \
      org.opencontainers.image.version="$VERSION" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_PATH=/app/data/db.sqlite3 \
    TRACKER_LOCAL_ENV_PATH=/app/data/tracker.env

WORKDIR /app

RUN groupadd --system tracker \
    && useradd --system --gid tracker --home-dir /app tracker

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=tracker:tracker . .
COPY --from=frontend-build --chown=tracker:tracker /frontend/dist /app/frontend/dist
RUN mkdir -p /app/data /app/staticfiles \
    && chown -R tracker:tracker /app/data /app/staticfiles \
    && chmod +x /app/docker-entrypoint.sh

USER tracker

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD python -c "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/admin/login/', headers={'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=3)" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--error-logfile", "-", "time_server.wsgi:application"]
