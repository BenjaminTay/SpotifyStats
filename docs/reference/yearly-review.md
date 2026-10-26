# 年度总结内容与缓存规则

适用读者：维护者与Agent。本文是共用技术参考；日常操作见[使用指南](../user-guide.md)，实施与验收证据见[报告索引](../reports/README.md)。

最近核对：2026-10-25。当前规则覆盖自有年度总结，不改变AI年报的[V6运行合同](ai-agent-runtime-v6.md)。

## 内容和事实来源

年度内容由 passport、honors、season、relationships、listening-life、records、taste-migration、epilogue 和 appendix 等模块编排，事实由确定性 builder 产生。具体年度字段与编排实现见[年度领域](../../backend/domains/yearly_review)、[服务入口](../../backend/services/yearly_review_service.py)和[响应模型](../../backend/models/yearly_review.py)。

### 年度总结 V2 消费契约

Desktop/Compact 与 Phone 的 `/yearly-review` 共用确定性 `YearlyReviewV2` 数据契约，但分别使用完整杂志年鉴与“口袋音乐年鉴”presentation；页面只提供这一套自有年度总结，不再提供“官方 Wrapped”页签。Phone/Desktop 必须互斥挂载。`/api/wrapped-hub`、官方导入表和读取服务仅作只读兼容冻结，不进入年度总结消费链路。

V2 统一继承当前 `music_only`、连续播放合并、动态阈值、`merge_level`、精选集、三类 Billboard Top N 与周边界。前端主报告 query key、后端 cache key 和兼容 records 响应必须使用同一过滤指纹，并包含版本化内容策略、display taxonomy 与艺人元数据 revision。

V2 的 `schema_version` 与 `content_version` 分开治理：前者只描述对外契约形状，后者覆盖统计、编排、公开文案与方法语义。任何语义变化都必须提升 content version，使进程 LRU 和 sidecar 精确键同时分流；sidecar 的压缩格式版本不能替代内容版本。

展示语义：

