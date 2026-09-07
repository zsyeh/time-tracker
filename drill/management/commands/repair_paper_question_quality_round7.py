import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from drill.models import Question, QuestionAsset, QuestionRevision


SECTION_ONLY_UUID = uuid.UUID('9a71044e-8a9a-5379-b2e9-3442297f2ee1')
LINEAR_ALGEBRA_UUID = uuid.UUID('cd101fe4-c495-5fcc-96ca-ceb6cb296f7d')
LIMIT_CHOICE_UUID = uuid.UUID('3ad7198e-dee3-5576-8e6d-e434053da67d')
JOINED_ODE_UUID = uuid.UUID('68b732c4-62dc-501b-94e9-369624f2454f')
SECOND_ODE_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    f'time-tracker:split:{JOINED_ODE_UUID}:660-85',
)
MULTIVARIABLE_UUID = uuid.UUID('8b94d3f0-7561-537e-959a-179d7a01f492')
MULTIVARIABLE_FRAGMENT_UUID = uuid.UUID('de4f57c4-8bf6-5adf-9db6-ffa78f5a68fe')


FIRST_ODE_ANSWER = r'''The characteristic equation is

$$
r^3-1=(r-1)(r^2+r+1)=0.
$$

Therefore the general solution is

$$
\boxed{y=C_1e^x+e^{-x/2}\left(C_2\cos\frac{\sqrt3x}{2}
+C_3\sin\frac{\sqrt3x}{2}\right)}.
$$'''

SECOND_ODE_ANSWER = r'''The characteristic equation is

$$
r^3-r=r(r-1)(r+1)=0,
$$

so $y=C_1+C_2e^x+C_3e^{-x}$. The three initial conditions give
$C_2=0$, $C_3=1$, and $C_1=2$. Hence

$$
\boxed{y=2+e^{-x}}.
$$'''


def crop_png(raw, *, width, y0=0, y1=None):
    document = pymupdf.open(stream=raw, filetype='png')
    try:
        page = document[0]
        scale = width / page.rect.width
        bottom = page.rect.height if y1 is None else y1 / scale
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            clip=pymupdf.Rect(0, y0 / scale, page.rect.width, bottom),
            alpha=False,
        )
        return pixmap.tobytes('png'), pixmap.width, pixmap.height
    finally:
        document.close()


def source_bounds(asset, y0, y1):
    if asset.source_y0 is None or asset.source_y1 is None:
        return None, None
    span = asset.source_y1 - asset.source_y0
    return (
        asset.source_y0 + span * y0 / asset.height,
        asset.source_y0 + span * y1 / asset.height,
    )


def replace_crop(asset, *, y0=0, y1):
    original_height = asset.height
    new_source_y0, new_source_y1 = source_bounds(asset, y0, y1)
    png, width, height = crop_png(
        bytes(asset.image_data), width=asset.width, y0=y0, y1=y1,
    )
    asset.image_data = png
    asset.width = width
    asset.height = height
    asset.sha256 = hashlib.sha256(png).hexdigest()
    fields = ['image_data', 'width', 'height', 'sha256']
    if new_source_y0 is not None:
        asset.source_y0 = new_source_y0
        asset.source_y1 = new_source_y1
        fields.extend(('source_y0', 'source_y1'))
    asset.save(update_fields=fields)
    return original_height


