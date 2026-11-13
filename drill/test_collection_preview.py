"""Synthetic collection contracts: stable identities, scope, snapshot and I/O."""
import datetime
import threading
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    ExamBlueprint, ExamBlueprintSection, ExamPaper, ExamPaperItem, Question,
    QuestionAsset, QuestionAttempt, QuestionAttemptError, QuestionDocument,
    QuestionErratum, QuestionReviewPlan, QuestionRevision, QuestionSearchState,
    QuestionTopic, QuestionUserState,
)


SETTINGS = dict(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['drill.test', 'ei.test'],
                DRILL_HOSTS={'drill.test'}, EI_HOSTS={'ei.test'}, DRILL_SEARCH_BACKEND='legacy')


@override_settings(**SETTINGS)
class CollectionPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('preview-owner')
        cls.other = get_user_model().objects.create_user('preview-other')
        cls.doc = QuestionDocument.objects.create(source_id=99101, workspace='drill', filename='preview.pdf',
            title='Preview mathematics', sha256='preview-doc', page_count=1, relation_type='selected_question_book')
        cls.ei_doc = QuestionDocument.objects.create(source_id=99102, workspace='ei', filename='signals.pdf',
            title='Preview signals', sha256='preview-ei', page_count=1)
        cls.topic = QuestionTopic.objects.create(source_id=99101, document=cls.doc, title='Calculus', level=1, sort_order=1)
        cls.items = Question.objects.bulk_create([Question(document=cls.doc, question_order=n,
            source_label=f'P{n}', prompt_text=f'Question {n}: derivative $x^2$', answer_markdown='ANSWER_MUST_NOT_LEAK',
            fingerprint=f'preview-{n}', content_mode='text', source_category='past_exam',
            similarity_topic=cls.topic, question_type='solution' if n % 2 else 'single_choice') for n in range(105)])
        cls.ei_items = Question.objects.bulk_create([Question(document=cls.ei_doc, question_order=n,
            source_label=f'E{n}', prompt_text=f'Signal {n}', fingerprint=f'preview-ei-{n}', content_mode='text',
            source_category='past_exam') for n in range(3)])

    def setUp(self):
        self.client = APIClient(HTTP_HOST='drill.test')
        self.client.force_authenticate(self.owner)

    def get(self, source='practice', expected=200, host='drill.test', **params):
        response = self.client.get('/api/drill/collection-preview/', {'source': source, **params}, HTTP_HOST=host)
        self.assertEqual(response.status_code, expected, getattr(response, 'data', response.content))
        return response

    def asset(self, question, source_id, kind='question_crop', position=0):
        return QuestionAsset.objects.create(question=question, source_id=source_id, position=position,
            asset_type=kind, sha256=f'{source_id:064x}', image_data=b'BINARY_MUST_NOT_LOAD', width=640, height=960)

    def test_navigation_preview_matches_existing_next_and_wrap_order(self):
        anchor = self.items[102]
        data = self.get('navigation', navigation_anchor=str(anchor.uuid)).data
        ids = [row['question_uuid'] for row in data['results']]
        self.assertEqual(ids[:4], [str(self.items[n].uuid) for n in [102, 103, 104, 0]])
        detail = self.client.get(f'/api/drill/questions/{anchor.uuid}/').data
        self.assertEqual(ids[1], detail['sequential_next_question_uuid'])
        self.assertEqual(data['located'], None)
        self.assertEqual(data['count'], 105)

    def test_navigation_review_modes_and_status_use_latest_attempt_age(self):
        anchor, old, recent, reset = self.items[:4]
        a = QuestionAttempt.objects.create(user=self.owner, question=old, result='review')
        QuestionAttempt.objects.filter(pk=a.pk).update(created_at=timezone.now() - datetime.timedelta(days=6))
        QuestionAttempt.objects.create(user=self.owner, question=recent, result='review')
        QuestionAttempt.objects.create(user=self.owner, question=reset, result='review')
        QuestionAttempt.objects.create(user=self.owner, question=reset, result='reset')
        for mode, expected in [('overdue', old), ('review', recent)]:
            data = self.get('navigation', navigation_anchor=str(anchor.uuid), navigation_mode=mode).data
            self.assertEqual([row['question_uuid'] for row in data['results']], [str(anchor.uuid), str(expected.uuid)])
            self.assertEqual(data['results'][1]['review_overdue'], mode == 'overdue')
            detail = self.client.get(f'/api/drill/questions/{anchor.uuid}/').data
            self.assertEqual(str(expected.uuid), detail['next_overdue_review_uuid' if mode == 'overdue' else 'next_review_uuid'])
        data = self.get('navigation', navigation_anchor=str(anchor.uuid), navigation_mode='unattempted').data
        self.assertEqual(data['results'][1]['question_uuid'], str(reset.uuid))
        self.assertNotIn(str(old.uuid), [row['question_uuid'] for row in data['results']])

    def test_navigation_favorites_retains_list_order_without_wrapping(self):
        for q in self.items[:3]:
            QuestionUserState.objects.create(user=self.owner, question=q, is_favorite=True)
        anchor = self.items[1]
        data = self.get('navigation', navigation_anchor=str(anchor.uuid), navigation_from='collection', collection='favorite').data
        self.assertEqual([row['question_uuid'] for row in data['results']], [str(q.uuid) for q in reversed(self.items[:3])])
        detail = self.client.get(f'/api/drill/questions/{anchor.uuid}/', {'from':'collection','collection':'favorite'}).data
        self.assertEqual(data['results'][2]['question_uuid'], detail['sequential_next_question_uuid'])

    def test_navigation_selected_unattempted_missing_anchor_starts_at_first_eligible(self):
        anchor = self.items[50]
        params = {'collection': 'selected', 'type_group': 'large'}
        data = self.get('navigation', navigation_anchor=str(anchor.uuid), navigation_mode='unattempted', **params).data
        detail = self.client.get(f'/api/drill/questions/{anchor.uuid}/', params).data
        self.assertEqual(data['results'][1]['question_uuid'], detail['next_unattempted_question_uuid'])
        self.assertEqual(data['results'][1]['question_uuid'], str(self.items[1].uuid))

    def test_navigation_rejects_invalid_modes_and_cross_workspace_anchor(self):
        self.get('navigation', expected=400, navigation_anchor=str(self.items[0].uuid), navigation_mode='anything')
        self.get('navigation', expected=404, host='ei.test', navigation_anchor=str(self.items[0].uuid))

    def test_50_batch_and_practice_page_metadata_are_compatible(self):
        first = self.get().data
        second = self.get(offset=50, collection_version=first['collection_version']).data
        last = self.get(offset=100, collection_version=first['collection_version']).data
        self.assertEqual((first['count'], first['limit'], len(first['results']), first['has_more']), (105, 50, 50, True))
        self.assertEqual((second['offset'], second['results'][0]['index']), (50, 50))
        self.assertEqual((len(last['results']), last['has_more']), (5, False))
        self.assertEqual(len({row['entry_id'] for data in (first, second, last) for row in data['results']}), 105)
        old = self.client.get('/api/drill/questions/', {'page': 2}).data
        self.assertEqual((old['count'], old['page'], old['page_size'], old['total_pages']), (105, 2, 24, 5))
        self.assertEqual([row['uuid'] for row in old['results']], [str(q.uuid) for q in self.items[24:48]])
        empty = self.client.get('/api/drill/questions/', {'q': 'no such literal'}).data
        self.assertEqual((empty['count'], empty['total_pages'], empty['page']), (0, 0, 1))

    def test_locate_selects_containing_batch_and_strict_neighbors(self):
        row = self.items[51]
        data = self.get(locate_uuid=str(row.uuid)).data
        self.assertEqual((data['offset'], data['located']['index']), (50, 51))
        self.assertEqual(data['located']['entry_id'], f'question:{row.uuid}')
        self.assertEqual(data['previous_entry']['question_uuid'], str(self.items[50].uuid))
        self.assertEqual(data['next_entry']['question_uuid'], str(self.items[52].uuid))
        self.assertIsNone(self.get(locate_uuid=str(self.items[0].uuid)).data['previous_entry'])
        self.assertIsNone(self.get(locate_uuid=str(self.items[-1].uuid)).data['next_entry'])

    def test_version_catches_reorder_without_count_change_and_refresh_fallback(self):
        first = self.get(locate_uuid=str(self.items[-1].uuid)).data
        Question.objects.filter(pk=self.items[0].pk).update(question_order=200)
        conflict = self.get(expected=409, collection_version=first['collection_version'])
        self.assertEqual(conflict.data['code'], 'COLLECTION_CHANGED')
        self.assertNotEqual(first['collection_version'], conflict.data['collection_version'])
        missing = self.get(locate_entry='question:removed', fallback_index=999).data
        self.assertEqual(missing['located']['index'], 104)
        self.assertEqual(missing['notice'], 'ENTRY_REMOVED_USING_NEAREST')
        self.assertEqual(self.get(locate_entry='question:removed').data['notice'], 'ENTRY_NOT_FOUND')

    def test_version_binds_owner_workspace_filters_and_index_generation(self):
        first = self.get().data
        self.client.force_authenticate(self.other)
        self.get(expected=409, collection_version=first['collection_version'])
        self.client.force_authenticate(self.owner)
        self.get(expected=409, host='ei.test', collection_version=first['collection_version'])
        self.get(expected=409, document=self.doc.pk, collection_version=first['collection_version'])
        heat = self.get(source='heatmap').data
        QuestionSearchState.objects.update_or_create(workspace='drill', defaults={'generation': 200})
        self.get(source='heatmap', expected=409, collection_version=heat['collection_version'])

    def test_version_changes_for_cross_device_state_without_membership_change(self):
        initial = self.get().data
        state = QuestionUserState.objects.create(user=self.owner, question=self.items[70], is_favorite=True, note='First')
        self.get(expected=409, collection_version=initial['collection_version'], offset=50)
        current = self.get().data
        state.note = 'Edited on another device'
        state.version += 1
        state.save(update_fields=['note', 'version', 'updated_at'])
        self.get(expected=409, collection_version=current['collection_version'])
        current = self.get().data
        QuestionAttempt.objects.create(user=self.owner, question=self.items[70], result='correct')
        self.get(expected=409, collection_version=current['collection_version'])
        current = self.get().data
        QuestionAttempt.objects.create(user=self.other, question=self.items[70], result='review')
        QuestionUserState.objects.create(user=self.owner, question=self.ei_items[0], note='Another workspace')
        self.assertEqual(current['collection_version'], self.get().data['collection_version'])
        # Deleting an older non-max state changes the count even if the most
        # recently updated row and max version remain unchanged.
        QuestionUserState.objects.create(user=self.owner, question=self.items[71], note='Newer row', version=10)
        current = self.get().data
        state.delete()
        self.get(expected=409, collection_version=current['collection_version'])

    def test_review_plan_edit_invalidates_cached_batch(self):
        plan = QuestionReviewPlan.objects.create(user=self.owner, question=self.items[0], status='active')
        first = self.get(source='diagnostics').data
        plan.status = 'paused'
        plan.save(update_fields=['status', 'updated_at'])
        self.get(source='diagnostics', collection_version=first['collection_version'], expected=409)

    def test_attempts_keep_duplicates_and_own_result_time(self):
        earlier = QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='correct')
        later = QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='review')
        outsider = QuestionAttempt.objects.create(user=self.other, question=self.items[0], result='correct')
        QuestionAttempt.objects.create(user=self.owner, question=self.ei_items[0], result='correct')
        data = self.get(source='attempts', locate_entry=f'attempt:{later.pk}').data
        self.assertEqual(data['count'], 2)
        self.assertEqual([row['attempt']['id'] for row in data['results']], [later.pk, earlier.pk])
        self.assertEqual([row['state'] for row in data['results']], ['review', 'mastered'])
        self.assertEqual(data['next_entry']['entry_id'], f'attempt:{earlier.pk}')
        self.assertEqual(data['next_entry']['question_uuid'], data['located']['question_uuid'])
        self.assertNotIn(outsider.pk, [row['attempt']['id'] for row in data['results']])
        self.assertEqual(self.get(source='attempts', sort='oldest').data['results'][0]['attempt']['id'], earlier.pk)
        self.assertEqual(self.get(source='attempts', state='mastered').data['count'], 1)

    def test_history_filters_and_notes_follow_existing_semantics(self):
        attempt = QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='review')
        QuestionAttemptError.objects.create(attempt=attempt, code='B1', is_primary=True)
        QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='reset')
        saved = QuestionUserState.objects.create(user=self.owner, question=self.items[0], note='私有 Fourier transform ' + 'n' * 200)
        QuestionUserState.objects.create(user=self.other, question=self.items[1], note='SECRET OTHER ACCOUNT')
        notes = self.get(source='notes', q='傅里叶变换', error='B1', state='review').data
        self.assertEqual(notes['count'], 1)
        self.assertEqual(notes['results'][0]['entry_id'], f'note:{saved.pk}')
        self.assertEqual(notes['results'][0]['state'], 'review')
        self.assertEqual(len(notes['results'][0]['note_excerpt']), 160)
        self.assertEqual(self.get(source='attempts', has_note='0').data['count'], 0)
        self.get(source='notes', expected=400, document='NaN')
        self.get(source='attempts', expected=400, start='2026-02-30')

    def test_favorites_and_review_later_owner_order_no_learning_writes(self):
        first = QuestionUserState.objects.create(user=self.owner, question=self.items[0], is_favorite=True)
        second = QuestionUserState.objects.create(user=self.owner, question=self.items[1], is_favorite=True, review_later=True)
        QuestionUserState.objects.create(user=self.other, question=self.items[2], is_favorite=True, note='SECRET')
        before = list(QuestionUserState.objects.values())
        data = self.get(source='favorite').data
        self.assertEqual([row['entry_id'] for row in data['results']], [f'favorite:{second.pk}', f'favorite:{first.pk}'])
        self.assertEqual(self.get(source='review_later').data['count'], 1)
        self.assertEqual(QuestionAttempt.objects.count(), 0)
        self.assertEqual(before, list(QuestionUserState.objects.values()))
        self.assertNotIn('note_excerpt', data['results'][0])

    def test_metadata_only_assets_and_shared_source_page(self):
        from drill_sources.models import SourceQuestionAnchor
        first = self.asset(self.items[0], 99102, position=1)
        leading = self.asset(self.items[0], 99101, position=0)
        self.asset(self.items[0], 99103, kind='answer_crop')
        source = Question.objects.create(document=self.doc, question_order=999, fingerprint='source-page', is_practiceable=False)
        source_asset = self.asset(source, 99104)
        SourceQuestionAnchor.objects.create(question=self.items[1], source_question=source, asset=source_asset,
            key='Q1', label='Q1', y=0.2, position=0)
        with CaptureQueriesContext(connection) as captured:
            data = self.get().data
        rendered = str(data)
        self.assertNotIn('ANSWER_MUST_NOT_LEAK', rendered)
        self.assertNotIn('BINARY_MUST_NOT_LOAD', rendered)
        self.assertFalse(any('image_data' in query['sql'].lower() for query in captured))
        self.assertEqual([row['id'] for row in data['results'][0]['preview']['assets']], [leading.pk, first.pk])
        self.assertEqual(data['results'][1]['preview']['assets'][0]['id'], source_asset.pk)
        self.assertTrue(data['results'][1]['preview']['source_page'])
        self.assertEqual(data['results'][0]['preview']['assets'][0]['width'], 640)
        self.assertLess(len(captured), 18)

    def test_batch_queries_are_constant_and_no_detail_view_hydration(self):
        from . import collection_preview
        from .views import DrillQuestionDetailView
        with patch.object(DrillQuestionDetailView, 'get', side_effect=AssertionError('N+1 detail call')):
            with patch.object(collection_preview, '_hydrate', wraps=collection_preview._hydrate) as hydrate:
                with CaptureQueriesContext(connection) as first_queries:
                    self.get(offset=0)
                self.assertEqual(len(hydrate.call_args.args[3]), 50)
                with CaptureQueriesContext(connection) as last_queries:
                    self.get(offset=100)
                self.assertEqual(len(hydrate.call_args.args[3]), 5)
        self.assertEqual(len(first_queries), len(last_queries))

    def test_foreign_source_anchor_cannot_leak_another_workspace_image(self):
        from drill_sources.models import SourceQuestionAnchor
        asset = self.asset(self.ei_items[0], 99801)
        # Deliberately bypass model clean to simulate an invalid historical row.
        SourceQuestionAnchor.objects.create(question=self.items[0], source_question=self.ei_items[0], asset=asset,
            key='invalid', label='Invalid cross-workspace source', y=0, position=0)
        self.assertEqual(self.get().data['results'][0]['preview']['assets'], [])

    def test_heatmap_matches_matrix_order_and_highlight_does_not_filter(self):
        QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='correct')
        matrix = self.client.get('/api/drill/heatmap/', {'scope': 'all', 'collection': 'selected'}).data
        expected = [q['uuid'] for group in matrix['groups'] for q in group['questions']]
        preview = self.get(source='heatmap', scope='all', collection='selected', status='mastered').data
        self.assertEqual([row['question_uuid'] for row in preview['results']], expected[:50])
        self.assertEqual(preview['count'], len(expected))
        self.get(source='heatmap', host='ei.test', collection='selected', expected=404)

    def test_selected_bucket_order_kind_filter_and_fingerprint(self):
        from . import circuit_selected
        data = {'schema_version': 1, 'buckets': [{'key': 'B'}, {'key': 'A'}], 'kinds': ['concept', 'calculation'],
            'questions': [{'uuid': str(q.uuid), 'fingerprint': q.fingerprint, 'bucket': 'A' if n == 0 else 'B',
                'tier': 'core', 'kind': 'concept' if n != 2 else 'calculation'} for n, q in enumerate(self.ei_items)]}
        with patch.object(circuit_selected, 'manifest', return_value=data):
            result = self.get(source='selected', host='ei.test', collection='circuit_selected', kind='concept').data
            self.assertEqual([row['question_uuid'] for row in result['results']],
                [str(self.ei_items[1].uuid), str(self.ei_items[0].uuid)])
            self.assertEqual(self.get(source='selected', host='ei.test', collection='circuit_selected', bucket='B').data['count'], 2)
            Question.objects.filter(pk=self.ei_items[1].pk).update(fingerprint='changed')
            self.assertEqual(self.get(source='selected', host='ei.test', collection='circuit_selected', kind='concept').data['count'], 1)

    def test_diagnostics_due_error_and_owner_scope(self):
        attempt = QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='review')
        QuestionAttemptError.objects.create(attempt=attempt, code='B2', is_primary=True)
        first = QuestionReviewPlan.objects.create(user=self.owner, question=self.items[0],
            next_review_at=timezone.now() - datetime.timedelta(days=1))
        QuestionReviewPlan.objects.create(user=self.owner, question=self.items[1],
            next_review_at=timezone.now() + datetime.timedelta(days=1))
        QuestionReviewPlan.objects.create(user=self.other, question=self.items[2], next_review_at=timezone.now())
        data = self.get(source='diagnostics', queue='due', error='B2').data
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['entry_id'], f'diagnostic:{first.pk}')
        self.get(source='diagnostics', queue='unknown', expected=400)

    def test_errata_are_workspace_public_with_distinct_entry_identity(self):
        first = QuestionErratum.objects.create(question=self.items[0], reporter=self.owner, description='Synthetic correction')
        second = QuestionErratum.objects.create(question=self.items[0], reporter=self.other, description='Another correction')
        QuestionErratum.objects.create(question=self.ei_items[0], reporter=self.owner, description='Other workspace')
        data = self.get(source='errata', question=str(self.items[0].uuid)).data
        self.assertEqual([row['entry_id'] for row in data['results']], [f'erratum:{second.pk}', f'erratum:{first.pk}'])
        self.assertEqual(data['count'], 2)

    def test_paper_owner_workspace_and_pinned_revision(self):
        question = self.items[0]
        crop = self.asset(question, 99501)
        revision = QuestionRevision.capture(question)
        blueprint = ExamBlueprint.objects.create(code='preview-blueprint', title='Synthetic exam', subject='math2',
            mode='standard', version=99, duration_minutes=10, total_score=5)
        section = ExamBlueprintSection.objects.create(blueprint=blueprint, order=1, title='Questions',
            question_type='solution', question_count=1, score_per_question=5)
        paper = ExamPaper.objects.create(user=self.owner, blueprint=blueprint, seed=1, mode='standard')
        item = ExamPaperItem.objects.create(paper=paper, section=section, question=question, question_revision=revision,
            position=1, score=5, selected_fingerprint=question.fingerprint)
        Question.objects.filter(pk=question.pk).update(prompt_text='CHANGED CURRENT QUESTION', display_label='Changed label')
        self.asset(question, 99502)
        with CaptureQueriesContext(connection) as captured:
            data = self.get(source='paper', paper=str(paper.uuid)).data
        row = data['results'][0]
        self.assertEqual(row['entry_id'], f'paper:{item.pk}')
        self.assertEqual(row['label'], revision.source_label)
        self.assertEqual(row['preview']['question_markdown'], revision.prompt_text)
        self.assertEqual([a['id'] for a in row['preview']['assets']], [crop.pk])
        self.assertEqual(data['notice'], 'PAPER_REVISION_PREVIEW_CANONICAL_PRACTICE_IS_SEPARATE')
        self.assertFalse(any('image_data' in query['sql'].lower() for query in captured))
        paper.refresh_from_db()
        self.assertEqual(paper.status, 'generated')
        self.client.force_authenticate(self.other)
        self.get(source='paper', paper=str(paper.uuid), expected=404)
        self.client.force_authenticate(self.owner)
        self.get(source='paper', paper=str(paper.uuid), host='ei.test', expected=404)

    def test_validation_cache_headers_empty_and_auth(self):
        for params in [{'source': 'unknown'}, {'limit': 51}, {'limit': 1}, {'offset': -1},
                       {'offset': 'bad'}, {'locate_uuid': 'bad'}, {'fallback_index': -1}]:
            self.get(expected=400, **params)
        empty = self.get(q='missing literal', locate_entry='missing', fallback_index=0, offset=100)
        self.assertEqual((empty.data['count'], empty.data['offset'], empty.data['results']), (0, 0, []))
        self.assertIsNone(empty.data['located'])
        self.assertIn('no-store', empty['Cache-Control'])
        self.assertIn('Cookie', empty['Vary'])
        self.client.force_authenticate(None)
        response = self.client.get('/api/drill/collection-preview/', HTTP_HOST='drill.test')
        self.assertIn(response.status_code, (401, 403))

    def test_practice_combined_filters_share_old_membership(self):
        QuestionAttempt.objects.create(user=self.owner, question=self.items[0], result='review')
        QuestionAttempt.objects.create(user=self.owner, question=self.items[1], result='correct')
        QuestionUserState.objects.create(user=self.owner, question=self.items[0], is_favorite=True)
        params = {'q': 'derivative', 'status': 'review', 'favorite': '1', 'collection': 'selected',
                  'document': self.doc.pk, 'topic': self.topic.pk, 'sort': 'source', 'type_group': 'small'}
        old = self.client.get('/api/drill/questions/', params)
        self.assertEqual(old.status_code, 200, old.data)
        new = self.get(**params).data
        self.assertEqual(new['count'], old.data['count'])
        self.assertEqual([row['question_uuid'] for row in new['results']], [row['uuid'] for row in old.data['results']])


