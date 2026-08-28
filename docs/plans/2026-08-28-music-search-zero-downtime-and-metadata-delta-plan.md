# 音乐查找零停机、上一可用版本与元数据增量维护完整修复方案

> 创建日期：2026-08-28
> 状态：已实施并验证；候选/统计 LKG、原子切换、任务竞态、署名增量与公开边界已完成，验收证据见对应交付报告
> 适用范围：Masthead Quick Open、`/music/search`、候选索引、精确统计快照、曲目署名与艺人身份维护、后台任务队列
> 现行方向：[`2026-08-16-music-search-direction-realignment.md`](2026-08-16-music-search-direction-realignment.md)
> 当前规则：[`../reference/music-metadata-management.md`](../reference/music-metadata-management.md)、[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)

> 2026-08-28 实施补充：原计划 migration 60–62 按设计落地；为完整实现 4.4 的即时撤销展示边界，
> 追加 migration 63 `music_search_entity_deny_overlay`。历史 snapshot lineage 不足时，曲目署名增量会
> 明确回退 shared-full，不以放松证明条件换取表面命中。完整结果见
> [`../reports/2026-08-28-music-search-zero-downtime-and-credit-delta.md`](../reports/2026-08-28-music-search-zero-downtime-and-credit-delta.md)。

## 0. 决策摘要

本轮不恢复“每次输入时同步加载 lifetime 播放帧并计算 Billboard”的旧重搜索，也不接受“精确统计
快照未 ready 就让名称搜索返回空结果”。目标架构明确分成三个相互独立的平面：

1. **候选服务平面**：始终从最后一次成功发布的 `active_generation_id` 返回名称、别名、封面和详情
   深链；后台构建失败或统计 warming 不得让它停机。
2. **候选构建平面**：新索引只写入影子 generation，通过完整性校验后原子切换 active 指针；失败时
   保留上一可用 generation。
3. **精确统计平面**：播放次数、总时长和 Billboard 摘要继续使用精确 fingerprint；新快照未完成时
   可返回明确标记的上一可用统计，或暂时不显示统计，但不能阻塞候选。

曲目署名、艺人身份和歌曲关系修改必须进一步按影响范围增量维护。角色调整不应重建统计；署名成员
增删只更新受影响 canonical track、canonical artist 和实际涉及的 Billboard 周。只有证明不足、规则
版本变化或影响范围超过安全上限时才回退全量重建；即使回退，用户仍使用上一可用版本搜索。

## 1. 已核实的当前事实

以下事实来自 2026-08-28 当前 checkout、运行中的本地 API 和真实 SQLite，只用于本次方案基线，实施
前必须重新验证：

| 项目 | 当前事实 | 结论 |
|---|---:|---|
| 曲目署名 revision | `current=35`、`active_aggregate=33`、`pending` | 最新两次修改尚未发布 |
| 最近重建任务 | 只有 revision 34，状态已经是 `done` | revision 35 被同实体任务去重后丢失 |
| 搜索 API 当前状态 | `snapshot_status=unavailable`、0 个候选 | UI 消费链被精确快照门禁阻断 |
| 同库 `any_local` 候选 | 约 0.136 秒，返回 13 个结果 | active 候选 generation 仍可读 |
| 同库旧 legacy 搜索 | 约 18.57 秒 | 能返回结果，但不适合作为自动兜底 |
| 候选索引 | active generation 仍在，19,443 个文档 | 不是索引文件丢失 |
| 当前支持的统计变体 | L2/L3 × dynamic/fixed，共 4 套 | 每次全量重建成本仍高 |
| 最近一组有效 context | 31,758 行 | 单次署名变化不应整体重新计算 |
| 样本 `track_id=4375` | 自身 4 条原始播放、约 3 个自然周 | 当前全局失效与实际影响严重不成比例 |
| 相邻历史完整维护 | 搜索 rebuild 约 20 分 23 秒 | 全量回退必须离开用户交互可用性路径 |

当前候选 builder 已经在新 generation 中写文档，并在一个事务中更新
`active_generation_id/previous_generation_id`。需要修复的不是是否有 generation，而是以下状态耦合：

- builder 开始时把共享 `music_search_index_state.status` 改成 `building`；
- builder 失败时把同一字段改成 `failed`；
- candidate repository 只有在该字段为 `ready/degraded` 时才读取 active generation；
- 失效逻辑还会清空 active generation 对应的 `source_revision/candidate_index_version`；
- candidate service 在精确 snapshot 不 ready 时直接返回空响应。

因此，物理上仍然完整的上一索引被业务代码主动停用。

