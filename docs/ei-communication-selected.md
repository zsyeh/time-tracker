# EI 通信严选 v1

入口 `/communication-selected`，API `/api/drill/communication-selected/`。复用既有虚拟集合、原UUID/fingerprint、题图、答案、勘误、QuestionAttempt和掌握记录；不复制题目，不迁移schema，不向生产数据库导入数据。

## 口径和统计

依据用户提供的五类训练优先级及项目 `drill.ei_syllabus.SYLLABUS['communication']`。优先级不是命题概率，不声称独立核验了2027官方大纲版本。用户给出的五道预测题仅作为筛选模板，本次没有自动作为真题或新题入库。

盘点VPS文档15、21共178条：选入102，待复核16，不纳入60。主分类互斥：

| 考点 | 道数 |
| --- | ---: |
| 无码间串扰/奈奎斯特/升余弦 | 12 |
| 匹配滤波 | 3 |
| PCM/信息量/香农容量 | 25 |
| AM/DSB/SSB频谱与带宽 | 14 |
| 二进制带通调制 | 7 |
| 基带码型/频谱/眼图基础 | 15 |
| 接收性能/误码率基础选练 | 17 |
| FM/PM/多进制基础选练 | 9 |

层次：核心32、进阶17、基础32、低优先级21。题型：计算68、波形/框图分析12、概念22。默认核心且本题题答已具备，没有未处理勘误。可按考点、层次、题型、资料、掌握状态和“前三类重点攻坚”筛选。

重要缺口：当前匹配滤波仅3道原理/公式题，没有完整计算题。保持concept类型，不冒充计算题；为了突出核心公式/原理，保留在核心层可见，并在页面明确标注缺口。接收端含“匹配滤波器”但只求误码率的题归低优先级接收性能，不用其凑匹配滤波大题数量。奈奎斯特条件中的“最佳抽样时刻”也不等于匹配滤波。

## 证据与去重

结构化题直接使用可靠题干。两本书的课后题来自同一《通信课后题与答案》PDF，SHA256为 `9d7b3792b89346c4f871907ba0a057069952f2ff75c827f52276f7bd2f74f8a5`，本地与VPS源文件核对一致。PDF有可靠文字层，本轮不OCR、不逐页交给模型，不重建公式。仅按现有有效question_crop的bbox读取题干文字。

旧书标签`1-1`与新书`1.1`按同书题号规范化去重，优先新版配对书；原记录保留，不删除或合并任何历史进度。只有书源已核对相同才能这样去重，不能推广到不同书本。

保留先前勘误修复的旧书5-22/5-23/5-24及原补图，均归无码间串扰；它们不在新版同号清单中。5-22/5-23附图的source_page_index属于独立reference-pages.pdf，不可拿该页号去主PDF提取文字。本次文字提取跳过这两块reference补图，仅从主PDF题干region获取分类证据；展示继续引用原有效图片。

复杂升余弦冲激响应证明、迫零/均衡设计、部分响应专题、多进制专项证明、依赖上题的独立条件不全条目留复核。FM/PM简单带宽和基本误码率公式应用单列低优先级；A律/非均匀PCM具体编解码也不占用默认核心计算训练。

## 复现、进度和发布

确定性规则在 `drill/communication_selection_rules.py`。生成器只向stdout输出JSON，不连接数据库：

```sh
python3 scripts/build_communication_selected.py \
  --inventory /private/inventory.zlib.b64 \
  --workbook-text /private/workbook-text.json --output selected
```

inventory为元数据JSON的zlib+base64编码；workbook-text为UUID到已提取题干文字的映射。另支持`--output review/stats`。提交索引为`communication_selected_v1.json`和`communication_selected_review_v1.json`，原始全文导出保持私有，运行时不调用模型。

逐题热力图和表头已做/未做/master/两种master率复用当前用户原记录；下一题、顺序题、待复习/到期复习均不离开当前筛选；返回保留筛选并定位原题。原卷和完整版答案功能不变。

先提交GitHub，再VPS fast-forward、合并前端构建、collectstatic与Gunicorn HUP。保留已有题图、数据库、静态哈希和远端未跟踪文件。测试覆盖后端217项、前端22项及手机/桌面8组、原题进度、资料加载、旧勘误三题访问和组内导航。
