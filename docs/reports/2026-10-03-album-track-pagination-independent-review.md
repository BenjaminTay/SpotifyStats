# 专辑曲目分页独立验收：核心通过，旧缓存位置兼容待修复

> 当前状态：2026-10-03 第二轮独立专项复核通过，原 P2 已关闭。下文保留首次验收发现及实施侧修复记录；最新独立结论见末节。默认完整全栈、真机和生产验收不包含在本次通过范围。

核验日期：2026-10-03。事项：SS-2026-09-24-001。

核验对象为隔离工作树 `album-track-pagination/202605-SpotifyStats` 基于 `fa683d97` 的未提交改动。
读取了“修复专辑曲目表完整分页”会话、[交付报告](2026-10-02-album-track-pagination-acceptance.md)、代码及本地副本证据。
本轮未修改业务代码、数据库，未提交、推送或部署；只更新验收文档和对应状态。

## 结论

完整分页、校验、失败保留旧结果和事务回滚的核心实现通过专项复核。任务尚不能整体标为验收完成：
发现一处真实旧缓存的发行位置兼容缺口，需要修复后复验。

### P2：旧完整 ID 列表仍使用另一发行的碟号和曲号

`backend/core/version_merge.py` 的 `get_album_track_comparison()` 在缺少发行级位置证据时，仍回退到
`spotify_track_meta` 上 recording 当前父专辑的 `disc_number` / `track_number`，并且未标记证据不足。
完整 ID 数量只能证明目录数量，不能证明 recording 的全局位置属于当前发行。

真实修复副本中，本地 `album_id=181` 的 `Did you know that there's a tunnel under Ocean Blvd`
选择 Spotify 发行 `5HOHne1wzItQlIYmLXLYfZ`，但没有 `spotify_album_tracklist_evidence`。
以只读连接直接调用 `get_album_track_comparison(181, 181)`，返回 `incomplete_album_ids=[]`，其中：

| 曲目 | 对比返回的碟号/曲号 | recording 当前父发行 |
| --- | --- | --- |
| A&W | Disc 1 / Track 1 | A&W（单曲容器） |
| Did you know that there's a tunnel under Ocean Blvd | Disc 1 / Track 1 | 同名单曲容器 |

两个不同曲目在同一专辑上均标成 Disc 1 / Track 1。该专辑的旧列表在修复前后相同；问题是历史数据边界未收口，
不是本次新增播放或曲目。`select_incomplete_album_ids()` 在修复副本上返回空列表，因此默认修复不会补充这一类证据。

修复应保持 GET 只读：缺少可靠发行位置时返回未知位置或明确的不完整状态，不借用另一发行位置，也不虚构 Disc 1。
若继续提供精确位置，增加有界的显式证据补齐路径，优先处理实际被消费的专辑；不要求全库无条件重抓。
补充旧完整列表、缺发行证据、recording 父发行不同和多碟未知位置的回归用例。现有 50 条已补齐发行的行为应保持。

## 本轮独立验证

- 复跑交付报告中的 13 个后端专项/相邻测试文件：**195 passed**，24.85 秒。
- 前端对比、详情元数据及版本归并工作台三个文件：**12 passed**。
- 文档审计 PASS、`git diff --check` 和 AGENTS/CLAUDE 一致性检查通过。
- 以 SQLite URI `mode=ro` 加 `query_only` 检查原始基线与修复副本：完整专辑 **3,187 → 3,234**，
  缺页 **12 → 0**，缺列表 **35 → 0**；50 条发行位置证据状态均为 complete。
- 独立比对 plays、tracks、track_artists、album_projects、album_project_tracks、album_project_albums、
  release_groups、release_group_members、agg_weekly_albums、agg_weekly_tracks 的有序行内容指纹及行数：全部一致。
- 副本 `integrity_check=ok`，`foreign_key_check` 无错误。
- 核对既存六场景浏览器日志，并查看手机详情与对比截图：Glee 的“发行 106 首 / 已听 1 首”及 Mimi
  的共享 14 首展示与交付记录一致。截图属于交付 session 的浏览器证据，本轮未重新启动浏览器，不宣称新一轮浏览器通过。

本轮未重新访问 Spotify，不回填副本或正式库，不运行默认完整全栈。当前属于本地专项复核 Partial，生产与真机未验收。
主分支已经推进到 `c91aac40`，本任务尚未合入；后续集成仍须核对并行专辑艺人证据任务的迁移编号及重叠写入路径。


## 后续修复与实施侧复验（2026-10-03）

