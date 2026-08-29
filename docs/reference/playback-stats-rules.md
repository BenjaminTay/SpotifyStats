# 播放统计与版本合并规则：最新版

> 创建日期：2026-06-18；最近修订：2026-08-30
> 状态：规则源文件，作为后续实现与验收依据
> 来源：整合 [`docs/archive/02-react-productization/playback-stats/2026-06-12-playback-stats-rules-v1.md`](../archive/02-react-productization/playback-stats/2026-06-12-playback-stats-rules-v1.md)、[`docs/archive/02-react-productization/playback-stats/2026-06-12-playback-stats-implementation-plan.md`](../archive/02-react-productization/playback-stats/2026-06-12-playback-stats-implementation-plan.md)，以及后续对歌曲/专辑多版本语义的确认。

---

## 1. 总体目标

SpotifyStats 的统计口径要回答三个不同问题：

1. 我实际听了多少次音乐。
2. 这些播放应该归到哪一首歌、哪一张专辑、哪位艺人。
3. 在不同版本合并级别下，榜单和详情页应该怎样展示。

因此所有统计都分三层处理：

| 层级 | 输入 | 输出 | 说明 |
|------|------|------|------|
| 播放事件层 | Spotify Extended Streaming History 原始行 | 有效播放事件 | 只处理过滤、连续播放合并、动态阈值；不做跨 track_id 的版本合并 |
| 实体归属层 | 有效播放事件 | 曲目/专辑/艺人归属播放 | 按歌曲、专辑项目、艺人做聚合、扇出和版本合并 |
| 展示解释层 | 聚合结果 | 榜单、详情页、来源拆分 | 解释 canonical 名称、封面、归属专辑、版本来源和贡献比例 |

核心原则：

- 有效播放事件不随 `merge_level` 改变。
- 跨歌曲版本、跨专辑版本的合并只发生在实体归属层。
- 专辑播放量定义为“专辑项目曲目总播放量”，不是单一 album container 的 source plays。
- Billboard 专辑周榜不能让专辑在正式发行前入榜。

---

## 2. 术语定义

| 术语 | 定义 |
|------|------|
| 原始播放行 | `plays` 表中导入的原始记录，未经过滤或合并 |
| 有效播放事件 | 经 music-only、连续播放合并、动态阈值过滤后的逻辑播放事件 |
| source album | 这一次播放在 Spotify 历史记录中显示的来源专辑/单曲/合辑容器 |
| canonical song | 在当前合并级别下用于统计和展示的歌曲实体 |
| album container | Spotify 中的一条具体 album/single/compilation 发行物记录 |
| album project | 统计意义上的专辑项目，例如 `GUTS` 项目包含标准版、豪华版和归属到该项目的先行单曲 |
| 专辑播放量 | album project 内 canonical song 播放量的去重求和 |
| 来源拆分 | 对专辑播放量按原版专辑、豪华版、单曲版、精选集等 source album 来源做解释 |
| canonical track | 本地稳定基础身份；一个基础身份可持有多个完全等价的 provider ID，一个 provider ID 只能有一个 owner |
| L2 | 默认统计模式，同录音/同发行项目口径 |
| L3 | 可选统计模式，同作品/同专辑项目口径 |

---

## 3. 播放事件层规则

### R1. 音乐记录过滤

默认只统计音乐播放：

- `track_id IS NOT NULL` 的记录进入音乐统计。
- 播客、有声书等非音乐记录不进入音乐统计。
- `skipped` 字段不作为硬过滤条件；它在 Spotify 历史数据中不够可靠。

### R2. 动态有效播放阈值

一次播放记录或合并后的逻辑事件被计为有效播放，需满足：

```text
ms_played >= max(30000, duration_ms * 0.1)
```

如果 `duration_ms` 缺失或为 0，则回退到：

```text
ms_played >= 30000
```

设计理由：

- 普通 3-4 分钟流行歌仍以 30 秒为有效播放阈值。
- 8-10 分钟长曲目不能只听 30 秒就计为有效。
- 极短 interlude 仍保留 30 秒保底，避免过度计数。

### R3. 连续播放合并

连续播放合并只处理相邻、来源一致且属于同一 session 的同一 `track_id`：

| 情况 | 是否合并 |
|------|:--:|
| 同一 `track_id` 连续出现 | 是 |
| 同一 `track_id`，但 `source_album_id` 改变 | 否 |
| 不同 `track_id`，即使属于同一 recording/composition group | 否 |
| A -> B -> A 这种非连续回到 A | 否 |

合并计算：

```text
total_ms = sum(ms_played)
full_plays = total_ms // duration_ms
remainder = total_ms % duration_ms
logical_plays = full_plays + (1 if remainder >= effective_threshold else 0)
```

合并后展开为逻辑播放事件：

- 完整播放事件：`ms_played = duration_ms`
- 余数事件：`ms_played = remainder`
- 每个展开事件都拥有独立 `counted_at`，不再继承合并组首行或末行时间。
- 第 `k` 个完整事件在累计有效收听达到 `k * duration_ms` 时成立。
- 余数事件在累计有效收听达到 `full_plays * duration_ms + effective_threshold` 时成立。

### R4. 连续播放边界

连续播放合并必须受 session 边界约束：

- 默认 `max_merge_gap_minutes = 5`，并由服务端 Settings 作为唯一事实源；桌面与手机使用同一设置。
- 间隔按“下一行推断开始时间 - 上一行停止时间”的实际空闲时间计算，不按两个停止时间直接相减。因而一首 6 分钟歌曲无缝重播不会被误判为超过 5 分钟。
- 实际空闲时间 `<= 5 分钟` 可继续合并；超过 5 分钟立即开启新 session。
- 原始行的推断重叠不超过 2 秒时视为时间戳舍入噪声并调整为单调时间线；更大的重叠开启新 session，避免生成不可能的播放顺序。
- 自然日、月份、年份和 Billboard 周不再作为合并边界。先在完整时间线上重建逻辑事件，再做时间归属，保证改变查询分区不会改变事件数量。

### R4.1 次数时间与收听时长归属

逻辑事件同时维护两个互不混用的时间语义：

1. **播放次数**归到 `counted_at`：即该次完整播放或余数播放刚刚达到成立条件的时刻。`ts`、`ts_date`、`ts_year`、`ts_month`、`ts_week`、`ts_dow`、`ts_hour` 均由 `counted_at` 按 `Asia/Shanghai` 重建。
2. **收听时长**归到推断收听区间：每条原始记录以 `[ts - ms_played, ts)` 近似，跨小时、自然日或 Billboard 周边界时按边界切片。

因此，一次跨午夜完成的播放可以在次日增加 1 次播放，同时把午夜前后的收听分钟分别计入两天。Billboard 预聚合使用独立 `play_count` / `total_ms` 权重：事件行只贡献次数，切片行只贡献时长；任何消费者不得用切片行数代替播放次数。

### R4.2 逻辑播放事件身份

连续播放合并和有效阈值过滤完成后，每一行最终逻辑播放事件必须获得一个稳定的、当前数据帧内唯一的 `_logical_event_id`，并在艺人署名扇出前生成。

