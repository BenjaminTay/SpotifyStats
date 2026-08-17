# SpotifyStats 音乐查找性能与体验完整优化规划

> 创建日期：2026-08-16
> 状态：已完成（首轮 M0–M5 与 remediation 全部门禁通过）
> 适用范围：Masthead Quick Open、`/music/search`、`/api/music/search`、搜索派生数据与公开只读运行面
> 关联文档：`docs/reference/playback-stats-rules.md`、`docs/reference/music-metadata-management.md`、`docs/plans/2026-08-05-mobile-web-design-and-implementation-plan.md`、`docs/plans/2026-08-13-dual-deployment-profile-plan.md`
> 历史设计：`docs/archive/05-yearly-report-genre/music-search/`
> 取代边界：保留旧方案的入口归属、详情深链、统计一致性和“不在播放排行重复放搜索框”等产品决策；取代“每次搜索同步计算过滤后播放统计与完整 Billboard payload”的性能实现
> 交付证据：`docs/reports/2026-08-16-music-search-optimization-delivery.md`
> 修复计划：`docs/plans/2026-08-16-music-search-remediation-plan.md`
> 后续方向：`docs/plans/2026-08-16-music-search-direction-realignment.md`（候选/统计身份解耦、发布续建、简繁与有限模糊匹配）

2026-08-16 后续实现已将随机索引 generation 从统计 fingerprint 移除，并以确定性
`candidate_index_version` 单独治理候选索引。真实副本首次只重建候选索引 4.62 秒，六个统计变体
全部 0ms 复用；重复维护 0.41 秒。本文 M0–M5 的两阶段结构与统计一致性结论继续有效，但“普通新
SHA 也必须冷建六变体”的发布假设已由后续方向文档取代。

首轮交付后发现的 L1/L3、动态阈值关闭、非默认 Billboard 参数和高命中查询缺口已经按 remediation
plan 全部修复。真实维护链路现有六个精确 ready 变体；七类查询各 60 次的 HTTP 候选 P50/P95 为
15.780/40.741ms，HTTP context 为 6.034/6.921ms。Chromium、Firefox、WebKit、360–1280px、
200% reflow、公开只读、生产 FTS5/trigram、full/showcase/dual 和迁移恢复门禁均通过。

## 0. 执行摘要

当前音乐查找的信息架构是正确的：Desktop 通过 Masthead 打开全局 Quick Open，Phone
进入独立 `/music/search` 推入页，歌曲、专辑、艺人结果打开现有详情路由。当前主要问题不是
入口不足，而是一个交互式搜索请求同时承担了四类工作：

1. 在本地实体表中查找候选；
2. 加载并切分完整 lifetime 逻辑播放时间线；
3. 按歌曲、album project 和有效艺人署名重新过滤候选统计；
4. 计算完整 Billboard payload，再从中提取少量搜索 badge。

在 2026-08-16 的真实主数据库上，91,286 条播放记录、12,362 首歌曲、5,316 张专辑、
1,189 位艺人的只读基准为：

| 场景 | 实测耗时 |
|---|---:|
| 只搜索候选，不计算过滤后次数和榜单 | 约 213ms |
| 过滤后搜索统计帧 | 冷 6.55s / 热 4.00s |
| 搜索 Billboard lookup | 冷 12.03s / 热 0.63s |
| 完整搜索，不含榜单 | 约 8.31s |
| 完整搜索，包含榜单 | 约 19.81s |
| 同一后端进程内搜索相邻关键词 | 约 5.80s |

这说明仅增加名称索引不能解决主要延迟。最终架构必须将搜索拆为两个独立层次：

- **候选层**：只负责名称、别名、类型、封面和详情深链，持久化索引，快速返回；
- **上下文层**：从精确、版本化、可失效的派生快照读取播放次数和个人 Billboard 摘要，
  不在用户输入请求中重算 lifetime 时间线或完整 Billboard。

前端先显示候选，再渐进补齐统计。用户仍能看到播放次数、`PK #`、在榜周数和走势排名，
但不再被这些次级信息阻塞。Quick Open 和完整页共享查询、实体键、统计语义与缓存，
Desktop、Compact、Phone 保持独立 presentation。

## 1. 目标、非目标与完成定义

### 1.1 目标

1. Quick Open 在本地或个人云的正常网络条件下快速出现首批可点击结果。
2. 搜索热路径不再调用 `load_period_plays()`、完整时间切片或
   `compute_billboard_data()`。
3. 搜索显示的播放次数与详情统计 API 一致，榜单摘要与三类 Billboard 详情一致。
4. 歌曲、专辑、艺人支持名称、相关艺人/专辑、有效别名和常见标点差异匹配。
5. “查看全部结果”进入真正可分页、可分享、可恢复的完整查找页。
6. 快速输入不会造成过时请求堆积、结果闪烁或中文输入法组合阶段误搜索。
7. 搜索在 `private-admin` 与 `public-readonly` 中遵循相同数据事实和不同副作用边界。
8. 导入、统计设置、版本归并、艺人身份与曲目署名变化后，搜索派生数据可诊断、可重建、
   可回滚。

### 1.2 非目标

- 不新增顶级导航项，不在“播放排行”页增加重复搜索框。
- 不建立全站设置、社区帖子、AI 消息或任意文本搜索。
- 不搜索 Spotify 云端未出现在本地数据中的音乐。
- 不调用 LLM、Spotify Web API、Wikipedia、歌词服务或任意外部 URL。
- 不改歌曲、专辑、艺人的既有详情路由。
- 不改播放统计、逻辑时间线、album project、有效署名或 Billboard 口径。
- 不通过拼音库、外部分词服务或模型猜测实体名称；拼写纠错留作独立后续能力。
- 不把导入的 Spotify `search_queries` 当作应用内最近搜索直接公开展示。

### 1.3 完成定义

只有同时满足以下条件才可将本计划标记为完成：

- 候选接口与上下文接口均达到本计划性能预算；
- 候选热路径没有全量 `plays` 聚合和完整 Billboard 计算；
- 三类实体在代表性过滤指纹下通过搜索与详情的一致性契约测试；
- Quick Open、完整页、Phone 页均完成正常、加载、空、错误、过期快照状态；
- 全部结果页具备真实总数和分页，不再把每类 5 条称作“全部”；
- 公开请求不会写库、排队、触发外部补全或构建搜索快照；
- 导入和所有相关治理 mutation 均进入明确的派生数据失效矩阵；
- 360/390/430/768/1280 路由矩阵、键盘、IME、焦点恢复和跨浏览器门禁通过；
- 发布前后性能证据、数据一致性、公共只读和回滚演练写入交付报告。

