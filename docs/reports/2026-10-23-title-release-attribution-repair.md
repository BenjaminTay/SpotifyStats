# Title 发行日期与歌曲归属修复：隔离验收

事项：`SS-2026-10-23-001`。最后核验：2026-10-23。

状态：**FIXED / LOCAL APPLIED / VERIFIED，本地应用及验收完成，生产未发布**。在 `codex/title-attribution-repair-20261023` 完成通用实现、隔离验收及用户确认后的本地正式应用；未提交、推送或部署生产。原始记录、项目成员、7015条歌曲归属和UI保持。原发行周期功能 `SS-2026-10-21-006` 的已发布结项不重新打开；本项属于独立治理缺口修复。

以下“真实副本结果”和“原后续计划”记录前一轮隔离检查点；最新正式应用结果见文末，Title不再处于本地暂缓状态。

## 根因与事实边界

Title 项目 41547 的旧日期为 `2025-03-28 / NULL`，与 28 首周年版相同；旧日期回退按曲目数择来源，可重现错误锚点。缺少当初写入审计，不能把某次历史调用描述为已查明。

《I’ll Be Home》现有稳定 owner 为 4447，已同时属于 Title 与 A Very Trainor Christmas（41603）的项目成员。L3 v2 将两者均视为原生专辑候选，再按项目日期排序；Title 改为 2015 年就会击败 2020 年 Christmas。成员 `standard` 和没有 Live/Remix 后缀都不能证明歌曲属于原版曲目。因此是旧来源数据与规则信息不足共同造成，并非界面问题。

现有 Christmas 归属是自动结果。继续保留它是用户明确的治理约束，应记录独立人工决定，不能声称由年代或播放多数自然证明。不同 Spotify ID/ISRC 不足以拆分作品 owner，本轮不拆分。

新取五份完整 Spotify 目录：11 首原版、15 首 Deluxe、18 首 Expanded、28 首周年版、18 首 Christmas。已有四份缓存的目录和原始日期均与当前来源一致。11/15 首不含该曲；Expanded 第 18 首为现有 owner 对应 ID，周年版第 20 首为另一个 ID。Sony 的 19 首实体特版与 18 首数字版不能混同。

证据入口：

