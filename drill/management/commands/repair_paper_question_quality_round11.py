import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.repair_paper_question_quality_round8 import render_part, replace_asset
from drill.models import Question, QuestionRevision


TYPE_REPAIRS = {
    uuid.UUID('a5dadcca-a0d8-5695-957a-806ed4167de6'): (
        'solution', 'Improper integral · convergence range',
    ),
    uuid.UUID('1eca71c9-4534-539f-8520-522d8d267f82'): (
        'fill_blank', 'Symmetric integral limit',
    ),
    uuid.UUID('a9b75fd5-b722-506e-a5f9-b0178e515d1f'): (
        'single_choice', 'Differential equation · linear drag',
    ),
}
HYDROSTATIC_UUID = uuid.UUID('545b2c94-dd52-53ec-990b-ff668c140dc4')
IMPROPER_FILL_UUID = uuid.UUID('8851c55d-8333-5bdf-9f8d-57880261c775')
OUTER_PRODUCT_UUID = uuid.UUID('99e21e59-a102-5777-88a5-c50b20aa141e')


class Command(BaseCommand):
    help = 'Apply the eleventh visually verified paper-candidate repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {*TYPE_REPAIRS, HYDROSTATIC_UUID, IMPROPER_FILL_UUID, OUTER_PRODUCT_UUID}
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
            all(questions[key].question_type == target[0] for key, target in TYPE_REPAIRS.items())
            and assets[1285].height == 430
            and assets[1286].asset_type == 'source_context'
            and assets[1488].height == 275
            and assets[1907].height == 150
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-eleven paper quality repairs are already applied.'))
            return

        expected_types = {
            key: old for key, old in zip(TYPE_REPAIRS, ('single_choice', 'solution', 'solution'))
        }
        for key, expected_type in expected_types.items():
            if questions[key].question_type != expected_type:
                raise CommandError(
                    f'Expected {key} to be {expected_type}; found {questions[key].question_type}.',
                )
        requirements = {
            1285: (690, 'question_crop'), 1286: (168, 'question_crop'),
            1488: (393, 'question_crop'), 1907: (229, 'question_crop'),
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
            1285: render_part(assets[1285], 0, 430),
            1488: render_part(assets[1488], 0, 275),
            1907: render_part(assets[1907], 0, 150),
        }
        self.stdout.write('Validated three type repairs and three crop-contamination repairs.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        changed = set()
        for key, (question_type, display_label) in TYPE_REPAIRS.items():
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

        hydrostatic = questions[HYDROSTATIC_UUID]
        replace_asset(assets[1285], rendered[1285])
        assets[1286].asset_type = 'source_context'
        assets[1286].position = 90
        assets[1286].save(update_fields=('asset_type', 'position'))
        hydrostatic.prompt_text = hydrostatic.prompt_text.rsplit('88/129', 1)[0].strip()
        hydrostatic.latex_text = ''
        hydrostatic.display_label = 'Hydrostatic force · elliptic plate'
        hydrostatic.save(update_fields=('prompt_text', 'latex_text', 'display_label'))
        changed.add(hydrostatic)

        improper_fill = questions[IMPROPER_FILL_UUID]
        replace_asset(assets[1488], rendered[1488])
        improper_fill.prompt_text = improper_fill.prompt_text.split('8. 已知', 1)[0].strip()
        improper_fill.latex_text = ''
        improper_fill.display_label = 'Limit and improper integral · solve n'
        improper_fill.save(update_fields=('prompt_text', 'latex_text', 'display_label'))
        changed.add(improper_fill)

        outer_product = questions[OUTER_PRODUCT_UUID]
        replace_asset(assets[1907], rendered[1907])
        outer_product.prompt_text = outer_product.prompt_text.rsplit('j)简单性质考察', 1)[0].strip()
        outer_product.latex_text = ''
        outer_product.display_label = '2003 · Mathematics II · outer product'
        outer_product.save(update_fields=('prompt_text', 'latex_text', 'display_label'))
        changed.add(outer_product)

        for question in changed:
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS(
            f'Applied round-eleven repairs to {len(changed)} questions.',
        ))
