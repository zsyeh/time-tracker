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


OPEN_LIMIT_UUID = uuid.UUID('2cd3801b-a0ff-55ee-a25b-db3e42b24d32')
JOINED_CHOICES_UUID = uuid.UUID('8691dc3b-8409-5de2-9b6b-8cb63102ce71')
SECOND_CHOICE_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    f'time-tracker:split:{JOINED_CHOICES_UUID}:880-chapter-2-choice-22',
)
QUADRATIC_FORM_UUID = uuid.UUID('efe1b965-f516-53a4-aac3-55f953ea32af')
IMPROPER_INTEGRAL_UUID = uuid.UUID('bc56a328-3ad7-5252-87cd-dea7fdd341f0')
EULER_IDENTITY_UUID = uuid.UUID('5a0b16f5-3f6c-5843-97c6-5060e08024a7')


OPEN_LIMIT_ANSWER = r'''From continuity and the given finite limit,
$f(a)^2=a$. Since $f$ is nonnegative and $a>0$, $f(a)=\sqrt a$. Hence

$$
1=\lim_{x\to a}\frac{f(x)-\sqrt a}{x-a}
\frac{f(x)+\sqrt a}{x+a}
=f'(a)\frac{1}{\sqrt a},
$$

so

$$
\boxed{f'(a)=\sqrt a}.
$$'''


