# Agentic Longform Yearly Report 设计

> 创建日期：2026-07-03
> 状态：设计稿，待人工确认后进入实施计划
> 相关模块：`backend/services/ai_insights_service.py`、`backend/services/ai_agent_service.py`、`backend/domains/ai_agent/`、`backend/domains/ai_reports/`、`frontend/src/features/ai-insights/`、`frontend/src/features/ai-tasks/`
> 设计目标：把 AI 年度报告从“播放分析年度总结的文字复述”升级为“由只读 Report Agent 自主查询、分析、审稿后生成的长篇个人音乐年度分析文章”

## 背景

当前 AI 年度报告已经完成 V12 级别的事实安全改造：它能识别 2026 是截至 2026-06-23 的阶段性报告，能使用 TOP 专辑和个人 Billboard Year-End，能避免把本地个人 Billboard 误写成外部官方 Billboard，也能用 validator 阻止明显幻觉、错误年份、歌词/性别/人生事件等无依据叙事。

但用户侧体验仍然不满意。最新生成的报告虽然事实正确，却更像播放分析页面的文字版：概览、TOP 艺人、TOP 单曲、TOP 专辑、个人 Billboard、人格与流派、高光日、下半年观察。它只是把已有年度总结页面和 Billboard 页面里的数据重新排列，并没有产生 AI 报告应有的独特价值。

因此，下一阶段不应继续小修 prompt，而应重新定义 AI 年度报告的产品定位和生成范式。

核心判断：

- 播放分析年度总结页回答“发生了什么”。
- Billboard 页面回答“哪些歌曲、专辑、艺人在个人榜单里表现最好”。
- AI 年度报告应该回答“这些数据共同说明了你的音乐生活发生了什么结构性变化”。

AI 报告应该像一篇文章，而不是仪表盘摘要。它应该能把播放行为、个人 Billboard、同期对比、流派变化、新发现、长期偏好和异常时刻组织成有主线、有解释、有洞见的长文。

## 当前问题

### 1. 报告结构过于固定

当前报告结构基本固定为：

```text
标题
主线句
概览
核心艺人、单曲与专辑
个人 Billboard 年榜
人格与流派
高光日
下半年观察
```

这让 AI 报告看起来像年度总结页的二次渲染。不同年份、不同用户、不同音乐行为模式，最后都会得到类似结构，缺少“今年为什么特别”的辨识度。

### 2. 生成方式仍是一次性喂数据

当前年度报告流程是后端先汇总一大包 `yearly_data`，再交给 LLM 写报告。这种方式让 LLM 被动消费后端已经选好的字段，很难像分析师一样主动发现：

- 播放次数和个人 Billboard 是否一致？
- 哪些对象播放多但榜单不稳？
- 哪些对象播放不算最多但在榜很久？
- 新发现是否真的改变了专辑、流派或个人榜结构？
- 某一年更像“稳定统治”，还是“探索扩张”？

### 3. Billboard 证据被浅层使用

当前报告会列出个人 Billboard 年榜排名和在榜周数，但仍停留在“谁第几、在榜多久”。它没有系统分析：

- 统治力：No.1 周数、峰值与榜首持续性。
- 稳定性：weeks on chart、持续留榜能力。
- 爆发力：高峰值但短周期的对象。
- 长尾力：播放次数不最高但持续在榜的对象。
- 三榜联动：艺人榜、专辑榜、单曲榜是否互相印证。
- 分歧：播放次数与榜单成绩是否指向不同结论。

### 4. 报告缺少文章级洞见

当前报告常见句式是：

```text
X 以 N 次播放排在第一。
Y 位列榜单第 N，在榜 M 周。
流派前列包括 A、B、C。
```

这些句子是事实，不是分析。报告应该进一步回答：

- 这个事实为什么重要？
- 它和其他事实之间有什么关系？
- 它说明用户偏好发生了什么变化？
- 它对下半年或下一年的观察有什么启发？

### 5. fallback 容易伪装成正式报告

