"""Deterministic bookmark/text-layer index for the A4 linear selected book.

Whole original pages are shared by their question anchors. Formula text is not
reconstructed and no OCR/LLM is used. A bookmark alone is never sufficient:
every numbered bookmark must agree with exactly one visible PDF text anchor.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re

import pymupdf


STRATEGY = 'linear-selected-full-pages-v1'
RELATION = 'selected_question_book'
TITLE = '数二线代臻选题 · A4留白'
CHAPTERS = ('行列式', '矩阵', '向量', '方程组', '特征值与特征向量', '二次型')
QUESTION = re.compile(r'^#(?P<number>\d{1,4})(?:\s*[·•]\s*(?P<source>.+))?$')
ANCHOR = re.compile(r'^#(\d{1,4})$')
CHAPTER_PREFIX = re.compile(r'^[一二三四五六七八九十]+[、.．]\s*')


@dataclass(frozen=True)
class SelectedTopic:
    order: int
    title: str
    level: int
    parent_order: int | None


@dataclass(frozen=True)
class SelectedQuestion:
    number: int
    source: str
    topic_order: int
    chapter: str
    page_index: int
    anchor_bbox: tuple[float, float, float, float]
    y: float
    question_type: str


@dataclass(frozen=True)
class SelectedBook:
    path: Path
    sha256: str
    page_count: int
    topics: tuple[SelectedTopic, ...]
    questions: tuple[SelectedQuestion, ...]

    def manifest(self):
        return {
            'schema_version': 1, 'parser': STRATEGY,
            'file': self.path.name, 'sha256': self.sha256,
            'page_count': self.page_count, 'question_count': len(self.questions),
            'question_page_count': len({q.page_index for q in self.questions}),
            'by_chapter': dict(Counter(q.chapter for q in self.questions)),
            'topics': [asdict(topic) for topic in self.topics],
            'questions': [asdict(question) for question in self.questions],
            'image_policy': 'full original page, shared across question anchors',
            'answer_policy': 'no answer PDF supplied; do not infer or attach answers',
            'ocr_pages': [],
        }


def parse_selected_book(path):
    path = Path(path)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    topics = []; pending = []; stack = []; chapter = None; numbers = set()
    with pymupdf.open(path) as pdf:
        for level, title, page in pdf.get_toc():
            title = title.strip()
            match = QUESTION.fullmatch(title)
            if level == 1 and not match:
                name = CHAPTER_PREFIX.sub('', title)
                chapter = title if name in CHAPTERS else None
                stack = []
            if chapter is None:
                if match:
                    raise ValueError(f'Question outside recognized chapter: {title}')
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            if match:
                number = int(match['number'])
                if not stack or number in numbers or not 1 <= page <= len(pdf):
                    raise ValueError(f'Invalid/duplicate question bookmark: {title}')
                numbers.add(number)
                pending.append((number, match['source'] or title, stack[-1][1], chapter, page - 1))
            else:
                topic = SelectedTopic(len(topics) + 1, title, level, stack[-1][1] if stack else None)
                topics.append(topic)
                stack.append((level, topic.order))
        if not pending:
            raise ValueError('No reviewed-layout question bookmarks found')
        if [item[0] for item in pending] != sorted(numbers):
            raise ValueError('Question bookmarks are not in increasing source order')

        expected = {}
        for item in pending:
            expected.setdefault(item[4], set()).add(item[0])
        locations = {}; types = {}
        for page_index, expected_numbers in expected.items():
            page = pdf[page_index]
            found = {}
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    text = ''.join(span['text'] for span in line['spans']).strip()
                    match = ANCHOR.fullmatch(text)
                    if not match:
                        continue
                    number = int(match[1]); bbox = tuple(line['bbox'])
                    if number in found or not (0 <= bbox[0] < bbox[2] <= page.rect.width
                                               and 0 <= bbox[1] < bbox[3] <= page.rect.height):
                        raise ValueError(f'Invalid anchor on PDF page {page_index + 1}')
                    found[number] = bbox
            if set(found) != expected_numbers:
                raise ValueError(f'Bookmark/text anchor mismatch on PDF page {page_index + 1}: '
                                 f'expected={sorted(expected_numbers)}, found={sorted(found)}')
            ordered = sorted(found, key=lambda n: found[n][1])
            if ordered != sorted(expected_numbers):
                raise ValueError(f'Ambiguous question layout on PDF page {page_index + 1}')
            for position, number in enumerate(ordered):
                bbox = found[number]
                locations[number] = (bbox, bbox[1] / page.rect.height)
                bottom = found[ordered[position + 1]][1] if position + 1 < len(ordered) else page.rect.height
                text = page.get_text(clip=pymupdf.Rect(0, bbox[1], page.rect.width, bottom))
                choices = set(re.findall(r'(?m)^\s*[（(]?([A-D])[)）.．、]', text))
                types[number] = ('single_choice' if choices == set('ABCD') else
                                 'fill_blank' if re.search(r'_{3,}|[—－]{3,}', text) else
                                 'solution' if re.search(r'[（(](?:[Ii]{1,3}|[123])[)）]', text) else 'unknown')
        questions = tuple(SelectedQuestion(number, source, topic_order, section, page_index,
                                          locations[number][0], locations[number][1], types[number])
                          for number, source, topic_order, section, page_index in pending)
        return SelectedBook(path, sha256, len(pdf), tuple(topics), questions)
