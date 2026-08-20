#!/usr/bin/env python3
"""Import self-contained question/answer image pairs from the answer books.

Only labels with a question image followed by at least one answer image are
accepted.  Existing source labels are treated as duplicates, so this is an
additive recovery path for content absent from the original question export.
"""
import hashlib
import os
import re
import sys
import uuid
from pathlib import Path

import django
import pymupdf
from django.db import transaction

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'work' / 'answer_sources'
BOOKS = {1:'极限答案册.pdf',2:'一元积分题库-答案.pdf',3:'线代1000题参考答案.pdf',4:'二重积分题库答案.pdf',5:'多元微分大观-答案.pdf',6:'微分方程大观-答案.pdf',7:'反常积分-答案.pdf',9:'一元微分大观-答案.pdf'}

def norm(s):
    return ''.join(re.findall(r'[a-z0-9\u4e00-\u9fff]+', (s or '').casefold()))

def sid(*parts):
    return int.from_bytes(hashlib.sha256('\x1f'.join(map(str,parts)).encode()).digest()[:8], 'big') & ((1<<63)-1) or 1

def main(dry_run=False, only_document=None):
    django.setup()
    from drill.cleaning import classify_source
    from drill.models import Question, QuestionAsset
    existing = {}
    for q in Question.objects.select_related('document').all():
        existing.setdefault((q.document_id, norm(q.source_label)), []).append(q.id)
    candidates=[]
    for document_id, filename in BOOKS.items():
        if only_document is not None and document_id != only_document:
            continue
        with pymupdf.open(SOURCE/filename) as doc:
            for page_no,page in enumerate(doc,1):
                page_text=page.get_text('text',sort=True)
                if '目录' in page_text and page_text.count('>>')>2: continue
                labels=[]
                for block in page.get_text('blocks',sort=True):
                    text=block[4].replace('\n',' ').strip()
                    if '>>' in text and len(norm(text))>=5: labels.append((block[1],text))
                if not labels: continue
                image_blocks = [
                    block for block in page.get_text('dict', sort=True)['blocks']
                    if block['type'] == 1
                    and block['bbox'][2] - block['bbox'][0] > 80
                    and block['bbox'][3] - block['bbox'][1] > 40
                ]
                page_xrefs = page.get_images(full=True)
                # The PDF writer preserves image object order in the content
                # stream.  Pairing it with text-dict image blocks avoids the
                # native-memory growth of get_image_info(xrefs=True).
                images = [
                    (block['bbox'][1], image[0])
                    for block, image in zip(image_blocks, page_xrefs)
                ]
                images.sort()
                for index,(y,label) in enumerate(labels):
                    end=labels[index+1][0] if index+1<len(labels) else page.rect.height-20
                    xrefs=[xref for iy,xref in images if y < iy < end]
                    if len(xrefs)<2: continue
                    key=(document_id,norm(label))
                    if key in existing: continue
                    candidates.append((document_id,filename,page_no,label,xrefs))
    print({'recovered_candidates':len(candidates),'dry_run':dry_run})
    if dry_run: return
    from drill.models import QuestionDocument
    with transaction.atomic():
        pdfs = {}
        try:
            for order,(document_id,filename,page_no,label,xrefs) in enumerate(candidates,1):
                document=QuestionDocument.objects.get(pk=document_id)
                fingerprint=hashlib.sha256(f'answer-book-pair:{filename}:{page_no}:{label}'.encode()).hexdigest()
                question,created=Question.objects.get_or_create(fingerprint=fingerprint,defaults={
                'uuid':uuid.uuid5(uuid.NAMESPACE_URL,'https://drill.ehzsy.site/recovered/'+fingerprint),
                'document':document,'question_order':100000+order,'source_label':label,
                'display_label':classify_source(label).display_label,'prompt_text':label,
                'latex_text':'','content_mode':'image','confidence':0.94,
                'is_past_exam':classify_source(label).is_past_exam,'source_category':classify_source(label).category,
                'record_kind':'question','is_practiceable':True,'classification_reason':'recovered from answer-book pair','classification_confidence':0.94,
                })
                if not created: continue
                doc = pdfs.setdefault(filename, pymupdf.open(SOURCE/filename))
                for position,xref in enumerate(xrefs):
                    pix=pymupdf.Pixmap(doc,xref)
                    data=pix.tobytes('png'); digest=hashlib.sha256(data).hexdigest()
                    QuestionAsset.objects.create(source_id=sid('answer-book',filename,page_no,label,position),question=question,position=position if position else 0,asset_type='question_crop' if position==0 else 'answer_crop',sha256=digest,mime_type='image/png',image_data=data,width=pix.width,height=pix.height,source_page_index=page_no-1,render_dpi=180)
        finally:
            for pdf in pdfs.values(): pdf.close()
    print({'imported':len(candidates)})

if __name__=='__main__':
    selected = next((int(arg.split('=', 1)[1]) for arg in sys.argv if arg.startswith('--document=')), None)
    main('--dry-run' in sys.argv, selected)
