# 音乐查找验收缺口完整修复规划

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

> 创建日期：2026-08-16
> 状态：已完成（实现、真实主库维护、生产副本预建、联合回滚与远程生产均通过）
> 前置结论：实施前仅默认 L2 + 动态阈值开启场景可用；该 Partial 基线已被本轮修复取代
> 适用范围：搜索快照覆盖、统计语义、候选热路径、Quick Open、`/music/search`、公开只读与生产门禁
> 关联文档：`2026-08-16-music-search-performance-and-experience-optimization-plan.md`、`../../reports/2026-08-16-music-search-optimization-delivery.md`

> 2026-08-16 后续调整：本文的六变体统计语义与历史验收证据继续有效，但“每个新 SHA 都在一次性
> 工作副本中冷建候选索引和六变体”的发布策略已被
> `2026-08-16-music-search-direction-realignment.md` 取代。新实现按确定性候选版本与统计 fingerprint
> 分别复用，随机 generation ID 不再触发统计重建；阶段 A–E 已完成。镜像经私有 CAS Artifact
> 增量传输到现有服务器，再由服务器推送 TCR；正常 production workflow `31977767545` 已成功切换，
> 最终 workflow `31979057642` 以 SHA `cf2270f1` 在 9 分 57 秒完成，六套统计精确复用，搜索预检
> 仅 2 秒，生产精确/模糊/简繁/短 CJK 语义门禁通过。

## 0. 执行摘要

最终结果为 **Pass**。migration 34、持久 revision state、六变体 snapshot-set、Billboard 非默认
参数贯穿、候选 SQL 分页与前端状态机均已落地。真实主库六个变体全部为
`ready + music_search_snapshot_v2`，搜索 GET 不再扫描 `plays` 推断 revision，也不把完整资格集合或
全部 FTS 命中加载到 Python。七类查询各 60 次、共 420 个 HTTP 候选样本 P95 为 40.741ms，HTTP
context P95 为 6.921ms，响应均小于 8KiB。Chromium、Firefox、WebKit、七档视口、200% reflow、
full/showcase/dual、本地生产镜像、schema 33→34、Online Backup 与恢复演练全部通过。

验收中另外发现并修复了三项计划外但同范围的问题：SQLite `foreign_keys=OFF` 时旧快照 context
不会随 meta 裁剪、Firefox 缺少可构造 `Intl.Segmenter` 会空白页、Docker 构建上下文会带入嵌套
`seed.db`。真实库 15,175 条搜索 context 孤儿已在 165MiB 在线备份保护下定点清理为 0；其余
7,831 条历史外键问题不属于本轮，未修改。生产发布由 GitHub Actions 在每个目标 SHA 上执行
自适应副本预检与 runtime exact gate；远程是否已运行该 SHA，仍只以 production deployment 记录
为准。

本轮修复不推翻已经完成的两阶段搜索架构。候选索引、context 快照、IME、请求取消、分页、
Quick Open、Phone presentation 和公开只读边界继续保留。需要修复的是三个尚未闭合的基础契约：

1. **快照覆盖契约**：前端实际支持 L1/L2/L3 与动态阈值开/关，但维护链路目前只预建
   L2 + 动态阈值开启；其他模式会永久返回 `unavailable / 0`。
2. **统计一致性契约**：过滤指纹包含 `merge_enabled` 与 `include_compilations`，但 Billboard
   lookup 没有完整消费这两个值，非默认设置下可能把不同口径的播放次数和榜单 badge 合并展示。
3. **轻量热路径契约**：候选请求仍通过 `COUNT / MAX / SUM / COUNT DISTINCT` 扫描整张 `plays`
   计算 revision，并在 Python 中加载、排序所有 FTS 命中；当前规模基本达标，但延迟仍随数据量和
   高命中查询线性增长。

目标状态是：六种消费搜索变体都有明确生命周期；搜索 GET 只做 O(1) revision 读取和有界索引查询；
context 中的播放次数、PK、在榜周数和走势排名与相同完整口径的详情接口一致；公开请求始终纯读取。

