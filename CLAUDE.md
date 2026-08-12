# CLAUDE.md

年度生成协调：在既有年度只读报告 API 外，新增 `/api/yearly-review/prewarm` 与 `/api/yearly-review/generation-status`。`yearly_review_generation_v1` 使用单工作线程优先级队列与 exact cache key 去重，当前年优先、其余可用年份从近到远后台预建，切年提升 queued 任务，等待时间使用服务端 `requested_at`，缓存命中不得被其他年份冷构建阻塞。前端离开页面只取消 HTTP 等待，不终止后台任务；Desktop/Compact/Phone 自定义总结共用批量预建，Official Wrapped 不触发。

> 完整项目上下文见 `AGENTS.md`。本文档保留常用命令、核心约束和架构要点作为速查。

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用 — **FastAPI 后端 + React 前端**。

UI：「编辑风 × 液态玻璃」— Playfair Display + Inter，毛玻璃，日/夜双皮肤。

导航命名：顶级入口使用“播放分析”；二级 tab 固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 账号中心”。年度总结与账号中心保持在播放分析 tab 行内，避免恢复独立顶级入口或重复下拉入口。

年度总结 V2：`/yearly-review` 的 Desktop/Compact 与 Phone 自定义总结共享确定性八章数据、过滤指纹、coverage、缓存和生成任务，但使用互斥的独立 presentation；桌面是完整杂志年鉴，Phone 是“口袋音乐年鉴”、2×3 KPI、章节进度 Sheet、纵向时间线和无宽表全屏榜单。官方 Wrapped 保持独立。V2 通过 `/api/yearly-review/available-years|{year}|{year}/records` 消费统一过滤指纹、coverage、策略与元数据 revision；播放/时长榜和个人 Billboard 必须明确区分，月度正文只有一条转折时间线，十二月明细按需展开。同比使用真实 aligned window，工作日/周末使用自然日日均，Passport 使用规范实体粒度，YTD 品味只比较完整季度；公开纪录、阶段和结语均受显式证据规则约束。消费 UI 不展示口径、指纹、策略、证据等级、coverage 或 limitations，只使用普通用户文案；六项 KPI 只显示红/绿箭头与百分比，实体故事和完整榜单优先显示封面/深链，大标题无解释性 subtitle。年份升序排列并默认最近完整年度；完整年度封面隐藏状态/日期，进行中保留截止日期；封面三条头条与海报功能均不展示。新关系标题必须区分歌曲、专辑、艺人；同专辑/艺人多首入榜必须显示准确曲目数；宽屏分歧故事使用两列，窄屏回到单列。年度纪录只展示精选集合，不提供完整目录展开；兼容 records API 只返回同一精选集合，artifact 不再序列化全部候选。桌面章节间距使用统一紧凑节奏；Phone 触控目标至少 44×44px，榜单正文 Top 5、全屏每页 10 条并恢复关闭焦点。LLM 不生成年度事实。schema/content version 分开治理，统计、编排或公开展示语义变化必须提升 content version。当前 content 为 v2.11；v2.8 四年性能基线为真实重算 10.65–16.54s、热响应 26.56–29.85ms、跨进程持久命中 10.20–21.07ms，probe v5 同时锁定公开文案、封面/深链、YTD 措辞、精选证据、结语去重与阶段状态，详见 `docs/reports/2026-08-12-yearly-review-v2-delivery.md`。

移动网页架构：`<768px` 使用独立 Phone presentation，`768–1023px` 为 Compact，`>=1024px` 使用 Desktop；Phone/Desktop 的重图表、宽表与长列表必须互斥挂载，但继续共享 Route Container、React Router URL 状态、TanStack Query、过滤指纹、row model 和统计事实。Phone Shell 固定使用 `MobileTopBar`、五项 `MobileBottomNav` 与播放分析/Billboard `MobileSectionSwitcher`；Push 详情按路由语义隐藏 Bottom Nav。主要移动触控目标至少 44×44px，关键操作不得依赖 hover，复杂图表需提供触摸 disclosure 与可恢复焦点的全屏模式。Settings 手机端只开放低风险日常设置；导入、元数据治理、凭据和系统维护保留桌面工作台。新增消费页面必须通过 360/390/430/768/1280 route matrix、移动 control inventory、interaction/chart、long-list 与 Chromium/Firefox/WebKit 门禁。完整规范见 `frontend/UI_STYLE_GUIDE.md` 和 `docs/plans/2026-08-05-mobile-web-design-and-implementation-plan.md`。

