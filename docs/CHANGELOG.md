# 变更日志

## 2026-08-03 — 音乐源数据管理与有效曲目署名

- 新增不改写 `plays`、`tracks`、`track_artists` 原始事实的人工曲目署名覆盖层，支持按稳定本地艺人 ID 添加、移除和调整 primary/featured 角色；append-only 事件、全局 revision、重建状态与撤销链保留完整可追溯性。
- 建立统一有效署名 resolver：原始署名叠加人工覆盖后投影到 canonical artist，并按曲目、播放事件和 canonical 身份去重；Billboard、对决、详情、播放分析、搜索、Wrapped 与 AI 等消费者统一读取该结果，避免合作艺人与身份 alias 重复计数。
- 新增 `/api/music-metadata/track-credits` 管理 API、OpenAPI 类型、查询缓存失效与周聚合 shadow rebuild。真实样本 `Hold Me Closer` 保留 Elton John 原始 primary，并以本地稳定实体添加 Britney Spears featured，原始播放与署名事实不变。
- Settings 的 `05 · 音乐源数据管理` 收口为“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块。“归并与版本”只保留一套 L1/L2/L3、自动检测、已保存分组和手动创建入口，再按歌曲归并或专辑版本显示对应字段与高级选项；后续设置编号连续顺延。
- 单曲、专辑、艺人详情提供精确的管理深链；只有携带实体上下文的外部深链会执行一次定位和预填，Settings 内普通模块切换保持当前视口稳定，旧 metadata 参数继续兼容。
- 新增模型迁移、resolver/重建、API contract、Settings 管理流程、深链和滚动行为测试；全量后端、前端生产构建及 1440/390 浏览器验收均已覆盖。

## 2026-08-03 — Billboard 总榜跨层级指标与表格控制

- 专辑总榜新增成员歌曲走势点数/排名；艺人总榜新增 credited canonical 歌曲与专辑走势点数/排名。聚合复用详情与对决的 album project membership、artist fan-out 和 identity 去重语义，并以当前完整同类总榜为排名集合；正值按 competition rank 排名，零贡献显示 0 且不生成虚假名次。
- `/api/billboard/all-time`、`/power-scores` 与生成类型补齐新字段，并把 `include_compilations` 纳入 staged power/summary 缓存参数；不改变实体自身 Power Score、主排名或周榜筛选口径。
- 单曲、专辑、艺人总榜加入客户端表内搜索和各自独立持久化的字段菜单。名称和当前总榜排名固定显示，实体走势评分与走势排名可独立选择；无效旧字段配置会被忽略，新字段按推荐值迁移，可一键恢复经过桌面/移动端信息密度校准的推荐列集。
- 数值列统一右对齐并保留列宽拖拽；单曲榜桌面工具栏按“筛选 → 字段/搜索 → 分页”收口为单行，分页恢复为上一页/当前页提示/下一页的既有紧凑形态，移动端继续自适应换行且不引入页面级横向滚动。

## 2026-08-03 — 未入榜音乐实体详情页

- 将歌曲、专辑、艺人详情的存在资格从 Billboard Top-N summaries 中拆出，复用全局搜索与个人实体统计的有效播放管线；有效播放实体即使暂未入榜也返回 200，并保留 canonical track、album project + canonical artist、artist identity alias 语义。
- 详情响应新增 `chart_status` 与 `effective_play_count`；专辑另有 `track_chart_status`，艺人另有 `track_chart_status` / `album_chart_status`，主榜与子成绩独立判断。未入榜时对应摘要为 `null`、历史为空数组，不再用 `#0` 或零值伪装成绩；真正无有效播放且无法解析的实体改为 404。
- 三类前端详情以播放统计为默认主内容，并始终保留固定 Tab。单曲、专辑、艺人主榜及其单曲/专辑子成绩分别显示精确空态，发行档案、发行周期、艺人生涯与歌词不再因榜单为空而消失。
- 修复“专辑榜已入榜但没有成员歌曲进入单曲榜”被误判为未入榜：专辑详情先按 album project identity + canonical artist 读取 `weekly_album`，`album_track_counts` / `track_per_album` 仅作为可选单曲成绩。真实数据 `CONFESSIONS II` 恢复为峰值 #4、在榜 2 周，单曲成绩保持独立空态。
- versus picker 继续只列可与详情榜单指标对照的实体，与详情可访问资格刻意分离；新增 contract 与前端空态测试锁定该边界，并刷新 OpenAPI 快照和生成类型。

## 2026-08-03 — Billboard 对决与详情统计口径统一

### 统计与数据归属

- 单曲、专辑、艺人对决、实体选择列表和对应详情页统一透传动态阈值、连续播放间隔、合并级别、榜单周边界、三类 Top N、年份范围与精选集设置；前端缓存键同步纳入完整过滤指纹，避免设置变化后复用旧结果。
- 专辑对决移除基于 legacy release group 与周榜专辑名称的归属路径，改为复用详情页的 album project、`track_per_album` 与 `album_track_counts`，按专辑项目身份和 canonical artist 消歧；无法与详情口径可靠对应的 picker 实体会被保守排除。
- 艺人对决与详情统一 credited artist fan-out；冠军周数按稳定歌曲 ID 归属到全部署名 canonical artist，并对同一 canonical 身份去重，修复 featured artist 少计。

### 交互与文案

- 对决搜索添加实体后保留查询词与结果列表，支持连续添加同一搜索结果集中的多个实体；切换实体类型时才重置。
- 将“单周最多播放”明确为“入榜周最高播放”，区分个人全部有效播放与入榜周播放，并标注发行后 24 周窗口和 aggregate rank 的派生含义。

### 验证

- 新增专辑项目归属、艺人 fan-out、完整参数传播和三模式前端对决回归测试；真实数据核对中 GUTS 为 4 首冠单 / 7 个冠军周，`you seem pretty sad for a girl so in love` 为 3 首冠单 / 5 个冠军周。
- 后端全量 1,410 项、前端 300 项测试、TypeScript 生产构建、Ruff/format、ESLint 与 1440/390 浏览器验收均通过；三种对决无横向溢出或控制台错误。

## 2026-07-28 — Billboard Year-End V3 积分

### 统计语义

- 歌曲、专辑、艺人的年榜主分数统一改为现有周积分之和，保留周积分内的排名、竞争强度与个体统治力，不再在年度层重复叠加持续性、peak 和冠军周奖励；相关成绩仍用于展示、荣誉和同分裁决。
- 年榜语义版本升级为 `year_end_v3`；AI 年报缓存键同步包含该版本，避免继续命中按 V2 积分生成的旧报告。

### 验证

- 年榜一致性探针新增 V3 积分复算，除在榜周数、peak、冠军周、Top 5/Top 10 和在榜播放外，也逐实体验证 `year_end_score = round(Σ weekly_score)`。
- 修复年榜初次加载时年份列表尚未返回便短暂显示“无数据”的状态闪烁；加载中改为年份骨架，请求失败只显示错误状态，只有成功返回空年份列表时才显示“无数据”。

## 2026-07-27 — Billboard Year-End 年榜口径修复

### 统计语义

- 修复年榜输出条数被错误复用为周榜入榜线的问题：年度积分、年度在榜周数、peak、#1/Top 5/Top 10 周数和在榜播放现在统一基于用户当前周榜 Top N 设置计算；年榜仍独立输出单曲 50、专辑 30、艺人 30。
- 年榜行同时返回 `annual_plays`（该年度全部有效播放）与 `chart_plays`（进入周榜入榜线的播放）；为避免重复，主表只展示后者并明确标为“在榜播放”，`annual_plays` 保留给 API 与 AI 年报证据消费者。
- 年榜 meta 新增语义版本、周榜与年榜各自的限制、实际播放观察期、首末榜单周、已观察/预期榜单周、内部缺口和完整年度状态；修复阶段年榜截止日期误用最后一个榜单周起始日的问题，年内或起始年份的荣誉改为阶段性标签。
- 年榜页在无 URL 覆盖时继承 Settings 的精选集偏好，并在同年切换合并级别或精选集口径时隐藏旧配置占位数据，避免短暂展示不一致结果。

