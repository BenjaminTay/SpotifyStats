# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用。从 Spotify 官方导出的 JSON 播放记录中导入数据到 SQLite，通过 FastAPI + React 提供交互式多维度统计仪表盘。

**架构演进**：已从 Streamlit 单体架构迁移到 FastAPI 后端 + React 前端。前端包含 Dashboard、stats.fm 风格播放统计、年度回顾页面（自定义总结 + 官方 Wrapped，双 Tab）、Billboard 周榜页（含对决、发行周期分析、榜单记录等 12 子 Tab）、全局音乐实体详情页（歌曲/专辑/艺人，含个人播放统计、Billboard 成绩、Genius 歌词、Spotify 元数据展示、Wikipedia 百科 AI 结构化数据）、账号中心页面（含收藏分析、搜索编年史、粉丝层级、播客聆听、推广转化、视频分析、收听人格）以及设置页面（含 LLM 配置档案持久化管理、Spotify OAuth 连接管理、数据同步）。Streamlit 原有应用和后端 API 仍可并行运行。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线标题 + Inter 无衬线正文）+ 毛玻璃卡片材质 + 日/夜双皮肤。详细风格指南见 `frontend/UI_STYLE_GUIDE.md`。

**性能策略**：后端启动后后台预热默认 Dashboard/Analysis/Billboard 缓存，`/api/billboard/data` 等大响应启用 gzip，Billboard 全量计算使用 normalized cache key + single-flight 避免重复冷算，播放统计使用参数化结果缓存。前端使用路由级 lazy 分包、Dashboard/Billboard/Analysis 共享 in-flight request 或参数化缓存，布局层延迟预取常用数据；ECharts 与 OpenCC 改为按需动态加载，默认首屏入口包约 276KB（gzip 约 89KB）。

## 常用命令

```bash
# 启动 FastAPI 后端（端口 8000，Swagger UI: http://localhost:8000/docs）
# 开发时只监听 backend/，避免 --reload 扫描 .venv、frontend/node_modules、data 导致 CPU 持续偏高
source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend

# 调试冷启动或暂时不需要预热缓存时，可关闭启动预热
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend

# 启动前端开发服务器（端口 5173，自动代理 /api → 后端 8000）
cd frontend && npm run dev

# 启动 ngrok HTTPS 隧道（Spotify OAuth 回调需要 HTTPS，静态域名配置在 .env 中）
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

# 构建前端生产版本
cd frontend && npm run build

# 添加 shadcn/ui 组件
cd frontend && npx shadcn@latest add <component-name>

# 启动 Streamlit 开发服务器
source .venv/bin/activate && streamlit run app/main.py

# 仅重新导入数据（不启动 UI）
source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, '.')
from app.import_data import import_data
result = import_data()
print(result)
"

# 分析每周独特曲目分布（确定 Billboard 默认 Top N）
source .venv/bin/activate && python3 scripts/analyze_weekly_tracks.py

# 清除 Streamlit 缓存后重启
streamlit run app/main.py --server.clearCaches=true

# 安装/更新依赖
source .venv/bin/activate && pip install -r requirements.txt

# 运行后端测试（230 个测试，分三层：unit / contract / integration）
source .venv/bin/activate && pytest backend/tests/ -v

# 分层运行测试
source .venv/bin/activate && pytest -m unit -v          # 纯函数单元测试，~5秒，无 DB
source .venv/bin/activate && pytest -m contract -v       # 结构验证，~1秒，seed SQLite DB
source .venv/bin/activate && pytest -m integration -v    # 真实数据集成测试，~80秒

# 快速验证后端测试耗时与慢点
source .venv/bin/activate && pytest backend/tests/ --durations=20 -q

# 运行单个测试文件
source .venv/bin/activate && pytest backend/tests/unit/test_crypto.py -v
source .venv/bin/activate && pytest backend/tests/integration/test_api.py -v

# 前端测试（20 个 vitest 单测）
cd frontend && npm test

# 生成 OpenAPI TypeScript 类型（需后端运行中）
cd frontend && npm run generate-types

# 代码质量检查
ruff check backend/                     # Lint 检查
ruff format --check backend/            # 格式检查
pre-commit run --all-files              # 全量预提交检查
```

## Git 提交说明规范

提交信息必须延续本仓库既有的详细说明风格，不要只写一行简略标题。推荐格式：

```text
<type>: <中文概括标题>

- 后端/数据层改动：说明新增或调整的 API、服务、缓存、数据库或计算口径
- 前端/UI 改动：说明新增页面、路由、组件、交互和视觉结构
- 性能/稳定性改动：说明缓存、预热、请求复用、错误回退或兼容迁移
- 测试验证：说明新增/更新的测试，以及实际跑过的验证命令或结果
- 文档同步：说明 README、CLAUDE、AGENTS、UI 指南等是否已同步
```

要求：
- 标题使用 conventional commit 前缀（如 `feat:` / `fix:` / `perf:` / `docs:`），后面用中文准确概括本次提交。
- 正文用 4-7 条中文 bullet，覆盖本次改动的关键模块和用户可感知行为。
- 如果改动包含文档同步、测试提速、缓存策略或路由兼容迁移，必须在正文单独写明。
- 提交前先看最近几条 `git log --format=fuller -n 5`，保持粒度和措辞风格一致。

## 架构

### 数据流

```
JSON 文件 (Spotify导出) ──→ import_data.py ──→ SQLite (spotify_stats.db)
                                    │
JSON 文件 (账号数据)  ──→ import_account_data.py ──┘
                                                        │
                    ┌───────────────────────────────────┘
                    │
                    ├──→ FastAPI backend (backend/)
                    │    ├── api/           路由层 (Depends 依赖注入)
                    │    ├── services/      计算逻辑层 (lru_cache)
                    │    ├── domains/       领域模块 (billboard, playback, settings, enrichment)
                    │    ├── providers/     第三方服务适配器 (spotify, genius, wikipedia, llm)
                    │    ├── infrastructure/ 基础设施层 (http client)
                    │    ├── models/        Pydantic 响应模型
                    │    └── core/          核心工具 (db, utils, cache, json_helpers)
                    │
                    └──→ Streamlit app (app/)
                         st.cache_data 缓存查询结果
```

**工程化工具链**：项目通过 `pyproject.toml` 统一配置 pytest / ruff / mypy。CI 前通过 `pre-commit`（ruff format+check + mypy + detect-secrets）自动检查。开发依赖见 `requirements-dev.txt`。

后端生产入口 `backend/main.py` 通过 FastAPI lifespan 启动后台缓存预热线程（`backend/core/warmup.py`），启动时调用 `setup_logging()` 配置日志脱敏。默认预热 `load_plays()`、播放统计默认页与 `compute_billboard_data()`。启动后短时间 CPU 占用较高属于正常预热现象；设置 `SPOTIFY_STATS_WARMUP=0` 可关闭启动预热，测试环境通过 pytest fixture 控制预热节奏。全局 `@app.exception_handler(Exception)` 返回通用 500 而不泄露 stack trace（异常仍通过脱敏后的 logger 记录）。CORS 来源支持 `FRONTEND_ORIGIN` 配置值（适配 ngrok 等非 localhost 来源）。开发模式下使用 `uvicorn --reload --reload-dir backend`，只监听后端代码变更；不要让 reloader 扫描整个仓库，否则 `.venv`、`frontend/node_modules`、`data` 等大目录会导致 CPU 持续偏高。

