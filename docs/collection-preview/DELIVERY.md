# 题单全局预览与分页交付报告

2026-11-13（Asia/Shanghai）。**生产发布完成；部分实机与性能验收仍未关闭。** 原 Master R01–R16、Round2 BUG/SYNC 不被本报告覆盖。GP-R01–R20 的逐条代码映射见[接口与追踪矩阵](README.md)。

## 发布与 Git

- `ffdbb713583cf879b799441fdff5bef3e06f0311`：题单上下文、认证分页投影、虚拟阅读、图片预算、各题单入口、Practice 分页与导航恢复。
- `735a2a7abea10898af4e4ef31919c58209842e13`：初始 viewport 宽度测量不能覆盖原返回偏移。
- 分支 `feat/collection-preview`，已推送 GitHub；本报告与证据随后单独提交，**文档提交不再重建生产镜像**。
- 生产47于 **03:02:18+08:00** 完成切换，部署退出0。镜像 `time-tracker-ha:20261113-preview-735a2a7`，ID `sha256:77a5e417d9646d5edf4704ca30bb1b944fa79b5032ccc4c569ed29822431ab6e`。
- Docker healthy；真实 `/accounts/login/`200；`time-tracker-search-queue.service` Result=success / ExecMainStatus=0，timer active。
- [代码文件清单](FILES.txt)是0865665→735a2a7真实 Git 差异；证据与工程流程文档属于后续文档提交。

## 实际实现

1. Practice/搜索、收藏/下次复习、历史 Attempt/Note、普通/严选/EI五科、诊断队列、勘误、试卷复盘使用统一题单定义。按当前已应用筛选与排序预览，不扩大为全库；重复 Attempt/试卷项保持独立条目身份。
2. `GET /api/drill/collection-preview/` 每批50；稳定排序、总数、定位、前后邻居、账号与工作区隔离、版本失效恢复。图片元数据含真实尺寸，不读取答案与图片二进制。后端复用来源查询。
3. 真正双向有界虚拟窗口；单集合500条元数据LRU，全局最多2集合/1000条；约20行DOM目标。图片fetch4/decode2，12张/32Mi像素软预算，可见超长图片例外。不下载整库图片，不把Base64存进元数据。
4. 异高图片按原始尺寸占位、ResizeObserver测量，稳定entry+相对offset恢复；方向overscan约2–3屏。独立题图放大动作不覆盖公式，拖动/多指不误进Practice。
5. 真实UUID进入现有Practice；前后题沿原题单。作答先保存，再处理题单导航；同UUID的不同Attempt不重复启动计时。预览本身不提交作答或掌握状态。
6. Practice显示当前/总页、筛选后总题数，首页/末页/前后页/输入Enter跳页；空结果0/0。修复Router对query变化无条件置顶，以分页栏为语义滚动锚点，取消旧请求与过期搜索防抖。
7. 不新增外观配置系统，沿用账号主题、强调色、字体、侧栏；原全屏做题/Note/诊断/计时协议保留。

## 测试与浏览器证据

| 检查 | 结果 / 范围 |
|---|---|
| 前端全量 Vitest |398 tests /73 files通过；此后仅一处宽度条件修复，针对性26测试及真实返回链路通过；不冒称再次全量运行|
| 后端全量 PostgreSQL |617 tests，189.482s，0失败；不是SQLite跳过替代|
| 构建 |Timer与Drill生产构建/类型检查通过；现有chunk体积警告保留；未配置ESLint|
| 分页 |Chromium/WebKit ×375/390/430 ×Drill/EI 12组；单行触控、键盘跳页、pager偏移0、不置顶|
| 集成 |[6组](integration/README.md)：238题点击/Back/下一题/内部返回/刷新、重复Attempt、EI搜索、状态移出集合、外观/旋转、账号切换|
| 真实大题单 |9281真实元数据、2326张SHA验证原PNG、隔离2000收藏；[窗口与图片报告](preview-window/RESULTS.md)|
| 生产实际浏览器 |[结果](production/production-browser.json)：Drill第238题→Practice→Back，同entry，偏移−36.906→−36.648px；EI预览2830题；JS错误0；[截图](production/production-preview.png)|
| 生产临时账号 |[清理证明](production/production-synthetic-cleanup.txt)：0 Attempt、1条仅该测试账号计时已清理、0用户状态；删除该临时账号/会话，不改真实用户记录|

## 实测性能（毫秒）

协议：HTTPS47，同一临时账号，GET-only、每case 2 warmup +20样本；包含网络时间、非并发负载测试。[before](production/production-api-before.json)、[after](production/production-api-after.json)。

| 接口 | before P50/P95 | after P50/P95 |
|---|---:|---:|
| Practice首页 |128.550 /153.493|131.177 /146.824|
| Practice第3页 |123.094 /134.760|119.925 /136.903|
| 题目详情 |175.139 /187.035|192.786 /278.341|
| 预览首批，5847题 |新接口，无旧基线|153.837 /203.800|
| 预览offset1000 |新接口，无旧基线|153.665 /192.991|
| 热力图范围预览 |新接口，无旧基线|172.371 /203.234|

**题目详情P95上升48.8%，P50上升10.1%，是实测退化；20样本和非同时采集不足以确认因果。没有宣称所有路径更快。** 新投影未替换详情API；需后续针对详情/服务器负载单独定位，不在本轮发布尾部盲目调参。

本地真实2000收藏：首题图704.7ms，最多20行/500元数据/431全页DOM，最多12张活跃PNG /7.86MP，采样JS heap21.32MiB。启动有1次288ms Long Task，后续遍历未记录新Long Task。持续下行到index1040、反向样本785、跳1250到index1249；正常HTTP缓存独立运行43图请求26命中、50题四次反转仅1次元数据请求。**JS heap不代表浏览器原生图片内存；不能以这些数字证明实体低内存iPad不会被系统回收。**

