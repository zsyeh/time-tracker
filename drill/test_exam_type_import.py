import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from drill.management.commands.import_exam_types import digest_for_question
from drill.models import Question, QuestionDocument, QuestionExamType


class ExamTypeImportTests(TestCase):
    def setUp(self):
        document = QuestionDocument.objects.create(
            workspace='ei', source_id=991231, filename='sample.pdf', title='Sample',
            sha256='e' * 64, page_count=1,
        )
        self.question = Question.objects.create(
            document=document, question_order=1, source_label='Q1',
            prompt_text='简述基尔霍夫定律。', content_mode='text',
            fingerprint='c' * 64,
        )

    def record(self):
        return {
            'source_system': 'ei', 'question_id': self.question.pk,
            'question_type': 'short_answer', 'subquestion_count': None,
            'classification_source': 'ai', 'model_id': 'gpt-6-luna',
            'classification_version': 'exam-form-v1',
            'content_hash': digest_for_question(self.question),
            'review_required': False, 'reason': 'Brief conceptual explanation.',
            'evidence_missing': '',
        }

    def test_dry_run_apply_and_verified_rollback(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'rows.jsonl'
            source.write_text(json.dumps(self.record()) + '\n')
            backup = Path(directory) / 'backup.json'
            output = StringIO()
            call_command('import_exam_types', input=source, stdout=output)
            self.assertEqual(QuestionExamType.objects.count(), 0)
            self.assertEqual(json.loads(output.getvalue())['rows'], 1)
            call_command('import_exam_types', input=source, apply=True,
                         batch_id='test_batch_001', backup=backup, stdout=StringIO())
            saved = QuestionExamType.objects.get(question=self.question)
            self.assertEqual(saved.question_type, 'short_answer')
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.stat().st_mode & 0o077, 0)
            call_command('import_exam_types', rollback=backup, stdout=StringIO())
            self.assertEqual(QuestionExamType.objects.count(), 0)

    def test_stale_content_is_rejected_before_any_write(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'rows.jsonl'
            source.write_text(json.dumps(self.record()) + '\n')
            self.question.prompt_text = 'The question has changed.'
            self.question.save(update_fields=['prompt_text'])
            with self.assertRaisesMessage(CommandError, 'Stale question content'):
                call_command('import_exam_types', input=source, apply=True,
                             batch_id='test_batch_002', backup=Path(directory) / 'backup.json',
                             stdout=StringIO())
            self.assertEqual(QuestionExamType.objects.count(), 0)
