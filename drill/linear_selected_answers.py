"""Reviewed-layout parser: ordered TOC, chapter and source must all agree.

Both PDFs remain authoritative. Full-width regions avoid clipping tall matrices
or diagrams. Answer boundaries use *all* headings, including non-question ones.
"""
from collections import Counter
import hashlib
import re
import unicodedata

import pymupdf

from .linear_selected import CHAPTERS, parse_selected_book


def normalize(value):
    value = unicodedata.normalize('NFKC', value).replace('🐙', '张宇')
    return re.sub(r'\s+|>>', '', value).replace('第一套套', '第一套').replace('张宇八套卷', '张宇八套')


def heading_title(value):
    return re.sub(r'^(?:[A-Ga-z]+[.)、]|\d+[.、]|\([a-z0-9]+\))', '', normalize(value))


def build_manifest(question_path, answer_path):
    book = parse_selected_book(question_path)
    result = {'schema_version': 1, 'question_sha256': book.sha256,
              'answer_sha256': hashlib.sha256(answer_path.read_bytes()).hexdigest(),
              'policy': 'individual questions and answers; full-width bbox; no OCR',
              'questions': [], 'review': []}
    with pymupdf.open(answer_path) as answers, pymupdf.open(question_path) as questions:
        toc = answers.get_toc(False)
        headings = []; leaves = []; chapter = None
        for index, (level, title, page_number, dest) in enumerate(toc):
            page_index = page_number - 1
            page = answers[page_index]
            if level == 2:
                chapter = heading_title(title)
            # Validate the actual visible heading, not merely its bookmark.
            expected = normalize(title)
            candidates = [line['bbox'] for block in page.get_text('dict')['blocks']
                          for line in block.get('lines', [])
                          if normalize(''.join(s['text'] for s in line['spans'])) == expected]
            if not candidates:
                raise ValueError(f'Answer heading not found: page {page_number}, {title}')
            y_hint = dest.get('to', pymupdf.Point(0, 0)).y
            bbox = min(candidates, key=lambda b: abs(b[1] - y_hint))
            if abs(bbox[1] - y_hint) > 35:
                raise ValueError(f'Answer heading destination mismatch: {title}')
            heading = {'page': page_index, 'y': bbox[1], 'title': title, 'chapter': chapter}
            headings.append(heading)
            if (index + 1 == len(toc) or toc[index + 1][0] <= level) and chapter in CHAPTERS:
                leaves.append((index, heading))
        if len(leaves) != len(book.questions):
            raise ValueError(f'Question/answer count mismatch: {len(book.questions)}/{len(leaves)}')
        if any((b['page'], b['y']) < (a['page'], a['y']) for a, b in zip(headings, headings[1:])):
            raise ValueError('Answer headings are not ordered geometrically')
        by_page = {}
        for q in book.questions:
            by_page.setdefault(q.page_index, []).append(q)
        for q, (index, answer) in zip(book.questions, leaves):
            if (normalize(q.source) != heading_title(answer['title']) or
                    heading_title(q.chapter) != answer['chapter']):
                # Chinese chapter numbering is removed separately.
                chapter = re.sub(r'^[一二三四五六七八九十]+[、.]', '', normalize(q.chapter))
                if normalize(q.source) != heading_title(answer['title']) or chapter != answer['chapter']:
                    raise ValueError(f'Question/answer source mismatch at #{q.number:03d}: {q.source} / {answer}')
            page = questions[q.page_index]
            siblings = by_page[q.page_index]
            pos = siblings.index(q)
            # Template header box starts 7.75 pt above its text; retain it all.
            top = max(0, q.anchor_bbox[1] - 14)
            bottom = siblings[pos + 1].anchor_bbox[1] - 14 if pos + 1 < len(siblings) else page.rect.height - 44
            qr = {'page': q.page_index, 'bbox': [0, top, page.rect.width, bottom]}
            following = headings[index + 1] if index + 1 < len(headings) else None
            end_page = following['page'] if following else len(answers) - 1
            regions = []
            for pi in range(answer['page'], end_page + 1):
                ap = answers[pi]
                y0 = max(60, answer['y'] - 6) if pi == answer['page'] else 60
                y1 = following['y'] - 6 if following and pi == end_page else 760
                if y1 <= y0:
                    continue
                images = ap.get_image_info()
                # Some embedded scans extend below the nominal body/footer
                # gap. Their actual image boxes take precedence over that
                # default, but never over a subsequent heading boundary.
                if not following or pi != end_page:
                    y1 = max(y1, max((im['bbox'][3] + 3 for im in images), default=y1))
                if pi != answer['page']:
                    y0 = min(y0, min((im['bbox'][1] - 3 for im in images), default=y0))
                rect = pymupdf.Rect(0, max(0, y0), ap.rect.width, min(ap.rect.height, y1))
                # A tall embedded image crossing either boundary must never be
                # silently cropped. Such a source requires manual review.
                for image in images:
                    ib = pymupdf.Rect(image['bbox'])
                    if ib.intersects(rect) and (ib.y0 < y0 - 1 or ib.y1 > y1 + 1):
                        raise ValueError(f'Answer image crosses boundary for #{q.number:03d} on page {pi + 1}')
                if any(pymupdf.Rect(image['bbox']).intersects(rect) for image in images):
                    regions.append({'page': pi, 'bbox': list(rect)})
            if not regions:
                raise ValueError(f'Empty answer for #{q.number:03d}')
            result['questions'].append({'number': q.number, 'source': q.source,
                'question_regions': [qr], 'answer_regions': regions, 'confidence': 1.0})
    result['counts'] = {'questions': len(result['questions']), 'matched_answers': len(result['questions']),
        'answer_regions': sum(len(q['answer_regions']) for q in result['questions']),
        'cross_page_answers': sum(len(q['answer_regions']) > 1 for q in result['questions']),
        'by_chapter': dict(Counter(q.chapter for q in book.questions)), 'ocr_pages': []}
    return result
