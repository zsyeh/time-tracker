> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Linear 研究与导航源码审计

日期：2026-11-12。仓库：`/home/eh/precision-study-ui-20261111`。本次只读源码、获取公开资料、写研究文档；未修改业务代码。

## 1. 证据边界与官方资料

1. **官方设计文章 L01**：[A calmer interface for a product in motion](https://linear.app/now/behind-the-latest-design-refresh)，2026-03-12。明确说明：侧栏降低亮度以让内容突出；减少和缩小图标；削弱多余分隔；默认主题从偏蓝转向低饱和灰；Header 的位置和视图控制趋于一致。它描述原则，未公开产品组件源码或精确尺寸。
2. **官方发布说明 L02**：[UI refresh](https://linear.app/changelog/2026-03-12-ui-refresh)。确认本次 refresh 涉及导航、Header、view controls 和 icon，不应理解为只换色。
3. **官方公开图片 L03**：[2026 sidebar before/after](https://webassets.linear.app/images/ornj730p/production/b6d6be14c96978b10553cfb9205be1065087e793-3904x2720.png)。已下载并通过图片工具观察。新侧栏为近黑背景、整行中性选中底色、非活跃文字弱化、小型单色图标、折叠组标题；没有每行彩色边框。图片不是 live app 实测。
4. **官方产品文档 L04**：[Workspaces](https://linear.app/docs/workspaces)。工作区名称位于左上，提供切换和设置入口。项目中的 Timer/Drill/EI 可采用这种“位置明确的上下文切换”概念，不照搬 Linear 的组织/权限模型。
5. **官方发布说明 L05**：[Personalized sidebar and new settings pages](https://linear.app/changelog/2024-12-18-personalized-sidebar)。提供分组、低频项目收进 More 的先例；不要求本项目实现拖拽自定义，避免扩大范围。
6. **官方文档 L06**：[Preferences](https://linear.app/docs/account-preferences)。支持 Light、Dark 和 System；仅用作外观模式的产品证据，不推断它的持久化方案。
7. **官方发布说明 L07**：[Collapsible Sidebar](https://linear.app/changelog/unpublished-collapsible-sidebar)。确认完整折叠并从左上重新打开的交互；不复制旧键盘快捷键，防止与数学编辑冲突。
8. **官方移动发布说明 L08**：[Customize your navigation in Linear Mobile](https://linear.app/changelog/2026-01-22-customize-your-navigation-in-linear-mobile)。其移动导航支持常用入口优先。我们不照搬底部工具栏：现有做题提交操作已占底部，双浮层会降低效率。
9. **公开仓库 L09**：[linear/linear](https://github.com/linear/linear)，README、`packages/`、`examples/nextjs-file-upload/`。实读仓库页面确认其为 API SDK、GraphQL 代码生成插件、相关工具；不能作为 Linear 产品 Sidebar/CSS 源码。未访问任何私有代码。未从第三方复刻推断官方实现。
10. **官方首页 L10**：[linear.app](https://linear.app)。可观察到 Workspace/Favorites 等产品层次，首页是营销演示，不等于完整产品交互实测。

所有下面的像素值、断点、组件边界和测试约束均是**基于本项目业务与源码作出的工程决定**，不是声称测得 Linear 的私有样式。

## 2. 已证实的代码问题与应保留的实现

### 2.1 圆点根因（R03、R04）

Drill/EI：`frontend/drill/src/styles.css:102` 的 `.more-tools-panel a::before`、`:107` 的 `.drill-sidebar nav a::before` 显式创建 `5px × 5px`、`border-radius:50%` 圆点；`:105`、`:112` 为 active 圆点着 Accent。不是浏览器 list marker，也不是 Markdown 渲染。导航模板 `frontend/drill/src/App.vue` 是 `nav > RouterLink`，没有 `ul/li`。宽泛的 `nav a::before` 还会影响工作区切换链接。

Timer：`frontend/src/components/navigation/SidebarItem.vue` 在无 icon 时真实渲染 `<span class="sidebar-item-marker" />`；`frontend/src/styles.css:207–208` 的 marker `::after` 再画圆点。科目行未传 icon，因此触发这条路径。**必须移除 fallback marker DOM 和其 CSS，不准新增 `display:none!important` 遮盖。** `MarkdownContent`、MarkdownEditor、题干和笔记 list 样式不在删除范围。

### 2.2 应保留

- Drill 已有整行 active 背景，不需要引入边框来增强。
- `App.vue` More 已 Teleport 到 body 并根据 visualViewport/resize 定位，已解决容器裁切问题；保留其行为语义，归入共享 Popover 后加强可访问性。
- Drill 折叠状态保存在 `drill.sidebar.collapsed.v1`，没有设置时 Question 路由默认折叠。这一默认与用户选择优先级必须保留。
- 进入 Question 时依赖 `from` 和 `collection` 保持导航上下文；不能只按 `route.name` 判断。
- `startLearningRecovery` 在身份加载后启用；侧栏重构不得移动到身份未就绪之前恢复学习状态。
- `deploy/pwa/navigation.js` 已对 Drill/EI 隐藏额外 PWA launcher，应维持。

### 2.3 仍有问题

- 两个 App 的导航实现分叉：Drill 单体 App 内联，Timer 使用 AppSidebar/SidebarItem/SidebarSection/WorkspaceSwitcher。
- Drill/EI 232px 侧栏、顶部品牌小字、三个带框 workspace links、coverage 大数字、来源长文字、两枚主题符号、语言 Select、账号分隔同时占空间。
- Timer 存在 WorkspaceSwitcher + workspace-quick-links 重复跨应用入口；部分内容是与学习无关的 YouTube 主题品牌变化，统一中性设计后须删除对应视觉变体，保留业务内容。
- Sidebar icon 体系分叉：Drill 用伪元素圆点/`•••`/Unicode chevron；Timer 用已安装 `@element-plus/icons-vue`。无需额外大型图标库。
- Drill drawer 用 transform 移出视口，但没有明确 inert、focus trap、body scroll lock；关闭时键盘焦点可能仍进入不可见导航。Timer 只有 body class 锁定和 Escape，不构成完整 dialog 焦点管理。
- Timer Sidebar 没有 Drill 已有的 safe-area padding；Drill drawer reopen 是固定浮动按钮，主体靠各页人工加52px padding，易漏页。
- 现有导航文字 12–13px，某些辅助字 9–11px；应统一正文行14px、组标题12px。
- Drill 页全局 neutral token 实际为蓝灰（`#101216/#13161b/#181b20`），Light active 为 `#e5ebf3`；不符合本轮纯中性色硬约束。
- Timer `SidebarItem` 未显式同步 `aria-current` 与自定义 active 来源上下文；RouterLink 自身只知道当前路由匹配，Question 派生 active 需要统一语义。

## 3. 真实导航矩阵（保留旧路径）

路由注册：Drill/EI `frontend/drill/src/main.ts`；Timer `frontend/src/routes.ts` + `router.ts`。Drill `createWebHistory(routerBase)` 区分 `/drill/`、`/ei/`，不能通过 app sidebar 重置 base。

| 空间 | 主入口（直接可见） | 次级入口（保留） |
|---|---|---|
| Drill | `/selected-heatmap` 严选题热力图；`/insight` 历史；`/progress` 学习进度 | `/practice`、`/diagnostics`、`/activity`、`/book-activity`、`/heatmap`、`/papers`、`/favorites`、`/review-later`、`/feel`、`/errata` |
| EI | `/core-heatmap` 五科核心热力图；`/insight`；`/progress`；`/cockpit` 892总览（保留直接入口） | Drill 的适用次级项；`/circuit-selected`、`/signal-selected`、`/analog-selected`、`/digital-selected`、`/communication-selected`、`/signal-formulas`、`/selected-pdf-pages` |
| Timer | `/today` 今日；`/trends` 趋势；`/sessions` 学习记录；`/issues` 问题 | `/sessions?subject=math|english|major|training`；`/settings` |

其他兼容路由：`/practice/:uuid`、`/diagnostic-queue`、`/papers/new`、`/papers/:uuid`、`/papers/:uuid/review`；`/paper` 重定向到 `/papers/new`；Timer `/sessions/:uuid` 高亮 sessions，公开 `/share/:token` 不渲染私有侧栏。现有首页 `/ -> /practice` 不变。

EI 顺序采用 core-heatmap → insight → progress → cockpit，使学习入口优先；如父计划决定维持 cockpit 首位，必须写成明确决策，不交给执行者临场决定。这里推荐 core-heatmap 首位。

## 4. 推荐施工规格

### 4.1 结构、组件与文件边界

建立 `frontend/shared/ui/navigation/AppSidebar.vue`（新）作为纯 shell，slots 为 workspace、primary、secondary、footer；业务路由数据仍分别留在各 app，不把 Timer 路由塞进 Drill router。共享组件不能 import Timer 的 Element Plus App 或其全局 CSS。

建立 `frontend/shared/ui/navigation/NavigationItem.vue`（新）：`label:string; to?:RouteLocationRaw; href?:string; icon?:Component; active:boolean; disabled?:boolean; badge?:string; depth?:0|1`。`to` 与 `href` 互斥；内部用 RouterLink 或 a；disabled 无导航；active 输出 `aria-current="page"`；icon可选、aria-hidden；无icon时只缩进对齐，绝不生成圆点；slot 的文本不省略可访问名称。

保留 Timer `SidebarItem.vue` 为暂时适配 wrapper，迁完调用后删除；SidebarSection 可迁为共享 NavigationGroup，增加 `aria-controls` 和稳定 id。`App.vue` 仍拥有 username、logout、identityReady、learningRecovery，不将认证和数据 API 下沉进展示组件。

共享基础 Popover 由主 Agent 统一拥有。Drill 更多工具、WorkspaceSwitcher、账号菜单使用它；导航 popover 是 `<nav>` + 正常链接 Tab 顺序，不假装 ARIA menu。若使用 `role=menu` 必须完整实现 arrow/Home/End/roving tabindex，不能只加 role。

### 4.2 几何规格（本项目决定）

| 项目 | 规格 |
|---|---|
| Expanded desktop ≥1200px | 侧栏240px；主区grid `240px minmax(0,1fr)`；可完全折叠到0 |
| Tablet 900–1199px | 侧栏224px；一般浏览默认展开；Question继承原有默认折叠与用户选择；主体无固定min-width |
| <900px | Modal drawer，宽 `min(288px,100vw - 48px)`；页头内44px导航按钮；不设置第二条底部app nav |
| 侧栏高度 | `100dvh`，fallback `100vh`；顶/底 padding `max(12px,env(safe-area-inset-*));` 左安全区同理 |
| 垂直结构 | fixed workspace header + `min-height:0;flex:1;overflow-y:auto` navigation + fixed footer；短高度只滚导航不挤掉账号 |
| Nav行 | pointer:fine 36px高；coarse 44px高；水平padding8px；图标16px；图标与文本8px；圆角6px |
| Text | nav 14px/20px 450；active 550；组标题12px/16px 550；组间16px，无组间分割线 |
| Workspace | 44px整行触发器，名称14px/20px 600，小图标18px，右侧chevron16px |
| Footer | 账号整行44px打开菜单；设置和退出登录在菜单，退出为危险文本语义，不常驻高饱和按钮 |
| More | 272px desktop popover，外边距≥8px，高 `min(520px,visualViewportHeight-16px)`；mobile drawer内以全宽分组展开或独立sheet，推荐保持小弹窗但必须有边界计算 |

为避免跨工作区高频切换额外点击，保留一行 **无边框、中性背景** 的 Timer / Drill / EI 直接链接（每个44px触控高），放workspace标题下。Timer 原WorkspaceSwitcher里重复的三项删除，名称行只承担应用名称、折叠；账号菜单统一承接设置。若父计划选择完全Linear式workspace下拉，应明确把跨应用由一次变两次列为取舍，而不能宣称效率无损。本建议优先保留当前单击效率。

### 4.3 色彩与状态

- Sidebar/main 色差仅 neutral：dark sidebar `#141414`、main `#181818`；light sidebar `#f5f5f5`、main `#ffffff`。最终引用父设计系统Token，禁止页面写死这些值。
- Default：secondary text；hover：neutral hover background；active：neutral selected background + primary text + 550字重；no colored border；icon同文字currentColor。
- Accent不染 sidebar、主区、active整行；允许焦点环和菜单check局部使用。真实未读/状态badge保留语义，但现仓库没有这类导航未读业务，不新增假计数。
- 外侧分割仅在需区分同色主区时使用1px subtle；推荐以背景差异为主。组间不画线。
- 删除 coverage常驻大块：数字仍在 Progress 中已有数据；可将来源致谢放设置“题库来源”实际只读组。此是展示迁移，不删除来源信息。
- 不新增按钮阴影；popover允许唯一轻阴影和subtle border定义浮层边界；普通行无shadow。

### 4.4 交互/焦点

- 顶部header导航toggle占正常文档流，杜绝悬浮遮挡与每页手动padding补偿。
- Drawer打开：记住触发器，锁body背景滚动，main inert，焦点移到当前nav；Escape/点击backdrop/成功导航关闭并恢复触发焦点；关闭drawer自身hidden或inert，不能只translate。
- 屏幕旋转：到desktop收起modal状态并解除inert/scroll lock；在同一次resize更新more位置；不可留下backdrop。
- Collapse不影响路由、题目进度、已保存state；重开按钮位于header内而不是覆盖题图。
- keyboard在输入、textarea、contenteditable内不劫持全局快捷键。暂不新增 `[` 快捷键以免数学编辑冲突。
- outside pointer关闭popover；Escape只关闭顶层popup，不同时退出Question fullscreen；关闭后焦点回触发器。
- Nav selected由统一函数做业务判断：Question读取`from`；collection读取`collection`；papers以route族判断；Timer session detail保留sessions上下文；避免selected-heatmap和more同时成为当前页面。

## 5. 可执行任务及验收

| ID | 需求 | 真实文件/新增文件 | 动作 | 自动化/截图证据 |
|---|---|---|---|---|
| NAV-01 | R03 R04 | drill/styles.css；Timer SidebarItem/styles | 删除伪元素圆点与marker DOM；引入真实icon slot | DOM无marker；computed `::before`无content；导航和Markdown正文并列截图证明正文bullet仍正常 |
| NAV-02 | R04 R16 | shared/ui/navigation/*（新）、两个App、Timer导航组件 | 共用shell/NavigationItem；各app传route data | 三空间active route参数测试；所有旧URL可访问；截图字号/行高一致 |
| NAV-03 | R04 R14 | Drill App.vue + main.ts仅导航接线 | 主入口顺序、more清单、context active；保留default redirect | selected/core→question→back、insight→question→back、papers detail/diagnostic queue高亮测试 |
| NAV-04 | R04 R15 | shared AppSidebar + 两个global CSS + PWA navigation.js只回归 | header正常流toggle、drawer focus/inert/scroll lock、安全区 | 375/390/430、768x1024、1024x768、1366x768；旋转；键盘Tab到页尾；无2个launcher |
| NAV-05 | R05 R08 | 两个App、SidebarPreferences、Settings页面 | 两枚主题符号撤出；账号菜单接Appearance设置；来源信息迁移 | Settings入口一致、原来源仍可查、logout请求未改 |
| NAV-06 | R02 R06 R07 | shared tokens + 两个样式 | 中性sidebar/hover/selected与accent解耦 | Light/Dark×Blue/Lime/Monochrome，采样global背景RGB通道差≤2；active无彩色border |

针对 R03 的验收不要使用全站禁止 `::before`；很多合法业务组件需要伪元素。测试精确定位导航元素，不影响题干与Note中的Markdown列表。

## 6. 风险和未知项

- 本次未登录 Linear 产品；已观察官方2026图像和文档，未测试其实际hover/keyboard行为。对应本项目行为是设计建议，不是Linear实测事实。
- 用户提到的截图未在当前子任务中作为可见附件提供；不能宣称逐像素对比截图。当前问题根因来自真实代码。
- iPad与iPhone真实Safari物理设备需后续人工QA；Chromium viewport模拟仅能证明布局和JS交互，不证明真实safe-area/软键盘行为。
- 240/224/288px、36/44px等不是Linear精确尺寸，必须在Master中标注本项目规范。
- 共享组件引入不能把Element Plus从Timer整包带进Drill；利用已安装icon组件或小SVG原语，构建产物比较依赖体积。
- Question CSS目前大量共享选择器，导航重构必须限定`.app-shell`/sidebar/header；全屏工作台结构保持；任何修改均有旧版截图作基线。
