# 892 首次模拟批阅导入与阅读（2026-11-24）

## 实现边界

- 复用 ExamPaper.generation_options.grading、ExamPaperItem.self_score/result/user_answer/self_note、QuestionUserState.note/review_later。无数据库迁移、不修改原题/答案/图片、不新增前端AI入口。
- `grading` 保存本次考试快照：日期、实际总时长、原AI估分、逐题比例/四态/证据、后续改判、五科学习薄弱点五段文本。五科文本留在各次考试中，便于纵向比较与Agent后续组卷；不是外观偏好，不自动更改TopicMastery的人工等级。
- 普通正确题不自动写全局掌握；非满分项复用待复习标记并追加带稳定批次标识的短Note，保留已有文本与收藏/掌握。
- 考试条目即本次作答记录，不额外复制30条QuestionAttempt、计时Session或平均分配耗时。只有用户明确确认“已掌握”的题才用稳定submission_key追加一次掌握动作。
- 管理命令先验真分享所有者和30个UUID，再校验分值；默认dry-run，apply必须有私有目标行备份。相同输入幂等，不同输入覆盖已有批阅必须先审差异，默认拒绝。
- 鉴权review API返回批阅；公开分享仍只含固定题/答案，没有私人作答、分数、Note、薄弱点。原未批阅详情不带grading。

## 已知评分依据

用户提交的是GPT Web对手写答卷的总结，本轮没有原手写图片，不能声称独立重新批阅步骤分。核对的是固定原题、答案、映射与明显参考冲突。主观题比例依照用户记录，始终标明非官方估分。

第5题用户改判：原答案B，但A的S5图示没有出边，也不能进入有效循环。记录初判与多解问题，接受A满分，按用户明确要求已掌握，从个人薄弱点/本次待复习移除。不修改共享题库答案。

实际分值选择/填空各3分、简答6分、计算12分。第5题改判后：选择8/10，等权89.5，按真实分值换算 **76.5/150**。保留最初84.5、约75.8、76–85原始估分，附换算说明，不把不同口径静默合并。

第25题需按实际矩形/三角频谱与角频率单位分析，不将标准升余弦公式机械当作原图；第9/27题考纲边界仍待核实，不标超纲。

## 组件和页面

- MarkdownSection：复用原Timer markdown-it + DOMPurify + KaTeX渲染器，经现有MarkdownAnswer加载；折叠阅读总体、分题、五科和复习策略。
- PaperGradingReport：总分/五科得分条形图（role=meter+数字替代）、30个题号分数格、逐题批阅、原题/答案贴图、真实`/practice/:uuid`跳转、query.question保留当前题号。
- PapersView：有批阅或已完成卷显示分数/批阅入口，不再显示开始作答；未开始/进行中保留正常入口。
- 不增加ECharts依赖，不改全屏做题流程，不生成AI Dashboard式彩色描边卡片。

## 验证与回滚

后端定向6用例：原分值换算、映射错拒绝、账号隔离、幂等、保存旧Note/掌握/收藏、只有显式确认才写一次掌握。前端2用例：成绩与可访问图表、逐题路由与真实Practice路径。类型及Drill生产构建通过。

第一次前端测试使用了项目没有的test-utils，改用现有createApp/jsdom测试设施，没有新增依赖；首次构建通过，最终控件修订后的构建曾被该测试导入阻断，修复后最终构建通过。必要的失败与重跑记录，不将其冒充一次全部通过。

用户/schema/config及旧镜像备份：`/var/snap/docker/common/time-tracker-ha/backups/exam-grading-20261124`，verify-exit=0。不重复备份未改题库图片。

`rollback_grading.py` 默认校验目标行与导入后快照完全一致；加 --apply 才恢复导入前考试/Note，删除本批新建状态/显式掌握行。发生新编辑会拒绝，避免覆盖后续用户操作。私有输入及before/after快照不得进Git。

组卷/下次批阅提示词：[Agent工作流](AGENT_EXAM_WORKFLOW.md)。后续追加真实部署、导入计数和截图结果。

## 最终生产结果

