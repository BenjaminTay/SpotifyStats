# 多源音乐元数据后续路线记录

> 创建日期：2026-09-23<br>
> 实现状态：PLANNED / DEFERRED<br>
> 验证状态：DOC_REVIEW（仅完成现状审计与方案分析）<br>
> 仓库状态（记录形成时）：UNCOMMITTED<br>
> 远端状态（记录形成时）：UNPUSHED<br>
> 部署状态（记录形成时）：NOT_DEPLOYED<br>
> 文档用途：记录后续可考虑的方向，不构成实施授权，也不改变当前产品规则

## 1. 为什么保留这份路线

SpotifyStats 当前能够从 Spotify 补齐歌曲、专辑、封面和艺人外部标识，但把某一个平台的数据直接当成完整事实，会留下三类长期问题：

1. 曲目署名不完整。Extended Streaming History 只有单个 `master_metadata_album_artist_name`，当前导入只能再从标题中的 `feat.`、`ft.`、`with` 补充显式合作艺人；标题未写合作关系时会漏记。
2. 元数据来源单一。平台的名称、封面、发行信息或身份关联发生错误时，本地缺少第二来源用于发现冲突。
3. 语言粒度不够。当前语言事实以艺人为主体，适合稳定的艺人级统计，但无法可靠回答同一位多语言艺人的某一首歌究竟使用什么语言。

这份文档只保存已经讨论过的方向、边界和重新启动条件。已完成的 Spotify Track `artists[]` 证据阶段见 [实施规划归档](../archive/06-productization-closeout/2026-09-23-spotify-track-artists-evidence-plan.md)及[交付报告](../reports/2026-09-24-spotify-track-artists-evidence-delivery.md)；本路线中的其他字段与第二来源仍未实施。

## 2. 已确认的当前事实

### 2.1 数据链路

- 原始播放导入读取 `master_metadata_album_artist_name`，并把标题中可识别的合作标记写入原始 `track_artists`。
- Spotify Web API 的 Track object 提供有序 `artists[]`；2026-09-23 规划基线中，刷新逻辑只用“名称精确归一化匹配”给已有本地艺人补 Spotify artist id。2026-09-24 已补齐独立 evidence 持久层，正式有效署名仍不自动更改。
- `spotify_track_meta` 已保存 Spotify track、album、ISRC 等信息；Track `artists[]` 的独立 provider evidence 实现及隔离验收见本页上方的交付报告链接。
- 人工治理已经通过 `track_credit_overrides`、审计事件和 revision 叠加在原始署名之上。按当前规则，外部元数据补齐不得重写 `plays`、`tracks` 或原始 `track_artists`。

### 2.2 2026-09-23 本地只读基线

| 指标 | 数值 | 说明 |
|---|---:|---|
| 曲目总数 | 10,026 | 当前本地数据库快照 |
| 已有多艺人原始署名 | 409 | 不代表完整，也不代表角色均准确 |
| 含 `featured` 原始署名 | 386 | 主要来自标题解析或现有导入事实 |
| 单署名曲目 | 9,617 | Spotify `artists[]` 的首轮重点审计范围 |
| 已有 ISRC | 9,941（99.15%） | 为 MusicBrainz / Apple Music 等后续交叉检索提供较好入口，但 ISRC 仍须校验一对多、版本和误配 |

这些数字只是规划时的数据库快照，正式实施任何阶段前必须重新测量，不应写成长期常量。

## 3. 后续可考虑的能力

| 方向 | 主要用途 | 可以解决什么 | 主要边界 | 当前决定 |
|---|---|---|---|---|
| Spotify Track `artists[]` | 保存平台返回的完整有序艺人数组 | 发现标题未标注的合作艺人；建立第一份结构化 provider evidence | 不提供 `primary` / `featured` 角色；平台也可能有误 | **证据层已实现并在隔离副本验收；正式库未发布** |
| MusicBrainz Recording / Artist Credit | 通过 ISRC、recording、release 交叉核对署名 | 提供独立于 Spotify 的第二来源与 credit phrase | 社区数据会有重复、错配或不完整；需遵守客户端标识和限流 | Spotify 证据层稳定后再做样本验证 |
| MusicBrainz Work 语言 | 获取作品层歌词语言候选 | 为曲目语言提供结构化候选证据 | recording 与 work 关系并非总是存在或可靠；作品语言不必然等于具体录音版本 | 仅作为候选证据，不自动批准 |
| Apple Music Catalog | 通过 ISRC 查询歌曲、艺人、封面和类型 | 第三方交叉核验署名与发行元数据 | 需要开发者凭据；同一 ISRC 可能返回多个地区或版本结果 | 在明确收益与凭据运维成本后再评估 |
| Cover Art Archive | 按 MusicBrainz release 获取封面 | 减少对 Spotify 封面的单点依赖 | 必须先可靠解析 release；图片自身版权与可用性另行核验 | 不进入首轮署名工作 |
| 歌词来源 + 本地语言识别 | 识别具体录音的主要语言、混合语言或无歌词 | 支持真正的 track-level language 统计 | 歌词授权、同步歌词噪声、短文本与混合语言识别均需专门评估 | 独立项目，不与署名接入捆绑 |
| Discogs / Wikidata | 处理长尾、人工核验与来源说明 | 为困难案例增加可解释证据 | 结构、许可、覆盖和身份映射差异较大 | 只考虑人工 review 辅助，不作为自动真相源 |

