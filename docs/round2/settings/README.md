# Round 2 — account preferences and Timer Settings

Owner: `plan_review`. Implementation handed back to root for shared UI integration;
no production change, commit or learning-record mutation was performed by this owner.

## SYNC01–04 backend

Files:

- `tracker/models.py`: new `UserPreferences` only.
- `tracker/migrations/0022_userpreferences.py`: additive OneToOne table.
- `tracker/user_preferences.py`: validation, defaults, owner-only service and API view.
- `tracker/test_user_preferences.py`: security, conflict and migration regressions.

Root owns production URL registration, `auth_session`, server-first HTML injection
and every frontend preference store. The view is exported as `UserPreferencesView`;
read-only hooks use `preferences_snapshot(user)`.

GET returns `{schema_version, revision, values, field_revisions}`. PATCH accepts only
`{schema_version:1, changes:{...}, base_revisions:{...}}`. Base keys must exactly match
changed keys. A global compare-and-swap makes each JSON merge atomic; per-field
revisions permit independent changes from stale global snapshots. A same-field
conflict returns HTTP409 and typed `{code, conflicts, current}`. No field in a failed
multi-field update is saved. No-op updates do not advance revision or create a row.

The fixed allowlist covers independent Appearance/Accent/Font/Language; workspace
sidebar configuration; explicitly saved Drill/EI filter presets; the three existing
shared practice preferences and workspace-specific copy modes. Runtime environment,
secrets, arbitrary user selectors and transient windows/menu/scroll/page/index-version
state are rejected. Sidebar order accepts a unique known subset and appends missing
manifest IDs; each workspace sidebar is one atomic field. Settings/account/workspace
links are outside this configurable manifest. Presets are limited to ten per workspace,
names to80 code points, query text to120 code points and request/stored payloads to32KiB.

Every API request is authenticated with the existing session mechanism; PATCH requires
CSRF. Responses are `private, no-store` and vary by Cookie. GET and server HTML hooks
never create rows and never read a device cookie as account authority.

### Executed tests

| Lane | Result |
|---|---|
| Initial SQLite, `tracker.test_user_preferences` | 21 tests,20 passed and1 PostgreSQL concurrency-only skip;0.866s |
| Initial isolated PostgreSQL, same module | 21/21 passed;2.567s |
| Final SQLite, expanded module | 30 tests,29 passed and1 PostgreSQL concurrency-only skip;3.284s |
| Final isolated PostgreSQL, expanded module | 30/30 passed;5.502s |
| `makemigrations tracker --check --dry-run` | No changes detected |

The PostgreSQL test uses two independent connections synchronized before the actual
UPDATE: different fields both survive; competing changes to one field yield exactly
one success and one conflict. Injected CAS races also run on SQLite. Real session/CSRF,
two-user isolation, stale whole-document rejection, typed conflict recovery and bounds
are covered. Both database lanes execute migration forward/reverse and verify source
Question UUID, Attempt outcome and duration, saved Note, TimeLog UUID and content.
Reversing0022 drops preferences only. Ordinary deployment rollback should retain the
new table and run the prior image; restoring old learning data is unnecessary.

The tests ran in disposable local containers/databases. Django destroyed the isolated
test database afterward. They are not claims of production migration execution.

Final logs: [SQLite](backend-sqlite-final.log), [PostgreSQL](backend-postgres-final.log).
The nine additional regressions cover real session middleware account affinity (an old
tab bound to A cannot read or PATCH preferences after another tab signs in as B), the
new course/material/tier/kind/combined/state/scope/bucket preset fields, new-client
round-trip and owner isolation, Timer/Drill/EI account-specific SSR, JSON script escaping,
public/anonymous bootstrap, auth/admin template ordering, non-cacheable auth session
refresh and logout cookie clearing on local, subdomain and apex hosts.

