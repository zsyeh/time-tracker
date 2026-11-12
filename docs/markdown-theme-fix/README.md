# 纯文字题干/答案暗色修复

2026-11-13，源码 `9cfe91f`，47生产 `time-tracker-ha:20261113-markdown-9cfe91f sha256:a97e767f032f46a2e1293672cf815bd4944fa7233abeef94f50705091bc8817f healthy`，部署退出0，登录200，queue成功；[发布与CSS校验](production.json)。开始03:37:37，最终健康03:40:51，上线墙钟194秒（3分14秒）。

## 原因与改动

`frontend/drill/src/styles.css` 把共享MarkdownAnswer正文、标题、KaTeX行内/块公式写死为#202124/#151619；这会把预览/全屏阅读的暗色主题文字压回黑色。改用text-primary及surface/border语义Token；纯文字question-canvas同步主题背景，答案文字容器同步主题。扫描题图/答案图片的纸色背景、图片像素、业务渲染和提交协议不变。

范围包括普通题干/答案、预览、FullscreenReader复用的MarkdownAnswer；浅色深色均跟随主题，代码/引文/表格局部底色也保持匹配。不改原Markdown渲染器、数据或主题偏好。

## 最小校验与证据

- 受影响Drill类型检查+生产构建，03:38:26.170–03:38:42.214，约16.04秒；Timer无改动，不重建，不跑全量PG/Vitest。
- Chromium加载真实生产构建CSS和与组件相同的Markdown/KaTeX DOM，检查题干/答案/预览3上下文×浅深2主题。深色正文/标题/行内公式/块公式/代码均rgb(237,237,237)，浅色均rgb(32,32,32)。[颜色断言](colors.json)、[深色截图](dark.png)、[浅色截图](light.png)。这是针对CSS的浏览器校验，不冒称完整认证做题或实体Safari测试。
- 生产实际CSS200、SHA256与本次构建一致；Dockerhealthy、真实登录入口200、queue成功。未因小样式修复执行整站回归。
- 用户数据备份2026-11-13T03:38:26+08:00→2026-11-13T03:38:29+08:00，并行约3秒，验证exit0；未重新导出题库，无迁移。

## 回滚

旧生产7cec16c镜像及web/queue/PWA配置保留在`/var/snap/docker/common/time-tracker-ha/backups/round2-markdown-20261113`；用户数据另备，不用旧备份覆盖新学习记录。47执行：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/markdown-9cfe91f/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-markdown-20261113
```

本轮只有一个CSS源文件，无新依赖、后端修改或数据库迁移。按相关构建+颜色断言发布，没有重新进行全站审计。文档提交不再部署。
