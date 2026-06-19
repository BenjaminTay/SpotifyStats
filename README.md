# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**架构**：FastAPI 后端 + React 前端。Streamlit 原有应用已冻结维护。

**Phase 5 产品化收口**：前端 GET 统一 TanStack Query（11 命名空间 queryKeys）、Provider 错误分层、业务 service urllib 清零、模块级 API Map 缓存清除；Billboard records 88 行 facade + chart_compute 211 行 facade；Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表分页基线。Phase 5.4 八阶段（A-H）全系列完成（2026-06-12）：架构护栏 105+ 测试、TrackDetail 574→5 行、HabitsTab 933 行→9 文件 feature、AI Insights 拆分、24 端点 response_model 硬化、Bundle 懒加载治理（Settings -88%/Records -69%/Account -34%）、TrackDetail 歌词 Query 漏网修复。播放统计规则引擎（Phase C+D，2026-06-18 贯穿修复）：动态阈值、Session 边界检测（`max_gap_minutes` + `boundary_column`）、Track Groups 三级合并（L1/L2/L3 recording/composition scope）、Album Projects 专辑项目统计、`merge_level` 查询参数、Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Release Cycle 统一传递 `dynamic_threshold` 与 `max_merge_gap_minutes`，设置页 L1/L2/L3 合并严格度选择器。2026-06-19 补齐全栈验证与性能收口：默认预热改用当前动态阈值口径，Billboard 基础排名共享缓存，Power Score、summaries 与播放合并路径向量化，Dashboard full 单请求复用播放 DataFrame，AI Insights 报告/问答透传播放过滤口径并按过滤指纹分流缓存，Behavior 全量事件分析只暴露/请求 `music_only`，专辑详情来源拆分批量映射，390px 移动端横向滚动归零，pre-commit 收敛到 backend 治理范围，OpenCC/ECharts 大依赖拆为按需加载子包且保存偏好不再模块级预取字典，账号页资源加载收敛并补充 dev/prod-preview Web Vitals lab 探针与 LCP/CLS/TBT 预算门禁，新增 96 请求可复跑 API smoke 探针、19 个非破坏性 API 边界 probe、Provider 异常响应分层 contract 护栏、Billboard enrichment 降级 contract 护栏、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON response_model contract 护栏（OpenAPI response_model 缺口 41→1，唯一剩余为 Spotify callback 显式 RedirectResponse，账号中心/画像、Timeline/Listening/Artist/Wrapped、Release Cycle compare 与 Lyrics JSON 发布稳定 schema）、8 端点 API 性能 benchmark 慢端点门禁、38 组合 route smoke 探针（19 路由含分析重定向别名，默认 5s + 业务内容 marker）、5 场景前端交互 smoke 探针（新增 Settings 过滤/显示偏好控件覆盖）、3 场景 ECharts 图表交互 smoke 探针（dev/prod-preview 均覆盖）、6 场景长列表分页/分段渲染 smoke 探针（dev/prod-preview 均覆盖）、全栈非破坏性验收聚合脚本、GitHub Actions 与本地 Phase 5 矩阵 parity 护栏与 Chromium/Firefox/WebKit 跨浏览器 smoke 探针，OpenAPI GET 覆盖核算，Chat/Settings/LLM profile mutation、Spotify auth JSON 端点、AI Insights 生成端点、Import job 调度和 Spotify OAuth PKCE 本地闭环 contract 覆盖，并修复 Spotify 当前播放 token refresh、OAuth login 未配置 Client ID 500、Settings 越界配置、清翻译缓存缺表、Provider 异常泛化 500、封面回退查询 schema mismatch 500、Billboard enrichment Wiki lookup 普通异常 500、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON 相关端点缺少 response_model、AI Insights 报告缓存 readonly 写入 warning、会话列表嵌套按钮、周快捷项重复 key console error，以及音乐详情隐藏 tab 挂载图表导致的 ECharts 零尺寸 warning。详见 [`docs/2026-06-08-phase5-productization-baseline.md`](docs/2026-06-08-phase5-productization-baseline.md)、[`docs/2026-06-18-playback-stats-rules-latest.md`](docs/2026-06-18-playback-stats-rules-latest.md) 和 [`docs/2026-06-19-fullstack-verification-performance-report.md`](docs/2026-06-19-fullstack-verification-performance-report.md)。

## 功能

- **总览仪表盘** — KPI 卡片、月度趋势、平台分布、周热力图、动态数据洞察
- **播放分析** — stats.fm 风格统计：8 KPI + 日历趋势 + 听歌时钟 + 个人排行榜（歌曲/专辑/艺人 × 次数/时长）+ 自定义时间范围
- **专辑项目统计** — 标准版/豪华版、先行单曲和确认项目版本按合并级别计入同一 album project；专辑详情页提供原版、豪华版、单曲、精选集等来源拆分
- **年度回顾** — 自定义 Wrapped 总结（听歌人格识别 6 型、曲风五大洲全景、发现与回归、聆听深度金字塔、特殊时刻、年度对比）+ 官方 Wrapped 数据
- **Billboard 周榜** — 12 子 Tab：周榜、每周榜首、单曲/艺人/专辑历史、走势总榜 Power Score、总榜、榜单记录、对决、发行周期分析
- **音乐实体详情** — 歌曲/专辑/艺人全局页面，整合个人播放统计、Billboard 成绩、Genius 歌词、Wikipedia 百科
- **账号中心** — 收藏分析（生命周期、化学反应、品味迁徙、Flip Side）+ 搜索编年史、粉丝层级、播客、视频分析
- **AI 洞察** — 自然语言听歌周报/月报/年度叙事 + 自由问答，LLM 驱动数据解读
- **设置** — Spotify OAuth 连接管理、LLM 翻译配置（多提供商 + 档案管理）、数据过滤、版本合并、数据导入
- **Spotify Web API** — OAuth PKCE 授权，回填收藏日期、Top 排行、最近播放、播放列表、实时播放状态

