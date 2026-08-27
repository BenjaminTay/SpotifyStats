# Canonical Track 与 L2/L3 版本治理交付报告

> 状态：Pass（最终语义、核心实现、真实数据库迁移、数据审计、完整测试和默认全栈门禁均已通过）
> 证据日期：2026-08-27
> 文件名说明：文件名沿用早期 Spotify-L1 方案以保持历史链接兼容；正文记录最终实施语义
> 当前规则：[`../reference/music-metadata-management.md`](../reference/music-metadata-management.md)、[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)

## 1. 最终决策

歌曲的基础身份是稳定的本地 canonical track，不是可切换的统计层级，也不等于某一个 Spotify ID。

| 层次 | 当前语义 | 用户是否可切换 |
|---|---|---|
| 原始事实 | `plays`、`tracks`、`track_artists` 及导入时 provider 证据 | 否，完整保留 |
| 基础身份 | 本地 canonical track；一个身份可拥有多个 provider ID | 否，仅高级纠错 |
| L2 | 同一录音/母带的不同基础身份 | 是，默认公共统计层级 |
| L3 | 同一作品的重录、现场、原声、Remix 等版本 | 是，可选公共统计层级 |

数据库兼容表和部分字段继续使用 `track_l1_*` / `l1_id` 名称，但其产品语义已经冻结为 canonical track。它们是兼容名称，不代表公共 L1 开关。

必须始终成立的硬规则：

1. 一个 canonical track 可以拥有多个 `(provider, external_track_id)`。
2. 同一个 `(provider, external_track_id)` 只能有一个活动 canonical owner；数据库唯一约束、事务冲突回滚和健康审计共同保证这一点。
3. 新出现的不同 Spotify ID 默认建立不同 canonical track；标题、艺人、ISRC 或时长相似不能自动做基础身份合并。
4. 同一 Spotify ID 的多条历史来源自动投影到同一个 canonical track，不建立 L2/L3 组。
5. 只有明确的底层误拆/误合才能通过高级治理进行 merge/split，并且必须保存依据、revision 与审计事件。
6. L2/L3 只表达版本关系，不改写原始事实。

## 2. 实施范围

- schema 48–58 建立身份证据并最终收口为“现有 Track ID + Spotify owner”模型；schema 58 进一步统一手动候选、已保存分组、代表版本与待确认候选的 owner 解析。
- 导入和元数据刷新统一调用 `backend/domains/metadata/track_identity.py`；provider owner 冲突会回滚，不会把同一 Spotify ID 写入两个身份。
- 搜索、歌曲详情、播放分析、Billboard、年度总结、音乐档案、首页和 AI 工具先读取 canonical track，再应用 L2/L3。
- 公共 API 的 `merge_level` 只接受 2 或 3；前端 `MergeLevel` 只包含 `2 | 3`，历史 URL/本地值 `1` 自动归一为 `2`。
- canonical API 和详情路由取代公开 L1 路由；旧 `/music/tracks/l1/{id}` 仅做兼容重定向。
- 歌曲和专辑共享“自动检测 / 已保存分组 / 手动创建”信息架构及三步手动流程；歌曲可以明确选择两个基础身份并选择 L2/L3。
- 详情页“编辑”改为任务选择器：归并歌曲版本、调整曲目署名、管理艺人身份。
- 基础身份 merge/split/audit 只放在折叠的“高级：基础身份纠错”中，和普通版本归并隔离。

## 3. 真实数据库迁移与不变量

迁移前通过 SQLite Online Backup 保存：

`data/backups/spotify_stats.before-governance-owner-normalization-20260827.db`

正式本地库已迁移到 schema 58，`integrity_check=ok`。迁移前备份与迁移后数据库的三张原始表双向 `EXCEPT` 均为 0，逐行摘要完全一致：

| 原始表 | 行数 | SHA-256 |
|---|---:|---|
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 12,649 | `c0f4fb98f71d28a4c45e53e4774a494d3b72e5a5f4fcb3ac84ef978010179bf2` |
| `track_artists` | 13,083 | `c85572aebe8c549be3ed75df516132e841776e012b6cd6c49e4d99db5d984960` |

迁移后身份健康：

