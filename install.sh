#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"

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
    temp_file=$(mktemp "${TMPDIR:-/tmp}/time-tracker-env.XXXXXX")
    awk -v key="$key" -v value="$value" '
        BEGIN { found = 0 }
        index($0, key "=") == 1 {
            print key "=" value
            found = 1
            next
        }
        { print }
        END {
            if (!found) print key "=" value
        }
    ' .env > "$temp_file"
    chmod 600 "$temp_file"
    mv "$temp_file" .env
}

if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env

    if command -v openssl >/dev/null 2>&1; then
        django_secret=$(openssl rand -hex 48)
        tracker_token=$(openssl rand -hex 32)
    else
        django_secret=$(od -An -N48 -tx1 /dev/urandom | tr -d ' \n')
        tracker_token=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
    fi

    public_host=${1:-localhost}
    replace_env DJANGO_SECRET_KEY "$django_secret"
    replace_env DJANGO_DEBUG false
    replace_env DJANGO_ALLOWED_HOSTS "$public_host,127.0.0.1,localhost"
    replace_env TRACKER_API_TOKEN "$tracker_token"
    echo "已生成 .env；Authorization 访问令牌保存在 TRACKER_API_TOKEN 中。"
else
    echo "检测到现有 .env，将保留其中的密钥和配置。"
fi

echo "正在构建并启动 Time Tracker..."
docker compose up -d --build

attempt=0
until docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/admin/login/', timeout=3)" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "服务未能在预期时间内就绪，请运行 docker compose logs web 查看日志。" >&2
        exit 1
    fi
    sleep 2
done

port=$(awk -F= '$1 == "TRACKER_PORT" { print $2; exit }' .env)
port=${port:-8000}
echo "安装完成：http://127.0.0.1:${port}"
echo "查看日志：docker compose logs -f web"
echo "启用 MCP：docker compose --profile mcp up -d"
