# 数据导入处理与治理 S6 最终验收报告

> 日期：2026-09-21；二轮、三轮独立复核修复收口：2026-09-22
> 规划：S0–S6 全部实施
> 实现状态：IMPLEMENTED
> 验证状态：PASS（真实隔离副本 + 故障恢复 + 性能 + API + 浏览器 + 默认完整 fullstack）
> Git：S0–S6 已提交 `ae6febc`、`d37c9af`、`37c8431`、`8102f47`；独立复核与追加验收提交 `031075a`、`17002f0`、`7d3d079`、`9dddc89`、`8c5dfc0`；UNPUSHED
> 部署：NOT_DEPLOYED

## 结论

导入事故修复规划的 S0–S6 已全部完成。串流输入、播放事实、指纹基线、活动来源和派生阶段由同一批次与代际证据串联；事实提交后的派生失败不会再默认整库回滚；关键任务不依赖封面队列排空；played 与全量治理范围分别可见；Settings 提供可刷新、可重启恢复的持久导入工作台。

初次收口后又执行了一轮独立破坏性复核。复核在隔离副本中发现并稳定复现三个 P1：默认 snapshot 尾包的活动原始来源缺少历史父链、replace 确认与独占锁之间存在跨进程覆盖窗口、事实事务提交后而控制日志仍为 `prepared` 的硬中止无法向前恢复。三个问题均已重新打开、修复并补入真实编排回归；本报告中的最终结论以追加修复后的证据为准，不再沿用 `8102f47` 时点的旧结论。

2026-09-22 的二轮独立复核又发现一个 P1 升级兼容问题和一个 P2 测试隔离问题：migration 79 的合法 legacy 指纹基线尚无活动来源登记，被来源三元组栅栏误判为漂移；崩溃恢复测试撤销整个 `monkeypatch` 后直接覆盖全局数据库/账号路径，导致后续 Community 测试读取错误数据库。两项均已用先红后绿回归修复；最新结论以 `9dddc89` 代码及本报告末尾的新默认完整门禁为准。

第三轮独立复核进一步证明另一种升级前置状态仍被误判：数据库已有播放事实，但逐行指纹、generation 和活动来源基线全部缺失时，预检正确返回 `baseline_required`，已确认的完整替换却被来源对齐检查提前阻断。`8c5dfc0` 将该状态单独收窄为 `legacy_baseline_missing`，只允许经过确认、锁内重评估和事务基线栅栏的 full replace 初始化；append、未确认执行、部分指纹、控制库已有来源或 pending recovery 仍然 fail-closed。修复已通过专项探针和最新默认完整门禁，尚待第三轮独立复核方重新验收，不能表述为已获独立签收。

最终真实副本从 92,908 条旧事实导入至 94,760 条，新增 1,852、删除 0，保留 2 条迟到记录。三次独立副本运行全部通过 14 项语义对账、四套公开搜索快照、replacement 对照和再次导入 noop。正式 `data` 没有再次导入；本轮没有 push 或部署。

## S0–S5 交付状态

| 阶段 | 结论 | 主要证据 |
| --- | --- | --- |
| S0 | PASS | 父子元数据写入、played/all 范围与 92,908→94,760 事故基线固化；见 [S0 报告](2026-09-21-import-remediation-s0-baseline.md) |
| S1 | PASS | 不可变批次、活动来源 resolver、独立控制库、发布日志、writer lease、成套恢复和 noop 零写入 |
| S2 | PASS | 持久阶段、attempt/证据、generation/revision fence、启动恢复和结构化错误 |
| S3 | PASS | 优先级与资源 lane、target 去重、依赖顺序、1,204 个封面排队不阻塞关键任务 |
| S4 | PASS | played 6,642 个身份无硬问题；全量 6,675 个身份含 33 个治理项；238 条未匹配音频完整分类 |
| S5 | PASS | Phone/Compact/Desktop 共用持久工作台、历史、报告、重试和三维结果；见 [S1–S5 报告](2026-09-21-import-remediation-s1-s5.md) |

## 真实副本正确性

三个样本均从同一经核对旧种子创建相互独立的 SQLite、原始来源、缓存与控制目录；元数据/provider 输入冻结，不向 Spotify 发出验收请求。

