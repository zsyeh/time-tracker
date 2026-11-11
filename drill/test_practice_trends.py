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
            relation_type='selected_question_book',
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
        self.assertEqual(drill['question_target'], 3)
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
        self.assertEqual(payload['summary']['remaining'], 1)
        self.assertEqual(payload['prediction']['days_remaining_including_today'], 24)
        self.assertEqual(payload['prediction']['required_daily'], 1)
        self.assertEqual(len(payload['prediction']['scenarios']), 2)
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

    def test_selected_scope_matches_heatmap_and_final_types_are_dynamic(self):
        from .models import QuestionExamType
        from .views import DrillHeatmapView
        for question, kind in ((self.q1, 'choice'), (self.q2, 'fill'), (self.q3, 'large')):
            QuestionExamType.objects.create(question=question, source_system='drill', question_type=kind,
                classification_source='manual', classification_version='test', content_hash='a' * 64)
        self.attempt(self.q1, self.today)
        self.attempt(self.q2, self.today, result='review')
        unrelated_doc = QuestionDocument.objects.create(source_id=88003, workspace='drill',
            title='Not selected', sha256='7' * 64, page_count=1)
        outside = self.question(unrelated_doc, 1, '8')
        self.attempt(outside, self.today)
        payload = self.response().data
        request = self.factory.get('/api/drill/heatmap/?scope=all&collection=selected', HTTP_HOST='drill.test')
        force_authenticate(request, user=self.user)
        heatmap = DrillHeatmapView.as_view()(request).data
        self.assertEqual(payload['goal']['total'], heatmap['question_count'])
        self.assertEqual(payload['goal']['covered'], heatmap['statistics']['attempted_question_count'])
        self.assertEqual(payload['goal']['mastered'], heatmap['statistics']['mastered_question_count'])
        self.assertEqual(payload['goal']['review'], heatmap['statistics']['review_question_count'])
        self.assertEqual(payload['goal']['type_breakdown']['small'],
                         {'total': 2, 'covered': 2, 'mastered': 1, 'review': 1, 'remaining': 0, 'required_daily': 0})
        self.assertEqual(payload['goal']['type_breakdown']['large']['remaining'], 1)
        self.assertEqual(payload['summary']['today'], 3)  # Existing workspace workload remains visible.
        self.assertEqual(payload['summary']['today_net_coverage'], 2)

    def test_reset_repeated_work_and_undo_recompute_net_coverage(self):
        yesterday = self.today - datetime.timedelta(days=1)
        self.attempt(self.q1, yesterday, hour=8)
        self.attempt(self.q1, yesterday, result='review', hour=9)
        reset = self.attempt(self.q1, self.today, result='reset', hour=8)
        payload = self.response().data
        self.assertEqual(payload['summary']['net_coverage_last7'], 1)
        self.assertEqual(payload['summary']['today_net_coverage'], -1)
        self.assertEqual(payload['goal']['covered'], 0)
        reset.delete()  # Undo removes evidence rather than appending a fake transition.
        payload = self.response().data
        self.assertEqual(payload['summary']['today_net_coverage'], 0)
        self.assertEqual(payload['goal']['covered'], 1)
        self.attempt(self.q1, self.today, result='reset', hour=8)
        self.attempt(self.q1, self.today, result='review', hour=9)
        self.assertEqual(self.response().data['summary']['today_net_coverage'], 0)

    def test_predictions_use_complete_net_days_not_workload_and_do_not_double_count_today(self):
        from .practice_trend_views import _forecast
        scenario = _forecast('test', 10, 100, 150, 50, self.today + datetime.timedelta(days=2),
                             self.today, 6, window_days=7, history_days=14)
        self.assertEqual(scenario['today_remaining_capacity'], 4)
        self.assertEqual(scenario['projected_added'], 24)
        self.assertEqual(scenario['projected_total'], 124)
        self.assertEqual(scenario['estimated_completion_date'], self.today + datetime.timedelta(days=5))
        self.assertFalse(scenario['on_track'])
        insufficient = _forecast('test', 10, 1, 3, 2, self.today, self.today, 0,
                                 window_days=14, history_days=2)
        self.assertEqual(insufficient['status'], 'insufficient_history')
        self.assertIsNone(insufficient['projected_total'])
        self.assertIsNone(insufficient['on_track'])
        overdue = _forecast('test', 10, 1, 3, 2, self.today - datetime.timedelta(days=1),
                            self.today, 0, window_days=14, history_days=2)
        self.assertEqual(overdue['status'], 'past_deadline')
        self.assertEqual(overdue['projected_added'], 0)
        payload = self.response(query='days=7').data
        self.assertEqual(payload['prediction']['deadline'], datetime.date(2026, 11, 21))
        self.assertEqual(payload['prediction']['original_deadline'], datetime.date(2026, 11, 22))
        self.assertEqual(payload['prediction']['forecast_basis'], 'net_coverage')

    def test_real_scale_dynamic_goal_and_per_type_daily_plan(self):
        self.drill_document.questions.all().delete()
        questions = Question.objects.bulk_create([
            Question(document=self.drill_document, question_order=index,
                     fingerprint=f'scale-{index}', prompt_text='Question',
                     question_type='fill_blank' if index < 619 else 'solution')
            for index in range(963)
        ])
        covered = questions[:345] + questions[619:619 + 157]
        QuestionAttempt.objects.bulk_create([
            QuestionAttempt(user=self.user, question=question, result='review',
                            created_at=self.at(self.today)) for question in covered
        ])
        with patch.object(self, 'today', datetime.date(2026, 11, 11)):
            payload = self.response(query='days=7').data
        goal = payload['goal']
        self.assertEqual((goal['total'], goal['covered'], goal['remaining']), (963, 502, 461))
        self.assertEqual(payload['prediction']['required_daily'], 42)
        self.assertEqual(goal['type_breakdown']['small']['required_daily'], 25)
        self.assertEqual(goal['type_breakdown']['large']['required_daily'], 17)
        self.assertEqual(goal['mastered'], 0)  # Coverage is not mastery.

    def test_repeated_work_cannot_improve_forecast_or_be_changed_by_workload_target(self):
        old = self.today - datetime.timedelta(days=20)
        self.attempt(self.q1, old)
        for day in range(1, 8):
            self.attempt(self.q1, self.today - datetime.timedelta(days=day), result='review')
        payload = self.response(query='days=7&target=1').data
        changed = self.response(query='days=7&target=500').data
        self.assertEqual(payload['summary']['last7'], 7)
        self.assertEqual(payload['summary']['net_coverage_last7'], 0)
        self.assertEqual(payload['prediction']['scenarios'][0]['status'], 'no_positive_rate')
        self.assertEqual(payload['prediction']['scenarios'], changed['prediction']['scenarios'])

    def test_timezone_window_boundary_and_undo_reveals_reset(self):
        boundary = self.today - datetime.timedelta(days=7)
        self.attempt(self.q1, boundary - datetime.timedelta(days=1), hour=23, minute=59)
        self.attempt(self.q1, boundary, result='review', hour=0, minute=0)
        self.attempt(self.q2, boundary, result='reset', hour=0, minute=0)
        valid = self.attempt(self.q2, boundary, hour=0, minute=1)
        self.assertEqual(self.response().data['summary']['net_coverage_last7'], 1)
        valid.delete()
        payload = self.response().data
        self.assertEqual(payload['summary']['net_coverage_last7'], 0)
        self.assertEqual(payload['goal']['covered'], 1)

    def test_fractional_prediction_is_conservative_and_empty_scope_is_unknown(self):
        from .practice_trend_views import _forecast
        projected = _forecast('test', 1.9, 0, 2, 2, self.today, self.today, 0,
                              window_days=7, history_days=7)
        self.assertEqual(projected['projected_total'], 1)
        self.assertEqual(projected['shortfall'], 1)
        self.assertFalse(projected['on_track'])
        self.assertEqual(projected['estimated_completion_date'], self.today + datetime.timedelta(days=1))
        self.drill_document.relation_type = ''
        self.drill_document.save(update_fields=['relation_type'])
        payload = self.response().data
        self.assertEqual(payload['goal']['status'], 'empty_scope')
        self.assertFalse(payload['prediction']['remaining_determinable'])
        self.assertIsNone(payload['prediction']['required_daily'])
        self.assertEqual(payload['prediction']['scenarios'][0]['status'], 'empty_scope')
        self.assertIsNone(payload['prediction']['scenarios'][0]['on_track'])

    def test_future_latest_state_matches_heatmap_but_not_observed_history(self):
        from .views import DrillHeatmapView
        self.attempt(self.q1, self.today - datetime.timedelta(days=1))
        self.attempt(self.q1, self.today + datetime.timedelta(days=1), result='reset')
        self.attempt(self.q2, self.today + datetime.timedelta(days=2), result='review')
        payload = self.response().data
        request = self.factory.get('/api/drill/heatmap/?scope=all&collection=selected', HTTP_HOST='drill.test')
        force_authenticate(request, user=self.user)
        heatmap = DrillHeatmapView.as_view()(request).data
        self.assertEqual(payload['goal']['covered'], heatmap['statistics']['attempted_question_count'])
        self.assertEqual(payload['goal']['review'], heatmap['statistics']['review_question_count'])
        self.assertEqual(payload['goal']['covered'], 1)
        self.assertEqual(payload['goal']['review'], 1)
        self.assertEqual(payload['summary']['net_coverage_last7'], 1)
        self.assertEqual(payload['summary']['today_net_coverage'], 0)
        self.assertEqual(payload['prediction']['history_available_days'], 1)
