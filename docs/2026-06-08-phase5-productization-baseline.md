# Phase 5：产品化收口与可持续迭代基线

> 状态台账日期：2026-06-08  
> 最近更新：Phase 5.3 Billboard chart compute 剩余拆分收口
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
| Query key 体系扩展 | 已完成 | 覆盖 dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge |
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

## 文档收口审计：2026-06-09

| 检查项 | 结果 | 说明 |
|---|---|---|
| Phase 5 最低验证矩阵 | 通过 | `sh scripts/phase5_check.sh`：unit 100 passed、contract 14 passed、ruff passed、frontend 40 tests passed、build success |
| Billboard records facade | 已收口 | `backend/domains/billboard/records.py` 当前 88 行；records 已拆为 output + 8 个 record family 子模块 |
| Billboard chart compute | 已收口 | `backend/domains/billboard/chart_compute.py` 当前 227 行；ranking、power score、summaries、staged cache、staged API 均已拆出 |
| 文档一致性 | 已修正 | 台账、README、AGENTS、CLAUDE 已统一使用当前行数：`records.py` 88 行、`chart_compute.py` 227 行、`chart_staged_api.py` 114 行、`chart_staged_cache.py` 336 行 ✓ |

## 仍需持续治理

| 优先级 | 方向 | 后续标准 |
|---|---|---|
| 中 | 音乐详情 feature 细拆 | `ArtistDetailExperience.tsx` 约 163 行、`AlbumDetailExperience.tsx` 约 144 行、`AlbumEraSection.tsx` 约 56 行；Artist/Album 体验层均已低于 300 行 ✓ |
| 中 | 后端 Billboard 二次拆分 | `records.py` 已全量拆为 8 个 record family 子模块，facade 仅 88 行 ✓；`chart_compute.py` 已收口为 227 行 facade ✓；后续只在触碰功能时继续细拆其他 Billboard 大模块 |
| 低 | 长列表性能 | Records、AllTimeCharts、RecentPlays、SavedTracks、PersonalRankTable 已有分页基线；后续新增超过 500 行 DOM 的表格必须使用服务端分页、分页组件或虚拟化 |
| 中 | API 契约硬化 | 高流量端点补 `response_model`，修改 schema 后运行 OpenAPI 类型生成 |
| 低 | Streamlit 物理归档 | 当前保持冻结维护；未来可迁入 `legacy/streamlit_app/` |

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