## 2. 事实基线与根因

### 2.1 当前产品与数据链路

当前入口：

- Desktop/Compact：Masthead 右侧搜索图标打开 `MusicSearchDialog`；
- Phone：Mobile Top Bar 搜索图标进入 `/music/search`；
- 完整页：URL 使用 `q` 与 `kind`，支持歌曲、专辑、艺人切换；
- 详情深链：
  - 歌曲：`/music/tracks/:trackId`
  - 专辑：`/music/albums/:albumName?artist=...`
  - 艺人：`/music/artists/:artistName`
- Quick Open 与完整页当前均请求 `include_chart=true`；
- Quick Open 默认不高亮第一条结果，只有 hover、focus 或方向键后才高亮。

当前后端调用链：

```text
输入关键词
  -> /api/music/search
  -> search_music_entities()
  -> load_period_plays() x track/album 与 artist fan-out
  -> resolve_entities() x track / album / artist
  -> 对每个候选重新过滤 DataFrame
  -> compute_billboard_data()
  -> 将完整 JSON payload 重新转换为 DataFrame 和 lookup
  -> 返回候选 + 播放次数 + chart
```

### 2.2 已确认的主要根因

| 根因 | 当前行为 | 影响 |
|---|---|---|
| 搜索与完整统计耦合 | 每个关键词加载 lifetime 逻辑播放帧 | 热缓存后仍需约 4s |
| 搜索与完整 Billboard 耦合 | 为少量 badge 计算完整榜单、纪录、Power Score 和封面 payload | 冷请求增加约 12s |
| 候选查询复用 AI resolver | 搜索同时承担 schema 探测、艺人 canonicalization 和全量署名播放聚合 | 交互热路径职责过重 |
| 名称查询不可 seek | `lower(name) LIKE '%query%'` | 普通名称索引主要被扫描，仍需临时排序 |
| 专辑候选查询聚合多来源 | 每个关键词组合 track album、junction 与 source album 播放来源 | 每次候选查询重复扫描播放数据 |
| 请求不能随输入取消 | TanStack `queryFn` 未把 `signal` 传给 API | 旧请求继续占用连接和后端线程 |
| 搜索继承全局重试 | 失败可自动重试两次 | 昂贵查询可能被放大三倍 |
| 前端替换整个结果区 | 新 query key 加载时显示 loading panel | 输入时产生明显闪烁和布局变化 |
| 完整页每类仍为 5 条 | API 上限 10，页面固定请求 5 | “查看全部结果”与实际能力不一致 |
| 缓存键未统一搜索文本 | 只 trim，不统一 Unicode、大小写和标点 | 相同意图形成多份缓存 |

### 2.3 为什么不能只调整防抖或加普通索引

- 250ms 防抖只能减少请求数量，不能缩短单个请求的 4–20s 执行时间。
- 普通 B-tree 对前导 `%` 的子串查询不能高效定位。
- 即使候选检索降到几十毫秒，完整播放统计和 Billboard 仍是主要耗时。
- HTTP 取消只能停止前端等待；FastAPI 同步线程中的 pandas/SQLite 计算不一定随断开终止。
- 因此必须先让每个搜索请求本身变轻，再把防抖、取消和索引作为配套能力。

## 3. 冻结的产品决策

### 3.1 信息架构不变

- 搜索继续是全局 utility，不增加第六个顶级导航。
- `/music/search` 继续是唯一完整查找页。
- 播放分析二级导航顺序不因本计划改变。
- 音乐详情页继续负责深入浏览，搜索结果不复制详情能力。

### 3.2 搜索范围

搜索文档只包含本地可访问的歌曲、专辑项目和艺人：

- 当前有效统计下存在播放，或已有可解析详情/榜单事实的实体；
- 歌曲以稳定 `track_id` 和当前合并语义为基础；
- 专辑以 album project identity + canonical artist 为主，缺少 project 时使用本地 album fallback；
- 艺人以 canonical artist identity 为主，别名只参与检索，不生成重复结果；
- 有效曲目署名参与歌曲的艺人检索文本与艺人归属，但不得重写原始表。

### 3.3 结果信息层级

第一阶段候选立即显示：

- 封面；
- 实体类型；
- 名称；
- 艺人/专辑等区分信息；
- 详情深链。

`match_field` / `match_type` 只用于内部排序、高亮、测试和诊断，不在消费界面展示“匹配艺人名称”、
“匹配别名”、“简繁匹配”或“近似匹配”等工程标签。名称、艺人和专辑文字必须跟随全局简繁体偏好，
但详情深链和本地保存值继续使用原始实体数据。

第二阶段渐进显示：

- 播放次数；
- `PK #`；
- 在榜周数；
- 走势排名。

继续不显示冠军周数、工程口径、缓存状态、过滤指纹或治理术语。没有榜单事实时只保留播放
次数，不增加噪声较高的“未入榜”标签。

### 3.4 Quick Open 与完整页职责

| 能力 | Quick Open | `/music/search` 全部 | 单类型页签 |
|---|---|---|---|
| 每类首批结果 | 最多 3 条 | 最多 5 条预览 | 每页 20 条 |
| 总数 | 显示分组数量或总数 | 显示每类准确总数 | 显示总数与页码 |
| 统计上下文 | 渐进补齐可见结果 | 渐进补齐可见结果 | 渐进补齐当前页 |
| 键盘导航 | 完整支持 | 标准 Tab/链接导航 | 标准 Tab/链接导航 |
| 分享 URL | “查看全部”进入页面 | `q` + `kind` | `q` + `kind` + `page` |
| 最近查看 | private 可显示 | private 可显示 | 不占用结果区 |

“全部”视图不一次挂载 60 条结果。它负责展示每类前 5 条和准确总数，每个分组提供
“查看全部 X 个”进入对应类型页签。

## 4. 目标架构

### 4.1 总体数据流

```text
用户输入
  -> 标准化 + IME 门禁 + 防抖
  -> GET /api/music/search?response_mode=candidates
       -> active music_search index generation
       -> exact semantic snapshot eligibility join
       -> 返回候选、total_by_kind、分页信息、entity_key、snapshot_status
  -> UI 立即渲染可点击结果
  -> GET /api/music/search/context?entity_key=...
       -> exact active semantic snapshot
       -> 返回播放次数与 chart 摘要，或 warming/unavailable
  -> UI 在预留区域渐进补齐上下文
```

