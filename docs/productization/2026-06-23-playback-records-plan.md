# 播放记录（Playback Records）完整规划

> 创建日期：2026-06-23  
> 状态：产品与技术规划，尚未实现  
> 目标位置：`/analysis/records`  
> 关联规则：`docs/playback-stats/rules.md`、`docs/playback-stats/album-project.md`、`docs/productization/2026-06-22-phase5-delivery-report.md`

## 1. 模块定位

播放分析现有页面主要回答三类问题：

| 页面 | 当前职责 | 局限 |
|---|---|---|
| `/analysis/stats` | 总体 KPI、小时/日/周/月/年分布、最近播放 | 更偏平均值、分布和趋势 |
| `/analysis/charts` | 歌曲/专辑/艺人个人排行榜 | 更偏总量排名 |
| `/billboard/records` | 基于周榜名次的榜单纪录 | 关注榜单竞争表现，而不是个人播放行为 |

新增 `/analysis/records` 的定位是：

> 基于有效播放事件的个人音乐史纪录馆，展示极值、连续、爆发、回归、统治、发现和行为巧合。

它应和 Billboard Records 形成语义对称：

| 模块 | 关注对象 | 代表问题 |
|---|---|---|
| Billboard Records | 榜单表现 | 谁冠军最多、谁在榜最长、谁走势最强 |
| Playback Records | 个人行为 | 哪天听得最疯、哪首歌陪得最久、哪个艺人统治某段时间 |

## 2. 设计硬原则

### 2.1 实体完整性原则

只要一个记录主题在歌曲、专辑、艺人三个实体层都语义成立，就必须同时支持三种实体，并放在同一个 RecordCard 内通过按钮切换显示。

禁止以下做法：

- 只实现歌曲版，遗漏同样成立的专辑版和艺人版。
- 分别做成“歌曲单日爆听”“专辑单日爆听”“艺人单日爆听”三个散落卡片。
- 后端返回三个互不相关的记录名，导致前端无法把它们识别为同一个 record family。

推荐数据形态：

```ts
daily_binge: {
  track: PlaybackRecordRow[]
  album: PlaybackRecordRow[]
  artist: PlaybackRecordRow[]
}
```

推荐前端形态：

```text
RecordCard: 单日爆听
  Toggle: 歌曲 / 专辑 / 艺人
  Body: 同一张表或 featured cards 按实体切换
```

### 2.2 记录类型分类

| 类型 | 处理方式 | 示例 |
|---|---|---|
| 三实体记录 | 必须提供 `track / album / artist` 切换 | 单日爆听、最长连续播放天数、沉睡后回归 |
| 双实体记录 | 同一卡片内只显示语义成立的实体按钮，并在 record definition 中说明缺失原因 | 合作偏好可做歌曲/艺人，不适合专辑 |
| 单实体记录 | 只在该实体语义独有时使用 | 专辑完成度只做专辑 |
| 事件型记录 | 不强行实体化 | 最长活跃日 streak、平台切换最多日、第 10000 次播放 |

### 2.3 统计口径原则

播放记录必须继承现有播放统计规则：

- 默认 `music_only=True`。
- 默认启用 dynamic threshold。
- 连续播放合并遵循“先 merge 后 filter”。
- 播放事件层不随 `merge_level` 改变。
- `merge_level` 只影响实体归属层的歌曲、专辑、艺人聚合。
- 专辑记录默认使用 album project 口径，而不是 source album 容器口径。
- 艺人记录使用 fan-out 口径，多艺人歌曲 credit 给所有参与艺人。

比例型记录必须设置最小样本门槛，避免小样本产生误导。例如：

| 记录 | 建议门槛 |
|---|---|
| Shuffle 率最高日 | 当日有效播放不少于 20 次 |
| 快进率最高歌曲 | 该实体有效播放不少于 10 次 |
| 深夜占比最高日 | 当日有效播放不少于 20 次 |
| 平台占比最高日 | 当日有效播放不少于 20 次 |

## 3. 页面整体结构

### 3.1 路由与导航

新增 Analysis 第三个 tab：

