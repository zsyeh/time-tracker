# BUG04 最小传输修复后的生产复测

发布：`time-tracker-ha:20261112-round2-2951e54`（镜像`36aaa65b`）。主Agent在Django热图View启用标准gzip，接口JSON内容、数据库、权限及统计口径保持不变。本次仅相同合成账号的严选热力图5个冷Chrome context，全部5/5通过；不再打开题目、不提交答案、不保存Note。根Agent负责合成账号清理。

保留原始before3、after3、诊断5全部数据；当前文件新增压缩后5样本，没有覆盖旧结果。

| 指标（中位） | 压缩前诊断5次 | 压缩后5次 |
|---|---:|---:|
| 原selector可用 | 1403.3 | 803.6 |
| 首次格子RAF候选 | 1209.2 | 765.4 |
| API正文传输 | 450.6 | 16.8 |
| API请求至响应头 | 117.5 | 167.4 |
| API完成→格子插入 | 24.1 | 22.8 |
| 格子插入→RAF布局 | 125.9 | 125.4 |
| API资源完整耗时 | 569.4 | 179.7 |
| API编码正文bytes | 307254.0 | 44184.0 |

## 实际确认

- 压缩后真实HTTPS响应头`Content-Encoding: gzip`，`Vary: Accept, Accept-Encoding, Cookie`。独立认证只读GET确认HTTP200，正文44195B、解压307254B；该额外header验证不混入5个浏览器性能样本。首次header探针遗漏session token而正确返回403，纠正后200，记录保留。
- 浏览器ResourceTiming每次均解压307254B，编码44165–44194B（Django随机padding造成小幅变化），较原307254B减少约85.6%。
- 原before3次selector中位1304ms、首次发布after3次1950ms；定位后压缩前诊断5次1403ms，最终压缩后5次804ms。没有删除原先退化数据，也没有以新样本回写旧样本。
- 压缩后selector样本809/727/804/911/801ms，RAF候选766/688/765/873/754ms。当前实际样本在原冷启动首屏目标上恢复并改善。
- API正文传输中位451→17ms，直接对应已定位的未压缩网络瓶颈；API→DOM约23ms、布局约125ms均维持原水平，修复不依赖改变矩阵功能或减少题量。
- TTFB中位118→167ms，本次没有改善；压缩有少量CPU与网络波动，不能声称SQL性能同步提升。收益主要来自正文压缩。
- 只有5次冷context样本，不构成稳定生产P95或真实iPadOS Safari承诺；RAF只是首格可布局候选，非屏幕合成呈现时间。保留完整JSON中的网络、DOM、LongTasks及探针轮询口径。

## 证据

- [压缩后5个完整浏览器样本](browser-production-heatmap-gzip.json)
- [HTTPS真实gzip响应头和字节](browser-production-heatmap-gzip-headers.json)
- [修复前分段定位](heatmap-diagnostic.md)
- [原始before/after及图片性能](README.md)
