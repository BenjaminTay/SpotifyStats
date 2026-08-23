# 数据导入与健康检查

## 目标

数据导入区只负责两件事：在导入前确认本地 Spotify 数据包可读，在导入后说明数据库、关系、元数据和派生统计是否可继续使用。健康检查是只读的，不会修复、删除或覆盖原始播放事实。

## 与现有导入流程的关系

当前导入流程仍由 Settings 页面触发：

1. 串流数据导入读取 `data/streaming/Streaming_History_Audio_*.json`，写入基础播放、曲目、专辑和艺人数据。
2. 账号数据导入读取 `data/account/` 下的 Account Data JSON，补充收藏、歌单、Wrapped、搜索记录等非播放数据。
3. 串流导入完成后继续执行 Spotify 曲目、专辑和艺人元数据维护，补齐本地实体的封面 URL，并为播放历史中有 URL 但缺文件的专辑和艺人排队下载。
4. Album Project 和 Billboard 预聚合发布后，先预热最新完整榜单与首页；六套音乐查找精确统计快照随后转入后台维护，兼容的同一开放周尾部追加可走 snapshot delta，其余情况整组六套 shared-full 重建；年度总结预热等精确快照完成后再启动，避免与首屏争抢资源。
5. 封面下载按“实体类型 + 实体 ID”去重，校验 HTTP 状态、图片签名和最小大小，采用临时文件原子替换；失败会真实记录并在上限内重试，不再把下载失败记作完成。
6. 快照未完成时搜索候选和详情深链仍可用，精确播放/榜单摘要显示为 warming，不显示虚假的 0。健康报告重新读取数据库状态，帮助判断维护是否完成；它不改变以上导入语义。

## 导入前检查

`GET /api/import/preflight` 只读检查本地文件，并把输入记录与当前数据库的持久化指纹基线进行比较：

- 必需输入：至少一个可解析且非空的 `Streaming_History_Audio_*.json`。
- 可选输入：视频历史和 Account Data 文件。缺失只产生提示，不阻止串流导入。
- Streaming History 会检查顶层数组、`ts` 时间戳、记录数量和 `ms_played` 字段提示。
- JSON 解析失败、必需文件缺失或音频历史为空会标记为 `blocked`。
- 预检还会计算串流文件 SHA-256，识别完全重复文件；同一文件内的完全重复记录会计入 `duplicate_record_count`。
- `date_overlaps` 只表示两个文件的日期区间相交，不直接等同于重复播放；每一对会附带 `shared_record_count`，用于区分“边界日期相交但记录不重复”和“确有共同记录”。
- 完全重复文件会进入 `blockers`；文件内重复记录、日期范围重叠和跨文件共同记录进入 `warnings`。导入时只对完全相同的记录自动去重，保留同一内容在稳定文件顺序中的第一次出现；日期重叠不会被当成重复，也不会自动合并。源 JSON 永远不会被修改。
- `POST /api/import/streaming` 会在后台任务真正创建快照前再次执行这份预检：有 `blockers` 时任务状态为 `blocked`；只有 `warnings` 且未传 `confirm_warnings=true` 时状态为 `needs_confirmation`；确认后才会进入计划执行。

增量导入 Phase A–E 使用以下证据与执行规则：

