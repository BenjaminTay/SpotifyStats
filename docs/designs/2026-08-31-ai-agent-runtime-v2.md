# AI Agent Runtime V2 架构与运行契约

状态：`IMPLEMENTED`（Phase 0–5，本分支）
验证：`PASS`（AI 范围；最终整仓结果以本分支验收记录为准）
仓库：`codex/ai-agent-runtime-v2`
部署：`NOT_DEPLOYED`
文档：`CURRENT`

## 目标与边界

V2 的目标不是建设通用 Agent 平台，而是让 SpotifyStats 内的 AI 问答和年度报告研究具备最小但真实的 Agent 能力：模型在每一步根据当前上下文决定调用哪个后端只读工具，观察真实返回后再决定继续查询、换查询范围或形成答案。

以下边界不变：

- 播放次数、时长、排行、图表和证据仍由确定性后端产生；LLM 不生成统计事实或图表数据。
- 模型只能看到后端注册的 read-only allowlist，不得执行任意 SQL、URL、写入、导入、设置、缓存或歌单操作。
- API Key 不进入前端、事件日志或工具结果。
- AI 报告仍为 cache-first / 手动生成；打开页面不会自动调用 LLM。

## 运行架构

```text
用户问题 / 年报研究任务
          │
          ▼
  Native Tool Model Adapter
  OpenAI-compatible tools / Anthropic tool_use
          │
          ▼
  AgentProfile → Turn → Step → Model decision
          │
     ┌────┴────┐
     │ tool call│ no tool call
     ▼          ▼
Tool Runtime   Answer Validator
allowlist      evidence/temporal/contract
typed params         │
     │               ▼
     └── observation ──► final answer / one repair step
          │
          ▼
 append-only Turn Event Log + metrics + SSE projection
```

V2 不再要求模型把工具调用伪装成正文 JSON，也不再用正则从文本中提取调用。Provider 必须返回原生结构化 tool call；不支持该协议时任务显式失败，运维可用 `AI_AGENT_RUNTIME=legacy` 临时回退。

## 状态机和预算

一次问答是一个 Turn，默认最多 6 个 Step、12 个实际工具调用、90 秒回合预算。确定性 ToolSelector 会先根据 QuestionFrame 选择 AgentProfile，正常只向模型暴露 3–6 个相关工具，而不是把全部 schema 塞进每次请求。每个 Step 只有两种有效进展：

1. 模型返回原生工具调用，Tool Runtime 校验名称和参数、补齐用户统计过滤条件、执行并将 observation 回传；
2. 模型不再调用工具，运行时校验回答与证据、时间口径和回答契约，必要时允许一次修正 Step。

数据问题在没有任何工具证据时直接回答会触发一次强制查证；连续两步重复相同工具和参数会终止循环。取消、超时、最大步骤和最大工具数都在步骤及工具边界检查。独立、只读且声明 `supports_parallel` 的同一步工具调用最多并行 2 个，结果仍按模型调用顺序稳定写回。单次在途 LLM HTTP 请求不能被 Python 线程强制中断，因此另有 45 秒请求超时和一次重试上限。

偏好比较不再固定展开成“累计 + 最近 6 个月 + 最近 4 周 + Billboard”的多组单实体调用。`compare_entities` 接受统一时间窗，普通比较默认不构建昂贵的个人 Billboard；只有问题明确提到个人 Billboard、Power Score、排名、冠军周或在榜周时才启用。所选窗口内同时返回播放次数、时长和周均强度，一次工具观察即可满足基础比较契约。

## 工具结果契约

工具执行结果统一区分：

- `ok`：查询成功并有可用结果；
- `empty`：查询成功但目标或窗口无数据；
- `partial`：查询成功但覆盖不完整；
- `error`：未知工具、参数校验或执行失败。

模型收到 `status`、`result_summary`、`source_range`、结构化 `data` 和脱敏错误。大型结果按结构递归压缩，始终保持合法 JSON，不再对序列化字符串从中间截断。

统计、图表、实体详情和比较工具使用 revision-aware 有界缓存；键包含规范化参数和播放、元数据、设置、identity、Album Project 与 Billboard revision，错误结果不缓存。工具元数据同时声明成本、超时、缓存类型和并行能力。实体比较在同一连接内共享一次 effective-play 加载，Billboard 也只做一次批量计算。

## 事件与可重放性

迁移 68 新增 `ai_agent_turn_events`。每轮按序记录 `turn_started`、`step_started`、`model_request`、`model_message`、`assistant_message`、`tool_call`、`tool_result`、`guardrail_retry`、`step_ended`、`turn_ended`、`run_failed` 或 `run_cancelled`。事件写入前会递归脱敏凭据字段和常见 Bearer/API Key 字符串。

