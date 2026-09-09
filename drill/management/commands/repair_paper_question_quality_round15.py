import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.repair_paper_question_quality_round8 import render_part, replace_asset
from drill.models import Question, QuestionRevision


QUADRATIC_UUID = uuid.UUID('31b69969-e93f-547d-a960-60bbc837b7ff')
LINEAR_SYSTEM_UUID = uuid.UUID('e6ad8baa-ad65-5998-ad8b-d9d5202247f1')


class Command(BaseCommand):
    help = 'Apply the fifteenth visually verified paper-candidate repair set.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {QUADRATIC_UUID, LINEAR_SYSTEM_UUID}
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
            assets[2649].height == 270
            and questions[LINEAR_SYSTEM_UUID].question_type == 'solution'
        )
        if already_applied:
            self.stdout.write(self.style.SUCCESS('Round-fifteen paper quality repairs are already applied.'))
            return
        if questions[LINEAR_SYSTEM_UUID].question_type != 'single_choice':
            raise CommandError(
                f'Expected {LINEAR_SYSTEM_UUID} to be single_choice; '
                f'found {questions[LINEAR_SYSTEM_UUID].question_type}.',
            )
        if assets.get(2649) is None or assets[2649].height != 285:
            raise CommandError(
                f'Expected question asset 2649 at 285px; found '
                f'{getattr(assets.get(2649), "height", None)}px.',
            )
        quadratic_crop = render_part(assets[2649], 0, 270)
        self.stdout.write('Validated one residual heading trim and one open-response type repair.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        quadratic = questions[QUADRATIC_UUID]
        replace_asset(assets[2649], quadratic_crop)
        QuestionRevision.capture(quadratic)

        linear_system = questions[LINEAR_SYSTEM_UUID]
        linear_system.question_type = 'solution'
        linear_system.question_type_source = 'human'
        linear_system.question_type_confidence = 1
        linear_system.question_type_human_verified = True
        linear_system.display_label = 'Linear systems · transformed coefficient matrix'
        linear_system.prompt_text = (
            'Given the solution set of Ax=β and the displayed matrix B, '
            'solve Bx=α₁−α₂+α₃.'
        )
        linear_system.latex_text = ''
        linear_system.save(update_fields=(
            'question_type', 'question_type_source', 'question_type_confidence',
            'question_type_human_verified', 'display_label', 'prompt_text', 'latex_text',
        ))
        QuestionRevision.capture(linear_system)
        self.stdout.write(self.style.SUCCESS('Applied round-fifteen repairs to 2 questions.'))
