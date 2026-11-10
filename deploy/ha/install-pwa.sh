#!/bin/bash
# Install only public PWA files and add static locations to the existing origin.
# Does not replace proxy, auth, certificate or application routing configuration.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Run as root on the 47 origin.' >&2; exit 1; }
SOURCE=$(cd "$(dirname "$0")/.." && pwd)
CONF=/etc/nginx/conf.d/time-tracker-ha.conf
ASSETS=/var/www/time-tracker-pwa
SNIPPET=/etc/nginx/time-tracker-ha/pwa.conf
BACKUP=${PWA_BACKUP_DIR:-/var/snap/docker/common/time-tracker-ha/backups/pwa-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$BACKUP"
[ ! -e "$BACKUP/nginx.conf.before" ] || { echo 'Use a fresh backup directory.' >&2; exit 1; }
cp -a "$CONF" "$BACKUP/nginx.conf.before"
if [ -e "$SNIPPET" ]; then cp -a "$SNIPPET" "$BACKUP/pwa.conf.before"; fi
if [ -d "$ASSETS" ]; then cp -a "$ASSETS" "$BACKUP/assets.before"; fi
rollback() {
    cp -a "$BACKUP/nginx.conf.before" "$CONF"
    if [ -e "$BACKUP/pwa.conf.before" ]; then cp -a "$BACKUP/pwa.conf.before" "$SNIPPET"; else rm -f "$SNIPPET"; fi
    rm -rf "$ASSETS"
    if [ -d "$BACKUP/assets.before" ]; then cp -a "$BACKUP/assets.before" "$ASSETS"; fi
    nginx -t && systemctl reload nginx
}
trap 'rollback' ERR
install -d -m 755 "$ASSETS" "$(dirname "$SNIPPET")"
for file in manifest.webmanifest navigation.js icon-180.png icon-192.png icon-512.png; do
    install -m 644 "$SOURCE/pwa/$file" "$ASSETS/$file.new"
    mv "$ASSETS/$file.new" "$ASSETS/$file"
done
install -m 644 "$SOURCE/ha/nginx-pwa.conf" "$SNIPPET"
python3 - "$CONF" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
for host in ['47.95.10.128','timer.ehzsy.site','drill.ehzsy.site','ei.ehzsy.site']:
    assert f'server_name {host};' in s, f'Unexpected deployment: {host}'
include='    include /etc/nginx/time-tracker-ha/pwa.conf;'
if include not in s:
    marker='    client_max_body_size 4m;'
    assert s.count(marker)==5, 'Inspect changed server layout before installing'
    s=s.replace(marker,marker+'\n'+include)
assert s.count(include)==5, 'Unexpected PWA include count'
p.write_text(s)
PY
nginx -t
systemctl reload nginx
trap - ERR
printf 'PWA static configuration installed. Backup: %s\n' "$BACKUP"
