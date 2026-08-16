import hashlib
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.cleaning import classify_source
from drill.models import Question, QuestionAsset, QuestionDocument, QuestionTopic
from drill.pdf_import import (
    parse_question_pdf,
    render_segment_png,
    stable_question_uuid,
    stable_source_id,
)


class Command(BaseCommand):
    help = 'Idempotently import the bookmarked cxy single-variable differentiation PDF.'

    def add_arguments(self, parser):
        parser.add_argument('pdf_path', type=Path)
        parser.add_argument('--dpi', type=int, default=160)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        pdf_path = options['pdf_path'].expanduser().resolve()
        if not pdf_path.is_file():
            raise CommandError(f'PDF does not exist: {pdf_path}')
        dpi = options['dpi']
        if not 120 <= dpi <= 200:
            raise CommandError('DPI must be between 120 and 200 for readable, storage-safe crops.')
        try:
            parsed = parse_question_pdf(pdf_path)
        except (OSError, ValueError, pymupdf.FileDataError) as exc:
            raise CommandError(f'Cannot parse {pdf_path}: {exc}') from exc

        category_counts = {}
        for question in parsed.questions:
            category = classify_source(question.source_label).category
            category_counts[category] = category_counts.get(category, 0) + 1
        asset_count = sum(len(question.segments) for question in parsed.questions)
        summary = ', '.join(f'{key}={value}' for key, value in sorted(category_counts.items()))
        self.stdout.write(
            f'Parsed {len(parsed.topics)} topics, {len(parsed.questions)} questions and '
            f'{asset_count} crop segments at {dpi} DPI ({summary}).'
        )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; the database was not changed.'))
            return

        strategy = f'pymupdf-bookmarks-crops-v1@{dpi}dpi'
        with transaction.atomic():
            document = self._upsert_document(parsed, strategy)
            topics = self._upsert_topics(parsed, document)
            expected_assets = asset_count
            exact_asset_ids = [
                stable_source_id(
                    'asset', parsed.sha256, question.question_order, position, dpi,
                )
                for question in parsed.questions
                for position, _segment in enumerate(question.segments)
            ]
            already_complete = (
                not options['force']
                and document.questions.count() == len(parsed.questions)
                and QuestionAsset.objects.filter(
                    question__document=document,
                    source_id__in=exact_asset_ids,
                ).count() == expected_assets
            )
            if already_complete:
                self.stdout.write(self.style.SUCCESS(
                    'This exact PDF and render profile are already fully imported.'
                ))
                return
            self._upsert_questions_and_assets(parsed, document, topics, dpi)

        self.stdout.write(self.style.SUCCESS(
            f'Imported {parsed.title}: {len(parsed.questions)} questions, '
            f'{asset_count} authenticated PNG crops at {dpi} DPI.'
        ))

    @staticmethod
    def _upsert_document(parsed, strategy):
        source_id = stable_source_id('document', parsed.sha256)
        document, _created = QuestionDocument.objects.update_or_create(
            sha256=parsed.sha256,
            defaults={
                'source_id': source_id,
                'filename': parsed.path.name,
                'title': parsed.title,
                'display_title': parsed.title,
                'author': parsed.author,
                'attribution': parsed.attribution,
                'page_count': parsed.page_count,
                'parser_strategy': strategy,
                'relation_type': 'single-variable differentiation',
            },
        )
        return document

    @staticmethod
    def _upsert_topics(parsed, document):
        topics = {}
        for parsed_topic in parsed.topics:
            topic, _created = QuestionTopic.objects.update_or_create(
                document=document,
                sort_order=parsed_topic.sort_order,
                defaults={
                    'source_id': stable_source_id(
                        'topic', parsed.sha256, parsed_topic.sort_order,
                    ),
                    'parent': None,
                    'title': parsed_topic.title,
                    'display_title': parsed_topic.display_title,
                    'normalized_title': parsed_topic.normalized_title,
                    'level': parsed_topic.level,
                },
            )
            topics[parsed_topic.sort_order] = topic
        changed = []
        for parsed_topic in parsed.topics:
            topic = topics[parsed_topic.sort_order]
            parent = topics.get(parsed_topic.parent_order)
            if topic.parent_id != (parent.pk if parent else None):
                topic.parent = parent
                changed.append(topic)
        if changed:
            QuestionTopic.objects.bulk_update(changed, ('parent',), batch_size=250)
        return topics

    def _upsert_questions_and_assets(self, parsed, document, topics, dpi):
        expected_orders = []
        with pymupdf.open(parsed.path) as pdf:
            for parsed_question in parsed.questions:
                expected_orders.append(parsed_question.question_order)
                source = classify_source(parsed_question.source_label)
                fingerprint = hashlib.sha256(
                    f'{parsed.sha256}:question:{parsed_question.question_order}:'.encode('utf-8')
                    + parsed_question.source_label.encode('utf-8')
                ).hexdigest()
                topic = topics.get(parsed_question.topic_order)
                question, _created = Question.objects.update_or_create(
                    document=document,
                    question_order=parsed_question.question_order,
                    defaults={
                        'uuid': stable_question_uuid(fingerprint),
                        'topic': topic,
                        'similarity_topic': topic,
                        'source_label': parsed_question.source_label,
                        'display_label': source.display_label,
                        'prompt_text': parsed_question.prompt_text,
                        'latex_text': '',
                        'content_mode': 'image',
                        'fingerprint': fingerprint,
                        'confidence': 0.98,
                        'is_past_exam': source.is_past_exam,
                        'source_category': source.category,
                        'record_kind': 'question',
                        'is_practiceable': True,
                        'classification_reason': source.reason,
                        'classification_confidence': source.confidence,
                        'exam_year': source.year,
                        'exam_variant': source.variant,
                    },
                )
                expected_source_ids = []
                for position, segment in enumerate(parsed_question.segments):
                    image_data, width, height = render_segment_png(pdf, segment, dpi)
                    image_sha = hashlib.sha256(image_data).hexdigest()
                    source_id = stable_source_id(
                        'asset', parsed.sha256, parsed_question.question_order, position, dpi,
                    )
                    expected_source_ids.append(source_id)
                    existing = QuestionAsset.objects.filter(source_id=source_id).only('sha256').first()
                    if existing is not None and existing.sha256 == image_sha:
                        continue
                    QuestionAsset.objects.update_or_create(
                        source_id=source_id,
                        defaults={
                            'question': question,
                            'position': position,
                            'asset_type': 'question_crop',
                            'sha256': image_sha,
                            'mime_type': 'image/png',
                            'image_data': image_data,
                            'width': width,
                            'height': height,
                        },
                    )
                QuestionAsset.objects.filter(question=question).exclude(
                    source_id__in=expected_source_ids,
                ).delete()
                if parsed_question.question_order % 100 == 0:
                    self.stdout.write(
                        f'Rendered {parsed_question.question_order}/{len(parsed.questions)} questions…'
                    )

        stale = Question.objects.filter(document=document).exclude(
            question_order__in=expected_orders,
        )
        if stale.filter(attempts__isnull=False).exists():
            raise CommandError('Stale imported questions have user attempts; refusing to delete them.')
        stale.delete()
