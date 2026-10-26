# 增量导入阶段与最终验收

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。按A、B、C、D1、D2、E至最终验收排列。早期Partial及未实施只说明当时阶段，最终闭环不追改旧样本；各阶段输入、版本及增量与全量等价性证据保留。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [增量导入 Phase A 交付报告](#增量导入-phase-a-交付报告)
- [增量导入 Phase B 交付报告](#增量导入-phase-b-交付报告)
- [增量导入 Phase C 交付报告](#增量导入-phase-c-交付报告)
- [增量导入 Phase D1 交付报告](#增量导入-phase-d1-交付报告)
- [增量导入 Phase D2 交付报告](#增量导入-phase-d2-交付报告)
- [增量串流导入 Phase E 交付与验收](#增量串流导入-phase-e-交付与验收)
- [串流数据增量导入最终闭环验收](#串流数据增量导入最终闭环验收)

## 增量导入 Phase A 交付报告

原记录：`2026-08-23-incremental-import-phase-a.md`。

> 验收日期：2026-08-23
>
> Phase A 状态：Pass
>
> 完整增量导入状态：Partial；Phase B–E 尚未实施

### 交付范围

本轮只交付持久化结构和只读关系判定，不改变现有串流导入的覆盖式写入语义：

- migration 37 新增播放源指纹、指纹版本、导入代际、单例活动状态和导入运行记录结构；
- 源文件检查器生成按音频/视频隔离的只读 staging manifest；
- dataset digest 不依赖文件名、文件顺序或重新分包，并按精确记录去重；
- ImportPlan 判定 `baseline_required`、`identical`、`snapshot_superset`、`delta_tail`、`reconciled_snapshot`、`truncated_or_regressive`、`different_account` 和 `ambiguous`；
- Settings 预检展示关系、预计策略、记录变化、日期范围和受影响周/年；
- Account Data 用户名只生成带命名空间的不可逆 SHA-256，不进入 API 或日志。

`POST /api/import/streaming` 仍使用原有文件门禁、快照、覆盖式导入和回滚路径。安全 noop、append-only、指纹基线填充和 ChangeSet 执行属于 Phase B 之后的工作。

### 真实数据库证据

先使用 SQLite Online Backup 创建真实库副本，在副本上应用 migration 37 并执行只读预检：

| 指标 | 结果 |
|------|------|
| 现有播放 | 92,908 |
| 输入记录 | 92,908 |
| 关系 | `baseline_required` |
| 基线状态 | `missing` |
| 预计策略 | `full` |
| 预计影响 | 218 个榜单周、5 个年度范围 |
| 预检耗时 | 1.757 秒 |
| 预检前后副本 SHA-256 | 完全一致 |
| `playback_import_runs` | 0 |

源码变更期间已有本地开发后端因 auto-reload 自动在正式本地库应用 migration 37。随后只读检查确认：92,908 条旧播放的 `source_fingerprint` 和 `import_generation_id` 均为空，活动状态没有 generation、fingerprint version 或 digest，运行记录为 0。即 schema 已升级，但旧事实未被反推、重写或导入。

运行中后端的 `GET /api/import/preflight` 返回同样的 `baseline_required/full` 结论，且 OpenAPI 快照与运行时接口逐字节一致。

### 自动化验证

- 后端 unit：1,121 passed；
- 后端 contract：358 passed；
- 前端 Vitest：73 个文件、550 项 passed；
- 前端生产构建：passed；
- 本次后端文件 Ruff：passed；
- 本次前端文件 ESLint：passed；
- OpenAPI 类型新鲜度：passed；
- 文档审计：54 个当前 Markdown，passed。

全量前端 `npm run lint` 仍被仓库既有、与本次修改无关的错误阻断；本次涉及的三个手写前端文件已单独通过 ESLint。首次完整 unit 回归还发现搜索 rebase 测试把最新 migration 版本硬编码为 36，本轮已更新为 37 并补充活动状态表断言，重跑后全绿。

### 未完成边界

- 还没有完整基线导入写入源记录指纹；
- 还没有 identical 的执行级 noop；
- 还没有 append-only 基础事实写入和活动代际原子发布；
- Billboard 周分区、搜索快照、年度缓存、元数据和封面仍未由 ChangeSet 定向维护；
- 尚未执行 Phase B 的增量—全量逐表等价性测试。

因此当前可以使用只读计划判断输入关系，但点击导入仍会执行现有完整导入。

## 增量导入 Phase B 交付报告

原记录：`2026-08-23-incremental-import-phase-b.md`。

> 验收日期：2026-08-23
>
> Phase B 功能状态：Pass
>
> 崩溃恢复与完整增量导入状态：Partial；派生 pending/active、后台任务代际隔离、ChangeSet 维护及历史修订仍待 Phase C–E

### 交付范围

本轮把 Phase A 的只读关系判定接入串流导入执行路径：

- `mode=auto|append|replace` 在真正写库前重新检查输入文件、账号证据和数据集关系；
- 旧库首次导入走完整替换并为每条播放写入版本化源指纹和导入代际；
- `identical` 在创建数据库快照和运行派生维护前结束为 noop；
- 已证明的 `snapshot_superset` 或同账号尾部 `delta_tail` 只插入新播放，复用既有事实和实体；
- append 不清空播放、聚合或曲目—专辑关系，同一事务内完成全部批次写入；
- 证据不足、不同账号、历史删除或修订不能用 append 绕过，风险 replace 必须明确确认；
- 已有播放但没有指纹基线时不会自动覆盖，必须确认输入包可作为完整历史；
- 警告与覆盖确认绑定具体输入和活动基线，文件或数据库变化会使旧确认失效；
- 自动尾部追加要求输入与活动集存在共同记录；零重合包不会借用可能过期的 Account Data 自动判为同账号，可由用户明确请求 fail-closed 尾部验证；
- append 在提交前核对旧基线 digest、实际输入 digest 和实际新增 identity digest，事实与活动状态同事务提交；
- 导入器异常会显式 rollback、关闭写连接，再进入 SQLite 快照恢复；
- 成功、noop 和等待确认写入紧凑运行记录，不保存原始播放 JSON、用户名或单条指纹明细；
- Settings 展示自动判定结果，并只在确需覆盖时提供明确替换确认。

Phase B 只增量化基础事实写入。append 成功后，元数据补齐、Album Project、Billboard、年度缓存和音乐查找仍调用现有完整维护入口，范围收缩属于 Phase C–D。

### 真实数据库副本证据

验证使用 SQLite Online Backup 创建的 `/tmp` 副本；没有对正式本地库执行 POST 导入，临时副本已删除。

| 场景 | 关系 / 策略 | 结果 | 基础写入耗时 |
|------|-------------|------|--------------|
| 首次建立基线 | `baseline_required` / full | 写入并激活 92,908 条 | 5.732 秒 |
| 相同输入 | `identical` / noop | 0 条写入，事实和维表不变 | 关系评估冷读 3.667 秒；终态记录 0.003 秒 |
| 完整快照增加 1 条尾部播放 | `snapshot_superset` / incremental | 新增 1，复用 92,908，活动集 92,909 | 3.529 秒 |
| 同一最终输入完整替换 | replace / full | 活动集 92,909 | 5.843 秒 |

对增量结果和完整替换结果比较 `plays`、`artists`、`albums`、`tracks`、`track_albums`、`track_artists` 的规范化语义哈希，六张表全部一致。append 事务回滚测试还将批次大小压到 1，并在第二批故意抛错；失败后活动事实、代际和导入状态均保持原值。

这些耗时只覆盖关系评估与基础事实写入，没有把 Phase C 尚未实现的完整派生维护计入，因此不能作为当前端到端导入时间承诺。当前最确定的端到端收益是 identical 输入不再创建快照、重写事实或重建派生数据。

### 正式本地库状态

开发后端 auto-reload 已在正式本地库应用 migration 37，但本轮没有替用户启动写入导入。只读检查时正式库仍有 92,908 条旧播放，指纹和导入代际为空；活动状态单例行存在但 generation、版本和 digest 为空，运行记录为 0。

因此下一次由用户在 Settings 触发的 `auto` 导入会要求确认完整替换，再建立一次基线；之后相同输入才能 noop，已证明的尾部新增才能 append。此次交付没有声称正式本地库已经建立基线。

### 自动化验证

- 后端 unit：1,147 passed；
- 后端 contract：366 passed；
- 前端 Vitest：73 个文件、557 项 passed；
- 前端生产构建：passed；
- 本次后端文件 Ruff：passed；
- 本次前端文件 ESLint：passed；
- OpenAPI 类型与运行时快照逐字节一致；
- 文档审计：56 个当前 Markdown，passed。

全量前端 lint 仍有仓库既有、与本轮修改无关的错误；本次涉及的手写前端文件单独通过 ESLint。

### 恢复与一致性边界

- append 的基础事实批次在一个 SQLite 事务内完成，计数或最终 digest 不一致会 fail closed；
- append 的实际输入、新增 identity、事实和活动代际在同一事务内核对并发布；可捕获异常先显式 rollback/close，再使用现有 SQLite 快照回滚；
- 活动事实发布后才运行完整派生维护；硬中止仍可能留下新事实与旧或半完成派生数据；
- 封面与搜索后台任务尚未绑定导入代际，维护后段失败与快照恢复之间仍存在后台副作用竞态；
- 完整 replace 仍沿用旧的分批提交路径。若进程被强制终止，恢复依赖导入前快照，不是跨进程原子切换；
- Phase B 没有新增独立 TEMP SQLite staging，延续现有批次 JSON reader；
- 历史删除、历史修订、时间倒退和不同账号不会自动 reconcile；
- Billboard 受影响周闭包、跨周连续播放边界、搜索快照 delta、年度缓存和封面任务去重仍待 Phase C–D。

### 下一步

Phase C 应从 append 产出的 ChangeSet 开始，只重算受影响实体、日期、年份与开放榜单周，并为每项派生数据建立独立 revision。验收重点是增量维护与完整重建等价，以及旧封闭榜单周不被重复扫描。

## 增量导入 Phase C 交付报告

原记录：`2026-08-23-incremental-import-phase-c.md`。

> 状态：Pass（ChangeSet、范围维护、年度缓存和封面恢复）；Billboard 周分区与搜索 snapshot delta 仍属于 Phase D
>
> 验证日期：2026-08-23；数据库证据来自 SQLite Online Backup 副本，不修改活动数据库

### 本阶段交付

- 从实际写入代际生成 `PlaybackChangeSet`，覆盖本地曲目/专辑/来源专辑/艺人、Spotify 曲目/专辑、日期、月份、年份、开放周和语义 revision；实际行数与计划不一致时拒绝发布。
- 事实、活动代际、年度分区和 `maintenance_pending` 运行记录同事务提交。维护成功后原记录提升为 `success`，进程中断不会丢失紧凑恢复依据。
- 增量元数据使用 generation play-time ID 与本地 canonical ID 的并集；专辑候选同时来自 generation play、曲目元数据和 album links。每次 scoped 刷新另带 200 条曲目/专辑/艺人和 100 条精确艺人封面的历史缺失扫尾。
- 封面以 provider URL 哈希判断缺失或过期。无来源证据的迁移前文件会重新校验下载；下载、临时写入、`fsync`、原子替换和数据库发布任一步失败都会留下可重试状态。后台队列启动时恢复 pending 和孤立 running；旧 URL 任务通过 CAS 拒绝覆盖新来源。
- 年度缓存使用逐年 direct/prefix digest，并摘要报告年前缀可达的艺人、Spotify 元数据、流派来源/覆盖、曲目组、Album Project membership 和可用年份。Migration 41 会清除不能安全升级的 V1 prefix 行，下一次导入完整回填。
- 播放事实提交后立即清理播放相关运行时缓存；聚合构建绑定开始代际并在原子发布时复核，防止旧事实计算被标记为新代际。无关的音乐档案、Podcast 等 cache namespace 不随播放导入清空。

### 自动化验证

- Unit：`1170 passed, 825 deselected`。
- Contract：`366 passed, 1629 deselected`。完整回归首次发现一个内部 helper 新参数未同步的测试调用，修正后再次执行全量门禁通过。
- 重点组合：ChangeSet、metadata、cover、JobQueue、Yearly Review 共 `54 passed`。
- Ruff 与 `git diff --check`：通过。

### 真实数据库副本

基线为 92,908 条播放，复制后增加 1 条尾部记录。副本先补齐版本化指纹和代际，仅用于测量 Phase C 的影响范围；测试后副本已移入废纸篓。

| 项目 | 结果 |
|------|------|
| ChangeSet 构建 | 0.0179 秒，3 个本地实体，影响年份仅 2026 |
| 年度分区发布 | 0.4460 秒 |
| 封面来源范围 | 全库 4,115 个；scoped 2 个 |
| 曲目/专辑 scoped selector | 各约 0.0001 秒 |
| 2025 年 scoped 年度依赖摘要 | 0.1271 秒 |
| 仍为全量的 Album Project | 2.3326 秒 |
| 仍为全量的 Billboard 聚合 | 3.1596 秒 |

当前真实库的 Spotify 曲目和专辑元数据已基本齐全，因此全量与 scoped 的请求数都为 0；全量艺人 selector 仍发现 26 个候选，单条尾部记录的 scoped 艺人候选为 0。这个结果证明范围收敛，不代表联网 provider 请求速度。

### 边界与下一步

- `billboard_scope_exact=false` 是有意的安全标记。当前维护仍全量重建 Billboard，不能用原始新增时间直接声称周贡献闭包。
- Album Project 暂时全量；真实副本耗时约 2.33 秒，低于 Billboard，但后续仍应通过成本门限决定定向或全量。
- 搜索候选与六套精确统计 snapshot 仍沿用现有重建/后台 warming。Phase D 需要实现受影响周替换、逻辑播放帧复用和 snapshot delta，并做增量—全量逐表等价性验收。
- Metadata backlog 当前由“仍然缺失”这一持久事实驱动并有界重试；尚未增加按错误类型的退避时间和尝试次数，这属于后续长期运行优化，不影响失败项被再次发现。

## 增量导入 Phase D1 交付报告

原记录：`2026-08-23-incremental-import-phase-d1.md`。

> 状态：Partial（Billboard 周聚合增量 Pass；搜索 shared-full 精确复用 Pass；snapshot delta 未完成）
>
> 验证日期：2026-08-23；真实数据库证据来自只读源的 SQLite Online Backup 临时副本，活动数据库未被写入

### 本阶段交付

- 尾部追加会从新增记录向前扩展完整的同曲、同来源连续播放链，分别构造旧、新局部逻辑帧，并把跨周收听时长切片纳入变化闭包；无法证明闭包、不是尾部追加或受影响完整周超过 25% 时安全回退全量。
- Billboard 从当前四张活动聚合复制到临时影子表，再对受影响周应用有符号贡献差值；单曲、专辑、来源和艺人四表通过唯一性、非负与代际依赖校验后在同一事务发布。
- 聚合有效性绑定 source dataset digest、事实代际、builder、播放策略、身份与署名 revision、曲目时长摘要和有效 canonical credit membership 摘要。Album Project membership 在四张基础周表之后读取，因此不错误地作为这四张表的复用门禁。
- 周榜、Power Score 与相关派生排序增加稳定 identity / 规范化文本裁决键；同播放次数、同收听时长的实体不再依赖数据库或 DataFrame 的偶然行顺序。
- 六套搜索精确上下文新增 `shared_full_snapshot_rebuild`：两个动态阈值作用域分别复用逻辑帧，L1/L2/L3 共用计算；primary 与 artist family 顺序处理并及时释放，且不再构建未消费的 lifetime 时长切片。
- 六个 context 全部计算、校验后才在一个 `BEGIN IMMEDIATE` 中激活；候选 generation、播放代际和语义依赖在构建前后均有稳定栅栏，失败不会留下部分 ready 集合。

### 等价性与自动化验证

- Billboard 覆盖动态/静态阈值、跨周时长、长连续链、已有歌曲新增署名、依赖变化回退、原子发布和稳定并列排序。局部路径与全量路径比较四张聚合表全部行，而不只比较 Top N。
- 搜索覆盖六个 `merge_level × dynamic_threshold` 变体、候选/语义代际栅栏、失败原子性、full fallback 和 shared/ordinary 上下文逐列等价。
- Unit：`1206 passed, 827 deselected`。
- Contract：`368 passed, 1665 deselected`。
- Ruff、格式检查、mypy 定向检查和 `git diff --check`：通过。

### 真实数据库副本

基线为 92,908 条播放、SQLite 文件 387,526,656 bytes；在临时副本加入 1 条精确尾部记录。源库以只读 URI 打开，所有合成指纹、migration 和构建只发生在 Online Backup 副本；默认自动删除工作目录。

| 项目 | 增量 / shared | 全量 / ordinary | 结果 |
|---|---:|---:|---|
| Billboard 四表 | 0.511 秒 | 3.258 秒 | 6.37×；双向 `EXCEPT=0` |
| Billboard 影响范围 | 1 个完整周 | 全部完整周 | 四表共 117,197 行完全一致 |
| 搜索六套 context | 24.935 秒 | 66.046 秒 | 单轮观察 2.649×；双向 `EXCEPT=0` |
| 搜索 payload/meta | 48,242 / 6 行 | 48,242 / 6 行 | 全列双向 `EXCEPT=0` |
| 搜索峰值 RSS | 1267.7 MiB | 约 1139.7 MiB | shared 低于 1280 MiB 门禁，但余量只有约 12.3 MiB |

这些性能数字来自单轮临时副本，不作为稳定基准结论；等价性结论来自逐表、逐列双向 `EXCEPT`。验收报告 SHA-256 为 `0639731a3f1fe16692bcc461df99d1009ec25d8ed18a9227fc4be17451b3ba31`，报告本身位于测试机临时目录，不含歌曲、艺人、文件路径或播放明细。

### 边界与下一步

- 搜索策略名称刻意使用 `shared_full_snapshot_rebuild`。它消除了六个变体各自重复扫描和重复构建，但仍从完整 lifetime 播放事实生成新的六套 snapshot；不能称为 snapshot delta。
- Phase D2 仍需复制兼容的上一 ready snapshot，只更新 ChangeSet 关联的歌曲、Album Project、有效署名艺人与受影响周排名实体；Power rank 需要从紧凑上下文全局重排，而不是重新加载完整播放历史。
- 当前 Billboard 影子发布虽然只重新计算受影响周，仍复制并重写四张活动聚合的全部约 11.7 万行。真实库已明显快于全量计算，但后续可在不破坏原子性的前提下评估更轻的发布方式。
- shared 搜索峰值 RSS 距 1280 MiB 既有冷建门禁较近。D2 除了降低 CPU，还必须给内存留下更稳定的余量；若旧 snapshot 或任何语义依赖不兼容，继续安全回退 shared-full。

## 增量导入 Phase D2 交付报告

原记录：`2026-08-23-incremental-import-phase-d2.md`。

> 状态：Pass（D2a snapshot lineage/周账本、D2b 同一开放周实体级 delta、D2c 跨周账本替换均已完成）
>
> 验证日期：2026-08-23；真实数据库证据来自只读源的 SQLite Online Backup 临时副本，活动数据库未被写入

### 本阶段交付

- migration 42 扩展搜索 snapshot meta，持久化稳定策略键、来源事实代际、来源数据集 digest、基础 snapshot、构建策略、依赖 digest 和 ChangeSet digest；旧 ready snapshot 可以继续读取，但没有完整 lineage 时不能作为 delta 基线。
- 新增按 `track:id`、L1 `album:id`、L2/L3 `album_project:id`、`artist:id` 归一化的周榜账本。shared-full 在整组六套上下文原子发布时同步写入账本和 lineage，作为后续增量引导基线。
- 对“精确尾部追加完全落在同一个当前开放榜单周，并且没有影响任何已发布完整周”的保守范围，复制兼容的六套基础上下文和周账本，只从尾部闭包生成有符号逻辑播放差值，更新歌曲、L1 专辑、L2/L3 Album Project 和有效署名艺人的 lifetime 指标。
- delta 构建不调用 lifetime 播放加载器；执行前后复核活动事实、基础 snapshot payload、候选内容、播放规则、聚合语义、身份、署名、曲目组与 Album Project 依赖。六套结果和 lineage 在一个 `BEGIN IMMEDIATE` 中激活，失败或不兼容自动回退 D1 `shared_full_snapshot_rebuild`。
- 固定阈值与动态阈值证明的 Billboard 影响周改为取并集，避免固定阈值完整周已经变化、搜索却误判可以直接复制旧周榜。
- 自动推断 Album Project 按 `(canonical_name, artist_id, scope)` 复用稳定 ID，精确替换 membership 并清理过期推断项目；人工项目保持不变。相同输入重建不再使 L2/L3 搜索实体键漂移。
- 对恰好跨越一个开放周的精确尾部追加，只读取新完成周及其前后连续播放链闭包，重建 fixed/dynamic、L1/L2/L3 的歌曲、专辑和艺人 Top-N 周账本；旧历史周直接复用，新的开放周仍不发布。
- 合并完整周账本后，按稳定实体 ID 全局重算 peak、在榜周数和 Power score/rank。shared-full 同步使用相同的账本重算语义，同名但不同 ID 的专辑或艺人不再因显示名称相同而合并。

### 实施中发现并修复的问题

- L1 专辑元数据旧路径仅按规范化专辑名关联 Spotify 元数据，同名但不同 Spotify 专辑可能扇出并污染播放/周榜统计。现在按 `album_spotify_links` 的播放、曲目和置信度证据为每个本地专辑稳定选择一条 Spotify metadata；旧库缺少链接时只允许本地标题与 Spotify 标题都唯一的名称兜底，歧义标题不猜测。
- L2/L3 增量帧可能不带 `artist_name`，与 Album Project membership 合并后列名不会带预期后缀。归一化逻辑现在同时支持带后缀和无后缀的稀疏帧，避免尾部 delta 误报缺列。
- 周账本引导会折叠字节完全相同的重复事实；同一身份若存在冲突事实，则保留确定性行但将基线标为不可复用，避免有歧义的 lineage 进入 delta。
- 第一版跨周 helper 使用了不存在的 pandas `Timestamp.add()`，且 artist fan-out 与已规范化帧的 `raw_artist_id` 列发生碰撞；两项均由真实跨周验收暴露并修复，补充了周边界单测。
- 初次对账中六套周账本已完全一致，但约 1,300 个实体的榜单摘要不同。根因是旧 shared-full 按显示名称归组专辑/艺人，delta 按稳定 ID 归组；统一为稳定 ID 后六套上下文全列一致。

### 自动化与等价性验证

- D2c 定向回归覆盖增量计划门禁、跨周发布、账本严格校验、同名实体 ID 隔离、Power 全局传导、受影响周闭包、开放周排除和验收报告隐私：`72 passed, 1 warning`。
- 真实数据库副本的同周与跨周场景均通过六套上下文和六套周账本逐列双向 `EXCEPT=0`；跨周额外证明旧历史周不变、新完成周已发布、当前开放周仍排除。
- 完整 Unit：`1252 passed, 851 deselected`；完整 Contract：`368 passed, 1735 deselected`。
- 文档审计、Ruff、格式、mypy、Detect secrets、`git diff --check`：通过；`AGENTS.md` 与 `CLAUDE.md` 保持一致。

### 真实数据库副本

基线为 92,908 条播放、SQLite 文件 387,526,656 bytes；分别在临时副本加入 1 条同开放周尾部记录，或加入 1 条完整落在下一开放周的记录。源库以只读 URI 打开，migration、合成指纹、基线引导、delta 和 shared-full 参照构建只发生在 Online Backup 副本；默认自动删除工作目录。

| 场景 | delta | shared-full 参照 | 结果 |
|---|---:|---:|---|
| 同一开放周 | 1.093 秒 | 26.416 秒 | 单轮观察约 24.2×；复制周账本 |
| 恰好跨一个开放周 | 6.500 秒 | 26.339 秒 | 单轮观察约 4.1×；替换 1 个新完成周 |
| 六套实体上下文 | 49,892 行基线 | 49,892 行基线 | 两场景全列双向 `EXCEPT=0` |
| 六套周榜账本 | 90,448 行基线 | 90,448 行基线 | 两场景全列双向 `EXCEPT=0` |
| ready lineage | 6 套 | 6 套 | 来源代际、数据集、策略与依赖门禁通过 |
| lifetime 播放扫描 | 否 | 是 | delta 报告 `lifetime_scan=false` |

性能数字来自单轮临时副本，不作为稳定基准结论；等价性来自实体上下文和周账本逐列双向 `EXCEPT`。同周、跨周验收报告 SHA-256 分别为 `24a31c196d5476b0c47e404d85e2bd9db37a7f31b35fcc7eab3f8bd6b95029b0`、`9b81a7d7b9e885ab9d164b498a806ec2a7247e00607833ae85dfa982eb2e400c`，报告位于测试机临时目录，不包含数据库路径、周边界值、歌曲/艺人内容或播放明细。

### 当前边界与下一步

- D2 delta 只接受同周或恰好跨一个开放周的精确尾部 append，并要求 fixed/dynamic 两套阈值的影响范围都被 ChangeSet 覆盖。多周跳跃、历史增删、关闭连续播放合并、超过 10,000 条新增、基础 snapshot/账本缺失、依赖变化、闭包超过 100,000 行或并发代际漂移都会回退 shared-full。
- `lifetime_scan=false` 表示 delta 不加载或扫描完整播放历史来重建 lifetime DataFrame；跨周路径仍会读取新完成周和必要的前后连续播放链，并读取、摘要曲目组与 Album Project 等较小依赖表。基础 snapshot 并发栅栏目前核对 snapshot 标识、激活时间和实体/账本行数，后续可再加入持久化 payload digest 或单调发布 revision。
- Album Project 仍执行完整 rebuild；本阶段只稳定了推断项目身份，没有实现 ChangeSet 定向项目重建。启动恢复、完整替换的硬中止恢复和历史修正继续留在后续阶段。

## 增量串流导入 Phase E 交付与验收

原记录：`2026-08-23-incremental-import-phase-e.md`。

> 状态：Pass
>
> 验证日期：2026-08-23
>
> 范围：历史完整快照对账、连续播放链局部闭包、定向 Album Project、硬中止与启动恢复

### 结论

Phase E 已完成。对于同账号、同时存在新增和移除、且输入时间包络覆盖现有完整范围的未知来源包，系统只会提出需要确认的 `reconciled_snapshot`；确认标识仍绑定输入和当前基线。确认后，旧身份精确删除、新身份插入、最终 count/digest 对账、活动代际、年度分区和 ChangeSet 在同一个 `BEGIN IMMEDIATE` 事务中发布。

历史修正会分别重建旧、新有序事实视图，从 added/removed 位置向前后闭合相同 track/source 的完整连续链，并比较 fixed/dynamic 两套逻辑贡献。只有 timestamp、维度、全局顺序、邻接、完整周、语义依赖、活动代际与 100,000 行成本门禁全部成立时，才从当前事实有界重算受影响完整周并原子替换四张 Billboard 聚合；否则自动全量重建。历史 reconcile 的六套搜索统计继续走 D1 shared-full，不使用未经证明的 snapshot delta。

Spotify 元数据刷新会返回实际更新的 Spotify 曲目/专辑和本地专辑重链范围。无删除且影响闭包精确时，Album Project 只重建相关 release group、standalone 和 compilation closure；manual 与未受影响项目保持不变。存在删除、证据不精确、闭包过大或无法证明时明确全量回退。Spotify 同曲分组也只扫描本次变化或实际刷新到的 Spotify 身份。

最终独立审计继续补齐了活动 `track_albums` 闭包、Track Group 自动身份和 staging 崩溃孤儿清理：reconcile 在事实事务内精确重算受影响曲目的活动专辑关系，播放仓库按逐条播放的 `source_album_id` 归属；自动项目与搜索只消费活动事实可达实体；自动 Track Group 使用 Spotify recording ID + artist ID，不再因同名不同艺人触发生产唯一约束。真实原始指纹 baseline 与完整派生冷构建、identical、两类 append、专辑历史纠正 reconcile 和空库 replace 的 14 项语义投影终验见 [`2026-08-23-incremental-import-final-acceptance.md`](#串流数据增量导入最终闭环验收)。

### 真实数据库副本验收

验收脚本：`scripts/phase_e_real_db_acceptance.py`。源库始终只读，所有迁移、合成修正、硬中止和恢复探针都在 `/tmp` Online Backup 副本完成；报告不输出数据库路径、实体内容、指纹或播放记录行。

| 项目 | 结果 |
| --- | --- |
| 源播放规模 | 92,908 条 |
| 历史修正影响范围 | 1 个完整榜单周 |
| Billboard 历史周局部替换 | 0.579 秒 |
| 同事实全量重建 | 3.540 秒 |
| 四张聚合双向差异 | 全部 0 |
| 未受影响历史周 | 四表摘要全部不变 |
| replace 在事实发布前 SIGKILL | 退出码 -9；旧事实、聚合、活动状态和关系保持不变；`quick_check=ok` |
| 合法 pending 启动恢复 | 幂等排队 1 个任务 |
| 活动 digest 漂移 | `recovery_blocked / recovery_active_digest_drift` |

机器可读报告位于一次性临时路径 `/tmp/spotifystats-phase-e-real.json`，SHA-256 为 `b19582fe2fcbea692003df85e48829a7a34fcf9354df672ea6f119143823331b`。

当前真实库仍早于 Phase B 指纹基线，因此验收副本使用 `play_id` 生成确定性测试指纹，并明确标记 `validates_source_fingerprints=false`。这可以验证 Phase E 的代际绑定、历史周等价、事务和恢复边界，但不冒充 Spotify 原始记录指纹验收；原始指纹关系仍由 Phase A/B 的真实导入证据负责。

### 故障与压力覆盖

- 全量后端门禁：Unit `1302 passed, 852 deselected`；Contract `369 passed, 1785 deselected`。仅有既存 urllib3/LibreSSL 与 AnyIO HTTP 422 弃用提醒。
- replace 批次中途失败和 finalizer 失败均验证旧事实、聚合、`track_albums` 与活动状态回滚。
- reconcile 验证 stale baseline、精确删除/新增、finalizer 异常回滚，以及与 clean replace 的活动事实等价。
- 20 轮 A/B 历史快照交替 reconcile 后，活动事实始终为 2 条、身份无重复、每轮只新增 1 条并移除 1 条。
- `maintenance_pending` 启动扫描严格反序列化 ChangeSet，并在维护前后核对 generation、fingerprint version、count 和 digest；瞬时维护错误保持 pending，证据漂移才进入 `recovery_blocked`。
- 定向 Album Project 测试覆盖 release-group 跨成员、compilation 传导、manual/未受影响三表整行不变、空影响 no-op、targeted/full 三表一致和四类 full fallback。

### 保留边界

- 删除场景的 Album Project 当前保守全量重建，因为删除后的旧反向链接不足以独立证明项目闭包。
- 历史 reconcile 的搜索快照仍使用 shared-full；D2 snapshot delta 只接受已证明的同周或恰跨一个开放周尾部追加。
- Online Backup 仍是维护阶段失败和跨事务外层事故的恢复边界；SQLite 原子事务负责事实发布前的进程崩溃回滚，启动 recovery 负责事实已发布但派生维护尚未完成的场景。

## 串流数据增量导入最终闭环验收

原记录：`2026-08-23-incremental-import-final-acceptance.md`。

> 日期：2026-08-23
> 结论：**Pass**
> 验收脚本：`scripts/incremental_import_end_to_end_acceptance.py`
> 结构化结果：`/tmp/spotifystats-import-e2e-final.json`
> SHA-256：`6350979f4095ed088f15d40f2e1de3bc554a7bc841fd71f8222b640a394f18de`

### 1. 验收边界

本轮补齐从原始 Spotify JSON 到生产 `import_data` 的闭环证据。终验脚本内的所有数据库写入、迁移、派生维护和对照计算都发生在 `/tmp` 新建的隔离目录；当前真实数据库在终验运行中只以 SQLite `mode=ro` 打开，原始导出文件只读。开发后端热重载触发的本地迁移单独记录在第 7 节。

临时 staging 使用分块 JSON array decoder 和每 1,000 条一次的 SQLite 批量写入，不读取或保留完整源文件；专项测试以 2,505 条单文件并禁止 `Path.read_bytes()` 验证真实流式路径。首次 staging 还会保守清理超过 24 小时、受控前缀、当前用户且保持 `0700` 的崩溃孤儿目录，任何边界不明确项都不会删除。

脚本包含两层验收：

1. 真实 13 个导出文件、92,908 条记录导入 `/tmp` 空库，建立真实源指纹基线，完整构建 Album Project、Billboard、六套搜索和首页，再执行 identical 计划；
2. 受控合成包执行 baseline → identical → 跨周 append → 同周 append → 历史 reconcile，并与“最终输入从空库完整重建”的 replace 比较全部要求的语义投影。

### 2. 真实源基线结果

- 真实库：92,908 条播放，migration 45，`PRAGMA quick_check=ok`；验收前后文件大小、mtime 和 inode 不变。
- 原始导出：13 个文件；验收前后 size/mtime manifest 不变。
- 空库 baseline：活动记录 92,908，输入 digest 与活动数据集 digest 相同。
- baseline staging + 计划：5,514.742 ms。
- 事实写入与活动状态发布：7,503.206 ms，其中事务内 finalizer 2,074.458 ms。
- Track Group full：3.166 ms；Album Project full：118.378 ms；Billboard 四表 full：3,869.784 ms；Billboard 消费 payload：5,533.333 ms。
- 六套搜索 full：73,947.015 ms，6 个 variant 全部 ready；首页服务层首响：7,050.656 ms。
- 第二次 identical staging + 计划：6,903.600 ms；关系为 `identical`，数据库无写入。
- 真实全链总时间：110,457.056 ms；消费侧共发布 216 个完整 Billboard 周。
- `validates_source_fingerprints=true`。这项证据不再依赖对旧库 play_id 生成的合成指纹。

### 3. 增量策略与时间

合成矩阵使用 12 个历史榜单周、4 首曲目、1 个跨周追加和 1 个同开放周追加，再把一首曲目的旧专辑关系纠正为新专辑。

| 阶段 | staging + 计划 | 事实发布 | Billboard | 搜索 | 端到端 | 实际策略 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 跨周 append | 4.761 ms | 33.519 ms | 28.386 ms | 894.204 ms | 967.670 ms | Billboard `partition`；首次建立 `shared_full_snapshot_rebuild` 基线 |
| 同周 append | 6.860 ms | 33.440 ms | 26.253 ms | 136.204 ms | 208.842 ms | Billboard `partition`；六套 `incremental_snapshot_delta` |
| 历史 reconcile | 8.269 ms | 74.665 ms | 33.098 ms | 1,728.930 ms | 1,852.023 ms | Billboard `historical_partition`；Album Project 因删除语义安全回退 full；搜索 full |
| 空库完整 replace 对照 | 3.494 ms | 38.459 ms | 28.954 ms | 2,170.555 ms | 2,243.170 ms | Billboard full；搜索 full |

跨周 append 后，消费者可见榜单包含刚刚结束的 `previous_open_week`，不包含新的 `current_open_week`；`complete_week_gate=true`。这里验收的是实际 Billboard 消费 payload，而不是内部聚合暂存行。

### 4. reconcile 与 replace 等价性

以下投影逐行比较全部通过：

- 活动播放事实闭包：41 行；
- 有效 credits：5 行，包含 primary 与 featured；
- 活动 `track_albums` 闭包：4 行；旧专辑关系不进入活动消费者；
- 自动 Track Group：1 个组、2 个成员；增量路径与空库完整重建的稳定身份、主曲、艺人和成员完全一致；
- Album Project identity、album membership、track membership；
- 四张 Billboard 聚合表；
- Billboard 完整 payload、Power、records；
- Year-End 输入与 payload；
- 音乐查找候选文档；
- L1/L2/L3 × dynamic on/off 六套精确 snapshot；
- 年度 partition 的 factual direct digest、记录数与覆盖范围；
- 首页 archive 事实。

搜索最终为 6 个 ready variant、44 条 entity context；候选索引为 17 条文档。增量 reconcile 与空库完整 replace 的候选和六套精确快照 digest 完全一致。共 14 项语义投影全部通过。

### 5. 年度与首页

- 年度 partition factual digest 在增量与 replace 间一致。
- `yearly_artifact_contract` 已成为终验硬门禁：跨周 append、同周 append 与历史 reconcile 均须提升受影响年份的 `impact_revision` 并更换 artifact key；identical 必须保持事实 partition、revision 与 key 不变。
- 年度 artifact key 不要求跨执行历史相同：`impact_revision` 会记录被接受的变更次数，因此同一最终事实经过不同导入路径时 prefix revision 与 cache key 可以不同；这属于预期失效语义，不是事实差异。正式决策见 [`../designs/2026-08-23-yearly-artifact-key-invalidation-contract.md`](../archive/06-productization-closeout/2026-08-23-yearly-artifact-key-invalidation-contract.md)。
- 在隔离小库上，确定性首页 builder 首次响应为 171.067 ms；这是服务层首响，不是浏览器/HTTP/生产网络时延。
- 同一隔离库的 Billboard 完整 payload 为 653.901 ms，Year-End payload 为 212.060 ms。

### 6. 未扩大结论

- 真实 92,908 条数据已验证原始源解析、真实指纹 baseline、事务事实发布、Album Project、Billboard、六套搜索、首页首响和 identical no-op；历史 reconcile 与空库 replace 的逐项等价矩阵使用受控合成原始 JSON，真实副本上的增量和硬中断恢复仍由 Phase D/E 的独立报告覆盖。
- 本报告不代表生产部署、浏览器视觉验收或外部 Spotify 元数据网络成功。
- `/tmp` JSON 是本次可复核结果；默认脚本结束会清理所有隔离数据库，不保留私人播放明细。

### 7. 开发库迁移说明

开发后端以 `uvicorn --reload` 运行，migration 43 文件保存后触发了自动重启，因此真实本地库在本轮开发过程中实际完成了 Track Group identity 迁移。过渡 schema 先后由 migration 44、45 修复；两次均先在 SQLite Online Backup 副本预演。最终真实库为 migration 45，`track_groups` 24 行、`track_group_members` 48 行，迁移前后数量不变；Track Group 外键检查为空，`PRAGMA integrity_check=ok`。这属于本地开发库迁移，不代表远程生产发布。

### 8. 提交前门禁

- 后端 Unit：1,337 passed；Contract：369 passed。
- 前端：73 个测试文件、557 项测试通过；生产构建通过，仅有既存的大 chunk 提示。
- 全仓 pre-commit：Ruff、Ruff format、mypy、Detect secrets 全部通过。
- `scripts/docs_audit.py` 与 `git diff --check` 通过。
