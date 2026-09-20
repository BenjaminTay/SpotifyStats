# 阶段 5B：Search shared-full 统计合同与真实 lineage

> 2026-09-20。已按用户裁定修正稳定 Album Project 身份与 Power 排名，修正后的 full / invocation_full 为基线。阶段 5 结论为 **Partial**，暂不进入阶段 6；不再等待统计合同决策。真实规模 shared-full 已完成等价对账；真实追加均因实际 identity revision 漂移安全回退，尚不能宣称真实 delta 发布通过。

## 1. 根因与修复

播放次数和收听时长继续遵守[双轨统计规则](../reference/playback-stats-rules.md)。三个差异有独立根因：

1. **duration-only**：shared-full 已通过共享 lifetime metrics 得到完整实体全集，随后却用 Top-N weekly ledger 重新构造 context。ledger reducer 的保留条件只有正次数或 chart，漏掉 `play_events=0、total_ms>0`。同周 delta 的 clone/apply 和跨周 delta 的 ledger reducer 也使用该错误条件。
2. **Power 排名**：full 的 `_sorted_power_frame` 对已有稳定 `power_rank` 再按 `power_score` 排序，以 pandas 默认 quicksort 和新索引排名；这会打乱同分顺序。旧 ledger reducer 为避免合并同名不同 ID，用数字身份代替名称聚合，但又将替代名称用于最终 tie-breaker。它与正式 Power builder 的完整排序不一致。duration-only 实体本身没有榜单排名，不能用补齐这些实体解释全部 4,740 处 rank 差异。
3. **L3 Album Project chart summary**：full 原来按 `(album_name, artist display name)` 匹配。候选 canonical artist 显示 `Jolin Tsai`，对应 weekly facts 显示 `JOLIN`，同一个稳定 Album Project 被误判为无成绩。

用户已批准第 3 项修正。以下事实保持，Search 不再将其清空：

| Album Project | 专辑 | 峰值 | 在榜周数 | 影响 |
|---|---|---:|---:|---|
| 42423 | Ugly Beauty | 10 | 6 | L3 dynamic/fixed |
| 42440 | 呸 | 7 | 3 | L3 dynamic/fixed |
| 42477 | Pleasure | 1 | 3 | L3 dynamic/fixed |
| 42517 | 花蝴蝶 | 13 | 1 | L3 dynamic/fixed |
| 42521 | 城堡 | 3 | 2 | L3 dynamic/fixed |

实现位于 Search 范围：

- `snapshot.py` 保留 `_shared_metric_maps` → `_context_rows` 的 lifetime 全集，移除 ledger 对该结果的覆盖。真实数据库共享构建复用 5A 已有 compact invocation loader，仍按 dynamic/fixed 分别加载 artist 与主轨，及时释放帧；未修改 `invocation.py` 或重做 5A 优化。
- `_album_chart_map` 以 `album_project_id` 提供成绩；候选展示名称不再参与事实匹配。旧 Search source-album 消费路径通过既有 project membership 与 canonical artist ID 查找同一成绩，候选匹配、排序、响应结构与链接格式均未修改。没有全局艺人改名、元数据治理或其他实体映射重构。
- full / invocation_full 直接保留 Power builder 的 `power_rank`。ledger reducer 保持稳定 ID 聚合，再恢复实际名称，调用同一个 `_stable_power_rank`，包括规范化文字、原文字和稳定排序；不改 Power builder、weekly ranking 或 Year-End 算法。
- 两条 delta 都保留正时长实体；补齐 `_track_delta_maps` 原先遗漏、但调用方实际需要的 physical/L1 映射。L2/L3 仍独立投影。context 和 ledger 发布顺序对齐 full；候选全集变化明确失败，不能静默过滤。
- delta 在重型工作前捕获 candidate generation，发布时继续核对原 generation；旧 builder baseline 不得进入新合同。full 也记录现有 schema 已支持的 lineage/dependency metadata，并在发布锁内复查。
- builder 升至 `music_search_snapshot_v11_shared_contract`；v10 只允许作为既有形状兼容的 LKG，不能 exact-ready 或作为新 delta baseline。唯一范围外的必要同步是独立生产 preflight 的 Search builder 常量，未执行部署。
- 真实 Year-End 故障注入暴露 shared-full 原先会回滚核心 Search 发布。现在 Year-End 写入在 savepoint 内，失败只回滚该可选投影；四变体核心 context/ledger 仍整组原子发布，由已有 Year-End 维护流程报告失败并重试。没有新增 schema、migration、持久 checkpoint 或长期缓存。

