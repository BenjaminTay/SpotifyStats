# 移动端网页 M0–M7 与 PWA Phase A 综合交付报告

> 状态：**PASS / 本地移动网页发布候选与可安装 PWA 基线完成**<br>
> 日期：2026-08-06<br>
> 产品与实施规划：[`../plans/2026-08-05-mobile-web-design-and-implementation-plan.md`](../plans/2026-08-05-mobile-web-design-and-implementation-plan.md)<br>
> App 化路线：[`../plans/2026-08-06-appification-pwa-capacitor-plan.md`](../plans/2026-08-06-appification-pwa-capacitor-plan.md)<br>
> 设计冻结：[`../designs/2026-08-05-mobile-web-m0-design-freeze.md`](../designs/2026-08-05-mobile-web-m0-design-freeze.md)

## 1. 交付结论

SpotifyStats 移动网页 M0–M7 已完成设计、实现和自动化质量收口。Phone presentation 不再是缩窄的桌面网页：它拥有独立 Top Bar、Bottom Nav、栏目与筛选 Sheet、移动榜单/详情结构、触控图表和 Settings 能力边界；Compact 与 Desktop presentation 继续保留。

两端共享 React Router、TanStack Query、API 类型、过滤指纹、排名事实和详情存在资格。移动改造只在 presentation 层分叉，没有建立第二套统计实现，也没有为了手机改变 Billboard 或播放统计口径。

在移动网页通过发布门禁后，Phase A 又补齐了可安装 PWA 壳层，包括 Manifest、App 图标、standalone 启动、安装引导和安全离线说明。当前结论只覆盖本地开发与生产预览，不代表已经完成 HTTPS 部署、物理设备验收或原生 App 发布。

## 2. 阶段交付总览

| 阶段 | 状态 | 核心交付 |
|---|---|---|
| M0 设计冻结 | PASS | 设备断点、Shell、路由状态、视觉系统、组件状态、六类代表页面与验收矩阵 |
| M1 Mobile Shell | PASS | Root/Section/Push Top Bar、五项 Bottom Nav、栏目 Sheet、稳定返回、safe area 与 URL 状态 |
| M2 通用组件 | PASS | Sheet、筛选、时间、实体榜单、图表、分页、状态模板与全屏图表原语 |
| M3 高频页面 | PASS | 首页、播放统计、播放排行与 Billboard 周榜的独立 Phone presentation |
| M4 年度与记录 | PASS | 年度总结、播放记录、榜首、年榜、总榜、榜单纪录与对决页面 |
| M5 音乐查找与详情 | PASS | 搜索、歌曲/专辑/艺人详情、URL 栏目状态、治理深链与纵向成绩列表 |
| M6 社区、AI、账号、设置 | PASS | 全宽社区 Feed、键盘安全对话、账号移动组件与 Settings 风险分层 |
| M7 发布门禁 | PASS | 五档视口、全路由、触控尺寸、跨浏览器、API、性能与 Web Vitals 收口 |
| PWA Phase A | PASS | Manifest、图标、安装卡、standalone、主题同步、Service Worker 与安全离线页 |

## 3. 移动端实现

### 3.1 设备模式与 Shell

- `<768px` 使用 Phone presentation，`768–1023px` 使用 Compact，`>=1024px` 使用 Desktop。
- Root、Section、Push 三种 `MobileTopBar` 分别承载根页面、栏目页面和详情返回。
- 首页、播放、榜单、社区、AI 五项 `MobileBottomNav` 只出现在允许的手机路由；搜索、Settings 和 Push 详情不重复挂载底部导航。
- Analysis/Billboard 栏目使用 Bottom Sheet，跳转保留时间范围、周次、类型与其他有效查询参数。
- Push 返回遵循 `history → 安全 return_to → fallback`；AI 输入聚焦时隐藏 Bottom Nav，避免软键盘遮挡输入区。
- safe area、内容 gutter、顶部/底部高度、滚动锁定和 z-index 使用统一移动 tokens。

### 3.2 通用移动组件

