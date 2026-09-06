import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


SPECS = (
    (uuid.UUID('9e5d4817-7f74-522e-8d72-f1105423caa4'), 1763, 303, 250),
    (uuid.UUID('b62ff395-ca64-562a-a930-962cdcb27cf2'), 3032, 234, 175),
    (uuid.UUID('a7170fe4-1561-5a2b-885c-6c919c01f6f7'), 3303, 220, 170),
)
TYPE_UUID = uuid.UUID('e864f276-af96-57d7-8ff7-ced272309fa7')


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
    help = 'Apply the fifth visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {item[0] for item in SPECS} | {TYPE_UUID}
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
        if all(assets.get(asset_id) and assets[asset_id].height == target for _, asset_id, _, target in SPECS) \
                and questions[TYPE_UUID].question_type == 'solution' \
                and questions[TYPE_UUID].question_type_human_verified:
            self.stdout.write(self.style.SUCCESS('Round-five paper quality repairs are already applied.'))
            return
        rendered = {}
        for _, asset_id, original_height, target_height in SPECS:
            asset = assets.get(asset_id)
            if asset is None or asset.height != original_height:
                raise CommandError(
                    f'Expected untouched asset {asset_id} at {original_height}px; '
                    f'found {getattr(asset, "height", None)}px.',
                )
            rendered[asset_id] = crop_png(
                bytes(asset.image_data), width=asset.width, y1=target_height,
            )
        self.stdout.write('Validated three trailing-fragment trims and one type correction.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for question_uuid, asset_id, original_height, target_height in SPECS:
            asset = assets[asset_id]
            original_source_y0 = asset.source_y0
            original_source_y1 = asset.source_y1
            png, width, height = rendered[asset_id]
            asset.image_data = png
            asset.width = width
            asset.height = height
            asset.sha256 = hashlib.sha256(png).hexdigest()
            fields = ['image_data', 'width', 'height', 'sha256']
            if original_source_y0 is not None and original_source_y1 is not None:
                asset.source_y1 = original_source_y0 + (
                    (original_source_y1 - original_source_y0) * target_height / original_height
                )
                fields.append('source_y1')
            asset.save(update_fields=fields)
            changed.add(questions[question_uuid])

        question = questions[TYPE_UUID]
        question.question_type = 'solution'
        question.question_type_source = 'human'
        question.question_type_confidence = 1
        question.question_type_human_verified = True
        question.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        changed.add(question)
        for item in changed:
            QuestionRevision.capture(item)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-five quality repairs to {len(changed)} questions.',
        ))
