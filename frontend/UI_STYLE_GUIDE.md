# 编辑风 × 液态玻璃 — UI 风格指南

Spotify Stats 前端的设计系统文档。本文档描述已落地的 UI 风格，供新增页面时参考。

## 设计理念

**编辑风 (Editorial)** 与 **液态玻璃 (Liquid Glass)** 的融合：
- 编辑风提供排版气质——大字距衬线标题、紧凑的无衬线标签、杂志式留白和信息层级
- 液态玻璃提供材质感——半透明卡片、背景模糊、柔和阴影、微妙的深度层次
- 日/夜双皮肤共用同一套结构变量，仅颜色切换

## 颜色系统

所有颜色使用 `oklch()` 色彩空间，定义在 `src/index.css` 的 `:root`（浅色）和 `.dark`（深色）中。

### 浅色主题 (Light)

| Token | 值 | 用途 |
|-------|-----|------|
| `--background` | `oklch(0.974 0.008 92.8)` ≈ `#FAF7F2` | 页面底色，暖奶油白 |
| `--foreground` | `oklch(0.228 0.018 67.5)` ≈ `#2D2420` | 主文字色，深棕 |
| `--card` | `oklch(1 0 0 / 0.7)` | 卡片背景，70% 透明白 |
| `--muted` | `oklch(0 0 0 / 0.03)` |  muted 背景 |
| `--muted-foreground` | `oklch(0.472 0.018 60.2)` ≈ `#6B5E58` | 次要文字，暖灰 |
| `--accent-foreground` | `oklch(0.563 0.18 28.2)` ≈ `#C84C3D` | 强调色，编辑风红 |
| `--border` | `oklch(0 0 0 / 0.06)` | 边框，6% 黑 |
| `--radius` | `0.75rem` (12px) | 基础圆角 |

### 深色主题 (Dark)

| Token | 值 | 用途 |
|-------|-----|------|
| `--background` | `oklch(0.149 0.003 270)` ≈ `#141416` | 页面底色，炭黑 |
| `--foreground` | `oklch(0.943 0.008 87.9)` ≈ `#F0EBE3` | 主文字色，暖米白 |
| `--card` | `oklch(0.199 0.003 270 / 0.65)` | 卡片背景，65% 透明深灰 |
| `--muted-foreground` | `oklch(0.659 0.015 80.4)` ≈ `#A09888` | 次要文字 |
| `--accent-foreground` | `oklch(0.632 0.12 35.1)` ≈ `#D4836F` | 强调色，柔和红 |
| `--border` | `oklch(1 0 0 / 0.06)` | 边框，6% 白 |

### 图表色盘 (6 色，浅色/深色各一套)

| 序号 | 浅色 | 深色 | 语义 |
|------|------|------|------|
| 1 | `oklch(0.563 0.18 28.2)` 红 | `oklch(0.632 0.12 35.1)` 红 | 主强调 |
| 2 | `oklch(0.583 0.108 51.4)` 橙 | `oklch(0.598 0.105 39.8)` 橙 | 次要 |
| 3 | `oklch(0.623 0.14 79.9)` 金 | `oklch(0.697 0.125 73.5)` 金 | 金色 |
| 4 | `oklch(0.443 0.065 151.5)` 绿 | `oklch(0.615 0.08 138)` 绿 | 苔绿 |
| 5 | `oklch(0.425 0.095 267.8)` 蓝 | `oklch(0.635 0.08 257)` 蓝 | 蓝调 |
| 6 | `oklch(0.47 0.06 330)` 紫 | `oklch(0.58 0.06 330)` 紫 | 紫调 |

### 语义色 (用于排名升降、NEW/RE 标记)

| 语义 | 浅色 | 深色 |
|------|------|------|
| 上升 (↑) | `#4A6B4F` | `#7D9B76` |
| 下降 (↓) | 同 `--accent-foreground` | 同 `--accent-foreground` |
| NEW | `#3B5998` | `#7B9CC8` |
| RE | `#B8860B` | `#D4A24E` |
| 峰值 #1 | 同 `--accent-foreground` | 同 `--accent-foreground` |

## 字体系统

### 字体族

| Token | 字体栈 | 用途 |
|-------|--------|------|
| `--font-serif` / `--font-heading` | `'Playfair Display', Georgia, 'Times New Roman', serif` | 标题、大数字、KPI 值 |
| `--font-sans` | `'Inter Variable', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif` | 正文、标签、导航、表格内容 |

