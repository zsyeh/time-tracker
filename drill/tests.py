import hashlib
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import pymupdf
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .cleaning import (
    classify_record_kind,
    classify_source,
    classify_source_with_context,
    clean_document_title,
    clean_topic_title,
    is_question_reference_topic,
)
from .asset_rerender import (
    CropLocation,
    FormulaAwareCropAdjuster,
    LegacyCropLocator,
    crop_pixmap_rows,
    reframe_crop_image,
    render_blank_crop,
    render_pdf_crop,
    trailing_edge_fragment_start,
)
from .models import (
    DrillLoginHandoff,
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionDocument,
    QuestionMarker,
    QuestionTopic,
    QuestionUserState,
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

    @override_settings(
        ALLOWED_HOSTS=['testserver', 'ei.ehzsy.site'],
        EI_HOSTS={'ei.ehzsy.site'},
    )
    def test_ei_host_has_an_isolated_question_workspace(self):
        ei_document = QuestionDocument.objects.create(
            source_id=892000000,
            workspace='ei',
            filename='892.md',
            title='892 Electronic Information',
            sha256='8' * 64,
            page_count=0,
        )
        ei_topic = QuestionTopic.objects.create(
            source_id=892000001,
            document=ei_document,
            title='Circuit Fundamentals',
            level=1,
            sort_order=1,
        )
        ei_question = Question.objects.create(
            document=ei_document,
            topic=ei_topic,
            similarity_topic=ei_topic,
            question_order=1,
            source_label='CIR-01-01-P01',
            prompt_text='EI ONLY',
            content_mode='markdown',
            fingerprint='8' * 64,
        )
        self.client.force_login(self.alice)

        drill_results = self.client.get('/api/drill/questions/').json()['results']
        ei_results = self.client.get(
            '/api/drill/questions/', HTTP_HOST='ei.ehzsy.site',
        ).json()['results']

        self.assertNotIn(str(ei_question.uuid), [row['uuid'] for row in drill_results])
        self.assertEqual([row['uuid'] for row in ei_results], [str(ei_question.uuid)])
        blocked = self.client.get(
            f'/api/drill/questions/{self.question.uuid}/',
            HTTP_HOST='ei.ehzsy.site',
        )
        self.assertEqual(blocked.status_code, 404)

    def test_agent_markdown_solution_is_detail_only(self):
        self.question.answer_markdown = '## Solution\n\n$\\int_0^1 x\\,dx=\\frac12$'
        self.question.answer_source = 'codex-reviewed'
        self.question.answer_confidence = 0.98
        self.question.save(update_fields=(
            'answer_markdown', 'answer_source', 'answer_confidence',
        ))
        self.client.force_login(self.alice)

        listing = self.client.get('/api/drill/questions/').json()['results']
        self.assertNotIn('answer_markdown', listing[0])
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertEqual(detail['answer_markdown'], self.question.answer_markdown)
        self.assertEqual(detail['answer_source'], 'codex-reviewed')
        self.assertEqual(detail['answer_confidence'], 0.98)

    def test_generate_paper_respects_filters_and_is_not_persisted(self):
        self.client.force_login(self.alice)
        before = Question.objects.count()
        response = self.client.post(
            '/api/drill/papers/generate/',
            {'count': 10, 'document': self.document.pk, 'source_category': 'past_exam'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['questions']), 2)
        self.assertTrue(all(item['source_category'] == 'past_exam' for item in payload['questions']))
        self.assertEqual(Question.objects.count(), before)

    def test_generate_unattempted_paper_is_user_scoped(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct')
        QuestionAttempt.objects.create(user=self.bob, question=self.similar, result='correct')
        self.client.force_login(self.alice)
        response = self.client.post(
            '/api/drill/papers/generate/',
            {'count': 10, 'source_category': 'past_exam', 'unattempted': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['uuid'] for item in response.json()['questions']], [str(self.similar.uuid)])

    def test_heatmap_supports_scopes_without_leaking_prompt(self):
        self.client.force_login(self.alice)
        mock = self.client.get('/api/drill/heatmap/?scope=mock_exam')
        self.assertEqual(mock.status_code, 200)
        self.assertEqual(mock.json()['question_count'], 0)
        self.assertEqual(mock.json()['topic_count'], 0)
        all_questions = self.client.get('/api/drill/heatmap/?scope=all').json()
        self.assertEqual(all_questions['question_count'], 4)
        self.assertNotIn('prompt_text', all_questions['groups'][0]['questions'][0])
        all_topics = self.client.get('/api/drill/heatmap/?scope=all&mode=topics').json()
        self.assertEqual(all_topics['question_count'], 4)
        self.assertEqual(all_topics['topic_count'], 2)
        topic_cells = all_topics['groups'][0]['topics']
        limits = next(item for item in topic_cells if item['topic'] == 'Limits')
        self.assertEqual(limits['question_count'], 3)
        self.assertEqual(limits['attempted_question_count'], 0)
        self.assertEqual(limits['coverage_percent'], 0)
        self.assertEqual(limits['intensity'], 0)
        self.assertEqual(limits['state'], 'unattempted')
        self.assertNotIn('prompt_text', limits)

    def test_activity_heatmap_is_user_and_workspace_scoped(self):
        ei_document = QuestionDocument.objects.create(
            source_id=99,
            workspace='ei',
            filename='ei.md',
            title='Signals',
            sha256='9' * 64,
            page_count=1,
        )
        ei_topic = QuestionTopic.objects.create(
            source_id=99,
            document=ei_document,
            title='Signals',
            level=1,
            sort_order=1,
        )
        ei_question = Question.objects.create(
            document=ei_document,
            topic=ei_topic,
            similarity_topic=ei_topic,
            question_order=1,
            source_label='EI 1',
            prompt_text='Private EI question',
            content_mode='text',
            fingerprint='9' * 64,
        )
        now = timezone.now()
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='done', created_at=now)
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct', created_at=now)
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='reset', created_at=now)
        QuestionAttempt.objects.create(user=self.bob, question=self.similar, result='review', created_at=now)
        QuestionAttempt.objects.create(user=self.alice, question=ei_question, result='done', created_at=now)

        self.client.force_login(self.alice)
        response = self.client.get('/api/drill/heatmap/activity/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        today = timezone.localdate().isoformat()
        today_cell = next(day for day in payload['overall']['days'] if day['date'] == today)
        self.assertEqual(payload['overall']['total_attempts'], 2)
        self.assertEqual(payload['overall']['active_days'], 1)
        self.assertEqual(today_cell['count'], 2)
        self.assertEqual(today_cell['level'], 2)
        self.assertEqual(payload['start_date'], f'{timezone.localdate().year}-07-20')
        self.assertEqual(payload['end_date'], f'{timezone.localdate().year}-12-19')
        self.assertEqual(len(payload['overall']['days']), 153)
        self.assertEqual(len(payload['books']), 1)
        self.assertEqual(payload['books'][0]['document'], 'Limits')
        self.assertEqual(payload['books'][0]['total_attempts'], 2)

        ei_response = self.client.get('/api/drill/heatmap/activity/', HTTP_HOST='ei.ehzsy.site')
        self.assertEqual(ei_response.status_code, 200)
        self.assertEqual(ei_response.json()['overall']['total_attempts'], 1)
        self.assertEqual(ei_response.json()['books'][0]['document'], 'Signals')

    def test_detail_navigation_respects_filter_context(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            f'/api/drill/questions/{self.question.uuid}/?topic={self.topic.pk}&source_category=past_exam',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload['previous_question_uuid'])
        self.assertEqual(payload['next_question_uuid'], str(self.similar.uuid))

    def test_detail_navigation_respects_search_and_unattempted_context(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.similar, result='correct')
        self.client.force_login(self.alice)
        response = self.client.get(
            f'/api/drill/questions/{self.question.uuid}/?q=2024&unattempted=1',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload['previous_question_uuid'])
        self.assertIsNone(payload['next_question_uuid'])

    def test_attempt_metadata_is_optional_and_user_scoped(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            f'/api/drill/questions/{self.question.uuid}/attempts/',
            {'result': 'review', 'confidence': 75, 'note': '定义域边界需要复查'},
        )
        self.assertEqual(response.status_code, 201)
        attempt = QuestionAttempt.objects.get(user=self.alice, question=self.question)
        self.assertEqual(attempt.confidence, 75)
        self.assertEqual(attempt.note, '定义域边界需要复查')
        self.assertEqual(response.json()['confidence'], 75)
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertEqual(detail['confidence'], 75)
        self.assertEqual(detail['note'], '定义域边界需要复查')

    def test_note_favorite_and_review_later_are_private_and_do_not_create_attempts(self):
        endpoint = f'/api/drill/questions/{self.question.uuid}/state/'
        self.client.force_login(self.alice)
        response = self.client.post(
            endpoint,
            {'note': 'Check the boundary.', 'is_favorite': True, 'review_later': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuestionAttempt.objects.filter(user=self.alice).count(), 0)
        state = QuestionUserState.objects.get(user=self.alice, question=self.question)
        self.assertTrue(state.is_favorite)
        self.assertTrue(state.review_later)
        self.assertEqual(state.note, 'Check the boundary.')
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertTrue(detail['is_favorite'])
        self.assertTrue(detail['review_later'])
        self.assertEqual(detail['note'], 'Check the boundary.')

        favorites = self.client.get('/api/drill/collections/?kind=favorite').json()
        queued = self.client.get('/api/drill/collections/?kind=review_later').json()
        self.assertEqual([row['uuid'] for row in favorites['results']], [str(self.question.uuid)])
        self.assertEqual([row['uuid'] for row in queued['results']], [str(self.question.uuid)])

        self.client.force_login(self.bob)
        self.assertEqual(self.client.get('/api/drill/collections/?kind=favorite').json()['count'], 0)
        other_detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertFalse(other_detail['is_favorite'])
        self.assertEqual(other_detail['note'], '')

    def test_feel_and_insight_are_user_scoped(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct')
        QuestionAttempt.objects.create(user=self.bob, question=self.similar, result='review')
        QuestionUserState.objects.create(user=self.alice, question=self.question, note='Recent note')
        self.client.force_login(self.alice)
        feel = self.client.get('/api/drill/feel/').json()['books'][0]
        self.assertEqual(feel['feel_score'], 0)
        self.assertEqual(feel['recent_attempts'], 1)
        insight = self.client.get('/api/drill/insight/').json()
        self.assertEqual(len(insight['recent_questions']), 1)
        self.assertEqual(insight['recent_questions'][0]['uuid'], str(self.question.uuid))
        self.assertEqual(insight['recent_notes'][0]['note'], 'Recent note')

    def test_multiple_learning_markers_coexist_with_state_and_are_private(self):
        marker_url = f'/api/drill/questions/{self.question.uuid}/markers/'
        self.client.force_login(self.alice)
        response = self.client.post(
            marker_url,
            {'codes': ['overconfident', 'forgotten']},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['markers'], ['overconfident', 'forgotten'])
        self.client.post(
            f'/api/drill/questions/{self.question.uuid}/attempts/',
            {'result': 'correct'},
            content_type='application/json',
        )
        detail = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertEqual(detail['state'], 'mastered')
        self.assertEqual(detail['markers'], ['overconfident', 'forgotten'])

        filtered = self.client.get('/api/drill/questions/?marker=forgotten').json()['results']
        self.assertEqual([row['uuid'] for row in filtered], [str(self.question.uuid)])
        stats = {
            row['code']: row['count']
            for row in self.client.get('/api/drill/insight/').json()['marker_stats']
        }
        self.assertEqual(stats['overconfident'], 1)
        self.assertEqual(stats['forgotten'], 1)
        self.assertEqual(stats['rusty'], 0)

        replaced = self.client.post(
            marker_url,
            {'codes': ['concept_gap', 'rusty']},
            content_type='application/json',
        )
        self.assertEqual(replaced.json()['markers'], ['concept_gap', 'rusty'])
        self.assertFalse(QuestionMarker.objects.filter(user=self.alice, code='forgotten').exists())

        self.client.force_login(self.bob)
        self.assertEqual(self.client.get('/api/drill/questions/?marker=rusty').json()['count'], 0)
        self.assertEqual(
            self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()['markers'],
            [],
        )

    def test_learning_marker_codes_are_validated(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            f'/api/drill/questions/{self.question.uuid}/markers/',
            {'codes': ['not-a-marker']},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_attempt_confidence_validation_and_null_metadata(self):
        self.client.force_login(self.alice)
        url = f'/api/drill/questions/{self.question.uuid}/attempts/'
        for confidence in (-1, 101):
            response = self.client.post(
                url,
                {'result': 'correct', 'confidence': confidence},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.post(
            url,
            {'result': 'correct', 'confidence': None, 'note': None},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['confidence'])
        self.assertIsNone(response.json()['note'])

    def test_attempt_frequency_and_heatmap_are_private_per_user(self):
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='done')
        QuestionAttempt.objects.create(user=self.alice, question=self.question, result='correct')
        QuestionAttempt.objects.create(user=self.bob, question=self.similar, result='review')
        self.client.force_login(self.alice)
        groups = self.client.get('/api/drill/heatmap/').json()['groups']
        cells = {cell['uuid']: cell for group in groups for cell in group['questions']}
        self.assertEqual(cells[str(self.question.uuid)]['attempt_count'], 2)
        self.assertEqual(cells[str(self.similar.uuid)]['attempt_count'], 0)
        topic = self.client.get('/api/drill/heatmap/?mode=topics').json()['groups'][0]['topics'][0]
        self.assertEqual(topic['attempt_count'], 2)
        self.assertEqual(topic['attempted_question_count'], 1)
        self.assertEqual(topic['review_question_count'], 0)
        self.assertEqual(topic['state'], 'progress')
        created = self.client.post(
            f'/api/drill/questions/{self.similar.uuid}/attempts/',
            {'result': 'review'},
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['attempt_count'], 1)
        updated_topic = self.client.get('/api/drill/heatmap/?mode=topics').json()['groups'][0]['topics'][0]
        self.assertEqual(updated_topic['attempt_count'], 3)
        self.assertEqual(updated_topic['attempted_question_count'], 2)
        self.assertEqual(updated_topic['review_question_count'], 1)
        self.assertEqual(updated_topic['coverage_percent'], 100)
        self.assertEqual(updated_topic['state'], 'review')

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

    def test_detail_separates_question_and_answer_assets_with_etag(self):
        answer_data = b'\x89PNG\r\n\x1a\nanswer-image'
        answer = QuestionAsset.objects.create(
            source_id=2,
            question=self.question,
            asset_type='answer_crop',
            sha256=hashlib.sha256(answer_data).hexdigest(),
            image_data=answer_data,
            width=120,
            height=40,
            source_page_index=3,
            render_dpi=180,
        )
        self.client.force_login(self.alice)
        payload = self.client.get(f'/api/drill/questions/{self.question.uuid}/').json()
        self.assertTrue(payload['has_answer'])
        self.assertEqual([item['id'] for item in payload['question_assets']], [self.asset.pk])
        self.assertEqual([item['id'] for item in payload['answer_assets']], [answer.pk])
        response = self.client.get(f'/api/drill/assets/{answer.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, answer_data)
        self.assertEqual(
            self.client.get(
                f'/api/drill/assets/{answer.pk}/',
                HTTP_IF_NONE_MATCH=response['ETag'],
            ).status_code,
            304,
        )

    def test_import_answer_crops_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'answers.pdf'
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((50, 50), 'official answer')
            document.save(source)
            document.close()
            mapping = root / 'mapping.jsonl'
            mapping.write_text(json.dumps({
                'question_uuid': str(self.question.uuid),
                'source_pdf': source.name,
                'page_indices': [1],
                'crop_regions': [{
                    'page_index': 1, 'x0': 0, 'y0': 0, 'x1': 595, 'y1': 842,
                }],
                'match_confidence': 1.0,
                'review_required': False,
            }) + '\n', encoding='utf-8')
            call_command(
                'import_answer_crops',
                mapping=mapping,
                source_root=root,
                dry_run=True,
            )
        self.assertEqual(QuestionAsset.objects.filter(asset_type='answer_crop').count(), 0)

    def test_last_practiceable_question_has_no_next_question(self):
        self.client.force_login(self.alice)
        detail = self.client.get(f'/api/drill/questions/{self.practice.uuid}/')
        self.assertIsNone(detail.json()['next_question_uuid'])

    def test_next_question_keeps_the_same_source_category(self):
        first_mock = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=5,
            source_label='Mock paper one',
            prompt_text='Mock one',
            content_mode='text',
            fingerprint='f' * 64,
            source_category='mock_exam',
        )
        first_past_exam = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=6,
            source_label='2019数一',
            prompt_text='Interleaved past exam',
            content_mode='text',
            fingerprint='g' * 64,
            source_category='past_exam',
        )
        second_mock = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=7,
            source_label='Mock paper two',
            prompt_text='Mock two',
            content_mode='text',
            fingerprint='h' * 64,
            source_category='mock_exam',
        )
        second_past_exam = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=8,
            source_label='2018数一',
            prompt_text='Second past exam',
            content_mode='text',
            fingerprint='i' * 64,
            source_category='past_exam',
        )

        self.client.force_login(self.alice)
        mock_detail = self.client.get(f'/api/drill/questions/{first_mock.uuid}/')
        past_exam_detail = self.client.get(
            f'/api/drill/questions/{first_past_exam.uuid}/',
        )

        self.assertEqual(mock_detail.json()['next_question_uuid'], str(second_mock.uuid))
        self.assertEqual(
            past_exam_detail.json()['next_question_uuid'], str(second_past_exam.uuid),
        )

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
        self.assertEqual(clean_topic_title('(a)夹逼定理'), '夹逼定理')
        self.assertEqual(clean_topic_title('(ab)定积分定义'), '定积分定义')
        self.assertEqual(clean_topic_title('一、审敛'), '审敛')
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

    def test_question_reference_topics_are_distinct_from_knowledge_topics(self):
        self.assertTrue(is_question_reference_topic('26版660数二第509题'))
        self.assertTrue(is_question_reference_topic('(c) 2019 数二'))
        self.assertTrue(is_question_reference_topic('(b)姜晓千基础'))
        self.assertTrue(is_question_reference_topic('清华大学'))
        self.assertFalse(is_question_reference_topic('(a)夹逼定理'))
        self.assertFalse(is_question_reference_topic('无穷小阶数'))

    def test_context_classification_never_promotes_unknown_practice_to_past_exam(self):
        mock = classify_source_with_context('25 八套数一二三第二套')
        workbook = classify_source_with_context('0✖️∞', '26版660数一二三第7题')
        generic = classify_source_with_context('求下列积分', '定积分计算')

        self.assertEqual(mock.category, 'mock_exam')
        self.assertEqual(workbook.category, 'workbook')
        self.assertEqual(generic.category, 'other_practice')
        self.assertFalse(generic.is_past_exam)
        self.assertLess(generic.confidence, workbook.confidence)

    def test_short_outline_split_across_two_crops_is_not_practiceable(self):
        kind, is_practiceable, _, confidence = classify_record_kind(
            source_category='unclassified',
            source_label='(2) 极坐标 >>',
            prompt_text='(2) 极坐标 >>',
            asset_count=2,
            max_asset_height=244,
        )

        self.assertEqual(kind, 'section')
        self.assertFalse(is_practiceable)
        self.assertGreaterEqual(confidence, 0.9)

    def test_known_linear_algebra_outline_is_not_practiceable_after_context_classification(self):
        kind, is_practiceable, reason, confidence = classify_record_kind(
            source_category='other_practice',
            source_label='1.逆',
            prompt_text='1.逆\na)具体矩阵求逆',
            asset_count=1,
            max_asset_height=147,
        )

        self.assertEqual(kind, 'section')
        self.assertFalse(is_practiceable)
        self.assertEqual(reason, 'recognized source-outline heading')
        self.assertEqual(confidence, 0.99)


class AgentSolutionImportTests(TestCase):
    def setUp(self):
        document = QuestionDocument.objects.create(
            source_id=991,
            filename='agent.pdf',
            title='Agent test',
            sha256='9' * 64,
            page_count=1,
        )
        self.question = Question.objects.create(
            document=document,
            question_order=1,
            prompt_text='Solve x + 1 = 2.',
            content_mode='text',
            fingerprint='8' * 64,
        )

    def _fixture(self, directory):
        path = Path(directory) / 'solutions.jsonl'
        path.write_text(json.dumps({
            'question_uuid': str(self.question.uuid),
            'answer_markdown': '## Solution\n\n$x=1$.',
            'confidence': 0.99,
            'source': 'codex-reviewed',
        }) + '\n', encoding='utf-8')
        return path

    def test_import_agent_solutions_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            call_command('import_agent_solutions', self._fixture(directory), dry_run=True)
        self.question.refresh_from_db()
        self.assertEqual(self.question.answer_markdown, '')

    def test_import_agent_solutions_writes_review_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            call_command('import_agent_solutions', self._fixture(directory))
        self.question.refresh_from_db()
        self.assertEqual(self.question.answer_source, 'codex-reviewed')
        self.assertEqual(self.question.answer_confidence, 0.99)
        self.assertIsNotNone(self.question.answer_generated_at)


class AgentTopicClassificationTests(TestCase):
    def setUp(self):
        self.document = QuestionDocument.objects.create(
            source_id=993,
            filename='极限题目册.pdf',
            title='Limits',
            display_title='极限',
            sha256='7' * 64,
            page_count=1,
        )
        self.topic = QuestionTopic.objects.create(
            source_id=993,
            document=self.document,
            title='求函数表达式',
            display_title='求函数表达式',
            level=3,
            sort_order=1,
        )
        self.question = Question.objects.create(
            document=self.document,
            question_order=100001,
            source_label='a) 880第一章基础填空1 >>',
            prompt_text='Recovered question',
            content_mode='image',
            fingerprint='6' * 64,
            classification_reason='recovered from answer-book pair',
        )
        QuestionAsset.objects.create(
            source_id=993,
            question=self.question,
            asset_type='question_crop',
            sha256=hashlib.sha256(TEST_PNG).hexdigest(),
            image_data=TEST_PNG,
            width=100,
            height=30,
            source_page_index=0,
        )

    def _answer_root(self, directory):
        path = Path(directory) / '极限答案册.pdf'
        pdf = pymupdf.open()
        pdf.new_page()
        pdf.set_toc([
            [1, '1. 极限 >>', 1],
            [2, 'A. 函数 >>', 1],
            [3, '1. 求函数表达式 >>', 1],
            [4, 'a) 880第一章基础填空1 >>', 1],
        ])
        pdf.save(path)
        pdf.close()
        for filename in (
            '一元积分题库-答案.pdf', '线代1000题参考答案.pdf',
            '二重积分题库答案.pdf', '多元微分大观-答案.pdf',
            '微分方程大观-答案.pdf', '反常积分-答案.pdf',
            '一元微分大观-答案.pdf',
        ):
            other = pymupdf.open()
            other.new_page()
            other.save(Path(directory) / filename)
            other.close()
        return Path(directory)

    def test_answer_book_toc_classification_is_reversible_and_dry_runnable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._answer_root(directory)
            call_command('classify_unassigned_topics', root, dry_run=True)
            self.question.refresh_from_db()
            self.assertIsNone(self.question.similarity_topic_id)
            call_command('classify_unassigned_topics', root)
        self.question.refresh_from_db()
        self.assertEqual(self.question.topic, self.topic)
        self.assertEqual(self.question.similarity_topic, self.topic)
        self.assertEqual(self.question.topic_classification_source, 'answer-book-toc')
        self.assertGreaterEqual(self.question.topic_classification_confidence, 0.9)


class TopicNormalizationCommandTests(TestCase):
    def setUp(self):
        self.document = QuestionDocument.objects.create(
            source_id=998,
            filename='limits.pdf',
            title='Limits',
            display_title='极限',
            sha256='8' * 64,
            page_count=1,
        )
        self.knowledge = QuestionTopic.objects.create(
            source_id=9981,
            document=self.document,
            title='极限计算',
            display_title='极限计算',
            level=3,
            sort_order=1,
        )
        self.reference = QuestionTopic.objects.create(
            source_id=9982,
            document=self.document,
            parent=self.knowledge,
            title='26版660数二第509题',
            display_title='26版660数二第509题',
            level=4,
            sort_order=2,
        )
        self.question = Question.objects.create(
            document=self.document,
            topic=self.reference,
            similarity_topic=self.reference,
            question_order=1,
            source_label='26版660数二第509题',
            prompt_text='Question',
            content_mode='image',
            fingerprint='8' * 64,
            topic_classification_source='answer-book-breadcrumb',
        )

    def test_normalization_is_dry_runnable_and_reversible(self):
        call_command('normalize_question_topics', dry_run=True)
        self.question.refresh_from_db()
        self.assertEqual(self.question.similarity_topic, self.reference)

        call_command('normalize_question_topics')
        self.question.refresh_from_db()
        self.assertEqual(self.question.topic, self.reference)
        self.assertEqual(self.question.similarity_topic, self.knowledge)

        call_command('normalize_question_topics', restore_source_topics=True)
        self.question.refresh_from_db()
        self.assertEqual(self.question.similarity_topic, self.reference)


class SourceClassificationCommandTests(TestCase):
    def test_only_visible_unclassified_questions_are_updated(self):
        document = QuestionDocument.objects.create(
            source_id=994,
            filename='source.pdf',
            title='Source',
            display_title='Source',
            sha256='5' * 64,
            page_count=1,
        )
        question = Question.objects.create(
            document=document,
            question_order=1,
            source_label='25 八套数一二三第二套',
            content_mode='text',
            fingerprint='4' * 64,
        )
        outline = Question.objects.create(
            document=document,
            question_order=2,
            source_label='目录',
            content_mode='text',
            fingerprint='3' * 64,
            record_kind='section',
            is_practiceable=False,
        )

        call_command('classify_unclassified_sources', dry_run=True)
        question.refresh_from_db()
        self.assertEqual(question.source_category, 'unclassified')
        call_command('classify_unclassified_sources')
        question.refresh_from_db()
        outline.refresh_from_db()
        self.assertEqual(question.source_category, 'mock_exam')
        self.assertEqual(outline.source_category, 'unclassified')


class CxyDifferentiationPdfTests(SimpleTestCase):
    def test_bookmarks_author_and_question_labels_are_preserved(self):
        parsed = parse_question_pdf(Path(__file__).with_name('【A4 紧凑】一元微分做题本.pdf'))
        self.assertEqual(parsed.title, '一元微分')
        self.assertEqual(parsed.author, '本本')
        self.assertIn('cxy', parsed.attribution)
        self.assertEqual(len(parsed.topics), 102)
        self.assertEqual(len(parsed.questions), 675)
        self.assertEqual(parsed.questions[0].source_label, 'a)1993 数二;880 第二章基础选择9')

    def test_formula_bounds_and_trailing_lines_are_inside_question_crops(self):
        parsed = parse_question_pdf(Path(__file__).with_name('【A4 紧凑】一元微分做题本.pdf'))
        tall_formula = next(item for item in parsed.questions if item.source_label.startswith('f )1994'))
        grouped_source = next(
            item for item in parsed.questions
            if item.source_label.startswith('(13) 姜晓千真题同源150')
        )

        self.assertLess(tall_formula.segments[0].y0, 653)
        self.assertGreater(grouped_source.segments[0].y1, 269.7)


class QuestionAssetRerenderTests(SimpleTestCase):
    def test_cut_formula_fragment_can_be_moved_to_following_crop(self):
        pdf = pymupdf.open()
        page = pdf.new_page(width=220, height=180)
        page.insert_text((20, 82), 'Previous question', fontsize=10)
        page.draw_line((95, 112), (95, 128), width=2)
        page.draw_line((80, 118), (150, 118), width=2)
        previous = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=pymupdf.Rect(0, 60, 220, 120), alpha=False,
        ).tobytes('png')
        current = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=pymupdf.Rect(0, 120, 220, 165), alpha=False,
        ).tobytes('png')

        fragment_start = trailing_edge_fragment_start(previous, 180)
        self.assertIsNotNone(fragment_start)
        previous_pixmap = pymupdf.Pixmap(previous)
        fragment = crop_pixmap_rows(previous, fragment_start, previous_pixmap.height, 180)
        repaired, width, height, leading_height = reframe_crop_image(
            current, 180, leading_fragment=fragment,
        )

        self.assertEqual(width, pymupdf.Pixmap(current).width)
        self.assertGreater(leading_height, 0)
        self.assertEqual(height, pymupdf.Pixmap(current).height + leading_height)
        self.assertTrue(repaired.startswith(b'\x89PNG\r\n\x1a\n'))

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


