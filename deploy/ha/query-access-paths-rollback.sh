#!/bin/sh
# Roll back the app first, then the small index-only migration; never restore data.
set -eu
backup=${1:?Usage: query-access-paths-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-...}
case "$backup" in /var/snap/docker/common/time-tracker-ha/backups/round2-*) ;; *) exit 2;; esac
image=$(cat "$backup/query-image-name.txt")
/usr/local/bin/time-tracker-docker image inspect "$image" >/dev/null
sh "$(dirname "$0")/round2-rollback.sh" "$backup"
/usr/local/bin/time-tracker-docker run --rm --no-healthcheck --network host --cpus .5 --memory 256m \
  --env-file /var/snap/docker/common/time-tracker-ha/secrets/app.env \
  -v /var/snap/docker/common/time-tracker-ha/secrets/app.env:/app/.env:ro \
  -v /var/snap/docker/common/time-tracker-ha/secrets/database.env:/app/.env.database:ro \
  -v /var/snap/docker/common/time-tracker-ha/secrets/data-encryption.key:/app/.data-encryption.key:ro \
  --entrypoint python "$image" manage.py migrate drill 0040 --noinput