### 消费者与验证

- AI 年报读取持久化 Billboard Top N、周边界和精选集设置，并消费新的完整年度播放与覆盖元数据；年度报告缓存合同升级为 `contract_v13`。
- 年榜 OpenAPI 响应改为显式的单曲、专辑、艺人与荣誉模型；新增 `scripts/billboard_year_end_consistency_probe.py`，逐年、逐 merge level 对照周榜复核全部年度指标。

## 2026-07-11 — 艺人语言事实、审核与真实统计

### 数据与审核

- 新增 artist-ID based 的语言来源、审核与 approved fact 数据层；语言与 genre 独立，legacy、LLM 和未审核 seed 只进入 suggested/review 流程。显式 reviewed seed 仅在证据、审核人和结论说明齐全，并通过同一 validator/state machine 时批准，不会自动猜测批准。
- 建立 canonical language registry、证据校验和审核状态机，支持批准、拒绝、证据不足、终态冲突保护与可追溯历史；`unknown`、`multilingual`、`instrumental` 均作为显式结果保留。
- 提供语言覆盖率、艺人状态/历史、审核写入和音乐搜索关联 API；统计使用 `tracks.artist_id` 主艺人归属并保持整数毫秒守恒，不使用协作艺人 fan-out。

### 前端与年度总结

- Settings 卡片 06 更新为“流派与语言数据健康”，在保留既有 genre 面板的同时新增语言覆盖率、Top unknown、艺人搜索、审核历史和证据审核 Dialog。
- 年度总结直接渲染后端动态 language buckets；流派和语言独立展示，不再从 genre 推断语种，并明确展示分类率、未知率与未归属时长。

### 验证与迁移

- OpenAPI 类型、operation/parameter audit、API smoke 和 Settings 非破坏性交互 smoke 已覆盖 5 个语言 API；生产 legacy 导入仅执行 `--dry-run`，不会写入现有数据库。

## 2026-07-07 — 迭代收口：测试修复 + Streamlit 移除 + 基础设施加固

### 测试修复（38 个）

- **visual_yearly_artifact_service (21→0)**：`call_report_writer_llm`→`run_report_agent` 适配 Agent 合成管道，软警告语义更新（success 恒 True），补齐 deterministic 管线 `run_report_agent` mock
- **ai_agent 系列 (8→0)**：`fake_llm_chat` 全局补 `**kwargs` 适配新增的 `thinking=True` 参数；tool_call_count 断言适配 temporal guard 自动注入
- **审计基线 (3→0)**：`api_smoke_probe.py` 登记 3 个新 artist-genres 路径；`openapi_parameter_boundary_audit.py` 登记 4 个新参数（review_id/report_mode/status/writer_pipeline）
- **contract 路由分发 (3→0)**：`yearly-story` 端点默认走 `visual_yearly_artifact` 缓存路径，测试补 `report_mode` 参数命中对应流水线
- **测试隔离 (3→0)**：`artist_genre_metadata_api`/`artist_genre_consumers` fixture 的 `DB_PATH` 用 monkeypatch 改但 teardown 不恢复，导致 `music_search_api` 全量跑时连到错误数据库；改为手动 save/restore

### 基础设施

- `wikipedia_cache` 表加入 SCHEMA（`backend/core/db.py`），确保所有环境（含 seed DB）自动建表，消除 `no such table: wikipedia_cache` 错误

### Streamlit 移除

- 删除 `app/` 目录（45 个 .py 文件，15,609 行），自 2026-05-30 冻结以来所有功能已迁移至 FastAPI + React
- `CLAUDE.md`/`README.md`/`AGENTS.md` 同步移除 Streamlit 相关引用和命令

### 验证

- BE unit 754/754 passed
- BE contract 265/265 passed
- FE 253/253 passed
- ruff lint + format 全过

## 2026-07-05 — Agent 多轮年报 + 事实准确性 + 思考模式

### 年报 Agent（report_agent.py）

- 用 Agent 多轮工具调用（Planner 规划 → 执行本地数据工具 + web_search → 直接写报告 JSON）替换单次 LLM 合成
- Web Search 工具（Wikipedia）注册到共享 Agent 工具注册表，年报和 Chat 均可使用
- Writer 只接收原始工具数据（ground truth），不接收 LLM 研究摘要，根除报告编造（girl in red / 周杰伦 / TikTok 等凭空艺人/事件）
- 删除 Editorial Agent 流水线（`editorial_agent/` 目录，~1,500 行），LLM 调用从 6 次减为 Agent 多轮（5-10 次）
- 所有质量门禁（critic/fact_validation/final_quality）改为软警告记录到 metadata，不再阻止报告展示
- 短报告自动重试（<300 字/<1 节 → 最多 3 次）
- 年报和 Chat 默认启用 DeepSeek 思考模式（`LLMProvider.chat(thinking=True)`）

### AI 洞察 UX 修复（12 项）

- 加载闪烁消除、多行输入、追问保留会话、幽灵消息修复、元数据徽章简化
- Markdown 渲染、滚动渐变、年报选择器统一、聊天高度优化、会话加载态、工具轨迹中文标签

### 文档

- 更新 AGENTS.md / CLAUDE.md / CHANGELOG 反映新架构

## 2026-07-05 — Agent 合成管道重构 + AI 洞察 UX 全面修复（旧）

### 重构

- **年度报告写作管道重构**：删除 6 阶段 `editorial_agent/` 流水线（~1,500 行），用 606 行 `report_writer.py` 替代。新方案用一次 LLM 合成调用（遵循 Agent Answer Philosophy 模式）生成报告正文，`build_report_writer_context()` 将研究数据转为富文本摘要（具体数字直接呈现给 LLM），`parse_report_sections()` 解析 JSON/Markdown 输出为 Section 列表。LLM 调用从 6 次减为 1 次，报告信息密度（具体数字/篇）提升 4-6 倍，抽象废话消除。
- `writer_pipeline` 新增 `agent_synthesis_v2` 并设为默认值，`editorial_agent_v1` 映射到新路径保持兼容。
- 保留全部确定性组件作为安全网：`visual_chart_data.py`、`visual_brief.py`、`visual_yearly_critic.py`、`yearly_validator.py`、`final_artifact_quality.py`、`_compose_sections()` 确定性 fallback。
- 删除 9 个 editorial_agent 相关测试文件，重写核心测试覆盖 agent_synthesis_v2 和 LLM 失败回退路径。

### AI 洞察 UX 修复（12 项）

- 报告面板：页面加载/切换类型时不再闪烁"暂无数据"，改为骨架屏过渡
- 聊天输入：`input` → `textarea` 支持多行，Enter 发送、Shift+Enter 换行，自适应高度
- 会话管理：追问从报告卡片跳转时保留当前对话不销毁；会话创建失败时消息不显示
- 元数据徽章：隐藏内部流水线术语（Agent 合成/Editorial Agent/事实核对/口味评分），仅保留"报告质量未通过校验"和"基础模式生成"两个异常状态徽章
- 报告内容：YearlySection prose 通过 `AiMarkdown` 正确渲染粗体/斜体/列表；底部添加渐变遮罩暗示可滚动
- 视觉一致性：年报年份选择器改为按钮组与周报/月报统一；EmptyState/ErrorState 使用不同图标区分
- 聊天体验：桌面端最大高度 460→640px；切换历史会话时显示加载动画；工具轨迹显示中文标签（`analysis_stats`→「播放统计」等 14 个）
- 思考模式：添加 tooltip 说明功能

### 验证

- 前端 253/253 通过，后端 unit 708/711（3 个预存失败），contract 258/264（6 个预存失败）
- 真实生成验收（2025 完整年份 + 2026 部分年份）：Critic/ Fact/ Quality 三门禁全过，writer_status=accepted

## 2026-07-05 — AI 年报 Editorial Agent 写作流水线（已废弃）

### 新增

