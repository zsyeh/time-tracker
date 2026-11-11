# Personal Learning OS

一个私有优先、低摩擦启动、重视结束复盘的个人学习操作系统。后端是 Django/DRF，前端是 Vue 3 + TypeScript + Vite + ECharts + Element Plus，生产环境保持同源部署。

## 当前生产事实源（维护前必须阅读）

> 本节记录 2026-11-05 的真实生产状态和本轮长期对话形成的强制约束。若仓库中的旧文档、脚本名称、systemd 描述或历史 HA 配置与本节冲突，以本节为准。不得根据文件名中的 `standby`、`promoted` 或旧故障切换脚本推断当前角色。

### 2026-11-11 基线补充

最近一次已验证生产业务版本为 `ab234ed`，镜像 `time-tracker-ha:20261111-performance-trends-ab234ed-r2`，`drill` 迁移仍为 `0035_learning_recovery`；此前学习恢复版本为 `ab6040f` / `time-tracker-ha:20261111-learning-recovery`。GitHub 的 `master` 与功能分支已同步到后续文档提交 `7d5b312`。恢复机制及授权、备份范围、回滚限制见 [`docs/learning-recovery.md`](docs/learning-recovery.md)。较早的 11 月 5 日 dump 已清理，现有完整备份为 `backups/examtypes-20261110/pre-examtypes.dump.gz`，并有已验证的 NUC 异地副本；恢复时先解开 gzip 外层。以下 11 月 5 日表格与发布记录保留作历史参考，不能用其中的旧镜像、迁移号或 dump 路径推断当前状态。单一业务写入和数据保护约束继续有效。

本轮性能优化及严选趋势改造已于2026-11-11经用户授权部署；没有数据库迁移或Nginx配置变更。后续生产操作仍须另行授权。 实测数据、独立提交及追加的严选题净新增预测和横竖屏修复见 [短期性能与可靠性报告](docs/short-term-performance.md)。

### 当前版本与服务入口

| 项目 | 当前事实 |
| --- | --- |
| GitHub 分支/提交 | `codex/ai-learning-share-20261104`（Draft PR #12；生产应用代码 revision `7302b9f`） |
| 生产镜像 | `time-tracker-ha:20261105-ai-share` |
| 唯一业务写入节点 | `47.95.10.128` |
| 业务组件 | Timer、Drill、EI、Django Session 和业务 PostgreSQL 均在 47 写入 |
| RainYun | HTTPS/证书/反向代理节点，不运行可独立写业务数据的 Django/PostgreSQL |
| NUC | 单向内容克隆/离线副本；同步功能关闭，不得成为写入或自动故障提升节点 |
| 数据库迁移 | `drill` 已应用到 `0031_learningshare` |
| 生产验证基线 | Django 357 项测试、前端 74 项测试、TypeScript、Vite 生产构建均通过 |

目前主要访问方式：

- `https://47.95.10.128/`：Timer。
- `https://47.95.10.128/drill/`：Drill 数学题库。
- `https://47.95.10.128/ei/`：EI 892 题库。
- `https://timer.ehzsy.site`、`https://drill.ehzsy.site`、`https://ei.ehzsy.site`：兼容域名入口；应用写入仍最终到达 47。

47 的 Nginx 会处理 `/drill`、`/ei` 前缀重写。直接请求 Django 内部端口时这些前缀可能返回 404，这是代理层与应用层的边界，不应据此修改 Django 路由。公网入口才是验收对象。

### 不可破坏的数据与拓扑约束

1. 47 是唯一业务 PostgreSQL 主库。禁止双向同步、双主、冲突合并、自动提升旧主或把 RainYun/NUC 恢复为业务写入节点。
2. RainYun 即使只提供页面读取，也必须反向代理到 47；Django Session 读取可能产生写入，不能在 RainYun 本地运行一套业务 Django。
3. 不得删除或重建题库，不得修改题目 UUID，不得覆盖用户作答、Note、诊断、计时、收藏、复习计划和掌握度。
4. 生产迁移、服务重启、Nginx/证书调整和主备角色变化必须得到明确授权。普通代码审计不包含这些权限。
5. 旧 HA 单元和脚本只用于历史分析。不得创建 `/etc/time-tracker/legacy-ha-explicitly-enabled`，不得启用自动 promotion、`pg_rewind`、旧 lease 或数据库合并流程。
6. 47 上业务库实际连接到本机 `127.0.0.1:55433`，经验证 `pg_is_in_recovery() = false`、`transaction_read_only = off`。主机还存在一个历史 5432 PostgreSQL listener；未观察到业务客户端使用它，但在确认消费者和留存需求前不得擅自删除。
7. 备份是恢复输入，不是在线同步输入。恢复 dump 前必须停止写入并进行人工确认，不能把 dump 导入正在服务的第二主库。