## 1. 当前验收事实

### 1.1 最终已通过并继续保留

- `response_mode=candidates` 与 `/api/music/search/context` 已从旧 lifetime pandas/Billboard 同步路径解耦。
- FTS5 trigram、fallback、准确总数、单类型分页、稳定 `entity_key` 和安全详情深链已经建立。
- 当前真实主库六个支持变体全部为 `ready + music_search_snapshot_v2`，`love` 在默认变体返回
  276 个候选。
- 七类查询共 420 个最终 HTTP 样本：候选 P50/P95 15.780/40.741ms，context
  P50/P95 6.034/6.921ms。
- Quick Open 的 Cmd/Ctrl+K、默认不预选、键盘导航、焦点归还、IME 门禁和 Phone 返回恢复已通过。
- public-readonly 显式允许两个搜索 GET、拒绝 `any_local`，并有零写入测试。
- migration 32/33/34、生产 FTS5/trigram、旧 HEAD 读取 additive schema、33→34 与本地恢复已经验证。

### 1.2 实施前必须修复的失败证据

真实接口同一查询：

| 过滤变体 | `snapshot_status` | `total` |
|---|---|---:|
| L2 + 动态阈值开启 | `ready` | 276 |
| L1 + 动态阈值开启 | `unavailable` | 0 |
| L3 + 动态阈值开启 | `unavailable` | 0 |
| L2 + 动态阈值关闭 | `unavailable` | 0 |

原因是 `music_search_maintenance_service._current_filter_values()` 将 `dynamic_threshold=True`、
`merge_level=2` 写死，而前端 `useAnalysisFilters()` 从 localStorage 读取这两个值。现有 L1/L2/L3
一致性契约测试在测试内部手工构建三份 snapshot，没有验证真实维护链路能否产生它们。

### 1.3 实施前性能复核

以下数据是确定修复范围时冻结的失败基线，不代表最终状态：

- `playback_source_revision()` 的查询计划包含 `SCAN plays` 和临时 B-tree；真实主库 P50 约 16.3ms。
- 完整 filter context 构建 P50 约 19.3ms、P95 约 20.9ms。
- 高命中三字符查询 `the` 的 60 次热 HTTP 请求为 P50 77.992ms、P95 81.359ms、最大 268.581ms，
  已略超候选 P95 80ms 预算。
- 当前 `get_ready_music_search_entity_keys()` 每次请求加载约 7,581 个 key；当前约 2.1ms，但仍随实体数增长。

## 2. 目标与非目标

### 2.1 修复目标

1. 前端实际支持的 L1/L2/L3 × 动态阈值开/关六种组合都能获得精确 snapshot。
2. source/settings 变化后，六种 snapshot 有可诊断的 `pending / running / ready / failed / stale` 生命周期。
3. 默认 L2 + 动态阈值开启优先恢复，其他变体随后后台完成；任何变体不得冒充另一个变体。
4. `merge_enabled`、`include_compilations`、merge level、动态阈值、最大间隔、Top N、周边界和年份
   在 snapshot 构建、详情对照、filter fingerprint 和缓存 key 中一致。
5. 候选和 context GET 不扫描 `plays`、Billboard aggregate 或 metadata 全表来计算 revision。
6. 候选 repository 不把完整 eligible key set 和所有高命中结果加载到 Python 后再分页。
7. warming/stale 状态会自动观察就绪，但网络失败仍保持 `retry: 0`，避免昂贵错误重试。
8. 当前规划、交付报告和变更日志只在新门禁实际通过后恢复 `Pass / 已完成`。

### 2.2 非目标

