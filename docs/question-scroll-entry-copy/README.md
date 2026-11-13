# 做题序列滚动预览、状态色与进入自动复制

2026-11-13，Drill/EI。分两批发布：`44a8603`滚动序列/状态色；用户在发布期间追加自动复制要求后，`0d23177`进入自动复制。最终生产`time-tracker-ha:20261113-entry-copy-0d23177 sha256:0a6eb50124f5f158d0fc869e23dbf6c4dc306a37b754f2bf1a54d78b934fefdb healthy`，两次deploy均exit0/登录200/queue成功，静态JS/CSS SHA与最终构建相同。Git分支`feat/collection-preview`。[生产记录](production.json)。

## 逐项交付

| ID | 用户要求 | 实现与验收 |
|---|---|---|
| QSCROLL-01 |做题页直接打开滚动预览|工具栏首项“滚动预览”，从当前真实UUID/条目定位；已有preview context直接复用，不丢重复Attempt身份|
| QSCROLL-02 |按既定下一题顺序|新增认证只读projection source=navigation；navigation_anchor/mode/from，顺序/未做/近期review/逾期四模式；沿用现有Next实际范围/排序/回绕而非另排题库|
| QSCROLL-03 |返回做题|navigation题单“返回做题”回原Question URL；点任意题仍进入现有Practice、前后题沿预览序列|
| QSCROLL-04 |红黄绿灰|过期review红、近期review黄、done/correct绿、未做/reset灰；小色点+文字，原状态含义/Accent独立|
| COPYENTRY-01 |从外部点进也复制|router beforeEach只在非Question→Question时启动promised ClipboardItem；Question首次加载领取结果，深链接尝试fallback，已有Next复制不重复|
| COPYENTRY-02 |保留偏好与倍率|复用账号practice.workspace.copy_mode（off/link/image）及image_copy_scale；不强开关闭的功能、不新增本地独立设置|
| COPYENTRY-03 |权限/失败可恢复|页面导航不等待剪贴板；失败显示明确重试提示，现有手动复制入口不变，不冒报成功、不强制prompt|
| COPYENTRY-04 |原做题行为|QuestionRecord/Next/preview导航相关测试保留；不改计时、作答、Note、掌握、统计公式或数据Schema|

## 实际接口与排序契约

`GET /api/drill/collection-preview/?source=navigation&navigation_anchor=UUID&navigation_mode=sequential|unattempted|review|overdue&navigation_from=...`；继承原题目的导航query和workspace，仍50条/批、现有500条LRU与有界虚拟窗口。只水合题干预览，无答案/图片二进制，无学习写入。

- 普通顺序/复习：按现有Next的同来源/严选集合/题型范围、document_id/question_order/pk排列；从当前题开始，后续到尾后回到前段，一次有限遍历，不无限复制相同DOM。原Next本来不按题库搜索相关性排序，本功能也不擅自更改。
- 未做：复用navigation_queryset及latest null/reset定义；保留原选集范围和回绕，当前题即使已做也显示为起点。选集当前题已不在有效范围的回退与原Next相同。
- 旧收藏/历史入口：沿现有Question的list_context_navigation顺序；历史默认翻题已按UUID去重，此入口保留该旧行为。直接由历史全局预览进入Question时仍复用原context/Attempt条目，不去重。顺序/复习不额外回绕；未做按旧规则回绕。
- 近期/逾期沿用最新Attempt.review及5日阈值，不新定义ReviewPlan业务口径。API为每条补review_overdue布尔供所有预览source着色。

## 自动复制机制及边界

`questionEntryCopy.ts`在站内跳转guard中立即创建剪贴板写入，Blob/URL promise等待现有认证详情与图片；使用原sourcePracticeTarget处理原卷→实际小题；Question领取一次结果。模式off不额外请求复制详情。已有Next继续原startPageTurnCopy，Question首次加载watch不会在每次Next重复执行。设置标签更新为“进入题目时复制（含翻题）”。

Safari可能拒绝刷新/直接外部打开后没有用户激活的自动写入，无法绕过平台权限；实现尝试在进入点击手势中预先启动，拒绝后如实提示手动复制。不声称已通过实体iPad系统剪贴板验收。

## 测试与证据

- 滚动/状态：34前端相关测试；23主后端+1选集边界=24个独立PostgreSQL测试通过（另SQLite23非额外独立用例）。匹配原Next、循环/收藏排序、reset、最新review年龄、workspace隔离及四状态标签。
- 自动复制：37相关前端测试通过，含4个新service用例、QuestionRecord与原导航/剪贴板；与前一批有11例重叠，不把71次执行称71个独立用例。新service fixture曾有TypeScript回调类型错误，修正后最终生产构建通过；未重复全量后端。
- 真实本地题图：[滚动入口→Next对照→返回原题](question-scroll/browser.json)，黄色色点/文字实际RGB相同，0JS错误，[截图](question-scroll/preview.png)。本地服务起初未重载新API，重载隔离fixture后通过，失败未当通过。
- [进入复制→Next→预览进入](entry-copy/browser.json)：实际PNG生成+2×参数，写入调用共1→2→3，不重复。系统剪贴板写入为instrumented替身，不冒充OS实际粘贴。
- [生产四模式只读GET](question-scroll/production-api.json)：顺序2372题、未做363题、空review/overdue保留当前题1条，各自下一题均等于原Practice详情。临时新账号无Attempt，因此不借此证明有历史记录的所有排序；对应已有PG测试覆盖。
- [清理](question-scroll/production-cleanup.txt)：临时账号删除，0Attempt/0Timing/0UserState，不碰真实用户数据。
- Drill生产构建通过；Timer/依赖未改，无数据库迁移、无题库内容或分类修改。实体Safari/PWA、系统剪贴板、直接外链权限尚无实机证据。

## 回滚与计时

开始16:25:52，首批上线2026-11-13T16:37:33+08:00（701秒）；追加复制后最终2026-11-13T16:47:12+08:00（从原任务开始1280秒）。完整备份/切换时点见production.json，构建/测试日志见子目录。两次发布是因用户中途追加复制要求；没有把第二批计算为第一批一分钟完成。

备份仅用户数据/配置/旧镜像，与开发并行，不导出未变题库。第一次备份`round2-question-scroll-20261113`保留834798e；第二次`round2-entry-copy-20261113`保留44a8603。

仅撤回自动复制、保留滚动预览/状态色，在47执行：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/entry-copy-0d23177/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-entry-copy-20261113
```

撤回两批则使用`releases/question-scroll-44a8603/deploy/ha/round2-rollback.sh`和`backups/round2-question-scroll-20261113`。均只回滚应用/worker/PWA，不覆盖新的学习记录。

## 文件映射

- drill/collection_preview.py、test_collection_preview.py：导航source、逾期标志、只读查询及相关回归。
- frontend/drill/src/lib/listContext.ts、views/QuestionView.vue/PreviewView.vue、components/preview/PreviewQuestionRow.vue及测试：入口/上下文/返回/颜色。
- frontend/drill/src/lib/questionEntryCopy.ts及测试、main.ts、QuestionView.vue、SettingsView.vue：进入手势复制、结果/倍率/标签与原翻题兼容。

后续改进：复用薄overlay，但尽量把多个变更源文件组织为一次COPY，避免旧Docker逐COPY提交多层的额外耗时；不改变本轮已验证的发布镜像。