后台派生链路：

```text
导入 / 设置 / 版本归并 / 艺人身份 / 曲目署名变化
  -> 标记 search documents 或 semantic snapshot dirty
  -> private maintenance / job queue 去重重建
  -> 新 generation/snapshot 完整验证
  -> 单事务切换 active pointer
  -> 清理旧 generation（保留一个可回滚版本）
```

### 4.2 分层职责

| 层 | 职责 | 禁止事项 |
|---|---|---|
| Search normalizer | Unicode、空白、标点、简繁体搜索变体 | 修改展示名称 |
| Search document builder | 从规范实体和别名生成派生文档 | 重写 `tracks`、`albums`、`artists` |
| Candidate repository | FTS/回退检索、精确资格 join、排序、分页、总数 | 加载 `plays` DataFrame |
| Context snapshot builder | 复用统计/榜单规范函数批量生成上下文 | 为每个候选逐行重新计算 |
| Context repository | 精确快照 lookup | 在 GET 请求中冷构建 |
| API facade | 参数校验、运行面策略、response model | 拼接任意 SQL |
| Frontend query layer | 候选/context 查询、取消、缓存与渐进状态 | 在组件内手写 fetch 状态机 |
| Presentation | Desktop/Phone 视觉、键盘与触控交互 | 改写统计事实 |

## 5. 搜索索引设计

### 5.1 派生表

通过 additive migration 创建以下派生结构，具体 migration 编号在实施时取当前下一个编号，
不得在规划阶段硬编码：

#### `music_search_index_state`

- `state_id = 1`
- `active_generation_id`
- `document_revision`
- `build_status`: `ready | pending | running | failed`
- `last_error`
- `updated_at`

#### `music_search_documents`

- `document_id`
- `generation_id`
- `entity_key`
- `kind`: `track | album | artist`
- `label`
- `secondary_text`
- `normalized_label`
- `normalized_secondary`
- `aliases_text`
- `track_id`
- `album_id`
- `album_project_id`
- `artist_id`
- `cover_type`
- `cover_entity_id`
- `href`
- `popularity_tiebreaker`
- generation 内唯一 `(entity_key)`

#### `music_search_fts`

- FTS5 虚拟表；
- 索引标准化名称、secondary text 和 aliases；
- `generation_id`、`kind`、`entity_key` 作为非检索过滤/关联字段；
- 当前本机 SQLite 3.51 已验证支持 FTS5 trigram；生产镜像必须通过运行时 doctor，
  不得只依据开发机能力下结论。

### 5.2 稳定实体键

| 类型 | 首选 entity key | fallback |
|---|---|---|
| 歌曲 | `track:{canonical_track_id}` | `track:{track_id}` |
| 专辑 | `album_project:{project_id}` | `album:{album_id}` |
| 艺人 | `artist:{canonical_artist_id}` | `artist:{artist_id}` |

`entity_key` 是搜索候选与上下文快照之间的唯一关联键。前端不得用 label、href 或数组位置
匹配上下文；专辑不得只用 `album_name` 匹配。

### 5.3 标准化规则

标准化只作用于检索文本，不改变消费界面的展示名称：

1. Unicode NFKC；
2. trim 并折叠连续空白；
3. Unicode-aware casefold；
4. 统一弯引号、直引号、连字符和全角标点的搜索变体；
5. 保留原文，同时生成简体、繁体搜索变体；
6. 将歌曲名称、有效艺人署名和专辑名称分字段索引；
7. 艺人 canonical name 与已批准 alias 同时索引；
8. 不从 genre、语言、歌词或外部常识生成搜索词。

前端只做最小且与后端共享测试向量的规范化，后端标准化是最终事实源。API response 返回
`normalized_query`，前端 TanStack key 使用同一结果或等价纯函数。

### 5.4 检索与排序

排序分层固定为：

1. 主名称完全匹配；
2. 主名称前缀匹配；
3. 主名称全部 token 匹配；
4. secondary/alias 完全或前缀匹配；
5. trigram 子串匹配；
6. 同层内使用 `popularity_tiebreaker`、规范名称和稳定实体键确定顺序。

个人播放热度只能作为同层 tie-breaker，不能让高播放但弱匹配结果压过准确名称。搜索排序不使用
Billboard peak 或 Power Score，以免过滤设置改变候选顺序和缓存键。

多字段示例：

- `cardigan taylor` 可匹配歌曲名 + 艺人名；
- `folklore taylor swift` 可匹配专辑名 + 艺人名；
- 艺人旧名或有效 alias 返回 canonical 艺人一条结果；
- 同名专辑通过 canonical artist 和封面区分。

### 5.5 短查询与 FTS fallback

- 拉丁/数字等单字符不请求远端候选，只展示初始状态；
- 两字符使用精确/前缀规范索引，不依赖 trigram；
- 中日韩文字允许单字符，但限制返回数量并优先主名称前缀；
- 三字符及以上使用 FTS5 trigram；
- 若生产 SQLite 缺少 FTS5/trigram，doctor 将状态标为 degraded，候选 repository 使用
  `normalized_label` 前缀索引 + 有界 substring fallback；
- fallback 不得重新聚合 `plays`，性能退化只能发生在候选匹配阶段。

### 5.6 构建与发布

- 在非 active `generation_id` 中完整构建文档与 FTS 行；
- 验证实体数、重复 entity key、空 label、无效 href 和随机抽样深链；
- 单事务更新 `active_generation_id`；
- 发布后保留上一代，下一次成功构建后再回收更早 generation；
- 构建失败保持上一 active generation，不暴露半成品；
- 文档索引是可重建数据，不进入原始数据备份的唯一事实层，但随 SQLite Online Backup 一并备份。

## 6. 精确上下文快照设计

### 6.1 快照内容

#### `music_search_snapshot_meta`

- `snapshot_key`
- 完整播放/Billboard 过滤指纹；
- 数据库播放 revision；
- track group revision；
- album project revision；
- artist identity revision；
- track credit revision；
- Billboard aggregation revision；
- `status`: `pending | running | ready | failed`；
- `created_at`、`activated_at`、`last_error`。

#### `music_search_entity_context`

- `snapshot_key`
- `entity_key`
- `play_events`
- `total_ms`
- `peak_position`
- `peak_weeks`
- `weeks_on_chart`
- `weeks_at_no1`
- `power_score`
- `power_rank`
- `first_week`
- `latest_week`
- `first_peak_week`
- 唯一 `(snapshot_key, entity_key)`。

