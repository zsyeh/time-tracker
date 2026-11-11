# Drill / EI 计时冲突恢复与未做题导航

日期：2026-11-11。沿用现有协议2、QuestionTimingSession.recovery、LearningRecoveryState与Attempt事务；没有新增模型或迁移。此文记录本轮针对性修复，发布结果见末节。

## 故障链与修复

原ForegroundTimer.sync在409后将claimed设为false并结束Promise，不向调用者区分同步失败；record随后仍snapshot并提交旧owner/key/sequence。finish_timing会拒绝过期租约、错误owner或active timer，从而回滚整个Attempt事务。重复点击继续复用无效计时快照，形成“刷新才能继续”的表象。

现在sync返回success、recoverable或conflict及脱敏原因。提交前prepareSubmission验证计时连接，在服务端允许时最多安全claim一次；真实其他活动窗口的有效租约不能被接管。document owner不再复用可能随标签复制的sessionStorage值；同设备共享缓存不能作为抢占有效租约的证据。正常pagehide/pause释放租约，异常退出未送达时需等待原租约到期，不伪造旧页面已关闭。

服务端区分owner_mismatch、lease_expired、stale_sequence、active_timer_mismatch等原因；409诊断只记录固定reason，不记录owner、timing key、凭证、Note或诊断文本。旧pause重复请求无副作用；旧checkpoint不能把不活跃计时伪装为同步成功，更不能释放新窗口租约。

## 当前页恢复与显式无计时保存

- 同页提供“重新连接计时”，不要求刷新。正常及全屏做题均能操作。
- 仍不能连接时，用户可明确选择“不记录本次用时，仍保存作答”。这不是删除计时字段降级到旧接口：提交包含协议2、timing_omit=true、计时轮次、owner与原submission_key，服务端逐项校验。
- 计时key若属于其他用户/题目不能使用；本页claim从未成功、key尚未建库时仍有受校验的无计时保存路径。省略计时不接受time_spent_seconds，不写入伪造时长。
- 显式省略使用现有计时JSON元数据记录审计；不修改其他owner轮次或其active pointer。没有新增计时统计表，也不重写历史时长。
- 本地计时快照、Note草稿和诊断保留。已经计入服务器的用时不会作为新轮次再累计；需要新轮次时保留当前草稿，使用新计时key。

## 幂等与响应丢失

保留原submission_key，并记录已准备发送的提交快照。POST网络结果不确定时先重试原请求，允许服务端在计时校验之前返回已有Attempt；不能因server timer已finalized就换新key重复提交。finalized但仍有待确认提交的本地记录跨刷新继续保留。

明确的计时409不会被当作作答成功；已确认Attempt成功后，缓存、导航或统计更新失败也不会被当作作答失败。重试期间新编辑的Note和诊断不被去重响应覆盖。成功后仍按原Mastered/Review自动翻题、翻题模式及全屏状态执行。

## 未做题模式

前后翻题下拉菜单新增“未做题 / Unattempted questions”，全屏使用灰色方向标识并继承同一偏好。未做复用当前系统语义：无Attempt或最新状态为Reset；Mastered和Review均跳过。Undo后按仍存的最新记录重算，不将旧next_question_uuid（未掌握，包含Review）误当未做。

保留书籍、知识点、题型、搜索、严选、workspace和用户筛选；历史/收藏模式只在自己的列表内寻找，可环绕但不会跳出或返回当前题。没有候选时禁用方向键并提供空状态，不自动退回顺序题。严选复用已加载的latest状态，不增加查询；普通范围增加两个LIMIT 1查询，作为新增双向模式的明确成本。

## 验证及限制

- Django完整510项通过；makemigrations --check --dry-run无变更。
- 后端覆盖正常计时、前后台、expired lease、stale sequence、active mismatch、复制缓存不抢活动租约、真实PostgreSQL并发竞争、事务回滚Note、字段删除防绕过、显式省略、未知key、他人key、幂等及跨账户限制。
- 未做导航新增8项后端测试，覆盖两个workspace、用户隔离、筛选、严选批量与普通查询、历史/收藏、Undo、环绕及无自环。
- 前端163项Vitest全部通过，Timer/Drill TypeScript及两套生产构建通过；其中30项针对性测试实际执行生产record处理器、ForegroundTimer和全屏slot，覆盖重复点击、一次claim上限、真实冲突、响应丢失后恢复同key去重及后编辑草稿。已有chunk大小告警保留。
- iPadOS真实系统回收、锁屏和Safari事件送达仍需实机验收。浏览器完全禁用本地存储时，跨进程恢复未确认提交无法保证；同页内存重试和服务端幂等仍有效。


## 生产发布与回滚

已按用户授权部署到47，应用代码 `fc16557`，镜像 `time-tracker-ha:20261111-timer-conflict-fc16557`。NUC完成两套构建后，在派生镜像中明确collectstatic；切换前核对传输SHA-256及全部191个静态资源，check、migrate --plan、makemigrations检查通过，没有执行数据库迁移。

发布前备份当前业务dump（不含大型QuestionAsset表二进制数据）、资产元数据和原service drop-in。gzip与pg_restore归档目录检查通过，业务数据及元数据已复制到NUC并验证哈希；既有完整资产备份和旧镜像继续保留。位置：47的 `/var/snap/docker/common/time-tracker-ha/backups/timer-conflict-20261111/`，NUC私有证据 `/home/eh/timer-conflict-deploy-20261111/`。

部署前19项、部署后28项公网HTTP检查通过：Timer/Drill/EI域名、IP同源API、统一Manifest、主JS/CSS哈希、题目和图片GET/HEAD/304、未做导航字段及目标确属未做状态。切换前同一短期测试Session在切换后仍认证成功，验证后只撤销该测试Session。真实冲突/无计时/重复提交等写入测试在隔离PostgreSQL完成，没有向生产作答历史写测试Attempt。

生产容器healthy、OOMKilled=false；约619MB可用内存、11GB可用磁盘，Nginx配置检查通过。没有修改Nginx、认证密钥、Session配置或数据库schema。清理本次临时Session及镜像传输归档，保留旧镜像 `time-tracker-ha:20261111-performance-trends-ab234ed-r2`。

需要回滚时，在47执行以下脚本，只切换旧应用镜像，不恢复旧数据库覆盖新学习记录：

```sh
python3 /var/snap/docker/common/time-tracker-ha/backups/timer-conflict-20261111/production.py rollback
```

用户首次刷新以加载新前端；之后计时冲突可在当前页面或全屏内处理，不需要依赖刷新恢复。iPadOS实际冻结/回收与多窗口仍需实机观察。
