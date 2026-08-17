# SpotifyStats 移动端网页 M0 设计冻结规格

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

> 状态：**M0 Frozen / M1–M2 已完成，可以进入 M3**<br>
> 日期：2026-08-05<br>
> 上位规划：[`2026-08-05-mobile-web-design-and-implementation-plan.md`](2026-08-05-mobile-web-design-and-implementation-plan.md)<br>
> 可交互原型：[`mobile-web-m0-prototype/index.html`](../../designs/mobile-web-m0-prototype/index.html)<br>
> 适用范围：手机端网页 `<768px`；768px 及以上继续使用桌面/紧凑桌面壳

## 1. 冻结结论

M0 已完成，可以开始 Mobile Shell 与移动通用组件实现。本规格冻结以下会影响全局架构的决定：

1. `<768px` 渲染独立 `MobileTopBar + MobileBottomNav`；不再把桌面 Masthead 换行后当作手机导航。
2. `768–1023px` 使用紧凑桌面壳，不显示手机 Bottom Nav；`>=1024px` 保持现有 PC 壳。
3. 移动端保留现有路由、API、TanStack Query、统计口径和过滤指纹，只拆 presentation。
4. 播放分析和 Billboard 的二级栏目进入 Bottom Sheet，不再常驻展示 5–6 个横向 Tab。
5. 音乐查找、音乐详情、Settings、社区详情属于推入层，隐藏 Bottom Nav，并提供稳定返回目标。
6. AI 报告模式显示 Bottom Nav；AI 问答进入输入态时隐藏 Bottom Nav，输入框固定在键盘上方。
7. Billboard V1 不增加一套重复的 Top 3 卡片；前三名只在统一榜单列表中强化。
8. Settings 手机 V1 只开放日常设置；导入、元数据治理、聚合重建等高级能力只显示状态和电脑端引导。

这些决定在 M1 实现期间不再重新讨论；只有真实浏览器验证证明不可行时才允许通过设计变更记录调整。

## 2. 当前移动端基线

### 2.1 证据来源

- 真实前端：`http://127.0.0.1:5173`。
- 真实本地 API：`http://127.0.0.1:8000`。
- 主基准视口：390×844。
- 基线截图：`output/playwright/mobile-m0/`，只保留在本地输出目录，不复制到正式文档资产中，避免把个人听歌数据固化进文档。
- 路由基线：`scripts/frontend_route_smoke.mjs`，移动视口、动态音乐/社区详情、console warning 严格模式。

### 2.2 路由基线结果

2026-08-05 实测 27 个移动路由组合：

- 25 个通过内容 marker、0px 页面级横向溢出、0 console error、0 console warning。
- `/billboard/records` 未在默认等待窗口内出现内容 marker，只显示 App Shell；延长等待后内容可以正常出现，说明需要在页面实施阶段治理冷加载就绪时间与骨架反馈，而不是修复横向布局。
- `/account` 页面已出现账号 Hero 和统计内容，但旧 smoke marker `你的收藏` 没有出现；属于 marker 与当前文案不一致，不是布局崩溃。
- 六个代表页面在 360、390、430、768、1280 宽度下均为 0px 页面级横向溢出。

### 2.3 当前导航高度

| 宽度 | 当前 Masthead 高度 | 结论 |
|---:|---:|---|
| 360 | 156.5px | 占用首屏过多，品牌、工具与五项导航分成三层 |
| 390 | 156.5px | 同上，是 Mobile Shell 首要改造点 |
| 430 | 111.5px | 仍是两层导航，不符合拇指导航模型 |
| 768 | 71.5px | 可作为紧凑桌面壳基线 |
| 1280 | 71.5px | 现有 PC 壳基线 |

### 2.4 六个代表页面现状

