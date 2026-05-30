# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用。从 Spotify 官方 JSON 播放记录导入 SQLite，通过 **FastAPI 后端 + React 前端** 提供交互式多维度统计仪表盘。

原 Streamlit 单体架构已迁移到 FastAPI + React。`app/` 目录下的 Streamlit 应用自 2026-05-30 进入**冻结维护**（只修严重 bug，新功能进 backend/ + frontend/）。两者仅共享 `data/spotify_stats.db`，无代码交叉依赖。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线 + Inter 无衬线）+ 毛玻璃材质 + 日/夜双皮肤。详见 `frontend/UI_STYLE_GUIDE.md`。

**性能策略**：Cache Manager 管理 5 命名空间（billboard/analysis/db/auth）LRU+TTL 缓存；Billboard 拆为 4 个独立 `@lru_cache` 函数；SQLite 版本化 Migration；后台 Job Queue（3 worker）异步处理封面下载与 Wikipedia+LLM enrichment；前端 TanStack React Query（staleTime 5min/gcTime 30min/retry 2），路由级 lazy 分包。

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

# 测试（244 个，分三层：unit / contract / integration）
source .venv/bin/activate && pytest backend/tests/ -v
source .venv/bin/activate && pytest -m unit -v         # ~5秒，无 DB
source .venv/bin/activate && pytest -m contract -v      # ~1秒，seed DB
source .venv/bin/activate && pytest -m integration -v   # ~80秒，只读生产DB

# 前端测试
cd frontend && npm test

# 代码质量
ruff check backend/
ruff format --check backend/
pre-commit run --all-files

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

## 架构

### 数据流

```
JSON 导出 ──→ import_data.py ──→ SQLite (spotify_stats.db) ──→ FastAPI backend/ ──→ React frontend/
                                         │
账号数据 ──→ import_account_data.py ─────┘         └──→ Streamlit app/ (冻结维护)
```

### 后端架构 (backend/)

四层分离：**api/**（路由 + Depends 依赖注入）→ **services/**（计算逻辑，`@lru_cache`）→ **domains/**（领域模块：billboard / playback / settings / enrichment）→ **core/**（db, utils, cache, config, crypto, json_helpers）

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
| `services/play_service.py` | 核心播放数据服务，所有基于 plays 的端点统一入口 |
| `services/wrapped_service.py` | 自定义年度总结（听歌人格/Top榜/曲风全景/发现回归等） |
| `services/billboard_service.py` | Billboard facade（~100行），实现已迁入 `domains/billboard/` |
| `services/spotify_auth.py` | OAuth PKCE 授权与数据同步 |

**测试分层**：`unit/`（纯函数，无 DB）→ `contract/`（seed DB 结构验证）→ `integration/`（真实数据只读）。Contract 测试 teardown 清除所有 `@lru_cache` 防止污染。

### 前端架构 (frontend/)

React 19 + Vite 8 + Tailwind CSS v4 + shadcn/ui (base-nova) + React Router v7 + TanStack React Query + ECharts 6。

**目录结构**：
```
frontend/src/
├── api/              ← 类型化 API 客户端 + TanStack QueryClient 配置 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件（settings/, account/collection/）
├── components/       ← ui/ (shadcn) | charts/ (ECharts + 纯DOM) | layout/ | shared/
├── pages/            ← 路由级页面组件（React.lazy 分包）
├── hooks/            ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount
├── lib/              ← 工具函数（cn, chinese, insights, theme, personality-themes, genre-regions）
└── types/            ← 手写 TypeScript 展示类型
```

**路由**：`/` → `/analysis/stats|charts` → `/yearly-review` → `/billboard` → `/account` → `/settings`；音乐实体详情 `/music/{tracks|albums|artists}/:id`；旧 `/billboard/track|album|artist/*` 仅兼容跳转。

**关键约定**：
- 外部文本渲染必须经 `react-markdown` + `rehype-sanitize`，禁止 `dangerouslySetInnerHTML`
- LLM API Key 永远不通过 API 返回前端，仅返回 `has_llm_key: bool`
- OpenAPI 类型通过 `npm run generate-types` 从后端自动生成
- 路径别名 `@/` → `src/`

### 数据库

维度表 `artists` → `albums` → `tracks`，事实表 `plays`（预计算 `ts_year/month/week/dow/hour/date`，均为北京时间 UTC+8）。`track_albums` 处理同曲多专辑关联。Spotify 元数据独立存储在 `spotify_*_meta` 表。`release_groups` + `release_group_members` 管理专辑版本合并。

账号数据表独立：`saved_tracks/albums/artists`、`playlists`、`search_queries`、`podcast_*`、`user_*`、`marquee_impressions`、`wrapped_*`、`banned_items`。

### 数据过滤策略

`base_filters()` 是唯一过滤入口：`ms_played >= min_ms`（默认 30s）+ `music_only`（排除播客）。合并连续播放（`merge_enabled`，默认开启）先合并再过滤。已移除不可靠的 `skipped` 过滤。

特殊页面例外：行为分析使用全量数据；播客/视频额外 `>= 30000ms`；Billboard 专辑榜排除 singles 和发前周。

## 技术约束

- Python 3.9：使用 `Optional[X]` 而非 `X | None`
- 后端绝对导入：`from backend.core.db import get_db`
- SQLite `data/spotify_stats.db`，由 `.gitignore` 排除
- `ttl_cached()` 不缓存 `None`，测试可调 `cache_clear()`
- 昂贵缓存优先通过公开 wrapper 规范化参数 + `singleflight()` 避免并发重复计算
- Spotify OAuth 开发需要 HTTPS，用 ngrok 静态域名代理
- LLM API Key 加密存储，前端永远不可见明文
- Token 加密密钥优先级：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥（仅限单用户本地）
