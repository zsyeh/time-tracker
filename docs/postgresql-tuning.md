# PostgreSQL VPS baseline and tuning

This document records the measured production baseline and the deliberately
small PostgreSQL configuration applied on 2026-08-11. It is not a reusable
"best settings" template for other servers.

## Measured environment

| Resource | Measurement |
| --- | --- |
| PostgreSQL | 15.18, Debian 12 package |
| Memory | 1.9 GiB total; 942 MiB available after PostgreSQL installation; no swap |
| CPU | 2 KVM vCPUs, Intel Xeon E5-2680 v4 |
| Disk | 30 GiB ext4; 16 GiB free after installation |
| Storage presentation | QEMU virtual block device reporting rotational media; not proven SSD/NVMe |
| Application memory | systemd cgroups: web 126 MiB + MCP 85 MiB (about 212 MiB total at measurement time) |
| Application concurrency | 2 synchronous Gunicorn workers + 1 MCP process; active-minute HTTP p50 2, p95 12, with one 678-request scan burst |
| Source database | SQLite, 492 KiB, 136 TimeLog rows, 260 exported Django objects |
| Existing disk consumers | application tree 623 MiB, `/var/log` 3.0 GiB, Docker data 3.0 GiB |
| PostgreSQL immediately after install | about 23 MiB resident cgroup memory; 39 MiB cluster directory; 17 MiB WAL directory |

Nginx rotates 14 logs. PostgreSQL logs rotate weekly with 10 retained compressed
files. The persistent journal was 2.8 GiB and uses systemd's size-aware default
cap. Logs are therefore bounded, but their current size remains a useful disk
alert signal.

## Memory and connection budget

Django uses a 60-second persistent connection lifetime; it does not create a
large connection pool. Two synchronous web workers and the MCP process normally
hold at most three application connections. Allowing for deploy commands,
background sync, an administrator and bursts, 20 total PostgreSQL connections
is ample. PostgreSQL keeps its default three superuser-reserved connections, so
17 regular slots remain.

`work_mem` is charged per sort/hash execution node and may be used several times
inside one query. It is therefore 2 MiB, not a percentage of total RAM. The
128 MiB shared buffer default is retained. `autovacuum_work_mem = -1` remains in
place and inherits the reduced 32 MiB maintenance budget. `temp_buffers` remains
8 MiB per session and is allocated only when temporary tables are used.

This leaves substantial room for the kernel, filesystem cache, Django, Gunicorn,
PostgreSQL backend private memory, SSH and other system services. No swap was
added as part of this database migration; sustained reductions in
`MemAvailable`, application growth or additional workers require another budget
review before raising any PostgreSQL memory value.

## Parameter decisions

| Parameter | Original | New | Reason / expected effect | Apply |
| --- | ---: | ---: | --- | --- |
| `shared_buffers` | 128 MiB | unchanged | Conservative for 1.9 GiB shared VPS; no evidence supports 256 MiB | none |
| `effective_cache_size` | 4 GiB | 768 MiB | Make planner estimate credible; this allocates no memory | reload |
| `work_mem` | 4 MiB | 2 MiB | Bound per-node sort/hash memory under concurrent queries | reload |
| `maintenance_work_mem` | 64 MiB | 32 MiB | Small database does not need a larger VACUUM/index-build budget | reload |
| `autovacuum_work_mem` | -1 | unchanged | Inherits 32 MiB; no dead-tuple pressure justifies a separate value | none |
| `temp_buffers` | 8 MiB | unchanged | No temporary-table workload observed | none |
| `max_connections` | 100 | 20 | Real workload needs about 3 persistent connections; preserve admin/deploy margin without funding 100 backends | restart |
| `temp_file_limit` | unlimited | 128 MiB/backend | Prevent one accidental spill from consuming the VPS disk | reload |
| `shared_preload_libraries` | empty | `pg_stat_statements` | Collect low-overhead evidence for future changes | restart |
| `pg_stat_statements.max` | extension default 5000 | 1000 | Bound monitoring shared memory for a small query set | restart |
| `max_wal_size` | 1 GiB | unchanged | 16 GiB is free and write volume is tiny; no evidence supports checkpoint/WAL changes | none |
| `min_wal_size` | 80 MiB | unchanged | Default fits the workload | none |
| `checkpoint_timeout` | 5 min | unchanged | No checkpoint pressure demonstrated | none |
| `checkpoint_completion_target` | 0.9 | unchanged | Safe default | none |
| `wal_buffers` | auto (4 MiB runtime) | unchanged | No WAL-buffer pressure demonstrated | none |
| autovacuum thresholds/workers | PostgreSQL defaults | unchanged | Tiny database has no dead-tuple evidence requiring aggressive vacuum | none |
| `random_page_cost` / `effective_io_concurrency` | 4 / 1 | unchanged | Virtual disk reports rotational; change only after real `EXPLAIN (ANALYZE, BUFFERS)` evidence | none |
| join/scan method switches | enabled | unchanged | Planner methods must not be disabled to force a plan | none |
| `fsync` / `synchronous_commit` / `full_page_writes` | on / on / on | unchanged | Data durability is not traded for marginal write speed | none |

The active settings live in
[`deploy/postgresql/99-time-tracker.conf`](../deploy/postgresql/99-time-tracker.conf).
They intentionally omit every unchanged setting.

