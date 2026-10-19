# 原卷整图 + 独立小题进度

新增独立 app `drill_sources`，没有修改已有 drill 表结构。迁移依赖共同的 drill.0020，兼容本机与 VPS 不同迁移链。

`SourceQuestionAnchor` 把普通 Question 关联到原卷 Question、现有 QuestionAsset 和归一化纵坐标。原图仍只保存一份；小题继续使用现有 QuestionAttempt、笔记、收藏和勘误接口。整卷历史记录不继承为每道小题的掌握记录，也不删除。

前端显示完整题目图片，题号按钮叠加于原图。热力图中已建索引的小题直接进入练习并滚动至题号；图片宽高预留空间以避免加载后定位偏移。手机端有随滚动保留的当前题号、待复习、掌握并下一题和定位按钮。参考答案明确标为整卷参考解析，未声称逐题答案已切分匹配。

## 本次索引

| 书本 | 独立题号 |
| --- | ---: |
| 电路原理真题 | 219 |
| 电子线路真题 | 676 |
| 859 信号与系统真题 | 437 |
| 合计 | 1332 |

82 个已有原卷/章节记录。34 个记录存在题号缺失或章节识别问题，保留可练习的整卷入口，页面显示索引待补全提醒。其余原卷仅关闭 is_practiceable 以避免热力图同时计入整卷和全部小题，原图与历史记录保留。以上题号为确定性 OCR 规则生成，尚不代表所有老卷题号经过人工逐个核准。

索引和复核文件：

- 本机 `/home/eh/ei-page-tracking/index-manifest.json`、`index-review.json`
- VPS `/root/time-tracker/imports/source-question-tracking-v1/`
- OCR 与窄栏识别缓存：本机 `/home/eh/ei-page-tracking/cache/`、`margins/`

已有图片未重新裁剪或增加。本次导入 `new_image_bytes=0`。两端索引 fingerprint、asset.source_id、y 的规范化哈希相同：`84108b6a48041eddb4287b851ba67e2156cdcbd839bf9da92339a552250f4b27`。

## 重跑

```sh
python manage.py migrate drill_sources --noinput
python manage.py index_source_questions /path/to/index-manifest.json --dry-run
python manage.py index_source_questions /path/to/index-manifest.json
python manage.py test drill_sources --noinput
```

命令先校验全体数据，再通过 transaction 导入；fingerprint 和稳定 UUID 保证幂等。重复导入只更新定位，不覆盖用户进度、笔记或自定义题目内容。仅支持指定 parser_strategy 的本次 EI 原卷，拒绝跨工作区/跨来源图片。

修改 manifest 的 y 后可重跑定位，不需重新生成图片。补充题号需使用稳定 key，避免改变已练习题的身份。导入新学科应先确认实际题号规律，不能直接假设与此批相同。

## 验证与部署

- 本机 PostgreSQL 上 4 项后端测试通过；VPS 用隔离内存 SQLite 跑同样 4 项测试通过，未提高生产 DB 建库权限。
- 浏览器测试：1440×900、390×844；热力图跳转定位、下一题定位、小题独立写入均通过。
- 两端真实 HTTP 认证接口检查独立热力图格数、题目详情与现有 PNG 可读取，检查不写 QuestionAttempt。
- VPS 通过 Gunicorn HUP 平滑加载；未停止 PostgreSQL、Nginx、SSH。
- 本机容器运行文件和静态资源已更新，源码改动保留在工作树；未提交或推送 Git。重建镜像时需包含新增 app、迁移及前端源文件，不要只复制热力图页面。

当前是两端执行同一幂等索引导入，不是新增了持续双向进度同步服务。
