# EI 数电严选 v1

入口 `/digital-selected`，接口 `/api/drill/digital-selected/`。沿用既有虚拟集合、原题 UUID/fingerprint、题答图片、勘误和用户掌握记录；不复制题目，不迁移 schema，不向生产导入数据库。

## 优先级与范围

采用用户提供的备考排序及项目 `drill.ei_syllabus.SYLLABUS['digital']`。S/A/B/C 是复习层次，不是命题概率；不声称独立核验了 2027 官方大纲版本。

- S：同步时序分析、组合逻辑分析、组合逻辑设计。
- A：简单同步设计、MUX、编码/译码、计数器应用、触发器分析。
- B：加法/比较、冒险、CMOS 逻辑、卡诺图/补码基础，以及概念小题。
- C：移位/序列、电气特性与级联计数器选练。复杂级联不挤占前三类训练。

盘点 VPS 文档13、20、25共952条：选入328、待复核439、不纳入185（含模电和整卷容器）。选入来源分别为51/70/207。主分类互斥，不重复计数：

| 考点 | 道数 |
| --- | ---: |
| 同步时序分析 | 11 |
| 组合逻辑分析 | 39 |
| 组合逻辑设计 | 16 |
| 简单同步设计 | 17 |
| MUX | 18 |
| 编码/译码 | 10 |
| 计数器应用 | 21 |
| 触发器/波形 | 48 |
| 加法器/比较器 | 16 |
| 竞争冒险 | 7 |
| CMOS 门网络 | 26 |
| 卡诺图/补码基础 | 69 |
| 移位寄存器/序列 | 15 |
| 门电路电气特性 | 15 |

层次：S42、A67、B209、C10；题型：分析94、设计47、基础计算35、概念152。概念小题从主攻层降至B。78道非概念标准题属于六类标准模板（中规模器件含MUX和译码两组）；使用“标准大题分析/设计”组合筛选。默认只显示S级且题答已具备、没有未处理勘误的原题。

## 证据与质量门槛

基础题读取可靠结构化题文。真题复用本地既有OCR缓存，文字证据按本题anchor和几何上最近的下一题anchor截断，避免仅按清单顺序错切。多页疑似整卷片段、缺图/题干不全、数模混合、Verilog/HDL/FPGA、地址译码、复杂异步时序等留复核。2003版本1题1旧索引混合多题，明确暂缓。

文档20原PDF SHA256 `fc3f8f5219d2ab61bd7eb2d6dae07701c3b053101b8b26c179e4c4a4a25fb9b5` 与本地《数电课后题做题本》一致，但文字层为空。仅对已入库76道题的76个题干region做本地Tesseract（chi_sim+eng，150DPI），OCR文字持久缓存；没有整书OCR，也没有识别答案重建公式。现有章节标题“分析与设计”过宽，不能拼进题干据此把所有题误判为设计。

小样本图像核验：题4.1的逻辑门与连线完整；题6.3三个JK触发器共用CLK，确为同步时序分析，题干、反馈连线和时钟完整。界面仍使用原题图，不重新裁切，不把OCR文字作为图像替代。缺图提示不进入严选；“题答已具备”表示资料存在且无未处理勘误，并非全题视觉完美的认证。

确定性规则在 `drill/digital_selection_rules.py`。生成器只输出JSON、不连接数据库：

```sh
python3 scripts/build_digital_selected.py \
  --inventory /private/inventory.zlib.b64 \
  --workbook-text /private/ocr-cache.json \
  --index /private/index.json --cache /private/ocr-pages --output selected
```

inventory为元数据JSON的zlib+base64编码，例题缓存键为`<uuid>-<region-index>.png`；另支持`--output review/stats`及多个`--cache`。提交的索引为`digital_selected_v1.json`、`digital_selected_review_v1.json`，私有全文和缓存不入仓库，运行时无模型调用。

## UI、进度与发布

可筛S/A/B/C、14考点、分析/设计/基础计算/概念、资料和掌握状态。通用集合仅对数电清单额外允许analysis/design，不改变其他严选的题型集合。逐题热力图、已做/未做/master及两种master率都复用当前用户原记录；下一题、顺序题、复习题和返回定位保留当前集合筛选。

GitHub提交后VPS fast-forward，合并前端构建并collectstatic，Gunicorn HUP。保留旧静态哈希、原题图、远端未跟踪文件和全部做题记录，不以本地数据库覆盖VPS。验证包含后端208项、前端20项、手机/桌面14组与设计筛选、原题状态和组内导航。
