# Drill / EI / Timer 学习现场恢复

## 状态与上线边界

本次实现需要可逆的 `drill.0035_learning_recovery` 迁移。**未在 47 生产环境执行迁移、重启或部署新前端。** 不应只上线前端：新前端使用计时协议 2，需要对应后端与迁移。实际审计见 `learning-recovery-audit.md`。

### 保留的旧机制

- 题目计时继续使用 `QuestionTimingSession`、现有 `/api/drill/questions/<uuid>/timing/` 和 `(user, question, client_key)` 唯一约束。
- 正式耗时只在原有 `/attempts/` 保存到 `QuestionAttempt.time_spent_seconds`；沿用原有 submission_key 去重、Question 行锁、作答/诊断/复习/Note version 校验和事务。
- 历史作答、耗时及统计查询不回填、不重算。旧 begin/cancel 客户端仍保持原行为。新记录按明确要求采用前台时间；整数秒仍按原服务端向下取整，日报仍按作答提交日期归属整轮耗时（不是新增按日分段事件）；旧时长可能包含后台墙钟时间，分析历史趋势时不能把两者视为完全相同的计时口径。新计时 JSON 留存 `time_basis=foreground_v2`、`attempt_id`、序号与累计值以供审计。
- Timer 的 TimeLog 起止时间、25 分钟/12 小时规则、效率等级、统计和已有运行会话不变；不把题目检查点写入 TimeLog。
- Note 继续使用现有用户名/题目作用域的草稿和服务器自动保存，未另建笔记表。未提交诊断、答案/提示使用情况追加本地草稿，恢复时不会把看过答案的本轮误标为独立作答。
- Cookie/Session/Passkey/CSRF 保持原机制。新增可选 `X-Learning-User-ID` 请求上下文校验，阻止同源另一个窗口切换账号后，旧窗口把旧数据写给新账号。该值不是凭证；没有该头的旧客户端行为不变。

## 数据结构

1. `QuestionTimingSession.recovery`：可空 JSON，协议、累计有效毫秒、剩余准备时间、单调递增序号、窗口 owner、检查点时间、45 秒租约及 finalized。可空是为了旧镜像仍可插入不包含新字段的计时行。
2. `LearningRecoveryState`：用户一对一，三个 workspace 各自的位置/滚动、最近服务、版本，以及前台题目租约指针。不保存另一套作答或时长统计。

计时协议 2：POST 同一 timing URL，action 为 claim/checkpoint/pause，携带 timing_key、owner、sequence、elapsed_ms、countdown_ms。旧 begin/cancel 不改。新作答附带 timing_protocol/owner/sequence/elapsed_ms，在既有作答事务内确认并封存该轮。重放同一 submission_key 不会再计时或新增作答。

恢复 API：GET/PUT `/api/learning/recovery/`，按认证用户隔离，PUT 需要当前版本。只接受学习页面路径和有限滚动字段，不接受账号/分享 Token/外部 URL/凭据；题目和 Timer 记录必须仍存在且属于正确作用域。请求冲突返回 409，默认不缓存。

## 保存与计时规则

- UI 每 500ms 刷新，依据 performance.now 的增量，不用 interval 次数计时。
- 五秒准备时间保留，刷新不会重复准备。每五秒保存本地累计快照，前台每 15 秒发送一次累计检查点；可观测生命周期边界立即本地保存并发送 pause（keepalive）。本地存储不可用时服务器检查点仍可工作。
- 后台/锁屏 visibilitychange、pagehide 暂停；pageshow、可见和 online 时重新 claim。不可观测的超过 15 秒冻结间隙不计入有效时长。操作系统忽略最终事件时，最多损失最后一次本地检查点后的少量时间；不凭冷启动时间戳补算整段后台时间。
- 绝对累计快照取单调上界并按序号去重，不进行“本地秒数 + 服务端秒数”。重复/乱序 pause 不能终止新租约。提交与并发 claim 使用相同用户行锁顺序。
- 同一用户同一时刻只有一个协议 2 前台题目租约。同一设备保留的轮次 key/原 owner/已确认累计基线匹配时可立即恢复，并撤销旧窗口的确认权限；无本地基线的新设备最长等待现有租约 45 秒到期后接管。旧版本客户端不参与新租约，上线后需刷新旧窗口。
- 离线时保留本机快照；原 owner 恢复后续传。尚未成功认领过的新题不会补造可确认时长，已认领的轮次才离线续计；页面和草稿仍可保留。若期间另一个设备接管，则不自动合并重叠时间，保存 `.conflict` 本地副本并采用服务端确认值。临时网络失败不会生成正式作答记录。
- 诊断/笔记/Timer 编辑草稿是用户作用域本地数据，不在 localStorage 保存认证凭据。

## PWA 冷启动

Manifest 的 id/scope 仍为 `/`，start_url 改为 `/?pwa_launch=1`。只有统一 IP Origin、standalone 模式、带该启动标记的根入口才尝试恢复。标记被消费后移除，再以 replace 进入最后一处有效学习页面。

普通 `/`、Home、Refresh、Back、Timer/Drill/EI 导航不带标记，不会被强制跳回上题。已保留的系统页面直接继续，原路由重新加载只恢复该页，不跨服务跳转。三个服务共享最近入口，但各自保存内部位置；失效题目不从缓存强制复活。滚动在数据/图片加载后短时间恢复，用户操作后停止。元数据只在变化时上传，隐藏窗口不持续写位置。

