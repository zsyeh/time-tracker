"""Classify math questions and export ambiguous cases for agent review."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question
from drill.question_type_classifier import classify_question_type


VALID_TYPES = {value for value, _label in Question.QUESTION_TYPE_CHOICES} - {'unknown'}


class Command(BaseCommand):
    help = 'Apply high-confidence question types and exchange low-confidence JSONL with an agent.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write high-confidence rule decisions.')
        parser.add_argument('--minimum-confidence', type=float, default=0.85)
        parser.add_argument('--export-review', type=Path)
        parser.add_argument('--import-agent', type=Path)
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **options):
        if options['minimum_confidence'] < 0 or options['minimum_confidence'] > 1:
            raise CommandError('--minimum-confidence must be between 0 and 1.')
        if options['import_agent']:
            self.import_agent_labels(options['import_agent'])
        queryset = Question.objects.filter(
            subject='math2', is_practiceable=True, record_kind='question',
            question_type_human_verified=False,
        ).select_related('document', 'similarity_topic').order_by('pk')
        if options['limit']:
            queryset = queryset[:options['limit']]
        decisions = []
        counts = {value: 0 for value, _label in Question.QUESTION_TYPE_CHOICES}
        threshold = options['minimum_confidence']
        for question in queryset.iterator(chunk_size=200):
            text = '\n'.join(filter(None, (
                question.source_label, question.display_label, question.prompt_text,
            )))
            decision = classify_question_type(text)
            counts[decision.label] += 1
            decisions.append((question, decision))
        if options['apply']:
            with transaction.atomic():
                for question, decision in decisions:
                    if decision.label == 'unknown' or decision.confidence < threshold:
                        continue
                    question.question_type = decision.label
                    question.question_type_source = 'rule'
                    question.question_type_confidence = decision.confidence
                    question.save(update_fields=(
                        'question_type', 'question_type_source', 'question_type_confidence',
                    ))
        if options['export_review']:
            self.export_review(options['export_review'], decisions, threshold)
        self.stdout.write(json.dumps(counts, ensure_ascii=False, sort_keys=True))

    def export_review(self, output, decisions, threshold):
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = 0
        with output.open('w', encoding='utf-8') as target:
            for question, decision in decisions:
                if decision.label != 'unknown' and decision.confidence >= threshold:
                    continue
                target.write(json.dumps({
                    'uuid': str(question.uuid),
                    'document': question.document.display_title or question.document.title,
                    'topic': (
                        question.similarity_topic.display_title or question.similarity_topic.title
                        if question.similarity_topic else ''
                    ),
                    'source_label': question.source_label,
                    'prompt_text': question.prompt_text,
                    'rule_label': decision.label,
                    'rule_confidence': decision.confidence,
                    'allowed_labels': sorted(VALID_TYPES),
                }, ensure_ascii=False) + '\n')
                rows += 1
        self.stdout.write(f'Exported {rows} low-confidence rows to {output}.')

    def import_agent_labels(self, source):
        source = source.expanduser().resolve()
        if not source.is_file():
            raise CommandError(f'Agent label file does not exist: {source}')
        updated = 0
        with transaction.atomic(), source.open(encoding='utf-8') as rows:
            for line_number, line in enumerate(rows, 1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    label = payload['question_type']
                    confidence = float(payload['confidence'])
                    question_uuid = payload['uuid']
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                    raise CommandError(f'Invalid agent row {line_number}: {error}') from error
                if label not in VALID_TYPES or not 0 <= confidence <= 1:
                    raise CommandError(f'Invalid agent label/confidence on row {line_number}.')
                updated += Question.objects.filter(
                    uuid=question_uuid,
                    subject='math2',
                    question_type_human_verified=False,
                ).update(
                    question_type=label,
                    question_type_source='agent',
                    question_type_confidence=confidence,
                )
        self.stdout.write(f'Imported {updated} agent labels from {source}.')
