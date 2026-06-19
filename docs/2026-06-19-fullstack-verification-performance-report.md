# 2026-06-19 全栈验证与性能收口报告

分支：`codex/playback-logic-update`

## 结论

- 后端全量测试通过：`639 passed, 2 warnings`
- 前端测试与构建通过：`131 passed`，`npm run build` 通过
- Phase 5 最低验证矩阵通过：unit `269 passed`，contract `170 passed`，前端 `131 passed`，`npm run build` 通过
- 本地 CI parity 护栏通过：`scripts/ci_baseline_parity.py` 确认 `.github/workflows/phase5-baseline.yml` 的 unit/contract/ruff/frontend test/build 检查均被 `scripts/phase5_check.sh` 覆盖
- API 性能 benchmark 通过：`scripts/benchmark_api.py` 覆盖 8 个核心 API 冷/热响应、raw/gzip 体积、JSON 输出与 hot P95 慢端点汇总；本地增强矩阵复跑 `slow_count=0`，最大 hot P95 约 `260ms`（阈值 500ms）
- 全栈非破坏性验收矩阵已有完整 PASS 记录：`scripts/fullstack_verification_check.sh` 在本地 dev server 串起 backend full、pre-commit、Phase 5、API smoke/boundary、benchmark、前端 route/interaction/chart/long-list/cross-browser smoke；2026-06-19 曾追加 `--preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --web-vitals` 跑通生产 `vite preview` smoke 与 dev/prod Web Vitals。本轮 preview 转发补强后，单独复跑 prod-preview route smoke PASS 38/38、interaction smoke PASS 5/5、cross-browser Chromium/Firefox/WebKit PASS，且脚本已把 preview route/interaction/chart/long-list/cross-browser smoke 与 Web Vitals 的 `/api`、`/covers` 请求转发到后端；脚本会在激活 `.venv` 前自动检测可导入 `playwright.sync_api` 的 Python，避免跨浏览器 smoke 误用无 Playwright 的 venv Python
- pre-commit 通过：ruff、ruff format、mypy、detect-secrets 全部通过
- 浏览器路由冒烟通过：`scripts/frontend_route_smoke.mjs` 覆盖 19 个默认路由 × 1280px 桌面/390px 移动端共 38 个组合，console error/warning、page error 与页面级横向滚动均为 0；生产 `vite preview` 产物同样 PASS 38/38，并通过路由业务内容 marker 防止只加载导航壳的误判
- 浏览器交互冒烟通过：`scripts/frontend_interaction_smoke.mjs` 覆盖分析页 tab、Billboard 子路由/浏览器前进后退、AI Insights 报告/问答 tab（含未配置 LLM 空状态）、Settings 过滤/显示偏好控件与主题切换共 5 个非破坏性场景；dev server 与生产 `vite preview` 产物均 PASS 5/5，生产 preview 通过 `--api-base-url` 转发同源 API/cover 请求，console error/warning、page error 与页面级横向滚动均为 0
- 图表交互冒烟通过：`scripts/frontend_chart_interaction_smoke.mjs` 覆盖 ECharts tooltip hover、legend toggle 与 dataZoom drag 共 3 个场景；dev server 与生产 `vite preview` 产物均 PASS 3/3，console error/warning、page error 与页面级横向滚动均为 0
- 跨浏览器冒烟通过：`scripts/frontend_cross_browser_smoke.mjs` 使用 Playwright Chromium / Firefox / WebKit（Safari-family）覆盖 6 个核心路由 × 桌面/390px 移动端 + 4 个非破坏性交互场景；dev server 与生产 `vite preview` 产物均 PASS 3/3 浏览器引擎，生产 preview 通过 Playwright `route.fetch`/`route.fulfill` 代理后端响应，避免 4173 非 CORS 白名单 origin 造成假阴性或弱证据
- 长列表分页/分段渲染冒烟通过：`scripts/frontend_long_list_smoke.mjs` 覆盖 Records mini-rank、Billboard All-Time、Community Feed infinite load、RecentPlays、SavedTracks、PersonalRankTable 共 6 个场景；dev server 与生产 `vite preview` 均 PASS 6/6，console error/warning、page error 与页面级横向滚动均为 0
- 可复跑只读 API smoke 通过：`scripts/api_smoke_probe.py` 覆盖 96 个本地只读 GET 请求，全部返回预期状态并带 `X-Request-ID`；OpenAPI GET 核算 `95/104 covered, 9 excluded, 0 unaccounted`
- 可复跑 API 边界 probe 通过：`scripts/api_boundary_probe.py` 覆盖 19 个非破坏性 GET 边界，包含越界参数、非法 path/entity、特殊字符查询，验证预期 422/200、`X-Request-ID`、无 500，且 422 响应带 FastAPI validation detail
- Provider 错误响应分层通过：新增 contract probe 覆盖 Network/Auth/RateLimit/Server/Parse/HTTP 六类 Provider 异常，验证响应映射为结构化 503/502/429、保留 `X-Request-ID`，且不向前端泄露原始上游错误文案
- Billboard enrichment 降级契约补强：专辑/艺人/歌曲详情页的 Wikipedia 可选增强 lookup 遇到普通包装异常时返回 `wiki: null` 而不是 500，同时保留 `ProviderError` 的全局分层语义；新增 4 个离线 contract 用例覆盖 album/artist/track enrichment GET 与 ProviderError 传播
- 基础设施 response_model 契约补强：`/api/health`、`/api/admin/cache-stats`、`/api/import/*`、`/api/jobs/{job_id}/status` 共 6 个启动/缓存/导入/Job Queue 端点补齐响应模型，OpenAPI 缺失 response_model 路由数从 41 降到 35
- Settings mutation response_model 契约补强：`PUT /api/settings`、聚合重建、翻译缓存清理、LLM profile create/apply/delete 共 6 个写端点补齐响应模型；`PUT /api/settings` 改为返回完整脱敏 `SettingsResponse`，避免前端 Settings Query 缓存被半份 payload 覆盖；OpenAPI 缺失 response_model 路由数从 35 降到 29，并已刷新前端 `openapi.json`/`api-types.ts`
- Spotify auth response_model 契约补强：登录、连接状态、断开连接、保存曲目同步、本地账号数据、当前播放、全量同步 7 个 JSON 端点补齐响应模型；OAuth callback 显式声明 `RedirectResponse`；OpenAPI 缺失 response_model 路由数从 29 降到 22，并已刷新前端 `openapi.json`/`api-types.ts`
- 账号中心 response_model 契约补强：Search History、Insights tiers/marquee、Podcast、Video、Profile、Wrapped Hub 共 12 个 GET 端点补齐响应模型；OpenAPI 缺失 response_model 路由数从 22 降到 10，并已刷新前端 `openapi.json`/`api-types.ts`
- 核心统计 response_model 契约补强：Timeline weekly、Listening Hours weekday/platform、Artist list/deep-dive、Wrapped available years 共 6 个 GET 端点补齐响应模型；OpenAPI 缺失 response_model 路由数从 10 降到 4，并已刷新前端 `openapi.json`/`api-types.ts`
- 剩余 JSON response_model 契约收口：Release Cycle compare、Genius lyrics 与 Genius URL 共 3 个 JSON 端点补齐响应模型；OpenAPI 缺失 response_model 路由数从 4 降到 1，唯一剩余项为 Spotify OAuth callback `RedirectResponse`，并已刷新前端 `openapi.json`/`api-types.ts`
- OpenCC 保存偏好恢复按需加载收口：`chinese.ts` 移除模块初始化时的 `ensureConverter(getChineseStyle())`，保存繁体偏好的用户不再仅因模块导入就后台请求 `cn2t` 大字典；新增架构护栏锁定 `displayName()` / `setChineseStyle()` 作为字典加载入口，并保留 `AppLayout` 的 `useChineseTextVersion()` 重渲染订阅

## 修复项

