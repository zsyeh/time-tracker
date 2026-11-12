# 题单全局预览与 Practice 分页

基线：`0865665` / 生产 `89d52bd`。施工分支：`feat/collection-preview`。本次不更换设计系统，不更改作答协议、题目 UUID、计时、笔记、掌握状态或统计公式。

## 1. 题单契约与入口

`frontend/drill/src/lib/listContext.ts` 是唯一前端题单定义。逻辑路由 `/preview`，直接 IP 分别是 `/drill/preview`、`/ei/preview`。版本1包含 workspace、source、完整有效筛选 query、原列表 returnTo。页码与旧 index_version 不属于集合身份，原列表的完整 URL（含独立分页）保留在 returnTo。用户输入草稿不冒充已应用的筛选。

| 页面 | source / 身份 | 范围与顺序 |
|---|---|---|
| Practice、搜索结果 | practice / question:UUID | 同一 `question_list_scope` + `order_question_scope`；相关性/书序及稳定 PK 次级排序完全共用 |
| 收藏 / 下次复习 | favorite、review_later / 对应 UserState PK | 当前账号、workspace，`-updated_at,-pk`；不是全站收藏 |
| 历史作答 | attempts / attempt:PK | 同一 Insight 查询，独立作答条目，不按 UUID 去重 |
| 历史 Note | notes / note:UserState PK | 同一 Insight Note 查询，与作答列各有入口与原分页 |
| 普通 / 数二严选 / EI核心热力图 | heatmap / question:UUID | 当前 scope、type、collection、course、material；书序。状态高亮原本不移除格子，预览也不把弱化格子过滤掉 |
| EI五科严选 | selected / question:UUID | 原 manifest 桶顺序、桶内书序；保留所有原筛选，不套用数学二 |
| 诊断队列 | diagnostics / diagnostic:Plan PK | 原 error / queue 与复习计划顺序，预览不限于首200条 |
| 勘误 | errata / erratum:PK | 原 workspace 公开权限与创建时间顺序，同题多个勘误保留 |
| 试卷复盘 | paper / paper:Item PK | 试卷所有者、位置顺序、QuestionRevision 快照；打开当前原题是独立 Practice，不写试卷作答，界面明确说明 |

驾驶舱考纲行是 Topic 集合，资料/活跃图是聚合，并非完整 Question 列表；保留它们已有代表题/题册入口，进入实际题目列表后使用其预览。进行中的组卷考试不改变其现有考试导航。

## 2. API

认证 GET `/api/drill/collection-preview/`，沿用部署的 workspace Host / IP 前缀路由。`source` 使用上表；其它参数直接复用来源列表语义。`offset>=0`，`limit=50`（只能省略或50）。

```ts
{
 count: number, offset: number, limit: 50, has_more: boolean,
 collection_version: string,
 located: { entry_id, question_uuid, index } | null,
 previous_entry: { entry_id, question_uuid, index } | null,
 next_entry: { entry_id, question_uuid, index } | null,
 notice?: string,
 results: [{
   entry_id, question_uuid, index, label, document, topic, state,
   is_favorite, review_later,
   preview: { question_markdown, assets: [{ id, url, width, height, position }], source_page },
   attempt?: { id, result, created_at }, note_excerpt?: string
 }]
}
```

`locate_entry` 优先于 `locate_uuid`；UUID 有重复时不得代替 Attempt 身份。定位响应返回包含该项的50条，以及跨批邻居。找不到原条目时使用 `fallback_index` 最近合法位置并返回说明。

`collection_version` 是不透明快照标识，绑定账号、workspace、筛选、顺序、搜索索引和学习数据修订。失配返回409 `COLLECTION_CHANGED`。所有查询在现有 PostgreSQL REPEATABLE READ / READ ONLY 快照中；只水合当前50条，不调用昂贵的完整 QuestionDetail，不读取答案或 image_data。无学习写入。响应 `private,no-store`、`Vary: Cookie`。

版本需要 O(total) 薄身份扫描/哈希；不是 O(50) 查询，不称游标分页。现有规模测试后选择 offset+定位，保留数字跳页；避免另建会写学习状态的集合表。新增查询固定，不随批中行数出现 N+1。

## 3. 六层资源边界

