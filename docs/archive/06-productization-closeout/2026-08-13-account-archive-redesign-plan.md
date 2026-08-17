# 账号中心重构方案：从“人格橱窗”到“个人音乐档案”

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

> 日期：2026-08-13
> 状态：已完成；本地统计、Desktop / Compact / Phone 音乐档案、旧链路退役与文档收口均已交付
> 范围：`/account` 的产品定位、统计语义、内容架构、Desktop / Compact / Phone UI、API 契约、性能、隐私与迁移计划
> 原调研轮次不包含页面代码、数据库迁移、导航改名和生产部署；后续实施进度按下方交付记录更新

实施证据见：

- `../../reports/2026-08-13-account-archive-phase-0-delivery.md`
- `../../reports/2026-08-13-account-archive-journey-cohorts-delivery.md`
- `../../reports/2026-08-13-account-archive-desktop-delivery.md`
- `../../reports/2026-08-13-account-archive-phone-delivery.md`
- `../../reports/2026-08-13-account-archive-phase-4-delivery.md`
- `../../reference/account-archive-statistics.md`

## 1. 结论先行

这一页有继续存在的价值，但不应继续作为传统“账号中心”，也不应继续用弱证据给用户贴人格标签。

本方案将它重构为 **“音乐档案”**，回答一个其他页面没有回答的问题：

> **我的音乐怎样从一次发现，变成收藏、习惯与长期记忆？**

最终产品决策如下：

1. 保留路由 `/account`，避免破坏已有深链、测试和 AI 工具调用。
2. 页面内容标题与二级导航统一使用“音乐档案”，路由继续保留 `/account`。
3. 页面核心只使用本地已导入的播放、收藏、歌单和搜索数据；Spotify OAuth 只作为可选的数据补全能力，不作为打开页面或计算核心指标的前提。
4. 删除收藏人格、习惯人格、粉丝等级、Marquee 转化、歌曲标题关键词迁移、估算收藏总时长等不可靠模块。
5. 新页面围绕“档案概览 → 收藏旅程 → 收藏后的关系 → 发现路径 → 找回音乐 → 收藏库 → 音乐之外”组织。
6. Desktop / Compact / Phone 共享统计事实、查询状态和 URL；Phone 使用独立的“口袋音乐档案”展示，不缩放桌面图表。
7. 不复制播放统计、播放排行、个人 Billboard 和年度总结已经承担的内容，只提供必要的事实引用和深链。

## 2. 调研方法与证据范围

本方案采用三条证据链交叉验证：

- **本地事实审计**：检查当前页面组件、API、导入器、SQLite schema、真实聚合数量、响应体和冷热性能。
- **竞品比较**：比较 Spotify Wrapped / Listening Stats、stats.fm、Last.fm Reports、Receiptify、volt.fm、Apple Music Replay、Airbuds 等产品的内容边界、时间模型、UI 和隐私模式。
- **统计方法核验**：核对多样性、集中度、探索—重复、固定观察窗回访、右删失、口味迁移、搜索行为与跨内容比较方法。

竞品和方法只用于帮助定义产品模式，不能替代本地数据是否真的支持某项结论。产品中的每条动态文案最终都必须能追溯到确定性指标和合格样本。

## 3. 当前页面审计

### 3.1 当前页面到底是什么

现有 `/account` 同时承载了四类职责：

- Spotify 账号身份：头像、名称、地区、关注关系；
- 收藏档案：收藏量、收藏时间线、生命周期、收藏列表和歌单；
- 行为分析：搜索时段、播客、视频、艺人分层；
- 平台侧资料：Marquee、Inferences、Sound Capsule。

这造成了两个直接问题。第一，“账号中心”这个名称让用户预期看到登录、授权、资料和安全设置，但这些实际在 Settings；第二，收藏与行为分析又被两张大型人格卡统领，使可靠事实反而埋在页面下方。

旧内容顺序曾由 `frontend/src/pages/account/CollectionTab.tsx` 和 `frontend/src/features/account/habits/HabitsTab.tsx` 承载。Phase 4 已在核清消费者后删除整套旧页面树；当前 `/account` 的 Desktop / Compact 与 Phone 只进入独立档案 presentation。

### 3.2 本地数据能力

以下数字来自 2026-08-13 对 `data/spotify_stats.db` 的只读核验，不展示任何原始搜索词、身份字段或实体名称。

| 数据域 | 当前规模与覆盖 | 可支持的内容 | 主要限制 |
|---|---|---|---|
| 播放历史 | 91,286 条原始事件，2022-07-01—2026-07-24 | 收藏前后关系、回访、回归、搜索后的播放 | 页面指标必须复用全局有效播放、连续同曲合并和实体归并口径 |
| 收藏歌曲 | 800 首，全部有 `added_date`；762 首可按 URI 对上本地曲目，匹配率 95.3% | 收藏时间线、准确总时长、固定窗回访、收藏—播放矩阵 | 当前只有“导出时仍在收藏”的快照，没有取消收藏历史；38 首 URI 未匹配 |
| 收藏专辑 / 艺人 | 250 张 / 59 位 | 档案规模、收藏库浏览 | 专辑 ID 精确匹配差，需复用 album project + canonical artist 归属 |
| 歌单 | 27 个、681 条成员记录，本地关联率约 91.0% | 歌单浏览、歌单重叠、整理轨迹 | 不应在本页复制播放排行 |
| 搜索 | 2,239 条、1,025 个规范化查询，2026-02-19—2026-05-18 | 搜索量、活跃日、时段、查询 burst、有限的交互链路 | 只有 85 条带 interaction URI，覆盖率 3.8%；不能稳定推断“搜索精准度”或人格 |
| 播客 | 125 条原始记录；51 条达到 30 秒，18.3 小时、6 个节目 | 轻量节目档案、时长、回访 | 没有 episode duration，不能计算完播率 |
| 视频 | 957 条原始事件；只有 31 条达到 30 秒 | 只适合展示少量档案事实 | 样本太少，不适合趋势和“多媒体人格” |
| Marquee | 767 条、763 位艺人 | 只能作为平台数据透明度材料 | 没有曝光时间，无法建立曝光后的播放或因果转化 |
| Inferences | 423 条平台推断 | 可在主动展开的隐私透明度界面解释 Spotify 保存了什么 | 不是经用户验证的真实人格，不能用于消费侧画像 |
| Sound Capsule | 28 条 highlight、3 天 daily stats | 当前不进入主页面 | 导出 schema 已漂移，现有导入只保留极少可用实体 |

