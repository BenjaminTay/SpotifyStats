# 阶段 6C：治理 Coverage / Health 共享事实与持久结果

日期：2026-09-20。结论：**6C 本地范围 Pass**。全量 contract 保留两个阶段开始前已有的 Analysis 503 失败，因此不称全项目或全栈 Pass。未修改正式数据、未提交或部署，停止于 6C。

## 实施范围

仅持久化 profile 证实昂贵的五类结果：Import health、Genre coverage、Genre taxonomy、Genre axis-gaps、Language coverage。Genre / Language reviews、L1 identity risk health、L3 attribution health、Track credits status 原有轻量读取保持不变。没有扩展 Community 6A、Archive 6B 或进入阶段 7。

共享事实采用局部紧凑查询、原 listening intervals 重建及原 `build_primary_artist_ms`：保留 canonical identity、主艺人归属、unknown 和 excluded_ms；不持久化宽 plays DataFrame，也不进入原宽帧 LRU。`active_local AS MATERIALIZED` 避免真实旧库的 fallback identity 关系在逐条播放连接中反复扫描。Genre / Language 投影共享一次时长事实，审核和人工覆盖语义不变。

独立治理 sidecar 沿用已有压缩 JSON、内容校验、active/previous、singleflight 与原子事务发布模式。migration 76 的 epoch/counter 与 schema marker 按真实字段依赖失效；本地 schema backfill 会重装自己的 FK 依赖触发器。仅在 Archive marker 原本有效时同步本阶段新增 DDL 的 schema 版本，未改 Archive builder、规则、结果或修复其历史漂移。

Private / public 读取均不构建、不写入、不 enqueue。公开路由权限没有扩大。维护来自私有启动、已提交治理写入、导入后本地维护或显式 CLI；相同合同的旧结果带 checked_at / checked_revision，缺失返回 503。Import 数据库重检查和实时任务错误、目录存在性分离；实时失败会覆盖历史绿色结论。用户显式 preflight 文件检查原样保留。

版本字段、完整失效矩阵、读取合同和本地重建命令见 [治理持久结果规则](../reference/governance-snapshots.md)。

## 基线与测量方法

工作区起点 HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，起点已有大量其他阶段 dirty / untracked。旧实现按开始时冻结源码测量，不以 HEAD 替代工作区基线。正式库只读 Online Backup 得到 92,908 条播放的隔离副本；schema 安装、故障注入和本地派生仅作用副本。

旧版每接口三个独立进程，每进程一次首次请求加 20 次 warm。下面 warm P95 合并 60 个样本，采用线性插值；SQL 包括 execute 与 fetch 时间和 fetch 返回行数（不是 SQLite 物理 page 扫描计数）。旧版 HTTP 边界是 FastAPI TestClient，gzip 为响应重新压缩；新版门槛另用真实 loopback TCP、独立服务器进程和实际 wire gzip。进程启动 / Python import 时间不计入 API 延迟。整个测量期间禁止外部网络，应用 lifespan 关闭，避免启动维护干扰只读请求。

| 接口 | 三个新进程首次 ms | Warm P95 ms（60 样本） | 首次 SQL 次数 / 读取行 | 峰值 RSS MiB | 原始 / gzip B |
|---|---|---|---|---|---|
| Genre axis-gaps | 33482.1 / 33608.8 / 33527.8 | 99.5 | 60 / 104475 | 653.4 | 11813 / 1179 |
| Track credits status | 31.6 / 24.2 / 18.6 | 14.6 | 14 / 15 | 174.4 | 2113 / 672 |
| Genre coverage | 38319.2 / 109438.2 / 67438.4 | 180.4 | 59 / 104475 | 638.0 | 896 / 412 |
| Genre reviews | 18.3 / 18.4 / 22.2 | 8.0 | 5 / 2 | 174.0 | 22 / 42 |
| Import health | 6000.0 / 4621.4 / 4209.2 | 7132.3 | 282 / 7735 | 186.0 | 3609 / 1522 |
| L1 identity risks | 49.3 / 51.0 / 48.4 | 34.5 | 5 / 128 | 169.7 | 881 / 409 |
| L3 attribution health | 32.2 / 51.6 / 36.3 | 14.1 | 11 / 133 | 168.8 | 615 / 330 |
| Language coverage | 36652.4 / 59524.9 / 50352.5 | 851.0 | 60 / 103297 | 641.1 | 4984 / 1693 |
| Language reviews | 26.6 / 29.4 / 29.8 | 16.4 | 5 / 2 | 174.5 | 22 / 42 |
| Genre taxonomy | 28741.9 / 27409.5 / 31931.9 | 177.5 | 59 / 104475 | 651.5 | 40645 / 6164 |


基线部分长请求与其他本地验证重叠，存在机器负载竞争，尤其 Genre coverage 的 109 秒样本；全部保留，不能用这些夸大联合构建改善。专门的联合 old/new 试验另顺序运行三个独立进程对：旧顺序执行允许原进程内宽帧缓存复用，新联合维护从空 sidecar 开始。

## 联合构建与存储