| 严重程度 | 问题 | 影响 | 修复 |
| --- | --- | --- | --- |
| P1 | contract seed fixture 残留 WAL/SHM 导致 `release_groups` 状态漂移 | L3 release group 测试在全量套件中偶发失败 | `build_seed_db.py` 重建前后清理 `seed.db-wal/-shm`，并重新生成 `seed.db` |
| P1 | contract 测试直接写 canonical `seed.db` | 只读/写入路径会污染后续测试，造成测试顺序依赖 | `backend/tests/contract/conftest.py` 改为每次复制临时 seed DB，teardown 删除临时 WAL/SHM |
| P1 | Billboard records 测试清缓存不完整 | `_load_and_rank_cached` / `_compute_records_cached` 污染导致 L2 bootstrap 测试全量失败 | 补齐 `_clear_billboard_runtime_caches()` 的缓存清理范围 |
| P2 | `chart_compute.py` / `chart_staged_cache.py` 超过架构护栏行数 | Phase 5 facade 约束回归 | 新增 `chart_load_rank.py` 承接共享 load/rank cache，facade 回到护栏内 |
| P2 | `import_data()` 遇到缺音频元数据的播放/视频记录可能引用未初始化 `album_id` | Extended Streaming History 中播客、视频或缺元数据条目会中断完整导入流程 | 每条记录先将 `album_id` 初始化为 `None`，新增临时 SQLite 导入测试覆盖音频、视频、featured artist、空 `source_album_id` 与预聚合表 |
| P2 | `/api/spotify/auth/playing` 在 token 过期时用只读连接刷新并落库 | 已连接 Spotify 且 access token 过期时，当前播放状态 GET 可能返回 500 `attempt to write a readonly database` | 该端点改用显式短生命周期可写连接，并新增 unit test 固定 token refresh 写入边界 |
| P2 | `/api/spotify/auth/login` 在未配置 `SPOTIFY_CLIENT_ID` 时抛出未处理异常 | 设置页点击连接 Spotify 时，本地未配 OAuth Client ID 会返回 500 并记录全局未处理异常 | API 边界将已知配置缺失收敛为 503 `spotify_client_not_configured`；新增 contract 测试覆盖无配置、PKCE state、callback 加密落库和 invalid state |
| P2 | `PUT /api/settings` 接受越界统计配置 | 负数 `min_ms`、过小/过大的 Billboard Top N、非法周起始日/小时会被写入设置并污染后续统计 | `SettingsUpdateRequest` 补齐与查询参数一致的 `ge/le` 约束，新增 422 边界 contract 测试 |
| P2 | `/api/settings/clear-translation-cache` 在新库或 seed 库缺少 `wikipedia_cache` 表时 500 | 首次使用设置页清缓存可能返回内部错误，无法作为幂等维护操作 | 清理前 `CREATE TABLE IF NOT EXISTS wikipedia_cache`，新增 contract 测试验证缺表时返回 `deleted_count` |
| P2 | `/covers/albums/{entity_id}.jpg` 回退查询假设 `albums.spotify_album_id` 存在 | contract seed 或只含基础 albums schema 的本地库请求缺失专辑封面时会从预期 404 变成 500，削弱封面与 preview `/covers` 分流验证 | 封面 CDN 回退改走 `tracks/track_albums -> spotify_track_meta -> spotify_album_meta` 的真实 schema 路径；API smoke 新增缺失封面 404 负向覆盖；OpenAPI path 模板匹配器支持 `{entity_id}.jpg` 嵌入式参数 |
| P2 | 未被路由层显式捕获的 `ProviderError` 会落入全局泛化 500 | Spotify/Genius/Wikipedia/LLM 等上游失败可能被包装成不透明内部错误，无法满足 Provider 错误分层与前端可恢复状态判断 | 新增 `ProviderError` 全局异常处理器，将 rate limit/network/auth/server/parse/http 分别映射为结构化 429/503/502 响应；新增 contract 测试覆盖 request id 透传和原始上游消息不外泄 |
| P2 | Billboard enrichment 的 Wikipedia lookup 普通异常会打到全局 500 | 音乐详情页可选百科增强失败时，album/artist/track enrichment GET 可能让整块详情增强接口失败，而不是返回空增强供前端降级展示 | 路由层新增 `_safe_wiki_lookup()`，普通异常返回 `wiki: null`，`ProviderError` 继续交给全局 Provider 分层处理；新增 album/artist/track 三个离线 contract 用例锁定 200 + `X-Request-ID` + 空增强 payload |
| P2 | 健康检查、缓存统计、导入任务和 Job Queue 状态端点未声明 `response_model` | OpenAPI 仍能生成，但基础设施端点缺少稳定响应契约，削弱“一键启动/导入/缓存/后台任务”验证证据 | 新增 `HealthResponse`、`CacheStatsResponse`、`ImportJobCreateResponse`、`ImportJobStatus`、`JobStatusResponse` 绑定 6 个端点，并新增 contract 测试同时检查 FastAPI route 与 OpenAPI 200 schema |
| P2 | Settings 写端点未声明 `response_model`，且 `PUT /api/settings` 返回半份设置对象 | 前端 `updateSettings` 会把 PUT 响应直接写入 TanStack Query；缺少 `db_record_count`、`spotify_connected` 等字段时，设置页后续读取可能拿到不完整缓存，同时 OpenAPI 对数据过滤、聚合重建和 LLM profile mutation 的响应合约不稳定 | 新增 Settings mutation response-model contract；6 个写端点补齐 Pydantic 响应模型；`PUT /api/settings` 复用 GET 的完整脱敏响应构造；重新生成前端 OpenAPI 快照和 TS 类型 |
| P2 | Spotify OAuth/Web API JSON 端点未声明 `response_model` | 设置页连接/断连/同步/当前播放等端点 OpenAPI 200 schema 为空；前端类型生成无法表达 OAuth 登录 URL、连接状态、同步结果和本地 Spotify 数据 bucket，削弱 Spotify Web API 代理验收证据 | 新增 Spotify auth response-model contract；7 个 JSON 端点补齐 Pydantic 响应模型，保留 Spotify 原始列表项为 `dict[str, Any]` 避免截断 payload；OAuth callback 显式声明 `RedirectResponse`；重新生成前端 OpenAPI 快照和 TS 类型 |
| P2 | 账号中心相邻 GET 端点未声明 `response_model` | Search History、粉丝层级、Marquee、Podcast、Video、Profile、Sound Capsule 与 Wrapped Hub 的 OpenAPI 200 schema 为空；前端类型生成无法稳定表达账号中心/画像 payload，削弱账号中心功能验收证据 | 新增 `backend/models/account_center.py` 与 response-model contract，12 个 GET 端点补齐 Pydantic 响应模型；对稀疏可用性 payload 使用 `response_model_exclude_unset` 保持兼容；重新生成前端 OpenAPI 快照和 TS 类型 |
| P2 | 核心统计只读 GET 端点未声明 `response_model` | Timeline weekly、Listening Hours 周末/平台小时、Artist selector/deep-dive 与 Wrapped available years 的 OpenAPI 200 schema 为空；前端生成类型无法稳定表达核心统计页面 payload | 补齐 timeline/behavior/artist/wrapped 响应模型并绑定 6 个路由；Artist deep-dive 的 `found: false` 稀疏响应保留 `response_model_exclude_unset`；新增 core stats response-model contract 并重新生成前端 OpenAPI 快照和 TS 类型 |
| P2 | Release Cycle compare 与 Genius lyrics JSON 端点未声明 `response_model` | 发行周期对比、歌词和 Genius URL 的 OpenAPI 200 schema 为空；前端生成类型无法稳定表达对比结果、歌词 found=true/false 与 URL payload | 新增 compare/lyrics 响应模型并绑定 3 个 JSON 路由；对错误/未命中稀疏响应使用 `response_model_exclude_unset` 保持兼容；新增 remaining JSON response-model contract 并重新生成前端 OpenAPI 快照和 TS 类型 |
| P2 | AI Insights 周报/月报/年度叙事/自由问答暴露 `dynamic_threshold` 与 `max_merge_gap_minutes` 但未传入最终计数管线 | 用户在设置页启用动态阈值或 Session 合并边界后，AI 报告可能继续按旧播放口径解读数据；不同过滤口径还可能撞到同一份报告缓存 | `backend/api/ai_insights.py` 透传 `PlayFilters` 新字段，`ai_insights_service.py` 将参数传入 `load_period_plays()` 与 `get_wrapped_full()`，并把过滤指纹纳入报告 cache key；新增离线 unit/contract 测试覆盖 5 个 AI Insights 端点、服务链路和 cache key 分流 |
| P3 | AI Insights 报告生成后用 readonly 请求连接写报告缓存 | 页面/API 返回 200，但后端日志出现 `AI report cache write failed` warning + traceback，且新报告无法写入缓存 | `_set_cache()` 遇到 readonly 连接时用短生命周期 `get_db(readonly=False)` 重试缓存写入；保留其它 SQLite 写入错误的 warning，新增 unit 测试锁定不再记录 readonly warning |
| P3 | `/api/behavior` 复用 `PlayFilters`，OpenAPI 暴露 `min_ms`、`merge_enabled`、`dynamic_threshold`、`max_merge_gap_minutes` 等无效参数 | 行为分析按设计使用全量事件；这些参数不会改变结果，却会误导 API 使用者并让前端过滤变化触发无效 refetch | 后端只声明有效的 `music_only` 参数，前端 behavior 请求/query key 收窄到 `music_only`，同步 OpenAPI snapshot/types；新增 contract 与前端 hook 测试 |
| P3 | AI Insights 会话列表把整行选择按钮包住删除按钮 | React 19 在 `/ai-insights` 输出 invalid DOM nesting console error，浏览器路由冒烟无法做到 0 console error，且嵌套交互对辅助技术不友好 | `ChatSessionList` 改为非交互行容器，左侧会话选择按钮与右侧删除/确认按钮做兄弟节点，并补充组件测试锁定无 `button button` 嵌套和删除交互 |
| P3 | AI Insights 周快捷选项在 latest listening range 加载前可能生成相同 value key | `/ai-insights` 桌面首屏偶发 React duplicate key console error，route smoke 可能失败 | `QuickPills` 改用 `label:value` 复合 key，保留两个语义不同的快捷按钮；新增组件测试覆盖重复 value 不应产生 console error |
| P3 | 前端 route smoke 只检查 root 文本长度，可能把“只有导航壳、业务内容尚未渲染”的页面误判为通过 | 生产 preview 冷跑时 `/billboard/records` 桌面在 2.5s 采样点曾只有导航文本，但旧探针仍 PASS；这会削弱前端零缺陷验证证据 | 为 19 个默认路由增加业务内容 marker，默认等待提高到 5s，并提供 `--disable-route-markers` 作为自定义路由逃生口；生产 preview marker smoke 复跑 PASS 38/38，Records 桌面 root text 从导航壳 45 提升到 3141 |
| P3 | 前端缺少可复跑的非破坏性交互 smoke，部分 tab/路由/history/设置控件/主题切换只能靠人工抽检 | route smoke 能证明页面渲染，但不能证明关键按钮可点击、路由历史状态正确、Settings 过滤/显示偏好控件可用或主题切换状态落入 DOM/localStorage；AI Insights 未配置 LLM 时还可能误判成报告按钮缺失 | 新增 `scripts/frontend_interaction_smoke.mjs`，通过 headless Chrome CDP 覆盖分析页 tab、Billboard 子路由/前进后退、AI Insights 报告/问答 tab（自适应未配置 LLM 空状态）、Settings 非破坏性控件与主题切换；新增 unit 护栏锁定 CLI、默认 5s 轮询、核心场景和 console/page error 采集 |
| P3 | 生产 `vite preview` 下 interaction/cross-browser smoke 未显式代理 `/api` 与 `/covers` | `vite preview` 不继承 Vite dev proxy，后端 CORS 白名单也不包含 4173；如果 smoke 只验证静态壳或空状态，可能把 API 未命中误判为生产预览可用。Playwright `route.continue_(url=...)` 还会触发跨 origin 语义，不能等价模拟同源 dev proxy | `frontend_interaction_smoke.mjs` 新增 CDP Fetch `--api-base-url` 转发；`frontend_cross_browser_smoke.mjs` 新增 `--api-base-url` 并用 Playwright `route.fetch` + `route.fulfill` 代理响应，关闭页面前等待 network idle 防止代理请求被打断；`fullstack_verification_check.sh` 的 preview interaction/cross-browser 调用接入 `--preview-api-url`；新增 unit 护栏并实跑 production preview interaction PASS 5/5、Chromium/Firefox/WebKit PASS |
| P3 | 生产 `vite preview` 下 Web Vitals lab 未显式代理 `/api` 与 `/covers` | 性能采样虽能量到 `dist/` 静态资源，但 `vite preview` 不提供 dev proxy；数据页请求可能落到 4173 静态服务或被 CORS 拦截，导致资源数/LCP/TBT 更像静态壳而非真实数据页面 | `frontend_web_vitals_probe.mjs` 新增 `--api-base-url` 与 CDP Fetch 转发，`fullstack_verification_check.sh --web-vitals` 的 preview Web Vitals 调用接入 `--preview-api-url`；新增 unit 护栏锁定 CLI、请求转发与 fullstack wiring；实跑 production preview `/account` 390px 采样 PASS，LCP 464ms、CLS 0、TBT 0ms，后端日志出现 request id |
| P3 | 音乐详情页隐藏 tab 仍挂载 `EntityStatsPanel` 图表 | 用户快速切到 Billboard 成绩等非统计 tab 时，隐藏容器宽高为 0，内部 ECharts 初始化会输出 `Can't get DOM width or height` warning，削弱 0 console warning 与图表交互验证目标 | Track/Artist/Album 详情页改为只在统计 tab 激活时挂载 `EntityStatsPanel`，新增架构护栏禁止 hidden tab 挂载统计图表，并新增图表交互 smoke 覆盖 tooltip、legend 与 dataZoom |
| P3 | 图表交互 smoke 对生产 preview 与冷启动场景不够稳 | `vite preview` 不显式提供 dev server `/api` proxy 语义，dataZoom 场景需要从真实 `/api/billboard/all-time` 选择长榜实体；冷启动下 `/account` 与音乐实体页可能超过默认 5s 内容等待，导致假阴性 | 新增 `--api-base-url` 分离前端页面地址与 API 地址；account legend 与 dataZoom 场景保留 12s 冷启动等待下限；dev server 与生产 `vite preview` 均 PASS 3/3 |
| P3 | Firefox/Safari-family 兼容性缺少可复跑自动证据 | 之前的浏览器证据主要来自 Chromium CDP；“确保 Chrome、Firefox、Safari 正常”的要求只能算部分覆盖 | 新增 `scripts/frontend_cross_browser_smoke.mjs`，用 Python Playwright API 跑 Chromium、Firefox、WebKit（Safari-family），覆盖 6 个核心路由 × 桌面/390px 移动端、横向溢出、console/page error、分析/Billboard/AI Insights/主题切换；dev server 与生产 preview 均 PASS |
| P3 | 长列表分页/分段渲染缺少端到端可复跑证据 | 组件单测能证明分页组件局部渲染，route/interaction smoke 只能覆盖页面加载和代表性交互，无法直接证明 Records、AllTime、Community Feed、RecentPlays、SavedTracks、PersonalRankTable 这些长列表的下一页/无限加载在真实页面中都能改变可见窗口；生产 preview 还需要静态页面到后端 API 的显式分流 | 新增 `scripts/frontend_long_list_smoke.mjs`，通过 headless Chrome CDP 点击分页或滚动 sentinel，验证可见行窗口变化、Community feed append、0 console error/warning、0 page error、0 横向溢出；新增 `--api-base-url` 用 CDP Fetch 将 preview 页面的 `/api` 和 `/covers` 请求重写到 8000 后端；新增 unit 护栏锁定 CLI、请求重写和 6 个命名场景 |
| P3 | API 参数边界覆盖仍分散在少量 contract 测试中 | “空值、超长值、非法值、特殊字符”边界要求缺少一条可独立复跑的只读探针；happy-path API smoke 无法证明代表性 422 响应都带 request id 与 validation detail | 新增 `scripts/api_boundary_probe.py`，覆盖 19 个非破坏性 GET 边界：limit/offset/top_n/weeks_before/weeks_after/significance_min 越界、invalid/empty entity、非 int path、特殊字符搜索；新增 unit/contract 护栏，锁定预期 422/200、`X-Request-ID`、无 500 和 FastAPI validation detail |
| P3 | API benchmark 只能人工读 Markdown，缺少慢端点阈值和机器可读报告 | “响应时间分布、慢 API >500ms”要求缺少可门禁的输出；旧脚本也会在极小响应上显示负 gzip ratio，影响报告可读性 | `scripts/benchmark_api.py` 新增 `--base-url`、`--slow-ms`、`--fail-on-slow`、`--json-output`，生成 slow endpoint summary 与 JSON 报告；压缩率下限钳为 0%；新增 unit 护栏锁定 CLI、慢端点筛选、JSON 输出和 tiny payload ratio |
| P3 | 全栈验证命令分散，容易漏跑 API、browser、benchmark 或 pre-commit 中的一类 | 交付要求需要后端、API、前端、浏览器、性能和质量检查都有明确入口；旧状态只能依赖报告中的长命令清单，复跑成本高 | 新增 `scripts/fullstack_verification_check.sh` 聚合非破坏性验收矩阵：backend full、pre-commit、Phase 5、API smoke/boundary、benchmark fail-on-slow、前端 route/interaction/chart/long-list/cross-browser smoke；preview 和 Web Vitals 通过 `--preview-url` / `--web-vitals` 显式启用；新增 unit 护栏和 `sh -n` 语法验证 |
| P3 | 全栈聚合脚本激活 `.venv` 后跨浏览器 smoke 误用无 Playwright 的 Python | 默认矩阵前半段全部通过后，`frontend_cross_browser_smoke.mjs` 在 `.venv/bin/python` 下报 `ModuleNotFoundError: No module named 'playwright'`，导致完整验收入口不能一键跑到底 | `fullstack_verification_check.sh` 在激活 `.venv` 前检测可导入 `playwright.sync_api` 的解释器并导出/传入 `--python "$PYTHON_PLAYWRIGHT"`；新增 unit 护栏锁定检测逻辑；复跑默认矩阵时自动选择 `/opt/anaconda3/bin/python`，Chromium/Firefox/WebKit 全部 PASS |
| P2 | 390px 移动端页面可横向滚动 47.5px | `/analysis/stats`、`/analysis/charts` 等页面移动端体验不稳 | `AppLayout` 增加页面级 `overflow-x-clip`，Masthead nav 增加 `basis-full/max-w-full`，Dashboard skeleton 改为 `w-full max-w-*` |
| P2 | pre-commit ruff hook 扫描冻结 Streamlit `app/` 与旧脚本 | `pre-commit run --all-files` 因历史页名/未用变量失败 | `.pre-commit-config.yaml` 将 ruff 与 ruff-format 限定到 `backend/`，与项目日常质量命令一致 |

