# 使用说明

## 开始与结束一次学习

1. 在首页选择 `Mathematics`、`English`、`Major` 或 `Training` 开始。
2. 运行中只显示 `TIMER HIDDEN`，不会显示累计时长。
3. 点击 `Finish & review`。有效会话只需填写两个英文界面字段：
   - `Title`：本次学习的大标题；旧数据中的 `note` 已原样迁移到这里。
   - `Details`：正文，可直接粘贴 ChatGPT 返回的纯文本或 Markdown。
4. 点击 `Save & finish` 保存。

时长小于 25 分钟或大于 12 小时的单次会话会直接删除，不进入完成记录。点击 `Discard` 的会话也直接删除。

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
