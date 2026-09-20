# 全栈验证与阶段执行规则

> 更新日期：2026-09-20
> 状态：当前规则
> 适用范围：本地 Phase 5、全栈门禁、局部排障和机器可读验收报告

## 1. 完整门禁

启动开发后端和前端后，标准入口保持不变：

```bash
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

默认完整门禁按以下阶段执行：

1. `preflight`：migration 注册表、脚本语法、全部 Markdown 链接、OpenAPI 静态覆盖和 `git diff --check`；
2. `quality`：pre-commit；Phase 5 的文档审计、CI parity、Ruff、前端测试和 production build；
3. `backend`：两个独立 pytest 进程分别执行完整 seed suite（排除 integration 目录）和显式真实数据 integration；collection 不重不漏，合并为一个 backend 阶段，不再由 Phase 5 重跑 unit/contract；
4. `api`：API smoke、boundary 和 首个观测请求 + 21 个同进程请求 benchmark（首个请求不推断为 cold）；
5. `browser-routes`：完整路由与重点视口矩阵；
6. `browser-interactions`：桌面/移动交互和图表交互；
7. `browser-inventory`：控件盘点与长列表；
8. `browser-compat`：Chromium、Firefox、WebKit。

`preflight` 必须先于完整后端测试运行，让 migration、文档、脚本和 OpenAPI 覆盖等确定性错误在昂贵阶段前失败。`--only` / `--from` 仍可在局部排障时显式选择后续阶段；这种结果继续只算 `PARTIAL`。

quickstart、resource time series、Web Vitals 和 preview 矩阵仍由原有显式参数启用，记录在 `optional` 阶段。本地完整 Pass 不推断 preview、真实部署或远程发布已经通过。

## 2. 局部排障

稳定阶段键可通过以下命令查看：

```bash
sh scripts/fullstack_verification_check.sh --list-stages
```

只重跑指定阶段：

```bash
sh scripts/fullstack_verification_check.sh \
  --only browser-inventory,browser-compat \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

从指定必需阶段运行到末尾：

```bash
sh scripts/fullstack_verification_check.sh \
  --from browser-inventory \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

`--only` 与 `--from` 互斥。`--dry-run` 只解析命令计划，不执行检查。局部和 dry-run 即使退出码为 0，也只能标为 `PARTIAL`，不能替代默认完整门禁。

## 3. 状态和报告

阶段状态：

- `PASS`：实际执行并通过；
- `FAIL`：实际执行但失败；
- `BLOCKED`：后端、前端或 Playwright 等前置条件缺失；
- `SKIPPED`：由显式参数或父门禁分工跳过；
- `NOT_RUN`：不在本次选择范围。

整体只有在默认完整模式的全部必需阶段通过时才为 `PASS`。局部成功或 `--skip-cross-browser` 为 `PARTIAL`；断言失败为 `FAIL`；前置条件无法满足且没有断言失败为 `BLOCKED`。

每次运行都生成唯一 run ID，并把规范结果写入 `/tmp/spotify-fullstack-verification/<run-id>/summary.json`。`/tmp/spotify-fullstack-verification/latest` 以原子 symlink 指向最近完成写入的运行目录。`--summary-json` 或 `SUMMARY_JSON` 只增加一个兼容副本，不会取代 run-scoped 规范证据。报告包含：

- run ID 和独立运行目录；
- selection mode 和实际阶段范围；
- 每个阶段的状态与 `duration_ms`；
- 总耗时、Git HEAD、dirty 标记；
- backend/frontend/preview URL；
- 共享阶段锁路径及本轮获取/阻塞事件；
- 未执行和跳过阶段。

脚本失败时也必须写出已完成阶段，不能只凭最终退出码判断覆盖。

使用真实数据库副本做验收时，应显式设置 `SPOTIFY_STATS_TEST_SOURCE_DB`：

```bash
SPOTIFY_STATS_TEST_SOURCE_DB=/absolute/path/to/acceptance-copy.db \
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