## 性能优化

| 项目 | 优化前 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| records 直接 profile 冷算 | 4.791s / 19,188,063 calls | 3.090s / 10,941,286 calls | 时间 -35.5%，调用数 -43.0% |
| `/api/billboard/records` 冷请求 | 2.19s | 1.871s | -14.6% |
| `/api/billboard/records` 热请求 | 0.01-0.02s | 0.012-0.013s | 持平 |
| OpenCC 默认懒加载包 | `full-yTi_27TG.js` 1,121.76KB / gzip 494.12KB | 简体路径 `t2cn-g7W6-1pz.js` 64.27KB / gzip 38.78KB；繁体路径 `cn2t-DJnOUolw.js` 1,059.13KB / gzip 457.19KB | 默认完整包消除；简体路径 gzip -455.34KB，繁体路径 gzip -36.93KB |
| OpenCC 已保存繁体偏好恢复 | 模块初始化直接执行 `ensureConverter(getChineseStyle())`，只要导入 `chinese.ts` 且偏好为繁体，就会后台请求 `cn2t-DJnOUolw.js` 1,059.13KB / gzip 457.19KB | 模块初始化 0 字典请求；仅 `displayName()` 渲染转换文本或 `setChineseStyle()` 切换偏好时触发对应子包 | 避免保存偏好用户在实际需要转换前消耗 457.19KB gzip 网络与解析资源 |
| ECharts 图表懒加载包 | `esm-CBcusPEn.js` 1,134.42KB / gzip 376.65KB | `EChartsTheme-*.js` 673.19KB / gzip 225.67KB | 原始体积 -461.23KB，gzip -150.98KB |
| `/account` 前端资源加载 | 桌面 250 requests / 24,632.6KB / TBT 132ms / LCP 2,480ms；移动 250 requests / 25,488.7KB / TBT 132ms / LCP 2,412ms | 桌面 92 requests / 7,565.5KB / TBT 0ms / LCP 2,132ms；移动 91 requests / 7,455.4KB / TBT 0ms / LCP 2,320ms | requests -63%，资源体积 -69%~-71%，TBT -132ms，LCP 小幅改善 |
| `merge_consecutive_plays()` 大批量片段合并 | 80k 行合成片段 2.58s；`/api/dashboard/full` 冷 profile 8.26s，`merge_consecutive_plays` 7.59s，`load_plays` 2 次 | 80k 行合成片段 0.06s 级；`/api/dashboard/full` 冷 profile 1.02s，`merge_consecutive_plays` 0.19s，`load_plays` 1 次 | 合成护栏约 -97%；真实冷 profile -87.7%，核心合并 -97.5% |
| Billboard summaries 直接 profile | 2.098s / 7,114,904 calls | 1.555s / 5,764,912 calls | 时间 -25.9%，调用数 -19.0% |
| 8 核心 API hot P95 慢端点 | benchmark 脚本无阈值/JSON 门禁 | `slow_count=0`，增强矩阵复跑最大 hot P95 约 `260ms`（`/api/billboard/data`，阈值 500ms） | 新增可复跑慢端点门禁与机器可读报告 |