| 路径 | Tab 文案 | 页面标题 |
|---|---|---|
| `/analysis/stats` | 总体统计 | 总体播放统计 |
| `/analysis/charts` | 个人排行榜 | 个人排行榜 |
| `/analysis/records` | 播放记录 | 播放记录 |

页面头部：

- Eyebrow：`Playback Records`
- H1：`播放记录`
- 描述：`基于有效播放事件，整理你的个人音乐史极值、连续、回归与行为纪录。`

页面保留 Analysis 统一时间范围选择器：

- lifetime
- today
- this_week
- this_year
- last_4_weeks
- last_6_months
- custom

### 3.2 页面信息架构

页面使用 6 个 section tab 或纵向 section。第一版推荐沿用 Billboard Records 的 tab 体验，默认打开“狂热时刻”，其余 section 懒加载。

| Section | 定位 | 默认优先级 |
|---|---|---|
| 狂热时刻 | 极端播放与循环行为 | P0 |
| 时间密码 | 小时、星期、月份、年度峰值 | P1 |
| 个人王朝 | 某实体在日/月/年维度的统治 | P0/P1 |
| 长线陪伴 | 连续天数、跨度、回归和长期陪伴 | P0 |
| 探索发现 | 新歌、新艺人、不重复与专辑完成度 | P1 |
| 行为奇观 | Shuffle、快进、平台、离线、里程碑 | P1/P2 |

### 3.3 Section 默认排序

建议首屏顺序：

1. Section tabs。
2. 当前 section 的 2-3 个 FeaturedRecord，高亮最强纪录。
3. 记录卡片列表，每个卡片内部再分页。

不要在首屏塞满所有 6 个 section 的内容，否则会变成信息瀑布。长表默认每页 10 行，保持和 Billboard Records 的阅读节奏一致。

## 4. 页面内容规划

### 4.1 Section：狂热时刻

关注“某一天或某段连续播放里听得最疯”的记录。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 单日爆听 | 歌曲 / 专辑 / 艺人 | P0 | 单个自然日内某实体播放次数最高；并展示同日时长、峰值日期、封面 |
| 单日听歌时长 | 歌曲 / 专辑 / 艺人 | P0 | 单个自然日内某实体累计播放时长最高 |
| 连续播放马拉松 | 歌曲 / 专辑 / 艺人 | P0 | 播放序列中连续出现同一实体的最长 run |
| 单日总量纪录 | 事件型 | P0 | 某自然日总播放次数、总时长、独特歌曲数最高 |
| 日内跨度纪录 | 事件型 | P1 | 一天内首次播放到最后播放跨度最长，展示起止歌曲和跨度小时 |

“连续播放马拉松”与“最长连续播放天数”必须分开：

| 名称 | 统计单位 | 示例 |
|---|---|---|
| 连续播放马拉松 | 播放序列 | 连续 36 次播放同一首歌 |
| 最长连续播放天数 | 自然日 presence streak | 连续 18 天每天都听某首歌 |

### 4.2 Section：时间密码

关注“时间维度里最有个性的峰值”。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 时段统治 | 歌曲 / 专辑 / 艺人 | P1 | 在某小时段内播放次数最多的实体，例如 23 点最常出现的歌曲 |
| 月度巅峰 | 歌曲 / 专辑 / 艺人 | P1 | 单月内某实体播放次数或时长最高 |
| 年度巅峰 | 歌曲 / 专辑 / 艺人 | P1 | 单年内某实体播放次数或时长最高 |
| 深夜峰值日 | 事件型 | P1 | 0-5 点播放次数或占比最高的日期，设最小样本门槛 |
| 星期偏好 | 事件型 | P2 | 星期几播放总量最高、平均活跃日播放最高 |
| 跨年时刻 | 事件型 | P2 | 跨年午夜前后播放的歌曲与艺人 |

### 4.3 Section：个人王朝

