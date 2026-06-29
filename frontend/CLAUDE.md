# Frontend Architecture

> 项目级上下文（Phase 5 基线、架构模式、提交规范）见根目录 `AGENTS.md`。

React 19 + TypeScript 6.0 + Vite 8 + Tailwind CSS v4 + shadcn/ui (base-nova) + React Router v7 + TanStack React Query + ECharts 6。

路径别名 `@/` → `src/`。

## 目录结构

```
src/
├── api/              ← API 客户端 + TanStack QueryClient + Query Key 工厂 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件
│   ├── analysis/records/  ← PlaybackRecordsExperience + 6 Section + Primitives + Data
│   ├── billboard/
│   │   ├── number-ones/   ← NumberOnesExperience + 3 Section（tracks/albums/artists）+ Primitives + Data
│   │   ├── records/       ← RecordsSections + 6 Section + Primitives + Data
│   │   └── all-time/      ← AllTimeTable + Data
│   ├── community/         ← CommunityExperience/Account + FeedToggle + TimeFilter + PostCard + PostMetrics + Timeline + Sidebar + PostDetailExperience + MobileSidebarDrawer + Skeleton + Data
│   ├── ai-insights/        ← AiInsightsExperience + ReportsPanel + ReportCard + ChatInterface + ChatComposer + ChatSessionList + ChatSessionDrawer + SuggestedQuestions + Primitives + Data
│   ├── ai-tasks/           ← AITaskProgress + AIEvidenceCards + AIToolTrace + AIResultShell，共享 AI task 进度/证据/工具轨迹 UI
│   ├── music/details/     ← Artist/Album Experience + Header/Tabs + Skeletons + Overview/Tracks/Albums/Career/AlbumEra 子 sections + ReleaseCycle sections + Primitives
│   ├── settings/components/  ← 7 配置 Section 组件
│   └── account/collection/   ← 收藏分析组件
├── components/
│   ├── ui/           ← shadcn/ui 组件（可随意修改）
│   ├── charts/       ← LazyEChart 按需 ECharts 封装 + 纯 DOM 图表
│   ├── layout/       ← AppLayout, Masthead, ThemeToggle
│   └── shared/       ← GlassCard, KpiCard, WeekSelector, CoverCell, FormattedText 等
├── pages/            ← 路由级页面容器（React.lazy 分包，纯组合 feature 组件）
├── hooks/            ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount, useCommunity, useAiInsights, useAiTasks
├── lib/              ← cn(), chinese, insights, theme, personality-themes, genre-regions
├── tests/            ← 含 phase5-architecture.test.ts 架构护栏测试
└── types/            ← 手写 TypeScript 展示类型
```

## 路由结构

```
/                          → DashboardPage
/analysis/stats            → AnalysisLayout > StatsTab
/analysis/charts           → AnalysisLayout > ChartsTab
/analysis/records          → AnalysisLayout > RecordsTab
/yearly-review             → YearlyReviewPage
/billboard                 → BillboardPage
/billboard/number-ones     → NumberOnesPage (5 行 route container)
/billboard/all-time        → AllTimeChartsPage (192 行 route container)
/billboard/records         → RecordsPage (115 行 route container)
/community                 → CommunityPage (5 行 route container)
/community/post/:postId      → PostDetailPage (5 行 route container)
/community/account/:handle → CommunityAccountPage (5 行 route container)
/ai-insights               → AiInsightsPage (4 行 route container)
/music/tracks/:trackId     → TrackDetailPage
/music/albums/:albumName   → AlbumDetailPage (5 行 route wrapper)
/music/artists/:artistName → ArtistDetailPage (5 行 route wrapper)
/settings                  → SettingsPage
/account                   → AccountCenterPage
```

旧 `/billboard/track|album|artist/*` 仅做兼容跳转到 `/music/*`。

播放分析子页面通过 URL search params 自动保留 `period`/`period_value`/`start`/`end` 参数。

播放分析二级 tab 顺序固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 账号中心”。`/yearly-review` 与 `/account` 仍是独立路由，但在导航语义上归属播放分析，避免在 Masthead 下再增加下拉或重复入口。

## 数据获取 (TanStack React Query)

统一配置：staleTime 5 分钟 / gcTime 30 分钟 / retry 2 次 / refetchOnWindowFocus false。

Query Key 工厂在 `@/api/query-keys.ts`，按领域 namespace：dashboard / billboard / analysis / settings / account / yearlyReview / music / library / versionMerge / community / aiInsights / aiTasks。

AppLayout 首屏渲染后延迟预取常用数据。年度总结使用序列化预取（`for...of` + `await`）避免并发请求触发 SQLite 锁竞争。

Community 列表、账号页、趋势侧栏和帖子详情必须通过 `useCommunityChartParams()` 带入当前榜单设置口径，并把这些参数放入 community query keys，避免不同 Top N、周起点、动态阈值、合并级别或精选集设置共用旧缓存。