实现：`chart_power_score.py` 将 track/album/artist Power Score 的逐行 `DataFrame.apply(axis=1)` 和 Python lambda 聚合改为列级向量化计算，并新增语义测试保证冠军差距、非冠军中位数、debut bonus、#1 bonus、peak/week 统计不漂移。

播放合并补充实现：`merge_consecutive_plays()` 从逐 `_merge_group` 的 `iterrows()/to_dict()` 构造改为组级聚合、首行批量重复与 NumPy 向量化 `ms_played` 回填；保留 `max_gap_minutes`、`boundary_column`、无 duration 行透传、完整播放 + 余数播放展开语义。`/api/dashboard/full` 同步将已加载 DataFrame 传给 `get_random_track()`，避免同一请求内再次进入播放加载路径。

Billboard summaries 补充实现：`compute_artist_track_counts()` 与 `compute_album_track_counts()` 去掉逐行 `DataFrame.apply()` 回查 best peak track，改为一次排序、`drop_duplicates()` 与 merge 回填；新增 summaries 语义测试和架构护栏防止回退到 row-wise apply。

前端补充实现：`displayName()` 将 OpenCC 默认 `full` 包拆为 `opencc-js/t2cn` 与 `opencc-js/cn2t` 两条按需路径，并取消 `chinese.ts` 模块初始化阶段根据已保存偏好预取字典；加载仍由 `displayName()` 或 `setChineseStyle()` 触发，加载完成后通过 `chinese-style-change` 事件让 `AppLayout` 订阅重渲染。ECharts 统一通过 `LazyEChart` 动态加载 `echarts-for-react/esm/core` 并只注册当前用到的 bar/line/pie/heatmap、tooltip、legend、dataZoom、visualMap 与 mark 组件，避免 `echarts-for-react` 默认入口静态拉入完整 ECharts runtime。

账号页补充实现：`ChemistryBlock` 将每类滚动预览限制到 8 条，保留全量分类计数；账号页深层封面图统一加 `loading="lazy"` 与 `decoding="async"`，避免收藏化学反应的数百张示例封面抢占首屏资源。

## 基准与探针

- 后端 import 基准：`1.48s real`，max RSS `140,410,880`
- 前端 build 基准：`4.97s real`，max RSS `667,516,928`
- 8001 临时冷启动 API 测量：
  - `/api/billboard/records?dynamic_threshold=true&merge_level=2`：`1.871, 0.013, 0.012s`
  - `/api/billboard/power-scores?dynamic_threshold=true&merge_level=2`：`0.105, 0.021, 0.021s`
  - `/api/billboard/weekly?dynamic_threshold=true&merge_level=2`：`0.481, 0.125, 0.122s`
  - `/api/dashboard/full?dynamic_threshold=true`：`5.393, 0.177, 0.167s`