| 页面 | 当前可用基础 | 当前手机问题 | 冻结目标 |
|---|---|---|---|
| 首页 | 2×2 KPI、趋势图、单列内容已基本响应式 | 桌面杂志 Hero 过高；顶部导航占 156.5px；缺少高频快捷入口 | 一屏看到标题、四项 KPI 和主图起点 |
| 播放统计 | 数据与图表完整；无页面溢出 | “播放分析”和“播放统计”双重 Hero；8 个 KPI 连续堆叠；栏目与时间控制密集 | 四项主 KPI + 更多数据；每日/累计切换；分布聚合 |
| 播放排行 | 搜索、实体与指标切换可用 | 仍以桌面表格语义呈现，字段密度高；横向 Tab 和时间栏拥挤 | `MobileRankList`，主指标固定，完整字段进 Sheet |
| Billboard 周榜 | 周次、摘要、实体切换、榜单数据完整 | 六项子导航横滑；榜单宽表压缩后信息拥挤 | 统一移动榜单行，前三名在原列表强化 |
| 单曲详情 | Hero、固定 Tab、榜单资格语义已具备 | 仍显示完整 Masthead；推入层感弱；高级管理入口抢占标题空间 | 返回 Top Bar、无 Bottom Nav、管理入口进更多 |
| AI 问答 | 报告/问答、证据、历史抽屉能力完整 | 页面 Hero 偏大；历史浮动按钮会与 Bottom Nav 冲突；输入态未形成 100dvh 壳 | 问答占满剩余高度，历史进 Top Bar，输入框贴键盘 |

### 2.5 页面族盘点

| 页面族 | 路由 | 移动改造等级 | 说明 |
|---|---|---:|---|
| 首页 | `/` | 中 | 保留数据，重排首屏与快捷入口 |
| 播放统计 | `/analysis/stats` | 高 | KPI、图表和最近播放均需移动 presentation |
| 播放排行 | `/analysis/charts` | 高 | 桌面表格替换为移动榜单行 |
| 年度总结 | `/yearly-review` | 中 | 已是纵向长页，主要改章节导航和 Top 列表 |
| 播放记录 | `/analysis/records` | 中高 | 复用已有卡片，替换 Section Tabs 和 Mini Tables |
| 账号中心 | `/account` | 中高 | Hero、收藏/习惯和长封面列表重排 |
| Billboard 周榜 | `/billboard` | 高 | 子导航、周选择器和榜单行重做 |
| 每周榜首 | `/billboard/number-ones` | 高 | 宽表转冠军时间线 |
| Billboard 年榜 | `/billboard/year-end` | 高 | 移动年榜行、阶段提醒和荣誉卡 |
| Billboard 总榜 | `/billboard/all-time` | 很高 | 字段预设、排序 Sheet、移动行；不可压缩完整宽表 |
| Billboard 记录 | `/billboard/records` | 中高 | 记录族 Sheet + 单列 Record Cards |
| Billboard 对决 | `/billboard/versus` | 很高 | 选择队列和结果改为纵向步骤流 |
| 音乐查找 | `/music/search` | 中 | Sticky 搜索、收起 Hero、推入层导航 |
| 歌曲/专辑/艺人详情 | `/music/*` | 高 | 统一推入层、紧凑 Hero、移动子列表和时间线 |
| 社区 | `/community` | 中 | 全宽 Feed，Sidebar/趋势进 Sheet |
| 社区详情 | `/community/post/*`、`/community/account/*` | 中 | 返回 Top Bar，隐藏 Bottom Nav |
| AI | `/ai-insights` | 高 | 报告和输入态分别布局 |
| Settings | `/settings` | 很高 | 另做手机 Landing，不渲染完整治理工作台 |
| Not Found | `*` | 低 | 统一推入层错误模板 |

## 3. 设备模式与 Shell

### 3.1 断点

| 模式 | 范围 | Shell | 内容布局 |
|---|---|---|---|
| Phone | `0–767px` | Mobile Top Bar + 按路由决定 Bottom Nav | 单列；禁止页面级横向滚动 |
| Compact Desktop | `768–1023px` | 紧凑 Masthead，无 Bottom Nav | 1–2 列；选择性保留表格 |
| Desktop | `>=1024px` | 现有 Masthead | 保持当前 PC presentation |