## 2. 原始差异的逐字段收口

使用 5A 保存的原始数据库副本与 payload，单独追踪用户给出的 36,212 / 30,970 行问题；此部分是原问题诊断复现，不作为合法 lineage 性能样本。

| 变体 | 原 full 行数 | 原 shared-full 行数 | duration-only 缺失（前→后） | 原 rank 差异→修正基线差异 |
|---|---:|---:|---:|---:|
| L2 dynamic | 9,304 | 7,960 | 1,344 → 0 | 1,208 → 0 |
| L2 fixed | 9,304 | 7,960 | 1,344 → 0 | 1,219 → 0 |
| L3 dynamic | 8,802 | 7,525 | 1,277 → 0 | 1,143 → 0 |
| L3 fixed | 8,802 | 7,525 | 1,277 → 0 | 1,170 → 0 |
| 合计 | 36,212 | 30,970 | **5,242 → 0** | **4,740 → 0** |

`original-replay.json` 从不变的 weekly facts 独立调用正式 Power builder 与修正后的 Search 映射，再与 ledger reducer 逐字段对账；四变体字段差异和重排后的序列差异均为零。10 条 L3 summary 全部恢复，不通过删除 ledger 成绩制造等价。

还在同一原始副本实际运行修正后的 invocation_full：36,212 行，实体键、次数、时长均未改变，weekly ledger 与 Year-End entity/meta 全字段及原 full 顺序完全相等。相对旧 full，4,121 个 rank 字段得到修正，其中包含上述 10 个原 null rank，其余 4,111 个来自旧 full 的排序错误；相对旧 shared-full，另有 1,334 个数字替代键排序错误得到修正。两组修正有重叠，不能简单相加当作原 4,740 差异数。

旧 shared-full ledger 的物理插入顺序与 full 原来不同；本轮保留 weekly facts 全字段，统一为 full 的 track → album → artist、周与榜位顺序。不是放宽顺序比较。

## 3. 正式 importer 的真实规模 lineage

输入为 `data/streaming/` 的 13 份真实 JSON，只读复制至隔离目录。以既有隔离主库副本保存元数据和治理事实，在新的 `real-import.db` 上调用 `backend.core.import_data.import_data`，事务 finalizer 使用正式 `summarise_current_playback_dataset` / `publish_playback_import_state`；source fingerprint 和 generation 均由 importer 产生，dataset digest 来自实际落库集合。然后使用正式 attribution reconcile、aggregation 和 candidate index builder。

| 项目 | 实际结果 |
|---|---:|
| 输入记录 | 92,975 |
| importer 接受并写入 | **92,908** |
| audio / video | 91,903 / 1,005 |
| 精确重复跳过 | 67 |
| 非法记录拒绝 | 0 |
| active plays | 92,908 |
| 缺少 source fingerprint / import generation | 0 |

`total_skipped=26,802` 是源数据的 Spotify skipped 标志数量，不是拒绝数量。输入范围为 2022-06-30 至 2026-08-21；generation 为 `9c13611a-8f58-4dc4-a9a4-f750890169f1`，实际 dataset digest 为 `d642b9bb924a6dc263e0b0a046035965511e9b366a9212ad54975d1c6791a801`。

