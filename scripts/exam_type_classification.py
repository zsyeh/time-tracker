#!/usr/bin/env python3
"""Local, read-only EI/Drill exam-form classifier. Never writes production DB.

The input is a metadata-only JSONL export. Human labels live in a separate
review queue; model output is never treated as human ground truth.
"""

import argparse
import base64
import csv
import hashlib
import json
import logging
import os
import random
import re
import subprocess
import sys
from copy import deepcopy
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
from pathlib import Path


VERSION = 'exam-form-v1'
MODEL = os.environ.get('EXAM_TYPE_MODEL', 'gpt-6-luna')
if MODEL not in ('gpt-6-luna', 'gpt-6.1-terra'):
    raise RuntimeError('Unsupported EXAM_TYPE_MODEL')
ALLOWED = {
    'drill': {'choice', 'fill', 'large', 'unknown'},
    'ei': {'judgment', 'choice', 'fill', 'short_answer', 'large', 'unknown'},
}
LEGACY = {'single_choice': 'choice', 'fill_blank': 'fill', 'solution': 'large'}
INPUT_PRICE = 0.10 / 1_000_000
CACHED_INPUT_PRICE = 0.01 / 1_000_000
OUTPUT_PRICE = 0.50 / 1_000_000
PRICES = {'gpt-6-luna': (0.10, 0.01, 0.50), 'gpt-6.1-terra': (1.00, 0.05, 5.00)}


def usage_cost(usage, model_id):
    input_price, cached_price, output_price = PRICES[model_id]
    return ((usage['input_tokens']-usage['cached_input_tokens'])*input_price
            +usage['cached_input_tokens']*cached_price
            +usage['output_tokens']*output_price)/1_000_000
HEADER_TYPE = re.compile(r'(?:^|[·|/\s])(?:题型[：:]\s*)?(判断题|选择题|单选题|多选题|填空题|简答题|解答题|计算题|证明题)(?:[·|/\s]|$)')
HEADER_MAP = {'判断题': 'judgment', '选择题': 'choice', '单选题': 'choice', '多选题': 'choice',
              '填空题': 'fill', '简答题': 'short_answer', '解答题': 'large',
              '计算题': 'large', '证明题': 'large'}
SYSTEM = '''Classify the ORIGINAL EXAM ANSWER FORMAT, not length, difficulty, amount of calculation, or answer length.
Drill: choice (single or multiple choice), fill (final result only), large (worked solution, proof, design).
EI: judgment (true/false, including multi-item judgment groups), choice, fill, short_answer (concept explanation or brief comparison), large (worked computation, derivation, proof, design, complete program).
Judgment groups remain judgment; count identifiable judgment subitems. If judgment requires a substantial explanation for marks, use short_answer when that is the main assessed response.
Never infer choice solely from option-like letters; never infer fill solely from a blank or calculation; never infer large solely from many subitems or answer length.
If the original format is missing, mixed, image-only without enough evidence, or the short_answer/large boundary is unclear, output unknown and review_required=true.
Existing metadata is evidence, not ground truth, unless explicitly human verified. Record concise evidence in reason. Return one JSON item per input ID, exactly once.'''
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['items'], 'properties': {
        'items': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['question_id', 'question_type', 'subquestion_count', 'review_required', 'reason', 'evidence_missing'],
            'properties': {
                'question_id': {'type': 'integer'},
                'question_type': {'type': 'string', 'enum': ['judgment', 'choice', 'fill', 'short_answer', 'large', 'unknown']},
                'subquestion_count': {'type': ['integer', 'null']},
                'review_required': {'type': 'boolean'},
                'reason': {'type': 'string'},
                'evidence_missing': {'type': 'string'},
            }}}}}


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def evidence(row):
    assets = row.get('assets') or []
    return {
        'question_id': row['question_id'], 'source_system': row['source_system'],
        'source_label': row.get('source_label') or '', 'display_label': row.get('display_label') or '',
        'prompt_text': row.get('prompt_text') or '', 'latex_text': row.get('latex_text') or '',
        'document_title': row.get('document_title') or '', 'topic_title': row.get('topic_title') or '',
        'legacy_type': row.get('legacy_type') or '', 'legacy_source': row.get('legacy_source') or '',
        'legacy_human_verified': bool(row.get('legacy_human_verified')),
        'content_mode': row.get('content_mode') or '',
        'question_asset_count': sum(a['type'] == 'question_crop' for a in assets),
        'question_asset_hashes': [a['sha256'] for a in assets if a['type'] == 'question_crop'],
    }


