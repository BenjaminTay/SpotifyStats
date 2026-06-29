# AI Project Context Prompt 设计

> 创建日期：2026-06-29  
> 状态：设计稿，待人工确认后进入实施计划  
> 相关模块：`backend/services/ai_agent_service.py`、`backend/domains/ai_agent/`、`backend/tests/fixtures/ai_agent_golden_questions.json`  
> 设计目标：为 AI 问答补一层稳定的项目语境，让 LLM 不只“会查数据”，还理解 SpotifyStats 的产品定位、统计口径和回答气质

## 背景

AI Observable Agent Orchestrator V2 与 Universal Analytical Harness 已经让问答具备只读工具规划、证据卡片、工具轨迹、QuestionFrame、EvidenceRecipe、EvidenceSufficiency、AnalyticalBrief、AnswerContract critic 和 golden-question harness。

这些能力解决的是“能不能查到正确数据”和“能不能避免明显矛盾”。但用户连续测试后仍有一个感受：LLM 对这个项目理解不深。它经常像一个通用数据查询器，只是在工具结果上做摘要，而不是像一个理解 SpotifyStats 的音乐数据分析助手。

这不是单个 bug，也不是模型智力问题。当前缺口是：系统没有一个明确、稳定、可复用的 Project Context Layer。Prompt 里散落着“本地 Billboard 不是官方 Billboard”“只基于 DATA 回答”等规则，但缺少完整的项目世界观、用户期望和分析哲学。

## 当前相似能力

| 现有能力 | 已解决 | 缺口 |
|---|---|---|
| `PLANNER_SYSTEM_PROMPT` | 约束 LLM 只能规划后端 allowlist read-only 工具 | 不解释项目是什么、哪些工具语义代表哪些产品概念 |
| `FINAL_ANSWER_SYSTEM_PROMPT` | 约束最终回答只基于 DATA、遵守 coverage / analytical brief | 只有局部规则，缺少稳定回答哲学和项目语气 |
| `QuestionFrame` / `EvidenceRecipe` | 判断问题家族、证据轴和最低工具配方 | 偏分析协议，不承载产品定位和用户偏好 |
| `AnalyticalBrief` | 给最终回答提供结构化分析底稿 | 不负责告诉模型“SpotifyStats 的分析应该像什么” |
| `Answer critic` | 抓 forbidden claims、coverage 矛盾和证据不足 | 主要抓错误，不提升项目理解深度 |
| Golden harness | 防止工具选择和 frame 回退 | 还没有把“项目语境是否被传入 prompt”作为可测试契约 |

因此本设计不替代现有 harness，而是在它上方新增一个可复用的 Project Context Prompt。

## 目标

1. 让 planner 和 final answer 都稳定理解 SpotifyStats 的产品定位：个人音乐数据、个人榜单、音乐偏好叙事，而不是官方行业数据查询。
2. 让 LLM 明确核心统计口径：播放次数、播放时长、近期强度、单位时间强度、个人 Billboard、发行/进入播放历史时间、公平性限制。
3. 让回答风格更贴近用户：先回答真正问题，再给必要证据；简单问题短答，复杂问题分层；避免工具流水账和模板化报告。
4. 让项目语境集中维护，避免散落在多个 prompt 字符串里越改越乱。
5. 通过单元测试和 golden harness 防回归，确保 project context 被注入 planner / final answer，并且不会覆盖只读安全边界。

## 非目标

- 不开放任意 SQL、任意 URL、外部 Billboard 或写操作。
- 不把所有项目文档全文塞进 prompt。
- 不让 Project Context 替代 QuestionFrame、EvidenceRecipe、AnalyticalBrief 或 AnswerContract。
- 不在本阶段改报告生成、艺人/专辑 enrichment 的 prompt；首批只覆盖 AI 问答 Agent。
- 不用一堆 few-shot 替代确定性工具和证据配方。
- 不追求让应用内 LLM 完全达到 Codex 的理解水平；目标是达到 70%-80% 的项目理解和回答稳定性。

## 设计原则

### 1. 项目语境短而稳定

Project Context 不应超过 1000-1800 中文字。它要像“项目宪法”，不是 README 摘抄。

需要长期稳定的内容：

- SpotifyStats 是个人 Spotify Extended Streaming History 分析应用。
- 数据来自用户本地播放记录和本地派生聚合。
- Billboard 在本项目里是个人 Billboard，是基于用户播放行为计算的本地榜单。
- 用户想要的是可解释的音乐偏好分析，不是机械数据转述。
- 简单问题要直接，复杂问题要分层和说明边界。
- 不知道时必须补查可用工具；工具证据不足时说明限制。

不应放入 Project Context：

- 具体文件路径和实现细节。
- 当前未稳定的实验性功能。
- 长篇历史 changelog。
- 会频繁变动的测试数量、端口、构建命令。