- 同一个逻辑事件展开到多个 credited artist 时，所有署名行共享同一个 `_logical_event_id`。
- 一个原始 `play_id` 因连续播放合并而展开为多个逻辑事件时，这些事件必须拥有不同的 `_logical_event_id`，不能仅按 `play_id` 去重。
- 艺人身份规范化时，优先按 `_logical_event_id + canonical artist_id` 去重；`_artist_event_id` 仅作为兼容旧消费者的别名。
- 单曲、track-source 和专辑项目聚合均基于合并后的逻辑事件行；艺人预聚合必须与原始艺人路径保持相同的逻辑事件粒度。
- 任何重建后的预聚合表都必须通过原始路径对账，至少覆盖艺人周榜的 `play_count` 与 `total_ms`。
- 预聚合先写入连接级影子表，再在一个事务内同时发布单曲、专辑、track-source、艺人和参数指纹；构建或发布失败时继续保留上一份完整快照。

### R5. 播放事件层不做版本合并

无论 `merge_level` 是 L1、L2 还是 L3，播放事件层都不跨 `track_id` 合并。

例如：

- `Karma` 和 `Karma (feat. Ice Spice)` 是两个不同 track_id，连续播放时不合并为一个播放事件。
- `Style` 和 `Style (Taylor's Version)` 连续播放时不合并为一个播放事件。
- 它们只会在 L3 的实体归属层聚合为同一 canonical song。

---

## 4. 合并级别总览

### R6. L1：物理实体口径

L1 下，只要 ID 不同，就不是同一首歌或同一张专辑：

- 不同 `track_id` 独立统计。
- 不同 `album_id` 独立统计。
- 单曲版、专辑版、豪华版、精选集版本都各自排名。

### R7. L2：同录音/同发行项目口径

L2 是默认推荐口径。

歌曲层面：同一份录音合并为同一首歌。包括：

- 单曲专辑中的单曲版。
- 录音室专辑中的 track 版。
- Explicit / Clean。
- Remastered。
- 区域限定但录音相同的版本。

专辑层面：同一发行项目合并为同一 album project。包括：

- 标准版。
- Deluxe / Expanded。
- Anniversary / Remastered。
- Clean / Explicit。
- 区域限定版。

L2 不合并：

- Acoustic 版。
- Live 版。
- Remix 版。
- Radio Edit。
- Demo。
- Taylor's Version 或其他重录版本。
- Live / Remix / Acoustic 专辑。
- 重录专辑。

### R8. L3：同作品/同专辑项目口径

L3 是宽松口径。

歌曲层面：同一作品的所有录音版本合并为同一 canonical song。包括：

- L2 已合并的所有版本。
- Acoustic。
- Live。
- Remix。
- Radio Edit。
- Instrumental。
- Demo。
- Taylor's Version 或其他重录版本。
- 合作版。

专辑层面：同一专辑项目的所有发行合并。包括：

- L2 已合并的所有发行。
- Live 专辑。
- Remix 专辑。
- Acoustic 专辑。
- Taylor's Version 或其他重录专辑。

---

## 5. 歌曲版本合并规则

### R9. 曲目聚合键

| 级别 | 曲目聚合键 | 行为 |
|------|------------|------|
| 基础身份 | `canonical_track_id` | 系统治理层，不作为用户可选统计模式 |
| L2 | `recording_group_id`，未入组则回退 `canonical_track_id` | 同录音聚合；公开默认 |
| L3 | `composition_group_id`，未入组则回退 L2/canonical key | 同作品聚合 |

### R10. L2 同录音判断

以下版本可在 L2 合并：

| 类型 | L2 合并 | 说明 |
|------|:--:|------|
| 单曲版与专辑 track 版 | 是 | 同一份录音，只是发行容器不同 |
| Explicit / Clean | 是 | 同录音的内容分级版本 |
| Remastered | 是 | 同一录音或母带的后期版本 |
| 区域限定版 | 是 | 发行市场不同，不改变录音本体 |
| Spotify relink 版本 | 是 | 市场可用性替代，不代表新录音 |

### R11. L3 同作品判断

以下版本只在 L3 合并：

| 类型 | L2 | L3 | 说明 |
|------|:--:|:--:|------|
| Acoustic | 否 | 是 | 不同录音/编曲，但同作品 |
| Live | 否 | 是 | 不同录音场合，但同作品 |
| Remix | 否 | 是 | 再创作版本，仍可归入原作品 |
| Radio Edit | 否 | 是 | 剪辑/时长差异较大 |
| Instrumental | 否 | 是 | 无人声版本 |
| Demo | 否 | 是 | 小样或早期录音 |
| Taylor's Version / 重录 | 否 | 是 | 不同录音 session，同作品 |
| 合作版 | 否 | 是 | 需满足 R12 |

### R12. 合作版合并条件

合作版可在 L3 合并到原作品组，条件是：

- 合作版的参与艺人中包含原版的主歌手。

例如：

- `Karma` 与 `Karma (feat. Ice Spice)` 可在 L3 合并，因为 Taylor Swift 仍参与合作版。

注意：

- 合作版合并只影响歌曲播放量和歌曲榜。
- 艺人榜仍按实际参与艺人扇出，不能把原版播放 credit 给只参与合作版的艺人。

### R13. 不自动合并的歌曲

以下情况默认不自动合并：

- 不同艺人的同名歌曲。
- 翻唱版本，即使曲名相同。
- 插曲、采样、mashup、parody、translation。
- 主艺人不同且原版主歌手没有参与的新 remix。

如果用户明确手动确认，可以进入人工合并组，但不能由标题相似自动推断。

### R14. canonical song 展示

合并后的歌曲必须通过同一个只读批量 `TrackPresentation` 解析器分别确定 album project
归属、具体展示发行版和封面发行版，不能再从代表 Track 的 `tracks.album_id` 反推。规则顺序如下：

- 名称优先使用原始作品名，去掉常见版本后缀。
- album project owner 先选人工治理项目，再选 release scope 的非精选项目；在同一项目中，
  `standard/original_album` 高于 `deluxe`，Deluxe-only / vault track 保留为 `deluxe`。
- 具体展示发行版优先使用原版录音室专辑主版本。即使当前播放只观察到 Deluxe，只要胜出的原版
  Spotify album catalog 通过规范化 Spotify Track ID 或 ISRC 证明包含该 L2 录音，也按标准曲处理。
- 原版 catalog 不包含该录音时，显示最早正式收录它的豪华版；多个豪华版按发行日期、稳定
  `album_id` 消歧。没有 album project 时，按 LP、EP、独立单曲、精选集顺序回退，并显式标记
  `fallback`。
- 封面选择与归属独立：同一 L2 录音存在真正的单曲发行时优先单曲封面；Spotify 标为
  `single` 但按曲目数判定为 EP 的发行不能抢占单曲封面。没有单曲时使用展示发行版，再回退
  owner 主版本和其他可靠来源。
- 普通榜单、搜索、详情、首页、年度总结、Wrapped 和播放记录消费上述 canonical presentation；
  最近播放、分页播放明细和版本来源拆分仍展示事件的实际 `source_album_id`，不能被 canonical
  presentation 覆盖。
- 解析结果至少包含 `album_project_id/name`、`display_album_id/name`、`membership_role`、
  `cover_album_id/url/source` 和 `resolution_status`。Album Project 发布递增 O(1) revision，候选
  generation 将 policy version 与该 revision 纳入 source fence，继续以 shadow + LKG 原子切换。

示例：

- `vampire` 显示单曲版封面，但归属专辑显示 `GUTS`。
- 原版 `GUTS` 不收录而只在豪华版首次出现的曲目，显示并使用该豪华版封面；不能因为同项目存在
  原版就伪装成原版曲目。