## 2. 问题拆解与根因

### 2.1 服务状态与构建状态混用

`music_search_index_state` 同时表达“当前是否有可服务索引”和“下一版构建到了哪里”。这两个事实可能
同时成立：active generation 正常服务，target generation 正在构建。用一个 `status` 字段只能表达其一，
最终造成构建期间停机。

### 2.2 候选资格与完整统计 context 过度绑定

当前 `eligibility=current` 要求同一 fingerprint 的精确统计 snapshot ready，并在候选 SQL 中 join
`music_search_entity_context`。这能保证候选与详情当前过滤口径完全一致，但把“能找到这个本地音乐
实体”错误提升成了“必须先完成四套播放/Billboard 统计”。

正确做法是保留资格层次，而不是返回空结果：

- `exact`：当前统计 fingerprint 精确 ready；
- `last_known_good`：使用上一份成功资格集合；
- `local_catalog`：使用当前 active 候选文档中的本地已播放实体；
- `fallback`：索引首次缺失时使用有界、只读的本地目录 resolver。

### 2.3 失效操作破坏上一可用事实

当前 mutation 立即把 ready snapshot 标成 stale，并清空 candidate state 的 revision/version 字段。旧
generation 和旧 snapshot 行仍在，但没有稳定的 serving pointer 和 freshness 模型可以继续读取。

失效应只创建“新的 target revision 待构建”，不能改写上一份成功发布物的身份与完整性证明。

### 2.4 后台任务去重存在 lost update

曲目署名任务按固定 `track_credit/global` 去重。revision 35 到来时 revision 34 仍 pending/running，
新任务未入队；旧 worker 发布前发现 revision 已变化后直接返回，队列仍把旧任务记为 done。最终形成
`current > active`、`pending`、但没有任务的永久卡死。

### 2.5 元数据修改走了全局重建

现有曲目署名 handler 全量加载艺人 Billboard 帧、重建整张 `agg_weekly_artists`，再 bump 搜索
metadata/candidate revision，触发四套 snapshot 与年榜投影维护。增量导入已经具备 snapshot clone、
有符号 lifetime delta、受影响周替换和紧凑周账本重建能力，但 track-credit revision 被当作 policy
不兼容，无法复用这条增量基础设施。

### 2.6 前端把统计维护错误展示成搜索不可用

候选响应为 unavailable 且 total=0 时，结果组件用全屏状态替代搜索结果；“重新检查”只 refetch，不
会修复后台任务；曲目署名设置页又只在 `failed` 时显示重试，卡在 `pending` 时没有恢复入口。

## 3. 目标与非目标

### 3.1 必须达到的目标

1. 有上一成功索引时，候选搜索在 target `pending/building/failed` 期间始终可用。
2. 新 generation 只在完整校验后原子切换；失败不污染 active，也不清除 previous。
3. 候选和统计分别报告 freshness；统计未就绪不阻塞候选。
4. GET 继续保持只读，不排队、不写库、不加载 lifetime 播放帧、不计算 Billboard。
5. 连续多次元数据修改最终收敛到最新 revision，不得出现无任务的永久 pending。
6. 角色变化不重建统计；署名成员变化的计算范围与受影响 canonical track、艺人和周数成比例。
7. 增量证明失败时允许全量回退，但全量回退期间继续服务 LKG。
8. private 与 public-readonly 都不得因为后台 warming 暴露写操作或未审核本地实体。

### 3.2 非目标

- 不引入 Elasticsearch、Meilisearch、Redis 或外部搜索服务。
- 不自动把旧 legacy 搜索作为前端兜底。
- 不在候选 GET 中补算精确播放资格。
- 不把 stale 统计伪装成 current，也不把缺失统计显示为 0。
- 不借本轮修改播放次数、时长切片、Billboard 排名或 canonical identity 业务规则。
- 不删除原始 `plays`、`tracks`、`track_artists` 或人工治理审计事件。

## 4. 目标架构

```text
数据/元数据 mutation
        │
        ├── 原子记录 target revision / change set / 必要 tombstone
        │
        └── 确保维护任务存在

用户查询                                      后台维护
   │                                             │
   ▼                                             ▼
读取 serving candidate pointer          构建 shadow candidate generation
   │                                             │
   ├── exact context ready ────────┐             ├── 校验文档/FTS/ngram/digest
   ├── LKG context 可用 ───────────┤             └── 原子切换 candidate pointer
   └── context unavailable ────────┤
                                   ▼
                        候选始终可点击，统计渐进补齐
                                                   │
                                                   ▼
                                     clone LKG snapshots + bounded delta
                                                   │
                                                   ├── 默认变体先发布
                                                   ├── 其余变体分别发布
                                                   └── 年榜投影低优先级跟进
```