当前架构选择“单一权威写入和可验证恢复”，不再承诺旧设计中的自动双机写入故障切换。RainYun 代理本身不能在 47 完全不可达时继续接受题目状态写入；若未来重新要求自动容灾，需要重新设计单写主库的共识/提升流程，不能复用历史双向同步。

### 生产备份、迁移与回滚

2026-11-05 部署 AI 学习数据分享前已执行完整 PostgreSQL custom-format dump，并使用 `pg_restore --list` 和 SHA-256 校验。生产遵循“仅保留最新完整 dump”；新备份验证后可清理旧备份：

- dump：`/var/backups/time-tracker/postgresql/time-tracker-20261105-011957.dump`
- 校验文件：同目录 `.dump.sha256`
- dump 权限：`600`
- 当前大小：约 2.86 GB
- Note 合并回滚审计：`/var/backups/time-tracker/note-merge/note-merge-audit-20261103-r25.json`，权限 `600`

审计文件含用户原始文本，禁止提交 Git、复制到 RainYun 或打印到日志。数据库连接串、Passkey 材料、Session Cookie、一次性 handoff token 和加密密钥同样不得进入 README、issue、命令输出或访问日志。

生产 secret bind mount 当前使用 `root:tracker` 和 `0640`：root 可写、容器内 tracker 组只读。不要机械改成 `0600`；这会导致非 root 容器无法读取 `.env.database` 并在入口迁移阶段反复退出。dump 和不需要容器读取的审计文件才使用 `0600`。

推荐发布顺序：

1. 确认 47 为可写主库、RainYun 无业务写入、旧 HA marker 不存在。
2. 记录当前镜像 tag，创建并校验新的完整 dump；只有新 dump 成功后才清理旧 dump。
3. 在隔离测试库运行后端测试，在前端运行单测、类型检查和两个 Vite build。
4. 构建带 Git revision label 的不可变镜像并加载到 47。
5. 使用新镜像运行 `manage.py check`、`migrate --plan` 和数据迁移 dry-run。
6. 数据迁移必须幂等；正式执行后立即二次执行并确认 `changed_pairs = 0`。
7. 先在独立端口按真实 entrypoint 启动烟雾测试。不能绕过 `collectstatic` 后把缺失 manifest 误判为应用故障。
8. 仅切换 47 Web 服务，等待 `active`、容器 `healthy`、登录页、静态哈希资源及公网 Timer/Drill/EI 全部通过。
9. 回滚应用时恢复上一镜像 tag；新增迁移均为加法时通常保留数据库结构。只有确认数据恢复必要时才还原 dump。

r25 的 systemd drop-in 切换前副本保存在 47 的 `/etc/systemd/system/time-tracker-ha-web.service.d/20-local-ports.conf.pre-ai-share-20261105`；r25 镜像保留作为快速应用回滚点。新迁移只新增分享表，不应把切换到旧数据库当作常规回滚。

### IP Passkey 登录的真实实现

WebAuthn RP ID 不能使用裸 IP，因此禁止把 `47.95.10.128` 配置成 RP ID，也禁止关闭 WebAuthn 校验。IP 登录流程是：

1. 用户在 `https://47.95.10.128` 选择“使用 Passkey 登录”。
2. 浏览器跳转到 `https://timer.ehzsy.site`，继续使用原有 Passkey/Face ID/Touch ID。
3. Timer 生成服务器端仅保存摘要的一次性 `DrillLoginHandoff`。
4. token 通过 URL fragment 回到固定的 `https://47.95.10.128/ip-auth/complete`，前端立刻移除 fragment，再以 CSRF 保护的 POST 兑换。
5. 47 原子消费凭证并建立独立 IP Host Session，然后返回经过白名单校验的原始站内路径。