关注“谁在你的时间线里统治过”。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 每日冠军次数 | 歌曲 / 专辑 / 艺人 | P0 | 成为自然日播放冠军次数最多的实体 |
| 月度统治 | 歌曲 / 专辑 / 艺人 | P1 | 成为自然月播放冠军次数最多，或单月占比最高 |
| 年度统治 | 歌曲 / 专辑 / 艺人 | P1 | 成为年度播放冠军，展示年份、播放数、份额 |
| 最快里程碑 | 歌曲 / 专辑 / 艺人 | P1 | 从首次播放到达到阈值所需天数最短 |
| 连续冠军天数 | 歌曲 / 专辑 / 艺人 | P2 | 连续多天成为日冠军的实体 |

里程碑阈值建议：

| 实体 | 阈值 |
|---|---|
| 歌曲 | 10 / 25 / 50 |
| 专辑 | 25 / 50 / 100 |
| 艺人 | 50 / 100 / 250 |

### 4.4 Section：长线陪伴

关注“长期关系”，这是 Playback Records 的核心 section 之一。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 最长连续播放天数 | 歌曲 / 专辑 / 艺人 | P0 | 某实体连续多少个自然日每天至少播放一次 |
| 最长陪伴跨度 | 歌曲 / 专辑 / 艺人 | P0 | 首次播放到最近一次播放的日期跨度最长 |
| 沉睡后回归 | 歌曲 / 专辑 / 艺人 | P0 | 同一实体两次出现之间间隔最长，并在后一次重新出现 |
| 长期稳定陪伴 | 歌曲 / 专辑 / 艺人 | P1 | 活跃月份或活跃年份最多的实体 |
| 用户连续活跃天数 | 事件型 | P0 | 用户连续有任意音乐播放记录的最长天数 |

#### 4.4.1 最长连续播放天数算法

输入是有效播放事件，先按实体生成每日 presence：

```text
track:  ts_date + canonical_track_id
album:  ts_date + album_project_id
artist: ts_date + artist_name fan-out
```

每个实体每天只保留一次 presence，然后按日期排序，若相邻日期差为 1 天则延续 streak，否则断开。

输出字段：

```ts
{
  entity_type: 'track' | 'album' | 'artist'
  entity_id: string | number | null
  name: string
  artist_name?: string
  streak_days: number
  start_date: string
  end_date: string
  total_plays: number
  total_hours: number
  active_dates: number
  peak_day: string
  peak_day_plays: number
  cover_url: string | null
}
```

排序：

1. `streak_days` 降序。
2. `total_plays` 降序。
3. `total_hours` 降序。
4. `end_date` 降序。
5. `entity_id` 稳定排序。

边界：

- 如果用户 period 是 custom，则 streak 只在该 period 内计算，不跨 period 补历史。
- 如果一个实体在 period 开始前已经连续播放，不在第一版展示“左截断提示”；后续可在 P2 增加 `is_left_censored`。
- 专辑用 album project membership 归因。
- 艺人用 fan-out，不只看主艺人。

### 4.5 Section：探索发现

关注“新东西”和“多样性”。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 发现日 | 歌曲 / 专辑 / 艺人 | P1 | 单日首次出现的新实体数量最多 |
| 最长不重复序列 | 歌曲 / 专辑 / 艺人 | P1 | 播放序列中连续不重复实体最长 |
| 专辑完成者 | 专辑 | P1 | album project 内播放过的 canonical songs 覆盖率最高 |
| 同名异曲 | 歌曲 | P2 | 相同歌名但不同艺人的歌曲集合 |
| 合作偏好 | 歌曲 / 艺人 | P2 | 多艺人歌曲播放占比、最常出现合作对象 |
| 冷门发现 | 歌曲 / 艺人 | P2 | 依赖 Spotify popularity 或 metadata 完整度 |
| 风格多样性 | 艺人 / 日期 | P2 | 依赖 genre metadata 完整度 |

冷门发现和风格多样性不进入第一版核心，因为它们依赖外部元数据质量。第一版应优先使用 Extended Streaming History 本身稳定可计算的事实。

### 4.6 Section：行为奇观

关注平台、shuffle、快进、离线等行为字段。

