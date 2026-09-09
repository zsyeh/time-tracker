import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from drill.management.commands.repair_paper_question_quality_round8 import (
    create_asset,
    render_part,
    replace_asset,
    shift_after,
    split_question,
)
from drill.models import Question, QuestionRevision


LIMIT_UUID = uuid.UUID('534bc009-af7f-5d57-ae42-b9bafcf02560')
VECTOR_UUID = uuid.UUID('34102bce-befd-5f1d-b250-ac8af9bf711d')
RATE_UUID = uuid.UUID('2cf3b5a8-e9f2-547a-8109-e4ae8adfbfbe')
EXTREMA_UUID = uuid.UUID('b0735ad0-2733-5873-9b6c-b1a4d6506cc1')
JOINED_ODE_UUID = uuid.UUID('e3f7b091-51a0-5eb5-b12f-7bfed1c613d2')
INTEGRAL_UUID = uuid.UUID('95807ca3-31f0-5e83-82f0-0b15ac911326')
IMPLICIT_UUID = uuid.UUID('ee54098d-a60b-5726-9167-d8f5f7bc1fa1')

ODE_GENERAL_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_ODE_UUID}:x2-general-solution',
)
ODE_INITIAL_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL, f'time-tracker:split:{JOINED_ODE_UUID}:initial-value-fill',
)

FIRST_ODE_ANSWER = r'''Treat $x$ as a function of $y$. The equation becomes

$$
\frac{dx}{dy}+\left(\frac{2}{y^3}-\frac{3}{y}\right)x=1.
$$

An integrating factor is $\mu(y)=y^{-3}e^{-1/y^2}$. Therefore

$$
\frac{d}{dy}\left(xy^{-3}e^{-1/y^2}\right)
=y^{-3}e^{-1/y^2},
$$

and the general solution can be written as

$$
\boxed{\frac{2x}{y^3}-1=Ce^{1/y^2}}.
$$'''


