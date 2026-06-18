# Frontend Architecture

> 项目级上下文（Phase 5 基线、架构模式、提交规范）见根目录 `AGENTS.md`。

React 19 + TypeScript 6.0 + Vite 8 + Tailwind CSS v4 + shadcn/ui (base-nova) + React Router v7 + TanStack React Query + ECharts 6。

路径别名 `@/` → `src/`。

## 目录结构

```
src/
├── api/              ← API 客户端 + TanStack QueryClient + Query Key 工厂 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件
│   ├── billboard/
│   │   ├── number-ones/   ← NumberOnesExperience + 3 Section（tracks/albums/artists）+ Primitives + Data
│   │   ├── records/       ← RecordsSections + 6 Section + Primitives + Data
│   │   └── all-time/      ← AllTimeTable + Data
│   ├── community/         ← CommunityExperience/Account + FeedToggle + TimeFilter + PostCard + PostMetrics + Timeline + Sidebar + PostDetailExperience + MobileSidebarDrawer + Skeleton + Data
│   ├── ai-insights/        ← AiInsightsExperience + ReportCard + ChatInterface + ChatSessionList + ChatSessionDrawer + SuggestedQuestions + Primitives + Data
│   ├── music/details/     ← Artist/Album Experience + Header/Tabs + Skeletons + Overview/Tracks/Albums/Career/AlbumEra 子 sections + ReleaseCycle sections + Primitives
│   ├── settings/components/  ← 7 配置 Section 组件
│   └── account/collection/   ← 收藏分析组件
├── components/
│   ├── ui/           ← shadcn/ui 组件（可随意修改）
│   ├── charts/       ← LazyEChart 按需 ECharts 封装 + 纯 DOM 图表
│   ├── layout/       ← AppLayout, Masthead, ThemeToggle
│   └── shared/       ← GlassCard, KpiCard, WeekSelector, CoverCell, FormattedText 等
├── pages/            ← 路由级页面容器（React.lazy 分包，纯组合 feature 组件）
├── hooks/            ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount, useCommunity, useAiInsights
├── lib/              ← cn(), chinese, insights, theme, personality-themes, genre-regions
├── tests/            ← 含 phase5-architecture.test.ts 架构护栏测试
└── types/            ← 手写 TypeScript 展示类型
```

## 路由结构

```
/                          → DashboardPage
/analysis/stats            → AnalysisLayout > StatsTab
/analysis/charts           → AnalysisLayout > ChartsTab
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

## 数据获取 (TanStack React Query)

统一配置：staleTime 5 分钟 / gcTime 30 分钟 / retry 2 次 / refetchOnWindowFocus false。

Query Key 工厂在 `@/api/query-keys.ts`，按领域 namespace：dashboard / billboard / analysis / settings / account / yearlyReview / music / library / versionMerge / community / aiInsights。

AppLayout 首屏渲染后延迟预取常用数据。年度回顾使用序列化预取（`for...of` + `await`）避免并发请求触发 SQLite 锁竞争。

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

- 外部文本（LLM、Wikipedia、翻译）必须经 `react-markdown` + `rehype-sanitize` 渲染，禁止 `dangerouslySetInnerHTML`
- LLM API Key 永不对前端返回明文，通过 `POST /apply` 端点让服务端直接写入
- 图表组件不能 SSR，必须 lazy load
- 新增页面务必参考 `UI_STYLE_GUIDE.md`
- 简繁转换用 `displayName()` 统一入口，OpenCC 按需动态 import `opencc-js/t2cn` 或 `opencc-js/cn2t`，禁止回退到默认 `opencc-js` full 包
- **新增 GET hook → TanStack Query + `queryKeys`**；禁止模块级 `new Map()` 数据缓存
- **页面容器只做路由入口**，实现细节在 `features/`

## 测试

vitest + React Testing Library (jsdom)，`npm test` 运行。含 `phase5-architecture.test.ts` 架构护栏测试。

Web Vitals lab 采样使用根目录脚本：

```bash
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0
node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_cross_browser_smoke.mjs --base-url http://127.0.0.1:5173
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
```

`frontend_route_smoke.mjs` 默认等待 5 秒，并对 13 个核心路由检查业务内容 marker；自定义临时路由可用 `--disable-route-markers` 关闭 marker 检查。
`frontend_interaction_smoke.mjs` 覆盖分析页 tab、Billboard 子路由/前进后退、AI Insights 报告/问答 tab（含未配置 LLM 空状态）与主题切换，dev server 和生产 preview 都应保持 0 console error、0 page error、0 横向溢出。
`frontend_chart_interaction_smoke.mjs` 覆盖 ECharts tooltip hover、legend toggle 与 dataZoom drag，默认从真实 `/api/billboard/all-time` 响应动态选择长榜艺人；dev server 应保持 0 console error/warning、0 page error、0 横向溢出。
`frontend_cross_browser_smoke.mjs` 使用 Python Playwright API 跑 Chromium、Firefox、WebKit（Safari-family）三引擎；若默认 `python` 不能 `import playwright.sync_api`，用 `PYTHON_PLAYWRIGHT=/path/to/python` 或 `--python` 指定。
