# 年度总结 V2 完整重构交付报告

日期：2026-08-12
状态：**PASS，内容重构、性能优化、统计验收与用户展示验收持续收口（当前 content `yearly_review_v2_13`）**
实施依据：[`../designs/2026-08-12-yearly-review-v2-content-data-contract.md`](../designs/2026-08-12-yearly-review-v2-content-data-contract.md)
执行计划：[`../archive/06-productization-closeout/2026-08-12-yearly-review-v2-rebuild-plan.md`](../archive/06-productization-closeout/2026-08-12-yearly-review-v2-rebuild-plan.md)

## 1. 最终结论

`/yearly-review` 的 Desktop/Compact 与 Phone 自定义年度总结已由旧模块平铺重建为确定性的八章个人音乐年鉴。三档视口共享年度事实与生成链路，Desktop/Compact 使用完整杂志年鉴，Phone 使用独立“口袋音乐年鉴”presentation。新报告包含：

1. 报告护照与年度头条。
2. 播放次数、播放时长与个人 Billboard 双视角荣誉。
3. 唯一年度赛季时间线与可展开十二月事实账本。
4. 陪伴、沉迷、深听、发现与回归关系。
5. 收听生活与行为事实。
6. 年度纪录精选；完整播放纪录与 Billboard 纪录留在原独立页面。
7. 主曲风、地区流行、语言和发行年代迁移。
8. 同比、个人历史参照、年度结语与完整榜单。

所有解释性内容都由结构化事实、coverage 与版本化策略生成，不调用 LLM。Phone 年度总结已经迁移到 V2，但没有照搬桌面 DOM。最终产品入口只保留自有年度总结；官方 Wrapped 前端展示已退役，官方导入数据与 `/api/wrapped-hub` 仅作只读兼容冻结。

最终验收分为统计语义与用户展示两层。统计层继续保证同比只使用真实对齐窗口、Passport 与榜单共享规范实体粒度、YTD 品味只比较完整季度，公开纪录、阶段和结语只使用可核验事实；展示层不再把这些内部防御机制写给普通用户，而是使用日常中文、六项直观同比、实体封面、可点击详情、固定章节导航和单一“完整榜单”入口讲述年度故事。内容版本独立于 schema 版本，统计、编排或公开展示语义变化都必须提升 `content_version`，以同时分流进程 LRU 与持久 sidecar。

2026-08-15 的播放时间归属修复将 content 提升到 `yearly_review_v2_13`：连续同曲默认只在实际空闲不超过 5 分钟时合并；每次逻辑播放按达到成立条件的 `counted_at` 归属年份，收听时长按北京时间区间切片。旧 v2.12 缓存不会被新报告复用。

## 2. 范围与不变量

### 已交付

- `YearlyReviewV2` Pydantic 契约、统一过滤上下文与 Coverage Passport。
- 播放双榜、个人 Billboard、两类纪录、时间与品味适配器。
- 八章确定性内容 builder 和共享 Orchestrator。
- 修订感知缓存、三条只读 API 和精选纪录兼容响应。
- Desktop/Compact 完整年鉴体验，以及 Phone 独立口袋年鉴、长加载、错误/空态和附录下钻。
- 面向用户的简洁文案、全章实体封面、六项同比与章节导航。
- API/OpenAPI、真实数据、五档视口和 Chromium/Firefox/WebKit 门禁。

### 明确未改

- 官方 Wrapped 导入表、只读兼容 API 和数据语义。
- AI 年报与 Power Score。
- 原始 `plays`、`tracks`、`track_artists` 或数据库 schema。
- 完整长图/PDF、年度播放列表、全球 percentile 与跨用户比较。

## 3. M0：真实数据审计与策略冻结

### 3.1 审计口径

审计命令：

```bash
.venv/bin/python scripts/audit_yearly_review_v2.py \
  --years 2023,2024,2025 \
  --merge-level 2 \
  --json-output /tmp/yearly_review_v2_audit.json
```

统一参数：`min_ms=30000`、`music_only=true`、连续播放合并、动态阈值、L2、排除精选集、Billboard 周五 12:00 起算、歌曲/专辑/艺人 Top N 为 30/20/20。脚本只读复用现有有效播放、canonical track、album project、有效艺人署名、Year-End、播放纪录和 consumer taste taxonomy。

