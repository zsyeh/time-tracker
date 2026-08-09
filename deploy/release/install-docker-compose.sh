#!/bin/sh
set -eu

download_base=${TIME_TRACKER_DOWNLOAD_BASE:-https://app.ehzsy.site/files}
install_dir=${TIME_TRACKER_DIR:-"$PWD/time-tracker-docker"}
image_repository=${TIME_TRACKER_IMAGE:-ehzsy/time-tracker}
image_tag=${TIME_TRACKER_TAG:-latest}
tracker_port=${TRACKER_PORT:-8000}
public_host=${1:-localhost}
admin_user=${ADMIN_USERNAME:-admin}
admin_email=${ADMIN_EMAIL:-${admin_user}@localhost.invalid}

case "$public_host" in
  *[!A-Za-z0-9.-]*|'')
    echo "Invalid host. Use a hostname or IP address." >&2
    exit 1
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required: https://docs.docker.com/engine/install/" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "The Docker Compose plugin is required." >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

random_hex() {
  bytes=$1
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
  fi
}

mkdir -p "$install_dir"
curl -fsSL "$download_base/compose.yaml" -o "$install_dir/compose.yaml"
umask 077
secret_key=$(random_hex 48)
csrf_origins="http://localhost:$tracker_port,http://127.0.0.1:$tracker_port"
if [ "$public_host" != "localhost" ] && [ "$public_host" != "127.0.0.1" ]; then
  csrf_origins="$csrf_origins,https://$public_host"
fi
cat > "$install_dir/.env" <<EOF
TIME_TRACKER_IMAGE=$image_repository
TIME_TRACKER_TAG=$image_tag
TRACKER_PORT=$tracker_port
DJANGO_SECRET_KEY=$secret_key
DJANGO_DEBUG=false
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_ALLOWED_HOSTS=$public_host,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=$csrf_origins
SESSION_REMEMBER_DAYS=30
TRACKER_EXAM_DATE=2026-12-26
TRACKER_HEATMAP_START_DATE=2026-05-23
MCP_PORT=8001
MCP_URL_KEY=
MCP_ALLOW_UNAUTHENTICATED=false
EOF

cd "$install_dir"
if [ "${TIME_TRACKER_SKIP_PULL:-false}" != "true" ]; then
  docker compose pull
fi
docker compose up -d

attempt=0
until docker compose exec -T web python -c "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/admin/login/', headers={'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=3)" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 40 ]; then
    echo "The service did not become healthy. Run: docker compose logs web" >&2
    exit 1
  fi
  sleep 2
done

user_count=$(docker compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())" | tail -1)
if [ "$user_count" = "0" ]; then
  admin_password=$(random_hex 12)
  docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD="$admin_password" web \
    python manage.py createsuperuser --noinput --username "$admin_user" --email "$admin_email" >/dev/null
  echo "Admin username: $admin_user"
  echo "Admin password: $admin_password"
  echo "Save this password now; it is shown only once."
fi

echo "Personal Learning OS is ready at http://127.0.0.1:$tracker_port"
echo "Install directory: $install_dir"
echo "For Passkeys on a public hostname, place the service behind HTTPS."
