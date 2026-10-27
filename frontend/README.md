# SpotifyStats 前端开发说明

面向前端开发者和维护者。本文介绍当前架构、查询与交互规则；环境和协作见[开发指南](../CONTRIBUTING.md)，视觉规范见[UI风格指南](UI_STYLE_GUIDE.md)。

技术依赖以 [package.json](package.json) 为准；路径别名 `@/` 指向 `src/`。

## 快速开始

```bash
npm ci --legacy-peer-deps
npm run dev
npm test
npm run build
```

默认开发地址为 `http://localhost:5173`，API 由 Vite proxy 转发到 `http://127.0.0.1:8000`。

## 路由结构

| 路由 | 当前职责 |
|---|---|
| `/` | 个人音乐头版 |
| `/analysis/stats` | 播放统计 |
| `/analysis/charts` | 播放排行 |
| `/analysis/records` | 播放记录 |
| `/yearly-review` | 自有年度总结 |
| `/billboard` | 个人 Billboard |
| `/music/tracks/:trackId` | 歌曲详情 |
| `/music/albums/:albumName` | 专辑详情 |
| `/music/artists/:artistName` | 艺人详情 |
| `/account` | 音乐档案 |
| `/settings` | 数据、统计、元数据和系统设置 |
| `/community`、`/community/post/:postId`、`/community/account/:handle` | 社区列表、帖子与账号 |
| `/ai-insights` | AI报告与问答 |

官方 Wrapped 只保留后端兼容边界，不再作为前端消费页面。旧 Billboard 详情路径只负责兼容跳转到 `/music/*`。

播放分析二级顺序固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 音乐档案”。Phone、Compact、Desktop 共享路由状态、Query、过滤指纹和统计事实，但使用互斥 presentation。

播放分析子页面通过 URL search params 保留 `period`／`period_value`／`start`／`end`。路由容器的源码以 `src/pages/` 为入口，组件行数不作为页面用途说明。

## 目录结构

```
src/
├── api/              ← API 客户端 + TanStack QueryClient + Query Key 工厂 + OpenAPI 生成类型
├── features/         ← Feature-first 业务组件
│   ├── analysis/records/  ← PlaybackRecordsExperience + 6 Section + Primitives + Data
│   ├── billboard/
│   │   ├── number-ones/   ← NumberOnesExperience + 3 Section（tracks/albums/artists）+ Primitives + Data
│   │   ├── records/       ← 6 Section + Primitives + Data，路由按需加载各Section
│   │   └── all-time/      ← AllTimeTable + Data
│   ├── community/         ← CommunityExperience/Account + FeedToggle + TimeFilter + PostCard + PostMetrics + Timeline + Sidebar + PostDetailExperience + MobileSidebarDrawer + Skeleton + Data
│   ├── ai-insights/        ← AiInsightsExperience + ReportsPanel + ReportCard + ChatInterface + ChatComposer + ChatSessionList + ChatSessionDrawer + SuggestedQuestions + Primitives + Data
│   ├── ai-tasks/           ← AITaskProgress + AIEvidenceCards + AIToolTrace，共享 AI task 进度/证据/工具轨迹 UI
│   ├── music/details/     ← Track/Artist/Album Experience + Header/Tabs + Skeletons + 榜单/成员/归属Section
│   ├── music/search/      ← Quick Open + 完整页 + candidate/context hooks + 输入/IME 控制 + private recent
│   ├── settings/components/  ← 7 配置 Section 组件
│   ├── account-archive/      ← 音乐档案桌面/手机展示与共享查询
│   └── yearly-review/        ← 当前桌面V2年度总结；手机展示在mobile/yearly-v2/
├── components/
│   ├── ui/           ← shadcn/ui 组件（可随意修改）
│   ├── charts/       ← LazyEChart 按需 ECharts 封装 + 纯 DOM 图表
│   ├── layout/       ← AppLayout, Masthead, ThemeToggle
│   └── shared/       ← GlassCard, KpiCard, WeekSelector, CoverCell 等
├── pages/            ← 路由级页面容器（React.lazy 分包，纯组合 feature 组件）
├── hooks/            ← useHome, useBillboard, useYearlyReviewV2, useSettings, useCommunity, useAiInsights, useAiTasks
├── lib/              ← cn(), chinese, datetime, theme, navigation等共享工具
├── tests/            ← 含 phase5-architecture.test.ts 架构护栏测试
└── types/            ← 手写 TypeScript 展示类型
```

## 数据获取规则

- 所有 GET 请求使用 TanStack Query 和 `queryKeys`。
- 禁止模块级 `Map` 缓存 API 响应。
- 默认 Query 配置为 stale time 5 分钟、gc time 30 分钟、retry 2 次、refetchOnWindowFocus=false；搜索候选请求按搜索专用规则使用 `retry: 0`。
- 音乐搜索先请求候选，再按稳定实体 key 请求精确统计 context；未加载 context 不得显示为 0。
- 页面离开只取消当前 HTTP 等待，不取消服务端后台任务。

Query Key 工厂在 `@/api/query-keys.ts`，按领域 namespace：dashboard / billboard / analysis / settings / account / yearlyReview / music / library / versionMerge / community / aiInsights / aiTasks。

