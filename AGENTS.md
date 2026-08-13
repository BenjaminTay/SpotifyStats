# AGENTS.md

## 年度生成协调（2026-08-12）

在既有年度只读报告 API 外，新增 `/api/yearly-review/prewarm` 与 `/api/yearly-review/generation-status`。`yearly_review_generation_v1` 使用单工作线程优先级队列和精确 cache key 去重：当前年份优先，其他可用年份从近到远后台预建，切换年份可提升 queued 任务，计时锚定服务端 `requested_at`。缓存命中必须绕过冷构建锁，前端离开页面只能取消 HTTP 等待，不能取消后台任务；Desktop/Compact/Phone 的年度总结共用该链路。

Spotify Extended Streaming History 数据分析 Web 应用的主项目提示词文件，供 Claude Code 及其他 AI 编码助手共同使用。

---

## 项目概述

从 Spotify 官方 JSON 播放记录导入 SQLite，通过 **FastAPI 后端 + React 前端** 提供交互式多维度统计仪表盘。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线 + Inter 无衬线）+ 毛玻璃材质 + 日/夜双皮肤。详见 `frontend/UI_STYLE_GUIDE.md`。

**个人音乐首页 V1（2026-08-13）**：`/` 是“个人音乐头版”，不再承担播放统计仪表盘职责。Desktop 使用头条、档案护照、最近 4 周、最新个人 Billboard、年度年鉴入口与旧爱重听的杂志编排，Phone 使用互斥挂载的单列口袋头版；首页不重复展示数据更新时间、音乐搜索、数据陈旧提醒或账号/AI/社区/更新数据快捷入口。两端共享 `/api/home/overview`、完整过滤指纹、实体深链和确定性事实。头条不调用 LLM；最近窗口严格使用最新有效播放日锚定的两个连续 28 个自然日，趋势补齐零播放日；首页进入播放分析的近期入口显式选择 `last_4_weeks` 并携带同一窗口起止日，不改变播放分析页的全部时间默认值。数据新鲜度使用原始音乐源最新日期，不能受有效播放阈值影响。首页的年度预览和 Billboard 摘要只能读取已存在的精确缓存，禁止因打开首页触发年度或榜单冷构建。App Shell 不再全局预取旧 Dashboard、周榜或总榜。

**导航命名（2026-08-13）**：顶级入口使用“播放分析”；二级 tab 顺序固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 音乐档案”。年度总结与音乐档案归属播放分析 tab 行，避免在 Masthead 中恢复独立顶级入口、重复下拉入口或第二套子导航。

**音乐档案（2026-08-13）**：`/account` 路由和二级导航统一命名为“音乐档案”。Desktop / Compact 与 Phone 使用互斥 presentation，共享 `account_archive` 严格统计事实和 `queryKeys.account.archive*`；封面只展示收藏歌曲、专辑、艺人和歌单数量，不展示数据范围、截止日期或数据状态。消费界面的章节标题只保留编号和主标题，不附解释性 subtitle；统计项必须用普通用户可直接理解的名称，不展示“可观察”“可验证”、方法说明或工程口径。收藏旅程使用第 100 / 200 / 400 / 800 首等倍增里程碑，不重复封面的最早/最近收藏；收藏后再次播放使用“7 天内 / 第 8–30 天 / 半年后 / 一年后”四个互补窗口，不并排展示四个单调累积指标；视频卡展示带封面和详情深链的本地可识别 Top 3。页面运行时不得请求 Spotify Web API、`/api/profile`、旧 `/api/account` 聚合或 `/api/account/collection-insights`。旧人格/chemistry、Habits、Marquee 和粉丝等级 UI 已删除，两条旧聚合路由与 `services/account_service.py` 已退役；AI 工具名 `account_summary` / `account_collection_insights` 为编排兼容名，事实必须来自 archive overview、journey、cohorts、returns 与隐私白名单 discovery，禁止恢复收藏人格推断。统计规则见 `docs/reference/account-archive-statistics.md`。

**年度总结 V2（2026-08-12）**：`/yearly-review` 是单一的自有年度总结入口；Desktop/Compact 与 Phone 共享确定性八章 `YearlyReviewV2` 数据、过滤指纹、缓存和后台生成链路，但保持互斥、独立的 presentation。桌面使用完整杂志年鉴，Phone 使用“口袋音乐年鉴”、2×3 KPI、紧凑章节进度 Sheet、纵向时间线和无宽表的全屏榜单。官方 Wrapped 页签及前端组件已退役；`/api/wrapped-hub`、官方导入表与读取服务仅作只读兼容冻结，不再新增消费 UI 或产品能力。后端只读 API 为 `/api/yearly-review/available-years`、`/{year}`、`/{year}/records`；主报告与兼容 records 响应必须共享完整过滤指纹、策略版本、display taxonomy/艺人元数据 revision 和缓存语义。月度正文只保留一条转折时间线，十二月明细进入可展开账本；播放榜与个人 Billboard 不得混名，YTD/partial/unknown 必须由 coverage 控制措辞，LLM 不参与事实生成。同比只使用真实 aligned window，工作日/周末使用观察区间自然日日均，Passport 与播放榜共享规范实体粒度；YTD 品味只比较完整季度，不足时只展示分布。公开纪录必须命中显式 renderer 并具备周期/数值证据，阶段无法证明时为空，结语不得复制开篇。消费界面只使用普通用户能理解的文案，不展示口径、指纹、策略、证据等级、coverage 或 limitations；六项年度 KPI 只用红/绿箭头与百分比表示同比，实体故事和完整榜单优先显示封面及详情深链，大标题不附加解释性 subtitle。年份按钮按升序排列、只显示年份，并默认最新可用年份（即使当前年度尚未结束）；完整年度封面不显示状态/日期，进行中报告仍在封面保留截止日期；封面不再显示三条头条或海报操作。所有年度动态文案与实体名称必须遵循全局简繁体偏好；回归、发现等时间线事件必须明确对象是歌曲、专辑还是艺人，避免与详情页的歌曲/专辑榜单混淆。新关系按实体分别称为“今年发现的新歌 / 今年新听的专辑 / 今年认识的新艺人”，同专辑或艺人多首入榜纪录必须写明准确曲目数；宽屏分歧故事两列、窄屏单列。年度纪录章只展示 6–8 条精选，不提供“更多年度纪录”目录；兼容 `/records` 只返回与正文相同的精选集合，artifact 不再序列化上千条候选。桌面章节纵向 padding 统一为 `clamp(48px, 5.5vw, 80px)`；Phone 主要触控目标至少 44×44px，完整榜单正文只预览 Top 5，全屏每页 10 条并在关闭后恢复焦点。schema version 与 content version 分开治理，任何统计/编排/公开展示语义变化都必须提升 content version。当前 content 为 v2.12；v2.8 的 2023–2026 性能基线为真实重算 10.65–16.54s、热响应 26.56–29.85ms、跨进程持久命中 10.20–21.07ms。公开文案、封面/深链、YTD 措辞、精选证据、结语去重和阶段状态由 `scripts/yearly_review_v2_probe.py` v5 固定。规则和最终证据见 `docs/reference/playback-stats-rules.md` 与 `docs/reports/2026-08-12-yearly-review-v2-delivery.md`。

