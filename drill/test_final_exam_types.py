from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Question, QuestionAttempt, QuestionDocument, QuestionExamType


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['drill.test', 'ei.test'], DRILL_HOSTS={'drill.test'}, EI_HOSTS={'ei.test'})
class FinalExamTypeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('final-types')
        self.client = APIClient(HTTP_HOST='drill.test')
        self.client.force_authenticate(self.user)
        self.doc = QuestionDocument.objects.create(workspace='drill', source_id=771,
            filename='types.pdf', title='Types', sha256='a'*64, page_count=1)
        self.questions = []
        for index, (old, new) in enumerate((('solution','choice'),('single_choice','unknown'),
                                            ('single_choice','large'),('solution','fill')), 1):
            q = Question.objects.create(document=self.doc, question_order=index,
                source_label=f'Q{index}', fingerprint=str(index)*64, is_practiceable=True,
                prompt_text='Question', question_type=old)
            QuestionExamType.objects.create(question=q, source_system='drill', question_type=new,
                classification_source='ai_image', model_id='gpt-6.1-terra', classification_version='exam-form-v1',
                content_hash='b'*64, review_required=True, review_reasons=['legacy_type_conflict'], batch_id='test_batch')
            self.questions.append(q)

    def test_audited_final_types_and_unknown_are_used_in_lists_and_details(self):
        response = self.client.get('/api/drill/questions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([q['question_type'] for q in response.data['results']], ['choice','unknown','large','fill'])
        detail = self.client.get(f'/api/drill/questions/{self.questions[0].uuid}/').data
        self.assertEqual(detail['question_type'], 'choice')
        self.assertEqual(detail['legacy_question_type'], 'solution')
        self.assertTrue(detail['classification']['review_required'])
        unknown = self.client.get('/api/drill/questions/?type_group=unknown').data
        self.assertEqual(unknown['count'], 1)
        self.assertEqual(unknown['results'][0]['uuid'], str(self.questions[1].uuid))

    def test_heatmap_statistics_and_next_previous_remain_inside_type_filter(self):
        QuestionAttempt.objects.create(user=self.user,question=self.questions[0],result='correct')
        QuestionAttempt.objects.create(user=self.user,question=self.questions[2],result='review')
        data = self.client.get('/api/drill/heatmap/?scope=all&type_group=small').data
        self.assertEqual(data['question_count'], 2)
        self.assertEqual(data['statistics']['attempted_question_count'], 1)
        self.assertEqual(data['statistics']['review_question_count'], 0)
        self.assertEqual(data['type_statistics']['small']['total'], 2)
        self.assertEqual({q['question_type'] for g in data['groups'] for q in g['questions']},{'choice','fill'})
        first = self.client.get(f'/api/drill/questions/{self.questions[0].uuid}/?type_group=small').data
        self.assertEqual(first['sequential_next_question_uuid'],str(self.questions[3].uuid))
        self.assertIsNone(first['next_review_uuid'])
        last = self.client.get(f'/api/drill/questions/{self.questions[3].uuid}/?type_group=small').data
        self.assertEqual(last['previous_question_uuid'],str(self.questions[0].uuid))
        self.assertEqual(last['sequential_next_question_uuid'],str(self.questions[0].uuid))

    def test_workspace_and_invalid_filter(self):
        self.assertEqual(self.client.get('/api/drill/questions/?type_group=invalid').status_code,400)
        self.assertEqual(self.client.get('/api/drill/questions/',HTTP_HOST='ei.test').data['count'],0)
