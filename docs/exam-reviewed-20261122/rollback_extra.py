"""Verify/restore the separate audited type edits or the final #92 crop.
Uses private backup paths; default read-only. Does not change any paper pin.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')
import django
django.setup()
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from drill.models import Question, QuestionAsset, QuestionRevision, QuestionExamType, QuestionErratum
from drill.exam_type_views import snapshot

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('kind', choices=['metadata', 'crop92'])
p.add_argument('backup', type=Path)
p.add_argument('--apply', action='store_true')
a = p.parse_args()
with transaction.atomic():
    if a.kind == 'metadata':
        old = json.loads(a.backup.read_text())
        expected = {6234: 'fill', 5708: 'judgment', 6953: 'large'}
        c = APIClient()
        # Identity derives from the original report, never an arbitrary account.
        e = QuestionErratum.objects.select_for_update().get(pk=84)
        assert e.status == 'resolved' and e.reporter_id is not None
        c.force_authenticate(user=get_user_model().objects.get(pk=e.reporter_id))
        for row in old['types']:
            q = Question.objects.select_for_update().get(pk=row['question_id'])
            record = QuestionExamType.objects.get(question=q)
            assert record.question_type == expected[q.pk], ('type subsequently changed', q.pk)
            if a.apply:
                response = c.patch(f'/api/drill/questions/{q.uuid}/exam-type/', {
                    'question_type': row['question_type'],
                    'expected_updated_at': snapshot(record)['updated_at'],
                }, format='json', HTTP_HOST='ei.ehzsy.site')
                assert response.status_code == 200, response.data
        if a.apply:
            prev = next(x for x in old['errata'] if x['id'] == 84)
            e.status, e.resolution, e.resolved_at = prev['status'], prev['resolution'], prev['resolved_at']
            e.save(update_fields=['status', 'resolution', 'resolved_at', 'updated_at'])
    else:
        old = json.loads((a.backup / 'q6244-before.json').read_text())
        result = json.loads((a.backup / 'q6244-applied.json').read_text())
        q = Question.objects.select_for_update().get(pk=6244)
        assert QuestionRevision.capture(q).pk == result['new_revision']
        asset = QuestionAsset.objects.get(pk=27057, question=q)
        assert hashlib.sha256(bytes(asset.image_data)).hexdigest() == old['asset']['sha256']
        new = QuestionAsset.objects.get(pk=result['new_asset'], question=q, asset_type='answer_crop')
        e = QuestionErratum.objects.select_for_update().get(pk=result['erratum_id'], status='resolved')
        if a.apply:
            asset.asset_type = old['asset']['asset_type'];asset.save(update_fields=['asset_type'])
            new.asset_type = 'answer_crop_superseded';new.save(update_fields=['asset_type'])
            e.status = 'open';e.resolution = '';e.resolved_at = None
            e.save(update_fields=['status', 'resolution', 'resolved_at', 'updated_at'])
            assert QuestionRevision.capture(q).pk == result['old_revision']
    if not a.apply:
        transaction.set_rollback(True)
print(json.dumps({'verified': True, 'kind': a.kind, 'applied': a.apply}))