- `components/mobile/` 提供 Sheet、分段控件、筛选/时间、实体行、榜单行、图表卡、全屏图表、分页和状态模板。
- 通用组件不访问 API，也不引入 Query/Mutation；页面或 feature 层继续负责把既有数据转换为 row、fact、series 与 filter model。
- `MobileChartCard` 接收图表节点，不直接依赖 ECharts；Phone/Desktop 重图表在路由容器中互斥挂载。
- Filter Sheet 只在确认应用后更新 URL；关闭时丢弃草稿。排名由后端 row model 传入，不因移动端搜索或分页重新编号。
- 主要移动触控目标下限为 44×44px；关键交互不依赖 hover，全屏图表关闭后恢复触发按钮焦点。

### 3.3 页面族

- **首页与播放分析**：紧凑 Hero、2×2 KPI、移动趋势图、快捷入口、播放统计图表切换、纵向排行与近期播放。
- **Billboard 周榜**：周次 Sheet、歌曲/专辑/艺人类型、PK/在榜周数/走势事实；`week` 与 `tab` 写入 URL，历史周返回最新周的状态恢复已修复。
- **年度与记录**：年度章节长页、移动锚点导航、记录 Top 3 渐进展开、榜首时间线、年榜/总榜字段 Sheet 与纵向对决成绩卡。
- **音乐查找与详情**：中文输入法 composition 结束后再同步 URL；三类详情使用 Compact Hero、URL 栏目状态、纵向榜单/曲目/最近播放和 Top Bar 更多操作。
- **社区**：Feed 占满手机内容宽度；搜索、时间和趋势进入 Sheet；帖子与账号详情使用 Push Top Bar。
- **AI 洞察**：报告/问答使用移动分段控件；消息区独立滚动，输入区贴底，历史会话进入 Top Bar Sheet。
- **账号中心**：身份 Hero、2×2 事实、收藏/习惯分段 Tab、纵向收藏和排行列表、按需展开的习惯模块。
- **Settings**：手机只开放主题、播放、榜单、Spotify 与 AI 当前配置等日常低风险操作；导入、元数据治理、密钥和系统维护继续由桌面工作台承担。

### 3.4 同期语义修复

音乐详情实施过程中修复了已入榜艺人详情 `effective_play_count` 错误返回 0 的问题。详情访问与 Hero 有效播放总数现在始终复用个人播放过滤链路，并由 contract test 锁定。该修复校正接口输出，没有改写底层播放统计规则。

### 3.5 验收后修复与移动端再校准

2026-08-06 按页面视觉验收结果完成一轮 P1/P2 收口：

- 播放排行实体行将“首次播放”徽章独立成可换行区域，避免 360–430px 下与右侧播放指标重叠；route smoke 增加真实几何重叠硬检查，不再只依赖页面级横向溢出判断。
- Wrapped `/api/wrapped/{year}/full` 新增基于有效年度播放帧计算的 `reporting_period`，返回起止日期、最新数据日期、活跃天数、覆盖天数、阶段年度状态和标签；当前年度未结束时，手机年度总结首屏明确显示“年度进行中 / 数据截至 YYYY-MM-DD”。
- AI 问答空态改为完整单列建议，四个推荐问题均为 44px 触控行，输入框保持首屏可见；输入聚焦后 Bottom Nav 仍按原契约隐藏。
- Billboard 对决空态增加清晰的两步指引和两项真实实体快捷建议，点击后直接进入选择队列；桌面交互和统计计算保持不变。
- Settings 在聚合等待重建时同时显示状态与影响，明确“统计可能不是最新”；社区账号页移除手机端重复标题区，帖子数量合入单一 Posts 标签。
- 音乐详情 Top Bar 的更多入口提高前景对比度和点击可见性，仍复用既有分享、搜索与治理深链动作。

这一轮仍遵守同一路由、同一 Query/API/统计事实、仅 presentation 分叉的移动架构边界。

### 3.6 2026-08-10 人工验收第二轮视觉收口

第二轮验收不再扩展页面范围，而是按真实手机浏览结果重排信息层级、压缩无效留白，并修正会造成误解的移动端呈现：