- dashboard/full 直接 profile（清 `load_plays` cache 后调用路由函数，`dynamic_threshold=true`）：优化前 `8.2606s / 32,861,799 calls`，`merge_consecutive_plays` `7.589s`，`load_plays` 2 次；优化后 `1.0155s / 915,814 calls`，`merge_consecutive_plays` `0.190s`，`load_plays` 1 次。
- dashboard/full HTTP benchmark（当前后台服务热身状态）：`cold=0.20s, hot=0.16s, 4.2KB/1.2KB gzip`。
- Billboard summaries 直接 profile（清 `compute_summaries_staged` cache，`dynamic_threshold=true&merge_level=2`）：优化前 `2.0980s / 7,114,904 calls`；优化后 `1.5549s / 5,764,912 calls`。
- Billboard summaries HTTP benchmark（临时 8000 后端，`SPOTIFY_STATS_WARMUP=0`）：`cold=1.19s, hot=0.04s, 1295.7KB/162.4KB gzip`。
- API benchmark probe：增强 `scripts/benchmark_api.py` 后，在无 reload 后端（`SPOTIFY_STATS_WARMUP=0`）采样 8 个核心端点，全部 200；hot P95 均低于 500ms；2026-06-19 增强 fullstack matrix 复跑时最大 `/api/billboard/data` hot P95 `0.26s`，`slow_count=0`；JSON 输出 `/tmp/spotify_api_benchmark.json` 记录 `result_count=8`、`slow_ms=500.0`。
- API smoke：`scripts/api_smoke_probe.py` 在真实本地库通过 96/96 个本地只读 GET 请求，覆盖 Dashboard、Analysis、Timeline、Leaderboard、Billboard、Release Cycle、Music Entity、Lyrics 未命中、Community 缺失详情、Settings 缺失 LLM profile、缺失封面、Version Merge、Account、AI Insights、Chat、Admin、Job、Spotify status/data，并逐项验证 `X-Request-ID`；OpenAPI GET 核算 `95/104 covered, 9 excluded, 0 unaccounted`，默认列表排除 AI 生成、enrichment、OAuth callback/login 与 live playback 等会触发外部网络或浏览器态的路径。
- API boundary probe：`scripts/api_boundary_probe.py` 在 TestClient 本地应用实例通过 19/19 个非破坏性 GET 边界，覆盖 Analysis/Leaderboard/Community/Music Entity/Billboard/Release Cycle/Lyrics/Chat 的越界查询参数、非法 path/entity 与特殊字符搜索；每个响应均验证预期状态、`X-Request-ID`、无 500，422 响应验证 FastAPI validation detail。
- Provider error contract probe：`backend/tests/contract/test_provider_error_responses.py` 覆盖 `ProviderNetworkError`、`ProviderAuthError`、`ProviderRateLimitError`、`ProviderServerError`、`ProviderParseError`、`ProviderHTTPError`，验证 API 层返回稳定 `detail.error/provider/status`、503/502/429 状态码、`X-Request-ID`，且不会泄露原始上游错误文案。
- Billboard enrichment contract probe：`backend/tests/contract/test_billboard_enrichment_contract.py` 覆盖 `/api/billboard/enrichment/album|artist|track` 三个外部增强 GET，在 Wikipedia lookup 普通异常下返回 200、`X-Request-ID` 和 `{"wiki": null, "genius": null}`，避免详情页可选百科增强失败拖垮整页；`ProviderError` 仍由全局 Provider 分层处理。
- Infrastructure response-model probe：`backend/tests/contract/test_infrastructure_response_models.py` 覆盖 `/api/health`、`/api/admin/cache-stats`、`/api/import/streaming`、`/api/import/account`、`/api/import/status/{job_id}`、`/api/jobs/{job_id}/status`，要求 FastAPI route 声明 `response_model` 且 OpenAPI 200 响应发布 JSON schema；该批 `/api` response_model 缺失数从 41 降到 35。
- Settings mutation response-model probe：`backend/tests/contract/test_settings_api_mutations.py` 覆盖 `PUT /api/settings`、`POST /api/settings/rebuild-agg`、`POST /api/settings/clear-translation-cache`、`POST /api/settings/llm-profiles`、`POST /api/settings/llm-profiles/{profile_id}/apply`、`DELETE /api/settings/llm-profiles/{profile_id}` 的 FastAPI route 与 OpenAPI 200 JSON schema；Settings 批次 `/api` response_model 缺失数从 35 降到 29，`pytest -m contract -q` 复跑 `157 passed`。
- Spotify auth response-model probe：`backend/tests/contract/test_spotify_auth_contract.py` 覆盖 `/api/spotify/auth/login|status|disconnect|sync|data|playing|sync-all` 7 个 JSON 端点的 FastAPI route 与 OpenAPI 200 JSON schema，并确认 `/api/spotify/auth/callback` 使用 `RedirectResponse`；本轮 `/api` response_model 缺失数从 29 降到 22，`pytest -m contract -q` 复跑 `160 passed`。
- Account-center response-model probe：`backend/tests/contract/test_account_center_response_models.py` 覆盖 `/api/search-history`、`/api/insights/tiers`、`/api/insights/marquee`、`/api/podcast*`、`/api/video`、`/api/profile*` 与 `/api/wrapped-hub*` 共 12 个 GET 端点的 FastAPI route 与 OpenAPI 200 JSON schema；本轮 `/api` response_model 缺失数从 22 降到 10，`pytest -m contract -q` 复跑 `162 passed`。
- Core stats response-model probe：`backend/tests/contract/test_core_stats_response_models.py` 覆盖 `/api/timeline/weekly`、`/api/listening-hours/weekday-weekend`、`/api/listening-hours/platform-hourly`、`/api/artist/list`、`/api/artist/{name}/deep-dive` 与 `/api/wrapped/available-years` 共 6 个 GET 端点的 FastAPI route 与 OpenAPI 200 JSON schema；本轮 `/api` response_model 缺失数从 10 降到 4，`pytest -m contract -q` 复跑 `164 passed`。
- Remaining JSON response-model probe：`backend/tests/contract/test_remaining_json_response_models.py` 覆盖 `POST /api/billboard/release-cycle/compare`、`GET /api/lyrics/{track_id}` 与 `GET /api/lyrics/{track_id}/url` 的 FastAPI route 与 OpenAPI 200 JSON schema；本轮 `/api` response_model 缺失数从 4 降到 1，唯一剩余路由为 `/api/spotify/auth/callback` 的 `RedirectResponse`；补充 Billboard enrichment 降级契约后，`pytest -m contract -q` 复跑 `170 passed`。
- Chat mutation probe：contract 临时 DB 覆盖 `/api/chat/sessions` 创建、消息写入、详情读取、标题更新、列表读取、删除后读取，以及非法 role 422 边界。
- Settings mutation probe：contract 临时 DB 覆盖设置更新持久化与密钥脱敏、越界设置 422、LLM profile 创建/重复名/读取/列表/更新/应用/删除，以及缺表场景下清翻译缓存幂等返回。
- Import job probe：contract 测试用同步 fake thread 验证 `/api/import/streaming` 与 `/api/import/account` 的 job_id 返回、进度回调、完成状态、account 嵌套结果摘要，以及 streaming 导入异常时的 error 状态。
- AI Insights contract probe：离线 monkeypatch 服务层，覆盖周报/月报/年度叙事/自由问答对 `min_ms`、`music_only`、`merge_enabled`、`dynamic_threshold`、`max_merge_gap_minutes` 的透传，并验证 `LLM 未配置` 映射为 503；unit 层覆盖生成报告与自由问答继续把过滤参数传入数据抓取链路、报告缓存 key 会随过滤口径变化，且 readonly 请求连接会用可写连接完成报告缓存写入。
- Spotify OAuth PKCE contract probe：覆盖 `/api/spotify/auth/login` 未配置 Client ID 返回 503、PKCE state/verifier 入库、`/callback` 成功换 token 后 AES 加密落库并重定向设置页、invalid state 不触发 token exchange。
- Behavior API probe：contract 测试锁定 `/api/behavior` OpenAPI 只暴露 `music_only` 和连接依赖的 `readonly`；前端 query hook 测试锁定 behavior 请求只发送 `music_only`，避免全局播放过滤变化导致无意义 refetch。
- 导入/WAL probe：临时 JSON + 临时 SQLite 验证音频/视频缺元数据记录不会中断导入，featured artist 写入 `track_artists`，空来源写入 `source_album_id IS NULL`；临时 DB 验证 WAL 下读事务快照不阻塞独立写提交，新读连接可见提交后数据。
- 前端 route smoke probe：新增 `scripts/frontend_route_smoke.mjs`，通过 headless Chrome CDP 覆盖 `/`、Analysis、5 个分析重定向别名、Yearly Review、Billboard 4 页、Community、AI Insights、Account、Settings 共 19 路由 × 桌面/移动 38 个组合；默认 5s 等待并检查每个默认路由的业务内容 marker，避免只加载导航壳就通过。dev server 与生产 `vite preview` 产物均 PASS 38/38，console error/warning/page error 全 0，scroll overflow 全 0px。首轮探针暴露 AI Insights 嵌套按钮与重复 key console error；生产 preview 补充探针暴露 `/billboard/records` 桌面 2.5s 导航壳误判风险，增强 marker 后复跑全绿。
- 前端交互 probe：新增 `scripts/frontend_interaction_smoke.mjs`，通过 headless Chrome CDP 执行 5 个非破坏性交互场景：`analysis-tabs` 在 `/analysis/stats` 与 `/analysis/charts` 间点击切换；`billboard-routing` 执行 `/billboard` → `/billboard/number-ones` → `/billboard/all-time` → `/billboard/records` 并验证浏览器后退/前进；`ai-insights-tabs` 点击报告/问答 tab，配置 LLM 时继续覆盖月报/年度叙事，未配置时验证空状态；`settings-controls` 验证 Settings 关键区块、过滤/动态阈值 switch、中文显示偏好 localStorage 与 Spotify 连接按钮状态；`theme-toggle` 验证白日/夜晚按钮同步 DOM class 与 `localStorage.theme`。脚本支持 `--api-base-url`，用于生产 `vite preview` 页面 + 8000 后端 API/cover 的 CDP Fetch 转发；dev server 与生产 `vite preview` 产物均 PASS 5/5，console error/warning/page error 全 0，scroll overflow 全 0px。
- 前端图表交互 probe：新增 `scripts/frontend_chart_interaction_smoke.mjs`，通过 headless Chrome CDP 执行 3 个 ECharts 交互场景：`chart-hover-tooltip` 在 `/analysis/stats` 悬停 canvas 并要求 tooltip 可见；`legend-toggle` 在 `/account` 点击图例区并要求 canvas 内容变化；`datazoom-drag` 从 `/api/billboard/all-time` 动态选择真实长榜艺人，进入音乐实体页 Billboard 成绩趋势图并拖拽 dataZoom。脚本支持 `--api-base-url`，用于生产 `vite preview` 页面 + 8000 后端 API 的分离验证；account legend 与 dataZoom 场景带 12s 冷启动等待下限。dev server 与生产 `vite preview` 均 PASS 3/3，console error/warning/page error 全 0，scroll overflow 全 0px；首轮探针暴露音乐详情隐藏 tab 图表 0 尺寸初始化 warning，后续又暴露冷启动等待假阴性，修复后复跑全绿。
- 跨浏览器 probe：新增 `scripts/frontend_cross_browser_smoke.mjs`，通过 Python Playwright API 覆盖 Chromium、Firefox、WebKit（Safari-family）。每个浏览器引擎执行 6 个核心路由 × 桌面/390px 移动端 marker 检查，以及 `analysis-tabs`、`billboard-routing`、`ai-insights-tabs`、`theme-toggle` 4 个非破坏性交互；生产 preview 用 `--api-base-url` 通过 Playwright `route.fetch` + `route.fulfill` 代理 `/api` 与 `/covers` 响应，并在关闭页面前等待 network idle，避免 4173 非 CORS 白名单和代理请求未完成造成假阴性。dev server 与生产 `vite preview` 产物均 PASS 3/3 浏览器引擎。该探针需要可导入 `playwright.sync_api` 的 Python，可用 `PYTHON_PLAYWRIGHT=/path/to/python` 或 `--python` 指定。
- 前端长列表 probe：新增 `scripts/frontend_long_list_smoke.mjs`，通过 headless Chrome CDP 覆盖 `records-mini-rank`、`all-time-table`、`community-feed`、`recent-plays`、`saved-tracks`、`personal-rank-table` 6 个场景，并支持 `--api-base-url` 将生产 preview 页面的 `/api` 与 `/covers` 请求重写到 8000 后端。当前 dev server 与生产 `vite preview` 结果均 PASS 6/6：Records `1—10 / 89` → `11—20 / 89`，All-Time `1 / 35` → `2 / 35`，Community Feed `50 posts` → `100 posts`，RecentPlays `第 1/1236 页` → `第 2/1236 页`，SavedTracks `第 1/40 页` → `第 2/40 页`，PersonalRankTable `显示 1-50 / 总数 250 条` → `显示 51-100 / 总数 250 条`；console error/warning/page error 全 0，scroll overflow 全 0px。
- 全栈聚合 probe：`sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --web-vitals` 此前在本地后端 8000 + Vite dev 5173 + `vite preview` 4173 环境完整通过，覆盖 backend full `616 passed`、pre-commit、Phase 5 unit `261` / contract `155` / frontend `130` / build、API smoke `91/91`、API boundary `19/19`、Provider error contract、Infrastructure response-model contract、当时默认 route smoke、interaction `5/5`、chart `3/3`、long-list `6/6`、cross-browser Chromium/Firefox/WebKit `PASS`，以及 dev/prod Web Vitals lab；本轮 response-model/API smoke、Billboard enrichment 降级契约、OpenCC 按需加载、路由 smoke 覆盖与 preview 转发收口后已单独复跑 backend full `639 passed`、Phase 5 unit `269` / contract `170` / frontend `131` / build、dev route smoke `38/38`、prod-preview route smoke `38/38`、prod-preview interaction `5/5`、prod-preview cross-browser Chromium/Firefox/WebKit `PASS`、prod-preview Web Vitals `/account` 390px PASS 以及 API smoke `96/96`。`fullstack_verification_check.sh` 当前 preview route/interaction/chart/long-list/cross-browser smoke 和 Web Vitals 均会通过 `--preview-api-url` 显式分流 `/api` 与 `/covers` 请求。
- Web Vitals lab probe（Vite dev server + headless Chrome + CDP）：6 路由 × 桌面/390px 移动端；增强矩阵复跑采样 CLS 全部 0，合成点击 FID 0.8-4.0ms，TBT 全部 0ms，非账号页 LCP 416-868ms，账号页 LCP 2,188ms（桌面）/ 2,264ms（移动）。`frontend_web_vitals_probe.mjs` 现支持 `--api-base-url`，生产 `vite preview` 采样可将 `/api` 与 `/covers` 转发到 8000 后端，避免只测静态壳；本轮 production preview `/account` 390px 单路由复跑 PASS，LCP 464ms、CLS 0、TBT 0ms、encoded resources 400.4KB，后端日志出现 request id；已有补充采样资源体积更接近交付产物：非账号页 LCP 376-864ms，账号页 LCP 2,140ms（桌面）/ 2,168ms（移动），CLS/TBT 全部 0。
- 本地 CI parity probe：新增 `scripts/ci_baseline_parity.py`，提取 `.github/workflows/phase5-baseline.yml` 的核心检查命令，并与 `scripts/phase5_check.sh` 对比。当前输出确认 workflow checks 与 local checks 均为 `pytest -m unit -q`、`pytest -m contract -q`、`ruff check backend/`、`npm test`、`npm run build`；`phase5_check.sh` 开头已接入该护栏。
- 文档同步：README、AGENTS、CLAUDE、backend/CLAUDE、frontend/CLAUDE 已更新 2026-06-19 验证报告、API smoke / API boundary / Provider error / Billboard enrichment degradation / Infrastructure/Settings/Spotify auth/Account-center/Core-stats/Remaining-JSON response-model / API benchmark / fullstack verification / route smoke / interaction smoke / chart interaction smoke / cross-browser smoke / long-list smoke / CI parity 探针、Power Score 向量化、Behavior API 参数收窄、OAuth PKCE 本地合同验证、移动端横向滚动护栏、pre-commit 范围与最新测试基线。