**Phase 5 强制约束**：
- 新增 GET hook 必须使用 `queryKeys` + `useQuery`
- **禁止模块级 `new Map()` 缓存 API 响应**（enrichment/release-cycle 等数据必须走 Query Client）
- 模块级变量只允许保存 UI 状态（tab/排序/页码），如 `let cachedTab`、`let cachedSortKey`

## Phase 5 架构模式

页面容器（`pages/`）只做路由入口，业务逻辑和渲染细节在 `features/` 中：

| 层级 | 位置 | 行数上限 | 禁含 |
|------|------|---------|------|
| Route Container | `pages/` | ≤450 | `<table>`, `function KpiCard`, `function No1BarChart` |
| Experience | `features/*/XXXExperience.tsx` | ≤450 | shared primitives（KpiCard, KpiStrip, PlaysCell） |
| Section | `features/*/XXXSection.tsx` | ≤300 | — |
| Primitives | `features/*/XXXPrimitives.tsx` | ≤350 | — |
| Data | `features/*/xxxData.ts` | — | JSX |

架构护栏测试（`src/tests/phase5-architecture.test.ts`）使用 `?raw` import + 负面断言强制执行上述约束。

## UI 规范

**主题**：「编辑风 × 液态玻璃」— Playfair Display 衬线标题 + Inter 无衬线正文 + 毛玻璃卡片 + 日/夜双皮肤。

- CSS 变量在 `src/index.css`：`@theme inline`（结构变量）、`:root`（浅色）、`.dark`（深色）
- `useTheme()` hook：localStorage 持久化 + 系统偏好回退
- GlassCard 是所有卡片的默认容器
- 移动端不得产生页面级横向滚动；全局 chrome（AppLayout/Masthead）和 loading skeleton 必须用 `min-w-0`、`max-w-full`、`basis-full` 或 `overflow-x-clip` 约束，宽表只允许在局部容器内横向滚动
- 账号页、收藏页和长列表里的封面图必须使用 `loading="lazy"` / `decoding="async"`；滚动预览类组件必须限制首屏示例数量
- 详细风格指南见 `UI_STYLE_GUIDE.md`

## 图表

- ECharts 统一通过 `components/charts/LazyEChart.tsx` 动态加载 `echarts-for-react/esm/core`
- 新增 ECharts 图表必须复用 `LazyEChart`，禁止直接 `import('echarts-for-react')` 默认入口
- 当前只注册 bar/line/pie/heatmap、tooltip、legend、dataZoom、visualMap、markLine、markPoint、markArea 和 CanvasRenderer；新增系列或组件时先扩展 `LazyEChart`
- `RankTrendChart`：排名趋势图（断档填充、全貌/细节缩放、dataZoom 滑块、峰值 Pin 标记、连续冠周 markArea 色带）
- `ReleaseTimelineChart`：发行周期排名趋势
- `ListeningClock`：极坐标时针式 24 小时听歌分布

## 关键约束

- 外部文本（LLM、Wikipedia、翻译）必须经 `react-markdown` + `rehype-sanitize` 渲染，禁止 `dangerouslySetInnerHTML`；AI 报告/问答正文统一复用 `features/ai-insights/AiMarkdown.tsx`，保留 GFM 表格但必须包裹横向滚动容器
- 后端 SQLite 风格时间戳（`YYYY-MM-DD HH:mm:ss`）默认视为 UTC；对话历史等相对时间显示必须通过 `lib/datetime.ts` 的 `formatRelativeTimeZh()`，避免本地时区偏移
- LLM API Key 永不对前端返回明文，通过 `POST /apply` 端点让服务端直接写入
- AI 报告页面必须 cache-first，不因打开页面或切换报告类型自动调用 LLM；无缓存时显示明确的手动生成动作
- AI 问答和音乐详情 enrichment 的长耗时流程必须通过 `features/ai-tasks` 展示 task progress；问答完成后必须保留 assistant message `meta.evidence_cards` 并展示 evidence cards 与 tool trace
- AI comparison evidence cards 必须在 390px 移动端保持单列可读，宽屏可用双列矩阵；长专辑名、维度胜者和限制说明不得造成横向滚动或卡片内文字溢出
- 图表组件不能 SSR，必须 lazy load
- 新增页面务必参考 `UI_STYLE_GUIDE.md`
- 简繁转换用 `displayName()` 统一入口，OpenCC 按需动态 import `opencc-js/t2cn` 或 `opencc-js/cn2t`，禁止回退到默认 `opencc-js` full 包，也禁止模块初始化时根据已保存偏好 eager-load 大字典
- **新增 GET hook → TanStack Query + `queryKeys`**；禁止模块级 `new Map()` 数据缓存
- **页面容器只做路由入口**，实现细节在 `features/`

## 测试

vitest + React Testing Library (jsdom)，`npm test` 运行。含 `phase5-architecture.test.ts` 架构护栏测试。