- 年度叙事默认 `visual_yearly_artifact` + `writer_pipeline=editorial_agent_v1`：新增 `backend/domains/ai_reports/editorial_agent/`，按 Research Brief、Storyline Planner、LLM writer、LLM editor、Claim Checker、Taste Rubric 与 pipeline orchestrator 生成长文。
- 年报 artifact metadata 记录 `writer_pipeline_version`、`writer_pipeline_status`、`claim_check_passed`、`editorial_review_passed`、`taste_score`、`research_brief_version` 与文章长度；前端报告卡片展示 Editorial Agent、事实核对、口味评分和编辑审稿状态。
- AI task 报告请求支持 `writer_pipeline`，年度图文报告缓存 key 纳入 writer pipeline，避免 deterministic visual composer 或旧 Markdown/agentic 缓存挡住新结果。
- `scripts/probe_visual_yearly_report_artifact.py` 支持 `--writer-pipeline editorial_agent_v1`，并校验 writer metadata、claim check、taste score、critic、fact validation、图表观察、golden terms 和 forbidden terms。

### 修复与质量

- artifact 组装层补充图表观察解释、必要实体事实、核心事实去重、partial-year 文案修正和故事义务兜底，避免年度报告退化为播放分析页面数据复述。
- 修复后处理把“表明年度”误替换成“表之后度”的词缝 bug；visual critic、HTTP probe 与单测都把“之后度”列为硬失败。
- 前端年度叙事刷新默认携带 `writer_pipeline=editorial_agent_v1`，任务进度增加研究简报、故事规划、写作、编辑、事实核对和口味评分阶段。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_yearly_editorial_agent_models.py backend/tests/unit/test_yearly_research_brief.py backend/tests/unit/test_yearly_storyline_planner.py backend/tests/unit/test_yearly_writer_editor.py backend/tests/unit/test_yearly_claim_checker.py backend/tests/unit/test_yearly_taste_rubric.py backend/tests/unit/test_yearly_editorial_agent_pipeline.py backend/tests/contract/test_yearly_editorial_agent_contract.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_visual_yearly_report_contract.py -q`：77 passed
- `.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_yearly_critic.py -q`：24 passed
- `cd frontend && npm test -- src/tests/ai-task-components.test.tsx src/tests/visual-yearly-report.test.tsx --run`：12 passed
- `cd frontend && npm run build`：PASS
- `scripts/probe_visual_yearly_report_artifact.py --mode changed --writer-pipeline editorial_agent_v1`：2025/2026 均 PASS，均为 `writer_pipeline_status=accepted`、`claim_check_passed=true`、`critic_passed=true`、`fact_validation_passed=true`。
- Playwright 模拟用户路径 `/ai-insights` → `年度叙事` → `刷新报告`：页面显示 `Editorial Agent`、`事实核对通过`、`口味评分 35` 与完整图文年报 artifact，未出现事实核对失败徽章、`之后度` 或 `fallback_visual_composer`。

## 2026-07-04 — AI Visual Yearly Report Artifact

### 新增

- 年度叙事默认 `report_mode=visual_yearly_artifact`，返回结构化图文年报 artifact：标题/副标题、故事章节、重点 insight cards、chart specs、真实 chart data、metadata、visual critic 与 fact validation。
- 新增 `backend/domains/ai_reports/visual_artifact_models.py`、`narrative_brief.py`、`visual_brief.py`、`visual_chart_data.py`、`visual_yearly_artifact_service.py`、`visual_yearly_critic.py` 与 `visual_yearly_prompts.py`，把年度报告拆为叙事底稿、视觉规划、只读图表数据、artifact 组合和风格/事实门禁。
- 前端新增 `features/ai-insights/yearly-artifact/` 渲染器，支持年度 hero、章节、重点卡片和 7 类图表：活跃日热力、艺人月度趋势、常听/长留专辑对照、高光日时间切片、流派/语种占比、新发现时间线、播放与个人榜单矩阵。
- 新增 `scripts/probe_visual_yearly_report_artifact.py`，通过真实 AI task API 触发年度图文 artifact，校验 report mode、contract version、章节数、图表数据、insight cards、禁用词、critic、fact validation 和 2025/2026 golden signals。

### 修复与兼容

- 年度报告缓存 key 区分 `visual_yearly_artifact` / `visual_yearly_v1`，避免旧 Markdown 或 agentic longform 年报缓存挡住图文 artifact。
- `agentic_longform` 与 `basic_summary` 保留为显式兼容/回退模式；年度 task 与前端年度叙事按钮默认请求 `visual_yearly_artifact`。
- 前端图表适配真实后端 schema：`artist_monthly_trend.entities/months`、`genre_language_mix.share`、`highlight_day_timeline.top_tracks` 对象数组、`discovery_timeline.new_artists/first_date` 均可正确渲染，避免空图、`[object Object]` 和重复 key warning。
- 年度图文报告新增 `story_insight_builder.py` 作为正文前的结构化洞察层，统一判断专辑播放/个人 Billboard 是 `aligned` 还是 `divergent`、第二艺人线索是否有语种证据、高光日是否为多曲目密集日、新发现应写成强支线还是入口。
- 重写年度图文报告章节正文，移除跨章节重复的“图表负责回答/正文负责回答”模板句，避免把内部写作指令、confidence 标签或 `interpretation_guidance` 泄漏给用户。
- 同专辑场景会写成“播放热度与个人 Billboard 长留指向同一个重心”，不再生成 `The Life of a Showgirl 和 The Life of a Showgirl 说明了两种不同的喜欢` 这类假对比；相关图表标题与 interpretation 也按 aligned/divergent 动态输出。
- 第二艺人线索不再把全局 `mandopop/c-pop` 流派标签套到 Olivia Rodrigo 等非华语艺人身上；visual critic 与真实 API probe 会拦截 Olivia Rodrigo 被无证据写成“华语/现场感/回望”的回答。
- 年度图文报告新增确定性 Editorial Plan，给核心事实分配唯一章节主场，记录 `section_roles` / `fact_count` / `language_budget`，并将 critic/probe 从“原样复述图表 observation”升级为“解释性使用图表证据”；这减少了模板词、重复事实和播放分析页面复述感，同时继续保留个人 Billboard 与本地播放数据的事实边界。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_editorial_plan.py backend/tests/unit/test_narrative_quality.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_visual_yearly_artifact_service.py -q`：32 passed
- `cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx`：5 passed
- `scripts/probe_visual_yearly_report_artifact.py --mode changed --year 2026`：PASS，2025/2026 均生成 `yearly_editorial_v1` metadata，7 个章节、7 个图表数据块、无 chart observation 缺失。
- `scripts/probe_visual_yearly_report_artifact.py --mode full --year 2026`：PASS，2022-2026 全部通过；所有年份均返回 `editorial_plan_version=yearly_editorial_v1`，`fact_count >= 6`，`section_roles` 非空。
- `.venv/bin/pytest backend/tests/unit/test_visual_yearly_artifact_models.py backend/tests/unit/test_narrative_brief.py backend/tests/unit/test_visual_brief.py backend/tests/unit/test_visual_chart_data.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_visual_yearly_report_contract.py -q`：36 passed
- `cd frontend && npm test -- --run src/tests/visual-yearly-report.test.tsx src/tests/ai-task-components.test.tsx`：7 passed
- `cd frontend && npm run build`：PASS
- `.venv/bin/ruff check backend/domains/ai_reports backend/services/ai_task_service.py backend/services/ai_insights_service.py backend/api/ai_insights.py backend/models/ai_tasks.py scripts/probe_visual_yearly_report_artifact.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_chart_data.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_visual_yearly_report_contract.py`：PASS
- `scripts/probe_visual_yearly_report_artifact.py --year 2025` 与 `--year 2026`：均 PASS；两个年份均生成 7 个章节、7 个图表数据块、4 张 insight cards，2026 报告明确 `截至 2026-06-23`。
- `.venv/bin/pytest backend/tests/unit/test_story_insight_builder.py backend/tests/unit/test_visual_yearly_critic.py backend/tests/unit/test_visual_yearly_artifact_service.py backend/tests/unit/test_visual_chart_data.py backend/tests/unit/test_visual_brief.py -q`：22 passed
- Chrome CDP 模拟用户路径 `/ai-insights` → `年度叙事`：desktop 1440px 与 mobile 390px 均渲染图文 artifact，8 个 figure、0 横向溢出、0 console warning/error，未出现空图 fallback 或 `[object Object]`。
- 应用内浏览器模拟用户刷新 2026 年度叙事：页面显示 `专辑热度与长留关系` 与 `播放量和持续在榜指向同一张专辑`，不再出现旧图表短句、同专辑假对比或内部提示词泄漏；390px 移动视口 `scrollWidth=390/clientWidth=390`。

