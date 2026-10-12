# 音乐详情榜单成绩性能验收

日期：2026-10-12。事项：`SS-2026-10-09-001`。当前结论：**艺人范围名称读取与已验证身份复用候选已实现，201个不同专项/真实身份oracle/9完整响应/两strict通过；单轮局部收益小，完整资源分窗有正负差异，总体资源准入NOT_PROVEN，整体Partial，full8 NOT_RUN，未提交发布**。最新结果见末尾“艺人范围名称读取与已验证身份复用”；前一JSON候选资源准入NOT_MET仍独立暂缓，旧settings前端候选也保持冻结。最后保存的生产4f3f首次89/1、OOM及手机OPEN保留，本轮无生产复验。

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

## 2026-10-10 后端冷排名与宽表驻留候选（本地 Partial）

基线源码为已发布文档头 `4d9e0ba3`（运行代码626），候选位于 `codex/detail-backend-contention`，未提交、未发布。本轮仅副本开发与验证，未新增生产请求、压力测试、重启或服务器清理。上一轮原生产83/90、7超时和整体OOM状态保持。

使用已准备schema90主库及Billboard副本，其他sidecar经Online Backup复制；正常lifespan、full warmup及维护自然结束后测量。与生产before capture的37套原始来源规范化事实全部相等，55/57保护表逐字事实相等；`artist_identity_state`管理字段和`governance_source_revisions`治理跟踪与生产不同，不能称生产57表完全相等。修前/修后隔离输入的57保护表全部相等；各自GET读窗口内主库与六sidecar文件SHA全部不变。旧sidecar不绕过路径身份校验，由正常维护在当前副本路径准备。

七个失败trace按实际path/query重放，分别做单独请求、原请求偏移并发和有界重复。浏览器已取消的rank在本地让其完整结束，以测量后端实际成本，不用取消传输证明计算终止。原时序并发先运行，随后单独/重复为热对照；另保留首轮单独冷请求诊断。剖析记录wall/thread CPU与SQLite执行/取数，资源采样50ms；DataFrame检查不调用强制GC。SQL汇总含execute/fetch操作，不能与嵌套service时间相加。

主要瓶颈是默认歌曲完整排名仍加载全量播放并三次构建时长切片及排名行。L3固定阈值service5509.240ms，其中builder wall5503.217ms/thread CPU5454.106ms、全量加载1760.345ms、三个全局时长约654.627/575.424/573.437ms；L2动态service3731.772ms。这里实际CPU占主导，未见busy/locked；不能据此推定生产所有summary/overview延迟都由排名造成。本地榜单目标读取约15–49ms，生产1–2.7秒目标服务成本没有完整复现，SQLite/JSON和锁等待并非本轮已确认主因。

候选仅两类改动：

- 默认lifetime歌曲完整排名复用现有 `entity_rank_context_v2` 精确发布，目标歌曲事件/时长/趋势/最近播放仍按原规则计算。只覆盖primary DB、L2/L3和默认四配置，其他scope保留原路径。发布缺失/漂移返回503，不冷建/写入/排队；不新增发布格式或维护任务，不改对决。
- 四套播放宽表缓存复用历史资源候选的共享384MiB字节预算，各自条目上限保留。计量包括attached DataFrame和嵌套区间，共享引用可能保守重复计量；超大条目只供本次调用。增加缓存失效generation防止在途旧结果重新驻留。未整包合入旧分支，未增加资源锁；预算限制缓存保留量，不是进程RSS上限。

修前/修后七场景×三序列共57个完整HTTP响应的规范化SHA全部相等（包括摘要、榜单、播放统计及排名）。原时序冷rank：L3固定5509.240→64.483ms，L2动态3731.772→51.988ms。正常启动后RSS1539.641→1356.281MiB；整个有界测量peak1795.875→1377.828MiB；结束空闲RSS1288.844→967.609MiB。结束可达DataFrame的深层列内存951.901→304.744MiB，候选共享预算实际327.136MiB。列内存、含区间的预算、RSS各有不同含义；结束RSS下降可能包含分配器/自然回收，不能全部归因于缓存或声称整体OOM已修复。启动等待6.052/18.078秒分别记录，不把启动成本混成详情耗时。

已有前端生产构建在新loopback代理及正常启动候选backend下，七个原失败case key加一个正常艺人点击对照8/8通过原local门槛（click1000/direct2000/all1500ms）。core43–569ms、all64–883.2ms，fresh browser context与PWA正常策略保留；这是本地热后端专项，不能替代生产自然首次、完整90或默认全栈验收。

回归覆盖四变体歌曲完整payload与旧builder逐字段相等、禁止无目标播放装载/全局排名计算、缺失与revision漂移fail-closed、跨loader预算淘汰、超大条目不驻留、在途失效；沿用对决排名兼容测试。完整后端门禁：unit2648通过/2skip（138.81秒）、contract563通过（151.64秒），均实际退出0；backend Ruff、当前/含归档文档审计、CI基线一致性及diff-check通过。其后追加默认完整门禁及定向复验，结果见下节，仍不标全栈Pass。前端及压缩源码未变，原证据按范围复用。

私有完整记录为 `output/music-detail-chart-acceptance/backend-followup/` 的baseline/cold-baseline/candidate、comparison、same-source-receipt及browser-eight；保留初始诊断和修复过程中失败的测试/启动日志，不覆盖为Pass。新开8024/5224进程和全部浏览器上下文已关闭，旧8013/5183与正式数据保持。

## 2026-10-10 追加默认门禁与定向复验（历史 Partial，后续诊断见下节）

`singleflight`原来已由`functools.wraps`自动透传`cache_budget_info`，不是预算可见性缺失；本次增加显式接口透传。实际两个播放loader与注册的`get_stats()`均显示共享预算402653184B，25项缓存/精确排名相关测试通过，实际退出0。已有57响应、本地8场景和资源对照不重复测量；性能路径源码保持，接口补充不改变统计响应。

原脚本未修改，backend为正常lifespan/full warmup，维护自然结束后运行；各轮应用/测试源码清单与SHA绑定到当前未提交候选，轮内均未变化。主库与六sidecar仍为上述schema90隔离副本，正式数据库和生产服务未参与。默认完整门禁首次因调用方使用了不合法dataset枚举而退出2，尚未进入阶段；原日志保留，改为`online_backup`后才进入实际门禁。

| 实际运行 | 选择模式 / 退出码 | 结果 |
| --- | --- | --- |
| `20261010T024228.170096Z-f6499c0db4ce`，516.109秒 | `full` / 1 | preflight、quality通过；种子后端3853通过/2skip，集成9通过后歌曲统计503失败，后续5阶段未运行 |
| `20261010T030237.092011Z-f181765951a3`，479.190秒 | `from api` / 1 | API通过，51接口22次/热P95 500ms原门槛无慢项；路由53/54通过，桌面周榜失败，后续3阶段未运行 |
| `20261010T031325.939811Z-5e41076e5d02`，309.552秒 | `from browser-interactions` / 0 | 交互80.032秒、清单45.731秒、兼容183.728秒均通过；Chromium/Firefox/WebKit通过，脚本总状态`PARTIAL` |

集成失败已修正测试准备：原测试只发布旧艺人rank，没有发布歌曲现在消费的精确rank。新增私有fixture执行`ensure/read`并断言ready，沿用原HTTP200和内容断言；产品缺失/漂移仍503，GET不构建。fixture hooks通过。定向集成先67通过后封面404失败，原因是复验误继承关闭外部封面的诊断参数；恢复原外部封面配置，剩余118通过/1skip/68 deselect。pytest前缀筛选连带排除了封面失败项，另以精确node ID单测通过。三份JUnit去重覆盖186通过/1skip，共187项；这不是一次完整集成运行，所有失败保留。前端完整803通过/4skip及build通过；新增文件显式hooks与集成两文件hooks通过，不以`--all-files`代替未跟踪文件检查。

桌面周榜首轮三个`projection=page`请求（最新周album/artist及前一周track）503，稍后的相同参数手机请求200；定向桌面复验通过且无控制台错误/告警/溢出。此路径没有直接调用新增歌曲rank读取，但首轮503根因未确定，不能据热复验排除候选资源影响或宣布已修复。原失败和门槛保持，不新增周榜产品改动。

所有测试存储guard均未触发限制并清理自有临时目录；默认轮峰值1099840959B。新后端四进程均完成shutdown并以SIGTERM退出（实际-15），自有Vite核对PID/cwd后SIGINT退出130，8024/5224均无监听；旧8013/5183未操作。私有`*-binding-after.json`、原/续跑summary、`integration-coverage-receipt.json`和`billboard-desktop-retry.json`保存退出码、源码哈希及覆盖边界。

候选实现及本地定向验证已完成；尚无一次默认完整八阶段Pass，整体仍Partial。下一步独立完整门禁与正式发布/生产自然首次验收分开安排，不能拼接本轮结果为Pass。未提交、推送、发布或访问生产；原83/90、7性能失败及整体OOM开放状态保持。


## 2026-10-10 周榜503有界因果诊断与补修

本轮真实人类授权来自协调聊天turn `01a123fe-b726-7e71-bf9f-d21b7f2d82b8` 的“可以”，限定副本诊断、必要修复与一次完整本地门禁；未扩大到提交/发布或生产访问。使用同一路径、同源schema90七库，正常lifespan/full warmup，维护自然结束后，依次比较已发布运行代码626对应的4d9e源码、此前候选及补修候选。原三条首轮503的工具仅保存控制台状态与服务访问日志，没有错误体或内部异常；不可恢复为逐请求因果证明。

三轮各限定5个HTTP请求，共15个：首次最新track后并发读取最新album/artist及前一周track，再对原最新album请求穿插受控运维提交。自然四请求三轮全部200，完整响应SHA逐一相等，未稳定自然复现原503。故不无限重试或把自然200称原失败已消失。

有界对照在独立writer线程仅更新现有`cover_cache_state.updated_at`，不写统计事实，不调用GET维护/排队；每轮恢复原运维时间值。基线及修前候选中，三次提交使`PRAGMA data_version`依次2→3→4→5，三次来源向量digest完全相同，却耗尽旧三次采集重试。真实HTTP503错误体为`weekly / snapshot_unavailable / target_revision=null`，内部异常为`Analysis source changed during revision collection`。三轮所有持久来源epoch/revision向量前后相等，exact weekly成品与source/target revision不变。原失败窗口有封面下载提交，初始正常启动报告成品current；本轮确定这是既有可达缺陷，基线与修前候选的revision源码SHA相同，不是共享Frame预算引入。原三条未捕获内部异常，仍不逐条断言与此次机制相同。

最小补修仅令`analysis_snapshot_revision.source_revision()`在一个短只读SQLite事务中读取tracking合同和持久来源向量，finally rollback；拒绝传入未提交事务、无效tracking继续失败，返回一个完整已提交读快照。移除对任意SQLite提交的物理token重试，不改摘要/榜单计算、来源向量格式、schema、发布版本或维护任务。外层Billboard发布前后revision校验和builder漂移校验保留，真实事实提交由下一次读取观察；不缓存过期token，不启用GET冷建、写入或排队。已有Community来源读取也采用相同读快照原则。

新增两family运维提交回归及中途事实提交读快照回归修前3失败、修后相关81项通过；原提交前可见性与非法tracking回归保留，异常后事务已结束。初次hook只自动修正import顺序并退出1，复跑hooks全部通过、实际0，失败日志保留。修后受控HTTP200/56.18ms，发布为exact ready/current，响应SHA与同轮自然album完全相等；自然四请求约68–160ms，仅有界诊断，不作性能P95。未重复57响应、资源、专项8或生产90矩阵。

私有证据位于`output/music-detail-chart-acceptance/backend-followup/weekly503/`：三轮receipt/events、完整HTTP失败体、comparison、regression-before/after、hooks-first/final及七库Online Backup输入收据。七库备份只作冻结输入溯源，实际完整门禁仍使用已就绪同源runtime路径，不借用新文件的LKG身份。首次备份helper因frontend cwd相对路径错误退出1，尚未备份或运行门禁；纠正后冻结7库，原错误保留。

使用标准未注入uvicorn、正常外部封面配置，冻结源码与输入后从头运行默认full模式八个必需阶段；实际完整结果如下。

## 2026-10-11 核验默认完整门禁结果（Partial）

运行`20261010T042212.525715Z-d54c21f86662`于2026-10-10实际结束，2026-10-11续接时核验。选择模式为`full`，未使用`--from/--only`或放宽门槛；总耗时1668.385秒，实际退出1、总状态FAIL，保留完整原日志。

| 必需阶段 | 实际结果 | 耗时秒 |
| --- | --- | --- |
| preflight | PASS | 7.645 |
| quality | PASS | 65.014 |
| backend | PASS | 683.784 |
| api | PASS | 204.425 |
| browser-routes | PASS | 399.552 |
| browser-interactions | PASS | 79.806 |
| browser-inventory | FAIL | 228.045 |
| browser-compat | NOT_RUN | 0 |

