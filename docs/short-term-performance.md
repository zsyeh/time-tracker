# Timer / Drill / EI 短期性能与可靠性优化

日期：2026-11-11。开发与本地验证完成后，已按用户后续明确授权部署到47；发布结果及回滚方式见文末。

## 测量口径

基线为 `7d5b312` 的业务代码（与已部署 `ab6040f` 一致，差别仅文档）。使用已有备份在隔离 PostgreSQL 15 恢复 9,281 条 Question 记录及真实业务分布；含非练习记录。23,712 条图片元数据用于还原关系，图片字节为空占位；图片读取成本另用 1 MiB 合成图片验证。用户 Note、完整响应、数据库备份和原始 SQL 不提交 Git。

两轮交替执行 before→after，每场景每轮 1 次预热、6 次采样，表中为两轮合计12次采样的中位数。固定业务时间以便逐字段比较；12种场景的完整 JSON 响应在两轮均与基线完全一致。handler 时间包含视图、数据库往返和 JSON 序列化；使用已认证 RequestFactory，**不包括 Session 中间件、TLS、公网、Nginx 或浏览器渲染时间**。SQL 时间来自 Django 查询计时，精度为毫秒。基准运行时不并行构建或测试，使用相同数据库设置和硬件；这些是本机微基准，不能当作生产提速承诺。

## SQL 与导航结果

| 场景 | SQL 次数：前 → 后 | handler 中位耗时 ms：前 → 后 | SQL 中位耗时 ms：前 → 后 |
|---|---:|---:|---:|
| drill_book | 19 → 19 | 107.10 → 99.04 | 66.00 → 54.50 |
| drill_unattempted | 19 → 19 | 108.89 → 94.78 | 64.00 → 56.50 |
| drill_large | 21 → 18 | 117.76 → 98.40 | 72.00 → 56.00 |
| drill_selected | 17 → 15 | 81.42 → 74.26 | 37.50 → 35.50 |
| drill_history | 24 → 14 | 108.89 → 49.03 | 50.00 → 19.00 |
| drill_favorites | 21 → 14 | 77.01 → 32.89 | 33.00 → 9.50 |
| ei_book | 26 → 24 | 86.57 → 70.48 | 41.00 → 30.00 |
| ei_unattempted | 26 → 24 | 96.40 → 75.16 | 51.00 → 35.50 |
| ei_large | 26 → 23 | 88.94 → 72.85 | 44.00 → 33.00 |
| ei_selected | 16 → 14 | 127.29 → 125.93 | 52.00 → 55.50 |
| ei_history | 20 → 12 | 88.20 → 52.18 | 37.50 → 18.00 |
| ei_favorites | 21 → 12 | 83.93 → 32.31 | 37.00 → 10.50 |

普通题库导航由完整结果集改为按 `(document_id, question_order, pk)` 的范围查询，返回 `LIMIT 1`；基线 EXPLAIN 中普通 Drill/EI 当前题集分别返回603/695行。现在每个邻居查询最多返回1行，减少 Python 物化；并不声称数据库底层扫描全部消失。

严选集合保留一次批量读取。试验中范围查询令 EI 严选从130.96ms退化到145.14ms，已撤回该路径；最终 EI 严选耗时变化很小，不能宣称显著提速。保留集合过滤模块和清单原样，未新建清单。

主要成本和修复：

- 历史/收藏原先先计算整套普通导航，再被列表导航覆盖；现在直接使用列表顺序，省去被丢弃的 SQL。
- 详情主查询重复计算 latest result/date，之后又查询完整最新 Attempt；详情复用完整 Attempt，列表/热力图仍默认保留原注解。
- `next_latest_at` 普通导航从未使用，移除该相关子查询。
- 最新 Attempt 已有有效耗时时复用；无 Attempt 时省略历史耗时查询；Reset/最新无耗时仍回查原有历史。
- unattempted 题集已筛选最新状态，不再重复同一筛选。
- 前向复习查询包含完整环绕；若其结果为空，对同一池的反向复习必为空，省掉重复反查。非空仍使用原 next/previous review 查询及5天边界。
- 题型关系随详情主查询读取，避免单独查询。

