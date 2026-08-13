# 音乐档案 Phone 交付记录

> 日期：2026-08-13
> 集成状态：已进入 `main`
> 范围：`/account` 的独立 Phone presentation、全屏收藏库、移动门禁与合并后的人工验收收口

## 1. 交付结论

Phone 已从旧账号 Hero 和桌面内容折叠壳切换为独立“口袋音乐档案”。它与 Desktop / Compact 共享本地统计事实、TanStack Query、过滤参数、URL 和格式化模型，但不会同时挂载桌面长列表或宽图。

页面使用既有 `/account` 路由，二级导航与正文统一命名为“音乐档案”。运行时只读取本地档案接口；没有 Spotify Client ID、token 或外网访问时，当前 SQLite 支持的章节仍可打开。

## 2. 页面与交互

- 封面：两张有明确角色的收藏封套、黑胶拼贴，以及收藏歌曲、专辑、艺人和歌单四项事实；不再显示覆盖期或数据状态。
- 章节：粘性横向编号条直达收藏旅程、播放多久后收藏、收藏后再次播放、找回音乐、搜索与发现、收藏库和音乐之外；章节状态写入 URL，当前项会自动滚到可见区域，两侧渐隐提示仍有章节。
- 收藏旅程：用第 100 / 200 / 400 / 800 首等倍增里程碑替代封面已经出现的最早与最近收藏。
- 收藏关系：正文展示收藏前后 30 天次数对比、“首次播放后隔了最久才收藏”的歌曲，以及 2×2 排列的 7 天内、第 8–30 天、半年后、一年后四个互补生命力指标；不展示逐周“可观察”曲线或隐藏横滑指标。
- 搜索与发现：显示去重后的星期分布、24 小时时段带和三步动作链，不展示原始查询词或内部映射数量。
- 找回音乐：歌曲名称最多展示两行，艺人和“多少天后 / 多少天未出现”进入同一正文列，不再用右侧窄列遮挡标题。
- 收藏库：正文预览 Top 5；完整目录通过 Portal 覆盖 App Shell，每页 10 条，支持类型、搜索、排序、前后翻页、直接跳页和 URL 恢复。
- 音乐之外：播客与视频卡统一使用紧凑头部加封面 Top 3；播客只显示本地已有封面，视频展示带封面和详情深链的本地可识别歌曲，不再突出悬殊的音频总时长对照。
- 全屏行为：Escape 和关闭按钮可退出，背景滚动被锁定，关闭后焦点回到原触发按钮；收藏库打开时 App Root 设置 `inert`。
- 视觉：延续暖纸、编辑红、细档案线与衬线标题；玻璃只留给现有 Shell 和临时控制层。承担含义的辅助文字统一不低于 10px，只有纯装饰序号保留 9px。

`AccountCenterPage` 现只按 `useViewportMode()` 在 `AccountArchivePhoneRoute` 与 `AccountArchiveDesktopRoute` 间互斥分流。新 Phone route 不再导入旧 profile、收藏人格、习惯人格，也不请求精确 `/api/account` 或 `/api/profile`。

## 3. 自动化证据

- 本轮修改范围 ESLint：通过。
- 前端完整回归：69 files / 504 tests passed；其中 Phone 档案 4 项组件测试覆盖本地端点隔离、收藏库跳页与焦点恢复、章节自动居中和长标题排版。
- `npm run build`：通过；账号页面异步 JS 约 55.94 kB raw / 12.35 kB gzip，CSS 约 56.12 kB raw / 8.76 kB gzip，包含两套互斥 presentation 样式。
- 真实页面 360×800、390×844、430×932 的 `documentElement.scrollWidth - innerWidth` 均为 0；390px 生命力四格为 174×142px，360px 为 161×142px。
- 390px 完整收藏库搜索、关闭、页码与跳页输入/提交控件均不低于 44px；第 1 页可直接跳到第 40 / 80 页，列表窗口更新为 391–400，关闭后背景滚动与触发按钮焦点恢复。

## 4. 真实浏览器检查

- 本轮完成亮色 360 / 390 / 430 目视复验；暗色 390 沿用初始交付验收结果。
- 364×751 人工评论复验中，封面“音乐 / 档案”行高从过度压缩恢复到清晰的双行排版；“开始翻阅”上下留白统一为 18px。
- 点击“再次播放”“收藏库”“音乐之外”后，URL、滚动位置和章节高亮一致；390px 最后一个“音乐之外”入口位于 291–366px，360px 位于 261–336px，均完整可见。
- 完整收藏库真正覆盖 Top Bar 与 Bottom Nav；页码按钮打开直接跳页面板，第 1 页可跳至第 40 页，关闭后焦点恢复到“打开完整收藏库”。
- `Running Up That Hill (A Deal With God) - 2018 Remaster` 在 390px 使用两行标题和 251px 正文列；“1240 天未出现”进入艺人下方元信息，不再遮挡标题。
- 播客与视频卡在 390px 分别约 354px、372px 高，均以总时长头部加 Top 3 组织；视频封面正常显示，播客只在本地有封面时渲染。
- 请求只命中新 `/api/account/archive-overview`、journey、cohorts、returns、discovery、library、other-media 链路，没有精确命中旧 `/api/account` 或 `/api/profile`。

关键截图位于：

- `output/playwright/account-archive-phone-360.png`
- `output/playwright/account-archive-phone-390.png`
- `output/playwright/account-archive-phone-430.png`
- `output/playwright/account-archive-phone-dark-390.png`
- `output/playwright/account-archive-phone-library-430.png`

## 5. 后续状态

Phase 4 已完成：旧人格、Marquee、粉丝等级、关键词迁移和 chemistry UI 已删除，旧 `/api/account` 聚合消费者已迁移，兼容 facade 与重型 service 已移除，API 台账和项目提示文件已同步。首页与音乐档案已完成合并，本记录继续作为 Phone 实现和人工验收证据。