Inter 通过 `@fontsource-variable/inter` npm 包加载。Playfair Display 通过 Google Fonts CDN 在 `index.html` 中加载（含 400-800 字重 + 斜体）。

### 排版规格

| 元素 | 字体 | 字号 | 字重 | 行高 | 字距 | 其他 |
|------|------|------|------|------|------|------|
| Dashboard Hero 标题 | serif | 52px | bold (700) | 1.06 | -1.2px | 可换行 |
| Billboard Hero 标题 | serif | 44px | bold (700) | 1.06 | -1.2px | — |
| Hero kicker | sans | 11px | bold (700) | — | 1.8px | 全大写，accent-foreground 色 |
| Hero 副标题 | sans | 17px | normal (400) | relaxed | — | muted-foreground，最大宽 520px |
| KPI 数值 | serif | 44px | bold (700) | 1 | -1px | — |
| KPI 标签 | sans | 12px | semibold (600) | — | 1px | 全大写，muted-foreground |
| KPI 趋势 | sans | 12px | semibold (600) | — | — | 带 lucide-react 图标 |
| 区域标题 | serif | 20px | semibold (600) | — | — | 如「月度播放趋势」 |
| 卡片小标题 | sans | 10px | bold (700) | — | 1.2px | 全大写，muted-foreground |
| 导航链接 | sans | 12px | semibold (600) | — | 1.2px | 全大写 |
| Logo | serif | 22px | bold (700) | — | -0.3px | "Stats" 部分斜体 + accent 色 |
| 周标签 | serif | 28px | semibold (600) | 1.1 | — | WeekSelector 中 |
| 周日期范围 | sans | 13px | normal (400) | — | — | muted-foreground |
| Billboard 排名 | serif | 22px | semibold (600) | — | — | 补零两位 |
| Billboard 曲目名 | sans | 14px | semibold (600) | — | — | — |
| Billboard 艺人名 | sans | 12px | normal (400) | — | — | 斜体，muted-foreground |
| Billboard 播放数 | sans | 15px | semibold (600) | — | — | tabular-nums |
| 表格列头 | sans | 10px | bold (700) | — | 1.2px | 全大写，muted-foreground |
| 升降标记 | sans | 11px | bold (700) | — | — | ↑↓ 箭头 + 数字 |
| NEW/RE 标记 | sans | 10px | bold (700) | — | 1px | 全大写 |
| 图表注释 | serif | 14px | italic (400) | relaxed | — | 左边 3px accent 竖线 |
| 页脚 | serif | 13px | italic (400) | — | — | muted-foreground |

## 布局系统

### 全局布局 (AppLayout)

```
┌──────────────────────────────────────────────┐
│ NoiseOverlay (fixed, z-0, opacity 0.035)     │
│ Dark ambient gradients (fixed, z-0,仅深色)    │
│                                              │
│ ┌─ Masthead (sticky, z-50) ─────────────────┐ │
│ │ Logo · Nav · ThemeToggle                  │ │
│ └────────────────────────────────────────────┘ │
│                                              │
│ ┌─ <main> (max-w-[1200px], mx-auto) ────────┐ │
│ │ <Outlet /> — 页面内容                     │ │
│ └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

关键数值：
- 页面最大宽度：`1200px`，水平居中
- 内边距：`px-10 py-10`（40px）
- Masthead 内边距：`px-10 py-4`（40px / 16px）

### 仪表盘页面布局 (DashboardPage)

```
┌─ Hero 区 ────────────────────────────────────┐
│ kicker (11px 全大写 accent)                   │
│ 标题 (52px serif)                             │
│ 副标题 (17px sans, muted, max-w-[520px])      │
└──────────────────────────────────────────────┘
┌─ KPI 行 ─────────────────────────────────────┐
│ grid grid-cols-4 gap-10                       │
│ border-b border-border pb-10 mb-10            │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐         │
│ │ 数值  │ │ 数值  │ │ 数值  │ │ 数值  │         │
│ │ 标签  │ │ 标签  │ │ 标签  │ │ 标签  │         │
│ └──────┘ └──────┘ └──────┘ └──────┘         │
└──────────────────────────────────────────────┘
┌─ 内容区 grid grid-cols-[1fr_380px] gap-10 ──┐
│ ┌─ 左：月度趋势图表 ───────────────────────┐  │
│ │ 标题 (20px serif)                       │  │
│ │ ECharts 柱状图 (240px)                  │  │
│ │ 注释 (14px serif italic, 左边 accent 线) │  │
│ └────────────────────────────────────────┘  │
│ ┌─ 右：侧边栏 space-y-6 ──────────────────┐  │
│ │ GlassCard: 平台分布 (进度条)             │  │
│ │ GlassCard: 聆听高峰 (32px serif)        │  │
│ └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Billboard 页面布局 (BillboardPage)

