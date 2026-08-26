# Deployment

## Production shape

Nginx terminates HTTPS and proxies the same origin to Gunicorn. WhiteNoise serves
hashed compressed frontend assets; Nginx adds a one-year immutable cache policy.
The Vue shell loads dashboard analytics in one request and lazy-loads secondary
views and ECharts. No third-party font/CDN request is required.

Use `deploy/nginx/learning-os.conf.example` as the Nginx baseline and the systemd
unit in `deploy/systemd/`. Gunicorn access logging is disabled because raw Launch
Tokens occur in request paths; Nginx logs ordinary routes but suppresses browser,
IoT launch, and disturbance paths. Replace the
domain/certificate paths, validate with `nginx -t`, and reload. Access logging is
disabled for `/launch/`, `/api/launch/`, and `/api/disturbance/` because their
paths contain capability tokens. Prefer
HTTP/2 and Certbot/another automated certificate issuer.

The optional `/api/stress-test/probe/` location also disables access logging,
not because its key is in the URI (it is not), but to ensure a CPU/network load
test does not generate a storage-write workload. Keep the probe disabled outside
planned tests and follow the bounded PC workflow in [`stress_test/`](../stress_test/).
The same example sets a proxy-handoff timestamp and exposes Nginx upstream
connect/header/response timing headers. Without that snippet, client latency,
Django/DB/CPU, and host metrics still work, but queue and Nginx timing are
reported as unavailable rather than guessed.

The production/default cache remains file based. A separate controlled Redis
experiment can install `requirements-loadtest-redis.txt` and set
`DJANGO_CACHE_BACKEND=redis` plus `REDIS_CACHE_URL`; do not change the baseline
deployment and Redis at the same time. Use identical seeded hot/cold runs before
retaining the change.
Use `DJANGO_CACHE_BACKEND=dummy` for the matching no-application-cache control;
it is an experiment setting, not a recommended production default.

## Native systemd deployment

Native production may keep the database selector in a mode-`600`, ignored
`.env.database` overlay. This prevents the administrator-editable `.env` display
settings from accidentally replacing database credentials. For a local
peer-authenticated PostgreSQL role matching the service OS user:

```dotenv
DATABASE_URL=postgresql:///time_tracker
```

Docker deployments continue to supply `DATABASE_URL` directly through Compose.

```bash
cd /path/to/time-tracker
cp db.sqlite3 /safe/backup/db-$(date +%F-%H%M%S).sqlite3
systemctl stop time-tracker-web.service time-tracker-mcp.service
.venv/bin/pip install -r requirements.txt
cd frontend && npm ci && npm run build && npm run build:drill && cd ..
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
systemctl start time-tracker-web.service time-tracker-mcp.service
systemctl enable --now time-tracker-github-sync.timer
./deploy/scripts/smoke-test.sh https://study.example.com
```

Set `LEARNING_REPO=owner/private-repository`, `LEARNING_REPO_PATH`, and optionally
`LEARNING_REPO_MAIN_BRANCH` (default `main`) in `.env`,
then authenticate the service account with `gh auth login`. Web completions
enqueue a durable record and dispatch an immediate background push. The systemd
timer retries pending records every minute without delaying the completion API.
Administrator notes are pushed to the main branch; invited users receive
username-derived branches automatically.

To enable the public contact form with Gmail SMTP, add the following to the
private `.env`. Use a Google app-specific password, never the normal account
password:

```dotenv
CONTACT_EMAIL=zsyeh7286@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=zsyeh7286@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_USE_TLS=true
SMTP_USE_SSL=false
DEFAULT_FROM_EMAIL=zsyeh7286@gmail.com
```

The form sends from the configured owner mailbox back to `CONTACT_EMAIL` and
sets the visitor address as `Reply-To`. It does not create a contact-message
database row. If SMTP delivery fails, the page exposes the direct `mailto:`
address instead of claiming that delivery succeeded.

Validate row count, total duration, owner assignment, HTTPS login, a session start
and finish, export download, and Passkey enrollment before discarding rollback
artifacts. Gunicorn, not `runserver`, is required in production.

The first user who enables at-rest encryption causes Django to create a mode-600
server key at `DATA_ENCRYPTION_KEY_PATH`. It lives outside PostgreSQL; Docker's
default path is in the existing persistent data volume. Back it up separately and
restore it before starting Django against encrypted records. Multi-host installs
should provision the same 32-byte URL-safe base64 `DATA_ENCRYPTION_MASTER_KEY`
through their secret manager instead of relying on a node-local key file.

## Docker Compose

`./install.sh domain` preserves the SQLite compatibility volume.
`./install.sh --postgres domain` adds PostgreSQL 16 for new production installs.
The multi-stage Docker image builds Vue assets first and contains only the Python
runtime and built static files in the final image.

The question drill uses a second Vue build from the same repository. Point
`drill.example.com` at the same Gunicorn service, add that hostname to
`DJANGO_ALLOWED_HOSTS`, and add its HTTPS origin to `CSRF_TRUSTED_ORIGINS`.
The root dispatcher serves `frontend/drill-dist` only when the request hostname
is listed in `DRILL_HOSTS`; the Timer navigation does not link to it. See
`deploy/nginx/drill.ehzsy.site.conf.example` for the separate virtual host.

The electronic-information practice workspace reuses that lightweight training
bundle and the same authenticated Django API, while host-level queryset scoping
keeps its catalog and progress separate from the mathematics drill. Configure
`EI_HOSTS=ei.example.com`, `EI_ORIGIN=https://ei.example.com`, add the origin to
`CSRF_TRUSTED_ORIGINS`, and use `deploy/nginx/ei.ehzsy.site.conf.example`.
Import the owner-provided structured bank idempotently with:

```bash
.venv/bin/python manage.py import_ei_markdown /path/to/892-question-bank.md
```

Anonymous EI visits are relayed through the Timer host using the same 90-second,
single-use authentication handoff used by Drill; Passkeys therefore remain bound
to the Timer relying-party domain.

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
