"""OCR-assisted, resumable classification of unresolved Mathematics II questions."""

import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
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
        parser.add_argument(
            '--promote-neighbor-consensus', action='store_true',
            help=(
                'Re-review low-confidence labels using matching high-confidence '
                'questions on both sides in the same topic, then stop.'
            ),
        )

    def handle(self, *args, **options):
        if not 1 <= options['workers'] <= 8:
            raise CommandError('--workers must be between 1 and 8.')
        if not 0 <= options['minimum_confidence'] <= 1:
            raise CommandError('--minimum-confidence must be between 0 and 1.')
        cache_path = options['cache'].expanduser().resolve()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if options['promote_neighbor_consensus']:
            self.promote_neighbor_consensus(cache_path, apply=options['apply'])
            return
        cached = self.read_cache(cache_path)
        queryset = Question.objects.filter(
            subject='math2', is_practiceable=True, record_kind='question',
            question_type='unknown', question_type_human_verified=False,
        ).select_related('document', 'similarity_topic').order_by('pk')
        if options['limit']:
            queryset = queryset[:options['limit']]
        questions = list(queryset)
        question_uuids = {str(question.uuid) for question in questions}
        cached_eligible = [
            row for uuid, row in cached.items()
            if uuid in question_uuids
            and row['confidence'] >= options['minimum_confidence']
        ]
        if options['apply']:
            self.apply_rows(cached_eligible)
        pending = [question for question in questions if str(question.uuid) not in cached]
        neighbor_context = self.neighbor_context()
        self.stdout.write(
            f'Agent classification: {len(questions)} unresolved, '
            f'{len(cached)} cached, {len(pending)} OCR pending.'
        )

        with cache_path.open('a', encoding='utf-8') as output, ThreadPoolExecutor(
            max_workers=options['workers'], thread_name_prefix='question-type-ocr',
        ) as executor:
            for offset in range(0, len(pending), options['workers'] * 2):
                batch = pending[offset:offset + options['workers'] * 2]
                evidence = [self.evidence(question, neighbor_context.get(question.pk)) for question in batch]
                preliminary = [
                    classify_question_type_evidence(
                        item['metadata_text'], answer_markdown=item['answer_markdown'],
                        question_ratio=item['question_ratio'], answer_ratio=item['answer_ratio'],
                        neighbor_type=item['neighbor_type'], neighbor_span=item['neighbor_span'],
                    )
                    for item in evidence
                ]
                ocr_results = executor.map(
                    lambda pair: '' if pair[1].confidence >= 0.85 else self.ocr(
                        pair[0]['image_data'], options['language'],
                    ),
                    zip(evidence, preliminary),
                )
                for item, initial, ocr_text in zip(evidence, preliminary, ocr_results):
                    decision = initial if initial.confidence >= 0.85 else classify_question_type_evidence(
                        item['metadata_text'], ocr_text=ocr_text, answer_markdown=item['answer_markdown'],
                        question_ratio=item['question_ratio'], answer_ratio=item['answer_ratio'],
                        neighbor_type=item['neighbor_type'], neighbor_span=item['neighbor_span'],
                    )
                    row = {
                        'uuid': item['uuid'], 'question_type': decision.label,
                        'confidence': decision.confidence, 'reason': decision.reason,
                        'ocr_excerpt': ocr_text[:3000],
                    }
                    cached[item['uuid']] = row
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    output.flush()
                    if options['apply'] and decision.confidence >= options['minimum_confidence']:
                        self.apply_rows([row])
                self.stdout.write(f'Processed {min(offset + len(batch), len(pending))}/{len(pending)}')

        eligible = [
            row for uuid, row in cached.items()
            if uuid in question_uuids
            and row['confidence'] >= options['minimum_confidence']
        ]
        counts = {}
        for row in eligible:
            counts[row['question_type']] = counts.get(row['question_type'], 0) + 1
        low = sum(row['confidence'] < 0.75 for row in eligible)
        self.stdout.write(json.dumps({'eligible': len(eligible), 'low_confidence': low, 'labels': counts}, ensure_ascii=False))

    @staticmethod
    def apply_rows(rows, *, maximum_existing_confidence=None):
        with transaction.atomic():
            for row in rows:
                questions = Question.objects.filter(
                    uuid=row['uuid'], subject='math2', question_type='unknown',
                    question_type_human_verified=False,
                )
                if maximum_existing_confidence is not None:
                    questions = Question.objects.filter(
                        uuid=row['uuid'], subject='math2',
                        question_type_human_verified=False,
                    ).filter(
                        Q(question_type_confidence__lt=maximum_existing_confidence)
                        | Q(question_type_confidence__isnull=True),
                    )
                questions.update(
                    question_type=row['question_type'], question_type_source=(
                        'neighbor' if row.get('reason', '').startswith(
                            'High-confidence questions on both sides'
                        ) else 'agent'
                    ),
                    question_type_confidence=row['confidence'],
                )

    def promote_neighbor_consensus(self, cache_path, *, apply):
        """Promote only labels bracketed by matching strong topic anchors.

        Context is calculated before any writes, so newly promoted rows cannot
        recursively become anchors and propagate a mistaken label through a
        long run of ambiguous questions.
        """
        context = self.neighbor_context()
        questions = Question.objects.filter(
            subject='math2', is_practiceable=True, record_kind='question',
            question_type_human_verified=False,
        ).filter(
            Q(question_type_confidence__lt=0.75)
            | Q(question_type_confidence__isnull=True),
        ).only('pk', 'uuid').order_by('pk')
        rows = []
        for question in questions.iterator(chunk_size=500):
            neighbor = context.get(question.pk)
            if not neighbor:
                continue
            label, span = neighbor
            rows.append({
                'uuid': str(question.uuid),
                'question_type': label,
                'confidence': 0.87,
                'reason': (
                    'High-confidence questions on both sides in the same topic '
                    f'use this type (anchor span {span}).'
                ),
                'ocr_excerpt': '',
            })
        if apply:
            self.apply_rows(rows, maximum_existing_confidence=0.75)
        if rows:
            with cache_path.open('a', encoding='utf-8') as output:
                for row in rows:
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
        verb = 'Promoted' if apply else 'Validated'
        counts = defaultdict(int)
        for row in rows:
            counts[row['question_type']] += 1
        self.stdout.write(json.dumps({
            'action': verb.lower(),
            'neighbor_consensus': len(rows),
            'labels': dict(sorted(counts.items())),
        }, ensure_ascii=False))

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
    def evidence(question, neighbor=None):
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
            'neighbor_type': neighbor[0] if neighbor else '',
            'neighbor_span': neighbor[1] if neighbor else 0,
        }

    @staticmethod
    def neighbor_context():
        groups = defaultdict(list)
        rows = Question.objects.filter(
            subject='math2', is_practiceable=True, record_kind='question',
        ).values(
            'pk', 'document_id', 'similarity_topic_id', 'topic_id',
            'question_order', 'question_type', 'question_type_confidence',
            'question_type_human_verified',
        )
        for row in rows:
            key = (row['document_id'], row['similarity_topic_id'] or row['topic_id'])
            groups[key].append(row)
        context = {}
        for group in groups.values():
            group.sort(key=lambda row: (row['question_order'], row['pk']))
            previous = [None] * len(group)
            following = [None] * len(group)
            known = None
            for index, row in enumerate(group):
                previous[index] = known
                if Command.is_context_anchor(row):
                    known = row
            known = None
            for index in range(len(group) - 1, -1, -1):
                following[index] = known
                if Command.is_context_anchor(group[index]):
                    known = group[index]
            for index, row in enumerate(group):
                before, after = previous[index], following[index]
                if Command.is_context_anchor(row) or not before or not after:
                    continue
                if before['question_type'] != after['question_type']:
                    continue
                span = after['question_order'] - before['question_order']
                if 0 < span <= 16:
                    context[row['pk']] = (before['question_type'], span)
        return context

    @staticmethod
    def is_context_anchor(row):
        return row['question_type'] != 'unknown' and (
            row['question_type_human_verified']
            or (row['question_type_confidence'] or 0) >= 0.85
        )

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
