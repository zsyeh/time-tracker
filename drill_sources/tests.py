import hashlib
import io
import json
from pathlib import Path
import tempfile
import pymupdf

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from drill.models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionRevision
from drill.views import DrillHeatmapView, DrillQuestionAttemptView, DrillQuestionDetailView
from .models import SourceQuestionAnchor


@override_settings(ALLOWED_HOSTS=['*'], EI_HOSTS={'ei.test'})
class SourceQuestionTrackingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='source-owner')
        self.other = get_user_model().objects.create_user(username='source-other')
        self.doc = QuestionDocument.objects.create(source_id=98710, workspace='ei', title='真题（部分超纲）',
            sha256='a'*64, page_count=1, parser_strategy='ucas-reviewed-manifest-v1')
        self.source = Question.objects.create(document=self.doc, question_order=20250001, source_label='ucas:test:2025::paper',
            fingerprint='b'*64, content_mode='image', record_kind='grouped', source_category='past_exam', exam_year=2025)
        self.asset = QuestionAsset.objects.create(source_id=98711, question=self.source, image_data=b'original-full-page',
            sha256='c'*64, width=1200, height=1800, asset_type='question_crop')
        self.answer = QuestionAsset.objects.create(source_id=98712, question=self.source, image_data=b'original-answer-page',
            sha256='d'*64, width=1200, height=1800, asset_type='answer_crop')
        QuestionAttempt.objects.create(user=self.user, question=self.source, result='correct')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'index.json'
        self.manifest = {'schema_version':1, 'papers':[{'source_fingerprint':self.source.fingerprint, 'complete':True,
            'items':[{'key':f'section-1-item-{n}', 'label':f'填空{n}', 'position':n, 'question_order':202500100+n,
                      'asset_source_id':self.asset.source_id, 'y':n*.3, 'confidence':.95} for n in (1,2)]}]}
        self.path.write_text(json.dumps(self.manifest))
        self.factory = APIRequestFactory()

    def run_index(self, **kwargs):
        call_command('index_source_questions', str(self.path), stdout=io.StringIO(), **kwargs)

    def request(self, view, question=None, data=None, user=None):
        request = self.factory.post('/',data,format='json',HTTP_HOST='ei.test') if data else self.factory.get('/',HTTP_HOST='ei.test')
        force_authenticate(request,user=user or self.user)
        return view.as_view()(request,**({'question_uuid':question.uuid} if question else {}))

    def test_dry_run_and_repeat_do_not_copy_images_or_erase_states(self):
        self.run_index(dry_run=True)
        self.assertEqual(Question.objects.count(),1)
        self.assertEqual(SourceQuestionAnchor.objects.count(),0)
        self.run_index()
        first=SourceQuestionAnchor.objects.order_by('position').first().question
        QuestionAttempt.objects.create(user=self.user,question=first,result='review',note='Keep my state')
        self.run_index()
        self.assertEqual(Question.objects.count(),3)
        self.assertEqual(QuestionAsset.objects.count(),2)
        self.assertEqual(SourceQuestionAnchor.objects.count(),2)
        self.assertTrue(QuestionAttempt.objects.filter(question=first,note='Keep my state').exists())
        self.source.refresh_from_db();self.assertFalse(self.source.is_practiceable)
        self.assertTrue(QuestionAttempt.objects.filter(question=self.source,result='correct').exists())

    def test_shared_full_paper_images_and_independent_user_progress(self):
        self.run_index()
        first,second=[a.question for a in SourceQuestionAnchor.objects.order_by('position')]
        before=self.request(DrillQuestionDetailView,first)
        self.assertEqual(before.status_code,200)
        self.assertEqual(before.data['state'],'unattempted')
        self.assertEqual(before.data['source_context']['anchor'],{'asset_id':self.asset.pk,'y':.3})
        self.assertEqual(before.data['question_assets'][0]['id'],self.asset.pk)
        self.assertEqual(before.data['answer_assets'][0]['id'],self.answer.pk)
        response=self.request(DrillQuestionAttemptView,first,{'result':'correct'})
        self.assertIn(response.status_code,(200,201))
        self.assertEqual(self.request(DrillQuestionDetailView,first).data['state'],'mastered')
        second_detail=self.request(DrillQuestionDetailView,second)
        self.assertEqual(second_detail.data['state'],'unattempted')
        self.assertEqual(second_detail.data['source_context']['anchors'][0]['state'],'mastered')
        other_detail=self.request(DrillQuestionDetailView,second,user=self.other)
        self.assertEqual(other_detail.data['source_context']['anchors'][0]['state'],'unattempted')
        heatmap=self.request(DrillHeatmapView)
        rows=heatmap.data['groups'][0]['questions']
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row['source_indexed'] for row in rows))
        self.assertEqual({row['uuid']:row['state'] for row in rows},{str(first.uuid):'mastered',str(second.uuid):'unattempted'})

    def test_locator_cannot_use_another_question_image(self):
        self.run_index()
        anchor=SourceQuestionAnchor.objects.first()
        anchor.asset=self.answer
        with self.assertRaises(ValidationError):anchor.full_clean()

    def test_bad_normalized_coordinate_rolls_back(self):
        self.manifest['papers'][0]['items'][1]['y']=1.5
        self.path.write_text(json.dumps(self.manifest))
        with self.assertRaises(Exception):self.run_index()
        self.assertEqual(Question.objects.count(),1)
        self.assertFalse(SourceQuestionAnchor.objects.exists())

    def region_manifest(self):
        self.run_index()
        question = SourceQuestionAnchor.objects.order_by('position').first().question
        pdf = pymupdf.open(); page = pdf.new_page(width=600, height=800)
        page.insert_text((50, 230), 'Question with circuit:')
        page.draw_rect(pymupdf.Rect(300, 210, 500, 430))
        path = Path(self.temp.name)/'source.pdf'; pdf.save(path); pdf.close()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        path.rename(path.with_name(f'{sha}.pdf'))
        manifest = {'schema_version': 1, 'profile': 'ei-full-width-whitespace-v1', 'review': [],
            'questions': [{'fingerprint': question.fingerprint, 'source_fingerprint': self.source.fingerprint,
                'key': question.source_anchor.key, 'confidence': .95,
                'question_regions': [{'source': sha, 'page_index': 0, 'bbox': [0, 200, 600, 480]}]}]}
        manifest_path = Path(self.temp.name)/'regions.json'
        manifest_path.write_text(json.dumps(manifest))
        return question, manifest, manifest_path

    def render(self, path, **options):
        output = io.StringIO()
        call_command('render_source_question_regions', str(path), source_dir=[Path(self.temp.name)], stdout=output, **options)
        return output.getvalue()

    def test_individual_crop_keeps_originals_answers_progress_and_paper_revision(self):
        first, manifest, path = self.region_manifest()
        attempt = QuestionAttempt.objects.create(user=self.user, question=first, result='review', note='Do not overwrite')
        self.render(path, dry_run=True)
        self.assertEqual(QuestionAsset.objects.count(), 2)
        self.render(path); self.assertIn('"new_images": 0', self.render(path))
        detail = self.request(DrillQuestionDetailView, first).data
        self.assertNotIn('source_context', detail)
        self.assertEqual(detail['original_source']['uuid'], str(self.source.uuid))
        self.assertEqual(detail['answer_scope'], 'source_paper')
        self.assertEqual(detail['answer_assets'][0]['id'], self.answer.pk)
        self.assertNotEqual(detail['question_assets'][0]['id'], self.asset.pk)
        self.assertEqual(detail['state'], 'review')
        self.assertEqual(QuestionRevision.capture(first).assets.count(), 2)
        self.asset.refresh_from_db(); self.assertEqual(bytes(self.asset.image_data), b'original-full-page')
        attempt.refresh_from_db(); self.assertEqual(attempt.note, 'Do not overwrite')
        self.assertEqual(Question.objects.count(), 3)

    def test_half_width_or_conflicting_crops_are_rejected(self):
        first, manifest, path = self.region_manifest()
        manifest['questions'][0]['question_regions'][0]['bbox'][2] = 500
        path.write_text(json.dumps(manifest))
        with self.assertRaises(Exception): self.render(path)
        self.assertEqual(QuestionAsset.objects.count(), 2)
        manifest['questions'][0]['question_regions'][0]['bbox'][2] = 600
        path.write_text(json.dumps(manifest)); self.render(path)
        with self.assertRaises(Exception): self.render(path, dpi=200)
        self.assertEqual(QuestionAsset.objects.count(), 3)