UI 继续只消费允许展示的字段。保留 `weeks_at_no1` 等字段是为了与详情契约完整对照，不代表搜索
UI 恢复冠军周数展示。

### 6.2 过滤指纹

搜索上下文指纹至少包含：

- `min_ms`
- `music_only`
- `merge_enabled`
- `dynamic_threshold`
- `max_merge_gap_minutes`
- `merge_level`
- `bb_top_n`
- `bb_album_top_n`
- `bb_artist_top_n`
- `bb_week_start_dow`
- `bb_week_start_hour`
- `year_start`
- `year_end`
- 所有相关数据与元数据 revision

指纹生成复用现有统计上下文规范，不在搜索 service 内维护第二套默认值。

### 6.3 构建规则

- 一次构建批量生成全部可搜索实体的统计映射；
- 播放次数复用逻辑播放事件和详情统计的规范归属，不使用搜索候选 SQL 的原始 `COUNT(*)`；
- 歌曲使用规范 track identity；
- 专辑使用 album project membership + canonical artist；
- 艺人使用有效曲目署名 fan-out，再经 canonical artist 去重；
- chart 摘要优先复用 staged weekly、summary 和 power cache/预聚合，不调用完整 records payload；
- 构建完成后抽样与三类详情 API 对照，失败不得激活；
- 构建过程允许秒级，但不能运行在用户关键词 GET 请求内。

普通消费搜索的候选资格也来自该精确快照：Candidate repository 先完成名称匹配，再按当前
`snapshot_key` join context，只保留 `play_events > 0` 或存在可解析 chart 事实的实体，并按当前
merge level 折叠规范歌曲/专辑身份。这样候选层虽然不做实时统计，仍不会把当前详情资格之外的
随机实体当成可访问结果。搜索文档本身保持可重建；资格、规范 entity key 和准确总数由精确快照
决定。

当精确快照处于 `pending/running` 时，普通消费搜索必须返回明确 `warming` 状态，不得用 raw
candidate 或旧 snapshot 冒充当前事实。Settings 治理选择器可以使用私有的 `eligibility=any_local`
模式查找本地原始实体，但该模式不属于普通消费搜索，也不得在 `public-readonly` 开放。

### 6.4 重建协调

- 使用单一 job type，例如 `music_search_snapshot_rebuild`；
- exact snapshot key 去重，同一 key 只允许一个 queued/running 任务；
- 当前设置指纹优先；旧设置快照可按 LRU/数量上限清理；
- 导入维护在 Billboard 预聚合和 album project 完成后构建搜索快照；
- 设置 mutation 先保存设置并标记新指纹 pending，再异步构建；
- 私人运行面若请求精确快照但状态 pending，只返回 `warming`，不得同步等待；
- 公共运行面只读取 `ready` 精确快照，不能排队、构建或降级到昂贵实时统计。

### 6.5 失效矩阵

| 变化来源 | 候选文档 | 播放上下文 | Billboard 上下文 |
|---|---:|---:|---:|
| Streaming History 导入 | 重建 | 重建 | 重建 |
| Spotify 元数据补全 | 可能重建 | 不一定 | 封面/identity 变化时重建 |
| `min_ms` / dynamic threshold / gap | 不变 | 重建 | 重建 |
| Billboard 周边界 / Top N | 不变 | 不变 | 重建 |
| L1/L2/L3 版本归并 | 可能重建 | 重建 | 重建 |
| album project 重建 | 专辑文档重建 | 专辑重建 | 专辑重建 |
| 艺人身份 mutation | 艺人/相关歌曲重建 | 艺人重建 | 艺人重建 |
| 曲目署名 mutation | 歌曲 secondary 与艺人文档重建 | 艺人重建 | 艺人重建 |
| 简繁体显示偏好 | 不变 | 不变 | 不变 |
| 主题偏好 | 不变 | 不变 | 不变 |

每个 mutation 只能调用一个集中式 `mark_music_search_derived_data_dirty()` 或等价编排入口，
不能由各 API 自行拼失效逻辑。

## 7. API 契约

### 7.1 候选接口

保留：

```http
GET /api/music/search
```

新增参数：

- `response_mode=candidates|legacy`
- `eligibility=current|any_local`，默认 `current`；`any_local` 仅 private 管理消费者可用
- `q`
- `kind=track|album|artist`
- `limit_per_type`
- `page`
- `page_size`

过渡规则：

- 实施期默认 `legacy`，确保旧前端和 Settings 消费者不被后端先行部署破坏；
- 新 UI 显式请求 `response_mode=candidates`；
- `eligibility=current` 使用 PlayFilters、BillboardFilters、MergeConfig 解析出的精确快照资格；
- `eligibility=any_local` 不返回消费统计，只供获得 private capability 的 Settings 治理选择器使用；
- `include_chart` 仅在 legacy 模式兼容，记录弃用但本计划同一交付不删除；
- 所有内部消费者迁移后，是否变更默认值必须单独提升 API contract version，不在本计划暗改。

候选响应示意：

```json
{
  "response_version": "music_search_v2",
  "query": "taylor",
  "normalized_query": "taylor",
  "snapshot_status": "ready",
  "filter_fingerprint": "...",
  "kind": null,
  "page": 1,
  "page_size": 5,
  "total": 24,
  "total_by_kind": {
    "track": 12,
    "album": 4,
    "artist": 8
  },
  "tracks": [],
  "albums": [],
  "artists": []
}
```

候选行新增：

- `entity_key`
- `match_field`: `label | artist | album | alias`
- `match_quality`: `exact | prefix | token | substring`

`match_quality` 只用于稳定渲染/调试，不向普通消费 UI显示工程术语。

### 7.2 上下文接口

新增显式只读 GET：

```http
GET /api/music/search/context?entity_key=track:123&entity_key=artist:45
```

规则：

- 最多 30 个 entity key；
- 去重并保持响应按 key 映射；
- 使用完整 PlayFilters、BillboardFilters、MergeConfig；
- 只读取精确 `ready` snapshot；
- 返回 `ready | warming | unavailable | stale`；
- `stale` 数据不冒充当前事实；若 candidate 与 context 指纹不一致，UI 使当前候选进入更新态并
  重新请求候选，不能把旧 context 附着到新实体；
- 不接受任意 SQL、名称匹配或 href；只接受合法稳定 key。

响应示意：

