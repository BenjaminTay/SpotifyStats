# 日期精度发布准备与生产验收

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。先记录副本演练与发布准备，再记录76a4968正式发布和有界日期应用。准备不能替代上线；生产专项通过与维护OOM、详情内存增长分别保留。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [日期精度与详情空统计：生产副本演练与发布准备](#日期精度与详情空统计生产副本演练与发布准备)
- [日期精度与详情空统计生产交付验收](#日期精度与详情空统计生产交付验收)

## 日期精度与详情空统计：生产副本演练与发布准备

原记录：`2026-10-08-release-date-production-rehearsal.md`。

日期：2026-10-08。对应 `SS-2026-09-24-003` / `SS-2026-10-07-001`。

业务基线为已本地合入的 `7f7185cf`，文档基线 `91736a5f`。本轮另有发布工具补修，已同步到主工作区，尚未提交、推送或部署；目标发布 SHA 尚未固定。本轮是生产来源副本与发布脚本专项验收，不是新补修版本的默认完整全栈 Pass。前一轮完整全栈保持其[原版本和范围](2026-10-07-release-date-and-empty-stats-acceptance.md#发行日期精度与详情空统计联合集成验收)。

### 新生产来源

生产现场与最终只读复核均为 `2faadc64c73dadbcca0f05b6a53d1a0aebef4611`、schema88、署名 revision38，三容器 healthy，Web 仍只绑定 loopback 3001/3002；未改变外层入口。

新 SQLite Online Backup 于 UTC 2026-10-08 02:37:08 生成，源连接 `mode=ro`，恢复点为 `/opt/spotify-stats/backups/spotify-stats-date-rehearsal-20261008T023708Z.db`。经 SSH 传输后 SHA256 为 `4cf34ba3a1493df5a95beff09d640dca51f345fe5379ec16a7fa237c6ab70db9`，与服务器相同，大小444,588,032 bytes，integrity=ok。封存文件只读，所有迁移、补证及缓存构建都指向独立本地副本。

最终服务器 source marker 与这份 Online Backup 相同，原始/自动/人工/身份/审计和过滤来源未漂移；生产仍没有日期精度列，未迁移或安装日期观测。原始 plays94,760 / tracks10,026 / track_artists10,496 / albums4,030 / projects2,940保持。

### 迁移和有界补证

- 88→89及重复迁移通过；56张受保护表的旧来源列双向EXCEPT均为0。迁移后旧字符串保持，Album/project来源精度全部NULL。
- 从新备份选取全部90个年/月原文，再加Midnights与C,XOXO各一个已缓存Spotify Album ID作day对照，总计92；不发现身份、不获取全库目录。实际来源是本轮既有SpotifyProvider批量响应，仅保留ID/date/precision供重放。
- 默认预览未修改输入副本。92个结果全部accepted，无缺失或冲突；应用只写日期观测/精度及78个非人工项目精度。重复应用92个unchanged、项目变更0，观测仍92行。
- Album来源：89 year / 1 month / 2 day / 3,142 unknown；项目：76 year / 1 month / 1 day / 2,862 unknown。尚未补证的旧日期保持unknown，不能当作确认发行日。
- 日期原文与56张保护表的来源列在全部准备完成后仍守恒；派生状态的active aggregate revision、ready/错误/时间字段单独排除，当前人工revision及事实没有改变。有效署名11,771行，两份副本的规范化摘要相同。
- 四张weekly aggregate逐行双向EXCEPT=0；60,294条既有FK orphan集合完全相同，未清理或批准身份关系。

### 两处发布工具补修

1. `rebase_music_search_preflight.py`原本只补旧搜索schema；遇到生产88、新候选89及预检期间的无关写入，误报source_facts漂移。修复仅升级可丢弃quiescent副本到staged登记的迁移合同，再比较来源；恢复点保持不动，已应用迁移36不重复失效候选。日期观测审计纳入SOURCE_TABLES，审计单独漂移也拒绝。
2. 独立宿主预检器仍写死聚合v4，后端日期合同已升为`billboard_aggregation_v6_legacy_year`，会拒绝正确的新副本。同步当前常量，并让测试夹具消费后端常量；新回归要求接受v6且拒绝v4，不放宽旧结果的资格。

相关101项回归通过，Ruff及所改两个工具的隔离Mypy通过。展开全部导入的Mypy有既有54项/22文件错误；修改前main同样54项，未把隔离检查称为全仓类型检查通过。保留既有LibreSSL和pandas告警。

真实副本复现：旧脚本拒绝；新脚本88→89成功，保留预检期间的非搜索写入，4精确变体ready、orphan0、integrity=ok。另改一条播放以及仅增加日期审计的两个探针均拒绝，17张派生表逐表摘要不变。临时探针DB已清理，原备份与两个用途的候选、日志及机器报告保留。

### 快照与只读消费者

搜索维护前后四套当前fingerprint全部精确复用，未冷建全库搜索统计。旧聚合v4不满足当前发布证明；在明确副本重新构建v6（约7.9秒），四张aggregate的事实内容逐行相同。受影响sidecar使用独立绝对路径，不借用其他文件身份的旧精确缓存。

已准备Analysis Stats/Records各三个默认范围、六类音乐档案、治理结果，以及默认过滤下全部可用2022–2026年度确定性报告。年度报告均能从精确持久缓存读取；未调用LLM。

两种运行面的20次TestClient API读取通过，覆盖四实体摘要、Afterlife found=false/null趋势、Midnights真实2,567次、无播放日真实0、Analysis与档案；之后公开读取四摘要及五年度也通过。公开与私有GET未改变source marker或增加后台任务。日期摘要实际为Afterlife2015、Midnights2022、收穫2001（legacy）；C,XOXO为来源确认2024-06-28/day。当前未补证的Midnights不能宣称已经确认发行日。

本轮未重新启动浏览器、未做物理手机或目标OCI镜像运行验收；此前双视口UI通过保留原范围。full/showcase/dual静态门禁通过；本轮不是生产发布或真实线上业务验收。

### 两个候选的用途与正式执行顺序

- `release-resume.db`：只迁移89和准备v6聚合，日期精度仍NULL、观测0。用新schema88备份实际执行prepare_music_search_resume，结果`source_equivalent_exact_statistics_resume`；然后仅复用维护4/4及新独立预检器的数据库合同全部通过。它与生产迁移后的事实等价，可用于正常发布续建。
- `runtime/spotify_stats.db`：已补证92份日期，用于新消费者和影响验证。它的来源已经变化，不能直接冒充与旧正式库同源的搜索续建文件；本轮没有将它安装到生产。

后续执行顺序：

1. 明确授权后，提交本轮发布补修并固定SHA；推送main将自动部署，须保留正式CI、镜像身份/三模式、健康与联合回滚门禁。
2. 发布前刷新Online Backup和source marker，在副本准备该SHA的v6聚合及精确四变体/Year-End。只允许同源的未补证候选进入续建；漂移则重新准备，禁止上传本轮旧候选强行覆盖。数据库不进入Git、镜像或Actions Artifact。
3. 目标版本发布成功后，再取得新备份，按同一92 ID重放/刷新来源、预览和事实对照；经有界事务安装日期及非人工项目精度，保持恢复点、源核对和maintenance.lock。此正式写库步骤本轮未授权执行。
4. 在生产自身文件身份下显式准备受影响Analysis/Archive/Governance/Yearly结果，不能直接复制本地sidecar冒充ready。完成公开/私有API、桌面与手机视口的空态/0/恢复和日期专项；失败按生产合同联合回滚数据、SHA和mode。

### 证据位置

隔离工作区为 `/Users/benjaminlei/.codex/worktrees/release-date-integration/202605-SpotifyStats`；ignored `output/release-date-production-20261008/` 包含provenance、migration、provider/observations、preview/apply/replay、aggregate/read preparation、rebase-probes、read-facts-probes、annual-headers、release-resume-probe、final-facts-after-annual和production-final-check的JSON及脚本/日志。辅助采集或探针试跑失败另保留，只将最终成功结果计入上述结论。

### 后续授权

本报告完成后，用户于2026-10-08明确授权提交本轮补修、推送发布及固定92份日期的正式补证。以上未提交/未授权表述保留演练结束时点；生产执行结果另行登记。

## 日期精度与详情空统计生产交付验收

原记录：`2026-10-08-release-date-production-delivery.md`。

日期：2026-10-08。任务 `SS-2026-09-24-003` / `SS-2026-10-07-001`。用户已明确授权提交、推送、发布及固定92份正式日期补证。

**当前结论：日期精度与详情空统计生产专项通过。** 固定业务版本 `76a4968db67490ae2b37ddf5a7d17175b41217a6` 已发布，schema89及92份日期/78项目补证已完成；私有与公开两视口、2022–2026精确年度缓存、两端30次API及最终事实守恒通过。12:54现场复核三容器healthy、管理连接恢复。本轮不是生产默认完整全栈Pass；维护期间发生的OOM及详情访问后内存增长另由 `SS-2026-10-08-001` 跟踪，尚未代码修复。

### 固定版本与正式流水线

- 发布补修提交 `76a4968`，合并包含日期精度三提交、详情空统计及集成 `7f7185cf`；精确12文件提交，hooks、文档审计及diff检查通过。README/AGENTS/CLAUDE产品与开发约束没有变化。
- [正式流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37721980387) attempt2全部success：unit2347 passed/2 skipped、contract455 passed、前端763 passed/4 skipped及build、生产部署契约28 passed、full/showcase/dual配置门禁、固定SHA镜像构建与digest/身份核验、部署。
- attempt1仅镜像传输阶段SSH连接reset，未切换正式数据/容器；服务器日志当时有MaxStartups限流。保留失败日志，重跑失败部署job使用相同SHA与产物，没有修改SSH配置或放宽门禁。
- 新补修的101项本地专项、真实副本与三模式静态证据见[演练报告](#日期精度与详情空统计生产副本演练与发布准备)。默认完整全栈仍是[7f7185cf联合验收](2026-10-07-release-date-and-empty-stats-acceptance.md#发行日期精度与详情空统计联合集成验收)的历史版本与范围，本轮不声称新完整全栈Pass。

### 同源正常发布

发布前再次核对正式来源，上传未补证的schema89/v6续建候选，仅原子替换可丢弃的`backups/music-search-resume.db`；旧续建副本保留。已补证的本地候选没有覆盖正式数据库，数据库未进入Git、镜像或Actions Artifact。

正式预检实际确认`source_equivalent_exact_statistics_resume`、四变体全部精确复用、完整Year-End、当前v6聚合、integrity=ok、搜索context orphan=0。运行门禁确认schema89、四变体、exact/fuzzy/CJK/短CJK。UTC03:42:09部署完成，dual/public模式；三容器实际healthy、Web仅loopback3001/3002、Backend不映射公网，旧版`2faadc64`及恢复镜像保留。外层入口没有变更。

恢复点：`/opt/spotify-stats/backups/spotify-stats-pre-release-76a4968db674-20261008T034015Z.db`；正式预检报告同目录`music-search-preflight-76a4968db674-20261008T034015Z.json`。

### 固定92份正式日期安装

UTC03:24:23通过既有SpotifyProvider重新获取相同92 ID；仅date/precision响应，与演练一致。等正常启动队列完成后，新生产Online Backup及独立候选预览通过：92 accepted，无缺失/冲突，78个非人工项目精度变化，重复应用92 unchanged/项目变化0。

正式操作使用maintenance.lock、既有exclusive publication、显式写连接和BEGIN IMMEDIATE，来源 fence 通过后调用既有有界日期函数；没有放宽副本CLI的正式库保护。UTC03:47:23安装92条实际来源审计，精度分布为：

| 对象 | year | month | day | unknown |
| --- | ---: | ---: | ---: | ---: |
| Spotify Album来源 | 89 | 1 | 2 | 3,142 |
| Album project | 76 | 1 | 1 | 2,862 |

原始日期字符串保持；56张来源表的保护列（排除本次批准更新的precision列及派生管理状态）和四张weekly aggregate逐行双向差集均0，其他精度与日期观测内容另与候选逐列核对。plays94,760、tracks10,026、track_artists10,496、albums4,030、projects2,940保持；有效署名11,771条及摘要保持，署名revision38。既有60,294条FK orphan集合一致，本轮未清理或批准身份。提交后重放无新增审计和项目变更，写后备份integrity=ok。

维护初次调用误用默认只读连接，在BEGIN IMMEDIATE前失败，未写正式日期；更正为显式写连接后安装成功。写后预览/正式source marker的唯一差异为日期观测的实际时间戳；逐列双向核对除observed_at外所有审计字段相同，正式observed_at落在备份后至复核时的UTC区间并原样保留。其他全部marker相同；幂等重放前后完整marker相同。未从全局来源核对中排除审计时间戳，普通发布重基仍拒绝审计漂移。

保护目录`/opt/spotify-stats/backups/date-delivery-76a4968/`保留before-date.db/candidate-date.db/after-date.db、preview/replay/facts/installation及来源响应。before SHA256为`ec64841ea2181ff9081274df36233ddeb60e284a7ee4cfad345ef39ec0f9552d`；after为`4e104c6b0f2ccbc91e97f63f79ff0c97707629725c975e8eba0fb1bd95ecfd73`。

### 消费者验收与连接恢复

生产自己的DB文件身份下：Analysis Stats三个默认范围精确复用；Records三个默认范围重新发布；Archive与Governance必要结果准备完成。首轮年度2022精确缓存确认（约50.7秒）后连接中断，该轮没有完整准备报告；保留既有pandas FutureWarning及失败日志，不将首轮记为成功。

私有真实浏览器1440×1000和390×844覆盖Afterlife、Midnights、收穫、C,XOXO八个实体视口及真实零播放/切回全部时间：无白屏、控制台异常、NaN和详情横向溢出；Afterlife found=false安全空态；Midnights2,567与真实0、恢复通过；收穫按2001年，C,XOXO按来源确认2024-06-28/day展示。Midnights仍是legacy年展示，没有把某个Album响应的day未经关系证据用于项目。

公开浏览器初次等待实体标题超时，随后SSH隧道报server not responding并退出；该次不是Pass。约11:55–12:04，直连/备用代理的SSH banner交换超时；TCP22/80/443可以建立连接，但HTTP/TLS应用层也超时。该时点没有资源日志，未推定原因。

12:43再次SSH连接成功：三个服务仍为76a4968，schema89、观测92、署名revision38及安装后的完整来源marker保持，队列无queued/running；旧维护CLI已经退出，未重复安装日期。内核日志确认12:22发生global OOM，终止uvicorn后后端自动重启；当时uvicorn匿名RSS约2.38GiB，另一Python进程RSS约850MiB。日志能证明内存耗尽和被终止进程，不能单凭时间关联精确定位11:55起全部超时的首个代码调用。

恢复后的公开真实浏览器重复上述四实体×桌面/手机、真实0及切回全部时间：10条结果、零控制台异常、NaN或横向溢出，与私有结果一致。浏览器访问后后端RSS再次约2.3GiB、宿主可用内存约606MB；为避免叠加重型维护，在队列空闲、正式事实保持时，仅于12:48重启本项目backend释放进程缓存。没有重启共享VM、停止其他应用、修改外层入口或回滚日期。

随后在正式DB自身文件身份下，逐年新建受监管子进程准备年度：2022精确复用，2023–2026各自发布并复核。每个子进程RSS上限1280MiB、宿主可用内存下限512MiB、单年墙钟上限240秒，失败只终止所属子进程。实际年度构建约73.6–77.9秒，最高RSS1,288,356KiB（约1.23GiB），五年全部exact cached且每年来源marker前后相同；12:53准备完成，无再次OOM。

两端API随后共30次200：四实体摘要/统计、真实零总量、Analysis Stats/Records、音乐档案及五年年度。两网关surface与固定SHA正确；Analysis快照ready/current，空态nullable、真实0、旧日期降级及confirmed/day符合合同。全部请求前后完整来源marker、后台任务数量/状态、schema89及署名revision38相同，无排队或事实写入。首个公开Afterlife摘要冷请求约17.98秒，其他请求最大约530ms；这是功能和只读验收，不是500ms性能预算Pass。

最终只读核验integrity=ok，61张保护表（含日期观测、四聚合及补充关系表；仅排除既定派生管理状态列）与after-date.db逐列双向差集均0，精度和实际observed_at均保持；60,294条既有FK集合、原始数量及完整来源marker保持。搜索运行门禁schema89、四变体及exact/fuzzy/CJK/短CJK通过。12:54三容器healthy，backend约510MiB、宿主可用约2.4GiB，Web仍只映射loopback，Backend不映射公网。

本范围收口，[日期实施计划](../archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)归档。下一步优先在副本复现并解决 `SS-2026-10-08-001`：区分详情/趋势冷路径、常驻缓存和并行年度维护的内存贡献，限制重型任务叠加并验证冷/热访问资源；本轮运维缓解不算代码修复。物理手机、生产真实LLM、OAuth仍独立待验收。

### 本地执行证据

ignored `output/release-date-production-delivery-20261008/`保留CI两次attempt、预检、日期安装/复核日志、installation、来源响应、维护脚本、两端浏览器结果和截图、公开失败及连接探针。恢复证据包括recovery-state、OOM内核日志、受控backend重启、yearly-bounded-preparation、api-probes（30条）、final-facts（61表）及final-health；保护备份和每年yearly-recovery报告保留于服务器既定保护目录。首轮失败、只读连接误用和审计时间戳核验失败均保留，未覆盖为成功。
