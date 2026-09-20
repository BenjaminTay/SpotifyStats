# 默认播放分析结果快照

阶段 3A 只覆盖 `GET /api/analysis/stats`、`GET /api/analysis/records`。原始 builder、逻辑播放事件、时长切片、L2/L3、艺人 fan-out 均保留。图表、实体详情、Community、Archive 不使用此存储。

## 存储与读取

- 独立 SQLite sidecar：`SPOTIFY_STATS_ANALYSIS_CACHE_PATH`；未配置时为 `data/analysis_cache.db`。不复用 Billboard，也不往主库保存 payload。
- family 分别为 `analysis_stats`、`analysis_records`。请求始终使用 readonly 连接读取 sidecar；不存在时不创建文件或表。
- payload 为 JSON + zlib，记录 raw bytes、SHA-256、builder version、来源 revision、创建时间。完成解码校验和 response model 校验后才允许维护发布。
- 单事务插入与淘汰，每 key 最多两代，全文件最多 16 个 request key；保留上次成功结果。JSON 上限 32 MiB/行；不是 DataFrame 对象缓存。SQLite 文件保留可复用空闲页，不在请求中 VACUUM。
- exact 返回 `snapshot.status=ready`、`freshness=current`；同 key 的旧发布返回 `warming/last_known_good`。`warming` 表示目标事实尚未发布，不能据此断言后台任务一定仍在运行。
- 无兼容发布、key 异常、来源依赖缺失返回结构化 503 `snapshot_unavailable`。不返回假零，不跨参数借 LKG。两种 surface 的 GET 都不构建、不写、不排队。
- 前端复用 `SnapshotStatusNotice` 展示旧发布；两个页面区分暂不可用与一般错误，不再把错误留在 skeleton。

## Request key

规范 JSON 摘要包含 family、数据文件 lineage、builder version、规范化过滤参数、解析后的范围。本期允许发布的范围仅 lifetime：start/end 均为 null，表示无边界，而非最新一条播放的日期；无效的 lifetime 日期参数统一忽略。

公共字段：`min_ms`、`music_only`、`merge_enabled`、`dynamic_threshold`、`max_merge_gap_minutes`。缺省最大合并间隔从 settings 读取。Records 额外包括 `merge_level`、`include_compilations`、`PLAYBACK_RECORDS_SORT_CONTRACT_VERSION`。自动维护只使用实际 settings 的过滤参数、dynamic=true，以及 lifetime L2 / compilation=false。

已知的非 lifetime 范围 GET 明确 unavailable；空或未知 period 沿用原 builder 的 lifetime 回退语义，在构造 key 前统一规范化。本期不为任意日期提供持久构建入口。已由受控维护显式发布的其他 lifetime 过滤/L3 变体可以读取，但不会由 GET 自动生成。历史 key 受上述 16-key 上限约束。

完整只读 smoke / boundary 契约通过私有 fixture 真实发布两个默认 family 后再请求 GET；不得通过改成预期 503、返回假零或在 GET 中构建来消除测试失败。

## 来源 revision 与失效

`analysis_snapshot_revision.py` 列出实际表依赖，按稳定主键顺序摘要完整语义列。不是 MAX(ts)、mtime 或“缺失则 0”。

| 依赖 | stats | records |
|---|---|---|
| active generation、dataset digest、playback_revision、全部原始播放事实 | 是 | 是 |
| 原始 track/album/artist/credit、L1 身份/所有权/别名、时长元数据 | 是 | 是 |
| Track Group、有效艺人身份/署名覆盖 | 是 | 是 |
| Album Project membership、L3 attribution、可靠发行日期 | 未调用这些投影 | 是 |
| approved 流派/语言、taxonomy/语言 registry version | 是 | 否 |

旧库没有 generation/dataset digest 时仍摘要真实 plays；不把 null 冒充已知 revision。身份和项目的管理事件计数也会因显示名称变化递增，故这些依赖使用完整语义投影摘要作为 revision，而非只使用管理计数。封面、显示名称、审计时间/说明、流行度与 follower 等非统计列排除；原始曲目/专辑/艺人名称属于不可变来源，仍参与。快照内展示字段保留发布时值，单纯更新封面/显示名称不会重建统计事实。

