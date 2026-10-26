# 导入事故复盘与治理修复验收

2026-10-26按主题合并。从正式导入事故复盘到S0、S1–S5和S6验收排列；事故中的正式写入、后续隔离副本测量、独立复核及未推送部署分别判断。

## 阅读顺序

- [2026-09-21 Spotify Extended Streaming History 导入复盘报告](#2026-09-21-spotify-extended-streaming-history-导入复盘报告)
- [阶段 S0：导入事故修复与测量基线](#阶段-s0导入事故修复与测量基线)
- [导入处理与治理修复 S1–S5 实施报告](#导入处理与治理修复-s1s5-实施报告)
- [数据导入处理与治理 S6 最终验收报告](#数据导入处理与治理-s6-最终验收报告)

## 2026-09-21 Spotify Extended Streaming History 导入复盘报告

原记录：`2026-09-21-streaming-import-incident-and-optimization.md`。

### 结论

本次导入已完成。下载目录中的原始串流 JSON 已替换到 `data/streaming`，SQLite 数据库已通过应用导入流程更新，导入后维护、音乐查找快照和 Billboard 快照均已完成。

本次不是增量导入，而是一次受确认保护的完整导入。原因是旧数据库没有可用的持久化播放记录指纹基线，系统无法安全证明旧数据与新导出之间的新增、删除和不变集合，因此按 fail-closed 策略回退为 `full`。本次成功后已经写入基线；导入同一份数据的预检结果为 `identical`、`estimated_strategy=noop`，后续新导出可以进入可比较的增量判定链路。

### 范围与输入

- 执行时间：2026-09-21（Asia/Shanghai）
- 源目录：`/Users/benjaminlei/Downloads/Spotify Extended Streaming History`
- 应用原始数据目录：`/Users/benjaminlei/Code/202605-SpotifyStats/data/streaming`
- 数据库：`/Users/benjaminlei/Code/202605-SpotifyStats/data/spotify_stats.db`
- 账号导出数据不在下载目录中，因此保留了 `data/account`，没有用不完整的下载目录覆盖它。

源目录和 `data/streaming` 最终文件集合一致、逐文件 SHA-256 一致；两边 JSON 原始记录数均为 94,854。导入器对文件内重复记录去重后写入 94,760 条播放事实，少 94 条重复记录。

### 原始文件替换与保护

替换前先创建了原始数据备份：

- 备份目录：`data/import_backups/streaming_before_20260921T122048+0800`
- 清单：`data/import_backups/streaming_before_20260921T122048+0800.manifest.txt`
- 替换方式：保留 `data/account`，仅对 `data/streaming` 执行带删除同步，使目录内容与下载目录一致。

数据库导入由应用自身创建 SQLite 快照并负责失败回滚。本次成功导入使用的数据库快照为：

`data/import_backups/spotify_stats_20260921T050216Z_055c43a59eaf_0fe0948b.db`

### 首次预检与“为什么没有增量导入”

原始数据替换后，应用预检得到：

| 项目 | 数值 |
| --- | ---: |
| 当前活动播放记录 | 92,908 |
| 输入原始记录 | 94,854 |
| 输入去重后记录 | 94,760 |
| 可比较的不变记录 | 0 |
| 输入新增记录（按当前基线） | 94,760 |
| 指纹基线 | missing |
| 比较状态 | baseline_missing |
| 判定关系 | baseline_required |
| 预计策略 | full |

数据库当时的 `playback_import_state` 中 `dataset_digest`、`fingerprint_version` 等持久化基线字段不可用；历史 92,908 条 `plays` 也没有完整兼容的源记录指纹。应用不能从旧的播放维度表、日期范围或 Spotify ID 反推“哪些行完全不变”，否则可能漏删、重复计入或错误追加。

导入完成后的事后集合核对确认：旧原始来源有 92,908 条唯一记录，新来源有 94,760 条；旧集合全部包含在新集合中，新增 1,852、移除 0。新增记录中有两条音频早于旧来源最大时间，因此这份新包属于 `snapshot_superset`，而不是只凭时间边界即可证明的 `delta_tail`。这些数字来自导入完成后的独立对账，不能倒写成首次预检当时已经拥有的基线证据。

因此，之前做过的“自动/增量”设置仍然会在证据不足时安全回退。设置表达的是允许自动判定，不是替代数据基线。这个行为是正确的安全回退，但产品提示需要更明确地说明“首次完整导入用于建立基线”。

首次预检还报告两类非阻断警告：

- 94 条文件内完全重复的串流记录；
- 5 对相邻串流文件日期范围重叠，但均属于边界日期，未发现跨文件共享记录。

### 失败过程与根因

应用每次失败都创建数据库快照并恢复旧库；没有把半成品数据库留在活动路径中。

#### 1. Spotify 元数据刷新阶段外键失败

- 任务：`3588133a52ad`
- 失败信息：`FOREIGN KEY constraint failed`
- 失败位置：Spotify 曲目/专辑元数据刷新
- 快照：`data/import_backups/spotify_stats_20260921T042118Z_3588133a52ad_94f98f35.db`
- 回滚：成功，恢复 `data/spotify_stats.db`

根因是 `album_spotify_links.spotify_album_id` 引用 `spotify_album_meta.spotify_album_id`，但曲目批处理先写了子表链接，父级专辑元数据尚未插入。

已修复：

- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/domains/metadata/spotify_refresh.py`
- 新专辑父行不存在时不立即写链接；专辑批处理完成后统一 backfill。
- 保留跨播放 generation 的历史链接回填语义。

#### 2. L3 专辑归属出现 33 个未解决问题

- 任务：`248aa9ed7e39`
- 失败信息：`post-import L3 album attribution has unresolved issues: 33`
- 快照：`data/import_backups/spotify_stats_20260921T042953Z_248aa9ed7e39_1e98fcaa.db`
- 回滚：成功

第一次修复尝试让导入维护在 L3 规划前执行影响范围内的 Album Project 修复，但问题仍然存在。

#### 3. L3 问题复现与第二次修复

- 任务：`8e3fbc25d42d`
- 结果：仍为同一组 33 个 L3 问题
- 快照：`data/import_backups/spotify_stats_20260921T043707Z_8e3fbc25d42d_2fdd2cf1.db`
- 回滚：成功

隔离数据库复现显示，这 33 条全部具有以下特征：

- `issue_kind=uncovered`；
- 证据为 `no_album_project_membership`；
- `raw_play_count=0`、`raw_ms=0`；
- 没有有效 `source_album_ids`；
- 是旧 Spotify 别名/维度行在全量替换后失去播放事实的结果。

全量替换把播放事实重新归并到当前 Spotify owner，旧别名仍保留为 active 兼容维度，但已经没有播放记录。原来的 L3 工作集按“所有 active L1 identity”扫描，于是把这些零播放兼容行误当成导入阻断问题。

已修复：

- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/domains/playback/l3_album_attribution.py`
  - 增加 `include_unplayed` 范围参数。
  - 导入维护、启动 reconcile、音乐查找维护只对有播放事实的 L3 work 进行阻断性检查。
  - 直接治理规划默认仍保留完整 active L1 覆盖语义。
- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/services/import_maintenance_service.py`
- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/services/music_search_maintenance_service.py`
- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/main.py`
- `/Users/benjaminlei/Code/202605-SpotifyStats/backend/domains/metadata/track_identity.py`
  - 导入期身份同步支持只同步有播放事实的曲目。
  - 播放来源链接使用播放时 Spotify ID，缺失时回退到曲目维度 Spotify ID。

另外，访问本机 API 时曾遇到代理把 localhost 请求拖慢/超时；验证本地服务时改用 `curl --noproxy '*'` 后恢复。该问题属于本机代理/命令环境边界，不是导入数据根因。

### 成功导入结果

- 任务：`055c43a59eaf`
- `detected_relation=baseline_required`
- `executed_strategy=full`
- 文件：13 个 JSON 串流文件
- 写入播放事实：94,760
- 文件内重复跳过：94
- unchanged：0
- 数据日期：2022-06-30 至 2026-09-19
- 数据库播放行：94,760
- 音频：93,587
- 视频：1,173
- 曲目：10,026
- 专辑：4,030
- 艺人：1,320
- L3 归属决策：6,642
- L3 unresolved issues：0
- SQLite `integrity_check`：`ok`
- SQLite `foreign_key_check`：空
- 孤儿播放曲目/专辑：均为 0
- 导入维护：`ok`

应用健康报告为 `partial`，唯一提示是 238 条没有曲目维度的音频播放记录；没有 blocker，`safe_to_use=true`。这些记录没有被删除，后续应按原始字段和 `content_type` 分层判断，不应仅凭数量自动清理。

导入后排队的任务也已完成：

- 音乐查找快照：`77518a75-f6e`，`done`
- Billboard 快照：`65a98777-942`，`done`
- 最终数据库没有 pending/running 后台任务。

### 基线建立后的验证

导入完成后再次对同一源目录执行应用预检：

| 项目 | 结果 |
| --- | --- |
| `fingerprint_baseline_status` | `ready` |
| `comparison_status` | `comparable` |
| `detected_relation` | `identical` |
| `record_delta_comparable` | `true` |
| 当前记录 / 输入记录 | 94,760 / 94,760 |
| unchanged | 94,760 |
| added / removed | 0 / 0 |
| `estimated_strategy` | `noop` |
| 计划动作 | 跳过数据库快照、播放写入和派生重建 |

这证明本次导入已经完成了此前缺失的基线建设。下一次同一份导出会被识别为 no-op；下一次只包含历史尾部新增记录的导出，可以在基线可比较的前提下进入增量策略。

### 自动化验证

本次针对修复运行：

```text
.venv/bin/pytest -m unit -q \
  backend/tests/unit/test_track_identity.py \
  backend/tests/unit/test_track_identity_risk.py \
  backend/tests/unit/test_spotify_metadata_refresh.py \
  backend/tests/unit/test_l3_album_attribution.py \
  backend/tests/unit/test_music_search_maintenance.py

91 passed, 1 warning
```

导入 API 及基础设施合同测试：`27 passed, 1 warning`。

另有隔离数据库实导入复现：94,760 条播放事实成功写入，导入范围 L3 扫描 6,642 条、有归属 6,642 条、问题 0；音乐查找四个快照均为 ready。

### 后续修复与优化建议

按优先级建议：

1. **P1：将原始文件替换纳入可恢复事务边界。** 目前原始 `data/streaming` 替换和数据库导入是两个阶段：数据库失败时数据库会回滚，但原始文件已经是新版本。当前通过备份可恢复，长期应使用 staging 目录，在数据库成功发布后再原子切换原始目录，或把原始 manifest 版本写入导入事务并提供一键回滚。
2. **P1：把 baseline missing 变成明确的一次性初始化流程。** 预检应直接展示“当前库没有可比较基线，需要一次完整导入”，并将确认后的 full import 标为 `baseline_initialization`，避免用户把它理解成增量设置失效。
3. **P1：优化导入后的后台任务优先级。** 本次导入排队了 1,204 个封面下载，音乐查找和 Billboard 任务先处于 pending，直到封面任务处理完才完成。建议为导入后关键派生快照设置独立队列或优先级，避免用户看到长时间 warming。
4. **P2：完善 L3 范围合同。** 将“完整治理覆盖”和“导入阻断覆盖”两个范围写进文档及指标，分别报告 `all active L1` 与 `played L3 work`，避免零播放兼容维度再次被误报为播放导入故障。
5. **P2：改进预检与后台锁竞争的可观测性。** 导入刚完成、后台任务仍在运行时，HTTP 预检曾短暂返回 500；稍后重试恢复，服务层直调结果正常。应记录异常堆栈、preflight key、job id 和数据库 revision，并对只读预检提供短重试/明确的 warming 响应，避免返回无上下文的 Internal Server Error。
6. **P2：细化重复与边界文件提示。** 94 条重复记录和 5 组边界日期重叠均被正确处理，但预检可进一步显示重复指纹样例、跨文件共享计数和“导入器将保留一条”的明确说明。
7. **P3：跟踪 238 条无曲目音频记录。** 保留原始事实，增加来源字段分布和可解释分类，确认哪些是 Spotify 原始无元数据、哪些是可通过别名/URI 修复的记录。

### 当前边界

- 本次没有执行 Git commit 或 push。
- 没有覆盖 `data/account`，因为用户下载目录不包含账号导出数据。
- 未删除任何原始播放记录；导入器只按源指纹去重，并保留了失败数据库快照和原始目录替换前备份。
- 报告记录的是本地数据库、应用 API 和后台任务证据，不代表任何 staging/生产环境已部署或验收。

## 阶段 S0：导入事故修复与测量基线

原记录：`2026-09-21-import-remediation-s0-baseline.md`。

日期：2026-09-21。范围：导入事故既有补丁复核、真实旧/新来源集合核对、缺基线与 ready 基线预检测量。正式 `data` 仅只读核对，没有重新导入或修改播放事实。

### 结论

S0 通过。Spotify 专辑父记录写入顺序、跨 generation 链接回填、导入期 played works 范围以及完整治理 all identities 范围已由代码和回归测试固化。旧来源与新来源的真实集合关系可复演：92,908 → 94,760，新增 1,852、移除 0；其中两条新增音频早于旧最大时间，所以真实关系是完整快照超集，不是纯时间尾包。

本阶段只确认事故修复和后续实施基线，不把历史成功导入当成本阶段测试，也没有修改正式库、原始来源、备份或治理记录。

### 已固化的修复合同

- 曲目响应带来新专辑 ID 时，只有 `spotify_album_meta` 父记录已存在才写入 `album_spotify_links`；专辑批次完成后再统一补链接。
- 链接回填按 Spotify album ID 覆盖全部匹配播放 generation，不只处理最新批次。
- 导入维护、启动 reconcile 和音乐查找维护以 played works 作为阻断范围；完整治理规划仍默认扫描 all identities。
- 播放时 Spotify ID 缺失时，来源链接允许回退到曲目维度 Spotify ID；零播放维度行不会在 played-only 同步中被重新注册成导入阻断身份。

### 真实来源与隔离种子

旧来源使用 `data/import_backups/streaming_before_20260921T122048+0800`，旧 SQLite 种子使用导入前 Online Backup；新来源使用当前 `data/streaming`。两者均只读参与核对，运行时 staging 位于系统临时目录。

| 项目 | 旧来源 | 新来源 | 差异 |
| --- | ---: | ---: | ---: |
| 音频唯一记录 | 91,903 | 93,587 | +1,684 |
| 视频唯一记录 | 1,005 | 1,173 | +168 |
| 全部唯一记录 | 92,908 | 94,760 | +1,852 |
| 从旧集合移除 | — | — | 0 |
| 早于旧最大时间的新增音频 | — | — | 2 |

旧 SQLite 副本的 `playback_import_state` 没有活动 generation、fingerprint version 或 digest；当前正式库只读核对为 94,760 行、fingerprint version 1、64 位十六进制 digest，`integrity_check=ok`。

### 预检测量基线

同一新来源对旧库副本执行缺基线预检：4.822 秒，结果为 `baseline_required / missing / baseline_missing`，当前 92,908、输入 94,760。响应中的 94,760 只能表示输入全集，不能解释为真实新增。

当前 ready 基线通过本机 API 测量：首次冷请求 6.498 秒；随后 20 个 hot 样本 median 69.8 ms、P95 95.5 ms、最大 127.0 ms，满足既有 hot P95 ≤500 ms 门槛。结果为 `identical / ready / comparable`，当前与输入均为 94,760。

本阶段先固定以上比较口径。三次独立进程冷样本、分阶段导入耗时、排队耗时和峰值资源留到 S3/S6 在统一实施版本上测量，避免把实施前数字误写成最终性能结果。

### 验证

```text
元数据、身份、L3、音乐查找、导入 API、恢复、范围、预检与增量执行：166 passed
文档审计：PASS
git diff --check：PASS
```

第二组测试暴露了测试进程中后台 worker 在临时数据库销毁后的线程警告；它不改变断言结果，但属于 S2/S3 的持久队列与生命周期收口项，不能作为最终验收通过依据。

### 边界

- 没有写入正式 SQLite、切换正式原始目录或清理历史恢复点。
- 没有把 33 个零播放历史身份直接标记为可退役；其引用和生命周期在 S4 处理。
- 没有把约 238 条无曲目音频统一视为损坏歌曲或自动修复。
- 没有 push、部署或生产验收。

## 导入处理与治理修复 S1–S5 实施报告

原记录：`2026-09-21-import-remediation-s1-s5.md`。

> 日期：2026-09-21
> 范围：持久批次、事实/来源发布、阶段恢复、任务调度、身份治理与 Settings 工作台
> 实现状态：IMPLEMENTED
> 验证状态：PASS（后端完整测试 + 前端测试/build + 定向故障矩阵；最终真实副本/浏览器/fullstack 另见 S6 报告）
> Git：`d37c9af`、`37c8431`；UNPUSHED
> 部署：NOT_DEPLOYED

### 结论

S1–S5 已按规划实现并提交。串流导入不再依赖浏览器路径或进程内任务字典：服务端拥有不可变批次，独立控制库持久保存运行、阶段、发布日志和报告；事实、来源和恢复均有 generation/digest/revision 栅栏。事实提交后的派生失败从对应阶段重试，不再默认整库回滚。Settings 在 Phone、Compact、Desktop 共用同一持久状态源，可上传、预检、确认、执行、查看历史/报告、重试和重新核对。

### S1：批次一致性与基线生命周期

- 新增服务端 `snapshot` / `delta` 批次，流式上传计算大小和 SHA-256；finalize 在批次锁内复核并原子冻结，重复 manifest 幂等复用。
- `import_control/control.sqlite3` 与活动主库分离；`import_sources/<batch-id>/packet|resolved` 保存不可变来源及完整解析视图。API/报告不返回服务端绝对路径或原始身份。
- 发布日志覆盖准备、快照、事实提交、来源准备、指针切换、完成与恢复；活动指针使用 compare-and-swap，启动恢复拒绝来源漂移和后来提交。
- writer lease 同时覆盖线程与进程；应用写连接和七个维护脚本接入共享/独占协调。上传、冻结、事实事务与恢复具有各自明确锁边界。
- noop 在快照、事实写入和派生构建前结束；append/reconcile/replace 在同一事务发布事实、基线、年度分区和 ChangeSet。

### S2：阶段恢复与错误诊断

- 固定阶段为 `metadata → identity_merge → album_project_l3 → billboard_aggregates → candidate_index → critical_prewarm → cover_supplemental → exact_snapshots`。
- 每次 attempt 保存 generation/digest、依赖 revision 向量、输入/输出证据、错误码、trace 摘要和 retryable；重试从失败阶段继续，不重新执行事实 ETL。
- 阶段前后双重事实 fence 与依赖 fence 阻止旧任务覆盖新事实。元数据 provider 不可用或有 errors 时为 `partial`，不会伪装为成功。
- readiness 区分 `facts_committed`、`core_ready`、`ready`、`warming`、`unavailable` 和 `failed`；无 LKG 时不返回虚假 ready/0。
- 发布前硬中止可成套恢复旧库/旧来源；事实提交后的可恢复阶段失败保留新事实。控制库不随主库恢复，失败历史仍可查询。

### S3：关键任务调度与定向处理

- JobQueue 持久保存 priority、resource lane、logical target、generation/revision fence、attempt 和有限重试。
- 关键 CPU、网络与 supplemental lane 分离并保留关键执行能力；重启保持优先级和目标，旧 target 不会吞掉新 generation。
- Billboard、Album Project、候选和四套精确搜索继续以 ChangeSet 证明闭包；不能证明时带原因安全 full fallback。L2/L3 × fixed/dynamic 是当前四套必需公开集合，L1 仅作兼容陈旧证据。
- 1,204 封面排队的确定性测试证明：依赖满足的关键 job 无需等待封面队列排空，低优先级仍能推进。

### S4：兼容身份与未匹配记录治理

- played L3 使用硬门禁，不能因缩小作用域排除真实播放问题；全量零播放/兼容别名进入独立治理账本。
- 33 个全量 identity 样本和 238 条未匹配音频都有唯一主分类或明确 unknown，并保存样本引用、影响播放数/时长、证据与处理状态。
- 当前 238 条拆分为 podcast 222、audiobook 1、unknown 15；原始事实 238 条 / 138,421,062 ms 保持不变。played 范围 6,642 个身份、0 个问题；全量 6,675 个身份、33 个治理项。
- 重复扫描/导入按稳定 issue key 幂等，不重复创建问题；人工覆盖、旧深链和别名解析仍有效。

### S5：设置页、运行历史与报告

- 新 `DataImportWorkspace` 与 `useDataImport` 统一 raw File/FormData 上传、批次/运行 query key、轮询、分页历史、报告、retry/recheck。
- Phone、Compact、Desktop 使用互斥 presentation，但共用 URL、Query 和持久后端事实；主操作触控目标按 44×44px 设计。
- 页面分别呈现数据更新、统计准备和质量事项；展示 baseline missing、noop、增量/协调、输入漂移、失败恢复、warming、无 LKG 和 provider 缺失，不用一个“完成”掩盖阶段状态。
- 旧健康检查、治理预览和账号导入仍保留；刷新或重启后运行历史来自控制库，不依赖组件本地定时器或模块级缓存。

### 验证

- Backend 完整测试：`2416 passed, 680 deselected`；3 个 warning 均另行记录，没有导入范围失败。
- OpenAPI 审计：234 operations，0 unaccounted；参数合同审计：110 obligations，0 unaccounted。
- Frontend Vitest：86 files passed、1 skipped；667 tests passed、4 skipped。
- Frontend production build：PASS；变更文件 scoped ESLint：PASS。
- 全仓 ESLint 仍有 184 个范围外既有问题；正式项目门禁是前端测试与 build，本轮没有借机清理旧债。
- `git diff --check` 与提交 hooks：PASS。

### 明确边界

- 本报告不把 S1–S5 局部证据写成最终 S6 Pass；真实 92,908→94,760 副本、三次可比样本、浏览器和默认完整 fullstack 由最终验收报告单列。
- 没有向 Spotify 发出验收网络请求；冻结 provider 响应与真实外部服务结果分开报告。
- 没有 push、部署或再次写入正式播放事实；本地开发服务曾因 `--reload` 被动应用 migration 79，正式 `plays` 仍为 94,760，未触发导入。

## 数据导入处理与治理 S6 最终验收报告

原记录：`2026-09-21-import-governance-final-acceptance.md`。

> 日期：2026-09-21；二轮、三轮独立复核修复收口：2026-09-22
> 规划：S0–S6 全部实施
> 实现状态：IMPLEMENTED
> 验证状态：PASS（真实隔离副本 + 故障恢复 + 性能 + API + 浏览器 + 默认完整 fullstack）
> Git：S0–S6 已提交 `ae6febc`、`d37c9af`、`37c8431`、`8102f47`；独立复核与追加验收提交 `031075a`、`17002f0`、`7d3d079`、`9dddc89`、`8c5dfc0`；UNPUSHED
> 部署：NOT_DEPLOYED

### 结论

导入事故修复规划的 S0–S6 已全部完成。串流输入、播放事实、指纹基线、活动来源和派生阶段由同一批次与代际证据串联；事实提交后的派生失败不会再默认整库回滚；关键任务不依赖封面队列排空；played 与全量治理范围分别可见；Settings 提供可刷新、可重启恢复的持久导入工作台。

初次收口后又执行了一轮独立破坏性复核。复核在隔离副本中发现并稳定复现三个 P1：默认 snapshot 尾包的活动原始来源缺少历史父链、replace 确认与独占锁之间存在跨进程覆盖窗口、事实事务提交后而控制日志仍为 `prepared` 的硬中止无法向前恢复。三个问题均已重新打开、修复并补入真实编排回归；本报告中的最终结论以追加修复后的证据为准，不再沿用 `8102f47` 时点的旧结论。

2026-09-22 的二轮独立复核又发现一个 P1 升级兼容问题和一个 P2 测试隔离问题：migration 79 的合法 legacy 指纹基线尚无活动来源登记，被来源三元组栅栏误判为漂移；崩溃恢复测试撤销整个 `monkeypatch` 后直接覆盖全局数据库/账号路径，导致后续 Community 测试读取错误数据库。两项均已用先红后绿回归修复；最新结论以 `9dddc89` 代码及本报告末尾的新默认完整门禁为准。

第三轮独立复核进一步证明另一种升级前置状态仍被误判：数据库已有播放事实，但逐行指纹、generation 和活动来源基线全部缺失时，预检正确返回 `baseline_required`，已确认的完整替换却被来源对齐检查提前阻断。`8c5dfc0` 将该状态单独收窄为 `legacy_baseline_missing`，只允许经过确认、锁内重评估和事务基线栅栏的 full replace 初始化；append、未确认执行、部分指纹、控制库已有来源或 pending recovery 仍然 fail-closed。修复已通过专项探针和最新默认完整门禁，尚待第三轮独立复核方重新验收，不能表述为已获独立签收。

最终真实副本从 92,908 条旧事实导入至 94,760 条，新增 1,852、删除 0，保留 2 条迟到记录。三次独立副本运行全部通过 14 项语义对账、四套公开搜索快照、replacement 对照和再次导入 noop。正式 `data` 没有再次导入；本轮没有 push 或部署。

### S0–S5 交付状态

| 阶段 | 结论 | 主要证据 |
| --- | --- | --- |
| S0 | PASS | 父子元数据写入、played/all 范围与 92,908→94,760 事故基线固化；见 [S0 报告](#阶段-s0导入事故修复与测量基线) |
| S1 | PASS | 不可变批次、活动来源 resolver、独立控制库、发布日志、writer lease、成套恢复和 noop 零写入 |
| S2 | PASS | 持久阶段、attempt/证据、generation/revision fence、启动恢复和结构化错误 |
| S3 | PASS | 优先级与资源 lane、target 去重、依赖顺序、1,204 个封面排队不阻塞关键任务 |
| S4 | PASS | played 6,642 个身份无硬问题；全量 6,675 个身份含 33 个治理项；238 条未匹配音频完整分类 |
| S5 | PASS | Phone/Compact/Desktop 共用持久工作台、历史、报告、重试和三维结果；见 [S1–S5 报告](#导入处理与治理修复-s1s5-实施报告) |

### 真实副本正确性

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

### 恢复、隔离与状态边界

恢复/队列矩阵共 190 项定向测试通过，并在最终审计中补齐以下边界：

- durable quarantine 只允许所属 run 穿越，其他 writer 继续 fail-closed；`sources_published` 与 gate 清除由同一控制事务/CAS 完成。
- 启动在 migration 前检查恢复与 gate 状态；证据不足时拒绝继续写入，不让迁移成为隔离窗口内的新提交。
- Year-End warming、无 LKG 但仍有活动 job、自动晋升 ready 和 failed/unavailable 分别映射，不返回虚假 ready 或 0。
- 阶段依赖 revision 排除发布账本、job 和错误记录自身的记账变化；重启时可复用已证明的 `core_ready` 早期阶段。
- 新 generation/revision 取代旧任务时，旧输出不得激活；事实提交后的派生失败只重试正确阶段，不重复播放 ETL。

真实 API 使用 `/tmp/spotifystats-s6-api-v2/spotify_stats.db`。无操作执行前后主库状态与 mtime 不变，未创建 import backup。隔离 helper 同步更新 Home 主库身份与 snapshot root，修复了副本被误判为非主库而无法发布公开 Home 快照的问题。

### 独立复核后的 P1 追加修复

追加修复严格限定在独立复核证明的三条失败路径及其必要证据链：

- 上传输入的 `batch_id` 与最终发布的 `source_version_id` 分离。`snapshot_superset` 可直接发布完整 snapshot；`delta_tail` 若输入本身不能重放完整事实，则在独占锁内从当前活动来源派生 delta 子版本。发布前后均对 resolved 来源的去重指纹 count/digest 与目标事实做语义对账。
- 确认 token 绑定 generation、dataset digest、record count 与活动 source version。取得跨进程独占锁后重新评估并复核 main/control 来源三元组；`import_data` 在 `BEGIN IMMEDIATE` 后、任何 DELETE/INSERT 前再执行事务内 baseline fence，replace 与首次初始化不再绕过旧状态校验。
- 恢复器遇到“主库已提交、控制库仍为 prepared”时，从同一主库事务写入的 `playback_import_state` 与 `playback_import_runs.change_set_json` 读取并严格校验证据，再用 CAS 将控制 run 补齐为 `facts_committed`，之后才发布来源。最终 CAS 仍不直接接受 prepared，证据不足继续 fail-closed。

新增的非 mock 编排矩阵覆盖：空库 full、snapshot superset、浏览器默认 snapshot 尾包、显式 delta、reconcile、replace、持久 noop、replace 事务栅栏、另一进程在确认后完成新发布，以及 `mark_facts_committed` 前硬中止。活动来源同时通过真实 importer 重放，最终 count/digest 与主库一致；noop 不新增备份、不改事实/主库 run/活动来源，仅保留输入批次与控制审计。

追加修复后的本地结果：定向编排 5/5、相关导入组 85/85、完整 unit 1,980 passed / 2 skipped、完整 contract 441 passed、前端 86 files passed / 1 skipped（669 tests passed / 4 skipped）、production build PASS。提交钩子的 ruff、format、mypy 与 secrets 全部 PASS。

最终完整门禁还发现 Community revision 在逐表摘要期间把封面下载、后台任务状态等数据库级并发写入误判为事实漂移，可能让正常 GET 瞬时返回 503。`7d3d079` 将语义摘要固定在一个 SQLite 一致性读快照内；并发提交时本次完整摘要仍可返回但不绑定到较新的 `data_version` 缓存，下次请求重算。新增 WAL 并发回归已通过；真实隔离副本在 80 次封面展示字段提交干扰下连续完成 36 个 Community 请求，全部 200。

### 二轮独立复核：legacy 首次来源登记与测试隔离

`9dddc89` 在独占发布锁内把活动基线明确分类为 `empty`、`legacy_unregistered` 或 `published`。合法 legacy 必须同时满足：指纹版本、事实 count/digest/generation 完整且与预检一致，主库 publication state 为 `legacy`，主库与控制库均无活动 source/publication 指针，并且没有 pending publication 或写隔离证据。已发布状态仍要求 main/control 的 source、generation、digest 完全一致；任何 pending、失配或状态漂移继续 fail-closed，没有放松原有 token、锁内重评估、`BEGIN IMMEDIATE` 事务栅栏和崩溃恢复。

行为矩阵已固定：

- legacy 相同输入的 auto 模式是真正 noop：事实、备份和来源指针不写入，运行明确返回 `legacy_source_unregistered`，界面提示用覆盖全部历史的完整导出执行完整替换。
- legacy 完整超集可在语义对账证明候选来源覆盖目标事实后追加并首次登记；显式 replace 对相同或新增完整输入都通过备份、事实事务和来源发布完成登记。
- 只有尾部数据而无法覆盖现有 legacy 历史时，以 `legacy_source_baseline_requires_full_snapshot` 阻断，并给出完整导出动作；不能构造缺父链的活动来源。
- 预检后竞争发布、已发布 control 指针失配、pending 主库状态和首次登记硬中止分别验证为阻断或可恢复，最终来源仍能真实重放同一事实集合。

测试隔离修复只把故障注入放进 `monkeypatch.context()`；数据库与账号路径继续由外层 fixture 管理，并在崩溃恢复前后显式断言不变。最小顺序和逆序各 2/2 通过；编排、control/source、API contract、Community 四文件组合正序和逆序各 96/96 通过，不再依赖测试运行顺序。

正式数据库只读核对为 94,760 条、fingerprint version 1、generation/digest 完整、source/publication 指针为空、`publication_state=legacy`，与缺陷前置状态一致。SQLite Online Backup 副本使用当前 `data/streaming` 完整导出验证 relation=`identical`；在首次登记的事实提交后模拟硬中止，恢复结果为 completed=1、blocked=0。恢复后主库/control 的 source、generation、digest 指针一致，pending=0、写闸门解除；活动来源在另一全新数据库重放为 94,760 条，指纹集合和 digest 均与副本一致。探针前后正式数据库 SHA-256、inode、大小和 mtime 全部不变。该探针明确跳过无关派生阶段；派生全链由下述默认完整门禁覆盖。

### 三轮独立复核：已有事实但无指纹基线

第三轮复核使用 tracked seed 稳定复现：主库有 117 条播放事实，但 `source_fingerprint`、`source_fingerprint_version`、`import_generation_id` 均为 0 条，`playback_import_state` 的 generation/digest/source/publication 为空、record count 为 0、publication state 为 `legacy`；控制库也没有活动来源或恢复证据。预检返回 `baseline_required`，修复前已确认的 replace/auto 都以 `confirmed_plan_drift` 阻断。

`8c5dfc0` 只在下列证据同时成立时把状态分类为 `legacy_baseline_missing`：主库确有事实；预检是 `active_state_missing`；主状态 generation、digest、source、publication 和 fingerprint version 为空且 record count 为 0；publication state 精确为 `legacy`；逐行 fingerprint、fingerprint version、generation 三类来源证据全部为 0；控制库 source/generation/digest 为空；不存在 pending publication 或写隔离。该分类只允许 `decision=replace`、`confirm_plan=true`、`relation=baseline_required` 的执行继续；其他组合仍按确认漂移拒绝。既有确认 token、跨进程独占锁、锁内重新预检、`BEGIN IMMEDIATE` 事务基线 fence、来源语义对账及崩溃恢复均未放宽。

专项矩阵和原始探针结果：

- missing-baseline 定向矩阵 8/8，完整真实编排文件 22/22；append 与未确认执行被阻断，replace 和 auto 的已确认 full replace 均成功，并在全新数据库真实重放为相同 count/digest。
- 竞争者先完成首次登记后，旧确认按 `confirmed_plan_drift` 阻断；首次登记在事实提交后硬中止，可恢复为 completed=1、blocked=0，主库/control 来源一致且写闸门解除。
- 部分逐行指纹、控制库已有来源、pending run 三种损坏状态均不能冒充合法旧库。
- 未改动的第三轮复核探针由 117 条无指纹事实成功完整替换为 2 条有指纹事实；随后 auto 对相同输入为 ready noop。未改动的上一轮三条 P1 探针和 migration 79 legacy 探针也全部通过。
- 编排、control/source、API contract、Community 四文件按原失败顺序共 104/104 通过；没有依赖测试顺序或全局路径泄漏。

以上均在独立 worktree 和临时 SQLite 中执行；没有写正式数据库、合并主检出、push 或部署。结论是“第三轮缺陷已本地修复并完成实现方验收”，不是“第三轮独立复核已经签收”。

### 性能、API 与浏览器

- ready 基线冷预检三次：5,666.722 / 5,300.994 / 5,539.753 ms，median 5,539.753 ms。
- 独立 21 个 hot 样本：median 69.662 ms、P95 71.258 ms、max 75.725 ms，满足 P95 ≤500 ms。
- 最终默认 fullstack 的 22 轮热 API：Import Preflight median 10.880 ms、P95 12.141 ms；最慢的 `/api/billboard/data` P95 为 345.295 ms，所有监测端点 hot P95 均低于 500 ms。
- API smoke 153/153；OpenAPI 234 operations、0 unaccounted；GET 149/162 覆盖、13 个明确排除、0 unaccounted。
- 独立真实浏览器检查覆盖 Desktop、Compact、Phone：导入 noop 流程、状态/历史、44×44 主要触控目标、无横向溢出、无本机绝对路径泄漏。
- P1 追加修复后再次用真实 Playwright CLI 检查 Desktop 与 390×844 Phone 导入工作台：运行历史与数据健康请求均为 200，Phone `scrollWidth == innerWidth == 390`，可见按钮无小于 44×44 的目标，控制台 0 error；会话验收后已关闭。
- 默认浏览器门禁覆盖完整路由与五档 viewport、桌面/移动交互、图表、长列表、40 组控件 inventory，以及 Chromium、Firefox、WebKit；全部 PASS。

验收中先后发现三处测试合同已落后于新界面/合法状态：导入工作台仍查找旧“串流数据”，移动筛选只接受 unavailable 而不接受 ready，跨浏览器脚本仍使用旧导入文案。三处均改为验证当前非写入合同并补回归测试，随后在同一默认完整 run 中通过。

### 默认完整本地门禁

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

### 数据与交付边界

- 三次真实导入和 API/浏览器使用隔离副本；正式播放事实保持 94,760。开发服务此前仅被动应用 migration 79，没有再次导入或执行治理清理。
- 机器可读 raw samples 保留在本机 `/tmp/spotifystats-s6-real-sample-{1,2,3}.json`，不提交真实数据、SQLite、缓存、恢复点或本机路径明细。
- 原事故 HTTP 500 缺少足够历史堆栈，仍标记为“根因未证实”；本轮交付的是结构化诊断、限定重试和已证明路径，而非猜测根因。
- 没有自动清理 33/238 治理项，没有删除历史恢复点，没有 push、正式数据迁移或部署。
- 本轮分支仍未合入主检出；主检出仅保留用户原有 `data/governance_cache.build.lock` 与 `data/import_backups/` 未跟踪项，本轮未修改或清理。
