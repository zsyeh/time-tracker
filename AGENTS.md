# Project execution instructions

Read [`.codex/DEVELOPMENT_WORKFLOW.md`](.codex/DEVELOPMENT_WORKFLOW.md) before development or deployment. This is the user's current workflow instruction: preserve a working rollback, develop and back up in parallel, match backup scope to changed data, and aim to finish affected validation within one minute. Broaden checks only for a concrete unresolved risk or required safety gate; do not repeat whole suites for ordinary small changes.

- Read `docs/DEVELOPMENT_LOG.md` and the relevant release note, then continue existing work. Do not restart an entire audit for each task.
- Preserve existing uncommitted work, learning data, authentication and mature fullscreen Practice behavior.
- If question content is unchanged, back up account and learning information plus relevant configuration/old image; do not automatically dump the unchanged question/image bank.
- Freeze optional work before deployment. Documentation-only commits do not require rebuild or production restart.
- Record actual results and uncovered cases. A one-minute target never authorizes publishing a known data/permission failure.

## High-bandwidth SSH transfer endpoint

For large transfers to/from the NUC, use `eh@98.142.241.45:10000` with explicit SCP port, e.g. `scp -P 10000 <source> eh@98.142.241.45:<destination>`. This endpoint is SSH to the local NUC. Actual FRPS administration is `root@98.142.241.45:22`.