EXPLAIN 使用了既有 document、source_category 和 Attempt question 索引。没有新增索引或迁移，没有改变跨题册、环绕、排序、workspace、严选来源、历史/收藏列表或格式参数400响应。

## 缓存与作答可靠性

- 浏览器存储读取、写入、删除、枚举均按可选缓存处理。QuotaExceededError/SecurityError 不再令成功的 API 请求 reject；内存缓存、TTL、预加载和跨标签页失效机制保留。
- 缓存按 workspace+username 隔离；切换 scope 清理共享内存/inflight，迟到响应不能写入新 scope。catalog 同样隔离并遵守原7天 TTL。底层实际 GET 合并键包含 workspace 和已知用户ID，避免新账号共享旧账号正在执行的 HTTP 请求。
- **Note 草稿保持原 username+全局唯一 Question UUID 键**，旧未同步草稿无需迁移。存储失败保留当前页内存内容并明确中英文提示；不保证刷新/关闭后仍能恢复失败写入的草稿。
- Attempt POST 确认是提交成功边界。成功后结束捕获的原计时轮次，不会因切题误结束新题计时。`applyState` 先更新权威 UI 状态，再尽力更新缓存；统计或导航失败不能变成“作答提交失败”，也不能恢复已结束计时。
- 原 submission_key 重试去重、Note version/409、Mastered/Review/Reset/Undo/诊断/TopicMastery 后端语义不变；PWA恢复与 Timer TimeLog 统计未改。

## 图片读取与真实预加载实验

| 请求 | 原实现 | 修改后 |
|---|---|---|
| 普通 GET | 1次SQL，读取图片字节 | 保持1次SQL、相同字节和缓存头 |
| GET ETag命中304 | 1次SQL，仍读取1 MiB测试图片 | 1次元数据SQL，不引用 image_data、不传图片字节到Django |
| HEAD | 1次SQL，读取图片字节 | 1次元数据SQL；数据库 length(bytea) 返回长度，Content-Length正确，不传图片字节到Django |
| GET ETag过期 | 1次SQL，读取图片字节 | 2次SQL：元数据+重新鉴权的完整读取；这是明确的代价 |

第二次读取同时获取 bytes/SHA/MIME 并重查 workspace，防止两次查询之间重渲染出现旧ETag配新字节或归属变化越权。权限始终先于304判断。UUID、资产引用、分享链接、清晰度和 private/immutable 策略不变。

预加载同URL合并，最多4个并发，成功URL缓存上限256；失败可重试，15秒停滞超时释放槽。真实 Chromium + 本机 HTTP/1.1 服务，8张图片连续预热两次：

| 指标 | 前 | 后 |
|---|---:|---:|
| 实际HTTP请求数 |8|8|
| 实际峰值并发请求 |6|4|
| Image对象创建数 |16|8|

第三次预热浏览器缓存均未增加HTTP请求；原创建对象累计24，新为8。**没有声称网络请求数减半**。收益是削减冗余调度和控制并发，保留浏览器缓存优势。

## 修改文件

- `frontend/drill/src/lib/{workspace,api}.ts`、`App.vue`：可选缓存、scope和HTTP请求合并隔离。
- `frontend/drill/src/views/QuestionView.vue`：提交边界、状态应用顺序、Note草稿反馈、等待导航结果。
- `drill/views.py`：详情/导航查询复用、有界读取、图片条件请求与HEAD。
- `drill/test_navigation_queries.py`, `drill/test_asset_delivery.py`：导航等价及权限、查询边界、重渲染并发回归。
- 前端 `workspaceReliability`, `workspaceScope`, `apiIsolation`, `workspaceMedia`, `QuestionRecord` 测试。
- `drill/management/commands/benchmark_drill_detail.py`：可复用的只读本地基准命令，不输出响应正文或用户笔记。
- `README.md`：补正生产基线日期，避免把旧镜像/备份路径当作当前版本。