- 不恢复旧同步 `include_chart=true` 搜索作为消费 UI 热路径。
- 不改变 Masthead utility、`/music/search` 和既有详情路由的信息架构。
- 不引入 Elasticsearch、Meilisearch、Redis、LLM、拼音猜测或外部搜索服务。
- 不让 public GET 排队、写 snapshot、写 background job 或触发外部补全。
- 不在本轮重构全部 Billboard；只扩展搜索 snapshot 所需的完整过滤参数，并用共享契约防回归。
- 不把任意 API 查询参数组合都预建为 snapshot。候选 V2 的消费范围限定为当前服务端基础设置和六个
  明确支持的客户端变体；旧 legacy 接口继续承担兼容用途。

## 3. 冻结的修复决策

### 3.1 支持六个、且只支持六个消费变体

`merge_level` 与 `dynamic_threshold` 是当前搜索消费界面可独立变化的参数，因此每一套服务端基础设置
必须覆盖：

```text
(L1, dynamic=true)   (L1, dynamic=false)
(L2, dynamic=true)   (L2, dynamic=false)
(L3, dynamic=true)   (L3, dynamic=false)
```

`min_ms`、`music_only`、`merge_enabled`、`max_merge_gap_minutes`、`include_compilations`、三类 Top N 和
Billboard 周边界继续以服务端 Settings 为基础事实。服务端基础设置发生变化时生成一个新的
`semantic_base_key`，旧 base 下的 snapshot 全部转为 stale。

候选 V2 若收到与当前服务端基础设置冲突的自定义参数，必须返回 422 和稳定错误码
`unsupported_candidate_filter`，不再以 `unavailable` 掩盖“该组合从未被维护链路支持”。
`year_start / year_end` 仅保留给 legacy 或其他明确支持年份窗口的接口，候选 V2 当前不接受自定义年份窗口。

### 3.2 搜索 GET 永远纯读取

- candidates/context GET 只读取 revision state、active index 和 snapshot。
- missing/warming/stale/failed 都不能在 GET 中创建 meta、enqueue job 或更新 `last_accessed_at`。
- private 和 public 使用相同读取代码；差别仅为 public 禁止 `any_local` 和维护写入口。
- 重建只允许由启动维护、导入维护、Settings mutation、版本归并、艺人身份、曲目署名和显式的
  private-admin 维护操作触发。

### 3.3 一个 snapshot-set job 顺序构建六个变体

不得向 3-worker 通用 JobQueue 同时投放六个会争用 pandas/SQLite/Billboard cache 的重任务。每个
`semantic_base_key` 只允许一个 `music_search_snapshot_set_rebuild` job，job 内顺序为：

1. L2 + dynamic=true（public 与默认 private 基线）；
2. L1 + dynamic=true；
3. L3 + dynamic=true；
4. L2 + dynamic=false；
5. L1 + dynamic=false；
6. L3 + dynamic=false。

入队事务先为六个 fingerprint 创建或更新 `pending` meta。每个变体独立事务发布，先完成的立即
`ready`，单个失败不得回滚已经 ready 的其他变体。job 最终报告 `ready_count / failed_count / timings`。

### 3.4 revision 必须持久化，不在 GET 中推断

新增 O(1) revision state，由已知 mutation 在同一业务事务或成功维护收口点显式递增。候选 GET 不再
通过表 cardinality、`SUM(ms_played)` 或文件 mtime 猜测数据是否变化。

## 4. 目标数据模型与指纹

### 4.1 migration 34

新增 `music_search_revision_state`：

| 字段 | 含义 |
|---|---|
| `state_id=1` | 单例 |
| `playback_revision` | 成功导入/播放事实变化后递增 |
| `billboard_revision` | aggregate 成功发布或榜单语义变化后递增 |
| `metadata_revision` | 影响搜索文档的名称、项目、身份、署名变化后递增 |
| `settings_revision` | 影响搜索基础语义的服务端 Settings 成功保存后递增 |
| `updated_at` | 诊断时间 |

为 `music_search_snapshot_meta` 增加：

- `semantic_base_key TEXT`；
- `merge_level INTEGER`；
- `dynamic_threshold INTEGER`；
- `builder_version TEXT`；
- 索引 `(semantic_base_key, status, merge_level, dynamic_threshold)`。

