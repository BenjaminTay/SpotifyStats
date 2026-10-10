# 音乐详情榜单成绩性能验收

日期：2026-10-09。事项：`SS-2026-10-09-001`。当前结论：**Partial；业务本地 S4 历史证据保持，当前 d838814d 已正式部署。独立生产自然首轮完整 90 项只有 30 项通过、60 项性能失败；旧 c587 的 39 项通过、51 项失败保留。116 项功能对账及完整读取守恒通过。冷页面性能和高驻留仍需修复，本项未收口**。

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


## ECharts 动态 renderer 最小候选（本地验证，未发布）

候选基于0790689f，仅移动共享图表的加载边界：LazyEChart延迟导入EChartRenderer，后者保留原四种图表、八种组件和Canvas注册及React适配器。原Suspense占位高度、style、option、事件与其他props透传保持；未增加依赖或修改API、统计事实及布局。

实际production build前后均exit0。三类详情route静态JavaScript闭包各减少671,514B（约656KiB），完整renderer为679,538B的独立dynamic entry，已退出route静态前置。Track/Album/Artist静态闭包分别由1,466,111/1,479,675/1,472,682B降至794,597/808,161/801,168B；共享主入口仍为658,419B，因此不宣称全部冷加载瓶颈已解决。实际manifest与依赖图分别保留在本轮私有证据的frontend-build-baseline及frontend-build-lazy-renderer文件。

六个既有针对性测试文件共128项通过（移动详情布局、年榜、Query生命周期、排名可见性、导航历史及架构），两文件ESLint及TypeScript/build通过。真实Chromium本地360/1280视口、歌曲/专辑/艺人、点击/深链共12场景均正常绘制canvas且功能通过。使用本项8013长期运行后端和5183当前开发前端，backend_startup_mode为unspecified；这是局部功能/绘制证据，不是新冷进程、完整八阶段或生产性能验收。原注册清单及props保持的diff与上述实际证据足供最小候选审阅，不额外扩大全站或搭建覆盖数测试。

原记录离线关联还显示：首轮L2 dynamic/fixed歌曲深链窗口较大的RSS增长之前，前一点击场景的include_rank_context=true请求已在浏览器取消，未得到响应。服务端计算可能跨场景继续，但现有采样仅能证明时间重叠，不能将增量直接归因于排名、摘要或overview。该关联单列为后续副本定位线索，不作为本次renderer修复因果或整体OOM关闭证据。

候选需要联合负责人审阅后统一申请新发布及保持原门槛的生产首次90项/资源/只读验收；新部署正常启动可提供新进程窗口，不默认再申请额外独立重启。旧c587的51项失败保留，详情事项继续OPEN/Partial。


## d838814d 正式发布后的完整首次验收（性能仍失败）

实际生产为`d838814d5790ad9884fa9c30020801fdcb1044bc`。人类在协调聊天直接授权正常推送、正式发布及公开详情验收；原四历史传输文件清理方案因外部空间变化作废，发布负责人未执行新增服务器删除。CI37946309124与Release37946309024均原attempt1 success，共7实际jobs，Deploy113879894252成功；NoDeploy本次frontend/docs路径不触发，Release本身质量与三模式门禁完整执行。负责人独立8检查全部exit0：三OCI/healthy、schema90/search4/rank4/detail4/BB48、17运行调用链与3host helper hash精确，启动维护6303done/38failed、无pending/running。不是本候选新运行了本地默认完整八阶段；已有128项/12真实canvas/build/ESLint按相同前端代码复用。

部署正常启动提供本轮唯一新进程，没有额外重启或详情预暖。Backend container为`f5a543bf4dc89d7e324341c0a26d9dac169070aefd0677807bcb93aca98b4533`，image为`sha256:913c9e413b2e4a463586533694f0462ea345fb332d9e7497365142029e48ac3c`，StartedAt为`2026-10-09T15:09:06.623465968Z`，initPID1639652，uvicorn PID7/startticks138172479。维护后15:13:03UTC VmRSS已1014896kB/VmHWM1256992kB；此高基线不归因于后续UI。

