# Artist Genre Taxonomy 与 Settings 审计面板

## 背景

Spotify Web API 对部分艺人不返回 genre；即使返回，也常见粒度重叠或地域标签混入风格标签的问题，例如 `mandopop`、`c-pop`、`taiwanese pop`、`cantopop` 在统计上并不应该被当成四个互斥流派。直接把 Spotify raw genre 用进年度总结、账号收藏画像或 AI 问答，会让流派分布被拆碎，也会让缺失艺人被低估。

当前方案把 genre 数据分成三层：

| 层级 | 作用 | 是否直接用于统计 |
|------|------|------------------|
| Source genre | Spotify、人工种子、手动覆盖、外部来源或 LLM 审核建议给出的原始标签 | 否，保留作审计和溯源 |
| Resolved artist genre | 单个艺人最终采用的一组标签；Spotify 有值时优先 Spotify，Spotify 缺失时才用本地已审核来源 | 是，但进入统计前还会标准化 |
| Statistical genre | 面向图表和报告的 canonical 标签，例如 `pop`、`r&b/soul`、`country` | 是 |
| Label axis | 对 canonical 标签补充维度说明，例如 `style`、`scene`、`context`、`role` | 用于解释和审计 |

## 来源优先级

艺人最终 genre 由 `backend/domains/metadata/artist_genres.py` 的 `resolve_artist_genres_map()` 统一解析：

1. Spotify genre 非空时直接采用 Spotify，`source=spotify`，置信度视为 1.0。
2. Spotify 缺失时，优先使用 `artist_genre_overrides` 的手动覆盖。
3. 仍缺失时，从 `artist_genre_sources` 里选择 `status=approved` 的最佳来源，按 `curated_seed`、`external_consensus`、`musicbrainz`、`lastfm`、`wikidata`、`llm` 的优先级和置信度排序。
4. `status=suggested` 的 LLM 或外部建议不会直接进入统计，必须在 Settings 审核通过后才会被采用。

`curated_seed` 是本地维护的种子数据，不等同于官方来源；`llm` 是模型建议，也不等同于官方来源。Last.fm、MusicBrainz、Wikidata 只能作为外部参考证据，最终仍以“已审核本地 fallback”的身份进入系统。

## 统计标准化

统计层由 `canonicalize_genres_for_statistics()` 负责，把 raw labels 折叠到稳定标签集合。v2 以后，canonical 标签不再假装全是同一类“风格”，而是带有 axis：

| Axis | 作用 | Examples |
|------|------|----------|
| `style` | 音乐风格主体 | `pop`, `rock/alternative`, `r&b/soul`, `country`, `folk`, `americana/roots` |
| `scene` | 语言、地区或市场场景 | `c-pop`, `k-pop`, `j-pop`, `latin` |
| `context` | 使用场景、媒介或内容来源 | `soundtrack/stage`, `holiday` |
| `role` | 创作/表演身份或表达方式 | `singer-songwriter` |

代表性映射：

- `mandopop`、`c-pop`、`taiwanese pop`、`cantopop`、`hong kong pop` -> `c-pop`
- `chinese r&b` -> `c-pop` + `r&b/soul`
- `latin pop` -> `latin` + `pop`
- `indie rock` -> `rock/alternative` + `indie/alternative`
- `singer-songwriter` -> `singer-songwriter`
- `folk`、`folk pop`、`folk rock`、`indie folk` -> `folk`，并按混合标签分摊到 `pop`、`rock/alternative` 或 `indie/alternative`
- `country`、`country pop` -> `country`
- `americana`、`bluegrass`、`roots rock` -> `americana/roots`
- `musicals`、`musical theatre`、`score`、`soundtrack` -> `soundtrack/stage`

一个艺人可以落到多个 canonical genre。统计播放时长时，系统先按 axis 分组，再只在同一 axis 内平均分摊：`style`、`scene`、`context`、`role` 各自独立计算覆盖率和构成，因此跨轴标签不会互相稀释；同一轴内的多标签也不会重复计算成超过 100%。例如 `latin pop` 的同一段播放时长会分别完整进入 scene 轴的 `latin` 与 style 轴的 `pop`，而不是各算一半。

## 消费展示 taxonomy（consumer_v1）

