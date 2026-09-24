# Spotify Track `artists[]` 多艺人署名证据接入完整实施规划

> 创建日期：2026-09-23<br>
> 实现状态：IMPLEMENTED（仅 Spotify Track `artists[]` provider evidence）<br>
> 验证状态：PASS（隔离副本迁移、真实 API 全量回填及复跑；范围见交付报告）<br>
> 仓库状态（隔离验收时）：UNCOMMITTED<br>
> 远端状态（隔离验收时）：UNPUSHED<br>
> 部署状态（隔离验收时）：NOT_DEPLOYED<br>
> 规划边界：只接入并审计 Spotify Track `artists[]` 证据；不自动修改有效署名

## 1. 目标与完成定义

本计划的目标不是“让 Spotify 覆盖本地艺人署名”，而是把 Spotify Track object 中有序的 `artists[]` 完整、幂等地保存为独立 provider evidence，并生成可守恒的差异报告，为后续人工治理或多源核验提供可靠输入。

只有同时达到以下条件，才可称本计划完成：

1. 每个成功返回且结构合法的 Spotify Track `artists[]` 都能按原始顺序持久化，保留 Spotify artist id 与 credited name。
2. 首次回填、重复刷新、数组变化、部分失败、凭据缺失和进程中断均有确定行为；旧的上一可用证据不会被坏响应清空。
3. provider evidence 不写入 `plays`、`tracks`、原始 `track_artists` 或人工 override，不递增正式 track-credit revision，也不触发下游统计重建。
4. 能把每个有权威本地 owner 的 Spotify track 分类为一致、provider 新增、本地独有、provider 艺人未解析、身份冲突、owner 冲突或 provider 响应不完整，分类总数可与输入集合守恒对账。
5. 真实数据库验收在 Online Backup 或隔离副本上完成，记录回填覆盖、错误、差异、重复运行幂等性和原始事实不变证据。
6. 当前导入在没有 Spotify 凭据或 provider 临时失败时仍可完成；元数据阶段只标记可重试的 partial/degraded，不把核心导入变成硬失败。

## 2. 现状、根因与基线

### 2.1 当前链路

- `backend/core/import_data.py` 从 Spotify Extended Streaming History 读取单个 `master_metadata_album_artist_name`，并解析标题中的 `feat.`、`ft.`、`with` 写入原始 `track_artists`。
- `backend/domains/metadata/spotify_refresh.py` 已读取 Track object 的 `artists[]`，但 `_link_local_artist_from_track()` 只在名称精确归一化匹配时给已有本地艺人补 Spotify artist id。
- 同一文件中的 `upsert_track_batch()` 会保存 `spotify_track_meta`、ISRC 与专辑信息，但不会保存完整的 Track `artists[]`。
- `backend/services/import_maintenance_service.py` 和 `backend/services/import_stage_service.py` 已把 Spotify 元数据刷新作为导入后固定阶段，具备 scoped candidates、bounded backlog 和 retryable provider failure 语义。
- `backend/domains/metadata/track_credits.py` 已提供有效署名解析：原始 `track_artists` + active override + canonical artist。该正式事实链在本计划中保持不变。

根因因此不是“Spotify 没有返回合作艺人”，而是当前应用没有把已经返回的完整 `artists[]` 建模、持久化和审计；现有逻辑只消费了数组中可与本地主艺人名称精确匹配的部分。

### 2.2 2026-09-23 只读基线

| 指标 | 数值 |
|---|---:|
| `tracks` | 10,026 |
| 原始多艺人曲目 | 409 |
| 含 `featured` 原始署名曲目 | 386 |
| 原始单署名曲目 | 9,617 |
| 已有 ISRC 曲目 | 9,941（99.15%） |

实施前必须在目标数据库重新生成基线，并记录数据库 revision、生成时间和查询口径。以上数字不得用作迁移断言。

## 3. 核心决策

### 3.1 证据先行，正式事实不变

