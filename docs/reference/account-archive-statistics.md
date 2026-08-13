# 音乐档案统计规则

版本：`account_archive_filter_v1` / `account_archive_cohorts_v1_0`
日期：2026-08-13

## 1. 适用范围

本文约束 `/api/account/collection-journey` 与 `/api/account/collection-cohorts`。音乐档案只分析本地导入数据，不在读取或计算时调用 Spotify Web API。

`YourLibrary.json` 是“导出时仍在收藏”的当前快照，不包含取消收藏历史。因此本文中的“收藏”始终指 **当前仍在收藏的曲目**；回访率不能解释为全部历史收藏的留存率，也不能用于推断收藏行为造成了后续播放。

## 2. 时间与播放事件

- `saved_tracks.added_date` 与 `plays.ts` 都按 UTC ISO 时间戳比较。
- Spotify Extended Streaming History 的 `ts` 表示播放停止时间。关系窗口使用 `event_at = ts - ms_played` 近似逻辑播放开始时间，避免把用户按下收藏时正在播放的同一次事件计作“收藏后再次播放”。
- 日期、季度和普通 UI 日期按 `Asia/Shanghai` 展示。
- 观察期锚定数据库原始播放的 `MIN(ts)` / `MAX(ts)`，不使用服务器今天。
- `latest_play_date` 是 `MAX(ts)` 转换为北京时间后的自然日。

连续片段先调用全局 `merge_consecutive_plays()`，再调用 `filter_effective_plays()` 应用静态或动态阈值。若一个合并组产生多个逻辑播放，现有全局合并器只保留组首时间；关系统计因此采取保守时间定位，不为缺失的组内时间编造事件时间。

## 3. 实体粒度与匹配

1. 收藏歌曲先按 `spotify_track_id`，再按 Spotify URI 匹配本地 `tracks.track_id`。
2. 无法匹配的收藏保留在覆盖率和“无法关联”数量中，不进入播放关系分母。
3. L1 使用本地 `track_id`；L2/L3 调用 `load_track_group_keys()` 映射到规范录音/作品。
4. 多个当前收藏版本映射到同一规范曲目时，以最早的有效 `added_date` 表示该规范关系，分母只计算一次。
5. 收藏旅程的库规模仍使用当前快照原始行数；关系指标使用规范曲目实体数。API 必须同时返回这两个粒度，不能混名。

## 4. 收藏旅程

- 年度与季度新增使用有效 `added_date` 转北京时间后聚合。
- 时间线表示当前收藏快照中各曲目的收藏时间分布，不等于历史库容量；已经取消收藏的曲目不可见。
- 收藏总时长只求和真实 `spotify_track_meta.duration_ms`；缺失曲长保留 coverage，不做“数量 × 平均分钟”估算。
- 发行年份取本地专辑或 Spotify 专辑元数据中可验证的 `release_date`。

## 5. 记录期内首次播放到收藏

只对满足以下条件的规范收藏实体分类：

1. 有有效收藏时间；
2. 可匹配本地曲目；
3. 记录期内存在有效逻辑播放；
4. 最早有效播放开始时间不晚于收藏时间；
5. 收藏时间不早于导入播放观察期起点。

使用北京时间自然日差分桶：同日、1–7 天、8–30 天、31–90 天、90 天以上。文案必须写“记录期内首次播放”，不能写“第一次听到”。

没有观察到收藏前播放的实体单列为 `no_observed_pre_save_play`；这不代表用户未曾播放，可能只是发生在数据起点之前或匹配失败。

## 6. 对称 30 天窗口

只有同时满足 `save_at - 30d >= first_play_at` 与 `save_at + 30d <= latest_play_at` 的规范收藏实体进入分母。

- 前窗：`[save_at - 30d, save_at)`；
- 后窗：`(save_at, save_at + 30d]`。

返回前后有效事件总数，以及 `more_before / equal / more_after` 三种互斥实体计数。后窗更多只能描述观察到的关联，不能写成收藏导致播放增加。

## 7. 固定窗回访

对 `h ∈ {7, 30, 90, 365}`：

```text
eligible(h) = 可匹配、日期有效、规范去重，且
              save_at >= first_play_at，
              save_at + h <= latest_play_at

returned(h) = eligible(h) 中在 (save_at, save_at + h] 至少有一次有效播放的实体

R(h) = returned(h) / eligible(h)
```

分母少于 30 时只返回数量，`return_rate_pct=null` 且 `display_status=count_only`；没有合格实体时为 `unavailable`。30 是产品展示护栏，不冒充跨场景统计显著性标准。

由于输入只包含当前仍在收藏的歌曲，`R(h)` 的正式名称是“当前收藏固定窗回访率”，不是收藏留存率。

## 8. 事件对齐周曲线

返回 `week_index=-4…12`。负周使用 `[start,end)`，非负周使用 `(start,end]`，避免相邻窗口重复。每一周独立检查左右观察边界，并返回合格实体数、至少一次播放的实体数、有效事件数和每合格实体事件数。

## 9. 关系矩阵

锚点为数据库 `latest_play_at`：

- `recent_active_saved`：可匹配当前收藏，最近 90 天至少一次有效播放；
- `sleeping_saved`：已收藏满 90 天，最近 90 天无有效播放；
- `recently_saved_without_recent_play`：收藏不足 90 天且最近 90 天无有效播放；
- `saved_without_date`：可匹配但没有有效收藏日期；
- `frequent_unsaved`：最近 90 天至少 5 次有效播放、但不在当前收藏规范实体集合；
- `unmatched_saved_tracks`：当前收藏 URI 无法映射本地曲目，保持原始快照行粒度。

“至少 5 次”是版本化展示阈值。普通 UI 不能把沉睡写成“不喜欢/遗忘”，也不能把常听未收藏写成“拒绝收藏”。

## 10. 缓存与契约

缓存键包含：最短时长、连续合并、动态阈值、最大合并间隔、merge level、UTC 观察边界、播放/收藏 source revision、track group revision 和账号导入/日期 provenance revision。

所有正式响应使用 `extra="forbid"` 的 Pydantic 白名单模型；不得返回 profile、原始搜索词、prompts、inferences、banned items、Spotify URI 或未分页实体全集。