### 4.1 三个独立状态面

| 状态面 | 权威事实 | 构建期间行为 |
|---|---|---|
| Candidate serving | 当前 active generation、active index version、内容 digest | 始终可读 |
| Candidate maintenance | target source/index version、pending/building/failed、job/error | 不改变 serving |
| Statistics variant | 每个变体的 active snapshot、target fingerprint、freshness | 旧 snapshot 可作为 LKG |

### 4.2 Candidate 发布规则

1. builder 开始只更新 maintenance state，不修改 serving state。
2. 所有新文档、FTS 与 n-gram 写入新的 generation。
3. 校验通过后，在一个 `BEGIN IMMEDIATE` 事务内更新 active/previous pointer 与 active proof。
4. 切换事务不得包含 lifetime 计算或大批 DataFrame 工作。
5. 查询在切换前读到旧 pointer，切换后读到新 pointer；不得观察半成品 generation。
6. previous 至少保留一个受控回滚窗口；清理只能删除非 active、非 previous、非 building generation。

### 4.3 Statistics 发布规则

每个 L2/L3 × dynamic/fixed 变体维护独立 active pointer：

- snapshot 行一旦成功发布就是不可变事实，不再因 target 变化改写其 builder、revision 或 digest；
- target fingerprint 与 active fingerprint 不同时，freshness 为 `last_known_good`；
- 新 snapshot 验证通过后只切换对应变体 pointer；
- 默认 L2/dynamic 优先发布，不等待其他三个变体；
- Year-End projection 不再决定核心 candidate/search job 是否成功，改为低优先级后续任务；
- 新 candidate generation 与旧 snapshot 通过稳定 `entity_key` 关联，缺少的单个 context item 返回缺失，
  不让整个候选响应失败。

### 4.4 删除与权限撤销的即时边界

普通名称、署名新增和角色调整可以安全使用 LKG。真正删除实体、撤销展示资格或产生安全/隐私影响时，
不能等待索引重建，应在 mutation 事务中写入小型 tombstone/deny overlay。候选 SQL 在 active generation
上额外排除这些 entity keys；新 generation 发布并确认不含目标后再清理 tombstone。

## 5. 持久状态与迁移设计

迁移编号以实施时的最新 schema 为准；当前最新为 migration 59，以下暂按 60–62 描述。迁移全部先做
additive 变更，不删除旧字段，便于兼容与回滚。

### 5.1 Migration 60：候选维护状态分离

新增 singleton `music_search_candidate_maintenance_state`：

```text
state_id
target_source_revision
target_candidate_index_version
maintenance_status      missing | pending | building | ready | failed
building_generation_id
job_id
started_at
finished_at
last_error
updated_at
```

现有 `music_search_index_state` 继续表达 serving generation：

- `active_generation_id`
- `previous_generation_id`
- serving `status=ready|degraded|missing`
- active `source_revision`
- active `candidate_index_version`
- active `content_digest`
- active `document_count/built_at`

mutation 不再把 active proof 设为 null。兼容期旧 `status=building/failed` 读取时，如果 active generation
通过最小完整性检查，应迁回 serving `ready/degraded`，同时把错误写入 maintenance state。

### 5.2 Migration 61：统计变体 serving pointer

新增 `music_search_snapshot_variant_state`：

```text
merge_level
dynamic_threshold
active_snapshot_key
active_filter_fingerprint
target_filter_fingerprint
maintenance_status      ready | pending | building | failed
job_id
last_error
updated_at
PRIMARY KEY (merge_level, dynamic_threshold)
```

backfill 规则：

1. 优先选择当前 builder 下最新的 exact-ready snapshot；
2. 当前 exact 不存在时，可选择通过 payload/orphan 校验的最新成功 snapshot 作为 LKG；
3. 无可验证 snapshot 时保持 active null，由候选层独立服务；
4. 不自动把历史失败或 builder 不兼容的 snapshot 升格为 LKG。

### 5.3 Migration 62：元数据 change set

新增 `track_credit_change_sets`，在署名 mutation 同一事务中记录：

```text
change_set_id
from_revision
to_revision
track_id
canonical_track_ids_json
before_credits_json
after_credits_json
before_roles_json
after_roles_json
affected_artist_ids_json
candidate_changed
statistics_membership_changed
created_at
consumed_at
```

before/after 必须保存 canonical 后的有效署名集合，不能只保存一条 override 行。连续 revision 的 change
set 可以合并，但必须验证 revision 连续、目标事实未漂移和 builder/policy 兼容。

