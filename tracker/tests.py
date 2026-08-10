import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .analytics import build_dashboard_overview
from .learning_log import (
    archive_completed_task,
    github_branch_for_user,
    markdown_relative_path,
    render_session_markdown,
    sync_session_note,
)
from .models import (
    GitHubNoteSync,
    InviteCode,
    InviteRedemption,
    KnowledgePoint,
    LaunchToken,
    LearningIssue,
    SessionReview,
    TimeLog,
)

TEST_PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def completed_session(user, *, day=None, minutes=60, subject='math', title='完整学习总结', details='完整学习详情'):
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
        title=title,
        details=details,
        breakthrough='掌握了关键方法',
        problems='仍需提高速度',
        next_action='明天完成练习',
    )


class HistoricalMigrationTests(TransactionTestCase):
    migrate_from = [('tracker', '0006_timelog_start_time_index')]
    migrate_to = [('tracker', '0010_rename_note_title_add_details')]

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

    def test_preserves_primary_key_duration_note_as_title_and_assigns_owner(self):
        Session = self.apps.get_model('tracker', 'TimeLog')
        row = Session.objects.get(pk=self.log_id)
        self.assertEqual(row.user_id, self.owner_id)
        self.assertEqual(row.title, '不可丢失的旧记录')
        self.assertEqual(row.details, '')
        self.assertEqual(row.status, 'completed')
        self.assertEqual(int((row.end_time - row.start_time).total_seconds() / 60), 75)


