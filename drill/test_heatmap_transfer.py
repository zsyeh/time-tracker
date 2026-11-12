"""Negotiated transfer compression must not change heatmap data or permissions."""
import gzip
import json
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from .models import Question, QuestionAttempt, QuestionDocument

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver','drill.test','ei.test'],
                   DRILL_HOSTS=['drill.test'], EI_HOSTS=['ei.test'])
class HeatmapTransferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a=get_user_model().objects.create_user('compression-a')
        cls.b=get_user_model().objects.create_user('compression-b')
        cls.questions={}
        for number,workspace in enumerate(['drill','ei'],1):
            doc=QuestionDocument.objects.create(source_id=number,workspace=workspace,
                filename='synthetic.pdf',title='Synthetic repeated collection title',
                sha256=str(number)*64,page_count=1)
            cls.questions[workspace]=Question.objects.create(document=doc,question_order=1,
                display_label='Synthetic repeated question label',source_category='past_exam',
                prompt_text='PRIVATE PROMPT NOT IN THE GRID',content_mode='text',fingerprint=str(number+2)*64)
            QuestionAttempt.objects.create(user=cls.a,question=cls.questions[workspace],result='correct',time_spent_seconds=60)

    def test_gzip_both_workspaces_is_byte_equivalent_after_decoding(self):
        self.client.force_login(self.a)
        for workspace in ['drill','ei']:
            with self.subTest(workspace=workspace):
                host=workspace+'.test';url='/api/drill/heatmap/?scope=all&mode=questions'
                plain=self.client.get(url,HTTP_HOST=host)
                zipped=self.client.get(url,HTTP_HOST=host,HTTP_ACCEPT_ENCODING='gzip, deflate, br')
                self.assertEqual(zipped.status_code,200)
                self.assertEqual(zipped['Content-Encoding'],'gzip')
                self.assertEqual(gzip.decompress(zipped.content),plain.content)
                self.assertLess(len(zipped.content),len(plain.content))
                self.assertEqual(int(zipped['Content-Length']),len(zipped.content))
                self.assertIn('Accept-Encoding',zipped['Vary']);self.assertIn('Cookie',zipped['Vary'])
                self.assertEqual(json.loads(gzip.decompress(zipped.content))['question_count'],1)
                self.assertNotIn(b'PRIVATE PROMPT',gzip.decompress(zipped.content))

    def test_without_negotiation_body_stays_uncompressed(self):
        self.client.force_login(self.a)
        response=self.client.get('/api/drill/heatmap/?scope=all')
        self.assertEqual(response.status_code,200);self.assertNotIn('Content-Encoding',response)
        self.assertEqual(response.json()['statistics']['attempted_question_count'],1)

    def test_compression_does_not_cross_account_or_workspace(self):
        self.client.force_login(self.b)
        response=self.client.get('/api/drill/heatmap/?scope=all',HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(json.loads(gzip.decompress(response.content))['statistics']['attempted_question_count'],0)
        self.client.force_login(self.a)
        response=self.client.get('/api/drill/heatmap/?collection=selected',HTTP_HOST='ei.test',HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response.status_code,404)
        response=self.client.get('/api/drill/heatmap/?scope=all',HTTP_X_LEARNING_USER_ID=str(self.b.pk),HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response.status_code,409)

    def test_anonymous_compressed_request_is_still_rejected(self):
        self.assertIn(self.client.get('/api/drill/heatmap/?scope=all',HTTP_ACCEPT_ENCODING='gzip').status_code,[401,403])