- `Say Don't Go (Taylor's Version)` 是 `1989 (Taylor's Version)` 独有歌曲，在 L3 下归属到 `1989` album project。

---

## 6. 专辑项目与专辑播放量规则

### R15. 专辑播放量定义

专辑播放量定义为：

```text
album_project_plays = sum(play_count(canonical_song) for canonical_song in album_project_track_set)
```

这意味着：

- 专辑播放量不是某个 album container 的 source plays。
- 先行单曲在专辑发行前产生的播放，也计入该专辑的全时专辑播放量。
- 同一首 canonical song 在同一个 album project 内只能贡献一次。

### R16. 专辑项目曲目集合

每个 album project 维护一个去重后的 canonical song 集合。

来源包括：

- 原版录音室专辑曲目。
- 标准版与豪华版共有曲目。
- 豪华版/扩展版独有曲目。
- 先行单曲，只要后续被收入该专辑项目。
- L3 下对应重录专辑中的同作品曲目。
- L3 下重录专辑独有曲目。

去重规则：

- 标准版和豪华版都包含的同一 canonical song，只算一次。
- 单曲包和录音室专辑都包含的同一 canonical song，只算一次。
- 精选集再次收录的既有 canonical song，不为精选集额外重复计数。

### R17. 基础发行与 L2/L3 专辑聚合键

| 级别 | 专辑聚合键 | 行为 |
|------|------------|------|
| 基础发行 | `album_id` | 系统内部的具体 album container，不作为用户可选统计模式 |
| L2 | `album_project_id` / `release_group_id(scope=release)` | 标准版、豪华版、区域版等合并 |
| L3 | `album_project_id` / `release_group_id(scope=composition)` | 重录、live、remix、acoustic 等项目级合并 |

### R18. 标准版与豪华版

L2 下，标准版和豪华版合并为同一 album project。

合并后：

- 共有曲目不重复计数。
- 豪华版独有曲目加入 album project_track_set。
- 专辑播放量按整个去重后的曲目集合求和。

例如：

- `GUTS` 与 `GUTS (spilled)` 在 L2 合并。
- `vampire` 只贡献一次。
- `obsessed`、`so american` 等豪华版独有曲目额外贡献。

### R19. 重录专辑

L2 下，重录专辑不合并。

L3 下，重录专辑参与同一 album project 合并。

例如：

- L2：`1989` 与 `1989 (Taylor's Version)` 独立。
- L3：`1989` 与 `1989 (Taylor's Version)` 合并为同一 album project。
- `Style` 与 `Style (Taylor's Version)` 合并为同一 canonical song。
- `Say Don't Go (Taylor's Version)` 作为 `1989 (Taylor's Version)` 独有曲目，也计入 `1989` album project。

### R20. 专辑发行前播放

如果单曲先于专辑发行：

- 该单曲发行后、专辑发行前的播放计入 album project 的全时专辑播放量。
- 专辑详情页、全时专辑榜、年度/长期统计可包含这些预发行播放。
- Billboard 专辑周榜不能让该专辑在正式发行前入榜。

Billboard 周榜中：

- 只有 `play_ts >= album_project.release_at` 的播放事件可计入该专辑项目当周得分。
- 如果专辑尚未发行，即使其先行单曲播放量很高，也不能出现在专辑周榜中。
- 发行后不回填专辑发行前历史周的榜单名次。

---

## 7. 专辑播放量来源拆分

### R21. 来源拆分用途

专辑播放量页应提供来源拆分，用于解释 album project plays 来自哪些 source album。

来源拆分是解释性视图，不改变专辑播放量总口径。

### R22. 来源桶

每个贡献到 album project 的播放事件按其 `source_album_id` 归入一个来源桶：

| 来源桶 | 说明 |
|--------|------|
| 原版专辑 | 播放时 source album 是原版录音室专辑 |
| 豪华版/扩展版 | 播放时 source album 是 deluxe、expanded、anniversary 等版本 |
| 单曲版 | 播放时 source album 是 single / single package |
| 精选集/合辑 | 播放时 source album 是 compilation / greatest hits |
| Live / Acoustic / Remix 项目 | L3 下才可能贡献到同一 album project |
| 重录版本 | L3 下才可能贡献到同一 album project |
| 其他来源 | soundtrack、未知发行物、无法分类来源 |
| 推断来源 | 历史 backfill 无法还原真实 source album，只能从 track primary album 推断 |

### R23. 来源拆分不重复计数

一个有效播放事件在某个 album project 的来源拆分中只能进入一个来源桶。

因此：

- 来源桶之和应等于该 album project 的播放量。
- 同一 canonical song 即使存在于多个发行容器，也不能让同一个播放事件进入多个来源桶。

---

## 8. 精选集与合辑规则

### R24. 全由既有歌曲组成的精选集

如果精选集内所有歌曲都是已有录音室专辑、EP 或单曲项目中的歌曲组合：

- L1 下可作为独立 album container 显示。
- 非 L1 下默认不作为独立 album project 进入专辑榜。
- 这些播放按 source breakdown 显示为“精选集/合辑来源”，但播放贡献回流到歌曲的 primary album project。

### R25. 含独有新歌的精选集

如果精选集包含独有新歌：

- 既有歌曲仍回流到各自 primary album project。
- 独有新歌形成一个 compilation-exclusive project。
- 这个 project 在专辑榜中表现为“只有独有歌曲贡献的 EP/项目”。

例如：

```text
精选集 = 已有歌曲 A/B/C + 新歌 X/Y
非 L1 下：
- A/B/C 回流到各自原始 album project
- X/Y 组成该精选集的独有项目播放量
```

### R26. catalog membership 视图

可选提供 catalog membership 视图，用于回答“这首歌出现在多少发行物里”。

该视图必须明确标注：

- 同一播放可能归属于多个 album container。
- 专辑播放次数之和可能大于有效播放事件数。
- 它不能替代默认专辑榜。

---

## 9. 专辑类型过滤

### R27. 专辑类型

专辑类型按 Spotify metadata 与曲目数/总时长共同判断：

| 类型 | 判断 |
|------|------|
| LP | 通常 `album_type=album` 且曲目数 >= 7 或总时长 >= 25min |
| EP | 通常 3-6 首，或总时长短于 LP |
| Single package | 1-2 首 |
| Compilation | Spotify 标记为 compilation，或人工标记为精选/合辑 |

### R28. 默认专辑榜过滤

默认专辑榜：

- 包含 LP。
- 包含 EP。
- 默认排除 single package。
- 精选集按 R24/R25 处理。

前端可提供筛选：

- 包含 compilation-exclusive project。
- 显示 L1 album container。
- 显示 source album plays 解释视图。

---

## 10. 艺人归属规则

### R29. 艺人 fan-out

艺人统计按参与艺人扇出：

- 一首歌有 N 位艺人，每次有效播放为每位参与艺人各计 1 次。
- 所有艺人播放次数之和可能大于有效播放事件数。
- UI 必须标注这一点。

fan-out 后必须保留稳定的逻辑播放事件标识。任何依赖时间顺序的艺人纪录都应按逻辑事件序列判断，不能把同一播放展开出的另一位合作艺人行当成新的中间播放。

### R30. 歌曲合并不改变艺人 credit

L2/L3 歌曲合并不把某个版本的艺人 credit 复制给其他版本。

例如：