V12 fallback 是事实安全摘要。它适合作为兜底，但不应被当作正式 AI 年度文章。否则用户会看到一份 validator 合格、但没有真正分析价值的报告。

## 目标

1. 把年度报告从固定模板摘要升级为动态结构的长篇分析文章。
2. 让报告生成改为只读 Agent 自主查询，而不是后端一次性把所有数据塞给 LLM。
3. 系统性纳入播放分析和个人 Billboard 两套数据，并解释二者的关系。
4. 先生成洞见和大纲，再写文章，避免直接复述榜单字段。
5. 支持不同年份生成不同文章结构，结构由当年数据主线决定。
6. 引入文章质量 critic，拦截“数据罗列型报告”。
7. 保留 V12 的安全边界、validator、fallback 与任务进度能力，作为新流程的 safety layer。

## 非目标

- 不开放任意 SQL。
- 不开放任意 URL 抓取。
- 不访问外部官方 Billboard。
- 不新增写操作、设置修改、导入任务、播放列表创建或缓存清理工具。
- 不替代播放分析年度总结页；AI 报告是更高层解释，不是原页面迁移。
- 不要求报告每次都写成华丽散文；重点是有分析、有结构、有证据。
- 不在本阶段重做 AI Insights 前端视觉设计，只做必要的进度、证据和文章展示适配。

## 推荐路线

推荐实现 **Agentic Longform Yearly Report V14**。

V14 不推翻已有 AI Orchestrator、只读 Agent、AI task runs/events/tool_calls 和年度报告 V12 validator。它在这些能力之上新增一个专门的 Report Agent 工作流：

```text
Report Mission
  ↓
Tool-Driven Research Loop
  ↓
Evidence Ledger
  ↓
Insight Synthesis
  ↓
Dynamic Article Outline
  ↓
Longform Draft
  ↓
Editorial Critic
  ↓
Final Report or Repair
  ↓
Cache + UI Rendering
```

V12 的确定性 `yearly_data` 仍保留，但从“主输入”降级为：

- 工具之一：供 Report Agent 查询年度概览和基础统计。
- 兜底材料：Agent 失败时生成基础摘要。
- 校验材料：validator/critic 判断报告是否缺失关键事实。

## 产品定位

### AI 年度报告是什么

AI 年度报告是一篇个人音乐年度分析文章。它应该像一位熟悉 SpotifyStats 数据口径的音乐数据编辑写出的长文，使用播放记录和个人 Billboard 证据解释用户这一年的音乐偏好结构。

它应该具备：

- 一个清晰标题。
- 一个能概括全年的核心 thesis。
- 多个由数据支持的分析论点。
- 对播放数据和个人 Billboard 数据关系的解释。
- 对变化、冲突、异常、稳定中心、新发现的判断。
- 文章式段落，而不是列表式字段复述。

### AI 年度报告不是什么

它不是：

- 播放分析年度总结页的文字复述。
- TOP 榜单的自然语言版。
- 固定章节模板。
- 无依据情绪散文。
- 外部音乐市场报告。
- 官方 Billboard 解读。

## 报告长度与形态

建议长度：

| 报告类型 | 目标长度 | 说明 |
|---|---:|---|
| 年中/阶段性报告 | 1400-2200 中文字 | 足够展开主线、证据、解释和下半年观察 |
| 完整年度报告 | 1800-3000 中文字 | 增加全年回顾、阶段变化和年度总结 |
| fallback 基础摘要 | 800-1200 中文字 | 明确标记为基础摘要，不冒充正式长文 |

输出格式：

- Markdown。
- 使用 `##` 作为主章节。
- 可以使用少量 `###` 小节，但不做仪表盘式碎片化。
- 不使用长表格作为主体。
- 可以在结尾附“数据边界”短段，说明本地播放记录、个人 Billboard、数据截止日。

## 动态文章结构

报告结构不应固定。Agent 应先根据数据选择文章角度，再生成 outline。

可能的文章结构示例：

### 稳定中心 + 新入口型

适用于：一个长期主轴很强，同时出现明显新发现。

