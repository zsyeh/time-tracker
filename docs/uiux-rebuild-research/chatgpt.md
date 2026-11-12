> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Research C — ChatGPT Appearance / Accent / Settings 与本仓库映射

研究日期：2026-11-12。研究工作树：`/home/eh/precision-study-ui-20261111`。本报告只读审计源码并写研究文档，没有修改业务代码、执行迁移、提交或部署。

## 1. 证据级别与限制

使用 OpenAI Docs skill 检索官方资料。用户明确要求研究 ChatGPT 官方应用设置，因此同时查阅直接相关的 OpenAI Help Center；本报告没有把帮助文档当成产品前端源码。

**已实际搜索、打开并阅读的官方来源：**

- **CG-01** [Updating your visual experience on ChatGPT](https://help.openai.com/en/articles/11958281-updating-your-visual-experience-on-chatgpt)。打开时页面显示更新于 24 天前；帮助中心说明设置与颜色可因平台、版本、账户和发布批次变化。
- **CG-02** [OpenAI UI guidelines](https://developers.openai.com/plugins/concepts/ui-guidelines)，原 `apps-sdk/concepts/ui-guidelines/` 重定向至此。这是为 ChatGPT 内嵌应用提供的官方设计规范，不是 ChatGPT Settings 的实现代码。
- **CG-03** CG-01 内的[官方桌面设置配图](https://images.ctfassets.net/j22is2dtoxu1/lbas_img_tlJ2f2Z9yrXiTO0-TXdn08aX_BCe38E-1X5vqvlzFwo/0bb9f694c6a3367a148d1a4af3929859/lbas_img_tlJ2f2Z9yrXiTO0-TXdn08aX_BCe38E-1X5vqvlzFwo.png?fm=webp&q=80&w=834)。已下载并实际查看，缓存 `chatgpt-official-settings.webp`。
- **CG-04** CG-01 内的[官方 iOS 设置配图](https://images.ctfassets.net/j22is2dtoxu1/lbas_img_xQhaAewLpvOxgD3B85z9xPfjo-J8Q9px-Yirbm0Vhyw/77776194ef180c97e01f9318d2c5cb73/lbas_img_xQhaAewLpvOxgD3B85z9xPfjo-J8Q9px-Yirbm0Vhyw.png?fm=webp&q=80&w=393)。已下载并实际查看，缓存 `chatgpt-official-ios.webp`。

**证据缺口：**当前用户消息未附 ChatGPT/iPad 或当前产品截图。不能宣称已检查“用户提供的截图”，也不能断言 CG-04 就是 iPad 截图。CG-04 是官方标注的 iOS 界面。没有访问登录后的 ChatGPT 实时界面、私有源码、内部 Token、设置持久化实现；下述项目架构均是我们的明确工程决策，不是对 ChatGPT 私有实现的猜测。

## 2. 官方可确认行为及借鉴边界

CG-01 确认：Appearance 具有 System/Light/Dark，Accent 独立控制局部界面色；修改其中一项不修改另一项。外观按设备/平台保存，Accent 可随同账户跨支持设备同步；颜色可用性不完全一致。Monochrome 在浅色与深色分别显示黑/白，属于同一中性色选项。这里采用的十色清单来自本项目 R07，不能声称 ChatGPT 固定提供这十色。[CG-01](https://help.openai.com/en/articles/11958281-updating-your-visual-experience-on-chatgpt)

CG-02 提倡保留系统背景、文本和分割语义，将品牌强调限制在局部操作；使用系统字体、少量文字层级、单色图标、对比度合格的文本，避免图案或渐变成为主体。[CG-02](https://developers.openai.com/plugins/concepts/ui-guidelines)

**对官方配图的可观察结论：**桌面设置有类别栏和内容栏；设置行左标题右当前值，行间有细分割线。Accent 菜单用颜色圆点辅助文字；勾选和中性整行底色表示当前值。iOS 将 Theme 下的 Appearance 与 Accent 放入同一分组，两行共用外容器，组内只有分割线。菜单自身浮于设置页之上，设置条目没有各自独立彩框。[CG-03/04，配图观察]

**适合当前项目的模式：**使用设置行表达“键→值”，整行触发选择；用菜单承载选择而不是把每个值做成矩形卡；语义状态色保持固定，Accent 只映射交互 Token。不要照搬 ChatGPT 的产品功能类别（订阅、语音、云浏览器等本系统不存在的选项），不要照搬图标或品牌资产。

## 3. 当前真实代码审计

|证据 ID|真实文件/位置|现状|工程影响|
|---|---|---|---|
|C-A01|`frontend/src/lib/uiPreferences.ts:3–9,55–116`|`UiScheme = dark \| light`；cookie 优先 localStorage；没有 System、matchMedia 或 Accent；首次默认 dark|无法随系统外观变化，不能只在 Settings 添加第三个 option|
|C-A02|`frontend/drill/src/lib/uiPreferences.ts:3–9,29–64`|重复实现同样的主题存取与 DOM 更新；同名 cookie/key；默认 dark|必须合并共享偏好核心，保留各自翻译字典|
|C-A03|`frontend/index.html:16–30`|同步 head 脚本先读 `learning-os-theme`，默认 violet；另读颜色模式，默认 dark|已经有避免首屏闪烁的入口；新架构必须替换而不是只在 mounted 更新|
|C-A04|`frontend/drill/index.html:16–27`|同步 head 只恢复 scheme/language，不恢复 accent|Timer/Drill/EI 色彩不同根因之一|
|C-A05|`frontend/src/views/SettingsView.vue:17,47–54,88–92,347–357`|六种品牌色：violet/coolapk/youtube/bilibili/meituan/apple；颜色按钮独立彩框；`setTheme` 只写 localStorage 和 `data-theme`|旧色要迁移，品牌命名要移除；需要十色、统一 store 和独立 Appearance|
|C-A06|`frontend/src/styles.css:100–104,143–144,546–552`|品牌色只改 accent 变量，但 youtube 还切换 workspace 标志/名称；色选卡片 active 彩色 border+底色，字体 7/10px|不是简单替换色值；移除主题对品牌结构的副作用并换 settings selection menu|
|C-A07|`frontend/src/components/navigation/SidebarPreferences.vue:1–23`|太阳/月亮按钮 + 语言下拉|用账户菜单的设置入口替代常驻二态外观控件|
|C-A08|`frontend/drill/src/App.vue:226–235`|◐/☀ 两个按钮 + 语言 select + 账户退出|和 Timer 共用行为；移除显眼图字符，保留退出和语言能力|
|C-A09|`frontend/src/styles.css:182–187,520–525,847–850`|偏好行已有可复用雏形；侧栏 160px；手机将所有类别变横向滚动；标题 9–11px、辅助字 10px|不需要另做五层卡片，重构现有行；手机用索引→详情而非拥挤横条|
|C-A10|`frontend/src/routes.ts:14`|当前正式设置入口仅 `/settings`|Drill/EI 可用同源 `/settings?from=<safe local path>#appearance`，不用复制 SettingsView 三份|
|C-A11|`tracker/api_views.py:491–517`、`tracker/serializers.py:413`|runtime settings 更新实例 .env；写入仅超级用户|绝不能把个人 Appearance/Accent 塞进 runtime endpoint|
|C-A12|`tracker/models.py:499–557`|SiteConfiguration 是站点策略；UserDataEncryptionPreference 是个人加密开关；未发现个人外观模型|本轮视觉偏好无需改业务数据库；如以后要求账户同步，必须独立模型/API|
|C-A13|`templates/allauth/layouts/base.html:14–16`、`templates/admin/base_site.html:13–15`、`templates/public/base.html:13–14`|登录/管理/公开页还读取旧 `learning-os-theme`，默认 coolapk|旧键至少一个回滚窗口保留；不能删除键后让外围页面随机变色|
|C-A14|`frontend/vite.config.ts`、`frontend/vite.drill.config.ts`|两个 Vite 入口，Drill 的 root 是 frontend/drill；TS 主配置 include 只覆盖 src|共享文件放 frontend/shared 后，两套构建/TS/Vitest 都要覆盖，路径以配置文件绝对目录定位|

`frontend/src/views/SettingsView.vue` 还拥有加密、Passkey、数据导出、任务预设/标签、邀请码、启动/扰动 URI、实例参数和管理入口。重构不能把这些功能删掉，不能把危险动作整行直接触发。

## 4. 推荐决策（固定输入给主施工文档）

### C-D01：外观与强调色拆为两个独立状态

```ts
type Appearance = 'system' | 'light' | 'dark'
type ResolvedScheme = 'light' | 'dark'
type Accent = 'blue' | 'cyan' | 'green' | 'lime' | 'yellow'
  | 'orange' | 'pink' | 'magenta' | 'purple' | 'monochrome'
interface VisualPreferencesV2 {
  version: 2
  appearance: Appearance
  accent: Accent
}
```

默认 `appearance=system, accent=blue`。`resolvedScheme` 是派生值，不写入用户意图字段。DOM 输出：`data-appearance`, `data-color-scheme`, `data-accent`；保留旧 `data-color-scheme` 选择器避免已有图表/组件失配。`color-scheme` CSS property 使用解析后的 light/dark。监听系统变化仅在 `appearance=system` 时应用；手动覆盖不受系统事件改变。监听单例只注册一次。

### C-D02：本阶段使用设备级持久化，不引入外观数据库表

依据：当前偏好是浏览器级设置，没有个人外观 API；R07 要求依据架构决定是否同步，未要求必须跨账户/跨设备。推荐延续设备偏好，明确在设置下提示“保存在此浏览器”。Appearance 与 Accent 均可跨同源 Timer/Drill/EI；不冒充 ChatGPT 账户同步。关闭 PWA、刷新、路由切换均恢复。

新 key `learning-os-visual-preferences-v2`；新 cookie `learning_os_visual_preferences_v2`，值为 encodeURIComponent 后的 compact JSON，Path=/，Max-Age=31536000，SameSite=Lax；HTTPS 加 Secure。现有 ehzsy.site 子域共享 cookie 行为保留，但 IP 与域名间不可能通过 cookie/localStorage 自动共享，文档必须说明这条平台边界。禁止使用认证 cookie/服务端 runtime 配置保存颜色。新键优先：有效 V2 cookie→有效 V2 localStorage→已验证旧值→默认。对格式错误逐字段回退而不是整组抛异常；所有 storage/cookie 访问分别 try/catch。不能让 storage blocked 引起应用启动失败。

考虑到无需账户同步，不新增后台 API，不影响用户表、学习记录和加密。若未来要求账户同步，则应新建专属 `UserUiPreference(user OneToOne, accent, updated_at)`、认证下 GET/PATCH `/api/settings/ui/`；Appearance 仍设备级。这个备选不在当前推荐施工范围，不能被后续 Agent 当作必须同时实现。

### C-D03：首屏同步 bootstrap 只有一个源

新增拟定文件（均为拟新增，当前不存在）：`frontend/shared/appearance-bootstrap.js`、`frontend/shared/useAppearance.ts`、`frontend/shared/appearance-types.ts`、`frontend/shared/styles/tokens.css`。主 Agent 可以在全局组件命名统一后调整目录一次，随后冻结。

推荐 `appearance-bootstrap.js` 为小型纯浏览器 IIFE，不依赖 Vue/网络：读取/迁移偏好→解析系统→设置 DOM/color-scheme/theme-color→暴露最小 `window.__learningAppearance` store（read/set/subscribe）。两个 Vite config 使用同一轻量 `transformIndexHtml` hook 读取此文件并同步内联于 head；替换现有两个独立内联实现，不能保留三份逻辑。Vue adapter 引用相同 store；两套 uiPreferences 只保留各自语言字典与兼容 re-export。该方案避免网络慢时先出现错误主题，也避免 TS 版本与内联 JS 版本漂移。构建测试必须断言两个产物都含同一 bootstrap 字节内容/哈希。不要新增第三方主题库。

同步 script 必须位于可绘制正文和模块入口之前。首屏背景由纯 neutral token 按 DOM theme 立即确定，meta theme-color 也只使用 neutral 背景。若 CSP 禁止 inline，则由 Django CSP nonce/hash 允许同一精确内容；不能添加 unsafe-inline 作为捷径。当前 CSP 是否启用仍需主 Agent 在服务配置审计中确认。

跨标签 `storage` 事件、页面 `pageshow`（含 BFCache）和可见时恢复应重新读取有效状态。cookie 不发 storage event，跨子域页面在 pageshow/visibilitychange 读取。仅用户变更时写持久化；系统变化更新 resolved scheme，不把 system 意图误写成 dark/light。首次运行迁移写 V2 一次，随后不反复重置用户选择。

### C-D04：明确旧值迁移及回滚

|旧值|新值|
|---|---|
|旧 color-scheme=light/dark|保留相同明确覆盖；只有没有有效旧偏好者默认 system|
|violet|purple|
|coolapk|green|
|youtube|orange（不新增错误语义 red）；首次设置页提示一次“旧红色主题已迁移为橙色”，允许立即改色|
|bilibili|pink|
|meituan|yellow|
|apple|monochrome|
|未知或空值|blue|

旧 `learning-os-theme` 只读迁移，不再用它控制产品名称或图标。旧 key 至少保留完整发布/回滚窗口，不清空用户 browser storage。旧页面兼容方案优先让 allauth/public/admin 的 bootstrap 改为新共享 neutral/appearance 映射，保留业务样式；如该阶段只覆盖三 SPA，则保持旧键不写不删，并把外围主题一致性列入后续必做全站任务。不要让新色映射回任意第三方品牌名。回滚前端后旧键仍可用。

## 5. 十色建议 Token 与已进行的技术验证

以下是为本项目原创的候选值，不是 ChatGPT Token。主 Agent 应在统一 Token 规范中固定一个版本。颜色作用范围只有 `--accent-*`，任何 `--surface-*`、`--bg-*`、`--text-primary`、`--border-*` 都不得出现在 `[data-accent]` selector 中。

|Accent id|浅色 fill/link|深色 fill/link|浅色白字对比|深色 #111 字对比|
|---|---|---|---:|---:|
|blue|#1D4ED8|#8AB4FF|6.70|9.04|
|cyan|#0E7490|#67D5E8|5.36|11.02|
|green|#18713D|#76CF9B|6.05|10.04|
|lime|#4D6C10|#B1D76C|6.06|11.52|
|yellow|#8A6100|#E5C45A|5.54|11.13|
|orange|#A84B08|#F2B07A|5.71|10.13|
|pink|#B32369|#EF9DC8|6.25|9.29|
|magenta|#A12891|#E9A1DB|6.51|9.52|
|purple|#6F42C1|#C4A7F4|6.51|9.15|
|monochrome|#242424|#E6E6E6|15.52|15.13|

以上比率通过只读 Python 3 sRGB 相对亮度计算实际验证，指表中前景/背景组合；不等于对所有 hover/soft/disabled 组合或截图完成可访问性验收。黄色/Lime 在浅色界面中须用较深色的 link/fill，可让色彩圆点展示更明亮的 swatch；swatch 不承载小号文字。

```css
/* data-color-scheme defines neutral/semantic values, never depends on accent. */
:root {
  --accent-light: #1d4ed8;
  --accent-dark: #8ab4ff;
  --accent-solid: var(--accent-light);
  --on-accent: #fff;
}
[data-color-scheme='dark'] {
  --accent-solid: var(--accent-dark);
  --on-accent: #111;
}
[data-accent='cyan'] { --accent-light: #0e7490; --accent-dark: #67d5e8; }
/* Remaining nine pairs generated once from one palette declaration. */
:root {
  --action-primary-bg: var(--accent-solid);
  --action-primary-text: var(--on-accent);
  --link-text: var(--accent-solid);
  --focus-color: var(--accent-solid);
  --accent-soft: color-mix(in srgb, var(--accent-solid) 10%, var(--surface));
}
```

浅色主按钮 hover：solid 与 black 88:12 混合；深色主按钮 hover：solid 与 white 92:8 混合，仍需计算对比度。选中色点+勾只用于色选择器；导航选中整行背景保持中性。不要用 soft accent 填满题库容器。Mastered/Review/Danger 永远读取独立 semantic tokens。旧 `--green: var(--accent)` 等兼容变量需逐调用者分类：若表达状态就改成功语义，若表达主要动作就改 action token；不可全局替换把掌握绿变成 Purple。

## 6. Settings 施工规范

**结构：**仍用 `/settings` 单一真实页面，不新增三份设置副本。桌面/可用内容宽度≥840px 使用 176px 类别列 + minmax(0,1fr) 内容列，gap 32，内容最大 760px；≤839px 显示类别索引页与当前类别详情页，顶部返回“设置”，不把所有类别横向滚动堆在顶部。使用 `?section=appearance` 维护子面板深链接；保留历史 hash anchor 解析兼容。Drill/EI 账户菜单可链接同源 `/settings?section=appearance&from=<encoded same-origin route>`；return URL 仅接受 allowlist 的本地路径，不允许任意外链。返回时利用原有页面恢复，不引入第二套学习状态系统。

**组件（拟新增）**：`SettingsGroup(title,description?)`；`SettingsRow(label,description?,value?,kind,disabled,busy)`；`AppearanceSelector(modelValue)`；`AccentColorPicker(modelValue)`。在整行可打开 menu 的情况下根节点就是 button，不能 button 内嵌 button/select。含 switch 的行用 label + switch，不触发导航；含危险动作的条目先打开详情/确认，不能整行立即执行。行高 min44px，推荐普通行52px；主标题14–16px，说明12–13px；内容左右16px，首末行共享8px外圆角；分割线从文字左沿起，只有组内一条，不给每行完整 border。

**类别与真实业务映射：**

|类别|实际内容|必须保留|
|---|---|---|
|账户|用户名（`/api/auth/session/`），退出；Passkey 添加/管理|现有 logout 协议、认证保护和安全入口|
|外观|Appearance、Accent Color 两独立行|本地持久化、system变化、十色、无首屏闪烁|
|通用|Language；现有追踪/考试日期/首页文案只在超级用户进入实例设置时显示|`isSuperuser` gate，原 runtime 保存/默认值动作|
|学习偏好/组织|现有任务预设、标签管理|最多四级、分类历史保护、原归档/删除语义|
|隐私与数据|存储加密、数据导出|必须保留现有加密说明、确认、服务端错误与 CSV/JSON/Markdown 全部格式|
|访问与邀请|邀请码；staff/superuser 管理入口|角色权限、日配额、一次性 raw code 展示，不写入截图和日志|
|自动化|启动与扰动 URI、配置、暂停/恢复、更新/撤销|原 secret URI 协议、时间窗和复制路径|

类别名称可最终统一中文，但不新增不存在的“通知/同步/订阅”等假设置。“Preferences”映射现有组织/学习默认值，不凭空加自动翻题总开关改变现有题目局部行为。

**菜单行为：**Appearance 菜单三个 menuitemradio；单次选择即应用关闭，焦点回到触发器。Accent 菜单十个单选行，文字+色点+勾；选中背景中性，无彩色描边。桌面 menu 宽240px、最大高度 min(440px, viewport safe-area available)，上下避让触发器且不出屏；手机可用底部 Sheet，标题“强调色”，固定关闭/完成区域，内容可滚动，底部 safe-area，仍是一次点选应用。Escape关闭、外点关闭、方向键/Home/End移动、Enter选择。这里是我们的项目交互规范，不声称 ChatGPT 私有菜单键盘规则。

**移除旧实现：**六个主题卡按钮、品牌 theme label 数组、setTheme DOM直接写入、youtube 标志切换 CSS、常驻太阳/月亮按钮。保留当前语言支持；账户区只留统一菜单触发器，菜单含设置与退出。外围模板旧主题依赖须按 C-A13 协调完成，不可粗暴删除键。

## 7. 需求/任务/验收映射

|需求|决策|施工任务|测试/证据|
|---|---|---|---|
|R05|C-D01/02/03|共享 appearance store、三态选择、head bootstrap、移除两套太阳/月亮|T-C01~06；首次paint录屏，冷启动PWA截图|
|R06|C-D01/05|neutral 与 accent selector完全隔离|T-C07；10色切换背景computed-style不变|
|R07|C-D01~04|十色、迁移、持久化、无账户API决定|T-C03/04/07/08；20组对比度报告|
|R08|Settings结构/行规范|拆分Settings组、原动作保留、移动索引详情|T-C09~11；Light/Dark桌面和iOS尺寸截图|
|R01/R02/R12/R13|Settings行和菜单|去独立彩框，层级有限；保留真实需要确认的危险动作|V-C01~04；控件结构和点击路径审查|
|R14|语义色独立|禁止 --green 盲目跟 accent；保持加密/邀请/计时动作|T-C07/10，Question专项回归|
|R15/R16|共享bootstrap与设置布局|两构建入口、PWA、跨页一致|T-C05/06/09/11|

### 自动化检查清单

- **T-C01** 空偏好+系统light/dark→默认 system且resolved一致；关闭存储/非法cookie不会抛异常。
- **T-C02** system监听变化，manual light/dark忽略系统变化；重新选system恢复跟随；监听器重复初始化不叠加。
- **T-C03** 10 Accent×2 Appearance，切换Accent不改appearance，反向同理；保存/刷新还原。
- **T-C04** 旧六主题+旧light/dark全部迁移；不覆盖已有效V2；未知值回默认；旧键仍保留；youtube迁移提示只一次。
- **T-C05** 主/Drill 两个 production index head bootstrap相同；JS入口加载前DOM和theme-color正确；阻断/延迟模块加载也无错误背景闪烁。
- **T-C06** 同源跨Timer/Drill/EI、storage事件、BFCache/pageshow、PWA重启；不触发学习状态写入。
- **T-C07** 逐accent比较body/sidebar/main/card背景computed-style完全一致；success/review/danger完全一致；主要按钮/链接/focus可见变化。
- **T-C08** 20组合主按钮文字4.5:1、小字link4.5:1、focus与邻接3:1；Yellow/Lime/Monochrome重点；hover/disabled单独验收。
- **T-C09** 390/430/768/1024/1366尺寸，菜单不超出可视区域；iPad旋转保持当前项；200%文字缩放可用。
- **T-C10** staff/superuser/普通账户分别验证显示；只改变视觉不得向runtime、加密、任务、邀请、URI接口发请求；危险设置维持原确认。
- **T-C11** menu focus、Escape、键盘、触屏；手机Sheet底部safe area；无嵌套button；错误提示可被读屏听到。

### 视觉检查清单

- **V-C01** Light时一个分组一个容器，组内细线，不是每行矩形，不用阴影顶替所有边框。
- **V-C02** Accent选择器当前值用中性整行+勾，色点只是辅助，十色标签可读；不能只依赖颜色。
- **V-C03** 主体和侧栏R=G=B的固定中性色，紫色Accent只影响局部行为，屏幕中不出现大面积紫灰/蓝灰底。
- **V-C04** Appearance/Accent行左标题右值同轴，正常字号，无7px SELECTED、无装饰大写小标题层层嵌套。
- **V-C05** Settings改造前后同视口截图；官方配图只作研究依据，项目截图必须来自本地实际构建，不合成效果图冒充验收。

## 8. 所有权、阶段与未验证项

主 Agent 独占两套全局 Token、bootstrap、Vite/TS配置、全局导航及两套 uiPreferences。Settings 子 Agent 在共同组件 contract冻结后实现 `SettingsView` 与专属组件。两个 Agent 不可分别发明持久化 key或主题CSS覆盖。Phase 1先完成偏好/Token；Phase 2账户设置入口；Phase 3设置页；Phase 8执行T-C/V-C完整验收。全局配色未稳定前不要同时改 QuestionView核心布局。

仍待主审计补齐：服务器CSP现状；外围认证/公开模板是否纳入本轮全站主规范；真实iPad Safari/PWA截图及软键盘；用户引用截图的真实视觉差异。上述缺口不阻止当前推荐架构，但施工文档不得把这些项写成已经通过。
