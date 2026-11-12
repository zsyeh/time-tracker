"""Synthetic account-isolation, CSRF, CAS and additive-migration regressions."""
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models.query import QuerySet
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import path
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.test import APIClient

from .models import TimeLog, UserPreferences
from .user_preferences import (
    MAX_PAYLOAD_BYTES, SIDEBAR_IDS, PreferencesConflict, UserPreferencesView,
    patch_preferences, preference_defaults, preferences_snapshot,
)


@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({'token': get_token(request)})


# Test the actual API view without claiming ownership of production URL files.
urlpatterns = [path('api/user-preferences/', UserPreferencesView.as_view()),
               path('test-csrf/', csrf_token)]
TEST_SETTINGS = dict(
    ROOT_URLCONF=__name__, SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver'],
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
URL = '/api/user-preferences/'


def payload(changes, bases=None):
    return {'schema_version': 1, 'changes': changes,
            'base_revisions': bases if bases is not None else dict.fromkeys(changes, 0)}


@override_settings(**TEST_SETTINGS)
class UserPreferencesAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('preferences-owner', password='synthetic')
        cls.other = get_user_model().objects.create_user('preferences-other', password='synthetic')

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)

    def change(self, changes, bases=None):
        return self.client.patch(URL, payload(changes, bases), format='json')

    def test_get_defaults_is_read_only_and_has_private_cache_headers(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, preferences_snapshot(self.user))
        self.assertEqual(response.data['values']['font'], 'small')
        self.assertEqual(response.data['values']['language'], 'en')
        self.assertEqual(response.data['revision'], 0)
        self.assertTrue(all(value == 0 for value in response.data['field_revisions'].values()))
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn('Cookie', response['Vary'])
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_get_ignores_device_cookie_and_default_mutation(self):
        self.client.cookies['learning_ui_visual_v1'] = json.dumps({'appearance': 'dark'})
        first = preference_defaults()
        first['sidebar.drill']['order'].clear()
        first['filters.ei'].append({'secret': 'not shared'})
        second = self.client.get(URL).data['values']
        self.assertEqual(second['appearance'], 'system')
        self.assertEqual(second['sidebar.drill']['order'], list(SIDEBAR_IDS['drill']))
        self.assertEqual(second['filters.ei'], [])

    def test_anonymous_and_inactive_accounts_cannot_read_or_write(self):
        self.client.logout()
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.change({'accent': 'green'}).status_code, 403)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_patch_requires_real_session_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        body = payload({'appearance': 'dark'})
        self.assertEqual(client.patch(URL, body, format='json').status_code, 403)
        self.assertEqual(UserPreferences.objects.count(), 0)
        token = client.get('/test-csrf/').json()['token']
        response = client.patch(URL, body, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['values']['appearance'], 'dark')

    def test_two_accounts_are_isolated_and_user_selector_is_rejected(self):
        self.assertEqual(self.change({'accent': 'purple'}).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(URL).data['values']['accent'], 'blue')
        self.assertEqual(self.change({'accent': 'orange'}).status_code, 200)
        bad = payload({'appearance': 'dark'})
        bad['user_id'] = self.user.pk
        self.assertEqual(self.client.patch(URL, bad, format='json').status_code, 400)
        self.assertEqual(preferences_snapshot(self.user)['values']['accent'], 'purple')
        self.assertEqual(preferences_snapshot(self.other)['values']['accent'], 'orange')

    def test_real_session_account_header_prevents_cross_tab_write_and_read(self):
        patch_preferences(self.user, payload({'accent': 'purple'}))
        patch_preferences(self.other, payload({'accent': 'orange'}))
        before = [preferences_snapshot(user) for user in (self.user, self.other)]
        # A live page is bound to A, but a second tab has changed the session to B.
        # force_authenticate would bypass AuthenticationMiddleware and miss this bug.
        client = Client()
        client.force_login(self.other)
        for method in ('get', 'patch'):
            with self.subTest(method=method):
                kwargs = {'HTTP_X_LEARNING_USER_ID': str(self.user.pk)}
                if method == 'patch':
                    kwargs.update(data=json.dumps(payload({'appearance': 'dark'})),
                                  content_type='application/json')
                response = getattr(client, method)(URL, **kwargs)
                self.assertEqual(response.status_code, 409)
                self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual([preferences_snapshot(user) for user in (self.user, self.other)], before)
        response = client.patch(URL, json.dumps(payload({'appearance': 'dark'})),
                                content_type='application/json', HTTP_X_LEARNING_USER_ID=str(self.other.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(preferences_snapshot(self.user), before[0])
        self.assertEqual(preferences_snapshot(self.other)['values']['appearance'], 'dark')

    def test_independent_fields_merge_despite_stale_global_snapshot(self):
        first = self.change({'appearance': 'dark'}).data
        second = self.change({'accent': 'green'}).data
        self.assertEqual(first['revision'], 1)
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['values']['appearance'], 'dark')
        self.assertEqual(second['values']['accent'], 'green')
        self.assertEqual(second['field_revisions']['appearance'], 1)
        self.assertEqual(second['field_revisions']['accent'], 2)

    def test_same_field_conflict_is_atomic_and_preserves_json_types(self):
        self.change({'appearance': 'dark'})
        response = self.change({'appearance': 'light', 'practice.review_auto_next': True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'PREFERENCES_CONFLICT')
        self.assertEqual(response.data['conflicts'], ['appearance'])
        current = response.data['current']
        self.assertIs(type(current['revision']), int)
        self.assertIs(current['values']['practice.review_auto_next'], False)
        self.assertEqual(current['values']['appearance'], 'dark')
        self.assertEqual(UserPreferences.objects.get(user=self.user).revision, 1)
        retry = self.change({'appearance': 'light'}, {'appearance': 1})
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data['revision'], 2)

    def test_stale_complete_document_cannot_clobber_newer_fields(self):
        initial = self.client.get(URL).data
        self.change({'font': 'large'})
        initial['values']['appearance'] = 'light'
        response = self.change(initial['values'], initial['field_revisions'])
        self.assertEqual(response.status_code, 409)
        self.assertIn('font', response.data['conflicts'])
        current = preferences_snapshot(self.user)
        self.assertEqual(current['values']['font'], 'large')
        self.assertEqual(current['values']['appearance'], 'system')

    def test_noop_does_not_create_or_bump_revision(self):
        self.assertEqual(self.change({'appearance': 'system'}).data['revision'], 0)
        self.assertEqual(UserPreferences.objects.count(), 0)
        self.change({'appearance': 'dark'})
        self.assertEqual(self.change({'appearance': 'dark'}, {'appearance': 1}).data['revision'], 1)
        self.assertEqual(self.change({'appearance': 'dark'}).status_code, 409)

    def test_progress_defaults_and_additive_upgrade_do_not_rewrite_existing_preferences(self):
        legacy_values = preference_defaults()
        legacy_values.pop('progress.drill'); legacy_values.pop('progress.ei')
        legacy_values['accent'] = 'green'
        row = UserPreferences.objects.create(user=self.user, values=legacy_values,
                                             field_revisions={'accent': 3}, revision=3)
        value = self.client.get(URL).data
        self.assertEqual(value['schema_version'], 1)
        self.assertEqual(value['values']['progress.drill'], {'target': 24, 'deadline': '2026-11-21'})
        self.assertEqual(value['values']['progress.ei'], {'target': 11, 'deadline': '2026-11-21'})
        self.assertEqual(value['field_revisions']['progress.drill'], 0)
        self.assertEqual(value['field_revisions']['progress.ei'], 0)
        row.refresh_from_db()
        self.assertEqual(row.values, legacy_values)
        self.assertEqual(row.revision, 3)
        goal = {'target': 30, 'deadline': '2027-01-01'}
        self.assertEqual(self.change({'progress.drill': goal}).status_code, 200)
        # An old client's allowlisted patch must not overwrite newly added fields.
        self.assertEqual(self.change({'accent': 'purple'}, {'accent': 3}).status_code, 200)
        self.assertEqual(self.client.get(URL).data['values']['progress.drill'], goal)

    def test_progress_two_devices_conflict_per_workspace_and_keep_accounts_isolated(self):
        second = APIClient(); second.force_login(self.user)
        initial = second.get(URL).data
        drill_goal = {'target': 40, 'deadline': '2028-02-29'}
        first = self.change({'progress.drill': drill_goal})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.get(URL).data['values']['progress.drill'], drill_goal)
        ei_goal = {'target': 18, 'deadline': '2027-06-30'}
        independent = second.patch(URL, payload({'progress.ei': ei_goal},
            {'progress.ei': initial['field_revisions']['progress.ei']}), format='json')
        self.assertEqual(independent.status_code, 200)
        self.assertEqual(independent.data['values']['progress.drill'], drill_goal)
        before = preferences_snapshot(self.user)
        stale_goal = {'target': 20, 'deadline': '2026-12-31'}
        conflict = second.patch(URL, payload({'progress.drill': stale_goal, 'accent': 'orange'}), format='json')
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data['conflicts'], ['progress.drill'])
        self.assertEqual(conflict.data['current']['values']['progress.drill'], drill_goal)
        self.assertEqual(preferences_snapshot(self.user), before)
        recovered = second.patch(URL, payload({'progress.drill': stale_goal},
            {'progress.drill': conflict.data['current']['field_revisions']['progress.drill']}), format='json')
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(self.client.get(URL).data['values']['progress.drill'], stale_goal)
        second.force_login(self.other)
        self.assertEqual(second.get(URL).data['values']['progress.drill']['target'], 24)
        self.assertEqual(second.get(URL).data['values']['progress.ei']['target'], 11)
        self.assertEqual(second.patch(URL, payload({'progress.drill': drill_goal}), format='json').status_code, 200)
        self.assertEqual(preferences_snapshot(self.user)['values']['progress.drill'], stale_goal)
        self.assertEqual(preferences_snapshot(self.user)['values']['progress.ei'], ei_goal)

    def test_progress_rejects_invalid_targets_and_calendar_dates_atomically(self):
        goal = {'target': 24, 'deadline': '2026-11-21'}
        invalid = [None, [], {}, {'target': 24}, {'deadline': '2026-11-21'},
                   dict(goal, total=963), dict(goal, formula='override')]
        invalid.extend(dict(goal, target=value) for value in [0, -1, 501, True, False, 1.5, '24', None])
        invalid.extend(dict(goal, deadline=value) for value in [None, 20261121, '', '2026-2-01',
            '2026-02-29', '1900-02-29', '2026-04-31', '2026-00-01', '2026-13-01',
            '2026-01-00', '0000-01-01', '10000-01-01', '2026-11-21T00:00:00Z',
            '2026-11-21\n', ' 2026-11-21', '２０２６-１１-２１'])
        for workspace in ('drill', 'ei'):
            for value in invalid:
                with self.subTest(workspace=workspace, value=value):
                    response = self.change({'progress.' + workspace: value, 'accent': 'green'})
                    self.assertEqual(response.status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_progress_accepts_target_boundaries_and_real_leap_dates(self):
        revision = 0
        for target, deadline in [(1, '0001-01-01'), (500, '9999-12-31'), (24, '2000-02-29'),
                                 (11, '2024-02-29'), (24, '2026-02-28')]:
            with self.subTest(target=target, deadline=deadline):
                goal = {'target': target, 'deadline': deadline}
                response = self.change({'progress.drill': goal}, {'progress.drill': revision})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['values']['progress.drill'], goal)
                revision = response.data['field_revisions']['progress.drill']

    def test_sidebar_manifest_normalization_and_workspace_atomicity(self):
        config = {'order': ['progress', 'selected-heatmap'],
                  'hidden': list(SIDEBAR_IDS['drill']), 'collapsed_groups': ['tools']}
        response = self.change({'sidebar.drill': config})
        self.assertEqual(response.status_code, 200)
        sidebar = response.data['values']['sidebar.drill']
        self.assertEqual(sidebar['order'][:2], ['progress', 'selected-heatmap'])
        self.assertEqual(set(sidebar['order']), set(SIDEBAR_IDS['drill']))
        self.assertEqual(len(sidebar['order']), len(SIDEBAR_IDS['drill']))
        self.assertEqual(sidebar['hidden'], list(SIDEBAR_IDS['drill']))
        self.assertEqual(self.change({'sidebar.drill': preference_defaults()['sidebar.drill']}).status_code, 409)
        self.assertEqual(self.change({'sidebar.ei': {'order': ['progress'], 'hidden': [], 'collapsed_groups': []}}).status_code, 200)

    def test_sidebar_rejects_unknown_duplicate_and_transient_fields(self):
        original = preference_defaults()['sidebar.drill']
        invalid = [dict(original, order=['core-heatmap']), dict(original, order=['progress', 'progress']),
                   dict(original, hidden=['settings']), dict(original, collapsed_groups=['drawer']),
                   dict(original, collapsed=True), dict(original, scroll=300)]
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(self.change({'sidebar.drill': value}).status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_presets_are_explicit_bounded_and_workspace_separate(self):
        preset = {'id': 'preset-1', 'name': '  导数  ', 'query': {
            'q': '  隐函数  ', 'document': '12', 'status': 'unattempted',
            'collection': 'selected', 'marker': 'rusty', 'sort': 'relevance',
        }}
        response = self.change({'filters.drill': [preset]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['values']['filters.drill'][0]['name'], '导数')
        self.assertEqual(response.data['values']['filters.drill'][0]['query']['q'], '隐函数')
        self.assertEqual(response.data['values']['filters.ei'], [])
        self.assertEqual(self.change({'filters.ei': [preset]}).status_code, 400)

    def test_saved_presets_round_trip_current_collection_and_course_scopes(self):
        queries = [
            {'q': '负反馈', 'course': 'analog', 'material': 'ready', 'tier': 'core',
             'kind': 'analysis', 'combined': '1', 'state': 'review', 'scope': 'past_exam',
             'bucket': 'core:chapter_2', 'collection': 'core_selected', 'sort': 'source'},
            {'q': 'Fourier', 'course': 'signal', 'collection': 'signal_selected',
             'material': 'ready', 'scope': 'mock_exam', 'type_group': 'large'},
        ]
        presets = [{'id': 'scope-' + str(i), 'name': 'Scope ' + str(i), 'query': query}
                   for i, query in enumerate(queries)]
        response = self.change({'filters.ei': presets})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['values']['filters.ei'], presets)
        # A new device reload must receive all scope keys unchanged for replay.
        fresh = Client(); fresh.force_login(self.user)
        self.assertEqual(fresh.get(URL).json()['values']['filters.ei'], presets)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(URL).data['values']['filters.ei'], [])

    def test_saved_preset_scope_rejects_invalid_values_and_transient_parameters(self):
        cases = [('course', 'math'), ('material', 'all'), ('tier', 'invented'),
                 ('kind', 'invalid'), ('combined', '0'), ('state', 'all'), ('scope', 'private'),
                 ('bucket', '../private'), ('bucket', 'x' * 121), ('offset', '20'),
                 ('index_version', 'old'), ('page', '2')]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                preset = {'id': 'invalid', 'name': 'Scope', 'query': {key: value}}
                self.assertEqual(self.change({'filters.ei': [preset]}).status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_presets_reject_transients_invalid_queries_and_count_overflow(self):
        preset = {'id': 'preset-1', 'name': 'Filter', 'query': {}}
        invalid = [[dict(preset, id='bad/id')], [dict(preset, name='')], [preset, preset],
                   [dict(preset, id=str(n)) for n in range(11)]]
        for key, value in [('page', '2'), ('index_version', '1:old:1'), ('user', '4'),
                           ('scroll', '10'), ('from', 'insight'), ('document', '-1'),
                           ('status', 'invented'), ('q', 'x' * 121), ('q', '\x00'),
                           ('favorite', True), ('topic', ['12']), ('collection', 'core_selected')]:
            invalid.append([dict(preset, query={key: value})])
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(self.change({'filters.drill': value}).status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_unknown_keys_types_and_versions_are_rejected(self):
        invalid_changes = [{'runtime': {}}, {'SECRET_KEY': 'no'}, {'window': {}}, {'scroll': 20},
                           {'font': '105%'}, {'appearance': 'auto'}, {'accent': '#fff'},
                           {'language': 'fr'}, {'practice.review_auto_next': 'false'},
                           {'practice.mastered_auto_next': 1}, {'appearance': None},
                           {'practice.drill.copy_mode': 'javascript:alert(1)'}]
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                self.assertEqual(self.change(changes).status_code, 400)
        for body in [[], {}, payload({}), dict(payload({'accent': 'green'}), schema_version=True),
                     dict(payload({'accent': 'green'}), schema_version=2),
                     payload({'accent': 'green'}, {}), payload({'accent': 'green'}, {'accent': False}),
                     payload({'accent': 'green'}, {'accent': -1}),
                     payload({'accent': 'green'}, {'accent': 2 ** 53})]:
            with self.subTest(body=body):
                self.assertEqual(self.client.patch(URL, body, format='json').status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_request_byte_bound_and_malformed_json(self):
        large = json.dumps(payload({'appearance': 'dark'})) + ' ' * MAX_PAYLOAD_BYTES
        self.assertEqual(self.client.patch(URL, large, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.patch(URL, '{"changes":', content_type='application/json').status_code, 400)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_stored_future_keys_are_not_exposed_or_destroyed(self):
        row = UserPreferences.objects.create(user=self.user, values={'future.safe': 'keep'},
                                              field_revisions={'future.safe': 1}, revision=1)
        response = self.change({'accent': 'green'})
        self.assertNotIn('future.safe', response.data['values'])
        row.refresh_from_db()
        self.assertEqual(row.values['future.safe'], 'keep')
        self.assertEqual(row.field_revisions['future.safe'], 1)

    def test_existing_shared_and_workspace_practice_semantics(self):
        response = self.change({'practice.next_mode': 'review', 'practice.review_auto_next': True,
                                'practice.mastered_auto_next': False, 'practice.ei.copy_mode': 'link'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['values']['practice.next_mode'], 'review')
        self.assertIs(response.data['values']['practice.review_auto_next'], True)
        self.assertIs(response.data['values']['practice.mastered_auto_next'], False)
        self.assertEqual(response.data['values']['practice.ei.copy_mode'], 'link')
        self.assertEqual(response.data['values']['practice.drill.copy_mode'], 'off')

    def test_actual_global_cas_race_remerges_unrelated_field(self):
        UserPreferences.objects.create(user=self.user)
        original = QuerySet.update
        injected = False

        def update(queryset, **kwargs):
            nonlocal injected
            if queryset.model is UserPreferences and not injected:
                injected = True
                patch_preferences(self.user, payload({'accent': 'green'}))
            return original(queryset, **kwargs)

        with patch.object(QuerySet, 'update', update):
            result = patch_preferences(self.user, payload({'appearance': 'dark'}))
        self.assertEqual(result['values']['appearance'], 'dark')
        self.assertEqual(result['values']['accent'], 'green')
        self.assertEqual(result['revision'], 2)

    def test_actual_global_cas_race_rejects_changed_field(self):
        UserPreferences.objects.create(user=self.user)
        original = QuerySet.update
        injected = False

        def update(queryset, **kwargs):
            nonlocal injected
            if queryset.model is UserPreferences and not injected:
                injected = True
                patch_preferences(self.user, payload({'appearance': 'light'}))
            return original(queryset, **kwargs)

        with patch.object(QuerySet, 'update', update), self.assertRaises(PreferencesConflict) as caught:
            patch_preferences(self.user, payload({'appearance': 'dark'}))
        self.assertEqual(caught.exception.payload['current']['values']['appearance'], 'light')
        self.assertEqual(caught.exception.payload['conflicts'], ['appearance'])


@override_settings(
    ROOT_URLCONF='time_server.urls', SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'drill.ehzsy.site', 'ei.ehzsy.site', 'timer.ehzsy.site', 'ehzsy.site'],
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class UserPreferencesBootstrapTests(TestCase):
    shell = ('<!doctype html><html><head><script src="/static/appearance-bootstrap.js"></script>'
             '<link rel="stylesheet" href="/static/app.css"></head><body>Fixture</body></html>')

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('bootstrap-owner', password='synthetic',
                                                       is_staff=True, is_superuser=True)
        cls.other = get_user_model().objects.create_user('bootstrap-other', password='synthetic')
        patch_preferences(cls.user, payload({'appearance': 'dark', 'accent': 'purple', 'font': 'large'}))
        patch_preferences(cls.other, payload({'appearance': 'light', 'accent': 'green', 'font': 'compact'}))

    def bootstrap(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        matches = re.findall(r'<script id="learning-user-preferences" type="application/json">(.*?)</script>',
                             html, re.DOTALL)
        self.assertEqual(len(matches), 1)
        return json.loads(matches[0]), html

    def test_account_html_is_per_request_and_precedes_synchronous_visual_bootstrap(self):
        with patch('tracker.web_views._frontend_html', return_value=self.shell), \
                patch('drill.web_views._drill_html', return_value=self.shell):
            for user in (self.user, self.other, self.user):
                self.client.force_login(user)
                self.client.cookies['learning_ui_visual_v1'] = '{"appearance":"light","accent":"yellow"}'
                for host, path in [('testserver', '/settings'), ('drill.ehzsy.site', '/progress'),
                                   ('ei.ehzsy.site', '/progress')]:
                    with self.subTest(user=user.pk, host=host):
                        response = self.client.get(path, HTTP_HOST=host)
                        value, html = self.bootstrap(response)
                        self.assertEqual(value, {'user_id': str(user.pk), 'snapshot': preferences_snapshot(user)})
                        self.assertLess(html.index('learning-user-preferences'), html.index('appearance-bootstrap.js'))
                        self.assertLess(html.index('learning-user-preferences'), html.index('app.css'))
                        self.assertIn('private', response['Cache-Control'])
                        self.assertIn('no-store', response['Cache-Control'])

    def test_json_bootstrap_escapes_script_end_and_round_trips_user_preset_text(self):
        name = '</script><script>alert("synthetic")</script>&'
        patch_preferences(self.user, payload({'filters.drill': [{'id': 'safe', 'name': name, 'query': {'q': '<&>'}}]}))
        self.client.force_login(self.user)
        with patch('tracker.web_views._frontend_html', return_value=self.shell):
            value, html = self.bootstrap(self.client.get('/settings'))
        self.assertEqual(value['snapshot']['values']['filters.drill'][0]['name'], name)
        self.assertNotIn(name, html)
        self.assertIn(r'\u003C/script\u003E', html)
        self.assertIn(r'\u0026', html)

    def test_public_share_and_public_template_never_embed_authenticated_preferences(self):
        self.client.force_login(self.user)
        self.client.cookies['learning_ui_visual_v1'] = '{"version":1,"appearance":"dark","accent":"purple"}'
        with patch('tracker.web_views._frontend_html', return_value=self.shell):
            share, html = self.bootstrap(self.client.get('/share/synthetic-only'))
        self.assertEqual(share, {'user_id': None, 'snapshot': None})
        public, html = self.bootstrap(self.client.get('/contact/'))
        self.assertEqual(public, {'user_id': None, 'snapshot': None})
        self.assertNotIn('bootstrap-owner', html)
        self.assertLess(html.index('learning-user-preferences'), html.index('appearance-bootstrap'))

    def test_auth_and_admin_templates_emit_explicit_identity_before_visual_script(self):
        self.client.cookies['learning_ui_visual_v1'] = '{"version":1,"appearance":"dark","accent":"purple"}'
        value, html = self.bootstrap(self.client.get('/accounts/login/'))
        self.assertEqual(value, {'user_id': None, 'snapshot': None})
        self.assertLess(html.index('learning-user-preferences'), html.index('appearance-bootstrap'))
        self.client.force_login(self.user)
        value, html = self.bootstrap(self.client.get('/admin/'))
        self.assertEqual(value['user_id'], str(self.user.pk))
        self.assertEqual(value['snapshot']['values']['appearance'], 'dark')
        self.assertLess(html.index('learning-user-preferences'), html.index('appearance-bootstrap'))

    def test_auth_session_refresh_is_no_store_and_ignores_old_page_affinity(self):
        self.client.force_login(self.other)
        response = self.client.get('/api/auth/session/', HTTP_X_LEARNING_USER_ID=str(self.user.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['id'], self.other.pk)
        self.assertEqual(response.json()['preferences'], preferences_snapshot(self.other))
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('Cookie', response['Vary'])

    def test_logout_clears_visual_cookie_for_local_subdomain_and_apex_then_anonymous_bootstrap(self):
        for host, domain in [('testserver', ''), ('timer.ehzsy.site', '.ehzsy.site'), ('ehzsy.site', '.ehzsy.site')]:
            with self.subTest(host=host):
                client = Client(); client.force_login(self.user)
                for name in ('learning_ui_visual_v1', 'learning_os_color_scheme', 'learning_os_ui_language'):
                    client.cookies[name] = 'synthetic-old-value'
                response = client.post('/api/auth/logout/', HTTP_HOST=host)
                self.assertEqual(response.status_code, 204)
                for name in ('learning_ui_visual_v1', 'learning_os_color_scheme', 'learning_os_ui_language'):
                    self.assertEqual(response.cookies[name]['max-age'], 0)
                    self.assertEqual(response.cookies[name]['domain'], domain)
                session = client.get('/api/auth/session/', HTTP_HOST=host)
                # This endpoint intentionally retains the existing authenticated
                # API permission contract; the anonymous HTML emits null instead.
                self.assertEqual(session.status_code, 403)
                self.assertNotIn('preferences', session.json())
                value, _html = self.bootstrap(client.get('/accounts/login/', HTTP_HOST=host))
                self.assertEqual(value, {'user_id': None, 'snapshot': None})


@override_settings(**TEST_SETTINGS)
class PreferencesConcurrentTests(TransactionTestCase):
    def test_two_postgres_connections_merge_independent_and_conflict_same_field(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Real concurrent connections use the production PostgreSQL backend; CAS race tests also run on SQLite.')
        user = get_user_model().objects.create_user('concurrent-preferences')
        UserPreferences.objects.create(user=user)
        original = QuerySet.update

        def race(changes):
            barrier = threading.Barrier(2)
            local = threading.local()

            def update(queryset, **kwargs):
                if queryset.model is UserPreferences and not getattr(local, 'arrived', False):
                    local.arrived = True
                    barrier.wait(timeout=10)
                return original(queryset, **kwargs)

            def write(change):
                close_old_connections()
                try:
                    return patch_preferences(user, payload(change))
                except PreferencesConflict as exc:
                    return exc.payload
                finally:
                    close_old_connections()

            with patch.object(QuerySet, 'update', update), ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(write, changes))

        results = race([{'appearance': 'dark'}, {'accent': 'green'}])
        self.assertTrue(all('code' not in result for result in results))
        current = preferences_snapshot(user)
        self.assertEqual(current['values']['appearance'], 'dark')
        self.assertEqual(current['values']['accent'], 'green')
        UserPreferences.objects.filter(user=user).delete()
        UserPreferences.objects.create(user=user)
        results = race([{'appearance': 'dark'}, {'appearance': 'light'}])
        self.assertEqual(sum(result.get('code') == 'PREFERENCES_CONFLICT' for result in results), 1)
        self.assertEqual(preferences_snapshot(user)['revision'], 1)


@override_settings(**TEST_SETTINGS)
class UserPreferencesMigrationTests(TransactionTestCase):
    def test_additive_migration_and_reverse_preserve_learning_records(self):
        from drill.models import Question, QuestionAttempt, QuestionDocument, QuestionUserState
        user = get_user_model().objects.create_user('migration-preferences')
        log = TimeLog.objects.create(user=user, category='math', start_time=timezone.now(),
                                     title='Synthetic history retained')
        document = QuestionDocument.objects.create(source_id=987654, workspace='drill', filename='synthetic.pdf',
                                                   title='Migration fixture', sha256='pref-migration', page_count=1)
        question = Question.objects.create(document=document, question_order=1, content_mode='text',
                                             fingerprint='preferences-migration', prompt_text='Synthetic problem')
        attempt = QuestionAttempt.objects.create(user=user, question=question, result='review', time_spent_seconds=42)
        note = QuestionUserState.objects.create(user=user, question=question, note='Synthetic saved note')
        preserved = (log.pk, str(log.uuid), attempt.pk, str(question.uuid), note.note)
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([('tracker', '0021_alter_knowledgepoint_category_and_more')])
            self.assertNotIn('tracker_userpreferences', connection.introspection.table_names())
            executor = MigrationExecutor(connection)
            executor.migrate([('tracker', '0022_userpreferences')])
            self.assertEqual(UserPreferences.objects.count(), 0)
            patch_preferences(user, payload({'appearance': 'dark'}))
            self.assertEqual(UserPreferences.objects.count(), 1)
            MigrationExecutor(connection).migrate([('tracker', '0021_alter_knowledgepoint_category_and_more')])
            self.assertNotIn('tracker_userpreferences', connection.introspection.table_names())
            log.refresh_from_db(); question.refresh_from_db(); attempt.refresh_from_db(); note.refresh_from_db()
            self.assertEqual((log.pk, str(log.uuid), attempt.pk, str(question.uuid), note.note), preserved)
            self.assertEqual(log.title, 'Synthetic history retained')
            self.assertEqual(attempt.result, 'review')
            self.assertEqual(attempt.time_spent_seconds, 42)
        finally:
            MigrationExecutor(connection).migrate([('tracker', '0022_userpreferences')])
