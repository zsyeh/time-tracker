# Practice页码键盘误弹修复

2026-11-13，源码`834798e`。47生产`time-tracker-ha:20261113-page-keyboard-834798e sha256:887223a338622a8100887738d58edb0146d2ec645586acecc8d4c66d99fbab8c healthy`，登录200、queue成功、deploy exit0；线上JS SHA与构建一致。[发布证据](production.json)。上线墙钟306秒，最终相关测试+构建17.28秒。

`PracticePagination.vue`没有显式autofocus/focus调用；本轮没有实体Safari录屏，未把浏览器焦点恢复作为已证实根因。修复明确限定“进入编辑”的条件：初始及失焦时readOnly/inputmode=none；只有真实pointerdown或编辑按键才同步解锁numeric，防止路由进入/浏览器恢复焦点引起数字键盘。有效跳页后blur并重新锁定，无效页码保留修正机会。主动点击仍一次即可输入，保留分页/Enter/范围验证。

7个组件测试通过，新增覆盖挂载/程序化focus仍只读、指针/按键解锁及失焦重锁。[浏览器证据](browser.json)：Chromium触控配置中Drill/EI均进入不编辑、恢复焦点仍inputmode none、点框可跳第3页、提交后blur、刷新保持非编辑。不能用Chrome视口测试宣称实体iPadOS软件键盘已经实机验证。

首次新增测试fixture对象有类型错误，修正后只重跑相关7例及Drill构建，最终通过。Timer/后端未改，不构建Timer、不跑全量PG、不迁移。无题库/学习记录/偏好数据修改。

用户备份与开发并行：2026-11-13T12:11:46+08:00→2026-11-13T12:11:49+08:00，verify exit0。不重新导出题库。旧5a555f2镜像及web/queue/PWA配置保留。此次仅前端overlay到明确旧生产基底，带改动组件源文件、完整Drill产物和revision label；发布包约1.5MB，未对正在运行容器热修改。

47回滚（保留新的学习记录）：

```sh
sh /var/snap/docker/common/time-tracker-ha/releases/page-keyboard-834798e/deploy/ha/round2-rollback.sh /var/snap/docker/common/time-tracker-ha/backups/round2-page-keyboard-20261113
```

阶段开始12:10:02；定位与实现到约12:11:47；最终校验12:12:50→12:13:07；后续本地双工作区操作检查、前端overlay打包/镜像切换；最终生产2026-11-13T12:15:08+08:00。具体部署/备份时点见production.json。文档提交不重复发版。