```
┌─ Hero 区 ────────────────────────────────────┐
│ kicker "Chart / Weekly"                       │
│ 标题 "Billboard 周榜" (44px serif)            │
└──────────────────────────────────────────────┘
┌─ Tab 切换 ───────────────────────────────────┐
│ 单曲榜 | 专辑榜 | 艺人榜                       │
│ (border-b-2 活动指示器)                       │
└──────────────────────────────────────────────┘
┌─ 周选择器 ───────────────────────────────────┐
│ ◀ (圆形按钮) | Week 21, 2026 (28px serif) | ▶│
│              | 5月18日 — 5月24日              │
└──────────────────────────────────────────────┘
┌─ 摘要条 ─────────────────────────────────────┐
│ 新入榜(N) · 重回榜(R) · 最高播放 · 总播放      │
│ (24px serif 数字 + 10px 全大写标签)           │
└──────────────────────────────────────────────┘
┌─ GlassCard 排名表格 ─────────────────────────┐
│ # | 变动 | 封面 | 曲目 | 播放 | PK | 在榜 | PK Wks │
│ 01| ↑ 1  | 🎵   | ... | 247 | 1  | 88  | 34     │
│ 02| ↓ 1  | 🎵   | ... | 231 | 1  | 96  | 51     │
│ ...                                         │
└──────────────────────────────────────────────┘
┌─ 页脚 (13px serif italic) ───────────────────┐
│ 共 N 首曲目 · 更新时间 · CST                  │
└──────────────────────────────────────────────┘
```

## 组件规格

### Masthead（粘性顶栏）

- 定位：`sticky top-0 z-50`
- 背景：`bg-card/45 backdrop-blur-[12px]`（45% 透明卡片 + 毛玻璃模糊）
- 边框：`border-b border-border`
- 高度：padding `py-4`（16px）
- Logo：`Spotify Stats`，serif 22px bold，"Stats" 斜体 accent 色
- 导航项：12px sans semibold 全大写 tracking-[1.2px]，活动项底部 accent 色 2px 下划线
- 当前导航：Masthead 顶级入口使用“播放分析”，其二级 tab 统一为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 账号中心”；不要再额外增加 Masthead 下拉或第二套页面子导航
- 主题切换：右对齐药丸按钮

### ThemeToggle（主题切换）

- 容器：`rounded-full border border-border bg-card p-1`
- 两个按钮：☀️ 白日 / 🌙 夜晚（lucide-react Sun/Moon 图标）
- 活动态：`bg-card text-foreground shadow-sm`，11px semibold
- 非活动态：`text-muted-foreground hover:text-foreground`
- 图标尺寸：`h-3.5 w-3.5`（14px）

### GlassCard（毛玻璃卡片）

```tsx
className="rounded-[16px] border border-border bg-card backdrop-blur-[12px] shadow-sm
           transition-[background,border,box-shadow] duration-400
           hover:bg-card hover:shadow-lg"
```
- 圆角：16px（`--radius-lg`）
- hover 时背景加实、阴影加深

### KpiCard（KPI 卡片）

- 无外层容器，直接由父级 grid 控制间距
- 标签：12px sans semibold 全大写 tracking-[1px]，muted-foreground，mb-1.5
- 数值：44px serif bold leading-none tracking-[-1px]，mb-2
- 趋势：12px sans semibold + lucide-react 图标 (h-3 w-3)，上下箭头分色
  - 上升：`text-[#4A6B4F] dark:text-[#7D9B76]`
  - 下降：`text-accent-foreground`
  - 持平：`text-muted-foreground`

### WeekSelector（周选择器）

- 布局：`flex items-center gap-3.5`
- 左右箭头按钮：圆形 34×34px，`rounded-full border bg-card backdrop-blur-[12px]`
  - 可用态：`cursor-pointer hover:border-foreground/15 hover:text-foreground`
  - 禁用态：`cursor-not-allowed opacity-40`
- 周标签：28px serif semibold leading-[1.1]
- 日期范围：13px sans，muted-foreground
- 使用 lucide-react 的 ChevronLeft / ChevronRight 图标 (h-4 w-4)

