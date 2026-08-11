# SpotifyStats 移动端网页完整设计与实施规划

> 创建日期：2026-08-05<br>
> 状态：M0–M7 已完成；移动网页进入可发布候选状态，物理 iOS/Android 仅保留上线前现场复核<br>
> 适用范围：`frontend/` 移动端网页体验；必要时包含少量 API 输出适配，但不改变统计口径<br>
> 目标设备：手机浏览器与后续 PWA/Capacitor 容器<br>
> 主要断点：`<768px` 手机、`768–1023px` 平板、`>=1024px` PC<br>
> 取代关系：本计划取代 `docs/archive/04-ai-agent-harness/2026-06-28-mobile-navigation-orientation.md` 作为现行移动端产品设计；旧文档保留为历史增量方案，不删除<br>
> 关联文档：`frontend/UI_STYLE_GUIDE.md`、`docs/reports/2026-06-19-fullstack-verification.md`、`docs/reference/playback-stats-rules.md`、`docs/reference/music-metadata-management.md`

## 0. 执行摘要

SpotifyStats 已经具备 390px 无页面级横向溢出、响应式断点、长列表分页、跨浏览器 smoke 和 Web Vitals 门禁，但当前手机体验主要仍是“把 PC 页面压缩到窄屏”：顶部 Masthead 横向滚动、二级 Tab 横向滚动、宽表横向滚动、复杂筛选器原样换行。

本阶段的目标不是建立第二套网站，也不是追求手机和 PC 像素级一致，而是：

> 在不分叉数据语义、路由与 API 契约的前提下，为手机建立独立的信息架构、导航壳、触控交互和信息密度；PC 继续承担高密度分析与数据治理，手机聚焦查看、探索、问答和分享。

推荐最终形态：

- 同一套 React Router 路由、TanStack Query、API 类型和业务状态。
- PC 使用现有顶部 Masthead、多栏布局、宽表和内联工具栏。
- 手机使用紧凑顶部栏、五项底部导航、Bottom Sheet、卡片榜单和单列图表。
- 普通网格优先使用 CSS 自适应；表格、导航、复杂筛选等结构差异显著的区域使用独立 Desktop/Mobile presentation。
- 手机端完整覆盖所有消费页面；复杂导入与元数据治理保留 PC 主流程，手机只显示状态、日常设置和明确的桌面端引导。
- 第一批先完成全局壳、首页、播放统计、播放排行、Billboard 周榜和音乐详情，以验证整套移动设计语言，再扩展到其他页面。

## 1. 背景与当前基线

### 1.1 当前已有能力

- React 19 + React Router + Tailwind CSS + TanStack Query，可复用现有前端业务层。
- `useIsMobile()` 已以 `<768px` 判断窄屏，可作为统一手机结构切换入口。
- 主路由与动态详情路由已有 390px route smoke、控件库存、跨浏览器和横向溢出检查。
- 长列表已有分页或分段渲染基线。
- ECharts 已按需加载，适合继续做移动图表简化和全屏查看。
- 音乐详情、社区、AI 对话已经存在部分窄屏抽屉和响应式实现。

### 1.2 当前问题

| 问题 | 当前表现 | 移动端影响 |
|---|---|---|
| 顶级导航仍是 PC 结构 | Masthead 在手机换行后横向滚动 | 占据两行高度，操作不像手机 App |
| 二级导航过多 | 播放分析 5 项、Billboard 6 项横向 Tab | 用户难以判断当前位置，入口易被滚出视口 |
| 筛选器平铺 | 时间范围、实体、指标、字段选择同时展示 | 首屏被控件占满，正文被推到下方 |
| 宽表依赖横向滚动 | 排行、总榜、最近播放、记录表格 | 阅读顺序和触控操作困难 |
| 页面 Hero 过大 | 44–56px 标题、长副标题、较大上边距 | 一屏只能看到标题，看不到数据 |
| 浮动按钮冲突 | 社区侧栏、AI 历史均位于右下角 | 会与未来底部导航和 safe area 冲突 |
| Settings 全量下放 | 一页包含导入、归并、署名、身份、流派语言、LLM | 手机上会形成极长且高风险的管理页面 |
| 响应式边界不统一 | Masthead 使用 639px，其他模块使用 768/1024px | 640–767px 之间出现混合界面 |

### 1.3 本阶段不改变的内容

- 不改变播放统计、Billboard、album project、有效署名、genre/language 等业务语义。
- 不创建 `/m/*` 或独立手机版路由。
- 不复制后端 API。
- 不恢复年度总结、账号中心为独立顶级导航。
- 不把来源、证据、置信度、审核等治理术语带入普通消费页面。
- 不在本阶段引入 PWA、Capacitor 或微信小程序构建；但设计必须为后续容器化预留 safe area、深链和触控结构。

## 2. 产品定位与能力边界

### 2.1 手机端定位

手机端定位为：

> 随时查看个人音乐数据、浏览榜单与详情、阅读年度故事、使用 AI 问答和分享结果的个人音乐数据伴侣。

手机的高频任务：

1. 快速查看最近和当前阶段的听歌状态。
2. 查看歌曲、专辑、艺人排行与个人 Billboard。
3. 搜索音乐实体并打开详情。
4. 阅读年度总结和记录高光。
5. 浏览社区信息流。
6. 向 AI 提问或查看报告。
7. 调整少量日常统计与显示偏好。

### 2.2 PC 端定位

PC 保留：

- 高密度多列比较。
- 自定义字段和列宽。
- 大范围筛选与多图并列。
- 数据文件导入。
- 音乐版本归并、曲目署名、艺人身份、流派与语言审核。
- LLM Profile、缓存和聚合重建等管理操作。

### 2.3 手机能力分级

| 能力 | 手机 V1 | 后续可扩展 | PC 保留 |
|---|---:|---:|---:|
| 首页、统计、排行、记录 | 完整 | — | 完整 |
| 年度总结 | 完整阅读与分享 | Story 分享模式 | 完整 |
| Billboard 全系列 | 完整阅读 | 高级字段自定义增强 | 完整 |
| 音乐搜索与详情 | 完整 | 系统分享、深链 | 完整 |
| 社区与 AI | 完整 | 通知、系统分享 | 完整 |
| 主题、名称、过滤、Billboard 参数 | 可编辑 | — | 可编辑 |
| Spotify 状态与同步 | 可查看、可同步 | OAuth 移动回跳 | 完整 |
| 文件导入 | 状态与桌面提示 | 文件选择上传需单独设计 | 完整 |
| 元数据治理 | 只读摘要和桌面提示 | 独立移动工作流 | 完整 |
| LLM 密钥/Profile 管理 | 当前状态 | 安全凭据管理后再开放 | 完整 |

## 3. 设计原则

### 3.1 数据同源，呈现分层