## 4. 已形成的治理原则

### 4.1 外部来源是证据，不是真相覆盖层

- Spotify、MusicBrainz、Apple Music 或其他来源都只能先进入 provider evidence。
- provider evidence 与当前有效事实不一致时，先形成可审计候选或冲突，不直接覆盖正式署名。
- 同一个结论应保留来源、外部稳定 ID、原始名称、获取时间、顺序、匹配方式和冲突状态。
- 无法证明安全时保留 `unknown` 或 review queue，不用名称猜测填满覆盖率。

### 4.2 原始事实与人工治理保持分层

- `plays`、`tracks`、`track_artists` 继续表达导入时的原始事实；新增 Track `artists[]` 证据和后续人工署名治理不得重写它们。现有导入后 metadata 阶段的专辑来源维护是另一个既有流程，不等同于本次证据回填。
- 当前有效署名仍由原始署名、人工 override、canonical artist resolver 共同产生。
- provider evidence 要先证明稳定、幂等、可回滚，再单独规划是否产生人工候选或自动晋升。

### 4.3 身份优先于名称

- ISRC、Spotify track id、MusicBrainz recording id、Apple song id 等只能作为身份证据的一部分；任何一种标识都可能出现重用、版本差异或映射冲突。
- 艺人匹配优先使用 provider external id。名称精确归一化匹配最多生成候选，不自动创建或合并本地艺人。
- 相同显示名称不能代替稳定本地 `artist_id`，跨 provider 的合并必须经过 identity resolver 和冲突检测。

### 4.4 曲目语言与艺人语言是两类事实

- 当前艺人语言规则继续服务艺人级归属，不因新增曲目证据而隐式改变。
- 未来 track-level language 必须以具体录音或歌词证据为主体，保留 `unknown`、`multilingual`、`instrumental` 和未归属时长。
- 艺人的国籍、名称、流派或常用语言不得直接推断某首歌的语言。

### 4.5 暂不提前建设通用 provider 框架

首个落地仅建立 Spotify 专用、可验证的证据表和读取边界。等第二个来源确实进入实施阶段，再从两个真实数据合同中抽取公共 provider interface，避免为了未知来源提前设计复杂抽象。

## 5. 各方向重新启动前的门槛

### 5.1 第二署名来源

只有同时满足下列条件，才开始 MusicBrainz 或 Apple Music 的正式接入计划：

1. Spotify `artists[]` 证据已完成持久化、幂等回填、差异报告和故障保留上一可用证据。
2. 已明确来源条款、署名要求、缓存限制、请求频率、客户端标识和生产凭据管理方式。
3. 使用隔离数据库副本完成分层抽样：单艺人、合作艺人、同名艺人、重制版、现场版、中文名/罗马字名及一 ISRC 多结果。
4. 能用稳定外部 ID 解释匹配，无法匹配的条目进入 `unresolved`，不退化为模糊名称自动合并。
5. 外部请求只由导入后维护、显式刷新或离线回填触发，任何页面 GET 不得同步访问外部来源。

### 5.2 曲目语言

只有同时满足下列条件，才开始 track-level language 设计：

1. 明确统计主体是 recording、track owner 还是歌词版本，并处理 instrumental 与混合语言。
2. 找到许可允许当前产品存储或派生所需信息的歌词/语言来源。
3. 建立带人工复核的标注样本，分别评估中文、英文、粤语、日语、韩语、无歌词和 code-switching。
4. 新事实拥有独立 revision、审计与 unknown 口径，不污染现有艺人语言统计。
5. 年度总结、播放分析和缓存失效的消费者范围已经明确。

### 5.3 封面替代来源

启动前必须明确封面选择优先级、尺寸/格式、缓存和版权展示要求；不得仅因为 URL 可访问就批量镜像或替换当前封面。

## 6. 建议的后续顺序

1. Spotify Track `artists[]` 证据层及隔离副本差异报告已完成，不改变正式署名；正式库发布仍需单独授权。
2. 后续依据已生成的差异报告，确定身份解析与人工核验的优先级。
3. 根据真实差异决定下一项：若主要缺口是署名可信度，优先试验 MusicBrainz；若主要缺口是具体歌曲语言，则单独启动 track-level language 研究。
4. 只有第二来源合同稳定后，才抽取通用 provider evidence 接口。
5. 自动晋升为正式署名、人工审核 UI、语言统计消费和封面替代均各自需要独立规划与授权。

## 7. 明确不在本路线中实施的事项

- 本路线剩余方向不自动授权修改代码、数据库 schema 或生产数据；Track `artists[]` 的独立实施已完成，但没有修改正式数据库。
- 不批量调用 Spotify、MusicBrainz、Apple Music 或歌词服务。
- 不把标题解析结果自动升级为权威署名。
- 不将 `artists[1:]` 一律解释为 `featured`。
- 不修改当前艺人语言统计规则。
- 不承诺某个外部来源一定会进入产品；后续选择以真实样本、许可和运维成本为准。

