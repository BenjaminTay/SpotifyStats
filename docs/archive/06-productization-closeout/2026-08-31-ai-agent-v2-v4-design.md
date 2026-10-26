# AI Agent V2至V4历史设计

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。同日运行时V2、质量V3与V4设计合并。阶段目标、当时预算和回退原因保留，当前执行与恢复规则由V6接管。

当前规则与状态见[文档地图](../../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [AI Agent Runtime V2 架构与运行契约](#ai-agent-runtime-v2-架构与运行契约)
- [AI Agent Quality V3 设计与实施说明](#ai-agent-quality-v3-设计与实施说明)
- [AI Agent Quality V4 完整优化方案与实施说明](#ai-agent-quality-v4-完整优化方案与实施说明)

## AI Agent Runtime V2 架构与运行契约

原记录：`2026-08-31-ai-agent-runtime-v2.md`。

> 文档状态：ARCHIVED / HISTORICAL（2026-10-25）。当前入口：[V6当前运行合同](../../reference/ai-agent-runtime-v6.md)，当前配置默认值以backend/core/config.py为准；旧memory默认值仅描述V2形成时点。下文分支、部署、验证与默认值均表达形成时状态。

状态：`IMPLEMENTED`（Phase 0–5，本分支）
验证：`PASS`（AI 范围；最终整仓结果以本分支验收记录为准）
仓库：`codex/ai-agent-runtime-v2`
部署：`NOT_DEPLOYED`
文档：`HISTORICAL`

### 目标与边界

V2 的目标不是建设通用 Agent 平台，而是让 SpotifyStats 内的 AI 问答和年度报告研究具备最小但真实的 Agent 能力：模型在每一步根据当前上下文决定调用哪个后端只读工具，观察真实返回后再决定继续查询、换查询范围或形成答案。

以下边界不变：

- 播放次数、时长、排行、图表和证据仍由确定性后端产生；LLM 不生成统计事实或图表数据。
- 模型只能看到后端注册的 read-only allowlist，不得执行任意 SQL、URL、写入、导入、设置、缓存或歌单操作。
- API Key 不进入前端、事件日志或工具结果。
- AI 报告仍为 cache-first / 手动生成；打开页面不会自动调用 LLM。

### 运行架构

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

### 状态机和预算

一次问答是一个 Turn，默认最多 6 个 Step、12 个实际工具调用、90 秒回合预算。确定性 ToolSelector 会先根据 QuestionFrame 选择 AgentProfile，正常只向模型暴露 3–6 个相关工具，而不是把全部 schema 塞进每次请求。每个 Step 只有两种有效进展：

1. 模型返回原生工具调用，Tool Runtime 校验名称和参数、补齐用户统计过滤条件、执行并将 observation 回传；
2. 模型不再调用工具，运行时校验回答与证据、时间口径和回答契约，必要时允许一次修正 Step。

数据问题在没有任何工具证据时直接回答会触发一次强制查证；连续两步重复相同工具和参数会终止循环。取消、超时、最大步骤和最大工具数都在步骤及工具边界检查。独立、只读且声明 `supports_parallel` 的同一步工具调用最多并行 2 个，结果仍按模型调用顺序稳定写回。单次在途 LLM HTTP 请求不能被 Python 线程强制中断，因此另有 45 秒请求超时和一次重试上限。

偏好比较不再固定展开成“累计 + 最近 6 个月 + 最近 4 周 + Billboard”的多组单实体调用。`compare_entities` 接受统一时间窗，普通比较默认不构建昂贵的个人 Billboard；只有问题明确提到个人 Billboard、Power Score、排名、冠军周或在榜周时才启用。所选窗口内同时返回播放次数、时长和周均强度，一次工具观察即可满足基础比较契约。

### 工具结果契约

工具执行结果统一区分：

- `ok`：查询成功并有可用结果；
- `empty`：查询成功但目标或窗口无数据；
- `partial`：查询成功但覆盖不完整；
- `error`：未知工具、参数校验或执行失败。

模型收到 `status`、`result_summary`、`source_range`、结构化 `data` 和脱敏错误。大型结果按结构递归压缩，始终保持合法 JSON，不再对序列化字符串从中间截断。

统计、图表、实体详情和比较工具使用 revision-aware 有界缓存；键包含规范化参数和播放、元数据、设置、identity、Album Project 与 Billboard revision，错误结果不缓存。工具元数据同时声明成本、超时、缓存类型和并行能力。实体比较在同一连接内共享一次 effective-play 加载，Billboard 也只做一次批量计算。

### 事件与可重放性

迁移 68 新增 `ai_agent_turn_events`。每轮按序记录 `turn_started`、`step_started`、`model_request`、`model_message`、`assistant_message`、`tool_call`、`tool_result`、`guardrail_retry`、`step_ended`、`turn_ended`、`run_failed` 或 `run_cancelled`。事件写入前会递归脱敏凭据字段和常见 Bearer/API Key 字符串。

所有进入模型的消息都以 `model_message` 事件保存，因此可按 sequence 重建当轮上下文、transcript、turn state 和 usage。`AI_AGENT_CONTEXT_SOURCE=memory|event_log` 支持影子哈希比较和逐步切换。进程重启时，未完成的只读 Agent turn 从事件 checkpoint 继续；已落盘的 `tool_result` 会预载进 Tool Runtime，不重复执行，只有尚未完成的工具调用会重放。

外部可通过 `GET /api/ai/tasks/{task_id}/trajectory` 读取轨迹，通过 `GET /api/ai/tasks/{task_id}/stream` 读取安全 SSE 投影。SSE 只包含任务快照、事实型进度、工具状态、最终答案增量和完成事件，不发送内部 runtime payload 或思维链。取消使用 `running → cancelling → cancelled`，HTTP ACK 不等待在途 Provider 请求结束；Worker 返回后会在任何新工具调用前再次检查取消状态。

迁移 69 新增 Session Inbox。运行中的 Chat turn 可通过 `POST /api/ai/tasks/{task_id}/inbox` 接收 `steer`、`followup` 或 `cancel`；补充要求在下一模型步骤边界按顺序消费。长会话上下文使用确定性压缩，保留事实摘要、时间范围、数据 revision 和 evidence reference，而不是无界回放历史正文。

### 问答与报告

- AI 问答默认使用完整 V2 Turn/Step 运行时，并把 `session_id` 与当轮事件关联；最终结果继续输出 evidence cards、coverage、temporal guard 和 validation issues，保持前端兼容。
- 年度视觉报告的确定性 research/chart 阶段不变；可变的补充研究阶段与 Chat 共用 `NativeObservationLoop`，并使用最多 6 个工具的 `report:yearly` AgentProfile。报告写作与既有事实审核仍在研究完成后执行。
- `AI_AGENT_RUNTIME=legacy` 同时回退问答和年报补充研究，便于针对不支持 native tools 的自定义 OpenAI-compatible Provider 临时止损。

### 配置

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| `AI_AGENT_RUNTIME` | `v2` | `v2` 或 `legacy` 回退 |
| `AI_AGENT_MAX_STEPS` | `6` | 单轮最大模型决策步数 |
| `AI_AGENT_MAX_TOOL_CALLS` | `12` | 单轮最大实际工具调用数 |
| `AI_AGENT_TURN_TIMEOUT_SECONDS` | `90` | 单轮总预算 |
| `AI_AGENT_LLM_TIMEOUT_SECONDS` | `45` | 单次 LLM HTTP 超时 |
| `AI_AGENT_LLM_RETRIES` | `1` | HTTP 重试次数 |
| `AI_AGENT_CONTEXT_SOURCE` | `memory` | `memory` 影子运行或 `event_log` 事件投影上下文 |

### 明确边界

V2 不是多 Agent 系统，没有任意插件执行、Shell、MCP 动态加载、长期后台自治或跨任务工作流调度。当前执行器仍是应用内 daemon thread，已支持进程启动后的事件 checkpoint 恢复，但不提供跨主机分布式租约或通用工作流调度。若未来需要多进程/多主机长任务，应将同一事件契约迁移到已有后台任务队列，而不是扩大模型权限。

### 本分支验收

- Provider、V2 observation loop、只读安全边界、空结果恢复、重复调用终止、报告原生研究、事件轨迹和 legacy 回退的定向测试通过。
- 后端 contract：415 项通过；前端 Vitest：611 项通过；前端生产 build 通过。
- 黄金问题矩阵：12/12；静态问题矩阵：141 题，其中 P0 12 题，全部通过。
- 真实数据库 Online Backup 副本 + 当前配置的 DeepSeek：Taylor Swift / Olivia Rodrigo 最近 6 个月复杂比较收敛为 1 次 `compare_entities`、2 个模型步骤、37.5 秒完成；19 个 trajectory event 可回放，回答校验问题为 0。
- 真实浏览器继续在运行中的同一回合追加“只看今年，不要全部时间”：Session Inbox 被下一模型步骤消费，Agent 并行调用 2 个 `analysis_charts`，最终答案使用 `2026-03-04..2026-08-31`，并展示证据卡片和工具轨迹。该回合 3 个模型步骤、2 个工具调用、110.7 秒完成；390px 下 `scrollWidth=clientWidth=390`。本地 dev server 因 `node_modules` 指向原工作树的外部符号链接产生 3 个字体 403 console error，属于验收环境资源边界；生产 build 已通过。
- 整仓 unit：1499 passed / 2 skipped；剩余 5 项均为本分支基线中 Album Project OpenAPI operation/parameter 覆盖缺口。这些对应原工作树已有、但为保护其 dirty 改动而未带入本工作树的独立审计修改，不属于 AI V2 变更。

## AI Agent Quality V3 设计与实施说明

原记录：`2026-08-31-ai-agent-quality-v3.md`。

> 文档状态：ARCHIVED / HISTORICAL（2026-10-25）。当前入口：[V6当前运行合同](../../reference/ai-agent-runtime-v6.md)；V3能力由后续V4/V5/V6继承。下文分支、部署、验证与默认值均表达形成时状态。

状态：`IMPLEMENTED`
验证：`PASS（AI 功能范围）`
分支：`codex/ai-agent-quality-v3`
仓库：`COMMITTED 1b75ae3d`（文档提交另计）
远端：`UNPUSHED`
部署：`NOT_DEPLOYED`
文档：`HISTORICAL`

### 结论

SpotifyStats 的 AI 问答已从“带工具的单次问答”推进为一个最小但真实的应用内 Agent：模型在 Turn/Step 循环中决定工具调用，观察只读工具结果后继续决策；运行时保存可重放事件、接受回合内转向、校验事实与答案，并在 Provider 或预算降级时只用已观察证据生成答案。

V3 不追求复制通用 Coding Agent。它采用 Pi 的小核心循环，吸收 DeepSeek Harness 的显式 Turn/Step、追加式事件与能力边界，再叠加 SpotifyStats 特有的确定性事实、时间口径和证据门禁。

### 架构对照

| 维度 | Pi Agent | DeepSeek Harness | SpotifyStats V3 |
|---|---|---|---|
| 核心循环 | 直接、紧凑的模型—工具循环 | 显式 Turn/Step 与插件组合 | 直接循环 + 显式 Turn/Step |
| 会话事实源 | Session 消息与扩展事件 | 事件溯源、可派生状态 | 追加式 `ai_agent_turn_events`，可恢复和回放 |
| 工具边界 | 通用工具，由宿主决定权限 | Tool service、策略与生命周期 | 注册式只读 allowlist、Pydantic 参数、无任意 SQL/URL |
| 上下文 | Coding Agent 系统提示、历史、扩展 | 从事件和能力接缝构建 | 问题框架、时间语义、会话约束、项目规则和证据摘要 |
| 事实约束 | 依赖模型和工具结果 | 依赖能力实现 | 确定性 builder + Fact Catalog + Claim Ledger + 数字硬门禁 |
| 运行中转向 | 可由宿主注入消息 | Inbox/事件适合扩展 | Session Inbox，结构化替换、追加、排除、取消 |
| 降级 | Provider/宿主决定 | 框架级错误与插件策略 | Step 重试、候选 Provider、熔断、证据保留式兜底 |
| 目标 | 通用交互式 Coding Agent | 工程化通用 Harness | 单用户本地播放分析 Agent |

与主流通用 Agent 最重要的差别不是“能力少”，而是权限与事实边界更窄：SpotifyStats 不允许模型自由读库、联网、写设置或生成统计事实。它的智能体现在选择正确的只读能力、持续修正查询范围、判断证据是否足够，并把确定性事实组织成可核验答案。

### V3 运行链路

```text
用户问题 / 回合内补充
        │
        ▼
Session State + Question Frame + Temporal Guard
        │
        ▼
Agent Profile / 动态预算 / 相关工具 schema
        │
        ▼
Model Step ── native tool call ──► Read-only Tool Runtime
    ▲                                  │
    └──────── structured observation ──┘
        │
        ▼
Evidence Recipe → Fact Catalog → Claim Ledger
        │
        ├── 证据不足：有界补查
        ├── Provider/预算降级：确定性证据答案
        └── 证据充分：回答校验与一次修正
        │
        ▼
安全 SSE / 任务结果 / 可重放事件日志
```

### 本轮关键完善

#### 路由和性能

- 根据问题家族选择小型 Agent Profile，只暴露相关工具。
- 工具元数据声明成本、缓存、并行和冷构建风险；个人 Billboard 只有在用户明确要求时启用。
- 工具缓存纳入播放、元数据、设置、identity、Album Project 与 Billboard revision。
- `compare_entities` 对全部时间优先读取精确 ready 的已发布搜索/榜单快照；不存在时安全回退完整 builder，不降低统计门禁。
- 受控只读工具最多两路并行，事件写回顺序保持稳定。

#### 事实和回答质量

- Evidence Recipe 定义问题家族最低证据，Evidence Coverage 逐轴判断是否需要补查。
- Fact Catalog 只收录工具可追溯事实；Claim Ledger 将答案数字映射回事实。
- 不可追溯数字是硬门禁。模型空完成、Provider 降级或回合超预算但已有可用证据时，使用确定性的排行/比较渲染器，不把成功工具结果丢弃。
- 排行兜底保留 Top 5，比较兜底同时展示播放次数、时长和同窗口强度；未请求 Billboard 时不渲染其列、说明或空值。

#### 真实会话转向

- Session State 独立保存实体、时间窗、指标、排除维度和过滤条件，不再只拼接自然语言。
- 混合补充如“只看今年，不要看 Billboard，再比较播放时长”按子句解析，`hours` 不会被负向词误删。
- 排除维度会从模型可见问题、Question Frame、Evidence Recipe 和工具默认参数中同步移除。
- 替换范围、移除维度或改问时，旧约束下的工具证据标记为失效；最终 Fact Catalog、充分性判断和回答只消费新约束证据。

#### Provider 与运行稳定性

- Provider 调用具有动态 step/turn 预算、仅失败 step 重试和熔断。
- 可用工具证据优先于 Provider 完整可用性；降级答案仍需通过事实和时间校验。
- 运行指标区分模型等待、工具墙钟/累计耗时、缓存/去重命中、验证耗时和上下文体积。

### 明确不做

本版本仍不是通用 Agent 平台，不包含多 Agent、Shell、任意插件/MCP 动态安装、任意联网、长期后台自治或跨主机调度。模型不能修改原始播放、设置、缓存、歌单或数据库。年度报告的图表和统计事实继续由确定性后端生成。

### 后续优先级

1. 缩短仍然昂贵的分析/社区工具冷路径；本轮真实门禁中 `analysis_stats`、跨年 `analysis_charts` 和社区检索仍可能达到分钟级。
2. 将会话状态从第一版规则解析升级为版本化 Constraint Patch schema，并扩大中英混合、否定和多子句黄金用例。
3. 把 Evidence Recipe 与工具语义元数据进一步统一，减少手工家族分支。
4. 建立真实模型的离线回放集和延迟/成本分位数门禁，区分模型决策质量、工具性能和最终答案质量。
5. 在事件投影稳定后再考虑持久 Worker/队列；不通过扩大模型权限解决可靠性问题。

## AI Agent Quality V4 完整优化方案与实施说明

原记录：`2026-08-31-ai-agent-quality-v4.md`。

> 文档状态：ARCHIVED / HISTORICAL（2026-10-25）。当前入口：[V6当前运行合同](../../reference/ai-agent-runtime-v6.md)；旧性能失败按原报告保留。下文分支、部署、验证与默认值均表达形成时状态。

状态：`IMPLEMENTED`
功能质量：`PASS`
交互性能：`PARTIAL`
分支：`codex/ai-agent-quality-v4`
代码提交：`6437bdea`、`bc75a1ce`
远端：`UNPUSHED`
部署：`NOT_DEPLOYED`

### 目标与结论

V4 的目标不是扩建通用 Agent 平台，而是让 SpotifyStats 的 AI 问答和年度报告成为一个最小、真实、可恢复、可验收的本地数据 Agent。成立标准不再是“接口存在”或“模型能调用一次工具”，而是一次任务必须完成：模型决策、只读工具、结构化观察、约束更新、证据追溯、答案门禁、持久事件、失败恢复和真实 UI 呈现。

对照 Pi Agent 与 DeepSeek Harness，V4 继续使用 Pi 式小核心循环，不引入重型工作流图；同时吸收 Harness 的 Turn/Step、append-only 事件、Inbox、lease 和 replay。SpotifyStats 的差异化部分是确定性统计事实：模型负责选择与解释，builder/validator 负责数字、时间和榜单口径。

### V4 架构

```text
Question / Inbox steering
        │
        ▼
Constraint Patch V2 ──► Session State / Temporal Guard
        │
        ▼
Agent Profile ──► Native Model/Tool/Observation Loop
        │                         │
        │                         ▼
        │              Read-only Tool Runtime
        │              + tool_evidence_v2
        │                         │
        └─────────────────────────┘
                    │
                    ▼
Fact Catalog ─► Evidence Coverage ─► Claim Ledger
                    │                    │
                    ├─ bounded补查       ├─ 无数据回答
                    ├─ 证据失效          └─ grounded fallback
                    ▼
          Answer Quality Contract
                    │
                    ▼
Durable Task + Event Log + Lease Heartbeat + SSE Replay
```

### 完整优化项

#### 1. 答案质量契约

新增五维 Answer Quality Contract：`directness`、`informativeness`、`constraint_fidelity`、`evidence_traceability`、`uncertainty_honesty`。真实问题矩阵只有五维全部通过、没有 validation issue、证据覆盖达标时才判 Pass。

空时间窗不再被“工具调用成功”误认为证据充分；没有记录时必须明确回答无数据，不能生成虚假排行。社区检索必须列出真实命中的主体或活动，只有查询条数不算有信息量。

#### 2. 统一证据协议

Chat 与年度报告统一输出 `tool_evidence_v2`。每份证据包含工具、调用身份、状态、source range、事实、限制和 constraint fingerprint。约束替换后，旧 fingerprint 下的证据显式失效，不能进入最终 Fact Catalog 或报告章节。

报告增加逐章节 checkpoint。每节独立检查标题、正文长度、图表引用、工具引用和不可追溯数字；失败章节只允许一次有界模型修复，剩余不支持数字由确定性安全网移除。

#### 3. Constraint Patch V2

运行中补充要求采用版本化 patch，支持 `replace`、`append`、`exclude` 与 metric 更新。requested range 与按本地数据截止日裁剪后的 effective range 分开保存。实体、时间、指标、Billboard 排除和过滤条件在 Session State、Question Frame、Evidence Recipe 与工具参数间保持同一语义。

#### 4. 工具性能与语义

- 新增 `taste_profile`，用一次专用读取回答曲风/语言偏好，避免通用分析工具重复扫描。
- 社区文本检索优先走 music-search 候选索引与已发布周榜上下文，真实工具耗时由约 227 秒降至约 0.1–0.2 秒；结果明确标注 scoped snapshot、LKG freshness 和不能覆盖完整社区正文的限制。
- 年度、排行与图表工具统一 `empty` 状态，避免无数据误判。
- 工具缓存、去重、并行和 revision 指纹继续保持只读与 fail-closed。

#### 5. 年度报告闭环

年度报告研究复用真实 Agent loop，图表和统计事实仍由确定性后端生成。V4 修复了“要求 2800 字但模型输出上限只有 2048 token”的冲突：写作上限提高到 6144 token，同一研究证据内最多重写一次，不再因为写作格式失败重复整套研究工具。

若模型初稿未达到结构门槛，系统使用相同确定性上下文生成长篇回退稿，再经过 `tool_evidence_v2`、逐节 checkpoint、图表观察、critic、事实校验和最终 artifact 门禁。任一硬门禁失败时任务标记 `error` 且不缓存，不能再以 HTTP 任务 `done` 掩盖不合格报告。

#### 6. 可恢复运行时与 SSE

- Worker lease 从 900 秒改为 90 秒，独立心跳每 30 秒续租；长工具或模型调用不会被误接管，崩溃后最迟在短租约到期后可恢复。
- 启动恢复读取 append-only trajectory，从 `run_resumed.next_step` 继续；已完成工具调用身份不重复执行。
- SSE 使用进度、工具、答案三通道组合 cursor。浏览器通过 `Last-Event-ID` 重连时只收到 cursor 之后的事件和答案分片。
- 当前保证是单机 SQLite + lease 的至少一次任务执行和已完成工具去重，不宣称跨主机分布式 exactly-once。

#### 7. 前端可用性

AI 页面展示进行中阶段、当前约束、答案和工具轨迹。桌面与 390px 共享任务事实和 SSE cursor。移动端思考模式与发送按钮均调整为至少 44×44px，不产生页面级横向溢出。

### 分层验收标准

| 层级 | Pass 条件 |
|---|---|
| 静态 | 问题矩阵、P0 和黄金问题完整，schema/version 可解析 |
| 自动化 | Agent/report/task unit、contract、前端测试与 build 通过 |
| 真实问答 | 当前模型 + Online Backup 副本；契约、V2 证据、约束和答案均通过 |
| 恢复 | 杀进程后 stale lease 接管；attempt 增加；已完成工具不重复 |
| 流式 | 组合 cursor 断线续传，无旧进度/工具/答案分片重复 |
| 报告 | critic、事实、最终 artifact、全部章节 checkpoint 通过后才缓存 |
| UI | Desktop 与 390px 真实浏览器，无横向溢出、控制台错误，触控目标达标 |

### 当前边界与下一阶段

1. 年度报告冷构建约 11 分钟，交互性能为 Fail。下一阶段必须把同 filter/revision 的年度确定性上下文做成持久 ready snapshot，并让报告工具共享一次构建结果。
2. 当前 DeepSeek writer 两次返回空内容，最终报告依赖确定性写作回退；研究 Agent、证据与质量闭环成立，但纯模型写作状态为 Partial。需记录 Provider finish reason/usage，并将写作输入拆成分节小上下文。
3. 问答 changed 集 11/11 通过，但复杂跨年和深夜分析仍为约 49–50 秒；需要真实 P50/P95 延迟门禁，而不是只设 180 秒超时。
4. 社区 scoped snapshot 只覆盖候选索引和周榜活动，不等同完整 Feed 帖子搜索；UI 必须保留限制说明。
5. 不扩大到任意 SQL、任意 URL、写设置、导入、歌单、多 Agent、Shell 或长期自治；这些不是“让当前 Agent 变聪明”的必要条件。