```json
{
  "response_version": "music_search_context_v1",
  "snapshot_status": "ready",
  "filter_fingerprint": "...",
  "items": {
    "track:123": {
      "play_events": 280,
      "total_ms": 50200123,
      "chart": {
        "peak_position": 1,
        "weeks_on_chart": 12,
        "power_rank": 8
      }
    }
  }
}
```

### 7.3 错误与降级

| 场景 | 候选接口 | 上下文接口 | UI |
|---|---|---|---|
| 空 query | 200 空集合 | 不调用 | 初始建议状态 |
| 索引 missing | 有界 resolver fallback | 不受影响 | 正常候选，记录 degraded |
| 索引 failed | 上一 active generation | 不受影响 | 无工程错误文案 |
| snapshot warming | 200 `warming`，不返回未经证明的消费候选 | 200 `warming` | 显示“音乐资料正在更新”，不伪装为空结果 |
| snapshot failed/unavailable | 200 `unavailable`，不返回未经证明的消费候选 | 200 `unavailable` | 显示暂不可用状态和轻量重试 |
| 非法 entity key | 不适用 | 422 | 不重试 |
| 网络失败 | 保留已有结果 | 保留已有候选 | 行内错误，不清空输入 |

### 7.4 公开只读运行面

- `/api/music/search` 已在公开 GET 白名单中；新 `/api/music/search/context` 必须经过显式安全评审后
  加入白名单，不能依赖路径前缀自动开放；
- 两个接口都只能返回本地结构化音乐实体和统计；
- public 只允许 `eligibility=current`，拒绝 private `any_local` 管理模式；
- 公共请求使用 `mode=ro` + `PRAGMA query_only=ON`；
- 公共搜索不得写 `background_jobs`、snapshot state、search history 或封面 metadata；
- 公共搜索不得触发外部封面补全。结果封面只使用已存在本地/数据库 URL，缺失时前端占位；
- snapshot 不精确时只返回 `unavailable`，不触发后台构建；
- 不把 imported Spotify 搜索历史或 private 最近查看下发到公共运行面。

## 8. 前端查询与状态架构

### 8.1 Query hooks

将搜索数据逻辑从通用 `useAnalysis.ts` 收口到搜索 feature：

- `useMusicSearchCandidates()`
- `useMusicSearchContext()`
- `musicSearchApi.searchCandidates()`
- `musicSearchApi.getContext()`

为了兼容 Settings 现有引用，`useAnalysis.ts` 可暂时 re-export，所有新代码直接使用 feature hook。

Query key：

```text
['music', 'search', 'candidates', semanticFilterKey, normalizedQuery, kind, page, pageSize]
['music', 'search', 'context', filterFingerprint, sortedEntityKeys]
```

搜索文档索引不因普通关键词查询重建，但普通消费候选必须按当前完整语义资格筛选，因此 candidate
query key 包含由当前播放/Billboard 设置生成的 `semanticFilterKey`。服务端仍以包含数据 revision
的完整 `filter_fingerprint` 为最终事实；导入和治理 mutation 必须集中失效 `queryKeys.music.all`。
上下文 key 包含服务端返回的完整过滤指纹与排序后的 entity keys。

### 8.2 请求行为

- `queryFn` 接收 TanStack `signal` 并传给 `api.get()`；
- 搜索候选 `retry: 0`；仅明确的瞬时网络错误允许用户手动重试；
- 初次候选显示轻量 skeleton；后续关键词变化用 `placeholderData/keepPreviousData` 保留布局，
  同时显示低干扰“正在更新”；
- 上下文加载不覆盖候选 loading 状态；
- 新候选集合返回时，只保留 entity key 仍存在的旧上下文；
- 关闭 Quick Open 后取消未使用 query observer，不主动清空可复用缓存；
- 搜索候选建议使用较短 `gcTime`，上下文快照使用与数据 revision 一致的较长 `staleTime`；
- 导入、设置、版本归并和 metadata mutation 继续按 `queryKeys.music.all` 集中失效。

### 8.3 输入状态

- Quick Open 与完整页共用 search input controller；
- Desktop 防抖目标 180–250ms，实际值在 M0 交互测试后冻结；
- `compositionstart` 到 `compositionend` 之间不请求、不改 URL；
- URL 只写 trim 后原始显示 query，查询 key 使用 normalized query；
- 完整页继续使用 `replace` 更新输入产生的 URL，避免每个字符污染浏览器历史；
- 点击类型和分页更新 URL；返回详情后恢复 query、kind、page 与滚动位置；
- 从 Phone Top Bar 明确点击搜索进入时聚焦并打开键盘；从详情返回时恢复焦点位置但不自动重开键盘。

### 8.4 过时请求与竞态

必须有自动化测试覆盖：

1. 输入 `tay` 发出请求 A；
2. 输入 `taylor` 取消 A 并发出 B；
3. 即使 A 最后返回，UI 也不能覆盖 B；
4. A 的取消不展示网络错误；
5. context A 不能附着到 candidates B 的同数组位置，只能按 entity key 匹配。

## 9. 体验设计

### 9.1 Desktop/Compact Quick Open

- 搜索图标保留原位置；
- 增加 `⌘K` / `Ctrl+K` 全局快捷键，输入框或可编辑区域获得焦点时不劫持普通按键；
- 打开后聚焦输入；关闭后恢复到触发按钮；
- 默认不选中第一条结果；
- `ArrowDown/ArrowUp` 首次使用后才激活结果；
- `Enter` 只在存在 active result 时打开详情；否则保持输入；
- `Escape` 关闭；Tab 遵循 dialog focus trap；
- 最多 9 条候选（每类 3 条），空分组不显示；
- 底部“查看全部结果”保留当前 query；
- 候选出现后上下文渐进填入，不显示全屏“匹配榜单信息”的阻塞 loading。

### 9.2 完整查找页

全部视图：

- 每类前 5 条；
- 分组标题显示准确总数；
- 每组底部“查看全部 X 个”；
- 不显示三组空容器；
- 全部为空时提供更具体的改写建议。

单类型视图：

- 每页 20 条；
- URL 为 `?q=...&kind=track&page=2`；
- 搜索词或类型变化时 page 回到 1；
- 显示结果范围，例如“21–40 / 128”；
- 上一页、下一页和页码控件满足 44×44px；
- 页面切换保留旧页直到新页就绪，避免整页闪烁。

### 9.3 Phone presentation