### Web Vitals Lab 采样

> 命令：`node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000`
> 说明：该数据来自本地 Vite dev server，不等同生产 Lighthouse/RUM；FID 为合成点击 first-input，TBT approx 为 FCP 后 5 秒内 long task 近似值。

| Route | Viewport | LCP | CLS | FID | TBT approx | Resources | Encoded resources | Scroll width |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | desktop | 868ms | 0 | 2.2ms | 0ms | 77 | 7,185.3KB | 1280 / 1280 |
| `/` | mobile | 616ms | 0 | 2.3ms | 0ms | 76 | 7,176.0KB | 390 / 390 |
| `/analysis/stats` | desktop | 416ms | 0 | 0.8ms | 0ms | 106 | 8,264.8KB | 1280 / 1280 |
| `/analysis/stats` | mobile | 424ms | 0 | 2.7ms | 0ms | 106 | 8,264.8KB | 390 / 390 |
| `/analysis/charts` | desktop | 428ms | 0 | 2.7ms | 0ms | 99 | 6,960.4KB | 1280 / 1280 |
| `/analysis/charts` | mobile | 428ms | 0 | 3.4ms | 0ms | 97 | 6,785.5KB | 390 / 390 |
| `/billboard/number-ones` | desktop | 664ms | 0 | 2.5ms | 0ms | 104 | 9,807.7KB | 1280 / 1280 |
| `/billboard/number-ones` | mobile | 684ms | 0 | 2.9ms | 0ms | 99 | 9,399.3KB | 390 / 390 |
| `/account` | desktop | 2,188ms | 0 | 3.3ms | 0ms | 92 | 7,564.7KB | 1280 / 1280 |
| `/account` | mobile | 2,264ms | 0 | 3.4ms | 0ms | 91 | 7,454.7KB | 390 / 390 |
| `/settings` | desktop | 464ms | 0 | 3.0ms | 0ms | 85 | 5,159.0KB | 1280 / 1280 |
| `/settings` | mobile | 472ms | 0 | 4.0ms | 0ms | 85 | 5,159.0KB | 390 / 390 |

