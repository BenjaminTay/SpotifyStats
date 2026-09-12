# AI Agent Quality V3 设计与实施说明

状态：`IMPLEMENTED`
验证：`PASS（AI 功能范围）`
分支：`codex/ai-agent-quality-v3`
仓库：`COMMITTED 1b75ae3d`（文档提交另计）
远端：`UNPUSHED`
部署：`NOT_DEPLOYED`
文档：`CURRENT`

## 结论

SpotifyStats 的 AI 问答已从“带工具的单次问答”推进为一个最小但真实的应用内 Agent：模型在 Turn/Step 循环中决定工具调用，观察只读工具结果后继续决策；运行时保存可重放事件、接受回合内转向、校验事实与答案，并在 Provider 或预算降级时只用已观察证据生成答案。

V3 不追求复制通用 Coding Agent。它采用 Pi 的小核心循环，吸收 DeepSeek Harness 的显式 Turn/Step、追加式事件与能力边界，再叠加 SpotifyStats 特有的确定性事实、时间口径和证据门禁。

## 架构对照

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

## V3 运行链路

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

## 本轮关键完善

### 路由和性能

- 根据问题家族选择小型 Agent Profile，只暴露相关工具。
- 工具元数据声明成本、缓存、并行和冷构建风险；个人 Billboard 只有在用户明确要求时启用。
- 工具缓存纳入播放、元数据、设置、identity、Album Project 与 Billboard revision。
- `compare_entities` 对全部时间优先读取精确 ready 的已发布搜索/榜单快照；不存在时安全回退完整 builder，不降低统计门禁。
- 受控只读工具最多两路并行，事件写回顺序保持稳定。

### 事实和回答质量

- Evidence Recipe 定义问题家族最低证据，Evidence Coverage 逐轴判断是否需要补查。
- Fact Catalog 只收录工具可追溯事实；Claim Ledger 将答案数字映射回事实。
- 不可追溯数字是硬门禁。模型空完成、Provider 降级或回合超预算但已有可用证据时，使用确定性的排行/比较渲染器，不把成功工具结果丢弃。
- 排行兜底保留 Top 5，比较兜底同时展示播放次数、时长和同窗口强度；未请求 Billboard 时不渲染其列、说明或空值。

### 真实会话转向

- Session State 独立保存实体、时间窗、指标、排除维度和过滤条件，不再只拼接自然语言。
- 混合补充如“只看今年，不要看 Billboard，再比较播放时长”按子句解析，`hours` 不会被负向词误删。
- 排除维度会从模型可见问题、Question Frame、Evidence Recipe 和工具默认参数中同步移除。
- 替换范围、移除维度或改问时，旧约束下的工具证据标记为失效；最终 Fact Catalog、充分性判断和回答只消费新约束证据。

### Provider 与运行稳定性

- Provider 调用具有动态 step/turn 预算、仅失败 step 重试和熔断。
- 可用工具证据优先于 Provider 完整可用性；降级答案仍需通过事实和时间校验。
- 运行指标区分模型等待、工具墙钟/累计耗时、缓存/去重命中、验证耗时和上下文体积。

## 明确不做

本版本仍不是通用 Agent 平台，不包含多 Agent、Shell、任意插件/MCP 动态安装、任意联网、长期后台自治或跨主机调度。模型不能修改原始播放、设置、缓存、歌单或数据库。年度报告的图表和统计事实继续由确定性后端生成。

## 后续优先级

1. 缩短仍然昂贵的分析/社区工具冷路径；本轮真实门禁中 `analysis_stats`、跨年 `analysis_charts` 和社区检索仍可能达到分钟级。
2. 将会话状态从第一版规则解析升级为版本化 Constraint Patch schema，并扩大中英混合、否定和多子句黄金用例。
3. 把 Evidence Recipe 与工具语义元数据进一步统一，减少手工家族分支。
4. 建立真实模型的离线回放集和延迟/成本分位数门禁，区分模型决策质量、工具性能和最终答案质量。
5. 在事件投影稳定后再考虑持久 Worker/队列；不通过扩大模型权限解决可靠性问题。
