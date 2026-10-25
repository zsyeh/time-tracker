import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from django.test import SimpleTestCase, TestCase
from django.core.management import call_command

from .management.commands.audit_ei_selected import image_checks
from .models import Question, QuestionAsset, QuestionAttempt
from . import test_circuit_selected


class ImageAuditTests(SimpleTestCase):
    def image(self,edge=False):
        with pymupdf.open() as d:
            p=d.new_page(width=100,height=80)
            if edge:p.draw_rect((0,10,10,60),fill=(0,0,0))
            return p.get_pixmap(alpha=False).tobytes('png')

    def test_blank_image_is_not_complete(self):
        blob=self.image();r=image_checks(blob,100,80,hashlib.sha256(blob).hexdigest())
        self.assertIn('blank_or_nearly_blank_image',r['issues'])
        self.assertNotIn('image_hash_mismatch',r['issues'])

    def test_edge_ink_is_review_suspicion_not_automatic_crop_fix(self):
        blob=self.image(True);r=image_checks(blob,90,80,'bad')
        self.assertIn('ink_touches_left',r['issues'])
        self.assertIn('image_dimensions_mismatch',r['issues'])
        self.assertIn('image_hash_mismatch',r['issues'])


class SelectedAuditTests(TestCase):
    def test_reports_each_original_without_writing_database_or_claiming_manual_pass(self):
        test_circuit_selected.CircuitCollectionTests.setUp(self)
        module=SimpleNamespace(manifest=lambda:{'questions':self.rows})
        before=(Question.objects.count(),QuestionAsset.objects.count(),QuestionAttempt.objects.count())
        with TemporaryDirectory() as tmp,patch('drill.management.commands.audit_ei_selected.COURSES',[('circuit','电路',module)]):
            path=Path(tmp)/'audit.json'
            call_command('audit_ei_selected',output=str(path),metadata_only=True)
            d=json.loads(path.read_text())
        self.assertEqual(d['summary']['selected'],3)
        self.assertEqual(d['summary']['manual_verified'],0)
        self.assertTrue(all(r['visual_review']=='PENDING' and r['answer_matching']=='PENDING' for r in d['questions']))
        q=next(r for r in d['questions'] if r['uuid']==str(self.q3.uuid))
        self.assertIn('no_own_answer_material',q['issues'])
        self.assertEqual(before,(Question.objects.count(),QuestionAsset.objects.count(),QuestionAttempt.objects.count()))
