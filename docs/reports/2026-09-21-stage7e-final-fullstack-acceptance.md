# 阶段 7E：Analysis 浏览器合同、测试存储与最终全栈验收

> 日期：2026-09-21
> 结论：阶段 7E 本地全栈 Pass，整轮性能优化正式完成；代码、测试与本报告纳入同一个本地阶段检查点。

## 提交与范围

阶段 7C Analysis revision 提交为 `410d0b971dfdd8bd9efb750030a4dfeaf7f8a63b`。Import Preflight 独立提交为 `53dbf90e1af781c79a846ab6eb50c2426e8c4dca`，原始 profile、三进程 cold、21 个 hot 与缓存合同见[阶段 7D](2026-09-20-stage7d-import-preflight.md)。

本阶段统一收口 Analysis/browser 验收合同、seed/integration 数据源分层、测试临时目录生命周期及存储保护。未改变产品统计/导入算法，未新增任意日期快照架构。验证时 HEAD 为上述 Import commit，工作区包含本阶段修改；本检查点最终 SHA 由提交后 Git 回执记录，避免在提交内自引用 SHA。README 的 unit/contract 入口不需修改，AGENTS/CLAUDE 未变化。

## Analysis/browser 正式合同

历史两个失败请求分别为 custom 2025-01-01..2025-12-31 和 last_4_weeks。两者均为结构化 503：error=snapshot_unavailable、status=unavailable、family=analysis_stats，消息为“此时间范围尚未提供已发布快照，请切换为全部时间。”，不是普通 500、网络错误或 key 异常。

真实页面已正确退出 skeleton，显示 role=alert 的“播放统计暂不可用”和原始消息，无假零、page error 或未处理 Promise rejection。顺序 HTTP 观测各 7 条 SQL / 27 行，builder/write/enqueue 均零。原浏览器脚本把预期 resource 503 误判为应用故障；本轮不修改前端产品消费代码。

- mobile-section-sheet 改用已发布 lifetime 验证栏目切换与时间 Query；新增实际点击单测继续覆盖 year/period_value=2025 的保留，既有反向切换、Escape 和焦点恢复保留。
- mobile-time-filter 仍真实点击“近 4 周”并应用，必须满足最终 URL last_4_weeks、完成的结构化 HTTP detail、可见原始 unavailable 消息、无骨架/统计 KPI。只允许该场景中同 request ID、同 URL 的原生 network 503 日志归类 expectedUnavailable。普通 503/500、其他资源错误、应用 console.error/assert、warning、page error 仍失败。
- 三引擎的两个定向场景均通过，截图、HTTP、console、最终 Query 和异常证据保存在阶段 7E 根目录；前端定向 39 项、脚本 4 项通过。此前局部 browser-interactions 仅记 Partial；本次默认完整运行再次实际执行并通过移动场景。

UI 继续暴露多种日期范围，自动维护仅保证默认 lifetime。任意范围是否立即可用、如何发布，以及 unavailable 下筛选入口的可达性留作产品决策；GET 不冷建、不写入、不排队。

## 测试存储放大与数据源分层

旧 SOURCE_DB 隐式进入全体 pytest，Analysis 每个参数 case 再复制约 424 MiB。按 28 个 case 加 1 次进程初始化，旧调用链每轮约 29 次真实文件复制（约 12.0 GiB）；两轮约 24.4 GiB 是此前磁盘核查结果，本轮没有重新制造这些副本。

普通 unit/contract/非 integration 始终取 tracked seed，Analysis case 直接复制小型 immutable seed，显式关闭 backup 连接，在成功或异常 teardown 删除其 DB/WAL/SHM 和发布文件。只设置 SOURCE_DB 不会改变 seed suite。

真实 integration 通过命令级 `-p backend.tests.real_data_integration` opt-in，插件在父 conftest/应用导入前选定已有 `/private/tmp/spotifystats-stage7c/data/main.db`，只接受 integration 路径，整个进程只创建一个 session 可写**文件副本**。未降低任何真实分布断言，API acceptance 继续显式 --db-path 使用该现有工作副本。

integration 定向记录 **1 次源文件到 session 文件 backup**；艺人身份测试另有 **11 次既有 :memory: backup**，逐一保留在 integration-copies.json，不形成 per-case 磁盘副本，也未将这些内存操作隐去。定向进程退出后 session 副本删除；完整门禁在新的独立进程中采用同一单 session 初始化路径。

### Collection 与定向验证

复用本轮之前已通过、测试节点未受此次父目录修复影响的 collection 原始列表：

| 分区 | 数量 |
|---|---:|
| 完整 backend/tests | 3039 |
| seed suite | 2852 |
| integration | 187 |
| missing / extra / intersection / duplicate | 0 / 0 / 0 / 0 |