## 2026-07-03 — Agentic Longform 年度报告落地

### 新增

- 年度报告默认接入 `agentic_longform` Report Agent：只读查询年度概览、TOP 实体、同期对比、个人 Billboard 年榜、Billboard 诊断、流派、发现回归和高光日，再形成 evidence ledger、insight synthesis、dynamic outline 与长文草稿。
- 新增 `backend/domains/ai_reports/agentic_tools.py`、`agentic_prompts.py`、`agentic_models.py` 与 `editorial_critic.py`，把报告生成拆为只读工具、提示词、结构化元数据和编辑质量门禁。
- 新增 `backend/services/yearly_report_agent_service.py` 编排年度 Report Agent；task result 返回 `metadata`、`critic`、`insight_synthesis`、`dynamic_outline`、`evidence_ledger`，并把 evidence ledger 持久化为 `ai_tool_calls`。
- 前端 AI 报告页展示 agentic 长文、critic、回退和字数元信息；AI task progress 将 `researching`、`synthesizing_insights`、`outlining`、`drafting`、`critic_review` 等阶段显示为中文。
- 新增 `scripts/probe_agentic_yearly_report.py`，通过真实 task API 创建年度报告、轮询结果并校验 metadata、critic、长度、工具轨迹和个人 Billboard 证据。
- Agentic 年报复用 `yearly_validator` 作为事实安全网，并在 task result 中保留 `fact_validation`；若 LLM 草稿/修订仍不合格，会退到同一 evidence context 生成的结构化长文修复，最后才标记 `basic_summary` 回退。

### 兼容与回退

- `/api/ai/tasks/report` 年度任务默认 `report_mode=agentic_longform`；显式 `report_mode=basic_summary` 时保留旧 `generate_yearly_story` 路径。
- `/api/ai-insights/yearly-story?force=true&report_mode=agentic_longform` 可直接触发新引擎并返回 metadata；非 force 兼容旧缓存查询行为，避免打开页面自动触发长文 LLM。
- 若编辑 critic 未通过，结果会标记 `fallback_level=basic_summary`，使用确定性基础摘要兜底，不把基础摘要伪装成正式长文。
- `report_period_context` 工具在未显式传入 `latest_play_date` 时会读取真实年度数据契约中的 `reporting_period.end_date`，保证 evidence ledger、最终报告和 metadata 的截止日期一致。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py backend/tests/unit/test_agentic_yearly_report_tools.py backend/tests/unit/test_agentic_yearly_report_critic.py -q`
- `.venv/bin/pytest backend/tests/unit/test_agentic_yearly_report_service.py backend/tests/unit/test_agentic_yearly_report_tools.py backend/tests/unit/test_agentic_yearly_report_critic.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_agentic_yearly_report_contract.py backend/tests/contract/test_ai_insights_contract.py backend/tests/contract/test_ai_task_api.py -q`：55 passed
- `.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py::test_yearly_agent_task_emits_research_outline_and_critic_events backend/tests/unit/test_ai_report_tasks.py::test_run_report_generation_task_dispatches_report_type backend/tests/unit/test_ai_report_tasks.py::test_basic_summary_yearly_report_mode_dispatches_legacy_generator -q`
- `.venv/bin/pytest backend/tests/contract/test_agentic_yearly_report_contract.py backend/tests/contract/test_ai_insights_contract.py::test_ai_insights_report_endpoints_forward_play_filters backend/tests/contract/test_ai_task_api.py::test_report_task_request_preserves_filter_parameters -q`
- `.venv/bin/python -m py_compile scripts/probe_agentic_yearly_report.py`
- `scripts/probe_agentic_yearly_report.py --year 2026`：PASS，`report_mode=agentic_longform`，`contract_version=agentic_yearly_v14`，`fallback_level=null`，9 个只读工具调用，`critic.ok=true`，`fact_validation.ok=true`，报告长度 1,846 字符。
- 应用内浏览器手动验收 `/ai-insights`：切换“年度叙事”并点击“刷新报告”，页面显示工具查询、洞见综合、动态大纲、长文撰写、编辑审稿与事实口径检查进度，最终卡片显示 `Agentic 长文`、`已通过编辑审稿`、`1,846 字`。

## 2026-07-03 — AI 年度叙事编辑质量与个人年榜证据

### 修复与增强

- 年度叙事 payload 在既有 `reporting_period` / TOP 艺人歌曲 / 同期对比基础上新增 `top_albums`、`billboard_year_end` 和 `editorial_brief`，让 LLM 能同时看到专辑偏好、个人 Billboard Year-End 稳定性证据和一条明确写作主线。
- 个人 Billboard Year-End 证据以只读、best-effort 方式接入年度报告，包含单曲/专辑/艺人年榜排名、Year-End Score、峰值、在榜周数、冠军周数和 chart plays，并明确这是本地个人榜而非外部官方 Billboard。
- 年度报告 prompt 新增编辑义务：必须使用 TOP 专辑与个人年榜证据、先读 `editorial_brief.thesis`、同一组 same-period YTD 对比只写一次，并避免“有意识地”“主动选择”等无数据支撑的主观意图推断。
- 年度报告 validator 扩展为编辑质量门禁：拦截缺 TOP 专辑、缺个人年榜证据、个人 Billboard 被误写成外部官方榜单、重复同期对比、无依据意图词、歌词/性别/别名外推、完整年度/阶段性报告标签混用、partial-year 中“年度专辑/年度单曲/年度冠军”等完整年度实体标签、错误时间段表述、过长报告和模糊“前者/后者”引用；年度报告缓存 key 升级到 `contract_v12`，避免旧报告绕过新合同。
- 年度报告生成改为低温首稿 + 多轮降温修订；若 LLM 多轮仍不满足 validator，则使用确定性 fallback 从同一份结构化 DATA 生成简洁可用报告，fallback 会按完整年/阶段性年份选择标题与后续观察口径，并在专辑、新艺人或部分个人年榜证据缺失时干净降级。
- `scripts/probe_ai_yearly_report_quality.py` 扩展到专辑/个人年榜/editorial brief；新增 `scripts/probe_ai_yearly_report_text_quality.py` 通过 HTTP API 获取年度报告并复用 validator 检查真实返回文本。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py backend/tests/unit/test_ai_insights_service.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_ai_insights_contract.py -q`：59 passed
- `.venv/bin/python scripts/probe_ai_yearly_report_quality.py --year 2026 --json-output /tmp/spotify_ai_yearly_2026_editorial_quality.json`：PASS
- `.venv/bin/python scripts/probe_ai_yearly_report_text_quality.py --year 2026 --force --json-output /tmp/spotify_ai_yearly_text_force.json`：PASS，返回 1183 字符、`issues=[]`
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`：12/12 PASS
- `node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --scenario ai-insights-tabs`：PASS，0 console error/warning，0px 横向溢出
- 真实浏览器 `/ai-insights` → 年度叙事 → `刷新报告`：页面展示 `AI 任务进度`、`calling_llm 70%`、`done 100%`，最终报告包含 `2026 年中音乐报告（截至 2026-06-23）`、TOP 专辑、个人 Billboard 年榜、人格/流派和高光日；浏览器 console error/warn 为 0。

## 2026-07-03 — AI 年度叙事数据契约与质量校验

### 修复与增强

- 年度叙事新增 `ai_reports/yearly_contract.py`，在 LLM 前构造稳定报告数据契约：`reporting_period`、年中/全年标记、同周期 YTD 对比、TOP 艺人与歌曲名称、人格维度、流派 caveat、高光解释和写作约束。
- 年度报告 prompt 改为可信个人音乐年度编辑，要求 partial year 明确写“截至数据截止日”、只使用同期对比、保留 TOP 名称与人格分数对应关系，并禁止编造天气、失眠、告别、人生转折等 DATA 外叙事。
- 新增年度报告 validator：对未完整年份缺少截止日、误用全年/来年表述、错误引用去年全年对比、TOP 名称缺失、人格分数错配、场景臆造、“其他流派”遗漏、流派 caveat 缺失和低置信高光夸大做拦截；首次生成不合格时带反馈重试一次，仍不合格则返回 502 且不写缓存。
- 年度报告缓存 key 引入 `contract_v2`，避免旧缓存继续展示已知错误的 2026 年度叙事。
- 新增 `scripts/probe_ai_yearly_report_quality.py`，用本地只读数据验证年度报告 payload 的截止日、partial year 标记、TOP 名称、同期对比和完整上一年变更禁用状态。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_insights_yearly_quality.py backend/tests/unit/test_ai_insights_service.py backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_ai_insights_contract.py -q`：40 passed
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`：12/12 PASS
- `.venv/bin/python scripts/probe_ai_yearly_report_quality.py --year 2026 --json-output /tmp/spotify_ai_yearly_2026_quality.json`：PASS
- 真实 API `/api/ai-insights/yearly-story?year=2026&force=false`：返回新 `contract_v2` 报告，标题含 `截至 2026-06-23`，使用同期 YTD 对比，保留 Taylor Swift / `Opalite` / `其他流派`，不再出现旧的 `少了 55%`、`来年寄语` 或编造雨夜叙事。
- 真实浏览器 `/ai-insights` → `年度叙事`：页面展示新报告，命中截止日、TOP 名称和流派 caveat，未命中旧错误文案；DOM 文本探针确认不含 `55%`、`来年寄语` 或雨夜叙事。

## 2026-07-03 — AI Agent 安全短路与矩阵复测

### 修复与增强

- 安全边界问题在 planner 前确定性短路，覆盖任意 SQL、API Key 外部网站、官方 Billboard/全球市场成绩和写操作请求，避免模型先调用只读工具再拒绝。
- `answer_obligations` 新增证据不足限制说明，最终回答 retry 后会重新运行 validation/critic，并在必要时追加数据截止、本地个人 Billboard 或证据限制兜底句。
- 校准 answer critic：允许“长期/近期/播放次数/个人 Billboard”等维度限定下的强弱表述，同时继续拦截全局单边结论；允许“无法给出确定性结论”等否定语境和“补充标签后才能确定”的条件句。
- temporal guard 校正后的 custom range 会投影到 EvidenceRecipe/AnalyticalBrief 的 `required_context`，避免工具已按正确日期执行但 evidence review 仍按 lifetime 判定。
- Project Context Prompt 新增曲风/语种边界：没有结构化 genre/language 标签时，只能把播放排行或艺人名称视为代理线索并保守说明限制。
- `scripts/evaluate_ai_question_matrix.py` 新增 live 模式：`p0`、`safety`、`multiturn`、`changed`、`full`，可真实创建 AI chat task、轮询结果、读取工具轨迹并执行质量门禁；`full` 会把 `AI-MULTI-*` 用例交给多轮 runner。
- WebKit/Safari-family 音乐详情页移动端封面尺寸改为稳定 120x120，cross-browser smoke 的横向溢出失败会输出候选撑宽元素。

### 验证

- `python scripts/evaluate_ai_question_matrix.py --mode p0 --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00`：12/12 Pass
- `python scripts/evaluate_ai_question_matrix.py --mode safety --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00`：8/8 Pass
- `python scripts/evaluate_ai_question_matrix.py --mode multiturn --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00`：3/3 Pass
- `python scripts/evaluate_ai_question_matrix.py --mode changed --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00`：11/11 Pass
- `python scripts/evaluate_ai_question_matrix.py --mode full --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00`：42 cases，41 Pass / 1 Partial / 0 Fail，质量门禁 PASS；唯一 Partial 是无结构化语种标签时模型凭艺人常识估算华语比例并给出偏强结论，后续应补 genre/language 证据工具或更严格降级。
- AI agent unit + task contract 定向测试：129 passed
- AI agent temporal recipe/critic 定向测试：62 passed
- `python scripts/evaluate_ai_question_matrix.py`：141 questions / P0 12 / golden 12 / PASS
- `node scripts/frontend_cross_browser_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --browser webkit --scenario route-markers --viewport mobile --include-detail-routes --max-scroll-overflow 0`：PASS
- `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://localhost:5173`：3/3 Pass
- `node scripts/frontend_long_list_smoke.mjs --base-url http://localhost:5173`：7/7 Pass
- `cd frontend && npm test -- --run`：229 passed
- `cd frontend && npm run build`：Pass，保留既有 Vite large chunk warning

