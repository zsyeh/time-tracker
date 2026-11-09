import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from drill.management.commands.import_exam_types import digest_for_question
from drill.models import Question, QuestionAsset, QuestionDocument, QuestionExamType


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

    def test_dry_run_does_not_select_binary_asset_data(self):
        QuestionAsset.objects.create(
            source_id=991232, question=self.question, position=0,
            asset_type='question_crop', sha256='f' * 64,
            image_data=b'private-image-bytes', width=10, height=10,
        )
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'rows.jsonl'
            source.write_text(json.dumps(self.record()) + '\n')
            with CaptureQueriesContext(connection) as queries:
                call_command('import_exam_types', input=source, stdout=StringIO())
            self.assertFalse(any('"image_data"' in query['sql'] for query in queries))

    def test_audit_flags_unknown_and_conflicting_types_are_imported_idempotently(self):
        self.question.question_type='single_choice'
        self.question.prompt_text=''
        self.question.save(update_fields=['question_type','prompt_text'])
        with TemporaryDirectory() as directory:
            source=Path(directory)/'rows.jsonl'
            for index,label in enumerate(('large','unknown'),1):
                source.write_text(json.dumps({**self.record(),'question_type':label,'review_required':label!='unknown'})+'\n')
                call_command('import_exam_types',input=source,apply=True,batch_id=f'test_all_{index}',
                    backup=Path(directory)/f'backup{index}.json',expected_workspace_count=['ei=1'],stdout=StringIO())
                self.assertEqual(QuestionExamType.objects.count(),1)
                saved=QuestionExamType.objects.get(question=self.question)
                self.assertEqual(saved.question_type,label)
                self.assertTrue(saved.review_required)
                self.assertIn('no_text_prompt',saved.review_reasons)
                self.assertIn('legacy_type_conflict',saved.review_reasons)
            call_command('import_exam_types',rollback=Path(directory)/'backup2.json',stdout=StringIO())
            self.assertEqual(QuestionExamType.objects.get().question_type,'large')
            self.question.refresh_from_db()
            self.assertEqual(self.question.question_type,'single_choice')

    def test_wrong_expected_totals_block_apply(self):
        with TemporaryDirectory() as directory:
            source=Path(directory)/'rows.jsonl'
            source.write_text(json.dumps(self.record())+'\n')
            with self.assertRaisesMessage(CommandError,'Workspace count mismatch'):
                call_command('import_exam_types',input=source,apply=True,batch_id='bad_count_001',
                    backup=Path(directory)/'backup.json',expected_workspace_count=['ei=2'],stdout=StringIO())
            self.assertEqual(QuestionExamType.objects.count(),0)