class QuestionCropEdgeRepairCommandTests(TestCase):
    def test_command_moves_cut_fragment_and_is_dry_runnable(self):
        document = QuestionDocument.objects.create(
            source_id=881,
            filename='edge.pdf',
            title='Edge formulas',
            display_title='Edge formulas',
            sha256='e' * 64,
            page_count=1,
            parser_strategy='TocLinkParser',
        )
        first = Question.objects.create(
            document=document,
            question_order=1,
            source_label='First',
            content_mode='image',
            fingerprint='1' * 64,
        )
        second = Question.objects.create(
            document=document,
            question_order=2,
            source_label='Second',
            content_mode='image',
            fingerprint='2' * 64,
        )
        pdf = pymupdf.open()
        page = pdf.new_page(width=220, height=180)
        page.insert_text((20, 82), 'Previous question', fontsize=10)
        page.draw_line((95, 112), (95, 128), width=2)
        page.draw_line((80, 118), (150, 118), width=2)
        first_png = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=pymupdf.Rect(0, 60, 220, 120), alpha=False,
        ).tobytes('png')
        second_png = page.get_pixmap(
            matrix=pymupdf.Matrix(2.5, 2.5),
            clip=pymupdf.Rect(0, 120, 220, 165), alpha=False,
        ).tobytes('png')
        first_asset = QuestionAsset.objects.create(
            source_id=8811, question=first, asset_type='question_crop', position=0,
            sha256=hashlib.sha256(first_png).hexdigest(), image_data=first_png,
            width=pymupdf.Pixmap(first_png).width, height=pymupdf.Pixmap(first_png).height,
            source_page_index=0, source_x0=0, source_y0=60, source_x1=220, source_y1=120,
            render_dpi=180,
        )
        second_asset = QuestionAsset.objects.create(
            source_id=8812, question=second, asset_type='question_crop', position=0,
            sha256=hashlib.sha256(second_png).hexdigest(), image_data=second_png,
            width=pymupdf.Pixmap(second_png).width, height=pymupdf.Pixmap(second_png).height,
            source_page_index=0, source_x0=0, source_y0=120, source_x1=220, source_y1=165,
            render_dpi=180,
        )
        original_total_height = first_asset.height + second_asset.height

        call_command('repair_question_crop_edges', source_id=[881], dry_run=True)
        document.refresh_from_db()
        self.assertNotIn('edge-safe-v1', document.parser_strategy)

        call_command('repair_question_crop_edges', source_id=[881])
        document.refresh_from_db()
        first_asset.refresh_from_db()
        second_asset.refresh_from_db()
        self.assertIn('edge-safe-v1', document.parser_strategy)
        self.assertLess(first_asset.height, pymupdf.Pixmap(first_png).height)
        self.assertGreater(second_asset.height, pymupdf.Pixmap(second_png).height)
        self.assertEqual(first_asset.height + second_asset.height, original_total_height)
        self.assertLess(second_asset.source_y0, 120)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    DEBUG=False,
    ALLOWED_HOSTS=['timer.ehzsy.site', 'drill.ehzsy.site', 'ei.ehzsy.site'],
    DRILL_HOSTS={'drill.ehzsy.site'},
    EI_HOSTS={'ei.ehzsy.site'},
)
class DrillHostRoutingTests(TestCase):
    def test_icons_are_drill_specific_without_changing_timer_icons(self):
        drill_touch = self.client.get('/icon-180.png', HTTP_HOST='drill.ehzsy.site')
        drill_favicon = self.client.get('/favicon.ico', HTTP_HOST='drill.ehzsy.site')
        timer_touch = self.client.get('/icon-180.png', HTTP_HOST='timer.ehzsy.site')
        timer_favicon = self.client.get('/favicon.ico', HTTP_HOST='timer.ehzsy.site')

        self.assertEqual(
            drill_touch.url,
            '/static/drill/drill-icon-180.png?v=img9392',
        )
        self.assertEqual(
            drill_favicon.url,
            '/static/drill/drill-favicon-32.png?v=img9392',
        )
        self.assertEqual(timer_touch.url, '/static/tracker/img9387-icon-180.png')
        self.assertEqual(timer_favicon.url, '/static/tracker/img9387-icon-180.png')

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
                ei_response = self.client.get('/', HTTP_HOST='ei.ehzsy.site')
                drill_book_activity = self.client.get('/book-activity', HTTP_HOST='drill.ehzsy.site')
                ei_book_activity = self.client.get('/book-activity', HTTP_HOST='ei.ehzsy.site')
                timer_response = self.client.get('/', HTTP_HOST='timer.ehzsy.site')
                blocked = self.client.get('/practice', HTTP_HOST='timer.ehzsy.site')
        self.assertContains(drill_response, 'DRILL FRONTEND')
        self.assertContains(ei_response, 'DRILL FRONTEND')
        self.assertContains(drill_book_activity, 'DRILL FRONTEND')
        self.assertContains(ei_book_activity, 'DRILL FRONTEND')
        self.assertContains(timer_response, 'TIMER FRONTEND')
        self.assertEqual(blocked.status_code, 404)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    DEBUG=False,
    ALLOWED_HOSTS=['timer.ehzsy.site', 'drill.ehzsy.site', 'ei.ehzsy.site'],
    DRILL_HOSTS={'drill.ehzsy.site'},
    EI_HOSTS={'ei.ehzsy.site'},
    DRILL_ORIGIN='https://drill.ehzsy.site',
    EI_ORIGIN='https://ei.ehzsy.site',
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

    def test_anonymous_paper_deep_link_preserves_target(self):
        response = self.client.get('/paper', HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=%2Fpaper', response.url)

    def test_anonymous_activity_deep_link_preserves_target(self):
        response = self.client.get('/activity', HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=%2Factivity', response.url)

    def test_anonymous_book_activity_deep_link_preserves_target(self):
        response = self.client.get('/book-activity', HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=%2Fbook-activity', response.url)

    def test_anonymous_ei_page_uses_timer_relay_and_preserves_site(self):
        response = self.client.get(
            '/practice?topic=3', HTTP_HOST='ei.ehzsy.site', secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(
            'https://timer.ehzsy.site/drill-auth/start?',
        ))
        self.assertIn('site=ei', response.url)
        self.assertIn('next=%2Fpractice%3Ftopic%3D3', response.url)

    def test_timer_handoff_can_target_ei(self):
        timer = Client()
        timer.force_login(self.user)
        start = timer.get(
            '/drill-auth/start?site=ei&next=/heatmap',
            HTTP_HOST='timer.ehzsy.site',
            secure=True,
        )
        self.assertTrue(start.url.startswith(
            'https://ei.ehzsy.site/drill-auth/complete/',
        ))
        raw_token = urlsplit(start.url).path.rsplit('/', 1)[1]
        completed = Client().get(
            f'/drill-auth/complete/{raw_token}',
            HTTP_HOST='ei.ehzsy.site',
            secure=True,
        )
        self.assertRedirects(completed, '/heatmap', fetch_redirect_response=False)

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
