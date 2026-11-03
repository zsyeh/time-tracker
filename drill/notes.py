"""Canonical per-question note helpers.

Attempt text fields are retained as immutable legacy evidence, while all new
free-form text is accumulated in ``QuestionUserState.note``.
"""

MAX_QUESTION_NOTE_LENGTH = 20_000


def merge_note_values(*values):
    """Join distinct non-empty values without duplicating earlier migrations."""
    merged = []
    for raw in values:
        value = str(raw or '').strip()
        if not value:
            continue
        existing = '\n\n'.join(merged)
        # A previous run may already have appended this source as one paragraph
        # of the canonical Note. Compare paragraph boundaries instead of only
        # whole strings so applying the command twice is genuinely idempotent.
        if existing and f'\n\n{value}\n\n' in f'\n\n{existing}\n\n':
            continue
        merged.append(value)
    return '\n\n'.join(merged)


def legacy_attempt_texts(attempt):
    return (
        attempt.note,
        attempt.correction_note,
        attempt.knowledge_note,
        attempt.first_step_note,
    )