- 页面 Route Container 负责查询、URL 状态、排序和分页。
- Desktop/Mobile presentation 只负责布局和交互表达。
- 同一个指标在两端必须使用同一个字段、同一个格式化器和同一个详情链接。
- 手机隐藏次级字段不代表删除数据；点击行或“更多指标”可以继续查看。

### 3.2 先结论，再解释

手机页面的阅读顺序固定为：

1. 当前页面和范围。
2. 最重要的 1–4 个结论。
3. 主榜单或主图。
4. 次级解释、完整字段和口径说明。

### 3.3 一屏一个主要任务

- 每个手机首屏最多保留一个主标题、一个上下文选择器、一组主内容。
- 不在首屏同时放栏目导航、时间范围、实体切换、指标切换、搜索、字段设置和分页。
- 低频控制进入 Bottom Sheet 或“更多”。

### 3.4 横向滚动必须是有意设计

允许横向滚动：

- 年份 Chip。
- 少量榜单摘要卡。
- 年度总结章节目录。
- 2–4 个对决实体。

禁止把横向滚动作为以下内容的默认补救：

- 主导航。
- 宽表。
- 表单。
- 长段正文。
- 关键操作按钮。

### 3.5 触控优先，不依赖 hover

- 所有 hover 才出现的删除、菜单、详情操作，在手机上必须常驻或通过明确的“更多”按钮提供。
- 可触控目标至少 44×44 CSS px；相邻目标保留足够间隔。
- 拖动列宽、鼠标悬停 tooltip 等桌面能力，手机改为点击、长按或全屏查看。

### 3.6 消费与治理分层

- 消费页面只展示结果，不展示 source/evidence/confidence/review 等治理术语。
- 音乐详情的“管理”入口在手机进入更多菜单，并提示复杂操作使用 PC。
- Settings 的高级治理不通过简单 `display: none` 隐藏，而要提供状态、解释和可发现的桌面端入口。

## 4. 设备模式与布局基线

### 4.1 断点

| 模式 | 宽度 | 主要布局 |
|---|---:|---|
| Phone | 0–767px | Mobile Shell、单列、底部导航、Bottom Sheet |
| Tablet | 768–1023px | 紧凑顶部导航、1–2 栏、可保留部分表格 |
| Desktop | >=1024px | 当前 Masthead、多栏、侧栏、完整宽表 |

要求：

- `useIsMobile()`、CSS `md:`、Masthead 和移动抽屉统一采用 768px 边界。
- 结构分流以 `useIsMobile()` 或等价 `useMediaQuery` 为准。
- 纯排列变化优先使用 CSS，不引入不必要的 JS 分支。

### 4.2 手机页面尺寸

| 项目 | 建议值 |
|---|---|
| 页面左右边距 | 16px |
| 页面顶部内容间距 | 16–20px |
| Section 间距 | 24–32px |
| 卡片间距 | 12–16px |
| 卡片圆角 | 12–16px |
| 主标题 | 28–34px |
| Section 标题 | 20–24px |
| 正文 | 14–16px |
| 辅助信息 | 11–13px |
| 顶部栏高度 | 52–56px + `env(safe-area-inset-top)` |
| 底部导航高度 | 56–64px + `env(safe-area-inset-bottom)` |

### 4.3 Safe area 与可视高度

- 页面容器使用 `padding-top: env(safe-area-inset-top)` 或由顶部栏统一承担。
- 底部内容使用 `padding-bottom: calc(var(--mobile-nav-height) + env(safe-area-inset-bottom) + 16px)`。
- 聊天、抽屉和全屏图表使用 `100dvh`，不使用固定 `100vh`。
- 键盘打开时，聊天输入区随 visual viewport 调整，不被底部导航遮挡。

## 5. 移动端视觉系统

### 5.1 品牌延续

保留：

- Playfair Display + Inter 的编辑式组合。
- 日/夜双主题。
- 暖色强调色。
- 封面图和个人音乐数据叙事。

调整：

- Playfair 仅用于页面主标题、重点数字或年度叙事标题。
- 手机不重复 PC 的大面积空白和 48–56px Hero。
- 液态玻璃主要用于导航层、临时控制层和 Bottom Sheet，不铺满所有内容卡片。
- 数据内容层优先使用稳定背景、细边框和更清晰的文字层级。

### 5.2 内容卡片类型

| 组件 | 使用场景 | 手机特征 |
|---|---|---|
| Summary Card | 首页、统计、荣誉 | 一条结论 + 1–2 个次级值 |
| Entity Row | 排行、详情成员、搜索结果 | 排名/封面/名称/主值/状态 |
| Record Card | 播放记录、榜单记录 | 纪录标题 + Top 1/Top 3 + 展开 |
| Chart Card | 趋势、分布、时钟 | 主结论、简图、全屏入口 |
| Story Section | 年度总结、艺人生涯 | 标题、叙事、图表或实体列表 |
| Status Card | 设置、任务、导入 | 状态、最后更新时间、主操作 |

### 5.3 动效

- 页面切换不做重动画；只使用 150–250ms 淡入或轻微位移。
- Bottom Sheet 使用系统式上滑和遮罩。
- 排行变化可使用轻微数字/条形过渡，不播放连续复杂动画。
- 遵守 `prefers-reduced-motion`。

## 6. 全局信息架构与导航

### 6.1 顶级区域

移动底部导航固定五项，使用现有产品命名：

| 标签 | 路由归属 | 图标建议 |
|---|---|---|
| 首页 | `/` | Home |
| 播放分析 | `/analysis/*`、`/yearly-review`、`/account` | Activity/Chart |
| 榜单 | `/billboard/*` | Trophy |
| 社区 | `/community/*` | Users/Message |
| AI | `/ai-insights` | Sparkles |

搜索和设置属于全局动作，不占底部导航。

### 6.2 Mobile Top Bar

三种状态：

1. **顶级页面**：品牌或当前区域标题 + 搜索 + 设置。
2. **区域子页面**：当前页面标题 + 栏目切换 + 搜索/更多。
3. **推入式详情**：返回 + 简短标题 + 分享/更多。

禁止：

- 顶部栏和页面 Hero 同时重复显示完整页面名称。
- 在音乐详情再添加第二套 `当前位置` 面包屑。
- 在 Top Bar 放超过三个动作。

### 6.3 Mobile Bottom Nav

- 仅用于顶级区域切换，不承载动作。
- `/analysis/*`、`/yearly-review`、`/account` 均高亮“播放分析”。
- `/billboard/*` 高亮“榜单”。
- `/community/post/*`、`/community/account/*` 高亮“社区”。
- 音乐详情、设置、全屏图表视为推入层，可以隐藏 Bottom Nav。
- AI 问答进入输入态后可以隐藏 Bottom Nav，退出输入态恢复。

### 6.4 播放分析二级导航

顺序固定，不得改变：

1. 播放统计
2. 播放排行
3. 年度总结
4. 播放记录
5. 账号中心

PC 保持现有横向 Tab。手机显示：

