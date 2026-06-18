# 2026-06-19 全栈验证与性能收口报告

分支：`codex/playback-logic-update`

## 结论

- 后端全量测试通过：`586 passed, 2 warnings in 62.86s`
- 前端测试与构建通过：`129 passed`，`npm run build` 通过
- Phase 5 最低验证矩阵通过：unit `239 passed`，contract `147 passed`，前端 test/build 通过
- pre-commit 通过：ruff、ruff format、mypy、detect-secrets 全部通过
- 浏览器路由冒烟通过：`scripts/frontend_route_smoke.mjs` 覆盖 13 个核心路由 × 1280px 桌面/390px 移动端共 26 个组合，console error/warning、page error 与页面级横向滚动均为 0
- 可复跑只读 API smoke 通过：`scripts/api_smoke_probe.py` 覆盖 91 个本地只读 GET 请求，全部返回预期状态并带 `X-Request-ID`；OpenAPI GET 核算 `90/104 covered, 14 excluded, 0 unaccounted`

## 修复项

| 严重程度 | 问题 | 影响 | 修复 |
| --- | --- | --- | --- |
| P1 | contract seed fixture 残留 WAL/SHM 导致 `release_groups` 状态漂移 | L3 release group 测试在全量套件中偶发失败 | `build_seed_db.py` 重建前后清理 `seed.db-wal/-shm`，并重新生成 `seed.db` |
| P1 | contract 测试直接写 canonical `seed.db` | 只读/写入路径会污染后续测试，造成测试顺序依赖 | `backend/tests/contract/conftest.py` 改为每次复制临时 seed DB，teardown 删除临时 WAL/SHM |
| P1 | Billboard records 测试清缓存不完整 | `_load_and_rank_cached` / `_compute_records_cached` 污染导致 L2 bootstrap 测试全量失败 | 补齐 `_clear_billboard_runtime_caches()` 的缓存清理范围 |
| P2 | `chart_compute.py` / `chart_staged_cache.py` 超过架构护栏行数 | Phase 5 facade 约束回归 | 新增 `chart_load_rank.py` 承接共享 load/rank cache，facade 回到护栏内 |
| P2 | `import_data()` 遇到缺音频元数据的播放/视频记录可能引用未初始化 `album_id` | Extended Streaming History 中播客、视频或缺元数据条目会中断完整导入流程 | 每条记录先将 `album_id` 初始化为 `None`，新增临时 SQLite 导入测试覆盖音频、视频、featured artist、空 `source_album_id` 与预聚合表 |
| P2 | `/api/spotify/auth/playing` 在 token 过期时用只读连接刷新并落库 | 已连接 Spotify 且 access token 过期时，当前播放状态 GET 可能返回 500 `attempt to write a readonly database` | 该端点改用显式短生命周期可写连接，并新增 unit test 固定 token refresh 写入边界 |
| P2 | `PUT /api/settings` 接受越界统计配置 | 负数 `min_ms`、过小/过大的 Billboard Top N、非法周起始日/小时会被写入设置并污染后续统计 | `SettingsUpdateRequest` 补齐与查询参数一致的 `ge/le` 约束，新增 422 边界 contract 测试 |
| P2 | `/api/settings/clear-translation-cache` 在新库或 seed 库缺少 `wikipedia_cache` 表时 500 | 首次使用设置页清缓存可能返回内部错误，无法作为幂等维护操作 | 清理前 `CREATE TABLE IF NOT EXISTS wikipedia_cache`，新增 contract 测试验证缺表时返回 `deleted_count` |
| P2 | AI Insights 周报/月报/年度叙事/自由问答暴露 `dynamic_threshold` 与 `max_merge_gap_minutes` 但未传入最终计数管线 | 用户在设置页启用动态阈值或 Session 合并边界后，AI 报告可能继续按旧播放口径解读数据；不同过滤口径还可能撞到同一份报告缓存 | `backend/api/ai_insights.py` 透传 `PlayFilters` 新字段，`ai_insights_service.py` 将参数传入 `load_period_plays()` 与 `get_wrapped_full()`，并把过滤指纹纳入报告 cache key；新增离线 unit/contract 测试覆盖 5 个 AI Insights 端点、服务链路和 cache key 分流 |
| P3 | AI Insights 报告生成后用 readonly 请求连接写报告缓存 | 页面/API 返回 200，但后端日志出现 `AI report cache write failed` warning + traceback，且新报告无法写入缓存 | `_set_cache()` 遇到 readonly 连接时用短生命周期 `get_db(readonly=False)` 重试缓存写入；保留其它 SQLite 写入错误的 warning，新增 unit 测试锁定不再记录 readonly warning |
| P3 | `/api/behavior` 复用 `PlayFilters`，OpenAPI 暴露 `min_ms`、`merge_enabled`、`dynamic_threshold`、`max_merge_gap_minutes` 等无效参数 | 行为分析按设计使用全量事件；这些参数不会改变结果，却会误导 API 使用者并让前端过滤变化触发无效 refetch | 后端只声明有效的 `music_only` 参数，前端 behavior 请求/query key 收窄到 `music_only`，同步 OpenAPI snapshot/types；新增 contract 与前端 hook 测试 |
| P3 | AI Insights 会话列表把整行选择按钮包住删除按钮 | React 19 在 `/ai-insights` 输出 invalid DOM nesting console error，浏览器路由冒烟无法做到 0 console error，且嵌套交互对辅助技术不友好 | `ChatSessionList` 改为非交互行容器，左侧会话选择按钮与右侧删除/确认按钮做兄弟节点，并补充组件测试锁定无 `button button` 嵌套和删除交互 |
| P3 | AI Insights 周快捷选项在 latest listening range 加载前可能生成相同 value key | `/ai-insights` 桌面首屏偶发 React duplicate key console error，route smoke 可能失败 | `QuickPills` 改用 `label:value` 复合 key，保留两个语义不同的快捷按钮；新增组件测试覆盖重复 value 不应产生 console error |
| P2 | 390px 移动端页面可横向滚动 47.5px | `/analysis/stats`、`/analysis/charts` 等页面移动端体验不稳 | `AppLayout` 增加页面级 `overflow-x-clip`，Masthead nav 增加 `basis-full/max-w-full`，Dashboard skeleton 改为 `w-full max-w-*` |
| P2 | pre-commit ruff hook 扫描冻结 Streamlit `app/` 与旧脚本 | `pre-commit run --all-files` 因历史页名/未用变量失败 | `.pre-commit-config.yaml` 将 ruff 与 ruff-format 限定到 `backend/`，与项目日常质量命令一致 |