同轮种子测试3856通过/2skip，完整真实副本集成186通过/1skip；前端803通过/4skip及build通过。API51接口按原22次/热P95 500ms门槛全部通过，0慢项。原桌面/手机54路由和响应式矩阵通过，榜单页首轮未再报503；不能以本轮正常请求逐条证明历史三个503属于同一机制。

清单已通过前12路由的桌面/手机24场景，随后`/ai-insights`仅导航栏、rootTextLength29，等待45秒后超时。没有原失败时的浏览器网络/异常详细记录，不能认定后端修复或revision事务引起，也不能凭重试通过认定其根因。按授权只做一次有界定向复验与末两阶段续跑，不再重复整轮门禁。

前后1454个应用/测试/脚本文件SHA全部相等，绑定记录实际fullstack_exit1；自有backend正常shutdown、实际SIGTERM退出-15。测试存储guard峰值1107681784B，最低剩余53050650624B，未触发限制，cleaned=true。续接前8024/5224均已无监听；旧Vite会话已不可读取，无法补报其退出码。此前已核实的旧进程退出码保留，不套用本次。所有证据在`backend-followup/final-fullstack-*`与对应run目录；正式库和生产未参与。

2026-10-11有界AI定向复验桌面/手机2/2通过；随后同源正常启动执行`from browser-inventory`续跑`20261011T034319.860761Z-3093766ceeca`，实际退出0、总状态PARTIAL，browser-inventory PASS / 46.840秒；browser-compat PASS / 227.217秒。源码清单仍全部相等。原完整full的AI超时保留、未定位，局部成功不覆盖原FAIL或拼接为默认八阶段Pass。未提交、推送、发布或新增生产请求，原83/90、7性能失败和整体OOM开放状态保持。

续跑自有backend正常关闭、实际退出-15；自有Vite进程组关闭、实际退出-2。收尾核验8024/5224无监听，未操作旧8013/5183。原失败清单和定向/续跑日志、绑定与summary分别保留。


## 2026-10-11 AI空白页有界基线对照与最终本地门禁

本轮新增真实人类授权为协调聊天turn`01a12914-b7fd-7023-b09b-88d3b0e4d17d`、human message`01a12914-b846-7f81-87a3-0ba16d2bf2fb`，明确要求定位AI空白并完成必要修复和完整门禁；范围仍仅自有副本/本地，不含提交、发布或生产访问。

对比已发布626对应4d9e后端与当前候选，前端AI/路由/能力发现源码完全相同，正常lifespan/full warmup、外部封面开启，沿用就绪同源runtime路径。每个版本限定一次原控件前序导航链和一次直接进入，桌面/手机均覆盖，共八个AI场景；导航链按原顺序/同一Chrome上下文，每次about:blank重置和45秒等待合同保持。原ready断言仍检查真实AI文本，本次诊断另确认`nav[aria-label="AI 洞察模式"]`实际挂载，不把导航栏AI链接当ready。记录CDP console/pageerror、所有请求及JS/静态响应、UI轮询时序、DOM、截图及对应后端/Vite日志。

八场景全部通过，实际导航开始到功能就绪511–598ms；基线前序链525/511、直接598/538ms，候选前序链528/511、直接596/533ms。八场景均没有pageerror、AI阶段failed request或HTTP错误，模块和runtime/settings请求正常；只读消费，无真实LLM生成调用。持久来源向量与周榜补修诊断后完全一致，两个版本测试源码清单均未变，自有进程已退出。证据为`backend-followup/ai-blank/{baseline,candidate}-receipt.json/comparison.json`及`output/playwright/detail-ai-blank/`四组events、DOM和截图。

未稳定再现历史AI超时，没有证据支持修改AI产品或就绪断言，未新增AI代码。此次排除的是有界正常启动对照中的候选必现回归、原导航链必现问题与“仅导航文本就算ready”；不能排除偶发JS模块/环境/导航竞态，也不能补写缺失的历史错误体。原失败只证明React导航shell出现而AI功能区未就绪，原因仍未知。共享node_modules/Vite缓存为已核实环境事实，但没有失败时的缓存/模块记录，不能认定其为根因。

根据这次明确授权及稳定有界对照，冻结1454应用/测试/脚本文件与七库Online Backup输入，再集中执行一次标准默认full八阶段。既有57响应、资源、专项8及压缩证据按未变源码范围复用。为避免再次失败时缺少证据，使用独立CDP observer只观察本次门禁拥有的control-inventory Chrome，记录AI挂载/错误/资源并截图；不改变标准脚本、断言、导航、等待或门槛，不额外发业务请求。本地冻结候选默认full八个必需阶段于2026-10-11全部通过，run`20261011T035817.979836Z-f647e7686469`、实际退出0、总状态PASS，耗时2330.890秒。原完整FAIL和局部Partial单独保留，不拼接结果。

| 默认完整必需阶段 | 结果 | 耗时秒 |
| --- | --- | --- |
| preflight | PASS | 8.023 |
| quality | PASS | 82.516 |
| backend | PASS | 1117.354 |
| api | PASS | 318.728 |
| browser-routes | PASS | 401.438 |
| browser-interactions | PASS | 83.728 |
| browser-inventory | PASS | 55.595 |
| browser-compat | PASS | 263.330 |

同轮后端种子3856通过/2skip、完整真实副本集成186通过/1skip，前端803通过/4skip及build/hooks通过；API51接口按原22次/热P95 500ms门槛通过，0慢项。路由/响应式矩阵、交互、控件/长列表、Chromium/Firefox/WebKit全部通过。原控件脚本中的AI桌面/手机均PASS。旁路observer实际退出0，pageerror/console error均0，AI阶段采集281个JS响应、HTTP错误和脚本加载失败均0；捕获到一次桌面root29/未挂载的加载中shell以及手机root83/已挂载状态。采样未捕获桌面就绪瞬间，桌面结论以原控件脚本PASS及先前有界功能挂载对照为准；相同shell可出现于正常短暂加载，但历史45秒为何未就绪仍未知，不恢复缺失因果。

源码前后1454文件SHA全部一致，七库Online Backup输入绑定保留，实际运行仍为已有ready runtime路径；正式库未参与。guard峰值1107891343B、最低剩余55788867584B，未触发限制、cleaned=true。自有backend正常shutdown、实际退出-15，Vite进程组退出-2，收尾8024/5224无监听；旧8013/5183未操作。完整日志、summary/JUnit/API与guard副本、binding及observer保存于`backend-followup/ai-fullstack-*`和`output/playwright/detail-ai-blank/fullgate-*`。

本轮只收口本地候选门禁，未提交、推送或发布，未新增生产访问、压力或重启。生产原83/90、7性能失败和OOM开放保持；后续候选审阅、提交/发布及生产自然首次分别取得明确授权。历史AI空白原因仍未确定，不能写成产品缺陷已修复；无需为未复现的问题添加AI行为改动。


## 2026-10-11 最终审阅与授权提交

真实人类授权来自协调聊天turn`01a12951-3aa6-7b63-8c19-ef31d0b45f44`、human message`01a12951-3aeb-7580-b6d3-72a8d9b12907`：“可以，你来验收这份补丁，通过后指示它们完成提交、发布和生产验收。”协调session核对18路径候选源码/补丁哈希及默认full同源结果，审阅来源事务、排名失效和预算，未发现阻塞；独立执行analysis_snapshots、playback_frame_budget、track_published_rank_context、closed_publication_source共63项通过，日志为私有`backend-followup/root-final-review-tests.log`。

本任务为唯一候选commit owner，只纳入已验收18路径及现有`docs/CHANGELOG.md`；原始数据、输出证据及其他session工作均不提交。README当前产品描述适用，AGENTS/CLAUDE一致且无需改规则；docs地图和当前交付状态同步。提交前执行文档审计、diff检查与项目hooks，应用/测试源码保持全门禁冻结哈希，纯文档收口不重跑39分钟门禁；提交SHA、父提交与精确路径保存在私有commit receipt及任务最终回复。

人类交付授权已生效，本提交交付冻结候选；联合整合、正常推送和正式发布由“排查榜单对决数据加载慢”session（`01a11bf5-d114-7b40-b133-716fd1e27cc1`）唯一执行。为避免并发生产探针，原FIRST90/资源/116/strict由该执行者单次执行，再由详情任务离线独立核对新release证据。当前没有新增生产请求或重启，626原83/90、7性能失败及OOM开放保持；正式发布与线上结果必须后续另行登记。


## 6dacfae7 正式生产首次验收（2026-10-11，OPEN/Partial）

沿用上述真实人类授权，由联合负责人将唯一候选commit `6dacfae7f293c9a8d5f9b6f573a5f39d5d84535c`（parent `4d9e0ba3277af976ee2a8e424706710b3686013a`）ff-only整合，19路径和1454应用文件与通过默认full8的冻结清单精确一致。正常push main实际退出0，05:07:33–05:07:40 UTC。发布前现成rank/detail/Billboard验证、导出、验证共九步全部0，4/4/48ready，源19事实及四库/WAL的inode、字节、mtime和SHA不变，零冷建/零源写入。三个清单上传600/哈希/原子更名通过；发布前可用11680022528B，高于保守晚阶段预算5189046272B，没有新清理。

[CI 38113788309](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38113788309)与[Release 38113788308](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38113788308)均attempt1 success，合计7实际jobs全部通过；Release含独立quality、full/showcase/dual三模式、images及安装114397441797。NoDeploy本次paths-not-triggered，不能套用626的三workflow/11jobs。正式安装按现有Online Backup、exact清单复用、source fence与联合回退流程成功；成功安装日志已保存，不称本轮执行了真实回滚演练。

独立8步实际核验退出0，三healthy且完整SHA一致，23个镜像源码文件和3个host helper哈希匹配固定commit；schema90/rank4/detail4/BB48ready。Backend container `bc9c15f93fa1d0f6d7e49e3308684a83e3b7f26446752862f78152da63c8f7d0`，image `sha256:bd09b2852961203bb96c012ce213f4d6f08246a0106e1d8ea3e78c31e0db1d01`，StartedAt `2026-10-11T05:35:54.152247887Z`，init3861235，host uvicorn3861278/startticks152013232。05:39:27 UTC启动维护自然结束，6323done/38历史failed，无pending/running；首轮前VmRSS970740kB，启动高基线单列。验收后仍为同一三container/config与真实uvicorn，无额外手动重启、预暖、强制GC或挑选重跑；私有入口未改，本次仅公开HTTPS。

原五个验收工具SHA保持，原90key与顺序、fresh contexts、正常PWA、production门槛及断言一致。浏览器窗口05:40:13.125412–05:46:04.321714 UTC；45点击core≤2000ms/all≤2500ms，45深链core≤3000ms、all从shell计≤2500ms。90完整完成，**79通过/11性能失败，生产仍Partial**：Chromium31/42、Firefox24/24、WebKit24/24；无pageerror、无非GET，12个屏外排名检查通过。相对626的83/7，5个原失败改善、9个原通过退化、2个原失败仍失败，净-4；保留历史与本轮失败，不以API通过替代性能通过。点击core最大2585.8ms/all2953.8ms，深链core最大5216.5ms/shell后all3007.1ms。

以下11项均Chromium；all使用对应原flow门槛口径：

| 实体 | 宽度 | flow | dynamic/merge | core ms | all gate ms | 同key变化 |
| --- | --- | --- | --- | --- | --- | --- |
| album | 900 | direct | true/L2 | 3868.5 | 1169.8 | 原通过→失败 |
| artist | 900 | direct | true/L2 | 3257.2 | 449.8 | 原通过→失败 |
| track | 1280 | direct | true/L2 | 3663.2 | 332.2 | 原通过→失败 |
| album | 1280 | click | true/L2 | 2585.8 | 2953.8 | 原通过→失败 |
| album | 1280 | direct | false/L2 | 3397.2 | 1507.4 | 原通过→失败 |
| artist | 1280 | click | false/L2 | 2496.7 | 2887.5 | 原通过→失败 |
| artist | 1280 | direct | false/L2 | 3202.5 | 458.5 | 原通过→失败 |
| album | 1280 | direct | true/L3 | 5216.5 | 3007.1 | 原通过→失败 |
| track | 1280 | click | false/L3 | 2581.2 | 2938.5 | 原失败仍失败 |
| track | 1280 | direct | false/L3 | 3545.3 | 397.0 | 原通过→失败 |
| album | 1280 | direct | false/L3 | 3436.9 | 1709.6 | 原失败仍失败 |

冻结请求时序显示多个失败的summary/overview `detail_service`本身约1.86–2.43秒，例如艺人900深链summary2053.306ms/overview2121.093ms，歌曲1280深链summary2344.495ms/overview2300.876ms；另有页面导航和请求外等待。证明服务路径延迟仍存在，不能归结为纯静态加载；本轮没有控制变量对照，不能直接认定共享预算/来源事务是退化原因，也不能称cold rank复用解决了整个详情路径。

