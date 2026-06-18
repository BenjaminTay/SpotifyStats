# Phase 5：产品化收口与可持续迭代基线

> 状态台账日期：2026-06-12  
> 最近更新：2026-06-12 Phase 5.4 最终验收 + Phase 5.5 规划
> 阶段定位：四阶段架构优化后的持续治理阶段  
> 主线策略：不新增大型业务功能，优先收紧数据获取、外部调用、可观测、验证与文档台账

## 目标

Phase 5 负责把现有 FastAPI + React 产品线收敛到可持续迭代状态：

- 前端 GET 数据获取统一到 TanStack Query 与 `queryKeys`
- 后端外部调用继续向 `providers/` 与 `infrastructure/http/` 收敛
- 剩余大文件按触碰范围逐步拆分，不改变统计口径
- 长列表优先通过分页或虚拟化降低渲染压力
- 请求链路补充 `X-Request-ID`，日志可关联单次请求
- 建立本地/CI 最低验证矩阵，阶段收尾保留验证结果

## 当前已落地

| 项目 | 状态 | 说明 |
|---|---|---|
| Query key 体系扩展 | 已完成 | 覆盖 dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge/community/aiInsights |
| Billboard hooks Query 迁移 | 已完成 | `useBillboard`、`useBillboardWeekly`、records、all-time 数据读取改为 TanStack Query |
| Settings Query 迁移 | 已完成 | `useSettings` 主数据与 LLM profile/Spotify status fetch 接入 Query Client |
| Analysis Query 迁移 | 已完成 | `useAnalysisOverview`、`useApiData`、`analysisApi` 通过 Query Client 去重与缓存 |
| Yearly Review Query 迁移 | 已完成 | 自定义年度回顾、年份列表、官方 Wrapped hub 接入 Query |
| Request ID | 已完成 | 请求自动生成/透传 `X-Request-ID`，响应返回同名 header，日志格式包含 request id |
| Provider 错误基线 | 已完成 | 新增 Provider 错误分类；共享 `HttpClient` 将网络失败映射为 `ProviderNetworkError` |
| Wikipedia service Provider 迁移 | 已完成 | `wikipedia_service.py` 使用 `WikipediaProvider` 执行 MediaWiki query/page URL，不再直接新建 `urllib.request.Request` |
| Release Cycle service Provider 迁移 | 已完成 | Spotify token、album batch、album search 改由 `SpotifyProvider` 封装，service 层不再直接 `urlopen` |
| Core Spotify HTTP 收敛 | 已完成 | `spotify_utils.py` 的 token/OAuth/API GET 改用共享 `HttpClient`；`version_merge.py` 的 album batch API 改用 `SpotifyProvider` |
| Cover download job | 已完成 | 后台封面下载改用共享 `HttpClient`，不再直接新建 `urllib.request.Request` |
| 详情页模块级数据缓存清理 | 已完成 | `TrackDetailPage`、`AlbumDetailPage`、`ArtistDetailPage` 的 enrichment/release-cycle 响应迁入 TanStack Query |
| RecordsPage 前端拆分 | 已完成 | `RecordsPage.tsx` 压缩为 115 行 route container；records primitives/data/sections 拆入 `frontend/src/features/billboard/records/` |
| Records 表格分页基线 | 已完成 | `MiniRankTable` 作为 records 专用分页表格组件保留 10 行分页，并通过真实渲染测试证明只渲染当前页 |
| AllTimeCharts 前端拆分 | 已完成 | `AllTimeChartsPage.tsx` 压缩为 192 行 route container；all-time 行合并/筛选/排序与表格渲染拆入 `frontend/src/features/billboard/all-time/` |
| AllTimeCharts 分页基线 | 已完成 | `AllTimeTable` 保留 50 行分页、列宽 UI 状态与排序交互；页面层不再直接渲染 `<table>`，真实渲染测试覆盖当前页 DOM 限制 |
| NumberOnes 前端拆分 | 已完成 | `NumberOnesPage.tsx` 保持 5 行 route wrapper；`NumberOnesExperience.tsx` 压缩为 121 行 feature container；计算、primitives、tracks/albums/artists sections 拆入 `frontend/src/features/billboard/number-ones/` |
| 音乐详情页 route container 化 | 已完成 | `ArtistDetailPage.tsx`、`AlbumDetailPage.tsx` 均压缩为 5 行 route wrapper；完整体验迁入 `frontend/src/features/music/details/` |
| 音乐详情页共享 primitives | 已完成 | `KpiCard`、`KpiStrip`、`PlaysCell` 与日期/数字格式化抽入 `MusicDetailPrimitives.tsx`，减少 Artist/Album 详情页重复实现 |
| 音乐详情页 feature 二次拆分 | 已完成 | `AlbumStoryCard`、`InfoRow`、`MiniStat`、`MatrixCell` 抽入 `AlbumDetailPrimitives.tsx`；Artist 发行周期列表抽入 `ArtistReleaseCycleSection.tsx` 与 `ArtistReleasesSection.tsx`；Artist/Album hero、tabs 与 loading skeleton 抽入 `MusicDetailHeader.tsx`、`MusicDetailSkeletons.tsx`；榜单概览 KPI/趋势/周榜历史抽入 `MusicChartOverviewSection.tsx`；单曲/专辑表格与 Artist 生涯抽入 `MusicTracksSection.tsx`、`ArtistAlbumsSection.tsx`、`ArtistCareerSection.tsx`；Album 发行档案编排层抽入 `AlbumEraSection.tsx`，并继续拆出 overview/timeline/composition/matrix/overflow/enrichment/personal-story 子 section |
| 前端展示类型硬化 | 已完成 | `frontend/src/types/billboard.ts` 补齐 Billboard、音乐详情、release-cycle 与 enrichment 展示字段，并保留展示记录索引签名以覆盖动态中文字段；`npm run build` 重新通过 |
| Billboard records 输出层拆分 | 已完成 | `_enrich_records_artist_names`、`_add_cover_urls`、`_serialize_records` 迁入 `backend/domains/billboard/records_output.py`；`records.py` 保留兼容 import |
| Billboard records championship 拆分 | 已完成 | 冠单/回冠/空冠/艺人同周占榜等 #1 相关 record family 迁入 `backend/domains/billboard/records_championship.py`；`records.py` 行数从约 1282 降至约 977 |
| Billboard records longevity 拆分 | 已完成 | 最长在榜、连续在榜、无 Top 5 长在榜、万年老二、回榜、同排名停留、艺人生涯跨度与最快出榜迁入 `backend/domains/billboard/records_longevity.py`；`records.py` 行数降至约 630 |
| Billboard records movement 拆分 | 已完成 | 最大升跌幅、同专辑同周占榜、登顶路与 Top 10 同周占榜迁入 `backend/domains/billboard/records_movement.py`；`records.py` 行数降至约 549 |
| Billboard records hall-of-fame 拆分 | 已完成 | all-time greatest、year-end #1、专辑/艺人 power ranking 与 decade best 迁入 `backend/domains/billboard/records_hall_of_fame.py`；`records.py` 行数降至约 455 |
| Billboard records self-replacement 拆分 | 已完成 | 自替换#1与阻挡王 record family 迁入 `backend/domains/billboard/records_self_replacement_blocker.py`；`records.py` 降至 88 行纯编排 facade |
| Billboard records endurance 拆分 | 已完成 | #2 未冠/回榜/稳定排名 record family 迁入 `backend/domains/billboard/records_endurance.py`；`records_longevity.py` 从约 358 降至 172 行 |
| Billboard chart 周榜排名拆分 | 已完成 | `compute_weekly_rankings`/`compute_album_weekly_rankings`/`compute_artist_weekly_rankings`/`_add_running_metrics` 迁入 `backend/domains/billboard/chart_ranking.py` |
| Billboard chart 走势评分拆分 | 已完成 | Power Score 参数/`compute_power_scores`/`compute_album_power_scores`/`compute_artist_power_scores` 迁入 `backend/domains/billboard/chart_power_score.py` |
| Billboard chart summaries 拆分 | 已完成 | `compute_track_summary`、artist/album summary 与 track-count helper 迁入 `backend/domains/billboard/chart_summaries.py`；`chart_compute.py` 从约 1515 降至 631 行 |
| Billboard chart staged cache 拆分 | 已完成 | `_load_and_rank()` 与 `_compute_weekly_data_cached()`/`_compute_power_scores_cached()`/`_compute_summaries_cached()`/`_compute_records_cached()` 迁入 `backend/domains/billboard/chart_staged_cache.py`；`chart_compute.py` 从 631 降至 319 行 |
| Billboard chart staged API 拆分 | 已完成 | `compute_weekly_data()`、`compute_power_scores_staged()`、`compute_summaries_staged()`、`compute_records_staged()` 迁入 `backend/domains/billboard/chart_staged_api.py`；`chart_compute.py` 从 319 降至 227 行 |
| Billboard chart compute facade 收口 | 已完成 | `chart_compute.py` 仅保留旧 `/api/billboard/data` 聚合入口、兼容 re-export 与 Cache Manager registration |
| Phase 5 架构红线测试 | 已完成 | 新增后端 service/core urllib 静态测试与前端详情页模块级 API Map 缓存、hero/tabs、overview、tracks/albums/album era/artist releases orchestration 静态测试，后端 records/chart/staged cache/staged API 拆分护栏测试，前端长列表分页渲染测试 |
| Phase 5 本地验证脚本 | 已完成 | `scripts/phase5_check.sh` 串联后端 unit/contract、ruff、前端 test/build |
| Community 新页面纳管 | 已完成 | `/community`、`/community/post/:postId`、`/community/account/:handle` 已接入 lazy route、feature 组件与 `useCommunity` Query hooks；Feed 使用 offset/limit 分页与 infinite query |
| AI Insights 新页面纳管 | 已完成 | `/ai-insights` 已接入 lazy route、`useAiInsights` Query/Mutation hooks、chat session Query keys 与独立 `docs/2026-06-11-ai-insights-module.md` 模块文档 |
| Phase 5.4-A 架构护栏补齐 | 已完成 | `phase5-architecture.test.ts` 从 17 测试扩展到 105+ 测试，覆盖 AI Insights/Community/Billboard Versus/Account Habits/Track Detail 所有新增页面；route container ≤10 行、Experience ≤450 行、section ≤300 行等负面断言 |
| Phase 5.4-B TrackDetail route container 化 | 已完成 | `TrackDetailPage.tsx` 574→5 行；`TrackDetailExperience.tsx` (237 行) + `TrackOverviewSection.tsx` (204 行) + `TrackLyricsSection.tsx` (157 行) 拆入 `features/music/details/` |
| Phase 5.4-C Account Habits 下沉 feature | 已完成 | `pages/account/HabitsTab.tsx` 933 行删除；9 文件拆入 `features/account/habits/`：HabitsTab 编排器 (79 行)、habitsData.ts (149 行)、primitives、SearchHistory/FanTiers/Podcast/Marquee/Video/PersonalityHero sections |
| Phase 5.4-D AI Insights 产品化收口 | 已完成 | `AiInsightsExperience` 560→427 行 + 新 `AiInsightsTimeSelectors.tsx` (235 行)；`ChatInterface` 423→312 行 + 新 `ChatMessageList.tsx` (136 行)；5 个 AI Insights + 6 个 Chat 端点补 `response_model`；7 个新 Query 行为测试 |
| Phase 5.4-E API 契约硬化 | 已完成 | Community post detail 补 `PostDetailResponse` model；`version_merge.py` 12 个端点全部补 `response_model`（ReleaseGroup/GroupMember/UngroupedAlbum/TrackComparison/DetectionResult/Status/CreateGroup/ApplyDetection 等 12 个 Pydantic 模型） |
| Phase 5.4-F Bundle 与 chunk 治理 | 已完成 | SettingsPage: VersionMergeSection + LLMTranslationSection 懒加载（148→17 kB, -88%）；RecordsPage: 5 非默认 tab 懒加载（64→20 kB, -69%）；AccountCenterPage: HabitsTab 懒加载（67→44 kB, -34%）；三项合计首屏节省 ~178 kB |
| Phase 5.4-G 文档与 CI 台账同步 | 已完成 | AGENTS/CLAUDE/台账全部刷新至 Phase 5.4 系列最新状态 |
| Phase 5.4-H TrackDetail 歌词 Query 漏网修复 | 已完成 | TrackDetailExperience 歌词读取从手动 `fetchLyrics` + `useState` 改为 `useQuery`（`queryKeys.music.trackLyrics`）；架构护栏补 `setLyrics`/`fetchLyrics` 负面断言 |