```text
播放分析
[ 播放统计  v ]     [ 全部时间  v ]
```

栏目按钮打开 `MobileSectionSwitcher`，时间按钮打开 `MobileTimeRangeSheet`。

### 6.5 Billboard 二级导航

顺序保持现状：

1. 周榜
2. 每周榜首
3. 年榜
4. 总榜
5. 榜单记录
6. 对决

手机不展示六项横向 Tab，使用：

```text
个人 Billboard
[ 周榜  v ]
```

### 6.6 URL 与返回行为

- 现有 URL、查询参数和可分享性全部保留。
- 栏目、年份、实体、指标、时间范围继续优先存 URL，不放到仅内存状态。
- 详情页优先返回触发来源；无有效 history 时返回稳定父级页面。
- 浏览器后退必须恢复列表滚动位置、搜索词、筛选和分页。
- Bottom Nav 切换顶级区域时，后续可缓存每个区域最后访问的子路由；V1 可先回默认路由。

## 7. 通用交互组件设计

### 7.1 MobileSectionSwitcher

用途：播放分析和 Billboard 的二级栏目切换。

- Trigger 显示当前栏目和下拉箭头。
- Sheet 内显示栏目名称、简短说明和当前状态。
- 当前项有 `aria-current`。
- 点击后导航并关闭 Sheet。
- 支持键盘、Escape、焦点回收和背景滚动锁定。

### 7.2 MobileFilterSheet

用途：时间范围、排序、字段、年份、实体筛选。

- 页面只显示筛选摘要和 active filter chips。
- Sheet 内分组显示所有低频控制。
- 底部固定“重置”和“应用”。
- 立即生效类控制可不显示“应用”，但同一 Sheet 内行为必须一致。
- 关闭 Sheet 不应丢失已应用 URL 状态。

### 7.3 MobileRankList

替代移动宽表，行结构固定为：

```text
01  [cover]  Entity name                 168 次
             Artist / secondary text    #3 · 11 周
             [optional value bar or movement badge]
```

- 主排名和实体名称固定可见。
- 主指标始终右对齐并使用 tabular nums。
- 最多显示两个次级指标。
- 点击行进入详情或打开指标详情 Sheet。
- 分页使用“上一页 / 当前页 / 下一页”或加载更多，不使用四个紧凑纯图标按钮。

### 7.4 MobileEntityDetailSheet

用于展示被移动榜单隐藏的完整字段：

- 实体封面、名称、艺人。
- 全部统计字段。
- 打开详情页。
- 分享。
- 与当前榜单或时间范围有关的说明。

### 7.5 MobileChartCard

- 卡片顶部给出标题和一句可验证结论。
- 默认只显示 1–2 个系列。
- tooltip 通过点击触发，不依赖 hover。
- 图例过多时改为分段器或 Sheet。
- 支持“全屏查看”，全屏时隐藏全局导航并提供明确关闭按钮。
- 长时间序列可以使用 dataZoom，但触控拖动区不得与页面横滑冲突。

### 7.6 MobilePageHeader

- 手机主标题 28–34px。
- Eyebrow 可保留，但减少上下间距。
- 描述最多显示 2–3 行，长说明进入帮助 Sheet。
- 页面操作最多保留一个主要按钮和一个更多菜单。

### 7.7 状态页面

加载、空、错误、权限/配置缺失使用统一移动模板：

- 不显示超过一屏的骨架。
- 主信息居中但保留顶部栏。
- 提供一个主操作和可选次操作。
- 错误文案不泄漏 Provider 原始错误。

## 8. 逐页面移动端设计

## 8.1 首页 `/`

### 目标

在一屏内回答“最近听得怎么样”和“下一步可以看什么”。

### 手机内容顺序

1. 紧凑标题：`你的聆听概览`，附当前数据范围。
2. 2×2 核心 KPI：播放次数、播放时长、独特歌曲、覆盖艺人。
3. 月度播放趋势主图。
4. 当前最高峰/最近变化洞察卡。
5. 平台分布和聆听高峰两个小卡。
6. 快捷入口：播放排行、年度总结、音乐查找。
7. 可选：最近播放 3 条。

### 与 PC 的区别

- PC 保留“聆听的形状与轨迹”杂志 Hero；手机改为紧凑数据首页。
- PC 并排趋势与右侧卡；手机单列排序。
- 手机不显示未经后端支持的趋势文案；比较值必须来自真实字段。

### 完成条件

- 390px 首屏能看到标题、4 个 KPI 和主图开头。
- 无横向滚动。
- 首页底部导航高亮正确。

## 8.2 播放统计 `/analysis/stats`

### 手机内容顺序

1. Mobile Analysis Header：栏目 + 时间范围。
2. 播放次数/播放时长分段器。
3. 四项主 KPI。
4. “更多数据”折叠区：日均、独特专辑、独特艺人等。
5. 每日播放主图。
6. 累计播放作为同卡第二视图。
7. 听歌时钟。
8. 星期/月度/年度分布在一个卡片内分段切换。
9. 最近播放移动列表。

### 结构调整

- 八项 KPI 不同时平铺。
- 每日和累计不同时占用两个大卡。
- 最近播放由宽表转为 `MobileEntityRow`。
- 时间范围不与二级导航同一行塞满。

### 完成条件

- 切换指标、时间范围后 URL 和 API 参数保持现有语义。
- 日/累计视图切换不重复请求。
- 最近播放搜索、日期筛选、分页可用。

## 8.3 播放排行 `/analysis/charts`

### 手机头部

```text
[歌曲 | 专辑 | 艺人]   [次数 | 时长]
[搜索当前榜单________________]
```

### 列表行

- 排名。
- 封面或艺人头像。
- 名称与次级实体。
- 主指标。
- 一个比例条或两个次级指标。
- 点击展开完整字段或进入详情。

### PC/Mobile 分层

- PC：保留 `PersonalRankTable`。
- Mobile：新增 `PersonalRankList`。
- 搜索、分页、entity、metric、API rows 共用。

### 完成条件

- 歌曲/专辑/艺人链接正确。
- 当前搜索、分页和排序不会改变原始全榜排名。
- 不渲染 784px 宽表。

## 8.4 年度总结 `/yearly-review`

### 手机结构

1. 年份选择器。
2. 年度 Hero + 4 项年度数字。
3. Sticky 章节目录。
4. 年度最爱。
5. 时间故事。
6. 曲风与语言。
7. 发现与回归。
8. 收听深度。
9. 听歌人格。
10. 年度对比。
11. 分享入口。

### 调整规则

- 仍以纵向长页为主，不强制变成逐页 Story。
- 章节目录允许横向滚动，但必须突出当前章节。
- Top 曲目/艺人/专辑由三栏改为封面列表或双列卡。
- 月历、时钟、月份趋势必须提供移动简版。
- `genre`、`scene`、language 仍按现有消费 taxonomy 独立展示，不泄漏治理术语。
- 分享卡可另做 9:16/4:5 模式，不改变正文。