**移动网页架构（2026-08-05）**：`<768px` 使用独立 Phone presentation，`768–1023px` 为 Compact，`>=1024px` 使用 Desktop；Phone/Desktop 的重图表、宽表与长列表必须互斥挂载，但继续共享 Route Container、React Router URL 状态、TanStack Query、过滤指纹、row model 和统计事实。Phone Shell 固定使用 `MobileTopBar`、五项 `MobileBottomNav` 与播放分析/Billboard `MobileSectionSwitcher`；Push 详情按路由语义隐藏 Bottom Nav。主要移动触控目标至少 44×44px，关键操作不得依赖 hover，复杂图表需提供触摸 disclosure 与可恢复焦点的全屏模式。Settings 手机端只开放低风险日常设置；导入、元数据治理、凭据和系统维护保留桌面工作台。新增消费页面必须通过 360/390/430/768/1280 route matrix、移动 control inventory、interaction/chart、long-list 与 Chromium/Firefox/WebKit 门禁。完整规范见 `frontend/UI_STYLE_GUIDE.md` 和 `docs/plans/2026-08-05-mobile-web-design-and-implementation-plan.md`。

**PWA / App 化基线（2026-08-06）**：生产前端通过 `/manifest.webmanifest`、192/512 maskable 图标、Apple Touch Icon 和 `/sw.js` 提供可安装 PWA；开发模式不得注册 Service Worker。手机 Settings 的安装卡只表达安装方式，不建立第二套导航。Service Worker 只缓存离线说明、PWA 图标和版本化静态 `/assets/`，必须绕过 `/api/`、`/covers/`、OAuth/LLM 凭据与所有个人统计数据；离线页不得伪装为可用数据页。现行 App 路线为 PWA → HTTPS 安全部署/真机 → Capacitor；在远程 API 鉴权、SQLite 持久化/备份和 Spotify OAuth 回跳完成前，不生成商店发布结论。完整路线见 `docs/plans/2026-08-06-appification-pwa-capacitor-plan.md`。

**音乐查找（2026-07-03）**：Masthead 右侧提供全局音乐搜索图标，`/music/search` 是可分享的完整查找页；后端 `/api/music/search` 只读搜索本地播放历史中的歌曲/专辑/艺人，结果打开既有 `/music/tracks/:trackId`、`/music/albums/:albumName?artist=...`、`/music/artists/:artistName` 详情页。`include_chart=true` 时返回与详情页同口径的个人 Billboard 摘要，前端只展示播放次数、`PK #`、在榜周数与走势排名，不展示冠军周数；Masthead 弹层默认不预选第一条结果，只有 hover/focus 或方向键后才高亮。不要在“播放排行”页再放重复搜索框或按钮。

**Billboard 对决一致性（2026-08-03）**：单曲、专辑、艺人对决及其 entity lists 必须与对应详情页共享完整统计上下文，包括动态阈值、连续播放间隔、合并级别、榜单周边界、三类 Top N、年份范围与精选集设置；前端 query key 必须包含完整过滤指纹。专辑对决按 `album project identity + canonical artist` 复用详情口径的 `track_per_album` / `album_track_counts`，不得退回 `release_groups` 或仅按 `album_name` 归属；艺人歌曲成绩按 credited artist fan-out 并以稳定播放事件与 canonical artist 去重。

**Billboard 总榜跨层级指标（2026-08-03）**：专辑的 `track_power_sum/rank` 与艺人的 `track_power_sum/rank`、`album_power_sum/rank` 必须通过 `cross_level_power.py` 复用详情/对决的 album project membership 和 canonical credited-artist 归属。派生排名面向当前完整同类总榜，正值使用 competition rank，零贡献不排名；客户端搜索、分页或字段隐藏不得改变原始总榜排名。三类总榜列偏好分别持久化，只有名称和当前排名固定；实体走势评分及其固定全榜排名必须作为相邻、可独立显示的字段。

**音乐详情存在资格与独立榜单成绩（2026-08-03）**：歌曲、专辑、艺人详情页的存在资格不得由 Billboard Top-N 或 versus picker 决定；当前有效播放口径下至少有一条播放，或已有可解析榜单事实时必须可访问。三类页面的固定 Tab 不因成绩为空而隐藏；`chart_status` 只描述实体自身榜单，专辑另用 `track_chart_status`，艺人另用 `track_chart_status` / `album_chart_status` 描述子成绩。专辑榜事实按 album project identity + canonical artist 匹配，不得依赖成员歌曲是否进入单曲榜；只有既无有效播放也无可解析事实的随机实体返回 404。versus picker 仍可保守只列可对照实体，两者资格边界必须通过 contract tests 分开锁定。

**性能策略**：Cache Manager 管理 5 命名空间（billboard/analysis/db/auth）LRU+TTL 缓存；Billboard 拆为 4 个独立 `@lru_cache` 函数，并通过共享 `_load_and_rank_cached` + `singleflight()` 避免 weekly/power/summaries/all-time 冷启动重复计算；Power Score、Billboard summaries 和 `merge_consecutive_plays()` 使用列级/组级向量化，避免逐行 `DataFrame.apply(axis=1)`、`iterrows()` 或 `to_dict()` 热路径；Dashboard full 单请求复用同一播放 DataFrame；`agg_weekly_track_sources` 支撑 album project 专辑榜和详情来源拆分；启动 warmup 使用当前默认动态阈值口径并预热 artist fan-out；SQLite 版本化 Migration；后台 Job Queue（3 worker）异步处理封面下载与 Wikipedia+LLM enrichment；前端 GET 数据统一进入 TanStack React Query（staleTime 5min/gcTime 30min/retry 2），路由级 lazy 分包；ECharts 统一走 `LazyEChart` + `echarts-for-react/esm/core` 按需注册，OpenCC 简繁转换只动态加载 `opencc-js/t2cn` 或 `opencc-js/cn2t` 子包，保存偏好恢复不得在模块初始化时预取大字典；账号页长图列表使用预览上限与原生图片懒加载，Web Vitals lab 通过 `scripts/frontend_web_vitals_probe.mjs` 采样，并可用 LCP/CLS/TBT/资源数量/encoded 体积/横向滚动溢出预算参数作为回归门禁。

