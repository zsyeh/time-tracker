# 使用说明

## 开始与结束一次学习

1. 在首页选择 `Mathematics`、`English`、`Major` 或 `Training` 开始。
2. 运行中只显示 `TIMER HIDDEN`，不会显示累计时长。
3. 点击 `Finish & review`。有效会话只需填写两个英文界面字段：
   - `Title`：本次学习的大标题；旧数据中的 `note` 已原样迁移到这里。
   - `Details`：正文，可直接粘贴 ChatGPT 返回的纯文本或 Markdown。
4. 点击 `Save & finish` 保存。

时长小于 25 分钟或大于 12 小时的单次会话会直接删除，不进入完成记录。点击 `Discard` 的会话也直接删除。

有效会话保存后会立即排队同步到私有 GitHub 仓库，每次会话对应一个独立 `.md` 文件，原始标题、正文、公式和增强 Markdown 语法都会保留。GitHub 暂时不可用不会影响本地保存，后台每分钟自动重试。

### Markdown 与公式预览

`Details` 原样保存 Markdown 源文本。录入时预览默认关闭，点击 `Preview Markdown` 才会按需加载渲染器；再次点击可以收起预览。历史会话、热力图二级详情和全局搜索详情也可以在源码与预览之间切换。Issues 的描述与解决方案使用相同方式；标题和设置备注仍是普通文本。

支持的增强语法包括：

- 行内公式：`$E=mc^2$` 或 `\(E=mc^2\)`
- 块级公式：`$$...$$`、`\[...\]`，以及语言为 `math` 的代码围栏
- GFM 表格、删除线、自动链接、任务列表和 Callout（如 `> [!NOTE]`）
- 围栏代码及常用语言高亮
- 脚注、上标、下标和 `==mark==` 标记

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

## Passkey 与数据

- iPhone/iPad 可在登录页直接使用本机 Passkey，不需要扫码；首次绑定在 `Settings` → `Add Passkey`。
- `Settings` 中可导出 CSV、JSON 或 Markdown。
- `Issues` 用于保留需要追踪的问题；知识点入口已从当前产品界面移除。
- 启动链接只具备启动指定科目的权限，可在 `Settings` 中撤销或重新生成。

## 本地运行和生产部署

本地、Docker 一键安装和服务检查命令见项目 [README](../README.md)。生产备份与恢复见 [backup and restore](backup-and-restore.md)，部署步骤见 [deployment](deployment.md)。
