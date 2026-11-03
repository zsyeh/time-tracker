#!/bin/sh
set -eu

writer=${TIME_TRACKER_WRITER_SSH:-root@47.95.10.128}
edge=${TIME_TRACKER_EDGE_SSH:-}

echo '47 writer role:'
ssh "$writer" "set -a; . /var/snap/docker/common/time-tracker-ha/secrets/database.env; set +a; psql \"\$DATABASE_URL\" -Atqc \"select inet_server_addr(), inet_server_port(), pg_is_in_recovery(), current_setting('transaction_read_only')\""
echo '47 application services/listeners:'
ssh "$writer" "systemctl is-active time-tracker-ha-postgres.service time-tracker-ha-web.service; ss -lnt | grep -E ':(443|5432|55432|55433|18000) '"

if [ -n "$edge" ]; then
    echo 'RainYun must be edge-only (no local PostgreSQL/Django listeners):'
    ssh "$edge" "if ss -lnt | grep -E ':(5432|55433|8000|18000) '; then exit 9; fi; nginx -T 2>/dev/null | grep -F '47.95.10.128:443'"
else
    echo 'Set TIME_TRACKER_EDGE_SSH to audit the RainYun node.'
fi
