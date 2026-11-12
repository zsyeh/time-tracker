# Account preferences — integration evidence

`chromium.json` and `webkit.json` were executed against Django HTTP + PostgreSQL15
on isolated database `learning_os_round2_sync`, with real session authentication,
CSRF tokens and PATCH/GET (not an in-memory mocked preferences API). Three browser
contexts represent two devices for one synthetic account and a separate account.
No production user or learning record was modified.

Five checks cover cross-device theme/font, account isolation, first paint before
main-module execution, explicitly saved filter reapplication, sidebar visibility
and order, offline optimistic edits/online replay, and seven viewport/rotation
states × all five font sizes. No document overflow or JavaScript error occurred.
WebKit is the Linux Playwright engine, **not physical iPadOS Safari**.

`browser_sync.py` uses local-only staging at127.0.0.1:8027. Its session file in the
private directory is generated using Django SessionStore for synthetic users;
it is deliberately excluded from Git. Start `manage.py runserver --noreload` with
DEBUG=true and a disposable database, migrate throughtracker0022, then generate
that session file. The script emulates the production Nginx `/drill/api/` stripping
by forwarding those requests to the same local Django `/api/`. Application JSON,
query handling, CSRF, ORM writes and server bootstrap remain real.

Example: `ROUND2_ENGINE=webkit <playwright-venv>/bin/python docs/round2/sync/browser_sync.py`.
Run against disposable synthetic users only. It creates/modifies their preferences
and recovery metadata. Screenshots remain outside Git to keep the report small.

Store tests independently use deferred network responses and field-CAS snapshots
for stale GET/200/409 ordering, reverse user intent during writes, cached queues,
identity header pinning, two-device conflicts, debounce, failures and logout.

Historical unscoped practice keys are never silently copied to a possibly different
account. Settings offers an explicit one-time import/discard choice. Existing
Drill/EI shared next-mode and auto-next semantics and independent copy modes remain.
