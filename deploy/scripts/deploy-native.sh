#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
service_name=${TIME_TRACKER_SERVICE:-time-tracker-web.service}

cd "$project_root"

.venv/bin/python manage.py check
(
    cd frontend
    npm run build
    npm run build:drill
)
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput

systemctl restart "$service_name"

drill_assets_ready() {
    grep -oE '/static/drill/[^" ]+' frontend/drill-dist/index.html \
        | while IFS= read -r asset; do
            curl --fail --silent --show-error \
                -H 'Host: drill.ehzsy.site' \
                -H 'X-Forwarded-Proto: https' \
                "http://127.0.0.1:8000$asset" >/dev/null || exit 1
        done
}

attempt=0
while [ "$attempt" -lt 20 ]; do
    if systemctl is-active --quiet "$service_name" \
        && curl --fail --silent --show-error --head \
            -H 'Host: timer.ehzsy.site' \
            -H 'X-Forwarded-Proto: https' \
            http://127.0.0.1:8000/accounts/login/ >/dev/null \
        && drill_assets_ready; then
        echo "Deployment complete: builds, migrations, static assets, and service are ready."
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 1
done

systemctl status "$service_name" --no-pager -n 30 >&2 || true
echo "Deployment failed readiness checks." >&2
exit 1