父门禁把该路径用于显式真实数据 integration 插件和两个 API acceptance 探针；普通 seed suite 不受该环境变量影响。integration 进程最多建立一份 session 可写副本，Analysis 参数化 unit 测试始终复制小型 seed。`api_smoke_probe.py`、`api_boundary_probe.py` 不得在已指定副本时重新打开默认数据库；否则探针触发的 schema/派生缓存写入会污染正式本地库。HTTP benchmark 与浏览器阶段仍以传入的 `backend-url` 为准，因此该后端进程也必须使用同一验收副本启动。

## 4. 共享阶段排他

`api`、浏览器阶段和显式 `optional` 性能探针使用主机级 Python `fcntl` 锁。设置 `SPOTIFY_STATS_TEST_SOURCE_DB` 时，`backend` 阶段也保留该排他区，避免多个 worktree 的测试与真实验收争用 CPU。锁只覆盖共享/性能阶段，不覆盖廉价 preflight 和普通 quality。

默认锁为 `/tmp/spotify-fullstack-verification.lock`。锁持有者元数据记录 run ID、父 PID、holder PID、worktree、Git SHA、UTC 开始时间和当前阶段。竞争者不会继续执行并制造性能 `FAIL`，而是将所见 owner 写入自己的 run 目录并把阶段和整体状态标为 `BLOCKED`。进程正常退出、失败或收到中断时都会释放锁；`fcntl` 还保证 holder 异常退出后由操作系统回收锁。

如需隔离测试，可用 `FULLSTACK_LOCK_FILE`、`FULLSTACK_LOCK_METADATA_FILE` 和 `FULLSTACK_RUN_ROOT` 改写位置，但正式证据应使用默认主机级位置。

实际运行由存储保护进程创建独立 TMPDIR 与 pytest basetemp，成功/失败均清理；12 GiB 最低可用空间、2 GiB 本轮临时文件上限及证据字段见[后端测试隔离](backend-test-isolation.md)。数据副本和报告不放进待清理目录。存储保护触发后停止本轮，不自动重试。

## 5. Phase 5 边界

独立运行 `sh scripts/phase5_check.sh` 时，仍完整执行文档审计、CI parity、unit、contract、Ruff、前端测试和 build。

`--skip-backend-tests` 只供同一次总门禁使用：父门禁的 `backend` 阶段负责一次完整 pytest，Phase 5 不再追加 marker 重跑。pre-commit Ruff 与 Phase 5 Ruff 使用不同版本/参数，因此当前仍各自保留，不把它们误判成等价重复。

## 6. 证据边界

- 默认完整门禁 Pass：可描述为本地开发后端与 Vite 开发前端的项目全栈门禁通过。
- `--only` / `--from` Pass：只能描述所选阶段通过，整体为 Partial。
- `--skip-cross-browser`：不得描述三浏览器通过。
- 未设置 `--preview-url`：不得描述 production preview 通过。
- 本地门禁不代表真实部署、远程生产、备份或发布通过。
- 阶段耗时必须引用当前 JSON；历史报告中的数字只代表当时快照。


## Analysis 移动交互的 unavailable 验收

`mobile-section-sheet` 使用已发布的 lifetime 验证栏目切换并保留时间 Query；year/period_value 的保留继续由 `mobile-shell.test.tsx` 的实际栏目点击测试覆盖。

`mobile-time-filter` 必须从 lifetime 真实点击“近 4 周”并应用，最终 URL 为 `period=last_4_weeks`。当前非 lifetime 合同要求结构化 503 `snapshot_unavailable`；脚本必须同时核实已完成响应的 error/status/family/message、可见“播放统计暂不可用”和后端原始消息、无加载骨架与统计 KPI。只有这个场景、这个已核实请求 ID 和 URL 对应的浏览器原生 network 503 日志可记为 `expectedUnavailable`，原始日志与 HTTP detail 仍保留。普通 503/500、其他资源失败、应用 console.error/assert、warning 和 JS/page error 继续失败。