### 2. Context 不替代证据

Project Context 只提供“如何理解项目和如何回答”的规则。最终事实仍必须来自 tool results、evidence cards、coverage、EvidenceSufficiency 和 AnalyticalBrief。

禁止：

- 用 Project Context 编造用户偏好。
- 用项目介绍替代工具查询。
- 没有证据时给确定性结论。

### 3. Planner 和 Final Answer 看到不同侧重点

Planner 需要的是“项目语义 + 工具选择 playbook”。

Final Answer 需要的是“项目语义 + 回答哲学 + 禁止误述”。

不要把完全相同的一大段 prompt 粘到所有 LLM 调用。建议拆成可组合片段：

- `PROJECT_CONTEXT_PROMPT`
- `TOOL_PLAYBOOK_PROMPT`
- `ANSWER_PHILOSOPHY_PROMPT`
- `SAFETY_BOUNDARY_PROMPT`

### 4. Prompt 作为代码契约测试

Prompt 不是散文资产，而是 harness 的一部分。需要测试：

- planner prompt 包含 project context version 和 read-only boundary。
- final prompt 包含个人 Billboard 语义和 answer style 规则。
- thinking final prompt 不会强制变长。
- golden harness 中高价值问题仍能匹配 frame、recipe 和 critic 预期。

## Project Context Prompt 草案

建议首版核心文案如下，实际实现可按模块拆分，但语义应保持一致。

```text
你正在为 SpotifyStats 回答问题。SpotifyStats 是一个基于用户本地 Spotify Extended Streaming History 的个人音乐数据分析应用，不是通用音乐百科，也不是官方 Billboard 或市场数据查询工具。

本项目的核心数据来自用户自己的播放记录、账号收藏、Spotify 元数据、album project / track group 聚合，以及基于这些本地数据计算出的个人 Billboard。除非工具结果明确提供，否则不要声称知道用户在其他平台、离线环境或外部市场中的行为。

SpotifyStats Billboard 永远表示“用户个人播放行为生成的本地榜单”。它可以说明一首歌、专辑或艺人在用户个人数据中的榜单统治力、峰值、在榜周数、Power Score 和稳定性，但不能表述为外部官方 Billboard、商业成绩、市场影响力或大众流行度。

分析用户偏好时，不要把播放次数直接等同于“最喜欢”。应按问题需要区分累计播放次数、播放时长、近期窗口、单位时间强度、稳定性、峰值、个人 Billboard 表现、发行时间和进入用户播放历史的时间。不同指标冲突时要分层回答，而不是强行说所有指标都指向同一个对象。

回答应像一个懂用户音乐数据的分析助手：先直接回答用户真正问的问题，再给关键数字和必要边界。简单排行或事实问题默认短答；比较、趋势、原因、身份偏好等复杂问题才展开。不要把工具调用过程写成正文，不要输出模板化“我查了什么/自检与限制”，除非用户明确要求详细说明或证据不足。

你只能基于系统提供的 DATA、工具结果、证据卡片、coverage、EvidenceSufficiency 和 AnalyticalBrief 回答。若证据不足，应说明缺口，并优先使用可用只读工具补查；不要编造工具、SQL、URL、外部搜索或写操作。
```

## Tool Playbook 草案

Planner prompt 应额外看到更短的工具选择规则：

```text
工具选择原则：
- 总体播放量、时间范围、Top 艺人/歌曲/专辑：优先 analysis_stats / analysis_charts / wrapped_yearly。
- 指定艺人、专辑、歌曲详情：优先 entity_stats；若用户提到榜单、Power Score、冠军周或个人 Billboard，再补 billboard_entity_detail。
- 2-4 个同类实体比较：优先 compare_entities；不要拆成大量单实体查询，除非需要补近期窗口。
- “更喜欢/喜爱程度/本命/偏好”不是单一播放次数问题；需要累计、近期、强度、稳定性或个人 Billboard 等多轴证据。
- 指定艺人范围内问最喜欢的专辑/歌曲：必须用 entity_stats(entity=artist) 的 top_albums/top_tracks，不能用全局 Top10 缺席判断。
- 趋势、最近、变化、下降、回升：不能只查 lifetime，必须查近期窗口或分期数据。
- 深夜/上午/时段类问题：必须使用 listening_hours 的对应 view。
```

## Answer Philosophy 草案

Final answer prompt 应额外看到：

```text
回答原则：
- 第一段先回答，不要先解释工具过程。
- 默认 answer_style=concise 时，3-6 句或最多 3 个 bullet。
- answer_style=structured 时，可以使用短小标题、表格或列表，但不写流水账。
- answer_style=detailed 时，才展开完整依据、限制和自检。
- 有冲突证据时，用“长期/近期/强度/榜单”分层，而不是压成假确定性。
- 所有数字都要能从 DATA 找到；没有来源的数字不要写。
- 必须保留本地个人 Billboard 与外部官方 Billboard 的边界。
```

