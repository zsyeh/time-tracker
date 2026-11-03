# Drill / EI reliability release runbook

This release assumes `47.95.10.128` is the only Django and PostgreSQL writer.
RainYun may terminate TLS and proxy requests, but must not serve a local Django
process or writable application database. Nothing in this runbook authorizes a
production migration, restart, or topology change.

## Pre-deployment read-only checks

1. Run `deploy/ha/audit-single-writer.sh` with `TIME_TRACKER_EDGE_SSH` set.
2. Confirm the application `DATABASE_URL` on 47 resolves to the local writer,
   `pg_is_in_recovery() = false`, and `transaction_read_only = off`.
3. Confirm RainYun has no PostgreSQL/Django listener and proxies all three
   public hosts to `47.95.10.128:443`.
4. Confirm the legacy marker
   `/etc/time-tracker/legacy-ha-explicitly-enabled` does not exist anywhere.
5. Take one consistent PostgreSQL backup and record the deployed image tag.

The read-only audit on 2026-11-02 found legacy lease/tunnel units on RainYun
and the old monitor on 47 still active. After verifying they are not carrying
application traffic, an explicitly approved maintenance action must stop and
disable those units. Installing the fail-closed unit files alone does not stop
an already-running service. Do not perform this cleanup as part of an
unreviewed web release.

The same audit found two local PostgreSQL listeners on 47: the application
target on `127.0.0.1:55433` is writable, and a separate legacy cluster on 5432
is also writable. The application URL does not target 5432, so no business
dual-write was observed; `pg_stat_activity` showed no other client connection
and its data directory is `/var/lib/postgresql/14/main`. Before declaring the
topology compliant, confirm its consumers and retention need, then stop/archive
it only under explicit operator approval.

## Database migration (requires explicit approval)

Compared with the old GitHub default branch, the deployed code has six
additive/reversible migrations:

- `0025`: formula-review mastery state;
- `0026`: append-only attempt diagnosis and review plans;
- `0027`: legacy method-note evidence fields (kept for history only);
- `0028`: permits the fixed direct-IP authentication handoff target;
- `0029`: adds optimistic state versions and separates manual/system mastery;
- `0030`: adds per-tab question timing sessions.

Run `showmigrations drill`, then `migrate --plan`. Apply once on 47 only. Do
not run migrations on RainYun and do not import/merge another database.

This release also canonicalizes legacy diagnosis free text into the per-question
Note without a schema migration. Take a fresh backup, run
`merge_attempt_text_into_notes` without flags, review its redacted counts, then
use `--apply --audit-file <protected-path>` on 47 only. The audit file contains
the original text needed for rollback and therefore must remain mode 0600 and
must never be committed or copied to RainYun. A second apply must report zero
changed pairs.

## Application and proxy rollout (requires explicit approval)

1. Build an immutable image and run the backend tests and Drill frontend build.
2. Apply the migrations on 47.
3. Replace the 47 web container with the new image; do not change its database
   target. Health-check locally before exposing it.
4. Install the exact `/ip-auth/start` and `/ip-auth/complete` proxy locations.
   They must set `X-Time-Tracker-External-Host` only in the trusted 47 proxy.
5. If RainYun is used, run the certificate sync hook once for all three
   allow-listed lineages to seed 47, then install `nginx-rainyun-edge.conf` and
   the 47 config. Validate each certificate before `nginx -t` and reload. The
   47 IP certificate remains under its independent Let's Encrypt directory.
6. Never log request bodies. The handoff token lives in a URL fragment and is
   removed by the callback page before its POST redemption.

## Verification

- Password login still works independently on the IP host.
- From the IP login page, Passkey redirects to `timer.ehzsy.site`; after a real
  WebAuthn ceremony Safari returns to the original allowed IP path.
- A handoff expires within 90 seconds, cannot be replayed, rejects a wrong
  Origin/Host, and cannot redirect off-site.
- Submit the same client submission key twice in a non-production test account:
  there is one Attempt and one mastery transition.
- A stale note version yields HTTP 409 without overwriting the server note.
- Two tabs have independent timers; Undo rebuilds review/mastery state while
  retaining manual mastery.
- Test bad UI routes plus API 401/403/404/409/429/5xx handling.
- Test widths 390, 768, 834, 1024, and 1440. Complete a physical iPhone/iPad
  Safari pass because Linux automation cannot validate platform Passkeys,
  virtual keyboard, or Safari safe-area behavior.

## Rollback

1. Stop routing new requests to the new web image and restore the previously
   recorded image tag. Do not point traffic at a second database.
2. The new columns/table are additive and old code ignores them, so normally
   leave migrations in place during an emergency application rollback.
3. Reverse migrations only in a maintenance window after confirming no new
   timing sessions/state versions are needed. Restore the pre-release backup if
   and only if an operator has confirmed data restoration is necessary.
4. Do not use the historical promotion/rejoin scripts as a rollback mechanism.
