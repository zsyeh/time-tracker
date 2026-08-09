# REST API

All endpoints below require a Django session and CSRF protection unless marked
public. Every response is restricted to the authenticated owner.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/auth/session/` | User and CSRF bootstrap |
| POST | `/api/auth/logout/` | End browser session |
| GET/POST | `/api/sessions/` | Paginated search / start session |
| GET/PATCH | `/api/sessions/<id>/` | Read/edit owned session |
| POST | `/api/sessions/<id>/finish/` | Finish with a title and details body |
| POST | `/api/sessions/<id>/abandon/` | Permanently delete the running session |
| GET | `/api/dashboard/overview/?days=180` | One-request dashboard analytics |
| GET/POST | `/api/issues/` | Learning issue list/create |
| GET/PATCH/DELETE | `/api/issues/<id>/` | Learning issue detail |
| GET/POST | `/api/launch-tokens/` | Manage scoped tokens |
| POST | `/api/launch-tokens/<id>/<action>/` | `revoke`, `regenerate`, `delete` |
| GET | `/api/export/csv/` | Flat complete export |
| GET | `/api/export/json/` | Nested complete export |
| GET | `/api/export/markdown/` | Human-readable export |
| POST | `/api/launch/<token>/start` | Public, token-scoped IoT start |

Session/export filters: `subject`, `status`, `date_from`, `date_to`, and `search`.
Use `compact=1` on the session list to return only timeline metadata and `title`;
fetch `/api/sessions/<id>/` only when the full `details` body is opened.
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
