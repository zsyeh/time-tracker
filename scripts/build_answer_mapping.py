#!/usr/bin/env python3
"""Build conservative per-question answer-PDF segment mappings."""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_ROOT = ROOT / 'work' / 'answer_sources'
OUT = ROOT / 'work' / 'answer_mapping.jsonl'
DOCUMENT_PDFS = {
    1: '极限答案册.pdf', 2: '一元积分题库-答案.pdf', 3: '线代1000题参考答案.pdf',
    4: '二重积分题库答案.pdf', 5: '多元微分大观-答案.pdf', 6: '微分方程大观-答案.pdf',
    7: '反常积分-答案.pdf', 9: '一元微分大观-答案.pdf',
}


def normalize(value):
    value = unicodedata.normalize('NFKC', value or '').lower()
    value = value.replace('>>', '').replace('>', '').replace(' ', '').replace('\u3000', '')
    value = re.sub(r'[\r\n\t]', '', value)
    return re.sub(r'[，。、“”‘’：:；;（）()【】\[\]{}·•]', '', value)


def loose_normalize(value):
    return ''.join(re.findall(r'[A-Za-z0-9\u4e00-\u9fff]+', normalize(value)))


def anchor_needles(value):
    normalized = loose_normalize(value)
    candidates = []
    candidates.extend(re.findall(r'[\(\[【（]([^\)\]】）]{4,})', normalized))
    candidates.extend(re.findall(r'(?:19|20)\d{2}数[一二三四五六七八九十]', normalized))
    candidates.extend(re.findall(r'(?:880|900|1000|660)[^，。；;\)\]】）]{2,18}', normalized))
    return list(dict.fromkeys(item for item in candidates if len(item) >= 4))


def label_block(page, needle, loose=False):
    for block in page.get_text('blocks'):
        block_text = loose_normalize(block[4]) if loose else normalize(block[4])
        if needle in block_text:
            return block
    return None


def source_label_parts(value):
    parts = [value]
    parts.extend(re.split(r'[;；]+', value or ''))
    parts.extend(re.split(r'(?=[(（][A-Za-z0-9]+[)）])', value or ''))
    return [part.strip() for part in dict.fromkeys(parts) if len(loose_normalize(part)) >= 4]


def find_unique_start(info, value):
    exact_needle = normalize(value)
    exact_matches = [
        index + 1
        for index, text in enumerate(info['texts'])
        if exact_needle and exact_needle in text
    ]
    if len(exact_matches) == 1:
        page_index = exact_matches[0]
        block = label_block(info['pdf'][page_index - 1], exact_needle)
        if block is not None:
            return page_index, round(block[1], 3), 1.0, 'exact'

    fallback_options = []
    for candidate in dict.fromkeys([loose_normalize(value), *anchor_needles(value)]):
        if len(candidate) < 4:
            continue
        candidate_matches = [
            index + 1
            for index, text in enumerate(info['loose_texts'])
            if candidate in text
        ]
        if len(candidate_matches) != 1:
            continue
        page_index = candidate_matches[0]
        block = label_block(info['pdf'][page_index - 1], candidate, loose=True)
        if block is not None:
            fallback_options.append((len(candidate), page_index, round(block[1], 3)))
    if fallback_options:
        _, page_index, y0 = max(fallback_options)
        return page_index, y0, 0.99, 'loose'
    return None


