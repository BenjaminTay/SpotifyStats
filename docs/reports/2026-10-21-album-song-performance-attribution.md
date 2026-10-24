# 专辑旗下单曲成绩归属修复

问题：`SS-2026-10-21-001`。基线 `7c4f0660`；本次本地提交保存修复与验证，不含推送、CI或生产部署。

## 根因与范围

旧 `load_track_album_map` 按代表L1/provider来源发行查专辑名，汇总再以歌曲艺人名连接专辑。它没有完整L2成员关系，也没有正式album project ownership。默认L2、动态阈值、全历史、排除合集时，确认72首歌曲遗漏于41个默认项目：代表来源丢失10首、专辑艺人与歌曲艺人键不一致60首、有效署名与旧原始键不一致2首。无合格默认项目的216首不是本问题的缺失项。

逐项接口核验还揭示两个相关读取差异：部分歌曲详情从搜索展示文档取旧项目（如Popular指向42213，而正式统计项目为44454）；详情列表用默认不稳定排序重排同分点数，导致Patient Zero列表#355、正式详情#356。两者都已纳入修复，不以初轮部分字段通过代替最终一致。

## 实现

- 新共享绑定以正式 `apply_canonical_song_keys`、`load_album_project_membership` 连接canonical song和稳定project ID。L2由完整成员决定唯一默认owner；L3使用已发布原生/剩余归属。L1保留原来源容器兼容路径。
- `track_per_album`保留歌曲艺人，另列项目艺人，专辑列表响应携带实际有效演唱者（不回退展示为专辑艺人）；计数、最佳歌曲、冠军周数、旗下歌曲点数/排名按项目ID汇总，不再用演唱者连接专辑。
- 完整/分阶段Billboard、详情、对比和候选列表共用该绑定。详情投影同时发布项目成员、叠加曲目键及逐曲统计owner；详情只读目标投影，源发行名/封面照旧。缺投影或校验失败仍拒绝读取，不回退全库构建。Phone/Desktop专辑链接消费稳定项目ID，保留发行显示名，避免原声带用演唱者错误消歧。
- 列表和对比复用正式 `power_rank`，不对同分歌曲重新分配排名。只有缺排名字段的旧兼容载荷保留稳定排序回退。
- Billboard builder升级为`billboard_persistent_snapshot_v5_project_song_ownership`，详情投影为`music_detail_v2_project_song_ownership`；原播放统计快照、歌曲/艺人分组和人工治理无需重建或改写。

## 发布与数据保护

本地恢复点：忽略目录`data/import_backups/album-performance-20261021/`，包含七库Online Backup、修复前72首清单、发布包、API逐项结果与脚本。副本在`/tmp/spotify-album-performance-20261021/`准备，经过源数据/治理依赖校验后，正式导入48个Billboard发布项及四个详情投影。48项包含四变体、六family和既有2022–2026年榜，使用同次构建共享事实，没有重做年度视觉报告。

服务重启直接复用当前发布，L3和Billboard均未触发启动重建。原始播放/曲目/署名、owner、L1来源、L2/L3分组、项目成员、人工覆盖、艺人身份和相关状态共23表与备份逐行双向EXCEPT一致；96,881条播放保持完整。没有改变代表曲目，没有全局合并冲突艺人，也没有逐曲临时硬编码归属。

## 验证

- 副本四变体：L2动态/固定均1,978首上榜歌曲、1,762条合格绑定；L3动态/固定均1,823首、1,613条绑定。与正式membership逐项一致，缺失/多余/重复均0。额外2026年份筛选一致。
- 默认L2的单曲/专辑/艺人周榜、歌曲摘要/点数、艺人摘要/计数/点数与修复前完整载荷相同。
- Patient Zero归属41476且只出现一次，最高第3、3周、18次上榜播放、582点、正式点数排名356；专辑由18→19首，上榜总周数185、Top5=12、Top10=16、歌曲总点数26,845。
- 最终本地HTTP核验230次全200：见恢复点`live-api-verification.json`及`72-song-verification.md`，逐首比较详情summary/overview、专辑成绩、周榜历史、点数、正式排名和有效演唱署名；41项目列表汇总与overview最佳单曲叠加一致。旧44777入口及expectations/零毫秒天黑黑作为保护案例；真实专辑对比19首/26,845点与7首/2,350点也与详情一致。
- 后端11文件138项定向回归通过；末次列表演唱者字段补充后，15项读取回归及72首接口复验通过。前端两文件22项及正式构建通过；浏览器Phone实测Patient Zero列表/详情#356及Popular→44454→单曲列表的稳定跳转，Desktop由组件回归覆盖。
- 定向回归覆盖成员来源、代表切换、署名差异、L2/L3与合集过滤、详情目标读取、点数同分及完整/分阶段构建。初轮12项旧seed缺revision迁移而失败，补齐私有夹具迁移后通过；首轮详情归属/浏览器同分排名差异及修复过程日志均保留。
- 直接运行当前`.venv`的mypy会因额外pandas类型存根产生跨模块既有错误；项目配置的pre-commit隔离mypy及其余hooks通过，不因此修改无关业务。

