"""Low-overhead Linux and PostgreSQL counters for capacity tests.

Only virtual procfs/sysfs files and database statistics views are read.  This
module never writes test files and does not benchmark storage.
"""

from __future__ import annotations

import os
import platform

from django.conf import settings
from django.db import connection

try:
    import resource
except ImportError:  # pragma: no cover - production is Linux.
    resource = None


CPU_FIELDS = (
    'user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal',
    'guest', 'guest_nice',
)
PROCESS_GROUPS = {'gunicorn', 'nginx', 'postgres'}


def _read_text(path: str, maximum_bytes: int = 1_000_000) -> str:
    try:
        with open(path, 'r', encoding='ascii', errors='replace') as handle:
            return handle.read(maximum_bytes)
    except OSError:
        return ''


def _cpu_metrics():
    aggregate = None
    cores = []
    context_switches = processes_started = None
    for line in _read_text('/proc/stat').splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'ctxt' and len(fields) > 1:
            context_switches = int(fields[1])
            continue
        if fields[0] == 'processes' and len(fields) > 1:
            processes_started = int(fields[1])
            continue
        if not fields[0].startswith('cpu'):
            continue
        try:
            values = [int(value) for value in fields[1:len(CPU_FIELDS) + 1]]
        except ValueError:
            continue
        values.extend([0] * (len(CPU_FIELDS) - len(values)))
        counters = dict(zip(CPU_FIELDS, values))
        # guest values are already included in user/nice, so exclude them from
        # the total to avoid double counting.
        counters['total'] = sum(values[:8])
        counters['idle_total'] = counters['idle'] + counters['iowait']
        if fields[0] == 'cpu':
            aggregate = counters
        else:
            counters['core'] = fields[0]
            cores.append(counters)

    load_average = None
    runnable = process_count = None
    load_fields = _read_text('/proc/loadavg', 256).split()
    if len(load_fields) >= 4:
        try:
            load_average = [float(value) for value in load_fields[:3]]
            runnable, process_count = [int(value) for value in load_fields[3].split('/', 1)]
        except (TypeError, ValueError):
            pass
    payload = aggregate or {}
    payload.update({
        # Backward-compatible names used by the first client.
        'total_ticks': payload.get('total'),
        'idle_ticks': payload.get('idle_total'),
        'cores': len(cores) or os.cpu_count() or 1,
        'per_core': cores,
        'load_average': load_average,
        'runnable_processes': runnable,
        'process_count': process_count,
        'context_switches': context_switches,
        'processes_started': processes_started,
        'clock_ticks_per_second': os.sysconf('SC_CLK_TCK') if hasattr(os, 'sysconf') else None,
    })
    return payload


def _memory_metrics():
    values = {}
    for line in _read_text('/proc/meminfo').splitlines():
        if ':' not in line:
            continue
        key, raw_value = line.split(':', 1)
        try:
            values[key] = int(raw_value.strip().split()[0])
        except (ValueError, IndexError):
            continue
    total_kib = values.get('MemTotal')
    available_kib = values.get('MemAvailable')
    swap_total_kib = values.get('SwapTotal')
    swap_free_kib = values.get('SwapFree')
    worker_peak_rss_mb = None
    if resource is not None:
        worker_peak_rss_mb = round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            3,
        )
    return {
        'total_mb': round(total_kib / 1024, 3) if total_kib is not None else None,
        'available_mb': round(available_kib / 1024, 3) if available_kib is not None else None,
        'used_percent': (
            round((total_kib - available_kib) / total_kib * 100, 3)
            if total_kib and available_kib is not None else None
        ),
        'swap_total_mb': round(swap_total_kib / 1024, 3) if swap_total_kib is not None else None,
        'swap_used_mb': (
            round((swap_total_kib - swap_free_kib) / 1024, 3)
            if swap_total_kib is not None and swap_free_kib is not None else None
        ),
        'worker_peak_rss_mb': worker_peak_rss_mb,
    }


