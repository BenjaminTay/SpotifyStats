# 近期产品化收口归档

本目录保存 2026-08 产品化收口阶段已经完成、但仍有回溯价值的计划、设计和专项治理方案。

## 当前替代入口

- 当前统计规则：[`../../reference/playback-stats-rules.md`](../../reference/playback-stats-rules.md)
- 当前音乐档案规则：[`../../reference/account-archive-statistics.md`](../../reference/account-archive-statistics.md)
- 当前元数据治理：[`../../reference/music-metadata-management.md`](../../reference/music-metadata-management.md)
- 当前移动端视觉规则：[`../../../frontend/UI_STYLE_GUIDE.md`](../../../frontend/UI_STYLE_GUIDE.md)
- 当前生产部署：[`../../../deploy/production/README.md`](../../../deploy/production/README.md)
- 交付证据索引：[`../../reports/README.md`](../../reports/README.md)

## 已完成规划

- [`2026-08-23-incremental-streaming-import-plan.md`](2026-08-23-incremental-streaming-import-plan.md)：串流数据关系识别、基础事实增量发布、派生分区更新、历史修正与恢复边界。当前运行规则以 [`../../reference/data-import-and-health.md`](../../reference/data-import-and-health.md) 为准，分阶段证据见 [`../../reports/README.md`](../../reports/README.md)。
- [`2026-08-27-spotify-track-identity-l1-migration-plan.md`](2026-08-27-spotify-track-identity-l1-migration-plan.md)：已被最终 canonical track / L2 / L3 方案取代的早期 Spotify-L1 规划；只用于回溯决策过程。当前规则见 [`../../reference/music-metadata-management.md`](../../reference/music-metadata-management.md)，最终证据见 [`../../reports/2026-08-27-spotify-track-l1-identity-migration.md`](../../reports/2026-08-27-spotify-track-l1-identity-migration.md)。

归档文件保留设计过程、决策和实施边界，不再作为新的开发计划直接执行。若归档内容与当前代码或 `reference/` 冲突，以当前实现和当前参考规则为准。
