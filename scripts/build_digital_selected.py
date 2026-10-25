"""Build a read-only virtual collection from exported metadata and cached text.

No database access, OCR calls or network requests. Source exports and caches
remain private; the small evidence/review manifests are the committed output.
"""
import argparse
import base64
import zlib
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drill.digital_selection_rules import BUCKETS, classify


def build(inventory, workbook, index, caches):
    papers = {p['source_fingerprint']: p for p in index['papers'] if p['book'] == 'electronics'}
    records = []
    for q in inventory:
        stem = q['prompt']; method = 'structured_text'; skip = ''
        if not q['practiceable'] or q['source_label'].startswith('ucas:'):
            skip = '整卷/非练习容器，避免与逐题索引重复'
        elif q['document'] == 20:
            method = 'local_crop_ocr'
            stem = '\n'.join(v for k,v in sorted(workbook.items()) if k.startswith(q['uuid']+'-'))
            number = q['label'].split()[-1].split('-')
            if len(number) == 2:
                match = re.search(r'\b' + re.escape(number[0]) + r'\s*[-－]\s*' + re.escape(number[1]) + r'(?!\d)', stem)
                if match: stem = stem[match.start():]
        elif q['document'] == 25:
            method = 'cached_local_ocr'; parts = q['source_label'].split(':')
            paper = papers.get(parts[1]) if len(parts) == 3 else None
            items = paper['items'] if paper else []
            item = next((i for i in items if i['key'] == parts[-1]), None)
            lines = []
            if item:
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
                        bottom = h-40
                    if page==item['page_index']:
                        top=max(top,item['y']*h-3)
                    # Clip to the following indexed anchor, even if an older
                    # crop still includes it. Never borrow the next stem.
                    next_y=[i['y']*h for i in items if i['key']!=item['key']
                            and i['source']==item['source'] and i['page_index']==page and i['y']*h>top+8]
                    if next_y:bottom=min(bottom,min(next_y))
                    lines.extend(l['text'] for l in d['lines'] if top-2 <= (l['bbox'][1]+l['bbox'][3])/2 < bottom
                                 and 35 < l['bbox'][1] < h-35)
                stem = '\n'.join(lines) or item.get('anchor_text', '')
                # OCR may include the next section heading before its first
                # indexed question. Drop that trailing section, not its topic.
                heading = re.search(r'\n[一二三四五六七八九十]+\s*[、．.]\s*(?:填\s*空|选\s*择|判\s*断|计\s*算|解\s*答|简\s*答)', stem)
                if heading: stem = stem[:heading.start()]
        classified = classify(stem, label=q['label'], topic=q['topic'], scope=q['scope'], source=method)
        if q['document']==25 and len([a for a in q['assets'] if a['asset_type']=='question_crop'])>3:
            classified.update(status='review',reason=['多页旧裁图可能混入整卷/多题，独立归属待核对'])
        if q['document']==25 and q['label']=='2003年 · 版本1 · 题1':
            classified.update(status='review',reason=['旧索引仅有整卷混合片段，模电/数电多题归属不可靠'])
        if skip: classified.update(status='excluded', reason=[skip])
        records.append(dict(uuid=q['uuid'], fingerprint=q['fingerprint'], document_id=q['document'],
                            label=q['label'], evidence_method=method, evidence=stem[:260], **classified))
    selected = [r for r in records if r['status'] == 'included']
    manifest = dict(schema_version=1, code='digital_selected', title='数电严选',
                    basis='按用户提供的892数电备考优先级，S/A/B/C不是命题概率。优先组合与同步时序分析/设计；复杂级联单独选练。',
                    syllabus_reference='drill.ei_syllabus.SYLLABUS[digital]', combination_key='combined_standard',
                    inventory_count=len(inventory), kinds=['analysis','design','calculation','concept'],
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
    m,r,all_rows = build(json.loads(zlib.decompress(base64.b64decode(args.inventory.read_text()))), json.loads(args.workbook_text.read_text()),
                         json.loads(args.index.read_text()), args.cache)
    m['inventory_sha256'] = hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    result = m if args.output == 'selected' else r if args.output == 'review' else dict(
        status=Counter(q['status'] for q in all_rows), buckets=Counter(q['bucket'] for q in m['questions']),
        sources=Counter(q['document_id'] for q in m['questions']), combined=sum(q['combined_standard'] for q in m['questions']))
    print(json.dumps(result, ensure_ascii=False, indent=2))
