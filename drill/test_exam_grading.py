from django.test import TestCase
from django.contrib.auth import get_user_model
from . import test_focus_training
from .models import ExamPaper, ExamPaperItem, QuestionRevision, DrillContentShare, QuestionUserState, QuestionAttempt
from .exam_grading import import_grading, SUBJECTS
from .views import exam_paper_payload, paper_queryset

class ExamGradingTests(TestCase):
    setUp = test_focus_training.FocusTrainingTests.setUp
    question = test_focus_training.FocusTrainingTests.question

    def fixture(self):
        self.bp.subject='ei';self.bp.save()
        self.doc.workspace='ei';self.doc.save()
        self.section.title='电路原理 · 填空';self.section.save()
        q=self.question(1)
        p=ExamPaper.objects.create(user=self.user, blueprint=self.bp, seed=1, mode='standard')
        ExamPaperItem.objects.create(paper=p, section=self.section, question=q,
          question_revision=QuestionRevision.capture(q), position=1, score=3, selected_fingerprint=q.fingerprint)
        _,token,_=DrillContentShare.get_or_issue(owner=self.user,workspace='ei',paper=p)
        data={'title':'非官方测试','exam_date':'2026-11-24','actual_duration_seconds':4200,
              'weaknesses':{s:'复习笔记' for s in SUBJECTS},'items':[{'position':1,'question_uuid':str(q.uuid),
              'raw_score':2.5,'status':'partial','user_answer':'原回答','note':'检查参考方向','priority':'P1'}]}
        return p,q,token,data

    def test_partial_score_idempotence_and_preserve_learning(self):
        p,q,token,data=self.fixture()
        QuestionUserState.objects.create(user=self.user,question=q,note='已有笔记',is_favorite=True)
        QuestionAttempt.objects.create(user=self.user,question=q,result='correct')
        preview=import_grading(user=self.user,share_token=token,data=data)
        self.assertEqual(preview['score'],1.5);self.assertEqual(p.items.get().self_score,None)
        result=import_grading(user=self.user,share_token=token,data=data,apply=True)
        state=QuestionUserState.objects.get(question=q);version=state.version
        self.assertTrue(state.is_favorite);self.assertTrue(state.review_later);self.assertIn('已有笔记',state.note)
        self.assertEqual(QuestionAttempt.objects.count(),1)
        self.assertTrue(import_grading(user=self.user,share_token=token,data=data,apply=True)['unchanged'])
        state.refresh_from_db();self.assertEqual(state.version,version)
        self.assertEqual(p.items.get().self_score,1.5)
        payload=exam_paper_payload(paper_queryset(self.user).get(pk=p.pk),review=True)
        self.assertEqual(payload['grading']['score'],1.5)
        self.assertNotIn('grading',exam_paper_payload(paper_queryset(self.user).get(pk=p.pk)))

    def test_mapping_mismatch_no_writes(self):
        p,q,token,data=self.fixture();data['items'][0]['question_uuid']='bad'
        with self.assertRaises(ValueError):import_grading(user=self.user,share_token=token,data=data,apply=True)
        self.assertEqual(p.items.get().result,'unanswered');self.assertEqual(QuestionUserState.objects.count(),0)

    def test_owner_isolation(self):
        p,q,token,data=self.fixture();other=get_user_model().objects.create_user('other-grading')
        with self.assertRaises(DrillContentShare.DoesNotExist):import_grading(user=other,share_token=token,data=data,apply=True)

    def test_correct_does_not_set_global_mastery(self):
        p,q,token,data=self.fixture();data['items'][0].update(status='correct',raw_score=5)
        import_grading(user=self.user,share_token=token,data=data,apply=True)
        self.assertEqual(QuestionAttempt.objects.count(),0);self.assertEqual(QuestionUserState.objects.count(),0)

    def test_different_second_import_refused(self):
        p,q,token,data=self.fixture();import_grading(user=self.user,share_token=token,data=data,apply=True)
        data['items'][0]['raw_score']=1
        with self.assertRaises(ValueError):import_grading(user=self.user,share_token=token,data=data,apply=True)

    def test_only_explicit_user_mastery_creates_one_idempotent_record(self):
        p,q,token,data=self.fixture()
        data['items'][0].update(status='correct',raw_score=5,confirm_mastered=True)
        import_grading(user=self.user,share_token=token,data=data,apply=True)
        self.assertEqual(QuestionAttempt.objects.get().result,'correct')
        import_grading(user=self.user,share_token=token,data=data,apply=True)
        self.assertEqual(QuestionAttempt.objects.count(),1)
