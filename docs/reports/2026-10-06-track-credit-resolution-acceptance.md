# 曲目署名覆盖与标题解析验收

> 问题：SS-2026-10-06-001；最后核验：2026-10-07。
> 完成：S0–S5全部闭环。生产 `2faadc64c73dadbcca0f05b6a53d1a0aebef4611` 已正式发布，两端API、桌面与手机视口的实际署名及跳转通过。S0–S4业务e4929e81默认完整全栈八阶段PASS；S5发布补修另有94项专项、独立53项及真实副本证明，不将旧全栈报告冒称2faadc64全量重跑。

## 真实副本前后对照

生产发布基线 `daf098ca`，一致 Online Backup 为 `spotify-stats-pre-credit-resolution-20261006T143200Z.db`，integrity_check=ok。本地封存副本只读，另建可写验收副本；未用本地较旧正式库代替生产对照。

基线：10,026曲目、1,907艺人、10,496原始署名、94,760播放记录、8,970自动署名、34条人工覆盖，revision37。比较旧 `75c161d8` 共用 resolver 和本次规则，身份映射与原始内容相同。新规则自动调整14个原始曲目；加上既有覆盖层的 My Heart 曲目级纠正，副本共15个曲目变化，有效署名11,789→11,771。只新增1条 remove，revision37→38；同幂等键重跑不新增事件或revision。

| 真实曲目 | 修改前 | 修改后 |
| --- | --- | --- |
| Safe & Sound | Taylor Swift、整体占位、Joy Williams、John Paul White | Taylor Swift、Joy Williams、John Paul White |
| Holidays | Meghan Trainor、完整乐队、Earth、Wind、Fire | Meghan Trainor、Earth, Wind & Fire |
| Fly To You、Get Lucky 两版 | 独立成员及拼接占位同时存在 | 仅独立结构化成员 |
| Mitchell Ayres / Jeff Goldblum 两首组合 | 完整组合及误拆实体同时存在 | 完整组合各一个，不展开成员 |
| Easy | Kacey Musgraves feat. Mark Ronson 占位与独立成员同时存在 | Troye Sivan、Kacey Musgraves、Mark Ronson |
| The Last Time、Rush、Mother I Sober | 带 of 团体说明的占位 | 独立成员，不添加所属团体 |
| Quit Playing Games (With My Heart) | Backstreet Boys、My Heart | Backstreet Boys；正式覆盖层已完成曲目级纠正 |

逐行核对 `plays`、`tracks`、`track_artists`、`artists`、`spotify_auto_track_credits` 完全一致；原有34条人工覆盖逐行一致，完整性检查ok。All Night Parking、Fields.、Machine Gun Kelly / mgk、98° / 98º、魏如萱 / Waa Wei 的有效署名保持；不猜别名，也不以Spotify缺席删除真实补充。

Come Alive 的历史改名、Henri René and / & 名称变体、Super Freaky Girl 含 Maliibu Mitch / Miitch 的完整片段仍无法唯一覆盖，作为例外保留；新导入不再从这些未知字符串创建艺人。不新增全库逐条审核流程。

## 已执行验证

