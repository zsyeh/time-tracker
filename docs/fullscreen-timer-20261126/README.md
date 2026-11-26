# 全屏显示现有计时器

- 用户要求：全屏状态也显示计时器。`84dd476`复用FullscreenReader顶部可选timer slot，Drill/EI Practice展示现有单题计时；考试模式展示现有剩余时间，已结束时显示结束状态。不创建第二个计时器，不改变计时、作答或考试答案限制。
- 修改：`FullscreenReader.vue`、`QuestionView.vue`、`PaperExamView.vue`及相关组件测试。顶部数字使用tabular numerals，保持现有按钮、缩放和退出操作，无新增操作步骤。
- 15项相关测试通过（1.42秒），Drill类型检查及生产构建通过（Vite7.22秒）。新增测试验证全屏slot实时更新及换题不重建显示节点。首次新测试因jsdom缺少dialog.close而在卸载时报错，补齐测试桩后通过；首次构建输出目录不可写，改用明确的staging环境变量，无产品修复伪造。
- 生产实际浏览器：Drill/EI、1180×820及390×844触屏尺寸，计时器实时变化，退出重新进入不重置，计时器及关闭按钮可见且不重叠，无pageerror。截图在私有发布工作目录，避免将真实题图复制进仓库。实体Safari/PWA未实测。
- 生产镜像`time-tracker-ha:20261126-fullscreen-timer-84dd476`，健康检查通过。无迁移、无学习数据重写；只用临时隔离账号验收，完成后删除该账号及会话，不改变真实用户学习状态。
- 备份：`/var/snap/docker/common/time-tracker-ha/backups/fullscreen-timer-20261126`，用户/学习数据及配置校验通过，不重复备份题库图片。
- 回滚：`sh /var/snap/docker/common/time-tracker-ha/releases/fullscreen-timer-84dd476/rollback.sh`，恢复f86ce04；脚本语法检查通过、旧镜像保留，无需反向迁移或还原旧数据库。
