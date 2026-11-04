# Drill / EI AI 学习数据分享与 RainYun 题图缓存

## 生产边界与本次核对

- 2026-11-04 GitHub `master` 为 `2c3f53b`，47 正在运行的 r25 镜像标记 Git revision `1bea62b`；两者的代码相同，差异只有 README 文档。
- 47 应用连接的 PostgreSQL 返回 `pg_is_in_recovery() = false`、`transaction_read_only = off`；RainYun 域名 Nginx 回源 47。旧 systemd 单元名不能用于判断业务主备。
- 47 上 `drill_questionasset` 有 23,707 条，总 `image_data` 字节数 2,690,554,378；当前均为 `image/png`。47 根分区剩余约 8.5 GB，RainYun 剩余约 14 GB。RainYun 旧题库资源没有进入本次缓存的信任链。

## 分享接口

登录用户在对应域名的 Insight/热力图使用「分享给 AI」，或调用 `POST /api/drill/learning-shares/`。请求示例：

```json
{"kind":"heatmap","scope":{"collection":"core_selected","course":"circuit"},"include_notes":true}
```

`kind` 为 `heatmap`、`daily`、`weekly`、`global`。日报 `scope` 可以是 `{"period":"today"}`、`{"period":"yesterday"}` 或 `{"date":"2026-11-04"}`；周报可以是 `recent7`、`previous7`，或 `{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}`，指定范围最多 91 个自然日。日期按 Asia/Shanghai 计算。

创建响应只出现一次明文链接。数据库保存 token 的 SHA-256 摘要、owner、workspace、范围、Note 开关、创建/到期/撤销时间。到期严格等于创建后 7 天。`GET /api/drill/learning-shares/` 仅列出本人当前有效记录；`DELETE /api/drill/learning-shares/<id>/` 立即撤销。浏览器本地保存由该浏览器创建的链接以便在管理列表复制；服务器无法恢复明文 token，跨设备遗失后应撤销并重建。原有单题/试卷分享模型和持久化策略保持独立。

公开入口固定为 `https://drill.ehzsy.site/share/learning/<token>/index.md` 或 EI 域名。仅 GET/HEAD，不需要 Cookie、登录或 JS；令牌绑定对应域名和用户选定的范围。`index.md`、`manifest.json` 说明读取顺序与资源。`heatmap.*`、`topology.*`、`subjects/*.md`、`chapters/*.md`、`questions/index.json?page=N`、`questions/<uuid>.*` 与 `assets/<id>/<sha256>` 可以逐层遍历。`export.md` 提供可手工复制的完整文字降级版，图片仍以授权链接提供。题目页含动态状态、当前 Note、作答摘要、复习计划、题图与答案链接。每页 100 题且提供 `next_url`；章节 Markdown 也分页。越权 UUID、资产 ID 或过期 SHA 均拒绝。

热力图/当前状态及 Note 每次从 47 重新读取。日报、周报和全局历史采用固定日期窗口，但每次请求从现有记录重新计算，明确 `calculated_at`、时区、未结束当天及重新计算口径。撤销/修正/补录会改变历史窗口结果。缺失的独立正确或计时样本返回 `null`；当前数据模型没有不可变的复习计划状态变迁历史，因此历史计划完成数明确为 `null/unknown`，不伪造。

公开响应 `no-store`、`noindex`、`no-referrer`、`nosniff`。Note 只作为学习数据呈现，不参与后端指令或命令执行。Nginx 的分享路径关闭包含 token 的访问日志；Django/Gunicorn 相关应用日志加过滤器，把 URL 中的 token 替换为 `<redacted>`；缓存指标日志仅记录时间、状态、hit/miss 和字节数。

## RainYun 资产缓存

47 的 `export_learning_assets --manifest` 从 PostgreSQL 输出只读清单，包含 workspace、asset ID、SHA-256、大小和 MIME。`export_learning_assets --ids ...` 以 tar 输出选中资产，先逐字节验证数据库 SHA。RainYun `scripts/sync-learning-assets.py --prune` 经 SSH 从 47 增量拉取；同名文件只有 SHA 校验通过才视为命中，缺失或损坏的文件重新传输。写入临时文件、再次校验并原子替换，保留 2 GiB 空闲磁盘下限。`--prune` 删除 manifest 中不存在的旧版本。systemd timer 草案每日自动执行，也可手工全量预热。

Nginx 的 `/__learning_asset_cache/<workspace>/<id>/<sha>` 为 `internal`。每个公开图片请求先到 47 Django 验证 token、期限、workspace、题目和资产归属。授权成功后 47 返回 X-Accel-Redirect；47 Nginx 保留此头，RainYun 再从只读磁盘交付字节。冷缓存通过带固定内部标记的请求回源 47，仍重新鉴权；47 不可用时无法得到授权重定向，缓存文件不可外部直连。RainYun 不写任何题库或用户数据库。HTTPS 上游证书通过系统 CA 校验，并使用各自域名作为 SNI。普通动态 API、Note、热力图、分享页没有 proxy_cache。