```text
标题：Taylor Swift 仍是中心，但新的中文入口正在打开
导语：今年真正的变化是什么
第一节：稳定中心如何成立
第二节：新入口为什么重要
第三节：专辑和单曲如何分工
第四节：个人 Billboard 揭示的稳定性
第五节：流派和地域版图如何变化
结尾：下半年最值得观察的问题
```

### 榜单统治型

适用于：某艺人/专辑/单曲在播放和个人 Billboard 中同时统治。

```text
标题：一条主线统治了你的音乐年
导语：播放行为与个人榜单共同指向同一中心
第一节：播放次数的统治
第二节：个人 Billboard 的统治
第三节：专辑、单曲、艺人三榜如何互相印证
第四节：统治之外还有哪些支线
结尾：这种统治是否会延续
```

### 探索扩张型

适用于：总播放下降或持平，但曲目数、艺人数、流派范围上升。

```text
标题：你不是听得更少，而是听得更散、更远
导语：数量下降和探索上升之间的张力
第一节：循环强度为何下降
第二节：探索范围如何扩大
第三节：新艺人、新专辑、新流派如何进入
第四节：个人 Billboard 中什么仍然稳定
结尾：下半年是继续扩张还是重新收束
```

### 冲突证据型

适用于：播放次数、时长、个人 Billboard、近期趋势指向不同对象。

```text
标题：播放次数说一件事，个人榜单说另一件事
导语：今年的偏好不是单一答案
第一节：累计播放指向谁
第二节：个人 Billboard 稳定性指向谁
第三节：近期趋势是否改变判断
第四节：如何理解这些冲突
结尾：更合理的分层结论
```

## Agent 工作流

### 1. Report Mission Prompt

系统提示词提供项目背景，而不是提供完整数据。

必须说明：

- SpotifyStats 分析本地 Spotify Extended Streaming History。
- 播放分析数据代表用户个人播放行为。
- 个人 Billboard 是基于本地播放记录计算的个人榜单，不是外部官方 Billboard。
- 年度报告目标是写长篇分析文章，不是复述年度总结页。
- Agent 必须自主调用只读工具获取证据。
- Agent 需要形成 thesis、证据、动态大纲和长文。
- 只能使用工具返回的数据，不得编造歌词含义、人生事件、艺人性别或外部市场结论。

### 2. Tool-Driven Research Loop

Report Agent 最多调用 12-20 次只读工具。默认预算建议：

| 类型 | 默认值 |
|---|---:|
| 最大工具调用数 | 16 |
| 最大运行时间 | 120 秒 |
| 最大 LLM 轮次 | 5 |
| 最低必要工具数 | 6 |
| 最低 Billboard 工具数 | 2 |

Agent 应按“先全局、后钻取、再验证”的顺序研究：

1. 查询年度/阶段性概览。
2. 查询同周期对比。
3. 查询 TOP 艺人、歌曲、专辑。
4. 查询个人 Billboard 年中/年榜三榜。
5. 对主轴实体做实体详情查询。
6. 对新发现或异常对象做补查。
7. 查询流派、时间、高光日或播放记录样本。
8. 汇总证据并判断是否足够。

### 3. Evidence Ledger

每次工具调用后写入 evidence ledger：

```json
{
  "tool_name": "yearly_overview",
  "params": {
    "year": 2026,
    "period_mode": "year_to_date"
  },
  "result_summary": "截至 2026-06-23，播放 7,860 次，累计 498 小时，覆盖 2,060 首曲目和 328 位艺人。",
  "supports": [
    "activity_level",
    "period_cutoff"
  ],
  "questions_raised": [
    "播放次数下降但曲目数上升，是否代表探索扩张？"
  ]
}
```

Evidence ledger 是最终报告可追溯性的核心。它同时服务：

- LLM 后续综合。
- UI 工具轨迹展示。
- critic 检查证据覆盖。
- 调试报告质量问题。

### 4. Insight Synthesis

工具调用后，Agent 必须先输出结构化洞见，而不是直接写文章。