断点判断应由统一 Hook/媒体查询负责；组件不得自行混用 `639px`、`768px` 和 `1024px` 判断 Shell。

### 3.2 Phone Shell 尺寸

| Token | 冻结值 |
|---|---|
| Top Bar 内容高度 | `56px` |
| Top Bar 实际高度 | `56px + env(safe-area-inset-top)` |
| Bottom Nav 内容高度 | `64px` |
| Bottom Nav 实际高度 | `64px + env(safe-area-inset-bottom)` |
| 页面左右 gutter | `clamp(16px, 5vw, 20px)` |
| 页面底部安全留白 | `Bottom Nav 实际高度 + 16px` |
| 标准触控目标 | 最小 `44×44px` |
| Sheet 顶部圆角 | `24px` |
| 普通卡片圆角 | `16px`；重点卡 `20px` |

### 3.3 Top Bar 三种模式

| 模式 | 左侧 | 中部/标题 | 右侧 | 适用页面 |
|---|---|---|---|---|
| Root | 品牌或区域名 | 可省略 | 搜索、设置/上下文动作 | 首页、顶级区域 |
| Section | 区域 overline | 当前栏目 | 筛选/说明 | 分析、Billboard、AI 报告 |
| Push | 返回 | 简短实体/页面名 | 分享/更多 | 搜索、音乐详情、Settings、社区详情 |

Top Bar 与页面内容不得再次完整重复同一 H1。Root 页面允许正文出现产品性标题；Section 页面正文改为数据叙事标题，而不是重复栏目名称。

### 3.4 Bottom Nav 显示规则

| 场景 | 是否显示 |
|---|---|
| 首页、播放分析各栏目、年度总结、播放记录、账号中心 | 显示 |
| Billboard 全部栏目 | 显示 |
| 社区 Feed | 显示 |
| AI 报告、AI 问答未聚焦输入框 | 显示 |
| AI 问答输入框聚焦/软键盘打开 | 隐藏 |
| 音乐查找、歌曲/专辑/艺人详情 | 隐藏 |
| 社区帖子、社区账号详情 | 隐藏 |
| Settings、Not Found、全屏图表 | 隐藏 |

## 4. 路由状态矩阵

### 4.1 正式矩阵