这是错误状态消费的交互验收，不把 unavailable 计为 ready 或成功 API 性能样本，也不改变路由 core-ready 门槛。GET 不构建、不写入、不排队；测试不自动发布非 lifetime 快照。`--screenshot-dir` 可保存每个交互场景结束时的截图。

## 7. 统一性能测量合同（阶段 0）

规范 JSON Schema 为 [`scripts/performance-report.schema.json`](../../scripts/performance-report.schema.json)，版本 `spotify-performance/1`。六个工具共享该样本合同；全栈外层阶段报告升级为 `schema_version: 2`，保留原有阶段、run ID、状态、时长、锁事件字段，并引用同一次运行的 performance context 和各子报告。校准证据见 [阶段 0 报告](../reports/2026-09-19-performance-measurement-contract.md)。

### 7.1 样本字段

| 字段 | 含义与边界 |
|---|---|
| schema_version / sample_id / kind | 合同版本、唯一样本 ID、api/page/service/resource 类型 |
| git.head / git.dirty | 运行时本地 HEAD、包含未跟踪文件的工作区 dirty；不是生产版本 |
| database | identity 是绝对路径的 SHA256；dataset 显式为 seed / online_backup / unknown；plays 是只读 COUNT；revision/fingerprint 对 schema、plays count/max-rowid、playback_import_state 和 music_search_revision_state 做摘要，不输出原始播放行。它不是全库内容哈希；绕过 revision 的等数量原地修改不能由此独立证明相等 |
| target / params / filter_fingerprint | 完整目标、请求参数及规范摘要；scope 明确仅覆盖提交参数，服务端默认值未公开时不冒充有效过滤全集。Search 专用工具以 query_hash/长度保留查询身份，省略原文 |
| presentation / viewport | 页面分 Desktop / Phone，保留宽高；API 为 not_applicable |
| process | state 为 cold / warm / unknown / not_applicable，附 id/evidence。cold 仅来自探针自己创建的新服务/搜索 worker；外部服务首个请求 unknown，重复请求经监听 PID 身份核对后标 warm。warm 不意味着内存缓存 hit |
| snapshot | state 为 exact / LKG / missing / rebuilding / unknown / not_applicable；保留 source_revision、target_revision、builder_version、request_key、cache_key 和证据来源。未暴露字段为 null，不能从首请求、低延迟或 warming 文案猜测。missing 表示不可消费的发布，也可能是内容损坏/key 异常；warming/LKG 不证明有后台任务正在运行 |
| http | status、error_type、raw_bytes、compressed_bytes、content_encoding、size_evidence；HTTP API 使用实际流的编码 body 字节及解码字节，不进行本地模拟压缩。它不含 TLS/HTTP framing 开销。搜索 TestClient 明示 in_process_http_transport_body；直接 service 模式压缩/HTTP 不适用 |
| timing | total_ms、phases_ms；Server-Timing 与可取得的客户端 header/body 时刻。非暴露阶段不补造数字 |
| started_at / ended_at | Unix 秒时间；浏览器 waterfall 另保留 CDP 单调时钟 start/response_start/end 及 wallTime |
| attempt / sequence / concurrency_group | 重试序号、请求次序及并发组；loading 同 key / 异 key 并发分别标记。浏览器每个目标/视口的 attempt 和每个 API 重试均保留 |
| instrumentation | builder_calls / singleflight_calls 未公开时 null，evidence=not_exposed；请求数不能冒充 builder 次数 |
| success | HTTP/应用状态和页面 core-ready 共同决定；503、404、timeout、cancel、错误页、缺失事实和错误 skeleton 不成为成功样本 |

数据库身份由 `--db-path --dataset` 或 `--context-file` 提供。调用方必须确保声明的数据库就是本地服务实际使用的数据库；工具不能从一个 URL 自动证明这个绑定。未声明时保留 unknown，不偷读默认正式库来填数。存储、rebuild 与 counter 的 unknown 和已知不适用的 not_applicable 分开。