**AI 可观察任务与只读 Agent（2026-07-03）**：AI 报告采用 cache-first + 手动生成，不因打开页面自动调用 LLM；年度叙事必须经过报告数据契约与质量校验，明确 reporting_period、年中/全年口径、同期对比、TOP 名称、TOP 专辑、个人 Billboard Year-End、editorial_brief 主线、人格维度、流派 caveat 与高光解释；不合格时按降温重试，多轮仍不合格则使用确定性 fallback 生成可用报告，只有通过 validator 的文本才写入缓存；AI task runs/events/tool_calls 持久化到 SQLite，前端通过 `features/ai-tasks` 统一展示进度、证据卡片和工具轨迹；问答改为后端只读 Agent 工具链，模型只可规划 allowlist read-only 工具（总体统计、排行、播放记录、年度总结、实体统计、个人 Billboard 实体详情、听歌时段/深夜歌曲排行、账号收藏概况、搜索历史、社区帖子搜索与热议趋势），不得调用任意 SQL/URL/写操作；最终回答只能基于 compact evidence、coverage、EvidenceSufficiency、AnalyticalBrief 和 answer_obligations，prompt 与 AnswerContract 明确区分本地个人 Billboard 与外部官方 Billboard，并在 coverage/answer contract 矛盾时自动重试一次；Project Context Prompt 作为 AI Agent 的项目语境层，集中描述 SpotifyStats 的个人音乐数据定位、本地个人 Billboard 边界、偏好分析口径、页面域工具和默认回答哲学；Planner 与最终回答 prompt 通过版本化 context 组合工具 playbook 与 answer philosophy，最终 payload / task result 记录 `project_context_version` 便于排查；QuestionFrame、EvidenceRecipe、EvidenceSufficiency、AnalyticalBrief、answer_obligations、entity resolver、compare_entities、answer critic 与 golden-question harness 共同构成 AI Agent 通用分析中间层；`scripts/evaluate_ai_question_matrix.py` 支持 static、p0、safety、multiturn、changed、full，其中 full 会把 `AI-MULTI-*` 用例按真实多轮 runner 执行；相对时间以 question_time 为准，数据范围优先使用本地 `ts_date`；艺人 career 与专辑 era enrichment 已接入同一 task 进度模型。

**AI Visual Yearly Report Artifact（2026-07-05 重构）**：年度报告默认 `report_mode=visual_yearly_artifact` + `writer_pipeline=agent_synthesis_v2`。后端 `report_writer.py` 用一次 LLM 合成调用（遵循 Agent Answer Philosophy 模式）生成报告正文，`build_report_writer_context()` 将研究数据转为富文本摘要喂给 LLM，`parse_report_sections()` 解析 LLM 输出为 Section 列表；保留确定性 chart data builder（`visual_chart_data.py`）、visual brief planner（`visual_brief.py`）、critic（`visual_yearly_critic.py`）、fact validator（`yearly_validator.py`）、final artifact quality gate 和 `_compose_sections()` 确定性 fallback 作为多层安全网。已删除 6 阶段 `editorial_agent/` 流水线（~1,500 行，含 pipeline/writer/editor/claim_checker/taste_rubric/research_brief/storyline_planner），用 606 行 `report_writer.py` 替代，LLM 调用从 6 次减为 1 次。`editorial_agent_v1` 保留为兼容值，映射到新路径。图表数据仍由确定性后端生成，LLM 不得生成图表数据。缓存 key 包含 `visual_yearly_artifact`、`visual_yearly_v1` 与 writer pipeline。前端优先渲染 `artifact`，无 artifact 时回退 Markdown；YearlySection prose 通过 `AiMarkdown`（react-markdown + remarkGfm + rehypeSanitize）正确渲染粗体/斜体/列表等 Markdown 格式。

**Agentic Longform Yearly Report（2026-07-03）**：`report_mode=agentic_longform` 保留为文本长文/兼容模式，由 `backend/services/yearly_report_agent_service.py` 编排；Report Agent 只能调用 `backend/domains/ai_reports/agentic_tools.py` 中 allowlist read-only 工具，流程固定为 research/evidence ledger → insight synthesis → dynamic outline → longform draft → editorial critic。`agentic_yearly_v14` metadata、critic、dynamic_outline 与 evidence_ledger 会进入 task result，evidence_ledger 会持久化为 `ai_tool_calls`；critic 不通过时只能标记 `fallback_level=basic_summary` 并调用旧确定性摘要，不得把基础摘要包装成正式长文。新增年报能力时优先扩展 report-specific read-only tools、artifact builders 和 critic，而不是把更多一次性 DATA 拼进 prompt。

**AI Agent 相对时间 grounding（2026-07-03）**：Chat Agent 请求可携带 `question_time` 与 `timezone`，后端会生成 `temporal_context`（含 `today`、数据起止日与 `latest_play_date`）并注入 planner/final answer；“今年/去年/上个月/最近/夏天”等相对时间必须以 `question_time` 为锚点，`temporal_guard` 会在工具执行前校正明显错年的只读工具参数，必要时补充 bounded custom range 工具并约束后续补查工具；校正后的 custom range 必须投影到 EvidenceRecipe/AnalyticalBrief 的 `required_context`，让 EvidenceSufficiency 按实际执行时间窗口判定；在 task events/result 与前端消息中展示时间解释。曲风/语种问题若没有结构化 genre/language 证据，只能给保守限制说明，不得仅凭艺人常识给强确定结论。

**艺人语言事实与统计（2026-07-11）**：语言元数据以稳定 `artist_id` 为主体，独立于 genre 解析与 taxonomy；播放语言统计只按 `tracks.artist_id` 的主艺人归属，不使用 `track_artists` fan-out。只有 approved fact 可进入统计和 Wrapped 缓存 revision；legacy 数据、LLM 和未审核 seed 只能进入 suggested/review 流程。显式 reviewed seed 仅可在 evidence、`reviewed_by` 与 `resolution_note` 齐全，并通过同一 validator 与 review state machine 时批准，仍不得自动猜测批准。统计与 UI 必须保留 `unknown`、`multilingual`、`instrumental` 以及未归属时长，不得通过 genre 或艺人名称启发式补齐。Settings 卡片 05 的“流派与语言”子模块负责覆盖率、缺失项、搜索、证据和审核历史；年度总结直接渲染后端动态 language buckets，并与 genre 独立显示。

**艺人 genre 四轴治理与消费展示（2026-08-04）**：resolved artist genre 仍遵循 Spotify 非空优先、本地 approved fallback 次之，但 source coverage 不等同于 style coverage。底层 canonical 标签继续按 `style`、`scene`、`context`、`role` 独立治理，只在同一 axis 内分摊艺人时长；不得改写原始或 approved facts。普通用户侧统一通过 `backend/domains/metadata/genre_display_taxonomy.py` 的版本化 display taxonomy：年度总结只展示“主曲风”（style）、“地区流行”（scene）和独立语言分布，unknown 写为“尚未归类”；`context` / `role` 不进入主图，Singer-Songwriter 不得再形成 100% 偏好图。Rock/Alternative 消费显示为 Rock，Indie/Alternative 显示为 Indie，R&B/Soul 保持合并；Electronic/Dance 仅在原始标签可靠时拆为 Electronic、Dance、Ambient。播放统计页不展示曲风/语言模块；Music Map 的地区 heuristic 保留底层兼容但不在年度消费页展示。Genre 和 language 统一采用 `tracks.artist_id` 主艺人归属、艺人 alias canonicalization 与明确的 track attribution exclusion，不做 featured artist fan-out。Settings 继续完整展示来源、证据、置信度、覆盖率和审核历史；消费 UI 不得泄漏这些治理术语。Wrapped、AI 报告及相关缓存必须包含 display taxonomy / artist metadata revision。

