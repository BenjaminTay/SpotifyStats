# 播放数据统计规则：现状分析、目标定义与优化规划

> 创建日期：2026-06-12
> 状态：实施中（Phase A-F 完成，P0-P1 修复完成 2026-06-13）

---

## 目录

1. [现状分析](#1-现状分析)
2. [目标统计规则（技术无关）](#2-目标统计规则技术无关)
   - 2.1 [播放有效性](#21-播放有效性)
   - 2.2 [连续播放合并](#22-连续播放合并)
   - 2.3 [曲目版本合并](#23-曲目版本合并)
   - 2.4 [专辑版本合并](#24-专辑版本合并)
   - 2.5 [专辑类型处理](#25-专辑类型处理)
   - 2.6 [多艺人归属](#26-多艺人归属)
   - 2.7 [多专辑归属](#27-多专辑归属)
   - 2.8 [Billboard 周榜](#28-billboard-周榜)
   - 2.9 [统计一致性约束](#29-统计一致性约束)
   - 2.10 [合并严格度分级](#210-合并严格度分级)
   - 2.11 [实体详情页版本展示](#211-实体详情页版本展示)
3. [现状与目标差距矩阵](#3-现状与目标差距矩阵)
4. [分步实施规划](#4-分步实施规划)
5. [审查补充：需要修正的判断](#5-审查补充需要修正的判断)

---

## 1. 现状分析

### 1.1 数据过滤：什么算"一次有效播放"

**核心函数**：`backend/core/db.py:479` `base_filters()`

| 规则 | 默认值 | 说明 |
|------|--------|------|
| `min_ms >= 30000` | 30 秒 | 全局硬阈值，不区分曲目时长 |
| `music_only = True` | 排除播客 | `track_id IS NOT NULL`，播客无 track_id |

**问题**：30 秒一刀切。2 分钟的朋克歌听 30 秒 ≈ 25%，8 分钟的古典乐听 30 秒 ≈ 6%。后者几乎肯定是跳过了。

---

### 1.2 连续播放合并

**核心函数**：`backend/core/db.py:506` `merge_consecutive_plays()`

**算法**：
1. 按 `ts` 排序后，相邻相同 `track_id` 归为一组（一次收听会话）
2. 逻辑播放次数 = `total_ms // duration_ms + (1 if remainder >= min_ms else 0)`
3. 展开为 `count` 行，完整播放 `ms_played = duration`，余数 `ms_played = remainder`
4. `duration_ms` 为 NULL/0 时原样穿透，不合并

**关键执行顺序**：SQL（min_ms=0 全量拉取）→ merge → `ms_played >= 30000` 过滤

**注意**：上述顺序对 `load_plays()` 普通统计路径成立；Billboard raw fallback 路径当前通过 `base_filters(min_ms=min_ms)` 读取，再调用 `merge_consecutive_plays()`，存在"短碎片先被 SQL 过滤掉"的口径不一致风险。预聚合路径是先合并再过滤。

**问题**：
- 只合并**同一 track_id** 的连续行，不同版本（原版 → Remix 版）即使连续播放也不合并
- 要求**严格连续**，A→B→C→A（回到 A）视为两次独立播放（这个行为本身合理）
- 没有最大时间间隔或周边界保护；两个相邻同曲记录即使间隔很长，也会被视为同一次合并组

---

### 1.3 多艺人归属

| 组件 | 现状 |
|------|------|
| 数据模型 | `track_artists` 多对多表 + `role`（primary/featured），正确 |
| 艺人统计路径 | `load_plays_for_artists()` 扇出，合并先于扇出，正确 |
| 非艺人统计路径 | `load_plays()` 只 JOIN `tracks.artist_id`（主艺人） |
| featured 艺人可见性 | 仅在艺人统计中可见，曲目/专辑统计中不可见 |

**有意设计**：艺人统计中每位合作艺人获得完整播放信用。但这导致"所有艺人播放次数之和 > 总播放次数"。

---

### 1.4 多专辑归属

| 组件 | 现状 |
|------|------|
| 数据模型 | `track_albums` 多对多表已存在 |
| 主统计路径 | `load_plays()` 只 JOIN `tracks.album_id`（主专辑），**不使用** `track_albums` |
| 使用位置 | 用于版本检测、Billboard album metadata、Billboard album track counts、封面/详情辅助查询；但主播放聚合仍不是基于每次播放的 source album |

**影响**：同一首歌先发单曲→后收录专辑→再被选入选集时，当前统计无法还原"这一次播放当时属于哪张专辑"。如果只用 `track_albums` 扇出，又会把同一次播放同时记给多张专辑，导致个人专辑榜膨胀。更合理的方向是：默认统计使用 `album_id_at_play` / source album；可选 catalog membership 视图再使用 `track_albums` 扇出。

---

### 1.5 专辑版本合并

| 组件 | 现状 |
|------|------|
| 数据模型 | `release_groups` + `release_group_members` 表，设计完善 |
| 自动检测 | `backend/core/version_merge.py`（62KB），三级管道检测 |
| Billboard 周榜 | ✅ 已应用 `_apply_album_release_groups()` |
| 个人分析统计 | ⚠️ 通用专辑排行榜未应用；专辑实体详情会解析同 release group 的 album aliases |

**检测逻辑**：
- 第一级：名称归一化（剥离 deluxe/expanded/bonus track 等后缀）+ 曲目重叠率验证
- 第一级半：前缀重叠检测（如 "TTPD" vs "TTPD: THE ANTHOLOGY"）
- 第二级：纯超集检测（Union-Find 连通分量）
- 排除关键词：Taylor's Version、Live、Remix、Radio Edit、Demo、Instrumental、Orchestral

---

### 1.6 专辑类型

| 组件 | 现状 |
|------|------|
| 数据来源 | `spotify_album_meta.album_type`（album/single/compilation） |
| Billboard 专辑榜 | ✅ 过滤 `album_type != 'single'` |
| 发行周期分析 | ✅ 区分 album/single |
| 个人分析统计 | ❌ LP/EP/精选/单曲**不做区分** |

---

### 1.7 曲目版本合并（最薄弱环节）

| 组件 | 现状 |
|------|------|
| 导入去重 | `_cache_track()` 按 `(artist_id, track_name)` 去重——名称相同则合并为一个 track_id |
| 归一化函数 | `normalize_track_name()` 剥离版本后缀——用于版本检测中的曲目名归一/重叠计算，不用于导入去重、排行榜聚合或播放合并 |
| 连续播放合并 | 只合并同 `track_id`——不同版本的同一首歌连续播放**不合并** |
| 版本分组 | **完全缺失**——无 track-level release_groups |

**影响**：
- "Song" 和 "Song - Remastered" → 两个 track_id，各自独立统计
- 用户先听原版→再听 Acoustic 版 → 不合并（不同 track_id）
- 歌曲榜上同一首歌的多个版本各排各的

---

### 1.8 现状影响矩阵

| 复杂维度 | 总播放次数 | 曲目榜 | 专辑榜 | 艺人榜 | Billboard 周榜 |
|----------|:--:|:--:|:--:|:--:|:--:|
| 30s 硬阈值 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| 多艺人扇出 | ✅ | — | — | ✅ | ✅ |
| 多专辑归属 | — | — | ⚠️ | — | ⚠️ |
| 专辑版本合并 | — | — | ⚠️ | — | ✅ |
| 专辑类型区分 | — | — | ❌ | — | ⚠️ |
| 曲目版本合并 | ❌ | ❌ | — | ❌ | ❌ |

> ✅ 正确处理　⚠️ 部分处理　❌ 未处理　— 不适用

---

## 2. 目标统计规则（技术无关）

以下规则定义了"正确"的统计行为。这些规则独立于任何技术实现，是修改的最终验收标准。

---

### 2.1 播放有效性

**R1 — 动态时长阈值**

一次播放记录被计为"有效"的条件是：

```
ms_played >= max(30000, duration_ms × 0.1)
```

| 场景 | 曲目时长 | 阈值 | 说明 |
|------|----------|------|------|
| 极短曲目（interlude） | 45s | 30s | 30s 保底，占曲目 67% |
| 典型流行歌 | 3min 30s | 30s | 10% = 21s < 30s，取保底 |
| 中等长度 | 6min | 36s | 10% = 36s > 30s，取比例 |
| 长曲目（prog/古典） | 10min | 60s | 10% = 60s，防止跳过片段被计为有效 |

**设计理由**：短曲目以 30s 为绝对保底；长曲目按 10% 比例提升阈值，确保收听占比合理。

**降级策略**：若 `duration_ms` 不可用（NULL/0），回退到 `min_ms >= 30000`。

---

**R2 — 播客排除**

`track_id IS NULL` 的记录（播客/有声书）不计入音乐统计。

---

### 2.2 连续播放合并

**R3 — 合并触发条件**

以下情况的连续播放行应视为同一次"收听会话"并合并：

| 情况 | 合并 | 理由 |
|------|:--:|------|
| 同一 track_id 连续出现 | ✅ | 碎片化播放片段合并为逻辑播放次数 |
| 不同 track_id 连续出现（无论是否同 recording/composition group） | ❌ | 不同的 track，即使同属一个版本组，也是独立的播放事件 |
| A→B→C→A（非连续回到 A） | ❌ | 两次独立的播放意图 |

> **跨 track_id 版本合并不在播放事件层处理**。同一 recording/composition group 内不同 track_id 的播放次数在排行榜聚合层求和（路径 A，见 R28 说明），而非在 `merge_consecutive_plays()` 中合并播放事件。路径 B（播放事件层跨 track 合并）为远期可选扩展，不进入 P0-P4 实施范围。

**R4 — 合并计算规则**

对合并组内的所有行：

```
total_ms = sum(ms_played)
full_plays = total_ms // duration_ms
remainder = total_ms % duration_ms

逻辑播放次数 = full_plays + (1 if remainder >= 有效阈值 else 0)
```

合并后展开为 `count` 行：
- 前 `full_plays` 行：`ms_played = duration_ms`
- 如有余数行：`ms_played = remainder`

**R5 — duration_ms 不可用时的降级**

若组的 `duration_ms` 为 NULL 或 0，该组不合并，原样输出。

---

### 2.3 曲目版本合并

**R6 — 曲目版本组定义**

`track_groups` 表（见 P4 数据模型）以 `scope` 字段区分两层分组：

- **`scope='recording'`（L2）**：同一录音 session 的不同发行包装。包含 Remastered、Clean/Explicit、区域限定版。不包含 Acoustic、Live、Remix、Instrumental、Radio Edit、Taylor's Version（这些来自不同录音场合）。
- **`scope='composition'`（L3）**：同一作品的所有录音版本。在 recording 组的基础上，额外通过 `parent_group_id` 关联多个 recording 组，并直接包含独立的 track 级成员（Acoustic、Live、Taylor's Version、Demo 等）。仅不同主艺人的 Remix 永远不归入任何组。

完整的 L2/L3 边界对照表见 R25，此处不重复，避免两份规则漂移。

**R7 — 版本合并对统计的影响**

- **曲目排行榜**：按当前 merge_level 选中的 group scope 聚合（L1: `track_id`；L2: `recording_group_id`；L3: `composition_group_id`），显示 canonical track_name，提供展开查看各版本详情的入口
- **播放次数计算**：同一聚合组内各 track_id 的播放次数在聚合层求和（不改变 valid play events）
- **时长统计**：同上求和
- **专辑归属**：各版本保留各自的专辑归属（原版归原专辑，Acoustic 版可能归另一张 EP）

**R8 — Canonical 曲目名**

合并后的 canonical 名取组内出现最早的 track_name（或 Spotify 元数据中的原始名称），去后缀（- Remastered、- Acoustic 等）。recording group 的 canonical 名通常是剥离后缀后的标准名；composition group 的 canonical 名通常是原始录音版名称。

---

### 2.4 专辑版本合并

**R9 — 专辑版本组定义**

`release_groups` 表（现有）应与 `track_groups` 采用相同的两层分组模型，扩展 `scope` 和 `parent_group_id` 字段：

- **`scope='release'`（L2）**：同一发行物的不同包装 — Deluxe、Expanded、Remastered、Anniversary、Clean/Explicit、区域版。不含 Live 专辑、Remix 专辑、Taylor's Version（这些是不同发行物/录音）。
- **`scope='composition'`（L3）**：同一作品的所有发行 — 在 release 组基础上通过 `parent_group_id` 关联多个 release 组，并直接包含 Live 专辑、Remix 专辑、Taylor's Version、Acoustic 版专辑。仅不同艺人的同名专辑永远不合并。

**判断原则**：核心曲目列表大量重叠（≥ 40%）的专辑应合并；核心曲目列表基本不重叠的应分开。L2 以"同一发行物"为边界，L3 以"同一作品"为边界。

> 完整的 L2/L3 边界对照表见 R26（唯一权威表），此处不重复。

**R10 — 版本合并对统计的影响**

- **专辑排行榜**：按当前 merge_level 选中的 group scope 聚合（L1: `album_id`；L2: `release_group_id` where `scope='release'`；L3: `release_group_id` where `scope='composition'`），显示 canonical album_name
- **播放次数**：聚合组内各 album_id 的播放次数在聚合层求和（不改变 valid play events）
- **时长统计**：同上求和
- **唯一曲目数**：聚合组内 track_id 去重后的数量
- **封面展示**：优先使用 primary_album_id（通常是标准版）的封面
- **曲目级别查看**：用户可展开 canonical album 查看各版本的曲目分布
- **composition release group 成员展开**：与 P4 中 track_groups 一致，实现时提供 resolver/view：`composition 组成员 = direct album members ∪ child release group members`，避免各处 SQL 临时拼凑

**R11 — Canonical 专辑名**

取 `release_groups.canonical_name`，通常是剥离版本后缀后的标准专辑名。release group 的 canonical 名是剥离后缀的标准名；composition group 的 canonical 名通常是原始标准版名称。

---

### 2.5 专辑类型处理

**R12 — 类型定义**

| 类型 | Spotify album_type | 特征 |
|------|-------------------|------|
| 全长专辑（LP） | `album` | 通常 ≥ 7 首或总时长 ≥ 25min |
| EP | `single`（部分）、`album`（部分） | 通常 3-6 首，总时长 < 25min |
| 精选集 | `compilation` | 各艺人精选/various artists |
| 单曲辑 | `single` | 1-2 首 |

**注**：Spotify 的 `album_type` 分类不完全准确（部分 EP 被标为 `album`，部分被标为 `single`）。以曲目数 + 总时长辅助判断。

**R13 — 专辑排行榜默认过滤**

| 榜单维度 | LP | EP | 精选集 | 单曲辑 |
|----------|:--:|:--:|:--:|:--:|
| 个人专辑总榜 | ✅ 包含 | ✅ 包含 | ✅ 包含 | ❌ 排除 |
| Billboard 周榜 | ✅ 包含 | ✅ 包含 | ✅ 包含 | ❌ 排除 |
| 前端默认视图 | ✅ 显示 | ✅ 显示 | ⚠️ 可切换 | ❌ 隐藏 |

**设计理由**：单曲辑只有 1-2 首歌，与专辑同台竞争不公平（单曲播放次数天然集中）。EP 虽然曲目少，但属于艺术上完整的作品，应保留。精选集可选显示。

**R14 — 前端交互**

专辑排行榜提供类型筛选开关：
- 默认：LP + EP
- 可选：包含精选集
- 始终排除：单曲辑

---

### 2.6 多艺人归属

**R15 — 艺人统计的扇出规则**

在艺人维度的统计中（艺人排行榜、个人艺人分析），一首有 N 位艺人的曲目的每次播放，为每位艺人各计 1 次。

**设计理由**：艺人统计回答的问题是"我听哪些艺人的时间最多"——如果你听了 Drake feat. Rihanna 的歌，你确实同时听了 Drake 和 Rihanna。

**R16 — 非艺人统计的艺人字段**

在曲目/专辑维度的统计中，`artist_name` 显示为逗号分隔的所有艺人名（primary + featured）。这是展示字段，不影响聚合。

**R17 — 总播放次数不变**

扇出仅用于艺人维度的聚合分组。总播放次数始终以 `load_plays()`（非扇出路径）为准。

| 统计口径 | 数据来源 | 说明 |
|----------|----------|------|
| 总播放次数 | `load_plays()` | 每行播放 = 1 次 |
| 艺人 A 的播放次数 | `load_plays_for_artists()` | 共享曲目完全计入 A |
| 所有艺人次数之和 | ≥ 总播放次数 | 预期膨胀，UI 标注 |

---

### 2.7 多专辑归属

**R18 — 专辑统计的默认归属规则**

每次播放应优先归属于该播放记录当时的 source album，即导入记录中的 `master_metadata_album_album_name` 所对应的 album。后续应在 `plays` 中持久化 `album_id_at_play` / `source_album_id`，避免只通过 `tracks.album_id` 推断。

**设计理由**：专辑统计默认回答的问题是"这一次播放来自哪张发行物"。如果用户播放的是单曲版，就应计入单曲版；如果播放的是专辑版，就应计入专辑。默认把一首歌同时记给原专辑、精选集和豪华版，会让个人专辑榜失真。

**R19 — Catalog membership 归属视图（可选）**

`track_albums` 表用于回答"这首歌属于哪些专辑/发行物"。可以提供一个可选视图：一首曲目属于 N 张专辑时，该曲目的播放为每张专辑各计 1 次，用于分析曲目覆盖、专辑曲目贡献和精选集覆盖度。

该视图必须明确标注为 catalog membership / 多专辑归属视图，不能替代默认专辑播放榜。

**R20 — 非专辑统计不受影响**

曲目/艺人维度的统计不因 catalog membership 视图重复计数；总播放次数始终以非扇出播放事件为准。

**R20b — UI 标注**

专辑列表默认展示 source album 口径；如提供 catalog membership 视图，需标注"同一曲目可能归属于多张专辑，因此专辑播放次数之和可能大于总播放次数"。

---

### 2.8 Billboard 周榜

**R21 — 所有上述规则在 Billboard 中生效**

Billboard 周榜的聚合管线应完整应用：
- 动态阈值（R1）
- 连续播放合并（R3-R4）
- 曲目版本聚合（R6-R7/R28）
- 专辑版本合并（R9-R10）
- 专辑类型过滤（R13）
- source album 归属（R18）
- 可选 catalog membership 视图（R19）

**R22 — 周榜排名规则**

按 `(billboard_week, entity_id)` 分组后：
- 排序：`play_count DESC, total_ms DESC`
- 先按播放次数排，次数相同按时长排

**R23 — 周边界规则**

- 周起始日可配置（默认周五，对齐全球发行日）
- 周起始时刻可配置（默认 0:00）
- 临界时刻的播放归属按配置的边界计算

---

### 2.9 统计一致性约束

**R24 — 术语定义**

以下术语贯穿所有统计口径，需精确定义：

| 术语 | 英文 | 定义 |
|------|------|------|
| **原始播放行** | raw play rows | `plays` 表中导入的原始行数，未经任何过滤或合并 |
| **有效播放事件** | valid play events | 经 counting policy（SQL 粗过滤 + `merge_consecutive_plays()` 合并 + DataFrame 层 `effective_threshold()` 二次过滤，见 P2）处理后的行数。**注意**：若合并时 `total_ms` 显著超过 `duration_ms`，一条原始行可能展开为多条逻辑播放事件，因此 valid play events 可能大于、等于或小于 raw play rows |
| **实体归属播放数** | entity credited plays | 对有效播放事件按实体维度（曲目/专辑/艺人）聚合、应用版本合并（track_group/release_group）和扇出（多艺人/多专辑）后的播放计数。由于扇出，艺人维度的 entity credited plays 之和 ≥ valid play events |

**R24b — 全局不变量**

以下不变量必须在所有统计场景中成立：

1. 有效播放事件数与原始播放行数不可直接等同：通常因过滤而显著减少（跳歌等），也可能因超长记录合并展开而局部增加
2. 所有艺人播放次数之和 ≥ 有效播放事件数（多艺人扇出）
3. source album 口径下，所有专辑播放次数之和应接近有效播放事件数（排除缺失专辑、被类型过滤的发行物）
4. catalog membership 口径下，所有专辑播放次数之和 ≥ 有效播放事件数（多专辑归属扇出）
5. 所有曲目播放次数之和（track_group 聚合后）应等于有效播放事件数。差异仅来自：显式 track 维度过滤、统计范围不一致，或异常数据导致有效播放事件缺少可聚合 track_id。未归入任何 group 的 track 按自身 `track_id` 作为聚合键参与统计，不产生差异
6. 同一专辑在 Billboard 周榜和个人榜中的排名不应因版本合并策略不同而产生显著差异（R10 和 R21 确保一致）

---

### 2.10 合并严格度分级

并非所有用户都希望相同的合并策略。提供三级可切换的合并严格度，让用户根据自己的理解选择统计口径。

**R25 — 曲目合并严格度**

| 级别 | 名称 | 合并行为 | 默认 |
|------|------|----------|:--:|
| L1 | **不合并** | 每个 track_id 独立统计；不同版本各自排名；连续播放只合并同 track_id | |
| L2 | **同录音合并**（推荐） | 同一录音的不同发行版本合并：原始版 + Remastered + Clean/Explicit + 区域版；连续播放仍只合并同 track_id，排行榜按 `recording_group_id` 聚合 | ✅ |
| L3 | **同作品合并** | 同一作品的所有录音版本全部合并：原始版 + Remastered + Live + Remix + Acoustic + Instrumental + Radio Edit + Taylor's Version + Demo；仅不同主艺人的 Remix 始终独立 | |

**L2 "同录音" 与 L3 "同作品" 的边界判断**：

| 版本类型 | L2（同录音） | L3（同作品） | 判断依据 |
|----------|:--:|:--:|------|
| Remastered 版 | ✅ 合并 | ✅ 合并 | 同一母带，不同后期 |
| Clean / Explicit | ✅ 合并 | ✅ 合并 | 同一录音，仅内容分级不同 |
| 区域限定版（Japan Ed.） | ✅ 合并 | ✅ 合并 | 同一录音，仅加曲/排序不同 |
| Acoustic 版 | ❌ 独立 | ✅ 合并 | L2：不同录音场合/编曲；L3：同一作品 |
| Live 版 | ❌ 独立 | ✅ 合并 | L2：不同录音场合；L3：同一作品 |
| Remix 版（同主艺人） | ❌ 独立 | ✅ 合并 | L2：再创作；L3：同一作品 |
| Remix 版（不同主艺人） | ❌ 独立 | ❌ 独立 | 不同艺人的 Remix 视为不同作品 |
| Radio Edit | ❌ 独立 | ✅ 合并 | 时长显著缩短，但仍是同一录音的剪辑 |
| Instrumental 版 | ❌ 独立 | ✅ 合并 | L2：不同编曲体验；L3：同一作品 |
| Demo 版 | ❌ 独立 | ✅ 合并 | L2：未完成品/小样；L3：同一作品 |
| Taylor's Version | ❌ 独立 | ✅ 合并 | L2：不同录音 session，独立；L3：同一作品的不同录音，合并 |

**判断原则**：
- L2 的界限是"是否来自同一次录音 session"——Remastered/Clean/区域版只是同一录音的不同包装，算同一录音；Acoustic/Live/Remix 是重新演奏或重新编曲，算不同录音
- L3 的界限是"是否是同一首作品的不同演绎"——只要原曲的旋律/歌词骨架不变，都算同一作品
- Taylor's Version 在 L2 独立（不同录音 session），在 L3 合并（同一作品的不同录音）
- Demo 在 L2 独立（未完成品/小样，不同录音场合），在 L3 合并（同一作品的不同阶段录音）
- 不同主艺人的 Remix 永远是例外：它本质上是"另一首歌用了你的旋律"，任何级别都不合并

**R26 — 专辑合并严格度**

| 级别 | 名称 | 合并行为 | 默认 |
|------|------|----------|:--:|
| L1 | **不合并** | 每个 album_id 独立统计；豪华版、扩展版各自排名 | |
| L2 | **同发行组合并**（推荐） | 同一 release_group 合并：标准版 + Deluxe + Expanded + Remastered + Anniversary + Clean/Explicit + 区域版；不合并 Live 专辑、Remix 专辑、Taylor's Version | ✅ |
| L3 | **同作品合并** | 同一作品的所有发行全部合并：标准版 + Deluxe + Live 专辑 + Remix 专辑 + Acoustic 版专辑 |

**L2 vs L3 边界判断**：

| 版本类型 | L2（同发行组） | L3（同作品） | 判断依据 |
|----------|:--:|:--:|------|
| Deluxe / Expanded | ✅ 合并 | ✅ 合并 | 同一发行，仅加曲 |
| Remastered 版 | ✅ 合并 | ✅ 合并 | 同一录音，不同后期 |
| Anniversary 版 | ✅ 合并 | ✅ 合并 | 同一发行，仅加曲+纪念包装 |
| Clean / Explicit | ✅ 合并 | ✅ 合并 | 同一发行，内容分级不同 |
| 区域限定版 | ✅ 合并 | ✅ 合并 | 同一发行，仅曲目排序/加曲不同 |
| Live 专辑 | ❌ 独立 | ✅ 合并 | L2：不同录音场合的完整专辑 |
| Remix 专辑 | ❌ 独立 | ✅ 合并 | L2：曲目经再创作 |
| Acoustic 版专辑 | ❌ 独立 | ✅ 合并 | L2：不同录音方式 |
| Taylor's Version | ❌ 独立 | ✅ 合并 | L2：不同录音 session；L3：同一作品的不同录音 |
| 不同艺人的同名专辑 | ❌ 独立 | ❌ 独立 | 完全不同的作品 |

**R27 — 严格度切换的前端交互**

1. **全局设置入口**：在设置页面或统计页面顶部提供合并严格度切换（下拉或分段控件）
2. **三级选项**：不合并 / 标准合并（推荐）/ 完全合并
3. **即时生效**：切换后所有排行榜（曲目榜、专辑榜、艺人榜、Billboard）和统计数字同步刷新
4. **当前级别提示**：在排行榜标题旁显示当前合并级别标签，避免用户混淆
5. **默认 L2**：新用户默认使用"标准合并"（同录音/同发行组合并）
6. **级别说明**：每个级别旁有 tooltip/问号图标，点击展示该级别会合并什么、不会合并什么

**R27b — 实现要求**

"即时生效"意味着 `merge_level` 必须进入所有受版本合并影响的排行榜/实体聚合参数空间；纯有效播放事件缓存和不受版本合并影响的聚合（如艺人总榜）可不纳入：

| 层级 | 影响 | 说明 |
|------|------|------|
| API Query 参数 | 所有排行榜端点新增 `merge_level` 参数（`1`/`2`/`3`，默认 `2`） | `PlayFilters` 或新增 `MergeConfig` 依赖注入 |
| TanStack Query keys | `queryKeys` 中纳入 `mergeLevel` | 切换级别自动触发 refetch，无需手动 invalidate |
| 后端 `@lru_cache` keys | 实体聚合缓存、排行榜缓存纳入 `merge_level` | 不同级别的聚合结果各自缓存；基础有效播放事件缓存（`_load_plays_cached()`）不纳入 `merge_level` — 路径 A 下 valid play events 不随 merge_level 变化 |
| `agg_weekly_*` 预聚合 | `agg_config.param_hash` **不纳入** `merge_level` | 预聚合表存储 base-grain（per track_id/album_id/artist_id × billboard_week），merge_level 在排名层应用。不同 merge_level 共享同一份预聚合数据，避免为 L1/L2/L3 各自重建 |
| 前端 URL / 路由状态 | `merge_level` 写入 URL search params 或持久化到 localStorage | 刷新页面保持级别选择 |

**R28 — 合并严格度对各项统计的影响范围**

| 影响的统计 | L1 | L2 | L3 |
|------------|:--:|:--:|:--:|
| 连续播放合并（仅同 track_id） | ✅ | ✅ | ✅ |
| 曲目排行榜聚合键 | `track_id` | `recording_group_id` | `composition_group_id` |
| 专辑排行榜聚合键 | `album_id` | `release_group_id`（scope=release） | `release_group_id`（scope=composition） |
| 艺人排行榜 | 不受影响（始终按艺人聚合） | 同左 | 同左 |
| Billboard 周榜 | 按原始 entity | 应用同级别合并 | 应用同级别合并 |
| 有效播放事件数 | 不受影响 | 不受影响 | 不受影响 |
| 实体详情页（版本明细） | 显示所有 track_id/album_id | 显示同 scope 组内各版本（recording/release） | 显示同 scope 组内各版本（composition） |

> **本规划选择路径 A**（仅聚合层合并）：`merge_consecutive_plays()` 始终只合并同 track_id。跨 track_id 的版本合并仅在排行榜聚合时生效（同 recording/composition group 的多个 track_id 的播放次数求和后统一排名）。valid play events 不受 merge_level 影响。
>
> 路径 B（播放事件层跨 track 合并）作为远期备选，不进入 P0-P4 实施范围。若未来启用路径 B，需将 merge_level 纳入 counting policy、所有缓存 key 和预聚合 hash。

---

### 2.11 实体详情页版本展示

在曲目详情页和专辑详情页中，当该实体属于某个合并组（track_group 或 release_group）时，需要展示合并关系。

**R29 — 曲目详情页版本展示**

当用户查看的曲目属于一个 track_group（非 L1 模式下），详情页应展示：

1. **Canonical 标识**：页面标题显示 canonical track_name，副标题标注"包含 X 个版本"
2. **版本列表**：以表格或卡片形式列出同组所有 track_id：
   - 版本名称（track_name）
   - 该版本的播放次数
   - 该版本的播放时长
   - 该版本所属专辑
   - 标记哪个是 primary/标准版本
3. **播放次数比例**：每个版本占总播放次数的百分比，辅助用户理解各版本的贡献
4. **各版本播放趋势**（可选）：小折线图展示各版本随时间推移的播放分布
5. **"这是不同录音" 标记**（L3 模式下）：对 Live/Remix/Acoustic 版本标注其录音类型，帮助用户理解为什么它们被合并在一起

**R30 — 专辑详情页版本展示**

当用户查看的专辑属于一个 release_group（非 L1 模式下），详情页应展示：

1. **Canonical 标识**：页面标题显示 canonical album_name，副标题标注"包含 X 个发行版本"
2. **版本列表**：以卡片形式列出同组所有 album_id：
   - 版本名称（album_name）
   - 封面图
   - 该版本的播放次数
   - 该版本的唯一曲目数
   - 该版本的发行日期
   - 标记哪个是 primary/标准版
3. **曲目覆盖对比**：以矩阵或列表展示各版本包含哪些曲目，哪些是独有曲目（如豪华版加曲）
4. **"独占曲目" 高亮**：标注每个版本独有的曲目，帮助用户理解不同版本的区别

**R31 — 版本展示的交互行为**

1. **默认折叠**：版本列表默认折叠（页面主要内容仍是该实体的统计图表），展开按钮清晰可见
2. **点击版本**：点击列表中的某个版本可跳转到该版本的独立详情页（即使合并了，每个 track_id/album_id 仍可独立查看）
3. **无合并时不显示**：如果该实体不属于任何合并组（L1 模式或无同组版本），不显示版本列表区域
4. **切换严格度时刷新**：用户在全局切换合并级别后，详情页的版本列表内容同步更新（L2 和 L3 下的同组成员不同）

---

## 3. 现状与目标差距矩阵

| 规则 | 当前状态 | 差距 |
|------|----------|------|
| R1 动态阈值 | ❌ | 需从硬编码 30s 改为 `max(30000, duration_ms * 0.1)` |
| R2 播客排除 | ✅ | 无差距 |
| R3 合并触发 | ⚠️ | 仅缺少最大间隔与周边界保护（跨 track_id 合并不在路径 A 范围内） |
| R4 合并计算 | ✅ | 计算逻辑本身无差距 |
| R5 duration_ms 降级 | ✅ | 无差距 |
| R6-R8 曲目版本合并 | ❌ | 完全缺失，需新建 track_groups 体系 |
| R9-R11 专辑版本合并（个人统计） | ⚠️ | Billboard 已有；专辑实体详情部分支持 alias，通用专辑榜仍需推广 canonical 口径 |
| R12-R14 专辑类型过滤 | ⚠️ | Billboard 有部分过滤，需推广并增强 |
| R15-R17 多艺人归属 | ✅ | 无差距（已正确实现） |
| R18-R20 多专辑归属 | ⚠️ | track_albums 已用于辅助分析；缺少播放时 source album 字段，默认专辑榜仍依赖 tracks.album_id |
| R21-R23 Billboard 一致性 | ⚠️ | 部分规则缺失，需补齐后统一 |
| R24 一致性约束 | ❌ | 尚无自动化验证 |
| R25-R27 合并严格度分级 | ❌ | 完全缺失，需设计 track_group 分级 + 前端切换 |
| R28 合并严格度影响范围 | ❌ | 需在各统计路径中实现分级切换 |
| R29-R31 实体详情页版本展示 | ⚠️ | 专辑详情页已有部分 alias 解析；曲目详情页无 |

---

## 4. 分步实施规划

### P0 — 统一 counting policy 与 Billboard fallback 口径

**目标**：不改变产品语义，先消除同一规则在不同路径中实现不一致的问题。

**工作项**：

1. 抽出统一的播放计数策略说明/函数边界：过滤、合并、扇出、聚合分层明确。
2. 修正 Billboard raw fallback：所有需要连续播放合并的路径都应先以 `min_ms=0` 加载音乐记录，再 merge，最后过滤。
3. 给预聚合路径和 raw fallback 路径加同一 seed DB 黄金断言，确保是否命中 `agg_weekly_*` 不改变榜单结果。
4. 将 `merge_enabled` 是否适用于 Billboard 明确化：
   - 推荐：Billboard 也支持 `merge_enabled`，默认 true；
   - 如果产品上不希望暴露开关，也应在 API/documentation 中说明 Billboard 永远使用 merge 口径。
5. 给 `merge_consecutive_plays()` 增加 gap / week boundary 的设计测试，但可先不改变默认行为。

---

### P1 — 播放时 source album 归属 + 专辑版本合并推广

**目标**：让个人专辑榜、实体专辑页、Billboard 专辑榜都基于同一 source album + release group 语义。

**工作项**：

1. Schema：在 `plays` 中新增 `album_id_at_play` / `source_album_id`，导入时从 `master_metadata_album_album_name` 写入。
2. Backfill：对历史数据用当前 `tracks.album_id` 回填，保留一份"无法还原真实 source album"的标记或说明。
3. release_groups 扩展：为现有 `release_groups` 表新增 `scope`（`'release'`/`'composition'`）和 `parent_group_id` 字段，与 P4 中 `track_groups` 的两层模型一致。现有数据全部标记为 `scope='release'`。**注意**：现有唯一约束 `UNIQUE(canonical_name, artist_id)` 需改为 `UNIQUE(canonical_name, artist_id, scope)`，否则同一 canonical name 无法同时存在 release 和 composition 两条记录。
4. 统计路径：专辑聚合优先使用 `source_album_id`，再应用 `release_groups` 合并到 canonical album（按当前 merge_level 选 scope）。
5. 通用专辑排行榜：在 `_chart_agg(entity="album")` 中使用 canonical album 口径，避免个人榜和 Billboard 榜版本合并不一致。
6. 专辑实体详情：继续支持输入任一 alias 进入 canonical album，同时保留版本明细。
7. 封面/metadata：canonical album 优先使用 `primary_album_id`，缺失时 fallback 到组内有封面的成员。

---

### P2 — 动态阈值 + 连续播放合并边界

**目标**：让"有效播放"对长曲目更公平，并避免相隔过久的同曲播放被误合并。

**工作项**：

1. 新建 `effective_threshold(duration_ms, min_ms=30000, ratio=0.1)`。
2. 由于 SQL 层无法在 WHERE 中引用 duration_ms（需要 JOIN），改为：
   - 不合并路径：SQL 可继续用 `ms_played >= min_ms` 做粗过滤，再 DataFrame 二次过滤；
   - 合并路径：SQL 必须用 `min_ms=0` 拉取候选记录，merge 后用动态阈值过滤。
3. `merge_consecutive_plays()` 增加可配置最大间隔，例如 10-30 分钟；超过间隔的同曲相邻记录不合并。
4. Billboard 合并时不跨 `billboard_week`；普通统计合并时不跨自然日或可配置 period boundary。
5. 更新 dashboard、analysis、entity、Billboard、pre-aggregation 的 contract 测试。

---

### P3 — 专辑类型区分

**目标**：实现 R12、R13、R14

**工作项**：

1. 在专辑聚合结果中附带 `album_type` 和曲目数
2. 默认过滤 `album_type = 'single'`（或曲目数 ≤ 2）
3. 辅助判断逻辑：对 `album` 类型但曲目数 ≤ 3 的标记为 "可能是 EP"
4. 前端增加类型筛选开关

---

### P4 — 曲目版本合并 + 合并严格度分级（高风险，后置）

**目标**：实现 R6-R8、R25-R28（与 R3 路径 A 边界一致：版本合并仅在聚合层，不扩展 `merge_consecutive_plays()` 的合并范围）。

**后置原因**：曲目版本合并会同时影响曲目榜、艺人榜、专辑归属、Billboard 历史记录、缓存参数和前端详情页，且误合并成本高。应在 P0-P3 的口径和测试稳定后再做。

**工作项**：

1. **数据模型 — 两层分组结构**

   L2（recording group）和 L3（composition group）是父子关系：多个 recording group 可归属于一个 composition group。不能用单个 `merge_level` 字段表达，需要自引用层级：

   ```sql
   -- track_groups: scope='recording' 对应 L2，scope='composition' 对应 L3
   CREATE TABLE track_groups (
       group_id INTEGER PRIMARY KEY,
       canonical_name TEXT NOT NULL,
       primary_track_id INTEGER REFERENCES tracks(track_id),
       scope TEXT NOT NULL CHECK(scope IN ('recording', 'composition')),
       parent_group_id INTEGER REFERENCES track_groups(group_id),  -- recording → composition
       is_manual BOOLEAN DEFAULT 0
   );

   CREATE TABLE track_group_members (
       group_id INTEGER REFERENCES track_groups(group_id),
       track_id INTEGER REFERENCES tracks(track_id),
       UNIQUE(group_id, track_id)
   );
   ```

   - **recording group**（L2）：同一次录音的不同发行包装（Remastered + Clean + 区域版）
   - **composition group**（L3）：同一作品的所有录音（多个 recording group 的父级 + 独立 track：Live、Acoustic、Taylor's Version 等）
   - **查询时**：L1 不查任何 group；L2 查 `scope='recording'` 的 group；L3 查 `scope='composition'` 的 group（通过 `parent_group_id` 或直接成员）

2. **自动检测**
   - 在 `version_merge.py` 中新增 `detect_track_groups()`
   - 第一阶段检测 recording groups（同名归一化 + ISRC + 时长匹配，高置信度自动应用）
   - 第二阶段检测 composition groups（跨 recording groups 聚类 + Spotify track relinking，低置信度人工确认）
   - 输出 recording groups 和 composition groups，后者通过 `parent_group_id` 关联前者
3. **聚合层集成**（路径 A — 跨 track_id 合并在聚合层）
   - `merge_consecutive_plays()` 不变，始终只合并同一 track_id 的连续行
   - L1：曲目排行榜按 `track_id` 聚合
   - L2：按 `recording_group_id` 聚合（同一 recording group 内各 track_id 的播放次数求和）
   - L3：按 `composition_group_id` 聚合（同一 composition group 内所有 track_id 的播放次数求和，含其下各 recording group）
   - duration 基准优先用实际播放 track 的 duration，不固定为 primary_track
4. **统计集成**
   - 曲目排行榜聚合键 = 上述按 merge_level 选中的 group scope
   - 默认展示 canonical track_name，可展开版本明细
   - **composition group 成员展开**：实现时提供 resolver/view，将 composition group 展开为全体成员 track_id = `direct members`（直接挂在 composition group 下的 track） ∪ `child recording group members`（通过 `parent_group_id` 关联的 recording group 下的所有 track）。避免各处 SQL 临时拼凑。

5. **管理界面**
   - CRUD API：`/api/track-groups/*`
   - 前端管理页：查看两层分组树、合并、拆分、标记不再提示

### P4b — 实体详情页版本展示（依赖 P4）

**目标**：实现 R29-R31

**工作项**：

1. 曲目详情页新增"版本"折叠区域，列出同 track_group 成员及各自播放次数
2. 专辑详情页在已有 alias 解析基础上增强：显示各版本播放次数、曲目覆盖对比
3. 版本列表支持点击跳转到独立详情页
4. 无合并组时不显示版本区域
5. 切换全局合并级别时版本列表同步更新

---

### P5 — Catalog membership 专辑视图（可选）

**目标**：实现 R18、R19、R20

**工作项**：

1. 不替代默认专辑榜；作为单独视图或筛选开关提供。
2. 新增专用 loader 或 aggregation helper，避免在 `load_plays()` 主路径中引入默认扇出。
3. 确保合并先于专辑 membership 扇出。
4. 前端明确标注：该视图下专辑播放次数之和可能大于总播放次数。

---

### P6 — 一致性测试与文档同步

**目标**：实现 R24

**工作项**：

1. 编写 contract/integration 测试验证各项不变量的成立
2. CI 中加入统计一致性校验
3. 更新 README、AGENTS/CLAUDE、后端架构文档中的播放统计口径
4. 为典型边界数据建立 seed fixture：
   - 短播放碎片合并
   - 长曲目动态阈值
   - 同曲跨 album source
   - release group 合并
   - 多艺人 fan-out
   - Billboard raw vs pre-aggregation 一致性

---

## 5. 审查补充：需要修正的判断

### 5.1 合理的部分

1. **先把规则写成技术无关目标是对的**。播放统计不是一个单点函数问题，而是播放事件、音乐实体、榜单实体三层语义的组合；先定义 R1-R24 可以避免后续每个页面各算各的。
2. **连续播放合并"先合并再过滤"的方向是对的**。Spotify Extended Streaming History 中常见碎片记录，直接 SQL 过滤会丢掉原本应合并成一次有效播放的片段。
3. **艺人 fan-out 是合理默认**。个人艺人统计回答的是"我听过哪些艺人"，合作曲给每个艺人完整 credit 可解释；但 UI 必须标注艺人播放次数之和会大于总播放次数。
4. **专辑 release group 继续沿用现有体系是对的**。现有 `release_groups` / `release_group_members`、曲目重叠率、超集检测、album/single 分管线，已经是可复用基础。
5. **Billboard 排名用 `play_count DESC, total_ms DESC` 是清晰且稳定的**。这符合个人榜单"次数优先，时长破平"的直觉。

### 5.2 本轮已采纳的审查修正

以下审查意见已在正文中修正，标注对应的规则/计划编号：

1. **多专辑归属默认扇出不合理** → 已在 R18 修正为 source album 默认口径，多专辑扇出改为可选的 catalog membership 视图（R19）。
2. **"多专辑归属完全未处理"的说法过重** → 已在现状分析 1.4 修正，区分了"track_albums 辅助用途"和"缺少播放事件级 source_album_id"。
3. **"个人分析统计未应用专辑版本合并"需要拆开说** → 已在现状分析 1.5 修正，标注了"专辑实体详情已支持部分 alias 解析"。
4. **曲目版本合并不能只靠名称归一化** → 已在 R6/R25 中明确：L2/L3 分级合并 + `track_groups` 表 `scope` 字段 + P4 中"高置信度自动应用，低置信度人工确认"。
5. **动态阈值不应直接塞进 `base_filters()`** → 已在 P2 工作项中明确：SQL 层保留粗过滤，DataFrame 层做 `effective_threshold()` 二次过滤。
6. **Billboard raw fallback 需要先修一致性** → 已提升为 P0，包含"统一 counting policy"和"给 raw vs pre-aggregation 加黄金断言"。
7. **连续播放合并缺少 session 边界** → 已在现状分析 1.2 中标注，P2 工作项中增加"最大间隔"和"不跨 Billboard 周边界"。
8. **艺人数据来源偏弱** → 已记录为已知局限，后续可从 Spotify metadata 回填，非本次优先级。
9. **专辑类型不能只依赖 album_type** → 已在 R12 中注明需要 taxonomy（曲目数 + 总时长辅助判断），P3 工作项包含辅助判断逻辑。
10. **实施顺序应从低风险开始** → 已重构为 P0（counting policy）→ P1（source album + release group）→ P2（动态阈值）→ P3（专辑类型）→ P4（曲目版本合并），风险递增。

### 5.3 下一步进入实现前的验收问题

1. 同一份 seed 数据，Billboard raw fallback 与 `agg_weekly_*` 预聚合输出是否完全一致？
2. 同一专辑标准版/豪华版，在个人专辑榜、专辑详情页、Billboard 专辑榜中是否都指向同一 canonical album？
3. 同一首歌出现在单曲和专辑中时，默认专辑榜是否按 `source_album_id` 统计，而不是按 `track_albums` 全量扇出？
4. 合作曲在艺人榜中是否完整 credit 给每个艺人，同时总播放 KPI 仍使用非扇出路径？
5. 长曲目 30 秒片段在动态阈值启用后是否被过滤，而普通 3 分钟流行歌仍保持 30 秒阈值？
6. 连续播放合并是否不会跨 Billboard 周边界改变周榜归属？
7. 曲目版本候选是否能区分"可合并版本"和"用户有意选择的不同录音体验"？

---

## 6. 实现状态

> 详细实现计划见 `docs/2026-06-12-playback-stats-implementation-plan.md`。

| Phase | 名称 | 状态 | 测试验证 |
|:---|---|:---:|:---|
| A (Task 0-2) | 计数边界提取 + Billboard raw/agg 一致性 | ✅ | `pytest -m contract test_playback_rules_baseline.py test_billboard_counting_consistency.py` |
| B (Task 3,4,6) | source_album_id + Release Groups + Album Type | ✅ | `pytest -m contract test_source_album_attribution.py test_album_release_groups.py` + `-m unit test_album_type_taxonomy.py` |
| C (Task 5) | 动态阈值 + Session 边界 | ✅ | `pytest -m unit test_playback_counting.py` |
| D (Task 7,8) | Track Groups + Merge Level API + 前端 | ✅ | `pytest -m unit test_track_groups.py` + `-m contract test_merge_level_aggregation.py` + `npm test query-hooks.test.tsx` |
| E (Task 9) | 版本详情展示 | ✅ | `pytest -m contract test_merge_level_aggregation.py` + `npm run build` |
| F (Task 10) | 不变式测试 + 文档同步 | ✅ | `pytest -m contract test_playback_invariants.py` |
| G (2026-06-18) | 过滤参数全入口贯穿 + Release Cycle 对齐 | ✅ | `pytest -m contract test_playback_filter_parameter_propagation.py` + 真实数据 API 对账 |

**测试基线**（2026-06-18）：
- backend unit: 223 passed
- backend contract: 104 passed（覆盖 R23 跨周边界、L3 父子组、R24b 不变量、Session 边界、source_album 归属、pre_agg 一致性、Leaderboard merge_level 传播、PlayFilters/BillboardFilters 过滤参数传播、TrackDetail 版本组 SQL）
- backend full: 520 passed
- frontend build: `npm run build` passed

**已知局限**：
- Issue 2 已修复：`_apply_track_groups()` 同步 canonicalize `album_name`，pre_agg 路径 groupby 移除 `album_name` 不再产生重复行
- 2026-06-18 已修复：Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Artist Deep Dive/Release Cycle 统一传递 `dynamic_threshold` 与 `max_merge_gap_minutes`，Release Cycle 改按 `billboard_week` 年份过滤并接入 `merge_level` / `include_compilations`
- P5: R19 catalog membership 可选视图未实现（远期，R24b.4 对应不变式测试随此功能延后）
- 远期：R29.4 各版本播放趋势折线图（规则标注为可选，非硬性需求）

---

## 附录：关键文件索引

| 文件 | 涉及规则 |
|------|----------|
| `backend/core/db.py` — `base_filters()`, `merge_consecutive_plays()`, `load_plays()` | R1-R5 |
| `backend/core/import_data.py` — `_cache_track()`, `_cache_album()` | R6, R9 |
| `backend/core/version_merge.py` — 版本检测引擎 | R9, R6 |
| `backend/domains/billboard/version_merge.py` — Billboard 版本合并 | R10 |
| `backend/domains/billboard/chart_ranking.py` — 周榜排名 | R13, R22 |
| `backend/services/analysis_stats_service.py` — 个人分析统计 | R10, R13 |
| `backend/services/entity_stats_service.py` — 实体统计 | R10, R15 |
| `backend/dependencies.py` — `PlayFilters` | R1, R2 |
| `backend/tests/contract/test_playback_filter_parameter_propagation.py` — 过滤参数传播合约 | R1, R2, R10, R15 |
