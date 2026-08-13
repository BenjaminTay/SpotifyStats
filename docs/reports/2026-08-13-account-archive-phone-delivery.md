# 音乐档案 Phone 交付记录

> 日期：2026-08-13
> 分支：`codex/account-archive-rebuild`
> 范围：`/account` 的独立 Phone presentation、全屏曲线与收藏库、移动门禁；旧兼容链路已由后续 Phase 4 删除，仍不包含分支合并

## 1. 交付结论

Phone 已从旧账号 Hero 和桌面内容折叠壳切换为独立“口袋音乐档案”。它与 Desktop / Compact 共享本地统计事实、TanStack Query、过滤参数、URL 和格式化模型，但不会同时挂载桌面长列表或宽图。

页面仍使用既有 `/account` 路由和二级导航“账号中心”，正文明确叫“音乐档案”。运行时只读取本地档案接口；没有 Spotify Client ID、token 或外网访问时，当前 SQLite 支持的章节仍可打开。

## 2. 页面与交互

- 封面：两张有明确角色的收藏封套、黑胶拼贴、2×2 档案事实、收藏覆盖期和数据状态深链。
- 章节：粘性横向编号条直达收藏旅程、遇见收藏、收藏之后、找回音乐、发现路径、收藏库和音乐之外；章节状态写入 URL。
- 收藏关系：正文保留 7 / 30 / 90 / 365 天固定窗结果，逐周曲线进入 `MobileFullscreenChart`。
- 发现路径：只显示去重后的星期分布、24 小时时段带和有限事件链，不展示原始查询词。
- 收藏库：正文预览 Top 5；完整目录通过 Portal 覆盖 App Shell，每页 10 条，支持类型、搜索、排序、分页和 URL 恢复。
- 全屏行为：Escape 和关闭按钮可退出，背景滚动被锁定，关闭后焦点回到原触发按钮；收藏库打开时 App Root 设置 `inert`。
- 视觉：延续暖纸、编辑红、细档案线与衬线标题；玻璃只留给现有 Shell 和临时控制层。

`AccountCenterPage` 现只按 `useViewportMode()` 在 `AccountArchivePhoneRoute` 与 `AccountArchiveDesktopRoute` 间互斥分流。新 Phone route 不再导入旧 profile、收藏人格、习惯人格，也不请求精确 `/api/account` 或 `/api/profile`。

## 3. 自动化证据

- 新增/修改范围 ESLint：通过。
- 前端定向回归：5 files / 104 tests passed。
- `npm run build`：通过；账号页面异步 JS 约 61.81 kB raw / 14.84 kB gzip，较 Desktop 交付时约 84.31 kB raw / 21.14 kB gzip 继续下降；CSS 约 57.38 kB raw / 8.94 kB gzip，包含两套互斥 presentation 样式。
- 生产 route matrix：360×800、390×844、430×932、768×1024、1280×800 全部通过；每个组合 console error / warning、page error 和横向溢出均为 0。
- control inventory：Phone `/account` 共 20 个可见控件，20 个均有可访问名称；8 个主要触控目标，无小于 44px 项，0 violation。
- 长列表门禁：Desktop 收藏库从第 1 / 40 页切换到第 2 / 40 页，20→20 行窗口更新；0 console error / warning，0 横向溢出。Phone 完整目录另以真实浏览器确认每页 10 条。
- 跨浏览器：Chromium、Firefox、WebKit（Safari-family）的 Desktop 与 Phone `/account` 均通过 route marker，0 横向溢出。

## 4. 真实浏览器检查

- 亮色 360 / 390 / 430 与暗色 390 均完成目视检查。
- 点击章节后 URL 与滚动位置稳定；`section=returns`、`section=library` 可刷新恢复。
- 完整收藏库真正覆盖 Top Bar 与 Bottom Nav；类型切换、`Taylor` 搜索、分页和 Escape 均正常，关闭后焦点恢复到“打开完整收藏库”。
- 全屏逐周曲线可由 Escape 关闭，焦点恢复到“查看完整回访曲线”。
- 请求只命中新 `/api/account/archive-overview`、journey、cohorts、returns、discovery、library、other-media 链路，没有精确命中旧 `/api/account` 或 `/api/profile`。

关键截图位于：

- `output/playwright/account-archive-phone-360.png`
- `output/playwright/account-archive-phone-390.png`
- `output/playwright/account-archive-phone-430.png`
- `output/playwright/account-archive-phone-dark-390.png`
- `output/playwright/account-archive-phone-library-430.png`
- `output/playwright/account-archive-phone-chart-390.png`

## 5. 后续状态

Phase 4 已完成：旧人格、Marquee、粉丝等级、关键词迁移和 chemistry UI 已删除，旧 `/api/account` 聚合消费者已迁移，兼容 facade 与重型 service 已移除，API 台账和项目提示文件已同步。当前分支继续与首页工作树隔离，不同步、rebase 或合并。
