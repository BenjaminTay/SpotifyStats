# 阶段 0.5：旧数据库身份索引一致性修复

> 2026-09-19；HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty；阶段 0/1 未提交实现作为基线保留。
> **Partial：索引实现、语义对账与局部性能验证完成；存在下述测试 sidecar 越界，不能声明满足全部数据安全验收。**

> 后续状态：本次事故已完成单独安全收口，见 [重新生成快照与测试隔离报告](2026-09-19-billboard-sidecar-safety-closeout.md)。以下保留事故发生时的原始记录与阶段 0.5 性能结论。

## 必须披露的测试副作用

第一次定向测试运行漏设 `SPOTIFY_STATS_BILLBOARD_CACHE_PATH`。既有 `test_billboard_counting_consistency.py::_clear_billboard_runtime_caches()` 调用 `clear_persisted_snapshots()`，对正式本地 `data/billboard_cache.db` 执行了清理，后续测试又可能发布测试 namespace 的快照。发现时该表为 **1 行**；未记录测试前行数，无法确认被删除的原快照数量。这是本轮执行错误，不是索引 migration 的行为。

发现后未再修改该正式 sidecar，也未擅自用历史副本恢复。后续定向回归显式绑定 `/tmp/spotifystats-stage05/test-billboard.db` 与 `test-yearly.db`。正式 `data/spotify_stats.db` 没有作为 migration、服务、测试或性能测量的写入目标；数据库测试源为 seed，测量源为历史 Online Backup 副本。该事件不应被“测试通过”或下列性能改善掩盖。事件证据为 `sidecar-test-boundary-incident.json`。

## 根因、语义与实现

`backend/core/db.py` 的主播放和 artist loader 都先取播放时 Spotify ID，再退到 source track 的 Spotify ID；`track_l1_external_ids` 的有效 owner 优先。仅在 Spotify token 不存在时连接未 superseded 的 fallback identity。`provider` 是兼容投影属性，不是所有历史 fallback 都必须为 local 的证明。

当前 SCHEMA 与 migration 48 对所有非空 `fallback_track_id` 要求全局唯一，含非 local / superseded 行。`track_identity._refresh_representatives()`、`_ensure_compat_track_identity()`、external owner 和 source link 路径也不支持为性能而删除该兼容查询语义。旧库同名索引只覆盖 `provider='local'`；`CREATE INDEX IF NOT EXISTS` 不会修复其实际谓词，JOIN 又不蕴含旧谓词，故逐行 `SCAN li_local`。

本轮仅新增 **migration 74**：读取实际 DDL，正确定义不重建；替换前检查重复 fallback；SAVEPOINT 包含检查和 DDL；显式外层事务将 runner 的版本账本与 DDL 一起提交。重复、创建失败或账本失败均不留缺失索引；同名索引若属于别表则拒绝操作。不改 JOIN，不用 INDEXED BY，不改变原始事实或触发重建。细则见 [迁移参考](../reference/track-identity-index-migration.md)。

真实副本迁移前：

```sql
CREATE UNIQUE INDEX idx_track_l1_local_identity
ON track_l1_identities(fallback_track_id)
WHERE provider='local';
```

迁移后与新建 SCHEMA、seed 一致：

```sql
CREATE UNIQUE INDEX idx_track_l1_local_identity
ON track_l1_identities(fallback_track_id)
WHERE fallback_track_id IS NOT NULL;
```

## 数据核对与安全性

| 检查 | seed | Online Backup |
|---|---:|---:|
| plays | 117 | 92,908 |
| local / active 身份 | 32 | 6,828 |
| local / superseded 身份 | 0 | 2,721 |
| 重复非空 fallback 组 | 0 | 0 |
| 非 local 且 fallback 非空 | 0 | 0 |
| 关联多个 external ID 的身份 | 0 | 817 |
| 指向 superseded 的 external ID | 0 | 0 |