- 应用：`5dc4bca`，镜像 `time-tracker-ha:20261124-exam-grading-5dc4bca` healthy。切换 **15:37:46–15:38:16（30秒）**；无数据库迁移。
- 账号的原试卷/本次考试记录主键 **148**，UUID `f2ab8798-0526-4a18-89af-802af6e664ae`，直接复用，没有创建第二场考试。
- [批阅记录（登录后）](https://47.95.10.128/ei/papers/f2ab8798-0526-4a18-89af-802af6e664ae/review?question=8)
- 原30题条目均准确对应固定题目，30条更新；考试记录更新1条。待复习Note状态更新12条、新增6条；新建1条用户明确授权的Q5掌握动作（独立submission_key），不是把所有满分题自动判掌握。
- 正确12、错误3、部分正确8、未完成7；18条非满分题设review_later，原有Note追加不覆盖（例如Q29原Note保留）。原手动掌握/收藏、TopicMastery均未批量重算或覆盖。
- 70分钟仅存在本场grading总时长，30个逐题时间仍全为null；导入不创建学习Session、不把70分钟分给每题、不再制造30条全局QuestionAttempt。**因此普通历史次数仅增加用户明确要求的第5题掌握动作1次**；本场所有逐题作答保留于ExamPaperItem与批阅快照，通过考试批阅入口阅读，不冒充30次独立Practice提交。
- 初始AI结果、第5题改判记录、五科学习漏洞与优先级、考纲边界、复习安排均已存数据库；原手写答题纸未提供，无法入库存档或独立核步骤分，已明示证据边界。
- 同输入再次apply返回unchanged；没有第二份备份目录、第二组Note或重复掌握记录。浏览器检查后回滚脚本再只读校验，50行仍与导入后快照一致。

|学科|估分 / 满分|
|---|---:|
|电路原理|13.5 / 30|
|模拟电子技术|20.4 / 30|
|数字电子技术|15.9 / 30|
|信号与系统|14.1 / 30|
|通信原理|12.6 / 30|
|合计|76.5 / 150|

## 实际浏览器与测试结果

6个相关后端用例通过（0.253秒），2个前端用例通过（测试44ms、进程1.33秒），类型检查/最终Vite构建通过（Vite6.98秒）。最终受影响自动化验证在一分钟内；真实数据核对/导入/线上检查另计，不声称完整审题只需一分钟。

生产登录态Chromium在390×844浅色、1180×820深色分别核验：76.5总分、5个学科meter、30个题号格、Markdown渲染、选择第8题、真实Practice跳转、浏览器返回保留question=8、试卷列表已变成绩/批阅入口、无横向溢出及JS错误。使用仅10分钟有效的隔离验证Session，检查后删除，不动已有登录Session。Safari/PWA真机本轮未测。

证据：`browser-check.json`、`import-evidence.json`、两尺寸成绩和第8题截图。私有答案原始输入与前后行快照留服务器备份及本机私有目录，不进Git。

## 精确回滚

应用回滚（保留新批阅数据）：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/exam-grading-5dc4bca/rollback.sh
```

恢复537d80f应用/配置，不重启数据库、不drop字段、不改独立队列镜像。目标数据备份位于：
`/var/snap/docker/common/time-tracker-ha/backups/exam-grading-20261124/import/{before,after,result}.json`，输入与验证另在父目录。

如确实要撤销此次数据导入，在宿主执行：

```sh
D=/usr/local/bin/time-tracker-docker
B=/var/snap/docker/common/time-tracker-ha/backups/exam-grading-20261124
$D cp "$B/rollback_grading.py" time-tracker-ha-web:/tmp/rollback_grading.py
$D cp "$B/import" time-tracker-ha-web:/tmp/grading-restore
$D exec -e PYTHONPATH=/app time-tracker-ha-web python /tmp/rollback_grading.py /tmp/grading-restore
# 全部验证一致，且用户确认要撤销数据后，才在同一命令末尾添加 --apply。
```

默认只读；出现后续真实编辑会拒绝，不能强制以旧快照覆盖。恢复只针对本次50行范围，不全库恢复。原题及原图不在变更范围。47仍余约11GiB。

## 16:06补修：题号点击定位与整卷回顾

用户反馈“点击题号回到顶部，整卷回顾找不到”。真实原因：全局Router把review查询变化按普通路由滚顶；列表“整卷查看”仍指向同一批阅总览，批阅组件又隐藏了原整卷列表。

- review题号变化保留路由滚动控制，组件等上方Markdown实际渲染并nextTick后，再对真实批阅区scrollIntoView，使用scroll-margin-top:64px。无任意延时、无自动聚焦、无键盘弹出。
- 首个候选已修复点击，但真实线上刷新探针发现Markdown异步布局仍导致偏移，补充rendered事件后再恢复，不把第一次候选称作最终通过。
- 成绩页与试卷列表均有“整卷回顾”，指向 `/papers/:uuid/review?mode=all`，恢复完整30题、用户答案、分数、原始答案贴图与折叠批阅；可从某题返回逐题批阅或标准Practice。只读回顾不显示会误写掌握的批量标记操作。
- 最终应用 `f946134`（前序修复提交1eeafdf、50a4b00），镜像 `time-tracker-ha:20261124-review-navigation-f946134` healthy。仅前端，无数据库写入/迁移，不修改76.5分、18待复习Note及第5题改判。
- 3个定向前端用例通过（进程约1秒），类型/最终Vite构建通过（7.02秒）；生产390×844和1180×820实测：点击8题内容距顶64.16px/63.97px，刷新也恢复，成绩页/列表两入口均显示30题，整卷返回8题定位正确，无JS错误。
- 原验收只断言URL与选中题号，遗漏“真实内容是否出现在视口”；本次改成实际DOM坐标断言+刷新+真实入口检查。Safari/PWA实体机仍未测。
- 备份 `/var/snap/docker/common/time-tracker-ha/backups/exam-review-navigation-20261124`（verify-exit=0），不重复导出题库。
- 回滚：`sh /var/snap/docker/common/time-tracker-ha/releases/exam-review-navigation-f946134/rollback.sh`，回到本次导航补修前5dc4bca；保留全部成绩和Note。
- 本次有两次构建候选及一次线上补发，用于修复已实测的刷新偏移；不掩饰返工。最终线上证据见 `navigation-browser-check.json`、`navigation-question8-*.png`、`whole-review-*.png`。