| RecordCard | 实体切换 | 优先级 | 定义 |
|---|---|---:|---|
| 快进风暴 | 歌曲 / 专辑 / 艺人 | P1 | `reason_end='fwdbtn'` 次数或比例最高，设实体播放门槛 |
| Shuffle 高峰 | 事件型 | P1 | Shuffle 率最高日期或月份，设样本门槛 |
| 平台统治 | 事件型 | P1 | 某平台播放占比最高时期 |
| 平台切换日 | 事件型 | P1 | 同日平台切换次数最多 |
| 离线峰值 | 事件型 | P2 | offline 播放占比最高日期或月份 |
| 隐身峰值 | 事件型 | P2 | incognito_mode 占比最高日期或月份 |
| 播放里程碑 | 事件型 | P1 | 第 1000 / 5000 / 10000 / 50000 次有效播放对应歌曲、日期和平台 |

## 5. 后端技术规划

### 5.1 API

新增端点：

```text
GET /api/analysis/records
```

参数：

| 参数 | 来源 | 说明 |
|---|---|---|
| `min_ms` | `PlayFilters` | 最短播放时长 |
| `music_only` | `PlayFilters` | 默认只统计音乐 |
| `merge_enabled` | `PlayFilters` | 是否合并连续播放 |
| `dynamic_threshold` | `PlayFilters` | 动态有效播放阈值 |
| `max_merge_gap_minutes` | `PlayFilters` | 连续播放最大合并间隔 |
| `merge_level` | `MergeConfig` | 实体归属合并级别 |
| `period` | query | 时间范围 |
| `start_date` | query | custom 起始日期 |
| `end_date` | query | custom 结束日期 |
| `include_compilations` | query | 专辑记录是否包含精选集 |

### 5.2 文件结构

```text
backend/api/analysis.py
backend/models/analysis.py
backend/services/analysis_records_service.py
backend/domains/playback/records.py
backend/domains/playback/records_obsession.py
backend/domains/playback/records_time.py
backend/domains/playback/records_reigns.py
backend/domains/playback/records_longevity.py
backend/domains/playback/records_discovery.py
backend/domains/playback/records_behavior.py
backend/domains/playback/records_output.py
```

职责：

| 文件 | 职责 |
|---|---|
| `analysis.py` | 暴露 `/analysis/records`，只做参数注入和 response model |
| `analysis_records_service.py` | 缓存、period 解析、一次性加载 DataFrame、调度 record families |
| `records.py` | facade，汇总 6 个 record family |
| `records_*` | 各 section 的纯计算逻辑 |
| `records_output.py` | 封面、artist names、JSON-safe 序列化、字段规范化 |
| `models/analysis.py` | Pydantic response models |

### 5.3 计算管线

整体管线：

```text
PlayFilters + period + merge_level
  -> load_period_plays()
  -> build entity attribution frames
  -> compute record families
  -> enrich covers / artist_names
  -> serialize response
```

实体归属 frames：

| Frame | 来源 |
|---|---|
| `track_events` | `load_plays()` + track group canonicalization |
| `album_events` | `compute_album_project_plays()` 或 album project membership 映射到事件层 |
| `artist_events` | `load_plays_for_artists()` |
| `event_frame` | 原有效播放事件，用于日期、平台、shuffle、reason_end 等事件型记录 |

为避免重复计算，`analysis_records_service.py` 应在一次请求里构造共享上下文：

```python
context = PlaybackRecordsContext(
    conn=conn,
    period=resolved,
    event_frame=df,
    track_events=track_events,
    album_events=album_events,
    artist_events=artist_events,
)
```

各 record family 只接收 context，不自行重新调用 `load_plays()`。

### 5.4 缓存策略

- `get_analysis_records()` 使用 `@lru_cache(maxsize=64)`。
- 注册到 Cache Manager：`register_lru("analysis", "records", _get_analysis_records_cached)`。
- 缓存 key 必须包含：
  - `min_ms`
  - `music_only`
  - `merge_enabled`
  - `period`
  - `start_date`
  - `end_date`
  - `merge_level`
  - `dynamic_threshold`
  - `max_merge_gap_minutes`
  - `include_compilations`
