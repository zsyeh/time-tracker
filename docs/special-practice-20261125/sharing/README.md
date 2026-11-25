# 专练整单分享 · 2026-11-25

- 应用 `fc6b7f6` 已上线，镜像 `time-tracker-ha:20261125-special-share-fc6b7f6`；15:31:09–15:31:19 +08完成切换，healthy，登录健康页200。
- Drill/EI 每份专练提供“分享题单”。复用 `/api/drill/papers/<uuid>/share/`、现有域名选择与剪贴板回退；同题单重复分享复用链接，不另造AI入口。
- 分享页/Markdown显示真实专练标题、题数、固定顺序和原题/参考答案贴图，隐藏混乱OCR；不带用户Note、得分、掌握状态或计时，不展示虚构0分考试总分。原考试分享行为保持不变。
- 修改：SpecialPracticeView.vue/组件测试、drill/sharing.py、test_special_practice.py。无迁移，无题库修改，不新建Attempt。

## 验证

- 前端3项通过（885ms）；后端4项通过（1.546秒），含重复分享、顺序、题答图片、账号越权404。类型检查通过，暂存目录生产构建7.24秒。
- 生产57题：1180×820和390×844 Chrome真实点击分享、复制域名链接成功，无横向溢出/JS错误；匿名HTML与content.md均200，Markdown含57题及答案贴图。实体Safari/PWA未测。
- 本地最初缺Node/依赖，恢复Node22及npm ci约2分钟；旧构建目录权限导致一次失败，改独立暂存目录构建。Docker新容器验证等待、测试角色缺CREATEDB、测试HTTP被301等环境问题分别通过隔离exec、仅创建独立测试库及关闭测试SSL跳转解决。不是业务测试失败；未改线上代码或认证配置。隔离测试库已删除。
- 改进：保留可用Node和依赖缓存，后续构建默认使用独立可写目录；隔离测试库由管理角色创建，应用角色只测试，不授予生产额外权限。避免重复排查相同环境问题。

## 备份与回滚

- 用户/学习数据、Schema、服务配置和旧镜像位于47 `/var/snap/docker/common/time-tracker-ha/backups/special-share-20261125`，verify-exit=0。未导出未变题库图片。pg_restore校验改用现有PG容器独立进程，未重启数据库。
- 回滚：`sh /var/snap/docker/common/time-tracker-ha/releases/special-share-fc6b7f6/rollback.sh`，恢复 `time-tracker-ha:20261125-special-practice-ef0a225-final`。保留数据库和本次分享记录，不恢复全库抹除后续学习数据。
- 47发布后磁盘约11GiB可用。没有无关queue或PWA配置修改。

[浏览器实测](browser-result.json) · [iPad尺寸](share-1180.png) · [手机尺寸](share-390.png)