### 完成条件

- 章节跳转、年份切换和分享截图可用。
- 长页面滚动不会被 Sticky 目录和 Bottom Nav 遮挡。
- 年中年份继续明确阶段性口径。

## 8.5 播放记录 `/analysis/records`

### 手机结构

1. 顶部横向滑动栏目条，默认“高光时刻”，栏目状态写入 `family` 查询参数。
2. 当前栏目 Record Cards；不重复显示栏目标题和介绍文案。
3. 每张卡默认 Top 3，完整榜单通过共享移动榜单 Sheet 查看并分段加载。
4. 全局时间范围使用右下角悬浮触发器，打开与播放统计相同的时间范围 Sheet。

### 五个栏目

- 高光时刻。
- 个人王朝。
- 长线陪伴。
- 时间习惯。
- 探索与品味。

### 调整规则

- 五个栏目使用单行横向滑动 Tab；不得恢复重复页面 H1、栏目标题或栏目说明。
- `MiniRankTable` 手机统一经 `MobileRecordTable` 渲染纵向排名行，Billboard 记录与播放记录不得维护两套展开逻辑。
- 歌曲/专辑/艺人切换保留紧凑三段分段器；与播放次数/听歌时长切换同排时，控件可见高度和 44px 触控目标必须一致。
- 日期、月份、年份和小时值使用紧凑 tabular-nums；决定排名的指标优先显示，重复的“连续次数”等可见前缀在手机卡片中省略，但保留桌面表头和 accessible name。
- 单日总量记录继续沿用现有响应式卡片方向。

### 完成条件

- 记录语义、实体切换和当前数据不变。
- Top 3 与完整榜单排序一致。
- 每个 Section 首屏不超过一个大表等价内容。
- 360/390/430px 无横向溢出，栏目、实体与统计口径切换均可单手触达。

## 8.6 账号中心 `/account`

### 手机结构

1. 紧凑个人 Hero：头像、名称、地区、人格。
2. 2×2 账号摘要。
3. 收藏/习惯分段器。
4. 收藏概览、生命周期、收藏榜单。
5. 歌曲/歌单浏览器。
6. 搜索、粉丝层级、播客、视频等折叠卡。

### 调整规则

- 头像由侧边布局改为居中或紧凑横排。
- 长封面列表使用 2 列网格或移动行。
- 表格中次要专辑列可以隐藏，但通过详情可见。
- 未导入账号数据时提示到 PC Settings 完成导入。

### 完成条件

- 收藏和习惯两个 Tab 状态稳定。
- 长列表分页/分段渲染继续有效。
- 空状态不把用户引导到手机不可完成的复杂导入表单。

## 8.7 Billboard 周榜 `/billboard`

### 手机头部

```text
个人 Billboard
[ 周榜  v ]        [ 本周  v ]
[ 歌曲 | 专辑 | 艺人 ]
```

### 手机内容

1. 周摘要：总播放、新上榜、回榜、最高播放。
2. 可选 Top 3 强化区。
3. 第 1/4 名起的统一 Chart Row 列表。
4. 加载更多或分页。

### Chart Row 字段

- 当前排名。
- 封面/头像。
- 名称、艺人。
- 播放次数。
- 新上榜/回榜/上升下降。
- 最高排名、在榜周数。

### 调整规则

- 周选择器进入年份/周次 Sheet。
- 走势 badge 必须兼顾颜色和文字/图标，不只靠颜色。
- 点击行进入既有音乐详情路由。
- 保留完整 Billboard filter fingerprint，不另做简化 API 口径。

### 完成条件

- 浏览器前进/后退恢复周次和实体类型。
- 榜单名次、PK、在榜周数与 PC 一致。
- Top 3 强化区若实现，不得重复第 1–3 名造成语义混乱。

## 8.8 每周榜首 `/billboard/number-ones`

### 手机结构

1. Billboard 栏目选择器。
2. 歌曲/专辑/艺人分段器。
3. 年份选择 Chip 或 Sheet。
4. 年度冠军摘要。
5. 每周冠军时间线。
6. 冠军次数 Top 10。

### 调整规则

- 周冠军表格改为时间线行：周次、冠军、连续状态、播放量。
- 年度统计使用摘要卡，不并排显示大表。
- 同一 entity tab 下只显示对应有效年份。

## 8.9 Billboard 年榜 `/billboard/year-end`

### 手机结构

1. 年份选择。
2. 阶段年榜/覆盖率提醒。
3. 年度荣誉横向卡片。
4. 歌曲/专辑/艺人分段器。
5. 排序摘要与“排序”按钮。
6. 移动年榜列表。

### 移动行默认字段

- 年终排名。
- 名称。
- Year-End Score。
- 周榜峰值。
- 在榜周数。

完整字段进入详情 Sheet。

### 完成条件

- 年份、排序、分页继续写入或正确恢复现有状态。
- 阶段性年份提醒不可被折叠到完全不可见。
- 荣誉实体与列表实体可进入详情。

## 8.10 Billboard 总榜 `/billboard/all-time`

### 手机策略

总榜是 PC/Mobile presentation 分离最彻底的页面。

手机不支持：

- 拖动列宽。
- 同时展示大量字段。
- 将完整字段选择器常驻页面。

手机支持：

- 歌曲/专辑/艺人切换。
- 搜索。
- 排序。
- 一个主指标 + 两个用户选择的次级指标。
- 名称、当前固定全榜排名始终显示。
- 字段选择 Sheet。

建议内置字段组合：

- 综合成绩。
- 走势成绩。
- 长期稳定。
- 跨层级带动。

组合只是展示预设，不生成新统计指标。

### 完成条件

- 客户端搜索、分页和字段隐藏不改变原始总榜排名。
- track/album/artist 三类字段偏好继续独立持久化。
- 实体走势评分与固定全榜排名保持相邻可读。

## 8.11 Billboard 记录 `/billboard/records`

### 手机结构

1. 栏目选择器。
2. 记录族选择：冠军、长寿、突破、名人堂、趣味、市场。
3. 记录族摘要。
4. 单列 Record Cards。

### 调整规则

- 六个 Tab 改为 Section Switcher。
- 每张记录卡默认 Top 3，完整榜单按需展开。
- 封面、实体名、纪录值优先。
- 口径说明折叠。

## 8.12 对决 `/billboard/versus`

### 手机流程

1. 选择实体类型。
2. 搜索并添加 2–4 个实体。
3. 确认对决队列。
4. 查看胜者摘要。
5. 查看各实体纵向成绩卡。
6. 查看图表和发行周期。

### 调整规则

- 对决选择器使用全屏 Sheet 或独立步骤区。
- 已选实体以横向封面 Chip 展示，可删除和调整顺序。
- 结果 Scoreboard 由横向列改为纵向卡。
- 图表每次只显示一个指标族。
- 发行周期宽表改为按实体折叠。
- 结果底部固定“调整对决对象”。