旧 snapshot 在 migration 后标记 stale。migration 不重写原始音乐事实；新 snapshot 完成前默认变体
显示 warming/unavailable，不回退到未经证明的 any-local 消费结果。

### 4.2 指纹 V2

`semantic_base_key` 包含：

- 服务端基础过滤设置；
- `playback_revision / billboard_revision / metadata_revision / settings_revision`；
- active search index revision；
- artist identity revision、track credit revision；
- normalization/index/snapshot/chart builder 版本。

最终 `filter_fingerprint` 为：

```text
sha256(semantic_base_key + merge_level + dynamic_threshold)
```

任何影响播放次数、资格、entity key 或 chart badge 的实现变化都必须提升对应 builder/version 常量。

### 4.3 失效矩阵

| 事件 | revision | documents | 六变体 snapshot | 触发时机 |
|---|---|---|---|---|
| Streaming import + maintenance 成功 | playback + billboard | rebuild | rebuild | 成功发布后 |
| min/music/merge/gap/Top N/周边界/精选集设置 | settings | 视字段决定 | rebuild | Settings 提交后 |
| aggregate shadow table 发布 | billboard | 不变 | rebuild | 单事务发布后 |
| track group / album project 变化 | metadata | rebuild | rebuild | 版本归并成功后 |
| artist identity revision | metadata | rebuild | rebuild | identity aggregate ready 后 |
| track credit revision | metadata | rebuild | rebuild | credit aggregate ready 后 |
| 名称/主体元数据修订 | metadata | rebuild | rebuild | metadata mutation 后 |
| 仅封面文件下载完成 | 不变 | 不变 | 不变 | cover URL 由稳定 ID 决定 |
| 搜索 normalization/index schema 改变 | metadata + version | rebuild | rebuild | deploy maintenance |

失败或回滚的业务 mutation 不得递增 revision；导入回滚后 revision 与 snapshot 状态必须恢复到备份事实。

## 5. 统计一致性修复

### 5.1 Billboard 参数贯穿

扩展 `_build_chart_lookup()` 及 Billboard staged/cache 链，使其显式消费：

- `merge_enabled`；
- `include_compilations`；
- 已有的 merge level、动态阈值、最大间隔、三类 Top N、周边界和年份。

`compute_billboard_data()`、`_compute_billboard_data_cached()`、`_load_and_rank*()` 及其 cache key 必须
同时增加 `merge_enabled`，不能只修改函数入口而继续命中旧缓存。`include_compilations` 已存在于 Billboard
计算签名，本轮必须从 search context 传到底。

`merge_enabled=false` 不得读取只代表 merge-enabled 口径的预聚合结果；若当前 aggregate schema 没有
对应维度，就显式走 raw exact 路径。`backend/api/billboard/data.py::_billboard_params()` 也必须传递该值，
避免搜索 snapshot 修正后与 Billboard weekly/data 页面继续分叉。

### 5.2 播放次数与榜单分别对照权威详情

每个 snapshot item 的验收规则：

- `play_events / total_ms` 对照同口径实体 Stats/Plays；
- `peak_position / weeks_on_chart / power_rank` 对照同口径 Billboard detail；
- 专辑按 album project + canonical artist；
- 艺人按有效署名 fan-out + canonical identity；
- L2/L3 track 使用规范 group 主体和详情真路由；
- 无上下文仍为 `context: null`，不得序列化 0 冒充未加载。

新增精选集 fixture，必须证明 `include_compilations=false/true` 会产生预期差异，且搜索与详情差异完全一致。

### 5.3 snapshot 发布安全

- 构建前写 `pending/running`，旧 exact-ready snapshot 不得被不同 fingerprint 复用。
- 数据行先写入新 fingerprint，数量、重复 entity key、负数指标、链接主体和 chart 范围验证通过后再 ready。
- 构建失败保存异常类型和阶段，不保存原始查询、实体名称或播放行。
- 每个 base 最多保留当前六变体和上一 base 的六变体；清理不得删除正在被读的 current rows。

