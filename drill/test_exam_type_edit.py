from .test_final_exam_types import FinalExamTypeTests
from .models import QuestionExamTypeEdit, QuestionExamType


class ExamTypeEditTests(FinalExamTypeTests):
    def url(self, question=None):
        return f'/api/drill/questions/{(question or self.questions[0]).uuid}/exam-type/'

    def edit(self, label='fill', **kwargs):
        current = self.client.get(self.url()).data
        return self.client.patch(self.url(), {'question_type': label,
            'expected_updated_at': current['classification']['updated_at'], **kwargs}, format='json')

    def test_edit_updates_final_reads_and_preserves_ai_and_legacy_history(self):
        response = self.edit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['question_type'], 'fill')
        self.questions[0].refresh_from_db()
        self.assertEqual(self.questions[0].question_type, 'solution')
        change = QuestionExamTypeEdit.objects.get()
        self.assertEqual(change.actor, self.user)
        self.assertEqual(change.before['question_type'], 'choice')
        self.assertEqual(change.before['model_id'], 'gpt-6.1-terra')
        self.assertTrue(change.before['review_required'])
        self.assertEqual(change.after['classification_source'], 'human')
        self.assertTrue(change.after['batch_id'].startswith('manual_'))
        detail = self.client.get(self.url().replace('exam-type/', '')).data
        self.assertEqual(detail['question_type'], 'fill')
        self.assertFalse(detail['classification']['review_required'])

    def test_invalid_workspace_auth_and_read_only_methods(self):
        self.assertEqual(self.edit('judgment').status_code, 400)
        self.assertEqual(self.client.patch(self.url(), {}, format='json', HTTP_HOST='ei.test').status_code, 404)
        self.assertEqual(self.client.post(self.url(), {}, format='json').status_code, 405)
        self.client.force_authenticate(None)
        self.assertIn(self.client.patch(self.url(), {}, format='json').status_code, (401, 403))
        self.assertFalse(QuestionExamTypeEdit.objects.exists())

    def test_stale_update_rejected_and_same_type_is_idempotent(self):
        previous = self.client.get(self.url()).data['classification']['updated_at']
        self.assertEqual(self.edit().status_code, 200)
        result = self.client.patch(self.url(), {'question_type': 'large', 'expected_updated_at': previous}, format='json')
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.edit().status_code, 200)
        self.assertEqual(QuestionExamTypeEdit.objects.count(), 1)

    def test_unknown_and_legacy_only_record_can_be_saved(self):
        self.assertEqual(self.edit('unknown').status_code, 200)
        self.assertTrue(QuestionExamType.objects.get(question=self.questions[0]).review_required)
        QuestionExamType.objects.filter(question=self.questions[0]).delete()
        result = self.client.patch(self.url(), {'question_type': 'large', 'expected_updated_at': None}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data['classification']['content_hash']), 64)

    def test_ei_all_formats_and_csrf(self):
        self.doc.workspace = 'ei'
        self.doc.save()
        self.client.defaults['HTTP_HOST'] = 'ei.test'
        self.assertEqual(self.edit('judgment').status_code, 200)
        self.assertEqual(self.edit('short_answer').status_code, 200)
        from rest_framework.test import APIClient
        session_client = APIClient(enforce_csrf_checks=True, HTTP_HOST='ei.test')
        session_client.force_login(self.user)
        self.assertEqual(session_client.patch(self.url(), {'question_type':'choice'}, format='json').status_code, 403)
