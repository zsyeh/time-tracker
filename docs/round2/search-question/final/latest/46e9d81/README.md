# 46e9d81 最终构建最小风险回归

本轮仅复核新增进度目标账号同步后的最终生产构建，不重复生产性能测试，不访问已清理的合成生产账号。

- 精确入口：`index-BCgPVMSo.js`；index.html SHA256 `53bb4b0bd76938cc2344e6c89546d43f78363374c96fecfa421d4cff399829bd`。
- 67个构建文件运行前后哈希完全一致。见`bundle-before.json`、`bundle-after.json`和`release-evidence.json`。
- 本地8023账号fixture按真实`preference_defaults()`更新为16个字段，包含Drill24/EI11、deadline2026-11-21；不再使用会被新schema拒绝的旧14字段bootstrap。

## 结果

| 门禁 | 结果 |
|---|---|
| WebKit27.2、820×1180触控视口、Drill完整搜索/next/prev/return/再次搜索 | 通过 |
| 同上EI工作区、独立路径 | 通过 |
| 两条路径各横屏1180×820→竖屏820×1180，4次切换 | 0横向溢出、0菜单/返回按钮重叠 |
| 搜索pointer-prefetch后立即点击 | 每条目标详情1个GET |
| 输入未提交草稿时立即进入题目，返回再次搜索 | URL和已提交搜索条件未被旧timer覆盖 |
| Question诊断/Note/Reader原始review.question | 通过，0JS错误 |
| 8项诊断、选择2项、Note Save/More/提交栏位置 | 触控目标至少44px，保存和工具未遮挡 |
| Reader1180×820旋转390×844后7项工具与Escape退出 | 保持打开、无横向溢出、至少44px、正常退出 |

已查看最终Note/More横屏和Reader旋转截图。fixture没有真实扫描图，Reader截图内容区为空或极淡，因此本轮只证明控制条/布局/诊断/Note的回归；真实图加载的独立生产证据见上级production目录，不能混淆两者。

WebKit不支持Long Tasks PerformanceObserver，本轮明确记录`long_task_observer_supported:false`；不是0长任务证明。桌面WebKit引擎触控视口不等同于真实iPadOS Safari/PWA或软键盘。

## 复现

本地fixture服务8023启动后，使用本目录`browser_flow.py --engine webkit --tablet-only --rotate --base http://127.0.0.1:8023 --output OUTPUT`，随后`reader_check.py --engine webkit --output OUTPUT`。`--tablet-only`只缩小重复设备矩阵，保留Drill和EI全部原始交互及断言。

详见[下一题图片预取源码核对](next-image-source-audit.md)。未改变任何业务源码或提交协议。
