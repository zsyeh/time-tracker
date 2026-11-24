# 2026-11-24 · 桌面做题快捷键

## 已发布

- 应用提交：`0c3044d`；生产镜像 `time-tracker-ha:20261124-study-shortcuts-0c3044d`。
- 2026-11-24 21:00:58 +08 完成切换并 healthy，HTTPS `/accounts/login/` 200。
- 未修改主题、布局、题库内容、考试分值或数据库 Schema；无需迁移。

## 按键与模式

|按键|Practice|考试做题 / 逐题批阅|
|---|---|---|
|← / →|复用原上一题 / 当前既定模式下一题|本卷顺序上一题 / 下一题，边界不越界|
|F|切换当前题收藏|同一题库收藏状态，仍按账号隔离|
|N|复用原待复习提交、计时提醒、自动翻题偏好|写入该题 Practice 待复习状态，不改本卷分数/答案/备注|
|M|复用原掌握提交与既有偏好|写入该题 Practice 掌握状态，不改本卷分数/答案/备注|
|U|复用原撤销最近状态操作|撤销当前页面本次 M/N 标记栈，允许跨本卷切题撤销；离开页面后不保存此临时栈|
|Q|打开保留原下一题顺序的滚动预览|打开当前整卷预览|
|A|原答案或整册答案全屏阅读|仅 `completed` 解锁答案全屏；未结束时提示并保持关闭|
|P / X|打开题目全屏 / 关闭全屏阅读器|打开当前内容全屏 / 关闭全屏阅读器|

用户明确补充：考试 M/N **修改 Practice 字段，但不改变分数**。没有另建本卷私有标记模型。考试中的标记复用标准 Attempt API，为明确的手动掌握/待复习记录；显式不记录逐题用时，避免把考试总时长重复累计。考试不会因 M/N 自动翻题。收藏不计入 U 的掌握撤销栈。

### 答案保护

- 考试未结束时按钮禁用；按 A 提示“考试未结束”。复用已有 `complete` API，确认“结束考试并解锁答案”后读取答案；结束不自动计算分数。
- 私有考试 `review`/更换题目的响应也过滤答案图和 Markdown，不只是前端隐藏。
- 结束后仍可查看原答案、标准 Practice、已有自评/批阅；全屏工具栏不新增答案按钮。
- 这是考试视图内的答案隔离。现有公开分享与独立题库 Practice 的既有权限/内容语义不变，并非监考防作弊系统。

### 防误触与并发

- 输入框、Note、分数、Select、contenteditable、菜单、输入法组合期间不触发；保留 Ctrl/Alt/Meta 浏览器快捷键，长按不重复提交。
- 普通确认/设置弹窗打开时阻止；全屏阅读器内继续有效；路由卸载清理监听。
- 考试 M/N 失败重试复用 submission UUID，避免丢失响应后重复记录；未确认前不允许以另一操作覆盖。
- U 带 `expected_attempt_id`，后端发现其他页面已有更新返回 409，不删除新记录；旧 Practice 无参数 DELETE 保持兼容。

## 文件与验收映射

|需求 ID|实现文件|验收|
|---|---|---|
|KEY-01：10 个按键、输入保护和清理|`frontend/drill/src/lib/studyShortcuts.ts`、`QuestionView.vue`|`studyShortcuts.test.ts` 4 项，生产 Practice P/A/X|
|KEY-02：考试固定顺序、全屏及整卷预览|`PaperExamView.vue`、`PaperGradingReport.vue`|生产左右切题、Q、P/A/X；批阅页不破坏原 URL/锚点逻辑|
|KEY-03：考试 M/N 同步 Practice，不改分数|`lib/paperKeyboardMarks.ts`、既有 Attempt API|2 项 helper 测试；生产 N/U/M/U 后分数与备注保留，用时为空|
|KEY-04：未结束禁止答案|`drill/views.py`、`PaperExamView.vue`|私有 payload 测试、组件键盘测试、线上结束前后 A 与响应图像检查|
|KEY-05：撤销防覆盖|`DrillQuestionAttemptView.delete`|后端 stale expected ID 409、新记录仍在；正确 ID 可撤销|

## 测试和证据

- 前端 4 个文件 **14 用例通过**：快捷键、标记幂等/撤销、考试更换回归、批阅编辑回归。类型检查发现纸卷 `mastery_state` 与 Practice `state` 字段差异，已显式映射；修复后 helper 2 项重跑通过。
- `vue-tsc` 与最终 Drill 生产构建通过（Vite 6.84 秒）；仅既有大 chunk 提示。没有以构建替代浏览器验证。
- 后端 `drill.test_exam_answer_lock drill.test_paper_replace` **11 用例通过，2.236 秒**。
- 生产 Chromium 1440×1000：考试箭头、F、N/U/M/U、Note 输入保护、未结束 A 拦截、结束解锁、Q、批阅箭头与 P/A/X、Practice P/A/X 均通过，无 pageerror。见 [browser-check.json](browser-check.json)、[答案阅读截图](exam-completed-answer-desktop.png)。
- 使用临时隔离账号、两份 QA 试卷；测试后已删除账号/试卷/会话，M/N 创建的测试 Attempt 均已撤销。原试卷148仍30题、76.5分，原用户未被用于可写测试。
- 第一次线上探针等待 Q 页面所有资源 `load` 超时，但 URL 已正确跳转；改为检查实际 URL。Practice 探针需等待题目内容而非页面壳；修正等待条件后通过，无应用补发。
- 本轮面向桌面键盘；实体 iPad Safari/PWA 键盘未测，不声称覆盖。

## 时间、备份与回滚

- 可核对时间起点：并行用户备份 20:51:08；结束20:51:21，13秒；9分50秒后于21:00:58上线。该起点不是未经记录的精确开发开始时间。
- 校验：前端14项1.89秒，后端11项2.236秒；类型修正后局部2项0.702秒及最终构建6.84秒。首轮类型检查失败如上，不能记成全部一次通过。没有全量题库/统计重测。
- 生产切换21:00:34–21:00:58，24秒；线上验证与临时数据清理至21:03左右。备份、开发并行，无数据库迁移。
- 用户数据约724KiB（备份含既有账号、学习、计时、试卷、分享等表），Schema/恢复目录校验通过；未重复备份题图大对象。
- 备份：`/var/snap/docker/common/time-tracker-ha/backups/study-shortcuts-20261124/`，`verify-exit.txt=0`。
- 回滚：在47执行 `sh /var/snap/docker/common/time-tracker-ha/releases/study-shortcuts-0c3044d/rollback.sh`，恢复 `time-tracker-ha:20261124-exam-grading-editor-691cdc4`。脚本可执行、`sh -n`通过；只恢复应用/config，不用旧数据库覆盖发布后学习记录。
- 保留旧镜像及旧哈希资源；未重启数据库、未变更无关队列。47剩余约11GiB。