### 完成条件

- 2–4 实体队列、排序、删除和类型切换无状态串线。
- 完整过滤指纹与详情/总榜保持一致。
- 结果卡与图表使用同一组 entities。

## 8.13 音乐查找 `/music/search`

### 手机结构

1. 推入式搜索顶部栏。
2. Sticky 搜索框。
3. 全部/歌曲/专辑/艺人 Chip。
4. 分实体类型的结果列表。
5. 空、加载、错误状态。

### 调整规则

- 输入后收起大 Hero，最大化结果空间。
- 每行显示封面、名称、艺人/专辑和个人 Billboard 摘要。
- 不自动高亮或打开第一条结果。
- 可增加最近搜索，但必须明确其本地存储边界。

### 完成条件

- URL `q`、`kind` 可分享并支持刷新恢复。
- 输入法组合输入不触发错误查询。
- 结果打开既有三类详情路由。

## 8.14 歌曲详情 `/music/tracks/:trackId`

### 手机结构

1. 返回顶部栏。
2. 封面、歌名、艺人、专辑。
3. 榜单状态和有效播放摘要。
4. 概览/统计/歌词分段器。
5. 当前 Tab 内容。

### 调整规则

- H1 缩为 30–34px，长歌名允许 2–3 行。
- 管理署名/版本入口进入“更多”，不与标题争抢宽度。
- 统计表改为摘要卡和移动记录列表。
- 歌词提高行高，避免底部栏/键盘遮挡。
- 版本组默认折叠。

## 8.15 专辑详情 `/music/albums/:albumName`

### 手机结构

1. 返回顶部栏。
2. 居中或大尺寸专辑封面。
3. 专辑名、艺人、发行信息。
4. 专辑自身成绩摘要。
5. 概览/统计/曲目/时代。
6. 当前 Tab 内容。

### 调整规则

- 专辑自身榜单与成员歌曲榜单状态继续分开。
- 曲目列表显示编号、名称、播放/榜单摘要。
- source breakdown、版本组和高级治理默认折叠。
- 管理专辑版本进入更多菜单。

## 8.16 艺人详情 `/music/artists/:artistName`

### 手机结构

1. 返回顶部栏。
2. 艺人头像、名称、整体成绩。
3. 高频入口：概览/统计/歌曲。
4. 更多栏目 Sheet：专辑/发行周期/生涯。
5. 当前内容。

### 调整规则

- 六个 Tab 不直接横向挤在一行。
- 歌曲、专辑使用移动实体列表。
- 发行周期和 Career 使用纵向时间线。
- 艺人身份管理进入更多菜单。

### 三类详情共同完成条件

- 详情存在资格与 Billboard Top-N/versus picker 保持解耦。
- 空榜单 Tab 继续存在并显示正确空状态。
- 返回、刷新、深链和 Settings return_to 不回退。

## 8.17 社区 `/community`、帖子与账号详情

### Feed 手机结构

1. 顶部栏：社区、搜索、趋势。
2. 精选/全部分段器。
3. 时间筛选摘要。
4. 全宽 Timeline。
5. 加载更多。

### 调整规则

- 移除右下角“探索”浮动按钮，避免与 Bottom Nav 冲突。
- Trending 和 Sidebar 内容进入顶部抽屉或 Bottom Sheet。
- 搜索和时间范围可合并为 Filter Sheet。
- Feed 卡减少外层边框，保持 X/微博式连续阅读。
- 帖子详情使用返回栏；社区账号使用紧凑 Profile Header。

### 完成条件

- 社区 chart params 继续与 Billboard 当前设置同步。
- Feed 搜索、时间范围、加载更多可用。
- Post/Account 详情仍高亮社区或按推入层规则隐藏 Bottom Nav。

## 8.18 AI 洞察 `/ai-insights`

### 报告模式

- 报告/问答分段器。
- 报告卡单列。
- 生成进度、状态和主操作在卡片内。
- 报告正文采用移动 Markdown 和章节导航。

### 问答模式

- 聊天区域使用剩余 `100dvh`。
- 输入框固定在键盘上方。
- 推荐问题横向滑动或换行 Chip。
- 对话历史从顶部按钮打开侧滑抽屉。
- 移除右下角历史浮动按钮。
- 输入态可隐藏 Bottom Nav。

### 完成条件

- 报告/问答状态不因移动结构切换而重置。
- 任务进度、证据卡、工具轨迹和时间解释完整。
- 键盘打开、长回答滚动、复制和 Markdown 表格可用。

## 8.19 Settings `/settings`

### 手机入口页

```text
设置
├─ 外观与名称
├─ 播放过滤
├─ Billboard 参数
├─ Spotify 连接
├─ 数据状态
├─ AI 设置
└─ 高级管理（建议使用电脑）
```

### 手机可编辑

- 主题与中文名称显示。
- 有效播放过滤、动态阈值、连续播放合并。
- Billboard Top N、周起点、是否包含精选集。
- Spotify 状态、连接、断开和同步；正式移动 OAuth 另行验收。
- LLM 开关和当前 Profile 选择。

### 手机只读/PC 引导

- Streaming/Account 文件导入。
- 归并与版本。
- 曲目署名。
- 艺人身份。
- 流派与语言证据审核。
- LLM 密钥与 Profile 完整编辑。
- 聚合重建、缓存清理等高风险操作。

### 结构要求

- 手机不渲染当前六区完整长页面后再隐藏内部控件。
- 使用 Settings Landing + 独立轻量设置页面/Sheet。
- 高级模块显示当前健康状态、待处理数量和“在电脑上管理”。
- 详情页深链到治理模块时，手机显示目标摘要和桌面提示，不丢失 return_to。

## 8.20 Not Found 与全局错误

- 保留 Mobile Top Bar。
- 提供“返回上一页”和“回到首页”。
- 不显示桌面大面积留白。
- 未知音乐实体与真正 404 保持现有契约，不把空榜单误判为不存在。

## 9. 技术架构

### 9.1 推荐组件树

```text
App
└─ ResponsiveAppLayout
   ├─ DesktopShell
   │  ├─ Masthead
   │  └─ Desktop content container
   └─ MobileShell
      ├─ MobileTopBar
      ├─ Mobile content container
      ├─ MobileBottomNav
      └─ Sheet/Modal portal layer
```

### 9.2 页面层职责

示例：

```text
AnalysisChartsPage
├─ useAnalysisFilters
├─ useAnalysisQueryState
├─ useApiData / query result
├─ shared filtered row model
└─ ResponsiveRankingPresentation
   ├─ DesktopPersonalRankTable
   └─ MobilePersonalRankList
```

要求：

- 数据 Hook 只执行一次。
- Desktop/Mobile 组件不各自请求 API。
- 排序、搜索、分页在共享 controller/hook 中处理。
- 复杂图表只挂载当前 presentation，避免隐藏组件仍消耗资源。

