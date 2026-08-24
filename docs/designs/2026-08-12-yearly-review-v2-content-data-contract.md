# 年度总结 V2 内容与数据契约设计

日期：2026-08-12
状态：已实现；保留为年度总结 V2 的设计决策记录，交付证据见 `docs/reports/2026-08-12-yearly-review-v2-delivery.md`
适用页面：`/yearly-review` 的“年度总结”Tab

## 1. 决策摘要

年度总结不再定位为一组年度统计卡片，而是重建为一份**可追溯的个人音乐年鉴**。

它必须回答六个问题：

1. 这一年最重要的三个结论是什么？
2. 谁被听得最多，谁在个人 Billboard 中统治最久？
3. 这些主角在什么时候出现、爆发、回落或回归？
4. 用户与歌曲、专辑、艺人的关系如何变深或改变？
5. 哪些播放与榜单事实构成真正值得记住的纪录？
6. 报告依据是否完整、口径是否统一、结论是否可以追溯？

本次采用以下硬决策：

- 新建版本化年度总结 V2 契约，不继续扩充旧 `WrappedFullResponse`。
- 核心报告完全由确定性统计事实生成，不依赖 LLM 是否配置。
- 播放排行与个人 Billboard 年榜同时进入报告，但必须回答不同问题。
- “月度脉搏”和“月度回顾”合并为唯一年度赛季时间线。
- 从播放记录和 Billboard records 中做年度精选，不把全部纪录直接堆进正文。
- 曲风与语言从静态占比改为有覆盖边界的品味迁移。
- M0–M6 首次交付只重建桌面内容与信息架构；后续 Phone 迁移阶段复用同一 V2 数据契约，并以独立移动 presentation 落地。
- `/yearly-review` 只提供自有年度总结，不再展示“官方 Wrapped”Tab。`/wrapped-hub`、官方导入表和官方数据语义不删除，进入只读兼容冻结。

## 2. 调研与当前基线

### 2.1 当前实现

当前桌面年度总结依次呈现：

1. 年度 KPI
2. 听歌人格
3. 年度最爱
4. 曲风与语言
5. 时间故事
6. 发现与回归
7. 收听深度
8. 特殊时刻
9. 月度回顾
10. 年度比较

当前主要问题：

- `TopCharts` 只返回艺人、曲目、专辑各 Top 5。
- `monthly_pulse` 与 `monthly_drilldown` 都计算并展示每月总时长。
- 个人 Billboard 年榜、年度荣誉和 Billboard records 没有进入年度总结。
- 播放记录页已有的大量有趣纪录没有被年度范围精选消费。
- `monthly_genres`、`music_map`、`top_vs_alltime` 等部分已计算数据没有形成有效内容。
- 年度页 query key 只有年份，没有完整过滤指纹。
- `days_covered` 仅由首末日期之间的自然日数推导，不能独立证明导入完整。
- 当前部分文案与实现口径不一致，例如“深度聆听率”的前端描述与后端阈值不同。

### 2.2 2025 真实数据探针

按当前默认有效播放口径、`merge_level=2` 的只读探针：

- 17,567 次有效播放。
- 约 1,135 小时。
- 364 个活跃日。
- 当前年度页只给 5/5/5 条 Top 榜。
- 个人 Billboard 年榜已有 50/30/30 条完整结果和 12 项年度荣誉。
- 年度范围播放记录已有 70 个非空纪录叶节点。

同一年度中，播放量最高专辑与个人 Billboard 年榜冠军可以不同，说明两种排行不是重复信息：

- 播放排行回答“谁被听得最多”。
- 个人 Billboard 年榜回答“谁在全年周榜中持续统治”。

### 2.3 外部产品启示

调研只用于提炼内容方法，不复制外部 UI：

- Spotify Wrapped 2025 使用 Top Artist Sprint、Top Albums、榜单竞争和特殊收听日，把排名变化与具体事件结合。
- Apple Music Replay 同时提供全年、逐月、里程碑、历年和 All Time 参照。
- YouTube Recap 选择关键月份和兴趣演变，而不是机械重复十二个月。
- Last.fm 的深度来自日历、时钟、年代、发现、集中、复听和同比等交叉维度。
- ListenBrainz 将艺人演变、发现、遗漏、发行年代和可分享产物建立在结构化统计上。

形成的设计原则是：**深度来自结构化事实、比较基线和高光筛选，不来自更长的 AI 文案。**