- migration 37 为播放事实预留版本化源记录指纹和导入代际，并建立单例活动状态与导入运行记录表；升级前已有播放不会从不完整的数据库列反推原始 JSON 指纹。
- 预检会从音频、视频记录生成与文件名、文件顺序和重新分包无关的 dataset digest，并返回指纹基线状态、账号身份匹配状态、输入与活动数据集的关系、增删复用数量、日期范围和预计影响的周/年数。
- Account Data 中的稳定用户名只用于生成带命名空间的不可逆 SHA-256；API、日志和导入运行表均不返回或保存原始用户名。
- 旧库没有完整指纹基线时返回 `baseline_required`；相同、超集、尾部增量、历史增删、不完整/倒退、不同账号和证据不足会分别返回明确关系。不能证明时不会自动追加、替换或删除。
- `GET /api/import/preflight?mode=auto|append|replace` 始终只读；Settings 中的计划卡片解释关系、复用范围和预计策略。
- `POST /api/import/streaming` 默认 `mode=auto`：空库可直接完整导入；已有播放但缺少指纹基线的旧库无法证明输入包覆盖全部历史，必须明确确认后才完整替换并写满指纹。`identical` 在创建数据库快照前结束为 noop；`snapshot_superset` 和“与活动数据存在共同记录、账号证据相符且全部新增记录位于尾部”的 `delta_tail` 只写新增播放。
- 同账号输入同时存在新增和移除、且时间包络覆盖现有首尾时，auto 只会提出需要确认的 `reconciled_snapshot`；确认标识仍绑定输入文件和当前基线。确认后在一个写事务中精确删除旧身份、插入新增身份，并核对最终 count/digest 等于输入快照。时间包络或账号证据不足时不会自动把缺失记录解释为删除。
- 完全无共同记录的晚期数据包不会仅凭固定 Account Data 目录中的账号文件自动追加，因为账号文件未必与本次串流包同源。Settings 可让用户明确选择“作为尾部增量验证”；后端会重新按 append 证据 fail closed，验证失败不写入，也不会删除历史。
- 警告确认和完整替换确认必须携带预检返回的 `confirmation_token`。这个标识绑定输入记录、文件检查结果、账号证据和当前活动数据集；文件或数据库在两次请求之间变化时，旧确认失效并要求重新核对。
- `append` 不会把输入中缺失的旧记录解释为删除，也不能绕过指纹基线、账号身份和尾部证据；证据不足时 Phase B 阻断追加。`replace` 对风险关系要求 `confirm_plan=true`，确认后仍先创建 SQLite 快照再完整替换。
- noop 只更新导入状态摘要并记录运行结果，不提升播放或派生 revision，不重建 Billboard、搜索快照、年度结果或封面任务。
- append 完成基础事实发布后，会在同一事务生成并持久化 `PlaybackChangeSet`。Spotify 曲目、专辑、艺人元数据和封面只处理相关实体，同时从全局缺失事实中有界抽取历史失败项重试；年度播放分区只从最早受影响年份向后更新，旧年度仍可复用。
- 已证明的尾部追加会为 Billboard 扩展旧、新连续播放链和跨周时长贡献闭包，只重算受影响完整周；非尾部变化、闭包证据不足、依赖不兼容或受影响周超过 25% 时回退完整聚合。四张周聚合在影子表中共同校验并原子发布。
- 搜索候选仍整体重建。migration 42 为六套精确搜索上下文增加稳定策略键、来源代际、数据集 digest、基础 snapshot、构建策略与依赖 digest，并保存按候选实体键归一化的周榜账本；第一次兼容构建仍使用 `shared_full_snapshot_rebuild`，两个阈值作用域各自复用逻辑帧并在三个 merge level 间共享计算，六套全部成功后才共同激活。
- 已证明的尾部追加如果完全落在同一个当前开放榜单周、没有影响任何已发布完整周，并且六套基础 snapshot、周账本、候选与统计语义依赖全部兼容，则复制旧上下文和周账本，只把新增逻辑播放贡献应用到歌曲、L1 专辑、L2/L3 Album Project 和有效署名艺人的 lifetime 指标，再整组六套原子激活。
- 精确尾部追加若恰好跨一个开放周，则有界读取新完成周及必要的前后连续播放链，重建 fixed/dynamic、L1/L2/L3 的歌曲、专辑和艺人周账本；旧历史周直接复用，当前开放周仍不发布。合并账本后按稳定实体 ID 全局重算 peak、在榜周数与 Power score/rank，同名不同 ID 的实体不会合并。
- 两条搜索 delta 路径执行前后都会复核基础 snapshot、活动事实代际、候选与统计依赖，报告策略为 `incremental_snapshot_delta`，且不扫描完整 lifetime 播放事实。多周跳跃、存在删除/历史修正、缺少兼容 lineage/账本、依赖变化、合并关闭、闭包超过 100,000 行或其他成本门禁失败时安全回退 D1 `shared_full_snapshot_rebuild`。
- Album Project 目前仍完整重建，但自动推断项目会按稳定语义键复用 ID，并精确替换 membership，避免相同输入重建导致搜索实体身份漂移。当前不能把基础追加、scoped 元数据、Billboard 局部耗时或搜索 snapshot delta 等同于整个导入任务耗时；Album Project 定向维护仍待后续阶段。

