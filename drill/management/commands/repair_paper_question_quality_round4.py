import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


TYPE_REPAIRS = {
    uuid.UUID('16f8e5ca-9d08-55ed-a2f1-5ef7f3bfb191'): 'fill_blank',
    uuid.UUID('fc287a9b-d2a6-54db-bc62-3a6cea13cb98'): 'single_choice',
}
MATRIX_UUID = uuid.UUID('98c38e71-4b72-5c4a-86df-7b816311ef3d')


def crop_png(raw, *, width, y0, y1):
    document = pymupdf.open(stream=raw, filetype='png')
    try:
        page = document[0]
        scale = width / page.rect.width
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            clip=pymupdf.Rect(0, y0 / scale, page.rect.width, y1 / scale),
            alpha=False,
        )
        return pixmap.tobytes('png'), pixmap.width, pixmap.height
    finally:
        document.close()


class Command(BaseCommand):
    help = 'Apply the fourth visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = set(TYPE_REPAIRS) | {MATRIX_UUID}
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        matrix = questions[MATRIX_UUID]
        assets = {asset.pk: asset for asset in matrix.assets.select_for_update()}
        if 2284 not in assets or 2285 not in assets:
            raise CommandError('Missing the expected matrix question crops.')
        already_applied = (
            assets[2284].asset_type == 'source_context'
            and assets[2285].height == 158
            and all(
                questions[question_uuid].question_type == question_type
                and questions[question_uuid].question_type_human_verified
                for question_uuid, question_type in TYPE_REPAIRS.items()
            )
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-four paper quality repairs are already applied.'))
            return
        if assets[2285].height != 238:
            raise CommandError(f'Expected untouched asset 2285 at 238px; found {assets[2285].height}px.')
        png, width, height = crop_png(
            bytes(assets[2285].image_data), width=assets[2285].width, y0=80, y1=238,
        )
        self.stdout.write('Validated two type corrections and one page-boundary crop repair.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = {matrix}
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

        assets[2284].asset_type = 'source_context'
        assets[2284].save(update_fields=('asset_type',))
        target = assets[2285]
        original_height = target.height
        original_source_y0 = target.source_y0
        original_source_y1 = target.source_y1
        target.image_data = png
        target.width = width
        target.height = height
        target.sha256 = hashlib.sha256(png).hexdigest()
        fields = ['image_data', 'width', 'height', 'sha256']
        if original_source_y0 is not None and original_source_y1 is not None:
            span = original_source_y1 - original_source_y0
            target.source_y0 = original_source_y0 + span * 80 / original_height
            target.source_y1 = original_source_y1
            fields.extend(('source_y0', 'source_y1'))
        target.save(update_fields=fields)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-four quality repairs to {len(changed)} questions.',
        ))