@override_settings(SECURE_SSL_REDIRECT=False)
class AuthAndIsolationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user('alice', password='valid-test-password')
        self.bob = User.objects.create_user('bob', password='valid-test-password')
        self.alice_session = completed_session(self.alice, title='ALICE-PRIVATE')
        self.bob_session = completed_session(self.bob, title='BOB-PRIVATE', subject='english')
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
        self.client.force_login(self.alice)
        response = self.client.get('/accounts/2fa/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/accounts/2fa/webauthn/add/')

    @override_settings(DEBUG=True)
    def test_login_prioritizes_passkey_and_loads_project_styles(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Passkey')
        self.assertContains(response, 'id="passkey_login"')
        self.assertContains(response, 'tracker/auth.css')
        self.assertContains(response, 'iCloud Keychain')
        self.assertContains(response, 'https://hub.docker.com/r/ehzsy/time-tracker')
        self.assertContains(response, 'https://github.com/zsyeh/time-tracker')
        self.assertContains(response, 'https://github.com/zsyeh')
        self.assertContains(response, 'https://blog.ehzsy.site')

    @override_settings(DEBUG=True)
    def test_django_admin_login_uses_project_branding_and_styles(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Learning OS')
        self.assertContains(response, 'tracker/admin.css')


@override_settings(SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class InviteRegistrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            'invite-admin', password='valid-test-password', is_staff=True,
        )
        self.member = User.objects.create_user('existing-member', password='valid-test-password')

    def test_signup_page_is_open_but_requires_a_valid_invite(self):
        page = self.client.get('/accounts/signup/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'INVITE CODE')

        invalid = self.client.post('/accounts/signup/', {
            'username': 'no-invite-user',
            'password1': 'valid-signup-password-7614',
            'password2': 'valid-signup-password-7614',
            'invite_code': 'not-a-real-code',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'invalid, expired, or already used')
        self.assertFalse(get_user_model().objects.filter(username='no-invite-user').exists())

    def test_only_admin_can_issue_and_raw_code_is_shown_once(self):
        self.client.force_login(self.member)
        denied = self.client.post(
            '/api/invite-codes/', {'name': 'Denied'}, content_type='application/json',
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.post('/api/invite-codes/', {
            'name': 'One new member', 'max_uses': 1,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        raw_code = response.json()['raw_code']
        invite = InviteCode.objects.get()
        self.assertNotEqual(invite.code_digest, raw_code)
        self.assertEqual(invite.code_digest, InviteCode.digest(raw_code))
        listed = self.client.get('/api/invite-codes/').json()
        self.assertNotIn('raw_code', listed[0])

    def test_one_use_invite_creates_isolated_account_and_cannot_be_reused(self):
        invite, raw_code = InviteCode.issue(name='Single use', created_by=self.admin)
        response = self.client.post('/accounts/signup/', {
            'username': 'invited-learner',
            'password1': 'valid-signup-password-7614',
            'password2': 'valid-signup-password-7614',
            'invite_code': raw_code,
        })
        self.assertEqual(response.status_code, 302)
        learner = get_user_model().objects.get(username='invited-learner')
        self.assertTrue(InviteRedemption.objects.filter(invite=invite, user=learner).exists())
        invite.refresh_from_db()
        self.assertEqual(invite.use_count, 1)
        self.assertFalse(invite.is_active)

        self.client.logout()
        reused = self.client.post('/accounts/signup/', {
            'username': 'second-learner',
            'password1': 'valid-signup-password-7614',
            'password2': 'valid-signup-password-7614',
            'invite_code': raw_code,
        })
        self.assertEqual(reused.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='second-learner').exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class RuntimeSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('settings-owner', password='password')
        self.client.force_login(self.user)
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temporary_directory.name) / '.env'

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_reads_local_env_and_falls_back_to_original_defaults(self):
        self.env_path.write_text(
            'UNMANAGED_SECRET=preserved\n'
            'STUDY_ROOM_CODE=from-local-file\n'
            'TRACKER_HOMEPAGE_CONTENT="Local dashboard copy"\n',
            encoding='utf-8',
        )
        with self.settings(
            TRACKER_LOCAL_ENV_PATH=self.env_path,
            TRACKER_HEATMAP_START_DATE='2026-05-23',
            TRACKER_EXAM_DATE='2026-12-26',
            TRACKER_COUNTDOWN_LABEL='Default countdown',
            TRACKER_HOMEPAGE_CONTENT='',
            STUDY_ROOM_CODE='default-room',
        ):
            response = self.client.get('/api/settings/runtime/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['values']['study_room_code'], 'from-local-file')
        self.assertEqual(payload['values']['homepage_content'], 'Local dashboard copy')
        self.assertEqual(payload['values']['tracking_start_date'], '2026-05-23')
        self.assertEqual(payload['values']['countdown_label'], 'Default countdown')
        self.assertNotContains(response, 'UNMANAGED_SECRET')

    def test_save_is_atomic_preserves_unmanaged_values_and_updates_dashboard(self):
        self.env_path.write_text('UNMANAGED_SECRET=preserved\nSTUDY_ROOM_CODE=old-room\n', encoding='utf-8')
        values = {
            'homepage_content': 'A concise local heading',
            'study_room_code': 'new-room',
            'tracking_start_date': '2026-06-01',
            'exam_date': '2027-01-02',
            'countdown_label': 'Exam window',
        }
        with self.settings(
            TRACKER_LOCAL_ENV_PATH=self.env_path,
            TRACKER_HEATMAP_START_DATE='2026-05-23',
            TRACKER_EXAM_DATE='2026-12-26',
            TRACKER_COUNTDOWN_LABEL='Default countdown',
            TRACKER_HOMEPAGE_CONTENT='',
            STUDY_ROOM_CODE='default-room',
        ):
            response = self.client.put(
                '/api/settings/runtime/', values, content_type='application/json',
            )
            dashboard = self.client.get('/api/dashboard/overview/?days=180').json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['values'], values)
        rendered = self.env_path.read_text(encoding='utf-8')
        self.assertIn('UNMANAGED_SECRET=preserved', rendered)
        self.assertIn('STUDY_ROOM_CODE="new-room"', rendered)
        self.assertEqual(os.stat(self.env_path).st_mode & 0o777, 0o600)
        self.assertEqual(dashboard['private_display']['homepage_content'], values['homepage_content'])
        self.assertEqual(dashboard['private_display']['study_room_code'], values['study_room_code'])
        self.assertEqual(dashboard['private_display']['countdown_label'], values['countdown_label'])
        self.assertEqual(dashboard['calendar']['exam_date'], values['exam_date'])
        self.assertEqual(dashboard['calendar']['heatmap_start_date'], values['tracking_start_date'])

    def test_rejects_tracking_start_after_exam_date_without_changing_file(self):
        self.env_path.write_text('UNMANAGED=value\n', encoding='utf-8')
        original = self.env_path.read_text(encoding='utf-8')
        with self.settings(TRACKER_LOCAL_ENV_PATH=self.env_path):
            response = self.client.put('/api/settings/runtime/', {
                'homepage_content': '',
                'study_room_code': '',
                'tracking_start_date': '2027-01-03',
                'exam_date': '2027-01-02',
                'countdown_label': 'Exam',
            }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.env_path.read_text(encoding='utf-8'), original)


@override_settings(SECURE_SSL_REDIRECT=False, LEARNING_REPO='')
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

    def test_finish_requires_title_and_details_only(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json').json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=26),
        )
        invalid = self.client.post(
            f'/api/sessions/{session_id}/finish/', {'title': 'Only a title'}, content_type='application/json',
        )
        self.assertEqual(invalid.status_code, 400)
        payload = {
            'title': '函数复盘', 'details': '完成题目并复盘',
        }
        response = self.client.post(f'/api/sessions/{session_id}/finish/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['discarded'])
        session = TimeLog.objects.get(pk=session_id)
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.title, '函数复盘')
        self.assertEqual(session.details, '完成题目并复盘')

    @override_settings(LEARNING_REPO='zsyeh/personal-learning-notes')
    @mock.patch('tracker.learning_log.subprocess.Popen')
    def test_web_finish_queues_github_markdown_without_waiting_for_push(self, popen):
        session_id = self.client.post(
            '/api/sessions/', {'subject': 'math'}, content_type='application/json',
        ).json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=26),
        )
        response = self.client.post(
            f'/api/sessions/{session_id}/finish/',
            {'title': 'Limits review', 'details': '$$\\lim_{x \\to 0} f(x)$$'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['github_note']['status'], 'queued')
        self.assertTrue(GitHubNoteSync.objects.filter(session_id=session_id, status='pending').exists())
        popen.assert_called_once()

    def test_finish_discards_session_shorter_than_25_minutes(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'english'}, content_type='application/json').json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=24),
        )
        payload = {'title': 'Reading', 'details': 'Short review'}
        response = self.client.post(f'/api/sessions/{session_id}/finish/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['discarded'])
        self.assertEqual(response.json()['minimum_minutes'], 25)
        self.assertFalse(TimeLog.objects.filter(pk=session_id).exists())

    def test_finish_discards_session_longer_than_12_hours_without_form_data(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json').json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(hours=12, seconds=1),
        )
        response = self.client.post(
            f'/api/sessions/{session_id}/finish/', {}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['discard_reason'], 'longer_than_maximum')
        self.assertEqual(response.json()['maximum_hours'], 12)
        self.assertFalse(TimeLog.objects.filter(pk=session_id).exists())

    def test_new_start_replaces_stale_session_longer_than_12_hours(self):
        stale_id = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json').json()['session']['id']
        TimeLog.objects.filter(pk=stale_id).update(
            start_time=timezone.now() - datetime.timedelta(hours=13),
        )
        response = self.client.post('/api/sessions/', {'subject': 'english'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(TimeLog.objects.filter(pk=stale_id).exists())
        self.assertEqual(response.json()['session']['subject'], 'english')

    def test_abandon_deletes_running_session_instead_of_recording_it(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'training'}, content_type='application/json').json()['session']['id']
        response = self.client.post(f'/api/sessions/{session_id}/abandon/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['deleted'])
        self.assertFalse(TimeLog.objects.filter(pk=session_id).exists())
        self.assertFalse(TimeLog.objects.filter(status='abandoned').exists())


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
        self.assertEqual(overview['calendar']['today'], today.isoformat())
        self.assertEqual(overview['calendar']['exam_date'], settings.TRACKER_EXAM_DATE)
        self.assertGreaterEqual(
            datetime.date.fromisoformat(overview['heatmap'][0]['date']),
            datetime.date.fromisoformat(settings.TRACKER_HEATMAP_START_DATE),
        )
        self.assertEqual(overview['calendar']['heatmap_start_date'], overview['heatmap'][0]['date'])
        expected_days = max(0, (datetime.date.fromisoformat(settings.TRACKER_EXAM_DATE) - today).days)
        self.assertEqual(overview['calendar']['days_until_exam'], expected_days)

    @override_settings(STUDY_ROOM_CODE='test-room-code')
    def test_dashboard_returns_private_study_room_code_to_authenticated_user(self):
        overview = build_dashboard_overview(self.user, 7)
        self.assertEqual(overview['private_display']['study_room_code'], 'test-room-code')

    def test_exports_keep_raw_reflection_and_filters(self):
        completed_session(self.user, subject='math', title='RAW-TITLE-SENTINEL', details='RAW-DETAILS-SENTINEL')
        completed_session(self.other, subject='english', title='OTHER-SECRET')
        response = self.client.get('/api/export/json/?subject=math')
        payload = json.loads(response.content)
        self.assertEqual(len(payload['sessions']), 1)
        self.assertEqual(payload['sessions'][0]['title'], 'RAW-TITLE-SENTINEL')
        self.assertEqual(payload['sessions'][0]['details'], 'RAW-DETAILS-SENTINEL')
        self.assertNotIn('OTHER-SECRET', response.content.decode())
        markdown = self.client.get('/api/export/markdown/?subject=math').content.decode()
        self.assertIn('RAW-TITLE-SENTINEL', markdown)
        self.assertIn('RAW-DETAILS-SENTINEL', markdown)

    def test_compact_session_list_defers_details_until_drilldown(self):
        session = completed_session(
            self.user,
            title='VISIBLE-TITLE',
            details='DEFERRED-DETAILS',
        )
        compact = self.client.get('/api/sessions/?compact=1').json()['results'][0]
        self.assertEqual(compact['title'], 'VISIBLE-TITLE')
        self.assertNotIn('details', compact)
        detail = self.client.get(f'/api/sessions/{session.pk}/').json()
        self.assertEqual(detail['details'], 'DEFERRED-DETAILS')

    def test_global_search_spans_sessions_and_issues_without_full_bodies(self):
        session = completed_session(
            self.user,
            title='Fourier transform review',
            details='A long body about the Fourier kernel and Parseval identity.',
        )
        LearningIssue.objects.create(
            user=self.user,
            category='math',
            topic='Fourier sign error',
            issue_type='calculation_error',
            description='The Fourier exponent sign was reversed.',
        )
        completed_session(
            self.other,
            title='Fourier private record',
            details='OTHER-SEARCH-SECRET',
        )
        response = self.client.get('/api/search/?q=Fourier')
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual({item['kind'] for item in results}, {'session', 'issue'})
        self.assertIn(session.pk, [item['record_id'] for item in results if item['kind'] == 'session'])
        self.assertTrue(all('details' not in item for item in results))
        self.assertNotContains(response, 'OTHER-SEARCH-SECRET')

    def test_global_search_empty_query_avoids_unbounded_results(self):
        completed_session(self.user, title='Should not appear')
        response = self.client.get('/api/search/?q=')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [])


@override_settings(PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class GitHubNoteSyncTests(TestCase):
    def test_markdown_uses_one_unique_file_and_preserves_formula_source(self):
        task = {
            'id': 42,
            'category': 'math',
            'category_label': 'Mathematics',
            'start_time': '2026-08-09T08:05:00+08:00',
            'end_time': '2026-08-09T09:10:00+08:00',
            'duration_minutes': 65,
            'title': '# Limits review',
            'details': 'Formula: $$\\lim_{x \\to 0} f(x)$$',
        }
        path = str(markdown_relative_path(task))
        document = render_session_markdown(task)
        self.assertEqual(path, 'sessions/2026/08/2026-08-09-0805-42-limits-review.md')
        self.assertIn('# Limits review', document)
        self.assertIn('$$\\lim_{x \\to 0} f(x)$$', document)
        self.assertIn('session_id: 42', document)

    @override_settings(LEARNING_REPO='zsyeh/personal-learning-notes')
    @mock.patch('tracker.learning_log.archive_completed_task')
    def test_successful_retry_marks_the_durable_outbox_synced(self, archive):
        user = get_user_model().objects.create_user('sync-user', password='password')
        session = completed_session(user, title='Retry me', details='Markdown body')
        archive.return_value = {
            'status': 'pushed',
            'repository': 'zsyeh/personal-learning-notes',
            'commit': 'abc1234',
            'file': 'sessions/2026/08/example.md',
        }
        result = sync_session_note(session)
        sync = GitHubNoteSync.objects.get(session=session)
        self.assertEqual(result['status'], 'pushed')
        self.assertEqual(sync.status, 'synced')
        self.assertEqual(sync.attempts, 1)
        self.assertEqual(sync.markdown_path, 'sessions/2026/08/example.md')
        self.assertIsNotNone(sync.synced_at)

    def test_branch_names_follow_username_and_never_collide_with_main(self):
        with self.settings(LEARNING_REPO_MAIN_BRANCH='main'):
            self.assertEqual(
                github_branch_for_user('Alice', is_admin=False, user_id=7), 'Alice',
            )
            self.assertEqual(
                github_branch_for_user('main', is_admin=False, user_id=8), 'main-user-8',
            )
            self.assertEqual(
                github_branch_for_user('unsafe/name', is_admin=False, user_id=9), 'unsafe-name',
            )
            self.assertEqual(
                github_branch_for_user('someone', is_admin=True, user_id=10), 'main',
            )

    def test_real_git_push_routes_member_to_username_branch_and_admin_to_main(self):
        def run(*args, cwd=None):
            return subprocess.run(
                args, cwd=cwd, check=True, capture_output=True, text=True, timeout=20,
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            remote = root / 'notes.git'
            seed = root / 'seed'
            checkout = root / 'checkout'
            run('git', 'init', '--bare', str(remote))
            run('git', 'init', str(seed))
            run('git', 'config', 'user.name', 'Test Writer', cwd=seed)
            run('git', 'config', 'user.email', 'writer@example.test', cwd=seed)
            (seed / 'README.md').write_text('# Learning notes\n', encoding='utf-8')
            run('git', 'add', 'README.md', cwd=seed)
            run('git', 'commit', '-m', 'Initialize notes', cwd=seed)
            run('git', 'branch', '-M', 'main', cwd=seed)
            run('git', 'remote', 'add', 'origin', str(remote), cwd=seed)
            run('git', 'push', '-u', 'origin', 'main', cwd=seed)
            run('git', 'symbolic-ref', 'HEAD', 'refs/heads/main', cwd=remote)
            run('git', 'clone', str(remote), str(checkout))
            run('git', 'config', 'user.name', 'Test Writer', cwd=checkout)
            run('git', 'config', 'user.email', 'writer@example.test', cwd=checkout)

            member_task = {
                'id': 501,
                'category': 'math',
                'category_label': 'Mathematics',
                'start_time': '2026-08-10T08:00:00+08:00',
                'end_time': '2026-08-10T09:00:00+08:00',
                'duration_minutes': 60,
                'title': 'Member review',
                'details': 'Member Markdown body',
                'username': 'Alice',
                'user_id': 11,
                'is_admin': False,
            }
            admin_task = {
                **member_task,
                'id': 502,
                'start_time': '2026-08-10T10:00:00+08:00',
                'end_time': '2026-08-10T11:00:00+08:00',
                'title': 'Admin review',
                'details': 'Admin Markdown body',
                'username': 'administrator',
                'user_id': 1,
                'is_admin': True,
            }

            with self.settings(
                LEARNING_REPO='local/notes',
                LEARNING_REPO_PATH=checkout,
                LEARNING_REPO_MAIN_BRANCH='main',
            ):
                member_result = archive_completed_task(member_task)
                admin_result = archive_completed_task(admin_task)

            self.assertEqual(member_result['branch'], 'Alice')
            self.assertEqual(admin_result['branch'], 'main')
            member_document = run(
                'git', 'show', f"Alice:{member_result['file']}", cwd=checkout,
            ).stdout
            admin_document = run(
                'git', 'show', f"main:{admin_result['file']}", cwd=checkout,
            ).stdout
            self.assertIn('username: "Alice"', member_document)
            self.assertIn('Member Markdown body', member_document)
            self.assertIn('username: "administrator"', admin_document)
            self.assertIn('Admin Markdown body', admin_document)


@override_settings(SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class SessionReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reviewer', password='password')
        self.other = get_user_model().objects.create_user('other-reviewer', password='password')
        self.session = completed_session(self.user, title='Review this session')
        self.client.force_login(self.user)

    def test_review_visit_is_deduplicated_and_returns_daily_trend(self):
        first = self.client.post(f'/api/sessions/{self.session.pk}/reviews/')
        second = self.client.post(f'/api/sessions/{self.session.pk}/reviews/')
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()['created'])
        self.assertFalse(second.json()['created'])
        self.assertEqual(second.json()['total'], 1)
        self.assertEqual(second.json()['review_days'], 1)
        self.assertEqual(len(second.json()['daily']), 1)
        self.session.refresh_from_db()
        self.assertEqual(self.session.review_count, 1)
        self.assertIsNotNone(self.session.last_reviewed_at)

        SessionReview.objects.filter(session=self.session).update(
            reviewed_at=timezone.now() - datetime.timedelta(minutes=11),
        )
        third = self.client.post(f'/api/sessions/{self.session.pk}/reviews/')
        self.assertTrue(third.json()['created'])
        self.assertEqual(third.json()['total'], 2)
        self.assertEqual(SessionReview.objects.filter(session=self.session).count(), 2)

    def test_review_is_user_scoped_and_summary_contains_review_fields(self):
        self.client.post(f'/api/sessions/{self.session.pk}/reviews/')
        compact = self.client.get('/api/sessions/?compact=1').json()['results'][0]
        self.assertEqual(compact['review_count'], 1)
        self.assertIn('last_reviewed_at', compact)
        self.assertNotIn('details', compact)

        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(f'/api/sessions/{self.session.pk}/reviews/').status_code,
            404,
        )


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
