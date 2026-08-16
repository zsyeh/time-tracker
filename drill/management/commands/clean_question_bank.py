from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Max

from drill.cleaning import (
    classify_record_kind,
    classify_source,
    clean_document_title,
    clean_topic_title,
)
from drill.models import Question, QuestionDocument, QuestionTopic


class Command(BaseCommand):
    help = 'Build reversible display/source metadata without changing imported raw fields.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        counters = Counter()
        changed_documents = []
        changed_topics = []
        changed_questions = []

        with transaction.atomic():
            for document in QuestionDocument.objects.all():
                display_title = clean_document_title(document.filename)
                if document.display_title != display_title:
                    document.display_title = display_title
                    changed_documents.append(document)

            for topic in QuestionTopic.objects.all():
                display_title = clean_topic_title(topic.title)
                if topic.display_title != display_title:
                    topic.display_title = display_title
                    changed_topics.append(topic)

            questions = Question.objects.annotate(
                cleanup_asset_count=Count('assets'),
                cleanup_max_asset_height=Max('assets__height'),
            ).iterator(chunk_size=500)
            for question in questions:
                source = classify_source(question.source_label)
                record_kind, is_practiceable, record_reason, record_confidence = classify_record_kind(
                    source_category=source.category,
                    source_label=question.source_label,
                    prompt_text=question.prompt_text,
                    asset_count=question.cleanup_asset_count,
                    max_asset_height=question.cleanup_max_asset_height,
                )
                values = {
                    'display_label': source.display_label,
                    'source_category': source.category,
                    'record_kind': record_kind,
                    'is_practiceable': is_practiceable,
                    'classification_reason': f'{source.reason}; {record_reason}',
                    'classification_confidence': min(source.confidence, record_confidence),
                    'is_past_exam': source.is_past_exam,
                    'exam_year': source.year,
                    'exam_variant': source.variant,
                }
                counters[f'source:{source.category}'] += 1
                counters[f'record:{record_kind}'] += 1
                if any(getattr(question, field) != value for field, value in values.items()):
                    for field, value in values.items():
                        setattr(question, field, value)
                    changed_questions.append(question)

            if not dry_run:
                if changed_documents:
                    QuestionDocument.objects.bulk_update(changed_documents, ('display_title',))
                if changed_topics:
                    QuestionTopic.objects.bulk_update(changed_topics, ('display_title',), batch_size=500)
                if changed_questions:
                    Question.objects.bulk_update(
                        changed_questions,
                        (
                            'display_label', 'source_category', 'record_kind', 'is_practiceable',
                            'classification_reason', 'classification_confidence', 'is_past_exam',
                            'exam_year', 'exam_variant',
                        ),
                        batch_size=500,
                    )
            else:
                transaction.set_rollback(True)

        mode = 'Dry run' if dry_run else 'Updated'
        self.stdout.write(f'{mode}: {len(changed_documents)} documents, {len(changed_topics)} topics, '
                          f'{len(changed_questions)} question rows')
        for key in sorted(counters):
            self.stdout.write(f'  {key}: {counters[key]}')