### 3.2 三年内容容量

| 年份 | 有效播放 | 有效时长 | 活跃日 | 歌曲 | 专辑项目 | 艺人 | Billboard |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2023 | 13,085 | 784.50h | 359 | 1,608 | 432 | 417 | 52/52，complete |
| 2024 | 18,360 | 1,201.19h | 355 | 2,507 | 540 | 457 | 52/52，complete |
| 2025 | 17,567 | 1,134.97h | 364 | 2,754 | 623 | 440 | 52/52，complete |

三年均能稳定提供播放榜 50/30/30、个人 Billboard 50/30/30 和 12 项 Year-End honors。播放榜与 Year-End 的匹配歌曲名次差中位数为 5–8、P75 为 10–13；因此双榜差异门槛冻结为歌曲至少 10 名、专辑/艺人至少 5 名。

播放纪录每年有 69–70 个非空叶节点和 2,173–2,268 个候选，问题不是内容不足，而是必须去重和限制垄断。三年都有完整十二个月；榜首易主正文最多三个，每月最多一个节点，只有持续至少两个月的变化才形成阶段边界。

关系候选按年内有效播放至少 10 次建立。正式规则要求：新关系在报告年首次出现，至少 10 次、3 个活跃日和 30 天跨度；真正回归在报告年前已有播放，沉寂至少 180 天，回归后至少 10 次和 3 个活跃日。三年均有充足候选。

### 3.3 品味覆盖与策略版本

| 年份 | 主曲风已知 | 地区流行已知 | 语言已分类 | 发行年代已知 |
| --- | ---: | ---: | ---: | ---: |
| 2023 | 92.43% | 8.77% | 98.01% | 100.00% |
| 2024 | 92.47% | 42.49% | 98.71% | 100.00% |
| 2025 | 92.29% | 48.12% | 98.65% | 99.77% |

coverage gate 冻结为：至少 70% 可生成核心结论，40%–69.99% 只能辅助观察，低于 40% 不生成迁移结论。版本化策略为：

- `relationship_policy_v2`：关系资格、证据、角色配额与用户侧去重。
- `highlight_policy_v2`：纪录白名单、去重、评分与 6–8 条多样性约束。
- `season_stage_v1`：6–10 个转折节点、3–5 个可成立阶段及降级。

## 4. M1：契约、过滤上下文与 Coverage Passport

`backend/models/yearly_review.py` 定义 `schema_version=yearly_review_v2` 的固定顶层响应，包含 `complete/year_to_date/observed_range/insufficient/empty` 五种状态、A/B/C 证据等级、充分/有限/不可用 coverage 和全部章节的合法空态。

一次请求由 `YearlyReviewFilterContext` 统一解析：

- 有效阈值、音乐过滤、连续播放合并、动态阈值。
- L1/L2/L3、精选集设置。
- 三类 Billboard Top N 与周边界。
- display taxonomy、艺人元数据、artist identity、有效署名 revision。
- track group 与 album project 内容 revision。

fingerprint 使用版本化、排序稳定的 canonical JSON + SHA-256；任一语义参数或 revision 改变都会分流缓存，字典插入顺序不影响结果。

Coverage Passport 分开记录：

- Play 首末日期、自然日跨度、活跃日、导入覆盖和内部缺口。
- Billboard 直接适配 Year-End meta，不重猜周完整性。
- Comparison 检查上一年是否覆盖同一对齐窗口，不可比时给原因而非伪 `0%`。
- Taste 使用 M0 冻结门槛。

同比计算不会只在文案层标记“同期”：Orchestrator 会把当前观察范围映射到上一年、处理闰日 clamp，并在 baseline coverage 不足时把 `baseline_stats` 置空。工作日/周末日均以观察区间内真实自然日数量为分母，不使用固定 `/5`、`/2`，也不使用活跃日数量。

即使自然年首末日期完整，`internal_gap_status=unknown` 也独立保留，不能生成“最长未听歌空窗”等不可核验结论。

## 5. M2：现有数据能力适配

### 5.1 播放双榜

- 歌曲沿用 canonical track key。
- 专辑沿用 album project identity。
- 艺人沿用 effective track credits fan-out 与 canonical artist identity。
- 每类同时输出 `by_plays` 和 `by_hours`，保留播放、时长、份额、活跃日/月、本地首末日期与详情链接。
- 正文候选上限为歌曲 50、专辑 30、艺人 30，并保留完整可用实体数。

