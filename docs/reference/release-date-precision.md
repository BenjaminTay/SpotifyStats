# 发行日期证据与精度

对应 `SS-2026-09-24-003`；规则版本 `release_date_evidence_v2_legacy_year`，schema89。

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

## 计算与读取

- 合法日期可支持年份分析；来源 month 可以支持月份分析。字符串形态推断有独立 legacy 标记。
- 发行周期、按发行日的七日窗口、排行对齐、提前单曲及日级 Records 里程碑只消费来源确认的 day。证据不足返回 `unavailable / release_day_unconfirmed`，发行对比逐项返回 `unavailable` 列表，或空的不可计算派生项；不使用首次播放日或父版本日期填补发行日。
- Billboard 对来源确认的日期使用来源范围上界作保守过滤。legacy 保留既有字符串形式范围上界的兼容 cutoff，明确属于格式推断，不声称该日是确定发行日或播放已被来源证明位于发行之后；比较范围改为年份不能悄悄改变这条历史统计过滤。日/周对齐仍禁止 legacy，非榜单播放不应用发行后过滤，不新增播放贡献。legacy cutoff 的来源不确定性须在正式副本补证和结果差异中继续审阅。
- 专辑项目只通过明确维护或已有重建同步非人工项目的日期精度；人工日期与 membership 不随补证改变。
- 日期和精度进入 Analysis、Archive、治理、Billboard、Yearly 现有 revision/cache 合同；规则 builder/version 一并升级，旧结果不能作为新规则的精确结果或跨规则 LKG。
- 公开 GET 不补证、联网、写库、冷建或排队。当前隐藏的歌词、发行档案、发行周期、艺人生涯页签保持隐藏。

## 有界维护

`scripts/backfill_spotify_release_dates.py` 必须指定隔离数据库副本和 1–200 个 Album ID；不自动发现/重抓全库，不改目录、身份或播放。默认仅在内存副本预览，`--apply` 才安装日期观测及非人工项目精度。可通过 `--observations-json` 重放已经取得的来源响应；联网使用现有 Spotify Provider。调用前先完成迁移，在共享验证锁下操作；数据库、响应和截图留在 ignored 输出中。
