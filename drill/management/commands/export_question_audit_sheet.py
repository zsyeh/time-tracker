from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError

from drill.models import ExamPaper, Question


PAGE_WIDTH = 1684
PAGE_HEIGHT = 1190
MARGIN = 28
GAP = 18
COLUMNS = 2
ROWS = 2
HEADER_HEIGHT = 38


class Command(BaseCommand):
    help = 'Export high-resolution contact sheets for visual question-crop auditing.'

    def add_arguments(self, parser):
        parser.add_argument('--paper')
        parser.add_argument('--question-ids')
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--raw-assets', action='store_true')

    def handle(self, *args, **options):
        if bool(options['paper']) == bool(options['question_ids']):
            raise CommandError('Provide exactly one of --paper or --question-ids.')
        if options['paper']:
            try:
                paper = ExamPaper.objects.get(uuid=options['paper'])
            except ExamPaper.DoesNotExist as exc:
                raise CommandError('Paper does not exist.') from exc
            question_ids = list(
                paper.items.order_by('position').values_list('question_id', flat=True),
            )
        else:
            try:
                question_ids = [
                    int(value.strip())
                    for value in options['question_ids'].split(',')
                    if value.strip()
                ]
            except ValueError as exc:
                raise CommandError('--question-ids must be comma-separated integers.') from exc
        questions = {
            item.pk: item
            for item in Question.objects.filter(pk__in=question_ids).select_related(
                'document', 'similarity_topic', 'topic',
            ).prefetch_related('assets')
        }
        missing = [pk for pk in question_ids if pk not in questions]
        if missing:
            raise CommandError(f'Questions do not exist: {missing}')

        output_dir = Path(options['output_dir']).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        document = pymupdf.open()
        cards_per_page = COLUMNS * ROWS
        card_width = (PAGE_WIDTH - 2 * MARGIN - GAP) / COLUMNS
        card_height = (PAGE_HEIGHT - 2 * MARGIN - GAP) / ROWS

        for index, question_id in enumerate(question_ids):
            slot = index % cards_per_page
            if slot == 0:
                page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            row, column = divmod(slot, COLUMNS)
            x0 = MARGIN + column * (card_width + GAP)
            y0 = MARGIN + row * (card_height + GAP)
            card = pymupdf.Rect(x0, y0, x0 + card_width, y0 + card_height)
            page.draw_rect(card, color=(0.35, 0.38, 0.42), width=1)
            question = questions[question_id]
            topic = question.similarity_topic or question.topic
            label = (
                f'{index + 1:02d}  qid={question.pk}  doc={question.document_id}  '
                f'type={question.question_type}  assets='
                f'{question.assets.filter(asset_type="question_crop").count()}'
            )
            page.insert_text(
                (x0 + 10, y0 + 24), label, fontname='helv', fontsize=12,
                color=(0.12, 0.12, 0.12),
            )
            meta = (
                f'order={question.question_order}  topic_id={topic.pk if topic else "-"}  '
                f'label={question.source_label[:70]}'
            )
            page.insert_text(
                (x0 + 10, y0 + 36), meta.encode('ascii', 'replace').decode('ascii'),
                fontname='helv', fontsize=8, color=(0.25, 0.25, 0.25),
            )
            image_box = pymupdf.Rect(
                x0 + 8, y0 + HEADER_HEIGHT + 8,
                x0 + card_width - 8, y0 + card_height - 8,
            )
            if options['raw_assets']:
                for raw_asset in question.assets.all():
                    (output_dir / (
                        f'q{question.pk}-a{raw_asset.pk}-p{raw_asset.position}-'
                        f'{raw_asset.asset_type}.png'
                    )).write_bytes(bytes(raw_asset.image_data))
            assets = list(question.assets.filter(asset_type='question_crop').order_by('position', 'pk'))
            if not assets:
                page.insert_text(
                    (image_box.x0 + 8, image_box.y0 + 24), 'NO QUESTION CROP',
                    fontname='helv', fontsize=18, color=(0.8, 0.1, 0.1),
                )
                continue
            total_height = sum(max(asset.height, 1) for asset in assets)
            cursor = image_box.y0
            for asset in assets:
                allocated = image_box.height * max(asset.height, 1) / total_height
                target = pymupdf.Rect(image_box.x0, cursor, image_box.x1, cursor + allocated)
                page.insert_image(target, stream=bytes(asset.image_data), keep_proportion=True)
                cursor += allocated

        pdf_path = output_dir / 'question-audit.pdf'
        document.save(pdf_path, garbage=4, deflate=True)
        page_count = document.page_count
        for page_number, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            pixmap.save(output_dir / f'question-audit-{page_number + 1:02d}.png')
        document.close()
        self.stdout.write(self.style.SUCCESS(
            f'Exported {len(question_ids)} questions across {page_count} page(s) to {output_dir}',
        ))
