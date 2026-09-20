# 阶段 5C：Search 真实 delta 可达性与 identity revision 精度

> 2026-09-20，本地隔离副本验收。Search 阶段 5：**Pass**。两个已知范围外 analysis GET 503 不计为 Search 新增回归；可以另开阶段 6，本任务未开始阶段 6。

## 逐实体根因

原 5B 的真实追加同时包含真实候选变化与 no-op revision churn，不能只选其一解释。

| 原场景 | projection 调用的无效 bump | source link 新增导致的有效 bump | revision |
|---|---:|---:|---|
| 同周 25 条 | 25 | 1 | 185100 → 185126 |
| 跨周 24 条 | 24 | 1 | 185126 → 185151 |

同周新增 `play_at_time` 关系为 track 49213（菊花台）、49214（陽光宅男）、49215（牛仔很忙），候选因此增加 6 个 L2/L3 文档；跨周新增 49216（彩虹）、49217（蒲公英的約定）、49218（無雙）、49219（我不配）、49220（扯）、49221（甜甜的），增加 12 个候选文档。对应 `track_albums` 观察关系分别新增 3/6 行。已有 provider owner、canonical work/group、Album Project membership、artist credit 没有身份内容变化。原两次追加必须保留 shared-full 回退。

`ensure_track_projection_identity` 通过 `conn.total_changes` 判定变化，但 `_ensure_compat_track_identity` 无条件 UPDATE，provider external alias UPSERT 也会写回相同字段和 updated_at。原同周/跨周分别因此多 bump 25/24 次。结束时刷新 source links，只因新增上述映射各 bump 一次；既有链接 observed_plays/last_seen_at 更新不构成身份变化。原 9,549 个 compatibility identity 行的 updated_at，以及 6,798/6,795 个 alias 行的 updated_at 变化，逐实体保存在外部证据；不是 9,549 个身份发生改变。

## 修复范围

- identity 两处 SQL 添加 NULL-safe 实际字段变化条件，相同值影响 0 行。保留已有 revision 类型、生产者和所有消费者语义，没有 schema/migration。
- candidate builder 在发布写锁和来源 fence 之后复用完整内容相同、tokenizer/normalization 相同的 active generation；内容改变仍切换 generation，旧 generation 与全部发布 fence 保留。
- 正常 Search 维护入口在完整 base dependency 证明成立时复用当前 attribution，省去播放历史全量聚合。delta 内部继续重查全部 fence。
- 跨周真实读取暴露 `_rows_share_merge_run` 所需 `l1_id` 缺失；周闭包改为复用 full 的 canonical SQL，并显式提供同一身份字段。真实 SQLite 测试覆盖前后边界、provider alias 与 legacy schema。

## 真实输入与正常发布

基线复用 5B 正式 importer 生成的 92,859 条真实前缀及正常 shared-full 成品。新的累计输入只从原始 Streaming History 尾部选取基线已有播放 provider identity 的记录：同周追加 22 条至 92,881；跨一周再追加 16 条至 92,897。未选的 11 条涉及基线未激活曲目。全部原始记录和所属文件、选择清单、正式 planner、importer 与 ChangeSet 证据保存在隔离目录。

同周开放周为 2026-08-14 → 2026-08-14；跨周为 2026-08-14 → 2026-08-21。正式 planner 判定 incremental / snapshot_superset；由 importer 生成新的 source fingerprint、generation、dataset digest，经正式 aggregation 和 `rebuild_current_music_search_derived_data` 发布四变体。没有直接调用内部 delta builder 作为真实发布入口。

## 逐字段依赖与 lineage

两条合法追加的 track identity revision 均保持 **185100**；Album Project 数值 revision 为 **7**（语义摘要 `d0848ef87f97e1257d27`），credit revision **37**。candidate generation、完整文档内容及摘要完全不变。所有 track/provider owner、canonical L2/L3 group key、Album Project membership、artist credit 字段均相等；同周 22 个、跨周 15 个已有 play source link 仅 observed_plays/last_seen_at 改变。聚合的 identity/credit 时间记账更新不改变 revision，agg_config 仅 data_generation_id/source_dataset_digest 更新。

Search dependency digest 全程为 `0283770e30565ced90290d1bf6eed64c5dfba2d226c37cf960c16f2cda35eeb6`。

| 状态 | source generation | dataset digest |
|---|---|---|
| base | `99f05f38-982e-493c-a234-c22e93ef8467` | `67bebac9d60089c974266d4d7f18f33951136b46a48f0277b7d7b0ceb7e338f9` |
| 同周 | `3479e5c7-dc79-4bef-be55-11d5fa7a18de` | `4bbc254d26b434019b380ef0492e2975ca313450f02eb6be731697257170f257` |
| 跨周 | `b9858f4b-a3d4-47c9-ae9a-a036a49dd91d` | `1f893a29ac0f1774427f05926a9de5a09a1c7c63937e2fd7367e128c7fff5939` |

