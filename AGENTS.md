# AGENTS.md

Spotify Extended Streaming History 数据分析 Web 应用的主项目提示词文件，供 Claude Code 及其他 AI 编码助手共同使用。

---

## 项目概述

从 Spotify 官方 JSON 播放记录导入 SQLite，通过 **FastAPI 后端 + React 前端** 提供交互式多维度统计仪表盘。

原 Streamlit 单体架构已迁移到 FastAPI + React。`app/` 目录下的 Streamlit 应用自 2026-05-30 进入**冻结维护**（只修严重 bug，新功能进 backend/ + frontend/）。两者仅共享 `data/spotify_stats.db`，无代码交叉依赖。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线 + Inter 无衬线）+ 毛玻璃材质 + 日/夜双皮肤。详见 `frontend/UI_STYLE_GUIDE.md`。

**性能策略**：Cache Manager 管理 5 命名空间（billboard/analysis/db/auth）LRU+TTL 缓存；Billboard 拆为 4 个独立 `@lru_cache` 函数；SQLite 版本化 Migration；后台 Job Queue（3 worker）异步处理封面下载与 Wikipedia+LLM enrichment；前端 GET 数据统一进入 TanStack React Query（staleTime 5min/gcTime 30min/retry 2），路由级 lazy 分包。

## Phase 5 产品化收口基线

Phase 5 目标是收紧产品线到可持续迭代状态。当前进度：

**已完成**：
- 前端 GET 数据获取统一到 TanStack Query + `queryKeys`（9 命名空间：dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge/community）
- Provider 错误分类体系（`ProviderError` → `ProviderNetworkError`/`ProviderHTTPError` → `ProviderAuthError`/`ProviderRateLimitError`/`ProviderServerError` + `ProviderParseError`）
- 业务 service 层 urllib 调用清零；core Spotify HTTP 收敛到 `HttpClient`/`SpotifyProvider`
- 所有页面容器 ≤ 192 行（Records 115 / AllTimeCharts 192 / NumberOnes 5 / ArtistDetail 5 / AlbumDetail 5）
- 音乐详情页持续拆分到 feature sections；header/tabs/skeletons/overview/tracks/albums/career/artist-releases/album-era 子 sections 与共享 primitives 已从 Artist/Album Experience 中抽出
- 前端展示类型 `frontend/src/types/billboard.ts` 已补齐 Billboard、音乐详情、release-cycle 与 enrichment 常用展示字段，`npm run build` 作为硬验证
- 模块级 API 响应 Map 缓存全部清除，迁移到 TanStack Query
- Records/AllTime/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页基线，新增长表必须继续使用分页或虚拟化
- Request ID（`X-Request-ID` 生成/透传/日志关联）
- Billboard records 输出层已拆入 `backend/domains/billboard/records_output.py`，championship/no1 family 已拆入 `records_championship.py`，longevity/persistence family 已拆入 `records_longevity.py`，movement/breakthrough family 已拆入 `records_movement.py`，hall-of-fame/power ranking family 已拆入 `records_hall_of_fame.py`，endurance/rank-stability family 已拆入 `records_endurance.py`，self-replacement/blocker family 已拆入 `records_self_replacement_blocker.py`，market/market-intensity family 已拆入 `records_market.py`，quirky/special-feat family 已拆入 `records_quirky.py`，`records.py` 保留 88 行纯编排 facade
- Billboard chart 周榜排名已拆入 `backend/domains/billboard/chart_ranking.py`，走势评分（Power Score）已拆入 `backend/domains/billboard/chart_power_score.py`，summary/count helper 已拆入 `backend/domains/billboard/chart_summaries.py`，staged cache 已拆入 `backend/domains/billboard/chart_staged_cache.py`，staged public API 已拆入 `backend/domains/billboard/chart_staged_api.py`，`chart_compute.py` 保留 227 行兼容入口/re-export/cache registration facade
- 架构护栏测试（`frontend/src/tests/phase5-architecture.test.ts`）与长列表分页渲染测试（`frontend/src/tests/long-list-pagination.test.tsx`）
- `scripts/phase5_check.sh` 最低验证矩阵 + GitHub Actions CI 基线（`.github/workflows/phase5-baseline.yml`）

