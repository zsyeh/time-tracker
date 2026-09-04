"""Import only syllabus-scoped, question/answer-paired EI PDF exercises.

The supplied workbooks keep mathematical content as PDF glyphs or raster scans.
Rather than trusting lossy OCR for the visible problem/answer, this command uses
OCR only to identify ``chapter-question`` anchors, then stores the matching
source crops losslessly as authenticated QuestionAsset rows.
"""

import hashlib
import os
import re
import subprocess
import tempfile
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset, QuestionDocument, QuestionTopic


SOURCE_ID_BASE = 892_300_000
TOPIC_ID_BASE = 892_300_000_000
ASSET_ID_BASE = 892_300_000_000_000
LABEL_RE = re.compile(
    # Signal workbooks use ``2-5``; the analog/digital books use ``2.5``
    # and occasionally prefix a problem with ``P``.  Keep the strict end
    # delimiter so textbook section labels such as ``1.1.3`` are not mistaken
    # for an exercise.
    r'^\s*(?:[\[【(（]\s*)?(?:习题\s*)?(?:题\s*)?(?:P\s*)?(?P<chapter>[1-9]\d?)\s*(?:[-—–一.]|\s+)\s*(?P<number>\d{1,3})(?:\s|题|[、:：\]】)）]|$)',
)
SOLUTION_RE = re.compile(r'^\s*(?:解|答)\s*[：:]')


PAIR_SOURCES = {
    'signal': {
        'document_title': '892 · 信号与系统',
        'question_file': '信号课后题做题本.pdf',
        'answer_file': '信号课后指导与答案.pdf',
        'allowed_chapters': {1, 2, 3, 4, 5, 7, 8},
    },
    'analog': {
        'document_title': '892 · 模拟电子技术',
        'question_file': '模电课后题做题本.pdf',
        'answer_file': '模电课后指导与答案.pdf',
        'allowed_chapters': {1, 2, 3, 4, 5},
    },
    'digital': {
        'document_title': '892 · 数字电子技术',
        'question_file': '数电课后题做题本.pdf',
        'answer_file': '数电课后指导与答案.pdf',
        'allowed_chapters': {1, 2, 3, 4, 5, 6},
    },
    'communication': {
        'document_title': '892 · 通信原理',
        'question_file': '通信课后题与答案.pdf',
        'answer_file': '通信课后题与答案.pdf',
        'allowed_chapters': {1, 2, 3, 4, 5},
        'combined_solution_pdf': True,
    },
}


@dataclass(frozen=True)
class Anchor:
    label: str
    chapter: int
    number: int
    page_index: int
    y: float


def stable_positive_id(prefix, value):
    digest = hashlib.sha256(value.encode('utf-8')).digest()
    return prefix + int.from_bytes(digest[:6], 'big')


def stable_uuid(value):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'https://ei.ehzsy.site/pdf-pairs/{value}')


def canonical_label(chapter, number):
    return f'{chapter}-{number}'


