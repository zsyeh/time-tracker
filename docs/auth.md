# Authentication and authorization

## Browser sessions

Normal browser access uses Django sessions and DRF `SessionAuthentication`. The
old fixed `Authorization` header gate is removed. Cookies are HttpOnly, Secure in
production, and SameSite=Lax. `SESSION_REMEMBER_DAYS` controls the maximum trusted
device lifetime; django-allauth asks whether the user wants to be remembered.
Public signup is disabled by the project account adapter. Administrators create
accounts through Django admin or `createsuperuser`.

All session, issue, knowledge-point, token, analytics, and export querysets filter
by `request.user`. Foreign-key validation also rejects cross-user session/parent
references.

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
