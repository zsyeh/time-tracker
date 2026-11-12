# P06 Practice / diagnosis evidence

These are isolated Vite component fixture screenshots using the real `DiagnosisSelector`, `PracticeActionToolbar`, `FullscreenReader` and shared neutral tokens. All questions are synthetic images. No production API or learning records were accessed.

`results.json` records 375/390/430/820/1180/1440 CSS pixel widths, Light/Dark, touch pointer on mobile/tablet, measured control rectangles and runtime errors. All 12 cases had no page horizontal overflow or JavaScript errors; touch Reader controls measured at least 44 × 44 px and all five actions stayed visible. Separate rotation check passed 1180 × 820 → 375 × 812 with the same open dialog and 125% → 100% zoom.

Representative images include mobile and iPad landscape diagnosis and Reader. These are Chromium fixture evidence, not native Safari / iOS PWA sign-off or whole-QuestionView integration screenshots. Full application and real-device acceptance remain the integrator's responsibility.

Local checks: 8 focused Vitest suites passed, covering 32 focused tests including the final additional Reader focus/overlay case (the original 8-suite run passed 31; the Reader suite rerun passed all 6). Original record handler / timer / diagnostic payload and 550 ms historical save behavior remain covered. TypeScript check was blocked at this checkpoint by concurrently written shared UI components, not a P06 error; rerun after integration.

Preference helper preserves existing persisted values: shared legacy `drill.next-mode.v1`, `drill.review-auto-next.v1`, `drill.mastered-auto-next.v1`; workspace-specific `${workspace}.page-turn-copy.v1`.
