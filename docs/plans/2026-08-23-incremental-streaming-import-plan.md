# Spotify 串流数据增量导入开发规划

> 状态：实施中；Phase A–C 已实现，Phase D–E 待实施
>
> 创建日期：2026-08-23
>
> 规划基线：`21f68ccc`
>
> 适用范围：Spotify Extended Streaming History 串流导入、导入后派生维护与相关缓存；账号数据导入暂不改动

## 1. 目标与结论

本计划不把“增量更新”实现成一个全局布尔开关，而是分成两个连续步骤：

1. 先用持久化记录指纹证明本次输入与当前活动数据集的关系，生成精确 `ChangeSet`。
2. 再由导入执行计划为基础播放、Billboard、搜索、年度总结、元数据、Album Project、封面和缓存分别选择 `noop`、增量、分区重建或全量回退。

首个可交付版本采用“安全半增量”：完全相同的数据直接跳过，能够证明的尾部追加只插入新增播放，其余情况继续使用现有快照、覆盖式导入和全量维护。之后再逐步把 Billboard 周分区和六套搜索统计快照改为增量更新。

目标不是消灭所有全量计算，而是优先消除无法带来新事实的重复计算，同时保持以下边界：

- 增量结果必须能与同输入的干净全量重建逐表对账。
- 无法证明输入关系时，不自动删除历史记录。
- 规则、身份、署名或 Album Project 语义变化时，对应领域允许主动回退全量。
- 导入请求和普通 GET 都不得触发未受控的六套搜索冷构建。
- 最新播放所在的开放榜单周继续不发布为正式周榜。

## 2. 当前基线

当前实现已经具备：

- `record_fingerprint()` 对完整原始记录做规范化 JSON SHA-256，同一导入内对音频和视频分别精确去重。
- 导入前只读检查、导入前 SQLite Online Backup、失败回滚和导入后硬健康检查。
- Spotify 元数据、Album Project、Billboard 预聚合、封面任务、搜索候选与六套统计快照的两阶段维护。
- Billboard 聚合影子表原子发布、搜索快照 generation、分领域 revision、后台任务和 warming 状态。
- 最新覆盖边缘周排除、首页与最新完整榜单优先预热。

当前限制是：

- `backend/core/import_data.py` 在导入开始时删除 `plays`、四张 Billboard 聚合表和 `agg_config`。
- 记录指纹只存在于一次导入进程的 `seen_audio_records` / `seen_video_records`，不能跨导入比较。
- 维表解析、播放事实写入、Album Project、周聚合和搜索快照仍以“整个数据集已经变化”为默认前提。
- 当前四张周聚合全量构建在真实规模下约 3.3 秒，首要成本仍是六套搜索统计与多个消费者重复加载、合并同一播放历史。

因此实施顺序应先解决“能否证明变化”，再解决“变化影响哪些派生事实”，最后才优化局部连续播放链。

## 3. 非目标

首轮不做以下扩展：

- 不按日期、歌名、相似度或猜测的事件身份做模糊去重。
- 不把网易云、Apple Music 等其他来源直接混入 Spotify `plays` 事实表。
- 不新增复杂的导入历史管理页面；Settings 只展示最近一次检测和执行结果。
- 不为了追求纯增量而维护难以审计的逐指标加减账本；优先替换受影响分区。
- 不改变播放次数、连续播放合并、时长切片、Album Project 或 Billboard 的现行统计语义。
- 不在第一阶段局部重建连续播放链；在获得等价性证据前，允许一次性重建规范逻辑帧。

## 4. 核心术语

