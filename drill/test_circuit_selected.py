from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .circuit_selected import manifest, review_manifest
from .circuit_selected_views import CircuitSelectedView
from .models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionErratum
from .views import DrillQuestionDetailView
from .web_views import _safe_drill_target


class CircuitManifestTests(SimpleTestCase):
    def test_full_inventory_partition_and_stable_canonical_ids(self):
        m=manifest(); r=review_manifest()
        ids=[q['uuid'] for q in m['questions']]+[q['uuid'] for q in r['records']]
        self.assertEqual(len(ids),457);self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(len(m['questions']),211)
        self.assertEqual(sum(q['status']=='review' for q in r['records']),177)
        self.assertEqual(sum(q['status']=='excluded' for q in r['records']),69)
        for row in m['questions']:
            uuid.UUID(row['uuid'])
            self.assertEqual(len(row['fingerprint']),64)
            self.assertIn(row['bucket'],{b['key'] for b in m['buckets']})
            self.assertTrue(row['reason']);self.assertTrue(row['evidence'])
        self.assertEqual([b['rank'] for b in m['buckets']],list(range(1,12)))
        self.assertEqual(sum(q['combined_first_order_thevenin'] for q in m['questions']),12)

    def test_second_order_and_cross_domain_are_not_silently_first_order(self):
        m=manifest();rows={q['label']:q for q in m['questions'] if q['document_id']==22}
        for n in [21,22,23,24,25,26,36,37]:self.assertEqual(rows[f'课后题 7-{n}']['bucket'],'second_order')
        for q in m['questions']:
            if q['bucket']=='laplace':self.assertEqual(q['tier'],'cross')
        self.assertEqual(_safe_drill_target('/circuit-selected?tier=core',site='ei'),'/circuit-selected?tier=core')


@override_settings(ALLOWED_HOSTS=['*'],EI_HOSTS={'ei.test'},DRILL_HOSTS={'drill.test'})
class CircuitCollectionTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='circuit-owner')
        self.other=get_user_model().objects.create_user(username='other-owner')
        self.doc=QuestionDocument.objects.create(source_id=87001,workspace='ei',title='电路',sha256='a'*64,page_count=0)
        self.doc2=QuestionDocument.objects.create(source_id=87002,workspace='ei',title='电路课后题',sha256='b'*64,page_count=2)
        self.q1=Question.objects.create(document=self.doc,question_order=1,fingerprint='1'*64,prompt_text='RC switch',answer_markdown='Response')
        self.q2=Question.objects.create(document=self.doc2,question_order=2,fingerprint='2'*64,prompt_text='Thevenin',answer_markdown='Answer')
        self.q3=Question.objects.create(document=self.doc2,question_order=3,fingerprint='3'*64,prompt_text='Needs answer')
        self.outside=Question.objects.create(document=self.doc2,question_order=4,fingerprint='4'*64,prompt_text='Unselected',answer_markdown='Answer')
        self.rows=[]
        for q,bucket in [(self.q1,'first_order'),(self.q2,'first_order'),(self.q3,'thevenin')]:
            self.rows.append({'uuid':str(q.uuid),'fingerprint':q.fingerprint,'bucket':bucket,'tier':'core','kind':'calculation','tags':[bucket],'reason':['reviewed source'],'combined_first_order_thevenin':False})
        m={'title':'电路严选','basis':'Subjective study priorities, not probabilities','inventory_count':4,'questions':self.rows,
           'buckets':[{'key':key,'title':key,'rank':i,'tier':'core','focus':'Practice'} for i,key in enumerate(['first_order','thevenin'],1)]}
        for target,value in [('drill.circuit_selected.manifest',m),('drill.circuit_selected_views.manifest',m),('drill.circuit_selected_views.review_manifest',{'records':[{'uuid':str(self.outside.uuid),'label':'outside','status':'review','reason':['unclassified']}]})]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
        self.factory=APIRequestFactory()

    def get(self,query='',*,view=CircuitSelectedView,question=None,user=None,host='ei.test'):
        req=self.factory.get('/?'+query,HTTP_HOST=host);force_authenticate(req,user=user or self.user)
        return view.as_view()(req,**({'question_uuid':question.uuid} if question else {}))

    def test_collection_is_read_only_and_progress_is_shared_but_user_scoped(self):
        QuestionAttempt.objects.create(user=self.user,question=self.q1,result='correct')
        QuestionAttempt.objects.create(user=self.other,question=self.q2,result='review')
        before=(Question.objects.count(),QuestionAsset.objects.count(),QuestionAttempt.objects.count())
        data=self.get().data
        self.assertEqual(data['progress'],{'total':3,'attempted':1,'mastered':1,'unattempted':2})
        self.assertEqual(data['ready_count'],2)
        self.assertEqual(self.get(user=self.other).data['progress']['attempted'],1)
        self.assertEqual(before,(Question.objects.count(),QuestionAsset.objects.count(),QuestionAttempt.objects.count()))
        QuestionAttempt.objects.create(user=self.user,question=self.q1,result='reset')
        self.assertEqual(self.get().data['progress']['attempted'],0)

    def test_ready_material_gate_and_open_errata(self):
        self.assertEqual(self.get('material=ready').data['progress']['total'],2)
        QuestionErratum.objects.create(question=self.q1,reporter=self.user,description='Check diagram',status='open')
        self.assertEqual(self.get('material=ready').data['progress']['total'],1)
        self.assertTrue(self.get().data['groups'][0]['questions'][0]['has_open_erratum'])

    def test_filters_and_latest_state_do_not_leak_other_users(self):
        QuestionAttempt.objects.create(user=self.user,question=self.q1,result='review')
        self.assertEqual(self.get('bucket=thevenin').data['progress']['total'],1)
        self.assertEqual(self.get('state=review').data['progress']['total'],1)
        self.assertEqual(self.get('state=review',user=self.other).data['progress']['total'],0)
        self.assertEqual(self.get('state=unattempted').data['progress']['total'],2)
        for query in ['bucket=bad','tier=bad','kind=bad','state=bad']:self.assertEqual(self.get(query).status_code,404)
        self.assertEqual(self.get(host='drill.test').status_code,404)

    def test_navigation_crosses_books_but_never_leaves_selected_bucket(self):
        query='collection=circuit_selected&bucket=first_order&material=ready'
        first=self.get(query,view=DrillQuestionDetailView,question=self.q1).data
        self.assertEqual(first['sequential_next_question_uuid'],str(self.q2.uuid))
        self.assertEqual(first['next_question_uuid'],str(self.q2.uuid))
        QuestionAttempt.objects.create(user=self.user,question=self.q1,result='correct')
        QuestionAttempt.objects.create(user=self.user,question=self.q2,result='correct')
        last=self.get(query,view=DrillQuestionDetailView,question=self.q2).data
        self.assertIsNone(last['next_question_uuid'])
        self.assertEqual(last['sequential_next_question_uuid'],str(self.q1.uuid))

    def test_stale_identity_or_out_of_scope_is_not_selected(self):
        self.q1.syllabus_scope='out_of_scope';self.q1.save(update_fields=['syllabus_scope'])
        self.q2.fingerprint='f'*64;self.q2.save(update_fields=['fingerprint'])
        self.assertEqual(self.get().data['progress']['total'],1)