真实副本 external evidence：provider_observed 6,794、migration 1,047、manual_confirmed 2，provider_relink 0；source links：play_at_time 6,833、track_projection 9,549；Spotify owners：play_majority 7,838、manual_override 5。完整表结构与索引 DDL 在 `before-inventory.json`，没有输出歌曲名、艺人名或播放明细。

真实数据没有非 local fallback / provider_relink 样本，因此另以最小 fixture 覆盖：local fallback、非 local fallback、播放时 external owner 优先于 catalog token、relink 新 owner / 已 superseded 旧 owner、一身份多 external ID、superseded fallback 排除。相同实际查询在旧/新索引下逐行逐字段相同。

迁移故障测试覆盖 active 和 superseded 重复 fallback，拒绝后旧唯一索引仍执行约束；模拟 CREATE 失败恢复索引和 schema cookie；外层事务 rollback 恢复旧定义；模拟 runner 写版本账本失败同时回滚索引且不记录 74。正确 DDL 重复执行不发出 DROP/CREATE，schema cookie 不变。seed 只新增 migration 74 账本记录，播放 fixture 未重建。

## 全字段对账与查询计划

同一 Online Backup 再生成独立 before/after 副本；只有 after 应用 migration 74。两个数据集各 **124 张业务表**（除迁移账本）全部按主键或 rowid 比较，所有字段与行均一致，包括 plays/tracks/track_artists、identity/external/source links/owners、L2/L3/专辑项目与 revision 表。

实际 SQL 从运行中的 `pd.read_sql_query` 调用捕获，不手写替代查询；比较字段、行顺序、`l1_id`、`resolved_track_id`、`source_track_id`，无差异。完整 loader 结果另外比较所有字段、顺序、dtype，以及 attrs 引用内的真实 listening-duration / Billboard-weighted DataFrame；不把不同 Python 引用对象的 identity equality 当成事实差异。

| 数据集 | SQL 行数（主 / artist / Billboard raw） | 完整主 loader | 完整 artist loader | Billboard raw |
| seed | 115 / 115 / 115 | 119 | 121 | 119 |
| real | 92568 / 92568 / 92568 | 66,436 | 70,826 | 66,436 |

主/artist 的时长帧与 Billboard 加权帧同样全字段完全一致。SQL 的 music-only 行数小于 plays 总数是原查询过滤结果，未删除事实。seed 完整事件数可能多于 SQL 行数，沿用原逻辑事件切分语义。

Search 的 `_load_filtered_search_frames()` 复用基础主/artist loader；不重复同类 SQL 测试。Billboard `load_billboard_raw()` 通过 `_track_identity_sql()` 生成同语义 JOIN，SELECT 投影不同，因此单独捕获、EXPLAIN 和计时。公开快照 GET 不应该为了此验证冷建；本轮的 Billboard 读取测量在副本中直接调用真实 raw loader，不执行榜单排行、全套重建或 Search 多变体重建。

seed 原索引已正确，迁移前后均 SEARCH。真实副本三个查询均由 SCAN 改为目标索引 SEARCH。`semantic-reconciliation.json` 包含 seed/real、before/after 的完整 plan 节点和列名；`queries.json` 保存实际 SQL 及绑定参数。以下列出真实副本全部相关 plan 节点：

### main

before：

```text
15 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
20 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
25 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
43 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
51 | 0 | 216 | SCAN li_local LEFT-JOIN
71 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
80 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
85 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
90 | 0 | 45 | SEARCH al_src USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
95 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

after：

```text
16 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
21 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
26 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
44 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
52 | 0 | 45 | SEARCH li_local USING INDEX idx_track_l1_local_identity (fallback_track_id=?) LEFT-JOIN
74 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
83 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
88 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
93 | 0 | 45 | SEARCH al_src USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
98 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

### artist

before：

