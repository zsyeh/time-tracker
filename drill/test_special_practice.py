from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from io import StringIO
from . import test_focus_training
from .special_practice import push_special_practice
from .models import ExamPaper,QuestionAttempt

@override_settings(DRILL_HOSTS=['testserver'])
class SpecialPracticeTests(TestCase):
    setUp=test_focus_training.FocusTrainingTests.setUp
    question=test_focus_training.FocusTrainingTests.question
    def push(self,ids,key='test'):
        return push_special_practice(user=self.user,workspace='drill',key=key,title='导数专项',question_uuids=ids)
    def test_order_idempotency_and_no_automatic_attempts(self):
        a,b=self.question(1),self.question(2)
        p,created=self.push([str(b.uuid),str(a.uuid)])
        self.assertTrue(created)
        self.assertEqual(list(p.items.order_by('position').values_list('question_id',flat=True)),[b.pk,a.pk])
        self.assertFalse(self.push([str(b.uuid),str(a.uuid)])[1])
        self.assertEqual(QuestionAttempt.objects.count(),0)
        with self.assertRaises(ValueError):self.push([str(a.uuid),str(b.uuid)])
    def test_invalid_push_is_atomic_and_workspace_scoped(self):
        q=self.question(1)
        for ids in [[str(q.uuid)]*2,['00000000-0000-0000-0000-000000000001']]:
            with self.assertRaises(ValueError):self.push(ids)
        with self.assertRaises(ValueError):
            push_special_practice(user=self.user,workspace='ei',key='x',title='x',question_uuids=[str(q.uuid)])
        self.assertEqual(ExamPaper.objects.filter(blueprint__code__startswith='special-practice-').count(),0)
    def test_api_is_private_not_in_exams_and_supports_collection_navigation(self):
        a,b=self.question(1),self.question(2)
        paper,_=self.push([str(b.uuid),str(a.uuid)])
        self.client.force_login(self.user)
        result=self.client.get('/api/drill/special-practice/').json()['results']
        self.assertEqual(result[0]['first_question'],str(b.uuid));self.assertEqual(result[0]['question_count'],2)
        self.assertEqual(self.client.get('/api/drill/papers/').json()['results'],[])
        preview=self.client.get('/api/drill/collection-preview/',{'source':'paper','paper':str(paper.uuid)})
        self.assertEqual(preview.status_code,200)
        self.assertEqual([v['question_uuid'] for v in preview.json()['results']],[str(b.uuid),str(a.uuid)])
        self.assertEqual(self.client.get('/drill/special-practice').status_code,200)
        self.client.force_login(get_user_model().objects.create_user('special-other'))
        self.assertEqual(self.client.get('/api/drill/special-practice/').json()['results'],[])
        self.assertEqual(self.client.get('/api/drill/collection-preview/',{'source':'paper','paper':str(paper.uuid)}).status_code,404)
