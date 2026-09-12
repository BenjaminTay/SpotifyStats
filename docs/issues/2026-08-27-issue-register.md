# SpotifyStats 问题台账

> 状态：持续维护
> 首次建立：2026-08-27
> 最后核验：2026-09-01
> 最近核验基线（2026-09-01）：播放次数/全部收听时长双轨后端改动已提交为 `911256f1`；尚未 push，也没有对应生产部署证据。后续文档提交不得反向表述为业务代码已发布。

## 当前开放与未闭环事项

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
|---|---|---|---|---|
| `SS-2026-08-24-004` | 全栈总门禁时间过长，且并发性能竞争、冷建等待和失败后整轮重跑放大交付成本 | `PARTIAL` · 工程验收尾项 | 早期完整运行约 27:48、29:07，后续受负载影响的通过轮为 34:08。2026-09-01 的 L2/L3 交付验收中，后端 2,542 项约 21–29 分钟，API 阶段约 14–16 分钟；并发任务曾造成接口超时和 871ms 热 P95，无竞争时恢复到 240ms 内。两个 Desktop 页面首次冷建又因内容 marker 等待超时触发整轮重跑；固定 summary 路径还会被其他工作区覆盖。见 [`fullstack-gate-duration-optimization-plan.md`](../plans/2026-08-24-fullstack-gate-duration-optimization-plan.md)。 | 依次实施廉价 preflight、跨工作区 benchmark lock、run-id summary、冷建/readiness 分层、`pytest --durations=100` 剖析与安全并行；再设计严格 evidence manifest 的失败阶段续跑。保持覆盖、三浏览器和 500ms 阈值不变。 |
| `SS-2026-08-06-005` | PWA/移动网页完成后，iPhone Safari 与 Android Chrome 真机安装、返回、安全区和 OAuth 验收仍未完成；Capacitor 尚未决策 | `PARTIAL` · 路线尾项 | 当前规划明确写为等待真机验收，不能把本地浏览器验收当作真机完成。见 [`appification-pwa-capacitor-plan.md`](../plans/2026-08-06-appification-pwa-capacitor-plan.md)。 | 有真实设备和 HTTPS/认证条件后再做真机验收；在此之前不宣称已完成 App 化。 |
| `SS-2026-08-31-001` | Billboard 周榜的 30 秒阈值、连续合并后余数和同次数 `total_ms` 是否应分成“次数轨/时长轨” | `RESOLVED` · 本地实施与验收完成 | 后端已按“阈值只约束 `play_count`、`total_ms` 统计全部有效音乐收听区间”实现，前端字段与文案未改。提交 `911256f1`；真实 Online Backup 副本完成聚合与四套搜索快照重建，曲目/专辑/艺人即时计算对预聚合均为 0 差异，真实 API 证明允许 0 次且有时长，但 Billboard 最小入榜次数仍为 1。详见 [`2026-08-31-billboard-count-duration-semantics-research.md`](../reports/2026-08-31-billboard-count-duration-semantics-research.md)。 | 本地规则已闭环；如需发布，另按生产发布流程使用数据库副本重建并留存 deploy、服务器 SHA、health 与 runtime gate 证据。 |

## 排序规则：当前实现

### 播放排行：同次数按时长和稳定实体键排序

播放排行页面是 [`AnalysisChartsPage.tsx`](../../frontend/src/pages/AnalysisChartsPage.tsx)，调用 `/api/analysis/charts`。2026-08-29 修复后的服务端排序逻辑为：

```text
metric=plays  : plays DESC, hours DESC, stable entity key ASC, normalized name ASC
metric=hours  : hours DESC, plays DESC, stable entity key ASC, normalized name ASC
```

歌曲、专辑、艺人均按各自稳定实体键排序；跨越同分组的 offset/limit 也不依赖输入顺序。当前真实接口默认过滤、L2、lifetime 样本中，歌曲榜第 11/12 名同为 180 次，11.9h 的 `drivers license` 排在 8.6h 的 `Midnight Rain` 之前。

### Billboard 周榜：同播放次数会按总收听时长降序

Billboard 周榜的单曲、专辑和艺人排名共用 [`chart_ranking.py`](../../backend/domains/billboard/chart_ranking.py) 的 `_stable_weekly_sort()`，规则是：

```text
billboard_week ASC → play_count DESC → total_ms DESC → 稳定 ID ASC → 标准化名称 ASC
```

所以 Billboard 周榜不是随机的：同周同播放次数时，`total_ms`（总收听毫秒数）更高者排名更前；如果连时长也相同，再用 ID/名称稳定区分。当前真实周榜 `2026-08-14` 的歌曲、专辑和艺人数据均符合这一规则。

> 注：Billboard All-time/Power Score 是另一套累计评分排名，不能简单套用“周榜播放次数 + 时长”的解释；如要核对该页面，应单独记录其评分与 tie-breaker。

### Billboard Records：所有同值列表使用业务二级键

2026-08-30 复核了 `/api/billboard/records` 和 `/api/billboard/data` 的 6 个 Records 子页面、8 个后端记录模块、共 51 个列表。冠军圣殿的冠军名人堂已拆成独立的单曲/专辑候选集：单曲按“冠军单曲数 DESC → 单曲冠军周数 DESC”，专辑按“冠军专辑数 DESC → 专辑冠军周数 DESC”，只有对应数量大于 0 的艺人进入榜单。其他记录列表也按各自的日期、周数、Peak、走势评分、播放差额或实体数量等业务指标补齐二级/后续排序，最后使用稳定实体键；完整规则见 [`playback-stats-rules.md`](../reference/playback-stats-rules.md) 的 R39.1。

