# Architecture

Personal Learning OS remains a monorepo and a modular monolith.

```text
Browser -> Nginx/TLS -> Vue static shell + Django same-origin API
                              |
                        relational database
```

- Django owns authentication, authorization, validation, persistence, analytics,
  exports, launch capabilities, and Passkey integration.
- Vue 3/Vite + Vue Router own authenticated `/today`, `/trends`, `/sessions`,
  `/sessions/<uuid>`, `/issues`, and `/settings` resources plus the isolated
  anonymous `/share/<token>` reader.
- Django admin and django-allauth templates remain server-rendered recovery paths.
- SQLite remains supported for safe in-place migration. PostgreSQL is supported
  through environment configuration and is preferred for new production installs.
- No server-side AI provider or model API is part of the architecture.
- Django's shared file cache keeps short-lived per-user overview aggregates;
  `TimeLog` signals invalidate them across Gunicorn workers. Redis is unnecessary
  at the current scale.
- The optional MCP process is a local protocol adapter over the same deterministic
  data and is not an embedded AI service.

The deployment stays same-origin to minimize round trips and avoid CORS, cookie,
CSRF, and WebAuthn relying-party complexity.

Optional per-user encryption at rest is implemented at the Django model boundary.
Small summary and long content payloads are encrypted separately, so archive
lists decrypt only the title payload while trends continue to query indexed
operational metadata without cryptographic work. Detail, search, export, GitHub
sync, and public-share serializers receive transparently decrypted model values.
The server key is deliberately retained outside the database; this preserves
features but means the mode is not end-to-end encryption.

Shortcut automation uses two independently randomized, unauthenticated bearer
capabilities per configured device: one can only start its bound subject and one
can only increment the current Session's disturbance aggregate. Only digests are
stored. Pause and the daily availability window are checked transactionally.
Disturbances update a bounded counter with one indexed write and deliberately
bypass duration-stat recomputation; no unbounded event stream is retained.

Django uses explicit SPA history fallback routes instead of a wildcard, so a
direct Session/share refresh serves the Vue shell without consuming `/api/`,
`/admin/`, `/accounts/`, `/start/`, or `/launch/` endpoints. Public share API
requests omit browser credentials and remain identical for logged-in and
anonymous visitors.