def main():
    django.setup()
    from drill.models import Question

    documents = {}
    for filename in set(DOCUMENT_PDFS.values()):
        path = SOURCE_ROOT / filename
        document = pymupdf.open(path)
        documents[filename] = {
            'pdf': document,
            'texts': [normalize(page.get_text('text')) for page in document],
            'loose_texts': [loose_normalize(page.get_text('text')) for page in document],
        }

    rows = []
    boundaries = {}
    stats = {'questions': 0, 'exact_unique': 0, 'fallback_unique': 0, 'ambiguous': 0, 'missing': 0, 'unsupported_document': 0}
    for question in Question.objects.order_by('document_id', 'question_order'):
        stats['questions'] += 1
        filename = DOCUMENT_PDFS.get(question.document_id)
        if not filename:
            stats['unsupported_document'] += 1
            continue
        info = documents[filename]
        starts = []
        for part in source_label_parts(question.source_label):
            found = find_unique_start(info, part)
            if found:
                starts.append(found)
        unique_starts = sorted({(page, y0): (confidence, kind) for page, y0, confidence, kind in starts}.items())
        if not unique_starts:
            stats['missing'] += 1
            continue
        if len(unique_starts) == 1 and len(source_label_parts(question.source_label)) > 1:
            stats['missing'] += 1
            continue
        if len(unique_starts) > 1:
            match_method = 'compound_labels_unique_segmented'
            match_confidence = min(item[1][0] for item in unique_starts)
            stats['compound_unique'] = stats.get('compound_unique', 0) + 1
        else:
            match_method = 'normalized_source_label_exact_unique_segmented' if unique_starts[0][1][1] == 'exact' else 'loose_anchor_unique_segmented'
            match_confidence = unique_starts[0][1][0]
            stats['exact_unique' if unique_starts[0][1][1] == 'exact' else 'fallback_unique'] += 1
        start_points = [point for point, _ in unique_starts]
        for point in start_points:
            boundaries.setdefault(filename, []).append(point)
        rows.append({
            'question_uuid': str(question.uuid),
            'document_id': question.document_id,
            'question_order': question.question_order,
            'source_label': question.source_label,
            'source_pdf': filename,
            'page_indices': [page for page, _ in start_points],
            'label_y0': start_points[0][1],
            'start_points': start_points,
            'match_confidence': match_confidence,
            'match_method': match_method,
            'review_required': False,
        })

    grouped = {}
    for row in rows:
        grouped.setdefault(row['source_pdf'], []).append(row)
    for filename, group in grouped.items():
        duplicate_starts = {}
        for row in group:
            key = tuple(row.get('start_points', [(row['page_indices'][0], row['label_y0'])]))
            duplicate_starts.setdefault(key, []).append(row)
        duplicate_rows = {id(row) for duplicate in duplicate_starts.values() if len(duplicate) > 1 for row in duplicate}
        if duplicate_rows:
            stats['exact_unique'] -= len(duplicate_rows)
            stats['ambiguous'] += len(duplicate_rows)
            group[:] = [row for row in group if id(row) not in duplicate_rows]
    for filename, group in grouped.items():
        document = documents[filename]['pdf']
        group.sort(key=lambda row: (row['page_indices'][0], row['label_y0']))
        starts = sorted(set(boundaries.get(filename, [])))
        for row in group:
            regions = []
            for start_page, start_y in row.get('start_points', [(row['page_indices'][0], row['label_y0'])]):
                following = [start for start in starts if start > (start_page, start_y)]
                end_page, end_y = following[0] if following else (len(document), document[-1].rect.y1)
                for page_number in range(start_page, end_page + 1):
                    page = document[page_number - 1]
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
            deduped = []
            seen_regions = set()
            for region in sorted(regions, key=lambda item: (item['page_index'], item['y0'], item['y1'])):
                key = tuple(region.items())
                if key not in seen_regions:
                    seen_regions.add(key)
                    deduped.append(region)
            regions = deduped
            row['page_indices'] = [region['page_index'] for region in regions]
            row['crop_regions'] = regions

    rows = [row for group in grouped.values() for row in group if row.get('crop_regions')]
    for info in documents.values():
        info['pdf'].close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', encoding='utf-8') as handle:
        for row in sorted(rows, key=lambda item: (item['document_id'], item['question_order'])):
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    report = ROOT / 'reports' / 'answer_mapping_report.md'
    report.write_text(
        '# Answer Mapping Report\n\n'
        + '\n'.join(f'- **{key}**: {value}' for key, value in stats.items())
        + f'\n\n- Mapping file: `{OUT}`\n'
        + f'- Archive SHA256: `{(SOURCE_ROOT / "archive.sha256").read_text().strip()}`\n'
        + '- Segments start at the matched question label and end immediately before the next question label, including cross-page continuations.\n',
        encoding='utf-8',
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
