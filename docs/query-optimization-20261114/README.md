# 后端查表与数据库访问路径优化 · 2026-11-14

## 交付与范围

47已上线 `time-tracker-ha:20261114-query-opt-811d82b`，2026-11-14T01:23:26+08:00 healthy。登录200、queue成功。[生产结果](production.json)。源码/运维提交 `a9dcbe5`、`5a583d4`、`811d82b`，分支 `feat/collection-preview`。

- PostgreSQL15：新增 `(user_id, question_id, created_at DESC, id DESC) INCLUDE(result)` 覆盖索引，支持现有大量“该用户该题最新一次作答”查询，保留时间相同按pk判定的语义。
- 删除 `drill_question_order_idx`，它与仍然有效的 `drill_question_document_order_unique(document_id,question_order)` 重复。不是根据“使用次数0”随意删除其它索引。原64KiB user/question索引本轮保留。
- 题目详情已取得完整UserState用于note/version，现在直接复用收藏、待复习和saved_note，省去同一SELECT中重复的三个关联子查询。无UserState时saved_note仍为null，账号隔离、计数/reset和Note fallback保持原样。
- 试过将作答COUNT改为关联聚合子查询，实测增加部分详情的Python/ORM开销，**811d82b已撤回该改写**，保留原Count语义与查询。没有以“数据库SQL看起来更简单”作为发布依据。
- 无前端变更、无依赖变更、无搜索算法/统计公式/题目内容修改；没有重建搜索投影，没有移动题图。

## 实际基线与证据

生产 `pg_stat_statements` 扩展存在但未通过shared_preload_libraries加载，因此不能读取累计查询统计；本轮没有为此重启数据库。使用只读管理进程、Django execute_wrapper和实际 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` 测量。以已有学习账号数据作为只读样本，不打印身份、请求参数、Note内容或响应正文，不增加公开API。

[基线](before.json)、[最终同口径复测](after.json)都是每接口1次warm-up+5次样本，包含view处理/SQL/JSON render，**不包含公网、TLS、浏览器或图片加载耗时**。P95在5个样本中等于最大值，不能当成长期流量P95。

基线EI翻题计划中有4,310/3,747次最新作答Limit→Sort→question_id索引扫描。新计划实际使用 `drill_attempt_latest_idx` 的有序访问路径，避免该最新作答子查询再排序；外围导航排序仍保留。严选详情中的963题最新状态查询也实际使用新索引。原始计划只保存节点、循环次数、索引名等摘要，未保存私人SQL参数。

| 应用内接口 | Before P50 ms | Final P50 ms | Final短样本P95 ms |
|---|---:|---:|---:|
| drill-detail | 68.9 | 90.4 | 126.8 |
| ei-detail | 74.9 | 82.1 | 114.3 |
| drill-selected-detail | 102.2 | 63.8 | 94.2 |
| drill-list | 32.9 | 30.5 | 46.6 |
| drill-search | 139.5 | 114.2 | 116.2 |
| drill-selected-heatmap | 129.7 | 164.2 | 201.4 |
| ei-heatmap | 286.1 | 233.5 | 330.8 |

这些跨时段数据受生产负载、GC和正在进行的学习操作影响；不能宣称全站都快了。普通详情短样本上升，Drill热图也有上升，EI热图下降；本轮没有重写热图，热图稳定提速仍未确认。搜索批次下降也不能全部归因为本次索引。

为分离查询改写与数据变化，另在**同一REPEATABLE READ READ ONLY快照、同一进程**内交替执行原实现与最终实现，每种8个warm样本；比较使用已有新索引，因此只测UserState复用的增益，不冒称整个迁移收益。5条路径规范化JSON全部一致：[交替对照](interleaved.json)。

| 路径 | 原状态查询P50 | 复用状态P50 | 结论 |
|---|---:|---:|---|
| Drill详情 | 72.275ms | 69.706ms | 本次小样本约3.6%改善 |
| EI详情 | 73.696ms | 71.457ms | 本次小样本约3.0%改善，P95仍有离群点 |
| 严选详情 | 94.345ms | 91.253ms | 本次小样本约3.3%改善 |
| 普通列表 | 46.621ms | 48.737ms | 查询语义未改，波动范围内不算收益 |
| 搜索 | 114.734ms | 115.507ms | 不算状态复用的提速收益 |

`initial-after.json`为已撤回的计数改写中间结果；`after-canonical-probe.json`是额外做JSON规范化的诊断探针，不用其时长与原始hash探针基线比较。实施期间真实作答数1390→1391，因此跨时段原始响应hash不能用于宣称数据损坏；没有覆盖或撤销新增学习记录。通过同快照JSON比较验证语义。

## 磁盘与资源

- 47约40GB盘，当前可用10,063,179,776字节，约9.37GiB，使用率仍75%。本次开始的磁盘样本可用10,064,728,064字节；整体约增加1.5MiB，包含两次很小的应用层、用户备份与日志，并非整盘释放空间任务。
- 原重复索引655,360字节，新索引98,304字节（96KiB），**索引净减少557,056字节/544KiB**；原630,784字节唯一索引保留。[实际有效性及大小](indexes.json)。
- 发布包约36KiB，仅Python源码/迁移/运维脚本，从明确旧镜像构建，不重复携带前端、依赖或图片。最终镜像构建2秒。
- 用户/学习数据、schema、配置、PWA与旧image已备份并验证归档可读，未重复导出未变的约2.7GB题图；开发/备份并行。本轮未删除既有回滚镜像或其它备份。
- 不执行VACUUM FULL、全库REINDEX、pg_stat_statements启用重启或大型索引重建。

## 迁移与兼容

`drill/migrations/0041_query_access_paths.py`是索引访问路径迁移：

1. 非原子migration；PostgreSQL创建/删除索引使用CONCURRENTLY，先增加有效新路径，再删除重复路径。
2. 删除重复索引前检查原唯一索引有效。中断遗留的同名无效新索引在重试时清理并重建。
3. 设置本连接lock_timeout=3s、statement_timeout=60s、maintenance_work_mem=32MB，最后恢复；不改全库参数。
4. SQLite等后端走schema_editor普通索引操作；数据库状态和Django模型通过SeparateDatabaseAndState同步。
5. 不改题库和学习表的行、字段类型、UUID或约束；反向迁移先恢复旧普通索引，再删新索引。旧应用兼容0041，应用回滚不必恢复数据库备份。

依据：[PostgreSQL15 CREATE INDEX](https://www.postgresql.org/docs/15/sql-createindex.html)、[Django并发索引操作](https://docs.djangoproject.com/en/4.2/ref/contrib/postgres/operations/#concurrent-index-operations)。并发建索引仍有短暂元数据锁和等待限制，不声称零锁。

## 测试和生产验收

- 本地PostgreSQL实际完成0041→0040→0041，无migration drift；`makemigrations --check --dry-run`通过。
- 最终43个针对性测试通过，执行11.637秒：[日志](tests.txt)。覆盖新状态复用的账号隔离、空note/null、favorite/review_later，reset计数与同时间pk顺序，原翻题/收藏/历史、Drill/EI、Hybrid搜索、全局预览和热图。
- 上一轮42用例含CLI校验13.04秒。首轮旧Navigation测试未显式隔离生产hybrid环境而503，已将该legacy测试fixture设为legacy；独立Hybrid搜索回归仍开启Hybrid并通过，不用关闭生产搜索绕过问题。
- 后端只改Python，无需重跑前端构建或全设备截图。原前端静态资源由既有镜像原样继承。
- 47实际迁移成功、无后续待执行迁移，new index有效，重复index不存在，唯一index有效；应用healthy、登录200、后台queue成功。
- 数据采样连接只读；未创建生产测试账号/Attempt。无全库恢复，真实用户新增学习数据保留。
- 生产没有演练实际故障回滚，以免打断学习；结构正反向在本地实测，宿主回滚脚本存在/可执行、sh -n通过、旧image存在。

## 回滚命令（47）

备份 `/var/snap/docker/common/time-tracker-ha/backups/round2-query-opt-20261114`。

仅回滚应用到19ef771、保留兼容索引与新学习记录：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/query-opt-811d82b/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-query-opt-20261114
```

