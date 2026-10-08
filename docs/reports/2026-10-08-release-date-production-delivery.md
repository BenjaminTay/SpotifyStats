# 日期精度与详情空统计生产交付验收

日期：2026-10-08。任务 `SS-2026-09-24-003` / `SS-2026-10-07-001`。用户已明确授权提交、推送、发布及固定92份正式日期补证。

**当前结论：日期精度与详情空统计生产专项通过。** 固定业务版本 `76a4968db67490ae2b37ddf5a7d17175b41217a6` 已发布，schema89及92份日期/78项目补证已完成；私有与公开两视口、2022–2026精确年度缓存、两端30次API及最终事实守恒通过。12:54现场复核三容器healthy、管理连接恢复。本轮不是生产默认完整全栈Pass；维护期间发生的OOM及详情访问后内存增长另由 `SS-2026-10-08-001` 跟踪，尚未代码修复。

## 固定版本与正式流水线

- 发布补修提交 `76a4968`，合并包含日期精度三提交、详情空统计及集成 `7f7185cf`；精确12文件提交，hooks、文档审计及diff检查通过。README/AGENTS/CLAUDE产品与开发约束没有变化。
- [正式流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37721980387) attempt2全部success：unit2347 passed/2 skipped、contract455 passed、前端763 passed/4 skipped及build、生产部署契约28 passed、full/showcase/dual配置门禁、固定SHA镜像构建与digest/身份核验、部署。
- attempt1仅镜像传输阶段SSH连接reset，未切换正式数据/容器；服务器日志当时有MaxStartups限流。保留失败日志，重跑失败部署job使用相同SHA与产物，没有修改SSH配置或放宽门禁。
- 新补修的101项本地专项、真实副本与三模式静态证据见[演练报告](2026-10-08-release-date-production-rehearsal.md)。默认完整全栈仍是[7f7185cf联合验收](2026-10-07-release-date-stats-integration.md)的历史版本与范围，本轮不声称新完整全栈Pass。

## 同源正常发布

发布前再次核对正式来源，上传未补证的schema89/v6续建候选，仅原子替换可丢弃的`backups/music-search-resume.db`；旧续建副本保留。已补证的本地候选没有覆盖正式数据库，数据库未进入Git、镜像或Actions Artifact。

正式预检实际确认`source_equivalent_exact_statistics_resume`、四变体全部精确复用、完整Year-End、当前v6聚合、integrity=ok、搜索context orphan=0。运行门禁确认schema89、四变体、exact/fuzzy/CJK/短CJK。UTC03:42:09部署完成，dual/public模式；三容器实际healthy、Web仅loopback3001/3002、Backend不映射公网，旧版`2faadc64`及恢复镜像保留。外层入口没有变更。

恢复点：`/opt/spotify-stats/backups/spotify-stats-pre-release-76a4968db674-20261008T034015Z.db`；正式预检报告同目录`music-search-preflight-76a4968db674-20261008T034015Z.json`。

## 固定92份正式日期安装

UTC03:24:23通过既有SpotifyProvider重新获取相同92 ID；仅date/precision响应，与演练一致。等正常启动队列完成后，新生产Online Backup及独立候选预览通过：92 accepted，无缺失/冲突，78个非人工项目精度变化，重复应用92 unchanged/项目变化0。

正式操作使用maintenance.lock、既有exclusive publication、显式写连接和BEGIN IMMEDIATE，来源 fence 通过后调用既有有界日期函数；没有放宽副本CLI的正式库保护。UTC03:47:23安装92条实际来源审计，精度分布为：

| 对象 | year | month | day | unknown |
| --- | ---: | ---: | ---: | ---: |
| Spotify Album来源 | 89 | 1 | 2 | 3,142 |
| Album project | 76 | 1 | 1 | 2,862 |

原始日期字符串保持；56张来源表的保护列（排除本次批准更新的precision列及派生管理状态）和四张weekly aggregate逐行双向差集均0，其他精度与日期观测内容另与候选逐列核对。plays94,760、tracks10,026、track_artists10,496、albums4,030、projects2,940保持；有效署名11,771条及摘要保持，署名revision38。既有60,294条FK orphan集合一致，本轮未清理或批准身份。提交后重放无新增审计和项目变更，写后备份integrity=ok。

维护初次调用误用默认只读连接，在BEGIN IMMEDIATE前失败，未写正式日期；更正为显式写连接后安装成功。写后预览/正式source marker的唯一差异为日期观测的实际时间戳；逐列双向核对除observed_at外所有审计字段相同，正式observed_at落在备份后至复核时的UTC区间并原样保留。其他全部marker相同；幂等重放前后完整marker相同。未从全局来源核对中排除审计时间戳，普通发布重基仍拒绝审计漂移。

