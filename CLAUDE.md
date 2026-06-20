# CLAUDE.md

> 完整项目上下文见 `AGENTS.md`。本文档保留常用命令、核心约束和架构要点作为速查。

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用 — **FastAPI 后端 + React 前端**。Streamlit `app/` 自 2026-05-30 冻结维护。

UI：「编辑风 × 液态玻璃」— Playfair Display + Inter，毛玻璃，日/夜双皮肤。

**Phase 5 基线**：前端 GET 统一 TanStack Query（11 命名空间 queryKeys）；Provider 错误分层；业务 service 层 urllib 清零；模块级 API Map 缓存清除；Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线；`records.py` 88 行 facade；`chart_compute.py` 211 行 facade；Request ID 链路；架构护栏 105+ 测试 + CI 基线。2026-06-12 Phase 5.4-A~H 全系列完成：TrackDetail (574→5 行)、HabitsTab (933 行→9 文件 feature)、AI Insights 拆分、24 端点 response_model 硬化、Bundle 懒加载治理（Settings -88%、Records -69%、Account -34%）、TrackDetail 歌词 Query 漏网修复。播放统计规则引擎（Phase C+D，2026-06-18 贯穿修复）：Session 边界检测（`max_gap_minutes` + `boundary_column`）、动态阈值、Track Groups 三级合并（L1/L2/L3 recording/composition scope）、Album Projects 专辑项目统计（L2/L3 使用 track membership，source album 仅作 breakdown，Billboard 按 release_date 排除发行前周）、`MergeConfig` FastAPI 依赖、Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Release Cycle 统一传递过滤参数、R24b + 过滤传播合约测试。2026-06-19 全栈验证与性能收口：Billboard load/rank 共享缓存拆入 `chart_load_rank.py`，Power Score、summaries 与 `merge_consecutive_plays` 向量化，Dashboard full 复用同一播放 DataFrame，AI Insights 报告/问答透传当前播放过滤口径并按过滤指纹分流缓存，Behavior 全量事件分析只暴露/请求 `music_only`，专辑详情来源拆分批量化，默认 warmup 改为当前动态阈值口径并预热 artist fan-out，移动端页面级横向滚动归零，pre-commit ruff 范围收敛到 backend，OpenCC/ECharts 大依赖改为按需子包与 `LazyEChart` core 入口，保存中文显示偏好恢复不再模块级预取 OpenCC 大字典，账号页资源加载收敛并补 dev/prod-preview Web Vitals lab 探针与 LCP/CLS/TBT/资源数量/encoded 体积/横向滚动溢出预算门禁，新增 96 请求本地只读 API smoke 探针、85 个非破坏性 API 边界 probe、OpenAPI 参数边界 audit（59 obligations / 36 boundary_probe / 16 string_resilience_probe / 7 controlled stateful-external / 0 unaccounted）、OpenAPI 134 operation 全量 audit（95 safe GET smoke / 30 targeted contract / 9 controlled stateful-external / 0 unaccounted）、Provider 异常响应分层 contract 护栏、Billboard enrichment 降级 contract 护栏、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON response_model contract 护栏（OpenAPI response_model 缺口 41→1，唯一剩余为 Spotify callback 显式 RedirectResponse，账号中心/画像、Timeline/Listening/Artist/Wrapped、Release Cycle compare 与 Lyrics JSON 发布稳定 schema）、8 端点 API 性能 benchmark 慢端点门禁、48 组合 route smoke 探针（19 主路由 + 5 个动态详情路由 × 2 视口，默认 5s + 业务内容 marker，dev server 与 prod preview 均已通过）、6 场景前端交互 smoke 探针（分析 tab、Billboard 子路由/前进后退、AI Insights 按 settings 分支验证、Settings 控件/数据导入区、主题切换）、3 场景 ECharts 图表交互 smoke 探针（tooltip/legend/dataZoom，dev/prod preview 均通过）、36 组合控件库存 smoke 探针（13 默认路由 + 5 动态详情路由 × 2 视口，dev/prod preview 均 0 violation）、6 场景长列表分页/分段渲染 smoke 探针（dev/prod preview 均通过）、全栈非破坏性验收聚合脚本、GitHub Actions/本地 Phase 5 矩阵 parity 护栏与 Chromium/Firefox/WebKit 跨浏览器 smoke 探针，Chat/Settings/LLM profile mutation、Spotify auth JSON 端点、AI Insights 生成端点、Import job 调度和 Spotify OAuth PKCE 本地闭环 contract 覆盖，修复 Spotify 当前播放 token refresh、OAuth login 未配置 Client ID 500、Settings 越界配置、清翻译缓存缺表、Provider 异常泛化 500、封面回退查询 schema mismatch 500、Billboard enrichment Wiki lookup 普通异常 500、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON 相关端点缺少 response_model、AI Insights 报告缓存 readonly 写入 warning、会话列表嵌套按钮、周快捷项重复 key、音乐详情隐藏 tab 图表零尺寸 warning，以及 Billboard/Records/AllTime/WeekSelector/音乐详情分页图标按钮与 Settings Slider 内部输入控件缺少可访问名称的问题。详见 `AGENTS.md`、`docs/2026-06-18-playback-stats-rules-latest.md` 和 `docs/2026-06-19-fullstack-verification-performance-report.md`。

**最新交互 smoke 口径**：`scripts/frontend_interaction_smoke.mjs` 默认覆盖 6 个非破坏性场景，新增 `settings-data-import`，AI Insights 会读取 `/api/settings` 后按 LLM 已配置/未配置分支验证；dev server 与生产 `vite preview` 均已复跑 PASS 6/6。

