# 使用说明

## 开始与结束一次学习

1. 在首页选择 `Mathematics`、`English`、`Major` 或 `Training` 开始。
2. 运行中只显示 `TIMER HIDDEN`，不会显示累计时长。
3. 点击 `Finish & review`。有效会话只需填写两个英文界面字段：
   - `Title`：本次学习的大标题；旧数据中的 `note` 已原样迁移到这里。
   - `Details`：正文，可直接粘贴 ChatGPT 返回的纯文本或 Markdown。
4. 点击 `Save & finish` 保存。

时长小于 25 分钟或大于 12 小时的单次会话会直接删除，不进入完成记录。点击 `Discard` 的会话也直接删除。

有效会话保存后会立即排队同步到私有 GitHub 仓库，每次会话对应一个独立 `.md` 文件，原始标题、正文、公式和增强 Markdown 语法都会保留。管理员账号写入主分支，普通账号写入按用户名生成的独立分支。GitHub 暂时不可用不会影响本地保存，后台每分钟自动重试。

### Markdown 与公式预览

`Details` 原样保存 Markdown 源文本。录入时预览默认关闭，点击 `Preview Markdown` 才会按需加载渲染器；再次点击可以收起预览。历史会话、热力图二级详情和全局搜索详情默认进入预览而不是编辑，右上角可全屏阅读。全屏预览直接挂载到页面根节点，不受抽屉尺寸限制；退出按钮固定在顶部，正文支持鼠标、触控板和 iOS 触摸上下滚动。只有点 `Edit` 才显示源码编辑器。眼睛图标表示回顾入口，详情里会显示该会话的回顾次数与近 28 天趋势。Issues 的描述与解决方案使用相同预览方式；标题和设置备注仍是普通文本。

支持的增强语法包括：

- 行内公式：`$E=mc^2$` 或 `\(E=mc^2\)`
- 块级公式：`$$...$$`、`\[...\]`，以及语言为 `math` 的代码围栏
- GFM 表格、删除线、自动链接、任务列表和 Callout（如 `> [!NOTE]`）
- 围栏代码及常用语言高亮
- 脚注、上标、下标和 `==mark==` 标记

公式区域可在 `Classic`、`Minimal`、`Paper` 和 `Blueprint` 四种样式之间切换。选择保存在当前浏览器；切换只更新 CSS，不会重复执行 Markdown 或 KaTeX 解析。

预览禁止 Markdown 中的原始 HTML，并会在写入页面前进行 HTML/MathML/SVG 净化。KaTeX 不信任可触发外部资源或 HTML 的 TeX 命令。

## 全局关键词搜索

点击侧栏 `Search everything`，或按 `⌘ K` / `Ctrl K`。搜索范围包括会话标题、Markdown 正文、旧结构化字段以及 Issues 的主题、描述和解决方案。

输入会在短暂防抖后查询；搜索结果只传回标题和短摘要。点击会话结果时才读取完整正文，随后可选择 Markdown 预览；点击 Issue 结果可直接查看描述和解决方案。

## 查看某天记录

首页热力图仅展示 2026-05-23 及之后的数据。颜色较亮的格子表示当天累计学习更久，达到 5 小时的格子使用最高对比绿色。

点击一个格子后：

1. 第一层显示当天 24 小时在线/离线时间轴和每次学习的 `Title`。
2. 再点击某个标题，才会打开该次学习的完整 `Details`。

这样浏览日期时不会一次加载和铺开大段正文。

## 切换主题颜色

进入 `Settings` → `Theme color`，可选择 Coolapk Green、YouTube Red、Bilibili Pink、Meituan Yellow 或 Apple White。选择会保存在当前浏览器中，并同步用于主应用、登录页和 Django 管理页；热力图的绿色分级保持不变，便于跨主题比较。

## 修改本地主页参数

进入 `Settings` → `Homepage and schedule`，可以修改以下参数：

