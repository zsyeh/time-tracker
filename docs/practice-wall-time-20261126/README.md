# Practice：按开始到提交计时

## 用户确认与数据

用户确认会切后台，要求按开始结束计时、超过30分钟不计。采用单次作答口径：后台/锁屏/浏览器暂停调度也计入经过时长；恰好30分钟计入，超过30分钟用时存NULL，作答、笔记、诊断和掌握状态正常保存。不会截断为30分钟或删除作答。

示例严选06-058（2018数一）：开始10:04:36，提交10:25:52，间隔约21分16秒，原前台协议保存425秒。相关计时请求全部200、未发现提交冲突，有约14分钟同步空档。旧规则隐藏时暂停、超过15秒的回调间隔被丢弃；用户已明确选择新的起止规则。

已完成历史作答不重算，示例原425秒保留。未提交旧轮次首次采用新版claim时升级，保留原开始时间及previous_foreground_elapsed_ms。原5秒准备期保持，之后算本轮开始。

## 实现文件

- frontend/shared/foregroundTimer.ts：显式wall-time模式，沿用protocol2、请求time_basis=wall_v1；服务端校准本地日期时钟锚点，恢复后重新计算，不再丢弃冻结间隔。旧前台客户端兼容。
- drill/serializers.py：验证可选wall_v1。
- drill/recovery.py：服务端以now减timer.starts_at核算，忽略客户端伪造毫秒；超过1800000毫秒记录duration_excluded_reason=over_30_minutes。隐藏的pause仅同步并释放租约，不停止墙钟；账号隔离、所有权、冲突及提交幂等保留。
- drill/views.py：保留真实计时依据，不强制覆盖foreground_v2。
- QuestionView.vue：普通和全屏共用计时状态，显示新规则；使用本次time_spent_seconds判断NULL，避免同题旧的有效用时掩盖本次不计时。
- 无Schema迁移、无题库或已完成作答重写；不改Timer全局净时长或考试倒计时，无新按钮。

## 校验

前端30项通过（1.53秒）、后端31项通过（12.642秒）。后端覆盖新后台间隔、精确30分钟、30分钟+1ms、伪造客户端时间、旧未提交轮次升级、账号所有权及重复提交。Drill类型检查和构建通过，最终Vite7.20秒。

生产Drill/EI手机尺寸验证实际请求wall_v1、计时增长及全屏可见，无pageerror。Chromium标签切换后仍报告visible，未将该项冒称真实后台检查。额外CDP冻结渲染进程16.2秒：计时0:51变为1:08，间隔保留。隐藏与长冻结由单元测试覆盖；实体Safari/PWA锁屏未测。

使用独立临时账号，不操作真实用户作答；验收后清理测试账号、会话及专用测试数据库。

## 发布与回滚

源码22381ca，镜像time-tracker-ha:20261126-practice-wall-22381ca，10:45:27开始切换，10:45:38完成，healthy及HTTPS登录200。已打开的旧Practice需要刷新，以发起新模式请求。

用户/学习备份位于/var/snap/docker/common/time-tracker-ha/backups/practice-wall-time-20261126，校验通过，未复制题库图片。

回滚：sh /var/snap/docker/common/time-tracker-ha/releases/practice-wall-22381ca/rollback.sh。旧84dd476镜像保留，脚本语法检查通过；无需反向迁移，不恢复旧数据库覆盖新增学习记录。回退后恢复旧计时规则，已保存的有效用时仍保留在Attempt中。
