# Data model

## Study session (`TimeLog`)

`TimeLog` remains the physical model/table to preserve primary keys and historical
foreign references. In product/API language it is exposed as a study session.
It stores an owner, subject, start/end timestamps, status, a `title`, a `details`
body, legacy reflection fields, and optional metadata. Duration is derived from the
timestamps; there is no second authoritative duration column.
The denormalized `review_count` and `last_reviewed_at` fields make archive lists
cheap to render; append-only `SessionReview` rows retain the bounded trend source.
Repeated opens within ten minutes do not create another event.

Migration `0010` renames the historical `note` column to `title` without rewriting
its contents, then adds an initially empty `details` body. Only sessions lasting
at least 25 minutes and no more than 12 hours can become completed records.
Explicit discard deletes the running row, so `abandoned` is retained only as a
legacy schema value and is not written by current application flows.

## GitHub note sync

`GitHubNoteSync` is a durable one-to-one outbox record created only when a new
session becomes completed. It tracks the generated Markdown path, target branch, retry count,
last error, and synchronization timestamp. Existing historical sessions are not
backfilled automatically. A failed GitHub operation never rolls back or removes
the completed learning record. Staff/superuser sessions target the configured
main branch; all other sessions target a Git-safe branch derived from username.
The configured main branch name is reserved so an ordinary username cannot
collide with it.

## Invite and redemption

`InviteCode` stores only a SHA-256 digest plus label, issuer, expiry, use limit,
and revocation state. Self-service codes also store their Asia/Shanghai issue
date and are constrained to one use; a conditional unique constraint permits
only one self-service code per issuer and day. `InviteRedemption` links the
consumed capability to the new account and timestamp for auditability without
retaining the raw code.

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