自然90结束且浏览器关闭后才执行原公开116 API，108个200及8个未知404全部通过，完整响应/快照头/四album identity字段规范化沿原合同，source/filter fence与原owned事实一致。before→browser、browser→API、before→API三个strict v2读窗口全部退出0：57保护表、37原源、五队列表、搜索发布/FTS、全部aux与6侧库发布表、schema/epochs/fence/文件身份均守恒；access clocks零变化，各capture的7只读连接关闭。自然90与116分别报告，未在首轮前执行116。

50ms采样从服务基线READY先于浏览器启动，到全context关闭后10秒闲置观察结束；7279样本覆盖完整90窗口，实际最大gap53.22ms，collector凭token/PID/startticks仅停止自身并实际退出0。RSS947.988281→2308.484375→2006.082031MiB，PSS945.613281→2306.126953→2003.724609MiB，CPU147.77秒；相对626同90记录峰值约低199.594MiB、末驻留低192.168MiB，属于两次真实记录的观察差异，非单因素因果。384MiB只是宽表估算预算，**整体RSS/OOM仍开放**。cgroup全部OOM事件增量0；host available2115014656→1022005248B，host oom_kill累计1→1，未新增内核OOM，但仍有约2GiB驻留和主机压力。

私有证据目录为联合worktree的`output/versus-personal-acceptance/release-6dacfae7f293c9a8d5f9b6f573a5f39d5d84535c/`：push/九步/upload/workflow receipt、成功安装日志、8步运行核验与前后process identity，以及`first-production-detail/`内原90、资源、116、三guard与离线同key比较/失败时序。根清单`evidence-manifest.json` SHA256 `e3f7cdd17f1aaf4718085a9f0e0b94e34ce519f3b8e47203d609580f874444a9`固定此时证据；输出/真实数据不提交。详情任务仅离线独立核对，根仅同步交付文档，不另开生产热重跑。

下一步维持`SS-2026-10-09-001` OPEN/Partial与OOM独立OPEN。在同源就绪副本对上述失败请求分段定位来源revision、projection读取与服务排队/CPU，并对共享budget前后做有界相同顺序对照，再决定最小修复；先复用已保存trace，不追加生产预暖/重启/压力或循环部署。旧AI超时原因仍未确定，完整full8准入证据及其历史FAIL分列。本计划不归档，对决已完成状态不重开。

## 2026-10-11 专辑默认排名复用候选（本地完整验证通过，未发布）

以 `47b623f7dc2cae65dbf95de03452c7095e083aad` 文档、6dac 应用为基线，用户授权继续修复。隔离诊断确认：前端取消请求后，专辑完整排名仍会在后端继续计算并与后续榜单请求重叠。原76案例没有复现生产服务慢阈值，不能据此认定全部生产失败由排名引起。旧观察器未透传原生 LRU 的 `cache_info/cache_clear`；原执行文件和结果保留，修正版另存并通过缓存命中、清理和参数接口 smoke，后续回放使用修正版。

候选只修改 `entity_stats_service.py` 与专辑排名专项测试。默认主库 lifetime 四配置、项目归属齐备的专辑复用 exact-ready `entity_rank_context_v2`，其余实体统计按项目成员读取。历史详情 ranks/Top250 实际沿用 L2，因此保留该响应合同，L3 请求仍同时校验自己的精确发布和同源 L2 发布。Top250 从三个范围前250行涉及的候选 ID 展开成员、装载有界播放，再按原展示行排序截取，保留多艺人展示、source album 与第250行语义；不把前置合并上下文事件纳入候选。

兼容性验证发现种子库中 `Beta Hits Remix / Beta` 有项目身份但没有曲目归属。候选保留这类旧专辑的原匹配路径，避免误报 `found:false`；未建立 L1 关联的原曲目 ID 也保留。非默认过滤、自定义范围、非主库沿用原路径。精确发布缺失/漂移返回503，读取结束再次检查来源，不在 GET 上准备发布、写库或排队。

专项回归106项通过（27.76秒），覆盖完整响应、四配置、全局时间边界、零次数但非零时长、全部种子专辑、缺失/漂移503、Top250多展示边界、歌曲排名与公开读取合同。修复前的两个种子目录等价失败及一次测试路径拼写错误日志保留，不作为通过证据。最终源码真实副本和页面回放已完成如下；新默认完整八阶段门禁独立验收，旧6dac full8不替代新候选验证。

最终源码真实副本比较20份完整响应全部一致（五张专辑 × 四配置），基线和候选两个严格读取窗口各退出0，事实与发布守恒。Midnights L2动态/固定从7730.65/7681.02ms降至2813.21/2670.27ms，L3动态/固定从8062.68/8055.29ms降至1582.55/1574.29ms；这是直接 builder、顺序请求窗口，后续配置会复用进程缓存。该窗口峰值RSS基线1246.36MiB、候选683.47MiB，不代表普通启动完整页面窗口、单请求内存或生产OOM修复。证据 `album-rank-final/payload-comparison.json` 及两套原始完整响应、conservation收据保持独立。

修正观察器对基线/最终候选各执行一次 Chromium 连续原索引30–33（歌曲点击/深链、专辑点击/深链，1280px、L3动态），共8案例，均满足本地观测门槛。没有追加0–33前缀或循环热重跑。观察器SHA256为 `2c87d740bba1edec4b2a718d1394a5933f66cc13dbff9c29340a0a6066e6f45a`，原生缓存接口 smoke 另有收据。两次正常 lifespan 启动维护自然结束，四精确发布ready、active jobs为0；全序列不清缓存、不插入预暖请求。

原索引32取消后的完整专辑排名请求：基线总8986.57ms、thread CPU8375.63ms，取消后还运行8902.96ms；候选总3340.24ms、CPU3153.28ms，取消后仍运行3255.79ms。两者均与原索引33 overview重叠，不能称请求取消终止了后台工作。索引33 overview服务163.10→100.25ms、thread CPU43.57→38.24ms，singleflight等待均为0，页面核心1832.1→1707.2ms；此次未复现生产1.5秒以上服务慢阈值，不能把本地改善外推为生产性能Pass。

正常启动页面序列资源：基线RSS启动1358.69/峰1447.84/闲置1438.22MiB，候选1356.66/1356.80/1063.69MiB；整个观测窗口CPU27.97→21.90秒。请求50ms采样，实际最大间隔67.60/71.77ms；共享预算闲置305460701→198535816B，预算外闲置DataFrame列深层字节均为124。这是整个短序列窗口观察，非单请求64MiB或生产整体RSS证明。两个strict读取窗口全部守恒，公开请求写入/排队尝试为0，源码绑定未变，所有自有后端与浏览器/preview已关闭。原始事件、失败请求UTC、完整响应头、资源样本与派生对照见 `album-rank-final/actual-page/`。

新默认full8首轮 `20261011T070019.690377Z-85d74d5b9d4c` 实际退出1，preflight PASS（7528ms）、quality FAIL（15753ms）。mypy检查818文件成功，但执行时并行编辑了验收文档，pre-commit报告“files were modified by this hook”；业务源码绑定未变，不是类型错误。失败summary、完整日志与启动/关闭收据保留。冻结所有仓库文件后另存 `fullgate-v2/` 从默认完整模式重新开始；不使用 `--from` 或 `--only` 把首轮改称Pass。

第二轮 `20261011T070259.019703Z-5b55dbda3f27` 默认full模式实际退出1、1428782ms：preflight/quality/backend/api/browser-routes通过，browser-interactions在手机时间筛选失败，inventory/compat未运行，因此仍为Partial。3876后端种子通过/2skip、186真实副本通过/1skip，前端803/4skip及构建通过，API157正常/113边界、热P95基准通过；全部阶段源码绑定保持不变。失败为点击后未见 `data-mobile-sheet="time-range"`，无控制台/页面错误。原始summary、junit、基准与锁记录已复制到 `fullgate-v2/run-evidence/`，未覆盖首轮。

在未改动前端基线与47b后端上一次受控复现：暂扣真实200分析响应，加载中打开弹层；释放响应后KPI出现、原按钮断开、弹层消失。截图与DOM收据证明 `AnalysisStatsPage` 加载分支的时间控件迁入 `MobileAnalysisStats` 后重新挂载。记为独立 `SS-2026-10-11-001` OPEN/P2，本轮不修改该产品交互；这不是新专辑服务引入的前端变更，也不是性能测量。证据 `mobile-gate-diagnosis/`。

门禁 `mobile-time-filter` 原先只等待页面标题，可能点到加载分支。验证脚本现在等待初始 lifetime 响应完成且有KPI，或明确的同范围snapshot_unavailable UI，再执行已加载页面筛选；沿用原30秒数据等待、5秒弹层等待及应用后的last_4_weeks响应/URL/UI断言。ready/unavailable辅助判断默认仍为last_4_weeks，只显式为初始检查传lifetime；对应边界回归保留错误状态、未完成响应和缺少UI的拒绝。验证脚本及其现有专项测试是产品两文件之外的验收修正，未修改冻结的生产90案例观察器或性能阈值。

门禁专项18项通过（0.17秒），Node语法与Ruff检查通过；正常基线应用中单次手机时间筛选退出0，初始lifetime与应用后last_4_weeks均收到完整200并有实际KPI/正确URL。三场景诊断批次中时间筛选也通过，但栏目场景在关闭外部封面配置下有10个封面404，批次实际退出1，原样保留为Partial；单项成功不替代完整门禁。专辑产品文件的SHA未变，原20完整响应及8页面回放仍绑定同一产品候选。新的默认完整运行独立保存在 `fullgate-v3/`，正常外部封面配置与八阶段不缩减。

最终默认完整门禁 `20261011T073600.905084Z-f1483ad94de8` 实际退出0、overall PASS，1854478ms（30分54.48秒）。没有使用阶段切片，八个必需阶段全部同轮通过；optional未请求、NOT_RUN。以47b为HEAD的未提交候选绑定1455个代码/测试文件，含新专辑测试；起止SHA不变，专辑产品两文件与20响应/8页面回放绑定一致。

| 必需阶段 | 状态 | 实际耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 7947 |
| quality | PASS | 71471 |
| backend | PASS | 806874 |
| api | PASS | 194647 |
| browser-routes | PASS | 399168 |
| browser-interactions | PASS | 79438 |
| browser-inventory | PASS | 45569 |
| browser-compat | PASS | 249234 |

最终门禁：3876后端种子通过/2skip（416.99秒）、186真实副本集成通过/1skip（377.66秒），前端803通过/4skip及build，Ruff/格式/mypy/敏感信息检查通过；API157正常和113边界全通过、51接口热P95基准无500ms慢项；桌面/手机/多视口页面、图表/页签/筛选、控制清单及Chromium/Firefox/WebKit均通过。原失败手机时间筛选在本轮完整模式中通过。此Pass指本地完整全栈，不表示生产90首次性能或手机加载期间弹层状态已修复。

全部自有进程已关闭：backend SIGTERM退出-15，Vite进程组SIGINT退出-2，验证脚本实际退出0。完整summary、源码起止绑定、真实命令/日志、junit、基准和阶段锁保存在 `fullgate-v3/`；原run目录14个证据文件另复制到 `fullgate-v3/run-evidence/`，不依赖临时目录保留。前两次完整模式失败和诊断批次404保持，不作热重跑抹除。

私有证据位于本工作树 `output/music-detail-chart-acceptance/backend-followup/album-rank-final/`；先前候选试验保存在独立 `album-rank-followup/`，原76诊断和生产6dac证据不覆盖。所有真实数据及输出均不提交。协调独立验收已通过，用户授权本次11路径提交，正式推送/部署/生产FIRST90交唯一联合负责人；本任务生产请求为0。`SS-2026-10-09-001`继续OPEN/Partial，生产首次90与整体OOM独立验收；`SS-2026-10-11-001`加载时弹层关闭仍OPEN。

协调独立复核11路径/补丁hash、最终v3八阶段与1455源码起止绑定均通过，并独立运行专辑、歌曲排名及门禁脚本测试30项通过（19.85秒），文档include-archive251份与diff检查通过。产品/测试源码未再修改，仅同步本次授权提交状态。权威最终PASS入口为 `fullgate-v3/fullstack-summary.json` 和 `fullgate-v3/fullstack-binding-after.json`；根目录同名文件仍为第一次FAIL历史，禁止覆盖。额外只读入口索引为 `evidence-entrypoints.json`，提交后的SHA/parent/精确路径及hooks结果另存 `commit-receipt.json`，不将正式提交等同生产已验收。


## ea93c476 专辑排名正式生产首次验收（2026-10-11，OPEN/Partial）