### 5.2 个人 Billboard 与两类纪录

Year-End 不修改 Score 或 Power Score，原样保留 `semantics_version`、coverage、honors 与年榜事实。专辑用 canonical name + artist 对齐 album project；无法对齐时保留显式 fallback identity。Billboard records 固定使用整数年份范围 `[year, year]`。

两类纪录统一为 `YearlyHighlightCandidate`：稳定 ID、来源、family、record key、category、fact type、实体、primary metric、JSON-safe 原始值、evidence grade、source refs 和 deep link。播放记录保留六族，Billboard records 归入 championship、longevity、endurance、movement、hall_of_fame、self_replacement_blocker、market、quirky 八族。

### 5.3 时间与品味

日、小时、星期、月、累计与行为事实复用播放统计 service；taste 只调用 `build_consumer_taste_profile()`，不复制 genre/language resolver。完整年比较上半年与下半年；YTD 仅比较最近两个完整季度，不足两个完整季度时只展示全年分布，不生成伪迁移。驱动实体与份额变化使用同一日期切片。

真实 2025 探针得到 2,754 首歌曲、623 个专辑项目、440 位艺人；Year-End 为 `year_end_v3`、52/52 周、50/30/30 行，专辑 project 对齐 30/30；Billboard/播放纪录内部候选分别为 976/2,257。

## 6. M3：确定性内容编排

内容 builder 将结构化事实编排为八章，且不重新计算另一套榜单、元数据或纪录：

- 护照只陈述观察范围、状态与核心指标；头条最多三条并按主题去重。
- 播放次数、播放时长和个人 Billboard 并列；不完整年榜只称“阶段领先”。
- 每个月在正文事实表中只出现一次；转折受月份唯一、事件配额和总量约束。
- 每条解释性关系至少有两个指标，同一实体最多承担两个角色。
- 收听生活使用归一化工作日/周末、时段、复听、探索、集中度和平台事实。
- 纪录先资格过滤与语义去重，再按幅度、持续性、历史稀有度、比较、具体性和证据质量评分。
- style、scene、language、release era 独立处理；unknown 进入分母，迁移需同时满足份额变化与具名驱动证据。

真实 2025 报告生成 6 项护照指标、3 条头条、12 项 Year-End honors、6 条双榜分歧、12 个月事实、10 个转折节点、8 条关系、8 项生活观察和 7 条精选纪录。公开纪录使用显式 renderer 白名单；未知/internal key、blocked map、重复年榜首和缺少周期/数值证据的候选不会进入 UI。早期 v2.6 曾保留 1,435 条分页候选目录；v2.11 已删除该目录，只保留 7 条正文精选。

时间线只接受具备单一日期或榜周锚点的事件，并使用事件优先级与族内归一化评分，原始大数值不能劫持排序；同月不同语义事件不会混并证据。阶段只在连续月份存在多数冠军时成立，无法证明时返回 `no_stable_phase` 和空 stages，不再等长强切月份。结语从全年节奏、陪伴主线、阶段/高峰与品味落点重新综合，不复制开篇 headline。

品味方面，style 92.29%、language 98.65%、release era 99.77% 可形成核心观察；scene 48.12% 只作辅助。最终只生成有驱动证据的 Pop 与 2010s 份额变化，不用覆盖不足的 scene 编故事。

## 7. M4：共享编排、API 与缓存

### 7.1 共享加载与降级

每份报告只加载一次完整有效播放 frame，只构建一次 track/album/artist entity frames，并从共享结果切出本年、上年和半年窗口。一个 Billboard source 同时服务 honors、season、records 与 appendix。

核心统计主干失败正常暴露；非关键章节单点失败写入 `methodology.limitations` 并降级为合法空章。空年份不会计算全历史实体、Billboard 或纪录；真实 2099 空报告冷态约 765ms。

### 7.2 缓存与失效

`yearly_review` 命名空间缓存内部 artifact。v2.11 起 artifact 只保存主报告与同一组精选纪录，不再重复序列化上千条公开候选。缓存键包含：年份、schema version、独立 `content_version`、filter fingerprint、三项策略版本、`year_end_v3`、display taxonomy、艺人/语言/身份/署名/track group/album project revisions 及稳定的播放事实 revision。

