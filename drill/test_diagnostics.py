import datetime
import json
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    Question, QuestionAttempt, QuestionAttemptError, QuestionDocument,
    QuestionReviewPlan, QuestionTopic, QuestionUserState,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class DiagnosticApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('diagnostic-user', password='x')
        self.other = User.objects.create_user('other-user', password='x')
        self.document = QuestionDocument.objects.create(
            source_id=910001, workspace='drill', filename='diagnostic.pdf', title='Math diagnostics',
            sha256='9' * 64, page_count=1,
        )
        self.topic = QuestionTopic.objects.create(
            source_id=910001, document=self.document, title='Calculus', level=1, sort_order=1,
        )
        self.questions = [Question.objects.create(
            document=self.document, topic=self.topic, similarity_topic=self.topic,
            question_order=index, display_label=f'Question {index}', prompt_text='Solve',
            content_mode='text', fingerprint=f'{index:064x}', is_practiceable=True,
        ) for index in range(1, 5)]
        self.client.force_login(self.user)

    def post_attempt(self, question, **data):
        payload = {'result': 'review', 'submission_key': str(uuid.uuid4()), **data}
        return self.client.post(
            f'/api/drill/questions/{question.uuid}/attempts/',
            data=json.dumps(payload), content_type='application/json',
        )

    def test_answer_view_forces_non_independent_and_creates_review_plan(self):
        response = self.post_attempt(
            self.questions[0], viewed_answer=True, is_independent=True,
            error_codes=['B2', 'C1'], primary_error='B2', method_level='M1',
            correction_note='Start from the governing equation.', judgement_source='self',
        )
        self.assertEqual(response.status_code, 201)
        attempt = QuestionAttempt.objects.get(pk=response.json()['id'])
        self.assertFalse(attempt.is_independent)
        self.assertEqual(attempt.outcome, 'incorrect')
        self.assertEqual(attempt.training_stage, 'first')
        self.assertEqual(attempt.attempt_round, 1)
        self.assertEqual(
            set(attempt.error_tags.values_list('code', 'is_primary')),
            {('B2', True), ('C1', False)},
        )
        plan = QuestionReviewPlan.objects.get(user=self.user, question=self.questions[0])
        self.assertEqual(plan.schedule_days, [0, 1, 3, 7])
        self.assertEqual(plan.status, 'active')

    def test_submission_key_is_idempotent(self):
        key = str(uuid.uuid4())
        first = self.post_attempt(self.questions[0], submission_key=key, error_codes=['A'])
        second = self.post_attempt(self.questions[0], submission_key=key, error_codes=['A'])
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['deduplicated'])
        self.assertEqual(QuestionAttempt.objects.filter(user=self.user).count(), 1)

    def test_metrics_exclude_legacy_unknown_and_use_explicit_second_independent_attempt(self):
        now = timezone.now()
        QuestionAttempt.objects.create(
            user=self.user, question=self.questions[3], result='correct', created_at=now,
        )  # Legacy: no diagnosis evidence.
        first_bad = QuestionAttempt.objects.create(
            user=self.user, question=self.questions[0], result='review', outcome='incorrect',
            is_independent=True, training_stage='first', attempt_round=1, created_at=now - datetime.timedelta(days=1),
        )
        QuestionAttemptError.objects.create(attempt=first_bad, code='B2', is_primary=True)
        second_good = QuestionAttempt.objects.create(
            user=self.user, question=self.questions[0], result='correct', outcome='correct',
            is_independent=True, training_stage='next_day_redo', attempt_round=2, created_at=now,
        )
        first_good = QuestionAttempt.objects.create(
            user=self.user, question=self.questions[1], result='correct', outcome='correct',
            is_independent=True, training_stage='first', attempt_round=1, created_at=now,
        )
        response = self.client.get('/api/drill/diagnostics/?days=7')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        metrics = payload['metrics']
        self.assertEqual(metrics['first_independent_accuracy'], {'value': 50.0, 'numerator': 1, 'sample': 2})
        self.assertEqual(metrics['second_independent_accuracy'], {'value': 100.0, 'numerator': 1, 'sample': 1})
        self.assertEqual(payload['period_activity']['submissions'], 4)
        self.assertEqual(payload['period_activity']['legacy_unknown_attempts'], 1)
        self.assertEqual(payload['period_activity']['diagnosed_attempts'], 3)
        self.assertEqual(len(payload['activity']), 7)
        self.assertTrue(any(row['daily_unique_questions'] == 0 for row in payload['activity']))

    def test_error_recurrence_and_user_isolation(self):
        now = timezone.now()
        for index in range(2):
            attempt = QuestionAttempt.objects.create(
                user=self.user, question=self.questions[0], result='review', outcome='incorrect',
                is_independent=True, training_stage='first' if index == 0 else 'same_day_redo',
                attempt_round=index + 1, created_at=now + datetime.timedelta(seconds=index),
            )
            QuestionAttemptError.objects.create(attempt=attempt, code='C2', is_primary=True)
        private = QuestionAttempt.objects.create(
            user=self.other, question=self.questions[1], result='review', outcome='incorrect',
            is_independent=True, training_stage='first', attempt_round=1,
        )
        QuestionAttemptError.objects.create(attempt=private, code='A', is_primary=True)
        payload = self.client.get('/api/drill/diagnostics/?days=7').json()
        self.assertEqual(payload['metrics']['error_recurrence_rate'], {'value': 100.0, 'sample': 1})
        counts = {row['code']: row['count'] for row in payload['error_distribution']}
        self.assertEqual(counts['C2'], 2)
        self.assertEqual(counts['A'], 0)

    def test_diagnosis_can_be_edited_without_replacing_attempt(self):
        response = self.post_attempt(self.questions[0], error_codes=['B1'], primary_error='B1')
        attempt_id = response.json()['id']
        edited = self.client.patch(
            f'/api/drill/attempts/{attempt_id}/diagnosis/',
            data=json.dumps({
                'error_codes': ['B2', 'C1'], 'primary_error': 'B2',
                'knowledge_level': 'K2', 'method_level': 'M1',
                'correction_note': 'Use KCL first.',
            }), content_type='application/json',
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(QuestionAttempt.objects.filter(pk=attempt_id).count(), 1)
        self.assertEqual(edited.json()['primary_error'], 'B2')
        self.assertEqual({row['code'] for row in edited.json()['errors']}, {'B2', 'C1'})

    def test_diagnosis_auto_edit_updates_independence_without_new_attempt(self):
        response = self.post_attempt(self.questions[0], error_codes=['B1'], primary_error='B1')
        attempt_id = response.json()['id']
        edited = self.client.patch(
            f'/api/drill/attempts/{attempt_id}/diagnosis/',
            data=json.dumps({
                'error_codes': ['B1'], 'primary_error': 'B1',
                'used_hint': True, 'viewed_answer': False, 'is_independent': True,
            }), content_type='application/json',
        )
        self.assertEqual(edited.status_code, 200)
        self.assertFalse(edited.json()['is_independent'])
        self.assertTrue(edited.json()['used_hint'])
        self.assertEqual(QuestionAttempt.objects.filter(pk=attempt_id).count(), 1)

    def test_question_attempt_history_is_not_silently_truncated(self):
        QuestionAttempt.objects.bulk_create([
            QuestionAttempt(
                user=self.user, question=self.questions[0], result='review',
                outcome='incorrect', training_stage='review', attempt_round=index + 1,
            )
            for index in range(55)
        ])
        response = self.client.get(f'/api/drill/questions/{self.questions[0].uuid}/attempts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 55)

    def test_correct_after_answer_is_not_first_independent_correct(self):
        response = self.post_attempt(
            self.questions[2], result='correct', outcome='correct',
            viewed_answer=True, is_independent=True,
        )
        self.assertEqual(response.status_code, 201)
        metric = self.client.get('/api/drill/diagnostics/?days=7').json()['metrics']['first_independent_accuracy']
        self.assertEqual(metric, {'value': 0.0, 'numerator': 0, 'sample': 1})

    def test_review_plan_can_be_snoozed_and_method_queue_is_clickable(self):
        self.post_attempt(self.questions[0], error_codes=['B3'], primary_error='B3')
        queue = self.client.get('/api/drill/diagnostics/questions/?error=B2,B3&queue=active').json()
        self.assertEqual(queue['count'], 1)
        self.assertEqual(queue['results'][0]['uuid'], str(self.questions[0].uuid))
        changed = self.client.patch(
            f'/api/drill/questions/{self.questions[0].uuid}/review-plan/',
            data=json.dumps({'action': 'snooze', 'days': 2}), content_type='application/json',
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()['status'], 'active')

    def test_custom_range_and_invalid_range(self):
        today = timezone.localdate()
        start = today - datetime.timedelta(days=13)
        response = self.client.get(
            f'/api/drill/diagnostics/?start={start.isoformat()}&end={today.isoformat()}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['range'], {
            'start': start.isoformat(), 'end': today.isoformat(),
        })
        invalid = self.client.get(
            f'/api/drill/diagnostics/?start={today.isoformat()}&end={start.isoformat()}'
        )
        self.assertEqual(invalid.status_code, 400)

    @override_settings(
        ALLOWED_HOSTS=['testserver', 'ei.ehzsy.site'],
        EI_HOSTS={'ei.ehzsy.site'},
    )
    def test_ei_and_drill_diagnostics_are_workspace_isolated(self):
        ei_document = QuestionDocument.objects.create(
            source_id=910002, workspace='ei', filename='ei.md', title='892 · 信号与系统',
            sha256='8' * 64, page_count=1,
        )
        ei_question = Question.objects.create(
            document=ei_document, question_order=1, display_label='EI 1',
            prompt_text='EI problem', content_mode='text', fingerprint='f' * 64,
            is_practiceable=True,
        )
        QuestionAttempt.objects.create(
            user=self.user, question=ei_question, result='correct', outcome='correct',
            is_independent=True, training_stage='first', attempt_round=1,
        )
        QuestionAttempt.objects.create(
            user=self.user, question=self.questions[0], result='review', outcome='incorrect',
            is_independent=True, training_stage='first', attempt_round=1,
        )
        drill = self.client.get('/api/drill/diagnostics/?days=7').json()
        ei = self.client.get(
            '/api/drill/diagnostics/?days=7', HTTP_HOST='ei.ehzsy.site',
        ).json()
        self.assertEqual(drill['workspace'], 'drill')
        self.assertEqual(drill['metrics']['first_independent_accuracy']['sample'], 1)
        self.assertEqual(drill['metrics']['first_independent_accuracy']['numerator'], 0)
        self.assertEqual(ei['workspace'], 'ei')
        self.assertEqual(ei['metrics']['first_independent_accuracy']['sample'], 1)
        self.assertEqual(ei['metrics']['first_independent_accuracy']['numerator'], 1)

    def test_method_notes_round_trip_and_no_division_by_zero(self):
        response = self.post_attempt(
            self.questions[0], error_codes=['B2'], primary_error='B2',
            knowledge_note='Use the convolution theorem.',
            first_step_note='Write Y(jw)=H(jw)X(jw).',
        )
        self.assertEqual(response.status_code, 201)
        diagnosis = response.json()
        self.assertEqual(diagnosis['knowledge_note'], '')
        self.assertEqual(diagnosis['first_step_note'], '')
        self.assertEqual(
            QuestionUserState.objects.get(user=self.user, question=self.questions[0]).note,
            'Use the convolution theorem.\n\nWrite Y(jw)=H(jw)X(jw).',
        )

        empty_user = get_user_model().objects.create_user('empty-user', password='x')
        self.client.force_login(empty_user)
        metrics = self.client.get('/api/drill/diagnostics/?days=7').json()['metrics']
        self.assertIsNone(metrics['first_independent_accuracy']['value'])
        self.assertIsNone(metrics['second_independent_accuracy']['value'])
        self.assertIsNone(metrics['method_start_failure_rate']['value'])