额外核验结果：收藏曲目元数据的真实时长覆盖为 800/800，实际总时长约 54.3 小时；当前页面使用 `收藏数 × 3.5 分钟` 得到约 46.7 小时，应直接退役该估算。

### 3.3 当前统计为什么不可信

问题不只是文案夸张，而是底层窗口和分母存在系统性错误。

#### A. 收藏主查询

重构前 `backend/services/account_service.py` 的 `get_collection_insights()` 存在以下问题；该服务现已在 Phase 4 删除：

1. `LEFT JOIN` 后使用 `COUNT(*)` 作为总播放数，未匹配播放的收藏也可能被计为 1 次。
2. 使用日粒度 `p.ts_date` 与带具体时间的 `added_date` 比较，同一天的播放会被错误分到收藏前或收藏后。
3. 以 `track_name + artist_name` 聚合，而不是稳定 URI / canonical track identity；800 首收藏会被折叠成约 797 组。
4. “冷却期 1–12 周”实际使用 30–90 天，7–30 天完全缺失。
5. “一年后命运”把尚未经历完整一年观察窗的近期收藏也放进分母，没有处理右删失。
6. “厚积薄发”比较前 6 个月与无限长后续历史；“细水长流”比较累计收藏前历史与收藏后 6 个月，观察长度不相等。
7. “收藏夹吃灰”的文案说收藏后播放，代码却使用包含收藏前历史的总播放。
8. 六类 chemistry 不是互斥分类；同一首歌最多可以同时落入三类，另有大量曲目不属于任何类。
9. 当前 100% 留存结论受到匹配和计数逻辑影响，不能作为正式产品事实。

#### B. 搜索与人格

`backend/services/search_service.py` 只判断查询字符串是否与本地艺人名或歌曲名完全相等，其余 87.8% 被归入“一般搜索”。前端 `habitsData.ts` 又把这个弱分类与深夜搜索、音视频次数比组合成“随性漫游者”“午夜诗人”等人格，没有验证依据。