旧主屏幕安装可能保留旧 start_url，需要 iPad 手动重新添加。没有新增离线 Service Worker：已有页面断网可保留待同步数据，但系统完全回收后若连 HTML 都无法加载，不能承诺离线冷启动。

## 文件

- `drill/models.py`, `migrations/0035_learning_recovery.py`, `recovery.py`：扩展旧计时、租约与位置恢复。
- `drill/views.py`, `serializers.py`, `time_server/urls.py`：现有计时/作答接口兼容扩展和位置接口。
- `tracker/learning_context.py`, `time_server/settings.py`：可选账号一致性检查。
- `frontend/shared/{foregroundTimer,learningRecovery}.ts`：累计计时、生命周期、本地快照、位置同步和冷启动。
- 两个前端 `App.vue`、两套 API helper：认证确认后初始化；保护账号作用域。
- `frontend/drill/src/views/QuestionView.vue`：计时、诊断草稿、Note 边界保存和原提交接口接入。
- `frontend/src/components/ActiveSession.vue`, `views/SessionDetailView.vue`：Timer 未提交表单草稿恢复，业务时间不变。
- `deploy/pwa/manifest.webmanifest`：唯一冷启动标记；无需 Nginx 路由变更。
- `frontend/src/lib/*Recovery.test.ts`, `foregroundTimer.test.ts`, `drill/test_recovery*.py`：恢复、并发、兼容和迁移测试。

## 测试命令

前端：`npm run build && npm run build:drill && npm test -- --maxWorkers=2`（frontend 目录）。
后端：`python manage.py test drill.test_recovery drill.test_recovery_migration drill.tests.DrillApiTests --noinput`。并发测试需要隔离 PostgreSQL，SQLite 会跳过 row-lock 测试。测试数据库必须与生产隔离。`python manage.py makemigrations --check --dry-run` 验证模型/迁移一致。

本次日志位于 `/home/eh/learning-recovery-audit/`。实际浏览器测试使用隔离本地 Django 和数据库，HTTP 请求按生产路径规则转发，不修改生产学习数据。Safari 的原生冻结/锁屏/主屏幕窗口行为不能由 Chromium 的合成事件证明。

## 上线与回滚（需要单独授权生产迁移）

1. 核对 47 当前镜像/提交、迁移计划、内存/磁盘；保留旧镜像和 service drop-in。RainYun 不迁移、不启用数据库。
2. 在 47 以现有数据库用户对 time_tracker 执行权限受限的完整 `pg_dump -Fc`；校验 SHA-256、`pg_restore --list`，在本机或备用机器实际恢复演练并核对表数/关键计数。不得在内存紧张的 47 再开一个测试 PostgreSQL。保留既有备份。
3. 暂停应用写入，使用新镜像单次执行 `python manage.py migrate drill 0035`（不运行未知额外迁移）；先检查 `migrate --plan`。迁移只增加恢复元数据，不更新历史耗时。
4. 部署新后端及两个前端，健康检查后再切换 Manifest 文件（原路径原 scope，不修改代理）。不要先把新前端部署到旧 schema。保留现有 Django secret/session、环境文件、证书和代理参数。
5. 实测同一会话、三个入口、GET API、刷新、前后台、冷启动与重复提交。iPad 新建主屏幕图标，确认 start_url 更新。
6. 回滚不恢复整库覆盖新作答历史。先备份新增恢复元数据并暂停写入，再用新镜像反向迁移至 drill 0034，最后切回旧镜像和旧 Manifest。反向迁移只删除恢复字段/表，已提交 QuestionAttempt/TimeLog 保持不变；未完成检查点须先导出以免丢失。只有明确接受停止该恢复功能并授权反向迁移后才执行。旧镜像在新 schema 上可插入旧计时行，但新增 FK 表可能影响旧版本删除父记录，因此完整回滚按上述顺序进行，不把旧镜像+新 schema 当成长期运行方案。

## iPad 实机验收

普通 Safari 和主屏幕 PWA 分别验证：计时一分钟刷新五次；Drill 前后题/EI/Timer 切换；Home 不回跳；锁屏/切 App；系统强制终止后从新图标启动；无网恢复；两台设备竞争；切换账号；输入法尚未结束时退出；缩放/题图全屏。确认后台不增长、焦点恢复与滚动不抢用户操作。App 回收可能不发送最后事件，五秒本地检查点不是零损失承诺。

## 本次验证结果

- 两个生产前端构建通过；30 个文件 / 118 项前端测试通过。
- 隔离 PostgreSQL 全套 64 项测试通过，覆盖既有 Drill API/热力图/统计与新增恢复逻辑；最后又重跑了 19 项恢复/迁移测试及账号过期兼容测试。
- 模型/迁移检查：No changes detected。可逆迁移演练保留旧作答 37 秒耗时，并验证旧客户端省略 recovery 列仍能插入。
- 本地真实 Django + 浏览器：前台等待 65 秒（含原有 5 秒准备）、连续刷新 5 次后计时约 62 秒；Note 和答案使用状态恢复；合成隐藏事件暂停；18 秒断网恢复；Drill/EI/Timer 切换；Home 保持首页；带标记的冷启动恢复；提交 201 响应丢失后刷新重试返回去重 200。
- 生产只读复核：仍为 `time-tracker-ha:20261111-reader-glass`、健康，实际 drill 迁移为 0034；生产计时表仍是原有七个字段。未执行新迁移、未重启生产应用、未替换生产 Manifest。
