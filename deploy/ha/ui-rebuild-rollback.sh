#!/bin/sh
# Application-only rollback. Never restore the DB over newer learning records.
set -eu
backup=${1:?Usage: ui-rebuild-rollback.sh /absolute/verified-backup-directory}
case "$backup" in /var/snap/docker/common/time-tracker-ha/backups/ui-rebuild-*) ;; *) echo 'Unexpected backup location' >&2; exit 2;; esac
test -r "$backup/web-service-dropins/20-local-ports.conf"
test -r "$backup/previous-image-id.txt"
image_id=$(cat "$backup/previous-image-id.txt")
/usr/local/bin/time-tracker-docker image inspect "$image_id" >/dev/null
systemctl disable --now time-tracker-search-queue.timer 2>/dev/null || true
systemctl stop time-tracker-search-queue.service 2>/dev/null || true
cp -p "$backup/web-service-dropins/20-local-ports.conf" /etc/systemd/system/time-tracker-ha-web.service.d/20-local-ports.conf
if test -d "$backup/pwa"; then
 stage=/var/www/time-tracker-pwa.rollback-stage
 test ! -e "$stage"
 cp -a "$backup/pwa" "$stage"
 old=/var/www/time-tracker-pwa.before-rollback-$(date -u +%Y%m%dT%H%M%SZ)
 mv /var/www/time-tracker-pwa "$old"
 mv "$stage" /var/www/time-tracker-pwa
fi
systemctl daemon-reload
systemctl restart time-tracker-ha-web.service
n=0
until /usr/local/bin/time-tracker-docker inspect time-tracker-ha-web --format '{{.State.Health.Status}}' 2>/dev/null | grep -qx healthy; do
 n=$((n+1)); test "$n" -lt 24 || { echo 'Health check failed; inspect service logs' >&2; exit 1; }
 sleep 5
done
printf 'Previous application restored; additive search tables retained. No learning data restored.\n'