底层四轴 taxonomy 是治理和审计事实，不直接等同于普通用户看到的图表。`backend/domains/metadata/genre_display_taxonomy.py` 提供显式、版本化、可回滚的消费映射；当前版本为 `consumer_v1`，不会写回或覆盖 Spotify raw genre、approved source 或人工 override。

年度总结只展示三个并列视角：

- **主曲风**：只消费 `style`。`rock/alternative` 显示为 Rock，`indie/alternative` 显示为 Indie，`r&b/soul` 显示为 R&B / Soul；`electronic/dance` 仅在原始标签明确支持时拆为 Electronic、Dance 或 Ambient。
- **地区流行**：只消费 `scene`，例如 C-Pop、J-Pop、K-Pop、Latin。它与主曲风不是互斥分类，同一段华语 R&B 聆听可以分别进入 C-Pop 与 R&B / Soul。
- **语言**：继续使用独立的 approved artist-language facts 和主艺人归属，不从 genre 或 Music Map 推断。

每个轴保留多标签语义，艺人时长只在同一 display axis 内平均分摊；百分比分母为全部可归属的有效聆听时长，未取得对应标签的部分显示为“尚未归类”。`context` / `role` 仍可在 Settings 审计，但不进入年度主图，避免 Singer-Songwriter 等单一 role 形成误导性的 100% 偏好。播放统计页不展示这一消费模块。

Music Map 仍是 genre/region heuristic，不是艺人国籍、语言或可靠地区事实；当前从年度消费页隐藏，底层字段保持兼容。`GENRE_DISPLAY_TAXONOMY_VERSION` 必须进入 Wrapped、AI 报告及相关消费缓存键；genre、language、identity 或 track-credit revision 变化后，相应查询也必须失效。

## Settings 审计面板

Settings 页的 **Genre 数据健康** 面板现在提供两类审计：

- 覆盖率审计：已知/待补播放时长、来源占比、Top 缺失艺人、待审核建议和小批量补全任务入口。
- 统计口径审计：Raw 标签数量、Canonical 标签数量、非标准透传数量、Top canonical genres、axis、source mix、Top driving artists、dominance warning、Raw -> canonical 映射样例。

`非标准透传` 应长期接近 0。若出现非 0，说明有 raw genre 没被 taxonomy 归并，统计结果可能重新碎片化，应该补充 `STATISTICAL_GENRE_MAP` 或确认它确实应成为新的 canonical 标签。

但 `非标准透传 = 0` 只说明 raw 标签都被映射了，不代表分类语义已经合理。Settings 还会显示 dominance warning：当一个 canonical label 被单个艺人贡献 70% 以上时，UI 和 AI 回答必须把它解释成“由某个高播放艺人驱动”，而不是泛化成整体偏好。

### 2026-07-05 第 1+2 层修复

本次先落地展示口径和风险信号，不进入 album/era override：

- `GET /api/metadata/artist-genres/taxonomy` 新增 `axis_summary`，按 `style`、`scene`、`context`、`role` 汇总播放时长、占比、canonical label 数量和解释文案。
- Top canonical genre 行新增 `interpretation`、`confidence_tier` 和结构化 `risk_flags`。
- `confidence_tier` 根据 source mix 计算；Spotify、人工种子和手动覆盖权重较高，LLM 权重较低。当某个标签主要由 LLM 或其他低可信来源支撑时，`risk_flags` 会包含 `source_confidence`。
- 单艺人贡献 70% 以上时，`risk_flags` 会包含 `single_artist_dominance`，沿用 dominance warning 的解释，但变成结构化字段，方便 UI 和 AI 消费。
- Settings 审计面板不再把 canonical genre 混成一个榜，而是分成“风格 / 场景 / 语境 / 身份”四类；例如 `c-pop` 进入“场景”，`singer-songwriter` 进入“身份”。
- Wrapped genre panorama 复用同一 caveat，明确 scene/context/role 不是纯声音风格，低可信来源或单一艺人主导标签需要降置信解读。

仍未解决的是 artist-level genre 对跨时期艺人的天然过粗问题。Taylor Swift 这类艺人的 country / singer-songwriter 影响仍需要后续 album-level 或 era-level override 才能从根上修复；本次只确保 UI 和 AI 不再把这些标签过度泛化。

对应 API：