### 9.3 建议文件结构

```text
frontend/src/
├─ components/layout/
│  ├─ AppLayout.tsx
│  ├─ Masthead.tsx
│  ├─ MobileTopBar.tsx
│  ├─ MobileBottomNav.tsx
│  ├─ MobileSectionSwitcher.tsx
│  └─ routeContext.ts
├─ components/mobile/
│  ├─ MobilePageHeader.tsx
│  ├─ MobileFilterSheet.tsx
│  ├─ MobileRankList.tsx
│  ├─ MobileEntityRow.tsx
│  ├─ MobileEntityDetailSheet.tsx
│  ├─ MobileChartCard.tsx
│  └─ MobileStickyActions.tsx
├─ hooks/
│  └─ useBreakpoint.ts
└─ features/<domain>/
   ├─ shared data/controller
   ├─ desktop presentation（仅结构差异显著时）
   └─ mobile presentation（仅结构差异显著时）
```

不要为了目录对称，给所有页面都建立 Desktop/Mobile 文件。只有 DOM 结构和交互模型明显不同的区域才拆分。

### 9.4 路由上下文扩展

扩展 `routeContext.ts`，至少提供：

```ts
type MobileRouteContext = {
  activeRoot: '/' | '/analysis' | '/billboard' | '/community' | '/ai-insights' | null
  title: string
  presentation: 'root' | 'section' | 'detail' | 'fullscreen'
  showBottomNav: boolean
  showBack: boolean
  sectionGroup?: 'analysis' | 'billboard'
}
```

它只负责路由展示归属，不读取 API，也不复制业务判断。

### 9.5 API 边界

第一阶段原则上不新增移动专用 API。

允许新增 API 的条件：

- 当前 API 只能返回巨量明细，无法在移动首屏合理加载。
- 已有分页不足以支撑移动无限列表。
- 新字段是所有消费者都合理需要的摘要，而不是移动端临时拼凑。

禁止：

- `/api/mobile/*` 复制已有统计。
- 手机端使用另一套 Billboard Top N 或播放过滤默认值。
- 为减少字段而改变固定全榜排名计算范围。

### 9.6 性能策略

- Mobile Shell 不预加载当前用户短期不会访问的大块图表。
- 首页继续保留轻量首屏查询；移动端减少非关键图表首屏挂载。
- ECharts 只在图表进入视口或当前 Tab 激活后加载。
- 图片提供合理尺寸、`loading="lazy"` 和稳定宽高，避免 CLS。
- 长列表继续使用分页、infinite query 或虚拟化。
- Bottom Sheet 内的重组件在打开时挂载，关闭后按状态需求卸载。

## 10. 分阶段实施规划

## Phase M0：设计冻结与基线记录

> **已完成（2026-08-05）**：冻结结论、真实移动基线、完整路由状态矩阵、六屏交互原型、组件状态规范与 M1/M2 原子任务见 [`../designs/2026-08-05-mobile-web-m0-design-freeze.md`](../designs/2026-08-05-mobile-web-m0-design-freeze.md)。

### 目标

在编码前冻结移动端导航、页面优先级和验收基线。

### 任务

- [x] 为 390px 保存首页、播放统计、播放排行、Billboard 周榜、音乐详情、AI 问答的当前截图。
- [x] 记录 360/390/430/768/1280 的导航高度、页面溢出和首屏状态。
- [x] 确认手机 V1 的 Settings 能力边界。
- [x] 确认是否在音乐详情隐藏 Bottom Nav。
- [x] 确认 Top 3 强化区是否用于周榜。
- [x] 建立移动 UI tokens 与组件命名约定。

### 退出条件

- 六个代表页面的线框/高保真方向已确认。
- 没有尚未拍板且会改变 Shell 架构的决策。

## Phase M1：全局 Mobile Shell

> **已完成（2026-08-05）**：独立 Phone Shell、路由状态、栏目 Sheet、稳定返回、AI/社区冲突处理、测试与浏览器门禁均已落地。交付证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

### 目标

建立手机和 PC 的结构分层，不改变页面业务内容。

### 主要文件

- `frontend/src/components/layout/AppLayout.tsx`
- `frontend/src/components/layout/Masthead.tsx`
- `frontend/src/components/layout/routeContext.ts`
- 新增 `MobileTopBar.tsx`
- 新增 `MobileBottomNav.tsx`
- 新增 `MobileSectionSwitcher.tsx`
- `frontend/src/hooks/useViewportMode.ts`
- `frontend/src/index.css`

### 任务

- [x] 统一手机断点为 `<768px`。
- [x] PC 继续渲染 Masthead；手机渲染 Top Bar + Bottom Nav。
- [x] 增加 safe-area tokens 和手机内容底部 padding。
- [x] 扩展 route context，覆盖所有路由归属。
- [x] 实现播放分析和 Billboard 的 Section Switcher。
- [x] 修复社区/AI 右下角浮动按钮与 Bottom Nav 冲突。
- [x] 添加 focus trap、Escape 和滚动锁定。

### 测试

- [x] routeContext 纯函数单元测试。
- [x] Mobile Shell 组件测试。
- [x] 390px 五项 Bottom Nav 可见、可点击、active 正确。
- [x] 1280px Masthead 与现状一致。
- [x] 音乐详情、Settings、全屏层的 Bottom Nav 显示规则正确。

### 退出条件

- 所有主路由可以通过新手机导航访问。
- PC 导航无视觉/功能回退。
- 页面级横向溢出为 0。

## Phase M2：移动通用组件

### 目标

在逐页改造前建立可复用的移动显示原语。

### 任务

- [x] `MobilePageHeader`。
- [x] `MobileBottomSheet` 基础层，并将 `MobileSectionSwitcher` 迁移到统一契约。
- [x] `MobileFilterSheet`。
- [x] `MobileTimeRangeSheet`。
- [x] `MobileRankList` 与 `MobileEntityRow`。
- [x] `MobileEntityDetailSheet`。
- [x] `MobileChartCard` 与全屏图表容器。
- [x] 移动分页/加载更多组件。
- [x] 统一移动 Loading/Empty/Error/Config Missing 状态。

### 测试

- [x] 无障碍名称、焦点顺序、Tab/Shift+Tab、Escape。
- [x] 主要操作、关闭与分页控件按 44px 触控下限实现。
- [x] Bottom Sheet 打开时背景不可滚动，关闭后恢复。
- [x] 360px 亮/暗主题、长文本、详情 Sheet 与横屏全屏图表截图。

### 完成记录

M2 已于 2026-08-05 完成，交付边界、组件地图和验证证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。本阶段只建立通用 presentation 原语；首页、播放统计、播放排行与 Billboard 周榜的真实页面重排属于 M3。

## Phase M3：高频数据页面

### 范围

- 首页。
- 播放统计。
- 播放排行。
- Billboard 周榜。

### 任务