Web Vitals lab 采样使用根目录脚本：

```bash
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --web-vitals --resource-snapshot --resource-max-total-rss-mb 1200 --resource-max-total-cpu-percent 200 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000
.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json
.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:5173 --viewport both --include-detail-routes
node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --include-detail-routes
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_long_list_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173 --include-detail-routes
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --include-detail-routes
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000
```

`frontend_route_smoke.mjs` 默认等待 5 秒，并对 19 个默认主路由（含 `/analysis` 与 5 个分析重定向别名）检查业务内容 marker；零警告验收用 `--fail-on-console-warning`，全栈聚合入口默认传递该门禁并启用 `--include-detail-routes`，从本地 API 动态追加歌曲/专辑/艺人/社区帖子/社区账号 5 个详情路由；自定义临时路由可用 `--disable-route-markers` 关闭 marker 检查。
`fullstack_verification_check.sh` 是非破坏性全栈聚合入口，会串起 backend full、pre-commit、Phase 5、OpenAPI operation audit、OpenAPI parameter boundary audit、API smoke/boundary、benchmark 和前端 smoke；需先启动后端 8000 与前端 5173，生产 preview 可用 `--preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000`；Web Vitals 可用 `--web-vitals-max-lcp-ms`、`--web-vitals-max-cls`、`--web-vitals-max-tbt-ms`、`--web-vitals-max-resource-count`、`--web-vitals-max-encoded-resource-kb` 进入同一聚合门禁，`--resource-snapshot` 会同步采集后端/前端/preview 监听进程树 CPU/RSS，并可用 `--resource-max-total-rss-mb`、`--resource-max-total-cpu-percent` 设置资源预算。脚本会在激活 `.venv` 前自动检测可导入 `playwright.sync_api` 的 Python，必要时也可显式设置 `PYTHON_PLAYWRIGHT`。
`frontend_interaction_smoke.mjs` 覆盖分析页 tab、Billboard 子路由/前进后退、AI Insights 报告/问答 tab（含未配置 LLM 空状态）、Settings 过滤/显示偏好控件与主题切换；生产 preview 用 `--api-base-url http://127.0.0.1:8000` 将 `/api` 与 `/covers` 请求转发到后端。dev server 和生产 preview 都应保持 0 console error、0 page error、0 横向溢出。
`frontend_chart_interaction_smoke.mjs` 覆盖 ECharts tooltip hover、legend toggle 与 dataZoom drag，默认从真实 `/api/billboard/all-time` 响应动态选择长榜艺人；生产 preview 用 `--api-base-url http://127.0.0.1:8000` 分离静态页面与后端 API。dev server 和生产 preview 都应保持 0 console error/warning、0 page error、0 横向溢出。
`frontend_control_inventory_smoke.mjs` 覆盖 13 个默认路由 + 5 个动态详情路由 × 桌面/390px 移动端，检查可见交互控件缺少可访问名称、嵌套交互控件、disabled 仍可 tab、输入控件无标签和重复 id；`--include-detail-routes` 若解析不到 5 个详情样本会失败，生产 preview 用 `--api-base-url http://127.0.0.1:8000` 转发 `/api` 与 `/covers`。
`frontend_long_list_smoke.mjs` 覆盖 Records mini-rank、Billboard All-Time、Community Feed infinite load、RecentPlays、SavedTracks、PersonalRankTable 6 个长列表分页/分段渲染场景，要求点击或滚动后可见窗口变化，并保持 0 console error/warning、0 page error、0 横向溢出；生产 preview 用 `--api-base-url http://127.0.0.1:8000` 将 `/api` 与 `/covers` 请求转发到后端。
`frontend_cross_browser_smoke.mjs` 使用 Python Playwright API 跑 Chromium、Firefox、WebKit（Safari-family）三引擎；`--include-detail-routes` 会从本地 API 动态追加歌曲/专辑/艺人/社区帖子/社区账号 5 个详情路由；生产 preview 用 `--api-base-url http://127.0.0.1:8000` 通过 Playwright request fetch/fulfill 代理 `/api` 与 `/covers`，避免 4173 非 CORS 白名单 origin 削弱证据。若默认 `python` 不能 `import playwright.sync_api`，用 `PYTHON_PLAYWRIGHT=/path/to/python` 或 `--python` 指定。
`frontend_web_vitals_probe.mjs` 采集 LCP/CLS/合成 FID/TBT lab 指标，并记录 resource count 与 encoded resource KB；生产 preview 用 `--api-base-url http://127.0.0.1:8000` 将 `/api` 与 `/covers` 请求转发到后端，避免只测到静态 preview 壳；可选 `--max-lcp-ms`、`--max-cls`、`--max-tbt-ms`、`--max-resource-count`、`--max-encoded-resource-kb` 会在任一路由/视口超预算时保留报告并以退出码 1 失败。
