# Community 与详情非核心请求合同

## Community 设置与查询身份

`useCommunityChartParams()` 返回 `params / ready / loading / error / refetch`。设置成功前，feed、trending 和 post Query 均 disabled；设置错误走页面错误状态和设置重试，不发 fallback 请求。服务端控制的字段来自 settings；merge level、dynamic threshold 沿用当前浏览器的既有用户选择，在 settings ready 后统一组合。

三个入口使用同一个 `buildBillboardContextParams()`：min_ms、music_only、merge_enabled、dynamic_threshold、merge_level、include_compilations、max_merge_gap_minutes 和五个 bb_* 参数。Query key 与 HTTP 请求共用规范化参数：忽略 undefined/空过滤条件及等价默认值；账号、标签、帖子类型集合去重排序；搜索与后端一样转小写。feed 的 limit=50、offset 仅由 useInfiniteQuery 的 pageParam 管理。其他搜索、时间和精选筛选保留在 key 中。

首次有效加载：feed 页和 account 页各一轮 feed + trending；post 页一轮 post + trending，不请求 feed。请求 signal 交给 API client，旧 Query 不覆盖新筛选结果。未启用预取入口；此前没有调用者的无参数预取函数已移除。

Community 后端现在遵守 [持久读模型合同](community-snapshots.md)：GET 只读已发布 generation，feed 先筛选分页后补全，trending/post 使用专用投影；缺失明确返回 unavailable。模板措辞随 generation 固定，模拟互动数仅按返回集合生成。

## 详情、播放统计与交互

- Summary 与 `include_rank_context=false` 基础 stats 并行；EntityStatsPrefetch 只预取基础 stats。album-project 的 stats 身份由 project ID 确定，不因 summary 补齐 artist 而产生相同 HTTP 请求的第二个 key。按名称寻址的 album 仍保留 artist 区分。
- 基础统计图表后展示排名区块，进入视口才启用 `include_rank_context=true`。排行榜区块独立观察；artist 仅请求当前 track/album 类型，类型切换、分页和 metric 使用各自精确 Query key。
- `useDeferredInView` 是按上下文触发一次的 IntersectionObserver，`rootMargin='0px'`。没有固定等待、设备延迟或缺少 Observer 时的 eager fallback。测试通过可控制的 Observer 注入相交事件。
- RecentPlaysSection 的分页请求也由视口启用，使用 TanStack Query。错误、加载、空结果分开显示。上下文包含 kind、规范化实体、artist/project、merge level、filters 与 period/start/end；page、page size、search、date 再进入分页 key。底层 analysisApi 的项目 plays/play-dates key 同样包含 project ID。
- Play-dates 只有首次打开日历才启用；关闭重开沿用同一 Query。实体、过滤或周期变化使用新 key。日期失败显示错误和重试，不把失败当作无播放日期。
- 多个区块同时进入真实视口时可同时请求；不通过填充空白、固定延时或串行阻塞伪造逐个触发。日历仍只由用户打开触发。

Desktop 与 Phone 使用同一触发和事实合同。Query cache 沿用应用现有 staleTime/gcTime；未新增持久缓存、后台重建或统计算法。

## 证据

[阶段 2B 请求图、测量和回归结果](../reports/2026-09-19-deferred-community-details.md)。本地定向验证为 Partial，不代表完整全栈或生产 SLA。
