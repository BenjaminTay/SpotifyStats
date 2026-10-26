# 早期AI分析框架设计与实施提纲

2026-10-26按主题合并。历史设计保留决策及合同，实施部分只保留目标、分工和验收要求；旧操作步骤不作为当前任务，计划中的Expected不等于实际通过。

## 阅读顺序

- [AI Agent Universal Analytical Harness 设计](#ai-agent-universal-analytical-harness-设计)
- [AI Agent Universal Analytical Harness Implementation Plan](#ai-agent-universal-analytical-harness-implementation-plan)

## AI Agent Universal Analytical Harness 设计

原记录：`2026-06-29-ai-agent-universal-analytical-harness-design.md`。

> 创建日期：2026-06-29\
> 状态：设计稿，待人工确认后进入实施计划\
> 相关模块：`backend/services/ai_agent_service.py`、`backend/domains/ai_agent/`、`frontend/src/features/ai-insights/`、`frontend/src/features/ai-tasks/`\
> 设计目标：把 AI 问答从“会调用工具的聊天模型”升级为“先建立分析口径、再查证据、再综合冲突证据的分析器”

### 背景

AI Observable Agent Orchestrator V2 已完成只读工具链、任务进度、思考模式、证据卡片、coverage 自检、answer critic 与 golden-question harness。当前系统已经能回答不少本地数据问题，也能在 UI 中展示工具轨迹和结构化证据。

但用户在问“从播放次数和个人 Billboard 榜单成绩来看，我对 GUTS 和 The Life of a Showgirl 这两张专辑的喜爱程度哪张更甚？”时，暴露出一个更通用的问题：系统能查到数据，却没有稳定地理解“喜爱程度”这类问题需要多口径分析。它容易把比较题压成单一胜者，忽略播放时长、近期窗口、单位时间强度、榜单统治密度等冲突证据。

这个问题不应只通过修补 GUTS vs The Life of a Showgirl 个案解决。它代表了所有复杂问答都会遇到的通用风险：问题类型理解不足、证据配方不完整、证据冲突未显式处理、最终回答过度简化。

### 当前相似能力

现有代码已经有中间层雏形，但职责分散：

| 现有模块 | 当前能力 | 缺口 |
|---|---|---|
| `question_intent.py` | 解析 `task_type`、`entity_type`、实体、指标、时间范围 | 只有粗粒度 task type，不知道“偏好型比较”“趋势偏好”“变化解释”等分析家族 |
| `PLANNER_SYSTEM_PROMPT` | 指导 LLM 选择只读工具 | 主要依赖 prompt，没有确定性证据配方 |
| `compare_entities` | 比较多实体播放量、时长、个人 Billboard 与强度 | 结果已有多维 winner，但缺少统一的冲突解释协议 |
| `coverage_review.py` | 检查实体是否查到、工具是否覆盖 | 只看 found/missing，不检查分析维度是否充分 |
| `evidence_cards` | 把工具结果转成 UI 和 LLM 可用的证据卡 | 偏展示证据，缺少分析结论底稿 |
| `answer_critic.py` | 抓本地 Billboard 误表述、found 数据被说成缺失 | 不抓过度结论、忽略冲突证据、答错问题轴 |
| golden harness | 用离线问题检查 parser、工具要求和 critic | 覆盖问题数量仍少，重点在工具调用，不足以约束分析形状 |

因此本设计不推翻现有架构，而是在这些模块之间插入一个显式分析协议层。

### 目标

1. 让复杂问答先进入明确的问题家族，而不是只进入粗粒度 `comparison` / `trend` / `ranking`。
2. 为每类问题定义最低证据配方，避免模型只查一个 lifetime 总量就下结论。
3. 在最终回答前生成结构化 `AnalyticalBrief`，把多维胜者、冲突证据、公平性限制和推荐结论显式化。
4. 用 `AnswerContract` 约束回答形状，让不同问题家族有不同的必答项和禁用项。
5. 扩展 critic 和 golden harness，从“事实是否错”升级到“分析是否充分、结论是否过度”。
6. 保持只读边界：不开放任意 SQL、不开放任意 URL、不新增写操作、不访问外部 Billboard。

### 非目标

- 不把 LLM 改成拥有任意后端 API 调用权。
- 不引入外部搜索或官方 Billboard 数据。
- 不替代现有 `ai_task_runs/events/tool_calls` 可观察任务模型。
- 不要求一次性支持所有可能的自然语言问题。
- 不把所有分析规则硬编码成最终文案模板；中间层提供分析底稿，最终自然语言仍由 LLM 生成。
- 不在本阶段大改前端聊天交互，只在有必要时增强证据卡片展示。

### 总体架构

```text
用户问题
  ↓
QuestionIntent
  ↓
QuestionFrame          新增：识别分析家族、轴、回答契约
  ↓
EvidenceRecipe         新增：定义最低证据配方
  ↓
Tool Plan / Execution  复用现有只读工具链
  ↓
EvidenceSufficiency    升级：按分析轴检查证据是否足够，必要时补查
  ↓
AnalyticalBrief        新增：结构化分析底稿
  ↓
Final Answer LLM       复用现有最终回答生成
  ↓
AnswerContractCritic   升级：检查分析质量和回答契约
  ↓
UI Evidence Cards      复用并适度增强
```

### 核心数据模型

#### QuestionFrame

`QuestionFrame` 是 `QuestionIntent` 的升级结果，回答“用户到底在问哪类分析问题”。

```json
{
  "family": "preference_comparison",
  "task_type": "comparison",
  "entity_type": "album",
  "entities": ["GUTS", "The Life of a Showgirl"],
  "time_scope": "lifetime",
  "requested_metrics": ["plays", "personal_billboard"],
  "analysis_axes": [
    "cumulative",
    "recency",
    "intensity",
    "personal_billboard",
    "fairness"
  ],
  "answer_contract": "layered_preference_comparison",
  "requires_layered_conclusion": true
}
```

建议先支持以下问题家族：

| Family | 典型问题 | 核心风险 |
|---|---|---|
| `simple_ranking` | “2023 年我听最多的艺人是谁？” | 忘记时间范围或排序指标 |
| `entity_detail` | “GUTS 表现如何？” | 只汇报数据，不解释含义 |
| `preference_comparison` | “我更喜欢 A 还是 B？” | 把偏好压成单一累计指标 |
| `trend_preference` | “我最近是不是越来越喜欢 Olivia Rodrigo？” | 用 lifetime 回答趋势 |
| `period_comparison` | “今年和去年口味有什么变化？” | 缺少同口径分期对比 |
| `change_explanation` | “为什么这张专辑最近掉下去了？” | 没有前后窗口或替代对象 |
| `time_of_day_ranking` | “我深夜最爱听什么歌？” | 只查总体排行，忽略时段 |
| `identity_preference` | “谁最像我的本命？” | 需要长期、近期、稳定性和峰值共同判断 |
| `habit_summary` | “我的听歌习惯是什么？” | 证据维度太散，回答空泛 |

#### EvidenceRecipe

`EvidenceRecipe` 定义每个问题家族的最低证据要求。

```json
{
  "family": "preference_comparison",
  "required_axes": ["cumulative", "recency", "intensity"],
  "conditional_axes": [
    {
      "when_requested_metric": "personal_billboard",
      "axis": "personal_billboard"
    },
    {
      "when_entity_entry_dates_differ": true,
      "axis": "fairness"
    }
  ],
  "required_tool_patterns": [
    "compare_entities",
    "entity_stats:last_6_months",
    "entity_stats:last_4_weeks"
  ],
  "max_followup_calls": 4
}
```

首批证据配方：

| Family | 必要证据 |
|---|---|
| `simple_ranking` | `analysis_charts` 或 `wrapped_yearly`，必须包含时间范围、entity、metric |
| `entity_detail` | `entity_stats`；若问题提到榜单则补 `billboard_entity_detail` |
| `preference_comparison` | `compare_entities`；近期窗口；归一化强度；若提到榜单则个人 Billboard 维度 |
| `trend_preference` | 至少两个时间窗口或时间序列；不能只用 lifetime |
| `period_comparison` | 两个或多个同口径 period 的 `analysis_stats` / `analysis_charts` |
| `change_explanation` | 目标对象前后窗口 + 同期替代对象或总体排行变化 |
| `time_of_day_ranking` | `listening_hours` 对应 view；若问歌曲必须用 `late_night_tracks` |
| `identity_preference` | lifetime + recent + consistency + peak / Billboard；必须分层结论 |
| `habit_summary` | 总体统计 + 时段 + 平台或行为记录，至少两类证据 |

#### EvidenceSufficiency

`EvidenceSufficiency` 是现有 `coverage_review` 的升级版。它不只判断“实体是否 found”，还判断“分析轴是否 covered”。

```json
{
  "sufficient": false,
  "axis_coverage": {
    "cumulative": "covered",
    "recency": "missing",
    "intensity": "covered",
    "personal_billboard": "covered",
    "fairness": "partial"
  },
  "reasons": [
    "preference_comparison 需要近期窗口，否则无法区分长期累计和近期偏好"
  ],
  "followup_tool_calls": [
    {
      "tool_name": "entity_stats",
      "params": {
        "entity": "album",
        "album_name": "GUTS",
        "period": "last_6_months"
      }
    }
  ]
}
```

升级规则：

- `comparison` 不再等同于 sufficient；必须满足对应 family 的 axes。
- `preference_comparison` 若不同实体 first_play_date 相差明显，必须标记 `fairness`。
- `trend_preference` 若没有时间序列或至少两个窗口，必须补查。
- `change_explanation` 若没有前后窗口，必须补查。
- 补查仍受 `MAX_TOOL_CALLS` 控制，不能无限循环。

#### AnalyticalBrief

`AnalyticalBrief` 是最终回答前的结构化分析底稿。它把工具证据转成“可解释结论”，降低 LLM 自己拼证据时的随机性。

```json
{
  "family": "preference_comparison",
  "answer_contract": "layered_preference_comparison",
  "main_question": "哪张专辑更能代表用户喜爱",
  "dimension_winners": {
    "cumulative_plays": "GUTS",
    "total_hours": "The Life of a Showgirl",
    "recent_6_months": "The Life of a Showgirl",
    "recent_4_weeks": "GUTS",
    "power_score": "GUTS",
    "no1_density": "The Life of a Showgirl",
    "intensity": "The Life of a Showgirl"
  },
  "conflict": true,
  "recommended_conclusion": {
    "long_term": "GUTS",
    "recent_intensity": "The Life of a Showgirl",
    "single_answer_if_forced": "GUTS"
  },
  "must_explain": [
    "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard",
    "累计值受进入播放历史时间影响",
    "不同口径胜者不一致，不能说单方明显胜出"
  ],
  "forbidden_claims": [
    "市场影响力更大",
    "外部官方 Billboard 成绩",
    "所有指标均指向同一对象"
  ]
}
```

`AnalyticalBrief` 不需要覆盖所有问题的最终推理，但必须提供：

- 主问题复述
- 维度胜者或关键发现
- 冲突状态
- 推荐结论
- 必须说明的边界
- 禁止出现的错误 claim

#### AnswerContract

`AnswerContract` 定义最终回答必须包含什么、不能说什么。

首批 contract：

| Contract | 必须包含 | 禁止 |
|---|---|---|
| `simple_rank_answer` | 时间范围、排序指标、Top 结果、关键数字 | 不说明口径 |
| `layered_preference_comparison` | 主结论、长期/近期/强度/榜单拆分、公平性、冲突解释 | 证据冲突时说“明显单方胜出” |
| `trend_answer` | 时间窗口、趋势方向、变化幅度、边界 | 只引用 lifetime |
| `period_comparison_answer` | 两期同口径对比、增减项、解释 | 混用不同时间范围 |
| `change_explanation_answer` | 前后窗口、可能原因、竞争/替代对象、限制 | 没有变化证据就解释原因 |
| `time_of_day_answer` | 时段窗口、Top 项、占比/次数 | 用总体排行替代时段排行 |
| `identity_preference_answer` | 长期、近期、稳定性、峰值，多层结论 | 把单一榜单第一当成本命 |

### 对现有模块的改造建议

#### 1. 新增 `question_frame.py`

职责：

- 从 `QuestionIntent` 和原始 question 构建 `QuestionFrame`
- 识别更细的问题家族
- 决定 `analysis_axes` 和 `answer_contract`

初期可使用确定性规则，不依赖 LLM。

#### 2. 新增 `evidence_recipes.py`

职责：

- 保存 family 到 recipe 的映射
- 输出 required axes、conditional axes、recommended tool patterns
- 供 planner prompt、coverage review 和 golden harness 共同引用

#### 3. 升级 `coverage_review.py`

职责变化：

- 从“实体 coverage”升级为“axis coverage”
- 输入从 `question_intent + coverage` 变为 `question_frame + evidence_recipe + tool_results`
- 返回 axis coverage、缺口原因和补查计划

#### 4. 新增 `analytical_brief.py`

职责：

- 从 `QuestionFrame`、`EvidenceRecipe`、tool results、evidence cards 生成 brief
- 对常见 family 做确定性摘要
- 对暂未支持的 family 降级为通用 brief，但仍保留边界和 forbidden claims

#### 5. 升级 `answer_critic.py`

新增问题类型：

- `overclaim_single_winner`：证据冲突时却说单方明显胜出
- `ignored_conflicting_metric`：brief 要求解释冲突，正文未解释
- `missing_fairness_adjustment`：进入历史时间差大但只看累计
- `wrong_question_axis`：偏好题答成排行题，趋势题答成 lifetime 题
- `unsupported_market_claim`：继续禁止外部 Billboard / 市场影响力 claim
- `missing_contract_section`：回答没有满足 contract 必答项

#### 6. 调整 `ai_agent_service.py`

建议流程：

```text
intent = parse_question_intent(question)
frame = build_question_frame(question, intent)
recipe = recipe_for_frame(frame)
planner_content includes frame + recipe
tool_results = execute planned tools
sufficiency = review_evidence_sufficiency(frame, recipe, tool_results)
tool_results += followups
brief = build_analytical_brief(frame, recipe, tool_results)
final_payload includes frame + recipe + brief + evidence_cards + compact tool_results
answer = LLM final answer
critic = critique_answer(answer, final_payload)
retry if critic fails
```

#### 7. 前端证据卡片增强

不要求首期大改 UI，但建议后续增加“维度胜负矩阵”：

```text
累计播放       GUTS
播放时长       The Life of a Showgirl
最近 6 个月    The Life of a Showgirl
最近 4 周      GUTS
Power Score   GUTS
冠军密度       The Life of a Showgirl
```

这能帮助用户直观看到“为什么答案不是单边胜利”。

### Planner 与 Final Prompt 调整

Planner prompt 应从“根据 question_intent 选工具”升级为：

- `DATA.question_frame` 是硬约束。
- `DATA.evidence_recipe` 是最低证据要求。
- 规划工具时优先满足 required axes。
- 如果 family 是 `preference_comparison`，必须优先使用 `compare_entities`，并补近期窗口。
- 如果 family 是 `trend_preference`，不得只查询 lifetime。

Final prompt 应从“只基于 DATA 回答”升级为：

- `DATA.analytical_brief` 是回答底稿。
- `DATA.answer_contract` 是硬约束。
- 如果 `analytical_brief.conflict=true`，必须分层回答。
- 不得忽略 `must_explain`。
- 不得出现 `forbidden_claims`。

### Golden Questions

新增 golden fixture 需要按问题家族组织，而不是按单个 bug 组织。

首批建议：

| Case | Family | 验收重点 |
|---|---|---|
| GUTS vs The Life of a Showgirl 哪张更喜欢 | `preference_comparison` | 分层结论、冲突解释、个人 Billboard 边界 |
| Taylor Swift 和 Olivia Rodrigo 谁更像我的本命 | `identity_preference` | 长期/近期/稳定性/峰值共同判断 |
| 最近六个月是不是越来越喜欢 Olivia Rodrigo | `trend_preference` | 必须用近期窗口或时间序列 |
| 2023 年我听最多的艺人是谁 | `simple_ranking` | 时间范围、排序指标清晰 |
| 我深夜最爱听什么歌 | `time_of_day_ranking` | 必须用 `late_night_tracks` |
| 今年和去年口味有什么变化 | `period_comparison` | 同口径 period comparison |
| 为什么某张专辑最近掉下去了 | `change_explanation` | 前后窗口和替代对象 |
| 播放次数最多是否就代表最喜欢 | `habit_summary` / `preference_explanation` | 解释指标边界，不能把 plays 当唯一偏好 |

每个 case 至少检查：

- expected `family`
- expected `analysis_axes`
- required tool call patterns
- required answer contract
- forbidden answer phrases
- critic 对错误回答必须失败

### 验收标准

#### 后端

- `QuestionFrame` 能稳定识别首批问题家族。
- `EvidenceRecipe` 能为每个 family 返回明确 axes。
- `EvidenceSufficiency` 能发现缺少近期、趋势、强度、公平性等证据。
- `AnalyticalBrief` 能输出维度胜者、冲突状态、推荐结论和 forbidden claims。
- `AnswerContractCritic` 能拦截过度单一结论和忽略冲突指标。
- 所有新模块都有 unit tests。

#### 前端

- 现有 evidence cards 和 tool trace 不退化。
- 若实现维度胜负矩阵，桌面和 390px 移动端无横向溢出。
- 问答历史中的 `meta.evidence_cards` 继续保留。

#### 真实用户体验

- GUTS vs The Life of a Showgirl 问题应输出分层结论，而不是单句“明显更喜欢 GUTS”。
- 趋势问题不能只用 lifetime 总量。
- 排名问题保持简洁，不被强行扩成复杂分析。
- 任何提到 Billboard 的回答都必须明确是本地个人榜单。

### 实施阶段建议

#### Phase 1：QuestionFrame 与 EvidenceRecipe

- 新增 `question_frame.py`
- 新增 `evidence_recipes.py`
- 把 frame 和 recipe 放入 planner payload
- 更新 golden fixture 校验 family 和 axes

#### Phase 2：EvidenceSufficiency

- 升级 `coverage_review.py`
- 按 axes 判断缺口
- 为 `preference_comparison` 补近期窗口
- 为 `trend_preference` 补时间序列或多窗口

#### Phase 3：AnalyticalBrief

- 新增 `analytical_brief.py`
- 首批支持 `preference_comparison`、`simple_ranking`、`time_of_day_ranking`
- final payload 增加 brief

#### Phase 4：AnswerContractCritic

- 扩展 `answer_critic.py`
- 增加 contract-level deterministic checks
- 对失败回答自动 retry 一次，retry prompt 引用 brief 和 contract violation

#### Phase 5：UI 与 Golden Harness 收口

- evidence cards 增加维度胜负矩阵
- golden harness 按 family 覆盖
- 真实浏览器验证 `/ai-insights` 常见问题
- 更新 `AGENTS.md`、`backend/CLAUDE.md`、`frontend/CLAUDE.md` 和 `docs/README.md`

### 风险与缓解

| 风险 | 缓解 |
|---|---|
| 规则过多导致回答僵硬 | 规则只约束 evidence 和 contract，不固定最终文案 |
| 工具调用数量增加，回答变慢 | 仍限制 `MAX_TOOL_CALLS`；高成本 family 才补查 |
| question family 误判 | golden questions 覆盖典型问法；低置信度降级到 general brief |
| 复杂问题仍证据不足 | 明确返回限制，避免硬答 |
| 前端证据卡过载 | UI 只展示 brief 摘要，完整 tool trace 保持折叠 |

### 人工确认项

以下决策建议采用默认值，不阻塞进入实施计划，但可以在实现前调整：

1. 首批问题家族采用 9 类：`simple_ranking`、`entity_detail`、`preference_comparison`、`trend_preference`、`period_comparison`、`change_explanation`、`time_of_day_ranking`、`identity_preference`、`habit_summary`。
2. `preference_comparison` 默认必须查近期窗口；推荐窗口为 `last_6_months` 和 `last_4_weeks`。
3. `AnalyticalBrief` 首期优先做确定性规则，不调用额外 LLM。
4. `AnswerContractCritic` 首期只做可确定检查，不做第二个 LLM judge。
5. 前端维度胜负矩阵可以作为 Phase 5，不阻塞后端分析质量提升。

### 成功判据

这个设计成功时，AI 问答应表现出三个变化：

1. 它不再只回答“哪个数最大”，而是先说明问题口径。
2. 它能主动承认并解释冲突证据。
3. 它对不同问题家族采用不同证据配方和回答形状。

最终目标不是让每个答案都更长，而是让复杂问题更可靠、简单问题仍然简洁。

## AI Agent Universal Analytical Harness Implementation Plan

原记录：`2026-06-29-ai-agent-universal-analytical-harness.md`。

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

**Goal:** Turn the read-only AI chat Agent into a general analytical harness that frames the user's question, gathers the minimum evidence for that question family, builds a structured analytical brief, and prevents over-simplified or unsupported final answers.

**Architecture:** Keep the existing observable AI task runner, read-only tool registry, evidence cards, coverage review, answer critic, and golden-question harness. Add a deterministic `QuestionFrame`, `EvidenceRecipe`, axis-level `EvidenceSufficiency`, `AnalyticalBrief`, and contract-aware answer checks between the current intent parser and final LLM answer.

**Tech Stack:** FastAPI, SQLite, Pydantic v2, pytest, React 19, TypeScript, Vitest, Playwright smoke scripts.

---

### Source Spec

Use this design document as the authority for scope and terminology:

- `docs/superpowers/specs/2026-06-29-ai-agent-universal-analytical-harness-design.md`

The five design decisions at the end of the spec are accepted:

- First supported families: `simple_ranking`, `entity_detail`, `preference_comparison`, `trend_preference`, `period_comparison`, `change_explanation`, `time_of_day_ranking`, `identity_preference`, `habit_summary`.
- `preference_comparison` requires recent-window evidence, using `last_6_months` and `last_4_weeks`.
- `AnalyticalBrief` is deterministic in the first version.
- `AnswerContractCritic` uses deterministic checks in the first version.
- Frontend dimension-winner matrix is a final phase and does not block backend quality.

### Current Baseline

The codebase already has most of the building blocks:

- `backend/domains/ai_agent/question_intent.py` parses coarse `task_type`, `entity_type`, `entities`, `requested_metrics`, and `time_scope`.
- `backend/services/ai_agent_service.py` runs planner LLM, sanitizes tool plans, executes read-only tools, reviews coverage, builds final payload, calls final LLM, and retries once on validation failures.
- `backend/domains/ai_agent/coverage_review.py` checks found/missing entity coverage and can request bounded follow-up tool calls.
- `backend/domains/ai_agent/comparison.py` summarizes cumulative plays, total hours, personal Billboard score/rank, normalized intensity, and fairness notes for `compare_entities`.
- `backend/domains/ai_agent/evidence.py` and `evidence_builders.py` already produce compact evidence cards for final-answer context and UI.
- `backend/domains/ai_agent/answer_critic.py` rejects unsupported external Billboard / market claims and contradictions where found data is described as missing.
- `backend/tests/fixtures/ai_agent_golden_questions.json` and `scripts/evaluate_ai_agent_harness.py` provide an offline harness baseline.
- `frontend/src/features/ai-tasks/AIEvidenceCards.tsx` renders evidence cards in chat and task result shells.

The implementation should extend these modules, not replace them.

### File Structure

Create:

- `backend/domains/ai_agent/question_frame.py`\
  Converts `QuestionIntent` plus the raw question into a narrower analysis family, required axes, and answer contract.
- `backend/domains/ai_agent/evidence_recipes.py`\
  Maps `QuestionFrame.family` to required axes, recommended tool patterns, and follow-up limits.
- `backend/domains/ai_agent/analytical_brief.py`\
  Builds a deterministic final-answer brief from frame, recipe, tool results, coverage, and evidence cards.
- `backend/tests/unit/test_ai_agent_question_frame.py`
- `backend/tests/unit/test_ai_agent_evidence_recipes.py`
- `backend/tests/unit/test_ai_agent_analytical_brief.py`

Modify:

- `backend/domains/ai_agent/coverage_review.py`\
  Add axis-level sufficiency review while preserving `review_coverage()` compatibility.
- `backend/domains/ai_agent/answer_critic.py`\
  Add contract-level checks for overclaim, ignored conflicts, missing fairness, wrong axis, and missing required answer sections.
- `backend/services/ai_agent_service.py`\
  Compute frame and recipe once, include them in planner/final payload, use axis-level sufficiency, pass analytical brief to final prompt, and include new metadata in task result.
- `backend/tests/unit/test_ai_agent_coverage_review.py`
- `backend/tests/unit/test_ai_agent_answer_critic.py`
- `backend/tests/unit/test_ai_agent_golden_questions.py`
- `backend/tests/fixtures/ai_agent_golden_questions.json`
- `scripts/evaluate_ai_agent_harness.py`
- `frontend/src/features/ai-tasks/AIEvidenceCards.tsx`
- `frontend/src/tests/ai-evidence-cards.test.tsx`
- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `backend/CLAUDE.md`
- `frontend/CLAUDE.md`

### Execution Rules

- Keep all new AI Agent tools and harness data read-only.
- Do not expose arbitrary SQL, arbitrary URL fetches, settings mutations, import jobs, cache clears, playlist operations, or write APIs.
- Preserve the existing `review_coverage(question_intent, coverage)` call shape until `ai_agent_service.py` is migrated.
- Keep `MAX_TOOL_CALLS = 5`; sufficiency follow-ups must deduplicate against already executed calls.
- Do not make ranking questions verbose by default. The layered response contract is for complex families such as preference comparison and identity preference.

---

#### Task 1: Add QuestionFrame

涉及文件：`backend/domains/ai_agent/question_frame.py`、`backend/tests/unit/test_ai_agent_question_frame.py`。

- Implement QuestionFrame
- Verify tests pass

---

#### Task 2: Add Evidence Recipes

涉及文件：`backend/domains/ai_agent/evidence_recipes.py`、`backend/tests/unit/test_ai_agent_evidence_recipes.py`。

- Implement EvidenceRecipe
- Verify tests pass

---

#### Task 3: Upgrade Coverage Review to Axis Sufficiency

涉及文件：`backend/domains/ai_agent/coverage_review.py`、`backend/tests/unit/test_ai_agent_coverage_review.py`。

- Add failing sufficiency tests
- Implement axis-level review

---

#### Task 4: Add AnalyticalBrief

涉及文件：`backend/domains/ai_agent/analytical_brief.py`、`backend/tests/unit/test_ai_agent_analytical_brief.py`。

- Implement AnalyticalBrief builder
- Verify tests pass

---

#### Task 5: Wire Frame, Recipe, Sufficiency, and Brief Into Agent Service

涉及文件：`backend/services/ai_agent_service.py`、`backend/tests/unit/test_ai_agent_tools.py`、`backend/tests/contract/test_ai_agent_task_contract.py`。

- Add focused service-level tests
- Import and compute frame plus recipe
- Update planner content and prompts

Extend `PLANNER_SYSTEM_PROMPT` with these sentences:

```text
DATA.question_frame 是硬约束，family 决定问题类型，analysis_axes 决定必须覆盖的证据维度。
DATA.evidence_recipe 是最低证据要求；规划工具时优先满足 required_axes 和 required_tool_patterns。
如果 family=preference_comparison，必须优先使用 compare_entities，并尽量补 last_6_months 或 last_4_weeks 的 entity_stats。
如果 family=trend_preference，不得只查询 lifetime。
如果 family=time_of_day_ranking，必须使用 listening_hours 且 view=late_night_tracks。
```

- Replace coverage review call with sufficiency review

Preserve the existing follow-up execution loop and deduplication.

- Add brief to final payload
- Update final-answer prompts and retry instruction

Extend both final system prompts:

```text
DATA.question_frame.family 决定回答形状，DATA.answer_contract 或 DATA.analytical_brief.answer_contract 是硬约束。
DATA.analytical_brief 是回答底稿；必须覆盖 must_explain，不得出现 forbidden_claims。
如果 DATA.analytical_brief.conflict=true，必须分层回答，不要说所有指标都指向同一个对象。
```

- Include metadata in task result

---

- 历史实施约束：Import `review_evidence_sufficiency` and keep `review_coverage` only for compatibility tests.

#### Task 6: Extend Answer Critic and Golden Harness

涉及文件：`backend/domains/ai_agent/answer_critic.py`、`backend/tests/unit/test_ai_agent_answer_critic.py`、`backend/tests/fixtures/ai_agent_golden_questions.json`、`backend/tests/unit/test_ai_agent_golden_questions.py`、`scripts/evaluate_ai_agent_harness.py`。

- Add failing critic tests
- Add contract-level critic helpers

At the end of `critique_answer()`, before returning, extend issues:

- Extend golden fixture fields

For each item in `backend/tests/fixtures/ai_agent_golden_questions.json`, add:

```json
"expected_frame": {
  "family": "preference_comparison",
  "answer_contract": "layered_preference_comparison",
  "analysis_axes_contains": ["cumulative", "recency", "intensity"]
},
"expected_recipe": {
  "required_axes_contains": ["cumulative", "recency", "intensity"],
  "required_tool_patterns_contains": [{"tool_name": "compare_entities"}]
}
```

Use these values for the existing cases:

- `album_guts_vs_showgirl`: family `preference_comparison`, contract `layered_preference_comparison`, axes `cumulative`, `recency`, `intensity`, `personal_billboard`, `fairness`.
- `artist_olivia_last_6_months_trend`: family `trend_preference`, contract `trend_answer`, axes `recency`, `trend`.
- `ranking_top_artist_2023`: family `simple_ranking`, contract `simple_rank_answer`, axes `ranking`.
- `deep_night_tracks_and_hours`: family `time_of_day_ranking`, contract `time_of_day_answer`, axes `time_of_day`, `ranking`.

Add four new cases:

- `artist_identity_taylor_vs_olivia`
- `period_this_year_vs_last_year`
- `album_recent_drop_explanation`
- `habit_plays_vs_preference_explanation`

Each new case must include `question`, `expected_intent`, `expected_frame`, `expected_recipe`, `required_tool_calls`, `recommended_tools`, `required_answer_terms`, and `forbidden_answer_terms`.

- Update evaluator

---

#### Task 7: Frontend Evidence Matrix and Documentation

涉及文件：`frontend/src/features/ai-tasks/AIEvidenceCards.tsx`、`frontend/src/tests/ai-evidence-cards.test.tsx`、`docs/README.md`、`docs/CHANGELOG.md`、`AGENTS.md`、`backend/CLAUDE.md`、`frontend/CLAUDE.md`。

- Add frontend test for comparison winner matrix
- Tighten comparison card layout

This keeps long album names readable on 390px mobile while preserving the compact two-column layout on wider screens.

- Update documentation

Update:

- `docs/README.md`: add this implementation plan under "当前功能设计" next to the spec.
- `docs/CHANGELOG.md`: add an Unreleased bullet describing the Universal Analytical Harness plan and the accepted scope.
- `AGENTS.md`: update the AI observable task paragraph once the implementation lands, naming `QuestionFrame`, `EvidenceRecipe`, `EvidenceSufficiency`, `AnalyticalBrief`, and answer contracts.
- `backend/CLAUDE.md`: add the new backend modules in the AI Agent/domain module list.
- `frontend/CLAUDE.md`: mention comparison evidence cards and the no-horizontal-overflow expectation.

The `docs/README.md` row should be:

```markdown
| [`superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`](superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md) | AI Agent 通用分析中间层实施计划：问题家族、证据配方、分析底稿、回答契约与验收步骤 |
```

Open `http://localhost:5173/ai-insights` and ask:

```text
从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？
```

Acceptance:

- Progress stages show planning, tool calls, coverage/evidence review, LLM generation.
- Tool trace includes `compare_entities` and recent-window follow-up evidence when available.
- Final answer states that cumulative/long-term evidence favors GUTS.
- Final answer states that intensity or some conflicting dimensions favor The Life of a Showgirl when evidence supports it.
- Final answer explicitly says SpotifyStats Billboard is the user's local personal chart, not external official Billboard.
- Final answer does not say every metric points to the same album.
- Evidence cards remain readable at desktop and 390px mobile widths.

---

- 历史验收要求：The existing evidence card layout already supports this; if text wraps poorly in manual browser verification, continue to Step 3.

- 历史实施约束：If the test passes but the comparison matrix is cramped, modify the metrics grid in `AIEvidenceCards.tsx`.

### Final Verification Matrix

Run these commands after all tasks are complete:

- All backend unit and contract tests pass.
- Golden harness prints `PASS`.
- Frontend tests and production build pass.
- `/ai-insights` interaction smoke passes.
- Control inventory smoke reports no visible interaction violations and no horizontal overflow.

### Self-Review Checklist

- Spec coverage: all accepted families have frame and recipe coverage; the first implementation deeply supports `preference_comparison`, `simple_ranking`, and `time_of_day_ranking`, while the other families receive deterministic frame/recipe/brief scaffolding and golden coverage.
- No write operations: the plan only touches read-only tool planning, local analysis evidence, deterministic validation, UI rendering, and docs.
- GUTS vs Showgirl generalization: the plan fixes the underlying axis/contract gap, not a single answer string.
- Backward compatibility: `review_coverage()` remains available; existing evidence cards and chat task result JSON remain additive.
- Verification: implementation must include unit tests, contract tests, golden harness, frontend tests, build, and browser-like AI Insights smoke.

### Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session with checkpoints.

Because this touches the backend harness, answer quality gates, frontend evidence rendering, and docs, Subagent-Driven is the safer default.
