> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Apple HIG / SwiftUI 研究与 Drill/EI 施工建议

研究时间：2026-11-12。审计工作树：`/home/eh/precision-study-ui-20261111`。只读源码及公开资料；未修改业务代码、未执行测试、未提交、未部署。用户消息中未提供可读取的 ChatGPT/iPad 截图附件，因此不声称进行了用户截图对照；以下“当前问题”来自真实代码。所有 Web 像素、断点、组件 API 均为本项目工程决策，不是 Apple 私有实现或 Apple 官方尺寸规范。

## 1. 官方证据及采用边界

以下官方页面实际通过 web 工具读取。Apple HIG HTML 部分为 JS 壳，但页面提供官方 `.md` 内容，已读取相应正文。每条归纳只保留少量原则，后续规格为针对本项目自主设计。

| ID | 实际读取的官方来源 | 证据类别与有限归纳 | 本项目取舍 |
|---|---|---|---|
| AP-S01 | [Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars) / [官方 Markdown](https://developer.apple.com/design/human-interface-guidelines/sidebars.md) | 官方 HIG；2026-06-08 更新说明可见。建议浅层分组、合理图标、可隐藏 sidebar，随可用宽度自适应。 | sidebar 具体视觉以 Linear 调研为主；采用分组、折叠、宽度驱动规则。 |
| AP-S02 | [Lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables?changes=_5) | 官方 HIG。列表适合文本扫描；导航行持续高亮，选项行可用勾选标识；层级使用 disclosure。 | 设置用组内行；诊断用可选行；不复制 Apple 资产。 |
| AP-S03 | [Settings](https://developer.apple.com/design/human-interface-guidelines/settings.md) | 官方 HIG。通用且低频的偏好集中到设置，任务选项留在任务上下文，减少无用设置。 | Theme/Accent/语言集中；翻题、自动复制仍可就地修改。 |
| AP-S04 | [Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons.md) | 官方 HIG。样式、内容、语义角色分离，主要行动更突出，所有自定义按钮应有按压反馈；一般触控命中区域至少 44×44 pt。 | Web 使用真实 44 CSS px 触控控件，保留密度通过布局完成；44 CSS px 是本项目规格，不称与 pt 完全等价。 |
| AP-S05 | [Menus](https://developer.apple.com/design/human-interface-guidelines/menus.md) | 官方 HIG。命令标签清楚、相关功能分组，优先高频项，图标有意义且组内一致，少用多层菜单。 | 收藏/复习/作答保持可见；低频导出和勘误按明确规则收纳。 |
| AP-S06 | [Pop-up buttons](https://developer.apple.com/design/human-interface-guidelines/pop-up-buttons.md) | 官方 HIG。单选菜单呈现当前值；选项集合小且稳定时可在设置上下文选择。 | Appearance 用三项单选；多选诊断绝不套成单选 pop-up。 |
| AP-S07 | [Popovers](https://developer.apple.com/design/human-interface-guidelines/popovers.md) | 官方 HIG。临时相关操作可放 popover；多选时不自动关闭；宽屏适用，紧凑窗口改 sheet；意外 dismiss 不应丢工作。 | 筛选即时生效，外点仅关闭；手机 sheet 同一状态模型。 |
| AP-S08 | [Sheets](https://developer.apple.com/design/human-interface-guidelines/sheets.md) | 官方 HIG。用于有界任务；一次一个 sheet；退出与保存语义要清楚。 | 筛选 sheet 即时应用，无草稿 Apply 事务；使用“关闭”与“清除筛选”，不误称“取消”已生效选择。 |
| AP-S09 | [Search fields](https://developer.apple.com/design/human-interface-guidelines/search-fields.md) | 官方 HIG。明确搜索范围，可随输入更新、提供建议、相关性优先，支持范围与条件细化。 | 搜索保持题库页顶部可见，避免将高频搜索藏到菜单；过滤其它维度。 |
| AP-S10 | [Segmented controls](https://developer.apple.com/design/human-interface-guidelines/segmented-controls.md) | 官方 HIG。用于少量紧密相关且同语义的选择；避免将操作与选择混合。 | 仅适合3项 Appearance、少量视图/周期；8项多选诊断不用 segmented。 |
| AP-S11 | [Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars.md) | 官方 HIG。行动按任务优先级组织、窄屏明确溢出策略、减少着色装饰。 | 做题主操作始终直接可达，次要工具中性无边框；工具栏不替代全局导航。 |
| AP-S12 | [Layout](https://developer.apple.com/design/human-interface-guidelines/layout.md) | 官方 HIG。用对齐、分组、渐进披露建立层级，考虑窗口缩放、旋转、文字变化和安全区。 | 按可用内容宽度断点，禁止设备品牌嗅探或仅 orientation 判定。 |
| AP-S13 | [Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode) | 官方 HIG。通常遵循系统并保证暗色可读性；其避免应用自定义外观偏好的建议与本用户 R05 不同。 | 明确采用用户 R05：System/Light/Dark，默认 System；不伪称该三项结构由 HIG 强制。 |
| AP-S14 | [SwiftUI insetGrouped](https://developer.apple.com/documentation/swiftui/liststyle/insetgrouped.md) | 公开 API 文档，非 SwiftUI 内部源码。组头、条目、组尾整体构成分组视觉。 | 一组设置一个自然容器，行间内缩细线，不给每行独立卡片。 |
| AP-S15 | [SwiftUI NavigationSplitView](https://developer.apple.com/documentation/swiftui/navigationsplitview.md) | 公开 API 文档。主从分栏在紧凑宽度折成导航栈，前列选择控制后列。 | 设置窄屏进入详情后保留返回、选中类别和滚动；不堆叠两个完整导航列。 |
| AP-S16 | [SwiftUI preferredColorScheme](https://developer.apple.com/documentation/SwiftUI/View/preferredColorScheme%28_%3A%29) | 公开 API 文档。空偏好与显式亮/暗区分。 | Web 持久化偏好与 resolved scheme 分离；System 不是“此刻系统是深色所以存 dark”。 |
| AP-S17 | [SwiftUI safeAreaInset](https://developer.apple.com/documentation/swiftui/view/safeareainset%28edge%3Aalignment%3Aspacing%3Acontent%3A%29-6gwby.md) | 公开 API 文档。固定邻接内容占据空间时主内容相应 inset。 | Web 固定操作区必须实际预留等高空间，不能只盖在内容上。 |
| AP-S18 | [Build a UIKit app with the new design, WWDC25](https://developer.apple.com/videos/play/wwdc2025/284/) | 官方 iOS/iPadOS 26 工程演示，公开 transcript 可读；覆盖 split/sidebar/search/control 分组。 | 理解新系统对内容和操作的组织，明确不采用其玻璃材质。 |
| AP-S19 | [Build a SwiftUI app with the new design, WWDC25](https://developer.apple.com/videos/play/wwdc2025/323/) | 官方公开工程演示，展示不同窗口下的结构适配。 | 保留既有 Vue 栈；不引入 SwiftUI 或模拟整套 Apple 框架。 |

**重要研究边界**：iPadOS 26 的官方设计确有 Liquid Glass、浮动控件等强调，用户 R06 与质量约束明确要求中性色、不增加玻璃拟态。施工采用语义和布局原则，拒绝照搬材质与大圆角。Apple 的原生设置通常显得协调，是因为组、行、当前值、选择标识各有稳定职责，控件层级与信息层级一致；此解释是对上述原则的本项目归纳，不是声称读取 Apple Settings 私有源码。

## 2. 真实代码审计

| 文件与定位 | 事实 | 问题或保护要求 |
|---|---|---|
| `frontend/drill/src/views/QuestionView.vue:31` | A/B1/B2/B3/C1/C2/C3/D 共8选项，中文标签明确。 | 不存在 `StructuredDiagnosisEditor.vue`；新组件须显式标记为新增，不可声称旧路径。 |
| `QuestionView.vue:970` | `toggleError` 多选；首选自动 primary；删除 primary 时变为剩余首项或 null。 | 必须逐项保持，不可将8项改为 radio/segmented 或排序 selectedErrors。 |
| `QuestionView.vue:980–1027` | payload含 error_codes/primary_error/K/M/E/used_hint/viewed_answer/is_independent；历史修改550ms PATCH，草稿随作答保存。 | 只抽视图，副作用与计时/保存仍归父级；不得产生新的自动提交。 |
| `QuestionView.vue:1428–1456` | 诊断、有无提示、主要原因 select、K/M/E select、历史都内嵌。 | 可用受控 `DiagnosisSelector` 与组内 selection rows；保持原点击次数与折叠可达性。 |
| `QuestionView.vue:1541–1598` | 通用诊断控件有边框；黄色 active border；primary黄色内阴影；后续 compact规则覆写早期规则，9–10px多。 | 删除旧块中的被替代规则，禁止再加第3套覆盖；使用中性选择底色+勾选/文字，正文13–14px。 |
| `QuestionView.vue:1356–1361` / `styles.css:266–270` | 收藏、复制分享、加入下次复习、勘误四按钮；选中使用不同彩边。 | 业务方法不变，改为明确工具栏语义；收藏与review_later不是作答状态，不能混合。 |
| `QuestionView.vue:1473` | 掌握、待复习、更多(撤销/重置)；标签依auto-next偏好变化。 | 掌握和待复习都始终一击；“更多”保持现有低频危险行动，不新加确认改变频次。 |
| `QuestionView.vue:1491–1497` | 前后翻题模式、掌握后切题、待复习后切题、翻题复制链接/题图。 | 属任务偏好，应在题目页维持快速访问；可在设置 Preferences 镜像同一 store，禁止副本状态。 |
| `frontend/drill/src/components/ReaderPracticeActions.vue` | 5按钮previous/next/mastered/review/answer，aria-label及pressed，32×32px，有语义SVG颜色；第二style块独立定义answer active。 | 现有行为成熟；可统一成无边框图标按钮和44px命中区，保留5动作次序、事件值及前后目标语义色；禁塞入更多菜单。 |
| `frontend/drill/src/lib/readerPractice.ts` | 明确联合类型和可用/忙碌/自动翻题状态。 | 不改action union，不合并事件。 |
| `frontend/drill/src/components/FullscreenReader.vue:142–175` | 原生dialog top layer；100dvh、安全区、独立scroll、zoom；小屏隐藏title及部分zoom。 | 不能改open/restore/zoom/scroll算法；只允许受控表面样式；不得覆盖dialog top layer。 |
| `frontend/drill/src/styles.css:742–820` | Question landscape存在独立两栏/视口高度策略及9px诊断覆盖。 | 全局组件CSS迁移要去掉相应已废规则，不能扩大字号后仍被末尾9px压回去。 |
| `frontend/drill/src/views/PracticeView.vue:67–80` | 当前查询q长度>=2才发送；`searchChanged`对长度1直接return。 | 这是中文单字搜索前端障碍；须与后端搜索施工同步解除，不仅换框。 |
| `PracticeView.vue:95–123` | 已有AbortController、requestSequence、缓存；400ms防抖。 | 保留并升级IME/单字/URL语义，不需重新发明取消机制。 |
| `PracticeView.vue:51–62,89,151` | 本地候选为topic.path/document.title.includes；@mousedown选候选，blur延迟150ms。 | 缺键盘候选导航与触屏明确pointer交互；新SearchInput需combobox语义。 |
| `PracticeView.vue:225–241` / `styles.css:182–195` | taxonomy source卡片+搜索/题册/知识点/未做面板+ExamTypeControls三层工具。 | 收敛为search+Filter+sort；保留已选摘要与结果计数。 |
| `frontend/drill/src/components/ExamTypeControls.vue` | 新版本题型统计已是neutral row，无逐卡彩色border；但active accent-muted，全局分色inset bottom shadow。 | 不重复报告旧彩色边框仍存在；将类型筛选能力移入统一Filter，类型分色继续是独立真实偏好。 |
| `frontend/src/views/SettingsView.vue:308–436` | 现有设置有General/Appearance/Instance/Organization/Privacy/Access/Invites/Data/Shortcuts；superuser/admin门禁。 | 内容齐全不能用新模板删功能；组内行只改布局，原表单及mutation函数不动。 |
| `SettingsView.vue:17,46–53,91,347–357` | 品牌主题六项`learning-os-theme`；Appearance只有dark/light；主题与颜色混杂。 | 以Appearance/Accent两行替换品牌主题矩形列表。 |
| `frontend/drill/src/App.vue:227–231` | 底部◐/☀按钮及语言select。 | 删除此显眼展示，将入口统一到账号/设置；不只用CSS hide残留可聚焦控件。 |

现有局部测试可复用：`components/ReaderPracticeActions.test.ts`、`components/FullscreenReader.test.ts`、`components/NoteVisibility.test.ts`、`components/OriginalAnswer.test.ts`、`lib/questionNavigation.test.ts`、`lib/sourcePractice.test.ts`。目前无 `QuestionView.test.ts` 或 `PracticeView.test.ts`，新增测试必须标记新增文件。

## 3. 推荐工程决策（供主文档映射）

### AP-D01 — 语义按钮体系（R01/R12/R14）

- Primary：每个上下文最多1个高强调外观。例如题库“继续练习”及题目“掌握并下一题”。使用共享accent填充+经过对比度验证的on-accent；绿色不再代表所有普通按钮。
- Secondary：中性填充，无彩色边框。题目“待复习并下一题”仍可见，带warning语义的小图标/短状态文字；不能将warning覆写为accent。
- Plain：透明背景、文本或图标，hover/pressed用neutral surface；适用于展开诊断、历史、复制、清除筛选、次要链接。
- Icon：仅含明确图形，必有aria-label、title；桌面视觉图形16/18/20px，触屏实际44px命中，不做不可检查的负边距命中伪层。
- Menu trigger：Plain/Secondary + chevron/ellipsis，用`aria-expanded`和`aria-controls`；下拉菜单与命令按钮不混用。
- Toggle/Checkbox：持久二态用checkbox或switch；整行label命中。收藏可用icon button aria-pressed；多个诊断是checkbox语义。
- Segmented：仅同语义少量互斥选择，单一group底色，不让每段成为独立边框矩形。
- Destructive：通常在菜单内红字+明确标签；危险确认沿用现有协议，不能为了样式移除。
- Selection Row：整行中性hover/selected + checkmark；不让彩色border表示选中。错误/焦点可有语义border例外。

### AP-D02 — 受控 DiagnosisSelector（R11/R12/R14）

新增 `frontend/drill/src/components/DiagnosisSelector.vue`，将原 `error-picker` 视觉模板迁移；该组件不调用API、不碰计时器、不持久化，不包含Note。

```ts
interface DiagnosisSelectorProps {
  options: ReadonlyArray<{ code: ErrorCode; label: string; group: string }>;
  selected: ReadonlyArray<ErrorCode>;
  primary: ErrorCode | null;
  disabled?: boolean;
}
// emits: toggle(code: ErrorCode), update:primary(code: ErrorCode | null)
```

- 父级保留`toggleError`、`diagnosisChanged`、`diagnosisPayload`以及所有保存/顺序守卫。`@toggle="toggleError"`；主要原因select依旧绑定`primaryError`。
- eight rows固定顺序A/B1/B2/B3/C1/C2/C3/D，所有选项一次展开后直接看到，不能藏在分组菜单。每项完整中文名称，无只有字母的神秘缩写。
- 组件容器宽度>=400px时两列×四行，按现有DOM行优先顺序；<400px时两列×四行仍可用每格最小140px、允许两行标签；<304px改一列八行。使用`container-type:inline-size`或父class；不得拿viewport宽度推断右侧窄面板宽度。
- 每项真实命中高度44px，文字13px line-height1.35，代码13px tabular；内间距8px；两列间12px；row自身无border和独立卡片radius，选中neutral surface。checkmark用accent；primary增加“主因”12px文本，不能只靠黄色竖线。
- 使用原生`<input type="checkbox">`与label，或button role=checkbox aria-checked；优先原生input以保留Space语义。不得给整个容器role=listbox，因为其内部还有primary select且这是表单多选。
- 提示使用独立toggle行，文本“本轮不计为独立作答”保留。`viewed_answer`不可由用户反选“没看过”规避原语义。
- K/M/E保留三个选择器，改同一group中的三行“名称→当前值”，每行44px；不默认折叠以免新增操作。右侧窄面板不是适合三个9px selects并排的环境。
- “完整历史”“收起诊断”使用PlainAction；状态文案12px，aria-live=polite；展开history保持每次attempt独立一行及时间，不合并同题。

**验收AP-T01**：8选项可单击切换；A→B1→取消A时primary为B1；无选项primary=null；历史修订仍550ms单次PATCH；新作答选诊断不立即POST；切题后旧PATCH不能写新题；K/M/E、hint、viewedAnswer payload完全与基线一致。

### AP-D03 — 做题操作层级（R12/R14/R15）

| 当前动作 | 新呈现 | 点击与行为约束 |
|---|---|---|
| 掌握/掌握并下一题 | 唯一Primary按钮；保留success图标或状态文字 | 仍直接record('correct')；不新增确认；auto-next保持 |
| 待复习/待复习并下一题 | Secondary中性按钮+warning小图标 | 仍直接record('review')，同屏一击 |
| 下一题/上一题 | Plain文字或Icon | 不记录作答，nextMode语义保持 |
| 收藏 | Plain icon+短标签，可aria-pressed | saveUserState(is_favorite)保持 |
| 加入下次复习 | Plain toggle+短标签 | review_later不是question.state，保持 |
| 复制分享 | Plain icon+短标签 | 用户手势→剪贴板保持同步发起，禁止搬进异步自动链 |
| 提交勘误 | >=768px Plain直接；手机更多菜单第1项 | 原展开/提交表单保留；记录此低频项额外一步是明确取舍，不涉及核心做题步骤 |
| 复制题图/全屏 | 就题图toolbar的Icon/Plain | 保持原full screen开关、clipboard降级 |
| 历史/诊断展开 | 同一heading尾部Plain | 直接一次点击，不进更多菜单 |
| 撤销/重置 | 原更多菜单内部 | 沿用disabled条件和处理函数 |

全屏Reader保持5个动作全部可见；不改`ReaderPracticeAction`。桌面toolbar可分为“前后”“作答”“答案/缩放/关闭”三组，12px组间距替代重复边框。手机375px按5×44px做题按钮 + 44px关闭 + 44px缩放恢复约束布局（间隙不超过4px；工具栏左右安全内距8px），标题已按现有规则隐藏；不允许横向滚动工具栏。屏幕不足时缩放恢复移入独立可关闭的缩放菜单，5动作及关闭保持，真实图像pinch与现有快捷键保留。建议最终主文档冻结这一规格，不能让实施者任意隐藏做题动作。

### AP-D04 — 单一 Filter 入口与状态反馈（R09/R10/R13/R15）

新增 `PracticeFilters.vue`（业务维度表单）与共享 `FilterTrigger/FilterPanel`（展示层），重构 `PracticeView.vue`，不在多个Vue watcher中重复发请求。

- 普通页面header后一个toolbar：SearchInput flex:1 min-width:0、FilterTrigger“筛选 N”、SortTrigger；结果计数放下一条紧凑行左侧。原“继续练习”保留header。
- `N`是非默认维度数量，不是所选项数量：document+topic算2；search q不计入N；type_group、source_category、state/unattempted规范化成一个状态维度、marker等各计1。存在collection上下文时单独展示不可静默清掉的范围标签，清除只清可编辑过滤条件。
- 数据维度分组：题源（source_category/document/topic）；题型(type_group/exam_type按真实API能力)；学习状态(state/unattempted/review_later/favorite按后端真实契约)；学习标记(marker)。现有页面未暴露的favorite/review筛选不允许仅在前端加无效控件，须与后端负责人确认真实接口并入施工任务。
- 每组使用label+select/checkbox/selection row，组容器不套卡；组间16px；题册与知识点支持列表内搜索；topic依赖document，切题册仅清不兼容topic，原规则保持。
- 即时应用每项变更；多条件修改200ms合并请求；点击外部或关闭保留已生效筛选。没有Apply/Cancel事务；“清除筛选”仍不删除搜索q，“清除全部”只出现在无结果状态并明确包含q。
- 选中条件在toolbar下一行显示可移除的中性chip，最多首3个+“另N项”打开filter；每个chip不要彩色border。手机摘要最多两行，不无限挤占首屏。
- 高频“全部/未做”可保留二项轻量scope，理由是热力图后的快速练习需求且仅占一行；不保留全部来源类别统计卡。是否保留应由主文档冻结为“保留未做Quick toggle一项”，避免后续自选。
- Sort可见选项只能来自真实排序契约；新q搜索默认相关性，q为空默认原题序；显式排序优先于相关性且tie-break stable，清空q恢复原排序。
- 原ExamTypeControls统计功能不能删：筛选形式合并入Filter；小/大题已做/掌握/复习及覆盖统计放“题型统计”紧凑details，不再先占两大行；所有信息可展开查看，“小题专练”保留Plain快捷。类型分色开关仍存在但仅映射小标识，禁止整行彩色底线。

**Popover/Sheet确定规则**：可用viewport>=768px且高度>=600px用锚定popover；宽440px、max-width=viewport-24px，max-height=min(640px,visualViewport.height-32px-safe-insets)。不足转换为modal sheet，横向全宽、顶部保留safe area+8px，最大高度100dvh，单个中间滚动区；header与清除/关闭在flow中sticky，不固定穿越键盘。外点/Escape关闭，焦点回trigger；内部选择不关闭；一次仅一个overlay；popover不被`.overflow:hidden`裁切。推荐已有原生dialog+Teleport能力封装，避免新增重库。

### AP-D05 — SearchInput及键盘/触控（R09/R10/R15）

- 保留请求取消与sequence guards，新增compositionstart/end避免中文IME每个拼音片段请求；输入settled后300ms发查询（由主搜索规格统一）；Enter仅在`event.isComposing === false`且composition会话已结束时立即commit（兼容旧WebKit需同时排除`keyCode === 229`）；IME确认候选用的Enter必须原样交输入法，不选择搜索建议、不导航、不preventDefault。Escape优先关建议，再次Escape不自动清空用户词。
- 单字查询不再无声忽略；后端若限制某一字段/候选规模，要返回明确策略meta，前端不能显示旧结果却让用户误以为已搜索。
- `role=combobox aria-expanded aria-controls aria-activedescendant`；suggestion listbox拥有id；ArrowUp/Down选择，Enter采用，Tab关闭但不偷改查询；pointerdown避免blur抢先但不阻止页面正常滚动；当前mousedown-only须删除。
- 移动输入font-size>=16px防Safari自动zoom；type=search,inputmode=search,enterkeyhint=search；清除按钮44px含aria-label；输入不能强行自动聚焦导致打开页即弹键盘。
- 查询提交后router.replace同步规范化URL；滤镜/paging变化恢复不从旧localStorage覆盖显式URL。stateKey需workspace+user命名空间，迁移旧key只在明确归属Drill下使用。
- 无结果展示q与有效范围、移除筛选、建议词及保留原词按钮；不可自动用纠错替代用户查询。

### AP-D06 — Apple式设置结构（R05/R07/R08/R15/R16）

现有设置内容映射，不制造无实际功能项：

| 设置类别 | 现有功能/真实来源 | 新呈现 |
|---|---|---|
| Account | auth/session身份、Access/passkey入口、Invites（按权限） | 当前用户名只读行；认证入口整行chevron；邀请码列表保留原生成/撤销协议 |
| Appearance | scheme、品牌theme选择 | 外观行→System/Light/Dark单选；强调色行→10色带文字radio selection；语言独立行 |
| General | SettingsView runtimeForm、superuser专属Homepage/Schedule | 组内简单项/详情表单；角色门禁不变；非管理员不渲染实例设置 |
| Preferences | QuestionView翻题模式/4个checkbox、formatColours | 使用同一共享store；题页就地入口保留；不能创建额外服务器字段冒充同步 |
| Organization | task-presets/study-tags | 入口行进入现有管理表单/列表，所有CRUD、4层限制保留 |
| Privacy & Data | data-encryption、export | 保留完整敏感操作说明及确认；不可让整行即时切加密，开关仍走原confirm与PUT |
| Integrations | launch-tokens/Shortcuts | 入口行至详情，secret只显示一次和权限语义保留；不在设置预览泄漏 |
| Administration | `/admin/`以及invite dashboard/recovery | 仅管理员入口行，原链接保留 |

- >=1024px主内容可用宽度时设置有216px类别列+minmax(0,1fr)详情，gap32px，详情最大760px；768–1023px根据应用sidebar实际占用后可用宽度决定：若content>=800则双栏，否则单栏类别→详情；<768单栏导航栈，顶部返回设置类别，保留URL section。
- 组标题13px/600，组间24px；组背景仅一级neutral；圆角10px只加组，不给每行加圆角。行最小48px（两行说明自动64px+），padding12px 16px，主文14–15px，右侧值13–14px。组内separator从文字起点缩进16px，最后行没有分隔线；不叠外border。
- `SettingsRow`必须区分link/button/control/static。button/link可整行激活，但包含switch/select时外层不是button，不嵌套交互元素；label关联控制器，真正控件可独立键盘操作。
- Appearance选择立即生效并保持菜单关闭状态；默认System。Accent色圆点只是预览，选项始终有文字及check；Monochrome有明确深浅映射；semantic success/warning/error不跟accent变。
- 账号菜单通往`/settings`并可直达appearance section；删除Drill底部太阳/月亮模板按钮，不保留隐形focus target。

## 4. 响应式与安全区工程规则

1. 结构以可用宽度为准，设备名称仅用于测试场景。一般页>=1200持久侧栏、768–1199可折叠sidebar按主架构规格；<768 drawer。题目landscape现有保护条件另有专属基线，不用通用sidebar断点覆盖。
2. body只承担一个页面主scroll；dialog/sheet仅自身单个scroll；桌面题目工作区现有左右独立scroll保留。不要为所有卡片加max-height/overflow:auto。
3. 页面grid轨道必须`minmax(0,1fr)`；grid/flex子项`min-width:0`；长文本`overflow-wrap:anywhere`只用于内容/标识，不影响题图；图表ResizeObserver之后调用chart.resize且不持久化旧canvas宽度。
4. 固定手机作答条必须用ResizeObserver测量block-size写CSS变量，主内容padding-bottom=`bar-height + env(safe-area-inset-bottom) + 16px`。若键盘打开（VisualViewport可见高度减少且editable聚焦）则切为页面flow或隐藏非核心浮动条，输入和Note保存可滚到，不挤出完整输入区。iOS键盘不可只用orientation事件推断。
5. sheet/菜单碰撞用VisualViewport的offsetTop/offsetLeft/width/height，监听resize/scroll并清理；异步内容长高后重新定位；最大高度扣safe-area。初期若不实现任意锚点碰撞，使用固定中心modal比半截popover更可靠，但主文档应冻结一种实现。
6. 对`env(safe-area-inset-*)`只在真正贴屏幕边缘的shell/overlay使用，不能内外层重复加；iframe或浏览器正常模式值0也正常。
7. 旋转时不要强制跳顶部；筛选保持，主内容scroll尽量保持，popup必要时关闭并还focus；重新打开使用新尺寸。原生reader zoom和定位算法保持。
8. reduced-motion时关闭scale/slide，仅允许即时状态或<=80ms opacity；普通hover/press120ms，overlay160ms，不让页面进出动画影响做题节奏。

## 5. 具体QA/测试计划

建议新增路径均需主Agent统一最终命名，已有路径保持不变。所有数据写入型回归在本地fixture或测试库进行，生产只读smoke。

| ID | 需求 | 步骤与证据 |
|---|---|---|
| AP-T01 | R11/R14 | `DiagnosisSelector.test.ts`验证8选项、checkbox语义、一次click恰一toggle、busy禁用、主因展示；`QuestionView`集成fixture验证原payload与550ms历史autosave。 |
| AP-T02 | R11/R14 | 打开历史attempt1→修改B2→切换到新题，旧响应不得覆盖；完整时间/round保持；Note不受诊断展开影响。 |
| AP-T03 | R12/R14 | `ReaderPracticeActions.test.ts`延续5动作顺序/disabled/aria-label，录制全屏开→下一题→mastered→自动下一题→answer→返回的行为轨迹。 |
| AP-T04 | R09/R10 | `PracticeView`集成：source+document+topic+type+state+q组合、URL刷新、返回恢复、清除只清可编辑filters；原collection范围仍存在。 |
| AP-T05 | R09/R10/R15 | IME、Arrow/Enter/Escape、触摸候选、Abort竞态；375px键盘下搜索/清除可点；单字“导”明确返回新结果而非旧列表。 |
| AP-T06 | R08/R05/R07 | Settings keyboard逐行操作、System监听切换、Light/Dark覆盖、10accent色；颜色变化不能改变background RGB；角色门禁和加密确认保留。 |
| AP-T07 | R15 | 375×812、390×844、430×932、768×1024、820×1180、1024×768、1180×820、1440×900截图；sheet打开时旋转、聚焦软键盘、关sheet焦点返回。 |
| AP-T08 | R01/R02/R13 | Light/Dark分别检查：设置只有组容器；无每行独立outline；题库无taxonomy彩色卡片；诊断无黄色边框矩形；类型语义标识仍可见。 |
| AP-T09 | R14/R15 | 图像缩放原行为、SourcePaperViewer按题定位、连续做题、返回scroll、iPad左右scroll独立；Reader顶部无overflow，hit区域>=44px且不互相重叠。 |
| AP-T10 | R12/R15 | 静态scan可检测彩色border候选但不直接判失败；人工审查焦点/错误例外；截图必须包含hover/focus/selected/disabled/saving/error状态。 |

完整前端门禁遵循现有`frontend/package.json`：`npm run typecheck`、`npm run build`、`npm run build:drill`、`npm test`。本轮研究未执行这些，不能写成“已通过”。新增诊断组件后需保留原`FullscreenReader.test.ts`、`ReaderPracticeActions.test.ts`、`NoteVisibility.test.ts`、`OriginalAnswer.test.ts`、`questionNavigation.test.ts`与`sourcePractice.test.ts`覆盖，不以新增组件测试替代成熟流程回归。

## 6. 给施工协调者的风险与拆分建议

- 原`QuestionView.vue`包含大量计时/幂等作答/草稿逻辑，风险高。一个Agent独占该文件；另一个只做`DiagnosisSelector.vue`受控组件及测试，交父Agent集成。不能两个Agent分别修改同一template/script/style。
- `styles.css`所有现有question-route覆盖属于主Agent；分配清理任务必须交具体selector与移除行，不能让组件Agent偷偷补!important。新组件独享scoped样式。
- `PracticeView.vue` UI重构和搜索状态管理由同一负责人；Search Backend可并行开发，但API contract先冻结。FilterPanel与SearchInput为共享层负责人维护，避免两个不同popover系统。
- Settings在`frontend/src`，Drill/EI在`frontend/drill/src`。抽shared controls/appearance store时注意两个Vite入口；不能假设Element Plus存在于Drill运行时，也不能把全量Element Plus引入Drill为一个menu服务。
- Apple模式不是“所有按钮无边界”，输入、弹层边缘、焦点、选中checkmark必须仍可见；中性无描边适用于已有上下文明确的操作和列表。
- 44px触控目标、13px诊断文字可能让原窄侧栏诊断更高；接受侧栏现有垂直scroll，禁止缩回9px；需保证作答条保持可达。不能以不改变任何像素作为“保护UX”，保护的是流程、时序、内容、手势和效率。
- 官方原生API文档不是可复制的产品源码。该报告没有声称阅读Apple Settings/App Store/Notes私有源码；示例是行为参考与自主Web工程规范。
