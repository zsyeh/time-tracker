import datetime
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TimeLog


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