真实人类协调turn `01a12a27-2781-7523-a0c2-c7f8632d6b84`、message `01a12a27-27a7-7d20-bb2a-7259bae6f731`要求“继续下一步”，沿用验收通过后提交、正常推送、正式发布和生产验收的完整交付授权。详情为唯一commit owner，提交 `ea93c476fc8c8e0584aad7419d5dc77504798cc7`，parent `47b623f7dc2cae65dbf95de03452c7095e083aad`；联合发布负责人ff-only整合精确11路径，未重复创建产品提交。1455应用/测试/脚本blob及整合文件逐项与最终`album-rank-final/fullgate-v3/`绑定相同，run `20261011T073600.905084Z-f1483ad94de8`为默认full八必需阶段PASS/实际0、1854478ms。根目录旧summary/binding为首轮历史FAIL，未改写或拼接；协调独立30项回归和本地20完整响应/8回放/4strict保持本地层证据。根全量文档237篇Pass，详情251篇为其工作树额外文档计数，分别报告。

发布前现成rank/detail/Billboard九步verify/export/validate全部0，rank4/detail4/BB48ready；19源事实与原baseline相同，四库/WAL内容、inode、mtime和SHA不变，零冷建/零源写。三个固定SHA清单600/哈希/原子上传通过。服务器schema90、6dac healthy、6323done/38历史failed、无active；可用磁盘10836385792B，高于保守副本/侧库预算4487634944B，MemAvailable1142833152B高于正常search-reuse640MiB门槛。没有新删除清理。正常push main08:59:02.138015–08:59:05.754574 UTC实际0。

[CI 38126733431](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38126733431)与[Release 38126733487](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38126733487)均attempt1 success，7实际jobs全部通过，包括独立质量、full/showcase/dual三模式、镜像及安装114434996951；NoDeploy本轮paths-not-triggered。现有Online Backup、search4精确复用、rank/detail/BBready及source fence/健康/联合回退流程实际安装成功；保留现版和上一版回滚材料，不称本轮执行过真实回滚演练。成功安装日志与actual workflow/job结论均保存。

独立8步运行核验实际0，三healthy且完整SHA一致，23个镜像源码文件及3个host helpers哈希匹配commit；schema90/rank4/detail4/BB48ready。Backend container `0293353fd95276bdccfc7518cc9e4048d48e3ede213ba93f9aa7b86cdf831c13`，image `sha256:8bfd9d5c756299ff46de64473da1d653c56e9a7c5541721996cb38150170ed63`，StartedAt `2026-10-11T09:20:03.470858386Z`，init4082701，真实host uvicorn4082742/startticks153358164。09:23:32UTC启动维护自然结束，6333done/38历史failed，无pending/running；前VmRSS981520kB。验收全程相同三容器/配置与uvicorn，未额外手动重启、强制GC、预暖或循环部署；私有入口现状保持，仅公开HTTPS。

原五工具哈希未变，原90key/顺序/production门槛/断言、fresh contexts与正常PWA全部保持。自然浏览器窗口09:24:16.465907–09:29:32.010190 UTC，45click core≤2000ms/all≤2500ms、45direct core≤3000ms/all从shell计≤2500ms。90完整完成，**86通过/4性能失败，仍Partial**。Chromium38/42、Firefox24/24、WebKit24/24；45点击全部达标，点击core最大982ms/all1645ms，深链core最大4817ms/shell后all2809.6ms。无pageerror/非GET，12屏外排名检查通过；原控件/图表/filter/unknown等合同按原完整本地门禁与后置API分层保留，未修改生产90阈值或缩短覆盖。

| 对照版本 | 原通过数 | 原失败→本轮通过 | 原通过→本轮失败 | 本轮通过数 |
| --- | --- | --- | --- | --- |
| 6dac | 79/90 | 7 | 0 | 86/90 |
| 626 | 83/90 | 6 | 3 | 86/90 |

本轮4失败均为Chromium专辑direct；相对6dac均原失败继续失败，相对626有3个原通过变失败、1个原失败保持。旧83/7、79/11与本轮86/4分别保留，不把其中任何一次性能结果改成Pass。完整逐key差异在私有`offline-assessment.json`。

| 原index | 宽度 | dynamic/merge | core ms | shell后all ms | 失败 |
| --- | --- | --- | --- | --- | --- |
| 15 | 900 | true/L2 | 4248.6 | 1627.6 | core_latency |
| 27 | 1280 | false/L2 | 4086.3 | 2339.8 | core_latency |
| 33 | 1280 | true/L3 | 4817 | 2809.6 | core_latency/all_visible_latency |
| 39 | 1280 | false/L3 | 4634.9 | 2780.1 | core_latency/all_visible_latency |

原失败请求时序仍显示专辑summary解析身份后请求overview：index15 summary service1390.789ms、overview1033.429ms；index27为510.940/1208.013ms；index33为906.474/1144.552ms；index39为754.428/1892.783ms。overview请求总等待1165.6/1959.88/2424.03/2336.38ms，存在请求外/传输等待与串联。详情独立离线复核确认这四例均未发起完整个人排名，但各自前一个点击场景取消过排名请求；生产记录未包含被取消的后端计算结束时间，跨场景争用仅为待验证假设。说明首屏链路还有服务和浏览器等待；单轮未控制来源、网络及取消rank时序，不可认定全部由排名、预算或导航造成，也不能用本地取消rank9→3.3秒当生产因果结论。下一步优先复用这四例已有trace和正常点击对照，详情任务仅离线复核并提出有界副本诊断。

### ea93 同源副本四场景分段诊断（2026-10-11，生产仍 Partial）

按继续授权完成一次有界副本诊断。独立工作树先 ff-only 吸收文档提交 `f76e60a3`，产品仍为 `ea93c476`；人工主工作区及已有忽略证据未写入。使用原 ready runtime 的相同绝对路径、七库 Online Backup 恢复材料、正常 lifespan/full 启动并等待队列归零；只顺序回放原 index **32、33、38、39，各一次**。原 Chromium/1280/L3/dynamic 与 fixed 参数、fresh context、PWA allow、性能门槛与断言不变，没有场景间清缓存或额外预暖。没有回放 0–31 前缀及 34–37 中间场景，因此这是局部诊断，不能复现生产整轮缓存历史。

输出专用观察器保留原调用和返回，转发原缓存的 `cache_info/cache_clear/cache_parameters` 等接口。实际 AST 抽取烟测确认同 key 两次调用只构建一次，clear 后才重新构建；普通 measured wrapper 也转发缓存接口。观测 route identity、服务子阶段、依赖/线程调度、SQL execute/fetch、响应模型序列化、JSON render、ASGI send 及浏览器资源阶段。冻结浏览器脚本未修改；增加的观察均在忽略目录的独立 runner。观察器有时间和记录开销，其 wall/CPU 是本地诊断量，不能代替生产测量。

四例实际执行成功且均达原门槛：32/38 点击 core 为 **118.1/151.7ms**，33/39 深链 core 为 **2284.1/1761.1ms**、shell 后全部可见为 **1632.8/788.1ms**。未复现生产超过 3000ms 的深链失败。

| 原 index | 导航→summary 发起 ms | summary 浏览器等待 ms | summary 完成→overview 发起 ms | overview 浏览器等待 ms | overview 完成→核心渲染 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 33 | 469.31 | 505.31 | 8.42 | 1254.33 | 46.73 |
| 39 | 426.00 | 848.99 | 8.67 | 430.48 | 46.96 |

以上采用浏览器同一 performance time origin 和 request timing，避免把创建 context 的时间计入导航。summary 确实完成后才发起稳定 project-ID overview；深链自身均没有 `include_rank_context=true` 请求，不能描述为 overview 等待自己的排名。

| index / view | ASGI 到 endpoint 开始 ms | route 身份解析 ms | detail service wall / 线程 CPU ms | 其中有效曲目数读取 wall ms | endpoint 后到 ASGI 完成 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 33 summary | 61.76 | 9.41 | 407.33 / 44.14 | 294.89 | 4.59 |
| 33 overview | 323.59 | 95.70 | 768.83 / 75.62 | 491.07 | 32.30 |
| 39 summary | 76.50 | 94.74 | 673.63 / 41.63 | 488.50 | 5.12 |
| 39 overview | 205.96 | 114.51 | 104.10 / 39.89 | 26.82 | 3.16 |

route 身份解析包含 stable-ID 解析及现有 L3 preferred-scope 校验的第二次姓名解析；没有跳过校验。33/39 overview 的 BillboardFilters 依赖分别 wall **193.42/171.82ms**、线程 CPU **4.07/3.82ms**，最大单次 dispatch 等待 **32.54/22.34ms**。响应模型序列化最大 **5.65ms**，JSON render 最大 **0.39ms**，该四个请求观测到的 singleflight 等待为零。ASGI 到 endpoint 的时间还包含其他依赖及调度；不能只称线程池排队。浏览器等待减服务时间也不能只称网络等待。

服务内主要重复工作是 `project_unique_song_count → _components → load_detail_source_facts`：summary 和 overview 均读取、校验目标来源事实并组装 DataFrame、补艺人等信息，再只取 canonical song 唯一数。33 overview 的原始来源事实 fetchall 为 **217.72ms wall / 2.44ms 线程 CPU**；39 summary 为 **312.18 / 3.83ms**。SQL、身份和服务阶段相互嵌套，不能把耗时直接相加。wall 远高于线程 CPU 说明时间大量落在该线程未执行 CPU 的区间，但本次没有做因果控制，无法进一步区分 GIL、操作系统调度、I/O 或其他等待，也未证明 SQLite 锁是根因。

取消后的后台工作在副本上得到直接确认：32/38 的排名请求浏览器均 `net::ERR_ABORTED`，后端分别 **4598.06/3518.81ms** 才完成，endpoint 线程 CPU **3678.83/3269.66ms**；浏览器 abort 后仍运行 **4528.20/3415.65ms**。两个排名任务分别覆盖了随后 33/39 的整个 summary 和 overview 请求区间。该事实证明副本中的取消请求继续计算及重叠，支持后续针对来源读取和 CPU 争用排障；生产仍缺对应后端结束 trace，不能据此宣称四个线上失败的全部因果已经确认。

读取前后独立 strict 为 PASS：57保护表、37原始表、队列、发布表、全部6侧库、schema90、epochs/source fence 与七库文件身份全部相同，无 access-clock 漂移，无公开请求写入/排队尝试。runner 实际退出0，尾部等待后无未完成统计请求，后端/preview 正常关闭，8025/5225端口关闭；产品 backend/frontend/scripts 与 f76 无差异。

资源记录覆盖正常启动、四场景、尾部及守恒采集，目标50ms，1006样本、实际最大间隔 **106.134ms**；RSS 启动 **1342.969MiB**、峰值 **1390.906MiB**、idle **1370.0MiB**，全该窗口 CPU **27.680秒**。缓存估算由326135446B到392273249B，不能当RSS上限。本机 Darwin/10逻辑CPU/24GiB，与保存的生产 MemTotal3904073728B、原90前缀和外部HTTPS环境不同；生产CPU配置未记录，不推断为某个核数。已有 Docker desktop context 无运行中的 daemon，未安装或启动新环境，因此 Linux 受限对照 NOT_RUN。本次不新增生产请求、重启、发布或完整90热重跑，整体OOM仍独立OPEN。

**最小后续建议**：优先缩减已测得的有效曲目数来源读取重复工作，考虑在相同只读事务和已验证 membership/source-check 上进行有界批量读取与计数，避免为一个数字完整组装、补元数据的 DataFrame，并减少逐行 SQLite→Python 往返。必须保留 source-check、metadata join 过滤语义、canonical key、stable-ID/L3 scope/别名/歧义404、缺快照503、同 source/filter publication 和完整响应等价。仅改 identity 重复解析不能解释本轮主要耗时；本次也没有证据支持直接改为前端并发。当前只形成诊断与建议，**产品改动0，不重跑full8，不宣称新修复**。后续实现前先固定该最小读取合同；候选须完成相关边界回归、同源完整payload/strict/资源专项，专项通过后才冻结并执行一次默认完整full8。

私有原始证据：`output/music-detail-chart-acceptance/backend-followup/album-direct-critical-path-diagnosis/`。入口为 `diagnosis-receipt.json`、`critical-paths.json`、`observer-smoke.json`、`source-bindings.json`；四例 browser、全部阶段 events、严格前后采集及资源样本在 `original-pairs-current/`。旧生产证据和历史FAIL全部保留。

### 有效曲目数轻量读取候选专项（2026-10-11，未提交/发布）

收到真实人类“继续下一步”的实施授权后，仅修改 `detail_project.project_unique_song_count` 和投影计数来源 helper。原 membership DataFrame/有效 payload 校验继续保留；目标 L1 的全部原始日/周来源事实以一份 JSON 读取，来源检查 payload 与 digest 以一份 JSON 读取，按每个目标分别验证原 `source_check` 行数、plays、total_ms 和完整 digest。随后只读取有有效事实且通过原 representative track/artist inner join 的 L1 集合，按原 membership canonical song key 去重。时长独立贡献、未播放成员、空 membership、L1兼容零值和来源过滤均保持。未增加缓存、迁移、发布字段或版本，不跳过 source-check、身份或外层发布校验；完整项目解释仍使用旧 `_components`，未改前端、取消机制、AI、对决或手机弹层。

