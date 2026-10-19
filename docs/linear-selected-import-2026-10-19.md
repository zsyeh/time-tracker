# 数二线代臻选题导入（2026-10-19）

## 先对齐

VPS 最新基线 `1d1059a` 加上此前运行中但未提交的 EI 原图小题索引功能，已先整理为 `188f441`。本机原 `/home/eh/src/time-tracker` 的未提交改动保持不动；本次独立工作树为 `/home/eh/src/time-tracker-aligned`。

核对发现原每日任务报 `Unknown command: sync_content`，并非处于正常同步状态。本轮执行的是经过验证的一次性对齐，不代表该旧定时任务已经修复。旧实现已从 MCP 旧代码归档找回，留作后续修复参考，不直接启用其旧版删除/冲突策略。

对齐前本机 264 条做题记录均已存在于 VPS 的 879 条记录中；没有本机独有的题目或做题事件。本机独有的少量用户状态均是无笔记、无收藏、无待复习标记的空计时缓存。

先备份本机完整数据库，再使用 VPS 的 drill 相关表快照，在单个事务中恢复本机。保留本机非 drill 业务数据。快照 SHA-256：`df560e66a8c13103756b4bf80db15fcef5d4082fd1b627c4dde0b731d75bead4`。

导入开始前，两端逐条一致：22 个文档、1355 个主题、8731 道题、879 条做题记录、831 条用户状态、36 个标记、8 条 correction、2 张试卷与44个试卷题目。对应私有审计与备份位于 `/home/eh/linear-selected-20261019/`，不要提交其中用户数据。

## PDF 与版式

- 原文件：`/home/eh/Downloads/2414586761_ehzsy/【A4留白】数二线代臻选题 .pdf`
- SHA-256：`d3f78eb73684cc01abb224f076fb082a31a4f79ac5dd6a1ee089ed1c6ede6042`
- 原文件 2,133,042 字节，192 页。
- 355 个题目书签与正文 `#001` 至 `#355` 一一匹配，无缺失、无重复。
- 176 个题目页：42 页一题、89 页两题、45 页三题。
- 16 个封面、前言、目录或章节过渡页不作为题目；无需 OCR。
- 按实际书签和正文数题，不使用前言中与当前正文不一致的旧题量。
- 抽看 PDF 12、29、97、138、191、192 页，确认一页多题、A4 留白、首尾页及矩阵/公式布局。

| 章节 | 独立题数 |
| --- | ---: |
| 行列式 | 40 |
| 矩阵 | 75 |
| 向量 | 31 |
| 方程组 | 74 |
| 特征值与特征向量 | 64 |
| 二次型 | 71 |
| 合计 | 355 |

## 存储与展示

复用 QuestionDocument、QuestionTopic、Question、QuestionAsset 与 SourceQuestionAnchor。最初按原页共享展示，用户随后明确要求逐题展示，最终已为每道题建立独立题图与逐题答案，原有共享页和定位索引仅保留为来源，前端优先显示独立题图。

共有355个可练习小题、176个隐藏的原页来源记录，以及176张整页图。题图共14,990,296字节（约14.30MiB），原PDF约2.03MiB，两者约16.33MiB，另有少量SQL索引和元数据。原始 PDF 永久保存，页码、完整 bbox、DPI 与题号纵坐标可追溯；图片可由原 PDF 重新生成。

补充下载百度 PCS-Go `/我的资源/线代臻选/【通用答案】线代臻选题.pdf`，345页、65,597,878字节，SHA-256 `dcce808547510fd5fe1a4e9765ebf9b781bc5a2c97f76dcd9a39780e6dc11411`。前六章355个叶书签与题目355条的章节、题源和顺序全部匹配；数学一专项不关联。只做明确字符等价归一化（全半角、🐙/张宇、八套卷/八套及一处“第一套套”重复字），不做模糊题源猜测。

新增355张独立题图、574个答案片段，其中198道答案跨页；新增图片99,613,524字节（约95MiB），加配套原PDF约157.56MiB。连同原题目本与共享页，累计约173.89MiB，SQL索引另计。题目始终保留整页宽度，以模板题号栏分界；答案以所有章节/题源标题分界，图片实际bbox优先于默认页脚线，任何图片跨题间边界会报错停止而非静默切掉。原题UUID、热力图及掌握记录不变，网页一次只显示一道题，展开的也是该题答案。

抽查17道逐题预览（#001/#003/#028/#040/#041/#075/#103/#110/#146/#153/#174/#198/#221/#263/#284/#344/#355），检查题干、矩阵、选项及答案开头；规则遍历全部574个答案片段，保证嵌入图片不被上下边界切断。第90页曾有高图片超过默认760pt页脚线，已按实际图框扩展，保留到底部767.88pt以下。

## 重跑与测试

```sh
python manage.py import_linear_selected_pdf /path/to/linear-selected.pdf --dry-run --manifest-output manifest.json
python manage.py import_linear_selected_pdf /path/to/linear-selected.pdf
python manage.py import_linear_selected_answers /path/to/linear-selected.pdf /path/to/linear-answers.pdf --dry-run --manifest-output paired-manifest.json
python manage.py import_linear_selected_answers /path/to/linear-selected.pdf /path/to/linear-answers.pdf --manifest-output paired-manifest.json
python manage.py test drill.test_linear_selected drill_sources --noinput
```

导入前全书书签/文字层交叉验证，写入使用 transaction。稳定 fingerprint/UUID 保证重跑不重复；已存在的题目、用户编辑、笔记与做题记录不覆盖。修改渲染 DPI 时拒绝直接覆盖既有图，应使用重新渲染工具。

16 项后端测试覆盖解析、题源层级、dry-run 零写入、整页边界、共享/独立图片、逐题答案、幂等、独立掌握、旧/新严选热力图、组卷图片、异常原子回滚，以及局域网换IP后的工作区路由。另61项现有回归测试使用公开域名配置通过。

本机真实浏览器在1440×900与390×844下验证严选热力图、首末题与图片加载；测试仅临时创建会话并拦截计时写请求，不写入用户练习数据。

另发现旧本机容器按固定172.20.10.2识别工作区，而当前LAN已变更。现仅对采用disabled.invalid标记的独立本机容器，按私网请求和容器角色识别drill/ei；私网登录使用同机相对路径。VPS共享服务仍按域名识别，未改成全站通配工作区。
