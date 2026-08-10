# Authentication and authorization

## Browser sessions

Normal browser access uses Django sessions and DRF `SessionAuthentication`. The
old fixed `Authorization` header gate is removed. Cookies are HttpOnly, Secure in
production, and SameSite=Lax. `SESSION_REMEMBER_DAYS` controls the maximum trusted
device lifetime; django-allauth asks whether the user wants to be remembered.
The signup page is public, but account creation requires a valid administrator-
issued invite code. Only staff users can generate or revoke invites from the
authenticated Settings page/API or the dedicated Django Admin invitation
dashboard. Codes are random, stored only as SHA-256 digests, optionally
expiring, configurable for 1–100 uses, and the raw value is displayed once.
Administrators can inspect remaining capacity, redemption timestamps, and the
username created by each redemption.

All session, issue, knowledge-point, token, analytics, and export querysets filter
by `request.user`. Foreign-key validation also rejects cross-user session/parent
references.

Public support pages do not grant application access. `/guide/` is read-only.
`/contact/` uses CSRF protection, a honeypot, per-network rate limiting, and
SMTP delivery to the administrator; contact text is not stored in the tracker
database.

## Passkeys

django-allauth MFA owns WebAuthn registration and authentication. The application
does not implement cryptography. Password login remains available for recovery.
Users enroll and remove authenticators at `/accounts/2fa/`.

For the best iPhone/iPad flow, sign in with the password once on that device and
open `/accounts/2fa/webauthn/add/` to save a Passkey in iCloud Keychain. Later
logins use the prominent Passkey button and invoke the native Face ID/Touch ID
sheet. A QR code is an operating-system cross-device fallback: it can still be
shown when no local credential exists or the user chooses another device.

Production requirements:

- HTTPS at the public origin;
- `DJANGO_ALLOWED_HOSTS` contains the exact host;
- `CSRF_TRUSTED_ORIGINS` contains the HTTPS origin;
- Nginx forwards `Host` and `X-Forwarded-Proto`;
- never enable `MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN` outside `DEBUG`.

## Launch tokens

A launch token is not a login. It stores only a SHA-256 digest of at least 32
random bytes and can only start its bound subject. It cannot read dashboard data,
notes, exports, account details, Passkeys, or other tokens. Revocation/expiry is
checked inside a database transaction and takes effect immediately. Raw tokens
are shown only on create/regenerate and should be treated like physical keys.