`prepare.py` 的 importer finalizer 构建真实 ChangeSet 并发布实际落库摘要，Search plan 当场保存。初次脚本未将完整 ChangeSet 序列化；随后使用不变 base、累计输入与实际 generation 行，通过同一个正式 builder 只读恢复完整 ChangeSet，确认所生成 Search plan 与原文件逐字段相等，见 `delta-*-changeset-replay.json`。没有修改任何 lineage/revision/digest 来取得兼容。另一次完整记录 finalizer 输出的独立 importer 复验保存在 `final-same-proof.json`，不与原 generation 的性能样本混用。

逐实体明细为 `old-*-diff.json`、`trace-old-*.json`、`root-cause-summary.json`、`*-identity-diff.json` 与 `dependency-proof.json`。这些文件保留所有改变字段、实体 ID、前后值；摘要未替代逐实体证据。

## 四变体发布与完整对账

两类正常维护入口均返回 `incremental_snapshot_delta`，没有 delta_fallback_reason，四个 active 一次事务切换。持久 build_strategy 为 schema 已支持的 `delta`，原 base_snapshot_key/change_set_digest 保留；维护报告 chart_strategy 分别为 `clone_unchanged_open_week` / `replace_affected_completed_weeks`，明确区分实际类型。

独立 corrected full 在相同最终数据库、候选与依赖状态上重建；每个最终性能进程又分别与 corrected full、同状态 shared-full 对账，共 12 组最终比较。

| 场景 | context（L2 D/F；L3 D/F） | weekly ledger（L2 D/F；L3 D/F） | Year-End entity/meta 合计 |
|---|---|---|---|
| 同周 | 9297 / 9297；8795 / 8795 | 14995 / 14995；15004 / 15004 | 2200 / 20 |
| 跨一周 | 9297 / 9297；8795 / 8795 | 15065 / 15065；15074 / 15074 | 2200 / 20 |

context 的全部公开字段、weekly ledger 全字段、Year-End entity/meta 全字段及完整顺序全部一致。filter fingerprint、source revision、semantic base、dependency digest、source generation/dataset digest、candidate generation、policy key、builder version 全相等。created_at/activated_at、base_snapshot_key、build_strategy、change_set_digest 的真实差异逐项记录在 metadata_all_differences；只按对应变体关联 snapshot_key，不删除统计字段来制造等价。

## 性能与工作量

每类至少三对独立进程，delta/shared-full 交错运行。计时覆盖正常维护入口直到 Year-End 完成；importer、聚合预维护与模块加载在计时外。每个样本独立数据库/缓存目录，最终测量期间没有并行运行回归或 full 参考构建。CPU 为进程 CPU；RSS 取采样与进程高水位的较大值，高水位还保守包含后续 payload 导出。SQL 调用与返回行、DataFrame copy 和嵌套阶段事件完整保存，copy 行数表示逻辑复制量。

| 场景 | delta wall 中位数 | shared-full wall 中位数 | 降低 | CPU 中位数 delta / shared-full | 最大 RSS delta / shared-full |
|---|---:|---:|---:|---:|---:|
| 同周 | 3.922 s | 42.676 s | **90.81%** | 3.733 / 40.806 s | **502.02** / 741.08 MiB |
| 跨一周 | 7.879 s | 37.588 s | **79.04%** | 7.717 / 35.647 s | **504.25** / 751.66 MiB |

同周原始 wall 配对为 4.596/44.600、3.922/42.676、3.738/40.924 s；跨周为 9.438/43.368、7.408/36.962、7.879/37.588 s。跨周最终使用编号 3/4/5；1/2 属于键集查询修复前诊断，完整保留但未混入最终统计。没有删除最终版本的较慢样本。

| 维护内工作量 | 同周 delta / shared-full | 跨周 delta / shared-full |
|---|---:|---:|
| SQL 批调用 | 613 / 13140 | 855 / 13140 |
| SQL 返回行（含已发布上下文/账本） | 398284 / 942430 | 658267 / 942589 |
| DataFrame copy 次数 | 1260 / 4002 | 6346 / 4018 |
| copy 累计行 | 1177994 / 17548177 | 1847016 / 17584623 |
| lifetime/shared-full loader | **0 / 4** | **0 / 4** |
| tail 贡献闭包（每阈值） | 22 raw → 18 logical | 16 raw → 15 logical |
| 完整周 raw 闭包 | 无 | 361 行，1 个完整周 |

同周 delta 核心/Year-End 阶段 wall 中位数 1.653/2.065 s；跨周 6.212/1.668 s，其中完整周替换 0.545 s。shared-full loader/metric/chart/publish 中位数分别为同周 8.024/1.347/21.798/3.388 s、跨周 7.168/1.222/18.321/3.631 s；阶段有嵌套，不能相加代替 wall。