## 6. API 合同

### 6.1 Candidate response

保持 `music_search_v2` 兼容字段，新增以下字段；待所有消费者迁移后再决定是否升为 v3：

```json
{
  "candidate_status": "ready",
  "candidate_freshness": "last_known_good",
  "candidate_index_version": "...",
  "statistics_status": "warming",
  "statistics_freshness": "last_known_good",
  "served_filter_fingerprint": "...",
  "target_filter_fingerprint": "..."
}
```

字段语义：

| 字段 | 允许值 | 含义 |
|---|---|---|
| `candidate_status` | ready/degraded/unavailable | 当前是否有候选可服务 |
| `candidate_freshness` | current/last_known_good/fallback | 候选相对 target revision 的新鲜度 |
| `statistics_status` | ready/warming/stale/failed/unavailable | 精确 context 维护状态 |
| `statistics_freshness` | current/last_known_good/unavailable | 返回的统计是否为当前口径 |

兼容 `snapshot_status` 暂时映射到 `statistics_status`，但前端不得再用它决定是否显示候选。
`target_filter_fingerprint` 和内部 maintenance 细节只在 private capability 下返回；公开只读响应不暴露
任务 ID、错误堆栈或内部 revision 结构。

### 6.2 Candidate 选择算法

按以下顺序执行，全程只读：

1. 有 serving candidate generation：始终查询它。
2. 当前 exact snapshot ready：用 snapshot membership join，`candidate_freshness=current`。
3. 当前 exact 未 ready，但有验证过的 LKG snapshot：可用 LKG membership，标记
   `last_known_good`。
4. 没有可用 snapshot：不做 context join，查询 active local-catalog documents，标记
   `candidate_freshness=last_known_good` 或 `fallback`。
5. 第一次启动连 active generation 都不存在：private 使用有界 resolver；public 只能使用明确限制为
   当前播放可达实体的只读 resolver，否则返回 candidate unavailable。
6. 任一层都禁止调用 legacy lifetime/Billboard 搜索。

### 6.3 Context response

context endpoint 优先返回当前 exact snapshot。未 ready 时有两种受产品设置控制的行为：

- 推荐默认：返回 LKG items，并明确 `statistics_freshness=last_known_good`；UI 显示“统计更新中”；
- 严格模式：items 为空但候选不受影响；UI 只隐藏播放/榜单摘要。

无论哪种模式，都不能把缺失值序列化为 0。candidate response 返回实际使用的 context fingerprint，
前端必须用它作为 context query key，避免切换前后的候选和统计串线。

### 6.4 Maintenance status 与恢复

private 设置页新增统一只读状态：

```text
serving_revision
target_revision
candidate_maintenance_status
statistics_variant_statuses
queued_or_running_job
lkg_age
last_error
retry_allowed
```

重试接口必须是幂等的“确保 target revision 有任务”，不是无条件再创建一次全量维护。pending 超过租约
且没有 queued/running job 时应自动恢复；UI 在 pending、failed 两种状态下都提供恢复入口。

## 7. 后台任务一致性修复

### 7.1 不再使用固定 global key 吞掉新 revision

第一版采用简单可靠的 revision-specific job identity：

```text
track_credit / global:revision:<n>
artist_identity / global:revision:<n>
```

这样 revision 35 不会被 revision 34 去重。旧任务执行时：

- `active_revision >= job_revision`：幂等完成；
- `current_revision > job_revision`：不得发布旧结果，确认最新 revision 的任务已持久化后标记 superseded；
- `current_revision == job_revision`：正常构建和原子发布。

后续可以在不改变正确性的前提下，把多个 queued revisions 合并到最新 change set。不得先做内存防抖
再补持久化，否则进程退出会重新出现 lost update。

### 7.2 发布完成条件

只有同时满足以下条件才能把领域状态设为 ready：

- `active_aggregate_revision == current_revision`；
- 相应 change sets 已消费或明确 no-op；
- candidate target 至少已入队，candidate serving 仍可用；
- 核心事务已提交且重读验证通过。

搜索 snapshot 和 Year-End projection 可以继续 warming，不应反向把曲目署名实时事实标成失败。

### 7.3 启动恢复

启动时检查每个维护领域：

1. `current > active` 且无有效任务：为 current revision 补排；
2. maintenance 显示 building 但没有 lease/running job：恢复为 pending 后补排；
3. candidate active 存在但旧共享 status 为 building/failed：修复 serving/maintenance 状态分离；
4. snapshot target 未完成：只排缺失变体，不重复计算 ready 变体；
5. 恢复动作必须记录原因和 revision，不修改查询事实。

