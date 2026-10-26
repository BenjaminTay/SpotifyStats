# 专辑证据审阅集成与生产交付

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。依次保存独立审阅、联合集成、最终本地集成及生产交付。旧缓存发行位置问题、本地完整门禁和daf098ca生产专项各有独立版本与边界，生产专项不等于生产默认完整全栈。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [专辑曲目分页独立验收：核心通过，旧缓存位置兼容待修复](#专辑曲目分页独立验收核心通过旧缓存位置兼容待修复)
- [专辑分页与稳定艺人证据：联合集成验收](#专辑分页与稳定艺人证据联合集成验收)
- [专辑证据与最新封面主线：最终本地集成验收](#专辑证据与最新封面主线最终本地集成验收)
- [专辑目录与艺人证据：生产交付](#专辑目录与艺人证据生产交付)

## 专辑曲目分页独立验收：核心通过，旧缓存位置兼容待修复

原记录：`2026-10-03-album-track-pagination-independent-review.md`。

> 当前状态：2026-10-03 第二轮独立专项复核通过，原 P2 已关闭。下文保留首次验收发现及实施侧修复记录；最新独立结论见末节。默认完整全栈、真机和生产验收不包含在本次通过范围。

核验日期：2026-10-03。事项：SS-2026-09-24-001。

核验对象为隔离工作树 `album-track-pagination/202605-SpotifyStats` 基于 `fa683d97` 的未提交改动。
读取了“修复专辑曲目表完整分页”会话、[交付报告](2026-10-02-album-track-pagination-acceptance.md)、代码及本地副本证据。
本轮未修改业务代码、数据库，未提交、推送或部署；只更新验收文档和对应状态。

### 结论

完整分页、校验、失败保留旧结果和事务回滚的核心实现通过专项复核。任务尚不能整体标为验收完成：
发现一处真实旧缓存的发行位置兼容缺口，需要修复后复验。

#### P2：旧完整 ID 列表仍使用另一发行的碟号和曲号

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

### 本轮独立验证

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

### 后续修复与实施侧复验（2026-10-03）

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

### 第二轮独立复核（2026-10-03）：本地专项通过

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

### 独立本地提交交接（2026-10-03，实施侧追加）

用户授权先提交已验收的分页交付，再由集成负责人使用固定 SHA 合并。交付分支为
`codex/album-track-pagination`，具体 SHA 以 Git 记录为准；首次及第二轮独立核验以上结论保持原日期与范围。
提交准备中发现并修正 schema 声明/人工 seed 与 migration 87 的一致性遗漏，新增 85→87 幂等和数据守恒
回归，详见交付报告门禁节。该补充属于提交前工程检查，不宣称独立复核或默认完整全栈已重跑。

## 专辑分页与稳定艺人证据：联合集成验收

原记录：`2026-10-03-album-metadata-integration-verification.md`。

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 基线 main `7b9a1f4e`；固定输入分页 `4f9a01ff`、艺人 `8f638494`。
> 集成分支 `codex/album-metadata-integration`；未新增集成提交、未推送、未部署。
> 当前状态：IMPLEMENTED / LOCAL_FULLSTACK_PASS；联合副本、默认完整全栈和桌面/手机视口验收完成。
> 后续主分支已新增封面提交 `f139ec4d` / `814ea7cb`；本报告仍只覆盖上述固定基线，不宣称包含这些提交。
> 代码 patch SHA-256：`0f5615f7ba61c06794fd0c5b0c2c300ee7e2326c65963b993cf39d64b59d06b0`；八阶段通过后复核一致。61 个任务文件暂存供审阅，集成未提交。

### 最终合同与范围

共同刷新函数同时接收 Provider/token/outcomes 与 source/source_run_id。完整目录/发行位置和有序 Album artists 分别校验、独立保留上一可靠证据；任一数据库写入错误回滚整批，包括显示和审计。版本补取、发行周期及两份维护 CLI 使用相同边界，封面 UPSERT 不损坏父行。Album 不覆盖 Track 署名，不扩散播放贡献，不恢复隐藏页签。

曲目比较的名称与艺人为二元组：本地 owner 复用有效 Track 署名，非本地只读已有 Track provider evidence。位置单独从与当前目录全部匹配的完整发行证据读取；旧完整目录成员可比较，未验证位置为 null。GET 不联网或写入。自动归并与 Records 保留 canonical artist、不同 canonical song 和人工批准边界。

迁移注册表保持 1..88 连续：86 安装专辑语义 revision，87 创建完整目录/位置证据，88 登记 Album 艺人表。86 复用现有 revision/trigger 实现，不是空占位。受控人工 seed 已重新生成，Various Artists 明确作为测试维度，全部 golden 断言通过。年报内容版本统一为 `yearly_review_v2_19_album_evidence`；准备层 revision 与播放来源专辑的目录、艺人和 external ID 触达依赖同时保留。

OpenAPI 从最终集成后端重新生成，并保留当前 main 的艺人署名链接行为。原快照还缺少主分支既有 V6/封面 schema 更新，生成物一并与实际后端合同同步；没有新增相应 AI 或封面业务。默认 quality 的全量 mypy 发现四个既有测试文件对动态 cache_clear 属性的 8 个类型错误，改为 getattr 检查并调用同一个公共属性，未改产品缓存行为、未跳过类型检查或放宽断言。

### 联合副本与真实消费者

正式默认库仅以 SQLite mode=ro 读取，通过 Online Backup 创建副本。源库仍为 schema 81，当前发布代码 schema 85 的升级路径由当前 main 在副本生成，不冒充远程生产数据库快照。

- 旧 81 与发布代码 85 两条路径升级至 88，重复迁移、连续注册表、证据表/触发器、完整性和外键单独核验。
- 固定有界范围为 60 个 Album，包括 47 个目录缺口、3 个 50 首边界及艺人/发行位置样本，存在目标重叠，不能把分类数量相加。全部完整发布；目录 complete 3,187→3,234，partial 12→0，missing 35→0。没有全库重新抓取。
- 艺人样本 7 个重复观察全部 unchanged；逗号名称和 JOLIN / Jolin Tsai canonical 532 均已解析。其余新证据保留真实未解析状态，不伪造身份。
- Lana 来源发行完整 16 个位置，A&W 为 Disc 1 / Track 4，同名曲 Disc 1 / Track 2；旧证据缺失返回未知。Mimi 本地 album 147/243 保持共享 14、豪华版独占 6，本轮显式请求这两发行后位置可信。
- Glee 完整发行 106 首，本地已听 1 首；发布目录不新增本地 track 或播放。
- 原始 plays 94,760、tracks 10,026、track_artists 10,496，自动署名 8,969、人工覆盖 36、当前有效署名 11,787，以及项目/归并关系和周榜聚合的有序行内容指纹一致。修复新增/补齐的 Spotify provider 曲目元数据属于目录证据，不是新增播放。
- 初次真实消费者 before/after：Records 只有 generated_at 不同；可信原版 membership 集合一致；自动归并无新增候选。一个原先 incomplete_track_list 的项目转为 album_artist_identity_unresolved，继续不自动批准。
- 默认全栈真实 integration 发现 Taylor Swift 无 Album 证据时公开只读发行周期返回空，旧测试期望 >10 个发行；没有恢复请求失败放行。为实际消费者在同一副本定向补入 94 个已有关联发行的 Album artists，5 个有界批请求、94 observed、0 failed/rejected，未补 Track 署名或扩展曲目目录。93 个可验证 Taylor 身份；《Cats》Album 实际署名为 Andrew Lloyd Webber 和剧组，两者本地未解析，继续不把歌曲艺人当成专辑艺人。
- 最终真实消费者再次核对：Records 仍仅 generated_at 不同，原版 membership 不变、自动归并候选仍 0；strong evidence 1,307→1,306，album_artist_identity_unresolved 为 2，incomplete_track_list 1→0。这是补入真实 Album 证据后保留身份审核边界，不执行任何自动批准。

副本证据位于 ignored `output/album-integration/`：`joint-evidence.json`、`final-migration-evidence.json`、`repair-selection.json`、`repair-outcomes.json`、`consumer-diffs.json`、`final-consumer-diffs.json`、Taylor 定向 selection/outcomes/unresolved、before/after 消费者、代码 patch 与任务白名单。数据库、密钥、缓存和截图不进入提交资产；唯一受控数据库变更为仓库测试 seed。

### 验证登记

| 验证 | 当前证据 |
| --- | --- |
| 初始相关选择 | 111 passed，属于早期草案 |
| 固定交付相关选择 | 139 passed / 1 fixture failed；历史初跑，不能登记通过 |
| 组合写入与实际只读比较 | 修正必填时间/父证据夹具后 2 passed；独立校验失败与数据库回滚边界 |
| 最终来源艺人/迁移组合 | 49 passed；与其他选择有重叠，不相加为总数 |
| 连续迁移及最终专项 | 99 passed / 14.87s；81/85→88 新副本重复迁移通过，1..88 连续，463 个触发器，原始/项目/周榜事实保持，完整性 ok / 外键 0 |
| Seed | 当前生成器 golden 断言通过，schema 88、同时包含两套证据表 |
| 真实消费者及副本 | 上述有界副本核验通过；不代表生产回填已执行 |
| Hooks | Ruff、ruff-format、mypy、detect-secrets 全文件通过；前端 697 passed / 4 skipped，TypeScript 与 Vite build 通过；最终默认完整门禁另登记 |
| 完整后端 | 最终同轮 seed 3,201 passed / 2 skipped；真实副本 integration 186 passed / 1 skipped；原发行周期断言保持 |
| 默认完整全栈 | `20261003T020011.704402Z-87d26d4d09e5`：full 模式八个必需阶段同轮全部 PASS，1,443,203ms（24分03秒）；API smoke 155/155、边界 113/113、22 轮热请求 500ms 门槛及三浏览器通过 |
| 发行周期真实消费者定向回归 | 定向补证后 7 passed / 14.08s；保留稳定身份门禁与旧断言 |
| 新一轮浏览器 | Chromium 1440×1000 / 390×844；Glee 106/1、Midnights 86、Mimi 14共享/6独占及 Track 2 / Disc 1；两端实际点击 Sabrina Carpenter 并返回，独立链接与中点保留；8 个测量结果横向溢出 0、console warning/error 0，手机对比按钮 62×44px。截图已视觉复核，不代表物理手机验收 |
| 最终事实守恒 | 全栈及专项浏览器后，源库与副本受保护原始/自动/人工/有效署名、项目/归并/周榜行内容指纹仍一致；源 schema 81、副本 88，双方 integrity ok / 外键 0 |
| 文档与交付 | 隔离目录 216 / 主目录 215 份 Markdown（含归档）审计 PASS；工作区及暂存 diff 检查 PASS，AGENTS/CLAUDE 一致；最终文档 Detect secrets PASS，代码 hooks 因仅文档选择而跳过，代码全量 hooks 已在同轮 quality 通过；主目录只更新两事项、相关开发顺序及维护记录，保留同期工作 |

早期 seed 轮记录 5 个 warning，含 AI task 后台线程对测试临时库的 disk I/O error；该线程文件未在本任务修改。最终完整轮 seed 为 4 个 warning（LibreSSL 和 HTTP 422 弃用），integration 为 1 个 LibreSSL warning。最初 runtime 禁用外部封面回退而 integration 临时目录没有本地封面；最终采用项目默认回退设置，并在隔离运行目录使用正式本地封面的 APFS 资产副本，不伪造图片或写正式目录。

早期失败和 BLOCKED 记录独立保留：dataset 参数错误、86 缺口、既有 mypy 错误、未补 Album 证据的发行周期失败，以及两次共享锁阻断，均不拼接为最终 Pass。最终 full 模式命令没有 `--only`、`--from` 或跳过跨浏览器选项；optional 未运行不影响八个必需阶段。阶段耗时依次为 preflight 7,668 / quality 65,106 / backend 517,632 / api 174,450 / routes 400,106 / interactions 80,054 / inventory 45,740 / compat 152,289ms。

持久证据为 ignored `output/album-integration/fullstack-pass.json`（完整 summary 的原样副本）、`fullstack.log`、`final-facts.json` 和 `output/playwright/album-integration/browser-metrics.json`、快照及截图。中断后继续时，原系统临时 run 目录已不存在，单独 benchmark 子 JSON 未保留；上述完整日志及兼容 summary 仍保留同轮状态、计时和请求结果，不重造临时子文件。浏览器最初连接已停止服务出现 connection refused，重启同代码副本服务后完成专项；中点探针因真实换行误判，检查 DOM 后规范化空白重跑通过，未改产品。最终浏览器 session、专项共享锁及本任务临时服务均已关闭。

### 待发布与数据维护

本地整合和验收不授权发布。后续按任务白名单审阅并授权集成提交，取得固定 SHA 后复跑必要检查/CI；生产发布前 Online Backup、schema 85→88、三模式/健康/回滚检查，先有界补目录和被消费发行位置，再按已审核范围补 Album artists，失败/歧义/冲突保留旧值或待审核。记录来源 run ID、成功/拒绝/未解析数量，再验证生产快照与受影响页面，不能无条件全库重抓或擅自修改人工身份。

历史专项：[艺人报告](2026-10-02-album-artist-evidence-verification.md)、[分页报告](2026-10-02-album-track-pagination-acceptance.md)、[分页独立复核](#专辑曲目分页独立验收核心通过旧缓存位置兼容待修复)。当前规则见[元数据规则](../reference/music-metadata-management.md)，范围及文件整合见[集成计划](../archive/06-productization-closeout/2026-10-03-album-metadata-integration-plan.md)。

## 专辑证据与最新封面主线：最终本地集成验收

原记录：`2026-10-03-album-metadata-final-integration.md`。

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 固定输入：分页 `4f9a01ff147f718ca9d697ed46870c41db8f3e5c`、艺人 `8f638494418770097a96bc6c4eb1ad67d447c964`。
> 已提交检查点 `ad9cc3c6`；合入主线输入 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e`，保留其封面提交 `f139ec4d`。
> 验证代码：`8464ffa635745ccb57e08c82002be7d484e10d63`。
> 当前：已实现、已本地提交、LOCAL_FULLSTACK_PASS；已安全合入本地 main。未推送、未部署，正式库未写入。

### 整合范围

业务代码三方自动合并。详情头部同时保留按尺寸/DPR 加载的 `coverDisplayUrl` 与“发行/已听”独立数量；四个动态 cache_clear 测试修复与主线一致，没有重复实现。四处文档冲突逐段保留双方记录，没有整文件选取 ours/theirs。最终后端重新生成 OpenAPI 和前端类型，包含 160/320/640 封面合同与来源 resolver。

专辑两类证据保持主体独立、独立校验与可靠旧结果；数据库异常整批回滚。连续迁移 86/87/88、受控 seed、Track 原始/有效署名守恒和年度 `yearly_review_v2_19_album_evidence` 依赖保持。没有涉及 SS-2026-09-24-003 日期精度。

全局开发状态总表继承另一任务尚未提交的整份内容，只维护两个事项，保留未跟踪文件，不把整份总表或 V6 归档混入本任务提交。两个输入分支和固定 SHA 均保留。主目录同期改动在安全合入前保持原样。

### 本轮证据

- 专项后端 137 passed / 1 LibreSSL warning，覆盖两类证据、身份、迁移、原子回滚、实际对比和封面来源/只读合同。
- 前端受影响四个文件 39 passed，TypeScript/Vite build 通过；现有分块大小提示不是失败。
- 新运行副本使用旧已验证联合副本的 Online Backup，复用有界证据与实际封面资产的 APFS 副本，不重复全库采集或写正式数据。
- 本轮 Online Backup 的 81/85→88 与重复迁移通过；注册表 1..88 连续、463 个触发器，integrity ok / FK 0，受保护原始表行内容一致。运行副本保持 60 份完整目录/位置证据、154 份 Album 艺人证据，复用已审阅的有界选择，未继续 API 采集。
- Records、原版 membership 和自动归并计划与历史已验证副本一致；完整门禁及专项后再次核对，正式源 schema 81 / 副本 88，plays 94,760、tracks 10,026、raw track_artists 10,496、自动署名 8,969、人工覆盖 36、有效署名 11,787，项目/归并/周榜有序行内容指纹均保持。维护不会新增播放贡献或批准身份。
- 搜索当前支持的四个精确变体 ready、repeat-safe；使用 `--statistics-reuse-only` 重新确认，没有冷重建。
- 默认完整全栈 `20261003T070853.211207Z-f917b9718886`：full 模式全部八个必需阶段同轮 PASS，1,360,570ms（22分40秒）；seed 3,231 passed / 2 skipped / 5 warnings，真实 integration 186 passed / 1 skipped / 1 warning；前端全量 726 passed / 4 skipped，API 157/157、边界 113/113，22 轮 500ms 热请求门槛与 Chromium/Firefox/WebKit 通过。没有 `--only`、`--from`、跨浏览器跳过或三次效率验收。八阶段分别 7,518 / 64,093 / 456,196 / 159,274 / 399,976 / 79,866 / 45,928 / 147,594ms。
- summary 的 git_head 为上述代码 SHA；dirty=true 仅因继承未跟踪的开发状态总表，业务 tracked diff 在运行前后均为空。规范 summary、OpenAPI 审计、benchmark、seed/integration JUnit 等 14 个 run 文件在结束时已复制至 ignored `output/album-final/run-artifacts/`，完整日志和兼容 summary 同时保留，不依赖系统临时目录长期存在。
- 实际 Chromium 1440×1000 / 390×844：Glee 106/1、Midnights 86、Mimi 14共享/6独占与 Track 2 / Disc 1，两端实际点击 Sabrina 并返回；嵌套链接 0。8 个测量结果横向溢出 0、console warning/error 0，手机对比按钮 62×44px。桌面 Glee 请求 `.320.webp`、手机请求 `.640.webp`，图片实际正常显示；本运行资产尚未补建这两档，使用合同内的原图回退，不能据此宣称本地变体齐备或图片体积已下降。三档 WebP 读取/回退合同由专项与完整后端覆盖。这两次视口测量 DPR 都为 1，DPR 选择另由封面单元合同覆盖，不冒充物理手机/高 DPI 实机验收。主要截图已视觉复核。
- 专项证据在 ignored `output/playwright/album-final/`；新数据库、资产、缓存、真实截图均不进入 Git。浏览器 session、专项锁和本任务临时服务已关闭。

本轮保留的边界：seed 的 5 warnings 包括 LibreSSL、HTTP 422 弃用，以及 `ai_task_service.py` 后台线程访问测试临时库时出现的 disk I/O warning（与早期历史轮相同）；实际 integration 只有 LibreSSL warning，没有扩大任务修改 AI 运行时。一次辅助迁移脚本引号错误与不支持的 CLI 参数在实际门禁前终止，修正后重新完整执行；专项首次桌面标题定位及手机 presentation 重挂载后的旧候选定位失败，按 fresh snapshot 修正标题/重新检测后重跑，保留失败文件，未改产品代码、未把失败拼为 Pass。

### 真实问题与现有消费者

名称含逗号的实际样本与 JOLIN / Jolin Tsai 人工 canonical 532 暴露了名称拆分/名称验证的不可靠边界；稳定 ID 使顺序、来源名称与身份分离。`_verify_album_artists` 的请求失败放行也在代码和回归中确认并修复。现有发行周期、版本补取/对比、Album Project 归并、Records、Billboard 和元数据健康改为稳定身份及明确 legacy/未解析状态；Album 不替代 Track 艺人。

同名不同 ID 在 Track 缓存有旁证，但本轮没有观察到 Album 实际误关联；同一 ID 历史改名的 Album 实样也未观察到，二者由合成身份测试覆盖。Cats Album 的 Andrew Lloyd Webber/剧组是真实未解析证据，继续待审核，不能用 Taylor 的 Track 署名替代。旧 ID 集合冲突、字段缺失、刷新失败均保留可靠旧证据；名称与顺序变化不意味着角色变化。

旧 `7b9a1f4e` 候选完整八阶段通过仅见[历史联合报告](#专辑分页与稳定艺人证据联合集成验收)，不能外推本轮 `814ea7cb` 整合、生产验收或三次效率验收。

### 发布交接边界

取得最终固定 SHA 后，正式发布仍须独立授权。先记录生产现有版本与 schema，Online Backup 并保存 SHA-256/完整性；正常生产 schema 85→88，先在副本迁移并确认连续注册表、幂等、FK 和守恒，失败联合回滚代码与备份。

目录维护 CLI 默认只审计；Album 艺人 CLI 要求明确源库、新输出副本和有界 limit，只在新副本写入。先限定现有缺口/被消费发行位置并预览，再有界补目录及 Album 艺人证据；正式发布数据另走经授权的副本审阅与切换。保存 run ID、成功/拒绝/失败/未解析数量；冲突保留已有可靠证据，身份缺失保持待审核，不全库重抓、不自动批准身份或归并，不修改 plays/tracks/raw track_artists 或 Track 有效署名。正式回填后验证 revision/快照及实际消费者；发布三模式、健康、搜索 ready 快照和回滚门禁另存证据。

### 安全合入窗口

2026-10-03：只读确认“优化榜单页面图片加载速度”会话已完成，提交/推送及验收隧道收尾结束，主目录无仍依赖代码的后端/前端服务。实时 main 为 `85a44cb888272d6229297d883af4f05dfd271e12`；相对 `814ea7cb` 只有封面报告、方案归档与规则/索引增量，业务代码未变化。隔离候选逐段吸收这些文档，保留其归档路径与发布记录；最终业务内容仍等于已完整验收的 `8464ffa6`。main 已 fast-forward 到 `824b2250b4e9fb37f351e9235a5654db52460aab`：五份重叠文档采用精确路径 stash 保护、三方内容恢复，未使用整树 reset/clean 或宽泛 stash。重叠之外的全部已有修改/删除/未跟踪文件及文件模式逐项保持，暂存区为空；只在台账消除本任务两个旧 OPEN 重复行，日期精度 003 保持。完整保护点与恢复 diff 在 ignored `output/album-final/main-preservation-85a/`。主目录 225 / 隔离目录 220 份 Markdown 审计及 diff 检查通过，AGENTS/CLAUDE 一致。后续收口仅更正文档状态，不改变已验收业务代码；本任务的临时保护 stash 在恢复核验后清理，其他已有 stash 保留。

## 专辑目录与艺人证据：生产交付

原记录：`2026-10-03-album-metadata-production-delivery.md`。

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 固定发布版本：`daf098ca035b5c587bb544a0ef0fb6c572514a98`；业务代码等于本地完整验收的 `8464ffa635745ccb57e08c82002be7d484e10d63`。
> 状态：已提交并推送业务、CI及正式发布成功、生产迁移/限定维护/HTTPS专项完成；全栈范围Partial。
> 本报告登记独立的生产备份、限定维护和线上验收；不改写此前本地报告的历史边界。

### 调查与数据合同

Album 缓存的 Earth, Wind & Fire、Tyler, The Creator 是真实含逗号样本；旧验证拆分名称会误拒绝。JOLIN provider 身份由已有人工治理解析至 canonical Jolin Tsai。发行周期原失败放行路径也已修正。Album 同名不同 Spotify ID 的实际误关联、同一 ID 历史改名未得到真实样本证明，相关边界由合成测试覆盖，不能把 Track 同名样本当成 Album 对账结果。

独立保存 `spotify_album_credit_sets`、`spotify_album_artist_credits` 和追加的 `spotify_album_credit_events`：Album 主体、Spotify artist ID、来源名称、从零开始的署名顺序、来源与观察信息、内容指纹及审计。解析复用现有外部身份与 canonical 人工治理；名称用于展示，顺序不表示 primary/featured。无法唯一解析保留 unresolved/ambiguous，不创建或按名称合并艺人。缺字段、请求失败及身份集合冲突保留上一可靠结果。严格验证要求稳定身份，旧名称兼容明确为 legacy。

主刷新、补取、发行周期与封面脚本共用写入合同；发行周期、Billboard/Album Project 元数据筛选、自动归并与 Records 可信原版判断使用对应证据。Album 不替代 Track 有效署名，不改变播放贡献，不恢复隐藏前端入口。完整目录与发行位置使用独立证据，未知位置不借另一发行推断。最终规则见[元数据参考](../reference/music-metadata-management.md)，代码及完整本地门禁见[最终集成报告](#专辑证据与最新封面主线最终本地集成验收)。

### 生产源与有界维护

生产原版本 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e`，dual，schema 85。Online Backup 为 `/opt/spotify-stats/backups/spotify-stats-pre-album-daf098ca-20261003-production.db`，444,588,032 字节，SHA-256 `529fb30f8082cf44cf2e1f9384975c8b7bcab74a31beec045275897471d58869`，integrity ok。最终停服保护点 `spotify-stats-pre-album-quiescent-daf098ca-retry2.db` 与其完整哈希相同，证明正式切换前源未漂移。

实际生产选样：47 个目录缺口（12 partial / 35 missing）、3 个 50 首完整边界及5个位置样本，去重后维护54个发行；Album 艺人选择当前消费者所需发行与上述样本的并集154个。Taylor 发行周期来源链为94个发行。没有全库采集或填满无关旧位置。

使用两份现有维护 CLI 在新副本完成：目录54 complete，艺人两个批次分别100/54，最终154份证据集、177条有序艺人、154条审计与54份目录/位置证据；请求失败与拒绝均0。5个发行重复读取 unchanged=5、observed/changed/rejected/failed=0。迁移86 `album_metadata_semantic_revisions`、87 `spotify_album_tracklist_evidence`、88 `spotify_album_artist_credit_evidence` 连续升级85→88并重复执行，旧记录保持可读。

审核增量只更新54份既有 Album 元数据并写入上述4张证据表，安装前核对154个来源元数据及35类保护事实。增量文件 SHA-256 `07d7d46d6c316b12ae555ef61904ab229b144a1c8f04f8513dbb1eb10f688632`。正式维护从新的停服 Online Backup 构造目标、验证后原子安装；没有用早期副本覆盖可能的新播放。旧镜像先证明可读增量 schema，再恢复健康，随后由既有流水线发布固定新版本。

生产原始与治理事实前后逐行指纹相同：plays 94,760、tracks 10,026、raw track_artists 10,496、自动署名8,970、人工覆盖34、有效署名11,789；项目/成员、人工关系、Track provider 身份与周榜等共35类均保持。这里使用生产实测值，不复用本地旧署名数量。主目录本机数据库仍schema81，未写入。

源库已有60,294条搜索派生 FK orphan：weekly chart context 60,270、year-end meta 20、year-end projection state 4。排序后的 FK 集合哈希 `d02726a739ee47501e34b8042ce5939ea795fc5344cbf6eabc2befd322a29fdd` 在源、维护副本和线上保持；没有新增 Album FK 错误，也没有清理该遗留问题。当前精确快照读取门禁另行检查，不能将本轮生产 FK 说成0。

### 消费者与发布证据

副本 Records 事实及1,413个原版 membership 结果相同；自动归并候选仍0，strong evidence 1,311→1,310，incomplete 跳过1→0、身份 unresolved 跳过新增2，属于保守证据判断，未批准归并。Lana 181：A&W Disc1/Track4，标题曲 Disc1/Track2；Mimi 147/243：14共享、6独占，发行位置来自各自完整列表。Taylor94个来源经现有发行组去重，消费结果71个发行。选样并集中的96个发行可稳定验证为Taylor，这与94个消费来源、71个去重结果是不同口径。

13个 Album 的证据集共24条艺人行，其中17条未解析；包括 Various Artists、古典/剧组身份与 Cats。JOLIN 映射为canonical532，未批准新身份或关系，不将 Cats 内Taylor歌曲署名当作其Album艺人。

四个当前受支持精确搜索变体以 `--statistics-reuse-only --require-all-ready` 在副本重复确认 ready/repeat-safe；旧镜像亦验证兼容，没有全局统计冷重建。年度内容版本为 `yearly_review_v2_19_album_evidence`。旧镜像启动会按旧合同重置 Analysis revision epoch，因此早期副本年度键与线上不一致，安装保护已拒绝旧结果；最终年度结果须在新代码启动后按实测修订准备，不手改缓存键。

固定版本交付分支质量[37111786346](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37111786346)及生产合同[37111786326](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37111786326)成功。主线发布[37126148736](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37126148736)，独立质量[37126148783](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37126148783)，主线发布 attempt2 与独立质量均 success；质量、full/showcase/dual、linux/amd64镜像、私有CAS传输、TCR digest-pull、健康及CAS保留均完成。线上三容器为固定daf098ca、healthy，dual/public，Backend不暴露宿主端口，Web仅127.0.0.1:3001/3002。

生产digest：API `sha256:fd443fd2432d38d6b7f86403e3a53beec7c533ec430383fe9d88a481cb8887e0`，Web `sha256:01ad917c18f8b7d3aafe672f029ef186d60ab89d661f1bd74907158e0b681314`。发布preflight可用内存2,132MiB、要求640MiB，未降低门槛；统计复用，当前entity context orphan0，未混同全库遗留FK。

#### 线上消费者发现的增量遗漏与补齐

初次线上Mimi比较为空，缺口为此前目录维护新增的简化曲目名称未纳入首次受控增量；不是原始歌曲或署名缺失。对缓存副本重新清点：54个已选发行中43个发行涉及1,175条新增 `spotify_track_meta`，全部没有本地 tracks/播放；另17条既有名称变化未安装，保留原有行。

新 Online Backup 副本只插入这1,175条缺失 provider 元数据，验证35类事实、FK集合、Lana/Mimi、71个Taylor消费发行、1,413个membership及四变体reuse-only通过。正式事务再次确认所有ID仍缺失、仍属于已选完整目录且没有本地歌曲，再原子插入；不更新既有行，不新增Track艺人证据或署名。补充保护点 `album-stage-daf098ca/supplement-pre-live.db` SHA-256 `207427c0588dcc8d0ec33b64db5aaea14c6f77befdeb2e800836291135f08fad`。

重启Backend清除进程缓存，正式verify通过（schema88、4/4 ready、当前entity context orphan0、exact/fuzzy/CJK/short-CJK语义门禁通过）；线上服务函数再次证明Mimi14共享/6独占、Lana位置和Taylor结果，membership与审核副本逐项完全相同。原始及治理事实仍一致。

#### 年度缓存

按新代码最终源在副本生成2026确定性V2，106.375秒，内容版本 `yearly_review_v2_19_album_evidence`，未调用LLM。补充元数据后再次按线上源准备并确认精确键 `5e38e39efc07eee4b1d6cddd2f347063113f9ad1e509e48b2a0fe0f8973e6faf`、filter `89a0533217853760298beda8c86b2d4a50c52efccdf67d9b1d4a480bb2a18997` 和来源修订 `ef33805afcfe92bab904fc8ae92bb49f9f340458edf3b519da3521ed70ff852b:album:f3fe65cb874322bab9cd` 完全匹配后安装。只写年度派生sidecar的2026新键及实际namespace的prepared-key，保留其他年份/旧键。

sidecar Online Backup `spotify-stats-pre-album-yearly-cache-daf098ca.db` SHA-256 `0815392045ab066fbd37dab128416da9f30d45e806231768bd0acda2a72c91f9`；安装后缓存读取ready。旧代码阶段生成的不同修订缓存没有发布。

#### 实际 HTTPS 专项

`/api/runtime/capabilities`、Glee project43076摘要、Records及2026年度V2均200；公开设置写入和年度prewarm均403，隐藏版本比较仍404。Glee旧摘要已声明106首，问题是目录只存前50，不能称为声明总数50→106。新详情同时显示发行106/已听1。

Records前后只有4项变化：`meta.generated_at` 和 `snapshot.request_key/source_revision/target_revision`；逐项排除这些必要修订字段后其余响应完全相同，没有把整个snapshot删掉再比较。第一次重启后的Glee摘要59.080秒，已记录为冷态，不计热请求通过；随后热态Glee0.484、Records0.528、年度1.400秒。不是生产默认完整全栈或全部API性能门禁。

#### 实际浏览器

实际HTTPS Chromium 1440×1000 / 390×844：Glee发行106/已听1、Records探索页Midnights86次完整回放，两端同一统计事实。合作曲排行Taylor/Sabrina为独立链接，中点与完整署名保留，两个视口分别实际点击Sabrina进入其艺人详情后返回；没有嵌套链接或横向溢出。最终浏览器console0错误/0警告。

合作曲区域抽样可见封面14个Desktop、6个Phone均加载成功，使用160px `thumb.webp`；Glee Desktop命中320px、Phone命中640px，Sabrina Phone命中320px WebP，无上述可见样本坏图，保留尺寸/DPR策略。Records手机首次resize后的全DOM测量有4张待加载图片，不能登记为4张坏图或全部离屏图片已经验收；随后以可见区域完成解码核验并保存截图。合作曲两端截图已实际检查，Glee/Records/Sabrina截图另保存；本轮实际消费覆盖160/320/640px，完整三档补建数量仍见封面报告。

浏览器属于生产专项通过，默认完整全栈范围标为Partial；未模拟登录、调用LLM、验证OAuth或物理手机。页面隐藏发行档案与艺人生涯的边界保持。

### 失败记录与回退

首次维护辅助脚本中 compose oneoff 消费了 SSH 脚本 stdin，Backend 停止后脚本提前结束，未切数据库，已恢复旧服务。第二次副本文件权限不足，保护流程拒绝安装并恢复旧服务，正式库仍未切换。修正仅限本任务新副本权限和 oneoff stdin；第三次完整运行成功。维护存在服务暂停，失败日志保留，不能登记为零停机。

旧版本镜像及schema85保护点保留；既有发布流程负责固定SHA、CAS缺块传输、三模式门禁、快照复用、健康检查与数据库/镜像/模式联合回滚。HTTPS/Tailscale、公网端口及入口身份边界保持。自动发布前备份另为 `spotify-stats-pre-release-daf098ca035b-20261003T135058Z.db`（schema88）；如需回到维护前schema85，使用前文独立停服保护点与814ea7cb镜像联合恢复，不把发布后备份当作维护前备份。

### 证据范围与后续

本轮是生产专项验收；完整本地八阶段PASS来自同业务代码的 `20261003T070853.211207Z-f917b9718886`，不是在生产重跑的默认全栈。真实手机、生产LLM和OAuth未由本任务验收。

发布 attempt 1 在容器集合恒定检查处失败：本任务并行年度缓存 oneoff 在传输期间结束，before/after 差异仅该临时容器，正式三容器与其他应用保持。未进入 deploy，旧服务健康。保留失败记录，停止 oneoff 并重跑同SHA失败发布任务，不修改或跳过门禁。

原始数据库、选择清单、增量、消费者响应、保护指纹、维护日志和Actions记录保存在ignored `output/album-production/`；线上浏览器证据保存在ignored `output/playwright/album-production/`，不提交真实数据、密钥或截图。服务器备份及回退镜像保留。
