# 严选题知识点补充：本机 API 脚本

2026-11-10 已完成并写入 47 生产数据库。无需部署应用、迁移数据库或重启服务。

## 本次结果

| 范围 | 严选题总数 | 补充知识点 | 保留已有有效知识点 |
|---|---:|---:|---:|
| Drill | 963 | 608 | 355 |
| EI 五科严选（全部层级） | 1,227 | 661 | 566 |
| 合计 | 2,190 | 1,269 | 921 |

- 最终采用 Terra 1,266 道、Sol 3 道；未解决 0 道。
- 266 道标为 approximate，作为审计信息，不阻止导入，也不是经人工测得的错误率。
- 识别“严选题”、年份真题、背诵简答、课后题章节编号等占位项；已有有效知识点保持原样。
- 数学复用同一本题册已有知识点。EI 复用现有五科标准题册的知识点；混合电子线路题册允许模电、数电两个现有目录，保留原严选科目归属。
- 默认 `gpt-6.1-terra`；未解决时补充题图，仍未解决再用 `gpt-6.1-sol`。允许就近或较粗的分类，不新增知识点。

本次逻辑 API 调用 227 次。API 返回 input_tokens=1,279,271、output_tokens=48,457（其中 reasoning_tokens=1,872，已包含在输出数中）。按标准 Token 价估算 $1.552；不是账单金额，可能不包括另计的缓存写入或价格调整。费率依据：[Terra 官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-terra)、[Sol 官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol)。

## 数据边界

只更新 Question 的三个已有字段：

- `similarity_topic_id`：指向现有 QuestionTopic。
- `topic_classification_source`：`api-topic:terra:sel1110a` 或 `api-topic:sol:sel1110a`。
- `topic_classification_confidence`：null，不把模型自评分当成真实正确概率。

原 `topic_id` 保留原题册章节/年份位置。Question UUID、题号、书籍、fingerprint、题干、题图、答案、题型、严选清单及知识点树都保持不变。作答、Note、诊断、复习、计时等用户表不写入。

导出不包含私人 Note 或作答记录。API Key 仅从本机 `~/.api_key_secret` 读取，要求权限 600，不打印或上传。官方 SDK 固定连接 `https://api.openai.com/v1`，`store=False`。API 分类只在 NUC 运行，47 保持唯一业务写入站，RainYun 不写数据库。

## 文件与运行

- 独立 API 脚本：`scripts/classify_selected_topics.py`
- 本机启动入口：`scripts/run_selected_topics.sh`
- 生产数据工具：`python manage.py selected_topic_data`
- 数据选择/导入保护：`drill/selected_topic_classification.py`
- 本机工作目录：`/home/eh/selected-topic-audit/`
- 当前依赖环境：`/home/eh/learning-type-audit/.venv/bin/python`，OpenAI SDK 2.54.0。

API 使用内容哈希缓存，按知识点目录分批；默认文本每批 20 道、图片每批 4 道，并发 20，远端只读题图提取最多并发 3。题图按 SHA-256 验证，已有本机图片缓存可直接复用。重启仅重试未解决或内容变化的记录。

```sh
# 本机：完整运行、断点续跑（此默认工作目录已完成）
scripts/run_selected_topics.sh

# 本机：查看日志和结构化进度
tail -f /home/eh/selected-topic-audit/run.log
cat /home/eh/selected-topic-audit/status.json
```

`results.jsonl` 为追加式历史缓存；`import-candidates.jsonl` 是去重后的正式导入文件，严格按题目 ID、UUID、workspace、内容哈希和允许的知识点 ID 验证。

### 新一轮增量运行

使用新工作目录和新导出路径，保留本次审计资料。导出/导入/回滚命令在 **47 的生产 Django 环境** 执行；API 命令在 **本机** 执行。

```sh
# 47：导出仍为空或占位的项目，不修改数据
python manage.py selected_topic_data export --export /secure/new-run/export.json

# 将导出复制至本机后，本机跑 API
python scripts/classify_selected_topics.py \
  --input /secure/local-new-run/export.json \
  --output-dir /secure/local-new-run --concurrency 20

# 将结果复制回 47 后：先 dry-run
python manage.py selected_topic_data import \
  --export /secure/new-run/export.json --results /secure/new-run/import-candidates.jsonl

# 47：备份后事务导入，batch-id 最长 12 字符
python manage.py selected_topic_data import \
  --export /secure/new-run/export.json --results /secure/new-run/import-candidates.jsonl \
  --backup /secure/new-run/rollback.json --batch-id nextbatch --apply
```

本次 47 已保留工具挂载启动器：
`/var/snap/docker/common/time-tracker-ha/backups/selected-topics-20261110/remote-run.sh`。
它以已部署镜像启动 256 MB 上限的临时容器，将维护工具只读挂载到容器内；无需替换运行中的应用镜像。该目录映射为 `/audit`，可用 `bash remote-run.sh export --export /audit/export-next.json` 等方式执行上面的数据命令。

### 扩大候选目录时复用

`--reuse-export previous-export.json` 仅在题目内容完全相同、旧目录是新目录的严格兼容子集、原选中知识点仍有效时复用结果；保存旧哈希与复用原因。新目录移除/修改知识点、题目内容改变、未解决结果，都不能这样复用。本次扩大混合电子线路目录后，仅对 5 道未解决项目重跑 API。

## 校验、备份、回滚

- 11 项测试通过：默认与降级模型、输出校验、占位识别、只补缺失分类、跨目录拒绝、只读导出、银行/学习数据保留、幂等、回滚、冲突保护、混合科目和缓存扩展。
- 生产 dry-run 1,269 道匹配通过。
- 真实数据库事务中完成 1,269 道更新及精确恢复演练，整体事务回滚，无持久测试修改。
- 导入前已备份 Question/QuestionTopic custom 归档，并通过完整 pg_restore 读取校验。
- 正式写入前持久保存每道题的前后字段及模型审计信息；全量回读校验后提交。再次执行更新数为 0，验证幂等。
- 保护哈希覆盖原题字段、题图元数据、书籍、知识点树和严格的严选成员标识。只允许三个分类字段变化。
- 正式域名导入前后校验严选成员、顺序、数量和新知识点读取；登录会话有效。未改生产服务或代理。

生产备份目录：`/var/snap/docker/common/time-tracker-ha/backups/selected-topics-20261110/`，本机亦保存 rollback.json、SQL 归档、export.json、模型结果和报告。

```sh
# 本次回滚，只恢复知识点分类，不恢复整库或覆盖用户学习数据
ssh root@47.95.10.128 \
  'bash /var/snap/docker/common/time-tracker-ha/backups/selected-topics-20261110/remote-run.sh rollback --backup /audit/rollback.json --apply'
```

目标存在后续修改时整笔拒绝回滚，避免覆盖人工修正。不要直接恢复整库覆盖后来的学习数据。
