"""Derive rates and utilization from cumulative Linux/PostgreSQL counters."""

from __future__ import annotations

import json
from typing import Any


def _delta(current, previous, name):
    try:
        return float(current[name]) - float(previous[name])
    except (KeyError, TypeError, ValueError):
        return None


def _rate(current, previous, name, elapsed):
    value = _delta(current, previous, name)
    return value / elapsed if value is not None and elapsed > 0 else None


def _round(value):
    return round(value, 4) if value is not None else None


def flatten_metrics(payload: dict[str, Any], previous: dict[str, Any] | None,
                    elapsed_seconds: float, *, offset_seconds: float,
                    stage: str, normal_page=None, db_elapsed_seconds=None):
    cpu = payload.get('cpu') or {}
    memory = payload.get('memory') or {}
    network = payload.get('network') or {}
    tcp = payload.get('tcp') or {}
    processes = payload.get('processes') or {}
    previous = previous or {}
    previous_cpu = previous.get('cpu') or {}
    total_delta = _delta(cpu, previous_cpu, 'total')

    def cpu_share(field):
        value = _delta(cpu, previous_cpu, field)
        return value / total_delta * 100 if value is not None and total_delta and total_delta > 0 else None

    idle_share = cpu_share('idle_total')
    cpu_percent = 100 - idle_share if idle_share is not None else None
    previous_cores = {
        row.get('core'): row for row in (previous_cpu.get('per_core') or [])
    }
    per_core_percent = {}
    for core in cpu.get('per_core') or []:
        prior_core = previous_cores.get(core.get('core')) or {}
        core_total = _delta(core, prior_core, 'total')
        core_idle = _delta(core, prior_core, 'idle_total')
        if core_total and core_idle is not None:
            per_core_percent[core.get('core')] = round(
                max(0, min(100, (core_total - core_idle) / core_total * 100)), 4,
            )
    primary = network.get('primary_interface')
    net = (network.get('interfaces') or {}).get(primary, {})
    previous_net = (
        ((previous.get('network') or {}).get('interfaces') or {}).get(primary, {})
        if primary else {}
    )
    tx_bytes_per_second = _rate(net, previous_net, 'tx_bytes', elapsed_seconds)
    rx_bytes_per_second = _rate(net, previous_net, 'rx_bytes', elapsed_seconds)

    clock_ticks = float(cpu.get('clock_ticks_per_second') or 100)

    def process_cpu(group):
        current_group = processes.get(group) or {}
        previous_group = (previous.get('processes') or {}).get(group) or {}
        user = _delta(current_group, previous_group, 'user_ticks')
        system = _delta(current_group, previous_group, 'system_ticks')
        if user is None or system is None or elapsed_seconds <= 0:
            return None
        # May exceed 100% for a group using more than one core.
        return (user + system) / clock_ticks / elapsed_seconds * 100

    row = {
        'offset_seconds': round(offset_seconds, 3),
        'stage': stage,
        'cpu_percent': _round(cpu_percent),
        'cpu_user_percent': _round(cpu_share('user')),
        'cpu_system_percent': _round(cpu_share('system')),
        'cpu_iowait_percent': _round(cpu_share('iowait')),
        'cpu_steal_percent': _round(cpu_share('steal')),
        'cpu_single_core_peak_percent': max(per_core_percent.values(), default=None),
        'cpu_per_core_percent_json': json.dumps(per_core_percent, sort_keys=True),
        'load_1': (cpu.get('load_average') or [None])[0],
        'load_5': (cpu.get('load_average') or [None, None])[1],
        'runnable_processes': cpu.get('runnable_processes'),
        'process_count': cpu.get('process_count'),
        'context_switches_per_second': _round(_rate(cpu, previous_cpu, 'context_switches', elapsed_seconds)),
        'memory_total_mb': memory.get('total_mb'),
        'memory_available_mb': memory.get('available_mb'),
        'memory_used_percent': memory.get('used_percent'),
        'swap_used_mb': memory.get('swap_used_mb'),
        'network_interface': primary,
        'network_tx_mbps': _round(tx_bytes_per_second * 8 / 1_000_000 if tx_bytes_per_second is not None else None),
        'network_rx_mbps': _round(rx_bytes_per_second * 8 / 1_000_000 if rx_bytes_per_second is not None else None),
        'network_tx_packets_per_second': _round(_rate(net, previous_net, 'tx_packets', elapsed_seconds)),
        'network_rx_packets_per_second': _round(_rate(net, previous_net, 'rx_packets', elapsed_seconds)),
        'tcp_public_established': tcp.get('public_established'),
        'tcp_gunicorn_established': tcp.get('gunicorn_established'),
        'gunicorn_listen_queue': tcp.get('gunicorn_listen_queue'),
        'gunicorn_processes': (processes.get('gunicorn') or {}).get('process_count'),
        'gunicorn_workers': (processes.get('gunicorn') or {}).get('worker_process_count'),
        'gunicorn_rss_mb': (processes.get('gunicorn') or {}).get('rss_mb'),
        'gunicorn_cpu_percent': _round(process_cpu('gunicorn')),
        'nginx_processes': (processes.get('nginx') or {}).get('process_count'),
        'nginx_rss_mb': (processes.get('nginx') or {}).get('rss_mb'),
        'nginx_cpu_percent': _round(process_cpu('nginx')),
        'postgres_processes': (processes.get('postgres') or {}).get('process_count'),
        'postgres_rss_mb': (processes.get('postgres') or {}).get('rss_mb'),
        'postgres_cpu_percent': _round(process_cpu('postgres')),
        'normal_page_status': normal_page.get('status') if normal_page else None,
        'normal_page_latency_ms': normal_page.get('latency_ms') if normal_page else None,
        'normal_page_success_percent': (
            100.0 if normal_page and 200 <= normal_page.get('status', 0) < 400 else 0.0
        ) if normal_page else None,
    }

    database = payload.get('database') or {}
    previous_database = previous.get('database') or {}
    if database:
        db_elapsed_seconds = db_elapsed_seconds or elapsed_seconds
        db = database.get('database') or {}
        prior_db = previous_database.get('database') or {}
        activity = database.get('activity') or {}
        locks = database.get('locks') or {}
        statements = database.get('pg_stat_statements') or {}
        prior_statements = previous_database.get('pg_stat_statements') or {}
        wal = database.get('wal') or {}
        prior_wal = previous_database.get('wal') or {}
        checkpoints = database.get('checkpoints') or {}
        prior_checkpoints = previous_database.get('checkpoints') or {}
        tables = database.get('tables') or {}
        hit = _delta(db, prior_db, 'blks_hit')
        read = _delta(db, prior_db, 'blks_read')
        row.update({
            'db_connections': activity.get('connections'),
            'db_active': activity.get('active'),
            'db_waiting': activity.get('waiting'),
            'db_lock_waiting': max(activity.get('lock_waiting') or 0, locks.get('ungranted') or 0),
            'db_max_connections': activity.get('max_connections'),
            'db_connection_utilization_percent': _round(
                activity.get('connections', 0) / activity.get('max_connections', 1) * 100
                if activity.get('max_connections') else None
            ),
            'db_transactions_per_second': _round(
                sum(value or 0 for value in (
                    _rate(db, prior_db, 'xact_commit', db_elapsed_seconds),
                    _rate(db, prior_db, 'xact_rollback', db_elapsed_seconds),
                )) if prior_db else None
            ),
            'db_statements_per_second': _round(
                _rate(statements, prior_statements, 'calls', db_elapsed_seconds)
            ),
            'db_rows_returned_per_second': _round(_rate(db, prior_db, 'tup_returned', db_elapsed_seconds)),
            'db_rows_fetched_per_second': _round(_rate(db, prior_db, 'tup_fetched', db_elapsed_seconds)),
            'db_rows_written_per_second': _round(
                sum(value or 0 for value in (
                    _rate(db, prior_db, 'tup_inserted', db_elapsed_seconds),
                    _rate(db, prior_db, 'tup_updated', db_elapsed_seconds),
                    _rate(db, prior_db, 'tup_deleted', db_elapsed_seconds),
                )) if prior_db else None
            ),
            'db_cache_hit_percent': _round(hit / (hit + read) * 100 if hit is not None and read is not None and hit + read > 0 else None),
            'db_temp_bytes_per_second': _round(_rate(db, prior_db, 'temp_bytes', db_elapsed_seconds)),
            'db_deadlocks_delta': _delta(db, prior_db, 'deadlocks'),
            'db_wal_bytes_per_second': _round(_rate(wal, prior_wal, 'wal_bytes', db_elapsed_seconds)),
            'db_checkpoints_timed_delta': _delta(checkpoints, prior_checkpoints, 'checkpoints_timed'),
            'db_checkpoints_requested_delta': _delta(checkpoints, prior_checkpoints, 'checkpoints_req'),
            'db_checkpoint_write_ms_per_second': _round(
                _rate(checkpoints, prior_checkpoints, 'checkpoint_write_time', db_elapsed_seconds)
            ),
            'db_checkpoint_sync_ms_per_second': _round(
                _rate(checkpoints, prior_checkpoints, 'checkpoint_sync_time', db_elapsed_seconds)
            ),
            'db_live_tuples': tables.get('live_tuples'),
            'db_dead_tuples': tables.get('dead_tuples'),
            'db_seq_scans': tables.get('seq_scans'),
            'db_index_scans': tables.get('index_scans'),
            'db_autovacuum_count': tables.get('autovacuum_count'),
            'db_autoanalyze_count': tables.get('autoanalyze_count'),
            'db_top_statements_json': json.dumps(
                database.get('top_statements') or [], sort_keys=True,
            ),
            'db_size_bytes': db.get('database_size_bytes'),
        })
    return row