| 层次 | 实际结果 | 范围 |
| --- | --- | --- |
| 原自然FIRST90 | **30通过/60失败，exit1** | Chromium16/42、Firefox12/24、WebKit2/24；45深链全部核心超3秒，15点击失败；只有性能失败，无页面错误、非GET或启动错误，12屏外排名检查符合原合同 |
| 原116接口 | **116/116通过，exit0** | 108个200、8个未知404，统计字段/顺序/归属完全对账，仅原四专辑请求身份字段归一；公开权限正确 |
| 唯一50ms资源 | **13,391样本，exit0，stop0** | 连续覆盖整个UI、同PID/ticks、最大间隙51.390ms；不冒称单请求资源门槛 |
| 三个完整strict窗口 | **全部exit0/unchanged** | 浏览器、API及总窗口：57保护/37原源、5队列、21主发布及6侧库全部发布表、schema/epoch/fence/inode同，clock变化0 |
| 最终运行状态 | **exit0，三服务healthy同d838** | 15:31:06.955956UTC，Backend容器/image/initPID/StartedAt及uvicorn ticks保持；全部浏览器/reader/collector结束 |

FIRST90 UTC`15:15:06.745746–15:25:49.999592`，PWA正常、fresh contexts、原顺序及2000/3000/2500ms门槛保持。资源窗口UTC`15:14:52.089386–15:26:01.600537`，RSS991.109→2299.176→1928.613MiB，峰增量1308.066MiB；CPU178.44秒，OOM事件增量全0。相对c587的资源窗口基线462.469MiB，本轮启动维护后基线更高，不能据峰值/增量差直接断言内存改善或renderer导致后端增长；整体OOM保持开放。

本轮before capture为UTC15:14:08.881342–15:14:35.342223，after-browser为15:27:06.933957–15:27:50.115727，after-API为15:29:40.307846–15:30:07.111055；所有采集在UI资源计时之外、7读连接正常关闭。API原入场门禁要求完整原90结束及精确source/aux/fence匹配，不要求自然性能Pass，本次没有改门禁后置116。没有追加线上诊断或热重跑。

### 与c587原90逐场景对照

同browser/viewport/entity/navigation/merge/threshold key完整90项对照：原39通过变为30通过，28持续通过、49持续失败，**11通过→失败、2失败→通过**。10项WebKit点击和1项Chromium fixed专辑点击退化；2项Chromium L3艺人点击改善。结果不能称整体改善；两个时点的启动基线与网络状态不同，这不是随机因果实验。

| 原场景key | 变化 | 核心ms：旧→新 | all门槛ms：旧→新 |
| --- | --- | --- | --- |
| chromium / 1280 / album / click / L2 / fixed | 通过→失败 | 818.1 → 3184.0 | 911.7 → 3267.1 |
| webkit / 360 / track / click / L2 / dynamic | 通过→失败 | 1450 → 2269 | 1504 → 2775 |
| webkit / 360 / album / click / L2 / dynamic | 通过→失败 | 423 → 2585 | 494 → 3869 |
| webkit / 360 / artist / click / L2 / dynamic | 通过→失败 | 657 → 2224 | 760 → 3464 |
| webkit / 390 / track / click / L2 / dynamic | 通过→失败 | 222 → 2320 | 293.0 → 2379 |
| webkit / 390 / album / click / L2 / dynamic | 通过→失败 | 434.0 → 2305.0 | 511.0 → 3758 |
| webkit / 390 / artist / click / L2 / dynamic | 通过→失败 | 749 → 2969 | 832 → 3465.0 |
| webkit / 900 / album / click / L2 / dynamic | 通过→失败 | 377 → 2199 | 461.0 → 2272 |
| webkit / 900 / artist / click / L2 / dynamic | 通过→失败 | 619 → 1800 | 685.0 → 3437 |
| webkit / 1280 / album / click / L2 / dynamic | 通过→失败 | 440 → 2083.0 | 491 → 3379.0 |
| webkit / 1280 / artist / click / L2 / dynamic | 通过→失败 | 583.0 → 2544 | 641 → 3438 |
| chromium / 1280 / artist / click / L3 / dynamic | 失败→通过 | 2246.8 → 1512.2 | 2373.3 → 1602.2 |
| chromium / 1280 / artist / click / L3 / fixed | 失败→通过 | 2244.6 → 1644.0 | 2325.3 → 1736.9 |

