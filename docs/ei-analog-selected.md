# EI 模电严选 v1

入口 `/analog-selected`，API `/api/drill/analog-selected/`，仅 EI。沿用电路/信号严选的只读虚拟集合、资料门槛、用户隔离和筛选内导航。引用原 UUID/fingerprint，不复制题目、答案、图片或做题记录；没有 schema migration。

## 筛选口径

以用户提供的九类备考优先级、项目 `drill.ei_syllabus.SYLLABUS['analog']` 为依据，不是命题统计概率，也不声称独立核验了 2027 官方大纲版本。核心为静态与小信号、深度负反馈、运放综合；差分、高频、多级和滞回为进阶；功放、二极管及概念小题为基础。

盘点 VPS 文档 12（模电基础）、17（例题精解）、25（混合电子线路真题）共 1030 条。选入 270，待复核 532，不纳入 228（包括数电和整卷容器）。选入来源为 49 / 49 / 172。以主分类计数，辅助标签不重复建题：

| 主考点 | 道数 |
| --- | ---: |
| 晶体管静态/小信号 | 45 |
| 负反馈/深度负反馈 | 55 |
| 集成运放运算 | 46 |
| 差分/电流源负载 | 33 |
| 高频/米勒/上限频率 | 19 |
| 多级放大 | 15 |
| 滞回比较器 | 4 |
| OCL/推挽功放 | 24 |
| 二极管分段模型基础 | 29 |

核心 63、进阶 30、基础 177；17 道带静态+动态组合标签，其中主分类晶体管组 9 道。概念、填空、选择、判断和简答归基础，不冒充计算题。默认核心且本题题答已具备，可另筛计算题、未做/待复习/已掌握及组合题。

## 证据与缓存

基础题使用结构化题文。真题使用已有 OCR 缓存并以自身 bbox/下一题 anchor 限定文字范围。旧题没有可靠题文时留复核，不按章节号猜电路。

原模电 PDF SHA256 `1b118a8a445d2782f17e72dabe1b1317ba39f590b5d5ab1383d08f48e1216469` 与 VPS 文档一致，但没有可靠文字层。因此仅对已入库 69 道例题的 104 个现有题干 region 做本地 Tesseract OCR（150 DPI，chi_sim+eng），结合已有逐题审定考点；不是整书 OCR，不读答案猜题，不用 LLM 重建公式。原 PDF、私有导出和 OCR 缓存不提交仓库，不上传新 PNG，不改现有裁图。

最小视觉核对确认：例7.3.5(b,c)含正反馈滞回比较器，例7.3.6(b)为滞回回线，归滞回组而不是线性运放核心组。普通/窗口比较器未确认滞回时留复核。例2.3.5依赖例2.3.4的前提和图，单独列待复核，不放进独立刷题组。现有图像质量不由关键词规则认证，“题答已具备”只表示本题素材存在且无未处理勘误。

规则防误判：A/D、D/A、触发器、计数器、逻辑门等数电或数模混合内容不进入严选；乘法器、振荡器、单稳态等非本轮主攻内容留复核。功率/效率计算不因为附问反馈而错归核心反馈。选择题干、逐题定性/组成标签和 `ANA-SA` 简答均降为基础。

## 复现与发布

`drill/analog_selection_rules.py` 为确定性规则，`scripts/build_analog_selected.py` 消费私有元数据及 OCR 缓存，只向 stdout 输出清单，不连接数据库：

```sh
python3 scripts/build_analog_selected.py \
  --inventory /private/inventory.zlib.b64 \
  --workbook-text /private/ocr-cache.json \
  --index /private/index.json --cache /private/ocr-pages --output selected
```

inventory 为元数据 JSON 的 zlib+base64 编码；例题缓存格式为 `<uuid>-<region-index>.png: OCR文本`。另支持 `--output review/stats` 及多个 `--cache`。最终索引为 `drill/data/analog_selected_v1.json`、`analog_selected_review_v1.json`；运行时无模型调用。

逐题热力图与表头的已做/未做/master/两种master率复用原记录；下一题、顺序下一题、复习题均不离开当前筛选；返回保留筛选并定位原题。原卷和完整版答案功能保留。

先推 GitHub，再 VPS fast-forward 拉取；合并前端静态构建后 collectstatic、Gunicorn HUP。保留已有资源和远端未跟踪文件，不从本地覆盖 VPS 数据库。测试覆盖规则、防数电误选、集合安全契约及三种集合隔离；浏览器只读验证桌面/手机、九组、原题状态、题答加载及返回定位。
