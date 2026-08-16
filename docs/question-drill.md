# Question drill

The drill is a separate Vue SPA served only on a configured drill hostname. It
shares Django authentication and PostgreSQL with the Timer application, while
keeping its routes, bundle, navigation, and visual system independent.

Existing Passkeys are bound to the Timer WebAuthn relying-party domain and
cannot be replayed directly on a sibling hostname. An anonymous Drill page
therefore redirects through the Timer login page, where the existing Passkey is
valid, then returns through a 90-second one-time handoff. Only the handoff hash
is stored, it is deleted when consumed, external return URLs are rejected, and
the Nginx example disables access logging for the completion path. This avoids
changing the WebAuthn RP ID or widening the session cookie to every subdomain.

## Data model

- `QuestionDocument` and `QuestionTopic` preserve the imported source hierarchy.
- `Question` has a deterministic UUID and a normalized similarity topic.
- `QuestionAsset` stores the verified PNG bytes in PostgreSQL and is fetched only
  from an authenticated, immutable-cache endpoint.
- `QuestionAttempt` belongs to one user. Frequencies, results, progress, and the
  past-paper heatmap are therefore isolated between accounts.

The supplied bank imports as 8 documents, 861 topics, 3,553 questions, and 4,123
PNG crops. The past-paper classifier recognizes a four-digit year immediately
associated with a Mathematics I/II/III label; descriptions that merely mention a
year elsewhere are not included in the heatmap.

## Normalized import

The idempotent command accepts four JSON Lines files (`documents.jsonl`,
`nodes.jsonl`, `questions.jsonl`, and `assets.jsonl`) plus the source asset root:

```bash
python manage.py import_question_bank /safe/export/normalized \
  --assets-root /safe/export/assets
```

Every PNG signature and SHA-256 digest is checked before the surrounding
transaction commits. Re-running the same import updates metadata and skips
unchanged image bytes without duplicating questions, topics, or assets. Always
take a PostgreSQL backup before importing a replacement bank.

## Routes

- `/practice` — catalog and filters
- `/practice/<question_uuid>` — stable question detail and similar set
- `/heatmap` — per-user past-paper frequency heatmap
- `/api/drill/catalog/` — lightweight books and topics
- `/api/drill/questions/` — paginated lightweight summaries
- `/api/drill/questions/<uuid>/` — detail and authenticated asset URLs
- `/api/drill/questions/<uuid>/attempts/` — create one frequency event
- `/api/drill/questions/<uuid>/similar/` — same-topic questions
- `/api/drill/heatmap/` — compact per-user heatmap cells