[本地API记录](production/api-performance.json)：50/200/500/1000/2000收藏P95分别25.179/25.939/28.341/31.685/52.082ms；真实5847题Practice/Heatmap投影P95为86.685/85.047ms。这些不是生产网络时延。

## 用户18场景验收（GP-R20）

| ID | 用户场景 | 实际证据与状态 |
|---|---|---|
| GQA-01 |收藏200题滚动到底|2000收藏真实数据、末尾定位/持续下行已测；未单独拍200题全程录像，部分覆盖|
| GQA-02 |严选561题到300|真实严选/热力图投影与2000题窗口已测；不伪造恰好561数据集，部分覆盖|
| GQA-03 |300反向到100|真实1040反向785及后续跳转/反转通过；不冒称字面300→100逐题轨迹|
| GQA-04 |238进入Practice再返回|本地Back/内部返回/刷新，生产Back同entry <0.3px，通过|
| GQA-05 |末尾反向回顶部|末尾与顶部跳转、真实反向滚动/缓存复用通过；长题单逐题全程未录制|
| GQA-06 |重复历史题正确跳转|attempt100→99同UUID，条目不同、不重启计时，通过|
| GQA-07 |搜索条件继承|EI搜索→预览→Practice→预览，URL与实际router一致，通过|
| GQA-08 |3/29跳20|真实总数/页数+任意输入、Enter和越界测试；不是伪造29页fixture，通过等价分页行为|
| GQA-09 |前后页不跳顶部|12组双引擎375/390/430，pager锚点与滚动轨迹，通过|
| GQA-10 |快速页码竞态|请求序列/取消与防抖回归通过|
| GQA-11 |失败题图重试|图片管线/组件单测通过；未保留生产图片故障截图，部分覆盖|
| GQA-12 |离线后恢复加载|offset600故障注入，UI重试后原anchor保留，通过|
| GQA-13 |实体iPad Safari横竖屏|Linux WebKit/Chromium视口与旋转通过；**实体设备未测**|
| GQA-14 |PWA切后台恢复|session刷新/既有恢复代码测试通过；**原生PWA生命周期未测**|
| GQA-15 |账号切换不串缓存|50→2000账号计数与缓存清理、服务端owner/workspace测试，通过|
| GQA-16 |不等高图不跳动|真实尺寸、旋转、1250定位、238返回偏移通过|
| GQA-17 |低性能设备内存有界|DOM/LRU/并发/lease预算通过；**实体原生解码内存长期测试未覆盖**|
| GQA-18 |作答改变筛选后的恢复|隔离临时用户50→49→48、按原序下一题与消失条目邻近恢复，通过|

未测/部分覆盖项保持开放，不能宣布全部Definition of Done通过；工程实现、部署完成与实机验收完成是不同事实。

## 数据库、代理与回滚

迁移 `drill.0040_preview_login_target_length` 只把临时登录handoff路径varchar500增宽到16384，不变更题库、Attempt、Note、计时或偏好。回滚旧应用保留兼容增宽，不缩列、不覆盖上线后的学习记录。

47的 `/etc/nginx/time-tracker-ha/proxy-promoted-common.conf` 与98的 `/etc/nginx/conf.d/ehzsy.site.conf`（仅三个学习域名server块）加入16k/8×16k/32k有限响应buffer；两端nginx -t通过后reload。Gunicorn请求行有限8190，保留既有worker/timeout/隐私日志。CSP仅img-src增加blob，不放宽脚本策略。

[长链接线上记录](production/production-long-links.json)：47预览→认证→登录实际302/302/200，长Location5610/7340B，无502/414。域名 `drill.ehzsy.site` 从此测试出口得到Cloudflare403，根路径和Timer登录也403；**域名外网认证链未通过，不把403解释为已证实的本次应用故障或已证实的历史故障**。生产IP登录/认证与实际已登录浏览器通过。后续需从用户网络/Cloudflare策略验证，禁止为通过探针移除认证或绕过权限。

备份：`/var/snap/docker/common/time-tracker-ha/backups/round2-preview-20261113`，fresh full dump **2,867,623,091B**，SHA256 `c21716610f423c84f32221992e44d3cc4d4c250fb8ee924a39128a8222263dab`；SHA、TOC及全pg_restore读取验证exit0。**不是完整数据库恢复演练**。含旧镜像、web/queue配置、PWA与47Nginx；98配置在 `/root/time-tracker-preview-backup-20261113/ehzsy.site.conf`。当前47磁盘约11GB可用。

应用回滚（在47执行）：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/collection-preview-735a2a7/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-preview-20261113
```

旧镜像 `time-tracker-ha:20261113-copy-scale-89d52bd` / `sha256:ce8af3d241398288cf779e1089718a84bfe0c36b775fd53e0b97d9e3233cd8f8`。此脚本恢复web/PWA/queue，不恢复旧学习数据。若需连带代理回滚，分别恢复上述47/98对应文件，先 `nginx -t` 再reload；不覆盖其它站点。回滚后登录200、Dockerhealthy、queue成功与旧静态资源确认即可。

## 流程复盘与后续默认

[投入产出复盘](../engineering/2026-11-13-preview-postmortem.md)、[最近开发记录](../DEVELOPMENT_LOG.md)、[项目敏捷流程](../../.codex/DEVELOPMENT_WORKFLOW.md)。用户最新要求优先：以后回滚保障下按影响范围校验，目标一分钟，开发与备份并行；不涉及题库时不再默认全库备份。历史已完成的长校验不作为以后每次发布模板。
