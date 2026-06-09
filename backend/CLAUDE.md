# Backend Architecture

> 项目级上下文（Phase 5 基线、架构模式、提交规范）见根目录 `AGENTS.md`。

FastAPI 后端采用四层分离：**api/**（路由 + Depends 依赖注入）→ **services/**（计算逻辑）→ **domains/**（领域模块）→ **core/**（工具层），辅以 **infrastructure/**（基础设施）和 **providers/**（第三方适配）。

## 路由层约定

### 依赖注入 (`backend/dependencies.py`)

- `PlayFilters` — 标准播放过滤（`min_ms`, `music_only`, `merge_enabled`）
- `BillboardFilters` — 继承播放过滤 + Billboard 参数（`bb_top_n`, `bb_week_start_dow`, `year_start/end`）
- `get_conn()` — 数据库只读连接注入

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
| `core/db.py` | `get_db()`, `load_plays()` (`@lru_cache(maxsize=16)`), `base_filters()`, `merge_consecutive_plays()` |
| `core/crypto.py` | AES-256-GCM 加解密，Token 落库前必须加密，`is_encrypted()` 自动区分明文/密文 |
| `core/json_helpers.py` | numpy/pandas → JSON 唯一入口（`py_val()` / `df_to_json()`），禁止 service 层重复定义 |
| `core/cache.py` | `ttl_cached()` 装饰器（不缓存 None）+ `singleflight()` 避免并发重复计算 |
| `core/cache_manager.py` | 5 命名空间（billboard/analysis/db/auth）统一管理，设置/导入/版本合并变更自动失效 |
| `core/migrations.py` | 版本化 Migration，`IF NOT EXISTS` 幂等，`schema_migrations` 表追踪 |
| `core/auth.py` | `require_auth()` 依赖，本地模式放行，远程模式校验 Bearer Token |
| `core/logging_config.py` | `SensitiveDataFilter` 脱敏敏感字段，全局 500 不泄露 stack trace |
| `core/request_context.py` | Request ID 上下文（`ContextVar`），响应返回 `X-Request-ID`，日志包含 request id |
| `core/warmup.py` | 启动后台预热 Billboard + Dashboard 缓存，`SPOTIFY_STATS_WARMUP=0` 可关闭 |
| `core/job_queue.py` | 3 worker 线程池 + `background_jobs` 表持久化，enrichment 用 stale-cache+refresh 模式 |
| `core/spotify_utils.py` | OAuth PKCE + Token 加密持久化 + 自动刷新 + 10 scope 全量数据拉取 |

## 服务层

| 文件 | 职责 |
|------|------|
| `services/play_service.py` | 核心播放数据服务，所有基于 plays 的端点统一入口 |
| `services/analysis_stats_service.py` | 总体统计 + 个人排行榜 + 时间范围解析 |
| `services/entity_stats_service.py` | 歌曲/专辑/艺人个人播放统计 |
| `services/wrapped_service.py` | 自定义年度总结（听歌人格/Top榜/曲风全景/发现回归等） |
| `services/billboard_service.py` | Billboard facade（~100行），实现已迁入 `domains/billboard/` |
| `services/release_cycle_service.py` | 发行周期分析 + Spotify API + 先行曲识别 |
| `services/genius_service.py` | Genius 歌词获取 + SQLite 缓存，懒加载单例 |
| `services/wikipedia_service.py` | Wikipedia 搜索/提取/缓存/翻译/LLM 结构化 |
| `services/llm_translator.py` | 多提供商 LLM 翻译与结构化（DeepSeek/OpenAI/Anthropic/自定义） |
| `services/spotify_auth.py` | OAuth PKCE 授权与数据同步 |
| `services/account_service.py` | 账号中心聚合（收藏分析 + 搜索/习惯） |

## 领域层 (domains/)

- `domains/billboard/` — 19 文件：`data_loader.py` / `chart_compute.py`（编排/caching/staged API）+ `chart_ranking.py`（周榜排名）+ `chart_power_score.py`（走势评分）+ `records.py`（facade）+ `records_*.py`（9 个 record 子模块）+ `details.py` / `versus.py` / `entity_lists.py` / `repository.py` / `version_merge.py`
- `domains/settings/repository.py` — Settings 表 CRUD
- `domains/playback/repository.py` — 播放数据查询封装
- `domains/enrichment/repository.py` — 歌词/Wikipedia/LLM 缓存表访问

## 外部调用规范

**Phase 5 强制约束**：所有第三方 API 通过 `providers/` 发出，禁止业务代码散落请求逻辑。

- `providers/spotify/client.py` — Spotify API
- `providers/genius/client.py` — Genius API
- `providers/wikipedia/client.py` — Wikipedia REST API
- `providers/llm/client.py` — 多后端 LLM（DeepSeek/OpenAI/Anthropic/自定义）
- `providers/base.py` — Provider 错误分类：`ProviderError` → `ProviderNetworkError` / `ProviderHTTPError` → `ProviderAuthError` / `ProviderRateLimitError` / `ProviderServerError` + `ProviderParseError`
- `infrastructure/http/client.py` — 统一 HTTP 客户端（timeout/retry/proxy/脱敏），网络失败映射为 `ProviderNetworkError`

**业务 service 层和 core Spotify 路径不得直接新建 `urllib.request.Request`/`urlopen`**，必须经 `HttpClient` 或对应 Provider。

## 测试策略

三层 pytest markers：`unit`（纯函数，无 DB，~5s）→ `contract`（seed DB 结构验证，~1s）→ `integration`（真实数据只读，~80s）。

Contract 测试 teardown 必须清除所有 `@lru_cache`，`autouse` fixture `disable_warmup` 通过 monkeypatch `SPOTIFY_STATS_WARMUP=0` 阻止后台预热。

## 关键约束

- Python 3.9：使用 `Optional[X]` 而非 `X | None`
- 后端绝对导入：`from backend.core.db import get_db`
- 昂贵缓存优先通过公开 wrapper 规范化参数 + `singleflight()` 避免并发重复
- `ttl_cached()` 不缓存 `None`，测试可调 `cache_clear()`
- 环境变量统一从 `core/config.py` 读取，禁止业务代码直接 `os.getenv()`
- Token 加密密钥：`SPOTIFY_STATS_TOKEN_KEY` 环境变量 → 内置密钥（仅限单用户本地）
- LLM API Key 永远不通过 API 返回前端
- **新增外部 HTTP 调用必须走 Provider/HttpClient**；禁止业务 service 和 core 直接 `urllib.request.Request`/`urlopen`
- 日志输出必须经 `SensitiveDataFilter` 脱敏，不打印 token/key/Authorization
- 开发用 `--reload-dir backend`，避免 reloader 扫描 `.venv`/`node_modules`/`data`