最大点击core2762.8→3184.0ms、all2844.9→3869ms；最大深链core7820.5→6226.3ms、shell后all1991→3991ms，深链导航起点all8177.7→8334ms。只改善某个最大值不能代替全部场景Pass。

### 现有时序支持的最小下一步

实际首个Chromium歌曲深链的theme仅1644B，完整renderer679538B按需加载，配合真实build graph支持引擎已退出route静态前置。settings首次启动约5996→3545ms；但main仍658419B、下载2673ms，DOMready2993ms，summary/overview服务1616/1643ms，核心5779ms仍失败。消除旧前置成立，端到端完成不成立。

WebKit专辑/艺人多个点击场景服务仅约70–80ms，renderer资源约3.7–3.8秒；部分还记录两次main资源，图表等待与退化时间重叠。现有记录不含完整asset请求起点、动态module initiator及Content-Encoding，不能断言renderer触发重复主入口、压缩失效或慢服务是唯一因果；Nginx源码已有gzip，不重复建议“开启gzip”。

下一步优先在本地production preview复现WebKit新增退化，检查dynamic renderer的实际依赖、PWA/模块加载是否延迟或重复，比较真实content绘制与网络链；同时限定主入口/初始化前置依赖。必要修复先形成可审阅候选，不立即追加生产重启、发布或整轮热测。高驻留另在副本拆分已取消rank计算及缓存生命周期，保留启动维护基线，不能借此关闭OOM。详情仍OPEN/Partial，计划不归档，对决已完成状态保持。

证据均在私有`output/music-detail-chart-acceptance/production-first-d838814d/`。原browser_probe把`--output`解释为文件，本轮误给无扩展路径，首个summarizer因此exit1/NotADirectoryError；完整90原始文件保留为browser-natural-original.json，仅byte-identical复制到browser-natural/results.json后汇总exit0，path receipt保留，不重跑/改字段。原截图路径保持，全部私有文件600。五工具原hash不变；唯一samplersignal停止0，不用SSH ControlMaster，无旧收尾255问题。

- `browser-natural/results.json` SHA `a4fb8b45dc95c691df639ecf3184b4232cdb1c8c64b3a53388cf52b61c06b3e6`。
- `browser-natural/summary.json` SHA `5019abe1b5f42bcd4b7d60fb7c8b10573321abad6b74653aa64de87d087e01ae`。
- `resources.json` SHA `d65d88ff36d841b502eaa4801e27a93ddc8b8968ebbcb172388e98a9e609605b`。
- `https-api-116-first/summary.json` SHA `204359042f21fdfd81fadd76dce4ade0fa745daae4eea8cf09e52c57071dcdc9`。
- `runtime-read-comparison.json` SHA `0e81dbcf5ee53abcc7f90f558a1003c970a0d9d6dc086e2c5bb2674e9886b6c4`。
- `offline-c587-d838-case-comparison.json` SHA `eef43f5012dac2836d90aca33b997b1e8d7e0083180d534421763de0dee874bd`。
- `offline-static-api-timing-comparison.json` SHA `684cdf7792383b603578100f0f85e61997d5daf0977d1c46a04d68acc2702f2f`。


## 2026-10-10 本地加载链对照与折线候选（Partial）

生产仍为d838，原30/90结果保持；本节仅本地production preview及既有8013副本后端，未重启、未访问生产、未新增资源采样或完整矩阵。日期采用Asia/Shanghai。私有证据目录为`output/music-detail-chart-acceptance/local-webkit-loading/`。