| 样本 | 总 wall ms | 增量链路 ms | noop 预检 ms | 峰值 RSS | 结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| sample-1 | 341,005.436 | 85,917.299 | 6,528.769 | 2,025.56 MiB | PASS |
| sample-2 | 312,395.238 | 72,021.779 | 5,256.846 | 2,037.16 MiB | PASS |
| sample-3 | 314,862.506 | 71,619.504 | 5,196.540 | 2,034.84 MiB | PASS |
| median | 314,862.506 | 72,021.779 | 5,256.846 | 2,034.84 MiB | PASS |

每个样本同时满足：

- 旧基线 92,908 条可初始化且相同输入为 noop；新包关系为 `snapshot_superset`，新增 1,852、删除 0、最终 94,760。
- 两条早于旧最大时间的迟到记录保留；开放边缘周不发布周榜，但非榜单事实仍进入统计。
- 事实集合、原始时长、年度分区、credits、track groups、Album Projects、Billboard、Home/Archive、Power、Records、Year-End 与四套搜索快照共 14 项语义对账一致。
- 再次导入关系为 `identical`；播放事实、语义 revision、派生调度和数据库备份均不写入。
- L2/L3 × fixed/dynamic 四套公开搜索 target 全部 ready；兼容 L1 不冒充当前必需公开集合。

原始样本使用 `import_governance_real_acceptance_v1`。其中字段名 `peak_rss_kib` 在 macOS 上实际保存 `ru_maxrss` 的字节值；上表按字节换算 MiB。脚本已升级为 v2，以 bytes/MiB 明确输出；没有为了改字段名重跑三次昂贵样本或改写原始证据。

## 恢复、隔离与状态边界

恢复/队列矩阵共 190 项定向测试通过，并在最终审计中补齐以下边界：

- durable quarantine 只允许所属 run 穿越，其他 writer 继续 fail-closed；`sources_published` 与 gate 清除由同一控制事务/CAS 完成。
- 启动在 migration 前检查恢复与 gate 状态；证据不足时拒绝继续写入，不让迁移成为隔离窗口内的新提交。
- Year-End warming、无 LKG 但仍有活动 job、自动晋升 ready 和 failed/unavailable 分别映射，不返回虚假 ready 或 0。
- 阶段依赖 revision 排除发布账本、job 和错误记录自身的记账变化；重启时可复用已证明的 `core_ready` 早期阶段。
- 新 generation/revision 取代旧任务时，旧输出不得激活；事实提交后的派生失败只重试正确阶段，不重复播放 ETL。

真实 API 使用 `/tmp/spotifystats-s6-api-v2/spotify_stats.db`。无操作执行前后主库状态与 mtime 不变，未创建 import backup。隔离 helper 同步更新 Home 主库身份与 snapshot root，修复了副本被误判为非主库而无法发布公开 Home 快照的问题。

## 独立复核后的 P1 追加修复

追加修复严格限定在独立复核证明的三条失败路径及其必要证据链：

- 上传输入的 `batch_id` 与最终发布的 `source_version_id` 分离。`snapshot_superset` 可直接发布完整 snapshot；`delta_tail` 若输入本身不能重放完整事实，则在独占锁内从当前活动来源派生 delta 子版本。发布前后均对 resolved 来源的去重指纹 count/digest 与目标事实做语义对账。
- 确认 token 绑定 generation、dataset digest、record count 与活动 source version。取得跨进程独占锁后重新评估并复核 main/control 来源三元组；`import_data` 在 `BEGIN IMMEDIATE` 后、任何 DELETE/INSERT 前再执行事务内 baseline fence，replace 与首次初始化不再绕过旧状态校验。
- 恢复器遇到“主库已提交、控制库仍为 prepared”时，从同一主库事务写入的 `playback_import_state` 与 `playback_import_runs.change_set_json` 读取并严格校验证据，再用 CAS 将控制 run 补齐为 `facts_committed`，之后才发布来源。最终 CAS 仍不直接接受 prepared，证据不足继续 fail-closed。

新增的非 mock 编排矩阵覆盖：空库 full、snapshot superset、浏览器默认 snapshot 尾包、显式 delta、reconcile、replace、持久 noop、replace 事务栅栏、另一进程在确认后完成新发布，以及 `mark_facts_committed` 前硬中止。活动来源同时通过真实 importer 重放，最终 count/digest 与主库一致；noop 不新增备份、不改事实/主库 run/活动来源，仅保留输入批次与控制审计。

追加修复后的本地结果：定向编排 5/5、相关导入组 85/85、完整 unit 1,980 passed / 2 skipped、完整 contract 441 passed、前端 86 files passed / 1 skipped（669 tests passed / 4 skipped）、production build PASS。提交钩子的 ruff、format、mypy 与 secrets 全部 PASS。