保护目录`/opt/spotify-stats/backups/date-delivery-76a4968/`保留before-date.db/candidate-date.db/after-date.db、preview/replay/facts/installation及来源响应。before SHA256为`ec64841ea2181ff9081274df36233ddeb60e284a7ee4cfad345ef39ec0f9552d`；after为`4e104c6b0f2ccbc91e97f63f79ff0c97707629725c975e8eba0fb1bd95ecfd73`。

## 消费者验收与连接恢复

生产自己的DB文件身份下：Analysis Stats三个默认范围精确复用；Records三个默认范围重新发布；Archive与Governance必要结果准备完成。首轮年度2022精确缓存确认（约50.7秒）后连接中断，该轮没有完整准备报告；保留既有pandas FutureWarning及失败日志，不将首轮记为成功。

私有真实浏览器1440×1000和390×844覆盖Afterlife、Midnights、收穫、C,XOXO八个实体视口及真实零播放/切回全部时间：无白屏、控制台异常、NaN和详情横向溢出；Afterlife found=false安全空态；Midnights2,567与真实0、恢复通过；收穫按2001年，C,XOXO按来源确认2024-06-28/day展示。Midnights仍是legacy年展示，没有把某个Album响应的day未经关系证据用于项目。

公开浏览器初次等待实体标题超时，随后SSH隧道报server not responding并退出；该次不是Pass。约11:55–12:04，直连/备用代理的SSH banner交换超时；TCP22/80/443可以建立连接，但HTTP/TLS应用层也超时。该时点没有资源日志，未推定原因。

12:43再次SSH连接成功：三个服务仍为76a4968，schema89、观测92、署名revision38及安装后的完整来源marker保持，队列无queued/running；旧维护CLI已经退出，未重复安装日期。内核日志确认12:22发生global OOM，终止uvicorn后后端自动重启；当时uvicorn匿名RSS约2.38GiB，另一Python进程RSS约850MiB。日志能证明内存耗尽和被终止进程，不能单凭时间关联精确定位11:55起全部超时的首个代码调用。

恢复后的公开真实浏览器重复上述四实体×桌面/手机、真实0及切回全部时间：10条结果、零控制台异常、NaN或横向溢出，与私有结果一致。浏览器访问后后端RSS再次约2.3GiB、宿主可用内存约606MB；为避免叠加重型维护，在队列空闲、正式事实保持时，仅于12:48重启本项目backend释放进程缓存。没有重启共享VM、停止其他应用、修改外层入口或回滚日期。

随后在正式DB自身文件身份下，逐年新建受监管子进程准备年度：2022精确复用，2023–2026各自发布并复核。每个子进程RSS上限1280MiB、宿主可用内存下限512MiB、单年墙钟上限240秒，失败只终止所属子进程。实际年度构建约73.6–77.9秒，最高RSS1,288,356KiB（约1.23GiB），五年全部exact cached且每年来源marker前后相同；12:53准备完成，无再次OOM。

两端API随后共30次200：四实体摘要/统计、真实零总量、Analysis Stats/Records、音乐档案及五年年度。两网关surface与固定SHA正确；Analysis快照ready/current，空态nullable、真实0、旧日期降级及confirmed/day符合合同。全部请求前后完整来源marker、后台任务数量/状态、schema89及署名revision38相同，无排队或事实写入。首个公开Afterlife摘要冷请求约17.98秒，其他请求最大约530ms；这是功能和只读验收，不是500ms性能预算Pass。

最终只读核验integrity=ok，61张保护表（含日期观测、四聚合及补充关系表；仅排除既定派生管理状态列）与after-date.db逐列双向差集均0，精度和实际observed_at均保持；60,294条既有FK集合、原始数量及完整来源marker保持。搜索运行门禁schema89、四变体及exact/fuzzy/CJK/短CJK通过。12:54三容器healthy，backend约510MiB、宿主可用约2.4GiB，Web仍只映射loopback，Backend不映射公网。

本范围收口，[日期实施计划](../archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)归档。下一步优先在副本复现并解决 `SS-2026-10-08-001`：区分详情/趋势冷路径、常驻缓存和并行年度维护的内存贡献，限制重型任务叠加并验证冷/热访问资源；本轮运维缓解不算代码修复。物理手机、生产真实LLM、OAuth仍独立待验收。

## 本地执行证据

ignored `output/release-date-production-delivery-20261008/`保留CI两次attempt、预检、日期安装/复核日志、installation、来源响应、维护脚本、两端浏览器结果和截图、公开失败及连接探针。恢复证据包括recovery-state、OOM内核日志、受控backend重启、yearly-bounded-preparation、api-probes（30条）、final-facts（61表）及final-health；保护备份和每年yearly-recovery报告保留于服务器既定保护目录。首轮失败、只读连接误用和审计时间戳核验失败均保留，未覆盖为成功。
