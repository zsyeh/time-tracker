# EI 真题逐题显示（2026-10-20）

## 范围与结果

沿用82个原卷记录、1332个 SourceQuestionAnchor，不重建题目或改UUID。

| 真题 book | 本轮独立切分 |
| --- | ---: |
| 电路原理 | 127 |
| 电子线路（数电、模电） | 204 |
| 859 信号与系统 | 351 |
| 合计 | 682 |

剩余650个题号继续使用完整原卷展示，并明确提示切分边界待核对。这不是全量切分完成。
新增815个无损PNG片段、88,410,696字节（约84.3MiB），180dpi保留原始颜色；127道保留多个跨页片段，某些片段包含原页页眉/上下文。没有新增PDF副本、重新OCR、模型识别调用或数据库迁移。

## 边界保护

- 原PDF SHA256校验；复用已有题号索引与OCR缓存，绝不按文本bbox紧裁。
- 每个片段保留原PDF整页宽度。上下边界必须落在全宽无墨迹的空白带中。
- 仅为检测空白带，忽略外侧15%范围内贯穿页面85%以上的扫描边框列；输出图片仍保留这些边框及全部原页宽度。正文中的长导线不忽略。
- 结合全部OCR框，拒绝切穿文字/图注；拒绝把上一题的选项尾行带入下一题。
- 缺号试卷仅允许已核对的连续题号区间，不跨缺失题号或未索引的最后一节。
- 650个待核对条目：523个缺少可确认空白带、74个题号位置非单调、48个缺号区间未确认、4个题号置信度低、1个异常短片段。疑点保留原页，不自动裁掉内容。
- 抽看12组原页/题图片段对照，覆盖三个book、不同年份、电路图、运放、数字电路、信号与跨页版式；发现上一题选项尾行混入的案例后补规则与回归测试。

## 兼容和数据保护

只给既有Question新增question_crop资产，原卷全部965个题图/答案资产及其二进制保留。原始PDF与完整整页图仍可用于重裁。

独立题图优先展示，保留“查看完整原卷／原页”入口。未逐题匹配的答案继续引用原卷答案，并明确标注“原卷参考答案（尚未逐题切分）”，不冒充该题独立答案。

QuestionRevision组卷快照同时引用独立题图与缺省原卷答案，不复制二进制。原卷和单题的掌握记录仍各自独立，不改题目、题号、收藏、笔记、勘误、attempt或userstate。

写入原子事务、稳定source_id、可重跑；拒绝覆盖不同bbox/DPI/来源的既有独立图。重复执行应新增0张图片。原图全量hash、原有Question行hash、做题状态hash在本机写入前后均一致；VPS单独核验其现有数据，不用本机旧状态覆盖VPS的新进度。

## 复现

```sh
python manage.py build_source_question_regions INDEX_MANIFEST \
  --source-manifest ORIGINAL_MANIFEST_A --source-manifest ORIGINAL_MANIFEST_B \
  --ocr-cache OCR_CACHE --output regions.json
python manage.py render_source_question_regions regions.json \
  --source-dir SOURCES_A --source-dir SOURCES_B --dry-run
python manage.py render_source_question_regions regions.json \
  --source-dir SOURCES_A --source-dir SOURCES_B
python manage.py test drill_sources drill.test_linear_selected drill.test_papers --noinput
```

索引旁的`index-review.json`用于缺号审计；缺少该文件时不自动处理不完整试卷。
本轮manifest和抽查清单保存在NUC `/home/eh/ei-individual-20261020/`，VPS的`imports/ei-individual-20261020/`。
57项相关测试通过；真实浏览器覆盖桌面/手机、三个book、跨页题、原卷回看与待核对题的完整原图回退，拦截计时等写请求，不写练习记录。
