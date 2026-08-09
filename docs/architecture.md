# Architecture

Personal Learning OS remains a monorepo and a modular monolith.

```text
Browser -> Nginx/TLS -> Vue static shell + Django same-origin API
                              |
                        relational database
```

- Django owns authentication, authorization, validation, persistence, analytics,
  exports, launch capabilities, and Passkey integration.
- Vue 3/Vite owns the authenticated dashboard experience.
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