首页和详情不得因预取冷建完整榜单或年度报告。Desktop/Compact/Phone 年度总结进入页面后向后端一次提交全部可用年份，当前年份优先，其余年份由后端单 worker 依次生成；前端只轮询任务状态，不并发下载全部年度 artifact。等待计时以服务端 `requested_at` 为准，切年或离开路由后返回不得归零。年度总结页面不再提供官方 Wrapped 模式；`/wrapped-hub` 只保留后端兼容。

Community 列表、账号页、趋势侧栏和帖子详情必须通过 `useCommunityChartParams()` 带入当前榜单设置口径，并把这些参数放入 community query keys，避免不同 Top N、周起点、动态阈值、合并级别或精选集设置共用旧缓存。

音乐查找的候选、context、IME、防抖、取消、轮询、URL 与滚动规则统一见[音乐搜索合同](../docs/reference/music-search.md)。年度总结的内容与缓存合同见[年度总结规则](../docs/reference/yearly-review.md)。

模块级变量只允许保存UI状态（tab／排序／页码），不能缓存API响应。

## 音乐详情加载契约

- 歌曲、专辑、艺人详情首屏只并行请求实体摘要与播放统计；榜单概览、成员歌曲和成员专辑进入对应页签后再请求。
- 后端 `view=full` 保留完整响应兼容，前端消费 `summary`、`overview`、`tracks`、`albums`、`project` 等无损子视图；不得为提速抽样或重算统计事实。
- 艺人成员歌曲使用服务端分页，长周榜历史在前端分段挂载；Desktop 与 Phone 共用数据契约，但使用各自页容量。
- 当前歌曲详情保留“播放统计 / 榜单成绩”，专辑保留“播放统计 / 榜单成绩 / 单曲成绩”，艺人保留“播放统计 / 榜单成绩 / 单曲成绩 / 专辑成绩”。旧歌词、发行档案、发行周期和艺人生涯页签深链统一回到播放统计，且不得触发对应后台请求。

## 页面与组件约束

- `pages/` 只做路由容器，业务逻辑放在 `features/`。
- 新增长列表必须分页、分段、无限查询或虚拟化。
- ECharts 必须通过 `components/charts/LazyEChart.tsx` 按需加载。
- 外部 Markdown 必须通过 `react-markdown` 与 `rehype-sanitize` 渲染。
- 简繁转换使用 `displayName()` 和按需 OpenCC 子包。
- Phone 主要触控目标至少 44×44px，页面不得产生全局横向滚动。

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
- `ListeningClock`：极坐标时针式 24 小时听歌分布

## 关键约束

- 外部文本（LLM、Wikipedia、翻译）必须经 `react-markdown` + `rehype-sanitize` 渲染，禁止 `dangerouslySetInnerHTML`；AI 报告/问答正文统一复用 `features/ai-insights/AiMarkdown.tsx`，保留 GFM 表格但必须包裹横向滚动容器
- 后端 SQLite 风格时间戳（`YYYY-MM-DD HH:mm:ss`）默认视为 UTC；对话历史等相对时间显示必须通过 `lib/datetime.ts` 的 `formatRelativeTimeZh()`，避免本地时区偏移
- LLM API Key 永不对前端返回明文，通过 `POST /apply` 端点让服务端直接写入
- AI 报告页面必须 cache-first，不因打开页面或切换报告类型自动调用 LLM；无缓存时显示明确的手动生成动作；年度叙事刷新/生成请求必须带 `report_mode=visual_yearly_artifact` 与 `writer_pipeline=agent_synthesis_v2`。`editorial_agent_v1` 只允许作为兼容输入，不得作为默认消费路径。
- AI 问答和音乐详情 enrichment 的长耗时流程必须通过 `features/ai-tasks` 展示 task progress；问答完成后必须保留 assistant message `meta.evidence_cards` 并展示 evidence cards 与 tool trace
- AI comparison evidence cards 必须在 390px 移动端保持单列可读，宽屏可用双列矩阵；长专辑名、维度胜者和限制说明不得造成横向滚动或卡片内文字溢出
- 图表组件不能 SSR，必须 lazy load
- 新增页面务必参考 `UI_STYLE_GUIDE.md`
- 简繁转换用 `displayName()` 统一入口，OpenCC 按需动态 import `opencc-js/t2cn` 或 `opencc-js/cn2t`，禁止回退到默认 `opencc-js` full 包，也禁止模块初始化时根据已保存偏好 eager-load 大字典

## 验证

```bash
npm test
npm run build
node ../scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node ../scripts/frontend_cross_browser_smoke.mjs --include-detail-routes
```

真实浏览器、生产 preview 和后端 API 的入口及范围见[验证规则](../docs/reference/fullstack-verification.md#验证工具入口)。音乐查找见[搜索合同](../docs/reference/music-search.md)，年度总结见[内容与缓存规则](../docs/reference/yearly-review.md)。

Vitest + React Testing Library，`npm test` 运行组件与架构护栏，`npm run build` 验证正式构建。默认按受影响范围选择验证，不把完整全栈作为每次编辑的必经流程。

路由、交互、图表、控件、长列表、三浏览器、生产 preview 及 Web Vitals 的入口与用途集中见[验证工具入口](../docs/reference/fullstack-verification.md#验证工具入口)。preview 使用 `--api-base-url` 转发真实 API；独立 fullstack 聚合使用 `--preview-api-url`，避免仅验静态页面壳。
