#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
service_name=${TIME_TRACKER_SERVICE:-time-tracker-web.service}
build_swap_path=''

cleanup_build_swap() {
    if [ -n "$build_swap_path" ]; then
        swapoff "$build_swap_path" || true
        rm -f "$build_swap_path"
    fi
}

prepare_build_memory() {
    total_memory_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
    swap_count=$(awk 'END {print NR - 1}' /proc/swaps)
    available_disk_kb=$(df -Pk /var/tmp | awk 'NR == 2 {print $4}')
    if [ "$total_memory_kb" -lt 3145728 ] \
        && [ "$swap_count" -eq 0 ] \
        && [ "$available_disk_kb" -gt 2097152 ]; then
        build_swap_path=/var/tmp/time-tracker-build.swap
        if [ -e "$build_swap_path" ]; then
            echo "Refusing to overwrite existing $build_swap_path" >&2
            exit 1
        fi
        fallocate -l 1536M "$build_swap_path"
        chmod 600 "$build_swap_path"
        mkswap "$build_swap_path" >/dev/null
        swapon "$build_swap_path"
        echo "Enabled temporary build swap for this low-memory VPS."
    fi
}

trap cleanup_build_swap EXIT INT TERM

cd "$project_root"

.venv/bin/python manage.py check
prepare_build_memory
export NODE_OPTIONS=${NODE_OPTIONS:---max-old-space-size=1024}
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
