"""Verify and idempotently import a locally prepared EI question package."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from drill.digital_892_package import import_package


class Command(BaseCommand):
    help = 'Validate checksums and import reviewed EI crops without OCR or PDF parsing.'

    def add_arguments(self, parser):
        parser.add_argument('package', type=Path)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            result = import_package(options['package'], dry_run=options['dry_run'])
        except (ValueError, KeyError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"new={result['new']} updated={result['updated']} assets={result['assets']} written={result['written']}")
