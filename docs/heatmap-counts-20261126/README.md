# 数学严选题总体及章节统计 · 2026-11-26

- 源码 `0fd3e2b`，生产镜像 `time-tracker-ha:20261126-heatmap-counts-0fd3e2b`。
- 顶部和每个章节显示已做、已掌握、未做、待复习：数量 / 当前筛选总量、百分比（最多一位小数）。未做=总量−已做，空集合显示0%；掌握百分比的分母为总量，不使用后端的已做题掌握率。
- 复用原热力图响应，不增加请求、不改状态定义、不改EI核心题页面、不改题库/学习数据，无数据库迁移。仅数学selectedOnly页面启用新摘要。
- 18项相关Vitest通过（2.30s）；Drill类型检查及生产构建通过（Vite7.19s），构建1次。旧总数摘要断言随本次明确需求更新；其余恢复、过滤及题目矩阵测试通过。
- 生产镜像healthy，登录HTTPS200。隔离QA账号真实959题/7章节，390、820、1180宽度均完整显示4项，无横向溢出和文字越界，无pageerror。Chromium视口验证，Safari/PWA实体设备未测。QA账号验证后清理。
- 开发/校验/发布约11:02—11:06；用户数据及schema备份与开发并行，无全题图备份。细分准确发布起止以服务器deploy-start/end.txt为准。
- 用户备份：`/var/snap/docker/common/time-tracker-ha/backups/heatmap-counts-20261126`，验证退出码0。
- 回滚：`sh /var/snap/docker/common/time-tracker-ha/releases/heatmap-counts-0fd3e2b/rollback.sh`，恢复上一版22381ca镜像及配置，不覆盖发布后学习数据。