本次仅本地事实、定向回归和代表浏览器检查，不声称完整全栈、远端部署或生产验收通过。OOM仍为独立正常使用观察，不启动新压力实验。

## 本地Git提交收口

用户授权仅本地提交。本次范围为31文件：12个后端业务文件、7个后端回归文件、1个详情投影准备脚本、4个前端文件及7份规则/状态/交付文档。按明确路径白名单暂存，原始数据、数据库、发布包、封面、构建产物与逐首核验原始记录均不入Git。

已检查README、AGENTS/CLAUDE与文档地图：产品定位和公共操作约定不变，README及两份一致的工作约定无需修改；元数据规则、变更日志、状态、问题台账、文档地图及报告入口已同步。原72首/41项目的230次HTTP、四变体与年份归属对账、23表守恒和正式构建证据复用，不再次重建真实数据。提交前补跑归属/详情读取22项、两份前端回归22项均通过；文档审计和差异检查通过，并执行项目hooks；结果保留于恢复点下`git-submission/`。

当前工作树复用main，没有新增研发分支或工作树；本次提交不涉及远端、生产部署，也不扩大OOM观察范围。

## GitHub CI补修

用户授权修复原13项失败并提交推送到`codex/local-fixes-20261021`，不合并main或部署。本轮起点为b627c5bf，工作区干净；切换到同SHA的同名跟踪分支开发，原本地main和远端main均不前移。

三笔原修复提交已推送到候选分支。[首轮CI 39462787415](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39462787415)在unit阶段得到3113通过、13失败、2跳过；合同、lint和前端阶段未执行，不能记作全套通过。

- 3项详情测试：mock只接受两个参数，正式归属读取新增snapshot key后抛TypeError；仅更新模拟签名，正式读取逻辑不变。
- 2项封闭/在线只读源测试：旧seed没有当前revision触发器；私有准备先迁移并checkpoint，再封存基线。迁移可以生成已有import-control目录，读取后仍逐字节保持主库且目录条目无新增（包括WAL/SHM）；不在读取期修复或写库。
- 8项预检：运行时builder已为v13，宿主独立脚本仍固定v12。同步到v13，并显式验证旧v12报告和数据库继续被拒绝；四变体、fingerprint、旧聚合、署名policy和孤儿检查保持原门禁，不通过接受旧快照绕过。

原失败所在三个文件共35项本地回归通过。首轮补修验证中，一项断言仍使用旧错误文本、另一项未考虑私有迁移提前创建的控制目录，已纠正断言与准备基线，日志保留；不改写为首轮全绿。文档同步生产预检说明、开发状态、台账及变更日志；没有新增或移动文档，README、AGENTS/CLAUDE和文档地图无需调整。

