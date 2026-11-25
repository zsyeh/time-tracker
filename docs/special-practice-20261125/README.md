# 专练模式与纠错后复盘 · 2026-11-25

## 交付

- 应用提交 `ef0a225`，最终镜像 `time-tracker-ha:20261125-special-practice-ef0a225-final`，11:58:56 +08 healthy；登录健康入口200。
- Drill/EI 独立侧栏“专练模式”，可调整显示、排序并随现有账号偏好同步。入口 `/drill/special-practice`、`/ei/special-practice`，直接刷新200。
- Agent CLI 推送固定顺序题单，幂等且工作区/账号隔离。开始专练直接复用 QuestionView 全部成熟功能、原答案和学习状态；本卷顺序上一/下一、滚动预览、返回题单正常。不新建作答协议、不引入考试倒计时/答案锁；推送不计入作答。当前显示最近100份题单。
- 复用 ExamPaper/Item 做成员关系容器，专用 inactive weak blueprint（版本30000）；不进入原考试列表，不新建数据库表或迁移。首次真实推送按工作区创建容器模板与固定成员，题目内容不改。
- 实际接入文件：`drill/special_practice.py`、`push_special_practice.py`、`drill/urls.py`/`views.py`，前端 `SpecialPracticeView.vue`、App/main/listContext；服务端SPA/PWA白名单与前后端sidebar manifest/labels，现有共享偏好模型保持不变。
- Agent后续使用：[推送工作流](AGENT_WORKFLOW.md)。用户复盘：[2026-11-25](POST_REVIEW_20261125.md)。未自动选取或推送66道题。

## 复盘入库

原试卷148，UUID `f2ab8798-0526-4a18-89af-802af6e664ae`。

- 用户新的失分分类以 `grading.post_review` 单独保存，来源user_post_review、日期、摘要digest；五科仍为五段文本，更新 `grading.weaknesses`，新报告显示在原总评下。
- Q12/17/19纠错后理解满分单独列位置，不替换原考试逐题earned/self_score；Q17歧义和Q9考纲边缘保留为用户意见，不冒充已核实的标准答案/考纲结论。
- 原考试估分 **76.5/150** 不变，原分数/逐题分值/作答次数前后检查一致；没有新增Attempt或时间。未将所有错误归为“不会做”，未自动将纠错结果改成永久掌握。
- 66题/300分钟保存为非强制建议，不将其当成已完成训练或成绩预测。
- 使用事务，只更新当前卷 JSON；重复执行返回Already saved/unchanged。原grading完整前像位于47受保护备份目录 `post-review-before.json`，不进Git。应用回滚不撤销用户本次复盘。

## 验证

- 前端7项通过：新页空态、真实Practice URL/题单上下文，以及既有listContext契约；1.24秒。
- 后端最终4项通过，0.255秒：顺序/幂等、非法UUID与跨库原子拒绝、账号隔离/预览/考试列表隔离/SPA、sidebar新增ID兼容。
- 首轮宽测试误发现引入的旧TestCase且受旧fixture/host限制；改成module导入并限定相关用例、明确测试域名；新模板版本60000超出PG smallint，修正30000后通过。没有将失败记成通过。
- 类型检查、Drill与Timer构建通过；Vite阶段分别7.24/10.56秒。共享sidebar schema变化会影响两应用的偏好校验，因此同步构建两端，不只Drill。
- 生产隔离账号测试两个工作区：1440桌面、390手机；左侧入口、开始标准Practice、固定下一题、Q预览、返回题单、直接刷新200、无横向溢出/无pageerror。见 [browser-check.json](browser-check.json) 及截图。
- 已删除临时QA账号、两份题单、会话和仅用于测试的空模板；确认无测试Attempt。真实用户复盘与成绩保留。实体Safari/PWA未实测，不声称通过。
- 登录/管理/公共页使用的 `/static/tracker/ui/appearance-bootstrap.js` 收集路径另行同步；线上解压文件SHA256与源码一致 `3ac3a043676ccac9e259d16b9d5a60036f505567ae63230f7f24772dae411697`，避免旧脚本拒绝新增sidebar ID。

## 发布、计时与回滚

- 可核对阶段：11:50:52启动用户备份→11:50:54完成；与开发并行。11:56左右完成首次上线与两端浏览器验证，11:58:56补齐登录静态bootstrap后最终healthy。备份起点到最终上线8分04秒；不冒充未记录的精确开发起点。
- 用户数据/Schema/服务配置/旧镜像备份在 `/var/snap/docker/common/time-tracker-ha/backups/special-practice-20261125`，verify-exit=0；没有全库题图导出。
- 回滚命令：`sh /var/snap/docker/common/time-tracker-ha/releases/special-practice-ef0a225/rollback.sh`，回到 `time-tracker-ha:20261124-review-favorite-34e10c8`；保留数据库，不覆盖发布后学习记录。回滚后新入口不可用，固定题单数据仍在。
- 静态bootstrap漏收集导致一次补发；不重做已通过源码构建，仅修正不可变镜像的静态映射。没有迁移、数据库重启或无关queue发布。
