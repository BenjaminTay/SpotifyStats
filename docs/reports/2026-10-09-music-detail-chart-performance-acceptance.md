# 音乐详情榜单成绩性能验收

日期：2026-10-09。事项：`SS-2026-10-09-001`。当前结论：**Partial；业务本地 S4 已通过，c58775f0 已正式部署。独立生产自然首轮完整 90 项只有 39 项通过、51 项性能失败；116 项功能对账及完整读取守恒通过。冷页面性能和高驻留仍需修复，本项未收口**。

本项基线为 `d5ba3094`，在独立工作树和 94,760 条播放的 Online Backup 副本执行。原始播放、身份、署名、人工覆盖和治理关系不作为本项写入目标；生产 OOM 和对决个人统计分别验收。

## 实现与事实边界

- 默认三类 summary/overview，以及专辑 project，读取 exact-ready 发布事实，在同一 SQLite 读事务中验证过滤指纹、源 revision、目标 context/ledger/source 校验。缺失、损坏、漂移返回 `503 snapshot_unavailable`；不调用完整时间线、个人统计、完整 Billboard，也不排队或写库。
- schema90 增加源双轨事实和目标成员/关联投影，接入完整、共享、增量和署名发布链。搜索 builder 仍为 v12；现行公开组合是 L2/L3 × 动态/固定四组合。旧 full/Agent/list 保留独立兼容路径。
- 前端消费 AbortSignal，页签退出取消观察者请求；失败退出 Skeleton，提供重试，刷新保留旧结果。专辑名称路由先取得稳定身份，再复用 Query；归属解释在可见区域请求。Phone 年榜仅挂载卡片，主触控目标至少 44px。
- 版本组成员深链用目标范围治理 SQL 归一到同合并级别的榜单代表：L2 recording 不扩 composition parent，L3 扩展父组及其子组。

## 独立规则核验

严格旧基线对账的差异保留，不能把旧错误当作新实现的期望值。

1. L3 来源 loader 遗漏 `release_date_precision`，缺列 fallback 又把 None 转为 NaN，导致旧 full 计算放行发行前播放。两处已修复；四组合从同一源事实逐周独立重算与既有 v12 ledger 一致。Midnights 的 L3 榜周由旧 full 的 87 周纠正为 ledger 的 88 周。全局专辑冠军另有六周真实事实纠正：2023-06-30/08-11 为 SOUR，2024-06-14 为 Speak Now，2024-11-22 为 Melodrama，2026-04-17 为 Kiss All The Time. Disco, Occasionally.，2026-05-22 为 Piano Man。动态/固定分别取这六周的 2,171 行逻辑源事实独立重算，冠军实体、次数和独立时长与 v12 ledger 完全相等；模拟缺精度/NaN 放行，又精确重现六个旧冠军，且全部早于对应项目发行截止日。既有搜索 ledger 正确，无需冷建搜索。Billboard 持久缓存独立升级为 v4，拒用旧计算成品。
2. 固定阈值旧项目详情仅累加计次事件的 ms，忽略独立收听时长轨。Midnights L2 精确差 3,135,708ms，L3 差 3,299,332ms；新投影与独立源双轨事实一致。
3. 旧 L2 版本说明错误扩展 composition parent，并用版本总数覆盖有效次数。cardigan 应为 recording 组 132 次，旧 full 显示 176 次；新事实按 R6/R31 的合并层级处理。

私人逐周、逐成员和源守恒证据在 ignored `output/music-detail-chart-acceptance/`，不提交真实数据。

## 108a5f41 阶段后端功能与读取边界

固定集成 SHA 为 `108a5f41`（专项业务 `708a67f` 与上游 `acdd` 合并）。基线继续使用干净 `d5ba3094` 源码及独立事实副本；旧严格差异和失败诊断均保留。

