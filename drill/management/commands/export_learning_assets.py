"""Read-only manifest/tar export from the authoritative PostgreSQL asset table."""
import hashlib
import io
import json
import sys
import tarfile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from drill.models import QuestionAsset


class Command(BaseCommand):
    help = 'Stream a SHA-256 asset manifest or selected verified assets as tar to stdout.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--manifest', action='store_true')
        group.add_argument('--ids', help='Comma-separated positive asset IDs for tar export')

    def handle(self, *args, **options):
        if options['manifest']:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT a.id, d.workspace, a.sha256, length(a.image_data), a.mime_type
                    FROM drill_questionasset a JOIN drill_question q ON q.id = a.question_id
                    JOIN drill_questiondocument d ON d.id = q.document_id ORDER BY a.id''')
                for asset_id, workspace, digest, size, mime in cursor:
                    self.stdout.write(json.dumps({'id': asset_id, 'workspace': workspace,
                        'sha256': digest, 'size': size, 'mime_type': mime}, separators=(',', ':')))
            return
        values = options['ids'].split(',')
        if len(values) > 500 or not values or any(not v.isdecimal() or int(v) <= 0 for v in values):
            raise CommandError('Provide 1–500 numeric asset IDs.')
        assets = QuestionAsset.objects.filter(pk__in=[int(v) for v in values]).select_related('question__document')
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as archive:
            for asset in assets.iterator(chunk_size=20):
                data = bytes(asset.image_data)
                digest = hashlib.sha256(data).hexdigest()
                if digest != asset.sha256:
                    raise CommandError(f'Asset {asset.pk} SHA-256 mismatch; export stopped.')
                path = f'{asset.question.document.workspace}/{asset.pk}/{digest}'
                info = tarfile.TarInfo(path)
                info.size = len(data)
                info.mode = 0o444
                archive.addfile(info, io.BytesIO(data))