def content_hash(row):
    return hashlib.sha256(json.dumps({'version': VERSION, 'evidence': evidence(row)},
                                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def rule_decision(row):
    workspace = row['source_system']
    if row.get('legacy_human_verified') and row.get('legacy_source') == 'human':
        label = LEGACY.get(row.get('legacy_type'))
        if label in ALLOWED[workspace]:
            return label, 'Existing human-verified original exam type.'
    # Section headings are strong only when the source metadata itself is explicit.
    labels = set()
    for field in ('source_label', 'display_label'):
        labels.update(HEADER_MAP[match] for match in HEADER_TYPE.findall(row.get(field) or ''))
    if len(labels) == 1:
        label = labels.pop()
        if label in ALLOWED[workspace] and (row.get('prompt_text') or row.get('latex_text')):
            return label, 'Explicit exam-form heading in source label.'
    return None


def prepare(args):
    rows = list(read_jsonl(args.input))
    by_key = {(r['source_system'], str(r['question_id'])): r for r in rows}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    queue_path = out/'validation_queue.csv'
    previous = {}
    manual_rows = []
    if queue_path.exists():
        with queue_path.open(encoding='utf-8', newline='') as source:
            for entry in csv.DictReader(source):
                key = (entry['source_system'], entry['question_id'])
                previous[key] = entry
                if entry.get('human_label') and entry.get('annotator') != 'existing_verified':
                    row = by_key.get(key)
                    if not row or not entry.get('content_hash') or entry['content_hash'] != content_hash(row):
                        raise ValueError(f'Human annotation {key} is stale; resolve it before regenerating the queue')
                    if entry['human_label'] not in ALLOWED[row['source_system']]:
                        raise ValueError(f'Invalid human label for {key}')
                    manual_rows.append(row)
    if len(manual_rows) > args.size:
        raise ValueError('Existing human annotations exceed requested sample size')
    rng = random.Random(20261109)
    verified = [r for r in rows if r.get('legacy_human_verified') and r.get('legacy_source') == 'human']
    verified_ids = {r['question_id'] for r in verified}
    others = [r for r in rows if r['question_id'] not in verified_ids]
    def stratum(r):
        prompt = (r.get('prompt_text') or '').lower()
        if not prompt and not r.get('latex_text'): return 'image_only'
        if r['source_system'] == 'ei' and ('判断' in prompt or '正确' in prompt and '错误' in prompt): return 'ei_judgment_candidate'
        if r['source_system'] == 'ei' and ('简述' in prompt or '解释' in prompt or '比较' in prompt): return 'ei_short_candidate'
        if r['source_system'] == 'drill' and ('填空' in prompt or '____' in prompt): return 'drill_fill_candidate'
        if r.get('legacy_type') == 'unknown': return 'legacy_unknown'
        return r['source_system'] + '_' + str(r.get('legacy_type'))
    groups = defaultdict(list)
    for row in others: groups[stratum(row)].append(row)
    for group in groups.values(): rng.shuffle(group)
    manual_ids = {r['question_id'] for r in manual_rows}
    sample = manual_rows + [r for r in verified if r['question_id'] not in manual_ids]
    selected = {row['question_id'] for row in sample}

    def add_matching(predicate, quota):
        candidates=[row for row in others if row['question_id'] not in selected and predicate(row)]
        rng.shuffle(candidates)
        for row in candidates[:min(quota,args.size-len(sample))]:
            sample.append(row);selected.add(row['question_id'])

    add_matching(lambda r:r['source_system']=='ei' and
        ('判断' in (r.get('prompt_text') or '') or '对错' in (r.get('prompt_text') or '')),15)
    add_matching(lambda r:r['source_system']=='ei' and
        any(word in (r.get('prompt_text') or '') for word in ('简述','解释','比较')),15)
    add_matching(lambda r:r['source_system']=='drill' and
        any(word in (r.get('prompt_text') or '') for word in ('填空','____')),15)
    add_matching(lambda r:not (r.get('prompt_text') or r.get('latex_text')) and bool(r.get('assets')),20)
    for workspace in ('ei','drill'):
        for legacy in ('single_choice','fill_blank','solution','unknown'):
            add_matching(lambda r,w=workspace,t=legacy:r['source_system']==w and r.get('legacy_type')==t,15)
    while len(sample) < args.size and any(groups.values()):
        for name in sorted(groups):
            if len(sample) >= args.size: break
            while groups[name] and groups[name][-1]['question_id'] in selected:groups[name].pop()
            if groups[name]:
                row=groups[name].pop();sample.append(row);selected.add(row['question_id'])
    sample = sample[:args.size]
    temporary = queue_path.with_name(queue_path.name+'.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=['question_id','uuid','content_hash','question_url','source_system','stratum','legacy_type','legacy_source',
            'document_title','display_label','prompt_excerpt','has_image','human_label','annotator','evidence'])
        writer.writeheader()
        for row in sample:
            known = rule_decision(row) if row.get('legacy_human_verified') else None
            prior = previous.get((row['source_system'], str(row['question_id'])), {})
            manual = prior.get('human_label') and prior.get('annotator') != 'existing_verified'
            writer.writerow({'question_id':row['question_id'],'uuid':row['uuid'],
                'content_hash':content_hash(row),
                'question_url':f'https://{row["source_system"]}.ehzsy.site/practice/{row["uuid"]}',
                'source_system':row['source_system'],
                'stratum':stratum(row),'legacy_type':row.get('legacy_type'),'legacy_source':row.get('legacy_source'),
                'document_title':row.get('document_title'),'display_label':row.get('display_label'),
                'prompt_excerpt':(row.get('prompt_text') or '')[:500],
                'has_image':any(a['type']=='question_crop' for a in row.get('assets') or []),
                'human_label':prior['human_label'] if manual else known[0] if known else '',
                'annotator':prior['annotator'] if manual else 'existing_verified' if known else '',
                'evidence':prior.get('evidence','') if manual else known[1] if known else ''})
        target.flush();os.fsync(target.fileno())
    os.replace(temporary, queue_path)
    ordered = sample[:]
    rng.shuffle(ordered)
    # Gold-backed cases first; then EI cases so a small trial tests both workspaces.
    ordered.sort(key=lambda r: (0 if r.get('legacy_human_verified') else 1,
                                0 if r['source_system']=='ei' else 1))
    with (out/'validation_sample.jsonl').open('w', encoding='utf-8') as target:
        for row in ordered: target.write(json.dumps(row, ensure_ascii=False)+'\n')
    print(json.dumps({'total':len(rows),'validation_queue':len(sample),'existing_verified':len(verified),
                      'pending_manual':len(sample)-sum(bool(r.get('legacy_human_verified')) for r in sample),
                      'strata':dict(Counter(stratum(r) for r in sample))},ensure_ascii=False))


def load_key():
    path=Path.home()/'.api_key_secret'
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise RuntimeError('~/.api_key_secret missing or permissions are too broad')
    key=path.read_text().strip()
    if not key.startswith('sk-') or '\n' in key:
        raise RuntimeError('~/.api_key_secret must contain one raw OpenAI API key')
    return key


def batches(rows, size=25, char_budget=60000):
    current=[]; chars=0
    for row in rows:
        length=len(json.dumps(evidence(row),ensure_ascii=False))
        if current and (len(current)>=size or chars+length>char_budget):
            yield current; current=[]; chars=0
        current.append(row); chars+=length
    if current: yield current


def validate_response(items, rows):
    ids={r['question_id'] for r in rows}
    if len(items)!=len(rows): raise ValueError(f'count mismatch: expected {len(rows)}, got {len(items)}')
    seen=set()
    for item in items:
        qid=item['question_id']
        if qid not in ids or qid in seen: raise ValueError(f'unexpected or duplicate ID: {qid}')
        seen.add(qid)
        row=next(r for r in rows if r['question_id']==qid)
        if item['question_type'] not in ALLOWED[row['source_system']]: raise ValueError(f'invalid type for {qid}')
        count=item['subquestion_count']
        if count is not None and (not isinstance(count,int) or count<1 or count>100): raise ValueError(f'invalid subquestion count for {qid}')
        if item['question_type']=='unknown' and not item['review_required']: raise ValueError(f'unknown must require review: {qid}')
        if not item['reason'].strip(): raise ValueError(f'missing reason: {qid}')
    return {item['question_id']:item for item in items}


def needs_review(row, item):
    if item['question_type']=='unknown' or item['review_required']:return True
    old=LEGACY.get(row.get('legacy_type'))
    if old and old!=item['question_type']:return True
    if not (row.get('prompt_text') or row.get('latex_text')):return True
    return False


def call_batch(batch, effort, api_key):
    from openai import OpenAI
    client=OpenAI(api_key=api_key, timeout=120, max_retries=2)
    schema=deepcopy(SCHEMA)
    schema['properties']['items']['items']['properties']['question_type']['enum']=sorted(ALLOWED[batch[0]['source_system']])
    response=client.responses.create(model=MODEL,reasoning={'effort':effort},store=False,
        input=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps([evidence(r) for r in batch],ensure_ascii=False)}],
        text={'format':{'type':'json_schema','name':'exam_form_batch','strict':True,'schema':schema}},
        max_output_tokens=8000)
    if response.status!='completed': raise RuntimeError(f'API response status {response.status}')
    items=json.loads(response.output_text)['items']
    checked=validate_response(items,batch)
    usage=response.usage
    usage_data={'input_tokens':usage.input_tokens,'output_tokens':usage.output_tokens,
        'cached_input_tokens':getattr(usage.input_tokens_details,'cached_tokens',0) or 0,
        'reasoning_tokens':getattr(usage.output_tokens_details,'reasoning_tokens',0) or 0}
    return checked,usage_data