- 解析及实际音频/视频导入、变更集与contract专项133项通过；补成员所属说明后解析/导入/署名组合98项通过。
- 覆盖与人工操作专项18项通过；独立审查定位跨别名撤销时序，修复后两类fixture及79项专项通过。
- 缓存消费者146项、维护/聚合/快照157项、导入变更集25项、生产准备脚本41项通过；无新schema或独立revision系统。
- 前端全量744 passed / 4 skipped，生产构建通过；合法歌曲ID修正仅限旧deployment-profile测试fixture。
- Ruff、Mypy、detect-secrets hooks与文档审计通过。初次unit/contract2696通过、1个报告fixture失败（缺新policy字段），已在相关脚本组修复验证，不将初次运行记为全量Pass。
- 首轮默认全栈预检/质量通过，在真实副本暴露成员所属说明边界后主动停止；最终版本另跑默认完整门禁。
- 第二轮默认全栈预检/质量通过，seed suite 3,321 项通过；发现页面后续修复后，在 integration 阶段主动停止，不记为完整 Pass。
- 桌面实际点击 Joy Williams、手机视口点击 John Paul White 均进入正确详情；Joy Williams 的 8 次播放、0 小时输入曾使日/年趋势报 500，补齐空时长索引名后相关专项 44 项通过，真实副本服务及页面正常。没有改变 featured 时长归属。
- 390×844 手机视口的 Safe & Sound 只显示 Taylor Swift、Joy Williams、John Paul White，Holidays 只显示 Meghan Trainor、完整 Earth, Wind & Fire；点分隔、完整名称链接及无横向溢出已实查。完整乐队点击进入正确艺人页；合作曲排行点击 Sabrina Carpenter 同样正常。此处是浏览器视口，不是物理手机验收。
- `1a9afc90` 镜像运输非部署演练已通过（Actions `37482838306`），现网容器和镜像未变；这不替代最终修复 SHA 的 CI 与发布。
- 手机周榜此前仍用逗号串展示且整行包链接；改为共用 ArtistLinks 数组渲染，独立歌曲/艺人链接，不产生嵌套 anchor。真实 2023-03-17 周榜 Safe & Sound 显示三位艺人和点分隔，实际点击 Joy Williams 进入正确详情；新艺人目标至少44px。补修后前端全量745 passed / 4 skipped，production build通过。
- 发布准备/重基原本只复制搜索6表，漏掉新规则聚合；补同源原子安装5个aggregate表、搜索和发布状态，不复制无关weekly/year-end缓存。源证明覆盖原始/自动/人工/身份与审计，current revision不改。最终专项29项及独立13项/新增1项通过；真实副本的治理38+旧派生目标升级后4精确变体ready，聚合与候选一致，credit state=(38,38,ready)，源事实完全一致。改一行plays后实际rebase拒绝且13张派生表不变；38对37拒绝且目标整库不变。漂移探针另发现旧helper会重复执行有失效副作用的migration36，已限定仅缺schema/登记时迁移，完整schema重跑不清空候选。候选写锁和只读WAL行为已独立核验。
- 第三轮默认全栈预检/质量通过，在发现上述迁移幂等问题后主动停止backend；不计完整Pass。最终SHA重新启动默认完整门禁。

验证服务早期启动遗漏显式Billboard/Analysis sidecar路径，曾在本地 `data/` 写入副本上下文的派生缓存；已停止并用六类明确临时sidecar路径重启。缓存不属于原始事实，本地主库仍保持旧时间戳；不声称所有本地缓存未写。当前验证及后续统计准备全部指向明确副本，生产原始事实表未修改；正式覆盖层变更见下文。

## 最终本地完整门禁

最终 SHA `e4929e81`、干净工作区，run `20261006T154229.183294Z-a862a8fcde5b`，默认完整模式八阶段全部 PASS，总耗时 1,787,021ms（29分47秒）。实际使用生产 Online Backup 的独立验收副本，HTTP 后端和浏览器均连接该副本。

| 阶段 | 结果 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8,586 |
| quality | PASS；前端745 passed / 4 skipped，生产构建与hooks通过 | 76,412 |
| backend | PASS；seed3,335、真实副本integration187 | 696,020 |
| api | PASS；smoke157、boundary113；热态P95无超过500ms门槛 | 255,709 |
| browser-routes | PASS；桌面/手机完整路由及五视口重点矩阵 | 400,304 |
| browser-interactions | PASS；桌面/手机导航、查找和图表交互 | 79,583 |
| browser-inventory | PASS；40路由视口组合、2,006控件、270主要触控目标，无违规 | 47,610 |
| browser-compat | PASS；Chromium、Firefox、Playwright WebKit | 222,658 |

