# P07 Heatmap / History evidence

The screenshots render the real Vue views and shared styles in an isolated Vite fixture with synthetic, owner-scoped API responses. No production requests, Attempts or Notes were written.

`results.json` records 24 Chromium cases: Heatmap and History × 375/390/430/820/1180/1440 CSS px × Light/Dark. All passed page horizontal overflow and runtime-error checks. Heatmap touch cells measured 44 × 44 px (fine pointer 32 px), all 120 question cells remained in place after state highlighting, and the next-unattempted action selected one question. History retained all 10 synthetic Attempts including repeated question UUIDs; advanced filtering, debounced search, mobile list tabs and Note expansion were exercised. Representative screenshots use viewport capture; no Chromium result is a native Safari/PWA sign-off.

Focused tests: `HeatmapView.test.ts` 7 passed; `InsightView.test.ts` 10 passed. Drill `vue-tsc --noEmit -p tsconfig.drill.json` passed. `git diff --check` passed for owned production files.

Implementation:

- Heatmap uses one compact progress line, a single next-unattempted action, title/spacing instead of book cards, neutral selected styling, semantic status text/icons, and readable dimmed cells. Current backend states, source order, filters and source-indexed direct entry remain authoritative.
- Existing heatmap return cache now includes owner/workspace and the original book anchor. Restoration waits for rendering/fonts/two frames, preserves the original browse position through consecutive questions, and does not override a user scroll or explicit new selection. Requests cancel and ignore obsolete failures.
- History separates applied conditions from drafts, preserves both server page cursors, promotes sort to the frequent toolbar, and collapses subject/book/chapter/diagnosis/Note filters. Search waits 250 ms and an IME commit, aborts old requests immediately, and rejects late responses.
- History scroll/list/expanded-Note state is scoped by owner and workspace. Only anonymous fixtures consume the old unscoped v1 cache. Note expansion is bounded to the most recent 100 UUIDs. Both the current query and page remain part of return restoration.
- History uses a 900 px content-container breakpoint for a 3:2 split, rather than a device viewport breakpoint. This intentionally keeps a readable split at iPad landscape width after the 224 px sidebar; narrower content uses keyboard-accessible tabs.

Remaining integration checks: full App shell/navigation header alignment, full production build, whole-site regression, real iOS keyboard/safe-area/PWA restart and native Safari. Legacy shared page-header padding and Question global rules are handled by the main agent; these view/component checks do not replace the final integrated screenshots.