| 路由/模式 | Bottom Nav 归属 | Top Bar 模式与标题 | Section Switcher | 必须保留的 URL 状态 | 无 history 返回 |
|---|---|---|---|---|---|
| `/` | 首页，显示 | Root：SpotifyStats；搜索、设置 | 无 | 无 | — |
| `/analysis` | 播放分析，显示 | Section：播放分析 / 播放统计 | Analysis | 透传目标查询参数 | `/analysis/stats` |
| `/analysis/stats` | 播放分析，显示 | Section：播放统计；筛选 | Analysis | `period`、`period_value`、`start`、`end`、`metric` | `/analysis/stats` |
| `/analysis/charts` | 播放分析，显示 | Section：播放排行；筛选 | Analysis | 时间参数、`entity`、`metric`、`q`、`page` | `/analysis/charts` |
| `/yearly-review` | 播放分析，显示 | Section：年度总结；分享 | Analysis | `year`、`section` | `/analysis/stats` |
| `/analysis/records` | 播放分析，显示 | Section：播放记录；筛选 | Analysis | 时间参数、`section`、`entity`、`metric`、`page` | `/analysis/stats` |
| `/account` | 播放分析，显示 | Section：账号中心；更多 | Analysis | `tab`、列表查询/分页 | `/analysis/stats` |
| `/billboard` | 榜单，显示 | Section：个人 Billboard / 周榜；说明 | Billboard | `week`、`entity`、`merge_level`、`page` | `/billboard` |
| `/billboard/number-ones` | 榜单，显示 | Section：每周榜首；筛选 | Billboard | `year`、`entity`、`page`、完整 filter fingerprint | `/billboard` |
| `/billboard/year-end` | 榜单，显示 | Section：年榜；筛选 | Billboard | `year`、`entity`、`sort`、`page`、完整 filter fingerprint | `/billboard` |
| `/billboard/all-time` | 榜单，显示 | Section：总榜；字段/筛选 | Billboard | `entity`、`sort`、`q`、`page`；列偏好继续分实体持久化 | `/billboard` |
| `/billboard/records` | 榜单，显示 | Section：榜单记录；记录族 | Billboard | `family`、`entity`、`page`、完整 filter fingerprint | `/billboard` |
| `/billboard/versus` | 榜单，显示 | Section：对决；更多 | Billboard | `entity`、对决实体 ids、完整 filter fingerprint | `/billboard` |
| `/music/search` | 不归属，隐藏 | Push：音乐查找；关闭/返回 | 无 | `q`、`kind` | `/` |
| `/music/tracks/:trackId` | 不归属，隐藏 | Push：单曲详情；分享/更多 | 详情 Tab | `tab`、`return_to` | `/music/search` |
| `/music/albums/:albumName` | 不归属，隐藏 | Push：专辑详情；分享/更多 | 详情 Tab | `artist`、`tab`、`return_to` | `/music/search` |
| `/music/artists/:artistName` | 不归属，隐藏 | Push：艺人详情；分享/更多 | 高频 Tab + 更多 | `tab`、`return_to` | `/music/search` |
| `/community` | 社区，显示 | Root/Section：社区；搜索、趋势 | Feed 类型 | `feed`、`range`、`q`、分页 cursor | `/community` |
| `/community/post/:postId` | 社区归属，隐藏 | Push：帖子；分享/更多 | 无 | `return_to` | `/community` |
| `/community/account/:handle` | 社区归属，隐藏 | Push：`@handle`；更多 | Posts/概览 | `tab`、`page`、`return_to` | `/community` |
| `/ai-insights?mode=reports` | AI，显示 | Section：AI 洞察；历史/设置 | 报告/问答 | `mode`、`report_type`、时间范围 | `/ai-insights` |
| `/ai-insights?mode=chat` | AI，输入态隐藏 | Section：AI 问答；历史 | 报告/问答 | `mode`、`session`；问题草稿只在内存/local draft | `/ai-insights` |
| `/settings` | 不归属，隐藏 | Push：设置；返回 | Settings Landing | 日常设置子路由或 `section`、`return_to`、已有 metadata 深链 | 合法 `return_to`，否则 `/` |
| `*` | 不归属，隐藏 | Push：页面未找到 | 无 | 原始 location 仅用于诊断 | `/` |

### 4.2 返回与状态恢复契约

1. 用户从列表进入详情时，在 navigation state 写入 `returnTo`、`scrollY` 和列表状态指纹。
2. 如果用户通过深链/刷新进入详情，不依赖 `navigate(-1)`；使用矩阵中的稳定 fallback。
3. 同路径只改变查询参数时不重置页面滚动；切换实际 pathname 时默认滚到顶部。
4. Browser POP 恢复滚动；Bottom Nav 切换区域滚到该区域最近位置的能力放到 V1.1，V1 先进入默认子路由。
5. `return_to` 只能接受站内相对路径并经过 allowlist 校验，禁止开放跳转。
6. 列表搜索和字段隐藏不得改变后端给出的固定全榜排名。

## 5. 视觉系统冻结

### 5.1 方向

名称：**掌上音乐手账 / Pocket Listening Ledger**。

它延续 PC 的编辑风和液态玻璃，但不复制桌面构图：