class Command(BaseCommand):
    help = 'Import 892 in-syllabus workbook/answer PDF pairs into the EI workspace.'

    def add_arguments(self, parser):
        parser.add_argument('source_root', type=Path)
        parser.add_argument('--subjects', default=','.join(PAIR_SOURCES), help='Comma-separated import source names.')
        parser.add_argument('--dpi', type=int, default=150)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0, help='Maximum matched pairs per subject, for audit runs.')
        parser.add_argument('--min-match-rate', type=float, default=0.70)
        parser.add_argument('--ocr-workers', type=int, default=1, help='Bounded local OCR workers (1-4; default 1 for small VPSes).')

    def handle(self, *args, **options):
        root = options['source_root'].expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'Not a source directory: {root}')
        dpi = options['dpi']
        if dpi < 100 or dpi > 200:
            raise CommandError('--dpi must be between 100 and 200.')
        self.ocr_workers = options['ocr_workers']
        if self.ocr_workers < 1 or self.ocr_workers > 4:
            raise CommandError('--ocr-workers must be between 1 and 4.')
        subjects = [item.strip() for item in options['subjects'].split(',') if item.strip()]
        unknown = set(subjects) - set(PAIR_SOURCES)
        if unknown:
            raise CommandError(f'Unknown subjects: {", ".join(sorted(unknown))}')

        reports = []
        for subject in subjects:
            report = self.audit_subject(
                subject, root, dpi, options['min_match_rate'], options['limit'],
            )
            reports.append(report)
            self.stdout.write(
                f'{subject}: question anchors={report["question_count"]}, '
                f'answer anchors={report["answer_count"]}, paired={len(report["pairs"])}.'
            )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; no database rows were written.'))
            return

        with transaction.atomic():
            total = 0
            for report in reports:
                total += self.import_subject(report, dpi)
        self.stdout.write(self.style.SUCCESS(f'Imported or updated {total} EI question/answer pairs.'))

    def audit_subject(self, subject, root, dpi, min_match_rate, limit):
        config = PAIR_SOURCES[subject]
        question_path = self.source_file(root, config['question_file'])
        answer_path = self.source_file(root, config['answer_file'])
        if not question_path.is_file() or not answer_path.is_file():
            raise CommandError(f'Missing paired PDFs for {subject}: {question_path.name}, {answer_path.name}')
        question_pdf = pymupdf.open(question_path)
        answer_pdf = pymupdf.open(answer_path)
        try:
            question_anchors = self.find_anchors(question_pdf, dpi)
            if config.get('combined_solution_pdf'):
                answer_anchors = self.find_solution_anchors(question_pdf, question_anchors)
            else:
                answer_anchors = self.find_anchors(answer_pdf, dpi)
        finally:
            question_pdf.close()
            answer_pdf.close()
        allowed = config['allowed_chapters']
        questions = {item.label: item for item in question_anchors if item.chapter in allowed}
        answers = {item.label: item for item in answer_anchors if item.chapter in allowed}
        pairs = [(label, questions[label], answers[label]) for label in questions.keys() & answers.keys()]
        pairs.sort(key=lambda item: (item[1].chapter, item[1].number))
        if limit:
            pairs = pairs[:limit]
        denominator = max(1, min(len(questions), len(answers)))
        rate = len(pairs) / denominator
        if rate < min_match_rate:
            raise CommandError(
                f'{subject} pairing rate is {rate:.1%} ({len(pairs)}/{denominator}), below {min_match_rate:.0%}; '
                'refusing to import unmatched material.'
            )
        return {
            'subject': subject,
            'config': config,
            'question_path': question_path,
            'answer_path': answer_path,
            'question_count': len(questions),
            'answer_count': len(answers),
            # Keep every anchor for clipping.  Pair eligibility is limited to
            # the syllabus, but an excluded neighbouring chapter must still
            # terminate the preceding crop.
            'all_question_anchors': question_anchors,
            'all_answer_anchors': question_anchors if config.get('combined_solution_pdf') else answer_anchors,
            'pairs': pairs,
        }

    @staticmethod
    def source_file(root, filename):
        """Accept either the extracted archive root or its inner directory."""
        direct = root / filename
        if direct.is_file():
            return direct
        matches = list(root.rglob(filename))
        if len(matches) == 1:
            return matches[0]
        return direct

    def find_anchors(self, document, dpi):
        anchors = []
        with tempfile.TemporaryDirectory(prefix='ei-pdf-ocr-') as temporary:
            temp_root = Path(temporary)
            page_lines = {}
            ocr_jobs = []
            for page_index, page in enumerate(document):
                lines = self.pdf_text_lines(page)
                if not any(LABEL_RE.match(text) for text, _x, _y in lines):
                    output = temp_root / f'{page_index:04d}.png'
                    scale = min(dpi, 100) / 72
                    clip = pymupdf.Rect(0, 0, page.rect.width * 0.32, page.rect.height)
                    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False).save(output)
                    ocr_jobs.append((page_index, output, scale))
                else:
                    page_lines[page_index] = lines
            if ocr_jobs:
                with ThreadPoolExecutor(max_workers=self.ocr_workers) as executor:
                    for page_index, lines in executor.map(self.ocr_image_lines, ocr_jobs):
                        page_lines[page_index] = lines
            for page_index, page in enumerate(document):
                lines = page_lines[page_index]
                seen = set()
                page_width = page.rect.width
                for text, x, y in lines:
                    match = LABEL_RE.match(text)
                    if not match or x > page_width * 0.42:
                        continue
                    chapter = int(match.group('chapter'))
                    number = int(match.group('number'))
                    label = canonical_label(chapter, number)
                    if label in seen:
                        continue
                    seen.add(label)
                    anchors.append(Anchor(label, chapter, number, page_index, max(0, y - 3)))
        return anchors

    def find_solution_anchors(self, document, question_anchors):
        """Locate the explicit 解:/答: that belongs to each in-document exercise."""
        by_page = {}
        for page_index, page in enumerate(document):
            by_page[page_index] = self.pdf_text_lines(page)
        ordered = sorted(question_anchors, key=lambda item: (item.page_index, item.y))
        solutions = []
        for index, question in enumerate(ordered):
            following = ordered[index + 1] if index + 1 < len(ordered) else None
            found = None
            for page_index in range(question.page_index, (following.page_index if following else len(document) - 1) + 1):
                for text, _x, y in by_page[page_index]:
                    if page_index == question.page_index and y <= question.y:
                        continue
                    if following and page_index == following.page_index and y >= following.y:
                        break
                    if SOLUTION_RE.match(text):
                        found = Anchor(question.label, question.chapter, question.number, page_index, max(0, y - 3))
                        break
                if found:
                    break
            if found:
                solutions.append(found)
        return solutions

    @staticmethod
    def pdf_text_lines(page):
        grouped = defaultdict(list)
        for x0, y0, _x1, _y1, text, block, line, _word in page.get_text('words'):
            grouped[(block, line)].append((x0, y0, text))
        lines = []
        for words in grouped.values():
            words.sort()
            lines.append((' '.join(item[2] for item in words), words[0][0], words[0][1]))
        return lines

    @staticmethod
    def ocr_image_lines(job):
        _page_index, output, scale = job
        result = subprocess.run(
            ['tesseract', str(output), 'stdout', '-l', 'eng', '--psm', '11', 'tsv'],
            check=True, capture_output=True, text=True,
            env={**os.environ, 'OMP_THREAD_LIMIT': '1'},
        )
        grouped = defaultdict(list)
        for row in result.stdout.splitlines()[1:]:
            fields = row.split('\t')
            if len(fields) != 12 or not fields[11].strip():
                continue
            try:
                block, paragraph, line = (int(fields[index]) for index in (2, 3, 4))
                left, top = int(fields[6]), int(fields[7])
            except ValueError:
                continue
            grouped[(block, paragraph, line)].append((left, top, fields[11].strip()))
        lines = []
        for words in grouped.values():
            words.sort()
            lines.append((' '.join(item[2] for item in words), words[0][0] / scale, words[0][1] / scale))
        return _page_index, lines

    def import_subject(self, report, dpi):
        config = report['config']
        document = QuestionDocument.objects.filter(
            workspace='ei', display_title=config['document_title'],
        ).first() or QuestionDocument.objects.filter(
            workspace='ei', title=config['document_title'],
        ).first()
        if document is None:
            raise CommandError(f'EI document is missing: {config["document_title"]}')
        question_pdf = pymupdf.open(report['question_path'])
        answer_pdf = pymupdf.open(report['answer_path'])
        try:
            total = 0
            topic_cache = {}
            for index, (label, question_anchor, answer_anchor) in enumerate(report['pairs'], 1):
                topic = topic_cache.get(question_anchor.chapter)
                if topic is None:
                    topic = self.topic_for(document, report['subject'], question_anchor.chapter)
                    topic_cache[question_anchor.chapter] = topic
                fingerprint = hashlib.sha256(
                    f'ei-paired-pdf:{report["subject"]}:{label}'.encode(),
                ).hexdigest()
                question, _ = Question.objects.update_or_create(
                    fingerprint=fingerprint,
                    defaults={
                        'uuid': stable_uuid(f'{report["subject"]}:{label}'),
                        'document': document,
                        'topic': topic,
                        'similarity_topic': topic,
                        'question_order': self.paired_order(report['subject'], question_anchor.chapter, question_anchor.number),
                        'source_label': f'{report["subject"]} · {label}',
                        'display_label': f'课后题 {label}',
                        'prompt_text': '',
                        'latex_text': '',
                        'content_mode': 'image',
                        'confidence': 1.0,
                        'is_past_exam': False,
                        'source_category': 'workbook',
                        'record_kind': 'question',
                        'is_practiceable': True,
                        'classification_reason': 'Syllabus-scoped paired workbook PDF.',
                        'classification_confidence': 1.0,
                    },
                )
                self.store_segment_assets(
                    question, question_pdf, question_anchor,
                    report['all_question_anchors'], dpi, 'question_crop', report['subject'], label,
                )
                self.store_segment_assets(
                    question, answer_pdf, answer_anchor,
                    report['all_answer_anchors'], dpi, 'answer_crop', report['subject'], label,
                )
                total += 1
        finally:
            question_pdf.close()
            answer_pdf.close()
        return total

    def topic_for(self, document, subject, chapter):
        key = f'ei-pdf-pair:{subject}:{chapter}'
        title = f'课后题 · 第 {chapter} 章'
        return QuestionTopic.objects.update_or_create(
            source_id=stable_positive_id(TOPIC_ID_BASE, key),
            defaults={
                'document': document,
                'parent': None,
                'title': title,
                'display_title': title,
                'normalized_title': key,
                'level': 1,
                'sort_order': 800 + chapter,
            },
        )[0]

    @staticmethod
    def paired_order(subject, chapter, number):
        subject_order = {'signal': 1, 'analog': 2, 'digital': 3, 'communication': 4}[subject]
        return 100_000 + subject_order * 10_000 + chapter * 100 + number

    def store_segment_assets(self, question, document, anchor, anchors, dpi, asset_type, subject, label):
        ordered = sorted(anchors, key=lambda item: (item.page_index, item.y))
        current_key = (anchor.page_index, anchor.y)
        next_anchor = next((item for item in ordered if (item.page_index, item.y) > current_key), None)
        end_page = next_anchor.page_index if next_anchor else anchor.page_index
        end_y = next_anchor.y if next_anchor and next_anchor.page_index == anchor.page_index else None
        existing_ids = []
        position = 0
        for page_index in range(anchor.page_index, end_page + 1):
            page = document[page_index]
            y0 = anchor.y if page_index == anchor.page_index else 0
            y1 = end_y if page_index == end_page and end_y is not None else page.rect.height
            if y1 - y0 < 8:
                continue
            rect = pymupdf.Rect(0, y0, page.rect.width, y1)
            scale = dpi / 72
            image_data = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).tobytes('png')
            digest = hashlib.sha256(image_data).hexdigest()
            source_key = f'ei-pdf-pair:{subject}:{label}:{asset_type}:{position}'
            asset, _ = QuestionAsset.objects.update_or_create(
                source_id=stable_positive_id(ASSET_ID_BASE, source_key),
                defaults={
                    'question': question,
                    'position': position,
                    'asset_type': asset_type,
                    'sha256': digest,
                    'mime_type': 'image/png',
                    'image_data': image_data,
                    'width': round(rect.width * scale),
                    'height': round(rect.height * scale),
                    'source_page_index': page_index,
                    'source_x0': rect.x0,
                    'source_y0': rect.y0,
                    'source_x1': rect.x1,
                    'source_y1': rect.y1,
                    'render_dpi': dpi,
                },
            )
            existing_ids.append(asset.pk)
            position += 1
        QuestionAsset.objects.filter(question=question, asset_type=asset_type).exclude(pk__in=existing_ids).delete()
