import hashlib
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import pymupdf
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from .cleaning import classify_source, clean_document_title, clean_topic_title
from .asset_rerender import (
    CropLocation,
    FormulaAwareCropAdjuster,
    LegacyCropLocator,
    render_blank_crop,
    render_pdf_crop,
)
from .models import (
    DrillLoginHandoff,
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionDocument,
    QuestionTopic,
)
from .pdf_import import parse_question_pdf


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
            author='Source Author',
            attribution='Question bank collected by cxy.',
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
            source_category='past_exam',
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
            source_category='past_exam',
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
        self.practice = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=4,
            source_label='26版660第1题',
            prompt_text='Practice',
            content_mode='text',
            fingerprint='e' * 64,
            source_category='workbook',
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

    def test_question_state_can_be_changed_reset_and_undone(self):
        self.client.force_login(self.alice)
        endpoint = f'/api/drill/questions/{self.question.uuid}/attempts/'
        mastered = self.client.post(
            endpoint, {'result': 'correct'}, content_type='application/json',
        ).json()
        self.assertEqual(mastered['state'], 'mastered')
        review = self.client.post(
            endpoint, {'result': 'review'}, content_type='application/json',
        ).json()
        self.assertEqual(review['state'], 'review')
        reset = self.client.post(
            endpoint, {'result': 'reset'}, content_type='application/json',
        ).json()
        self.assertEqual(reset['state'], 'unattempted')
        self.assertEqual(reset['attempt_count'], 2)
        undone = self.client.delete(endpoint).json()
        self.assertEqual(undone['state'], 'review')
        self.assertTrue(undone['can_undo'])

    def test_unattempted_filter_uses_current_state_after_reset(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct')
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='reset')
        self.client.force_login(self.alice)
        rows = self.client.get('/api/drill/questions/?unattempted=1').json()['results']
        self.assertIn(str(self.question.uuid), [row['uuid'] for row in rows])

    def test_similar_questions_require_explicit_source_kind(self):
        self.client.force_login(self.alice)
        endpoint = f'/api/drill/questions/{self.question.uuid}/similar/'
        summary = self.client.get(endpoint).json()
        self.assertEqual(summary['results'], [])
        self.assertEqual(summary['counts'], {'past_exam': 1, 'practice': 1})
        response = self.client.get(f'{endpoint}?kind=past_exam')
        ids = [row['uuid'] for row in response.json()['results']]
        self.assertIn(str(self.similar.uuid), ids)
        self.assertNotIn(str(self.practice.uuid), ids)
        self.assertNotIn(str(self.unrelated.uuid), ids)
        practice_ids = [
            row['uuid']
            for row in self.client.get(f'{endpoint}?kind=practice').json()['results']
        ]
        self.assertIn(str(self.practice.uuid), practice_ids)
        self.assertNotIn(str(self.similar.uuid), practice_ids)

    def test_detail_and_asset_are_authenticated(self):
        self.client.force_login(self.alice)
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['prompt_text'], 'PRIVATE QUESTION BODY')
        self.assertEqual(detail.json()['formula_source'], 'original_pdf_crop')
        self.assertEqual(detail.json()['document_author'], 'Source Author')
        self.assertEqual(detail.json()['document_attribution'], 'Question bank collected by cxy.')
        self.assertEqual(detail.json()['next_question_uuid'], str(self.similar.uuid))
        self.assertEqual(
            detail.json()['assets'][0]['url'],
            f'/api/drill/assets/{self.asset.pk}/?v={self.asset.sha256[:16]}',
        )
        asset = self.client.get(f'/api/drill/assets/{self.asset.pk}/')
        self.assertEqual(asset.status_code, 200)
        self.assertEqual(asset.content, TEST_PNG)
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/drill/assets/{self.asset.pk}/').status_code, 403)

    def test_last_practiceable_question_has_no_next_question(self):
        self.client.force_login(self.alice)
        detail = self.client.get(f'/api/drill/questions/{self.practice.uuid}/')
        self.assertIsNone(detail.json()['next_question_uuid'])

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
        self.assertEqual(question.source_category, 'past_exam')
        self.assertEqual(question.exam_year, 2023)
        self.assertEqual(bytes(QuestionAsset.objects.get().image_data), TEST_PNG)


class QuestionBankCleaningTests(TestCase):
    def test_topic_leaders_and_document_wrappers_are_cleaned(self):
        self.assertEqual(
            clean_topic_title('11. 定积分应用 >> ................................. 66'),
            '定积分应用',
        )
        self.assertEqual(clean_document_title('【紧凑】多元微分.pdf'), '多元微分')
        self.assertEqual(clean_document_title('【A4 紧凑】一元微分做题本.pdf'), '一元微分')
        self.assertEqual(
            clean_document_title('线代1000题打印版（密集不留空）(1).pdf'),
            '线性代数',
        )

    def test_source_types_do_not_mix_past_mock_and_workbook(self):
        self.assertEqual(classify_source('(3) 2019 数二').category, 'past_exam')
        self.assertEqual(classify_source('(2) 2022 数二（改编）').category, 'adapted_exam')
        self.assertEqual(classify_source('25 李永乐六套数一二三第三套').category, 'mock_exam')
        self.assertEqual(classify_source('26版660数二第509题').category, 'workbook')
        self.assertEqual(classify_source('北京市2008年竞赛题').category, 'competition')

    def test_source_display_keeps_existing_emoji(self):
        classification = classify_source('🐙 a)2024 数一')
        self.assertEqual(classification.category, 'past_exam')
        self.assertIn('🐙', classification.display_label)


