"""Navigation equivalence and query-bound regressions (no production fixtures)."""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from .models import Question, QuestionAttempt, QuestionDocument, QuestionUserState
from .views import (
    navigation_queryset, navigation_with_latest_result, next_unmastered_question,
    ordinary_question_navigation, next_review_question, previous_review_question, question_progress,
)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['drill.test', 'ei.test'],
                   DRILL_HOSTS={'drill.test'}, EI_HOSTS={'ei.test'}, DRILL_SEARCH_BACKEND='legacy')
class NavigationQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('navigation-owner')
        cls.other = get_user_model().objects.create_user('navigation-other')
        cls.questions = []
        for book in range(3):
            document = QuestionDocument.objects.create(
                source_id=9900 + book, workspace='ei' if book == 2 else 'drill',
                filename=f'nav{book}.pdf', title=f'Book {book}', sha256=str(book) * 64,
                page_count=1, relation_type='selected_question_book',
            )
            for index in range(8):
                question = Question.objects.create(
                    document=document, question_order=index,
                    source_label=f'Question {index}', fingerprint=f'{book}-{index}',
                    source_category='past_exam' if index < 6 else 'mock',
                    question_type='single_choice' if index % 2 else 'solution',
                    prompt_text='needle' if index % 2 else 'haystack', is_practiceable=True,
                )
                cls.questions.append(question)
                if index % 4:
                    QuestionAttempt.objects.create(
                        user=cls.user, question=question,
                        result=('reset', 'correct', 'review', 'done')[index % 4],
                        created_at=timezone.now() - datetime.timedelta(days=6 if index < 4 else 1),
                    )
                QuestionAttempt.objects.create(user=cls.other, question=question, result='correct')

    def request(self, params=None, host='drill.test'):
        request = Request(APIRequestFactory().get('/', params or {}, HTTP_HOST=host))
        request._user = self.user
        return request

    def test_progress_counts_reset_and_other_users_without_changing_latest_state(self):
        question = self.questions[0]
        stamp = timezone.now()
        for result in ('done', 'correct', 'review', 'reset'):
            QuestionAttempt.objects.create(user=self.user, question=question,
                                           result=result, created_at=stamp)
        summary = question_progress(Question.objects.filter(pk=question.pk), self.user).get()
        self.assertEqual(summary.attempt_count, 3)
        self.assertEqual(summary.state_change_count, 4)
        self.assertEqual(summary.latest_result, 'reset')
        self.assertEqual(summary.latest_attempted_at, stamp)
        other = question_progress(Question.objects.filter(pk=question.pk), self.other).get()
        self.assertEqual(other.attempt_count, 1)
        self.assertEqual(other.state_change_count, 1)
        self.assertEqual(other.latest_result, 'correct')

    def test_progress_returns_zero_counts_for_questions_without_own_attempts(self):
        summary = question_progress(Question.objects.filter(pk=self.questions[0].pk), self.user).get()
        self.assertEqual(summary.attempt_count, 0)
        self.assertEqual(summary.state_change_count, 0)
        self.assertIsNone(summary.latest_result)
        self.assertIsNone(summary.latest_attempted_at)

    def test_bounded_neighbors_equal_original_materialized_order_and_fallback(self):
        # Covers ordering across books, hidden current question,
        # reset/other-user states, type/search/unattempted filters and both workspaces.
        for host, questions in (('drill.test', self.questions[:16]), ('ei.test', self.questions[16:])):
            for params in ({}, {'q': 'needle'}, {'unattempted': '1'}, {'type_group': 'small'},
                           {'collection': 'selected'}, {'source_category': 'mock'}):
                request = self.request(params, host)
                for question in questions:
                    with self.subTest(host=host, params=params, question=question.pk):
                        rows = list(navigation_with_latest_result(
                            navigation_queryset(question, request), self.user,
                        ).values_list('pk', 'uuid', 'next_latest_result'))
                        position = next((i for i, row in enumerate(rows) if row[0] == question.pk), -1)
                        previous = rows[position - 1][1] if position > 0 else None
                        following = next_unmastered_question(question, request, rows)
                        actual = ordinary_question_navigation(question, request)
                        self.assertEqual(actual['previous_question_uuid'], str(previous) if previous else None)
                        self.assertEqual(actual['next_question_uuid'], str(following) if following else None)

    def test_ordinary_navigation_only_returns_bounded_rows(self):
        with CaptureQueriesContext(connection) as queries:
            ordinary_question_navigation(self.questions[2], self.request())
        selects = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith('SELECT')]
        self.assertTrue(selects)
        self.assertTrue(all('LIMIT 1' in sql.upper() for sql in selects))

    def test_collection_detail_does_not_compute_discarded_default_navigation(self):
        QuestionUserState.objects.create(user=self.user, question=self.questions[0], is_favorite=True)
        QuestionUserState.objects.create(user=self.user, question=self.questions[1], is_favorite=True)
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(self.user)
        with patch('drill.views.ordinary_question_navigation', side_effect=AssertionError('unused navigation')):
            response = client.get(f'/api/drill/questions/{self.questions[1].uuid}/',
                                  {'from': 'collection', 'collection': 'favorite'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['sequential_next_question_uuid'], str(self.questions[0].uuid))
        invalid = client.get(f'/api/drill/questions/{self.questions[1].uuid}/',
                             {'from': 'collection', 'collection': 'favorite', 'type_group': 'invalid'})
        self.assertEqual(invalid.status_code, 400)

    def test_history_detail_does_not_compute_discarded_default_navigation(self):
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(self.user)
        with patch('drill.views.ordinary_question_navigation', side_effect=AssertionError('unused navigation')):
            response = client.get(f'/api/drill/questions/{self.questions[2].uuid}/',
                                  {'from': 'insight', 'insight_list': 'attempts', 'insight_return': '/insight'})
        self.assertEqual(response.status_code, 200)

    def test_detail_reuses_full_latest_attempt_without_duplicate_latest_projections(self):
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(self.user)
        for question in (self.questions[0], self.questions[2]):
            with self.subTest(question=question.pk), CaptureQueriesContext(connection) as queries:
                response = client.get(f'/api/drill/questions/{question.uuid}/')
            self.assertEqual(response.status_code, 200)
            latest = QuestionAttempt.objects.filter(user=self.user, question=question).order_by('-created_at', '-pk').first()
            self.assertEqual(response.data['latest_result'], latest.result if latest else None)
            detail_sql = next(q['sql'] for q in queries if ' AS "attempt_count"' in q['sql'])
            self.assertNotIn(' AS "latest_result"', detail_sql)
            self.assertNotIn(' AS "latest_attempted_at"', detail_sql)
        # List/heatmap callers keep their original projections by default.
        summary = question_progress(Question.objects.filter(pk=self.questions[2].pk), self.user).get()
        self.assertEqual(summary.latest_result, 'review')
        self.assertIsNotNone(summary.latest_attempted_at)

    def test_last_timed_reuses_latest_but_falls_back_after_reset_or_untimed_attempt(self):
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(self.user)
        question = self.questions[0]

        def detail():
            with CaptureQueriesContext(connection) as queries:
                response = client.get(f'/api/drill/questions/{question.uuid}/')
            self.assertEqual(response.status_code, 200)
            timed_queries = [row['sql'] for row in queries
                             if '"time_spent_seconds" IS NOT NULL' in row['sql']]
            return response.data, timed_queries

        data, queries = detail()
        self.assertIsNone(data['last_time_spent_seconds'])
        self.assertFalse(queries)
        timed = QuestionAttempt.objects.create(user=self.user, question=question,
                                              result='correct', time_spent_seconds=71)
        data, queries = detail()
        self.assertEqual(data['last_time_spent_seconds'], 71)
        self.assertFalse(queries)
        for result in ('review', 'reset'):
            QuestionAttempt.objects.create(user=self.user, question=question, result=result)
            data, queries = detail()
            self.assertEqual(data['latest_result'], result)
            self.assertEqual(data['last_time_spent_seconds'], 71)
            self.assertEqual(data['last_timed_at'], timed.created_at)
            self.assertEqual(len(queries), 1)

    def test_review_neighbors_match_full_forward_and_reverse_lookups(self):
        for host, questions in [('drill.test', self.questions[:16:2]), ('ei.test', self.questions[16::2])]:
            for params in ({}, {'source_category': 'mock'}, {'type_group': 'small'}):
                for question in questions:
                    request = self.request(params, host)
                    with self.subTest(host=host, params=params, question=question.pk):
                        actual = ordinary_question_navigation(question, request)
                        for overdue, suffix in [(True, 'overdue_review_uuid'), (False, 'review_uuid')]:
                            self.assertEqual(actual['next_' + suffix], next_review_question(question, request, overdue=overdue))
                            self.assertEqual(actual['previous_' + suffix], previous_review_question(question, request, overdue=overdue))