- [x] 首页紧凑 Hero、2×2 KPI、单列图表与快捷入口。
- [x] 播放统计 KPI 折叠、图表分段和最近播放列表。
- [x] 播放排行 Desktop Table/Mobile List 分层。
- [x] Billboard 周榜周选择 Sheet、移动 Chart Row 和摘要区。
- [x] 保持全部 URL、filters 和 query key 指纹。

### 退出条件

- 四个页面完成 360/390/430/768/1280 验收。
- 代表性数据与 PC 对照一致。
- 搜索、排序、分页和实体跳转可用。

### 完成记录

M3 已于 2026-08-05 完成：首页、播放统计、播放排行与 Billboard 周榜均采用 Phone/Desktop presentation 互斥挂载，继续消费原 API、filters 与 TanStack Query。360/390/430/768/1280 五档、URL 周次历史、固定原始排名、实体跳转和 Phase 5 最低矩阵均已验收。实现边界与证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

## Phase M4：年度与记录页面

### 范围

- 年度总结。
- 播放记录。
- 每周榜首。
- Billboard 年榜。
- Billboard 总榜。
- Billboard 记录。
- 对决。

### 任务

- [x] 年度章节导航和移动 Story Sections。
- [x] 播放记录 Section Switcher 与 Mobile Record Cards。
- [x] 每周榜首时间线。
- [x] 年榜荣誉卡、移动排序和榜单列表。
- [x] 总榜字段组合与 Field Sheet。
- [x] 榜单记录族选择和 Top 3 展开。
- [x] 对决三步式选择和纵向 Scoreboard。

### 退出条件

- 所有 Billboard 页面不依赖页面级宽表横向滚动。
- 年度/记录长页的导航和滚动定位稳定。
- 总榜固定排名、走势排名和跨层级指标未改变。

### 完成记录

M4 已于 2026-08-05 完成：七个页面均使用面向手机的信息重排，同时继续复用原 API、过滤指纹、榜单事实与详情路由。年度总结采用章节式长页；两类记录页采用栏目切换与 Top 3 渐进展开；每周榜首、年榜和总榜分别采用时间线、固定年榜排名列表和固定全榜排名列表；对决支持 2–4 个实体与纵向成绩卡。360/390/430/768/1280 五档、桌面/手机 route smoke、控件库存与 Phase 5 最低矩阵均已验收。实现边界与证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

## Phase M5：音乐搜索与详情

### 范围

- `/music/search`
- 歌曲详情。
- 专辑详情。
- 艺人详情。

### 任务

- [x] Sticky 搜索框和分组结果。
- [x] 三类详情统一返回 Top Bar。
- [x] Compact Hero 与详情 Tab/Section Switcher。
- [x] 曲目、专辑、艺人子列表移动化。
- [x] 歌词移动排版。
- [x] 版本/署名/身份治理入口移入更多菜单。
- [x] 空榜单和无详情事实状态复核。

### 退出条件

- 搜索到三类详情的完整链路通过。
- 返回地址和深链刷新正确。
- 管理入口仍能定位 Settings 目标，但手机不会渲染完整治理工作台。

### 完成记录

M5 已于 2026-08-05 完成：全局音乐查找采用吸附搜索与歌曲/专辑/艺人分组结果，中文输入法组合阶段不会提前改写 URL；三类详情均使用实体专属 Compact Hero、URL 驱动的栏目状态和移动纵向列表。艺人高频三栏常驻，专辑、发行周期与生涯信息进入“更多详情栏目”；版本来源在手机默认折叠，署名/版本/身份治理入口统一进入 Top Bar“更多”，并保留精确 `return_to`。同时修复已入榜艺人详情错误返回 0 次有效播放的接口问题。四页 360/390/430/768/1280 共 20 组均为 0px 横向溢出，desktop/mobile route smoke 8/8、控件库存 103 个控件/0 violation，Phase 5 最低矩阵全部通过。实现边界与证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

## Phase M6：社区、AI、账号与设置

### 任务

- [x] 社区趋势抽屉、筛选 Sheet、Feed 全宽化。
- [x] 帖子和社区账号详情 Top Bar。
- [x] AI 对话 `100dvh` 布局、键盘适配和历史抽屉。
- [x] AI 报告移动 Markdown 和任务状态。
- [x] 账号 Hero、收藏/习惯移动组件。
- [x] Settings Landing 和日常设置页面。
- [x] 高级治理状态卡与 PC 提示。

### 退出条件

- 社区和 AI 不再使用与 Bottom Nav 冲突的悬浮按钮。
- 聊天输入区在 iOS/Android 键盘打开时可见。
- Settings 手机边界清晰，不误导用户可在手机完成复杂治理。

### 完成记录

M6 已于 2026-08-05 完成：社区改为全宽连续 Feed，搜索/时间筛选和趋势进入共享 Bottom Sheet，帖子与社区账号详情使用 Push Top Bar；AI 报告/问答采用手机分段切换，对话区按剩余 `dvh` 布局，输入聚焦时隐藏 Bottom Nav，历史记录进入 Top Bar Sheet；账号中心增加编辑式身份 Hero、2×2 事实、无障碍分段 Tab、纵向收藏/排行列表和按需加载的习惯折叠区；Settings 首屏改为七类任务入口，日常主题、播放、榜单、Spotify 与 AI Profile 可在手机完成，文件导入、元数据治理、凭据和系统维护明确引导到电脑端，实体治理深链仍保留目标与返回地址。六类 M6 路由在 360/390/430/768/1280 共 30 组均为 0px 横向溢出，desktop/mobile route smoke 8/8、移动控件库存 82 个控件/0 violation，Phase 5 最低矩阵全部通过。实现边界与证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

## Phase M7：质量门禁与发布收口

### 单元/组件测试

- [x] route context。
- [x] Bottom Nav active/visibility。
- [x] Section Switcher。
- [x] Filter Sheet。
- [x] Mobile Rank List。
- [x] 详情 Sheet。
- [x] Settings mobile capability boundary。

### 浏览器验证

- [x] 扩展 `frontend_route_smoke.mjs`，验证手机 Shell marker。
- [x] 扩展 `frontend_interaction_smoke.mjs`，覆盖 Bottom Nav、Section Sheet、时间筛选。
- [x] 扩展 `frontend_control_inventory_smoke.mjs`，检查 Bottom Sheet 和移动榜单控件。
- [x] 扩展 `frontend_chart_interaction_smoke.mjs`，覆盖点击 tooltip 和全屏图表。
- [x] 扩展 `frontend_cross_browser_smoke.mjs`，覆盖 Chromium/Firefox/WebKit。
- [x] 保持 long-list smoke 和 API smoke/boundary 通过。

### 视觉矩阵

| 宽度/环境 | 必测 |
|---|---|
| 360×800 | 小尺寸 Android、长标题、Bottom Nav |
| 390×844 | 主移动基线 |
| 430×932 | 大尺寸手机 |
| 768×1024 | 平板边界 |
| 1280×800 | PC 回归 |
| iOS Safari | safe area、键盘、滚动、PWA 预备 |
| Android Chrome | 系统返回、键盘、点击 tooltip |

