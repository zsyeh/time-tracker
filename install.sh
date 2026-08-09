#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"

database_mode=sqlite
if [ "${1:-}" = "--postgres" ]; then
    database_mode=postgres
    shift
fi
public_host=${1:-localhost}

if ! command -v docker >/dev/null 2>&1; then
    echo "未检测到 Docker，请先安装 Docker Engine：https://docs.docker.com/engine/install/" >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "未检测到 Docker Compose 插件，请先安装 docker-compose-plugin。" >&2
    exit 1
fi

replace_env() {
    key=$1
    value=$2
    temp_file=$(mktemp "${TMPDIR:-/tmp}/learning-os-env.XXXXXX")
    awk -v key="$key" -v value="$value" '
        BEGIN { found = 0 }
        index($0, key "=") == 1 { print key "=" value; found = 1; next }
        { print }
        END { if (!found) print key "=" value }
    ' .env > "$temp_file"
    chmod 600 "$temp_file"
    mv "$temp_file" .env
}

random_hex() {
    bytes=$1
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "$bytes"
    else
        od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
    fi
}

if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    replace_env DJANGO_SECRET_KEY "$(random_hex 48)"
    replace_env DJANGO_DEBUG false
    replace_env DJANGO_ALLOWED_HOSTS "$public_host,127.0.0.1,localhost"
    if [ "$public_host" = "localhost" ]; then
        replace_env CSRF_TRUSTED_ORIGINS "http://localhost,http://127.0.0.1"
        replace_env DJANGO_SECURE_SSL_REDIRECT false
    else
        replace_env CSRF_TRUSTED_ORIGINS "https://$public_host"
        replace_env DJANGO_SECURE_SSL_REDIRECT true
    fi
    replace_env POSTGRES_PASSWORD "$(random_hex 32)"
    echo "已生成权限为 600 的 .env。"
else
    echo "检测到现有 .env，将保留其中的密钥和配置。"
fi

if [ "$database_mode" = "postgres" ]; then
    if ! grep -Eq '^POSTGRES_PASSWORD=.+$' .env; then
        replace_env POSTGRES_PASSWORD "$(random_hex 32)"
    fi
    set -- -f compose.yaml -f compose.postgres.yaml
    echo "正在使用 PostgreSQL 构建 Personal Learning OS..."
else
    set -- -f compose.yaml
    echo "正在使用持久化 SQLite 构建 Personal Learning OS..."
fi

docker compose "$@" up -d --build

attempt=0
until docker compose "$@" exec -T web python -c "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/admin/login/', headers={'X-Forwarded-Proto':'https'}); urllib.request.urlopen(request, timeout=3)" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 40 ]; then
        echo "服务未能在预期时间内就绪，请运行 docker compose logs web 查看日志。" >&2
        exit 1
    fi
    sleep 2
done

user_count=$(docker compose "$@" exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())" | tail -1)
if [ "$user_count" = "0" ]; then
    admin_user=${ADMIN_USERNAME:-admin}
    admin_password=$(random_hex 12)
    docker compose "$@" exec -T -e DJANGO_SUPERUSER_PASSWORD="$admin_password" web \
        python manage.py createsuperuser --noinput --username "$admin_user" \
        --email "${ADMIN_EMAIL:-${admin_user}@localhost.invalid}"
    echo "首次管理员：$admin_user"
    echo "首次密码（仅显示这一次）：$admin_password"
    echo "登录后请立即修改密码并绑定 Passkey。"
fi

port=$(awk -F= '$1 == "TRACKER_PORT" { print $2; exit }' .env)
port=${port:-8000}
echo "安装完成：http://127.0.0.1:${port}"
echo "查看日志：docker compose $* logs -f web"
echo "启用 MCP：docker compose $* --profile mcp up -d"
