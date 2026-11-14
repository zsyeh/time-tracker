# 账号级题型与全局勾选记忆

## 行为

- 题型筛选（小题/大题等）记住上次用户选择，Practice、普通/严选/核心热力图和 EI 五科严选入口复用。
- Practice 常用条件：具体题型、作答状态、来源、仅收藏、下次复习、标记、包含资料目录随账号记忆。Drill / EI 分开保存，避免跨科题型混用。
- “题型分色预览”和 EI“显示原题标签”是全局显示偏好，在页面、设备之间复用。
- 既有“掌握/待复习后切题、自动复制、计时提醒”等账号偏好继续沿用。
- **取消勾选 / 全部题型同样记住**，用显式空值覆盖旧设备的旧选择，不会刷新后重新勾上。
- 第一次升级时，原页面 URL / 本机 Practice 恢复状态已有题型、账号尚未保存题型，会采纳已有选择。后续有明确条件的 URL / 分享 / 返回做题上下文优先，不让全局默认改写题单。
- 书本/章节、关键词、页码、滚动、弹窗及焦点不跨设备同步；做题诊断中的业务勾选仍按原题和 Attempt 保存，不转换成全局默认。
- 已打开的题单保持自己的 URL；另一端的最新偏好用于下次正常进入。显示类勾选跟随原偏好刷新机制更新。

## 性能与同步

- 复用现有 `UserPreferences` JSON、服务端 bootstrap、账号隔离、本地缓存、字段 CAS 冲突处理和离线队列；**没有新增模型、迁移、接口、轮询或题库查询**。
- UI 即时更新，沿用已有 **500ms 合并写入**；重复选中相同值不产生偏好写入，不等待保存才加载题目。
- 初始列表请求前确定默认筛选。单测及两份独立浏览器状态实测：另一端打开已同步“小题 + 仅未作答”的 Practice，**仅 1 次题目列表 GET**，没有“全部 → 小题”的双重请求。
- 账号偏好覆盖旧设备的本地筛选时，清除不再适用的设备页码和索引版本，防止落在筛选后的越界页。
- 新增 Drill 主 JS 约 2KB / gzip 约 0.7KB（生产构建摘要近似差值）；没有引入依赖。未声称全站绝对零开销或进行新的全站性能基准。

新增字段（Schema version 1 的兼容增量）：

```text
browse.drill.filters    {type_group?, exam_type?, status?, source_category?, favorite?, review_later?, marker?, include_structure?}
browse.ei.filters      同上
browse.format_colours  boolean，默认 true
browse.original_labels boolean，默认 true
```

过滤对象只接受白名单枚举字符串和显式空值；拒绝关键词、分页、用户 ID、题目 ID 及其他临时/敏感字段。不同账号隔离，旧本地缓存补齐新增字段且保留待同步队列。旧服务版本忽略新增 JSON 字段，应用回滚不覆盖数据库。

## 文件与验证

- `frontend/drill/src/lib/browsePreferences.ts`：共用偏好访问、恢复优先级、白名单与去重。
- `frontend/shared/preferences/schema.ts`、`store.ts`、`tracker/user_preferences.py`：校验、默认值、旧缓存兼容及原账号 API。
- `ExamTypeControls.vue`、`lib/examTypes.ts`：用户选择/小题专练入口记忆、首次继承、全局分色。
- `composables/usePracticeQuery.ts`、`views/PracticeView.vue`：只有实际筛选操作保存；首次请求之前恢复。
- `HeatmapView.vue`、`Circuit/Signal/Analog/Digital/CommunicationSelectedView.vue`：默认题型和原题标签复用，保留原 URL、矩阵、导航及样式。
- 对应 `browsePreferences` / `PracticeView` / `HeatmapView` / `SelectedCollections` / `schema` / `store` 等测试；生成的 `appearance-bootstrap.js` 随两前端产物同步。

结果：相关前端用例累计 **89 个通过**，最后受影响 41 项和首次继承 6 项重跑通过；后端 `UserPreferencesAPITests` **29 项通过（1.390 秒）**，覆盖第二设备读取、Drill/EI/其他账号隔离、非法字段和取消状态。

Timer / Drill TypeScript 与生产构建通过。原 EI 展示模式测试原先未绑定账号，改为与实际应用一致的登录偏好夹具后通过；另修正 helper 的 TypeScript 索引类型。未靠修改产品权限来通过测试。

[本地双浏览器验收](browser.json)：服务器读回、新设备题型/未做/分色、单次列表请求、热力图继承、显式链接优先、取消后刷新均通过，无页面错误。[手机截图](phone-synced.png)。浏览器使用隔离账号；实体 iPad Safari / PWA 本轮未测，不把 Chromium 尺寸测试当实机证据。

## 发布与回滚

- `51fb07d` 核心实现；`b496ae2` 补齐首次升级继承，最终发布使用后者。中间镜像未切到生产。
- 最终镜像 `time-tracker-ha:20261114-browse-sync-b496ae2`；回滚旧生产 `time-tracker-ha:20261114-study-timer-93c418e`。
- 并行账号/学习数据、schema、旧镜像/服务/PWA 备份：`/var/snap/docker/common/time-tracker-ha/backups/round2-browse-sync-20261114`，21:13:28–21:13:32，4 秒，可解析且校验退出 0；不重复导出题库。
- 宿主回滚入口已实际放置、可执行并校验 shell 语法，回滚保留上线后的学习记录：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/browse-sync-b496ae2/deploy/ha/round2-rollback.sh \
  /var/snap/docker/common/time-tracker-ha/backups/round2-browse-sync-20261114
```

47 于 **2026-11-14 21:28:08 +08:00** 切换完成，最终镜像 ID `e3d7076c8642` healthy，HTTPS 登录 200、queue 成功，服务 error journal 无记录；磁盘约 9.1GiB 可用（76%）。

[真实 HTTPS 线上双浏览器结果](production.json)：隔离测试账号保存小题/仅未做/关闭分色后，另一独立浏览器全部恢复，初始列表 1 次请求，严选热力图继承小题；无页面错误。[线上截图](production-synced.png)。仅写该合成账号偏好，验证后清理该账号和会话，未改真实用户、题库、作答或计时。

### 实际时间与返工

| 阶段 | 实测 |
|---|---|
| 用户数据并行备份 | 21:13:28–21:13:32，4 秒 |
| 前端相关测试 | 初次4.71秒；修正登录夹具后5项通过；最终受影响41项3.69秒、首次继承6项1.09秒 |
| 后端相关测试 | 29项1.390秒 |
| 本地产物 | Timer Vite 10.64秒；Drill Vite 6.90秒，追加首次继承后6.92秒；不冒充含类型检查的总时长 |
| 核心镜像 | 21:20:15–21:22:34，139秒，未切到生产 |
| 最终增量镜像 | 21:26:22–21:27:17，55秒 |
| 生产切换/健康 | 21:27:47–21:28:08，21秒 |
| 可测墙钟区间 | 首个生产快照21:11:15→健康21:28:08，16分53秒；不含此前初始读取 |

返工如实保留：首次Drill类型检查发现动态键类型错误；EI旧测试夹具未登录；冻结后补首次继承导致第二次Drill产物/增量镜像；构建脚本连锁替换误改BASE_IMAGE，Docker试图拉不存在镜像并超时，修正并加本地image存在门禁后成功。期间没有切换中间版或影响生产。后续在冻结前纳入旧状态继承，发布变量明确赋值，避免连锁字符串替换。文档提交不再重建/重启。
