#!/usr/bin/env python3
"""Map answer segments for records whose imported prompt contains multiple labels."""
import json
import os
import re
import sys
from pathlib import Path

import django
import pymupdf

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_ROOT = ROOT / 'work' / 'answer_sources'
OUT = ROOT / 'work' / 'answer_mapping_grouped_remaining.jsonl'
DOCUMENT_PDFS = {
    1: '极限答案册.pdf', 2: '一元积分题库-答案.pdf', 3: '线代1000题参考答案.pdf',
    4: '二重积分题库答案.pdf', 5: '多元微分大观-答案.pdf', 6: '微分方程大观-答案.pdf',
    7: '反常积分-答案.pdf', 9: '一元微分大观-答案.pdf',
}

def loose(value):
    return ''.join(re.findall(r'[A-Za-z0-9\u4e00-\u9fff]+', (value or '').lower()))

def anchors(value):
    raw = (value or '').lower()
    value = loose(value)
    parts = []
    parts.extend(
        loose(item)
        for item in re.findall(r'[\(\[【（]([^\)\]】）]{4,})', raw)
    )
    parts.extend(re.findall(r'(?:19|20)\d{2}数[一二三四五六七八九十]', value))
    parts.extend(re.findall(r'(?:880|900|1000|660)[^，。；;\)\]】）]{2,18}', value))
    parts.extend(
        loose(item)
        for item in re.findall(
            r'(?:姜晓千|基础|强化|综合|选择|填空|解答|真题同源|竞赛题)'
            r'[^\n>]{2,24}',
            raw,
        )
    )
    return list(dict.fromkeys(item for item in parts if len(item) >= 4))

def block_for(page, needle):
    for block in page.get_text('blocks'):
        if needle in loose(block[4]):
            return block
    return None

def main():
    django.setup()
    from drill.models import Question, QuestionAsset

    mapped = set(QuestionAsset.objects.filter(asset_type='answer_crop').values_list('question_id', flat=True))
    documents = {}
    for filename in set(DOCUMENT_PDFS.values()):
        pdf = pymupdf.open(SOURCE_ROOT / filename)
        documents[filename] = {
            'pdf': pdf,
            'texts': [loose(page.get_text('text')) for page in pdf],
        }

    boundaries = {}
    mapping_path = ROOT / 'work' / 'answer_mapping.jsonl'
    if mapping_path.exists():
        for line in mapping_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            filename = row['source_pdf']
            for region in row.get('crop_regions', []):
                boundaries.setdefault(filename, set()).add((region['page_index'], round(region['y0'], 3)))

    candidates = []
    for question in Question.objects.filter(record_kind='question').order_by('document_id', 'question_order'):
        if question.id in mapped or question.document_id not in DOCUMENT_PDFS:
            continue
        info = documents[DOCUMENT_PDFS[question.document_id]]
        parts = [question.source_label]
        parts.extend(part for part in (question.prompt_text or '').split('>>') if part.strip())
        starts = set()
        for part in parts:
            needles = [loose(part), *anchors(part)]
            for needle in dict.fromkeys(needles):
                if len(needle) < 4:
                    continue
                matches = [index + 1 for index, text in enumerate(info['texts']) if needle in text]
                if len(matches) != 1:
                    continue
                page_index = matches[0]
                block = block_for(info['pdf'][page_index - 1], needle)
                if block is not None:
                    starts.add((page_index, round(block[1], 3)))
        if starts:
            candidates.append((question, DOCUMENT_PDFS[question.document_id], sorted(starts)))
            boundaries.setdefault(DOCUMENT_PDFS[question.document_id], set()).update(starts)

    rows = []
    for question, filename, starts in candidates:
        pdf = documents[filename]['pdf']
        ordered_boundaries = sorted(boundaries[filename])
        regions = []
        for start_page, start_y in starts:
            following = [item for item in ordered_boundaries if item > (start_page, start_y)]
            end_page, end_y = following[0] if following else (len(pdf), pdf[-1].rect.y1)
            for page_number in range(start_page, end_page + 1):
                page = pdf[page_number - 1]
                y0 = start_y if page_number == start_page else page.rect.y0
                y1 = end_y if page_number == end_page else page.rect.y1
                if y1 - y0 > 2:
                    regions.append({
                        'page_index': page_number,
                        'x0': 0.0,
                        'y0': round(y0, 3),
                        'x1': round(page.rect.x1, 3),
                        'y1': round(y1, 3),
                    })
        unique = []
        seen = set()
        for region in sorted(regions, key=lambda item: (item['page_index'], item['y0'], item['y1'])):
            key = tuple(region.items())
            if key not in seen:
                seen.add(key)
                unique.append(region)
        if unique:
            rows.append({
                'question_uuid': str(question.uuid),
                'document_id': question.document_id,
                'question_order': question.question_order,
                'source_label': question.source_label,
                'source_pdf': filename,
                'page_indices': [region['page_index'] for region in unique],
                'crop_regions': unique,
                'match_confidence': 0.985,
                'match_method': 'embedded_grouped_label_anchor_segmented',
                'review_required': False,
            })

    for info in documents.values():
        info['pdf'].close()
    OUT.write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in rows) + ('\n' if rows else ''), encoding='utf-8')
    print(json.dumps({'rows': len(rows), 'segments': sum(len(row['crop_regions']) for row in rows)}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
