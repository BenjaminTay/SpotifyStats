# L2 自动归并治理执行与验收报告

> 状态：Pass。规则收口、代码实现、克隆演练、真实数据库治理、派生重建、真实 API、双视口浏览器和默认完整全栈门禁均已完成。证据日期：2026-08-30 至 2026-08-31；当前终态以第 8 节 v3 追补为准。
> 当前交付：实现已进入 `origin/main`，并包含在 dual 生产代码版本 `b0d674bd`；本报告的数据库数字仍是当时验收快照。
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
- 原始验收轮当时只在本地提交；2026-09-13 后续交付已将对应代码推进到 `origin/main` 并随 `b0d674bd` 部署。真实数据库和 backup 始终不进入 Git。

## 8. v3 同名强归并追补与最终终验（2026-08-31）

本节记录用户进一步确认“同 canonical artist、同普通歌名即同一首 L2 歌曲，即使时长相差较长也合并”后的 v3 追补实施。第 1—6 节保留 v2 历史执行证据；其中候选数、活动组数、revision、snapshot key 和自动决策边界如与本节冲突，以本节终态为准。

### 8.1 当前 L2/L3 口径

- L2 身份策略为 `canonical_artist_title_v3`，标题策略为 `nfkc_t2s_title_semantic_source_v4`。
- 普通标题在 canonical primary artist 与规范化歌名相同时直接机器 accepted；时长差、ISRC 不相交、来源专辑或 Soundtrack 语境只保留为 warning/evidence，不再阻止 L2 归并，也不产生人工审核队列。
- `intro`、`outro`、`interlude` 等结构性标题是硬例外：即使同艺人同规范化标题，也不自动合并。
- Acoustic、Live、Remix、Taylor's Version、Original/Single/Album Version、Extended、Radio Edit、Demo、Instrumental、Sped Up/Slowed 等显式录音语义仍保留为不同 L2 recording；只有建立 composition 关系后才可在 L3 合并。
- Album Project 与歌曲 recording 身份继续分离：Long Pond、Acoustic Collection 等发行可以进入同一专辑项目，但不会因此把其中的 Acoustic/Live 单曲在歌曲 L2 吞入原版。

这套规则将人工审核收缩到真正需要产品判断或外部事实的边界；普通同名不再因“时长差太大”“ISRC 不同”进入 pending。

### 8.2 克隆与主库治理

一次性克隆目录为 `/tmp/spotifystats-l2-governance-v3.3wVfdT`，运行 ID `7348a597-6850-4980-9171-48713362fee5`。克隆结果为 L1 操作 0、L2 创建 5 组/更新 40 组/归档 0 组/新增 10 个成员，accepted 48、pending 0、rejected 585；第二次 dry-run 无变化。

正式主库第一次运行 `c5c4d249-6f9d-45e2-897f-59d5906941a8` 在关系层完成后遇到并发候选索引生成导致的派生 fence 失败，运行被明确记录为 failed，没有原始事实破坏。随后以同策略幂等恢复运行：

- 成功运行 ID：`fe988290-2a49-436f-887f-15ae1bc48514`
- Online Backup：`data/backups/spotify_stats_20260830T144420Z_before-l2-governance.db`
- L1：操作 0；817 个多 owner 风险项继续仅审计，不自动分拆。
- L2：创建 5 组、更新 40 组、归档 0 组、新增 10 个成员；终态 46 个活动 recording group。
- 候选账本：accepted 48、pending 0、rejected 585；活动成员重叠 0。
- revision：track identity `7 → 8`，album project `2 → 3`。
- 成功后再次 dry-run：L1 0、L2 创建/更新/归档 0，证明收敛与幂等。

2026-08-31 最终全栈验收后再次只读核对：track revision 8、album revision 3、活动组 46、accepted 48、pending 0、rejected 585、重叠 0，`foreign_key_check=0`、`integrity_check=ok`。原始事实仍为：