### 后端架构 (backend/)

FastAPI 后端采用四层分离架构：**路由层 (api/)** → **服务层 (services/)** → **领域层 (domains/)** **核心工具层 (core/)**，并辅以 **基础设施层 (infrastructure/)** 和 **第三方适配层 (providers/)**。

#### 路由层 (api/)

后端按领域拆分子路由模块，所有路由通过 `backend/api/router.py` 组装，挂载到 `backend/main.py` 的 `/api` 前缀下。

**过滤参数依赖注入** (`backend/dependencies.py`)：
- `PlayFilters` — 标准播放数据过滤（`min_ms`, `music_only`, `merge_enabled`），用于仪表盘、时间线、排行榜、行为分析、听歌时段等端点
- `BillboardFilters` — Billboard 计算过滤（继承播放过滤 + `bb_top_n`, `bb_album_top_n`, `bb_artist_top_n`, `bb_week_start_dow`, `bb_week_start_hour`, `year_start`, `year_end`）
- `get_conn()` — 数据库连接依赖注入（默认只读连接）

端点使用方式：`def endpoint(filters: PlayFilters = Depends(), conn: Connection = Depends(get_conn)):`

**连接管理约定**：
- API 层：通过 `Depends(get_conn)` 注入连接，请求结束时自动关闭
- 非缓存服务：接收 `conn` 参数从 API 层传入
- 缓存服务（`@lru_cache` / `@ttl_cached`）：内部调用 `get_db()` 获取连接（连接对象不可哈希，无法作为缓存键）

**端点清单**：
```
GET  /api/health                         健康检查
GET  /api/dashboard/*                    仪表盘（6 端点：summary, monthly-trend, top-tracks, platform-dist, dow-dist, random-track）
GET  /api/timeline/*                     时间线（annual, monthly, weekly + 周下钻 top5）
GET  /api/leaderboard                    排行榜（track/artist/album × plays/hours × all/year）
GET  /api/analysis/overview              播放分析入口摘要
GET  /api/analysis/stats                 总体播放统计（时间范围、日/累计趋势、时钟、分布、最近播放）
GET  /api/analysis/charts                个人排行榜（track/album/artist × plays/hours × 任意时间范围）
GET  /api/music/tracks/{id}/stats        歌曲个人播放统计
GET  /api/music/albums/{name}/stats      专辑个人播放统计
GET  /api/music/artists/{name}/stats     艺人个人播放统计
GET  /api/music/{tracks,albums,artists}/*/plays  实体最近播放记录
GET  /api/behavior                       行为分析（reason_end, reason_start, fwdbtn, shuffle, platform）
GET  /api/listening-hours/*              听歌时段（heatmap, yearly-heatmap, late-night, weekday-weekend, platform-hourly）
GET  /api/artist/{name}/deep-dive        艺人深度分析
GET  /api/wrapped/available-years        自定义年度总结可用年份列表
GET  /api/wrapped/{year}/full            年度总结完整数据（含听歌人格、英雄区、Top榜、曲风全景、时间故事、发现与回归、聆听深度、特殊时刻、月度钻取、年度对比）
GET  /api/wrapped-hub/available-years    Wrapped 2025 官方可用年份列表
GET  /api/wrapped-hub                    Wrapped 2025 官方数据（俱乐部、Top榜、收听年龄、存档报告等）
GET  /api/library/*                      音乐库
GET  /api/search-history/*               搜索编年史
GET  /api/insights/*                     音乐画像
GET  /api/podcast/*                      播客
GET  /api/video/*                        视频分析
GET  /api/profile                        个人档案
GET  /api/billboard/data                  Billboard 统一数据入口（返回全部 15 个数据结构，~2-5MB JSON，含 cover_url）
GET  /api/billboard/track/{id}            单曲榜单历史（升降列 NEW/RE/▲n/▼n/─ + 断档 gap 检测）
GET  /api/billboard/artist/{name}         艺人榜单详情（周榜历史 + 歌曲/专辑表现 + Power Score）
GET  /api/billboard/album/{name}          专辑榜单详情（周榜历史 + 收录曲表现 + 最佳单曲叠加）
GET  /api/billboard/entity-lists          对决搜索选择器数据（歌曲/专辑/艺人列表）
GET  /api/billboard/versus/track          歌曲对决（排名历史 + 指标对比）
GET  /api/billboard/versus/album          专辑对决（含版本合并成员聚合）
GET  /api/billboard/versus/artist         艺人对决（歌曲/专辑双维度统计）
GET  /api/billboard/release-cycle/*       发行周期分析（artist-list, artist/{name}, artist/{name}/album/{album}, compare）
GET  /api/billboard/enrichment/album/{name}  Wikipedia 百科 + Genius 专辑扩展（AI 结构化数据）
GET  /api/billboard/enrichment/artist/{name} Wikipedia 百科 + Genius 艺人扩展（AI 结构化数据）
GET  /api/billboard/enrichment/track/{name}  Wikipedia 百科 + Genius 单曲扩展
GET  /api/lyrics/{track_id}               Genius 歌词获取（按需获取 + SQLite 缓存）
GET  /api/lyrics/{track_id}/url           Genius 链接查询（轻量，仅返回 URL）
GET  /api/settings                       设置（GET 读取 / PUT 更新，llm_api_key 不返回明文，仅返回 has_llm_key: bool）
GET  /api/settings/llm-profiles          LLM 配置档案列表（不含 key/base_url）
GET  /api/settings/llm-profiles/{id}     LLM 配置档案详情（不返回明文 key，仅 has_llm_key: bool）
POST /api/settings/llm-profiles          创建 LLM 配置档案
PUT  /api/settings/llm-profiles/{id}     更新 LLM 配置档案
POST /api/settings/llm-profiles/{id}/apply  应用 LLM 配置档案（服务端读取 key 写入 settings，前端不接触明文）
DELETE /api/settings/llm-profiles/{id}   删除 LLM 配置档案
GET  /api/version-merge/*                版本合并管理（groups, detect, apply）
GET  /covers/{type}/{id}.jpg              封面图片服务（三级回退：本地缓存 → CDN 重定向 + 后台下载 → 404）
POST /api/import/streaming               串流数据导入（异步任务）
POST /api/import/account                 账号数据导入
GET  /api/spotify/auth/login             Spotify OAuth PKCE 授权开始（返回 auth_url + state）
GET  /api/spotify/auth/callback          Spotify OAuth 回调（换 token + 全量数据拉取 + RedirectResponse）
GET  /api/spotify/auth/status            连接状态 + 已持久化数据摘要
DELETE /api/spotify/auth/disconnect      断开连接，清除所有 Spotify 数据
POST /api/spotify/auth/sync              同步收藏日期（user-library-read）
GET  /api/spotify/auth/data              返回所有持久化数据（top artists/tracks × 3 窗口 + recently played + followed + playlists）
GET  /api/spotify/auth/playing           实时播放状态（live from Spotify）
POST /api/spotify/auth/sync-all          全量数据刷新（profile + top items × 6 + recently played + followed + playlists）
```

#### 服务层 (services/)

计算逻辑从 Streamlit 页面中提取，不依赖任何 Web 框架。每个服务文件职责单一：