第四轮完整门禁在API阶段因隔离sidecar缺少语言覆盖快照返回503，保持FAIL记录；用现有 `rebuild_governance.py` 仅准备验收副本的语言覆盖后，第五轮默认完整门禁全部通过，没有放宽200断言或修改语言业务逻辑。seed日志保留5项warning，其中一项为既有AI后台线程在测试副本清理时的SQLite I/O warning；integration保留LibreSSL warning，不称零警告。

规范报告位于本机 `/var/folders/9h/n_gtpg9s1mgctkbpbn_hvdzw0000gn/T/spotify-fullstack-verification/20261006T154229.183294Z-a862a8fcde5b/summary.json`，兼容副本 `/tmp/spotify-credit-resolution.oIlhRJ/final-fullstack-v5-summary.json`。这些是本地门禁，不替代生产专项。

## S5 正式维护与发布准备

两次业务提交分别为 `1a9afc90`（共用规则、导入防复发与缓存合同）和 `e4929e81`（真实验收发现的空时长趋势、手机周榜及同源派生安装补修），已推送 main。最终版本独立[质量CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37487386847)、[部署契约CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37487387154)、[镜像运输非部署演练](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37487388404)均success。

首次[正式发布](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37494217721)的质量、三模式和正式镜像构建均success，在准备精确本地ref时失败：维护过程中提前将演练镜像发布为e4929e81正式tag，正式流水线重新构建同一源码的image ID不同，不可变校验正确拒绝覆盖。尚未执行deploy、未停服或替换live DB，现网仍为daf098ca。保留原镜像及失败证据，不删除或覆盖精确tag；通过记录S4完整验收与S5同源准备的文档阶段提交取得新发布SHA，再手动触发既有正式workflow。相对e4929e81仅文档变化，业务代码不变，不再预先推广演练镜像。

- 正式维护前 Online Backup：`/opt/spotify-stats/backups/spotify-stats-pre-credit-maintenance-20261006T154800Z.db`。用既有 `apply_track_credit_override` 仅移除track5585 / artist7727的错误关系，actor=`authorized-maintenance`，幂等键=`credit-policy-v2-my-heart-20261006`。event36、override35、revision37→38，重复调用不新增事件或revision。五张受保护事实表摘要及原有34条覆盖逐行保持，integrity_check=ok。
- 维护后 Online Backup：`/opt/spotify-stats/backups/spotify-stats-post-credit-maintenance-20261006T161300Z.db`，确认revision38、35条覆盖。通过SSH传至本机独立副本准备，不上传数据库到Git或Actions。
- 服务器可用内存不足2,304MiB冷建门槛，因此在本机正式备份副本冷建，不调低门槛、不重启旧Backend。实际采用min_ms30000、music_only=true、周五12:00、动态阈值true、合并间隔5分钟；新aggregate rows为tracks49,618 / track_sources69,153 / albums23,071 / artists16,629，state=(38,38,ready)。
- 搜索四变体全部ready、schema88、当前署名policy；准备耗时32,165.568ms，进程峰值819MiB。封存副本integrity_check=ok、context orphan=0；source marker证明原始、自动、人工、身份及审计事实不变。
- 上传后再次用目标镜像确认与live source一致、4精确变体ready。准备文件原子安装为 `/opt/spotify-stats/backups/music-search-resume.db`；原文件恢复性移至 `music-search-resume-pre-credit-20261006T162300Z.db`，没有删除。正式发布继续走640MiB候选预算和 `--statistics-reuse-only`，不在live DB冷建。

## S5 第二次发布失败与恢复记录

仅文档阶段提交 `3e2c39425fe9b7e5d520935fc5e3e2dc89f0ef27` 相对 e4929e81 无业务、脚本或镜像配置变化。[第二次正式发布](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37497317613)的质量、full/showcase/dual、镜像构建、精确镜像ref及TCR运输均通过；Deploy commit 失败，不登记为已发布。