播放事实 revision 由 `plays` 的行数、最大 ID、最新时间与总时长，核心曲目/专辑/艺人表 cardinality 和 migration version 组成。它会因正常追加导入而变化，但不会因 AI task、job log 或 WAL checkpoint 等无关写入失效；治理元数据继续使用各自显式 revision。旧 artifact 因 content key 改变自然不可达，并由 sidecar 32 条上限逐步淘汰。

导入、身份/署名 rebuild、统计设置、版本归并、album project 重建、genre approve 与 language review decision 都会使年度缓存失效。

### 7.3 API

```text
GET /api/yearly-review/available-years
GET /api/yearly-review/{year}
GET /api/yearly-review/{year}/records?page=1&page_size=50
```

三条 endpoint 均有 Pydantic response model；年份 2000–2100，页大小 1–100。主响应只含精选纪录和候选计数；兼容 records endpoint 保留相同过滤指纹，但只返回与正文一致的精选集合。完整播放纪录和 Billboard 纪录由各自独立页面承载。空年份返回合法 `empty` payload，`X-Request-ID` 继续由全局 middleware 处理。

## 8. M5：Desktop/Compact 年鉴体验

### 8.1 数据链路

前端新增 V2 类型、query hook、章节 feature 和编辑部年鉴样式。Query 参数完整继承分析设置，query key 使用稳定过滤上下文，后端 `filter_fingerprint` 作为报告身份与组件重置边界。

主报告兼容 GET 的等待上限为 120 秒；首次生成显示阶段性等待文案与已等待秒数，不伪造百分比。`yearly_review_generation_v1` 以服务端 `requested_at` 作为计时锚点，切换年份或离开页面再返回不会从 0 重新计时，也不会把上一年 placeholder 错显为当前年。前端取消 HTTP 请求只停止当前等待，后台 worker 继续完成 artifact。

### 8.2 展示与边界

Desktop/Compact 使用暖奶油纸张、深色唱片封面、期刊编号和不对称编辑排版。没有恢复旧“听歌人格”，完整附录每页 10 行；年度纪录章只展示 6–8 条精选。

M5 首次交付时，`YearlyReviewPage` 互斥启用：

- `<768px`：V1 available years、`/wrapped/{year}/full` 与 `CustomSummary`。
- `>=768px`：V2 available years、`/yearly-review/{year}` 与 V2 experience。
- 冻结兼容：`/wrapped-hub/available-years` 与 `/wrapped-hub` 继续保留 contract 和 smoke，但不再有前端消费者。

该阶段边界已被 M7/M8 替代：当前 Phone/Compact/Desktop 全部消费 V2，页面只保留自有年度总结；年份继续保留在 URL。

### 8.3 浏览器阶段修复

- 消除 Records/Appendix 重复 React key。
- 去除可点击纪录卡与实体深链的嵌套 `<a>`。
- 纪录目录数量改用 `input_total`，不再把重叠 family counts 相加。
- Spotify 封面失败时显示实体首字母占位。

### 8.4 用户展示重构

- 年报正文不显示统计口径、过滤指纹、策略版本、证据等级、coverage、limitations 或“可比基线”等审计术语；这些信息继续保留在后端契约、日志、测试和 probe 中。
- 所有章标题只保留章节编号、栏目短名和主标题，不再附加解释性 subtitle；封面也移除说明段落。
- 顶部六项指标改为“年度播放 / 年度时长 / 年度活跃天数 / 年度播放曲目 / 年度播放专辑 / 年度播放艺人”，同比只在数值右侧显示红/绿箭头和百分比。
- 荣誉、时间线、关系、收听生活、纪录、品味变化、结语和完整榜单统一使用共享实体媒体组件；歌曲、专辑、艺人优先显示封面并链接既有详情页。
- 附录只保留“播放榜 / 个人 Billboard”两个用户入口，标题统一为“完整榜单”；月份只在年度时间线的可展开明细出现，方法信息不进入消费界面。
- 年份按钮由小到大排列，Desktop/Compact 默认打开最近一个完整年度；完整年度封面不重复显示状态和起止日期，当前年保留“进行中 · 截至日期”。封面三条头条和海报按钮均已移除。