**持续治理**：
- Provider 全量替换：`release_cycle_service.py`、`wikipedia_service.py`、`spotify_utils.py` 和 `version_merge.py` 已收敛；后续按架构护栏防回归
- 后端 Billboard chart compute 已收口（`records.py` 88 行 / `chart_compute.py` 227 行 / `chart_staged_api.py` 114 行 / `chart_staged_cache.py` 336 行 / `chart_ranking.py` 142 行 / `chart_power_score.py` 272 行 / `chart_summaries.py` 220 行）；后续按触碰拆分其他大文件
- 长列表已建立分页基线；后续新增超过 500 行 DOM 的表格必须使用服务端分页、分页组件或虚拟化

详见 `docs/2026-06-08-phase5-productization-baseline.md`。

## 常用命令

```bash
# 启动后端（只监听 backend/，避免扫描 .venv/node_modules/data）
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend

# 关闭预热冷启动
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend

# 前端开发
cd frontend && npm run dev

# ngrok HTTPS 隧道（Spotify OAuth 回调需要）
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

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

# 其他
cd frontend && npm run build          # 生产构建
cd frontend && npx shadcn@latest add <component-name>
source .venv/bin/activate && streamlit run app/main.py  # Streamlit（冻结维护）
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
账号数据 ──→ import_account_data.py ─────┘         └──→ Streamlit app/ (冻结维护)
```

### 后端架构 (backend/)