## 接入架构

```text
backend/domains/ai_agent/project_context.py
  ├── PROJECT_CONTEXT_VERSION
  ├── PROJECT_CONTEXT_PROMPT
  ├── TOOL_PLAYBOOK_PROMPT
  ├── ANSWER_PHILOSOPHY_PROMPT
  ├── SAFETY_BOUNDARY_PROMPT
  ├── planner_system_prompt(base_prompt)
  └── final_answer_system_prompt(base_prompt, thinking_mode)

backend/services/ai_agent_service.py
  ├── PLANNER_SYSTEM_PROMPT = planner_system_prompt(...)
  ├── FINAL_ANSWER_SYSTEM_PROMPT = final_answer_system_prompt(...)
  └── THINKING_FINAL_ANSWER_SYSTEM_PROMPT = final_answer_system_prompt(..., thinking_mode=True)
```

也可以不使用 builder，而是直接在 `ai_agent_service.py` 拼接常量。但首选独立模块，原因是：

- prompt 变成可测试单元。
- 后续报告/enrichment 要复用项目语境时不用复制。
- 可以在 payload 中加入 `project_context_version`，便于调试回答质量。

## 数据流变化

### Planner

当前：

```text
PLANNER_SYSTEM_PROMPT + DATA(question_intent/question_frame/evidence_recipe/tools)
```

调整为：

```text
PROJECT_CONTEXT_PROMPT
+ TOOL_PLAYBOOK_PROMPT
+ SAFETY_BOUNDARY_PROMPT
+ PLANNER_SYSTEM_PROMPT
+ DATA(question_intent/question_frame/evidence_recipe/tools)
```

### Final Answer

当前：

```text
FINAL_ANSWER_SYSTEM_PROMPT + DATA(tool_results/evidence_cards/coverage/brief/answer_style)
```

调整为：

```text
PROJECT_CONTEXT_PROMPT
+ ANSWER_PHILOSOPHY_PROMPT
+ SAFETY_BOUNDARY_PROMPT
+ FINAL_ANSWER_SYSTEM_PROMPT
+ DATA(tool_results/evidence_cards/coverage/brief/answer_style/project_context_version)
```

### Thinking Mode

Thinking mode 不改变项目语境，只改变工具规划和可见分析摘要。它不能自动进入长报告模式。

## Golden Examples 设计

Project Context 不宜放太多 few-shot，但 golden harness 应覆盖这些项目语境回归：

| 问题 | 应体现的项目理解 |
|---|---|
| “从播放次数和 billboard 榜单成绩来看，我对 GUTS 和 The Life of a Showgirl 哪张更喜欢？” | 知道 billboard 是个人 Billboard；按长期/近期/强度/公平性分层 |
| “我最喜欢的 Ariana Grande 的专辑和歌曲是什么？” | 知道是艺人范围内排行；用 top_albums/top_tracks；默认短答 |
| “我深夜最爱听什么歌？” | 知道不能用总体排行；必须查时段工具 |
| “2023 年我听最多的艺人是谁？” | 简单事实问题短答，说明时间范围和指标即可 |
| “Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？” | 知道本命不是单一播放次数；需要长期、近期、稳定性、峰值分层 |

首版不强求 LLM few-shot 输出完全一致，但需要 golden fixture 检查 frame、recipe、required tool patterns、forbidden claims 和 answer style。

## 实施步骤

### Phase 1：新增 Project Context 模块

新增：

- `backend/domains/ai_agent/project_context.py`
- `backend/tests/unit/test_ai_agent_project_context.py`

测试要求：

- `PROJECT_CONTEXT_VERSION` 非空。
- `PROJECT_CONTEXT_PROMPT` 包含“个人 Spotify”“本地播放记录”“个人 Billboard”“不是外部官方 Billboard”。
- `TOOL_PLAYBOOK_PROMPT` 包含 `entity_stats(entity=artist)`、`compare_entities`、`listening_hours` 等关键工具语义。
- `ANSWER_PHILOSOPHY_PROMPT` 包含“默认短答”和“不要工具调用流水账”。
- prompt 总长度在预算内，例如所有片段拼接后不超过 2500-3200 中文字符。

### Phase 2：接入 planner / final answer

修改：

- `backend/services/ai_agent_service.py`

要求：

- Planner system prompt 引入 `PROJECT_CONTEXT_PROMPT`、`TOOL_PLAYBOOK_PROMPT`、`SAFETY_BOUNDARY_PROMPT`。
- Final answer 和 thinking final answer 引入 `PROJECT_CONTEXT_PROMPT`、`ANSWER_PHILOSOPHY_PROMPT`、`SAFETY_BOUNDARY_PROMPT`。
- `_final_payload()` 增加 `project_context_version`。
- Retry prompt 也要求遵守 project context 和 answer style。

