import datetime
import json
from unittest import mock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .views import _execute_lazy_garbage_collection, token_required
from .models import DailyStudyStat, TimeLog
from .schedule import get_summer_schedule


SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
AUTH_HEADERS = {'HTTP_AUTHORIZATION': 'test-token'}


def shanghai_datetime(year, month, day, hour, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=SHANGHAI_TZ)


@override_settings(TRACKER_API_TOKEN='test-token')
class ApiActionTests(TestCase):
    def post_action(self, payload, token='test-token'):
        return self.client.post(
            reverse('api_action'),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=token,
        )

    def test_rejects_missing_token(self):
        response = self.post_action({'action': 'start', 'category': 'math'}, token='')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(TimeLog.objects.count(), 0)

    def test_rejects_invalid_category(self):
        response = self.post_action({'action': 'start', 'category': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(TimeLog.objects.count(), 0)

    def test_start_creates_active_log(self):
        response = self.post_action({'action': 'start', 'category': 'math'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TimeLog.objects.filter(end_time__isnull=True).count(), 1)
        self.assertEqual(DailyStudyStat.objects.count(), 0)

    def test_start_accepts_training_category(self):
        response = self.post_action({'action': 'start', 'category': 'training'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TimeLog.objects.filter(category='training', end_time__isnull=True).exists())

    def test_stop_deletes_too_short_log(self):
        TimeLog.objects.create(category='math')

        response = self.post_action({'action': 'stop', 'note': 'short'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TimeLog.objects.count(), 0)
        self.assertEqual(DailyStudyStat.objects.count(), 0)

    def test_stop_closes_valid_log(self):
        now = shanghai_datetime(2026, 7, 18, 10, 0)
        start = now - datetime.timedelta(minutes=30)
        TimeLog.objects.create(
            category='math',
            start_time=start,
        )

        with mock.patch('tracker.views._get_safe_now', return_value=now):
            response = self.post_action({'action': 'stop', 'note': 'done'})

        self.assertEqual(response.status_code, 200)
        log = TimeLog.objects.get()
        self.assertEqual(log.end_time, now)
        self.assertEqual(log.note, 'done')
        stat = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 18))
        self.assertEqual(stat.study_count, 1)
        self.assertEqual(stat.first_start_time, start)
        self.assertEqual(stat.total_minutes, 30)

    def test_stop_deletes_log_just_before_25_minute_boundary(self):
        now = shanghai_datetime(2026, 7, 18, 10, 0)
        TimeLog.objects.create(
            category='math',
            start_time=now - datetime.timedelta(minutes=24, seconds=59),
        )

        with mock.patch('tracker.views._get_safe_now', return_value=now):
            response = self.post_action({'action': 'stop', 'note': 'too short'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'error')
        self.assertFalse(TimeLog.objects.exists())
        self.assertFalse(DailyStudyStat.objects.exists())

    def test_stop_keeps_log_at_25_minute_boundary(self):
        now = shanghai_datetime(2026, 7, 18, 10, 0)
        start = now - datetime.timedelta(minutes=25)
        TimeLog.objects.create(category='math', start_time=start)

        with mock.patch('tracker.views._get_safe_now', return_value=now):
            response = self.post_action({'action': 'stop', 'note': 'boundary'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        log = TimeLog.objects.get()
        self.assertEqual(log.end_time, now)
        self.assertEqual(log.note, 'boundary')
        stat = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 18))
        self.assertEqual(stat.study_count, 1)
        self.assertEqual(stat.total_minutes, 25)

    def test_export_requires_token(self):
        response = self.client.get(reverse('export_logs_csv'))

        self.assertEqual(response.status_code, 403)

    def test_export_csv_contains_completed_logs(self):
        start = timezone.now() - datetime.timedelta(minutes=45)
        TimeLog.objects.create(
            category='english',
            start_time=start,
            end_time=start + datetime.timedelta(minutes=45),
            note='vocabulary',
        )

        response = self.client.get(
            reverse('export_logs_csv'),
            {'days': '7'},
            HTTP_AUTHORIZATION='test-token',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        body = response.content.decode('utf-8')
        self.assertIn('category_label', body)
        self.assertIn('english', body)
        self.assertIn('vocabulary', body)

    def test_dashboard_contains_month_and_all_time_summaries(self):
        now = timezone.now()
        TimeLog.objects.create(
            category='math',
            start_time=now - datetime.timedelta(days=3, minutes=30),
            end_time=now - datetime.timedelta(days=3),
        )
        TimeLog.objects.create(
            category='english',
            start_time=now - datetime.timedelta(days=60, minutes=60),
            end_time=now - datetime.timedelta(days=60),
        )

        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        month_summary = json.loads(response.context['month_summary'])
        all_time_summary = json.loads(response.context['all_time_summary'])
        streak_summary = json.loads(response.context['streak_summary'])
        self.assertEqual(month_summary['total_minutes'], 30)
        self.assertEqual(month_summary['session_count'], 1)
        self.assertEqual(month_summary['active_days'], 1)
        self.assertEqual(month_summary['best_day_minutes'], 30)
        self.assertEqual(all_time_summary['total_minutes'], 90)
        self.assertEqual(all_time_summary['session_count'], 2)
        self.assertEqual(all_time_summary['active_days'], 2)
        self.assertEqual(streak_summary['active_days'], 2)


@override_settings(TRACKER_API_TOKEN='test-token')
class AuthorizationMiddlewareTests(TestCase):
    def assert_private_no_store(self, response):
        directives = {
            directive.strip().lower()
            for directive in response['Cache-Control'].split(',')
        }
        self.assertEqual(directives, {'private', 'no-store'})
        vary_headers = {
            header.strip().lower()
            for header in response.get('Vary', '').split(',')
            if header.strip()
        }
        self.assertIn('authorization', vary_headers)
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_dashboard_and_daily_stats_require_token_without_leaking_data(self):
        start = shanghai_datetime(2026, 7, 18, 8, 15)
        TimeLog.objects.create(
            category='english',
            start_time=start,
            end_time=start + datetime.timedelta(minutes=45),
            note='PRIVATE-NOTE-SENTINEL',
        )

        for url_name in ('dashboard', 'daily_stats'):
            for header_kwargs in ({}, {'HTTP_AUTHORIZATION': 'wrong-token'}):
                with self.subTest(url_name=url_name, headers=header_kwargs):
                    response = self.client.get(reverse(url_name), **header_kwargs)

                    self.assertEqual(response.status_code, 403)
                    self.assertTemplateUsed(response, 'auth_gate.html')
                    self.assertIn('<body></body>', response.content.decode('utf-8'))
                    self.assertNotContains(
                        response,
                        'PRIVATE-NOTE-SENTINEL',
                        status_code=403,
                    )
                    self.assertNotContains(
                        response,
                        '2026年07月18日',
                        status_code=403,
                    )
                    self.assertNotContains(
                        response,
                        'Academic Analytics',
                        status_code=403,
                    )
                    self.assert_private_no_store(response)

    def test_correct_token_can_read_dashboard_and_daily_stats(self):
        start = shanghai_datetime(2026, 7, 18, 8, 15)
        TimeLog.objects.create(
            category='english',
            start_time=start,
            end_time=start + datetime.timedelta(minutes=45),
            note='PRIVATE-NOTE-SENTINEL',
        )

        dashboard_response = self.client.get(
            reverse('dashboard'),
            **AUTH_HEADERS,
        )
        daily_stats_response = self.client.get(
            reverse('daily_stats'),
            **AUTH_HEADERS,
        )

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'PRIVATE-NOTE-SENTINEL')
        self.assertEqual(daily_stats_response.status_code, 200)
        self.assertContains(daily_stats_response, '2026年07月18日')
        self.assert_private_no_store(dashboard_response)
        self.assert_private_no_store(daily_stats_response)

    def test_dashboard_escapes_log_json_before_embedding_it_in_html(self):
        start = timezone.now() - datetime.timedelta(minutes=45)
        TimeLog.objects.create(
            category='<img onerror=x>',
            start_time=start,
            end_time=start + datetime.timedelta(minutes=30),
            note='</span><img src=x onerror=alert(1)>',
        )

        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)
        html = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('</span><img src=x onerror=alert(1)>', html)
        self.assertNotIn('<img onerror=x>', html)
        self.assertIn('&lt;/span&gt;&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('const safeName = escapeHtml(item.name);', html)

    def test_anonymous_dashboard_request_never_runs_garbage_collection(self):
        active_log = TimeLog.objects.create(
            category='math',
            start_time=timezone.now() - datetime.timedelta(hours=7),
        )

        with mock.patch(
            'tracker.views._execute_lazy_garbage_collection',
            wraps=_execute_lazy_garbage_collection,
        ) as garbage_collection:
            response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)
        garbage_collection.assert_not_called()
        active_log.refresh_from_db()
        self.assertIsNone(active_log.end_time)

    def test_wrong_token_stop_does_not_change_the_active_task(self):
        active_log = TimeLog.objects.create(
            category='major',
            start_time=timezone.now() - datetime.timedelta(minutes=30),
        )

        response = self.client.post(
            reverse('api_action'),
            data=json.dumps({'action': 'stop', 'note': 'must-not-be-saved'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='wrong-token',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')
        active_log.refresh_from_db()
        self.assertIsNone(active_log.end_time)
        self.assertIsNone(active_log.note)

    def test_non_gate_routes_return_empty_forbidden_response(self):
        responses = (
            self.client.get('/admin/'),
            self.client.post(
                reverse('api_action'),
                data=json.dumps({'action': 'stop'}),
                content_type='application/json',
            ),
            self.client.get(reverse('export_logs_csv')),
            self.client.post(reverse('dashboard')),
            self.client.get('/not-a-real-route/'),
        )

        for response in responses:
            with self.subTest(path=response.wsgi_request.path):
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.content, b'')
                self.assert_private_no_store(response)

    def test_valid_token_is_compared_with_compare_digest(self):
        with mock.patch('tracker.auth.compare_digest', return_value=True) as compare:
            response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        compare.assert_called_once_with(b'test-token', b'test-token')

    @override_settings(TRACKER_API_TOKEN='正确令牌')
    def test_non_ascii_tokens_are_compared_without_server_errors(self):
        rejected_response = self.client.get(
            reverse('dashboard'),
            HTTP_AUTHORIZATION='错误令牌',
        )
        accepted_response = self.client.get(
            reverse('dashboard'),
            HTTP_AUTHORIZATION='正确令牌',
        )

        self.assertEqual(rejected_response.status_code, 403)
        self.assert_private_no_store(rejected_response)
        self.assertEqual(accepted_response.status_code, 200)

    @override_settings(TRACKER_API_TOKEN='')
    def test_empty_token_configuration_fails_closed(self):
        response = self.client.get(
            reverse('dashboard'),
            HTTP_AUTHORIZATION='eH_',
        )

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'auth_gate.html')
        self.assert_private_no_store(response)

    def test_view_decorator_uses_same_empty_forbidden_response(self):
        request = RequestFactory().post('/protected/')

        @token_required
        def protected_view(_request):
            return HttpResponse('private')

        response = protected_view(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'')
        self.assert_private_no_store(response)


@override_settings(TIME_ZONE='Asia/Shanghai', USE_TZ=True)
class DailyStudyStatSignalTests(TestCase):
    def create_completed_log(self, start, minutes, category='math'):
        return TimeLog.objects.create(
            category=category,
            start_time=start,
            end_time=start + datetime.timedelta(minutes=minutes),
        )

    def test_date_field_is_unique(self):
        self.assertTrue(DailyStudyStat._meta.get_field('date').unique)

    def test_same_day_uses_earliest_start_and_repeated_save_is_idempotent(self):
        day = datetime.date(2026, 7, 18)
        later_start = shanghai_datetime(2026, 7, 18, 10, 0)
        earlier_start = shanghai_datetime(2026, 7, 18, 7, 30)
        later_log = self.create_completed_log(later_start, 35)
        earlier_log = self.create_completed_log(earlier_start, 55, category='english')

        stat = DailyStudyStat.objects.get(date=day)
        self.assertEqual(stat.study_count, 2)
        self.assertEqual(stat.first_start_time, earlier_start)
        self.assertEqual(stat.total_minutes, 90)

        later_log.note = 'saved again'
        later_log.save(update_fields=['note'])

        stat.refresh_from_db()
        self.assertEqual(DailyStudyStat.objects.filter(date=day).count(), 1)
        self.assertEqual(stat.study_count, 2)
        self.assertEqual(stat.first_start_time, earlier_start)
        self.assertEqual(stat.total_minutes, 90)

        earlier_log.delete()
        stat.refresh_from_db()
        self.assertEqual(stat.study_count, 1)
        self.assertEqual(stat.first_start_time, later_start)
        self.assertEqual(stat.total_minutes, 35)

        later_log.delete()
        self.assertFalse(DailyStudyStat.objects.filter(date=day).exists())

    def test_uses_shanghai_start_date_across_utc_and_local_midnight(self):
        crosses_midnight_start = datetime.datetime(
            2026, 7, 17, 15, 50, tzinfo=datetime.timezone.utc
        )
        after_midnight_start = datetime.datetime(
            2026, 7, 17, 16, 5, tzinfo=datetime.timezone.utc
        )
        self.create_completed_log(crosses_midnight_start, 40)
        self.create_completed_log(after_midnight_start, 30, category='major')

        july_17 = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 17))
        july_18 = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 18))
        self.assertEqual(july_17.study_count, 1)
        self.assertEqual(july_17.first_start_time, crosses_midnight_start)
        self.assertEqual(july_17.total_minutes, 40)
        self.assertEqual(july_18.study_count, 1)
        self.assertEqual(july_18.first_start_time, after_midnight_start)
        self.assertEqual(july_18.total_minutes, 30)

    def test_active_log_is_excluded_and_becoming_active_removes_summary(self):
        start = shanghai_datetime(2026, 7, 18, 8, 0)
        log = TimeLog.objects.create(category='math', start_time=start)

        self.assertFalse(
            DailyStudyStat.objects.filter(date=datetime.date(2026, 7, 18)).exists()
        )

        log.end_time = start + datetime.timedelta(minutes=45)
        log.save(update_fields=['end_time'])
        stat = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 18))
        self.assertEqual(stat.study_count, 1)
        self.assertEqual(stat.total_minutes, 45)

        log.end_time = None
        log.save(update_fields=['end_time'])
        self.assertFalse(
            DailyStudyStat.objects.filter(date=datetime.date(2026, 7, 18)).exists()
        )

    def test_moving_completed_log_rebuilds_old_and_new_dates(self):
        old_start = shanghai_datetime(2026, 7, 17, 9, 0)
        new_start = shanghai_datetime(2026, 7, 19, 6, 45)
        log = self.create_completed_log(old_start, 30)

        log.start_time = new_start
        log.end_time = new_start + datetime.timedelta(minutes=50)
        log.save(update_fields=['start_time', 'end_time'])

        self.assertFalse(
            DailyStudyStat.objects.filter(date=datetime.date(2026, 7, 17)).exists()
        )
        stat = DailyStudyStat.objects.get(date=datetime.date(2026, 7, 19))
        self.assertEqual(stat.study_count, 1)
        self.assertEqual(stat.first_start_time, new_start)
        self.assertEqual(stat.total_minutes, 50)


