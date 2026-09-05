"""Import the compact 892 review sheets that contain explicit question/answer pairs.

These PDFs are text-based and are deliberately handled separately from the
scanned workbook/answer pairs.  The importer accepts only sources with an
unambiguous ``number + question + 答: + answer`` structure; a source that does
not meet that contract is reported and left untouched rather than creating
guessed question/answer pairings.
"""

import hashlib
import re
import uuid
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionDocument, QuestionTopic


TOPIC_ID_BASE = 892_400_000_000

REVIEW_SOURCES = {
    'signal': {
        'filename': '信号简答.pdf',
        'document_title': '892 · 信号与系统',
        'order_base': 210_000,
    },
    'digital': {
        'filename': '数电简答.pdf',
        'document_title': '892 · 数字电子技术',
        'order_base': 220_000,
    },
    'analog': {
        'filename': '模电简答.pdf',
        'document_title': '892 · 模拟电子技术',
        'order_base': 230_000,
    },
    'circuit': {
        'filename': '电路简答.pdf',
        'document_title': '892 · 电路原理',
        'order_base': 240_000,
    },
}

# Keep the item delimiter at the beginning of a line.  This avoids treating
# numbered scoring points inside an answer as the following question.
PAIR_RE = re.compile(
    r'(?ms)^\s*(?P<number>\d{1,3})\s*[、.．]\s*'
    r'(?P<prompt>.+?)\s*答\s*[：:]\s*'
    r'(?P<answer>.*?)(?=^\s*\d{1,3}\s*[、.．]|\Z)',
)


def stable_positive_id(prefix, value):
    digest = hashlib.sha256(value.encode('utf-8')).digest()
    return prefix + int.from_bytes(digest[:6], 'big')


def stable_uuid(value):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'https://ei.ehzsy.site/review/{value}')


def normalize(value):
    """Preserve paragraph breaks while removing PDF extraction whitespace."""
    paragraphs = []
    for paragraph in value.splitlines():
        cleaned = re.sub(r'\s+', ' ', paragraph).strip()
        if cleaned:
            paragraphs.append(cleaned)
    return '\n\n'.join(paragraphs)


def label(number, prompt):
    plain = re.sub(r'\s+', ' ', prompt).strip()
    return f'背诵简答 {number} · {plain[:68]}{"…" if len(plain) > 68 else ""}'


class Command(BaseCommand):
    help = 'Idempotently import unambiguous 892 review-sheet question/answer pairs.'

    def add_arguments(self, parser):
        parser.add_argument('source_root', type=Path)
        parser.add_argument('--subjects', default=','.join(REVIEW_SOURCES))
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        root = options['source_root'].expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'Not a source directory: {root}')
        subjects = [item.strip() for item in options['subjects'].split(',') if item.strip()]
        unknown = set(subjects) - set(REVIEW_SOURCES)
        if unknown:
            raise CommandError(f'Unknown review source(s): {", ".join(sorted(unknown))}')

        reports = [self.audit_subject(root, subject) for subject in subjects]
        for report in reports:
            self.stdout.write(
                f'{report["subject"]}: {len(report["records"])} verified review pairs from '
                f'{report["path"].name}.'
            )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; no database rows were written.'))
            return

        with transaction.atomic():
            count = sum(self.import_subject(report) for report in reports)
        self.stdout.write(self.style.SUCCESS(f'Imported or updated {count} EI review questions.'))

    def audit_subject(self, root, subject):
        config = REVIEW_SOURCES[subject]
        path = self.source_file(root, config['filename'])
        if not path.is_file():
            raise CommandError(f'Missing review PDF for {subject}: {config["filename"]}')
        document = pymupdf.open(path)
        try:
            text = '\n'.join(page.get_text() for page in document)
        finally:
            document.close()
        records = []
        seen = set()
        for match in PAIR_RE.finditer(text):
            number = int(match.group('number'))
            prompt = normalize(match.group('prompt'))
            answer = normalize(match.group('answer'))
            if number in seen or len(prompt) < 8 or len(answer) < 8:
                raise CommandError(
                    f'{config["filename"]} contains an ambiguous or incomplete review item #{number}.'
                )
            seen.add(number)
            records.append({'number': number, 'prompt': prompt, 'answer': answer})
        if not records:
            raise CommandError(f'No explicit question/answer pairs found in {config["filename"]}.')
        return {'subject': subject, 'config': config, 'path': path, 'records': records}

    @staticmethod
    def source_file(root, filename):
        direct = root / filename
        if direct.is_file():
            return direct
        matches = list(root.rglob(filename))
        return matches[0] if len(matches) == 1 else direct

    def import_subject(self, report):
        config = report['config']
        document = QuestionDocument.objects.filter(
            workspace='ei', display_title=config['document_title'],
        ).first() or QuestionDocument.objects.filter(
            workspace='ei', title=config['document_title'],
        ).first()
        if document is None:
            raise CommandError(f'EI document is missing: {config["document_title"]}')
        topic_key = f'ei-review:{report["subject"]}'
        topic, _ = QuestionTopic.objects.update_or_create(
            source_id=stable_positive_id(TOPIC_ID_BASE, topic_key),
            defaults={
                'document': document,
                'parent': None,
                'title': '背诵简答',
                'display_title': '背诵简答',
                'normalized_title': topic_key,
                'level': 1,
                'sort_order': 900,
            },
        )
        for record in report['records']:
            key = f'{report["subject"]}:{record["number"]}'
            fingerprint = hashlib.sha256(f'ei-review-pdf:{key}'.encode()).hexdigest()
            Question.objects.update_or_create(
                fingerprint=fingerprint,
                defaults={
                    'uuid': stable_uuid(key),
                    'document': document,
                    'topic': topic,
                    'similarity_topic': topic,
                    'question_order': config['order_base'] + record['number'],
                    'source_label': f'{report["subject"]} · review · {record["number"]}',
                    'display_label': label(record['number'], record['prompt']),
                    'prompt_text': record['prompt'],
                    'latex_text': '',
                    'content_mode': 'markdown',
                    'confidence': 1.0,
                    'is_past_exam': False,
                    'source_category': 'workbook',
                    'record_kind': 'question',
                    'is_practiceable': True,
                    'classification_reason': 'Owner-provided 892 review sheet with explicit answer.',
                    'classification_confidence': 1.0,
                    'answer_markdown': record['answer'],
                    'answer_source': 'provided-reference',
                    'answer_confidence': 1.0,
                    'topic_classification_source': 'source-review-sheet',
                    'topic_classification_confidence': 1.0,
                    'question_type': 'solution',
                    'question_type_source': 'import',
                    'question_type_confidence': 1.0,
                },
            )
        return len(report['records'])