正式 importer 的元数据重建后，真实测试库的完整 context 为 36,220 行；相对原副本，`artist:813`、`artist:923` 在四变体中成为可达实体，共多 8 行。该库旧 shared-full 为 30,982 行，duration-only 缺失为 5,238；因此不把这组新库数字冒充原问题的 5,242。每次 before/after 与 full 对账均使用同一个 importer 产物和相同治理事实。

## 4. 四变体完整合同对账

逐行比较 context 的全部 12 项公开事实：`entity_key`、`play_events`、`total_ms`、`peak_position`、`peak_weeks`、`weeks_on_chart`、`weeks_at_no1`、`power_score`、`power_rank`、`first_week`、`latest_week`、`first_peak_week`，另有物理关联列 snapshot_key 通过变体关联核验，共 13 列。九个公开 chart summary 字段没有删除、忽略或容差。

weekly ledger、Year-End entity/meta 比较全部事实字段与完整顺序。metadata 核对 filter fingerprint、source revision、semantic base、dependency digest、source generation/dataset digest、policy key、candidate generation、builder version。构建时间、build_strategy 和 delta 的 base/change-set 来源是不同执行的审计信息，单独保留差异，不当作统计事实相等。

| 数据/配置 | 四变体 context 行数（L2 D/F；L3 D/F） | context / ledger / Year-End / metadata |
|---|---|---|
| 默认：独立 corrected full vs shared-full | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |
| 默认：invocation_full vs shared-full | 同上 | 全字段、全顺序相等 |
| compilation 开启 | 9360 / 9360 / 8855 / 8855 | 全字段、全顺序相等 |
| merge 关闭 | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |
| max_merge_gap_minutes=2 | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |

默认每个 L2 ledger 为 15,065 行，L3 为 15,074 行；每变体 Year-End entity 550 行、meta 5 行，共 2,200 / 20。L2/L3 的结果不同，未把 L2 复制给 L3。非默认设置与 invocation_full 对账；默认另有独立 full 全流程基线。

空帧、duration-only、稳定 Power ties、L2/L3 独立身份、同周/跨周 delta reducers 与发布路径由定向单元测试覆盖。额外尝试正式空输入 importer 成功生成 0 行真实 lineage，但其后既有 Billboard 空聚合路径报 `cannot start a transaction within a transaction`；没有修改该范围外路径，也没有把它记为完整空库维护成功。

## 5. 同周与跨周追加：真实结果及边界

用真实输入的时间前缀建立初始 shared-full，再依次导入真实累积输入，正式 planner 判定 `snapshot_superset` / `incremental`，而非手填 generation 或 delta 证明。单独的无重叠尾片段被 planner 判为 ambiguous，因此没有强制执行；最终测试采用能证明集合包含关系的累积输入。

| 步骤 | 接受新增 | 已存在跳过 | 文件内重复 | active plays | 开放周 | 实际 Search 策略 |
|---|---:|---:|---:|---:|---|---|
| 前缀 | 92,859 | 0 | 67 | 92,859 | 2026-08-14 | shared-full |
| 同周追加 | 25 | 92,859 | 67 | 92,884 | 2026-08-14 | 安全回退 shared-full |
| 跨一周追加 | 24 | 92,884 | 67 | 92,908 | 2026-08-21 | 安全回退 shared-full |

两次回退原因都是 `incompatible_incremental_snapshot_base`。track identity revision 实际从 185100 → 185126 → 185151，policy/dependency fence 随之变化。核心 importer 的 `ensure_track_projection_identity` 和 `refresh_play_source_links` 会更新身份依据；本任务不通过清空 revision、补写 digest 或放宽 fence 强行进入 delta。

两次真实维护的产物另从治理与候选均已完成维护的同一副本强制运行 corrected full 参考 builder，重建 context、ledger 与 Year-End，两组四变体的 context、ledger、Year-End 和要求的 metadata 全字段、全顺序相等，见 `delta-*-ready-full`。最初在候选/attribution 尚未完成维护的中间副本运行 full，出现缺候选及 L3 dependency 错误；该次明确作废，未混入最终比较。