## 验证及环境限制

最终 Django 全套486项通过（隔离PostgreSQL）；首次导航用例的重复题序违反既有唯一约束，已修正为有效fixture。测试容器补齐Git/systemd工具、collectstatic、pg_stat_statements后再运行；仅测试进程使用PGOPTIONS关闭JIT，避免小fixture大量参考查询的编译开销，**性能基准仍使用相同默认JIT设置**。没有为通过测试修改生产配置或无关业务模块。

最终前端35个测试文件、136项Vitest全部通过，Timer/Drill vue-tsc及两套Vite生产构建全部通过。已有大chunk警告保留，未借机拆包重构。`makemigrations --check --dry-run` 无变更。

本地原始证据：`/home/eh/performance-audit-20261111/`，包括 comparison.json、navigation-explain.json、media-browser-results.json、django-verified.log、frontend-verified.log；私有响应快照不入Git。

尚未验证：生产硬件/公网端到端延迟、真实iPadOS Safari/PWA的资源调度与系统冻结、真实生产缓存命中分布。首次使用新workspace cache key会冷缓存；旧Note草稿保持兼容。本地审计阶段未执行生产发布；后续授权发布见文末。

## 复现

使用**隔离测试数据库**及其中有效用户/题目，按照README准备Python依赖、静态文件和测试工具：

```sh
python manage.py benchmark_drill_detail --user-id <local-user-id> --question-uuid <uuid> --workspace drill --samples 12 --explain
python manage.py benchmark_drill_detail --user-id <local-user-id> --question-uuid <uuid> --workspace ei --query-json '{"collection":"core_selected"}' --samples 12
python manage.py test --noinput
cd frontend
npm test -- --maxWorkers=2
npm run typecheck
npm run build
npm run build:drill
```

collection值必须使用当前题库实际值；可由页面请求参数取得，不根据上例猜测清单名称。回滚代码可按独立提交逐项revert，无数据库迁移或数据回滚步骤。


## 独立本地提交

- `d65c995`：缓存失败隔离、账号/workspace隔离、Note草稿兼容、作答确认边界。
- `043ff6a`：合并并限制图片预加载，处理失败/停滞。
- `df2e06f`：详情/导航查询复用，保留严选批量路径。
- `ffa8b68`：图片304/HEAD元数据读取与并发更新安全。
- 最后一个文档/基准命令提交记录本报告和复现工具。

开发交付时没有推送GitHub或发布生产；后续授权发布见文末。

## 增量：严选题目标、净新增预测与趋势布局

### 目标来源与统计口径

Drill 不再使用固定690题目标。目标集合复用现有 `selected_collections.filter_collection(collection=selected)`，与严选热力图的 `scope=all` 一致；只含可练习的严选题，题型复用最终分类及现有小题/大题分组。没有新建严选清单或修改题库。按 `(created_at, pk)` 的最新作答状态计算：`done/correct` 为掌握、`review` 为待复习，已做为二者之和，Reset 为未做；Undo 删除证据后从仍存的记录重新计算。

本地已有的11月11日较早备份与截图时间不同。对同一隔离快照实际调用趋势和热力图，逐项核对如下，不能用这些数字代替生产实时数据：

| 范围 | 总数 | 已做 | 掌握 | 待复习 | 未做 | 11月21日前每日需新增（11天） |
|---|---:|---:|---:|---:|---:|---:|
| 小题 |619|333|248|85|286|26|
| 大题 |344|157|83|74|187|17|
| 合计 |963|490|331|159|473|43|

截图中的502已做和461未做不被写入代码；当前生产数据更新后会重新计算。测试另验证截图基线的461/11向上取整为42，以及大小题274/11为25、187/11为17。覆盖率为已做/目标集合总数；掌握率为掌握/该集合总数，区别于旧热力图的“掌握/已做”指标。EI继续保留独立的307道原计划题量，不套用数学严选范围，也不把全EI题库大小题剩余量当作307目标的子任务。

