# 音乐档案 Phase 4 退役与收口交付记录

> 日期：2026-08-13
> 分支：`codex/account-archive-rebuild`
> 范围：旧账号 UI、重型聚合服务、HTTP 兼容路由、AI 消费者、预热、OpenAPI 与项目文档；分支合并状态在本记录末尾补记

## 1. 交付结论

音乐档案重构已完成最后一阶段。运行时只剩新的本地档案页面和严格分拆接口；旧人格、chemistry、Habits、Marquee、粉丝等级和关键词迁移页面已删除，旧重型 `/api/account` 聚合与 `/api/account/collection-insights` 已从 FastAPI 和 OpenAPI 退役。

Spotify OAuth 仍只是 Settings 中可选的收藏日期补全能力。打开 `/account`、浏览收藏库、查看关系与回访均不要求 Spotify Client ID、token 或外网；部署到国内服务器时，音乐档案本身不新增 Spotify 运行时依赖。

## 2. 删除与保留边界

已删除：

- `backend/services/account_service.py`：旧收藏人格、chemistry、关键词迁移与整页大聚合；
- `GET /api/account`、`GET /api/account/collection-insights` 及两个宽松 response model；
- `frontend/src/features/account/`、`frontend/src/features/mobile/account/`、`frontend/src/pages/account/`；
- `frontend/src/hooks/useAccount.ts`、`frontend/src/types/account.ts` 及旧 query keys/type exports；
- 旧 M6 account Hero、人格标签、Habits disclosure 样式和只验证旧组件的测试。

明确保留：

- `/api/profile`、`/api/insights/tiers`、`/api/insights/marquee`、Podcast、Video 与 Wrapped Hub 等独立只读兼容/透明度接口；它们不再是音乐档案页面依赖；
- AI 工具名 `account_summary` 与 `account_collection_insights`，仅作为既有 planner、recipe 和 golden harness 的稳定标识；
- `/account` 路由继续保留；后续人工验收已将二级导航和页面正文统一命名为“音乐档案”。

架构测试新增反向护栏：旧 account、mobile account 和 page account 模块树必须保持为空；Phone route 不能导入 `useProfile` 或旧 `useAccount`。

## 3. AI 与预热迁移

`account_summary` 现在组合 archive overview，并按参数补充固定窗关系和不含原始查询词的 discovery 摘要。`account_collection_insights` 组合 overview、journey、cohorts 与 returns，返回收藏规模、覆盖率、固定观察窗、关系矩阵、回归和沉睡事实；两者均不再返回人格或 chemistry。

Project Context 提升为 `spotify-stats-project-context-v2`，明确当前收藏只是快照，禁止把关系事实包装成收藏人格或因果结论。启动 warmup 也只预热 `archive-overview`，不再构建旧整页聚合。

## 4. 契约与体积对比

| 项目 | 旧链路 | 当前链路 |
|---|---:|---:|
| 首屏 HTTP | `/api/account` | `/api/account/archive-overview` |
| raw payload | 约 456 KB | 1,936 bytes |
| 冷响应 | 约 1.8–4.2 s | 约 157–200 ms |
| 热响应 | 约 14 ms | 热 p95 约 6–9 ms |
| 响应契约 | `extra=allow` 大聚合 | `extra=forbid` 白名单 DTO |
| 长列表 | 随 summary 整批返回 | 服务端分页，Desktop 20 / Phone 10 |
| Spotify 运行时请求 | 旧页面混有身份/在线语义 | 0；只读本地 SQLite |

新页面的重章节继续渐进加载。已有真实数据采样显示，journey、cohorts、returns、discovery、other-media 和四类收藏分页 raw JSON 均低于各自 80/120 KB 预算，重统计冷构建低于 1.5 s，采样热响应低于 75 ms。当前生产构建的账号异步 JS 为 61.81 kB raw / 14.85 kB gzip，CSS 为 57.38 kB raw / 8.94 kB gzip；旧组件此前已经不在运行时依赖图，本阶段删除的主要收益是代码与契约收口，而不是虚报额外 bundle 降幅。

## 5. 验收证据

- 后端迁移定向矩阵：58 passed；扩展档案 + AI 回归为 82 passed，覆盖 archive 全领域、AI 工具、Project Context、warmup、旧路由 404 与账号 response models。
- 前端退役与页面定向矩阵：4 files / 113 passed；完整前端回归 68 files / 496 passed。
- TypeScript + Vite production build：通过；仅保留项目既有的大 chunk 提示。
- OpenAPI operation audit：192 operations，110 safe GET smoke / 73 targeted contract / 9 controlled，0 unaccounted。
- OpenAPI parameter boundary audit：89 obligations，0 unaccounted。
- 项目 Phase 5 基线：unit 876 passed / 2 skipped，contract 325 passed，backend Ruff 通过，前端 68 files / 496 passed，production build 通过。
- 全量基线额外发现并修复收藏库“不支持的实体排序”422 仍返回字符串的问题；现在返回带 `loc=[query, sort]` 的标准 validation detail，API boundary probe 通过。
- 生成的 OpenAPI snapshot 与 TypeScript types 已刷新，旧两条路径和旧 response model 不再出现。
- 既有 Phone / Desktop 实页证据继续成立：五视口 route matrix、可访问控件、长列表、Chromium / Firefox / WebKit 均已通过，页面请求日志未命中旧聚合或 `/api/profile`。

## 6. 集成状态

本批次最初在 `/Users/benjaminlei/Code/202605-SpotifyStats-account-archive` 的 `codex/account-archive-rebuild` 上独立完成。首页完成后，两边通过单独的冲突预检合并进入 `main`；其后的 Desktop / Phone 人工验收修复均在合并后的工作树继续收口。
