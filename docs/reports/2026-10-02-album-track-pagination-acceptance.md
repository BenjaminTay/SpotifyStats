# SS-2026-09-24-001：专辑完整曲目表分页与本地专项验收

首次实施与副本/浏览器验收：2026-10-02；发行位置后续修复与最后核验：2026-10-03。状态：S0–S5 本地专项完成；默认完整全栈为 **Partial（未执行）**。
本地独立提交交付分支：`codex/album-track-pagination`；未推送、未部署，未写入主工作区默认库或生产库。

## 工作区与授权边界

- 基于 `fa683d97` 创建隔离工作树：`/Users/benjaminlei/.codex/worktrees/album-track-pagination/202605-SpotifyStats`。
- 主工作区有其他任务的文档改动。本任务只读取并继承当前 AGENTS/CLAUDE、状态总表和相关文档上下文；没有暂存、提交、覆盖主目录中的内容。AGENTS 与 CLAUDE 保持一致。
- 用 SQLite Online Backup 从主目录默认库只读备份到本工作树 `output/album-pagination/baseline.db`，再创建 `data/spotify_stats.db` 验收副本。运行服务指定副本路径，使用 18021/15173 独立 loopback 端口和独立分析/Billboard/年度缓存。
- 浏览器专项持有共享排他锁；后端关闭 lifespan 自动维护，只显式生成一份默认 Records 快照用于页面读取。没有执行全库 Spotify 重抓、全部统计重建或完整 Billboard 构建。

## S0：修改前基线

此处数量只属于本次副本，不代表生产状态。

| 维度 | 修改前 | 修改后 |
| --- | ---: | ---: |
| 专辑元数据 | 3,234 | 3,234 |
| 长度与声明总数一致、必要 ID 齐全 | 3,187 | 3,234 |
| 缺页 | 12 | 0 |
| 缺列表 | 35 | 0 |
| 列表/声明都为 50 的边界疑点 | 3 待核验 | 3 条声明确为 50 |
| Spotify 曲目元数据行 | 24,823 | 25,987 |

三条边界为 `Karajan A-Z: Adam - Bartók`、`The 50 Greatest Pieces of Classical Music`、
`Kyou, Kun Sairai Suisan Toei Aizou Tokuten`。当前来源均确认 50 个位置，没有发现它们声明总数被改小。
历史被改小但不是 50 的缓存无法仅凭当前 ID 列表反推；本次没有把这个有界核查描述成全目录历史证明。

## S1–S2：实现与维护方式