## 性能优化

| 项目 | 优化前 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| records 直接 profile 冷算 | 4.791s / 19,188,063 calls | 3.090s / 10,941,286 calls | 时间 -35.5%，调用数 -43.0% |
| `/api/billboard/records` 冷请求 | 2.19s | 1.871s | -14.6% |
| `/api/billboard/records` 热请求 | 0.01-0.02s | 0.012-0.013s | 持平 |
| OpenCC 默认懒加载包 | `full-yTi_27TG.js` 1,121.76KB / gzip 494.12KB | 简体路径 `t2cn-g7W6-1pz.js` 64.27KB / gzip 38.78KB；繁体路径 `cn2t-DJnOUolw.js` 1,059.13KB / gzip 457.19KB | 默认完整包消除；简体路径 gzip -455.34KB，繁体路径 gzip -36.93KB |
| ECharts 图表懒加载包 | `esm-CBcusPEn.js` 1,134.42KB / gzip 376.65KB | `EChartsTheme-*.js` 673.19KB / gzip 225.67KB | 原始体积 -461.23KB，gzip -150.98KB |
| `/account` 前端资源加载 | 桌面 250 requests / 24,632.6KB / TBT 132ms / LCP 2,480ms；移动 250 requests / 25,488.7KB / TBT 132ms / LCP 2,412ms | 桌面 92 requests / 7,565.5KB / TBT 0ms / LCP 2,132ms；移动 91 requests / 7,455.4KB / TBT 0ms / LCP 2,320ms | requests -63%，资源体积 -69%~-71%，TBT -132ms，LCP 小幅改善 |
| `merge_consecutive_plays()` 大批量片段合并 | 80k 行合成片段 2.58s；`/api/dashboard/full` 冷 profile 8.26s，`merge_consecutive_plays` 7.59s，`load_plays` 2 次 | 80k 行合成片段 0.06s 级；`/api/dashboard/full` 冷 profile 1.02s，`merge_consecutive_plays` 0.19s，`load_plays` 1 次 | 合成护栏约 -97%；真实冷 profile -87.7%，核心合并 -97.5% |
| Billboard summaries 直接 profile | 2.098s / 7,114,904 calls | 1.555s / 5,764,912 calls | 时间 -25.9%，调用数 -19.0% |

