"""Private image delivery: body-free conditional requests must stay authorized."""
import hashlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Question, QuestionAsset, QuestionDocument
from .views import DrillAssetView


class DrillAssetDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('asset-reader')
        document = QuestionDocument.objects.create(
            source_id=91001, filename='assets.pdf', title='Assets',
            sha256='a' * 64, workspace='drill', page_count=1,
        )
        question = Question.objects.create(
            document=document, question_order=1, fingerprint='b' * 64,
        )
        cls.body = b'\x89PNG\r\n\x1a\n' + b'x' * (1024 * 1024)
        cls.asset = QuestionAsset.objects.create(
            source_id=91001, question=question, image_data=cls.body,
            sha256=hashlib.sha256(cls.body).hexdigest(), width=100, height=100,
        )
        cls.etag = f'"{cls.asset.sha256}"'

    def request(self, method='get', *, authenticated=True, workspace='drill', **headers):
        request = getattr(APIRequestFactory(), method)(
            f'/api/drill/assets/{self.asset.pk}/',
            HTTP_HOST=f'{workspace}.ehzsy.site', **headers,
        )
        if authenticated:
            force_authenticate(request, user=self.user)
        with CaptureQueriesContext(connection) as queries:
            response = DrillAssetView.as_view()(request, asset_id=self.asset.pk)
        return response, [query['sql'] for query in queries]

    def test_cold_get_reads_binary_once_and_preserves_headers(self):
        response, sql = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.body)
        self.assertEqual(len(sql), 1)
        self.assertIn('image_data', sql[0])
        self.assertEqual(response['ETag'], self.etag)
        self.assertEqual(response['Cache-Control'], 'private, max-age=31536000, immutable')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_matching_etag_skips_binary_including_weak_list_and_wildcard(self):
        for etag in (self.etag, f'"old", W/{self.etag}', '*'):
            with self.subTest(etag=etag):
                response, sql = self.request(HTTP_IF_NONE_MATCH=etag)
                self.assertEqual(response.status_code, 304)
                self.assertEqual(response.content, b'')
                self.assertEqual(len(sql), 1)
                self.assertNotIn('image_data', sql[0])
                self.assertEqual(response['ETag'], self.etag)

    def test_head_never_reads_binary(self):
        for headers in ({}, {'HTTP_IF_NONE_MATCH': '"stale"'}, {'HTTP_IF_NONE_MATCH': self.etag}):
            with self.subTest(headers=headers):
                response, sql = self.request('head', **headers)
                self.assertIn(response.status_code, (200, 304))
                self.assertEqual(response.content, b'')
                self.assertEqual(len(sql), 1)
                self.assertNotIn('"drill_questionasset"."image_data",', sql[0])
                if response.status_code == 200:
                    self.assertEqual(response['Content-Length'], str(len(self.body)))

    def test_stale_or_malformed_etag_returns_current_binary(self):
        for etag in ('"stale"', 'malformed'):
            with self.subTest(etag=etag):
                response, sql = self.request(HTTP_IF_NONE_MATCH=etag)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, self.body)
                self.assertEqual(len(sql), 2)
                self.assertNotIn('image_data', sql[0])
                self.assertIn('image_data', sql[1])

    def test_conditional_and_head_cannot_bypass_authentication_or_workspace(self):
        for method in ('get', 'head'):
            with self.subTest(method=method):
                response, _ = self.request(method, authenticated=False, HTTP_IF_NONE_MATCH='*')
                self.assertEqual(response.status_code, 403)
                response, sql = self.request(method, workspace='ei', HTTP_IF_NONE_MATCH=self.etag)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn('ETag', response)
                self.assertNotIn('"drill_questionasset"."image_data",', sql[0])

    def test_write_methods_are_rejected(self):
        response, _ = self.request('post')
        self.assertEqual(response.status_code, 405)

    def mutate_before_body(self, mutate):
        from . import views
        original = views.get_object_or_404
        calls = 0

        def fetch(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                mutate()
            return original(*args, **kwargs)

        with mock.patch.object(views, 'get_object_or_404', side_effect=fetch):
            return self.request(HTTP_IF_NONE_MATCH='"stale"')

    def test_rerender_between_metadata_and_body_keeps_etag_and_bytes_consistent(self):
        new_body = b'new image'
        new_sha = hashlib.sha256(new_body).hexdigest()
        response, _ = self.mutate_before_body(lambda: QuestionAsset.objects.filter(pk=self.asset.pk).update(
            image_data=new_body, sha256=new_sha, mime_type='image/jpeg',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, new_body)
        self.assertEqual(response['ETag'], f'"{new_sha}"')
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_workspace_reassignment_between_queries_denies_body(self):
        response, _ = self.mutate_before_body(lambda: QuestionDocument.objects.filter(
            pk=self.asset.question.document_id,
        ).update(workspace='ei'))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('ETag', response)
