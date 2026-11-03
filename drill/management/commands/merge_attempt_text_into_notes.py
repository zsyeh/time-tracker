import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from drill.models import QuestionAttempt, QuestionUserState
from drill.notes import MAX_QUESTION_NOTE_LENGTH, legacy_attempt_texts, merge_note_values


class Command(BaseCommand):
    help = 'Dry-run, apply, or roll back legacy attempt free text into canonical question Notes.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--audit-file')
        parser.add_argument('--rollback')

    @staticmethod
    def _write_audit(path, payload):
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', dir=target.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
                stream.write('\n')
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _rollback(self, audit_path):
        payload = json.loads(Path(audit_path).read_text(encoding='utf-8'))
        changes = payload.get('changes') or []
        restored = 0
        with transaction.atomic():
            for change in changes:
                state = QuestionUserState.objects.select_for_update().filter(
                    user_id=change['user_id'], question_id=change['question_id'],
                ).first()
                if state is None:
                    raise CommandError('Rollback target is missing; refusing a partial rollback.')
                if state.note != change['after']:
                    raise CommandError(
                        f"Note changed after migration for user={change['user_id']} "
                        f"question={change['question_id']}; refusing to overwrite it."
                    )
                state.note = change['before']
                state.version += 1
                state.save(update_fields=['note', 'version', 'updated_at'])
                restored += 1
        self.stdout.write(self.style.SUCCESS(f'Rolled back {restored} canonical Notes.'))

    def handle(self, *args, **options):
        if options['rollback']:
            if options['apply'] or options['audit_file']:
                raise CommandError('--rollback cannot be combined with --apply/--audit-file.')
            return self._rollback(options['rollback'])
        if options['apply'] and not options['audit_file']:
            raise CommandError('--apply requires --audit-file so every changed Note is recoverable.')

        from django.db.models import Q
        attempts = QuestionAttempt.objects.filter(
            (Q(note__isnull=False) & ~Q(note='')) |
            ~Q(correction_note='') |
            ~Q(knowledge_note='') |
            ~Q(first_step_note='')
        ).order_by('user_id', 'question_id', 'created_at', 'pk')
        grouped = defaultdict(list)
        sources = defaultdict(list)
        for attempt in attempts.iterator():
            key = (attempt.user_id, attempt.question_id)
            values = [value for value in legacy_attempt_texts(attempt) if str(value or '').strip()]
            for value in values:
                value = str(value).strip()
                if value not in grouped[key]:
                    grouped[key].append(value)
            if values:
                sources[key].append({'attempt_id': attempt.pk, 'fields': {
                    name: value for name, value in zip(
                        ('note', 'correction_note', 'knowledge_note', 'first_step_note'),
                        legacy_attempt_texts(attempt),
                    ) if str(value or '').strip()
                }})

        states = {
            (state.user_id, state.question_id): state
            for state in QuestionUserState.objects.filter(
                user_id__in={key[0] for key in grouped},
                question_id__in={key[1] for key in grouped},
            )
        }
        changes = []
        for (user_id, question_id), values in grouped.items():
            before = states.get((user_id, question_id)).note if (user_id, question_id) in states else ''
            after = merge_note_values(before, *values)
            if after == before:
                continue
            if len(after) > MAX_QUESTION_NOTE_LENGTH:
                raise CommandError(
                    f'Merged Note would be {len(after)} characters for user={user_id}, '
                    f'question={question_id}; no data was changed.'
                )
            changes.append({
                'user_id': user_id,
                'question_id': question_id,
                'state_existed': (user_id, question_id) in states,
                'before': before,
                'after': after,
                'sources': sources[(user_id, question_id)],
            })

        summary = {
            'candidate_pairs': len(grouped),
            'changed_pairs': len(changes),
            'new_state_rows': sum(not row['state_existed'] for row in changes),
            'existing_state_rows': sum(row['state_existed'] for row in changes),
            'max_merged_length': max((len(row['after']) for row in changes), default=0),
        }
        self.stdout.write(json.dumps(summary, ensure_ascii=False))
        for row in changes[:5]:
            self.stdout.write(json.dumps({
                'user': f"u***{str(row['user_id'])[-2:]}",
                'question': f"q***{str(row['question_id'])[-3:]}",
                'before_length': len(row['before']),
                'after_length': len(row['after']),
                'source_attempts': len(row['sources']),
            }, ensure_ascii=False))
        if not options['apply']:
            self.stdout.write('Dry-run only; no database rows were changed.')
            return

        audit_path = Path(options['audit_file']).expanduser().resolve()
        if audit_path.exists():
            if changes:
                raise CommandError(
                    'Audit file already exists and there are pending changes; choose a new protected path.'
                )
            self.stdout.write(self.style.SUCCESS(
                'Merged 0 canonical Notes; existing audit file was preserved.'
            ))
            return

        audit = {
            'format': 'time-tracker-note-merge-v1',
            'created_at': timezone.now().isoformat(),
            'status': 'prepared',
            'summary': summary,
            'changes': changes,
        }
        self._write_audit(audit_path, audit)
        with transaction.atomic():
            for change in changes:
                state, _ = QuestionUserState.objects.select_for_update().get_or_create(
                    user_id=change['user_id'], question_id=change['question_id'],
                )
                current = state.note or ''
                after = merge_note_values(current, *[
                    value
                    for source in change['sources']
                    for value in source['fields'].values()
                ])
                if len(after) > MAX_QUESTION_NOTE_LENGTH:
                    raise CommandError('Concurrent Note growth exceeded the safe limit; rolled back.')
                if after != current:
                    state.note = after
                    state.version += 1
                    state.save(update_fields=['note', 'version', 'updated_at'])
        audit['status'] = 'applied'
        audit['applied_at'] = timezone.now().isoformat()
        self._write_audit(audit_path, audit)
        self.stdout.write(self.style.SUCCESS(f"Merged {len(changes)} canonical Notes."))
