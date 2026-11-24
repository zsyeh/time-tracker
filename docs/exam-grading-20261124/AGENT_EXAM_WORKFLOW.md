# Agent 组卷与纸笔批阅工作流

本规范不新增前端 AI 组卷入口。用户让 Agent 选题→A4 纸作答→把整卷域名分享链接及答卷交 GPT Web 批阅→用户将总结交 Agent→核对题目映射、幂等入库及追加五科薄弱点。

## 读取上下文

1. 核对账号、workspace、分享 digest 对应的 ExamPaper，读取原固定 QuestionRevision，不以题号充当 Question ID。
2. 用户最近已批阅 EI 试卷的 `generation_options.grading` 是考试快照：原始估分、逐题作答/分数比例、复核记录、总用时与五科薄弱点。使用账号过滤、按考试日期与创建时间查找；不得读取别人的数据。
3. `grading.weaknesses` **只有电路原理、模拟电子技术、数字电子技术、信号与系统、通信原理五个键，每个值为一段文本**。每次考试单独保留快照，可纵向比较，不覆盖历史。不把内容混入外观偏好，不虚构掌握率。后续组卷综合最近记录，显式已修复项优先于旧缺陷。
4. 检查真实 QuestionAttempt、QuestionUserState、题型、知识点和 open/reviewing 勘误，不仅匹配 OCR；不改题库原文及分类。

## 出卷提示词（用户选一种，均复用现有 PaperGenerator）

- **薄弱卷**：读取当前账号最近批阅的五科文本，优先P0/P1与复发漏洞，但保持用户要求的科目/题型/分值配额；排除已明确修复的漏洞，逐题人工核图，不让同知识点挤占整卷。
- **Need to review卷**：按该账号现有待复习状态（最新review及review_later），再交叉科目、题型与用户筛选；缺额明确报告，不静默扩大到全库。
- **新图卷**：使用用户未浏览/未做过的真实题图优先；若没有可靠的“浏览过”日志，只能保证未有作答记录，必须说明这一证据边界，不将题号变化当新图。
- **随机卷**：在明确有效范围内固定seed随机，排除开放勘误；尊重掌握/待复习/近期做过等用户勾选，题量不足提示。
- **均衡卷**：892真实考纲分值与五科比例优先，分散章节/知识点，实际题型按已有人类校正分类；不要把训练模板题数宣传为官方题数。

共同要求：先内置工具生成→检查题/答案原图及可用性→不合适则用更换本题API替换→完成所有调整后再发布域名分享。已分享卷固定，不静默换题。不给未请求的候选自动加收藏、严选或待复习。

## 批阅导入

- 私有 JSON 的每行保留 `position` + `question_uuid`、用户答案、参考、原5分制得分比例、四态(correct/incorrect/partial/incomplete)、简短Note、优先级及核实证据。
- 先核对数据库真实分值，再按比例换算；保留原始AI分数及后续改判，不称官方成绩。没有原手写答卷时只核参考与映射，不能声称重阅过答题纸。
- 不伪造逐题计时、不新建学习Session。考试条目本身即本次逐题历史；默认不再创建一套QuestionAttempt，避免重复计数或一次正确自动掌握。
- 非满分项设置现有 `review_later` 并追加Note；保留旧Note、收藏、掌握记录。用户明确确认“已掌握”时才能用幂等submission_key新增显式掌握记录。
- 复核发现原题多解或标准答案冲突，保存用户改判、初判和证据；不改共享题库答案。后续同卷新改判不得盲目重跑不同JSON，先比对当前import_digest，事务中只改用户指定题及汇总，补充修订日志。
- 先dry-run，再备份用户/目标行，最后apply。相同输入重放返回unchanged，不重复Note、待复习、掌握或题目次数。

```sh
python manage.py import_exam_grading --username USER --share-token TOKEN --input /private/grading.json
python manage.py import_exam_grading --username USER --share-token TOKEN --input /private/grading.json --apply --backup /private/unique-backup
```

命令默认只验证；输入、身份、答题内容和备份不提交Git。不同JSON覆盖已有批阅会被拒绝，必须先明确审阅差异。`grading` 只出现在账号鉴权后的review API，不进入公开分享或普通未批阅考试页。