因此：shared-full 与两条 delta **实现采用同一 duration / identity / Power 合同**；真实同周、跨周的安全回退与最终统计可验证，真正通过全部 fence 的真实 delta 原子发布仍缺证据。后续需取得 importer 追加后 identity、membership、candidate content 均保持兼容的合法基线/追加对，或单独立项审计 importer identity revision 的变更边界；不属于修改本任务的统计语义。

## 6. 性能与资源

使用真实 importer 产物，before 为本轮开始保存的 pre-5B Search 源码（包含既有 5A），after 为修复后源码。每个样本独立进程、独立 SQLite 副本与 sidecar，按 before1 → after1 → before2 → after2 → before3 → after3 交错，均正常请求 atomic shared-full，未强制调用 legacy builder、未伪造 lineage。

最终性能表及阶段明细由 `final-*-*.json` 和 `performance-final-summary.json` 提供。采集 wall、进程 CPU、RSS 采样与进程高水位、SQL execute/executemany 调用和返回行、loader 次数、DataFrame.copy 次数/累计行与单元格数、关键阶段耗时。SQL 调用数把一次 executemany 计为一次批调用，返回行按 fetch/迭代累计；copy 量是逻辑复制工作量，不声称每次都分配相同物理字节。

| 独立进程 | wall s | CPU s | 峰值 RSS MiB | SQL 批调用 / 返回行 | copy 次数 / 累计行 |
|---|---:|---:|---:|---|---|
| final-before-1 | 61.266 | 56.683 | 1531.44 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-1 | 48.750 | 43.770 | 649.27 | 13,140 / 942,750 | 4,018 / 17,586,245 |
| final-before-2 | 57.638 | 54.809 | 1625.11 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-2 | 40.102 | 37.825 | 641.38 | 13,140 / 942,750 | 4,018 / 17,586,245 |
| final-before-3 | 63.897 | 59.075 | 1615.17 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-3 | 65.158 | 58.061 | 642.44 | 13,140 / 942,750 | 4,018 / 17,586,245 |

wall 中位数 **61.266 → 48.750 s（改善 20.4%）**；CPU 中位数 56.683 → 43.770 s。after 最大 RSS **649.27 MiB < 768 MiB**；满足资源门槛。copy 累计单元格由 780,989,175 降至 246,668,427。

| 关键阶段（每组调用数；wall 中位数） | before | after |
|---|---:|---:|
| 共享 loader | 4；11.236 s | 4；8.141 s |
| lifetime metrics | 4；4.673 s | 4；1.423 s |
| chart/ledger | 4；28.537 s | 4；27.687 s |
| 整组发布（含 Year-End） | 1；3.269 s | 1；3.418 s |

阶段计时含嵌套调用，不能将所有阶段相加。after 仍只有四次必要加载：两个阈值各一次 artist、一次主轨；不恢复逐变体 lifetime 全表扫描。


初轮六样本也完整保留，包括 after3 的较慢样本，没有删除离群值；恢复边界修复后，最终六样本另行重测。统计等价性为前置条件，不用资源改进抵消事实差异。

## 7. 并发、恢复与公共读取