@override_settings(**{**SETTINGS, 'DRILL_SEARCH_BACKEND': 'hybrid_v1'})
class CollectionPreviewHybridTests(TestCase):
    def test_ranked_membership_matches_existing_list_and_index_pin(self):
        from .search.index import enqueue, process_queue, verify_workspace
        user = get_user_model().objects.create_user('preview-hybrid')
        doc = QuestionDocument.objects.create(source_id=99201, workspace='drill', filename='rank.pdf',
            title='Rank fixture', sha256='rank-doc', page_count=1)
        for index, text in enumerate(['傅里叶级数', '傅里叶变换 Fourier transform', 'Fourier direct', 'other']):
            Question.objects.create(document=doc, question_order=index, fingerprint=f'preview-ranked-{index}',
                source_label=f'Q{index}', prompt_text=text)
        enqueue(Question.objects.values_list('pk', flat=True))
        self.assertFalse(process_queue(100, 30)['failed'])
        self.assertTrue(verify_workspace('drill')['valid'])
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(user)
        old = client.get('/api/drill/questions/', {'q': 'Fourier transform', 'sort': 'relevance'})
        preview = client.get('/api/drill/collection-preview/', {'source': 'practice', 'q': 'Fourier transform', 'sort': 'relevance'})
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual([row['question_uuid'] for row in preview.data['results']], [row['uuid'] for row in old.data['results']])
        changed = client.get('/api/drill/collection-preview/', {'source': 'practice', 'q': 'Fourier transform', 'index_version': 'stale'})
        self.assertEqual(changed.status_code, 409)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL repeatable-read snapshot test')
