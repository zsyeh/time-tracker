# 数学二专注训练 · 2026-11-21

## 已确定的产品范围

用户最后确认：固定题单训练，**无需交卷，随时看答案**，可跳入原题标准练习。题干、答案与 PDF 全用原始贴图，不展示 OCR。旧组卷入口替换，旧试卷数据允许删除，但先留可恢复备份。整卷分享是按固定题序聚合现有单题域名分享链接，不公开私人备注或计时。没有整站反作弊、自动评分、难度自适应或新的搜索工程。

## 实现

- 沿用 `/papers`、`/papers/new`、`/papers/:uuid`；`/paper` 兼容重定向。删除无人引用的旧 `PaperView.vue`；侧栏入口改为“专注训练”。
- 数据迁移 `0042_focus_training_blueprints` 仅新增版本化配额、停用旧模板，无 Schema 变更、无题库或学习状态变更。3h：7高数选+3线代选+5高数填+1线代填+5高数大+1线代大；4h：11+4+7+2+7+2，180/240分钟。4h 是比例取整的强化训练方案。
- 同一 `POST /api/drill/papers/` 供 Agent / Web 使用。支持 `blueprint`、`seed?`、`include_mastered`、`exclude_review`、`cooldown_days`、`document_ids?`、`topic_ids?`。Web 提供模式、已掌握/待复习排除、近期排除天数；Agent 可进一步传已有目录/知识点 ID。筛选不足返回400及 section/required/available，不改用其他条件，不写半套试卷。
- 新题单严格要求题干和答案图片都有，保留原质量隔离规则；按目录标题识别高数/线代，不拿 OCR 题干猜学科。不假装题库已有完整难度数据。知识点分散、近期练习偏好沿用原服务；知识点上限是软偏好，显式状态和时间排除是硬条件。
- 固定题目和顺序及版本快照保留；单题页可前后/题号跳转、展开答案、全屏翻题和切答案、标记“不会做：”并保存原因。只保存题单私有备注，不因此创建 Attempt 或更改掌握状态。
- 倒计时从服务端 started_at 计算，后台/刷新继续；到时不锁题、不交卷。当前位置保存在 URL 的 position，刷新恢复。标准练习通过既有 paper ListContext 和**真实 ExamPaperItem 主键**保持题单上下题顺序；返回浏览器恢复原题号。
- 分享创建时复用/建立 canonical 单题分享；聚合页按卷序提供单题域名链接和原题练习入口，图片仍使用现有分享权限。答案折叠，不展示新题单 OCR。域名沿用 `drill.ehzsy.site` 和既有 98/47 代理，无 Nginx 改动。
- PDF 沿用 PyMuPDF，中文封面、A4、原图不做 OCR；小题连续排版，大题留空。超长图分跨页显示同一原图完整连续区域，不把整张长图缩成难辨认的小字。保留原图。没有新增依赖。

Agent 示例（只做实际题单请求，不用另写数据库抽题脚本）：

```json
{"blueprint":"math2-focus-standard-v2","include_mastered":false,"exclude_review":true,"cooldown_days":3}
```

## 验证

- 原组卷后端34项通过，18.914秒。
- 新训练+内容分享10项通过，3.911秒；最终 PDF 修改后新训练4项重跑通过，0.582秒。
- 共用全屏阅读器与预览导航17项通过，1.55秒。
- Drill TypeScript 与生产构建通过，Vite约7.6秒（不把Vite时间当包含类型检查的总时间）。
- 本地真实题图 Chromium：1180×820 dark、390×844 light；答案显示/全屏翻题/答案切换/备注刷新/标准练习再返回/无横向溢出/无 pageerror 均通过，见 `browser.json` 和截图。不是实体 iPad Safari/PWA 实机证据。
- 生产只读候选检查（不施加个人排除）：完整图片对的选择1212（线代179）、填空644（线代161）、解答853（线代260）。不把这些数当作每位用户过滤后的保证。

### 如实记录的返工

首轮分享测试环境未配置真实 Drill/EI 测试域名，且新增夹具误用了项目没有的 Pillow；改成已有 PyMuPDF 生成测试图，并仅重跑相关内容分享测试。无关 learning-share 测试误选且在该域名环境失败，不宣称通过。后续未修改产品鉴权来配合测试。

本地开发服务器未自动重载，第一次浏览器拿到旧 API，缺少新增 item.id；重启本地容器后解决。截图又发现本地题库有图片元数据而部分二进制为空，补入第8/9题的5张生产原图副本到**本地**，并增加 complete/naturalWidth 检查后通过；未改生产题图。验证分步跑、避免用空图和仅 DOM 出现冒充图像成功。

## 发布与回滚

发布结果、时间、镜像与清理结果在健康检查后追加。旧镜像 `time-tracker-ha:20261118-inactive-image-0305903`；并行备份 `/var/snap/docker/common/time-tracker-ha/backups/round2-focus-training-20261121`，backup-end 03:41:30+08，verify-exit=0。范围为用户/学习/旧试卷、schema、配置和旧镜像，不重复导出不变题库。

仅旧试卷主键7、105是本次授权清理目标。清理前另存 Django JSON（试卷、题单条目及对应分享），不删除 Question/QuestionRevision/QuestionAsset/Attempt。应用回滚不恢复整库，不覆盖上线后的学习记录。私有备份/身份/Cookie/Token均不入 Git。