测试：

- contract test monkeypatch `_llm_chat`，确认 planner/final system prompt 包含 project context version 或核心短语。
- 确认 thinking mode prompt 不包含强制四段式。
- 确认 `project_context_version` 出现在 final payload。

### Phase 3：扩展 answer critic 与 golden harness

修改：

- `backend/domains/ai_agent/answer_critic.py`
- `backend/tests/fixtures/ai_agent_golden_questions.json`
- `scripts/evaluate_ai_agent_harness.py`

要求：

- Critic 保持 deterministic，不引入 LLM critic。
- 新增或强化 forbidden claims：
  - “官方 Billboard”
  - “市场影响力”
  - “商业成绩”
  - “所有指标均指向”
  - 对 scope ranking 使用全局 Top10 缺席下结论
- Golden fixture 新增 `expected_answer_style` 或利用现有 expected frame 检查 answer style。

### Phase 4：文档同步

修改：

- `docs/CHANGELOG.md`
- `AGENTS.md`
- `backend/CLAUDE.md`

可选：

- `docs/superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md` 不建议改，它记录的是已实施的分析中间层；本次应单独建 plan。

同步内容：

- 新增 Project Context Layer 的职责。
- 明确它不替代证据配方和只读边界。
- 更新验证命令和 golden harness 数量。

### Phase 5：真实问题验收

需要至少手工或脚本验证以下问题：

1. “我最喜欢的 Ariana Grande 的专辑和歌曲是什么？”
   - 期望：短答，艺人范围内排行，给 top album / top track，不写工具流水账。
2. “从播放次数和 billboard 榜单成绩来看，我对 GUTS 和 The Life of a Showgirl 哪张更喜欢？”
   - 期望：个人 Billboard 边界明确，分层，不说市场影响力。
3. “我深夜最爱听什么歌？”
   - 期望：调用时段工具，不用全局排行替代。
4. “Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？”
   - 期望：多轴分层，不把播放次数直接等同于本命。

## 验证矩阵

最低验证：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider \
  backend/tests/unit/test_ai_agent_project_context.py \
  backend/tests/unit/test_ai_agent_question_frame.py \
  backend/tests/unit/test_ai_agent_evidence_recipes.py \
  backend/tests/unit/test_ai_agent_coverage_review.py \
  backend/tests/unit/test_ai_agent_analytical_brief.py \
  backend/tests/unit/test_ai_agent_answer_critic.py \
  backend/tests/unit/test_ai_agent_golden_questions.py \
  backend/tests/unit/test_ai_agent_evidence.py \
  backend/tests/contract/test_ai_agent_task_contract.py -q

.venv/bin/python scripts/evaluate_ai_agent_harness.py
.venv/bin/ruff check backend/domains/ai_agent backend/services/ai_agent_service.py
git diff --check
```

若涉及前端展示，不在本轮默认范围；如果顺手暴露 `project_context_version` 到 UI，再补前端 Vitest 与浏览器 smoke。

## 风险与控制

| 风险 | 控制 |
|---|---|
| Prompt 太长稀释任务指令 | 控制总字符预算；只保留稳定项目语境 |
| Project Context 被模型当作事实来源 | 明确“事实只能来自 DATA/tool results” |
| Few-shot 过拟合具体问题 | 示例放入 golden harness，不大量塞进 prompt |
| 和 AnalyticalBrief 职责重叠 | Context 讲世界观；Brief 讲本次问题的证据和结论 |
| 文档逐渐过期 | 单独 `PROJECT_CONTEXT_VERSION`，变更必须更新测试和 changelog |
| 简单问题又变啰嗦 | Answer Philosophy 明确默认短答；answer_style 继续作为硬约束 |

## 待人工确认

1. 首批是否只接入 AI 问答 Agent，不接入周报/月报/年度叙事？
   - 建议：只接入问答 Agent。报告 prompt 以后单独收敛。
2. Project Context 的语气是否采用“懂个人音乐数据的分析助手”，而不是更文学化的音乐评论人？
   - 建议：分析助手优先，保留少量音乐叙事感。
3. 是否允许在 prompt 中明确提到“用户期待”？
   - 建议：允许，但只写通用产品期待，不写用户私人偏好。
4. 是否把 `project_context_version` 存入 task result 方便未来排查？
   - 建议：存入 result metadata，但前端不展示。

## 完成标准

- Project Context 以单一源码存在，不再散落复制。
- Planner 和 final answer 都能看到项目语境，但仍遵守只读边界。
- Final payload 包含 `project_context_version`。
- Golden harness 覆盖项目语境代表问题。
- 真实 `/ai-insights` 问答不再像通用数据查询器，而是能体现个人音乐数据、个人 Billboard、分层偏好和默认短答的产品理解。

