"""A search generation pin expires a page, never a valid question UUID."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from unittest.mock import patch
from rest_framework.test import APIClient
from .models import Question, QuestionDocument, QuestionSearchState
from .search.index import process_queue, verify_workspace


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['drill.test', 'ei.test'],
                   DRILL_HOSTS={'drill.test'}, EI_HOSTS={'ei.test'},
                   DRILL_SEARCH_BACKEND='hybrid_v1')
class SearchNavigationRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('search-navigation-owner')
        book = QuestionDocument.objects.create(source_id=98601, workspace='drill',
            filename='navigation.pdf', title='微分题册', sha256='search-navigation', page_count=1,
            relation_type='selected_question_book')
        cls.items = [Question.objects.create(document=book, question_order=n,
            prompt_text='偏导数 微分', fingerprint=f'nav-search-{n}', is_practiceable=True)
            for n in range(3)]
        cls.cross_book = QuestionDocument.objects.create(source_id=98602, workspace='drill',
            filename='second.pdf', title='第二题册', sha256='nav-second', page_count=1,
            relation_type='selected_question_book')
        cls.cross_question = Question.objects.create(document=cls.cross_book, question_order=1,
            prompt_text='偏导数 微分', fingerprint='nav-cross-book', is_practiceable=True)
        ei_book = QuestionDocument.objects.create(source_id=98603, workspace='ei',
            filename='signals.pdf', title='信号题册', sha256='nav-signals', page_count=1)
        cls.ei_items = [Question.objects.create(document=ei_book, question_order=n,
            prompt_text='Fourier transform 偏导数', fingerprint=f'nav-ei-{n}', is_practiceable=True)
            for n in range(3)]
        process_queue(100, 30)
        assert verify_workspace('drill')['valid']
        assert verify_workspace('ei')['valid']

    def setUp(self):
        self.client = APIClient(HTTP_HOST='drill.test')
        self.client.force_authenticate(self.user)

    def test_stale_generation_rejects_pagination_but_not_valid_uuid_entry(self):
        result = self.client.get('/api/drill/questions/', {'q': '导数', 'search_version': '2'})
        self.assertEqual(result.status_code, 200, result.data)
        pin = result.data['search']['index_version']
        QuestionSearchState.objects.filter(workspace='drill').update(generation=999)
        params = {'q': '导数', 'search_version': '2', 'index_version': pin}
        stale = self.client.get('/api/drill/questions/', {**params, 'page': '2'})
        self.assertEqual(stale.status_code, 409)
        detail = self.client.get(f'/api/drill/questions/{self.items[0].uuid}/', params)
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['uuid'], str(self.items[0].uuid))
        self.assertEqual(detail.data['next_unattempted_question_uuid'], str(self.items[1].uuid))

    def test_unpinned_uuid_navigation_keeps_workspace_identity_and_readiness_checks(self):
        uuid = self.items[0].uuid
        self.assertEqual(self.client.get(f'/api/drill/questions/{uuid}/',
            HTTP_HOST='ei.test').status_code, 404)
        QuestionSearchState.objects.filter(workspace='drill').update(ready=False)
        self.assertEqual(self.client.get(f'/api/drill/questions/{uuid}/',
            {'q': '导数', 'index_version': 'stale'}).status_code, 503)
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(f'/api/drill/questions/{uuid}/').status_code, (401, 403))

    def test_narrow_join_matches_materialized_search_for_cross_book_selected_and_ei(self):
        from .search.service import membership
        navigation_keys = (
            'previous_question_uuid', 'next_question_uuid', 'sequential_next_question_uuid',
            'next_unattempted_question_uuid', 'previous_unattempted_question_uuid',
            'next_overdue_review_uuid', 'next_review_uuid',
            'previous_overdue_review_uuid', 'previous_review_uuid',
        )
        def materialized(*args, **kwargs):
            return membership(*args, **{**kwargs, 'materialize_candidates': True})
        cases = [('drill.test', self.items[-1], {'q': '偏导数', 'collection': 'selected'}, self.cross_question),
                 ('ei.test', self.ei_items[0], {'q': 'Fourrier'}, self.ei_items[1])]
        for host, question, params, next_question in cases:
            with self.subTest(host=host, params=params):
                path = f'/api/drill/questions/{question.uuid}/'
                joined = self.client.get(path, params, HTTP_HOST=host)
                with patch('drill.search.service.membership', side_effect=materialized):
                    original = self.client.get(path, params, HTTP_HOST=host)
                self.assertEqual(joined.status_code, 200, joined.data)
                self.assertEqual(original.status_code, 200, original.data)
                self.assertEqual({key: joined.data[key] for key in navigation_keys},
                                 {key: original.data[key] for key in navigation_keys})
                self.assertEqual(joined.data['sequential_next_question_uuid'], str(next_question.uuid))
                self.assertEqual(joined.data['next_unattempted_question_uuid'], str(next_question.uuid))
