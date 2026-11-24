from django.test import TestCase
from . import test_focus_training
from .paper_generator import PaperGenerator
from .views import exam_paper_payload, paper_queryset

class ExamAnswerLockTests(TestCase):
    setUp=test_focus_training.FocusTrainingTests.setUp
    question=test_focus_training.FocusTrainingTests.question
    def test_private_review_payload_hides_images_until_completed(self):
        self.question(1);p=PaperGenerator().generate(user=self.user,blueprint=self.bp,include_mastered=True)
        payload=exam_paper_payload(paper_queryset(self.user).get(pk=p.pk),review=True)
        self.assertEqual(payload['items'][0]['question']['answer_assets'],[])
        self.assertEqual(payload['items'][0]['question']['answer_markdown'],'')
        p.status='in_progress';p.save()
        self.assertEqual(exam_paper_payload(paper_queryset(self.user).get(pk=p.pk),review=True)['items'][0]['question']['answer_assets'],[])
        p.status='completed';p.save()
        self.assertTrue(exam_paper_payload(paper_queryset(self.user).get(pk=p.pk),review=True)['items'][0]['question']['answer_assets'])

    def test_conditional_undo_does_not_delete_a_newer_practice_attempt(self):
        from .models import QuestionAttempt
        q=self.question(1)
        first=QuestionAttempt.objects.create(user=self.user,question=q,result='review')
        newer=QuestionAttempt.objects.create(user=self.user,question=q,result='correct')
        self.client.force_login(self.user)
        url=f'/api/drill/questions/{q.uuid}/attempts/'
        response=self.client.delete(url+f'?expected_attempt_id={first.pk}')
        self.assertEqual(response.status_code,409)
        self.assertTrue(QuestionAttempt.objects.filter(pk=newer.pk).exists())
        response=self.client.delete(url+f'?expected_attempt_id={newer.pk}')
        self.assertEqual(response.status_code,200)
        self.assertFalse(QuestionAttempt.objects.filter(pk=newer.pk).exists())
