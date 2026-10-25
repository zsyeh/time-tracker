# Selected-question audit, 2026-10-26

The core heatmap shipped first at `/core-heatmap`, commit `01bec7f`. No bank copies, progress reset or production snapshot replacement.

## First pass (not a manual completeness certificate)

All 1,228 manifest memberships were checked on VPS: **1,227 unique originals**, because one op-amp offset-voltage question was also incorrectly selected as digital electrical-characteristics practice. The digital rule now rejects the analog stem even when a distractor mentions power consumption; the original analog question and progress remain untouched. Digital selected count becomes 327. Further per-question priority review downgrades eight digital items: 2.1/2.3/2.5/2.8 are Boolean/truth-table basics, 5.1/5.2 are latch waveforms rather than combinational analysis, 3.10 includes OD load-resistance design, and 4.21 specifically requires a MUX. Current unique core count becomes **421**, digital 34. They remain available in the appropriate selected tiers. The full source restriction missing from the old 4.21 OCR is saved as a fingerprint-guarded priority override.

The read-only command `audit_ei_selected --output <new-report.json>` checks each selected UUID/fingerprint, workspace/scope, open errata, current own material, PNG decoding/hash/dimensions, bbox validity, duplicate image hashes and suspicious boundary ink. It uses bounded binary fetches, not a PostgreSQL holdable server cursor (which can spool the entire image result onto VPS disk). It does not modify the bank. `AUTO_CHECKED` explicitly does not mean visual/semantic verification.

Initial findings: 557 automatic-check-only records, 670 needing some review; 429 lack their own answer material, 278 lack their own question material. These two counts do **not** prove that the original full paper has no such content: existing full-page fallback may still exist. There were no decode failures, hash mismatches or invalid bboxes. 18 questions have a blank/nearly-blank component, often a spare continuation strip; those must not be deleted on that heuristic alone. Boundary ink is only a suspicion, not an automatic crop-edit instruction.

Private detailed report and cache: `reports/ei-core-heatmap-20261026/` on VPS; local `/home/eh/ei-core-heatmap-20261026/`. No full PDF text or image cache is committed.

## Confirmed digital answer-margin defect

The answer source is **数电课后指导与答案.pdf**, SHA256 `4dd052df4cabe65aa0c4bd31cb6911015610547a77b7c516bede26a5a9a422f0`, not the question workbook (`fc3f8f...`). Saved page indexes for answers refer to that separate answer PDF.

The old answer bbox uses x=35 through width−35 on single-column scanned pages. Confirmed examples 2.1, 2.5, 3.10, 4.1, 4.2, 4.3 and 4.21 clip text/table edges. The allowlisted repair covers 125 answer regions for 70 selected questions (13 core), restores full horizontal page width, and **does not alter vertical bounds**. The dry-run/apply command is `restore_ei_selected_answer_width --manifest <digital-answer-width.json> --source <original-answer.pdf> [--dry-run]`. Exact old image and source PDF hashes guard against stale data. Superseded binaries and immutable revision links remain; UUIDs, attempts and mastery states are not replaced. Repeated execution adds nothing.

Anchor-only checks on 140 small crops matched 137 directly. Visual review confirmed the remaining three labels (2.5 answer, 2.21 answer and 2.24 question); OCR had dropped the decimal point. This validates source-number pairing, not the full correctness/completeness of all 70 solutions.

Caption-anchor OCR additionally scanned only the 79 answer-source pages used by these selected regions (no reliable text layer). It found one corresponding figure caption outside the saved answer regions: A4.21, subsequently confirmed visually. Results are cached as structured anchors/bboxes, not repeatedly sent to a model. This check can miss poorly recognized or uncaptioned figures, so it is not a completeness certificate.

Figure A4.21 floats beside the next question's diagram, below its stem. It needs an explicit **supplementary** crop, not a full-width vertical extension. `digital_selected_figure_repairs_v1.json` keeps its exact source hash, bbox, label and review reason. `append_ei_reviewed_answer_figures` is dry-run by default, requires `--apply`, preserves existing images, and captures revisions. Neither script automatically closes user errata.

## Remaining verification

Do not label all selected questions important/complete/answer-matched based on these checks. Source-number matching and image integrity do not establish that a circuit/waveform, floating figure, final condition or last answer step was retained. The per-question report retains explicit pending visual-review and answer-matching fields. Missing independent material and unresolved boundary risks require source comparison before any overall passed status.