1. **元数据**：50条/批、单集合10批即500条 LRU；注册表最多2集合，总计1000条。账号变化立即清理/中止。缓存不含 Blob/Base64。已缓存区域反向滚动复用，淘汰区域允许重取。
2. **API分页**：offset50批、稳定版本、独立在途合并/取消。fresh 完成前后续分页等待，过期版本不能覆盖新版本；401与账号 affinity 409不能当集合变化无限重试。
3. **网络图片缓存**：沿用私有认证的 HTTP Cache 与 SHA 版本 URL。不新增全题库 Cache Storage/Service Worker，不把图片跨账号共享到应用缓存。
4. **预取**：虚拟窗口按方向提供约2–3屏缓冲；可见优先，邻近其次；最多4个 fetch、2个 decode，离开窗口取消/释放。不会预取答案或整库图片。
5. **解码与DOM**：媒体12张 / 32Mi像素软预算；约20行 DOM 目标。必须保留实际可见的超长原图，故这些是软预算，不能保证浏览器原生解码内存严格上限；图片释放不等于 GC 已完成。显式放大使用单个现有 FullscreenReader。
6. **位置**：owner+workspace+canonical context key 的设备 sessionStorage，stable entry ID + index fallback + 相对偏移。不是账号同步的窗口滚动偏好，不干扰既有主题/字体/侧栏同步。

TanStack Vue Virtual `3.13.52`（MIT，锁定版本）只负责几何窗口。几何 key 使用固定版本内的序号，业务子组件使用真实 entry_id，避免 LRU 淘汰后 key 翻转。Float32 几何 ledger 只保存数值高度，O(total)，约4字节/题；与最多500条题目元数据分开计量。原始宽高预留图像空间，ResizeObserver 测量实际高度。手动跳题与恢复使用有界测量帧校正，用户触摸/滚轮立即取消，不用任意 setTimeout 循环追赶滚动。

## 4. 导航与恢复

预览点击题图或“进入做题”都通过 `previewQuestionLocation` 传真实 UUID、entry、当前位置与同一 context。放大按钮独立；多指、拖动、pointercancel 不进入 Practice。只有进入现有 Practice 才激活原计时流程。

QuestionView 在 preview 上下文只用该集合前后邻居，不修改持久化的 next_mode。两个历史 Attempt 即使 UUID 相同，也更新 entry 游标而不重启同题计时或丢失诊断/Note 草稿。答案保存先完成；慢/失败的题单导航不能阻止保存。提交导致当前项离开筛选时，以当前序号定位最近合法后继，避免跳过一题。

打开 Practice 前消费预览 URL 中首次深链接定位 entry/question，保留 list；因此浏览器 Back 不会被最初入口题覆盖。内部“返回全局预览”同样使用原 saved anchor。刷新重建对应50批与相对偏移；版本变更先重新定位原 entry，消失再邻近恢复并说明。

窗口级 learningRecovery 允许 preview 路由，但不对其私有虚拟 scroller 调用 window.scrollTo。停止恢复后的残余 RAF 不再移动新页面。普通 Question fullscreen 分栏、图像缩放、计时、Note、诊断及提交协议保留。

## 5. Practice 分页策略

原后端24条/页不变，兼容增加 `page/page_size/total_pages`。总页按当前 count 计算；空结果为0/0而不是1/0。上下两个分页提供首页、上一页、当前/总页与题数、下一页、末页，以及 Enter/明确提交的页码输入，拒绝越界/非整数。

Router 不再对 Practice 的 query 变化无条件返回 `{top:0}`。底部分页以点击前分页栏 viewport offset 为锚点，数据更新后恢复其可见位置并合法 clamp；顶部/筛选操作定位结果区域。返回列表以可见题目 UUID+offset 恢复。用户滚动/键盘操作取消过期校正。序列号+AbortController 拒收旧响应；未提交搜索防抖不得在翻页后意外重置页码。

## 6. 数据库、CSP与部署

`drill.0040_preview_login_target_length` **仅**把短期认证 Handoff 的 `target_path` 从varchar500增宽至16384，解决较长预览深链接在 PostgreSQL 登录交接时失败；不迁移题目/Attempt/Note/用户偏好数据。输入严格有界，不接受外域/控制字符。应用回滚保留该兼容增宽，不缩列、不恢复过期学习快照。

私有 Drill SPA 的 CSP 仅为 `img-src` 增加 `blob:`，供预览受控图片解码；script-src/object/frame 限制不放宽。长URL仍须通过部署的 Nginx/Gunicorn request-line 预算验证，不把模型字段上限当作代理无穷大支持。

47发布前新建受保护的 `backups/round2-preview-20261113`：当前89d52bd镜像ID、web/queue unit、PWA副本、最新完整 pg_dump、SHA256、TOC、全档案读取验证。新镜像在迁移计划与测试通过后才切换，web/queue保持一致，真实 `/accounts/login/`200 + Docker healthy。失败执行保留的 `round2-rollback.sh`，恢复旧应用/queue/PWA，**不覆盖上线后学习数据**。98分享/代理入口不改业务；交付时验证新静态hash与现有深链接。

## 7. 需求追踪（GP前缀避免覆盖原 Master R01–R16）

