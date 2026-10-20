import hashlib
import json
from pathlib import Path
import tempfile

import pymupdf
from django.test import SimpleTestCase

from .answer_segmentation import adjacent_keys, build_answer_manifest, match_numbered_answers, numbered_lines


class AnswerSegmentationTests(SimpleTestCase):
    def candidate(self, kind, number):
        return {'kind': kind, 'number': number}

    def test_main_answers_ignore_nested_numeric_solution_steps(self):
        candidates = [self.candidate('main', 1), self.candidate('item', 1),
                      self.candidate('item', 2), self.candidate('main', 2)]
        matches = match_numbered_answers([{'key': 'main-1'}, {'key': 'main-2'}], candidates)
        self.assertEqual([m['key'] for m in matches], ['main-1', 'main-2'])

    def test_section_numbers_do_not_reset_existing_question_identities(self):
        matches = match_numbered_answers([{'key': 'section-2-item-1'}, {'key': 'main-3'}], [
            self.candidate('main', 2), self.candidate('item', 1),
            self.candidate('main', 3), self.candidate('item', 1)])
        self.assertEqual([m['key'] for m in matches], ['heading-2', 'section-2-item-1', 'main-3'])

    def test_arabic_and_chinese_flat_styles_preserve_section_zero_keys(self):
        items = [{'key': f'section-0-item-{n}'} for n in (1, 2)]
        for kind in ('main', 'item'):
            matches = match_numbered_answers(items, [self.candidate(kind, n) for n in (1, 2)])
            self.assertEqual([m['key'] for m in matches], ['section-0-item-1', 'section-0-item-2'])

    def test_only_consecutive_intervals_are_eligible(self):
        self.assertTrue(adjacent_keys('section-1-item-3', 'section-1-item-4'))
        self.assertTrue(adjacent_keys('section-1-item-3', 'heading-2'))
        self.assertFalse(adjacent_keys('main-2', 'main-4'))
        self.assertFalse(adjacent_keys('section-1-item-3', 'section-1-item-5'))
        self.assertFalse(adjacent_keys('section-1-item-3', 'main-3'))

    def fixture(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        pdf = pymupdf.open(); page = pdf.new_page(width=600, height=800)
        page.insert_text((50, 120), 'Question 1 and full answer')
        page.draw_rect(pymupdf.Rect(100, 160, 500, 300))
        page.insert_text((50, 420), 'Question 2 and full answer')
        binary = pdf.tobytes(); pdf.close()
        sha = hashlib.sha256(binary).hexdigest(); (root/f'{sha}.pdf').write_bytes(binary)
        parent = {'year': 2025, 'variant': '', 'key': 'paper',
                  'answer_regions': [{'source': sha, 'page_index': 0, 'bbox': [0, 0, 600, 800]}]}
        source = {'sources': {sha: {'file': f'{sha}.pdf'}}, 'books': [{'key': 'circuit', 'questions': [parent]}]}
        fp = hashlib.sha256(b'ucas-past-exams:v1:circuit:2025::paper').hexdigest()
        index = {'schema_version': 1, 'papers': [{'book': 'circuit', 'year': 2025, 'variant': '',
                'source_fingerprint': fp, 'complete': True, 'items': [
                    {'key': f'main-{n}', 'label': str(n), 'position': n} for n in (1, 2)]}]}
        cache = root/'cache'/sha; cache.mkdir(parents=True)
        data = {'width': 600, 'height': 800, 'lines': [
            {'text': '一、题目与解析', 'bbox': [50, 108, 300, 122]},
            {'text': '二、题目与解析', 'bbox': [50, 408, 300, 422]}]}
        (cache/'0000.json').write_text(json.dumps(data))
        (root/'source.json').write_text(json.dumps(source)); (root/'index.json').write_text(json.dumps(index))
        return root, parent, data, cache

    def build(self, root):
        return build_answer_manifest(root/'index.json', [root/'source.json'], root/'cache')

    def test_end_to_end_preserves_full_width_and_does_not_merge_next_question(self):
        root, parent, data, cache = self.fixture()
        manifest = self.build(root)
        self.assertEqual(len(manifest['questions']), 2)
        first, second = [q['solution_regions'][0] for q in manifest['questions']]
        self.assertEqual(first['bbox'][2], 600)
        self.assertLess(first['bbox'][3], 408)
        self.assertGreater(first['bbox'][3], 300)  # Entire tall diagram retained.
        self.assertEqual(first['bbox'][3], second['bbox'][1])

    def test_duplicate_anchors_are_review_only(self):
        root, parent, data, cache = self.fixture()
        data['lines'].append({'text': '一、重号', 'bbox': [50, 600, 300, 620]})
        (cache/'0000.json').write_text(json.dumps(data))
        manifest = self.build(root)
        self.assertEqual(manifest['questions'], [])
        self.assertEqual(manifest['review'][0]['reason'], 'ambiguous_answer_anchor')

    def test_exam_instructions_cannot_become_question_answer_matches(self):
        root, parent, data, cache = self.fixture()
        path = root/'index.json'; index = json.loads(path.read_text())
        index['papers'][0]['items'][0]['anchor_text'] = '1. 本试卷共有十一题，满分100分'
        path.write_text(json.dumps(index))
        manifest = self.build(root)
        self.assertEqual(manifest['questions'], [])
        self.assertEqual({r['reason'] for r in manifest['review']}, {'invalid_question_index'})

    def test_margin_disagreement_and_decimals_are_not_silently_matched(self):
        root, parent, data, cache = self.fixture()
        data['lines'].append({'text': '1.23 volts', 'bbox': [50, 250, 300, 270]})
        (cache/'0000.json').write_text(json.dumps(data))
        margins = root/'margins'/cache.name; margins.mkdir(parents=True)
        (margins/'0000.json').write_text(json.dumps({'lines': [
            {'text': '三、误识别', 'bbox': [50, 108, 180, 122]}]}))
        candidates = numbered_lines(parent['answer_regions'], root/'cache', root/'margins')
        self.assertTrue(candidates[0]['ambiguous'])
        self.assertFalse(any(c['kind'] == 'item' for c in candidates))