| 名称 | 含义 |
|---|---|
| 活动数据集 | 当前 `plays` 及其持久化指纹所代表的已发布串流事实 |
| 输入包 | 本次读取到的音频、视频 Streaming History 文件集合 |
| 完整快照 | 声明或能够证明代表目标完整历史的数据包 |
| 增量包 | 只提供需要追加的尾部记录，不声明旧记录删除的数据包 |
| 导入代际 | 一次成功发布后的稳定 `generation_id` |
| `ChangeSet` | 新增、删除、保持不变的记录及其实体、时间和榜单周影响范围 |
| 语义 revision | 播放规则、设置、艺人身份、曲目署名、Album Project 或 builder 版本 |
| 分区重建 | 保留未受影响结果，只重新生成受影响周、年份或实体集合 |

## 5. 总体流程

```text
只读预检
  → 将输入记录规范化写入临时 staging
  → 比较活动数据集指纹
  → 识别账号与数据覆盖模式
  → 生成 ImportPlan / ChangeSet
  → 无变化直接结束，歧义等待确认
  → 创建现有 SQLite 快照
  → 发布基础播放事实
  → 按领域执行派生计划
  → 健康检查与等价性检查
  → 原子切换活动代际并启动低优先级后台任务
```

“输入关系判定”和“派生执行策略”必须分开。例如，基础数据可能是可靠追加，但 Album Project 因规则 revision 变化仍需要全量重建；封面可以只处理新增实体；搜索候选索引因为本身很轻，可以继续整体重建。

## 6. 数据模型

### 6.1 Migration 37：导入身份基线

为 `plays` 增加：

- `source_fingerprint TEXT NULL`：沿用当前完整记录 SHA-256 十六进制值。
- `source_fingerprint_version INTEGER NULL`：首版固定为 `1`。
- `import_generation_id TEXT NULL`：创建该播放事实的活动代际。

索引：

```sql
CREATE UNIQUE INDEX uq_plays_source_fingerprint
ON plays(content_type, source_fingerprint_version, source_fingerprint)
WHERE source_fingerprint IS NOT NULL;

CREATE INDEX idx_plays_import_generation
ON plays(import_generation_id);
```

音频和视频继续分开判重，保持现有语义。旧行不根据当前数据库列反推原始 JSON 指纹，因为数据库没有保存所有原始字段；升级后的第一次串流导入必须走一次完整基线导入并填充指纹。

新增 `playback_import_state` 单例表：

```text
state_id=1
active_generation_id
account_identity_hash
fingerprint_version
dataset_digest
record_count / first_ts / latest_ts
last_relation / last_strategy
updated_at
```

新增 `playback_import_runs`：

```text
run_id, requested_mode, detected_relation, status,
incoming_digest, previous_digest,
incoming_count, unchanged_count, added_count, removed_count,
first_ts, latest_ts, earliest_changed_ts, latest_changed_ts,
plan_json, started_at, completed_at, error_code
```

主库只保证成功、noop 和等待确认的运行记录；进程中失败和回滚细节继续进入现有导入 job 结果。不得在表中保存完整原始播放 JSON。

### 6.2 临时 staging

使用同一 SQLite 连接的 TEMP 表或独立临时 SQLite 文件保存：

- `source_type`
- `source_fingerprint`
- 原始时间与标准化时间列
- 导入器消费的曲目、专辑、艺人、URI 和播放属性
- 文件序号和记录序号，仅用于稳定错误定位

staging 在活动数据发布前可丢弃，不写入 Git，不作为长期数据资产。解析仍按批次进行，避免同时保留全部 Python dict。

### 6.3 数据集摘要

`dataset_digest` 使用排序后的 `(source_type, source_fingerprint)` 计算，与文件名称、文件顺序和 Spotify 重新拆分 JSON 文件无关。

读取时允许先使用文件 SHA-256 做快速命中；文件集合变化时必须回退记录级比较。指纹算法升级必须提升 `fingerprint_version`，并触发一次新的完整基线，不能混用不同版本集合。

## 7. 输入关系判定

### 7.1 账号身份

如果 Account Data 中存在稳定 Spotify 账号标识，预检生成不可逆 `account_identity_hash`。原始账号标识不写日志。若本次没有 Identity 文件，则沿用“未知”而不是猜测。

