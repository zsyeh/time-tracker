import hashlib
import io
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from drill.models import Question, QuestionAsset, QuestionAttempt, QuestionDocument
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