- `Karma` 和 `Karma (feat. Ice Spice)` 在 L3 下合并为同一 canonical song。
- Ice Spice 只获得 feat 版本实际播放的艺人 credit。
- Ice Spice 不获得 `Karma` 原版播放的艺人 credit。

### R31. 非艺人维度展示

曲目榜、专辑榜和详情页中的 `artist_name` 是展示字段。

建议展示：

- canonical primary artist。
- featured artists。
- version-level artist differences。

但聚合键不能只依赖展示文本。

专辑所有权、专辑项目匹配和主艺人 join 必须使用 primary canonical artist，不能用完整展示署名做 identity key。艺人详情的歌曲播放排行继续使用有效署名 fan-out，因此合作曲可以进入合作艺人的歌曲榜；艺人详情的专辑播放排行只允许统计 canonical owner 为该艺人的 album projects。合作曲来自其他艺人的专辑时，该次播放不能让对方专辑进入合作艺人的专辑排行。

### R31a. 连续播放马拉松

“连续播放马拉松”统计过滤、有效播放判定和连续播放合并后的逻辑事件序列，并与“连续播放天数”严格分开：

- 歌曲：相邻逻辑事件的 canonical track key 相同时属于同一 run。
- 专辑：相邻逻辑事件的 canonical album project key 相同时属于同一 run。
- 艺人：相邻逻辑事件都包含目标 canonical artist 的有效署名时属于同一 run；同一事件 fan-out 的其他合作艺人行不得打断 run。
- 每个实体输出所有 run 中事件数最大的记录，同时累计该 run 的实际播放时长和起止时间。

因此艺人 run 可以大于其中任一专辑 run：例如连续听某艺人的其他歌曲后无缝进入同一艺人的整张专辑，艺人连续段会跨越专辑边界继续累计。

---

## 11. Billboard 周榜规则

### R32. 周榜基础管线

Billboard 周榜与个人统计使用同一基础规则：

1. 加载原始播放行。
2. music-only 过滤。
3. 同 `track_id` 连续播放合并。
4. 动态阈值过滤。
5. 周边界归属。
6. 只保留已经完整结束的榜单周。
7. 按 `merge_level` 应用曲目/专辑项目聚合。
8. 排名：`play_count DESC, total_ms DESC`；仍相同时使用稳定实体 identity，缺少 identity 时才使用规范化展示文本作为最终裁决键。相同输入不得因数据库或 DataFrame 行顺序不同而改变名次。

Spotify 导出不提供独立的“数据覆盖结束时间”，因此最新一条已导入播放所在的榜单周视为仍在观察中，不生成单曲、专辑或艺人周榜，也不进入在榜周数、走势、纪录、Power Score 和 Year-End 积分。只有严格早于该周的榜单周才视为完整周；后续导入跨过下一个周边界后，上一周才会进入榜单。完整周过滤只影响榜单事实，不删除播放记录，也不从全时播放次数和收听时长中扣除最新几天。

### R33. 曲目周榜

曲目周榜：

- L1 按 `track_id` 排名。
- L2 按 `recording_group_id` 排名。
- L3 按 `composition_group_id` 排名。
- 周榜中的 NEW/RE 等状态基于当前合并级别的 canonical key 判断。

### R34. 专辑周榜

专辑周榜使用 album project plays，而不是 source album plays。

某一周的 album project 得分：

```text
weekly_album_project_plays =
  sum(count(valid_play_events for canonical_song during this billboard_week
            where play_ts >= album_project.release_at)
      for canonical_song in deduped album_project_track_set)
```

约束：

- 专辑未发行前不能入榜。
- 发行后不回填发行前历史周。
- 先行单曲的发行前播放可计入全时专辑播放量，但不计入发行前周榜。
- 同一 canonical song 在同一 album project 当周只作为一个曲目成员求和一次；它当周的所有有效播放都计入。

### R35. 预聚合与 merge_level

`agg_weekly_*` 预聚合存储 base-grain：

- track_id x billboard_week。
- source_album_id / album_id x billboard_week。
- artist_id x billboard_week。

`merge_level` 不应进入基础有效播放事件或 base-grain 预聚合 hash。

基础身份、L2/L3 的差异在排名层通过 canonical key resolver 应用；公开消费只允许 L2/L3。

### R36. Billboard Year-End 年榜

Billboard Year-End 年榜不是单纯的年度播放量榜。它先使用当前 Billboard 过滤、连续播放合并、动态阈值、周边界、`merge_level` 与 album project 规则生成周榜，再按单个 `billboard_week.year` 窗口重算年度榜单积分。

单曲、专辑、艺人年榜分别来自应用当前周榜入榜线后的 `weekly`、`weekly_album` 与 `weekly_artist`。例如设置为单曲 Top 25 时，年度在榜周数只能统计每周排名 1–25 的周，不得因为年榜要输出 50 行而把周榜入榜线扩大为 Top 50。

周榜入榜线与年榜输出规模是两个独立参数：

- `weekly_top_n` / `weekly_album_top_n` / `weekly_artist_top_n`：决定哪些实体周进入年度积分与在榜指标，来自当前 Billboard 设置。
- `year_end_top_n` / `year_end_album_top_n` / `year_end_artist_top_n`：只决定年度排序完成后返回多少行，默认单曲 50、专辑 30、艺人 30。

改变年榜输出规模不得改变共同实体的年度积分、年度排名或任何在榜指标。

主排序为 `year_end_score DESC`，同分时依次比较 #1 周数、peak、Top 10 周数和 `chart_plays`。行级播放字段必须区分：

- `annual_plays`：该实体在所选 `billboard_week.year` 内的全部有效播放，不受周榜 Top N 截断影响。
- `chart_plays`：该实体进入当前周榜入榜线的周内播放，仅用于榜单成绩解释与同分裁决。

年榜主表只展示 `chart_plays`，列名固定为“在榜播放”，避免与听歌排行中的全年播放量形成重复信息。`annual_plays` 仍保留在 API 与 AI 年报证据中，供需要解释全年有效播放的消费者使用；任何消费者若展示该字段，必须明确标为“年度播放”。

年榜使用 V3 积分口径：`year_end_score = round(Σ weekly_score)`。其中 `weekly_score` 继续使用周榜既有的“排名基础分 × 当周竞争强度 × 个体统治力”公式；年榜层不再重复叠加持续性、年度 peak 或冠军周奖励。`peak_position`、`weeks_on_chart`、`weeks_at_no1`、Top 5/Top 10 周数继续作为展示、荣誉与同分裁决字段，单曲真实空降 #1 只作为事实字段和荣誉叙事素材保留。

年榜必须返回年份覆盖元数据。`period_start` / `period_end` 表示实际有效播放日期范围，`first_billboard_week` / `last_billboard_week` 表示榜单周边界；两者不得混用。只有首个预期榜单周至最后一个预期榜单周全部存在且无内部缺口时，`is_complete_year=true`；当年尚未结束、导入从年中开始或中间缺周时，必须显示阶段/不完整提示，荣誉不得写成已确定的完整年度冠军。

歌曲、专辑和艺人详情页复用同一套年榜计分与覆盖口径。详情 `summary` 不读取年榜投影并返回稳定空值，`overview/full` 读取持久化摘要和按年份降序的年榜历史；请求不得同步构建完整 Billboard 或 Year-End。详情页展示时按年份从旧到新排列，只展示 `chart_plays` 并标为“年度上榜播放”，不把 `annual_plays` 混入榜单成绩。