- **`analysis_stats_service.py` / `entity_stats_service.py`** — stats.fm 风格播放统计。前者负责统一时间范围解析、总体统计、个人排行榜、最近播放记录；后者负责歌曲/专辑/艺人个人播放统计、实体排名、Top 250 计数、实体内曲目/专辑拆解。两者继续复用 `load_plays()` 的标准过滤与合并口径
- **`play_service.py`** — 核心播放数据服务。`load_plays()` 封装，通用 groupby 聚合（按年/月/周/小时/平台/艺术家等），仪表盘 KPI、时间线（年度/月度/周度+下钻）、排行榜、行为分析、听歌时段热力图、工作日vs周末对比、平台×小时分布等所有基于播放数据的旧端点均调用此服务。Dashboard 相关函数支持可选 `df` 参数，`/dashboard/full` 端点加载一次 plays 后传递给 5 个子函数复用，避免 6 次冗余 SQL 查询。`get_hourly_dist()` 提供逐小时播放量分布，用于前端动态洞察生成
- **`wrapped_service.py`** — 自定义年度总结服务。`get_wrapped_full()` 一次性构建年度总结的完整数据结构（英雄区 KPI + 去年对比变化率、听歌人格识别 Explorer/Loyalist/Binger/深度鉴赏家/午夜诗人/潮流捕手、Top 5 曲目/艺人/专辑含封面与占比、曲风全景五大洲地图映射、逐小时播放分布 + 高峰识别、发现与新欢/老歌回归/遗忘曲目三分类、聆听深度金字塔、特殊时刻识别、月度钻取 Top 3、年度对比变化率），通过 `get_available_years()` 提供可用年份列表。内部复用 `load_plays()` 缓存，单年查询约 1-3 秒
- **`billboard_service.py`** — Billboard 计算管线 facade（~90行）。所有实现已迁入 `backend/domains/billboard/`（7 个领域模块：data_loader、version_merge、chart_compute、records、details、versus、entity_lists），原文件仅保留 re-export 以兼容旧 import 路径。`compute_billboard_data()` 一次性计算 15+ 数据结构（周榜 ×3、总榜 ×3、走势总榜 ×3、榜单记录、每周榜首等），内部使用 `@lru_cache(maxsize=8)` + `singleflight`，缓存装饰器通过 facade 重导出保持可用。详情和对比功能：`get_track_history()` / `get_artist_chart_detail()` / `get_album_chart_detail()` / `get_versus_{track,album,artist}()` / `get_billboard_entity_lists()` 均在领域模块中实现
- **`release_cycle_service.py`** — 发行周期分析。艺人发行列表、单曲 Billboard 历史、专辑周期指标（首周排名、峰值、影响力得分、半衰期）、先行曲识别（三级查找：DB → Spotify API → 最早播放日期）、`compare_releases()` 多发行叠加对比。Spotify API 令牌通过 `@ttl_cached` 缓存（~58 分钟 TTL），网络/解析失败返回 `None` 进入离线回退路径且不会缓存失败值；对比接口支持通过合并子版本名解析到 canonical 专辑，并保留子版本发行日期用于周期对齐
- **`library_service.py`** — 收藏交叉查询（收藏曲目/专辑/艺人与实际收听对比），含封面 URL 解析
- **`search_service.py`** — 搜索历史统计（日搜索量、意图分类、时段热力图）
- **`insights_service.py`** — 粉丝层级分析 + Marquee 推广转化率（按转化率降序排列，含艺人封面）
- **`genius_service.py`** — Genius 歌词服务。懒加载 `GeniusClient` 单例（token 从统一 config 模块读取），`get_track_lyrics()` 按需获取歌词并缓存到 `track_lyrics` 表，`get_track_genius_url()` 轻量 URL 查询。歌词清洗：去除 Genius 元数据（Contributors/Translations/Read More），提取嵌入式分段标题（`[Verse]`/`[Chorus]` 等），规范化分段间距（每段之间恰好一空行）
- **`podcast_service.py`** — 播客统计（含 `ms_played >= 30000` 过滤排除自动预览噪音，按收听时长降序排列）
- **`video_service.py`** — 视频分析（含视频曲目封面解析）
- **`profile_service.py`** / **`wrapped_hub_service.py`** — 账号数据页面服务
- **`wikipedia_service.py`** — Wikipedia 百科扩展服务。专辑/艺人/单曲页面搜索、全文提取、Infobox 解析、段落分割、SQLite 缓存（`wikipedia_cache` 表）、中文翻译（LLM 优先 → Google Translate 回退）、LLM 结构化数据生成（artist → key_facts + career_timeline + genres + stats + achievements，album → key_facts + genres + chart_performance + accolades + singles）
- **`spotify_auth.py`** — Spotify OAuth PKCE 授权与数据同步服务。`begin_oauth_flow()` 生成 PKCE 挑战 + auth URL；`complete_oauth_flow()` 换 token 后自动拉取全量数据（profile、top artists/tracks × 3 窗口、recently played、followed artists、playlists）；`get_connection_status()` 返回连接状态 + 数据摘要；`fetch_saved_tracks()` 拉取收藏曲目回填 `added_date`；`get_live_playback()` 实时播放状态
- **`account_service.py`** — 账号中心聚合服务。`get_account_summary()` 返回收藏分析 + 搜索/习惯两大 Tab 综合数据。`get_collection_insights()` 性能重构：核心 saved_tracks×plays 交叉查询只执行一次，所有衍生计算（人格、生命周期、化学反应、关键词等）均在 Python 内存中完成。关键词提取使用 jieba 分词 + TF-IDF 加权（各年作为"文档"，IDF 惩罚跨年通用词）。新增封面图映射辅助函数 `_cover_url()` / `_artist_cover_map()` / `_track_album_cover_map()`，收藏曲目、生命周示例、化学反应示例、Flip Side 等均返回 `cover_url`
- **`llm_translator.py`** — LLM 翻译/结构化服务。多提供商（DeepSeek/OpenAI/Anthropic/自定义）、API Key 配置从 settings 模块懒加载、代理支持、`translate_with_llm()` 翻译 + `enrich_with_llm()` 结构化 JSON 提取、长文本自动分段（4000 字符/段）、含 3 次重试和速率限制退避

#### 领域层 (domains/)

按业务领域拆分的计算逻辑与数据访问模块，从 `services/` 中提取以根治大文件膨胀：

- **`domains/billboard/`** — Billboard 领域模块（7 个文件）。`data_loader.py`：原始播放数据加载、track/album map、album metadata（含 `@lru_cache` 缓存）；`version_merge.py`：专辑版本合并辅助函数（`_normalize_album_column`、`_resolve_album_members`、`_apply_album_release_groups`）；`chart_compute.py`：周榜/总榜/Power Score 计算与 `_compute_billboard_data_cached()`（`@singleflight` + `@lru_cache(maxsize=8)`）；`records.py`：榜单记录计算（6 大展区 37 项记录）；`details.py`：歌曲/艺人/专辑详情与周榜历史序列化；`versus.py`：双实体对决对比；`entity_lists.py`：对决搜索选择器实体列表；`repository.py`：Spotify metadata 与预聚合表 SQLite 查询封装
- **`domains/settings/repository.py`** — Settings 表 CRUD（load_all / update / delete），`backend/api/settings.py` 通过此 repository 读写设置
- **`domains/playback/repository.py`** — 播放数据查询封装（计数、年份、日期范围、实体播放次数、最近播放）
- **`domains/enrichment/repository.py`** — 歌词缓存、Wikipedia 缓存、LLM 翻译缓存表的读写封装

#### 基础设施层 (infrastructure/)

横切能力，不反向依赖业务：

