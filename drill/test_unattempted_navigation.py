"""Unattempted navigation respects current latest state and the originating list."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from .models import Question, QuestionAttempt, QuestionDocument, QuestionTopic, QuestionUserState
from .views import list_context_navigation, navigation_queryset, navigation_with_latest_result, unattempted_question_navigation


@override_settings(DRILL_HOSTS={'drill.test'}, EI_HOSTS={'ei.test'}, ALLOWED_HOSTS=['drill.test', 'ei.test'])
class UnattemptedNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('unattempted-owner')
        cls.other = get_user_model().objects.create_user('unattempted-other')
        cls.questions = []
        for book in range(3):
            document = QuestionDocument.objects.create(
                source_id=81000 + book, filename=f'{book}.pdf', title=f'Book {book}',
                workspace='ei' if book == 2 else 'drill', sha256=str(book) * 64,
                page_count=1, relation_type='selected_question_book',
            )
            for index in range(5):
                cls.questions.append(Question.objects.create(
                    document=document, question_order=index, fingerprint=f'{book}-{index}',
                    source_category='past_exam', is_practiceable=True,
                    question_type='single_choice' if index % 2 else 'solution',
                    prompt_text='needle' if index % 2 else 'other',
                ))
        # Only latest reset counts as unattempted. Another user's work is irrelevant.
        QuestionAttempt.objects.create(user=cls.user, question=cls.questions[1], result='correct')
        QuestionAttempt.objects.create(user=cls.user, question=cls.questions[1], result='reset')
        QuestionAttempt.objects.create(user=cls.user, question=cls.questions[2], result='review')
        QuestionAttempt.objects.create(user=cls.user, question=cls.questions[3], result='reset')
        QuestionAttempt.objects.create(user=cls.user, question=cls.questions[3], result='correct')
        for question in cls.questions:
            QuestionAttempt.objects.create(user=cls.other, question=question, result='correct')

    def request(self, params=None, host='drill.test'):
        request = Request(APIRequestFactory().get('/', params or {}, HTTP_HOST=host))
        request._user = self.user
        return request

    def assert_destinations(self, current, expected_next, expected_previous, params=None, host='drill.test', bulk=False):
        request = self.request(params, host)
        rows = list(navigation_with_latest_result(navigation_queryset(current, request), self.user).values_list(
            'pk', 'uuid', 'next_latest_result',
        )) if bulk else None
        value = unattempted_question_navigation(current, request, rows)
        self.assertEqual(value['next_unattempted_question_uuid'], str(expected_next.uuid) if expected_next else None)
        self.assertEqual(value['previous_unattempted_question_uuid'], str(expected_previous.uuid) if expected_previous else None)

    def test_latest_reset_review_correct_and_other_users(self):
        for bulk in (False, True):
            with self.subTest(bulk=bulk):
                self.assert_destinations(self.questions[0], self.questions[1], self.questions[4], bulk=bulk)
                self.assert_destinations(self.questions[1], self.questions[4], self.questions[0], bulk=bulk)
                self.assert_destinations(self.questions[4], self.questions[0], self.questions[1], bulk=bulk)

    def test_filters_and_workspace_do_not_leak(self):
        self.assert_destinations(self.questions[0], self.questions[1], self.questions[1], {'type_group':'small'})
        self.assert_destinations(self.questions[0], self.questions[1], self.questions[1], {'q':'needle'})
        self.assert_destinations(self.questions[0], self.questions[5], self.questions[9], {'document':self.questions[5].document_id})
        self.assert_destinations(self.questions[10], self.questions[11], self.questions[14], host='ei.test')
        self.assert_destinations(self.questions[0], None, None, {'q':'not present'})

    def test_single_candidate_never_links_to_itself(self):
        current = self.questions[0]
        for question in (self.questions[1], self.questions[4]):
            QuestionAttempt.objects.create(user=self.user, question=question, result='correct')
        for bulk in (False, True):
            self.assert_destinations(current, None, None, bulk=bulk)

    def test_selected_bulk_and_range_are_equivalent_across_books(self):
        for current in self.questions[:10]:
            request = self.request({'collection':'selected'})
            rows = list(navigation_with_latest_result(navigation_queryset(current, request), self.user).values_list('pk','uuid','next_latest_result'))
            self.assertEqual(unattempted_question_navigation(current, request), unattempted_question_navigation(current, request, rows))
        self.assert_destinations(self.questions[9], self.questions[0], self.questions[8], {'collection':'selected'}, bulk=True)

    def test_favorites_wrap_only_inside_owners_collection(self):
        for question in (self.questions[0], self.questions[1], self.questions[2], self.questions[10]):
            QuestionUserState.objects.create(user=self.user, question=question, is_favorite=True)
        QuestionUserState.objects.create(user=self.other, question=self.questions[4], is_favorite=True)
        request = self.request({'from':'collection','collection':'favorite'})
        for current, other in ((self.questions[0],self.questions[1]), (self.questions[1],self.questions[0])):
            value = list_context_navigation(request,current)
            self.assertEqual(value['next_unattempted_question_uuid'],str(other.uuid))
            self.assertEqual(value['previous_unattempted_question_uuid'],str(other.uuid))
        QuestionUserState.objects.filter(user=self.user,question=self.questions[1]).update(is_favorite=False)
        value=list_context_navigation(request,self.questions[0])
        self.assertIsNone(value['next_unattempted_question_uuid'])
        self.assertIsNone(value['previous_unattempted_question_uuid'])

    def test_history_attempts_wrap_but_do_not_pull_in_unlisted_unattempted(self):
        # History contains q1(reset), q2(review), q3(correct); q0 and q4 are unlisted.
        QuestionAttempt.objects.create(user=self.user,question=self.questions[3],result='reset')
        request=self.request({'from':'insight','insight_list':'attempts','insight_return':'/insight'})
        for current, other in ((self.questions[1],self.questions[3]),(self.questions[3],self.questions[1])):
            value=list_context_navigation(request,current)
            self.assertEqual(value['next_unattempted_question_uuid'],str(other.uuid))
            self.assertEqual(value['previous_unattempted_question_uuid'],str(other.uuid))

    def test_undo_reveals_previous_state_and_topic_filter_is_preserved(self):
        reset = QuestionAttempt.objects.filter(user=self.user,question=self.questions[1],result='reset').get()
        reset.delete()  # Undo removes latest reset; the preceding correct becomes current.
        self.assert_destinations(self.questions[0],self.questions[4],self.questions[4])
        topic=QuestionTopic.objects.create(source_id=81999,document=self.questions[0].document,title='Scope topic',level=1,sort_order=1)
        Question.objects.filter(pk__in=[self.questions[0].pk,self.questions[4].pk]).update(similarity_topic=topic)
        self.assert_destinations(self.questions[0],self.questions[4],self.questions[4],{'topic':topic.pk})
        self.assert_destinations(self.questions[4],self.questions[0],self.questions[0],{'topic':topic.pk})

    def test_selected_reuses_loaded_rows_and_ordinary_uses_two_bounded_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        current = self.questions[0]
        request = self.request({'collection': 'selected'})
        rows = list(navigation_with_latest_result(navigation_queryset(current, request), self.user).values_list(
            'pk', 'uuid', 'next_latest_result'))
        with self.assertNumQueries(0):
            unattempted_question_navigation(current, request, rows)
        with CaptureQueriesContext(connection) as captured:
            unattempted_question_navigation(current, self.request())
        self.assertEqual(len(captured), 2)
        self.assertTrue(all('LIMIT 1' in item['sql'] for item in captured))
