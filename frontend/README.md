# Spotify Stats — React 前端

## 技术栈

- **框架**：React 19 + TypeScript 6.0
- **构建**：Vite 8（开发端口 5173，`/api` 代理至后端 8000）
- **样式**：Tailwind CSS v4 + shadcn/ui v4（base-nova）
- **路由**：React Router v7
- **图表**：ECharts 6 + echarts-for-react
- **图标**：lucide-react
- **字体**：Inter Variable（sans）+ Playfair Display（serif，Google Fonts CDN）

## 快速启动

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 生产构建
```

确保后端已启动（`uvicorn backend.main:app --reload`，端口 8000）。

## 页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | DashboardPage | 总览仪表盘：KPI 行、月度趋势图、平台分布、动态数据洞察（月度季节分析 + 聆听高峰） |
| `/analysis` | AnalysisLayout | 播放分析：二级 tab 收敛 `/stats`（播放统计 + 最近播放 + 时钟图）、`/charts`（播放排行 track/album/artist × plays/hours）、`/yearly-review`（年度总结）、`/analysis/records`（播放记录）与 `/account`（账号中心） |
| `/yearly-review` | YearlyReviewPage | 年度总结：2 Tab（自定义年度总结 + 官方 Wrapped 2025）、年份选择器、序列化预取（避免 SQLite 并发锁）、ErrorBoundary 容错 |
| `/billboard` | BillboardPage | Billboard 周榜：单曲/专辑/艺人三榜、周切换（含 URL 参数 `?week=`）、排名表（含 CoverCell 封面 + 跳转详情链接）、Tab 选择跨页面记忆保持 |
| `/billboard/number-ones` | NumberOnesPage | 每周榜首：3 子 Tab（单曲/专辑/艺人）、年度筛选 + KPI 卡片 + 冠单表 + 排行柱状图 + 空冠统计、子 Tab 和年份选择跨页面记忆保持 |
| `/billboard/all-time` | AllTimeChartsPage | Billboard 总榜：3 实体 Tab（歌曲/专辑/艺人）、富数据表格（走势评分/排名峰值/在榜周数等）、列头排序、排名峰值筛选（全部/#1/Top5/Top10/空冠）、可拖拽列宽（localStorage 记忆）、翻页、Tab/筛选/排序/翻页均跨页面记忆保持 |
| `/music/tracks/:trackId` | TrackDetailPage | 单曲详情：封面 Hero、KPI 卡片行、排名趋势图（含断档填充 + 全貌/细节缩放 + 峰值标记 + 连续冠周色带）、榜单历史表（含播放条、PK/PK Wks/在榜滚动统计）、艺人名和专辑名可点击跳转对应详情 |
| `/music/artists/:artistName` | ArtistDetailPage | 艺人详情：4 Tab（榜单表现/单曲成绩/专辑成绩/歌手生涯）、封面 Hero、6 KPI 卡片、排名趋势图 + 最佳单曲叠加线、视觉播放条、走势点数/排名、Popularity 视觉进度条 |
| `/music/albums/:albumName` | AlbumDetailPage | 专辑详情：3 Tab（榜单表现/曲目表现/专辑百科）、封面 Hero、6 KPI 卡片、排名趋势图 + 最佳单曲叠加线、视觉播放条、走势点数/排名、艺人名可点击跳转艺人详情 |
| `/settings` | SettingsPage | 设置：5 区块（Data & Display / LLM Translation / Billboard Parameters / Version Merge / Data Import，含 LLM 配置档案管理） |

## UI 风格

**编辑风 × 液态玻璃** — 杂志式排版 + 毛玻璃材质 + 日/夜双皮肤。

详细设计规范见 [`UI_STYLE_GUIDE.md`](./UI_STYLE_GUIDE.md)。新增页面前务必阅读。

### 移动网页

- `<768px` 使用独立 Phone presentation；`768–1023px` 为 Compact；`>=1024px` 使用 Desktop。
- Phone Shell 由 `MobileTopBar`、五项 `MobileBottomNav` 和栏目 `MobileSectionSwitcher` 构成，Phone/Desktop 重组件互斥挂载。
- 手机和 PC 共用 Route Container、TanStack Query、URL 状态、过滤指纹和统计事实；Settings 的复杂治理工作台保留桌面端。
- 本地查看可把浏览器响应式视口设为 390×844；发布前用 `node ../scripts/frontend_route_smoke.mjs --viewport matrix` 运行五档视口门禁。

### PWA / App Mode

- 生产构建会注册 `/sw.js`，Manifest 位于 `/manifest.webmanifest`；开发服务器不注册 Service Worker，避免缓存干扰热更新。
- 手机 Settings 首页提供安装卡；Chromium 使用 `beforeinstallprompt`，iOS 显示 Safari“添加到主屏幕”说明。
- Service Worker 只缓存 PWA 壳层和版本化静态资源，禁止缓存 `/api`、`/covers`、OAuth/LLM 凭据或个人统计响应。
- `npm run build && npm run preview` 可验证 PWA 静态资源；真实手机安装需要 HTTPS 和手机可访问的后端。

## 目录结构

```
src/
├── components/
│   ├── ui/          ← shadcn/ui 组件
│   ├── charts/      ← 图表组件（ECharts + 纯 DOM，含 RankTrendChart 排名趋势图）
│   ├── layout/      ← Desktop/Phone Shell（AppLayout, Masthead, MobileTopBar/BottomNav/SectionSwitcher）
│   ├── mobile/      ← Sheet、实体行、移动图表/全屏、分页和状态原语
│   └── shared/      ← 共享组件（GlassCard, KpiCard, WeekSelector, ChangeCell, CoverCell, BillboardSubNav 等）
├── features/        ← Feature-first Experience/Section/Primitives/Data 与移动 presentation
├── pages/           ← 薄路由容器
│   └── yearly-review/  ← 年度总结子组件（14 个：HeroSection, PersonalityReveal, TopCharts, GenrePanorama, TimeStory, HourClock, MusicMap, DiscoveryReturns, ListeningDepth, SpecialMoments, MonthlyDrilldown, YearComparison, ShareButton, OfficialWrapped）
├── hooks/           ← 自定义 hooks（GET 数据统一使用 TanStack Query + queryKeys）
├── lib/             ← API 客户端、工具函数、图表色盘、听歌人格主题、曲风地理映射
└── types/           ← TypeScript 类型定义（dashboard, billboard, analysis, settings, yearly-review）
```

## 主题

CSS 变量定义在 `src/index.css`：
- `@theme inline` — 结构变量（字体、圆角、shadcn 引用）
- `:root` — 浅色主题颜色
- `.dark` — 深色主题颜色

`useTheme()` hook 管理主题切换，localStorage 持久化，系统偏好回退。

## 性能

- GET 数据统一使用 TanStack Query；禁止新增模块级 API 响应缓存
- Phone/Desktop 的重图表、宽表和长列表互斥挂载，避免同时请求和渲染两套 presentation
- Dashboard `/full` 端点复用单个 `load_plays()` 调用（后端优化）
- Billboard `compute_billboard_data()` 有 `@lru_cache` 缓存（后端优化）