- 最终 116 个服务响应由主样本 52、补充状态样本 24、真实版本组样本 40 组成，四组合全部零请求错误。positive 未入榜、零有效播放、未知实体和 featured 署名状态分别核验；ready publication 的 `not_charted` / `found=false` 与 `snapshot_unavailable` 明确区分。主样本 overview 年榜全部 ready，并与基线逐字段相等。
- 40 个版本身份响应覆盖 recording 无 parent、recording 子组、composition parent，以及 primary/非 primary L1。输入 L1 ID 保留；同组身份的 canonical 名、榜单和年榜字段一致。版本成员逐项次数/时长与独立 raw 双轨审计及最终 aux SQL 相等，L2 cardigan 为 132 次、L3 composition 为 176 次；版本列表按逻辑次数降序、L1 ID 排序，未删除可见版本字段。
- 严格 UI 差异主样本 572 项、补充样本 0 项、版本样本 140 项，保留原逐字段对账。主样本中 54 项属于固定阈值项目双轨时长纠正，28 项属于 L3 榜单/叠加排名的发行资格纠正，490 项是六周全局冠军事实变化及原排序造成的数组位置传播。版本差异对应旧非 primary 榜单身份失配和 L2 错扩 composition parent；最终 canonical 名差异已消除。各样本与独立证明的对应关系记录在 `strict-diff-rule-map-108a5f41.json`，不能把 490 个数组字段差异写成 490 个冠军事实变化。
- 真 HTTP 合同证明：仅 search+aux exact-ready、Billboard 侧库完全不存在时，三类 summary/overview 及专辑名称/稳定 ID 的 project 共 10 个 GET 返回 200，提供自身 snapshot headers，禁止旧 full gate/重型计算且无写；旧 full/list/release 三个 GET 仍明确 503。修订后的四文件合同专项 21 passed，旧 fixture 缺发布导致的失败保留为诊断。
- 五个独占 Online Backup 故障副本分别模拟缺 aux、context 篡改、缺 ledger、旧 projection 版本及 revision 漂移。三类 summary/overview 共 30 项全部明确 `503 snapshot_unavailable`；完整时间线/个人统计/Billboard/年榜等重型 spy 零调用，五个副本请求前后整个主库 SHA 均相同。
- 基线与投影副本的 38 表守恒审计中，37 表行数和 SHA 相同；唯一不同的 `governance_source_revisions` 是 schema90 安装 revision tracking 后的 epoch/新增派生域元数据（93→96 行），不描述为 38 表全部相等。最终 HTTP 与功能请求前后，两侧目录的全部 15 个 `.db` 文件 SHA 完全相同，覆盖主库源事实、发布/队列和侧库成品；验证期间未访问或修改正式数据库。

上述私人证据分别保存在 `functional-summary-108a5f41.json`、三份 `*-differences-108a5f41.json`、`projection-fact-audit.json`、`projection-global-no1-audit.json`、`version-group-independent-weight-audit-final.json`、`faults-final/summary.json`、`extended-source-conservation.json` 和 `contract-boundary-ready-final.log`。

## 108a5f41 阶段后端资源门槛

同一冻结样本、固定 SHA 与独占 CPU 窗口，顺序运行 service、完整应用内 HTTP 路由及流式 cohort。HTTP 使用无 lifespan 的 TestClient，包含 public middleware、router gate、响应校验与序列化；不包含真实浏览器、网络/TLS 或启动预热。每次冷样本为独立进程，热调用为同一进程第二次请求，RSS 以 2ms 采样，响应立即落盘，不累积 payload 污染驻留。

| 最终采样 | 冷请求 | 热请求 | 冷请求峰值 RSS 增量 | 判定 |
| --- | --- | --- | --- | --- |
| 三类各三次 service | 23.86–158.43ms | 15.75–63.81ms | 4.02–13.89MiB | 通过 |
| 三类各三次完整 HTTP | 27.68–127.48ms | 22.36–42.79ms | 9.38–16.84MiB | 通过 |

门槛仍为冷请求 ≤500ms、热请求 ≤100ms、冷请求峰值增量 ≤64MiB，两套 `gates.json` 均无违反项。

正式 HTTP 连续 cohort 为每类 36 实体、共 108 实体 × 三轮 = 324 请求，每类超过 LRU32；两侧均零错误。基线使用原副本精确 ready 的 v3 Billboard 成品，候选使用最终发布事实，不修改基线规则或原始事实。

| 资源 | 基线 HTTP | 候选 HTTP | 下降 |
| --- | --- | --- | --- |
| 324 请求峰值 RSS | 1059.36MiB | 197.67MiB | 81.34% |
| 最后一轮末驻留 RSS | 804.84MiB | 179.66MiB | 77.68% |

