#!/usr/bin/env python3
"""Compare Baseline, Optimization Round 1, and Round 2 capacity reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_report(path: Path):
    report_path = path / 'report.json' if path.is_dir() else path
    return json.loads(report_path.read_text(encoding='utf-8'))


def extract(report):
    stage = report.get('recommended_stage') or {}
    return {
        'label': report['run']['label'],
        'max_qps': report['capacity']['maximum_observed_qps'],
        'safe_qps': report['capacity']['recommended_sustained_qps'],
        'burst_qps': report['capacity']['recommended_burst_qps'],
        'p50_ms': (stage.get('total_ms') or {}).get('p50'),
        'p95_ms': (stage.get('total_ms') or {}).get('p95'),
        'p99_ms': (stage.get('total_ms') or {}).get('p99'),
        'p99_9_ms': (stage.get('total_ms') or {}).get('p99_9'),
        'queue_p99_ms': (stage.get('queue_ms') or {}).get('p99'),
        'cpu_ms_per_request': (stage.get('cpu_ms') or {}).get('average'),
        'cpu_peak_percent': stage.get('cpu_peak_percent'),
        'db_queries_per_request': (stage.get('db_queries') or {}).get('average'),
        'db_p99_ms': (stage.get('db_ms') or {}).get('p99'),
        'cache_hit_percent': stage.get('cache_hit_percent'),
        'network_tx_mbps': stage.get('network_tx_peak_mbps'),
        'memory_available_mb': stage.get('memory_minimum_available_mb'),
        'error_rate_percent': stage.get('error_rate_percent'),
        'safe_dau_normal': report['dau']['normal_peak_dau'],
        'safe_dau_22_00': min(report['dau']['finish_burst_dau'].values()),
        'safe_dau_final': report['dau']['safe_final_dau'],
        'primary_bottleneck': report['bottleneck']['primary'],
    }


def _ratio(after, before):
    if after is None or before in {None, 0}:
        return None
    return round(after / before, 3)


def _reduction_percent(after, before):
    if after is None or before in {None, 0}:
        return None
    return round((before - after) / before * 100, 3)


def gains(rows):
    before, after = rows[0], rows[-1]
    rounds = []
    for prior, current in zip(rows, rows[1:]):
        rounds.append({
            'from': prior['label'],
            'to': current['label'],
            'max_qps_multiple': _ratio(current['max_qps'], prior['max_qps']),
            'safe_qps_multiple': _ratio(current['safe_qps'], prior['safe_qps']),
            'p99_reduction_percent': _reduction_percent(current['p99_ms'], prior['p99_ms']),
            'queue_p99_reduction_percent': _reduction_percent(
                current['queue_p99_ms'], prior['queue_p99_ms'],
            ),
        })
    comparable = [row for row in rounds if row['safe_qps_multiple'] is not None]
    best = max(comparable, key=lambda row: row['safe_qps_multiple'], default=None)
    return {
        'baseline_label': before['label'],
        'final_label': after['label'],
        'max_qps_multiple': _ratio(after['max_qps'], before['max_qps']),
        'safe_qps_multiple': _ratio(after['safe_qps'], before['safe_qps']),
        'p99_reduction_percent': _reduction_percent(after['p99_ms'], before['p99_ms']),
        'queue_p99_reduction_percent': _reduction_percent(
            after['queue_p99_ms'], before['queue_p99_ms'],
        ),
        'cpu_ms_reduction_percent': _reduction_percent(
            after['cpu_ms_per_request'], before['cpu_ms_per_request'],
        ),
        'new_primary_bottleneck': after['primary_bottleneck'],
        'best_round_by_safe_qps_multiple': best,
        'rounds': rounds,
    }


def markdown(rows, comparison):
    fields = [
        ('Max QPS', 'max_qps'), ('Safe QPS', 'safe_qps'), ('Burst QPS', 'burst_qps'),
        ('p50 ms', 'p50_ms'), ('p95 ms', 'p95_ms'), ('p99 ms', 'p99_ms'),
        ('p99.9 ms', 'p99_9_ms'), ('Queue p99 ms', 'queue_p99_ms'),
        ('CPU ms/request', 'cpu_ms_per_request'), ('CPU peak %', 'cpu_peak_percent'),
        ('DB queries/request', 'db_queries_per_request'), ('DB p99 ms', 'db_p99_ms'),
        ('Cache hit %', 'cache_hit_percent'), ('Network TX Mbps', 'network_tx_mbps'),
        ('Minimum available MB', 'memory_available_mb'), ('Error %', 'error_rate_percent'),
        ('Safe DAU normal', 'safe_dau_normal'), ('Safe DAU 22:00', 'safe_dau_22_00'),
        ('Safe DAU final', 'safe_dau_final'), ('Primary bottleneck', 'primary_bottleneck'),
    ]
    lines = [
        '# Capacity Optimization Comparison', '',
        '| Metric | ' + ' | '.join(row['label'] for row in rows) + ' |',
        '|---|' + '|'.join('---:' for _ in rows) + '|',
    ]
    for label, key in fields:
        lines.append('| ' + label + ' | ' + ' | '.join(str(row.get(key) if row.get(key) is not None else 'N/A') for row in rows) + ' |')
    lines.extend([
        '',
        '## Evidence-based gains',
        '',
        f'- Maximum-QPS multiple, first→last: **{comparison.get("max_qps_multiple") or "N/A"}×**.',
        f'- Safe-QPS multiple, first→last: **{comparison.get("safe_qps_multiple") or "N/A"}×**.',
        f'- p99 reduction, first→last: **{comparison.get("p99_reduction_percent") if comparison.get("p99_reduction_percent") is not None else "N/A"}%**.',
        f'- Queue-p99 reduction, first→last: **{comparison.get("queue_p99_reduction_percent") if comparison.get("queue_p99_reduction_percent") is not None else "N/A"}%**.',
        f'- CPU-ms/request reduction, first→last: **{comparison.get("cpu_ms_reduction_percent") if comparison.get("cpu_ms_reduction_percent") is not None else "N/A"}%**.',
        f'- New first bottleneck: **{comparison.get("new_primary_bottleneck") or "N/A"}**.',
        f'- Largest measured safe-QPS round: **{json.dumps(comparison.get("best_round_by_safe_qps_multiple"), sort_keys=True)}**.',
        '',
        'Only compare runs with the same seed, scenario, endpoint mix, ramp, stage duration, and fixture profile.',
        'Change one bottleneck-related variable per optimization round.',
        '',
    ])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=Path('load-test-comparison'))
    args = parser.parse_args(argv)
    if not 2 <= len(args.reports) <= 3:
        parser.error('provide two or three report directories')
    reports = [load_report(path) for path in args.reports]
    signatures = {
        (
            report['run']['seed'], report['run']['scenario'],
            tuple(report['run']['ramp_steps']), report['run']['stage_seconds'],
            json.dumps(report['run']['endpoint_mix'], sort_keys=True),
            report['run'].get('concurrency'), report['run'].get('user_count'),
            report['run'].get('fixture_history_rows'),
            json.dumps(report['run'].get('fixture_profiles'), sort_keys=True),
            report['run'].get('finish_fraction'),
            tuple(report['run'].get('burst_windows_seconds') or ()),
            tuple(report['run'].get('burst_dau_steps') or ()),
            report.get('machine', {}).get('cpu_count'),
            report.get('machine', {}).get('memory_total_mb'),
            report.get('client_version'), report['run'].get('arrival_model'),
            report['run'].get('client_transport'), report['run'].get('target_origin'),
        )
        for report in reports
    }
    if len(signatures) != 1:
        parser.error('reports do not use the same reproducibility signature')
    rows = [extract(report) for report in reports]
    comparison = gains(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'comparison.json').write_text(
        json.dumps({'runs': rows, 'gains': comparison}, ensure_ascii=False, indent=2), encoding='utf-8',
    )
    (args.output / 'comparison.md').write_text(markdown(rows, comparison), encoding='utf-8')
    print(args.output / 'comparison.md')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