排序实现会先对完整候选集排序再截断 Top N，因此 cutoff 同值行不会因为 groupby、缓存重建或输入行顺序变化而交换。固定参数和同一 revision 下，两个 Records 接口各 51 个列表的排序巡检均为 0 个违规；这次补充仍不改变 Billboard 周榜的播放次数/总时长排序规则。

## 已确认解决或不再作为开放问题

以下事项有后续交付证据，因此不应从旧提问清单中再次当作“未解决”提出：

- `SS-2026-08-27-001`：播放排行同次数排序已解决。播放次数榜现在按 `plays DESC → hours DESC → stable entity key → normalized name`，播放时长榜保留 `hours DESC → plays DESC` 后追加稳定键；歌曲、专辑、艺人及跨同分分页的乱序输入测试通过，真实 180 次样本为 11.9h 在 8.6h 前。该修复没有修改 Billboard 周榜规则。见 [`2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- `SS-2026-08-26-002`：设置重建状态、导入健康口径、只读治理预览和导入前比较语义已解决。功能范围、真实主库只读探针、Desktop/390px 浏览器、完整 unit/contract 和前端回归已通过，修复提交为 `62f48299`；后续 descendant `dc7055a7` 又通过默认完整全栈门禁。业务修复提交 `0b23c442` 未重新运行默认完整门禁，且审计时的 7 个本地业务提交均未 push；历史数据实际清理仍是独立授权事项。见 [`交付报告`](../reports/2026-08-27-settings-rebuild-and-data-governance-remediation.md)。
- `SS-2026-06-23-006`：播放记录历史规划与当前实现的文档核对已完成。当前 `/api/analysis/records`、路由容器、TanStack Query、5 个栏目和 20 个模块均已存在，并有 Phase 5、移动端与播放记录专项验收；历史规划已补“最终实现差异”并归档。早期 6 栏方案和未采用 P2 只用于回溯，不自动成为当前缺陷或待办。见 [`归档规划`](../archive/06-productization-closeout/2026-06-23-playback-records-plan.md)。
- `SS-2026-08-10-003`：Billboard 冠军圣殿与艺人详情的冠军单曲数不一致已解决。2026-08-29 的实施与验收基线为 detached HEAD `c21ad22841dcc98b3ce7fa20c9306d4830a1da15`，最终修复已在本地提交为 `0b23c442`；schema 63、同一主库和不变 revision 下，固定 `min_ms=30000`、仅音乐、连续播放合并、5 分钟间隔、周五 12:00 周边界、`30/20/20` 榜单规模、无年度范围及不含精选集，并覆盖 L2/L3 × dynamic/fixed 四个变体；Taylor Swift 在 Records、`artist_track_counts.top1`、艺人详情 `info.top1`、详情冠军曲和周榜有效署名中的结果均为 34，稳定 `track_id` 集合差集为空，301 首上榜歌曲逐行指标差异为 0。覆盖边缘开放周 `2026-08-21` 未发布。2026-08-30 又完成全部 51 个 Records 列表的二级排序和冠军专辑独立候选集收口，并提交为 `46fc7afa`；`0b23c442` 与 `46fc7afa` 均尚未 push、未部署，默认完整全栈门禁未在本次 HEAD 上运行。见 [`交付报告`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- 年度总结的 `Manchild/1000`、重复“今年听歌最多的一天”、首次发现和跨章节分母/身份语义问题，已在 [`2026-08-24-yearly-review-semantic-correction.md`](../reports/2026-08-24-yearly-review-semantic-correction.md) 标记为年度修复范围 Pass。
- Billboard 周榜同次数排序本身不是随机行为；当前代码和稳定排序单测已经覆盖单曲、专辑、艺人及输入顺序打乱场景。见 [`test_billboard_stable_ranking.py`](../../backend/tests/unit/test_billboard_stable_ranking.py)。
- 音乐详情加载、专辑/艺人子榜错误空态、专辑发行日期版本消歧、艺人专辑排行日期聚合、Billboard 艺人预聚合逻辑事件粒度和搜索候选/统计解耦，都已有对应交付报告或回归证据；后续若再次出现症状，应按当前代码和真实数据重新复核，不直接复用旧结论。

## 更新记录

| 日期 | 变化 |
|---|---|
| 2026-08-29 | 完成播放记录规划与当前 5 栏/20 模块实现的差异核对并归档，将 `SS-2026-06-23-006` 更新为已解决。 |
| 2026-08-29 | 同步仓库与验证状态：Billboard 修复已本地提交为 `0b23c442`，Settings 修复已提交为 `62f48299`，均未 push；Settings 移入已解决，播放记录文档核对随后完成并归档。 |
| 2026-08-29 | 完成 Billboard B1–B4 与独立播放排行 R1 的实现、完整 backend unit/contract、frontend test/build、真实库副本/主库 proof 和响应式验收；默认完整全栈门禁未在 `0b23c442` 上运行。将 `SS-2026-08-27-001` 更新为已解决。 |
| 2026-08-29 | 为 Billboard 次要一致性问题和独立播放排行 tie-breaker 建立分阶段修复规划。 |
| 2026-08-29 | 将 `SS-2026-08-10-003` 更新为已解决：在实施基线、真实数据库、固定参数与同一 revision 下完成 Records/艺人详情四变体的稳定实体 ID 集合、计数、排序和逐行指标对账，Taylor Swift 均为 34，差集为空。 |
| 2026-08-30 | 复核 6 个 Records 子页面、8 个后端记录模块的全部 51 个列表，补齐业务二级/后续指标和稳定实体键；冠军专辑候选集只保留 `冠军专辑数 > 0` 的艺人，并同步更新当前规则、计划与交付报告。 |
| 2026-08-27 | 首次建立台账；登记历史未闭环项；确认播放排行同次数不按时长排序；确认 Billboard 周榜按 `total_ms` 作为第二排序。 |
