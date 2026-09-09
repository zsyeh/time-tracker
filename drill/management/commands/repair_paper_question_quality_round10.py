import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionRevision


FILL_UUID = uuid.UUID('931f0bfb-d2a2-5192-a8c9-343bfd4987c3')
SOLUTION_UUID = uuid.UUID('7bcde355-8274-5e43-bde0-3dd57a5c7538')
CHOICE_UUID = uuid.UUID('6a60eea4-9157-5c22-ba6a-c215c8e16903')


class Command(BaseCommand):
    help = 'Apply the tenth visually verified paper-candidate type repairs.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        expected = {FILL_UUID, SOLUTION_UUID, CHOICE_UUID}
        questions = {
            question.uuid: question
            for question in Question.objects.select_for_update().filter(uuid__in=expected)
        }
        missing = expected - set(questions)
        if missing:
            raise CommandError(f'Missing expected questions: {sorted(str(value) for value in missing)}')
        targets = {
            FILL_UUID: ('fill_blank', 'Asymptote · logarithmic oscillation'),
            SOLUTION_UUID: ('solution', '2004 · Mathematics II · functional equation'),
            CHOICE_UUID: ('single_choice', 'Limit · radical expansion'),
        }
        if all(questions[key].question_type == value[0] for key, value in targets.items()):
            self.stdout.write(self.style.SUCCESS('Round-ten paper quality repairs are already applied.'))
            return

        expected_types = {
            FILL_UUID: 'single_choice', SOLUTION_UUID: 'single_choice', CHOICE_UUID: 'fill_blank',
        }
        for key, expected_type in expected_types.items():
            if questions[key].question_type != expected_type:
                raise CommandError(
                    f'Expected {key} to be {expected_type}; found {questions[key].question_type}.',
                )

        self.stdout.write('Validated three visually confirmed question-type corrections.')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to write the repairs.')
            transaction.set_rollback(True)
            return

        for key, (question_type, display_label) in targets.items():
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
            QuestionRevision.capture(question)
        self.stdout.write(self.style.SUCCESS('Applied round-ten repairs to 3 questions.'))
