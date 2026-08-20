import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from drill.models import Question


class Command(BaseCommand):
    help = 'Import reviewed Markdown/LaTeX Agent solutions from JSONL by stable question UUID.'

    def add_arguments(self, parser):
        parser.add_argument('jsonl', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--overwrite', action='store_true')

    def handle(self, *args, **options):
        path = options['jsonl'].expanduser().resolve()
        if not path.is_file():
            raise CommandError(f'JSONL file does not exist: {path}')
        rows = []
        seen = set()
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(f'Invalid JSON at line {line_number}: {exc}') from exc
            uuid = str(row.get('question_uuid', ''))
            markdown = str(row.get('answer_markdown', '')).strip()
            confidence = row.get('confidence')
            if not uuid or not markdown:
                raise CommandError(f'Line {line_number} requires question_uuid and answer_markdown.')
            if uuid in seen:
                raise CommandError(f'Duplicate question_uuid at line {line_number}: {uuid}')
            if confidence is None or not 0 <= float(confidence) <= 1:
                raise CommandError(f'Line {line_number} confidence must be between 0 and 1.')
            seen.add(uuid)
            rows.append((uuid, markdown, float(confidence), str(row.get('source') or 'agent-reviewed')[:32]))

        questions = {str(item.uuid): item for item in Question.objects.filter(uuid__in=[row[0] for row in rows])}
        missing = sorted(seen - questions.keys())
        if missing:
            raise CommandError(f'Unknown question UUID(s): {missing[:5]}')
        blocked = [uuid for uuid, *_rest in rows if questions[uuid].answer_markdown and not options['overwrite']]
        if blocked:
            raise CommandError(f'{len(blocked)} question(s) already have Agent solutions; use --overwrite explicitly.')
        self.stdout.write(json.dumps({'validated': len(rows), 'dry_run': options['dry_run']}))
        if options['dry_run']:
            return
        now = timezone.now()
        with transaction.atomic():
            for uuid, markdown, confidence, source in rows:
                question = questions[uuid]
                question.answer_markdown = markdown
                question.answer_confidence = confidence
                question.answer_source = source
                question.answer_generated_at = now
                question.save(update_fields=(
                    'answer_markdown', 'answer_confidence', 'answer_source', 'answer_generated_at',
                ))
        self.stdout.write(self.style.SUCCESS(f'Imported {len(rows)} Agent Markdown solutions.'))