首轮只持久化和比较 Spotify evidence，不生成 `track_credit_overrides`，不改变有效署名，不刷新搜索/统计/年度总结，不向普通用户展示“已修正”的合作艺人。

### 3.2 不推断艺人角色

Spotify Track `artists[]` 表达有序 artist credits，但没有提供 `primary` / `featured` 角色。必须保存 `credit_order`，但不得把 `artists[0]` 之外的成员一律标记成 `featured`。差异报告只比较成员集合和顺序，不声称角色冲突。

### 3.3 不自动创建本地艺人

provider artist 优先通过 `artist_identity_external_ids(provider='spotify', external_id=...)` 解析本地稳定身份。名称精确匹配只能生成 linkage candidate；模糊匹配、同名或冲突时进入未解析报告，首轮不自动创建、合并或 canonicalize 新艺人。

### 3.4 使用 Spotify 专用 schema

首轮不建设抽象的多 provider 通用框架。只有第二个来源进入实施并形成真实合同后，才从 Spotify 与第二来源的共性中抽取 provider interface。

### 3.5 由 authoritative owner 承担比较主体

同一个 Spotify track id 可能与历史重复本地行有关。比较时必须先用 `spotify_track_owners` 解析权威本地 owner，再读取 owner 的有效署名；不得遍历任意 `tracks` 行并重复计数。

## 4. 范围与不做项

### 4.1 本计划包含

- additive schema migration；
- Track `artists[]` 响应校验、签名和原子持久化；
- scoped import refresh 与 bounded backlog 的证据缺口选择；
- 一次性、可恢复、可 dry-run 的全库回填入口；
- owner / artist identity 解析和只读差异报告；
- 健康与阶段结果中的 evidence coverage / provider partial 指标；
- 单元、合同、迁移、失败注入和隔离真实数据验收；
- 完成后更新当前参考规则和交付报告。

### 4.2 本计划不包含

- 不修改 `plays`、`tracks`、原始 `track_artists`；
- 不写 `track_credit_overrides` / events / state，不递增正式 metadata revision；
- 不将 provider evidence 自动晋升为有效署名；
- 不实现人工审核 UI；
- 不接入 MusicBrainz、Apple Music、歌词或语言识别；
- 不修改封面优先级或专辑身份；
- 不在任何 GET 请求中同步访问 Spotify 或冷建证据；
- 不把局部单元测试描述为全栈 Pass、生产部署或线上验收。

## 5. 目标数据流

```text
Spotify /tracks batch
        │
        ▼
校验完整 Track 与 artists[]
        │
        ▼
同批事务保存 spotify_track_meta + credit evidence
        │
        ├── 响应非法/部分失败：保留上一可用 evidence，报告 retryable error
        │
        ▼
通过 spotify_track_owners 解析本地 owner
        │
        ▼
通过 artist_identity_external_ids 解析 provider artist
        │
        ▼
与 owner 的 effective track credits 做离线差异报告

本阶段到此停止：不写 override，不递增 revision，不触发统计重建。
```

## 6. 数据模型设计

正式实现前先核对当前最大 migration id；规划时观察到最大值为 79，因此预计使用 migration 80，但不得硬编码占用一个已经被其他并行工作使用的编号。

### 6.1 `spotify_track_credit_sets`

每个 Spotify track 保存一份当前上一可用证据摘要：

| 字段 | 建议类型 | 约束 / 用途 |
|---|---|---|
| `spotify_track_id` | TEXT | 主键；关联现有 Spotify track identity |
| `artist_count` | INTEGER | 非负；与子表数量一致 |
| `credit_signature` | TEXT | 对按顺序规范化后的 `(artist_id, credited_name)` 计算稳定摘要 |
| `fetched_at` | TEXT | 最近一次合法响应获取时间 |
| `source_run_id` | TEXT NULL | 关联刷新/回填运行，便于审计与恢复 |
| `created_at` / `updated_at` | TEXT | 本地状态时间 |