部署日志（UTC）确认：16:53:59完成 `/opt/spotify-stats/backups/spotify-stats-pre-release-3e2c39425fe9-20261006T165352Z.db` Online Backup；16:54:49续建判定 `reused=true reason=source_equivalent_exact_statistics_resume ready_rows=12`，随后执行 `--statistics-reuse-only` 候选维护与校验；16:56:50仍在运行，17:01:18 SSH `Broken pipe`、exit255。未出现预检完成、停Backend、原子数据库替换或镜像切换日志。ready_rows12是含历史行的续建库存，不代替当前四精确变体ready证明。

故障前实际 `docker compose ps` 仍为 daf098ca 三容器healthy；故障后SSH直连及经既有代理均在banner交换超时，生产SSH网关HTTP亦超时。TCP22握手可达，但不能据此判断应用健康。尚不能确认资源压力、进程残留或网络/主机故障原因，也不能保证容器未在断线后继续执行。没有再次触发部署、强制重启主机、删除恢复点或削弱发布门禁。

北京时间01:05恢复连接：旧daf098ca三容器healthy，private capability也返回该SHA；无残留preflight容器或deploy/prepare/rebuild进程。主机load51.14、swap1985/1987MiB，随后vmstat趋于空闲；磁盘有13GiB可用。kernel记有01:04:29 `Under memory pressure`，未找到OOM kill；不将原因描述为已确认的OOM。

失败续建库经独立Online Backup保存为 `music-search-resume-after-failed-3e2c3942-20261007T010800Z.db`，integrity=ok。限512MiB/禁swap/0.5CPU只读探针确认当前聚合、候选及四精确变体ready；四Year-End投影在断线后也完成，说明没有持续残留重建进程。本机原完整candidate从准备时已含当前四组周榜明细（每组15,363或15,372行）、Year-End meta5/entity550/state1。

必要修复定位：原13表installer没有携带当前fingerprint的周榜明细/Year-End投影，而维护service即使 `statistics_reuse_only=True` 仍无条件ensure年度投影；缺明细时回调 `build_exact_weekly_ledger_for_context`，越过640MiB候选预算进入重计算。补修同源原子安装当前四fingerprint的相关派生表、保留target其他历史键，并让仅复用模式先只读检查年度投影及L3 attribution，缺失直接拒绝，禁止secondary冷建。不弱化四精确变体或源漂移门禁。

真实补修探针 `/tmp/spotify-credit-resolution.oIlhRJ/secondary-install-proof.py` 在正式维护后备份的独立副本验证：Year-End ready0→4，移植当前周榜明细61,470行、年度meta20行、实体年度2,200行及4条投影state；与原完整prepared artifact当前行逐项一致，target其他历史secondary行保持，完整source marker保持、integrity=ok。17表安装后 `--statistics-reuse-only` 为 `revalidated_existing_snapshot_set`，31.522ms、峰值108.047MiB。修改一条原始播放后明确拒绝，17张派生表全部保持。正/负副本保存在本机 `credit-secondary-proof.fy55yx_1`；没有修改正式库。

补修最终94项专项、Ruff/format、两个实现模块Mypy通过；独立差量审查53项通过，无阻挡。审查曾定位L3依赖未ready时只跳过planner却仍可返回ready，现已改为预先拒绝，缺失/failed/旧policy/track revision及album project revision不匹配5种真实state均拒绝且DB不变。冻结后在同一真实正向副本重新执行仅复用：15.769ms、峰值108.234MiB，四变体全部reused、candidate revalidated，DB/WAL大小无变化；这是两次观测，不作为稳定P95。S0–S4默认完整全栈e4929e81的证据范围保持，新发布补修另以专项、真实副本与最终生产验收证明。

## S5 最终生产发布与验收

