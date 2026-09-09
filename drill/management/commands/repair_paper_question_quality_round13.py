import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.repair_paper_question_quality_round8 import render_part, replace_asset
from drill.models import Question, QuestionRevision


TAYLOR_UUID = uuid.UUID('2906fc84-b538-5c62-8754-272d1b56ca41')
CENTROID_UUID = uuid.UUID('06f940f1-821c-5275-9e02-060288129425')
MATRIX_UUID = uuid.UUID('60de8cf2-3373-5394-80e4-9077b9c44ac1')
INTEGRAL_ORDER_UUID = uuid.UUID('fd882ed1-147b-57b5-9080-4b8d0488e98a')
ODE_UUID = uuid.UUID('abdbf442-3e2c-51cf-bd2d-4f7a737f6682')


class Command(BaseCommand):
    help = 'Apply the thirteenth visually verified paper-candidate repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {TAYLOR_UUID, CENTROID_UUID, MATRIX_UUID, INTEGRAL_ORDER_UUID, ODE_UUID}
        questions = {
            question.uuid: question
            for question in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        assets = {
            asset.pk: asset
            for question in questions.values()
            for asset in question.assets.select_for_update()
        }
        already_applied = (
            questions[TAYLOR_UUID].question_type == 'fill_blank'
            and questions[CENTROID_UUID].question_type == 'fill_blank'
            and assets[1751].asset_type == 'source_context'
            and assets[2989].asset_type == 'source_context'
            and assets[3590].height == 125
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-thirteen paper quality repairs are already applied.'))
            return

        expected_types = {TAYLOR_UUID: 'solution', CENTROID_UUID: 'single_choice'}
        for key, expected_type in expected_types.items():
            if questions[key].question_type != expected_type:
                raise CommandError(
                    f'Expected {key} to be {expected_type}; found {questions[key].question_type}.',
                )
        requirements = {
            13943: (281, 'answer_crop'), 14702: (200, 'answer_crop'),
            1751: (227, 'question_crop'), 1752: (316, 'question_crop'),
            2989: (125, 'question_crop'), 3590: (184, 'question_crop'),
        }
        for asset_id, (height, asset_type) in requirements.items():
            asset = assets.get(asset_id)
            if asset is None or asset.height != height or asset.asset_type != asset_type:
                raise CommandError(
                    f'Expected untouched {asset_type} asset {asset_id} at {height}px; '
                    f'found {getattr(asset, "asset_type", None)} '
                    f'{getattr(asset, "height", None)}px.',
                )
        ode_crop = render_part(assets[3590], 0, 125)
        self.stdout.write(
            'Validated two fill-blank type repairs, three blank-footer removals, '
            'and one topic-heading crop.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for key, display_label in {
            TAYLOR_UUID: 'Taylor expansion · determine coefficients',
            CENTROID_UUID: 'Variable-density wire · centroid',
        }.items():
            question = questions[key]
            question.question_type = 'fill_blank'
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

        for position, asset_id in enumerate((13943, 14702), 90):
            asset = assets[asset_id]
            asset.asset_type = 'source_context'
            asset.position = position
            asset.save(update_fields=('asset_type', 'position'))

        matrix = questions[MATRIX_UUID]
        assets[1751].asset_type = 'source_context'
        assets[1751].position = 90
        assets[1751].save(update_fields=('asset_type', 'position'))
        assets[1752].position = 0
        assets[1752].save(update_fields=('position',))
        matrix.display_label = 'Matrix rank · structured 4×4 matrix'
        matrix.prompt_text = 'Find the rank of the displayed 4×4 matrix.'
        matrix.latex_text = ''
        matrix.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(matrix)

        integral_order = questions[INTEGRAL_ORDER_UUID]
        assets[2989].asset_type = 'source_context'
        assets[2989].position = 90
        assets[2989].save(update_fields=('asset_type', 'position'))
        integral_order.display_label = 'Double integral · reverse integration order'
        integral_order.prompt_text = 'Reverse the order of integration in the displayed expression.'
        integral_order.latex_text = ''
        integral_order.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(integral_order)

        ode = questions[ODE_UUID]
        replace_asset(assets[3590], ode_crop)
        ode.display_label = 'First-order ODE · separable trigonometric form'
        ode.prompt_text = "Find the general solution of y' = 1/((1−x) sin y)."
        ode.latex_text = ''
        ode.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(ode)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-thirteen repairs to {len(changed)} questions.',
        ))
