import hashlib
import json
import uuid
from pathlib import Path, PureWindowsPath

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.cleaning import classify_source, clean_document_title, clean_topic_title
from drill.models import (
    Question,
    QuestionAsset,
    QuestionDocument,
    QuestionTopic,
)


PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def load_json_lines(path):
    try:
        with path.open(encoding='utf-8') as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise CommandError(f'Invalid JSON in {path}:{line_number}: {exc}') from exc
    except OSError as exc:
        raise CommandError(f'Cannot read {path}: {exc}') from exc


def stable_question_uuid(fingerprint):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'https://drill.ehzsy.site/question/{fingerprint}')


class Command(BaseCommand):
    help = 'Idempotently import a normalized question-bank export and its PNG crops.'

    def add_arguments(self, parser):
        parser.add_argument(
            'export_directory',
            help='Directory containing documents.jsonl, nodes.jsonl, questions.jsonl and assets.jsonl.',
        )
        parser.add_argument(
            '--assets-root',
            help='Directory containing the source-hash asset subdirectories.',
        )
        parser.add_argument('--skip-assets', action='store_true')

    def handle(self, *args, **options):
        export_dir = Path(options['export_directory']).expanduser().resolve()
        required = {
            name: export_dir / f'{name}.jsonl'
            for name in ('documents', 'nodes', 'questions', 'assets')
        }
        missing = [str(path) for path in required.values() if not path.is_file()]
        if missing:
            raise CommandError(f'Missing normalized export files: {", ".join(missing)}')

        assets_root = Path(options['assets_root'] or export_dir / 'assets').expanduser().resolve()
        if not options['skip_assets'] and not assets_root.is_dir():
            raise CommandError(f'Assets root does not exist: {assets_root}')

        with transaction.atomic():
            documents = self._import_documents(required['documents'])
            topics = self._import_topics(required['nodes'], documents)
            questions = self._import_questions(required['questions'], documents, topics)
            asset_count = 0
            if not options['skip_assets']:
                asset_count = self._import_assets(required['assets'], assets_root, questions)

        call_command('clean_question_bank', stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            f'Question bank ready: {len(documents)} documents, {len(topics)} topics, '
            f'{len(questions)} questions, {asset_count} assets processed.'
        ))

    def _import_documents(self, path):
        result = {}
        for row in load_json_lines(path):
            source_id = int(row['id'])
            document, _ = QuestionDocument.objects.update_or_create(
                source_id=source_id,
                defaults={
                    'filename': row['filename'],
                    'title': Path(row['filename']).stem,
                    'display_title': clean_document_title(row['filename']),
                    'sha256': row['sha256'],
                    'page_count': int(row['page_count']),
                    'parser_strategy': row.get('parser_strategy') or '',
                    'relation_type': row.get('relation_type') or '',
                },
            )
            result[source_id] = document
        return result

    def _import_topics(self, path, documents):
        rows = list(load_json_lines(path))
        result = {}
        for row in rows:
            source_id = int(row['id'])
            document_id = int(row['document_id'])
            if document_id not in documents:
                raise CommandError(f'Topic {source_id} references missing document {document_id}.')
            topic, _ = QuestionTopic.objects.update_or_create(
                source_id=source_id,
                defaults={
                    'document': documents[document_id],
                    'parent': None,
                    'title': row['title'],
                    'display_title': clean_topic_title(row['title']),
                    'normalized_title': row.get('normalized_title') or '',
                    'level': int(row['level']),
                    'sort_order': int(row['sort_order']),
                },
            )
            result[source_id] = topic

        changed = []
        for row in rows:
            topic = result[int(row['id'])]
            parent_source_id = row.get('parent_id')
            parent = result.get(int(parent_source_id)) if parent_source_id is not None else None
            if parent_source_id is not None and parent is None:
                raise CommandError(f'Topic {topic.source_id} references missing parent {parent_source_id}.')
            if parent is not None and parent.document_id != topic.document_id:
                raise CommandError(f'Topic {topic.source_id} has a cross-document parent.')
            if topic.parent_id != (parent.pk if parent else None):
                topic.parent = parent
                changed.append(topic)
        if changed:
            QuestionTopic.objects.bulk_update(changed, ('parent',), batch_size=500)
        return result

    @staticmethod
    def _similarity_topic(topic):
        cursor = topic
        visited = set()
        while cursor is not None and cursor.level > 4 and cursor.pk not in visited:
            visited.add(cursor.pk)
            cursor = cursor.parent
        return cursor or topic

    def _import_questions(self, path, documents, topics):
        result = {}
        for row in load_json_lines(path):
            source_id = int(row['id'])
            document_id = int(row['document_id'])
            topic_source_id = row.get('knowledge_node_id')
            document = documents.get(document_id)
            topic = topics.get(int(topic_source_id)) if topic_source_id is not None else None
            if document is None:
                raise CommandError(f'Question {source_id} references missing document {document_id}.')
            if topic_source_id is not None and topic is None:
                raise CommandError(f'Question {source_id} references missing topic {topic_source_id}.')
            label = row.get('source_label') or ''
            source = classify_source(label)
            fingerprint = row['fingerprint']
            question, _ = Question.objects.update_or_create(
                fingerprint=fingerprint,
                defaults={
                    'uuid': stable_question_uuid(fingerprint),
                    'document': document,
                    'topic': topic,
                    'similarity_topic': self._similarity_topic(topic),
                    'question_order': int(row['question_order']),
                    'source_label': label,
                    'display_label': source.display_label,
                    'prompt_text': row.get('raw_text') or '',
                    'latex_text': row.get('latex_text') or '',
                    'content_mode': row['content_mode'],
                    'confidence': float(row.get('confidence', 1)),
                    'is_past_exam': source.is_past_exam,
                    'source_category': source.category,
                    'classification_reason': source.reason,
                    'classification_confidence': source.confidence,
                    'exam_year': source.year,
                    'exam_variant': source.variant,
                },
            )
            result[source_id] = question
        return result

    def _asset_path(self, assets_root, source_path):
        parts = PureWindowsPath(source_path).parts
        if len(parts) < 2:
            raise CommandError(f'Invalid asset path: {source_path}')
        candidate = (assets_root / parts[-2] / parts[-1]).resolve()
        try:
            candidate.relative_to(assets_root)
        except ValueError as exc:
            raise CommandError(f'Asset escapes its root: {source_path}') from exc
        return candidate

    def _import_assets(self, path, assets_root, questions):
        existing = dict(QuestionAsset.objects.values_list('source_id', 'sha256'))
        processed = 0
        for row in load_json_lines(path):
            source_id = int(row['id'])
            expected_sha = row['sha256']
            if existing.get(source_id) == expected_sha:
                processed += 1
                continue
            question_id = int(row['question_id'])
            question = questions.get(question_id)
            if question is None:
                raise CommandError(f'Asset {source_id} references missing question {question_id}.')
            source_file = self._asset_path(assets_root, row['file_path'])
            try:
                image_data = source_file.read_bytes()
            except OSError as exc:
                raise CommandError(f'Cannot read asset {source_file}: {exc}') from exc
            if not image_data.startswith(PNG_SIGNATURE):
                raise CommandError(f'Asset is not a PNG: {source_file}')
            actual_sha = hashlib.sha256(image_data).hexdigest()
            if actual_sha != expected_sha:
                raise CommandError(
                    f'Asset checksum mismatch for {source_file}: expected {expected_sha}, got {actual_sha}'
                )
            QuestionAsset.objects.update_or_create(
                source_id=source_id,
                defaults={
                    'question': question,
                    'position': int(row.get('position', 0)),
                    'asset_type': row.get('asset_type') or 'question_crop',
                    'sha256': expected_sha,
                    'mime_type': 'image/png',
                    'image_data': image_data,
                    'width': int(row['width']),
                    'height': int(row['height']),
                },
            )
            existing[source_id] = expected_sha
            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f'Processed {processed} assets…')
        return processed
