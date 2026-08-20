from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.cleaning import clean_topic_title, is_question_reference_topic
from drill.models import Question, QuestionTopic
from drill.topic_classifier import TopicMatcher


class Command(BaseCommand):
    help = (
        'Replace exercise-reference similarity topics with their nearest knowledge '
        'ancestor while retaining the original source topic for provenance.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--restore-source-topics', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['dry_run'] and options['restore_source_topics']:
            raise CommandError('--dry-run and --restore-source-topics cannot be combined.')

        topics_by_document = defaultdict(list)
        changed_topic_titles = []
        for topic in QuestionTopic.objects.select_related('parent').order_by(
            'document_id', 'sort_order'
        ):
            display_title = clean_topic_title(topic.title)
            if topic.display_title != display_title:
                topic.display_title = display_title
                changed_topic_titles.append(topic)
            topics_by_document[topic.document_id].append(topic)
        matchers = {
            document_id: TopicMatcher(topics)
            for document_id, topics in topics_by_document.items()
        }

        questions = list(
            Question.objects.filter(
                is_practiceable=True,
                similarity_topic__isnull=False,
            ).select_related('document', 'topic', 'similarity_topic')
        )
        changed = []
        by_document = Counter()
        cells_before = defaultdict(set)
        cells_after = defaultdict(set)
        for question in questions:
            cells_before[question.document_id].add(question.similarity_topic_id)
            target = question.similarity_topic
            if options['restore_source_topics']:
                if (
                    question.topic_id
                    and question.topic_id != question.similarity_topic_id
                    and question.topic_classification_source.startswith('answer-book-')
                    and is_question_reference_topic(
                        question.topic.display_title or question.topic.title
                    )
                ):
                    target = question.topic
            else:
                target = matchers[question.document_id].knowledge_topic(target)
            cells_after[question.document_id].add(target.pk)
            if target.pk == question.similarity_topic_id:
                continue
            question.similarity_topic = target
            changed.append(question)
            by_document[question.document.display_title or question.document.title] += 1

        action = 'restore' if options['restore_source_topics'] else 'normalize'
        self.stdout.write(f'Validated {len(changed)} question topic(s) to {action}.')
        self.stdout.write(f'Validated {len(changed_topic_titles)} cleaned topic title(s).')
        for document, count in sorted(by_document.items()):
            document_id = next(
                question.document_id
                for question in changed
                if (question.document.display_title or question.document.title) == document
            )
            self.stdout.write(
                f'  {document}: {count} question(s), '
                f'{len(cells_before[document_id])} -> {len(cells_after[document_id])} heatmap cells'
            )

        if options['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write('Dry run: no database rows changed.')
            return
        if changed:
            Question.objects.bulk_update(changed, ('similarity_topic',), batch_size=500)
        if changed_topic_titles:
            QuestionTopic.objects.bulk_update(
                changed_topic_titles,
                ('display_title',),
                batch_size=500,
            )
        self.stdout.write(self.style.SUCCESS(
            f'Updated {len(changed)} question topic(s) and '
            f'{len(changed_topic_titles)} topic title(s).'
        ))
