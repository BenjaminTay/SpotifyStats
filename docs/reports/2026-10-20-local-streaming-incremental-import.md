# 2026-10-20 本地串流增量导入

> 本文按阶段保留失败、临时处置与后续补修；早期“待核”“未提交”是当时状态。最终实现、暂缓范围及本地Git提交状态见[提交收口](#本地git提交收口)。

> 以下首次导入经过保留当时的失败与临时处置；用户随后授权继续修复，代码及复验见末尾“后续根因修复”。

## 范围与恢复点

仅更新本机数据及必要导入修复；基线 `f9526aff`，未提交、推送或部署。输入为用户下载的 `Spotify Extended Streaming History` 中14个串流JSON；无新账号导出，保留 `data/account`。

导入前对主库与六个侧库执行 SQLite Online Backup，保留控制目录和旧原始文件，恢复点为忽略目录 `data/import_backups/local-import-20261020T142420/`。应用另建自身导入快照。事实及不可变来源发布后切换 `data/streaming`，15个文件（含说明PDF）与下载包SHA-256一致；下载目录未改动。

## 事实与实际策略

| 项目 | 结果 |
| --- | ---: |
| 原有唯一播放 | 94,760 |
| 新包原始 / 唯一记录 | 96,986 / 96,881 |
| 新增 / 移除 / 复用 | 2,121 / 0 / 94,760 |
| 完全重复，自动跳过 | 105 |
| 旧ID缺失 / 旧时间、时长、源指纹变化 | 0 / 0 |

预检 `comparable / snapshot_superset / incremental`，实际执行append。运行 `df897f874686`，批次 `2b42c013c2034346919a850cf325d1b3`。涉及5个周、1个年份；最新播放 `2026-10-18T20:07:10Z`，即北京时间10月19日04:07:10。旧指纹基线已完整；本次完整来源与目标count/digest对齐，增量写事实同时登记可重放的完整来源，无需替换旧播放。

## 失败与修复

- 首次元数据维护因代理连接中断失败，已提交事实及来源保留。代理/直连探针复核后，恢复进程临时清空代理环境，直连认证及元数据补齐成功，错误数0；未改项目、Codex或系统配置。网络异常本次被分类为不可重试，使用既有generation/digest fence阶段runner恢复，没有直接篡改状态或重放ETL。
- 专辑名称/艺人更新使7个自动目录项目被替换，旧外部ID引用导致父项目删除失败。`_upsert_project` 现在只在同一主来源专辑、同scope、带目录映射且唯一的自动owner上复用稳定ID；人工、无目录证据和多owner不走此复用。外键保持开启，副本中179条旧目录映射全部保留，外键问题0。
- 核心预热成功但健康仅有历史提示时，原 `partial` 被误判为元数据失败。执行状态现为 `ready`，独立保留 `health_status` 和warning数；硬blocker仍阻断。失败attempt保留，修复后定点恢复。

相关5个测试文件65项通过，Ruff通过。没有运行默认完整全栈，专项验证不代表全栈Pass。

## 派生维护与查看

元数据、身份、Album Project/L3和周聚合已完成。L3归属7,015条；Album Project因 `closure_too_large`、Billboard因 `billboard_base_incompatible` 安全回退全量派生计算。事实仍只追加2,121条，两种策略分别报告。

导入运行最终为 `succeeded / ready`，四套搜索精确上下文与四套详情年榜投影均ready。默认播放统计/播放记录的lifetime、last_4_weeks、last_6_months六份结果，以及档案、社区、治理、四套对决个人排名及艺人排名维护均已完成；封面197项全部done，无pending/running任务。2022–2026五年确定性年度总结已逐年预计算。重启日常入口后，19个主要消费接口全部HTTP 200；首页/档案/社区和六份分析结果为current/ready。另核对健康、运行和同包预检；预检为identical/noop。

稳定发布另经历两类失效：封面image_path写回推进分析revision，以及main publication_state从core_ready切到ready推进同一revision，使已构建的Billboard结果失效。本轮先排空封面，再按最终ready状态调用既有Billboard维护补发，最终exact检查通过；没有修改依赖追踪合同，也未将此前失败改写为成功。此后只验证最终读取，不继续扩展依赖治理修复。

最终SQLite integrity_check=ok、foreign_key_check为空；95,500条audio、1,381条video，原始时长16,054,838,068ms。

聚合证据JSON、旧目录与副本均保留在上述本地恢复点；个人原始数据和数据库不进入Git。

## 最终页面核验

本地日常入口 `http://127.0.0.1:4173/` 已启动并在浏览器保留。首页显示最近区间2026.09.22–2026.10.19、有效播放69,485、4,421h、6,429首不同歌曲；最新完整榜单周2026.10.09，冠军歌曲/专辑/艺人正常显示。浏览器仅核验首页，不代表全站浏览器矩阵。

首次首页虽HTTP 200/current，榜单预览却为unavailable：冷进程未从持久周榜恢复内存中的小预览。维护进程从已有exact周榜恢复预览，再用既有builder原子补发首页，并重启本轮拥有的日常入口清除旧内存结果；接口与浏览器复查均正常，没有修改事实或让首页GET冷建全榜。冷恢复边界并入SS-2026-10-20-002，未扩展代码修复。

最终健康为partial，但safe_to_use=true、blockers=0、当前统计问题数0；唯一说明项是239条无曲目音频记录，按原始事实保留。65项专项测试、Ruff、文档审计和diff检查通过；日常前端构建通过。源码修复及报告未提交，无生产写入。

## 后续根因修复

用户授权处理剩余问题后，补齐以下本地代码，原失败attempt与上述临时处置记录均保留：

| 问题 | 现在的处理 | 验证边界 |
| --- | --- | --- |
| 封面路径、发布状态使统计快照自失效 | analysis触发器和全内容oracle统一排除image_path及五个publication运维字段；保留generation/digest/count/playback_revision与实际成员依赖。迁移91更新旧库合同。 | seed回归及真实Online Backup副本：运维写回revision不变，真实播放修改仍失效，重复迁移epoch不变；只读缺合同仍拒绝。 |
| 网络错误误记为不可重试 | 明确识别ProviderNetworkError、429与5xx的标准异常并记录稳定error code；认证和解析错误仍不泛化为可重试。 | 网络失败后metadata单阶段续跑成功；复用原ChangeSet与事实栅栏，不进入播放ETL。沿用HttpClient既有有限重试与阶段retry/startup恢复，没有无限重试或自动改代理。 |
| 首页冷进程预览缺失、旧unavailable文件长期命中 | 私有预热和后台首页维护从exact weekly恢复最近两周的小预览，再原子更新首页；Billboard后台发布完成后刷新首页。 | 缺exact不借LKG冒充ready；公开请求不恢复、不构建或写入。已存在unavailable首页文件由维护替换的回归通过。 |
| readiness重复attempt、候选阶段停在warming | 同一进程并发复查合并，持久证据/依赖不变时不重复记attempt或更新run；就绪后完成原warming候选attempt，保留失败历史；每次实际复查仍过事实栅栏。 | ready/failed重复复查均幂等；真实API连续两次复查保持exact attempt=18、candidate=succeeded。 |

定向回归累计135个不同用例通过（10文件首轮133项；新增网络续跑和旧首页修复用例后，受影响两文件46项通过，其余结果复用），Ruff通过。专项涵盖公开读取边界；未运行默认完整全栈、CI或生产验证。

启用前在原恢复点新增 `followup-fixes/`，对七库及控制库执行Online Backup。真实副本的迁移、运维写回与正向事实失效探针通过，integrity=ok、FK=0。探针首次在未提交事务内读取revision被既有合同拒绝，随后改为在副本提交测试写入后验证；正式库未执行故障写入。

代理链路本身未修改，当前日常进程延续本次获准的临时直连环境；未来网络恢复后可从可重试阶段继续。239条无曲目音频仍是源数据说明项；Album Project/Billboard安全回退全量派生的边界继续保留，不影响原始事实增量导入。未提交、推送或部署。

本机正式运行库已应用迁移91并自动完成受影响的派生维护，2022–2026年度结果重新准备。96,881条play_id/ts/ms_played/source_fingerprint逐条与本轮修复前备份一致，完整性ok、FK=0。对账工具首次ATTACH备份失败，改为两个独立只读连接逐条比较后通过，没有修改正式事实。

最后冷启动日志明确为“Billboard snapshots already current; startup rebuild skipped”，Billboard任务总数重启前后均29，没有为恢复预览重算完整榜单。首页HTTP 200、current/ready且榜单预览ready；19个主要消费接口再次全部200，分析/档案/社区快照current/ready。运行仍succeeded/ready，八个最新阶段均succeeded，待运行任务0；两次额外复查的attempt和run.updated_at均不变。JSON和原日志位于 `followup-fixes/`，包括 `migration-probe.json`、`facts-preserved.json`、`readiness-idempotence.json`、`cold-restart.json` 及API结果。SS-2026-10-20-002本地结项，未验证CI、生产或全站浏览器矩阵。

## 署名续跑与独唱合唱归并补修

用户随后发现expectations专辑独唱版与未标feat的合唱录音在L2合并。SS-2026-10-20-006已经实现并本地应用；前文135项回归的结果保留，但没有覆盖本次中途失败后的署名应用缺口。

根因：首次metadata attempt在UTC06:27提交Track及署名证据，06:30于Album网络请求失败，未执行函数末尾的自动署名应用；06:32续跑只抓取12条剩余Track，已经有证据的50155被跳过。另一个独立缺陷是L2只比较primary artist，补上featured署名后仍会把同名独唱/合唱接受为同组。内存副本分别复现了这两个缺陷。

schema93新增逐owner应用状态，绑定证据签名、ID归属、艺人解析、策略及自动覆盖内容。覆盖、状态及credit revision同事务；续跑先补缓存应用，最后核对剩余应用。导入中延后独立credit job，由现有identity → L2/L3 →聚合→快照链统一维护。pending阻止exact ready；blocked是身份歧义的明确处理结果，保留当前有效署名、原因及健康说明，相关L2候选保持pending，不冒充自动应用成功。

L2加入完整生效canonical参与集合和未应用证据门禁，标题连接、传递连接与ISRC fallback均不能绕过；人工覆盖仍优先。L3保留合法作品关系。版本列表改为显示曲名并另列“来源发行”，明确50124虽然来自合唱单曲发行，但本身仍是独唱录音。

备份与证据保留在忽略目录`data/import_backups/track-credit-20261020T090526Z/`，包含七库、控制库、probe/apply计划及结果、待核清单、API结果、统计对账和启动日志。先在副本验证后停止本轮拥有的本地服务应用，再离线完成周聚合，重启正常维护，未调用外部写接口。

| 结果 | 本地证据 |
| --- | --- |
| 自动署名维护 | 审计7,726个有缓存证据的owner；补应用/纠正444首，创建19个由Spotify ID确定的艺人；33首身份歧义保留blocked。pending=0。 |
| 分组修复 | 8个机器L2分组成员关系调整，人工分组、署名覆盖及歌曲归并覆盖逐条保全；L2/L3重复计划无变更。 |
| expectations L2 | 48690、50124同组23次；50123与50155分别保留5次、2次。 |
| expectations L3 | 48690、50123、50124、50155仍为同一作品30次；修复前后summary一致，时长1.8h，原始三表逐条相同。 |
| 事实保护 | plays 96,881、tracks 10,480、track_artists 10,964全列逐条保全；integrity=ok，FK问题0。 |
| 派生维护 | 本次关系变更安全全量重建周聚合，不重导入播放；四套搜索及四套详情年榜ready，默认派生队列清空，2022–2026年度准备完成，首页榜单预览ready。 |
| 定向验证 | 162项后端unit、Ruff、前端正式构建通过；4入口×L2/L3×summary/overview共16接口200/current/ready；Encore新旧项目ID仍解析41476。 |

脚本第一次对账预期详情API会重写请求track_id，实际摘要保留请求身份，随后改核对canonical归属和相同统计；该脚本断言问题未改业务代码。首次读取WAL格式备份使用mode=ro失败，改为immutable只读备份后完成前后统计对账。新回归的最小schema夹具起初缺少refresh依赖的艺人/封面列，补齐后通过；保留这些工具失败记录，不计为业务回归通过。

SS-2026-10-20-007继续OPEN / REVIEW：33首blocked涉及来源署名与现有主艺人/身份解析冲突，未擅自修改全球艺人身份；清单及具体reason在`apply-blocked.json`。健康报告同时保留239条无曲目音频说明。未提交、推送或部署，没有运行默认完整全栈或生产验收。


## 全库 L2 独唱与合唱误合并复查

用户要求检查其他歌曲，并核对详情与榜单。此轮复查覆盖全部7,724个活动曲目身份及172个活动L2录音组（171个自动组、1个人工组），共356个分组成员；356个成员全部有缓存Spotify结构化署名证据。逐组比较完整有效canonical参与艺人集合，并核对署名应用状态、语义版本和人工覆盖。

- 当前活动L2组内参与艺人集合冲突为0，未应用/身份歧义成员为0，本轮没有发现需新增拆分的组。因此没有重复应用分组计划，也没有重建已经正确的快照。
- 上轮全库维护已经调整8组，不能描述成只修了expectations，也不能将8组全部描述成“独唱/合唱”：其中包括不同演出阵容和署名歧义的保守分离。修复前备份和应用收据可逐组追溯。
- 唯一跨标题合作标记的组是人工组5874《手心的薔薇》：852与4309的有效参与者均为JJ Lin、G.E.M.，只是一个标题没有ft.，保留人工归并。
- 33首身份歧义仍为blocked（SS-2026-10-20-007），pending=0；这些曲目均不在当前活动L2组内。不能因此声称33首身份均已治理完毕。

| 上轮调整的歌曲 | 本轮L2有效播放及当前状态 |
| --- | --- |
| 天黑黑 | 2948、3481保留同组114次；参与者增加Lin Zheng-Zhong的50145独立。该曲仅两条0毫秒原始记录，详见下方详情边界。 |
| JOYRIDE | 3272为2次、5829为1次，保持独立；3272署名解析歧义未消除，不将其称为已确认独唱/合唱冲突。 |
| For Good | 原卡司3559为55次、另一演出阵容4266为45次，独立。 |
| Gonna Build a Mountain | Lady Gaga独唱2972为1次，Lady Gaga/Joaquin Phoenix的3573为0次，独立。 |
| City of Stars | Ryan Gosling/Emma Stone的3832为7次，Ryan Gosling的5799为0次，独立。 |
| Guess featuring Billie Eilish | 2815为1次，增加FINNEAS、The Dare署名的49692为0次，保持独立；不将结构化艺人名单等同于已确认的演唱角色。 |
| Whenever You Call | Mariah Carey独唱992为14次，Mariah Carey/Brian McKnight的49894为1次，独立。 |
| expectations | 独唱48690/50124同组23次，50123为5次、50155为2次，继续独立。 |

详情与榜单实测：

- 逐一访问上述18首曲目的L2 summary/overview，共36个接口；其中17首的34个请求为200且snapshot ready/current。有效播放量与直接只读统计一致；overview版本成员与活动L2成员一致；页面入榜状态、每周排名和播放次数与周榜完整一致。
- 唯一例外是50145的summary/overview均503 `snapshot_unavailable`。直接核对原始两条记录均为0毫秒，直接统计没有summary，该曲独立身份存在，但没有已发布的目标统计context。本轮保留既定缺失事实拒绝回退合同，未制造0值页面；这两个请求不计为详情通过，也不能宣称全部详情200。
- 已发布的全部6,742条L2周榜记录逐条检查：条目ID均为当前L2代表ID，播放次数均等于当前成员在`agg_weekly_tracks`中的当周贡献之和，没有继续使用修复前的跨录音合计。最新完整周仍为2026-10-09；未入榜的独立实体不强行生成榜单条目。
- 浏览器实测《Whenever You Call》两个独立页面：独唱只署名Mariah Carey、14次；合唱署名Mariah Carey和Brian McKnight、1次并显示未入榜。独唱历史跳转2023-12-29周榜后为第22名、2次，深链指向992，和详情一致。
- 原始plays 96,881、tracks 10,480、track_artists 10,964行全列逐条与修复前Online Backup相同，人工分组与36条曲目署名覆盖保全；integrity=ok、FK错误=0。本轮没有业务代码、源数据或分组写入，无需重复运行上轮162项代码回归；仅补充真实数据、接口和浏览器证据。

本地证据保存在`data/import_backups/track-credit-20261020T090526Z/`：`l2-collaboration-audit.json`、`l2-collaboration-api-verification.json`、`l2-collaboration-detail-payloads.json`、`l2-collaboration-conservation.json`及对应只读脚本。验证脚本初轮误将周榜的legacy `snapshot=null`与摘要不返回version_group视为异常；按实际接口合同改为验证周榜事实及overview的`meta.version_group.versions`，未因此修改业务代码。0毫秒50145的503作为独立边界保留。范围为本地默认L2过滤，未扩展到全站、CI或生产发布。


## 艺人身份歧义治理与零毫秒详情修复

用户授权继续治理33首阻塞项并修复零毫秒50145。恢复点为`data/import_backups/artist-review-20261020T100949Z/`（七库及独立导入控制库），先在`probe.db`验证后应用正式库。

### 已确定并应用的15首

- Jason Zhang（439）与張杰（8517）指向相同Spotify艺人ID `75udD9hen8NeHTe92rUNLa`。通过身份治理API统一到439，保留Jason Zhang展示名，生成可撤销identity event19；涉及2197、5699、49726–49734共11首。
- 黄霄云（688）与黃霄雲（8529）为简繁同名，3751《星辰大海》结构化署名提供唯一Spotify ID，统一到688，生成可撤销identity event20。
- 5091《风华正茂 - Live》门尼/門尼为简繁同名，已验证外部ID关联825到`7f331FTM03lasCUX19RGsy`，TIA RAY合作署名保留。
- 3414《PLATONIK》的Danna Paola/DANNA由[Universal官方CHILDSTAR发行页](https://universalmusicmexico.lnk.to/2024)（旧署名Danna Paola及PLATONIK）和[现行Danna艺人页](https://www.universalmusicmexico.com/artist/danna/)确认，绑定原646身份的已验证Spotify ID。
- 3272《JOYRIDE》原始Track Spotify ID已不属于当前owner，而其拥有的两个Spotify ID的有序artists证据完全一致。自动应用允许在等价证据中稳定选择，证据不同仍blocked；不重写owner/raw track。3272与5829恢复同一L2组，合计3次。应用策略升为`spotify_owner_credits_v3_equivalent_evidence`。

共解除15首阻塞，自动署名投影13首改变，无新增艺人。pending=0、blocked=18；L2由172组变173组，新增JOYRIDE组，L3归档其已由完整L2承载的冗余作品组。expectations L2仍为独唱23次、合唱5/2次独立，L3四成员不变。全部173个L2组参与集合冲突0。

### 零毫秒曲目详情

根因：`_context_rows()`跳过已完成扫描但次数/时长均0的曲目，曲目统计builder又将空收听帧视为不存在。现在维护期为已索引曲目发布明确0/0事实，完整构建与ledger增量重建一致；曲目存在时返回完整空统计，首次/最近有效收听为null。缺失或损坏事实仍拒绝读取，GET不冷建。

快照builder升为`music_search_snapshot_v13_zero_track_context`，迁移版本声明同步至已注册93。50145两条原始0毫秒记录保全；summary/overview/stats均200，0次/0小时，首次/最近为“—”，最近播放为空，榜单未入榜，没有生成零播放榜单条目。浏览器已实测两个页签及滚动后的最近播放空状态。

### 需要用户确认的18首

> 此表保留当时待确认状态。用户随后已批准建议，当前应用与验收结果见[用户确认后的身份与逐曲署名收口](#用户确认后的身份与逐曲署名收口)。

以下项没有写入新身份合并或曲目覆盖，继续保留blocked及现有有效署名。Track artists证明具体发行的署名，不能单独证明不同Spotify档案是同一人，也不能替用户决定个人、组合和独立艺名是否共用统计身份。可按track_id逐项回复，4170/5903与4704/5726可成组确认。

| 曲目 | 待确认类型 | 本地身份 | 本曲Spotify结构化署名 | 建议与需确认内容 |
| --- | --- | --- | --- | --- |
| [545 · We Don't Talk About Bruno](http://127.0.0.1:4173/music/tracks/545?merge_level=2) | 同名档案冲突 | Carolina Gaitán（artist_id=107）；[现有Spotify档案](https://open.spotify.com/artist/10dkJJ1zEFfkVmQBI8fgOx) | [Carolina Gaitán - La Gaita](https://open.spotify.com/artist/29PgYEggDV3cDP9QYTogwv)、[Mauro Castillo](https://open.spotify.com/artist/36CUTsdtNgCwMq6zKD1l8I)、[Adassa](https://open.spotify.com/artist/72kqSqk124Vnl1wtT6q9Fh)、[Rhenzy Feliz](https://open.spotify.com/artist/2as15AH2BTrPk8v4gyElmr)、[Diane Guerrero](https://open.spotify.com/artist/18MFcGBHtyW0mU3ufcm0X1)、[Stephanie Beatriz](https://open.spotify.com/artist/5PYToRCsrnvikZg3yl2JMr)、[Encanto - Cast](https://open.spotify.com/artist/3xLU748QxpTmIVaiNXXg0P) | Carolina Gaitán与La Gaita的Spotify ID不同。建议先仅本曲采用La Gaita的发行署名，暂不全局合并；请确认。 |
| [1207 · Club Believer](http://127.0.0.1:4173/music/tracks/1207?merge_level=2) | 同名档案冲突 | Jeak（artist_id=205）；[现有Spotify档案](https://open.spotify.com/artist/5hHQtouVj7uD8NSUEp9AbK) | [Jeak](https://open.spotify.com/artist/4JUettwlB4WVsbyV4nesPo)、[Tiborg](https://open.spotify.com/artist/017LB7BYpa2Bmvzbkg0fHE) | Jeak现有ID与本曲ID不同，需确认是否同一人，再决定统一或保留独立Jeak；合作艺人Tiborg不能遗漏。 |
| [2713 · 多心](http://127.0.0.1:4173/music/tracks/2713?merge_level=2) | 组合与成员 | Michael Wong（artist_id=382）；[现有Spotify档案](https://open.spotify.com/artist/26SQFo2qNNGOxh2PUAsTeO) | [無印良品](https://open.spotify.com/artist/1cONRqlhCuf0bNtBVBm0hC) | 本地归Michael Wong，Spotify归無印良品。建议组合/成员保持独立，仅按所选发行修正本曲；请确认。 |
| [3282 · 再见](http://127.0.0.1:4173/music/tracks/3282?merge_level=2) | 别名待确认 | Matt吕彦良（artist_id=621）；暂无Spotify ID | [Matt Lv](https://open.spotify.com/artist/71vPRIlP7xw7wawonVE4ax) | 是否将Matt吕彦良与Matt Lv认作同一人，绑定该Spotify ID？ |
| [3431 · 身邊](http://127.0.0.1:4173/music/tracks/3431?merge_level=2) | 组合与成员 | 無印良品（artist_id=518）；[现有Spotify档案](https://open.spotify.com/artist/1cONRqlhCuf0bNtBVBm0hC) | [Victor Wong](https://open.spotify.com/artist/70ht8hGTKjvbPJ37xVO9cW)、[Michael Wong](https://open.spotify.com/artist/26SQFo2qNNGOxh2PUAsTeO) | 本地归無印良品，Spotify列Victor Wong、Michael Wong。建议不全局合并组合/成员，本曲按两位成员署名；请确认。 |
| [3433 · 每一次喊你](http://127.0.0.1:4173/music/tracks/3433?merge_level=2) | 组合与成员 | 無印良品（artist_id=518）；[现有Spotify档案](https://open.spotify.com/artist/1cONRqlhCuf0bNtBVBm0hC) | [Michael Wong](https://open.spotify.com/artist/26SQFo2qNNGOxh2PUAsTeO) | 本地归無印良品，Spotify仅列Michael Wong。建议组合身份保持独立，本曲按该发行归Michael Wong；请确认。 |
| [3659 · Stay (I Missed You)](http://127.0.0.1:4173/music/tracks/3659?merge_level=2) | 组合与成员 | Lisa Loeb（artist_id=675）；暂无Spotify ID | [Lisa Loeb & Nine Stories](https://open.spotify.com/artist/4a7CDXcRCXi4kp5z7SEXtg) | Lisa Loeb与Lisa Loeb & Nine Stories是个人/组合差异。是否保留组合独立，本曲归组合？ |
| [3822 · 一念執著](http://127.0.0.1:4173/music/tracks/3822?merge_level=2) | 同名档案冲突 | 胡歌（artist_id=702）；[现有Spotify档案](https://open.spotify.com/artist/5UdHvTeCIVfpFb8ijyKdJl) | [胡歌](https://open.spotify.com/artist/04T9gfyccsmxG79OSJp5r1)、[阿蘭](https://open.spotify.com/artist/6mKe9KBbcbx01sxxTOM7A1) | 胡歌现有Spotify ID与本曲不同，请确认是否重复档案。本曲应保留阿蘭的合作署名。 |
| [3880 · 情人咒](http://127.0.0.1:4173/music/tracks/3880?merge_level=2) | 中英文及档案冲突 | Yisa Yu（artist_id=373）；[现有Spotify档案](https://open.spotify.com/artist/75CM5fojYdKYD0xYSFh22Z) | [郁可唯](https://open.spotify.com/artist/4XOgZBMcpRQqKHbE8L9zW1)、[Ayanga](https://open.spotify.com/artist/1c48HJvfsdzRQSr9svnE8B) | Yisa Yu与郁可唯看似别名，但Spotify ID也不同，请确认两个档案是否统一；本曲另有Ayanga。 |
| [4057 · Adrenaline Rush](http://127.0.0.1:4173/music/tracks/4057?merge_level=2) | 同名档案冲突 | Michael Wong（artist_id=382）；[现有Spotify档案](https://open.spotify.com/artist/26SQFo2qNNGOxh2PUAsTeO) | [Michael Wong](https://open.spotify.com/artist/0vf3OWbxq6KDSfkJUp8022) | 本曲Michael Wong的ID不同于现有光良身份。建议保留独立身份，避免将同名英文曲计给光良；请确认。 |
| [4170 · 1987我不知会遇见你](http://127.0.0.1:4173/music/tracks/4170?merge_level=2) | 别名待确认 | Chris Lee Artiste（artist_id=750）；暂无Spotify ID | [Chris Lee](https://open.spotify.com/artist/02VPWD8AZ7qSuug0dM4Hk1) | 是否将Chris Lee Artiste与Spotify的Chris Lee（李宇春发行）统一？与5903一起处理。 |
| [4704 · Tokyo](http://127.0.0.1:4173/music/tracks/4704?merge_level=2) | 别名待确认 | Sebastian Croft（artist_id=790）；暂无Spotify ID | [Bash Croft](https://open.spotify.com/artist/0z6dMH7qcKgqKnJy4j9nil) | 是否将Sebastian Croft与Bash Croft统一？与5726一起处理；艺人自建歌单不能单独证明身份关系。 |
| [5368 · 你的存在就是愛我](http://127.0.0.1:4173/music/tracks/5368?merge_level=2) | 艺名统计选择 | A-Mei Chang（artist_id=21）；[现有Spotify档案](https://open.spotify.com/artist/6noxsCszBEEK04kCehugOp) | [阿密特](https://open.spotify.com/artist/2WpN5ddRbqM9mb2Xjxcy5l) | 阿密特与A-Mei Chang是否共用统计身份？现有张惠妹是人工组，不自动吸收；也可保留独立艺名，仅修本曲。 |
| [5726 · Better than ever](http://127.0.0.1:4173/music/tracks/5726?merge_level=2) | 别名待确认 | Sebastian Croft（artist_id=790）；暂无Spotify ID | [Bash Croft](https://open.spotify.com/artist/0z6dMH7qcKgqKnJy4j9nil) | 同4704：Sebastian Croft与Bash Croft是否统一？ |
| [5729 · 张学友之歌](http://127.0.0.1:4173/music/tracks/5729?merge_level=2) | 同名档案冲突 | 8（artist_id=904）；[现有Spotify档案](https://open.spotify.com/artist/65fhULmtkynLZf1ylcBxm0) | [8](https://open.spotify.com/artist/65fhULmtkynLZf1ylcBxm0)、[Jacky Cheung](https://open.spotify.com/artist/6rESBiNTAqtyP56ihK42Bb) | Jacky Cheung本曲ID不同于现有张学友身份，需确认档案关系，不能仅凭名称合并。 |
| [5903 · 是你（电视剧《难哄》片尾曲）](http://127.0.0.1:4173/music/tracks/5903?merge_level=2) | 别名待确认 | Chris Lee Artiste（artist_id=750）；暂无Spotify ID | [Chris Lee](https://open.spotify.com/artist/02VPWD8AZ7qSuug0dM4Hk1) | 同4170：Chris Lee Artiste与Chris Lee是否统一？ |
| [49593 · (Drop Dead) Beautiful (feat. Sabi)](http://127.0.0.1:4173/music/tracks/49593?merge_level=2) | 同名档案冲突 | Britney Spears（artist_id=53）；[现有Spotify档案](https://open.spotify.com/artist/26dSoYclwsYLMAKD3tpOr4) | [Britney Spears](https://open.spotify.com/artist/26dSoYclwsYLMAKD3tpOr4)、[Sabi](https://open.spotify.com/artist/3tB8VKd0rtEnc9x8l78ymo) | 本曲Sabi与现有Sabi的Spotify ID不同；需确认是同一歌手还是独立身份。 |
| [49722 · 我期待](http://127.0.0.1:4173/music/tracks/49722?merge_level=2) | 同名档案冲突 | Zhang Yu Sheng（artist_id=814）；[现有Spotify档案](https://open.spotify.com/artist/3LefT7hR0PJgShJNQoPns5) | [Zhang Yu Sheng](https://open.spotify.com/artist/3LefT7hR0PJgShJNQoPns5)、[Mark](https://open.spotify.com/artist/4pFXWOmjmZo6dPOdd7YDwS) | 合作艺人为Mark，现有近似名称Márk的ID不同。建议保持独立，不因去重音规范化合并；请确认本曲身份。 |

### 本地验证结果

- 141项快照/ledger/详情/空统计/署名恢复回归及46项增量维护/身份治理/Spotify证据回归通过，共187项。新增fixture首轮漏第二个Spotify meta父行，修正fixture后通过；迁移检查发现LATEST_SCHEMA_VERSION仍为90，纠正为已注册93后46项通过。历史失败日志保留。
- 四套精确快照及四套详情年榜投影ready/current；40首summary、overview、stats共120次请求200，覆盖原33首、50145及独唱/合唱对照。直接统计、版本成员和周榜历史一致。Jason Zhang/張杰、黄霄云/黃霄雲4次艺人摘要200，同身份返回相同canonical名、播放及榜单摘要。
- 全部6,742条L2周榜与当前成员周贡献逐条一致，零播放不入榜，覆盖边缘周不发布。健康safe_to_use=true，当前统计问题0，身份阻塞显示18。
- Online Backup对账：plays96,881、tracks10,480、track_artists10,964全列逐条相同，36条人工署名覆盖、人工歌曲分组及原15个艺人身份组保全。新增两个身份组与两个已验证外部ID关联有来源；integrity=ok、FK错误0。
- 本轮无前端代码变动，复用现有正式构建，本地服务重启并验证；没有提交、推送、CI或生产发布。

脚本与证据保存在上述恢复点：`probe-result.json`、`apply-result.json`、`api-verification.json`、`api-payloads.json`、`snapshot-publication.json`及维护/测试日志。API探针首轮误用艺人summary字段，按真实合同改为chart_summary及effective_play_count后完成，未为探针修改业务接口。

最终收口：2022–2026年度总结及首页已准备完成；最终只读对账确认8,774条Spotify owner全列逐条、1,960个既有艺人名称、原始三表及人工覆盖全部保全，background_jobs待运行/运行中为0，readiness=ready。`final-conservation.json`保存最终结果。待用户确认的18首没有自动合并或新增覆盖。


## 用户确认后的身份与逐曲署名收口

用户明确批准按建议处理：阿密特与张惠妹共用统计，但保留发行署名；其余冲突先逐曲纠正，不全局合并。先做七库及独立导入控制库Online Backup，在副本验证后应用；本轮恢复点为`data/import_backups/confirmed-credits-20261020T142012Z/`。

### 实际应用

- 已确认别名登记为可撤销身份组：Chris Lee Artiste/Chris Lee统一到750；A-Mei Chang/張惠妹/阿密特统一到21；Matt吕彦良/Matt Lv统一到621；Sebastian Croft/Bash Croft统一到790；Yisa Yu/郁可唯统一到373。身份事件21–25、revision最终26。原身份组10按用户选择扩展，其余既有组保全。新增三个别名名称入口，避免只绑定外部ID却无法按新旧名称稳定打开同一艺人页。
- 11首逐曲纠正共27条可审计覆盖：545完整七方署名；1207归该发行Jeak与Tiborg；2713归無印良品；3431归Victor Wong与Michael Wong；3433归Michael Wong；3659归Lisa Loeb & Nine Stories；3822保留该发行胡歌与阿蘭；4057归Adrenaline Rush的独立Michael Wong档案；5729保留8与该发行Jacky Cheung；49593保留Britney Spears与该发行Sabi；49722保留Zhang Yu Sheng与Mark。
- Carolina两档、Jeak两档、组合与个人、胡歌两档、Michael Wong同名档、Jacky Cheung两档、Sabi两档及Mark/Márk均未因此全局合并。必要的新档案按具体发行区分显示名称，不把“不同Spotify档案”断言为“不同自然人”。共新增12个provider艺人实体（含自动补齐Ayanga）和3个已确认别名入口，1,960个既有艺人名称保全。
- 原待确认18首全部解除，加上前批15首，原33首阻塞已全部处理；应用覆盖pending=0、blocked=0，并非隐藏阻塞提示。自动署名本批18首改变，补别名后再次同步改变0，证明可幂等复用。
- 修正3433后与3196形成同一Michael Wong独唱L2组6503，合计5次；活动L2组174个，组内canonical参与集合冲突0。expectations独唱L2仍为48690/50124共23次，两条合唱50123/50155分别5/2次；L3四成员30次保持。

### 防复发与展示

应用策略升为`spotify_owner_credits_v4_reviewed_primary`。当原始主艺人与该发行署名不一致时，仅允许已有active逐曲人工覆盖、所有provider成员均唯一解析、有效canonical参与集合与完整provider集合完全相等且存在有效primary的曲目恢复应用；部分覆盖仍阻塞。应用输入指纹纳入有序active人工覆盖，撤销或证据变化会重新进入待应用，而不是复用过时成功状态。

曲目summary与完整详情的primary统一读取有效署名，不再错误展示原始主艺人。API另保留有序`meta.release_artist_names`，桌面与Phone在发行署名不同于统一统计身份时显示“发行署名”；5368因此链接A-Mei Chang统计页，同时明确显示“发行署名：阿密特”。专辑名称入口沿用既有行为，本轮没有修改其路由解析。

### 最终验证与边界

- 定向后端110项、前端14项通过；TypeScript/Vite正式构建通过。后端保留现有LibreSSL警告，前端保留既有chunk大小提示，不把警告伪称为失败。
- 本地40首summary/overview/stats共120请求200，包含原33首、零毫秒50145与独唱/合唱对照；均与直接统计、有效署名、当前L2成员和历史周榜一致。11个别名艺人摘要入口200，同组canonical名、播放量与榜单摘要一致。
- 全部6,742条L2单曲周榜与当前成员周贡献逐条一致，全部4,453条艺人周榜与当前canonical聚合逐条一致。四套精确统计与四套详情年榜ready；2022–2026年度和首页已准备，最终readiness=ready、background_jobs待运行/运行中0、健康safe_to_use=true。
- 实际浏览器：5368显示统一统计名A-Mei Chang、发行署名阿密特、累计8次；2026-01-02周榜第16名、3次，与详情一致。3431显示Victor Wong/Michael Wong、1次、未入榜，不再使用無印良品作本曲主艺人。浏览器详情与桌面周榜核对完成；Phone/桌面发行署名组件均有定向回归，未扩展为全站多浏览器验收。
- 最终Online Backup全列逐条对账：plays96,881、tracks10,480、track_artists10,964、Spotify owner8,774均未变；旧36条人工覆盖、人工歌曲分组、既有名称及除获准扩展组10外的既有身份组保全。integrity=ok、FK错误0。
- 辅助专辑探针发现42398虽有项目引用，但对应详情返回404；这是本轮曲目/艺人验收之外的专辑发布范围边界，不计作专辑链接全部通过。保留失败日志，并撤回了本轮附带尝试的专辑深链改动；最终探针只对本轮授权的曲目、艺人和周榜作通过判断。首次年度准备早于周榜后台完成也曾失败，等待实际维护结束后再次准备成功，原日志保留。

证据包含`probe-result.json`、`apply-result.json`、`apply-name-aliases.json`、`snapshot-publication.json`、`api-verification.json`、`api-payloads.json`、`final-conservation.json`，以及测试、正式构建、两次发布、年度准备与只读探针脚本。仅本地实现、应用与验收；未提交、推送、运行CI或部署生产。冲突档案的全局身份归并仍按用户决定暂缓，后续若确认再通过独立身份治理处理。


## 导入与Spotify刷新后的治理持久性复验

用户要求确认逐曲纠正与艺人身份在后续导入、刷新后不会丢失。本轮沿实际写入链审计并补修两处保护，仍属SS-2026-10-20-007问题链；没有执行真实外网刷新或再次向正式库导入播放。

### 保留规则与补修

- `track_credit_overrides`及其审计、`artist_identity_groups/members/events`是独立持久治理层；导入replace/append/reconcile不会清空它们。已知Spotify Track ID优先复用稳定owner，不按标题重新建曲；有效署名最后叠加人工覆盖、再按活动canonical身份去重。未知的新Spotify Track ID拥有独立临时曲目，不按歌名直接继承其他曲目的人工覆盖。
- 查实封面搜索分支原来无条件更新`artists.spotify_artist_id`。现在Track精确同名关联与封面名称搜索共用既有Spotify ID约束，包含本艺人及已批准canonical别名成员的便捷ID与verified外部ID。名称匹配不得追加与既有身份冲突的ID；封面搜索也不能替换已有便捷ID。冲突报告`artist_identity_conflict:<artist_id>`，不写错误ID、外部关联或封面；原有已验证证据不降级。
- 查实完整逐曲审核仍有一处漏洞：当Spotify继续包含原始主艺人，自动应用可能接受新增/移除的其他成员。现在对active `spotify_track_review`审核要求完整canonical成员集合仍与当前已审核有效集合一致，任何未解析成员或集合变化均保留旧自动投影和人工署名，并以`reviewed_track_credits_changed`阻塞。L2对blocked/pending证据继续等待，标题、传递连接及ISRC不得绕过。普通局部add/remove覆盖不冒充完整发行审核。
- 应用策略升级为`spotify_owner_credits_v5_reviewed_members`；正式库只重核7,726个owner的应用状态，changed=0、skipped=0、created_artists=0、署名revision不变，pending=0、blocked=0。没有重算未变的统计；本地后端已重启加载新保护，启动明确复用当前Billboard快照。

### 副本与实际接口验证

- Online Backup恢复点`data/import_backups/identity-persistence-20261020T145827Z/`保存正式库基线、probe及正式库应用状态更新证据；额外已确认别名导入副本为`identity-persistence-20261020T150228Z/`。
- 基于40首受影响/对照曲目及其全部owner缓存证据，重放两轮正常Track/Artist元数据写入与自动应用，均改变0；身份组、成员、事件、人工覆盖及有效署名保持。这里重放的是已保存的真实provider响应，不是现场调用Spotify网络。
- 两个副本均通过实际append ETL新增18条模拟未来播放，再重复同一批导入新增0条；新增播放全部指向原18个owner。第二副本特意将7条导出署名换成已确认的Matt Lv、Chris Lee、Bash Croft、郁可唯、阿密特，canonical有效署名不变。执行日常导入共用的L2/L3归并planner，L2成员集合保持；expectations独唱/合唱L2分离、L3四成员关系保持。未扩展到模拟播放的下游全量统计发布。
- 对11首逐曲纠正分别注入额外不符的provider参与艺人，均blocked、改变0，旧有效署名及人工设置保持；攻击用savepoint回滚，不触及正式库。
- 新增7项有意义回归先在旧代码复现失败（4项身份ID覆盖、3项完整审核成员漂移），补修后与刷新/署名恢复/身份治理/L2/导入定向测试合计137项通过；Ruff与文档审计通过。仅后端逻辑变化，复用上一轮已验前端构建与展示证据。
- 正式库原始plays96,881、tracks10,480、track_artists10,964、Spotify owner8,774全列逐条与本轮备份一致；治理行、自动署名投影及署名/身份revision保持，integrity=ok、FK错误0。本地重启后6首曲目summary/overview共12请求和阿密特/張惠妹/A-Mei Chang三入口均200、current；阿密特发行署名保留，单/合唱与零播放对照正确，readiness=ready、健康safe_to_use=true。

证据为恢复点内`probe-result.json`、`primary-ledger-update.json`、`api-verification.json`、7项修复前失败日志、137项修复后日志及探针脚本；别名副本另保留其`probe-result.json`。本轮未提交、推送、CI或生产部署。逐曲覆盖的作用域是已识别的稳定曲目owner；新的未知发行或尚未确认的艺名不靠同名猜测继承人工决定，保留独立或待复核边界。


## 本地Git提交收口

本次提交以main `f9526aff`为基线，集中保存SS-2026-10-20-001/002/003/006/007/008这一导入与元数据治理问题链：

| 方面 | 当前交付结果 |
| --- | --- |
| 导入与恢复 | 项目ID/外部映射保全，迁移91修正非事实revision，网络阶段可重试、首页从精确周榜恢复，readiness幂等收敛 |
| 专辑归并 | 迁移92保存内容证据、人工分离、项目重定向与审计；任意名称扩展版走完整录音判定，Encore并入稳定41476 |
| 歌曲归并 | 迁移93分开保存证据与应用状态；续跑恢复署名，L2比较完整canonical参与集合，独唱/合唱仅在L3按作品关系汇总 |
| 身份与署名 | 33首阻塞已审核解除，阿密特/张惠妹共用统计并保留发行署名，11首按曲覆盖；后续刷新不替换已确认身份或静默改变完整审核的参与集合 |
| 零毫秒详情 | 曲目存在时维护期显式发布零值事实；50145详情可打开且不制造榜单条目，缺失事实仍拒绝读取 |

必要文档同步了规则、问题台账、开发状态、变更日志及两个文档索引；README的产品介绍和启动方式没有变化，AGENTS/CLAUDE保持相同且无需新增重复规则。既有分阶段回归、正式构建、副本守恒及浏览器证据按上文复用，提交前集中检查累计受影响代码与项目hooks；不把本地专项描述为全量全栈、CI或生产验收。

正式播放导出、数据库、封面、个人恢复点及模拟播放留在忽略的本地目录，Git只保存代码、测试和报告。周榜行高与播放条排版（SS-004/005）的三个界面文件和相应状态文档片段不纳入本次提交，工作区原改动保留。其余专辑候选仍只预览，同名冲突艺人不全局合并；辅助专辑42398无发布详情的404、资源/OOM观察及未发布边界保持记录。

交付状态为本地Git提交检查点，未推送、未运行远端CI、未部署生产；本机数据修复已应用不代表未来克隆仓库会自动获得个人治理数据。


提交前最终验证：27个后端定向文件共478项，首轮477通过、1项旧seed详情测试因revision触发器尚未迁移失败；该测试补充显式私有迁移后单项复验通过，其余477项同版本结果复用。前端详情14项通过。首轮hooks自动格式化14文件，并发现专辑归并局部变量类型复用及tuple/dict标注问题；仅补标注与变量名后，Ruff、格式化、mypy、detect-secrets四hooks通过。文档审计、staged/worktree差异检查通过。失败与修复后日志保留在`data/import_backups/git-submission-20261020/`，不将旧失败改写成一次全绿，也未扩大到全后端或完整全栈。
