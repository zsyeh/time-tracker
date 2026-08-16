import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionTopic


TEST_PNG = b'\x89PNG\r\n\x1a\nquestion-image'


@override_settings(SECURE_SSL_REDIRECT=False)
class DrillApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user('drill-alice', password='password')
        self.bob = User.objects.create_user('drill-bob', password='password')
        self.document = QuestionDocument.objects.create(
            source_id=1,
            filename='limits.pdf',
            title='Limits',
            sha256='d' * 64,
            page_count=10,
        )
        self.topic = QuestionTopic.objects.create(
            source_id=1,
            document=self.document,
            title='Limits',
            level=2,
            sort_order=1,
        )
        self.other_topic = QuestionTopic.objects.create(
            source_id=2,
            document=self.document,
            title='Continuity',
            level=2,
            sort_order=2,
        )
        self.question = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=1,
            source_label='2024数一',
            prompt_text='PRIVATE QUESTION BODY',
            content_mode='mixed',
            fingerprint='a' * 64,
            is_past_exam=True,
            exam_year=2024,
            exam_variant='数一',
        )
        self.similar = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=2,
            source_label='2020数二',
            prompt_text='Similar',
            content_mode='text',
            fingerprint='b' * 64,
            is_past_exam=True,
            exam_year=2020,
            exam_variant='数二',
        )
        self.unrelated = Question.objects.create(
            document=self.document,
            topic=self.other_topic,
            similarity_topic=self.other_topic,
            question_order=3,
            source_label='Exercise',
            prompt_text='Unrelated',
            content_mode='text',
            fingerprint='c' * 64,
        )
        self.asset = QuestionAsset.objects.create(
            source_id=1,
            question=self.question,
            sha256=hashlib.sha256(TEST_PNG).hexdigest(),
            image_data=TEST_PNG,
            width=100,
            height=30,
        )

    def test_question_bank_requires_auth_and_list_is_lightweight(self):
        self.assertEqual(self.client.get('/api/drill/questions/').status_code, 403)
        self.client.force_login(self.alice)
        response = self.client.get('/api/drill/questions/')
        self.assertEqual(response.status_code, 200)
        first = response.json()['results'][0]
        self.assertNotIn('prompt_text', first)
        self.assertNotIn('assets', first)

    def test_attempt_frequency_and_heatmap_are_private_per_user(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='done')
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct')
        QuestionAttempt.objects.create(user=self.bob, question=self.similar, result='review')
        self.client.force_login(self.alice)
        groups = self.client.get('/api/drill/heatmap/').json()['groups']
        cells = {cell['uuid']: cell for group in groups for cell in group['questions']}
        self.assertEqual(cells[str(self.question.uuid)]['attempt_count'], 2)
        self.assertEqual(cells[str(self.similar.uuid)]['attempt_count'], 0)
        created = self.client.post(
            f'/api/drill/questions/{self.similar.uuid}/attempts/',
            {'result': 'review'},
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['attempt_count'], 1)

    def test_similar_questions_use_indexed_topic(self):
        self.client.force_login(self.alice)
        response = self.client.get(f'/api/drill/questions/{self.question.uuid}/similar/')
        ids = [row['uuid'] for row in response.json()['results']]
        self.assertIn(str(self.similar.uuid), ids)
        self.assertNotIn(str(self.unrelated.uuid), ids)

    def test_detail_and_asset_are_authenticated(self):
        self.client.force_login(self.alice)
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['prompt_text'], 'PRIVATE QUESTION BODY')
        asset = self.client.get(f'/api/drill/assets/{self.asset.pk}/')
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.content, TEST_PNG)
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/drill/assets/{self.asset.pk}/').status_code, 403)

    def test_progress_does_not_include_another_users_attempts(self):
        QuestionAttempt.objects.create(user=self.bob, question=self.question, result='correct')
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get('/api/drill/progress/').json()['total_attempts'], 0)


@override_settings(SECURE_SSL_REDIRECT=False)
class QuestionBankImportTests(TestCase):
    def test_normalized_import_is_idempotent_and_preserves_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / 'assets' / 'sourcehash'
            assets.mkdir(parents=True)
            (assets / 'q1.png').write_bytes(TEST_PNG)
            rows = {
                'documents': [{
                    'id': 1, 'filename': '真题.pdf', 'sha256': 'f' * 64,
                    'page_count': 3, 'parser_strategy': 'test', 'relation_type': None,
                }],
                'nodes': [{
                    'id': 1, 'document_id': 1, 'parent_id': None, 'title': '极限',
                    'normalized_title': '极限', 'level': 2, 'sort_order': 1,
                }],
                'questions': [{
                    'id': 1, 'document_id': 1, 'knowledge_node_id': 1,
                    'question_order': 1, 'source_label': '2023数二',
                    'raw_text': 'Question', 'latex_text': None, 'content_mode': 'mixed',
                    'confidence': 0.9, 'fingerprint': '1' * 64,
                }],
                'assets': [{
                    'id': 1, 'question_id': 1, 'position': 0,
                    'asset_type': 'question_crop', 'file_path': r'C:\out\sourcehash\q1.png',
                    'sha256': hashlib.sha256(TEST_PNG).hexdigest(), 'width': 100, 'height': 30,
                }],
            }
            for name, values in rows.items():
                (root / f'{name}.jsonl').write_text(
                    ''.join(f'{json.dumps(value, ensure_ascii=False)}\n' for value in values),
                    encoding='utf-8',
                )
            call_command('import_question_bank', root, assets_root=root / 'assets')
            call_command('import_question_bank', root, assets_root=root / 'assets')
        self.assertEqual(Question.objects.count(), 1)
        self.assertEqual(QuestionAsset.objects.count(), 1)
        question = Question.objects.get()
        self.assertTrue(question.is_past_exam)
        self.assertEqual(question.exam_year, 2023)
        self.assertEqual(bytes(QuestionAsset.objects.get().image_data), TEST_PNG)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    DEBUG=False,
    ALLOWED_HOSTS=['timer.ehzsy.site', 'drill.ehzsy.site'],
    DRILL_HOSTS={'drill.ehzsy.site'},
)
class DrillHostRoutingTests(TestCase):
    def test_drill_root_uses_independent_frontend_and_timer_has_no_drill_route(self):
        user = get_user_model().objects.create_user('host-user', password='password')
        self.client.force_login(user)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            timer = root / 'timer'
            drill = root / 'drill'
            timer.mkdir()
            drill.mkdir()
            (timer / 'index.html').write_text('<html>TIMER FRONTEND</html>', encoding='utf-8')
            (drill / 'index.html').write_text('<html>DRILL FRONTEND</html>', encoding='utf-8')
            with self.settings(FRONTEND_DIST=timer, DRILL_FRONTEND_DIST=drill):
                drill_response = self.client.get('/', HTTP_HOST='drill.ehzsy.site')
                timer_response = self.client.get('/', HTTP_HOST='timer.ehzsy.site')
                blocked = self.client.get('/practice', HTTP_HOST='timer.ehzsy.site')
        self.assertContains(drill_response, 'DRILL FRONTEND')
        self.assertContains(timer_response, 'TIMER FRONTEND')
        self.assertEqual(blocked.status_code, 404)