仅靠记录集合无法完全区分“同账号、只含新记录的增量包”和“另一个账号、时间更晚的数据包”。因此账号未知且记录无重合时必须进入 `ambiguous`，不能静默追加或替换。

### 7.2 关系类型

设活动指纹集合为 `E`，输入集合为 `I`：

| 关系 | 证明条件 | 默认动作 |
|---|---|---|
| `baseline_required` | 活动库还没有持久化指纹 | 完整导入建立基线 |
| `identical` | `I = E` | `noop`，不提升播放 revision |
| `snapshot_superset` | `E ⊂ I` | 只插入 `I - E` |
| `delta_tail` | 账号一致，输入声明/确认是增量，且记录位于当前覆盖尾部 | 只追加输入中不存在的记录，不推断删除 |
| `reconciled_snapshot` | 已确认完整快照，同时存在新增和删除 | 精确增删；超出成本门限时派生层全量回退 |
| `truncated_or_regressive` | 输入是活动集合子集、覆盖明显倒退或缺少历史文件 | 默认阻断，不自动删除 |
| `different_account` | 账号身份明确不一致 | 默认阻断；用户确认后完整替换或未来新建 Profile |
| `ambiguous` | 无法证明是增量还是替换 | 要求一次明确选择 |

### 7.3 API 显式模式

`POST /api/import/streaming` 增加：

- `mode=auto|append|replace`，默认 `auto`。
- `confirm_plan=false|true`，用于确认 `ambiguous`、`truncated_or_regressive` 或 `different_account`。

`append` 永远不把输入中缺失的旧指纹解释为删除；`replace` 必须保留当前数据库快照并走完整导入。`auto` 只有在证据充分时才选择增量。

## 8. ChangeSet 与影响范围

`ChangeSet` 至少包含：

- `added_fingerprints`、`removed_fingerprints` 及计数。
- 新旧记录的最早/最晚变化时间。
- 直接涉及的 `track_id`、source album、primary/featured artist。
- 受影响的自然日、月份、年份和 Billboard 周。
- 导入前开放周与导入后开放周。
- 语义 revision 快照：播放策略、设置、艺人身份、曲目署名、Album Project、候选/统计 builder。

### 8.1 连续播放边界

同曲连续播放合并依赖全局时间顺序、相邻曲目、推断开始时间和 `max_merge_gap_minutes`。新增或删除一条记录可能改变它前后的逻辑事件，不能只按记录自身日期更新。

实现分两级：

1. 实用版本：每次播放事实变化后只构造两套规范逻辑帧（动态阈值开/关），在三个 merge level 间复用；避免六次重复加载和合并原始历史。
2. 完整版本：对变化记录前后寻找连续链闭包，直到遇到曲目变化、严重时间重叠或超过最大间隔，再局部重建旧、新逻辑事件并比较贡献。

在第二级完成等价性验证前，不使用固定 `±5 分钟` 代替连续链闭包，因为一串相邻片段可能连续延伸更久。

### 8.2 榜单周范围

受影响周由旧、新逻辑事件的计数归属和收听时长切片共同决定，并额外包括：

- 导入前的开放周。
- 导入后的开放周。
- 因覆盖边界跨越而首次变成完整周的上一周。

这样即使新增播放全部位于新开放周，上一周仍会在正确时机发布为最新完整榜单周。

## 9. 领域执行计划

