# Question drill

The drill is a separate Vue SPA served only on a configured drill hostname. It
shares Django authentication and PostgreSQL with the Timer application, while
keeping its routes, bundle, navigation, and visual system independent.

Existing Passkeys are bound to the Timer WebAuthn relying-party domain and
cannot be replayed directly on a sibling hostname. An anonymous Drill page
therefore redirects through the Timer login page, where the existing Passkey is
valid, then returns through a 90-second one-time handoff. Only the handoff hash
is stored, it is deleted when consumed, external return URLs are rejected, and
the Nginx example disables access logging for the completion path. This avoids
changing the WebAuthn RP ID or widening the session cookie to every subdomain.

## Data model

- `QuestionDocument` and `QuestionTopic` preserve the imported source hierarchy.
  Separate display titles remove PDF table-of-contents leaders without replacing
  raw provenance.
- `Question` has a deterministic UUID, a normalized similarity topic, a cleaned
  display label, a provenance category, and a record kind.
- `QuestionAsset` stores the verified PNG bytes plus source PDF crop coordinates
  in PostgreSQL and is fetched only from an authenticated, immutable-cache
  endpoint. A content hash in the asset URL safely refreshes browser caches after
  a source re-render.
- `QuestionAttempt` belongs to one user. Frequencies, results, progress, and the
  past-paper heatmap are therefore isolated between accounts. A reset is an
  append-only state marker; undo removes only the latest marker and restores the
  previous state.

The original normalized bank imports as 8 documents, 861 topics, 3,553 source records, and
4,123 PNG crops. Cleanup currently identifies 3,208 practiceable records and 345
high-confidence source-outline rows. It separates 1,013 official past-exam
records, 2 adapted exam records, 95 mock-paper records, 1,783 workbook records,
31 competition records, and 284 practiceable records whose provenance is not
safe to infer. The classifier recognizes an exam year immediately associated
with Mathematics I/II/III; descriptions that merely mention a year elsewhere
are not included in the official heatmap.

All question-bank source material was collected and organized by Bilibili
creator **cxy (澄潇宇)**. Thanks to cxy. PDF authorship remains separate source
metadata and is displayed on question detail pages when available.

The original `/root/Downloads.7z` contains limits, single-variable integration,
linear algebra, double integration, multivariable differentiation, differential
equations, and improper integration. The later bookmarked single-variable
differentiation PDF is imported separately at 180 DPI, preserving its PDF author
metadata (`本本`), original source labels, and bookmark hierarchy.

After that import, production contains 9 documents, 963 topics, 4,228 source
records, 3,883 practiceable questions, and 4,830 authenticated crops. The new
document contributes 675 questions and 707 crops (about 15.5 MiB): 281 official
past-exam questions, 376 workbook questions, and 18 competition questions.

## Formula fidelity

A PDF produced by LaTeX does not retain the original TeX source. These PDFs mix
embedded raster questions, vector glyphs, subset fonts, and text with imperfect
Unicode maps. The normalized export contains zero non-empty `latex_text` values.
Consequently the authenticated PNG crop remains the canonical renderer: it
preserves the exact formula instead of presenting math OCR as trusted TeX. The
question page labels the render source. Supplying the original `.tex` files (or a
reviewed math-OCR export) is required before exact structured LaTeX can replace
the crops safely.

## Reversible cleanup

Raw filenames, topic titles, source labels, and extracted text are never
overwritten. Rebuild display metadata and inspect the resulting counts with:

```bash
python manage.py clean_question_bank --dry-run
python manage.py clean_question_bank
```

Rules are intentionally conservative: official exams, adapted exams, mock
papers, workbooks, and competitions require explicit source markers. Anything
else remains `Unclassified`. Only a small single crop that repeats a source
outline heading is hidden as a `section`; grouped extracts remain practiceable
and are labelled.

## Normalized import

The idempotent command accepts four JSON Lines files (`documents.jsonl`,
`nodes.jsonl`, `questions.jsonl`, and `assets.jsonl`) plus the source asset root:

```bash
python manage.py import_question_bank /safe/export/normalized \
  --assets-root /safe/export/assets
```

Every PNG signature and SHA-256 digest is checked before the surrounding
transaction commits. Re-running the same import updates metadata and skips
unchanged image bytes without duplicating questions, topics, or assets. Always
take a PostgreSQL backup before importing a replacement bank.

Import the bookmarked cxy single-variable differentiation PDF with:

```bash
python manage.py import_cxy_differentiation_pdf \
  'drill/【A4 紧凑】一元微分做题本.pdf' --dpi 180 --dry-run
python manage.py import_cxy_differentiation_pdf \
  'drill/【A4 紧凑】一元微分做题本.pdf' --dpi 180
```

The default 180 DPI keeps thin mathematical strokes readable while remaining
well within the current disk budget. The command accepts only 120–200 DPI and
is idempotent.

Legacy normalized crops can be recovered from their exact source PDFs and
re-rendered at the same 180 DPI without changing questions, attempts, UUIDs, or
topic metadata. The command first locates every crop and refuses to mutate any
row if a source file or crop cannot be verified:

