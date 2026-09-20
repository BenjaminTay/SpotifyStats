# Community 持久读模型

> 当前合同：阶段 6A；本地验收见 [交付报告](../reports/2026-09-20-community-read-model.md)。

Community 的 feed、trending、post GET 只读取已发布 SQLite sidecar。打开页面不构建历史帖子、不排队；private/public 行为一致。`POST /api/community/refresh` 是 private 维护入口，按完整 Billboard 参数幂等排队；public 禁止调用。启动、播放导入/身份/credit/Billboard 维护完成，以及设置/元数据/收藏同步写入后的维护钩子确保默认投影。失败任务沿用 JobQueue 重试；终止失败后可重新 refresh。

## 身份与失效

- 默认文件与当前主库同目录，名为 `community_cache.db`；可通过 `SPOTIFY_STATS_COMMUNITY_CACHE_PATH` 指定独立路径。主库不新增 Community 表。
- semantic request key 包含数据库 file-lineage namespace（device/inode）、规范化的完整 Billboard 参数（含 year、merge_enabled、merge_level、dynamic_threshold、compilation、TopN、周边界、合并间隔）、builder `community_rows_v1` 和内容政策 `completed_weeks_time_capsule_v1`。
- 精确 revision 对实际播放投影、identity/credit/Album Project/L3 membership、预聚合配置、收藏事实求确定性摘要；兼容没有 dataset digest 的旧库，不用 TTL、MAX(ts)、mtime 或行数充当来源版本。复用 analysis 的依赖表定义，Community 使用 SQLite JSON 编码和有界分批读取。`PRAGMA data_version` 仅使最多四个连接的进程内摘要失效，不充当事实 revision。
- 封面 URL、display 字段与管理时间戳不进入事实摘要。封面映射按当前返回实体从主库读取，不因换封面重建历史文案。
- account/tag/date/search/post_type/highlights/significance 是已发布完整 generation 的 SQL 读取投影，不各建重复历史；不同 Billboard 参数绝不借用其他 key 的 LKG。

## 发布与存储

`generations` 保存 revision；`active` 保存 active/previous 指针与失败目标。`posts` 按 generation/ordinal 保存事实 JSON 及可查询列，`tags`、`entities` 保存索引投影。帖子稳定排序继承原 Python stable sort；同一 generation 的 ID/content 不因 GET 或 ensure 改变。模拟互动字段不持久化。

维护以私有文件锁及 singleflight 串行化，同一目标后继调用复查 exact。所有 staging INSERT、最后来源/配置 fence、active 切换和 pruning 位于一个 SQLite 事务；失败回滚，不替换 active。每个 semantic key 保留 active 和 previous，旧代行在发布事务中删除，SQLite 空闲页可复用。sidecar 使用 rollback journal，避免 WAL 新副本的只读初始化竞争；读连接使用 `mode=ro`、`query_only` 和读事务。构建期继续读取旧代，发布事务提交时遵守 SQLite 读写锁。

构建的核心 payload/search 字节预算为每代 20 MiB；索引和 SQLite 实际文件大小另行测量，不把逻辑预算冒充物理磁盘上限。GET 不创建索引缓存或载入全历史 JSON。

## 读取与展示

- feed：SQL 筛选、count、稳定 ordinal 的 LIMIT/OFFSET 后，只反序列化返回页。`total_all` 不含 highlights 限制，其他过滤与 total 相同。
- trending：实体提及 GROUP BY，平票沿用首次出现顺序；直接读取最新 no1/debut 候选。保留原 `debut` 类型匹配语义，不自行更改为其他类型。无封面或互动补全。
- post：索引查 ID；同日、共有实体、其他账号的最早候选，每账号一个、最多四条回复。只反序列化目标及最终回复。
- 展示补全：按返回帖子关联的 track/artist/album 分批查询封面映射；模拟 metrics 沿用既有范围和字段，按返回集合生成。
- exact：200，`snapshot.status=ready`、`freshness=current`；兼容旧代：200，`warming/last_known_good`。失败目标另有 `build_status=failed`，保留旧事实。完全缺失/不兼容：503 `snapshot_unavailable`，不得转成空社区。
- 页面继续等待 settings ready，Query key/signal 保留阶段 2B 的筛选与迟到响应隔离。共享 SnapshotStatusNotice 支持无限分页的 pages，以及 failed-LKG；account/post 同样显示明确 unavailable 文案。

## 构建语义

阶段 4 的完整 ranked weekly facts 是 invocation 内临时共享对象，持久 sidecar 是 API 投影，不能证明它能无损回答 Community 的全部候选。因此本实现没有复用已发布 Billboard payload，也不从公开 GET 触发其构建。后台复用现有 raw loader、排名函数、有效署名与 canonical artist 规则；从同一次加载的独立次数/时长贡献行派生艺人输入，避免第二次完整 raw 加载。

兼容的主库预聚合可由既有校验器选择；动态阈值、merge gap、merge_enabled 全部传入。Community 排除最新播放所在开放周，完成周使用原周结束时间。时代总结必须在最后完整周结束后发布；此前开始周时间戳提前暴露全周事实的问题已修正。其他周序历史 state、文案变体、字段与帖子生成规则保持。

内部 `generate_all_posts()` 保留给既有 read-only 调用者；页面和 API 已脱离该入口。维护使用 uncached `build_publication_posts()`，不让旧 TTL 内容进入新 revision。
