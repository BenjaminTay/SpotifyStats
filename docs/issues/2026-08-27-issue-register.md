# SpotifyStats 问题台账

> 状态：持续维护
> 首次建立：2026-08-27
> 最后核验：2026-08-27
> 当前工作区：歌曲身份、归并与版本管理仍在开发中；本台账不把当前 dirty worktree 当作已发布结果。

## 当前开放与未闭环事项

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
|---|---|---|---|---|
| `SS-2026-08-27-001` | 播放排行同播放次数时的第二排序不明确，当前没有按时长降序 | `OPEN` · 已复现，未修改 | `/api/analysis/charts` 的聚合排序为 `plays` 后再次排序 `plays`；当前真实接口中歌曲榜出现同为 180 次但时长为 8.62h、11.87h 的相邻条目，故不是按时长排序。见 [`analysis_stats_service.py`](../../backend/services/analysis_stats_service.py)。 | 先确定产品规则；建议明确为“播放次数降序 → 收听时长降序 → 稳定 ID/名称”，再补服务端和分页回归测试。 |
| `SS-2026-08-26-002` | 设置重建状态、导入健康口径、历史残留治理和导入前比较语义尚未整体收口 | `IN_PROGRESS` · 方案已写，当前工作区有相关改动，但未完成独立验收 | 方案仍标记“待实施”，且上一轮没有真实 UI 验收；当前 checkout 已出现相关后端/设置组件改动，因此不能再写成“完全未开始”。见 [`settings-rebuild-and-data-governance-remediation-plan.md`](../plans/2026-08-26-settings-rebuild-and-data-governance-remediation-plan.md)。 | 等歌曲身份/归并改动稳定后，单独完成 API、真实数据库副本、浏览器和清理预览门禁；实际清理仍需另行授权。 |
| `SS-2026-08-10-003` | Billboard 冠军圣殿曾出现 Taylor Swift 28 首与详情 34 首不一致，最终 ID 集合对账没有闭环 | `OPEN` · 已定位链路，未确认根因已解决 | 历史调查已定位 Records 与艺人详情使用不同计算链，但没有保存同参数原始响应并完成 ID 集合差异；当前仓库也没有这项 28/34 的最终交付报告。当前歌曲身份迁移可能改变结果，不能沿用旧数字。 | 在当前 canonical track/归并语义稳定后，固定全部过滤参数、cache revision，重新比较 Records 与详情的原始字段及实体 ID 集合。 |
| `SS-2026-08-24-004` | 全栈总门禁的 25 分钟目标与低干扰环境连续三次稳定运行尚未达成 | `PARTIAL` · 工程验收尾项 | 两次完整运行约 27:48、29:07，另一次遇到 API 性能尾部尖峰失败；后续 34:08 的通过轮受共享主机负载干扰，不能作为稳定基线。见 [`fullstack-gate-duration-optimization.md`](../reports/2026-08-24-fullstack-gate-duration-optimization.md)。 | 只在可控负载窗口重新执行三次默认完整门禁并记录阶段耗时；不通过删减覆盖或放宽阈值换取达标。 |
| `SS-2026-08-06-005` | PWA/移动网页完成后，iPhone Safari 与 Android Chrome 真机安装、返回、安全区和 OAuth 验收仍未完成；Capacitor 尚未决策 | `PARTIAL` · 路线尾项 | 当前规划明确写为等待真机验收，不能把本地浏览器验收当作真机完成。见 [`appification-pwa-capacitor-plan.md`](../plans/2026-08-06-appification-pwa-capacitor-plan.md)。 | 有真实设备和 HTTPS/认证条件后再做真机验收；在此之前不宣称已完成 App 化。 |
| `SS-2026-06-23-006` | 播放记录历史规划与当前 `/analysis/records` 实现仍需重新核对 | `OPEN` · 文档核对项，暂不等同于代码缺陷 | 规划文件本身标记“待核对”，而 2026-08-02 的播放记录 UI 修复已有独立实现和验收记录；因此需要做“规划—当前实现—交付证据”的差异清单，而不是直接重做功能。见 [`playback-records-plan.md`](../plans/2026-06-23-playback-records-plan.md)。 | 后续以当前 API、页面和交付报告逐项核对，确认差异后再决定是否需要代码修改。 |

## 本次排序核查：已确认的规则

### 播放排行：当前确实不是按时长解决同次数

播放排行页面是 [`AnalysisChartsPage.tsx`](../../frontend/src/pages/AnalysisChartsPage.tsx)，调用 `/api/analysis/charts`。服务端当前排序逻辑为：

```text
metric=plays  : plays DESC, plays DESC
metric=hours  : hours DESC, plays DESC
```

因此：

- 选择“播放次数”时，同次数条目的第二键实际上仍是同一个 `plays`，没有时长键，也没有显式的稳定 ID/名称键。
- 这不等于代码主动随机排序，但同值条目的顺序依赖上游 DataFrame 分组和排序实现，当前没有对用户承诺的稳定 tie-breaker。
- 选择“播放时长”时，才是 `hours DESC`，播放次数作为第二键。

当前真实接口快照（默认过滤、L2、lifetime）还观察到：歌曲榜第 11/12 名都为 180 次，但分别为 8.62h 和 11.87h；这直接排除了“同次数按时长从高到低”的解释。

### Billboard 周榜：同播放次数会按总收听时长降序

Billboard 周榜的单曲、专辑和艺人排名共用 [`chart_ranking.py`](../../backend/domains/billboard/chart_ranking.py) 的 `_stable_weekly_sort()`，规则是：

```text
billboard_week ASC → play_count DESC → total_ms DESC → 稳定 ID ASC → 标准化名称 ASC
```

所以 Billboard 周榜不是随机的：同周同播放次数时，`total_ms`（总收听毫秒数）更高者排名更前；如果连时长也相同，再用 ID/名称稳定区分。当前真实周榜 `2026-08-14` 的歌曲、专辑和艺人数据均符合这一规则。

> 注：Billboard All-time/Power Score 是另一套累计评分排名，不能简单套用“周榜播放次数 + 时长”的解释；如要核对该页面，应单独记录其评分与 tie-breaker。

## 已确认解决或不再作为开放问题

以下事项有后续交付证据，因此不应从旧提问清单中再次当作“未解决”提出：

- 年度总结的 `Manchild/1000`、重复“今年听歌最多的一天”、首次发现和跨章节分母/身份语义问题，已在 [`2026-08-24-yearly-review-semantic-correction.md`](../reports/2026-08-24-yearly-review-semantic-correction.md) 标记为年度修复范围 Pass。
- Billboard 周榜同次数排序本身不是随机行为；当前代码和稳定排序单测已经覆盖单曲、专辑、艺人及输入顺序打乱场景。见 [`test_billboard_stable_ranking.py`](../../backend/tests/unit/test_billboard_stable_ranking.py)。
- 音乐详情加载、专辑/艺人子榜错误空态、专辑发行日期版本消歧、艺人专辑排行日期聚合、Billboard 艺人预聚合逻辑事件粒度和搜索候选/统计解耦，都已有对应交付报告或回归证据；后续若再次出现症状，应按当前代码和真实数据重新复核，不直接复用旧结论。

## 更新记录

| 日期 | 变化 |
|---|---|
| 2026-08-27 | 首次建立台账；登记历史未闭环项；确认播放排行同次数不按时长排序；确认 Billboard 周榜按 `total_ms` 作为第二排序。 |