| 不变量 | 结果 |
|---|---:|
| 活动兼容身份行 | 12,649（与现有 Track ID 一一对应，不是公共身份命名空间） |
| Spotify external owner | 7,843 |
| 已播放 distinct Spotify ID | 7,843 |
| 同一 external ID 多 owner | 0 |
| 未解析播放 | 0 |
| external owner / source orphan | 0 / 0 |
| 缺少代表记录 | 0 |
| unresolved / superseded identity | 0 / 0 |
| 多 Spotify ID owner Track | 817，最多 7 个 |
| 活动 L2/L3 歌曲组 | 1 |
| 已归档旧组 | 23 |
| 待审候选 | 0；与活动组相同的历史候选已同步为 accepted |
| 活动组成员重叠 / 冲突 | 0 / 0 |
| 活动组非 owner 成员 / 无效代表 | 0 / 0 |
| pending 非 owner 候选 | 0 |

完整后端测试首次发现 schema 50 清空 canonical 粒度聚合后，艺人 revision 状态与四张表的整体就绪性没有被正确区分。schema 56 清除无效 `agg_config` 并失效依赖快照；schema 57 按播放时 Spotify owner 重建正确的现有 Track ID 粒度聚合。schema 58 不修改播放聚合，迁移前后 `agg_weekly_tracks` 与 `agg_weekly_track_sources` 双向 `EXCEPT` 均为 0。当前曲目聚合 37,832 行、来源 51,559 行，两者均为 66,436 次、15,106,724,870 ms。

目标歌曲“假如我們還愛著”现在只有一个面向用户的 owner Track `5734`，Spotify ID `5DpQ7EYvM9aCG90luO9PQW`、4 条历史来源、艺人“單依純”。历史 Track `4548/10605/11791` 会解析到 `5734`，不再出现在手动候选。此前把“纯妹妹”组判断为同一 Spotify ID 的伪 L2 组并不准确：Track `4546` 实际拥有播放时 Spotify ID `5tqjFAm0Byo65VmopgMMh6`，Track `5732` 拥有 `2YvzVstQ1VPKESFqvfqIFk`，因此该组是两个不同 owner 的有效 L2 关系，schema 58 保留该组并把重复 pending 证据同步为 accepted。

## 4. 搜索和派生状态

schema 55 把所有公共 L1 快照以及非当前 builder 的旧快照标为 stale；schema 56 在 canonical 聚合未完整发布时继续失效派生状态。当前精确 ready 集合只有四套：

- 动态阈值 L2 / L3
- 固定阈值 L2 / L3

四套均使用 `music_search_snapshot_v8_canonical_track`，指纹互不重复；重复维护可精确复用，真实库复验耗时 184.479 ms。旧 v7 和 L1 证据仍保留为 stale，不会被公共读取路径误用。

身份 projection 刷新只在 owner、代表、来源关系或展示语义变化时递增 identity revision；仅观察次数/日期变化不会触发全量语义失效。该修复同时恢复 Billboard 开放周增量与全量结果等价。

## 5. API 与事务安全

- canonical merge、split、audit API 已覆盖成功路径、冲突、审计记录和事务回滚。
- 公共 `merge_level=1` 返回参数错误；OpenAPI 的最小值为 2，旧 L1 API 不再出现在公开 schema。
- 同一 Spotify ID 的重复写入由 external owner 唯一约束阻断；失败事务不会留下半成品身份、来源或审计记录。
- 历史详情链接 `/music/tracks/l1/5200?merge_level=1` 实测重定向到 `/music/tracks/canonical/5200?merge_level=2`。

## 6. 用户体验验收

Desktop 1440×1000 与 Phone 390×844 使用真实浏览器验收；“已保存分组”使用正式数据库的隔离副本临时构造一个有效 L2 组，不写正式库。

通过项：

- 顶层类别和当前内容不再重复显示同名标题；“自动检测 / 已保存分组 / 手动创建”选项下也不再重复同名标题。
- 歌曲与专辑都具有同一套工作方式和“选择成员 → 配置规则 → 确认保存”三步手动流程。
- 普通界面和默认统计中均无 L1 选项，只显示 L2/L3；基础身份纠错明确折叠在高级区域。
- 已保存分组卡片和成员行的三张封面均加载成功，艺人均显示“單依純”，没有“未知艺人”，页面级横向溢出为 0。
- 详情页编辑入口同时提供归并版本、曲目署名和艺人身份，不再直接跳到署名页。
- Phone 使用专属高级数据管理页面，390px 下 `scrollWidth=clientWidth=390`，当前视口内交互控件均不低于 44px。
- 浏览器控制台 0 error、0 warning。
- 手动搜索“假如我们还爱着”、历史 Track ID `4548` 或 Spotify ID `5DpQ7EYvM9aCG90luO9PQW` 均只返回 Track `5734`。
- “纯妹妹”已保存组展开后明确显示两个不同 Spotify ID，不再依据遗留 `tracks.spotify_track_id` 错判成员身份。