### 平台分布进度条 (PlatformDistChart)

不使用 ECharts，纯 DOM + Tailwind 进度条：

- 容器：`space-y-3`
- 每行：标签 + 百分比 + 5px 高进度条
- 标签：13px sans font-medium，两端对齐
- 百分比：font-semibold tabular-nums
- 进度条轨道：`h-[5px] w-full rounded-[3px] bg-border`
- 进度条填充：`h-full rounded-[3px]`，颜色循环 4 色：
  1. `bg-accent-foreground`
  2. `bg-[#C17A4E] dark:bg-[#C97B6B]`
  3. `bg-[#B8860B] dark:bg-[#D4A24E]`
  4. `bg-[#3B5998] dark:bg-[#7B9CC8]`
- 宽度相对于最大值等比缩放，`transition-all duration-500`

### NoiseOverlay（噪点纹理）

- 定位：`fixed inset-0 z-0 opacity-[0.035] pointer-events-none`
- SVG feTurbulence 滤镜生成 fractalNoise，256×256 重复平铺
- 浅色和深色模式共用，无颜色差异

### 深色环境渐变 (AppLayout 中)

仅在深色模式下显示（`hidden dark:block`）：
- 两个 `radial-gradient` 叠加：
  - 左上区域：`oklch(0.563 0.18 28.2 / 0.06)`（accent 色 6% 透明度）
  - 右下区域：`oklch(0.697 0.125 73.5 / 0.04)`（金色 4% 透明度）
- `pointer-events-none`，不阻挡交互

## 图表规范 (ECharts)

### 公共主题 (EChartsTheme)

- 背景：`transparent`（无背景色块）
- 字体：`'Inter Variable', 'Inter', -apple-system, sans-serif`
- 文字颜色：`#A09888`（深色）/ `#6B5E58`（浅色）
- 网格：虚线分割线，`rgba(255,255,255,0.04)`（深色）/ `rgba(0,0,0,0.04)`（浅色）
- 坐标轴线：隐藏
- 刻度线：隐藏
- Tooltip：半透明背景（90% 不透明），匹配主题色

### 月度趋势柱状图 (MonthlyTrendChart)

- 类型：柱状图 (bar)
- X 轴：月份标签（如「1月」「2月」），11px
- Y 轴：播放次数，标签名「播放次数」，11px
- 柱体：6 色循环，柱顶圆角 `[3,3,0,0]`，最大宽 36px
- 交互：emphasis 时 opacity 0.85
- 高度：240px
- Tooltip：axis 触发 + shadow 指示器

## 数据状态处理

### 加载态

每个页面有对应的 Skeleton 组件，使用 shadcn/ui 的 `<Skeleton>` 组件：

- **DashboardSkeleton**：模仿 Hero + KPI 4 列 + 月度图表 + 侧边卡片的骨架布局
- **BillboardSkeleton**：模仿 Hero + Tabs + 周选择器 + 摘要条 + 表格的骨架布局

### 错误态

统一的错误展示模式：
```
┌── AlertCircle icon (h-8 w-8, accent-foreground) ──┐
│  "加载失败：{error.message}" (muted-foreground)     │
│  [重新加载] 圆角按钮 (accent-foreground 底色)       │
└────────────────────────────────────────────────────┘
```
按钮样式：`rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground`

### 客户端缓存

所有 GET 数据统一使用 TanStack React Query 与 `queryKeys`。Desktop/Phone presentation 必须复用同一 Route Container、查询结果、过滤指纹和 URL 状态；不得为移动端新增模块级 API 响应缓存或第二套请求。

## 动画与过渡

| 属性 | 时长 | 缓动 |
|------|------|------|
| 背景色 (background) | 400ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| 文字色 (color) | 400ms | 同上 |
| 边框色 (border) | 400ms | 同上 |
| 卡片阴影 (box-shadow) | 400ms | 同上 |
| 导航 active 态 | 200ms | ease |
| 播放量进度条宽度 | 300ms | ease |
| 平台分布进度条宽度 | 500ms | ease |
| Tab 切换 (color, border) | 200ms | ease |
| 主题切换按钮 | 250ms | ease |

播放进度条使用 `<span>` + `transition-[width] duration-300`，数据变化时宽度平滑过渡。

## 页面通用模式

新增页面时应遵循以下模式：

