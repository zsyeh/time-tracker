#!/bin/sh
# Application rollback only. Keep tracker0022 and every newer study/preferences row.
set -eu
backup=${1:?Usage: round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-TIMESTAMP}
case "$backup" in /var/snap/docker/common/time-tracker-ha/backups/round2-*) ;; *) echo 'Unexpected backup directory' >&2; exit 2;; esac
for name in previous-image-id.txt web-service-dropins/20-local-ports.conf time-tracker-search-queue.service time-tracker-search-queue.timer queue-enabled.txt queue-active.txt; do test -r "$backup/$name"; done
/usr/local/bin/time-tracker-docker image inspect "$(cat "$backup/previous-image-id.txt")" >/dev/null
systemctl stop time-tracker-search-queue.timer
systemctl stop time-tracker-search-queue.service
cp -p "$backup/web-service-dropins/20-local-ports.conf" /etc/systemd/system/time-tracker-ha-web.service.d/20-local-ports.conf
cp -p "$backup/time-tracker-search-queue.service" /etc/systemd/system/time-tracker-search-queue.service
cp -p "$backup/time-tracker-search-queue.timer" /etc/systemd/system/time-tracker-search-queue.timer
if test -d "$backup/pwa"; then
 stage=/var/www/time-tracker-pwa.round2-rollback-stage
 test ! -e "$stage"
 cp -a "$backup/pwa" "$stage"
 mv /var/www/time-tracker-pwa "/var/www/time-tracker-pwa.before-round2-rollback-$(date -u +%Y%m%dT%H%M%SZ)"
 mv "$stage" /var/www/time-tracker-pwa
fi
systemctl daemon-reload
systemctl restart time-tracker-ha-web.service
n=0
until /usr/local/bin/time-tracker-docker inspect time-tracker-ha-web --format '{{.State.Health.Status}}' 2>/dev/null | grep -qx healthy; do
 n=$((n+1)); test "$n" -lt 24 || { echo 'Previous web image did not become healthy' >&2; exit 1; }
 sleep 5
done
if grep -qx enabled "$backup/queue-enabled.txt"; then systemctl enable time-tracker-search-queue.timer; else systemctl disable time-tracker-search-queue.timer; fi
if grep -qx active "$backup/queue-active.txt"; then systemctl start time-tracker-search-queue.timer; fi
printf 'Previous web/PWA/queue restored. Database and newer learning records retained.\n'
