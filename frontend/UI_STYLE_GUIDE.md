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
| `--font-serif` / `--font-heading` | `'Playfair Display Variable', 'Playfair Display', 'Songti SC', 'STSong', 'Noto Serif CJK SC', 'Noto Serif SC', 'SimSun', Georgia, serif` | 标题、大数字、KPI 值 |
| `--font-sans` | `'Inter Variable', 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif` | 正文、标签、导航、表格内容 |

Inter 与 Playfair Display 都通过 `@fontsource-variable/*` npm 包本地加载（Playfair Display Variable 含 400-800 字重 + 斜体）。中文字符使用显式 CJK 回退链，优先保持 macOS 与 iPhone 的宋体标题风格一致。

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

### 个人音乐头版布局 (DashboardPage)

```
┌─ 当日头条：叙事标题 + 主封面与两张辅助封面 ──┐
├─ 档案护照：记录跨度 / 有效播放 / 时长 / 歌曲 ┤
├─ 01 最近一章 ────────────────────────────────┤
│  最近 4 周摘要 + 轻量趋势 + 歌曲/专辑/艺人主角 │
├─ 02 最新个人 Billboard：三类冠军快照 ────────┤
└─ 03 长期记忆：年度年鉴入口 + 旧爱重听 ───────┘
```

头条由统计规则确定性生成，不调用 LLM。首页不重复放置数据更新时间、音乐搜索、数据陈旧提醒或账号/AI/社区/更新数据快捷入口，这些能力继续由全局导航和对应页面承载。Phone presentation 使用独立单列“口袋头版”，不挂载桌面拼贴；两端共享同一响应、过滤指纹与实体深链。

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
- 当前导航：Masthead 顶级入口使用“播放分析”，其二级 tab 统一为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 音乐档案”；不要再额外增加 Masthead 下拉或第二套页面子导航
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

### 音乐档案（`/account`）

- 页面和二级导航统一使用“音乐档案”，路由保留 `/account`。
- 视觉采用私人唱片档案：暖纸底、细档案线、编辑红、唱片封套与大号衬线数字；玻璃只用于导航、筛选和临时工具层，不给每段正文套玻璃卡。
- Desktop 使用档案封面与粘性纵向章节索引；Compact 使用横向章节条；Phone 是独立“口袋音乐档案”，不得缩放或同时挂载 Desktop DOM。
- Phone 封面使用两张有明确角色的收藏封套与黑胶拼贴，首屏事实固定为 2×2；章节正文实体只预览 Top 3–5。
- Phone 横向章节导航必须自动将当前章节滚入视口，并通过两侧渐隐提示仍有内容；正文中承担含义的辅助文字不低于 10px，只有纯装饰编号可使用 9px。
- Phone 收藏生命力固定为 2×2 卡片，不使用需要猜测可横滑的指标带；歌曲标题最多显示两行，艺人和时间状态进入同一正文列，不得由右侧状态栏挤压歌名。
- Phone 收藏库必须进入覆盖 Shell 的全屏层，服务端每页 10 条；搜索、类型、排序和页码恢复到 URL，页数较多时支持直接跳页，并支持 ESC、背景滚动锁定与焦点恢复。
- Phone 的播客和视频使用同构紧凑卡片：总时长与范围事实放在头部，下方展示带可用封面的 Top 3；不得恢复音频与视频总时长的悬殊对照条。
- 封面只显示收藏歌曲、专辑、艺人和歌单数量，不显示收藏覆盖期、播放截止日、数据状态或统计说明。
- 章节标题只保留编号与主标题，不添加解释性 subtitle；“播放多久后收藏”“收藏后再次播放”“搜索后的动作”等名称必须直接表达统计对象和时间范围。
- 收藏后再次播放展示“7 天内又听 / 第 8–30 天仍听 / 半年后还在听 / 一年后还在听”四个互补指标及其分子、分母；不得用四个单调累积的“多少天内”指标占满同一排，也不提供含义不直观的逐周“可观察”曲线。
- 收藏旅程不重复封面上的最早/最近收藏，改为第 100 / 200 / 400 / 800 首等倍增里程碑；“首次播放后，隔了最久才收藏”的示例必须直接显示间隔天数。
- “音乐之外”的播客与视频卡都使用标题条加 Top 3：播客标为“播放最多的电台和播客”，有本地节目封面才显示封面；视频展示本地可识别歌曲封面和详情深链。两卡不再用悬殊的音频总时长作主视觉对照。
- 搜索与发现只显示去重后的星期分布、24 小时时段带和三步动作链；不得向消费 UI 暴露原始搜索词、身份资料、人格推断、OAuth 凭据、“可验证”数量或方法口径。
- 数据读取只允许 `queryKeys.account.archive*` 对应的分拆接口；旧 `/api/account`、`/api/account/collection-insights`、`/api/profile` 及旧 account/habits 组件树均已退役，不得重新作为页面依赖。

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

- **HomeLoading**：分别模仿 Desktop 头版和 Phone 口袋头版的首屏骨架
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

### 播放分析与详情统计

