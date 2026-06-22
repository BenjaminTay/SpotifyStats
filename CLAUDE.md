# CLAUDE.md

> 完整项目上下文见 `AGENTS.md`。本文档保留常用命令、核心约束和架构要点作为速查。

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用 — **FastAPI 后端 + React 前端**。Streamlit `app/` 自 2026-05-30 冻结维护。

UI：「编辑风 × 液态玻璃」— Playfair Display + Inter，毛玻璃，日/夜双皮肤。

**当前状态**：Phase 5 产品化收口完成。后端 694 / 前端 135 测试 PASS，全栈 smoke (48 route + 6 interaction + 3 chart + 36 control + 6 long-list + 3 cross-browser) 全部通过，OpenAPI 134 op / 59 parameter boundary 0 unaccounted。开发台账与验证细节见 `AGENTS.md`、`docs/productization/`、`docs/verification/` 和 `docs/CHANGELOG.md`。最终交付报告见 `docs/productization/2026-06-22-phase5-delivery-report.md`。

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

# 全栈非破坏性验收矩阵（需后端 8000 + 前端 5173；资源数量/体积预算需同时启动 preview 4173）
# 跨浏览器 smoke 会自动检测可 import playwright.sync_api 的 Python，也可显式设置 PYTHON_PLAYWRIGHT
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing.json --web-vitals --resource-snapshot --resource-max-total-rss-mb 1200 --resource-max-total-cpu-percent 200 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000 --web-vitals-max-scroll-overflow-px 0

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
.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173）
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
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