## 文档收口审计：2026-06-09

| 检查项 | 结果 | 说明 |
|---|---|---|
| Phase 5 最低验证矩阵 | 通过 | `sh scripts/phase5_check.sh`：unit 100 passed、contract 14 passed、ruff passed、frontend 40 tests passed、build success |
| Billboard records facade | 已收口 | `backend/domains/billboard/records.py` 当前 88 行；records 已拆为 output + 8 个 record family 子模块 |
| Billboard chart compute | 已收口 | `backend/domains/billboard/chart_compute.py` 当前 227 行；ranking、power score、summaries、staged cache、staged API 均已拆出 |
| 文档一致性 | 已修正 | 台账、README、AGENTS、CLAUDE 已统一使用当前行数：`records.py` 88 行、`chart_compute.py` 227 行、`chart_staged_api.py` 114 行、`chart_staged_cache.py` 336 行 ✓ |

## 最新代码审计：2026-06-12（Phase 5.4-H 正式通过）

| 检查项 | 当前状态 | Phase 5 影响 |
|---|---|---|
| 最低验证矩阵 | 通过 | `sh scripts/phase5_check.sh`：unit 184 passed、contract 25 passed、ruff passed、frontend 106 tests passed、build success |
| OpenAPI Schema | 正常 | `app.openapi()` 生成 118 paths，无异常 |
| 新增路由 | 全部纳管 | `/community`、`/community/post/:postId`、`/community/account/:handle`、`/ai-insights`、`/billboard/versus` 全部 lazy load 且架构护栏覆盖完毕 |
| Query key 体系 | 已扩展 | `queryKeys` 当前 11 个命名空间（含 `music.trackLyrics`）；新增 GET 读取均走 Query；架构测试对 10 个文件执行 `new Map` 缓存回流负面断言 |
| Provider/urllib 红线 | 保持通过 | 业务 service 与 core Spotify 直接 `urllib.request.Request`/`urlopen` 静态护栏仍通过 |
| 模块级 API Map 缓存 | 未发现回归 | 架构测试持续监控，无回流 |
| 前端页面容器 | 已收口 | TrackDetailPage 574→5 行；所有 route container 均 ≤450 行，目标 ≤10 行 |
| 大组件治理 | 已完成 | HabitsTab 933 行已拆为 9 文件 feature；AiInsightsExperience 560→427 + TimeSelectors 235；ChatInterface 423→312 + ChatMessageList 136；VersionMergeSection 574 行仍在 feature 内但已懒加载 |
| API 契约 | 已硬化 | AI Insights (5)、Chat (6)、Community post detail (1)、Version Merge (12) 共 24 个端点全部补 `response_model` |
| Bundle/chunk | 已治理 | SettingsPage: 148→17 kB (-88%); RecordsPage: 64→20 kB (-69%); AccountCenterPage: 67→44 kB (-34%) |
| TrackDetail 歌词 Query | 已修复 | 手动 `fetchLyrics` + `useState` 改为 `useQuery`（`queryKeys.music.trackLyrics`），架构护栏补裸 GET 漏网断言 |

