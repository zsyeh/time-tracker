import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Question, QuestionDocument, SignalFormulaMastery
from .four_subject_formula_library import (
    FORMULA_COUNTS as FOUR_FORMULA_COUNTS,
    FORMULA_LIBRARY as FOUR_FORMULA_LIBRARY,
)
from .signal_formula_library import FORMULA_LIBRARY, FOURIER_DAILY_KEYS
from .signal_formula_review_views import SignalFormulaReviewView


class SignalFormulaLibraryTests(SimpleTestCase):
    def test_fixed_library_keeps_all_sections_and_required_details(self):
        self.assertEqual(len(FORMULA_LIBRARY), 48)
        self.assertEqual(sum(len(item['formulas']) for item in FORMULA_LIBRARY), 125)
        self.assertEqual({item['section'] for item in FORMULA_LIBRARY}, set('ABCDEF'))
        formulas = '\n'.join(formula for item in FORMULA_LIBRARY for formula in item['formulas'])
        for required in (
            r'\delta(at)=\frac{1}{|a|}\delta(t)',
            r'e^{-at}\varepsilon(t)\leftrightarrow\frac{1}{a+j\omega}',
            r'f(t)e^{j\omega_0t}\leftrightarrow F(j(\omega-\omega_0))',
            r'Z\{x[n+1]\}=zX(z)-zx[0]',
            r'X_s(j\omega)=\frac{1}{T_s}\sum_{k=-\infty}^{+\infty}X(j(\omega-k\omega_s))',
        ):
            self.assertIn(required, formulas)

    def test_four_subject_library_is_complete_and_keeps_required_details(self):
        self.assertEqual(len(FOUR_FORMULA_LIBRARY), 268)
        self.assertEqual(FOUR_FORMULA_COUNTS, {
            'circuit': 77,
            'analog': 72,
            'digital': 55,
            'communication': 64,
        })
        formulas = '\n'.join(item['formulas'][0] for item in FOUR_FORMULA_LIBRARY)
        for required in (
            r'R_{\mathrm{Th}}=\frac{U_{\mathrm{test}}}{I_{\mathrm{test}}}',
            r'A_f=\frac{A}{1+AF}',
            r'[-X]_{\mathrm{comp}}=(\overline{[X]_2}+1)\bmod2^n',
            r'T_{clk}\ge t_{CQ,\max}+t_{comb,\max}+t_{setup}',
            r'h(t)=Ks^*(t_0-t)',
        ):
            self.assertIn(required, formulas)


@override_settings(ALLOWED_HOSTS=['*'], EI_HOSTS={'ei.test'}, DRILL_HOSTS={'drill.test'})
class SignalFormulaReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='formula-owner')
        self.document = QuestionDocument.objects.create(
            source_id=99201,
            workspace='ei',
            title='信号严选测试',
            sha256='9' * 64,
            page_count=1,
        )
        self.questions = []
        rows = []
        for index, bucket in enumerate(('fourier', 'fourier', 'convolution'), 1):
            question = Question.objects.create(
                document=self.document,
                question_order=index,
                fingerprint=str(index) * 64,
                prompt_text=f'Formula application {index}',
                answer_markdown='Answer',
            )
            self.questions.append(question)
            rows.append({
                'uuid': str(question.uuid),
                'fingerprint': question.fingerprint,
                'bucket': bucket,
                'tier': 'core',
                'kind': 'calculation',
                'reason': ['reviewed 892 source'],
                'combined_z_initial': False,
            })
        self.manifest = {
            'questions': rows,
            'buckets': [],
            'combination_key': 'combined_z_initial',
        }
        self.factory = APIRequestFactory()

    def request(self, method='get', *, data=None, query='date=2026-10-30', host='ei.test'):
        request = getattr(self.factory, method)(
            '/api/drill/signal-formulas/?' + query,
            data=data or {},
            format='json',
            HTTP_HOST=host,
        )
        force_authenticate(request, user=self.user)
        with patch('drill.signal_formula_review_views.signal_manifest', return_value=self.manifest), patch.dict(
            'drill.signal_formula_review_views.FOUR_MANIFESTS',
            {'circuit': lambda: self.manifest},
        ):
            return SignalFormulaReviewView.as_view()(request)

    def test_first_day_is_deterministic_and_reuses_two_signal_questions(self):
        payload = self.request().data
        self.assertEqual(payload['day_number'], 1)
        self.assertEqual(payload['cycle_day'], 1)
        self.assertIn('傅里叶变换对', payload['title'])
        self.assertEqual(len(payload['recall']), 5)
        self.assertGreaterEqual(
            sum(item['key'] in FOURIER_DAILY_KEYS for item in payload['recall']),
            2,
        )
        self.assertEqual(len(payload['core']), 5)
        self.assertEqual(len(payload['applications']), 2)
        self.assertTrue(all('signal_selected' in item['route'] for item in payload['applications']))
        self.assertFalse(payload['has_history'])

    def test_grade_c_schedules_next_first_third_and_seventh_day(self):
        response = self.request(method='post', data={
            'formula_key': 'C2_right_exponential',
            'grade': 'C',
            'date': '2026-10-30',
        }, query='')
        self.assertEqual(response.status_code, 200)
        mastery = SignalFormulaMastery.objects.get(user=self.user)
        self.assertEqual(mastery.grade, 'C')
        self.assertEqual(mastery.next_review_on, datetime.date(2026, 10, 31))
        self.assertEqual(mastery.due_dates, ['2026-10-31', '2026-11-02', '2026-11-06'])
        next_day = self.request(query='date=2026-10-31').data
        self.assertIn('C2_right_exponential', next_day['due_keys'])

    def test_four_subject_first_day_is_circuit_and_reuses_circuit_questions(self):
        payload = self.request(query='date=2026-10-30&track=four').data
        self.assertEqual(payload['track'], 'four')
        self.assertEqual(payload['subject'], 'circuit')
        self.assertEqual(payload['topic'], '电路原理')
        self.assertEqual(payload['formula_count'], 268)
        self.assertEqual(len(payload['recall']), 5)
        self.assertEqual(sum(item['subject'] == 'circuit' for item in payload['recall'][:3]), 3)
        self.assertNotEqual(payload['recall'][3]['subject'], 'circuit')
        self.assertEqual(len(payload['core']), 5)
        self.assertEqual(len(payload['applications']), 2)
        self.assertTrue(all('circuit_selected' in item['route'] for item in payload['applications']))

    def test_four_subject_grade_a_schedules_next_cycle_and_seven_day_check(self):
        response = self.request(method='post', data={
            'formula_key': 'four_circuit_a3_05',
            'grade': 'A',
            'date': '2026-10-30',
        }, query='')
        self.assertEqual(response.status_code, 200)
        mastery = SignalFormulaMastery.objects.get(user=self.user)
        self.assertEqual(mastery.due_dates, ['2026-11-03', '2026-11-06'])
        self.assertEqual(mastery.next_review_on, datetime.date(2026, 11, 3))

    def test_non_ei_workspace_is_hidden(self):
        self.assertEqual(self.request(host='drill.test').status_code, 404)
