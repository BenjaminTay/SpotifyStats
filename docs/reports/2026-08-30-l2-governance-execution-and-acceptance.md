# L2 自动归并治理执行与验收报告

> 状态：Pass。规则收口、代码实现、克隆演练、真实数据库治理、派生重建、真实 API、双视口浏览器和默认完整全栈门禁均已完成。证据日期：2026-08-30。
> 当前规则：[`../reference/music-metadata-management.md`](../reference/music-metadata-management.md)、[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)

## 1. 最终口径

| 层级 | 身份语义 | 本轮边界 |
| --- | --- | --- |
| L1 | 稳定 provider owner | 不做歌曲版本或专辑项目合并；只安全收口已证明属于同一 owner 的 relink/历史投影，并清理零播放、无外部身份的兼容壳 |
| L2 | 同一首歌的 recording 口径 | canonical primary artist 与语义规范化标题相同默认机器归并；无需人工逐条审核 |
| L3 | 同一作品的 composition 口径 | Acoustic、Live、Remix、Taylor's Version 等跨录音关系只在 composition 关系存在时进一步归并 |

L2 的“同艺人 + 同歌名”仍是主规则。标题规范化会合并简繁、大小写、等价标点、Explicit/Clean、Bonus、Remaster 等发行标签，但保留 Acoustic、Live、Remix、Radio Edit、Demo、Instrumental、Taylor's Version、Original/Single/Album Version、Extended、Sped Up/Slowed 等录音语义。

为了让机器处理更多对象且避免制造明显错组，自动决策使用 `accepted/rejected/pending` 三态：普通同艺人同语义标题直接 accepted；通用短标题在 ISRC 不相交且时长差至少 10 秒时 rejected；Soundtrack 等来源语境与无语境标题只有共享 ISRC 且时长兼容才 accepted；双方均无播放、外部 ID 和来源事实时 pending。rejected/pending 都不建活动组，不会形成新的人工审核队列。

专辑 L2 使用 Album Project。标准版、豪华版、Acoustic Collection、Long Pond 等只要满足正式主体曲目与发行证据，就可属于同一专辑项目；这不会把其中 Acoustic/Long Pond 单曲在歌曲 L2 与原版录音合并。精选集产品策略仍冻结，自动任务不改变 compilation membership 或榜单资格。

## 2. 实施内容

- 标题策略升级为 `nfkc_t2s_title_semantic_source_v3`，L2 身份策略升级为 `canonical_artist_title_v2`。
- L2 规划器支持三态候选、无序 pair 幂等、人工 `force_separate/force_merge` 优先级、非 canonical 成员清理和旧候选状态收敛。
- L1 自动治理只处理同 canonical artist、共享 ISRC、时长差不超过 2 秒且语义兼容的安全目标；不会凭标题创建新 L1。零播放且无外部身份的 shadow identity 标为 superseded。
- 治理执行器在同一关系事务内最多运行两轮 L1 → L2，第三轮只读检查收敛；track revision 只发布一次。执行前后校验原始表 hash、identity/group/FK/integrity 不变量。
- 运行头先于关系事务持久化；成功和失败均保留 run 状态，每个变更写入 before/after/evidence。治理 CLI 结束后无论成功或失败都恢复原 `DB_PATH`，不会污染后续任务或测试进程。
- Album Project 在关系变更后强制重建 membership；四套 L2/L3 × 动态阈值开关的音乐查找 snapshot 和四套 Year-End 投影必须同事务 ready，失败时不激活半套派生数据。
- 公开 `/music/tracks/{track_id}` 与 Billboard 详情优先使用同 ID 的活动 L1 owner；仅在不存在稳定 owner 时回退历史 source link，避免代表 track ID 因历史 fan-out 被误报 409。

## 3. 克隆演练与真实数据库执行

正式执行前在一次性克隆库完成两轮演练：L1 共 2,721 个操作，L2 第一轮变化、第二轮稳定，第三轮收敛检查为 L1 操作 0、L2 `changed=false`；track revision 只增加 1，原始事实 hash 不变，`foreign_key_check=0`、`integrity_check=ok`。同一克隆再次 dry-run 保持无变化。

正式本地库治理运行 ID：`3b4b395b-2895-41f3-8d9d-156eb0d3a4c1`。执行前使用 SQLite Online Backup 保存：

`data/backups/spotify_stats_20260830T122202Z_before-l2-governance.db`

数据库 schema 为 67，治理结果为 `applied`，共记录 3,448 个审计事件。原始事实表在治理后及最终验收时均保持以下值：