`/var/log/nginx/learning-asset-metrics.log` 可按最后两列观察 hit/miss 和回源字节；`/var/cache/time-tracker/learning-asset-sync.json` 记录清单字节、增量下载和剩余磁盘。分享路径按 token 限流 240 次/分钟，突发余量 480 次，不设普通遍历的每日硬上限。

## 发布与验证边界

本次仅修改隔离工作区。正式发布前：

1. 再次确认 47 的唯一写入角色和现行镜像 revision，备份整个业务 PostgreSQL，运行 `pg_restore --list`、SHA-256 校验，并准备上一镜像和 Nginx 配置回滚副本。
2. 将 RainYun 草案中的**新增**学习分享 location、限流和内部缓存位置合并进当前实际 Nginx 配置，保留现有其他站点、MCP、证书续签和登录路由。不能直接覆盖整份线上配置。47 同样只合并分享 location。两端先 `nginx -t`，经明确批准后才 reload。必须先让两层代理具备转交 `X-Accel-Redirect` 的能力，再切换新版 Django，否则边缘题图请求可能暂时返回空内容。
3. 在隔离数据库执行 migration `0031_learningshare`，再对生产运行 `migrate --plan`；经用户明确批准后才在 47 执行生产迁移、部署镜像或重启服务。
4. 先在 RainYun 跑 `sync-learning-assets.py --prune` 全量预热并检查校验统计，再启用 timer。预热失败不影响反代；缓存未命中仍回源。
5. 用真实公开域名生成短期测试链接，由无 Cookie 的外部 HTTP 客户端逐页走完 Drill/EI 目录、题目、Note、题图，检验冷/热命中、撤销后资产 410、47 不可用时无旁路以及 iPad Safari 复制。Cloudflare 规则仅在出现具体误拦截时针对 `/share/learning/` 调整。

单题/试卷分享不受新模型及到期策略影响。生产迁移、服务重启、代理改动与 Cloudflare 规则尚未执行，真实有效 token 的公网验收因此尚未完成。

## 六阶段交付记录（2026-11-04 发布前）

| 阶段 | 根因与实施 | 修改文件 | 已验证 | 剩余风险 |
| --- | --- | --- | --- | --- |
| 1. 审计 | 旧 HA 服务名与当前角色不符；核对镜像 Git revision、实际 PostgreSQL 写入状态、两端 Nginx、旧分享/资产/严选筛选。 | 本文档 | 47 `pg_is_in_recovery=false`、资产 23,707 条；域名无效分享返回 Cloudflare DYNAMIC 404。 | 有效 token 的公网行为需发布后验证。 |
| 2. 七天模型与接口 | 旧 `DrillContentShare` 是持久单题/试卷链接，不能承载临时个人数据。增加独立哈希 token 模型、owner 管理、7 天期限、410、GET/HEAD 公开路由与应用日志脱敏。 | `drill/models.py`、`drill/migrations/0031_learningshare.py`、`drill/urls.py`、`time_server/urls.py`、`drill/learning_shares.py`、`drill/apps.py`、`drill/logging_filters.py` | 新增权限、日志脱敏测试及迁移一致性检查。 | 生产迁移未执行。 |
| 3. 学习数据 | 现有热力图/严选/Note 分散于既有模型；从当前题库与严选筛选器动态组装目录、分页逐题、图片、日报、周报和全局报告。 | `drill/learning_shares.py`、`drill/test_learning_shares.py` | Drill 253 项测试通过；新增北京时间、分页、Note、EI 核心严选用例通过。 | 不可变的历史复习计划完成事件不存在，报告明确 unknown。全量实时报告的大规模性能仍需生产规模压测。 |
| 4. 前端 | 原 Insight/热力图缺少 AI 分享入口。增加统一简短表单、workspace 切换、复制链接/提示词、有效分享列表及撤销。 | `frontend/drill/src/components/LearningSharePanel.vue`、`frontend/drill/src/views/HeatmapView.vue`、`frontend/drill/src/views/InsightView.vue` | TypeScript 与 Drill Vite 构建、74 项前端测试通过。 | iPad Safari 需实体设备验收。 |
| 5. RainYun 缓存 | 原图每次经 47 读取 PostgreSQL；增加只读 SHA manifest/tar 导出、校验增量预热、内部鉴权后文件交付与回源。 | `drill/management/commands/export_learning_assets.py`、`scripts/sync-learning-assets.py`、两份 Nginx 草案、systemd service/timer、`scripts/test_sync_learning_assets.py` | 两端独立草案 `nginx -t` 通过；同步校验与跨 workspace tar 拒绝测试通过；RainYun 临时端口假数据演练冷回源、热命中、内部路径拒绝、无效 token、上游断开均通过。 | 未部署/预热，真实用户令牌与生产流量需上线后实测。 |
| 6. 外部验收 | 正式域名是 Cloudflare → RainYun → 47；本地测试无法替代有效公开链接。 | 本文档 | 无效链接经真实外部 `curl` 返回 404，且 `cf-cache-status: DYNAMIC`。 | 需要生产迁移与代理发布的单独授权后，才能执行有效 token 的完整公网验收。 |