同时回滚应用和0041索引结构：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/query-opt-811d82b/deploy/ha/query-access-paths-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-query-opt-20261114
```

组合脚本先恢复旧应用，再用保留的新镜像执行`migrate drill 0040`，不覆盖任何学习行。已核验这些是宿主release/deploy/ha实际文件，不能用镜像overlay里的路径冒充宿主入口；此前本轮相关release也补齐了对应宿主脚本。

## 文件清单

- `drill/models.py`：覆盖索引、移除精确重复的普通索引定义。
- `drill/migrations/0041_query_access_paths.py`：有界并发/反向操作及模型状态。
- `drill/views.py`：include_user_state默认兼容，详情复用已读取状态；最终保留原计数方式。
- `drill/test_navigation_queries.py`：计数/reset/账号隔离、详情状态复用回归；legacy fixture明确隔离。
- `scripts/benchmark_backend_queries.py`：可复用只读管理员诊断，不是公开接口；只输出统计/计划摘要/hash。
- `deploy/ha/query-access-paths-rollback.sh`：组合回退入口。
- 本报告、Master追加、最近开发记录与`.codex/DEVELOPMENT_WORKFLOW.md`：证据/时间/交接。

## 时间与流程改进

首次只读诊断01:02:02，最终健康01:23:26，约21分24秒；报告整理另计。用户备份01:04:11–01:04:20，9秒；最终镜像01:21:04–01:21:06，2秒；最终迁移目标检查/幂等执行7秒（0041已在首批应用），最终应用切换17秒。初次发布计时保留于生产备份`initial-release/`，不是用最终时间覆盖所有历史。

额外耗时主要来自：计数改写先上线后才量出ORM开销，随后撤回该方案；早期诊断事务未与search自管理RR事务匹配、比较脚本变量复用、空迁移计划缩进处理造成可避免的返工。错误探针未算通过，迁移计划检查失败时旧应用保持运行。

后续规则：先用相同快照、交替顺序测候选实现及端到端CPU/SQL，再发布；接口自己管理RR事务时不能另外包默认READ COMMITTED事务；语义hash规范化与性能探针分离，前后探针保持一致；只保留证实有用的索引/改写。不要为小改动再做全站研究或全量测试。仍需关注真实流量下详情/热图尾延迟，未在本轮承诺全站稳定提速。