## 8. 候选索引维护成本

### 8.1 第一版：保留全量 shadow candidate build

当前候选索引完整构建的历史真实副本证据约为 4.62 秒，远小于统计全量重建。完成 LKG 零停机后，
第一版可以继续完整生成约两万条 candidate documents；它在 shadow generation 中运行，不影响用户。
这样可以先解决可用性和一致性，避免同时重写 FTS/ngram 增量发布。

### 8.2 第二版：受影响文档增量 generation

稳定后再实现 copy-on-write candidate delta：

1. 从 active generation 克隆未受影响文档、ngram 和 FTS 行；
2. 重建受影响 canonical track 在 L2/L3 下的文档；
3. 必要时重建新增/移除 canonical artist 文档；
4. 重新计算内容 digest、文档数和 orphan 证明；
5. 原子切换 generation。

不能原地改 active generation；否则并发查询可能看到文档、FTS 和 n-gram 不一致。即使 delta 失败，也
只丢弃 building generation，不影响 active。

## 9. 曲目署名增量统计

### 9.1 变更分类

| 变更类型 | Candidate | `agg_weekly_artists` | 四套 snapshot | Year-End |
|---|---|---|---|---|
| 只调整 primary/featured，canonical 成员集合不变 | 更新相关歌曲副标题/主艺人 | 不变 | 不变 | 不变 |
| 添加/移除 canonical 署名成员 | 更新歌曲和必要艺人文档 | 受影响艺人/周 delta | artist lifetime + 受影响周 delta | 受影响年份 |
| 重复 raw 艺人但 canonical 成员不变 | 视展示变化决定 | 不变 | 不变 | 不变 |
| 艺人身份归并 | 相关歌曲/艺人文档 | 受影响 canonical 闭包 | 受影响艺人/周；超限回退 full | 受影响年份 |
| 统计规则/builder/entity key 变化 | 按规则重建 | full | full | full |

### 9.2 Canonical 影响闭包

署名覆盖输入虽是一个物理 `track_id`，统计维护不得只过滤该 ID。必须先解析：

- 当前 canonical track / L1 代表来源；
- L2/L3 活动歌曲组映射；
- 该 canonical track 的全部有效来源成员；
- before/after canonical artist membership；
- 连续同曲合并所需的前后边界闭包；
- 实际包含有效逻辑事件的 Billboard 周和年份。

这一步应复用现有 track identity/group resolver、`load_track_group_keys()` 和逻辑时间线规则，不能新增
一套按 raw track_id 计数的捷径。

### 9.3 更新 `agg_weekly_artists`

对两个阈值口径分别构造 changed-track 的逻辑事件；`agg_weekly_artists` 当前只对应默认聚合口径时，
只更新该口径：

1. 对 before credits fan-out 得到负贡献；
2. 对 after credits fan-out 得到正贡献；
3. 按 `billboard_week + canonical_artist_id` 合并 signed delta；
4. 在 `BEGIN IMMEDIATE` 中 upsert/delete 受影响行；
5. 校验非负、总贡献守恒、目标 revision 未变化；
6. 更新 aggregate revision/param hash 后提交。

不得再 `DELETE FROM agg_weekly_artists` 后整表替换。增量验证失败时保留旧 aggregate，并进入 full
fallback；candidate serving 不受影响。

### 9.4 更新四套搜索 snapshot

为 track-credit change set 新增专用 delta builder，复用现有 snapshot clone 和 weekly ledger 基础设施：

1. 选择每个变体的验证过 active/LKG base snapshot；
2. 允许且只允许预期的 track-credit、metadata、candidate-content 依赖变化；其他依赖漂移立即拒绝；
3. track/album lifetime metrics 原样复制；
4. 对 before/after credits 计算 artist lifetime signed delta；
5. 受影响 completed weeks 可以不连续，按周或相邻周簇有界加载，不套用“只允许连续尾部周”的导入
   假设；
6. 每个受影响周只重建 artist family 的完整 Top-N，track/album ledger 保持 base；
7. 用合并后的紧凑周账本重新生成 peak、weeks、power score/rank；
8. 校验 candidate keys、非负 metrics、稳定排序、payload proof 和 revision fence；
9. 每个变体原子发布，默认 L2/dynamic 优先。

周账本只保存 Top-N，因此重建受影响周时必须读取该周全部合格艺人贡献，不能只对旧 Top-N 加减；否则
无法正确处理新艺人进入榜单、榜尾实体被挤出和并列排名变化。读取范围是受影响周，不是 lifetime。