## 6. 候选热路径修复

### 6.1 移除请求内全表 revision 计算

`build_music_search_filter_context()` 改为只读取：

- `music_search_revision_state` 单行；
- `music_search_index_state` 单行；
- identity/credit state 单行；
- Settings 的已解析快照。

`playback_source_revision()` 与 `billboard_aggregation_revision()` 可保留为离线 doctor/审计工具，但不得由
candidates/context GET 调用。目标为 fingerprint phase P95 ≤2ms，查询计划不得出现 `SCAN plays` 或扫描
任一 aggregate 全表。

### 6.2 eligibility 改为 SQL join

repository 接收 `snapshot_key`，在 FTS/document 查询中 join `music_search_entity_context`，不再先读取
全部 7,581+ eligible entity keys 为 Python set。不存在 exact-ready snapshot 时仍 fail closed。

### 6.3 相关性、总数和分页下推 SQLite

把稳定排序规则写成 SQL `CASE`：

1. label exact；
2. label prefix；
3. label token；
4. secondary/alias exact 或 prefix；
5. trigram substring；
6. popularity、normalized label、entity key tie-break。

同一 bounded match CTE 分别产生：

- `GROUP BY kind` 的准确总数；
- 当前 kind 的 `ORDER BY ... LIMIT/OFFSET`；
- all 视图每类前 5 条，可使用 window function 或三次有界查询。

不得先把所有命中行构造成 Pydantic 对象后再切片。fallback 继续允许 bounded LIKE，但两字符查询只做
exact/prefix；fallback 必须返回准确状态，不把前 10 条数量冒充 total。

### 6.4 性能探针升级

固定探针至少覆盖：

- exact；
- prefix；
- 多 token 跨字段；
- 高命中三字符；
- Unicode/NFKC；
- 单字符 CJK；
- 单类型第 2 页。

报告继续只记录 query id、长度、类型和命中数量，不写 raw query 或实体内容。每种 query class 至少
60 个 warm 样本，分别报告 fingerprint、snapshot join、candidate SQL、serialize 和 HTTP total。

## 7. 前端状态与体验修复

### 7.1 snapshot 状态观察

- 网络错误仍使用 `retry: 0`。
- 当成功响应为 `warming` 或 `stale` 时，候选 hook 使用显式状态轮询：2s 起步，退避至 10s；ready、
  unavailable、组件卸载或页面隐藏后停止。
- Quick Open 关闭后由 TanStack observer 自动取消无观察者请求，不做前缀级 `cancelQueries`。
- `unavailable` 显示“暂不可用”和手动重新检查；private 可提供前往 Settings 维护区的入口，public 只展示
  cache-only 文案。
- 状态刷新期间保留当前可证明的同 fingerprint 候选；不得显示其他变体的 placeholder 数据。

### 7.2 filter key 与服务端能力对齐

- query key 继续包含 `semantic_base_key + normalized query + kind + page + page size + eligibility`。
- context key 继续包含服务端返回的完整 fingerprint 和排序去重后的 entity key。
- 前端不再发送服务端不接受/忽略的伪参数；`include_compilations` 由服务端 Settings base 决定。
- 切换 merge level 或动态阈值必须形成新 key，并正确显示该变体的 warming/ready，而不是旧结果冒充。

### 7.3 标准化高亮

`HighlightedSearchText` 使用与 query key 相同的 NFKC、标点和稳定 lowercase 规则，并维护规范化字符到
原始 grapheme 范围的映射；继续输出 React text/`<mark>`，禁止 `innerHTML`。根据 `match_field` 在 label
或 subtitle 中高亮；alias 命中仍可参与排序和诊断，但消费界面不展示“匹配别名”等内部标签。结果名称
与副标题必须跟随全局简繁体偏好，深链和最近查看的持久化值继续保留原始实体数据。

