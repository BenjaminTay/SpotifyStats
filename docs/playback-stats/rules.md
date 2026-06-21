# 播放统计与版本合并规则：最新版

> 创建日期：2026-06-18
> 状态：规则源文件，作为后续实现与验收依据
> 来源：整合 `docs/playback-stats/2026-06-12-playback-stats-rules.md`、`docs/playback-stats/implementation-plan.md`，以及 2026-06-18 对歌曲/专辑多版本语义的最新确认。

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
| L1 | 不合并，物理 Spotify entity 口径 |
| L2 | 标准合并，同录音/同发行项目口径 |
| L3 | 宽松合并，同作品/同专辑项目口径 |

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

连续播放合并只处理相邻的同一 `track_id`：

| 情况 | 是否合并 |
|------|:--:|
| 同一 `track_id` 连续出现 | 是 |
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

### R4. 连续播放边界

连续播放合并必须受 session 边界约束：

- 超过 `max_merge_gap_minutes` 的相邻同曲记录不合并。
- Billboard 周榜计算不跨 `billboard_week` 合并。
- 普通周期统计可按自然日、统计 period 或显式 boundary 分组。

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
| L1 | `track_id` | 每个 Spotify 曲目实体独立 |
| L2 | `recording_group_id`，未入组则回退 `track_id` | 同录音聚合 |
| L3 | `composition_group_id`，未入组则回退 L2/L1 key | 同作品聚合 |

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

合并后的歌曲展示遵循：

- 名称优先使用原始作品名，去掉常见版本后缀。
- 封面优先使用单曲版封面。
- 归属专辑优先显示该歌曲被收入的原版录音室专辑主版本。
- 如果歌曲从未被收入录音室专辑，则归属到首次发行的单曲/EP 项目。
- Deluxe-only / vault track 归属到对应 album project。

示例：

- `vampire` 显示单曲版封面，但归属专辑显示 `GUTS`。
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

### R17. L1/L2/L3 专辑聚合键

| 级别 | 专辑聚合键 | 行为 |
|------|------------|------|
| L1 | `album_id` | 每个 album container 独立 |
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

---

## 11. Billboard 周榜规则

### R32. 周榜基础管线

Billboard 周榜与个人统计使用同一基础规则：

1. 加载原始播放行。
2. music-only 过滤。
3. 同 `track_id` 连续播放合并。
4. 动态阈值过滤。
5. 周边界归属。
6. 按 `merge_level` 应用曲目/专辑项目聚合。
7. 排名：`play_count DESC, total_ms DESC`。

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

L1/L2/L3 的差异在排名层通过 canonical key resolver 应用。

---

## 12. 展示规则

### R36. 歌曲详情页

歌曲详情页在非 L1 下应展示：

- canonical song 名称。
- 单曲版封面优先。
- 归属的原版录音室专辑主版本。
- 合并了哪些版本。
- 各版本播放量、时长、占比。
- 各版本 source album。
- L3 下标注不同录音类型，例如 Acoustic、Live、Taylor's Version。

### R37. 专辑详情页

专辑详情页展示 album project：

- canonical album project 名称。
- primary album 封面。
- album project track set。
- 标准版/豪华版/重录版等发行版本。
- 独有曲目。
- 专辑播放量来源拆分。
- 发行前单曲播放是否计入全时专辑播放量。
- Billboard 入榜起始日期。

### R38. 榜单页

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

---

## 13. 数据关系要求

### R39. 必需概念关系

为了实现上述规则，需要维护以下概念关系：

| 关系 | 用途 |
|------|------|
| `track_groups` / `track_group_members` | L2/L3 歌曲版本组 |
| `release_groups` / `release_group_members` | L2/L3 发行版本组 |
| `album_project` | 统计意义上的专辑项目 |
| `album_project_tracks` | album project 去重后的 canonical song 集合 |
| `source_album_id` | 每次播放的来源发行容器 |
| `album_source_breakdown` | 专辑播放量来源解释 |

### R40. 自动检测与人工确认

自动检测可以高置信应用：

- 同 ISRC / Spotify relink / 同录音证据明确的 L2 track group。
- 标准版/豪华版/expanded 的 L2 release group。

低置信候选必须人工确认：

- Acoustic / Live / Remix。
- Taylor's Version / 重录。
- 精选集独有歌曲归属。
- 同名不同歌。
- 翻唱、采样、mashup。

### R41. 历史 backfill 标注

历史播放若缺少真实 source album，只能用当前 track primary album 推断。

这类数据必须标注为 inferred，不能与导入时真实 source album 混为一谈。

---

## 14. 全局不变量

以下不变量必须长期成立：

1. `valid_play_events` 不随 `merge_level` 改变。
2. 曲目榜在 L1/L2/L3 下只是聚合键变化，总播放事件不丢失。
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

截至 2026-06-18，album statistics 已在 analysis charts、leaderboards、Billboard album charts 和 album detail pages 使用 album project 语义。

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
