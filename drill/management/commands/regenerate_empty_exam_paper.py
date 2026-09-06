from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import ExamPaper, ExamPaperItem, Question, QuestionRevision
from drill.paper_generator import PaperGenerator


class Command(BaseCommand):
    help = 'Safely replace the items of an entirely unanswered exam paper.'

    def add_arguments(self, parser):
        parser.add_argument('paper_uuid')
        parser.add_argument('--seed', type=int)
        parser.add_argument(
            '--question-ids',
            help='Comma-separated, visually audited question IDs in final paper order.',
        )
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

            explicit_ids = self.parse_question_ids(options['question_ids'])
            if explicit_ids is not None:
                selected = self.validate_explicit_questions(paper, explicit_ids)
                replacement_ids = explicit_ids
                if options['apply']:
                    items.delete()
                    ExamPaperItem.objects.bulk_create([
                        ExamPaperItem(
                            paper=paper,
                            section=section,
                            question=question,
                            question_revision=QuestionRevision.capture(question),
                            position=position,
                            score=section.score_per_question,
                            selected_fingerprint=question.fingerprint,
                        )
                        for position, (section, question) in enumerate(selected, 1)
                    ])
                    self.reset_paper(paper, options['seed'])
            else:
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
                    replacement_seed = replacement.seed
                    replacement.delete()
                    self.reset_paper(
                        paper,
                        options['seed'] if options['seed'] is not None else replacement_seed,
                    )
                else:
                    transaction.set_rollback(True)

        action = 'Regenerated' if options['apply'] else 'Validated replacement for'
        reported_seed = paper.seed if options['apply'] else options['seed']
        self.stdout.write(self.style.SUCCESS(
            f'{action} {paper.uuid}: {len(replacement_ids)} questions, '
            f'seed={reported_seed}, ids={replacement_ids}',
        ))

    @staticmethod
    def parse_question_ids(raw):
        if raw is None:
            return None
        try:
            values = [int(value.strip()) for value in raw.split(',') if value.strip()]
        except ValueError as exc:
            raise CommandError('--question-ids must be comma-separated integers.') from exc
        if not values:
            raise CommandError('--question-ids cannot be empty.')
        if len(values) != len(set(values)):
            raise CommandError('--question-ids cannot contain duplicates.')
        return values

    @staticmethod
    def validate_explicit_questions(paper, question_ids):
        sections = list(paper.blueprint.sections.order_by('order'))
        required = sum(section.question_count for section in sections)
        if len(question_ids) != required:
            raise CommandError(
                f'Blueprint requires {required} questions; received {len(question_ids)}.',
            )
        questions = {
            question.pk: question
            for question in Question.objects.filter(pk__in=question_ids).select_related(
                'document',
            ).prefetch_related('assets')
        }
        missing = [question_id for question_id in question_ids if question_id not in questions]
        if missing:
            raise CommandError(f'Questions do not exist: {missing}.')
        selected = []
        cursor = 0
        for section in sections:
            for question_id in question_ids[cursor:cursor + section.question_count]:
                question = questions[question_id]
                if (
                    question.subject != paper.blueprint.subject
                    or question.document.workspace != 'drill'
                    or not question.is_practiceable
                    or question.record_kind != 'question'
                ):
                    raise CommandError(f'Question {question_id} is not eligible for this paper.')
                if question.question_type != section.question_type:
                    raise CommandError(
                        f'Question {question_id} is {question.question_type}, '
                        f'but position {cursor + 1} requires {section.question_type}.',
                    )
                has_answer = bool(question.answer_markdown.strip()) or any(
                    asset.asset_type == 'answer_crop' and asset.height >= 60
                    for asset in question.assets.all()
                )
                if not has_answer:
                    raise CommandError(f'Question {question_id} has no reviewable answer.')
                selected.append((section, question))
                cursor += 1
        return selected

    @staticmethod
    def reset_paper(paper, seed):
        if seed is not None:
            paper.seed = seed
        paper.status = 'generated'
        paper.started_at = None
        paper.completed_at = None
        paper.save(update_fields=('seed', 'status', 'started_at', 'completed_at'))