检查不会把文件导入数据库，也不会启动后台 Job。确认文件后，用户仍需显式点击已有的「导入串流数据」或「导入账号数据」。

## 导入后健康报告

`GET /api/import/health` 返回四组信息：

| 区域 | 检查内容 | 用途 |
|------|---------|------|
| `database` | 播放数量、音频/视频数量、有效音频数量、日期范围、空曲目、负时长、SQLite 完整性、外键问题 | 判断基础库是否可读、是否存在明显坏数据 |
| `relationships` | 播放→曲目/专辑、曲目→主艺人和曲目署名关系 | 判断统计链路是否会丢掉有效播放 |
| `metadata` | 最近 90 天的曲目与来源专辑、Spotify 元数据、Album Project 覆盖 | 判断新导入内容是否需要维护 |
| `derived` | 周聚合、Album Project、Billboard 聚合、artist identity/track credit revision | 判断下游页面是否与当前事实同步 |

状态含义：

- `healthy`：没有发现问题。
- `partial`：有历史外键残留、元数据缺口或其它非阻断提醒，但核心播放关系仍可用。
- `stale`：派生统计或治理 revision 尚未同步。
- `blocked`：没有播放数据、SQLite 完整性检查失败，或播放记录引用了不存在的实体。

外键检查会按「子表 → 父表」返回明细。历史元数据孤儿记录不会自动删除，也不会仅凭健康检查改写 `plays`、`tracks`、`track_artists`；后续如需清理，必须单独设计可预览、可回滚的维护任务。

## 可行动问题

健康报告同时返回 `issues`。每个问题包含：

- `severity`：`critical`、`high`、`medium`、`low`；
- `count`：该问题关联的记录数；
- `affected_play_count`：已知直接影响播放事实的记录数；
- `impact`：对当前统计的影响说明；
- `recommended_action`：下一步建议；
- `evidence`：关系拆分、检查日期等证据。

具体关系问题会优先展示，外键总数仍保留在 `database.foreign_key_issue_count`。这样同一批孤儿记录不会在用户界面被重复计算；例如当前真实库外键总数为 7,831，但已去重后的问题列表显示曲目/专辑艺人关系、其他历史任务关系和专辑关系等 6 类问题。

## 当前边界

当前只处理可以被完整记录内容证明的重复，不加入近似重复判断、日期合并或根据歌曲名称猜测重复。艺人封面只接受曲目 API 的精确艺人关联或规范化名称完全相同的搜索结果；没有可验证来源时保留未知，不使用相似名称的第一条结果。精确音乐查找快照属于导入后的可恢复派生维护，不影响基础播放事实和 Billboard 完整周榜可用性。

## 第二轮：导入安全边界

当前串流和账号导入在实际写入前都会尝试创建 SQLite 一致性快照，快照使用 SQLite backup API，能够覆盖 WAL 中已经提交的内容。快照放在 `data/import_backups/`，不会写入 Git，也不会被自动删除。

- 已有数据库：快照创建失败时，导入不会开始；导入或串流导入后的维护失败时，系统尝试恢复导入前快照。
- 并发边界：同一进程内只允许一个数据库导入任务；已有导入运行时，后续任务直接标记为未开始，不创建快照、不修改数据库。
- 导入门禁：串流导入会重新核对最新文件状态，避免用户查看预检后文件又发生变化；账号数据导入不受 Streaming History 文件门禁影响。
- 首次导入：数据库尚不存在时，快照状态为 `skipped`；如果这次首次导入失败，系统会清理本次创建的半成品数据库。
- 导入任务结果：成功结果包含 `database_snapshot`；失败结果包含 `database_snapshot` 和 `rollback`，其中 `rollback.status` 为 `restored` 表示已有数据库已恢复，`removed_new_database` 表示首次导入半成品已清理，`failed` 表示需要停止继续导入并人工检查。
- 串流导入成功结果还包含 `duplicate_records_skipped` 和 `post_import_health`。后者只复核 SQLite 完整性、播放记录数量和播放→曲目/专辑关系；这些硬指标失败会按导入异常进入已有回滚路径，普通元数据缺口仍只显示为 `partial` 提醒。
- 回滚后会清空运行时统计缓存，避免页面继续使用失败导入产生的旧派生结果。

