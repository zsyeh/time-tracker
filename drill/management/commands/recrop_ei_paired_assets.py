"""Tighten existing paired EI PDF assets without repeating OCR."""

import hashlib
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.import_ei_paired_pdfs import Command as PairImporter
from drill.management.commands.import_ei_paired_pdfs import PAIR_SOURCES
from drill.models import QuestionAsset


class Command(BaseCommand):
    help = 'Re-render and vertically trim existing paired EI crops from saved PDF coordinates.'

    def add_arguments(self, parser):
        parser.add_argument('source_root', type=Path)
        parser.add_argument('--subjects', default=','.join(PAIR_SOURCES))
        parser.add_argument('--dpi', type=int, default=150)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        root = options['source_root'].expanduser().resolve()
        subjects = [item.strip() for item in options['subjects'].split(',') if item.strip()]
        unknown = set(subjects) - set(PAIR_SOURCES)
        if unknown:
            raise CommandError(f'Unknown subjects: {", ".join(sorted(unknown))}')
        if not root.is_dir():
            raise CommandError(f'Not a source directory: {root}')
        dpi = options['dpi']
        if dpi < 100 or dpi > 200:
            raise CommandError('--dpi must be between 100 and 200.')

        total = 0
        for subject in subjects:
            total += self.recrop_subject(root, subject, dpi, options['dry_run'])
        suffix = ' would be updated' if options['dry_run'] else ' updated'
        self.stdout.write(self.style.SUCCESS(f'{total} EI assets{suffix}.'))

    def recrop_subject(self, root, subject, dpi, dry_run):
        config = PAIR_SOURCES[subject]
        paths = {
            'question_crop': PairImporter.source_file(root, config['question_file']),
            'answer_crop': PairImporter.source_file(root, config['answer_file']),
        }
        if any(not path.is_file() for path in paths.values()):
            raise CommandError(f'Missing source PDF for {subject}.')
        documents = {asset_type: pymupdf.open(path) for asset_type, path in paths.items()}
        assets = QuestionAsset.objects.filter(
            question__document__workspace='ei',
            question__source_label__startswith=f'{subject} · ',
            question__is_practiceable=True,
            asset_type__in=paths,
        ).order_by('pk')
        changed = 0
        try:
            with transaction.atomic():
                for asset in assets.iterator(chunk_size=50):
                    document = documents[asset.asset_type]
                    page = document[asset.source_page_index]
                    rect = pymupdf.Rect(
                        asset.source_x0, asset.source_y0, asset.source_x1, asset.source_y1,
                    ) & page.rect
                    trim_top, trim_bottom = PairImporter.vertical_trim_bounds(page, rect)
                    if not trim_top and not trim_bottom:
                        continue
                    rect.y0 += trim_top
                    rect.y1 -= trim_bottom
                    scale = dpi / 72
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False,
                    )
                    image_data = pixmap.tobytes('png')
                    digest = hashlib.sha256(image_data).hexdigest()
                    changed += 1
                    if dry_run:
                        continue
                    duplicate = QuestionAsset.objects.filter(
                        question=asset.question, sha256=digest,
                    ).exclude(pk=asset.pk).first()
                    if duplicate:
                        asset.delete()
                        continue
                    asset.image_data = image_data
                    asset.sha256 = digest
                    asset.width = pixmap.width
                    asset.height = pixmap.height
                    asset.source_y0 = rect.y0
                    asset.source_y1 = rect.y1
                    asset.render_dpi = dpi
                    asset.save(update_fields=[
                        'image_data', 'sha256', 'width', 'height', 'source_y0',
                        'source_y1', 'render_dpi',
                    ])
                if dry_run:
                    transaction.set_rollback(True)
        finally:
            for document in documents.values():
                document.close()
        self.stdout.write(f'{subject}: {changed} crops tightened.')
        return changed
