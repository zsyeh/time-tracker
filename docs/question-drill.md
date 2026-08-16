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
  Separate display titles remove PDF table-of-contents leaders without replacing
  raw provenance.
- `Question` has a deterministic UUID, a normalized similarity topic, a cleaned
  display label, a provenance category, and a record kind.
- `QuestionAsset` stores the verified PNG bytes in PostgreSQL and is fetched only
  from an authenticated, immutable-cache endpoint.
- `QuestionAttempt` belongs to one user. Frequencies, results, progress, and the
  past-paper heatmap are therefore isolated between accounts. A reset is an
  append-only state marker; undo removes only the latest marker and restores the
  previous state.

The supplied bank imports as 8 documents, 861 topics, 3,553 source records, and
4,123 PNG crops. Cleanup currently identifies 3,208 practiceable records and 345
high-confidence source-outline rows. It separates 1,013 official past-exam
records, 2 adapted exam records, 95 mock-paper records, 1,783 workbook records,
31 competition records, and 284 practiceable records whose provenance is not
safe to infer. The classifier recognizes an exam year immediately associated
with Mathematics I/II/III; descriptions that merely mention a year elsewhere
are not included in the official heatmap.

The original `/root/Downloads.7z` contains limits, single-variable integration,
linear algebra, double integration, multivariable differentiation, differential
equations, and improper integration. It does **not** contain a single-variable
differentiation PDF. The catalog reports this source gap explicitly instead of
pretending that a filter or importer lost those questions.

## Formula fidelity

A PDF produced by LaTeX does not retain the original TeX source. These PDFs mix
embedded raster questions, vector glyphs, subset fonts, and text with imperfect
Unicode maps. The normalized export contains zero non-empty `latex_text` values.
Consequently the authenticated PNG crop remains the canonical renderer: it
preserves the exact formula instead of presenting math OCR as trusted TeX. The
question page labels the render source. Supplying the original `.tex` files (or a
reviewed math-OCR export) is required before exact structured LaTeX can replace
the crops safely.

## Reversible cleanup

Raw filenames, topic titles, source labels, and extracted text are never
overwritten. Rebuild display metadata and inspect the resulting counts with:

```bash
python manage.py clean_question_bank --dry-run
python manage.py clean_question_bank
```

Rules are intentionally conservative: official exams, adapted exams, mock
papers, workbooks, and competitions require explicit source markers. Anything
else remains `Unclassified`. Only a small single crop that repeats a source
outline heading is hidden as a `section`; grouped extracts remain practiceable
and are labelled.

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
- `POST /api/drill/questions/<uuid>/attempts/` — set mastered/review/reset state
- `DELETE /api/drill/questions/<uuid>/attempts/` — undo the latest state change
- `/api/drill/questions/<uuid>/similar/` — same-topic questions
- `/api/drill/heatmap/` — compact per-user official-exam state cells