class Command(BaseCommand):
    help = 'Apply the twelfth visually verified paper-candidate repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {
            LIMIT_UUID, VECTOR_UUID, RATE_UUID, EXTREMA_UUID,
            JOINED_ODE_UUID, INTEGRAL_UUID, IMPLICIT_UUID,
        }
        questions = {
            question.uuid: question
            for question in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')

        ode_general = Question.objects.filter(uuid=ODE_GENERAL_UUID).first()
        ode_initial = Question.objects.filter(uuid=ODE_INITIAL_UUID).first()
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            ode_general is not None
            and ode_initial is not None
            and questions[LIMIT_UUID].question_type == 'fill_blank'
            and questions[VECTOR_UUID].question_type == 'solution'
            and questions[RATE_UUID].question_type == 'solution'
            and questions[INTEGRAL_UUID].question_type == 'fill_blank'
            and questions[IMPLICIT_UUID].question_type == 'single_choice'
            and assets[429].height == 240
            and assets[3486].height == 185
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-twelve paper quality repairs are already applied.'))
            return
        if ode_general is not None or ode_initial is not None:
            raise CommandError('Joined differential-equation split is only partially applied.')

        expected_types = {
            LIMIT_UUID: 'single_choice', VECTOR_UUID: 'single_choice',
            RATE_UUID: 'single_choice', INTEGRAL_UUID: 'solution',
            IMPLICIT_UUID: 'solution', JOINED_ODE_UUID: 'fill_blank',
        }
        for key, expected_type in expected_types.items():
            if questions[key].question_type != expected_type:
                raise CommandError(
                    f'Expected {key} to be {expected_type}; found {questions[key].question_type}.',
                )
        requirements = {
            429: (617, 'question_crop'), 430: (180, 'question_crop'),
            13669: (733, 'answer_crop'), 13670: (749, 'answer_crop'),
            14643: (239, 'answer_crop'), 3486: (372, 'question_crop'),
            3652: (337, 'question_crop'), 3653: (249, 'question_crop'),
            19256: (666, 'answer_crop'), 19257: (1007, 'answer_crop'),
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
            'limit': render_part(assets[429], 0, 240),
            'extrema': render_part(assets[3486], 0, 185),
            'initial_question': render_part(assets[19257], 0, 205),
            'initial_answer': render_part(assets[19257], 245, 930),
        }
        self.stdout.write(
            'Validated five type repairs, two contamination trims, and a '
            'three-question differential-equation reconstruction.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        type_repairs = {
            LIMIT_UUID: ('fill_blank', 'Limit · logarithmic composite'),
            VECTOR_UUID: ('solution', 'Vector groups · equivalent conditions'),
            RATE_UUID: ('solution', 'Volume of revolution · rate of change'),
            INTEGRAL_UUID: ('fill_blank', 'Indefinite integral · exponential substitution'),
            IMPLICIT_UUID: ('single_choice', 'Implicit differentiation · homogeneous variables'),
        }
        for key, (question_type, display_label) in type_repairs.items():
            question = questions[key]
            question.question_type = question_type
            question.question_type_source = 'human'
            question.question_type_confidence = 1
            question.question_type_human_verified = True
            question.display_label = display_label
            question.latex_text = ''
            question.save(update_fields=(
                'question_type', 'question_type_source', 'question_type_confidence',
                'question_type_human_verified', 'display_label', 'latex_text',
            ))
            changed.add(question)

        limit_question = questions[LIMIT_UUID]
        replace_asset(assets[429], rendered['limit'])
        for position, asset_id in enumerate((430, 13669), 90):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = position
            asset.save(update_fields=('asset_type', 'position'))
        assets[13670].position = 0
        assets[13670].save(update_fields=('position',))
        limit_question.prompt_text = (
            'Given the displayed finite limit I=3, find lim_(x→0) f(x)/x².'
        )
        limit_question.save(update_fields=('prompt_text',))

        assets[14643].asset_type = 'source_context'
        assets[14643].position = 90
        assets[14643].save(update_fields=('asset_type', 'position'))

        extrema = questions[EXTREMA_UUID]
        replace_asset(assets[3486], rendered['extrema'])
        extrema.prompt_text = extrema.prompt_text.split('3.条件极值', 1)[0].strip()
        extrema.display_label = 'Quadratic form · strict extremum condition'
        extrema.latex_text = ''
        extrema.save(update_fields=('prompt_text', 'display_label', 'latex_text'))
        changed.add(extrema)

        joined = questions[JOINED_ODE_UUID]
        shift_after(joined, 2)
        joined.display_label = 'Differential equation · linear equation in x(y)'
        joined.source_label = joined.display_label
        joined.prompt_text = (
            'Find the general solution of '
            '(2x−3xy²−y³)y\' + y³ = 0.'
        )
        joined.question_type = 'solution'
        joined.question_type_source = 'human'
        joined.question_type_confidence = 1
        joined.question_type_human_verified = True
        joined.answer_markdown = FIRST_ODE_ANSWER
        joined.answer_source = 'human-repair'
        joined.answer_confidence = 1
        joined.answer_generated_at = timezone.now()
        joined.latex_text = ''
        joined.save(update_fields=(
            'display_label', 'source_label', 'prompt_text', 'question_type',
            'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'answer_markdown', 'answer_source',
            'answer_confidence', 'answer_generated_at', 'latex_text',
        ))

        ode_general = split_question(
            joined,
            target_uuid=ODE_GENERAL_UUID,
            order=joined.question_order + 1,
            label='Differential equation · solve for x²(y)',
            prompt=(
                'Treat x² as a function of y and solve '
                '(y⁴−3x²)dy + xy dx = 0.'
            ),
            question_type='fill_blank',
            answer_markdown='$$\\boxed{x^2=Cy^6+y^4}$$',
        )
        assets[3653].question = ode_general
        assets[3653].position = 0
        assets[3653].save(update_fields=('question', 'position'))
        assets[19256].question = ode_general
        assets[19256].position = 0
        assets[19256].save(update_fields=('question', 'position'))

        ode_initial = split_question(
            joined,
            target_uuid=ODE_INITIAL_UUID,
            order=joined.question_order + 2,
            label='Differential equation · initial value',
            prompt=(
                'Solve dy/dx = y/(x+y²), subject to y(2)=1, and fill in x as a function of y.'
            ),
            question_type='fill_blank',
            answer_markdown='$$\\boxed{x=y^2+y}$$',
        )
        create_asset(
            ode_initial, rendered['initial_question'], assets[19257],
            asset_type='question_crop', position=0,
        )
        assets[19257].question = ode_initial
        assets[19257].position = 0
        replace_asset(assets[19257], rendered['initial_answer'])
        assets[19257].save(update_fields=('question', 'position'))
        changed.update((joined, ode_general, ode_initial))

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-twelve repairs to {len(changed)} questions.',
        ))