- **周榜与每周榜首**：所有周次统一显示 `Week N, YYYY`，切周按钮与标题对齐，日期继续通过日历组件选择；榜单类型、紧凑摘要和榜单主体整体上移。排名与变化状态分层对齐，手机端一次展示完整榜单。每周榜首把年份选择收进“每周冠军”作用域，时间线补齐封面，避免年份按钮看似控制整个页面。
- **音乐详情**：歌曲、专辑、艺人移除重复英文 eyebrow，Hero 事实统一为一行四列；标签栏、全貌/细节切换和分布图切换收紧。每日/累计播放及星期/月度/年度分布继续共享图表区域，排名趋势、图表高度和听歌时钟按 Phone 密度缩减。
- **榜单记录**：记录家族使用横向滑动栏目，卡片内实体类型切换改为紧凑控件；第四名以后行高和指标层级收敛。冠军传承、回归冠军、阻挡王、最长登顶路等记录把决定排名的指标放在右侧重点位置，辅助日期并排放在下方；Peak 使用 `1/2/3` 等自然数字，周数使用统一衬线数字样式。
- **名人堂、持久记录与市场记录**：年度之歌按年逐行显示，年代选择适配窄屏滑动；最长在榜、冠军周数等周数格式统一。市场类与长列表继续保留既有数据和入口，只调整手机 presentation，不改变排序、分页数据源或桌面呈现。
- **奇趣记录**：双榜空降中的歌曲/专辑、全榜单制霸中的艺人/歌曲/专辑改为平级的事件单元，统一封面、名称、作者、Peak、在榜周数和播放指标的位置；修正“双榜空降”为歌曲与专辑同周登顶的语义。最早上榜、最新上榜、最长歌名、最短歌名去除重复外层标题，并收进同一大框；劳模歌手等数量指标改用统一展示字体。
- **全局视觉清理**：删除用户进入页面后无需重复解释的 subtitle，缩短页面标题与首个内容块之间的空隙；共享 `rank-tone` 负责状态和前列排名色阶，避免各页面自行复制颜色判断。

本轮没有修改后端 API、数据库结构、统计规则或桌面信息架构；所有变化均限定在 Phone presentation、共享视觉工具和前端契约测试。

## 4. PWA Phase A

- `manifest.webmanifest` 声明应用名称、scope、start URL、standalone、主题色、192/512 maskable 图标与四个快捷入口。
- `index.html` 增加通用/Apple App Mode 元信息、Apple Touch Icon 与 `viewport-fit=cover`。
- 手机 Settings 增加 App Mode 安装卡：Chromium 调用安装提示，iOS 显示 Safari 添加到主屏幕步骤，standalone 显示已安装状态。
- 日/夜主题同步更新 `theme-color` 与 `color-scheme`。
- Service Worker 只缓存离线说明、PWA 图标和版本化 `/assets/`，明确绕过 `/api/` 与 `/covers/`。
- 离线时只显示连接说明，不回放个人统计，不缓存 SQLite、API 响应、OAuth token 或 LLM 凭据。

## 5. 最终验证证据

### 5.1 测试与构建

| 门禁 | 最终结果 |
|---|---:|
| Backend full | 1,472 passed |
| Backend unit | 853 passed |
| Backend contract | 323 passed |
| Frontend Vitest（验收后修复最新） | 58 files / 445 tests passed |
| Ruff + TypeScript/Vite production build | PASS |
| Phase 5 最低矩阵 | PASS |

Vite 仅保留既有大 chunk 提示；没有新增运行时 warning。

`npm run lint` 不是当前 Phase 5 发布门禁，仓库全量 ESLint 仍有 194 个历史问题，集中在既有 `any`、React effect/ref 与 Fast Refresh 规则。本轮新增/调整且不含这些既有基线问题的 15 个 TS/TSX 文件已定向通过 ESLint；本次不顺带扩大为全仓 lint 治理。

### 5.2 路由、交互与可访问性

| 检查 | 最终结果 |
|---|---:|
| 五档视口代表页面矩阵 | 30/30 PASS |
| 全路由 desktop/mobile | 开发与生产预览均 54/54 PASS |
| Chromium/Firefox/WebKit | 3/3 引擎 PASS；每个引擎覆盖 22 组路由与 6 个核心交互 |
| 移动 Bottom Nav / Section Sheet / 时间筛选 | 3/3 PASS |
| 移动触摸 tooltip / 全屏图表 | 2/2 PASS |
| 桌面核心交互 | 7/7 PASS |
| 桌面图表交互 | 3/3 PASS |
| 长列表分页/分段渲染 | 7/7 PASS |

全量控件库存覆盖 20 个路由 × desktop/mobile，共 40 个组合。开发环境检查 1,807 个控件 / 353 个主要移动触控目标，生产预览检查 1,690 个控件 / 351 个主要移动触控目标；两套环境均为 0 可访问性违规、0 欠尺寸主要触控目标。

