"""Read-only, reproducible checks. AUTO_CHECKED never means visually verified."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError

from drill.core_selected import COURSES
from drill.models import Question, QuestionAsset, QuestionErratum


def image_checks(blob, width, height, sha256):
    issues=[]
    if hashlib.sha256(blob).hexdigest()!=sha256:
        issues.append('image_hash_mismatch')
    original=pymupdf.Pixmap(blob)
    if (original.width,original.height)!=(width,height):issues.append('image_dimensions_mismatch')
    if min(original.width,original.height)<30:issues.append('tiny_image')
    # Render onto a white PDF page so transparent PNG pixels cannot be
    # confused with black ink. No new image is saved to disk or PostgreSQL.
    with pymupdf.open() as document:
        page=document.new_page(width=original.width,height=original.height)
        page.insert_image(page.rect,stream=blob)
        gray=page.get_pixmap(colorspace=pymupdf.csGRAY,alpha=False)
    w,h=gray.width,gray.height
    ink=gray.samples.translate(bytes(1 if p<160 else 0 for p in range(256)))
    ratio=ink.count(1)/len(ink)
    if ratio<0.0002:issues.append('blank_or_nearly_blank_image')
    edges={'left':ink[0::w]+ink[min(1,w-1)::w],
           'right':ink[w-1::w]+ink[max(0,w-2)::w],
           'top':ink[:w*min(2,h)],'bottom':ink[-w*min(2,h):]}
    edges={side:round(values.count(1)/len(values),5) for side,values in edges.items()}
    # Only a suspicion: page borders and handwritten marks can also touch
    # an edge. Never widen or overwrite a crop based on this heuristic.
    for side,value in edges.items():
        if value>0.015:issues.append('ink_touches_'+side)
    return {'issues':issues,'ink_ratio':round(ratio,5),'edge_ink':edges}


class Command(BaseCommand):
    help='Audit every selected EI question without modifying questions, assets or progress.'

    def add_arguments(self,parser):
        parser.add_argument('--output',required=True)
        parser.add_argument('--force',action='store_true')
        parser.add_argument('--metadata-only',action='store_true')

    def handle(self,*args,**options):
        output=Path(options['output']).expanduser().resolve()
        if output.exists() and not options['force']:raise CommandError('Output exists; use a new filename or --force.')
        selected={};duplicates=[]
        for course,title,module in COURSES:
            for row in module.manifest()['questions']:
                if row['uuid'] in selected:duplicates.append(row['uuid']);continue
                selected[row['uuid']]={**row,'course':course,'course_title':title}
        questions={str(q.uuid):q for q in Question.objects.filter(uuid__in=selected).select_related('document','topic')}
        errata=defaultdict(list)
        for e in QuestionErratum.objects.filter(question__uuid__in=selected,status__in=['open','reviewing']).values('question_id','id','kind','description'):
            errata[e['question_id']].append(e)
        records={};pk_to_uuid={}
        for uuid,row in selected.items():
            q=questions.get(uuid);issues=[]
            if not q:
                records[uuid]={'uuid':uuid,'course':row['course'],'tier':row['tier'],'issues':['missing_question'],'status':'NEEDS_REVIEW'};continue
            pk_to_uuid[q.pk]=uuid
            if q.fingerprint!=row['fingerprint']:issues.append('stale_fingerprint')
            if q.document.workspace!='ei' or not q.is_practiceable:issues.append('not_practiceable_ei')
            if q.syllabus_scope=='out_of_scope':issues.append('wrong_scope')
            if errata[q.pk]:issues.append('unresolved_erratum')
            records[uuid]={'uuid':uuid,'question_id':q.pk,'document_id':q.document_id,'fingerprint':q.fingerprint,
                'course':row['course'],'tier':row['tier'],'bucket':row['bucket'],'kind':row.get('kind'),
                'label':q.display_label or q.source_label,'source_label':q.source_label,
                'source_category':q.source_category,'scope':q.syllabus_scope,
                'importance':{'status':'RULE_SELECTED_NOT_MANUALLY_REVERIFIED','reason':row.get('reason',[]),'evidence':row.get('evidence','')},
                'question_text_length':len(q.prompt_text.strip()),'answer_text_length':len(q.answer_markdown.strip()),
                'answer_source':q.answer_source,'answer_confidence':q.answer_confidence,
                'prompt_excerpt':q.prompt_text[:300],'answer_excerpt':q.answer_markdown[:300],
                'assets':[],'errata':errata[q.pk],'issues':issues,
                'visual_review':'PENDING','answer_matching':'PENDING','status':'PENDING'}
        hashes=defaultdict(list)
        fields=['id','source_id','question_id','asset_type','position','sha256','width','height','source_page_index',
                'source_x0','source_y0','source_x1','source_y1','render_dpi']
        assets=QuestionAsset.objects.filter(question_id__in=pk_to_uuid,asset_type__in=['question_crop','answer_crop']).order_by('pk')
        # Do not use a holdable PostgreSQL server cursor for BinaryField rows:
        # it may materialize all images into a large temporary spool on VPS.
        asset_ids=list(assets.values_list('pk',flat=True))
        def bounded_assets():
            for start in range(0,len(asset_ids),15):
                yield from assets.filter(pk__in=asset_ids[start:start+15]).values(
                    *fields,*([] if options['metadata_only'] else ['image_data']))
        for a in bounded_assets():
            r=records[pk_to_uuid[a['question_id']]];blob=bytes(a.pop('image_data',b''));a['issues']=[]
            bbox=[a['source_x0'],a['source_y0'],a['source_x1'],a['source_y1']]
            if any(v is not None for v in bbox):
                if any(v is None for v in bbox) or bbox[0]<0 or bbox[1]<0 or bbox[2]<=bbox[0] or bbox[3]<=bbox[1]:a['issues'].append('abnormal_bbox')
            else:a['issues'].append('source_bbox_unavailable')
            if a['source_page_index'] is None:a['issues'].append('source_page_unavailable')
            if not options['metadata_only']:
                try:
                    check=image_checks(blob,a['width'],a['height'],a['sha256'])
                    a['issues']+=check.pop('issues');a.update(check)
                except Exception as exc:a['issues'].append('image_decode_failed');a['decode_error']=type(exc).__name__
            hashes[(a['asset_type'],a['sha256'])].append(r['uuid'])
            r['assets'].append(a)
        for r in records.values():
            if 'assets' not in r:continue
            qa=[a for a in r['assets'] if a['asset_type']=='question_crop'];aa=[a for a in r['assets'] if a['asset_type']=='answer_crop']
            if not qa and not r['question_text_length']:r['issues'].append('no_own_question_material')
            if not aa and not r['answer_text_length']:r['issues'].append('no_own_answer_material')
            r['question_region_count']=len(qa);r['answer_region_count']=len(aa)
            for kind,group in [('question',qa),('answer',aa)]:
                positions=[a['position'] for a in group]
                if len(set(positions))!=len(positions):r['issues'].append(kind+'_duplicate_positions')
            for a in r['assets']:
                r['issues'].extend(a['issues'])
                if len(set(hashes[(a['asset_type'],a['sha256'])]))>1:r['issues'].append('shared_'+a['asset_type']+'_hash')
            r['issues']=sorted(set(r['issues']))
            r['status']='NEEDS_REVIEW' if r['issues'] else 'AUTO_CHECKED'
        counts=Counter(r['status'] for r in records.values());issue_counts=Counter(i for r in records.values() for i in r['issues'])
        report={'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),
            'mode':'metadata_only' if options['metadata_only'] else 'metadata_and_image_integrity',
            'notice':'AUTO_CHECKED is not visual verification, syllabus confirmation, diagram completeness or answer matching. No production data changed.',
            'summary':{'selected':len(selected),'core':sum(r['tier']=='core' for r in records.values()),
                'statuses':dict(counts),'issues':dict(issue_counts),'manual_verified':0,'duplicate_manifest_uuids':duplicates,
                'courses':{c:dict(Counter(r['status'] for r in records.values() if r['course']==c)) for c,_t,_m in COURSES}},
            'questions':list(records.values())}
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        self.stdout.write(json.dumps({'output':str(output),**report['summary']},ensure_ascii=False))