```text
14 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
19 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
24 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
42 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
50 | 0 | 216 | SCAN li_local LEFT-JOIN
70 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
79 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
84 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
89 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

after：

```text
15 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
20 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
25 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
43 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
51 | 0 | 45 | SEARCH li_local USING INDEX idx_track_l1_local_identity (fallback_track_id=?) LEFT-JOIN
73 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
82 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
87 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
92 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

### billboard_raw

before：

```text
15 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
20 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
25 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
43 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
51 | 0 | 216 | SCAN li_local LEFT-JOIN
71 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
80 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
85 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
90 | 0 | 45 | SEARCH al_src USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
95 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

after：

```text
16 | 0 | 223 | SCAN p USING INDEX idx_plays_ts
21 | 0 | 45 | SEARCH t_source USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
26 | 0 | 47 | SEARCH external_spotify USING INDEX sqlite_autoindex_track_l1_external_ids_1 (provider=? AND external_track_id=?) LEFT-JOIN
44 | 0 | 45 | SEARCH li_spotify USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
52 | 0 | 45 | SEARCH li_local USING INDEX idx_track_l1_local_identity (fallback_track_id=?) LEFT-JOIN
74 | 0 | 45 | SEARCH t USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
83 | 0 | 45 | SEARCH a USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
88 | 0 | 45 | SEARCH al USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
93 | 0 | 45 | SEARCH al_src USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
98 | 0 | 46 | SEARCH stm USING INDEX sqlite_autoindex_spotify_track_meta_1 (spotify_track_id=?) LEFT-JOIN
```

## 独立进程性能复测

使用阶段 0 `performance_contract` 的 metadata/sample/request/report/statistics 和 owned server；机器 schema 校验通过。每个操作 before/after 各 3 个新进程，共 24 个样本；全部保留，没有重试、删慢样本或 profiler。before/after 顺序逐轮交错，同一机器、同一 loader/API 代码；正式计时期间未并行跑测试。process cold 不等于清空 OS 文件缓存，未执行系统缓存清理。

所有 loader 为 min_ms=30000、music_only=true、merge_enabled=true、dynamic_threshold=false、gap=5；Billboard 周界 4 / 0。API 显式提交对应五个过滤参数，默认全期，public-readonly，120s 原 timeout。此前阶段 0 的 24.8s 是不同观测条件的单样本，不能与本表直接计算收益。

SQL 行为是 execute+fetchall；Billboard 包括真实 raw DataFrame 与周/时长处理。API 计时覆盖真实本地 HTTP/gzip；API 内 SQL 子阶段未做产品埋点，不把单独 SQL 计时伪装成该请求 trace。快照状态均为 not_applicable；内部 builder/singleflight 计数未暴露。每个样本保存 DB 身份、revision/schema fingerprint、PID、参数、机器 load、时间与 50ms RSS 序列；schema fingerprint 因索引 DDL 改变不同，事实相同由上述全表对账证明。

单位 ms；每格样本按 replicate 1/2/3 排列。各组成功 3、失败 0；只报告 observed values，P95=null。

| 操作 | before 原始样本 | after 原始样本 | before median | after median | 中位耗时下降 |
| main_sql | 19134.89, 19416.42, 19740.95 | 755.09, 682.20, 758.03 | 19416.42 | 755.09 | 96.11% |
| artist_sql | 19078.56, 19055.09, 20825.65 | 627.03, 370.76, 732.53 | 19078.56 | 627.03 | 96.71% |
| billboard_raw | 29270.52, 37365.97, 38020.56 | 4134.20, 4402.31, 4300.41 | 37365.97 | 4300.41 | 88.49% |
| analysis_stats | 40024.38, 42896.13, 38210.31 | 11276.99, 10360.03, 10041.58 | 40024.38 | 10360.03 | 74.12% |

| 操作 | before min / max | after min / max | before peak RSS（MiB，逐样本） | after peak RSS（MiB，逐样本） | 行数 / HTTP |
|---|---|---|---|---|---|
| main_sql | 19134.89 / 19740.95 | 682.20 / 758.03 | 237.4, 237.6, 237.4 | 237.3, 237.5, 237.1 | 92,568；HTTP 不适用 |
| artist_sql | 19055.09 / 20825.65 | 370.76 / 732.53 | 225.5, 225.0, 225.5 | 224.9, 224.9, 225.0 | 92,568；HTTP 不适用 |
| billboard_raw | 29270.52 / 38020.56 | 4134.20 / 4402.31 | 430.8, 424.8, 422.8 | 429.8, 427.4, 429.2 | 66,436；HTTP 不适用 |
| analysis_stats | 38210.31 / 42896.13 | 10041.58 / 11276.99 | 1861.2, 2001.0, 1820.2 | 1842.0, 2004.2, 1974.2 | 汇总对象，输入 92,908；6 次 HTTP 200 |

API 实际传输大小（各 replicate；raw / gzip bytes）：

- before 1：205,638 / 34,055。
- before 2：205,638 / 34,055。
- before 3：205,638 / 34,055。
- after 1：205,638 / 34,055。
- after 2：205,638 / 34,055。
- after 3：205,638 / 34,055。

RSS 是完整操作窗口的采样峰值：SQL/raw 测自身工作进程，API 测拥有的 backend 进程树，不混入 HTTP 客户端。进程导入和服务健康检查在业务计时前，计时本身没有 warmup 业务请求。index 缩短扫描时间，没有显著降低存储宽 DataFrame 的峰值内存；该结论不能替代生产 SLA。

## 文件、验证与停止点

本轮新增/修改 8 个路径：

- `backend/core/migrations.py`：schema 74 与显式原子索引修复。
- `backend/tests/unit/test_track_identity_index_migration.py`：11 个迁移/身份/实际查询计划回归用例。
- `backend/tests/unit/test_music_search_incremental_migration.py`：当前版本断言 73 → 74。
- `backend/tests/fixtures/seed.db`：仅版本账本同步。
- 本报告、`docs/reference/track-identity-index-migration.md`、`docs/README.md`、`docs/CHANGELOG.md`。

显式临时 sidecar 的最终定向回归 **209 passed（30.00s，2 条既有环境/弃用 warning）**，见 `isolated-targeted-tests.log`；覆盖 migration、identity/relink/superseded、主/artist/Billboard 查询计划、analysis/Search/Billboard、L2/L3、双轨时长及 seed schema 一致性。Python Ruff / py_compile、统一报告 schema 校验、文档审计（95 文件）与 `git diff --check` 全部通过，记录在证据目录。隔离重跑前后正式 sidecar 的 mtime 和行数保持不变，见 `scope-and-boundary.json`。阶段 0/1 已有产品和探针文件保留；共享文档只追加阶段 0.5 内容。未运行默认完整全栈门禁，结论 Partial。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage05`。包含全字段对账的安全摘要、DDL/完整查询计划、24 条原始性能样本与 RSS 序列、一次性 harness、测试及检查日志和 sidecar 越界事件。数据库副本只留在 `/tmp/spotifystats-stage05`，未放入仓库或报告目录。

## 后续阶段决策

- **阶段 2 仍有独立依据**：此前审计确认 Records/Weekly 大响应与前端请求组织问题；索引修复不改变 payload 或请求图。本轮不声称重新测过这些页面。
- **阶段 3 对 stats 有继续评估的充分依据**：本轮 after 独立进程仍为 10.04–11.28s，peak RSS 1.8–2.0GiB。基础 SQL 已降到亚秒，后续逻辑事件/时长帧、artist fan-out 和统计聚合仍占用成本；没有 profiler，不能给这些阶段各自的精确占比。Records/其他 family 应先按新索引基线校准，不能继续拿旧 24–43s 自动决定全部缓存方案。
- 本轮到此停止；不实施阶段 2–7，不改请求组织、缓存、重建算法、统计规则或生产。未 commit、push 或部署。由于已披露的正式 sidecar 测试副作用，不将“代码与测量完成”表述为全项安全验收通过。
