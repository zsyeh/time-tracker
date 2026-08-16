"""Pure analysis helpers for repeatable capacity reports."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any


# Audit-derived amplification for the current Vue implementation.  A dashboard
# navigation can reuse the SPA payload (low) or involve a reload (high).
AMPLIFICATION_MODEL = {
    'logical_profile_interpretation': (
        'The six dashboard/stat/heatmap observations are one consolidated '
        'overview operation; review and Markdown reuse the same detail payload.'
    ),
    'current_origin_requests_per_dau_low': 107,
    'current_origin_requests_per_dau_high': 131,
    'current_high_request_breakdown': {
        'dashboard_overview': 55,
        'auth_session': 8,
        'session_start': 4,
        'session_finish': 4,
        'history': 8,
        'session_detail_markdown': 12,
        'session_review_read': 12,
        'session_review_write': 12,
        'search': 8,
        'issues': 4,
        'share_management': 2,
        'public_share': 2,
    },
    'optimized_origin_requests_per_dau_low': 99,
    'optimized_origin_requests_per_dau_high': 115,
    'authenticated_requests_current_low': 103,
    'authenticated_requests_current_high': 127,
    'current_session_write_amplification': (
        'SESSION_SAVE_EVERY_REQUEST=True can add one django_session UPDATE to '
        'nearly every authenticated origin request.'
    ),
    'finish_chain_requests': 3,
    'finish_chain': ['POST finish', 'GET dashboard overview', 'GET auth/session'],
    'finish_external_side_effect_note': (
        'Synthetic users execute all local Session/cache/statistics work, but '
        'GitHub outbox dispatch is deliberately suppressed so a production '
        'capacity test cannot publish synthetic Markdown.'
    ),
}


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    value = ordered[lower]
    if upper != lower:
        value += (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


def distribution(values: list[float]) -> dict[str, float | None]:
    return {
        'count': len(values),
        'min': round(min(values), 3) if values else None,
        'average': round(sum(values) / len(values), 3) if values else None,
        'p50': percentile(values, 0.50),
        'p90': percentile(values, 0.90),
        'p95': percentile(values, 0.95),
        'p99': percentile(values, 0.99),
        'p99_9': percentile(values, 0.999),
        'max': round(max(values), 3) if values else None,
    }


def _metric_values(rows, name):
    return [float(row[name]) for row in rows if row.get(name) is not None]


def summarize_stages(requests: list[dict[str, Any]], metrics: list[dict[str, Any]]):
    grouped_requests = defaultdict(list)
    grouped_metrics = defaultdict(list)
    for row in requests:
        grouped_requests[row['stage']].append(row)
    for row in metrics:
        grouped_metrics[row.get('stage', '')].append(row)

    summaries = []
    for stage, rows in grouped_requests.items():
        samples = grouped_metrics.get(stage, [])
        successes = [
            row for row in rows
            if 200 <= int(row.get('status', 0)) < 400 and not row.get('error')
        ]
        elapsed = max(
            0.001,
            max(float(row.get('offset_seconds', 0)) for row in rows)
            - min(float(row.get('offset_seconds', 0)) for row in rows),
        ) if len(rows) > 1 else 1.0
        offered_qps = float(rows[0].get('offered_qps') or 0)
        statuses = Counter(str(row.get('error') or row.get('status') or 'network_error') for row in rows)
        summary = {
            'stage': stage,
            'scenario': rows[0].get('scenario'),
            'endpoint': rows[0].get('endpoint', 'mixed'),
            'offered_qps': offered_qps,
            'attempted': len(rows),
            'successful': len(successes),
            'successful_qps': round(len(successes) / elapsed, 3),
            'error_rate_percent': round((len(rows) - len(successes)) / len(rows) * 100, 3),
            'status_counts': dict(statuses),
            'client_dropped_arrivals': sum(
                row.get('error') == 'client_vu_busy' for row in rows
            ),
            'total_ms': distribution(_metric_values(successes, 'total_ms')),
            'queue_ms': distribution(_metric_values(successes, 'queue_ms')),
            'app_wall_ms': distribution(_metric_values(successes, 'app_wall_ms')),
            'app_non_db_wall_ms': distribution(_metric_values(successes, 'app_non_db_wall_ms')),
            'client_edge_residual_ms': distribution(_metric_values(successes, 'client_edge_residual_ms')),
            'cpu_ms': distribution(_metric_values(successes, 'cpu_ms')),
            'db_ms': distribution(_metric_values(successes, 'db_ms')),
            'db_queries': distribution(_metric_values(successes, 'db_queries')),
            'db_writes': distribution(_metric_values(successes, 'db_writes')),
            'json_render_ms': distribution(_metric_values(successes, 'json_render_ms')),
            'response_bytes': distribution(_metric_values(successes, 'response_bytes')),
            'cache_hits': sum(row.get('cache') == 'hit' for row in successes),
            'cache_misses': sum(row.get('cache') == 'miss' for row in successes),
            'cpu_average_percent': _average(_metric_values(samples, 'cpu_percent')),
            'cpu_peak_percent': _maximum(_metric_values(samples, 'cpu_percent')),
            'single_core_peak_percent': _maximum(
                _metric_values(samples, 'cpu_single_core_peak_percent')
            ),
            'memory_minimum_available_mb': _minimum(_metric_values(samples, 'memory_available_mb')),
            'network_tx_peak_mbps': _maximum(_metric_values(samples, 'network_tx_mbps')),
            'network_rx_peak_mbps': _maximum(_metric_values(samples, 'network_rx_mbps')),
            'gunicorn_cpu_peak_percent': _maximum(_metric_values(samples, 'gunicorn_cpu_percent')),
            'gunicorn_workers': _maximum(_metric_values(samples, 'gunicorn_workers')),
            'gunicorn_connections_peak': _maximum(
                _metric_values(samples, 'tcp_gunicorn_established')
            ),
            'gunicorn_listen_queue_peak': _maximum(
                _metric_values(samples, 'gunicorn_listen_queue')
            ),
            'postgres_cpu_peak_percent': _maximum(_metric_values(samples, 'postgres_cpu_percent')),
            'db_connections_peak': _maximum(_metric_values(samples, 'db_connections')),
            'db_connection_utilization_peak_percent': _maximum(
                _metric_values(samples, 'db_connection_utilization_percent')
            ),
            'db_active_peak': _maximum(_metric_values(samples, 'db_active')),
            'db_waiting_peak': _maximum(_metric_values(samples, 'db_waiting')),
            'db_locks_waiting_peak': _maximum(_metric_values(samples, 'db_lock_waiting')),
            'db_statements_peak_qps': _maximum(_metric_values(samples, 'db_statements_per_second')),
            'db_cache_hit_percent': _average(_metric_values(samples, 'db_cache_hit_percent')),
            'swap_growth_mb': _growth(_metric_values(samples, 'swap_used_mb')),
            'normal_page_success_percent': _average(_metric_values(samples, 'normal_page_success_percent')),
        }
        cache_total = summary['cache_hits'] + summary['cache_misses']
        summary['cache_hit_percent'] = (
            round(summary['cache_hits'] / cache_total * 100, 3) if cache_total else None
        )
        summaries.append(summary)
    return sorted(summaries, key=lambda row: (row['offered_qps'], row['stage']))


def _average(values):
    return round(sum(values) / len(values), 3) if values else None


def _maximum(values):
    return round(max(values), 3) if values else None


def _minimum(values):
    return round(min(values), 3) if values else None


def _growth(values):
    return round(max(values) - min(values), 3) if values else None


def find_knee(stages: list[dict[str, Any]], thresholds: dict[str, float]):
    if not stages:
        return {'stage': None, 'reason': 'No measured stages.', 'previous_safe_stage': None}
    previous = None
    for stage in stages:
        reasons = []
        if stage['error_rate_percent'] > thresholds['max_error_percent']:
            reasons.append(f'error rate {stage["error_rate_percent"]}%')
        if (stage['total_ms']['p99'] or 0) > thresholds['max_p99_ms']:
            reasons.append(f'p99 {stage["total_ms"]["p99"]} ms')
        if (stage['cpu_peak_percent'] or 0) >= thresholds['max_cpu_percent']:
            reasons.append(f'CPU {stage["cpu_peak_percent"]}%')
        if (stage.get('single_core_peak_percent') or 0) >= thresholds['max_cpu_percent']:
            reasons.append(f'single-core CPU {stage["single_core_peak_percent"]}%')
        if (
            stage['memory_minimum_available_mb'] is not None
            and stage['memory_minimum_available_mb'] < thresholds['min_available_memory_mb']
        ):
            reasons.append(f'available memory {stage["memory_minimum_available_mb"]} MB')
        if (stage['swap_growth_mb'] or 0) > thresholds['max_swap_growth_mb']:
            reasons.append(f'swap grew {stage["swap_growth_mb"]} MB')
        if (stage['network_tx_peak_mbps'] or 0) >= thresholds.get('max_network_mbps', float('inf')):
            reasons.append(f'network TX {stage["network_tx_peak_mbps"]} Mbps')
        if (stage['db_waiting_peak'] or 0) > thresholds['max_db_waiting']:
            reasons.append(f'DB waiting connections {stage["db_waiting_peak"]}')
        if (stage['db_connection_utilization_peak_percent'] or 0) >= 80:
            reasons.append(
                f'DB connection utilization {stage["db_connection_utilization_peak_percent"]}%'
            )
        if (stage['normal_page_success_percent'] or 100) < 100:
            reasons.append('normal-page availability dropped')
        if previous:
            prior_queue = previous['queue_ms']['p99'] or 0
            queue = stage['queue_ms']['p99'] or 0
            if queue > max(thresholds['queue_p99_jump_ms'], prior_queue * 3):
                reasons.append(f'queue p99 jumped from {prior_queue} to {queue} ms')
            offered_gain = stage['offered_qps'] - previous['offered_qps']
            throughput_gain = stage['successful_qps'] - previous['successful_qps']
            if offered_gain > 0 and throughput_gain / offered_gain < thresholds['minimum_throughput_gain_ratio']:
                reasons.append('throughput gain flattened while offered QPS increased')
        if reasons:
            return {
                'stage': stage,
                'reason': '; '.join(reasons),
                'previous_safe_stage': previous,
            }
        previous = stage
    return {
        'stage': None,
        'reason': 'No knee was reached within the configured safety envelope.',
        'previous_safe_stage': stages[-1],
    }


def identify_bottleneck(stage: dict[str, Any] | None, network_capacity_mbps: float | None):
    if not stage:
        return {
            'primary': 'not measured',
            'evidence': ['No completed stage is available.'],
            'next': 'Run a bounded ramp before making an infrastructure decision.',
        }
    cpu = stage.get('cpu_peak_percent') or 0
    single_core = stage.get('single_core_peak_percent') or 0
    queue = stage['queue_ms']['p99'] or 0
    app = stage['app_wall_ms']['p99'] or 0
    db = stage['db_ms']['p99'] or 0
    total = stage['total_ms']['p99'] or 0
    db_waiting = stage.get('db_waiting_peak') or 0
    network = stage.get('network_tx_peak_mbps') or 0
    memory = stage.get('memory_minimum_available_mb')
    if stage.get('client_dropped_arrivals'):
        return {
            'primary': 'PC load-generator virtual-user ceiling',
            'evidence': [
                f'{stage["client_dropped_arrivals"]} offered arrivals found every isolated virtual user busy.',
                'Those arrivals were recorded as client-side errors instead of being hidden.',
            ],
            'next': 'Increase PC-side USER_COUNT/CONCURRENCY without changing the server, then repeat the identical offered-QPS stage.',
        }
    if memory is not None and memory < 256:
        return {
            'primary': 'memory pressure',
            'evidence': [f'Available memory fell to {memory} MB.'],
            'next': 'Reduce resident processes/workers or add RAM before increasing traffic.',
        }
    if network_capacity_mbps and network >= network_capacity_mbps * 0.9:
        return {
            'primary': 'network TX saturation',
            'evidence': [f'Origin TX reached {network} Mbps of configured {network_capacity_mbps} Mbps.'],
            'next': 'Reduce dynamic payloads or move cacheable static/Markdown transfer off origin.',
        }
    if db_waiting > 0 or (total and db >= total * 0.5):
        return {
            'primary': 'PostgreSQL latency or connection contention',
            'evidence': [
                f'DB p99 was {db} ms versus total p99 {total} ms.',
                f'Peak waiting DB connections: {db_waiting}.',
            ],
            'next': 'Use EXPLAIN (ANALYZE, BUFFERS) on the measured endpoint before changing DB settings.',
        }
    if single_core >= 95 and cpu < 90:
        return {
            'primary': 'single-core CPU saturation',
            'evidence': [
                f'One core peaked at {single_core}% while aggregate CPU peaked at {cpu}%.',
                f'Measured request CPU p99 was {stage["cpu_ms"]["p99"]} ms.',
            ],
            'next': 'Profile the serial Python/serialization path; adding cores alone may not accelerate one request.',
        }
    if queue > max(20, app * 0.5) and cpu < 90 and single_core < 95:
        return {
            'primary': 'Gunicorn request queue / sync-worker concurrency',
            'evidence': [
                f'Queue p99 was {queue} ms while app p99 was {app} ms.',
                f'Host CPU peak was only {cpu}%.',
            ],
            'next': 'Test one worker-count change with the identical seed/workload; keep RAM headroom.',
        }
    if cpu >= 90:
        return {
            'primary': 'CPU saturation',
            'evidence': [
                f'Host CPU peak reached {cpu}%.',
                f'Measured request CPU p99 was {stage["cpu_ms"]["p99"]} ms.',
            ],
            'next': 'Profile the hottest endpoint; faster/more cores help only if DB and queue remain below saturation.',
        }
    return {
        'primary': 'no proven saturation point',
        'evidence': [
            f'CPU peak {cpu}%, queue p99 {queue} ms, DB p99 {db} ms, TX {network} Mbps.',
            'The configured ramp stopped before one resource showed a decisive saturation signature.',
        ],
        'next': 'Increase one ramp step within the server-advertised cap or lengthen stage duration.',
    }


def capacity_recommendation(stages, knee, *, headroom_percent=40):
    maximum = max((stage['successful_qps'] for stage in stages), default=0)
    safe_stage = knee.get('previous_safe_stage')
    if knee.get('stage') is None:
        safe_stage = stages[-1] if stages else None
    reference = safe_stage['successful_qps'] if safe_stage else 0
    sustained = reference * (1 - headroom_percent / 100)
    burst = reference * 0.8
    return {
        'maximum_observed_qps': round(maximum, 3),
        'knee_offered_qps': knee['stage']['offered_qps'] if knee.get('stage') else None,
        'knee_successful_qps': knee['stage']['successful_qps'] if knee.get('stage') else None,
        'recommended_sustained_qps': round(sustained, 3),
        'recommended_burst_qps': round(burst, 3),
        'recommended_production_qps': round(sustained, 3),
        'headroom_percent': headroom_percent,
        'capacity_is_lower_bound': knee.get('stage') is None,
    }


def summarize_endpoints(requests: list[dict[str, Any]]):
    grouped = defaultdict(list)
    for row in requests:
        grouped[row.get('endpoint', 'unknown')].append(row)
    result = []
    for endpoint, rows in sorted(grouped.items()):
        successes = [
            row for row in rows
            if 200 <= int(row.get('status', 0)) < 400 and not row.get('error')
        ]
        result.append({
            'endpoint': endpoint,
            'requests': len(rows),
            'success_percent': round(len(successes) / len(rows) * 100, 3) if rows else 0,
            'total_ms': distribution(_metric_values(successes, 'total_ms')),
            'queue_ms': distribution(_metric_values(successes, 'queue_ms')),
            'app_wall_ms': distribution(_metric_values(successes, 'app_wall_ms')),
            'app_non_db_wall_ms': distribution(_metric_values(successes, 'app_non_db_wall_ms')),
            'client_edge_residual_ms': distribution(_metric_values(successes, 'client_edge_residual_ms')),
            'cpu_ms': distribution(_metric_values(successes, 'cpu_ms')),
            'db_ms': distribution(_metric_values(successes, 'db_ms')),
            'db_queries': distribution(_metric_values(successes, 'db_queries')),
            'db_writes': distribution(_metric_values(successes, 'db_writes')),
            'json_render_ms': distribution(_metric_values(successes, 'json_render_ms')),
            'response_bytes': distribution(_metric_values(successes, 'response_bytes')),
        })
    return result


def cpu_scaling_estimate(capacity, bottleneck, *, current_cores):
    maximum = float(capacity.get('maximum_observed_qps') or 0)
    per_core = maximum / current_cores if current_cores else None
    if bottleneck.get('primary') == 'CPU saturation' and current_cores:
        return {
            'measured_qps_per_current_core': round(per_core, 3),
            'four_core_theoretical_qps_range': [round(maximum * 1.6, 3), round(maximum * 1.9, 3)],
            'classification': 'derived upper planning range, not a guarantee',
            'reason': 'CPU was the measured first bottleneck; scaling is reduced for serial work and shared DB/network limits.',
            'same_2c2g_software_gain': 'Requires identical optimization-round measurements; not invented from one baseline.',
        }
    if bottleneck.get('primary') == 'single-core CPU saturation':
        return {
            'measured_qps_per_current_core': round(per_core, 3) if per_core is not None else None,
            'four_core_theoretical_qps_range': None,
            'classification': 'more cores do not fix a proven serial hot path',
            'reason': (
                'One core saturated before aggregate CPU. A faster core or software '
                'profiling may help; 2→4 cores is not projected as linear scaling.'
            ),
            'same_2c2g_software_gain': 'Requires identical optimization-round measurements; not invented from one baseline.',
        }
    return {
        'measured_qps_per_current_core': round(per_core, 3) if per_core is not None else None,
        'four_core_theoretical_qps_range': None,
        'classification': 'CPU upgrade benefit not established',
        'reason': 'The measured first bottleneck was not host CPU; resolving it comes before projecting 2-to-4-core scaling.',
        'same_2c2g_software_gain': 'Requires identical optimization-round measurements; not invented from one baseline.',
    }


def resource_headroom(stage: dict[str, Any] | None, network_capacity_mbps: float | None):
    """Describe measured resource margin without inventing worker capacity."""
    if not stage:
        return {
            'cpu': {'status': 'not measured'},
            'database': {'status': 'not measured'},
            'network': {'status': 'not measured'},
            'workers': {'status': 'not measured'},
            'memory': {'status': 'not measured'},
        }
    cpu_used = stage.get('cpu_peak_percent')
    db_used = stage.get('db_connection_utilization_peak_percent')
    tx = stage.get('network_tx_peak_mbps')
    return {
        'cpu': {
            'peak_used_percent': cpu_used,
            'single_core_peak_percent': stage.get('single_core_peak_percent'),
            'remaining_percent_points': (
                round(max(0, 100 - cpu_used), 3) if cpu_used is not None else None
            ),
        },
        'database': {
            'connection_peak_utilization_percent': db_used,
            'connection_remaining_percent_points': (
                round(max(0, 100 - db_used), 3) if db_used is not None else None
            ),
            'waiting_connections_peak': stage.get('db_waiting_peak'),
            'lock_waiters_peak': stage.get('db_locks_waiting_peak'),
        },
        'network': {
            'tx_peak_mbps': tx,
            'configured_capacity_mbps': network_capacity_mbps,
            'remaining_mbps': (
                round(max(0, network_capacity_mbps - tx), 3)
                if network_capacity_mbps is not None and tx is not None else None
            ),
            'remaining_percent': (
                round(max(0, 100 * (network_capacity_mbps - tx) / network_capacity_mbps), 3)
                if network_capacity_mbps and tx is not None else None
            ),
        },
        'workers': {
            'sync_workers_observed': stage.get('gunicorn_workers'),
            'gunicorn_connections_peak': stage.get('gunicorn_connections_peak'),
            'listen_queue_peak': stage.get('gunicorn_listen_queue_peak'),
            'queue_p99_ms': (stage.get('queue_ms') or {}).get('p99'),
            'note': (
                'No synthetic worker-capacity percentage is reported: sync-worker '
                'headroom depends on request service time. Queue p99 and listen queue '
                'are the measured saturation evidence.'
            ),
        },
        'memory': {
            'minimum_available_mb': stage.get('memory_minimum_available_mb'),
            'swap_growth_mb': stage.get('swap_growth_mb'),
        },
    }


def dau_capacity(capacity: dict[str, Any], *, requests_per_dau=131,
                 active_hours=8, normal_peak_factor=3.0,
                 finish_fraction=0.60, finish_chain_requests=3):
    sustained = float(capacity.get('recommended_sustained_qps') or 0)
    burst_qps = float(capacity.get('recommended_burst_qps') or sustained)
    normal_rate_per_dau = requests_per_dau / (active_hours * 3600) * normal_peak_factor
    normal = math.floor(sustained / normal_rate_per_dau) if normal_rate_per_dau else 0
    bursts = {}
    for window in (600, 120, 30):
        per_dau = normal_rate_per_dau + finish_fraction * finish_chain_requests / window
        bursts[str(window)] = math.floor(burst_qps / per_dau) if per_dau else 0
    final = min([normal, *bursts.values()]) if normal else 0
    return {
        'inputs': {
            'requests_per_dau': requests_per_dau,
            'active_hours': active_hours,
            'normal_peak_factor': normal_peak_factor,
            'finish_fraction': finish_fraction,
            'finish_chain_requests': finish_chain_requests,
        },
        'normal_peak_dau': normal,
        'finish_burst_dau': {
            '10_minutes': bursts['600'],
            '2_minutes': bursts['120'],
            '30_seconds': bursts['30'],
        },
        'safe_final_dau': final,
        'method': (
            'derived: background peak traffic and synchronized finish-chain traffic '
            'share the same measured capacity budget.'
        ),
    }
