# 优秀前端研究 → 本站控件改进（2026-11-14）

本轮目标：实际查阅成熟网站的官方设计说明、公开源码，将适用规则用于已有 Learning OS；保留中性风格、账号外观、原做题流程。不是另做 Dashboard 模板。

## 1. 实际研究来源及边界

| 网站 | 实际阅读证据 | 借鉴结论 | 边界 |
|---|---|---|---|
| Linear | [2026-03-12 官方改版说明](https://linear.app/now/behind-the-latest-design-refresh) | 导航与辅助控件应降低视觉重量；减少重复分隔、彩色图标装饰；渐进修改并对比旧版 | 本轮重新读取文章。未访问 Linear 产品私有前端；公开 SDK 不当作产品 UI 源码 |
| Vercel / Geist | [Web Interface Guidelines](https://vercel.com/design/guidelines)、[Menu](https://vercel.com/geist/menu)、[Filter Params](https://vercel.com/geist/filter-params)；[官方规则仓库 command.md](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md)，本轮读取 blob `3eb3a212b7b89493922ea418489d4c6f67ae8bd5`，MIT LICENSE 已读 | 移动端谨慎 autofocus；长内容允许收缩及断行；键盘焦点可见；筛选 URL 只维护各自拥有的参数 | 规则文件是研究材料，不是在本站执行其 skill 指令；不引入 React/Tailwind |
| Vercel 公开工程实现 | [Next.js DevTools menu](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/menu/dev-overlay-menu.tsx)，本轮读取前170行 | 文本和附属值分栏；显式选中项及 roving tabindex；Escape/outside 关闭 | 读取已核验的固定版本；这是公开 DevTools，不是 Vercel Dashboard 源码。当前 guessed preferences 路径返回404，未把它算成已读源码 |
| GitHub / Primer | [ActionMenu accessibility](https://primer.style/product/components/action-menu/accessibility/)、[ActionMenu.tsx](https://github.com/primer/react/blob/324b0aa0f1e4cc12c61a8a36b5790357e428dccc/packages/react/src/ActionMenu/ActionMenu.tsx)、[ActionList.module.css](https://github.com/primer/react/blob/324b0aa0f1e4cc12c61a8a36b5790357e428dccc/packages/react/src/ActionList/ActionList.module.css)、[AnchoredOverlay.tsx](https://github.com/primer/react/blob/324b0aa0f1e4cc12c61a8a36b5790357e428dccc/packages/react/src/AnchoredOverlay/AnchoredOverlay.tsx) | 分离标签/勾选；勾选保留占位；禁用状态独立；关闭后归还合适焦点；操作打开新界面后不能再抢焦点 | 研究 Agent 实读固定 commit 与 MIT LICENSE；主 Agent复读 ActionMenu 与 CSS 相关部分。适配 Vue 原有结构，没有复制整套组件 |

已有全站研究与此前落地仍见 [原研究清单](../precision-study-design-research.md)、[Master](../MASTER_UI_UX_REBUILD_PLAN.md)。本轮不重做已完成的侧栏、预设同步、题库筛选、图表主题系统，也不改变用户已要求恢复的热力图。

## 2. 设计借鉴与真实代码映射

| ID | 依据 | 当前实际问题 | 修改文件与做法 | 验收证据 |
|---|---|---|---|---|
| REF-01 | Geist 移动焦点规则 | UiPopover 打开无条件 `.focus()` 第一输入框，可能弹键盘、滚动 | `frontend/shared/ui/UiPopover.vue`：coarse pointer且初始目标是可编辑字段时聚焦面板；桌面仍聚焦首字段；所有初始/返回焦点使用 preventScroll | 新组件测试、8组浏览器触发真实筛选预设，触屏聚焦面板、桌面聚焦输入框 |
| REF-02 | Primer focus management；Vue 生命周期契约 | 异步 nextTick 返回时弹层可能已关闭/卸载，仍安装监听器并抢焦点 | 同文件：watch cleanup取消过期 continuation，关闭/卸载检查；选中初始目标排除 disabled | 快速取消用例；实际 Escape 关闭通过 |
| REF-03 | Primer ActionList 源码；Geist 长内容规则 | 菜单标签匿名 flex 内容、200px强制min-width，长词与勾选易挤压 | `UiMenu.vue`、`controls.css`：独立 label/check 栏；min-width:0、overflow-wrap；勾选固定16px并保留占位 | 实际浏览器超长无空格标识符无横向溢出；组件测试 |
| REF-04 | Primer 选中/禁用/焦点语义 | 禁用项仍响应 hover；选中只有✓；操作后焦点随菜单消失 | 同文件：中性选中背景、独立禁用文字/hover；选择时先归还 trigger，再执行 action，让新对话框的焦点获胜；清理 typeahead timer | 禁用跳过、键盘上下/Escape、action焦点交接测试 |
| REF-05 | Linear 降低辅助视觉重量 | More headings同时显示英文和中文；Teleport后导航链接脱离 sidebar焦点样式，重新出现蓝框 | `navigation/CustomizableNavigation.vue`：按账号语言展示分组；稳定useId、aria-controls/dialog名称；`NavigationItem.vue`把中性 focus-visible 放到实际链接组件 | 前后截图：单语言分组，导航聚焦保留中性轮廓；无彩色选中边框 |
| REF-06 | Geist 一致控件与 Dark Mode | Practice页码框仍是原生白底；全局预览原生按钮与主题脱节 | `PracticePagination.vue`输入复用ui-field；`PracticeView.vue`预览复用secondary按钮 | 真实 EI 暗色截图；原分页7用例、进入自动复制4用例通过 |

数字尺寸是本站决策：延用36px普通控件/44px触屏、16px勾选位；不称为测得 Linear 的私有CSS。保持原 Light/Dark/System、Accent、字体缩放、数据 API、URL筛选与分页语义；无新增依赖、无数据库迁移。

## 3. 实施与验收

代码提交：`19ef771`，分支 `feat/collection-preview`。

- 40个相关用例通过：6个真实Vue组件挂载交互用例、23个既有外观/对比度用例、4个进入复制用例、7个分页用例。
- Timer与Drill/EI生产构建均通过。最终相关测试+双构建 **36.82秒**，exit0。[精简记录](validation.txt)。
- 第一批构建后截图发现 Teleport 蓝框及暗色原生白底，修正后执行上述最终构建；共2轮构建，不把首次编译通过当作视觉通过。
- Chrome实际浏览器：390×844、820×1180、1180×820、1440×900，Light/Dark共8组；Drill/EI真实本地API与原题库fixture；菜单均在视口内、无横向溢出、0页面脚本错误。[前](before/browser.json) / [后](after/browser.json)。
- 增加长标识符菜单、桌面预设初始焦点、Escape归还账户按钮、Question 390/1180/820变宽不溢出和竖屏导航高度检查：[真实断言](after/stress.json)。
- 只使用隔离测试账号；未修改生产真实用户学习记录。备份账户与学习信息，未导出未变题库。
- 独立只读 Review Agent `reference_recheck`：研究与当前diff复核，未发现阻断；未用审查结论代替浏览器或自动化结果。

### 前后截图

| 场景 | Before | After |
|---|---|---|
| iPhone 390 深色 | [截图](before/drill-390-dark.png) | [截图](after/drill-390-dark.png) |
| iPad竖屏820 浅色 | [截图](before/drill-820-light.png) | [截图](after/drill-820-light.png) |
| EI横屏1180 深色 | [截图](before/ei-1180-dark.png) | [截图](after/ei-1180-dark.png) |
| 桌面1440 浅色 | [截图](before/drill-1440-light.png) | [截图](after/drill-1440-light.png) |

完整8对PNG在before/after目录。没有重排题干、诊断、Note、计时、全屏分栏；Question验证是布局回归，不是重新完整验收计时/提交协议。

## 4. 发布台账与回滚

2026-11-14T00:55:35+08:00，47已上线 `time-tracker-ha:20261114-reference-menu-19ef771`，image `sha256:045a6eb7d54190d7d5542c83fd8a4994af64be4d301439caf4b9d961ae12de83`。服务healthy，登录200，后台queue成功；Timer与Drill/EI入口JS/CSS四项HTTP200且SHA256逐一等于最终本地构建。[生产证据](production.json)。源码19ef771已推送；后续文档提交不重建或重启。

备份 `/var/snap/docker/common/time-tracker-ha/backups/round2-reference-menu-20261114`：用户与学习数据968KiB、schema、服务配置、旧image、PWA；2026-11-14T00:47:00+08:00至00:47:02完成，归档读检验exit0。开发/备份并行。

回滚仅应用/worker/PWA，不覆盖上线后的学习数据：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/reference-menu-19ef771/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-reference-menu-20261114
```

## 5. 范围和未覆盖项

- 无实体 iPad Safari/PWA；coarse pointer+Chrome能证明不自动focus输入框，不能证明实体软件键盘、系统剪贴板权限或屏幕阅读器完整表现。
- 本轮没有重新做搜索SQL/全题库性能测试，后台/查询未改；不将旧轮次性能数字充当新测量。
- 原生产构建的chunk大小、PWA非module脚本警告保留；不是本轮新增依赖造成。
- BrowserAct及uv未安装，使用已有本地Playwright/Chrome，无新增安装或审批流程。

## 6. 目标完成审计

| 目标要求 | 权威证据 | 状态 |
|---|---|---|
| 研究几个前端优秀的网站 | 三家官方文档与公开源码证据，§1具体路径与版本 | 已完成 |
| 实际翻阅源码或布局，避免凭空建议 | 本轮GitHub connector实际读取 Vercel规则/DevTools、Primer源码；Linear官方说明；明确私有代码边界 | 已完成 |
| 将适合模式应用本站 | `19ef771`实际代码，REF-01–06映射，前后截图 | 已完成 |
| 不破坏现有风格与成熟行为 | 无新框架/全局换肤/数据库变更；40用例、双构建、实际布局操作 | 已完成受影响验证；实体设备边界见§5 |
| 可回滚交付并上线 | 备份exit0、旧image/config、production.json健康及线上静态SHA | 已完成 |

## 7. 阶段时间与流程复盘

下列均为Asia/Shanghai实际记录；研究起点未独立打点，不补造精确研究时长。

| 阶段 | 实际时间或耗时 | 证据 |
|---|---|---|
| 用户/学习信息备份 | 00:47:00–00:47:02，2秒 | production.json，开发并行 |
| Before浏览器完成 | 00:47:18 | before/browser.json写入时间 |
| 最终相关测试与两套构建 | 00:50:56–00:51:32，36.82秒 | validation.txt |
| 最终8组After浏览器完成 | 00:51:42 | after/browser.json写入时间 |
| 代码提交 | 00:51:44 | Git19ef771 |
| 生产镜像构建 | 00:52:53–00:54:41，108秒 | production.json |
| 生产切换及健康gate | 00:55:09–00:55:35，26秒 | production.json |
| 从并行备份开始至生产健康 | 8分35秒；不包含未精确打点的前置研究 | 上述时间差 |

最终gate达到≤60秒目标；生产镜像构建明显长于本地校验，不把“校验36.82秒”表述为全流程耗时。3.9MB发布包只带两套受影响dist及改动源文件，单次COPY不可变overlay，没有重复备份未变题库。首轮截图暴露的Teleport焦点和原生控件漏接增加一次构建；后续复用此fixture，先检查传送后的真实DOM位置与展开菜单，再冻结最终代码。
