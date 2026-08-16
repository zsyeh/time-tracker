"""CSV, SVG, JSON, Markdown, and first-screen capacity reports."""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _display(value, suffix=''):
    return 'N/A' if value is None else f'{value}{suffix}'


def _write_csv(path: Path, rows: list[dict[str, Any]]):
    fields = []
    seen = set()
    for row in rows:
        for field in row:
            if field not in seen and field != 'payload':
                fields.append(field)
                seen.add(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _svg_chart(path: Path, title: str, x_label: str,
               series: list[tuple[str, str, str]], stages, *, marker_x=None):
    width, height = 920, 520
    left, right, top, bottom = 90, 35, 58, 72
    values = []
    for _, key, _ in series:
        for stage in stages:
            value = stage
            for part in key.split('.'):
                value = value.get(part) if isinstance(value, dict) else None
            if value is not None:
                values.append(float(value))
    x_values = [float(stage['offered_qps']) for stage in stages]
    max_x = max(x_values, default=1) or 1
    max_y = max(values, default=1) or 1

    def point(x, y):
        px = left + x / max_x * (width - left - right)
        py = top + (1 - y / max_y) * (height - top - bottom)
        return px, py

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        f'<text x="{left}" y="32" fill="#f0f6fc" font-size="20" font-family="system-ui">{html.escape(title)}</text>',
    ]
    for index in range(6):
        y = top + index * (height - top - bottom) / 5
        value = max_y * (1 - index / 5)
        elements.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#263043" stroke-width="1"/>',
            f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" fill="#8b949e" font-size="12">{value:.1f}</text>',
        ])
    elements.extend([
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#8b949e"/>',
        f'<text x="{(left+width-right)/2:.1f}" y="{height-24}" text-anchor="middle" fill="#8b949e" font-size="13">{html.escape(x_label)}</text>',
    ])
    for index in range(6):
        value = max_x * index / 5
        x, _ = point(value, 0)
        elements.append(f'<text x="{x:.1f}" y="{height-bottom+22}" text-anchor="middle" fill="#8b949e" font-size="12">{value:.1f}</text>')
    if marker_x is not None:
        marker_position, _ = point(float(marker_x), 0)
        elements.extend([
            f'<line x1="{marker_position:.1f}" y1="{top}" x2="{marker_position:.1f}" '
            f'y2="{height-bottom}" stroke="#ff7b72" stroke-width="2" stroke-dasharray="6 5"/>',
            f'<text x="{marker_position + 7:.1f}" y="{top + 17}" fill="#ff7b72" '
            f'font-size="12" font-weight="700">KNEE {float(marker_x):g} QPS</text>',
        ])
    legend_x = left
    for name, key, color in series:
        points = []
        for stage in stages:
            value = stage
            for part in key.split('.'):
                value = value.get(part) if isinstance(value, dict) else None
            if value is not None:
                x, y = point(float(stage['offered_qps']), float(value))
                points.append((x, y))
        if points:
            coordinates = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
            elements.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="3"/>')
            elements.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>' for x, y in points)
        elements.extend([
            f'<rect x="{legend_x}" y="{height-48}" width="12" height="12" fill="{color}"/>',
            f'<text x="{legend_x+18}" y="{height-37}" fill="#c9d1d9" font-size="12">{html.escape(name)}</text>',
        ])
        legend_x += 155
    if not values:
        elements.append(f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#8b949e">No measured values</text>')
    elements.append('</svg>')
    path.write_text('\n'.join(elements), encoding='utf-8')


def write_charts(directory: Path, stages, *, knee_qps=None):
    directory.mkdir(parents=True, exist_ok=True)
    charts = {
        'qps-vs-latency.svg': ('QPS vs latency', [('p50', 'total_ms.p50', '#58a6ff'), ('p99', 'total_ms.p99', '#ff7b72'), ('p99.9', 'total_ms.p99_9', '#d2a8ff')]),
        'qps-vs-p99-queue.svg': ('QPS vs p99 + queue p99', [('total p99', 'total_ms.p99', '#ff7b72'), ('queue p99', 'queue_ms.p99', '#f2cc60')]),
        'qps-vs-cpu.svg': ('QPS vs host CPU', [('average CPU', 'cpu_average_percent', '#3fb950'), ('peak CPU', 'cpu_peak_percent', '#ff7b72'), ('single-core peak', 'single_core_peak_percent', '#d2a8ff')]),
        'qps-vs-cpu-request.svg': ('QPS vs CPU ms/request', [('CPU p50', 'cpu_ms.p50', '#58a6ff'), ('CPU p99', 'cpu_ms.p99', '#d2a8ff')]),
        'qps-vs-db.svg': ('QPS vs DB latency', [('DB p50', 'db_ms.p50', '#3fb950'), ('DB p99', 'db_ms.p99', '#ff7b72')]),
        'qps-vs-network.svg': ('QPS vs origin network', [('TX Mbps', 'network_tx_peak_mbps', '#f2cc60'), ('RX Mbps', 'network_rx_peak_mbps', '#58a6ff')]),
        'qps-vs-errors.svg': ('QPS vs error rate', [('error %', 'error_rate_percent', '#ff7b72')]),
        'qps-vs-memory.svg': ('QPS vs minimum available memory', [('available MB', 'memory_minimum_available_mb', '#3fb950')]),
        'qps-vs-cache.svg': ('QPS vs application cache hit rate', [('cache hit %', 'cache_hit_percent', '#d2a8ff')]),
        'qps-vs-db-qps.svg': ('QPS vs PostgreSQL statements', [('DB statements/s', 'db_statements_peak_qps', '#f2cc60')]),
    }
    for filename, (title, series) in charts.items():
        _svg_chart(
            directory / filename,
            title,
            'Offered QPS',
            series,
            stages,
            marker_x=knee_qps if filename == 'qps-vs-p99-queue.svg' else None,
        )
    return list(charts)


def summary_text(report):
    machine = report['machine']
    capacity = report['capacity']
    knee = report['knee']
    bottleneck = report['bottleneck']
    dau = report['dau']
    recommended_stage = report.get('recommended_stage') or {}
    headroom = report.get('resource_headroom') or {}
    cpu_headroom = headroom.get('cpu') or {}
    db_headroom = headroom.get('database') or {}
    network_headroom = headroom.get('network') or {}
    workers = headroom.get('workers') or {}
    return '\n'.join([
        '========================================',
        'TIME TRACKER CAPACITY REPORT',
        '========================================',
        '',
        f'Machine: {machine.get("cpu_count", "N/A")} vCPU / {_display(machine.get("memory_total_mb"), " MB RAM")}',
        f'Cache: {machine.get("cache_variant") or "N/A"}',
        '',
        f'Primary bottleneck: {bottleneck["primary"]}',
        '',
        f'Knee point: {_display(capacity.get("knee_offered_qps"), " QPS")}',
        f'Max observed: {capacity["maximum_observed_qps"]} QPS',
        f'Recommended sustained: {capacity["recommended_sustained_qps"]} QPS',
        f'Recommended burst: {capacity["recommended_burst_qps"]} QPS',
        f'Recommended production: {capacity.get("recommended_production_qps", capacity["recommended_sustained_qps"])} QPS',
        '',
        f'p99 @ recommended: {_display((recommended_stage.get("total_ms") or {}).get("p99"), " ms")}',
        f'queue p99: {_display((recommended_stage.get("queue_ms") or {}).get("p99"), " ms")}',
        f'CPU/request: {_display((recommended_stage.get("cpu_ms") or {}).get("average"), " ms")}',
        f'DB p99: {_display((recommended_stage.get("db_ms") or {}).get("p99"), " ms")}',
        f'CPU remaining: {_display(cpu_headroom.get("remaining_percent_points"), " percentage points")}',
        f'DB connection remaining: {_display(db_headroom.get("connection_remaining_percent_points"), " percentage points")}',
        f'Network remaining: {_display(network_headroom.get("remaining_mbps"), " Mbps")}',
        f'Workers/queue: {_display(workers.get("sync_workers_observed"), " sync workers")} / '
        f'{_display(workers.get("queue_p99_ms"), " ms queue p99")}',
        '',
        f'Safe DAU normal: {dau["normal_peak_dau"]}',
        f'Safe DAU 22:00: {min(dau["finish_burst_dau"].values())}',
        f'Safe DAU final: {dau["safe_final_dau"]}',
        '',
        f'Next bottleneck/action: {bottleneck["next"]}',
        f'Knee evidence: {knee["reason"]}',
        '========================================',
        '',
    ])


def markdown_report(report):
    capacity = report['capacity']
    bottleneck = report['bottleneck']
    dau = report['dau']
    amplification = report['request_amplification']
    recommended = report.get('recommended_stage') or {}
    headroom = report.get('resource_headroom') or {}
    scaling = report.get('cpu_scaling') or {}
    lines = [
        '# Time Tracker Capacity Report',
        '',
        f'Run: `{report["run"]["run_id"]}` · label `{report["run"]["label"]}` · seed `{report["run"]["seed"]}`',
        '',
        '## Capacity conclusion',
        '',
        f'- Maximum observed: **{capacity["maximum_observed_qps"]} QPS**.',
        f'- Knee point: **{_display(capacity.get("knee_offered_qps"), " QPS")}**.',
        f'- Recommended sustained: **{capacity["recommended_sustained_qps"]} QPS** with {capacity["headroom_percent"]}% headroom.',
        f'- Recommended short burst: **{capacity["recommended_burst_qps"]} QPS**.',
        f'- Capacity is a lower bound because the knee was not reached: **{str(capacity["capacity_is_lower_bound"]).lower()}**.',
        '',
        '## Primary bottleneck',
        '',
        f'**{bottleneck["primary"]}**',
        '',
        *[f'- {item}' for item in bottleneck['evidence']],
        f'- Next controlled experiment: {bottleneck["next"]}',
        '',
        '## Resource margin at the recommended stage',
        '',
        f'- CPU: {_display((headroom.get("cpu") or {}).get("remaining_percent_points"), " percentage points remaining after observed peak")}.',
        f'- PostgreSQL connections: {_display((headroom.get("database") or {}).get("connection_remaining_percent_points"), " percentage points remaining")}; peak waiters {_display((headroom.get("database") or {}).get("waiting_connections_peak"))}.',
        f'- Origin network: {_display((headroom.get("network") or {}).get("remaining_mbps"), " Mbps remaining")}; the value is unavailable until configured provider bandwidth is supplied.',
        f'- Gunicorn: {_display((headroom.get("workers") or {}).get("sync_workers_observed"), " sync workers observed")}; queue p99 {_display((headroom.get("workers") or {}).get("queue_p99_ms"), " ms")}; listen queue peak {_display((headroom.get("workers") or {}).get("listen_queue_peak"))}.',
        '- Worker percentage headroom is deliberately not fabricated; queue time and socket backlog are the measured evidence.',
        f'- Memory: {_display((headroom.get("memory") or {}).get("minimum_available_mb"), " MB minimum available")}; swap growth {_display((headroom.get("memory") or {}).get("swap_growth_mb"), " MB")}.',
        '',
        '## DAU model (derived, not directly measured)',
        '',
        f'- Normal peak: **{dau["normal_peak_dau"]} DAU**.',
        f'- 22:00 finish burst, 10 minutes: **{dau["finish_burst_dau"]["10_minutes"]} DAU**.',
        f'- 22:00 finish burst, 2 minutes: **{dau["finish_burst_dau"]["2_minutes"]} DAU**.',
        f'- 22:00 finish shock, 30 seconds: **{dau["finish_burst_dau"]["30_seconds"]} DAU**.',
        f'- Final safe planning value: **{dau["safe_final_dau"]} DAU**.',
        '',
        dau['method'],
        '',
        '## Request amplification audit',
        '',
        f'- Current implementation: **{amplification["current_origin_requests_per_dau_low"]}–{amplification["current_origin_requests_per_dau_high"]} origin requests/DAU/day**.',
        f'- Reasonable optimized model: **{amplification["optimized_origin_requests_per_dau_low"]}–{amplification["optimized_origin_requests_per_dau_high"]} origin requests/DAU/day**.',
        f'- Finish action chain: `{ " → ".join(amplification["finish_chain"]) }`.',
        f'- DB write amplification: {amplification["current_session_write_amplification"]}',
        '',
        '## Stage results',
        '',
        '| Stage | Offered | Success QPS | Error | p50 | p90 | p95 | p99 | p99.9 | Max | Queue p99 | CPU avg/peak | DB p99 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for stage in report['stages']:
        lines.append(
            f'| {stage["stage"]} | {stage["offered_qps"]} | {stage["successful_qps"]} | '
            f'{stage["error_rate_percent"]}% | {_display(stage["total_ms"]["p50"])} | '
            f'{_display(stage["total_ms"]["p90"])} | {_display(stage["total_ms"]["p95"])} | '
            f'{_display(stage["total_ms"]["p99"])} | {_display(stage["total_ms"]["p99_9"])} | '
            f'{_display(stage["total_ms"]["max"])} | '
            f'{_display(stage["queue_ms"]["p99"])} | {_display(stage["cpu_average_percent"])} / '
            f'{_display(stage["cpu_peak_percent"])} | {_display(stage["db_ms"]["p99"])} |'
        )
    lines.extend([
        '',
        '## Endpoint results',
        '',
        '| Endpoint | Requests | Success | p50 | p95 | p99 | Queue p99 | CPU avg | DB p99 | JSON p99 | DB queries avg | Writes avg |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ])
    for endpoint in report.get('endpoints') or []:
        lines.append(
            f'| {endpoint["endpoint"]} | {endpoint["requests"]} | {endpoint["success_percent"]}% | '
            f'{_display(endpoint["total_ms"]["p50"])} | {_display(endpoint["total_ms"]["p95"])} | '
            f'{_display(endpoint["total_ms"]["p99"])} | {_display(endpoint["queue_ms"]["p99"])} | '
            f'{_display(endpoint["cpu_ms"]["average"])} | {_display(endpoint["db_ms"]["p99"])} | '
            f'{_display(endpoint["json_render_ms"]["p99"])} | '
            f'{_display(endpoint["db_queries"]["average"])} | {_display(endpoint["db_writes"]["average"])} |'
        )
    lines.extend([
        '',
        '## CPU scaling',
        '',
        f'- Measured QPS/current core: **{_display(scaling.get("measured_qps_per_current_core"))}**.',
        f'- 2→4 core theoretical range: **{_display(scaling.get("four_core_theoretical_qps_range"))}**.',
        f'- Classification: {scaling.get("classification", "not measured")}.',
        f'- Reason: {scaling.get("reason", "No completed stage.")}',
        f'- Same-server software gain: {scaling.get("same_2c2g_software_gain", "Requires before/after measurements.")}',
        '',
        '## Decision answers from this run',
        '',
        f'1. Maximum observed QPS: **{capacity["maximum_observed_qps"]}**.',
        f'2. Recommended sustained / burst QPS: **{capacity["recommended_sustained_qps"]} / {capacity["recommended_burst_qps"]}**.',
        f'3. p99 knee: **{_display(capacity.get("knee_offered_qps"), " offered QPS")}**; {report["knee"]["reason"]}.',
        f'4. Request CPU average / p99: **{_display((recommended.get("cpu_ms") or {}).get("average"))} / {_display((recommended.get("cpu_ms") or {}).get("p99"))} ms**.',
        f'5. Queue p99: **{_display((recommended.get("queue_ms") or {}).get("p99"), " ms")}**.',
        f'6. First bottleneck: **{bottleneck["primary"]}**; evidence is listed above.',
        f'7. Best next optimization: **{bottleneck["next"]}**. Gain is unknown until an identical optimization round is measured.',
        '8. Before/after gains and the new bottleneck require `compare.py`; a baseline alone cannot support those claims.',
        f'9. Normal / 22:00 / final safe DAU: **{dau["normal_peak_dau"]} / {min(dau["finish_burst_dau"].values())} / {dau["safe_final_dau"]}**.',
        f'10. If DAU doubles, the next resource experiment follows the measured bottleneck: **{bottleneck["next"]}**.',
        f'11. 4C4G projection: **{_display(scaling.get("four_core_theoretical_qps_range"))}** ({scaling.get("classification", "not measured")}).',
        f'12. Further 2C2G software gain: {scaling.get("same_2c2g_software_gain", "requires comparison rounds")}',
        '',
        '## Measurement definitions',
        '',
        '- **Measured:** PC-observed latency; Django app wall time; request-thread user/system CPU; ORM SQL count/write count/wall time; DRF JSON render time; Linux and PostgreSQL cumulative counters.',
        '- JSON render time covers final JSON encoding. Serializer model-to-Python conversion remains inside app wall time and is not mislabeled as separately measured.',
        '- **Estimated:** queue time is Nginx proxy-handoff timestamp to Django middleware entry. It includes socket backlog and Gunicorn scheduling, with millisecond timestamp/clock error.',
        '- **Derived:** rates from adjacent counters, knee point, headroom, bottleneck classification, and DAU capacity.',
        '- App non-DB wall is `app wall − ORM SQL wall`; it still includes middleware, Python view/service/serializer work, and JSON rendering.',
        '- Client/edge residual is `PC total − Nginx upstream response time`; it combines Internet/TLS/Cloudflare/Nginx client transfer and is not mislabeled as pure network latency.',
        '- Nginx upstream connect/header/response timings are included in raw request CSV when the production snippet is installed.',
        '- PostgreSQL statistics sampling itself adds a small, documented query workload and runs less frequently than host sampling.',
        '- Raw server metrics include the protected metrics-probe latency so telemetry overhead is visible rather than hidden.',
        '- No storage or disk benchmark was performed.',
        '',
        '## Charts',
        '',
        *[f'- [`{name}`](charts/{name})' for name in report['files']['charts']],
        '',
        '## Reproducibility',
        '',
        f'- Started: `{report["run"]["started_at"]}`',
        f'- Scenario: `{report["run"]["scenario"]}`',
        f'- Ramp: `{report["run"]["ramp_steps"]}`',
        f'- Stage duration: `{report["run"]["stage_seconds"]}` seconds',
        f'- Test users: `{report["run"]["user_count"]}`',
        f'- Concurrency: `{report["run"].get("concurrency", "N/A")}`',
        f'- Fixture rows/profiles: `{report["run"].get("fixture_history_rows", "N/A")}` / `{json.dumps(report["run"].get("fixture_profiles"), sort_keys=True)}`',
        f'- Workload seed: `{report["run"]["seed"]}`',
        f'- Endpoint mix: `{json.dumps(report["run"]["endpoint_mix"], sort_keys=True)}`',
        f'- Client transport: `{report["run"].get("client_transport", "N/A")}`',
        f'- Finish fraction/windows/DAU steps: `{report["run"].get("finish_fraction", "N/A")}` / `{report["run"].get("burst_windows_seconds", [])}` / `{report["run"].get("burst_dau_steps", [])}`',
        '',
        'Raw request, server, and database measurements are under `raw/`. Ephemeral session IDs, run tokens, share tokens, and the load-test key are never written.',
        '',
    ])
    return '\n'.join(lines)


def write_report_tree(root: Path, *, report: dict[str, Any], requests, server_metrics, db_metrics):
    raw = root / 'raw'
    charts = root / 'charts'
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(raw / 'requests.csv', requests)
    _write_csv(raw / 'server-metrics.csv', server_metrics)
    _write_csv(raw / 'db-metrics.csv', db_metrics)
    report['files'] = {'charts': write_charts(
        charts,
        report['stages'],
        knee_qps=(report.get('capacity') or {}).get('knee_offered_qps'),
    )}
    (root / 'report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8',
    )
    (root / 'report.md').write_text(markdown_report(report), encoding='utf-8')
    (root / 'summary.txt').write_text(summary_text(report), encoding='utf-8')
    return root


def new_result_directory(base: Path, label: str):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    safe_label = ''.join(character if character.isalnum() or character in '-_' else '-' for character in label)[:40]
    return base / f'{stamp}-{safe_label or "baseline"}'
