# 阶段 0：统一性能测量合同交付与校准

> 2026-09-19；本地基线 HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty。
> **Partial：工具实现与有边界校准；不是全应用性能验收或生产 SLA。**
> 阶段 1 未提交产品实现作为基线保留。本轮没有产品性能优化、索引迁移、commit、push 或部署。

## 合同与六个探针

规范入口：[统一测量合同](../reference/fullstack-verification.md#7-统一性能测量合同阶段-0)；机器 schema：[`performance-report.schema.json`](../../scripts/performance-report.schema.json)，`schema_version=spotify-performance/1`。

| 文件 | 本轮改动 |
|---|---|
| `scripts/benchmark_api.py` | 实际消费者目录；参数/数据/状态 metadata；HTTP 流编码 body 大小；首请求 unknown；独立临时服务至少 3 进程；保留原始样本；错误非零退出，少样本不算 P95 通过 |
| `scripts/loading_performance_probe.py` | 接统一 HTTP 样本，保留 first/repeated；canonical 摘要和 L1 stats；可指定 album-project；同 key/异 key 并发完整记录与分组；失败不被快速耗时掩盖 |
| `scripts/music_search_performance_probe.py` | 直接 service 与 HTTP 两种测量清楚分开；完整候选→统计请求序列；保留 warmup、unavailable 和失败；独立 cold 至少 3 worker；按查询/状态统计，避免不同查询混算 P95；查询原文继续省略；公开只读 guard |
| `scripts/frontend_web_vitals_probe.mjs` | 路由+query、核心 DOM、核心成功 JSON API、无错误联合判 ready；Desktop/Phone 分开；waterfall/大小/起止时间/pending 请求；逐 attempt 留存；移除固定完成等待、择优覆盖重试和随机点击/FID 替代 INP |
| `scripts/runtime_resource_probe.py` | 操作前后连续采样，timestamped time series、阶段标签、进程树峰值、可取得 I/O、目标文件大小；应用/browser/operation/probe 分开；仅清理自身操作，窗口启动可握手 |
| `scripts/fullstack_verification_check.sh` | v2 外层报告及共享 context、子报告路径；Web Vitals 保存独立 JSON；资源覆盖共享阶段全窗口并先等首个观测 ready；原阶段/锁/Partial/预算不变 |

严格服务于上述工具的新模块：`scripts/performance_contract.py`（字段、只读身份、分类、真实 HTTP、统计）、`performance_catalog.py`（current/compatible/unused/probe）、`performance_server.py`（临时副本独立进程）、`lib/performance_browser_contract.mjs`（路由与 ready 判定）及 schema。

测试范围为 6 个原脚本测试文件、`backend/tests/unit/test_performance_contract.py`、`scripts/tests/performance_browser_contract.test.mjs`。文档只新增本报告、更新 fullstack reference / docs 地图 / CHANGELOG。没有改变阶段 1 的 backend/frontend 产品代码或测试。

## 旧口径与新口径

| 旧口径 | 新口径 |
|---|---|
| 第一次请求 = cold/cache miss | process-cold、warm、snapshot exact/LKG/missing、并发分别记录；缺证据 unknown |
| 单次或数次也写 P95 | 至少 20 个有效同状态 warm 样本；否则只给 observed values |
| 本地 gzip 再压缩当网络大小 | 捕获真实 HTTP 编码 body；TestClient 标明进程内 transport，不冒充 TCP 网络 |
| warmup/不可用样本省略 | 原样保留，503/404/unavailable/cancel/timeout 均不能计入性能成功 |
| 浏览器等 5 秒、随机点击、重试取较好者 | 5 秒仍是原期限上界，记录 core-ready 后在原期限内收齐 API 终态；无伪 INP；所有 attempt 影响结果 |
| 结束时一次 ps | 整段操作时间序列与采样峰值，浏览器和探针开销单列 |
| 报告缺少数据和状态身份 | 每样本保留 HEAD/dirty、dataset/plays/只读 revision 摘要、参数、snapshot 元数据及可观测性来源 |

旧 results/profiles/snapshots 等主要结构保留；旧 API cold_* 不再塞入无法证明的首请求。CLI 原预算未改。未配置实体/年份/entity_key/job_id 的目录项显式标 configured=false，并列入 unconfigured_targets，不以空统计请求冒充覆盖。

## seed 与 Online Backup 校准

seed 为仓库封闭 fixture 的临时副本：**117 plays**，不混入真实库汇总。真实数据使用阶段 1 留存的 Online Backup 临时副本：**92,908 plays**；保留已有历史索引和已经发布的 sidecar/Home，未做索引修复或算法优化。所有服务绑定临时数据库/sidecar/Home；正式数据库没有作为运行后端或测量写入目标。

数值单位 ms；unavailable 行统计其失败响应的 observed latency，**成功数仍为 0**，没有转成性能通过。

| 校准 | n | 成功 / 失败 | min | median | P95 | max |
|---|---:|---:|---:|---:|---:|---:|
| seed candidates / 3 process-cold | 3 | 3 / 0 | 46.44 | 47.00 | — | 66.53 |
| 93k Records exact / 3 process-cold | 3 | 3 / 0 | 88.06 | 88.11 | — | 92.18 |
| 93k Records exact / warm | 60 | 60 / 0 | 18.11 | 24.48 | 36.48 | 41.02 |
| 93k Records unavailable / 3 process-cold | 3 | 0 / 3 | 128.94 | 171.97 | — | 286.13 |

- Records exact 每个进程 1 次独立 process-cold + 20 次 warm，合计 3 + 60；请求的 source revision 相同。实际 gzip body **43,921 B**，解码 **289,171 B**，不是本地估算压缩。
- unavailable 使用 `bb_top_n=31`，不删除任何快照；3 次均 HTTP 503、探针退出 1。seed Home 的 3 个独立进程也均 503，负例保留。
- Home 的附加 3 次独立进程实际上全部 **exact**（234.50 / 249.13 / 662.87 ms），即使早期证据文件名为 `real-lkg.json`，也以响应状态为准，不声称测到了 LKG。LKG 分类由单元用例验证；本轮真实副本以 unavailable 满足该校准项。
- 即时计算 `/api/analysis/stats` 为 **24,807.96 ms**，HTTP 200，raw **205,638 B** / gzip **34,071 B**；进程为外部服务 unknown，不称独立 cold。仅一个样本，不报 P95。
- seed HTTP candidates 返回 snapshot unavailable；warmup 和后续观测均保留，并以非零退出，不能因为 HTTP 200 就把不可用统计认作成功。

## 浏览器与资源校准

使用阶段 1 留存的 production build、本地副本服务和 Chromium；路径 `/music/album-projects/41476`，5,000 ms 原期限未增加。

| presentation | viewport | core-ready | LCP | 结果 |
|---|---|---:|---:|---|
| Desktop | 1280×900 | 768 ms | 732 ms | core-ready 通过，已发起 API 全部终态且无错误 |
| Phone | 390×844 | 496 ms | 484 ms | 同上 |

每端为一个最终样本，P95=null。服务复用前序请求，浏览器同实例、每次新 target，不将结果写成独立冷启动基线。最终校准 `browser-terminal.json` 两端均无未结束 API。核心时间单独保留，未完成 API 会使整体失败；更早的 core-only 校准仅作工具开发证据，不作为最终性能通过。首次调试曾因空白文档 DOM 尚未建立而导致工具错误；四条失败 attempt 保留在 `browser-calibration.json`，修复的是探针读取时机，不是页面或预算。

资源校准包围上述慢 analysis 请求，**70 个 timestamped 样本**，阶段标签 `analysis-stats-request`。应用同时刻采样 peak RSS **1,917.7 MB**；backend 树 **1,909.9 MB / 100.845% CPU**；frontend **15.4 MB**；operation **29.3 MB**；probe **20.1 MB** 单列。没有把 probe/browser 算入应用预算。macOS 此运行未提供 psutil 进程 I/O counter，read/write 为 null，不伪报 0。

DB、WAL、Billboard sidecar、Home 目录的大小变化均为 0；这是资源大小观测，不宣称其内容零写入。SQLite SHM 读锁边界沿用阶段 1 报告。浏览器校准另记录 8 个资源点，browser peak RSS 684.5 MB、operation 146.8 MB、probe 19.6 MB，PID 分组无重复。服务是既有服务，资源工具没有终止它们；本轮结束由任务清理自己启动的两个服务。

## 已可测与仍缺埋点

| 状态/量 | 当前可靠范围 |
|---|---|
| 独立 process-cold / 同进程 warm | owned server、搜索 worker 有独立身份；外部 API 可核对监听 PID 连续性，首个请求仍 unknown；多 worker 的具体服务 worker 未暴露 |
| exact / LKG | 有阶段 1 response metadata 时直接分类，保存 source/target；LKG warming 不推断后台执行 |
| missing/unavailable | 503 或 snapshot_status unavailable 被保留为失败；物理缺文件、损坏内容和 key 异常仍需副本准备记录区分 |
| rebuilding | schema 支持，但仅响应 warming 不足以证明。实时 JobQueue 生命周期与发布切换需要以后产品埋点或与任务观测关联，本轮没有假造这个状态 |
| request/cache key、builder version | 字段存在，但当前多数响应未暴露；保留 null/not_exposed，没有复制产品 key 算法猜测 |
| builder/singleflight 次数、SQL 阶段/行数 | 未公开则 null；不能用 HTTP 请求次数代替。现有 Server-Timing 原样记录，其余留待后续埋点 |
| 数据相同证明 | dataset/plays/schema/revision 摘要可用于固定副本对比；不能检测所有绕过 revision 的原地修正。URL 与数据库的绑定由调用方负责，未声明不偷猜 |
| 资源峰值 / I/O | 是采样观测峰值；极短子进程可能漏采，I/O 依赖平台能力。这里不把单次 ps 或 unavailable I/O 宣称为全窗口完整计数 |

## 验证与停止点

- 定向 Python 测试：58 passed（含既有 LibreSSL/urllib3 环境 warning）；资源窗口握手相关子集另有 39 passed 复验（非额外 39 个独立用例）。
- Node core-ready / 重试 / 页面目录 / API 终态测试：4 passed。
- Python Ruff、编译检查、Node 语法、`sh -n`、JSON Schema 校准验证、文档审计（93 文件）和 `git diff --check` 均通过。
- 全栈执行 local dry-run 及 `--only optional --resource-snapshot` 集成校准：optional PASS（1,502 ms），两条带 optional 标签的资源观测，summary v2 为 **PARTIAL**；没有执行默认完整门禁。
- 阶段 1 基线快照在 `/tmp/spotifystats-stage0.GFfiTJ/phase1-baseline.json`。产品与阶段 1 测试文件内容校验未变；共享 docs/README、CHANGELOG 只追加阶段 0 内容。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage0`。包含 schema 校准报告、API 原始样本、browser waterfall、资源序列、失败/调试日志与测试日志；数据库副本、浏览器 profile 和 build 目录未放入仓库或报告目录。

阶段 0 在工具实现、定向验证和文档后停止；不开始阶段 0.5、阶段 2 或任何缓存、索引、响应、请求组织及重建算法优化。