@override_settings(**SETTINGS)
class CollectionPreviewSnapshotTests(TransactionTestCase):
    def test_concurrent_delete_does_not_mix_ids_version_and_hydration(self):
        from . import collection_preview
        user = get_user_model().objects.create_user('snapshot-preview')
        doc = QuestionDocument.objects.create(source_id=99401, workspace='drill', filename='snapshot.pdf',
            title='Snapshot fixture', sha256='snapshot-doc', page_count=1)
        question = Question.objects.create(document=doc, question_order=1, fingerprint='snapshot-question',
            prompt_text='Visible in original snapshot')
        client = APIClient(HTTP_HOST='drill.test')
        client.force_authenticate(user)
        original_hydrate = collection_preview._hydrate
        failures = []

        def delete_concurrently():
            try:
                Question.objects.filter(pk=question.pk).delete()
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        def hydrate_after_delete(*args):
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_isolation')
                self.assertEqual(cursor.fetchone()[0], 'repeatable read')
                cursor.execute('SHOW transaction_read_only')
                self.assertEqual(cursor.fetchone()[0], 'on')
            writer = threading.Thread(target=delete_concurrently)
            writer.start()
            writer.join(timeout=10)
            self.assertFalse(writer.is_alive(), 'Concurrent writer blocked unexpectedly')
            self.assertEqual(failures, [])
            return original_hydrate(*args)

        with patch.object(collection_preview, '_hydrate', side_effect=hydrate_after_delete):
            response = client.get('/api/drill/collection-preview/', {'source': 'practice'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['count'], len(response.data['results'])), (1, 1))
        self.assertEqual(response.data['results'][0]['preview']['question_markdown'], 'Visible in original snapshot')
        refreshed = client.get('/api/drill/collection-preview/', {'source': 'practice'})
        self.assertEqual(refreshed.data['count'], 0)
        self.assertNotEqual(response.data['collection_version'], refreshed.data['collection_version'])