### 7.2 统计与退出

- 独立 process-cold 每种目标/参数/状态至少 3 个不同进程；`benchmark --independent-processes` 少于 3 拒绝执行，Search `--cold` 默认 3 次。操作系统 page cache 不清除，cold 时长是新进程中的请求时长，不包含服务启动就绪时间。
- 仅在同一目标、过滤、presentation、数据 fingerprint、snapshot 状态/来源/版本和并发类别下，至少 20 个有效 warm 样本才报告 nearest-rank P95。不同状态不混池。cold 的 3 次只给 observed values，不称稳定 P95。
- 报告保留全部原始样本、成功/失败数、min、median、P95、max、失败观测值。主分位数只使用成功样本；失败延迟不是成功性能。
- warmup 和全部 retry 都保留；浏览器不再选两次中较快的一次替换结果。重试成功不能抹去首次失败，也不能把本轮改为整体通过。
- 非预期 HTTP、应用 unavailable 和传输失败非零退出。配置了 P95 门槛但样本不足时也不能通过。既有数值预算和 timeout 不变。
- 旧 `results`、Search `profiles`、资源 `snapshots` 字段保留。API 旧 cold_* 字段不再承载首请求，保持 null/空；hot_* 只是同进程观测的兼容名；旧 gzip_kb 仅在实际编码为 gzip 时填值。规范统计优先看 samples/statistics。

### 7.3 API 与浏览器范围

`benchmark_api.py --catalog` 输出 GET 目录及 usage（current / compatible / unused / probe），覆盖 Home、analysis stats/charts/records/plays/play-dates、Billboard 家族、Search 两阶段、实体 summary/非核心 view 与 stats/子视图、年度、档案、Community 和 Settings 读取/维护状态。默认不运行 unused；当前周榜、总榜、榜首与 Records 页使用显式 projection，完整响应单列为兼容接口。目录的 `surface` 区分公开读取和私有治理/维护消费者；默认 `--surface auto` 按此选择，显式 surface 仍可用于边界检查。零个可执行目标必须失败，不能空跑通过。实体/年度必须提供相应 ID/名称/年份，Search statistics 应提供有效 entity_key，导入状态需 job_id，Community 帖子详情可用 `--post-id`；未配置项以 configured=false 和 unconfigured_targets 保留，不执行空集合请求来冒充覆盖。

浏览器路由合同集中在 [`scripts/lib/performance_browser_contract.mjs`](../../scripts/lib/performance_browser_contract.mjs)。覆盖 Home、三种播放分析、Weekly/All-time/Year-end/Records、Search、歌曲/专辑项目/艺人详情、年度总结、音乐档案、Community 和 Settings。默认动态详情通过 `--route-params '{"track_id":123,"project_id":456,"artist":"Example"}'` 填充；未提供时明确失败，不静默省略。`--viewport both` 分开输出 Desktop 和 Phone；`mobile` 是原 Phone CLI 别名。

core-ready 必须路由和 query 正确、核心事实 DOM 出现、核心 API 完成且返回有效 JSON、没有已观测错误响应/提示/错误 skeleton。实体还检查 `.entity-stats-kpi-grid`。每个 URL 的 waterfall 保留重试、状态、body/transfer 大小、起止时刻与 initiator。非核心仍在途的请求列入 pending_requests。core_ready_ms 单独保留；整体 success 还要求原观察期限内所有已发起 API 得到终态，未结束标为 IncompleteAPIRequests，不能通过关闭浏览器取消它们后报成功。

`--wait-ms 5000` 保留为原有观察期限上界，已不再固定等待 5 秒后判成功；事件驱动观测以短轮询读取 DOM，条件满足立即记录 core-ready 时间，随后仅在原期限内收齐 API 终态。LCP/CLS/long-task TBT 在同一观察窗内采集，未产生真实交互序列时 INP=null；移除随机点击与 FID 替代。新目标页仍共享该次 Chrome 的正常浏览器 cache，browser_instance 明示此点，不能把每页称为独立 browser cold。