如果 schema 已有合适的 Spotify track 外键，使用显式外键和级联规则；否则必须在 migration 测试中证明孤儿行不会产生。不要使用 `INSERT OR REPLACE` 更新父行，以免触发隐式 delete/insert 和子行级联删除。

### 6.2 `spotify_track_artist_credits`

保存 provider 返回的有序数组：

| 字段 | 建议类型 | 约束 / 用途 |
|---|---|---|
| `spotify_track_id` | TEXT | 外键到 credit set |
| `spotify_artist_id` | TEXT | provider 稳定 artist id |
| `credited_name` | TEXT | 原样保存的显示名称，不作为本地稳定身份 |
| `credit_order` | INTEGER | 从 0 开始；同一 track 唯一 |
| `observed_at` | TEXT | 本次合法观察时间 |

建议主键为 `(spotify_track_id, spotify_artist_id)`，并增加唯一约束 `(spotify_track_id, credit_order)`。如果真实样本证明同一 Spotify artist id 会在同一数组重复出现，则在进入迁移前调整主键为 `(spotify_track_id, credit_order)`，而不是静默丢项。

### 6.3 `spotify_track_credit_events`

只在签名首次建立或发生变化时写 append-only 事件：

| 字段 | 建议类型 | 说明 |
|---|---|---|
| `event_id` | INTEGER | 自增主键 |
| `spotify_track_id` | TEXT | 事件主体 |
| `event_type` | TEXT | `observed` / `changed` |
| `before_json` | TEXT NULL | 变化前有序数组；首次观察为空 |
| `after_json` | TEXT | 变化后有序数组 |
| `source_run_id` | TEXT NULL | 刷新运行 |
| `observed_at` | TEXT | provider 观察时间 |

重复刷新且签名不变时只更新 `fetched_at` / `updated_at`，不得新增事件。事件 JSON 只保存最小必要 evidence，不复制完整 Track response。

### 6.4 响应校验

只有同时满足以下条件，响应才可替换上一可用 evidence：

- Track object 非空，且 `id` 与请求的 Spotify track id 一致；
- `artists` 是非空数组；
- 每项都含非空字符串 `id` 和 `name`；
- `credit_order` 连续并保持 API 原顺序；
- 同一数组没有重复 artist id，除非真实样本和 schema 决策明确允许；
- 整个单 track evidence 可在一个事务中写入并重新读回相同签名。

单个 track 响应非法时，记录结构化错误并保留旧 evidence。批次请求成功不代表每个 id 都成功；缺失对象、`null` 或 id 不匹配必须逐项报告。

## 7. 刷新、选择与回填策略

### 7.1 日常导入后的 scoped refresh

在现有 metadata stage 中增加 `missing_credit_evidence` 选择器：

1. 优先选择本次导入新增或 identity 发生变化、已有 Spotify track id 但没有合法 credit set 的目标；
2. 再从历史缺口中选择有稳定顺序的 bounded backlog；
3. 沿用 Spotify Track API 每批最多 50 个 id 的边界，并保留 provider client 的共享 `HttpClient`、超时和重试规范；
4. evidence 成功/失败统计并入 metadata stage 结果，但不得改变核心导入提交成功语义；
5. 没有凭据时返回明确的 `provider_available=false` / retryable 状态，不伪造零缺口或删除旧 evidence。

现有 metadata 缺口选择不能直接代表本计划的缺口：已存在 `spotify_track_meta` 的曲目仍可能从未保存过 `artists[]`，因此必须建立独立 evidence coverage。

### 7.2 全库历史回填

新增显式命令行入口，例如 `scripts/backfill_spotify_track_artist_credits.py`，实际命名前再次核对项目脚本约定。要求：

- 默认 dry-run，只报告候选数、已有证据数、预计批次和缺少凭据状态；
- `--apply` 才联网并写 evidence；
- 支持 batch limit、resume cursor / run id、失败列表和机器可读 JSON 报告；
- 按稳定 Spotify track id 顺序推进，重复执行幂等；
- 不由页面 GET、应用启动或普通测试隐式触发；
- 正式数据库执行必须先做 Online Backup，并单独获得执行授权。

