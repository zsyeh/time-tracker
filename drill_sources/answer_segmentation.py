"""Conservative, offline answer matching for previously indexed EI papers.

No model calls, database writes or OCR here. Numbered section/item identities
must be unique, and cuts must pass the same full-width ink/box checks as the
question importer. Missing/ambiguous evidence is a review record, not a guess.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import pymupdf

from .identity import child_fingerprint
from .segmentation import page_profile, whitespace_boundary


CN = {token: value for value, token in enumerate('一二三四五六七八九十', 1)}
MAIN = re.compile(r'^([一二三四五六七八九十]{1,3})[、.,．:：](.*)')
ITEM = re.compile(r'^(\d{1,2})[、.,．:：](?!\d)(.*)')


def chinese_number(token):
    if token in CN:
        return CN[token]
    if token.startswith('十') and token[1:] in CN:
        return 10 + CN[token[1:]]
    return None


def numbered_lines(regions, cache, margin_cache=None):
    """Merge independent local OCR passes only at matching spatial anchors."""
    output = []
    for position, region in enumerate(regions):
        path = Path(cache) / region['source'] / f'{region["page_index"]:04}.json'
        data = json.loads(path.read_text())
        lines = list(data['lines'])
        if margin_cache:
            margin = Path(margin_cache) / region['source'] / path.name
            if margin.exists():
                lines += json.loads(margin.read_text())['lines']
        candidates = []
        for line in lines:
            text = re.sub(r'\s+', '', line['text'])
            main = MAIN.match(text); item = ITEM.match(text)
            x, y, _, _ = line['bbox']
            if not (main or item) or x > data['width'] * .28 or not region['bbox'][1] <= y < min(region['bbox'][3], data['height'] * .95):
                continue
            number = chinese_number(main[1]) if main else int(item[1])
            if number is None or not 1 <= number <= 40:
                continue
            candidate = {'kind': 'main' if main else 'item', 'number': number,
                         'text': text, 'bbox': line['bbox'], 'region_position': position,
                         'source': region['source'], 'page_index': region['page_index']}
            near = [c for c in candidates if abs(c['bbox'][1] - y) < 7 and abs(c['bbox'][0] - x) < 15]
            if any(c['number'] != number or c['kind'] != candidate['kind'] for c in near):
                # Disagreeing passes cannot silently choose different identities.
                for c in near:
                    c['ambiguous'] = True
                candidate['ambiguous'] = True
            elif near:
                continue
            candidates.append(candidate)
        output += sorted(candidates, key=lambda c: (c['bbox'][1], c['bbox'][0]))
    return output


def match_numbered_answers(items, candidates):
    """Preserve source keys; never renumber questions from an answer list."""
    expected = {item['key'] for item in items}
    generic = {int(key.split('-')[1]) for key in expected if key.startswith('section-')}
    zero_section = generic == {0}
    main_style = any(c['kind'] == 'main' for c in candidates)
    current = None
    mapped = []
    for candidate in candidates:
        c = dict(candidate)
        number = c['number']
        if c['kind'] == 'main':
            if zero_section:
                c['key'] = f'section-0-item-{number}'
            elif number in generic:
                current = number
                c['key'] = f'heading-{number}'
            else:
                current = None
                c['key'] = f'main-{number}'
        elif zero_section and not main_style:
            c['key'] = f'section-0-item-{number}'
        elif current is not None:
            c['key'] = f'section-{current}-item-{number}'
        else:
            # Parenthesized solution steps and numeric formula lines must not
            # become independent answers inside a long-answer question.
            continue
        mapped.append(c)
    return mapped


def adjacent_keys(current, following):
    main = re.fullmatch(r'main-(\d+)', current)
    if main:
        return following in (f'main-{int(main[1])+1}', f'heading-{int(main[1])+1}')
    item = re.fullmatch(r'section-(\d+)-item-(\d+)', current)
    if item:
        section, number = map(int, item.groups())
        return following in (f'section-{section}-item-{number+1}',
                             f'heading-{section+1}', f'main-{section+1}')
    return False


def build_answer_manifest(index_path, source_manifests, cache, margin_cache=None):
    index = json.loads(Path(index_path).read_text())
    if index.get('schema_version') != 1:
        raise ValueError('Unsupported index manifest')
    sources = {}; parents = {}
    review_config = json.loads((Path(__file__).parent/'data'/'past_exam_answer_review.json').read_text())
    excluded_papers = {r['source_fingerprint']: r['reason'] for r in review_config['excluded_papers']}
    excluded_questions = {r['fingerprint']: r['reason'] for r in review_config['excluded_questions']}
    for manifest_path in source_manifests:
        path = Path(manifest_path); data = json.loads(path.read_text())
        for sha, source in data['sources'].items():
            file = path.parent / source['file']
            if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                raise ValueError(f'Corrupt PDF {sha}')
            sources[sha] = file
        for book in data['books']:
            for parent in book['questions']:
                fp = hashlib.sha256(f'ucas-past-exams:v1:{book["key"]}:{parent["year"]}:{parent["variant"]}:{parent["key"]}'.encode()).hexdigest()
                parents[fp] = parent
    output = {'schema_version': 1, 'profile': 'ei-full-width-whitespace-v1',
              'questions': [], 'review': [], 'sources': [], 'papers': []}

    @lru_cache(maxsize=12)
    def profile(sha, index):
        with pymupdf.open(sources[sha]) as pdf:
            return page_profile(pdf[index])

    @lru_cache(maxsize=256)
    def boundary(sha, index, y):
        lines = json.loads((Path(cache) / sha / f'{index:04}.json').read_text())['lines']
        return whitespace_boundary(None, y, lines, profile=profile(sha, index))

    for paper in index['papers']:
        parent = parents[paper['source_fingerprint']]
        items = sorted(paper['items'], key=lambda i: i['position'])
        invalid_index = any(re.search(r'本试卷|答题纸|考试时间|请把答案|试题共有', item.get('anchor_text', '')) for item in items)
        regions = parent['answer_regions']
        try:
            candidates = match_numbered_answers(items, numbered_lines(regions, cache, margin_cache)) if regions else []
            missing_cache = False
        except FileNotFoundError:
            candidates = []; missing_cache = True
        counts = Counter(c['key'] for c in candidates)
        successful = 0
        for item in items:
            record = {'fingerprint': child_fingerprint(paper['source_fingerprint'], item['key']),
                      'source_fingerprint': paper['source_fingerprint'], 'key': item['key'],
                      'label': item['label'], 'book': paper['book'], 'year': paper['year'],
                      'variant': paper['variant']}
            hits = [(n, c) for n, c in enumerate(candidates) if c['key'] == item['key']]
            reason = (excluded_papers.get(paper['source_fingerprint']) or excluded_questions.get(record['fingerprint']) or
                      ('invalid_question_index' if invalid_index else
                      'missing_original_answer' if not regions else 'missing_anchor_cache' if missing_cache else
                      'missing_answer_anchor' if not hits else 'ambiguous_answer_anchor' if len(hits) != 1 or hits[0][1].get('ambiguous') else ''))
            if not reason:
                n, current = hits[0]
                following = candidates[n+1] if n+1 < len(candidates) else None
                if following and (following.get('ambiguous') or counts[following['key']] != 1 or not adjacent_keys(item['key'], following['key'])):
                    reason = 'unverified_answer_interval'
                elif following is None and (not paper.get('complete') or item['key'] != items[-1]['key']):
                    reason = 'unverified_answer_tail'
            if not reason:
                start = current['region_position']
                end = following['region_position'] if following else len(regions)-1
                top = boundary(current['source'], current['page_index'], current['bbox'][1])
                bottom = boundary(following['source'], following['page_index'], following['bbox'][1]) if following else regions[-1]['bbox'][3]
                if top is None or bottom is None:
                    reason = 'no_safe_full_width_gap'
                elif top < regions[start]['bbox'][1] or bottom > regions[end]['bbox'][3]:
                    reason = 'outside_original_answer_region'
                elif (end, bottom) <= (start, top):
                    reason = 'non_monotonic_answer_regions'
            if reason:
                output['review'].append({**record, 'reason': reason})
                continue
            crops = []
            for pos in range(start, end+1):
                original = regions[pos]
                box = [0, top if pos == start else original['bbox'][1], 0,
                       bottom if pos == end else original['bbox'][3]]
                # Use PDF dimensions rather than rounded raster dimensions.
                with pymupdf.open(sources[original['source']]) as pdf:
                    box[2] = pdf[original['page_index']].rect.width
                if box[3]-box[1] < 3:
                    continue
                crops.append({'source': original['source'], 'page_index': original['page_index'], 'bbox': box})
            if not crops:
                output['review'].append({**record, 'reason': 'empty_answer_region'})
                continue
            output['questions'].append({**record, 'confidence': .95, 'solution_regions': crops})
            successful += 1
        output['papers'].append({'source_fingerprint': paper['source_fingerprint'], 'book': paper['book'],
                                 'year': paper['year'], 'variant': paper['variant'],
                                 'indexed': len(items), 'matched': successful})
    output['sources'] = sorted({r['source'] for q in output['questions'] for r in q['solution_regions']})
    output['counts'] = {'matched': len(output['questions']), 'needs_review': len(output['review']),
                        'regions': sum(len(q['solution_regions']) for q in output['questions']),
                        'reasons': dict(Counter(q['reason'] for q in output['review']))}
    return output
