# Backend Architecture

> 项目级上下文（Phase 5 基线、架构模式、提交规范）见根目录 `AGENTS.md`。

FastAPI 后端采用四层分离：**api/**（路由 + Depends 依赖注入）→ **services/**（计算逻辑）→ **domains/**（领域模块）→ **core/**（工具层），辅以 **infrastructure/**（基础设施）和 **providers/**（第三方适配）。

## 路由层约定

### 依赖注入 (`backend/dependencies.py`)

- `PlayFilters` — 标准播放过滤（`min_ms`, `music_only`, `merge_enabled`, `dynamic_threshold`, `max_merge_gap_minutes`）
- `BillboardFilters` — 继承播放过滤 + Billboard 参数（`bb_top_n`, `bb_week_start_dow`, `year_start/end`）
- `MergeConfig` — 版本合并严格度（`merge_level`: 1=不合并, 2=recording scope, 3=composition+recording scope）
- `get_conn()` — 数据库只读连接注入
- 暴露 `PlayFilters` / `BillboardFilters` 的统计路由必须把 `dynamic_threshold` 与 `max_merge_gap_minutes` 传到最终 `load_plays()` / `load_billboard_raw()` 路径；新增入口应补传播契约测试或复用已有 service 管线

### 连接管理

- API 层：通过 `Depends(get_conn)` 注入，请求结束自动关闭
- 非缓存服务：接收 `conn` 参数从 API 层传入
- 缓存服务（`@lru_cache` / `@ttl_cached`）：内部调用 `get_db()`（连接不可哈希）
- 端点模式：`def endpoint(filters: PlayFilters = Depends(), conn: Connection = Depends(get_conn)):`

### 路由注册注意

- FastAPI `:path` 贪婪匹配，含子路径路由必须注册在泛化路由之前
- 所有路由通过 `backend/api/router.py` 组装，挂载 `/api` 前缀

## 核心模块

| 文件 | 职责 |
|------|------|
| `core/config.py` | 集中配置管理（`python-dotenv`），禁止业务代码直接 `os.getenv()` |
| `core/db.py` | `get_db()`, `load_plays()` / `load_plays_for_artists()` (`@lru_cache(maxsize=16)` + `singleflight()`), `base_filters()`, 向量化 `merge_consecutive_plays()`, `build_aggregations()` |
| `domains/billboard/chart_summaries.py` | Billboard track/artist/album summary 与 counts；best peak track 使用排序 + merge，禁止 row-wise `DataFrame.apply(axis=1)` |
| `core/crypto.py` | AES-256-GCM 加解密，Token 落库前必须加密，`is_encrypted()` 自动区分明文/密文 |
| `core/json_helpers.py` | numpy/pandas → JSON 唯一入口（`py_val()` / `df_to_json()`），禁止 service 层重复定义 |
| `core/cache.py` | `ttl_cached()` 装饰器（不缓存 None）+ `singleflight()` 避免并发重复计算 |
| `core/cache_manager.py` | 5 命名空间（billboard/analysis/db/auth）统一管理，设置/导入/版本合并变更自动失效 |
| `core/migrations.py` | 版本化 Migration，`IF NOT EXISTS` 幂等，`schema_migrations` 表追踪 |
| `core/auth.py` | `require_auth()` 依赖，本地模式放行，远程模式校验 Bearer Token |
| `core/logging_config.py` | `SensitiveDataFilter` 脱敏敏感字段，全局 500 不泄露 stack trace |
| `core/request_context.py` | Request ID 上下文（`ContextVar`），响应返回 `X-Request-ID`，日志包含 request id |
| `core/warmup.py` | 启动后台预热 Billboard + Dashboard + artist fan-out 缓存；默认使用当前前端过滤口径（`dynamic_threshold=True`），`SPOTIFY_STATS_WARMUP=0` 可关闭 |
| `core/job_queue.py` | 3 worker 线程池 + `background_jobs` 表持久化，enrichment 用 stale-cache+refresh 模式 |
| `core/spotify_utils.py` | OAuth PKCE + Token 加密持久化 + 自动刷新 + 10 scope 全量数据拉取 |

## 服务层

| 文件 | 职责 |
|------|------|
| `services/play_service.py` | 核心播放数据服务，所有基于 plays 的端点统一入口；负责播放过滤参数贯穿 |
| `services/analysis_stats_service.py` | 总体统计 + 个人排行榜 + 时间范围解析 |
| `services/entity_stats_service.py` | 歌曲/专辑/艺人个人播放统计 |
| `services/wrapped_service.py` | 自定义年度总结（听歌人格/Top榜/曲风全景/发现回归等） |
| `services/billboard_service.py` | Billboard facade（~100行），实现已迁入 `domains/billboard/` |
| `services/release_cycle_service.py` | 发行周期分析 + Spotify API + 先行曲识别 |
| `services/genius_service.py` | Genius 歌词获取 + SQLite 缓存，懒加载单例 |
| `services/wikipedia_service.py` | Wikipedia 搜索/提取/缓存/翻译/LLM 结构化 |
| `services/llm_translator.py` | 多提供商 LLM 翻译与结构化（DeepSeek/OpenAI/Anthropic/自定义） |
| `services/ai_insights_service.py` | AI 洞察：周报/月报/年度叙事 + 自然语言问答 + 推荐问题随机池（复用 LLM 基建 + wikipedia_cache 表） |
| `services/chat_service.py` | 对话历史管理：会话 CRUD + 消息持久化 + 自动标题（取首条用户消息前 30 字符） |
| `services/spotify_auth.py` | OAuth PKCE 授权与数据同步 |
| `services/account_service.py` | 账号中心聚合（收藏分析 + 搜索/习惯） |

## 领域层 (domains/)

- `domains/billboard/` — `data_loader.py` / `chart_compute.py`（编排/re-export/cache registration facade）+ `chart_load_rank.py`（共享 `_load_and_rank_cached`）+ `chart_ranking.py`（周榜排名）+ `chart_power_score.py`（走势评分，列级向量化）+ `chart_staged_cache.py`（weekly/power/summaries/records 分段缓存）+ `chart_staged_api.py`（公开 staged wrapper）+ `records.py`（facade）+ `records_*.py`（record 子模块）+ `details.py` / `versus.py` / `entity_lists.py` / `repository.py` / `version_merge.py`
- `domains/settings/repository.py` — Settings 表 CRUD
- `domains/playback/` — `repository.py`（播放数据查询封装）/ `counting.py`（有效播放判定）/ `merge_levels.py`（L1/L2/L3 规范化）/ `track_groups.py`（track group 聚合键加载）/ `release_groups.py`（发行版本关系）/ `album_projects.py`（L2/L3 专辑项目 membership、source breakdown、Billboard release-date eligibility）/ `album_type.py`（专辑类型分类）
- `domains/enrichment/repository.py` — 歌词/Wikipedia/LLM 缓存表访问
- `domains/community/` — 榜单社区模拟 X 时间线：`accounts.py`（10 个模拟资讯账号）+ `post_types.py`（18 种帖子类型/7 种精选类型/模板/评分）+ `historical_state.py`（逐周累计历史状态追踪器，去重计数）+ `feed_generator.py`（编排器，~600 行）+ `feed_helpers.py`（格式/ID/指标工具）+ `feed_data.py`（榜单数据加载）+ `feed_weekly.py`（每周速报）+ `feed_records.py`（纪录/里程碑）+ `feed_personal.py`（个人播放/收藏）+ `feed_talk.py`（深度分析）+ `feed_ranking.py`（全时期排名/Power Score）+ `feed_images.py`（封面匹配）
- `domains/chat/repository.py` — 对话历史持久化：`ChatRepository` 类封装 `chat_sessions`/`chat_messages` 表 CRUD，`ON DELETE CASCADE` 删除会话自动清消息

## 外部调用规范

**Phase 5 强制约束**：所有第三方 API 通过 `providers/` 发出，禁止业务代码散落请求逻辑。

- `providers/spotify/client.py` — Spotify API
- `providers/genius/client.py` — Genius API
- `providers/wikipedia/client.py` — Wikipedia REST API
- `providers/llm/client.py` — 多后端 LLM（DeepSeek/OpenAI/Anthropic/自定义）
- `providers/base.py` — Provider 错误分类：`ProviderError` → `ProviderNetworkError` / `ProviderHTTPError` → `ProviderAuthError` / `ProviderRateLimitError` / `ProviderServerError` + `ProviderParseError`
- `infrastructure/http/client.py` — 统一 HTTP 客户端（timeout/retry/proxy/脱敏），网络失败映射为 `ProviderNetworkError`
- `backend.main` — `ProviderError` 全局异常处理器，将上游失败映射为结构化 429/503/502 响应并保留 `X-Request-ID`，不向前端泄露原始上游错误文案

**业务 service 层和 core Spotify 路径不得直接新建 `urllib.request.Request`/`urlopen`**，必须经 `HttpClient` 或对应 Provider。

## 测试策略

三层 pytest markers：`unit`（纯函数，无 DB，~5s）→ `contract`（seed DB 结构验证，~1s）→ `integration`（真实数据只读，~80s）。当前基线：unit 264 / contract 170 / backend full 634。`scripts/ci_baseline_parity.py` 校验 GitHub Actions Phase 5 baseline 的核心检查命令已被本地 `scripts/phase5_check.sh` 覆盖，且 `phase5_check.sh` 会先运行该护栏。全栈非破坏性验收矩阵入口是 `sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173`，需先启动后端和前端，可选 `--preview-url` 与 `--web-vitals`；preview route/chart/long-list smoke 会用 `--preview-api-url` 将 `/api` 与 `/covers` 请求转发到后端；该脚本会在激活 `.venv` 前自动检测可导入 `playwright.sync_api` 的 Python，也可通过 `PYTHON_PLAYWRIGHT=/path/to/python` 指定。补充只读 API smoke 使用 `.venv/bin/python scripts/api_smoke_probe.py`，覆盖 96 个本地 GET、验证 `X-Request-ID`，并核算 OpenAPI GET 覆盖（未核算路径必须为 0）；非破坏性 API 边界 probe 使用 `.venv/bin/python scripts/api_boundary_probe.py`，覆盖 19 个 GET 边界（越界参数、非法 path/entity、特殊字符查询、422 validation detail 与 `X-Request-ID`）；Provider 错误响应 probe 使用 `.venv/bin/pytest backend/tests/contract/test_provider_error_responses.py -q`，覆盖六类上游失败到结构化 429/503/502 响应的映射；Billboard enrichment 降级 probe 使用 `.venv/bin/pytest backend/tests/contract/test_billboard_enrichment_contract.py -q`，覆盖专辑/艺人/歌曲可选 Wiki 增强普通异常返回空增强而非 500；response-model probes 使用 `.venv/bin/pytest backend/tests/contract/test_infrastructure_response_models.py backend/tests/contract/test_settings_api_mutations.py backend/tests/contract/test_spotify_auth_contract.py backend/tests/contract/test_account_center_response_models.py backend/tests/contract/test_core_stats_response_models.py backend/tests/contract/test_remaining_json_response_models.py -q`，覆盖 health/cache/import/job 6 个基础设施端点、settings mutation 6 个写端点、Spotify auth 7 个 JSON 端点、账号中心/画像 12 个 GET 端点、核心统计 6 个 GET 端点和 release-cycle/lyrics 3 个剩余 JSON 端点的 FastAPI route 与 OpenAPI 200 schema；API 性能 benchmark 使用 `.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500`，覆盖 8 个核心 API 的冷/热响应、raw/gzip 体积和 hot P95 慢端点汇总，并可用 `--json-output` 输出机器可读报告；前端 route smoke 使用 `node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0` 覆盖 19 个默认路由，生产 preview 可用 `--api-base-url http://127.0.0.1:8000` 显式转发 API；前端非破坏性交互 smoke 使用 `node scripts/frontend_interaction_smoke.mjs` 覆盖分析 tab、Billboard 子路由/历史导航、AI Insights tab/空状态、Settings 控件与主题切换；图表交互 smoke 使用 `node scripts/frontend_chart_interaction_smoke.mjs` 覆盖 ECharts tooltip hover、legend toggle 与 dataZoom drag，生产 preview 可用 `--api-base-url http://127.0.0.1:8000` 显式指定后端；长列表 smoke 使用 `node scripts/frontend_long_list_smoke.mjs` 覆盖 Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 的分页或分段渲染窗口变化，生产 preview 可用 `--api-base-url http://127.0.0.1:8000` 将 `/api` 与 `/covers` 请求转发到后端；跨浏览器 smoke 使用 `node scripts/frontend_cross_browser_smoke.mjs` 覆盖 Chromium/Firefox/WebKit 三引擎。本地 mutation/基础设施优先在 contract 临时 DB 里验证，例如 Chat CRUD、Settings 更新、LLM profile CRUD/apply、Spotify auth JSON 端点、AI Insights 生成端点、Import job 调度，以及 Spotify OAuth PKCE login/callback 加密落库与 invalid state。

Contract 测试使用 canonical `backend/tests/fixtures/seed.db` 的临时副本，teardown 必须清除所有 `@lru_cache` 并删除临时 WAL/SHM sidecar；`autouse` fixture `disable_warmup` 通过 monkeypatch `SPOTIFY_STATS_WARMUP=0` 阻止后台预热。

## 关键约束

- Python 3.9：使用 `Optional[X]` 而非 `X | None`
- 后端绝对导入：`from backend.core.db import get_db`
- 昂贵缓存优先通过公开 wrapper 规范化参数 + `singleflight()` 避免并发重复
- L2/L3 专辑统计必须走 album project track membership；source album 只作为来源拆分解释，不得重新作为专辑播放量聚合口径
- `ttl_cached()` 不缓存 `None`，测试可调 `cache_clear()`
- 环境变量统一从 `core/config.py` 读取，禁止业务代码直接 `os.getenv()`
- Token 加密密钥：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥（仅限单用户本地）
- LLM API Key 永远不通过 API 返回前端
- **新增外部 HTTP 调用必须走 Provider/HttpClient**；禁止业务 service 和 core 直接 `urllib.request.Request`/`urlopen`
- 日志输出必须经 `SensitiveDataFilter` 脱敏，不打印 token/key/Authorization
- 开发用 `--reload-dir backend`，避免 reloader 扫描 `.venv`/`node_modules`/`data`