### 硬门禁

- 页面级横向溢出：0。
- console error：0。
- console warning：0，除非有明确 allowlist。
- 可见交互控件缺少 accessible name：0。
- 嵌套交互控件：0。
- 重复 id：0。
- disabled 仍可 tab：0。
- 主要触控目标小于 44×44：0。
- Bottom Nav/Top Bar 遮挡正文或操作：0。
- 手机 LCP、CLS、TBT 不劣于既有预算；初始目标可采用 LCP <=2.5s、CLS <=0.1、TBT <=200ms，再按真实基线收紧。

### 完成记录

M7 已于 2026-08-05 完成自动化质量与发布收口：五档视口矩阵、完整 desktop/mobile 控件库存、Bottom Nav/Section Sheet/时间筛选、触摸 tooltip、全屏图表、长列表、API、性能、Web Vitals 和 Chromium/Firefox/WebKit 均纳入可重复门禁。生产预览 12/12 Web Vitals 样本满足 LCP <=2.5s、CLS <=0.1、TBT <=200ms；最终聚合运行中，开发/生产控件库存分别检查 1,807/1,690 个可见控件与 353/351 个主要移动触控目标，违规和欠尺寸目标均为 0。发布证据和物理设备边界见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

物理 iOS Safari 与 Android Chrome 的安全区、软键盘和系统返回仍建议在真正对外部署前各做一次现场复核；当前由 WebKit Safari-family、Chromium Android UA/触控模拟和移动输入聚焦 smoke 代替，不把模拟结果描述成真机结果。

## 11. 页面优先级

| 优先级 | 页面 | 原因 |
|---|---|---|
| P0 | Mobile Shell、首页、播放统计、播放排行、Billboard 周榜、音乐搜索/详情 | 覆盖日常最高频任务与全部关键组件类型 |
| P1 | 年度总结、播放记录、年榜、总榜、每周榜首、AI、社区 | 形成完整核心产品体验 |
| P2 | 榜单记录、对决、账号中心、Settings 日常项 | 重要但不是手机首批验证入口 |
| P3 | 高级元数据治理移动工作流 | 只有确认真实移动需求后再设计 |

## 12. 预计工作量

以下以单人连续开发、现有 API 基本不变为前提，不包含 PWA、Capacitor、远程认证和商店发布：

| 阶段 | 粗略时间 |
|---|---:|
| M0 设计冻结与基线 | 3–5 天 |
| M1 Shell | 4–7 天 |
| M2 通用组件 | 4–7 天 |
| M3 高频数据页面 | 2–3 周 |
| M4 年度与 Billboard 深页 | 2–3 周 |
| M5 搜索与详情 | 1–2 周 |
| M6 社区、AI、账号、设置 | 1.5–2.5 周 |
| M7 完整验收与收口 | 4–7 天 |

建议以 M1–M3 作为第一个里程碑，约 4–6 周形成可用的移动核心版；全页面移动化约 8–12 周。若缩减详情或高级 Billboard 页面，可以更早交付 V1。

## 13. 风险与缓解

| 风险 | 表现 | 缓解 |
|---|---|---|
| 复制两套页面导致漂移 | Desktop/Mobile 各自查询和格式化 | 共享 Route Container、Hook、row model，只拆 presentation |
| 移动版隐藏太多信息 | 用户无法核对完整指标 | 行点击详情 Sheet、全字段入口、PC 完整表 |
| Bottom Nav 与现有浮动按钮冲突 | 社区/AI 操作被遮挡 | 浮动入口迁入 Top Bar/Sheet，统一 z-index 和 safe area |
| 图表触控冲突 | dataZoom 拖动导致页面无法滚动 | 仅必要图表开启 zoom，提供全屏模式和明确交互区 |
| 详情 Tab 过多 | 艺人六项 Tab 难以导航 | 高频三项 + 更多栏目 Sheet |
| Settings 手机化扩大风险 | 在小屏误操作治理数据 | V1 只开放日常设置，高级治理只读和 PC 引导 |
| 性能回退 | 同时挂载 Desktop/Mobile 重组件 | 只挂载当前 presentation，图表延迟加载 |
| PC 版被移动重构破坏 | 共享组件样式意外改变 | 1280px 视觉回归、Desktop snapshots、changed-file smoke |
| 路由/返回体验混乱 | 详情无父级、刷新后 back 无效 | route context + 稳定 fallback + return_to |

## 14. Definition of Done

移动端网页阶段只有同时满足以下条件才算完成：

### 产品

- [x] 手机具有独立 Top Bar、Bottom Nav 和二级栏目选择器。
- [x] 全部消费页面在手机可访问并可完成核心任务。
- [x] PC 与手机的功能边界有明确解释。
- [x] 复杂治理没有被简单压缩成难以使用的长表单。

### 语义

- [x] 手机与 PC 使用相同 API、过滤指纹和排名事实。
- [x] 隐藏字段不改变排序、资格和固定全榜排名。
- [x] 音乐详情存在资格、独立榜单状态和子成绩状态不回退。

### 交互

- [x] 所有导航、筛选、排序、搜索、分页、详情和返回路径可用。
- [x] 没有 hover-only 关键操作。
- [x] 键盘、safe area、Bottom Sheet、全屏图表行为稳定（自动化模拟通过，真机现场复核见 M7 备注）。

### 质量

- [x] 360/390/430/768/1280 通过。
- [x] Chromium/Firefox/WebKit 通过。
- [x] 横向溢出、console error/warning、控件库存违规均为 0。
- [x] 前端测试、构建、Phase 5 架构护栏与全栈发布门禁通过。

### 文档

- [x] `frontend/UI_STYLE_GUIDE.md` 增加移动端规范。
- [x] `AGENTS.md` / `CLAUDE.md` 只在形成稳定架构契约后更新。
- [x] `docs/CHANGELOG.md` 记录各里程碑完成情况。
- [x] 旧增量移动导航文档继续归档，不作为现行实施依据。

## 15. 首个实施批次建议

第一批不应同时改全部页面，建议严格控制为：

1. Mobile Shell。
2. Mobile Top Bar + Bottom Nav。
3. 播放分析/Billboard Section Switcher。
4. 首页。
5. 播放统计。
6. 播放排行。
7. Billboard 周榜。
8. 一种音乐详情页作为推入层样板。

该批次必须先证明：

- PC 完全不回退。
- 手机导航成立。
- 宽表可以稳定转换为移动列表。
- 图表可以触控使用。
- URL 和统计语义保持不变。
- 现有验证脚本可以识别 Desktop/Mobile 两种 Shell。

确认这套样板后，再将同一组件体系扩展到年榜、总榜、记录、年度总结、社区、AI 和 Settings。
