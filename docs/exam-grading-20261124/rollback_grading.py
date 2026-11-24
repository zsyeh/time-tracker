"""Run inside image: python script.py BACKUP_DIR [--apply]. Refuses newer edits."""
import os,json,argparse
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','time_server.settings')
import django;django.setup()
from django.core import serializers
from django.apps import apps
from django.db import transaction
p=argparse.ArgumentParser(description=__doc__);p.add_argument('backup',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
before=json.loads((a.backup/'before.json').read_text());after=json.loads((a.backup/'after.json').read_text())
oldkeys={(r['model'],r['pk']) for r in before}
with transaction.atomic():
 for row in after:
  model=apps.get_model(row['model']);obj=model.objects.select_for_update().get(pk=row['pk'])
  current=json.loads(serializers.serialize('json',[obj]))[0]
  assert current==row,('Record edited after import; stop rollback',row['model'],row['pk'])
 if a.apply:
  for row in reversed(after):
   if (row['model'],row['pk']) not in oldkeys:
    assert row['model'] in ('drill.questionuserstate','drill.questionattempt')
    apps.get_model(row['model']).objects.get(pk=row['pk']).delete()
  for obj in serializers.deserialize('json',json.dumps(before)):obj.save()
print(json.dumps({'verified':True,'applied':a.apply,'rows':len(after)}))