1. **Hero 区**：`mb-12`（Dashboard）/ `mb-6`（Billboard），kicker + 标题 + 可选副标题
2. **容器卡片**：用 `<GlassCard>` 包裹数据密集区域
3. **区域标题**：`font-serif text-xl font-semibold mb-5`
4. **卡片内小标题**：`font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-3`
5. **无内容区标题**：masthead 导航即页面切换，页面内不放 PageSwitcher
6. **数字格式**：使用 `new Intl.NumberFormat('zh-CN').format(n)`，时长用 `{n}h` 格式
7. **页脚**：`font-serif text-[13px] italic text-muted-foreground mt-6`
8. **三种状态**：loading（Skeleton）→ error（AlertCircle + 重试按钮）→ data（正式内容）

## 移动端网页规范

移动端不是桌面页面等比缩小，而是共享业务状态的独立 presentation。`useViewportMode()` 将宽度划分为 Phone（`<768px`）、Compact（`768–1023px`）和 Desktop（`>=1024px`）；Phone 与 Desktop 的重图表、宽表和长列表必须互斥挂载，Compact 默认沿用桌面信息结构并做单列或紧凑排布。

### Shell 与导航

- Phone 使用 `MobileTopBar`、`MobileBottomNav` 和 `MobileSectionSwitcher`，不挂载桌面 Masthead；Desktop/Compact 不挂载 Phone Shell。
- Bottom Nav 固定为首页、播放、榜单、社区、AI。播放分析和 Billboard 的二级栏目通过 Section Sheet 进入，当前栏目和返回目标继续由路由/URL 表达。
- 音乐搜索、音乐详情、社区详情和 Settings 子页使用 Push Top Bar；按页面语义决定是否隐藏 Bottom Nav，禁止叠加第二套悬浮导航。
- Top Bar、Bottom Nav、Sheet 和全屏层必须处理 `env(safe-area-inset-*)`；正文底部留出导航与安全区空间。

### 信息重排

- 桌面宽表在 Phone 转换为 `MobileEntityRow`、排名列表、时间线或纵向成绩卡；隐藏列不得改变原始排序、资格或固定排名。
- KPI 通常使用 2×2 网格；筛选、排序、年份和字段选择优先使用 chips、segmented control 或 Bottom Sheet。
- 手机详情保留高频栏目，低频栏目进入“更多”；栏目、实体、年份、排序、分页和筛选继续写入或恢复现有 URL 状态。
- Desktop/Phone 共享同一 API、TanStack Query、row model、格式化函数和统计事实，只允许 presentation 层分叉。

### 触控与图表

- 主要可见操作的最小触控区域为 `44×44px`；图标按钮必须有 accessible name，输入框必须有可关联标签。
- 关键能力不得依赖 hover。图表必须支持点击/触摸 disclosure；复杂图表提供 `MobileFullscreenChart`，打开后锁定背景滚动，关闭后把焦点还给触发按钮。
- 页面滚动与图表拖动区域要有明确边界；仅在确有必要时启用 dataZoom，避免吞掉纵向页面手势。

### Settings 能力边界

- Phone 可完成主题、名称显示、播放过滤、合并级别、榜单参数、Spotify 日常连接/同步和当前 AI Profile 等低风险操作。
- 文件导入、元数据归并、曲目署名、艺人身份、流派与语言审核、LLM 凭据和系统维护保留桌面工作台；手机只显示状态、目标摘要和“在电脑上管理”入口。
- 普通消费页面不展示来源、证据、置信度、审核状态或内部 ID 等治理术语。

### PWA 与独立窗口

- 手机 Settings 首页可以展示一张 `App Mode / PWA` 安装卡；它属于访问方式，不新增第二套功能导航。
- 安装卡沿用编辑风卡片、品牌强调色和至少 44px 操作目标；Chromium 提供安装按钮，iOS 提供 Safari 分享菜单说明，standalone 显示已安装状态。
- PWA `theme-color` 必须随日/夜主题切换；standalone 继续使用同一 Phone Shell、safe area 与路由语义。
- 离线状态只提供连接说明。不得缓存或伪造个人统计、榜单、账号、OAuth 或 AI 数据，也不得把“安装成功”表述为“离线数据可用”。

### 移动质量门禁

- 必测矩阵：360×800、390×844、430×932、768×1024、1280×800。
- Phone 页面级横向溢出、console error/warning、无障碍控件库存违规、主要触控目标小于 44px 均为 0。
- Chromium、Firefox、WebKit（Safari-family）均需通过 Shell 与核心交互 smoke；生产预览预算为 LCP <=2.5s、CLS <=0.1、TBT <=200ms、横向溢出 0。
- 发布前使用 `frontend_route_smoke.mjs --viewport matrix`、移动 interaction/chart smoke、control inventory、long-list、cross-browser 与 Web Vitals probe 复核。

