# SpotifyStats 文档地图

本目录按“当前规则、进行中的计划、已确认设计、交付证据、历史归档”分层。阅读时先判断文档状态，再判断它属于规则、计划还是证据；历史文件不会自动代表当前实现。

## 从哪里开始

| 目的 | 入口 |
|---|---|
| 了解项目、安装和启动 | [`../README.md`](../README.md) |
| AI/开发工作约定 | [`../AGENTS.md`](../AGENTS.md) / [`../CLAUDE.md`](../CLAUDE.md) |
| 后端开发 | [`../backend/CLAUDE.md`](../backend/CLAUDE.md) |
| 前端开发 | [`../frontend/README.md`](../frontend/README.md) / [`../frontend/CLAUDE.md`](../frontend/CLAUDE.md) |
| UI 设计系统 | [`../frontend/UI_STYLE_GUIDE.md`](../frontend/UI_STYLE_GUIDE.md) |
| 数据准备与导入 | [`../data/README.md`](../data/README.md) |
| 生产部署 | [`../deploy/production/README.md`](../deploy/production/README.md) |
| 最近变更 | [`CHANGELOG.md`](CHANGELOG.md) |
| 完整交付证据 | [`reports/README.md`](reports/README.md) |

## 当前有效参考规则

`reference/` 是当前统计和数据契约的权威入口。代码、测试或部署运行手册若与这里冲突，应先核对实际实现和证据，再更新规则文档。

- [`reference/playback-stats-rules.md`](reference/playback-stats-rules.md)：逻辑播放事件、收听时长、版本合并、专辑项目和 Billboard 统计
- [`reference/account-archive-statistics.md`](reference/account-archive-statistics.md)：音乐档案、收藏旅程、回归、发现和其他媒体统计
- [`reference/music-metadata-management.md`](reference/music-metadata-management.md)：版本归并、曲目署名、艺人身份和人工治理
- [`reference/2026-07-04-artist-genre-taxonomy.md`](reference/2026-07-04-artist-genre-taxonomy.md)：流派四轴与消费展示 taxonomy
- [`reference/artist-language-statistics.md`](reference/artist-language-statistics.md)：艺人语言事实、审核和播放语言统计
- [`reference/data-import-and-health.md`](reference/data-import-and-health.md)：导入前检查、导入后健康报告和数据库边界

## 当前进行中的计划

`plans/` 只保留尚未完成、仍需外部验收或持续维护的路线。已完成计划已经移入 [`archive/06-productization-closeout/`](archive/06-productization-closeout/)。

- [`plans/2026-06-23-playback-records-plan.md`](plans/2026-06-23-playback-records-plan.md)：播放记录方案，需继续核对计划与当前实现的差异
- [`plans/2026-06-29-ai-agent-harness-quality-roadmap.md`](plans/2026-06-29-ai-agent-harness-quality-roadmap.md)：AI Agent Harness 持续质量路线
- [`plans/2026-08-06-appification-pwa-capacitor-plan.md`](plans/2026-08-06-appification-pwa-capacitor-plan.md)：PWA、远程部署、真机验收和 Capacitor 决策
- [`plans/2026-08-16-music-search-direction-realignment.md`](plans/2026-08-16-music-search-direction-realignment.md)：音乐查找候选索引、统计快照和生产复用方向
- [`plans/2026-08-23-incremental-streaming-import-plan.md`](plans/2026-08-23-incremental-streaming-import-plan.md)：串流数据关系判定、增量写入、派生分区更新和全量回退规划

## 已确认但仍有实现参考价值的设计

- [`designs/2026-07-04-genre-review-settings-design.md`](designs/2026-07-04-genre-review-settings-design.md)：Settings 流派审核面板
- [`designs/2026-08-12-yearly-review-v2-content-data-contract.md`](designs/2026-08-12-yearly-review-v2-content-data-contract.md)：年度总结 V2 内容与数据契约
- [`designs/mobile-web-m0-prototype/README.md`](designs/mobile-web-m0-prototype/README.md)：移动端 M0 视觉原型

## 交付与验证报告

报告按主题和日期保存，完整入口见 [`reports/README.md`](reports/README.md)。报告中的性能、测试数量、数据库数量和生产 SHA 都是带日期的证据快照，不应直接当成当前基线。

- [`reports/2026-08-19-music-detail-performance-delivery.md`](reports/2026-08-19-music-detail-performance-delivery.md)：音乐详情按需加载、旧子页收口与优化前后数据等价性证据

## 历史归档

所有已完成或被取代的计划、设计和实施记录均保留在 [`archive/`](archive/)。

- [`archive/README.md`](archive/README.md)：归档阅读规则与阶段目录
- [`archive/06-productization-closeout/`](archive/06-productization-closeout/)：最近一次产品化收口阶段
- [`archive/01-streamlit-mvp/`](archive/01-streamlit-mvp/) 至 [`archive/05-yearly-report-genre/`](archive/05-yearly-report-genre/)：早期开发阶段

## 文档维护规则

- 当前文档必须说明状态、适用范围和替代关系。
- 规则写入 `reference/`，计划写入 `plans/`，设计写入 `designs/`，证据写入 `reports/`。
- 已完成计划不得继续留在 `plans/`；被替代的设计必须标记替代入口。
- 根目录 `AGENTS.md` 与 `CLAUDE.md` 保持一致，详细领域规则通过链接引用。
- 新增或移动文档后运行 `python3 scripts/docs_audit.py`。
