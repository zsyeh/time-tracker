import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


TYPE_REPAIRS = {
    uuid.UUID('a3febf0d-114c-5a8a-96ba-4fc29124a28f'): 'fill_blank',
    uuid.UUID('6c92ce2a-7ba8-5492-bb5a-1b83ef1a28bf'): 'fill_blank',
    uuid.UUID('18866a6f-d86c-5f6e-b994-b372cf049088'): 'solution',
    uuid.UUID('443d7d23-f4d1-5be7-99f7-45e350df384c'): 'single_choice',
}
SWAPPED_ASSET_UUID = uuid.UUID('7b001a58-215a-56cd-a619-f46a34586569')
CROP_REPAIRS = {
    uuid.UUID('eae60425-3caf-5826-b53b-a7f1bdfec794'): (
        (3823, 0, 170, 'question_crop'),
        (3824, None, None, 'source_context'),
    ),
    uuid.UUID('85e70ec0-a40e-54bb-b06b-3dce5e3dab6a'): (
        (1561, 0, 70, 'question_crop'),
        (1562, 80, 316, 'question_crop'),
    ),
}


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
    help = 'Repair verified paper-candidate type labels and malformed image assets.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = set(TYPE_REPAIRS) | set(CROP_REPAIRS) | {SWAPPED_ASSET_UUID}
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')

        current_assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.all()
        }
        already_applied = (
            all(
                questions[question_uuid].question_type == question_type
                and questions[question_uuid].question_type_human_verified
                for question_uuid, question_type in TYPE_REPAIRS.items()
            )
            and current_assets.get(21999)
            and current_assets[21999].asset_type == 'question_crop'
            and current_assets.get(21998)
            and current_assets[21998].asset_type == 'answer_crop'
            and current_assets.get(3823)
            and current_assets[3823].height == 170
            and current_assets.get(3824)
            and current_assets[3824].asset_type == 'source_context'
            and current_assets.get(1561)
            and current_assets[1561].height == 70
            and current_assets.get(1562)
            and current_assets[1562].height == 236
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Paper question quality repairs are already applied.'))
            return

        prepared_crops = {}
        for question_uuid, specs in CROP_REPAIRS.items():
            question = questions[question_uuid]
            assets = {asset.pk: asset for asset in question.assets.select_for_update()}
            for asset_id, y0, y1, asset_type in specs:
                if asset_id not in assets:
                    raise CommandError(f'Missing asset {asset_id} for {question_uuid}.')
                asset = assets[asset_id]
                if y0 is not None:
                    if y1 > asset.height:
                        raise CommandError(f'Asset {asset_id} is shorter than {y1}px.')
                    prepared_crops[asset_id] = crop_png(
                        bytes(asset.image_data), width=asset.width, y0=y0, y1=y1,
                    )

        swapped = questions[SWAPPED_ASSET_UUID]
        swapped_assets = {asset.pk: asset for asset in swapped.assets.select_for_update()}
        if set(swapped_assets) != {21998, 21999}:
            raise CommandError(
                f'Expected assets 21998 and 21999 for {SWAPPED_ASSET_UUID}; '
                f'found {sorted(swapped_assets)}.'
            )
        self.stdout.write(
            f'Validated {len(TYPE_REPAIRS)} type repairs, {len(prepared_crops)} crops, '
            'and one reversed question/answer pair.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed_questions = set()
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
            changed_questions.add(question)

        swapped.display_label = 'Exponential limit · geometric mean'
        swapped.prompt_text = (
            'For positive a, b and c, evaluate '
            'lim[x→∞] ((a^(1/x)+b^(1/x)+c^(1/x))/3)^x.'
        )
        swapped.content_mode = 'image'
        swapped.question_type = 'solution'
        swapped.question_type_source = 'human'
        swapped.question_type_confidence = 1
        swapped.question_type_human_verified = True
        swapped.save(update_fields=(
            'display_label', 'prompt_text', 'content_mode', 'question_type',
            'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        swapped_assets[21999].asset_type = 'question_crop'
        swapped_assets[21999].position = 0
        swapped_assets[21999].save(update_fields=('asset_type', 'position'))
        swapped_assets[21998].asset_type = 'answer_crop'
        swapped_assets[21998].position = 0
        swapped_assets[21998].save(update_fields=('asset_type', 'position'))
        changed_questions.add(swapped)

        for question_uuid, specs in CROP_REPAIRS.items():
            question = questions[question_uuid]
            assets = {asset.pk: asset for asset in question.assets.select_for_update()}
            for asset_id, y0, y1, asset_type in specs:
                asset = assets[asset_id]
                asset.asset_type = asset_type
                fields = ['asset_type']
                if y0 is not None:
                    original_height = asset.height
                    original_source_y0 = asset.source_y0
                    original_source_y1 = asset.source_y1
                    png, width, height = prepared_crops[asset_id]
                    asset.image_data = png
                    asset.width = width
                    asset.height = height
                    asset.sha256 = hashlib.sha256(png).hexdigest()
                    fields.extend(('image_data', 'width', 'height', 'sha256'))
                    if original_source_y0 is not None and original_source_y1 is not None:
                        span = original_source_y1 - original_source_y0
                        asset.source_y0 = original_source_y0 + span * y0 / original_height
                        asset.source_y1 = original_source_y0 + span * y1 / original_height
                        fields.extend(('source_y0', 'source_y1'))
                asset.save(update_fields=fields)
            changed_questions.add(question)

        for question in changed_questions:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Repaired {len(changed_questions)} questions and captured fresh revisions.',
        ))