## 2026-07-03 — 音乐查找榜单摘要与快速搜索交互

### 修复与增强

- `/api/music/search` 新增 `include_chart=true`，返回与音乐详情页同口径的播放次数和个人 Billboard 摘要，覆盖歌曲、专辑和艺人。
- 完整搜索页与 Masthead 快速搜索统一显示播放次数、`PK #`、在榜周数和走势排名；按产品取舍不展示冠军周数和 peak weeks。
- 快速搜索加载态压缩为单行状态提示；结果默认不高亮第一条，只有鼠标 hover/focus 或键盘方向键后才进入高亮态，Enter 打开当前高亮结果。

### 验证

- `pytest backend/tests/unit/test_music_search_service.py backend/tests/contract/test_music_search_api.py backend/tests/contract/test_music_search_counting_consistency.py -q`：通过
- `cd frontend && npm test -- --run src/tests/music-search-components.test.tsx src/tests/music-search-flow.test.tsx src/tests/query-hooks.test.tsx`：29 passed
- `cd frontend && npm run build`：Pass，保留既有 Vite large chunk warning
- 浏览器实测 Masthead 搜索 `Anti`：初始 `activeCount=0`，按一次 `ArrowDown` 后 `activeCount=1`，console error/warn 为 0

## 2026-07-03 — 音乐查找入口与本地实体搜索

### 新增

- 新增只读 `/api/music/search`，复用本地实体解析能力搜索歌曲、专辑、艺人，并返回既有音乐详情页链接。
- Masthead 右侧新增全局音乐搜索图标，支持快速输入、分组结果和“查看全部结果”跳转。
- 新增 `/music/search` 完整查找页，URL `q` / `kind` 参数可分享，继续使用 TanStack Query + `queryKeys.music.search`，结果列表会显示本地 `/covers` 封面并在图片失败时回退占位。
- route/interaction smoke 覆盖 `/music/search` 和 Masthead 快速查找；播放排行页不增加重复搜索入口。

### 验证

- `pytest backend/tests/unit/test_music_search_service.py backend/tests/contract/test_music_search_api.py -v`：9 passed
- `cd frontend && npm test -- --run src/tests/music-search-components.test.tsx src/tests/music-search-flow.test.tsx src/tests/masthead-navigation.test.tsx src/tests/masthead-route-context.test.ts src/tests/query-hooks.test.tsx src/tests/phase5-architecture.test.ts`：123 passed
- `cd frontend && npm test -- --run`：229 passed
- `cd frontend && npm run build`
- `.venv/bin/python scripts/api_smoke_probe.py`：101/101 passed；OpenAPI GET coverage 0 unaccounted
- `.venv/bin/python scripts/api_boundary_probe.py`：95/95 passed
- `.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit_music_search.json`：144 operations / 0 unaccounted
- `.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit_music_search.json`：64 obligations / 0 unaccounted
- `node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --routes /music/search --viewport both --max-scroll-overflow 0 --fail-on-console-warning`：desktop/mobile PASS，0 console warning/error，0 横向溢出
- `node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --scenario music-search-quick-open --wait-ms 15000`：PASS，0 console/page error，0 横向溢出
- `pytest -m unit -q`：543 passed；`pytest -m contract -q`：229 passed；`npm test`：229 passed
- CDP 页面探针 `/music/search?q=the`：15 个音乐结果链接、15 张封面图片全部加载完成，样例 `/covers/albums/1894.jpg` 为 640x640

## 2026-07-03 — AI Agent 相对时间 grounding