## Phase 5.4 最终验收记录（2026-06-12）

Phase 5.4 已于 2026-06-12 **正式通过**。本轮验收确认：架构护栏、页面拆分、API 契约、bundle 懒加载、TrackDetail 歌词 Query 漏网修复和文档口径收口均已完成。

| 验收项 | 结果 | 证据 |
|---|---|---|
| TrackDetail 歌词 Query | 通过 | `queryKeys.music.trackLyrics(trackId)` 已加入；`TrackDetailExperience.tsx` 通过 `useQuery` 读取歌词，并用 `enabled: activeTab === 'lyrics' && !!trackId` 保持懒触发 |
| Query 漏网护栏 | 通过 | `phase5-architecture.test.ts` 检查 `queryKeys.music.trackLyrics`，并负向断言不再出现 `setLyrics` / `fetchLyrics` |
| 文档口径 | 通过 | README、AGENTS、CLAUDE 与本台账均改为 Phase 5.4 A-H 完成口径 |
| 最低验证矩阵 | 通过 | `sh scripts/phase5_check.sh`：unit 184 passed、contract 25 passed、ruff passed、frontend 106 tests passed、build success |
| OpenAPI smoke | 通过 | `app.openapi()` 生成 118 paths，AI Insights 与 Version Merge response model 可被 schema 引用 |