def fetch_question_image(row, output_dir):
    hashes=[a['sha256'] for a in row.get('assets') or [] if a['type']=='question_crop']
    if not hashes:return None
    digest=hashes[0]
    if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('invalid asset hash')
    destination=Path(output_dir)/'assets'/f'{digest}.png'
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        data=destination.read_bytes()
    else:
        query=f"SELECT encode(image_data, 'base64') FROM drill_questionasset WHERE question_id={int(row['question_id'])} AND sha256='{digest}' AND asset_type='question_crop' AND octet_length(image_data)<=4000000 ORDER BY position,id LIMIT 1;"
        command='set -a; . /var/snap/docker/common/time-tracker-ha/secrets/database.env; set +a; PGOPTIONS="-c default_transaction_read_only=on" psql "$DATABASE_URL" -X -qAt'
        result=subprocess.run(['ssh','root@47.95.10.128',command],input=query.encode(),capture_output=True,timeout=45)
        if result.returncode:raise RuntimeError('read-only image fetch failed')
        if not result.stdout.strip():return None
        data=base64.b64decode(result.stdout,validate=False)
        if len(data)>4_000_000:raise ValueError('asset exceeds image size cap')
        destination.write_bytes(data);destination.chmod(0o600)
    if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('image SHA-256 mismatch')
    return data