class CxyDifferentiationPdfTests(SimpleTestCase):
    def test_bookmarks_author_and_question_labels_are_preserved(self):
        parsed = parse_question_pdf(Path(__file__).with_name('【A4 紧凑】一元微分做题本.pdf'))
        self.assertEqual(parsed.title, '一元微分')
        self.assertEqual(parsed.author, '本本')
        self.assertIn('cxy', parsed.attribution)
        self.assertEqual(len(parsed.topics), 102)
        self.assertEqual(len(parsed.questions), 675)
        self.assertEqual(parsed.questions[0].source_label, 'a)1993 数二;880 第二章基础选择9')


class QuestionAssetRerenderTests(SimpleTestCase):
    def test_legacy_crop_can_be_located_and_rendered_at_180_dpi(self):
        pdf = pymupdf.open()
        page = pdf.new_page(width=200, height=300)
        page.insert_text((20, 94), 'Integral and derivative question 42')
        page.draw_line((20, 105), (170, 105))
        source = page.get_pixmap(
            matrix=pymupdf.Matrix(1.5, 1.5),
            clip=pymupdf.Rect(0, 70, 200, 125),
            colorspace=pymupdf.csRGB,
            alpha=False,
        ).tobytes('png')

        location, _cursor = LegacyCropLocator(pdf).locate(source)
        rendered, width, height = render_pdf_crop(pdf, location, 180)

        self.assertEqual(location.page_index, 0)
        self.assertAlmostEqual(location.y0, 70, delta=1)
        self.assertEqual(width, 500)
        self.assertGreater(height, 130)
        self.assertTrue(rendered.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_blank_legacy_crop_can_be_scaled_without_pdf_coordinates(self):
        source = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 90, 30), False)
        source.clear_with(255)
        pdf = pymupdf.open()
        pdf.new_page(width=60, height=60)

        location, _cursor = LegacyCropLocator(pdf).locate(source.tobytes('png'))
        rendered, width, height = render_blank_crop(150, 50, 180)

        self.assertTrue(location.is_blank)
        self.assertEqual((width, height), (150, 50))
        self.assertTrue(rendered.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_formula_aware_bounds_include_matrix_above_question_anchor(self):
        pdf = pymupdf.open()
        page = pdf.new_page(width=240, height=300)
        page.insert_text((20, 110), '4. Matrix question', fontsize=11)
        page.insert_textbox(
            pymupdf.Rect(120, 65, 220, 135),
            '[ a  b ]\n[ c  d ]\n[ e  f ]',
            fontsize=11,
        )
        page.draw_line((115, 58), (115, 137))
        page.insert_text((20, 170), '5. Next question', fontsize=11)

        adjusted = FormulaAwareCropAdjuster(pdf).adjust(
            CropLocation(0, 0, 100, 240, 170, 1.0),
        )

        self.assertLess(adjusted.y0, 58)
        self.assertLess(adjusted.y1, 170)
        self.assertGreater(adjusted.y1, 145)


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


@override_settings(
    SECURE_SSL_REDIRECT=False,
    DEBUG=False,
    ALLOWED_HOSTS=['timer.ehzsy.site', 'drill.ehzsy.site'],
    DRILL_HOSTS={'drill.ehzsy.site'},
    DRILL_ORIGIN='https://drill.ehzsy.site',
    DRILL_AUTH_HOST='timer.ehzsy.site',
    DRILL_AUTH_ORIGIN='https://timer.ehzsy.site',
)
class DrillPasskeyHandoffTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('handoff-user', password='password')

    def test_anonymous_drill_page_uses_timer_login_origin(self):
        response = self.client.get(
            '/practice?document=2',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(
            'https://timer.ehzsy.site/drill-auth/start?',
        ))
        self.assertIn('next=%2Fpractice%3Fdocument%3D2', response.url)

    def test_authenticated_timer_issues_hashed_one_time_login_for_drill(self):
        timer = Client()
        timer.force_login(self.user)
        start = timer.get(
            '/drill-auth/start?next=/heatmap',
            HTTP_HOST='timer.ehzsy.site',
            secure=True,
        )
        self.assertEqual(start.status_code, 302)
        self.assertTrue(start.url.startswith(
            'https://drill.ehzsy.site/drill-auth/complete/',
        ))
        raw_token = urlsplit(start.url).path.rsplit('/', 1)[1]
        handoff = DrillLoginHandoff.objects.get()
        self.assertNotEqual(handoff.token_digest, raw_token)
        self.assertEqual(handoff.token_digest, DrillLoginHandoff.digest(raw_token))

        drill = Client()
        completed = drill.get(
            f'/drill-auth/complete/{raw_token}',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertRedirects(
            completed,
            '/heatmap',
            fetch_redirect_response=False,
        )
        self.assertEqual(int(drill.session['_auth_user_id']), self.user.pk)
        self.assertFalse(DrillLoginHandoff.objects.exists())
        replay = Client().get(
            f'/drill-auth/complete/{raw_token}',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertEqual(replay.status_code, 404)

    def test_external_return_url_is_replaced_with_practice(self):
        timer = Client()
        timer.force_login(self.user)
        response = timer.get(
            '/drill-auth/start?next=https://evil.example/steal',
            HTTP_HOST='timer.ehzsy.site',
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DrillLoginHandoff.objects.get().target_path, '/practice')
