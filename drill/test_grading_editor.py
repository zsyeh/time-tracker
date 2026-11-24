from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from . import test_exam_grading
from .models import QuestionAttempt, QuestionUserState
from .exam_grading import import_grading
from .exam_grading_views import PaperGradingItemView

@override_settings(ALLOWED_HOSTS=['ei.ehzsy.site','drill.ehzsy.site'],EI_HOSTS={'ei.ehzsy.site'},DRILL_HOSTS={'drill.ehzsy.site'})
class GradingEditorTests(TestCase):
    setUp=test_exam_grading.ExamGradingTests.setUp
    question=test_exam_grading.ExamGradingTests.question
    fixture=test_exam_grading.ExamGradingTests.fixture
    def prepare(self):
        p,q,token,data=self.fixture();import_grading(user=self.user,share_token=token,data=data,apply=True)
        return p,q
    def patch(self,p,q,changes,expected,*,user=None,host='ei.ehzsy.site'):
        request=APIRequestFactory().patch('/',{'expected_question_uuid':str(q.uuid),'changes':changes,'expected':expected},format='json',HTTP_HOST=host)
        force_authenticate(request,user=user or self.user)
        return PaperGradingItemView.as_view()(request,paper_uuid=p.uuid,position=1)
    def test_private_edits_preserve_source_score_and_history(self):
        p,q=self.prepare();before=q.answer_markdown
        result=self.patch(p,q,{'reference':'复核参考','note':'新批阅','user_answer':'新作答','priority':'P0'},
                         {'reference':'','note':'检查参考方向','user_answer':'原回答','priority':'P1'})
        # The fixture omits reference, treated as an empty string.
        self.assertEqual(result.status_code,200)
        p.refresh_from_db();q.refresh_from_db();item=p.items.get()
        self.assertEqual(q.answer_markdown,before);self.assertEqual(item.self_score,1.5)
        self.assertEqual(item.user_answer,'新作答');self.assertIn('新批阅',item.self_note)
        state=QuestionUserState.objects.get(question=q);self.assertIn('P0 · 新批阅',state.note)
        self.assertEqual(QuestionAttempt.objects.count(),0)
        self.assertEqual(p.generation_options['grading']['edit_history'][0]['changes']['note']['before'],'检查参考方向')
    def test_stale_field_rejected(self):
        p,q=self.prepare()
        self.assertEqual(self.patch(p,q,{'note':'first'},{'note':'检查参考方向'}).status_code,200)
        self.assertEqual(self.patch(p,q,{'note':'stale'},{'note':'检查参考方向'}).status_code,409)
    def test_unchanged_replay_does_not_add_history(self):
        p,q=self.prepare();self.patch(p,q,{'note':'检查参考方向'},{'note':'检查参考方向'})
        p.refresh_from_db();self.assertNotIn('edit_history',p.generation_options['grading'])
    def test_account_and_workspace_isolation(self):
        p,q=self.prepare();other=get_user_model().objects.create_user('editor-other')
        self.assertEqual(self.patch(p,q,{'note':'bad'},{'note':'检查参考方向'},user=other).status_code,404)
        self.assertEqual(self.patch(p,q,{'note':'bad'},{'note':'检查参考方向'},host='drill.ehzsy.site').status_code,404)
    def test_score_field_cannot_be_changed(self):
        p,q=self.prepare()
        self.assertEqual(self.patch(p,q,{'earned':'3'},{'earned':'1.5'}).status_code,400)