- **`infrastructure/http/client.py`** — 统一 HTTP 客户端。支持 timeout、retry、proxy、JSON/表单编码自动识别、`redact()` 脱敏；Spotify/Wikipedia/LLM Provider 均通过此客户端发出 HTTP 请求

#### 第三方适配层 (providers/)

所有外部 API 调用统一通过 Provider 接口发出，禁止在业务代码中散落请求逻辑：

- **`providers/base.py`** — `BaseProvider` 抽象类（`health_check()` / `redact()`）+ `ProviderConfig` dataclass（timeout、retries、rate_limit_rps、proxy）
- **`providers/spotify/client.py`** — `SpotifyProvider`，包装现有 `spotify_utils` 函数（get_cc_token、get_profile、get_top_artists/tracks、get_recently_played、get_playback、get_followed_artists、get_playlists）
- **`providers/genius/client.py`** — `GeniusProvider`，包装现有 `GeniusClient`（get_song、get_artist、search），懒加载 client 单例
- **`providers/wikipedia/client.py`** — `WikipediaProvider`，通过共享 `HttpClient` 调用 Wikipedia REST API（get_page_summary、get_page_extract、search），支持多语言
- **`providers/llm/client.py`** — `LLMProvider`，多后端支持（DeepSeek/OpenAI/Anthropic/自定义 OpenAI 兼容）、统一 chat/translate/extract_structured 接口、自动处理 Anthropic 不同 API 格式

#### 核心工具层 (core/)

从 `app/` 目录原样迁移或提取的纯逻辑模块，不含任何 Web 框架依赖：