### 7.3 事务语义

- 对单个 provider batch，在同一数据库事务中保存现有 track metadata 与该批次所有合法 credit evidence；
- 单 track evidence 的父摘要、子行和 change event 必须原子更新；
- 采用 UPSERT 父行、显式删除并重插该 track 子集或等价的集合更新，不使用 `INSERT OR REPLACE`；
- 数据库异常时回滚当前事务，不能留下摘要与子表不一致；
- provider 的部分响应可按 track 拆分合法与失败项，但报告必须保存请求数、返回数、成功数、失败数和失败 id。

## 8. 身份解析与差异报告

### 8.1 解析顺序

对每个 eligible Spotify track：

1. 通过 `spotify_track_owners` 解析唯一 authoritative local owner；
2. 读取保存的有序 provider credits；
3. 对每个 Spotify artist id 查询 `artist_identity_external_ids`；
4. 对已解析本地艺人执行 canonical artist 投影；
5. 读取 owner 的 `get_effective_track_credits()` 结果并同样 canonicalize；
6. 比较成员集合、provider 顺序和解析状态；角色仅作为本地现状展示，不把 provider 顺序解释成角色。

名称精确归一化相同但无 external id 的项目只进入 `link_candidate` 辅助字段；它仍属于 unresolved，不计作确定匹配。

### 8.2 互斥主分类

每个 eligible Spotify track 必须落入且只落入以下一个主状态：

| 状态 | 定义 |
|---|---|
| `exact_member_match` | provider 全部艺人均解析，canonical 成员集合与当前有效署名一致 |
| `provider_additions` | provider 全部艺人均解析，且存在当前有效署名没有的成员 |
| `local_only_members` | provider 全部艺人均解析，且当前有效署名存在 provider 没有的成员 |
| `bidirectional_difference` | 两侧同时存在独有成员 |
| `unresolved_provider_artist` | 至少一个 Spotify artist id 尚未解析为唯一稳定本地艺人 |
| `artist_identity_conflict` | 同一 provider id 对应多个不一致本地/canonical 身份，或 resolver 无法唯一决定 |
| `owner_conflict` | Spotify track id 缺少唯一 authoritative owner，或 owner 约束损坏 |
| `provider_incomplete` | 没有合法上一可用 credit set，或最近响应结构不完整且从未成功保存 |

同时可以输出非互斥辅助标记，如 `order_differs`、`name_changed`、`has_link_candidate`、`latest_refresh_failed_but_lkg_available`，但不能破坏主分类守恒。

### 8.3 报告守恒

报告至少包含：

- eligible unique Spotify track ids；
- 各主分类数量，且总和等于 eligible 数；
- provider artist 总数、已解析数、未解析数、冲突数；
- evidence coverage、最新刷新成功/失败、使用上一可用证据数量；
- 受影响本地 owner 数、播放事件数和收听时长；
- 按歌曲列出的 provider credits、当前有效 credits、外部/本地稳定 ID、主分类和原因码；
- `generated_at`、数据库 revision / fingerprint、evidence run id 和脚本版本。

播放量和时长只用于离线影响评估，不得改变歌曲本身的播放事件数，也不得因多艺人 fan-out 重复累计全局总量。报告需同时给出去重 owner 总量与按艺人展开量，避免口径混淆。

## 9. 阶段实施计划

### A0：基线、合同与固定样本

**工作**

- 重新确认 schema migration 最大编号、现有 Spotify identity 约束、metadata stage 输出合同和真实数据库只读基线。
- 建立 Track API 固定 fixture：单艺人、双艺人、三艺人、名称变化、重复 id、空数组、缺失对象、批次部分 `null`。
- 用当前有效署名 resolver 固定一组比较案例，不访问网络。

**验证**

