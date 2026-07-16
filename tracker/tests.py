import datetime
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TimeLog
from .schedule import get_summer_schedule


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

    def test_start_accepts_training_category(self):
        response = self.post_action({'action': 'start', 'category': 'training'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TimeLog.objects.filter(category='training', end_time__isnull=True).exists())

    def test_stop_deletes_too_short_log(self):
        TimeLog.objects.create(category='math')

        response = self.post_action({'action': 'stop', 'note': 'short'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TimeLog.objects.count(), 0)

    def test_stop_closes_valid_log(self):
        TimeLog.objects.create(
            category='math',
            start_time=timezone.now() - datetime.timedelta(minutes=30),
        )

        response = self.post_action({'action': 'stop', 'note': 'done'})

        self.assertEqual(response.status_code, 200)
        log = TimeLog.objects.get()
        self.assertIsNotNone(log.end_time)
        self.assertEqual(log.note, 'done')

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

        response = self.client.get(reverse('dashboard'))

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


class DashboardScheduleTests(TestCase):
    def test_dashboard_receives_complete_summer_schedule(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        schedule = response.context['summer_schedule']
        self.assertEqual(schedule['timeline'][0]['time'], '06:30')
        self.assertEqual(schedule['timeline'][-1]['time'], '23:00')
        self.assertEqual(len(schedule['timeline']), 15)
        self.assertEqual(len(schedule['weekly_training']), 7)
        self.assertEqual(len(schedule['study_quotas']), 3)
        self.assertEqual(len(schedule['rules']), 6)

    def test_dashboard_renders_hidden_responsive_schedule_dialog(self):
        response = self.client.get(reverse('dashboard'))

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
