# Phase 5：产品化收口与可持续迭代基线

> 状态台账日期：2026-06-08  
> 最近更新：Phase 5.2-J 音乐详情页 Album era 子 section 拆分
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
| Records 表格分页基线 | 已完成 | `MiniRankTable` 作为 records 专用分页表格组件保留 10 行分页，并通过架构测试防止页面重新膨胀 |
| AllTimeCharts 前端拆分 | 已完成 | `AllTimeChartsPage.tsx` 压缩为 192 行 route container；all-time 行合并/筛选/排序与表格渲染拆入 `frontend/src/features/billboard/all-time/` |
| AllTimeCharts 分页基线 | 已完成 | `AllTimeTable` 保留 50 行分页、列宽 UI 状态与排序交互；页面层不再直接渲染 `<table>` |
| NumberOnes 前端拆分 | 已完成 | `NumberOnesPage.tsx` 保持 5 行 route wrapper；`NumberOnesExperience.tsx` 压缩为 121 行 feature container；计算、primitives、tracks/albums/artists sections 拆入 `frontend/src/features/billboard/number-ones/` |
| 音乐详情页 route container 化 | 已完成 | `ArtistDetailPage.tsx`、`AlbumDetailPage.tsx` 均压缩为 5 行 route wrapper；完整体验迁入 `frontend/src/features/music/details/` |
| 音乐详情页共享 primitives | 已完成 | `KpiCard`、`KpiStrip`、`PlaysCell` 与日期/数字格式化抽入 `MusicDetailPrimitives.tsx`，减少 Artist/Album 详情页重复实现 |
| 音乐详情页 feature 二次拆分 | 进行中 | `AlbumStoryCard`、`InfoRow`、`MiniStat`、`MatrixCell` 抽入 `AlbumDetailPrimitives.tsx`；Artist 发行周期列表抽入 `ArtistReleaseCycleSection.tsx`；Artist/Album hero、tabs 与 loading skeleton 抽入 `MusicDetailHeader.tsx`、`MusicDetailSkeletons.tsx`；榜单概览 KPI/趋势/周榜历史抽入 `MusicChartOverviewSection.tsx`；单曲/专辑表格与 Artist 生涯抽入 `MusicTracksSection.tsx`、`ArtistAlbumsSection.tsx`、`ArtistCareerSection.tsx`；Album 发行档案编排层抽入 `AlbumEraSection.tsx`，并继续拆出 overview/timeline/composition/matrix/overflow/enrichment/personal-story 子 section |
| Phase 5 架构红线测试 | 已完成 | 新增后端 service/core urllib 静态测试与前端详情页模块级 API Map 缓存、hero/tabs、overview、tracks/albums/album era orchestration 静态测试 |
| Phase 5 本地验证脚本 | 已完成 | `scripts/phase5_check.sh` 串联后端 unit/contract、ruff、前端 test/build |

## 仍需持续治理

| 优先级 | 方向 | 后续标准 |
|---|---|---|
| 中 | 音乐详情 feature 细拆 | `ArtistDetailExperience.tsx` 约 317 行、`AlbumDetailExperience.tsx` 约 144 行、`AlbumEraSection.tsx` 约 56 行；Album 发行档案子 section 均小于 100 行，后续可继续把 Artist 生涯细节压到 300 行以内 |
| 中 | 后端 Billboard 二次拆分 | `records.py`、`chart_compute.py` 后续按 record family、weekly compute、power score、all-time aggregation 继续拆子域 |
| 中 | 长列表性能 | 超过 500 行 DOM 的表格必须使用服务端分页或虚拟化；默认不一次性渲染全量 |
| 中 | API 契约硬化 | 高流量端点补 `response_model`，修改 schema 后运行 OpenAPI 类型生成 |
| 低 | Streamlit 物理归档 | 当前保持冻结维护；未来可迁入 `legacy/streamlit_app/` |

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