凭证有效期不超过 90 秒、不可重放、不可跨目标站点使用；回调 Host/Origin 固定，禁止根据任意 Host、Referer 或用户 URL 决定目标。IP 入口必须保留密码登录。Linux 自动化只能验证服务器流程，Face ID、iPadOS Safari、安全区和系统剪贴板必须在实体设备上验收。

### Drill / EI 的核心数据语义

- 只有成功保存的 `QuestionAttempt` 才算一次有效作答；打开题目、浏览、看答案不自动计为完成。
- 每次作答追加新 Attempt，不覆盖历史。客户端 submission key 和服务端事务共同防止双击、超时重试导致重复 Attempt 或 TopicMastery 虚假升级。
- 状态分为未开始、已掌握、待复习；Undo/Reset 必须重建由系统推导的复习/掌握结果，不能删除无关的手动评价。
- 作答状态、结构化诊断、独立程度和题目 Note 是四个不同维度，不能互相替代。
- 诊断保留 A、B1、B2、B3、C1、C2、C3、D，以及 K/M/E 三层能力信息、提示/答案使用情况和 D0/D1/D3/D7 复习计划。
- 当前唯一可编辑自由文本是 `QuestionUserState.note`。`QuestionAttempt.note/correction_note/knowledge_note/first_step_note` 仅作为历史证据保留。
- r25 上线时将 19 个用户—题目组合的旧自由文本无损合并到 canonical Note；最长合并结果 113 字符，二次执行变更为 0。
- Note 使用版本号/HTTP 409 防止多标签页或多设备旧内容覆盖新内容；快速切题必须保留本地草稿并隔离旧请求响应。
- Drill 与 EI 共用实现和账号，但所有题目、统计和用户状态必须按当前用户与 workspace/host 隔离。

诊断指标口径见 [`docs/attempt-diagnostics.md`](docs/attempt-diagnostics.md)。部署与回滚细节见 [`docs/drill-ei-reliability-deployment.md`](docs/drill-ei-reliability-deployment.md)。

### 当前题目页、统计和导入功能

- 题目页采用“题目工作区 + 顶部稳定导航 + 紧凑统一作答栏 + 按需辅助面板”。上一题/下一题位于顶部；题图或当前题加载失败时仍保留恢复与可用导航，不得继续显示旧题伪装为新题。
- 主要操作是“掌握并下一题”和“待复习并下一题”；诊断会自动保存并有明确动画/状态反馈。诊断选择可联动待复习，但错误类型不等于知识掌握等级。
- iPad 竖屏优先保证题干/题图宽度，手机使用约 44px 触摸目标，横屏/桌面可使用题目与控制区双栏。每次翻页保持全局框架稳定并回到合理阅读位置。
- “复制题图”优先使用 Clipboard API；多图纵向拼成 PNG。Safari 不支持时降级为系统分享或下载，不能悄悄只复制第一张图。
- 分享按钮复制当前权威站点 URI，不唤起 Apple Share；使用 47 时链接保持 `/drill/...` 或 `/ei/...` 完整链条。
- Vue Router 有未知路径兜底；Django SPA fallback 只覆盖合法页面，不能把 `/api/`、`/static/`、认证、Passkey 回调和分享接口的真实 404 改成 200。
- Insight 支持诊断、科目、书籍/章节、状态、日期、是否含 Note、关键词和排序的服务端组合筛选；Note 可原地展开，返回时恢复过滤器、分页和滚动位置。
- 刷题趋势按北京时间自然日统计同一题当日去重题数、提交次数和周期不同题数；三者不能混淆。支持 7/14/30/50/90 天、7 日移动平均、目标线和截止日预测。
- PDF 页码状态入口只处理“严选题”，题目册页码与题答对照册页码分开输入；可预览匹配、批量标记 Mastered/Need to review、记录同款结构化诊断和唯一 Note，不能导入标准题库。
- 892 每日公式及其他四科公式循环是独立训练入口；历史表现不可用时不得编造 A/B/C 掌握状态。

### 本轮长期对话形成的关键决策

以下是从问题定位到 r25 上线的关键中间结论，供后续维护者理解“为什么这样实现”：

