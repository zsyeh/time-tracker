# Collection preview integration QA

## Result

[browser.json](browser.json) records six passing cases on the isolated localhost8035 production-prefix fixture with real original PNGs. Chromium page JavaScript errors:0. The latest failed case was rerun after its specific fix; previously passing cases were retained instead of repeating the entire suite. No production data/service was accessed or changed by this script.

| ID | Case | Evidence |
|---|---|---|
| INT-01 | Favorites list entry → ordinal238 → visible-image coordinate tap → Practice → browser Back; reenter → next → Question return; refresh |Same `favorite:3563` at index237. Before first tap offset−73.1953px; returned offset−73.3164px. Second tap saved−73.3164px; Question-return−73.3164px; refresh−72.8789px. All within3px; absolute `scrollTop` deliberately differs as earlier unmounted row estimates change. Latest initial-width-fix build passed.|
| INT-02 | Explicit history `attempt:100` → next `attempt:99`, same question UUID |Question timer0:10→0:11; zero new claim/pause requests between the entries.|
| INT-03 | EI keyword search → Preview → Practice → Preview |`workspace=ei`; `/ei/preview` and `/ei/practice/...` preserved. Actual router path agrees with document URL; one initial index script. Passed after static Preview route registration was restored.|
| INT-04 |50-user favorite+unattempted filtered Practice collection; save correct; auto-next; return to removed entry |Count49→48, next UUID exactly matched the prior collection's second entry. Original removed question restored to nearest index0, with localized explanation. Only this synthetic user's answer changed.|
| INT-05 |Appearance/font/accent, rotation and account isolation |Light/blue/compact, dark/purple/extra-large, system-following-dark/monochrome/default; widths390/820/1180. No sampled horizontal overflow; same entry through rotation. Account50→2000 changes collection count50→2000, without reusing old account metadata. Original preferences restored.|
| INT-06 |One zoom action per question; no controls over scans |One question-level meta action opens read-only FullscreenReader with actual images and no practice actions. No `.preview-asset .preview-zoom` overlay exists. Screenshot [final-single-row-zoom-390.png](final-single-row-zoom-390.png).|

These are Chromium viewport tests, not physical iPadOS Safari/PWA acceptance. Native gesture/OS lifecycle and production-network latency retain their separately documented limits.

## Two real regressions found and closed

1. **List → Preview address changed while the old list stayed visible.** The router instance attached to `#app` still reported Favorites while the browser URL reported Preview. Direct Preview loading worked. Restoring Preview's static component registration, consistent with the existing views, fixed Favorites and EI entry. Do not reintroduce the late lazy-route optimization without checking production-built navigation in both workspaces and the index-module dependency graph. A suspected contributing mechanism was an async chunk importing an entry without its HTML `?v` suffix and creating a second app/router; the duplicate-module explanation was an inference, while the route/URL mismatch and static-registration fix were observed.
2. **Returned entry correct, intra-row offset lost.** Visible-coordinate tapping plus capture-phase anchor recording reproduced−73px→0px; this was not Playwright's automatic scroll-into-view. Initial VirtualPreviewList width measurement (`previousWidth=0`) started a second restore from the temporary offset0 and canceled the caller's saved-offset restore. The minimal fix allows size-change restoration only when `previousWidth>0`. The original three-frame saved-anchor correction remains. The actual browser Back/next-return/refresh case then passed without widening its3px tolerance.

Before-fix evidence remains in `before-static-freeze/`, `before-static-preview-route/`, `before-coordinate-tap/`, and `before-initial-width-fix/`; these folders are not passing acceptance evidence. Capturing real image taps avoids the automation artifact where `locator.click()` scrolls a partially visible image/header before clicking.

## Execution and safety

```sh
/home/eh/ei-page-tracking/browser-env/bin/python docs/collection-preview/integration/browser.py
# Recheck only a changed case; retain prior passing results:
/home/eh/ei-page-tracking/browser-env/bin/python docs/collection-preview/integration/browser.py --only favorite_origin_238_browser_back_next_and_refresh
```

Cookies are read from the private local fixture file and never serialized. Request evidence records path, method, action/result and a short digest of timing identity, without credentials. The script writes only isolated synthetic settings, timing/recovery state and the explicitly authorized synthetic correct answer; no Note/diagnosis content is edited. User settings are restored on successful cases.

`network_failures` is retained rather than hidden: one learning-recovery optimistic-version409 was handled without blocking the EI flow, and two image requests were intentionally aborted when their row leases ended. These are distinct from the recorded zero browser JavaScript errors and successful question navigation/save assertions.

26 relevant frontend unit tests passed after the one-condition width fix (layout4, image pipeline5, asset interaction3, question row1, PreviewView13). Final central builds/backend suite/deployment are owned by the primary agent.