class ConservativeSegmentationTests(TestCase):
    def page(self):
        pdf = pymupdf.open(); page = pdf.new_page(width=600, height=800)
        self.addCleanup(pdf.close)
        return page

    def test_tall_circuit_beside_text_prevents_an_unsafe_cut(self):
        from .segmentation import whitespace_boundary
        page = self.page()
        page.draw_rect(pymupdf.Rect(300, 30, 500, 190), width=2)
        self.assertIsNone(whitespace_boundary(page, 100, []))

    def test_scanner_frame_does_not_prevent_a_safe_full_width_cut(self):
        from .segmentation import whitespace_boundary
        page = self.page()
        page.draw_line(pymupdf.Point(40, 0), pymupdf.Point(40, 800), width=1)
        page.insert_text((80, 115), 'Question 2 with circuit below')
        page.draw_rect(pymupdf.Rect(300, 140, 500, 280), width=2)
        cut = whitespace_boundary(page, 100, [])
        self.assertIsNotNone(cut); self.assertLess(cut, 100)

    def test_ocr_box_crossing_candidate_band_is_not_cut(self):
        from .segmentation import whitespace_boundary
        page = self.page()
        self.assertIsNone(whitespace_boundary(page, 100, [{'text':'tall diagram caption', 'bbox':[10,0,500,150]}]))

    def test_a_prior_option_must_not_be_added_above_current_question(self):
        from .segmentation import whitespace_boundary
        page = self.page()
        page.draw_rect(pymupdf.Rect(50, 90, 500, 99), fill=(0,0,0))
        self.assertIsNone(whitespace_boundary(page, 100, [{'text':'previous option D', 'bbox':[50,90,500,99]}]))

    def test_an_incomplete_paper_only_allows_verified_consecutive_items(self):
        from .segmentation import interval_verified
        paper = {'complete': False}
        items = [{'key': f'main-{n}'} for n in (1,2,4,5)]
        audit = {'issues':[{'reason':'missing_main_sections','missing':[3]}],
                 'sections':[[n, ''] for n in (1,2,4,5)]}
        self.assertTrue(interval_verified(paper, items, 0, audit))
        self.assertFalse(interval_verified(paper, items, 1, audit))
        self.assertTrue(interval_verified(paper, items, 2, audit))
        self.assertFalse(interval_verified(paper, items, 0, None))
        audit['sections'].append([6, 'Unindexed final section'])
        self.assertFalse(interval_verified(paper, items, 3, audit))