最终路由和交互样本均为 console error 0、console warning 0、page error 0、页面级横向溢出 0px。

### 5.3 API 与性能

| 门禁 | 最终结果 |
|---|---:|
| API smoke | 116/116 PASS；0 unaccounted |
| API boundary | 101/101 PASS |
| 核心 API benchmark | PASS；hot P95 均小于 500ms |
| Production Web Vitals | 12/12 PASS |

生产预览覆盖 6 个代表路由 × desktop/mobile：最大 LCP 812ms、CLS 0、TBT 0ms、最大资源数 45、最大 encoded 体积约 4,580.3KB、横向溢出 0px。

### 5.4 PWA 浏览器证据

- 390×844 Chromium 生产预览中，Service Worker 为 `activated` 且控制页面。
- `Page.getAppManifest` 返回 0 个 Manifest error；自动化环境唯一 installability 原因为 `in-incognito`，不是应用配置缺陷。
- 强制断网后进入专用离线页，控制台 0 error / 0 warning。
- `/settings` production smoke 覆盖 320、390、430、768 与 1440px，全部 0 错误、0 告警、0 页面异常、0 横向溢出。
- Manifest、图标、Service Worker 与离线页静态响应均为 HTTP 200，MIME 正确。

### 5.5 验收后修复专项证据

| 检查 | 结果 |
|---|---:|
| 7 个受影响页面 × 五档视口 | 35/35 PASS |
| 全移动路由（含歌曲、专辑、艺人、帖子、社区账号详情） | 27/27 PASS |
| 移动控件库存 | 20 个页面 / 640 个控件 / 305 个主要触控目标 / 0 violation |
| 移动导航、栏目 Sheet、时间筛选 | 3/3 PASS |
| 移动触摸 tooltip、全屏图表 | 2/2 PASS |
| 桌面核心交互与图表回归 | 7/7 + 3/3 PASS |
| 长列表分页与分段渲染 | 7/7 PASS |
| Chromium / Firefox / WebKit 移动代表路由 | 3/3 引擎 PASS |

上述有效场景均为 console error 0、console warning 0、page error 0、横向溢出 0px；个人排行内部徽章/指标几何重叠为 0。桌面专用交互和移动专用交互按脚本定义分别执行，不把桌面 hover 场景误作手机触控门禁。

### 5.6 第二轮人工验收视觉收口证据

| 检查 | 结果 |
|---|---:|
| 移动端定向 Vitest（M3–M6、公共组件、Shell、详情图表） | 8 files / 72 tests passed |
| Frontend Vitest full | 59 files / 456 tests passed |
| TypeScript + Vite production build | PASS |
| 文档与代码 diff whitespace 检查 | PASS |

生产构建仍只有既有大 chunk 提示；本轮没有新增 TypeScript、测试或构建错误。视觉调整不改变后端契约，因此未重复执行数据库迁移、API benchmark 或后端全量测试。

## 6. 长期架构契约

- Phone/Desktop 共享路由容器、Query、API、统计事实和过滤指纹，只在 presentation 层分叉。
- 同一路由的 Phone/Desktop 重组件必须互斥挂载；新增长表继续采用分页、分段渲染、infinite query 或虚拟化。
- 手机主要触控目标至少 44×44px；关键交互必须支持触摸和键盘，不得只依赖 hover。
- Settings 手机端保持低风险日常操作边界，复杂治理与凭据维护不迁入消费页面。
- 新增消费页面必须进入五档 route matrix、移动 control inventory、核心 interaction/chart smoke 和跨浏览器门禁。
- PWA 开发模式不注册 Service Worker；生产 Service Worker 不得缓存个人数据、OAuth/LLM 凭据或动态 API 响应。

## 7. 尚未完成的外部边界

以下项目未被本报告描述为已完成：

1. 稳定 HTTPS 域名、远程 API、鉴权、SQLite 持久化与备份。
2. iPhone Safari 与 Android Chrome 物理设备安装和交互验收。
3. Spotify OAuth 在最终 HTTPS 域名上的真实回跳。
4. Capacitor iOS/Android 工程、签名、安装包与商店发布。
5. 微信小程序或微信 WebView 包装。
6. 个人统计数据离线可用；当前只提供安全离线说明。

在没有部署需求时，项目可以停在当前本地发布候选状态，不需要提前引入服务器或原生工程。