最终完整门禁还发现 Community revision 在逐表摘要期间把封面下载、后台任务状态等数据库级并发写入误判为事实漂移，可能让正常 GET 瞬时返回 503。`7d3d079` 将语义摘要固定在一个 SQLite 一致性读快照内；并发提交时本次完整摘要仍可返回但不绑定到较新的 `data_version` 缓存，下次请求重算。新增 WAL 并发回归已通过；真实隔离副本在 80 次封面展示字段提交干扰下连续完成 36 个 Community 请求，全部 200。

## 二轮独立复核：legacy 首次来源登记与测试隔离

`9dddc89` 在独占发布锁内把活动基线明确分类为 `empty`、`legacy_unregistered` 或 `published`。合法 legacy 必须同时满足：指纹版本、事实 count/digest/generation 完整且与预检一致，主库 publication state 为 `legacy`，主库与控制库均无活动 source/publication 指针，并且没有 pending publication 或写隔离证据。已发布状态仍要求 main/control 的 source、generation、digest 完全一致；任何 pending、失配或状态漂移继续 fail-closed，没有放松原有 token、锁内重评估、`BEGIN IMMEDIATE` 事务栅栏和崩溃恢复。

行为矩阵已固定：

- legacy 相同输入的 auto 模式是真正 noop：事实、备份和来源指针不写入，运行明确返回 `legacy_source_unregistered`，界面提示用覆盖全部历史的完整导出执行完整替换。
- legacy 完整超集可在语义对账证明候选来源覆盖目标事实后追加并首次登记；显式 replace 对相同或新增完整输入都通过备份、事实事务和来源发布完成登记。
- 只有尾部数据而无法覆盖现有 legacy 历史时，以 `legacy_source_baseline_requires_full_snapshot` 阻断，并给出完整导出动作；不能构造缺父链的活动来源。
- 预检后竞争发布、已发布 control 指针失配、pending 主库状态和首次登记硬中止分别验证为阻断或可恢复，最终来源仍能真实重放同一事实集合。

测试隔离修复只把故障注入放进 `monkeypatch.context()`；数据库与账号路径继续由外层 fixture 管理，并在崩溃恢复前后显式断言不变。最小顺序和逆序各 2/2 通过；编排、control/source、API contract、Community 四文件组合正序和逆序各 96/96 通过，不再依赖测试运行顺序。

正式数据库只读核对为 94,760 条、fingerprint version 1、generation/digest 完整、source/publication 指针为空、`publication_state=legacy`，与缺陷前置状态一致。SQLite Online Backup 副本使用当前 `data/streaming` 完整导出验证 relation=`identical`；在首次登记的事实提交后模拟硬中止，恢复结果为 completed=1、blocked=0。恢复后主库/control 的 source、generation、digest 指针一致，pending=0、写闸门解除；活动来源在另一全新数据库重放为 94,760 条，指纹集合和 digest 均与副本一致。探针前后正式数据库 SHA-256、inode、大小和 mtime 全部不变。该探针明确跳过无关派生阶段；派生全链由下述默认完整门禁覆盖。

## 三轮独立复核：已有事实但无指纹基线

第三轮复核使用 tracked seed 稳定复现：主库有 117 条播放事实，但 `source_fingerprint`、`source_fingerprint_version`、`import_generation_id` 均为 0 条，`playback_import_state` 的 generation/digest/source/publication 为空、record count 为 0、publication state 为 `legacy`；控制库也没有活动来源或恢复证据。预检返回 `baseline_required`，修复前已确认的 replace/auto 都以 `confirmed_plan_drift` 阻断。

`8c5dfc0` 只在下列证据同时成立时把状态分类为 `legacy_baseline_missing`：主库确有事实；预检是 `active_state_missing`；主状态 generation、digest、source、publication 和 fingerprint version 为空且 record count 为 0；publication state 精确为 `legacy`；逐行 fingerprint、fingerprint version、generation 三类来源证据全部为 0；控制库 source/generation/digest 为空；不存在 pending publication 或写隔离。该分类只允许 `decision=replace`、`confirm_plan=true`、`relation=baseline_required` 的执行继续；其他组合仍按确认漂移拒绝。既有确认 token、跨进程独占锁、锁内重新预检、`BEGIN IMMEDIATE` 事务基线 fence、来源语义对账及崩溃恢复均未放宽。

专项矩阵和原始探针结果：