**音乐源数据管理与有效曲目署名（2026-08-03）**：Settings 的“音乐源数据管理”以“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块统一承载人工修订；归并工作区只有一套 L1/L2/L3 与自动检测/已保存分组/手动创建入口，歌曲和专辑版本以对象类型标签区分，专辑阈值和发行项目重建只出现在高级上下文。这是单管理员直接编辑工具，理由/证据不是 UI 或 API 必填项，普通修改直接应用，只有跨 provider/canonical 冲突保留一次确认。原始 `plays`、`tracks`、`track_artists` 不得因人工治理而重写；曲目署名用 `track_credit_overrides` + append-only events + revision/rebuild state 叠加。所有 artist fan-out 消费者必须调用 `backend/domains/metadata/track_credits.py` 的有效署名 resolver，再经过 artist identity canonicalization，并以稳定播放事件 + canonical artist 去重。人工署名只接受本地 `artist_id`；preview、expected revision/idempotency、实时 resolver 兜底、shadow rebuild 和 undo 仍是内部强制契约。详情页只通过含目标、实体、返回地址和 anchor 的深链进入 Settings，不另建写逻辑。完整规则见 `docs/reference/music-metadata-management.md`。

## Phase 5 产品化收口基线

Phase 5 目标是收紧产品线到可持续迭代状态。当前进度：

**已完成**：
- 前端 GET 数据获取统一到 TanStack Query + `queryKeys`（12 命名空间：dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge/community/aiInsights/aiTasks）
- Provider 错误分类与 API 响应分层体系（`ProviderError` → `ProviderNetworkError`/`ProviderHTTPError` → `ProviderAuthError`/`ProviderRateLimitError`/`ProviderServerError` + `ProviderParseError`；API 层映射结构化 503/502/429）
- 业务 service 层 urllib 调用清零；core Spotify HTTP 收敛到 `HttpClient`/`SpotifyProvider`
- Billboard 与 Artist/Album 详情页完成 route container 化；新增页面遵守 route container ≤450 行，当前例外和后续治理见 Phase 5 台账
- 音乐详情页持续拆分到 feature sections；header/tabs/skeletons/overview/tracks/albums/career/artist-releases/album-era 子 sections 与共享 primitives 已从 Artist/Album Experience 中抽出
- 前端展示类型 `frontend/src/types/billboard.ts` 已补齐 Billboard、音乐详情、release-cycle 与 enrichment 常用展示字段，`npm run build` 作为硬验证
- 模块级 API 响应 Map 缓存全部清除，迁移到 TanStack Query
- Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线，新增长表必须继续使用分页、infinite query 或虚拟化
- Request ID（`X-Request-ID` 生成/透传/日志关联）
- Billboard records 输出层已拆入 `backend/domains/billboard/records_output.py`，championship/no1 family 已拆入 `records_championship.py`，longevity/persistence family 已拆入 `records_longevity.py`，movement/breakthrough family 已拆入 `records_movement.py`，hall-of-fame/power ranking family 已拆入 `records_hall_of_fame.py`，endurance/rank-stability family 已拆入 `records_endurance.py`，self-replacement/blocker family 已拆入 `records_self_replacement_blocker.py`，market/market-intensity family 已拆入 `records_market.py`，quirky/special-feat family 已拆入 `records_quirky.py`，`records.py` 保留 88 行纯编排 facade
- Billboard chart 周榜排名已拆入 `backend/domains/billboard/chart_ranking.py`，走势评分（Power Score）已拆入 `backend/domains/billboard/chart_power_score.py`，summary/count helper 已拆入 `backend/domains/billboard/chart_summaries.py`，共享 load/rank cache 已拆入 `backend/domains/billboard/chart_load_rank.py`，staged cache 已拆入 `backend/domains/billboard/chart_staged_cache.py`，staged public API 已拆入 `backend/domains/billboard/chart_staged_api.py`，`chart_compute.py` 保留 211 行兼容入口/re-export/cache registration facade
- 架构护栏测试（`frontend/src/tests/phase5-architecture.test.ts`）与长列表分页渲染测试（`frontend/src/tests/long-list-pagination.test.tsx`）
- AI Observable Agent Orchestrator V2 + Universal Analytical Harness：报告/问答/艺人和专辑 enrichment 接入 AI task 进度，问答支持只读工具规划、思考模式、证据卡片、工具轨迹、QuestionFrame/EvidenceRecipe 证据配方、EvidenceSufficiency 补查、AnalyticalBrief 回答底稿、AnswerContract critic、矛盾回答重试和 golden-question harness
- `scripts/phase5_check.sh` 最低验证矩阵 + GitHub Actions CI 基线（`.github/workflows/phase5-baseline.yml`）

**持续治理**：
- Provider 全量替换：`release_cycle_service.py`、`wikipedia_service.py`、`spotify_utils.py` 和 `version_merge.py` 已收敛；后续按架构护栏防回归
- 后端 Billboard chart compute 已收口（`records.py` 88 行 / `chart_compute.py` 211 行）
- Phase 5.4-A 至 5.4-H 全系列完成（2026-06-12）：
  - 架构护栏测试 17→105+ 用例，覆盖所有新增页面
  - TrackDetailPage (574→5 行)、HabitsTab (933 行→9 文件 feature)、AiInsightsExperience/ChatInterface 拆分完毕
  - API 契约硬化：AI Insights (5) + Chat (6) + Community post (1) + Version Merge (12) = 24 端点补 response_model
  - Bundle 治理：SettingsPage -88%、RecordsPage -69%、AccountCenterPage -34%，合计首屏节省 ~178 kB
	  - TrackDetail 歌词 Query 漏网修复：手动 `fetchLyrics` + `useState` 改为 `useQuery`（`queryKeys.music.trackLyrics`）