播放事实读取仅按真实 generation 索引、周时间范围和有界相邻页进行。查询计划确认周范围及两端 seek 使用 idx_plays_ts；既有 importer 尾部前驱证明使用时间索引倒序 LIMIT 256，从最新尾部取有界页，并非读取 lifetime 帧。没有完整 plays 聚合或 shared-full loader。delta 仍读取已有 compact context/weekly ledger 来维护全局 Power 与完整 Year-End；其工作量包含已发布事实规模，不宣称所有操作只随新增行数线性增长。原始播放重建闭包为 22/16/361 行，不随整个 92,897 条最终播放历史重扫。

## 并发、LKG、失败与重启

- 两类场景各四个连接并发调用正常维护入口，只有一次 delta 构建（两个阈值各一次贡献加载），四个调用都 ready；构建期间旧四套 active LKG 可读。
- 两类场景第四变体 INSERT 注入失败，delta 事务完整回滚，四个旧 active 全部保留。
- 设置/旧任务、track identity、Album Project、credit、实际 candidate 内容改变分别触发语义、attribution 或 candidate fence；原 old active 保留。identity 修正复验使用真实 alias 注册 helper；初轮 harness 误取 NULL track_id 的失败不计为 fence 证据，保留日志并由 corrected 结果替代。
- 源代际竞争通过正式 importer 再追加真实 cross 输入，旧构建被 `playback generation changed` 拒绝。故障矩阵同时注入 full fallback 不可用，以隔离验证失败任务不能用后续成功 full 发布掩盖旧 active 是否保留；正常无故障发布及对账均未禁用 fallback。
- 旧 Job 携带旧 base key/旧 plan，在已有新跨周 ready 成品上经正式 handler 执行，0 构建，所有核心、账本、Year-End、候选及 active 行原样保留。
- 独立进程重启复用同周/跨周成品：ready，0 lifetime loader、0 delta/full、0 publish、0 Year-End rebuild；只执行轻量 Year-End ensure。

## Search GET 与回归门禁

五状态 ready/warming/LKG/failed/unavailable × private-admin/public-readonly × candidates/context，各预热一次再测 30 次，共 **600 个计时 GET，全部 200**。warming 和 failed-LKG 保留真实实体事实，unavailable 返回空统计；无冷建、Billboard、发布、排队、plays/agg_weekly SQL。SQLite authorizer 拒绝写入，探针 DB/WAL 内容和 mtime 不变。GET 同时运行在回归压力下，候选最高 P95 323.78 ms，不将该探针当作独占延迟基准。

- revision、candidate、同周/跨周、shared-full/invocation、lineage 定向：155 passed；最终 SQL seek 另由完整 unit 验证。
- 最终完整 backend unit：**1832 passed**。
- 最终完整 contract：**434 passed，2 个已知 analysis GET 503 失败**（`test_api_boundary_probe`、`test_safe_readonly_api_smoke_probe`）；与初轮及 5B 既有失败相同，没有新增失败。测试日志还保留原有隔离任务清理期间的线程警告，不修改范围外分析/AI task 路径。
- backend Ruff、compile、docs audit、git diff --check 通过。全 scripts Ruff 的 11 个既有错误保留，相关文件本轮 SHA 不变。

## 范围与结论

正式 `data/` 前后均为 **4183 个文件**，size/SHA 全同，没有新增或删除；正式数据库、缓存、设置、导入状态未修改。相对开始时逐文件 SHA，仅 15 个授权源码/测试/文档文件改变，范围外 dirty 文件变化 **0**；既有 schema/migrations 与 snapshot_lineage fence 文件均保持原 SHA。初始及最终 git status、SHA 清单、HEAD、差异白名单保存在证据目录。未 git add、commit、push、部署。

**Search 阶段 5 最终为 Pass**：两条真实 delta 均通过正式 importer/planner/正常维护入口原子发布，与 corrected full 全字段和顺序一致，性能、RSS、无 lifetime 播放重扫、完整 Year-End、LKG/fence/失败回滚/重启和 Search 读取门禁均通过，没有新增回归。完整仓库 contract 仍有上述两项既有范围外失败，不能把这个 Search 独立结论写成整个仓库全绿。

可以开始单独的阶段 6；本任务没有实施阶段 6。

证据工作目录：`/tmp/spotifystats-phase5c-20260920-121341/`。真实输入、数据库、逐实体 payload 不进入 Git。

长期证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bd04-aab8-7073-aa25-fb2ba6fee97b/spotifystats-phase5c/`。入口 `acceptance-summary.json`；性能见 `performance-summary.json`，恢复见 `recovery-results.json` / `recovery-source.json` / `stale-job.json`，只读探针见 `public-probe-after.json`，范围见 `scope-audit.json`。脚本、全部诊断失败与最终门禁日志一并保留；数据库和真实累计输入仍位于隔离工作目录，不进入 Git。