- missing-baseline 定向矩阵 8/8，完整真实编排文件 22/22；append 与未确认执行被阻断，replace 和 auto 的已确认 full replace 均成功，并在全新数据库真实重放为相同 count/digest。
- 竞争者先完成首次登记后，旧确认按 `confirmed_plan_drift` 阻断；首次登记在事实提交后硬中止，可恢复为 completed=1、blocked=0，主库/control 来源一致且写闸门解除。
- 部分逐行指纹、控制库已有来源、pending run 三种损坏状态均不能冒充合法旧库。
- 未改动的第三轮复核探针由 117 条无指纹事实成功完整替换为 2 条有指纹事实；随后 auto 对相同输入为 ready noop。未改动的上一轮三条 P1 探针和 migration 79 legacy 探针也全部通过。
- 编排、control/source、API contract、Community 四文件按原失败顺序共 104/104 通过；没有依赖测试顺序或全局路径泄漏。

以上均在独立 worktree 和临时 SQLite 中执行；没有写正式数据库、合并主检出、push 或部署。结论是“第三轮缺陷已本地修复并完成实现方验收”，不是“第三轮独立复核已经签收”。

## 性能、API 与浏览器

- ready 基线冷预检三次：5,666.722 / 5,300.994 / 5,539.753 ms，median 5,539.753 ms。
- 独立 21 个 hot 样本：median 69.662 ms、P95 71.258 ms、max 75.725 ms，满足 P95 ≤500 ms。
- 最终默认 fullstack 的 22 轮热 API：Import Preflight median 10.880 ms、P95 12.141 ms；最慢的 `/api/billboard/data` P95 为 345.295 ms，所有监测端点 hot P95 均低于 500 ms。
- API smoke 153/153；OpenAPI 234 operations、0 unaccounted；GET 149/162 覆盖、13 个明确排除、0 unaccounted。
- 独立真实浏览器检查覆盖 Desktop、Compact、Phone：导入 noop 流程、状态/历史、44×44 主要触控目标、无横向溢出、无本机绝对路径泄漏。
- P1 追加修复后再次用真实 Playwright CLI 检查 Desktop 与 390×844 Phone 导入工作台：运行历史与数据健康请求均为 200，Phone `scrollWidth == innerWidth == 390`，可见按钮无小于 44×44 的目标，控制台 0 error；会话验收后已关闭。
- 默认浏览器门禁覆盖完整路由与五档 viewport、桌面/移动交互、图表、长列表、40 组控件 inventory，以及 Chromium、Firefox、WebKit；全部 PASS。

验收中先后发现三处测试合同已落后于新界面/合法状态：导入工作台仍查找旧“串流数据”，移动筛选只接受 unavailable 而不接受 ready，跨浏览器脚本仍使用旧导入文案。三处均改为验证当前非写入合同并补回归测试，随后在同一默认完整 run 中通过。

## 默认完整本地门禁

初次 S6 run：`20260921T124842.178610Z-150a940588e1`，mode=`full`，总耗时 1,399,250 ms。该 run 证明初次 S6 时点的完整门禁，但发生在追加修复前；追加修复后的新默认完整 run 见本节末尾更新。

| 必需阶段 | 状态 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8,039 |
| quality | PASS | 38,271 |
| backend | PASS | 500,967 |
| api | PASS | 175,055 |
| browser-routes | PASS | 399,742 |
| browser-interactions | PASS | 80,085 |
| browser-inventory | PASS | 45,606 |
| browser-compat | PASS | 151,353 |

门禁明细：Backend seed 2,923 passed；真实 integration 187 passed；Frontend 86 files passed / 1 skipped、669 tests passed / 4 skipped；production build、pre-commit、mypy、ruff、secrets 和文档审计全部通过。

warning 未被虚写为零：seed 有 1 个 LibreSSL/urllib3 环境 warning 与 3 个 AnyIO HTTP 422 弃用 warning；integration 有同一 LibreSSL warning；Vite 保留大 chunk 建议。它们没有改变本次导入合同或门禁结果。

追加修复后的默认完整 fullstack：`20260921T160828.009214Z-b57c14810266`，mode=`full`，HEAD=`7d3d0795ec978864750d9c63622818d941591758`，启动时 `dirty=false`，数据集=`online_backup`、播放事实 94,760 条，总耗时 1,675,434 ms。八个必需阶段全部 PASS；optional 未选择，不影响默认完整结论。

