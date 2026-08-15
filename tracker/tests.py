import base64
import datetime
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .analytics import build_dashboard_overview
from .learning_log import (
    archive_completed_task,
    github_branch_for_user,
    markdown_relative_path,
    render_session_markdown,
    session_task,
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
    SessionShare,
    SiteConfiguration,
    StudyTag,
    TaskPreset,
    TimeLog,
    UserDataEncryptionPreference,
)
from .data_encryption import DataEncryptionError, PAYLOAD_PREFIX
from .web_views import _frontend_html

TEST_PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
TEST_DATA_ENCRYPTION_KEY = base64.urlsafe_b64encode(b'E' * 32).decode('ascii')


def completed_session(
    user,
    *,
    day=None,
    minutes=60,
    subject='math',
    title='完整学习总结',
    details='完整学习详情',
    efficiency_grade='A',
):
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
        efficiency_grade=efficiency_grade,
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


class SessionResourceMigrationTests(TransactionTestCase):
    migrate_from = [('tracker', '0015_site_configuration_math_visualization')]
    migrate_to = [('tracker', '0016_session_resources_and_shares')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'] + self.migrate_from
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps
        User = old_apps.get_model('auth', 'User')
        TimeLogOld = old_apps.get_model('tracker', 'TimeLog')
        owner = User.objects.create(username='uuid-migration-owner', is_active=True)
        start = timezone.now() - datetime.timedelta(hours=2)
        self.session_ids = [
            TimeLogOld.objects.create(
                user_id=owner.pk,
                category='math',
                start_time=start + datetime.timedelta(minutes=index),
                end_time=start + datetime.timedelta(minutes=60 + index),
                status='completed',
                title=f'Legacy session {index}',
            ).pk
            for index in range(2)
        ]
        executor = MigrationExecutor(connection)
        new_targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'] + self.migrate_to
        executor.migrate(new_targets)
        self.apps = executor.loader.project_state(new_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_sessions_receive_unique_valid_uuids(self):
        Session = self.apps.get_model('tracker', 'TimeLog')
        values = list(Session.objects.filter(pk__in=self.session_ids).values_list('uuid', flat=True))
        self.assertEqual(len(values), 2)
        self.assertEqual(len(set(values)), 2)
        for value in values:
            self.assertEqual(uuid.UUID(str(value)), value)


class EfficiencyGradeMigrationTests(TransactionTestCase):
    migrate_from = [('tracker', '0019_task_presets_and_tags')]
    migrate_to = [('tracker', '0020_timelog_efficiency_grade')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_targets = [
            node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'
        ] + self.migrate_from
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps
        User = old_apps.get_model('auth', 'User')
        TimeLogOld = old_apps.get_model('tracker', 'TimeLog')
        owner = User.objects.create(username='efficiency-migration-owner', is_active=True)
        start = timezone.now() - datetime.timedelta(hours=1)
        self.session_id = TimeLogOld.objects.create(
            user_id=owner.pk,
            category='math',
            start_time=start,
            end_time=start + datetime.timedelta(minutes=60),
            status='completed',
        ).pk

        executor = MigrationExecutor(connection)
        new_targets = [
            node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracker'
        ] + self.migrate_to
        executor.migrate(new_targets)
        self.apps = executor.loader.project_state(new_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_session_defaults_to_grade_a(self):
        Session = self.apps.get_model('tracker', 'TimeLog')
        self.assertEqual(Session.objects.get(pk=self.session_id).efficiency_grade, 'A')


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

    def test_uuid_detail_is_owned_and_stable_across_edits(self):
        self.client.force_login(self.alice)
        resource_url = f'/api/sessions/{self.alice_session.uuid}/'
        response = self.client.get(resource_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['uuid'], str(self.alice_session.uuid))
        self.assertEqual(
            self.client.get(f'/api/sessions/{self.bob_session.uuid}/').status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f'/api/sessions/{uuid.uuid4()}/').status_code,
            404,
        )
        updated = self.client.patch(
            resource_url,
            {'title': 'Changed title', 'subject': 'training', 'details': '# Updated'},
            content_type='application/json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['uuid'], str(self.alice_session.uuid))
        self.alice_session.refresh_from_db()
        self.assertEqual(self.alice_session.uuid, uuid.UUID(response.json()['uuid']))

    def test_passkey_routes_and_secure_session_settings_are_enabled(self):
        self.assertIn('allauth.mfa', settings.INSTALLED_APPS)
        self.assertTrue(settings.MFA_PASSKEY_LOGIN_ENABLED)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.client.force_login(self.alice)
        response = self.client.get('/accounts/2fa/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/accounts/2fa/webauthn/add/')
        self.assertNotContains(response, 'User Guide')

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
        self.assertContains(response, 'CREATE ACCOUNT')
        self.assertContains(response, '/guide/')

    @override_settings(DEBUG=True)
    def test_django_admin_login_uses_project_branding_and_styles(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Learning OS')
        self.assertContains(response, 'tracker/admin.css')


@override_settings(SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class AuthenticationPolicyTests(TestCase):
    network = '198.51.100.24'

    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('rate-user', password='correct')

    def tearDown(self):
        cache.clear()

    def test_twenty_failed_logins_are_allowed_before_clear_limit_feedback(self):
        for attempt in range(20):
            response = self.client.post('/accounts/login/', {
                'login': self.user.username,
                'password': 'wrong',
            }, REMOTE_ADDR=self.network)
            self.assertEqual(response.status_code, 200, attempt)
        limited = self.client.post('/accounts/login/', {
            'login': self.user.username,
            'password': 'wrong',
        }, REMOTE_ADDR=self.network)
        self.assertEqual(limited.status_code, 200)
        self.assertContains(limited, 'Too many failed login attempts. Try again later.')
        self.assertContains(limited, 'Continue with Passkey')


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
        self.assertContains(page, 'zsyeh7286@gmail.com')
        self.assertNotContains(page, 'href="/guide/"')

        invalid = self.client.post('/accounts/signup/', {
            'username': 'no-invite-user',
            'password1': 'valid-signup-password-7614',
            'password2': 'valid-signup-password-7614',
            'invite_code': 'not-a-real-code',
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'ACCOUNT NOT CREATED')
        self.assertContains(invalid, 'invalid, expired, or already used')
        self.assertFalse(get_user_model().objects.filter(username='no-invite-user').exists())

    def test_passkey_only_signup_requires_and_redeems_an_invite(self):
        page = self.client.get('/accounts/signup/passkey/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'INVITE + PASSKEY')
        self.assertContains(page, 'INVITE CODE')

        missing = self.client.post('/accounts/signup/passkey/', {
            'username': 'passkey-without-invite',
            'invite_code': '',
        })
        self.assertEqual(missing.status_code, 200)
        self.assertContains(missing, 'Enter an invite code')
        self.assertFalse(get_user_model().objects.filter(username='passkey-without-invite').exists())

        invite, raw_code = InviteCode.issue(name='Passkey access', created_by=self.admin)
        started = self.client.post('/accounts/signup/passkey/', {
            'username': 'passkey-only-user',
            'invite_code': raw_code,
        })
        self.assertEqual(started.status_code, 302)
        self.assertEqual(started.url, '/accounts/2fa/webauthn/signup/')
        user = get_user_model().objects.get(username='passkey-only-user')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(InviteRedemption.objects.filter(invite=invite, user=user).exists())

    def test_open_registration_removes_invite_requirement_from_all_signup_modes(self):
        SiteConfiguration.objects.create(singleton_key=1, registration_open=True)
        password_signup = self.client.post('/accounts/signup/', {
            'username': 'open-password-user',
            'password1': '1',
            'password2': '1',
            'invite_code': '',
        })
        self.assertEqual(password_signup.status_code, 302)
        self.client.logout()

        passkey_signup = self.client.post('/accounts/signup/passkey/', {
            'username': 'open-passkey-user',
            'invite_code': '',
        })
        self.assertEqual(passkey_signup.status_code, 302)
        self.assertFalse(get_user_model().objects.get(username='open-passkey-user').has_usable_password())
        self.assertEqual(InviteRedemption.objects.count(), 0)

    def test_ordinary_member_can_issue_only_one_single_use_invite_per_day(self):
        self.client.force_login(self.member)
        issued = self.client.post(
            '/api/invite-codes/',
            {'name': 'Daily share', 'max_uses': 99},
            content_type='application/json',
        )
        self.assertEqual(issued.status_code, 201)
        payload = issued.json()
        self.assertEqual(payload['max_uses'], 1)
        self.assertTrue(payload['is_self_service'])
        self.assertEqual(payload['issued_local_date'], timezone.localdate().isoformat())
        second = self.client.post(
            '/api/invite-codes/', {'name': 'Second daily share'}, content_type='application/json',
        )
        self.assertEqual(second.status_code, 409)
        self.assertIn('already been generated', second.json()['detail'])
        self.client.logout()
        registered = self.client.post('/accounts/signup/', {
            'username': 'daily-invited-user',
            'password1': '2',
            'password2': '2',
            'invite_code': payload['raw_code'],
        })
        self.assertEqual(registered.status_code, 302)
        self.client.force_login(self.member)
        owned = self.client.get('/api/invite-codes/').json()
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0]['visitors'][0]['username'], 'daily-invited-user')

    def test_admin_can_issue_configurable_invite_and_raw_code_is_shown_once(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/invite-codes/', {
            'name': 'Study group', 'max_uses': 7,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        raw_code = response.json()['raw_code']
        invite = InviteCode.objects.get()
        self.assertEqual(invite.max_uses, 7)
        self.assertFalse(invite.is_self_service)
        self.assertNotEqual(invite.code_digest, raw_code)
        self.assertEqual(invite.code_digest, InviteCode.digest(raw_code))
        listed = self.client.get('/api/invite-codes/').json()
        self.assertNotIn('raw_code', listed[0])

    def test_signup_accepts_a_one_character_numeric_password_and_recommends_passkey(self):
        invite, raw_code = InviteCode.issue(name='Weak password access', created_by=self.admin)
        page = self.client.get('/accounts/signup/')
        self.assertContains(page, 'Short or numeric passwords are accepted')
        self.assertContains(page, 'PASSKEY RECOMMENDED')
        response = self.client.post('/accounts/signup/', {
            'username': 'short-password-user',
            'password1': '1',
            'password2': '1',
            'invite_code': raw_code,
        })
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='short-password-user')
        self.assertTrue(user.check_password('1'))
        self.assertTrue(InviteRedemption.objects.filter(invite=invite, user=user).exists())

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

        self.client.force_login(self.admin)
        listed = self.client.get('/api/invite-codes/').json()[0]
        self.assertEqual(listed['visitors'][0]['username'], 'invited-learner')

    def test_admin_dashboard_generates_capacity_and_lists_visitors(self):
        self.client.force_login(self.admin)
        generated = self.client.post('/admin/tracker/invitecode/dashboard/', {
            'name': 'Study group',
            'max_uses': 7,
            'expires_at': '',
        }, follow=True)
        self.assertEqual(generated.status_code, 200)
        self.assertContains(generated, 'NEW CODE · COPY NOW')
        self.assertNotContains(generated, 'USER GUIDE')
        invite = InviteCode.objects.get(name='Study group')
        self.assertEqual(invite.max_uses, 7)
        self.assertEqual(invite.remaining_uses, 7)
        self.assertContains(generated, '7')

        visitor = get_user_model().objects.create_user('invited-visitor', password='password')
        InviteRedemption.objects.create(invite=invite, user=visitor)
        invite.use_count = 1
        invite.last_used_at = timezone.now()
        invite.save(update_fields=('use_count', 'last_used_at'))
        dashboard = self.client.get('/admin/tracker/invitecode/dashboard/')
        self.assertContains(dashboard, 'invited-visitor')
        self.assertContains(dashboard, 'REGISTERED VISITORS')
        self.assertEqual(invite.remaining_uses, 6)

        listed = self.client.get('/api/invite-codes/').json()[0]
        self.assertEqual(listed['remaining_uses'], 6)

    def test_admin_dashboard_can_open_and_close_registration(self):
        self.client.force_login(self.admin)
        opened = self.client.post('/admin/tracker/invitecode/dashboard/', {
            'action': 'registration_policy',
            'registration_open': 'on',
            'math_visualization_enabled': 'on',
        }, follow=True)
        self.assertEqual(opened.status_code, 200)
        self.assertContains(opened, 'Registration is open')
        self.assertContains(opened, 'MATH VISUALIZATION')
        configuration = SiteConfiguration.load()
        self.assertTrue(configuration.registration_open)
        self.assertTrue(configuration.math_visualization_enabled)
        self.assertEqual(configuration.updated_by, self.admin)

        closed = self.client.post('/admin/tracker/invitecode/dashboard/', {
            'action': 'registration_policy',
        }, follow=True)
        self.assertEqual(closed.status_code, 200)
        configuration.refresh_from_db()
        self.assertFalse(configuration.registration_open)
        self.assertFalse(configuration.math_visualization_enabled)
        self.assertContains(closed, 'Invite-only registration')

    def test_math_visualization_is_disabled_by_default(self):
        configuration = SiteConfiguration.load()
        self.assertFalse(configuration.math_visualization_enabled)
        self.assertFalse(SiteConfiguration.math_visualization_is_enabled())

    def test_admin_can_inspect_and_reset_login_rate_status(self):
        self.admin.is_superuser = True
        self.admin.save(update_fields=('is_superuser',))
        network = '198.51.100.91'
        cache.set(f'allauth:rl:login:ip:{network}', [timezone.now().timestamp()], 900)
        cache.set(f'allauth:rl:login_failed:ip:{network}', [timezone.now().timestamp()], 900)
        self.client.force_login(self.admin)
        page = self.client.get(
            '/admin/tracker/invitecode/auth-recovery/', {'network': network},
        )
        self.assertContains(page, 'Authentication recovery')
        self.assertContains(page, network)
        response = self.client.post('/admin/tracker/invitecode/auth-recovery/', {
            'network_address': network,
            'scope': 'network',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(cache.get(f'allauth:rl:login:ip:{network}'))
        self.assertIsNone(cache.get(f'allauth:rl:login_failed:ip:{network}'))


@override_settings(SECURE_SSL_REDIRECT=False, LEARNING_REPO='')
class TaskPresetAndTagTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('taxonomy-owner', password='password')
        self.other = get_user_model().objects.create_user('taxonomy-other', password='password')
        self.client.force_login(self.user)

    def _tag(self, name='Analysis'):
        response = self.client.post(
            '/api/study-tags/',
            {'name': name, 'color': 'blue'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _preset(self, name, *, parent=None, tag_ids=None, home=False, subject='math'):
        response = self.client.post(
            '/api/task-presets/',
            {
                'name': name,
                'subject': subject,
                'parent': parent,
                'tag_ids': tag_ids or [],
                'is_home_shortcut': home,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_user_can_build_four_levels_but_not_a_fifth_or_cross_owner_parent(self):
        calculus = self._preset('Calculus')
        limits = self._preset('Limits', parent=calculus['id'])
        techniques = self._preset('Techniques', parent=limits['id'])
        lhopital = self._preset("L'Hopital", parent=techniques['id'])
        self.assertEqual(lhopital['depth'], 4)
        self.assertEqual(lhopital['path'], "Calculus › Limits › Techniques › L'Hopital")

        fifth = self.client.post(
            '/api/task-presets/',
            {'name': 'Too deep', 'subject': 'math', 'parent': lhopital['id']},
            content_type='application/json',
        )
        self.assertEqual(fifth.status_code, 400)
        self.assertIn('four levels', fifth.content.decode('utf-8'))

        other_parent = TaskPreset.objects.create(
            user=self.other,
            subject='math',
            name='Private other task',
        )
        cross_owner = self.client.post(
            '/api/task-presets/',
            {'name': 'Invalid child', 'subject': 'math', 'parent': other_parent.pk},
            content_type='application/json',
        )
        self.assertEqual(cross_owner.status_code, 400)
        self.assertNotContains(self.client.get('/api/task-presets/'), 'Private other task')

    def test_home_preset_starts_subject_defaults_blank_note_and_drives_tag_stats(self):
        tag = self._tag('Core concept')
        calculus = self._preset('Calculus')
        limits = self._preset(
            'Limits',
            parent=calculus['id'],
            tag_ids=[tag['id']],
            home=True,
        )

        start = self.client.post(
            '/api/sessions/',
            {'task_preset': limits['id']},
            content_type='application/json',
        )
        self.assertEqual(start.status_code, 201)
        session_id = start.json()['session']['id']
        self.assertEqual(start.json()['session']['subject'], 'math')
        self.assertEqual(start.json()['session']['task_path'], 'Calculus › Limits')
        self.assertEqual([item['name'] for item in start.json()['session']['tags']], ['Core concept'])
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=40),
        )

        finish = self.client.post(
            f'/api/sessions/{session_id}/finish/',
            {'title': '   ', 'details': '', 'tag_ids': [tag['id']]},
            content_type='application/json',
        )
        self.assertEqual(finish.status_code, 200)
        session = TimeLog.objects.get(pk=session_id)
        self.assertEqual(session.title, 'Limits')
        self.assertEqual(session.details, '')
        self.assertEqual(list(session.tags.values_list('pk', flat=True)), [tag['id']])

        overview = self.client.get('/api/dashboard/overview/?days=180').json()
        self.assertEqual(overview['task_shortcuts'][0]['label'], 'Mathematics: Calculus › Limits')
        self.assertEqual(overview['tag_totals'][0]['name'], 'Core concept')
        self.assertEqual(overview['tag_totals'][0]['minutes'], 40)
        self.assertEqual(overview['task_totals'][0]['path'], 'Calculus › Limits')

        options = self.client.get('/api/completion-options/').json()
        self.assertIn('Limits', options['recent_titles'])
        self.assertEqual(options['tags'][0]['name'], 'Core concept')
        filtered = self.client.get(f"/api/sessions/?tag={tag['id']}").json()
        self.assertEqual(filtered['count'], 1)

    def test_tag_and_preset_mutations_are_owner_scoped(self):
        other_tag = StudyTag.objects.create(user=self.other, name='Other private tag')
        other_preset = TaskPreset.objects.create(
            user=self.other,
            subject='english',
            name='Other private preset',
        )
        self.assertEqual(
            self.client.patch(
                f'/api/study-tags/{other_tag.pk}/',
                {'name': 'Stolen'},
                content_type='application/json',
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/task-presets/{other_preset.pk}/',
                {'name': 'Stolen'},
                content_type='application/json',
            ).status_code,
            404,
        )
        invalid_start = self.client.post(
            '/api/sessions/',
            {'task_preset': other_preset.pk},
            content_type='application/json',
        )
        self.assertEqual(invalid_start.status_code, 404)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CONTACT_EMAIL='zsyeh7286@gmail.com',
    DEFAULT_FROM_EMAIL='zsyeh7286@gmail.com',
    CONTACT_RATE_LIMIT_PER_HOUR=3,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class PublicGuideAndContactTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_public_guide_has_registration_and_usage_entry_points(self):
        response = self.client.get('/guide/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register with an invite')
        self.assertContains(response, 'Read before editing')
        self.assertContains(response, 'zsyeh7286@gmail.com')

    def test_bilingual_legal_page_explains_exports_and_gpl(self):
        response = self.client.get('/legal/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Availability is not a promise')
        self.assertContains(response, '不保证数据绝不丢失')
        self.assertContains(response, 'GPL-3.0-or-later')

    def test_contact_sends_smtp_message_from_owner_to_owner_without_database_record(self):
        response = self.client.post('/contact/', {
            'name': 'Visitor Name',
            'reply_email': 'visitor@example.com',
            'message': 'I need help with an invitation code.',
            'website': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your message was sent to the administrator.')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.from_email, 'zsyeh7286@gmail.com')
        self.assertEqual(message.to, ['zsyeh7286@gmail.com'])
        self.assertEqual(message.reply_to, ['visitor@example.com'])
        self.assertIn('Visitor Name', message.body)

    def test_contact_honeypot_does_not_send(self):
        response = self.client.post('/contact/', {
            'name': 'Automated visitor',
            'reply_email': 'bot@example.com',
            'message': 'This automated message should not be delivered.',
            'website': 'https://spam.example',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(SECURE_SSL_REDIRECT=False)
class RuntimeSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('settings-owner', password='password')
        self.admin = get_user_model().objects.create_superuser(
            'settings-admin', password='password', email='admin@example.com',
        )
        self.client.force_login(self.admin)
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
        self.assertTrue(payload['writable'])
        self.assertNotContains(response, 'UNMANAGED_SECRET')

    def test_ordinary_user_cannot_read_or_write_superuser_env_values(self):
        self.env_path.write_text(
            'STUDY_ROOM_CODE=private-admin-room\n'
            'TRACKER_HOMEPAGE_CONTENT="Private admin copy"\n',
            encoding='utf-8',
        )
        self.client.force_login(self.user)
        with self.settings(
            TRACKER_LOCAL_ENV_PATH=self.env_path,
            STUDY_ROOM_CODE='private-process-room',
            TRACKER_HOMEPAGE_CONTENT='Private process copy',
        ):
            response = self.client.get('/api/settings/runtime/')
            dashboard = self.client.get('/api/dashboard/overview/?days=7').json()
            denied = self.client.put('/api/settings/runtime/', {
                'homepage_content': 'Attempted overwrite',
                'study_room_code': 'attempted-room',
                'tracking_start_date': '2026-05-23',
                'exam_date': '2026-12-26',
                'countdown_label': 'Attempted label',
            }, content_type='application/json')
        payload = response.json()
        self.assertEqual(payload['values']['study_room_code'], '')
        self.assertEqual(payload['values']['homepage_content'], '')
        self.assertFalse(payload['writable'])
        self.assertFalse(payload['local_env_exists'])
        self.assertEqual(dashboard['private_display']['study_room_code'], '')
        self.assertEqual(dashboard['private_display']['homepage_content'], '')
        self.assertEqual(denied.status_code, 403)
        self.assertIn('private-admin-room', self.env_path.read_text(encoding='utf-8'))

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

    def test_finish_accepts_title_and_markdown(self):
        session_id = self.client.post('/api/sessions/', {'subject': 'math'}, content_type='application/json').json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=26),
        )
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

    def test_finish_applies_selected_efficiency_grade_to_credited_time(self):
        session_id = self.client.post(
            '/api/sessions/', {'subject': 'math'}, content_type='application/json',
        ).json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=40),
        )

        response = self.client.post(
            f'/api/sessions/{session_id}/finish/',
            {'efficiency_grade': 'C'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()['session']
        self.assertEqual(payload['duration_minutes'], 40)
        self.assertEqual(payload['efficiency_grade'], 'C')
        self.assertEqual(payload['efficiency_coefficient'], 0.9)
        self.assertEqual(payload['credited_duration_minutes'], 36)
        session = TimeLog.objects.get(pk=session_id)
        self.assertEqual(session.efficiency_grade, 'C')
        self.assertEqual(session.credited_duration_minutes, 36)

    def test_finish_defaults_to_grade_a_and_rejects_unknown_grade(self):
        invalid_id = self.client.post(
            '/api/sessions/', {'subject': 'english'}, content_type='application/json',
        ).json()['session']['id']
        TimeLog.objects.filter(pk=invalid_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=30),
        )
        invalid = self.client.post(
            f'/api/sessions/{invalid_id}/finish/',
            {'efficiency_grade': 'G'},
            content_type='application/json',
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(TimeLog.objects.get(pk=invalid_id).status, 'running')

        TimeLog.objects.filter(pk=invalid_id).delete()
        default_id = self.client.post(
            '/api/sessions/', {'subject': 'english'}, content_type='application/json',
        ).json()['session']['id']
        TimeLog.objects.filter(pk=default_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=30),
        )
        completed = self.client.post(
            f'/api/sessions/{default_id}/finish/', {}, content_type='application/json',
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()['session']['efficiency_grade'], 'A')
        self.assertEqual(completed.json()['session']['credited_duration_minutes'], 30)

    @override_settings(LEARNING_REPO='zsyeh/personal-learning-notes')
    @mock.patch('tracker.learning_log.subprocess.Popen')
    def test_finish_allows_empty_title_and_markdown_and_queues_archive(self, popen):
        session_id = self.client.post(
            '/api/sessions/', {'subject': 'english'}, content_type='application/json',
        ).json()['session']['id']
        TimeLog.objects.filter(pk=session_id).update(
            start_time=timezone.now() - datetime.timedelta(minutes=26),
        )

        response = self.client.post(
            f'/api/sessions/{session_id}/finish/', {}, content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['discarded'])
        self.assertEqual(response.json()['github_note']['status'], 'queued')
        session = TimeLog.objects.get(pk=session_id)
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.title or '', '')
        self.assertEqual(session.details, '')
        self.assertTrue(GitHubNoteSync.objects.filter(session=session, status='pending').exists())
        popen.assert_called_once()

    def test_mcp_stop_allows_omitting_title_and_markdown(self):
        from .mcp_server import stop_task

        session = TimeLog.objects.create(
            user=self.user,
            category='major',
            status='running',
            start_time=timezone.now() - datetime.timedelta(minutes=26),
        )
        with self.settings(TRACKER_OWNER_USERNAME=self.user.username, LEARNING_REPO=''):
            result = stop_task()

        self.assertEqual(result['status'], 'completed')
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.title or '', '')
        self.assertEqual(session.details, '')

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

    def test_dashboard_uses_credited_duration_for_all_time_aggregates(self):
        today = timezone.localdate()
        completed_session(
            self.user,
            day=today,
            minutes=270,
            subject='math',
            efficiency_grade='B',
        )
        completed_session(
            self.user,
            day=today,
            minutes=40,
            subject='english',
            efficiency_grade='C',
        )

        overview = build_dashboard_overview(self.user, 7)

        self.assertEqual(overview['today']['minutes'], 293)
        self.assertEqual(overview['summary']['total_minutes'], 293)
        self.assertEqual(overview['summary']['five_hour_days'], 0)
        self.assertEqual(
            {row['subject']: row['minutes'] for row in overview['subject_totals']},
            {'math': 257, 'english': 36},
        )
        self.assertEqual(overview['weekly_totals'][-1]['minutes'], 293)

    def test_dashboard_exposes_the_global_math_visualization_flag(self):
        disabled = self.client.get('/api/dashboard/overview/?days=7').json()
        self.assertFalse(disabled['features']['math_visualization'])
        configuration = SiteConfiguration.load()
        configuration.math_visualization_enabled = True
        configuration.save(update_fields=('math_visualization_enabled', 'updated_at'))
        enabled = self.client.get('/api/dashboard/overview/?days=7').json()
        self.assertTrue(enabled['features']['math_visualization'])

    @override_settings(
        STUDY_ROOM_CODE='test-room-code',
        TRACKER_LOCAL_ENV_PATH='/tmp/time-tracker-tests/no-runtime.env',
    )
    def test_dashboard_hides_private_study_room_code_from_ordinary_user(self):
        overview = build_dashboard_overview(self.user, 7)
        self.assertEqual(overview['private_display']['study_room_code'], '')
        admin = get_user_model().objects.create_superuser(
            'overview-admin', password='password', email='overview@example.com',
        )
        admin_overview = build_dashboard_overview(admin, 7)
        self.assertEqual(admin_overview['private_display']['study_room_code'], 'test-room-code')

    def test_exports_keep_raw_reflection_and_filters(self):
        completed_session(
            self.user,
            subject='math',
            minutes=40,
            title='RAW-TITLE-SENTINEL',
            details='RAW-DETAILS-SENTINEL',
            efficiency_grade='C',
        )
        completed_session(self.other, subject='english', title='OTHER-SECRET')
        response = self.client.get('/api/export/json/?subject=math')
        payload = json.loads(response.content)
        self.assertEqual(len(payload['sessions']), 1)
        self.assertEqual(payload['sessions'][0]['title'], 'RAW-TITLE-SENTINEL')
        self.assertEqual(payload['sessions'][0]['details'], 'RAW-DETAILS-SENTINEL')
        self.assertEqual(payload['sessions'][0]['duration_minutes'], 40)
        self.assertEqual(payload['sessions'][0]['efficiency_grade'], 'C')
        self.assertEqual(payload['sessions'][0]['credited_duration_minutes'], 36)
        self.assertNotIn('OTHER-SECRET', response.content.decode())
        csv_export = self.client.get('/api/export/csv/?subject=math').content.decode()
        self.assertIn('efficiency_grade,efficiency_coefficient,credited_duration_minutes', csv_export)
        markdown = self.client.get('/api/export/markdown/?subject=math').content.decode()
        self.assertIn('RAW-TITLE-SENTINEL', markdown)
        self.assertIn('RAW-DETAILS-SENTINEL', markdown)
        self.assertIn('Efficiency: C (0.90)', markdown)
        self.assertIn('36 credited minutes', markdown)

    def test_compact_session_list_defers_details_until_drilldown(self):
        session = completed_session(
            self.user,
            title='VISIBLE-TITLE',
            details='DEFERRED-DETAILS',
        )
        summary = self.client.get('/api/sessions/').json()['results'][0]
        self.assertEqual(summary['title'], 'VISIBLE-TITLE')
        self.assertEqual(summary['uuid'], str(session.uuid))
        self.assertNotIn('details', summary)
        compact = self.client.get('/api/sessions/?compact=1').json()['results'][0]
        self.assertNotIn('details', compact)
        self.assertEqual(
            self.client.get('/api/sessions/?full=1').json()['results'][0]['details'],
            'DEFERRED-DETAILS',
        )
        detail = self.client.get(f'/api/sessions/{session.uuid}/').json()
        self.assertEqual(detail['details'], 'DEFERRED-DETAILS')
        self.assertEqual(self.client.get(f'/api/sessions/{session.pk}/').status_code, 200)

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

    def test_empty_completion_uses_safe_untitled_markdown_fallback(self):
        task = {
            'id': 43,
            'category': 'english',
            'category_label': 'English',
            'start_time': '2026-08-09T10:00:00+08:00',
            'end_time': '2026-08-09T10:30:00+08:00',
            'duration_minutes': 30,
            'title': '',
            'details': '',
        }

        self.assertEqual(
            str(markdown_relative_path(task)),
            'sessions/2026/08/2026-08-09-1000-43-untitled-session.md',
        )
        document = render_session_markdown(task)
        self.assertIn('title: "Untitled session"', document)
        self.assertIn('# Untitled session', document)

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


@override_settings(SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class SessionShareTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('share-owner', password='password')
        self.other = User.objects.create_user('share-other', password='password')
        self.session = completed_session(
            self.owner,
            title='Public calculus article',
            details='# Integral\n\n<script>window.pwned = true</script>\n\n$$\\int_0^1 x^2 dx$$',
        )
        self.manage_url = f'/api/sessions/{self.session.uuid}/share/'

    def _create_share(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.manage_url,
            {'expires_at': (timezone.now() + datetime.timedelta(days=2)).isoformat()},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        raw_token = urlsplit(response.json()['share_url']).path.rsplit('/', 1)[-1]
        return response, raw_token

    def test_share_is_private_until_owner_creates_high_entropy_hashed_token(self):
        self.client.force_login(self.owner)
        private = self.client.get(self.manage_url)
        self.assertEqual(private.json()['status'], 'private')
        self.assertFalse(private.json()['is_shared'])

        response, raw_token = self._create_share()
        share = SessionShare.objects.get(session=self.session)
        self.assertGreaterEqual(len(raw_token), 48)
        self.assertNotEqual(share.token_digest, raw_token)
        self.assertEqual(share.token_digest, SessionShare.digest(raw_token))
        self.assertTrue(response.json()['is_active'])
        self.assertNotIn(raw_token, str(share.__dict__))

    def test_valid_share_is_anonymous_read_only_and_minimal(self):
        _, raw_token = self._create_share()
        self.client.logout()
        public_url = f'/api/public/shares/{raw_token}/'
        response = self.client.get(public_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {
            'title', 'subject', 'start_time', 'end_time', 'duration_minutes', 'markdown',
        })
        self.assertEqual(response.json()['markdown'], self.session.details)
        serialized = json.dumps(response.json())
        for private_field in ('user_id', 'email', 'review_count', 'session_id', 'uuid', 'quick-start'):
            self.assertNotIn(private_field, serialized)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.client.force_login(self.owner)
        self.assertEqual(set(self.client.get(public_url).json()), set(response.json()))
        self.assertEqual(self.client.post(public_url, {}, content_type='application/json').status_code, 405)
        self.assertEqual(self.client.patch(public_url, {}, content_type='application/json').status_code, 405)

    def test_invalid_revoked_and_expired_tokens_return_404(self):
        invalid = self.client.get('/api/public/shares/not-a-token/')
        self.assertEqual(invalid.status_code, 404)
        self.assertIn('no-store', invalid['Cache-Control'])
        self.assertEqual(invalid['Referrer-Policy'], 'no-referrer')
        _, raw_token = self._create_share()
        self.assertEqual(self.client.delete(self.manage_url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/public/shares/{raw_token}/').status_code, 404)

        expired, expired_token = SessionShare.issue(session=self.session)
        expired.expires_at = timezone.now() - datetime.timedelta(seconds=1)
        expired.save(update_fields=('expires_at',))
        self.assertEqual(self.client.get(f'/api/public/shares/{expired_token}/').status_code, 404)

    def test_share_management_is_owner_scoped_and_csrf_protected(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.manage_url).status_code, 404)
        self.assertEqual(self.client.post(self.manage_url, {}, content_type='application/json').status_code, 404)
        self.assertEqual(self.client.delete(self.manage_url).status_code, 404)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(
            csrf_client.post(self.manage_url, {}, content_type='application/json').status_code,
            403,
        )
        csrf_client.get('/api/auth/session/')
        csrf = csrf_client.cookies['csrftoken'].value
        self.assertEqual(
            csrf_client.post(
                self.manage_url, {}, content_type='application/json', HTTP_X_CSRFTOKEN=csrf,
            ).status_code,
            201,
        )


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=TEST_PASSWORD_HASHERS,
    DATA_ENCRYPTION_MASTER_KEY=TEST_DATA_ENCRYPTION_KEY,
    DATA_ENCRYPTION_KEY_PATH='/unused/test-data-encryption.key',
)
class UserDataAtRestEncryptionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('encrypted-owner', password='password')
        self.other = User.objects.create_user('plaintext-owner', password='password')
        self.session = completed_session(
            self.owner,
            title='PRIVATE-TITLE-SENTINEL',
            details='# PRIVATE-MARKDOWN-SENTINEL',
        )
        self.session.learning_mode = 'exercise'
        self.session.difficulty = 4
        self.session.focus_level = 5
        self.session.save(update_fields=('learning_mode', 'difficulty', 'focus_level'))
        self.issue = LearningIssue.objects.create(
            user=self.owner,
            category='math',
            topic='PRIVATE-ISSUE-TOPIC',
            issue_type='concept_error',
            description='PRIVATE-ISSUE-DESCRIPTION',
            solution='PRIVATE-ISSUE-SOLUTION',
        )
        self.sync, _ = GitHubNoteSync.objects.get_or_create(session=self.session)
        self.sync.status = 'pending'
        self.sync.markdown_path = 'sessions/PRIVATE-TITLE-SENTINEL.md'
        self.sync.last_error = 'PRIVATE-SYNC-ERROR'
        self.sync.save(update_fields=('status', 'markdown_path', 'last_error'))
        self.other_session = completed_session(
            self.other,
            title='OTHER-PLAINTEXT-TITLE',
            details='OTHER-PLAINTEXT-DETAILS',
        )
        self.client.force_login(self.owner)
        self.settings_url = '/api/settings/data-encryption/'

    def _raw_session(self, session=None):
        return TimeLog.objects.filter(pk=(session or self.session).pk).values(
            'chapter', 'topic', 'title', 'details', 'breakthrough', 'problems',
            'next_action', 'learning_mode', 'difficulty', 'focus_level',
            'encrypted_summary', 'encrypted_content',
        ).get()

    def _raw_issue(self):
        return LearningIssue.objects.filter(pk=self.issue.pk).values(
            'topic', 'issue_type', 'description', 'solution', 'encrypted_content',
        ).get()

    def _raw_sync(self):
        return GitHubNoteSync.objects.filter(pk=self.sync.pk).values(
            'markdown_path', 'last_error', 'encrypted_content',
        ).get()

    def _enable(self):
        response = self.client.put(
            self.settings_url,
            {'enabled': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['enabled'])
        self.assertEqual(response.json()['mode'], 'server-managed-at-rest')
        self.assertNotIn('key', response.json())
        return response

    def test_default_is_plaintext_and_each_user_controls_only_their_policy(self):
        status_response = self.client.get(self.settings_url)
        self.assertEqual(status_response.status_code, 200)
        self.assertFalse(status_response.json()['enabled'])
        self.assertTrue(status_response.json()['available'])
        self.assertEqual(self._raw_session()['title'], 'PRIVATE-TITLE-SENTINEL')

        self._enable()
        self.assertTrue(UserDataEncryptionPreference.objects.get(user=self.owner).enabled)
        self.assertFalse(
            UserDataEncryptionPreference.objects.filter(user=self.other, enabled=True).exists(),
        )
        self.assertEqual(self._raw_session(self.other_session)['title'], 'OTHER-PLAINTEXT-TITLE')

    def test_enable_removes_private_plaintext_from_raw_database_but_orm_is_transparent(self):
        self._enable()
        raw_session = self._raw_session()
        raw_issue = self._raw_issue()
        raw_sync = self._raw_sync()

        self.assertIn(raw_session['title'], (None, ''))
        self.assertEqual(raw_session['details'], '')
        self.assertEqual(raw_session['chapter'], '')
        self.assertEqual(raw_session['learning_mode'], '')
        self.assertIsNone(raw_session['difficulty'])
        self.assertIsNone(raw_session['focus_level'])
        self.assertTrue(raw_session['encrypted_summary'].startswith(PAYLOAD_PREFIX))
        self.assertTrue(raw_session['encrypted_content'].startswith(PAYLOAD_PREFIX))
        self.assertEqual(raw_issue['topic'], '')
        self.assertEqual(raw_issue['description'], '')
        self.assertEqual(raw_issue['solution'], '')
        self.assertTrue(raw_issue['encrypted_content'].startswith(PAYLOAD_PREFIX))
        self.assertEqual(raw_sync['markdown_path'], '')
        self.assertEqual(raw_sync['last_error'], '')
        self.assertTrue(raw_sync['encrypted_content'].startswith(PAYLOAD_PREFIX))

        raw_dump = json.dumps({'session': raw_session, 'issue': raw_issue, 'sync': raw_sync})
        for sentinel in (
            'PRIVATE-TITLE-SENTINEL', 'PRIVATE-MARKDOWN-SENTINEL',
            'PRIVATE-ISSUE-TOPIC', 'PRIVATE-ISSUE-DESCRIPTION',
            'PRIVATE-ISSUE-SOLUTION',
            'PRIVATE-SYNC-ERROR',
        ):
            self.assertNotIn(sentinel, raw_dump)

        restored_session = TimeLog.objects.get(pk=self.session.pk)
        restored_issue = LearningIssue.objects.get(pk=self.issue.pk)
        restored_sync = GitHubNoteSync.objects.get(pk=self.sync.pk)
        self.assertEqual(restored_session.title, 'PRIVATE-TITLE-SENTINEL')
        self.assertEqual(restored_session.details, '# PRIVATE-MARKDOWN-SENTINEL')
        self.assertEqual(restored_session.learning_mode, 'exercise')
        self.assertEqual(restored_session.difficulty, 4)
        self.assertEqual(restored_session.focus_level, 5)
        self.assertEqual(restored_issue.topic, 'PRIVATE-ISSUE-TOPIC')
        self.assertEqual(restored_issue.description, 'PRIVATE-ISSUE-DESCRIPTION')
        self.assertEqual(restored_sync.markdown_path, 'sessions/PRIVATE-TITLE-SENTINEL.md')
        self.assertEqual(restored_sync.last_error, 'PRIVATE-SYNC-ERROR')

    def test_task_presets_tags_and_session_path_follow_encryption_policy(self):
        tag = StudyTag.objects.create(user=self.owner, name='PRIVATE-TAG-SENTINEL')
        preset = TaskPreset.objects.create(
            user=self.owner,
            subject='math',
            name='PRIVATE-PRESET-SENTINEL',
            is_home_shortcut=True,
        )
        preset.tags.add(tag)
        self.session.task_preset = preset
        self.session.task_path = 'PRIVATE-PRESET-SENTINEL'
        self.session.tags.add(tag)
        self.session.save(update_fields=('task_preset', 'task_path'))

        self._enable()
        raw_tag = StudyTag.objects.filter(pk=tag.pk).values('name', 'encrypted_content').get()
        raw_preset = TaskPreset.objects.filter(pk=preset.pk).values('name', 'encrypted_content').get()
        raw_session = self._raw_session()
        raw_session_path = TimeLog.objects.filter(pk=self.session.pk).values('task_path').get()
        self.assertEqual(raw_tag['name'], '')
        self.assertEqual(raw_preset['name'], '')
        self.assertEqual(raw_session_path['task_path'], '')
        self.assertTrue(raw_tag['encrypted_content'].startswith(PAYLOAD_PREFIX))
        self.assertTrue(raw_preset['encrypted_content'].startswith(PAYLOAD_PREFIX))
        self.assertNotIn('PRIVATE-PRESET-SENTINEL', raw_session['encrypted_summary'])
        self.assertEqual(StudyTag.objects.get(pk=tag.pk).name, 'PRIVATE-TAG-SENTINEL')
        self.assertEqual(TaskPreset.objects.get(pk=preset.pk).name, 'PRIVATE-PRESET-SENTINEL')
        self.assertEqual(TimeLog.objects.get(pk=self.session.pk).task_path, 'PRIVATE-PRESET-SENTINEL')

        disabled = self.client.put(
            self.settings_url,
            {'enabled': False},
            content_type='application/json',
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(StudyTag.objects.get(pk=tag.pk).name, 'PRIVATE-TAG-SENTINEL')
        self.assertEqual(TaskPreset.objects.get(pk=preset.pk).name, 'PRIVATE-PRESET-SENTINEL')

    def test_encrypted_records_keep_list_detail_search_export_github_and_share_behavior(self):
        self._enable()

        with CaptureQueriesContext(connection) as queries:
            listing = self.client.get('/api/sessions/').json()['results'][0]
        self.assertEqual(listing['title'], 'PRIVATE-TITLE-SENTINEL')
        self.assertNotIn('details', listing)
        list_queries = [
            query['sql'] for query in queries
            if 'FROM "tracker_timelog"' in query['sql'] and 'COUNT(' not in query['sql']
        ]
        self.assertTrue(list_queries)
        self.assertTrue(all('encrypted_content' not in query for query in list_queries))
        detail = self.client.get(f'/api/sessions/{self.session.uuid}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['details'], '# PRIVATE-MARKDOWN-SENTINEL')

        history_search = self.client.get('/api/sessions/?search=MARKDOWN-SENTINEL')
        self.assertEqual(history_search.json()['count'], 1)
        global_search = self.client.get('/api/search/?q=PRIVATE-ISSUE-DESCRIPTION')
        self.assertEqual([row['kind'] for row in global_search.json()['results']], ['issue'])

        exported = self.client.get('/api/export/markdown/').content.decode('utf-8')
        self.assertIn('PRIVATE-TITLE-SENTINEL', exported)
        self.assertIn('PRIVATE-MARKDOWN-SENTINEL', exported)
        task = session_task(TimeLog.objects.get(pk=self.session.pk))
        self.assertEqual(task['title'], 'PRIVATE-TITLE-SENTINEL')
        self.assertEqual(task['details'], '# PRIVATE-MARKDOWN-SENTINEL')

        share_response = self.client.post(
            f'/api/sessions/{self.session.uuid}/share/',
            {},
            content_type='application/json',
        )
        self.assertEqual(share_response.status_code, 201)
        raw_token = urlsplit(share_response.json()['share_url']).path.rsplit('/', 1)[-1]
        self.client.logout()
        public = self.client.get(f'/api/public/shares/{raw_token}/')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()['title'], 'PRIVATE-TITLE-SENTINEL')
        self.assertEqual(public.json()['markdown'], '# PRIVATE-MARKDOWN-SENTINEL')

    def test_new_writes_updates_and_disable_transition_preserve_content(self):
        self._enable()
        new_session = completed_session(
            self.owner,
            title='NEW-ENCRYPTED-TITLE',
            details='NEW-ENCRYPTED-DETAILS',
        )
        raw_new = self._raw_session(new_session)
        self.assertIn(raw_new['title'], (None, ''))
        self.assertNotIn('NEW-ENCRYPTED-TITLE', raw_new['encrypted_summary'])
        new_issue = LearningIssue.objects.create(
            user=self.owner,
            category='math',
            issue_type='concept_error',
            description='NEW-ENCRYPTED-ISSUE',
        )
        raw_new_issue = LearningIssue.objects.filter(pk=new_issue.pk).values(
            'description', 'encrypted_content',
        ).get()
        self.assertEqual(raw_new_issue['description'], '')
        self.assertNotIn('NEW-ENCRYPTED-ISSUE', raw_new_issue['encrypted_content'])

        updated = self.client.patch(
            f'/api/sessions/{self.session.uuid}/',
            {'title': 'UPDATED-ENCRYPTED-TITLE', 'details': 'UPDATED-ENCRYPTED-DETAILS'},
            content_type='application/json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['title'], 'UPDATED-ENCRYPTED-TITLE')
        raw_updated = self._raw_session()
        self.assertIn(raw_updated['title'], (None, ''))
        self.assertNotIn('UPDATED-ENCRYPTED-TITLE', raw_updated['encrypted_summary'])
        self.assertNotIn('UPDATED-ENCRYPTED-DETAILS', raw_updated['encrypted_content'])

        disabled = self.client.put(
            self.settings_url,
            {'enabled': False},
            content_type='application/json',
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()['enabled'])
        raw_plaintext = self._raw_session()
        self.assertEqual(raw_plaintext['title'], 'UPDATED-ENCRYPTED-TITLE')
        self.assertEqual(raw_plaintext['details'], 'UPDATED-ENCRYPTED-DETAILS')
        self.assertEqual(raw_plaintext['encrypted_summary'], '')
        self.assertEqual(raw_plaintext['encrypted_content'], '')

    def test_payloads_use_random_nonces_and_reject_database_tampering(self):
        self._enable()
        first_payload = self._raw_session()['encrypted_summary']
        self.client.put(
            self.settings_url, {'enabled': False}, content_type='application/json',
        )
        self._enable()
        second_payload = self._raw_session()['encrypted_summary']
        self.assertNotEqual(first_payload, second_payload)

        replacement = 'A' if second_payload[-10] != 'A' else 'B'
        tampered = f'{second_payload[:-10]}{replacement}{second_payload[-9:]}'
        TimeLog.objects.filter(pk=self.session.pk).update(encrypted_summary=tampered)
        with self.assertRaises(DataEncryptionError):
            TimeLog.objects.get(pk=self.session.pk)

    def test_missing_existing_key_fails_closed_without_generating_a_replacement(self):
        self._enable()
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / 'missing.key'
            with self.settings(
                DATA_ENCRYPTION_MASTER_KEY='',
                DATA_ENCRYPTION_KEY_PATH=missing_path,
            ):
                response = self.client.put(
                    self.settings_url,
                    {'enabled': True},
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 503)
                self.assertFalse(missing_path.exists())
        self.assertTrue(UserDataEncryptionPreference.objects.get(user=self.owner).enabled)

    def test_first_enable_creates_a_private_server_key_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            key_path = Path(temporary_directory) / 'generated.key'
            with self.settings(
                DATA_ENCRYPTION_MASTER_KEY='',
                DATA_ENCRYPTION_KEY_PATH=key_path,
            ):
                self._enable()
                self.assertTrue(key_path.exists())
                self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(
                    TimeLog.objects.get(pk=self.session.pk).title,
                    'PRIVATE-TITLE-SENTINEL',
                )

    def test_toggle_is_csrf_protected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        denied = csrf_client.put(
            self.settings_url, {'enabled': True}, content_type='application/json',
        )
        self.assertEqual(denied.status_code, 403)


@override_settings(SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
class SpaHistoryFallbackTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.frontend_dist = Path(self.temp.name)
        (self.frontend_dist / 'index.html').write_text(
            '<!doctype html><div id="spa-history-test">SPA</div>', encoding='utf-8',
        )
        self.settings_override = override_settings(FRONTEND_DIST=self.frontend_dist)
        self.settings_override.enable()
        _frontend_html.cache_clear()
        self.user = get_user_model().objects.create_user('spa-user', password='password')
        self.session = completed_session(self.user)

    def tearDown(self):
        _frontend_html.cache_clear()
        self.settings_override.disable()
        self.temp.cleanup()

    def test_private_vue_routes_support_direct_refresh_for_authenticated_user(self):
        self.client.force_login(self.user)
        paths = (
            '/today', '/trends', '/sessions', f'/sessions/{self.session.uuid}',
            '/issues', '/settings',
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'spa-history-test')
                self.assertIn('private', response['Cache-Control'])

    def test_private_deep_link_redirects_anonymous_but_share_shell_does_not(self):
        private = self.client.get(f'/sessions/{self.session.uuid}')
        self.assertEqual(private.status_code, 302)
        self.assertIn('next=', private.url)
        public = self.client.get('/share/example-token')
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'spa-history-test')
        self.assertIn('no-store', public['Cache-Control'])
        self.assertIn("default-src 'self'", public['Content-Security-Policy'])

    def test_spa_fallback_does_not_swallow_django_endpoint_namespaces(self):
        paths = (
            '/api/not-a-route/', '/accounts/not-a-route/', '/admin/not-a-route/',
            '/start/not-a-subject', '/launch/not-a-token',
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertNotContains(response, 'spa-history-test', status_code=response.status_code)


@override_settings(SECURE_SSL_REDIRECT=False)
class LaunchTokenTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('launcher', password='password')

    def _issue_pair(self, **fields):
        return LaunchToken.issue_with_disturbance(
            user=self.user,
            name=fields.pop('name', 'iPhone'),
            category=fields.pop('category', 'english'),
            available_from=fields.pop('available_from', datetime.time(0, 0)),
            available_until=fields.pop('available_until', datetime.time(0, 0)),
            **fields,
        )

    def test_token_is_scoped_idempotent_and_does_not_expose_private_data(self):
        token, raw = LaunchToken.issue(
            user=self.user,
            name='desk',
            category='english',
            available_from=datetime.time(0, 0),
            available_until=datetime.time(0, 0),
        )
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
            user=self.user, name='expired', category='math',
            expires_at=timezone.now() - datetime.timedelta(seconds=1),
            available_from=datetime.time(0, 0), available_until=datetime.time(0, 0),
        )
        self.assertEqual(self.client.get(f'/launch/{raw_revoked}').status_code, 404)
        self.assertEqual(self.client.post(f'/api/launch/{raw_expired}/start').status_code, 404)

    def test_authenticated_create_returns_separate_one_time_shortcut_uris(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/launch-tokens/',
            {'name': 'Study automation', 'subject': 'math'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['available_from'], '06:00:00')
        self.assertEqual(payload['available_until'], '22:00:00')
        self.assertTrue(payload['shortcut_start_url'].startswith('http://testserver/api/launch/'))
        self.assertTrue(payload['disturbance_url'].startswith('http://testserver/api/disturbance/'))
        self.assertEqual(payload['shortcuts_create_url'], 'shortcuts://create-shortcut')
        self.assertNotEqual(payload['raw_token'], payload['raw_disturbance_token'])

        token = LaunchToken.objects.get(user=self.user)
        self.assertEqual(token.token_digest, LaunchToken.digest(payload['raw_token']))
        self.assertEqual(
            token.disturbance_token_digest,
            LaunchToken.digest(payload['raw_disturbance_token']),
        )
        database_values = json.dumps({
            'start': token.token_digest,
            'disturbance': token.disturbance_token_digest,
        })
        self.assertNotIn(payload['raw_token'], database_values)
        self.assertNotIn(payload['raw_disturbance_token'], database_values)

        listing = self.client.get('/api/launch-tokens/').json()[0]
        self.assertTrue(listing['has_disturbance_uri'])
        self.assertNotIn('raw_token', listing)
        self.assertNotIn('shortcut_start_url', listing)
        self.assertNotIn('disturbance_url', listing)

    def test_pause_resume_and_daily_window_are_non_destructive_no_ops(self):
        token, raw_start, raw_disturbance = self._issue_pair()
        self.client.force_login(self.user)
        paused = self.client.post(f'/api/launch-tokens/{token.pk}/pause/')
        self.assertEqual(paused.status_code, 200)
        self.assertTrue(paused.json()['is_paused'])
        self.client.logout()

        start_paused = self.client.post(f'/api/launch/{raw_start}/start')
        disturbance_paused = self.client.post(
            f'/api/disturbance/{raw_disturbance}/record',
        )
        self.assertEqual(start_paused.json()['status'], 'paused')
        self.assertEqual(disturbance_paused.json()['status'], 'paused')
        self.assertFalse(TimeLog.objects.filter(user=self.user, status='running').exists())

        self.client.force_login(self.user)
        resumed = self.client.post(f'/api/launch-tokens/{token.pk}/resume/')
        self.assertFalse(resumed.json()['is_paused'])
        self.client.logout()
        self.assertEqual(self.client.post(f'/api/launch/{raw_start}/start').json()['status'], 'started')

        token.available_from = datetime.time(6, 0)
        token.available_until = datetime.time(22, 0)
        token.save(update_fields=('available_from', 'available_until'))
        fixed_now = timezone.make_aware(datetime.datetime(2026, 8, 12, 5, 59))
        with mock.patch('tracker.models.timezone.now', return_value=fixed_now):
            outside = self.client.post(f'/api/launch/{raw_start}/start')
        self.assertEqual(outside.status_code, 200)
        self.assertEqual(outside.json()['status'], 'outside_schedule')
        self.assertFalse(outside.json()['started'])

    def test_schedule_supports_boundaries_overnight_and_equal_all_day(self):
        token, _, _ = self._issue_pair(
            available_from=datetime.time(6, 0),
            available_until=datetime.time(22, 0),
        )
        local = timezone.get_current_timezone()
        at = lambda hour, minute=0: timezone.make_aware(
            datetime.datetime(2026, 8, 12, hour, minute), local,
        )
        self.assertTrue(token.schedule_allows(at(6)))
        self.assertTrue(token.schedule_allows(at(21, 59)))
        self.assertFalse(token.schedule_allows(at(22)))
        token.available_from = datetime.time(22, 0)
        token.available_until = datetime.time(6, 0)
        self.assertTrue(token.schedule_allows(at(23)))
        self.assertTrue(token.schedule_allows(at(5, 59)))
        self.assertFalse(token.schedule_allows(at(12)))
        token.available_until = datetime.time(22, 0)
        self.assertTrue(token.schedule_allows(at(12)))

    def test_disturbance_uri_counts_only_a_current_session_and_is_separately_scoped(self):
        token, raw_start, raw_disturbance = self._issue_pair(max_uses=1)
        self.assertEqual(self.client.post(f'/api/launch/{raw_start}/start').json()['status'], 'started')
        self.assertEqual(self.client.post(f'/api/launch/{raw_start}/start').status_code, 404)

        wrong_scope = self.client.post(f'/api/disturbance/{raw_start}/record')
        self.assertEqual(wrong_scope.status_code, 404)
        event = self.client.post(f'/api/disturbance/{raw_disturbance}/record')
        self.assertEqual(event.status_code, 200)
        self.assertEqual(event.json()['status'], 'recorded')
        self.assertEqual(event.json()['disturbance_count'], 1)
        session = TimeLog.objects.get(user=self.user, status='running')
        self.assertEqual(session.disturbance_count, 1)
        self.assertIsNotNone(session.last_disturbance_at)
        self.assertNotIn('session_id', event.json())
        method_not_allowed = self.client.get(f'/api/disturbance/{raw_disturbance}/record')
        self.assertEqual(method_not_allowed.status_code, 405)
        self.assertIn('no-store', method_not_allowed['Cache-Control'])
        self.assertIn('no-store', event['Cache-Control'])

        invalid = self.client.post('/api/disturbance/not-a-valid-secret/record')
        self.assertEqual(invalid.status_code, 404)
        self.assertIn('no-store', invalid['Cache-Control'])

        session.delete()
        no_session = self.client.post(f'/api/disturbance/{raw_disturbance}/record')
        self.assertEqual(no_session.json(), {
            'status': 'no_active_session',
            'recorded': False,
            'subject': token.category,
        })

    def test_disturbance_request_discards_a_stale_running_session(self):
        _, _, raw_disturbance = self._issue_pair(category='math')
        stale = TimeLog.objects.create(
            user=self.user,
            category='math',
            status='running',
            start_time=timezone.now() - datetime.timedelta(hours=12, seconds=1),
        )
        response = self.client.post(f'/api/disturbance/{raw_disturbance}/record')
        self.assertEqual(response.json()['status'], 'stale_session_discarded')
        self.assertFalse(TimeLog.objects.filter(pk=stale.pk).exists())

    def test_owner_can_configure_and_rotate_each_secret_independently(self):
        token, raw_start, raw_disturbance = self._issue_pair()
        other = get_user_model().objects.create_user('other-launch-owner', password='password')
        self.client.force_login(other)
        self.assertEqual(
            self.client.put(
                f'/api/launch-tokens/{token.pk}/configure/',
                {'name': 'No access', 'available_from': '07:00', 'available_until': '21:00'},
                content_type='application/json',
            ).status_code,
            404,
        )

        self.client.force_login(self.user)
        configured = self.client.put(
            f'/api/launch-tokens/{token.pk}/configure/',
            {
                'name': 'Updated phone', 'available_from': '07:00',
                'available_until': '21:00', 'max_uses': None,
                'expires_at': None, 'source_label': 'Action Button', 'notes': '',
            },
            content_type='application/json',
        )
        self.assertEqual(configured.status_code, 200)
        self.assertEqual(configured.json()['available_from'], '07:00:00')
        rotated_disturbance = self.client.post(
            f'/api/launch-tokens/{token.pk}/regenerate-disturbance/',
        ).json()
        self.assertNotIn('shortcut_start_url', rotated_disturbance)
        self.assertIn('disturbance_url', rotated_disturbance)
        self.client.logout()
        self.assertEqual(self.client.post(f'/api/disturbance/{raw_disturbance}/record').status_code, 404)
        self.assertNotEqual(
            LaunchToken.objects.get(pk=token.pk).token_digest,
            LaunchToken.digest(rotated_disturbance['raw_disturbance_token']),
        )
        self.assertEqual(
            LaunchToken.objects.get(pk=token.pk).token_digest,
            LaunchToken.digest(raw_start),
        )