### 原20场景、并行实验8场景及入口减量

原8个不限速点击场景两种边界均正常；允许SW的重复main记录来自SW，禁用SW时仍有304记录，不能据页面资源条目推定重复下载。受控静态传输使用每响应250KiB/s加80ms、identity编码、immutable资源，API仍沿既有8013代理，属于合成网络诊断。原受控8点击中d838图表约2.4–2.7秒、恢复旧边界约0.15秒；4个直接深链对照中，恢复旧边界却把核心3.2–3.4秒拖至约5.6秒。回退不是完整修复。原传输保留一次旧边界main的BrokenPipeError，不能称全部传输成功。

另8个并行预载实验收益只有几十至约253ms，仍不达标；六文件实验patch保存，源代码已恢复，没有并入当前候选。既有128测试/build/lint与首个TS失败修正回执分别保留。原20和parallel8的数值及请求trace JSON不覆盖；旧本地工具截图使用共享四个文件名，截图只能代表最新场景，不能用于历史图像对照，生产原截图不受影响。

入口既有一次graph提供两处mobile barrel→leaf导入线索。实际仅修改MobileTopBar/MusicSearchResults后，main658419→527193B，gzip205931→165814B；但renderer静态闭包1337957→1319273B仅少18684B，三详情route静态总量各增加约1.9–2.1KB。不能把主入口减20%说成详情总量减20%。正常build/TS、两文件lint与两个既有搜索/移动测试文件32项通过。

### 五前端文件折线候选

在两leaf之上，新增LineEChartRenderer，LazyEChart保留默认full及占位/style/props传递并增加显式line选项，仅RankTrendChart选line。原EChartRenderer逐字保持。三类overview主图及所有叠加series均line；保留Line、DataZoom、Grid、Legend、MarkArea/MarkLine/MarkPoint、Tooltip与Canvas注册，没有预载hooks、全局预载或业务Query修改。

| 实际正常构建闭包 | d838 | line+leaf候选 | 变化 |
| --- | ---: | ---: | ---: |
| main，B | 658419 | 527193 | -131226 |
| renderer冷静态闭包，B | 1337957 | 1241148 | -96809 |
| Track route + line闭包，B | 1474135 | 1398153 | -75982 |
| Album route + line闭包，B | 1487699 | 1411829 | -75870 |
| Artist route + line闭包，B | 1480706 | 1404961 | -75745 |
| default full冷静态闭包，B | 1337957 | 1321607 | -16350 |
| 全产物JS，B | 3744653 | 3751775 | +7122 |

文件去重按manifest imports计算，gzip逐文件测量。新折线实际新增下载为core601187加line261，共601448B，不能以261B称图表引擎大小。line/full共享core；对两leaf中间版本，default full闭包增加2334B，三个route静态闭包各增加218B。完整图表及整个站点体积并非全面减少。

### 唯一新受控8场景

WebKit360、album/artist、click/direct、SW allow/block，fresh contexts全部正常关闭，runner实际exit0仅表示诊断无异常。复用原工具local1000/2000/1500ms profile，raw性能失败保持；下表离线按原生产2000/3000/2500ms门槛评估，仍只是本地诊断，不能替代生产首次验收。

| SW / 实体 / 导航 | core ms | all导航 ms | all shell后 ms | 原门槛本地满足 |
| --- | ---: | ---: | ---: | --- |
| allow / album / click | 117 | 2555 | 2686 | 否 |
| allow / artist / click | 90 | 2399 | 2538 | 是 |
| block / album / click | 72 | 2312 | 2524 | 是 |
| block / artist / click | 76 | 2299 | 2471 | 是 |
| allow / album / direct | 2925 | 5407 | 2542 | 否 |
| allow / artist / direct | 2925 | 5413 | 2539 | 否 |
| block / album / direct | 2905 | 5382 | 2534 | 否 |
| block / artist / direct | 2939 | 5433 | 2542 | 否 |