1. 最初尝试过本机、47、RainYun、NUC 的主从/灾备与反向同步；由于双向写入会产生无法可靠自动合并的用户状态，最终明确 47 为唯一权威写入节点。
2. 47 曾以 `/timer`、`/drill`、`/ei` 和端口混合暴露，出现 CSRF、空白页、URI 链不完整和分享 500。最终统一到 HTTPS 443，用 `/drill`、`/ei` 前缀与域名兼容入口。
3. 题目页曾存在重复的 Next、红/黄复习、Mastered、Need to review、诊断和笔记卡片，横屏侧栏还会只弹出一半或收起正文。最终改成稳定顶部导航和单一作答工作流。
4. EI 题图曾因代理/资源 URI 问题整体无法加载；因此静态哈希资源、题图 API、Host 与前缀重写必须作为每次部署的烟雾测试。
5. 旧刷题数据没有进入新诊断看板，根因是新能力字段无法从历史行为可靠推断。历史记录保留为 unknown，不能把“做过”伪造为“独立做对”。
6. “错误原因”自由文本和 Note 并存造成重复与丢失风险，最终确定唯一自由文本 Note；结构化 A-D 诊断继续独立保存。
7. PDF 页码功能最初错误覆盖标准题库，最终限制为严选题并要求题目册/题答对照册双页码核验。
8. IP Passkey 不能直接使用裸 IP RP ID，最终复用 Timer 域名的 WebAuthn 和一次性 handoff，而不是降低安全校验。
9. r25 发布前完成 357 个 Django 测试、74 个前端测试、类型检查和双前端构建；生产先备份再迁移，Note 合并通过幂等复跑。
10. 部署中一次诊断命令意外暴露了数据库连接凭据，已在 2026-11-03 完成数据库密码轮换并清除旧凭据临时副本。后续禁止打印完整进程命令行或连接串。

## 维护者 / Codex Agent 主提示词

下面的提示词整合了本轮对话中反复确认的边界。可以直接交给后续 Agent；具体需求附在末尾，不要删除安全约束。

```text
你正在维护 GitHub 项目 zsyeh/time-tracker。请直接检查真实代码、测试和生产角色，完成可运行实现，不要只给方案。

生产事实：
- 47.95.10.128 是 Timer、Drill、EI、Django Session 和业务 PostgreSQL 的唯一写入节点。
- RainYun 只允许做 HTTPS、证书和反向代理；NUC 只允许单向内容克隆。
- 禁止双主、双向数据库同步、数据合并、自动提升旧主以及启用历史 HA marker。
- 仓库、历史文档和 systemd 文件名可能落后于真实生产，必须先只读核对 Git commit、镜像 tag、迁移状态、数据库角色和线上代码差异。

数据安全：
- 不得删除/重建题库，不得改变题目 UUID，不得清空或覆盖用户作答、Note、诊断、计时、收藏、复习计划和掌握度。
- 任何数据迁移都要先完整 PostgreSQL dump、校验、dry-run、脱敏统计、幂等复跑和明确回滚审计。
- 禁止输出数据库连接串、密码、Cookie、Passkey 材料、一次性 token、加密密钥或用户文本。
- 未经明确授权，不得部署、重启生产服务、执行生产迁移、修改 Nginx/证书或切换数据库角色。

认证与路由：
- 裸 IP 不能作为 WebAuthn RP ID。IP Passkey 必须跳到 timer.ehzsy.site 完成认证，再通过固定 Origin/Host、90 秒内、摘要存储、一次性原子消费的 handoff 返回 47。
- 保持 CSRF、Secure/HttpOnly/SameSite Cookie、限流和密码备用登录。
- 47 使用 443 和 /drill、/ei 前缀；域名入口必须兼容。分享链接由当前权威入口生成完整 URI。
- SPA fallback 只能处理合法前端路由，API、静态资源、认证、分享和回调必须保留真实状态码。

刷题语义：
- 只有成功保存的 QuestionAttempt 才算作答；浏览、看题、看答案不算完成。
- submission key 幂等，Attempt、TopicMastery、复习计划和状态变更必须在事务内一致。
- 作答状态、结构化诊断、独立程度和 QuestionUserState.note 是四个独立维度。
- 唯一可编辑自由文本是 canonical Note；历史 Attempt 文本只能无损迁入，不能删除。
- 旧数据缺少独立作答/诊断证据时必须标 unknown，禁止推断。
- Drill/EI 的用户与 workspace 数据必须隔离。

前端体验：
- 题目页保持稳定顶部上一题/下一题；加载失败不得显示旧题，也不能让可用导航消失。
- 主操作统一为掌握/待复习并按设置进入下一题；诊断自动保存必须有清晰反馈。
- Note 自动保存需版本冲突保护，本地草稿不可无提示覆盖服务器新值。
- iPad 竖屏优先题干与题图，手机触摸区约 44px，横屏侧栏不能遮挡、半开或带走正文。
- 图片复制使用原始图和 ClipboardItem，多图明确拼接，Safari 提供分享/下载降级。

实施顺序：
1. 只读审计真实分支、部署版本、模型、接口、前端和数据语义。
2. 先写/补回归测试，再修数据一致性、认证和路由，再做交互与视觉优化。
3. 运行 Django 全量测试、前端单测、TypeScript 检查、Timer 与 Drill 两套 production build。
4. 报告修改文件、迁移、测试、兼容风险、未完成的实体 Safari 验证。
5. 只有得到部署授权后，才按“备份 -> 校验 -> dry-run -> 新镜像独立烟雾测试 -> 47 切换 -> 公网健康检查 -> 保留上一镜像回滚”的顺序上线。

本次具体任务：
[在这里追加本次需求。]
```