四层分离：**api/**（路由 + Depends 依赖注入）→ **services/**（计算逻辑，`@lru_cache`）→ **domains/**（领域模块：billboard / playback / settings / enrichment / community）→ **core/**（db, utils, cache, config, crypto, json_helpers）

**基础设施**：`infrastructure/http/` 统一 HTTP 客户端（timeout/retry/proxy/脱敏）；`providers/` 封装所有第三方 API（spotify / genius / wikipedia / llm），禁止业务代码散落请求逻辑。

**路由层关键约定**：
- `backend/dependencies.py`：`PlayFilters`（标准播放过滤）、`BillboardFilters`（继承 + Billboard 参数）、`get_conn()`（数据库连接注入）
- API 层通过 `Depends(get_conn)` 注入连接，请求结束自动关闭
- 非缓存服务接收 `conn` 参数从 API 层传入
- 缓存服务（`@lru_cache` / `@ttl_cached`）内部调用 `get_db()`（连接不可哈希）
- FastAPI `:path` 贪婪匹配，含子路径路由注册在泛化路由之前

**核心模块速览**：

| 文件 | 职责 |
|------|------|
| `core/db.py` | `get_db()`, `load_plays()` (@lru_cache), `base_filters()`, `merge_consecutive_plays()` |
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
│   ├── community/         ← CommunityExperience/Account + FeedToggle + PostCard + Timeline + Sidebar + Data
│   ├── music/details/     ← Artist/Album Experience + Header/Tabs + Skeletons + Overview/Tracks/Albums/Career/ArtistReleases/AlbumEra 子 sections + ReleaseCycle sections + Primitives
│   ├── settings/components/  ← 7 配置 Section 组件
│   └── account/collection/   ← 收藏分析组件
├── components/
│   ├── ui/            ← shadcn/ui 组件
│   ├── charts/        ← ECharts 封装（动态 import）+ 纯 DOM 图表
│   ├── layout/        ← AppLayout, Masthead, ThemeToggle
│   └── shared/        ← GlassCard, KpiCard, CoverCell, FormattedText 等
├── pages/             ← 路由级页面容器（React.lazy 分包，≤192 行，纯组合 feature 组件）
├── hooks/             ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount（均用 useQuery）
├── lib/               ← 工具函数（cn, chinese, insights, theme, personality-themes, genre-regions）
├── tests/             ← 含 phase5-architecture.test.ts 架构护栏测试
└── types/             ← 手写 TypeScript 展示类型
```

**路由**：`/` → `/analysis/stats|charts` → `/yearly-review` → `/billboard` → `/community` → `/account` → `/settings`；音乐实体详情 `/music/{tracks|albums|artists}/:id`；社区账号页 `/community/account/:handle`；旧 `/billboard/track|album|artist/*` 仅兼容跳转。

**Phase 5 架构模式**（新增组件必须遵守）：

| 层级 | 位置 | 行数上限 | 职责 |
|------|------|---------|------|
| Route Container | `pages/` | ≤450 | 数据获取 + 组合 feature 组件，不含 `<table>`/`function KpiCard` 等实现细节 |
| Experience | `features/*/XXXExperience.tsx` | 目标 ≤450 | 编排子组件，管布局和数据流；音乐详情仍在按 section 逐轮收敛 |
| Section | `features/*/XXXSection.tsx` | ≤300 | 单个业务模块渲染 |
| Primitives | `features/*/XXXPrimitives.tsx` | ≤350 | 跨 Section 共享的 UI 零件（KpiCard, CoverCell 等） |
| Data | `features/*/xxxData.ts` | — | 纯函数，计算逻辑与 UI 完全分离 |

**关键约定**：
- 外部文本渲染必须经 `react-markdown` + `rehype-sanitize`，禁止 `dangerouslySetInnerHTML`
- LLM API Key 永远不通过 API 返回前端，仅返回 `has_llm_key: bool`
- OpenAPI 类型通过 `npm run generate-types` 从后端自动生成
- **新增 GET hook 必须使用 `queryKeys` + TanStack Query**，禁止新增模块级数据缓存
- 模块级变量只允许保存 tab/排序/页码等 UI 状态（如 `let cachedTab`、`let cachedSortKey`）
- **禁止模块级 `new Map()` 缓存 API 响应**，详情页 enrichment/release-cycle 数据必须走 Query Client
- 页面容器禁止包含 `<table>`、`function KpiCard`、`function No1BarChart` 等直接实现——这些必须放在 features/
- 架构护栏测试（`phase5-architecture.test.ts`）使用 `?raw` import + 负面断言强制执行上述约束
- 路径别名 `@/` → `src/`

详细前端架构见 `frontend/CLAUDE.md`。

### 数据库

维度表 `artists` → `albums` → `tracks`，事实表 `plays`（预计算 `ts_year/month/week/dow/hour/date`，均为北京时间 UTC+8）。`track_albums` 处理同曲多专辑关联。Spotify 元数据独立存储在 `spotify_*_meta` 表。`release_groups` + `release_group_members` 管理专辑版本合并。

账号数据表独立：`saved_tracks/albums/artists`、`playlists`、`search_queries`、`podcast_*`、`user_*`、`marquee_impressions`、`wrapped_*`、`banned_items`。

### 数据过滤策略

`base_filters()` 是唯一过滤入口：`ms_played >= min_ms`（默认 30s）+ `music_only`（排除播客）。合并连续播放（`merge_enabled`，默认开启）先合并再过滤。已移除不可靠的 `skipped` 过滤。

特殊页面例外：行为分析使用全量数据；播客/视频额外 `>= 30000ms`；Billboard 专辑榜排除 singles 和发前周。

---

## 技术约束

- Python 3.9：使用 `Optional[X]` 而非 `X | None`
- 后端绝对导入：`from backend.core.db import get_db`
- SQLite `data/spotify_stats.db`，由 `.gitignore` 排除
- `ttl_cached()` 不缓存 `None`，测试可调 `cache_clear()`
- 昂贵缓存优先通过公开 wrapper 规范化参数 + `singleflight()` 避免并发重复计算
- Spotify OAuth 开发需要 HTTPS，用 ngrok 静态域名代理
- LLM API Key 加密存储，前端永远不可见明文
- Token 加密密钥优先级：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥（仅限单用户本地）
- **业务层新增外部 HTTP 调用必须走 Provider/HttpClient**；service 层和 core Spotify 路径不得直接 `urllib.request.Request`/`urlopen`
- **新增 GET hook 必须使用 TanStack Query + `queryKeys`**；禁止模块级 `new Map()` 数据缓存
- **页面容器只做路由入口**，业务逻辑和渲染细节必须在 `features/` 中
