# 专练题号 · Practice / 全屏

- 最终应用 `762a24a`，生产镜像 `time-tracker-ha:20261125-special-number-762a24a`。15:49:18–15:49:27 +08切换，healthy，登录健康入口200。
- 从专练开始或其全局预览进入Practice，普通页标题前显示“专练 · 第 N / 总数 题”，保留原题册标题；全屏题目、答案及完整答案标题沿用同一序号。手机全屏使用紧凑编号行，避免原布局隐藏长标题后看不到题号。
- 从现有ListContext和located索引取号，零基索引+1；API完成前用URL已有position，完成后显示总数。只对paper且returnTo=/special-practice启用；普通题库、历史及考试页不改。题目切换时不把旧题的索引或总数用于新题。
- 无新增API/数据模型/请求，无迁移；不修改作答、计时、收藏、答案权限及考试协议。

## 文件与验证

- QuestionView.vue：编号派生、普通标题及全屏传值；FullscreenReader.vue：可选positionLabel，仅小屏显示；QuestionPreviewNavigation.test.ts：索引与上下文隔离。
- 最终19项相关测试通过（12导航+7阅读器，1.55秒），类型检查及生产构建通过（最后Vite7.17秒）。
- 生产Drill1440与EI1180：普通下一题1→2、全屏上一题2→1、切换答案、退出全屏和刷新检查通过（026127c时）。最终手机390复测同路径通过、无pageerror；后续修正仅补手机编号显示，不重复跑已通过桌面路径。截图时不等待题图网络完成，只作为编号可见性证据，不冒充图片加载性能测试。
- 新建隔离QA账号与两份2题专练，未提交Attempt，测试结束清理账号、题单、临时计时与Session。没有用真实账号做假作答。实体Safari/PWA未实测。

## 迭代、用时与回滚

- 15:41:10首批12导航测试开始；15:46:39扩到19项相关检查；15:49:27最终healthy。没有精确开发起点，不虚报总时长。备份与开发并行。
- 首次将编号放入eyebrow，而全局compact CSS会隐藏它；第二次普通标题修正后，手机全屏原规则仍隐藏strong。补独立小屏编号时一次字符串替换误作用于reader-count选择器，真实手机校验发现并修复。四次应用切换增加成本，属于实现/发布流程问题，不能归因于题库或数据库。
- 后续此类信息展示变更先检查实际隐藏规则，针对普通/紧凑/全屏及小屏做可见性截图，再统一发布；CSS修改用精确区块编辑，避免全文件同名子串替换。函数测试不能代替CSS可见性验收。
- 用户数据/Schema/config/旧镜像备份 `/var/snap/docker/common/time-tracker-ha/backups/special-number-20261125`，verify-exit=0；未重复导出题库图片。
- 回滚：`sh /var/snap/docker/common/time-tracker-ha/releases/special-number-762a24a/rollback.sh`，返回已验证分享版本 `time-tracker-ha:20261125-special-share-fc6b7f6`；保留数据库，不覆盖后续学习记录。

[手机复测](browser-result.json) · [手机全屏](ei-390-fullscreen.png) · [iPad尺寸](ei-1180-fullscreen.png) · [Drill桌面](drill-1440-fullscreen.png)
