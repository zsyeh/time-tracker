#!/usr/bin/env python3
"""Combine normal mixed-load and finish-burst runs into one DAU plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_report(path: Path):
    report_path = path / 'report.json' if path.is_dir() else path
    return json.loads(report_path.read_text(encoding='utf-8'))


def combine_reports(normal, finish):
    if normal['run']['scenario'] != 'ramp':
        raise ValueError('the normal report must use SCENARIO=ramp')
    if finish['run']['scenario'] != 'finish-burst':
        raise ValueError('the finish report must use SCENARIO=finish-burst')
    for field in ('target_origin', 'seed'):
        if normal['run'].get(field) != finish['run'].get(field):
            raise ValueError(f'normal and finish reports differ in {field}')
    for field in ('cpu_count', 'memory_total_mb', 'cache_variant'):
        if normal.get('machine', {}).get(field) != finish.get('machine', {}).get(field):
            raise ValueError(f'normal and finish reports differ in machine.{field}')
    measured_finish = [
        row for row in finish.get('modeled_finish_scenarios') or []
        if row.get('status') == 'measured'
    ]
    if not measured_finish:
        raise ValueError('finish report has no fully measured finish-burst stage')
    burst_windows = finish['dau']['finish_burst_dau']
    normal_dau = int(normal['dau']['normal_peak_dau'])
    final_dau = min([normal_dau, *[int(value) for value in burst_windows.values()]])
    return {
        'schema_version': 1,
        'normal_run_id': normal['run']['run_id'],
        'finish_run_id': finish['run']['run_id'],
        'normal_safe_qps': normal['capacity']['recommended_sustained_qps'],
        'finish_safe_burst_qps': finish['capacity']['recommended_burst_qps'],
        'safe_dau_normal': normal_dau,
        'safe_dau_22_00': burst_windows,
        'safe_dau_final': final_dau,
        'normal_primary_bottleneck': normal['bottleneck']['primary'],
        'finish_primary_bottleneck': finish['bottleneck']['primary'],
        'normal_capacity_lower_bound': normal['capacity']['capacity_is_lower_bound'],
        'finish_capacity_lower_bound': finish['capacity']['capacity_is_lower_bound'],
        'fully_measured_finish_stages': len(measured_finish),
        'method': (
            'safe_DAU = min(normal mixed-load peak model, finish-chain 10-minute, '
            '2-minute, and 30-second models), using separate measured workloads.'
        ),
    }


def markdown(plan):
    burst = plan['safe_dau_22_00']
    return '\n'.join([
        '# Combined Production Capacity Plan',
        '',
        f'- Normal run: `{plan["normal_run_id"]}`; safe sustained **{plan["normal_safe_qps"]} QPS**.',
        f'- Finish run: `{plan["finish_run_id"]}`; safe short burst **{plan["finish_safe_burst_qps"]} QPS**.',
        f'- Safe normal DAU: **{plan["safe_dau_normal"]}**.',
        f'- Safe 22:00 DAU (10 min / 2 min / 30 sec): **{burst["10_minutes"]} / {burst["2_minutes"]} / {burst["30_seconds"]}**.',
        f'- Final planning DAU: **{plan["safe_dau_final"]}**.',
        f'- First bottlenecks (normal / finish): **{plan["normal_primary_bottleneck"]} / {plan["finish_primary_bottleneck"]}**.',
        f'- Lower-bound flags (normal / finish): **{plan["normal_capacity_lower_bound"]} / {plan["finish_capacity_lower_bound"]}**.',
        '',
        plan['method'],
        '',
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('normal_report', type=Path)
    parser.add_argument('finish_report', type=Path)
    parser.add_argument('--output', type=Path, default=Path('load-test-capacity-plan'))
    args = parser.parse_args(argv)
    try:
        plan = combine_reports(
            load_report(args.normal_report), load_report(args.finish_report),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'plan.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8',
    )
    (args.output / 'plan.md').write_text(markdown(plan), encoding='utf-8')
    print(args.output / 'plan.md')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
