# Deployment

## Production shape

Nginx terminates HTTPS and proxies the same origin to Gunicorn. WhiteNoise serves
hashed compressed frontend assets; Nginx adds a one-year immutable cache policy.
The Vue shell loads dashboard analytics in one request and lazy-loads secondary
views and ECharts. No third-party font/CDN request is required.

Use `deploy/nginx/learning-os.conf.example` as the Nginx baseline and the systemd
unit in `deploy/systemd/`. Gunicorn access logging is disabled because raw Launch
Tokens occur in request paths; Nginx logs ordinary routes but suppresses both
browser and IoT launch paths. Replace the
domain/certificate paths, validate with `nginx -t`, and reload. Access logging is
disabled for `/launch/` because its path contains a capability token. Prefer
HTTP/2 and Certbot/another automated certificate issuer.

## Native systemd deployment

```bash
cd /path/to/time-tracker
cp db.sqlite3 /safe/backup/db-$(date +%F-%H%M%S).sqlite3
systemctl stop time-tracker-web.service time-tracker-mcp.service
.venv/bin/pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
systemctl start time-tracker-web.service time-tracker-mcp.service
./deploy/scripts/smoke-test.sh https://study.example.com
```

Validate row count, total duration, owner assignment, HTTPS login, a session start
and finish, export download, and Passkey enrollment before discarding rollback
artifacts. Gunicorn, not `runserver`, is required in production.

## Docker Compose

`./install.sh domain` preserves the SQLite compatibility volume.
`./install.sh --postgres domain` adds PostgreSQL 16 for new production installs.
The multi-stage Docker image builds Vue assets first and contains only the Python
runtime and built static files in the final image.

For an existing SQLite deployment, do not simply switch its database URL. Export
and import data in a maintenance window, verify counts/totals, and retain the
SQLite volume until validation is complete.

## Performance/security checklist

- `DJANGO_DEBUG=false`; random `DJANGO_SECRET_KEY`.
- `DJANGO_SECURE_SSL_REDIRECT=true` behind the HTTPS reverse proxy; local-only
  HTTP installs may explicitly set it to `false`.
- Exact `DJANGO_ALLOWED_HOSTS` and HTTPS `CSRF_TRUSTED_ORIGINS`.
- HTTPS only; proxy forwards original scheme and host.
- Hashed assets cached immutably; gzip/Brotli enabled when available.
- PostgreSQL connection reuse (`CONN_MAX_AGE=60`) for remote production.
- Launch URLs excluded from logs, sitemaps, previews, and analytics.
- Django admin protected at the network/proxy layer where practical.
