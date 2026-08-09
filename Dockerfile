FROM node:18-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_PATH=/app/data/db.sqlite3

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

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--error-logfile", "-", "time_server.wsgi:application"]