- 不在子模块内部做新的模块级 Map 缓存。

### 5.5 Response shape

推荐顶层结构：

```ts
interface PlaybackRecordsResponse {
  period: AnalysisResolvedPeriod
  meta: {
    total_plays: number
    total_hours: number
    active_days: number
    merge_level: number
    min_sample_plays: number
    generated_at: string
  }
  records: {
    obsession: PlaybackObsessionRecords
    time_patterns: PlaybackTimePatternRecords
    reigns: PlaybackReignRecords
    longevity: PlaybackLongevityRecords
    discovery: PlaybackDiscoveryRecords
    behavior: PlaybackBehaviorRecords
  }
}
```

三实体 record family：

```ts
interface EntityRecordFamily {
  track: PlaybackRecordRow[]
  album: PlaybackRecordRow[]
  artist: PlaybackRecordRow[]
}
```

通用行模型：

```ts
interface PlaybackRecordRow {
  rank: number
  entity_type?: 'track' | 'album' | 'artist'
  entity_id?: string | number | null
  name: string
  artist_name?: string | null
  artist_names?: string[] | null
  value: number
  unit: string
  secondary_value?: number | null
  secondary_unit?: string | null
  date?: string | null
  start_date?: string | null
  end_date?: string | null
  total_plays?: number | null
  total_hours?: number | null
  share_pct?: number | null
  cover_url?: string | null
  caption?: string | null
}
```

事件型 record family 可以使用专用模型，但字段仍尽量接近 `PlaybackRecordRow`，方便前端复用。

## 6. 前端技术规划

### 6.1 路由与数据

修改：

```text
frontend/src/App.tsx
frontend/src/components/shared/AnalysisSubNav.tsx
frontend/src/hooks/useAnalysis.ts
frontend/src/api/query-keys.ts
frontend/src/types/analysis.ts
```

新增：

```text
frontend/src/pages/AnalysisRecordsPage.tsx
frontend/src/features/analysis/records/PlaybackRecordsExperience.tsx
frontend/src/features/analysis/records/PlaybackRecordsPrimitives.tsx
frontend/src/features/analysis/records/ObsessionSection.tsx
frontend/src/features/analysis/records/TimePatternsSection.tsx
frontend/src/features/analysis/records/ReignsSection.tsx
frontend/src/features/analysis/records/LongevitySection.tsx
frontend/src/features/analysis/records/DiscoverySection.tsx
frontend/src/features/analysis/records/BehaviorSection.tsx
frontend/src/features/analysis/records/recordsData.ts
```

新增 query key：

```ts
queryKeys.analysis.records(params)
```

新增 API helper：

```ts
analysisApi.records(filters, {
  period,
  start_date,
  end_date,
  include_compilations,
})
```

### 6.2 页面组件边界

| 层级 | 文件 | 行数目标 | 职责 |
|---|---|---:|---|
| Route Container | `AnalysisRecordsPage.tsx` | ≤120 | 获取 filters/query state，调用 API，处理 loading/error |
| Experience | `PlaybackRecordsExperience.tsx` | ≤450 | 管 section tab、总体布局、section 懒加载 |
| Section | `*Section.tsx` | ≤300 | 渲染一个 section 的 record cards |
| Primitives | `PlaybackRecordsPrimitives.tsx` | ≤350 | Entity toggle、RecordCard、MiniRankTable、FeaturedRecord |
| Data helpers | `recordsData.ts` | 不限 UI | 格式化、排序、cover map、类型 guard |

### 6.3 实体切换组件

必须提供专用组件，避免每个 section 手写按钮：

```ts
type EntityRecordType = 'track' | 'album' | 'artist'

interface EntityRecordToggleProps {
  value: EntityRecordType
  available: EntityRecordType[]
  onChange: (value: EntityRecordType) => void
}
```

三实体卡片统一入口：

