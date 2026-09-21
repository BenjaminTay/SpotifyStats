# 2026-09-21 Spotify Extended Streaming History 导入复盘报告

## 结论

本次导入已完成。下载目录中的原始串流 JSON 已替换到 `data/streaming`，SQLite 数据库已通过应用导入流程更新，导入后维护、音乐查找快照和 Billboard 快照均已完成。

本次不是增量导入，而是一次受确认保护的完整导入。原因是旧数据库没有可用的持久化播放记录指纹基线，系统无法安全证明旧数据与新导出之间的新增、删除和不变集合，因此按 fail-closed 策略回退为 `full`。本次成功后已经写入基线；导入同一份数据的预检结果为 `identical`、`estimated_strategy=noop`，后续新导出可以进入可比较的增量判定链路。

## 范围与输入

- 执行时间：2026-09-21（Asia/Shanghai）
- 源目录：`/Users/benjaminlei/Downloads/Spotify Extended Streaming History`
- 应用原始数据目录：`/Users/benjaminlei/Code/202605-SpotifyStats/data/streaming`
- 数据库：`/Users/benjaminlei/Code/202605-SpotifyStats/data/spotify_stats.db`
- 账号导出数据不在下载目录中，因此保留了 `data/account`，没有用不完整的下载目录覆盖它。

源目录和 `data/streaming` 最终文件集合一致、逐文件 SHA-256 一致；两边 JSON 原始记录数均为 94,854。导入器对文件内重复记录去重后写入 94,760 条播放事实，少 94 条重复记录。

## 原始文件替换与保护

替换前先创建了原始数据备份：

- 备份目录：`data/import_backups/streaming_before_20260921T122048+0800`
- 清单：`data/import_backups/streaming_before_20260921T122048+0800.manifest.txt`
- 替换方式：保留 `data/account`，仅对 `data/streaming` 执行带删除同步，使目录内容与下载目录一致。

数据库导入由应用自身创建 SQLite 快照并负责失败回滚。本次成功导入使用的数据库快照为：

`data/import_backups/spotify_stats_20260921T050216Z_055c43a59eaf_0fe0948b.db`

## 首次预检与“为什么没有增量导入”

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

## 失败过程与根因

应用每次失败都创建数据库快照并恢复旧库；没有把半成品数据库留在活动路径中。

### 1. Spotify 元数据刷新阶段外键失败

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

### 2. L3 专辑归属出现 33 个未解决问题

- 任务：`248aa9ed7e39`
- 失败信息：`post-import L3 album attribution has unresolved issues: 33`
- 快照：`data/import_backups/spotify_stats_20260921T042953Z_248aa9ed7e39_1e98fcaa.db`
- 回滚：成功

第一次修复尝试让导入维护在 L3 规划前执行影响范围内的 Album Project 修复，但问题仍然存在。

### 3. L3 问题复现与第二次修复

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

## 成功导入结果

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

## 基线建立后的验证

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

## 自动化验证

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

## 后续修复与优化建议

按优先级建议：

1. **P1：将原始文件替换纳入可恢复事务边界。** 目前原始 `data/streaming` 替换和数据库导入是两个阶段：数据库失败时数据库会回滚，但原始文件已经是新版本。当前通过备份可恢复，长期应使用 staging 目录，在数据库成功发布后再原子切换原始目录，或把原始 manifest 版本写入导入事务并提供一键回滚。
2. **P1：把 baseline missing 变成明确的一次性初始化流程。** 预检应直接展示“当前库没有可比较基线，需要一次完整导入”，并将确认后的 full import 标为 `baseline_initialization`，避免用户把它理解成增量设置失效。
3. **P1：优化导入后的后台任务优先级。** 本次导入排队了 1,204 个封面下载，音乐查找和 Billboard 任务先处于 pending，直到封面任务处理完才完成。建议为导入后关键派生快照设置独立队列或优先级，避免用户看到长时间 warming。
4. **P2：完善 L3 范围合同。** 将“完整治理覆盖”和“导入阻断覆盖”两个范围写进文档及指标，分别报告 `all active L1` 与 `played L3 work`，避免零播放兼容维度再次被误报为播放导入故障。
5. **P2：改进预检与后台锁竞争的可观测性。** 导入刚完成、后台任务仍在运行时，HTTP 预检曾短暂返回 500；稍后重试恢复，服务层直调结果正常。应记录异常堆栈、preflight key、job id 和数据库 revision，并对只读预检提供短重试/明确的 warming 响应，避免返回无上下文的 Internal Server Error。
6. **P2：细化重复与边界文件提示。** 94 条重复记录和 5 组边界日期重叠均被正确处理，但预检可进一步显示重复指纹样例、跨文件共享计数和“导入器将保留一条”的明确说明。
7. **P3：跟踪 238 条无曲目音频记录。** 保留原始事实，增加来源字段分布和可解释分类，确认哪些是 Spotify 原始无元数据、哪些是可通过别名/URI 修复的记录。

## 当前边界

- 本次没有执行 Git commit 或 push。
- 没有覆盖 `data/account`，因为用户下载目录不包含账号导出数据。
- 未删除任何原始播放记录；导入器只按源指纹去重，并保留了失败数据库快照和原始目录替换前备份。
- 报告记录的是本地数据库、应用 API 和后台任务证据，不代表任何 staging/生产环境已部署或验收。