- 长列表已建立分页基线；后续新增超过 500 行 DOM 的表格必须使用服务端分页、分页组件、infinite query 或虚拟化
- 播放统计规则引擎 Phase C+D（2026-06-12）：
  - P2 动态阈值 + Session 边界检测：`effective_threshold()` / `filter_effective_plays()`（`backend/domains/playback/counting.py`），`merge_consecutive_plays()` 支持 `max_gap_minutes` + `boundary_column`，`PlayFilters` 新增 `dynamic_threshold` / `max_merge_gap_minutes`
  - P4 Track Groups 三级合并：`track_groups` + `track_group_members` 表（scope: recording/composition），`backend/domains/playback/track_groups.py` 聚合键解析，`_apply_track_groups()` 在 Billboard 和个人榜聚合层生效
  - P4 Merge Level API：`MergeConfig` FastAPI 依赖，`/billboard/*` + `/analysis/charts` 端点 `merge_level` 查询参数，Settings 页面 L1/L2/L3 选择器持久化至 localStorage，4 个 Billboard 页面 URL 优先/localStorage 回退
  - 2026-06-18 贯穿修复：Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Artist Deep Dive/Release Cycle 全部传递 `dynamic_threshold` 与 `max_merge_gap_minutes`；Release Cycle 按 `billboard_week` 年份过滤，并接入 `merge_level` / `include_compilations`
  - 2026-06-18 Album Project 统计收口：新增 `album_projects` / `album_project_albums` / `album_project_tracks` + `agg_weekly_track_sources`；L2/L3 专辑统计改为 album project track membership，source album attribution 仅作为来源拆分解释；Billboard 专辑榜按 `album_project.release_date` 排除发行前播放；release groups 只描述版本关系，不再作为最终专辑播放量聚合层
  - 2026-06-19 全栈验证与性能收口：Billboard 分段接口共享基础排名缓存，Power Score、summaries、`_add_running_metrics()` 与 `merge_consecutive_plays()` 向量化；Dashboard full 复用同一播放 DataFrame；专辑详情 source breakdown 批量查 album metadata；AI Insights 周报/月报/年度叙事/自由问答透传 `dynamic_threshold` 与 `max_merge_gap_minutes` 到计数链路，并用过滤指纹分流报告缓存，readonly 请求连接会用可写连接完成报告缓存写入；Behavior 保持全量事件分析语义，仅暴露/请求有效的 `music_only` 参数；Provider 异常响应按分层映射为结构化 429/503/502 并防止原始上游错误文案外泄；基础设施、Settings mutation、Spotify auth、账号中心、核心统计与剩余 JSON response_model contract 覆盖 health/cache/import/job、设置写操作、Spotify OAuth/Web API JSON 端点、Search/Profile/Podcast/Video/Wrapped Hub GET、Timeline/Listening Hours/Artist/Wrapped GET、Release Cycle compare 和 Lyrics JSON 共 40 个端点，OpenAPI response_model 缺失从 41 降至 1，唯一剩余为 Spotify callback `RedirectResponse`；`load_plays()` / `load_plays_for_artists()` 缓存 miss 用 `singleflight()` 去重；warmup 改为 `dynamic_threshold=True` 默认口径；390px 移动端页面级横向滚动归零；pre-commit ruff/format 收敛到 `backend/`；前端 OpenCC full 包拆为 t2cn/cn2t 子包，保存偏好恢复不再模块级预取 `cn2t` 大字典，ECharts 默认入口改为 `LazyEChart` 按需 core 入口；账号页资源从约 250 requests / 25MB 收敛到 dev server 约 91-92 requests / 7.5MB，生产 preview 约 19-20 requests / 1.35-1.46MB，Web Vitals lab 已采集并补充 LCP/CLS/TBT/资源数量/encoded 体积/横向滚动溢出预算门禁；新增 `scripts/api_smoke_probe.py` 覆盖 96 个本地只读 GET 与 OpenAPI GET 覆盖核算，新增 `scripts/api_boundary_probe.py` 覆盖 85 个非破坏性 GET 边界（越界参数、非法 path/query 类型、非法 path/entity、特殊字符查询、422 validation detail 与 `X-Request-ID`），新增 `scripts/openapi_parameter_boundary_audit.py` 核算 59 个 OpenAPI 参数边界义务（36 boundary_probe / 16 string_resilience_probe / 7 controlled stateful-external / 0 unaccounted），新增 `scripts/openapi_operation_audit.py` 核算 134 个 OpenAPI operation 的验证归属（95 safe GET smoke / 30 targeted contract / 9 controlled stateful-external / 0 unaccounted），新增 Provider error contract probe 覆盖六类上游失败响应，新增 Billboard enrichment contract probe 覆盖专辑/艺人/歌曲可选 Wiki 增强异常降级，增强 `scripts/benchmark_api.py` 覆盖 8 个核心 API 的冷/热响应、raw/gzip 体积、JSON 输出与 hot P95 慢端点门禁，新增 `scripts/frontend_route_smoke.mjs` 覆盖 19 个主路由 + 5 个动态详情路由 × 2 视口（含 `/analysis` 与 5 个分析重定向别名；详情路由来自本地 API 样本）、默认 5s 等待并检查业务内容 marker，新增 `scripts/frontend_interaction_smoke.mjs` 覆盖分析页 tab、Billboard 子路由/前进后退、AI Insights 报告/问答 tab（按 settings 判断 LLM 已配置/未配置分支）、Settings 过滤/显示偏好控件、数据导入区与主题切换，新增 `scripts/frontend_chart_interaction_smoke.mjs` 覆盖 ECharts tooltip hover、legend toggle、dataZoom drag，并支持 `--api-base-url` 跑生产 preview + 8000 API，新增 `scripts/frontend_control_inventory_smoke.mjs` 覆盖 13 默认路由 + 5 动态详情路由 × 2 视口的可见交互控件命名、嵌套、tabbable、表单标签和重复 id，新增 `scripts/frontend_long_list_smoke.mjs` 覆盖 Records mini-rank、Billboard All-Time、Community Feed、RecentPlays、SavedTracks、PersonalRankTable 6 个长列表分页/分段渲染场景，并支持 `--api-base-url` 将生产 preview 的 `/api` 与 `/covers` 请求转发到 8000 后端，新增 `scripts/fullstack_verification_check.sh` 聚合 backend full、pre-commit、Phase 5、OpenAPI operation audit、OpenAPI parameter boundary audit、API smoke/boundary、benchmark 与前端 smoke 的非破坏性验收矩阵，新增 `scripts/ci_baseline_parity.py` 校验 `.github/workflows/phase5-baseline.yml` 与 `scripts/phase5_check.sh` 的核心检查命令一致，新增 `scripts/frontend_cross_browser_smoke.mjs` 通过 Playwright Chromium/Firefox/WebKit（Safari-family）覆盖 6 路由 × 2 视口与核心交互，dev/prod preview 均锁定 0 console error/warning 与 0 横向溢出，聚合入口对 route smoke 与 control inventory smoke 传递 `--include-detail-routes`；Chat/Settings/LLM profile mutation、Spotify auth JSON 端点、AI Insights 生成端点、Import job 调度和 Spotify OAuth PKCE 本地闭环已用 contract 临时环境验证；修复 Spotify 当前播放 token refresh 写连接边界、OAuth login 未配置 Client ID 500、Settings 越界配置/清翻译缓存缺表、Provider 异常泛化 500、封面回退查询 schema mismatch 500、Billboard enrichment Wiki lookup 普通异常 500、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON 相关端点缺少 response_model、AI Insights 会话列表嵌套按钮、周快捷项重复 key、音乐详情隐藏 tab 图表零尺寸 warning、Billboard/Records/AllTime/WeekSelector/音乐详情分页图标按钮与 Settings Slider 内部输入控件缺少可访问名称问题
  - 2026-06-19 交互 smoke 补强：`scripts/frontend_interaction_smoke.mjs` 默认覆盖 6 个非破坏性场景，新增 `settings-data-import`，AI Insights 会读取 `/api/settings` 后按 LLM 已配置/未配置分支验证；dev server 与生产 `vite preview` 均已复跑 PASS 6/6
  - 2026-06-19 控件库存 smoke 补强：`scripts/frontend_control_inventory_smoke.mjs --include-detail-routes` 覆盖 13 个默认路由 + 5 个动态详情路由 × 桌面/390px 移动端，检查可见交互控件缺少可访问名称、嵌套交互控件、disabled 仍可 tab、输入控件无标签和重复 id；dev server 36 组合 / 1821 控件 / 0 violation，生产 `vite preview` 36 组合 / 1763 控件 / 0 violation
  - 2026-06-19 跨浏览器 smoke 补强：`scripts/frontend_cross_browser_smoke.mjs` 的 `core-interactions` 也覆盖同一组 6 个核心交互；dev server 完整 route-marker + core-interactions 与生产 `vite preview` core-interactions 均已在 Chromium/Firefox/WebKit PASS 3/3
  - 2026-06-20 fix 分支跟进：在 `fix/bugfixes-and-polish` 上修复旧 `/analysis/*` 别名嵌套在 lazy `AnalysisLayout` 内导致的冷导航空壳风险；首页 Dashboard 月度趋势按产品偏好保留 ECharts 视觉，并通过 `MonthlyTrendChart` lazy wrapper + `MonthlyTrendEChart` 动态块隔离 ECharts runtime，production preview 首页 desktop LCP 2004ms / CLS 0 / TBT 0ms、mobile LCP 544ms / CLS 0 / TBT 0ms；账号页新增轻量 `/profile` 首屏 Hero 查询，`/api/account` 聚合加入 TTL cache + warmup，production `/account` desktop LCP 从 3532ms 降至 468ms；根级 `scrollbar-gutter: stable` 将 `/billboard/number-ones` desktop CLS 从 0.1 压到 0；Spotify OAuth 在 ngrok `SPOTIFY_REDIRECT_URI` 且未显式设置 `FRONTEND_ORIGIN` 时，callback 回跳 origin 会从 redirect URI 推导，避免授权后掉回 localhost；图表交互 smoke 默认冷态等待调至 12s，避免 Vite dev 懒加载 ECharts chunk 误报；前端 CDP smoke 共享浏览器查找 helper，默认优先 Playwright `chromium_headless_shell-*`、Chrome for Testing，系统 Chrome 后置兜底；完整 fullstack verification 已覆盖 backend full、pre-commit、Phase 5、OpenAPI/API probes、benchmark、route/interaction/chart/control/long-list/cross-browser smoke 并通过；2026-06-21 复核固定域名 ngrok HTTPS tunnel 已可建立，外部 health、Spotify login URL、invalid-state callback 回跳和 auth data 入口通过；2026-06-28 用户已在真实浏览器完成人工 Spotify consent，授权后外部探针 PASS
  - 2026-06-27 社区榜单口径同步：Community feed/trending/post detail 改用 `BillboardFilters` + `MergeConfig`，前端通过 `useCommunityChartParams()` 把设置页的 Top N、周起点、动态阈值、合并级别和是否包含精选集带入社区列表/账号页/详情页，避免社区动态继续按旧硬编码榜单口径生成；`PostCard` 封面尺寸同步收紧，单图 160px、多图网格 320px
  - 2026-06-27 验收补强：OpenAPI 参数边界审计解包 nullable schema，`max_merge_gap_minutes` 纳入边界 probe；播放排行 track 行补回 `album_name`，避免音乐详情链路生成空专辑路径；Year-End staged wrapper 拆入独立模块，保持 staged public API facade 行数护栏；route/control/cross-browser smoke 对冷态重页面与动态详情路由使用分层等待，chart smoke 的 legend 场景改用稳定音乐详情 ECharts，long-list smoke 对 Year-End 单页 50 行封顶表格走 capped 验收；Web Vitals probe 对单次 lab 预算失败样本复测一次，降低 CLS 噪声误杀；fullstack benchmark 在本地 127.0.0.1 检查时清空代理变量，避免 SOCKS 环境污染；固定域名 ngrok HTTPS + Spotify auth status/data/login/invalid-state callback 已复核可达，2026-06-28 用户人工 consent 成功并经外部探针复核
  - R24b 不变式合约测试：`test_playback_invariants.py`（6 条断言）+ `test_merge_level_aggregation.py`（14 条断言）+ `test_playback_filter_parameter_propagation.py`（过滤参数传播）
  - 测试基线：AI Agent Harness Quality Roadmap 后本地 unit 432 / contract 223 / frontend 217；`npm run build`、OpenAPI operation/parameter audit、API smoke/boundary、AI Insights interaction smoke、`/ai-insights` control inventory smoke 与真实浏览器思考模式问答已通过；Phase 5 既有完整验证矩阵仍以 `scripts/fullstack_verification_check.sh` 为发布前门禁

