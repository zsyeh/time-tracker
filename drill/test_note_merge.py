import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Question, QuestionAttempt, QuestionDocument, QuestionUserState


class CanonicalNoteMergeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('note-owner')
        self.other = get_user_model().objects.create_user('note-other')
        self.document = QuestionDocument.objects.create(
            source_id=991001, workspace='ei', title='Signal', sha256='9' * 64, page_count=1,
        )
        self.question = Question.objects.create(
            document=self.document, question_order=1, fingerprint='8' * 64,
        )

    def test_dry_run_does_not_write_and_apply_is_idempotent(self):
        QuestionUserState.objects.create(user=self.user, question=self.question, note='原 Note')
        QuestionAttempt.objects.create(
            user=self.user, question=self.question, result='review',
            note='原 Note', correction_note='错误原因',
        )
        QuestionAttempt.objects.create(
            user=self.user, question=self.question, result='review', correction_note='错误原因',
        )
        out = StringIO()
        call_command('merge_attempt_text_into_notes', stdout=out)
        self.assertIn('Dry-run only', out.getvalue())
        self.assertEqual(QuestionUserState.objects.get().note, '原 Note')

        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / 'note-audit.json'
            call_command('merge_attempt_text_into_notes', apply=True, audit_file=audit)
            self.assertEqual(QuestionUserState.objects.get().note, '原 Note\n\n错误原因')
            self.assertEqual(
                json.loads(audit.read_text(encoding='utf-8'))['summary']['changed_pairs'], 1,
            )
            payload = json.loads(audit.read_text(encoding='utf-8'))
            self.assertEqual(payload['status'], 'applied')
            self.assertEqual(payload['summary']['changed_pairs'], 1)
            self.assertEqual(audit.stat().st_mode & 0o777, 0o600)
            call_command('merge_attempt_text_into_notes', apply=True, audit_file=audit)
            self.assertEqual(QuestionUserState.objects.get().note, '原 Note\n\n错误原因')

    def test_new_state_and_user_isolation_and_rollback(self):
        QuestionAttempt.objects.create(
            user=self.user, question=self.question, result='review', correction_note='我的原因',
        )
        QuestionAttempt.objects.create(
            user=self.other, question=self.question, result='review', correction_note='他人原因',
        )
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / 'note-audit.json'
            call_command('merge_attempt_text_into_notes', apply=True, audit_file=audit)
            self.assertEqual(
                QuestionUserState.objects.get(user=self.user, question=self.question).note, '我的原因',
            )
            self.assertEqual(
                QuestionUserState.objects.get(user=self.other, question=self.question).note, '他人原因',
            )
            call_command('merge_attempt_text_into_notes', rollback=audit)
            self.assertEqual(
                QuestionUserState.objects.get(user=self.user, question=self.question).note, '',
            )

    def test_identical_text_is_not_duplicated(self):
        QuestionUserState.objects.create(user=self.user, question=self.question, note='相同内容')
        QuestionAttempt.objects.create(
            user=self.user, question=self.question, result='review', correction_note='相同内容',
        )
        out = StringIO()
        call_command('merge_attempt_text_into_notes', stdout=out)
        self.assertIn('"changed_pairs": 0', out.getvalue())

    def test_over_limit_merge_is_rejected_without_writing(self):
        QuestionUserState.objects.create(user=self.user, question=self.question, note='A' * 19999)
        QuestionAttempt.objects.create(
            user=self.user, question=self.question, result='review', correction_note='extra',
        )
        with self.assertRaises(CommandError):
            call_command('merge_attempt_text_into_notes')
        self.assertEqual(
            QuestionUserState.objects.get(user=self.user, question=self.question).note,
            'A' * 19999,
        )