## 依赖关系

- **样式**：Tailwind CSS v4 + `tw-animate-css`
- **组件库**：shadcn/ui v4（base-nova, neutral），源码在 `@/components/ui/`
- **图表**：ECharts 6 + echarts-for-react（仅月度趋势图使用）
- **图标**：lucide-react
- **工具**：`cn()` from `@/lib/utils`（tailwind-merge + clsx）

## 文件索引

| 文件 | 职责 |
|------|------|
| `src/index.css` | 全局主题变量（`@theme inline` + `:root` + `.dark`） |
| `src/App.tsx` | 路由定义（`/` + `/analysis` + `/billboard` + `/music/*`） |
| `src/lib/theme.ts` | 图表色盘常量 + `getChartColors()` |
| `src/hooks/useTheme.tsx` | ThemeProvider + useTheme hook |
| `src/hooks/useDashboard.ts` | Dashboard 数据获取 + 缓存 |
| `src/hooks/useBillboard.ts` | Billboard 数据获取 + 缓存 + 周导航 |
| `src/hooks/useAnalysis.ts` | 播放统计、播放排行、实体播放统计 API hook |
| `src/components/layout/AppLayout.tsx` | 按视口互斥挂载 Desktop/Phone Shell（NoiseOverlay + Masthead 或 Mobile Top/Bottom Bar + Outlet） |
| `src/components/layout/Masthead.tsx` | 粘性顶栏（Logo + Nav + ThemeToggle） |
| `src/components/layout/MobileTopBar.tsx` | Phone 页面顶栏、返回、栏目和更多操作入口 |
| `src/components/layout/MobileBottomNav.tsx` | Phone 五项主导航与 safe-area 处理 |
| `src/components/layout/MobileSectionSwitcher.tsx` | 播放分析/Billboard 二级栏目 Bottom Sheet |
| `src/components/mobile/` | Mobile Sheet、实体行、图表卡、全屏图表、分页和状态原语 |
| `src/components/layout/ThemeToggle.tsx` | 日/夜切换药丸 |
| `src/components/shared/NoiseOverlay.tsx` | SVG 噪点纹理 |
| `src/components/shared/GlassCard.tsx` | 毛玻璃卡片 |
| `src/components/shared/KpiCard.tsx` | KPI 数值卡片 |
| `src/components/shared/WeekSelector.tsx` | 周导航选择器 |
| `src/components/shared/PageSwitcher.tsx` | 页面切换按钮组（已废弃，导航由 Masthead 承担） |
| `src/components/shared/ArtistEnrichmentView.tsx` | 艺人百科结构化视图（摘要/基本信息/生涯时间线/风格/数据/成就） |
| `src/components/shared/AlbumEnrichmentView.tsx` | 专辑百科结构化视图（摘要/基本信息/风格/榜单表现/荣誉/单曲） |
| `src/components/shared/KeyFactsCard.tsx` | 基本信息卡片（分类着色图标） |
| `src/components/shared/StatsGrid.tsx` | 统计数据网格（渐变背景 + 彩色数值） |
| `src/components/shared/CareerTimeline.tsx` | 生涯时间线（彩色节点 + 渐变连线） |
| `src/components/shared/GenreTags.tsx` | 音乐风格标签（按流派着色） |
| `src/components/shared/ChartBars.tsx` | 榜单表现条形图（渐变进度条 + 冠单皇冠图标） |
| `src/components/shared/FormattedText.tsx` | 格式化文本（段落分割 + 粗体标注） |
| `src/components/charts/EChartsTheme.ts` | ECharts 公共主题配置 |
| `src/components/charts/MonthlyTrendChart.tsx` | 月度趋势柱状图 |
| `src/components/charts/PlatformDistChart.tsx` | 平台分布进度条 |
| `src/components/charts/ReleaseTimelineChart.tsx` | 发行周期排名趋势图 |
| `src/pages/DashboardPage.tsx` | 总览仪表盘页面 |
| `src/pages/BillboardPage.tsx` | Billboard 周榜页面 |
| `src/types/dashboard.ts` | Dashboard 类型定义 |
| `src/types/billboard.ts` | Billboard 类型定义 |
