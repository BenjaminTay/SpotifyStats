# AI Agent Universal Analytical Harness 设计

> 创建日期：2026-06-29  
> 状态：设计稿，待人工确认后进入实施计划  
> 相关模块：`backend/services/ai_agent_service.py`、`backend/domains/ai_agent/`、`frontend/src/features/ai-insights/`、`frontend/src/features/ai-tasks/`  
> 设计目标：把 AI 问答从“会调用工具的聊天模型”升级为“先建立分析口径、再查证据、再综合冲突证据的分析器”

## 背景

AI Observable Agent Orchestrator V2 已完成只读工具链、任务进度、思考模式、证据卡片、coverage 自检、answer critic 与 golden-question harness。当前系统已经能回答不少本地数据问题，也能在 UI 中展示工具轨迹和结构化证据。

但用户在问“从播放次数和个人 Billboard 榜单成绩来看，我对 GUTS 和 The Life of a Showgirl 这两张专辑的喜爱程度哪张更甚？”时，暴露出一个更通用的问题：系统能查到数据，却没有稳定地理解“喜爱程度”这类问题需要多口径分析。它容易把比较题压成单一胜者，忽略播放时长、近期窗口、单位时间强度、榜单统治密度等冲突证据。

这个问题不应只通过修补 GUTS vs The Life of a Showgirl 个案解决。它代表了所有复杂问答都会遇到的通用风险：问题类型理解不足、证据配方不完整、证据冲突未显式处理、最终回答过度简化。

## 当前相似能力

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

## 目标

1. 让复杂问答先进入明确的问题家族，而不是只进入粗粒度 `comparison` / `trend` / `ranking`。
2. 为每类问题定义最低证据配方，避免模型只查一个 lifetime 总量就下结论。
3. 在最终回答前生成结构化 `AnalyticalBrief`，把多维胜者、冲突证据、公平性限制和推荐结论显式化。
4. 用 `AnswerContract` 约束回答形状，让不同问题家族有不同的必答项和禁用项。
5. 扩展 critic 和 golden harness，从“事实是否错”升级到“分析是否充分、结论是否过度”。
6. 保持只读边界：不开放任意 SQL、不开放任意 URL、不新增写操作、不访问外部 Billboard。

## 非目标

- 不把 LLM 改成拥有任意后端 API 调用权。
- 不引入外部搜索或官方 Billboard 数据。
- 不替代现有 `ai_task_runs/events/tool_calls` 可观察任务模型。
- 不要求一次性支持所有可能的自然语言问题。
- 不把所有分析规则硬编码成最终文案模板；中间层提供分析底稿，最终自然语言仍由 LLM 生成。
- 不在本阶段大改前端聊天交互，只在有必要时增强证据卡片展示。

## 总体架构

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

## 核心数据模型

### QuestionFrame

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

### EvidenceRecipe

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

### EvidenceSufficiency

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

### AnalyticalBrief

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

### AnswerContract

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

## 对现有模块的改造建议

### 1. 新增 `question_frame.py`

职责：

- 从 `QuestionIntent` 和原始 question 构建 `QuestionFrame`
- 识别更细的问题家族
- 决定 `analysis_axes` 和 `answer_contract`

初期可使用确定性规则，不依赖 LLM。

### 2. 新增 `evidence_recipes.py`

职责：

- 保存 family 到 recipe 的映射
- 输出 required axes、conditional axes、recommended tool patterns
- 供 planner prompt、coverage review 和 golden harness 共同引用

### 3. 升级 `coverage_review.py`

职责变化：

- 从“实体 coverage”升级为“axis coverage”
- 输入从 `question_intent + coverage` 变为 `question_frame + evidence_recipe + tool_results`
- 返回 axis coverage、缺口原因和补查计划

### 4. 新增 `analytical_brief.py`

职责：

- 从 `QuestionFrame`、`EvidenceRecipe`、tool results、evidence cards 生成 brief
- 对常见 family 做确定性摘要
- 对暂未支持的 family 降级为通用 brief，但仍保留边界和 forbidden claims

### 5. 升级 `answer_critic.py`

新增问题类型：

- `overclaim_single_winner`：证据冲突时却说单方明显胜出
- `ignored_conflicting_metric`：brief 要求解释冲突，正文未解释
- `missing_fairness_adjustment`：进入历史时间差大但只看累计
- `wrong_question_axis`：偏好题答成排行题，趋势题答成 lifetime 题
- `unsupported_market_claim`：继续禁止外部 Billboard / 市场影响力 claim
- `missing_contract_section`：回答没有满足 contract 必答项

