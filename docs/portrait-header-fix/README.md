# 竖屏做题顶部、侧栏点击高亮与小猫Logo

源码`5a555f2`，2026-11-13。修改仅3个文件：`frontend/drill/src/styles.css`、`frontend/shared/ui/navigation/AppSidebar.vue`、新增`frontend/shared/assets/study-cat.webp`。

## 改动与原因

- 旧≤620px规则把顶部导航强制column；≤900px还为已移除的悬浮菜单留52px padding。取消空位，窄屏改为菜单/返回/翻题同一行；竖屏状态/记录并排、标题/路径紧凑，收藏/分享/待复习/勘误为可横向滚动的一行，全部功能保留。宽屏横屏/FullscreenReader独立规则不改。
- 用户再次报告Drill/EI点击后蓝框。本次补上Safari `-webkit-tap-highlight-color:transparent`，鼠标/触控focus非focus-visible时无outline；键盘Tab仍保留中性focus-visible轮廓。上次仅改outline颜色不足以覆盖WebKit tap overlay；本轮真实Safari未测，不能称已实机证明。
- 小猫来自仓库`tracker/static/tracker/img9387-icon-180.png`（原始`IMG_9387.jpeg`）。ImageMagick等比例降至48×48 WebP、814B，显示24×24；共享侧栏Timer/Drill/EI共用。没有生成新图或替换猫形象。

## 最小校验

Timer与Drill共用侧栏，因此串行构建两者，类型检查与生产构建约35.92秒通过；没有跑全量测试/数据库迁移。

Chromium真实本地题库、英文界面：390×844和820×1180顶部导航45px、工具44px；1180×820横屏43px导航；3组无全页水平溢出。鼠标点击链接outline none/tap透明；Tab→ShiftTab回到同一链接focus-visible为solid中性灰。Logo原图48px、实际24px，见[browser.json](browser.json)。[手机](question-390.png)、[iPad竖屏](question-820.png)、[横屏](question-1180.png)、[侧栏](sidebar.png)。这些不是实体iPadOS Safari结果。

用户数据备份与开发并行，不重新导出题库。旧9cfe91f镜像及web/queue/PWA配置保留；应用回滚不覆盖新学习记录。最终部署和阶段时间写入production.json/timing.json。

## 最终部署与计时

生产镜像`time-tracker-ha:20261113-portrait-5a555f2 sha256:eb7e4be6e9374fedda52a360ee0d82834c21d0310752fd533a9f326a5d4ed163 healthy`，切换2026-11-13T03:58:06+08:00→2026-11-13T03:58:26+08:00，退出0，登录200，queue成功。生产Drill CSS200、SHA256与构建一致。[实际发布证据](production.json)。

- 开始03:51:40；实现/备份启动03:53:53附近；双前端构建03:53:54→03:54:30，35.92秒；本地浏览器约数秒。
- 用户备份2026-11-13T03:53:54+08:00→2026-11-13T03:53:56+08:00，982728字节，验证exit0；未重备题库。
- 最终生产健康03:58:26；从开始到健康406秒（6分46秒）。镜像打包阶段较前两轮慢，原始时点见[timing.json](timing.json)；没有用额外全量测试解释等待。
- 源码`5a555f2`；当前分支`feat/collection-preview`，文档提交不重新部署。

47回滚到9cfe91f（保留新学习数据）：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/portrait-5a555f2/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-portrait-20261113
```
