from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from rest_framework.test import force_authenticate
from . import core_selected
from .models import QuestionAttempt
from .test_circuit_selected import CircuitCollectionTests as Fixture
from .views import DrillHeatmapView,DrillQuestionDetailView
from .web_views import _safe_drill_target


class CoreManifestTests(SimpleTestCase):
    def test_union_is_core_only_unique_and_has_five_courses(self):
        m=core_selected.manifest();rows=m['questions']
        self.assertEqual(len(rows),421);self.assertEqual(len({q['uuid'] for q in rows}),421)
        self.assertTrue(all(q['tier']=='core' for q in rows))
        self.assertEqual({q['course'] for q in rows},{c[0] for c in core_selected.COURSES})
        self.assertEqual(_safe_drill_target('/core-heatmap?course=analog',site='ei'),'/core-heatmap?course=analog')


@override_settings(ALLOWED_HOSTS=['*'],EI_HOSTS={'ei.test'},DRILL_HOSTS={'drill.test'})
class CoreHeatmapTests(TestCase):
    def setUp(self):
        Fixture.setUp(self)
        for i,row in enumerate(self.rows):row['course']='circuit' if i==0 else 'signal'
        m={'questions':self.rows,'buckets':[{'key':'first_order','title':'Dynamic'},{'key':'thevenin','title':'Equivalent'}]}
        p=patch('drill.core_selected.manifest',return_value=m);p.start();self.addCleanup(p.stop)

    def get(self,query='',*,view=DrillHeatmapView,question=None,host='ei.test',user=None):
        req=self.factory.get('/?collection=core_selected&scope=all&mode=questions&'+query,HTTP_HOST=host)
        force_authenticate(req,user=user or self.user)
        return view.as_view()(req,**({'question_uuid':question.uuid} if question else {}))

    def test_progress_and_timing_only_use_current_visible_core_questions(self):
        QuestionAttempt.objects.create(user=self.user,question=self.q1,result='correct',time_spent_seconds=10)
        QuestionAttempt.objects.create(user=self.user,question=self.outside,result='correct',time_spent_seconds=90)
        QuestionAttempt.objects.create(user=self.other,question=self.q2,result='correct',time_spent_seconds=50)
        response=self.get('material=ready');self.assertEqual(response.status_code,200)
        d=response.data;self.assertEqual(d['question_count'],2)
        self.assertEqual(d['statistics']['attempted_question_count'],1)
        self.assertEqual(d['statistics']['average_time_seconds'],10)
        self.assertEqual(d['curation_total'],3)
        self.assertEqual(self.get('material=ready&course=circuit').data['question_count'],1)

    def test_workspace_and_invalid_course(self):
        self.assertEqual(self.get(host='drill.test').status_code,404)
        self.assertEqual(self.get('course=unknown').status_code,404)
        self.assertEqual(self.get('scope=invalid').status_code,400)

    def test_question_navigation_keeps_course_and_material_filter(self):
        d=self.get('course=circuit&material=ready',view=DrillQuestionDetailView,question=self.q1).data
        self.assertIsNone(d['next_question_uuid'])
        self.assertIsNone(d['sequential_next_question_uuid'])
