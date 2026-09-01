import hashlib
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.asset_rerender import (
    crop_pixmap_rows, reframe_crop_image, trailing_edge_fragment_start,
)
from drill.models import QuestionAsset, QuestionDocument


REPAIR_MARKER = 'edge-safe-v1'


class Command(BaseCommand):
    help = 'Move formula fragments crossing legacy question-crop boundaries to the correct question.'

    def add_arguments(self, parser):
        parser.add_argument('--source-id', type=int, action='append')
        parser.add_argument('--max-points', type=float, default=18.0)
        parser.add_argument('--separator-points', type=float, default=3.0)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if not 8 <= options['max_points'] <= 30:
            raise CommandError('--max-points must be between 8 and 30.')
        if not 1.5 <= options['separator_points'] <= 8:
            raise CommandError('--separator-points must be between 1.5 and 8.')

        documents = QuestionDocument.objects.filter(
            workspace='drill',
        ).exclude(
            parser_strategy__startswith='pymupdf-bookmarks-crops',
        ).exclude(
            parser_strategy__contains=REPAIR_MARKER,
        ).order_by('source_id')
        if options['source_id']:
            documents = documents.filter(source_id__in=options['source_id'])
        documents = list(documents)
        if not documents:
            self.stdout.write(self.style.SUCCESS('No unrepaired legacy documents matched.'))
            return

        total_candidates = 0
        total_updated = 0
        for document in documents:
            pages = self._page_assets(document)
            candidates = self._count_candidates(pages, options)
            total_candidates += candidates
            self.stdout.write(f'{document.display_title or document.title}: {candidates} cut edge(s) found.')
            if options['dry_run']:
                continue
            with transaction.atomic():
                updated = self._repair_pages(pages, options)
                document.parser_strategy = '+'.join(filter(None, (
                    document.parser_strategy, REPAIR_MARKER,
                )))
                document.save(update_fields=('parser_strategy',))
            total_updated += updated
            self.stdout.write(self.style.SUCCESS(
                f'{document.display_title or document.title}: repaired {updated} crop image(s).'
            ))
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Dry run complete: {total_candidates} cut edge(s); no rows changed.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Crop-edge repair complete: {total_candidates} fragments, {total_updated} images updated.'
            ))

    @staticmethod
    def _page_assets(document):
        pages = defaultdict(list)
        assets = QuestionAsset.objects.filter(
            question__document=document,
            asset_type='question_crop',
            source_page_index__isnull=False,
            source_y0__isnull=False,
            source_y1__isnull=False,
            render_dpi__isnull=False,
        ).select_related('question').defer('image_data').order_by(
            'source_page_index', 'source_y0', 'pk',
        )
        for asset in assets:
            pages[asset.source_page_index].append(asset)
        return pages

    @staticmethod
    def _contiguous(first, second):
        return (
            first.render_dpi == second.render_dpi
            and abs(first.width - second.width) <= 2
            and abs(first.source_y1 - second.source_y0) <= 2.0
        )

    def _fragment_start(self, asset, options):
        try:
            return trailing_edge_fragment_start(
                bytes(asset.image_data), asset.render_dpi,
                max_points=options['max_points'],
                separator_points=options['separator_points'],
            )
        finally:
            # Binary crops are large; keep the page plan metadata-only on the 2 GiB VPS.
            asset.__dict__.pop('image_data', None)

    def _count_candidates(self, pages, options):
        count = 0
        for assets in pages.values():
            for current, following in zip(assets, assets[1:]):
                if self._contiguous(current, following) and self._fragment_start(current, options) is not None:
                    count += 1
        return count

    def _repair_pages(self, pages, options):
        updated = 0
        for assets in pages.values():
            leading_fragment = None
            leading_y0 = None
            for index, current in enumerate(assets):
                following = assets[index + 1] if index + 1 < len(assets) else None
                fragment_start = None
                fragment = None
                fragment_y0 = None
                if following is not None and self._contiguous(current, following):
                    fragment_start = self._fragment_start(current, options)
                    if fragment_start is not None:
                        raw = bytes(current.image_data)
                        fragment = crop_pixmap_rows(
                            raw, fragment_start, current.height, current.render_dpi,
                        )
                        fragment_y0 = current.source_y1 - (
                            (current.height - fragment_start) * 72.0 / current.render_dpi
                        )

                if leading_fragment is not None or fragment_start is not None:
                    raw = bytes(current.image_data)
                    trim_rows = current.height - fragment_start if fragment_start is not None else 0
                    image_data, width, height, _leading_height = reframe_crop_image(
                        raw, current.render_dpi,
                        leading_fragment=leading_fragment,
                        trim_bottom_rows=trim_rows,
                    )
                    current.image_data = image_data
                    current.sha256 = hashlib.sha256(image_data).hexdigest()
                    current.width = width
                    current.height = height
                    if leading_y0 is not None:
                        current.source_y0 = leading_y0
                    if fragment_y0 is not None:
                        current.source_y1 = fragment_y0
                    current.save(update_fields=(
                        'image_data', 'sha256', 'width', 'height', 'source_y0', 'source_y1',
                    ))
                    updated += 1

                leading_fragment = fragment
                leading_y0 = fragment_y0
                current.__dict__.pop('image_data', None)
        return updated
