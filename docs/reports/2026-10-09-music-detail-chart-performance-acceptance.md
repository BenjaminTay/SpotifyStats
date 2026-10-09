# 音乐详情榜单成绩性能验收

日期：2026-10-09。事项：`SS-2026-10-09-001`。当前结论：**Partial，S1–S3 已实现，S4 后端功能与资源门槛通过，自然浏览器/完整全栈及 S5 尚未完成**。

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

## 最终后端功能与读取边界

固定集成 SHA 为 `108a5f41`（专项业务 `708a67f` 与上游 `acdd` 合并）。基线继续使用干净 `d5ba3094` 源码及独立事实副本；旧严格差异和失败诊断均保留。

- 最终 116 个服务响应由主样本 52、补充状态样本 24、真实版本组样本 40 组成，四组合全部零请求错误。positive 未入榜、零有效播放、未知实体和 featured 署名状态分别核验；ready publication 的 `not_charted` / `found=false` 与 `snapshot_unavailable` 明确区分。主样本 overview 年榜全部 ready，并与基线逐字段相等。
- 40 个版本身份响应覆盖 recording 无 parent、recording 子组、composition parent，以及 primary/非 primary L1。输入 L1 ID 保留；同组身份的 canonical 名、榜单和年榜字段一致。版本成员逐项次数/时长与独立 raw 双轨审计及最终 aux SQL 相等，L2 cardigan 为 132 次、L3 composition 为 176 次；版本列表按逻辑次数降序、L1 ID 排序，未删除可见版本字段。
- 严格 UI 差异主样本 572 项、补充样本 0 项、版本样本 140 项，保留原逐字段对账。主样本中 54 项属于固定阈值项目双轨时长纠正，28 项属于 L3 榜单/叠加排名的发行资格纠正，490 项是六周全局冠军事实变化及原排序造成的数组位置传播。版本差异对应旧非 primary 榜单身份失配和 L2 错扩 composition parent；最终 canonical 名差异已消除。各样本与独立证明的对应关系记录在 `strict-diff-rule-map-108a5f41.json`，不能把 490 个数组字段差异写成 490 个冠军事实变化。
- 真 HTTP 合同证明：仅 search+aux exact-ready、Billboard 侧库完全不存在时，三类 summary/overview 及专辑名称/稳定 ID 的 project 共 10 个 GET 返回 200，提供自身 snapshot headers，禁止旧 full gate/重型计算且无写；旧 full/list/release 三个 GET 仍明确 503。修订后的四文件合同专项 21 passed，旧 fixture 缺发布导致的失败保留为诊断。
- 五个独占 Online Backup 故障副本分别模拟缺 aux、context 篡改、缺 ledger、旧 projection 版本及 revision 漂移。三类 summary/overview 共 30 项全部明确 `503 snapshot_unavailable`；完整时间线/个人统计/Billboard/年榜等重型 spy 零调用，五个副本请求前后整个主库 SHA 均相同。
- 基线与投影副本的 38 表守恒审计中，37 表行数和 SHA 相同；唯一不同的 `governance_source_revisions` 是 schema90 安装 revision tracking 后的 epoch/新增派生域元数据（93→96 行），不描述为 38 表全部相等。最终 HTTP 与功能请求前后，两侧目录的全部 15 个 `.db` 文件 SHA 完全相同，覆盖主库源事实、发布/队列和侧库成品；验证期间未访问或修改正式数据库。

上述私人证据分别保存在 `functional-summary-108a5f41.json`、三份 `*-differences-108a5f41.json`、`projection-fact-audit.json`、`projection-global-no1-audit.json`、`version-group-independent-weight-audit-final.json`、`faults-final/summary.json`、`extended-source-conservation.json` 和 `contract-boundary-ready-final.log`。

## 最终后端资源门槛

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

## 诊断与其余阶段证据

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

## 后续与发布

冻结门槛、样本和判定保持规划第 5 节，不以热重跑替换首轮失败。S4 后端功能与冷/热/324 资源证据已登记，整体验收仍为 Partial；三浏览器四视口自然首次访问（自然 90 项矩阵）及默认完整全栈尚未通过登记。S5 仍需 CI/三部署模式、正式 Online Backup、source-fenced 副本成品复用、生产健康/首次访问/资源与联合回滚证据。正式 Online Backup 副本为 schema89/94,760 条播放，迁移副本至 schema90 后 source_marker、lineage/治理及六类原搜索表逐表 SHA 守恒；两份既有 manifest 精确复用，搜索/aux/Billboard 冷建均为0，aux 四变体及 v4 的48 targets ready。manifest 权限600，仅保存在私有目录。专项分支已推送，尚未发布；本报告的本地后端结果不代表生产验收通过。
