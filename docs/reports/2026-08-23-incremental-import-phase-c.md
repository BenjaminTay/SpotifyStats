# 增量导入 Phase C 交付报告

> 状态：Pass（ChangeSet、范围维护、年度缓存和封面恢复）；Billboard 周分区与搜索 snapshot delta 仍属于 Phase D
>
> 验证日期：2026-08-23；数据库证据来自 SQLite Online Backup 副本，不修改活动数据库

## 本阶段交付

- 从实际写入代际生成 `PlaybackChangeSet`，覆盖本地曲目/专辑/来源专辑/艺人、Spotify 曲目/专辑、日期、月份、年份、开放周和语义 revision；实际行数与计划不一致时拒绝发布。
- 事实、活动代际、年度分区和 `maintenance_pending` 运行记录同事务提交。维护成功后原记录提升为 `success`，进程中断不会丢失紧凑恢复依据。
- 增量元数据使用 generation play-time ID 与本地 canonical ID 的并集；专辑候选同时来自 generation play、曲目元数据和 album links。每次 scoped 刷新另带 200 条曲目/专辑/艺人和 100 条精确艺人封面的历史缺失扫尾。
- 封面以 provider URL 哈希判断缺失或过期。无来源证据的迁移前文件会重新校验下载；下载、临时写入、`fsync`、原子替换和数据库发布任一步失败都会留下可重试状态。后台队列启动时恢复 pending 和孤立 running；旧 URL 任务通过 CAS 拒绝覆盖新来源。
- 年度缓存使用逐年 direct/prefix digest，并摘要报告年前缀可达的艺人、Spotify 元数据、流派来源/覆盖、曲目组、Album Project membership 和可用年份。Migration 41 会清除不能安全升级的 V1 prefix 行，下一次导入完整回填。
- 播放事实提交后立即清理播放相关运行时缓存；聚合构建绑定开始代际并在原子发布时复核，防止旧事实计算被标记为新代际。无关的音乐档案、Podcast 等 cache namespace 不随播放导入清空。

## 自动化验证

- Unit：`1170 passed, 825 deselected`。
- Contract：`366 passed, 1629 deselected`。完整回归首次发现一个内部 helper 新参数未同步的测试调用，修正后再次执行全量门禁通过。
- 重点组合：ChangeSet、metadata、cover、JobQueue、Yearly Review 共 `54 passed`。
- Ruff 与 `git diff --check`：通过。

## 真实数据库副本

基线为 92,908 条播放，复制后增加 1 条尾部记录。副本先补齐版本化指纹和代际，仅用于测量 Phase C 的影响范围；测试后副本已移入废纸篓。

| 项目 | 结果 |
|------|------|
| ChangeSet 构建 | 0.0179 秒，3 个本地实体，影响年份仅 2026 |
| 年度分区发布 | 0.4460 秒 |
| 封面来源范围 | 全库 4,115 个；scoped 2 个 |
| 曲目/专辑 scoped selector | 各约 0.0001 秒 |
| 2025 年 scoped 年度依赖摘要 | 0.1271 秒 |
| 仍为全量的 Album Project | 2.3326 秒 |
| 仍为全量的 Billboard 聚合 | 3.1596 秒 |

当前真实库的 Spotify 曲目和专辑元数据已基本齐全，因此全量与 scoped 的请求数都为 0；全量艺人 selector 仍发现 26 个候选，单条尾部记录的 scoped 艺人候选为 0。这个结果证明范围收敛，不代表联网 provider 请求速度。

## 边界与下一步

- `billboard_scope_exact=false` 是有意的安全标记。当前维护仍全量重建 Billboard，不能用原始新增时间直接声称周贡献闭包。
- Album Project 暂时全量；真实副本耗时约 2.33 秒，低于 Billboard，但后续仍应通过成本门限决定定向或全量。
- 搜索候选与六套精确统计 snapshot 仍沿用现有重建/后台 warming。Phase D 需要实现受影响周替换、逻辑播放帧复用和 snapshot delta，并做增量—全量逐表等价性验收。
- Metadata backlog 当前由“仍然缺失”这一持久事实驱动并有界重试；尚未增加按错误类型的退避时间和尝试次数，这属于后续长期运行优化，不影响失败项被再次发现。
