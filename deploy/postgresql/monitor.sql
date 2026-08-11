\pset pager off
\set ON_ERROR_STOP on

-- Run as a role that can read cluster statistics, for example:
-- sudo -u postgres psql -d time_tracker < deploy/postgresql/monitor.sql

SELECT version();

SELECT current_database() AS database,
       pg_size_pretty(pg_database_size(current_database())) AS database_size;

SELECT relname AS relation,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_relation_size(relid)) AS table,
       pg_size_pretty(pg_indexes_size(relid)) AS indexes
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

SELECT state, count(*) AS connections
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state
ORDER BY state;

SELECT datname,
       round(100 * blks_hit::numeric / NULLIF(blks_hit + blks_read, 0), 2) AS cache_hit_percent,
       temp_files,
       pg_size_pretty(temp_bytes) AS temporary_bytes,
       deadlocks
FROM pg_stat_database
WHERE datname = current_database();

SELECT relname,
       n_live_tup,
       n_dead_tup,
       last_autovacuum,
       last_autoanalyze,
       autovacuum_count,
       autoanalyze_count
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC, relname;

SELECT pid,
       relid::regclass AS relation,
       phase,
       heap_blks_total,
       heap_blks_scanned,
       heap_blks_vacuumed
FROM pg_stat_progress_vacuum;

SELECT checkpoints_timed,
       checkpoints_req,
       checkpoint_write_time,
       checkpoint_sync_time,
       buffers_checkpoint,
       buffers_backend,
       buffers_backend_fsync,
       stats_reset
FROM pg_stat_bgwriter;

SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) AS wal_generated_since_cluster_init,
       pg_size_pretty(sum(size)) AS current_wal_directory_size
FROM pg_ls_waldir();

SELECT calls,
       round(total_exec_time::numeric, 2) AS total_exec_ms,
       round(mean_exec_time::numeric, 2) AS mean_exec_ms,
       rows,
       left(query, 240) AS query_sample
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC
LIMIT 20;

-- For a query identified above, inspect the real plan before changing planner
-- costs or indexes:
-- EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