调研来源（访问日期：2026-08-12）：

- [Spotify Wrapped 2025 体验说明](https://newsroom.spotify.com/2025-12-03/2025-wrapped-user-experience/)
- [Spotify Wrapped 2025 数据方法](https://newsroom.spotify.com/2025-12-03/how-your-wrapped-is-made/)
- [Apple Music Replay 支持说明](https://support.apple.com/en-asia/109356)
- [YouTube Recap 2025 官方介绍](https://blog.youtube/news-and-events/youtube-recap-2025/)
- [Last.fm Last.year 公开样例](https://www.last.fm/user/Lastfmsupport/listening-report/year)
- [ListenBrainz Statistics API](https://listenbrainz.readthedocs.io/en/latest/users/api/statistics.html)

## 3. 产品定位与范围

### 3.1 产品承诺

> 基于真实播放事件与本地个人 Billboard 周榜，重建这一年的音乐轨迹：谁长期统治、谁阶段爆发、什么时候发生转折、哪些关系加深、哪些瞬间成为纪录。

普通用户侧统一写“个人 Billboard”或“本地个人 Billboard”，不得暗示外部官方 Billboard 数据。

### 3.2 本次范围

包含：

- 新的年度总结 V2 后端契约与编排层。
- 新的桌面年度总结内容架构。
- 播放排行、个人 Billboard 年榜、年度纪录、时间线、关系故事、收听生活、品味迁移和完整榜单。
- 统一过滤指纹、覆盖状态、同比与个人历史参照。
- 旧 V1 年度总结的兼容保留。

不包含：

- 删除或改写已冻结的官方 Wrapped 导入表与 `/wrapped-hub` 兼容数据语义。
- 本阶段重做 Phone presentation。
- 修改个人 Billboard Power Score 公式。
- 引入全球用户 percentile 或伪造平台级排名。
- 让 LLM 计算、选择或改写统计事实。
- 分享长图、PDF、社交比较、朋友榜或自动生成播放列表。

## 4. 内容所有权与去重规则

每类内容只有一个主职责：

| 内容类型 | 唯一回答的问题 |
| --- | --- |
| 播放排行 | 谁被听得最多、时间花在哪里 |
| 个人 Billboard 年榜 | 谁长期、稳定地统治周榜 |
| 年度赛季时间线 | 什么时候发生了变化 |
| 关系故事 | 用户与某个实体形成了什么关系 |
| 收听生活 | 用户在什么时间、以什么模式听歌 |
| 年度纪录簿 | 哪个事实构成极值、稀有或历史节点 |
| 品味迁移 | 口味结构从年初到年末如何变化 |
| 完整榜单 | 为需要查全表的用户提供下钻 |

硬规则：

1. 同一指标只能有一个主展示位置。
2. 同一实体可以重复出现，但必须承担不同叙事角色。
3. 第二次出现时引用已有结论，不复制整张卡片和全部指标。
4. 每条故事必须包含“结论、证据、比较基线、下钻入口”。
5. 只把 Top 1 改写成一句形容词不构成故事。
6. 月度完整明细只保留一套。
7. 正文负责精选，附录负责完整。

## 5. 年度年鉴章节

### 5.1 序章：年度报告护照

回答：这是一份什么范围、什么质量的年度报告？

展示：

- 年份和报告状态：完整年度、截至某日、观察区间、数据不足。
- 观察到的首末播放日期、活跃日、有效播放、有效时长。
- 唯一曲目、专辑、艺人数。
- 与上一年或上一年同期相比最重要的总量变化。
- 三条年度头条结论。
- 简化后的当前统计口径入口。

不展示：

- 听歌人格。
- 无比较基线的情绪化结论。
- 把自然日跨度包装成数据完整率。

### 5.2 第一章：年度荣誉殿堂

回答：谁赢得了这一年，为什么？

每种实体统一展示两个视角：

#### 播放冠军

- 年度播放排名。
- 有效播放次数。
- 有效时长。
- 活跃日或活跃月份。
- 年度份额。

#### 个人 Billboard 冠军

- 年榜排名和 Year-End Score。
- 峰值。
- 在榜周、冠军周、Top 5/Top 10 周。
- 首次和最后一次榜周。
- 年榜覆盖状态。

#### 双榜差异故事

只在结果确实不同时生成：

- 集中爆发：播放量高，但榜单持续性较弱。
- 稳定统治：播放量不是最高，但年榜位置更高。
- 后程逆袭：年末高位进入并改变年度排名。
- 贯穿全年：长期在榜、跨多个阶段保持高位。

#### 年度荣誉

复用个人 Billboard Year-End honors：

- 年度 #1 曲目、专辑、艺人。
- 最长在榜曲目、专辑、艺人。
- 最长冠军统治曲目、专辑、艺人。
- 最高新进曲目。
- 突破艺人。
- 年度专辑时代。

完整播放榜和年榜进入附录，正文不重复完整长表。

### 5.3 第二章：年度赛季时间线

回答：这一年如何展开？

唯一月度模型包含：

- 每月有效播放与时长。
- 每月播放冠军曲目、专辑、艺人。
- 每月个人 Billboard 冠军。
- 新发现、回归、单日爆发、连续收听等候选事件。
- 与上月和上一年同月的可比变化。
- 该月所属年度阶段。

正文只精选 6–10 个转折节点；十二个月完整明细作为同一时间线的展开状态，不再存在第二个月度章节。

允许的转折类型：

- 榜首易主。
- 新艺人或新专辑突破。
- 专辑时代开始或结束。
- 最大探索月。
- 最强回归。
- 最大高峰日。
- 年末逆袭。
- 收听习惯显著变化。

年度阶段数量默认 3–5 个。阶段边界必须由月度结构变化产生，不由 LLM 自由命名。

M0 冻结 `season_stage_policy_v1`：

- 每个自然月最多一个正文节点；同月多个事实合并为一个可展开节点。
- 固定候选池包含收听时长峰值月、探索峰值月、个人 Billboard 榜首易主、新关系、真实回归、最显著且覆盖合格的品味变化和高分年度纪录。
- 艺人或专辑榜首变化只有连续维持至少 2 个月才可单独形成阶段边界；单月易主只能作为事件候选。
- 正文最多保留 3 个榜首易主节点，避免 2025 这类高换手年份淹没其他故事。
- 阶段最短 2 个月；单月孤岛并入相邻相似阶段。只有能稳定得到 3–5 段时才展示阶段，否则只展示转折时间线，不强行分幕。
- 先按证据充分度、变化强度、持续性、个人历史稀有性排序，再执行月份与类型多样性约束；任何阶段标题都只能复述已选事实。

### 5.4 第三章：你与音乐的关系

回答：哪些关系贯穿、爆发、加深或重新开始？

`relationship_policy_v2` 支持的关系类型：

- 年度主线艺人。
- 年度专辑时代。
- 长期陪伴。
- 短期着迷。
- 新关系。
- 旧爱回归。
- 深度专辑聆听。
- 播放量与榜单赛季表现差异。

“慢热作品”和“被低估作品”暂不作为 V1 固定标签；前者需要另行审计月度增长曲线，后者容易把两种不同排名口径误写成价值判断。V1 只陈述“总量更集中”或“赛季更持久”。

解释性关系必须至少由两个独立指标支持，例如：

- 时间跨度 + 活跃月份。
- 峰值强度 + 持续时间。
- 播放排行 + Billboard 排行差异。
- 专辑曲目覆盖 + 回放轮次。
- 沉寂跨度 + 回归后的有效播放。

不得只用艺人常识、作品标题或 LLM 推断情绪和现实生活事件。

M0 已基于 2023–2025 三个完整自然年建立候选规则；最终展示由 `relationship_policy_v2` 进一步限制为最多 8 条，并去除与年度荣誉重复的主线/专辑时代事实：

| 关系 | 最低资格 | 排序证据 |
| --- | --- | --- |
| 年度主线艺人 / 专辑时代 | 直接复用个人 Billboard Year-End honor，且 Billboard coverage 为 `complete` | 年榜名次、在榜周、冠军周、赛季积分 |
| 长期陪伴 | 年内有效播放 ≥10、活跃月 ≥9、最长连续活跃月 ≥6、首末跨度 ≥240 天 | 活跃月、连续月、跨度、活跃日、播放量 |
| 全年陪伴强化标记 | 长期陪伴基础上，活跃月 ≥11、连续活跃月 ≥9、跨度 ≥300 天 | 同上 |
| 短期着迷 | 有效播放 ≥10、单一峰值月占比 ≥70%、活跃月 ≤4 | 峰值月占比、峰值播放、全年播放 |
| 深度专辑聆听 | 专辑项目有效播放 ≥20、独立曲目 ≥8、活跃日 ≥10 | 曲目覆盖、播放量、活跃日；有可靠总曲数时补充完成率 |
| 广泛艺人聆听 | 艺人有效播放 ≥30、独立曲目 ≥15、活跃月 ≥4 | 目录宽度、播放量、活跃月 |
| 新关系 | 全历史首次播放发生在报告年；年内有效播放 ≥10、活跃日 ≥3、首末跨度 ≥30 天 | 首次日期、留存跨度、播放和活跃日 |
| 旧爱回归 | 报告年前已有播放；报告年前最后一次与报告年首次相隔 ≥180 天；回归后有效播放 ≥10、活跃日 ≥3 | 沉寂跨度、回归后播放、活跃日 |
| 赛季表现差异 | 同时进入两类年榜；歌曲绝对名次差 ≥10，专辑/艺人绝对名次差 ≥5 | 播放榜名次、Year-End 名次、在榜周与峰值月 |

约束：

- 同一实体最多占两个不同关系角色，每种关系正文最多展示 2 个实体。
- `10 plays` 只定义候选池，不足以单独生成关系结论；所有解释性关系仍至少需要两个独立 A/B 指标。
- “旧爱回归”不得复用现有 Wrapped 中“发行超过 5 年的热门旧歌”定义；必须按用户自身播放间隔计算。
- 报告范围不足 90 天时不生成关系标签；非完整年份不生成“全年陪伴”强化标记，只展示截至报告日的事实。

审计依据：10 次播放候选池每年仍有歌曲 369–511、专辑 176–257、艺人 107–128 个；上述“长期陪伴”场景每年分别产生歌曲 67–78、专辑 27–58、艺人 27–40 个候选，“短期着迷”分别产生歌曲 31–51、专辑 24–51、艺人 11–21 个候选，既不会空缺，也需要后续排序而非继续放宽阈值。

### 5.5 第四章：你的收听生活

回答：用户如何听歌，而不是听了谁？

候选内容：

- 小时分布和一天中的主要时段。
- 工作日与周末差异。
- 深夜收听比例及其同比。
- 活跃连续期和可证实的空窗。
- 单曲循环、专辑沉浸和艺人集中度。
- 探索率、复听率和集中度。
- 平台使用与切换，仅在数据可靠且有解释意义时展示。

每项都需要比较基线；单独一个百分比不能生成“更集中”“更探索”等结论。

若没有导入覆盖证据，禁止把无播放日期直接解释为用户没有听歌，也不得生成“最长空窗”。

### 5.6 第五章：年度纪录簿

回答：什么事实真正值得记住？

候选来源：

- 年度范围 `/analysis/records`。
- 年度范围 `/billboard/records`。
- 个人 Billboard Year-End honors。
- 年度同比和个人历史新高。
- 年度赛季时间线中的显著节点。

正文默认精选 6–8 条，且每个一级类别最多 2 条。年报不再承接完整纪录目录；完整播放纪录和 Billboard 纪录分别回到原页面。

年度纪录候选统一为：

```text
YearlyHighlightCandidate
- candidate_id
- category
- fact_type
- title
- statement
- entity_refs
- period
- primary_metric
- secondary_metrics
- comparison
- evidence_grade
- coverage_status
- source_refs
- deep_link
- semantics
  - scope
  - rank / rank_basis
  - is_top / is_tied_top
  - observed_start / observed_end
  - comparison_start / comparison_end
  - denominator_scope
- noteworthiness_components
```

候选必须携带机器可读语义，renderer 和选择器不得仅凭 `record_key` 或自然语言猜测“个人历史”“本年第一”或比较窗口：

- 播放里程碑只允许从完整个人历史累计序列计算，再筛选“阈值跨越日期发生在报告年”的事件；年内计数不得冒充个人历史累计。
- “第一次听到”先从完整历史确定 canonical 实体的真实首播日期，再筛选首播发生在报告年的歌曲、album project 或 canonical artist；报告年切片内的首次出现不能称为第一次听到。
- 每日播放次数和每日收听时长分属两个独立排名族，各自使用 dense rank；只有 `rank=1` 可以使用“最多/最长”，并列第一必须明确写“并列”。
- 不完整月份的环比和同比只能分别与上月同期、上年同期的等长窗口比较，并在 metric 中同时记录观察与比较起止日期；完整月才可使用完整自然月比较。
- 歌曲数量、探索率和复听率统一使用 canonical track identity；艺人播放占比的分母是年度逻辑播放总数，分子允许按有效署名 fan-out 后包含该艺人的播放。

筛选流程：

1. 资格过滤：排除数据不足、样本不足、不可解释和范围不一致的事实。
2. 语义去重：合并同一实体、同一日期、同一底层指标产生的重复候选。
3. 重要性排序：结合强度、持续性、个人历史稀有性、同比变化和具体性。
4. 多样性约束：避免同一艺人、同一类别或同一指标占满正文。
5. 最终选择：固定规则选出 6–8 条，不由 LLM 决定。

当前冻结 `highlight_policy_v3`：

- 只接收 A/B 级事实和由至少两个 A/B 指标支持的 C 级事实；范围或覆盖不一致的候选直接淘汰。
- 先按 `entity identity + fact family + period + underlying metric` 语义去重，再排序；图片 URL、展示标题和名次字段不参与去重。
- 重要性分数由变化强度 30%、持续性 20%、个人历史稀有性 20%、同比变化 15%、日期/实体具体性 10%、证据与覆盖 5% 构成；缺失但非必需的比较项按剩余权重归一化，不以 0 分惩罚。
- 最终选择 6–8 条；每个一级类别最多 2 条、同一实体最多 2 条、同一底层指标最多 1 条。
- 在存在合格候选时，正文至少覆盖高峰/着迷、持续/陪伴、发现/回归、收听行为四种事实家族；个人 Billboard honors 已在第二章展示，不为凑数重复进入纪录簿。
- 若严格多样性约束后不足 6 条，可放宽类别上限到 3 条，但不得放宽证据、覆盖和语义去重门槛。
- 任何自称年度唯一极值的候选都必须携带 `rank=1`；非第一名只能使用中性名次文案。`annual_first_seen` discovery 与非 lifetime milestone 直接淘汰。

筛选策略通过 `highlight_policy_version` 版本化，并记录在响应与缓存键中。M0 三年审计每年发现 69–70 个非空纪录叶节点和 2,173–2,268 条候选，因此 V1 的核心问题是去重与多样性，而不是扩大候选池。

### 5.7 第六章：品味迁移

回答：口味结构如何变化？

只展示普通用户可理解的消费层：

- 主曲风 `style`。
- 地区流行 `scene`。
- 语言分布。
- 发行年代。

不展示：

- `context`、`role` 治理轴。
- 来源、证据、审核状态等 Settings 术语。
- 依赖地区 heuristic 的 Music Map。
- 没有真实总体的主流度或全球 percentile。

每个迁移结论至少包含：

- 年初与年末、季度或上年同期的结构差异。
- 推动变化的主要艺人或作品。
- 已知与 unknown 覆盖。
- 变化是持续趋势还是单一实体短期驱动。

曲风、语言和年代分别计算，不互相启发式推断。

消费侧覆盖门槛冻结为：

- 已知覆盖 ≥70%：允许进入核心图表和迁移结论。
- 已知覆盖 40%–69.99%：允许显示含 unknown 的辅助分布，不生成年度身份或主线结论。
- 已知覆盖 <40%：消费界面隐藏该轴；完整 buckets、unknown 比例和限制说明只留在 API/probe，不生成迁移结论。

三年审计中主曲风已知覆盖为 92.29%–92.47%，语言已分类覆盖为 98.01%–98.71%，可进入核心迁移；`scene` 只有 8.77%、42.49%、48.12%，因此当前数据下不得成为年度主线，其中 2023 只保留覆盖说明，2024–2025 最多作为带 unknown 的辅助观察。

### 5.8 终章：这一年留下了什么

回答：与以前相比，什么真正改变了？

展示：

- 三项最重要的同比或个人历史变化。
- 新进入个人历史 Top 的实体。
- 延续到下一年的艺人、专辑或曲目；只有存在下一年数据时生成。
- 完整榜单入口。

终章不重新展示全套 KPI 或 Top 榜。

### 5.9 附录：完整榜单

包含：

- 播放排行：曲目 Top 50、专辑 Top 30、艺人 Top 30。
- 个人 Billboard 年榜：曲目 Top 50、专辑 Top 30、艺人 Top 30。
- 年度纪录只保留第五章精选集合，不在附录或正文建立第二套完整目录。
- 月度冠军表只在第三章唯一月份明细中展开，不在附录重复。
- 数据范围、过滤口径、版本与方法说明仅保留在后端契约和 probe，不进入用户附录。

附录只负责完整与可查，不承担主叙事。

## 6. 证据与结论等级

内部使用四级证据：

| 等级 | 定义 | 示例 | 是否可直接生成结论 |
| --- | --- | --- | --- |
| A | 直接事件或榜单事实 | 播放次数、日期、周榜排名 | 是 |
| B | 稳定派生指标 | 集中度、复听率、在榜周数 | 是 |
| C | 解释性结论 | 短期着迷、长期陪伴、品味迁移 | 需至少两个 A/B 指标支持 |
| D | 证据不足或范围不一致 | 缺失覆盖下的最长空窗 | 否 |

普通用户界面不展示 A/B/C/D，只展示：

- 数据充分。
- 样本有限。
- 暂无法判断。

## 7. 统一过滤指纹

所有章节必须共享同一个 `filter_context`：

```text
- min_ms
- music_only
- merge_enabled
- dynamic_threshold
- max_merge_gap_minutes
- merge_level
- include_compilations
- bb_top_n
- bb_album_top_n
- bb_artist_top_n
- bb_week_start_dow
- bb_week_start_hour
- display_taxonomy_version
- artist_metadata_revision
- track_credit_revision
- album_project_revision
```

要求：

- 前端 query key 包含年份与完整过滤指纹。
- 后端所有 builder 接收同一个已解析 context，不分别读取默认值。
- 播放排行、个人 Billboard、纪录和品味统计不得使用不同口径。
- 缓存键包含 filter fingerprint、schema version、独立 content version、稳定播放事实 revision 和所有相关元数据 revision。content version 每次统计/编排语义变化都必须提升，不能借 sidecar 压缩格式版本表达内容变化。

## 8. 覆盖契约

顶层 `coverage` 分开描述不同事实，不能压缩为一个误导性的百分比：

```text
play_coverage
- observed_start
- observed_end
- active_days
- natural_days_span
- import_coverage_status
- internal_gap_status

billboard_coverage
- coverage_status
- observed_weeks
- expected_weeks
- has_internal_gaps
- first_billboard_week
- last_billboard_week

comparison_coverage
- baseline_year
- aligned_start
- aligned_end
- comparable
- reason

taste_coverage
- style_known_pct
- scene_known_pct
- language_known_pct
- unknown_hours
```

显示规则：

- 当年未结束：写“截至 YYYY-MM-DD”，只做上一年同期比较。
- 历史数据不完整：写“观察区间”，荣誉使用“阶段领先”。
- Billboard 周数不足：显示阶段榜，不生成完整年榜统治结论。
- 无可比上年：隐藏同比，不显示 `0%` 或默认 `100%`。
- 元数据覆盖不足：保留 unknown，隐藏不可靠迁移结论。
- 没有导入 manifest 或其他覆盖证据：`internal_gap_status=unknown`，不能把无播放解释为缺口或空窗。

## 9. V2 响应契约

新增：

```text
GET /api/yearly-review/{year}
```

可选：

```text
GET /api/yearly-review/available-years
POST /api/yearly-review/prewarm
GET /api/yearly-review/generation-status
GET /api/yearly-review/{year}/records
```

主响应概念结构：

```json
{
  "schema_version": "yearly_review_v2",
  "year": 2025,
  "status": "complete",
  "filter_context": {},
  "coverage": {},
  "passport": {},
  "headlines": [],
  "honors": {
    "play_leaders": {},
    "billboard_leaders": {},
    "divergence_stories": [],
    "annual_honors": []
  },
  "season": {
    "stages": [],
    "turning_points": [],
    "months": []
  },
  "relationships": [],
  "listening_life": {},
  "records": {
    "policy_version": "yearly_highlights_v1",
    "featured": [],
    "catalog_counts": {}
  },
  "taste_migration": {},
  "epilogue": {},
  "appendix": {
    "play_charts": {},
    "billboard_charts": {},
    "monthly_champions": []
  },
  "methodology": {}
}
```

兼容 `/records` endpoint 只返回与主响应一致的精选纪录，不再物化完整候选目录；主响应仍返回精选纪录和内部候选计数供自动验收。

所有 endpoint 声明 `response_model`，并通过现有 `X-Request-ID` 中间件。

## 10. 后端架构

建议新增独立 domain：

```text
backend/domains/yearly_review/
├── contract.py
├── context.py
├── coverage.py
├── passport.py
├── honors.py
├── season.py
├── relationships.py
├── listening_life.py
├── records.py
├── taste_migration.py
├── comparison.py
├── appendix.py
└── orchestrator.py
```

架构原则：

- `orchestrator` 负责共享 frame、context、coverage 和 builder 编排。
- 各章节 builder 不自行重新加载全部播放数据。
- 个人 Billboard 复用既有 staged cache，不重写 Power Score。
- 记录 builder 复用既有播放记录和 Billboard records 域函数。
- 跨视角实体匹配使用 canonical track、album project、canonical credited artist。
- 旧 `wrapped_service.py` 保留为 V1 兼容，不继续承载 V2。

## 11. 前端边界

建议新增：

```text
frontend/src/features/yearly-review/
├── YearlyReviewDesktopExperience.tsx
├── passport/
├── honors/
├── season/
├── relationships/
├── listening-life/
├── records/
├── taste-migration/
├── epilogue/
└── appendix/
```

要求：

- `YearlyReviewPage` 继续负责年份和 route container，不再维护年度模式 Tab。
- Desktop/Compact 的自定义总结使用 V2 desktop experience。
- Phone 自定义总结使用同一 V2 数据、筛选与生成状态，但由独立 `YearlyReviewPhoneExperience` 组织移动 UI，不挂载桌面章节 DOM。
- 页面不导入或请求 `OfficialWrapped`；冻结的 `/wrapped-hub` 只由兼容测试和诊断工具访问。
- 新 TanStack Query key 使用完整过滤指纹。
- 新章节必须使用现有实体详情路由，不建立第二套详情页。
- 桌面主报告避免将完整长表全部挂载；附录使用分页或按需挂载。
- 消费界面只展示故事、榜单、变化和实体，不展示过滤指纹、统计口径、策略版本、证据等级、coverage 或 limitations；严谨信息保留在 API、probe 与工程文档。
- 章节大标题下不再增加解释性 subtitle；“完整榜单”只保留播放榜与个人 Billboard 两个入口，月份只在唯一时间线中展开。
- 顶部六项 KPI 使用用户能直接理解的年度命名；存在同比时只在数值右侧显示箭头与百分比，不重复显示“高/低”，完整的比较语义通过 accessible label 保留。
- 新关系公开标题按实体类型分别使用“今年发现的新歌 / 今年新听的专辑 / 今年认识的新艺人”。同专辑/艺人多首入榜必须携带并展示准确 `track_count`，缺少该字段时不得公开该条纪录。
- 歌曲、专辑、艺人在荣誉、时间线、关系、生活、纪录、品味、结语和完整榜单中统一使用封面与既有详情深链；缺图使用稳定占位，不隐藏实体。
- 年份按钮由小到大排列且只显示年份，所有视口默认选择最新可用年份（包括进行中的当前年）；完整年度封面不重复显示状态和起止日期，当前年报告仍在封面显示“进行中 · 截至日期”。章节导航滚动后保持可见。
- 封面不显示三条年度头条，也不提供生成年度海报操作。

## 12. AI 边界

核心报告无需 LLM 即可完整使用。

允许的后续能力：

- 根据已选定的 headlines 和 featured records 写一段编辑导语。
- 为确定性阶段或特殊日期生成可选摘要。
- 生成分享文案。

禁止：

- 让 LLM决定年度冠军、阶段边界或纪录资格。
- 让 LLM补齐缺失曲风、语言或现实场景。
- 把 AI artifact 缓存是否存在作为年度总结可用条件。
- 用未通过 fact validator 的文本替换确定性内容。

## 13. 兼容与迁移

- 保留 `GET /api/wrapped/{year}/full` 和 `WrappedFullResponse`。
- 保留现有 V1 组件作为历史兼容代码，不再由自定义年度总结的 Phone/Desktop 路由挂载。
- Desktop 与 Phone V2 通过同一 hook 和类型接入，presentation 互斥挂载。
- V2 验收完成后，桌面不再挂载旧人格、TopCharts、TimeStory、DiscoveryReturns、ListeningDepth、SpecialMoments、MonthlyDrilldown 和 YearComparison 组合。
- 不删除历史文档，旧年度总结设计继续保留在 `docs/archive/`。

## 14. 验收标准

### 内容验收

- 30 秒内可读到报告范围、三条头条和年度冠军。
- 播放冠军与个人 Billboard 冠军明确区分。
- 正文只有一套月度时间线。
- 时间线优先包含 6–10 个可核验转折节点；证据不足时允许 4–8 个高质量节点，不得为了数量混入无日期年度汇总。
- 年度纪录正文精选 6–8 条，且没有单一实体或类别垄断。
- 每条解释性故事都能追溯到数值、周期和实体。
- 完整播放榜和个人 Billboard 年榜可在附录查看。
- 无证据的人格、现实情境和全球 percentile 不出现。

### 语义验收

- 全章节共享同一个过滤指纹。
- 播放排行和个人 Billboard 使用同一年度范围。
- Billboard 年榜完整性直接复用现有 coverage contract。
- 不完整年份只显示阶段性结论。
- 无同比基线时不显示默认变化百分比。
- 曲风、语言、年代保留 unknown 和各自覆盖率。
- 专辑使用 album project identity；艺人使用有效署名与 canonical identity。
- 同比必须裁剪到真实 aligned window，基线覆盖不足时不向章节传递 baseline stats。
- 工作日/周末日均使用观察区间内真实自然日数量；YTD 品味只比较两个完整季度，不足时为 distribution-only。
- `stage_status` 与 stages 必须一致；无法证明稳定阶段时 stages 为空。
- Passport 与收听生活的年度歌曲数必须完全一致，均使用 canonical track identity。
- 收听生活的头号艺人播放占比必须能由“包含该艺人的逻辑播放数 / 年度逻辑播放总数”复算。
- 不完整月份的环比与同比必须使用等长同日窗口，并公开保存两侧日期；不得把当月至今与上月或上年整月相比。
- 同一年度不得产生多个未标注并列的“播放次数最多的一天”或“听歌时间最长的一天”。
- 个人历史里程碑和真实首次发现必须由完整历史计算；报告年只负责筛选事件发生时间。

### 范围验收

- 官方 Wrapped Tab 与前端展示组件已移除；`/wrapped-hub` 继续保持只读响应兼容，不进入消费页面。
- Phone 与 Desktop/Compact 共享年度事实；Phone 必须通过独立 presentation 完成移动适配。
- 核心年度总结不需要 LLM 配置。
- 未修改个人 Billboard Power Score 公式。

### 工程验收

- V2 API 有明确 response model、OpenAPI contract 和缓存版本。
- route container 保持轻量，章节组件 feature-first 拆分。
- 纪录与完整榜单不产生超过 500 行的无分页 DOM。
- 桌面 `/yearly-review` route smoke、control inventory 和 production build 通过。
- Phone V2 与 Desktop V2 互斥挂载，页面不存在 Official Wrapped/V1 DOM；冻结的 `/wrapped-hub` contract 继续通过。

## 15. 完成定义

只有以下两部分都完成，才能称为“年度总结内容完全重构”：

1. V2 骨架：报告护照、双榜荣誉、唯一时间线、纪录精选、完整榜单。
2. 深度内容：关系故事、收听生活、品味迁移、同比与个人历史参照。

AI 编辑、分享导出和播放列表属于后续阶段，不阻塞内容重构完成。

## 16. Phone V2 迁移补充（2026-08-12）

Phone 迁移不改变本文件定义的年度事实、章节顺序、过滤指纹、缓存 key 或内容版本。移动端只新增独立 presentation，并遵守以下契约：

- 自定义总结在 Phone、Compact、Desktop 默认选择最新可用年份，显式 URL 年份继续优先；年度动态文案与实体名称使用全局简繁体偏好，事件正文和实体卡明确歌曲、专辑、艺人类型。
- Phone 进入页面时也提交全部可用年份的后台预生成；计时继续锚定服务端 `requested_at`。
- 封面使用 2×3 KPI；完整年度隐藏状态，进行中显示截止日期。
- 八章保持同一内容所有权，但时间线改为纵向、月份一次展开一个、关系与结语改为单列。
- 年度纪录完整展示精选集合；完整榜单正文只预览 Top 5，全屏列表每页 10 条，不使用横向表格。
- 章节目录使用 Bottom Sheet；全屏榜单必须支持背景滚动锁定、Escape/关闭和焦点恢复。
- Phone 与 Desktop/Compact DOM 互斥挂载，主要触控目标至少 44×44px，360/390/430px 不得出现横向溢出。
- 官方 Wrapped 的前端展示退役；官方导入数据与 `/wrapped-hub` 路由冻结保留。
