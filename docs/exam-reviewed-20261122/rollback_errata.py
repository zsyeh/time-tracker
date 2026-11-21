"""Run inside the production image with PYTHONPATH=/app.

Default is verification only. ROOT must contain plan.json, applied.json and
backup/rows.json from ONE approved repair batch. --apply restores canonical
content, not old paper pins or user learning data. Never deletes binaries.
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
from drill.models import Question, QuestionAsset, QuestionErratum, QuestionRevision

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('root', type=Path)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
plans = json.loads((args.root / 'plan.json').read_text())
results = {r['question_id']: r for r in json.loads((args.root / 'applied.json').read_text())}
backups = {r['question']['id']: r for r in json.loads((args.root / 'backup/rows.json').read_text())}
with transaction.atomic():
    for plan in plans:
        qid = plan['question_id']
        result, backup = results[qid], backups[qid]
        q = Question.objects.select_for_update().get(pk=qid)
        assert q.fingerprint == backup['question']['fingerprint']
        assert QuestionRevision.capture(q).pk == result['new_revision'], ('content changed after repair', qid)
        erratum = QuestionErratum.objects.select_for_update().get(pk=plan['erratum_id'], question=q)
        assert erratum.status == 'resolved' and erratum.resolution == plan['resolution']
        originals = {a['id']: a for a in backup['assets']}
        for asset in q.assets.filter(pk__in=originals):
            assert asset.sha256 == originals[asset.pk]['sha256']
            assert hashlib.sha256(bytes(asset.image_data)).hexdigest() == asset.sha256
        for asset_id in result['new_assets']:
            asset = q.assets.get(pk=asset_id)
            assert hashlib.sha256(bytes(asset.image_data)).hexdigest() == asset.sha256
        if args.apply:
            for asset in q.assets.filter(pk__in=originals):
                old = originals[asset.pk]
                asset.asset_type, asset.position = old['asset_type'], old['position']
                asset.save(update_fields=['asset_type', 'position'])
            for asset_id in result['new_assets']:
                asset = q.assets.get(pk=asset_id)
                asset.asset_type += '_superseded'
                asset.save(update_fields=['asset_type'])
            for field in plan['question_updates']:
                setattr(q, field, backup['question'][field])
            if plan['question_updates']:
                q.save(update_fields=list(plan['question_updates']))
            old = backup['erratum']
            erratum.status, erratum.resolution = old['status'], old['resolution']
            erratum.resolved_at = old['resolved_at']
            erratum.save(update_fields=['status', 'resolution', 'resolved_at', 'updated_at'])
            restored = QuestionRevision.capture(q)
            assert restored.pk == result['old_revision'], ('restored revision mismatch', qid)
        print(json.dumps({'question_id': qid, 'mode': 'apply' if args.apply else 'verify', 'verified': True}))
    if not args.apply:
        transaction.set_rollback(True)  # verification must leave no revision write behind