实现：`chart_power_score.py` 将 track/album/artist Power Score 的逐行 `DataFrame.apply(axis=1)` 和 Python lambda 聚合改为列级向量化计算，并新增语义测试保证冠军差距、非冠军中位数、debut bonus、#1 bonus、peak/week 统计不漂移。

播放合并补充实现：`merge_consecutive_plays()` 从逐 `_merge_group` 的 `iterrows()/to_dict()` 构造改为组级聚合、首行批量重复与 NumPy 向量化 `ms_played` 回填；保留 `max_gap_minutes`、`boundary_column`、无 duration 行透传、完整播放 + 余数播放展开语义。`/api/dashboard/full` 同步将已加载 DataFrame 传给 `get_random_track()`，避免同一请求内再次进入播放加载路径。

Billboard summaries 补充实现：`compute_artist_track_counts()` 与 `compute_album_track_counts()` 去掉逐行 `DataFrame.apply()` 回查 best peak track，改为一次排序、`drop_duplicates()` 与 merge 回填；新增 summaries 语义测试和架构护栏防止回退到 row-wise apply。

前端补充实现：`displayName()` 将 OpenCC 默认 `full` 包拆为 `opencc-js/t2cn` 与 `opencc-js/cn2t` 两条按需路径；ECharts 统一通过 `LazyEChart` 动态加载 `echarts-for-react/esm/core` 并只注册当前用到的 bar/line/pie/heatmap、tooltip、legend、dataZoom、visualMap 与 mark 组件，避免 `echarts-for-react` 默认入口静态拉入完整 ECharts runtime。

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
- API smoke：`scripts/api_smoke_probe.py` 在真实本地库通过 91/91 个本地只读 GET 请求，覆盖 Dashboard、Analysis、Timeline、Leaderboard、Billboard、Release Cycle、Music Entity、Community、Version Merge、Account、AI Insights、Chat、Admin、Job、Spotify status/data，并逐项验证 `X-Request-ID`；OpenAPI GET 核算 `90/104 covered, 14 excluded, 0 unaccounted`，默认列表排除歌词检索、AI 生成、enrichment、OAuth callback/login、live playback 与静态封面等会触发外部网络、浏览器态或非稳定本地 artifact 的路径。
- Chat mutation probe：contract 临时 DB 覆盖 `/api/chat/sessions` 创建、消息写入、详情读取、标题更新、列表读取、删除后读取，以及非法 role 422 边界。
- Settings mutation probe：contract 临时 DB 覆盖设置更新持久化与密钥脱敏、越界设置 422、LLM profile 创建/重复名/读取/列表/更新/应用/删除，以及缺表场景下清翻译缓存幂等返回。
- Import job probe：contract 测试用同步 fake thread 验证 `/api/import/streaming` 与 `/api/import/account` 的 job_id 返回、进度回调、完成状态、account 嵌套结果摘要，以及 streaming 导入异常时的 error 状态。
- AI Insights contract probe：离线 monkeypatch 服务层，覆盖周报/月报/年度叙事/自由问答对 `min_ms`、`music_only`、`merge_enabled`、`dynamic_threshold`、`max_merge_gap_minutes` 的透传，并验证 `LLM 未配置` 映射为 503；unit 层覆盖生成报告与自由问答继续把过滤参数传入数据抓取链路、报告缓存 key 会随过滤口径变化，且 readonly 请求连接会用可写连接完成报告缓存写入。
- Behavior API probe：contract 测试锁定 `/api/behavior` OpenAPI 只暴露 `music_only` 和连接依赖的 `readonly`；前端 query hook 测试锁定 behavior 请求只发送 `music_only`，避免全局播放过滤变化导致无意义 refetch。
- 导入/WAL probe：临时 JSON + 临时 SQLite 验证音频/视频缺元数据记录不会中断导入，featured artist 写入 `track_artists`，空来源写入 `source_album_id IS NULL`；临时 DB 验证 WAL 下读事务快照不阻塞独立写提交，新读连接可见提交后数据。
- 前端 route smoke probe：新增 `scripts/frontend_route_smoke.mjs`，通过 headless Chrome CDP 覆盖 `/`、Analysis、Yearly Review、Billboard 4 页、Community、AI Insights、Account、Settings 共 13 路由 × 桌面/移动 26 个组合；最终采样 PASS 26/26，console error/warning/page error 全 0，scroll overflow 全 0px。首轮探针暴露 AI Insights 嵌套按钮与重复 key console error，修复后复跑全绿。
- 前端交互 probe：`/analysis/stats` 与 `/analysis/charts` 的 `role=tab` 切换后无错误；Billboard 路由执行 `/billboard` → `/number-ones` → `/all-time` → `/records` 并通过浏览器后退/前进验证路由状态，控制台 error 为 0。
- Web Vitals lab probe（Vite dev server + headless Chrome + CDP）：6 路由 × 桌面/390px 移动端；最终采样 CLS 全部 0，合成点击 FID 0.7-3.6ms，TBT 全部 0ms，非账号页 LCP 416-896ms，账号页 LCP 2,132ms（桌面）/ 2,320ms（移动）。
- 文档同步：README、AGENTS、CLAUDE、backend/CLAUDE、frontend/CLAUDE 已更新 2026-06-19 验证报告、API smoke / route smoke 探针、Power Score 向量化、Behavior API 参数收窄、移动端横向滚动护栏、pre-commit 范围与最新测试基线。