```json
{
  "main_thesis": "Taylor Swift 仍是稳定中心，但 Zhang Zhen Yue 打开了今年最清晰的新入口；整体播放强度略降，探索半径扩大。",
  "supporting_arguments": [
    {
      "claim": "Taylor Swift 是稳定中心",
      "evidence_refs": ["artist_rank_1", "album_rank_1", "track_rank_1", "billboard_artist_rank_1"]
    },
    {
      "claim": "Zhang Zhen Yue 是新入口，不只是偶然出现",
      "evidence_refs": ["new_artist_rank", "albums_top5", "genre_shift"]
    }
  ],
  "billboard_findings": [
    "Taylor Swift 在个人艺人榜、专辑榜、单曲榜均有核心位置。",
    "The Life of a Showgirl 的专辑榜稳定性强于单纯播放次数所显示的程度。"
  ],
  "playback_findings": [
    "播放次数下降 10.0%，但曲目数增长 23.3%，更像从循环转向探索。"
  ],
  "tensions": [
    "总量下降与探索扩大同时存在。",
    "个人 Billboard 稳定中心与新发现扩张并存。"
  ],
  "interesting_anomalies": [
    "最活跃日最高单曲仅 4 次，说明高光日不是单曲循环，而是多曲目密集播放。"
  ]
}
```

### 5. Dynamic Outline

根据 insight synthesis 生成大纲。大纲必须包含每节要回答的问题，而不只是章节名。

```json
{
  "title": "Taylor Swift 仍是中心，但你的音乐版图正在外扩",
  "sections": [
    {
      "heading": "今年真正的变化",
      "question": "为什么播放量下降不等于音乐热情下降？",
      "claims": ["探索半径扩大", "核心循环减少"]
    },
    {
      "heading": "稳定中心如何成立",
      "question": "Taylor Swift 的中心地位是否被播放和个人 Billboard 同时支持？",
      "claims": ["艺人榜第一", "专辑榜第一", "单曲榜第一"]
    }
  ]
}
```

### 6. Longform Draft

最终草稿必须基于 outline 和 evidence ledger。每个主要段落都应遵循：

```text
判断 -> 证据 -> 解释 -> 对用户意味着什么
```

示例：

```text
Taylor Swift 的领先不是单点爆发，而是一个横跨艺人、专辑、单曲和个人 Billboard 的稳定中心。她以 1,115 次播放位居艺人榜首，《The Life of a Showgirl》是专辑榜首，Opalite 又是单曲榜首；个人 Billboard 中，她也保持了最长的艺人榜统治力。这说明 Taylor Swift 在 2026 上半年不是某一首歌带来的短期热度，而是构成了你音乐生活的基本坐标。
```

这种段落比“Taylor Swift 以 1115 次播放排在第一”更接近报告应有的价值。

### 7. Editorial Critic

Draft 完成后必须经过 critic。critic 不只检查事实错误，还检查文章质量。

critic 输出：

```json
{
  "ok": false,
  "issues": [
    {
      "code": "data_listing_too_heavy",
      "message": "连续多个段落只列排名和播放次数，缺少解释。"
    },
    {
      "code": "billboard_underused",
      "message": "个人 Billboard 只被列出排名，没有分析稳定性、统治力或三榜联动。"
    }
  ],
  "repair_instructions": [
    "把 TOP 艺人、专辑、单曲合并为 Taylor Swift 稳定中心的论证。",
    "增加一段解释播放次数下降但曲目数上升的含义。"
  ]
}
```

允许最多 2 次修订。若仍失败，使用 fallback 基础摘要，并在结果 metadata 中标记 `fallback_level=basic_summary`。

## 只读工具设计

Report Agent 不调用任意后端 API，而调用后端注册的 allowlist 工具。工具可以复用 AI Chat 的只读工具注册机制，但建议为年度报告增加 report-oriented wrapper，避免模型需要理解太多底层路由。

### 必备工具

