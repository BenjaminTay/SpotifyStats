# AI Agent Quality V3 实施验收报告

验收日期：2026-08-31
实现状态：`IMPLEMENTED`
验证状态：`PASS（AI 功能范围）`
仓库状态：代码 `COMMITTED 1b75ae3d`；文档提交另计
远端状态：`UNPUSHED`
部署状态：`NOT_DEPLOYED`

## 验收范围

本报告验证 AI 问答的路由、模型—工具—观察循环、证据校验、运行中转向、Provider 降级、真实数据库读取和前端呈现。它不代表生产部署，也不代表线上 SQLite 被修改。

## 数据和安全边界

- 来源库只通过 SQLite Online Backup 复制到 `/tmp/spotify-agent-v3.rNsd2m/spotify_stats.db`。
- 副本 `PRAGMA quick_check=ok`，119 张表、92,908 条 `plays`，文件大小 444,588,032 bytes。
- 所有真实 Agent 工具均为已注册只读工具；未执行任意 SQL、任意 URL、设置、导入、缓存或歌单写入。
- Provider 配置只核对启用状态、Provider、模型和 Key 存在性/长度；未输出 Key 值。
- 本轮没有 push、部署或修改生产库。

## 真实模型门禁

使用当前配置的 DeepSeek 模型和真实数据库副本运行变更集 11 题：

- `Pass 11 / Partial 0 / Fail 0`
- 覆盖相对时间、个人榜单专辑比较、跨年 Top 5 表格、深夜歌曲、社区搜索、数据覆盖外年份和四个只读安全边界。
- 全部题目 `evidence_coverage=1.0`，没有最终 validation issue。

代表性结果：

| 用例 | 结果 | 工具与范围 | 总耗时 |
|---|---|---|---:|
| P0-01 去年夏天 | Pass | `analysis_charts` + `analysis_stats`，`2025-06-01..2025-08-31` | 91.8s |
| P0-03 专辑偏好 + 个人榜单 | Pass | 1 次 `compare_entities` | 22.7s |
| P0-04 2023–2025 Top 5 | Pass | 3 次 `analysis_charts`，受控并行 | 56.1s |
| P0-08 深夜歌曲 | Pass | `listening_hours` | 18.2s |
| P0-10 社区检索 | Pass | `community_feed_search` | 99.5s |
| P0-11 数据覆盖外年份 | Pass | `analysis_charts` + `wrapped_yearly` | 14.0s |
| 安全边界 5 题 | Pass | 0 工具、安全策略直接拒绝 | 16–53ms |

这说明“能工作”已经成立，但不能把它描述为所有问题都快。社区和部分分析工具的冷路径仍是下一阶段性能重点。

## 真实运行中转向

初始问题要求比较 GUTS 与 The Life of a Showgirl 的播放和个人 Billboard；第一步完成后，Inbox 收到：

> 只看今年，不要看 Billboard，再比较播放时长

最终状态与结果：

- Inbox 在下一 Step 被消费，动作是 `replace_constraints`。
- 时间范围裁剪为 `2026-01-01..2026-08-21`；请求的 2026 年末超出本地数据截止日，因此保留 requested/effective 两套日期。
- `excluded_dimensions=[personal_billboard]`，工具参数 `include_billboard=false`。
- 旧的 lifetime + Billboard 工具证据通过 `tool_evidence_invalidated` 失效。
- 最终只保留 1 个新约束下的 `compare_entities`：GUTS 271 次 / 14.3 小时 / 周均 8.14；The Life of a Showgirl 524 次 / 31.3 小时 / 周均 15.74。
- Evidence Sufficiency 的 cumulative、intensity、recency、fairness 均为 `covered`；`evidence_coverage=1.0`、`validation_issues=[]`。
- 最终答案不包含 Billboard、Power Score、榜单列或 `None` 空值。

## 性能修复证据

- 修复前，真实 `compare_entities` 全部时间冷构建约 120.2s；读取精确 ready 的已发布快照后约 0.7–1.0s，定制 2026 窗口约 1.6s。
- 模型首步通常只占数秒，原主要失败来自工具冷构建和总预算后丢弃已成功证据。
- 新运行时在工具成功后即使总预算耗尽，也以 `budget_degraded_fallback` 发布可追溯答案，而不是把任务标成 error。

## 浏览器验收

在真实后端与本地前端开发服务上检查 `/ai-insights?mode=chat`：

- Desktop：AI 模式切换、思考模式、问题输入、历史会话、Markdown 回答、证据卡片和工具轨迹均可见。
- Markdown 比较答案真实渲染为语义 `<table>`，不是纯文本表格。
- 390×844：`documentScrollWidth=documentClientWidth=390`；520px 表格位于 256px、`overflow-x:auto` 的局部容器中，不造成页面横向溢出；输入框宽 279px。
- 移动顶部导航、对话历史抽屉、底部主导航均可访问。
- 浏览器 console 的 error/warn 为 0。

由于通过浏览器新发真实问题会再次把个人播放问题和证据发送给已配置的外部模型，本轮没有为纯 UI 观察重复发起一轮；真实转向通过相同 HTTP/SSE/任务数据链路验收，约束状态组件另由前端测试覆盖。

## 自动化验证

- Agent 单元：258 passed。
- Agent 相关契约：33 passed。
- AI 前端定向：17 passed；生产 build Pass。
- 静态问题矩阵：141 题、P0 12 题、黄金问题 12 题，Pass。
- Ruff：Pass。
- 定向 mypy：Pass。
- 整仓 unit：1,526 passed / 2 skipped / 5 failed。5 项均为本分支基线已有的 Album Project OpenAPI smoke/operation/parameter 审计缺口；对应修复存在于原工作树的用户 dirty 文件，本工作树为保护其来源没有复制或提交，因此整仓 unit 标记为 `PARTIAL（非 AI 失败）`。
- 整仓 contract：415 passed。
- 整仓 frontend：78 files / 615 tests passed；生产 build Pass。
- 全递归 mypy：662 个文件中存在 29 个文件的 116 项既有类型债务，标记为 `PARTIAL`；本轮 9 个源文件定向 mypy Pass，提交 hook 对全部 15 个 staged Python 文件 Pass。

## 验收结论

`PASS（AI 功能范围）`：当前实现已经具备最小真实 Agent 的成立条件——模型决策、结构化工具调用、观察反馈、会话状态、运行中转向、事件事实源、证据充分性和安全降级均在真实数据库与真实模型上闭环。

未声明为 Pass 的范围：生产部署、线上数据库、跨主机 Worker、通用 Agent 能力，以及仍为分钟级的冷工具性能。

整仓门禁总状态为 `PARTIAL`，原因仅是上述 5 项基线 OpenAPI 审计缺口；AI 功能范围、完整 contract 和完整 frontend 均为 Pass。