PWA/App 基线：生产构建通过 `/manifest.webmanifest`、PWA 图标和 `/sw.js` 提供安装能力，开发模式不注册 Service Worker；手机 Settings 安装卡支持 Chromium prompt、iOS 添加到主屏幕说明与 standalone 状态。Service Worker 只能缓存离线说明、PWA 图标和版本化静态资产，必须绕过 `/api`、`/covers` 与个人/凭据数据。路线按 PWA → HTTPS 安全部署与真机 → Capacitor 推进，见 `docs/plans/2026-08-06-appification-pwa-capacitor-plan.md`。

音乐查找：Masthead 右侧提供全局搜索图标，`/music/search` 提供可分享的完整查找页；后端 `/api/music/search` 只搜索本地播放历史中的歌曲/专辑/艺人，并打开既有 `/music/{tracks|albums|artists}/...` 详情页。`include_chart=true` 时返回与详情页同口径的个人 Billboard 摘要，前端仅显示播放次数、`PK #`、在榜周数与走势排名；搜索弹层默认不高亮第一条结果。

Billboard 对决：单曲、专辑、艺人对决及 entity lists 必须与详情页共享完整统计上下文（动态阈值、连续播放间隔、合并级别、榜单周边界、三类 Top N、年份范围、精选集设置），前端 query key 必须包含完整过滤指纹。专辑曲目归属复用详情的 album project + canonical artist 口径，艺人歌曲成绩复用 credited artist fan-out 并按 stable event + canonical artist 去重。

Billboard 总榜：专辑成员歌曲及艺人歌曲/专辑的跨层级走势点数统一走 `cross_level_power.py`；排名基于完整当前同类实体集合，零贡献不排名，客户端搜索、分页和字段配置不得重排。三榜字段配置独立持久化，名称和当前排名固定；实体走势评分与走势排名相邻且均可独立显示。

音乐详情存在资格与成绩：Billboard Top-N 和 versus picker 不是详情页存在条件；当前有效播放口径下有播放或已有榜单事实的歌曲、专辑、艺人均可打开详情。详情固定 Tab 始终存在，`chart_status` 仅描述实体自身榜单；专辑和艺人的单曲/专辑子成绩使用独立状态与空态，专辑自身入榜不得依赖成员歌曲入榜。真正无有效播放且无法解析的请求才返回 404。

曲风与语言消费层：底层 `style/scene/context/role` 四轴 facts 与 Settings 治理保持不变；年度总结通过版本化 `genre_display_taxonomy.py` 只展示“主曲风 / 地区流行 / 语言”，unknown 使用“尚未归类”，不展示审核、证据、置信度或内部 ID。`context/role` 与 Music Map heuristic 不进入年度消费页，播放统计页也不放曲风/语言模块。Wrapped、AI 报告缓存需包含 display taxonomy 与艺人元数据 revision。

**当前状态**：Phase 5 产品化收口完成 + AI Observable Agent Orchestrator V2。AI 报告已改为缓存优先、手动生成并显示任务进度；年度叙事默认走 `visual_yearly_artifact` + `writer_pipeline=agent_synthesis_v2`，在只读 Report Agent 证据、deterministic chart data builder 和 fact validator 基础上用 `report_agent.py` Agent 多轮工具调用（含 web_search）+ 直接写报告，图表数据仍由确定性后端生成；保留 `_compose_sections()` 确定性 fallback 作为安全网；年报和 Chat 默认启用 DeepSeek 思考模式；`agentic_longform`、`basic_summary` 和 `editorial_agent_v1` 保留为兼容/回退模式。AI 问答通过后端只读 Agent 工具查询数据，支持思考模式、工具轨迹、coverage 自检、answer obligations、矛盾回答重试，以及账号收藏/搜索历史/社区数据域工具；相对时间会以 `question_time`/`timezone` grounding，并把 temporal guard 校正后的 custom range 投影到 EvidenceRecipe/AnalyticalBrief；艺人与专辑详情 enrichment 已接入可观察任务。当前本地验证基线随迭代变化，AI harness 定向基线见 `docs/reports/2026-07-03-ai-question-matrix-test-report.md`，年度图文报告回归可用 `scripts/probe_visual_yearly_report_artifact.py --mode changed`，大范围 live 问答回归可用 `scripts/evaluate_ai_question_matrix.py --mode changed|full`。开发台账与验证细节见 `AGENTS.md`、`docs/plans/`、`docs/reports/`、`docs/designs/` 和 `docs/CHANGELOG.md`。

