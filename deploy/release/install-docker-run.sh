#!/bin/sh
set -eu

image=${TIME_TRACKER_IMAGE:-ehzsy/time-tracker:latest}
container_name=${TIME_TRACKER_CONTAINER:-time-tracker}
volume_name=${TIME_TRACKER_VOLUME:-time_tracker_data}
tracker_port=${TRACKER_PORT:-8000}
public_host=${1:-localhost}
admin_user=${ADMIN_USERNAME:-admin}
admin_email=${ADMIN_EMAIL:-${admin_user}@localhost.invalid}
config_root=${XDG_CONFIG_HOME:-${HOME:-/tmp}/.config}
config_dir=$config_root/time-tracker
env_file=$config_dir/docker.env

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
if docker container inspect "$container_name" >/dev/null 2>&1; then
  echo "Container $container_name already exists. Remove or rename it before installing." >&2
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

mkdir -p "$config_dir"
umask 077
secret_key=$(random_hex 48)
csrf_origins="http://localhost:$tracker_port,http://127.0.0.1:$tracker_port"
if [ "$public_host" != "localhost" ] && [ "$public_host" != "127.0.0.1" ]; then
  csrf_origins="$csrf_origins,https://$public_host"
fi
cat > "$env_file" <<EOF
DJANGO_SECRET_KEY=$secret_key
DJANGO_DEBUG=false
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_ALLOWED_HOSTS=$public_host,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=$csrf_origins
SESSION_REMEMBER_DAYS=30
TRACKER_EXAM_DATE=2026-12-26
TRACKER_HEATMAP_START_DATE=2026-05-23
EOF

docker volume create "$volume_name" >/dev/null
if [ "${TIME_TRACKER_SKIP_PULL:-false}" != "true" ]; then
  docker pull "$image"
fi
docker run -d \
  --name "$container_name" \
  --restart unless-stopped \
  --env-file "$env_file" \
  -p "$tracker_port:8000" \
  -v "$volume_name:/app/data" \
  "$image" >/dev/null

attempt=0
until [ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container_name" 2>/dev/null)" = "healthy" ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 40 ]; then
    echo "The container did not become healthy. Run: docker logs $container_name" >&2
    exit 1
  fi
  sleep 2
done

user_count=$(docker exec "$container_name" python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())" | tail -1)
if [ "$user_count" = "0" ]; then
  admin_password=$(random_hex 12)
  docker exec -e DJANGO_SUPERUSER_PASSWORD="$admin_password" "$container_name" \
    python manage.py createsuperuser --noinput --username "$admin_user" --email "$admin_email" >/dev/null
  echo "Admin username: $admin_user"
  echo "Admin password: $admin_password"
  echo "Save this password now; it is shown only once."
fi

echo "Personal Learning OS is ready at http://127.0.0.1:$tracker_port"
echo "Environment file: $env_file"
echo "For Passkeys on a public hostname, place the container behind HTTPS."
