# EI 复核试卷与考试换题发布（2026-11-21—22）

## 交付

- 应用提交：`537d80f`，已推送、上线；生产镜像 `time-tracker-ha:20261121-exam-replace-537d80f`，最终健康检查 healthy。
- Drill / EI 考试页及全屏页新增 **更换本题**，保持当前题号、科目、题型和分值；先确认，保存排队中的备注，换题后收起答案。
- EI 复核卷：`f2ab8798-0526-4a18-89af-802af6e664ae`。
  - [账号内打开考试](https://47.95.10.128/ei/papers/f2ab8798-0526-4a18-89af-802af6e664ae)
  - [整卷分享](https://ei.ehzsy.site/share/paper_wWIBwo-dCR0NwVPNA54zfBEvHKRy-sN5pk-tr2N9p-Y)
- 原卷 `64333a87-4414-48ae-9067-6c08dc1407ee` 在停顿期间已被用户开始使用，所以没有重置或覆盖；新建无训练状态的复核副本，实际调用新换题接口替换 12 题，再固定修订版本。
- 勘误 #64–92 共 29 项：**28 resolved，1 open（#90）**。#90 的原 PDF 本身缺图，不能伪造补图；对应题已从复核卷排除。新候选同样排除 open / reviewing 勘误。
- 本次续做没有开启、唤醒或委派任何 Subagent。

## 考纲与组卷依据

实际阅读用户已上传 `892 电子信息专业综合.pdf`（2025-06-30）：180 分钟、150 分，电路、模电、数电、信号、通信各约 20%；选择 / 填空 / 简答 / 计算证明分值为 30 / 30 / 30 / 60。**考纲没有规定 30 道题**，当前训练模板自定为 10 选择、10 填空、5 简答、5 计算，每科 30 分。不能把此题量当作官方真题数量。

初卷经真实创建 API、固定 seed 生成；原题和答案贴图逐题检查，不依赖混乱 OCR。复核不是宣称达到正式命题难度标定；缺少真实考生用时数据，180 分钟适配仍需实际训练反馈。

### 实际替换（题号 → 新 Question ID）

|题号|新题 ID|原因 / 选择|
|---|---:|---|
|2|6123|替换实际为填空的旧分类题，改为晶体管增量选择|
|13|6122|晶体管识别，减少过长复合填空|
|14|6162|滤波器填空，替换判断题|
|16|6244|完整频响图及三个判断空，源答案错误概述另登记 #92|
|18|7899|补码运算，替换波形作图大题|
|20|8320|正余弦傅里叶变换，替换归入信号科目的 PCM 题|
|23|6221|频响定性简答，减少不合理计算工作量|
|26|7093|RL/RC 换路，替换考纲依据不足的二端口参数题|
|27|6111|单片 74161 状态与自启动，替换过长触发器分析|
|28|7200|二阶系统初始状态与系数，替换过于单薄的 12 分题|
|29|5804|条件完整的三角频谱，替换缺 g(t) 图题|
|30|6190|条件自足的基带题，替换依赖缺失 H(f) 图题|

保留题修订版本也已重新固定到复核卷；原卷固定版本不变。分享发布后不能继续更换此卷题目，以保证同一分享链接题目和顺序固定；需要调整时生成新卷。尚未分享的个人试卷可以正常换题。

## 换题接口与数据保护

`POST /api/drill/papers/<uuid>/items/<position>/replace/`，Drill / EI 使用各自 workspace 前缀及上下文。

```json
{"expected_question_uuid":"当前真实 Question UUID","question_uuid":"可选：指定候选 UUID"}
```

- 不传指定候选时复用现有组卷选择逻辑；新卷持久化原始筛选 `generation_options`，不静默放宽。
- 同科目、题型、分值；排除当前整卷及此前已换出的题；无候选明确提示。
- 所有权及 workspace 隔离；整卷行锁避免两处同时换入重复题。
- 旧题不匹配返回 409，已分享返回 409；历史无筛选元数据的旧卷明确显示宽松筛选警告。
- 仅重置被替换题在当前考试中的自评分、备注等；不写全局掌握、收藏或 QuestionAttempt。
- 备注 PATCH 带 expected_question_uuid；旧异步备注不能保存到新题。换题、分享和备注操作共享并发保护。
- 增量迁移 `drill.0045_paper_generation_options`：只增加 ExamPaper JSON 字段，不迁移/删除学习记录；应用回滚时保留该兼容列。

## 勘误处理

|批次|勘误|处理|
|---|---|---|
|已有待处理|64–74|缺失题干、错裁、答案混入题干、公式/原答案错误；以原 PDF 修复，必要时显式标记复核勘误图片|
|本卷图片与答案|76–78、81–83、86–89、91|清除广告/后页标题/泄题答案；恢复缺失图、纠正电感符号与带宽单位|
|类型/主题/续页|75、79、80、84、85|补充真实 PDF 续页；更正填空/判断/大题分类与 PCM 通信归属；移除与原题极性不一致的重复答案图|
|新候选|92|原答案概述误把(c)写成(a)，保留扫描中三条正确推理及(a)/(c)/(c)结论，去掉错误概述和下一节标题|
|待源文件|90|原 PDF 本身无关键三角脉冲图。保持 open，换题避开，等待权威完整源|

- 原图二进制、旧 asset PK、所有旧 QuestionRevision 保留。旧图只改为 `_superseded`，原有试卷仍由固定 RevisionAsset 读取旧内容。
- 非原版扫描的数学纠错图，显式标明“复核勘误 / Reviewed correction · 非原版扫描”；由确定性 KaTeX 排版，不用生成图片冒充原卷。
- 类型更正通过现有带 expected_updated_at 的 API，追加 QuestionExamTypeEdit 审计，不直接抹除分类历史。
- 逐批记录修复前后 Attempt / UserState 数量，相同；复核换题及分享前后 Attempt 不变，并核对原卷条目完全相同。

## 验证与时刻

- 21 个相关 PostgreSQL 后端测试通过（2.670 秒），含真实双线程竞争、权限、workspace、筛选不足、旧备注、已分享锁定。
- 4 个换题前端测试通过；TypeScript 与生产 Vite 构建通过，Vite 7.01 秒。无需因文档重复构建。
- 生产实际 12 次指定换题通过；每次旧 expected UUID 重放均返回 409；最终 30 个唯一题、150 分、五科配额不变。
- 新卷固定修订前逐图校验 SHA、题图和答案都存在、没有未关闭勘误。公开分享返回 200、30 个单题域名链接、答案默认折叠。
- Playwright Chromium：390×844 Light、1180×820 Dark；真实生产题图 decode、横向无溢出，结果及截图同目录。桌面宽度遍历全部 30 道题干图；手机抽检首尾。不是实体 iPad Safari / PWA 验证。
- 回滚程序默认仅验证：三批 26 道内容修复、3 个分类及 #92 均在生产通过只读检查；没有实际回滚已修复内容。
- 首次生成 API 单次 1170ms，不是 P50/P95；浏览器总遍历时间含下载，不当作接口性能指标。
- 应用切换：2026-11-21 20:50:03–20:50:31，28 秒。后续内容复核有独立工作段；中间跨夜配额中断不计作连续开发。
- 续做工作段：2026-11-22 03:57:45 开始；本文最终提交记录完成时刻。数据修复、分类、最终复核及备份独立记录，不声称“一分钟完成整卷审题”。

## 备份、磁盘与回滚

47 最终检查剩余 11 GiB，使用率 72%。仅备份用户/学习/试卷 + schema/config、实际受影响题目和原图，没有重复完整题库。

宿主备份根目录：`/var/snap/docker/common/time-tracker-ha/backups/`：

- `exam-replace-20261121`：功能上线前用户/schema/config 备份。
- `exam-review-final-20261122`：本轮续做前用户数据 dump（691 KiB）、schema（177 KiB）、配置及镜像记录，`verify-exit.txt=0`。
- `errata-review-20261121-existing`：已有 11 项 plan、backup/rows.json、原二进制、applied.json。
- `errata-review-20261122-exam`：新 11 项，同上。
- `errata-review-20261122-remaining-v2`：4 项，同上，另含 `metadata-before.json`（3 类别与报告原状态）。
- `ei-reviewed-final-20261122`：#92 原图、前后修订、最终新卷 pin-result、share/result。

### 应用回滚

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/exam-replace-537d80f/rollback.sh
```

恢复 `time-tracker-ha:20261121-pwa-keyboard-92822b1` 与旧配置，不 drop 0045，不重置数据库，不修改独立后台队列镜像。脚本可执行及 `sh -n` 已检查。

### 内容回滚（按批次，有意执行才追加 --apply）

脚本 `rollback_errata.py` 已存宿主 `backups/rollback-errata-20261122.py`，`rollback_extra.py` 存为 `backups/rollback-extra-20261122.py`。先恢复备份文件进容器再运行，避免依赖易丢失的 `/tmp`。示例在宿主执行：

```sh
D=/usr/local/bin/time-tracker-docker
B=/var/snap/docker/common/time-tracker-ha/backups
$D cp "$B/rollback-errata-20261122.py" time-tracker-ha-web:/tmp/rollback_errata.py
$D cp "$B/errata-review-20261122-exam" time-tracker-ha-web:/tmp/restore-exam
$D exec -e PYTHONPATH=/app time-tracker-ha-web python /tmp/rollback_errata.py /tmp/restore-exam
# 上一步全部 verified 后，如确实要撤销此批，才在同一命令末尾加 --apply。
```

其他两批替换对应目录；分类使用 `rollback_extra.py metadata /tmp/metadata-before.json`，#92 使用 `rollback_extra.py crop92 /tmp/恢复后的ei-reviewed-final-20261122`；同样默认验证、显式 `--apply` 才修改。

内容脚本核对当前 revision、旧二进制 SHA、报告状态后原子恢复字段/asset 类型，并保留新增二进制与固定纸卷；发生后续编辑即拒绝，不能强制覆盖。分类回退走既有 API，追加审计，不删历史。回滚内容不会自动重写已经分享的固定卷；若固定卷本身需撤销，使用既有撤销分享/删除个人套卷路径，**不删除 QuestionRevision、不全量恢复用户数据库**。

## 未覆盖 / 限制

1. #90 仍待权威缺图源；不是已完成修复。
2. 真机 Safari/PWA 手势、系统剪贴板未在本轮复测；Chromium 尺寸仿真不能替代。
3. 此卷是覆盖考纲的练习卷，不保证正式命题难度或实测完成时间；原扫描自身的非致命印刷错误仍可能存在。
4. 已分享卷刻意禁止换题，避免外部链接静默变卷。旧卷筛选元数据缺失时会警告，不能声称恢复了未知原始筛选。
5. 私人工作目录保留完整证据和源图；仓库只存报告、脱敏统计、回滚程序及少量验收截图，不提交账户、Cookie、完整题库或 Base64 资源。

## 文件变更清单

应用提交 `537d80f`：

- `drill/models.py`、`drill/migrations/0045_paper_generation_options.py`
- `drill/paper_generator.py`、`drill/serializers.py`、`drill/urls.py`、`drill/views.py`
- `drill/test_paper_replace.py`
- `frontend/drill/src/views/PaperExamView.vue`、`PaperExamView.replace.test.ts`
- `frontend/drill/src/components/PaperSelfEvaluation.vue`

交付记录提交：本目录报告、脱敏 `review-evidence.json`、`browser-check.json`、四张验收截图、两个默认只读回滚程序，以及 `docs/DEVELOPMENT_LOG.md`、`docs/MASTER_UI_UX_REBUILD_PLAN.md` 增量。

最终验收记录：2026-11-22 04:13:44 +08。本续做工作段约 16 分钟，含真实源图复核、数据修复、最终分享遍历与回滚验证；不是普通样式发布。两尺寸线上浏览器遍历合计约 23 秒，不冒充所有审题工作的耗时。应用构建本轮续做 0 次，沿用已上线产物；文档不触发重新发布。
