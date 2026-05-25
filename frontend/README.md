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
| `/` | DashboardPage | 总览仪表盘：KPI 行、月度趋势图、平台分布、聆听高峰 |
| `/billboard` | BillboardPage | Billboard 周榜：单曲/专辑/艺人三榜、周切换（含 URL 参数 `?week=`）、排名表（含跳转详情链接） |
| `/billboard/track/:trackId` | TrackDetailPage | 单曲详情：封面 Hero、KPI 卡片行、排名趋势图、榜单历史表（含播放条、PK/PK Wks/在榜滚动统计） |
| `/billboard/artist/:artistName` | ArtistDetailPage | 艺人详情：3 Tab（榜单表现/周榜历史/曲目表现）、封面 Hero、排名趋势图 + 最佳单曲叠加线 |
| `/billboard/album/:albumName` | AlbumDetailPage | 专辑详情：2 Tab（榜单表现/曲目表现）、封面 Hero、排名趋势图 + 最佳单曲叠加线 |

## UI 风格

**编辑风 × 液态玻璃** — 杂志式排版 + 毛玻璃材质 + 日/夜双皮肤。

详细设计规范见 [`UI_STYLE_GUIDE.md`](./UI_STYLE_GUIDE.md)。新增页面前务必阅读。

## 目录结构

```
src/
├── components/
│   ├── ui/          ← shadcn/ui 组件
│   ├── charts/      ← 图表组件（ECharts + 纯 DOM，含 RankTrendChart 排名趋势图）
│   ├── layout/      ← 布局（AppLayout, Masthead, ThemeToggle）
│   └── shared/      ← 共享组件（GlassCard, KpiCard, WeekSelector, ChangeCell 等）
├── pages/           ← 页面组件
├── hooks/           ← 自定义 hooks（数据获取 + 客户端缓存）
├── lib/             ← API 客户端、工具函数、图表色盘
└── types/           ← TypeScript 类型定义
```

## 主题

CSS 变量定义在 `src/index.css`：
- `@theme inline` — 结构变量（字体、圆角、shadcn 引用）
- `:root` — 浅色主题颜色
- `.dark` — 深色主题颜色

`useTheme()` hook 管理主题切换，localStorage 持久化，系统偏好回退。

## 性能

- 模块级变量缓存 API 响应，页面切换不重复请求
- Dashboard `/full` 端点复用单个 `load_plays()` 调用（后端优化）
- Billboard `compute_billboard_data()` 有 `@lru_cache` 缓存（后端优化）
