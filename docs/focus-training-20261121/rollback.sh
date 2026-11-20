#!/bin/sh
set -eu
backup=/var/snap/docker/common/time-tracker-ha/backups/round2-focus-training-20261121
release=/var/snap/docker/common/time-tracker-ha/releases/focus-training-36efc8f
sh "$release/deploy/ha/round2-rollback.sh" "$backup"
if test -e "$backup/old-papers-deleted.txt"; then
 /usr/local/bin/time-tracker-docker exec -i -w /app time-tracker-ha-web python manage.py loaddata --format=json - < "$backup/deleted-old-papers.json"
fi
/usr/local/bin/time-tracker-docker exec -i -w /app time-tracker-ha-web python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','time_server.settings')
import django;django.setup()
from drill.models import ExamBlueprint
from django.db import transaction
with transaction.atomic():
 ExamBlueprint.objects.filter(code__startswith='math2-focus-').update(is_active=False)
 ExamBlueprint.objects.filter(subject='math2',version=1).update(is_active=True)
print('Old blueprint availability restored; newer learning data retained.')
PY