- 继续使用独立 Phone presentation 和 Push Top Bar，不挂载 Desktop dialog；
- 无 query 时保留紧凑页面标题；有 query 时首屏优先吸附搜索和类型切换；
- 类型切换为 44px 触控目标，允许有意的 chip 横向滚动但不得产生页面级溢出；
- 结果继续使用 `MobileEntityRow`，上下文使用固定高度 facts/badges 区域；
- 完整页分页不得使用宽表或密集页码，使用“上一页 / 第 N 页 / 下一页”；
- 360/390/430px 下名称、secondary 和 badge 不造成横向滚动；
- 键盘出现时使用 `100dvh`/visual viewport，底部内容不被系统键盘遮挡。

### 9.4 初始状态与最近查看

`private-admin` 可以显示应用内最近打开的音乐实体：

- 最多 6 条；
- 只存稳定 entity key、label、kind、href 和本地时间；
- 优先使用前端本地存储，不写入服务端搜索历史；
- 导入/身份变化后无法解析的实体静默移除；
- 提供清除操作。

`public-readonly` 不展示 private 最近查看，也不读取 imported Spotify 搜索历史；初始状态只显示
搜索范围说明或公开安全的固定引导。

### 9.5 匹配解释与高亮

- 名称中安全高亮匹配片段，不使用 `dangerouslySetInnerHTML`；
- 如果歌曲因艺人或专辑字段命中，secondary text 显示自然语言区分信息；
- 不向普通用户显示 `exact/prefix/token/trigram` 等工程标签；
- 同名实体必须依靠 canonical artist、专辑或封面区分，不能只显示重复 label。

### 9.6 可访问性

- Quick Open 使用可访问 dialog + combobox/listbox 关系或等价 APG 模式；
- 输入框提供 `aria-controls`、结果数量 live region 和 active descendant；
- loading live region 只在状态变化时播报一次；
- 上下文渐进补齐不重复朗读整行；
- 所有封面保留实体化 alt，装饰 icon 隐藏；
- focus ring、暗色对比度、reduced motion 和 200% zoom 通过验收；
- 关闭 dialog、打开详情再返回时焦点恢复可预测。

## 10. 性能预算与可观察性

### 10.1 服务端预算

以下预算以当前真实数据库量级和个人云单用户部署为基线：

| 指标 | 目标 |
|---|---:|
| 候选 repository 热查询 P50 | ≤50ms |
| 候选 API 热查询 P95 | ≤150ms |
| 候选 API 冷连接 P95 | ≤400ms |
| 30 个 entity context 精确快照 lookup P95 | ≤100ms |
| Quick Open 首批可点击结果 P95 | ≤400ms |
| 已缓存 query 重新打开可见结果 | ≤100ms |

预算门禁还包括：

- 候选 query plan 不扫描/聚合 `plays`；
- context query plan 只访问 snapshot meta/context 索引；
- 任何搜索 GET 不触发 snapshot build；
- 单次候选响应建议控制在 50KB 以内；
- Quick Open 最多请求 9 张可见封面，继续 lazy decoding；
- 搜索交互区域新增 CLS 目标 ≤0.02。

预算若因 CI 硬件差异无法使用绝对值，应在本地真实数据 probe 使用绝对预算，CI 使用“不得访问
plays/不得调用重计算函数”和相对基线双门禁，避免脆弱的毫秒测试。

### 10.2 Server-Timing

候选响应至少记录：

- `normalize`
- `candidate_query`
- `serialize`
- `total`

上下文响应至少记录：

- `fingerprint`
- `snapshot_lookup`
- `serialize`
- `total`

日志只记录 request id、query 长度、kind、结果数、索引 generation、snapshot 状态和耗时。默认不记录
原始搜索词，避免把个人搜索意图复制到服务端日志。

### 10.3 性能探针

新增 `scripts/music_search_performance_probe.py`：

- 默认以 `mode=ro` 打开数据库；
- 支持 candidate/context/end-to-end；
- 支持 cold process 与 warm repeat；
- 使用固定非敏感 query 集合或调用者显式传入 query；
- 输出 JSON 和人类可读表格；
- 记录数据库大小、plays/tracks/albums/artists 数量、SQLite 版本和 FTS 能力；
- 支持预算参数，超预算退出非零；
- 不打印真实完整结果或用户原始历史。

## 11. 实施阶段

### M0：契约冻结与基准固化

目标：在改代码前固定“快什么、准什么、不能做什么”。

任务：

- 建立只读性能 probe，复现本计划基线；
- 增加当前搜索调用链的分段计时；
- 冻结 `entity_key`、candidate response、context response 和状态枚举；
- 建立 query 标准化测试向量；
- 建立三类详情一致性 golden cases；
- 确认生产 Docker SQLite FTS5/trigram 能力；
- 记录公开运行面安全评审结论。

门禁：

- probe 可在真实 DB 和 seed DB 重复运行；
- 基准结果附机器、数据量和冷/热条件；
- API schema 评审通过后才进入 M1。

粗略工作量：0.5–1.5 个开发日。

### M1：候选与上下文解耦

目标：在还未建立 FTS 和持久快照前，先消除首屏 8–20s 阻塞。

任务：

- 为 `/api/music/search` 增加显式 candidate 模式；
- candidate 模式禁止加载过滤后 lifetime frames 和完整 Billboard；
- 增加 `/api/music/search/context` schema，但初期可以返回缓存已有/`warming`；
- 前端拆为 candidates/context 两个 hook；
- 传递 AbortSignal，关闭搜索请求的自动重试；
- 初次 skeleton、后续 keep-previous-data；
- Quick Open 与完整页改为候选先显示、上下文渐进补齐；
- Settings 中复用搜索的消费者显式选择 candidate + private `any_local` 模式；
- M1 可以完成内部链路与体感验证，但普通消费搜索不得在缺少 M3 精确资格快照时作为生产默认切换。

门禁：

- candidate service 测试通过 monkeypatch 保证不会调用 `load_period_plays()` 和
  `compute_billboard_data()`；
- 当前真实 DB candidate end-to-end P95 ≤400ms；
- 旧 legacy 合同继续通过；
- 搜索结果先出现时已经可点击，不等待 context。

粗略工作量：1.5–3 个开发日。

### M2：持久搜索索引与相关性

目标：将候选查询从通用 AI resolver 收口为专用、稳定、可分页的搜索 repository。

任务：

- additive migration 创建 generation state、documents 与 FTS；
- 实现 normalizer、document builder、FTS doctor 与 fallback；
- 接入 canonical artist、album project 和有效署名；
- 实现 exact/prefix/token/secondary/trigram 排序；
- 实现 `total_by_kind`、全部视图预览和单类型分页；
- 增加重建 CLI 与导入维护接入；
- 增加 active generation 原子发布与上一代回滚。

