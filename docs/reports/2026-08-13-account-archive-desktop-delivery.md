# 音乐档案 Desktop / Compact 交付记录

> 日期：2026-08-13
> 分支：`codex/account-archive-rebuild`
> 范围：`/account` 的 Desktop / Compact 页面、前端数据层、收藏库交互与真实浏览器验收；Phone 暂时保留原 presentation

## 1. 交付结论

Desktop 与 Compact 已从旧“账号中心”切换为本地优先的“音乐档案”。新页面不再把 Spotify 在线身份放在首屏，也不请求旧 `/api/account` 聚合或 `/api/profile`；没有配置 Spotify OAuth 时仍可完整打开核心档案。

页面使用“私人唱片档案”而非通用 dashboard 的视觉模型：纸张纹理、编号章节、唱片封套与编辑式排版承担主体层级，玻璃材质只用于导航和工具控件。Desktop 使用粘性纵向索引，Compact 使用粘性横向章节条；Phone 将在下一阶段单独实现“口袋音乐档案”。

## 2. 已交付内容

- 档案封面：当前收藏、歌单数、关联播放覆盖、准确收藏总时长和四个可核验收藏故事。
- 收藏旅程：年度新增、累计增长、发行年代跨度和关键收藏里程碑。
- 从遇见到收藏：收藏前后固定观察窗、30 天对称比较与样本边界。
- 收藏之后：回访节点、关系矩阵与成熟样本说明。
- 找回音乐：回归概览、代表回归与沉睡收藏，不把“尚未回访”写成放弃。
- 发现路径：只展示搜索过程、时段与有限事件链，不向浏览器发送原始查询词。
- 收藏库：歌曲、专辑、艺人、歌单四类服务端搜索、排序和分页，每页最多 20 条，状态写入 URL。
- 音乐之外：播客和视频的保守累计事实；没有单集时长时不伪造完播率。

## 3. 前端结构与状态

- `AccountCenterPage` 只负责 presentation 分流：Phone 暂时使用旧组件，Desktop / Compact 进入新 route container。
- 所有 GET 读取通过 TanStack Query 和 `queryKeys.account.archive*`；默认 `staleTime=5min`、`gcTime=30min`。
- 各章节使用 IntersectionObserver 渐进加载；直接打开 `?section=library` 时会在请求和布局变化结束前保持章节锚点，避免 URL 被错误回写到前一章。
- 收藏库使用 `library`、`sort`、`search`、`page` 查询参数，可分享并支持浏览器前进/后退。
- Spotify 导出项使用不可逆稳定键作为列表身份；本地 catalogue id 只负责详情深链，避免多个 Spotify 版本映射到同一本地实体时出现重复键。
- route container 为 91 行，数据 hooks、导航协调、统计模型和 presentation 分层放置，符合 Phase 5 薄路由约束。

## 4. 验收证据

自动化结果：

- 账号档案后端单元测试：30 passed。
- 前端定向矩阵：5 files / 126 passed，覆盖新 route、query hooks、Phase 5 架构与旧 Phone 回归。
- 新增/修改文件 ESLint：通过。
- `npm run build`：通过；账号页面异步 JS 约 84.31 kB raw / 21.14 kB gzip，CSS 约 30.62 kB raw / 5.62 kB gzip。

真实数据浏览器验收：

- 1280、1024、768 三个视口横向溢出均为 0。
- 亮色与暗色主题均完成目视检查。
- 冷打开 `?section=library` 后 URL 保持不变，目标章节顶部稳定在约 80 px。
- 专辑切换后 URL 为 `library=albums&sort=name`；搜索 `Taylor` 后服务端返回 27 条、首屏渲染 20 条。
- 请求日志只出现 `/api/account/archive-overview`、journey / cohorts / returns / discovery / library / other-media 等新链路，没有精确命中旧 `/api/account` 或 `/api/profile`。
- 唯一浏览器控制台错误来自当前 worktree 复用另一 worktree `node_modules` 时 Vite 对 `@fs` 字体路径的 403 限制；生产构建已正常输出 Inter 字体资源，不属于页面运行错误。

## 5. 尚未完成

下一阶段只处理独立 Phone presentation，包括手机封面、章节切换、纵向故事卡、全屏收藏库、触控目标和 360 / 390 / 430 真机尺寸验收。两条 Git 分支仍不做同步、rebase 或合并，待首页与音乐档案各自完成后统一处理冲突。
