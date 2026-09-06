from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import ExamPaper, ExamPaperItem
from drill.paper_generator import PaperGenerator


class Command(BaseCommand):
    help = 'Safely replace the items of an entirely unanswered exam paper.'

    def add_arguments(self, parser):
        parser.add_argument('paper_uuid')
        parser.add_argument('--seed', type=int)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        with transaction.atomic():
            try:
                paper = ExamPaper.objects.select_for_update().select_related(
                    'blueprint', 'user',
                ).get(uuid=options['paper_uuid'])
            except ExamPaper.DoesNotExist as error:
                raise CommandError('Paper does not exist.') from error
            items = ExamPaperItem.objects.filter(paper=paper)
            has_activity = (
                items.exclude(result='unanswered').exists()
                or items.exclude(user_answer='').exists()
                or items.filter(time_spent_seconds__isnull=False).exists()
            )
            if has_activity:
                raise CommandError(
                    'Refusing to regenerate a paper with answers, results, or recorded time.',
                )

            replacement = PaperGenerator().generate(
                user=paper.user,
                blueprint=paper.blueprint,
                seed=options['seed'],
            )
            replacement_ids = list(
                replacement.items.order_by('position').values_list('question_id', flat=True),
            )
            if options['apply']:
                items.delete()
                replacement.items.update(paper=paper)
                replacement.delete()
                paper.seed = options['seed'] if options['seed'] is not None else replacement.seed
                paper.status = 'generated'
                paper.started_at = None
                paper.completed_at = None
                paper.save(update_fields=(
                    'seed', 'status', 'started_at', 'completed_at',
                ))
            else:
                transaction.set_rollback(True)

        action = 'Regenerated' if options['apply'] else 'Validated replacement for'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {paper.uuid}: {len(replacement_ids)} questions, '
            f'seed={options["seed"]}, ids={replacement_ids}',
        ))