搜索研究强调，应结合搜索目标、交互和下游行为理解发现是否成功，不能把字符串未精确命中等同于“漫游”。Spotify 自身关于音乐发现的研究也把保存、加入歌单、艺人/专辑页访问和后续收听视为不同目标下的信号，而不是单一“精准度”。见 [Understanding and Evaluating User Satisfaction with Music Discovery](https://doi.org/10.1145/3209978.3210049)。

#### C. Marquee、粉丝等级与平台推断

- Marquee 导入只有 `artistName + segment`，没有曝光时间；当前用艺人的全量历史播放除以曝光次数，425 位艺人的所谓转化率超过 100%，最高达到 22,444，不能保留“看到推广后转化为收听”的表达。
- 粉丝等级按排名位置把 Top 5 / Top 15 分成超级粉丝、核心粉丝，本质上是人为切段，且与艺人排行重复。
- Inferences 是 Spotify 和广告伙伴形成的市场分群。Spotify 官方也将其描述为广告和兴趣推断，不等于用户自我身份。[Understanding your data](https://support.spotify.com/in-en/article/understanding-your-data/)

### 3.4 隐私、导入和性能问题

| 问题 | 当前表现 | 新方案要求 |
|---|---|---|
| 敏感资料过量返回 | `/api/account` 和 `/api/profile` 可把出生日期、邮编、家庭/支付等页面不用的字段发到浏览器 | 消费接口使用白名单 DTO；默认不返回原始 profile、prompts、inferences、原始搜索词 |
| 收藏日期可能丢失 | 重新导入 `YourLibrary.json` 会先清空 `saved_tracks`；该导出本身不含收藏日期，可能抹掉 OAuth 补齐的 `added_date` | 先修导入合并策略和 provenance，再重建收藏指标 |
| 聚合响应过重 | `/api/account` 实测约 456 KB raw / 65 KB gzip；冷调用约 1.8–4.2 秒，热命中约 14 ms | 拆成渐进接口；首屏不计算搜索、Marquee、播客、视频和全部长列表 |
| 过量例子 | chemistry 684 条、tiers 1,174 位、Marquee 763 位全部返回 | 摘要只给 Top 3/5；长列表服务端分页，每页默认 20 条 |
| 重复请求 | `/account` 已内嵌 profile，前端又请求 `/profile` | 首屏只请求 archive overview；需要身份点缀时使用最小白名单字段 |
| 远程资源 | 头像或封面可能依赖 Spotify CDN | 页面只使用本地 `/covers`；缺失时使用稳定占位，不阻塞内容 |

## 4. 竞品和研究给出的方向

### 4.1 应借鉴什么

| 产品 / 研究 | 值得借鉴 | 不应照搬 |
|---|---|---|
| [Spotify Wrapped](https://newsroom.spotify.com/2025-12-03/2025-wrapped-user-experience/) | 一条故事配一组证据、特殊日期、排名变化、实体可视化 | 年度全屏故事、全球百分位、Listening Age；这些已由 `/yearly-review` 承担或缺少本地分母 |
| [Spotify Listening Stats / Sound Capsule](https://support.spotify.com/us/article/listening-stats/) | 常驻但轻量的近期变化 | 不公开算法的人格或国家平均比较 |
| [stats.fm](https://web.stats.fm/plus) | 自定义时间、实体深链、精细分包加载 | 排行榜堆叠、社交竞争、依赖第三方服务器保存完整历史 |
| [Last.fm Reports](https://www.last.fm/user/Potlah/listening-report/year) | 长期档案的章节节奏、探索与重复分开、历史报告可回看 | Mainstream Score 和全站平均；本项目没有跨用户样本 |
| [Apple Music Replay](https://support.apple.com/en-au/109356) | 全年累计 + 月度检查点 + 历史可回看 | Top Listener 等平台全体用户百分位 |
| [Receiptify](https://receiptify.herokuapp.com/about.html) | 一个清晰视觉隐喻和一张可选摘要卡 | 用分享噱头替代完整页面 |
| [volt.fm](https://volt.fm/blog/music-exclusion) | 可排除白噪声、儿童音乐、共享设备等污染数据的内容 | 全球目录和社交兼容度 |
| [Spotify 探索研究](https://doi.org/10.1609/icwsm.v16i1.19324) | 探索率、内容多样性和品味迁移是不同概念，应分开度量 | 用一个“探索者人格”概括全部行为 |

Spotify 官方导出可以提供收藏快照、搜索时间/平台/交互 URI，以及终身 Extended Streaming History 的时间、时长、平台、skip、shuffle、offline 和 private session 等字段，这正是本项目构建本地关系档案的差异化来源。[Spotify 数据导出说明](https://support.spotify.com/in-en/article/understanding-your-data/)

Spotify 的大规模研究进一步指出，探索会随生命周期和季节形成不均匀阶段，而且探索与品味多样性并不是同一个概念。[The Dynamics of Exploration on Spotify](https://doi.org/10.1609/icwsm.v16i1.19324)

### 4.2 本项目真正的空位

市面上的成熟产品几乎都把资源投入到播放排行、年度回顾、音乐人格和社交分享；很少有产品认真解释：

- 一首歌在被收藏前听了多久；
- 收藏之后有没有真正留下；
- 哪些收藏沉睡后又重新回来；
- 哪些歌经常听，却始终没有进入收藏；
- 搜索、点击、播放和收藏之间在有限证据下形成了怎样的路径。

因此，新页面不应成为另一个 stats.fm，也不应成为第二个年度总结，而应占据“个人音乐关系档案”这一独特位置。

## 5. 新产品定位与边界

### 5.1 命名

- 页面内容与二级导航名称：**音乐档案**
- 路由：继续使用 `/account`
- 英文小标题：`PERSONAL MUSIC ARCHIVE`
- 首屏主问句：**“哪些音乐只是路过，哪些真正留了下来？”**

“收藏与发现”适合作为章节名，但不足以覆盖歌单、回归和播客；“聆听身份”仍容易滑向人格判断，因此不采用。

### 5.2 与其他页面的职责分工

| 页面 | 负责回答 | 音乐档案中如何处理 |
|---|---|---|
| 播放统计 | 我听了多少、在什么时候听 | 不重复完整 KPI 和时间热图，只在收藏/发现关系中引用 |
| 播放排行 | 哪些实体播放最多 | 不复制 Top 榜，必要时深链 |
| 年度总结 | 这一年发生了什么 | 不做沉浸式年度故事和年度榜单 |
| 播放记录 | 每一次播放是什么 | 实体故事可跳到筛选后的记录 |
| Billboard | 我的榜单成绩如何 | 不展示冠军、在榜周数、走势分 |
| Settings | 如何导入、授权、治理和排除数据 | 音乐档案不重复设置状态；授权与数据治理继续由 Settings 承担 |

### 5.3 页面不得做的推断

消费 UI 禁止从日志推断人格、心理状态、情绪、年龄、社会身份或价值高低。以下文案不应出现：

- “你是午夜诗人 / 随性漫游者 / 精准猎手”；
- “你比 98% 的人更独特 / 全球前 1%”；
- “你很冷门 / 主流 / 高级”；
- “你不喜欢这首歌”，仅因为发生 skip；
- “推广让你爱上了某位艺人”，因为 Marquee 没有时间和对照组。

可以保留有趣叙事，但必须写成可验证事实，例如：

- “这 47 首歌在收藏后 90 天仍有回访”；
- “这首歌沉睡 184 天后，在 7 月重新出现”；
- “在有交互记录的 85 次搜索中，23 次在一小时内出现了对应播放”。

## 6. 新页面内容架构

页面采用一个长期档案，七个章节；不再使用“你的收藏 / 你的习惯”两个互相割裂的本地 state Tab。

### 00. 档案封面

首屏只回答“当前收藏了什么”：

- 当前收藏歌曲数；
- 当前收藏专辑数；
- 当前收藏艺人数；
- 歌单数。

Desktop 封面使用最早/最近收藏与最早/最新发行四张实体封面；Phone 只使用最早和最近收藏两张封套与黑胶拼贴。它们不是 Top 榜单，而是档案叙事入口。

不再展示头像、用户名、地区、关注数、人格徽章、数据范围、截止日期或“查看数据状态”入口。

### 01. 收藏旅程

回答“我的收藏库怎样长大”：

- 年度 / 季度收藏新增时间线；
- 首次和最近一次收藏；
- 真实收藏总时长及 duration coverage；
- 发行年代跨度；
- 收藏歌曲 / 专辑 / 艺人 / 歌单规模。

主图采用编辑式时间轴，不使用四张等权 KPI 卡铺满首屏。点击年份只改变本章实体预览，并写入 `?period=` URL。

### 02. 从遇见到收藏

回答“我通常在什么时候决定收藏”：

- **记录期内首次播放 → 收藏的时间差**：同日、1–7 天、8–30 天、31–90 天、90 天以上；
- 收藏前 30 天与收藏后 30 天的对称事件窗；
- 首次播放早于数据起点或无法匹配的曲目单列，不强行归类；
- 代表实体故事最多 5 条，可跳歌曲详情和相关播放记录。

文案使用“记录期内首次听到”，不能写“人生第一次听”。收藏快照没有取消收藏历史，因此使用“当前仍在收藏”，不能写“从未取消收藏”。

### 03. 收藏之后

回答“收藏是否变成了长期关系”：

- 收藏后 7 天内再次播放；
- 收藏后第 8–30 天仍有播放；
- 收藏半年后仍有播放；
- 收藏一年后仍有播放；
- 每个时距只使用具有对应完整观察窗的合格收藏作为分母，但消费 UI 不展示“可观察”等工程术语；
- 四项在 Desktop 与 Phone 均以互补生命力指标呈现，不再展示逐周事件曲线。

固定回访率定义为：

```text
R(h) = 在收藏后 h 天内再次有效播放的收藏数
       ÷ 具备完整 h 天观察窗且可稳定匹配的收藏数
```

该章不再生成“常青 / 偶尔 / 遗忘”人格式比例。实体状态改为可以直接验证且互斥的四类：

- 近期活跃收藏：最近 90 天有有效播放；
- 沉睡收藏：已收藏满 90 天，最近 90 天无有效播放；
- 常听未收藏：最近窗口达到展示阈值，但不在当前收藏快照；
- 无法关联：收藏 URI 暂时无法映射到规范曲目。

### 04. 找回音乐

回答“哪些音乐离开后又回来了”：

- 回归：至少连续 90 天未播放，之后再次出现；
- 最长沉睡后回归；
- 最近 30 / 90 天找回的收藏；
- 值得重听：沉睡收藏的可排序列表，但不使用“被你遗忘”这种带责备的语气。

回归锚点必须使用数据库的 `latest_play_date`，不能使用服务器今天，以保证缓存和重算结果稳定。

### 05. 发现路径

回答“我怎样主动寻找音乐”，但严格受搜索覆盖限制：

- 覆盖期和活跃日；
- 去重后的查询数与查询 burst；
- 星期 / 时段分布；
- interaction URI 覆盖率；
- 只在可映射样本中展示“搜索 → 1 小时内播放 → 30 天内收藏”的漏斗。

默认不展示原始查询全文。若后续提供“查看原始记录”，必须在本地、主动展开、可清除，并明确可能包含敏感内容。

该章不做“精准 / 漫游”分类。查询主题如需自动归类，必须输出置信度并允许回到“未分类”，不能把模型结果写成确定事实。

### 06. 收藏库

收藏浏览是工具型能力，不再埋在长报告最底部：

- 分段：歌曲 / 专辑 / 艺人 / 歌单；
- 服务端搜索、排序和分页；
- 歌曲、专辑、艺人使用统一实体深链；
- 歌单提供成员预览和重叠关系；
- 默认只渲染 20 行，Phone 正文 Top 5，完整列表进入全屏层。

Desktop 使用右侧档案抽屉或独立章节；Phone 从封面和章节底部的“打开收藏库”进入全屏浏览器，关闭后恢复焦点。

### 07. 音乐之外

播客和视频作为可选折叠章节：

- 播客：有效收听时长、节目数、活跃月、节目回访；
- 视频：有效播放时长和事件数；样本不足时只给一条档案事实；
- 音频与视频使用相同时间覆盖和“分钟”比较，不能拿有效视频次数除以全部音频原始事件；
- 无 episode duration 时不展示播客完播率。

Marquee 和 Inferences 不进入该章。若保留，只能迁移到 Settings 的“平台数据透明度”，展示 Spotify 导出中包含了哪些资料，不做行为判断。

## 7. 指标与数据契约

### 7.1 统一播放口径

所有涉及播放的账号指标必须复用项目全局统计上下文：

- `dynamic_threshold`；
- `max_merge_gap_minutes`；
- `merge_level`；
- music / video / podcast 内容边界；
- track group、album project、artist identity 和有效曲目署名；
- 排除项 revision；
- `latest_play_date` 与时区；
- 数据导入 revision。

不得在账号服务中再次直接 `COUNT(*) FROM plays` 建立第二套事实。

### 7.2 多样性和长尾只作为辅助解释

若“收藏之后”需要解释关系集中度，可使用：

- Shannon entropy `H = -Σ pᵢ ln pᵢ`；
- 有效多样性 `D₁ = exp(H)`，解释为等效均匀实体数；
- Top 10 播放占比；
- 可选 Lorenz 曲线 / Gini，仅针对记录期内实际听过的实体。

有效多样性与集中度不得包装成两个重复的“人格分数”。方法参考 [Shannon 1948](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x)、[Jost 2006](https://doi.org/10.1111/j.2006.0030-1299.14714.x)。

这些指标在本页只用于解释收藏关系是否集中，不建立独立“品味多元”大章，以免与播放统计和年度总结重复。

### 7.3 最低展示门槛

以下是产品质量护栏，不宣称为跨场景学术标准：

| 指标 | 最低门槛 | 门槛不足时 |
|---|---|---|
| 7 / 30 / 90 / 365 天回访率 | 至少 30 个完整观察窗样本 | 展示“x 首有回访 / y 首可观察”，不显示稳定百分比 |
| 搜索漏斗 | 至少 30 条带 interaction URI 且可映射 | 只展示搜索量、活跃日和覆盖说明 |
| 季度变化 | 至少 100 次有效播放、10 个活跃日、完整季度 | 不展示季度结论 |
| 播客趋势 | 至少 3 个活跃月 | 只展示累计时长和节目数 |
| 视频趋势 | 至少 100 次有效事件或 10 个活跃日 | 只展示累计档案事实 |

### 7.4 数据质量语言

普通用户不需要看到“过滤指纹、右删失、taxonomy revision”等工程词，但必须获得简洁且真实的范围提示：

- “基于可匹配的 762 首收藏”；
- “90 天结果使用已完整经历 90 天的收藏”；
- “搜索数据覆盖 2026-02—2026-05，其中 3.8% 带有点击记录”。

完整口径进入信息按钮和项目 reference 文档；Settings 保留详细数据健康与治理术语。

## 8. UI 重新设计

### 8.1 视觉方向：私人唱片档案室

在既有“编辑风 × 液态玻璃”基础上，新页采用 **私人唱片档案室 / record archive** 的单一视觉隐喻：

- 暖奶油纸张作为正文底色，炭黑夜间皮肤；
- 编辑红作为档案索引、章节编号和选中态；
- Playfair Display 负责封面标题、章节编号和关键数字，Inter 负责说明与控件；
- 封面图像像档案卡和唱片套叠放，不使用通用紫色渐变或 Spotify 绿色；
- 液态玻璃只用于 sticky 导航、筛选器、Sheet 和临时控制层，不给每一块内容都套玻璃卡；
- 图表优先使用细线、刻度、纸张分隔和直接标注，减少甜甜圈和仪表盘。

视觉记忆点是 **红色索引页签 + 有角色的四张唱片封面 + 收藏事件轴**，不是一组同尺寸 KPI 卡。

### 8.2 Desktop（≥1024px）

页面宽度从当前 `max-w-[900px]` 放宽到 1200px，与全站内容容器一致。

```text
┌──────────────────────────────────────────────────────────┐
│ PERSONAL MUSIC ARCHIVE                                   │
│ 音乐档案                                                  │
│ [歌曲] [专辑] [艺人] [歌单]              [四封面档案拼贴] │
└──────────────────────────────────────────────────────────┘

┌──────────────┬───────────────────────────────────────────┐
│ 00 档案封面   │ 01 收藏旅程：编辑式时间轴                  │
│ 01 收藏旅程   │ 02 从遇见到收藏：分布 + 实体故事            │
│ 02 遇见收藏   │ 03 收藏之后：四项生命力 + 3 类关系矩阵        │
│ 03 收藏之后   │ 04 找回音乐：回归故事 + Top 5               │
│ 04 找回音乐   │ 05 发现路径：覆盖期 + 有限漏斗               │
│ 05 发现路径   │ 06 收藏库 / 07 音乐之外                     │
└──────────────┴───────────────────────────────────────────┘
```

- 左侧 208–224px 档案索引 sticky；当前章用红色竖签，不再创建第二套页面导航。
- 主内容 8–9 列，实体故事可在右侧 3–4 列形成注释栏。
- 每章纵向间距使用 `clamp(48px, 5.5vw, 80px)`，与年度总结的编辑节奏协调。
- 图表点击点位后在同章打开 entity disclosure，不通过 hover 承担关键能力。

### 8.3 Compact（768–1023px）

- 保留档案封面和章节顺序；
- 左侧索引变成顶端可横向滚动的轻量章节条；
- 双栏故事改为单栏，图表与说明上下排列；
- 收藏库使用同页抽屉，不挂载 Desktop 的宽表；
- 不同时挂载 Desktop 和 Phone 的重图表。

### 8.4 Phone（<768px）：口袋音乐档案

Phone 不重复 Top Bar 已显示的页面 H1。正文结构为：

```text
┌──────────────────────────────┐
│ 音乐档案                      │
│ [两张唱片封套 + 黑胶拼贴]     │
│ 歌曲 / 专辑 / 艺人 / 歌单     │
│ [开始翻阅]                    │
└──────────────────────────────┘

01 收藏旅程
[年度刻度 + 本章一句结论]
[实体故事 Top 3]

02 播放多久后收藏
[收藏前后 30 天] [收藏时距分布]

03 收藏后再次播放
[7 天内] [第 8–30 天] [半年后] [一年后]

03 找回音乐
[单列回归故事]
...
```

- 首屏使用 2×2 档案事实，不展示人格徽章、头像大卡和四个重复账号 KPI。
- 档案封面用两张可核验收藏封套与黑胶形成静态拼贴，不自动轮播；章节由紧凑、粘性的横向编号条直接进入。
- 收藏生命力使用 2×2 四项互补窗口，不提供隐藏横滑或全屏曲线。
- 实体列表正文只预览 Top 3–5；完整列表每页 10 条，进入全屏列表，关闭后恢复焦点。
- 搜索热图在手机只显示“星期分布 + 时段带”；完整 7×24 图进入全屏。
- 主要触控目标至少 44×44px，0px 横向页面溢出，关键说明不能只存在于 hover。

### 8.5 状态与动效

- 页面先加载封面 overview，再按章节进入视口或用户展开触发查询；不在首次导航时下载完整收藏列表。
- Skeleton 必须匹配最终结构，避免 Hero 和章节条跳动。
- 事件轴只做 200–300ms 的位置 / 透明度过渡；遵循 `prefers-reduced-motion`。
- 空状态按缺失来源分开：有播放无账号导出、有收藏无播放匹配、无搜索文件、无播客，而不是统一写“账号数据不可用”。
- 数据补全引导统一深链到 Desktop Settings；Phone 不承载复杂导入和 OAuth 凭据配置。

## 9. API 与前端架构

### 9.1 新接口

保留 `/api/account` 前缀，但退役单一重型 summary：

| 接口 | 首屏 / 懒加载 | 内容 |
|---|---|---|
| `GET /api/account/archive-overview` | 首屏 | 档案数量、覆盖期、关联率、四个封面角色、最小数据状态 |
| `GET /api/account/collection-journey` | 首屏后 | 收藏时间线、准确总时长、首末收藏、年代跨度 |
| `GET /api/account/collection-cohorts` | 进入章节 | 固定窗回访、事件对齐曲线、合格分母、关系矩阵 |
| `GET /api/account/returns` | 进入章节 | 回归与沉睡收藏摘要、实体预览 |
| `GET /api/account/discovery` | 展开章节 | 搜索覆盖、去重/burst、有限漏斗、时段分布 |
| `GET /api/account/library/{entity_type}` | 用户操作 | 搜索、排序、分页后的歌曲/专辑/艺人/歌单 |
| `GET /api/account/other-media` | 展开章节 | 播客和视频的最小、同窗口摘要 |

所有响应使用严格 Pydantic model；禁止 `extra="allow"` 充当正式契约。overview 不返回原始 profile、搜索词、prompts、Inferences 或 banned item 明细。

### 9.2 推荐代码边界

```text
backend/domains/account_archive/
├── models.py                  # 严格响应模型与 metric metadata
├── overview.py                # 纯档案事实
├── collection_journey.py      # 收藏时间线与准确时长
├── collection_cohorts.py      # 固定观察窗、右删失、关系矩阵
├── returns.py                 # 回归 / 沉睡状态
├── discovery.py               # 搜索去重、burst、有限链路
└── other_media.py             # 播客 / 视频同窗口摘要

frontend/src/features/account-archive/
├── route/                     # Route Container、URL、query orchestration
├── desktop/                   # Desktop / Compact presentation
├── phone/                     # Phone presentation
├── components/                # 共享实体行、档案事实、口径提示
├── model/                     # row model、格式化、章节定义
└── hooks/                     # TanStack Query hooks
```

AI Agent 不能继续为了“账号收藏概况”先构建完整页面汇总；应改接 `archive-overview` 和所需的专用 compact evidence adapter。Dashboard 与 Community 继续读取各自稳定摘要，不能依赖页面聚合响应。

### 9.3 URL 与状态

- `section=journey|cohorts|returns|discovery|library|other-media`：当前章节；
- `period=all|year:2025|quarter:2026-Q1`：收藏 / 搜索可用时间范围；
- `library=tracks|albums|artists|playlists`、`sort=`、`page=`：收藏库状态；
- 页面内切换使用 `replace`，实体详情进入使用正常 `push`；
- 刷新、分享、前进后退必须恢复章节和收藏库状态。

Desktop / Phone 共用同一 URL、TanStack Query、过滤指纹、row model 和格式化函数；只允许 presentation 分叉。

### 9.4 性能预算

| 项目 | 目标 |
|---|---:|
| `archive-overview` raw JSON | ≤ 40 KB |
| overview 热响应 p95 | ≤ 75 ms |
| overview 冷响应 p95 | ≤ 750 ms |
| cohorts raw JSON | ≤ 120 KB |
| cohorts 冷响应 p95 | ≤ 1.5 s |
| 首屏实体封面请求 | ≤ 6 |
| 章节摘要例子 | 每类 ≤ 5 |
| 长列表 | 服务端分页，默认 20；Phone 全屏每页 10 |
| Desktop / Phone LCP（生产 preview） | ≤ 2.5 s |
| CLS | ≤ 0.05 |
| TBT | ≤ 150 ms |
| 360 / 390 / 430px 横向溢出 | 0px |

缓存 key 至少包含播放过滤指纹、账号导入 revision、收藏日期 provenance revision、实体归并 revision、排除项 revision、时区和 `latest_play_date`。数据库或导入变更必须失效相关命名空间；缓存命中不能掩盖日期来源变化。

## 10. Spotify OAuth 与国内部署

### 10.1 页面是否依赖 OAuth

重构后的页面 **不在运行时调用 Spotify Web API**。核心数据来自：

- Extended Streaming History JSON；
- Account Data 中的 Your Library、Playlist、Search、Podcast 等导出；
- SQLite 中已保存的元数据与本地封面。

当前 OAuth 只在以下场景有价值：

- 补齐 / 刷新收藏歌曲的 `added_at`；
- 同步最新收藏或 Spotify 私有资源；
- 项目其他位置的当前播放、歌单或在线元数据功能。

当前数据库的 800 首收藏已经全部具有 `added_date`，因此迁移现有 SQLite 后，即使 Spotify OAuth 或 Web API 不可达，“音乐档案”的本地统计仍可工作；受影响的只是可选在线刷新。

但新的空数据库如果只导入 `YourLibrary.json`，只能获得收藏快照，不能凭空恢复收藏日期。此时收藏数量和浏览仍可用，“收藏旅程 / 固定窗回访”需要已有日期快照、显式 OAuth 补全或未来支持的可信日期来源；UI 必须按章节降级，不能伪造时间线。

### 10.2 实施前必须修的本地优先问题

1. `YourLibrary.json` 重导入不得清掉已有 `added_date`；按 URI upsert 并记录 `added_date_source=oauth|manual|legacy`。
2. 远程头像和封面不得成为首屏必需资源；统一本地 cover proxy 和占位。
3. 页面 API 不做任何隐式 Spotify 请求；在线补全只由 Settings 中的显式操作触发。
4. 无 OAuth 时不显示红色错误，只显示“在线刷新未配置；当前基于截至 xx 的导入数据”。
5. 国内服务器仍需全站 HTTPS、外层认证、SQLite 持久化与备份；页面本地可用不等于整站可安全公开。

## 11. 迁移与实施顺序

### Phase 0：统计止损与数据契约（P0）

- 为当前人格、Marquee 转化、粉丝等级、关键词迁移增加退役标记，禁止在新 UI 继续消费；
- 修复 `YourLibrary` 重导入覆盖收藏日期的问题并加入 provenance；
- 建立统一 account archive 过滤指纹和 `latest_play_date` 锚点；
- 用独立 probe 对 800 首收藏的匹配、窗口资格、固定窗回访和实体归属留 evidence；
- 建立响应隐私白名单。

完成条件：同一数据库重复导入后收藏日期不丢失；所有固定窗分母可复现；API 不返回页面不需要的敏感资料。

### Phase 1：后端领域重建（P0）

- 新建 `account_archive` domain 和严格 response models；
- 实现 overview、journey、cohorts、returns、discovery、other-media；
- 接入统一有效播放、连续合并、track group、album project 和 artist identity；
- 将 AI Agent、Dashboard、Community 从重型 page summary 解耦；
- 增加 cache revision、单飞和性能 probe。

完成条件：契约、语义、隐私、性能测试通过；旧 `/api/account` 在 Phase 1 期间只作为短期兼容 facade，新页面不再调用，并已于 Phase 4 正式删除。

### Phase 2：Desktop / Compact 信息架构与 UI（P1）

- 落地档案封面、七章结构、sticky index 和实体深链；
- 用事件轴、固定窗和关系矩阵替换人格卡与 chemistry；
- 收藏库改成分页工具；
- URL 恢复章节、时间和列表状态；
- 浅色 / 深色、加载 / 错误 / 部分数据 / 空状态全覆盖。

完成条件：1280 / 1024 / 768px 视觉与交互验收；不出现播放排行、年度总结或 Billboard 的重复内容。

### Phase 3：Phone presentation（P1）

- 独立口袋档案 Hero、2×2 事实、粘性横向章节条；
- 四里程碑替代宽生命周期图；
- 收藏库进入覆盖 Shell 的全屏层并支持直接跳页；
- Top 3–5 预览、每页 10 条、焦点恢复和滚动锁定；
- Phone / Desktop 重图表和长列表互斥挂载。

完成条件：360 / 390 / 430 / 768 / 1280 route matrix、control inventory、interaction、chart、long-list、Chromium / Firefox / WebKit 全部通过。

交付状态：已完成。Phone 使用独立组件树；收藏库具备 ESC、滚动锁定、直接跳页和焦点恢复，正文预览 Top 5、完整收藏库每页 10 条。完整证据见 `../../reports/2026-08-13-account-archive-phone-delivery.md`。

### Phase 4：退役旧链路与文档收口（P2）

- 删除两个旧人格 Hero、MarqueeSection、FanTiersSection、关键词迁移和旧 chemistry UI；
- 在消费者迁移完后删除旧重型 account summary；
- 更新 `AGENTS.md`、`frontend/UI_STYLE_GUIDE.md`、统计规则 reference 和 API 台账；
- 记录 before / after 的 payload、冷/热性能、资源数和截图。

完成条件：仓库中不再有新页面对退役字段的消费，旧契约有明确移除记录，文档名称与导航一致。

交付状态：已完成。旧前端页面树、宽松类型和 hooks 已删除；旧重型 service 与两条聚合 HTTP 路由已退役；AI 工具名保留但已迁到档案白名单事实；OpenAPI、smoke 台账、项目提示和统计 reference 已同步。完整证据见 `../../reports/2026-08-13-account-archive-phase-4-delivery.md`。

## 12. 验收矩阵

### 12.1 统计语义

- [x] 未匹配收藏的播放次数不会因 `LEFT JOIN COUNT(*)` 虚增。
- [x] 收藏前后使用精确时间戳和统一时区，同日事件不会整日错分。
- [x] 7 / 30 / 90 / 365 天结果各自使用完整观察窗分母。
- [x] 缓存和回归判断锚定 `latest_play_date`，不是服务器今天。
- [x] “当前仍在收藏”“记录期内首次听到”等文案正确表达快照和左截断。
- [x] 搜索漏斗只在可映射 interaction 样本上计算。
- [x] 播客 / 视频按对齐覆盖期的分钟比较，不声称完播率。

### 12.2 产品边界

- [x] 页面没有人格、心理、年龄、冷门度和全球百分位推断。
- [x] 没有重复完整播放排行、年度榜单、Billboard 成绩或曲风语言大章。
- [x] Marquee / Inferences 若保留，只在独立兼容/透明度接口，不进入音乐档案消费页。
- [x] 每个动态故事都能跳到实体或解释其样本范围。

### 12.3 隐私与部署

- [x] overview API 不返回 birthdate、postal code、payment、family、prompts、raw queries。
- [x] 页面在没有 Spotify Client ID、token 和外网访问时仍能加载当前 SQLite 已支持的本地章节；缺少收藏日期时只按章节降级。
- [x] 封面远程失败不阻塞 LCP 或内容；本地缺图有稳定占位。
- [ ] 生产部署位于全站认证之后，API、SQLite、原始导出和封面不裸露。

### 12.4 UI 与可访问性

- [x] Desktop / Compact / Phone presentation 互斥挂载。
- [x] 所有主要操作至少 44×44px，图标按钮有 accessible name。
- [x] Tab / full-screen chart / full-screen list 支持键盘、ESC、背景锁定和焦点恢复。
- [x] 浅色 / 深色文本和图表完成生产预览检查。
- [x] `prefers-reduced-motion` 下无非必要动画。
- [x] 360 / 390 / 430px 无页面级横向滚动。

## 13. 退役、保留与迁移清单

| 当前内容 | 决策 | 去向 |
|---|---|---|
| Profile / follower Hero | 退役 | 档案封面；身份资料仍由 Settings 管理 |
| 收藏人格 | 删除 | 固定窗回访与关系矩阵 |
| 习惯人格 | 删除 | 有范围的搜索事实 |
| 收藏 KPI / 时间线 | 保留重做 | 收藏旅程 |
| 第一首收藏 | 保留但改口径 | 档案封面 / 收藏旅程 |
| 生命周期 | 重算 | 连续事件轴 + 7/30/90/365 固定窗 |
| 六类 chemistry | 删除 | 互斥关系矩阵 + 回归故事 |
| 常听未收藏 | 保留重算 | 关系矩阵 |
| 标题关键词迁移 | 删除 | 不替换；品味迁移已有年度总结 / 可后续使用规范 taxonomy |
| 收藏艺人 / 专辑排行 | 移出主叙事 | 收藏库排序；播放排行深链 |
| 收藏曲目 / 歌单浏览器 | 保留升级 | 收藏库分页工具 |
| 粉丝等级 | 删除 | 艺人播放排行 / 详情深链 |
| Marquee 转化 | 删除 | 可选数据透明度，只展示原始导出存在性 |
| 播客 | 保留降级 | 音乐之外 |
| 视频 | 保留降级 | 音乐之外；样本不足只给事实 |
| Inferences / Sound Capsule | 移出消费页 | Settings 数据透明度 / 导入健康 |

## 14. 研究限制与风险

- 本地数据只代表一个用户，足够判断该产品的数据可用性，但不能建立跨用户基准或普遍人格分类。
- Your Library 是请求时点快照，无法观察取消收藏；任何长期关系结论都必须限定为“当前收藏集合”。
- 搜索只覆盖约三个月，interaction URI 极少；发现漏斗只能作为小样本事实。
- 播客和视频样本稀疏，不能稳定外推趋势。
- 本轮没有进行真实用户可用性测试，也没有制作高保真 Figma；UI 方案需要在实现阶段以 Desktop / Phone 原型再做一次视觉验收。
- Obscurify 当前页面触发 Vercel Security Checkpoint，其详细功能仅作为次级资料参考，不进入关键统计决策。
- 竞品、Spotify API 和导出 schema 会变化；实现时需要重新核验当期官方文档。

## 15. 主要来源

### 官方产品与数据

- [Spotify — Understanding your data](https://support.spotify.com/in-en/article/understanding-your-data/)
- [Spotify — 2025 Wrapped experience](https://newsroom.spotify.com/2025-12-03/2025-wrapped-user-experience/)
- [Spotify — How Your Wrapped Is Made](https://newsroom.spotify.com/2025-12-03/how-your-wrapped-is-made/)
- [Spotify — Wrapped Methodology](https://newsroom.spotify.com/2025-12-05/wrapped-methodology-explained/)
- [Spotify — Listening Stats](https://support.spotify.com/us/article/listening-stats/)
- [stats.fm — Plus](https://web.stats.fm/plus)
- [stats.fm — About importing](https://support.stats.fm/docs/import/)
- [stats.fm — Spotify import](https://support.stats.fm/docs/import/spotify-import/)
- [Last.fm — Public yearly listening report](https://www.last.fm/user/Potlah/listening-report/year)
- [Apple — How to get your Apple Music Replay](https://support.apple.com/en-au/109356)
- [Receiptify — About](https://receiptify.herokuapp.com/about.html)
- [volt.fm — Music exclusion](https://volt.fm/blog/music-exclusion)

### 统计与行为研究

- [Mok et al. — The Dynamics of Exploration on Spotify](https://doi.org/10.1609/icwsm.v16i1.19324)
- [Mehrotra et al. — Understanding and Evaluating User Satisfaction with Music Discovery](https://doi.org/10.1145/3209978.3210049)
- [Way et al. — Finding Structure in Users’ Evolving Listening Preferences](https://doi.org/10.1145/3442381.3450028)
- [Shannon — A Mathematical Theory of Communication](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x)
- [Jost — Entropy and Diversity](https://doi.org/10.1111/j.2006.0030-1299.14714.x)
- [Kaplan & Meier — Nonparametric Estimation from Incomplete Observations](https://doi.org/10.1080/01621459.1958.10501452)

## 16. AI 使用说明

本调研使用 AI 协助并行检索、代码审计和方案综合；关键产品事实回到官方页面，统计方法优先使用论文或 DOI，项目判断回到当前仓库和只读 SQLite 证据。未将本地原始身份、搜索词或实体明细发送到外部来源。最终方案中的产品门槛是实现质量护栏，不冒充论文给出的通用阈值。
