import hashlib,json
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
from django.core.management import call_command,CommandError
from django.test import TestCase

from . import test_circuit_selected
from .models import QuestionAsset,QuestionAttempt,QuestionRevision,QuestionRevisionAsset


class AnswerWidthRepairTests(TestCase):
    def setUp(self):
        test_circuit_selected.CircuitCollectionTests.setUp(self)
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.pdf=root/'source.pdf';self.manifest=root/'manifest.json'
        with pymupdf.open() as d:
            p=d.new_page(width=100,height=80);p.draw_line((1,20),(99,20),width=2)
            old=p.get_pixmap(dpi=72,clip=(10,5,90,50),alpha=False).tobytes('png');d.save(self.pdf)
        self.old=QuestionAsset.objects.create(source_id=991919,question=self.q1,asset_type='answer_crop',position=0,
            image_data=old,sha256=hashlib.sha256(old).hexdigest(),width=80,height=45,source_page_index=0,
            source_x0=10,source_y0=5,source_x1=90,source_y1=50,render_dpi=72)
        self.data={'source_sha256':hashlib.sha256(self.pdf.read_bytes()).hexdigest(),'regions':[
            dict(uuid=str(self.q1.uuid),fingerprint=self.q1.fingerprint,asset_source_id=self.old.source_id,
                 old_sha256=self.old.sha256,page_index=0,old_bbox=[10,5,90,50],bbox=[0,5,100,50])]}
        self.save_manifest()

    def save_manifest(self):self.manifest.write_text(json.dumps(self.data))

    def run_repair(self,dry=False):
        call_command('restore_ei_selected_answer_width',manifest=self.manifest,source=self.pdf,dry_run=dry)

    def test_dry_run_idempotence_binary_progress_and_revision_preservation(self):
        attempt=QuestionAttempt.objects.create(question=self.q1,user=self.user,result='correct')
        revision=QuestionRevision.capture(self.q1)
        links=list(revision.revision_assets.values_list('asset_id','asset_type','position'))
        self.run_repair(True);self.assertEqual(QuestionAsset.objects.count(),1)
        self.run_repair();self.old.refresh_from_db()
        self.assertEqual(self.old.asset_type,'answer_crop_superseded')
        self.assertEqual(hashlib.sha256(bytes(self.old.image_data)).hexdigest(),self.old.sha256)
        current=self.q1.assets.get(asset_type='answer_crop');self.assertEqual(current.width,100)
        self.assertEqual(current.source_y0,5);self.assertEqual(current.source_y1,50)
        self.assertTrue(QuestionAttempt.objects.filter(pk=attempt.pk,result='correct').exists())
        self.assertEqual(links,list(revision.revision_assets.values_list('asset_id','asset_type','position')))
        counts=(QuestionAsset.objects.count(),QuestionRevision.objects.count(),QuestionRevisionAsset.objects.count())
        self.run_repair()
        self.assertEqual(counts,(QuestionAsset.objects.count(),QuestionRevision.objects.count(),QuestionRevisionAsset.objects.count()))

    def test_rejects_changed_source_and_vertical_bounds(self):
        self.data['source_sha256']='bad';self.save_manifest()
        with self.assertRaises(CommandError):self.run_repair()
        self.data['source_sha256']=hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.data['regions'][0]['bbox'][1]=4;self.save_manifest()
        with self.assertRaises(CommandError):self.run_repair()
        self.assertEqual(QuestionAsset.objects.count(),1)

    def test_reviewed_supplement_is_dry_by_default_and_preserves_existing_images(self):
        self.data['regions']=[dict(uuid=str(self.q1.uuid),fingerprint=self.q1.fingerprint,position=1,
                                  page_index=0,bbox=[0,5,100,50],figure_label='A1',review_reason='Confirmed separate floating figure.')]
        self.save_manifest()
        call_command('append_ei_reviewed_answer_figures',manifest=self.manifest,source=self.pdf)
        self.assertEqual(QuestionAsset.objects.count(),1)
        call_command('append_ei_reviewed_answer_figures',manifest=self.manifest,source=self.pdf,apply=True)
        self.assertEqual(QuestionAsset.objects.count(),2)
        self.old.refresh_from_db();self.assertEqual(self.old.asset_type,'answer_crop')
        call_command('append_ei_reviewed_answer_figures',manifest=self.manifest,source=self.pdf,apply=True)
        self.assertEqual(QuestionAsset.objects.count(),2)
        self.data['regions'][0]['position']=0;self.save_manifest()
        with self.assertRaises(CommandError):call_command('append_ei_reviewed_answer_figures',manifest=self.manifest,source=self.pdf,apply=True)