def call_image_followup(row, image, effort, api_key):
    from openai import OpenAI
    client=OpenAI(api_key=api_key,timeout=120,max_retries=2)
    schema=deepcopy(SCHEMA)
    schema['properties']['items']['items']['properties']['question_type']['enum']=sorted(ALLOWED[row['source_system']])
    response=client.responses.create(model=MODEL,reasoning={'effort':effort},store=False,
        input=[{'role':'system','content':SYSTEM},
            {'role':'user','content':[
                {'type':'input_text','text':'Inspect the original question image and classify this one item. JSON evidence: '+json.dumps(evidence(row),ensure_ascii=False)},
                {'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(image).decode()},
            ]}],
        text={'format':{'type':'json_schema','name':'exam_form_image','strict':True,'schema':schema}},max_output_tokens=2000)
    if response.status!='completed':raise RuntimeError(f'API response status {response.status}')
    item=validate_response(json.loads(response.output_text)['items'],[row])[row['question_id']]
    usage=response.usage
    return item,{'input_tokens':usage.input_tokens,'output_tokens':usage.output_tokens,
        'cached_input_tokens':getattr(usage.input_tokens_details,'cached_tokens',0) or 0,
        'reasoning_tokens':getattr(usage.output_tokens_details,'reasoning_tokens',0) or 0}


def followup(args):
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=out/f'run-{args.effort}-image.log',level=logging.INFO,
                        format='%(asctime)s %(message)s',force=True)
    rows={r['question_id']:r for r in read_jsonl(args.input)}
    base_path=out/f'results-{args.effort}.jsonl'
    if not base_path.exists():raise RuntimeError('base classification cache is missing')
    base={r['question_id']:r for r in read_jsonl(base_path) if r['source_system'] in ALLOWED}
    cache_path=out/f'results-{args.effort}-image.jsonl'
    cached={(r['question_id'],r['content_hash'],r.get('model_id')) for r in read_jsonl(cache_path)} if cache_path.exists() else set()
    candidates=[]
    for qid,row in rows.items():
        prior=base.get(qid)
        if not prior or prior['content_hash']!=content_hash(row) or prior.get('model_id') not in (None,MODEL):continue
        if prior['question_type']!='unknown' and not prior['review_required']:continue
        if (qid,prior['content_hash'],MODEL) in cached:continue
        if any(a['type']=='question_crop' for a in row.get('assets') or []):candidates.append(row)
    if args.limit:candidates=candidates[:args.limit]
    logging.info('start image followup candidates=%s effort=%s',len(candidates),args.effort)
    print(f'log={out/f"run-{args.effort}-image.log"} candidates={len(candidates)}',flush=True)
    if not candidates:return
    key=load_key()
    with cache_path.open('a',encoding='utf-8') as target,ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending={}

        def collect(completed):
            for future in completed:
                index,row=pending.pop(future)
                qid=row['question_id']
                try:
                    item,usage=future.result()
                    record={'source_system':row['source_system'],'question_id':qid,
                        'question_type':item['question_type'],'subquestion_count':item['subquestion_count'],
                        'classification_source':'ai_image','model_id':MODEL,'classification_version':VERSION,
                        'content_hash':content_hash(row),'review_required':needs_review(row,item),
                        'reason':item['reason'],'evidence_missing':item['evidence_missing'],'usage':usage}
                    target.write(json.dumps(record,ensure_ascii=False)+'\n');target.flush()
                    logging.info('image_done %s/%s id=%s label=%s input=%s output=%s',index,len(candidates),
                                 qid,item['question_type'],usage['input_tokens'],usage['output_tokens'])
                except Exception as error:
                    logging.exception('image_failed id=%s error=%s',qid,error)

        for index,row in enumerate(candidates,1):
            qid=row['question_id']
            try:
                image=fetch_question_image(row,out)
                if image is None:
                    logging.warning('image_unavailable id=%s',qid);continue
                future=pool.submit(call_image_followup,row,image,args.effort,key)
                pending[future]=(index,row)
                if len(pending)>=args.concurrency:
                    completed,_=wait(pending,return_when=FIRST_COMPLETED)
                    collect(completed)
            except Exception as error:
                logging.exception('image_fetch_failed id=%s error=%s',qid,error)
        while pending:
            completed,_=wait(pending,return_when=FIRST_COMPLETED)
            collect(completed)
    logging.info('finished')