- “播放排行”同时保留播放次数与播放时长，两者不得混名。
- “个人 Billboard 年榜”使用[播放统计中的Billboard Year-End规则](playback-stats-rules.md#r36-billboard-year-end-年榜)，只能描述本地个人榜；不得写成 Spotify 或外部官方 Billboard。
- 月度正文只有一条年度赛季/转折时间线；十二个月完整事实只在可展开账本中出现，不再复制第二套月度叙事。
- 关系、回归、发现、纪录和品味迁移只有在对应 coverage/支持阈值成立时才生成；不足时降级为空态或限制说明，不得由 LLM 补写。
- 主曲风只消费 `style`，地区流行只消费 `scene`，语言独立统计；`context` / `role` 不进入主图，unknown 必须保留为“尚未归类”并显示覆盖率。
- YTD、完整年、部分年和空年份由实际播放范围与榜单周覆盖决定；YTD/partial 不得使用“完整年度冠军”等已结算措辞。
- 年度里程碑必须先在完整个人历史的 canonical track 播放序列上计算累计阈值，再筛选阈值跨越日期是否位于报告年；报告年内的第 1,000 次播放不得写成个人历史第 1,000 次。
- 年度 discovery 必须先从完整历史得到 canonical track、album project、canonical artist 的真实首次播放日期，再筛选首次日期位于报告年的实体；只在年度切片内第一次出现的旧实体不算“第一次听到”。
- 每日播放次数与每日收听时长分别排名并使用 dense rank。只有各自的第一名可写“最多的一天/最长的一天”；并列第一必须明确标注并列，第二名及以后只能陈述名次或普通事实。
- 同比必须使用当前观察范围映射出的上一年 aligned window；闰日取合法月末。若上一年没有覆盖完整 aligned window，则回退到两年映射后的最大共同日历区间，且共同区间至少 90 天才可比较；否则不生成比较。比较模式明确区分 `full_year`、`same_period`、`common_period` 与 `unavailable`，消费端在非完整年度窗口显示“比去年同期”。工作日/周末日均以观察区间自然日数量为分母，不以活跃日或固定 5/2 为分母。
- 当报告截止在未完整月份时，该月的环比与同比只能分别与上月同期、上年同期的等长窗口比较，metric 必须保存两侧起止日期；只有完整自然月才能使用完整自然月比较。
- Passport 曲目/专辑/艺人数分别与播放榜的规范曲目、album project、有效署名艺人口径一致；同比也必须使用同粒度。
- 收听生活的歌曲总数、新歌数、探索率与复听率统一使用 canonical track identity。头号艺人的“播放占比”以年度逻辑播放总数为分母，以包含该有效署名艺人的逻辑播放数为分子；不得使用 fan-out 后艺人表总行数作分母。
- 完整年品味比较 H1→H2；YTD 只比较最近两个完整季度，少于两个完整季度时仅显示分布。差值和驱动实体必须使用同一日期切片。
- 公开纪录必须命中显式 renderer 并具备实体、数值或精确周期证据；未知/internal key、blocked map 和开篇/年榜首重复事实不得公开。阶段无法由连续月度多数冠军证明时必须返回空 stages，结语不得原样复制开篇头条。
- 主报告只携带 Top 50/30/30 和 6–8 条精选纪录。年报不提供“更多年度纪录”下钻，完整播放纪录/Billboard 纪录回到各自独立页面；兼容 `/api/yearly-review/{year}/records` 只返回与正文相同的精选集合，artifact 不得再序列化数千条候选。
- 消费界面不得渲染过滤指纹、策略版本、证据等级、coverage、limitations 或“统计口径 / 可比基线”等审计词；这些信息只服务于 API 契约、诊断与自动验收。
- 顶部六项指标统一称为“年度播放 / 年度时长 / 年度活跃天数 / 年度播放曲目 / 年度播放专辑 / 年度播放艺人”。有上一年数据时只显示红/绿方向箭头与百分比，不再重复显示“高/低”或绝对差值；完整比较语义保留在 accessible label 中。
- 年份按钮按升序排列且只显示年份；完整年度封面不显示“完整年度”和起止日期，YTD 报告仍在封面保留“进行中 · 截至日期”。封面不显示三条头条或海报按钮。
- 大标题下不附加解释性 subtitle。附录用户入口只称“完整榜单”，并且只保留播放榜与个人 Billboard；十二月明细只能从唯一年度时间线展开。
- 用户界面提到的歌曲、专辑、艺人应尽可能提供封面和既有详情深链；统一占位负责缺图降级。Phone/Compact/Desktop 默认最新可用年度，当前年明确标注进行中。年度名称和动态文案遵循全局简繁体偏好；回归等事件必须标注实体类型，避免把专辑事件误读为歌曲事实。
- 新关系故事按实体类型分别使用“今年发现的新歌 / 今年新听的专辑 / 今年认识的新艺人”，不得用“新名字”指代歌曲或专辑。同一专辑或艺人多首进入个人榜单的纪录必须显示准确曲目数；分歧故事在宽屏使用两列，空间收窄时回到单列。
- 所有正文章节统一使用紧凑纵向节奏；当前 Desktop/Compact section padding 为 `clamp(48px, 5.5vw, 80px)`，不得恢复为造成双倍大空白的超宽间距。

## 生成和持久缓存

- 当前缓存热响应预算为 250ms，未压缩主 JSON 预算为 512 KiB，真实重算预算为 30 秒。
- 关系历史中的首次播放与回归前末次播放日期必须按实体类型一次性聚合，不得在逐实体循环中反复扫描和转换完整历史；年度播放纪录应复用编排层已经建立的年度事件与实体帧。
- 最终 artifact 可以压缩持久化，但必须使用独立 sidecar SQLite，完整 cache key 继续包含稳定播放事实 revision、过滤指纹、content version、策略和元数据 revision；不得使用 SQLite main/WAL 物理 mtime 让无关写入造成缓存抖动，不得用旧 key 或近似 key 返回 stale 报告。
- 持久缓存损坏时必须自动视为 miss 并重算。
- 年度生成使用 `yearly_review_generation_v1`：相同精确 key 只允许一个任务，不同年份的缓存命中不得被冷构建阻塞；单工作线程优先生成当前年份，其余真实可用年份从近到远排队，revision 漂移时不得写入旧 key，失败只公开稳定错误码且可重试，终态任务表必须有界。
- 设置变更、流式导入与应用启动继续预建最新默认年份；Desktop/Compact/Phone 进入年度总结后按当前完整筛选上下文批量预建全部可用年份。
- 性能优化不得改变统计口径或让浏览器静默吞掉本地 API 超时。
- 内容和策略版本分别由[versions](../../backend/domains/yearly_review/versions.py)和[policies](../../backend/domains/yearly_review/policies.py)定义；probe 除公开文案、封面/深链、YTD 措辞、精选证据、结语去重和阶段状态外，还必须验证跨章节歌曲 identity、艺人占比分母、未完整月份以及完整年缺失基线时的共同区间比较。

## artifact key 与增量失效

年度总结验收不要求“增量路径”和“最终输入完整替换路径”生成相同的 artifact key。两条路径必须生成相同的年度确定性事实分区；artifact key 继续包含受影响年份的 `impact_revision`，用于记录被接受的事实变更历史并强制旧 artifact 失效。

因此，正式门禁是：

1. 相同最终输入的年度 factual partition（`report_year`、`direct_digest`、记录数和覆盖范围）完全等价；
2. 每次被接受且影响该年份的 append、reconcile 或 replace 都提升 `impact_revision`，并生成不同的 artifact key；
3. `identical` 导入不改变 factual partition、`impact_revision` 或 artifact key；
4. 不受影响年份继续使用原有 revision 和 artifact；
5. 任何依赖、规则或事实 revision 不匹配的缓存都不得作为 ready artifact 发布。

跨路径 artifact key 是否相同只作为诊断字段记录，不参与等价性通过判定。

### 保留变更历史的原因

artifact key 同时承担事实依赖标识和缓存失效边界。增量 reconcile 与最终输入完整替换即使收敛到相同事实，也经历了不同数量的已接受变更；若为了追求跨路径 key 相等而移除 `impact_revision`，可能重新命中变更前生成的旧 artifact，削弱“接受变更后必失效”的安全保证。

年度事实等价应由稳定事实分区证明，不应由带审计历史的缓存 key 代替。`prefix_digest`、`impact_revision` 和 `source_generation_id` 仍保留为失效与追踪信息，但不作为跨执行历史的事实相等条件。

### 增量与全量等价性验证

`scripts/incremental_import_end_to_end_acceptance.py` 显式输出 `yearly_artifact_contract`：

- `fact_partition_equal` 比较增量 reconcile 与完整 replace 的最终事实分区；
- 三个 `*_invalidated_impacted_year` 门禁分别验证跨周 append、同周 append 和历史 reconcile；
- 三个 `identical_*_unchanged` 门禁验证重复导入不抖动事实、revision 或 key；
- `yearly_key_interpretation.artifact_keys_equal` 只保留为解释性观测。

以上门禁任一失败，终验脚本整体状态为 `failed`。


## 实现与历史证据

- [generation coordinator](../../backend/services/yearly_review_generation.py)：精确key去重、前台优先与后台持续生成。
- [artifact sidecar](../../backend/domains/yearly_review/artifact_cache.py)：独立压缩持久化及损坏miss。
- [年度总结交付](../reports/2026-08-12-yearly-review-v2-delivery.md)、[统计语义补修](../reports/2026-08-24-yearly-review-semantic-correction.md)、[共同同期比较](../reports/2026-08-30-yearly-review-common-period-comparison.md)。

上述报告保留各自版本的重算耗时与验收结果，不作为当前版本新采样。