seed 定向 **77 passed**，真实库复制 **0 次**，53 次小型 backup，其中 Analysis 28 个 case 的目录均已验证删除。integration 定向 **186 passed / 1 既有 skip**，此前 88 个失败节点全部通过，耗时 199.94s。skip 为 Genius 客户端不可用的既有条件测试，没有跳过那 88 项。存储与隔离/脚本回归 **45 passed**。

### Basetemp 与保护

storage guard 在启动子进程前集中创建 owned_root/pytest，再导出 BASETEMP；seed-directed、integration-directed、seed、integration 各自使用子目录。父目录创建、正常/测试失败/中断清理、其他任务 canary 保留、12 GiB 可用空间边界、2 GiB 临时文件边界均有定向测试。边界测试以受控测量值触发，不为测试真实分配 2 GiB。

整个服务与门禁树使用同一 run-owned TMPDIR；200ms 采样，超过 2 GiB 或可用空间低于 12 GiB 即停止且不自动重试。正式数据源、已有 stage7c 工作副本和永久证据不在清理范围。

| 运行 | 采样峰值 MiB | 退出清理 |
|---|---:|---|
| seed 定向 | 5.969 | 成功 |
| integration 定向 | 430.448 | 成功 |
| 默认完整 fullstack（含服务） | 626.924 | 成功 |

完整运行峰值 **657377834 bytes**，最低可用空间 **121.738 GiB**，保护未触发，owned_root 已删除。报告保留全量采样；不声称采样间隔内的绝对瞬时峰值。

## 唯一一次新的默认完整 fullstack

当前请求授权后只运行一次，run ID `20260920T160333.344990Z-20a995560f64`，selection=full，overall=PASS，耗时 **1317354ms**。没有 --only/--from、没有历史局部结果拼接，没有改变并发、500ms 门槛或 21 个 hot 样本。历史磁盘失败、integration 错用 seed 和 basetemp 定向失败证据均保留，未覆盖。

| 阶段 | 状态 | duration_ms |
|---|---|---:|
| preflight | PASS | 7746 |
| quality | PASS | 42253 |
| backend | PASS | 408998 |
| api | PASS | 164643 |
| browser-routes | PASS | 401824 |
| browser-interactions | PASS | 80282 |
| browser-inventory | PASS | 46965 |
| browser-compat | PASS | 164329 |
| optional | NOT_RUN | 0 |

backend 合并两个独立 pytest 进程：seed **2850 passed / 2 skipped，214.64s**；integration **186 passed / 1 skipped，183.97s**。合计 **3036 passed / 3 skipped**，总节点 3039 与分区对账一致。原始 JUnit XML 分别保存两部分数量、失败/跳过与耗时。

前端完整测试 **659 passed / 4 skipped**，production build、hooks 和文档检查通过。既有 warnings 原样保留在日志，未隐藏。

API **51 个目标**，slow_count=**0**；Import Preflight 22 次全部 HTTP 200，首个观测请求 4223.146ms（外部服务首请求不冒称独立进程 cold），21 个 hot P95 **64.329ms ≤500ms**。hot 原始 ms：

64.147, 63.425, 63.273, 63.509, 63.030, 63.745, 63.160, 63.382, 63.805, 63.298, 63.405, 63.459, 63.359, 64.080, 64.329, 64.387, 63.215, 63.674, 63.130, 63.164, 63.376

browser-routes、browser-interactions、browser-inventory、browser-compat 四阶段均 PASS；两移动场景在默认运行实际通过，控件/长列表通过，Chromium、Firefox、WebKit 全部 PASS。optional 未请求，不将其或生产部署描述为已验收。

## 正式数据、证据与停止边界

正式 data 前后 **4183 → 4183** 文件：新增 0、删除 0、size/SHA-256/mtime 改变全为 0；定向后和完整门禁后均逐文件对账。主库、sidecar、导入源文件未修改，未恢复已删除 stage0–7B 目录。

最终证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0be86-06d0-7b51-b1ad-8a3f70c1a9ee/spotifystats-stage7e/basetemp-closeout`。包含复用的四份 collection 清单/对账、seed/integration 原始 copy 记录、88 节点恢复对账、测试日志、各轮磁盘全量采样、正式数据前后清单、fullstack-summary.json 与 runs 下规范 summary/API benchmark/JUnit。早期浏览器原始截图与 HTTP/console 证据在父级 spotifystats-stage7e 目录。

本轮 8000/5173 服务已停止，run-owned 临时目录清理完成。最终本地提交回执、HEAD、缓存 origin/main 的 ahead/behind 与 clean 状态另外写入本机证据。未 fetch、未 push、未部署、未运行或打开 Docker、未调用应用 AI/LLM、未访问 Spotify 或其他外部服务，未同步正式数据。
