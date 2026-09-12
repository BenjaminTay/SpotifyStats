# Billboard 持久化快照优化升级验收报告

状态：`IMPLEMENTED`；验证：`PASS（本地与生产）`；远端：`PUSHED（codex/agent-v5-main-integration）`；生产：`DEPLOYED（5a5e37779a58f3c49bcaf1b5896af9d9877eba29）`。

日期：2026-09-13

## 结论

已完成 Billboard 周榜、总榜、完整 staged 数据和年榜的持久化快照与事件驱动重建，并已部署到生产。相同数据库、参数和来源 revision 下，普通 GET 优先读取 SQLite sidecar；进程重启或内存 LRU 清空不再自动触发 DataFrame 冷计算。播放导入、统计设置、聚合重建、元数据治理和版本归并完成后，JobQueue 去重排队后台重建，旧快照继续承担 LKG 返回边界。

前端已删除年榜首响应后对全部年份的自动预取，只在切换到某年时请求该年份；TanStack Query 页面缓存和切年时的旧数据占位保留。

## 主要实现

- 新增 `billboard_snapshots` SQLite sidecar：压缩 payload、source revision、builder version、checksum、exact key 和 request-level LKG。
- key 纳入数据库路径、播放事实 revision、Billboard revision、聚合 builder、年榜语义版本、参数和开放周边界，避免不同数据库或参数互相污染。
- 周榜、power scores、summaries、records、总榜组合、完整 Billboard 和年榜均接入 cache-first wrapper；重建失败不覆盖旧 LKG。
- 新增 `billboard_snapshot_rebuild` JobQueue handler，应用启动和真实数据/设置/治理变更完成后触发，CPU-heavy gate 保证 Billboard 重建串行。
- 公共只读面只读既有 sidecar，不创建或写入缓存；损坏 payload 会跳过并回退计算。

## 验证证据

### 测试与门禁

- 后端 unit：`1687 passed, 1070 deselected`。
- Billboard 关键 contract：`23 passed`。
- 完整 contract：`419 passed, 2338 deselected`。
- 前端全测：`622 passed`。
- 前端生产构建：`vite build` 通过。
- 重要回归：启动顺序、JobQueue 去重、缓存损坏/参数隔离/force rebuild、设置接口响应模型、年榜单年请求和 Phase 5 架构门禁均通过。
- 文档审计：`python3 scripts/docs_audit.py` 通过。

完整 contract 过程中观察到一个已有 AI 后台线程在测试清理时报告 SQLite `disk I/O error` 的 `PytestUnhandledThreadExceptionWarning`；该警告未导致 contract 失败，也不属于本次 Billboard 变更范围。

### 重启命中集成探针

在复制的 `backend/tests/fixtures/seed.db` 上使用独立 sidecar：

| 请求 | 首次冷建 | 清空进程内 LRU 后 | 结果 |
|---|---:|---:|---|
| 周榜 | 0.638s | 0.009s | JSON 等价，未再次调用 builder |
| 年榜 | 0.422s | 0.012s | JSON 等价，未再次调用 builder |

探针 sidecar 最终包含 `weekly=1`、`year_end=1` 两条持久化快照。此处耗时用于验证机制，不代表生产 92,908 条播放数据的冷建耗时。

### 生产发布与线上验收

- 发布工作流 `34707096113` 将 `8cba7661` 部署为基线；修复健康重启重复重建后，工作流 `34709561695` 将 `5a5e3777` 部署到 dual 模式。三个生产容器均为 healthy，当前 `IMAGE_TAG=5a5e37779a58f3c49bcaf1b5896af9d9877eba29`。
- 首次生产后台构建完成后，sidecar 已有 `all_time=1`、`full_data=1`、`records=1`、`weekly=4`、`summaries=4`、`power_scores=4`、`year_end=7`；额外行来自参数版本隔离和变更演练，不影响当前 exact key。
- 生产重启后日志为 `Billboard snapshots already current; startup rebuild skipped.`，任务表没有新增运行中的启动重建任务，`bb_top_n=30`、`rebuild_pending=false`。
- 服务器本机 public gateway 实测：`/api/billboard/weekly` HTTP 200 / 4.886s，`/api/billboard/all-time` HTTP 200 / 0.564s，`/api/billboard/year-end` HTTP 200 / 0.031s；均低于 30 秒。周榜约 4.65 MB 响应体的耗时主要来自响应传输与 Nginx 缓冲，不是每次打开重新跑全量计算。
- 真实设置变更 `bb_top_n:30 -> 31` 返回 200 并排队 `billboard_snapshot_rebuild`；旧快照仍可用。该临时重建运行约 30 分钟后观察到后端 RSS 约 2.4--2.75 GiB、主机可用内存降低，因此在恢复 `bb_top_n=30` 后主动取消并记录为 failed，未把临时半成品当作生产快照。
- 回滚脚本两次均在音乐搜索数据库副本预检阶段拒绝，错误为 `MusicSearchStatisticsReuseRequiredError`；第二次清理了与当前源修订不符的续建副本后仍拒绝。生产容器、主库和当前 Billboard 快照均未切换，说明旧版本兼容性门禁有效。要让该旧版本真正可回滚，需先为它准备兼容的音乐搜索派生快照。

## 发布边界

- 代码已按 commit SHA push 并部署；生产数据库备份、快照预建、重启和线上 API 验收均有独立证据。
- 回滚未强行切换到不兼容旧镜像；当前结果是“回滚门禁保护性通过”，不是“旧镜像已完成线上回滚”。
- 本次优化已经解决无数据变化时的打开路径；完整临时设置变更重建暴露出生产资源压力，后续若要缩短重建窗口，应另立任务做分阶段/限内存的 builder 优化，不应恢复请求内冷建。
