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
| POST | `/api/sessions/<id>/finish/` | Finish with a title and details body |
| POST | `/api/sessions/<id>/abandon/` | Permanently delete the running session |
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

Session/export filters: `subject`, `status`, `date_from`, `date_to`, and `search`.
The session list returns only timeline metadata, UUID, title, and review counters
by default. Fetch `/api/sessions/<uuid>/` only when the full `details` body is
opened. `compact=1` remains accepted and `full=1` explicitly requests the legacy
full-list payload for transitional clients.

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

Global search spans owned completed-session text and owned Issues. It returns at
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

For an eligible session, the finish endpoint requires non-empty `title` and
`details`. A finish attempt before 25 elapsed minutes or after 12 elapsed hours
deletes the session and returns `discarded: true` with `discard_reason`; it never
creates a completed or abandoned record. Historical structured fields remain in
exports for compatibility but are not required by current completion flows.

The knowledge-point tables and endpoints are retained as a legacy compatibility
surface, but they are no longer linked from the product UI. `Issues` is the one
active structured learning follow-up feature.
