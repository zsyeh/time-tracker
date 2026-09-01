import hashlib
from collections import defaultdict
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.asset_rerender import trailing_edge_fragment_start
from drill.models import QuestionAsset, QuestionDocument
from drill.pdf_import import parse_question_pdf, render_segment_png


REPAIR_MARKER = 'source-edge-safe-v2'


class Command(BaseCommand):
    help = 'Re-render clipped cxy question crops from the exact vector PDF without replacing questions.'

    def add_arguments(self, parser):
        parser.add_argument('pdf_path', type=Path)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        pdf_path = options['pdf_path'].expanduser().resolve()
        if not pdf_path.is_file():
            raise CommandError(f'PDF does not exist: {pdf_path}')
        parsed = parse_question_pdf(pdf_path)
        document = QuestionDocument.objects.filter(sha256=parsed.sha256).first()
        if document is None:
            raise CommandError('The exact source PDF is not registered in the database.')
        if REPAIR_MARKER in document.parser_strategy:
            self.stdout.write(self.style.SUCCESS('Source crop edges are already repaired.'))
            return

        assets = list(
            QuestionAsset.objects.filter(
                question__document=document,
                asset_type='question_crop',
                source_page_index__isnull=False,
                source_y0__isnull=False,
                source_y1__isnull=False,
                render_dpi__isnull=False,
            ).select_related('question').order_by('source_page_index', 'source_y0', 'pk')
        )
        cut_pairs = []
        for current, following in zip(assets, assets[1:]):
            contiguous = (
                current.source_page_index == following.source_page_index
                and current.render_dpi == following.render_dpi
                and abs(current.width - following.width) <= 2
                and abs(current.source_y1 - following.source_y0) <= 2.0
            )
            if contiguous and trailing_edge_fragment_start(
                bytes(current.image_data), current.render_dpi,
            ) is not None:
                cut_pairs.append((current, following))
        affected_questions = {
            asset.question_id: asset.question
            for pair in cut_pairs for asset in pair
        }

        parsed_by_label = defaultdict(list)
        for item in parsed.questions:
            parsed_by_label[item.source_label].append(item)
        plans = []
        for question in affected_questions.values():
            question_assets = [asset for asset in assets if asset.question_id == question.pk]
            candidates = [
                item for item in parsed_by_label.get(question.source_label, [])
                if len(item.segments) == len(question_assets)
                and [segment.page_index for segment in item.segments]
                == [asset.source_page_index for asset in question_assets]
            ]
            if not candidates:
                raise CommandError(f'No exact source match for question {question.uuid}.')
            ranked = sorted((
                (
                    sum(abs(segment.y0 - asset.source_y0) for segment, asset in zip(item.segments, question_assets)),
                    item,
                )
                for item in candidates
            ), key=lambda match: match[0])
            if len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) < 0.5:
                raise CommandError(f'Ambiguous source match for question {question.uuid}.')
            if ranked[0][0] > 45:
                raise CommandError(
                    f'Source match for question {question.uuid} moved {ranked[0][0]:.1f}pt; refusing.'
                )
            plans.append((question, question_assets, ranked[0][1]))

        self.stdout.write(
            f'{len(cut_pairs)} cut edge(s), {len(plans)} questions and '
            f'{sum(len(item[1]) for item in plans)} assets are uniquely source-matched.'
        )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; no rows changed.'))
            return

        with pymupdf.open(pdf_path) as pdf, transaction.atomic():
            for _question, question_assets, parsed_question in plans:
                for asset, segment in zip(question_assets, parsed_question.segments):
                    image_data, width, height = render_segment_png(pdf, segment, asset.render_dpi)
                    asset.image_data = image_data
                    asset.sha256 = hashlib.sha256(image_data).hexdigest()
                    asset.width = width
                    asset.height = height
                    asset.source_page_index = segment.page_index
                    asset.source_x0 = segment.x0
                    asset.source_y0 = segment.y0
                    asset.source_x1 = segment.x1
                    asset.source_y1 = segment.y1
                    asset.save(update_fields=(
                        'image_data', 'sha256', 'width', 'height', 'source_page_index',
                        'source_x0', 'source_y0', 'source_x1', 'source_y1',
                    ))
            document.parser_strategy = '+'.join(filter(None, (
                document.parser_strategy, REPAIR_MARKER,
            )))
            document.save(update_fields=('parser_strategy',))
        self.stdout.write(self.style.SUCCESS(
            f'Re-rendered {sum(len(item[1]) for item in plans)} source-authenticated assets.'
        ))
