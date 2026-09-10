"""Import explicitly solved exercises from the supplied Fengkao EI notes."""

import hashlib
import re
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F

from drill.management.commands.import_ei_paired_pdfs import (
    Anchor,
    Command as CropImporter,
    SOLUTION_RE,
    stable_positive_id,
    stable_uuid,
)
from drill.models import Question, QuestionDocument, QuestionTopic


TOPIC_ID_BASE = 892_500_000_000
QUESTION_RE = re.compile(r'^\s*题\s*(?P<number>\d{1,3})\s*[.．、]')
LESSON_RE = re.compile(r'^\s*课时\s*[一二三四五六七八九十\d]+')
SUBSECTION_RE = re.compile(r'^\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*\S')

SOURCES = {
    'honey-signal': {
        'filename': '蜂考信号.pdf',
        'document_title': '892 · 信号与系统',
        'order_base': 310_000,
    },
    'honey-digital': {
        'filename': '蜂考数电.pdf',
        'document_title': '892 · 数字电子技术',
        'order_base': 320_000,
    },
    'honey-analog': {
        'filename': '蜂考模电.pdf',
        'document_title': '892 · 模拟电子技术',
        'order_base': 330_000,
    },
}


class Command(BaseCommand):
    help = 'Import only Fengkao EI exercises with explicit solution boundaries.'

    def add_arguments(self, parser):
        parser.add_argument('source_root', type=Path)
        parser.add_argument('--subjects', default=','.join(SOURCES))
        parser.add_argument('--dpi', type=int, default=150)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        root = options['source_root'].expanduser().resolve()
        if not root.is_dir():
            raise CommandError(f'Not a source directory: {root}')
        if not 100 <= options['dpi'] <= 180:
            raise CommandError('--dpi must be between 100 and 180.')
        subjects = [item.strip() for item in options['subjects'].split(',') if item.strip()]
        unknown = set(subjects) - set(SOURCES)
        if unknown:
            raise CommandError(f'Unknown Fengkao source(s): {", ".join(sorted(unknown))}')

        reports = [self.audit_subject(root, subject) for subject in subjects]
        for report in reports:
            self.stdout.write(
                f'{report["subject"]}: questions={report["question_count"]}, '
                f'explicitly solved={len(report["pairs"])}.'
            )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; no database rows were written.'))
            return
        with transaction.atomic():
            total = sum(self.import_subject(report, options['dpi']) for report in reports)
        self.stdout.write(self.style.SUCCESS(f'Imported or updated {total} solved Fengkao EI questions.'))

    def audit_subject(self, root, subject):
        config = SOURCES[subject]
        path = CropImporter.source_file(root, config['filename'])
        if not path.is_file():
            raise CommandError(f'Missing Fengkao PDF: {config["filename"]}')
        document = pymupdf.open(path)
        try:
            lessons, sections, questions, page_lines = self.find_anchors(document)
            boundaries = sorted(lessons + sections + questions, key=self.anchor_key)
            pairs = []
            for question in questions:
                following = next(
                    (item for item in boundaries if self.anchor_key(item) > self.anchor_key(question)),
                    None,
                )
                solution = self.find_solution(
                    document, page_lines, question, following, len(document),
                )
                # Some dense answer keys place ``答案: D`` and the next
                # question on virtually the same baseline. A full-width crop
                # cannot separate those two records without leaking the next
                # question, so leave that item out of the verified set.
                if (
                    solution is not None
                    and following is not None
                    and solution.page_index == following.page_index
                    and following.y - solution.y < 8
                ):
                    solution = None
                if solution is not None:
                    pairs.append((question, solution))
        finally:
            document.close()
        return {
            'subject': subject,
            'config': config,
            'path': path,
            'question_count': len(questions),
            'boundaries': boundaries,
            'pairs': pairs,
        }

    @staticmethod
    def anchor_key(anchor):
        return anchor.page_index, anchor.y

    @staticmethod
    def find_anchors(document):
        page_lines = {}
        lesson_rows = []
        section_rows = []
        question_rows = []
        for page_index, page in enumerate(document):
            lines = CropImporter.pdf_text_lines(page)
            page_lines[page_index] = lines
            for text, _x, y in lines:
                if LESSON_RE.match(text):
                    lesson_rows.append((
                        page_index, CropImporter.visual_line_top(page, y),
                        re.sub(r'\s+', ' ', text).strip(),
                    ))
                elif SUBSECTION_RE.match(text):
                    section_rows.append((
                        page_index, CropImporter.visual_line_top(page, y),
                        re.sub(r'\s+', ' ', text).strip(),
                    ))
                match = QUESTION_RE.match(text)
                if match:
                    anchor_y = CropImporter.visual_line_top(page, y)
                    anchor_y = Command.after_preceding_solution(
                        page, lines, y, anchor_y,
                    )
                    question_rows.append((
                        page_index, anchor_y,
                        int(match.group('number')),
                    ))
        lessons = [
            Anchor(f'lesson-{index}', index, 0, page, y)
            for index, (page, y, _title) in enumerate(lesson_rows, 1)
        ]
        sections = [
            Anchor(f'section-{index}', 0, 0, page, y)
            for index, (page, y, _title) in enumerate(section_rows, 1)
        ]
        questions = []
        occurrences = {}
        for page, y, number in question_rows:
            preceding = [
                index for index, (lesson_page, lesson_y, _title) in enumerate(lesson_rows, 1)
                if (lesson_page, lesson_y) <= (page, y)
            ]
            if not preceding:
                continue
            lesson_index = preceding[-1]
            occurrence_key = lesson_index, number
            occurrence = occurrences.get(occurrence_key, 0) + 1
            occurrences[occurrence_key] = occurrence
            suffix = f'-{occurrence}' if occurrence > 1 else ''
            questions.append(Anchor(
                f'{lesson_index}-{number}{suffix}', lesson_index, number, page, y,
            ))
        return lessons, sections, questions, page_lines

    @staticmethod
    def after_preceding_solution(page, lines, question_y, anchor_y):
        """Do not include a tightly packed previous answer in a question crop.

        Some Fengkao pages place ``答案: D`` immediately above the next cyan
        question row. Their embedded font gives the next ``题`` word an
        unusually tall bounding box, so the normal top padding overlaps the
        answer. Clamp the question start below that answer's real glyph box.
        """
        nearby_solutions = [
            y for text, _x, y in lines
            if SOLUTION_RE.match(text) and 0 <= question_y - y <= 8.0
        ]
        if not nearby_solutions:
            return anchor_y
        solution_y = max(nearby_solutions)
        solution_bottoms = [
            y1 for _x0, y0, _x1, y1, _text, _block, _line, _word
            in page.get_text('words')
            if abs(y0 - solution_y) <= 1.5
        ]
        if not solution_bottoms:
            return anchor_y
        return max(anchor_y, max(solution_bottoms) + 2.0)

    @staticmethod
    def find_solution(document, page_lines, question, following, page_count):
        last_page = following.page_index if following else min(question.page_index + 3, page_count - 1)
        for page_index in range(question.page_index, last_page + 1):
            for text, _x, y in page_lines[page_index]:
                if (
                    page_index < question.page_index
                    or (
                        page_index == question.page_index
                        and y <= question.y + 3.1
                    )
                ):
                    continue
                if following and (
                    page_index > following.page_index
                    or (
                        page_index == following.page_index
                        and y >= following.y + 3.1
                    )
                ):
                    return None
                if SOLUTION_RE.match(text):
                    return Anchor(
                        question.label, question.chapter, question.number,
                        page_index,
                        CropImporter.visual_line_top(document[page_index], y),
                    )
        return None

    def import_subject(self, report, dpi):
        config = report['config']
        document = QuestionDocument.objects.filter(
            workspace='ei', display_title=config['document_title'],
        ).first() or QuestionDocument.objects.filter(
            workspace='ei', title=config['document_title'],
        ).first()
        if document is None:
            raise CommandError(f'EI document is missing: {config["document_title"]}')

        Question.objects.filter(
            document=document,
            source_label__regex=(
                rf'^{re.escape(report["subject"])} · \d+-\d+(?:-\d+)?$'
            ),
        ).update(is_practiceable=False)
        # Move the previous batch out of the target order range first. The
        # verified set can shrink when a structural crop boundary is improved;
        # updating rows directly would otherwise collide with a later stale
        # row before that row is processed.
        Question.objects.filter(
            document=document,
            source_label__startswith=f'{report["subject"]} · ',
            question_order__lt=10_000_000,
        ).update(question_order=F('question_order') + 10_000_000)
        source = pymupdf.open(report['path'])
        cropper = CropImporter()
        try:
            topic_cache = {}
            for order, (question_anchor, solution_anchor) in enumerate(report['pairs'], 1):
                topic = topic_cache.get(question_anchor.chapter)
                if topic is None:
                    topic = self.topic_for(
                        document, report['subject'], question_anchor.chapter,
                    )
                    topic_cache[question_anchor.chapter] = topic
                key = f'{report["subject"]}:{question_anchor.label}'
                fingerprint = hashlib.sha256(f'ei-fengkao:{key}'.encode()).hexdigest()
                question, _ = Question.objects.update_or_create(
                    fingerprint=fingerprint,
                    defaults={
                        'uuid': stable_uuid(key),
                        'document': document,
                        'topic': topic,
                        'similarity_topic': topic,
                        'question_order': (
                            config['order_base']
                            + question_anchor.page_index * 1_000
                            + round(question_anchor.y)
                        ),
                        'source_label': f'{report["subject"]} · {question_anchor.label}',
                        'display_label': f'蜂考 · 课时 {question_anchor.chapter} · 题 {question_anchor.number}',
                        'prompt_text': '',
                        'latex_text': '',
                        'content_mode': 'image',
                        'confidence': 1.0,
                        'is_past_exam': False,
                        'source_category': 'workbook',
                        'record_kind': 'question',
                        'is_practiceable': True,
                        'classification_reason': 'Fengkao note with an explicit solution boundary.',
                        'classification_confidence': 1.0,
                    },
                )
                cropper.store_segment_assets(
                    question, source, question_anchor,
                    report['boundaries'] + [solution_anchor], dpi,
                    'question_crop', report['subject'], question_anchor.label,
                )
                cropper.store_segment_assets(
                    question, source, solution_anchor,
                    report['boundaries'], dpi,
                    'answer_crop', report['subject'], question_anchor.label,
                )
        finally:
            source.close()
        return len(report['pairs'])

    @staticmethod
    def topic_for(document, subject, lesson):
        key = f'ei-fengkao:{subject}:{lesson}'
        title = f'蜂考 · 课时 {lesson}'
        return QuestionTopic.objects.update_or_create(
            source_id=stable_positive_id(TOPIC_ID_BASE, key),
            defaults={
                'document': document,
                'parent': None,
                'title': title,
                'display_title': title,
                'normalized_title': key,
                'level': 1,
                'sort_order': 1_000 + lesson,
            },
        )[0]