| 领域 | 首个版本 | 完整版本的增量策略 | 强制全量条件 |
|---|---|---|---|
| `plays` | identical 跳过；可靠追加只插入；其他沿用全量 | 精确插入/删除指纹对应行 | 基线、确认替换、指纹版本变化 |
| artists/albums/tracks | 稳定 upsert，不清空 | 只新增或补充相关维表；孤立清理延后 | 唯一键或实体解析规则变化 |
| track groups | 继续执行幂等合并 | 只处理变更 Spotify track ID | 分组语义版本变化 |
| Spotify metadata | 只请求新增/缺失实体 | 接收 `changed_entity_ids`，失败按现有队列重试 | Provider/builder 语义变化不要求全量，只重新评估缺口 |
| 封面 | 继续缺失扫描和幂等排队 | 只扫描新增、URL 变化和失败待重试实体 | 不因播放导入全量清空 |
| Album Project | 首轮继续全量重建 | 按受影响艺人和发行项目重建 | membership/identity/人工治理 revision 变化 |
| Billboard 聚合 | 首轮仍允许全量 3.3 秒构建 | 影子表复制未变周，只替换受影响周 | 设置、播放策略、署名、身份、Album Project revision 变化；受影响周比例过高 |
| 周排名 | 从受影响周重新排名 | 只重排对应周的全部入榜候选 | Top N/排序语义变化 |
| Power/纪录/年榜 | 从紧凑周数据重算 | 只失效受影响年份；跨年总纪录从周聚合重算 | Year-End/Power builder 变化 |
| 搜索候选 | 继续整体重建，当前成本低 | 观察到成本后再考虑 generation clone/upsert | normalization、alias、Album Project 文档规则变化 |
| 六套搜索统计 | 后台完整构建 | 复制旧 snapshot，更新受影响实体；全体 `power_rank` 用 SQL 重排 | 统计 fingerprint 或 merge 语义变化 |
| 首页 | 按新播放 revision 精确失效 | 只重建与近期窗口或 lifetime 摘要相交的片段 | 首页 builder 变化 |
| 年度总结 | 只失效受影响年份 | 历史未受影响年份继续精确命中 sidecar artifact | content/策略/元数据 revision 变化 |

### 9.1 成本门限

关系判定决定“数据是否安全”，成本门限只决定“增量是否值得”。初始门限作为内部常量，不暴露成 Settings：

- 变化记录超过活动播放的 20%，派生层优先全量。
- 受影响榜单周超过全部完整周的 25%，Billboard 优先全量。
- identity、track credit、Album Project 或播放规则 revision 不匹配时，忽略比例并全量重建对应领域。

门限必须通过真实数据库副本 benchmark 调整；不得为了命中增量而牺牲等价性。

## 10. Billboard 分区发布

新增 `build_aggregations_for_weeks()`，复用现有四张影子表和原子发布协议：

1. 创建 TEMP shadow 表。
2. 从活动聚合复制未受影响周。
3. 从变化闭包覆盖的原始播放重新生成受影响周。
4. 对 track、album、track source、artist 四张表做主键唯一性和非负校验。
5. 在一个 `BEGIN IMMEDIATE` 中替换四张活动表并更新 `agg_config`。

`agg_config` 增加逻辑键：

- `data_generation_id`
- `playback_policy_version`
- `identity_revision`
- `track_credit_revision`
- `album_project_revision`
- `build_strategy=full|partition`

若任一依赖与活动聚合不一致，不得复制旧周。

周分区验收不仅比较 Top N，还要比较四张聚合表的全部行、完整周集合、同分稳定排序、Power Score、纪录和 Year-End 输入。

## 11. 搜索快照增量策略

搜索候选与精确统计继续分离。候选 generation 整体重建很轻，不应优先为它增加复杂增量逻辑。

六套精确统计快照的完整方案：

1. 为每个 `merge_level × dynamic_threshold` 创建 pending snapshot。
2. 从上一 ready snapshot 复制未受影响实体上下文。
3. 变化实体包括直接变化的歌曲、所属 Album Project、有效署名艺人，以及受影响周所有参与排名的实体。
4. 重新计算这些实体的 lifetime metrics 和完整 chart summary。
5. `power_score` 更新后，对整张紧凑 context 表用 SQL window function 重排 `power_rank`；不重新加载全部原始播放。
6. 校验实体键唯一、计数非负、ready snapshot 实体集合与候选 generation 兼容后再激活。

