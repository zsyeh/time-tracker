# Master Plan 独立复核记录

日期：2026-11-12。主文档：[MASTER_UI_UX_REBUILD_PLAN.md](../MASTER_UI_UX_REBUILD_PLAN.md)。基准：6b83e2924b9042e75e87bc091ea7f24e0948f8ee。

## 结论

独立Review Agent `/root/plan_review` 完整复核结论：**规划复核通过，无剩余阻断项**。主Agent依据其实际报告记录；不是由主作者自行替代独立审查。仓库专项复核由 `/root/plan_repo_audit`，搜索专项复核由 `/root/plan_search` 完成。其余研究分工：`plan_linear`负责Linear及Geist公开资料/源码，`plan_apple`负责Apple HIG，`plan_chatgpt`负责ChatGPT官方资料，`plan_search`负责搜索，`plan_repo_audit`负责真实代码架构。

这是文档完整性、实际路径、决策一致性、施工可执行性及安全边界审查。不是新UI/搜索效果、实体Safari、迁移或生产验收。独立review没有修改业务代码。

## 机械与人工核对范围

- 31个连续强制章节；R01–R16全部有设计决策、真实代码、施工任务、测试和证据映射。
- UAC01–UAC22逐项闭环；T01–T12；25个具体P任务都有Phase定义，无悬空任务。
- Phase 0–9各有目标、前置、文件、步骤、接口、旧代码删除、测试、截图、验收、回滚、记录和依赖共12项。
- 文件所有权、worktree/集成、失败恢复、跨上下文台账和给Sol Medium的阶段指令明确。
- 实际现存路径抽查、settings host fallback、CSP、认证/权限、分享、全屏Reader和PWA保护边界已核对。
- 8张当前构建fixture PNG、4份可解析JSON、6份研究稿。所有相对链接在主Agent最终校验中通过。
- 主Agent与独立review均核对：已跟踪业务文件diff为空；新增交付仅docs主文档、研究和证据。

## 已发现并关闭的关键问题

| 编号 | 复核发现 | 最终修订位置 |
|---|---|---|
| RV01 | 匿名分享CSP禁止内联bootstrap | §12同源同步外部脚本；不放宽CSP；无script分享仅CSS |
| RV02 | 旧root/light/EI样式会覆盖shared | §11/P01同步删除旧值，只留明示兼容别名 |
| RV03 | Yellow/Lime旧Primary使用ink可能低对比 | §11/P01将Element和分享等实填迁solid/on-solid |
| RV04 | Token与组件路径/Props不完整、More角色冲突 | §11完整primitive/semantic/component/compat，§13统一路径，More为Popover+nav |
| RV05 | Settings query白名单并非真实已有机制 | §14改为新增section enum+现有安全key规则 |
| RV06 | Question返回来源/五科高亮漏项 | §14补heatmap/cockpit/五科from与collection别名 |
| RV07 | 历史primary手动选择容易被抽组件删掉 | §18保留父Question select和原自动主因规则 |
| RV08 | worker运行45秒与25秒systemd超时冲突 | §17/26统一worker20秒/timeout25/30秒tick；rebuild500与queue100明确 |
| RV09 | State命名及lib/types.ts等路径不一致 | §17/22/28统一QuestionSearchState与真实完整路径 |
| RV10 | UUID/题号未明确优先解析 | §17.3标识符先行，scope内exact，保留印刷编号差异 |
| RV11 | 新coalesce参数没有必要 | §21保留现有带signal不合并逻辑，独立signal回归 |
| RV12 | done掌握口径容易丢失 | §17明确done/correct mastered，引用真实旧统计代码 |
| RV13 | “原命中优先”与纯score冲突 | §17新增match_tier，literal正文优于typo标题测试 |
| RV14 | 源题序/分类/资料可用性变更到worker间分页失效窗口 | §17源事务立即推进generation；完整源字段与Asset/Erratum/ExamType触发清单 |
| RV15 | 回填ready/断点、词典反向计数和失败项处理不足 | §17 ready/rebuild_last_pk/build_source_version、lexeme_refs/delta/DELETE、退避与verify门禁 |
| RV16 | Timer有损SQL预筛会漏全角/别名 | §17限制为无损范围，必要时owner流式扫描；加密不建明文索引 |
| RV17 | service benchmark与完整HTTP混淆 | §17固定独立HTTP runner/私有会话文件/仅GET |
| RV18 | SQLite仅设DATABASE_PATH仍可能连PG | §24清DATABASE_URL且隔离.env/.env.database |
| RV19 | 通用Docker entrypoint会在plan前先migrate | §26固定镜像家族与显式--entrypoint python，备份/restore在前 |
| RV20 | Evidence别名与附件链接 | E-surface-audit/E-baseline统一；附件落盘和最终链接校验 |

## 尚未执行、必须由后续施工验证

- 新设计控件与界面代码、搜索索引/算法、任何新迁移均未实施。
- 当前搜索基线只是旧SQL的3样本，不是质量评估或稳定p95。
- 当前截图使用真实构建和合成只读API；没有改后图，没有生产用户数据或实体Safari证据。
- 代表性搜索qrels、完整HTTP性能、10倍数据压测、真实iOS/PWA、备份restore和发布smoke均有未来明确任务，不在本记录中标passed。
- 本轮未提交代码、未变更数据库、未生产部署。后续部署须新的明确授权和P08全门禁通过。