### 预测算法和边界

- 全workspace每日有效提交、每日去重题量和周期去重仍保留，作为工作量查看；目标覆盖与净新增只计算目标范围。
- 流式读取必要的Attempt标量字段，重演状态转换：未覆盖→有效状态为+1、有效→有效为0、有效→Reset为−1。跨天复习不再制造覆盖增长，窗口前状态作为基线；Undo和补录会重算历史序列，序列不是不可变的事件快照。
- 使用最近7/14个完整北京时间自然日的净覆盖变化/天数，今天单列。当前累计已做已包含今日变化，未来投影使用 `max(日速度−今日净增,0)+日速度×未来完整天数`，避免再次加上今天已完成的量。
- 每日工作量目标只用于工作量图表，不输入覆盖预测。预测的两种情景均基于历史净新增速度；投影保守取整、与实际已做分开，封顶展示不作为已完成判断。
- 争取完成日默认11月21日，原计划11月22日继续可见并可选择；日期以北京时间自然日结束为界。所需每日新增按当前剩余/可用自然日向上取整，大小题独立计算。
- 目标日期已过且仍有未做时显示逾期；历史不足、没有正向净增长、空目标范围时不编造确定完成日期。估算不构成完成保证。

### 前端与横竖屏

`PracticeTrendPanel.vue` 首屏突出目标覆盖、剩余、大小题任务、今日工作量和所需净新增。预测先显示能否完成、预计日期和差额；7/14/30天工作量、增长率、连续活跃等放到图表下方折叠区。保留ECharts和原日期范围切换。

根因是图表依赖异步数据的条件渲染，原onMounted时元素尚不存在，ResizeObserver未监听；移动端负边距和扩展宽度又放大了溢出。现在随图表元素出现绑定、卸载清理，容器变化、orientationchange、visualViewport、pageshow触发合并resize，去掉负边距并约束min-width/最大宽度。

真实本地Chromium使用实际Vue组件/ECharts及现有父级布局，中英文各5种横竖屏尺寸连续切换均无水平溢出；另不发送window resize，只缩窄父容器，canvas仍与容器同步，验证异步监听确实生效。真实iPadOS Safari/PWA安全区和系统冻结仍需实机验证。

### 与原优化的关系

新增后端修改限于 `drill/practice_trend_views.py` 及其测试；前端限于现有趋势组件和组件测试。复用现有热力图、题型、用户和workspace机制；未重复实现缓存、PWA恢复或导航查询，没有修改Timer统计、数据库模型、认证或生产代理。原5个优化提交保持独立，新增趋势提交也可以单独revert。


### 增量验证结果与限制

- Django全套493项通过；最后补充未来时间戳与热力图一致性边界后，13项趋势测试再次全部通过。未来记录仍参与当前最新状态，但不进入历史净新增速度和可用历史天数。
- 前端36个文件、146项Vitest通过，Timer与Drill类型检查及两套生产构建通过。已有大chunk告警保留。
- 最终真实浏览器验证使用后端实际返回的隔离快照，而非硬编码截图数据；中英文各5尺寸与2次独立容器缩放共12项通过，未出现pageerror。
- 趋势端点维持5次SQL；增加了必要的标量历史状态重演，不声称该新增功能比旧错误口径更快。历史Attempt按2000条流式读取，不加载题图、答案或Note；内存状态按目标题数保存。原题目详情/图片性能表仍对应前文独立优化实验。
- 证据可查看本机 `/home/eh/performance-audit-20261111/django-trend-final.log`、`trend-goals-final.log`、`frontend-trend-final.log`、`trend-comparison.json`、`trend-browser-results.json`。真实设备安全区、系统冻结和生产当前数据尚未验证；没有执行生产部署、迁移、重启或配置修改。

趋势独立提交：`1eb3cdf`（动态严选目标与净新增预测）、`0108b9f`（进度交互与响应式图表）。回滚可先分别revert这两个提交，原缓存、作答、详情查询及图片优化不受影响。上线仍需另行授权，正常构建并按既有发布流程切换镜像；本轮没有数据库迁移。


