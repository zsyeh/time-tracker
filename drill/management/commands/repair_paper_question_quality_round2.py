import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


TYPE_REPAIRS = {
    uuid.UUID('4f1a2828-9f14-5252-b94a-b91c487b5292'): 'fill_blank',
    uuid.UUID('c28ff9b2-dacb-5416-8a41-2d455ba2ac77'): 'fill_blank',
    uuid.UUID('537c5d69-30e5-5562-a283-2d856cb0bd5f'): 'solution',
}
CROP_UUID = uuid.UUID('b3b1c84b-3aa8-5924-8409-ae47c19d5dce')
CROP_ASSET_ID = 4098
CROP_HEIGHT = 195


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
    help = 'Apply the second visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = set(TYPE_REPAIRS) | {CROP_UUID}
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        crop_question = questions[CROP_UUID]
        try:
            asset = crop_question.assets.select_for_update().get(pk=CROP_ASSET_ID)
        except crop_question.assets.model.DoesNotExist as exc:
            raise CommandError(f'Missing expected crop asset {CROP_ASSET_ID}.') from exc
        already_applied = (
            asset.height == CROP_HEIGHT
            and all(
                questions[question_uuid].question_type == question_type
                and questions[question_uuid].question_type_human_verified
                for question_uuid, question_type in TYPE_REPAIRS.items()
            )
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-two paper quality repairs are already applied.'))
            return
        if asset.height != 263:
            raise CommandError(
                f'Expected untouched 263px asset {CROP_ASSET_ID}; found {asset.height}px.',
            )
        png, width, height = crop_png(
            bytes(asset.image_data), width=asset.width, y1=CROP_HEIGHT,
        )
        self.stdout.write(
            f'Validated {len(TYPE_REPAIRS)} type corrections and crop '
            f'{asset.width}x{asset.height} -> {width}x{height}.',
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = {crop_question}
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

        original_height = asset.height
        original_source_y0 = asset.source_y0
        original_source_y1 = asset.source_y1
        asset.image_data = png
        asset.width = width
        asset.height = height
        asset.sha256 = hashlib.sha256(png).hexdigest()
        fields = ['image_data', 'width', 'height', 'sha256']
        if original_source_y0 is not None and original_source_y1 is not None:
            asset.source_y1 = original_source_y0 + (
                (original_source_y1 - original_source_y0) * CROP_HEIGHT / original_height
            )
            fields.append('source_y1')
        asset.save(update_fields=fields)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-two quality repairs to {len(changed)} questions.',
        ))