The SSR tests prove the account JSON is emitted before the synchronous appearance
script, and that public pages use an explicit null bootstrap even with an authenticated
cookie. They do not independently measure first paint. The initial logout regression
incorrectly expected anonymous `/api/auth/session/` to return200; it was corrected to
the existing authenticated API contract (403, no preferences) before the passing runs.
Review found an apex-domain cookie deletion omission; root fixed it and the final
regression covers `ehzsy.site` as well as `timer.ehzsy.site`.

## BUG01 / BUG05 Timer Settings

The old built application reproduced the actual defect with synthetic capabilities:
`.token-row` used `minmax(0,1fr) auto auto`, so status and a long unwrapped action group
took nearly all available width. At1180px the name column was45.7px, although the page
had **no horizontal overflow**. At1440px it was97.7px. Checking only document overflow
would have missed the failure.

Classification links previously called `scrollIntoView` while route query changes could
reset scroll. Every section remained expanded. The implementation now has independent
top-level panels selected with `v-show`, with URL query and legacy hash compatibility.
Account/general, appearance, instance, privacy, access, data, organization, invitations
and shortcuts remain available. Instance remains superuser-only. Mobile includes the
previously missing access and permitted instance entries. Existing handlers, permissions
and form models are retained; v-show preserves mounted controls and unsaved values.

Capability status stays beside its title, while actions use a full second row. Long
names/URI content wrap within bounded containers. Local component styles cover these
layouts; this owner did not modify shared/global CSS.

### Evidence

- [Reproducible browser script](browser_settings.py): all API traffic is synthetic;
  requests to any non-local origin are aborted. Capability URI strings use
  `example.invalid/SYNTHETIC-NOT-A-SECRET` and cannot contact a real capability.
- [Before](before/results.json): old built application, Light/Dark ×390/820/1180/1440px.
- [Intermediate after](after-structural/results.json): the isolated structural build,
  before root's final shared settings widgets. All8 cases pass: one active panel,
  stable target position, readable title column, no document/URI overflow, all actions
  within the viewport and no browser errors. Build hashes are recorded in each JSON.
- Five new Timer component tests pass; the runner also matched two existing Drill
  Settings tests, so the command returned7/7 across2 files in5.71s. Tests check all
  section routes, legacy hashes, ordinary-account restrictions, complete mobile choices,
  original actions remaining present and unsaved form values surviving navigation.

| Viewport | Title width before | Structural after | Target top after selection |
|---|---:|---:|---:|
|390px|362px|362px|193px|
|820px|149.7px|665.6px|189px|
|1180px|45.7px|585.6px|113px|
|1440px|97.7px|613.6px|113px|

Screenshots were visually inspected, including the1180px before/after and390px dark
URI dialog. The script waits for the Element Plus enter transition before capturing
the dialog; a mounted box during a transparent animation is not accepted as screenshot
evidence. All displayed URI content is synthetic.

Root subsequently identified and fixed an existing shared style which colored nested
primary-button labels as secondary text. That shared correction is outside the isolated
structural build and requires the final integrated screenshot run. Physical Safari/PWA
keyboard and first-paint behavior are not established by Chromium emulation.

### Final integrated browser verification

[Final results](after-final/results.json) and the accompanying16 PNGs use root's Timer
production bundle with the shared preference widgets, sidebar and font system. All8
cases pass (Light/Dark ×390/820/1180/1440px): one active shortcuts panel, no JavaScript
errors, no document or URI overflow, all capability actions within the viewport, and
all three synthetic URI fields remain bounded. Title widths are362/665.6/585.6/613.6px;
panel top positions are217/217/189/189px. The additional sync status accounts for the
position change relative to the intermediate build. The1180px Light screenshot shows
the primary label in white; the390px Dark dialog was also visually inspected.

Built `index.html` SHA256:
`79b8d32e188210547c6653ca3e7cb6439bb8e66e37c6a945919dd28d65f786d1`.
The browser fixture uses the complete14-field preference schema and denies preference
writes. The only synthetic write is the intercepted capability regeneration that returns
`example.invalid` URIs. No production token, account preference or learning record was
read or changed. A later bundle requires its own risk-based rerun; these results refer
to the recorded build hash, not automatically to every subsequent build.