- 大标题只在数据叙事处出现；导航标题保持紧凑。
- 暖奶油纸张作为内容底，红色作为编辑标记，蓝/金只用于榜单语义。
- 毛玻璃只用于 Top Bar、Bottom Nav、Sheet 和临时悬浮层。
- 数据卡更接近杂志信息块，不把每段内容都包成同样的白色圆角卡。
- 封面、排名数字和结论形成纵向阅读节奏。

### 5.2 颜色角色

生产实现继续使用 `frontend/src/index.css` 的现有主题变量，不新建第二套品牌色。

| 角色 | 浅色语义 | 深色语义 | 使用限制 |
|---|---|---|---|
| Background | 暖奶油纸张 | 近黑灰 | 页面主底 |
| Foreground | 深棕黑 | 暖白 | 正文和主数字 |
| Accent | 编辑红 | 暖珊瑚红 | active、主操作、关键标记 |
| Chart Blue | 蓝 | 浅蓝 | NEW、部分图表系列 |
| Chart Gold | 金 | 浅金 | RE、荣誉与冠军语义 |
| Success Green | 深绿 | 浅绿 | 上升和健康状态 |
| Border | 6% 黑 | 6–8% 白 | 结构分隔，不做高对比描边 |

颜色不得作为排名变化、错误、选中状态的唯一信息通道。

### 5.3 移动排版

| 元素 | 字体 | 字号/行高 | 规则 |
|---|---|---|---|
| 数据叙事 H1 | Playfair Display | 30–34px / 1.06 | 最多 3 行 |
| 详情实体名 | Playfair Display | 30–36px / 1.04 | 长名称换行，不截断 |
| Section H2 | Playfair Display | 22–26px / 1.12 | 卡片/章节标题 |
| KPI 数值 | Playfair Display | 28–34px / 1 | tabular 数字除外 |
| 正文 | Inter | 14px / 1.65 | 中文最小正文基线 |
| 控件/榜单名称 | Inter | 13px / 1.4 | 重要名称可 semibold |
| 次级信息 | Inter | 12px / 1.45 | 不低于 11px |
| Eyebrow | Inter | 10px / 1.2 | 大写，letter-spacing 1.4–1.8px |

原型为了在桌面工作台展示完整手机画板，内部部分文字按比例缩小；生产实现以上表为准。

### 5.4 层级与材质

| 层 | z-index 建议 | 材质 |
|---|---:|---|
| 页面内容 | 0–10 | 不透明/轻透明内容卡 |
| Sticky 页面控制 | 20 | 90% 背景 + 轻 blur |
| Top Bar / Bottom Nav | 40 | 75–85% 背景 + 16–24px blur |
| Sheet backdrop | 60 | 40% 黑 |
| Bottom Sheet / Drawer | 70 | 接近不透明 Surface |
| Toast | 90 | 高对比临时提示 |
| 全屏图表/系统级 Dialog | 100 | 独立层，隐藏全局导航 |

## 6. 组件状态规范

| 组件 | 默认 | Active/Selected | Loading | Empty/Error | Disabled/Focus |
|---|---|---|---|---|---|
| `MobileTopBar` | 当前标题 + 0–2 个动作 | 无 | 标题保留，不闪烁整栏 | 错误页仍显示返回 | 动作 44px；focus ring 清晰 |
| `MobileBottomNav` | 五项等宽 | 背景 tint + 图标/文字同时变化 | 不受页面加载影响 | 路由错误时隐藏 | 每项最小 48px；`aria-current=page` |
| `MobileSectionSwitcher` | Trigger 显示当前栏目 | 当前项勾选 | Sheet 内骨架不超过 5 行 | 无栏目时不渲染 Trigger | Escape、焦点回收、滚动锁定 |
| `MobileFilterSheet` | 显示已应用摘要 | Active chips 可移除 | 应用按钮进入忙碌态 | 验证错误留在对应组 | Disabled 不可 tab；按钮 44px |
| `MobileRankList` | 主指标 + 最多 2 个次级事实 | 行按下轻微 tint | 5 行骨架 | 提供清除搜索/重试 | 整行可点并有独立可访问名称 |
| `MobileEntityDetailSheet` | 完整字段和详情入口 | 当前实体标题固定 | 只加载额外字段 | 保留基本实体信息 | 焦点从关闭按钮开始 |
| `MobileChartCard` | 1–2 系列、结论、点击 tooltip | 当前系列突出 | 固定高度骨架 | 文案解释无数据原因 | 全屏关闭 44px；reduced motion |
| `MobilePagination` | 上一页/页码/下一页或加载更多 | 当前页不可点击 | 按钮内 spinner | 到底给出结束提示 | 不使用无标签纯图标四按钮 |
| `MobileStatePanel` | 图标、标题、说明、主操作 | — | 一屏内骨架 | 不泄漏 Provider 原始错误 | 主操作在首个 Tab stop |
| `ChatComposer` | 贴底且不遮消息 | 聚焦后隐藏 Bottom Nav | 发送按钮忙碌 | 失败保留草稿并允许重试 | 适配 visualViewport 和 safe area |

