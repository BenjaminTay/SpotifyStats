# Billboard Records 一致性与排行稳定性修复规划

> 创建日期：2026-08-29
> 状态：B1–B4、R1 已实施并完成范围验收；默认完整全栈门禁未运行，由既有门禁耗时开放项继续跟踪
> 适用范围：Billboard 预聚合有效性、Records 完整/分段接口一致性、Records 过滤参数传播、Billboard 记录与详情稳定排序、播放排行同次数排序
> 关联台账：[`../issues/2026-08-27-issue-register.md`](../issues/2026-08-27-issue-register.md)
> 当前规则：[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)
> 交付证据：[`../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)

## 0. 决策摘要

### 0.1 实施结果（2026-08-29）

- B1：聚合 hash 与完整 semantic proof 已收敛为共享 helper；全量、历史分区、track-credit role-only/成员变化、artist identity 和搜索署名 delta 发布均使用同一兼容性检查与 proof 刷新路径。
- B2：完整与 staged Records 共用 track enrichment/Power Score 输入 helper；L2/L3 × dynamic/fixed 四个 endpoint contract 均断言 `data.records == records.records`。
- B3：Records 页面改用完整 `BillboardContextParams`，query key、请求和 preload 复用同一对象，并在分析设置加载完成前关闭查询。
- B4/R1：Records、艺人/专辑详情与播放排行追加稳定实体键；播放次数榜明确以时长为第二排序键，播放时长榜保留次数为第二键。
- 主库派生聚合已在 Online Backup 和数据库副本验收后按当前设置重建；原始 `plays` 指纹未变，`agg_config.param_hash=222fbd0a3bcca38b`，track-credit/track-identity revision 分别为 35/5。
- 范围门禁通过：后端 unit 1,421 passed/2 skipped、contract 396 passed、前端 76 files/598 tests、前端 build、真实数据库副本四变体 API 及 desktop/390px 浏览器验收。默认完整全栈门禁未重复运行，由 `SS-2026-08-24-004` 继续跟踪，不影响本项统计与排序结论。

本轮修复分成两条独立工作流，不能把它们解释为同一根因：

1. **Billboard 一致性加固**：修复预聚合 proof/hash 发布、完整与 staged Records 的展示契约、Records 页面完整参数传播，以及 Records/艺人详情返回列表的最终稳定排序键。
2. **播放排行排序契约**：单独修复 `/api/analysis/charts?metric=plays` 的同次数排序，明确为“播放次数降序 → 收听时长降序 → 稳定实体键升序”。

历史 Taylor Swift 28/34 问题已经在当前数据上完成 34/34 对账，本规划不重写已确认正确的冠军判定、canonical track、L2/L3 或艺人有效署名规则。目标是消除潜在复发路径、恢复预聚合命中、统一接口展示，并让所有同值列表具有确定顺序。

实施顺序采用“先证明、后切换”：先补会失败的单元/契约测试，再改聚合 proof，再统一 Records builder 和前端参数，最后修改排序。任何真实数据库派生数据刷新都只能在备份和数据库副本验证通过后执行。

## 1. 当前基线与问题矩阵

以下事实来自 2026-08-29 对 HEAD `c21ad22841dcc98b3ce7fa20c9306d4830a1da15`、schema 63、真实 SQLite 和本地 API 的只读审计，只是实施前基线，不是永久常量：

| ID | 当前事实 | 风险 | 优先级 |
|---|---|---|---|
| B1 | role-only 曲目署名发布生成的 `agg_config.param_hash` 未包含当前 `track_identity_revision`，也未同步完整聚合依赖 proof；当前 hash 与读取路径期望不一致，预聚合安全回退到 raw 计算 | 结果当前正确，但冷请求约 48–54 秒，并产生 CPU、超时和 readiness 误判风险 | P0 |
| B2 | [`chart_staged_cache.py`](../../backend/domains/billboard/chart_staged_cache.py) 在 featured artist 展示名 enrichment 之前计算 track Power Score；完整 [`chart_compute.py`](../../backend/domains/billboard/chart_compute.py) 顺序相反 | `/billboard/data.records` 与 `/billboard/records.records` 的一条合作曲目 `artist_name` 不一致；指标未受影响 | P1 |
| B3 | [`RecordsPage.tsx`](../../frontend/src/pages/RecordsPage.tsx) 只向 `useBillboard()` 传 `merge_level`，其他参数依赖服务端设置和 API 默认值；艺人详情使用完整 `buildBillboardContextParams()` | 当前 Taylor 在 dynamic/fixed 下均为 34，但其他实体或非默认参数可能再次跨页漂移 | P0 |
| B4 | `artist_most_no1`、艺人详情冠军/上榜歌曲等可见列表只声明主要指标排序，没有统一的最终稳定实体键 | 同值条目可能在重建、输入乱序或分页边界上交换位置；计数事实不变 | P1 |
| R1 | [`chart_rows()`](../../backend/services/analysis_stats_service.py) 对 `metric=plays` 使用 `plays DESC, plays DESC` | 用户看到的同次数顺序没有时长或稳定键保证；与 Billboard 周榜规则不同 | P1，独立工作流 |

Taylor Swift 当前四变体基线必须保留：L2/L3 × dynamic/fixed 下，Records、`artist_track_counts.top1`、艺人详情 `info.top1`、详情冠军曲与周榜有效署名均为 34；稳定 `track_id` 集合差集为空，301 首上榜歌曲逐行指标差异为 0。

## 2. 范围与非目标

### 2.1 本轮必须完成

- 聚合读取 proof 与所有发布路径使用同一个构造器，role-only 发布后可继续命中未变化的周聚合。
- 相同参数和 revision 下，`/api/billboard/data.records` 与 `/api/billboard/records.records` 语义及展示字段完全一致。
- Records 页面请求、TanStack Query key 和详情页使用同一完整 Billboard filter fingerprint。
- Records/详情的可见列表在既有业务排序后追加稳定键，不改变冠军数、peak、weeks、Power Score 或有效署名集合。
- 播放排行 `metric=plays` 明确使用时长作为第二键，并按实体粒度追加确定性键。
- 真实数据库副本、真实 API、desktop 和 390px 页面均完成验收。

### 2.2 本轮不做

- 不修改 Billboard 周榜现有规则；其 `play_count DESC → total_ms DESC → 稳定 ID/名称` 已正确。
- 不重写 canonical track、L2/L3 membership、featured/primary 署名或开放周发布规则。
- 不把 All-time/Power Score 改成普通播放次数榜。
- 不新增 schema migration；若实施中发现必须迁移，停止并单独评审迁移方案。
- 不修改或删除原始 `plays`、`tracks`、`track_artists`、canonical identity 或人工治理审计记录。
- 不以放宽 hash/readiness 校验换取表面缓存命中。

## 3. 目标契约

### 3.1 Billboard 聚合 proof

聚合命中必须同时满足：

```text
param_hash == hash(
  playback policy,
  min_ms / music_only / week boundary / dynamic threshold / merge gap,
  artist identity revision,
  track-credit revision,
  track-identity revision
)

并且 agg_config 中的 generation/dataset digest、builder、duration、
credit membership、identity、track credit、track identity、album project
等依赖 proof 全部与当前事实一致。
```

role-only 变化只允许推进“证明”和候选展示 revision，不得重算或改写 `agg_weekly_*` 事实行。实现时应在 [`backend/core/db.py`](../../backend/core/db.py) 提取一个事务内可复用的聚合 proof 刷新函数，由全量、增量、artist identity 和 track-credit role-only 发布共同调用；禁止继续在 service 中手写不完整的 `_agg_param_hash(...)` 参数列表。

### 3.2 Records 接口一致性

对同一 normalized 参数对象和同一进程缓存 revision：

```text
GET /api/billboard/data       -> payload.records
GET /api/billboard/records    -> payload.records

canonicalized(payload.records) 必须完全相等
```

`artist_name` 是多艺人展示标签，`artist_names` 是逐艺人深链和 attribution 数组；二者不能互相替代。track enrichment 必须发生在依赖展示字段的 Power Score/Records 计算之前。完整与 staged builder 应复用同一个“小型 records inputs builder”，避免仅靠复制执行顺序维持一致。

### 3.3 Records 参数与缓存键

Records 页面有效参数固定来自 `useAnalysisFilters()`，URL `merge_level` 只覆盖其中的 merge level：

```text
min_ms
music_only
merge_enabled
dynamic_threshold
max_merge_gap_minutes
merge_level
include_compilations
bb_top_n
bb_album_top_n
bb_artist_top_n
bb_week_start_dow
bb_week_start_hour
```

同一个 `buildBillboardContextParams()` 返回值必须同时用于：

- API query string；
- TanStack Query key；
- `/data` 与详情/对决等下游请求；
- 测试中的过滤 fingerprint 断言。

设置尚未加载时不发送带前端硬编码默认值的抢跑请求；应使用 `enabled: !filtersLoading` 或等价门禁。`family`、`record` 等纯展示 query 不进入统计 fingerprint。

### 3.4 确定性排序

排序只追加 tie-breaker，不改变既有主要指标语义：

| 消费链 | 目标排序 |
|---|---|
| 播放排行，`metric=plays` | `plays DESC → hours DESC → stable_entity_key ASC → normalized_name ASC` |
| 播放排行，`metric=hours` | 保持 `hours DESC → plays DESC`，追加同一稳定实体键和名称 |
| `artist_most_no1` | `冠单数 DESC → normalized canonical artist name ASC`；其他冠军周/专辑字段保持展示指标，不暗中改变“最多冠单”的主语义 |
| 艺人详情歌曲 | 保持 `peak_position ASC → weeks_on_chart DESC`，追加 `track_id ASC → normalized track name ASC` |
| 其他 Records 可见列表 | 保留现有业务键，统一追加该实体稳定 ID；无 ID 时使用 canonical normalized name tuple |

`stable_entity_key` 按结果粒度生成：歌曲优先 canonical `track_id`；专辑优先当前 project/release 稳定键，缺失时使用 normalized `(artist_name, album_name)`；艺人优先 canonical artist ID，当前结果帧没有 ID 时使用 normalized canonical artist name。不得使用 DataFrame 当前 index 或输入位置作为稳定键。

## 4. 分阶段实施计划

### Phase 0：冻结证据并先补失败测试

1. 记录实施 HEAD、工作树、SQLite 路径/大小、schema、`PRAGMA quick_check`、播放数据 generation/digest、artist/track-credit/track-identity revisions 和完整 `agg_config`。
2. 固定审计参数，保存 L2/L3 × dynamic/fixed 的 `/data`、`/records` 和 Taylor Swift 详情原始 JSON 摘要及稳定 ID digest。
3. 在数据库副本记录 `_try_load_from_agg()` 当前 miss、raw fallback 耗时和聚合表行数。
4. 先增加会在旧实现失败的测试：role-only proof 命中、完整/staged records 相等、Records 完整参数、输入乱序稳定排序、播放排行同次数按时长。

退出门禁：所有新测试都能明确复现对应问题；不允许用当前真实数字直接硬编码通用业务测试。

### Phase 1：修复聚合 proof/hash 发布（B1）

涉及文件：

- [`backend/core/db.py`](../../backend/core/db.py)
- [`backend/services/track_credit_rebuild_service.py`](../../backend/services/track_credit_rebuild_service.py)
- [`backend/tests/unit/test_track_credit_rebuild.py`](../../backend/tests/unit/test_track_credit_rebuild.py)
- 聚合命中/一致性 contract tests

实施内容：

1. 提取单一 `build/refresh aggregation proof` helper，统一计算 `_agg_param_hash` 与 `_aggregation_semantic_dependencies`。
2. role-only 路径显式读取当前 `track_identity_revision`，并在推进 `active_aggregate_revision` 的同一事务中刷新全部语义 proof；保留 generation、dataset digest、build strategy 等不变事实。
3. helper 在现有聚合 proof 不完整或事实依赖发生变化时拒绝“只推进 revision”，转入安全的 bounded/full rebuild，不伪造 ready。
4. 发布前后比较四张 `agg_weekly_*` 的行数与内容 digest，role-only 路径必须完全不变。
5. 清理相关进程内 Billboard cache 后，验证 `_try_load_from_agg()` 返回有效 DataFrame，而不是 raw fallback。

退出门禁：unit/contract 全绿；数据库副本上的 stored/expected hash 相等，`check_agg_valid=true`，聚合事实 digest 不变。

### Phase 2：统一 Records builder 与接口契约（B2）

涉及文件：

- [`backend/domains/billboard/chart_compute.py`](../../backend/domains/billboard/chart_compute.py)
- [`backend/domains/billboard/chart_staged_cache.py`](../../backend/domains/billboard/chart_staged_cache.py)
- [`backend/domains/billboard/records*.py`](../../backend/domains/billboard/)
- Billboard unit/contract tests

实施内容：

1. 把 `track_summary` 构建、track artist enrichment、Power Score 和 Records 输入准备收敛到共享 helper。
2. staged 路径在 Power Score/Records 之前完成 `weekly` 和 `track_summary` enrichment。
3. 确认 `artist_name`、`artist_names`、cover、track ID 和所有数值字段在完整/staged 返回中逐字段相等。
4. 加入合作歌曲合成 fixture，至少覆盖 primary + featured、同一周重复行和 L2/L3 canonical track。
5. 增加 endpoint contract：相同 query 参数下 canonicalized `data.records == records.records`。

退出门禁：已知曲目 4453 的两个接口均显示完整合作署名；所有 Records 数量、排名和 Power Score 与修复前基线一致。

### Phase 3：统一 Records 参数传播（B3）

涉及文件：

- [`frontend/src/pages/RecordsPage.tsx`](../../frontend/src/pages/RecordsPage.tsx)
- [`frontend/src/hooks/useBillboard.ts`](../../frontend/src/hooks/useBillboard.ts)
- [`frontend/src/features/billboard/billboardContext.ts`](../../frontend/src/features/billboard/billboardContext.ts)
- `queryKeys.billboard` 与前端测试

实施内容：

1. Records 页面读取 `useAnalysisFilters()`，等待设置加载完成，并用 URL merge level 覆盖 filters 中的 merge level。
2. `useBillboard()` 改为接收完整 params 对象；query key 和 request 共用同一对象，移除只传 `merge_level/include_compilations` 的窄接口。
3. `loadBillboardData()`、preload helper 若继续保留，必须接受明确 params；没有完整上下文时不预取可能污染缓存的默认版本。
4. 为 dynamic true/false、非默认周边界、Top-N、merge gap 和 include compilations 增加参数/缓存键测试。
5. 验证 query 中的 `family` 切换只改变 UI，不产生新的 Billboard 数据请求；merge level 切换必须产生新 fingerprint。

退出门禁：浏览器网络证据显示 Records 与艺人详情 query 参数逐项一致；四个统计变体不会串缓存。

### Phase 4：补齐确定性排序（B4、R1）

涉及文件：

- [`backend/domains/billboard/records_championship.py`](../../backend/domains/billboard/records_championship.py)
- [`backend/domains/billboard/details.py`](../../backend/domains/billboard/details.py)
- 其他返回可见 Records 列表的 `records_*.py`
- [`backend/services/analysis_stats_service.py`](../../backend/services/analysis_stats_service.py)
- 对应 unit/integration tests

实施内容：

1. 提取或复用 normalized stable sort key，逐个审计 Records 返回列表，不修改中间集合的冠军判定。
2. 对 `artist_most_no1` 在 `head(15)` 之前完成完整稳定排序，避免 cutoff tie 依赖 groupby 输入顺序。
3. 艺人详情歌曲在现有 `peak/weeks` 后追加 `track_id/name`，专辑详情同类列表采用对应稳定实体键。
4. `chart_rows()` 按实体构造稳定键；plays 排行使用 `plays/hours/stable key/name`，hours 排行使用 `hours/plays/stable key/name`。
5. 使用同一 fixture 的多次随机乱序输入断言输出完全一致，并覆盖 offset/limit 跨越同分组的分页场景。

退出门禁：真实 API 的同次数样本按时长降序；Billboard 周榜排序测试保持原样通过；Records/详情的实体集合和指标均无变化。

### Phase 5：真实数据库副本与 UI 验收

1. 通过 SQLite Online Backup 创建带时间戳的数据库副本；所有 proof 修复、role-only 模拟和聚合重建先在副本执行。
2. 在副本执行 `PRAGMA quick_check`、外键检查和聚合表/配置 digest 对比。
3. 同一服务进程、同一 revision、同一参数下重新获取四变体：
   - Records/详情 Taylor Swift 均为 34；
   - 稳定 `track_id` 差集为空；
   - 301 首上榜歌曲的 play count、peak、weeks、冠军字段逐行相等；
   - `/data.records` 与 `/records.records` 完全相等；
   - 开放周仍不发布。
4. 清冷/热进程缓存分别验证一次，证明聚合路径真实命中；记录耗时但不以单次时间阈值代替命中证据。
5. desktop 与 390px 验收 Records、艺人详情和播放排行；检查筛选切换、深链、同分顺序、加载/错误状态与横向溢出。
6. 只有副本验收通过后，才允许在主库备份后刷新派生 proof/cache；不需要重建时不得为了“保险”全量重写聚合表。

## 5. 测试矩阵

| 层级 | 必测内容 |
|---|---|
| Unit | `_agg_param_hash` 包含三类 revision；role-only 完整 proof；聚合事实行不变；合作署名 enrichment 顺序；各实体 stable sort；输入乱序 |
| Contract | `/data.records == /records.records`；Records/详情冠军 ID 集合一致；L2/L3 × dynamic/fixed；完整周边界；featured attribution |
| Integration | `/api/analysis/charts` plays/hours 两种 metric、track/album/artist 三种 entity、offset/limit 同分分页 |
| Frontend | 完整参数对象同时进入 query key/request；filters loading 门禁；dynamic false；非默认周边界；family 不改 fingerprint |
| Real DB copy | hash/proof 命中、四聚合表 digest、34/34 ID 对账、301 行指标、开放周、冷/热请求 |
| Browser | desktop/390px Records、详情、播放排行；参数切换和稳定顺序 |

建议的代码门禁：

```bash
.venv/bin/pytest backend/tests/unit/test_track_credit_rebuild.py -q
.venv/bin/pytest backend/tests/unit/test_billboard_record_artist_attribution.py -q
.venv/bin/pytest backend/tests/unit/test_billboard_stable_ranking.py -q
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
cd frontend && npm test
cd frontend && npm run build
python3 scripts/docs_audit.py
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
```

局部测试通过只能标记 Partial；最终交付至少需要目标 contract、真实数据库副本和真实浏览器验收。默认完整全栈门禁若受现有耗时开放项阻断，应明确记录为外部于本修复的 Partial，不能省略已完成的业务证据。

## 6. 发布、回滚与数据安全

### 6.1 发布顺序

1. 合并后端 proof 与 Records contract 修复，重启后端以清空进程内 `lru_cache`。
2. 验证 API parity 和聚合命中后，再发布前端完整参数传播。
3. 最后发布排序修改，避免参数/缓存问题与可见顺序变化同时排障。
4. 对主库只执行已经在副本验证的派生 proof/cache 刷新；保留变更前 Online Backup。

### 6.2 回滚

- 代码回滚：revert 对应 scoped commit，重启后端和前端；不回退原始事实表。
- 排序回滚：只回退排序 helper/调用点；它不需要数据库恢复。
- proof 发布失败：继续让读取路径安全 raw fallback，标记 degraded；从备份恢复 `agg_config`/派生聚合，或执行受控全量重建。禁止手工拼接 hash 冒充 ready。
- staged parity 失败：临时继续由 RecordsPage 消费已验证的 `/billboard/data`；不得让不一致的 `/records` 成为默认消费链。
- 参数传播失败：回退前端请求改动和对应 query cache；服务端统计规则不回退。

任何回滚都不得删除或重写 `plays`、原始曲目/专辑/艺人、署名治理事件或 canonical membership。备份保留期限和最终清理仍按现有数据治理规则执行。

## 7. 完成定义

只有同时满足以下条件，才将本规划标记为已实施：

- B1–B4、R1 的失败测试先红后绿，并有对应源码与 contract 证据。
- 当前真实数据库副本的聚合 proof 有效且真实命中，role-only 路径未改写聚合事实行。
- `/data.records` 与 `/records.records` 同参数完全一致。
- Records 与详情四变体的稳定实体集合、计数和指标一致，Taylor Swift 保持 34/34。
- 播放排行同次数按时长降序，所有实体和分页顺序在乱序输入下稳定。
- desktop/390px 浏览器验收通过，未出现参数串缓存或加载回归。
- 文档审计、目标测试、前后端构建及适用的全栈门禁均有明确状态。
- 问题台账 `SS-2026-08-27-001` 和本计划状态只在证据齐全后更新；未完成阶段不得提前标记 resolved。