click用点击后all，direct用shell后all。8项只有3项满足原门槛，5项图表可见超时。相对原d838六个可配对场景，业务请求path/query multiset全部一致；新增两个block/direct没有旧对应基线，不能虚构对照。相对parallel8八项业务请求均一致。allow深链album核心3364→2925ms、all6274→5407ms，artist3221→2925ms、all6024→5413ms；allow artist点击all2379→2399ms略回退。核心改善成立，整体修复不成立。

五文件lint、正常build/TS及原六文件128项测试actual0；两leaf32测试复用同未变路径结果，不重跑。另一个真实Chromium桌面艺人overview局部scene复用既有CDP工具验证tooltip内容、实际legend点击selected变化及dataZoom拖动canvas变化，actual0，无console warning/error、pageerror或横向溢出，只加载line/core。首次通用legend比例未命中actual1，完整失败JSON/log保留，按实际legend文本bounds修正诊断后通过，不把首个失败写成0。

临时5196 preview经核对PID/cwd后SIGTERM退出143；5206 transport优雅退出0，322个asset请求无传输错误。既有8013/5183未改。五文件候选patch SHA256为`3d13f4e7191591df453e09efbdfce84292e0be44d4eb29446f5815e478e7ae42`，所有actual exit、source/hash、原门槛离线结果和证据局限见`line-leaf-final-receipt.json`。候选未提交/推送/发布；详情保持OPEN/Partial，OOM保持开放。

## 2026-10-10 静态代理gzip缺口与联合候选（本地验证）

此项只读生产探针在d838 FIRST90完整结束后执行，只有静态GET与运行配置读取，没有业务API、预暖、配置写入、服务重载或重启。原本地八场景禁止新预载；五前端源文件及七份证据SHA逐项与详情任务一致，整合正常build/TS实际0。