Phase 5.4 收口后，当前阶段不再继续扩大重构范围；后续工作进入 Phase 5.5，以性能、类型同步、真实运行 smoke 与低风险持续治理为主。

## Phase 5.5：可观测性能、类型契约与真实运行治理规划

### Summary

Phase 5.5 的目标不是新增大功能，而是在 Phase 5.4 的产品化基线之上，补齐“可量化、可复查、可持续”的运行质量台账：控制大 vendor chunk、刷新 OpenAPI 类型、建立真实浏览器 smoke 流程，并把仍偏大的 AI/community 后端模块纳入按触碰拆分策略。

默认策略：

- 先量化性能与类型漂移，再做轻量拆分。
- 不在 Phase 5.5 强行拆所有后端大文件。
- 不改变现有用户可见统计口径、路由和公开 API。
- Streamlit 继续冻结维护，不迁回新功能。

### Milestone 1：Bundle 与 Vendor Chunk 专项

**目标**：定位 `full` / `esm` vendor chunk 超 1MB 的来源，形成可重复比较的 bundle 台账，并优先拆低风险依赖。

当前基线：

- 页面 chunk 已治理：SettingsPage 约 17 kB、RecordsPage 约 20 kB、AccountCenterPage 约 44 kB。
- 仍存在大 vendor chunk：`full` 与 `esm` 约 1.1 MB，属于后续性能专项。