日常 `upsert_album_batch()` 与显式 `_fetch_album_tracks_from_api()` 共用 Provider 完整读取。
复用经过验证的 Album 首页，后续固定请求 `GET /v1/albums/{id}/tracks?limit=50&offset=...`，
不透传 `next` URL。检查声明/分页总数、offset、页长度、结束标记、必要 ID/名称、重复页和碟号/曲号顺序。
官方分页合同于本日核对：[Spotify Get Album Tracks](https://developer.spotify.com/documentation/web-api/reference/get-an-albums-tracks)。

发行位置可以重复同一 track ID；校验前不去重，持久 ID 列表保持完整发行顺序。
新增 additive migration 87 `spotify_album_tracklist_evidence`，保存完整位置对象、已验证总数、
最近状态、尝试总数与错误。列表和必要曲目元数据在同一事务提交；写入失败回滚，读取失败保留上一完整
列表/总数/位置证据。已有 recording 的父专辑、时长和位置不会被另一发行的简化对象覆盖。

消除三个调用方的 `len(tracks)` 回写。旧缓存仅当声明总数、位置数量及所有 ID 一致才可参与完整读取；
缺失/部分/损坏列表不因非空被信任。版本对比与归并读取优先选本地名称匹配的播放来源发行，避免歌曲当前
Spotify 父专辑把某张本地发行指向另一容器。没有来源链接时保留原链路回退。

版本对比 GET 不再触发 Spotify 自愈或写数据库；不完整时给出 `incomplete_album_ids`，也不把证据不足
显示成空表或另一版本的独占曲目。对比使用发行级位置，重复 ID/归一化歌曲名只展示首次位置；同时修正
前端原先把 disc/track 两列反向显示的问题，手机对比按钮达到 44px 触控高度。

其他消费者与缓存：

- `album_project_auto_merge` 使用位置数量校验，允许同 ID 多位置，但不执行新的归并计划。
- 曲目专辑展示归属只使用完整目录证据；新目录中的未播放曲目不会产生本地播放或项目成员。
- Records 全碟回放采用不同 canonical song 集合，不用重复发行位置增加分母或播放。
- 专辑详情分别显示“发行 N 首 / 已听 M 首”；未知来源总数不再用本地曲目数量填充。
- Records 使用既有专辑元数据语义 revision，并推进缓存合同；治理健康增加 `track_list` 依赖。
- 年度内容版本推进至 `yearly_review_v2_18`；年度指纹增加播放来源专辑链接的触达范围，并兼容没有
  该关系表的旧测试/紧凑数据库。

有界、可重复执行的脚本：

```bash
# 指定副本，默认只审计
.venv/bin/python scripts/repair_album_tracklists.py --db data/spotify_stats.db

# 已迁移的副本，最多 50 个目标，包含 50 首边界复核
.venv/bin/python scripts/repair_album_tracklists.py --db data/spotify_stats.db \
  --apply --limit 50 --verify-boundary-50 --report output/album-pagination/repair.json

# 显式指定发行，可重复传入 --album-id
.venv/bin/python scripts/repair_album_tracklists.py --db data/spotify_stats.db \
  --apply --album-id 4fZXOp8No89WLudGy6brXd
```

脚本要求明确 DB 路径，默认审计，单次上限 200，不批准分组、不重建全部统计。
运行 `--apply` 前必须在目标副本执行项目迁移。正式库应用需要另行授权和正式发布门禁。

## S3：测试证据

`output/album-pagination/backend-tests.log`：**195 passed**，覆盖 13 个专项/相邻测试文件，包含：

- 1/50/51/106/121 个位置、多页、多碟、发行顺序及重复 ID；
- 空页、重复页、偏移错误、缺 ID/位置、总数变化、缺 next、中途失败；
- 旧完整结果保留、旧部分列表识别、重复执行幂等、失败事务回滚；
- 两条写入路径共用合同，显式归并补取失败保持 LKG；
- GET 不触发补取、发行级位置不被 recording 父专辑/位置污染；
- 重复发行位置与实际歌曲数分离，以及年度来源专辑依赖失效；
- 专辑项目规则、版本确认流程、曲目展示归属、Records 构建、分析/治理快照和导入范围回归。

`output/album-pagination/frontend-tests.log`：**16 passed**，4 个文件，验证发行/已听标注、对比碟号/曲号、
不完整状态、详情导航和归并工作台。`npm run build` 通过。
有既存 LibreSSL/urllib3 提示及构建 chunk 大小提示，未导致上述检查失败。
Ruff、`git diff --check` 与文档审计均通过。

## S4：真实副本修复与事实守恒

实际请求 50 条专辑：**47 条缺口修复成功，3 条边界确认完整，0 失败**。
再次默认执行修复选择 0 个目标，完整数量保持 3,234；没有重抓已完整目录。

| 专辑 | 修改前列表/声明 | 修改后列表/声明 | 对比展示 |
| --- | --- | --- | --- |
| Glee: The Music, The Complete Season Four | 50/106 | 106/106 | 105 条归一化歌曲名；完整位置仍为 106 |
| Miss You Much, Leslie | 50/78 | 78/78 | 78 条 |
| The Singles Collection | 50/58 | 58/58 | 58 条，优先本发行，不再借用另一精选集容器 |
| 夜色钢琴曲 | 50/121 | 121/121 | 三页完整位置已保存 |

曲目元数据新增 1,164 行属于 Spotify 发行目录，未新增原始 tracks/plays，也未将未听歌曲填入项目、榜单或统计。
未选中的 **3,184 条专辑元数据逐字段一致**。副本 `integrity_check=ok`，`foreign_key_check` 无错误。

以下表的行数和完整内容指纹保持一致：

| 原始/派生事实 | 行数 |
| --- | ---: |
| plays | 94,760 |
| tracks | 10,026 |
| track_artists | 10,496 |
| album_projects | 2,940 |
| album_project_tracks | 7,921 |
| album_project_albums | 3,181 |
| release_groups / release_group_members | 76 / 171 |
| agg_weekly_albums / agg_weekly_tracks | 23,071 / 49,618 |

自动归并扫描 1,435 个项目；强证据项目 **1,307 → 1,308**，`incomplete_track_list` 跳过数 **1 → 0**，
自动归并候选 **0 → 0**。没有自动批准人工关系。

手动完整检测使用统一修复后的读取规则，在同一前/后副本、阈值 0.8（包含 album/single）下，候选
**41 → 42**。唯一新增组是 Mariah Carey 的 `The Emancipation of Mimi`（album_id 243）与
`The Emancipation Of Mimi`（147）；完整曲目补齐后满足既有超集判断。其余候选逐字段一致，未保存新增组。
UI 使用自身筛选范围展示专辑候选，并对该新增组打开真实 API 对比。

110 个可信全碟回放项目的歌曲集合与分母均一致，Records 业务响应完全一致；只有 `meta.generated_at`
不同。例如 `Midnights` 仍为 **86 次完整回放，13/13 首**。来源事实和榜单原始聚合守恒不等于生产验收。

## S5：浏览器专项与交付边界

桌面 1440×1000、手机视口 390×844，使用真实修复副本和真实后端，验收：

- Glee 专辑详情：发行 106 首、已听 1 首、1 次有效播放、仍未入专辑榜；没有把补齐曲目当成听过。
- 新增 Mariah Carey 候选的版本对比：共享 14 条、豪华版独占 6 条。该轮仍展示 recording 的位置；后续独立核验发现此兼容边界不足，10-03 已改为明确未知，不能将当时的曲号/碟号展示视为发行证据。
- Records“探索与品味 / 专辑全碟回放”：Midnights 的 86 次、13/13 覆盖在两种布局一致。
- 窄视口无页面横向溢出，Phone 和 Desktop 使用各自 presentation。

本地机器证据位于 `output/album-pagination/`，该目录及数据库不进入 Git：
`baseline.json`、`repair.json`、`repair-repeat.json`、`album-changes.json`、
`before-consumers.json`、`after-consumers.json`、`conservation.json`、
`detection-before.json`、`detection-after.json`、`detection-diff.json`、
`comparison-before.json`、`comparison-after.json`、`after-browser-conservation.json`、`browser-acceptance.log`、
`album-{desktop,phone}.png`、`compare-{desktop,phone}.png`、`records-{desktop,phone}.png`。

本地专项已闭环。默认完整全栈未运行，因此不标完整 Pass；真实 iPhone/Android、生产数据库修复、发布和外部
客户端验收没有执行。后续如授权集成，需要按最终 staged diff 复核迁移编号、当前文档上下文和生产发布规则；
专辑艺人稳定 ID、日期精度、第二来源及歌曲语言不在本任务范围。


## 2026-10-03：后续发行位置证据修复

[独立核验](2026-10-03-album-track-pagination-independent-review.md) 保留当时的 P2 发现与 195 项测试记录。
本节为实施侧当时的修复与复验；第二轮独立复核随后通过，记录见独立核验报告末节。该轮未修改主目录默认库、提交、推送或部署。

### 读取与维护合同

- 精确位置只来自与当前完整目录的有序 ID、声明总数完全匹配且名称/碟号/曲号有效的整份证据。
  缺失、错配或损坏时返回 `null` 与 `position_incomplete_album_ids`；目录成员仍可比较。
  不读取 recording 的碟号/曲号，不推断 Disc 1 或 Track 下标；前端显示“位置未知”。
- `last_status` 记录最近尝试，不能否定匹配当前目录的上一完整证据。读取 GET 无网络、无维护写入。
- `--include-position-evidence` 是显式、有界的维护选项：除目录缺口外，只选择与播放相连的旧完整
  目录位置缺口。审计即输出范围，指定 `--album-id` 可维护一个发行，不加入全库自动刷新队列。
  继续用 migration 87、同一原子事务和既有修订/缓存机制；无新增迁移、归并审批或统计全量重建。
  对比没有后端持久事实缓存；位置字段不进入不使用它的 Records/年度依赖。

### 真实副本结果

在已修复副本上再执行 Online Backup，保存到 `output/album-pagination/position-followup/before.db`。
只补齐本地 album_id 181 对应 Spotify `5HOHne1wzItQlIYmLXLYfZ`：

| 项目 | 后续修复前 | 后续修复后 |
| --- | --- | --- |
| 目录声明 / 位置数量 | 16 / 16 | 16 / 16 |
| 全库完整目录 / 缺页 / 缺列表 | 3,234 / 0 / 0 | 3,234 / 0 / 0 |
| 完整发行位置证据 | 50 | 51 |
| A&W | 另一单曲容器的 Disc 1 / Track 1 | 来源确认 Disc 1 / Track 4 |
| 同名曲 | 另一单曲容器的 Disc 1 / Track 1 | 来源确认 Disc 1 / Track 2 |
| Spotify 曲目元数据行 | 25,987 | 25,987 |

修复前旧 ID 列表成员齐全但顺序不同于当前来源。修复后成员集合与声明数量不变，列表恢复发行顺序；
来源 popularity 同步从 77 更新到 82。只有这一条专辑元数据行变化，其他 3,233 条逐字段一致；
曲目元数据全表一致。重复指定该发行刷新后，目录、元数据及位置证据内容一致，仅尝试时间可更新。
仍有 3,183 条旧完整目录没有发行位置证据，兼容读取时明确未知；本任务没有为位置显示而全库重抓。

plays、tracks、track_artists、album_projects、album_project_tracks、album_project_albums、release_groups、
release_group_members、agg_weekly_albums、agg_weekly_tracks 的完整行指纹与行数均不变；
自动归并计划、110 个可信全碟回放项目的成员/分母不变，Records 仅 `meta.generated_at` 变化。
版本检测在同样 0.8/0.8 阈值下仍为 42 个候选且逐字段一致，无新人工归并或批准。
副本重复刷新及浏览器读取后 `integrity_check=ok`，`foreign_key_check` 无错误。

Mimi 两个已选发行也缺少发行位置证据：共享 14 首、豪华版独占 6 首的成员判断保持不变，20 行现在显示
“位置未知”。这是证据边界修正，未另行重抓这两个发行。Glee 的发行 106 首 / 已听 1 首、未入专辑榜保持。

### 后续测试与浏览器复验

后端同一组 13 个专项/相邻文件最终 **203 passed**；覆盖旧完整目录缺证据/缺表、ID/总数错配、必要 ID
缺失、无效/乱序位置、多碟未知、另一父发行、失败 LKG、恢复与幂等，保留原分页/重复 ID/原始事实边界。
前端四个相关文件 **17 passed**，TypeScript/Vite build、Ruff、文档审计、diff check、AGENTS/CLAUDE 一致性通过。

持有共享排他锁，使用隔离副本、独立 18021/15173 端口，关闭后端 lifespan 自动维护：

- Lana 未补齐与已补齐两种状态：真实 compare API + 正式 `TrackComparePanel` 组件临时验证页，
  桌面 1440×1000 / 手机视口 390×844 共四场景；16 行由未知变为真实位置，A&W 4、同名曲 2。
  临时验证页只用于验收，已移出前端源码；不将它描述成现有设置页的 Lana 操作流程。
- 实际应用 Glee 详情、Mimi 设置候选对比、Records 全碟回放：两种视口六场景通过并查看截图。
  Mimi 14+6 成员保持且未知提示清楚；Midnights 仍为 86 次、13/13 首；无页面横向溢出，比较按钮 62×44px。

后续本地证据位于忽略目录 `output/album-pagination/position-followup/`：`before.db`、`after.db`、
`before-audit.json`、`repair.json`、`repair-repeat.json`、`position-selection-preview.json`、
`before-comparison.json`、`unknown-181-181.json`、`after-comparison.json`、`mimi-comparison.json`、
`before-consumers.json`、`after-consumers.json`、`conservation.json`、`after-browser-conservation.json`、
`detection-before.json`、`detection-after.json`、`backend-tests.log`、`unknown-browser.log`、`repaired-browser.log`、
`unknown-{desktop,phone}.png`、`repaired-{desktop,phone}.png` 与三类实际应用截图。

当前为本地专项完成，默认完整全栈仍是 Partial；真机、生产回填与发布未执行。
基线为 fa683d97，主目录已继续推进；集成前仍须核对并行专辑艺人证据任务的迁移和写入重叠。


## 本地独立提交准备与门禁（2026-10-03）

按用户授权在 `codex/album-track-pagination` 分支形成独立交付，提交对象仅为本任务代码、回归测试、
类型生成物、规则及交付报告。docs 地图、CHANGELOG、路线只暂存本任务片段；不纳入继承的
AGENTS/CLAUDE、全局 DEVELOPMENT_STATUS 总表或 V6 归档。完整工作区文档均保留供集成负责人合并。

提交前额外迁移检查发现：migration 87 已注册，但声明版本和人工 seed 未同步。最小修复将
`LATEST_SCHEMA_VERSION` 改为 87，按受控生成器重建 `backend/tests/fixtures/seed.db`（人工边界样本，
不含本地真实用户数据）；补充版本一致性、seed 表合同，以及 85→87 升级、原始事实守恒与重复运行保留
已有证据的回归。此门禁补充不改变已通过的真实副本/浏览器统计结论；最终测试和 hooks 结果以本轮记录为准。

第二轮独立专项已通过，不替代默认完整全栈、真机或生产验收。本次本地提交不包含数据、副本、输出、
缓存、密钥或截图（唯一数据库文件是仓库已有的受控人工测试 seed），不 push、不部署、不写主工作树。


提交门禁最终结果：原专项加迁移合同共 14 个后端测试文件 **230 passed**；受控 seed 生成器的 golden
断言全部通过，大小 782,336 字节，migration 注册/版本声明/seed 均为 87，完整性与外键检查通过。
最初 hook 检查补齐了 `album_outcomes` 的类型注解并格式化两个本任务文件；复跑 Ruff、ruff-format、
mypy、detect-secrets 全部通过。精确暂存白名单 38 个文件，暂存快照独立文档审计 PASS，
`git diff --cached --check` 与 AGENTS/CLAUDE 一致性检查通过。前端 17 项与构建、真实副本及浏览器证据
沿用本次交付与第二轮独立复核；不把提交检查描述为默认完整全栈或生产验收。