## 常用命令

```bash
# 后端（只监听 backend/）
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend
# 关闭预热
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend

# 前端
cd frontend && npm run dev

# ngrok（Spotify OAuth 需要 HTTPS）
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173
.venv/bin/python scripts/spotify_oauth_external_probe.py --json-output /tmp/spotify_oauth_external_probe.json

# 测试
source .venv/bin/activate && pytest -m unit -v         # ~5秒
source .venv/bin/activate && pytest -m contract -v      # ~1秒
source .venv/bin/activate && pytest -m integration -v   # ~80秒
cd frontend && npm test

# 代码质量
ruff check backend/ && ruff format --check backend/
pre-commit run --all-files

# Phase 5 验证矩阵
sh scripts/phase5_check.sh
.venv/bin/python scripts/ci_baseline_parity.py

# AI 问答矩阵检查（static 不调用 LLM；live 模式需后端 8000 与 LLM 已配置）
.venv/bin/python scripts/evaluate_ai_question_matrix.py
.venv/bin/python scripts/evaluate_ai_question_matrix.py --mode changed --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00
.venv/bin/python scripts/evaluate_ai_question_matrix.py --mode full --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00

# 全栈非破坏性验收矩阵（需后端 8000 + 前端 5173；资源数量/体积预算需同时启动 preview 4173）
# 跨浏览器 smoke 会自动检测可 import playwright.sync_api 的 Python，也可显式设置 PYTHON_PLAYWRIGHT
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing.json --web-vitals --resource-snapshot --resource-max-total-rss-mb 1200 --resource-max-total-cpu-percent 200 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000 --web-vitals-max-scroll-overflow-px 0

# 一键启动冒烟（自动启动/复用后端 8000 + 前端 5173，验证 health/docs/前端壳/API 代理后清理，并输出时序 JSON）
.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json

# 修复已导入 Streaming History 后缺失的 Spotify 元数据、album projects 与榜单聚合
.venv/bin/python scripts/refresh_import_derived_data.py --json-output /tmp/spotify_import_maintenance.json

# 本地只读 API smoke（101 个 GET + OpenAPI GET 核算）
.venv/bin/python scripts/api_smoke_probe.py

# 非破坏性 API 边界 probe（95 个 GET）
.venv/bin/python scripts/api_boundary_probe.py

# OpenAPI 全操作覆盖归属核算（144 operation，0 unaccounted）
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json

# OpenAPI 参数边界覆盖归属核算（64 obligations，0 unaccounted）
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json

# API 性能 benchmark（需后端 8000 已启动）
.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json

# 本地服务 CPU/RSS 快照（需后端 8000 + 前端 5173 已启动）
.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173）
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
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/analysis/records,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/analysis/records,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/analysis/records,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0

# 其他
cd frontend && npm run build
```

## Git 提交规范

```text
<type>: <中文概括标题>

- 后端/数据层改动：...
- 前端/UI 改动：...
- 性能/稳定性改动：...
- 测试验证：...
- 文档同步：...
```

conventional commit 前缀 + 4-7 条中文 bullet。

## 架构速览

```
JSON → import → SQLite → FastAPI (backend/) → React (frontend/)
```

**后端**：api/ → services/ → domains/（billboard/playback/settings/enrichment/community/chat/ai_agent/ai_tasks）→ core/，辅以 infrastructure/http/ + providers/（spotify/genius/wikipedia/llm）

**前端**：pages/（route container，≤450 行）→ features/（analysis/records/Experience|6 Section|Primitives|Data、billboard/records|number-ones|all-time、community/Experience|Account|FeedToggle|TimeFilter|PostCard|Timeline|Sidebar|PostDetailExperience|MobileSidebarDrawer|communityData、ai-insights/Experience|ReportsPanel|ReportCard|ChatInterface|ChatComposer|ChatSessionList|ChatSessionDrawer|SuggestedQuestions|Primitives|Data、ai-tasks/Progress|ToolTrace|ResultShell、music/details 与 music/search、settings/components、account/collection）→ components/（ui/charts/layout/shared）

**Phase 5 架构模式**：