```bash
python manage.py rerender_question_assets /safe/extracted-pdfs --dpi 180 --dry-run
python manage.py rerender_question_assets /safe/extracted-pdfs --dpi 180
```

Always take a PostgreSQL backup first. Source page and clip coordinates are
saved with each asset, so later re-renders are direct and do not need to recover
the crop position again.

Some PDFs place a question-link anchor at the vertical centre of a tall matrix.
For a verified source document, formula-aware bounds include both PDF text
blocks and vector determinant/bracket paths before re-rendering:

```bash
python manage.py rerender_question_assets /safe/extracted-pdfs \
  --source-id 3 --dpi 180 --formula-aware-text-bounds --force --dry-run
python manage.py rerender_question_assets /safe/extracted-pdfs \
  --source-id 3 --dpi 180 --formula-aware-text-bounds --force
```

The option requires an explicit source ID so it cannot silently re-segment the
whole bank. It leaves question UUIDs, attempts, classifications, and source
labels unchanged.

## Routes

- `/practice` — catalog and filters
- `/practice/<question_uuid>` — stable question detail, next-question navigation,
  and similar set
- `/heatmap` — per-user past-paper frequency heatmap
- `/api/drill/catalog/` — lightweight books and topics
- `/api/drill/questions/` — paginated lightweight summaries
- `/api/drill/questions/<uuid>/` — detail and authenticated asset URLs
- `POST /api/drill/questions/<uuid>/attempts/` — set mastered/review/reset state
- `DELETE /api/drill/questions/<uuid>/attempts/` — undo the latest state change
- `/api/drill/questions/<uuid>/similar/` — same-topic source counts
- `/api/drill/questions/<uuid>/similar/?kind=past_exam` — official past exams
- `/api/drill/questions/<uuid>/similar/?kind=practice` — mock/workbook practice
- `/api/drill/heatmap/` — compact per-user official-exam state cells
- `POST /api/drill/papers/generate/` — ephemeral randomized paper (1–100 questions) filtered by book, topic, source and per-user unattempted state


## 二期 Drill 工作区（安全优先）

当前 Drill 前端以服务端为权威数据源，同时在浏览器保存轻量工作区状态：

- Practice 状态使用版本化 key `drill.practice.state.v1` 保存 book、topic、source category、搜索词、页码和滚动位置；缓存仅包含筛选元数据，不保存题图或题面正文。
- Catalog 使用版本化 `drill.taxonomy.v1` key 和 7 天 TTL 缓存；第二次进入可先显示本地 Book/Topic，再后台刷新。题目列表按用户与查询条件隔离在 5 分钟 session cache。
- 搜索聚焦时先从本地 taxonomy 给出 Book/Topic 候选；单字符不触发远程全文搜索，稳定输入 2 个以上字符后使用 400ms 防抖、`AbortController`、sequence guard 和短期结果缓存。
- Question 详情支持稳定的 previous/next 导航。进入题目时携带 Practice 的 `document`、`topic`、`source_category`、`q` 和 `unattempted` 查询上下文，导航优先留在当前集合；无上下文时使用稳定的 document/order 顺序。
- Question detail 采用内存 + 用户隔离 session cache（24 小时 TTL、最多 120 项）并 stale-while-revalidate；next、previous 和空闲时 next+2 复用同一 inflight Promise，且只预热目标题首图的现有 HTTP immutable cache。
- 横屏布局使用可收起的左侧抽屉导航，题目区域始终占满主视口；Question 页面不再提供 Focus 或 Browser Fullscreen 控件。题图保持原始比例，使用带 hash 的私有 immutable URL 缓存。
- Heatmap 支持 `scope=past_exam`、`scope=mock_exam` 和 `scope=all`，compact cell 不返回 prompt 或图片；每个 scope 使用用户隔离的 2 分钟 session cache，Attempt 写入后立即失效。
- Build Paper 通过 `/paper` 提供临时组卷；后端只返回轻量题目摘要，浏览器保存当前题目 UUID 列表，不为每份试卷创建数据库记录。
- Attempt 继续区分题库识别置信度 `Question.confidence` 与用户作答置信度 `QuestionAttempt.confidence`；后者允许空值，范围为 0–100，并可绑定最多 2000 字符的批注。未提交 Note 以用户和题目 UUID 隔离在浏览器保存 3 天，成功提交后立即清除。
- 题图导入和重渲染命令默认使用 200 DPI，仍支持 120–200 DPI 的显式 dry-run 与源 crop 校验；不会修改既有 Question UUID、Topic 或 Attempt。

新增迁移：`drill.0006_questionattempt_metadata`。验证命令：

```bash
./.venv/bin/python manage.py makemigrations --check --dry-run
cd frontend && npm run build:drill
DATABASE_URL='' DATABASE_PATH=/tmp/time-tracker-drill-tests.sqlite3 ./.venv/bin/python manage.py test drill
```

生产数据库恢复前必须先执行 PostgreSQL dump，见 [`backup-and-restore.md`](backup-and-restore.md)。