def run(args):
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    log=out/f'run-{args.effort}.log'
    logging.basicConfig(filename=log,level=logging.INFO,format='%(asctime)s %(message)s',force=True)
    rows=list(read_jsonl(args.input))
    if args.limit: rows=rows[:args.limit]
    if len(rows)>300 and not args.full_approved:
        raise RuntimeError('Full API classification requires --full-approved after review approval')
    cache_path=out/f'results-{args.effort}.jsonl'
    cache={(r['source_system'],r['question_id'],r['content_hash']):r for r in read_jsonl(cache_path)} if cache_path.exists() else {}
    fresh_rules=[]
    pending=[]; reused=0; rules=0
    for row in rows:
        key=(row['source_system'],row['question_id'],content_hash(row))
        if key in cache and (cache[key].get('model_id') in (None,MODEL)): reused+=1;continue
        decision=None if args.force_ai else rule_decision(row)
        if decision:
            label,reason=decision
            record={'source_system':row['source_system'],'question_id':row['question_id'],'question_type':label,
                'subquestion_count':None,'classification_source':'existing_human' if row.get('legacy_human_verified') else 'explicit_rule',
                'model_id':None,'classification_version':VERSION,'content_hash':key[2],
                'review_required':False,'reason':reason,'evidence_missing':'','usage':None}
            cache[key]=record;fresh_rules.append(record);rules+=1
        else: pending.append(row)
    with cache_path.open('a',encoding='utf-8') as target:
        for record in fresh_rules: target.write(json.dumps(record,ensure_ascii=False)+'\n')
        target.flush()
    jobs=[batch for workspace in ('drill','ei') for batch in batches(
        [r for r in pending if r['source_system']==workspace],args.batch_size,args.char_budget)]
    logging.info('start effort=%s rows=%s reused=%s rules=%s pending=%s batches=%s workers=%s',
                 args.effort,len(rows),reused,rules,len(pending),len(jobs),args.concurrency)
    print(f'log={log} rows={len(rows)} reused={reused} rules={rules} pending={len(pending)} batches={len(jobs)}',flush=True)
    if not jobs:return
    api_key=load_key()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool,cache_path.open('a',encoding='utf-8') as target:
        futures={pool.submit(call_batch,batch,args.effort,api_key):batch for batch in jobs}
        for index,future in enumerate(as_completed(futures),1):
            batch=futures[future]
            try:
                results,usage=future.result()
            except Exception as error:
                logging.exception('batch_failed ids=%s error=%s',[r['question_id'] for r in batch],error)
                continue
            for row in batch:
                item=results[row['question_id']]
                record={'source_system':row['source_system'],'question_id':row['question_id'],
                    'question_type':item['question_type'],'subquestion_count':item['subquestion_count'],
                    'classification_source':'ai','model_id':MODEL,'classification_version':VERSION,
                    'content_hash':content_hash(row),'review_required':needs_review(row,item),
                    'reason':item['reason'],'evidence_missing':item['evidence_missing'],
                    'usage':usage if row==batch[0] else None}
                target.write(json.dumps(record,ensure_ascii=False)+'\n')
            target.flush()
            logging.info('batch_done %s/%s ids=%s input=%s output=%s reasoning=%s',index,len(jobs),
                         [r['question_id'] for r in batch],usage['input_tokens'],usage['output_tokens'],usage['reasoning_tokens'])
    logging.info('finished')