相关单元/接口合同首次 **98项通过（6.28秒）**，包含身份/别名/歧义、详情分视图、分页、公开快照边界；新增计数/投影边界最后 **42项通过（0.14秒）**，覆盖四默认配置、两个版本同 canonical song/不同 song、duration-only、来源专辑差异、元数据 inner join 缺失、来源丢失/权重/归属修改、缺校验/坏digest/非法JSON、stale/source/version drift、逐成员校验、兼容空校验及未请求目标的隔离。计数与旧 `_components` oracle 相等，并断言计数不调用 `pd.read_sql_query`、不产生写入。Ruff check/format 与 diff 检查通过。

同源相同路径 ready 副本上，以 f76/ea93 原后端为 baseline、仅覆盖产品两文件的候选为对照，完整 ASGI 响应 **60/60 canonical payload及status相等**：五专辑×四配置×summary/overview/project，54个200、6个既有503。`1989 (Taylor's Version)` L3 动态/固定三视图在基线即503，候选原样保留，没有将 unavailable 当成功200；独立稳定身份读取确定project ID，没有按名称猜ID。20组原计数 oracle全部相等，计数本身均200。初次 harness 假定所有样本200因该既有503而退出1，原日志和不完整响应保留在根 `baseline/`；正确的状态/body完整对照独立保存在 `payload-v2/`，没有覆盖失败材料，也未新增正式维护或重建。

| Midnights配置 | canonical song数 | baseline→候选计数 wall ms | baseline→候选线程CPU ms | SQL calls | 来源DataFrame组装 |
| --- | ---: | ---: | ---: | --- | --- |
| L2动态 | 23 | 18.18→5.60 | 18.03→5.58 | 55→6 | 1→0 |
| L2固定 | 23 | 19.77→5.38 | 19.54→5.35 | 55→6 | 1→0 |
| L3动态 | 21 | 21.06→5.92 | 20.74→5.73 | 77→6 | 1→0 |
| L3固定 | 21 | 23.94→6.27 | 23.57→6.21 | 77→6 | 1→0 |

20组计数 wall 合计305.45→96.68ms，候选各组来源DataFrame组装均0。这里是无lifespan的ASGI/直接计数oracle，不能替代正常启动页面或生产首次证据。

修正观察器 native cache API 烟测通过，两版本各正常启动/队列归零，按原32→33、38→39各回放一次。四场景 key/顺序/PWA/fresh/门槛不变，场景间无清缓存/额外预暖，原0–31/34–37未扩展。baseline/候选产品两文件绑定一致，全部原断言通过。

| 原index / flow | baseline core ms | 候选 core ms | 结果 |
| --- | ---: | ---: | --- |
| 32 / click | 132.5 | 135.4 | 两者达标；候选增加2.9ms |
| 33 / direct | 1992.0 | 734.1 | 两者达标；候选减少1257.9ms |
| 38 / click | 106.1 | 382.6 | 两者达标；候选增加276.5ms，保留退化 |
| 39 / direct | 1825.8 | 641.1 | 两者达标；候选减少1184.7ms |

33 summary/overview计数 wall **203.13/140.07→10.16/15.47ms**；39为 **173.94/132.37→8.32/11.66ms**。33服务wall **312.76/401.94→30.30/58.67ms**；39为 **261.07/373.69→27.59/43.57ms**。计数线程CPU约24–29ms→8–14ms。候选减少了测得的服务段及此局部序列的深链等待，但本地两版本均未复现生产3秒失败，不宣称四线上FAIL已修复。

必须同时保留资源限制：两版本正常启动、四场景、尾部和采集窗口的RSS启动/峰值/idle分别 **1347.422/1374.813/1354.656→1366.234/1372.563/1222.844MiB**；全窗口CPU **28.020→35.316秒，增加7.296秒**，不称整体CPU改善。目标50ms采样，实际最大间隔74.773/89.671ms。取消排名32/38的 wall **3763.92/3577.71→7221.37/6289.47ms**、线程CPU **3552.75/3295.16→6215.16/5341.49ms**，候选仍继续计算并与下一页重叠。两版本冷frame构建key集合完全相同、无观察器重复构建/缓存clear；更快页面改变自然并发时序，尚未做控制实验，不能将增加全部归因于计数补丁、某个锁或预算。本补丁未改排名取消机制，整体OOM继续OPEN。

两个payload窗口及两个正常启动browser窗口，共四个独立strict全部通过：57保护/37原始/队列/发布/6侧库/schema90/epochs/fence/七库身份不变，无公开写入/排队尝试，所有请求最终结束，自有服务已关闭。采集中的正常启动维护在各窗口前自然结束，不能把跨启动当单一strict窗口。生产请求/重启/发布为0。

专项完成后将冻结当前候选从头执行一次默认full8；尚未以旧fullgate-v3覆盖本候选。完整证据在忽略目录 `output/music-detail-chart-acceptance/backend-followup/count-source-final/`：`payload-v2/payload-comparison.json`、`browser-comparison.json`、`actual-page/observer-smoke.json` 与各原始响应/events/strict/sample/log；完整门禁单独置于 `fullgate/`，完成后登记run、实际退出和源码起止绑定。

### 计数轻量读取候选默认完整验收完成（2026-10-11，待协调审阅）

专项通过后冻结的候选仅执行一次默认完整full8：run **`20261011T102216.614157Z-bc0c921c926f`**，实际退出 **0**，overall **PASS**，**2092445ms（34分52.445秒）**。以f76为HEAD的未提交候选，正常lifespan/full维护自然归零后开始；八个必需阶段同轮通过，没有`only/from`切片。optional未请求，NOT_RUN。1455个应用/测试/脚本文件起止绑定未变，产品两文件与60完整响应/20计数oracle及双版本四场景绑定一致；门禁结束后只更新交付文档，不再改产品或测试。

| 必需阶段 | 结果 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8305 |
| quality | PASS | 108211 |
| backend | PASS | 1011322 |
| api | PASS | 245411 |
| browser-routes | PASS | 399300 |
| browser-interactions | PASS | 79828 |
| browser-inventory | PASS | 45857 |
| browser-compat | PASS | 194043 |

本轮后端种子3900通过/2skip（487.81秒）、真实副本集成186通过/1skip（501.85秒），前端803通过/4skip及build；Ruff/format/mypy/密钥扫描通过。API157正常及113参数边界全通过，51接口22轮共1122样本热P95无500ms慢项；桌面/手机、多视口、音乐详情、页签/筛选/控制清单和Chromium/Firefox/WebKit均通过。手机时间筛选验证已加载页面原最终断言，独立加载弹层旧缺陷保持OPEN。该Pass是本地完整全栈，不是新生产FIRST90或整体OOM验收。

自有backend SIGTERM退出-15、Vite进程组SIGINT退出-2，均关闭。权威文件为 `count-source-final/fullgate/fullstack-summary.json`、`fullstack-binding-before.json`、`fullstack-binding-after.json` 和完整命令/日志；原run目录14份JSON/XML另保存在 `fullgate/run-evidence/`，入口清单为 `run-evidence-index.json`。证据归档准备时误复制了最终测试文件到副本测量的源码归档，已按测量时记录哈希恢复两个原测试版本，产品两文件及全部测量输出未变，修复记录为 `archive-test-recovery.json`；当前最终42测试版本由新full8的起止绑定覆盖，未改写旧测量记录。

可审核范围为两个后端产品文件、一个既有测试文件及七份必要文档；补丁/精确路径/最终检查和证据入口保存在 `candidate-review-receipt.json` 与 `candidate.patch`。当前尚未git提交、推送或部署，也无新生产请求/重启。交唯一协调负责人审阅，再按已有授权决定整合发布及原FIRST90；生产保持ea93 **86/90、OPEN/Partial**。候选四场景的取消rank和全窗口CPU增加如实保留；局部计数/深链改善不关闭整体OOM，手机弹层仍独立OPEN，旧失败材料不覆盖。

### 发布前串行CPU对照与提交准入（2026-10-11）

协调独立审阅42项投影/计数回归、10路径/patch/fullgate1455起止及当前绑定、source-check完整digest/逐成员/inner join/canonical key/同事务合同后，要求补做一次有界串行CPU对照。只使用相同路径的现成ready副本，两版本各一次正常启动/维护归零，按 **L3动态summary→overview→完整rank，L3固定summary→overview→完整rank** 固定顺序执行；每个真实后端请求结束后才开始下一个，共每版6请求，没有取消或后端重叠。不回放浏览器/PWA/base-stats预取，不修改产品源码，不重跑full8或原90，不清缓存/额外预暖。startup和strict采集与请求CPU窗口分开。

沿用两版相同观察器，native cache API烟测通过；增加艺人映射阶段观察，未调用会枚举GC/referrer的memory snapshot。明确请求窗口为动态summary发起前至固定完整rank结束检查后，包含两版对称的完成记录读取；其wall **6801.16→6641.99ms**、进程CPU **6.426825→6.349098秒**，约减少1.2%。startup单列：wall20759.70→17838.09ms、进程CPU17.034596→16.720865秒，不能并入请求窗口或归因计数补丁。

| 请求 | baseline→候选wall ms | baseline→候选进程CPU ms | baseline→候选endpoint线程CPU ms |
| --- | ---: | ---: | ---: |
| L3动态完整rank | 3284.96→3271.07 | 3050.68→3066.35 | 3036.71→3051.32 |
| L3固定完整rank | 3014.05→3029.17 | 2996.38→3010.67 | 2983.30→2996.98 |

单次rank CPU约增加0.5%，本次串行控制未复现原四页序列的显著增加。计数wall：动态summary/overview **20.48/18.02→5.23/4.31ms**，固定 **18.08/18.00→5.76/4.06ms**；其线程CPU也下降。两个rank每版都各有 **2个冷frame miss/build**，四个构建key和调用次数逐项相同，无重复构建/缓存clear。rank中的`get_artist_identity_map`两版均各5次，合计线程CPU动态10.97→11.51ms、固定11.25→11.46ms。旧计数在每个summary/overview中额外调用该函数一次，候选计数不调用；该函数本身每次重建映射、没有Python/native cache，未发现旧计数预热了rank的对象缓存或减少frame构建。仍不能唯一控制或排除OS/SQLite页缓存等更细影响。

6完整响应canonical payload/status相同，两个独立strict窗口57/37/队列/发布/6侧库/schema/epochs/fence/七库身份全守恒，零写入/排队尝试，六后端请求严格不重叠且无disconnect，实际脚本退出0。全部自有backend正常SIGTERM退出-15，8025关闭。两版请求窗口RSS起止分别1351.984/1363.281→1354.016/1366.359MiB，含启动和采集的峰值1384.641→1386.328MiB；这里只是串行副本观察，不是原并发或生产资源PASS。产品/最终测试三文件哈希未变，原默认full8继续绑定；原四页CPU28.020→35.316秒、点击38退化、取消任务继续计算、线上ea93 86/90以及OOM/手机OPEN全部保留。串行结果支持继续按不同执行时序或并发条件核验该差异，不能证明GIL/调度是唯一原因或线上四失败已修复。

原始证据在 `count-source-final/serial-cpu-control/`：`comparison.json`、`batch-receipt.json`、`observer-smoke.json`、`control.log` 与两版receipt/events/完整payload/strict/sample。协调已独立核对该对照和前述完整验收，批准沿已有用户授权提交本轮原10路径；本任务为唯一commit owner，只提交，不push/部署/新增生产请求，统一发布交原联合负责人。README/AGENTS/CLAUDE通用约定不需改，docs地图/CHANGELOG/reference和状态按本轮事实同步，提交SHA/父SHA、精确路径、源码绑定及实际hooks另登记在忽略目录 `commit-receipt.json`。

自然90全部context关闭，读取守恒校验通过后才执行原116 API：108个200+8个未知404全部通过，完整payload/快照头/四album identity规范化和原固定source/filter fence沿既有合同。before→browser、browser→API、before→API三个strict v2窗口全部0：57保护表、37原始表、5队列表、搜索发布/FTS、全部aux、6sidecar发布表与schema/epochs/fence/文件身份守恒，access clocks零变化，三次capture各7只读连接关闭。API功能Pass不替代性能Partial。