@override_settings(
    TIME_ZONE='Asia/Shanghai',
    USE_TZ=True,
    TRACKER_API_TOKEN='test-token',
)
class DailyStatsPageTests(TestCase):
    def create_completed_log(self, start, minutes, category='math'):
        return TimeLog.objects.create(
            category=category,
            start_time=start,
            end_time=start + datetime.timedelta(minutes=minutes),
        )

    def test_daily_stats_route_renders_empty_state(self):
        self.assertEqual(reverse('daily_stats'), '/daily-stats/')

        response = self.client.get(reverse('daily_stats'), **AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'daily_stats.html')
        self.assertContains(response, '每日学习统计')
        self.assertContains(response, '暂无学习统计')

    def test_daily_stats_page_is_newest_first_and_contains_overview(self):
        older = shanghai_datetime(2026, 7, 16, 9, 0)
        newer_early = shanghai_datetime(2026, 7, 18, 7, 15)
        newer_late = shanghai_datetime(2026, 7, 18, 13, 0)
        self.create_completed_log(older, 30)
        self.create_completed_log(newer_late, 45, category='major')
        self.create_completed_log(newer_early, 60, category='english')

        response = self.client.get(reverse('daily_stats'), **AUTH_HEADERS)

        dates = [stat.date for stat in response.context['page_obj'].object_list]
        self.assertEqual(
            dates,
            [datetime.date(2026, 7, 18), datetime.date(2026, 7, 16)],
        )
        overview = response.context['overview']
        self.assertEqual(overview['day_count'], 2)
        self.assertEqual(overview['study_count'], 3)
        self.assertEqual(overview['total_minutes'], 135)
        self.assertEqual(overview['total_hours'], 2.25)
        self.assertContains(response, '返回 Dashboard')

    def test_dashboard_exposes_today_metrics_and_metric_elements(self):
        now = shanghai_datetime(2026, 7, 18, 15, 0)
        first_start = shanghai_datetime(2026, 7, 18, 7, 15)
        self.create_completed_log(first_start, 60)
        self.create_completed_log(shanghai_datetime(2026, 7, 18, 11, 30), 45)

        with mock.patch('tracker.views._get_safe_now', return_value=now):
            response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        daily_metrics = json.loads(response.context['daily_metrics'])
        self.assertEqual(
            daily_metrics['2026-07-18'],
            {'study_count': 2, 'first_start_time': '07:15'},
        )
        self.assertContains(response, 'id="today-study-count"')
        self.assertContains(response, 'id="today-first-start"')
        self.assertContains(response, 'id="data-daily-metrics"')


