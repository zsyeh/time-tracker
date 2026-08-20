from django.core.management.base import BaseCommand
from django.db import transaction

from drill.models import Question


OUTLINE_UUIDS = {
    '3b2d32f2-8d01-5a79-8eba-a93ab3e57d1f': 'polar-coordinate outline label',
    'c7805161-9bdd-599d-bb6b-e57bb3ff3c4e': 'matrix-equivalence outline label',
    'a469f431-0925-59b4-ad8c-9b77be76d08d': 'split option belonging to question 373',
    '74be0bf6-5ce5-5827-979c-1fd26d584d6a': 'split option belonging to question 373',
}


class Command(BaseCommand):
    help = 'Mark known imported outline labels as non-practiceable records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        questions = {str(q.uuid): q for q in Question.objects.filter(uuid__in=OUTLINE_UUIDS)}
        missing = sorted(set(OUTLINE_UUIDS) - questions.keys())
        if missing:
            self.stderr.write(self.style.WARNING(f'Missing known outline UUIDs: {missing}'))

        changes = []
        for uuid, question in questions.items():
            if question.record_kind != 'section' or question.is_practiceable:
                changes.append((question, OUTLINE_UUIDS[uuid]))

        self.stdout.write(f'Outline records requiring repair: {len(changes)}')
        for question, reason in changes:
            self.stdout.write(f'  {question.uuid}: {reason}')
        if not options['apply']:
            self.stdout.write('Dry run only; pass --apply to update the database.')
            return

        with transaction.atomic():
            for question, _reason in changes:
                question.record_kind = 'section'
                question.is_practiceable = False
                question.save(update_fields=('record_kind', 'is_practiceable'))
        self.stdout.write(self.style.SUCCESS(f'Repaired {len(changes)} outline records.'))