详见 `docs/reference/playback-stats-rules.md`、`docs/archive/02-react-productization/2026-06-08-phase5-baseline.md`、`docs/reports/2026-06-19-fullstack-verification.md` 和 `docs/reports/2026-06-20-fix-branch-follow-up.md`。

## 常用命令

```bash
# 启动后端（只监听 backend/，避免扫描 .venv/node_modules/data）
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend

# 关闭预热冷启动
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend

# 前端开发
cd frontend && npm run dev

# 一键启动冒烟（自动启动/复用后端 8000 + 前端 5173，验证 health/docs/前端壳/API 代理后清理，并输出时序 JSON）
.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json

# 修复已导入 Streaming History 后缺失的 Spotify 元数据、album projects 与榜单聚合
.venv/bin/python scripts/refresh_import_derived_data.py --json-output /tmp/spotify_import_maintenance.json

# ngrok HTTPS 隧道（Spotify OAuth 回调需要）
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

# ngrok tunnel 建立后，非破坏性验证外部 OAuth 初段/回跳（不交换真实授权 code）
.venv/bin/python scripts/spotify_oauth_external_probe.py --json-output /tmp/spotify_oauth_external_probe.json

# 测试（三层：unit / contract / integration）
source .venv/bin/activate && pytest backend/tests/ -v
source .venv/bin/activate && pytest -m unit -v         # ~5秒，无 DB
source .venv/bin/activate && pytest -m contract -v      # ~1秒，seed DB
source .venv/bin/activate && pytest -m integration -v   # ~80秒，只读生产DB

# 前端测试（含架构护栏测试）
cd frontend && npm test

# 代码质量
ruff check backend/
ruff format --check backend/
pre-commit run --all-files

# Phase 5 最低验证矩阵
sh scripts/phase5_check.sh
.venv/bin/python scripts/ci_baseline_parity.py

# AI 问答矩阵检查（static 不调用 LLM；live 模式需后端 8000 与 LLM 已配置）
.venv/bin/python scripts/evaluate_ai_question_matrix.py
.venv/bin/python scripts/evaluate_ai_question_matrix.py --mode changed --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00
.venv/bin/python scripts/evaluate_ai_question_matrix.py --mode full --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00

# 全栈非破坏性验收矩阵（需后端 8000 + 前端 5173 已启动；资源数量/体积预算需同时启动 preview 4173）
# 跨浏览器 smoke 会自动检测可 import playwright.sync_api 的 Python，也可显式设置 PYTHON_PLAYWRIGHT
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing.json --web-vitals --resource-snapshot --resource-max-total-rss-mb 1200 --resource-max-total-cpu-percent 200 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000 --web-vitals-max-scroll-overflow-px 0

# 本地只读 API smoke（101 个 GET，验证 X-Request-ID，并核算 OpenAPI GET 覆盖）
.venv/bin/python scripts/api_smoke_probe.py

# 非破坏性 API 边界 probe（95 个 GET，验证 422/200、X-Request-ID 与 validation detail）
.venv/bin/python scripts/api_boundary_probe.py

# OpenAPI 全操作覆盖归属核算（144 operation，0 unaccounted）
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json

# OpenAPI 参数边界覆盖归属核算（64 obligations，0 unaccounted）
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json

# API 性能 benchmark（需后端 8000 已启动；输出冷/热响应、体积、慢端点汇总）
.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json

# 本地服务 CPU/RSS 快照（需后端 8000 + 前端 5173 已启动；输出进程树 CPU/RSS）
.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173 已启动）
node scripts/frontend_route_smoke.mjs --viewport matrix --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node scripts/frontend_interaction_smoke.mjs --viewport mobile --scenario mobile-bottom-navigation,mobile-section-sheet,mobile-time-filter
node scripts/frontend_chart_interaction_smoke.mjs --viewport mobile --scenario mobile-tap-tooltip,mobile-fullscreen
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport both --include-detail-routes
node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --include-detail-routes
node scripts/frontend_long_list_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_cross_browser_smoke.mjs --base-url http://localhost:5173 --include-detail-routes
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --include-detail-routes
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0

# 其他
cd frontend && npm run build          # 生产构建
cd frontend && npx shadcn@latest add <component-name>
```