- fixture 不含真实 token；测试可完全离线运行。
- 明确同一 track 重复 artist id 的真实处理决策。
- 记录预期 migration id，但在 A1 落地前再检查并行变更。

**停止门**

若 `spotify_track_owners` 或 external id 唯一性无法支持确定 owner / artist 解析，先提交身份约束修复的独立方案，不带病进入回填。

### A1：additive migration 与 repository

**工作**

- 新增三张 Spotify evidence 表、索引、外键和 migration。
- 新增集中 repository / domain helper，负责校验、签名、原子 UPSERT、LKG 保留和事件写入。
- 提供按 Spotify track id 批量读取及 coverage 查询，禁止业务层拼装重复 SQL。

**验证**

- 空库迁移、从当前 schema 升级、重复 migrate、外键、唯一约束和 rollback 测试。
- 父行 UPSERT 不触发子行意外删除。
- 合法数组 round-trip 后顺序、id、name 和签名一致。

**停止门**

任一失败路径可能清空旧 evidence 或留下半套状态时，不进入 A2。

### A2：接入 Spotify metadata refresh

**工作**

- 在 `upsert_track_batch()` 附近引入经过校验的 credit persistence，但保持 provider client 与共享 `HttpClient` 约束。
- 对批次缺失、非法对象、token 缺失、HTTP 失败和数据库异常输出结构化结果。
- 保留现有本地主艺人 exact-name linkage 行为，但把它与“完整 credit evidence 已保存”分开统计。

**验证**

- 首次保存产生 `observed` event；相同数组重复刷新不产生新 event；顺序或成员变化产生单个 `changed` event。
- 坏响应保留 LKG；批次事务失败不出现摘要/子表不一致。
- 不写原始署名、override、metadata revision 或下游任务。

**停止门**

若接入改变现有 `refresh_missing_spotify_metadata()` 的凭据缺失/partial 语义，先修复回归再继续。

### A3：候选选择、回填与差异报告

**工作**

- 新增独立 evidence 缺口 selector，并接入 scoped candidates + bounded backlog。
- 实现 dry-run 默认的 resumable backfill 命令。
- 实现 owner / artist identity 解析和守恒差异报告。

**验证**

- selection 稳定、无重复、受 limit 约束；已有 `spotify_track_meta` 但无 credit set 的曲目会被选中。
- 中断后按 run/cursor 恢复不重复制造事件。
- 分类互斥且求和等于 eligible；identity / owner 冲突不会被名称匹配吞掉。
- 报告重跑在数据不变时语义等价，仅时间/run 元数据变化。

**停止门**

若报告不能守恒或影响量存在多艺人重复累计，禁止用它制定自动晋升规则。

### A4：导入阶段、健康与可观测性

**工作**

- 在 metadata stage 结果中增加 evidence requested / stored / LKG / failed / missing coverage 字段。
- 健康读取只消费已持久化状态；GET 不联网、不冷建、不返回虚假健康或虚假 0。
- 明确 `ready`、`warming/stale`、`unavailable`、`failed` 的映射，沿用当前导入健康规则。

**验证**

- 新导入优先处理 scoped ids，历史 backlog 有上限。
- provider 不可用时核心导入仍成功，metadata stage 明确 partial/retryable。
- 健康读取在 evidence 尚未回填时显示真实 missing，而不是 100% 或 0 个问题。

### A5：隔离真实数据/API 验收

**前置**

- 真实 Spotify API 仅通过命令级显式 opt-in；普通 pytest 不读取真实 token、真实数据库或用户目录。
- 对正式数据库先做 Online Backup 到 `/tmp`，记录备份 manifest、大小和 SHA；优先在隔离副本执行首次全量回填。

**执行**

1. 记录回填前 schema、原始表行数/摘要、evidence coverage 和 provider 候选数。
2. 先跑小样本，人工核对至少单艺人、已知合作、标题未写合作、同名/未解析和历史重复 owner 案例。
3. 执行完整隔离回填，保留每批 raw counters、失败 id 和运行报告。
4. 在完全相同数据上再运行一次，验证幂等。
5. 生成差异报告，并复核分类守恒、播放事件守恒和时长口径。
6. 回填后重新计算原始表摘要，确认正式事实未变化。

