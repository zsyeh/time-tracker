# 作答前学习计时提醒 / 自动开始

## 需求与实现

| ID | 用户需求 | 实现与验证 |
|---|---|---|
| TIMER-01 | 点击 Mastered / Needs review 时检查对应学习计时 | `QuestionView.vue` 的原 `record()` 提交入口调用 `StudyTimerGuard.ensure()`；普通页面与全屏阅读器共用，未重写作答流程。 |
| TIMER-02 | Drill 对应数学；EI 对应专业课 | `studyTimer.ts` 映射 `drill → math`、`ei → major`，复用认证 Session API；不是单题 ForegroundTimer。 |
| TIMER-03 | 未开启时弹窗提醒 | 默认 `remind`；可以开始计时并保存、继续保存、取消本次提交。已有对应计时直接保存。 |
| TIMER-04 | 设置关闭提醒或自动开始 | 各应用 Settings → 练习偏好 → 作答时的学习计时，`remind / auto_start / off`。 |
| TIMER-05 | 不再提醒并保存预设 | 弹窗勾选后继续保存，将当前 workspace 的模式置为 `off`，通过既有账号 CAS 偏好 API 同步；取消不会保存“不再提醒”。 |
| TIMER-06 | 不影响成熟做题及已有计时 | 其他科目正在计时时不停止、不切换；网络异常允许继续保存；未确认提交的原请求重试不重复弹窗。保留剪贴板手势初始化、诊断、Note、自动翻题、单题计时协议与 Attempt 幂等键。 |

## 状态规则

- `remind`：对应科目计时已开 → 原提交；未开 → 弹窗。
- `auto_start`：对应科目计时已开 → 原提交；没有活动科目 → 使用 `/api/sessions/` 从当前时刻开始，随后原提交。
- `off`：跳过学习计时检查，不查询、不自动开始。
- 其他科目正在计时：两种启用模式均提示冲突，只允许取消或继续保存；可打开 Timer 管理，不自动结束其他学习记录。
- 检查限时 4 秒，开始限时 8 秒；超时、断网或跨设备竞争失败均提供继续保存入口，不补记过去时间、不自动重试 POST。
- 题目或账号切换会取消当前弹窗，丢弃旧的检查返回；页面不因旧结果继续提交。
- 提醒不修改题目状态；只有用户确认后才进入原 Attempt 提交过程。开始计时本身不等于作答成功，原作答保存失败仍沿用原恢复流程。

## 持久化与兼容

新增 JSON 偏好字段：

```text
practice.drill.study_timer_mode = remind | auto_start | off
practice.ei.study_timer_mode    = remind | auto_start | off
```

默认均为 `remind`。复用 `UserPreferences`、字段版本冲突处理、账号隔离、离线待同步队列、失败反馈。旧数据库行通过已有 defaults 合并机制读取新默认值，不批量重写用户行。旧本地缓存只补新增字段，保留原离线更改。

**无需 migration、DDL、索引变更或题库导出。** 应用回滚保留新偏好 JSON 字段和上线后所有学习数据；旧应用忽略新增字段。不要恢复旧数据库覆盖新增学习记录。

## 相关文件

- `frontend/drill/src/components/StudyTimerGuard.vue`：原生顶层 dialog，可在现有全屏 dialog 上方操作，独立中性样式。
- `frontend/drill/src/lib/studyTimer.ts`：已有 Session API、科目映射与限时。
- `frontend/drill/src/views/QuestionView.vue`：原提交入口唯一接入。
- `frontend/drill/src/views/SettingsView.vue`、`lib/practicePreferences.ts`：每个 workspace 的账号模式设置。
- `frontend/shared/preferences/schema.ts`、`store.ts`：类型、校验、默认值与旧缓存兼容。
- `tracker/user_preferences.py`：服务端白名单和默认值；没有新增 Timer API。
- `tracker/static/tracker/ui/appearance-bootstrap.js`：两前端构建生成的既有启动产物。
- 对应 `StudyTimerGuard.test.ts`、`studyTimer.test.ts`、`QuestionRecord.test.ts`、`practicePreferences.test.ts`、`store.test.ts`、`tracker/test_user_preferences.py`。

## 验证

