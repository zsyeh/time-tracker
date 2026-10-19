import hashlib
import json
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.linear_selected import STRATEGY
from drill.linear_selected_answers import build_manifest
from drill.management.commands.import_linear_selected_pdf import fingerprint
from drill.models import Question, QuestionAsset, QuestionDocument
from drill.pdf_import import stable_source_id


class Command(BaseCommand):
    help = 'Attach verified individual question/answer regions to the existing linear selected book.'

    def add_arguments(self, parser):
        parser.add_argument('questions', type=Path)
        parser.add_argument('answers', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--manifest-output', type=Path)
        parser.add_argument('--dpi', type=int, default=150)

    def handle(self, *args, **options):
        if not 120 <= options['dpi'] <= 200:
            raise CommandError('DPI must be between 120 and 200')
        try:
            manifest = build_manifest(options['questions'], options['answers'])
        except (OSError, ValueError, pymupdf.FileDataError) as error:
            raise CommandError(str(error)) from error
        if options['manifest_output']:
            options['manifest_output'].write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        if options['dry_run']:
            self.stdout.write(json.dumps({**manifest['counts'], 'dry_run': True}, ensure_ascii=False))
            return
        new_assets = new_bytes = 0
        with transaction.atomic(), pymupdf.open(options['questions']) as questions, pymupdf.open(options['answers']) as answers:
            document = QuestionDocument.objects.filter(sha256=manifest['question_sha256'], parser_strategy=STRATEGY).first()
            if document is None:
                raise CommandError('Import the question book first')
            provenance = f'配套通用答案 PDF SHA256={manifest["answer_sha256"]}；逐题定位见配套 manifest。'
            if provenance not in document.attribution:
                document.attribution = f'{document.attribution}\n{provenance}'.strip()
                document.save(update_fields=['attribution'])
            for item in manifest['questions']:
                question = Question.objects.select_for_update().get(document=document,
                    fingerprint=fingerprint(manifest['question_sha256'], 'question', item['number']))
                for kind, pdf, key, sha in [('question_crop', questions, 'question_regions', manifest['question_sha256']),
                                           ('answer_crop', answers, 'answer_regions', manifest['answer_sha256'])]:
                    expected_ids = []
                    for position, region in enumerate(item[key]):
                        source_id = stable_source_id('linear-individual-v1', sha, item['number'], kind, position,
                                                     json.dumps(region, sort_keys=True), options['dpi'])
                        expected_ids.append(source_id)
                    existing = question.assets.filter(asset_type=kind)
                    if existing.exclude(source_id__in=expected_ids).exists():
                        raise CommandError(f'Existing individual assets conflict for #{item["number"]:03d}; refusing overwrite')
                    for position, (region, source_id) in enumerate(zip(item[key], expected_ids)):
                        if existing.filter(source_id=source_id).exists():
                            continue
                        page = pdf[region['page']]; rect = pymupdf.Rect(region['bbox'])
                        if rect.is_empty or not page.rect.contains(rect):
                            raise CommandError('Invalid region')
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(options['dpi'] / 72, options['dpi'] / 72), clip=rect, alpha=False)
                        data = pix.tobytes('png')
                        QuestionAsset.objects.create(question=question, source_id=source_id, asset_type=kind,
                            position=position, sha256=hashlib.sha256(data).hexdigest(), image_data=data,
                            width=pix.width, height=pix.height, source_page_index=region['page'],
                            source_x0=rect.x0, source_y0=rect.y0, source_x1=rect.x1, source_y1=rect.y1,
                            render_dpi=options['dpi'])
                        new_assets += 1; new_bytes += len(data)
                if question.answer_source not in ('', 'linear-reference-pdf'):
                    raise CommandError(f'Existing answer metadata conflict for #{item["number"]:03d}')
                if question.answer_source != 'linear-reference-pdf' or question.answer_confidence != 1:
                    question.answer_source = 'linear-reference-pdf'; question.answer_confidence = 1
                    question.save(update_fields=['answer_source', 'answer_confidence'])
        self.stdout.write(json.dumps({**manifest['counts'], 'new_assets': new_assets, 'new_image_bytes': new_bytes}, ensure_ascii=False))