详情页年榜成绩采用独立投影状态：`ready` 表示当前精确统计 fingerprint 已完成投影，`warming` 表示投影已排队或正在后台构建，`unavailable` 表示缺少精确 snapshot、投影失败或版本不兼容。应用启动必须同时检查四套公开精确 snapshot（L2/L3 × 动态阈值开/关）与四套当前版本投影；旧库已有 ready snapshot 但缺少账本/投影时，由一个幂等后台维护任务补齐，详情 GET 始终只读且不得触发计算。`ready` 且历史为空表示实体从未进入年榜，不得显示 `#0`。年榜最佳先按最低 `year_end_rank` 选择；最低排名多年并列时，以最早达到该排名的年度作为首次 peak，不以完整年度或最近年度覆盖。年榜最佳与入榜年度数只作为“榜单成绩”页内的同级 KPI，不进入详情 Hero；阶段年度必须在 KPI 和历史中显示覆盖标签，不得省略完整性边界。所有名次数值沿用 Billboard 衬线数字样式。

只读一致性检查：

```bash
.venv/bin/python scripts/billboard_year_end_consistency_probe.py \
  --merge-levels 2,3 \
  --json-output /tmp/billboard_year_end_consistency.json
```

---

## 12. 展示规则

### 详情页存在资格与成绩状态

歌曲、专辑、艺人详情页的可访问资格与 Billboard 入榜资格分离：当前统计设置下只要存在至少一条有效播放，或存在可解析的对应榜单事实，详情 API 就应返回可渲染结果。只有既无有效播放、也无可解析本地实体或榜单事实的请求返回 404。对决选择器可继续只列出具有可对照榜单指标的实体，不得反向限制详情页入口。

详情页的固定 Tab 不因任一榜单数据为空而隐藏。成绩状态按数据域独立判断：

- 歌曲 `chart_status` 只表示该歌曲是否进入单曲榜。
- 专辑 `chart_status` 只表示该 album project 是否进入专辑榜；`track_chart_status` 独立表示成员歌曲是否进入单曲榜。
- 艺人 `chart_status`、`track_chart_status`、`album_chart_status` 分别表示艺人榜、其歌曲单曲榜和其专辑专辑榜事实。
- 未入榜成绩使用 `not_charted`、`null` summary 和空 history/list 表达，并显示精确空态；不得用峰值 `#0`、`0 周`等数值伪装成绩。
- `effective_play_count` 用于解释未入榜实体仍可访问的个人播放事实，继续遵循当前有效播放、动态阈值、连续播放合并和实体 identity 规则。
- “榜单成绩”先展示周榜趋势与周榜历史，再展示独立年榜历史；Desktop 使用年度表格，Phone 使用年度卡片，两端均按年份从旧到新。Desktop 年份使用与年度积分一致的无衬线半粗字重与等宽数字；Phone 年份使用 Playfair Display 半粗花体。年榜排名和周榜峰值继续使用 Billboard 衬线数字。完整年度不显示冗余覆盖标签；起始覆盖不足显示“不完整”，当前年度显示“进行中”，状态轻量且不换行，不单设“覆盖范围”列。年榜历史不显示重复的右侧说明；年榜排名数字保持原样，仅在首次达到最佳排名的年度旁显示一次无边框纯文字 `PEAK`，其字体、10px 字号、字重、大小写和字距与周榜变动 `RE / NEW` 一致。`PEAK` 不得参与排名的水平定位：Desktop 使用固定排名锚点、锚点垂直中线和脱离文档流的文字，Phone 使用等宽且垂直居中的文字槽，保证所有年度名次纵向对齐；两端均在几何居中基础上向下做 3px 光学校正。Phone 卡片底部的周榜峰值、在榜周数、冠军周数和前五周数必须共用固定 24px、垂直居中的数值行，避免 Playfair 与无衬线字体行盒差异造成错位。Desktop 表格列头承担“年度 / 积分 / 周数”语义，单元格不重复小单位；Phone 卡片脱离表头，继续保留必要单位。“年榜入榜”KPI 只显示年度数量，不重复解释其含义。年榜年度样本稀疏且完整/阶段年度不可无提示连线，当前不提供年榜趋势图。

- 详情页年榜历史的年度数字必须链接到 `/billboard/year-end`，并携带该行 `year` 与实体类型对应的 `tab`：歌曲为 `tracks`、专辑为 `albums`、艺人为 `artists`。年榜页面必须从 URL 恢复目标榜单类型，用户在年榜内切换类型时同步更新 `tab`，保证刷新、返回和分享语义稳定。
- 详情页周榜历史的榜单周必须链接到 `/billboard`，并携带该行 `week` 与相同的实体类型 `tab` 映射；Desktop 与 Phone 不得分叉 URL 规则。歌曲榜单成绩 KPI 与专辑/艺人统一使用共享 `KpiCard` 外观和主值/副文案层级；首次达峰、首次入榜、总播放和走势排名作为副文案保留。Desktop 有年榜摘要时为 3×2、无年榜摘要时为单行四列，Phone 为两列。

专辑自身榜单成绩必须优先按 album project identity + canonical artist 匹配 `weekly_album`；成员曲的 `album_track_counts` / `track_per_album` 只服务“单曲成绩”，不得作为专辑是否入榜的前置条件。

### 详情页统计实现约束

歌曲、专辑和艺人详情页的播放次数与收听时长必须在实体范围内分别计算：

- 播放次数来自实体过滤后的逻辑播放事件行；收听时长来自同一实体逻辑事件推断出的 `[ts - ms_played, ts)` 时长切片。不得复用全库 `DataFrame.attrs` 或其他隐式携带的全局切片。
- 详情页摘要、小时/日期/星期/月/年分布，以及歌曲/专辑/艺人详情内的时长排行，都必须显式传入实体范围的时长帧；实体没有播放时不能因全局切片而出现非零时长。
- 艺人“最近 50 次”按稳定 `_logical_event_id` 去重后计数；艺人 fan-out 行数不能直接当作最近事件数。
- 歌曲版本组与专辑发行组的版本播放量和时长必须复用 Billboard 逻辑播放加权帧的 `play_count` / `total_ms`，不能回退到原始 `plays` 表的静态 `ms_played` 阈值计数。
- 歌曲详情的统计摘要、最近播放、播放日历和排名必须与全局曲目榜使用同一 L2/L3 聚合键。L2 只解析活动 `recording` 组，L3 才跟随其活动 `composition` 父组；分组内所有成员必须先共同进入逻辑事件重建，不得将成员各自预聚合的结果直接相加。
- 请求歌曲组内任一 `track_id` 时，详情主体返回该层级的代表 `track_id`，统计和日历总数与该代表在全局榜中的逻辑播放数一致；分页播放行保留每条事件的实际来源版本。
- `last_4_weeks` 与 `last_6_months` 在播放分析/详情统计中以当前有效播放帧的最新数据日为结束日，避免数据源停止更新后相对窗口全部落在空白日期。

### R37. 歌曲详情页

歌曲详情页在 L2/L3 下应展示：

- canonical song 名称。
- 单曲版封面优先。
- 归属的原版录音室专辑主版本。
- 合并了哪些版本。
- 各版本播放量、时长、占比。
- 各版本 source album。
- L3 下标注不同录音类型，例如 Acoustic、Live、Taylor's Version。

### R38. 专辑详情页

专辑详情页展示 album project：