def next_source_id(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


class Command(BaseCommand):
    help = 'Apply the seventh visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {
            SECTION_ONLY_UUID, LINEAR_ALGEBRA_UUID, LIMIT_CHOICE_UUID,
            JOINED_ODE_UUID, MULTIVARIABLE_UUID, MULTIVARIABLE_FRAGMENT_UUID,
        }
        questions = {
            item.uuid: item
            for item in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')

        second_ode = Question.objects.filter(uuid=SECOND_ODE_UUID).first()
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            second_ode is not None
            and assets[1964].height == 425
            and assets[17193].height == 640
            and all(assets[pk].asset_type == 'source_context' for pk in range(19837, 19843))
            and not questions[SECTION_ONLY_UUID].is_practiceable
            and questions[LIMIT_CHOICE_UUID].question_type == 'single_choice'
            and assets[3762].height == 105
            and assets[21131].asset_type == 'source_context'
            and assets[3434].question_id == questions[MULTIVARIABLE_UUID].pk
            and not questions[MULTIVARIABLE_FRAGMENT_UUID].is_practiceable
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-seven paper quality repairs are already applied.'))
            return
        if second_ode is not None:
            raise CommandError('ODE split is only partially applied; refusing an ambiguous repair.')

        required_assets = {
            1144: (300, 'question_crop'), 1145: (207, 'question_crop'),
            14546: (118, 'answer_crop'), 1964: (497, 'question_crop'),
            17193: (718, 'answer_crop'), 22050: (174, 'question_crop'),
            3762: (242, 'question_crop'), 21131: (1288, 'answer_crop'),
            3432: (245, 'question_crop'), 3433: (122, 'question_crop'),
            3434: (69, 'question_crop'), 17465: (967, 'answer_crop'),
        }
        for asset_id, (height, asset_type) in required_assets.items():
            asset = assets.get(asset_id)
            if asset is None or asset.height != height or asset.asset_type != asset_type:
                raise CommandError(
                    f'Expected untouched {asset_type} asset {asset_id} at {height}px; '
                    f'found {getattr(asset, "asset_type", None)} '
                    f'{getattr(asset, "height", None)}px.',
                )
        for asset_id in range(19837, 19843):
            if assets.get(asset_id) is None or assets[asset_id].asset_type != 'answer_crop':
                raise CommandError(f'Expected adjacent-answer contamination asset {asset_id}.')

        joined_asset = assets[3762]
        second_png, second_width, second_height = crop_png(
            bytes(joined_asset.image_data), width=joined_asset.width, y0=105, y1=242,
        )
        second_digest = hashlib.sha256(second_png).hexdigest()
        second_source_y0, second_source_y1 = source_bounds(joined_asset, 105, 242)

        self.stdout.write(
            'Validated one section-only row, two answer-contamination repairs, '
            'one type correction, one ODE split, and one fragmented-question merge.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()

        section = questions[SECTION_ONLY_UUID]
        section.record_kind = 'section'
        section.is_practiceable = False
        section.question_type = 'unknown'
        section.question_type_source = 'human'
        section.question_type_confidence = 1
        section.question_type_human_verified = True
        section.classification_reason = 'visually verified source navigation heading; no question body'
        section.classification_confidence = 1
        section.save(update_fields=(
            'record_kind', 'is_practiceable', 'question_type', 'question_type_source',
            'question_type_confidence', 'question_type_human_verified',
            'classification_reason', 'classification_confidence',
        ))
        for asset in section.assets.all():
            asset.asset_type = 'source_context'
            asset.save(update_fields=('asset_type',))
        changed.add(section)

        linear = questions[LINEAR_ALGEBRA_UUID]
        replace_crop(assets[1964], y1=425)
        replace_crop(assets[17193], y1=640)
        for position, asset_id in enumerate(range(19837, 19843), 1):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = position
            asset.save(update_fields=('asset_type', 'position'))
        changed.add(linear)

        limit_choice = questions[LIMIT_CHOICE_UUID]
        limit_choice.question_type = 'single_choice'
        limit_choice.question_type_source = 'human'
        limit_choice.question_type_confidence = 1
        limit_choice.question_type_human_verified = True
        limit_choice.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        changed.add(limit_choice)

        joined = questions[JOINED_ODE_UUID]
        original_question_order = joined.question_order
        replace_crop(joined_asset, y1=105)
        wrong_answer = assets[21131]
        wrong_answer.asset_type = 'source_context'
        wrong_answer.position = 90
        wrong_answer.save(update_fields=('asset_type', 'position'))
        joined.display_label = '2021 · Math II'
        joined.source_label = '2021 · Math II'
        joined.prompt_text = "Find the general solution of y''' - y = 0."
        joined.latex_text = ''
        joined.content_mode = 'image'
        joined.answer_markdown = FIRST_ODE_ANSWER
        joined.answer_source = 'agent'
        joined.answer_confidence = 1
        joined.answer_generated_at = timezone.now()
        joined.question_type = 'fill_blank'
        joined.question_type_source = 'human'
        joined.question_type_confidence = 1
        joined.question_type_human_verified = True
        joined.save(update_fields=(
            'display_label', 'source_label', 'prompt_text', 'latex_text', 'content_mode',
            'answer_markdown', 'answer_source', 'answer_confidence', 'answer_generated_at',
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        for later in Question.objects.select_for_update().filter(
            document=joined.document, question_order__gt=original_question_order,
        ).order_by('-question_order'):
            later.question_order += 1
            later.save(update_fields=('question_order',))
        second_ode = Question.objects.create(
            uuid=SECOND_ODE_UUID,
            subject=joined.subject,
            document=joined.document,
            topic=joined.topic,
            similarity_topic=joined.similarity_topic,
            question_order=original_question_order + 1,
            source_label='660 #85 · third-order IVP',
            display_label='660 #85 · third-order IVP',
            prompt_text=(
                "Find the solution of y''' - y' = 0 satisfying "
                "y(0)=3, y'(0)=-1, and y''(0)=1."
            ),
            content_mode='image',
            fingerprint=hashlib.sha256(
                f'split:{JOINED_ODE_UUID}:660-85'.encode(),
            ).hexdigest(),
            confidence=1,
            is_past_exam=False,
            source_category='workbook',
            record_kind='question',
            is_practiceable=True,
            classification_reason='visually split from a joined ODE crop',
            classification_confidence=1,
            answer_markdown=SECOND_ODE_ANSWER,
            answer_source='agent',
            answer_confidence=1,
            answer_generated_at=timezone.now(),
            topic_classification_source='human-repair',
            topic_classification_confidence=1,
            question_type='fill_blank',
            question_type_source='human',
            question_type_confidence=1,
            question_type_human_verified=True,
        )
        QuestionAsset.objects.create(
            source_id=next_source_id(second_digest),
            question=second_ode,
            position=0,
            asset_type='question_crop',
            sha256=second_digest,
            mime_type='image/png',
            image_data=second_png,
            width=second_width,
            height=second_height,
            source_page_index=joined_asset.source_page_index,
            source_x0=joined_asset.source_x0,
            source_y0=second_source_y0,
            source_x1=joined_asset.source_x1,
            source_y1=second_source_y1,
            render_dpi=joined_asset.render_dpi,
        )
        changed.update((joined, second_ode))

        multivariable = questions[MULTIVARIABLE_UUID]
        fragment = questions[MULTIVARIABLE_FRAGMENT_UUID]
        clean_question = assets[3434]
        clean_question.question = multivariable
        clean_question.position = 0
        clean_question.save(update_fields=('question', 'position'))
        for position, asset_id in enumerate((3432, 3433), 90):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = position
            asset.save(update_fields=('asset_type', 'position'))
        replace_crop(assets[17465], y0=245, y1=967)
        multivariable.prompt_text = fragment.prompt_text
        multivariable.latex_text = fragment.latex_text
        multivariable.display_label = '1000 · Chapter 13 · Basic 22'
        multivariable.content_mode = 'image'
        multivariable.question_type = 'solution'
        multivariable.question_type_source = 'human'
        multivariable.question_type_confidence = 1
        multivariable.question_type_human_verified = True
        multivariable.classification_reason = 'merged with its separately imported question crop'
        multivariable.classification_confidence = 1
        multivariable.save(update_fields=(
            'prompt_text', 'latex_text', 'display_label', 'content_mode',
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'classification_reason',
            'classification_confidence',
        ))
        fragment.record_kind = 'grouped'
        fragment.is_practiceable = False
        fragment.classification_reason = f'merged into question {multivariable.pk}'
        fragment.classification_confidence = 1
        fragment.save(update_fields=(
            'record_kind', 'is_practiceable', 'classification_reason',
            'classification_confidence',
        ))
        changed.update((multivariable, fragment))

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-seven quality repairs to {len(changed)} question records.',
        ))