def _network_metrics():
    interfaces = {}
    for line in _read_text('/proc/net/dev').splitlines()[2:]:
        if ':' not in line:
            continue
        interface, values = line.split(':', 1)
        fields = values.split()
        if len(fields) < 16:
            continue
        interface = interface.strip()
        interfaces[interface] = {
            'rx_bytes': int(fields[0]),
            'rx_packets': int(fields[1]),
            'rx_errors': int(fields[2]),
            'rx_dropped': int(fields[3]),
            'tx_bytes': int(fields[8]),
            'tx_packets': int(fields[9]),
            'tx_errors': int(fields[10]),
            'tx_dropped': int(fields[11]),
        }
    preferred = getattr(settings, 'STRESS_TEST_NETWORK_INTERFACE', '')
    if preferred not in interfaces:
        candidates = [name for name in interfaces if name != 'lo' and not name.startswith(('docker', 'veth', 'br-'))]
        preferred = max(candidates, key=lambda name: interfaces[name]['rx_bytes'], default=None)
    return {
        'primary_interface': preferred,
        'interfaces': interfaces,
        'configured_capacity_mbps': settings.STRESS_TEST_NETWORK_CAPACITY_MBPS or None,
    }


def _tcp_metrics():
    sockstat = {}
    for line in _read_text('/proc/net/sockstat', 8192).splitlines():
        if ':' not in line:
            continue
        group, values = line.split(':', 1)
        fields = values.split()
        parsed = {}
        for index in range(0, len(fields) - 1, 2):
            try:
                parsed[fields[index]] = int(fields[index + 1])
            except ValueError:
                continue
        sockstat[group.lower()] = parsed

    states = {}
    public_established = 0
    gunicorn_established = 0
    gunicorn_listen_queue = 0
    for path in ('/proc/net/tcp', '/proc/net/tcp6'):
        for line in _read_text(path).splitlines()[1:]:
            fields = line.split()
            if len(fields) < 5:
                continue
            try:
                local_port = int(fields[1].rsplit(':', 1)[1], 16)
                state = fields[3]
                _, receive_queue = fields[4].split(':', 1)
            except (ValueError, IndexError):
                continue
            states[state] = states.get(state, 0) + 1
            if state == '01' and local_port in {80, 443}:
                public_established += 1
            if state == '01' and local_port == settings.STRESS_TEST_GUNICORN_PORT:
                gunicorn_established += 1
            if state == '0A' and local_port == settings.STRESS_TEST_GUNICORN_PORT:
                gunicorn_listen_queue += int(receive_queue, 16)
    return {
        'sockstat': sockstat,
        'states_hex': states,
        'public_established': public_established,
        'gunicorn_established': gunicorn_established,
        'gunicorn_listen_queue': gunicorn_listen_queue,
        'nginx_reading_writing_waiting': None,
        'nginx_status_note': 'stub_status is not configured; public_established is a socket-count approximation.',
    }


def _process_metrics():
    page_size = os.sysconf('SC_PAGE_SIZE') if hasattr(os, 'sysconf') else 4096
    groups = {
        name: {'process_count': 0, 'user_ticks': 0, 'system_ticks': 0, 'rss_mb': 0.0}
        for name in PROCESS_GROUPS
    }
    groups['gunicorn']['worker_process_count'] = 0
    try:
        entries = os.scandir('/proc')
    except OSError:
        return groups
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            stat = _read_text(f'/proc/{entry.name}/stat', 4096)
            closing = stat.rfind(')')
            if closing < 0:
                continue
            comm = stat[stat.find('(') + 1:closing]
            group = next((name for name in PROCESS_GROUPS if comm.startswith(name)), None)
            if group is None:
                continue
            fields = stat[closing + 2:].split()
            if len(fields) < 22:
                continue
            try:
                user_ticks = int(fields[11])
                system_ticks = int(fields[12])
                rss_pages = int(fields[21])
            except ValueError:
                continue
            row = groups[group]
            row['process_count'] += 1
            row['user_ticks'] += user_ticks
            row['system_ticks'] += system_ticks
            row['rss_mb'] += rss_pages * page_size / 1024 / 1024
            if group == 'gunicorn':
                command_line = _read_text(
                    f'/proc/{entry.name}/cmdline', 16_384,
                ).replace('\x00', ' ')
                if 'gunicorn: worker' in command_line:
                    row['worker_process_count'] += 1
    for row in groups.values():
        row['rss_mb'] = round(row['rss_mb'], 3)
    return groups


def _machine_metrics():
    disk = {}
    try:
        stat = os.statvfs('/')
        disk = {
            'filesystem_total_mb': round(stat.f_blocks * stat.f_frsize / 1024 / 1024, 2),
            'filesystem_available_mb': round(stat.f_bavail * stat.f_frsize / 1024 / 1024, 2),
        }
    except OSError:
        pass
    rotational = _read_text('/sys/block/sda/queue/rotational', 16).strip()
    if rotational:
        disk['root_block_rotational_flag'] = int(rotational) if rotational.isdigit() else None
    return {
        'platform': platform.platform(),
        'kernel': platform.release(),
        'architecture': platform.machine(),
        'cpu_count': os.cpu_count() or 1,
        'disk_inventory_only': disk,
        'storage_benchmark_performed': False,
    }