如果旧 snapshot、周聚合或 revision 无法被证明兼容，继续走当前后台全量构建。warming 期间仍返回候选和深链，不返回虚假 0。

## 12. revision、缓存和可见状态

- 播放 revision 只在基础事实成功发布后提升一次；identical/noop 不提升。
- Billboard revision 在四张聚合原子发布后提升。
- metadata/candidate revision 只在相应事实确实变化时提升。
- 首页、年度总结和搜索快照 key 使用它们真正依赖的 revision，不使用 SQLite 文件 mtime、WAL 大小或一个全局“任何写入”版本。
- 导入发布后不调用无差别 `invalidate_all()`；按 namespace 和精确 key 失效。
- 基础事实已发布但派生结果尚未就绪时，API 明确返回 `warming`；不能继续把旧派生结果伪装成当前代际。

建议为聚合、搜索 snapshot 和年度 artifact 记录 `source_generation_id`。读取端只有在代际和语义依赖匹配时才视为 ready。

## 13. 事务、失败和回滚

1. 关系检测和 ImportPlan 生成期间不修改主库。
2. 需要写入时继续先创建 SQLite Online Backup。
3. append/reconcile 的基础事实与活动代际更新放在明确事务中；任何唯一性或关系错误都回滚。
4. Billboard 分区在自己的影子发布事务中完成，失败时保留上一完整聚合。
5. 搜索 snapshot 继续 generation publish，单个变体失败不得激活不完整集合。
6. 基础事实发布后派生失败时，健康状态为 `partial/warming`，并保留可重试任务；如果硬健康检查失败，沿用现有数据库快照恢复。
7. 回滚后清理本次 staging、未激活 generation 和进程缓存，不删除上一 ready snapshot。

## 14. API 与 Settings 展示

扩展 `ImportPreflightResponse`：

```text
account_identity_status
fingerprint_baseline_status
detected_relation
requested_mode
requires_confirmation
existing / incoming / unchanged / added / removed counts
existing / incoming date ranges
affected_weeks / affected_years counts
planned_actions[]
estimated_strategy = noop | incremental | mixed | full
```

Settings 导入前检查展示自然语言摘要，例如：

- “与当前数据完全相同，不需要重新导入。”
- “检测到同一账号新增 1,834 条记录，预计更新 2 个榜单周和 2026 年度数据。”
- “输入包缺少当前库中的历史记录，无法判断是增量包还是不完整快照；请选择追加或替换。”

导入进度拆成：比对输入、发布播放事实、更新榜单、刷新查找候选、后台构建精确快照、补封面。基础数据和主要页面可用后，任务可以结束为 `done + warming`，不再长时间停在模糊的“导入中”。

## 15. 测试与验收矩阵

### 15.1 单元测试

- 同记录不同 JSON key 顺序得到同一指纹。
- 文件顺序和文件拆分变化不改变 `dataset_digest`。
- 音频与视频继续按类型隔离判重。
- `identical`、`snapshot_superset`、`delta_tail`、`reconciled_snapshot`、`truncated`、`different_account`、`ambiguous` 分类。
- 账号未知且无记录重合时必须要求确认。
- identical 不 bump revision、不排队搜索/封面任务。
- 开放周跨界时旧开放周进入 affected weeks。
- 规则 revision 变化强制相应领域全量。

### 15.2 合同测试

- preflight 新字段与 OpenAPI 类型。
- `mode=append|replace` 和 `confirm_plan` 门禁。
- blocked/needs_confirmation 不创建数据库快照、不写播放事实。
- done/warming/partial 的任务文案和结果字段。
- public-readonly 继续拒绝导入写操作。

### 15.3 增量—全量等价性测试

为每个场景准备两份临时数据库：A 执行增量，B 使用最终输入完整重建。逐项比较：