```ts
interface EntityRecordCardProps {
  title: string
  subtitle?: string
  recordsByEntity: {
    track?: PlaybackRecordRow[]
    album?: PlaybackRecordRow[]
    artist?: PlaybackRecordRow[]
  }
  defaultEntity?: EntityRecordType
  columns: Record<EntityRecordType, PlaybackRecordColumn[]>
}
```

验收约束：

- 同一个 record family 只能渲染一个 `EntityRecordCard`。
- 如果 `track / album / artist` 都存在，toggle 必须显示三个按钮。
- 如果某个实体不存在，必须由 record definition 决定，不允许因为后端临时为空就隐藏实体类型。

### 6.4 视觉与交互

整体沿用项目当前“编辑风 + 液态玻璃”风格：

- 标题和数字使用 Playfair Display。
- 正文、表格、按钮使用 Inter。
- 卡片半透明玻璃材质，但不嵌套卡片。
- RecordCard 半径控制在 8px 左右，和现有产品内工具界面一致。
- 按钮使用 segmented controls，不用散落的文本按钮。
- 表格默认分页 10 行，避免长列表 DOM 爆炸。

首屏 loading：

- 使用固定高度 skeleton，避免 CLS。
- section 懒加载 fallback 使用 2-3 个记录卡骨架。

## 7. 实施步骤规划

### Phase A：文档与合约冻结

目标：冻结 record families、响应结构和实体完整性规则。

交付：

- 本规划文档。
- 后续实现前可单独补 `docs/playback-stats/records.md` 作为统计口径说明。
- 明确 P0/P1/P2，不在第一版引入元数据依赖型记录。

验收：

- 所有三实体记录在文档中都有 track/album/artist 定义。
- 所有事件型记录都有“不强行三实体化”的理由。

### Phase B：后端 P0 计算与 API

目标：实现 `/api/analysis/records` 的 P0 记录。

P0 records：

- 单日爆听：track / album / artist。
- 单日听歌时长：track / album / artist。
- 连续播放马拉松：track / album / artist。
- 每日冠军次数：track / album / artist。
- 最长连续播放天数：track / album / artist。
- 最长陪伴跨度：track / album / artist。
- 沉睡后回归：track / album / artist。
- 用户连续活跃天数：事件型。
- 单日总量纪录：事件型。

验收：

- Contract tests 覆盖 response shape。
- Unit tests 覆盖 streak、run、comeback gap、daily champion。
- 极端筛选返回空数组但 shape 不变。
- 动态阈值参数会改变结果或在 seed DB 中有可验证差异。

### Phase C：前端页面骨架与 P0 展示

目标：完成 `/analysis/records` 可用页面。

交付：

- AnalysisSubNav 新增“播放记录”。
- App route 新增 `/analysis/records`。
- 页面加载 `/api/analysis/records`。
- 6 个 section tab 骨架。
- P0 RecordCards 完整展示。
- 三实体 toggle 工作正常。

验收：

- `npm run build` 通过。
- route smoke 覆盖 `/analysis/records`。
- control inventory 覆盖实体切换按钮、section tabs 和分页按钮。
- 不出现横向滚动溢出。

### Phase D：P1 记录扩展

目标：补齐更丰富但仍稳定的数据记录。

P1 records：

- 月度巅峰：track / album / artist。
- 年度巅峰：track / album / artist。
- 月度统治：track / album / artist。
- 最快里程碑：track / album / artist。
- 发现日：track / album / artist。
- 最长不重复序列：track / album / artist。
- 专辑完成者：album。
- 快进风暴：track / album / artist。
- Shuffle 高峰：事件型。
- 平台统治：事件型。
- 平台切换日：事件型。
- 播放里程碑：事件型。

验收：

- 新增 record family 都有 response model。
- 三实体记录完整性测试继续通过。
- 长列表分页 smoke 覆盖至少一个 Playback Records 表格。

### Phase E：验证矩阵与文档同步

目标：纳入现有 Phase 5 验证体系。

需要更新：

