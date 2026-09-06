import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset, QuestionRevision


SOURCE_UUID = uuid.UUID('012a0ed8-6ce3-51d0-8033-8a6bbabcb85d')
PARTS = (
    {
        'y0': 0,
        'y1': 130,
        'uuid': SOURCE_UUID,
        'label': 'Derivative definition · initial value',
        'prompt': (
            'A continuous function y=y(x) satisfies '
            'Δy(1+Δy)=yΔx/(x²+x+1)+o(Δx), with y(0)=π. Find y(1).'
        ),
        'question_type': 'fill_blank',
        'source_category': 'workbook',
    },
    {
        'y0': 130,
        'y1': 318,
        'uuid': uuid.uuid5(uuid.NAMESPACE_URL, f'time-tracker:split:{SOURCE_UUID}:660-76'),
        'label': '660 #76 · increment equation',
        'prompt': (
            'For differentiable y on [0,+∞), the increment satisfies '
            'Δy(1+Δy)=yΔx/(1+x)+α, where α~Δx as Δx→0, and y(0)=1. '
            'Find y(x).'
        ),
        'question_type': 'fill_blank',
        'source_category': 'workbook',
    },
    {
        'y0': 318,
        'y1': 481,
        'uuid': uuid.uuid5(uuid.NAMESPACE_URL, f'time-tracker:split:{SOURCE_UUID}:moscow-1975'),
        'label': 'Moscow 1975 · functional equation',
        'prompt': (
            'Given f(x+y)=(f(x)+f(y))/(1-f(x)f(y)) and f\'(0)=1, find f(x).'
        ),
        'question_type': 'solution',
        'source_category': 'competition',
    },
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


def source_bounds(asset, y0, y1):
    if asset.source_y0 is None or asset.source_y1 is None:
        return None, None
    span = asset.source_y1 - asset.source_y0
    return (
        asset.source_y0 + span * y0 / asset.height,
        asset.source_y0 + span * y1 / asset.height,
    )


class Command(BaseCommand):
    help = 'Split the three derivative-definition questions historically joined as one record.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        created = [part['uuid'] for part in PARTS[1:]]
        if all(Question.objects.filter(uuid=value).exists() for value in created):
            self.stdout.write(self.style.SUCCESS('Derivative-definition split is already applied.'))
            return
        if any(Question.objects.filter(uuid=value).exists() for value in created):
            raise CommandError('Split is only partially applied; refusing an ambiguous repair.')
        try:
            question = Question.objects.select_for_update().get(uuid=SOURCE_UUID)
        except Question.DoesNotExist as exc:
            raise CommandError(f'Missing source question {SOURCE_UUID}.') from exc
        crops = list(question.assets.select_for_update().filter(
            asset_type='question_crop',
        ).order_by('position', 'pk'))
        if len(crops) != 1 or crops[0].height != 481:
            raise CommandError(
                f'Expected one untouched 481px question crop; found '
                f'{[(asset.pk, asset.height) for asset in crops]}.'
            )
        source_asset = crops[0]
        rendered = [
            crop_png(
                bytes(source_asset.image_data), width=source_asset.width,
                y0=part['y0'], y1=part['y1'],
            )
            for part in PARTS
        ]
        answers = list(question.assets.select_for_update().filter(
            asset_type='answer_crop',
        ).order_by('position', 'pk'))
        if len(answers) != 2 or answers[0].height != 1243:
            raise CommandError(
                f'Expected the two original answer crops; found '
                f'{[(asset.pk, asset.height) for asset in answers]}.'
            )
        clean_answer = crop_png(
            bytes(answers[0].image_data), width=answers[0].width, y0=0, y1=675,
        )
        self.stdout.write(
            'Validated split into crop heights '
            f'{[height for _, _, height in rendered]} and a {clean_answer[2]}px answer.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repair.')
            transaction.set_rollback(True)
            return

        shift = len(PARTS) - 1
        for later in Question.objects.select_for_update().filter(
            document=question.document,
            question_order__gt=question.question_order,
        ).order_by('-question_order'):
            later.question_order += shift
            later.save(update_fields=('question_order',))

        targets = []
        for index, (part, rendered_crop) in enumerate(zip(PARTS, rendered)):
            png, width, height = rendered_crop
            digest = hashlib.sha256(png).hexdigest()
            crop_y0, crop_y1 = source_bounds(source_asset, part['y0'], part['y1'])
            if index == 0:
                target = question
                target.display_label = part['label']
                target.prompt_text = part['prompt']
                target.content_mode = 'image'
                target.source_category = part['source_category']
                target.question_type = part['question_type']
                target.question_type_source = 'human'
                target.question_type_confidence = 1
                target.question_type_human_verified = True
                target.confidence = 1
                target.save(update_fields=(
                    'display_label', 'prompt_text', 'content_mode', 'source_category',
                    'question_type', 'question_type_source', 'question_type_confidence',
                    'question_type_human_verified', 'confidence',
                ))
                source_asset.image_data = png
                source_asset.width = width
                source_asset.height = height
                source_asset.sha256 = digest
                source_asset.source_y0 = crop_y0
                source_asset.source_y1 = crop_y1
                source_asset.save(update_fields=(
                    'image_data', 'width', 'height', 'sha256', 'source_y0', 'source_y1',
                ))
            else:
                target = Question.objects.create(
                    uuid=part['uuid'],
                    subject=question.subject,
                    document=question.document,
                    topic=question.topic,
                    similarity_topic=question.similarity_topic,
                    question_order=question.question_order + index,
                    source_label=part['label'],
                    display_label=part['label'],
                    prompt_text=part['prompt'],
                    content_mode='image',
                    fingerprint=hashlib.sha256(
                        f'split:{SOURCE_UUID}:{index}'.encode(),
                    ).hexdigest(),
                    confidence=1,
                    is_past_exam=False,
                    source_category=part['source_category'],
                    record_kind='question',
                    is_practiceable=True,
                    classification_reason='split from a historically joined question crop',
                    classification_confidence=1,
                    topic_classification_source='human-repair',
                    topic_classification_confidence=1,
                    question_type=part['question_type'],
                    question_type_source='human',
                    question_type_confidence=1,
                    question_type_human_verified=True,
                )
                QuestionAsset.objects.create(
                    source_id=next_source_id(digest),
                    question=target,
                    position=0,
                    asset_type='question_crop',
                    sha256=digest,
                    mime_type='image/png',
                    image_data=png,
                    width=width,
                    height=height,
                    source_page_index=source_asset.source_page_index,
                    source_x0=source_asset.source_x0,
                    source_y0=crop_y0,
                    source_x1=source_asset.source_x1,
                    source_y1=crop_y1,
                    render_dpi=source_asset.render_dpi,
                )
            targets.append(target)

        answer_png, answer_width, answer_height = clean_answer
        answer_digest = hashlib.sha256(answer_png).hexdigest()
        primary_answer, alternate_answer = answers
        primary_answer.question = targets[2]
        primary_answer.position = 0
        primary_answer.image_data = answer_png
        primary_answer.width = answer_width
        primary_answer.height = answer_height
        primary_answer.sha256 = answer_digest
        if primary_answer.source_y0 is not None and primary_answer.source_y1 is not None:
            original_y0 = primary_answer.source_y0
            span = primary_answer.source_y1 - original_y0
            primary_answer.source_y1 = original_y0 + span * 675 / 1243
        primary_answer.save(update_fields=(
            'question', 'position', 'image_data', 'width', 'height', 'sha256', 'source_y1',
        ))
        alternate_answer.question = targets[2]
        alternate_answer.position = 1
        alternate_answer.asset_type = 'source_context'
        alternate_answer.save(update_fields=('question', 'position', 'asset_type'))

        for target in targets:
            QuestionRevision.capture(target)
        self.stdout.write(self.style.SUCCESS(
            f'Split {SOURCE_UUID} into {", ".join(str(target.uuid) for target in targets)}.',
        ))