- `plays` 的稳定自然事实和指纹集合，不比较自增 `play_id`。
- tracks/albums/artists 与 track credits。
- Album Project membership。
- 四张 Billboard 聚合表。
- 完整周集合、周榜、Power、纪录和 Year-End。
- 六套搜索 snapshot 的每个实体上下文。
- 受影响年份的年度总结确定性事实与 artifact key。

使用双向 SQL `EXCEPT` 和稳定排序哈希；任何差异都阻止增量策略发布。

### 15.4 必测场景

1. 同一文件重复导入。
2. 同一记录集合但文件重命名、排序或重新分片。
3. 完整历史加若干新记录。
4. 同账号仅提供尾部增量包。
5. 历史记录被修正，表现为一删一增。
6. 输入缺少旧历史文件。
7. 不同账号数据。
8. 音频/视频存在相同原始内容。
9. 新增记录跨自然日、月、年和 Billboard 周边界。
10. 新增短片段与旧末尾记录形成连续播放链。
11. Spotify metadata 不可用、封面下载失败和任务重试。
12. 导入进程在基础发布前、聚合发布中和搜索 warming 时中断。
13. 设置、identity、track credit 或 Album Project revision 变化。

### 15.5 真实数据库副本验收

- 先对当前真实库执行一次 baseline 建立。
- identical 再导入应只完成读取和比对，不改变播放数、revision 或 ready snapshot。
- 使用人工构造的新尾部记录副本验证增量路径，再与完整重建副本对账。
- 记录 staging、基础发布、Billboard、六套搜索、首页首响和总任务时间。
- 主库始终只读验证；破坏性演练仅在 `/tmp` 或 Online Backup 副本。

## 16. 分阶段实施与工作量

### Phase A：持久化基线与只读 ImportPlan（已实现，2026-08-23）

- Migration 37、指纹列、活动状态和 import run 表。
- staging reader、dataset digest、账号身份探针。
- 只读分类和 API/UI 计划展示。
- 旧库显示 `baseline_required`，行为仍回退当前全量导入。

验收：不改变现有统计结果；七类关系判定单测通过；预检不写库。

实现说明：Phase A 使用源检查器生成只读内存 staging manifest，完成 dataset digest、账号身份探针、关系分类和 API/UI 展示；migration 37 只建立持久化结构。92,908 条真实库副本的预检与自动化验收已通过，证据见 [`../reports/2026-08-23-incremental-import-phase-a.md`](../reports/2026-08-23-incremental-import-phase-a.md)。

### Phase B：安全 noop 与 append-only（已实现，2026-08-23）

- 完整基线导入写入指纹。
- identical 直接结束。
- `snapshot_superset` 和确认的 `delta_tail` 只插入新增播放和维表。
- ambiguous、truncated、replacement 保留全量/阻断回退。

验收：追加后的基础事实与全量重建一致；崩溃和唯一索引冲突不改变活动代际。

实现说明：完整基线导入写满版本化指纹并发布活动代际；已有播放但无基线时必须先确认完整替换。identical 在快照与派生维护前 noop；snapshot superset 和具备共同记录、账号与时间证据的尾部包自动追加。零重合包不会借用固定 Account Data 自动认作同账号，用户可明确选择 fail-closed 尾部验证。确认标识绑定输入与当前基线，append 在同一事务内精确对账旧基线、实际输入和新增指纹并发布活动代际，异常显式 rollback、关闭连接后再进入快照恢复。Phase B 延续现有批次 JSON reader，没有新增独立 TEMP SQLite staging；派生 pending/active 发布、后台任务代际隔离、历史删除/修订和完整替换的硬中止恢复仍留在后续阶段。92,908 条基线加 1 条尾部记录与 92,909 条完整替换的六张基础事实/关系表逐表哈希一致，证据见 [`../reports/2026-08-23-incremental-import-phase-b.md`](../reports/2026-08-23-incremental-import-phase-b.md)。

### Phase C：ChangeSet 驱动的维护（已实现，2026-08-23）