- canonical album project 名称。
- primary album 封面。
- L2/L3 顶部发行日期使用 `album_projects.release_date`；具体 Spotify 版本的发行日期只在版本列表中展示，不能用日期更晚的 Deluxe、Anniversary、Bonus、精选集或原声带覆盖项目发行日。
- album project track set。
- 标准版/豪华版/重录版等发行版本。
- 独有曲目。
- 专辑播放量来源拆分。
- 发行前单曲播放是否计入全时专辑播放量。
- Billboard 入榜起始日期。

### R39. 榜单页

榜单页必须显示当前合并级别：

- L1：不合并。
- L2：同录音/同发行项目合并。
- L3：同作品/同专辑项目合并。

切换合并级别后：

- 曲目榜刷新。
- 专辑榜刷新。
- Billboard 刷新。
- 详情页版本列表刷新。
- 有效播放事件总数不变。

#### 总榜跨层级走势指标

- 专辑 `track_power_sum` 是当前统计上下文中、由该 album project membership 归属且已进入单曲榜的 canonical tracks 的 Power Score 去重求和；同名专辑必须同时以 canonical artist 消歧。
- 艺人 `track_power_sum` 按 credited canonical artist fan-out 汇总已入榜歌曲，同一稳定歌曲/艺人身份只贡献一次；`album_power_sum` 汇总该 canonical artist 的已入榜 album projects。
- `track_power_rank` / `album_power_rank` 只在当前完整同类总榜实体集合中对正值使用 competition rank（并列共享最小名次）；零贡献显示 0，派生排名为 `null`。
- 表内搜索、分页和列显示偏好只是客户端展示控制，不得改变 Power Score、上述聚合值或任何原始/派生排名。

#### R39.1 Records 记录板块稳定排序

`/api/billboard/records` 与兼容的 `/api/billboard/data` 记录列表必须在同一统计上下文中使用相同的排序契约。每个记录板块先对完整候选集排序，再应用 Top N；不能先截断再对同值行排序，也不能使用 DataFrame 的输入顺序或当前 index 作为裁决依据。缺失的次级指标按“缺失值置后”处理，不得把缺失事实擅自解释成真实的 0。

所有业务排序键相同的行，都必须继续使用实体稳定键作为最终裁决：歌曲优先 canonical `track_id`，专辑使用 album project/release 与 canonical artist 的稳定组合，艺人使用 canonical artist ID/name；文本键按规范化文本、原文顺序比较。前端为排序切换做本地重排时，必须保留同一组稳定键。

当前 6 个 Records 子页面（对应 8 个后端记录计算模块）的二级及后续排序如下（`DESC` 为高值在前，`ASC` 为低值或较早日期在前）：

| Records 家族 | 业务排序（主 → 次 → 后续） |
|---|---|
| 冠军圣殿 | 同时上榜：曲目数 DESC → 榜单周 DESC；冠军名人堂（单曲）：冠军单曲数 DESC → 单曲冠军周数 DESC；冠军名人堂（专辑）：冠军专辑数 DESC → 专辑冠军周数 DESC；回归冠军：间隔周数 DESC → 回冠日期 DESC；空降冠军：空降周 ASC；冠军传承：接力周 DESC；阻挡王：阻挡数 DESC → 走势评分 DESC。 |
| 持久传奇 | 最长在榜：在榜周数 DESC → Peak ASC → 冠军周数 DESC → 首次上榜 ASC；无 Top 5：在榜周数 DESC → Peak ASC → 首次上榜 ASC；最长连续在榜：连续周数 DESC → 起始周 ASC → 结束周 DESC；艺人生涯跨度：跨度天数 DESC → 上榜歌曲数 DESC → 最近上榜 DESC → 首次上榜 ASC；夺冠后最快出榜：巅峰后周数 ASC → 末次上榜 DESC → 首次夺冠周 DESC；最多亚军但未夺冠：亚军周数 DESC → Peak ASC；最多回榜：回榜次数 DESC → 在榜周数 DESC；同一排名最长停留：连续周数 DESC → 停留排名 ASC → 起始周 ASC → 结束周 DESC。 |
| 爆发时刻 | 最大上升：变化 DESC → 本周排名 ASC → 日期 DESC；最大下跌：变化 ASC → 本周排名 DESC → 日期 DESC；同专辑/Top 10 同时上榜：曲目数 DESC → 榜单周 DESC；最强周：大盘播放 DESC → 榜单周 DESC；最长/最快登顶：登顶周数分别 DESC/ASC，再按首次上榜、首次夺冠周 ASC。 |
| 名人堂 | 歌曲/专辑/艺人走势总榜：走势评分 DESC；年度冠军：年份 DESC；年代之王：年代 ASC → 走势评分 DESC → 在榜周数 DESC → Peak ASC。 |
| 奇趣纪录 | 双空冠/三榜制霸：榜单周 DESC；一击即中/多曲艺人：冠军周数、在榜周数等业务指标 DESC，再按稳定艺人键；同名分组：组内数量 DESC → 规范化名称 ASC → 艺人/曲目稳定键；最早/最近上榜和最长/最短曲名：日期或长度为主，名称与稳定实体键为后续裁决。前端可切换日期或市场播放量，但切换后仍沿用实体稳定键。 |
| 每周大盘 | 周大盘：总播放 DESC → 曲目数 DESC → 榜单周 DESC；最激烈/最悬殊竞争：播放差额分别 ASC/DESC → 周总播放 DESC → 榜单周 DESC；新歌占比：新歌占比 DESC → 大盘播放 DESC → 榜单周 DESC。 |

冠军名人堂的单曲与专辑是两个独立候选集：单曲榜只保留冠军单曲数大于 0 的艺人，专辑榜只保留冠军专辑数大于 0 的艺人。因此，某艺人没有冠军专辑时不会以“0 张冠军专辑”占据专辑名人堂名次；它仍可在单曲榜中出现。排序规则只影响同值行的先后，不改变冠军事实、实体集合或周榜的 `play_count DESC → total_ms DESC → 稳定实体键` 规则。

### 年度总结 V2 消费契约

Desktop/Compact 与 Phone 的 `/yearly-review` 共用确定性 `YearlyReviewV2` 数据契约，但分别使用完整杂志年鉴与“口袋音乐年鉴”presentation；页面只提供这一套自有年度总结，不再提供“官方 Wrapped”页签。Phone/Desktop 必须互斥挂载。`/api/wrapped-hub`、官方导入表和读取服务仅作只读兼容冻结，不进入年度总结消费链路。

V2 统一继承当前 `music_only`、连续播放合并、动态阈值、`merge_level`、精选集、三类 Billboard Top N 与周边界。前端主报告 query key、后端 cache key 和兼容 records 响应必须使用同一过滤指纹，并包含版本化内容策略、display taxonomy 与艺人元数据 revision。

V2 的 `schema_version` 与 `content_version` 分开治理：前者只描述对外契约形状，后者覆盖统计、编排、公开文案与方法语义。任何语义变化都必须提升 content version，使进程 LRU 和 sidecar 精确键同时分流；sidecar 的压缩格式版本不能替代内容版本。

展示语义：