| 原始表 | 行数 | SHA-256 |
| --- | ---: | --- |
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` |

### 8.3 真实样本与专辑项目

新增或补齐的普通同名 L2 组包括：

| 歌曲 | 成员 track ID | 结果 |
| --- | --- | --- |
| 纯妹妹 | `4546/5107/5732` | 组 `5846`，真实 API 30 次、1.6 小时 |
| Boom Clap | `1047/1469` | 同一活动 L2 组 |
| Gonna Build A Mountain | `2972/3573` | 同一活动 L2 组 |
| City of Stars | `3832/5799` | 同一活动 L2 组；来源语境不再阻止普通同名归并 |
| 有点甜 | `4384/49154` | 同一活动 L2 组 |
| 千言萬語 | `5118/5119` | 同一活动 L2 组 |

结构性反例 `INTRO` `2613` 与 `Intro` `2876` 的旧组已归档，候选因 structural title 被 rejected；两首分别保留 11 次与 5 次，不发生机器归并。

专辑项目终态：

- `The Life of a Showgirl` project `41476` 同时包含原版和 `The Life of a Showgirl + Acoustic Collection` 别名；真实 L2 API 为 1,663 次、97.4 小时。
- `folklore` project `41478` 同时包含原版和 `The Long Pond Studio Sessions` 发行别名；真实 L2 API 为 1,305 次、82.8 小时。
- 搜索结果使用稳定 `/music/album-projects/{project_id}` href；旧名称 URL 在详情数据解析后 replace 到稳定 project URL。
- 稳定项目提供 stats、rankings、plays、play-dates 与 Billboard detail 五个真实入口；API 烟测动态选择主库现存 project `41553`，五个入口全部 200，不再硬编码测试夹具 ID。

### 8.4 派生快照终态

四套精确快照均为 ready/current，每套 7,873 个 entity context、5 个年度、550 行 Year-End 投影：

| merge level | 动态阈值 | snapshot key |
| ---: | :---: | --- |
| 2 | 关 | `bc2b19830dde7f576a3deff9953b03ce8d2d8c21c8b7a8e9138664b3bdfa35cc` |
| 2 | 开 | `9017ca9f2cd9aff7f2e3d8add7cdfd8f16ced079972924b14a05e7bea40710c4` |
| 3 | 关 | `9cbceb668ba56429d90d1ac9868d5fda79bfed608a2dbf08a323f9a92b62d853` |
| 3 | 开 | `0bed4742d23ed7f66f4b84ad23eb339610da55da2be89fcd109b2e27eff5390e` |

### 8.5 UI 与默认完整门禁

- 稳定 album-project 页面已在 desktop 与 390×844 phone 真实浏览器验收；手机顶栏正确显示“专辑详情”，返回/分享可用，`clientWidth=scrollWidth=390`。
- 跨浏览器脚本对旧专辑 URL 等待实际 replace 到 `/music/album-projects/{id}`，并要求稳定页再次出现“有效播放”；避免把跳转前的短暂 DOM 当成完成态。
- 路由烟测只对唯一明确的瞬态 `net::ERR_CONNECTION_CLOSED` 允许重跑一次；第二次必须零 console/page error、零 warning、零溢出才通过，持续错误仍失败。

最终默认完整模式 `scripts/fullstack_verification_check.sh` 状态为 **PASS**，机器报告 `/tmp/spotify_fullstack_verification.json`：总耗时 2,496,788ms。

| 阶段 | 状态 | 耗时 | 关键证据 |
| --- | --- | ---: | --- |
| quality | PASS | 36,050ms | 文档审计、全文件 pre-commit、前端 610/610、production build |
| backend | PASS | 879,486ms | 2,443 passed，4 个既存环境/弃用 warning |
| api | PASS | 747,745ms | smoke 143/143、边界 113/113、211 operations 与 98 parameter obligations 均 0 未归属；热 P95 全部低于 500ms |
| browser-routes | PASS | 466,571ms | desktop/mobile 全路由与 30 个五档代表视口均通过；console/page error、warning、横向溢出均为 0 |
| browser-interactions | PASS | 90,436ms | 桌面、移动、图表交互全部通过 |
| browser-inventory | PASS | 80,297ms | 40 个页面/视口控件样本、主要触控目标尺寸违规 0；7 个长列表场景通过 |
| browser-compat | PASS | 196,025ms | Chromium、Firefox、WebKit 的路由、搜索与核心交互全部通过 |

阶段实现提交为 `a74cb5aa fix: 统一 L2 同名归并与专辑项目别名`。本轮仍只在本地提交，不 push、不部署；主库、backup、候选索引和快照均不进入 Git。
