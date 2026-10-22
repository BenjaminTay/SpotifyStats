# 发行日期证据与精度

对应 `SS-2026-09-24-003`；规则版本 `release_date_evidence_v3_independent_dates`，schema94。

## 来源与持久化

[Spotify Album 官方合同](https://developer.spotify.com/documentation/web-api/reference/get-an-album)把 `release_date` 和 `release_date_precision` 列为必需字段，精度枚举为 year、month、day。官方页面没有承诺缺失/异常值的容错行为，示例还包含年月字符串与 year 精度不一致；本项目独立校验日历和二者一致性。

- 原始日期按来源字符串保存，不补齐月日。year 对应 YYYY，month 对应 YYYY-MM，day 对应合法 YYYY-MM-DD，包括闰年。
- `spotify_album_meta.release_date_precision` 仅保存来源声明，NULL 表示未知。日期与精度在同一事务中发布。新增观测表 `spotify_album_date_observations` 保存收到的日期、精度、状态、来源、旧值和运行 ID。
- 来源确认、日历合法且范围兼容时，允许精度提升；来源冲突、精度倒退、缺失或异常刷新保留可靠旧值，记录原因。重复相同输入不新增语义 revision 或重复拒绝事件。冲突需要单独审阅，不自动覆盖旧日期。
- 新缓存收到只有字符串的旧格式输入时保留原文，但不标为来源已确认。既有可靠 pair 不会被缺失精度的输入拆开。
- 迁移只增加列与观测表，不推断来源精度，不改原始字符串、播放、歌曲、署名、人工决定或 membership。受控 seed 的来源精度是明确构造的合成证据。

## 旧缓存与状态

解析同时返回 `format_precision` 与来源 `precision`：前者只识别合法字符串形态，后者必须有来源声明。`confirmed` 表示合法且一致；`legacy` 表示格式可识别但无来源精度；`missing`、`invalid`、`inconsistent` 分别表示缺失、非法日历/格式、声明与日期不一致。

legacy 的完整 ISO 字符串（包括 01-01、每月首日）不能证明真实发行日。当前日期展示降为年份；合法来源 year/month/day 分别显示年、年月、完整日期。原文保留在元数据中供核查，展示值由 `release_date_display` 提供；异常值不冒充日期。

合法 legacy 的比较证据只到年份，`comparison_start/end` 为该年边界；年月或完整字符串均不证明月日，不特殊识别首日。`start/end` 是经过日历校验的字符串形式边界，保留用于确定性展示排序和既有兼容过滤，不能用于确认发行日。来源声明合法且一致时，比较范围才使用该来源的年/月/日精度。

同一 Spotify Album ID 的新来源证据可纠正同年 legacy 的月日或降到来源 year；日期与精度一起安装，旧 pair 保留在观测审计中。legacy 不同年份仍为冲突；已经来源确认的冲突、精度倒退和异常输入继续保留旧 pair。项目精度同步须校验拟确认的精确 pair 与所有链接来源，不能仅用目标 legacy 的年范围掩盖两个来源 day 冲突；人工项目日期保持。

## 比较与排序

| 结果 | 证据合同 |
| --- | --- |
| same（确定相同） | 两个来源确认的 day，且合法日期相同 |
| compatible（范围兼容） | 比较证据范围重叠，包括相同年/月、不同精度及 legacy 同年；不能证明同一发行日 |
| conflict（明确冲突） | 可证明的比较范围不重叠；legacy 只能证明年份冲突 |
| unknown（无法判断） | 缺失、异常或声明不一致 |

日期排序按校验后的字符串形式范围起点、终点及稳定身份作确定性排序，异常值后置。legacy 的月日只是稳定展示排序信息；范围重叠时不宣称已经证明真实先后。

同一 Spotify Album ID 仍需完整目录、稳定身份等既有证明。不同 ID 的 catalog alias 日期强证据必须为 same；兼容范围不能代替强证据。remaster/deluxe 的年份顺序仅是既有完整目录/有序录音证据的约束。规划候选保持只读，不自动批准关系；人工批准和 project membership 合同保持。

详情代表元数据比较必须传入项目与候选的实际精度，不能只传字符串。明确 conflict 的候选不提供项目日期旁的厂牌、发行曲目数或热度；无可用候选时保留项目日期/类型，来源字段缺省。same/compatible 属于可用日期组，优先于 unknown；组内保留主来源、名称/基础名称和类型约束，再以 same、compatible、unknown 作日期证据排序，最后比较置信度、播放量和稳定键。legacy 同年仍只能算 compatible；日期不是身份或归并批准。Records 可信原版目录同样加载两侧精度，保持完整目录/稳定曲目与身份条件。

详情 full/summary 回退使用 `album_detail_meta_v2_source_precision` 进入进程 revision key；轻量 summary 的元数据每次从当前 SQLite 重新选择，持久搜索快照只提供统计/身份，不缓存该代表元数据，无需为此重建全库搜索/Billboard。Records sort/build 版本升级，拒绝复用旧版目录选择结果。

## 计算与读取

- 合法日期可支持年份分析；来源 month 可以支持月份分析。字符串形态推断有独立 legacy 标记。
- 发行周期、按发行日的七日窗口、排行对齐、提前单曲及日级 Records 里程碑只消费来源确认的 day，或本项目已经审核且范围适用的独立 day。证据不足返回 `unavailable / release_day_unconfirmed`，发行对比逐项返回 `unavailable` 列表，或空的不可计算派生项；不使用首次播放日或父版本日期填补发行日。
- Billboard 对来源确认的日期使用来源范围上界作保守过滤。legacy 保留既有字符串形式范围上界的兼容 cutoff，明确属于格式推断，不声称该日是确定发行日或播放已被来源证明位于发行之后；比较范围改为年份不能悄悄改变这条历史统计过滤。日/周对齐仍禁止 legacy，非榜单播放不应用发行后过滤，不新增播放贡献。legacy cutoff 的来源不确定性须在正式副本补证和结果差异中继续审阅。
- 专辑项目只通过明确维护或已有重建同步非人工项目的日期精度；人工日期与 membership 不随补证改变。
- 对决周期复用 L2/L3 project 身份和正式成员计次；主项目使用既有确认的主发行来源，明确成员版本保留自己的日期。主来源优先既有高置信 Spotify project 绑定；无明确绑定时仍须满足对应版本及艺人证据，不以同名、最早日期或播放最多代选。
- 默认发行来源集合混有同名 album/compilation 与 single 时，专辑优先非 single 证据；明确单曲项目优先 single。single-only 与未知旧类型保持可用，已有明确 primary 绑定和成员版本锚点优先；筛选不删除来源关系，不把不同专辑的日期冲突自动消解。
- 对决选择器提供稳定 `project_id`，队列、普通榜单、个人统计/排名、发行周期请求、查询键、响应列和详情深链共同保留该身份。同名不同发行分别选择；显式 ID 必须通过艺人和 L2/L3 范围校验，错误 ID 不回退名称，旧名称调用仅在唯一时兼容。
- 项目重建与维护使用同一日期 pair 决策。已确认的项目日期与精度不被较弱名称匹配覆盖；新来源不一致时保留锚点和审核原因。legacy 仅在主来源全部确认且 pair 一致、比较范围兼容时纠正；人工日期保持。重复同步和重建必须稳定。
- 周期对比逐项区分 `release_source_unconfirmed`（对应发行来源尚未确认）、`release_day_unconfirmed`（来源缺确认日）、`release_date_coarse`、`release_date_invalid`、`release_date_conflict`、`artist_identity_unconfirmed`、`release_ambiguous` 和 `entity_not_found`。缺快照属于请求级不可用，不能伪装空指标；真实零、未上榜、无窗口播放与缺证各自表达。
- 对外周期表保持修复前的六项指标与原有布局：首发排名、最高排名、发行周播放、艺人影响力、大盘影响力、半数播放距。不增加发行日期、计算状态、诊断说明或重试控件；缺失/不可用值显示“—”，真实0保留，加载沿用原版文案。接口继续保留逐项状态、原因及日期事实，UI回退不影响计算和项目身份修复。
- 私有和公开周期对比均只消费已安装证据和 exact-ready 成品，不在读取时联网补证、写库、排队或冷建。部分不可用保留请求列和原因，其余目标继续计算。
- 对决影响力的先行单曲沿用同一项目/版本、Album 艺人与 confirmed/day 合同，候选歌曲来自当前 L2/L3 有效成员的完整来源集合；候选还须具有实际共享 Album 成员关系、来源类型 single 且早于目标发行日。不能通过全局同名 `LIMIT 1` 选择其他艺人或版本。存在歧义、日期冲突或粗日期时排除该先行候选，按既有公式回退发行前四周/全时段基线；主发行已可计算的其他指标保持。读取显式传入已验证先行证据，不调用旧名称补证 helper。
- 日期和精度进入 Analysis、Archive、治理、Billboard、Yearly 现有 revision/cache 合同；规则 builder/version 一并升级，旧结果不能作为新规则的精确结果或跨规则 LKG。
- 公开 GET 不补证、联网、写库、冷建或排队。当前隐藏的歌词、发行档案、发行周期、艺人生涯页签保持隐藏。

## 有界维护

`scripts/backfill_spotify_release_dates.py` 必须指定隔离数据库副本。`--manifest-only` 只读枚举已播放、曲目元数据、容器关联、项目绑定及本地 Album 引用，孤立缓存单列；每个显式批次为 1–200 个 Album ID。按语义缺证选择，确认到年/月与待审冲突不因缺 day 无限重抓。

同一个官方 Album 响应安装日期 pair 和 Album 艺人证据，纯证据维护不抓曲目分页，不改目录、身份批准或播放。默认仅在内存副本预览，`--apply` 才安装；manifest 和每批输入 fingerprint 检查来源漂移。`--observations-json` 离线重放，`--fetch-only` 保存响应，失败恢复只请求缺失/失败 ID。联网使用既有 Provider，终局同步还须覆盖未进入本次 fetch 的已知确认来源，不能只同步新抓取的 ID。

调用前先完成迁移，在共享验证锁下操作；数据库、响应和截图留在 ignored 输出中。正式应用先 Online Backup 与副本演练，保护原始事实、人工决定和成员关系，并准备受影响派生成品；输入漂移时停止，不能用旧整库覆盖新增用户数据。完整执行和验收见[发行周期修复规划](../archive/06-productization-closeout/2026-10-21-versus-release-cycle-repair-plan.md)。

配套搜索快照淘汰必须先显式删除同一淘汰范围内的详情投影、来源事实和投影状态，再删除父快照，不能依赖连接已启用外键级联；当前/前代、活动指针及pending/running的保留条件保持一致。副本准备先维护revision/schema合同，应用前后检查外键完整性。历史孤立派生缓存的修复须单独留证，仅删除失去父快照的行，保留有效快照内容、原始事实与成员。

## 独立发行日期登记与审核

Spotify 只声明 year/month 时，独立官网、厂牌或同期发行材料另存于 schema94 的 `album_release_date_assertions`，不得把它们写成 `spotify_album_meta` 的来源 day 声明。每项记录明确 project、既有 Spotify 目录、原专辑日或版本日、地区、介质、适用说明、来源 URL/标题/日期主张/核验时间，以及登记人与运行 ID；`album_release_date_events` 保留登记、批准、拒绝和撤销审计，revision 单独维护。

登记为 pending，不改变计算。批准前同时核对非人工项目身份、既有来源选择、完整有序目录、Album 艺人稳定 ID、原始日期 pair 和旧项目日期。候选必须与来源集合及旧项目的可证明日期范围兼容；明确跨年或 day 冲突保留 pending，不能经普通精度补齐自动覆盖。来源批准、项目成员、歌曲归属和日期治理是分别审核的事实。

审核入口为 `scripts/govern_album_release_dates.py`，提供 `list / stage / approve / reject / revoke`。必须显式指定 `--db-path` 与输出；修改要求 actor/run-id，审核要求 reason。默认在临时磁盘 Online Backup 副本演练并丢弃，`--apply` 仅允许显式隔离副本，拒绝配置中的正式库及同 inode 别名。每批1–50项；approve可使用具体manifest或已登记ID，stage只登记。正式应用仍走 fresh Online Backup、副本准备、来源围栏、可恢复本地切换与消费者验收，不能将维护 CLI 直接指向日常库写入。

批准/撤销在调用事务内完成，合批比较 L3 规划前后的歌曲集合、目标项目、决定语义及问题/排除集合；改变任何歌曲归属或成员含义就回滚整批。只允许日期排序证据变化，保留全部既有已发布归属决定，仅更新其上游 revision 和摘要；不顺便采用已有的无关规划差异。重复批准不追加事件或 revision。撤销保留原证据与审计，在项目身份及当前批准日期仍相同时恢复此前项目 pair；来源后来刷新失效也可撤销，不要求将旧来源重新变为有效。

统一 `release_anchor_sources` 仅为本项目的主专辑返回已批准、守卫仍匹配的日期事实，并在返回对象中分列原 Spotify pair、independent origin 与 assertion ID。其他项目及明确成员版本不能借用此日，目录/日期/艺人或主专辑漂移时停止使用旧批准事实。普通读取不建表、不联网、不审核、不排队。`project_release_date_pair` 与周期解析共同消费该事实，重建/同步稳定；派生项目日期及 album project revision 在维护事务内更新，相关榜单 cutoff、搜索、详情、排名、年度等使用相同日期和新规则版本，旧精确成品不可冒充新版本 ready。

命令示例（路径均为显式私有副本；缺省不写该副本）：

```bash
.venv/bin/python scripts/govern_album_release_dates.py --db-path /absolute/private-copy.db --action stage --manifest /absolute/dates.json --actor reviewer --run-id date-review --output /absolute/stage-preview.json
.venv/bin/python scripts/govern_album_release_dates.py --db-path /absolute/private-copy.db --action approve --assertion-ids 1 2 --actor reviewer --run-id date-review --reason verified-scope --apply --output /absolute/approve-copy.json
.venv/bin/python scripts/govern_album_release_dates.py --db-path /absolute/private-copy.db --action list --output /absolute/date-registry.json
```

manifest 的 `items` 每项需要 `project_id`、`spotify_album_id`、`release_date`、`date_kind`（original_release或edition_release）、`territory`、`medium`、`scope_note`、`sources`；sources每项含公开HTTPS的url、title、source_kind、claim、observed_at。可携带expected_source_pair与expected_project_pair作显式旧值守卫。独立来源的原版日与再版/地区/预购/单曲日期必须分别记录，不能仅凭同名或多数网站一致批准。
