# SpotifyStats 文档地图

按读者和要完成的事情选择入口。使用指南说明操作，开发与运维文档说明维护方法，技术参考维护共同规则，Agent指令约束执行；计划和报告分别记录未来路线与历史事实。

## 使用者入口

| 你想做什么 | 阅读 |
| --- | --- |
| 了解产品、查看界面 | [项目首页](../README.md) |
| 安装、准备数据并首次使用 | [使用指南](user-guide.md#安装与首次启动) |
| 导入数据、配置AI或排查常见问题 | [操作与常见问题](user-guide.md) |
| 了解使用体验的变化 | [更新记录](CHANGELOG.md) |

## 维护者与共用参考

开发从[开发指南](../CONTRIBUTING.md)开始；当前事项、排期和环境边界以[开发状态](DEVELOPMENT_STATUS.md)为准，问题身份与复现依据在[问题台账](issues/README.md)。

| 用途 | 入口 |
| --- | --- |
| 后端架构与开发 | [后端README](../backend/README.md) |
| 前端架构、交互与设计 | [前端README](../frontend/README.md)、[UI规范](../frontend/UI_STYLE_GUIDE.md) |
| 输入JSON、导入实现与运行文件 | [数据格式参考](../data/README.md) |
| 维护、验证与性能工具 | [脚本用途与运行边界](../scripts/README.md) |
| 部署、网关、备份与恢复 | [运维手册](../deploy/production/README.md) |

以下是维护者与Agent共用的当前规范，各自只维护一份。技术标识和实现边界用于精确理解行为；普通操作不要求通读。

### 统计与内容

- [播放统计与版本合并规则](reference/playback-stats-rules.md)
- [音乐档案统计规则](reference/account-archive-statistics.md)
- [年度总结内容与缓存规则](reference/yearly-review.md)

### 音乐元数据

- [音乐源数据管理与曲目署名规则](reference/music-metadata-management.md)
- [发行日期证据与精度](reference/release-date-precision.md)
- [流派分类与审核](reference/artist-genre-taxonomy.md)
- [艺人语言事实与统计规则](reference/artist-language-statistics.md)

### 输入与数据库

- [数据导入与健康检查](reference/data-import-and-health.md)
- [旧数据库身份fallback索引一致性](reference/track-identity-index-migration.md)

### 页面与图片

- [首页展示与长期记忆规则](reference/homepage-presentation-rules.md)
- [音乐封面传输规则](reference/cover-artwork-delivery.md)

### 搜索与发布读取

- [音乐搜索候选与统计读取合同](reference/music-search.md)
- [Home／Billboard公开快照读取合同](reference/public-snapshot-read-contract.md)
- [默认播放分析结果快照](reference/analysis-result-snapshots.md)
- [Billboard页面响应投影](reference/billboard-page-projections.md)
- [Community持久读模型](reference/community-snapshots.md)
- [治理Coverage／Health持久结果](reference/governance-snapshots.md)
- [Community与详情非核心请求合同](reference/deferred-read-contract.md)

### AI运行

- [AI Agent V6运行、恢复与报告发布规则](reference/ai-agent-runtime-v6.md)

### 开发与验证

- [开发、整合与工作树收尾规则](reference/development-delivery-workflow.md)
- [Backend测试的数据库与派生文件隔离](reference/backend-test-isolation.md)
- [全栈验证与阶段执行规则](reference/fullstack-verification.md)

## Agent 入口

- [根执行约定](../AGENTS.md)与[CLAUDE入口](../CLAUDE.md)完全一致，维护全局执行边界。
- [后端局部指令](../backend/CLAUDE.md)与[前端局部指令](../frontend/CLAUDE.md)说明局部工作要求，架构和默认值链接到开发文档。
- 开始任务先查[状态总表](DEVELOPMENT_STATUS.md)，按问题选读共用参考，完成后更新相应证据与状态；不用产品首页承担研发速查职责。

## 当前计划与历史追溯

滚动路线保留未完成工作、观察及重启条件，是否启动与当前余量以状态总表为准。

- [PWA与原生分发路线](plans/appification-and-mobile-distribution.md)
- [全栈验证性能与成本](plans/fullstack-verification-performance.md)
- [多源音乐元数据路线](plans/multi-source-music-metadata.md)
- [加载结项与内存观察](plans/performance-and-memory-closeout.md)
- [发行周期数据治理](plans/release-cycle-data-governance.md)

追溯决策、版本与验证时使用下列入口：

- [设计决策](designs/README.md)、[交付与验证报告](reports/README.md)、[历史归档](archive/README.md)、[月度变更历史](archive/changelog/README.md)。
- [近期产品化归档](archive/06-productization-closeout/README.md)、[项目截图素材说明](assets/readme/README.md)。
- [清理后恢复基线重建与生产发布重试](reports/2026-10-28-recovery-baseline-and-release-retry.md)。
- [项目文件整理交付](reports/2026-10-26-project-file-organization.md)、[已完成实施规划](archive/06-productization-closeout/2026-10-26-project-file-organization-plan.md)。
- [文档整理与验收记录](reports/2026-10-25-documentation-cleanup-delivery.md#读者分工与命名更新)。

## 文档职责与维护

当前状态、优先级、下一步和最后核验日期只维护在总表；台账保存身份、现象和判断；报告保存带日期的过程与证据。当前规则不重复开发过程，索引只负责导航。历史失败和旧数量保留原日期语境。

长期台账、当前规则和滚动路线使用稳定主题文件名，创建／修订日期写入正文。冻结设计、报告与归档保留日期；有实际合同含义的版本号保留。新增、移动或修改标题后更新入链，Agent入口保持根AGENTS／CLAUDE完全一致。具体分工见[开发指南](../CONTRIBUTING.md#文档职责与命名)。

文档变更执行 `python3 scripts/docs_audit.py --include-archive` 和差异检查，核对标题锚点、索引覆盖、读者定位及内容承接。修改审计脚本时运行 `python3 -m unittest scripts.tests.test_docs_audit`；不默认运行应用全栈。