覆盖弯引号、全角 Latin、Unicode 空白、`ß -> ss` 和 CJK 标点；浏览器 locale 不得改变 query key 或高亮。

## 8. 实施阶段

### R0：先把失败写进门禁（小）

1. 将现有交付报告和原规划状态暂改为 `Partial / remediation pending`。
2. 新增真实维护链路测试：只调用 `rebuild_current...`/snapshot-set builder，不允许测试手工补齐 L1/L3。
3. 固定六变体失败向量、精选集/merge disabled 语义向量和高命中性能向量。
4. 给测试数据库加硬门禁：任何会写派生表/job 的测试若连接真实 `data/spotify_stats.db` 立即失败。

退出条件：新测试在旧实现上稳定暴露本报告的三个根因，且测试本身不改真实主库。

### R1：revision state 与六变体生命周期（大）

1. migration 34 与 revision helpers。
2. 统一 mutation/maintenance revision bump 和失效矩阵。
3. snapshot meta 增加可诊断维度。
4. 单 job、顺序构建六变体；默认 L2/true 优先。
5. doctor/rebuild script 输出六变体状态、实体数和阶段耗时。

退出条件：新基础设置下六个 fingerprint 都能从 pending/running 进入 ready；任一失败不污染其他变体。

### R2：统计语义贯穿（大）

1. Billboard 计算与缓存 key 增加 `merge_enabled`。
2. search chart lookup 传递 `merge_enabled/include_compilations`。
3. 六变体 × 三实体对照详情；精选集 true/false、merge true/false 独立覆盖。
4. 提升 search snapshot/chart builder version，禁止旧 snapshot 继续 ready。

退出条件：所有非默认配置一致性 contract 通过，且同一 fingerprint 内没有混合口径。

### R3：候选热路径收口（中到大）

1. candidates/context 改读持久 revision。
2. eligibility 下推 SQL join。
3. rank、total、pagination 下推 SQLite。
4. 升级性能 probe 和 Server-Timing 门禁。

退出条件：GET 查询计划无 plays/aggregate scan；全部固定 query class 的 warm HTTP P95 ≤80ms，context
P95 ≤20ms，响应 ≤8KiB。

### R4：前端状态与高亮（中）

1. warming/stale 状态轮询与停止条件。
2. variant key/placeholder 隔离。
3. 标准化高亮和 match field 展示。
4. Quick Open、完整页、Phone、Settings 两个治理消费者回归。

退出条件：切换 L1/L2/L3、动态阈值和输入法时没有空白假结果、旧指标串线或请求风暴。

### R5：生产与文档收口（中）

1. 全量 unit/contract/frontend/build/pre-commit/OpenAPI。
2. 真实主库只读性能、六变体离线构建时间和磁盘增量。
3. Chromium/Firefox/WebKit 与 360/390/430/768/1024/1280、200% reflow。
4. production backend 镜像 FTS5/trigram、full/showcase/dual、public zero-write。
5. Online Backup、migration 34 升级、旧镜像读取、失败回滚演练。
6. 只有全部门禁通过后，将原规划和交付报告恢复为 `Pass / 已完成`。

## 9. 文件级实施地图

### 9.1 后端新增

- `backend/domains/music_search/revisions.py`：持久 revision 读取、递增和 base key。
- `backend/domains/music_search/variants.py`：六变体枚举、优先级和 fingerprint 构造。
- `backend/tests/unit/test_music_search_revisions.py`。
- `backend/tests/contract/test_music_search_snapshot_variants.py`。
- `backend/tests/contract/test_music_search_nondefault_consistency.py`。

### 9.2 后端修改