README 只保存长期有效、已脱敏的工程事实。完整聊天原文可能包含过期假设、临时故障和敏感数据，不应原样提交；需要保留的中间信息应像上面这样提炼为决策、根因、约束和验收标准。

## Docker Hub 与一键部署

> **[打开一键部署页面](https://app.ehzsy.site)** · **[Docker Hub 镜像](https://dockerhub.ehzsy.site)** · 镜像：`ehzsy/time-tracker:latest`

Docker Run 版本：

```bash
curl -fsSL https://app.ehzsy.site/install/docker-run.sh | sh
```

Docker Compose 版本：

```bash
curl -fsSL https://app.ehzsy.site/install/docker-compose.sh | sh
```

需要指定公网域名时，在管道末尾增加参数，例如：

```bash
curl -fsSL https://app.ehzsy.site/install/docker-compose.sh | sh -s -- study.example.com
```

两个脚本都会拉取已经构建好的前后端镜像、创建持久化数据卷、生成随机 Django 密钥、执行数据库迁移和健康检查，并在空数据库中输出一次性管理员账号。公网 Passkey 必须配合 HTTPS 反向代理使用。

## 主要能力

- 独立的 `drill.ehzsy.site` 刷题前端与计时前端共用 Django 账号和 PostgreSQL，但不会在 `timer.ehzsy.site` 添加入口。首次访问会自动回到 Timer 域名使用既有 Passkey，再通过 90 秒一次性凭证返回 Drill，无需重建原 Passkey。当前 4,228 条导入记录中有 3,883 条可练习记录，345 条目录/分隔项默认隐藏；全部题图都从原 PDF 以 180 DPI 渲染，并保留裁剪来源以便安全重建。题目页可按题册顺序进入下一题；同类题入口会先选择官方真题或模拟/题册练习，来源不会混淆。所有题库材料由 B 站 UP 主 cxy（澄潇宇）收集整理，**Thanks to cxy**；PDF 作者信息另行保留和展示。
- `ei.ehzsy.site` 是独立的 892 电子信息专业综合训练入口，复用 Drill 的高性能训练交互与同一 Django 账号，但按 hostname 隔离目录、进度、收藏和作答记录。题库按电路原理、模拟电子技术、数字电子技术、信号与系统、通信原理拆成五本独立 Book；当前结构化 Markdown 题库包含 156 道基础例题与 60 道简答题，题干和参考答案均直接渲染 Markdown、LaTeX，不生成额外截图；首次访问同样经 Timer 的一次性凭证接力，继续使用原有 Passkey。
- 真题热力图只覆盖可明确识别的官方历年考试题。题目状态统一为灰色未做、绿色已掌握、黄色待复习，可随时修改、重置或撤销最近一次修改；练习历史和结果按用户严格隔离。
- 从 2026-05-23 开始的学习热力图；达到 5 小时的日期使用高对比亮绿色。
- 点击任意日期查看 24 小时在线/未在线时间轴和当天每次学习标题；再点标题才显示正文详情。
- 普通连续学习日、连续 5 小时日、历史最长连续日、达标日数、每日首次开始时间。
- `/start/math`、`/start/english`、`/start/professional` 快速启动，服务器时间为准且重复请求幂等。
- 运行中隐藏时长；结束时只填写 `Title` 和可粘贴 ChatGPT 内容的 `Details`。
- 结算时可选 A–F 效率等级（`1.00 / 0.95 / 0.90 / 0.85 / 0.80 / 0.75`，默认 A）；真实起止时间保持不变，热力图、科目、任务、标签和 Trends 使用折算后的计入时长。
- `Details` 支持按需 Markdown 预览、KaTeX 行内/块级公式、代码高亮、表格、任务列表、脚注和 GFM Callout；默认不加载预览引擎。
- 历史回顾默认直接显示 Markdown 预览，支持原生顶层沉浸式全屏阅读、单独进入编辑，以及按会话统计回顾次数和近 28 天回顾趋势。
- 可选的按需公式窗口提供线性映射、复变映射与 domain coloring、Fourier/FFT、Laplace 数值积分和三维曲面。该功能默认关闭，管理员可在 Django Admin 的全局站点策略中开启；关闭时 Markdown 不生成公式快捷按钮，也不会加载可视化代码。开启后点击公式旁的 `↗` 会自动分类并直接打开对应场景。见 [Math Lab](docs/math-lab.md) 与 [渲染兼容性](docs/math-renderer-compatibility.md)。
- `⌘/Ctrl + K` 全局关键词搜索学习标题、正文和 Issues，结果按需下钻完整内容。
- 每次完成后生成一个独立 Markdown 文件并通过本机 GitHub CLI 推送到私有仓库；管理员写入主分支，普通账号写入以用户名命名的隔离分支，失败会进入持久化队列自动重试。
- 少于 25 分钟、超过 12 小时或主动放弃的会话直接删除，不写入完成记录。
- Django Session 登录、邀请码注册、可配置“记住我”、django-allauth Passkey/WebAuthn、多用户数据隔离；支持不保存密码的 Passkey-only 注册，而且该路径同样必须验证邀请码。管理员可在专用面板切换为开放注册（开放后所有注册方式都免邀请码）。普通用户每天可生成一个单次邀请码，管理员可生成 1–100 次邀请码，双方都能看到邀请码注册人。
- 登录页保留明确的邀请注册按钮，并提供公开的 `/guide/` 使用说明和 `/contact/` 联系入口；注册页显示管理员邮箱。
- Django Admin 提供独立的邀请码控制页，可设置 1–100 次使用容量并查看剩余次数、使用时间和注册访客。
- 科目趋势、周/月汇总、学习记录检索和问题闭环；知识点入口已从当前界面移除。
- Coolapk 绿、YouTube 红、Bilibili 粉、Meituan 黄和 Apple 白五套主题颜色，以及  标签图标。
- 登录页提供小尺寸的 Docker Hub、项目源码、GitHub 主页与个人博客链接。
- 只有超级管理员可从设置页修改主页内容、自习室口令、记录起始日期、考试日期和倒计时名称并与本地 `.env` 双向同步；普通用户使用隔离的安全默认值，不会收到自习室口令或私有主页内容。
- 注册允许短密码或纯数字密码，但界面会明确推荐首次登录后绑定 Passkey；同一网络 15 分钟内允许 20 次失败登录，管理员可从 Django Admin 查看并重置临时锁定。
- 可撤销、可过期、只允许启动指定科目的 Launch Token，支持浏览器、NFC、快捷指令和 IoT POST。
- Launch capability 同时生成相互隔离的免登录 Start URI 与 Disturbance URI，可保留原 URI 临时暂停/恢复，并设置每日有效时段（默认上海时区 06:00–22:00）。iPhone 可用“获取 URL 内容”POST 启动学习；“充电器已断开连接”自动化可累计当前 Session 的扰动次数。
- CSV、JSON、Markdown 完整导出；不嵌入任何 AI API。
- 每个用户可在 Settings 中选择服务端管理的 AES-256-GCM 静态加密。开启后学习标题、Markdown、复盘、主观评分和 Issue 文本在数据库及数据库备份中只保存密文；趋势所需的最小运行元数据保持可索引。该功能不增加密码、不影响导出、GitHub 同步或明文公开分享，但不是端到端加密，服务器持钥者仍可解密。
- 用户可按学科创建最多四级的任务预设（如 `Mathematics → Calculus → Limits`），把任意层设为首页一键按钮，并配置可复用内容标签。空标题会在存在预设时取叶子任务名；结束页可点选标签和最近标题，Trends 按任务路径与标签聚合。
- 可选的密钥保护容量压测系统使用隔离账号跑真实 API workload，拆分 queue/app/CPU/DB 时间，采集主机、进程、网络和 PostgreSQL 指标，自动寻找 knee point 并推导安全 QPS/DAU。PC 工具与双语说明见 [`stress_test/`](stress_test/)，实际生产审计见 [`ARCHITECTURE_AUDIT.md`](stress_test/ARCHITECTURE_AUDIT.md)。默认关闭，无磁盘压测、无远程 shell。

## 本地开发

需要 Python 3.11+ 和 Node.js 18+。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd frontend && npm install && npm run build && cd ..
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

访问 `http://127.0.0.1:8000/`。首次登录后在“设置”中绑定 Passkey。开发模式允许 HTTP WebAuthn；生产环境必须是 HTTPS。

超级管理员登录后进入 `Settings` → `Homepage and schedule` 可以修改本地实例参数。普通安装读写项目根目录的 `.env`；官方 Docker 镜像读写持久卷内的 `/app/data/tracker.env`。网页仅允许超级管理员修改五个展示参数，不会读取或覆盖 Django 密钥、数据库地址、GitHub 凭据等其他环境变量。普通账号既不能读取也不能写入这些本地值。

前端独立开发：

```bash
cd frontend
npm run dev
npm run typecheck
npm test
npm run build
npm run build:drill
```

## Docker 一键安装

SQLite 兼容模式（适合单机和从旧版本平滑升级）：

```bash
./install.sh your-domain.example.com
```

新生产部署推荐 PostgreSQL：

```bash
./install.sh --postgres your-domain.example.com
```

脚本会生成权限为 `600` 的 `.env`、随机密钥、构建前后端、迁移数据库、收集静态资源、运行健康检查，并在空数据库创建一次性初始管理员。已有 `.env` 和数据库卷不会被覆盖。

```bash
docker compose ps
docker compose logs -f web
docker compose --profile mcp up -d
```

PostgreSQL 模式的后续命令需同时带 `-f compose.yaml -f compose.postgres.yaml`。

## 测试与部署检查

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
cd frontend && npm run build
./deploy/scripts/smoke-test.sh http://127.0.0.1:8000
```

原生 VPS 部署使用 `deploy/scripts/deploy-native.sh`。该脚本会同时构建 Timer 与 Drill、执行数据库迁移、运行 `collectstatic`，然后重启服务并等待就绪。不要只运行 Vite 构建；否则新 HTML 可能引用尚未进入 `staticfiles` 的哈希资源，表现为前端白屏。对于不足 3 GiB RAM 且没有 swap 的主机，脚本仅在构建期间创建 1.5 GiB 临时 swap，并在退出时自动清理，避免 Vite 构建中途被 OOM killer 终止。

安全优先：生产部署必须先使用 `scripts/postgres-backup.sh` 生成并校验 PostgreSQL dump，再停止 Web/MCP、执行迁移和前端构建，最后重启；需要回退时使用 `scripts/postgres-rollback.sh --yes`，脚本会先自动保留当前库备份。完整步骤见 [deployment](docs/deployment.md) 和 [backup/restore](docs/backup-and-restore.md)。2 GiB VPS 的实测 PostgreSQL 参数、磁盘预算、回滚和监控命令见 [PostgreSQL tuning report](docs/postgresql-tuning.md)；它是当前服务器基线，不是应当复制到其他机器的通用模板。

## 常用路由

- `https://drill.ehzsy.site/practice`：独立刷题前端（使用与 Timer 相同的账号数据库）
- `https://drill.ehzsy.site/practice/<uuid>`：稳定的题目页面及同类题入口
- `https://drill.ehzsy.site/heatmap`：个人官方真题状态热力图
- `https://drill.ehzsy.site/papers`：数学二智能组卷历史
- `https://drill.ehzsy.site/papers/new`：标准模拟、强化卷、弱点训练入口
- `https://drill.ehzsy.site/papers/<uuid>`：固定题序的考试模式
- `https://drill.ehzsy.site/papers/<uuid>/review`：答案、解析与学习状态复盘
- `https://dash.ehzsy.site/`：仅 superuser 可进入的服务、静态资源、数据库和 VPS 资源状态面板，并提供固定白名单运维操作
- `https://ei.ehzsy.site/practice`：892 电子信息专业综合训练
- `https://ei.ehzsy.site/heatmap`：按 156 个知识点统计的个人 EI 热力图
- `/api/drill/*`：登录后可用的题库、作答、同类题、进度和图片 API

数学二组卷使用版本化 `ExamBlueprint`，题型数量是硬约束，章节/知识点分散是软约束。默认排除当前用户已掌握和 cooldown 内刚做过的题；Paper 只保存 Question/QuestionRevision 外键、顺序、分值与生成 seed，不在 PaperItem 复制题干、图片、答案或解析。轻量 `QuestionRevision` 固定生成当时的文本与资源引用，后续修改原题不会改变历史卷。题目卷和解析卷 PDF 都从固定 revision 重新生成。

题型元数据可先运行可解释规则，再把低置信度集合交给 Agent 批处理：

```bash
python manage.py classify_question_types --apply --export-review question_type_review.jsonl
# Agent 为每行补充 question_type 与 confidence 后：
python manage.py classify_question_types --import-agent agent_labels.jsonl

# 或使用可恢复的本地 OCR/版式 Agent 直接处理图片型题库：
python manage.py agent_classify_question_types --apply --workers 2
```

允许标签为 `single_choice`、`fill_blank`、`solution`。OCR Agent 综合来源标签、题目图片中的选项/空格结构、答案形式与版式，保存理由和置信度；低于 0.75 的结果仍作为待复核集合。人工确认记录不会被后续批处理覆盖。
- `/`：跳转到 `/today`
- `/today`：Today
- `/trends`：趋势
- `/sessions`：Session History
- `/sessions/<uuid>`：需要登录且按 owner 隔离的 Session 永久文章 URI
- `/issues`：Issues
- `/settings`：Settings
- `/share/<token>`：无需登录的独立只读分享文章；token 可撤销、可过期且数据库只保存 hash
- `/accounts/login/`：密码或 Passkey 登录
- `/accounts/signup/`：密码注册（默认需要有效邀请码）
- `/accounts/signup/passkey/`：Passkey-only 注册（默认同样需要邀请码）
- `/guide/`：公开、独立的网站使用说明
- `/contact/`：限流且不落库的管理员邮件联系表单
- `/legal/`：中英双语服务、数据与 GPL 免责声明
- `/accounts/2fa/`：Passkey 管理
- `/start/<subject>`：登录用户快捷启动
- `/launch/<token>`：受限启动令牌
- `/api/launch/<token>/start`：IoT 启动
- `/api/disturbance/<token>/record`：免登录、独立密钥、仅记录当前 Session 扰动的 POST URI
- `/api/export/{csv,json,markdown}/`：完整导出
- `/api/sessions/<id>/reviews/`：记录回顾并读取该会话的回顾趋势
- `/api/sessions/<uuid>/`：按需读取或更新本人 Session 正文
- `/api/sessions/<uuid>/share/`：创建、查看状态或撤销公开分享
- `/api/public/shares/<token>/`：公开只读、最小字段 Session 文章
- `/api/stress-test/probe/`：默认关闭、Bearer 密钥保护、仅支持固定动作的有界容量测试探针；只有显式打开隔离数据设置后才创建测试账号
- `/api/invite-codes/`：普通用户每日单次邀请码与管理员高级邀请码管理
- `/admin/`：管理员恢复入口
- `/admin/tracker/invitecode/dashboard/`：管理员邀请码容量与访客记录
- `/admin/tracker/invitecode/auth-recovery/`：管理员查看并重置登录限制

第一次使用建议先看 [使用说明](docs/usage.zh-CN.md)。API、认证、模型和部署配置分别见 [API](docs/api.md)、[认证](docs/auth.md)、[数据模型](docs/data-model.md)、[架构](docs/architecture.md)。

## 许可与免责声明

本项目依照 [GNU GPL-3.0-or-later](LICENSE) 发布。已发布源代码可以依照 GPL 持续使用、查看、修改和再分发。软件及托管服务按“现状”提供，不保证永久运行或绝不丢失数据；用户可以随时从设置页导出 CSV、JSON 和 Markdown 完整记录。完整中英条款见网站 `/legal/`。