@override_settings(TRACKER_API_TOKEN='test-token')
class DashboardScheduleTests(TestCase):
    def test_dashboard_receives_complete_summer_schedule(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)
        schedule = response.context['summer_schedule']
        self.assertEqual(schedule['timeline'][0]['time'], '06:30')
        self.assertEqual(schedule['timeline'][-1]['time'], '23:00')
        self.assertEqual(len(schedule['timeline']), 15)
        self.assertEqual(len(schedule['weekly_training']), 7)
        self.assertEqual(len(schedule['study_quotas']), 3)
        self.assertEqual(len(schedule['rules']), 6)

    def test_dashboard_renders_hidden_responsive_schedule_dialog(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertContains(response, 'id="open-study-plan"')
        self.assertContains(response, 'id="study-plan-dialog"')
        self.assertContains(response, 'aria-label="关闭暑假作息计划"')
        self.assertContains(response, 'data-plan-tab="timeline"')
        self.assertContains(response, 'data-plan-tab="training"')
        self.assertContains(response, 'data-plan-tab="quota"')
        self.assertContains(response, 'data-plan-tab="rules"')
        self.assertContains(response, '低刺激放松')
        self.assertContains(response, '睡眠少于 6 小时')

    def test_schedule_accessor_returns_an_isolated_copy(self):
        first = get_summer_schedule()
        first['timeline'][0]['title'] = 'changed'

        second = get_summer_schedule()
        self.assertEqual(second['timeline'][0]['title'], '起床')


@override_settings(TRACKER_API_TOKEN='test-token')
class DashboardFocusModeTests(TestCase):
    def test_focus_overlay_hides_elapsed_duration_and_shows_shanghai_clock(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertContains(response, 'id="zen-subject"')
        self.assertContains(response, 'id="zen-clock"')
        self.assertContains(response, '上海时间')
        self.assertContains(response, "timeZone: 'Asia/Shanghai'")
        self.assertContains(response, '结束学习')
        self.assertNotContains(response, 'id="zen-timer"')
        self.assertNotContains(response, 'function formatTime')
        html = response.content.decode('utf-8')
        focus_markup = html.split('<div id="zen-overlay"', 1)[1].split(
            '<div id="django-context">', 1
        )[0]
        self.assertNotIn('00:00:00', focus_markup)

    def test_focus_mode_keeps_hidden_elapsed_guard_for_short_sessions(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)

        self.assertContains(response, 'getActiveElapsedSeconds() < 25 * 60')
        self.assertContains(response, 'activeElapsedBaseSeconds + elapsedSinceSync')
        self.assertContains(response, 'id="data-active-elapsed"')
        self.assertContains(response, 'dashboard.inert = true')

    def test_action_auth_failure_prompts_and_retries_the_same_request(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)
        html = response.content.decode('utf-8')

        self.assertIn(
            'const authFailed = response.status === 401 || response.status === 403;',
            html,
        )
        self.assertIn('Authorization 请求头值无效，请重新输入', html)
        self.assertIn(
            'body: JSON.stringify({ action: action, category: category, note: note })',
            html,
        )
        self.assertIn('finally {\n            setNetworkState(false, finalStatus);', html)

    def test_soft_reload_uses_auth_header_without_full_reload_loop(self):
        response = self.client.get(reverse('dashboard'), **AUTH_HEADERS)
        html = response.content.decode('utf-8')

        soft_reload = html.split('async function softReloadDashboard()', 1)[1].split(
            'function handleStop()',
            1,
        )[0]
        self.assertIn('fetchWithEhAuth(', soft_reload)
        self.assertIn('window.location.href', soft_reload)
        self.assertNotIn('window.location.reload()', soft_reload)


@override_settings(TIME_ZONE='Asia/Shanghai', USE_TZ=True)
class DailyStudyStatMigrationTests(TransactionTestCase):
    migrate_from = ('tracker', '0003_timelog_note_alter_timelog_category')
    migrate_to = ('tracker', '0004_dailystudystat')

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_backfills_completed_legacy_logs_by_shanghai_start_date(self):
        HistoricalTimeLog = self.old_apps.get_model('tracker', 'TimeLog')
        first_start = shanghai_datetime(2026, 7, 18, 0, 5)
        second_start = shanghai_datetime(2026, 7, 18, 8, 0)
        next_day_start = shanghai_datetime(2026, 7, 19, 23, 50)
        HistoricalTimeLog.objects.create(
            category='mth',
            start_time=first_start,
            end_time=first_start + datetime.timedelta(minutes=30),
        )
        HistoricalTimeLog.objects.create(
            category='eng',
            start_time=second_start,
            end_time=second_start + datetime.timedelta(minutes=45),
        )
        HistoricalTimeLog.objects.create(
            category='pro',
            start_time=next_day_start,
            end_time=next_day_start + datetime.timedelta(minutes=40),
        )
        HistoricalTimeLog.objects.create(
            category='mth',
            start_time=shanghai_datetime(2026, 7, 20, 9, 0),
            end_time=None,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        HistoricalDailyStudyStat = new_apps.get_model('tracker', 'DailyStudyStat')

        self.assertEqual(HistoricalDailyStudyStat.objects.count(), 2)
        july_18 = HistoricalDailyStudyStat.objects.get(date=datetime.date(2026, 7, 18))
        self.assertEqual(july_18.study_count, 2)
        self.assertEqual(july_18.first_start_time, first_start)
        self.assertEqual(july_18.total_minutes, 75)
        july_19 = HistoricalDailyStudyStat.objects.get(date=datetime.date(2026, 7, 19))
        self.assertEqual(july_19.study_count, 1)
        self.assertEqual(july_19.first_start_time, next_day_start)
        self.assertEqual(july_19.total_minutes, 40)