- 旧 Genre + Language 顺序执行：34.360 / 37.666 / 34.525 秒，中位数 **34.525 秒**，primary builder 每次 2 次。
- 新联合维护：0.736 / 0.683 / 0.519 秒，中位数 **0.683 秒**，primary builder 每次 1 次；中位改善 **98.02%**，超过 40% 目标。
- 峰值 RSS：旧 584.41 / 580.58 / 572.06 MiB；新 189.73 / 188.22 / 189.84 MiB。不是仅将两次小聚合减成一次带来的提升：旧首次 SQL 32.16 秒，新 compact 查询约 0.46 秒，避免宽表关系扫描是主要原因。
- 真实副本同 key 四线程并发：共享事实和 primary builder 各 **1 次**，三个等待者复查 exact 后不重建；总耗时 1.460 秒，峰值 195.83 MiB。
- 五类完整初次联合发布（与基线并发负载重叠）52.816 秒，峰值 189.22 MiB；其中重型 Import 检查仍占主要成本。它被移出 GET，未声称 Import 冷构建自身提速。
- 两代真实发布已验证，sidecar 文件 167936 B；以下包含结果与元数据，不仅是压缩后的业务字段。最大 axis-gaps 为全部 axis 的完整候选，而 GET 保留既有 limit 投影。

| Family | Active + previous 原始 B | 压缩 B |
|---|---|---|
| genre_axis_gaps | 960454 | 99833 |
| genre_coverage | 3590 | 1390 |
| genre_taxonomy | 83020 | 13083 |
| import_health | 17880 | 4371 |
| language_coverage | 11475 | 3931 |
| primary_artist_ms | 28036 | 12877 |


每个结果 family 两代原始 JSON 均 <1 MiB；共享 primary_artist_ms 两代共 28,036 B，远低于 5 MiB。只读边界探针和每接口 profile 的宽 plays LRU 条目均为 0，builder 只持有函数内紧凑帧，持久事实只含 artist_id→整数毫秒与 excluded_ms。

## 跨进程 HTTP 验收

每 state / family 使用三个独立服务器进程；其中第一个追加 20 个 warm 样本，共 345 条实际 HTTP 样本。Exact / LKG 首次均 ≤500 ms，无快照均 ≤300 ms。LKG 通过副本源播放时长 +1 而持久结果仍为旧代产生；failed 来自真实 builder 故障注入，未伪造 HTTP 健康响应。

| 接口 | Exact 三次首次 ms | LKG 三次首次 ms | 无快照三次首次 ms | Warm P95：Exact / LKG / 无快照 ms |
|---|---|---|---|---|
| Import health | 34.4 / 27.2 / 57.8 | 25.1 / 30.7 / 20.7 | 16.4 / 12.2 / 8.2 | 21.3 / 9.8 / 10.5 |
| Genre coverage | 31.5 / 61.4 / 36.9 | 25.1 / 16.8 / 19.2 | 23.4 / 20.3 / 20.5 | 29.0 / 16.7 / 11.2 |
| Genre taxonomy | 43.3 / 52.4 / 26.7 | 23.1 / 17.8 / 19.4 | 12.6 / 12.7 / 19.2 | 33.6 / 17.1 / 10.5 |
| Genre axis-gaps | 36.8 / 44.3 / 31.5 | 25.5 / 36.2 / 31.0 | 13.3 / 21.0 / 20.5 | 40.9 / 24.4 / 11.1 |
| Language coverage | 21.1 / 19.2 / 15.5 | 182.1 / 89.1 / 41.7 | 17.8 / 18.5 / 19.5 | 18.1 / 75.0 / 11.3 |


原始 / gzip wire 大小和每条采样详见 `http-performance.csv`；无快照响应不足 gzip 中间件阈值，因此 encoding 为空，wire 即原始 JSON。额外 `profile-{state}-{family}.json` 保存每接口 SQL、读取行、RSS 和 21 次调用；这些仪器化 TestClient 样本不替代以上 TCP 门槛。

只读探针对副本主库和 sidecar 前后 SHA 核验无变化，并以 sentinel 禁止 builder / publish / enqueue。覆盖 exact、LKG、missing 的 API profile 每个维护调用计数为 0；public guard 单测也覆盖 exact/LKG/missing。源或配置漂移拒绝发布，失败保留旧代；缺失 marker/counter 明确 unavailable，只能显式 backfill。

## 正确性

同一真实副本、相同参数和源 revision：五类完整业务字典逐字段相等，`real-comparison.json` 五项 `equal=true`、`different_keys=[]`；保留旧 / 新完整 payload。对账仅剔除新增 snapshot/runtime 元数据和检查时间，不剔除计数、顺序、百分比、known/unknown 时长、风险或健康结论。Axis 比较覆盖实际 API 默认 axis/limit；单测另对持久全部 axis 逐字段比较。

32 项治理单测覆盖默认、空 plays、unknown / 未归属、无 genre、无 language、identity/credit / alias / attribution、不同过滤合同、genre / language 独立变更、Album Project / L3、导入状态、名称/封面、schema marker/counter 缺失、schema 新 FK 后显式 backfill、事务回滚、并发、source fence、失败保留 LKG 和无 LKG。七组完整五 family 原 builder 对账覆盖完整列表顺序及各业务字段。