候选三轮末驻留为 178.20 / 179.31 / 179.66MiB，形成平台，未观察到随请求数线性增长。正式证据为 `resource-summary-108a5f41.json`、`candidate-service-cold-108a5f41/`、`candidate-http-cold-sequential-108a5f41/`、`candidate-http-cohort-sequential-108a5f41.json`、`baseline-http-cohort-108a5f41.json`。

## 108a5f41 历史诊断与阶段证据

- 初版 service 冷 18–91ms、热 16–33ms、增量 9.1–13.8MiB，以及初版流式峰值 810.5→116.7MiB、末驻留 630.9→108.0MiB，仅保留为实现过程诊断，不替代 `108a5f41` 最终 HTTP 证据。最初 collector 留存 payload 的无效资源诊断，以及最终首套 HTTP run 与 cohort 发起相近的诊断目录均保留；正式结论使用明确顺序的 `sequential` 目录。
- 三浏览器控制场景 36/36 通过：暂扣排名、请求取消、失败/重试、旧帧连续、来源返回、归属可见触发、Phone 互斥 DOM/44px/无溢出。控制场景阻止 Service Worker，不能用作自然性能证据；旧探针兼容失败、Firefox 被 SW 绕过注入的诊断均保留。
- `108a5f41` 分支的 CI 与 No Deploy Production Contract 均完成，后端 unit/contract、前端、文档和部署合同 job 通过；这不代替本地默认完整全栈或生产验收。
- 版本说明功能首轮 20/24 通过；WebKit 的原生 SIGSEGV 栈落在探针的 accessibilitySnapshot，原 crash 和首轮保留。仅将探针改为真实 DOM role/name/可见 bbox 后，三引擎版本功能 24/24 通过，产品代码没有用此修正回避问题。
- 自然矩阵首轮完整 90 项，86 项达到冻结门槛；4 项超时保留：Chromium360 艺人点击核心 1218.5ms、Chromium1280 L2fixed 专辑深链核心 2099.8ms、L3dynamic 艺人点击核心 1440.2ms/完整 1555.4ms、L3fixed 艺人点击核心 1149ms。无功能、布局或非 GET 失败。第一项早于其他全栈任务；其余三项与同机另一任务全栈重叠，时间关联来自 PNG mtime 与 case duration 的近似还原，不能伪称原始 wallclock 埋点。
- 隔离并发诊断确认逐成员校验造成 485 次投影检查、485 次 payload SELECT；完整请求共 1054 次 execute 与 1046 次 fetch。排名为约 1.7–1.9 秒 CPU 任务，800ms 偏移时 overview 约 60ms 线程 CPU/291ms wall，主要等待在 SQLite 行读取；未复现原 883ms，不用诊断热结果覆盖首轮。已补按目标批量 JSON 读取及摘要校验，排名区域实际可见才请求；新固定实现尚需独立自然矩阵验收。
- 批量化前后隔离诊断，完整 overview JSON SHA 相等，8 个 owned 数据库 SHA 守恒；SQLite execute/fetch 从 1054/1046 降为 98/90，合计 2100→188（减少 91.05%），projection_available 485→7。400/800/1200ms 并发偏移 service 从 154.84/290.72/67.77ms 降为 109.60/244.77/53.85ms；诊断仍有排名计算/环境竞争，不替代正式自然门槛。真实 Phone360/390 排名区域分别位于 y840.71/855.48，屏高800/844，首 GET 为0、滚入为1；Desktop1280 区域 y571.38，屏高900，可见即 GET1。
- 自动发布失败回退已补同文件系统原 inode 保护、旧镜像只读 exact gate 与侧库恢复；本地 31 项回归证明 schema89/原库字节 SHA/inode/旧侧库共同恢复及失败保留。发布成功后人工 `rollback.sh` 回旧 v3 仍未验证，不与自动失败回退混称通过。
- 最新前端完整测试 796 passed / 4 skipped，年榜互斥回归、构建通过。新批量读取专项 30 passed；新增可见性回归、后端完整及默认八阶段完整全栈仍在进行。

## 83bc5567 正式复验与稳定身份补修