- 四个并发维护调用均 ready，仅一组四次 compact loader、一次整组核心发布。全部重型加载期间仍能读取旧 active LKG；owner 在结束后释放。
- 新独立进程 exact-ready：0 loader、0 context/ledger 构建、0 publish、0 Year-End 重建；仅调用轻量 ensure 检查。保留 ready 成品的重启复用成立。
- 核心 INSERT 故障：事务回滚，四个旧 active 指针全部保持；旧任务/新 revision 竞争拒绝发布。
- Album Project、track identity、credit revision、candidate generation 漂移分别注入，必须拒绝旧任务发布。revision 使用现有变更 helper，candidate 通过正式 index rebuild 产生新 generation。
- source generation 漂移用正式 importer 的实际 append/事务发布产生，最终出现明确 `playback generation changed during shared-full snapshot build`，不是手改 lineage 字段。
- Year-End INSERT 故障：核心四变体仍 ready，Year-End 四个变体明确 failed/partial；移除隔离测试触发器后，仅重建四份 Year-End，0 loader、0 核心重建，最终恢复 ready。
- GET：5 个状态 × private-admin/public-readonly × candidates/context，每组合 30 个计时请求并预热一次，全部 200。ready/warming/failed-LKG 返回真实 items；unavailable 返回空 items 与 unavailable，不伪装计数 0。
- GET 哨兵 loader/Billboard 冷建/发布/排队/plays 或 agg_weekly SQL 均为 0。SQLite 初次只读连接创建 0 字节 WAL/SHM 后，探针期间 DB/WAL 字节与 mtime 不变；所有写 SQL 均由 authorizer 拒绝。
- Search API/model 与前端文件无修改；复核 `useMusicSearch.ts`、`MusicSearchResults.tsx` 和 `types/music-search.ts`，仍以 fingerprint/entity_key 拼接上下文、明确区分缺失与真实 0、消费相同九项 summary。没有重跑全应用 UI。

## 8. 门禁、范围和最终结论

| 验证 | 最终结果 |
|---|---|
| shared-full / duration-only / delta / invocation 定向 | 94 passed |
| Search 消费合同、旧 service 与 preflight 定向 | 32 passed |
| 完整 backend unit：`pytest -m unit -q` | 1,830 passed |
| 完整 contract：`pytest -m contract -q` | 434 passed；2 个既有 analysis 探针失败 |
| `ruff check backend deploy/production/validate-music-search-preflight.py` | PASS |
| Python compile：backend、scripts、preflight | PASS |
| docs audit | PASS，109 份当前 Markdown |
| `git diff --check` | PASS |
| Search GET + 页面消费结构 | 600 个计时 GET 全部 200；无冷建、无 plays/agg_weekly 读取；结构未变 |
| 正式文件 / 其他 dirty 文件 | 4,183 个正式文件 size/SHA 全同；范围外变更 0 |

九组最终全量对账包含独立 full、默认 invocation、三个非默认配置、两次真实追加后回退成品与独立 full、三个 after 性能进程之间的结果，全部统计字段/顺序、要求的 metadata 和 candidate generation 均相等。

完整 contract 中两个既有失败为 analysis stats/records GET 503：`test_api_boundary_probe`、`test_safe_readonly_api_smoke_probe`。在同一 dirty 工作区加载保存的 pre-5B Search 源码再次运行这两个探针，仍为相同 503；不改断言、跳过测试或修复范围外 analysis 路径。扩大 Ruff 到所有 scripts 还发现 11 个既有错误，均位于未修改的旧脚本；backend 与本轮 preflight 文件的 Ruff 通过。

正式 `data/` 的 4,183 个文件 size/SHA 全同；共享 worktree 范围外变更为 0。相对本轮恢复点仅 13 个授权文件发生变化（5 个 Search 源码、3 个测试文件、preflight 常量及 4 个文档）。`invocation.py` 与 maintenance service 的既有 5A 修改保持原 SHA。前后 SHA、初始/最终 git status、变更白名单记录在证据目录。未 git add、commit、push、部署；未开始阶段 6。没有修改正式数据库、缓存、设置、导入状态；没有改动其他任务的功能代码。

阶段 5 为 **Partial**：统计差异已经收口，真实 shared-full 具备正式 importer lineage 和规模验证；但合法真实 delta 成功发布尚未得到证实，完整 contract 仍有已复现的范围外失败，额外空库维护尝试也暴露既有空聚合事务问题。**目前不能进入阶段 6。** 这不是新的待审批统计决策，不应绕过 fence 或扩大为导入/身份治理重构来换取 Pass。

证据临时目录：`/tmp/spotifystats-phase5b/`。脚本、结构化对账、逐次性能结果、故障/GET 和门禁日志的长期副本保存于本任务外部产物目录 `spotifystats-phase5b/`，不将真实输入、数据库或用户播放 payload 提交 Git。
