#!/bin/sh
set -eu

base_url=${1:-http://127.0.0.1:8000}
login_headers=$(mktemp "${TMPDIR:-/tmp}/learning-os-smoke.XXXXXX")
trap 'rm -f "$login_headers"' EXIT

curl --fail --silent --show-error --head "$base_url/accounts/login/" > "$login_headers"
grep -qi '^X-Frame-Options: DENY' "$login_headers"
curl --fail --silent --show-error "$base_url/admin/login/" >/dev/null

redirect=$(curl --silent --output /dev/null --write-out '%{http_code} %{redirect_url}' "$base_url/")
case "$redirect" in
    302*accounts/login*) ;;
    *) echo "Dashboard auth redirect failed: $redirect" >&2; exit 1 ;;
esac

echo "Smoke test passed: login, admin recovery, and protected dashboard are reachable."