## 9. M6：最终验证与性能

### 9.1 后端与 API

| 门禁 | 结果 |
| --- | --- |
| Yearly V2 unit + contract | 87 passed |
| Wrapped / Year-End / playback records 回归 | 28 passed |
| 全量 unit | 1,051 passed |
| 全量 contract | 329 passed |
| OpenAPI operation audit | 185 operations，0 unaccounted |
| OpenAPI parameter audit | 85 obligations，0 unaccounted |
| API smoke | 119/119；118 GET covered + 13 excluded；0 unaccounted |

API smoke 已纳入 available-years、空年份主报告与分页 records；真实年份由专用 probe 负责，避免广域 smoke 重复触发高成本计算。

### 9.2 四年真实数据、内容指纹与预算（早期含完整目录基线）

| 年份 | 状态 | 优化前冷响应 | 真实重算 | 跨进程持久命中 | 热响应 | JSON | 当时目录候选 | 语义指纹前 12 位 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2023 | complete | 79.62s | 15.94s | 12.29ms | 1.64ms | 236,380 B | 3,140 | `27be4fcebf59` |
| 2024 | complete | 82.47s | 11.77s | 23.68ms | 1.87ms | 243,453 B | 3,246 | `9997dd971b0e` |
| 2025 | complete | 80.94s | 12.25s | 12.48ms | 1.64ms | 241,111 B | 3,233 | `970d6be0dfc3` |
| 2026 | year_to_date | 76.27s | 9.95s | 11.31ms | 1.63ms | 226,609 B | 2,979 | `2067d274350c` |

冻结预算为未压缩主 JSON 不超过 512 KiB、真实冷响应不超过 30 秒、热响应不超过 250ms；四年全部通过。2026 响应 gzip 为 27,805 B。

冷启动专项通过 `cProfile` 定位到关系历史计算：旧实现对每个年度实体重新扫描完整历史、重复执行 `astype(str)` 与 `to_datetime()`，2026 单章累计约 65.4 秒。现改为每种实体类型一次性聚合首次播放与报告年前末次播放日期，2026 单年独立冷启动从 88.74 秒降至 17.86 秒；最新四年同进程重算稳定在 9.95–15.94 秒，较原交付基线下降约 80%–87%。播放纪录同时复用编排层已有年度事件/实体帧，独立记录页仍保留原加载路径。

`yearly_review_v2_probe_v4` 在当时保留 coverage、身份去重、内容体积、30 秒真实重算预算以及主报告/纪录目录语义指纹，并新增 content version、公开文案、精选证据、结语去重和阶段状态不变量。v2.11 删除完整目录后，records 指纹只代表与正文一致的精选集合。`recompute` / `persistent` 双模式仍分别验证真实计算和新进程持久命中，后续同一数据 revision 下可直接用指纹识别内容漂移。

### 9.3 跨进程持久缓存与后台预建

年度 artifact 使用独立 `data/yearly_review_cache.db` sidecar SQLite，不写入 `spotify_stats.db`，避免缓存写入改变主库文件 revision 后自我失效。持久层只接受完整 cache key 精确命中，payload 使用 zlib 压缩并限制解压后最大 64 MiB，最多保留 32 个 artifact；格式错误、尺寸异常或压缩损坏的行会删除并按 miss 重新生成，不返回 stale 数据。

2026 先以 `--cache-mode recompute` 在独立进程强制重算并持久化，再启动第二个 Python 进程、清空内存 LRU，以 `--cache-mode persistent --max-cold-ms 1000` 验收：

| 场景 | 响应 | 主报告指纹 | 当时纪录目录指纹 |
| --- | ---: | --- | --- |
| 强制重算并写入 sidecar | 18.54s | `2067d274350c…` | 基线 |
| 新进程持久命中 | 35.24ms | 一致 | 一致 |
| 同进程后续热命中 | 4.98ms | 一致 | 一致 |