| 原始表 | 行数 | SHA-256 |
| --- | ---: | --- |
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` |

关系层执行结果：

- L1 共执行 2,721 个安全 shadow/relink 收口操作；817 个多外部 ID 风险 owner 保留为审计集合，安全自动分拆为 0，没有冒险改写基础 owner。
- L2 最终有 41 个活动 recording group：40 个机器组、1 个人工组；本轮更新 40 组、归档 46 个错误自动组、移除 92 条成员关系，没有创建低证据组。
- 当前候选账本为 accepted 43、pending 3、rejected 583。账本包含历史 pair 状态，因此 accepted 数不等于活动组数。
- 活动组成员重叠 0、少于两个成员 0、无效 primary 0；active group 非 canonical 成员、pending 非 canonical 引用、identity/source/external owner orphan 均为 0。
- Album Project 本轮无新的 catalog merge 候选，但因 L1/L2 关系变化强制重建 membership；track revision `6 → 7`，album project revision `1 → 2`。
- 正式库执行后再次 dry-run：L1 操作 0、L2 创建/更新/归档均为 0、Album Project 新候选 0，证明幂等。

## 4. 真实数据复核

保留的正确 L2 归并：

- “纯妹妹”组 `5846`：`4546/5107/5732`，代表 `4546`；真实 API 和页面均为 30 次、1.6 小时，播放明细保留三个来源版本。
- “手心的薔薇”组 `5874`：`852/4309`，代表 `4309`；聚合 87 次。
- “For Good”组 `5924`：`3559/4266`，代表 `3559`；聚合 99 次。

已拆开的代表性误合并：

| 对象 | 修复后结果 |
| --- | --- |
| `the lakes - bonus track` `310` / 原版 `1095` | L2 分开；分别 54 次与 1 次 |
| `Thriller` `2405` / `Single Version` `4176` | L2 分开；分别 1 次与 1 次 |
| `Loverboy - Original Version` `3070` / 基础版 `3736` | L2 分开；分别 11 次与 1 次 |
| `INTRO` `2613` / `Intro` `2876` | L2 分开；分别 11 次与 5 次 |
| `City Of Stars - From ... Soundtrack` `3832` | 不再保留无证据单成员活动组；自身 7 次 |

专辑项目结果：

- `The Life of a Showgirl` project `41476` 包含原版和 `+ Acoustic Collection` 两张发行、33 首项目曲目；真实 L2 API 为 1,663 次、97.4 小时、30 首唯一曲目。
- `folklore` project `41478` 包含原版及两张 `The Long Pond Studio Sessions` 发行、34 首项目曲目；真实 L2 API 为 1,305 次、82.8 小时、34 首唯一曲目。
- Album Project 会共同统计额外录音，但歌曲 L2 仍保留各 recording key，符合“Long Pond 可进专辑项目、Acoustic 不在歌曲 L2 吞掉原版”的产品边界。

## 5. 派生数据、API 与浏览器

四套精确快照均为 ready/current，每套 7,874 个 entity context；四套 Year-End 投影各 550 行、覆盖 5 年：

| merge level | 动态阈值 | snapshot key |
| ---: | :---: | --- |
| 2 | 关 | `9618c0280cda437d5a780c61c8f99b44cb7da205635e5f038a765c3e4cb4b1b2` |
| 2 | 开 | `eab66be3ab3a576340844de7b862dc43e75ccc4b609cc849853d46e5313640a2` |
| 3 | 关 | `1db21501a7931a7178675ef70b2547b5d51eb84e4a2e5ff525753b4136823184` |
| 3 | 开 | `d529ba81e13477f283a72584e96bd2715d003787849e0c37038cd111d95a8de2` |

当前真实库没有活动 composition group，因此当前 L2 与 L3 结果暂时相同；这是数据状态，不代表层级语义相同。

真实浏览器额外验收：

- Desktop 1440×1000 与 Phone 390×844 打开 `/music/tracks/4546` 均展示 30 次，三个来源版本均出现在明细中。
- 390px 下 `clientWidth=390`、`scrollWidth=390`，控制台 error 0。
- `/music/tracks/2405` 展示 Thriller 自身 1 次，不再混入 Single Version；控制台 error 0。
- 截图和快照只保存在本地 `output/playwright/l2-governance-final/`，不提交个人音乐数据。

## 6. 自动化验收

- L2/L1/治理编排定向回归：160 passed；代表 ID 解析定向契约：11 passed；执行器路径隔离相关回归：23 passed。
- 后端 unit：1,474 passed；contract：403 passed。
- 前端 Vitest：607 passed；TypeScript 与 Vite production build passed。
- 文档审计和全文件 pre-commit passed。
- 默认完整全栈矩阵：**Pass**，总耗时 3,114,396ms。
  - quality 53,940ms
  - backend 1,012,705ms：2,415 passed
  - API 914,942ms：smoke 138/138、边界 112/112、OpenAPI 206 operations 无遗漏，热端点 P95 全部低于 500ms
  - browser routes 726,002ms：54 个 desktop/mobile 组合和 30 个五档代表视口全部通过，console/page error、warning、横向溢出均为 0
  - browser interactions 95,356ms：桌面、移动、图表交互全部通过
  - browser inventory 94,341ms：2,141 个控件、418 个主要触控目标，违规 0；7 个长列表场景通过
  - browser compatibility 216,831ms：Chromium、Firefox、WebKit 全部通过

## 7. 边界、回滚与 Git

- 817 个 L1 风险 owner 是待更多 provider 证据的审计集合，不等于 817 个已确认错误；本轮没有为了降低人工量而冒险分拆。
- 精选集策略和 L3 composition 关系仍是明确未自动推断的产品边界，不影响本轮 L2 修复完成状态。
- 回滚优先恢复本报告记录的 Online Backup；搜索 snapshot 和 Year-End 投影是可重建派生数据。
- 核心收紧提交：`7a0ec623 fix: 收紧 L2 自动归并与治理发布门禁`。
- 代表详情解析提交：`7e91e8e5 fix: 修复 L2 代表曲目详情解析`。
- 本轮只在本地提交，未 push、未部署；真实数据库和 backup 不进入 Git。