门禁：

- 实际候选 API 热 P95 ≤150ms；
- query plan 不访问 `plays`；
- 同名专辑、艺人 alias、合作署名和 album project 用例通过；
- FTS unavailable fallback 合同通过；
- 构建失败仍可查询上一代。

粗略工作量：2–4 个开发日。

### M3：精确统计与 Billboard 快照

目标：让上下文重新具备完整详情一致性，同时保持 lookup 级延迟。

任务：

- 创建 snapshot meta/context 派生表；
- 实现完整过滤指纹和 revision；
- 批量构建三类播放统计；
- 从 staged/preaggregated Billboard 结果生成轻量 chart context；
- 接入 job queue exact-key 去重；
- 接入 import maintenance、settings、version merge、artist identity 和 track credits 失效；
- public GET 实现 exact-ready-only；
- 增加快照健康状态与管理探针，不新增普通消费 UI 治理术语。

门禁：

- 30 个实体 lookup P95 ≤100ms；
- 三类搜索 context 与详情 API 在 L1/L2/L3、动态阈值、gap、榜单周边界代表矩阵中一致；
- 搜索 GET 期间 job queue 无新增任务；
- pending/failed snapshot 不阻塞候选；
- public-readonly 的数据库 total changes、job 数量和外部 provider 调用均不变化。

粗略工作量：3–5 个开发日。

### M4：完整页、键盘、Phone 与体验收口

目标：解决“有搜索但不够像完整查找工具”的体验缺口。

任务：

- Quick Open 每类 3 条和 `⌘K/Ctrl+K`；
- 完整页准确总数、每类 5 条预览和单类型 20 条分页；
- IME、焦点 trap/restore、live region、active descendant；
- 匹配片段安全高亮和 secondary match 解释；
- private 最近查看与 public capability 隔离；
- Phone sticky controls、分页、键盘视口和返回状态恢复；
- 保留默认不预选第一条结果。

门禁：

- 键盘、鼠标、触控均可完成查询和打开详情；
- 旧请求晚返回不覆盖新 query；
- “查看全部”与真实总数一致；
- 360/390/430/768/1280 0px 页面级横向溢出；
- Chromium/Firefox/WebKit 交互 smoke 通过。

粗略工作量：2–3 个开发日。

### M5：生产发布、回滚与文档收口

目标：将搜索优化作为可回滚的生产变更交付，而不是只通过本地测试。

任务：

- 部署前 Online Backup；
- 在 private/full 中构建并验证 active search generation/snapshot；
- showcase/dual 发布前检查 exact snapshot ready；
- 执行 full/showcase/dual 三模式门禁；
- 对比发布前后冷/热基准、HTTP timing、数据库完整性和公共副作用；
- 演练回滚旧 commit SHA：旧代码忽略 additive 派生表，旧 `/api/music/search` legacy 仍工作；
- 更新 README、AGENTS、CLAUDE、docs/CHANGELOG 与交付报告；
- 只有用户明确要求时才提交 Git。

门禁：

- 同一 commit SHA 的两个 Web 运行面搜索结果一致；
- public 无写入、无外部请求、无后台构建；
- 真实浏览器 Quick Open 与 Phone 页面达到预算；
- 回滚后旧搜索仍可用，数据库无需 destructive downgrade。

粗略工作量：1–2 个开发日。

总工作量预估：单人约 10–18 个开发日。该估算不包含发现统计口径缺陷后的额外修复，实施时应按
M0–M5 独立验收，不把总工期当作跳过阶段门禁的理由。

## 12. 文件与模块地图

### 12.1 后端预计新增

- `backend/domains/music_search/__init__.py`
- `backend/domains/music_search/normalization.py`
- `backend/domains/music_search/documents.py`
- `backend/domains/music_search/repository.py`
- `backend/domains/music_search/context_snapshot.py`
- `backend/domains/music_search/rebuild.py`
- `scripts/rebuild_music_search_derived_data.py`
- `scripts/music_search_performance_probe.py`
- 对应 unit/contract/integration tests

### 12.2 后端预计修改

- `backend/api/music.py`
- `backend/models/music_search.py`
- `backend/services/music_search_service.py`：最终成为兼容 facade，不继续堆积查询实现
- `backend/core/migrations.py`
- `backend/core/access_surface.py`
- `backend/core/cache_manager.py`
- `backend/services/import_maintenance_service.py`
- Settings、version merge、artist identity、track credits 的集中失效调用点
- `scripts/api_smoke_probe.py`
- `scripts/phase5_check.sh`

### 12.3 前端预计新增/收口

- `frontend/src/features/music/search/api.ts`
- `frontend/src/features/music/search/useMusicSearch.ts`
- `frontend/src/features/music/search/searchInputController.ts`
- 搜索 response/context 类型与状态组件

### 12.4 前端预计修改

- `frontend/src/features/music/search/MusicSearchDialog.tsx`
- `frontend/src/features/music/search/MusicSearchPage.tsx`
- `frontend/src/features/music/search/MusicSearchResults.tsx`
- `frontend/src/features/music/search/musicSearchUtils.ts`
- `frontend/src/hooks/useAnalysis.ts`：兼容 re-export
- `frontend/src/api/query-keys.ts`
- `frontend/src/components/layout/Masthead.tsx`
- `frontend/src/components/layout/MobileTopBar.tsx`
- 搜索、移动 Shell、route context、query hook 和 public surface tests

模块拆分应遵守 Phase 5 route container 和 feature 边界，不因为搜索优化将所有逻辑继续集中到一个
service 或一个 React 组件。

## 13. 验证矩阵

### 13.1 后端 unit

- 标准化：Unicode、大小写、空白、弯引号、连字符、简繁体；
- 排序：exact、prefix、token、secondary、alias、稳定 tie-break；
- entity key：track group、album project、canonical artist、fallback；
- FTS doctor 与 fallback；
- generation 原子发布和失败保留旧代；
- snapshot fingerprint、dedupe、pending/ready/failed；
- GET 请求不调用 rebuild；
- context 最多 30 key、非法 key 和去重。

### 13.2 后端 contract

- legacy `/api/music/search` 兼容；
- candidate V2 response model、total_by_kind、分页；
- context ready/warming/unavailable；
- 搜索播放次数与三类 stats detail 一致；
- 搜索 chart 与三类 Billboard detail 一致；
- `dynamic_threshold`、gap、L1/L2/L3、Top N、周边界；
- public allowlist、query-only、零写入、零 provider；
- OpenAPI 与生成类型更新。

