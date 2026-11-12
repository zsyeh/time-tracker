# Practice 分页、题单入口与独立共享契约审查

基于`0865665`工作树实施；不访问生产、不操作现有真实学习记录。主Agent统一维护路由/Question/热图/listContext和后端；本模块不提交Git，由主Agent整合。

## 根因与改动

原`main.ts scrollBehavior`对同路径query分页也返回`{top:0}`。Practice组件复用时不unmount，旧代码也不保存离开页位置；永久`interacted`标记又阻止异步恢复，造成翻页跳顶。

当前Router由主Agent让Practice自主恢复滚动，本模块在新页DOM与两个RAF完成后按语义锚点定位：

- 顶部/底部分页分别保留同位置pager的viewport offset；短末页使用文档高度clamp。
- 搜索/筛选到结果区；返回题库优先恢复原可见行UUID与offset，失效后使用saved scroll。
- 返回缓存先显示并定位，同时后台重新验证；只允许当前请求sequence/当前route执行滚动。
- 用户等待期间wheel/touchmove/pointer/key交互取消待执行定位，不再永久取消后续恢复。
- 全部筛选、原关键词、sort、source提示和index_version随分页保留。分页前取消未提交输入draft，不让250ms timer事后重置页码。
- 缓存列表恢复时立即使用缓存的index_version，避免输入取消revalidate后分页缺少generation pin；409仍保留筛选并返回第1页。

## UI及入口

`PracticePagination.vue`在列表上、下各一处普通文档流：上一/下一、首页/末页、当前/总页、总结果数、任意整数页提交。输入范围1..N，不合法不请求；无结果禁用。非法输入纠正为当前合法页时立即清除错误，不产生无意义导航；该回归已由先红后绿的6例focused测试验证。后端page/page_size/total_pages为权威，旧缓存遵循原24题/页契约，绝不从末页长度推总页。

所有控件至少44×44px。实际390截图发现末页单独换行后，移动端改为5列（first/prev/summary/next/last）＋第二行jump，保留原字号与触控尺寸。最终中央构建已验证紧凑布局；`before-compact-grid`保留修复前证据，`final-mobile`为最终门禁。

新增全局预览入口均调用统一`buildListContext`/`previewLocation`：

| 页面 | source | 保留内容 |
|---|---|---|
| PracticeView | practice | 全部applied filters/search/sort，去page/index_version/from；returnTo保留原完整URL；按当前页首题预选 |
| CollectionView | favorite/review_later | 正确保存时间排序的独立收藏源，完整returnTo页码；不替换成题册序favorite筛选 |
| InsightView两个header | attempts/notes | 已应用筛选/日期/排序，无未提交draft；完整returnTo保留两套独立页码；attempt:ID或note UUID预定位 |
| 五科SelectedViews | selected | 各自collection及bucket/tier/kind/combined/state/type条件；returnTo原路径 |

普通题目行仍直接进入原题，未增加一次强制预览步骤。热图及Question由主Agent负责。

## 测试与证据

- 独占6个模块文件49/49测试通过：Practice17、Pagination6、query6、Insight12、Collection3、五科入口5。
- 共享契约独立17/17通过：listContext5、PreviewSession12。原失败日志保留，修复由主Agent写source。
- 完整Drill TypeScript检查exit0。两处scoped CSS独立PostCSS解析通过；最终生产构建由主Agent执行。
- Chrome8/8、WebKit8/8：Drill/EI ×390/820/1180/1440，底部完整页锚点漂移0px，Enter任意页/首页与Space末页通过，短末页97题的第5页1行安全clamp，无横向溢出/JS错误。
- 8033真实隔离PostgreSQL/本地HTTP账号2000收藏，Chrome390/820两例通过：2000题/84页/末页8行，底部锚点漂移0px，首末页真实键盘与末页clamp通过。

### 最终中央构建门禁

中央构建 `index-0uldzb3Z.js`，index SHA256 `b531d11419c31b58374196f93ba969980dd6b8a25ee189a2824c83f77639839f`。运行前后所有assets SHA256一致，详见`final-mobile/bundle-{before,after}.json`。

- Chrome 6/6、WebKit 6/6：375/390/430px × Drill/EI。
- 四个首/前/后/末按钮全部同一行、底部翻页锚点漂移0px。375截图已人工检查，未出现独占第三行的末页按钮。
- 完整页翻页scroll事件追踪从未出现scrollY=0（Chrome最小2010px，WebKit最小2016px）；短末页按实际文档高度正常clamp，不将合法0位置误判回归。
- 未提交搜索draft不覆盖跳页；Enter提交任意页/首页、Space末页通过，末页禁用正确，无水平溢出、无JS错误。
- 本门禁只做Practice GET分页，不替代主Agent的题单预览/真实Question保存与返回闭环；没有新增生产性能结论。

### 审查发现并修复的共享缺陷

1. fresh开始后并发非fresh仍带旧opaque version，fresh先回而旧pin响应晚回会覆盖新cache；主Agent新增fresh gate和response pin一致性校验。
2. inflight第二consumer取消信号未订阅；主Agent增加独立signal wrapper。
3. 旧owner session.find未做owner检查；主Agent补隔离。
4. Preview Question导航尚未返回时提交auto-next，可能将loading误判末尾；主Agent在成功保存后等待导航，而不阻塞保存。
5. 重复UUID不同Attempt只换entry不重载Question是正确方向，但新neighbor未预热；主Agent在entry更新后重新schedulePrefetch而不重启timer。

所有通过数据与原红证据分开保留，未掩盖失败。

## 范围与限制

浏览器全部在localhost，API及写入仅本地合成fixture（主要是App recovery）；分页QA不进入Question、不提交Attempt/Note。PG测试绑定独立合成账号，身份文件只在私有路径读取，没有cookie复制到本文档。桌面WebKit不是实机iPadOS Safari，系统软键盘/PWA chrome仍需真机验证。这里是交互/布局回归，不作为生产性能基准。