50ms资源窗口09:24:16.328942–09:29:44.384668 UTC包含全部90及浏览器结束后10秒idle，6562样本、实际最大gap53.026ms；sampler在READY后才开始浏览器，只用绑定token/PID/startticks停止自身，actual0，没有向后端发送信号。RSS958.515625→1461.449219→1461.187500MiB，PSS956.179688→1459.113281→1458.851562MiB，CPU74.34秒。相对6dac同90的RSS峰2308.484375/末2006.082031MiB，分别低847.035156/544.894531MiB，CPU147.77→74.34秒；这是两轮实际记录差异，不作单因素对照因果。cgroup全部OOM事件增量0，host available2163912704→1583079424B、host oom_kill累计1→1。但idle仍约1.43GiB驻留，384MiB只约束宽表估算缓存，**整体OOM继续独立OPEN**，未以这一轮无OOM关闭资源问题。

生产冻结证据在联合工作树私有`output/versus-personal-acceptance/release-ea93c476fc8c8e0584aad7419d5dc77504798cc7/`：唯一候选/1455fullgate整合收据、九步/readiness/上传/push、workflow/job/成功安装日志、8步verify与startup/前后identity，及`first-production-detail/`下原90、50ms样本、116、三guard、两版逐key比较与四失败时序。`evidence-manifest.json` SHA256 `cfbcd109c5e142a05547d2a8648e2b5c263ea8e4f81d06aaac997ca7907b63f9`固定此时证据；原始数据/输出不提交。协调及详情接收此冻结证据仅离线核对；根随后只同步六份交付文档，文档提交不作为新运行版本，不再发生产请求。

`SS-2026-10-09-001`继续OPEN/Partial，`SS-2026-10-08-001`整体OOM与`SS-2026-10-11-001`手机加载弹层问题各自OPEN。本轮专辑补丁已上线，不能称全部详情性能收口。下一步唯一研发负责人为详情任务，先离线复核四个专辑深链/正常点击时序，再在同源ready隔离副本分段定位summary身份解析、overview服务/排队及取消rank重叠，形成最小待审核候选；本发布任务保持对决研发收口，不新增生产预暖、热重跑、重启、清理或部署。当前计划不归档，历史AI/门禁失败继续分列。


## 4f3f2ac0 计数轻量读取正式生产首次验收（2026-10-11，OPEN/Partial）

详情为唯一产品commit owner，提交 `4f3f2ac0436ba6556bc3ca90773860e18cd9dc77`，parent `f76e60a3d345a7cf89f5cf9960edbff3affd9b59`，精确两个后端产品文件、一个测试文件和七份文档，共10路径。根按既有用户完整交付授权ff-only整合；1455个commit blob和整合文件与`count-source-final/fullgate/`起止绑定全部相同，默认完整run `20261011T102216.614157Z-bc0c921c926f` 八必需阶段同轮PASS、实际0、2092445ms。3900种子、186真实副本集成、前端803及三浏览器属于本地门禁；协调独立42项回归通过；详情提供的60完整响应/20计数、原四场景及串行每版6请求证据保持分层。原并发CPU28.020→35.316秒、取消rank增加与串行6.427→6.349秒并存，不能用串行控制宣布并发/OOM已解决。详情docs256与根docs237分别是对应工作树全量计数。

发布前仅只读核验：生产ea93三healthy、schema90、6333done/38历史failed且active0，19源事实与原baseline完全相同，rank4/detail4/BB48ready；MemAvailable1399111680B，可用磁盘9843843072B高于保守预算4526792704B。固定SHA现成快照九步verify/export/validate均0，源四库/WAL内容、inode、mtime和哈希不变，零冷建/零源写；三清单600/哈希/原子上传实际0。正常push main实际0；首次内联远端确认断言失败，未保留该次返回码/输出，不判定原因；随后一次独立只读ls-remote实际0确认精确SHA，无重复push。原始异常保留在交付记录。

[CI 38140719684](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38140719684)和[Release 38140719661](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38140719661)均attempt1实际success，共7jobs通过，包括三部署模式、镜像和正式安装114476731493。现有Online Backup、精确ready/source fence、健康与联合回退合同完成正常发布；保存成功安装日志，不称本轮执行过真实回滚演练。NoDeploy为paths-not-triggered。独立8步runtime实际0：三容器完整SHA/healthy一致，25镜像源码和3host helpers哈希匹配，schema90/rank4/detail4/BB48ready。启动维护自然结束，6343done/38历史failed、active0；backend `4a6a7fa581e0df8e79865580c6c708e433a5812d3642be2df53856c60c743783`、image `sha256:69ca984889aa8bebad9ea934c0b3518e94238919ef0f1994468c85af0835fd76`，StartedAt `2026-10-11T13:13:06.235382695Z`、host uvicorn118850/startticks154756440。只验公开HTTPS，私有入口现状保持，无额外手动重启、GC、清理或统计预暖。

原五工具哈希、90key/顺序/断言、fresh contexts、正常PWA及原production阈值保持：click core2000ms、direct core3000ms、all2500ms（direct all从shell计）。唯一首次窗口`summarize_natural`确认完整 **89通过/1性能失败，仍Partial**；Chromium41/42、Firefox24/24、WebKit24/24。45click全部达标，点击core最大1114ms/all1496ms，direct core最大3125.1ms、shell后all最大1638.3ms。pageerror0、非GET0、12屏外排名检查通过，没有热重试覆盖FAIL。浏览器原始UTC窗口为`2026-10-11T13:17:54.134889+00:00`至`2026-10-11T13:23:04.763239+00:00`。

| 对照版本 | 原通过数 | 原失败→本轮通过 | 原通过→本轮失败 | 本轮通过数 |
| --- | --- | --- | --- | --- |
| ea93 | 86/90 | 3 | 0 | 89/90 |
| 6dac | 79/90 | 10 | 0 | 89/90 |
| 626 | 83/90 | 6 | 0 | 89/90 |

剩余原index39：Chromium/1280px/专辑direct/固定阈值/L3，core3125.1ms超过原3000ms门槛，shell后all1638.3ms通过。原summary请求wall747.19ms/service197.592ms，随后overview wall1258.91ms/service969.220ms；保留串联和请求外等待事实，不把单轮125.1ms超额归因网络、调度或取消rank。该例在ea93为4634.9ms，但仍不能改为Pass。本地候选快速结果和生产旧83/7、79/11、86/4、本轮89/1分别保留。

浏览器关闭后原资源采样继续10秒idle，只用绑定token/PID/startticks停止自有采集器，actual0；之后浏览器strict通过才执行原116 API，108个200+8个未知404全部通过，完整payload/快照头/四album identity规范化/source和filter fence不变。before→browser、browser→API、before→API三strict v2窗口均实际0/all true：57保护表、37原始表、5队列表、搜索发布/FTS、所有aux和6sidecar发布表、schema/epochs/fence/文件身份守恒；access clock变化为空，每次七只读连接关闭。

**原验收wrapper最终实际退出1，原始失败保留。** 所有90/116/strict/资源和after-runtime步骤已取得原始输出，最后`containers/config`整体digest断言失败；原`execution-receipt.json` SHA256 `c2c4adb62834878461b7e29a1b123edf4a0dcebc7f38a85b763cfae049bed5d6`含AssertionError，没有改写成complete/exit0。验收前后全部container ID/image/revision/starttime/init和真实uvicorn PID/startticks相同，仅backend及public-web配置整体digest不同。随后唯一一次只读inspect在相同当前Config/HostConfig及完整Mounts元素下枚举挂载列表排列，三个容器都精确重现前后两个原始digest；backend2挂载/public-web3挂载，证明差异仅为Docker返回列表顺序。补证`identity-order-diagnostic.json` SHA256 `d83675c950524b54bad9be786a8c4e7a9516c834653eaf72a64695e58040ac68`，以及`acceptance-completion-supplement.json`单列物理配置/进程连续性成立。该补证不修改原断言结果、不放宽性能阈值、不重跑90或发统计GET；五冻结工具未变。整体仍因1项性能FAIL为Partial，不能把原wrapper称为实际0。

50ms采样窗口（北京时间）`2026-10-11T21:17:53.950172+08:00—2026-10-11T21:23:17.157600+08:00`，6465样本、最大gap51.256ms，覆盖全部90及idle。RSS940.730469→1513.730469→1493.691406MiB，PSS938.339844→1511.330078→1491.291016MiB，CPU72.72秒；相对ea93的峰/末分别增加52.281250/32.503906MiB，CPU少1.62秒，不能称资源持续改善或确定单因素因果。cgroup全部OOM事件增量0，host MemAvailable2202456064→1621016576B、host oom_kill累计1→1。idle仍约1.46GiB，384MiB宽表预算不是RSS上限；整体OOM继续独立OPEN。副本并发CPU回归与生产此窗口资源各自保留。

生产证据冻结在联合工作树忽略目录`output/versus-personal-acceptance/release-4f3f2ac0436ba6556bc3ca90773860e18cd9dc77/`：候选/整合/1455门禁绑定、现成快照九步/source/上传/push/首次确认边界、actual workflows/jobs/成功安装日志、8步runtime/startup，及`first-production-detail/`原90/116/3strict/全50ms资源、三个旧版逐key比较、原wrapper失败与独立连续性补证。`evidence-manifest.json` SHA256 `44cb4bebec82fd336776abc4af330fdc76cb78e4892c4316a724c57843df6903`固定此时339文件；原始数据和output不提交。协调已独立离线确认89/1、116/三strict、资源增加及挂载顺序补证；原失败与补证分列保留。根随后仅同步六份交付文档，文档提交不是新的运行版本，不再部署或发生产请求。

`SS-2026-10-09-001`继续OPEN/Partial，`SS-2026-10-08-001`整体OOM、`SS-2026-10-11-001`手机加载弹层各自OPEN。后续唯一产品负责人仍是详情任务：先离线复核index39、正常点击和完整资源，再提出同源副本有界分段诊断；不改前端并发猜测归因，不扩大生产热重跑/重启/清理/循环发布，对决已完成状态保持，计划不归档。


## 名称身份有序批量传输候选（2026-10-12，独立后端分支／资源准入未满足）

用户“继续下一步”及协调批准后，在独立managed工作树`album-identity-json-batch/202605-SpotifyStats`、分支`codex/album-identity-json-batch`，从9468bb484f75ad9e0c5c6877447c1698834e42b3（产品4f）实现。旧详情工作树的前端settings提前11路径、全部patch/测试/文档和原证据已绑定保留，未撤销或合入本轮。该前端候选原42专项/full8通过，但38→39/32对照core1381.0→1412.6ms未改善、全批次peak+49.422MiB，发布暂缓；旧有界profile捕获GIL重取等待仍不能认定rank唯一因果，连续RSS/threadCPU未取得的Partial原样保留。

本轮只有`album_project_identity._project_rows`全名称分支改变传输：保留原JOIN、ap.project_id/apa.album_id有序子查询、完整8字段、null/值类型/重复，用SQLite JSON一次传输，再恢复匹配器需要的映射。原stable ID路径继续有界原生Row；返回及匹配器注解如实声明Row或Mapping。NFKC/casefold/空白、artist歧义fail-closed、canonical/member优先、L2/L3 preferred scope及fallback、必要第二次兼容校验均不改；单项和batch共用读取。没有缓存、schema/index/依赖、SQL lower、取消/线程池/预算修改或GET写入/排队。

新回归以旧SQL为独立oracle，覆盖逐字段/类型/null、重复与缺成员/空集合、明确行顺序、大整数精度、Unicode/NFKC/casefold/多空白/引号换行反斜杠、归一后同名艺人歧义、canonical/member多成员、两scope/fallback、stable ID及单项/batch消费。身份/alias API、投影/source/公开只读及详情/未ready边界专项共155项通过（77+64+14）；完整默认unit/contract/full8未宣称已跑。真实副本3181行ordered-value/type digest和完整身份完全相同。测试与实际返回均证明没有改候选事实，不能把“减少传输交接”称为“减少SQL扫描行数”。

### 安静单次行读取与分配

每版一个独立进程、同一Online Backup副本只读一次全行；旧rows为oracle，后续hash/实体匹配在读取计时之后。记录Python tracemalloc而不强制GC，OS页缓存冷暖未控制；tracemalloc自身有开销，不能外推为真实请求CPU。

| 指标 | 基线 | JSON候选 |
| --- | ---: | ---: |
| rows / fields | 3181 / 8 | 3181 / 8 |
| 行读取wall / threadCPU ms | 8.390 / 8.389 | 13.093 / 13.092 |
| Python分配current / peak B | 1612935 / 1613327 | 2333155 / 3265681 |
| 进程RSS before / after B | 17154048 / 24035328 | 16990208 / 27721728 |

候选传输285665 UTF8 B/264659字符；有tracemalloc的SQL execute3.982ms、fetchone0.006ms、decode6.362ms。读取CPU增加约4.704ms，Python分配peak增加1652354B（约1.576MiB）；不能用无竞争安静样本宣布更快。这些增加与真实页面收益分列保留。

### 两版各一次38→39，原前端共同基线