- 新独立进程三类各三次 service 冷 17.74–57.39ms、热 16.14–35.11ms、RSS 增量 7.55–13.89MiB；完整 HTTP 冷 27.46–114.48ms、热 21.52–79.07ms、增量 6.41–16.92MiB，均达到原 500/100ms 与 64MiB 门槛。候选 324 请求零错误，峰值 198.27MiB、末驻留 178.19MiB，对冻结 d5ba 基线下降 81.28%/77.86%；轮末 176.45/177.77/178.19MiB。证据为 `resource-summary-83bc5567.json`。
- 116 服务响应相对 108a 候选零逐字段差异，真实 HTTP 108 项 200 与 8 项预期未知 404；30 个故障请求全部明确 503、重型 spy 零调用；7 库完整 SHA 和 57 表守恒。独立规则证明及旧严格差异继续保留，未重复无变化的基线构建。证据为 `functional-summary-83bc5567.json`、`final-state-after-83bc5567.json`。
- 自然首次完整矩阵 **89/90，仍未通过**：Chromium 41/42、Firefox/WebKit 各 24/24。唯一失败是 Chromium1280 的 L2 fixed 专辑点击：核心 1209ms >1000ms，全部可见 1300.3ms <1500ms。该视口排名区域可见，请求必须启动；overview 1172.64ms，其中 service 317.66ms，服务计时之外 854.98ms。保留 `browser-natural-83bc5567-first/` 的首次失败和 trace，不把受控热诊断当自然 Pass。
- 后续定位发现专辑稳定 ID 已查目标 1 行，却再次经名称解析读取全部 3181 行项目/别名；共享响应入口现直接复用已验证身份。L3 非首选 release 的必要兼容检查保持，名称/别名入口合同保持。29 项针对性测试通过；三个独立 HTTP 对照的完整响应 SHA 和 7 库 SHA 相同。800ms 并发偏移诊断 HTTP 493.96→354.68ms，ASGI 服务计时外 178.05→58.38ms，不能据此认定自然验收通过。证据为 `album-id-route-diagnosis/before-after-summary.json`。
- `83bc5567` 正式 CI 失败：2555 passed、2 skipped，唯一失败是旧部署测试仍要求被取代的 `replace_live_database` 回退。测试现检查原 inode、两侧库、旧 exact gate 与激活顺序，43 项集成回归通过；新固定 SHA 的 CI 待重新验证。原失败 log 留存，108a 的历史绿 CI 不替代新结果。
- 可见性/取消/错误等三引擎控制场景 45/45 通过（SW block，仅功能）；Phone 排名滚入请求一次、重入复用，Desktop 可见即请求。业务前端与 83 相同，稳定 ID 补修后仍需新固定版本的自然首次矩阵及默认完整八阶段全栈。

## 47147879 本地验收与首次发布

- 稳定 ID 补修的业务版本为 `fd549b1a`；集成上游对决日计次优化后的固定版本为 `47147879287ca8e79cae257bc254b57402380865`。三类 service/投影及前端业务与此前版本一致；对变更的实际 ID HTTP 路径重新执行九个独立进程冷/热样本和324请求，不重复未变化的旧基线重建。冷26.97–53.48ms、热21.93–86.58ms、RSS增量10.44–15.48MiB，原500/100ms、64MiB门槛均通过。
- 实际 ID cohort 零错误，峰值196.94MiB、末驻留179.05MiB，对冻结d5ba基线下降81.41%/77.75%；三轮末178.06/178.53/179.05MiB。基线专辑使用名称路由，候选使用相同实体的稳定项目ID；216个歌曲/艺人响应全文相同，108个专辑响应仅四个明确请求身份字段不同，其他字段完全相同。7个库完整SHA守恒。证据为 `resource-summary-fd549b1a.json`、`http-id-payload-equivalence-fd549b1a.json`、`final-state-after-fd549b1a.json`。
- 固定471版本的自然首次矩阵90/90通过：Chromium42/42、Firefox24/24、WebKit24/24，PWA正常开启、fresh context，不单项热重跑。最慢点击核心956.1ms、全部可见1015.0ms；直接深链核心1502.2ms、shell后全部可见1087.5ms，满足原1000/2000/1500ms合同。无页面错误、非GET或功能失败，12个屏外排名检查均符合按可见性请求。旧108a的86/90及83的89/90全留。证据为 `browser-natural-47147879-first/`。
- 471版本默认完整八阶段同轮 **PASS**，run `20261009T054156.622796Z-0daf913b317e`，干净源码、正常lifespan、真实Online Backup数据，耗时1,530,093ms（25分30.093秒）。八阶段全部PASS，optional未运行；前端803 passed/4 skipped、后端3789 passed/2 skipped、真实集成186 passed/1 skipped（Genius客户端缺失）。本轮不证明独立25分钟门禁事项已关闭。
- 全栈launcher首个无效dataset参数在阶段启动前失败；首个完整尝试继承性能环境的禁外部封面参数，导致正常CDN307合同变404。修正仅限ignored launcher的普通正确性子进程环境，未改业务、跳过测试或放宽合同；从默认完整八阶段重新执行并通过。两份失败log/summary保留，正式证据为 `fullstack-47147879-summary.json`。
- fd分支CI `37888288004`、471分支CI `37888523263` 与471主线CI `37892112247` 均success。主线fast-forward发布471，正式release `37892112260` 的quality、full/showcase/dual三模式及镜像构建通过，安装失败。失败发生在正式数据库替换前：详情manifest validate/import成功，随后只读verify报 `sqlite3.OperationalError: unable to open database file`；stage清理另报root-owned `import_control` 权限错误。失败日志保留为 `production-first-47147879/release-attempt1-failed.log`。
- 失败后SSH独立核验：旧9dd镜像的backend、private/public web三个容器healthy，dual边界保持，旧Billboard只读exact gate为true。这证明服务恢复及旧成品可读，不代表新版本发布、生产性能、原inode联合回退演练或人工rollback已通过。正在定位stage SQLite及临时控制文件权限，未发本项生产详情/排名预暖请求。