- 70 项相关 Vitest 通过（6 文件，2.17 秒）：默认/关闭/自动模式、正确科目、冲突、超时/断网、取消、不再提醒、题目切换、原 Attempt 提交与重试、偏好校验与离线缓存。
- 后端 PostgreSQL：`UserPreferencesAPITests` + `SessionWorkflowTests` 共 40 项通过（6.166 秒）。新增两设备读取、workspace 独立、其他账号隔离、非法值拒绝断言；补充断言后单独重跑该用例通过（0.046 秒）。
- 旧缓存补字段/保留待同步更改的断言补充后，仅重跑 store 24 项通过（1 秒），没有重复全量构建。
- Timer / Drill 两前端 TypeScript 检查与生产构建通过，各构建 Vite 阶段 10.49 / 6.99 秒。现有 bundle size / navigation.js 非 module 警告保留，没有新增依赖。
- 本地实际 Chromium：1180×820 Drill 暗色全屏、390×844 EI 浅色；真实 Session GET 为 200，设置保存后从服务器读回；弹窗居中、无横向溢出、位于全屏阅读器上方，取消没有开始计时或提交 Attempt。见 [browser.json](browser.json)、[iPad 尺寸](drill-1180-dark.png)、[手机尺寸](ei-390-light.png)。
- 浏览器使用隔离测试账号，计时结果通过受控拦截复现场景；服务端真实开始/重复开始/跨科冲突由上述 Session API 测试覆盖。未在真实用户账号制造学习会话。
- 实体 iPad Safari/PWA 及系统剪贴板没有本轮实机证据；不以 Chromium 尺寸测试冒充实机通过。

## 发布与回滚

- 代码 `93c418e`，GitHub 分支 `feat/collection-preview`。
- 发布镜像 `time-tracker-ha:20261114-study-timer-93c418e`；基于当前生产 `time-tracker-ha:20261114-query-opt-811d82b` 构建薄 overlay，保留两前端完整产物、后端偏好白名单和源码。
- 并行备份：`/var/snap/docker/common/time-tracker-ha/backups/round2-study-timer-20261114`，包括账号/学习表、schema、旧镜像 ID、受影响服务配置和 PWA。备份 19:45:52–19:45:58，归档可解析、校验退出 0；不导出题库图片。
- 宿主 release 回滚脚本已单独放置并校验 `sh -n` / 可执行权限；不将镜像内 overlay 路径误当宿主入口。

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/study-timer-93c418e/deploy/ha/round2-rollback.sh \
  /var/snap/docker/common/time-tracker-ha/backups/round2-study-timer-20261114
```

47 已于 **2026-11-14 20:04:22 +08:00** 完成切换，镜像 `54c98f266d11` 为 healthy，HTTPS 登录页 200，搜索队列运行成功且 timer active，发布期间服务 error journal 无记录。磁盘约 9.3GiB 可用（76%）。应用保留旧 `811d82b` 镜像及配置回滚，数据库不回退。

### 本轮时间记录

| 项目 | 实测 |
|---|---|
| 从接手开始到生产健康 | 19:42:26 → 20:04:22，21 分 56 秒 |
| 用户学习数据并行备份 | 19:45:52 → 19:45:58，6 秒 |
| 相关自动化测试 | Vitest 2.17 秒、后端 6.166 秒，并行；补充缓存/设备断言仅重跑对应测试 |
| 两前端构建 | Vite 阶段分别 10.49 / 6.99 秒；这不是包含类型检查的总 gate 时长，总 gate 未独立计时 |
| 生产镜像构建 | 20:00:49 → 20:03:44，175 秒（含静态资源处理与镜像提交） |
| 生产切换及健康 | 20:03:59 → 20:04:22，23 秒 |

本轮审计区分了全局科目学习计时与单题 ForegroundTimer，复用已有 Session API 和偏好存储，避免新迁移。总耗时仍明显长于纯样式修复；不把测试执行时间冒充上线时间。只构建一次发布代码，文档提交不再构建或重启。

### 线上浏览器闭环

20:07 已从真实 HTTPS47 的 Drill Settings 进入题目、打开全屏、点击 Needs review，确认顶层提醒可见并取消。服务器返回 Drill/EI 默认模式 `remind`；浏览器无页面错误，未发起 Attempt 或全局计时 POST。见 [production.json](production.json) 与 [线上全屏截图](production-drill-fullscreen.png)。使用新建的隔离合成账号，测试后仅清理该账号、它的临时会话及关联测试状态，不触及真实用户或题库。

首次线上探针复用的旧测试账号已经被清理，实际跳到登录页，等待组件两次超时；不是产品页面故障。查明后更换隔离账号，未因该探针重建或回退生产。这段验收额外耗时没有计入“到生产健康”的21分56秒，今后先验证测试身份有效再等待UI元素。
