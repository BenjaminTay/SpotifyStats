# Billboard 艺人榜逻辑播放事件预聚合修复

## 状态

- 日期：2026-08-13
- 状态：已修复、已重建真实派生聚合、已完成 API 与全量对账
- 影响范围：Billboard 艺人周榜预聚合；单曲榜和专辑榜未发现同类计数错误

## 问题表现

在当前榜单设置“周五 12:00”下，2023 年第 26 周（`2023-06-30`）出现：

- 单曲榜：Olivia Rodrigo 的 `vampire` 为冠军，播放量 118。
- 艺人榜：Olivia Rodrigo 只有 83 次。

原始艺人路径对该周计算出 159 次，说明 83 次来自预聚合链路的错误折叠，而不是 `plays` 原始数据缺失。

## 根因

连续播放合并会将一组原始记录展开成一个或多个逻辑播放事件。展开后的多个事件可能继续携带同一个来源 `play_id`。

单曲和 track-source 聚合直接按合并后的逻辑事件行计数；艺人预聚合则先通过 `track_artists` 做署名扇出，再调用 `canonicalize_artist_frame()`。修复前该分支没有携带逻辑事件身份，艺人身份去重只能退回到 `play_id + artist_id`，因此同一个 `play_id` 展开的多个逻辑事件被错误地合并为一个。

原始艺人 Billboard 路径此前已经通过 `_artist_event_id` 区分扇出前的有效事件，所以原始路径和预聚合路径产生了不同结果。

## 修复内容

1. 在播放合并和有效阈值过滤完成后、艺人署名扇出前生成帧内唯一的 `_logical_event_id`。
2. `canonicalize_artist_frame()` 优先使用 `_logical_event_id + canonical artist_id` 去重；保留 `_artist_event_id` 作为旧消费者兼容别名。
3. 艺人预聚合、原始艺人 Billboard 路径统一使用同一逻辑事件身份规则。
4. `build_aggregations()` 成功或清空派生表后统一清理运行时缓存，防止同一进程继续返回旧榜单结果。
5. 增加一个“单个连续会话展开为多个逻辑事件”的原始/预聚合一致性测试，并保留专辑项目原始/track-source 预聚合对账测试。

## 真实数据修复

重建参数：

| 参数 | 值 |
|------|------|
| `min_ms` | `30000` |
| `music_only` | `true` |
| Billboard 周起点 | 周五 |
| 周起始时间 | `12:00` |
| `dynamic_threshold` | `true` |
| `max_merge_gap_minutes` | `null` |

重建结果：

- `plays`：91,286 行，未修改原始播放事实。
- `agg_weekly_tracks`：36,725 行。
- `agg_weekly_track_sources`：50,495 行。
- `agg_weekly_artists`：9,969 行。
- `agg_config.param_hash` 与当前身份/署名修订及重建参数一致。

2023-06-30 修复后结果：

| 榜单实体 | 播放量 | 说明 |
|------|------:|------|
| `vampire` 单曲榜 | 118 | 保持原冠军结果 |
| Olivia Rodrigo 艺人榜 | 159 | 从错误的 83 修正 |
| Olivia Rodrigo 的 `SOUR` 专辑榜 | 39 | 专辑口径正常 |

## 影响范围验证

### 艺人榜

使用同一组过滤参数，对原始艺人路径和预聚合艺人表按 `(billboard_week, artist_id)` 对账：

- 9,969 个艺人-周组合。
- `play_count` 差异：0。
- `total_ms` 差异：0。

修复前的历史扫描发现 503 个艺人-周组合存在正向差异，分布于 181 个榜单周；因此该问题不是 2023 年第 26 周的孤立数据异常，其他周也可能受到同一链路影响。

### 专辑榜

专辑榜的 track-source 预聚合在艺人扇出之前生成，且专辑项目聚合使用 canonical song 去重，不经过这次出错的艺人身份去重分支。真实数据原始专辑路径与 track-source 预聚合对账结果为：

- 13,000 行专辑周榜结果。
- `play_count` 差异：0。

因此本次根因不会传导到专辑榜；专辑榜仍保留独立的原始/预聚合对账测试。

## 验证记录

- 目标回归测试：48 项通过。
- 目标文件 Ruff 检查：通过。
- 目标文件 `compileall`：通过。
- 真实 API `/api/billboard/weekly`：返回 `vampire=118`、Olivia Rodrigo 艺人榜 `159`。
- SQLite 主数据库和修复前备份：`PRAGMA integrity_check` 均为 `ok`。

项目全量 `pytest -m unit -q` / `pytest -m contract -q` 在测试收集阶段受到本机环境中 `/opt/anaconda3/site-packages/scripts` 与项目 `scripts/` 同名包冲突影响；该阻断与本次修改无关，目标测试已独立通过。

## 回滚与备份

修复前 SQLite 一致性备份保留在本地：

`data/spotify_stats.db.pre-logical-event-fix-20260813`

该备份及其 SQLite WAL sidecar 已加入 `.gitignore`，不纳入 Git 提交或远程推送。回滚时应先停止写入，再使用该备份恢复数据库并清理 Billboard 运行时缓存。
