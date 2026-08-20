from collections import Counter
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionTopic
from drill.topic_classifier import ANSWER_PDF_BY_DOCUMENT, TopicMatcher, toc_entries_by_page


class Command(BaseCommand):
    help = 'Assign recovered topicless questions from answer-book pages and bookmark ancestry.'

    def add_arguments(self, parser):
        parser.add_argument('answer_root', type=Path)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        root = options['answer_root'].expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'Answer PDF directory does not exist: {root}')
        updates = []
        counters = Counter()
        unresolved = []
        for document_title, filename in ANSWER_PDF_BY_DOCUMENT.items():
            pdf_path = root / filename
            if not pdf_path.is_file():
                raise CommandError(f'Required answer PDF is missing: {pdf_path}')
            questions = list(
                Question.objects.filter(
                    document__display_title=document_title,
                    is_practiceable=True,
                    similarity_topic__isnull=True,
                ).select_related('document').prefetch_related('assets').order_by('question_order')
            )
            if not questions:
                continue
            topics = list(
                QuestionTopic.objects.filter(document=questions[0].document)
                .select_related('parent', 'parent__parent', 'parent__parent__parent')
            )
            matcher = TopicMatcher(topics)
            pdf = pymupdf.open(pdf_path)
            pages = toc_entries_by_page(pdf.get_toc())
            for question in questions:
                topic = matcher.from_breadcrumb(question.source_label)
                confidence = 0.97 if topic else 0.0
                method = 'answer-book-breadcrumb'
                if topic is None:
                    page_numbers = {
                        asset.source_page_index + 1
                        for asset in question.assets.all()
                        if asset.asset_type == 'question_crop'
                        and asset.source_page_index is not None
                    }
                    entries = [entry for page in page_numbers for entry in pages.get(page, ())]
                    topic, leaf_score = matcher.from_toc_page(question.source_label, entries)
                    confidence = min(0.96, 0.85 + leaf_score * 0.1) if topic else 0.0
                    method = 'answer-book-toc'
                if topic is None:
                    unresolved.append(str(question.uuid))
                    counters['unresolved'] += 1
                    continue
                question.topic = topic
                question.similarity_topic = topic
                question.topic_classification_source = method
                question.topic_classification_confidence = confidence
                updates.append(question)
                counters[method] += 1
            pdf.close()

        self.stdout.write(f'Validated {sum(counters.values())} topicless practice rows.')
        for key, count in sorted(counters.items()):
            self.stdout.write(f'  {key}: {count}')
        if unresolved:
            self.stdout.write(f'  unresolved UUID sample: {unresolved[:10]}')
        if options['dry_run']:
            self.stdout.write('Dry run: no database rows changed.')
            return
        with transaction.atomic():
            Question.objects.bulk_update(
                updates,
                (
                    'topic', 'similarity_topic', 'topic_classification_source',
                    'topic_classification_confidence',
                ),
                batch_size=500,
            )
        self.stdout.write(self.style.SUCCESS(f'Classified {len(updates)} topicless questions.'))