完整 Django 套件在隔离镜像中跑了 402 项，其中 400 项通过；另外两项旧测试因该最小镜像没有 `git` 与 `journalctl` 可执行文件而报环境错误。Drill 子套件 253/253、前端 74/74 和缓存脚本 2/2 均通过。

## 2026-11-05 生产部署记录

- 47 仍是唯一业务写入主站。发布前再核验 PostgreSQL `pg_is_in_recovery=false`、`transaction_read_only=off`，原 Web 镜像为 `time-tracker-ha:20261103-r25`。新完整备份 `/var/backups/time-tracker/postgresql/time-tracker-20261105-011957.dump`（2,857,326,536 字节，权限 600）通过 SHA-256 和 `pg_restore --list`；旧镜像、systemd drop-in 与两端 Nginx 配置保留回滚副本。
- 47 新镜像 `time-tracker-ha:20261105-ai-share` 的应用代码来自 `7302b9f`，前端 Timer/Drill 已在本地重新构建并进入镜像。迁移预检只显示 `drill.0031_learningshare`，生产执行成功。`time-tracker-ha-web` 新容器健康，`manage.py check` 无问题，Drill/EI 登录跳转和 Drill 静态 JS 的公网请求正常。47 Docker 守护进程在镜像加载时曾卡住，重启后 Web 与 PostgreSQL 均自动恢复，随后完成迁移和镜像切换。
- 实际 Nginx 仅合并新分享与题图位置。RainYun 到 47 的公网 TLS 在带域名 SNI 时发生连接重置，所以新分享专用 `time-tracker-47-share-tunnel.service` 将本地 `127.0.0.1:18443` 经 SSH 转发至 47 的 HTTPS；边缘仍验证 Drill/EI 域名证书。旧登录与其他代理位置未改动。新位置关闭含 token 的访问/错误日志；早期调试中边缘错误日志出现的测试 token 已脱敏。
- 真实公网无 Cookie 测试：Drill/EI 的 HTML、Markdown、JSON、当前 Note、题图均 200；Drill 一个 910 题范围完整分页；Drill 全局目录显示 5,847 题、全局总结 515 道历史去重已做题，响应约 4 秒；跨 workspace UUID 和内部缓存路径 404。冷缓存 `miss`、预热后两个 workspace 的图片 `hit` 均经 SHA-256 验证。撤销临时分享后入口、逐题及已缓存图片都立即 410，临时明文 token 文件已删除。
- RainYun 的旧 `time-tracker-github-sync.service` 因本机 PostgreSQL 已停用而每分钟失败。新脚本由 RainYun 经 SSH 只读取得 47 的待同步学习记录，在 RainYun 提交 GitHub，成功后请求 47 更新同步 outbox；没有在 RainYun 恢复业务数据库。真实提交及回写已通过，积压记录清零。部署文件为 `scripts/sync-github-notes-from-47.py` 与 `deploy/ha/time-tracker-github-sync-from-47.service`；原服务单元有回滚副本。
- RainYun 题图同步脚本以最多 500 个资产为一批全量预热，`time-tracker-learning-asset-sync.service` 正在运行，daily timer 已启用；完成后以 `/var/cache/time-tracker/learning-asset-sync.json`、文件数、总字节与 SHA 校验作最终核对。跨境 SSH tar 流曾中断一次，已新增同批剩余资产重试及 systemd 失败重启，从现有哈希校验通过的缓存续传。同步失败只影响命中率，冷缓存继续经 47 授权回源。
- Cloudflare 对默认 `Python-urllib/3.13` User-Agent 返回 1010；`ChatGPT-User/1.0`、curl、浏览器 UA 已验证 200。RainYun 现有 Cloudflare 令牌只有 DNS 权限，Rulesets API 返回 403。待具备 WAF 编辑权限后，按官方文档只在 Drill/EI 的 GET/HEAD `/share/learning/` 路径跳过 Browser Integrity Check，不改全站保护。iPad Safari 的实体复制操作仍需设备实测。

建议的 Cloudflare 自定义规则表达式：

```text
(http.host in {"drill.ehzsy.site" "ei.ehzsy.site"} and starts_with(http.request.uri.path, "/share/learning/") and http.request.method in {"GET" "HEAD"})
```

动作为 `Skip`，只选 `Browser Integrity Check`（API `products: ["bic"]`），其他安全产品继续生效。依据：[Cloudflare Browser Integrity Check](https://developers.cloudflare.com/waf/tools/browser-integrity-check/)、[Skip options](https://developers.cloudflare.com/waf/custom-rules/skip/options/)。