## 7. 六个代表页面设计签字

可交互原型位于 [`mobile-web-m0-prototype/index.html`](../../designs/mobile-web-m0-prototype/index.html)。六个画板不是独立产品分支，而是以下通用结构的样板。

### 7.1 首页

- Root Top Bar：品牌、搜索、设置。
- 紧凑 Hero：时间范围 + 一句可验证的变化描述。
- 2×2 主 KPI；趋势图进入首屏下半部。
- 快捷入口连接播放排行和周榜。
- Bottom Nav 常驻并高亮首页。

### 7.2 播放统计

- Section Top Bar 不再重复大标题。
- 栏目与时间分别打开 Sheet。
- 只展示四项主 KPI；其余数据进入“更多数据”。
- 每日/累计共用一个图表卡；时钟/星期/月度/年度共用一个分布卡。

### 7.3 播放排行

- 实体分段器、搜索和主指标在同一控制区，但不塞在同一行。
- 移动行保留排名、封面、名称、艺人、主指标和一个比例条。
- 完整日期、占比、日均等字段通过实体详情 Sheet 查看。
- 搜索和分页不得重新编号。

### 7.4 Billboard 周榜

- 栏目与周次都用 Sheet。
- 周摘要为四项紧凑数字。
- Top 1/2/3 可用背景、封面和数字层级强化，但仍位于同一列表，禁止重复。
- `NEW`、`RE`、上升下降同时使用文字/箭头和颜色。

### 7.5 音乐详情

- Push Top Bar：返回、实体类型、更多。
- 隐藏 Bottom Nav。
- Hero 先展示封面和实体身份，再展示有效播放与实体自身榜单成绩。
- 固定 Tab 不因榜单为空而隐藏；高级治理入口进入更多菜单。

### 7.6 AI 问答

- 历史入口移到 Top Bar，移除右下角浮动按钮。
- 回答、证据和建议追问形成单列消息流。
- 输入框固定在 visual viewport 底部；输入态隐藏 Bottom Nav。
- 证据卡、时间解释和工具轨迹不能因移动布局被删除。

## 8. Settings 手机 V1 边界

### 8.1 手机上可编辑

- 白日/夜间主题、简繁体、个人榜单名称显示。
- 有效播放阈值、动态阈值、连续播放合并间隔。
- Billboard Top N、周起点、是否包含精选集。
- Spotify 连接状态、连接/断开、轻量同步状态。
- LLM 开关和已有 Profile 选择。

### 8.2 手机上只读并提示电脑端

- Streaming History / Account 文件导入。
- 归并与版本工作区。
- 曲目署名、艺人身份、流派与语言审核。
- LLM 密钥和完整 Profile 编辑。
- 聚合重建、缓存清理和其他高风险操作。

手机深链到这些模块时必须保留目标、实体、`return_to` 和 anchor，显示状态摘要与电脑端提示，不能静默重定向到 Settings 首页。