另建七库Online Backup副本（schema90/quick_check ok/现成ready），仅在该副本正常lifespan/维护；没有额外预暖、清缓存、强制GC、热重试、生产GET或全90前缀。两版backend分别9468归档及精确一个产品文件候选，均使用相同原前端source/dist，不包含旧settings提前候选。每case fresh context、正常PWA及原production阈值；低开销阶段wrapper保留原生cache/singleflight，没有authorizer或原生/Python栈采样。SQL/JSON阶段只聚合一次调用，不逐行观察。

| case | core基线→候选ms | 原断言 |
| --- | ---: | --- |
| 38固定L3点击 | 87.3→84.1 | 两版PASS |
| 39固定L3直接进入 | 1454.8→1273.2（-181.6ms） | 两版PASS |

9个完成API响应逐URL/filter核对完整body/status/快照头全部相同；两版各自窗口57保护/37原始/队列/六侧库/schema/epochs/fence/七库身份strict全部守恒，零写/排队尝试。跨版进入窗口的57/37/source/fence/epochs/schema/四exact-ready也全部相同。real-row/type oracle、backend归档、共同原前端、观察器及旧前端候选起止绑定一致。

39 summary名称rows95.061ms wall/7.082ms CPU→8.046/8.038ms，完整身份98.067→10.669ms；overview必要名称rows351.233/6.649→11.192/5.599ms，完整名称身份354.132→13.954ms。真实未tracemalloc decode为summary2.736ms、overview1.545ms。服务summary109.967→136.127ms、overview270.925→425.321ms增加也保留，父子不相加；整页净收益181.6ms小于各名称wall下降之和。单轮不是统计结论，也不能等同生产剩余125.1ms已修复。

### 连续资源及停止条件

连续process RSS/CPU/host-headroom50ms采样已先以自有短进程实际校验15样本通过。本轮取得基线2593/候选756样本，最大gap67.598/76.134ms，覆盖startup、请求、真实rank完成和idle。仅正常SIGTERM后记录到ZombieProcess（server_exit=-15），无请求期异常或资源guard触发；没有像前一profile把空samples/guard[]称通过。旧profile缺口仍保留。本次dispatch/singleflight等待没有观测，记录null，不以0伪装无等待。

| 分窗指标 | 基线 | 候选 |
| --- | ---: | ---: |
| 正常startup wall s | 126.612 | 20.760 |
| startup点RSS MiB | 1219.266 | 1372.750 |
| 请求→真实后端完成wall / CPU s | 5.604 / 3.670528 | 4.931 / 3.711517 |
| 请求窗口RSS start / end / peak MiB | 1219.266 / 1091.203 / 1219.266 | 1255.172 / 1259.875 / 1285.656 |
| idle RSS MiB | 1091.203 | 1259.875 |
| 含startup全批次peak MiB | 1692.797 | 1381.609 |
| budget start / end B | 326135446 / 196151193 | 326135446 / 196151193 |

请求CPU增加0.040989s（约1.1%），请求peak增加66.391MiB、idle增加168.672MiB（约15.5%）；全批次peak降低主要和不同startup维护历史并存，不能抵消请求/idle驻留增加。首次新路径副本startup维护126.6秒，第二版复用其持久ready事实约20.8秒，OS缓存/allocator/维护历史不同；不能把168.7MiB唯一归给JSON，也不能据此称无资源回归或关闭OOM。约3ms归一匹配不改，结构化传输增加的decode/分配及所有正负结果均保留。

按照已批准的“资源明显恶化就停止扩展”条件，本轮 **资源准入NOT_MET，默认完整full8 NOT_RUN**，没有尝试/失败后重跑fullgate，也不追加配对矩阵、调线程池/取消/缓存或继续微调凑性能。候选功能专项通过，单轮耗时及资源差异已记录，因继承维护状态混杂均未作JSON因果归属，无明显资源回归尚未证明；交协调独立审阅停止决定及原始证据，不commit/push/deploy。前端旧候选继续独立暂缓。生产4f原89/1、wrapperexit1/挂载顺序补证、原并发CPU回归，以及整体OOM/nonframe/native和手机问题全部保留OPEN。

证据在新隔离工作树`output/album-identity-json-acceptance/`：旧前端保留绑定、schema90 Online Backup/preparation、source/tool绑定、旧SQL单位oracle及真实行读取/分配、sampler实际校验、每版原browser完整响应/events/连续samples/strict/receipt、batch实际0及`compare_saved.py`实际0/`comparison.json`。共同原前端source/dist仍绑定于旧工作树的原基线归档，旧未发布前端产品未被包含。只关闭本轮自有backend/preview，8025/5225均关闭；原始数据与output不提交。


### 原顺序对照起点离线补证（2026-10-12，不新增测量）

协调反馈独立identity+transfer unit17项actual0、8路径/patch及receipt hashes匹配，认可功能专项与按资源停止、不跑fullgate的决定；并指出相同source/fence不等于相同维护起点。本轮只读16个保存的startup日志/receipt/source captures/preparation/recovery manifest及runner AST，输入SHA起止相同，不打开DB、不启动服务/浏览器、不重跑benchmark/profile/门禁或修改产品。原候选代码、原patch和原对照/收据没有覆盖，只新增解释补证。

runner在版本循环之前做一次七库Online Backup，之后baseline/candidate均使用同一个OUT/runtime；两版之间没有restore或分别派生副本。因此 **候选继承基线正常启动的持久维护结果，-181.6ms、peak+66.391MiB及idle+168.672MiB都只能称观测差异，不能归因JSON**。功能响应/只读守恒继续成立，资源准入未证实、停止扩展与full8 NOT_RUN维持。

保存的日志直接记录：baseline排队analysis_stats/analysis_records各lifetime/last_4_weeks/last_6_months六组维护，并于09:21:20重建2022–2026 Billboard snapshots；candidate未记录这些Analysis排队消息，09:23:43明确Billboard already current、startup rebuild skipped。两版L3均already current/跳过、JobQueue均3worker，settled active0；startup wall126.612→20.760秒、ready点累计processCPU125.749→21.151秒。排队不等于全部实际构建/成功，没有per-job执行/状态明细，不能将全部时间差分配给六项。

baseline窗口结束→candidate启动后窗口开始，主发布表与六侧库发布表的rows/全hash均相同（含clocks），其中Analysis20条、Billboard78条；source57/original37、epochs/schema/四exact-ready及fence相同。这是持久维护状态继承的可见证据，不是相同启动前缓存ready证明。background_jobs总8146→8147且hash改变，其余四队列摘要相同；七库path/device/inode未变，main size645062656→645070848B。未保存新任务的类型/状态，不凭总数认定warmup。

初始runtime-preparation与baseline启动后first capture的57共有保护表摘要中，56相同，只有governance_source_revisions的96行digest改变（65d824f0…→7c535196…）。初始具体行未保存，无法确认revision/domain或时间戳字段变化，不宣称完全相同治理起点或原始播放被重写。初始main清单v12 ready12条/旧v10 running1条，不能代替aux初始ready/request/source/builder摘要，也未证明旧v10是否active或导致重建。recovery manifest仅七DB哈希，本輪未打开备份数据库补读。

内存cache keys/hits/entry身份、allocator/native驻留和OS页缓存/IO/调度均未证明相等；相同326135446B预算不是完整内存起点。原各自read-window strict及跨版两个启动后source/fence比较不能替代相同启动前queue/publication/cache生命周期；此前“局部收益”只保留为观察到耗时差异。

若后续补受控配对，先交具体有界方案：同一初始七库Online Backup派生各自独立runtime，启动前逻辑schema/source/queue及main+aux ready/publication/filter摘要一致；文件inode差异单列，ready/source不匹配就停止。共同原前端/相同配置，各正常lifespan一次并分列启动维护，然后每版恰一次38→39 fresh/PWA，已验证50ms CPU/RSS/headroom、完整响应/strict及startup/请求/真实完成/idle分窗，无预暖/GC/清缓存/热重跑。当前只记录方案，未执行；不自行再跑profile/fullgate或改变实现。

补证为`output/album-identity-json-acceptance/startup-origin-review.py`（实际0）、`startup-origin-review/audit.json`及`audit.md`，绑定原输入、脚本行号、保存日志和摘要差异。原8路径候选/patch与旧前端11路径继续可恢复，155专项与协调17项是功能证据；无commit/push/deploy，生产89/1、wrapper FAIL/排序补证、旧并发CPU回归和上轮采样缺口全部保留，OOM/native/nonframe与手机继续OPEN。本轮完成此离线审阅后结束。


### 受控配对的初始ready核验（2026-10-12，测量未启动）

协调通过起点补证并批准一次独立runtime受控配对后，选定已有`output/album-identity-json-acceptance/pre-batch-online-backup`为唯一初始七库来源。原manifest七文件SHA全匹配、无WAL/journal/shm；资源预检约6.7GiB可用内存/46.37GiB磁盘，预计两副本约1.25GiB。产品/测试仍冻结，旧前端候选不包含。计划两个独立路径`controlled-pair/runtime-baseline`和`runtime-candidate`，但未创建或启动。

只读/immutable捕获schema90、57保护/37原始、完整queue/main及六侧库发布摘要、source/filter fence，四音乐查找exact-ready全部True；`projection_available`检查对应详情投影source/version/ready全部True。进一步对默认四组排名参数检查family/request_key/source_revision/builder_version，备份当前文件身份的精确匹配全部0，尽管同版本entity_rank_context存在4条发布记录。

该排名key包含`analysis_snapshot_revision.database_identity`的device/inode，设计明确是file-local lineage；Online Backup及派生副本改变物理身份。以保存的原来源runtime strict capture的device/inode、相同默认params和v2版本计算，四个发布key各匹配1条；以备份当前身份计算均0。故可确认记录位于原文件身份键空间；key-only对照不代替原namespace完整payload/source校验，不称原发布丢失或损坏。

依本轮明确“初始ready/source不满足就报告并停止，不擅自冷建/修复”的门槛，停在前检，**受控配对NOT_RUN、full8 NOT_RUN**。未创建两份runtime、启动backend/browser、重跑benchmark/profile/矩阵、调用ensure/build/rebuild、修改发布key/source或写原备份；所有只读查询后七库SHA不变，连接已关闭，未打开正式数据。正常lifespan可预期为新inode建立本地排名发布，但不是初始exact-ready，本轮没有以自然启动维护越过该初始门槛。

后续需协调明确file-local命名空间失配与初始必要ready门槛的关系（是否作为两副本一致的预期正常启动维护，或依既有严格source安装合同处理），当前不换备份、不共享硬链接、不伪造身份、不自动重绑定或挑测量。前一顺序轮的耗时/RSS均保持非因果观测，155专项/协调17项及只读等价仍有效；原8路径后端、11路径前端候选和全部原补丁/证据保留，发布暂缓，89/1、wrapper FAIL/排序补证、并发CPU回归、上轮采样缺口、OOM/native/nonframe及手机OPEN不改。

初始证据在`output/album-identity-json-acceptance/controlled-pair/`：`preflight.json`、`source-initial-strict.json`（closed immutable捕获实际0）、`source-required-ready.json`、`rank-lineage-key-proof.json`和`preflight-report.md`。不存在新受控回放结果；只追加该前检解释，不覆盖原实验或patch，不commit/push/deploy。


### 独立副本命名空间规范准备与受控配对（2026-10-12，已完成，资源准入未满足）

协调已明确解除新file-local命名空间的前检阻断：原备份保持只读，两个独立runtime从同一初始七库派生，初始完整逻辑状态一致；同一现成manifest完整规范验证通过并对称install/verify排名4/4，原源备份未写。单次受控38→39对照已完成，局部耗时下降但资源准入NOT_MET；旧前检停止与原顺序实验记录保留，默认full8 NOT_RUN，未提交发布。

源为原pre-batch-online-backup，新的runtime-baseline/runtime-candidate路径独立、七库inode各异；初始source57/original37、治理/queue/main与六侧pub、schema/fence/ready均相同。采用已有versus-ranks-4f manifest，validate检查完整filters/builder/metadata/source/payload/digest/defaults，通过后用原后端规范工具分别validate/install/verify，各4项实际0。只改两实验Analysis sidecar，源main/queue/main pubs和其它五侧库守恒，原七库SHA未变。测量使用原前端，metadata/rank ready验证放在独立只读进程，不暖被测后端缓存。


受控回放工具首次在baseline正常启动后、任何浏览器案例之前因metadata只读助手缺少scripts导入路径退出1；该失败日志/启动样本/副本保留，零浏览器案例，不是性能失败重试。修正仅输出目录内工具导入路径，并从同一原始七库备份重新派生两个全新独立runtime于controlled-pair-v2，对称规范安装4rank。修正助手已在实际runner环境预检通过，初始逻辑状态/完整任务/rank payload合同再次相同；未复用已维护副本，真正页面测量仍每版一次，旧controlled-pair初次工具失败不覆盖。

