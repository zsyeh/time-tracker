#!/usr/bin/env python3
"""Run a bounded real-API capacity test from a PC and export a full report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from stress_test.capacity_analysis import (
        AMPLIFICATION_MODEL,
        capacity_recommendation,
        cpu_scaling_estimate,
        dau_capacity,
        find_knee,
        identify_bottleneck,
        resource_headroom,
        summarize_endpoints,
        summarize_stages,
    )
    from stress_test.capacity_http import ControlClient, RequestSpec, VirtualUser, resolve_target
    from stress_test.capacity_metrics import flatten_metrics
    from stress_test.capacity_report import new_result_directory, write_report_tree
except ModuleNotFoundError:  # Direct execution from this folder.
    from capacity_analysis import (  # type: ignore
        AMPLIFICATION_MODEL,
        capacity_recommendation,
        cpu_scaling_estimate,
        dau_capacity,
        find_knee,
        identify_bottleneck,
        resource_headroom,
        summarize_endpoints,
        summarize_stages,
    )
    from capacity_http import ControlClient, RequestSpec, VirtualUser, resolve_target  # type: ignore
    from capacity_metrics import flatten_metrics  # type: ignore
    from capacity_report import new_result_directory, write_report_tree  # type: ignore


CLIENT_VERSION = '2.1'
ABSOLUTE_MAX_RPS = 1000
ABSOLUTE_MAX_CONCURRENCY = 1000
ABSOLUTE_MAX_USERS = 10000
MIX_WEIGHTS = {
    'dashboard': 43,
    'auth_bootstrap': 7,
    'history': 7,
    'session_detail': 10,
    'review_get': 10,
    'review_post': 10,
    'search': 7,
    'issues': 3,
    'share_status': 1,
    'public_share': 2,
}
ENDPOINT_NAMES = {
    'auth_bootstrap', 'dashboard', 'active_session', 'statistics', 'heatmap',
    'session_start', 'session_finish', 'history', 'session_detail',
    'review_get', 'review_post', 'search', 'issues', 'markdown',
    'share_status', 'share_create', 'public_share', 'session_update',
    'static_asset',
}


def load_env_file(path: Path):
    values = {}
    for line_number, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'Invalid config line {line_number}: expected NAME=value')
        key, value = line.split('=', 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _integer(values, name, default):
    try:
        return int(values.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be an integer') from exc


def _float(values, name, default):
    try:
        return float(values.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a number') from exc


def _boolean(values, name, default=False):
    value = values.get(name)
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def _number_list(values, name, default, cast=float):
    raw = values.get(name, default)
    try:
        result = [cast(item.strip()) for item in str(raw).split(',') if item.strip()]
    except ValueError as exc:
        raise ValueError(f'{name} must be a comma-separated number list') from exc
    if not result:
        raise ValueError(f'{name} must not be empty')
    return result


@dataclass(frozen=True)
class CapacityConfig:
    origin: str
    probe_url: str
    key: str
    scenario: str
    endpoint: str
    label: str
    seed: int
    user_count: int
    ramp_steps: tuple[float, ...]
    stage_seconds: int
    cooldown_seconds: int
    concurrency: int
    timeout_seconds: float
    sample_interval_seconds: float
    db_sample_interval_seconds: float
    public_check_url: str
    report_root: Path
    cleanup: bool
    max_error_percent: float
    max_p99_ms: float
    max_cpu_percent: float
    high_cpu_samples: int
    min_available_memory_mb: float
    max_swap_growth_mb: float
    max_db_waiting: int
    max_network_utilization_percent: float
    queue_p99_jump_ms: float
    minimum_throughput_gain_ratio: float
    headroom_percent: float
    burst_dau_steps: tuple[int, ...]
    burst_windows: tuple[int, ...]
    finish_fraction: float

    @classmethod
    def from_values(cls, values, base_dir: Path):
        target = values.get('TARGET_URL') or values.get('STRESS_TEST_URI') or ''
        key = values.get('LOAD_TEST_KEY') or values.get('STRESS_TEST_KEY') or ''
        allow_http = _boolean(values, 'ALLOW_HTTP', False)
        origin, probe_url = resolve_target(target, allow_http=allow_http)
        if len(key) < 32:
            raise ValueError('LOAD_TEST_KEY must contain at least 32 characters')
        scenario = values.get('SCENARIO', 'ramp').strip().lower()
        if scenario not in {'ramp', 'endpoint', 'cache-hot', 'cache-cold', 'finish-burst'}:
            raise ValueError('SCENARIO must be ramp, endpoint, cache-hot, cache-cold, or finish-burst')
        endpoint = values.get('ENDPOINT', 'dashboard').strip().lower()
        if endpoint not in ENDPOINT_NAMES:
            raise ValueError(f'ENDPOINT must be one of: {", ".join(sorted(ENDPOINT_NAMES))}')
        if scenario == 'endpoint' and endpoint == 'session_finish':
            raise ValueError('Use SCENARIO=finish-burst for eligible, isolated Session finish writes')
        cache_endpoints = {'dashboard', 'statistics', 'heatmap'}
        if scenario == 'cache-hot' and endpoint not in cache_endpoints:
            raise ValueError('cache-hot ENDPOINT must be dashboard, statistics, or heatmap')
        if scenario == 'cache-cold' and endpoint not in cache_endpoints | {'history'}:
            raise ValueError('cache-cold ENDPOINT must be dashboard, statistics, heatmap, or history')
        ramp_steps = tuple(sorted(set(_number_list(values, 'RAMP_STEPS', '1,5,10,20', float))))
        if ramp_steps[0] <= 0 or ramp_steps[-1] > ABSOLUTE_MAX_RPS:
            raise ValueError(f'RAMP_STEPS must stay within 0-{ABSOLUTE_MAX_RPS} QPS')
        user_count = _integer(values, 'USER_COUNT', 60)
        concurrency = _integer(values, 'CONCURRENCY', 16)
        stage_seconds = _integer(values, 'STAGE_SECONDS', 30)
        if not 1 <= user_count <= ABSOLUTE_MAX_USERS:
            raise ValueError(f'USER_COUNT must be between 1 and {ABSOLUTE_MAX_USERS}')
        if not 1 <= concurrency <= ABSOLUTE_MAX_CONCURRENCY:
            raise ValueError(f'CONCURRENCY must be between 1 and {ABSOLUTE_MAX_CONCURRENCY}')
        if not 10 <= stage_seconds <= 600:
            raise ValueError('STAGE_SECONDS must be between 10 and 600')
        # Check the real Vue shell, not the server-rendered login page. A fake
        # share token still serves only the public shell; its data API is never
        # requested. Missing frontend/dist therefore trips the availability
        # guard without exposing or creating a share.
        public_url = values.get(
            'PUBLIC_CHECK_URL',
            f'{origin}/share/capacity-availability-check',
        )
        public_origin, _ = resolve_target(origin, allow_http=allow_http)
        if not public_url.startswith(public_origin + '/'):
            raise ValueError('PUBLIC_CHECK_URL must use the same tested origin')
        report_root = Path(values.get('REPORT_ROOT', 'load-test-results')).expanduser()
        if not report_root.is_absolute():
            report_root = base_dir / report_root
        finish_fraction = _float(values, 'FINISH_FRACTION', 0.60)
        if not 0.40 <= finish_fraction <= 0.60:
            raise ValueError('FINISH_FRACTION must be between 0.40 and 0.60')
        return cls(
            origin=origin,
            probe_url=probe_url,
            key=key,
            scenario=scenario,
            endpoint=endpoint,
            label=values.get('RUN_LABEL', 'baseline').strip() or 'baseline',
            seed=_integer(values, 'RANDOM_SEED', 20260815),
            user_count=user_count,
            ramp_steps=ramp_steps,
            stage_seconds=stage_seconds,
            cooldown_seconds=max(0, min(_integer(values, 'COOLDOWN_SECONDS', 5), 60)),
            concurrency=concurrency,
            timeout_seconds=max(2, min(_float(values, 'TIMEOUT_SECONDS', 8), 30)),
            sample_interval_seconds=max(0.5, min(_float(values, 'SAMPLE_INTERVAL_SECONDS', 1), 10)),
            db_sample_interval_seconds=max(2, min(_float(values, 'DB_SAMPLE_INTERVAL_SECONDS', 5), 30)),
            public_check_url=public_url,
            report_root=report_root,
            cleanup=_boolean(values, 'CLEANUP_AFTER_RUN', True),
            max_error_percent=max(0, min(_float(values, 'MAX_ERROR_PERCENT', 1), 100)),
            max_p99_ms=max(50, min(_float(values, 'MAX_P99_MS', 1000), 30000)),
            max_cpu_percent=max(50, min(_float(values, 'MAX_CPU_PERCENT', 95), 100)),
            high_cpu_samples=max(2, min(_integer(values, 'HIGH_CPU_SAMPLES', 5), 30)),
            min_available_memory_mb=max(64, min(_float(values, 'MIN_AVAILABLE_MEMORY_MB', 256), 8192)),
            max_swap_growth_mb=max(0, min(_float(values, 'MAX_SWAP_GROWTH_MB', 32), 4096)),
            max_db_waiting=max(0, min(_integer(values, 'MAX_DB_WAITING', 1), 100)),
            max_network_utilization_percent=max(50, min(_float(values, 'MAX_NETWORK_UTILIZATION_PERCENT', 90), 100)),
            queue_p99_jump_ms=max(5, min(_float(values, 'QUEUE_P99_JUMP_MS', 40), 10000)),
            minimum_throughput_gain_ratio=max(0, min(_float(values, 'MINIMUM_THROUGHPUT_GAIN_RATIO', 0.5), 1)),
            headroom_percent=max(30, min(_float(values, 'HEADROOM_PERCENT', 40), 50)),
            burst_dau_steps=tuple(_number_list(values, 'BURST_DAU_STEPS', '100,500,1000,2000,5000,10000', int)),
            burst_windows=tuple(_number_list(values, 'BURST_WINDOWS_SECONDS', '600,120,30', int)),
            finish_fraction=finish_fraction,
        )


class State:
    def __init__(self):
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.stage = 'setup'
        self.abort_reason = None
        self.requests = []
        self.server_metrics = []
        self.db_metrics = []

    def set_stage(self, stage):
        with self.lock:
            self.stage = stage

    def current_stage(self):
        with self.lock:
            return self.stage

    def abort(self, reason):
        with self.lock:
            if self.abort_reason is None:
                self.abort_reason = reason
        self.stop.set()


def public_check(url, timeout_seconds):
    started = time.perf_counter()
    try:
        with urlopen(Request(url, headers={'User-Agent': f'time-tracker-capacity/{CLIENT_VERSION}'}), timeout=timeout_seconds) as response:
            response.read(512)
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        status = 0
    return {'status': status, 'latency_ms': round((time.perf_counter() - started) * 1000, 3)}


def monitor(config, control, state, started, network_capacity_mbps):
    previous_host = None
    previous_host_at = None
    previous_db = None
    previous_db_at = None
    next_db_at = 0.0
    public_failures = high_cpu = low_memory = 0
    initial_swap = None
    while not state.stop.is_set():
        sample_started = time.monotonic()
        include_db = sample_started >= next_db_at
        try:
            response = control.action('metrics', sample_database=include_db)
            payload = response['metrics']
        except RuntimeError as exc:
            state.abort(f'Metrics probe failed: {exc}')
            return
        normal = public_check(config.public_check_url, config.timeout_seconds)
        now = time.monotonic()
        host_elapsed = now - previous_host_at if previous_host_at is not None else config.sample_interval_seconds
        comparison = previous_host or {}
        db_elapsed = None
        if include_db:
            comparison = dict(comparison)
            comparison['database'] = previous_db or {}
            db_elapsed = now - previous_db_at if previous_db_at is not None else config.db_sample_interval_seconds
        row = flatten_metrics(
            payload,
            comparison,
            host_elapsed,
            offset_seconds=now - started,
            stage=state.current_stage(),
            normal_page=normal,
            db_elapsed_seconds=db_elapsed,
        )
        row['metrics_probe_client_latency_ms'] = response.get('_client_latency_ms')
        state.server_metrics.append(row)
        if include_db and payload.get('database'):
            state.db_metrics.append(dict(row))
            previous_db = payload['database']
            previous_db_at = now
            next_db_at = now + config.db_sample_interval_seconds
        previous_host = dict(payload)
        previous_host.pop('database', None)
        previous_host_at = now

        public_ok = 200 <= normal['status'] < 400
        public_failures = 0 if public_ok else public_failures + 1
        cpu = row.get('cpu_percent')
        single_core = row.get('cpu_single_core_peak_percent')
        cpu_saturated = (
            (cpu is not None and cpu >= config.max_cpu_percent)
            or (single_core is not None and single_core >= config.max_cpu_percent)
        )
        high_cpu = high_cpu + 1 if cpu_saturated else 0
        available = row.get('memory_available_mb')
        low_memory = low_memory + 1 if available is not None and available < config.min_available_memory_mb else 0
        swap = row.get('swap_used_mb')
        if initial_swap is None and swap is not None:
            initial_swap = swap

        if public_failures >= 3:
            state.abort('Normal-user login page failed three consecutive checks.')
        elif high_cpu >= config.high_cpu_samples:
            state.abort(
                'Aggregate or single-core CPU stayed at or above '
                f'{config.max_cpu_percent}% for {config.high_cpu_samples} samples.'
            )
        elif low_memory >= 2:
            state.abort(f'Available memory stayed below {config.min_available_memory_mb} MB.')
        elif initial_swap is not None and swap is not None and swap - initial_swap > config.max_swap_growth_mb:
            state.abort(f'Swap grew by more than {config.max_swap_growth_mb} MB.')
        elif (row.get('db_waiting') or 0) > config.max_db_waiting:
            state.abort(f'PostgreSQL waiting connections exceeded {config.max_db_waiting}.')
        elif (
            network_capacity_mbps
            and (row.get('network_tx_mbps') or 0)
            >= network_capacity_mbps * config.max_network_utilization_percent / 100
        ):
            state.abort(f'Network TX exceeded {config.max_network_utilization_percent}% of configured capacity.')
        state.stop.wait(max(0.0, config.sample_interval_seconds - (time.monotonic() - sample_started)))


def make_spec(name, credential, public_share_token=None):
    detail_uuid = credential.get('detail_uuid')
    if name in {'dashboard', 'active_session', 'statistics', 'heatmap'}:
        return RequestSpec(name, 'GET', '/api/dashboard/overview/?days=180')
    if name == 'auth_bootstrap':
        return RequestSpec(name, 'GET', '/api/auth/session/')
    if name == 'session_start':
        return RequestSpec(name, 'POST', '/api/sessions/', {'subject': 'math'})
    if name == 'session_finish':
        session_id = credential.get('finish_session_id')
        if not session_id:
            raise ValueError('session_finish requires a prepared finish-burst fixture')
        return RequestSpec(name, 'POST', f'/api/sessions/{session_id}/finish/', {
            'title': 'Capacity test finish',
            'details': 'Synthetic finish-burst Markdown.',
            'efficiency_grade': 'A',
        })
    if name == 'history':
        return RequestSpec(name, 'GET', '/api/sessions/?page=1')
    if name in {'session_detail', 'markdown'}:
        return RequestSpec(name, 'GET', f'/api/sessions/{detail_uuid}/')
    if name == 'review_get':
        return RequestSpec(name, 'GET', f'/api/sessions/{detail_uuid}/reviews/')
    if name == 'review_post':
        return RequestSpec(name, 'POST', f'/api/sessions/{detail_uuid}/reviews/', {})
    if name == 'search':
        return RequestSpec(name, 'GET', '/api/search/?q=load&limit=18')
    if name == 'issues':
        return RequestSpec(name, 'GET', '/api/issues/')
    if name == 'share_status':
        return RequestSpec(name, 'GET', f'/api/sessions/{detail_uuid}/share/')
    if name == 'share_create':
        return RequestSpec(name, 'POST', f'/api/sessions/{detail_uuid}/share/', {'expires_at': None})
    if name == 'public_share':
        if not public_share_token:
            raise ValueError('public_share requires a provisioned test share')
        return RequestSpec(name, 'GET', f'/api/public/shares/{public_share_token}/', authenticated=False)
    if name == 'session_update':
        return RequestSpec(name, 'PATCH', f'/api/sessions/{detail_uuid}/', {
            'title': 'Capacity test article',
            'details': 'Synthetic Markdown update used by a repeatable write workload.',
        })
    if name == 'static_asset':
        return RequestSpec(name, 'GET', '/static/app/index.html', authenticated=False)
    raise ValueError(f'Unsupported endpoint: {name}')


def weighted_endpoint(rng):
    choice = rng.uniform(0, sum(MIX_WEIGHTS.values()))
    cursor = 0.0
    for name, weight in MIX_WEIGHTS.items():
        cursor += weight
        if choice <= cursor:
            return name
    return next(reversed(MIX_WEIGHTS))


def _collect_finished(pending, busy, state):
    finished = {future for future in pending if future.done()}
    for future in finished:
        index = pending[future]
        busy.discard(index)
        try:
            result = future.result()
        except Exception as exc:
            result = {
                'offset_seconds': 0,
                'stage': state.current_stage(),
                'scenario': 'client',
                'endpoint': 'client_exception',
                'method': 'N/A',
                'status': 0,
                'error': exc.__class__.__name__,
                'offered_qps': 0,
            }
        result.pop('payload', None)
        state.requests.append(result)
        pending.pop(future, None)


def run_open_loop_stage(config, state, users, *, stage, offered_qps,
                        endpoint_name=None, public_share_token=None, rng, started):
    state.set_stage(stage)
    stage_started = time.monotonic()
    pending = {}
    busy = set()
    max_workers = min(config.concurrency, len(users))
    next_arrival = stage_started
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while not state.stop.is_set() and time.monotonic() - stage_started < config.stage_seconds:
            _collect_finished(pending, busy, state)
            now = time.monotonic()
            if now < next_arrival:
                time.sleep(min(0.01, next_arrival - now))
                continue
            available = [index for index in range(len(users)) if index not in busy]
            if not available:
                state.requests.append({
                    'offset_seconds': round(now - started, 3),
                    'stage': stage,
                    'scenario': config.scenario,
                    'endpoint': endpoint_name or 'mixed',
                    'method': 'N/A',
                    'status': 0,
                    'error': 'client_vu_busy',
                    'offered_qps': offered_qps,
                })
                next_arrival = now + rng.expovariate(offered_qps)
                continue
            index = rng.choice(available)
            user, credential = users[index]
            name = endpoint_name or weighted_endpoint(rng)
            spec = make_spec(name, credential, public_share_token)
            future = executor.submit(
                user.request,
                spec,
                stage=stage,
                scenario=config.scenario,
                offered_qps=offered_qps,
                offset_seconds=now - started,
            )
            pending[future] = index
            busy.add(index)
            # Poisson arrivals model aggregate independent users and avoid the
            # unrealistic synchronized hot loop of closed-loop benchmarks.
            next_arrival = now + rng.expovariate(offered_qps)
        while pending:
            done, _ = wait(pending, timeout=config.timeout_seconds, return_when=FIRST_COMPLETED)
            if not done:
                state.abort('PC worker pool did not drain before the timeout.')
                break
            _collect_finished(pending, busy, state)


def run_fixed_stage(config, state, users, *, stage, duration_seconds,
                    endpoint_name, public_share_token, started):
    """Send exactly one operation per supplied user across a business window."""
    state.set_stage(stage)
    stage_started = time.monotonic()
    event_count = len(users)
    offered_qps = event_count / max(1, duration_seconds)
    pending = {}
    max_workers = min(config.concurrency, event_count)
    schedule = [
        stage_started + duration_seconds * (index + 0.5) / event_count
        for index in range(event_count)
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for index, ((user, credential), due_at) in enumerate(zip(users, schedule)):
            if state.stop.is_set():
                break
            remaining = due_at - time.monotonic()
            if remaining > 0:
                state.stop.wait(remaining)
            if state.stop.is_set():
                break
            spec = make_spec(endpoint_name, credential, public_share_token)
            future = executor.submit(
                user.request,
                spec,
                stage=stage,
                scenario=config.scenario,
                offered_qps=offered_qps,
                offset_seconds=time.monotonic() - started,
            )
            pending[future] = index
            while len(pending) >= max_workers * 2:
                done, _ = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
                for completed in done:
                    result = completed.result()
                    result.pop('payload', None)
                    state.requests.append(result)
                    pending.pop(completed, None)
        for future in list(pending):
            result = future.result()
            result.pop('payload', None)
            state.requests.append(result)


def run_finish_flow_stage(config, state, users, *, stage, duration_seconds,
                          public_share_token, started):
    """Run the code-audited finish → dashboard + auth refresh request chain."""
    state.set_stage(stage)
    stage_started = time.monotonic()
    event_count = len(users)
    chain = ('session_finish', 'dashboard', 'auth_bootstrap')
    offered_qps = event_count * len(chain) / max(1, duration_seconds)
    max_workers = min(config.concurrency, event_count)
    schedule = [
        stage_started + duration_seconds * (index + 0.5) / event_count
        for index in range(event_count)
    ]

    def run_chain(user, credential):
        results = []
        for endpoint_name in chain:
            result = user.request(
                make_spec(endpoint_name, credential, public_share_token),
                stage=stage,
                scenario=config.scenario,
                offered_qps=offered_qps,
                offset_seconds=time.monotonic() - started,
            )
            result.pop('payload', None)
            results.append(result)
            if endpoint_name == 'session_finish' and not 200 <= result['status'] < 300:
                break
        return results

    pending = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for (user, credential), due_at in zip(users, schedule):
            if state.stop.is_set():
                break
            remaining = due_at - time.monotonic()
            if remaining > 0:
                state.stop.wait(remaining)
            if state.stop.is_set():
                break
            pending.add(executor.submit(run_chain, user, credential))
            while len(pending) >= max_workers * 2:
                done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
                for completed in done:
                    state.requests.extend(completed.result())
        for future in pending:
            state.requests.extend(future.result())


def run_finish_burst(config, control, state, users, run_id, run_token,
                     public_share_token, rng, started, modeled_scenarios):
    by_username = {credential['username']: (user, credential) for user, credential in users}
    for window in config.burst_windows:
        for dau in config.burst_dau_steps:
            desired = math.ceil(dau * config.finish_fraction)
            if desired > len(users):
                modeled_scenarios.append({
                    'dau': dau,
                    'window_seconds': window,
                    'desired_finish_events': desired,
                    'status': 'derived-only',
                    'reason': f'Only {len(users)} isolated users were provisioned; no result is labeled measured.',
                })
                continue
            prepared = control.action(
                'prepare_finish', run_id=run_id, run_token=run_token, limit=desired,
            )['fixtures']['sessions']
            selected = []
            for row in prepared:
                user, credential = by_username[row['username']]
                credential['finish_session_id'] = row['session_id']
                selected.append((user, credential))
            stage = f'finish-{dau}dau-{window}s'
            # The fixed-count event stream is spread across the whole business
            # window, so the stage ramps naturally instead of a zero-to-N shock.
            request_cursor = len(state.requests)
            run_finish_flow_stage(
                config, state, selected,
                stage=stage, duration_seconds=window,
                public_share_token=public_share_token,
                started=started,
            )
            stage_rows = state.requests[request_cursor:]
            completed_finishes = sum(
                row.get('endpoint') == 'session_finish'
                and 200 <= int(row.get('status') or 0) < 300
                for row in stage_rows
            )
            modeled_scenarios.append({
                'dau': dau,
                'window_seconds': window,
                'desired_finish_events': desired,
                'origin_requests_per_finish': AMPLIFICATION_MODEL['finish_chain_requests'],
                'offered_origin_qps': round(
                    desired * AMPLIFICATION_MODEL['finish_chain_requests'] / window, 6,
                ),
                'completed_finish_events': completed_finishes,
                'status': 'measured' if completed_finishes == desired else 'measured-partial',
            })
            if state.stop.is_set():
                return


def thresholds(config, network_capacity_mbps):
    return {
        'max_error_percent': config.max_error_percent,
        'max_p99_ms': config.max_p99_ms,
        'max_cpu_percent': config.max_cpu_percent,
        'min_available_memory_mb': config.min_available_memory_mb,
        'max_swap_growth_mb': config.max_swap_growth_mb,
        'max_db_waiting': config.max_db_waiting,
        'max_network_mbps': (
            network_capacity_mbps * config.max_network_utilization_percent / 100
            if network_capacity_mbps else float('inf')
        ),
        'queue_p99_jump_ms': config.queue_p99_jump_ms,
        'minimum_throughput_gain_ratio': config.minimum_throughput_gain_ratio,
    }


def build_users(config, fixtures, run_token, *, state=None):
    users = []
    for credential in fixtures['users']:
        if state is not None and state.stop.is_set():
            raise RuntimeError(state.abort_reason or 'Safety monitor stopped fixture bootstrap.')
        user = VirtualUser(
            config.origin,
            session_key=credential['session_key'],
            run_token=run_token,
            timeout_seconds=config.timeout_seconds,
            username=credential['username'],
        )
        user.bootstrap()
        users.append((user, credential))
    return users


def run_capacity(config, *, check_only=False):
    control = ControlClient(config.probe_url, config.key, config.timeout_seconds)
    run_id = f'run-{config.seed:x}-{int(time.time()):x}'[-40:]
    requested_max = math.ceil(max(config.ramp_steps))
    begin = control.action(
        'begin', run_id=run_id, max_rps=requested_max,
        ttl_seconds=4 * 60 * 60,
    )
    if check_only:
        safe = dict(begin)
        safe['run']['run_token'] = '<redacted>'
        print(json.dumps(safe, ensure_ascii=False, indent=2))
        return 0
    run = begin['run']
    run_token = run['run_token']
    server_cap = float(run['max_rps_per_worker'])
    server_user_cap = int((begin.get('limits') or {}).get('max_users') or 0)
    if server_user_cap and config.user_count > server_user_cap:
        raise ValueError(
            f'USER_COUNT={config.user_count} exceeds the server-advertised '
            f'max_users={server_user_cap}; raise the server limit deliberately first.'
        )
    ramp_steps = tuple(step for step in config.ramp_steps if step <= server_cap)
    if not ramp_steps:
        ramp_steps = (server_cap,)
    metrics = begin.get('metrics') or {}
    network_capacity = (
        ((metrics.get('network') or {}).get('configured_capacity_mbps')) or None
    )
    print(f'Protected probe ready. Server-advertised conservative client cap: {server_cap:g} QPS.')
    print(f'Provisioning {config.user_count} isolated users; no real account is used.')
    state = State()
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    monitor_thread = threading.Thread(
        target=monitor,
        args=(config, control, state, started, network_capacity),
        daemon=True,
        name='capacity-monitor',
    )
    monitor_thread.start()
    try:
        fixtures = control.action(
            'provision',
            run_id=run_id,
            run_token=run_token,
            user_count=config.user_count,
            seed=config.seed,
        )['fixtures']
        users = build_users(config, fixtures, run_token, state=state)
    except Exception:
        # A bootstrap failure after provisioning must not strand synthetic
        # users. Cleanup still uses the long-lived key if the run token failed.
        try:
            control.action('cleanup', run_id=run_id)
        except RuntimeError:
            pass
        state.stop.set()
        monitor_thread.join(
            timeout=config.timeout_seconds + config.sample_interval_seconds + 2,
        )
        raise
    public_share_token = fixtures.get('public_share_token')
    rng = random.Random(config.seed)
    modeled_scenarios = []
    cleanup_result = None
    try:
        if state.stop.is_set():
            raise RuntimeError(state.abort_reason or 'Safety monitor stopped during setup.')
        if config.scenario == 'finish-burst':
            run_finish_burst(
                config, control, state, users, run_id, run_token,
                public_share_token, rng, started, modeled_scenarios,
            )
        else:
            endpoint = config.endpoint if config.scenario == 'endpoint' else None
            if config.scenario == 'cache-hot':
                endpoint = config.endpoint
                print(f'Warming each isolated {endpoint} cache key before measurement.')
                for user, credential in users:
                    if state.stop.is_set():
                        raise RuntimeError(
                            state.abort_reason or 'Safety monitor stopped cache warmup.'
                        )
                    result = user.request(
                        make_spec(endpoint, credential), stage='warmup', scenario='cache-hot',
                        offered_qps=0, offset_seconds=time.monotonic() - started,
                    )
                    if result['status'] != 200:
                        raise RuntimeError('Cache warmup failed.')
            single_use_endpoint = (
                config.scenario == 'endpoint'
                and config.endpoint in {'session_start', 'review_post', 'share_create'}
            )
            fresh_cache_users = (
                config.scenario == 'cache-cold' and config.endpoint != 'history'
            )
            single_use_users = users[1:] if config.endpoint == 'share_create' else users
            if fresh_cache_users or single_use_endpoint:
                endpoint = config.endpoint
                if single_use_endpoint:
                    endpoint = config.endpoint
                # A cold dashboard is measured once per fresh user.  Reusing a
                # user would silently turn later requests into cache hits.  A
                # start/review/share write is likewise measured only once per
                # isolated user so conflict/dedup paths do not replace writes.
                usable_steps = []
                required_users = 0
                for step in ramp_steps:
                    stage_users = math.ceil(step * config.stage_seconds)
                    if required_users + stage_users > len(single_use_users):
                        break
                    usable_steps.append(step)
                    required_users += stage_users
                if not usable_steps:
                    raise ValueError(
                        'This single-use scenario needs at least '
                        'ceil(first RAMP_STEP * STAGE_SECONDS) isolated users.'
                    )
                if len(usable_steps) < len(ramp_steps):
                    print(
                        'Single-use safety truncated the ramp to '
                        f'{usable_steps}; raise USER_COUNT deliberately for later stages.'
                    )
                ramp_steps = tuple(usable_steps)
            cold_cursor = 0
            for index, step in enumerate(ramp_steps):
                if state.stop.is_set():
                    break
                stage = f'{config.scenario}-{step:g}qps'
                print(f'Running {stage} for {config.stage_seconds}s.')
                if fresh_cache_users or single_use_endpoint:
                    count = math.ceil(step * config.stage_seconds)
                    cold_users = single_use_users[cold_cursor:cold_cursor + count]
                    cold_cursor += count
                    run_fixed_stage(
                        config, state, cold_users,
                        stage=stage, duration_seconds=config.stage_seconds,
                        endpoint_name=endpoint, public_share_token=public_share_token,
                        started=started,
                    )
                else:
                    run_open_loop_stage(
                        config, state, users,
                        stage=stage, offered_qps=step, endpoint_name=endpoint,
                        public_share_token=public_share_token, rng=rng, started=started,
                    )
                stages = summarize_stages(state.requests, state.server_metrics)
                knee = find_knee(stages, thresholds(config, network_capacity))
                if knee.get('stage') is not None:
                    state.abort(f'Automatic knee/safety stop: {knee["reason"]}')
                    break
                if index < len(ramp_steps) - 1 and config.cooldown_seconds:
                    state.set_stage('cooldown')
                    state.stop.wait(config.cooldown_seconds)
    except KeyboardInterrupt:
        state.abort('Interrupted by user.')
    finally:
        state.stop.set()
        monitor_thread.join(timeout=config.timeout_seconds + config.sample_interval_seconds + 2)
        if config.cleanup:
            try:
                cleanup_result = control.action(
                    'cleanup', run_id=run_id, run_token=run_token,
                ).get('fixtures')
            except RuntimeError as exc:
                cleanup_result = {'error': str(exc)}

    stages = summarize_stages(state.requests, state.server_metrics)
    knee = find_knee(stages, thresholds(config, network_capacity))
    capacity = capacity_recommendation(stages, knee, headroom_percent=config.headroom_percent)
    reference_stage = (
        knee.get('previous_safe_stage')
        if knee.get('stage') is not None
        else (stages[-1] if stages else None)
    )
    bottleneck_stage = knee.get('stage') or reference_stage
    bottleneck = identify_bottleneck(bottleneck_stage, network_capacity)
    dau = dau_capacity(
        capacity,
        requests_per_dau=AMPLIFICATION_MODEL['current_origin_requests_per_dau_high'],
        finish_fraction=config.finish_fraction,
        finish_chain_requests=AMPLIFICATION_MODEL['finish_chain_requests'],
    )
    machine_source = metrics.get('machine') or {}
    memory_source = metrics.get('memory') or {}
    scaling = cpu_scaling_estimate(
        capacity, bottleneck, current_cores=int(machine_source.get('cpu_count') or 0),
    )
    headroom = resource_headroom(reference_stage, network_capacity)
    if config.scenario == 'ramp':
        endpoint_mix = MIX_WEIGHTS
    elif config.scenario in {'cache-hot', 'cache-cold'}:
        endpoint_mix = {config.endpoint: 100}
    elif config.scenario == 'finish-burst':
        endpoint_mix = {'session_finish': 100}
    else:
        endpoint_mix = {config.endpoint: 100}
    report = {
        'schema_version': 2,
        'client_version': CLIENT_VERSION,
        'run': {
            'run_id': run_id,
            'label': config.label,
            'scenario': config.scenario,
            'endpoint': config.endpoint if config.scenario == 'endpoint' else None,
            'started_at': started_at.isoformat(),
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'seed': config.seed,
            'ramp_steps': list(ramp_steps),
            'stage_seconds': config.stage_seconds,
            'cooldown_seconds': config.cooldown_seconds,
            'concurrency': config.concurrency,
            'user_count': len(users),
            'fixture_history_rows': fixtures.get('history_rows'),
            'fixture_profiles': fixtures.get('profile_rows'),
            'endpoint_mix': endpoint_mix,
            'finish_fraction': config.finish_fraction,
            'burst_windows_seconds': list(config.burst_windows),
            'burst_dau_steps': list(config.burst_dau_steps),
            'server_advertised_qps_cap_per_worker': server_cap,
            'arrival_model': 'aggregate Poisson arrivals; no closed-loop zero-think-time hot loop',
            'client_transport': 'persistent HTTP/1.1 connection per virtual user; gzip accepted',
            'key_fingerprint': hashlib.sha256(config.key.encode()).hexdigest()[:12],
            'target_origin': config.origin,
            'probe_path': '/api/stress-test/probe/',
            'abort_reason': state.abort_reason,
            'cleanup': cleanup_result,
        },
        'machine': {
            'cpu_count': machine_source.get('cpu_count'),
            'memory_total_mb': memory_source.get('total_mb'),
            'platform': machine_source.get('platform'),
            'network_capacity_mbps': network_capacity,
            'cache_variant': (metrics.get('cache') or {}).get('variant'),
            'cache_backend': (metrics.get('cache') or {}).get('backend'),
            'storage_benchmark_performed': False,
        },
        'request_amplification': AMPLIFICATION_MODEL,
        'stages': stages,
        'endpoints': summarize_endpoints(state.requests),
        'knee': {
            'reason': knee['reason'],
            'stage': knee['stage']['stage'] if knee.get('stage') else None,
            'previous_safe_stage': knee['previous_safe_stage']['stage'] if knee.get('previous_safe_stage') else None,
        },
        'capacity': capacity,
        'recommended_stage': reference_stage,
        'bottleneck': bottleneck,
        'resource_headroom': headroom,
        'cpu_scaling': scaling,
        'dau': dau,
        'modeled_finish_scenarios': modeled_scenarios,
        'measurement_labels': {
            'measured': ['HTTP latency', 'app wall', 'thread CPU', 'DB query time/count', 'host/process/DB counters'],
            'estimated': ['Nginx-to-Django queue time'],
            'derived': ['counter rates', 'knee', 'bottleneck', 'safe QPS', 'safe DAU'],
        },
    }
    result_dir = new_result_directory(config.report_root, config.label)
    write_report_tree(
        result_dir,
        report=report,
        requests=state.requests,
        server_metrics=state.server_metrics,
        db_metrics=state.db_metrics,
    )
    print((result_dir / 'summary.txt').read_text(encoding='utf-8'))
    print(f'Report directory: {result_dir}')
    if cleanup_result and cleanup_result.get('error'):
        print('WARNING: automatic isolated-user cleanup failed; use the cleanup command.', file=sys.stderr)
        return 3
    return 2 if state.abort_reason else 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config', type=Path,
        default=Path(__file__).with_name('stress-test.env'),
    )
    parser.add_argument('--check', action='store_true', help='Verify key/URI and print redacted capabilities only.')
    parser.add_argument('--scenario', choices=['ramp', 'endpoint', 'cache-hot', 'cache-cold', 'finish-burst'])
    parser.add_argument('--endpoint', choices=sorted(ENDPOINT_NAMES))
    parser.add_argument('--label')
    parser.add_argument('--keep-fixtures', action='store_true')
    parser.add_argument('--cleanup-run', metavar='RUN_ID', help='Delete only the isolated users for an interrupted run.')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if not args.config.exists():
            raise ValueError(f'Config not found: {args.config}. Copy stress-test.example.env first.')
        values = load_env_file(args.config)
        if args.scenario:
            values['SCENARIO'] = args.scenario
        if args.endpoint:
            values['ENDPOINT'] = args.endpoint
        if args.label:
            values['RUN_LABEL'] = args.label
        if args.keep_fixtures:
            values['CLEANUP_AFTER_RUN'] = 'false'
        config = CapacityConfig.from_values(values, args.config.resolve().parent)
        if args.cleanup_run:
            control = ControlClient(config.probe_url, config.key, config.timeout_seconds)
            print(json.dumps(control.action('cleanup', run_id=args.cleanup_run), ensure_ascii=False, indent=2))
            return 0
        return run_capacity(config, check_only=args.check)
    except (ValueError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