## 2026-11-11 授权生产部署

用户后续明确要求部署。最终应用代码revision为 `ab234ed`，镜像为 `time-tracker-ha:20261111-performance-trends-ab234ed-r2`；旧镜像 `time-tracker-ha:20261111-learning-recovery` 保留用于回滚。仅将既有 `20-local-ports.conf` 的应用镜像更新并重启应用；PostgreSQL、密钥、Session设置、认证和Nginx代理配置保持原样。

发布前核对运行镜像与本地基线ID一致，容器源代码无热修改；`check`、`migrate --plan`、`makemigrations --check --dry-run`通过，没有待执行迁移。新镜像在NUC构建，不在47编译；运行期间未发生OOM，发布后约610MB可用内存、11GB可用磁盘。

备份位于47的 `/var/snap/docker/common/time-tracker-ha/backups/performance-20261111/`：当前业务记录dump（排除大型QuestionAsset二进制表数据）、当前资产元数据、原service drop-in、校验文件及部署/回滚脚本。dump已通过gzip及pg_restore目录检查；业务dump和资产元数据有NUC私有副本。既有完整资产备份继续保留。本次没有修改业务记录或数据库schema，回滚不需要恢复旧数据库覆盖后续作答。

### 静态资源发布修正

第一次发布发现新JS返回404，已实际回滚旧镜像。原因是复用的生产基础镜像没有自动collectstatic入口，初次派生包包含前端dist但未更新staticfiles。修正包在构建阶段明确运行collectstatic；本地HTTP验证新JS/CSS的200和SHA-256，并在生产切换前校验全部166个收集后的前端资源。最终包重新发布后，通过公网逐项比对主JS/CSS与本地构建哈希。已删除失败镜像和47上的临时传输归档，保留最终镜像、旧回滚镜像与业务备份。未通过修改代理或访问控制掩盖资源缺失。

### 真实生产验收

部署前19项、部署后26项公网HTTP检查通过，包括Timer/Drill/EI域名、IP同源API、统一Manifest、前端资源哈希、题目详情、题图GET/HEAD/ETag304。部署前创建的同一个短期测试Session在切换后仍通过认证；验证结束只撤销该测试Session，不清理其他用户Session。Nginx配置检查通过，但没有改动或重载代理配置。未在生产创建测试Attempt或改写Note。

| 严选范围 | 总数 | 已做 | 掌握 | 待复习 | 未做 | 11月21日前每日需净新增 |
|---|---:|---:|---:|---:|---:|---:|
| 小题 |619|345|259|86|274|25|
| 大题 |344|157|83|74|187|17|
| 合计 |963|502|342|160|461|42|

上表为此次生产HTTP验收时的实时结果；与同一用户的严选热力图一致，不是硬编码。后续继续作答会自动更新。EI保留307道原计划，未将数学目标套用到EI。

本机部署证据位于 `/home/eh/performance-deploy-20261111/`，包含preflight-r2.log、static-smoke-r2.log、deploy-r2.log、public-before.json、public-after.json和cleanup.log。真实iPadOS Safari/PWA仍需用户刷新后确认横竖屏与系统生命周期表现。

### 回滚

在47运行以下已实际使用过的脚本可恢复旧应用镜像，不触碰数据库和后续学习记录：

```sh
python3 /var/snap/docker/common/time-tracker-ha/backups/performance-20261111/production.py rollback
```

重新发布时不要省略collectstatic及静态资源校验。运行中的镜像保留既有启动参数，不自动运行迁移。GitHub尚未推送；这次只执行了用户授权的生产部署及本地文档更新。


后续未做题双向导航新增普通范围的两个LIMIT 1查询，严选集合复用已有行数据、额外查询为0；对应查询数有独立回归测试。前文性能表是当时独立优化版本的测量，不代表加入新导航功能后的全部接口查询数。计时冲突后续修复与验证见 [计时冲突恢复](timer-conflict-recovery.md)。