class Command(BaseCommand):
    help = 'Apply the ninth visually verified paper-candidate quality repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {
            OPEN_LIMIT_UUID, JOINED_CHOICES_UUID, QUADRATIC_FORM_UUID,
            IMPROPER_INTEGRAL_UUID, EULER_IDENTITY_UUID,
        }
        questions = {
            question.uuid: question
            for question in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')

        second_choice = Question.objects.filter(uuid=SECOND_CHOICE_UUID).first()
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            second_choice is not None
            and questions[OPEN_LIMIT_UUID].question_type == 'solution'
            and assets[5248].height == 350
            and assets[2594].height == 195
            and assets[1479].height == 225
            and questions[EULER_IDENTITY_UUID].question_type == 'fill_blank'
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-nine paper quality repairs are already applied.'))
            return
        if second_choice is not None:
            raise CommandError('Joined choice split is only partially applied.')

        requirements = {
            460: (228, 'question_crop'),
            16977: (694, 'answer_crop'), 16978: (2105, 'answer_crop'),
            16979: (1139, 'answer_crop'), 19435: (1061, 'answer_crop'),
            5248: (568, 'question_crop'), 5249: (182, 'question_crop'),
            16569: (1282, 'answer_crop'), 16570: (2105, 'answer_crop'),
            16571: (1253, 'answer_crop'),
            2594: (269, 'question_crop'),
            1479: (354, 'question_crop'),
            23427: (130, 'question_crop'),
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
            'first_choice': render_part(assets[5248], 0, 350),
            'second_choice': render_part(assets[5248], 375, 568),
            'quadratic_form': render_part(assets[2594], 0, 195),
            'improper_integral': render_part(assets[1479], 0, 225),
        }

        self.stdout.write(
            'Validated one open-response type repair, one two-question split, '
            'two contaminated crop trims, and one fill-blank type repair.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()

        open_limit = questions[OPEN_LIMIT_UUID]
        open_limit.question_type = 'solution'
        open_limit.question_type_source = 'human'
        open_limit.question_type_confidence = 1
        open_limit.question_type_human_verified = True
        open_limit.display_label = 'Limit definition · derivative at a'
        open_limit.prompt_text = (
            'Let f be nonnegative and continuous. If '
            'lim_(x→a) (f(x)²−a)/(x²−a²)=1 for a>0, find f\'(a).'
        )
        open_limit.latex_text = ''
        open_limit.answer_markdown = OPEN_LIMIT_ANSWER
        open_limit.answer_source = 'human-repair'
        open_limit.answer_confidence = 1
        open_limit.answer_generated_at = timezone.now()
        open_limit.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'display_label', 'prompt_text',
            'latex_text', 'answer_markdown', 'answer_source', 'answer_confidence',
            'answer_generated_at',
        ))
        for position, asset_id in enumerate((16977, 16978, 16979), 90):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = position
            asset.save(update_fields=('asset_type', 'position'))
        assets[19435].position = 0
        assets[19435].save(update_fields=('position',))
        changed.add(open_limit)

        joined = questions[JOINED_CHOICES_UUID]
        shift_after(joined, 1)
        replace_asset(assets[5248], rendered['first_choice'])
        joined.display_label = '2022 · Mathematics II · Question 3'
        joined.source_label = '2022 · Mathematics II · Question 3'
        joined.prompt_text = 'Select the true statement when f has a second derivative at x₀.'
        joined.latex_text = ''
        joined.content_mode = 'image'
        joined.is_past_exam = True
        joined.source_category = 'past_exam'
        joined.exam_year = 2022
        joined.exam_variant = '数二'
        joined.answer_markdown = '$$\\boxed{B}$$'
        joined.answer_source = 'human-repair'
        joined.answer_confidence = 1
        joined.answer_generated_at = timezone.now()
        joined.question_type = 'single_choice'
        joined.question_type_source = 'human'
        joined.question_type_confidence = 1
        joined.question_type_human_verified = True
        joined.save(update_fields=(
            'display_label', 'source_label', 'prompt_text', 'latex_text',
            'content_mode', 'is_past_exam', 'source_category', 'exam_year',
            'exam_variant', 'answer_markdown', 'answer_source', 'answer_confidence',
            'answer_generated_at', 'question_type', 'question_type_source',
            'question_type_confidence', 'question_type_human_verified',
        ))
        assets[16569].asset_type = 'source_context'
        assets[16569].position = 90
        assets[16569].save(update_fields=('asset_type', 'position'))
        assets[16570].position = 0
        assets[16570].save(update_fields=('position',))

        second_choice = split_question(
            joined,
            target_uuid=SECOND_CHOICE_UUID,
            order=joined.question_order + 1,
            label='880 · Chapter 2 · Comprehensive choice 22',
            prompt=(
                'Given equal one-sided limits of f\'(x) at x₀, both equal to 1, '
                'select the conclusion that must hold.'
            ),
            question_type='single_choice',
            answer_markdown='$$\\boxed{D}$$',
        )
        create_asset(
            second_choice, rendered['second_choice'], assets[5248],
            asset_type='question_crop', position=0,
        )
        assets[5249].question = second_choice
        assets[5249].position = 1
        assets[5249].save(update_fields=('question', 'position'))
        assets[16571].question = second_choice
        assets[16571].position = 0
        assets[16571].save(update_fields=('question', 'position'))
        changed.update((joined, second_choice))

        quadratic = questions[QUADRATIC_FORM_UUID]
        replace_asset(assets[2594], rendered['quadratic_form'])
        quadratic.display_label = 'Quadratic form · orthogonal transformation'
        quadratic.prompt_text = quadratic.prompt_text.rsplit('c)可逆+正交', 1)[0].strip()
        quadratic.latex_text = ''
        quadratic.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(quadratic)

        improper = questions[IMPROPER_INTEGRAL_UUID]
        replace_asset(assets[1479], rendered['improper_integral'])
        improper.display_label = 'Improper integral sequence · minimum'
        improper.prompt_text = (
            'For n=2,3,…, let a_n=∫₀^∞ x n^(−x/n) dx. Find the minimum of {a_n}.'
        )
        improper.latex_text = ''
        improper.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(improper)

        euler = questions[EULER_IDENTITY_UUID]
        euler.display_label = 'Homogeneous function · Euler identity'
        euler.question_type = 'fill_blank'
        euler.question_type_source = 'human'
        euler.question_type_confidence = 1
        euler.question_type_human_verified = True
        euler.save(update_fields=(
            'display_label', 'question_type', 'question_type_source',
            'question_type_confidence', 'question_type_human_verified',
        ))
        changed.add(euler)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-nine quality repairs to {len(changed)} question records.',
        ))
