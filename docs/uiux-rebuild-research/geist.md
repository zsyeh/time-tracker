> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Vercel / Geist：公开规范、源码与本项目落地决策

研究日期：2026-11-12。只读研究与技术验证，未修改业务代码、提交或部署。本文源码均为实际读取；明确区分 Geist 文档、Web Interface Guidelines、Next.js DevTools 公开实现。**未访问 Vercel Dashboard 私有源码。**

## 1. 官方资料摘要（按来源限制简述）

| 编号 | 证据 | 确认的事实与适用范围 |
|---|---|---|
| G01 | [Geist Introduction](https://vercel.com/geist/introduction) | 官方设计系统文档提供基础规则及React组件文档；不意味着需要本项目采用React。 |
| G02 | [Colors](https://vercel.com/geist/colors) | 背景、组件填充、边框、高对比填充、文字/图标是不同角色；默认用实色灰，透明灰用于需要透底的场景。边界应只画一次。 |
| G03 | [Typography](https://vercel.com/geist/typography) | 字号、行高、字重、字距成套定义；14px是常见正文/菜单规格，数字比较采用tabular。文档包含营销大标题，本项目不使用那部分。 |
| G04 | [Button](https://vercel.com/geist/button) | 操作和导航语义分开；Primary/Secondary/Tertiary、loading、disabled有独立状态；icon-only要求可访问名称。无需全部outline。 |
| G05 | [Input](https://vercel.com/geist/input) | 区分自由文本、Textarea、Combobox；label与id/说明有关联；搜索有明确范围和清除行为。 |
| G06 | [Select](https://vercel.com/geist/select) | 短固定选项适用Select；列表很长且需要文字检索用Combobox；多选不伪装单选。 |
| G07 | [Menu](https://vercel.com/geist/menu) | 点击打开，窗口边界自适应；方向键、Home/End、键入定位、Escape、焦点返回构成完整交互。 |
| G08 | [Materials](https://vercel.com/geist/materials) | 普通内容与浮层采用不同层级；尽量选择足够表达层次的最低elevation，不把每个块都抬起。 |
| G09 | [Empty State](https://vercel.com/geist/empty-state) | 无结果、首次使用、权限失败、请求错误不是同一状态；提供实际下一步，而不是统一空白占位。 |
| G10 | [Skeleton](https://vercel.com/geist/skeleton) | 已知布局的异步内容可保持尺寸；骨架不是空结果；loading区域标记busy，尊重reduced-motion。 |
| G11 | [Search Input](https://vercel.com/geist/search-input) | 内联搜索把输入、清除和loading整合，不另叠多张卡片。 |
| G12 | [Web Interface Guidelines](https://vercel.com/design/guidelines) | 键盘操作、可见焦点、触控目标、URL状态、返回滚动、safe-area、减少布局跳动是适用于本项目的质量要求。 |

以上是简要事实。以下落地尺寸、文件组织、组件API与验收规则是本项目工程判断，不是将Vercel规范逐段改写或复制。

## 2. 真实公开源码、版本和许可证

### S01：官方 agent-skills

仓库：[vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)。读取时HEAD `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62`。

实读文件：[skills/web-design-guidelines/SKILL.md](https://github.com/vercel-labs/agent-skills/blob/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/web-design-guidelines/SKILL.md)。它是审核流程包装，指向另一仓库的规则，不含Geist Button/Menu实现。GitHub API的license字段为null，完整tree未发现LICENSE；故**仅引用研究，不复制进项目、不宣称MIT**。读取它是研究对象，不是在本项目安装或启用第三方skill。

### S02：Web Interface Guidelines 的可版本化规则

仓库：[vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)，MIT；HEAD `434b7f91364665f2f733b310ec54809bf8f37937`。

实读文件：[command.md](https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md)。具体可复用的是审核维度：语义元素、focus-visible、label、tabular-nums、URL条件、safe-area、theme-color、长内容和min-width。规则存在针对React/Tailwind的示例，应改写为本项目Vue/Vite测试，而非新增React依赖。

### S03：Next.js DevTools公开UI（不是Dashboard）

仓库：[vercel/next.js](https://github.com/vercel/next.js)，MIT；读取canary HEAD `1430e15cd572b2e6a468af11792cfd3127a29d5b`。

实读文件：

- [styles/colors.css](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/styles/colors.css)：`:host`中声明白/浅灰背景、Gray十阶与单独语义色阶；ANSI语法色以别名映射到有语义的颜色。
- [styles/dark-theme.css](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/styles/dark-theme.css)：明确dark类和系统偏好分支；背景为中性黑，灰阶为RGB相等的灰；彩色语法/诊断色独立。
- [styles/default-theme.css](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/styles/default-theme.css)：字体栈、focus ring、radius、menu shadow等集中声明。
- [menu/dev-overlay-menu.tsx](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/menu/dev-overlay-menu.tsx)：selectedIndex、`data-selected`、`role=menuitem`、roving tabindex、方向/Home/End键、outside/Escape关闭、中性背景及单层边界。
- [components/dialog/dialog.tsx](https://github.com/vercel/next.js/blob/1430e15cd572b2e6a468af11792cfd3127a29d5b/packages/next/src/next-devtools/dev-overlay/components/dialog/dialog.tsx)：labelledby/describedby、Escape和关闭后焦点恢复；还含针对ShadowRoot和Safari的特定处理。

**不能盲目照搬**：此DevTools menu在keydown入口统一preventDefault，本项目必须仅消费已处理按键，让Tab有明确退出行为；该dialog文件的注释写focus trap，但该文件可见实现主要是初始焦点/恢复，不能把注释当成完整焦点循环证明。源码还包含彩色instant-guidance边界和复杂弹簧token，均不适用于用户要求的低噪声学习UI。文档Menu支持typeahead，不代表上述DevTools文件已实现它；两者证据要分开。

### S04：Geist字体

[vercel/geist-font](https://github.com/vercel/geist-font)，HEAD `ef2597cfc42f4797676df105517ccc0a1cfa6569`，OFL-1.1。已核验仓库元信息；本任务不增加字体依赖。既有系统中英文字体栈更适合当前触控学习工具，避免为“像Vercel”新增下载。

## 3. 当前项目审计

### 3.1 技术栈与重复定义

`frontend/package.json`确认Vue `^3.5.13`、Vue Router `^4.6.4`、Element Plus `^2.8.8`、icons-vue `^2.3.1`、Vite `^5.4.11`、ECharts `^6.1.0`。版本范围不是锁文件实际安装版本，最终实施Phase0应记录lock/install版本。

`frontend/src/main.ts`先加载`elementStyles`、注册`elementComponents`，再本地`styles.css`；Drill `frontend/drill/src/main.ts`不注册Element Plus应用。两者是两个Vite入口；共享tokens可以直接import，但不允许为复用样式把Timer整个App或Element Plus注册引入Drill。

真实重复位置：

- `frontend/src/styles.css:1–105`：Timer root neutrals、accent、语义色、空间、radius、Element变量和data-theme品牌映射。
- `frontend/drill/src/styles.css:1–69`：Drill另一套root/light token；`:80–81` EI再次覆盖accent。
- `frontend/src/styles.css:765–789`：Element Plus大批`!important`全局样式；标签9px、下拉项10px、label11px。
- `frontend/src/lib/uiPreferences.ts`与`frontend/drill/src/lib/uiPreferences.ts`：重复Light/Dark存储、cookie、apply逻辑；无System。
- `frontend/src/views/SettingsView.vue:17,47,88–91,347–355`：品牌theme独立localStorage，HTML`data-theme`；与颜色模式分离但仅Timer生效，且带品牌装饰。
- `frontend/index.html`与`frontend/drill/index.html`：各自早期主题脚本；`meta theme-color`及背景值不同。

### 3.2 对比度只读技术验证

用标准sRGB相对亮度公式计算**原始颜色pair**（未声称截图实测）：

| 当前值 | 对白背景#fff | 影响 |
|---|---:|---|
| Timer light tertiary `#85858f` | 3.65:1 | 12–13px说明文字不足4.5:1 |
| Timer apple accent `#d8d8dc` | 1.42:1 | 用作浅色模式链接不合格 |
| Timer meituan accent `#d6b442` | 2.01:1 | 黄色不能同时担当浅色文字色 |
| Timer bilibili accent `#e77fa0` | 2.64:1 | 同上 |
| Timer coolapk accent `#40b979` | 2.49:1 | 同上 |
| Timer violet accent `#8b7cf6` | 3.33:1 | 普通文字不足4.5:1 |
| Drill tertiary `#737b88` 对`#181b20` | 4.04:1 | 小字也需调亮或提升语义文字token |

这些计算解释为什么需要`accent-solid`、`accent-ink`、`accent-on-solid`，不能把一个`--accent`同时用于背景、链接、focus和小字。

## 4. 推荐共享Token组织（主Agent唯一所有者）

新增文件建议：

1. `frontend/shared/design/primitives.css`：基础neutral、10种accent色盘、固定spacing/radius/typography；仅此处允许基础十六进制色值。
2. `frontend/shared/design/semantic.css`：Appearance下surface/text/border/focus/status映射。
3. `frontend/shared/design/components.css`：control、menu、nav、setting-row等少量组件token，不放页面布局。
4. `frontend/shared/design/compatibility.css`：现有`--bg-app/--text-primary/--accent/...`映射别名，迁移期间保证Question不因变量丢失退化。
5. `frontend/src/styles/element-adapter.css`：仅Timer入口加载，桥接`--el-*`及少量Element结构例外。
6. `frontend/shared/appearance.ts`：数据模型、解析、事件、持久化；语言字典继续各app维护，不为共享Appearance重写i18n。

这是新增路径，应在Master标记“新增”。现有CSS的布局页规则逐步迁到各页scoped样式，不一次全搬。两套root颜色定义删除后只import同一token入口；绝不在两个CSS文件尾部再加第三套覆盖。

推荐命名层级示例：`--neutral-0`基础色 → `--surface-canvas`语义 → `--nav-item-selected-bg`组件。组件不直接取`--neutral-200`或某种Blue palette；通过语义层才能保持主题与contrast正确。

Accent运行映射只由`html[data-accent]`选择，Appearance只由`data-color-scheme=light|dark`解析；背景token不引用任何Accent。状态色独立`--status-mastered-ink/fill`、`--status-review-ink/fill`、`--status-danger-ink/fill`，禁止Theme覆盖掌握/复习意义。

最少Accent契约：`--accent-solid`（按钮实填）、`--accent-solid-hover`、`--accent-solid-pressed`、`--accent-on-solid`（内部文字）、`--accent-ink`（链接/局部强调）、`--accent-soft`（小面积选择背景）、`--focus-color`。十个选项Light/Dark各有完整映射。普通导航active仍用neutral，不能依靠accent-soft染整栏。

### 4.1 兼容别名要逐个审计

Timer当前`--green:var(--accent)`是公式workspace兼容别名，Drill当前`--green:var(--success)`是成功意义；**不能在共享文件直接统一这两个不同含义**。保留在各app compatibility scope，逐个查消费者后改成语义变量，最后删除。`--muted`在Timer指secondary、Drill指tertiary，同样不能机械替换。

### 4.2 CSS落地顺序

- 先建立token与snapshot/contrast测试，接入两个入口且保留兼容别名；先不同时改Question布局。
- 抽走重复root、light、EI强制accent、Timer品牌theme视觉规则；迁移旧preference到新accent id。
- Element适配优先使用`--el-color-primary`/text/fill变量，删除已被变量替代的重复`!important`；遇到结构样式必须在单一adapter中显式保留，不制造多层覆盖。
- `.el-button--primary`文字映射到`--accent-on-solid`；链接映射`--accent-ink`；disabled需独立token，不能全局opacity同时降低文本对比到不可读。
- 原生input/select、Element input采用同一尺寸/文字token；移动输入至少16px并保留浏览器缩放。
- 不直接引入全站cascade layers：当前CSS是unlayered，新增layer会被旧规则压制。若采用layer，须在一项独立任务中将两入口所有相关样式归层，不能只给新增token套layer。

## 5. 本项目基础控件决策

| 控件 | 推荐视觉与行为 | 适用现有动作 |
|---|---|---|
| Primary | 每个任务区最多一个高强调实填；Accent solid+on-solid；不画彩色outline | 保存设置、开始练习、明确当前提交主动作 |
| Secondary | neutral轻填充，无彩色边框；只有独立边界有价值时1pxneutral | Filter、日期、恢复上一题、取消 |
| Plain | 透明背景；hover neutral；文字正常；focus独立 | 收起诊断、查看历史、复制辅助内容 |
| IconButton | 16–18px单色SVG；44px触控target；label说明动作+对象 | 收藏、全屏、复制题图、更多 |
| MenuTrigger | Plain或Secondary +一致chevron；当前值不变成badge套badge | Sort、Appearance、账号菜单 |
| Segmented | 同一choice语义、小量互斥选项；整体一容器，选中项neutral底和weight | 7/14/30日，状态短选项；不代替所有filters |
| Toggle / Checkbox | 真实`input`或完善role；整行label命中；check除颜色还表达状态 | 收藏筛选、多诊断选择、开关偏好 |
| Select / Pop-up | 少量固定值优先原生select（整行label）；复杂搜索列表用Combobox | Appearance三选、排序、知识点多项 |
| Destructive | 默认plain危险文字，真正确认动作才danger实填 | 撤销分享、删除；原业务确认链保留 |

不要把Geist的React `typeName`属性带进Vue。项目Button API建议`variant`控制视觉，`type='button|submit|reset'`保持HTML语义，`loading`状态保留可见标签与宽度并阻止重复提交；不自动修改掌握/复习动作的状态机。

## 6. Menu、Loading、Empty的工程验收

### Menu

共享`Menu.vue`需要：trigger aria-haspopup/expanded/controls；打开聚焦选中或首个可用项；上下循环、Home/End、Enter/Space、Escape返回；typeahead本地label匹配；Tab关闭并自然继续焦点，不能preventDefault所有key；disabled不可激活；outside关闭；滚动容器内active item可见；移动视窗剩余高度不足转Sheet。Popover内是form/filter时不套role=menu，而用dialog/form及正常Tab顺序。

窗口定位必须使用visualViewport偏移/高度并考虑safe-area；每次resize/orientationchange更新；desktop min8px gutter；手机search聚焦不自动把popover挤出视窗。

### Loading

- 初次页面加载采用与最终列表行/图表槽尺寸一致的局部骨架；等待250ms后才显示；不要把整个app盖loading遮罩用于每次搜索。
- 搜索刷新保留旧结果但标记busy，响应回来一次替换；过时响应不能写回。加载提示不抢焦点。
- 不为满足“最小显示时长”故意延迟结果可用；可以让简短状态指示稳定显示，数据一到即展示。
- loading区域`aria-busy`；结果数量是简短`aria-live=polite`；骨架本身aria-hidden；减少动画偏好关闭pulse。

### Empty

- 空查询展示默认目录；不能显示“搜索失败”。
- 0结果显示查询/有效filter摘要；主行动为清除筛选；若只有query可改词，给实际已计算建议。
- 网络错误保留query/filter和旧结果，显示重试；403不渲染私人题库摘要；无学习记录显示真实起步入口。
- 图表无数据不给假曲线、随机数字、装饰插图；保留轴标题或简明说明即可。

## 7. 可验证完成条件

- `R01/R12`：代表页面按钮列出动作→variant映射；无分类彩色outline；按钮label/width在loading中不消失。
- `R02/R13`：浅色截图同级内容以排版分组，卡片边框不嵌套两层；分隔只画一次；不以shadow替代所有border。
- `R06/R07`：Light/Dark×10 accents自动采样canvas/sidebar/surfaceRGB恒定；每个accent的ink文字≥4.5:1、on-solid≥4.5:1；focus与邻接背景≥3:1；yellow/lime/mono必须测试。
- `R15`：375/390/430手机与iPad转向，focus不被sticky遮挡；所有input可缩放，移动字号≥16px；menu边界不裁切。
- `R16`：两个入口只import一份token定义；Element adapter只在Timer编译；Drill构建依赖无全量Element Plus扩张。
- 对现有Question截图进行before/after回归；共享token调整允许表面变化，不允许图像容器尺寸、全屏分栏、提交位置漂移。

## 8. 不照搬项与证据缺口

- Geist React库内部实现并未全面公开；文档上的“Show code”多数为使用示例。本研究不把它写成生产Dashboard组件源码。
- Web guidelines给出的一些框架特定方案（React Suspense、nuqs、uncontrolled inputs）不应用于此Vue工程；采用现有Vue Router/reactivity。
- 公开文档某处给`maximum-scale=1`作为移动输入变通，但同页又要求不禁zoom，且源码规则列为反模式。本项目明确只采用16px输入，**不禁缩放**。
- 不执行“>50项一律虚拟化”的机械规则：热力图依赖稳定位置、滚动恢复、键盘定位；先profiling，必要时按题册渲染优化，不能为套用规则破坏矩阵。
- 本次没有对Vercel登录Dashboard做交互实测；交互依据是官方文档和上述明确标注的公开DevTools源码。
