# CLAUDE.md

> 完整项目上下文见 `AGENTS.md`。本文档保留常用命令、核心约束和架构要点作为速查。

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用 — **FastAPI 后端 + React 前端**。Streamlit `app/` 自 2026-05-30 冻结维护。

UI：「编辑风 × 液态玻璃」— Playfair Display + Inter，毛玻璃，日/夜双皮肤。

**Phase 5 基线**：前端 GET 统一 TanStack Query（11 命名空间 queryKeys）；Provider 错误分层；业务 service 层 urllib 清零；模块级 API Map 缓存清除；Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线；`records.py` 88 行 facade；`chart_compute.py` 227 行 facade；Request ID 链路；架构护栏 105+ 测试 + CI 基线。2026-06-12 Phase 5.4-A~H 全系列完成：TrackDetail (574→5 行)、HabitsTab (933 行→9 文件 feature)、AI Insights 拆分、24 端点 response_model 硬化、Bundle 懒加载治理（Settings -88%、Records -69%、Account -34%）、TrackDetail 歌词 Query 漏网修复。播放统计规则引擎（Phase C+D）：Session 边界检测（`max_gap_minutes` + `boundary_column`）、Track Groups 三级合并（L1/L2/L3 recording/composition scope）、`MergeConfig` FastAPI 依赖、`/analysis/charts` 与 `/billboard/*` 端点 `merge_level` 查询参数。详见 `AGENTS.md` 和 `docs/2026-06-08-phase5-productization-baseline.md`。

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
- 环境变量统一 `core/config.py`；禁止业务代码直接 `os.getenv()`
- Token 加密：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥
- **新增 GET hook → TanStack Query + `queryKeys`；禁止模块级 `new Map()` 数据缓存**
- **新增外部 HTTP 调用 → Provider/HttpClient；禁止直接 `urllib.request.Request`/`urlopen`**
- **页面容器只做路由入口；业务逻辑在 `features/`**
- 架构护栏测试 `phase5-architecture.test.ts` 对上述约定做负面断言强制执行

完整架构、模块表、数据库结构、过滤策略见 `AGENTS.md`；后端细节见 `backend/CLAUDE.md`；前端细节见 `frontend/CLAUDE.md`。
