"""Emit communication manifests from private exports; no database writes."""
import argparse,base64,hashlib,json,re,sys,zlib
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from drill.communication_selection_rules import BUCKETS,classify


def number(label):
    return tuple(re.findall(r'\d+',label))


def build(inventory,workbook):
    paired={number(q['label']) for q in inventory if q['document']==21}
    rows=[]
    for q in inventory:
        stem=q['prompt'] or workbook.get(q['uuid'],'')
        method='structured_text' if q['prompt'] else 'pdf_text_layer'
        result=classify(stem,label=q['label'],topic=q['topic'],scope=q['scope'],source=method)
        if not q['practiceable']:
            result.update(status='excluded',reason=['非独立练习容器'])
        elif q['document']==15 and q['source_label'].startswith('communication ·') and number(q['label']) in paired:
            result.update(status='excluded',reason=['同一原PDF同号习题已在新版配对书中引用；原题和进度不修改'])
        rows.append(dict(uuid=q['uuid'],fingerprint=q['fingerprint'],document_id=q['document'],label=q['label'],
                         evidence_method=method,evidence=stem[:280],**result))
    m=dict(schema_version=1,code='communication_selected',title='通信严选',
           basis='按用户提供的892通信备考优先级，不是命题概率。重点无码间串扰、匹配滤波和PCM/香农容量；不把误码率代入题冒充匹配滤波大题。',
           syllabus_reference='drill.ei_syllabus.SYLLABUS[communication]',combination_key='combined_priority',
           inventory_count=len(inventory),kinds=['calculation','analysis','concept'],
           buckets=[dict(key=k,title=t,rank=n,tier=tier,focus=f) for n,(k,t,tier,f) in enumerate(BUCKETS,1)],
           questions=[q for q in rows if q['status']=='included'])
    matched=[q for q in m['questions'] if q['bucket']=='matched_filter']
    m['coverage_notes'] = ([f'当前匹配滤波仅有{len(matched)}道原理/公式题，暂无完整计算题；没有把误码率代入题冒充匹配滤波大题。']
                           if matched and not any(q['kind']!='concept' for q in matched) else [])
    r=dict(schema_version=1,inventory_count=len(inventory),records=[
        {k:q[k] for k in ['uuid','document_id','label','status','reason']} for q in rows if q['status']!='included'])
    return m,r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--workbook-text',type=Path,required=True)
    p.add_argument('--output',choices=['selected','review','stats'],default='stats');args=p.parse_args()
    m,r=build(json.loads(zlib.decompress(base64.b64decode(args.inventory.read_text()))),json.loads(args.workbook_text.read_text()))
    m['inventory_sha256']=hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    result=m if args.output=='selected' else r if args.output=='review' else dict(
        selected=len(m['questions']),review=Counter(q['status'] for q in r['records']),
        buckets=Counter(q['bucket'] for q in m['questions']),tiers=Counter(q['tier'] for q in m['questions']),
        kinds=Counter(q['kind'] for q in m['questions']),sources=Counter(q['document_id'] for q in m['questions']))
    print(json.dumps(result,ensure_ascii=False,indent=2))
