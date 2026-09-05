"""OCR-assisted, resumable classification of unresolved Mathematics II questions."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from drill.models import Question
from drill.question_type_classifier import classify_question_type_evidence


class Command(BaseCommand):
    help = 'Use question-image OCR plus source and answer evidence to classify unresolved math questions.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--language', default='eng')
        parser.add_argument('--cache', type=Path, default=Path('question_type_agent_review.jsonl'))
        parser.add_argument('--minimum-confidence', type=float, default=0.5)

    def handle(self, *args, **options):
        if not 1 <= options['workers'] <= 8:
            raise CommandError('--workers must be between 1 and 8.')
        if not 0 <= options['minimum_confidence'] <= 1:
            raise CommandError('--minimum-confidence must be between 0 and 1.')
        cache_path = options['cache'].expanduser().resolve()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cached = self.read_cache(cache_path)
        queryset = Question.objects.filter(
            subject='math2', is_practiceable=True, record_kind='question',
            question_type='unknown', question_type_human_verified=False,
        ).select_related('document', 'similarity_topic').order_by('pk')
        if options['limit']:
            queryset = queryset[:options['limit']]
        questions = list(queryset)
        pending = [question for question in questions if str(question.uuid) not in cached]
        self.stdout.write(
            f'Agent classification: {len(questions)} unresolved, '
            f'{len(cached)} cached, {len(pending)} OCR pending.'
        )

        with cache_path.open('a', encoding='utf-8') as output, ThreadPoolExecutor(
            max_workers=options['workers'], thread_name_prefix='question-type-ocr',
        ) as executor:
            for offset in range(0, len(pending), options['workers'] * 2):
                batch = pending[offset:offset + options['workers'] * 2]
                evidence = [self.evidence(question) for question in batch]
                ocr_results = executor.map(
                    lambda item: self.ocr(item['image_data'], options['language']), evidence,
                )
                for item, ocr_text in zip(evidence, ocr_results):
                    decision = classify_question_type_evidence(
                        item['metadata_text'], ocr_text=ocr_text,
                        answer_markdown=item['answer_markdown'],
                        question_ratio=item['question_ratio'], answer_ratio=item['answer_ratio'],
                    )
                    row = {
                        'uuid': item['uuid'], 'question_type': decision.label,
                        'confidence': decision.confidence, 'reason': decision.reason,
                        'ocr_excerpt': ocr_text[:3000],
                    }
                    cached[item['uuid']] = row
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    output.flush()
                self.stdout.write(f'Processed {min(offset + len(batch), len(pending))}/{len(pending)}')

        question_uuids = {str(question.uuid) for question in questions}
        eligible = [
            row for uuid, row in cached.items()
            if uuid in question_uuids
            and row['confidence'] >= options['minimum_confidence']
        ]
        if options['apply']:
            with transaction.atomic():
                for row in eligible:
                    Question.objects.filter(
                        uuid=row['uuid'], subject='math2', question_type='unknown',
                        question_type_human_verified=False,
                    ).update(
                        question_type=row['question_type'], question_type_source='agent',
                        question_type_confidence=row['confidence'],
                    )
        counts = {}
        for row in eligible:
            counts[row['question_type']] = counts.get(row['question_type'], 0) + 1
        low = sum(row['confidence'] < 0.75 for row in eligible)
        self.stdout.write(json.dumps({'eligible': len(eligible), 'low_confidence': low, 'labels': counts}, ensure_ascii=False))

    @staticmethod
    def read_cache(path):
        rows = {}
        if not path.exists():
            return rows
        with path.open(encoding='utf-8') as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if row['question_type'] not in {'single_choice', 'fill_blank', 'solution'}:
                        raise ValueError('invalid label')
                    rows[row['uuid']] = row
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise CommandError(f'Invalid cache row {line_number}: {error}') from error
        return rows

    @staticmethod
    def evidence(question):
        assets = list(question.assets.only(
            'image_data', 'width', 'height', 'asset_type', 'position',
        ).order_by('asset_type', 'position', 'pk'))
        question_assets = [asset for asset in assets if asset.asset_type == 'question_crop']
        answer_assets = [asset for asset in assets if asset.asset_type == 'answer_crop']
        primary = question_assets[0] if question_assets else None
        topic = question.similarity_topic
        return {
            'uuid': str(question.uuid),
            'metadata_text': '\n'.join(filter(None, (
                question.source_label, question.display_label, question.prompt_text,
                (topic.display_title or topic.title) if topic else '',
            ))),
            'answer_markdown': question.answer_markdown,
            'image_data': bytes(primary.image_data) if primary else b'',
            'question_ratio': sum(asset.height / max(asset.width, 1) for asset in question_assets),
            'answer_ratio': sum(asset.height / max(asset.width, 1) for asset in answer_assets),
        }

    @staticmethod
    def ocr(image_data, language):
        if not image_data:
            return ''
        try:
            process = subprocess.run(
                ['tesseract', 'stdin', 'stdout', '-l', language, '--psm', '6'],
                input=image_data, capture_output=True, timeout=45, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ''
        if process.returncode:
            return ''
        return process.stdout.decode('utf-8', errors='replace')
