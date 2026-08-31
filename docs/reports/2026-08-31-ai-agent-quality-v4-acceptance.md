# AI Agent Quality V4 实施验收报告

验收日期：2026-08-31
实现状态：`IMPLEMENTED`
问答质量：`PASS`
恢复与流式：`PASS`
年度报告质量：`PASS（确定性写作回退）`
年度报告性能：`FAIL`
仓库：代码 `6437bdea`、`bc75a1ce`；文档提交另计
远端：`UNPUSHED`
部署：`NOT_DEPLOYED`

## 安全数据边界

- 生产数据只通过 SQLite Online Backup 复制到 `/tmp/spotify-agent-v4.D9nvlF/spotify_stats.db`，没有修改 live DB。
- 副本 `PRAGMA quick_check=ok`，119 张表、92,908 条 `plays`，444,588,032 bytes；schema 由 67 在副本内迁移到 70。
- Provider 只核对 enabled、provider、model 和 Key 存在性/长度，未输出 Key 值。
- 全部 Agent 工具来自只读 allowlist；没有任意 SQL、任意 URL、设置、导入、缓存门禁绕过或歌单写入。

## 真实模型问答门禁

增强后的 `changed` 门禁强制检查五维答案契约、`tool_evidence_v2`、constraint fingerprint、validation issue 和 evidence coverage。结果：`Pass 11 / Partial 0 / Fail 0`。

| 用例 | 结果 | 总耗时 | 工具耗时 | 工具数 |
|---|---|---:|---:|---:|
| P0-01 去年夏天曲风 | Pass | 20.3s | 7.8s | 2 |
| P0-03 专辑偏好 + 个人榜单 | Pass | 17.3s | 0.4s | 1 |
| P0-04 2023–2025 Top 5 | Pass | 50.2s | 16.2s | 5 |
| P0-08 深夜歌曲 | Pass | 49.1s | 33.0s | 1 |
| P0-10 社区 Olivia Rodrigo | Pass | 15.9s | 0.15s | 2 |
| P0-11 2010 无数据 | Pass | 21.4s | 4.6s | 3 |
| 写操作/SQL/外部榜单/API Key 5 题 | Pass | 14–31ms | 0 | 0 |

P0-10 的社区工具从首次真实运行约 227.1 秒降到 0.1–0.2 秒。它返回 `scoped_chart_snapshot` 与 LKG freshness，并明确完整帖子正文仍需完整 Feed 的限制。P0-11 明确回答该范围没有播放记录，不再把空排行当作已覆盖证据。

## Constraint Patch 与转向

真实任务 `7d86aff0401a` 在第一次工具调用后接收“只看今年，不要看 Billboard，再比较播放时长”：

- Patch schema 2，`operation=replace`，新增 `hours`，排除 `personal_billboard`。
- requested range 为 2026 全年，effective range 按数据截止日裁剪到 2026-08-21。
- 旧证据失效 1 份；最终只消费新约束下的 `compare_entities`。
- GUTS：271 次 / 14.3 小时 / 周均 8.14；The Life of a Showgirl：524 次 / 31.3 小时 / 周均 15.74。
- 最终答案契约 `pass`，`validation_issues=[]`，不包含 Billboard。

## 崩溃恢复与 SSE

恢复任务 `c8cab4bac4a7`：

- 首进程完成 3 次 `analysis_charts` 后被终止，task 保持 `running`、`attempt_count=1`。
- 仅在隔离副本把该任务 lease 置为过期，模拟 90 秒租约自然到期；新进程启动后接管为 `attempt_count=2`。
- trajectory 记录 `run_resumed={next_step:3, completed_call_count:3}`；恢复后只补跑 `analysis_stats` 和 `listening_hours`，原 3 个工具无重复。
- 最终 task `done`，Answer Contract `pass`，5 份 `tool_evidence_v2` 均有 constraint fingerprint。

SSE 对同一完成任务从 `v1:p11386:t2755:a1` 重连，只收到答案分片 `a2/a3/a4` 与完成事件；没有重放旧 progress 或 tool 事件。

## 年度报告真实验收

2025 年 `visual_yearly_artifact + agent_synthesis_v2` 经三轮暴露—修复完成质量闭环：

1. 首轮 599 秒虽返回 `done`，但 critic/fact 为 false、checkpoint 为 0，确认原软门禁会伪装成功。
2. 第二轮 651 秒被新硬门禁正确标记 `error`，没有缓存；6 个章节 checkpoint 已通过，仅缺月度趋势图观察。
3. 最终任务 `4dea3aca6edb` 在 677 秒完成并缓存：6 节、3345 字，critic、fact validation、final artifact quality、6/6 section checkpoint 全部 Pass；13 份 `tool_evidence_v2` 全部带 constraint fingerprint。

最终 metadata：`fallback_level=agent_writer_quality_fallback`、`writer_pipeline_status=fallback_visual_composer`。模型研究 Agent 实际调用年度/分析/Billboard 等只读工具，模型 writer 两次返回空内容，因此最终正文使用确定性长篇回退。报告事实质量 Pass，但纯模型写作只能标 Partial；677 秒性能标 Fail。

## 浏览器验收

真实后端 8014 + 本地前端 5184，页面 `/ai-insights?mode=chat`：

- Desktop 1280×720：无页面横向溢出；console error/warn 为 0。
- 通过 UI 提交“社区里 Olivia Rodrigo 相关帖子有哪些？”，任务 `592dd41eaad3` 在约 16 秒完成；页面显示 Agent 阶段、当前约束、最终答案和两条社区查询轨迹。
- 390×844：`scrollWidth=innerWidth=390`，无横向溢出；修复后 9 个可见按钮/开关全部至少 44px，思考模式 90×44、发送按钮 44×44；console error/warn 为 0。
- 开发服务因 worktree 复用原仓库 `node_modules`，Vite 终端报告字体文件超出 serve allow list；生产 build 正常打包字体，因此这是本地 worktree dev-server 环境边界，不是浏览器 console 或生产构建失败。

## 自动化验证

- 静态问题矩阵：141 题、P0 12、黄金问题 12，Pass。
- 变更相关单元：100 passed。
- 整仓 unit：1607 passed / 2 skipped。
- 整仓 contract：417 passed。
- 前端：78 files / 619 tests passed；production build Pass。
- 变更文件 Ruff / format：Pass；scoped Mypy（10 源文件，`follow-imports=skip`）：Pass；scoped ESLint：Pass。
- 整仓 Ruff：11 项既有脚本问题；整仓 ESLint：173 errors / 11 warnings；递归 Mypy 仍会进入未触碰模块并报告既有 Pandas/Literal 类型债务。它们不由本次改动引入，因此整仓静态门禁标 `PARTIAL（baseline）`。
- Git hooks：Ruff、format、Mypy、secret scan 均 Pass。

## 验收结论

V4 已达到“最小但真实、可工作的问答 Agent”：真实模型决策、工具观察、结构化转向、证据门禁、无数据语义、崩溃恢复、SSE 续传和响应式 UI 均闭环。

总体状态为 `PARTIAL`，不是因为问答正确性，而是年度报告的 677 秒冷路径与模型 writer 空完成仍不满足可交互的 Agent 体验。下一阶段应优先建设 revision/filter 精确的年度 ready snapshot、单次共享报告上下文和分章节 writer，不应通过增加模型权限、多 Agent 或任意 SQL 来掩盖性能问题。
