import hashlib
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from drill.asset_rerender import (
    CropLocation,
    FormulaAwareCropAdjuster,
    LegacyCropLocator,
    render_blank_crop,
    render_pdf_crop,
)
from drill.models import QuestionAsset, QuestionDocument


class Command(BaseCommand):
    help = 'Safely re-render legacy normalized question crops from their exact PDFs.'

    def add_arguments(self, parser):
        parser.add_argument('pdf_directory', type=Path)
        parser.add_argument('--dpi', type=int, default=180)
        parser.add_argument('--source-dpi', type=int, default=108)
        parser.add_argument(
            '--source-id', type=int, action='append',
            help='Limit work to one or more QuestionDocument source IDs.',
        )
        parser.add_argument('--force', action='store_true')
        parser.add_argument(
            '--formula-aware-text-bounds', action='store_true',
            help='Move link-anchor crop edges above tall PDF text/formula blocks.',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        pdf_directory = options['pdf_directory'].expanduser().resolve()
        if not pdf_directory.is_dir():
            raise CommandError(f'PDF directory does not exist: {pdf_directory}')
        dpi = options['dpi']
        source_dpi = options['source_dpi']
        formula_aware = options['formula_aware_text_bounds']
        if not 144 <= dpi <= 240:
            raise CommandError('Target DPI must be between 144 and 240.')
        if not 72 <= source_dpi < dpi:
            raise CommandError('Source DPI must be at least 72 and lower than target DPI.')
        if formula_aware and not options['source_id']:
            raise CommandError(
                '--formula-aware-text-bounds requires an explicit --source-id.'
            )

        source_files = self._source_files(pdf_directory)
        documents_query = (
            QuestionDocument.objects.annotate(asset_count=Count('questions__assets'))
            .filter(asset_count__gt=0)
            .exclude(parser_strategy__startswith='pymupdf-bookmarks-crops')
            .order_by('source_id')
        )
        if options['source_id']:
            documents_query = documents_query.filter(source_id__in=options['source_id'])
        documents = list(documents_query)
        if not documents:
            raise CommandError('No legacy question documents matched the requested source IDs.')
        missing = [document.filename for document in documents if document.sha256 not in source_files]
        if missing:
            raise CommandError(f'Missing exact source PDFs: {", ".join(missing)}')

        plans = []
        for document in documents:
            if not options['force'] and not QuestionAsset.objects.filter(
                question__document=document,
            ).exclude(render_dpi=dpi).exists():
                self.stdout.write(f'{document.display_title}: already {dpi} DPI; skipped.')
                continue
            source_path = source_files[document.sha256]
            try:
                plan, blank_count, ambiguous_count = self._build_plan(
                    document, source_path, source_dpi, formula_aware,
                )
            except (OSError, ValueError, pymupdf.FileDataError) as exc:
                raise CommandError(f'Preflight failed for {document.filename}: {exc}') from exc
            plans.append((document, source_path, plan))
            self.stdout.write(
                f'{document.display_title}: located {len(plan)} assets '
                f'({blank_count} blank, {ambiguous_count} repeated-header crops).'
            )

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Dry run complete: {sum(len(plan) for _doc, _path, plan in plans)} '
                f'assets can be rendered at {dpi} DPI; no database rows changed.'
            ))
            return

        total_assets = 0
        old_bytes = 0
        new_bytes = 0
        for document, source_path, plan in plans:
            updated, before, after = self._apply_plan(
                document, source_path, plan, source_dpi, dpi,
            )
            total_assets += updated
            old_bytes += before
            new_bytes += after
            self.stdout.write(self.style.SUCCESS(
                f'{document.display_title}: updated {updated} assets at {dpi} DPI.'
            ))
        self.stdout.write(self.style.SUCCESS(
            f'Re-render complete: {total_assets} assets; '
            f'{old_bytes / 1024 / 1024:.1f} MiB -> {new_bytes / 1024 / 1024:.1f} MiB.'
        ))

    @staticmethod
    def _source_files(directory):
        result = {}
        for path in directory.glob('*.pdf'):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result[digest] = path
        return result

    @staticmethod
    def _build_plan(document, source_path, source_dpi, formula_aware=False):
        plan = {}
        blank_count = 0
        ambiguous_count = 0
        previous_end = None
        with pymupdf.open(source_path) as pdf:
            locator = None
            adjuster = FormulaAwareCropAdjuster(pdf) if formula_aware else None
            selected_fields = [
                'id', 'render_dpi', 'source_page_index',
                'source_x0', 'source_y0', 'source_x1', 'source_y1',
            ]
            if not formula_aware:
                selected_fields.append('image_data')
            assets = QuestionAsset.objects.filter(
                question__document=document,
            ).order_by('source_id').only(*selected_fields)
            for asset in assets.iterator(chunk_size=100):
                if asset.source_page_index is not None:
                    location = CropLocation(
                        asset.source_page_index,
                        asset.source_x0,
                        asset.source_y0,
                        asset.source_x1,
                        asset.source_y1,
                        1.0,
                    )
                else:
                    if locator is None:
                        locator = LegacyCropLocator(pdf, source_dpi=source_dpi)
                    location, previous_end = locator.locate(
                        bytes(asset.image_data), previous_end=previous_end,
                    )
                if adjuster is not None:
                    location = adjuster.adjust(location)
                blank_count += int(location.is_blank)
                ambiguous_count += int(location.ambiguous)
                plan[asset.pk] = location
        return plan, blank_count, ambiguous_count

    def _apply_plan(self, document, source_path, plan, source_dpi, dpi):
        updated = 0
        old_bytes = 0
        new_bytes = 0
        with pymupdf.open(source_path) as pdf, transaction.atomic():
            assets = QuestionAsset.objects.select_for_update().filter(
                pk__in=plan,
            ).order_by('source_id')
            for asset in assets.iterator(chunk_size=50):
                location = plan[asset.pk]
                old_bytes += len(asset.image_data)
                if location.is_blank:
                    scale = dpi / (asset.render_dpi or source_dpi)
                    image_data, width, height = render_blank_crop(
                        round(asset.width * scale),
                        round(asset.height * scale),
                        dpi,
                    )
                else:
                    image_data, width, height = render_pdf_crop(pdf, location, dpi)
                asset.image_data = image_data
                asset.sha256 = hashlib.sha256(image_data).hexdigest()
                asset.width = width
                asset.height = height
                asset.render_dpi = dpi
                asset.source_page_index = location.page_index
                asset.source_x0 = location.x0
                asset.source_y0 = location.y0
                asset.source_x1 = location.x1
                asset.source_y1 = location.y1
                asset.save(update_fields=(
                    'image_data', 'sha256', 'width', 'height', 'render_dpi',
                    'source_page_index', 'source_x0', 'source_y0', 'source_x1', 'source_y1',
                ))
                updated += 1
                new_bytes += len(image_data)
                if updated % 250 == 0:
                    self.stdout.write(
                        f'{document.display_title}: rendered {updated}/{len(plan)}…'
                    )
        return updated, old_bytes, new_bytes
