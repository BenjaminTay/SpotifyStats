# Genre Axis Supplement 与 Metadata 预审核设计

## 目标

在不覆盖 Spotify 原始标签、不从 genre 推断语言、也不自动批准 AI 候选的前提下：

- 允许 approved 本地 genre source 只补 Spotify 缺失的 axis。
- 在 Settings 暴露按播放时长排序的 `style` 缺失队列。
- 为 genre 与 language review 增加 Codex 首轮审核信息，但保持 review 为 `open`。
- 首批补全 6 位高影响 style 缺失艺人，并分两批预审核 69 位语言未知艺人。

## 当前基线

默认过滤口径为 `min_ms=30000`、`music_only=true`、`merge_enabled=true`、
`dynamic_threshold=true`、`max_merge_gap_minutes=NULL`：

| 指标 | 基线 |
| --- | ---: |
| Genre source 覆盖率 | 100.0% |
| Genre style 覆盖率 | 72.6% |
| Genre style 未知时长 | 1098.4h |
| Language 覆盖率 | 95.37% |
| Language 未知时长 | 185.56h |
| Language 未知艺人 | 619 |

## Genre 按轴解析

Spotify 与本地 source 都先 canonicalize，再按 `style`、`scene`、`context`、`role`
分组。每个 axis 独立选择来源：

1. Spotify 在该 axis 有 canonical 标签时，使用 Spotify。
2. Spotify 在该 axis 没有标签时，允许使用最佳 approved 本地 source 的该 axis 标签。
3. suggested、open、pre-reviewed、rejected source 均不得进入统计。
4. 本地 source 不得通过 `c-pop -> pop`、`holiday -> pop` 等跨轴启发式产生 style。
5. 同一 axis 多标签平均分摊，跨 axis 不分摊。

Resolved 结果保留原始 Spotify genres，并额外携带每个 axis 的标签、来源、置信度和证据，
避免把本地 canonical 补充伪装成 Spotify raw genre。

## Axis Gap

`GET /api/metadata/artist-genres/axis-gaps` 接受 PlayFilters、`axis` 和 `limit`，返回：

- `artist_name`、`hours`
- Spotify/raw genres 与已解析的其他 axis
- 当前 source、confidence、evidence
- 是否已有 open review 与 Codex 预审核结论

Settings 卡片 06 在 Genre 审核中增加“轴缺失”视图，默认 `style`，不得新增顶级页面。

## Codex 首轮审核

Genre 与 language review queue 增加：

- `pre_review_recommendation`
- `pre_review_confidence`
- `pre_review_note`
- `pre_reviewed_by`
- `pre_reviewed_at`

推荐值固定为：

- `recommend_approve`
- `manual_review`
- `insufficient_evidence`
- `recommend_reject`

预审核 mutation 只允许更新 open review，不改变 source/review status，不进入统计，也不写
`reviewed_by`/`reviewed_at` 终态字段。用户最终动作继续走既有 approve/reject/
insufficient-evidence state machine。

## 证据规则

- LLM 文本不是 evidence；必须提供可访问的 HTTPS 外部来源。
- 官方艺人、唱片公司、作品 credits 或可靠编辑来源优先。
- MusicBrainz/Wikidata 可用于交叉验证，不以无上下文 tag 单独支持高影响结论。
- 国籍、地区、市场、艺人姓名和 genre 不能证明演唱语言。
- `multilingual` 需要至少两个不同语言或 variant 的艺人级演唱证据。
- 音乐剧和合辑必须核对实际表演者，不能按作曲者或专辑默认艺人归属。
- 单一候选影响超过总时长 2%，或预计令 canonical share 改变超过 3 个百分点时，标记
  `manual_review`，即使证据完整也需要用户最终确认。

## 审核批次

Genre G1：Michael Wong、Stefanie Sun、A-Mei Chang、Fish Leong、JJ Lin、G.E.M.。
候选合计约 816h，全部通过且至少补一个 style 时，理论覆盖率约 92.9%。

Language L1：按未知时长前 32 位，预计覆盖率约 97%。

Language L2：继续后 37 位，总计 69 位，预计覆盖率约 98%。

每条候选先由 Codex 查证并写 pre-review；导入后全部保持 `open`。用户最终批准前，
覆盖率不得发生变化。

## 验收

- 预审核前后 genre/language 统计完全相同。
- 用户批准后，只有对应 axis 或 language bucket 改变。
- Genre style 覆盖率目标 `>=90%`，Language 目标 `>=98%`，但不得强行达到 100%。
- 所有新增终态 fact 都有 HTTPS evidence、reviewer、reviewed_at 和 resolution_note。
- 后端、前端、OpenAPI、迁移、真实数据库重算和 Settings 双视口 UI 验收通过。