启动 warmup 会在既有播放/Billboard 热路径之后预建最新默认年份；统计设置变更与流式导入完成后也会刷新该年份。Desktop/Compact/Phone 打开年度总结后，前端通过 `POST /api/yearly-review/prewarm` 按当前完整筛选上下文一次提交全部可用年份，并通过 `GET /api/yearly-review/generation-status` 读取状态。单 worker 优先处理当前年份，其余年份从近到远排队；用户点击 queued 年份会提升优先级。相同 exact key 只生成一次，缓存命中不经过冷构建全局锁，后台生成旧年份时已缓存年份仍可立即返回。冻结的官方 Wrapped 兼容接口不进入该队列。probe 默认保持 `recompute` 模式，以免持久命中掩盖真实计算性能；`persistent` 模式专门验证重启后的用户等待时间。

### 9.4 前端门禁

| 门禁 | 结果 |
| --- | --- |
| Vitest | 62 files / 475 tests passed |
| TypeScript + Vite production build | PASS |
| 本次变更文件 ESLint | PASS |
| 年度 route matrix | 360/390/430/768/1280，5/5 PASS，0 overflow/error |
| control inventory | 15 routes × desktop/mobile；1,533 controls；283 touch targets；0 violation |
| Chromium / Firefox / WebKit | route markers + 七组 core interactions 全部 PASS |

年度交互覆盖荣誉 Tab、十二月账本、品味轴切换、附录榜单分页、单一年度模式、实体详情深链与浏览器返回。全仓 `npm run lint` 仍有 181 个既有错误，主要位于旧 Billboard 类型、AI、Settings 与共享 UI；本次年度文件定向 ESLint 为 0 error。

### 9.5 统计语义验收复验（content v2.6）

| 门禁 | 结果 |
| --- | --- |
| Yearly V2 unit + contract | 103 passed |
| 前端 Yearly V2 Vitest | 5 passed |
| Ruff + TypeScript + Vite build | PASS |
| 2023–2026 真实重算 | 9.80–15.43s；热 5.04–21.65ms；全部 PASS |
| 新进程持久命中 | 9.75–19.71ms；热 4.64–5.28ms；全部 PASS |
| 真实 API | 2022 observed_range / 2025 complete / 2026 YTD / 2099 empty，均返回 v2.6 |
| 五档 route matrix | 360/390/430/768/1280，0 error/warning/overflow |
| 1023 Compact 人工检查 | 正文完整、实体/附录深链可用、0 overflow |
| 控件库存 | desktop/mobile 共 160 controls，0 violation |
| Chromium / Firefox / WebKit | route markers + 七组 core interactions 全部 PASS |

真实 2025 的 Passport 为 2,754 首规范曲目、623 个专辑项目、440 位署名艺人；工作日/周末日均、同期比较、YTD 季度比较均由新增单元测试锁定。方法页只显示业务指标、周期、实体粒度与自动限制，不再暴露 schema/policy key、过滤指纹或 A/B/C 证据等级；实体深链由共享 builder 统一生成，fallback records 链接使用真实 `?family=` 参数。

### 9.6 用户展示验收复验（content v2.8–v2.9）

| 门禁 | 结果 |
| --- | --- |
| Yearly V2 unit + contract | 104 passed |
| 前端 Yearly V2 Vitest | 9 passed |
| Ruff + TypeScript + Vite build | PASS |
| 2023–2026 真实重算 | 10.65–16.54s；热 26.56–29.85ms；全部 PASS |
| 新进程持久命中 | 10.20–21.07ms；同进程热 4.83–5.85ms；全部 PASS |
| 主 JSON | 224,135–239,178 B，低于 512 KiB 预算 |
| `yearly_review_v2_probe_v5` | 用户文案、封面/深链、YTD 措辞、纪录重复、阶段状态全部 0 issue |
| 1280 人工复验 | 年份升序、完整年度无状态/日期、YTD 截止日期保留、箭头颜色正确、0 横向溢出 |
| 页面控制台 | 0 error / warning |

真实 2025 首屏六项 KPI 显示红色向下/绿色向上箭头和百分比，不再显示“高/低”或绝对差值；完整年度状态和日期、三条头条与海报按钮均不出现。真实 2026 保留“进行中 · 截至 2026.07.24”。2025/2026 的 season、relationships、listening life、records、taste 和 epilogue 实体引用均已补齐封面与详情链接。内部 limitations 仍保留在 API artifact 中供诊断，但前端不渲染。

### 9.7 人工验收细节复验（content v2.10）