本轮只改测试、宿主预检常量和文档；不重建96,881条播放或任何正式统计，不改变已核验的72首事实、不运行本地全量套件。完整unit/contract、前端和部署合同检查交由GitHub既有CI完成。最终远端结论以候选分支最新提交SHA的[Actions](https://github.com/BenjaminTay/SpotifyStats/actions?query=branch%3Acodex%2Flocal-fixes-20261021)为准；逐次run结果、日志和SHA写入忽略目录`data/import_backups/album-performance-20261021/ci-repair/`，与旧失败证据分别保留。

### 后续合同阶段修复

补修提交ef4b4633的完整unit阶段已通过，原13项失败解除；[常规CI 39537380427](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39537380427)和[无部署合同CI 39537380421](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39537380421)随后首次执行完整contract，得到510通过、68失败。此前未执行的阶段暴露共同seed准备缺口，不能把unit通过记作完整CI成功。

68项分布在Billboard归属3项、播放不变量1项、对比个人统计64项。共同夹具只复制旧seed并准备L3，未安装当前revision触发器；前4项直接报revision追踪缺失，对比接口将其按既有安全合同转换为503。现仅在`use_seed_db`切换到函数独占副本后执行当前私有迁移，再按原流程发布L3；不修改读取路径、503门禁或全库扫描边界。受影响三文件102项定向通过。

共用夹具影响整个contract套件，因此再执行一次完整本地contract验证原先通过的用例；此前远端未到达的后端lint、前端全量测试和构建也在本地补查。完整contract578项通过，前端805通过/4跳过及正式构建、后端lint通过；完整contract日志与后继远端CI结果均存于`ci-repair/`。后继提交仍只推送原候选分支，不合并main或部署。

## 正式部署与生产核对

用户随后明确授权合并main、按正式流程部署，并核对受影响详情、专辑成绩和榜单。五个源提交bba7cd78、7c4f0660、b627c5bf、ef4b4633、bc6a7a97均以原SHA快进main，没有重写业务。bc6a7a97的候选质量CI 39539698763及无部署合同CI 39539698779成功；main发布流程39547691039的质量、三模式和镜像构建也已通过。

生产原版本f1280ac1，dual/public，schema90、94,760条播放；本机最新schema93、96,881条。生产Online Backup为`backups/spotify-stats-pre-import-release-20261021.db`；下载压缩包SHA256为`172b458c22a020fd64771933b30cf5e6cf6d44f7c5733553cc82575cdf16e39c`。生产全部旧播放ID及时间、时长、来源指纹等原始字段在本机逐项保持，只有import generation随新批次变更；本机增加2,121条。正式同步采用本机已确认治理，生产历史原库完整保留；线上独有的一条AI任务及其事件、与服务器密钥绑定的模型凭据在最新暂存副本中保全，原始三表不为此改写。最新搜索四变体直接复用，详情v2、48份Billboard与四默认排名在副本验证。

升级演练发现独立migration91为两份副本各自生成Analysis epoch，虽然完整源相同，旧预检只传搜索/详情派生表，导致Billboard manifest factual dependency mismatch，排名也无法保留来源revision。首个Release在镜像传输阶段取消，未进入停服或数据库切换。补修仅在既有完整源内容fence、精确聚合/四变体证明内传递Analysis revision向量，并验证两端当前触发器合同；不复制文件身份、不改源事实、不放宽manifest依赖、不冷建生产统计。新增同源迁移及损坏触发器回归，旧源漂移拒绝继续保留；三个文件22项定向回归及真实生产副本48份榜单/四默认排名的重复升级验证通过。

私有日志、失败演练、保护点、暂存包与最终回执位于`data/import_backups/production-delivery-20261021/`；实际部署结果和生产验收在完成后追加。本轮不重开OOM实验或全站性能矩阵。

### a1241fdf发布及最新数据切换

[正式Release 39550345802](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39550345802)、质量CI 39550345872、无部署合同39550345801均成功。运行三镜像revision为a1241fdf8d51930f0a5f37abf1228336de2cccbe，dual/public及外部入口不变。四搜索统计精确复用，没有生产冷建搜索；迁移93、四详情、48榜单及四排名门禁通过。

最新数据在私有暂存副本复用四搜索成品，按未来生产文件身份顺序准备默认分析六范围、社区、音乐档案、治理、艺人排名、2022–2026确定性年度和首页，未调用AI。Online Backup后的治理schema标记在首次暂存准备被拒绝；按已有startup私有tracking安装顺序登记后完成，已准备结果继续复用，未修改人工决定。

切换前再次证明生产31表未漂移，检查暂存库integrity/FK并封存文件身份；切换时保留同一inode及完整原文件。保护点为`backups/spotify-stats-pre-latest-sync-a1241fdf.db`、`spotify-stats-post-latest-sync-a1241fdf.db`和`backups/import-release-20261021/originals-20261021T062142Z/`。生产现有96,881 plays、10,480 tracks、10,964 track_artists，最新UTC2026-10-18T20:07:10Z，署名pending/blocked=0、readiness=ready、待运行任务0。

72首/41项目共230次生产HTTP全部200：详情归属、专辑列表唯一出现、汇总/叠加、点数及正式排名、周榜历史一致；三榜全部6,742歌曲/4,449专辑/4,453艺人周行与已验事实相同。Patient Zero在41476的19首成绩中为582点/排名356，浏览器从列表进入详情核对峰值3、3周、18次上榜播放通过；其发行名仍显示Encore并链接41476。Desktop实际三榜70行的数字位置、垂直中心及70px条全部通过，Phone复用此前同源码414×739验收。浏览器通过SSH映射生产公开网关读取；正式HTTPS能力接口200且SHA一致，工具直开正式域名页面超时的边界保留，不宣称完成HTTPS浏览器矩阵。

### 生产日期边界补修

扩展署名复核先发现测试脚本复用了仅私有可用的`canonical/.../stats`路径，公开面按既有政策404；改用实际公开的`l1/.../stats`同一handler，未放宽路由。随后发现真实独立差异SS-2026-10-21-002：expectations的有界播放统计为22次/19活跃日，而本地及精确摘要为23次/20日，逐日差异只在北京时间2026-10-19。生产私有和公开统计同为22，排除访问面差异。

根因是`_global_period_bounds`用SQLite `localtime`读取原始时间边界。开发机为上海，UTC容器把最新覆盖日当作10月18日，再过滤已按上海重建的逻辑事件，遗漏次日凌晨一次。只将该共用有界详情边界固定为UTC+8，不改原始数据、L2/L3、聚合、快照builder或计次规则。独立UTC进程在旧代码先失败、上海通过；修复后两环境及既有发布排名/零毫秒回归共8项通过。发布前不将扩展署名请求记录为全部通过；既有230项归属及周榜验证不受影响。

### 署名决定保全及增量目标登记

24e2ccf7的[正式Release 39559112357](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39559112357)及[质量CI 39559111954](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39559111954)全部success，实际三容器同SHA且healthy。UTC敏感的独唱/L3、专辑、艺人及全局排名五项生产请求均与本机上海事实相同：expectations恢复23次/20活跃日，L3为30次。SS-2026-10-21-002已发布验证。

137项署名扩展核对到5585时发现旧生产My Heart逐曲排除遗漏，不能把该轮记为全通过。数据同步以本地治理为准时未逐项合并这个生产独有决定；旧完整库仍在原文件和Online Backup内。逐项比较旧生产全部活跃人工覆盖对应曲目的有效署名，仅5585多出My Heart；5531的另一集合变化是已确认蔡健雅/Tanya Chua身份去重，不恢复重复实体。其余缺少旧覆盖行的曲目有效参与者与角色均相同。

通过现有apply覆盖层、原证据及新幂等键恢复5585/7727 remove，本地和生产各新增审计；不直接拼接冲突的override/event ID。生产event94、override64、revision99；Online Backup为`spotify-stats-pre-restore-credit-20261021.db`，原始plays/tracks/track_artists摘要逐项不变。仅缓存重放该目标Spotify证据，自动成员变化0，application pending/blocked均0。

正式重试维护暴露独立SS-2026-10-21-003：增量在提交时复用完整构建所有权fence，但入口未登记新四目标，旧目标被置空后发布被拒绝。错误和有界重试保留，原成品未被覆盖。修复在完整旧成品证明之后调用共用`prepare_music_search_snapshot_set`，随后才计算增量；不放宽源、候选代、revision或并发目标检查。入口回归使用真实SQLite四目标和真实发布fence，覆盖旧服务键保留、正确目标通过及计算中目标替换仍拒绝；旧代码先失败，补修与既有署名维护共16项通过。生产先通过既有私有prepare登记当前目标，再走正式HTTP重试入口恢复；此为本轮维护处置，永久补修另走CI/正式Release。最终状态在完成后追加。

### 最终发布与生产验收

最终代码15d96469b9a97c9497c0deaff59d0024a102ce3c的[质量CI 39565916955](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39565916955)通过；[正式Release 39565916890 attempt3](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39565916890/attempts/3)的质量、full/showcase/dual、镜像及部署全部success。运行三容器均为该SHA且healthy，正式HTTPS能力接口SHA相同，Patient Zero的HTTPS摘要归属41476/582点也通过。dual/public、私有/公开网关及外部入口未改变。

该Release attempt1、attempt2分别在停服前被容量门禁拒绝：可用3383/4148 MiB，要求4456 MiB。首次预留未充分计入重试新增Online Backup和暂存副本占用；补齐预算、仅压缩并校验已关闭Online Backup后可用8706 MiB，再只重跑失败部署任务，复用已验证镜像与CI。未下调容量、源漂移、快照、排名或安全门禁。恢复后全矩阵48份榜单及四排名在独立Online Backup副本准备并绑定此SHA，正式流程再次验证和导入；根权限成品清单首次复制拒绝保留，按精确路径完成复制后校验通过。

最终版本重新完成全部372项API核对：72首/41项目230次、40首三视图/11别名及L2/L3/零值/旧署名控制137次、跨时区歌曲/专辑/艺人及全局排名5次，均200且事实一致。三榜全量6742/4449/4453周行与已验事实相同；曲目在对应项目唯一出现，汇总、叠加、历史、点数及正式排名一致。137项包含恢复后的5585仅Backstreet Boys。生产96881 plays、10480 tracks、10964 track_artists，credit=(99,99,ready)、application pending/blocked=0、readiness=ready，健康safe_to_use=true；239条无曲目音频仍为既有说明，不删除或伪补。

最终浏览器从41476的19首成绩实际点击Patient Zero进入50143，发行名Encore链接41476；峰值3、3周、582点/排名356、18次上榜播放和19次有效播放一致。另已验证独唱23次、合唱独立页5次、5368统一艺人链接但发行署名阿密特、50145零值统计及未入榜空态。Desktop三榜70行数字/播放条证据与Phone同源码证据复用，未扩大为全站或真机矩阵。浏览器用SSH映射正式公开网关，HTTPS能力和摘要另行直接核验；此前工具直开正式域名超时保留。最终截图`production-patient-zero-final.png`、372项回执、失败及重试日志均保存在本报告私有证据目录，不提交数据库、导出或密钥。

数据库实例切换后的2022–2026确定性年度总结与首页按既有入口逐项准备，独立限额进程、网络禁用且主库只读挂载，未调用AI。最终再从实际backend进程环境走cache-only读取，五年均命中；readiness=ready、署名pending/blocked=0、待运行任务0。最终回执为`production-state-closed.json`，先前初始年度未命中/治理任务仍运行的检查点另存保留。

本地源分支codex/local-fixes-20261021已用merge-base证明完全合入main并删除，本地仅main且无新增工作树；远端源分支保留为已整合历史。五个原候选SHA未重写，三次发布补修分别是a1241fdf、24e2ccf7、15d96469。后续交付文档单独提交，不触发业务部署；README、AGENTS/CLAUDE和文档地图无新增入口，保持不变。独立OOM事项仍OPEN/OBSERVING，不以本轮健康状态代替长期正常使用观察。

恢复资料仍在`backups/import-release-20261021/originals-20261021T062142Z/`及各Online Backup。为满足容量，报告上文部分`.db`路径现对应同名`.db.gz`，包括pre-import、pre/post-latest-sync、pre-restore-credit及已关闭pre-release/定时备份；均gzip校验通过，恢复时先解压到独立路径。在线DB、原文件身份恢复目录和旧失败resume未因此压缩或替换。跨库同步的人工治理保全和全过程容量预算已补入[导入规则](../reference/data-import-and-health.md#第二轮导入安全边界)，明确为维护要求，未宣称新增自动合库能力。

## 2026-10-25远端分支清理

按用户本轮清理授权，核对 `codex/local-fixes-20261021` 的远端HEAD为 `bc6a7a97395ff1e2cb5fa191357aaaccee970a4f`，是当前main `65591730607259c9ca8c0fbf5177010516eb1ceb` 的祖先，没有独有提交或打开的PR。使用精确SHA的force-with-lease随同另一条已合入交付分支原子删除；此前本地分支已删除，没有对应工作树需要移除。上文“远端保留”仅描述原交付时状态。

原提交仍在main历史，可按需使用 `git branch codex/local-fixes-20261021 bc6a7a97395ff1e2cb5fa191357aaaccee970a4f` 恢复本地分支；本轮没有执行恢复。既有7个源码恢复引用、2个历史stash及运行数据保持不变，不新增业务修复或生产操作。
