# EI / Drill 解题能力诊断

EI 与 Drill 共用实现，但所有查询都按当前登录用户和当前主机对应的
`QuestionDocument.workspace` 隔离。两个系统不会合并统计。

## 数据口径

- 只有成功保存的 `QuestionAttempt` 才进入统计。
- 旧记录的新增诊断字段保持 `unknown` / `NULL`，不会被推断成独立正确。
- 首次独立正确率：每题第一次有效作答中，明确为独立且正确的题数 / 第一次有效作答题数。
- 二次独立正确率：首次未独立做对的题中，第一次后续独立作答正确数 / 已发生该次独立重做的题数。
- 错误复发率：至少两次带主错误标签的题中，后续再次出现既有主错误类型的题目比例，按题去重。
- 方法启动失败率：主错误为 B2 或 B3 的作答数 / 有明确主错误的诊断作答数。
- 无样本时比例返回 `null`，前端显示 `—`，不会伪装成 0%。
- 查看提示或完整解析后，同一轮即使标记正确，也强制不算独立正确。

## 闭环复习

第一次未独立做对会创建 D0/D1/D3/D7 复习计划。每次作答均新增 Attempt，
不会覆盖旧诊断；独立正确后进入下一检查点，失败则保留当前检查点。
计划可暂停、恢复、延后或改为自定义间隔。

## 接口

- `GET /api/drill/diagnostics/`：能力看板；支持 `days=7|14|30|50|90` 或 `start/end`。
- `GET /api/drill/diagnostics/questions/`：按错误标签或到期状态进入题目队列。
- `GET|POST /api/drill/questions/<uuid>/attempts/`：历史诊断与幂等提交。
- `PATCH /api/drill/attempts/<id>/diagnosis/`：修订诊断标签，不替换 Attempt。
- `PATCH /api/drill/questions/<uuid>/review-plan/`：暂停、恢复、延后或调整复习间隔。

## 迁移兼容性

迁移 `0026_attempt_diagnostics` 只增加可空/有默认值字段、两个新表和索引；
迁移 `0027_attempt_method_notes` 只增加两列文本字段。没有数据回填、题目重建、
UUID 修改或历史记录删除。迁移可通过 Django 反向迁移回滚结构，但生产回滚前应先保留数据库备份。

题目自由文本的唯一可编辑来源是 `QuestionUserState.note`。旧版 Attempt 中的
`note/correction_note/knowledge_note/first_step_note` 只作为不可变历史证据保留，
新前端不再提供四个并列输入框。上线前必须先执行 dry-run：

```bash
python manage.py merge_attempt_text_into_notes
```

确认备份和脱敏统计后，再在 47 唯一写入节点执行：

```bash
python manage.py merge_attempt_text_into_notes \
  --apply --audit-file /var/backups/time-tracker/note-merge-audit.json
```

命令按用户与题目严格隔离、以双换行拼接不同内容、重复执行不重复追加，并在
合并结果超过 20,000 字符时整批拒绝。回滚会先确认 Note 未被用户继续编辑：

```bash
python manage.py merge_attempt_text_into_notes \
  --rollback /var/backups/time-tracker/note-merge-audit.json
```

## 验证

```bash
DATABASE_URL='' DATABASE_PATH=/tmp/diagnostics.sqlite3 \
  .venv/bin/python manage.py test \
  drill.test_diagnostics drill.test_practice_trends drill.tests.DrillApiTests

cd frontend
npm run build -- --config vite.drill.config.ts
```
