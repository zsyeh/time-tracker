# COPY-01 — Account-saved image copy multiplier

Implemented: Settings → Practice preferences → Image copy scale. Quick choices
1×/2×/3×/4×; Custom accepts finite numeric1–8 including decimals, saved explicitly
with Save scale. The selected multiplier is saved to the account and shared by
Drill/EI. Default remains1; old presets/pending queues remain intact.

- Server field `practice.image_copy_scale`, schema1 additive JSON, **no DB migration**.
- Manual/navigation copying and generated fallback PNG sharing/download use the scale.
- Single PNG at1× preserves original bytes. Higher scales create a PNG with width and
  height multiplied; more pixels do not recover image detail. Destination applications
  can still rescale pasted content; no fixed on-screen physical size is promised.
- Upscaled output has16Mi pixels/8192width/16384height limits, maintaining aspect ratio
  and reporting limits rather than cropping. This bounds output canvas allocations;
  source decode still consumes memory. Source images and learning records are unchanged.
- Synchronous `clipboard.write(ClipboardItem({'image/png':BlobPromise}))` is retained
  for gesture-sensitive browsers. No pre-copy awaited fetch was introduced.
- Account persistence/field-CAS/isolation/offline retry use the existing preference API.
  Invalid large integer inputs return400; changing the question/scale invalidates
  fallback caches and guards late completions.

## Verification

- Entire frontend:62files/320tests passed; both production builds/typechecks passed.
- Dedicated backend:35PG passed;34SQLite passed/1PG-concurrency skip.
- Independent review:51focused frontend tests; both findings fixed/read-reviewed.
- Real PNG generation/decode in Chromium and WebKit:320×180 becomes640×360 at2×,
  960×540 at3×,1280×720 at4× and480×270 at1.5×. Two pages at3× yield960×1080.
- Real DjangoHTTP+PG/WebKit:custom3.5 saved in Drill, observed in EI on another browser
  context; another account stays1. Existing theme/font/sidebar/preset/offline checks
  and7viewport states×5font sizes pass. Custom controls checked375/820/1180, no overflow.
- Engine QA is not a physical iPadOS system clipboard or target-application paste test.
  Browser PNG checks do not claim OS clipboard readback.

Evidence: [PNG dimensions](browser-png.json), [account sync](browser-sync.json),
[frontend](frontend.log), [PG](backend-postgres.log), [SQLite](backend-sqlite.log),
[large integer regression](bigint-regression.log). Browser scripts need local Vite8031
and disposable Django/PG8027 respectively. Session files stay private outside Git.

## Release

Deployed source`89d52bd`, image`time-tracker-ha:20261113-copy-scale-89d52bd`,
healthy,OOM=false,deploy-exit0, no planned migration operations, queue succeeded.
[Release record](release.json). Final HTTPS checks:31core and8preference groups passed;
custom3.5 is observed from both workspaces, independent accounts remain1, stale
same-field update409s, invalid9/huge-integer requests400. Private shell bootstrap also
contains3.5 before the appearance script. Temporary users/sessions are cleaned in finally.
[Core smoke](production-smoke.json),[preference smoke](preferences-smoke.json),
[98edge three current asset hashes](edge-static.json),[changed files](CHANGED_FILES.txt).

Rollback on47 (application/PWA/queue only, never reverse DB or overwrite study rows):

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/copy-scale-89d52bd/deploy/ha/round2-rollback.sh \
 /var/snap/docker/common/time-tracker-ha/backups/round2-copy-scale-20261113
```

This restores46e9d81. A fresh pre-cutover preference dump and app/queue/PWA metadata
are retained privately; the previously verified full DB dump is referenced by symlink,
not misrepresented as a new full backup. Synthetic375/820/1180 screenshots are uploaded
to`eh@20.222.88.115:/home/eh/learning-os-round2-screenshots/copy-scale/`.

The existing Round2 report remains a dated record of46e9d81; its native-device and
performance gaps are not silently closed by this incremental feature.