当前已完成增量导入 Phase A–E。写入任务仍保留 SQLite Online Backup；append 与 reconcile 都在一个事务中批量写入，并在同一次提交内精确核对输入关系、实际新增/移除、活动 count/digest 和事实代际；导入器异常时显式 rollback 并关闭写连接，随后才允许快照恢复。

派生维护仍在活动事实发布后执行。事实、活动代际、年度分区和紧凑 ChangeSet 会在同一事务提交；维护完成前导入运行记录保持 `maintenance_pending`。应用启动会先严格反序列化 ChangeSet，再核对活动代际、指纹版本、实际记录数和数据集摘要；证据一致时通过持久队列幂等恢复维护，证据无效或事实漂移时标记 `recovery_blocked`，不会把旧派生结果冒充为成功。播放缓存会在事实提交后立即失效，Billboard 聚合只能在活动代际未变化时原子发布。封面后台任务会在进程重启后恢复 pending/orphan running，过期 URL 任务不能覆盖新来源。完整 replace 的清空、批量写入、ChangeSet 与活动状态发布位于同一个写事务，进程内异常可直接回滚；导入前 Online Backup 继续作为跨进程硬中止与维护失败的外层恢复边界。六套搜索快照已经具备整组原子发布、代际栅栏，以及同一开放周和恰好跨一个开放周的实体级 delta；历史修正走精确 Billboard 周替换与搜索 shared-full 安全回退。

Billboard 四张预聚合已经支持精确尾部变化的周分区更新：局部旧/新逻辑帧包含可合并的完整前序链，时长贡献按周切片，变化以有符号差值应用到四张影子表；固定与动态阈值证明的影响周取并集，无法证明闭包时仍安全回退全量。六套搜索统计已完成同周和恰好跨一个开放周追加的 snapshot delta；多周或历史变化仍回退 shared-full。年度分区已经额外覆盖跨年收听区间和可合并的前序连续链。

历史 reconcile 使用独立的旧、新有序事实视图，从增删位置及相邻记录向前后闭合相同 track/source 连续链，并比较 fixed/dynamic 两套贡献。变化只涉及完整历史周、活动代际和统计依赖一致、闭包不超过 100,000 行时，从当前事实有界重算并替换目标周四张聚合；开放周、证据或成本门禁失败时全量重建。Album Project 仅在无删除且实际元数据影响闭包精确时定向重建；其他情况全量回退。历史 reconcile 的搜索六变体继续使用 shared-full。

## 相关代码

- 后端文件检查：`backend/domains/imports/source_inspector.py`
- 增量关系分类：`backend/domains/imports/incremental.py`
- Phase B 执行动作：`backend/domains/imports/execution.py`
- 指纹基线与运行记录：`backend/domains/imports/state.py`
- ChangeSet 与年度播放分区：`backend/domains/imports/change_set.py`
- 搜索 snapshot lineage、周账本与增量发布：`backend/domains/music_search/snapshot_lineage.py`、`backend/domains/music_search/snapshot_delta.py`、`backend/domains/music_search/snapshot_ledger.py`、`backend/domains/music_search/snapshot_week_delta.py`
- 尾部逻辑播放差值：`backend/domains/playback/logical_delta.py`
- 增量元数据与封面维护：`backend/domains/metadata/spotify_refresh.py`、`backend/services/cover_cache_service.py`
- 只读导入计划：`backend/services/import_plan_service.py`
- 导入快照与回滚：`backend/domains/imports/database_snapshot.py`
- 后端健康报告：`backend/domains/metadata/import_health.py`
- API：`backend/api/import_.py`
- 前端入口：`frontend/src/features/settings/components/DataImportSection.tsx`
- 前端查询：`frontend/src/hooks/useDataImportHealth.ts`
