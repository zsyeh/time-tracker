#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
service_name=${TIME_TRACKER_SERVICE:-time-tracker-web.service}
build_swap_path=''
build_stage=''
previous_builds=''
published_builds='false'

cleanup_build_swap() {
    if [ -n "$build_swap_path" ]; then
        swapoff "$build_swap_path" || true
        rm -f "$build_swap_path"
    fi
}

cleanup_build_directories() {
    if [ "$published_builds" != 'true' ] && [ -n "$previous_builds" ] && [ -d "$previous_builds" ]; then
        if [ -d "$previous_builds/app" ]; then
            rm -rf -- "$project_root/frontend/dist"
            mv "$previous_builds/app" "$project_root/frontend/dist"
        fi
        if [ -d "$previous_builds/drill" ]; then
            rm -rf -- "$project_root/frontend/drill-dist"
            mv "$previous_builds/drill" "$project_root/frontend/drill-dist"
        fi
    fi
    if [ -n "$build_stage" ] && [ -d "$build_stage" ]; then
        rm -rf -- "$build_stage"
    fi
    if [ -n "$previous_builds" ] && [ -d "$previous_builds" ]; then
        rm -rf -- "$previous_builds"
    fi
}

cleanup() {
    cleanup_build_swap
    cleanup_build_directories
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

trap cleanup EXIT INT TERM

cd "$project_root"

.venv/bin/python manage.py check
prepare_build_memory
export NODE_OPTIONS=${NODE_OPTIONS:---max-old-space-size=1024}
build_stage=$(mktemp -d "$project_root/.frontend-build.XXXXXX")
(
    cd frontend
    TIME_TRACKER_VITE_OUT_DIR="$build_stage/app" npm run build
    TIME_TRACKER_DRILL_VITE_OUT_DIR="$build_stage/drill" npm run build:drill
)

test -s "$build_stage/app/index.html"
test -s "$build_stage/drill/index.html"

# Publish new hashed assets before exposing the new index files. Old assets
# remain available, so in-flight browsers and a failed build keep working.
mkdir -p "$project_root/staticfiles/app" "$project_root/staticfiles/drill"
cp -a "$build_stage/app/." "$project_root/staticfiles/app/"
cp -a "$build_stage/drill/." "$project_root/staticfiles/drill/"

previous_builds=$(mktemp -d "$project_root/.frontend-previous.XXXXXX")
if [ -d "$project_root/frontend/dist" ]; then
    mv "$project_root/frontend/dist" "$previous_builds/app"
fi
if [ -d "$project_root/frontend/drill-dist" ]; then
    mv "$project_root/frontend/drill-dist" "$previous_builds/drill"
fi
mv "$build_stage/app" "$project_root/frontend/dist"
mv "$build_stage/drill" "$project_root/frontend/drill-dist"
published_builds='true'

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