公开同一`/assets/index-Cdw7F_pV.js`接受gzip与identity均HTTP200/658419B，无Content-Encoding；原始header有`via: 1.1 Caddy`。本机3002同资产direct gzip为240732B，加`Via: 1.1 probe`为658419B。活动Nginx只有gzip on/vary/min/types，没有gzip_proxied；活动Caddy统计域名路由反代127.0.0.1:3002，无encode handler/显式header操作。安装版本v2.11.4的[官方tag源码](https://github.com/caddyserver/caddy/blob/v2.11.4/modules/caddyhttp/reverseproxy/reverseproxy.go#L808-L809)向上游添加Via；[Nginx官方规则](https://nginx.org/en/docs/http/ngx_http_gzip_module.html#gzip_proxied)按该头识别代理请求，默认off。以上证明静态压缩缺口；两次公开耗时不作为控制变量一致的性能比较，也不证明全部详情慢均由压缩导致。

修复仅在fallback、public/private两模板的/assets/下添加gzip_proxied any，不改全局gzip/API/Caddy/Tailscale。先在已有本地Docker Nginx1.30.5执行三种完整网关配置，dummy token/open showcase include，后端解析为隔离地址且不请求API。每种baseline/candidate各检查direct gzip、Via gzip、Via identity及Via目录外对照，共24项通过。原d838尺寸资产658419B在修复后240744B，内容SHA守恒；随后对整合构建实际main527193B再执行24项，Via gzip为194317B，identity仍527193B，所有解压SHA、Vary、immutable缓存正确。后者是本地传输证据，不能宣称生产已缩小至194317B。局部覆盖使目录外Via压缩仍关闭，完整生产Nginx1.31.6及端到端首次验收待发布后验证。

首次检查将多个Cache-Control转dict丢失重复头，immutable断言实际1；修正诊断为get_all合并后实际0，无产品追加修改，初次失败保留。另首次SSH Python缩进失败1且没有发请求，修正后host controls0。全部隔离自有容器已停止；未清理额外生产文件或镜像。证据位于联合worktree私有`output/versus-personal-acceptance/release-d838814d5790ad9884fa9c30020801fdcb1044bc/static-encoding-readonly/`，包括公开原始headers、host-controls、active-caddy-route、caddy-version、isolated-nginx两轮receipts、初次失败及集成构建log。未提交/推送/发布，原两轮生产失败和本地identity3/8结果保持；详情OPEN/Partial，OOM独立开放。

## 626232b0 正式生产首次验收（2026-10-10，OPEN/Partial）

真实人类授权turn `01a1235c-2b71-7281-8fba-1ded8a98a617`对应固定15文件联合补丁SHA256 `6ddb27a598ec66ffcacf2b8714ace16ce7e8f2e42071c560b8a4b5c59df34cc6`。唯一发布负责人正常提交/推送`626232b0709b4751ff1a95d1f67d76d2e5166882`，CI38012311927、NoDeploy38012311958、Release38012311948均attempt1 success，11实际jobs全部通过，安装114098510565成功；本次Nginx路径实际触发NoDeploy，不能套用d838的未触发状态。独立8运行核验全部0，三healthy同完整SHA，17源码/3host helper精确、schema90/rank4/detail4/BB48ready。

部署新进程提供唯一首次窗口；没有额外手动重启、详情预暖或挑选重跑。Backend container `1a3d2bd6b63a6d74d67509bc674bd3c5fb769d5d8b4b289d2166358ea78e0254`，image `sha256:4073324e8a8db010948569e84e61fb92f44a96690e932ac9e3b2ddc7418f834f`，StartedAt `2026-10-10T01:39:29.622873479Z`，host init2248790、uvicorn2248831/container7/startticks141954778。启动维护01:42:29UTC自然结束，6313done/38failed，无active；handoff01:42:39UTC身份/配置精确，VmRSS已978180kB，启动高基线单列。

所有下列时间为UTC；本节日期按Asia/Shanghai。原FIRST90从01:44:21.384316至01:50:37.092215，fresh contexts、PWA正常、原顺序/同90key及点击核心2000ms、深链核心3000ms、all2500ms保持。45点击all从点击计，45深链all从shell计，不将导航起点all混作门槛。

| 验收层次 | 实际结果 | 边界 |
| --- | --- | --- |
| 原FIRST90 | **83通过/7失败，exit1** | Chromium36/42，Firefox23/24，WebKit24/24；全部90完整，不以旧本地8覆盖 |
| 原116接口 | **116通过/0失败，exit0** | 108个200、8未知404；原全字段/顺序/归属对账与仅四专辑身份字段归一保持 |
| 唯一50ms资源窗口 | **7881样本，collector0/stop0** | 全UI连续覆盖，同PID/ticks、最大gap51.425ms；整页混合窗口不是单请求64MiB门禁 |
| 三个完整strict读窗口 | **全部exit0/unchanged** | before→browser、browser→API、before→API；57保护/37源、5队列、21主发布及6侧库全部发布、schema/epoch/fence/inode相同，accessclock变化0 |
| 最终服务/进程 | **exit0，三healthy同626** | 01:53:55.278796UTC，Backend容器/image/init/StartedAt及uvicornticks全部保持；读连接/浏览器/collector均结束 |

### 七项原始性能失败

没有功能异常、页面错误、非GET或launch失败，12个屏外排名检查符合合同。7项core超门槛，其中2点击另有all失败；完整原结果及截图保留，不再热重跑。

| 浏览器/宽度/实体/导航/变体 | core ms | all导航 ms | shell后all ms | 失败 |
| --- | ---: | ---: | ---: | --- |
| Chromium360歌曲direct/L2 dynamic | 3230.4 | 3544.2 | 314.0 | core |
| Chromium360专辑click/L2 dynamic | 3009.1 | 3339.4 | 6173.4 | core/all点击 |
| Chromium360专辑direct/L2 dynamic | 3771.2 | 4083.9 | 783.6 | core |
| Chromium1280歌曲click/L3 fixed | 2524.5 | 2898.0 | 3436.0 | core/all点击 |
| Chromium1280专辑direct/L3 fixed | 3374.8 | 3712.4 | 876.9 | core |
| Chromium1280艺人direct/L3 fixed | 3129.9 | 3510.5 | 1262.9 | core |
| Firefox360歌曲click/L2 dynamic | 2025.0 | 2370.0 | 2515.0 | core |

最大点击core3009.1/all3339.4ms，最大深链core3771.2/shell后all1408ms。相同90key完整离线对照d83830→83：54失败转通过、1通过转失败、29持续通过/6持续失败；对c58739→83：45改善、1退化、38/6持续。唯一原通过→失败为Firefox360歌曲点击，d838 core1898→2025ms、all2231→2370ms；保留127ms退化，不把总体改善称全Pass。三个时点的网络和启动基线不同，不是随机控制因果实验。

### 真实静态传输与剩余服务等待

原浏览器ResourceTiming的首个歌曲深链main encodedBodySize194353B、duration542.1ms、DOMContentLoaded901.6ms，前d838对应main2673ms/DOM2993ms。原工具不含asset Content-Encoding；发布负责人仅在整个自然/资源窗口结束之后，于01:51:38.630763UTC独立两次static GET补足头证据，没有业务API。生产Nginx1.31.6经真实Via:1.1 Caddy：gzip响应Content-Encoding:gzip/194353B，identity527193B，两者解压/原文SHA256 `1a27ff1c20d8dda7ce4ffc3668a4f6c0bc812387c109b5823beee6d698aea705`与安装两Web相同，Vary/immutable正确。真实产物名index-C1TWxgjQ.js，不沿用本地hash名或194317B数值；两GET耗时不是受控网络因果比较。

剩余失败原请求时序已有服务贡献：初始歌曲deep summary/overview server1690.044/1449.609ms；初始专辑click overview2729.247ms；L3 fixed歌曲click overview2267.186ms，Firefox360歌曲click overview1852.866ms。部分取消rank与这些请求时间重叠，不能据此断言rank阻塞/服务端取消有效/缓存驻留根因。后续以现有七失败trace在明确副本定位目标读取及缓存生命周期，避免新增线上诊断或再盲目加预取hook。

### 完整资源与只读证据

资源窗口01:44:12.958524–01:50:46.975996UTC，RSS955.25390625→2508.078125→2198.25MiB，peak增量1552.82421875MiB，CPU184.49秒，OOM事件增量全0。相对前轮462/991等不同维护基线和混合顺序，不能据峰值称内存改善；后端高驻留仍开放，前端与压缩修复不能关闭OOM。

before capture01:43:39.386220–01:44:06.233434；after-browser01:51:18.382943–01:52:03.965348；after-API01:52:50.652050–01:53:24.352036UTC，各7读连接关闭，均在资源测量之外。原API gate仅在完整90结束及exact source/aux/fence匹配之后放行116，未改变失败门禁。唯一collector按token/PID/ticks停止，不给uvicorn信号。最终三healthy同626，所有生产采集正常结束。

私有证据目录`output/music-detail-chart-acceptance/production-first-626232b0/`，文件600；`production-completion-receipt.json`记录实际退出码/进程连续性/全部哈希，原五工具完全未变。主要SHA256：results `cdf7e7bd6ac0d336d3f09e23d7b07c8ab365ced32c0049272af8b355e67adf70`；summary `3948187f206491e7a8f59ee6fe311fa23d37b95005a966cffd598695edad677d`；resources `49e03e7d9bc87cfdc3ee3b82b0db77ff3bda2dc9ee795d8a938ad39256163f17`；API `71d7e71294906e828fec9ed63cc1fee28d0160d1c3e3d830aff18ade89183dca`；三个strict均`0e81dbcf5ee53abcc7f90f558a1003c970a0d9d6dc086e2c5bb2674e9886b6c4`。前两轮生产失败与旧20/parallel8/line8完整保留。

联合修复已实现、已正式发布、压缩端到端证据和功能/守恒通过，整体详情性能仍OPEN/Partial。7项超时和后端驻留后续分开处理；对决完成状态保持，详情计划不归档，OOM不关闭。
