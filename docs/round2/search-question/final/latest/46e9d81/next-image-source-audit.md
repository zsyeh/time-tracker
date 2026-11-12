# 下一题图片70→363ms三样本的源码核对

只读比较`0103df5..46e9d81`，没有重新访问生产或已清理账号。

## 实际代码变化

- `frontend/drill/src/views/QuestionView.vue`的`schedulePrefetch`完全相同：先`warmQuestionMedia(loadedQuestion)`，预取`sequential_next_question_uuid`，随后闲时next-next，另保留previous、备用未掌握、复习及未做范围目标。
- `frontend/drill/src/lib/workspace.ts`的`warmQuestionMedia`、`prefetchQuestion`、`drainMediaQueue`、`fetchQuestion`、`fetchNavigationQuestion`实现未变。仍4并发、`Image.decoding=async`、`fetchPriority=low`、15秒超时，pending/warmed去重及成功HTTP图片缓存逻辑不变。
- workspace唯一变化是`detailKey`将URLSearchParams排序，让参数插入顺序不同的等价查询共用缓存和in-flight请求。
- Question普通入口原来走带独立signal的`fetchQuestion`，现复用既有`fetchNavigationQuestion`，改善prefetch与点击的共用Promise。前者带signal时不参与inflight去重，后者始终共用inflight并对当前视图独立处理取消。
- 新增navigation slot仅改变顶部按钮正常flex占位，不触碰预取/图片URL/解码/缓存。

核对命令：`git diff 0103df5 46e9d81 -- frontend/drill/src/views/QuestionView.vue frontend/drill/src/lib/workspace.ts`。最终本地WebKit两条完整交互中，已确认被点击目标的详情GET均为1，不是重复请求。

## 结论与边界

未找到下一题预取漏发、被新逻辑取消、缓存移除或图片队列退化的明确源码证据。共享query key与Promise反而减少重复请求，但不能据此声称图片普遍变快。

真实生产原3次样本中，next UI中位68→53ms，而题图decode中位70→363ms。两者都保留。用户在首张图完成后很快点next时，相邻低优先级图可能尚在4并发队列或网络中；原有预取也不保证在点击前完成。当前证据只能证明小样本出现图片等待波动，不能严格归因为网络，也不能判定所有设备存在代码回归。没有进行额外生产试验、删功能或为追求指标更改既有预取策略。
