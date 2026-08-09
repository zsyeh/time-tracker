# Personal Learning OS

一个私有优先、低摩擦启动、重视结束复盘的个人学习操作系统。后端是 Django/DRF，前端是 Vue 3 + TypeScript + Vite + ECharts + Element Plus，生产环境保持同源部署。

## 主要能力

- 从 2026-05-23 开始的学习热力图；达到 5 小时的日期使用高对比亮绿色。
- 点击任意日期查看 24 小时在线/未在线时间轴和当天每次学习标题；再点标题才显示正文详情。
- 普通连续学习日、连续 5 小时日、历史最长连续日、达标日数、每日首次开始时间。
- `/start/math`、`/start/english`、`/start/professional` 快速启动，服务器时间为准且重复请求幂等。
- 运行中隐藏时长；结束时只填写 `Title` 和可粘贴 ChatGPT 内容的 `Details`。
- 少于 25 分钟、超过 12 小时或主动放弃的会话直接删除，不写入完成记录。
- Django Session 登录、可配置“记住我”、django-allauth Passkey/WebAuthn、多用户数据隔离。
- 科目趋势、周/月汇总、学习记录检索和问题闭环；知识点入口已从当前界面移除。
- Coolapk 绿、YouTube 红、Bilibili 粉、Meituan 黄和 Apple 白五套主题颜色，以及  标签图标。
- 可撤销、可过期、只允许启动指定科目的 Launch Token，支持浏览器、NFC、快捷指令和 IoT POST。
- CSV、JSON、Markdown 完整导出；不嵌入任何 AI API。

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

前端独立开发：

```bash
cd frontend
npm run dev
npm run typecheck
npm run build
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

生产部署必须先备份，再停止 Web/MCP、执行迁移和前端构建，最后重启。完整步骤见 [deployment](docs/deployment.md) 和 [backup/restore](docs/backup-and-restore.md)。

## 常用路由

- `/`：认证后的 Vue 应用
- `/accounts/login/`：密码或 Passkey 登录
- `/accounts/2fa/`：Passkey 管理
- `/start/<subject>`：登录用户快捷启动
- `/launch/<token>`：受限启动令牌
- `/api/launch/<token>/start`：IoT 启动
- `/api/export/{csv,json,markdown}/`：完整导出
- `/admin/`：管理员恢复入口

第一次使用建议先看 [使用说明](docs/usage.zh-CN.md)。API、认证、模型和部署配置分别见 [API](docs/api.md)、[认证](docs/auth.md)、[数据模型](docs/data-model.md)、[架构](docs/architecture.md)。