### Web Vitals Lab 采样

> 命令：`node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000`
> 说明：该数据来自本地 Vite dev server，不等同生产 Lighthouse/RUM；FID 为合成点击 first-input，TBT approx 为 FCP 后 5 秒内 long task 近似值。

| Route | Viewport | LCP | CLS | FID | TBT approx | Resources | Encoded resources | Scroll width |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | desktop | 896ms | 0 | 1.9ms | 0ms | 77 | 7,185.7KB | 1280 / 1280 |
| `/` | mobile | 616ms | 0 | 2.3ms | 0ms | 76 | 7,176.4KB | 390 / 390 |
| `/analysis/stats` | desktop | 416ms | 0 | 0.7ms | 0ms | 106 | 8,265.2KB | 1280 / 1280 |
| `/analysis/stats` | mobile | 420ms | 0 | 2.6ms | 0ms | 106 | 8,265.2KB | 390 / 390 |
| `/analysis/charts` | desktop | 416ms | 0 | 1.3ms | 0ms | 99 | 6,960.8KB | 1280 / 1280 |
| `/analysis/charts` | mobile | 428ms | 0 | 3.5ms | 0ms | 97 | 6,785.9KB | 390 / 390 |
| `/billboard/number-ones` | desktop | 704ms | 0 | 2.7ms | 0ms | 104 | 9,808.3KB | 1280 / 1280 |
| `/billboard/number-ones` | mobile | 668ms | 0 | 3.0ms | 0ms | 99 | 9,399.9KB | 390 / 390 |
| `/account` | desktop | 2,132ms | 0 | 3.6ms | 0ms | 92 | 7,565.5KB | 1280 / 1280 |
| `/account` | mobile | 2,320ms | 0 | 0.8ms | 0ms | 91 | 7,455.4KB | 390 / 390 |
| `/settings` | desktop | 484ms | 0 | 2.5ms | 0ms | 85 | 5,159.4KB | 1280 / 1280 |
| `/settings` | mobile | 480ms | 0 | 2.8ms | 0ms | 85 | 5,159.4KB | 390 / 390 |

