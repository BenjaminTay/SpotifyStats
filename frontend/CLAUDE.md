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
│   ├── music/details/     ← ArtistDetailExperience + AlbumDetailExperience + ArtistReleaseCycleSection + Primitives
│   ├── settings/components/  ← 7 配置 Section 组件
│   └── account/collection/   ← 收藏分析组件
├── components/
│   ├── ui/           ← shadcn/ui 组件（可随意修改）
│   ├── charts/       ← ECharts 封装（动态 import）+ 纯 DOM 图表
│   ├── layout/       ← AppLayout, Masthead, ThemeToggle
│   └── shared/       ← GlassCard, KpiCard, WeekSelector, CoverCell, FormattedText 等
├── pages/            ← 路由级页面容器（React.lazy 分包，纯组合 feature 组件）
├── hooks/            ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount
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

Query Key 工厂在 `@/api/query-keys.ts`，按领域 namespace：dashboard / billboard / analysis / settings / account / yearlyReview / music / library / versionMerge。

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
- 详细风格指南见 `UI_STYLE_GUIDE.md`

## 图表

- ECharts 通过组件内动态 `import()` 按需加载
- `RankTrendChart`：排名趋势图（断档填充、全貌/细节缩放、dataZoom 滑块、峰值 Pin 标记、连续冠周 markArea 色带）
- `ReleaseTimelineChart`：发行周期排名趋势
- `ListeningClock`：极坐标时针式 24 小时听歌分布

## 关键约束

- 外部文本（LLM、Wikipedia、翻译）必须经 `react-markdown` + `rehype-sanitize` 渲染，禁止 `dangerouslySetInnerHTML`
- LLM API Key 永不对前端返回明文，通过 `POST /apply` 端点让服务端直接写入
- 图表组件不能 SSR，必须 lazy load
- 新增页面务必参考 `UI_STYLE_GUIDE.md`
- 简繁转换用 `displayName()` 统一入口，OpenCC 按需动态 import
- **新增 GET hook → TanStack Query + `queryKeys`**；禁止模块级 `new Map()` 数据缓存
- **页面容器只做路由入口**，实现细节在 `features/`

## 测试

vitest + React Testing Library (jsdom)，`npm test` 运行。含 `phase5-architecture.test.ts` 架构护栏测试。
