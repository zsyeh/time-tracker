import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import SimpleTestCase

from scripts.exam_type_classification import content_hash, needs_review, prepare, report, validate_response


class ExamTypeClassifierTests(SimpleTestCase):
    def setUp(self):
        self.row = {
            'question_id': 7, 'source_system': 'drill', 'source_label': 'Question 7',
            'prompt_text': 'Choose the correct statement.', 'latex_text': '',
            'legacy_type': 'unknown', 'legacy_source': '', 'legacy_human_verified': False,
            'assets': [],
        }

    def item(self, **changes):
        return {'question_id': 7, 'question_type': 'choice', 'subquestion_count': None,
                'review_required': False, 'reason': 'Explicit instruction to choose.',
                'evidence_missing': '', **changes}

    def test_rejects_wrong_workspace_type_duplicate_and_missing_ids(self):
        with self.assertRaisesMessage(ValueError, 'invalid type'):
            validate_response([self.item(question_type='judgment')], [self.row])
        with self.assertRaisesMessage(ValueError, 'count mismatch'):
            validate_response([self.item(), self.item()], [self.row])
        with self.assertRaisesMessage(ValueError, 'count mismatch'):
            validate_response([], [self.row])

    def test_hash_changes_with_asset_version_and_image_only_requires_review(self):
        initial = content_hash(self.row)
        changed = {**self.row, 'assets': [{'type': 'question_crop', 'sha256': 'a' * 64}]}
        self.assertNotEqual(initial, content_hash(changed))
        self.assertFalse(needs_review(self.row, self.item()))
        image_only = {**changed, 'prompt_text': ''}
        self.assertTrue(needs_review(image_only, self.item()))
        self.assertTrue(needs_review(self.row, self.item(question_type='unknown', review_required=True)))

    def test_prepare_preserves_human_annotation_and_rejects_stale_gold(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'questions.jsonl'
            row = {**self.row, 'uuid': '00000000-0000-0000-0000-000000000007'}
            source.write_text(json.dumps(row) + '\n')
            args = SimpleNamespace(input=source, output_dir=Path(directory), size=1)
            prepare(args)
            queue = Path(directory) / 'validation_queue.csv'
            with queue.open(newline='') as stream:
                entry = next(csv.DictReader(stream))
            entry.update(human_label='choice', annotator='reviewer', evidence='Original choice instruction')
            with queue.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(entry))
                writer.writeheader(); writer.writerow(entry)
            prepare(args)
            with queue.open(newline='') as stream:
                saved = next(csv.DictReader(stream))
            self.assertEqual(saved['human_label'], 'choice')
            self.assertEqual(saved['annotator'], 'reviewer')
            source.write_text(json.dumps({**row, 'prompt_text': 'Changed question'}) + '\n')
            with self.assertRaisesMessage(ValueError, 'stale'):
                prepare(args)
            with queue.open(newline='') as stream:
                preserved = next(csv.DictReader(stream))
            self.assertEqual(preserved['human_label'], 'choice')

    def test_report_excludes_old_results_outside_current_sample(self):
        with TemporaryDirectory() as directory:
            out = Path(directory)
            first = {**self.row, 'question_id': 7}
            second = {**self.row, 'question_id': 8}
            source = out / 'questions.jsonl'
            source.write_text('\n'.join(json.dumps(r) for r in (first, second)) + '\n')
            (out / 'validation_sample.jsonl').write_text(json.dumps(first) + '\n')
            result_rows = [
                {'source_system': 'drill', 'question_id': row['question_id'],
                 'content_hash': content_hash(row), 'question_type': 'choice',
                 'classification_source': 'ai', 'review_required': False,
                 'subquestion_count': None, 'usage': None}
                for row in (first, second)
            ]
            (out / 'results-low.jsonl').write_text('\n'.join(json.dumps(r) for r in result_rows) + '\n')
            (out / 'results-low-image.jsonl').write_text(json.dumps({**result_rows[0],
                'question_type':'fill','usage':{'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}})+'\n')
            report(SimpleNamespace(input=source, output_dir=out))
            data = json.loads((out / 'report.json').read_text())
            self.assertEqual(data['efforts']['low']['classified'], 1)
            self.assertEqual(data['efforts']['low']['final_result']['total'], 1)
            self.assertEqual(data['efforts']['low']['final_result']['by_workspace']['drill']['counts'], {'fill':1})
