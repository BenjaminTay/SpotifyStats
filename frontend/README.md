# SpotifyStats 前端开发说明

前端位于 `frontend/`，使用 React、TypeScript、Vite、Tailwind CSS、React Router、TanStack React Query、ECharts 和 Vitest。

## 快速开始

```bash
npm ci --legacy-peer-deps
npm run dev
npm test
npm run build
```

默认开发地址为 `http://localhost:5173`，API 由 Vite proxy 转发到 `http://127.0.0.1:8000`。

## 路由入口

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

官方 Wrapped 只保留后端兼容边界，不再作为前端消费页面。旧 Billboard 详情路径只负责兼容跳转到 `/music/*`。

播放分析二级顺序固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 音乐档案”。Phone、Compact、Desktop 共享路由状态、Query、过滤指纹和统计事实，但使用互斥 presentation。

## 目录结构

```text
src/
├── api/              API 客户端、QueryClient、queryKeys 和类型
├── features/         按业务域组织的页面内容
├── components/       UI、图表、布局和共享 primitives
├── pages/             路由级容器，只负责组合
├── hooks/             领域 hooks
├── lib/               日期、主题、简繁转换等基础工具
├── tests/             单元、组件和架构护栏测试
└── types/             展示层 TypeScript 类型
```

详细架构约束见 [`CLAUDE.md`](CLAUDE.md)，视觉规范见 [`UI_STYLE_GUIDE.md`](UI_STYLE_GUIDE.md)。

## 数据获取规则

- 所有 GET 请求使用 TanStack Query 和 `queryKeys`。
- 禁止模块级 `Map` 缓存 API 响应。
- 默认 Query 配置为 stale time 5 分钟、gc time 30 分钟、retry 2 次；搜索候选请求按搜索专用规则使用 `retry: 0`。
- 音乐搜索先请求候选，再按稳定实体 key 请求精确统计 context；未加载 context 不得显示为 0。
- 页面离开只取消当前 HTTP 等待，不取消服务端后台任务。

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

## 验证

```bash
npm test
npm run build
node ../scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node ../scripts/frontend_cross_browser_smoke.mjs --include-detail-routes
```

真实浏览器、生产 preview 和后端 API 的完整验证入口见根目录 `CLAUDE.md` 与 `scripts/fullstack_verification_check.sh`。