## 9. 运行前提与外部阻塞项

本规格只冻结移动网页 UI。以下事项不属于 M1/M2，但决定手机是否能在开发机之外长期使用：

1. 当前产品仍是 local-first FastAPI + React 应用。
2. 同一局域网、ngrok 或受控 tunnel 可以用于移动验收，但不能直接等同正式部署。
3. 公开远程访问前必须另行设计 HTTPS、认证、会话、CSRF/CORS、数据文件权限、备份和更新策略。
4. PWA、Capacitor、原生 App 和微信小程序继续保持在本阶段范围外。
5. Spotify OAuth 的正式手机回跳需单独做真实设备验收。

因此，“移动端 UI 完成”和“可公开访问的移动产品上线”是两个不同里程碑。

## 10. M1 原子实施任务

| ID | 状态 | 任务 | 主要文件 | 验收 |
|---|---|---|---|---|
| M1-01 | 完成 | 建立统一设备模式 Hook | 新增 `frontend/src/hooks/useViewportMode.ts` | 767/768 边界测试；SSR/测试环境有稳定默认值 |
| M1-02 | 完成 | 扩展 route context 数据结构 | `components/layout/routeContext.ts` | 覆盖矩阵全部 route pattern、Top Bar、Bottom Nav、fallback |
| M1-03 | 完成 | AppLayout 按模式只挂载一种 Shell | `AppLayout.tsx` | Phone 不挂 Masthead；Desktop 不挂 Mobile Shell |
| M1-04 | 完成 | 固化 Desktop Masthead 回归边界 | `Masthead.tsx` | 768/1280 与当前导航命名、顺序和动作一致 |
| M1-05 | 完成 | 实现 `MobileTopBar` | 新增 layout component | Root/Section/Push 三模式；动作数不超过 2 |
| M1-06 | 完成 | 实现 `MobileBottomNav` | 新增 layout component | 五项、active 归属、显示/隐藏矩阵、safe area |
| M1-07 | 完成 | 建立 Mobile Shell tokens | `index.css` | top/bottom safe area、gutter、content padding、z-index |
| M1-08 | 完成 | 实现 Analysis/Billboard Section Switcher | 新增 `MobileSectionSwitcher.tsx` | 顺序固定、导航后关闭、焦点回收、URL 透传 |
| M1-09 | 完成 | 实现稳定返回 helper | 新增 `lib/mobile-navigation.ts` | history、合法 return_to、fallback 三层顺序 |
| M1-10 | 完成 | 处理浮动按钮冲突 | Community、AI 相关组件 | Phone 下不再出现与 Bottom Nav 重叠的 FAB |
| M1-11 | 完成 | 补 Shell 组件与纯函数测试 | `src/tests/mobile-shell*.test.*` | 路由矩阵、a11y、Escape、断点全部覆盖 |
| M1-12 | 完成 | 扩展浏览器 smoke | `scripts/frontend_route_smoke.mjs` 等 | 390px 能识别 Mobile Shell；1280px 识别 Desktop Shell |

### M1 合并顺序

```text
M1-01 → M1-02 → M1-03
                  ├─ M1-04
                  ├─ M1-05 → M1-06 → M1-07
                  ├─ M1-08 → M1-09
                  └─ M1-10
全部完成 → M1-11 → M1-12
```

### M1 退出门禁

- 360/390/430 显示 Mobile Shell，768/1280 显示 Desktop Shell。
- 全部主路由可通过 Bottom Nav + Section Switcher 到达。
- Push 页面返回与 fallback 正确。
- 页面级横向溢出、console error/warning、无障碍命名违规均为 0。
- PC Masthead 导航命名、顺序和路由归属不回退。

## 11. M2 原子实施任务