**最新 fix 分支跟进**：2026-06-20 在 `fix/bugfixes-and-polish` 上修复旧 `/analysis/*` 别名嵌套在 lazy `AnalysisLayout` 内导致的冷导航空壳风险，并把首页 Dashboard 月度趋势从 ECharts 改为轻量 DOM 条形图，production preview 首页 encoded resources 从约 `1,282KB` 降至 `1,060KB`；账号页新增轻量 `/profile` 首屏 Hero 查询，`/api/account` 聚合加入 TTL cache + warmup，production `/account` desktop LCP 从 `3532ms` 降至 `468ms`；根级 `scrollbar-gutter: stable` 将 `/billboard/number-ones` desktop CLS 从 `0.1` 压到 `0`；图表交互 smoke 默认冷态等待调至 12s，前端 CDP smoke 脚本默认优先使用 Playwright Chromium/Chrome for Testing，避免系统 Chrome 启动阶段崩溃造成假失败。最终验证：backend full 691、unit 320、contract 171、frontend 134、完整 fullstack verification PASS。详见 `docs/2026-06-20-fix-branch-verification-follow-up.md`。

**最新控件库存 smoke 口径**：`scripts/frontend_control_inventory_smoke.mjs --include-detail-routes` 覆盖 13 个默认路由 + 5 个动态详情路由 × 桌面/390px 移动端，检查可见交互控件缺少可访问名称、嵌套交互控件、disabled 仍可 tab、输入控件无标签和重复 id；dev server 覆盖 36 组合 / 1821 控件 / 0 violation，生产 `vite preview` 覆盖 36 组合 / 1763 控件 / 0 violation。

**最新跨浏览器 smoke 口径**：`scripts/frontend_cross_browser_smoke.mjs` 的 `core-interactions` 也覆盖同一组 6 个核心交互；dev server 完整 route-marker + core-interactions 与生产 `vite preview` core-interactions 均已在 Chromium/Firefox/WebKit PASS 3/3。

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

# 全栈非破坏性验收矩阵（需后端 8000 + 前端 5173；可选 --preview-url/--web-vitals/--resource-snapshot）
# 跨浏览器 smoke 会自动检测可 import playwright.sync_api 的 Python，也可显式设置 PYTHON_PLAYWRIGHT
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing.json --web-vitals --resource-snapshot --resource-max-total-rss-mb 1200 --resource-max-total-cpu-percent 200 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000 --web-vitals-max-scroll-overflow-px 0

# 一键启动冒烟（自动启动/复用后端 8000 + 前端 5173，验证 health/docs/前端壳/API 代理后清理，并输出时序 JSON）
.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json

# 本地只读 API smoke（96 个 GET + OpenAPI GET 核算）
.venv/bin/python scripts/api_smoke_probe.py

# 非破坏性 API 边界 probe（85 个 GET）
.venv/bin/python scripts/api_boundary_probe.py

# OpenAPI 全操作覆盖归属核算（134 operation，0 unaccounted）
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json

# OpenAPI 参数边界覆盖归属核算（59 obligations，0 unaccounted）
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json

# API 性能 benchmark（需后端 8000 已启动）
.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json

# 本地服务 CPU/RSS 快照（需后端 8000 + 前端 5173 已启动）
.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173）
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:5173 --viewport both --include-detail-routes
node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --include-detail-routes
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173 --include-detail-routes
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --include-detail-routes
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0

# 其他
cd frontend && npm run build
source .venv/bin/activate && streamlit run app/main.py  # 冻结
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
                              └── Streamlit (app/ 冻结)
```

**后端**：api/ → services/ → domains/（billboard/playback/settings/enrichment/community/chat）→ core/，辅以 infrastructure/http/ + providers/（spotify/genius/wikipedia/llm）

**前端**：pages/（route container，≤450 行）→ features/（billboard/records|number-ones|all-time、community/Experience|Account|FeedToggle|TimeFilter|PostCard|Timeline|Sidebar|PostDetailExperience|MobileSidebarDrawer|communityData、ai-insights/Experience|ReportCard|ChatInterface|ChatSessionList|ChatSessionDrawer|SuggestedQuestions|Primitives|Data、music/details 的 header/primitives/skeletons/overview/tracks/albums/career/artist-releases/album-era 子 sections、settings/components、account/collection）→ components/（ui/charts/layout/shared）

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
- **新增 GET hook → TanStack Query + `queryKeys`；禁止模块级 `new Map()` 数据缓存**
- **ECharts 图表 → `LazyEChart`；禁止直接 `import('echarts-for-react')` 默认入口**
- **简繁转换 → `displayName()`；禁止直接导入默认 `opencc-js` full 包，也禁止模块初始化时预取已保存偏好的大字典**
- 账号页长图片列表必须有预览上限或分页，并使用 `loading="lazy"` / `decoding="async"`
- **新增外部 HTTP 调用 → Provider/HttpClient；禁止直接 `urllib.request.Request`/`urlopen`**
- **页面容器只做路由入口；业务逻辑在 `features/`**
- 架构护栏测试 `phase5-architecture.test.ts` 对上述约定做负面断言强制执行
- 使用 `PlayFilters` / `BillboardFilters` 的统计端点必须透传 `dynamic_threshold` 与 `max_merge_gap_minutes` 到最终计数管线；新增入口要补传播测试或复用已有 service

完整架构、模块表、数据库结构、过滤策略见 `AGENTS.md`；后端细节见 `backend/CLAUDE.md`；前端细节见 `frontend/CLAUDE.md`。