- KPI 可见文案只保留箭头与百分比，完整“比去年高/低”语义继续保留在 accessible label。
- 荣誉分歧故事在 907px 实页为两列，在 800px 自动回到单列，两档均为 0 横向溢出。
- 新关系标题按实体区分为“今年发现的新歌 / 今年新听的专辑 / 今年认识的新艺人”；真实 2025 两张专辑卡均显示“今年新听的专辑”，不再使用“新名字”。
- 同专辑/艺人多首入榜的 renderer 强制要求 `track_count`。真实 2025 分别显示 The Life of a Showgirl 同周 12 首、Michael Wong 同周 17 首；缺少准确首数时该候选不公开。
- 年度后端 106 项、前端全量 480 项（其中 Yearly V2 10 项）通过；真实 API 返回 `yearly_review_v2_10`，实页控制台 0 error/warning。

### 9.8 年度纪录与章节节奏复验（content v2.11）

- 删除年报中的“更多年度纪录”、展开状态、分页请求和相关样式；完整播放纪录与 Billboard 纪录继续由原有独立页面承载。
- 后端仍从播放纪录与个人 Billboard 候选中确定性挑选精选，但 artifact 的 `record_catalog` 只保存最终精选，不再把上千条候选二次公开序列化。兼容 `/records` 返回与正文相同的集合。
- 真实 2024 主报告为 7 条精选，兼容 records 响应同样为 7 条且 ID 完全一致。
- 全部章节纵向 padding 最终从 `clamp(72px, 10vw, 138px)` 收紧为 `clamp(48px, 5.5vw, 80px)`；897px 下相邻内容到下一标题统一约 99px，较原约 179px 缩短约 45%。
- 真实 897px 页面为 0 “更多年度纪录”控件、7 张精选卡、0 横向溢出、0 console error/warning。
- 年度后端 106 项、前端全量 479 项与 production build 通过；2024 persistent probe v5 为 0 issue，v2.11 命中 81.20ms、同进程热响应 4.68ms。

### 9.9 后台生成与连续计时复验（generation v1）

- 新增 `yearly_review_generation_v1` 单 worker 协调器、202 Accepted 批量预热与只读状态接口；任务按完整 artifact key 去重，当前年份优先，其他年份从近到远排队。
- 前端计时使用服务端 `requested_at`，年份 A → B → A 或离开年度路由再返回时保持累计等待；queued/running 状态优先于短暂 HTTP error，ready 后自动重新获取正文。
- 报告 GET 消费 React Query AbortSignal，但取消请求不取消后台 task；兼容 GET 等待同一任务，120 秒后只返回 504，worker 仍继续。
- 移除跨年份全局 singleflight。自动测试锁定：相同 exact key 只 build 一次、queued promotion、revision drift 不写旧 key、失败可重试、后台冷建不阻塞另一 ready 年份、终态 registry 最多 32 条、只能预热真实可用年份。
- 验证：后端全量 1,596 项通过；年度专项 116 项通过；前端全量 484 项通过；API smoke 120/120；production build、Ruff、定向 ESLint、OpenAPI 187 operations / 85 parameter obligations 均为 0 unaccounted。

### 9.10 Phone V2 迁移复验

- Phone 自定义总结与 Desktop/Compact 共用 `YearlyReviewV2` available years、report、generation status、prewarm 和过滤指纹；显式 URL 年份优先，无 URL 时默认最新可用年度，包括尚未结束的当前年。
- content v2.12 将全局简繁体偏好应用到年度动态文案与实体名称；回归事件在正文和实体卡中明确歌曲、专辑、艺人类型。2025 年“認了吧”复核确认为 Eason Chan 的专辑回归：2024-08-31 与 2025-05-02 的有效播放形成 243 天间隔，艺人详情的歌曲区仅列个人 Billboard 入榜歌曲，而专辑区已有《認了吧》10 次播放，因此原问题是实体类型表达不清，并非播放事实丢失。
- `YearlyReviewPhoneExperience` 独立组织八章内容，没有挂载或缩放桌面章节 DOM。封面为 2×3 KPI，章节入口为 sticky 进度 + Bottom Sheet，阶段为纵向时间线，月份一次只展开一个。
- 荣誉、关系、收听生活、纪录、品味迁移与结语全部改为单列/触控友好的卡片；年度纪录展示完整精选集合。完整榜单正文 Top 5，全屏每页 10 条且不使用 table，关闭后恢复焦点和原滚动位置。
- route marker 明确禁止 Phone V2、Desktop V2 与 legacy `CustomSummary` 同时挂载；页面不再挂载官方 Wrapped 组件。
- 验证：本轮前端全量 66 files / 498 tests、production build 通过；年度后端非脚本专项 98 项、补充契约/模型/纪录测试 20 项通过。年度 route matrix 在 360/390/430/768/1280 五档均为 0 console error/warning、0px 横向溢出；Chromium/Firefox/WebKit Phone route marker 全部通过；smoke 脚本单元测试 6 项通过。

