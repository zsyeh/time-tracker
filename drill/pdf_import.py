"""Structured import helpers for the supplied single-variable differentiation PDF.

The source document contains reliable PDF bookmarks and vector formula glyphs.
Bookmarks provide the knowledge hierarchy; conservative provenance-labelled lines
provide question boundaries.  Rendering remains the canonical representation so
imperfect PDF Unicode mappings never become trusted TeX.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .asset_rerender import FormulaAwareCropAdjuster
from .cleaning import classify_source, clean_topic_title


CONTENT_LEFT = 64.0
CONTENT_RIGHT = 532.0
CONTENT_TOP = 40.0
CONTENT_BOTTOM = 790.0
HEADING_DESTINATION_OFFSET = 22.0
COLLECTOR_ATTRIBUTION = 'Question bank collected and organized by Bilibili creator cxy (澄潇宇).'
SOURCE_PREFIX_RE = re.compile(
    r'^\s*(?:[\U0001F300-\U0001FAFF]\s*)*'
    r'(?:(?:[A-Za-z]{1,3}|[ivxlcdmIVXLCDM]+|\d+)\s*\)'
    r'|\(\s*(?:\d+|[A-Za-z]{1,3}|[ivxlcdmIVXLCDM]+)\s*\))'
)


@dataclass(frozen=True)
class PdfLine:
    page_index: int
    x0: float
    y0: float
    y1: float
    text: str


@dataclass(frozen=True)
class ParsedTopic:
    sort_order: int
    level: int
    title: str
    display_title: str
    normalized_title: str
    parent_order: int | None
    page_index: int
    y: float


@dataclass(frozen=True)
class CropSegment:
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class ParsedQuestion:
    question_order: int
    source_label: str
    topic_order: int | None
    prompt_text: str
    segments: tuple[CropSegment, ...]


@dataclass(frozen=True)
class ParsedQuestionDocument:
    path: Path
    sha256: str
    page_count: int
    title: str
    author: str
    attribution: str
    topics: tuple[ParsedTopic, ...]
    questions: tuple[ParsedQuestion, ...]


def stable_source_id(*parts: object) -> int:
    digest = hashlib.sha256('\x1f'.join(str(part) for part in parts).encode('utf-8')).digest()
    return int.from_bytes(digest[:8], 'big') & ((1 << 63) - 1) or 1


def stable_question_uuid(fingerprint: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f'https://drill.ehzsy.site/question/{fingerprint}')


def normalize_topic_key(value: str) -> str:
    value = clean_topic_title(value).casefold()
    return re.sub(r'[\W_]+', '', value, flags=re.UNICODE)


def iter_pdf_lines(document: pymupdf.Document, page_index: int):
    page = document[page_index]
    for block in page.get_text('dict', sort=True)['blocks']:
        if block.get('type') != 0:
            continue
        for line in block['lines']:
            text = ''.join(span['text'] for span in line['spans']).strip()
            if not text:
                continue
            x0, y0, _x1, y1 = line['bbox']
            yield PdfLine(page_index, x0, y0, y1, text)


def is_question_source_line(line: PdfLine) -> bool:
    if line.x0 > 90 or not (CONTENT_TOP <= line.y0 <= CONTENT_BOTTOM):
        return False
    if not SOURCE_PREFIX_RE.search(line.text):
        return False
    return classify_source(line.text).category != 'unclassified'


def extract_topics(document: pymupdf.Document) -> list[ParsedTopic]:
    topics = []
    parents: dict[int, int] = {}
    for sort_order, item in enumerate(document.get_toc(simple=False), 1):
        level, title, _page_number, destination = item
        page_index = int(destination.get('page', -1))
        point = destination.get('to')
        if page_index < 0 or point is None:
            continue
        parent_order = parents.get(level - 1)
        for deeper_level in [value for value in parents if value >= level]:
            parents.pop(deeper_level, None)
        parents[level] = sort_order
        display_title = clean_topic_title(title)
        topics.append(ParsedTopic(
            sort_order=sort_order,
            level=int(level),
            title=title,
            display_title=display_title,
            normalized_title=normalize_topic_key(display_title),
            parent_order=parent_order,
            page_index=page_index,
            y=max(CONTENT_TOP, float(point.y) + HEADING_DESTINATION_OFFSET),
        ))
    if not topics:
        raise ValueError('The PDF has no usable bookmark hierarchy.')
    return topics


def _content_bottom(document: pymupdf.Document, page_index: int) -> float:
    return min(CONTENT_BOTTOM, document[page_index].rect.height - 35.0)


def _question_segments(
    document: pymupdf.Document,
    start: tuple[int, float],
    end: tuple[int, float] | None,
) -> tuple[CropSegment, ...]:
    start_page, start_y = start
    end_page, end_y = end if end is not None else (start_page, _content_bottom(document, start_page))
    segments = []
    for page_index in range(start_page, end_page + 1):
        y0 = max(CONTENT_TOP, start_y) if page_index == start_page else CONTENT_TOP
        y1 = (
            min(_content_bottom(document, page_index), end_y)
            if page_index == end_page
            else _content_bottom(document, page_index)
        )
        if y1 - y0 >= 18:
            segments.append(CropSegment(
                page_index=page_index,
                x0=CONTENT_LEFT,
                y0=y0,
                x1=min(CONTENT_RIGHT, document[page_index].rect.width - 18.0),
                y1=y1,
            ))
    if not segments:
        raise ValueError(f'Question at page {start_page + 1}, y={start_y:.1f} has no renderable area.')
    return tuple(segments)


def _segment_text(document: pymupdf.Document, segments: tuple[CropSegment, ...]) -> str:
    parts = []
    for segment in segments:
        rect = pymupdf.Rect(segment.x0, segment.y0, segment.x1, segment.y1)
        text = document[segment.page_index].get_text('text', clip=rect, sort=True).strip()
        if text:
            parts.append(text)
    return '\n'.join(parts)


def parse_question_pdf(path: Path | str) -> ParsedQuestionDocument:
    source_path = Path(path).expanduser().resolve()
    raw_pdf = source_path.read_bytes()
    sha256 = hashlib.sha256(raw_pdf).hexdigest()
    with pymupdf.open(stream=raw_pdf, filetype='pdf') as document:
        topics = extract_topics(document)
        topic_events = {
            (topic.page_index, topic.y, 0, topic.sort_order): topic
            for topic in topics
        }
        source_lines = [
            line
            for page_index in range(2, document.page_count)
            for line in iter_pdf_lines(document, page_index)
            if is_question_source_line(line)
        ]
        if not source_lines:
            raise ValueError('No conservative provenance-labelled questions were found.')

        # This PDF uses vector page decorations near the content boundary.
        # Text blocks retain formula extents without mistaking those lines for math.
        crop_adjuster = FormulaAwareCropAdjuster(document, include_drawings=False)
        safe_question_starts = {
            index: (
                line.page_index,
                max(CONTENT_TOP, crop_adjuster.boundary(line.page_index, line.y0)),
            )
            for index, line in enumerate(source_lines, 1)
        }

        question_events = {
            (line.page_index, line.y0, 1, index): line
            for index, line in enumerate(source_lines, 1)
        }
        events = sorted([*topic_events, *question_events])
        active_topics: dict[int, ParsedTopic] = {}
        question_topics: dict[int, int | None] = {}
        for event in events:
            if event[2] == 0:
                topic = topic_events[event]
                for deeper_level in [value for value in active_topics if value >= topic.level]:
                    active_topics.pop(deeper_level, None)
                active_topics[topic.level] = topic
            else:
                question_topics[event[3]] = (
                    active_topics[max(active_topics)].sort_order if active_topics else None
                )

        boundaries = sorted(
            [(topic.page_index, topic.y) for topic in topics]
            + list(safe_question_starts.values())
        )
        questions = []
        for index, line in enumerate(source_lines, 1):
            start = safe_question_starts[index]
            end = next((boundary for boundary in boundaries if boundary > start), None)
            segments = _question_segments(document, start, end)
            questions.append(ParsedQuestion(
                question_order=index,
                source_label=line.text,
                topic_order=question_topics[index],
                prompt_text=_segment_text(document, segments),
                segments=segments,
            ))

        metadata = document.metadata or {}
        return ParsedQuestionDocument(
            path=source_path,
            sha256=sha256,
            page_count=document.page_count,
            title='一元微分',
            author=(metadata.get('author') or '').strip(),
            attribution=COLLECTOR_ATTRIBUTION,
            topics=tuple(topics),
            questions=tuple(questions),
        )


def render_segment_png(
    document: pymupdf.Document,
    segment: CropSegment,
    dpi: int,
) -> tuple[bytes, int, int]:
    scale = dpi / 72.0
    pixmap = document[segment.page_index].get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        clip=pymupdf.Rect(segment.x0, segment.y0, segment.x1, segment.y1),
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    return pixmap.tobytes('png'), pixmap.width, pixmap.height