数据身份为文件 device/inode lineage，不是绝对路径，也不声称是账号身份。同文件重启可以命中；Online Backup、替换主库或复制 sidecar 到其他数据库，不允许借用原库 LKG。

每个进程持有最多四个只读 `PRAGMA data_version` observer：仅在没有新 commit 时复用来源摘要；任意 commit 后重新检查语义列。无关 settings/任务状态提交会重新校验，但相同语义不产生新 key 或构建任务。旧库首次完整来源校验计入 GET 耗时，不隐藏在启动等待中。

## 维护与并发

- private 启动注册 `analysis_snapshot_rebuild`，只维护两个默认 lifetime；exact 已存在时不排队。
- 已有 settings/import/version-merge/metadata/music-metadata/artist-identities 成功写请求完成后检查默认 key。import maintenance、artist identity、track credit 后台任务成功后再次检查，覆盖异步提交。
- 只给缺少 exact 的 family 排队；pending/running 按 job type + family + request key 去重。CPU-heavy gate 与其他重型维护共享单个执行槽。
- 构建锁使用 primitive request key + source revision，锁内再次检查 exact；四个同 key 构建请求只执行一次 builder。不同 key 不共用构建锁。
- 构建前后检查 source fence，变化时失败并交给现有 JobQueue 重试；不得用旧 target 覆盖当前成功发布。失败状态/错误由 JobQueue 记录，LKG 保留。
- 旧即时 service 的 LRU singleflight 移至不含 SQLite Connection 的 wrapper；用户 API 已改读结果快照。

测试隔离在应用导入前设置 analysis 临时路径，见[后端测试隔离](backend-test-isolation.md)。本地临时副本实测与未达标项见[阶段 3A 报告](../reports/2026-09-19-analysis-result-snapshots.md)。


## 阶段 3B：Records 局部实现约束

Records 来源摘要按512行批量读取 tuple 并更新哈希；使用与旧逐行实现相同的 `repr(tuple(row)) + "\n"` 字节流、列顺序和行排序，不改变 request key/source revision/builder version。Stats 继续原摘要分支。完整来源扫描仍计入首次 GET，没有放到启动 warmup。

Records 单次 builder 内批量读取可信原版 Album Project 成员和 Spotify 候选，canonical song key 一次生成；event/duration 共用 membership。映射随调用结束释放，不形成持久或全局中间缓存。原版可信条件和 L2/L3/compilation 参数不变，fallback 总曲目查询保留原 LIMIT 1 选择。

`records_duration_frame(copy=False)` 仅供只读聚合使用；需要修改或 attach 的调用继续独立复制。Yearly preloaded event/entity frames、年度范围及 milestone 语义保持不变。快照 GET 仍走完整 Pydantic/JSON/GZip 校验与响应链路，没有 raw JSON 绕行。

本地实测、逐字段对账和未达标项见[阶段 3B 报告](../reports/2026-09-20-records-read-build-optimization.md)：warm/RSS/并发边界通过，exact 首读 P95 和重建中位数尚未达到目标。


## Records 单次构建共享事实（阶段 3C）

`RecordsDurationFacts` 只在一次 Records builder invocation 内存在。完整、有序的 `(start_ns, end_ns)` 区间序列是内存复用键，小时边界和逐切片毫秒取整仍由原 `explode_listening_slices()` 计算。event 与 artist 分别从自己的源行恢复身份、有效 credit 和顺序；共享的是切片几何，不是事件数、实体归属或聚合结果。范围过滤在各自附着时执行；Yearly 已切片的预加载 frame 不再 explode。实体 frame 准备完成后释放 context，不形成跨请求缓存。

Longevity 为 track、album、artist 分别建立一次 facts。streak/comeback 共用实体级日期 presence 与双轨累计值；span/month 共用含名称的原分组口径，保留 null 分组排除规则，不从实体级总数推导。消费端只读取 facts，对榜单表取得独立 copy 后排序和裁剪；原 tie-break、Top 50、日期和展示字段不变。

阶段 3C 不改变 snapshot key、source revision、builder version、LKG、失效或发布合同，也不改变共享 logical timeline 和 loader。完整字段对账、独立进程实测与停止结论见[阶段 3C 报告](../reports/2026-09-20-records-invocation-facts.md)。
