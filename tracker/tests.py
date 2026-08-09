import datetime
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .analytics import build_dashboard_overview
from .models import KnowledgePoint, LaunchToken, LearningIssue, TimeLog


def completed_session(user, *, day=None, minutes=60, subject='math', note='完整学习总结'):
    day = day or timezone.localdate()
    start = timezone.make_aware(
        datetime.datetime.combine(day, datetime.time(8, 0)),
        timezone.get_current_timezone(),
    )
    return TimeLog.objects.create(
        user=user,
        category=subject,
        start_time=start,
        end_time=start + datetime.timedelta(minutes=minutes),
        status='completed',
        chapter='第一章',
        topic='核心主题',
        note=note,
        breakthrough='掌握了关键方法',
        problems='仍需提高速度',
        next_action='明天完成练习',
    )


class HistoricalMigrationTests(TransactionTestCase):
    migrate_from = [('tracker', '0006_timelog_start_time_index')]
    migrate_to = [('tracker', '0008_backfill_session_ownership')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'] + self.migrate_from
        executor.migrate(old_targets)
        apps = executor.loader.project_state(old_targets).apps
        User = apps.get_model('auth', 'User')
        owner = User.objects.create(username='historical-owner', is_active=True, is_superuser=True)
        TimeLogOld = apps.get_model('tracker', 'TimeLog')
        start = timezone.now() - datetime.timedelta(minutes=75)
        self.log_id = TimeLogOld.objects.create(
            category='english', start_time=start, end_time=start + datetime.timedelta(minutes=75), note='不可丢失的旧记录',
        ).pk
        executor = MigrationExecutor(connection)
        new_targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'] + self.migrate_to
        executor.migrate(new_targets)
        self.apps = executor.loader.project_state(new_targets).apps
        self.owner_id = owner.pk

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_preserves_primary_key_duration_note_and_assigns_owner(self):
        Session = self.apps.get_model('tracker', 'TimeLog')
        row = Session.objects.get(pk=self.log_id)
        self.assertEqual(row.user_id, self.owner_id)
        self.assertEqual(row.note, '不可丢失的旧记录')
        self.assertEqual(row.status, 'completed')
        self.assertEqual(int((row.end_time - row.start_time).total_seconds() / 60), 75)


@override_settings(SECURE_SSL_REDIRECT=False)
class AuthAndIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user('alice', password='valid-test-password')
        self.bob = User.objects.create_user('bob', password='valid-test-password')
        self.alice_session = completed_session(self.alice, note='ALICE-PRIVATE')
        self.bob_session = completed_session(self.bob, note='BOB-PRIVATE', subject='english')
        LearningIssue.objects.create(user=self.bob, category='math', issue_type='concept_error', description='BOB-ISSUE')
        KnowledgePoint.objects.create(user=self.bob, category='math', name='BOB-KNOWLEDGE')

    def test_dashboard_redirects_anonymous_to_login_with_next(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertIn('next=/', response.url)

    def test_session_login_and_complete_user_isolation(self):
        self.client.force_login(self.alice)
        sessions = self.client.get('/api/sessions/').json()['results']
        self.assertEqual([row['id'] for row in sessions], [self.alice_session.pk])
        self.assertEqual(self.client.get(f'/api/sessions/{self.bob_session.pk}/').status_code, 404)
        self.assertNotContains(self.client.get('/api/export/json/'), 'BOB-PRIVATE')
        self.assertNotContains(self.client.get('/api/issues/'), 'BOB-ISSUE')
        self.assertNotContains(self.client.get('/api/knowledge/'), 'BOB-KNOWLEDGE')

    def test_passkey_routes_and_secure_session_settings_are_enabled(self):
        self.assertIn('allauth.mfa', settings.INSTALLED_APPS)
        self.assertTrue(settings.MFA_PASSKEY_LOGIN_ENABLED)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        response = self.client.get('/accounts/2fa/')
        self.assertIn(response.status_code, (200, 302))


@override_settings(SECURE_SSL_REDIRECT=False)
class SessionWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('learner', password='password')
        self.client.force_login(self.user)

    def test_direct_start_is_idempotent_and_uses_subject_alias(self):
        first = self.client.get('/start/professional')
        second = self.client.get('/start/professional')
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(TimeLog.objects.filter(user=self.user, status='running').count(), 1)
        self.assertEqual(TimeLog.objects.get(user=self.user).category, 'major')

    def test_api_reuses_same_subject_and_rejects_parallel_subject(self):
        first = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json')
        repeated = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json')
        conflict = self.client.post('/api/sessions/', {'subject': 'english'}, content_type='application/json')
        self.assertEqual(first.status_code, 201)
        self.assertFalse(first.json()['reused'])
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json()['reused'])
        self.assertEqual(conflict.status_code, 409)

    def test_finish_requires_deliberate_structured_reflection(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json').json()['session']['id']
        invalid = self.client.post(
            f'/api/sessions/{session_id}/finish/', {'note': 'only a note'}, content_type='application/json',
        )
        self.assertEqual(invalid.status_code, 400)
        payload = {
            'topic': '函数', 'note': '完成题目并复盘', 'breakthrough': '理解了转换',
            'problems': '计算速度偏慢', 'next_action': '再练十题', 'focus_level': 4,
        }
        response = self.client.post(f'/api/sessions/{session_id}/finish/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        session = TimeLog.objects.get(pk=session_id)
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.next_action, '再练十题')


@override_settings(SECURE_SSL_REDIRECT=False)
class AnalyticsAndExportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('analyst', password='password')
        self.other = get_user_model().objects.create_user('other', password='password')
        self.client.force_login(self.user)

    def test_five_hour_streak_heatmap_threshold_and_start_time(self):
        today = timezone.localdate()
        completed_session(self.user, day=today - datetime.timedelta(days=2), minutes=301)
        completed_session(self.user, day=today - datetime.timedelta(days=1), minutes=300)
        completed_session(self.user, day=today, minutes=299)
        overview = build_dashboard_overview(self.user, 7)
        self.assertEqual(overview['summary']['five_hour_days'], 2)
        self.assertEqual(overview['summary']['longest_five_hour_streak'], 2)
        self.assertEqual(overview['summary']['current_streak'], 3)
        self.assertEqual(overview['heatmap'][-1]['level'], 2)
        self.assertEqual(overview['heatmap'][-2]['level'], 4)
        self.assertEqual(overview['summary']['average_start_time'], '08:00')

    def test_exports_keep_raw_reflection_and_filters(self):
        completed_session(self.user, subject='math', note='RAW-REFLECTION-SENTINEL')
        completed_session(self.other, subject='english', note='OTHER-SECRET')
        response = self.client.get('/api/export/json/?subject=math')
        payload = json.loads(response.content)
        self.assertEqual(len(payload['sessions']), 1)
        self.assertEqual(payload['sessions'][0]['note'], 'RAW-REFLECTION-SENTINEL')
        self.assertNotIn('OTHER-SECRET', response.content.decode())
        markdown = self.client.get('/api/export/markdown/?subject=math').content.decode()
        self.assertIn('RAW-REFLECTION-SENTINEL', markdown)


@override_settings(SECURE_SSL_REDIRECT=False)
class LaunchTokenTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('launcher', password='password')

    def test_token_is_scoped_idempotent_and_does_not_expose_private_data(self):
        token, raw = LaunchToken.issue(user=self.user, name='desk', category='english')
        first = self.client.get(f'/launch/{raw}')
        second = self.client.get(f'/launch/{raw}')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(TimeLog.objects.filter(user=self.user, status='running').count(), 1)
        self.assertNotContains(first, token.token_digest)
        directives = {item.strip() for item in first['Cache-Control'].split(',')}
        self.assertTrue({'private', 'no-store', 'max-age=0'}.issubset(directives))

    def test_revoked_and_expired_tokens_fail_closed(self):
        revoked, raw_revoked = LaunchToken.issue(user=self.user, name='revoked', category='math', is_active=False)
        expired, raw_expired = LaunchToken.issue(
            user=self.user, name='expired', category='math', expires_at=timezone.now() - datetime.timedelta(seconds=1),
        )
        self.assertEqual(self.client.get(f'/launch/{raw_revoked}').status_code, 404)
        self.assertEqual(self.client.post(f'/api/launch/{raw_expired}/start').status_code, 404)