- Phone Top Bar 已显示当前播放分析栏目时，播放统计、播放排行、年度总结和播放记录正文不再重复页面 H1；Desktop/Compact 继续保留原页面标题结构。
- 播放统计、播放排行和播放记录的时间范围触发器固定在右下角安全区上方，不能占据内容流或遮挡右上角内容。歌曲、专辑、艺人详情的统计 Tab 复用同一紧凑触发器与 `MobileTimeRangeSheet`，并在一个 Sheet 内同时调整时间窗口和统计口径。
- 播放记录五个栏目使用顶部横向滑动 Tab，并通过 `family` 查询参数恢复状态；栏目下不重复显示栏目标题或说明。手机排名卡统一使用 `MobileRecordTable`，默认展示 Top 3，完整榜单进入共享 Sheet。
- 同一行的统计口径按钮与实体分段器应具有相同的可见高度，同时保留至少 44px 的触控目标。手机卡片可省略与数值文案重复的列标题，但桌面表头和 accessible name 必须保留。

### 年度总结 V2（Desktop / Compact / Phone）

- 年报是面向个人用户的年度故事，不是审计报告。正文不得展示统计口径、过滤指纹、策略版本、证据等级、coverage、limitations 或“可比基线”等工程词；相关信息留在后端和测试。
- 每章标题只保留编号、短 kicker 和主标题，不在大标题下增加解释性 subtitle；封面也只保留年份、年鉴标题、时间范围和 KPI。
- 顶部六项 KPI 使用“年度播放 / 年度时长 / 年度活跃天数 / 年度播放曲目 / 年度播放专辑 / 年度播放艺人”，同比只在数值右侧显示红/绿箭头和百分比，不重复显示“高/低”，也不显示绝对差值。
- 荣誉分歧故事在宽屏使用两列，视口收窄时回到单列；关系故事标题必须按歌曲、专辑、艺人区分，同专辑/艺人多首入榜必须显示准确首数。
- 年度纪录章只展示后端精选出的 6–8 条，不提供“更多年度纪录”展开；完整播放纪录与 Billboard 纪录留在各自独立页面。相邻章节统一使用 `clamp(48px, 5.5vw, 80px)` 的纵向 padding，避免标题与上一模块之间出现过大空白。
- 歌曲、专辑、艺人优先用 `EntityMediaLink` 统一展示封面、名称、副标题和详情链接；完整榜单、时间线、纪录及故事卡片不得退回纯文字清单。
- 年度月份只有一个正文入口：年度时间线下的可展开月份明细。附录标题统一为“完整榜单”，只提供播放榜与个人 Billboard。
- 章节导航固定在桌面 Masthead 下方，并为锚点保留滚动间距。年度 V2 当前不展示海报操作；后续新增操作也不得使用会遮挡 KPI、表格或故事卡片的浮动按钮。
- 年份按钮从小到大排列且只显示四位年份，不附加“进行中”等状态；年度总结默认打开最新可用年份，即使当前年仍在进行中。完整年度封面隐藏状态与日期，当前年报告仍在封面显示“进行中 · 截至日期”；封面不显示三条头条或海报按钮。年度动态文案、歌曲/专辑/艺人名称遵循全局简繁体偏好，事件卡需要明确实体类型。
- `/yearly-review` 只保留自有年度总结，不显示“年度总结 / 官方 Wrapped”模式切换；移除切换后不得保留空框、占位间距或隐藏的第二套年度 DOM。
- Phone 与 Desktop/Compact 共享 V2 报告、筛选、生成状态和缓存，但不得直接缩放桌面 DOM。Phone 使用独立“口袋音乐年鉴”presentation：2×3 KPI、紧凑 sticky 章节进度、Bottom Sheet 目录、纵向阶段时间线和单列故事卡。
- Phone 的月份账本一次只展开一个月；年度纪录完整展示后端精选，完整榜单正文仅预览 Top 5。查看全部时使用无宽表的全屏列表，每页 10 条，支持筛选、ESC/关闭、背景滚动锁定与焦点恢复。
- Phone 时间线只保留左侧月份编号，事件卡不重复显示序号；月份账本使用单行横向月份选择、英文月份缩写、三项月度摘要和带间距的主角列表。艺人封面统一为圆形，歌曲与专辑继续使用方形封面。
- Phone 品味维度固定为一行四项，完整榜单主切换固定为等宽两项；正文预览的完整榜单筛选不使用深色大框或外层描边，只保留轻量分隔与浅色选中态，全屏弹层继续使用紧凑胶囊。排名值使用年鉴衬线数字，单位缩小为无衬线辅助信息。正文已经写出的主指标不得再在下方重复展示。关系、纪录、品味与结语必须声明自己的移动字体层级，不能依赖浏览器默认字号；结语延续实体使用双列封面货架。
- Phone 主要操作保持至少 `44×44px`，章节导航和全屏榜单不得造成横向滚动；Phone、Compact、Desktop 三套 presentation 必须互斥挂载。

### 详情页历史语义

- 歌曲、专辑和艺人详情内部 Tab 只改变当前详情视图，使用 replace 更新查询参数，不新增浏览器历史条目。
- 左上角返回按钮与浏览器回退都应离开当前详情页，回到用户进入详情前的页面；进入来源可能是榜单页，也可能是另一个详情页。
- 详情内部切换仍须保留可分享的 `tab` URL 状态；“不增加历史”不得退化为丢失刷新恢复能力。

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
| `src/hooks/useHome.ts` | 首页聚合数据获取 + 完整过滤 query key |
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
| `src/pages/DashboardPage.tsx` | 首页薄路由容器，互斥挂载 Desktop/Phone presentation |
| `src/features/home/` | 首页两套 presentation、共享原语、加载/空/错误状态与样式 |
| `src/types/home.ts` | 首页聚合响应类型 |
| `src/pages/BillboardPage.tsx` | Billboard 周榜页面 |
| `src/types/dashboard.ts` | Dashboard 类型定义 |
| `src/types/billboard.ts` | Billboard 类型定义 |