## 只读stage与临时权限补修

首次失败已真实复现：协调写连接将主文件设为WAL，最后连接闭库后WAL/SHM消失但主文件仍保留WAL标志；普通连接在只读目录首个SELECT尝试创建辅助文件，报unable to open database file。root容器另创建700的import_control，宿主ubuntu无法清理。

补修限定维护CLI及部署helper：stage显式closed-source、拒绝任何WAL、mode=ro/immutable/query_only与读事务、前后文件身份检查；live普通只读读取仍可见已提交WAL。aux/BB stage容器使用宿主UID/GID，rank/checkpoint/Backend用户及现有正式文件权限保持。目标HTTP、统计服务、数据库核心及前端源码与已通过S4的471完全一致，不将471的全栈结果写成新部署SHA曾运行同轮。

92项针对性SQLite/CLI/部署回归、ruff、Shell语法及diff检查通过；真实471镜像overlay的owned tiny Docker十阶段复现与补修验证通过：旧root控制目录700与只读SELECT失败，修后host-owned导入/闭库读取/清理成功，root644旧BB复制后的stage写入正确；empty WAL及篡改成绩仍拒绝。只读操作前后主库/BB完整SHA相同，无WAL/SHM产生。tiny来源上下文有fixture adapter，仅证明文件系统边界，不能代替生产四变体及48 targets业务对账。私人证据为 `deploy-permission-fixture/remote-result-final.json`（whole SHA `21b357481768d264f219b622c7e029eecdc2ad06352b5500c7644c086a2687a9`）；原失败stage保留。

首次发布前后旧schema89的57个实际保护表、37原源、schema/epochs/fence及文件身份全部相同；旧capture未包含队列/全部发布表，不能声称全窗口守恒。扩展v2探针已用11项真实tiny SQLite验证并取得新生产before89：五队列表、搜索六表/FTS、全部aux及六侧库全部发布表按read transaction捕获；下一次schema90正式窗口需before/after v2严格比较。采样工具旧9dd纯proc传输诊断验证PID识别、0600输出及只停止collector，不发详情GET，也不作为新版本性能证据。

## 6430 / cb8 后续本地证据与真实联合恢复

业务集成6430d4de默认完整八阶段实际通过，run `20261009T075213.655349Z-147218655db1`，耗时1,532,685ms；其全新正常lifespan自然90/90通过，点击核心最大962.9ms、全部1047.3ms，深链核心1295.6ms、shell后全部525.5ms，严格v2读窗口守恒。部署补修cb8d05b1另跑默认完整八阶段，run `20261009T094929.575812Z-954fd3885f46`，1,488,756ms，八必需阶段全部PASS，后端3840 passed/2 skipped、真实集成186/1 skipped。两轮真实summary SHA分别 `34a619e4204c3696feb64f2eeb5b07e30eab69f5d1173f57fb56653e10c6621b`、`7e46849cdaae887c7b32a4d9edeb8130586f634da20c8c5b61c2a31a31e2831a`。这些是原版本实际本地证据，不改标c587曾运行新的本地full8。