| 用户要求 | 施工 / 文件 | 自动化与验收证据 |
|---|---|---|
| GP-R01 全部当前题单 | 各入口、listContext、collection_preview adapters | SelectedPreviewEntries、CollectionView、InsightView与backend equivalence/owner tests |
| GP-R02 连续上下阅读 | PreviewView、VirtualPreviewList | 真实题单至末尾/反向、空/结束状态 |
| GP-R03 窗口预算 | preview/layout、imagePipeline | layout/pipeline unit、真实DOM/媒体指标 |
| GP-R04 元数据LRU | collectionPreview | 1000条缓存500、两集合1000、账号切换tests |
| GP-R05 双向虚拟化 | VirtualPreviewList、TanStack | 实际大题单反向、真实key与动态高度 |
| GP-R06 方向/overscan | layout.previewRange、优先媒体队列 | 方向单测、快速跳转/反向截图 |
| GP-R07 不等高稳定 | Float32高度、尺寸、RO、anchor | 旋转/尺寸变化、1250定位回归；原失败证据保留 |
| GP-R08 图片分层 | preview/imagePipeline | 真实PNG、HTTP缓存与有限resident；heap不冒充native内存 |
| GP-R09 优先/失败重试 | PreviewAssetImage、imagePipeline | 并发/取消/错误重试tests、离线恢复 |
| GP-R10 真实题目/题单导航 | QuestionView、previewQuestionLocation | QuestionPreviewNavigation与完整点击/相邻题browser |
| GP-R11 放大手势 | PreviewAssetImage、FullscreenReader | 多指/拖动/取消/键盘与放大独立tests |
| GP-R12 返回/刷新/PWA恢复 | PreviewView、collectionPreview、learningRecovery | Back入口A→滚到B回归、entry+offset、移出集合fallback |
| GP-R13 当前页总页总题 | PracticePagination、search/service | filtered count、empty0、旧API兼容 |
| GP-R14 任意页/首末页 | PracticePagination、usePracticeQuery | 边界输入、真实Enter/Space、多端分页QA |
| GP-R15 不跳顶部 | main.scrollBehavior、PracticeView | pager anchor0px、短末页clamp、快速切页、scroll事件轨迹 |
| GP-R16 共用题单定义 | listContext、collectionPreview、QuestionView | filter/URL序列化、重复Attempt独立、权限/cache隔离 |
| GP-R17 API/定位/稳定顺序 | collection_preview、shared search scope | 50meta/locate/邻居/快照并发删除/稳定次级排序 |
| GP-R18 权限与学习数据 | 后端owner/workspace、no-store | readonly事务/0writes、跨账号/工作区/损坏anchor tests |
| GP-R19 真实数据性能 | 隔离9281真实元数据、真实题图测试集 | api-performance、窗口/图像/browser指标；未实测项明确不通过 |
| GP-R20 18场景矩阵 | 三模块与集成QA | 下列状态与逐项browser/单测证据，实体Safari不冒充LinuxWebKit |

## 8. 测试与证据索引

- [分页与入口](practice-pagination/README.md)：模块与独立双引擎分页QA；前后截图标明版本。
- [虚拟窗口与图像](preview-window/README.md)：合成10k与真实题库分别标注，原漂移失败留档。
- `drill/test_collection_preview.py`：稳定分页、查询复用、权限、重复身份、无blob/答案水合、RR并发与跨设备修订。
- `drill/test_preview_login.py`：PG长deep link、CSP与输入边界。
- `frontend/drill/src/lib/*.contract.test.ts`：缓存/版本竞态、owner与URL。
- QuestionPreviewNavigation / QuestionRecord / QuestionDiagnosis：原保存语义与新导航。
- [最终集成报告](DELIVERY.md)：最终测试数量、生产镜像/提交/备份、真实测量与未关闭项。尚未出具最终报告时不得把本文件当作部署已完成证明。

## 9. 分工与续接

主Agent独占共享context/cache、QuestionView、main/router、Heatmap与额外入口、恢复/认证/CSP/迁移、Master、集成/部署。A后端负责新投影与共用查询，B负责新preview/virtual/image，C负责Practice分页与收藏/历史/五科入口。互不覆盖；新文档证据各有独占子目录。A冻结后独立审查前端，C独立审查root导航/缓存，全部具体问题先报告owner再修。

实际阶段：审计/合同 → 独立后端与分页/窗口 → 媒体与导航 → 缓存/几何竞态修复 → 自动化+真实数据多端QA → 新备份/迁移/不可变镜像 → 健康/用户路径/日志/回滚检查。每次最终修复后重新验证受影响范围，最终完整suite不以旧绿测替代。

**保持未关闭**：没有实体iPhone/iPad的iPadOS Safari、原生PWA退出重启、真实双指手势/系统内存回收证据时，不能勾选“实机Safari/PWA验收通过”。Linux WebKit与Chrome截图/standalone模拟仅证明其实际覆盖范围。
