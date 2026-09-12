# Billboard 持久化快照优化升级验收报告

状态：`IMPLEMENTED`；验证：`PASS（本地范围）`；远端：`UNPUSHED`；生产：`NOT_DEPLOYED`。

日期：2026-09-13

## 结论

已完成 Billboard 周榜、总榜、完整 staged 数据和年榜的持久化快照与事件驱动重建。相同数据库、参数和来源 revision 下，普通 GET 优先读取 SQLite sidecar；进程重启或内存 LRU 清空不再自动触发 DataFrame 冷计算。播放导入、统计设置、聚合重建、元数据治理和版本归并完成后，JobQueue 去重排队后台重建，旧快照继续承担 LKG 返回边界。

前端已删除年榜首响应后对全部年份的自动预取，只在切换到某年时请求该年份；TanStack Query 页面缓存和切年时的旧数据占位保留。

## 主要实现

- 新增 `billboard_snapshots` SQLite sidecar：压缩 payload、source revision、builder version、checksum、exact key 和 request-level LKG。
- key 纳入数据库路径、播放事实 revision、Billboard revision、聚合 builder、年榜语义版本、参数和开放周边界，避免不同数据库或参数互相污染。
- 周榜、power scores、summaries、records、总榜组合、完整 Billboard 和年榜均接入 cache-first wrapper；重建失败不覆盖旧 LKG。
- 新增 `billboard_snapshot_rebuild` JobQueue handler，应用启动和真实数据/设置/治理变更完成后触发，CPU-heavy gate 保证 Billboard 重建串行。
- 公共只读面只读既有 sidecar，不创建或写入缓存；损坏 payload 会跳过并回退计算。

## 验证证据

### 测试与门禁

- 后端 unit：`1686 passed, 1068 deselected`。
- Billboard 关键 contract：`23 passed`。
- 完整 contract：`419 passed, 2335 deselected`。
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

## 发布边界

- 本地代码已提交；本次工作未 push。
- 未执行生产数据库备份、生产副本快照预建、镜像构建、部署、重启、线上 API 验收或回滚演练。
- 生产发布前仍需确认当前镜像与 Billboard 聚合 builder 版本一致，在生产数据副本预建默认快照并核对新旧 API JSON 等价；随后按 `backup -> deploy -> health/ready -> exact hit -> restart hit -> mutation rebuild -> rollback` 验收。
