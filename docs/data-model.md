# Data model

## Study session (`TimeLog`)

`TimeLog` remains the physical model/table to preserve primary keys and historical
foreign references. In product/API language it is exposed as a study session.
It stores an owner, subject, chapter/topic, start/end timestamps, status, learning
mode, reflection fields, and optional self-ratings. Duration is derived from the
timestamps; there is no second authoritative duration column.

## Learning issue

Optional user-owned structured problem connected to a study session when useful.
Issue type, description, solution, repeat count, and resolved state are retained.

## Knowledge point

Optional user-owned hierarchical map with importance, status, self-assigned
mastery, review count, and last-reviewed timestamp.

## Launch token

Stores only a SHA-256 digest of a 32-byte random capability. It is user-owned,
subject-scoped, revocable, optionally expiring/use-limited, and can only start a
session. Raw tokens are shown once and never persisted.

## Passkey credential

Passkey/WebAuthn credentials are managed by django-allauth MFA. Only public
credential material and counters are stored; authenticator private keys never
reach the server.