## Git 提交规范

```text
<type>: <中文概括标题>

- 后端/数据层改动：说明新增或调整的 API、服务、缓存、数据库或计算口径
- 前端/UI 改动：说明新增页面、路由、组件、交互和视觉结构
- 性能/稳定性改动：说明缓存、预热、请求复用、错误回退或兼容迁移
- 测试验证：说明新增/更新的测试，以及实际跑过的验证命令或结果
- 文档同步：说明 README、CLAUDE、UI 指南等是否已同步
```

标题使用 conventional commit 前缀（`feat:`/`fix:`/`perf:`/`docs:`），正文 4-7 条中文 bullet。提交前先看 `git log --format=fuller -n 5` 保持粒度和措辞一致。

---

## 架构

### 数据流

```
JSON 导出 ──→ import_data.py ──→ SQLite (spotify_stats.db) ──→ FastAPI backend/ ──→ React frontend/
                                         │
账号数据 ──→ import_account_data.py ─────┘
```

### 后端架构 (backend/)

四层分离：**api/**（路由 + Depends 依赖注入）→ **services/**（计算逻辑，`@lru_cache`）→ **domains/**（领域模块：billboard / playback / settings / enrichment / community / chat / ai_agent / ai_tasks）→ **core/**（db, utils, cache, config, crypto, json_helpers）

**基础设施**：`infrastructure/http/` 统一 HTTP 客户端（timeout/retry/proxy/脱敏）；`providers/` 封装所有第三方 API（spotify / genius / wikipedia / llm），禁止业务代码散落请求逻辑。

**路由层关键约定**：
- `backend/dependencies.py`：`PlayFilters`（标准播放过滤）、`BillboardFilters`（继承 + Billboard 参数）、`get_conn()`（数据库连接注入）
- 使用 `PlayFilters` / `BillboardFilters` 的端点必须把 `dynamic_threshold` 与 `max_merge_gap_minutes` 传入最终 `load_plays()` / `load_billboard_raw()` 路径；Community feed/trending/post detail 也必须使用 `BillboardFilters` + `MergeConfig`，并把 `merge_level` / `include_compilations` 纳入生成参数和 query key；新增统计端点必须补传播测试或复用已有管线
- API 层通过 `Depends(get_conn)` 注入连接，请求结束自动关闭
- 非缓存服务接收 `conn` 参数从 API 层传入
- 缓存服务（`@lru_cache` / `@ttl_cached`）内部调用 `get_db()`（连接不可哈希）
- FastAPI `:path` 贪婪匹配，含子路径路由注册在泛化路由之前

**核心模块速览**：

| 文件 | 职责 |
|------|------|
| `core/db.py` | `get_db()`, `load_plays()` / `load_plays_for_artists()` (`@lru_cache` + `singleflight`), `base_filters()`, `merge_consecutive_plays()`, `build_aggregations()` |
| `core/config.py` | 所有环境变量集中管理（`python-dotenv`），禁止业务代码直接 `os.getenv()` |
| `core/crypto.py` | AES-256-GCM 加解密，Token 落库前必须加密 |
| `core/json_helpers.py` | numpy/pandas → JSON 唯一入口，禁止 service 层重复定义 |
| `core/cache.py` | `ttl_cached()` 装饰器（不缓存 None）+ `singleflight()` |
| `core/cache_manager.py` | 5 命名空间统一管理，设置/导入/版本合并变更自动失效 |
| `core/migrations.py` | SQLite 版本化 Migration，`IF NOT EXISTS` 保证幂等 |
| `core/auth.py` | `require_auth()` 依赖，本地模式放行，远程模式校验 Bearer Token |
| `core/logging_config.py` | `SensitiveDataFilter` 脱敏 API Key/Token，全局 500 不泄露 stack trace |
| `core/request_context.py` | Request ID 上下文，响应返回 `X-Request-ID`，日志包含 request id |
| `core/spotify_utils.py` | OAuth PKCE + Token 加密持久化 + 自动刷新（HTTP 已收敛到 HttpClient） |
| `services/play_service.py` | 核心播放数据服务，所有基于 plays 的端点统一入口 |
| `services/wrapped_service.py` | 自定义年度总结（听歌人格/Top榜/曲风全景/发现回归等） |
| `services/billboard_service.py` | Billboard facade（~100行），实现已迁入 `domains/billboard/` |
| `services/ai_task_service.py` | AI task 编排：报告 cache check/manual generation、艺人/专辑 enrichment、任务状态与事件持久化 |
| `services/ai_agent_service.py` | 只读 Agent 问答：工具规划、allowlist 执行、compact evidence、证据充分性复核、分析底稿、answer obligations、回答契约 critic 与回答重试 |
| `services/chat_service.py` | 对话历史管理：会话 CRUD + 消息持久化 + 自动标题 |
| `services/spotify_auth.py` | OAuth PKCE 授权与数据同步 |

详细后端架构见 `backend/CLAUDE.md`。

**测试分层**：`unit/`（纯函数，无 DB）→ `contract/`（seed DB 结构验证）→ `integration/`（真实数据只读）。Contract 测试 teardown 清除所有 `@lru_cache` 防止污染。

### 前端架构 (frontend/)

React 19 + TypeScript 6.0 + Vite 8 + Tailwind CSS v4 + shadcn/ui (base-nova) + React Router v7 + TanStack React Query + ECharts 6。

**目录结构**（Phase 5 拆分后）：

```
frontend/src/
├── api/              ← 类型化 API 客户端 + TanStack QueryClient + Query Key 工厂 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件
│   ├── billboard/
│   │   ├── number-ones/   ← NumberOnesExperience + 3 Section（tracks/albums/artists）+ Primitives + Data
│   │   ├── records/       ← RecordsSections + 6 Section（Championship/Longevity/Market/Breakthrough/HallOfFame/Curiosities）+ Primitives + Data
│   │   └── all-time/      ← AllTimeTable + Data
│   ├── community/         ← CommunityExperience/Account + FeedToggle + TimeFilter + PostCard + Timeline + Sidebar + PostDetailExperience + MobileSidebarDrawer + Data
│   ├── music/details/     ← Artist/Album Experience + Header/Tabs + Skeletons + Overview/Tracks/Albums/Career/ArtistReleases/AlbumEra 子 sections + ReleaseCycle sections + Primitives
│   ├── music/search/      ← Masthead 快速搜索 + `/music/search` 全页查找 + 结果分组渲染
│   ├── ai-insights/        ← AiInsightsExperience + ReportsPanel + ReportCard + ChatInterface + ChatComposer + ChatSessionList + ChatSessionDrawer + SuggestedQuestions + Primitives + Data
│   ├── ai-tasks/           ← AITaskProgress + AIToolTrace + AIResultShell，共享 AI task 进度/结果/工具轨迹 UI
│   ├── settings/components/  ← 7 配置 Section 组件
│   └── account-archive/      ← 音乐档案共享数据层 + Desktop/Compact/Phone 独立 presentation
├── components/
│   ├── ui/            ← shadcn/ui 组件
│   ├── charts/        ← LazyEChart 按需 ECharts 封装 + 纯 DOM 图表
│   ├── layout/        ← AppLayout, Masthead, ThemeToggle
│   └── shared/        ← GlassCard, KpiCard, CoverCell, FormattedText 等
├── pages/             ← 路由级页面容器（React.lazy 分包，≤450 行，纯组合 feature 组件）
├── hooks/             ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount, useCommunity, useAiTasks（均用 useQuery）
├── lib/               ← 工具函数（cn, chinese, insights, theme, personality-themes, genre-regions）
├── tests/             ← 含 phase5-architecture.test.ts 架构护栏测试
└── types/             ← 手写 TypeScript 展示类型
```

**路由**：`/` → `/analysis/stats|charts` → `/yearly-review` → `/billboard` → `/community` → `/ai-insights` → `/account` → `/settings`；音乐查找 `/music/search`；音乐实体详情 `/music/{tracks|albums|artists}/:id`；社区 `/community/account/:handle`（账号页）+ `/community/post/:postId`（帖子详情）；旧 `/billboard/track|album|artist/*` 仅兼容跳转。

**Phase 5 架构模式**（新增组件必须遵守）：

| 层级 | 位置 | 行数上限 | 职责 |
|------|------|---------|------|
| Route Container | `pages/` | ≤450 | 数据获取 + 组合 feature 组件，不含 `<table>`/`function KpiCard` 等实现细节 |
| Experience | `features/*/XXXExperience.tsx` | 目标 ≤450 | 编排子组件，管布局和数据流；音乐详情仍在按 section 逐轮收敛 |
| Section | `features/*/XXXSection.tsx` | ≤300 | 单个业务模块渲染 |
| Primitives | `features/*/XXXPrimitives.tsx` | ≤350 | 跨 Section 共享的 UI 零件（KpiCard, CoverCell 等） |
| Data | `features/*/xxxData.ts` | — | 纯函数，计算逻辑与 UI 完全分离 |

**关键约定**：
- 外部文本渲染必须经 `react-markdown` + `rehype-sanitize`，禁止 `dangerouslySetInnerHTML`；AI 报告/问答正文统一复用 `features/ai-insights/AiMarkdown.tsx`，保留 GFM 表格但必须包裹横向滚动容器
- 后端 SQLite 风格时间戳（`YYYY-MM-DD HH:mm:ss`）默认按 UTC 解析；对话历史等相对时间必须通过 `frontend/src/lib/datetime.ts` 的 `formatRelativeTimeZh()`，避免本地时区偏移
- LLM API Key 永远不通过 API 返回前端，仅返回 `has_llm_key: bool`
- OpenAPI 类型通过 `npm run generate-types` 从后端自动生成
- ECharts 图表必须复用 `LazyEChart`，禁止直接 `import('echarts-for-react')` 默认入口；新增图表能力先扩展共享 wrapper
- 简繁转换必须通过 `displayName()` / `chinese.ts`，禁止直接导入默认 `opencc-js` full 包，也禁止在模块初始化时根据已保存偏好 eager-load 大字典
- **新增 GET hook 必须使用 `queryKeys` + TanStack Query**，禁止新增模块级数据缓存
- 模块级变量只允许保存 tab/排序/页码等 UI 状态（如 `let cachedTab`、`let cachedSortKey`）
- **禁止模块级 `new Map()` 缓存 API 响应**，详情页 enrichment/release-cycle 数据必须走 Query Client
- 页面容器禁止包含 `<table>`、`function KpiCard`、`function No1BarChart` 等直接实现——这些必须放在 features/
- 架构护栏测试（`phase5-architecture.test.ts`）使用 `?raw` import + 负面断言强制执行上述约束
- 路径别名 `@/` → `src/`

详细前端架构见 `frontend/CLAUDE.md`。

### 数据库

维度表 `artists` → `albums` → `tracks`，事实表 `plays`（预计算 `ts_year/month/week/dow/hour/date`，均为北京时间 UTC+8）。`plays.spotify_track_id_at_play` / `spotify_album_id_at_play` 保留播放当时的 Spotify 归属，`track_albums` 处理同曲多专辑关联。Spotify 元数据独立存储在 `spotify_*_meta` 表，`album_spotify_links` 记录本地 album 到 Spotify album 的证据链接。`release_groups` + `release_group_members` 管理专辑版本合并。

账号数据表独立：`saved_tracks/albums/artists`、`playlists`、`search_queries`、`podcast_*`、`user_*`、`marquee_impressions`、`wrapped_*`、`banned_items`。

### 数据过滤策略

`base_filters()` 是 SQL 粗过滤入口：`music_only` 排除播客；未合并路径直接应用 `ms_played >= min_ms`。合并连续播放（`merge_enabled`，默认开启）使用 `min_ms=0` 先保留短片段，按 `track_id` + `source_album_id` + 可选 `max_merge_gap_minutes` 合并，再由 `filter_effective_plays()` 应用固定阈值或动态阈值。已移除不可靠的 `skipped` 过滤。

特殊页面例外：行为分析使用全量数据；播客/视频额外 `>= 30000ms`；Billboard 专辑榜排除 singles 和发前周。L2/L3 album statistics 必须使用 album project track membership，不得回退到 source album 行聚合；source album attribution 只通过 source breakdown 解释统计来源。

---

## 技术约束

- Python 3.9：使用 `Optional[X]` 而非 `X | None`
- 后端绝对导入：`from backend.core.db import get_db`
- SQLite `data/spotify_stats.db`，由 `.gitignore` 排除
- Streaming History 导入必须在 job `done` 前运行元数据刷新、album project rebuild、聚合重建和缓存失效；`maintenance_status=partial` 不代表基础播放导入失败
- `ttl_cached()` 不缓存 `None`，`cache_clear()` 必须同时清空条目并重置 hit/miss 统计
- 昂贵缓存优先通过公开 wrapper 规范化参数 + `singleflight()` 避免并发重复计算
- Spotify OAuth 开发需要 HTTPS，用 ngrok 静态域名代理
- LLM API Key 加密存储，前端永远不可见明文
- Token 加密密钥优先级：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥（仅限单用户本地）
- **业务层新增外部 HTTP 调用必须走 Provider/HttpClient**；service 层和 core Spotify 路径不得直接 `urllib.request.Request`/`urlopen`
- **新增 GET hook 必须使用 TanStack Query + `queryKeys`**；禁止模块级 `new Map()` 数据缓存
- **页面容器只做路由入口**，业务逻辑和渲染细节必须在 `features/` 中
