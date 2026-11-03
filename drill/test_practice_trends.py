import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Question, QuestionAttempt, QuestionDocument
from .practice_trend_views import PracticeTrendView


@override_settings(
    ALLOWED_HOSTS=['*'],
    DRILL_HOSTS={'drill.test'},
    EI_HOSTS={'ei.test'},
    TIME_ZONE='Asia/Shanghai',
)
class PracticeTrendTests(TestCase):
    today = datetime.date(2026, 10, 30)

    def setUp(self):
        self.user = get_user_model().objects.create_user('trend-owner')
        self.other = get_user_model().objects.create_user('trend-other')
        self.drill_document = QuestionDocument.objects.create(
            source_id=88001, workspace='drill', title='Math', sha256='1' * 64, page_count=1,
        )
        self.ei_document = QuestionDocument.objects.create(
            source_id=88002, workspace='ei', title='EI', sha256='2' * 64, page_count=1,
        )
        self.q1 = self.question(self.drill_document, 1, '3')
        self.q2 = self.question(self.drill_document, 2, '4')
        self.q3 = self.question(self.drill_document, 3, '5')
        self.ei_question = self.question(self.ei_document, 1, '6')
        self.factory = APIRequestFactory()

    def question(self, document, order, fingerprint):
        return Question.objects.create(
            document=document,
            question_order=order,
            prompt_text=f'Question {order}',
            fingerprint=fingerprint * 64,
        )

    def at(self, day, hour=12, minute=0):
        local = datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=ZoneInfo('Asia/Shanghai'))
        return local.astimezone(datetime.timezone.utc)

    def attempt(self, question, day, *, result='correct', user=None, hour=12, minute=0):
        return QuestionAttempt.objects.create(
            user=user or self.user,
            question=question,
            result=result,
            created_at=self.at(day, hour, minute),
        )

    def response(self, *, host='drill.test', user=None, query='days=30&target=24&deadline=2026-11-22'):
        request = self.factory.get('/api/drill/practice-trends/?' + query, HTTP_HOST=host)
        force_authenticate(request, user=user or self.user)
        with patch('drill.practice_trend_views.timezone.localdate', return_value=self.today):
            return PracticeTrendView.as_view()(request)

    def seed_history(self):
        # Same question, same day: one daily question but two submissions.
        self.attempt(self.q1, self.today)
        self.attempt(self.q1, self.today, result='review')
        self.attempt(self.q2, self.today)
        # Same question on another date is counted on that date too.
        self.attempt(self.q1, self.today - datetime.timedelta(days=1))
        self.attempt(self.q1, self.today - datetime.timedelta(days=3))
        self.attempt(self.q2, self.today - datetime.timedelta(days=3))
        # 00:01 Beijing belongs to this natural day.
        self.attempt(self.q2, self.today - datetime.timedelta(days=7), hour=0, minute=1)
        # Previous non-overlapping seven-day window.
        self.attempt(self.q1, self.today - datetime.timedelta(days=8))
        self.attempt(self.q2, self.today - datetime.timedelta(days=10))
        # Reset is a state change, not a completed attempt.
        self.attempt(self.q3, self.today, result='reset')
        # Other users and the other workspace are private/isolated.
        self.attempt(self.q3, self.today, user=self.other)
        self.attempt(self.ei_question, self.today)

    def test_daily_dedup_missing_days_windows_average_and_timezone(self):
        self.seed_history()
        payload = self.response(query='days=14&target=2&deadline=2026-11-22').data
        by_date = {str(item['date']): item for item in payload['points']}
        self.assertEqual(by_date['2026-10-30']['count'], 2)
        self.assertEqual(by_date['2026-10-30']['submissions'], 3)
        self.assertTrue(by_date['2026-10-30']['is_today'])
        self.assertFalse(by_date['2026-10-30']['is_complete_day'])
        self.assertEqual(by_date['2026-10-29']['count'], 1)
        self.assertEqual(by_date['2026-10-28']['count'], 0)
        self.assertEqual(by_date['2026-10-23']['count'], 1)
        self.assertEqual(payload['summary']['last7'], 4)
        self.assertEqual(payload['summary']['previous7'], 2)
        self.assertEqual(payload['summary']['growth_percent'], 100.0)
        self.assertEqual(payload['summary']['average7'], 0.6)
        self.assertEqual(by_date['2026-10-30']['moving_average_7'], 0.7)
        self.assertEqual(payload['period']['submissions'], 9)
        self.assertEqual(payload['period']['different_questions'], 2)

    def test_workspace_and_user_are_isolated_and_today_can_be_zero(self):
        self.seed_history()
        drill = self.response().data
        ei = self.response(host='ei.test', query='days=7&target=11').data
        empty = self.response(user=self.other, query='days=7').data
        self.assertEqual(drill['workspace'], 'drill')
        self.assertEqual(drill['question_target'], 690)
        self.assertEqual(drill['summary']['today'], 2)
        self.assertEqual(ei['workspace'], 'ei')
        self.assertEqual(ei['question_target'], 307)
        self.assertEqual(ei['summary']['today'], 1)
        self.assertEqual(empty['summary']['today'], 1)
        third = get_user_model().objects.create_user('no-attempts')
        no_data = self.response(user=third, query='days=7').data
        self.assertEqual(no_data['summary']['today'], 0)
        self.assertEqual([item['count'] for item in no_data['points']], [0] * 7)

    def test_current_completion_uses_latest_state_and_prediction_is_safe(self):
        self.seed_history()
        payload = self.response(query='days=7&target=24&deadline=2026-11-22').data
        self.assertEqual(payload['summary']['completed_distinct'], 2)
        self.assertEqual(payload['summary']['remaining'], 688)
        self.assertEqual(payload['prediction']['days_remaining_including_today'], 24)
        self.assertEqual(payload['prediction']['required_daily'], 29)
        self.assertEqual(len(payload['prediction']['scenarios']), 3)
        self.assertFalse(payload['prediction']['scenarios'][0]['on_track'])

    def test_zero_previous_period_has_no_division_error(self):
        self.attempt(self.q1, self.today - datetime.timedelta(days=1))
        payload = self.response(query='days=7').data
        self.assertIsNone(payload['summary']['growth_percent'])
        self.assertEqual(payload['summary']['previous7'], 0)

    def test_query_count_remains_bounded(self):
        self.seed_history()
        with self.assertNumQueries(5):
            response = self.response(query='days=90')
            self.assertEqual(response.status_code, 200)
