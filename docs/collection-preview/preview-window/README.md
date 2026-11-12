# Collection preview browser evidence

These scripts use synthetic 10,000-entry metadata and dynamic-ratio synthetic PNGs. They are a bounded-window stress fixture, **not real corpus or production performance evidence**. `synthetic-window.py` mounts the actual virtual list and image pipeline with generated items; it is isolated from Question and never starts a timer or writes an Attempt. The separate `real-fixture.py` uses the complete built application against the local isolated database.

Run with Vite Drill dev server on localhost:5187, e.g. existing Docker node22 environment, then:

```sh
/home/eh/ei-page-tracking/browser-env/bin/python docs/collection-preview/preview-window/synthetic-window.py
/home/eh/ei-page-tracking/browser-env/bin/python docs/collection-preview/preview-window/real-fixture.py --source favorite --account 2000 --base http://127.0.0.1:8035/drill
```

`synthetic-window.py` is an isolated virtual-list fixture. It initially verified 10k mixed scan ratios, bidirectional jumps, saved row offsets and width change. `real-practice-5847.json` records the actual App traversing the public Practice5847-question collection under the2000-fixture account; the collection count must not be confused with the number of account favorites. The App automatically persists learning-recovery device state (one PUT), but this run never enters Question or writes an Attempt/timer. Full-view/session evidence is the stronger contract check. Both use Chromium; native iPad Safari/PWA remain separate acceptance gates.

Budgets: default virtual mounted target 20; visible rows are retained even if they exceed that target. Nonvisible overscan expands up to 2 screens behind/3 forward (direction reverses), subject to that target. Metadata is held only in the parent 500-item LRU. Identity and explicit height helper maps each cap at500; TanStack keeps normal O(total-count) lightweight positioning measurements. Media transfer is4 concurrent, decode2, source-image admission12/32MP soft. Actual browser decoded/cache memory is not a hard bound. Visible original scans may individually exceed the soft pixel budget; the full-screen reader also opens original scans on explicit demand. There is no new server thumbnail endpoint.

Only question assets are requested; the preview does not use the workspace question/answer warming function. Released row leases abort transfer/decode and revoke objectURLs. Account changes abort/clear the view and session. Asset requests carry the current account affinity header. UI tests cover one-tap image opening, pinch/drag cancellation and separate zoom action.

## Geometry regression found by actual metadata QA

`real-favorite-2000-before-geometry.json` is a **failed baseline**, not an acceptance artifact: absolute jump1250 drifted to first-visible index1275 after page/key changes; a simulated network error also exposed position drift. Changes in loaded metadata and LRU eviction were changing estimates for earlier rows.

The fix keeps TanStack geometry keys immutable (`collection_version:index`), while each inner question component uses its real `entry_id` key, so repeated Attempts keep separate component identities. A Float32 numerical height ledger uses4 bytes per collection index, stores only geometry, and survives metadata eviction. Identity and explicit measured-height lookup maps still cap at500. Width/font/version changes invalidate geometry and restore a measured entry anchor; unrelated theme/preference writes no longer reset the geometry. Absolute-position jumps use the same bounded measured-frame correction as anchor restoration and yield to touch/wheel/keyboard input. Final browser evidence must be generated from the rebuilt bundle after this fix.

The real-fixture script uses a private local-only cookie file without saving its contents. It can add `--continuous-steps 300` to traverse and reverse with the independent scroller; output separates API page offsets, mounted rows, metadata cache count, layout overflow, visible decoded pixels, Chromium JS heap and ResourceTiming. JS heap excludes native image decode memory. `first_rendered_image_ms` is captured from the first preview image's load event, measured from navigation time origin; it is not an assertion about native decoder completion timing. Deliberately interrupted requests are recorded and retried. App learning-recovery PUTs are listed separately from core question data writes.

Final measured results and artifact status: [RESULTS.md](RESULTS.md). Intermediate failures are retained as explicitly labelled baselines, not passing results.