以上结论、P2 发现与 195 passed 保留为本轮独立核验当时的证据。本节是实施会话追加的修复记录，
不宣称已进行第二轮独立复审。详细结果见 [交付报告后续修复](2026-10-02-album-track-pagination-acceptance.md#2026-10-03后续发行位置证据修复)。

- 对比取消 recording 位置及 Disc 1 / Track 下标回退。发行位置证据必须与当前完整目录全部匹配，
  否则返回 null 与独立的 `position_incomplete_album_ids`，曲目异同仍可读取，GET 无网络/写入。
- 有界脚本增加显式播放相关位置证据选项与只读范围预览；不对全库旧完整缓存无条件重抓。
  失败保留匹配的上一完整证据，复查采用原事务/修订机制，无新迁移。
- Lana 实际副本仅补齐一个发行：16/16 成员集合不变，恢复来源顺序；A&W Disc 1 / Track 4，
  同名曲 Disc 1 / Track 2。全库目录 3,234 完整，位置证据 50→51；原始表/周榜聚合/归并关系指纹守恒，
  版本检测 42 个候选逐字段一致，Records 只生成时间变化。重复刷新除尝试时间外内容相同。
- Mimi 共享 14 / 豪华版独占 6 仍成立；其位置未核验，前端现在明确未知。其余旧完整目录按需维护位置。
- 最终专项后端 203 passed、前端 17 passed、构建及代码/文档检查通过；真实副本 API 与正式组件验收
  Lana 未知/补齐各两视口，实际 Glee/Mimi/Records 两视口六场景通过并查看截图。
  Lana 使用临时组件验证页，不能代替设置页 Lana 工作流；默认完整全栈为 Partial，真机/生产未验收。

SS-2026-09-24-001 已收口本地专项，保持未提交、未推送、未部署和未修改默认库的边界。

## 第二轮独立复核（2026-10-03）：本地专项通过

读取后续交付会话，并复核位置证据校验、对比只读逻辑、显式选择范围和回归用例。未发现阻碍本次专项收口的新问题，首次验收的 P2 关闭。

- 独立复跑原 13 个后端专项/相邻文件：**203 passed**，31.56 秒；四个前端相关文件：**17 passed**。
- 独立执行 TypeScript/Vite build：通过；文档审计、diff check 和 AGENTS/CLAUDE 一致性通过。
- 使用 `position-followup/before.db` 和当前修复副本的 SQLite 只读连接，加 `query_only`，调用当前实现。
  未补齐的 Lana 专辑仍有 16 条共享曲目，返回 `position_incomplete_album_ids=[181]`，所有碟号/曲号为 null；
  已补齐副本返回位置完整，同名曲 Disc 1 / Track 2，A&W Disc 1 / Track 4。调用期间禁止显式联网补取。
- Mimi 在两份副本上均保持共享 14 首、另一版独占 6 首，返回位置未核验的专辑 ID，所有相关位置为 null。
  目录完整性与位置证据可信度已分别表达，不影响曲目成员比较。
- 两份副本均为 3,234 条完整目录；完整位置证据 50→51，仍缺位置证据的目录 3,184→3,183。
  这批历史目录可继续比较成员并显示未知位置，可通过显式、有界维护补齐，不要求全库回填才能关闭本次问题。
- 独立重新比对 plays、tracks、track_artists、album_projects、album_project_tracks、album_project_albums、
  release_groups、release_group_members、agg_weekly_albums、agg_weekly_tracks 和 spotify_track_meta 的全部有序行内容及行数：一致。
  专辑元数据只有指定的 Lana 发行变化，其余 3,233 条一致；`integrity_check=ok`，无外键错误。
- 核对实施侧未知/修复后共 10 个桌面与手机视口场景日志，查看 Lana 未知/修复后及 Mimi 的手机截图，
  确认实际显示与接口合同一致。此项复核已有浏览器证据，本轮未重新启动浏览器；Lana 场景仍属于真实 API + 正式组件的临时验证页。
  验证页首次打开日志有 favicon.ico 404，因此不将日志描述为零 console error；该请求不涉及曲目事实或对比接口。

本轮只修改验收文档和对应状态，未写入验收或正式数据库，未提交、推送或部署。主分支已推进至 `3a4e6310`；
当前实现仍在基于 `fa683d97` 的隔离工作树中。下一步按授权合入，复核并行艺人证据任务的迁移和写入重叠，再进行最终集成验证。


## 独立本地提交交接（2026-10-03，实施侧追加）

用户授权先提交已验收的分页交付，再由集成负责人使用固定 SHA 合并。交付分支为
`codex/album-track-pagination`，具体 SHA 以 Git 记录为准；首次及第二轮独立核验以上结论保持原日期与范围。
提交准备中发现并修正 schema 声明/人工 seed 与 migration 87 的一致性遗漏，新增 85→87 幂等和数据守恒
回归，详见交付报告门禁节。该补充属于提交前工程检查，不宣称独立复核或默认完整全栈已重跑。
