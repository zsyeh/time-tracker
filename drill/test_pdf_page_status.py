from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Question, QuestionAttempt, QuestionDocument, QuestionReviewPlan, QuestionUserState
from .pdf_page_status_views import PdfPageStatusView, parse_page_expression


@override_settings(
    ALLOWED_HOSTS=['*'],
    DRILL_HOSTS={'drill.test'},
    EI_HOSTS={'ei.test'},
)
class PdfPageStatusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('pdf-page-owner')
        self.other = get_user_model().objects.create_user('pdf-page-other')
        self.document = QuestionDocument.objects.create(
            source_id=89001, workspace='ei', title='Signal', sha256='a' * 64, page_count=100,
        )
        self.q1 = Question.objects.create(
            document=self.document, question_order=1, display_label='Q1',
            prompt_text='One', fingerprint='1' * 64,
        )
        self.q2 = Question.objects.create(
            document=self.document, question_order=2, display_label='Q2',
            prompt_text='Two', fingerprint='2' * 64,
        )
        self.standard = Question.objects.create(
            document=self.document, question_order=3, display_label='Standard Q3',
            prompt_text='Standard', fingerprint='3' * 64,
        )
        self.mapping = {
            str(self.q1.uuid): {
                'course': 'signal', 'fingerprint': self.q1.fingerprint,
                'question': 12, 'answer': 9, 'paired': 20,
            },
            str(self.q2.uuid): {
                'course': 'signal', 'fingerprint': self.q2.fingerprint,
                'question': 13, 'answer': 10, 'paired': 21,
            },
            str(self.standard.uuid): {
                'course': 'signal', 'fingerprint': self.standard.fingerprint,
                'question': 14, 'answer': 11, 'paired': 22,
            },
        }
        self.allowlist = {
            'signal': {
                str(self.q1.uuid): self.q1.fingerprint,
                str(self.q2.uuid): self.q2.fingerprint,
            },
        }
        self.factory = APIRequestFactory()

    def call(self, body, *, host='ei.test', user=None):
        request = self.factory.post('/api/drill/pdf-page-status/', body, format='json', HTTP_HOST=host)
        force_authenticate(request, user=user or self.user)
        with patch('drill.ei_selected_pdf_pages._pages', return_value=self.mapping), patch(
            'drill.ei_selected_pdf_pages.selected_question_fingerprints', return_value=self.allowlist,
        ):
            return PdfPageStatusView.as_view()(request)

    def test_page_parser_supports_lists_ranges_and_chinese_punctuation(self):
        self.assertEqual(parse_page_expression('1, 3-5，8 8'), {1, 3, 4, 5, 8})
        with self.assertRaises(ValueError):
            parse_page_expression('5-3')
        with self.assertRaises(ValueError):
            parse_page_expression('1, hello')

    def test_preview_separates_books_deduplicates_and_does_not_write(self):
        response = self.call({
            'action': 'preview', 'course': 'signal', 'result': 'correct',
            'question_pages': '12-13, 99', 'paired_pages': '20, 21, 88',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_count'], 2)
        self.assertEqual(response.data['unmatched_question_pages'], [99])
        self.assertEqual(response.data['unmatched_paired_pages'], [88])
        self.assertEqual(len(response.data['questions'][0]['matched_by']), 2)
        self.assertIn('collection=signal_selected', response.data['questions'][0]['route'])
        self.assertEqual(QuestionAttempt.objects.count(), 0)

    def test_apply_appends_private_attempts_without_altering_history(self):
        old = QuestionAttempt.objects.create(user=self.user, question=self.q1, result='review')
        QuestionAttempt.objects.create(user=self.other, question=self.q1, result='review')
        response = self.call({
            'action': 'apply', 'course': 'signal', 'result': 'correct',
            'question_pages': '12', 'paired_pages': '21',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['created_count'], 2)
        self.assertTrue(QuestionAttempt.objects.filter(pk=old.pk, result='review').exists())
        self.assertEqual(QuestionAttempt.objects.filter(user=self.user).count(), 3)
        self.assertEqual(QuestionAttempt.objects.filter(user=self.other).count(), 1)
        self.assertEqual(
            set(QuestionAttempt.objects.filter(user=self.user).order_by('-pk')[:2].values_list('result', flat=True)),
            {'correct'},
        )

    def test_apply_records_the_same_diagnosis_dimensions_as_question_page(self):
        response = self.call({
            'action': 'apply', 'course': 'signal', 'result': 'review',
            'question_pages': '12', 'paired_pages': '',
            'error_codes': ['B2', 'C1'], 'primary_error': 'B2',
            'knowledge_level': 'K2', 'method_level': 'M1', 'execution_level': 'E1',
            'used_hint': True, 'viewed_answer': False, 'is_independent': True,
            'note': '先写出系统函数。',
        })
        self.assertEqual(response.status_code, 201)
        attempt = QuestionAttempt.objects.get(user=self.user, question=self.q1)
        self.assertEqual(attempt.outcome, 'incorrect')
        self.assertFalse(attempt.is_independent)
        self.assertEqual(attempt.training_stage, 'first')
        self.assertEqual(attempt.attempt_round, 1)
        self.assertEqual(attempt.method_level, 'M1')
        self.assertEqual(attempt.correction_note, '')
        self.assertEqual(
            QuestionUserState.objects.get(user=self.user, question=self.q1).note,
            '先写出系统函数。',
        )
        self.assertEqual(
            set(attempt.error_tags.values_list('code', 'is_primary')),
            {('B2', True), ('C1', False)},
        )
        self.assertTrue(QuestionReviewPlan.objects.filter(user=self.user, question=self.q1).exists())

    def test_stale_fingerprint_is_skipped_and_drill_host_is_not_exposed(self):
        self.mapping[str(self.q1.uuid)]['fingerprint'] = 'f' * 64
        self.allowlist['signal'][str(self.q1.uuid)] = 'f' * 64
        response = self.call({
            'action': 'apply', 'course': 'signal', 'result': 'review',
            'question_pages': '12', 'paired_pages': '',
        })
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['stale_mapping_count'], 1)
        self.assertEqual(QuestionAttempt.objects.count(), 0)
        hidden = self.call({
            'action': 'preview', 'course': 'signal', 'result': 'review',
            'question_pages': '12', 'paired_pages': '',
        }, host='drill.test')
        self.assertEqual(hidden.status_code, 404)

    def test_empty_and_invalid_inputs_are_rejected(self):
        empty = self.call({
            'action': 'preview', 'course': 'signal', 'result': 'correct',
            'question_pages': '', 'paired_pages': '',
        })
        self.assertEqual(empty.status_code, 400)
        invalid = self.call({
            'action': 'apply', 'course': 'signal', 'result': 'reset',
            'question_pages': '12', 'paired_pages': '',
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(QuestionAttempt.objects.count(), 0)

    def test_standard_bank_question_cannot_be_imported(self):
        response = self.call({
            'action': 'apply', 'course': 'signal', 'result': 'correct',
            'question_pages': '14', 'paired_pages': '22',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_count'], 0)
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['unmatched_question_pages'], [14])
        self.assertEqual(response.data['unmatched_paired_pages'], [22])
        self.assertFalse(QuestionAttempt.objects.filter(question=self.standard).exists())