- **`config.py`** — 集中配置管理。通过 `python-dotenv` 在 import 时调用 `load_dotenv()`，替代所有手动 `.env` 解析。暴露所有配置项为模块级变量（`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, `GENIUS_ACCESS_TOKEN`, `HTTPS_PROXY`, `HTTP_PROXY`, `FRONTEND_ORIGIN`, `SPOTIFY_STATS_WARMUP`, `SPOTIFY_STATS_REQUIRE_AUTH`, `SPOTIFY_STATS_API_TOKEN`, `SPOTIFY_STATS_TOKEN_KEY` 等），每个变量有合理默认值
- **`crypto.py`** — AES-256-GCM 加解密模块。使用 `cryptography` 库的 `AESGCM` 进行加密；Key 来源优先级：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 硬编码应用密钥（单用户本地场景可接受）；通过 PBKDF2（600,000 轮迭代）从密码派生 32 字节 AES 密钥。提供 `encrypt(plaintext) -> str` / `decrypt(ciphertext) -> str` / `is_encrypted(value) -> bool` 三个函数，`is_encrypted` 通过检测是否以 `{` 开头区分明文/密文
- **`auth.py`** — API 鉴权依赖模块。使用 `fastapi.security.HTTPBearer` 提取 Authorization header；`require_auth()` 依赖函数在 `SPOTIFY_STATS_REQUIRE_AUTH != "1"` 时直接放行（本地模式），否则校验 Bearer token 是否等于 `SPOTIFY_STATS_API_TOKEN`（不匹配返回 403）。应用于所有写/敏感接口（settings 写操作、llm-profiles 变更、Spotify disconnect/sync、import、version-merge 变更）
- **`logging_config.py`** — 统一日志配置。`SensitiveDataFilter`（`logging.Filter` 子类）基于正则表达式脱敏日志中的敏感数据（`llm_api_key`, `access_token`, `refresh_token`, `Bearer` token, `sk-...`, `deepseek-...`, `Authorization`, `x-api-key`, `client_secret`）；`setup_logging()` 配置 root logger，添加 `StreamHandler` + `SensitiveDataFilter`，抑制 urllib3/httpx 等噪声库日志
- **`genius/`** — Genius API 客户端模块。`client.py`（`lyricsgenius` 封装：搜索、获取歌词/专辑/艺人/排行榜、封面下载、`_clean_lyrics()` 清洗）+ `models.py`（`Song`/`SearchResult`/`AlbumInfo` dataclass）
- **`db.py`** — 从 `app/db.py` 完整迁移。`get_db()` 使用 `check_same_thread=False` 适配 Starlette 后台任务线程清理（每个请求独立连接，无并发风险），只读模式通过 `PRAGMA query_only = ON` 实现。`base_filters()`, `load_plays()`（`@lru_cache(maxsize=16)` 按参数缓存 DataFrame，避免重复 SQL+merge 计算），`merge_consecutive_plays()`, `ensure_schema()`（含 `track_lyrics`, `settings`, `llm_profiles`, `wikipedia_cache` 表）, `build_aggregations()` 等所有函数
- **`utils.py`** — 从 `app/utils.py` 完整迁移。`convert_to_local_time()`, `classify_platform()`
- **`version_merge.py`** — 从 `app/version_merge.py` 完整迁移。`detect_release_groups()`, `apply_detected_groups()`, `create_group()`, `delete_group()` 等
- **`import_data.py`** / **`import_account_data.py`** — 从 `app/` 迁移，progress_callback 改为 threading.Event + 共享字典。日志使用 `logger.warning()` 替代 `print("[WARN] ...")`，统一接入脱敏管道
- **`json_helpers.py`** — 消除 3 处重复定义的序列化工具。`py_val()` 将 numpy/pandas 类型转为 JSON 安全的原生 Python 类型；`df_to_json()` 将 DataFrame 转为 dict 列表
- **`spotify_utils.py`** — Spotify Web API 核心工具（~500 行）。PKCE 辅助函数（`generate_pkce_pair`, `build_auth_url`）、OAuth token 交换与自动刷新（`exchange_code_for_tokens`, `get_user_access_token`, `_refresh_user_token`）、Token 加密持久化到 settings 表（AES-256-GCM 加密存储，`_load_user_token_json` 自动迁移旧明文数据）、用户档案拉取与持久化（`fetch_spotify_profile`, `save_user_profile`, `get_user_profile`）、10 个 scope 全覆盖数据拉取：top artists/tracks × 3 时间窗口（`fetch_top_artists/tracks`, `save/get_top_items`）、recently played（`fetch_recently_played`, `save/get_recently_played`）、followed artists（`fetch_followed_artists`, `save/get_followed_artists`）、playlists（`fetch_playlists`, `save/get_playlists`）、当前播放（`fetch_current_playback`, `fetch_currently_playing`，实时不持久化）、通用 API 调用（`spotify_api_get`, `spotify_api_get_all_pages`）、客户端凭据令牌 TTL 缓存（`get_client_credentials_token`）、全量同步（`sync_all_spotify_data`）。配置从 `backend.core.config` 统一读取
- **`cache.py`** — 从 `release_cycle_service.py` 提取。`ttl_cached(ttl_seconds)` 装饰器用于 Spotify API 等需要时间过期的外部调用缓存，支持 `cache_clear()`，且不缓存 `None` 失败值；`singleflight()` 用于序列化昂贵缓存函数的首次并发 miss
- **`warmup.py`** — 后端缓存预热工具。`warm_common_caches()` 预热默认播放数据与 Billboard 全量数据；`start_warmup_thread()` 由 FastAPI lifespan 后台启动，避免阻塞服务启动
- **`scripts/fetch_covers.py`** — 封面批量下载脚本。通过 Spotify API 批量拉取播放记录中所有专辑/艺人的封面，下载到 `data/covers/`，支持增量更新（已有 `image_path` 的记录自动跳过）。三级 ID 解析：`spotify_*_meta` 表 → Track API 反向查找 → Search API 模糊匹配

#### 响应模型 (models/)

Pydantic v2 模型定义 API 响应结构，按领域拆分：
- `common.py` — 通用模型（分页、错误响应）
- `dashboard.py` — 仪表盘响应（含 `HourlyDist` 逐小时播放量模型）
- `timeline.py` — 时间线 + Wrapped 年度总结响应（`AnnualTimelinePoint`, `MonthlyTimelinePoint`, `YearlyWrapped` 含 `personality` 听歌人格字段）
- `leaderboard.py` — 排行榜响应（`LeaderboardEntry`, `LeaderboardResponse`）
- `behavior.py` — 行为分析 + 听歌时段响应（`ReasonDist`, `FwdbtnByHour`, `HeatmapResponse` 等）
- `wrapped.py` — 年度总结完整响应模型（`WrappedFullResponse` 含 hero/personality/top_lists/genre_panorama/time_story/discovery_returns/listening_depth/special_moments/monthly_drilldown/comparison）

#### 测试 (tests/)

测试套件分为三层，通过 pytest markers（`unit` / `contract` / `integration` / `slow`）区分，配置在 `pyproject.toml` 中。

**目录结构**：
```
backend/tests/
├── conftest.py                # 根 fixtures（client, default_params, warm_default_caches, billboard_data）
├── unit/                      # 纯函数单元测试（无 DB 连接）
│   ├── conftest.py            # 空文件 — 阻断父级 DB fixture 加载
│   ├── test_json_helpers.py   # numpy/pandas → JSON 类型转换
│   ├── test_utils.py          # convert_to_local_time, classify_platform
│   ├── test_crypto.py         # AES-256-GCM encrypt/decrypt 往返
│   ├── test_cache.py          # TTL 缓存命中/过期/不缓存 None + singleflight
│   ├── test_logging.py        # SensitiveDataFilter 脱敏 API Key/Token/Bearer/sk-
│   └── test_billboard_pure.py # 纯 DataFrame 排名/评分/变化列/断档图计算
├── contract/                  # API 结构验证（便携 seed SQLite DB）
│   ├── conftest.py            # monkeypatch DB_PATH → fixtures/seed.db + use_seed_db fixture
│   └── test_api_contract.py   # 13 个端点 JSON 结构/状态码验证
├── integration/               # 真实数据集成测试（生产 SQLite DB，只读）
│   ├── conftest.py            # 引用父级 fixtures
│   ├── test_api.py            # API 层：结构验证、自洽性、交叉校验、边界条件、过滤器变化
│   ├── test_services.py       # Service 层：数值断言、numpy 类型安全、JSON 序列化、TTL 缓存、缓存预热
│   ├── test_analysis_api.py   # 分析端点专项测试
│   └── test_wrapped_full.py   # 年度总结服务专项测试
└── fixtures/
    ├── seed.db                # 便携测试数据库（~4KB，可提交 git）
    └── build_seed_db.py       # 构建脚本（含 11 条 golden assertions）
```

**测试分层统计**：230 个测试（50 unit + 13 contract + 167 integration）

- **Unit**（pytest -m unit）：纯函数单元测试，~5 秒完成，不加载任何数据库。覆盖 JSON 序列化、时区转换、加密往返、缓存行为、日志脱敏、Billboard 纯计算。
- **Contract**（pytest -m contract）：API 结构验证，~1 秒完成，使用便携 seed SQLite DB（3 艺人、15 曲目、85 条播放记录，覆盖短播放过滤、跨周边界、播客、skipped/offline 等边界）。验证 JSON 键名、HTTP 状态码和响应类型，不验证具体数据值。
- **Integration**（pytest -m integration）：真实数据集成测试，~80 秒完成，使用生产 SQLite 数据库只读验证。Session 级 `warm_default_caches` 预热 `load_plays()` 与 `compute_billboard_data()`；`billboard_data` fixture module 级复用避免重复冷算。

**跨测试缓存污染防护**：Contract 测试通过 `use_seed_db` fixture teardown 清除所有可能被种子数据污染的 `@lru_cache`：`_load_plays_cached`、`compute_billboard_data`、`_compute_billboard_data_cached`、`load_billboard_raw`、`load_track_album_map`、`_load_album_metadata`、`_get_analysis_stats_cached`、`_get_analysis_charts_cached`。`autouse` fixture `disable_warmup` 通过 monkeypatch `SPOTIFY_STATS_WARMUP=0` 阻止 contract 测试触发后台预热线程。

测试设计模式：真实数据断言（如 `total_plays > 50000`）而非 mock 返回固定值；交叉校验（如 dashboard 的 total_plays 与 timeline 的 annual 求和一致）；边界条件（不存在的艺人返回空、空年份标记 `empty: true`）。

### 前端架构 (frontend/)

React + Vite + Tailwind CSS v4 + shadcn/ui（样式 `base-nova`，基础色 `neutral`，图标库 `lucide-react`）。TypeScript 6.0 + React 19。

**技术栈**：
- **构建**：Vite 8，开发端口 5173，自动代理 `/api` → `localhost:8000`
- **样式**：Tailwind CSS v4（`@tailwindcss/vite` 插件），`tw-animate-css` 动画库
- **主题**：CSS 变量 + `.dark` class 切换，`oklch()` 色彩空间。结构变量在 `@theme inline`，颜色在 `:root` / `.dark`。`useTheme()` hook 提供 localStorage 持久化 + 系统偏好回退
- **组件**：shadcn/ui v4（base-nova 风格），源码在 `@/components/ui/`
- **路由**：React Router v7。主导航包含 `/`、`/analysis`、`/yearly-review`、`/billboard`、`/account`、`/settings`（顺序：总览 → 分析 → 年度回顾 → Billboard → 账号 → 设置）；播放分析使用 `/analysis/stats`（总体统计）与 `/analysis/charts`（个人排行榜）；音乐实体详情使用全局 `/music/tracks/:trackId`、`/music/albums/:albumName`、`/music/artists/:artistName`，旧 `/billboard/track|album|artist/*` 仅做兼容跳转。页面组件均通过 `React.lazy()` 路由级分包，首屏只下载当前路由代码
- **图表**：ECharts 6 + echarts-for-react（月度趋势图、排名趋势图、发行周期图）；图表库通过组件内动态 import 按需加载。平台分布使用纯 DOM 进度条
- **字体**：Inter Variable（`@fontsource-variable/inter`）+ Playfair Display（Google Fonts CDN）
- **国际化**：中文简繁转换（opencc-js），`displayName()` 覆盖所有页面的名称展示；OpenCC 转换器按需动态 import，默认「原文」模式不加载大字典包，切换简/繁后通过事件触发页面重渲染
- **日期工具**：date-fns + react-day-picker（日历周选择器，`Popover` + `Calendar` 弹窗跳转）
- **客户端缓存**：模块级变量缓存 API 响应和 in-flight Promise，页面切换和后台预取不会重复请求；AppLayout 首屏渲染后延迟预取 Dashboard/Billboard 常用数据；Analysis 统计页等设置读取完成后再请求，避免默认参数重复请求；BillboardPage/NumberOnesPage/AllTimeChartsPage 使用模块级变量记忆 Tab/筛选/排序/翻页状态，导航返回后自动恢复；RecordsPage 复用 Billboard 模块级缓存；年度回顾使用序列化预取（`for...of` + `await`）避免并发请求触发 SQLite 锁竞争导致 500 错误

**目录结构**：
```
frontend/src/
├── api/              ← API 客户端与错误模型
│   ├── client.ts     ← 类型化 API 客户端（30s 超时、AbortController、错误分类）
│   ├── errors.ts     ← ApiError / NetworkError / AuthRequiredError / TimeoutError
│   └── generated/    ← OpenAPI 自动生成的 TypeScript 类型（npm run generate-types）
│       ├── api-types.ts   ← 全量 API DTO 类型（95 端点）
│       └── openapi.json   ← OpenAPI spec 快照（离线对比用）
├── features/         ← Feature-first 业务组件（新增）
│   ├── settings/components/  ← 设置页 7 个 Section 组件（SpotifyConnection / DataFiltering / BillboardParams / VersionMerge / DataImport / LLMTranslation / SettingsHelpers）
│   └── account/collection/   ← 收藏分析 11 个业务组件（PersonalityHero / CollectionOverview / FirstSaveStory / SaveLifecycle / Chemistry / FlipSideAndMigration / Leaderboard / SavedTracksBrowser / PlaylistsBrowser / NotAvailable + formatDate 工具）
├── components/
│   ├── ui/          ← shadcn/ui 组件（可随意修改，含 calendar, popover）
│   ├── charts/      ← ECharts 封装（动态 import）+ 纯 DOM 图表（RankTrendChart：时间线填充断档周、全貌/细节缩放切换+dataZoom滑块、峰值Pin标记+连续冠周markArea色带；ReleaseTimelineChart：发行周期排名趋势图）
│   ├── layout/      ← 布局（AppLayout, Masthead, ThemeToggle）
│   └── shared/      ← 共享组件（GlassCard, KpiCard, WeekSelector 含日历弹窗, NoiseOverlay, PageSwitcher, ChangeCell, CoverCell, ArtistEnrichmentView, AlbumEnrichmentView, KeyFactsCard, StatsGrid, CareerTimeline, GenreTags, ChartBars, FormattedText）
├── pages/           ← 页面组件
│   ├── DashboardPage.tsx    ← 总览仪表盘（动态数据洞察：月度趋势 + 聆听高峰智能分析）
│   ├── YearlyReviewPage.tsx ← 年度回顾（2 Tab：自定义年度总结 + 官方 Wrapped，年份选择器 + 序列化预取 + ErrorBoundary 容错）
│   ├── yearly-review/       ← 年度回顾子组件（12 个）
│   ├── BillboardPage.tsx    ← Billboard 周榜（3 Tab + 排名表 + CoverCell 封面 + 详情链接，Tab 记忆跨页面保持）
│   ├── NumberOnesPage.tsx   ← 每周榜首（3 子 Tab，年度筛选 + KPI 卡片 + 冠单表 + 排行 + 柱状图）
│   ├── AllTimeChartsPage.tsx ← Billboard 总榜（3 实体 Tab，8 列头排序 + 排名峰值筛选 + 翻页）
│   ├── RecordsPage.tsx      ← 榜单记录（6 大展区 37 项记录）
│   ├── TrackDetailPage.tsx  ← 单曲详情（3 Tab：榜单表现/歌词/Wikipedia 百科）
│   ├── ArtistDetailPage.tsx ← 艺人详情（4 Tab：榜单表现/单曲成绩/专辑成绩/歌手生涯）
│   ├── AlbumDetailPage.tsx  ← 专辑详情（3 Tab：榜单表现/曲目表现/专辑百科）
│   ├── SettingsPage.tsx     ← 设置（容器组件：组合 7 个 feature section 组件）
│   ├── AccountCenterPage.tsx ← 账号中心（2 Tab：你的收藏 / 你的习惯）
│   └── account/              ← 账号中心子组件（HabitsTab, CollectionTab — CollectionTab 为 48 行容器，业务组件在 features/account/collection/）
├── hooks/           ← 自定义 hooks（useTheme, useDashboard, useBillboard, useYearlyReview, useSettings, useAccount）
├── lib/             ← API 客户端、工具函数
│   ├── api.ts       ← 向后兼容重导出（→ @/api/client）
│   ├── theme.ts     ← 图表色盘常量 + getChartColors(isDark)
│   ├── utils.ts     ← cn() 工具（tailwind-merge + clsx）
│   ├── chinese.ts   ← 中文简繁转换（opencc-js 动态加载），displayName() 统一入口
│   ├── insights.ts  ← 动态洞察生成（月度趋势季节分析 + 聆听高峰智能识别）
│   ├── personality-themes.ts ← 听歌人格主题定义（6 种人格 × 渐变配色）
│   └── genre-regions.ts ← 曲风五大洲地理映射
├── tests/           ← 前端测试（vitest + React Testing Library）
│   ├── FormattedText.test.tsx  ← 纯文本/markdown 渲染/XSS 防护
│   ├── api-errors.test.ts      ← ApiError/NetworkError/AuthRequiredError/TimeoutError
│   └── utils.test.ts           ← cn() 工具函数
├── types/           ← TypeScript 手写展示类型
│   ├── dashboard.ts ← Dashboard 响应类型
│   ├── billboard.ts ← Billboard 响应类型
│   ├── settings.ts  ← 设置
│   ├── account.ts   ← 账号中心
│   └── yearly-review.ts ← 年度总结完整类型
└── UI_STYLE_GUIDE.md ← 详细 UI 风格指南（新增页面必读）
```

**前端 API 错误模型**（`@/api/errors.ts`）：类型化错误替代原有通用 `throw new Error('API error: ...')`。`ApiError` 基类（status + detail + cause + isAuthError/isNotFound/isServerError 属性）；`NetworkError`（status=0，fetch 失败）；`AuthRequiredError`（status=401）；`TimeoutError`（status=408，30s 默认超时可配置）。

**前端测试**：vitest + React Testing Library（jsdom 环境），3 个测试文件共 20 个单测。`npm test`（vitest run）或 `npm run test:watch`（vitest 交互模式）。

**OpenAPI 类型自动生成**：`npm run generate-types` 从运行中后端 `/openapi.json` 拉取 spec 并生成 `src/api/generated/api-types.ts`。`npm run check-types-fresh` 对比本地快照与后端 spec 检测漂移。

**路径别名**：`@/` → `src/`（Vite resolve.alias + tsconfig paths）。

**shadcn/ui 主题**：CSS 变量定义在 `src/index.css`，`components.json` 记录配置。已安装的组件：button, card, table, tabs, select, slider, separator, skeleton, tooltip, badge, avatar, sheet, collapsible, dropdown-menu, scroll-area, calendar, popover。

**UI 风格指南**：`frontend/UI_STYLE_GUIDE.md` 包含完整的颜色系统、字体规格、布局模式、组件 API 和页面模板。新增页面时必须参考此文档。

### Streamlit 应用 (app/)

以下为原有 Streamlit 架构文档，在 React 前端构建完成前仍为主要的用户界面。

#### 核心模块

- **`app/db.py`** — 数据库层。`get_db()` 获取连接（默认只读，WAL模式），`base_filters()` 生成标准 WHERE 条件片段（最短时长 + 仅音乐，已移除不可靠的 skipped 过滤），`load_plays()` 统一数据加载入口（4 表 JOIN + 过滤），`merge_consecutive_plays()` 合并连续同曲目播放为逻辑播放次数（先合并再过滤，避免碎片丢失）。`ensure_schema()` 增量升级 schema（新增表/索引/列安全重复执行），所有统计页面通过此函数统一过滤逻辑。预聚合表 `agg_weekly_{tracks,albums,artists}` + `agg_config` 存储 Billboard 预计算结果，参数变更时通过参数哈希自动失效回退实时计算。`release_groups` + `release_group_members` 表管理专辑版本合并关系；`spotify_album_meta` 新增 `total_tracks` 和 `track_list` 列用于版本合并超集检测。
- **`app/import_data.py`** — 串流数据 ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track，以 `(artist_id, track_name)` 为 key 合并重复版本），同步写入 `track_albums` 关联表，事实表 5000 行批量插入。
- **`app/import_account_data.py`** — 账号数据 ETL 管线。从 Spotify Account Data 包中导入：搜索历史（`search_queries`）、收藏（`saved_tracks`/`saved_albums`/`saved_artists`）、播客（`podcast_plays`/`podcast_interactions`/`saved_shows`）、播放列表（`playlists`/`playlist_tracks`）、社交（`user_follows`）、个人资料（`user_profile`）、Marquee 推广（`marquee_impressions`）、Wrapped 年度回顾（各种 `wrapped_*` 表）、黑名单（`banned_items`）。
- **`app/utils.py`** — `convert_to_local_time()` 固定使用北京时间（UTC+8），忽略 Spotify 上报的 `conn_country` 字段（因 VPN/网络路由可能导致该字段不准确）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/styles.py`** — 全局 CSS 注入。「Vinyl Archive」暖色主题：CSS 变量（`--gold`/`--bg-page`/`--bg-card` 等）、噪点纹理背景、卡片金左边线、衬线字体、表头暖金底色、侧边栏牛皮纸色。`page_header()` 和 `kpi_row()` 辅助函数供各页面统一使用。`PLOTLY_TEMPLATE` 定义全局 Plotly 图表样式（含 legend title 修复），`COLORS` 定义暖色色盘。
- **`app/version_merge.py`** — 版本合并引擎。`detect_release_groups()` 自动检测同名专辑的不同版本（豪华版、Acoustic版等），通过曲目重叠率（Phase 1）和名称归一化（Phase 2）判定合并候选；`apply_detected_groups()` / `create_group()` / `delete_group()` / `update_group_members()` 管理 release groups；`get_album_track_comparison()` 对比两版本曲目差异（共享/独有/加曲）。- **`app/main.py`** — 入口 + 总览仪表盘。使用 `st.navigation` + `st.Page` 定义全站导航结构（中文侧边栏标签/英文文件名），`dashboard()` 函数包含仪表盘全部内容。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `music_only`, `merge_enabled`），侧边栏展示当前参数摘要和数据库状态，首次运行时自动触发数据导入。
- **`app/pages/09_settings.py`** — 总设置页。集中管理数据过滤（最短播放时长/仅音乐/合并连续播放）、Billboard 三个榜单独立 Top N（`bb_top_n` 单曲 / `bb_album_top_n` 专辑 / `bb_artist_top_n` 艺人）、统计周期边界（`bb_week_start_dow`/`bb_week_start_hour`）、版本合并管理（自动检测/手动创建/已保存组管理）、数据导入。任何参数变更时自动清除全局缓存并重跑，确保所有页面数据一致。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。`track_albums` 关联表处理同一歌曲（同艺人+同曲名）出现在多张专辑的情况，`_cache_track` 以 `(artist_id, track_name)` 为唯一标识合并重复版本。维度表仅保留核心识别字段，Spotify API 元数据（专辑类型、发行日期、热度、厂牌、曲风、封面图、总曲目数 `total_tracks`、曲目列表 `track_list` 等）独立存储在 `spotify_album_meta`/`spotify_artist_meta`/`spotify_track_meta` 三张表中，通过 `spotify_track_uri` 链式关联。`release_groups` + `release_group_members` 两张表管理专辑版本合并（豪华版、Acoustic版等合并为 canonical 名称），`version_merge.py` 提供自动检测和手动管理功能。

`albums` / `artists` 表新增 `image_url`（Spotify CDN URL）和 `image_path`（本地相对路径）列，封面通过 `/covers/{type}/{id}.jpg` 端点服务。`scripts/fetch_covers.py` 批量拉取并缓存封面，支持增量更新。

`plays` 表预计算了时间字段（`ts_year`, `ts_month`, `ts_week`, `ts_dow`, `ts_hour`, `ts_date`），均为本地时间（固定北京时间 UTC+8）。所有 `boolean` 字段用 INTEGER 0/1 存储。

账号数据表独立于串流事实表：`saved_tracks`/`saved_albums`/`saved_artists`（收藏）、`playlists`/`playlist_tracks`（播放列表）、`search_queries`（搜索历史）、`podcast_plays`/`podcast_interactions`/`saved_shows`（播客）、`user_follows`/`user_profile`（社交与个人资料）、`marquee_impressions`（推广展示）、`wrapped_*`（官方 Wrapped 数据）、`banned_items`（黑名单）。

### 页面结构

使用 `st.navigation` + `st.Page` 统一管理侧边栏导航，文件名保持英文（兼容性），侧边栏显示中文标签。`main.py` 为入口，定义所有页面的导航结构和中文标题；每个页面文件作为独立的 MPA 脚本运行。

侧边栏共 6 个入口（3 个 wrapper + Billboard + 设置 + 首页），Wrapper 页面使用 `importlib.util.spec_from_file_location()` 动态加载数字前缀命名的原始页面模块：

```
侧边栏:
├── 总览仪表盘 (main.py, default)
├── 播放分析 (02_playback.py)       ← 5 Tab: 时间线 / 排行榜 / 行为分析 / 听歌时段 / 艺人深潜
├── 年度回顾 (03_yearly.py)         ← 2 Tab: 自定义年度总结 / Wrapped 2025 官方
├── Billboard 周榜 (08_billboard.py) ← 12 Tab，委派至 billboard/ 包
├── 账号中心 (04_account.py)        ← 6 Tab: 音乐库 / 搜索编年史 / 音乐画像 / 播客专区 / 视频分析 / 个人档案
└── 设置 (09_settings.py)
```

每个原始页面暴露 `render()` 函数，由 wrapper 在对应 Tab 内调用。`st.stop()` 均改为 `return`，避免 Tab 内警告波及整个 wrapper。

`08_billboard.py` 为薄入口（15 行），委派至 `app/pages/billboard/` 模块化包（18 个文件，~9,000 行）：

```
app/pages/billboard/
├── __init__.py          # 主路由 + session_state 初始化 + query_params 处理
├── shared.py            # 公共数据加载 + 排名计算 + 版本合并（_normalize_album_column / _apply_album_release_groups / _resolve_album_members / _add_canonical_metadata）+ _bb_url + _render_bb_table
├── weekly.py            # Tab 1: 周榜（单曲/专辑/艺人 3 子 Tab）+ ◀▶ 快速切周 + 截至当周滚动 Peak/Wks/Pk Wks
├── number_ones.py       # Tab 2: 每周榜首 + 冠单排行 + 空冠 + 大盘
├── track_history.py     # Tab 3: 单曲历史 + 升降列（断档 >8 天显示 RE，连续在榜正常计算升降）
├── artist_chart.py      # Tab 4: 艺人榜单 + 艺人周榜历史（含升降列，断档显示 RE）
├── album_chart.py       # Tab 5: 专辑榜单 + 专辑周榜历史（含升降列，断档显示 RE，支持版本合并）
├── power_score.py       # Tab 6: 走势总榜（歌曲/专辑/艺人 Power Score）
├── all_time_tracks.py   # Tab 7: 歌曲总榜
├── all_time_artists.py  # Tab 8: 艺人总榜
├── all_time_albums.py   # Tab 9: 专辑总榜
├── records.py           # Tab 10: 榜单记录（6 大展区 37 项记录）
├── versus.py            # Tab 11: 对决（歌曲/专辑/艺人对决对比，支持版本合并）
└── release_cycle/       # Tab 12: 发行周期分析
    ├── __init__.py       # 主路由 + 艺人选择器 + 三个视图切换（st.session_state）
    ├── shared.py         # 数据加载（load_artist_releases / _ad_hoc_name_grouping / _filter_release_group_duplicates）+ 指标计算 + 先行曲识别（三级查找：DB → Spotify API → 最早播放日期）+ Spotify API 集成
    ├── artist_view.py    # 视图①：艺人总览（KPI 卡片、排名趋势图 + 发行事件标记、发行卡片流、对比入口）
    ├── album_view.py     # 视图②：专辑下钻（周期曲线仅连续周连线、先行曲/最佳单曲单曲榜排名线、歌曲入榜矩阵、老歌回榜、加曲来源）
    └── compare_view.py   # 视图③：多发行周期叠加对比（排名/播放量曲线 + 指标对比表）
```

每个模块暴露 `render(df, weekly, ...)` 函数，由 `__init__.py` 传递所需数据。`st.session_state` 实现跨 Tab 导航、子 Tab 记忆、周选择器位置记忆。

### 数据过滤策略

通过「⚙️ 设置」页面集中管理，参数存入 `st.session_state` 供所有页面读取。变更时自动 `st.cache_data.clear()` + `st.rerun()`，确保 Billboard 等页面拿到全新数据。

两个过滤条件：
- **`ms_played >= min_ms`**（默认 30s）：过滤过短的播放，仅此一个硬过滤条件
- **`music_only`**：排除播客/有声书（`track_id IS NOT NULL`）
- 已移除 `skipped` 过滤——`skipped` 和 `reason_end` 字段反映按钮行为而非收听行为，不可靠

合并连续播放（`merge_enabled`，默认开启）：先合并再过滤，将连续同曲目记录拼接为逻辑播放次数，避免碎片化片段被误丢弃。可关闭以保留原始逐条计数。

`base_filters()` 是唯一的过滤入口，修改此函数即可影响所有统计页面。

**特殊页面过滤策略：**
- 行为分析（`04_behavior.py`）：使用全量数据（`filtered=False, music_only=False`），保证快进/隐身/随机播放等分析准确性
- 视频分析 + 播客聆听（`video_service.py` / `podcast_service.py`）：额外过滤 `ms_played >= 30000`（30 秒），排除滑动/自动预览的噪音
- Billboard 专辑榜（`billboard/shared.py`）：通过 `_load_album_metadata()` 从 `spotify_album_meta` 获取类型和发行日期，排除 `album_type = 'single'` 的发行，以及专辑发行日之前的周数（同一专辑的单曲提前发行不计入专辑榜）
- 播客专区、音乐画像等账号数据页面：直接查询各自独立的账号数据表，不经过 `base_filters()`

## 技术约束

- Python 3.9 — 使用 `Optional[X]` 而非 `X | None`，`dict[str, int]` 可用
- **后端**：使用标准 Python 绝对导入（`from backend.core.db import get_db`），uvicorn 自动处理模块路径
- **Streamlit**：`sys.path.insert(0, ...)` 在每个文件顶部，因为 Streamlit 运行时项目根目录不在 path 中
- SQLite 数据库文件位于 `data/spotify_stats.db`，由 `.gitignore` 排除
- 数据文件夹结构：`data/streaming/`（长期串流记录）、`data/account/`（账号数据），详见 `data/README.md`
- 数字前缀文件名（如 `02_timeline.py`）通过 `importlib.util.spec_from_file_location()` 动态加载，不要在 wrapper 中直接 `import`
- FastAPI `:path` 参数是贪婪匹配的，含子路径的路由（如 `/artist/{name:path}/album/{album_name:path}`）必须注册在更泛化的路由之前
- `backend/core/json_helpers.py` 是所有 numpy/pandas → JSON 序列化的唯一入口，不要在 service 层重复定义 `_py_val` / `_df_to_json`
- 缓存服务函数使用 `@lru_cache` 时，内部必须调用 `get_db()` 获取连接（连接对象不可哈希）；非缓存服务从 API 层接收 `conn` 参数
- 对昂贵缓存函数，优先通过公开 wrapper 规范化参数后再进入内部 cached 函数，避免位置参数/关键字参数造成重复 cache key；并考虑 `singleflight()` 避免首次并发重复计算
- `ttl_cached()` 不缓存 `None`，外部 API 瞬时失败应允许后续请求重试；测试中可调用包装函数的 `cache_clear()`
- **Spotify OAuth**：开发环境需要 HTTPS 回调 URL。使用 ngrok 静态域名（`stuffing-nebula-tamer.ngrok-free.dev`）提供公网 HTTPS 隧道代理到 localhost:5173 Vite 开发服务器。Spotify API scope 变更后已有 token 不会自动升级，需断开重连。Redirect URI 在 `.env` 的 `SPOTIFY_REDIRECT_URI` 和 Spotify Developer Dashboard 中需同步更新
- Vite 开发服务器需设置 `allowedHosts: true` 以允许 ngrok 域名的外部请求
- **安全约束**：
  - 所有环境变量统一通过 `backend/core/config.py` 读取，禁止在业务代码中直接 `open('.env')` 或 `os.getenv()`
  - Spotify OAuth Token 在 SQLite 落库前必须经过 `crypto.encrypt()` 加密，读取时通过 `crypto.is_encrypted()` 自动判断并解密（兼容旧明文自动迁移）
  - LLM API Key 永远不通过 API 返回给前端；`GET /api/settings/llm-profiles/{id}` 仅返回 `has_llm_key: bool`；前端通过 `POST /apply` 端点让服务端直接写入 settings
  - 外部文本（LLM 输出、Wikipedia、翻译结果）在前端渲染必须经过 `react-markdown` + `rehype-sanitize`，禁止 `dangerouslySetInnerHTML`
  - 远程模式（`SPOTIFY_STATS_REQUIRE_AUTH=1`）下所有写/敏感接口必须通过 `require_auth` 依赖校验 Bearer Token
  - 日志系统通过 `SensitiveDataFilter` 自动脱敏 API Key、Token 等敏感字段；全局异常处理器返回通用 500 不泄露 stack trace
  - Token 加密密钥优先级：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 应用内置密钥。单用户本地场景可接受内置密钥，多用户/远程部署必须设置环境变量

## Legacy 模块（Streamlit 旧应用）

`app/` 目录下的 Streamlit 应用已于 2026-05-30 进入**冻结维护**状态：

- **只修严重 bug，不新增功能**。所有新功能进入 FastAPI (backend/) + React (frontend/)。
- Streamlit 仍可正常运行（`streamlit run app/main.py`），但不作为主要开发入口。
- `app/` 与 `backend/` **无代码交叉依赖**，仅共享 `data/spotify_stats.db` 数据库文件。
- 如需修改 Streamlit 页面，优先评估是否可在 FastAPI + React 中实现。
- 迁移理由详见 `docs/ARCHITECTURE_OPTIMIZE.md`。
