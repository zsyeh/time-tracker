import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from drill.models import Question, QuestionAsset, QuestionRevision


LINEAR_ALGEBRA_UUID = uuid.UUID('cd101fe4-c495-5fcc-96ca-ceb6cb296f7d')
REVERSED_MATRIX_UUID = uuid.UUID('0532c67e-9f29-5fda-ac01-474c32b0cc4e')
SOLUTION_ONLY_UUID = uuid.UUID('d94a3590-e2a4-50b1-8741-39585b019331')
OVERSIZED_MULTIVARIABLE_UUID = uuid.UUID('b8a6fc98-aa12-5aa4-8d43-f3a7252d5dfd')
CHOICE_UUIDS = (
    uuid.UUID('e63044cb-68b9-5a42-a574-9751fb164892'),
    uuid.UUID('ff38ab58-fe6e-544c-9516-7bebe20e67b5'),
)
JOINED_LIMIT_UUID = uuid.UUID('9c891375-486d-5056-9bf1-2efefe6a6de7')
SECOND_LIMIT_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_LIMIT_UUID}:880-basic-fill-1',
)
JOINED_IMPLICIT_UUID = uuid.UUID('7f5888ee-4c7f-5f9b-88b1-7c8e548b3dd9')
IMPLICIT_13_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_IMPLICIT_UUID}:900-a-13',
)
IMPLICIT_234_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_IMPLICIT_UUID}:660-234',
)
IMPLICIT_2025_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_IMPLICIT_UUID}:2025-math3',
)


def crop_png(raw, *, width, y0=0, y1):
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


def source_bounds(asset, y0, y1):
    if asset.source_y0 is None or asset.source_y1 is None:
        return None, None
    span = asset.source_y1 - asset.source_y0
    return (
        asset.source_y0 + span * y0 / asset.height,
        asset.source_y0 + span * y1 / asset.height,
    )


def render_part(asset, y0, y1):
    png, width, height = crop_png(
        bytes(asset.image_data), width=asset.width, y0=y0, y1=y1,
    )
    return {
        'png': png,
        'width': width,
        'height': height,
        'sha256': hashlib.sha256(png).hexdigest(),
        'source_y0': source_bounds(asset, y0, y1)[0],
        'source_y1': source_bounds(asset, y0, y1)[1],
    }


def replace_asset(asset, rendered):
    asset.image_data = rendered['png']
    asset.width = rendered['width']
    asset.height = rendered['height']
    asset.sha256 = rendered['sha256']
    fields = ['image_data', 'width', 'height', 'sha256']
    if rendered['source_y0'] is not None:
        asset.source_y0 = rendered['source_y0']
        asset.source_y1 = rendered['source_y1']
        fields.extend(('source_y0', 'source_y1'))
    asset.save(update_fields=fields)