本地截图（不提交个人音乐信息）：

- `output/playwright/canonical-settings-desktop-saved.png`
- `output/playwright/canonical-settings-copy-saved-members.png`
- `output/playwright/canonical-settings-phone.png`
- `output/playwright/acceptance-manual-track-owner-fixed.png`
- `output/playwright/acceptance-saved-track-members-distinct-spotify.png`

## 7. 验证状态

已通过：

- schema 58 完整后端门禁：unit 1,373 passed；contract 376 passed；合计 1,749 passed，0 failed。
- 前端 Vitest：75 files、582 tests passed。
- 前端 TypeScript + Vite production build：passed；仅保留既有大 chunk 警告。
- 更早一轮后端完整套件为 2,260 passed；schema 58 本轮重新执行 unit/contract，未把未重跑的 integration 数量包装成当前结果。
- canonical API、迁移 55/56、identity revision、搜索四变体、Billboard 分区等价和公开 L1 拒绝的定向回归均通过。
- API smoke：139/139 passed；API 边界：112/112 passed；OpenAPI 211 个 operation 和 97 项参数义务均无未登记项。
- 默认完整全栈门禁：Pass，用时 2,136,339 ms。七个必需阶段全部通过：quality 41,365 ms、backend 725,100 ms、API 480,663 ms、browser routes 519,887 ms、browser interactions 92,819 ms、browser inventory 79,512 ms、browser compatibility 196,800 ms。
- 浏览器路由矩阵覆盖 Desktop/Mobile 及 phone-small、phone-large、tablet；控制台 error/warning、页面错误和横向溢出均为 0。控件清单覆盖 1,975 个控件、308 个主要触控目标，无未命名或小于门槛的违规；Chromium、Firefox、WebKit 均通过。
- 文档审计与 `git diff --check` 最终复核通过；本轮只做本地 Git 提交收口，不 push、不发布远程生产。
- schema 58 定向回归新增覆盖 owner-first 解析、历史 alias 搜索去重、同 owner 写入拒绝、分组/候选迁移和治理健康门禁；本轮相关后端扩展回归及 27 项 import-health 回归通过，前端 13 项相关测试与 production build 通过。

## 8. 回滚与边界

- 回滚优先使用迁移前 Online Backup；兼容表名和旧证据未删除，不需要重写原始事实。
- schema 55/56 的 snapshot stale 与 `agg_config` 清理只影响可重建派生状态；原子重建四张聚合并运行四套 v8 维护即可恢复 ready。
- 当前真实库已有 817 个 owner Track 拥有多个 Spotify ID，最高 7 个；`Anti-Hero` 的 Track `157` 拥有 4 个标准 Spotify ID，聚合保持 315 次、62,404,986 ms。
- 迁移前备份和迁移后库均存在完全相同的 7,831 条历史外键债务：`tracks → artists` 3,098、`track_artists → artists` 3,098、`albums → artists` 1,590、`ai_task_events → ai_task_runs` 27、`ai_tool_calls → ai_task_runs` 9、`chat_messages → chat_sessions` 7、`tracks → albums` 2。前两项是同一批 3,098 条重复曲目被两个外键各计一次，不代表 6,196 首坏歌。
- 这 3,098 条曲目自身播放为 0，覆盖 2,885 个 Spotify ID；每条都存在 Spotify ID 相同、艺人有效且承载播放的正常 owner。1,590 张孤儿艺人专辑和 2 条缺专辑曲目也没有当前播放引用。当前库与 2026-08-24 schema 45、canonical 改造前 schema 54、schema 57 三份备份按 `table / rowid / parent / fkid` 完全一致，本轮未制造或扩大债务，canonical owner/source 不变量与本次身份迁移阻断项均为 0。
- 形成原因是历史重复维表写入与后续父记录清理发生在 `foreign_keys=OFF` 的普通应用连接上，声明的级联没有执行；聊天会话删除路径仍可直接证明这一机制。音乐父记录缺少当时的变更审计，无法可靠归因到某一条历史命令。完整分类、影响与后续清理门禁见 [`../reference/data-import-and-health.md`](../reference/data-import-and-health.md)。
- 本轮是本地实现与本地真实库迁移，不代表远程生产已经发布；生产仍需按 release Online Backup、预检、四变体复用和业务 smoke 执行。