def report(args):
    input_rows=list(read_jsonl(args.input)); by_id={(r['source_system'],r['question_id']):r for r in input_rows}
    out=Path(args.output_dir);records={}
    sample_path=out/'validation_sample.jsonl'
    sample_ids={(r['source_system'],r['question_id']) for r in read_jsonl(sample_path)} if sample_path.exists() else None
    for effort in ('none','low'):
        path=out/f'results-{effort}.jsonl'
        if path.exists():
            for row in read_jsonl(path):
                original=by_id.get((row['source_system'],row['question_id']))
                if (original and row['content_hash']==content_hash(original)
                        and (sample_ids is None or (row['source_system'],row['question_id']) in sample_ids)):
                    records[(effort,row['source_system'],row['question_id'])]=row
    gold={}
    queue=out/'validation_queue.csv'
    if queue.exists():
        with queue.open(encoding='utf-8',newline='') as source:
            for row in csv.DictReader(source):
                original=by_id.get((row['source_system'],int(row['question_id'])))
                if (original and row.get('content_hash')==content_hash(original)
                        and row['human_label'] and row['annotator']
                        and row['human_label'] in ALLOWED[row['source_system']]):
                    gold[(row['source_system'],int(row['question_id']))]=row['human_label']
    queue_size=0
    if queue.exists():
        with queue.open(encoding='utf-8',newline='') as source:
            queue_size=sum(1 for _ in csv.DictReader(source))
    result={'snapshot':{w:{'total':sum(r['source_system']==w for r in input_rows),
        'trained':sum(r['source_system']==w and bool(r.get('has_training')) for r in input_rows),
        'legacy_types':dict(Counter(r.get('legacy_type') for r in input_rows if r['source_system']==w)),
        'rule_candidates':sum(r['source_system']==w and rule_decision(r) is not None for r in input_rows)} for w in ('drill','ei')},
        'validation':{'queue_size':queue_size,
                      'human_gold_count':len(gold)},'efforts':{}}
    for effort in ('none','low'):
        selected=[r for (e,_,_),r in records.items() if e==effort]
        matrix=defaultdict(Counter);cost=0;usage=Counter();conflicts=[];abstentions=[]
        for row in selected:
            g=gold.get((row['source_system'],row['question_id']))
            if g:
                matrix[g][row['question_type']]+=1
                if row['question_type']=='unknown': abstentions.append(row['question_id'])
                elif g!=row['question_type']: conflicts.append(row['question_id'])
            u=row.get('usage')
            if u:
                usage.update(u)
                cost+=usage_cost(u,row.get('model_id') or 'gpt-6-luna')
        result['efforts'][effort]={'classified':len(selected),'by_workspace':{
            w:{'counts':dict(Counter(r['question_type'] for r in selected if r['source_system']==w)),
               'percent':{label:round(100*count/max(1,sum(r['source_system']==w for r in selected)),1)
                    for label,count in Counter(r['question_type'] for r in selected if r['source_system']==w).items()},
               'trained_counts':dict(Counter(r['question_type'] for r in selected if r['source_system']==w and by_id[(w,r['question_id'])].get('has_training'))),
               'review_required':sum(needs_review(by_id[(w,r['question_id'])],r) for r in selected if r['source_system']==w),
               'judgment_subquestions':sum(r.get('subquestion_count') or 0 for r in selected if r['source_system']==w and r['question_type']=='judgment')}
            for w in ('drill','ei')},
            'sources':dict(Counter(r['classification_source'] for r in selected)),
            'confusion_matrix':{k:dict(v) for k,v in matrix.items()},'mismatches':conflicts,
            'gold_abstentions':abstentions,
            'unknown_ids':[r['question_id'] for r in selected if r['question_type']=='unknown'],
            'legacy_conflict_ids':[r['question_id'] for r in selected
                if LEGACY.get(by_id[(r['source_system'],r['question_id'])].get('legacy_type'))
                and LEGACY[by_id[(r['source_system'],r['question_id'])]['legacy_type']]!=r['question_type']
                and r['question_type']!='unknown'],
            'human_evaluated':sum(sum(v.values()) for v in matrix.values()),
            'gold_accuracy_with_abstentions':round(sum(v.get(k,0) for k,v in matrix.items())/max(1,sum(sum(v.values()) for v in matrix.values())),4),
            'confirmed_precision_on_gold':round(sum(v.get(k,0) for k,v in matrix.items())/max(1,sum(sum(v.values()) for v in matrix.values())-len(abstentions)),4),
            'unknown':sum(r['question_type']=='unknown' for r in selected),
            'api_requests':sum(r.get('usage') is not None for r in selected),
            'tokens':dict(usage),'estimated_usd':round(cost,6)}
        image_path=out/f'results-{effort}-image.jsonl'
        if image_path.exists():
            image_rows=[r for r in read_jsonl(image_path)
                        if (r['source_system'],r['question_id']) in by_id
                        and r['content_hash']==content_hash(by_id[(r['source_system'],r['question_id'])])
                        and (sample_ids is None or (r['source_system'],r['question_id']) in sample_ids)]
            image_usage=Counter();image_cost=0
            for row in image_rows:
                u=row.get('usage') or {};image_usage.update(u)
                image_cost+=usage_cost(u,row.get('model_id') or 'gpt-6-luna')
            result['efforts'][effort]['image_followup']={'count':len(image_rows),
                'counts':dict(Counter(r['question_type'] for r in image_rows)),
                'review_required':sum(needs_review(by_id[(r['source_system'],r['question_id'])],r) for r in image_rows),
                'tokens':dict(image_usage),'estimated_usd':round(image_cost,6)}
        log=out/f'run-{effort}.log'
        if log.exists():result['efforts'][effort]['failed_requests_unmetered']=sum('batch_failed' in line for line in log.open(encoding='utf-8'))
    path=out/'report.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(path)