### Production Preview Web Vitals Lab 采样

> 命令：`cd frontend && npm run preview -- --host 127.0.0.1 --port 4173`，再运行 `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000`
> 说明：该数据来自本地 `vite preview` 生产构建预览，验证真实 `dist/` chunk 加载；preview 采样可通过 `--api-base-url` 访问 8000 后端数据；仍不等同线上 CDN/HTTPS Lighthouse 或 RUM。

| Route | Viewport | LCP | CLS | FID | TBT approx | Resources | Encoded resources | Scroll width |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | desktop | 864ms | 0 | 2.2ms | 0ms | 17 | 1,282.1KB | 1280 / 1280 |
| `/` | mobile | 588ms | 0 | 2.2ms | 0ms | 16 | 1,280.6KB | 390 / 390 |
| `/analysis/stats` | desktop | 376ms | 0 | 2.4ms | 0ms | 39 | 1,385.5KB | 1280 / 1280 |
| `/analysis/stats` | mobile | 392ms | 0 | 2.4ms | 0ms | 39 | 1,385.6KB | 390 / 390 |
| `/analysis/charts` | desktop | 384ms | 0 | 2.5ms | 0ms | 46 | 2,570.0KB | 1280 / 1280 |
| `/analysis/charts` | mobile | 388ms | 0 | 2.7ms | 0ms | 44 | 2,395.1KB | 390 / 390 |
| `/billboard/number-ones` | desktop | 612ms | 0 | 2.6ms | 0ms | 39 | 3,757.3KB | 1280 / 1280 |
| `/billboard/number-ones` | mobile | 624ms | 0 | 2.7ms | 0ms | 34 | 3,348.9KB | 390 / 390 |
| `/account` | desktop | 2,140ms | 0 | 2.8ms | 0ms | 20 | 1,462.4KB | 1280 / 1280 |
| `/account` | mobile | 2,168ms | 0 | 3.0ms | 0ms | 19 | 1,352.4KB | 390 / 390 |
| `/settings` | desktop | 428ms | 0 | 2.6ms | 0ms | 32 | 1,158.3KB | 1280 / 1280 |
| `/settings` | mobile | 428ms | 0 | 2.8ms | 0ms | 32 | 1,158.3KB | 390 / 390 |

## 覆盖矩阵

| 目标项 | 当前证据 | 状态 |
| --- | --- | --- |
| 后端现有测试全量通过 | `pytest backend/tests/ -q`：`639 passed, 2 warnings` | 已自动验证 |
| OpenAPI/核心 API 只读覆盖 | 122 paths / 134 operations schema 存在；96 个可复跑只读请求覆盖 Dashboard、Billboard、Analysis、Community、Lyrics 未命中、Settings 缺失 profile、缺失封面、AI Insights、Account、Spotify status/data；OpenAPI GET 核算 0 unaccounted；19 个 API boundary GET 覆盖代表性越界参数、非法 path/entity 与特殊字符查询；Provider error contract 覆盖六类上游失败的结构化响应分层；Billboard enrichment contract 覆盖 4 个外部增强 GET 在 Wiki 普通异常下返回空增强而非 500，并验证 ProviderError 仍走结构化 503；基础设施 response-model contract 覆盖 6 个启动/缓存/导入/Job 状态端点；Settings mutation response-model contract 覆盖 6 个设置写端点；Spotify auth response-model contract 覆盖 7 个 OAuth/Web API JSON 端点；Account-center response-model contract 覆盖 12 个账号中心/画像 GET 端点；Core-stats response-model contract 覆盖 6 个核心统计 GET 端点；Remaining JSON response-model contract 覆盖 release-cycle compare 与 lyrics 3 个 JSON 端点，剩余未声明 response_model 的 `/api` 路由数为 1（唯一剩余项为 Spotify callback 显式 RedirectResponse） | 已覆盖只读核心路径、代表性参数边界、Provider 失败响应、Billboard enrichment 降级、基础设施响应契约、Settings 关键 mutation、Spotify auth JSON、账号中心/画像、核心统计与剩余 JSON 响应契约；其它 mutation/真实外部网络端点未逐一实打 |
| Extended Streaming History 完整导入 | 新增临时 JSON 导入测试覆盖音频、视频、缺元数据、featured artist、预聚合 | 已自动验证最小完整流程 |
| 多版本与统计过滤语义 | contract/full tests 覆盖 Version Merge、Album Project、Power Score、AI Insights 播放过滤传播、Behavior 全量事件例外参数收窄、播放过滤参数传播与 Billboard invariants | 已自动验证 |
| SQLite WAL 并发读写 | 新增临时 DB WAL reader snapshot + writer commit 测试 | 已自动验证 |
| OAuth/加密/缓存/Job Queue/Request ID | AES、cache manager、job queue 单测；API smoke 验证 `X-Request-ID`；cache-stats/import/job/health 已有 response_model contract；Spotify auth JSON 端点已有 response_model contract；Spotify status/data 只读 200；当前播放端点 token refresh 写入边界有 unit test；OAuth PKCE contract 覆盖 login 503、state/verifier、callback token exchange、AES 加密落库、callback RedirectResponse 和 invalid state | 自动验证基础设施与本地 OAuth 回调语义；真实 OAuth 外部授权未闭环 |
| 前端路由与响应式 | `scripts/frontend_route_smoke.mjs` 覆盖 19 路由 × 桌面/390px 移动端，无页面错误、无 console error/warning、无横向溢出，并检查业务内容 marker；dev server 与生产 `vite preview` 均 PASS 38/38；`scripts/frontend_cross_browser_smoke.mjs` 额外覆盖 Chromium/Firefox/WebKit 的 6 路由 × 2 视口，生产 preview 通过 `--api-base-url` 代理 API/cover 响应；图表入口由架构护栏防止回退到完整 ECharts/OpenCC 默认包；Web Vitals lab 覆盖 6 路由 × 2 视口，生产 preview 可用 `--api-base-url` 代理后端数据；音乐详情隐藏 tab 图表挂载由架构护栏防回归 | 已自动验证主路径与三浏览器引擎 smoke |
| 前端交互 / 本地 mutation | `scripts/frontend_interaction_smoke.mjs` 覆盖分析页 tab、Billboard 子路由/前进后退、AI Insights 报告/问答 tab、Settings 过滤/显示偏好控件与主题切换，dev/prod preview 均 PASS 5/5，生产 preview 通过 `--api-base-url` 代理 API/cover 响应；`scripts/frontend_chart_interaction_smoke.mjs` 覆盖 ECharts hover tooltip、legend toggle、dataZoom drag，dev/prod preview 均 PASS 3/3；`scripts/frontend_cross_browser_smoke.mjs` 在 Chromium/Firefox/WebKit 复跑同类核心交互；`scripts/frontend_long_list_smoke.mjs` 覆盖 Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表分页或分段渲染，dev/prod preview 均 PASS 6/6；Chat CRUD、Settings 更新、LLM profile CRUD/apply、清翻译缓存、Import job 启动/状态在 contract 临时环境自动验证；`PUT /api/settings` 现在返回完整脱敏 Settings payload，避免设置页 Query 缓存被局部响应覆盖 | 已自动验证非破坏性主交互、Settings 关键控件、代表性图表交互和 6 个长列表窗口变化；所有按钮/表单/全部图表实例仍未逐项人工穷尽 |
| 本地 CI / 全栈验收流程 | `scripts/ci_baseline_parity.py` 提取 GitHub Actions baseline 并确认 `scripts/phase5_check.sh` 覆盖 unit、contract、ruff、frontend test、frontend build；`phase5_check.sh` 已内置该 parity 护栏；`scripts/fullstack_verification_check.sh` 已在 dev server + 生产 `vite preview` + Web Vitals 模式完整串起 backend full、pre-commit、Phase 5、API probes、benchmark 与前端 smoke | 已自动验证本地最低矩阵与 CI baseline 不漂移；全栈非破坏性验收入口已实跑通过 |
| 性能优化 | records profile、API 冷/热请求、`benchmark_api.py` slow endpoint summary/JSON report、build/import、bundle chunk、dev/prod-preview Web Vitals lab 与账号页资源/TBT 均有前后对比；preview Web Vitals 可通过 `--api-base-url` 采样真实后端数据页 | 已量化关键瓶颈；仍缺真实 RUM 与生产静态托管 Lighthouse |

