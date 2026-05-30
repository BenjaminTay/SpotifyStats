# Frontend Architecture

React 19 + TypeScript 6.0 + Vite 8 + Tailwind CSS v4 + shadcn/ui (base-nova) + React Router v7 + TanStack React Query + ECharts 6。

路径别名 `@/` → `src/`。

## 目录结构

```
src/
├── api/              ← API 客户端 + 错误模型 + TanStack QueryClient + Query Key 工厂 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件（settings/ | account/collection/）
├── components/
│   ├── ui/           ← shadcn/ui 组件（可随意修改）
│   ├── charts/       ← ECharts 封装（动态 import）+ 纯 DOM 图表
│   ├── layout/       ← AppLayout, Masthead, ThemeToggle
│   └── shared/       ← GlassCard, KpiCard, WeekSelector, CoverCell, FormattedText 等
├── pages/            ← 路由级页面（React.lazy 分包）
├── hooks/            ← useDashboard, useBillboard, useYearlyReview, useSettings, useAccount
├── lib/              ← cn(), chinese, insights, theme, personality-themes, genre-regions
└── types/            ← 手写 TypeScript 展示类型
```

## 路由结构

```
/                          → DashboardPage
/analysis/stats            → AnalysisLayout > StatsTab
/analysis/charts           → AnalysisLayout > ChartsTab
/yearly-review             → YearlyReviewPage
/billboard                 → BillboardPage
/billboard/number-ones     → NumberOnesPage
/billboard/all-time        → AllTimeChartsPage
/billboard/records         → RecordsPage
/music/tracks/:trackId     → TrackDetailPage
/music/albums/:albumName   → AlbumDetailPage
/music/artists/:artistName → ArtistDetailPage
/settings                  → SettingsPage
/account                   → AccountCenterPage
```

旧 `/billboard/track|album|artist/*` 仅做兼容跳转到 `/music/*`。

播放分析子页面通过 URL search params 自动保留 `period`/`period_value`/`start`/`end` 参数。

## 数据获取 (TanStack React Query)

统一配置：staleTime 5 分钟 / gcTime 30 分钟 / retry 2 次 / refetchOnWindowFocus false。

Query Key 工厂在 `@/api/query-keys.ts`，按领域 namespace（dashboard/billboard/analysis/settings/account/yearlyReview）。

AppLayout 首屏渲染后延迟预取常用数据。年度回顾使用序列化预取（`for...of` + `await`）避免并发请求触发 SQLite 锁竞争。

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

## 测试

vitest + React Testing Library (jsdom)，`npm test` 运行。