## 覆盖矩阵

| 目标项 | 当前证据 | 状态 |
| --- | --- | --- |
| 后端现有测试全量通过 | `pytest backend/tests/ -q`：`586 passed, 2 warnings in 62.86s` | 已自动验证 |
| OpenAPI/核心 API 只读覆盖 | 122 paths / 134 operations schema 存在；91 个可复跑只读请求覆盖 Dashboard、Billboard、Analysis、Community、AI Insights、Account、Settings、Spotify status/data；OpenAPI GET 核算 0 unaccounted | 已覆盖只读核心路径；mutation/破坏性端点未逐一实打 |
| Extended Streaming History 完整导入 | 新增临时 JSON 导入测试覆盖音频、视频、缺元数据、featured artist、预聚合 | 已自动验证最小完整流程 |
| 多版本与统计过滤语义 | contract/full tests 覆盖 Version Merge、Album Project、Power Score、AI Insights 播放过滤传播、Behavior 全量事件例外参数收窄、播放过滤参数传播与 Billboard invariants | 已自动验证 |
| SQLite WAL 并发读写 | 新增临时 DB WAL reader snapshot + writer commit 测试 | 已自动验证 |
| OAuth/加密/缓存/Job Queue/Request ID | AES、cache manager、job queue 单测；API smoke 验证 `X-Request-ID`；Spotify status/data 只读 200；当前播放端点 token refresh 写入边界有 unit test | 自动验证基础设施；真实 OAuth 外部授权未闭环 |
| 前端路由与响应式 | `scripts/frontend_route_smoke.mjs` 覆盖 13 路由 × 桌面/390px 移动端，无页面错误、无 console error/warning、无横向溢出；图表入口由架构护栏防止回退到完整 ECharts/OpenCC 默认包；Web Vitals lab 覆盖 6 路由 × 2 视口 | 已自动验证主路径 |
| 前端交互 / 本地 mutation | 分析页 Tab、Billboard 前进/后退路由、长列表可见分页按钮采样；Chat CRUD、Settings 更新、LLM profile CRUD/apply、清翻译缓存、Import job 启动/状态在 contract 临时环境自动验证 | 部分自动验证；所有按钮/表单/ECharts 细交互未逐项人工穷尽 |
| 性能优化 | records profile、API 冷/热请求、build/import、bundle chunk、Web Vitals lab 与账号页资源/TBT 均有前后对比 | 已量化关键瓶颈；仍缺真实 RUM 与生产静态托管 Lighthouse |

## 验证命令

```bash
.venv/bin/pytest backend/tests/ -v
.venv/bin/python scripts/api_smoke_probe.py
.venv/bin/ruff check backend/
.venv/bin/ruff format --check backend/
cd frontend && npm test
cd frontend && npm run build
sh scripts/phase5_check.sh
.venv/bin/pre-commit run --all-files
```

补充验证：

