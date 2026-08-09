# REST API

All endpoints below require a Django session and CSRF protection unless marked
public. Every response is restricted to the authenticated owner.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/auth/session/` | User and CSRF bootstrap |
| POST | `/api/auth/logout/` | End browser session |
| GET/POST | `/api/sessions/` | Paginated search / start session |
| GET/PATCH | `/api/sessions/<id>/` | Read/edit owned session |
| POST | `/api/sessions/<id>/finish/` | Manual structured finish |
| POST | `/api/sessions/<id>/abandon/` | Explicitly abandon |
| GET | `/api/dashboard/overview/?days=180` | One-request dashboard analytics |
| GET/POST | `/api/issues/` | Learning issue list/create |
| GET/PATCH/DELETE | `/api/issues/<id>/` | Learning issue detail |
| GET/POST | `/api/knowledge/` | Knowledge map list/create |
| GET/PATCH/DELETE | `/api/knowledge/<id>/` | Knowledge point detail |
| GET/POST | `/api/launch-tokens/` | Manage scoped tokens |
| POST | `/api/launch-tokens/<id>/<action>/` | `revoke`, `regenerate`, `delete` |
| GET | `/api/export/csv/` | Flat complete export |
| GET | `/api/export/json/` | Nested complete export |
| GET | `/api/export/markdown/` | Human-readable export |
| POST | `/api/launch/<token>/start` | Public, token-scoped IoT start |

Session/export filters: `subject`, `status`, `date_from`, `date_to`, and `search`.
History is paginated. A duplicate start for the same running subject returns that
session with `reused: true`; a different running subject returns HTTP 409 and is
never silently stopped.

The finish endpoint requires `chapter` or `topic`, plus non-empty `note`,
`breakthrough`, `problems`, and `next_action`. Optional self-ratings remain
inspectable data and are not presented as scientific measurements.
