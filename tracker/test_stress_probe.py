import json
import time

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import LiveServerTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection

from .loadtest import _RUN_RATE_LIMITER, verify_run_token
from .models import GitHubNoteSync, TimeLog
from .stress_probe import _RATE_LIMITER
from stress_test.capacity_http import ControlClient, RequestSpec, VirtualUser


TEST_KEY = 's' * 48


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STRESS_TEST_ENABLED=True,
    STRESS_TEST_KEY=TEST_KEY,
    STRESS_TEST_MAX_RPS=100,
    STRESS_TEST_MAX_BODY_BYTES=4096,
    STRESS_TEST_ALLOW_DATA_SETUP=True,
    STRESS_TEST_MAX_USERS=3,
    STRESS_TEST_MAX_HISTORY_ROWS=3000,
    STRESS_TEST_RUN_TTL_SECONDS=3600,
    STRESS_TEST_NETWORK_INTERFACE='',
    STRESS_TEST_NETWORK_CAPACITY_MBPS=0,
    STRESS_TEST_GUNICORN_PORT=8000,
)
class StressTestProbeTests(TestCase):
    def setUp(self):
        _RATE_LIMITER.reset()
        _RUN_RATE_LIMITER.reset()

    def _post(self, payload=None, key=TEST_KEY):
        return self.client.post(
            '/api/stress-test/probe/',
            payload or {},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {key}',
        )

    def test_valid_capability_returns_metrics_without_database_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self._post({'request_id': 'sample-1', 'sample_metrics': True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(queries), 0)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['request_id'], 'sample-1')
        self.assertGreaterEqual(payload['metrics']['cpu']['cores'], 1)
        self.assertIn('available_mb', payload['metrics']['memory'])
        self.assertNotContains(response, TEST_KEY)
        self.assertEqual(response['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')

    def test_load_response_omits_metrics_and_bounds_request_id(self):
        response = self._post({'request_id': 'x' * 200, 'sample_metrics': False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['request_id'], 'x' * 64)
        self.assertNotIn('metrics', response.json())

    def test_disabled_short_or_invalid_keys_are_indistinguishable_404s(self):
        self.assertEqual(self._post(key='wrong-key').status_code, 404)
        with override_settings(STRESS_TEST_ENABLED=False):
            self.assertEqual(self._post().status_code, 404)
        with override_settings(STRESS_TEST_KEY='too-short'):
            self.assertEqual(self._post(key='too-short').status_code, 404)

    def test_rate_limit_returns_429_without_affecting_other_routes(self):
        with override_settings(STRESS_TEST_MAX_RPS=1):
            self.assertEqual(self._post().status_code, 200)
            limited = self._post()
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited['Retry-After'], '1')
        self.assertEqual(self.client.get('/accounts/login/').status_code, 200)

    def test_rejects_oversized_or_non_object_json(self):
        oversized = self._post({'padding': 'x' * 5000})
        self.assertEqual(oversized.status_code, 413)
        _RATE_LIMITER.reset()
        non_object = self.client.post(
            '/api/stress-test/probe/',
            data=json.dumps(['not', 'an', 'object']),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {TEST_KEY}',
        )
        self.assertEqual(non_object.status_code, 400)

    def test_recovery_cleanup_remains_available_after_fixture_creation_is_disabled(self):
        preserved = get_user_model().objects.create_user(
            'loadtest_run-recovery-test_real-user', password='password',
        )
        with override_settings(STRESS_TEST_ALLOW_DATA_SETUP=False):
            response = self._post({'action': 'cleanup', 'run_id': 'run-recovery-test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['fixtures']['deleted_users'], 0)
        self.assertTrue(get_user_model().objects.filter(pk=preserved.pk).exists())

    def test_begin_issues_short_lived_signed_instrumentation_token(self):
        response = self._post({
            'action': 'begin',
            'run_id': 'run-capacity-test',
            'max_rps': 12,
            'ttl_seconds': 600,
        })
        self.assertEqual(response.status_code, 200)
        run = response.json()['run']
        capability = verify_run_token(run['run_token'])
        self.assertEqual(capability['run_id'], 'run-capacity-test')
        self.assertEqual(capability['max_rps'], 12)
        self.assertNotContains(response, TEST_KEY)
        ordinary = self.client.get('/accounts/login/')
        self.assertNotIn('X-Load-Test-App-Wall-Ms', ordinary)
        invalid = self.client.get('/accounts/login/', HTTP_X_LOAD_TEST_RUN='invalid')
        self.assertNotIn('X-Load-Test-App-Wall-Ms', invalid)
        malformed = self.client.get(
            '/accounts/login/', HTTP_X_LOAD_TEST_RUN='lt1.%%%%.signature',
        )
        self.assertNotIn('X-Load-Test-App-Wall-Ms', malformed)

    @override_settings(STRESS_TEST_MAX_HISTORY_ROWS=100)
    def test_fixture_limit_fails_closed_instead_of_dropping_history_profiles(self):
        run_id = 'run-small-history'
        run_token = self._post({
            'action': 'begin', 'run_id': run_id, 'max_rps': 20,
        }).json()['run']['run_token']
        response = self._post({
            'action': 'provision', 'run_id': run_id, 'run_token': run_token,
            'user_count': 2, 'seed': 1,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('too small', response.json()['detail'])

    def test_isolated_fixtures_authenticate_instrument_and_cleanup(self):
        run_id = 'run-fixture-test'
        run_token = self._post({
            'action': 'begin', 'run_id': run_id, 'max_rps': 20,
        }).json()['run']['run_token']
        provisioned = self._post({
            'action': 'provision',
            'run_id': run_id,
            'run_token': run_token,
            'user_count': 2,
            'seed': 7,
        })
        self.assertEqual(provisioned.status_code, 200)
        fixtures = provisioned.json()['fixtures']
        self.assertEqual(len(fixtures['users']), 2)
        self.assertGreater(fixtures['history_rows'], 0)
        credential = fixtures['users'][0]
        self.client.cookies['sessionid'] = credential['session_key']
        measured = self.client.get(
            '/api/dashboard/overview/?days=180',
            HTTP_X_LOAD_TEST_RUN=run_token,
            HTTP_X_LOAD_TEST_PROXY_START=f't={time.time() - 0.01}',
        )
        self.assertEqual(measured.status_code, 200)
        self.assertIn('X-Load-Test-App-Wall-Ms', measured)
        self.assertIn('X-Load-Test-App-CPU-Ms', measured)
        self.assertIn('X-Load-Test-DB-Queries', measured)
        self.assertIn('X-Load-Test-DB-Writes', measured)
        self.assertIn('X-Load-Test-JSON-Render-Ms', measured)
        self.assertIn('X-Load-Test-Queue-Ms', measured)
        self.assertIn(measured['X-Load-Test-Cache'], {'hit', 'miss'})

        cleaned = self._post({
            # Recovery cleanup deliberately works with the long-lived key even
            # after a PC crash or short-lived run-token expiry.
            'action': 'cleanup', 'run_id': run_id,
        })
        self.assertEqual(cleaned.status_code, 200)
        self.assertEqual(cleaned.json()['fixtures']['deleted_users'], 2)
        self.assertFalse(get_user_model().objects.filter(username__startswith='loadtest_').exists())
        self.assertFalse(Session.objects.filter(session_key=credential['session_key']).exists())

    @override_settings(LEARNING_REPO='owner/private-notes')
    def test_finish_burst_never_dispatches_github_for_test_users(self):
        run_id = 'run-finish-test'
        run_token = self._post({
            'action': 'begin', 'run_id': run_id, 'max_rps': 20,
        }).json()['run']['run_token']
        fixtures = self._post({
            'action': 'provision', 'run_id': run_id, 'run_token': run_token,
            'user_count': 1, 'seed': 9,
        }).json()['fixtures']
        prepared = self._post({
            'action': 'prepare_finish', 'run_id': run_id, 'run_token': run_token,
            'limit': 1,
        }).json()['fixtures']['sessions'][0]
        self.client.cookies['sessionid'] = fixtures['users'][0]['session_key']
        response = self.client.post(
            f'/api/sessions/{prepared["session_id"]}/finish/',
            data=json.dumps({'title': '', 'details': '', 'efficiency_grade': 'A'}),
            content_type='application/json',
            HTTP_X_LOAD_TEST_RUN=run_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['github_note']['status'], 'loadtest-skipped')
        self.assertFalse(GitHubNoteSync.objects.filter(session_id=prepared['session_id']).exists())
        self.assertEqual(TimeLog.objects.get(pk=prepared['session_id']).status, 'completed')


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    STRESS_TEST_ENABLED=True,
    STRESS_TEST_KEY=TEST_KEY,
    STRESS_TEST_MAX_RPS=100,
    STRESS_TEST_MAX_BODY_BYTES=4096,
    STRESS_TEST_ALLOW_DATA_SETUP=True,
    STRESS_TEST_MAX_USERS=2,
    STRESS_TEST_MAX_HISTORY_ROWS=3000,
    STRESS_TEST_RUN_TTL_SECONDS=3600,
    STRESS_TEST_NETWORK_INTERFACE='',
    STRESS_TEST_NETWORK_CAPACITY_MBPS=0,
    STRESS_TEST_GUNICORN_PORT=8000,
)
class CapacityClientIntegrationTests(LiveServerTestCase):
    def setUp(self):
        _RATE_LIMITER.reset()
        _RUN_RATE_LIMITER.reset()

    def test_standard_library_client_runs_real_authenticated_api(self):
        control = ControlClient(
            f'{self.live_server_url}/api/stress-test/probe/', TEST_KEY, 5,
        )
        run = control.action(
            'begin', run_id='run-http-client', max_rps=20,
        )['run']
        fixtures = control.action(
            'provision', run_id=run['run_id'], run_token=run['run_token'],
            user_count=1, seed=11,
        )['fixtures']
        credential = fixtures['users'][0]
        user = VirtualUser(
            self.live_server_url,
            session_key=credential['session_key'],
            run_token=run['run_token'],
            timeout_seconds=5,
            username=credential['username'],
        )
        self.assertEqual(user.bootstrap()['status'], 200)
        result = user.request(
            RequestSpec('dashboard', 'GET', '/api/dashboard/overview/?days=180'),
            stage='integration', scenario='endpoint', offered_qps=1,
            offset_seconds=0,
        )
        self.assertEqual(result['status'], 200)
        self.assertIsNotNone(result['app_wall_ms'])
        self.assertIsNotNone(result['cpu_ms'])
        self.assertGreater(result['db_queries'], 0)
        self.assertIsNotNone(result['json_render_ms'])
        # No Nginx is present in LiveServerTestCase, so queue is correctly
        # unavailable instead of fabricated.
        self.assertIsNone(result['queue_ms'])
        updated = user.request(
            RequestSpec(
                'session_update', 'PATCH',
                f'/api/sessions/{credential["detail_uuid"]}/',
                {'title': 'CSRF-protected integration update'},
            ),
            stage='integration', scenario='endpoint', offered_qps=1,
            offset_seconds=0,
        )
        self.assertEqual(updated['status'], 200)
        self.assertGreaterEqual(updated['db_writes'], 1)
        cleaned = control.action('cleanup', run_id=run['run_id'])['fixtures']
        self.assertEqual(cleaned['deleted_users'], 1)