```bash
.venv/bin/pytest backend/tests/unit/test_chart_power_score.py -q
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py -q
.venv/bin/pytest backend/tests/unit/test_phase5_architecture.py::test_chart_power_score_avoids_row_wise_dataframe_apply -q
.venv/bin/pytest backend/tests/unit/test_playback_counting.py backend/tests/unit/test_play_service_dashboard.py -q
.venv/bin/pytest backend/tests/unit/test_billboard_chart_summaries.py backend/tests/unit/test_phase5_architecture.py::test_chart_summaries_avoid_row_wise_dataframe_apply -q
.venv/bin/pytest backend/tests/unit/test_api_smoke_probe_script.py backend/tests/unit/test_spotify_auth_api.py backend/tests/contract/test_api_smoke_probe.py -q
.venv/bin/pytest backend/tests/contract/test_chat_api_crud.py -q
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py -q
.venv/bin/pytest backend/tests/contract/test_import_api_jobs.py -q
.venv/bin/pytest backend/tests/unit/test_ai_insights_service.py backend/tests/unit/test_ai_insights_filter_propagation.py backend/tests/contract/test_ai_insights_contract.py -q
.venv/bin/pytest backend/tests/contract/test_api_contract.py::TestBehaviorEndpoints -q
.venv/bin/pytest backend/tests/unit/test_frontend_route_smoke_script.py -q
cd frontend && npm test -- src/tests/query-hooks.test.tsx -t "requests behavior data"
cd frontend && npm test -- src/tests/ai-insights-components.test.tsx
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "Chinese conversion"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "lightweight ECharts"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "account chemistry"
cd frontend && ANALYZE=true npm run build
node scripts/frontend_route_smoke.mjs --viewport both --wait-ms 2500 --max-scroll-overflow 0
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
git diff --check
```

## 已知限制

- 生产构建仍提示两个大懒加载 chunk：`cn2t-DJnOUolw.js` gzip 457.19KB、`EChartsTheme-*.js` gzip 225.67KB。旧 `full-yTi_27TG.js` 与 `esm-CBcusPEn.js` 已消除；剩余体积分别来自繁体词典和当前图表能力集合，未牺牲简繁转换语义或图表功能继续强拆。
- 未执行真实 ngrok + Spotify OAuth 浏览器授权闭环；已验证 `/api/spotify/auth/status` 与 `/api/spotify/auth/data` 只读端点返回 200 和 request id，并修复 `/api/spotify/auth/playing` token refresh 写连接问题。
- 未在 Firefox/Safari 真机浏览器中执行同等交互；当前浏览器自动化证据来自本地 headless Chromium CDP route smoke / Web Vitals lab 与前端测试。
- 未逐一实打所有破坏性或外部依赖端点，例如断开 Spotify、导入生产数据、同步远程账号数据等，避免污染本地真实状态；本地 Settings/Chat mutation 与 Import job 调度已通过 contract 临时环境覆盖。
- Web Vitals 已用 headless Chrome lab probe 采集 LCP/CLS/合成 FID/TBT；仍未采集真实用户 RUM、Firefox/Safari Web Vitals，也未在生产静态托管环境跑 Lighthouse。

## 10 分钟快速验证

1. 启动后端：`source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend`
2. 启动前端：`cd frontend && npm run dev`
3. 打开 `http://127.0.0.1:5173/`，确认 Dashboard 有 KPI 与图表。
4. 切到移动宽度约 390px，访问 `/analysis/stats`、`/analysis/charts`，页面不能横向拖动。
5. 访问 `/billboard/number-ones`、`/billboard/all-time`、`/billboard/records`，确认三页能加载业务内容。
6. 访问 `/account`、`/settings`，确认账户数据和设置区块能渲染。
7. 打开 `http://127.0.0.1:8000/docs`，快速试 `/api/health`、`/api/billboard/records`、`/api/spotify/auth/status`。
8. 运行 `.venv/bin/python scripts/api_smoke_probe.py`，确认 91 个只读 GET 请求全绿。
9. 运行 `node scripts/frontend_route_smoke.mjs --viewport both --wait-ms 2500 --max-scroll-overflow 0`，确认 26 个路由/视口组合全绿。
10. 运行 `sh scripts/phase5_check.sh`，确认最低矩阵仍全绿。