### 13.3 数据与迁移

- 空 DB、seed DB、真实旧 DB migration；
- migration 幂等；
- FTS 重建后文档数与规范实体数对账；
- 重复 entity key、空 label、无效 deep link 为 0；
- import maintenance success/partial/error 报告包含搜索派生状态；
- snapshot build 中断后旧 active 仍可读；
- Online Backup 和 restore 后 FTS/context 可用。

### 13.4 前端 unit/integration

- candidates/context 独立状态；
- context 渐进补齐和固定布局；
- AbortSignal、取消错误不展示、竞态不串线；
- IME composition；
- Quick Open 默认无 active result；
- Arrow/Enter/Escape/Tab；
- `⌘K/Ctrl+K` 与 editable target 排除；
- 准确总数、类型页、分页 URL；
- 最近查看 private-only；
- context unavailable 时候选仍可用。

### 13.5 浏览器与可视验收

- 360/390/430/768/1024/1280；
- 日间/夜间；
- Chromium/Firefox/WebKit；
- 中文输入法、英文快速输入、复制粘贴、清空；
- 长名称、同名专辑、缺封面、无 chart、大数字；
- 慢速网络、offline、context warming；
- 200% zoom、reduced motion、键盘-only；
- Quick Open 关闭焦点恢复、详情返回状态恢复；
- public/full/dual 三运行面。

### 13.6 性能验收命令目标

实施时将最终命令固化到 probe 和文档，至少包含：

```bash
.venv/bin/python scripts/music_search_performance_probe.py --mode candidate --cold --json-output /tmp/music-search-candidate.json
.venv/bin/python scripts/music_search_performance_probe.py --mode context --warm-repeat 10 --json-output /tmp/music-search-context.json
.venv/bin/pytest backend/tests/unit/test_music_search_*.py -q
.venv/bin/pytest backend/tests/contract/test_music_search_*.py -q
cd frontend && npm test -- --run src/tests/music-search-components.test.tsx src/tests/music-search-flow.test.tsx src/tests/query-hooks.test.tsx
cd frontend && npm run build
```

最终实际文件名以实施为准；规划中的命令不得在对应脚本尚未落地时写成“已通过”。

## 14. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 搜索快照与详情口径漂移 | 构建器复用规范函数；三类详情 contract 对照；指纹纳入所有 revision |
| album 同名/版本归属错误 | entity key 使用 album project + canonical artist，不按名称关联 context |
| 艺人 alias 重复 | 文档生成阶段 canonicalize，alias 只进检索字段 |
| FTS 在生产不可用 | 发布前 doctor；前缀索引 + 有界 substring fallback |
| rebuild 与在线读冲突 | generation/snapshot 非 active 构建，单事务切换 pointer |
| public 搜索触发副作用 | exact-ready-only、query-only、job/provider spy contract |
| HTTP 取消未终止后端线程 | 不把取消当性能核心；先保证请求本身轻量 |
| 快照状态长期 pending | maintenance health、last_error、显式 rebuild CLI、上一 active 保底 |
| 搜索 query 泄漏日志 | 默认只记长度、hash/类别和耗时，不记录原始文本 |
| 前端旧 context 串到新结果 | 只按 entity key 合并，不按 index/label/href |
| 派生表增加数据库体积 | 记录 generation 数量上限，仅保留 active + 上一代 |
| 回滚旧 SHA 不识别新表 | additive migration；旧代码忽略派生表；保留 legacy API |

## 15. 发布与回滚

### 15.1 发布顺序

1. 备份主 SQLite 并记录 commit SHA、部署模式和现有搜索基准；
2. 应用 additive migration；
3. private maintenance 构建 search documents 与当前精确 context snapshot；
4. 验证数据对账、性能和三类详情一致性；
5. 启动目标 full/showcase/dual 模式；
6. 执行公共白名单、query-only、封面无外部补全和浏览器门禁；
7. 记录发布后冷/热结果与 active generation/snapshot key。

### 15.2 回滚

- 代码回滚使用上一 commit SHA 和原部署模式作为一个单元；
- SQLite 不做 destructive downgrade，新派生表由旧代码忽略；
- legacy `/api/music/search` 在弃用期保留，旧前端仍可工作；
- 新 generation 出错时只切换 active pointer 到上一代，不删除当前原始数据；
- 若上下文快照异常，前端可以只显示候选，不能把错误快照冒充当前事实；
- 回滚后重新执行旧搜索 smoke、数据库 integrity check 与公共只读门禁。

## 16. 后续可选能力

以下首项已由后续方向实现，其余能力仍不属于本计划完成门禁：

- [x] 有界拼写纠错、确定性简繁体扩展与短 CJK fallback；
- 拼音/罗马字检索；
- 搜索结果快捷预览面板；
- 系统级 Spotlight/快捷指令集成；
- 本地最近搜索跨设备同步；
- 统一搜索歌曲、专辑、艺人之外的播放记录或社区内容。

任何扩展都不得让音乐实体搜索重新依赖 LLM、外部服务或同步全量统计计算。

## 17. 规划验收清单

- [x] M0 基准、契约和 FTS runtime 能力已冻结
- [x] M1 候选与 context 解耦，首批结果不再等待统计
- [x] M2 持久搜索索引、相关性、总数与分页完成
- [x] M3 精确统计/Billboard 快照、六变体覆盖、失效矩阵和 public cache-only 完成
- [x] M4 Desktop/Compact/Phone、键盘、IME、焦点与最近查看完成
- [x] M5 三模式本地生产门禁、真实浏览器、全部性能向量、回滚和文档收口完成
- [x] 旧入口归属、详情深链、默认不预选和搜索 badge 展示规则未回归
- [x] remediation plan 的阻断项已修复并由新证据证明，不再提前声明 Pass

后续方向已按
[`2026-08-16-music-search-direction-realignment.md`](2026-08-16-music-search-direction-realignment.md)
完成：候选版本与统计 fingerprint 解耦，简繁、短 CJK 和有限模糊匹配已上线；镜像改经私有 CAS
Artifact 将缺失 blob 续传到现有服务器，再由服务器推送 TCR。一次性旧库统计引导后，正常 production
workflow `31977767545` 首次成功；最终 workflow `31979057642` 在 9 分 57 秒内完成，搜索预检精确
复用六变体且仅耗时 2 秒，生产精确/模糊/简繁/短 CJK 语义门禁全绿，远程状态不再 Blocked。
