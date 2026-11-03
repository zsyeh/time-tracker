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