### 9.5 Year-End projection

核心 snapshot 发布后立即允许 context 使用。Year-End 使用新周账本只重建受影响年份/变体，并作为
独立低优先级任务运行。其失败显示在维护状态中，但不能把 candidate 或已经 ready 的核心 snapshot
降级成不可用。

### 9.6 全量回退条件

出现以下任一情况才允许 full fallback：

- 没有通过 payload/orphan/builder 校验的 base snapshot；
- identity、track group、album project、settings 或播放事实发生非预期漂移；
- change set revision 不连续或 before/after 证明缺失；
- canonical 影响闭包超过配置的行数/周数/实体数上限；
- 受影响周重建无法证明 Top-N 完整性；
- entity key 或 builder/policy version 改变；
- delta 等价性断言失败。

full fallback 必须在状态和报告中记录具体原因，不能静默退化；执行期间继续服务 active/LKG。

## 10. 前端体验

### 10.1 搜索结果不再被 maintenance notice 替换

`MusicSearchResults` 只在 `candidate_status=unavailable` 且没有任何候选时显示阻塞空态。其他情况：

- `candidate_freshness=last_known_good`：结果顶部显示非阻塞提示“搜索索引正在更新，当前使用上一可用
  版本”；
- candidate current、statistics warming：显示“搜索可用，播放统计正在更新”；
- statistics LKG：旧统计可显示，但增加“上一版本”标记，不与 current 混淆；
- statistics failed：候选照常可点，提供“查看数据维护”，不清空结果；
- 新 generation 切换后由 query invalidation/refetch 无缝更新，保持输入、键盘焦点、active row、页码和
  滚动位置。

### 10.2 Query 行为

- candidate query key 继续包含搜索语义，不把 target maintenance revision 当作必须清空 placeholder 的
键；
- response 返回的实际 served version/fingerprint 进入 context query key；
- polling 只观察 maintenance 状态，2/4/8/10 秒退避，页面隐藏时停止；
- 切换后只 refetch，不恢复同步 legacy 路径；
- Quick Open 与完整页共享同一状态模型；Phone/Compact/Desktop 不维护三套逻辑。

### 10.3 设置页恢复入口

曲目署名与统一数据维护区域同时展示：

- 当前服务版本；
- 目标 revision；
- candidate/statistics 分别是 ready、warming、failed 还是 LKG；
- pending 无有效任务、failed 或 lease 超时时的“恢复维护”按钮；
- 不把“后台统计仍 warming”描述为“实时署名未生效”。

## 11. Public-readonly 与安全

1. public GET 始终只读，不创建任务、不更新 last-accessed、不补封面、不调用外部 API。
2. public 可使用此前已经通过 public-safe 校验的 active/LKG candidate generation。
3. public fallback resolver 必须限制为当前播放可达、允许公开的实体；不能直接开放现有 private
   `any_local`。
4. tombstone/deny overlay 对 private/public 同时生效。
5. API 不返回原始 query 日志、后台堆栈、数据库路径、任务 payload 或内部实体治理证据。
6. LKG 只表示上一成功产品事实，不等于绕过认证或展示范围。

## 12. 可观测性与维护报告

每次维护至少记录：

```text
domain
from_revision / target_revision / published_revision
strategy = noop | role_only | candidate_full | candidate_delta |
           credit_delta | shared_full | full_fallback
fallback_reason
affected_track_count / artist_count / week_count / year_count
candidate_build_ms / aggregate_ms / snapshot_ms / year_end_ms
rows_scanned / rows_written
served_candidate_freshness_during_build
peak_rss（离线/脚本验收）
```

维护状态必须能回答三个不同问题：

1. 用户现在能不能搜索；
2. 当前结果是 current 还是 LKG；
3. 后台为什么还没追上 target revision。

日志继续隐藏原始搜索词和实体内容。性能报告使用固定非敏感 query 集合。

## 13. 分阶段实施计划

### Phase 0：当前故障恢复与竞态回归

目标：先保证 revision 不丢失，但不宣称已解决重建成本。

- revision-specific job identity；
- superseded 任务确认 latest job 后退出；
- pending/failed 启动恢复；
- 设置页 pending 也可重试；
- 用数据库副本复现 revision 34/35 快速连续修改；
- 修复上线后再明确触发当前 revision 35，避免在旧代码上重复全量重建。

退出条件：`current_revision == active_aggregate_revision`，状态 ready，latest candidate maintenance 已入队
或 ready；连续修改测试不再永久 pending。

### Phase 1：Candidate LKG 零停机

