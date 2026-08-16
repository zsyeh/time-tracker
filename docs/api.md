# REST API

All endpoints below require a Django session and CSRF protection unless marked
public. Every response is restricted to the authenticated owner.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/auth/session/` | User and CSRF bootstrap |
| POST | `/api/auth/logout/` | End browser session |
| GET/POST | `/api/sessions/` | Paginated search / start session |
| GET/PATCH | `/api/sessions/<uuid>/` | Read/edit owned permanent session resource |
| GET/PATCH | `/api/sessions/<id>/` | Legacy integer lookup retained for compatibility |
| GET/POST | `/api/sessions/<uuid>/reviews/` | Read trend / record a deduplicated review visit |
| GET/POST | `/api/sessions/<id>/reviews/` | Read trend / record a deduplicated review visit |
| GET/POST/DELETE | `/api/sessions/<uuid>/share/` | Inspect, create, or revoke an owned session share |
| GET | `/api/public/shares/<token>/` | Public read-only article projection; no authentication |
| POST | `/api/sessions/<id>/finish/` | Finish; optional title/details may be empty and `efficiency_grade` may be A–F |
| POST | `/api/sessions/<id>/abandon/` | Permanently delete the running session |
| GET/POST | `/api/study-tags/` | List/create reusable owned content tags |
| PATCH/DELETE | `/api/study-tags/<id>/` | Edit/delete an unused owned tag |
| GET/POST | `/api/task-presets/` | List/create owned subject task presets |
| PATCH/DELETE | `/api/task-presets/<id>/` | Edit, archive, or remove an owned task preset |
| GET | `/api/completion-options/` | Lazy completion data: active task tree, tags, and eight recent titles |
| GET | `/api/dashboard/overview/?days=180` | One-request dashboard analytics |
| GET/PUT | `/api/settings/runtime/` | Read safe defaults; superusers can atomically update allow-listed local `.env` display settings |
| GET/PUT | `/api/settings/data-encryption/` | Read or toggle the current user's server-managed encryption-at-rest policy |
| GET | `/api/search/?q=<keyword>&limit=18` | Bounded global text search summaries |
| GET/POST | `/api/issues/` | Learning issue list/create |
| GET/PATCH/DELETE | `/api/issues/<id>/` | Learning issue detail |
| GET/POST | `/api/launch-tokens/` | Manage scoped tokens |
| POST | `/api/launch-tokens/<id>/<action>/` | `pause`, `resume`, `regenerate`, `regenerate-disturbance`, `revoke`, `delete` |
| PUT | `/api/launch-tokens/<id>/configure/` | Update the owned capability label, limits, expiry, and daily window |
| GET/POST | `/api/invite-codes/` | Own daily single-use invites; administrators list/generate all configurable invites |
| POST | `/api/invite-codes/<id>/revoke/` | Revoke an owned invite; administrators can revoke any invite |
| GET | `/api/export/csv/` | Flat complete export |
| GET | `/api/export/json/` | Nested complete export |
| GET | `/api/export/markdown/` | Human-readable export |
| POST | `/api/launch/<token>/start` | Public, token-scoped IoT start |
| POST | `/api/disturbance/<token>/record` | Public, separately scoped disturbance counter for the current Session |
| POST | `/api/stress-test/probe/` | Optional bearer-key capacity-test control/metrics endpoint with fixed actions only |

Session/export filters: `subject`, `status`, `tag`, `date_from`, `date_to`, and `search`.
The session list returns only timeline metadata, UUID, title, and review counters
by default. Fetch `/api/sessions/<uuid>/` only when the full `details` body is
opened. `compact=1` remains accepted and `full=1` explicitly requests the legacy
full-list payload for transitional clients.

Task presets belong to one subject and may be nested to four custom levels. A
start request may send `{ "task_preset": <id> }`; the server derives the subject,
copies the current task path onto the Session, and applies the preset's default
tags. The owner can still start with `{ "subject": "math" }` for an unclassified
Session. On completion, `tag_ids` replaces the Session's tag selection. If the
title is blank and the Session came from a preset, the leaf task name becomes the
title; without a preset it remains blank. Preset/tag IDs are always owner-scoped.
Used presets are archived instead of deleting historical classification.

Opening a completed session review posts one review visit. Visits by the same
owner within ten minutes are deduplicated. The response contains the lifetime
count and a bounded 90-day daily trend; compact session summaries contain only
the denormalized count and last-review timestamp.

Ordinary users can create one self-service invite per Asia/Shanghai calendar
day; the server forces it to one use and enforces the quota with a database
unique constraint. Staff retain configurable 1–100-use codes. The raw invite
code is returned only by the create response. Subsequent owned list responses
expose metadata, use counts, availability, and registered usernames/timestamps,
but never the raw secret or digest.

Global search spans owned completed-session text, task paths, tag names, and owned Issues. It returns at
most 24 mixed summary records and never includes a complete session `details`
body; Session results include `session_uuid` so the client navigates directly to
the owned permanent resource.

Session shares are private until the owner explicitly creates one. The create
response reveals the public URL once; only a SHA-256 token digest is persisted.
At most one active capability exists per Session. Revocation is immediate and an
optional future `expires_at` is enforced on every public read. The anonymous
response is a fixed whitelist of `title`, `subject`, start/end timestamps,
derived duration, and `markdown`; it never includes internal IDs, UUIDs, owner,
review, Issue, authentication, or launch data. Public POST/PATCH/DELETE methods
are not implemented.

The data-encryption settings endpoint accepts `{ "enabled": true|false }`. It
rewrites only the authenticated user's protected study content and never returns
key material. AES-256-GCM payloads are transparently decrypted inside Django, so
detail reads, export, GitHub sync, search, and public shares retain their existing
response formats. This is database-at-rest protection, not end-to-end encryption.

Runtime settings expose local homepage content, study-room code, tracking start
date, exam date, and countdown label only to superusers. Ordinary users receive
fixed safe defaults with no private homepage content or study-room code, and
PUT returns HTTP 403. Unknown dotenv entries are never returned and are
preserved during superuser updates. Docker stores the managed file in its data
volume; local installs use the project `.env` unless `TRACKER_LOCAL_ENV_PATH` is
set.
History is paginated. A duplicate start for the same running subject returns that
session with `reused: true`; a different running subject returns HTTP 409 and is
never silently stopped.

Creating a Launch capability returns three one-time values: a browser GET start
URL, a Shortcut-friendly POST start URL, and a separately randomized POST
disturbance URL. Only SHA-256 digests are retained. Authenticated owners can
configure the daily `available_from`/`available_until` window (default
06:00–22:00 Asia/Shanghai), pause/resume without changing installed URLs, rotate
either secret independently, or delete the capability. Equal start/end times mean
all day; a start later than end represents an overnight window. A valid paused or
out-of-window request returns HTTP 200 as a no-op so personal automations do not
fail noisily. Invalid, expired, revoked, exhausted start, and rotated secrets
return 404. Maximum use count applies only to starts.

The disturbance endpoint never starts a Session and never exposes its internal
identifier. It increments `disturbance_count` and updates `last_disturbance_at`
only when the owner has a running Session. With no running Session it returns
`no_active_session`; a running Session older than 12 hours is deleted and returns
`stale_session_discarded`. GET is not accepted for either Shortcut API; configure
the iOS `Get Contents of URL` action to use POST with no body.

The capacity probe is disabled unless `STRESS_TEST_ENABLED=true` and a 32+
character `STRESS_TEST_KEY` is configured. Clients send the key in the
`Authorization: Bearer` header. Disabled and invalid-key requests return 404.
The bounded JSON body accepts only fixed actions: `sample`/`preflight`, `begin`,
`metrics`, `provision`, `prepare_finish`, and `cleanup`. It never accepts a
command, SQL, path, or target URL. Host sampling reads Linux virtual counters;
optional lower-frequency PostgreSQL sampling reads statistics views.

`begin` returns a signed, short-lived run token. Supplying that token as
`X-Load-Test-Run` on a normal authenticated API request enables response timing
headers but grants no authentication or ownership permission. The outer timing
middleware measures Django wall time, request-thread user/system CPU, ORM query
count/write count/time, DRF JSON render time, and an optional trusted-proxy
queue approximation.
Normal traffic without a valid token pays only a disabled header check.

Real workload fixtures require `STRESS_TEST_ALLOW_DATA_SETUP=true`. They use an
exact `loadtest_<run>_*` username prefix, ordinary database sessions/CSRF, and
normal API authorization. Cleanup can only address exact generated numeric
usernames within that run prefix and remains available after fixture creation
is switched off. Test
finishes never enqueue or dispatch GitHub synchronization. Application and
probe per-worker rate limits return 429 above the signed/server cap. No storage
benchmark exists. See [`stress_test/README.md`](../stress_test/README.md) and
[`stress_test/ARCHITECTURE_AUDIT.md`](../stress_test/ARCHITECTURE_AUDIT.md).

For an eligible session, the finish endpoint accepts optional `title` and
`details`; both may be empty. It also accepts `efficiency_grade` with `A` as the
default. Grades A–F map to coefficients `1.00`, `0.95`, `0.90`, `0.85`, `0.80`,
and `0.75`. Authenticated session responses keep the actual `duration_minutes`
and additionally return `efficiency_grade`, `efficiency_coefficient`, and
whole-minute `credited_duration_minutes`. An empty completion still retains subject, timing,
duration, and disturbance metadata, and its GitHub archive uses the safe
`Untitled session` fallback. A finish attempt before 25 elapsed minutes or after 12 elapsed hours
deletes the session and returns `discarded: true` with `discard_reason`; it never
creates a completed or abandoned record. Historical structured fields remain in
exports for compatibility but are not required by current completion flows.

Dashboard, subject, task, tag, heatmap, weekly, and monthly totals use credited
minutes. The 24-hour timeline continues to use the real timestamps. CSV, JSON,
Markdown, and GitHub Markdown retain both actual and credited duration metadata.

The knowledge-point tables and endpoints are retained as a legacy compatibility
surface, but they are no longer linked from the product UI. `Issues` is the one
active structured learning follow-up feature.