唯一必要完整owned自动联合恢复采用实际9dd/6430镜像与后来固定到cb8的同哈希host helpers，16个实际阶段均exit0：恢复原主库inode/schema/完整字节、完整Analysis及Billboard备份字节与原semantic rows，旧rank4/BB48 exact与三个旧镜像HTTP保持，只读源守恒。报告 `owned-joint-automatic-restore-6430-report.json` SHA `848837e6e9a8c61524346c11cc5b4000b908d29ada26626893b5f602e8d59a79`，owned工作数据成功释放。原SSH传输收尾255单列，不称整个SSH wrapper0；不称c587镜像的完整恢复或真实生产回滚，也不代替发布成功后人工rollback旧v3验证。

6430及cb8各次实际发布失败、两轮及后续精确清理、三库WAL准备最小补修和新清单九步证据，见[联合发布报告](2026-10-08-versus-personal-statistics-performance-acceptance.md)第21节。历史失败和文件权限诊断保留；正常发布没有冷建搜索、详情或Billboard。

## c58775f0 生产独立首轮（性能失败完整保留）

固定生产SHA `c58775f0df53ec05d2524a06b84f3b9945b6d024`。CI37929372415、Release37929372279（实际Deploy113822444726）及NoDeploy37929372233均success；联合负责人独立核验三个容器同完整SHA/healthy，schema90、搜索4/排名4/详情4/Billboard48 ready。当前detail/BB清单wholeSHA分别为 `ff918b224573c59f8e863f2ed3ac5cd702240fa8a9d5a5ac5c06f77d2468df05`、`c54ff721b3e0aebe46a557bc44c8cbd2c56c83508e9f3ed586a1a0d6469c147a`，与历史文件相同但路径、准备/上传时间及SHA绑定分别保留；rank当前wholeSHA `198bd602956b1246f7841509ed446e19a03f424dce30874687bcf86b7294d0a2`。

人类明确本轮仅验收公开HTTPS，私有入口保持现状；另一项对决公开验收全部结束后，另明确授权一次 `docker restart --timeout 30 spotify-stats-production-backend-1`，实际只执行一次exit0、正常维护自然结束。三服务配置/镜像/容器保持，uvicorn新进程startticks137481646；此前两个SSH preflight失败没有执行restart。根未先请求summary/overview/stats预暖，也未清缓存、再次重启或改外层入口。

| 实际生产证据 | 结果 | 判定边界 |
| --- | --- | --- |
| 三引擎自然90，原2s点击/3s深链/2.5s全部可见 | 39/90通过；51项性能失败 | **性能FAIL**，完整首轮保留；Chromium15/42、Firefox12/24、WebKit12/24 |
| 点击45项 | 39通过、6超2s，其中2项全部可见超2.5s；最大核心2762.8ms、全部2844.9ms | 多数点击变快，不能据此称全部达标 |
| 深链45项 | 全部核心超3s，最大7820.5ms；shell后全部可见最大1991ms | 导航端到端失败，不能改用shell后时间替代 |
| 实际功能/布局 | 无页面错误/非GET/launch error；12屏外排名检查保持按可见性请求 | 性能失败之外未发现这些功能失败 |
| 116原顺序HTTPS全字段对账 | 实际exit0、116/116；108个200及8个未知实体404 | 功能Pass，不能覆盖性能FAIL；原入场要求完整自然90/同SHA/生产origin，并未要求性能Pass |
| 浏览器、API及总窗口strict v2 | 三个比较均exit0、完整read-window unchanged | 57保护表/37原源、五队列表、21主库发布表及六侧库全部表、schema/epochs/fence/inode全部同；access clock变化0 |

浏览器UTC `13:20:22.302760–13:31:36.522309`，PWA正常/fresh contexts，完整90项结束、全部context/browser关闭，实际进程exit1仅因性能门槛失败。没有修改门槛、单项热重跑或补一轮“首次”。API入场使用本轮完整自然报告及schema90/四exact/aux/fence对照，全字段只允许已定义的四个专辑请求身份归一。

