import json
import tempfile
import unittest
from pathlib import Path

from stress_test.capacity import CapacityConfig
from stress_test.capacity_analysis import (
    AMPLIFICATION_MODEL,
    capacity_recommendation,
    cpu_scaling_estimate,
    dau_capacity,
    find_knee,
    percentile,
    resource_headroom,
)
from stress_test.compare import gains
from stress_test.combine import combine_reports
from stress_test.capacity_metrics import flatten_metrics
from stress_test.capacity_report import write_report_tree


TEST_KEY = 'capacity-test-key-' + 'x' * 32


def stage(name, qps, p99, queue=1, cpu=20, errors=0):
    latency = {'count': 100, 'min': 1, 'average': p99 / 2, 'p50': p99 / 3,
               'p90': p99 / 2, 'p95': p99 * .75, 'p99': p99,
               'p99_9': p99 * 1.1, 'max': p99 * 1.2}
    return {
        'stage': name, 'scenario': 'ramp', 'endpoint': 'mixed',
        'offered_qps': qps, 'successful_qps': qps * (1 - errors / 100),
        'attempted': 100, 'successful': 100, 'error_rate_percent': errors,
        'status_counts': {'200': 100}, 'total_ms': latency,
        'queue_ms': {**latency, 'p99': queue}, 'app_wall_ms': latency,
        'cpu_ms': latency, 'db_ms': latency, 'db_queries': latency,
        'db_writes': latency, 'response_bytes': latency,
        'cache_hits': 0, 'cache_misses': 0, 'cache_hit_percent': None,
        'cpu_average_percent': cpu / 2, 'cpu_peak_percent': cpu,
        'memory_minimum_available_mb': 800, 'network_tx_peak_mbps': 2,
        'network_rx_peak_mbps': 1, 'gunicorn_cpu_peak_percent': 20,
        'postgres_cpu_peak_percent': 10, 'db_connections_peak': 4,
        'db_connection_utilization_peak_percent': 20, 'db_active_peak': 2,
        'db_waiting_peak': 0, 'db_locks_waiting_peak': 0,
        'db_statements_peak_qps': 20, 'db_cache_hit_percent': 99,
        'swap_growth_mb': 0, 'normal_page_success_percent': 100,
    }


