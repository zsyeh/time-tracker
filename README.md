# Personal Learning OS

一个私有优先、低摩擦启动、重视结束复盘的个人学习操作系统。后端是 Django/DRF，前端是 Vue 3 + TypeScript + Vite + ECharts + Element Plus，生产环境保持同源部署。

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

- 独立的 `drill.ehzsy.site` 刷题前端与计时前端共用 Django 账号和 PostgreSQL，但不会在 `timer.ehzsy.site` 添加入口。首次访问会自动回到 Timer 域名使用既有 Passkey，再通过 90 秒一次性凭证返回 Drill，无需重建原 Passkey。源库的 3,553 条导入记录已清洗为 3,208 条可练习记录，345 条目录/分隔项默认隐藏；真题、真题改编、模拟卷、题册题、竞赛题和来源未明题分开筛选。
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

生产部署必须先备份，再停止 Web/MCP、执行迁移和前端构建，最后重启。完整步骤见 [deployment](docs/deployment.md) 和 [backup/restore](docs/backup-and-restore.md)。2 GiB VPS 的实测 PostgreSQL 参数、磁盘预算、回滚和监控命令见 [PostgreSQL tuning report](docs/postgresql-tuning.md)；它是当前服务器基线，不是应当复制到其他机器的通用模板。

## 常用路由

- `https://drill.ehzsy.site/practice`：独立刷题前端（使用与 Timer 相同的账号数据库）
- `https://drill.ehzsy.site/practice/<uuid>`：稳定的题目页面及同类题入口
- `https://drill.ehzsy.site/heatmap`：个人官方真题状态热力图
- `/api/drill/*`：登录后可用的题库、作答、同类题、进度和图片 API
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