### 新增

- **提问时间上下文**：Chat Agent 请求新增可选 `question_time` 与 `timezone`，后端生成 `temporal_context` 并把 `today`、数据起止日、`latest_play_date` 注入 planner 与最终回答。
- **相对时间护栏**：新增 `domains/ai_agent/temporal_context.py`，对“去年/今年/上个月/最近/夏天”等高置信表达做轻量 guard；当 planner 把“去年夏天”错规划到 2024 或只规划全年/全部时间工具时，会在工具执行前校正或补充基于提问时间的 2025 夏天 custom range，后续补查工具也会沿用同一时间范围。
- **可观察性**：AI task events/result 保留 `temporal_guard`，前端问答消息显示“时间解释/已校正”摘要，便于用户确认 Agent 使用的时间窗口。

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_agent_temporal_context.py backend/tests/unit/test_ai_agent_question_intent.py backend/tests/contract/test_ai_agent_task_contract.py -q`：30 passed
- `.venv/bin/ruff check backend/domains/ai_agent/temporal_context.py backend/services/ai_agent_service.py backend/models/ai_tasks.py backend/api/ai_tasks.py`
- `cd frontend && npm test -- --run`：222 passed
- `cd frontend && npm run build`
- 真实页面验证 `/ai-insights` 问答：“去年夏天我最常听什么类型的音乐？”显示 `去年夏天 → 2025-06-01 至 2025-08-31`，工具调用均为 `2025-06-01..2025-08-31`，console error/warning 为 0。

## 2026-07-03 — AI Agent Harness 矩阵修复

### 修复与增强

- 拆分 AI 最终回答阶段的 LLM 未配置与 provider 调用失败，并对 provider 临时失败增加一次重试和任务事件记录
- `latest_play_date` 优先使用本地 `ts_date`，并为“去年冬天”等跨年季节生成明确显示标签
- 新增 `answer_obligations`，强制最终回答覆盖数据截止日、本地个人 Billboard 边界和只读安全拒绝等硬约束
- 新增账号收藏、账号总览、搜索历史、社区帖子搜索、社区热议趋势等只读 AI 工具，并接入 QuestionFrame、EvidenceRecipe、Project Context 和 golden harness
- Planner 可用工具描述改为 compact schema，避免工具增长后 payload 截断成无效 JSON
- 修复 chart/long-list smoke 的旧文案与冷态等待误报
- 新增 AI 问题矩阵静态检查脚本 `scripts/evaluate_ai_question_matrix.py`

### 验证

- AI agent unit + task contract：190 passed
- AI golden harness：12/12 passed
- AI question matrix static check：141 questions / P0 12 / PASS
- Frontend chart interaction smoke：3/3 passed
- Frontend long-list smoke：7/7 passed
- in-app Browser 真实问答：收藏问题调用账号工具；删除播放记录请求被只读边界拒绝

详见 [`docs/verification/2026-07-03-ai-question-matrix-test-report.md`](verification/2026-07-03-ai-question-matrix-test-report.md)。

---

## 2026-06-29 — AI Agent Project Context Layer 与回答渲染

### 新增

- **Project Context Prompt**：AI 问答新增稳定项目语境层，集中描述 SpotifyStats 的个人音乐数据定位、本地个人 Billboard 边界、偏好分析口径和默认回答哲学。
- **Prompt 组合与版本化**：Planner 与最终回答 prompt 通过 `project_context.py` 组合 Project Context、Tool Playbook、Answer Philosophy 和 Safety Boundary，并在最终 payload / task result 中记录 `project_context_version`。
- **Golden answer style 护栏**：Golden harness 可检查代表问题的 `expected_answer_style`，防止简单问题再次退化为长报告或复杂比较被压成单一结论。
- **AI Markdown 渲染**：AI 报告和问答统一通过 `AiMarkdown` 渲染 LLM 返回的 Markdown，启用 GFM 表格并用 `rehype-sanitize` 保持外部文本安全边界。
- **对话时间显示修正**：前端将 SQLite 风格后端时间戳按 UTC 解析，避免对话历史“刚刚 / N 分钟前”因本地时区偏移显示错误。

### 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_project_context.py backend/tests/unit/test_ai_agent_question_frame.py backend/tests/unit/test_ai_agent_evidence_recipes.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_analytical_brief.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py backend/tests/unit/test_ai_agent_tools.py backend/tests/unit/test_ai_agent_question_intent.py backend/tests/unit/test_ai_agent_evidence.py backend/tests/unit/test_ai_agent_evidence_cards.py backend/tests/contract/test_ai_agent_task_contract.py -q`：151 passed
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`：9/9 PASS
- `.venv/bin/ruff check backend/domains/ai_agent backend/services/ai_agent_service.py`
- `cd frontend && npm test -- ai-markdown-rendering.test.tsx ai-insights-components.test.tsx`
- `cd frontend && npm run build`
- 真实浏览器验证：`/ai-insights` 新建对话、打开思考模式并询问“我最喜欢的Ariana Grande的专辑和歌曲是什么”，页面展示 task 进度、证据卡片和工具轨迹，回答短答命中 `eternal sunshine` / `Santa Tell Me`，task result 含 `project_context_version=spotify-stats-project-context-v1` 且 `validation_issues=[]`。

## 2026-06-29 — AI Agent Universal Analytical Harness

### 新增

- **通用分析中间层**：AI 问答新增 QuestionFrame、EvidenceRecipe、EvidenceSufficiency 与 AnalyticalBrief，把用户问题先归类为问题家族，再按证据配方补查只读工具，最后用结构化分析底稿约束回答。
- **回答契约护栏**：Answer critic 会检查 forbidden claims、must_explain、个人 Billboard 边界、冲突口径和证据不足场景；当回答过度单边、把本地个人榜单说成官方/市场成绩，或在证据不足时给确定性结论，会触发一次重试。
- **Golden harness 扩展**：golden fixture 扩展到 8 条问题，覆盖偏好比较、近期趋势、年度排行、深夜歌曲、本命偏好、跨年变化、近期下降解释和播放次数/喜好边界，并校验 QuestionFrame、EvidenceRecipe、required tool patterns 与 critic 行为。
- **真实任务回归**：AI chat task contract 覆盖 evidence_sufficiency=false 时的真实 retry 路径，确认不是只在 unit critic 层通过。

### 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider backend/tests/unit/test_ai_agent_question_frame.py backend/tests/unit/test_ai_agent_evidence_recipes.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_analytical_brief.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_golden_questions.py backend/tests/unit/test_ai_agent_tools.py backend/tests/contract/test_ai_agent_task_contract.py -q`：105 passed
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`：8/8 PASS
- `cd frontend && npm test -- ai-evidence-cards.test.tsx` 与 `cd frontend && npm run build`

## 2026-06-29 — AI Agent Harness Quality Roadmap

### 新增

- **Evidence-driven Agent harness**：新增 evidence cards、确定性问题意图解析、实体解析、通用实体比较、coverage follow-up、answer critic 与 golden-question eval harness
- **问答证据可视化**：AI 问答完成后在回答旁展示结构化证据卡片，并保留原始工具轨迹
- **深夜歌曲只读工具**：`listening_hours` 增加 `late_night_tracks` view，可回答“深夜最爱听什么歌”这类时段歌曲问题
- **Golden fixtures**：覆盖 GUTS vs The Life of a Showgirl、Olivia Rodrigo 近期趋势、2023 Top artist、深夜歌曲问题，并校验 required tool calls 与 forbidden metrics

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_agent_* backend/tests/unit/test_play_service_dashboard.py backend/tests/contract/test_ai_agent_task_contract.py -q`
- `.venv/bin/pytest -m unit -q`：432 passed
- `.venv/bin/pytest -m contract -q`：223 passed
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`
- `cd frontend && npm test -- --run`：217 passed
- `cd frontend && npm run build`
- OpenAPI operation/parameter audit：143 operations / 61 obligations，0 unaccounted
- `.venv/bin/python scripts/api_smoke_probe.py`：100/100 passed；OpenAPI GET coverage 0 unaccounted
- `.venv/bin/python scripts/api_boundary_probe.py`：91/91 passed
- `node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --wait-ms 15000`：6/6 passed，0 console/page error，0 横向溢出
- `node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport desktop --include-detail-routes`：19 routes / 928 controls / 0 violation
- 真实浏览器验证：`/ai-insights` 提交“我深夜最爱听什么歌？请用本地数据回答，并展示依据。”，生成中显示阶段进度，完成后显示 conclusion、thinking sections、evidence cards 与 tool trace；1280px 桌面无横向溢出、无 console warning/error；此前 390px 移动端问答证据卡验证无横向溢出

## 2026-06-29 — AI 可观察任务与只读 Agent V2

### 新增

- **AI Task Orchestrator**：新增 AI task runs/events/tool calls 持久化模型，报告、AI 问答、艺人 career enrichment、专辑 era enrichment 统一展示阶段进度
- **AI 报告 cache-first**：周报/月报/年度叙事不再打开页面自动调用 LLM；无缓存时显示手动生成，生成过程中展示准备数据、调用 LLM、保存缓存等事件
- **只读 Agent 问答**：AI 问答改为 LLM 规划后端 allowlist read-only 工具，再基于工具结果生成回答；支持思考模式、工具轨迹、coverage 自检和矛盾回答重试
- **证据压缩与提示词护栏**：最终回答只接收 compact evidence + coverage，prompt 明确个人 Billboard 不是外部官方 Billboard，并要求比较问题说明统计窗口和公平性限制

### 验证

- `pytest -m unit -q`：385 passed
- `pytest -m contract -q`：222 passed
- `cd frontend && npm test -- --run`：214 passed
- `cd frontend && npm run build`
- `ruff check backend/`
- OpenAPI operation/parameter audit、API smoke/boundary、AI Insights interaction smoke、`/ai-insights` control inventory smoke 通过
- 真实浏览器验证：在 `/ai-insights` 打开思考模式询问 GUTS vs The Life of a Showgirl，工具轨迹正确查询两张专辑的 entity stats 与个人 Billboard detail，回答不再误报 Showgirl 数据缺失

---

## 2026-06-27 — 榜单社区口径同步

### 修复

- **社区榜单口径跟随设置**：Community feed、trending 和 post detail 改用 `BillboardFilters` + `MergeConfig`，向帖子生成链路转发 Top N、周起点、年份范围、动态阈值、最大连续播放合并间隔、`merge_level` 和 `include_compilations`
- **前端社区缓存分流**：社区列表、账号页、帖子详情和趋势侧栏通过 `useCommunityChartParams()` 带入当前设置口径，帖子详情 query key 纳入 filters，避免设置变化后继续显示旧口径社区动态
- **社区图片尺寸微调**：`PostCard` 单图从 208px 收紧到 160px，多图网格最大宽度从 424px 收紧到 320px，让榜单社区时间线更紧凑

### 验证

- `pytest backend/tests/unit/test_community_api_filter_propagation.py backend/tests/unit/test_feed_generator.py -q`
- `cd frontend && npm test -- community-components.test.tsx`
- `cd frontend && npm run build`
- `node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --routes /community --viewport mobile --max-scroll-overflow 0 --fail-on-console-warning`

---

## 2026-06-24 — fix/bugfixes-and-polish 收口修复

### 修复

- **PK Wks 算法重写**：`running_peak_wks` 从"日历周差（含非达峰周）"改为"累计达峰周数（同 running_peak 级别累加，新峰值重置，非达峰周 forward-fill）"，只基于实时 `cummin()` 不预知未来
- **Album Project artist_id 容错**：`load_album_project_membership` 改用 `LEFT JOIN artists`，`_bootstrap_from_release_groups` 新增 artist_id≤0 时从 albums 表回退查找，修复 Red/Fearless (Taylor's Version) 因 artist_id=0 从统计中消失
- **Album Project 本地曲目回退**：`_bootstrap_standalone_album_projects` 当 Spotify 元数据缺失时使用本地曲目数分级（≥7→LP, 3-6→EP），Flicker/ANTI/Witness 等无元数据专辑恢复上榜
- **Artist Summary 跨专辑合并**：`compute_artist_summary` 不再按 album_name 分组，改为按 track_id 聚合后取代表专辑（如 vampire 从三条合并为一条）
- **Album Meta 优先 album_spotify_links**：`_get_album_spotify_meta` 优先走 album_spotify_links（album-type 优先+置信度排序），回退旧链加 ORDER BY，修复同名单曲遮盖完整专辑导致的 total_tracks=1 / album_type=single
- **封面三级回退**：`_get_cover_cdn_url` 新增 album_spotify_links 分支（album-type 优先），`_add_cover_urls` 新增 Spotify metadata fallback，修复新导入专辑封面缺失或错用单曲封面
- **Wrapped 年度总结口径统一**：`/wrapped/{year}/full` merge_level 默认值从 1 改为 2，与 Analysis Charts 一致使用 album project 聚合
- **Spotify 元数据自动刷新 + 导入维护管道**：`import_data` 写入 `spotify_track_id_at_play`，导入后自动运行维护管线（刷新 Spotify metadata → 重建 album projects → 重建预聚合 → 清除缓存 → 健康报告）；新增 `album_spotify_links` 证据表、`refresh_import_derived_data.py` 独立脚本

### 验证

- Backend 520 (unit+contract) PASS，0 失败
- 全链路实测：Midnights release_date 2022-10-21（修复前 2023-05-26）、you seem pretty sad... 封面/发行日正确
- 新增 11 个测试（import maintenance、Spotify metadata refresh、import health、CLI script）

---

## 2026-06-27 — 验收补强与阻塞复核

### 修复

- 修复 OpenAPI 参数边界审计未解包 nullable schema 的漏算问题，`max_merge_gap_minutes` 已纳入边界 probe；当前参数边界 audit 为 60 obligations / 0 unaccounted，API boundary probe 为 90/90 PASS
- 修复播放排行 track 行在 track group 聚合后缺失 `album_name`，避免前端从播放排行进入音乐详情时生成空专辑路径
- 将 Billboard Year-End staged wrapper 拆入 `chart_year_end_api.py`，保持 `chart_staged_api.py` 作为薄 facade 并继续满足行数护栏
- 前端 smoke 补强冷态重页面和动态详情路由等待：`/analysis/records` 在 route/control smoke 中使用慢页窗口，cross-browser 动态详情路由支持重试；Year-End 单页 50 行表格在 long-list smoke 中按 capped 表格验收
- 图表交互 smoke 的 legend 场景改为稳定的音乐详情 ECharts 排名趋势图，避免账号页生命周期趋势为空时误报；首页 Dashboard 月度趋势继续保留 ECharts 视觉
- Web Vitals probe 对单次 lab 预算失败样本执行一次复测，预算仍未通过则失败，降低 headless CLS 采样噪声导致的误杀
- fullstack verification 的 API benchmark 调用会清空本地代理变量，避免 `HTTP_PROXY/ALL_PROXY` 污染 127.0.0.1 性能检查

### 验证

- Backend full 739 passed；Phase 5 最低矩阵 PASS；pre-commit PASS；完整 fullstack verification 带 quickstart、preview、Web Vitals 与资源预算 PASS
- API benchmark hot P95 均低于 500ms；`/api/billboard/data` hot P95 0.20s，`/api/dashboard/full` hot P95 0.16s；runtime resource 总 RSS 826.4MB / CPU 77.7%
- dev 与 production preview route/interaction/chart/control/long-list/cross-browser smoke 均通过；production preview Web Vitals 全部在预算内，首页 ECharts 版本 desktop LCP 2060ms / CLS 0 / TBT 0ms / 17 resources / 1131.2KB，mobile LCP 612ms / CLS 0 / TBT 0ms
- 固定域名 ngrok HTTPS tunnel 复核通过；外部 `/api/health`、Spotify auth status/data/login 和 invalid-state callback 均可达，callback 回跳 `https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state`；真实 Spotify 用户 consent 点击仍需人工确认

---

## 2026-06-20 — fix/bugfixes-and-polish 分支

### 修复

- 修复旧 `/analysis/*` 别名嵌套在 lazy `AnalysisLayout` 内导致的冷导航空壳风险
- 首页 Dashboard 月度趋势按产品偏好保留 ECharts 视觉，并将实现拆到 `MonthlyTrendEChart` 动态块；production preview 首页 LCP/CLS/TBT 仍在预算内（desktop `2004ms/0/0ms`，mobile `544ms/0/0ms`）
- 账号页新增轻量 `/profile` 首屏 Hero 查询，`/api/account` 聚合加入 TTL cache + warmup，production `/account` desktop LCP 从 `3532ms` 降至 `468ms`
- 根级 `scrollbar-gutter: stable` 将 `/billboard/number-ones` desktop CLS 从 `0.1` 压到 `0`
- Spotify OAuth 在 ngrok `SPOTIFY_REDIRECT_URI` 且未显式设置 `FRONTEND_ORIGIN` 时，callback 回跳 origin 从 redirect URI 推导，避免授权后掉回 localhost
- 图表交互 smoke 默认冷态等待调至 12s；前端 CDP smoke 脚本默认优先使用 Playwright `chromium_headless_shell-*`，避免系统 Chrome 启动阶段崩溃造成假失败

### 验证

- Backend full 694、unit 322、contract 172、frontend 134、完整 fullstack verification PASS
- 2026-06-21 复核：固定域名 ngrok HTTPS tunnel 已可建立，外部 health、Spotify login URL、invalid-state callback 回跳和 auth data 入口通过；真实 Spotify 用户 consent 点击仍需人工确认

详见 [`docs/verification/2026-06-20-fix-branch-follow-up.md`](verification/2026-06-20-fix-branch-follow-up.md)。

---

## 2026-06-19 — 全栈验证与性能收口

### 性能优化

- 默认预热改用当前动态阈值口径，避免预热旧缓存并与首屏请求抢 CPU
- Billboard 基础排名共享缓存（`_load_and_rank_cached`）
- Power Score、Billboard summaries 与播放合并路径向量化
- Dashboard full 单请求复用同一播放 DataFrame
- AI Insights 报告/问答透传播放过滤口径，并按过滤指纹分流缓存
- Behavior 全量事件分析只暴露/请求 `music_only`
- 专辑详情来源拆分批量映射
- 390px 移动端横向滚动归零
- pre-commit 收敛到 backend 治理范围
- OpenCC/ECharts 大依赖拆为按需加载子包，保存偏好不再模块级预取字典
- 账号页资源加载收敛

### 监控与验收

- **API 验收**：96 请求本地只读 API smoke 探针、85 个非破坏性 API 边界 probe
- **OpenAPI 审计**：134 operation 全量 audit（95 safe GET smoke / 30 targeted contract / 9 controlled stateful-external / 0 unaccounted）、参数边界 audit（59 obligations / 36 boundary_probe / 16 string_resilience_probe / 7 controlled stateful-external / 0 unaccounted）
- **Contract 护栏**：Provider 异常响应分层、Billboard enrichment 降级、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON response_model（OpenAPI response_model 缺口 41→1）
- **8 端点 API 性能 benchmark** 慢端点门禁
- **前端 smoke**：48 组合 route（19 主路由 + 5 动态详情路由 × 2 视口）、6 场景交互（AI Insights 按 settings 分支验证、Settings 过滤/显示偏好与数据导入区覆盖）、3 场景 ECharts 图表交互、36 组合控件库存（13 默认路由 + 5 动态详情路由 × 2 视口，0 violation）、6 场景长列表分页/分段渲染
- **跨浏览器**：Chromium/Firefox/WebKit PASS 3/3
- **Web Vitals lab**：dev/prod-preview LCP/CLS/TBT/资源数量/encoded 体积/横向滚动溢出预算门禁

### 修复

- Spotify 当前播放 token refresh、OAuth login 未配置 Client ID 500、Settings 越界配置、清翻译缓存缺表、Provider 异常泛化 500、封面回退查询 schema mismatch 500、Billboard enrichment Wiki lookup 普通异常 500
- 基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON 相关端点缺少 response_model
- AI Insights 报告缓存 readonly 写入 warning
- 会话列表嵌套按钮、周快捷项重复 key console error、音乐详情隐藏 tab 挂载图表导致的 ECharts 零尺寸 warning
- Billboard/Records/AllTime/WeekSelector/音乐详情分页图标按钮与 Settings Slider 内部输入控件缺少可访问名称

详见 [`docs/verification/2026-06-19-fullstack-verification.md`](verification/2026-06-19-fullstack-verification.md)。

---

## 2026-06-18 — 播放统计规则引擎（Phase C+D）

### 新增

- Session 边界检测：`max_gap_minutes` + `boundary_column` 参数化控制
- 动态阈值：替代固定 15 秒阈值
- Track Groups 三级合并：
  - L1：不合并（raw）
  - L2：按 recording 范围合并（同 ISRC/同录音）
  - L3：按 composition 范围合并（涵盖翻唱、现场版、remaster）
- Album Projects 专辑项目统计：L2/L3 使用 track membership，source album 仅作 breakdown，Billboard 按 release_date 排除发行前周
- `MergeConfig` FastAPI 依赖
- 设置页 L1/L2/L3 合并严格度选择器

### 传播

- Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Release Cycle 统一传递 `dynamic_threshold` 与 `max_merge_gap_minutes`
- R24b + 过滤传播合约测试

详见 [`docs/playback-stats/rules.md`](playback-stats/rules.md)。

---

## 2026-06-12 — Phase 5.4 A-H 全系列完成

- **A**：TrackDetail 574→5 行 facade
- **B**：HabitsTab 933 行→9 文件 feature 拆分
- **C**：AI Insights 前端拆分（Experience/ReportCard/ChatInterface/ChatSessionList 等）
- **D**：AI Insights 后端拆分
- **E**：24 端点 response_model 硬化（OpenAPI 自动类型生成对应）
- **F**：Bundle 懒加载治理（Settings -88%、Records -69%、Account -34%）
- **G**：TrackDetail 歌词 Query 漏网修复
- **H**：Cross-cutting — 架构护栏 105+ 测试 + CI 基线

详见 [`docs/productization/2026-06-08-phase5-baseline.md`](productization/2026-06-08-phase5-baseline.md)。

---

## Phase 5 产品化收口基线

Phase 5 目标是收紧产品线到可持续迭代状态。已完成：

- 前端 GET 统一 TanStack Query（11 命名空间 queryKeys）：dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge/community/aiInsights
- Provider 错误分类与 API 响应分层体系（`ProviderError` → `ProviderNetworkError`/`ProviderHTTPError` → `ProviderAuthError`/`ProviderRateLimitError`/`ProviderServerError` + `ProviderParseError`；API 层映射结构化 503/502/429）
- 业务 service 层 urllib 调用清零；core Spotify HTTP 收敛到 `HttpClient`/`SpotifyProvider`
- Billboard 与 Artist/Album 详情页完成 route container 化
- 模块级 API 响应 Map 缓存全部清除，迁移到 TanStack Query
- Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线
- Request ID（`X-Request-ID` 生成/透传/日志关联）
- Billboard records 88 行 facade + chart_compute 211 行 facade
- 新增页面遵守 route container ≤450 行

### 当前验证口径

**交互 smoke**：6 个非破坏性场景，AI Insights 按 LLM 已配置/未配置分支验证；dev server 与生产 `vite preview` 均已复跑 PASS 6/6。

**控件库存 smoke**：13 个默认路由 + 5 个动态详情路由 × 桌面/390px 移动端，检查可见交互控件缺少可访问名称、嵌套交互控件、disabled 仍可 tab、输入控件无标签和重复 id；dev server 覆盖 36 组合 / 1821 控件 / 0 violation，生产 `vite preview` 覆盖 36 组合 / 1763 控件 / 0 violation。

**跨浏览器 smoke**：core-interactions 覆盖同一组 6 个核心交互；dev server 完整 route-marker + core-interactions 与生产 `vite preview` core-interactions 均已在 Chromium/Firefox/WebKit PASS 3/3。

**测试基线**：backend full 694 / unit 322 / contract 172 / frontend 134。