| 必需阶段 | 状态 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8,279 |
| quality | PASS | 51,553 |
| backend | PASS | 612,150 |
| api | PASS | 197,506 |
| browser-routes | PASS | 402,254 |
| browser-interactions | PASS | 81,029 |
| browser-inventory | PASS | 47,575 |
| browser-compat | PASS | 274,907 |

该代码 HEAD 门禁明细：Backend seed 2,927 passed / 2 skipped / 4 warnings；真实 integration 186 passed / 1 skipped / 1 warning；Frontend 86 files passed / 1 skipped（669 tests passed / 4 skipped）；API smoke 153/153、boundary 113/113；40 组控件 inventory 共 1,979 个控件、307 个主要触控目标、0 个尺寸违规；Chromium、Firefox、WebKit 全部 PASS。warning 仍是既有 LibreSSL/urllib3、AnyIO HTTP 422 弃用及 Vite 大 chunk 建议，没有被虚写为零。

二轮独立复核修复后的最新默认完整 fullstack：`20260921T172419.302072Z-692fe0db8429`，mode=`full`，HEAD=`9dddc897fd2f9467f4878171046ded438d32b79d`，启动时 `dirty=false`、播放事实 94,760 条，总耗时 1,364,251 ms。八个必需阶段全部 PASS；optional 未选择。

| 必需阶段 | 状态 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 7,613 |
| quality | PASS | 42,288 |
| backend | PASS | 463,699 |
| api | PASS | 170,314 |
| browser-routes | PASS | 399,935 |
| browser-interactions | PASS | 80,052 |
| browser-inventory | PASS | 45,767 |
| browser-compat | PASS | 154,418 |

最新门禁明细：Backend seed 2,936 passed / 2 skipped / 4 warnings；真实 integration 186 passed / 1 skipped / 1 warning；Frontend 86 files passed / 1 skipped（670 tests passed / 4 skipped）；production build、pre-commit、mypy、ruff、secrets 与文档/OpenAPI 审计均通过；API smoke 153/153、boundary 113/113，所有监测端点 hot P95 均低于 500 ms；路由、交互、40 组控件 inventory、长列表及 Chromium、Firefox、WebKit 全部 PASS。既有 LibreSSL/urllib3、AnyIO HTTP 422 弃用和 Vite 大 chunk warning 仍如实保留。

第三轮 P1 修复后的最新默认完整 fullstack：`20260922T064118.846119Z-33ffa88be60d`，mode=`full`，HEAD=`8c5dfc0a4ba50b90588c7b457fdf87338009467f`，启动时 `dirty=false`、播放事实 94,760 条，总耗时 1,528,668 ms。八个必需阶段全部 PASS；optional 未选择。

| 必需阶段 | 状态 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8,386 |
| quality | PASS | 50,348 |
| backend | PASS | 535,101 |
| api | PASS | 225,447 |
| browser-routes | PASS | 401,930 |
| browser-interactions | PASS | 81,528 |
| browser-inventory | PASS | 47,670 |
| browser-compat | PASS | 178,041 |

该 run 明细：Backend seed 2,944 passed / 2 skipped / 4 warnings；真实 integration 186 passed / 1 skipped / 1 warning；Frontend 86 files passed / 1 skipped（670 tests passed / 4 skipped）；production build、pre-commit、mypy、ruff、secrets 与文档/OpenAPI 审计均通过；API smoke 153/153、boundary 113/113，所有监测端点 hot P95 均低于 500 ms；完整路由、五档 viewport、交互、图表、40 组控件 inventory、长列表及 Chromium、Firefox、WebKit 全部 PASS。既有 LibreSSL/urllib3、AnyIO HTTP 422 弃用和 Vite 大 chunk warning 仍如实保留。

## 数据与交付边界

- 三次真实导入和 API/浏览器使用隔离副本；正式播放事实保持 94,760。开发服务此前仅被动应用 migration 79，没有再次导入或执行治理清理。
- 机器可读 raw samples 保留在本机 `/tmp/spotifystats-s6-real-sample-{1,2,3}.json`，不提交真实数据、SQLite、缓存、恢复点或本机路径明细。
- 原事故 HTTP 500 缺少足够历史堆栈，仍标记为“根因未证实”；本轮交付的是结构化诊断、限定重试和已证明路径，而非猜测根因。
- 没有自动清理 33/238 治理项，没有删除历史恢复点，没有 push、正式数据迁移或部署。
- 本轮分支仍未合入主检出；主检出仅保留用户原有 `data/governance_cache.build.lock` 与 `data/import_backups/` 未跟踪项，本轮未修改或清理。