- migration 60；
- serving/maintenance state 分离；
- mutation 不清空 active proof；
- candidate service 删除“snapshot 不 ready 就空响应”的门禁；
- active generation、LKG membership、local-catalog 和 bounded resolver 分级；
- candidate API/前端非阻塞状态；
- builder 失败保留 active；
- shadow generation 原子切换与 previous 回滚测试。

退出条件：有 active generation 时，candidate build pending/running/failed 三种状态下均返回可点击结果；
GET 不访问 plays/Billboard 计算路径。

### Phase 2：Statistics LKG 与逐变体切换

- migration 61；
- snapshot immutable + active/target pointer；
- context current/LKG 明确区分；
- 默认变体先发布；
- Year-End 从核心搜索 job 解耦；
- candidate/context 实际 served fingerprint 配对；
- LKG 过旧策略和严格隐藏统计模式。

退出条件：四变体任一 warming/failed 不阻塞 candidate；已 ready 变体不被其他变体失败回滚。

### Phase 3：Track-credit change set 与角色 no-op

- migration 62；
- mutation 原子记录完整 before/after canonical membership；
- role-only 不触发 aggregate/snapshot/year-end；
- candidate 相关文档更新；
- 审计事件与 change set 对账。

退出条件：primary/featured 调整不扫描 lifetime plays、不创建 snapshot rebuild job，候选展示更新正确。

### Phase 4：署名成员增量统计

- canonical 影响闭包；
- `agg_weekly_artists` signed delta；
- 四变体 artist lifetime delta；
- 任意受影响周的 artist Top-N 重建；
- compact ledger power/peak 重算；
- 受影响年份 Year-End；
- full fallback 和 fallback reason。

退出条件：代表性 add/remove/undo 在四变体下与隔离数据库完整重建逐行等价，且正常样本不进入 lifetime
scan。

### Phase 5：Candidate delta（可选优化）

在 Phase 1 全量 shadow candidate build 已满足体验预算后再评估。只有真实测量证明 4–10 秒维护仍影响
编辑体验时，才实现 copy-on-write 文档 delta；不得延误前四阶段的正确性和可用性修复。

### Phase 6：真实库、浏览器与生产收口

- Online Backup 副本完整迁移和回滚演练；
- 当前真实样本 revision 34/35 故障重放；
- candidate/context warm/cold probe；
- 390px、Compact、Desktop Quick Open 与完整页浏览器验收；
- private/public-readonly 合同；
- 默认完整全栈门禁；
- 更新 reference、方向计划、CHANGELOG、交付报告和 OpenAPI 生成类型。

只有 Phase 0–6 必需门禁通过后，本文状态才能改为“已实施并验证”。

## 14. 测试与验证矩阵

### 14.1 后端 unit

重点新增/修改：

- `test_job_queue.py`：revision-specific 去重、superseded/latest 收敛；
- `test_track_credit_rebuild.py`：两次快速 mutation、role-only、delta/fallback；
- `test_music_search_candidate_service.py`：snapshot unavailable 仍返回 active candidates；
- `test_music_search_snapshot.py`：LKG pointer、逐变体切换、immutable snapshot；
- 新增 `test_music_search_track_credit_delta.py`：四变体 lifetime/周账本等价；
- `test_music_search_year_end_projection.py`：projection 失败不降级 candidate/core snapshot；
- `test_music_search_startup.py`：无任务 pending 恢复、active serving 保留。

### 14.2 后端 contract

至少覆盖：

| 场景 | Candidate | Context | 写副作用 |
|---|---|---|---|
| current 全 ready | current | current | 0 |
| candidate building | LKG | current 或 LKG | 0 |
| candidate build failed | LKG | current 或 LKG | 0 |
| snapshot building | current/LKG | LKG 或 unavailable | 0 |
| snapshot failed | current/LKG | LKG 或 unavailable | 0 |
| 首次无索引（private） | bounded fallback | unavailable | 0 |
| 首次无索引（public） | public-safe fallback 或 unavailable | unavailable | 0 |
| tombstone 存在 | 不返回目标实体 | 不返回目标实体 | 0 |

请求前后逐表比较 candidate、snapshot、background job、revision 和 tombstone 状态，证明 public/private
GET 均为零写入。

### 14.3 Delta 等价性

每个 mutation fixture 建立两份相同数据库：

1. A 执行 track-credit delta；
2. B 执行现有 full rebuild；
3. 逐行比较：
   - `agg_weekly_artists`；
   - 四套 `music_search_entity_context`；
   - 四套 `music_search_weekly_chart_context`；
   - 受影响 Year-End projection；
   - candidate documents/ngram/FTS 的业务字段；
