"""Build a read-only virtual collection from exported metadata and cached text.

No database access, OCR calls or network requests. Source exports and caches
remain private; the small evidence/review manifests are the committed output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drill.signal_selection_rules import BUCKETS, classify


def build(inventory, workbook, index, caches):
    papers = {p['source_fingerprint']: p for p in index['papers'] if p['book'] == 'signals_859'}
    paired = {q['label'] for q in inventory if q['document'] == 23}
    records = []
    for q in inventory:
        stem = q['prompt']; method = 'structured_text'; skip = ''
        if not q['practiceable'] or q['source_label'].startswith('ucas:'):
            skip = '整卷/非练习容器，避免与逐题索引重复'
        elif q['document'] == 14 and q['source_label'].startswith('signal ·') and q['label'] in paired:
            skip = '同号课后题已有新版配对题答，虚拟集合优先新版，保留旧题及旧进度不修改'
        elif q['document'] == 23:
            method = 'pdf_text_layer'
            stem = '\n'.join(r['text'] for r in workbook.get(q['uuid'], []) if r['kind'] == 'question_crop')
            number = q['label'].split()[-1].split('-')
            if len(number) == 2:
                match = re.search(r'\b' + re.escape(number[0]) + r'\s*[-－]\s*' + re.escape(number[1]) + r'(?!\d)', stem)
                if match: stem = stem[match.start():]
        elif q['document'] == 26:
            method = 'cached_local_ocr'; parts = q['source_label'].split(':')
            paper = papers.get(parts[1]) if len(parts) == 3 else None
            items = paper['items'] if paper else []
            item = next((i for i in items if i['key'] == parts[-1]), None)
            lines = []
            if item:
                n = items.index(item); following = items[n+1] if n+1 < len(items) else None
                own = [a for a in q['assets'] if a['asset_type'] == 'question_crop']
                regions = [(a['source_page_index'], a['source_y0'], a['source_y1']) for a in own]
                if not regions:
                    regions = [(item['page_index'], None, None)]
                for page, top, bottom in regions:
                    path = next((root / item['source'] / f'{page:04}.json' for root in caches
                                 if (root / item['source'] / f'{page:04}.json').exists()), None)
                    if path is None: continue
                    d = json.loads(path.read_text()); h = d['height']
                    if top is None:
                        top = item['y']*h-3
                        bottom = following['y']*h if following and following['page_index'] == page else h-40
                    # Clip to the following indexed anchor, even if an older
                    # crop still includes it. Never borrow the next stem.
                    if following and following['page_index'] == page:
                        bottom = min(bottom, following['y']*h)
                    lines.extend(l['text'] for l in d['lines'] if top-2 <= (l['bbox'][1]+l['bbox'][3])/2 < bottom
                                 and 35 < l['bbox'][1] < h-35)
                stem = '\n'.join(lines) or item.get('anchor_text', '')
                # OCR may include the next section heading before its first
                # indexed question. Drop that trailing section, not its topic.
                heading = re.search(r'\n[一二三四五六七八九十]+\s*[、．.]\s*(?:填\s*空|选\s*择|判\s*断|计\s*算|解\s*答|简\s*答)', stem)
                if heading: stem = stem[:heading.start()]
        classified = classify(stem, label=q['label'], topic=q['topic'], scope=q['scope'], source=method)
        if skip: classified.update(status='excluded', reason=[skip])
        records.append(dict(uuid=q['uuid'], fingerprint=q['fingerprint'], document_id=q['document'],
                            label=q['label'], evidence_method=method, evidence=stem[:260], **classified))
    selected = [r for r in records if r['status'] == 'included']
    manifest = dict(schema_version=1, code='signal_selected', title='信号严选',
                    basis='按用户给定的892备考优先级，不是命题概率。复用原题、原答案和掌握记录；859深度不等于892主攻深度。',
                    syllabus_reference='drill.ei_syllabus.SYLLABUS[signals]', combination_key='combined_z_initial',
                    inventory_count=len(inventory),
                    buckets=[dict(key=k,title=t,rank=n,tier=tier,focus=f) for n,(k,t,tier,f) in enumerate(BUCKETS,1)],
                    questions=selected)
    review = dict(schema_version=1, inventory_count=len(inventory), records=[
        {k:r[k] for k in ['uuid','document_id','label','status','reason']} for r in records if r['status'] != 'included'])
    return manifest, review, records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--workbook-text', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--cache', type=Path, action='append', required=True)
    parser.add_argument('--output', choices=['selected','review','stats'], default='stats')
    args = parser.parse_args()
    m,r,all_rows = build(json.loads(args.inventory.read_text()), json.loads(args.workbook_text.read_text()),
                         json.loads(args.index.read_text()), args.cache)
    m['inventory_sha256'] = hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    result = m if args.output == 'selected' else r if args.output == 'review' else dict(
        status=Counter(q['status'] for q in all_rows), buckets=Counter(q['bucket'] for q in m['questions']),
        sources=Counter(q['document_id'] for q in m['questions']), combined=sum(q['combined_z_initial'] for q in m['questions']))
    print(json.dumps(result, ensure_ascii=False, indent=2))