| 工具 | 作用 |
|---|---|
| `report_period_context` | 返回 year、start/end date、is_partial_year、latest_play_date、同周期窗口 |
| `yearly_overview` | 年度/年中播放总量、时长、曲目数、艺人数、活跃日 |
| `yearly_top_entities` | TOP 艺人、歌曲、专辑，支持播放次数和时长 |
| `yearly_same_period_comparison` | 当前周期 vs 去年同期，不允许 partial-year 对比去年全年 |
| `personal_billboard_year_end` | 个人 Billboard 单曲/专辑/艺人年中/年榜 |
| `personal_billboard_entity_detail` | 单个实体 peak、weeks、No.1、走势、power score |
| `entity_stats` | 艺人/专辑/歌曲播放统计、时间窗口、时长、首次/最近播放 |
| `genre_distribution` | 流派占比、标签 caveat、可能重叠说明 |
| `discovery_and_returns` | 新发现艺人、回归对象、最长情对象 |
| `highlight_day_detail` | 最活跃日播放明细、top track repeat、是否循环或多样化 |
| `listening_time_profile` | 时段分布、白天/夜晚/深夜比例 |
| `playback_records_sample` | 必要时查看有限播放记录样本，用于解释某天或某阶段 |

### Billboard 分析工具增强

建议新增一个聚合工具：

`billboard_yearly_diagnostics`

返回：

```json
{
  "dominance": {
    "artist": "Taylor Swift",
    "reason": "artist rank #1, 25 weeks on chart, 9 weeks at No.1"
  },
  "stability_leaders": [
    {"entity": "Taylor Swift", "type": "artist", "weeks_on_chart": 25},
    {"entity": "The Life of a Showgirl", "type": "album", "weeks_on_chart": 24}
  ],
  "breakout_leaders": [
    {"entity": "Zhang Zhen Yue", "type": "artist", "first_seen": "2026-03-09", "rank": 4}
  ],
  "cross_chart_alignment": [
    {
      "entity": "Taylor Swift",
      "alignment": "artist_album_track_all_strong",
      "evidence": ["artist #1", "album #1", "track #1"]
    }
  ],
  "playback_billboard_tensions": []
}
```

这个工具不是替代 LLM 分析，而是把 Billboard 的可分析维度结构化暴露出来。

## 数据口径

### 年中与全年

若 `is_partial_year=true`：

- 标题和导语必须写“截至 YYYY-MM-DD”。
- 可称“年中报告”“阶段性报告”“上半年报告”，不得称完整年度总结。
- 不使用“年度专辑榜”“年度单曲冠军”“来年寄语”等完整年度表达。
- 同比只能使用 same-period YTD。
- Billboard 可称“个人 Billboard 年中榜”或“阶段性个人年榜”。

若 `is_partial_year=false`：

- 可称“年度报告”“全年总结”。
- 可使用完整上一年对比。
- 不应写“年中”“阶段性”“下半年观察”。

### 个人 Billboard

所有报告必须保留语义边界：

- 个人 Billboard 是本地个人榜单。
- 它基于用户自己的播放记录和项目内部计算口径。
- 它不是外部官方 Billboard。
- 它可以用于分析个人偏好稳定性、峰值、持续性和统治力。
- 不得扩展为市场影响力、官方成绩、全球热度。

## 前端体验

V14 不需要重做 AI Insights 页面，但应该增强年度报告生成过程的可观察性。

### 进度阶段

年度报告任务事件建议展示：

1. 理解报告任务。
2. 查询年度播放概览。
3. 查询个人 Billboard 三榜。
4. 分析主线和异常。
5. 生成文章大纲。
6. 撰写长篇报告。
7. 审稿与修订。
8. 保存报告。
9. 完成。

### 工具轨迹

前端应展示用户可读 trace：

```text
查询 2026 年中播放概览
查询 2026 个人 Billboard 单曲/专辑/艺人榜
查询 Taylor Swift / Zhang Zhen Yue 详情
分析播放量下降与探索范围扩大
生成文章大纲并审稿
```

默认折叠详细 JSON，只展示用户能理解的摘要。

### 报告结果 metadata