### 7.4 资源窗口与阶段标签

`runtime_resource_probe.py --command ...` 在操作启动前开始、退出后结束采样；也支持 `--duration`，或父进程创建 `--stop-file` 结束窗口。不启动独立采样子进程。SIGINT/SIGTERM 清理自己启动的操作进程组，不停止按端口发现的既有服务。直接调用旧 CLI 且没有窗口参数时仍为 legacy point observation，不能作为操作峰值证据。

每点记录 timestamp、phase、应用进程树、browser（由浏览器 PID 文件绑定）、operation 和 probe 自身。RSS/CPU 峰值从整段序列计算；总应用峰值取同一时刻的树总和，browser/probe 独立报告。psutil 已可用时采集区间 CPU 和 I/O；未安装或平台不暴露 I/O 时 null 并标注原因，不引入新依赖。不捕获采样间隔内已退出的极短子进程峰值，属于采样上界限制。`--watch-file` 可重复监视 DB、WAL、sidecar 或 Home 目录的大小变化；大小不变不等于内容零写入。

调用方更新 `--phase-file` 的文本即可切换阶段。全栈 `--resource-snapshot` 现在包围每个已选择的共享阶段，按 `resources-<stage>.json` 保存；旧 RESOURCE_SNAPSHOT_JSON 仍接收最近一次兼容报告。预算使用峰值，阈值不变，可能因此暴露旧结束快照漏掉的问题。

### 7.5 可复现调用与安全

所有 HTTP/browser 目标限 loopback，浏览器阻断外部请求及写方法。独立进程 harness 仅接受临时数据库及 snapshot root，关闭 lifespan/启动维护，外网连接被拒绝。它不创建事实、不自动迁移或发布；需已有 seed/Online Backup 副本。正式快照不得删除或改名来造 missing；缺失、revision 注入、重建仅可在临时副本准备。

```bash
# 身份由调用方绑定到实际服务副本；声明不是远程服务自动证明。
.venv/bin/python scripts/performance_contract.py   --db-path /tmp/measurement/data/spotify_stats.db --dataset online_backup   --output /tmp/measurement/context.json

# 三个独立服务进程，各一次 process-cold + 20 次同进程 warm。
.venv/bin/python scripts/benchmark_api.py   --db-path /tmp/measurement/data/spotify_stats.db --dataset online_backup   --snapshot-root /tmp/measurement/data --independent-processes 3 --runs 21   --endpoint /api/billboard/records --json-output /tmp/measurement/api.json

node scripts/frontend_web_vitals_probe.mjs   --base-url http://127.0.0.1:5173 --context-file /tmp/measurement/context.json   --routes /music/album-projects/456 --viewport both   --output /tmp/measurement/pages.json

.venv/bin/python scripts/runtime_resource_probe.py   --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173   --context-file /tmp/measurement/context.json --phase-file /tmp/measurement/phase.txt   --watch-file /tmp/measurement/data/spotify_stats.db   --watch-file /tmp/measurement/data/spotify_stats.db-wal   --watch-file /tmp/measurement/data/billboard.db --watch-file /tmp/measurement/data/home   --json-output /tmp/measurement/resources.json   --command .venv/bin/python scripts/benchmark_api.py     --base-url http://127.0.0.1:8000 --endpoint /api/analysis/stats --runs 1     --context-file /tmp/measurement/context.json
```

全栈可用 `PERFORMANCE_DB_PATH`、`PERFORMANCE_DATASET`、`PERFORMANCE_ROUTE_PARAMS`、`RESOURCE_WATCH_PATH` 传入同一上下文；没有显式 PERFORMANCE_DB_PATH 时继承 SPOTIFY_STATS_TEST_SOURCE_DB，但 HTTP 服务仍须由调用方绑定到同一副本。局部校准仍为 Partial，不替代完整应用验收或生产 SLA。