- `backend/core/migrations.py`：migration 34。
- `backend/domains/music_search/context.py`：移除 GET 内扫描，升级 fingerprint v2。
- `backend/domains/music_search/snapshot.py`：snapshot-set 构建、参数贯穿、逐变体发布。
- `backend/domains/music_search/repository.py`：snapshot join、SQL 排序/总数/分页。
- `backend/services/music_search_candidate_service.py`：传 snapshot key，不再传完整 eligible set。
- `backend/services/music_search_maintenance_service.py`：单 set job、六变体生命周期。
- `backend/services/music_search_service.py`：完整 chart 参数。
- `backend/domains/billboard/chart_compute.py`、`chart_load_rank.py` 及必要 data loader：`merge_enabled`
  贯穿、raw/aggregate 分流与 cache key。
- `backend/api/billboard/data.py`：所有 staged Billboard facade 传递 `merge_enabled`，与详情和搜索共享口径。
- `backend/api/music.py`：支持范围校验、稳定状态响应和日志。
- 导入、Settings、version merge、artist identity、track credits：统一 revision bump/失效 helper。
- `backend/tests/conftest.py`：真实数据库写入硬阻断，而不是只 patch 个别 client fixture。

### 9.3 前端修改

- `frontend/src/features/music/search/useMusicSearch.ts`：状态轮询、variant placeholder 隔离。
- `frontend/src/features/music/search/api.ts`：只发送受支持参数。
- `frontend/src/api/query-keys.ts`：base/variant key。
- `frontend/src/features/music/search/HighlightedSearchText.tsx`：规范化范围映射。
- `MusicSearchDialog.tsx`、`MusicSearchPage.tsx`、`MusicSearchResults.tsx`：warming/failed/manual check 文案。
- 搜索 hooks/components/flow 测试：六变体、轮询停止、过时响应和高亮向量。

### 9.4 运维与文档

- `scripts/rebuild_music_search_derived_data.py`：六变体报告与 `--require-all-ready`。
- `scripts/music_search_performance_probe.py`：query class 和 phase budgets。
- `scripts/api_smoke_probe.py`、boundary/parameter audit：unsupported base filters 与状态协议。
- 原规划、交付报告、CHANGELOG、AGENTS/CLAUDE：仅同步成为长期约束的最终事实。

## 10. 验证矩阵

### 10.1 后端功能与一致性

| 维度 | 必测值 |
|---|---|
| merge level | L1 / L2 / L3 |
| dynamic threshold | true / false |
| merge enabled | true / false |
| include compilations | true / false |
| entity | track / album / artist |
| snapshot | missing / pending / running / ready / stale / failed |
| index runtime | FTS5 trigram / degraded fallback |
| surface | private-admin / public-readonly |

不做 3×2×2×2×3 的盲目笛卡尔积；使用 pairwise 覆盖全部参数交互，同时保留六变体 × 三实体的核心
18 个端到端事实对照。

### 10.2 前端交互

- composition 期间 0 请求，结束并防抖后 1 请求；
- A 请求晚于 B 返回，UI 仍只显示 B；
- variant 切换不得保留旧 context；
- warming 自动观察 ready，network error 不自动重试；
- URL q/kind/page、Back、Phone autofocus 和滚动恢复；
- Quick Open 无默认选择、方向键、Enter、Escape、Tab trap、focus restore；
- public 不读写 recent localStorage；
- NFKC/弯引号/全角/ß/CJK 高亮仍为安全 React nodes。

### 10.3 性能与容量预算

| 指标 | 门禁 |
|---|---:|
| fingerprint warm P95 | ≤2ms |
| candidate HTTP warm P50 | ≤50ms |
| candidate HTTP warm P95 | ≤80ms |
| context HTTP warm P95 | ≤20ms |
| candidate/context response | 各 ≤8KiB |
| candidate GET plays/aggregate scan | 0 |
| GET database writes/background jobs | 0 |
| 单 base 同时运行的 snapshot-set job | ≤1 |