| ID | 任务 | 建议位置 | 验收 |
|---|---|---|---|
| M2-01 | `MobilePageHeader` | `components/mobile/` | Root/Section 内容头；不重复 Top Bar 标题 |
| M2-02 | `MobileBottomSheet` 基础层 | `components/mobile/` | focus trap、Escape、滚动锁定、焦点回收 |
| M2-03 | `MobileFilterSheet` | `components/mobile/` | draft/apply/reset 一致；关闭不丢已应用 URL 状态 |
| M2-04 | `MobileTimeRangeSheet` | `components/mobile/` | 全部/近 6 月/近 4 周/年/月/周/日/自定义完整 |
| M2-05 | `MobileEntityRow` | `components/mobile/` | 三类实体、长名称、缺封面、多个 credited artists |
| M2-06 | `MobileRankList` | `components/mobile/` | 固定排名、主指标、次级指标、分页/加载更多 |
| M2-07 | `MobileEntityDetailSheet` | `components/mobile/` | 完整字段、详情链接、分享和范围说明 |
| M2-08 | `MobileChartCard` | `components/mobile/` | 点击 tooltip、系列切换、结论、reduced motion |
| M2-09 | 全屏图表容器 | `components/mobile/` | 隐藏全局导航、明确关闭、方向变化稳定 |
| M2-10 | 移动分页组件 | `components/mobile/` | 非纯图标四按钮；44px 触控；列表结束状态 |
| M2-11 | 统一状态模板 | `components/mobile/` | Loading/Empty/Error/Config Missing 四类 |
| M2-12 | 组件测试与主题视觉检查 | `src/tests/mobile-primitives*.test.*` | 键盘、焦点、触控、亮/暗主题、长文本 |

### M2 设计约束

- `components/mobile/` 只承载通用 presentation，不发请求、不重新计算统计值。
- 页面/feature 层负责组装已有 query data 和 row model。
- Desktop 与 Mobile presentation 不能同时挂载重图表或长列表。
- 新增组件必须允许在 360px 下显示 20 个中文字符或 36 个拉丁字符的长名称。

## 12. M0 验收记录

| 项目 | 状态 | 产物/证据 |
|---|---|---|
| 六个当前页面 390px 截图 | 完成 | `output/playwright/mobile-m0/*-current-390.png` |
| 360/390/430/768/1280 导航与溢出基线 | 完成 | 本文 2.2–2.3；六页均 0px overflow |
| Settings 手机边界 | 完成 | 本文第 8 节 |
| 音乐详情 Bottom Nav 决策 | 完成 | 隐藏，使用 Push Top Bar |
| Billboard Top 3 决策 | 完成 | 不重复；在统一列表强化 |
| UI tokens 与组件命名 | 完成 | 本文第 3、5、6 节 |
| 路由状态矩阵 | 完成 | 本文第 4 节 |
| 六屏视觉方向 | 完成 | `mobile-web-m0-prototype/` |
| M1/M2 原子任务 | 完成 | 本文第 10–11 节 |
| 无 Shell 架构级未决项 | 完成 | 本文第 1 节冻结结论 |

## 13. M1–M2 验收与下一实施动作

M1 已于 2026-08-05 完成，完整证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../../reports/2026-08-06-mobile-web-and-pwa-delivery.md)：Phase 5 最低矩阵通过，54 个 desktop/mobile 路由组合最终通过，19 个移动路由共 772 个控件为 0 violation。

M2 也已于 2026-08-05 完成，完整证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../../reports/2026-08-06-mobile-web-and-pwa-delivery.md)：11 类通用移动组件全部落地，栏目切换器迁移到统一 Bottom Sheet，50 个前端测试文件共 406 个用例通过，360px 明暗主题与横屏全屏图表通过真实浏览器验收。

下一步进入 M3。以首页、播放统计、播放排行和 Billboard 周榜为首批真实页面样板，接入 M2 组件但继续复用原查询数据、URL 状态和过滤指纹；一种音乐详情页随 M5 统一改造，M3 不提前复制详情业务逻辑。
