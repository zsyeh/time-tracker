"""Restore only horizontal margins of allowlisted answers; retain old binaries."""
import hashlib
import json
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction

from drill.models import Question,QuestionAsset,QuestionAttempt,QuestionUserState,QuestionRevision,QuestionRevisionAsset
from drill.pdf_import import stable_source_id


class Command(BaseCommand):
    help='Restore full PDF width for explicitly reviewed answer regions, with exact hash guards and immutable revisions.'

    def add_arguments(self,parser):
        parser.add_argument('--manifest',type=Path,required=True)
        parser.add_argument('--source',type=Path,required=True)
        parser.add_argument('--dry-run',action='store_true')

    def handle(self,*args,**options):
        manifest=json.loads(options['manifest'].read_text());source=options['source']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['source_sha256']:raise CommandError('Source PDF hash mismatch.')
        prepared=[];seen=set()
        with pymupdf.open(source) as pdf:
            for row in manifest['regions']:
                if row['asset_source_id'] in seen:raise CommandError('Duplicate source asset.')
                seen.add(row['asset_source_id'])
                q=Question.objects.get(uuid=row['uuid'],fingerprint=row['fingerprint'],document__workspace='ei')
                old=QuestionAsset.objects.get(source_id=row['asset_source_id'],question=q)
                if old.sha256!=row['old_sha256'] or hashlib.sha256(bytes(old.image_data)).hexdigest()!=row['old_sha256']:raise CommandError('Old image hash changed.')
                if old.asset_type not in {'answer_crop','answer_crop_superseded'}:raise CommandError('Only answer crops can be widened.')
                if old.source_page_index!=row['page_index']:raise CommandError('Source page changed.')
                old_bbox=[old.source_x0,old.source_y0,old.source_x1,old.source_y1]
                if old_bbox!=row['old_bbox']:raise CommandError('Old bbox changed.')
                page=pdf[row['page_index']];bbox=row['bbox'];rect=pymupdf.Rect(bbox)
                if bbox[0]!=0 or abs(bbox[2]-page.rect.width)>0.01 or bbox[1]!=old_bbox[1] or bbox[3]!=old_bbox[3]:raise CommandError('Repair must change horizontal margins only, to full page width.')
                if not page.rect.contains(rect) or rect.is_empty:raise CommandError('Invalid crop bbox.')
                dpi=old.render_dpi or 150
                pix=page.get_pixmap(dpi=dpi,clip=rect,alpha=False);blob=pix.tobytes('png');sha=hashlib.sha256(blob).hexdigest()
                sid=stable_source_id('ei-reviewed-fullwidth-answer-v1',str(q.uuid),old.source_id,manifest['source_sha256'],json.dumps(bbox),dpi)
                existing=QuestionAsset.objects.filter(source_id=sid).first()
                if existing and (existing.question_id!=q.pk or existing.sha256!=sha or existing.asset_type!='answer_crop'):raise CommandError('Repaired asset identity conflict.')
                conflicts=q.assets.filter(asset_type='answer_crop',position=old.position).exclude(source_id__in=[old.source_id,sid])
                if conflicts.exists():raise CommandError('Unexpected answer crop at this position.')
                prepared.append((q,old,row,sid,blob,sha,pix.width,pix.height,dpi))
        qids={q.pk for q,*_rest in prepared}
        new=[p for p in prepared if not QuestionAsset.objects.filter(source_id=p[3]).exists()]
        summary={'dry_run':options['dry_run'],'questions':len(qids),'regions':len(prepared),'new_images':len(new),'new_bytes':sum(len(p[4]) for p in new),'old_images_retained':len(prepared)}
        if options['dry_run']:
            self.stdout.write(json.dumps(summary));return
        with transaction.atomic():
            list(Question.objects.select_for_update(no_key=True).filter(pk__in=qids).order_by('pk'))
            attempts=set(QuestionAttempt.objects.filter(question_id__in=qids).values_list('pk',flat=True))
            states=set(QuestionUserState.objects.filter(question_id__in=qids).values_list('pk',flat=True))
            links=list(QuestionRevisionAsset.objects.filter(revision__question_id__in=qids).order_by('pk').values_list('pk','asset_id','asset_type','position'))
            for q in Question.objects.filter(pk__in=qids):QuestionRevision.capture(q)
            for q,old,row,sid,blob,sha,width,height,dpi in prepared:
                locked=QuestionAsset.objects.select_for_update().get(pk=old.pk)
                if locked.sha256!=row['old_sha256'] or locked.asset_type not in {'answer_crop','answer_crop_superseded'}:raise CommandError('Concurrent source asset change.')
                QuestionAsset.objects.filter(pk=old.pk).update(asset_type='answer_crop_superseded')
                x0,y0,x1,y1=row['bbox']
                QuestionAsset.objects.get_or_create(source_id=sid,defaults=dict(question=q,asset_type='answer_crop',position=old.position,
                    image_data=blob,sha256=sha,width=width,height=height,source_page_index=row['page_index'],
                    source_x0=x0,source_y0=y0,source_x1=x1,source_y1=y1,render_dpi=dpi))
                if hashlib.sha256(bytes(QuestionAsset.objects.get(pk=old.pk).image_data)).hexdigest()!=row['old_sha256']:raise CommandError('Old binary preservation failed.')
            for q in Question.objects.filter(pk__in=qids):QuestionRevision.capture(q)
            if QuestionAttempt.objects.filter(pk__in=attempts).count()!=len(attempts):raise CommandError('Attempt preservation failed.')
            if QuestionUserState.objects.filter(pk__in=states).count()!=len(states):raise CommandError('State preservation failed.')
            current=list(QuestionRevisionAsset.objects.filter(pk__in=[r[0] for r in links]).order_by('pk').values_list('pk','asset_id','asset_type','position'))
            if current!=links:raise CommandError('Revision link preservation failed.')
        summary.update(attempts_preserved=len(attempts),states_preserved=len(states),existing_revision_links_preserved=len(links))
        self.stdout.write(json.dumps(summary))