### 9.11 Phone 人工验收修复

- 年度荣誉的多个称号由长句改为可换行标签；所有艺人实体使用圆形头像，歌曲与专辑封面保持方形。
- 时间线只保留左侧红色月份，删除事件内部重复序号；实体行增加独立间距。月份账本改为横向月份胶囊、三列月度摘要和有留白的主角列表。
- 收听生活和结语会检测正文是否已经写出主指标，避免同一数字紧接着再次出现。
- 修复普通纪录实体链接误套黑色背景的问题，并为关系标题、纪录 kicker、品味标签和结语建立明确的移动字体层级。
- 品味迁移改为一行四维切换、分布白卡和变化黑卡；完整榜单的播放榜/个人 Billboard 切换改为等宽双列。
- 月卡用 JAN–DEC 替代重复月份标题；结语延续实体改为双列封面货架。完整榜单正文筛选移除深色外框，排名值改用年鉴衬线数字并缩小单位，全屏筛选继续保持清晰的紧凑选中态。

### 9.12 单一年度入口收口

- Desktop/Compact/Phone 的年份按钮统一只显示年份，删除当前年份的“进行中”后缀；YTD 状态仍在报告封面显示截止日期。
- 删除“年度总结 / 官方 Wrapped”模式切换、`OfficialWrapped` 组件、`wrapped-hub` 前端查询键和展示类型；年度路由不再请求官方数据。
- 后端 `/api/wrapped-hub`、官方导入表和读取服务采用冻结而非删除：继续满足历史数据、API contract 和诊断回溯，但不再扩展产品能力。自有 `wrapped_service` 因仍被 AI 与年度统计适配层使用，不在清理范围内。
- 定向 18 项测试、ESLint 与 production build 通过；真实 1280px 页面和 432px 页面均只显示 2022–2026 年份与自有年鉴，432px 横向溢出为 0。

## 10. 交付文件地图

核心后端：

- `backend/models/yearly_review.py`
- `backend/domains/yearly_review/`
- `backend/domains/yearly_review/artifact_cache.py`
- `backend/services/yearly_review_service.py`
- `backend/api/yearly_review.py`

核心前端：

- `frontend/src/types/yearly-review-v2.ts`
- `frontend/src/hooks/useYearlyReviewV2.ts`
- `frontend/src/features/yearly-review/`
- `frontend/src/features/mobile/yearly-v2/`
- `frontend/src/pages/YearlyReviewPage.tsx`

审计与验证：

- `scripts/audit_yearly_review_v2.py`
- `scripts/yearly_review_v2_probe.py`
- `backend/tests/unit/test_yearly_review_*.py`
- `backend/tests/contract/test_yearly_review_v2_contract.py`
- `frontend/src/tests/yearly-review-v2.test.ts`

## 11. 发布、回滚与后续

M8 后不建立长期 feature flag 或第二年度模式。V2 在 Desktop/Compact 与 Phone 中共享数据层并互斥挂载独立 presentation；如需回滚 Phone 展示，只恢复 `YearlyReviewPage` 的 Phone presentation 分支，V2 只读 API/domain 与冻结的 `/wrapped-hub` 兼容接口可以保留，不重新暴露官方 Wrapped UI，也不删除数据库中的官方导入数据。

后续独立方向按优先级为：

1. 分享/PDF、年度播放列表和 AI 编辑导语。
2. 安全部署后的 Phone 真机与 PWA 安装验收。
3. 如真实数据规模继续增长，再评估 Billboard/播放纪录阶段缓存或后台预计算。

冷态性能债已在不改变统计口径的前提下收口到 30 秒预算内；其余方向均不影响本次内容重构完成。