[正式流水线37503310902](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37503310902)固定2faadc64，质量、full/showcase/dual、镜像构建、精确TCR运输和Deploy全部success。CI后端unit2,280 passed / 2 skipped、contract455 passed / 1 warning，前端745 passed / 4 skipped及构建通过，生产部署契约27项通过；保留既有React key、Node action弃用及runner升级提示，不称零警告。

北京时间2026-10-07 01:43完成切换：backend、web、public-web均healthy，实际OCI revision和两端capability都是2faadc64；Backend 8000仅容器内，Web仍绑定127.0.0.1:3001/3002，外部入口未改变。发布前Online Backup为 `/opt/spotify-stats/backups/spotify-stats-pre-release-2faadc64c73d-20261006T174112Z.db`。预检报告 `music-search-preflight-2faadc64c73d-20261006T174112Z.json` 确认当前四变体ready且全部reused、候选revalidated、当前policy、schema88、聚合artists16,629、orphan0、integrity=ok；仅复用维护50.244ms、峰值95.027MiB、DB/WAL大小变化0。此耗时不包括备份、源核对和安装，不作为整次发布P95。

生产只读完整事实对照再次通过：94,760 plays、10,026 tracks、10,496 track_artists、1,907 artists、8,970自动署名逐行等于S0封存基线；旧34条人工覆盖逐行保持，现35条仅多出授权My Heart remove，幂等事件恰好1条。source marker等于维护后备份，credit state=(38,38,ready)，四精确变体唯一ready、context orphan0、integrity=ok。独立补充、别名冲突及三个歧义例外保持；Mother I Sober生产共用resolver只保留Kendrick Lamar与Beth Gibbons。

私有版和公开版各11个可读歌曲摘要均显示预期独立实体，包含Safe & Sound、Fly To You、Get Lucky两版、Holidays、两首Orchestra、Easy、The Last Time、Rush及With My Heart。Mother I Sober原始ID49158有身份但默认有效播放条件下详情404，故该样本用上述生产只读resolver验证；尝试替代过滤请求30秒超时，不计API通过，也不改变过滤规则。两端Joy Williams均8次/0小时、日/年趋势非空；Records当前ready、全局67,881次、合作曲6,518次/9.6%，前三艺人Taylor1574/Ariana512/Lana304保持。

生产真实浏览器通过SSH隧道读取服务器3001/3002，不使用本地候选页面：1440×1000公开周榜同一2023-03-17周Safe & Sound从4个署名变为3个，2个点分隔，点击Joy Williams进入正确详情；390×844公开周榜3个独立艺人目标均至少44×44px、无嵌套anchor或横向溢出，点击John Paul White成功。私有详情桌面/手机Holidays只显示Meghan和完整Earth, Wind & Fire，完整乐队点击成功；私有手机Safe详情点击Joy成功，8次/0小时趋势与排名正常。合作曲排行桌面私有、手机公开均实际点击Sabrina Carpenter成功，实体间点分隔，手机无溢出。启动补建期间公开排名曾503，后台准备后200，不将该早期错误隐藏或误称署名失败。

公开Records手机实际点击vampire进入整数1493并正常显示；旧1493.0链接规范化保留merge_level与锚点。公开桌面及手机时间控件均8选项可见，2026-10-06日范围请求映射custom起止日期，仍返回snapshot_unavailable/503并保留切换入口，不在公开GET冷建。这两项此前本地修复也已包含在本次生产版本。

前后及手机截图位于ignored `output/playwright/credit-prod-safe-before.png`、`credit-prod-safe-after.png`、`credit-prod-safe-phone.png`、`credit-prod-holidays-phone.png`；已查看截图。此为实际生产浏览器视口验收，不是物理手机或外层HTTPS链路专项，不替代生产LLM/OAuth验收。

S0–S5已完成，[实施计划](../archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)归档。未新增全库逐条审批、未批量删除31个差异条目，身份歧义继续独立维护。