- [Sony 原版及 Deluxe 公告](https://www.sonymusic.co.jp/artist/meghantrainor/info/449705)：区分 11/15 首原版目录。
- [Sony 西班牙特别版公告](https://www.sonymusic.es/lanzamientos/meghan-trainor-publica-el-20-de-noviembre-la-edicion-especial-de-su-exitoso-album-tittle/)与[日本 EU 特版目录](https://www.sonymusic.co.jp/artist/meghantrainor/discography/buy/00DE-14675)：19 首实体版分别有 2015-11-20 / 2015-11-24 的地区日期。
- [Qobuz 11 首原版目录](https://www.qobuz.com/us-en/album/title-meghan-trainor/0886444905183)：原版目录日期 2015-01-09，为本轮副本项目原始日提案依据；不声称所有地区、所有版别同时发行。
- [Spotify 18 首 Expanded](https://open.spotify.com/album/7m2Gzfu5nMgHTiMbNDwPr7)：原始平台日期仍为 2015-01-09，不能独自证明附加曲目首次收录日。

因此副本可以登记“附加收录”，但 `included_on` 保持 NULL，18 首版具体收录日仍待独立证据。网络首次 TLS EOF 经既有 7897 代理重试成功，未改持久网络配置。

## 通用实现

1. 日期用途分离。项目原始发行日与具体版本发行日分别读取、登记和审核。版本日期不改项目原始日，原版日期也不覆盖明确版本请求；版本证据可绑定非主成员。原有同年粗日期补精度的冲突拒绝保留，跨年纠正走独立事务。
2. 日期回退使用明确来源与已审核日期。曲目数排序仍可用于旧元数据选择，但不再用于发行日；多来源矛盾时拒绝推定。日期读取合同升为 `release_date_evidence_v4_release_scopes`，使发行周期及相关统计/年度准备依赖识别语义变化，防止沿用旧版日期缓存。独立日期覆盖只作用于有效读取，不重写 Spotify 声明。
3. schema95 增加逐曲版别收录事实及审核事件。记录 original / bonus / reissue、可为空的确切收录日、日期用途、地区、媒介和来源。既有项目成员行不改写。新事实采用 `album_track_release_evidence_v1`，没有新事实的历史候选保持 v2 合同，不触发全库重分配。
4. L3 只用经审核且仍匹配目录、艺人、owner 和成员的逐曲证据细化候选。附加曲目不继承项目更早日期；同级候选在来源或日期不可比时进入冲突。有效人工决定可保留既有目标，但不能掩盖已失效证据。原版收录事实不把合辑、重录、Live 或单曲升级为原生专辑。
5. 显式纠正事务同时核验旧项目、完整目录、来源占用、项目成员、规划输入及现有发布摘要；保存来源、跨年项目日、人工归属保留与审核证据。任何未批准目标/原生项目变化、范围外规划变化或基线漂移均回滚。来源不得从其他项目抢占；既有冲突人工决定不得覆盖。
6. 只发布闭合歌曲范围，不调用会发布全库规划的旧覆盖 POST。保留范围外既有事实，核验完整前后规划后推进必要依赖及发布摘要，审计记录真实已发布内容。重复请求幂等，不重复升 revision。

入口为 `scripts/correct_project_release.py`，默认 prepare 会 Online Backup 到临时库并实际预演事务。apply 只接受明确隔离副本，拒绝配置正式库及其同 inode / 符号链接别名；调用方显式事务，失败完整回滚。CLI 不提供本轮正式应用通道，不新增 UI 或网络写入口。

## 真实副本结果

副本 `output/title-attribution-repair-20261023/baseline.db` 与 `candidate.db` 来自本地 Online Backup。只在 candidate 中迁移、登记和应用以下提案：

| 对象 | 原值 | 副本结果 |
| --- | --- | --- |
| Title 项目日 | 2025-03-28 / NULL | 2015-01-09 / day，项目原始日提案 |
| Title 主来源 | 无明确绑定 | 18 首 Expanded，7m2Gzfu5nMgHTiMbNDwPr7 |
| Title 中歌曲收录事实 | 无逐曲证据 | bonus；included_on=NULL |
| I’ll Be Home 目标 | 41603，automatic | 41603，manual，保留理由入审计 |
| 独立 Positions 既有发布 | 41567 | 41567；未带入规划中的 44793 |

本次闭合范围 6 个歌曲键；7009 个范围外发布行除共享依赖水位外逐字段一致。全部 7015 个目标/原生项目、代表曲目、艺人及归属种类均保持。146 张未涉及修改的表（包括原始记录、成员、Spotify 元数据/目录/owner/署名/日期证据）按既有有序行摘要合同一致。

单列允许变化为迁移记录、新证据/审计、Title 单一项目日期及来源绑定、一个归属保留决定、范围内决策解释与必要派生 revision；不是放开原始字段。分析/治理来源水位由既有触发器推进。

L2 / L3 各核对 3097 个 release 项目的真实发行锚点，仅 Title 变化；之前可解析的 2590 / 2588 项保持，含 TTPD / Showgirl。Title 两层都使用明确来源及 2015-01-09。唯一 owner 与原始事实完全相同，因此日期纠正没有造成 L3 重复记账或全局播放/时长的归属变化。L3 发布依赖 ready，外键异常 0，重复 apply 返回 idempotent=true。

正式本地仍为 schema94，没有新增证据表；Title / Christmas 项目、成员、来源绑定、覆盖和全部已发布归属与基线相同。生产没有应用、迁移或部署操作。未重启当前 8000 / 4173 应用，前端源码、构建和表格显示均无本轮改动。

## 验证与范围

- 受影响六个测试模块：160 passed，保留一条既有 LibreSSL 环境警告。覆盖原生/附加收录、未知日期、不可比地区、来源漂移、手动归属、拒绝抢占、原子回滚、幂等、范围外漂移隔离及历史重建合同。
- 文档审计与 `git diff --check` 通过。本轮文件 Ruff 检查通过；新增三个业务/工具文件的定向 mypy 通过。现有两播放模块 16 条 pandas 等类型错误，与 `git show HEAD` 提取的基线错误逐项相同；不是项目全量类型检查通过。
- 真实副本验收、解析器批量读取与正式库只读保护证明分别保存。不将解析器检查描述成新版本正式 HTTP、浏览器或生产验收。
- 初期工具/夹具失败和首次保护比对失败日志保留：补齐夹具 schema、恢复 CLI ContextVar，以及将触发器派生来源水位纳入允许变化；未降低原始/成员/owner 保护。静态 Online Backup 读取使用 immutable，运行中正式库仍按只读 WAL 读取。

证据目录：`output/title-attribution-repair-20261023/`。关键材料：`live-editions.json`、`real-preview.json`、`real-applied.json`、`real-repeated.json`、`real-acceptance.json`、`final-targeted-tests.log`、`typecheck-comparison.json`。历史只读诊断保留于 `output/title-attribution-diagnosis-20261023/`。

## 原后续计划与结束边界（本地部分已按下节执行）

程序修复和隔离数据验收完成。正式 Title 仍暂缓，其他 28 项独立审核不因本修复自动通过。后续正式应用须使用正式环境自身 fresh Online Backup 重生成提案，确认原始项目日期的统计口径、主来源及“保留 Christmas 归属”的显式决定；18 首版未知收录日可继续保留 NULL。

批准应用后再执行受控迁移/数据纠正及下游精确快照维护，完成受影响 HTTP / 原六指标页面验收；提交、推送、部署与生产自身应用按相应明确指令执行。本轮仅证明 L3 与发行锚点正确，不把 `requires_downstream_refresh=true` 的副本称为全站快照 ready。

当前共享目录另有发布材料清理任务的未提交修改；本轮不纳入、不回退它们。自身修改未提交，未建立新的工作树。源码分支保留为本地待整合，证据及隔离库不入 Git。


## 用户确认后的本地正式应用与收口

最后核验：2026-10-23。用户明确确认已验收方案，并授权本地正式库应用、相关快照维护、接口和原界面验收；没有要求提交、推送或生产部署。

从当时正式库 fresh Online Backup 重新核对 Title 全项目行、完整目录、来源艺人和来源 guard，与已验收提案一致。新副本完成 schema95、18首主来源绑定、Title `2025-03-28/NULL → 2015-01-09/day`、bonus收录事实与独立人工归属保留，并记录完整确认原文。重复应用幂等，没有第二次修改。具体版别首次收录日仍为NULL，没有改写Spotify声明或用实体19首版日期补数字18首版。

切换前停止已验证身份的日常8000/4173服务，全158表及schema源围栏与fresh基线一致。七库 quick_check 通过，旧七库原inode与首页缓存保留联合恢复点，再切换受验副本。114项保护检查通过；96881条原始播放、原始歌曲/署名、项目成员、Spotify owner/元数据/目录及既有日期证据保持，7015条目标/原生项目归属不变，7009个范围外发布行只推进已证明适用的共享依赖水位。《I’ll Be Home》仍归41603，Positions仍归41567。

相关快照维护与正式路径重绑定均完成：

- 搜索四个L2/L3、动态阈值组合精确统计 ready，并通过严格复用验证；只在明确隔离副本重建，没有用搜索GET冷建。
- Billboard八配置、96项发布；四套详情投影及manifest验证；默认四套和含精选四套个人排名发布通过。
- 默认统计/记录、社区、音乐档案、治理和艺人排名准备/验证通过；正式路径2022–2026年度与首页快照完成，缓存读取验证通过。
- 日期依赖合同v4已参与新准备，L3发布依赖ready；外键异常0。没有重建项目成员或采纳无关的全库归属规划漂移。

隔离与正式本地各42项实际HTTP矩阵通过，覆盖八配置的选择器、Title/Christmas/TTPD/Showgirl发行周期、个人统计/排名、榜单对决、重排及歌曲详情。两边各32次比较、192项六指标从计次/排名基础独立对账通过。TTPD、Showgirl和Christmas的日期/来源/六指标均与应用前相同。Title改正发行锚点后会影响其历史榜单资格，因此选择器排序可发生变化；实际对象集合在八配置中保持，不把排序改变误判为成员改变。

正式歌曲详情返回 `album_attribution.album_project_id=41603`。具体展示版仍可能是Title（display_album_id=59）；统计归属与具体发行版展示原本就是独立字段，没有改歌曲owner或封面规则。

真实浏览器完成1280×900桌面和390×844手机验收，操作选择TTPD、Showgirl、Title及Christmas。发行周期仍是首发排名、最高排名、发行周播放、艺人影响力、大盘影响力、半数播放距六行；没有“发行日期”行或内部状态文案。原两专辑表格 outerHTML 在应用前后完全一致；前端源码输入和全部成品文件字节保持，无本轮重新构建。四对象默认页面Title发行周为0、半数播放距567周，Christmas为0/263；缺少历史榜单和基线的指标继续显示“—”。手机页面整体横向溢出0，表格仍沿用原局部横向滚动布局，没有借验收调整UI。浏览器控制台0错误/0警告，验收session已关闭。

当前前端构建标记此前就与14个输入的mtime/大小不一致，含本轮无关的RankTrend文件变化；没有伪造build manifest或触发常规启动器重新构建。为明确复用原成品，本地使用受成品字节校验的 `output/title-attribution-repair-20261023/local-apply/run_local.py` 监督进程启动后端和Vite preview。现监督PID89337、后端89338、前端89339；8000/4173正常运行。该操作脚本与此目录是当前运行消费者，不得按旧临时材料删除；后续统一提交/启动收尾时再处置。

启动后仅新增一条 `startup_cache_warmup` / minimal任务且已done，既有任务行完全保持。最初运行态保护检查因这条新任务失败，随后单列精确任务类型、payload、终态及既有任务保留条件完成运行态证明，未放开用户/Spotify/成员/归属保护。验收脚本首次对选择器顺序、详情URL和Playwright代码形态的错误假设已纠正；原失败日志保留，不作为产品故障或掩盖为首轮全通过。

本轮业务源码与上一轮已通过的160项定向回归版本逐文件一致，复用该代码证据，没有重复全量测试。文档审计和差异检查通过。所有本地新证据位于 `output/title-attribution-repair-20261023/local-apply/`：`user-confirmation.json`、`installation-proof.json`、`preparation-receipts.json`、`formal-api.json`、`formal-six-metrics.json`、`formal-protection-runtime.json`、`original-pair-dom-proof.json`及`acceptance-summary.json`；截图位于 `output/playwright/title-local-20261023/`。

联合恢复点为同目录 `local-activation/old/`（旧七库原inode）和 `old-home-overview/`；`journal.json`保存移动/新进程状态，失败候选留存目录为`failed-new/`。不覆盖旧恢复材料；回滚时停止已核验的新监督进程、整体恢复旧七库及首页后再启动旧版本，不能只回滚主库或对运行中的WAL文件直接覆盖。

本地应用和本轮验收已收口，正式数据的Title暂缓解除；18首版具体收录日未知保持独立事实边界。剩余其他来源、粗日期和身份项目继续独立治理，没有本轮自动批准。当前未提交、推送或部署生产；本地分支READY待后续明确提交/交付安排，共享目录其他清理任务修改保持，不纳入本轮。
