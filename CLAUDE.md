# CLAUDE.md

> 完整项目上下文见 `AGENTS.md`。本文档保留常用命令、核心约束和架构要点作为速查。

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用 — **FastAPI 后端 + React 前端**。Streamlit `app/` 自 2026-05-30 冻结维护。

UI：「编辑风 × 液态玻璃」— Playfair Display + Inter，毛玻璃，日/夜双皮肤。

**Phase 5 基线**：前端 GET 统一 TanStack Query（11 命名空间 queryKeys）；Provider 错误分层；业务 service 层 urllib 清零；模块级 API Map 缓存清除；Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线；`records.py` 88 行 facade；`chart_compute.py` 211 行 facade；Request ID 链路；架构护栏 105+ 测试 + CI 基线。2026-06-12 Phase 5.4-A~H 全系列完成：TrackDetail (574→5 行)、HabitsTab (933 行→9 文件 feature)、AI Insights 拆分、24 端点 response_model 硬化、Bundle 懒加载治理（Settings -88%、Records -69%、Account -34%）、TrackDetail 歌词 Query 漏网修复。播放统计规则引擎（Phase C+D，2026-06-18 贯穿修复）：Session 边界检测（`max_gap_minutes` + `boundary_column`）、动态阈值、Track Groups 三级合并（L1/L2/L3 recording/composition scope）、Album Projects 专辑项目统计（L2/L3 使用 track membership，source album 仅作 breakdown，Billboard 按 release_date 排除发行前周）、`MergeConfig` FastAPI 依赖、Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Release Cycle 统一传递过滤参数、R24b + 过滤传播合约测试。2026-06-19 全栈验证与性能收口：Billboard load/rank 共享缓存拆入 `chart_load_rank.py`，Power Score、summaries 与 `merge_consecutive_plays` 向量化，Dashboard full 复用同一播放 DataFrame，AI Insights 报告/问答透传当前播放过滤口径并按过滤指纹分流缓存，Behavior 全量事件分析只暴露/请求 `music_only`，专辑详情来源拆分批量化，默认 warmup 改为当前动态阈值口径并预热 artist fan-out，移动端页面级横向滚动归零，pre-commit ruff 范围收敛到 backend，OpenCC/ECharts 大依赖改为按需子包与 `LazyEChart` core 入口，账号页资源加载收敛并补 dev/prod-preview Web Vitals lab 探针，新增 91 请求本地只读 API smoke 探针、19 个非破坏性 API 边界 probe、OpenAPI GET 覆盖核算、26 组合 route smoke 探针（默认 5s + 业务内容 marker，dev/prod preview 均通过）、4 场景前端交互 smoke 探针（分析 tab、Billboard 子路由/前进后退、AI Insights tab/空状态、主题切换）、3 场景 ECharts 图表交互 smoke 探针（tooltip/legend/dataZoom，dev/prod preview 均通过）、6 场景长列表分页/分段渲染 smoke 探针与 Chromium/Firefox/WebKit 跨浏览器 smoke 探针，Chat/Settings/LLM profile mutation、AI Insights 生成端点、Import job 调度和 Spotify OAuth PKCE 本地闭环 contract 覆盖，修复 Spotify 当前播放 token refresh、OAuth login 未配置 Client ID 500、Settings 越界配置、清翻译缓存缺表、AI Insights 报告缓存 readonly 写入 warning、会话列表嵌套按钮、周快捷项重复 key 和音乐详情隐藏 tab 图表零尺寸 warning 问题。详见 `AGENTS.md`、`docs/2026-06-18-playback-stats-rules-latest.md` 和 `docs/2026-06-19-fullstack-verification-performance-report.md`。

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

# 本地只读 API smoke（91 个 GET + OpenAPI GET 核算）
.venv/bin/python scripts/api_smoke_probe.py

# 非破坏性 API 边界 probe（19 个 GET）
.venv/bin/python scripts/api_boundary_probe.py

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173）
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000

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
- **简繁转换 → `displayName()`；禁止直接导入默认 `opencc-js` full 包**
- 账号页长图片列表必须有预览上限或分页，并使用 `loading="lazy"` / `decoding="async"`
- **新增外部 HTTP 调用 → Provider/HttpClient；禁止直接 `urllib.request.Request`/`urlopen`**
- **页面容器只做路由入口；业务逻辑在 `features/`**
- 架构护栏测试 `phase5-architecture.test.ts` 对上述约定做负面断言强制执行
- 使用 `PlayFilters` / `BillboardFilters` 的统计端点必须透传 `dynamic_threshold` 与 `max_merge_gap_minutes` 到最终计数管线；新增入口要补传播测试或复用已有 service

完整架构、模块表、数据库结构、过滤策略见 `AGENTS.md`；后端细节见 `backend/CLAUDE.md`；前端细节见 `frontend/CLAUDE.md`。