- `Homepage content`：显示在当天日期下方的可选主页内容，留空时维持原来的简洁主页。
- `Study room code`：首页的小号自习室口令，留空时隐藏。
- `Tracking start date`：热力图和统计开始展示记录的日期。
- `Exam date` 与 `Countdown label`：首页倒数日日期及名称。

打开设置页时会读取本地 `.env`，保存时只原子更新上述五个键并立即应用，文件里其余密钥和注释不会被网页读取或覆盖。`Load defaults` 只把原有默认值填回表单，需要再次点击 `Save settings` 才会写入。Docker 版本把网页管理的本地参数保存到数据卷内的 `/app/data/tracker.env`，因此重建容器后仍然存在。

## Passkey 与数据

- iPhone/iPad 可在登录页直接使用本机 Passkey，不需要扫码；首次绑定在 `Settings` → `Add Passkey`。
- `Settings` 中可导出 CSV、JSON 或 Markdown。
- `Issues` 用于保留需要追踪的问题；知识点入口已从当前产品界面移除。
- 启动链接只具备启动指定科目的权限，可在 `Settings` 中撤销或重新生成。

## 邀请新账号

普通用户进入 `Settings` → `Invite codes`，每天（Asia/Shanghai 日期）可以生成一个只能使用一次的邀请码。管理员可以设置标签、1–100 次最大使用次数和可选到期时间。列表会明确显示已使用次数、剩余次数、最近使用时间，以及使用该邀请码注册的用户名。原始邀请码只显示一次，应立即复制。

新用户可以打开 `/accounts/signup/` 使用用户名、密码和邀请码注册，也可以打开 `/accounts/signup/passkey/` 使用用户名、邀请码和设备 Passkey 注册。Passkey-only 账号不会保存密码，该路径不能绕过邀请码。管理员可在 Django Admin 的 `Invitation control` 页面打开 `Open registration`；开关启用后，密码和 Passkey-only 注册均不再要求邀请码，关闭后立即恢复邀请码校验。短密码和纯数字密码仍允许使用，但更容易被猜到。

`eh` 等管理员账号可以从设置页进入 Django Admin。专用的 `Invitation dashboard` 会集中显示邀请码容量、剩余次数、使用时间和通过每个邀请码注册的访客用户名。

同一网络在 15 分钟内允许 20 次失败密码登录，第 21 次会临时限制。管理员可以进入 Django Admin 的 `Authentication recovery` 查看某个 IP 的计数并重置单个网络，也可以清除全部临时登录限制；这不会修改账号密码或 Passkey。

## 本地参数隔离

只有 `eh` 等超级管理员可以在网页中读取和修改本地 `.env` 展示参数。普通用户不能读取或写入 `.env`，主页内容和自习室口令固定为空，不会继承管理员的私有口令；日期和倒计时使用安全默认值。

## 使用说明与联系

只有登录页显示独立的 `/guide/` 使用说明入口；登录后主应用、设置页和管理面板都会隐藏该入口。注册遇到问题时可以直接发送邮件到 `zsyeh7286@gmail.com`，也可以打开 `/contact/` 表单。表单使用 SMTP 直接发送给管理员，不在学习系统数据库中保存正文，并带有 CSRF、蜜罐和每小时限流。

## 免责声明与 GPL

软件和托管网站按“现状”提供，不保证因不可抗力、维护、网络、硬件、第三方服务或其他原因仍能永久运行，也不保证数据绝不丢失、损坏或同步失败。请自行保留备份；只要服务可用，你可以随时在 Settings 中将全部学习记录导出为 CSV、JSON 和 Markdown。

已发布源代码依照 GNU GPL 第 3 版或后续版本持续开放，可在遵守协议的前提下使用、查看、修改和再分发。开源许可不等于托管服务永久在线的承诺。网站 `/legal/` 提供完整中英双语说明。

## 本地运行和生产部署

本地、Docker 一键安装和服务检查命令见项目 [README](../README.md)。生产备份与恢复见 [backup and restore](backup-and-restore.md)，部署步骤见 [deployment](deployment.md)。