- `scripts/api_smoke_probe.py`：新增 `analysis_records`。
- `scripts/api_boundary_probe.py`：新增 period/date/merge_level 边界。
- `scripts/openapi_operation_audit.py`：记录新 operation 覆盖归属。
- `scripts/openapi_parameter_boundary_audit.py`：记录新参数边界覆盖。
- `scripts/frontend_route_smoke.mjs`：新增 `/analysis/records` marker。
- `scripts/frontend_control_inventory_smoke.mjs`：新增 `/analysis/records`。
- `scripts/frontend_long_list_smoke.mjs`：新增 Playback Records 表格分页场景。
- `frontend/src/tests/phase5-architecture.test.ts`：新增 route container / section / primitive 结构护栏。
- `frontend/src/tests/query-hooks.test.tsx`：新增 query key 测试。

文档同步：

- `docs/README.md` 增加 Playback Records 入口。
- `README.md` 如已有功能清单，应在实现完成后补入口。
- `AGENTS.md` / `CLAUDE.md` 只在功能真正落地后同步，不在规划阶段声称已完成。

## 8. 测试与验收标准

### 8.1 后端测试

Unit tests：

- `daily_presence_streak` 正确断开非连续日期。
- `consecutive_run` 区分播放序列 run 与自然日 streak。
- `comeback_gap` 计算同实体相邻播放日期最大 gap。
- `daily_champion` 对并列使用稳定排序。
- `fastest_milestone` 不把未达到阈值的实体纳入。

Contract tests：

- `/api/analysis/records` 返回 `period / meta / records`。
- P0 三实体记录都包含 `track / album / artist`。
- album record 使用 album project。
- artist record 使用 fan-out。
- empty filter 保持 shape。

Integration tests：

- 真实 DB 下 P0 records 至少有非空结果。
- record rows 包含 `cover_url` 字段。
- `merge_level=1` 与 `merge_level=2/3` 在实体聚合记录上可产生不同或至少不破坏 shape。

### 8.2 前端测试

- Route container 不直接实现表格细节。
- `AnalysisRecordsPage.tsx` 行数 ≤450，目标 ≤120。
- Section 文件 ≤300 行。
- 三实体 RecordCard 只渲染一个标题和一个 toggle。
- `npm run build` 通过。
- `/analysis/records` route smoke 通过。
- 390px 移动端无横向滚动。
- visible controls 都有 accessible name。

### 8.3 验收口径

功能完成不能只看测试通过，还要满足：

- 页面能解释“这是播放记录，不是榜单记录”。
- 同一 record family 的歌曲/专辑/艺人不散落。
- P0 记录在真实数据下有足够强的叙事性。
- 专辑/艺人口径与现有播放统计规则一致。
- 新增 API 不显著拖慢 `/analysis` 首次使用体验。

## 9. 风险与取舍

| 风险 | 影响 | 对策 |
|---|---|---|
| 记录太多导致页面碎片化 | 用户难以阅读 | 使用 6 个 section tab，每个卡片聚合三实体 |
| 三实体强约束增加后端工作量 | 实现周期变长 | P0 只做最稳定的三实体记录 |
| album project 事件层归因复杂 | 专辑记录可能口径不一致 | 复用现有 album project membership，不回退 source album |
| artist fan-out 让总量大于播放事件数 | 用户可能疑惑 | 文案标注“多艺人歌曲计入所有参与艺人” |
| period 内 streak 可能被截断 | custom range 解释复杂 | 第一版只计算 period 内 streak，后续再做截断提示 |
| metadata 依赖不完整 | 冷门/genre/完播记录不稳 | 放入 P2，不进入第一版核心 |

## 10. 最终推荐范围

第一版推荐完成：

- `/analysis/records` 页面。
- 6 个 section 的完整框架。
- P0 记录全量展示。
- P1 中不依赖外部元数据的记录优先补齐。
- 三实体 RecordCard 组件和后端 response shape 固化。
- API smoke、route smoke、control inventory、long-list smoke 纳入验证矩阵。

暂不做：

- 分享卡。
- AI 纪录解说。
- 冷门发现和风格多样性。
- 基于完播率的复杂记录。
- 社区动态自动发帖。

这些可以作为 Playback Records 第二阶段，在 P0/P1 数据口径稳定后继续推进。