def _number(value):
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _row_dict(cursor, row):
    return {
        column.name: _number(value)
        for column, value in zip(cursor.description, row)
    }


def sample_database_metrics():
    payload = {
        'backend': connection.vendor,
        'available': connection.vendor == 'postgresql',
        'statistics_overhead': 'Measured by the protected probe; sample less frequently than host metrics.',
    }
    if connection.vendor != 'postgresql':
        return payload
    statements = {
        'database': """
            SELECT numbackends, xact_commit, xact_rollback, blks_read, blks_hit,
                   tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted,
                   temp_files, temp_bytes, deadlocks, blk_read_time, blk_write_time,
                   conflicts, sessions, sessions_abandoned, sessions_fatal,
                   pg_database_size(current_database()) AS database_size_bytes
              FROM pg_stat_database WHERE datname = current_database()
        """,
        'activity': """
            SELECT count(*) AS connections,
                   count(*) FILTER (WHERE state = 'active') AS active,
                   count(*) FILTER (
                       WHERE state = 'active' AND wait_event_type IS NOT NULL
                   ) AS waiting,
                   count(*) FILTER (
                       WHERE state = 'active' AND wait_event_type = 'Lock'
                   ) AS lock_waiting,
                   current_setting('max_connections')::integer AS max_connections
              FROM pg_stat_activity WHERE datname = current_database()
        """,
        'locks': """
            SELECT count(*) AS locks,
                   count(*) FILTER (WHERE NOT granted) AS ungranted
              FROM pg_locks
        """,
        'wal': 'SELECT wal_records, wal_fpi, wal_bytes FROM pg_stat_wal',
        'checkpoints': """
            SELECT checkpoints_timed, checkpoints_req, checkpoint_write_time,
                   checkpoint_sync_time, buffers_checkpoint, buffers_clean,
                   maxwritten_clean, buffers_backend FROM pg_stat_bgwriter
        """,
        'tables': """
            SELECT coalesce(sum(n_live_tup), 0) AS live_tuples,
                   coalesce(sum(n_dead_tup), 0) AS dead_tuples,
                   coalesce(sum(seq_scan), 0) AS seq_scans,
                   coalesce(sum(idx_scan), 0) AS index_scans,
                   coalesce(sum(autovacuum_count), 0) AS autovacuum_count,
                   coalesce(sum(autoanalyze_count), 0) AS autoanalyze_count
              FROM pg_stat_user_tables
        """,
    }
    with connection.cursor() as cursor:
        for name, sql in statements.items():
            try:
                cursor.execute(sql)
                row = cursor.fetchone()
                payload[name] = _row_dict(cursor, row) if row else None
            except Exception as exc:  # Statistics differ slightly by PG release.
                connection.rollback()
                payload[name] = {'unavailable': exc.__class__.__name__}
        try:
            cursor.execute("""
                SELECT count(*) AS tracked_statements, coalesce(sum(calls), 0) AS calls,
                       coalesce(sum(total_exec_time), 0) AS total_exec_time_ms,
                       coalesce(max(max_exec_time), 0) AS maximum_exec_time_ms
                  FROM pg_stat_statements
                 WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
            """)
            payload['pg_stat_statements'] = _row_dict(cursor, cursor.fetchone())
            cursor.execute("""
                SELECT queryid, calls, rows, total_exec_time,
                       mean_exec_time, max_exec_time
                  FROM pg_stat_statements
                 WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                 ORDER BY total_exec_time DESC
                 LIMIT 10
            """)
            payload['top_statements'] = [
                _row_dict(cursor, row) for row in cursor.fetchall()
            ]
        except Exception as exc:
            connection.rollback()
            payload['pg_stat_statements'] = {'unavailable': exc.__class__.__name__}
            payload['top_statements'] = []
    return payload


def sample_system_metrics(*, include_database=False):
    payload = {
        'machine': _machine_metrics(),
        'cpu': _cpu_metrics(),
        'memory': _memory_metrics(),
        'network': _network_metrics(),
        'tcp': _tcp_metrics(),
        'processes': _process_metrics(),
        'cache': {
            'backend': settings.CACHES['default']['BACKEND'],
            'variant': settings.CACHE_BACKEND_VARIANT,
            'instrumentation': 'Per-request dashboard hit/miss is returned in X-Load-Test-Cache.',
        },
    }
    if include_database:
        payload['database'] = sample_database_metrics()
    return payload