## 8. 参考入口

- 当前元数据治理规则：[`../reference/music-metadata-management.md`](../reference/music-metadata-management.md)
- 当前艺人语言规则：[`../reference/artist-language-statistics.md`](../reference/artist-language-statistics.md)
- 当前导入与健康规则：[`../reference/data-import-and-health.md`](../reference/data-import-and-health.md)
- MusicBrainz API：<https://musicbrainz.org/doc/MusicBrainz_API>
- MusicBrainz rate limiting：<https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting>
- Apple Music API：<https://developer.apple.com/documentation/applemusicapi/>
- Cover Art Archive API：<https://musicbrainz.org/doc/Cover_Art_Archive/API>

## 9. 停止条件

本路线只保存剩余分析与未来入口。Spotify Track `artists[]` 证据已按独立计划实施并在隔离副本验收；其余方向继续停留在 `PLANNED / DEFERRED`。没有新的明确授权时，不继续做第二来源、曲目语言、封面替代或其他字段的真实 API 回填、schema 设计与实现。

> 2026-10-03 历史候选（`7b9a1f4e`）：两个专辑事项已形成固定专项交付，并从 main `7b9a1f4e` 完成隔离联合集成、默认完整八阶段 PASS 及桌面/手机视口验收；见[联合报告](../reports/2026-10-03-album-metadata-integration-verification.md)。集成版本尚未提交/合入，后续 main 封面变更仍须审阅；正式库迁移、回填和生产验收另行授权。

## 10. 2026-09-24 Spotify 现有字段利用审计：后续问题

以下问题是只读代码与 Spotify 官方接口对账的结果，均不并入 Track `artists[]` 证据接入的当前实施范围；后续按影响量另行排期。

| 优先级 | 问题与当前证据 | 后续处理门槛 |
|---|---|---|
| 高 | Album `artists[]` 包含稳定 Spotify artist id 和名称；`upsert_album_batch()` 当前只把名称拼成 `album_artists` 字符串，`release_cycle_service._verify_album_artists()` 再按逗号拆分并用名称比较。同名、改名和含逗号名称都可能造成错误关联。 | 本地实现已采用有序 Album evidence、稳定 ID/canonical 解析与冲突保留；完成副本验证，待共享文件合入、正式回填及生产验收。 |
| 已完成本地专项 | SS-2026-09-24-001：统一 Album Tracks 完整分页与原子发布；副本 12 条缺页、35 条缺列表已补齐，3 条 50 首边界经核验无缩小总数；2026-10-03 收口旧缓存位置证据，定向补齐 Lana，其余未核验位置明确显示未知。 | [交付报告](../reports/2026-10-02-album-track-pagination-acceptance.md)；本地独立提交交付，未推送/发布，默认完整全栈和真实终端另验。 |
| 中 | Album 返回 `release_date_precision`（年/月/日），当前 `spotify_album_meta` 只保存日期字符串；专辑候选与归并比较无法区分日期精度。 | 先量化部分精度样本和被日期匹配影响的候选，再持久保存 precision 并修正规则。 |
| 中 | 已知 Spotify 专辑/艺人 ID 时 API 对象直接有 `images[]`。当前封面主链已使用它，但缺图兜底会按名称搜索专辑，甚至采用第一个有图结果，可能误配。 | 先统计走名称搜索的比例和错配样本；已有稳定 ID 时优先 ID 读取，不明身份则保留缺图。 |
| 低 | Album Tracks 的每首歌有 `duration_ms`，而 `analysis_stats_service._resolve_album_category()` 用 `total_tracks × 210000` 估算专辑总时长。 | 依赖完整曲目表后，比较估算与真实时长对 LP/EP 分类的影响，再决定是否替换。 |

不要误列为遗漏：Track 的 `duration_ms`、`explicit`、`track_number`、`disc_number`、`external_ids.isrc`、专辑 `album_type`、`total_tracks` 和封面 URL 已被现有元数据表保存。Spotify Track/Album 对象未提供可靠的歌曲演唱语言、`primary`/`featured` 角色或结构化 live/remaster/acoustic 类型；Artist `genres` 已被官方标为 deprecated，Album `genres` 官方说明始终为空，不应作为上述问题的直接替代。

官方参考：[Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)、[Get Album](https://developer.spotify.com/documentation/web-api/reference/get-an-album)、[Get Album Tracks](https://developer.spotify.com/documentation/web-api/reference/get-an-albums-tracks)、[Get Artist](https://developer.spotify.com/documentation/web-api/reference/get-an-artist)。

2026-10-03 最终恢复：`SS-2026-09-24-001/002` 已以 `8464ffa6` 与封面主线整合，新默认完整全栈与两视口专项通过；已吸收封面收口 `85a44cb8` 并安全合入本地 main，未推送本任务/部署，正式迁移/回填仍需独立授权。见[最终报告](../reports/2026-10-03-album-metadata-final-integration.md)。日期精度 `003` 未实施。
