import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


TYPE_REPAIRS = {
    uuid.UUID('eb2f4a59-3b1e-5897-b577-ef0331d661f0'): 'fill_blank',
    uuid.UUID('b87aadd7-0381-587e-977f-92f88c99d737'): 'fill_blank',
    uuid.UUID('a0b876ce-1d83-51c6-81be-9df600643c31'): 'fill_blank',
}
CROPS = (
    (uuid.UUID('64807760-ff1d-535d-94d3-6105886f1121'), 352, 842, 230, 'question_crop'),
    (uuid.UUID('64807760-ff1d-535d-94d3-6105886f1121'), 353, 180, None, 'source_context'),
    (uuid.UUID('dbb5a9b6-5ee9-5f7e-9212-b34fa0bd8336'), 3062, 291, 230, 'question_crop'),
    (uuid.UUID('338df646-275c-5fe2-8b0a-1b405114b2df'), 3047, 337, 265, 'question_crop'),
    (uuid.UUID('eb77c1ac-f047-5166-947c-7c88548c1729'), 3250, 228, 125, 'question_crop'),
    (uuid.UUID('02cbe0b4-13c6-5d48-ad12-802d04e27afe'), 3540, 329, 110, 'question_crop'),
    (uuid.UUID('02cbe0b4-13c6-5d48-ad12-802d04e27afe'), 3541, 122, None, 'source_context'),
)


def crop_png(raw, *, width, y1):
    document = pymupdf.open(stream=raw, filetype='png')
    try:
        page = document[0]
        scale = width / page.rect.width
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            clip=pymupdf.Rect(0, 0, page.rect.width, y1 / scale),
            alpha=False,
        )
        return pixmap.tobytes('png'), pixmap.width, pixmap.height
    finally:
        document.close()


class Command(BaseCommand):
    help = 'Apply the sixth visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = set(TYPE_REPAIRS) | {item[0] for item in CROPS}
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            all(
                assets.get(asset_id)
                and (
                    assets[asset_id].height == target_height
                    if target_height is not None
                    else assets[asset_id].asset_type == target_type
                )
                for _, asset_id, _, target_height, target_type in CROPS
            )
            and all(
                questions[question_uuid].question_type == question_type
                and questions[question_uuid].question_type_human_verified
                for question_uuid, question_type in TYPE_REPAIRS.items()
            )
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-six paper quality repairs are already applied.'))
            return
        rendered = {}
        for _, asset_id, original_height, target_height, _ in CROPS:
            asset = assets.get(asset_id)
            if asset is None or asset.height != original_height:
                raise CommandError(
                    f'Expected untouched asset {asset_id} at {original_height}px; '
                    f'found {getattr(asset, "height", None)}px.',
                )
            if target_height is not None:
                rendered[asset_id] = crop_png(
                    bytes(asset.image_data), width=asset.width, y1=target_height,
                )
        self.stdout.write('Validated five trims, two context demotions, and three type corrections.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for question_uuid, asset_id, original_height, target_height, target_type in CROPS:
            asset = assets[asset_id]
            asset.asset_type = target_type
            fields = ['asset_type']
            if target_height is not None:
                original_source_y0 = asset.source_y0
                original_source_y1 = asset.source_y1
                png, width, height = rendered[asset_id]
                asset.image_data = png
                asset.width = width
                asset.height = height
                asset.sha256 = hashlib.sha256(png).hexdigest()
                fields.extend(('image_data', 'width', 'height', 'sha256'))
                if original_source_y0 is not None and original_source_y1 is not None:
                    asset.source_y1 = original_source_y0 + (
                        (original_source_y1 - original_source_y0) * target_height / original_height
                    )
                    fields.append('source_y1')
            asset.save(update_fields=fields)
            changed.add(questions[question_uuid])

        for question_uuid, question_type in TYPE_REPAIRS.items():
            question = questions[question_uuid]
            question.question_type = question_type
            question.question_type_source = 'human'
            question.question_type_confidence = 1
            question.question_type_human_verified = True
            question.save(update_fields=(
                'question_type', 'question_type_source', 'question_type_confidence',
                'question_type_human_verified',
            ))
            changed.add(question)
        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-six quality repairs to {len(changed)} questions.',
        ))
