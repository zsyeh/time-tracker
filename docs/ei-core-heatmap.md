# Five-course core heatmap

Route: `/core-heatmap` (EI only). API: `/api/drill/heatmap/?collection=core_selected&mode=questions`.

The union of the five selected manifests includes only `tier=core`, deduplicated by original UUID. It creates no questions, attempts, assets or schema. Existing progress, mastery and timing are scoped to the current user and the visible original questions. Filters: course, all/past/mock, and own question/answer material without unresolved errata (`material=ready`, default) versus all core questions.

Question navigation carries the collection, course, scope and material filters. Returning to the heatmap preserves these filters and highlights the original question. The page reuses the Drill progress and book/timing cards.

Initial manifest totals (2026-10-26): circuit 123, signal 169, analog 63, digital 42, communication 32; total 429. These are curated priorities, not exam probabilities. Material availability is **not** individual verification of completeness or answer matching. The page explicitly states that importance, question/diagram completeness and answer completeness need a separate audit. Do not call an image-presence check a passed visual review.

Checks: `python manage.py test drill.test_core_selected`; full Drill regression; frontend type/build; read-only desktop/mobile browser QA. Production deployment must first push GitHub, then fast-forward VPS, collect static and gracefully reload Gunicorn; never replace the production database.