最终结果应包含：

```json
{
  "report_mode": "agentic_longform",
  "contract_version": "agentic_yearly_v14",
  "fallback_level": null,
  "tool_calls": 13,
  "data_range": "2026-01-01 to 2026-06-23",
  "is_partial_year": true,
  "critic_passed": true,
  "article_length": 1840
}
```

## 缓存与 fallback

### 缓存 key

缓存 key 必须包含：

- report type。
- contract version。
- year。
- filters fingerprint。
- report mode (`agentic_longform`)。
- tool registry version。
- project context version。

### fallback 分级

| fallback_level | 触发条件 | 用户展示 |
|---|---|---|
| `none` | Agent 成功，critic 通过 | 正式 AI 报告 |
| `repaired_draft` | 初稿失败，修订后通过 | 正式 AI 报告，可记录修订 |
| `basic_summary` | Agent/critic 失败，但基础数据可用 | 标记为“基础摘要”，不伪装成长文 |
| `error` | 数据或 LLM 不可用 | 显示可重试错误 |

V12 fallback 可作为 `basic_summary` 的基础，但需要在 UI 和 metadata 中明确区别正式长文。

## Validator 与 Critic

### 事实安全 validator

继续保留 V12 validator：

- 年中/全年口径。
- TOP 实体名称。
- 个人 Billboard caveat。
- 禁止歌词/性别/别名/外部官方 Billboard/场景幻觉。
- 流派 caveat。
- 高光日低置信循环判断。

### 文章质量 critic

新增 editorial critic，检查：

| Code | 含义 |
|---|---|
| `too_short_for_longform` | 正式报告低于最低长度 |
| `dashboard_restatement` | 结构过于接近播放分析年度总结页 |
| `data_listing_too_heavy` | 连续大量句子只列数字和排名 |
| `missing_main_thesis` | 没有清晰核心主线 |
| `thesis_not_developed` | 开头有 thesis，但正文未展开 |
| `billboard_underused` | Billboard 只列排名，没有解释统治力/稳定性/三榜关系 |
| `playback_billboard_not_connected` | 播放数据和 Billboard 数据没有互相解释 |
| `no_interpretation` | 段落有事实但没有“所以呢” |
| `generic_conclusion` | 结尾只是泛泛继续观察，没有提出具体问题 |
| `fixed_template_shape` | 章节顺序与固定模板高度一致 |

### 反数据罗列规则

可用启发式：

- 若超过 40% 句子包含数字但没有解释词，标记风险。
- 若连续 3 句以上都是 `X 以 N`、`X 位列`、`X 播放`，标记风险。
- 若 Billboard section 只包含 rank/weeks，没有 dominance/stability/alignment 词，标记风险。
- 若每个 section 都对应一个 dashboard widget，标记 `fixed_template_shape`。

解释词不应硬编码成唯一标准，但可以包含：

```text
说明、意味着、反映、相比、不是...而是、共同指向、形成、支撑、改变、转向、稳定、扩张、收束、分化、矛盾
```

## 测试策略

### Unit tests

- Report tool registry 只暴露 read-only 工具。
- Agent budget 正确限制工具次数。
- Evidence ledger 记录每次工具调用。
- Billboard diagnostics 能输出 dominance/stability/cross-chart alignment。
- Dynamic outline 根据不同 diagnosis 选择不同结构。
- Critic 能拒绝数据罗列型报告。
- Critic 能拒绝 Billboard 只列排名的报告。
- Critic 能拒绝 partial-year 中完整年度措辞。
- fallback metadata 正确标记 `basic_summary`。

### Contract tests

- `/api/ai-insights/yearly-story` 或新 endpoint 返回 `report_mode`、`task_id`、`metadata`。
- AI task events 包含 research、outline、draft、critic 阶段。
- 工具轨迹持久化到 `ai_tool_calls`。
- LLM 未配置时返回明确错误或基础摘要，不产生 500。
- 缓存命中不重新调用工具。

### Golden report tests

至少准备以下问题/年份样本：

