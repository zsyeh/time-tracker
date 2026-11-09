# 手动编辑题型（2026-11-10）

做题页的题型小字现在可以点击。入口无边框，保持 11px 题型文字和 6px 色点；展开后直接列出紧凑题型选项，点击目标题型立即保存并关闭，总计两次点击，无额外保存按钮。支持中英文。

## 数据与权限

- 新增认证接口 `GET/PATCH /api/drill/questions/<uuid>/exam-type/`，按访问域名限定 workspace；Session 认证保留 CSRF 校验。
- Drill 手动菜单仅 choice/fill/large（选择、填空、大题），没有简答选项。原有 unknown 数据继续如实显示，可手动修正为上述三类。EI 菜单保留 judgment/short_answer/unknown 等选项。后台仍保留 unknown 数据兼容性。
- 题型属于 workspace 内共享题库元数据。原 `Question.question_type` 不变，更新独立最终分类记录，筛选和统计继续优先读取它。
- 每次实际修改在 `QuestionExamTypeEdit` 保存修改人、时间及修改前后完整分类元数据，包括原模型、版本、哈希和审计原因。
- 已知类型经人工修改后标记 human/manual-v1，并清除待审计标记；选择 unknown 仍保留 unknown 审计标记。之前的标记保留在修改历史。
- 更新带 `expected_updated_at`，版本冲突返回 409；重复保存相同类型不产生冗余记录。
- 每次修改产生独立 manual 批次，旧导入批次的回滚保护不会静默覆盖后续人工修改。
- 清除当前题目各查询条件的旧缓存，并使列表、热力图及其他标签页刷新。保留 Note 草稿与登录会话。

## 验证

- 后端相关测试 16 项通过：保存、历史与旧字段保留、未知类型、旧题型补建、无登录拒绝、跨 workspace 拒绝、CSRF、非法类型、冲突及幂等保存。
- 前端全套 85 项通过，包含编辑器保存与失败提示；TypeScript 与生产构建通过。
- 本地迁移演练：0033 → 0034 → 0033 → 0034。
- 生产 23 项正式域名 HTTP 检查通过，含 GET/HEAD、带真实 Session/CSRF 的幂等 PATCH、409 冲突及跨 workspace 404。
- 两个 workspace 的实际分类修改、审计记录、冲突检查在生产数据库事务中验证，并全部回滚，没有留下测试分类。
- 原有 8,635 条分类保持完整。发布前的同一测试会话在 Timer/Drill/EI 发布后仍有效，随后仅删除该测试会话。

## 部署与回滚

镜像：`time-tracker-ha:20261110-manual-examtype`；47 健康，OOMKilled=false，可用内存约 598 MB。
PostgreSQL 仍从 2026-11-04 运行，本次没有重启数据库，也没有修改 RainYun 代理。

迁移前备份目录：
`/var/snap/docker/common/time-tracker-ha/backups/manual-examtype-20261110/`

其中 classification-before.dump 包含全部最终分类及迁移记录，已通过完整 pg_restore 读取校验并复制到本机；另存 schema-before.sql、SHA256SUMS、原服务配置、迁移与完整性日志。之前完整数据库备份原件继续保留。

应用回滚：恢复该目录 `20-local-ports.conf.before` 至服务 drop-in 的 `20-local-ports.conf`，daemon-reload 后重启应用，返回 `20261110-final-examtypes-r2`。保留新增审计表可确保上线后人工修改记录不丢失。不要恢复旧分类备份覆盖后来人工修改或学习数据。若确需撤销数据库迁移，必须先另行导出新增审计记录；0034 本身只新增表。

本机验收日志位于 `/home/eh/learning-type-audit/deploy-20261110/` 的 manual-type-* 文件。

## 两次点击更新

镜像：`time-tracker-ha:20261110-examtype-two-click`。本次只修改前端，无数据库迁移。
编辑器及筛选组件 6 项测试及生产构建通过：两次点击保存、Drill 仅三个选项、Drill 不显示简答筛选/统计、EI 选项、失败时不更新显示、保存期间阻止重复提交。
应用回滚可恢复 `time-tracker-ha:20261110-manual-examtype`，保留审计数据与登录配置。

上线后 9 次正式域名 HTTP 检查通过；EI/Drill 的 JavaScript、CSS 字节哈希与本地最终构建一致。发布前同一登录会话在 Timer/Drill/EI 发布后保持有效。服务 healthy，OOMKilled=false；数据库保持原启动时间。
