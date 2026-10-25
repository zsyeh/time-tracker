"""Append explicitly reviewed floating answer figures; never guess figure boxes."""
import hashlib,json
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction

from drill.models import Question,QuestionAsset,QuestionRevision
from drill.pdf_import import stable_source_id


class Command(BaseCommand):
    help='Append allowlisted answer figures from the original PDF, with dry-run as default.'

    def add_arguments(self,parser):
        parser.add_argument('--manifest',type=Path,required=True)
        parser.add_argument('--source',type=Path,required=True)
        parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        m=json.loads(options['manifest'].read_text());source=options['source']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=m['source_sha256']:raise CommandError('Source PDF hash mismatch.')
        prepared=[];seen=set()
        with pymupdf.open(source) as pdf:
            for row in m['regions']:
                if not row.get('review_reason') or not row.get('figure_label'):raise CommandError('Explicit visual review evidence is required.')
                q=Question.objects.get(uuid=row['uuid'],fingerprint=row['fingerprint'],document__workspace='ei')
                key=(q.pk,row['position'])
                if key in seen:raise CommandError('Duplicate figure position.')
                seen.add(key);page=pdf[row['page_index']];rect=pymupdf.Rect(row['bbox'])
                if rect.is_empty or not page.rect.contains(rect):raise CommandError('Invalid reviewed bbox.')
                sid=stable_source_id('ei-reviewed-selected-answer-figure-v1',str(q.uuid),m['source_sha256'],row['figure_label'],json.dumps(row['bbox']),180)
                pix=page.get_pixmap(dpi=180,clip=rect,alpha=False);blob=pix.tobytes('png');sha=hashlib.sha256(blob).hexdigest()
                existing=QuestionAsset.objects.filter(source_id=sid).first()
                if existing and (existing.question_id!=q.pk or existing.sha256!=sha or existing.asset_type!='answer_crop' or existing.position!=row['position']):raise CommandError('Existing figure identity conflict.')
                if q.assets.filter(asset_type='answer_crop',position=row['position']).exclude(source_id=sid).exists():raise CommandError('Answer position already occupied.')
                prepared.append((q,row,sid,blob,sha,pix.width,pix.height))
        new=[p for p in prepared if not QuestionAsset.objects.filter(source_id=p[2]).exists()]
        summary={'dry_run':not options['apply'],'figures':len(prepared),'new_images':len(new),'new_bytes':sum(len(p[3]) for p in new)}
        if options['apply']:
            with transaction.atomic():
                qids={q.pk for q,*_rest in prepared}
                list(Question.objects.select_for_update(no_key=True).filter(pk__in=qids).order_by('pk'))
                for q in Question.objects.filter(pk__in=qids):QuestionRevision.capture(q)
                for q,row,sid,blob,sha,w,h in prepared:
                    if q.assets.filter(asset_type='answer_crop',position=row['position']).exclude(source_id=sid).exists():raise CommandError('Concurrent answer position change.')
                    x0,y0,x1,y1=row['bbox']
                    QuestionAsset.objects.get_or_create(source_id=sid,defaults=dict(question=q,asset_type='answer_crop',position=row['position'],image_data=blob,sha256=sha,
                        width=w,height=h,source_page_index=row['page_index'],source_x0=x0,source_y0=y0,source_x1=x1,source_y1=y1,render_dpi=180))
                for q in Question.objects.filter(pk__in=qids):QuestionRevision.capture(q)
        self.stdout.write(json.dumps(summary))