## 验证命令

```bash
.venv/bin/pytest backend/tests/ -v
.venv/bin/python scripts/api_smoke_probe.py
.venv/bin/python scripts/api_boundary_probe.py
.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json
.venv/bin/ruff check backend/
.venv/bin/ruff format --check backend/
cd frontend && npm test
cd frontend && npm test -- src/tests/phase5-architecture.test.ts
cd frontend && npm run build
cd frontend && npm run generate-types -- http://127.0.0.1:8000/openapi.json
sh scripts/phase5_check.sh
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --web-vitals
.venv/bin/python scripts/ci_baseline_parity.py
.venv/bin/pre-commit run --all-files
```

补充验证：

```bash
.venv/bin/pytest backend/tests/unit/test_chart_power_score.py -q
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py -q
.venv/bin/pytest backend/tests/unit/test_phase5_architecture.py::test_chart_power_score_avoids_row_wise_dataframe_apply -q
.venv/bin/pytest backend/tests/unit/test_playback_counting.py backend/tests/unit/test_play_service_dashboard.py -q
.venv/bin/pytest backend/tests/unit/test_billboard_chart_summaries.py backend/tests/unit/test_phase5_architecture.py::test_chart_summaries_avoid_row_wise_dataframe_apply -q
.venv/bin/pytest backend/tests/unit/test_providers.py backend/tests/contract/test_provider_error_responses.py -q
.venv/bin/pytest backend/tests/contract/test_billboard_enrichment_contract.py -q
.venv/bin/pytest backend/tests/contract/test_infrastructure_response_models.py backend/tests/contract/test_import_api_jobs.py backend/tests/unit/test_job_queue.py -q
.venv/bin/pytest backend/tests/unit/test_api_smoke_probe_script.py backend/tests/unit/test_spotify_auth_api.py backend/tests/contract/test_api_smoke_probe.py -q
.venv/bin/pytest backend/tests/unit/test_api_boundary_probe_script.py backend/tests/contract/test_api_boundary_probe.py -q
.venv/bin/python scripts/api_boundary_probe.py
.venv/bin/pytest backend/tests/contract/test_spotify_auth_contract.py -q
.venv/bin/pytest backend/tests/contract/test_chat_api_crud.py -q
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py -q
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py backend/tests/contract/test_infrastructure_response_models.py -q
.venv/bin/pytest backend/tests/contract/test_spotify_auth_contract.py backend/tests/unit/test_spotify_auth_api.py -q
.venv/bin/pytest backend/tests/contract/test_account_center_response_models.py -q
.venv/bin/pytest backend/tests/contract/test_core_stats_response_models.py -q
.venv/bin/pytest backend/tests/contract/test_remaining_json_response_models.py -q
.venv/bin/pytest backend/tests/contract/test_import_api_jobs.py -q
.venv/bin/pytest backend/tests/unit/test_ai_insights_service.py backend/tests/unit/test_ai_insights_filter_propagation.py backend/tests/contract/test_ai_insights_contract.py -q
.venv/bin/pytest backend/tests/contract/test_api_contract.py::TestBehaviorEndpoints -q
.venv/bin/pytest backend/tests/unit/test_frontend_route_smoke_script.py -q
.venv/bin/pytest backend/tests/unit/test_frontend_interaction_smoke_script.py -q
.venv/bin/pytest backend/tests/unit/test_frontend_chart_interaction_smoke_script.py -q
.venv/bin/pytest backend/tests/unit/test_frontend_cross_browser_smoke_script.py -q
.venv/bin/pytest backend/tests/unit/test_frontend_long_list_smoke_script.py -q
.venv/bin/pytest backend/tests/unit/test_benchmark_api_script.py -q
.venv/bin/pytest backend/tests/unit/test_fullstack_verification_check_script.py -q
cd frontend && npm test -- src/tests/query-hooks.test.tsx -t "requests behavior data"
cd frontend && npm test -- src/tests/ai-insights-components.test.tsx
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "Chinese conversion"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "lightweight ECharts"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "hidden music detail tabs"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "account chemistry"
cd frontend && ANALYZE=true npm run build
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0
node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --max-scroll-overflow 0
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
sh -n scripts/fullstack_verification_check.sh
git diff --check
```

## 已知限制

- 生产构建仍提示两个大懒加载 chunk：`cn2t-DJnOUolw.js` gzip 457.19KB、`EChartsTheme-*.js` gzip 225.67KB。旧 `full-yTi_27TG.js` 与 `esm-CBcusPEn.js` 已消除；剩余体积分别来自繁体词典和当前图表能力集合，其中 `cn2t` 已从“保存偏好导入即预取”改为实际转换入口触发，未牺牲简繁转换语义或图表功能继续强拆。
- 未执行真实 ngrok + Spotify OAuth 浏览器授权闭环；已验证 `/api/spotify/auth/status` 与 `/api/spotify/auth/data` 只读端点返回 200 和 request id，修复 `/api/spotify/auth/playing` token refresh 写连接问题，并用 contract 临时 DB 覆盖 OAuth PKCE login/callback 本地闭环、加密落库与 invalid state。
- 未在用户真实 Firefox.app / Safari.app 有界面会话中人工执行同等交互；当前跨浏览器自动化证据来自 Playwright Chromium / Firefox / WebKit（Safari-family），其中 WebKit 是 Safari-family 引擎 smoke，不等同用户 Safari.app 会话。
- 未逐一实打所有破坏性或外部依赖端点，例如断开 Spotify、导入生产数据、同步远程账号数据等，避免污染本地真实状态；本地 Settings/Chat mutation 与 Import job 调度已通过 contract 临时环境覆盖。
- Web Vitals 已用 headless Chrome lab probe 采集 Vite dev server 与本地 `vite preview` 生产构建的 LCP/CLS/合成 FID/TBT，preview 采样可用 `--api-base-url` 代理后端数据；仍未采集真实用户 RUM、Firefox/WebKit Web Vitals，也未在生产静态托管/CDN/HTTPS 环境跑 Lighthouse。

## 10 分钟快速验证

1. 启动后端：`source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend`
2. 启动前端：`cd frontend && npm run dev`
3. 打开 `http://127.0.0.1:5173/`，确认 Dashboard 有 KPI 与图表。
4. 切到移动宽度约 390px，访问 `/analysis/stats`、`/analysis/charts`，页面不能横向拖动。
5. 访问 `/billboard/number-ones`、`/billboard/all-time`、`/billboard/records`，确认三页能加载业务内容。
6. 访问 `/account`、`/settings`，确认账户数据和设置区块能渲染。
7. 打开 `http://127.0.0.1:8000/docs`，快速试 `/api/health`、`/api/billboard/records`、`/api/spotify/auth/status` 和 `/api/spotify/auth/login`（按本机配置返回 `auth_url` 或受控 503）。
8. 运行 `.venv/bin/python scripts/api_smoke_probe.py` 和 `.venv/bin/python scripts/api_boundary_probe.py`，确认 96 个只读 GET 与 19 个边界 GET 全绿。
9. 运行 `node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0`、`node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173`、`node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000`、`node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173`、`node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173`、`node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000`、`node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173` 和 `node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000`，确认路由、交互、图表交互、长列表分页/分段加载与三浏览器引擎 smoke 全绿。
10. 运行 `sh scripts/phase5_check.sh`，确认最低矩阵仍全绿；需要完整非破坏性矩阵时，运行 `sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173`。