class CapacityAnalysisTests(unittest.TestCase):
    def test_config_needs_only_target_and_key_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            config = CapacityConfig.from_values({
                'TARGET_URL': 'https://timer.example.com',
                'LOAD_TEST_KEY': TEST_KEY,
            }, Path(directory))
        self.assertEqual(config.probe_url, 'https://timer.example.com/api/stress-test/probe/')
        self.assertEqual(
            config.public_check_url,
            'https://timer.example.com/share/capacity-availability-check',
        )
        self.assertEqual(config.ramp_steps, (1.0, 5.0, 10.0, 20.0))
        self.assertEqual(config.seed, 20260815)

    def test_percentile_knee_capacity_and_burst_dau_are_derived(self):
        self.assertEqual(percentile([1, 2, 3, 4], .5), 2.5)
        stages = [stage('5qps', 5, 40), stage('10qps', 10, 70), stage('20qps', 20, 1400, queue=500)]
        knee = find_knee(stages, {
            'max_error_percent': 1, 'max_p99_ms': 1000, 'max_cpu_percent': 95,
            'min_available_memory_mb': 256, 'max_swap_growth_mb': 32,
            'max_db_waiting': 1, 'max_network_mbps': 27,
            'queue_p99_jump_ms': 40, 'minimum_throughput_gain_ratio': .5,
        })
        self.assertEqual(knee['stage']['stage'], '20qps')
        capacity = capacity_recommendation(stages, knee, headroom_percent=40)
        self.assertEqual(capacity['recommended_sustained_qps'], 6)
        dau = dau_capacity(capacity, requests_per_dau=131)
        self.assertLess(dau['finish_burst_dau']['30_seconds'], dau['normal_peak_dau'])
        self.assertEqual(dau['safe_final_dau'], dau['finish_burst_dau']['30_seconds'])

    def test_first_stage_knee_is_not_reported_as_safe_capacity(self):
        stages = [stage('1qps', 1, 1500, queue=700)]
        knee = find_knee(stages, {
            'max_error_percent': 1, 'max_p99_ms': 1000, 'max_cpu_percent': 95,
            'min_available_memory_mb': 256, 'max_swap_growth_mb': 32,
            'max_db_waiting': 1, 'max_network_mbps': 27,
            'queue_p99_jump_ms': 40, 'minimum_throughput_gain_ratio': .5,
        })
        capacity = capacity_recommendation(stages, knee, headroom_percent=40)
        self.assertIsNone(knee['previous_safe_stage'])
        self.assertEqual(capacity['recommended_sustained_qps'], 0)
        self.assertEqual(capacity['recommended_burst_qps'], 0)

    def test_amplification_headroom_cpu_scaling_and_comparison_are_explicit(self):
        self.assertEqual(sum(AMPLIFICATION_MODEL['current_high_request_breakdown'].values()), 131)
        measured = stage('10qps', 10, 80, cpu=40)
        measured['gunicorn_workers'] = 2
        measured['gunicorn_connections_peak'] = 2
        measured['gunicorn_listen_queue_peak'] = 0
        headroom = resource_headroom(measured, 30)
        self.assertEqual(headroom['cpu']['remaining_percent_points'], 60)
        self.assertEqual(headroom['network']['remaining_mbps'], 28)
        non_cpu = cpu_scaling_estimate(
            {'maximum_observed_qps': 10}, {'primary': 'Gunicorn request queue / sync-worker concurrency'},
            current_cores=2,
        )
        self.assertIsNone(non_cpu['four_core_theoretical_qps_range'])
        comparison = gains([
            {'label': 'before', 'max_qps': 10, 'safe_qps': 6, 'p99_ms': 100,
             'queue_p99_ms': 40, 'cpu_ms_per_request': 20,
             'primary_bottleneck': 'CPU saturation'},
            {'label': 'after', 'max_qps': 15, 'safe_qps': 9, 'p99_ms': 70,
             'queue_p99_ms': 20, 'cpu_ms_per_request': 14,
             'primary_bottleneck': 'Gunicorn queue'},
        ])
        self.assertEqual(comparison['safe_qps_multiple'], 1.5)
        self.assertEqual(comparison['p99_reduction_percent'], 30)

    def test_combined_plan_requires_real_finish_measurement_and_uses_minimum_dau(self):
        common_run = {'target_origin': 'https://timer.example.com', 'seed': 7}
        machine = {'cpu_count': 2, 'memory_total_mb': 2048, 'cache_variant': 'file'}
        normal = {
            'run': {**common_run, 'scenario': 'ramp', 'run_id': 'normal'},
            'machine': machine,
            'capacity': {'recommended_sustained_qps': 12, 'capacity_is_lower_bound': False},
            'dau': {'normal_peak_dau': 4000},
            'bottleneck': {'primary': 'CPU saturation'},
        }
        finish = {
            'run': {**common_run, 'scenario': 'finish-burst', 'run_id': 'finish'},
            'machine': machine,
            'capacity': {'recommended_burst_qps': 8, 'capacity_is_lower_bound': True},
            'dau': {'finish_burst_dau': {
                '10_minutes': 5000, '2_minutes': 2200, '30_seconds': 700,
            }},
            'bottleneck': {'primary': 'Gunicorn request queue / sync-worker concurrency'},
            'modeled_finish_scenarios': [{'status': 'measured'}],
        }
        plan = combine_reports(normal, finish)
        self.assertEqual(plan['safe_dau_final'], 700)
        finish['modeled_finish_scenarios'] = [{'status': 'derived-only'}]
        with self.assertRaisesRegex(ValueError, 'no fully measured'):
            combine_reports(normal, finish)

    def test_counter_deltas_separate_cpu_network_process_and_database(self):
        previous = {
            'cpu': {'total': 1000, 'idle_total': 500, 'user': 300, 'system': 150,
                    'iowait': 20, 'steal': 0, 'clock_ticks_per_second': 100},
            'memory': {},
            'network': {'primary_interface': 'eth0', 'interfaces': {'eth0': {
                'tx_bytes': 1000, 'rx_bytes': 2000, 'tx_packets': 10, 'rx_packets': 20,
            }}},
            'processes': {'gunicorn': {'user_ticks': 10, 'system_ticks': 5}},
            'database': {
                'database': {'xact_commit': 10, 'xact_rollback': 0, 'blks_hit': 100,
                             'blks_read': 5, 'tup_returned': 20, 'tup_fetched': 10,
                             'tup_inserted': 1, 'tup_updated': 2, 'tup_deleted': 0,
                             'temp_bytes': 0, 'deadlocks': 0},
                'pg_stat_statements': {'calls': 50}, 'wal': {'wal_bytes': 1000},
            },
        }
        current = {
            'cpu': {'total': 1100, 'idle_total': 530, 'user': 350, 'system': 165,
                    'iowait': 25, 'steal': 0, 'clock_ticks_per_second': 100,
                    'load_average': [1, .5, .25]},
            'memory': {'total_mb': 2000, 'available_mb': 900, 'used_percent': 55, 'swap_used_mb': 0},
            'network': {'primary_interface': 'eth0', 'interfaces': {'eth0': {
                'tx_bytes': 126000, 'rx_bytes': 64000, 'tx_packets': 110, 'rx_packets': 120,
            }}},
            'tcp': {},
            'processes': {'gunicorn': {'user_ticks': 50, 'system_ticks': 15, 'process_count': 2, 'rss_mb': 160}},
            'database': {
                'database': {'xact_commit': 20, 'xact_rollback': 0, 'blks_hit': 190,
                             'blks_read': 10, 'tup_returned': 120, 'tup_fetched': 30,
                             'tup_inserted': 3, 'tup_updated': 5, 'tup_deleted': 1,
                             'temp_bytes': 0, 'deadlocks': 0, 'database_size_bytes': 10000},
                'activity': {'connections': 4, 'active': 2, 'waiting': 0,
                             'lock_waiting': 0, 'max_connections': 20},
                'locks': {'ungranted': 0}, 'pg_stat_statements': {'calls': 90},
                'wal': {'wal_bytes': 5000},
            },
        }
        row = flatten_metrics(current, previous, 1, offset_seconds=1, stage='test')
        self.assertEqual(row['cpu_percent'], 70)
        self.assertEqual(row['network_tx_mbps'], 1)
        self.assertEqual(row['gunicorn_cpu_percent'], 50)
        self.assertEqual(row['db_statements_per_second'], 40)
        self.assertEqual(row['db_connection_utilization_percent'], 20)

    def test_report_tree_has_required_files_and_no_raw_key(self):
        measured_stage = stage('5qps', 5, 40)
        capacity = {
            'maximum_observed_qps': 5, 'knee_offered_qps': 5,
            'knee_successful_qps': 5, 'recommended_sustained_qps': 3,
            'recommended_burst_qps': 4, 'headroom_percent': 40,
            'capacity_is_lower_bound': False,
        }
        dau = dau_capacity(capacity)
        report = {
            'schema_version': 2,
            'run': {'run_id': 'run-report-test', 'label': 'baseline', 'seed': 7,
                    'started_at': '2026-08-15T00:00:00Z', 'scenario': 'ramp',
                    'ramp_steps': [5], 'stage_seconds': 30, 'user_count': 4,
                    'endpoint_mix': {'dashboard': 100}},
            'machine': {'cpu_count': 2, 'memory_total_mb': 2048},
            'capacity': capacity,
            'knee': {'reason': 'not reached'},
            'bottleneck': {'primary': 'no proven saturation point',
                           'evidence': ['bounded run'], 'next': 'increase one step'},
            'dau': dau,
            'recommended_stage': measured_stage,
            'request_amplification': AMPLIFICATION_MODEL,
            'stages': [measured_stage],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'result'
            write_report_tree(
                root, report=report,
                requests=[{'stage': '5qps', 'status': 200, 'total_ms': 10}],
                server_metrics=[{'stage': '5qps', 'cpu_percent': 20}],
                db_metrics=[{'stage': '5qps', 'db_connections': 2}],
            )
            files = {str(path.relative_to(root)) for path in root.rglob('*') if path.is_file()}
            serialized = (root / 'report.json').read_text(encoding='utf-8')
            knee_chart = (root / 'charts/qps-vs-p99-queue.svg').read_text(encoding='utf-8')
        self.assertIn('raw/requests.csv', files)
        self.assertIn('raw/server-metrics.csv', files)
        self.assertIn('raw/db-metrics.csv', files)
        self.assertIn('charts/qps-vs-p99-queue.svg', files)
        self.assertIn('report.md', files)
        self.assertIn('summary.txt', files)
        self.assertNotIn(TEST_KEY, serialized)
        self.assertFalse(json.loads(serialized)['machine'].get('storage_benchmark_performed', False))
        self.assertIn('KNEE 5 QPS', knee_chart)


if __name__ == '__main__':
    unittest.main()