def next_source_id(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


def create_asset(question, rendered, source, *, asset_type, position=0):
    return QuestionAsset.objects.create(
        source_id=next_source_id(rendered['sha256']),
        question=question,
        position=position,
        asset_type=asset_type,
        sha256=rendered['sha256'],
        mime_type='image/png',
        image_data=rendered['png'],
        width=rendered['width'],
        height=rendered['height'],
        source_page_index=source.source_page_index,
        source_x0=source.source_x0,
        source_y0=rendered['source_y0'],
        source_x1=source.source_x1,
        source_y1=rendered['source_y1'],
        render_dpi=source.render_dpi,
    )


def shift_after(question, count):
    for later in Question.objects.select_for_update().filter(
        document=question.document, question_order__gt=question.question_order,
    ).order_by('-question_order'):
        later.question_order += count
        later.save(update_fields=('question_order',))


def split_question(source, *, target_uuid, order, label, prompt, question_type,
                   source_category='workbook', exam_year=None, exam_variant='',
                   answer_markdown=''):
    now = timezone.now() if answer_markdown else None
    return Question.objects.create(
        uuid=target_uuid,
        subject=source.subject,
        document=source.document,
        topic=source.topic,
        similarity_topic=source.similarity_topic,
        question_order=order,
        source_label=label,
        display_label=label,
        prompt_text=prompt,
        content_mode='image',
        fingerprint=hashlib.sha256(f'split:{target_uuid}'.encode()).hexdigest(),
        confidence=1,
        is_past_exam=source_category == 'past_exam',
        source_category=source_category,
        record_kind='question',
        is_practiceable=True,
        classification_reason='visually split from a joined source crop',
        classification_confidence=1,
        exam_year=exam_year,
        exam_variant=exam_variant,
        answer_markdown=answer_markdown,
        answer_source='agent' if answer_markdown else '',
        answer_confidence=1 if answer_markdown else None,
        answer_generated_at=now,
        topic_classification_source='human-repair',
        topic_classification_confidence=1,
        question_type=question_type,
        question_type_source='human',
        question_type_confidence=1,
        question_type_human_verified=True,
    )


class Command(BaseCommand):
    help = 'Apply the eighth visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {
            LINEAR_ALGEBRA_UUID, REVERSED_MATRIX_UUID, SOLUTION_ONLY_UUID,
            OVERSIZED_MULTIVARIABLE_UUID, JOINED_LIMIT_UUID, JOINED_IMPLICIT_UUID,
            *CHOICE_UUIDS,
        }
        questions = {
            question.uuid: question
            for question in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        created_uuids = (SECOND_LIMIT_UUID, IMPLICIT_13_UUID, IMPLICIT_234_UUID, IMPLICIT_2025_UUID)
        created = list(Question.objects.filter(uuid__in=created_uuids))
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            len(created) == len(created_uuids)
            and assets[17193].height == 310
            and assets[21592].asset_type == 'question_crop'
            and assets[21591].asset_type == 'answer_crop'
            and not questions[SOLUTION_ONLY_UUID].is_practiceable
            and assets[3380].height == 150
            and assets[3381].asset_type == 'source_context'
            and all(questions[value].question_type == 'single_choice' for value in CHOICE_UUIDS)
            and assets[3109].height == 175
            and assets[3285].height == 95
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-eight paper quality repairs are already applied.'))
            return
        if created:
            raise CommandError('One or more split groups are only partially applied.')

        requirements = {
            17193: (640, 'answer_crop'),
            21591: (115, 'question_crop'), 21592: (65, 'answer_crop'),
            23408: (899, 'question_crop'), 23409: (528, 'answer_crop'),
            3380: (1750, 'question_crop'), 3381: (232, 'question_crop'),
            3109: (341, 'question_crop'), 15115: (773, 'answer_crop'),
            15116: (1528, 'answer_crop'), 3285: (708, 'question_crop'),
            3286: (320, 'question_crop'), 19229: (782, 'answer_crop'),
            19230: (1123, 'answer_crop'), 19231: (202, 'answer_crop'),
        }
        for asset_id, (height, asset_type) in requirements.items():
            asset = assets.get(asset_id)
            if asset is None or asset.height != height or asset.asset_type != asset_type:
                raise CommandError(
                    f'Expected untouched {asset_type} asset {asset_id} at {height}px; '
                    f'found {getattr(asset, "asset_type", None)} '
                    f'{getattr(asset, "height", None)}px.',
                )

        rendered = {
            'linear_answer': render_part(assets[17193], 330, 640),
            'oversized_question': render_part(assets[3380], 0, 150),
            'limit_q1': render_part(assets[3109], 0, 175),
            'limit_q2': render_part(assets[3109], 175, 341),
            'limit_a1': render_part(assets[15116], 120, 570),
            'limit_a2': render_part(assets[15116], 1120, 1528),
            'implicit_q18': render_part(assets[3285], 0, 95),
            'implicit_q13': render_part(assets[3285], 95, 285),
            'implicit_q234': render_part(assets[3285], 285, 575),
            'implicit_q2025': render_part(assets[3286], 65, 250),
            'implicit_a2025': render_part(assets[19229], 170, 782),
        }

        self.stdout.write(
            'Validated two joined groups (six resulting questions), one reversed pair, '
            'one solution-only quarantine, two type repairs, and two crop cleanups.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        replace_asset(assets[17193], rendered['linear_answer'])
        changed.add(questions[LINEAR_ALGEBRA_UUID])

        reversed_matrix = questions[REVERSED_MATRIX_UUID]
        assets[21591].asset_type = 'answer_crop'
        assets[21591].position = 0
        assets[21591].save(update_fields=('asset_type', 'position'))
        assets[21592].asset_type = 'question_crop'
        assets[21592].position = 0
        assets[21592].save(update_fields=('asset_type', 'position'))
        reversed_matrix.question_type = 'fill_blank'
        reversed_matrix.question_type_source = 'human'
        reversed_matrix.question_type_confidence = 1
        reversed_matrix.question_type_human_verified = True
        reversed_matrix.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))
        changed.add(reversed_matrix)

        solution_only = questions[SOLUTION_ONLY_UUID]
        solution_only.record_kind = 'grouped'
        solution_only.is_practiceable = False
        solution_only.classification_reason = 'visually verified solution fragment without a question'
        solution_only.classification_confidence = 1
        solution_only.save(update_fields=(
            'record_kind', 'is_practiceable', 'classification_reason',
            'classification_confidence',
        ))
        for asset in solution_only.assets.all():
            asset.asset_type = 'source_context'
            asset.save(update_fields=('asset_type',))
        changed.add(solution_only)

        oversized = questions[OVERSIZED_MULTIVARIABLE_UUID]
        replace_asset(assets[3380], rendered['oversized_question'])
        assets[3381].asset_type = 'source_context'
        assets[3381].save(update_fields=('asset_type',))
        changed.add(oversized)

        for question_uuid in CHOICE_UUIDS:
            question = questions[question_uuid]
            question.question_type = 'single_choice'
            question.question_type_source = 'human'
            question.question_type_confidence = 1
            question.question_type_human_verified = True
            question.save(update_fields=(
                'question_type', 'question_type_source', 'question_type_confidence',
                'question_type_human_verified',
            ))
            changed.add(question)

        joined_limit = questions[JOINED_LIMIT_UUID]
        shift_after(joined_limit, 1)
        replace_asset(assets[3109], rendered['limit_q1'])
        replace_asset(assets[15116], rendered['limit_a1'])
        assets[15115].asset_type = 'source_context'
        assets[15115].position = 90
        assets[15115].save(update_fields=('asset_type', 'position'))
        joined_limit.display_label = 'Jiang Xiaoqian · multivariable limit'
        joined_limit.source_label = 'Jiang Xiaoqian · analogous problem 150'
        joined_limit.prompt_text = (
            'Evaluate lim_(x,y→0) x²y² sin(x⁴) tan⁵(y) / (x⁶+y⁸).'
        )
        joined_limit.content_mode = 'image'
        joined_limit.answer_markdown = r'$$\boxed{0}$$'
        joined_limit.answer_source = 'agent'
        joined_limit.answer_confidence = 1
        joined_limit.answer_generated_at = timezone.now()
        joined_limit.save(update_fields=(
            'display_label', 'source_label', 'prompt_text', 'content_mode',
            'answer_markdown', 'answer_source', 'answer_confidence', 'answer_generated_at',
        ))
        second_limit = split_question(
            joined_limit,
            target_uuid=SECOND_LIMIT_UUID,
            order=joined_limit.question_order + 1,
            label='880 · Chapter 4 · Basic fill 1',
            prompt='Evaluate lim_(x→3,y→0) ln(x+eʸ)/√(x²+y²).',
            question_type='fill_blank',
            answer_markdown=r'$$\boxed{\frac{2}{3}\ln 2}$$',
        )
        create_asset(
            second_limit, rendered['limit_q2'], assets[3109], asset_type='question_crop',
        )
        create_asset(
            second_limit, rendered['limit_a2'], assets[15116], asset_type='answer_crop',
        )
        changed.update((joined_limit, second_limit))

        joined_implicit = questions[JOINED_IMPLICIT_UUID]
        joined_implicit.refresh_from_db()
        shift_after(joined_implicit, 3)
        replace_asset(assets[3285], rendered['implicit_q18'])
        for asset_id in (3286, 19229, 19230, 19231):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = 90 + asset_id % 10
            asset.save(update_fields=('asset_type', 'position'))
        joined_implicit.display_label = 'Implicit differentiation · exercise 18'
        joined_implicit.source_label = 'Implicit differentiation · exercise 18'
        joined_implicit.prompt_text = (
            'For 3x+xyz+z³=1 defining z=z(x,y), find z_xx at x=0, y=0.'
        )
        joined_implicit.content_mode = 'image'
        joined_implicit.question_type = 'fill_blank'
        joined_implicit.question_type_source = 'human'
        joined_implicit.question_type_confidence = 1
        joined_implicit.question_type_human_verified = True
        joined_implicit.answer_markdown = r'At $(0,0)$, $z=1$. Implicit differentiation gives $\boxed{z_{xx}=-2}$.'
        joined_implicit.answer_source = 'agent'
        joined_implicit.answer_confidence = 1
        joined_implicit.answer_generated_at = timezone.now()
        joined_implicit.save(update_fields=(
            'display_label', 'source_label', 'prompt_text', 'content_mode',
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'answer_markdown', 'answer_source',
            'answer_confidence', 'answer_generated_at',
        ))
        implicit_13 = split_question(
            joined_implicit,
            target_uuid=IMPLICIT_13_UUID,
            order=joined_implicit.question_order + 1,
            label='900 · Chapter 4 · A13',
            prompt=(
                'The positive implicit branch satisfies '
                'x²+y²+z²−2x−4y−2z=0. Select the true derivative statement at (2,4).'
            ),
            question_type='single_choice',
            answer_markdown='$$\\boxed{C}\qquad z_{xx}=-2.$$ ',
        )
        create_asset(implicit_13, rendered['implicit_q13'], assets[3285], asset_type='question_crop')
        implicit_234 = split_question(
            joined_implicit,
            target_uuid=IMPLICIT_234_UUID,
            order=joined_implicit.question_order + 2,
            label='660 · #234',
            prompt=(
                'For 3xy+2x−4y−z=eᶻ with z(1,1)=0, select z_xy at (1,1).'
            ),
            question_type='single_choice',
            answer_markdown='$$\\boxed{B}\qquad z_{xy}(1,1)=\\frac{17}{8}.$$ ',
        )
        create_asset(implicit_234, rendered['implicit_q234'], assets[3285], asset_type='question_crop')
        implicit_2025 = split_question(
            joined_implicit,
            target_uuid=IMPLICIT_2025_UUID,
            order=joined_implicit.question_order + 3,
            label='2025 · Mathematics III',
            prompt='Find z_xx(1,1) for the implicit function shown.',
            question_type='fill_blank',
            source_category='past_exam',
            exam_year=2025,
            exam_variant='数三',
        )
        create_asset(
            implicit_2025, rendered['implicit_q2025'], assets[3286], asset_type='question_crop',
        )
        create_asset(
            implicit_2025, rendered['implicit_a2025'], assets[19229], asset_type='answer_crop',
        )
        changed.update((joined_implicit, implicit_13, implicit_234, implicit_2025))

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-eight quality repairs to {len(changed)} question records.',
        ))
