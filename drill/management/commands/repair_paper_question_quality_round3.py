import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset, QuestionRevision


SPLIT_UUID = uuid.UUID('6ecdd8e0-5a6b-5caf-ac67-a78d62850315')
NEW_UUID = uuid.uuid5(uuid.NAMESPACE_URL, f'time-tracker:split:{SPLIT_UUID}:660-607')
TYPE_UUID = uuid.UUID('a93953e2-0edc-56bd-83d3-59feb0c16f57')
SIMPLE_CROPS = (
    (uuid.UUID('70fa0ee8-3fd1-5e1e-a669-3c8c6ba59aae'), 3551, 0, 300, 'question_crop'),
    (uuid.UUID('3162605b-2f5b-52ed-8fb1-68904d01cc5a'), 413, 0, 170, 'question_crop'),
    (uuid.UUID('3162605b-2f5b-52ed-8fb1-68904d01cc5a'), 414, None, None, 'source_context'),
    (uuid.UUID('100e5087-0819-57f9-9b95-356ac0e7f690'), 2212, 0, 330, 'question_crop'),
    (uuid.UUID('100e5087-0819-57f9-9b95-356ac0e7f690'), 2213, None, None, 'source_context'),
)


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


def next_source_id(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


def update_crop(asset, rendered, *, y0, y1, original_height):
    png, width, height = rendered
    original_source_y0 = asset.source_y0
    original_source_y1 = asset.source_y1
    asset.image_data = png
    asset.width = width
    asset.height = height
    asset.sha256 = hashlib.sha256(png).hexdigest()
    fields = ['image_data', 'width', 'height', 'sha256']
    if original_source_y0 is not None and original_source_y1 is not None:
        span = original_source_y1 - original_source_y0
        asset.source_y0 = original_source_y0 + span * y0 / original_height
        asset.source_y1 = original_source_y0 + span * y1 / original_height
        fields.extend(('source_y0', 'source_y1'))
    asset.save(update_fields=fields)


class Command(BaseCommand):
    help = 'Apply the third visually verified paper-candidate crop and split repairs.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected_uuids = {item[0] for item in SIMPLE_CROPS} | {SPLIT_UUID, TYPE_UUID}
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected_uuids)
        }
        missing = expected_uuids - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            Question.objects.filter(uuid=NEW_UUID).exists()
            and assets.get(3551) and assets[3551].height == 300
            and assets.get(413) and assets[413].height == 170
            and assets.get(414) and assets[414].asset_type == 'source_context'
            and assets.get(2212) and assets[2212].height == 330
            and assets.get(2213) and assets[2213].asset_type == 'source_context'
            and assets.get(3828) and assets[3828].height == 210
            and questions[TYPE_UUID].question_type == 'fill_blank'
            and questions[TYPE_UUID].question_type_human_verified
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-three paper quality repairs are already applied.'))
            return
        if Question.objects.filter(uuid=NEW_UUID).exists():
            raise CommandError('The joined ODE record is partially split; refusing an ambiguous repair.')

        expected_heights = {3551: 364, 413: 355, 2212: 778, 3828: 447, 15821: 1009, 15822: 2105}
        for asset_id, height in expected_heights.items():
            if asset_id not in assets or assets[asset_id].height != height:
                found = assets.get(asset_id)
                raise CommandError(
                    f'Expected untouched asset {asset_id} at {height}px; '
                    f'found {getattr(found, "height", None)}px.',
                )

        rendered_simple = {
            asset_id: crop_png(bytes(assets[asset_id].image_data), width=assets[asset_id].width, y0=y0, y1=y1)
            for _, asset_id, y0, y1, _ in SIMPLE_CROPS if y0 is not None
        }
        split_asset = assets[3828]
        first_question = crop_png(
            bytes(split_asset.image_data), width=split_asset.width, y0=0, y1=210,
        )
        second_question = crop_png(
            bytes(split_asset.image_data), width=split_asset.width, y0=210, y1=395,
        )
        first_answer = crop_png(
            bytes(assets[15821].image_data), width=assets[15821].width, y0=0, y1=700,
        )
        second_answer = crop_png(
            bytes(assets[15822].image_data), width=assets[15822].width, y0=0, y1=740,
        )
        self.stdout.write(
            'Validated three trims, two context demotions, one two-way split, '
            'two answer trims, and one type correction.',
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for question_uuid, asset_id, y0, y1, asset_type in SIMPLE_CROPS:
            asset = assets[asset_id]
            asset.asset_type = asset_type
            asset.save(update_fields=('asset_type',))
            if y0 is not None:
                update_crop(
                    asset, rendered_simple[asset_id], y0=y0, y1=y1,
                    original_height=expected_heights[asset_id],
                )
            changed.add(questions[question_uuid])

        type_question = questions[TYPE_UUID]
        type_question.question_type = 'fill_blank'
        type_question.question_type_source = 'human'
        type_question.question_type_confidence = 1
        type_question.question_type_human_verified = True
        type_question.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        changed.add(type_question)

        source = questions[SPLIT_UUID]
        for later in Question.objects.select_for_update().filter(
            document=source.document, question_order__gt=source.question_order,
        ).order_by('-question_order'):
            later.question_order += 1
            later.save(update_fields=('question_order',))
        source.display_label = 'ODE solutions bounded on the real line'
        source.prompt_text = (
            'How many of the four parameter cases make every solution of '
            'y\'\'+ay\'+by=0 bounded on the whole real line?'
        )
        source.question_type_source = 'human'
        source.question_type_confidence = 1
        source.question_type_human_verified = True
        source.save(update_fields=(
            'display_label', 'prompt_text', 'question_type_source',
            'question_type_confidence', 'question_type_human_verified',
        ))
        update_crop(split_asset, first_question, y0=0, y1=210, original_height=447)

        second_png, second_width, second_height = second_question
        second_digest = hashlib.sha256(second_png).hexdigest()
        second_y0 = second_y1 = None
        if split_asset.source_y0 is not None and split_asset.source_y1 is not None:
            # ``split_asset`` coordinates now describe the first part, so use
            # the original source span reconstructed from its pre-split range.
            original_y0 = 298.0
            original_y1 = 476.6666666666667
            second_y0 = original_y0 + (original_y1 - original_y0) * 210 / 447
            second_y1 = original_y0 + (original_y1 - original_y0) * 395 / 447
        second = Question.objects.create(
            uuid=NEW_UUID,
            subject=source.subject,
            document=source.document,
            topic=source.topic,
            similarity_topic=source.similarity_topic,
            question_order=source.question_order + 1,
            source_label='26 版 660 数二第 607 题',
            display_label='660 #607 · decaying ODE solution',
            prompt_text=(
                'The equation y\'\'+qy=0 has a nonzero solution tending to zero '
                'as x approaches +∞. Choose the correct condition on q.'
            ),
            content_mode='image',
            fingerprint=hashlib.sha256(f'split:{SPLIT_UUID}:660-607'.encode()).hexdigest(),
            confidence=1,
            source_category='workbook',
            record_kind='question',
            is_practiceable=True,
            classification_reason='split from a historically joined question crop',
            classification_confidence=1,
            topic_classification_source='human-repair',
            topic_classification_confidence=1,
            question_type='single_choice',
            question_type_source='human',
            question_type_confidence=1,
            question_type_human_verified=True,
            exam_variant='数二',
        )
        QuestionAsset.objects.create(
            source_id=next_source_id(second_digest),
            question=second,
            position=0,
            asset_type='question_crop',
            sha256=second_digest,
            mime_type='image/png',
            image_data=second_png,
            width=second_width,
            height=second_height,
            source_page_index=split_asset.source_page_index,
            source_x0=split_asset.source_x0,
            source_y0=second_y0,
            source_x1=split_asset.source_x1,
            source_y1=second_y1,
            render_dpi=split_asset.render_dpi,
        )
        update_crop(assets[15821], first_answer, y0=0, y1=700, original_height=1009)
        assets[15822].question = second
        assets[15822].position = 0
        assets[15822].save(update_fields=('question', 'position'))
        update_crop(assets[15822], second_answer, y0=0, y1=740, original_height=2105)
        for context_id in (15823, 20571):
            assets[context_id].asset_type = 'source_context'
            assets[context_id].save(update_fields=('asset_type',))
        changed.update((source, second))

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-three quality repairs to {len(changed)} questions.',
        ))