| 层级 | 位置 | 行上限 | 禁含 |
|------|------|--------|------|
| Route Container | `pages/` | 450 | `<table>`, `function KpiCard` |
| Experience | `features/*/XXXExperience.tsx` | 目标 450 | shared primitives；音乐详情仍在按 section 逐轮收敛 |
| Section | `features/*/XXXSection.tsx` | 300 | — |
| Primitives | `features/*/XXXPrimitives.tsx` | 350 | — |
| Data | `features/*/xxxData.ts` | — | JSX |

## 技术约束

- Python 3.9：`Optional[X]` 非 `X | None`；后端绝对导入：`from backend.core.db`
- SQLite `data/spotify_stats.db`（gitignore 排除）
- `ttl_cached()` 不缓存 `None`；`singleflight()` 防并发重复
- 默认启动 warmup 必须使用当前前端默认过滤口径（`dynamic_threshold=True`，`max_merge_gap_minutes=None`），避免预热旧缓存并与首屏请求抢 CPU
- 环境变量统一 `core/config.py`；禁止业务代码直接 `os.getenv()`
- Token 加密：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥
- Streaming History 导入必须在 `done` 前运行派生数据维护；`maintenance_status=partial` 只表示 Spotify 元数据仍有缺口，不代表基础播放导入失败
- **新增 GET hook → TanStack Query + `queryKeys`；禁止模块级 `new Map()` 数据缓存**
- **ECharts 图表 → `LazyEChart`；禁止直接 `import('echarts-for-react')` 默认入口**
- **简繁转换 → `displayName()`；禁止直接导入默认 `opencc-js` full 包，也禁止模块初始化时预取已保存偏好的大字典**
- 账号页长图片列表必须有预览上限或分页，并使用 `loading="lazy"` / `decoding="async"`
- **新增外部 HTTP 调用 → Provider/HttpClient；禁止直接 `urllib.request.Request`/`urlopen`**
- **AI Agent 工具必须后端 allowlist + read_only**；不得提供任意 SQL、任意 URL、settings/import/cache/playlist 写工具；最终回答只能基于 persisted tool results 和 coverage；曲风/语种问题没有结构化证据时必须保守说明限制
- **艺人语言元数据以 `artist_id` 为主体并独立于 genre**；统计只使用 `tracks.artist_id` 主艺人归属，禁止 track-artist fan-out 或 genre-to-language 推断；legacy、LLM 和未审核 seed 只能 suggested，显式 reviewed seed 仅可在 evidence、`reviewed_by`、`resolution_note` 齐全并通过同一 validator/state machine 时批准，禁止自动猜测批准；只有 approved fact 进入统计，`unknown`、`multilingual`、`instrumental` 与未归属时长必须保留并可审计
- **人工曲目署名不得修改原始事实**；统一使用 `track_credit_overrides`/events/revision 和 `backend/domains/metadata/track_credits.py` resolver，以稳定本地 `artist_id` 保存，先 canonicalize 再按播放事件去重。Settings“音乐源数据管理”是单管理员直接编辑入口，理由/证据不必填，普通修改直接应用而底层 revision/idempotency/undo/rebuild 继续强制；详情页仅精准深链，聚合 revision 落后时必须走实时 resolver，重建失败不得回退旧署名
- **AI 年度叙事 → `visual_yearly_artifact_service.py` + `report_agent.py` + `visual_chart_data.py` + `visual_yearly_critic.py`**；默认年度报告必须返回 `visual_yearly_artifact` 且走 `writer_pipeline=agent_synthesis_v2`，Agent 多轮调用本地数据工具 + web_search 后直接输出报告 JSON（无中间摘要），图表数据只能由 deterministic backend builder 生成；年报和 Chat 默认启用 DeepSeek 思考模式；`editorial_agent_v1` 映射到新路径，旧 `yearly_contract.py` / `yearly_validator.py` / 确定性 fallback 只作为事实安全网和 `basic_summary` 回退
- **页面容器只做路由入口；业务逻辑在 `features/`**
- 架构护栏测试 `phase5-architecture.test.ts` 对上述约定做负面断言强制执行
- 使用 `PlayFilters` / `BillboardFilters` 的统计端点必须透传 `dynamic_threshold` 与 `max_merge_gap_minutes` 到最终计数管线；Community feed/trending/post detail 也必须使用 `BillboardFilters` + `MergeConfig`，并把 `merge_level` / `include_compilations` 纳入生成参数和 query key；新增入口要补传播测试或复用已有 service

完整架构、模块表、数据库结构、过滤策略见 `AGENTS.md`；后端细节见 `backend/CLAUDE.md`；前端细节见 `frontend/CLAUDE.md`。
