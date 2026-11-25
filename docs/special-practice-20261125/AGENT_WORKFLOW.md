# Agent 专练题单推送

## 产品约定

- Drill 与 EI 各有侧栏“专练模式”，`/drill/special-practice` / `/ei/special-practice`。
- 本页显示当前账号最近100份 Agent 固定题单；其他账号不可读取。没有前端 AI 组题入口。
- 开始后就是标准 Practice：原计时、答案、Note、收藏、诊断、掌握/待复习、快捷键和自动翻题偏好不变。题目顺序来自当前题单，不走默认全题库下一题。
- 复用现有题单缓存/滚动预览和恢复，列表→做题→滚动预览→返回题单。无考试倒计时、交卷、答案锁或虚构分数。
- 复用既有 ExamPaper/Item **作为固定成员关系容器**，专用 inactive blueprint，模式weak、版本30000，不要求150分或固定题型比例，不进入考试列表。不新增Schema，不复制题图和学习状态。

## 选题与推送

1. 明确账号、Drill/EI、训练目标、排除条件、数量、知识点范围。读取最近批阅中的五科 `grading.weaknesses` 与 `grading.post_review`，新的纠错结论优先于过时的原始知识漏洞。
2. 选择真实题目 UUID；审查原图和答案，按期望训练顺序排列。不用题号/Attempt ID冒充UUID。
3. 保存 JSON **数组**：`["真实UUID1","真实UUID2"]`，1–1000题，不允许重复、跨工作区或不可练习的题目。题量不足明确报告，不自动放宽。
4. 在47应用容器中运行：

```sh
python manage.py push_special_practice \
  --username '<实际账号>' --workspace ei \
  --key 'ei-frequency-20261125-v1' \
  --title '放大电路频率响应专项' \
  --description '针对16/23题：先定性分析，再计算截止频率。' \
  --questions-json /tmp/selected-question-uuids.json
```

5. 返回固定题单 UUID、created/count、入口地址。用同 key 和相同内容再次执行只返回已有题单；同 key 内容不同则拒绝，不能覆盖用户已做题单。改变成员/顺序用新 key。
6. 确认列表出现、首题正确、下一题遵循选定顺序；**推送和预览不生成 Attempt、Note 或学习时长**。实际作答按已有Practice协议保存。

创建逻辑：`drill/special_practice.py`；Agent 命令 `drill/management/commands/push_special_practice.py`；私有列表 `GET /api/drill/special-practice/`（EI通过 `/ei` 前缀）。首次推送才创建该工作区容器模板；不是数据库迁移。用户锁保证同账号并发推送幂等；整个创建流程事务化。

## 本次复盘

[2026-11-25用户复盘](POST_REVIEW_20261125.md) 是**纠错后理解/建议训练**，不能回写实际考试成绩。12/17/19的纠错满分理解单独保存，不覆盖原逐题得分。66题/300分钟只是建议，用户授权具体选题推送后才创建题单。