1. 2026 年中：稳定中心 + 新入口 + 探索扩张。
2. 完整年份：完整年度报告不得写“年中/下半年观察”。
3. Billboard 统治型：单一艺人三榜统治。
4. 冲突证据型：播放次数和个人 Billboard 指向不同对象。
5. 稀疏数据型：数据不足时生成基础摘要或明确限制。

每个样本验收：

- 长度达标。
- 有主线。
- 有 Billboard 分析。
- 有播放与 Billboard 关系解释。
- 不像年度总结页重述。
- 无事实口径错误。

### Browser/user-flow tests

- 在 `/ai-insights` 手动点击生成 2026 年中报告。
- 页面显示多阶段 task progress。
- 工具轨迹包含播放概览、个人 Billboard、实体详情。
- 最终 Markdown 长文渲染正常。
- 表格、标题、段落在桌面和移动端不溢出。
- 生成失败时显示基础摘要或可重试错误。

## 分阶段实施建议

### Phase 1: Spec-to-plan and tool inventory

- 整理现有 AI Chat 工具中哪些可复用于 Report Agent。
- 定义 report-oriented 工具 registry。
- 明确 endpoint 复用还是新增。
- 写实施计划。

### Phase 2: Report Agent research loop

- 新增 `yearly_report_agent_service.py` 或拆分 `ai_insights_service.py` 中年度报告逻辑。
- 接入 task events。
- 实现工具预算和 evidence ledger。
- 初步生成 insight synthesis。

### Phase 3: Billboard diagnostics and dynamic outline

- 新增 `billboard_yearly_diagnostics`。
- 实现 `InsightSynthesis` 和 `DynamicOutline` schema。
- 增加测试覆盖不同报告结构。

### Phase 4: Longform draft and editorial critic

- 新增长文 prompt。
- 新增 critic prompt + deterministic heuristics。
- 支持最多 2 次修订。
- 保留 V12 validator 作为事实安全层。

### Phase 5: UI and probes

- 前端展示 research/outline/critic 进度。
- 扩展文本质量 probe。
- 增加 browser smoke。
- 更新 docs 和 changelog。

## 验收标准

功能通过的最低标准：

1. 2026 年中报告不再只是数据罗列，长度至少 1400 中文字。
2. 报告有一个明确 thesis，并在正文至少 3 个 section 中展开。
3. 报告同时使用播放分析和个人 Billboard，且解释二者关系。
4. 个人 Billboard 至少分析一个维度：统治力、稳定性、爆发力、长尾力或三榜联动。
5. 报告结构可随数据变化，不固定复刻年度总结页。
6. 工具调用轨迹可见，且工具均为只读 allowlist。
7. critic 能拒绝当前 V12 fallback 这种数据罗列型文本。
8. fallback 被明确标记为基础摘要，不作为正式长文。

## 开放问题

1. 年度报告是否继续使用现有 `/api/ai-insights/yearly-story`，还是新增 `/api/ai-insights/yearly-report-agent`？
   - 推荐：先复用现有用户入口，内部以 `report_mode=agentic_longform` 区分；必要时保留旧模式参数便于回滚。
2. Report Agent 是否允许查询有限播放记录样本？
   - 推荐：允许只读、分页、上限明确的样本查询，用于解释高光日和阶段变化。
3. 长文报告是否需要流式输出？
   - 推荐：本阶段不做 token streaming，先用 task progress + 最终长文，降低复杂度。
4. 是否保留短摘要版本？
   - 推荐：保留，但作为“基础摘要”或“快速摘要”，不替代正式 AI 报告。

## 设计自检

- 没有开放任意 SQL、任意 URL 或写操作。
- 没有推翻现有 AI task/event/tool_calls 架构。
- 没有把 AI 报告定位为年度总结页替代品。
- 已明确个人 Billboard 与外部官方 Billboard 的边界。
- 已明确为什么要由 Agent 自主查询，而不是一次性喂数据。
- 已明确文章质量 critic 如何阻止数据罗列。
- 已明确 fallback 与正式长文的区别。
