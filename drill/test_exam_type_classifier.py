from django.test import SimpleTestCase

from scripts.exam_type_classification import content_hash, needs_review, validate_response


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
