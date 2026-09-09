import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.repair_paper_question_quality_round8 import render_part, replace_asset
from drill.models import Question, QuestionRevision


INTEGRAL_ORDER_UUID = uuid.UUID('fd882ed1-147b-57b5-9080-4b8d0488e98a')
MONOTONICITY_UUID = uuid.UUID('c0305f5e-b758-5baa-98ba-af52494f8e41')
DETERMINANT_UUID = uuid.UUID('df585428-0aa0-5dce-9d89-732f8ebe2f57')
QUADRATIC_UUID = uuid.UUID('31b69969-e93f-547d-a960-60bbc837b7ff')
INDEFINITE_UUID = uuid.UUID('ccaf326f-e90a-5067-952d-c1b461205732')
LIMIT_UUID = uuid.UUID('aeabeb04-1aef-5e24-b541-6f3d59a630cd')


class Command(BaseCommand):
    help = 'Apply the fourteenth visually verified paper-candidate repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {
            INTEGRAL_ORDER_UUID, MONOTONICITY_UUID, DETERMINANT_UUID,
            QUADRATIC_UUID, INDEFINITE_UUID, LIMIT_UUID,
        }
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
            assets[2988].height == 220
            and assets[3385].height == 330
            and assets[2649].height == 285
            and assets[783].height == 320
            and assets[784].asset_type == 'source_context'
            and assets[21348].asset_type == 'source_context'
            and assets[21349].asset_type == 'question_crop'
            and questions[LIMIT_UUID].question_type == 'solution'
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-fourteen paper quality repairs are already applied.'))
            return

        if questions[LIMIT_UUID].question_type != 'fill_blank':
            raise CommandError(
                f'Expected {LIMIT_UUID} to be fill_blank; '
                f'found {questions[LIMIT_UUID].question_type}.',
            )
        requirements = {
            2988: (399, 'question_crop'), 3385: (446, 'question_crop'),
            2649: (346, 'question_crop'), 783: (495, 'question_crop'),
            784: (168, 'question_crop'), 21348: (181, 'question_crop'),
            21349: (149, 'answer_crop'), 21350: (100, 'answer_crop'),
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
            2988: render_part(assets[2988], 0, 220),
            3385: render_part(assets[3385], 0, 330),
            2649: render_part(assets[2649], 0, 285),
            783: render_part(assets[783], 0, 320),
        }
        self.stdout.write(
            'Validated four crop-contamination repairs, one recovered clean '
            'question crop, one blank continuation removal, and one type repair.'
        )
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for asset_id, value in rendered.items():
            replace_asset(assets[asset_id], value)

        integral_order = questions[INTEGRAL_ORDER_UUID]
        integral_order.display_label = 'Double integral · reverse integration order'
        integral_order.prompt_text = 'Reverse the order of integration in the displayed expression.'
        integral_order.save(update_fields=('display_label', 'prompt_text'))
        changed.add(integral_order)

        monotonicity = questions[MONOTONICITY_UUID]
        monotonicity.display_label = 'Partial derivatives · monotonicity comparison'
        monotonicity.prompt_text = monotonicity.prompt_text.split('2.无条件极值', 1)[0].strip()
        monotonicity.latex_text = ''
        monotonicity.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(monotonicity)

        quadratic = questions[QUADRATIC_UUID]
        quadratic.display_label = 'Quadratic form · orthogonal reduction and equation'
        quadratic.prompt_text = quadratic.prompt_text.split('6.求二次型最值', 1)[0].strip()
        quadratic.latex_text = ''
        quadratic.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(quadratic)

        indefinite = questions[INDEFINITE_UUID]
        assets[784].asset_type = 'source_context'
        assets[784].position = 90
        assets[784].save(update_fields=('asset_type', 'position'))
        indefinite.display_label = 'Indefinite integral · inverse cosine substitution'
        indefinite.prompt_text = 'Evaluate the displayed indefinite integral.'
        indefinite.latex_text = ''
        indefinite.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(indefinite)

        determinant = questions[DETERMINANT_UUID]
        assets[21348].asset_type = 'source_context'
        assets[21348].position = 90
        assets[21348].save(update_fields=('asset_type', 'position'))
        assets[21349].asset_type = 'question_crop'
        assets[21349].position = 0
        assets[21349].save(update_fields=('asset_type', 'position'))
        assets[21350].position = 0
        assets[21350].save(update_fields=('position',))
        determinant.display_label = '2010 · Mathematics II/III · determinant identity'
        determinant.prompt_text = (
            'For 3×3 matrices A and B with |A|=3, |B|=2 and |A⁻¹+B|=2, '
            'find |A+B⁻¹|.'
        )
        determinant.latex_text = ''
        determinant.save(update_fields=('display_label', 'prompt_text', 'latex_text'))
        changed.add(determinant)

        limit_question = questions[LIMIT_UUID]
        limit_question.question_type = 'solution'
        limit_question.question_type_source = 'human'
        limit_question.question_type_confidence = 1
        limit_question.question_type_human_verified = True
        limit_question.display_label = '2017 · Mathematics II/III · integral limit'
        limit_question.prompt_text = 'Evaluate the displayed integral limit as x approaches 0 from the right.'
        limit_question.latex_text = ''
        limit_question.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'display_label', 'prompt_text', 'latex_text',
        ))
        changed.add(limit_question)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-fourteen repairs to {len(changed)} questions.',
        ))