Import health 只抽取原 `format_import_health` 组合步骤；原 album eligibility、single/compilation 不适用边界、Spotify ID 来源优先级及近期元数据 SQL 不变。实时 identity / credits / L3、最新导入失败重新组合状态，测试证明历史绿色结果不能覆盖当前错误。

## Desktop / Phone 浏览器

真实 Chromium、Desktop 1440×1000、Phone 390×844。路由代理只允许本机 GET；没有 import/preflight、治理写入、AI 或外部 provider 调用。所有检查使用真实副本 API；无快照 503 是预期状态，未将错误或 skeleton 算作 ready。

| 场景 | 旧版请求 | 6C 请求 / 行为 |
|---|---|---|
| Desktop Settings 初始 | capabilities、settings、LLM 配置及 Import health | capabilities、settings、LLM 配置；治理 health / coverage **0 请求** |
| 展开导入面板 | 已提前加载 health | 此时才请求 Import health；preflight 不自动触发 |
| 进入“流派与语言” | Genre 三类与审核数据 | Genre coverage/taxonomy/axis-gaps 与 reviews；Language coverage **0 请求** |
| 展开“艺人语言数据” | 即时 coverage | 此时请求 Language coverage |
| Phone Settings 初始 | capabilities、settings | capabilities、settings；治理请求 **0** |
| Phone data / advanced 与旧 metadata 深链 | 原移动入口 | 保留“在电脑上管理”；不挂载桌面治理面板，治理请求 **0** |

Phone 当前产品没有导入/流派/语言完整治理面板；本阶段验证真实手机挂载边界，未扩展治理信息架构，也未将手机管理提示算作治理 ready。Desktop 验证五类 ready 数据及 LKG、failed、unavailable：旧结果明确显示检查时间；失败/旧代标题不再显示当前“数据状态良好”；无快照显示本地维护说明与重新读取，结束 loading。各 viewport 无水平溢出，pageerror 为空；无快照的 503 console resource error 属于预期。

## 测试、正式数据与 Git

- Backend unit：**1902 passed**，包含 32 项治理测试。
- Backend contract：**435 passed，2 failed**；与起点两个测试完全一致：`test_api_boundary_probe`、`test_safe_readonly_api_smoke_probe` 的 Analysis stats/records 503。首次本轮出现的过滤参数契约失败已改为显式维护对应合同并复验通过，未恢复 GET 冷建。
- Frontend：**657 passed，4 skipped**（`npm test -- --maxWorkers=2`，限制并发避免原审核 dialog timeout）；TypeScript + Vite production build 通过。默认并发的首次运行曾有 4 个未改审核 dialog timeout，原日志保留；重跑全套无失败。
- 新增及相关后端定向、Ruff 通过；文档审计及 `git diff --check` 见最终日志。
- 正式 `data/` **4178 文件**大小/SHA-256 前后相同，新增/删除/改动列表为空。SQLite `-shm` 临时共享内存文件不计入内容证明；其余包括数据库、WAL、快照、封面和配置。原库仅只读 Online Backup，未执行导入、backfill、数据同步或部署。
- 起点和终点 Git 状态、逐文件起止 SHA、相对于**开始时 dirty 内容**的源代码 patch 见 `git-scope.json` / `stage6c-source.patch`。机器生成的 OpenAPI JSON 起点仅保留 SHA，未保存原文，因此单独附最终文件，不纳入源代码 patch；其模型生成器与 TypeScript 类型改动完整包含。6A/6B 专属源码均与起点相同；未执行 git add、commit 或 push。

## 原始证据

本地持久证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bda9-0b89-7c32-a315-00e88518fc01/spotifystats-stage6c`。证据保存在本机，不进入 Git，不包含数据库副本或 node_modules。

- `summary.json`、`performance.csv`：完整基线与仪器化 API 样本；`http-performance.csv` / `http-*.json`：真实 TCP。
- `before[1-3]-*.json`、`profile-*.json`、`sql-top.csv`：SQL、RSS、调用次数和响应体积。
- `joint-old*.json`、`joint-new*.json`、`concurrent.json`、`two-generations.json`、`boundaries.json`：联合维护与发布边界。
- `real-comparison.json`、`*-old-full.json`、`*-new-full.json`：完整对账。
- `browser-*.log/json`、`desktop-*.png`、`genre-language-*.png`、`phone-*.png`：请求、状态及截图。
- `formal-before.json`、`formal-after.json`、`formal-data-proof.json`：正式内容证明。
- `baseline-contract.log`、`contract-confirm.log`、`unit-confirm.log`、`frontend-confirm.log`、`frontend-build-confirm.log`、`docs-audit-final.log`、`diff-check-final.log`：门禁原始记录。

6C 的性能、语义、按需加载、只读和持久结果目标已满足。该结论限本地本阶段，不代表生产已迁移或全应用所有既有测试通过。到此停止。