所有进入模型的消息都以 `model_message` 事件保存，因此可按 sequence 重建当轮上下文、transcript、turn state 和 usage。`AI_AGENT_CONTEXT_SOURCE=memory|event_log` 支持影子哈希比较和逐步切换。进程重启时，未完成的只读 Agent turn 从事件 checkpoint 继续；已落盘的 `tool_result` 会预载进 Tool Runtime，不重复执行，只有尚未完成的工具调用会重放。

外部可通过 `GET /api/ai/tasks/{task_id}/trajectory` 读取轨迹，通过 `GET /api/ai/tasks/{task_id}/stream` 读取安全 SSE 投影。SSE 只包含任务快照、事实型进度、工具状态、最终答案增量和完成事件，不发送内部 runtime payload 或思维链。取消使用 `running → cancelling → cancelled`，HTTP ACK 不等待在途 Provider 请求结束；Worker 返回后会在任何新工具调用前再次检查取消状态。

迁移 69 新增 Session Inbox。运行中的 Chat turn 可通过 `POST /api/ai/tasks/{task_id}/inbox` 接收 `steer`、`followup` 或 `cancel`；补充要求在下一模型步骤边界按顺序消费。长会话上下文使用确定性压缩，保留事实摘要、时间范围、数据 revision 和 evidence reference，而不是无界回放历史正文。

## 问答与报告

- AI 问答默认使用完整 V2 Turn/Step 运行时，并把 `session_id` 与当轮事件关联；最终结果继续输出 evidence cards、coverage、temporal guard 和 validation issues，保持前端兼容。
- 年度视觉报告的确定性 research/chart 阶段不变；可变的补充研究阶段与 Chat 共用 `NativeObservationLoop`，并使用最多 6 个工具的 `report:yearly` AgentProfile。报告写作与既有事实审核仍在研究完成后执行。
- `AI_AGENT_RUNTIME=legacy` 同时回退问答和年报补充研究，便于针对不支持 native tools 的自定义 OpenAI-compatible Provider 临时止损。

## 配置

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| `AI_AGENT_RUNTIME` | `v2` | `v2` 或 `legacy` 回退 |
| `AI_AGENT_MAX_STEPS` | `6` | 单轮最大模型决策步数 |
| `AI_AGENT_MAX_TOOL_CALLS` | `12` | 单轮最大实际工具调用数 |
| `AI_AGENT_TURN_TIMEOUT_SECONDS` | `90` | 单轮总预算 |
| `AI_AGENT_LLM_TIMEOUT_SECONDS` | `45` | 单次 LLM HTTP 超时 |
| `AI_AGENT_LLM_RETRIES` | `1` | HTTP 重试次数 |
| `AI_AGENT_CONTEXT_SOURCE` | `memory` | `memory` 影子运行或 `event_log` 事件投影上下文 |

## 明确边界

V2 不是多 Agent 系统，没有任意插件执行、Shell、MCP 动态加载、长期后台自治或跨任务工作流调度。当前执行器仍是应用内 daemon thread，已支持进程启动后的事件 checkpoint 恢复，但不提供跨主机分布式租约或通用工作流调度。若未来需要多进程/多主机长任务，应将同一事件契约迁移到已有后台任务队列，而不是扩大模型权限。

## 本分支验收

- Provider、V2 observation loop、只读安全边界、空结果恢复、重复调用终止、报告原生研究、事件轨迹和 legacy 回退的定向测试通过。
- 后端 contract：415 项通过；前端 Vitest：611 项通过；前端生产 build 通过。
- 黄金问题矩阵：12/12；静态问题矩阵：141 题，其中 P0 12 题，全部通过。
- 真实数据库 Online Backup 副本 + 当前配置的 DeepSeek：Taylor Swift / Olivia Rodrigo 最近 6 个月复杂比较收敛为 1 次 `compare_entities`、2 个模型步骤、37.5 秒完成；19 个 trajectory event 可回放，回答校验问题为 0。
- 真实浏览器继续在运行中的同一回合追加“只看今年，不要全部时间”：Session Inbox 被下一模型步骤消费，Agent 并行调用 2 个 `analysis_charts`，最终答案使用 `2026-03-04..2026-08-31`，并展示证据卡片和工具轨迹。该回合 3 个模型步骤、2 个工具调用、110.7 秒完成；390px 下 `scrollWidth=clientWidth=390`。本地 dev server 因 `node_modules` 指向原工作树的外部符号链接产生 3 个字体 403 console error，属于验收环境资源边界；生产 build 已通过。
- 整仓 unit：1499 passed / 2 skipped；剩余 5 项均为本分支基线中 Album Project OpenAPI operation/parameter 覆盖缺口。这些对应原工作树已有、但为保护其 dirty 改动而未带入本工作树的独立审计修改，不属于 AI V2 变更。