**通过标准**

- 所有合法成功响应均与持久化有序数组逐项一致；
- 所有失败项保留既有 LKG，没有旧证据被清空；
- 第二次运行没有新增 change event，除非 Spotify 响应实际变化；
- 主分类总和严格等于 eligible unique Spotify ids；
- `plays`、`tracks`、`track_artists`、track-credit overrides/events/state 的行数与内容摘要不变；
- 正式 track-credit revision 和下游构建队列不变；
- 无凭据路径仍保持可导入、可重试和可解释；
- 没有任何页面 GET 产生外部请求。

真实 API 的 provider 内容具有时间变化；验收报告必须保存获取时间和样本，不把两次不同时间返回的变化误判为本地非幂等。

### A6：规则、报告与阶段关闭

**工作**

- 更新 `docs/reference/music-metadata-management.md` 与 `docs/reference/data-import-and-health.md`，写入实际落地合同。
- 新增交付报告，记录 migration、代码路径、测试、真实样本、coverage、差异分布和仍未实现的晋升边界。
- 更新 `docs/README.md`；通过文档审计。

**关闭条件**

只有 A0—A5 证据齐全，才将本计划标为 `IMPLEMENTED`。完成 evidence 与报告后立即停止；自动晋升、审核 UI、第二来源和曲目语言进入新计划，不顺手扩展。

## 10. 预计修改面

以下是规划时的预计位置，实施时应先通过 `rg` 重新确认真实调用链：

| 范围 | 预计文件 |
|---|---|
| schema / migration | `backend/core/db.py`、`backend/core/migrations.py` |
| evidence domain / repository | 新增 `backend/domains/metadata/spotify_track_credits.py` 或遵循届时目录约定的等价文件 |
| Spotify refresh | `backend/domains/metadata/spotify_refresh.py` |
| import stage / maintenance | `backend/services/import_stage_service.py`、`backend/services/import_maintenance_service.py` |
| health / response models | 现有导入健康相关 service、schema 与测试；具体位置实施前检索 |
| 回填与审计 | 新增 `scripts/backfill_spotify_track_artist_credits.py`、`scripts/audit_spotify_track_credits.py` 或合并为一个职责清晰的命令 |
| 单元/合同测试 | `backend/tests/unit/test_spotify_metadata_refresh.py`、migration、import maintenance、health、credit comparison 相关测试 |
| 文档 | 两份当前 reference、交付报告和文档地图 |

不预计修改前端。若后续要求展示候选或审核，必须先定义权限、普通用户可见语义和移动端交互，再开独立阶段。

## 11. 测试矩阵

### 11.1 schema / repository

- migration from current schema、fresh DB、重复 migrate；
- 外键与唯一约束；
- 有序 round-trip；
- 重复 artist id、重复 order、空数组、空 id/name；
- UPSERT 不触发 cascade；
- 首次 event、无变化、成员变化、顺序变化、名称变化；
- 事务失败回滚和 LKG 保留。

### 11.2 refresh / provider failure

- 单 track、多 track、批次部分 null、返回 id 不匹配；
- HTTP timeout、401/429/5xx、token 缺失；
- track metadata 成功但 credit 非法时的原子策略；
- scoped targets、bounded backlog、limit 和稳定顺序；
- 已有 metadata 但缺 evidence 的重新选择；
- 重跑幂等与事件数量。

### 11.3 identity / comparison

- provider id 唯一解析；
- unresolved、同名不同人、一个 provider id 多个本地候选、canonical alias 重叠；
- authoritative owner 缺失/冲突；
- exact、单向新增、单向本地独有、双向差异；
- 顺序变化不被误判为角色变化；
- 分类守恒、播放事件守恒、时长展开口径；
- 名称候选不自动变成确定匹配。

### 11.4 不变性回归