def export_candidates(args):
    out=Path(args.output_dir)
    rows=list(read_jsonl(args.input))
    base_path=out/f'results-{args.effort}.jsonl'
    image_path=out/f'results-{args.effort}-image.jsonl'
    records={}
    for path in (base_path,image_path):
        if path.exists():
            for record in read_jsonl(path):
                records[(record['source_system'],record['question_id'])]=record
    destination=out/'import-candidates.jsonl'
    counts=Counter()
    with destination.open('w',encoding='utf-8') as target:
        for row in rows:
            record=records.get((row['source_system'],row['question_id']))
            if not record or record['content_hash']!=content_hash(row):continue
            record={**record,'review_required':needs_review(row,record)}
            record.pop('usage',None)
            target.write(json.dumps(record,ensure_ascii=False)+'\n')
            counts[(row['source_system'],record['question_type'])]+=1
    print(json.dumps({'path':str(destination),'rows':sum(counts.values()),
                      'types':{f'{w}:{label}':n for (w,label),n in sorted(counts.items())}},ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','run','followup','report','export'):
        p=sub.add_parser(name);p.add_argument('--input',type=Path,required=True)
        p.add_argument('--output-dir',type=Path,required=True)
        if name=='prepare':p.add_argument('--size',type=int,default=300)
        if name=='run':
            p.add_argument('--effort',choices=['none','low'],required=True)
            p.add_argument('--limit',type=int,default=0)
            p.add_argument('--batch-size',type=int,default=25)
            p.add_argument('--char-budget',type=int,default=60000)
            p.add_argument('--concurrency',type=int,default=10)
            p.add_argument('--force-ai',action='store_true',help='Evaluate model even for existing human labels')
            p.add_argument('--full-approved',action='store_true',help='Explicit gate for more than 300 API candidates')
        if name=='followup':
            p.add_argument('--effort',choices=['none','low'],required=True)
            p.add_argument('--limit',type=int,default=0)
            p.add_argument('--concurrency',type=int,default=10)
        if name=='export':p.add_argument('--effort',choices=['none','low'],required=True)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args)
    elif args.command=='run':run(args)
    elif args.command=='followup':followup(args)
    elif args.command=='export':export_candidates(args)
    else:report(args)


if __name__=='__main__':main()
