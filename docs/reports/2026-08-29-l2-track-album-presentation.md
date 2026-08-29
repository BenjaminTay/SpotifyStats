# L2 歌曲专辑归属与封面选择交付报告

> 状态：已实现、核心代码已本地提交、规则与真实数据已验证；未 push、未部署。证据日期：2026-08-29。

## 交付结果

L2 同录音版本现在共享一份结构化 `TrackPresentation` 结果，专辑归属与封面来源不再由各消费端自行推断：

- 归属优先原版非合辑录音室全长专辑；原版未收录时才使用收录该曲的豪华版；没有可用 album project 时回退到独立单曲或 EP。
- 封面独立决策：存在真实单曲发行时优先单曲封面，但不改变专辑归属；豪华版独占且无单曲时使用豪华版封面。
- 原版收录判断只接受同一消歧 provider 曲目表或 ISRC 等价证据，不把不同版本的跨链接曲目表并集当作原版收录。
- 合辑不会覆盖已确定的正式归属；来源播放明细继续展示每次播放实际来自的专辑与封面。

对外结构同时保留 `album_project_id/name`、`display_album_id/name`、`membership_role`、`cover_album_id/url/source` 和 `resolution_status`，便于后续排查与演进。

## 一致性范围

统一解析结果已接入歌曲详情、音乐查找与其派生文档、Billboard 曲目投影、播放排行、记录发现、年度总结和相关公共播放卡片。专辑项目重建会递增独立 revision；搜索 generation 的 filter context 同时包含该 revision 与 presentation policy version，避免旧 generation 静默复用旧归属或旧封面。

2026-08-30 补充收口轻量歌曲 identity：`/api/music/tracks/{canonical_track_id}` 与 legacy identity 现在也批量消费同一 TrackPresentation，并返回结构化 `album_attribution`；`/sources` 仍保留实际来源语义。真实库复核 `Opalite` 为原版 album 1894 归属、单曲 album 2313 封面，`The Fate of Ophelia` 为原版 album 1894 归属、单曲 album 2031 封面，均与搜索和统计详情一致。

迁移 64 增加 album project revision 状态，迁移 65 为结构化搜索文档增加 presentation 字段。真实数据库已完成迁移，并通过 shadow generation 原子发布新搜索派生数据。

## 真实数据证据

| 曲目 | 归属结果 | 封面结果 | 状态 |
| --- | --- | --- | --- |
| `vampire`（canonical track 1493） | `GUTS`，display album 597 | 单曲发行 569，`/covers/albums/569.jpg` | `standard` / `single` |
| `Irreplaceable`（canonical track 1659） | `B’Day`，display album 668 | 按规则解析 | `standard` |
| `Hampstead`（canonical track 4280） | `eternal sunshine deluxe: brighter days ahead`，display album 1811 | 豪华版 1811 | `deluxe` |

`vampire` 的真实来源播放仍能区分 `GUTS`、`vampire` 单曲和 `GUTS (spilled)`；API 分页汇总分别返回 218、154、6 个逻辑播放明细，封面分别为来源专辑 597、569、1171，而详情抬头仍稳定为 `GUTS` + 单曲封面。

搜索 shadow rebuild 发布 generation `20260829T110452-436f99b53bb2`，四个必需变体均为 ready，精确统计快照复用成功，发布门禁通过。

## 自动化与浏览器验收

- 新增 TrackPresentation contract 回归：7 passed，覆盖原版 + 单曲封面、豪华版独占、L2 成员一致、合辑独占、跨链接不得误升原版、revision 失效和独立单曲回退。
- 后端 unit + contract：1826 passed，516 deselected，2 warnings。
- 前端：76 个测试文件、598 tests passed；生产构建通过，仅保留既有 chunk-size warning。
- pre-commit：ruff、ruff format、mypy、secret detection 全部通过。
- 真实 API：track 1493 返回 `display_album_name=GUTS`、`cover_album_id=569`、`cover_source=single`；搜索候选副标题为 `Olivia Rodrigo · GUTS`，封面为 `/covers/albums/569.jpg`。
- 真实浏览器 1440×1000 与 390×844：`vampire` 均显示 `GUTS` 与单曲封面；`Hampstead` 显示豪华版归属与 `/covers/albums/1811.jpg`；无横向溢出，控制台 0 error。
- 默认完整全栈门禁最终 **PASS**：文档审计 139 个 Markdown；后端 2344 passed、4 个既有环境/弃用 warning；API smoke 138/138、参数边界 112/112；前端 76 个测试文件、598 tests passed，生产构建通过。
- 性能门禁所有热端点 P95 均低于 500ms：`/api/billboard/weekly` 170ms、`/api/billboard/all-time` 210ms、`/api/dashboard/full` 370ms。为消除数 MB Billboard JSON 在缓存命中后仍被 gzip level 9 重压缩的 CPU 开销，中间件显式使用 level 5；30 次定向热采样和配置回归测试均通过，响应事实不变。
- 浏览器门禁：52 个 Desktop/Phone 路由检查、30 个五档视口代表检查、桌面/移动导航和 ECharts 交互、40 个控件清单组合与长列表场景全部通过；1976 个控件、388 个移动主要触控目标均无违规。Chromium、Firefox、WebKit 的真实实体详情和核心交互全部通过，控制台 error/warning、page error 与横向溢出均为 0。

## Git 与外部状态

- 核心实现提交：`1d01b099 feat: 统一 L2 歌曲专辑归属与封面选择`
- 迁移版本同步：`47431f1c fix: 同步最新数据库迁移版本`
- 首页解析范围优化：`467ad2ff perf: 限定首页歌曲封面解析范围`
- 大响应在线压缩优化：`e83710dd perf: 降低大响应在线压缩开销`
- 本报告及规则文档在上述实现和完整验收之后独立提交。
- 未执行 push、生产部署或外部数据写入。
