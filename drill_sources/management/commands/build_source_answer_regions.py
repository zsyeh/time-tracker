import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from drill_sources.answer_segmentation import build_answer_manifest


class Command(BaseCommand):
    help = 'Match existing EI question identities to numbered answer regions; offline, no database writes.'

    def add_arguments(self, parser):
        parser.add_argument('index', type=Path)
        parser.add_argument('--source-manifest', type=Path, action='append', required=True)
        parser.add_argument('--ocr-cache', type=Path, required=True)
        parser.add_argument('--margin-cache', type=Path)
        parser.add_argument('--output', type=Path, required=True)

    def handle(self, *args, **options):
        try:
            manifest = build_answer_manifest(options['index'], options['source_manifest'],
                                             options['ocr_cache'], options['margin_cache'])
            options['output'].write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
            self.stdout.write(json.dumps(manifest['counts']))
        except (ValueError, OSError, KeyError, IndexError) as error:
            raise CommandError(str(error)) from error
