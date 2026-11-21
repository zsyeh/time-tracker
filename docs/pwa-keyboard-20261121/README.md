# Apple PWA Note 键盘偏移修复 · 2026-11-21

## 代码证据与范围

用户报告做题页Note弹键盘/回车导致整页上移。现有 `styles.css` 横屏分栏在min-width1000/min-height500/landscape时锁住html/body滚动，shell使用100dvh；没有VisualViewport键盘处理，QuestionView没有拦截Note回车。与Apple所述键盘仅改变可视区域、可平移可视区域而不改变布局视口一致：[Apple WWDC19](https://developer.apple.com/videos/play/wwdc2019/203/)、[WebKit VisualViewport说明](https://webkit.org/blog/9674/new-webkit-features-in-safari-13/)。这是代码和机制支持的定位，尚非实体设备录屏复现。

`92822b1` 新增 `lib/practiceKeyboardViewport.ts`，只在Apple触屏、既有横屏分栏且编辑输入发生键盘收缩/平移时，把shell限定到VisualViewport.height/offsetTop。Note在原右栏内就近滚动；不调用window.scrollTo，不拦截Enter、输入法或touchmove，不改保存/计时。不改变手机/竖屏正常文档滚动、非Apple桌面、双指缩放及全屏阅读器。关闭键盘、旋转出分栏或组件卸载移除临时样式和监听。过高编辑框不反复上下强制对齐。

真实修改：`frontend/drill/src/lib/practiceKeyboardViewport.ts`、对应3项单测、`views/QuestionView.vue`生命周期、`styles.css`既有分栏规则内6行样式。无API、数据库或题图修改。

## 校验及未覆盖

- 3项局部Vitest通过，880ms（其中测试259ms）；Drill类型/生产构建通过，Vite6.98秒；一次最终构建。首次测试因jsdom无maxTouchPoints属性失败，改测试夹具后通过，未改产品检测条件迁就环境。
- 本地真实QuestionView + Chromium 1180×820，模拟Apple navigator及VisualViewport事件：820→420高、offset96→132，shell/main高度420、window.scrollY=0、Enter保留换行、关闭恢复，无JS错误。见 `browser-simulation.json`。**模拟视口不等于真实Safari键盘复现**。
- 生产新JS/CSS均HTTP200，逐字节SHA与本地产物一致；登录200、Dockerhealthy、queue Result=success/ExecMainStatus=0。见 `production-assets.json`。
- **实体iPad Safari/PWA仍待用户确认**；如果竖屏/手机也有持续偏移，必须单独录其真实滚动容器和VisualViewport值，不能把横屏方案盲目推广为整站body锁定。

## 发布/计时与回滚

- 新镜像：`time-tracker-ha:20261121-pwa-keyboard-92822b1`；旧镜像保留 `time-tracker-ha:20261121-exam-ei-daa3fc8`。
- 并行用户数据/Schema/配置备份：`/var/snap/docker/common/time-tracker-ha/backups/pwa-keyboard-20261121`，verify-exit=0。题库不变，未重复备份原题图片。
- 新增实现文件实际创建20:29:08→发布健康20:31:10，可核对施工区间2分02秒；此前代码阅读不在此区间，不能当总开发时长。发布切换20:30:55–20:31:10，15秒。局部校验不足60秒；前后只做受影响路径，无全套后端测试。
- 回滚（仅恢复旧Web配置/镜像，不回写数据库或删除上线后笔记）：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/pwa-keyboard-92822b1/rollback.sh
```