执行内容：

1. 运行现有 bundle 分析能力：
   - `cd frontend && npm run build`
   - 如 `npm run analyze` 可用，输出可视化分析报告；如不可用，先用 Vite build chunk 输出建立文本台账。
2. 定位大 chunk 主要来源：
   - ECharts / `echarts-for-react`
   - calendar/date picker
   - markdown / sanitize
   - shadcn/floating-ui 组合依赖
3. 优先处理低风险拆分：
   - 确认 ECharts 只在图表组件内动态加载，不从 route 顶层静态进入。
   - 确认 AI Insights 的 markdown/sanitize 只随 AI 页面或 chat/message 组件加载。
   - 确认 calendar 只随 AI Insights 日期选择器或相关组件加载。
4. 记录 build 输出中的关键 chunk：
   - `SettingsPage`
   - `RecordsPage`
   - `AccountCenterPage`
   - `AiInsightsPage`
   - `full`
   - `esm`

验收标准：

- 不引入新的首屏大页面 chunk 回归。
- `SettingsPage`、`RecordsPage`、`AccountCenterPage` 保持 Phase 5.4 后的数量级。
- `full` / `esm` 来源被记录到台账；若无法立即拆小，也要有明确归因。
- `cd frontend && npm run build` 通过。

### Milestone 2：OpenAPI 类型刷新与前端类型漂移治理

**目标**：在后端 `response_model` 稳定后，刷新 OpenAPI 生成类型，并逐步减少前端手写类型与后端 schema 的漂移。

当前基线：

- AI Insights 5 个端点、Chat 6 个端点、Community post detail 1 个端点、Version Merge 12 个端点已补 `response_model`。
- OpenAPI smoke 已能生成 118 paths。
- 前端仍有不少手写展示类型，短期不强制全量替换。

执行内容：

1. 运行 OpenAPI smoke：
   ```bash
   source .venv/bin/activate
   python -c "from backend.main import app; schema = app.openapi(); print(len(schema.get('paths', {})))"
   ```
2. 运行类型生成：
   ```bash
   cd frontend && npm run generate-types
   ```
3. 对比生成结果：
   - 若生成文件稳定，只提交必要更新。
   - 若生成结果过大，先记录差异，不强行重构所有调用方。
4. 优先迁移高漂移风险类型：
   - AI Insights response
   - Chat session / message response
   - Community post detail response
   - Version Merge response
5. 保留展示层手写类型：
   - Billboard 动态中文记录字段
   - ECharts 组件内部展示结构
   - UI-only view model

验收标准：

- `npm run generate-types` 可运行或明确记录阻塞原因。
- `npm run build` 通过。
- 至少 AI Insights / Chat / Community / Version Merge 的 schema 来源有清晰台账。
- 不因类型刷新改动后端响应结构。

### Milestone 3：真实浏览器 Smoke 基线

**目标**：把 Phase 5 的关键页面从“测试/构建通过”推进到“真实浏览器可交互验证有记录”。

覆盖页面：

- `/ai-insights`
- `/music/tracks/:id`
- `/account`
- `/settings`
- `/community`

执行内容：

1. 启动后端与前端开发服务器。
2. 用浏览器或 Playwright smoke 检查桌面与移动端视口。
3. 每个页面至少检查：
   - 首屏无空白。
   - lazy fallback 不永久停留。
   - 无明显横向溢出。
   - 核心 tab 可切换。
   - 关键 GET 请求不重复风暴。