受控实际回放保存在`output/album-identity-json-acceptance/controlled-pair-v2/`，runner实际退出0，每版仅一次38→39、fresh context、正常PWA/原阈值、共同原前端；没有预暖/GC/清缓存或性能失败后重跑。初始化后rank/search/detail各4 ready、active jobs为空；两版各新增12个正常启动任务且全部done，类型/数量一致（analysis六项，其余community/Billboard/archive/governance/artist-rank/warmup各一），8130个既有任务未变。初始七库source57/original37、queue、main/六侧发布、schema/fence/ready完整逻辑等价，独立inode的命名空间差异单列，未沿用前一顺序轮的维护状态。

| 原案例/窗口 | baseline | candidate | 观测差异 |
| --- | ---: | ---: | ---: |
| 38 点击核心可见 ms | 105.5 | 86.4 | -19.1 |
| 39 固定L3专辑direct核心可见 ms | 1530.0 | 1273.7 | -256.3 |
| 正常启动 wall s | 108.895 | 112.234 | +3.340 |
| 启动就绪 RSS MiB | 1260.797 | 1264.547 | +3.750 |
| 请求至真实后端完成 wall / CPU s | 5.682 / 3.799563 | 4.952 / 3.881736 | -0.730 / +0.082173 |
| 请求 RSS start / end / peak MiB | 1110.219 / 1115.875 / 1131.141 | 1264.547 / 1262.516 / 1295.406 | peak +164.266 |
| idle RSS MiB | 1115.875 | 1262.516 | +146.641 |
| 含启动全窗口 RSS peak MiB | 1541.453 | 1640.453 | +99.000 |
| 连续样本 / 最大间隔 ms | 2462 / 61.341 | 2394 / 87.797 | 请求窗口105 / 87样本 |

九对完成响应按完整body/status/URL参数/快照头精确相同，38和39原功能断言两版均通过。两版各自请求前后strict全部通过：57保护/37原始/队列/主发布及六侧库/schema/epochs/fence/七库身份不变，公开写入/排队尝试0，无残留统计请求。rank四发布的完整payload/metadata/filters精确相同，artist-rank发布payload同样相等。起止共享宽表预算估算326135446→196151193B、native cache_info相同，但cache完整key包含进程owner和file-local命名空间，opaque key hash不同不等于缓存语义不同；预算估算也不能替代RSS。没有headroom guard触发；采样在自有后端终止时分别记录NoSuchProcess/ZombieProcess，发生于真实完成、idle、strict及停止之后，原异常保留，不计为请求样本缺失。

**跨正常启动的差异不并入strict读窗口Pass**：启动后两版57保护表的原摘要仅`governance_source_revisions`不同，96行domain/revision相同、只有epoch UUID不同（不是时间戳）。离线只读核对已关闭副本：初始备份PRAGMA schema_version=1、治理记录1146，匹配现有治理安装的schema-cookie失配/随机epoch重置分支；两版启动后均573/573。原37表、schema90、source/filter fence与ready保持相等。第一次离线比较误按updated_at排除字段导致实际退出1，原`comparison.log`保留；改为准确排除epoch后`comparison-v2.log`实际0，原raw差异没有改写。

原`comparison.json`的`settled_analysis_payload_semantic_digest_equal=false`保留：该比较包含source_revision，不是纯body比较。随后只在已关闭实验副本做有界解压/长度和SHA校验、13对同publication_id/family/period逐字段离线比较，统计六条body全部相同；记录七条仅最新三个周期的`/meta/generated_at`不同，精确移除这一字段后13对body全部相同。原发布行的request_key/source_revision/created_at仍不同，records三条原sha256也不同；file-local request/source身份不伪造、不统一；其他body字段无差异。`publication-difference-audit.json`保留每对差异路径/哈希及五个closed DB起止SHA，实际0、数据库零写入，没有服务/浏览器/新计时。不能将规范化body相同写成全部原发布行/原source_revision相同。

**停止决定**：虽然39核心可见局部少256.3ms，但请求峰+164.266MiB、idle+146.641MiB、请求CPU+0.082秒，按已授权“资源明显恶化则停止扩展”条件，资源准入NOT_MET，默认完整八阶段full8 NOT_RUN。两版初始持久状态已对齐；OS页缓存/分配器/GC时序未控制，单次配对不证明JSON是耗时或驻留差异的唯一原因。复用155专项及协调独立17项，不再补测/改产品/跑完整门禁。原backend两文件保持冻结，六文档更新，最终8路径补丁及收据供独立审阅；没有commit/push/deploy/生产GET。

原顺序轮、初始ready阻断、零浏览器导入失败、原补丁/收据全部保留；旧前端11路径及补丁哈希未变且不进入本候选。生产89/1、wrapper实际exit1与独立挂载排序补证、并发CPU回归、上轮连续采样缺口、整体OOM/native/nonframe及手机OPEN继续保留。自有后端/preview/context已关闭、8025/5225关闭；原七库备份SHA保持不变。


## 艺人范围名称读取与已验证身份复用（2026-10-12，专项完成，资源准入未证实）

用户确认下一步建议并要求执行后，在新独立managed工作树`album-identity-targeted/202605-SpotifyStats`、分支`codex/album-identity-targeted`，从9468原产品基线开始；不合入旧JSON行传输或settings前端候选，其补丁/11路径/原测量与停止决定保持冻结。

离线按已保存请求拆分12次身份读取：4次目标ID读取各1行，8次完整项目JOIN各3181行。后者为名称summary两次、必要L3 release兼容校验四次、stats builder重复名称解析两次。不能写成12次全表扫描，或把wall-threadCPU差额直接归为GIL/IO/锁。原12读取分组与原events SHA保存在`output/album-identity-targeted-acceptance/offline-request-inventory.json`。

最小改动三个产品文件：名称单项查询先按原NFKC/casefold/空白规则筛出所有同名艺人ID（保留归一后不同ID的歧义），以现有artist_id索引缩小原项目JOIN候选；完整8字段、排序、原生Row与匹配器保持。艺人缺省/归一后空白继续完整候选，稳定ID仍单独有界读取，batch仍原一次完整视图。JSON仅用于小型艺人ID参数列表，未恢复旧全行JSON聚合/解码。没有缓存/schema/index/发布格式变化、SQL lower、前端/取消/线程池/预算修改。

L3 release稳定入口原来必须通过名称规则证明没有更优/歧义项目；该校验保留。只有通过这项检查的身份复用到stats builder，连同现有revision进入响应cache key；首选scope ID的名称歧义语义继续原名称解析，避免未经证明直接将ID代替名称规则。route请求身份响应仍由原attach函数生成；不在GET构建或排队，不删除404/503/source fence。

初始41项通过，最终消费者/身份/排名发布/公开只读/投影及API专项199项通过；补充超2**53与2**63-1艺人ID后targeted单文件29项通过，合计201个不同用例通过。首次消费者命令误用不存在的复数文件名实际exit4、未执行用例，原log/xml保留；核对实际路径后最终命令0。首次Ruff检查发现fixture导入和Python3.9 Optional样式问题，按现有fixture导出方式及backend说明修正，最终check/format通过，不把初次检查写成通过。

真实原七库备份只读、有界12身份例与旧完整行oracle精确一致；目标JOIN3181→82行，顺序/字段值/类型完全一致、已有idx_album_projects_artist实际使用。名称查询仍读取1907行艺人目录的两个字段，作为实际成本保留，不称消除所有全表读取。该核对无service/HTTP/计时，备份SHA起止不变。

两版独立runtime来自同一原初始七库，初始完整source/governance/queue/main+六侧发布/schema/fence/ready一致，七库inode不同。现成rank manifest以共同原后端工具规范validate/install/verify各4实际0；main、queue与其它五侧库无安装写入，原备份SHA未变。实际runner环境下metadata助手预检0、rank/search/detail各4、8130既有任务相同且active0，验证放在单独只读进程，不预暖被测后端缓存。源码/共同原前端与低开销观察器均起止绑定，每版唯一正常启动38→39，PWA和原门槛不改；本轮功能和结构性收益已验证；完整资源准入未证实，最终结果分列如下。


### 唯一独立副本配对与最终停止决定

两版各自正常启动后，rank/search/detail各4 ready、active0，既有任务不变、新增12正常维护任务类型/数量相同且全部done。runner与离线比较实际0，原PWA/阈值/共同原前端、每版唯一38→39无预暖/GC/清缓存/热重试。两个统计builder少两次重复名称解析，身份读取12→10；四ID读取各1行保持，八个全项目JOIN变为六个艺人范围JOIN各82行，项目JOIN累计25452→496。目录查询成本包含在resolver wall/threadCPU内，不能用JOIN降幅代替完整SQL/读取成本降幅。identity.rows累计wall/threadCPU630.246/71.051→22.629/10.924ms，resolver含目录查询656.255/96.817→105.214/35.501ms；四overview builder累计wall298.733→538.202ms、threadCPU77.609→80.119ms，不能以身份局部改善宣布全部等待消除。两个stats builder累计threadCPU3599.154→3519.328ms，重型统计和切页后继续计算仍是独立后续方向。

| 原案例/窗口 | baseline | candidate | 观测差异 |
| --- | ---: | ---: | ---: |
| 38 点击核心可见 ms | 124.3 | 138.4 | +14.1 |
| 39 固定L3专辑direct核心可见 ms | 1447.0 | 1395.5 | -51.5 |
| 正常启动 wall s | 117.439 | 115.181 | -2.258 |
| 启动就绪 RSS MiB | 1173.703 | 1261.734 | +88.031 |
| 请求至真实后端完成 wall / CPU s | 5.682 / 3.916799 | 5.456 / 3.769922 | -0.226 / -0.146877 |
| 请求 RSS start / end / peak MiB | 1173.719 / 1195.891 / 1205.609 | 1116.453 / 1134.203 / 1164.563 | absolute peak -41.047 |
| 请求peak相对请求起点增长 MiB | 31.891 | 48.109 | +16.219 |
| idle RSS MiB | 1195.891 | 1134.219 | absolute -61.672 |
| idle相对请求起点增长 MiB | 22.172 | 17.766 | -4.406 |
| 含启动全窗口 RSS peak MiB | 1684.641 | 1770.734 | +86.094 |
| 连续样本 / 最大间隔 ms | 2640 / 66.422 | 2577 / 103.953 | 请求窗口106 / 100样本 |

两版各自read-window strict57保护/37原始/全部queue/pub/六侧库/schema/epochs/fence/文件身份全守恒，公开写入/排队尝试0、无未完成stats请求；9对body/status/URL参数/快照头完整相同。四rank完整filters/metadata/payload精确相同；跨版原37与schema/fence/ready相同，治理96行仅epoch UUID不同，初始schema-cookie1/记录1146与启动后573/573单列。13统计发布body仅最新三周期records的meta.generated_at不同，精确排除该元数据后全部相同；原request_key/source_revision/created_at/records原sha不同仍保留，原比较false不改。离线解压/原SHA校验与五closed DB起止SHA核验实际0，没有服务/浏览器新测量。

**资源准入未证实，full8 NOT_RUN**：开始只根据请求/idle绝对值降低曾在commentary提出继续完整门禁；在启动任何门禁之前核对完整分窗，发现请求起点已低57.266MiB、启动峰反高86.094MiB、请求净峰增长反高16.219MiB，及时撤回该过早判断。不能把61.672MiB idle绝对差全归于本补丁驻留改善。单轮深链收益51.5ms、点击退化14.1ms，结构性收益成立，但总体资源准入NOT_PROVEN；没有默认full8尝试，也未局部门禁/重测或挑选结果。OS页缓存/分配器/GC时序未控制，正负RSS差异均不作产品唯一因果归属，整体OOM不关闭。

当前三产品/两测试/六文档共11路径候选冻结，源码起止绑定一致；原JSON8路径补丁及旧前端11路径/原patch全部保持，原备份七SHA未变，自有backend/preview/context关闭、8025/5225关闭。没有commit/push/deploy/生产GET。请求工作量、完整比较、资源复核、发布差异与最终补丁/收据保存在`output/album-identity-targeted-acceptance/`，最终review与停止决定以`controlled-pair/admission-review.json`为准，不能继承前一JSON候选的资源判断或门禁结果。下一步独立核对启动驻留与排名跨页延续的成本，当前不继续微调/扩门禁。


## 2026-10-12 候选归档与单一研发工作树

前端设置加载、JSON批量传输和艺人范围读取候选已冻结归档，处置与恢复见[分支整理报告](2026-10-12-development-worktree-closeout.md)。本报告的历史路径/计时/失败保留原样；本机归档`spotifystats-cleanup/20261012T082400Z/path-map.json`解释旧output位置。三个候选均未合入main业务代码，历史full8不能转移到其它候选。

当前唯一研发为`codex/album-rank-cost`，继续有界定位Top250统计、切页后的排名计算与启动驻留；源码已发现排名复用后仍有时长/排行构建路径，因果与资源影响尚待分段测量。协调方统一维护共享状态文档，当前实验通过`archive-locations.json`读取已迁移证据；生产仍保留原89/1及OOM/手机OPEN边界。