- “播放排行”同时保留播放次数与播放时长，两者不得混名。
- “个人 Billboard 年榜”使用本文件 Billboard Year-End 规则，只能描述本地个人榜；不得写成 Spotify 或外部官方 Billboard。
- 月度正文只有一条年度赛季/转折时间线；十二个月完整事实只在可展开账本中出现，不再复制第二套月度叙事。
- 关系、回归、发现、纪录和品味迁移只有在对应 coverage/支持阈值成立时才生成；不足时降级为空态或限制说明，不得由 LLM 补写。
- 主曲风只消费 `style`，地区流行只消费 `scene`，语言独立统计；`context` / `role` 不进入主图，unknown 必须保留为“尚未归类”并显示覆盖率。
- YTD、完整年、部分年和空年份由实际播放范围与榜单周覆盖决定；YTD/partial 不得使用“完整年度冠军”等已结算措辞。
- 年度里程碑必须先在完整个人历史的 canonical track 播放序列上计算累计阈值，再筛选阈值跨越日期是否位于报告年；报告年内的第 1,000 次播放不得写成个人历史第 1,000 次。
- 年度 discovery 必须先从完整历史得到 canonical track、album project、canonical artist 的真实首次播放日期，再筛选首次日期位于报告年的实体；只在年度切片内第一次出现的旧实体不算“第一次听到”。
- 每日播放次数与每日收听时长分别排名并使用 dense rank。只有各自的第一名可写“最多的一天/最长的一天”；并列第一必须明确标注并列，第二名及以后只能陈述名次或普通事实。
- 同比必须使用当前观察范围映射出的上一年 aligned window；闰日取合法月末。若上一年没有覆盖完整 aligned window，则回退到两年映射后的最大共同日历区间，且共同区间至少 90 天才可比较；否则不生成比较。比较模式明确区分 `full_year`、`same_period`、`common_period` 与 `unavailable`，消费端在非完整年度窗口显示“比去年同期”。工作日/周末日均以观察区间自然日数量为分母，不以活跃日或固定 5/2 为分母。
- 当报告截止在未完整月份时，该月的环比与同比只能分别与上月同期、上年同期的等长窗口比较，metric 必须保存两侧起止日期；只有完整自然月才能使用完整自然月比较。
- Passport 曲目/专辑/艺人数分别与播放榜的规范曲目、album project、有效署名艺人口径一致；同比也必须使用同粒度。
- 收听生活的歌曲总数、新歌数、探索率与复听率统一使用 canonical track identity。头号艺人的“播放占比”以年度逻辑播放总数为分母，以包含该有效署名艺人的逻辑播放数为分子；不得使用 fan-out 后艺人表总行数作分母。
- 完整年品味比较 H1→H2；YTD 只比较最近两个完整季度，少于两个完整季度时仅显示分布。差值和驱动实体必须使用同一日期切片。
- 公开纪录必须命中显式 renderer 并具备实体、数值或精确周期证据；未知/internal key、blocked map 和开篇/年榜首重复事实不得公开。阶段无法由连续月度多数冠军证明时必须返回空 stages，结语不得原样复制开篇头条。
- 主报告只携带 Top 50/30/30 和 6–8 条精选纪录。年报不提供“更多年度纪录”下钻，完整播放纪录/Billboard 纪录回到各自独立页面；兼容 `/api/yearly-review/{year}/records` 只返回与正文相同的精选集合，artifact 不得再序列化数千条候选。
- 消费界面不得渲染过滤指纹、策略版本、证据等级、coverage、limitations 或“统计口径 / 可比基线”等审计词；这些信息只服务于 API 契约、诊断与自动验收。
- 顶部六项指标统一称为“年度播放 / 年度时长 / 年度活跃天数 / 年度播放曲目 / 年度播放专辑 / 年度播放艺人”。有上一年数据时只显示红/绿方向箭头与百分比，不再重复显示“高/低”或绝对差值；完整比较语义保留在 accessible label 中。
- 年份按钮按升序排列且只显示年份；完整年度封面不显示“完整年度”和起止日期，YTD 报告仍在封面保留“进行中 · 截至日期”。封面不显示三条头条或海报按钮。
- 大标题下不附加解释性 subtitle。附录用户入口只称“完整榜单”，并且只保留播放榜与个人 Billboard；十二月明细只能从唯一年度时间线展开。
- 用户界面提到的歌曲、专辑、艺人应尽可能提供封面和既有详情深链；统一占位负责缺图降级。Phone/Compact/Desktop 默认最新可用年度，当前年明确标注进行中。年度名称和动态文案遵循全局简繁体偏好；回归等事件必须标注实体类型，避免把专辑事件误读为歌曲事实。
- 新关系故事按实体类型分别使用“今年发现的新歌 / 今年新听的专辑 / 今年认识的新艺人”，不得用“新名字”指代歌曲或专辑。同一专辑或艺人多首进入个人榜单的纪录必须显示准确曲目数；分歧故事在宽屏使用两列，空间收窄时回到单列。
- 所有正文章节统一使用紧凑纵向节奏；当前 Desktop/Compact section padding 为 `clamp(48px, 5.5vw, 80px)`，不得恢复为造成双倍大空白的超宽间距。

当前缓存热响应预算为 250ms，未压缩主 JSON 预算为 512 KiB，真实重算预算为 30 秒。关系历史中的首次播放与回归前末次播放日期必须按实体类型一次性聚合，不得在逐实体循环中反复扫描和转换完整历史；年度播放纪录应复用编排层已经建立的年度事件与实体帧。最终 artifact 可以压缩持久化，但必须使用独立 sidecar SQLite，完整 cache key 继续包含稳定播放事实 revision、过滤指纹、content version、策略和元数据 revision；不得使用 SQLite main/WAL 物理 mtime 让无关写入造成缓存抖动，不得用旧 key 或近似 key 返回 stale 报告。持久缓存损坏时必须自动视为 miss 并重算。年度生成使用 `yearly_review_generation_v1`：相同精确 key 只允许一个任务，不同年份的缓存命中不得被冷构建阻塞；单工作线程优先生成当前年份，其余真实可用年份从近到远排队，revision 漂移时不得写入旧 key，失败只公开稳定错误码且可重试，终态任务表必须有界。设置变更、流式导入与应用启动继续预建最新默认年份；Desktop/Compact/Phone 进入年度总结后按当前完整筛选上下文批量预建全部可用年份。性能优化不得改变统计口径或让浏览器静默吞掉本地 API 超时。历史 content v2.8 的 2023–2026 同进程真实重算为 10.65–16.54 秒、热响应为 26.56–29.85ms，跨进程持久命中为 10.20–21.07ms。当前 `yearly_review_v2_16` 使用 `highlight_policy_v3`、`season_stage_v2` 与 probe v7；probe 除公开文案、封面/深链、YTD 措辞、精选证据、结语去重和阶段状态外，还必须验证跨章节歌曲 identity、艺人占比分母、未完整月份以及完整年缺失基线时的共同区间比较。

---

## 13. 数据关系要求

### R40. 必需概念关系

为了实现上述规则，需要维护以下概念关系：

| 关系 | 用途 |
|------|------|
| `track_groups` / `track_group_members` | L2/L3 歌曲版本组 |
| `release_groups` / `release_group_members` | L2/L3 发行版本组 |
| `album_project` | 统计意义上的专辑项目 |
| `album_project_tracks` | album project 去重后的 canonical song 集合 |
| `source_album_id` | 每次播放的来源发行容器 |
| `album_source_breakdown` | 专辑播放量来源解释 |

### R41. 自动检测与人工确认

自动检测可以高置信应用：

- 同 ISRC / Spotify relink / 同录音证据明确的 L2 track group。
- 标准版/豪华版/expanded 的 L2 release group。

低置信候选必须人工确认：