- `GET /api/metadata/artist-genres/coverage`
- `GET /api/metadata/artist-genres/taxonomy`
- `GET /api/metadata/artist-genres/reviews`
- `PATCH /api/metadata/artist-genres/reviews/{review_id}/evidence`
- `POST /api/metadata/artist-genres/reviews/{review_id}/approve`
- `POST /api/metadata/artist-genres/reviews/{review_id}/reject`

## 2026-07-15 当前数据快照

按 Settings 默认过滤口径重新计算：

- Source genre 已知时长：4011.0h，原始标签覆盖率 100%。这只代表每位已归属艺人都有 source genre，不代表每个标签都能解释成声音风格。
- Style 轴覆盖率：72.6%，未知 27.4%；Scene 轴 32.9%；Context 轴 4.2%；Role 轴 30.2%。四个轴独立统计，未知时长不会被隐藏。
- Style 轴 Top 构成：Pop 55.0%、Country 18.8%、R&B / Soul 9.6%、Rock / Alternative 7.2%、Indie / Alternative 3.7%。这些百分比是 style 已知时长内部构成，不等同于全部播放时长占比。
- 主要来源时长：Spotify 2009.0h、curated seed 1263.0h、LLM approved 739.0h。来源置信度会同时乘以该行自身 confidence；缺少证据 URL、LLM 占比过高或单一艺人主导都会触发风险标记并限制最高置信度。

年度总结通过 `consumer_v1` 分别展示 style 的“主曲风”、scene 的“地区流行”和独立语言分布；`context`、`role` 只保留在 Settings 治理层。Settings 继续保留 raw -> canonical 映射、来源、证据覆盖、Top driving artists 和审核历史，供维护者复核。

## 2026-07-04 历史数据快照

以下是旧版跨轴分摊逻辑的历史结果，仅用于对比，不应再作为当前口径：

- Raw genre labels: 230
- Canonical genre labels: 26
- Noncanonical passthrough: 0
- Unknown artist genre hours: 30.9h，约占 lifetime 播放时长 0.8%

Settings taxonomy audit 的 lifetime Top canonical genres：

| Genre | Axis | Share | Dominance |
|-------|------|-------|-----------|
| pop | style | 33.0% | - |
| c-pop | scene | 26.3% | - |
| singer-songwriter | role | 10.7% | Taylor Swift contributes 79.6% |
| country | style | 9.3% | Taylor Swift contributes 90.8% |
| r&b/soul | style | 4.6% | - |
| rock/alternative | style | 4.4% | - |
| holiday | context | 2.3% | Mariah Carey contributes 72.4% |
| indie/alternative | style | 1.7% | - |
| folk | style | 0.7% | - |

这说明 v2 taxonomy 已经把 `singer-songwriter/folk` 和 `country/americana` 拆开，但也暴露了新的解释风险：`singer-songwriter` 与 `country` 在当前 lifetime 数据里高度受 Taylor Swift 的 curated fallback 标签驱动。因此报告和 AI 回答应把这两个结果解释为 dominance-sensitive，而不是直接说“整体偏好明显偏 country / folk”。

## High-Impact Artist Policy

当一个艺人贡献某个 canonical label 至少 70% 时，该 label 视为 dominance-sensitive。数据可以保留，但 UI、年度报告和 AI 回答必须使用保守措辞，例如“这个标签主要由 Taylor Swift 驱动”，而不是泛化为稳定、广泛的个人流派偏好。

对于跨时期艺人，`country pop` 这类时代相关标签不应默认套到该艺人的全部播放。如果缺少 track/album-level genre 证据，应优先保守使用艺人级 fallback，并让 dominance warning 暴露风险。后续若接入 track/album-level enrichment，再把 era-specific genre 下沉到更细粒度。

## 验证命令

```bash
.venv/bin/python -m pytest backend/tests/contract/test_artist_genre_metadata_api.py::test_artist_genre_metadata_api_returns_taxonomy_audit -q
cd frontend && npm test -- genre-data-health-section
```

发布前建议继续跑 genre 相关聚焦矩阵：

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/contract/test_artist_genre_metadata_api.py backend/tests/contract/test_artist_genre_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py -q
.venv/bin/ruff check backend/domains/metadata/artist_genres.py backend/models/artist_genre_metadata.py backend/api/artist_genre_metadata.py backend/services/wrapped_service.py
cd frontend && npm run build
```