- 生成实体、日期、年份、开放周变化范围。
- 元数据、封面、年度缓存按范围更新。
- 播放 revision 和 cache key 精确失效。
- Album Project 暂时全量，记录实际耗时决定是否进入定向重建。

验收：首页和完整周榜优先恢复；旧年度 artifact 保持命中；无关缓存不抖动。

实现说明：事实发布事务会从实际写入代际生成并持久化 `PlaybackChangeSet`，记录本地实体、Spotify 实体、日期、年份、开放周和语义 revision；维护完成前运行状态为 `maintenance_pending`，中断后仍保留恢复依据。增量维护只刷新相关元数据和封面，同时带有界历史失败扫尾；封面任务支持重启恢复、全流程失败记录、来源 URL 哈希和过期任务 CAS。年度总结使用逐年直接/前缀 digest 与报告年前缀可达的元数据、流派、曲目组和 Album Project 依赖摘要，普通最新年追加不会使旧年度播放分区抖动。播放事实提交和聚合发布都会精确失效播放相关缓存，聚合构建绑定活动代际并在发布事务再次核对，避免旧计算冒充新代际。Album Project 与 Billboard 仍全量重建，榜单周影响范围暂标记为非精确；这些成本和六套搜索快照属于 Phase D。92,908 条真实数据库副本加 1 条尾部记录的范围与耗时证据见 [`../reports/2026-08-23-incremental-import-phase-c.md`](../reports/2026-08-23-incremental-import-phase-c.md)。

### Phase D：Billboard 周分区与搜索快照增量（3–5 人日）

- `build_aggregations_for_weeks()` 与聚合代际依赖。
- 受影响周分区替换、排名和 Year-End 范围失效。
- 六套 snapshot 复制/更新/全局 power rank 重排。
- 两套逻辑播放帧在三个 merge level 间复用。

验收：所有必测场景的增量—全量聚合和搜索上下文完全一致；增量导入不再重复六次扫描完整播放历史。

### Phase E：历史修正与局部连续链（可选，4–6 人日）

- 完整快照的精确删除/修正。
- 旧、新连续播放链闭包和局部贡献比较。
- 定向 Album Project rebuild 与成本门限自动回退。
- 中断、恢复和长期运行压力测试。

验收：历史修正场景等价；无法建立闭包时安全回退全量。

实用版本完成 Phase A–D，预计 10–14 人日；包括历史修正局部化的完整版本预计 14–20 人日。第一批可独立上线的 Phase A–B 约 4–5 人日。

## 17. 建议提交拆分

1. `feat(import): persist playback dataset identity`
2. `feat(import): add staged relation detection and import plan`
3. `feat(import): support safe noop and append-only publish`
4. `perf(import): scope metadata covers and yearly invalidation`
5. `perf(billboard): rebuild affected weekly partitions`
6. `perf(search): incrementally publish exact context snapshots`
7. `test(import): prove incremental and full rebuild equivalence`
8. `docs(import): document incremental import operation and evidence`

每个阶段都必须保持完整全量路径可用。不得把 schema、基础增量写入、Billboard 分区和搜索 snapshot 四项压进一个不可回退的大提交。

## 18. 完成定义

增量更新只有同时满足以下条件才算完成：

- 能稳定识别 identical、可靠追加、歧义输入和替换输入。
- identical 不产生播放、聚合、搜索或缓存 revision 变化。
- append 的基础事实、完整周榜和六套搜索上下文与全量重建一致。
- 最新开放周不会提前发布，跨周后上一周会自动成为最新完整周。
- 无法证明关系或依赖 revision 不兼容时自动回退，不静默丢数据。
- 导入中断不破坏活动代际，旧 ready 派生结果不会冒充新代际。
- Settings 能解释检测结果、执行策略、复用范围和后台 warming 状态。
- 真实数据库副本有可重复的性能和等价性报告，规则同步进入 `docs/reference/`，完成计划移入 archive。