4. TrackDetail 重点检查：
   - 默认 stats tab 不请求 lyrics。
   - 切到 lyrics tab 后请求 `/lyrics/:trackId`。
   - 再次切回 lyrics tab 使用 Query 缓存，不重复打同一请求。
5. AI Insights 重点检查：
   - 日期选择器不造成移动端溢出。
   - chat session 切换不丢上下文。
   - LLM 未配置时显示明确降级状态。

验收标准：

- 记录桌面与移动端 smoke 结果。
- 若发现 UI 溢出或请求异常，修复后跑 `npm test` 与 `npm run build`。
- smoke 不作为每次提交硬门槛，但作为 Phase 5.5 结束验收材料。

### Milestone 4：后端 AI / Community 大模块按触碰拆分

**目标**：把当前偏大的后端模块纳入治理台账，但避免为了行数强行拆分稳定业务。

当前观察：

- `ai_insights_service.py` 约 1000 行。
- Community feed 生成模块中 `feed_ranking.py`、`feed_generator.py`、`feed_records.py` 偏大。
- `release_cycle_service.py`、`account_service.py` 仍偏大，但已不作为 Phase 5.5 主动硬拆范围。

执行原则：

1. 只有触碰相关功能或修 bug 时才拆。
2. 优先提取纯函数：
   - prompt 构建
   - 数据聚合
   - intent parse
   - cache key / cache read-write
   - post factory / ranking helper
3. 拆分后保留 facade / public import 兼容。
4. 每次拆分补 unit test 或扩展现有测试。

验收标准：

- 不改变 AI Insights / Community API 响应结构。
- 不改变现有 feed/post 生成口径。
- `pytest -m unit -q` 与相关 contract/integration 测试通过。
- 文档只记录已触碰拆分，不把未拆模块标成完成。

### Milestone 5：Phase 5.5 文档与 CI 台账收口

**目标**：把 Phase 5.5 的性能、类型、smoke、持续治理结果沉淀回长期文档。

执行内容：

1. 更新本台账：
   - bundle 基线
   - OpenAPI 类型生成结果
   - smoke 页面结果
   - 后端大模块是否触碰拆分
2. 必要时同步：
   - `README.md`
   - `AGENTS.md`
   - `CLAUDE.md`
3. 保持 Phase 5 最低验证矩阵不变：
   ```bash
   sh scripts/phase5_check.sh
   ```
4. 若新增 smoke 脚本或 bundle 台账脚本，再决定是否纳入 CI；默认不把慢 smoke 纳入每次 PR 硬门槛。

验收标准：

- Phase 5.5 完成项和未完成项在台账中清楚分开。
- 文档不夸大未执行的拆分或性能优化。
- 本地最低验证矩阵仍全绿。

### 建议执行顺序

1. Bundle 与 vendor chunk 归因，先建立可比较台账。
2. OpenAPI smoke 与 `npm run generate-types`，确认类型生成链路。
3. 真实浏览器 smoke，覆盖 AI Insights / TrackDetail / Account / Settings / Community。
4. 根据 smoke 和实际 bug，按触碰拆分 AI/community 后端纯函数。
5. 更新 README、AGENTS、CLAUDE 与本台账，跑 `sh scripts/phase5_check.sh` 做最终收口。

### Non-goals

- 不新增 Last.fm、Apple Music、网易云等新数据源。
- 不重做 AI Insights 产品逻辑。
- 不强制全量替换所有手写前端类型。
- 不把 Playwright smoke 变成每次提交硬门槛。
- 不把 Streamlit 重新纳入新功能开发。

## 仍需持续治理

| 优先级 | 方向 | 后续标准 |
|---|---|---|
| 低 | 后端大模块按触碰拆分 | `ai_insights_service.py` 1007 行、community feed 生成模块（`feed_ranking.py` 614 行等）后续只随功能触碰提取 |
| 低 | 长列表性能 | Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 已有分页/分段基线；后续核查 |
| 低 | Streamlit 物理归档 | 当前保持冻结维护；未来可迁入 `legacy/streamlit_app/` |
| 低 | OpenAPI 类型生成 | schema 稳定后可运行 `npm run generate-types` 刷新前端类型 |

## Phase 5 执行结果（2026-06-12）

Phase 5.4-A 至 5.4-H 全部完成。以下为各阶段摘要：