唯一资源采样0.05秒、14,098连续样本，UTC `13:20:05.226048804–13:31:50.088600123`，覆盖整个UI窗口；同uvicorn PID7/startticks137481646，最大采样间隙52.595ms，采样进程实际exit0并以signal正常停止。RSS baseline462.469MiB、peak2095.602MiB、末驻留1724.961MiB；PSS baseline460.088MiB、peak2093.213MiB、末驻留1722.570MiB，CPU增量183.7秒、cgroup OOM事件增量全0。这是自然summary/stats/rank/overview混合窗口，**不能冒称单请求64MiB门槛或与纯overview本地324矩阵相同**。观察到高驻留，未据此认定整体OOM根因或关闭OOM事项。

原before89-v2仍保留实际旧采集时间与SHA `0654263f7735b02f5a3c7fdb053e6578893ae46b45df848b215d1e8f3ef8fe36`。跨迁移37原源事实完全同，schema89→90，artist_identity_state/governance_source_revisions、background_jobs及搜索FTS/aux/各侧发布表变化显式记录，publication fence同、主库inode改变；这不是同runtime GET守恒，也不称整库字节相同。生产同runtime的before、after-browser、after-API读连接均关闭，采集在资源窗口外：before `13:18:45.236295–13:19:10.926925`，after-browser `13:33:30.024073–13:34:08.636121`，after-API `13:36:33.377887–13:36:59.631037`（UTC）。

私有证据在 `output/music-detail-chart-acceptance/production-first-c58775f0/`，不提交真实数据：

- `browser-natural/results.json` SHA `517e9d7a8f9377dc14f2731402b7a5f132a38e5711fcedc9310e61de49a8a64f`；summary SHA `ca0fea89fe66c7828449b543f021461d7e98f8f6ff2b72b248d798cb297e2bb2`。
- `resources.json` SHA `388ab5806a4f9c4303aa50697c52de633c892c67300cb22e8cb8d486dff06675`；`browser-resource-completion-receipt.json`确认完整实际覆盖。
- `https-api-116-first/summary.json` SHA `0347080cb2fc2c733b8233ed6f0cd54d2f4c5ee9d26cfe310cd31ac24cb6b23f`；116原response逐个保留。
- `runtime-read-comparison.json`及两个分窗口比较SHA均 `0e81dbcf5ee53abcc7f90f558a1003c970a0d9d6dc086e2c5bb2674e9886b6c4`；三个v2 capture及独立receipt分别保留。

SSH首次握手失败发生在任何source capture/业务请求之前，最小代理验证后复用任务独占ControlMaster；现有sampler只增加传输参数，REMOTE原文/采样/矩阵合同不变。末端最终dockerinspect实际0、容器/镜像/PID/StartedAt/healthy与before同；owned master已自行结束，`ssh -O exit`因此255、最终logger wrapper1，原回执保留，随后仅本机ps确认原PID不存在、owned空目录清理成功。该清理收尾不改API/守恒/采样实际结果，未向backend发送信号。

## 剩余定位与下一步

本轮证据不能把全部超时归因于等待排名。首个歌曲深链HTML responseEnd302ms，但DOMready3021ms；entry JS为658,419B（约643KiB）下载2688ms，后续673,158B（约657KiB）图表chunk下载2890ms；capabilities于3117ms才发出、settings于5996ms才发出，overview/summary并行而服务耗时979/1058ms。首个专辑点击overview服务2256ms；另一些深链overview服务约82–125ms却仍端到端超5秒。需要分别处理静态加载/初始化、少数较慢服务及混合流程高驻留，不能统一当作纯网络或纯计算。

c587的三套Nginx源码已配置gzip；ResourceTiming的transfer/encoded/decoded字节与真实响应编码尚未形成完整压缩归因证据，不提出重复“开启gzip”或擅改外层代理。已用实际本地production build确认另一具体前置依赖：LazyEChart模块顶层导入ECharts，引擎进入三类详情route静态闭包。最小本地候选将整个引擎/注册/React适配器移入动态图表renderer；候选验证单独记录，未发布，不继承本轮或历史S4/生产Pass。后续维护原门槛、只读和统计合同；001保持OPEN/Partial，规划不归档，额外发布及独立首轮重启需具体授权。对决已完成状态及整体OOM独立事项保持。
