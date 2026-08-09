# Data model

## Study session (`TimeLog`)

`TimeLog` remains the physical model/table to preserve primary keys and historical
foreign references. In product/API language it is exposed as a study session.
It stores an owner, subject, start/end timestamps, status, a `title`, a `details`
body, legacy reflection fields, and optional metadata. Duration is derived from the
timestamps; there is no second authoritative duration column.

Migration `0010` renames the historical `note` column to `title` without rewriting
its contents, then adds an initially empty `details` body. Only sessions lasting
at least 25 minutes and no more than 12 hours can become completed records.
Explicit discard deletes the running row, so `abandoned` is retained only as a
legacy schema value and is not written by current application flows.

## Learning issue

Optional user-owned structured problem connected to a study session when useful.
Issue type, description, solution, repeat count, and resolved state are retained.

## Knowledge point (legacy)

The historical table is retained to avoid destructive data loss, but it is no
longer exposed in the current navigation. `LearningIssue` is the active structured
follow-up model.

## Launch token

Stores only a SHA-256 digest of a 32-byte random capability. It is user-owned,
subject-scoped, revocable, optionally expiring/use-limited, and can only start a
session. Raw tokens are shown once and never persisted.

## Passkey credential

Passkey/WebAuthn credentials are managed by django-allauth MFA. Only public
credential material and counters are stored; authenticator private keys never
reach the server.