1. **Phase 5.4-A：新增页面架构护栏补齐** ✓ — `phase5-architecture.test.ts` 从 17 扩展到 105+ 测试
2. **Phase 5.4-B：TrackDetail route container 化** ✓ — 574→5 行，拆为 Experience + 2 Section
3. **Phase 5.4-C：Account Habits 下沉 feature** ✓ — 933 行删除，9 文件拆入 `features/account/habits/`
4. **Phase 5.4-D：AI Insights 产品化收口** ✓ — Experience / ChatInterface 拆分 + 11 端点 response_model + 7 新测试
5. **Phase 5.4-E：API 契约硬化** ✓ — Community post + Version Merge 全部 13 端点补 response_model
6. **Phase 5.4-F：Bundle 与 chunk 治理** ✓ — 懒加载拆分：Settings -88%、Records -69%、Account -34%
7. **Phase 5.4-G：文档与 CI 台账同步** ✓ — AGENTS/CLAUDE/台账 全部刷新至最新状态
8. **Phase 5.4-H：TrackDetail 歌词 Query 漏网修复** ✓ — 歌词读取从手动 fetchLyrics 改为 useQuery（queryKeys.music.trackLyrics），架构护栏补裸 GET 漏网断言

## chart_compute 拆分收口结果

### 当前职责边界

`chart_compute.py` 当前保留 227 行，主要承担三类 facade 职责：

- 兼容入口：`_compute_billboard_data_cached()` 与 `compute_billboard_data()` 负责旧 `/api/billboard/data` 聚合响应，不改变公开结构
- 兼容 re-export：继续从 `chart_ranking.py`、`chart_staged_api.py` 暴露旧调用方依赖的导入路径
- cache registration：继续注册 full-data 与 staged cache 函数，维持 Cache Manager 失效路径兼容

### 执行结果

1. **Phase 5.3-I：拆 staged cache orchestration（已完成）**
   - `backend/domains/billboard/chart_staged_cache.py` 已创建
   - `_load_and_rank()` 与四个 `_compute_*_cached()` 函数已迁入
   - `chart_compute.py` 保留兼容 import，并降至 319 行

2. **Phase 5.3-J：拆 staged public wrappers（已完成）**
   - `backend/domains/billboard/chart_staged_api.py` 已创建
   - `compute_weekly_data()`、`compute_power_scores_staged()`、`compute_summaries_staged()`、`compute_records_staged()` 已迁入
   - 保持既有 import 兼容与 cache registration
   - `chart_compute.py` 降至 227 行

3. **Phase 5.3-K：收口 compatibility facade（已完成）**
   - `chart_compute.py` 只保留旧聚合入口、兼容 re-export、cache registration
   - 架构护栏已覆盖 ranking/power/summary/staged cache/staged API 逻辑回流
   - `chart_compute.py` 成为 227 行稳定 facade

### 验收标准

- 不改变 `/api/billboard/data` 响应结构和 records/chart 统计口径 ✓
- `backend/tests/unit/test_phase5_architecture.py` 增加 chart staged 拆分护栏 ✓
- Billboard contract 测试继续通过 ✓
- `sh scripts/phase5_check.sh` 全部通过 ✓

## 2026-06-18 Album Project Playback Stats

本轮把非 L1 专辑统计从 release/source album 行聚合收口到 album project 语义：

- 新增 `album_projects`、`album_project_albums`、`album_project_tracks`，并通过 migration 16 持久化；新增 `agg_weekly_track_sources` 和 migration 17，保证 Billboard album raw/pre-agg 在项目口径下一致。
- `backend/domains/playback/album_projects.py` 负责 project bootstrap、canonical song ownership、source breakdown、Billboard release-date eligibility 和 inferred project rebuild。
- `/analysis/charts?entity=album`、leaderboard album rows、Billboard album chart 均改为 L2/L3 album project track membership；source album attribution 只作为解释性 breakdown。
- Album detail API 返回 `album_project` payload，前端 `AlbumProjectSection` 展示项目播放、发行日、项目曲目和来源拆分。
- Version Merge 设置页新增 album project rebuild 与 collaboration track-group candidate 查询；候选检测只读，不自动改变统计。

已执行的聚焦验证：

```bash
source .venv/bin/activate && python backend/tests/fixtures/build_seed_db.py
source .venv/bin/activate && pytest backend/tests/unit/test_album_project_resolver.py -v
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_billboard_counting_consistency.py -q
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_merge_level_aggregation.py -q
source .venv/bin/activate && pytest -m unit -q
source .venv/bin/activate && pytest -m contract -q
source .venv/bin/activate && ruff check backend/
cd frontend && npm test -- --run phase5-architecture
cd frontend && npm test
cd frontend && npm run build
```

