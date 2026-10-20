"""Conservative full-width segmentation of the existing UCAS source index.

No OCR or model calls: reuse the reviewed index and cached OCR coordinates.
A cut needs a genuinely ink-free horizontal band, checked against all OCR
boxes. Uncertain or incomplete indexes retain the original shared pages.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import pymupdf

from .identity import child_fingerprint


def page_profile(page, dpi=120):
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    samples = pix.samples
    # Historical scans have a page-height frame around the paper. Ignore only
    # persistent columns in the outer 15%, not circuit wires in the body.
    rows = range(0, pix.height, 4)
    frame = set()
    for x in [*range(int(pix.width*.02), int(pix.width*.15)),
              *range(int(pix.width*.85), int(pix.width*.98))]:
        if sum(samples[y*pix.stride+x] < 150 for y in rows) >= len(rows)*.85:
            frame.update(range(max(0, x-3), min(pix.width, x+4)))
    return pix.width, pix.height, pix.stride, samples, frame, dpi/72


def whitespace_boundary(page, anchor_y, lines, dpi=120, profile=None):
    width, height, stride, samples, frame, scale = profile or page_profile(page, dpi)
    # Ignore scanner-edge noise for detection only. The output retains the
    # entire original width, including those margins.
    left = int(width * .02); right = width - left
    start = max(0, int((anchor_y - 48) * scale))
    stop = min(height, int((anchor_y - 4) * scale))
    runs = []; begin = None
    for y in range(start, stop):
        row = bytearray(samples[y * stride + left:y * stride + right])
        for x in frame:
            if left <= x < right:
                row[x-left] = 255
        blank = min(row, default=255) >= 150
        if blank and begin is None:
            begin = y
        if begin is not None and (not blank or y == stop - 1):
            end = y if not blank else y + 1
            if end - begin >= 2 * scale:
                runs.append((begin, end))
            begin = None
    for top, bottom in reversed(runs):
        cut = (top + bottom) / (2 * scale)
        # A distant blank band can be above the previous question's last
        # option/caption. Never attach that intervening line to the new item.
        if any(line['text'].strip() and cut + .5 < line['bbox'][3] <= anchor_y - .5
               for line in lines):
            continue
        if not any(line['text'].strip() and line['bbox'][1] + .5 < cut < line['bbox'][3] - .5
                   for line in lines):
            return round(cut, 3)
    return None


def interval_verified(paper, items, position, review):
    """An incomplete paper can still have explicitly consecutive safe items.

    Never span a reported missing item/section, or an unindexed final section.
    Without its audit, an incomplete paper is not eligible at all.
    """
    if paper['complete']:
        return True
    if not review or any(issue['reason'] not in {'missing_main_sections', 'number_gaps', 'no_numbered_items'}
                         for issue in review['issues']):
        return False
    def key(item):
        match = re.fullmatch(r'main-(\d+)|section-(\d+)-item-(\d+)', item['key'])
        if not match:
            return None
        return (int(match[1]), None) if match[1] else (int(match[2]), int(match[3]))
    current = key(items[position])
    if current is None:
        return False
    if any(issue['reason'] == 'no_numbered_items' and issue['section'] == current[0] for issue in review['issues']):
        return False
    if position + 1 == len(items):
        return current[0] >= max((section[0] for section in review.get('sections', [])), default=current[0])
    following = key(items[position+1])
    if following is None:
        return False
    if following[0] == current[0]:
        return current[1] is not None and following[1] == current[1]+1
    return following[0] == current[0]+1


def build_manifest(index_path, source_manifests, ocr_cache):
    index = json.loads(Path(index_path).read_text())
    if index.get('schema_version') != 1:
        raise ValueError('Unsupported source index')
    sources = {}; originals = {}
    review_file = Path(index_path).with_name('index-review.json')
    reviews = {(r['book'], r['year'], r['variant'], r['part']): r
               for r in json.loads(review_file.read_text())} if review_file.exists() else {}
    for manifest_path in source_manifests:
        path = Path(manifest_path); data = json.loads(path.read_text())
        for sha, item in data['sources'].items():
            file = (path.parent / item['file']).resolve()
            if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                raise ValueError(f'Source hash mismatch: {sha}')
            sources[sha] = file
        for book in data['books']:
            for question in book['questions']:
                identity = f'ucas-past-exams:v1:{book["key"]}:{question["year"]}:{question["variant"]}:{question["key"]}'
                originals[hashlib.sha256(identity.encode()).hexdigest()] = question
    output = {'schema_version': 1, 'profile': 'ei-full-width-whitespace-v1',
              'sources': sorted(sources), 'questions': [], 'review': []}

    @lru_cache(maxsize=8)
    def profile(sha, page_index):
        with pymupdf.open(sources[sha]) as pdf:
            return page_profile(pdf[page_index])

    @lru_cache(maxsize=8)
    def boundary(sha, page_index, y):
        cache = Path(ocr_cache) / sha / f'{page_index:04}.json'
        if not cache.exists():
            return None
        lines = json.loads(cache.read_text())['lines']
        return whitespace_boundary(None, y, lines, profile=profile(sha, page_index))

    for paper in index['papers']:
        parent = originals[paper['source_fingerprint']]
        regions = parent['question_regions']
        positions = {(r['source'], r['page_index']): i for i, r in enumerate(regions)}
        items = sorted(paper['items'], key=lambda q: q['position'])
        locations = []
        for item in items:
            pi = positions[(item['source'], item['page_index'])]
            region = regions[pi]
            y = region['bbox'][1] + item['y'] * (region['bbox'][3] - region['bbox'][1])
            cut = boundary(item['source'], item['page_index'], y)
            locations.append((pi, cut))
        bad_order = any((a[0], items[i]['y']) >= (b[0], items[i+1]['y'])
                        for i, (a, b) in enumerate(zip(locations, locations[1:])))
        for i, item in enumerate(items):
            fp = child_fingerprint(paper['source_fingerprint'], item['key'])
            record = {'fingerprint': fp, 'source_fingerprint': paper['source_fingerprint'],
                      'key': item['key'], 'label': item['label'], 'book': paper['book'],
                      'year': paper['year'], 'variant': paper['variant']}
            start_page, top = locations[i]
            end_page, bottom = locations[i+1] if i+1 < len(items) else (len(regions)-1, regions[-1]['bbox'][3])
            audit = reviews.get((paper['book'], paper['year'], paper['variant'], paper['part']))
            reason = ('unverified_number_gap' if not interval_verified(paper, items, i, audit) else
                      'non_monotonic_source_anchors' if bad_order else
                      'low_anchor_confidence' if min(item['confidence'], items[min(i+1,len(items)-1)]['confidence']) < .9 else
                      'no_safe_full_width_gap' if top is None or bottom is None else '')
            if reason:
                output['review'].append({**record, 'reason': reason})
                continue
            crops = []
            for pos in range(start_page, end_page+1):
                region = regions[pos]
                y0 = top if pos == start_page else region['bbox'][1]
                y1 = bottom if pos == end_page else region['bbox'][3]
                if y1 <= y0:
                    continue
                with pymupdf.open(sources[region['source']]) as pdf:
                    page_rect = pdf[region['page_index']].rect
                    width = page_rect.width
                crops.append({'source': region['source'], 'page_index': region['page_index'],
                              'bbox': [0, max(0, round(y0, 3)), width, min(page_rect.height, round(y1, 3))]})
            if not crops or any(r['bbox'][3]-r['bbox'][1]<3 for r in crops):
                output['review'].append({**record, 'reason': 'abnormal_region'})
            else:
                output['questions'].append({**record, 'confidence': .95, 'question_regions': crops})
    output['counts'] = {'individual_questions': len(output['questions']), 'needs_review': len(output['review']),
        'regions': sum(len(q['question_regions']) for q in output['questions']),
        'cross_page_questions': sum(len(q['question_regions']) > 1 for q in output['questions']),
        'new_ocr_pages': 0}
    return output