## 快速开始

```bash
# 安装
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 启动后端（端口 8000）
uvicorn backend.main:app --reload --reload-dir backend

# 启动前端（端口 5173，自动代理 /api → 后端）
cd frontend && npm run dev

# Spotify OAuth 需要 HTTPS，开发环境用 ngrok
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

# 测试
pytest backend/tests/ -v          # 后端测试（unit/contract/integration）
pytest -m unit -q                 # 快速单元层
pytest -m contract -q             # seed DB 契约层
.venv/bin/pytest backend/tests/contract/test_spotify_auth_contract.py -q  # OAuth PKCE 本地闭环
.venv/bin/python scripts/api_smoke_probe.py  # 本地只读 API smoke（96 个 GET + OpenAPI GET 核算）
.venv/bin/python scripts/api_boundary_probe.py  # 非破坏性 API 边界 probe（19 个 GET）
.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500  # API 性能 benchmark
cd frontend && npm test           # 前端 vitest 单测 + 架构护栏测试

# 代码质量
ruff check backend/ && ruff format --check backend/
pre-commit run --all-files

# Phase 5 最低验证矩阵
sh scripts/phase5_check.sh
.venv/bin/python scripts/ci_baseline_parity.py  # GitHub Actions / 本地矩阵一致性护栏

# 全栈非破坏性验收矩阵（需后端 8000 + 前端 5173 已启动；可选 --preview-url/--web-vitals）
# 跨浏览器 smoke 会自动检测可 import playwright.sync_api 的 Python，也可显式设置 PYTHON_PLAYWRIGHT
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173

# 前端 route/interaction/cross-browser smoke + Web Vitals lab 采样（需后端 8000 + 前端 5173 已启动）
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100
```

首次启动自动导入 JSON 数据到 SQLite。浏览器打开 `http://localhost:5173` 使用 React 界面，`http://localhost:8000/docs` 查看 API 文档。

## 技术栈

**后端**：FastAPI · Pandas · SQLite (WAL) · Pydantic v2 · pytest · Ruff · Mypy

**前端**：React 19 · TypeScript 6.0 · Vite 8 · Tailwind CSS v4 · shadcn/ui · React Router v7 · TanStack React Query · ECharts 6 · Vitest

**基础设施**：AES-256-GCM 加密 · OAuth PKCE · 统一 Cache Manager (LRU+TTL) · 版本化 Migration · 后台 Job Queue · OpenAPI 自动生成类型 · Request ID 链路追踪 · Provider 错误分类 · 架构护栏测试 · GitHub Actions CI

## 项目结构

```
SpotifyStats/
├── backend/               # FastAPI 后端（api/ → services/ → domains/ → core/）
├── frontend/              # React 前端
│   └── src/
│       ├── features/      # Feature-first 业务组件（billboard/music/settings/account/ai-insights/community）
│       ├── pages/         # 路由级页面容器（React.lazy 分包）
│       ├── components/    # ui/charts/layout/shared
│       ├── hooks/         # useDashboard, useBillboard, useYearlyReview, useAiInsights...
│       └── api/           # QueryClient + queryKeys + OpenAPI 类型
├── app/                   # Streamlit 旧应用（冻结维护）
├── data/                  # SQLite 数据库 + JSON 源数据
├── docs/                  # 架构文档 + Phase 5 台账
├── scripts/               # 工具脚本（phase5_check.sh, fullstack_verification_check.sh, ci_baseline_parity.py, api_smoke_probe.py, api_boundary_probe.py, benchmark_api.py）
└── requirements.txt
```

## 详细文档

- 主项目提示词（多 Agent 协作）见 [`AGENTS.md`](AGENTS.md)
- Claude Code 速查卡见 [`CLAUDE.md`](CLAUDE.md)
- 后端架构细节见 [`backend/CLAUDE.md`](backend/CLAUDE.md)
- 前端架构细节见 [`frontend/CLAUDE.md`](frontend/CLAUDE.md)
- UI 风格指南见 [`frontend/UI_STYLE_GUIDE.md`](frontend/UI_STYLE_GUIDE.md)
- 数据目录说明见 [`data/README.md`](data/README.md)
- 架构优化文档见 [`docs/phase4-architecture/2026-05-30-architecture-optimize.md`](docs/phase4-architecture/2026-05-30-architecture-optimize.md)
- Phase 5 产品化收口台账见 [`docs/2026-06-08-phase5-productization-baseline.md`](docs/2026-06-08-phase5-productization-baseline.md)
- 播放统计规则定义与实现状态见 [`docs/2026-06-18-playback-stats-rules-latest.md`](docs/2026-06-18-playback-stats-rules-latest.md)
- 播放统计实现计划见 [`docs/2026-06-12-playback-stats-implementation-plan.md`](docs/2026-06-12-playback-stats-implementation-plan.md)
- 全栈验证与性能收口报告见 [`docs/2026-06-19-fullstack-verification-performance-report.md`](docs/2026-06-19-fullstack-verification-performance-report.md)

## License

MIT
