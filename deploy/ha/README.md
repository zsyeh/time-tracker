# Current production role: 47 is the sole writer

This directory contains historical standby artifacts as well as the current
edge configuration. The authoritative production topology is now:

- `47.95.10.128`: Django, Timer, Drill, EI and the only writable PostgreSQL.
- RainYun US VPS: TLS/HTTPS edge and reverse proxy only. It must not run a
  writable application database or a local Django instance for user traffic.
- NUC: offline/content clone only; never a replication or failover writer.

The old lease, promotion, `pg_rewind`, Cloudflare failover and standby monitor
files are retained solely for historical rollback analysis. They are not the
current runbook and must not be enabled. There is no automatic promotion or
database merge path. Any future topology change requires an explicit operator
review and a fresh protection backup.

## Current files

- `nginx-standby-promoted.conf`: current 47 application ingress (legacy name).
- `nginx-rainyun-edge.conf`: edge-only proxy; all application traffic goes to 47.
- `sync-edge-certs-to-47`: renewal hook that copies only domain certificates to
  an allow-listed `/etc/nginx/certs/edge-sync/<domain>` directory. It cannot overwrite the independent
  `/etc/letsencrypt/live/47.95.10.128` IP certificate.
- `audit-single-writer.sh`: read-only role/listener audit.

Every historical HA unit is fail-closed with
`ConditionPathExists=/etc/time-tracker/legacy-ha-explicitly-enabled`. Do not
create that marker in the current architecture.

## Safety invariants

1. Do not start PostgreSQL as a writer anywhere except 47.
2. Do not enable bidirectional replication, conflict merging, or automatic
   promotion of the former writer.
3. RainYun must proxy reads and writes alike to 47; even Django session reads
   may mutate state in some configurations.
4. Backups are restore inputs, never synchronization inputs for a live DB.
5. Production migrations and service restarts require explicit authorization.

## Final exam-format import (2026-11-10)

The production exam-format table includes all 8,635 candidates, including 901
unknown labels and 4,357 audit flags. Migrations 0032 and 0033 are additive;
legacy question types and learning records are preserved. The full import,
idempotence and rollback were rehearsed using an isolated PostgreSQL metadata
fixture before the production dry-run and transactional import.

The effective application image is configured in
`/etc/systemd/system/time-tracker-ha-web.service.d/20-local-ports.conf`.
During this deployment Snap-wrapped Docker client commands repeatedly stalled;
the application launcher now uses `/usr/local/bin/time-tracker-docker`, a
standalone client connected to the same Snap Docker daemon. The companion
`25-native-client.conf` overrides only start-preparation and stop commands.
Future image updates should continue to edit the image in `20-local-ports.conf`.
The PostgreSQL container was not restarted.

The production backup and classification rollback manifest are kept under
`/var/snap/docker/common/time-tracker-ha/backups/examtypes-20261110/`.
An offsite archive copy may replace the large raw dump after the NUC verifies
its complete decompressed SHA-256; the classification rollback manifest stays
on 47. Use the classification rollback for reverting labels without replacing
subsequent learning records. See `docs/exam-type-classification.md` for commands.