初版生产 `linux/amd64` 镜像在真实 Online Backup 副本上的完整构建峰值为 1,569.547MiB，真实服务器
仅有 1,349MiB 可用时被门禁正确拦截。完成变体间 cache/GC 与主播放帧、艺人 fan-out 顺序计算后，
最终同规模六变体为 983,317.824ms（约 16 分 23.3 秒）、峰值 RSS 876.758MiB、数据库增量约
31.43MiB、WAL 0；同一 ready 副本重复校验为 313.549ms 且 DB/WAL 增量为 0。生产门禁据此冻结为
一次性统计冷建为 MemAvailable ≥1,280MiB（峰值之上约 403MiB/46% 余量）；普通发布固定严格复用
统计，使用 ≥640MiB 的候选预算（候选峰值 318.984MiB 的 2 倍以上）。可用磁盘均要求
≥`max(1GiB, DB × 4)`；目标服务器只有在候选版本或统计 fingerprint 实际变化时才执行对应独立维护，
普通新 SHA 只做精确复用校验。

### 10.4 发布门禁

- `pytest -m unit`、`pytest -m contract`、搜索聚焦和 mutation 失效测试；
- 前端全量 Vitest、production build、目标 ESLint；
- Ruff、format、mypy、detect-secrets、OpenAPI generate/diff/audit；
- production Docker SQLite FTS5/trigram doctor；
- full/showcase/dual config validation；
- public GET 前后逐表/`total_changes`/job count 零变化；
- migration 33→34、Online Backup、旧镜像只读兼容和回滚演练；
- 新 SHA 在明确数据库副本上关闭 startup rebuild，执行自适应 `--require-all-ready`；
- 精确六 fingerprint、migration 36、builder v2、搜索 context orphan=0 与容量门禁；
- 停服后的第二份 Online Backup 必须与预检源一致，否则拒绝替换；
- 失败时 SQLite、镜像 SHA 与 deployment mode 联合回滚；远程结果按 production workflow 判定。

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 六变体构建耗时或内存过高 | 只在统计 fingerprint 真实变化时构建；精确 ready 逐变体复用，持久 resume artifact 续建未完成部分；1,280MiB/4× 磁盘门禁继续 fail closed |
| Billboard 增加 merge flag 引发缓存串线 | 所有 facade/staged/LRU key 同步增加参数并加 key-separation test |
| revision 漏接 mutation | 集中 helper、失效矩阵 contract、禁止业务代码直接手写 stale SQL |
| 旧 snapshot 被新代码误读 | fingerprint/builder version v2，migration 后旧 snapshot 统一 stale |
| SQL 排序与 Python 旧排序不一致 | 固定 golden vectors、稳定 tie-break、分页重放测试 |
| 测试再次污染真实主库 | 测试启动时检查 `PRAGMA database_list`，命中真实路径立即 fail |
| public 打开隐式维护能力 | rebuild/prewarm API 不进 public allowlist，公开 GET 逐表零写入 |
| warming 轮询形成请求风暴 | 仅状态响应轮询、2–10s 退避、页面隐藏/卸载停止 |

## 12. 完成定义

只有同时满足以下条件，修复计划才可标记完成：

- [x] 真实维护链路产生六个支持变体，不依赖测试手工补 snapshot；
- [x] L1/L2/L3 和动态阈值开/关的消费搜索均能 ready；
- [x] merge enabled/disabled、精选集 included/excluded 的搜索 badge 与详情一致；
- [x] candidates/context GET 查询计划没有 `SCAN plays` 或 aggregate 全表扫描；
- [x] 高命中、Unicode、分页等全部性能向量满足预算；
- [x] warming/stale/failed、variant 切换和高亮完成浏览器验收；
- [x] public-readonly 保持零写入、零排队、零外部补全；
- [x] 真实主库、生产镜像、三浏览器、三模式和回滚门禁通过；
- [x] 全量测试在隔离数据库运行，没有新增主库 job/generation；
- [x] 原规划和交付报告根据新证据更新，不再提前声明 Pass；
- [x] 生产新 SHA 的副本预建、容量、精确六变体和联合回滚门禁已落地；
- [x] 远程运行状态只按对应 SHA 的 production deployment 记录表述，不以本地镜像代替。