## 2026-06-19 Billboard And Detail Performance Closeout

本轮排查并修复 Billboard、歌曲/专辑/艺人详情页首次加载长时间转圈的问题。根因不是前端页面失效，而是后端在默认 `dynamic_threshold=True` 口径下没有命中旧预聚合、并且多个分段接口冷启动时重复计算同一份 Billboard 基础排名；专辑详情还存在逐行 SQLite 查询 source album bucket 的热点。

已完成收口：

- 当前本地 DB 的 Billboard 预聚合已按 `dynamic_threshold=True` 重建，`agg_config.param_hash` 与 API 默认过滤口径一致。
- `_load_and_rank()` 拆出共享 `_load_and_rank_cached`，配合 `singleflight()` 和 Cache Manager，避免 weekly / power-scores / summaries / all-time 冷启动重复计算。
- `_add_running_metrics()` 从逐组 Python loop 改为 pandas 向量化。
- `load_plays()` / `load_plays_for_artists()` 的底层 LRU cache miss 加 `singleflight()`，避免详情页并发首次打开时重复扫播放表。
- `core/warmup.py` 改为当前默认过滤口径（`dynamic_threshold=True` / `max_merge_gap_minutes=None`），并预热 artist fan-out 播放表。
- Album detail source breakdown 改为批量读取 album metadata 后映射 bucket，避免对 4.7 万行逐行查 SQLite。

实测验证：

```text
FastAPI TestClient + warmup:
- /api/billboard/weekly: 0.439s
- /api/billboard/all-time: 1.518s
- /api/billboard/track/1503: 0.020s
- /api/billboard/album/GUTS?artist_name=Olivia Rodrigo: 0.857s
- /api/billboard/artist/Olivia Rodrigo: 0.209s
- /api/music/tracks/1503/stats: 0.938s
- /api/music/albums/GUTS/stats?artist=Olivia Rodrigo: 0.799s
- /api/music/artists/Olivia Rodrigo/stats: 0.739s

真实 8000 端口 smoke:
- /api/health: 0.005s
- /api/billboard/weekly: 0.467s
- /api/billboard/album/GUTS: 1.141s

验证命令:
- .venv/bin/ruff check backend/core/db.py backend/core/warmup.py backend/domains/billboard/details.py backend/domains/billboard/chart_staged_cache.py backend/domains/billboard/chart_compute.py backend/domains/billboard/chart_ranking.py backend/domains/playback/album_projects.py backend/tests/unit/test_warmup.py backend/tests/unit/test_billboard_running_metrics.py
- .venv/bin/python -m pytest backend/tests/unit/test_warmup.py backend/tests/unit/test_billboard_running_metrics.py backend/tests/unit/test_album_project_resolver.py backend/tests/contract/test_billboard_counting_consistency.py backend/tests/contract/test_album_project_rules.py -q
- cd frontend && npm run build
```

## 验证矩阵

Phase 5 最低验证命令：

```bash
sh scripts/phase5_check.sh
```

等价手动命令：

```bash
source .venv/bin/activate
pytest -m unit -q
pytest -m contract -q
ruff check backend/
cd frontend && npm test && npm run build
```

阶段性性能对比：

```bash
source .venv/bin/activate
python scripts/benchmark_api.py
```

`benchmark_api.py` 用于冷/热响应与 gzip 体积对比，不作为每次提交硬门槛。

## 开发约束

- 新增 GET hook 必须使用 TanStack Query 与 `queryKeys`
- 禁止新增模块级数据缓存；只允许保存 UI 状态，如 tab、排序、页码
- 路由页面应保持 container 化；Billboard records/all-time/number-ones 业务组件分别放在 `frontend/src/features/billboard/{records,all-time,number-ones}/`，音乐详情业务组件放在 `frontend/src/features/music/details/`
- 新增第三方 HTTP 调用必须经 `providers/` 或 `infrastructure/http/`
- 业务 service 不得直接新建 `urllib.request.Request` 或调用 `urlopen`
- Spotify API/OAuth/token 请求不得在 `backend/core/` 直接新建 `urllib.request.Request` 或调用 `urlopen`
- 写接口、导入、设置修改仍需 `require_auth`
- 旧 `/api/billboard/data` 保持兼容，不删除
- Streamlit `app/` 只修严重 bug，不承接新功能