- 原始 `plays` / `tracks` / `track_artists` 不变；
- override / audit / metadata revision 不变；
- 不创建统计或搜索 rebuild job；
- 无 Spotify 凭据时导入仍按现有合同完成；
- GET 请求不调用 provider。

### 11.5 项目门禁

实现阶段至少运行相关 unit、migration 和 contract 测试，再按影响决定是否运行完整：

```bash
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
python3 scripts/docs_audit.py
```

局部测试只能标记 Partial。只有项目默认完整 fullstack 门禁全部通过，才可另行声明本地全栈 Pass；本计划本身不要求以 UI 变化冒充完成证据。

## 12. 发布与回滚

### 12.1 发布

- migration 只新增表、索引和读取路径，旧版本代码忽略新表；
- 首次生产写入前在隔离副本完成全量回填和二次幂等验收；
- 先发布 schema / dormant reader，再显式开启 scoped refresh，最后才安排独立全量回填；
- 每一步保留 commit SHA、数据库备份、健康结果和可回滚开关。

### 12.2 回滚

- 关闭 evidence 写入/读取和 backlog 调度即可恢复旧行为；
- 保留新增 evidence 表用于审计，不在紧急回滚中 DROP 表或删除事件；
- 因本计划不修改正式署名，回滚不应要求恢复 `plays`、`tracks`、`track_artists` 或统计快照；
- 若 migration 或事务违反不变性，使用发布前 Online Backup 恢复，并将本阶段判为失败，不继续回填。

## 13. 风险与控制

| 风险 | 控制 |
|---|---|
| 把数组顺序误当角色 | schema 只保存 order；报告不推断 primary/featured |
| 名称匹配误合并同名艺人 | external id 优先；名称仅候选；首轮不自动创建/合并 |
| Spotify id 与历史本地重复 owner | 只用 `spotify_track_owners`；冲突单列并停止自动比较 |
| 坏响应清空旧证据 | 严格校验；LKG；原子事务；失败注入测试 |
| 重复刷新制造事件膨胀 | 稳定 signature；无变化只更新时间 |
| 回填占用 provider 配额或拖慢导入 | 显式命令、批次 50、bounded backlog、resume、速率与错误报告 |
| 没有凭据导致导入失败 | 保持 retryable partial；核心导入不依赖 evidence 完成 |
| evidence 被误解为正式事实 | 表名、API 和文档明确 provider evidence；不接入有效署名 resolver |
| 并行 schema 迁移冲突 | 实施前重查最大 migration id；精确修改，不覆盖其他工作 |

## 14. 交付清单与最终停止线

完成时应交付：

- additive migration 与 schema 合同；
- Spotify Track `artists[]` 校验、持久化和 LKG；
- scoped refresh、bounded backlog、dry-run/resumable backfill；
- 守恒差异报告；
- unit / contract / migration / failure tests；
- 隔离真实数据库与显式真实 API 验收报告；
- 当前参考规则与文档地图更新。

本计划的最终停止线是“证据完整、回填幂等、差异可量化”。下列动作必须另行规划和授权：

- 把 Spotify evidence 自动写成正式合作艺人；
- 为候选增加管理员审核 UI；
- 接入 MusicBrainz / Apple Music；
- 建立 track-level language；
- 重新计算并发布受署名变化影响的搜索、排行、年度总结或 Billboard 结果。

## 15. 依赖文档与交付证据

- [Spotify Track `artists[]` 证据交付与隔离验收报告](../../reports/2026-09-24-spotify-track-artists-evidence-delivery.md)
- [多源音乐元数据后续路线记录](../../plans/2026-09-23-multi-source-music-metadata-roadmap.md)
- [音乐元数据管理规则](../../reference/music-metadata-management.md)
- [数据导入与健康规则](../../reference/data-import-and-health.md)
- [艺人语言事实与统计规则](../../reference/artist-language-statistics.md)
- [音乐搜索零停机与元数据 delta 历史计划](2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md)
