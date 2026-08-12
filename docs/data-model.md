# Data model

## Study session (`TimeLog`)

`TimeLog` remains the physical model/table to preserve primary keys and historical
foreign references. In product/API language it is exposed as a study session.
It stores an owner, subject, start/end timestamps, status, a `title`, a `details`
body, legacy reflection fields, and optional metadata. Duration is derived from the
timestamps; there is no second authoritative duration column.
Each row also has a unique immutable UUID used by `/sessions/<uuid>` and the
owner-scoped detail API. Integer primary keys remain unchanged for internal
relationships and compatibility; complete domain URLs are never stored.
The denormalized `review_count` and `last_reviewed_at` fields make archive lists
cheap to render; append-only `SessionReview` rows retain the bounded trend source.
Repeated opens within ten minutes do not create another event.

## Task presets and study tags

`TaskPreset` is a user-owned, subject-bound tree node with an immutable UUID and
a protected self-parent relationship. API validation caps the custom tree at
four levels, prevents cycles/cross-owner parents, and keeps active children from
being orphaned. Any node can be a homepage shortcut and can carry default tags.
Used presets are archived rather than removed.

`StudyTag` is a reusable user-owned blog-style content label. Tags have a small
display color and may be attached to both presets and completed Sessions. The
Session stores a nullable preset relation plus an encrypted `task_path` snapshot,
so renaming or archiving a preset does not rewrite historical classification.
Task/tag relations stay queryable for aggregation. Preset names, tag names, and
the path snapshot follow the user's optional at-rest encryption policy.

## Session share

`SessionShare` is an explicit public capability linked to a Session. It stores a
SHA-256 digest of a 32-byte random token, creation/optional expiry/revocation
timestamps, and active state. A conditional unique constraint allows only one
active share per Session. Raw tokens are returned once and never stored. A share
does not change Session ownership or grant write access; the public API projects
only the small article field whitelist.

## Optional encryption at rest

`UserDataEncryptionPreference` is a per-user, default-off storage policy. When it
is enabled, `TimeLog` stores title/chapter/topic in `encrypted_summary` and long
Markdown, reflection, and personal rating fields in `encrypted_content`.
`LearningIssue` stores its private text in a separate encrypted payload, and
`GitHubNoteSync` protects paths and error text that may contain a title. The
original protected columns are cleared, while owner, UUID, subject, timestamps,
status, duration inputs, and relationship keys remain queryable operational
metadata. Payloads use AES-256-GCM with random nonces and per-user keys derived
from a server master key; ciphertext is authenticated and non-deterministic.

The key is stored outside PostgreSQL and database backups. Django can still
decrypt it, so this is not end-to-end or zero-knowledge encryption. ORM/API reads,
exports, GitHub Markdown, and explicit public shares continue to produce readable
content. Losing the server key makes encrypted records unrecoverable.

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

Stores separate SHA-256 digests for two 32-byte random capabilities: subject-
scoped Session start and current-Session disturbance recording. It is user-owned,
temporarily pausable, revocable, optionally expiring/start-use-limited, and has a
daily availability window defaulting to 06:00–22:00 Asia/Shanghai. Raw tokens are
shown once and never persisted. `TimeLog.disturbance_count` and
`last_disturbance_at` retain a bounded aggregate instead of an indefinitely
growing event table.

## Passkey credential

Passkey/WebAuthn credentials are managed by django-allauth MFA. Only public
credential material and counters are stored; authenticator private keys never
reach the server.
