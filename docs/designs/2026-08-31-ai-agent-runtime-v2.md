# AI Agent Runtime V2 架构与运行契约

状态：`IMPLEMENTED`（本分支）
验证：`PASS`（AI 范围；整仓 OpenAPI 基线缺口单列于验收说明）
仓库：`BRANCH_IN_PROGRESS`
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
  Turn → Step → Model decision
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
 append-only Turn Event Log + existing task/tool trace
```

V2 不再要求模型把工具调用伪装成正文 JSON，也不再用正则从文本中提取调用。Provider 必须返回原生结构化 tool call；不支持该协议时任务显式失败，运维可用 `AI_AGENT_RUNTIME=legacy` 临时回退。

## 状态机和预算

一次问答是一个 Turn，默认最多 6 个 Step、12 个实际工具调用、90 秒回合预算。每个 Step 只有两种有效进展：

1. 模型返回原生工具调用，Tool Runtime 校验名称和参数、补齐用户统计过滤条件、执行并将 observation 回传；
2. 模型不再调用工具，运行时校验回答与证据、时间口径和回答契约，必要时允许一次修正 Step。

数据问题在没有任何工具证据时直接回答会触发一次强制查证；连续两步重复相同工具和参数会终止循环。取消、超时、最大步骤和最大工具数都在步骤及工具边界检查。单次在途 LLM HTTP 请求不能被 Python 线程强制中断，因此另有 45 秒请求超时和一次重试上限。

偏好比较不再固定展开成“累计 + 最近 6 个月 + 最近 4 周 + Billboard”的多组单实体调用。`compare_entities` 接受统一时间窗，普通比较默认不构建昂贵的个人 Billboard；只有问题明确提到个人 Billboard、Power Score、排名、冠军周或在榜周时才启用。所选窗口内同时返回播放次数、时长和周均强度，一次工具观察即可满足基础比较契约。

## 工具结果契约

工具执行结果统一区分：

- `ok`：查询成功并有可用结果；
- `empty`：查询成功但目标或窗口无数据；
- `partial`：查询成功但覆盖不完整；
- `error`：未知工具、参数校验或执行失败。

模型收到 `status`、`result_summary`、`source_range`、结构化 `data` 和脱敏错误。大型结果按结构递归压缩，始终保持合法 JSON，不再对序列化字符串从中间截断。

## 事件与可重放性

迁移 68 新增 `ai_agent_turn_events`。每轮按序记录 `turn_started`、`step_started`、`model_request`、`model_message`、`assistant_message`、`tool_call`、`tool_result`、`guardrail_retry`、`step_ended`、`turn_ended`、`run_failed` 或 `run_cancelled`。

所有进入模型的消息都以 `model_message` 事件保存，因此可按 sequence 重建当轮上下文。外部可通过 `GET /api/ai/tasks/{task_id}/trajectory` 读取轨迹；原有 `/events` 和 `ai_tool_calls` 继续供前端展示阶段进度与数据查询轨迹。

## 问答与报告

- AI 问答默认使用完整 V2 Turn/Step 运行时，并把 `session_id` 与当轮事件关联；最终结果继续输出 evidence cards、coverage、temporal guard 和 validation issues，保持前端兼容。
- 年度视觉报告的确定性 research/chart 阶段不变；可变的补充研究阶段改用相同的原生工具调用/observation 协议。报告写作与既有事实审核仍在研究完成后执行。
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

## 明确未实现

V2 不是多 Agent 系统，没有任意插件执行、Shell、MCP 动态加载、长期后台自治或跨任务工作流调度。当前任务执行仍使用应用内 daemon thread；事件和结果是持久的，但进程崩溃后不会自动恢复正在运行的线程。若未来需要长任务恢复，应将执行器迁移到已有后台任务队列，而不是扩大模型权限。

## 本分支验收

- Provider、V2 observation loop、只读安全边界、空结果恢复、重复调用终止、报告原生研究、事件轨迹和 legacy 回退的定向测试通过。
- 后端 contract：410 项通过；前端 Vitest：608 项通过；前端生产 build 通过。
- 黄金问题矩阵：12/12；静态问题矩阵：141 题，其中 P0 12 题，全部通过。
- 真实数据库副本 + 当前配置的 DeepSeek：基础排行使用原生工具调用完成；删除请求零工具调用即时拒绝；Taylor Swift / Olivia Rodrigo 最近 6 个月复杂比较从原先 5 次调用并超时，收敛为 1 次 `compare_entities`、51 秒完成、22 个事件可完整回放。
- 生产 preview 的 AI Insights 浏览器交互 smoke 通过：0 console error、0 warning、0 page error、0 横向溢出。
- 整仓 unit：1495 passed / 2 skipped；剩余 5 项均为本分支基线中 Album Project OpenAPI operation/parameter 覆盖缺口。这些对应原工作树已有、但为保护其 dirty 改动而未带入本工作树的独立审计修改，不属于 AI V2 变更。