- Acoustic / Live / Remix。
- Taylor's Version / 重录。
- 精选集独有歌曲归属。
- 同名不同歌。
- 翻唱、采样、mashup。

### R42. 历史 backfill 标注

历史播放若缺少真实 source album，只能用当前 track primary album 推断。

这类数据必须标注为 inferred，不能与导入时真实 source album 混为一谈。

---

## 14. 全局不变量

以下不变量必须长期成立：

1. `valid_play_events` 不随 `merge_level` 改变。
2. 曲目榜在 L2/L3 下只是聚合键变化，总播放事件不丢失；基础身份只负责确定事件归属。
3. 同一 canonical song 在同一 album project 中只能贡献一次。
4. album project 的来源拆分桶之和等于 album project plays。
5. 艺人播放次数之和可以大于有效播放事件数。
6. 非 catalog membership 的默认专辑榜不能因精选集或豪华版重复收录而重复计数。
7. 专辑全时播放量可以包含发行前先行单曲播放。
8. Billboard 专辑周榜不能在专辑发行前出现该专辑。
9. Billboard raw fallback 与预聚合路径在同一参数下输出一致。
10. 前端展示的封面、归属专辑、来源拆分只能解释统计结果，不能反向改变计数。

---

## 15. 典型示例

### vampire / GUTS

```text
vampire / vampire / 2023-06-30
vampire / GUTS / 2023-09-08
vampire / GUTS (spilled) / 2024-03-22
```

规则：

- L2 下三者作为同一份录音合并为同一 canonical song。
- 歌曲封面优先显示单曲版封面。
- 歌曲归属专辑显示 `GUTS`。
- `vampire` 在 2023-06-30 到 2023-09-07 的播放计入 `GUTS` 全时专辑播放量。
- `GUTS` 不能在 2023-09-08 发行前进入 Billboard 专辑周榜。

### GUTS / GUTS (spilled)

```text
GUTS / 2023-09-08
GUTS (spilled) / 2024-03-22
```

规则：

- L2 下合并为同一 album project。
- 共有曲目不重复计数。
- `GUTS (spilled)` 独有曲目额外计入 `GUTS` album project。
- 专辑详情页来源拆分展示原版专辑来源、豪华版来源、单曲来源等。

### Karma / Karma feat. Ice Spice

规则：

- L2 下不合并。
- L3 下合并，因为合作版仍包含原版主歌手 Taylor Swift。
- Ice Spice 只获得合作版实际播放的艺人 credit。

### 1989 / 1989 (Taylor's Version)

规则：

- L2 下不合并。
- L3 下合并为同一 album project。
- `Style` 与 `Style (Taylor's Version)` 合并为同一 canonical song。
- `Say Don't Go (Taylor's Version)` 作为重录专辑独有歌曲，也计入 `1989` album project。

### 精选集

规则：

- 如果全是已有歌曲，非 L1 下默认不显示为独立专辑榜实体。
- 播放回流到各歌曲 primary album project。
- 如果有独有新歌，则独有新歌形成 compilation-exclusive project。

---

## 16. 与 2026-06-12 规则的主要变化

| 旧规则 | 最新规则 |
|--------|----------|
| 默认专辑统计偏 source album / release group 口径 | 默认专辑播放量改为 album project 曲目总播放量 |
| catalog membership 是可选多专辑视图 | 默认 album project 需要基于 canonical song membership，但仍禁止重复计数 |
| 精选集默认可选显示 | 精选集拆成“纯既有歌曲默认隐藏”和“独有新歌形成项目”两类 |
| 专辑版本合并按 album_id/release_group 聚合播放 | 专辑项目播放量按去重 canonical song 集合求和 |
| 先行单曲 source album 归单曲 | 先行单曲播放可计入后续录音室专辑全时播放量 |
| 未明确发行前 Billboard 入榜边界 | 专辑发行前不能入 Billboard 专辑周榜，发行后不回填历史周 |
| 合作版 L3 合并条件较宽泛 | 明确为“参与艺人包含原版主歌手” |
| 歌曲封面/归属专辑未拆开 | 封面优先单曲版，归属专辑优先原版录音室专辑主版本 |

---

## 17. Implementation Status

截至 2026-08-30，Billboard Records 的 6 个家族共 51 个列表已使用完整候选集排序、业务二级/后续指标和稳定实体键；冠军单曲/专辑名人堂分别按对应冠周排序，专辑名人堂只接受冠军专辑数大于 0 的艺人。实现与真实 API/浏览器验收证据见 [`docs/reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。

截至 2026-08-17，album statistics 已在 analysis charts、leaderboards、Billboard album charts 和 album detail pages 使用 album project 语义；歌曲、专辑、艺人详情统计已统一采用实体范围时长帧和逻辑播放加权版本拆分。

已落地的不变式：

- Valid play events 独立于 `merge_level`。
- L2/L3 专辑统计使用 album project track membership，不再按 source album 行直接求和。
- 先行单曲播放计入全时 album project totals。
- Billboard 专辑周榜按 `album_project.release_date` 排除发行前播放。
- Source breakdown bucket totals 与 album project plays 对齐。
- 纯既有歌曲精选集不会在非 L1 下成为默认独立 album project。
- 精选集独有曲目可以形成 compilation-exclusive project。
- track-source weekly pre-aggregation 与 raw fallback 在新 album project 口径下一致。
- 专辑详情页返回 `album_project` payload，并展示来源拆分与项目曲目集合。
- 详情页摘要、分布和时长排行不会从全库时长切片继承时长；实体播放次数与收听时长保持双轨归属。
- 艺人最近 50 次按逻辑播放事件去重，版本组和发行组展示复用 Billboard `play_count` / `total_ms` 加权帧。
- 相对窗口 `last_4_weeks` / `last_6_months` 以最新有效数据日锚定；修复证据见 `docs/reports/2026-08-17-music-detail-statistics-fix-delivery.md`。

---

## 18. Import-Time Derived Data Maintenance

导入新的 Extended Streaming History 后，系统必须动态维护后端数据库，而不是假设所有歌曲、专辑和艺人都已经在旧库中出现过。

导入阶段分为两步：

1. `import_data()` 只负责确定性的本地事实：播放事件、艺人/专辑/曲目维度、featured artist、原始 Spotify track URI，以及播放当时的 `spotify_track_id_at_play`。
2. 导入 job 在标记 `done` 前运行后置维护：刷新 Spotify track/album 元数据、建立本地 album 到 Spotify album 的证据链接、重建 album projects、重建周聚合表、清理缓存，并返回导入健康报告。

维护不变式：

- 新播放记录中的 Spotify track id 要优先来自原始播放行，而不是只依赖 `tracks` 维表中的当前值。
- 本地 `albums` 不直接承载唯一 Spotify album 归属；`album_spotify_links` 记录证据、置信度、播放数、曲目数与首次/末次出现时间。
- album project bootstrap 必须优先使用 `album_spotify_links` 指向的 Spotify album metadata；同名 single 与完整专辑冲突时，完整专辑候选优先。
- 如果 Spotify API 凭据缺失或上游失败，导入仍应完成基础播放数据写入，并返回 `maintenance_status=partial`；不得让新歌播放记录整体不可用。
- `build_aggregations()` 必须在 metadata refresh 和 album project rebuild 之后运行，避免榜单基于旧封面、旧 duration 或旧 album project membership。
- 既有数据库可用 `scripts/refresh_import_derived_data.py` 手动运行同一条维护管线。