The native service connects through the local Unix socket using peer
authentication (`DATABASE_URL=postgresql:///time_tracker`). PostgreSQL listens
only on localhost. The matching `root` database role is an application role: it
can log in but is not a PostgreSQL superuser and cannot create roles, databases,
or replication slots. The selector is stored in the ignored, mode-`600`
`.env.database` overlay; no database password is stored in the repository.

## Disk budget

The filesystem had 16 GiB free before application data import. PostgreSQL
packages added about 199 MiB and the empty cluster used 39 MiB. The migrated
database was 9.4 MiB immediately after import. The unchanged
1 GiB `max_wal_size` is not a reservation or a hard cap, so monitoring must allow
for temporary WAL overshoot. A 128 MiB per-backend temporary-file limit bounds a
single bad query but is not a global cap; at the realistic three application
backends the spill exposure is about 384 MiB.

Keep at least 8 GiB filesystem headroom for WAL bursts, package operations,
backups and logs. Investigate before `/` exceeds 70%, and stop nonessential
writes before 85%. Backups must be rotated and restore-tested; do not store an
unbounded sequence of dumps on this filesystem.

## Apply and rollback

Install the versioned file and restart once (the restart is required for
`max_connections` and `shared_preload_libraries`):

```bash
sudo install -m 0644 deploy/postgresql/99-time-tracker.conf \
  /etc/postgresql/15/main/conf.d/99-time-tracker.conf
sudo pg_ctlcluster 15 main restart
sudo -u postgres psql -d time_tracker -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements;'
```

The pre-change values are stored with the migration backup as
`postgresql-settings.before.txt`. To restore all package defaults, remove only
the isolated override and restart:

```bash
sudo rm /etc/postgresql/15/main/conf.d/99-time-tracker.conf
sudo pg_ctlcluster 15 main restart
```

This does not delete the database or application data. Verify rollback with
`SELECT name, setting, unit, source FROM pg_settings ...`; `max_connections`
should return to 100, `work_mem` to 4 MiB, and `shared_preload_libraries` to
empty.

## Measure after changes

Run the bundled low-overhead report:

```bash
sudo -u postgres psql -d time_tracker \
  < deploy/postgresql/monitor.sql
```

Useful focused commands:

```bash
# Database and relation sizes
sudo -u postgres psql -d time_tracker -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
sudo -u postgres psql -d time_tracker -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"

# Connections, cache hits, temporary files and dead tuples
sudo -u postgres psql -d time_tracker -c "SELECT state,count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY state;"
sudo -u postgres psql -d time_tracker -c "SELECT blks_hit,blks_read,temp_files,temp_bytes,deadlocks FROM pg_stat_database WHERE datname=current_database();"
sudo -u postgres psql -d time_tracker -c "SELECT relname,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;"

# Current vacuum and checkpoint/WAL state
sudo -u postgres psql -d time_tracker -c "SELECT * FROM pg_stat_progress_vacuum;"
sudo -u postgres psql -d time_tracker -c "SELECT checkpoints_timed,checkpoints_req,buffers_checkpoint,buffers_backend,buffers_backend_fsync FROM pg_stat_bgwriter;"
sudo du -sh /var/lib/postgresql/15/main/pg_wal /var/log/postgresql /var/log/journal

# Statements consuming the most total execution time
sudo -u postgres psql -d time_tracker -c "SELECT calls,round(total_exec_time::numeric,2) total_ms,round(mean_exec_time::numeric,2) mean_ms,left(query,200) FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;"
```

Use `EXPLAIN (ANALYZE, BUFFERS)` only on a specific slow query identified by
measurement. Re-check the memory budget before adding Gunicorn workers,
increasing `max_connections`, or raising any per-operation memory setting. If
connection demand eventually becomes genuinely high, measure it first and then
evaluate PgBouncer rather than preallocating hundreds of PostgreSQL backends.

## Post-change verification (2026-08-11)

- A preflight fixture was migrated into a temporary PostgreSQL database before
  downtime. The final migration imported 260 objects; all 19 model counts,
  completed-session seconds and the running-session count matched SQLite.
- A custom-format PostgreSQL dump was restored into a fresh temporary database.
  The same counts and duration totals matched again before that temporary
  database was removed.
- The production database measured 9,821,543 bytes (9.4 MiB). Initial statistics
  showed a 99.65% cache hit ratio, zero temporary files, zero deadlocks and zero
  dead tuples. `pg_stat_statements` was reset once after migration so ongoing
  reports are not dominated by schema creation and fixture import.
- At steady state PostgreSQL used about 59 MiB of cgroup memory, Web + MCP used
  about 183 MiB, and Linux reported 996 MiB available. The PostgreSQL cluster
  directory was 64 MiB and the filesystem still had 16 GiB free.
- The frontend production build temporarily used about 725 MiB and reduced
  available memory to 206 MiB because this host has no swap. That transient build
  pressure is separate from PostgreSQL: prefer CI/off-host image builds as the
  frontend grows, and do not raise database memory settings to consume the
  steady-state headroom.
- All changed settings reported `pending_restart = false`; 49 Django tests,
  20 frontend tests, TypeScript checking, the production build, Django deploy
  checks and the HTTPS-aware smoke test passed. The deploy check retains two
  existing warnings because HSTS subdomain inclusion and preload remain
  deliberately disabled.