### 6. 调整 `ai_agent_service.py`

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

### 7. 前端证据卡片增强

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

## Planner 与 Final Prompt 调整

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

## Golden Questions

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

## 验收标准

### 后端

- `QuestionFrame` 能稳定识别首批问题家族。
- `EvidenceRecipe` 能为每个 family 返回明确 axes。
- `EvidenceSufficiency` 能发现缺少近期、趋势、强度、公平性等证据。
- `AnalyticalBrief` 能输出维度胜者、冲突状态、推荐结论和 forbidden claims。
- `AnswerContractCritic` 能拦截过度单一结论和忽略冲突指标。
- 所有新模块都有 unit tests。

### 前端

- 现有 evidence cards 和 tool trace 不退化。
- 若实现维度胜负矩阵，桌面和 390px 移动端无横向溢出。
- 问答历史中的 `meta.evidence_cards` 继续保留。

### 真实用户体验

- GUTS vs The Life of a Showgirl 问题应输出分层结论，而不是单句“明显更喜欢 GUTS”。
- 趋势问题不能只用 lifetime 总量。
- 排名问题保持简洁，不被强行扩成复杂分析。
- 任何提到 Billboard 的回答都必须明确是本地个人榜单。

## 实施阶段建议

### Phase 1：QuestionFrame 与 EvidenceRecipe

- 新增 `question_frame.py`
- 新增 `evidence_recipes.py`
- 把 frame 和 recipe 放入 planner payload
- 更新 golden fixture 校验 family 和 axes

### Phase 2：EvidenceSufficiency

- 升级 `coverage_review.py`
- 按 axes 判断缺口
- 为 `preference_comparison` 补近期窗口
- 为 `trend_preference` 补时间序列或多窗口

### Phase 3：AnalyticalBrief

- 新增 `analytical_brief.py`
- 首批支持 `preference_comparison`、`simple_ranking`、`time_of_day_ranking`
- final payload 增加 brief

### Phase 4：AnswerContractCritic

- 扩展 `answer_critic.py`
- 增加 contract-level deterministic checks
- 对失败回答自动 retry 一次，retry prompt 引用 brief 和 contract violation

### Phase 5：UI 与 Golden Harness 收口

- evidence cards 增加维度胜负矩阵
- golden harness 按 family 覆盖
- 真实浏览器验证 `/ai-insights` 常见问题
- 更新 `AGENTS.md`、`backend/CLAUDE.md`、`frontend/CLAUDE.md` 和 `docs/README.md`

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 规则过多导致回答僵硬 | 规则只约束 evidence 和 contract，不固定最终文案 |
| 工具调用数量增加，回答变慢 | 仍限制 `MAX_TOOL_CALLS`；高成本 family 才补查 |
| question family 误判 | golden questions 覆盖典型问法；低置信度降级到 general brief |
| 复杂问题仍证据不足 | 明确返回限制，避免硬答 |
| 前端证据卡过载 | UI 只展示 brief 摘要，完整 tool trace 保持折叠 |

## 人工确认项

以下决策建议采用默认值，不阻塞进入实施计划，但可以在实现前调整：

1. 首批问题家族采用 9 类：`simple_ranking`、`entity_detail`、`preference_comparison`、`trend_preference`、`period_comparison`、`change_explanation`、`time_of_day_ranking`、`identity_preference`、`habit_summary`。
2. `preference_comparison` 默认必须查近期窗口；推荐窗口为 `last_6_months` 和 `last_4_weeks`。
3. `AnalyticalBrief` 首期优先做确定性规则，不调用额外 LLM。
4. `AnswerContractCritic` 首期只做可确定检查，不做第二个 LLM judge。
5. 前端维度胜负矩阵可以作为 Phase 5，不阻塞后端分析质量提升。

## 成功判据

这个设计成功时，AI 问答应表现出三个变化：

1. 它不再只回答“哪个数最大”，而是先说明问题口径。
2. 它能主动承认并解释冲突证据。
3. 它对不同问题家族采用不同证据配方和回答形状。

最终目标不是让每个答案都更长，而是让复杂问题更可靠、简单问题仍然简洁。