4. 比较 context payload proof、非负约束、orphan 和稳定排序；
5. 输入顺序打乱、重复 canonical identity、undo、非连续历史周和 Top-N 边界都必须覆盖。

### 14.4 前端

- `music-search-components.test.tsx`：warming/failed notice 不替代结果；
- `music-search-hooks.test.tsx`：served fingerprint query key、切换 refetch、退避；
- `music-search-flow.test.tsx`：Quick Open/完整页在 LKG → current 切换时保持状态；
- 设置组件：pending 无 job、failed、ready/warming 分层；
- public capability：无 private retry、target revision 或治理链接泄漏。

### 14.5 命令门禁

实施阶段按风险逐层运行，最终至少包括：

```bash
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
cd frontend && npm test
cd frontend && npm run build
python3 scripts/docs_audit.py
sh scripts/phase5_check.sh
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://127.0.0.1:5173
```

局部通过只能标记 Partial；只有默认完整全栈模式全部必需阶段通过才是本地全栈 Pass。

## 15. 性能与容量预算

以下是实施验收目标，不是尚未测量的完成事实：

| 指标 | 预算 |
|---|---:|
| current candidate warm P95 | ≤80ms |
| LKG candidate warm P95 | ≤80ms；不得比 current 增加无界扫描 |
| bounded fallback P95 | ≤250ms，候选池有硬上限 |
| context current/LKG P95 | ≤20ms |
| 单响应 | ≤8KiB |
| GET lifetime/Billboard 计算 | 0 次 |
| candidate 切换写锁 | 目标 ≤200ms，必须实测 |
| role-only snapshot rebuild | 0 个任务 |
| 正常署名 delta lifetime scan | 0；只允许影响闭包/受影响周 |
| 普通署名 delta | 目标 ≤30 秒、峰值 RSS ≤256MiB；以真实副本测量为准 |
| full fallback | 可长时间运行，但 candidate downtime 必须为 0 |

容量门禁必须覆盖 active、previous 和 building generation/snapshot 同时存在的峰值；不得只测切换后的净
大小。清理策略至少保留 active + previous，building 失败产物在诊断保留期后受控删除。

## 16. 发布、回滚与特性开关

### 16.1 发布顺序

1. additive migrations 与旧代码兼容性检查；
2. 部署后端状态模型，但继续使用旧消费逻辑；
3. backfill serving/maintenance pointers 并只读验证；
4. 打开 candidate LKG serving；
5. 部署前端非阻塞体验；
6. 打开 statistics LKG；
7. 打开 role-only/no-op 与 track-credit delta；
8. 保留 full fallback，观察真实维护报告；
9. 稳定后再清理兼容字段或评估 candidate delta。

特性开关统一从 `backend/core/config.py` 读取，至少包含 candidate LKG、statistics LKG、credit delta 三个
独立开关；不得在业务 service 直接读取环境变量。

### 16.2 回滚

- candidate：原子把 active pointer 切回 previous generation；
- statistics：逐变体把 active snapshot pointer 切回上一验证版本；
- delta：关闭开关后回到 full maintenance，但继续 LKG serving；
- API：新增字段保持 optional，旧前端仍可消费兼容字段；
- migration：additive 表和列不需要在紧急代码回滚时删除；
- 任一回滚后重验 source revision、builder version、document/context orphan、公开只读和深链。

不得用删除 active/previous generation、清空 snapshot 表或回写原始事实作为回滚方式。

## 17. 完成定义

本方案只有同时满足以下条件才能关闭：

1. 重建期间、失败期间和连续 mutation 期间，候选搜索均可用；
2. active → new generation 切换无空窗、无半成品、可回滚；
3. `snapshot_status` 不再控制候选是否显示；
4. role-only 修改零统计重建；
5. 署名 add/remove/undo 增量结果与 full rebuild 四变体逐行等价；
6. latest revision 不再丢失，pending 必有任务或可自动恢复；
7. Year-End 失败不阻塞 candidate/core context；
8. public/private GET 零写入、零 lifetime/Billboard 计算；
9. 真实数据库副本达到性能、内存、容量和 orphan 门禁；
10. 桌面、Compact、390px 与 public capability 浏览器验收通过；
11. reference、OpenAPI、CHANGELOG、交付报告和文档地图同步；
12. 默认完整全栈门禁 Pass，并明确记录未执行的生产外部条件。

在这些证据完成前，任何 Phase 的局部测试都只能标记 Partial，不能描述为搜索零停机或元数据增量
维护已经交付。
