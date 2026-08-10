# REST API

All endpoints below require a Django session and CSRF protection unless marked
public. Every response is restricted to the authenticated owner.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/auth/session/` | User and CSRF bootstrap |
| POST | `/api/auth/logout/` | End browser session |
| GET/POST | `/api/sessions/` | Paginated search / start session |
| GET/PATCH | `/api/sessions/<id>/` | Read/edit owned session |
| GET/POST | `/api/sessions/<id>/reviews/` | Read trend / record a deduplicated review visit |
| POST | `/api/sessions/<id>/finish/` | Finish with a title and details body |
| POST | `/api/sessions/<id>/abandon/` | Permanently delete the running session |
| GET | `/api/dashboard/overview/?days=180` | One-request dashboard analytics |
| GET/PUT | `/api/settings/runtime/` | Read or atomically update allow-listed local `.env` display settings |
| GET | `/api/search/?q=<keyword>&limit=18` | Bounded global text search summaries |
| GET/POST | `/api/issues/` | Learning issue list/create |
| GET/PATCH/DELETE | `/api/issues/<id>/` | Learning issue detail |
| GET/POST | `/api/launch-tokens/` | Manage scoped tokens |
| POST | `/api/launch-tokens/<id>/<action>/` | `revoke`, `regenerate`, `delete` |
| GET/POST | `/api/invite-codes/` | Administrator-only list/generate invite codes |
| POST | `/api/invite-codes/<id>/revoke/` | Administrator-only invite revocation |
| GET | `/api/export/csv/` | Flat complete export |
| GET | `/api/export/json/` | Nested complete export |
| GET | `/api/export/markdown/` | Human-readable export |
| POST | `/api/launch/<token>/start` | Public, token-scoped IoT start |

Session/export filters: `subject`, `status`, `date_from`, `date_to`, and `search`.
Use `compact=1` on the session list to return only timeline metadata and `title`;
fetch `/api/sessions/<id>/` only when the full `details` body is opened.

Opening a completed session review posts one review visit. Visits by the same
owner within ten minutes are deduplicated. The response contains the lifetime
count and a bounded 90-day daily trend; compact session summaries contain only
the denormalized count and last-review timestamp.

Invite APIs require `is_staff`. The raw invite code is returned only by the
create response; subsequent list responses expose metadata, use counts, expiry,
and availability but never the raw secret or its digest.

Global search spans owned completed-session text and owned Issues. It returns at
most 24 mixed summary records and never includes a complete session `details`
body; the client fetches the owned detail endpoint only after selection.

Runtime settings expose only homepage content, study-room code, tracking start
date, exam date, and countdown label. Unknown dotenv entries are never returned
and are preserved during updates. Docker stores the managed file in its data
volume; local installs use the project `.env` unless `TRACKER_LOCAL_ENV_PATH` is
set.
History is paginated. A duplicate start for the same running subject returns that
session with `reused: true`; a different running subject returns HTTP 409 and is
never silently stopped.

For an eligible session, the finish endpoint requires non-empty `title` and
`details`. A finish attempt before 25 elapsed minutes or after 12 elapsed hours
deletes the session and returns `discarded: true` with `discard_reason`; it never
creates a completed or abandoned record. Historical structured fields remain in
exports for compatibility but are not required by current completion flows.

The knowledge-point tables and endpoints are retained as a legacy compatibility
surface, but they are no longer linked from the product UI. `Issues` is the one
active structured learning follow-up feature.
