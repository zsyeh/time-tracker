from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from drill.cleaning import classify_source_with_context
from drill.models import Question


class Command(BaseCommand):
    help = 'Conservatively classify visible practice rows whose source is still unclassified.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        questions = list(
            Question.objects.filter(
                is_practiceable=True,
                source_category='unclassified',
            ).select_related('topic').order_by('pk')
        )
        updates = []
        counters = Counter()
        for question in questions:
            topic_title = ''
            if question.topic_id:
                topic_title = question.topic.display_title or question.topic.title
            result = classify_source_with_context(question.source_label, topic_title)
            if result.category == 'unclassified':
                continue
            question.source_category = result.category
            question.is_past_exam = result.is_past_exam
            question.exam_year = result.year
            question.exam_variant = result.variant
            question.classification_reason = result.reason
            question.classification_confidence = result.confidence
            updates.append(question)
            counters[result.category] += 1

        self.stdout.write(f'Validated {len(questions)} unclassified practice rows.')
        for category, count in sorted(counters.items()):
            self.stdout.write(f'  {category}: {count}')
        if options['dry_run']:
            self.stdout.write('Dry run: no database rows changed.')
            return
        with transaction.atomic():
            Question.objects.bulk_update(
                updates,
                (
                    'source_category', 'is_past_exam', 'exam_year', 'exam_variant',
                    'classification_reason', 'classification_confidence',
                ),
                batch_size=500,
            )
        self.stdout.write(self.style.SUCCESS(f'Classified {len(updates)} practice rows.'))
