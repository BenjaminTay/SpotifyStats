# SpotifyStats 文档地图

- [数据导入处理与治理 S6 最终验收](reports/2026-09-21-import-governance-final-acceptance.md)

- [数据导入处理与治理 S1–S5 实施报告](reports/2026-09-21-import-remediation-s1-s5.md)

- [阶段 S0：导入事故修复与测量基线](reports/2026-09-21-import-remediation-s0-baseline.md)

- [2026-09-21 串流导入事故复盘与优化建议](reports/2026-09-21-streaming-import-incident-and-optimization.md)

- [阶段 8：快照可用性与 Billboard 交互连续性收口](reports/2026-09-21-stage8-snapshot-and-billboard-ux-closeout.md)

- [全应用性能优化成果与最终验收报告](reports/2026-09-21-full-application-performance-optimization-outcome.md)

- [阶段 7E：最终本地全栈 Pass 与测试存储收口](reports/2026-09-21-stage7e-final-fullstack-acceptance.md)

- [阶段 7D：Import Preflight 优化与历史验收](reports/2026-09-20-stage7d-import-preflight.md)

- [阶段 7C：Git 检查点与剩余性能收口（Partial）](reports/2026-09-20-stage7c-checkpoints-performance-acceptance.md)

- [阶段 7B：验收阻塞修复与本地收口（Partial）](reports/2026-09-20-stage7b-performance-closeout.md)

- [阶段 7：全路由性能验收与本地收口（Partial）](reports/2026-09-20-stage7-local-performance-acceptance.md)

- [阶段 6C：治理 Coverage / Health 实施报告](reports/2026-09-20-governance-coverage-health.md)

- [治理 Coverage / Health 持久结果](reference/governance-snapshots.md)

- [阶段 6B：音乐档案共享事件与持久结果](reports/2026-09-20-account-archive-shared-events.md)

本目录按“当前规则、进行中的计划、已确认设计、交付证据、历史归档”分层。阅读时先判断文档状态，再判断它属于规则、计划还是证据；历史文件不会自动代表当前实现。

## 阶段 6A Community

- [Community 冷计算、持久读模型与分页](reports/2026-09-20-community-read-model.md)
- [Community 持久读取合同](reference/community-snapshots.md)

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

## 问题台账

长期问题入口：[`issues/README.md`](issues/README.md)；当前开放、部分完成、已解决和已确认不是问题的事项见 [`issues/2026-08-27-issue-register.md`](issues/2026-08-27-issue-register.md)。

## 阶段 5A / 5B / 5C 交付

- [Search 真实 delta 可达性与 identity revision 精度（阶段 5C）](reports/2026-09-20-search-real-delta-reachability.md)

- [Search 四变体配置重建共享、完整等价与边界](reports/2026-09-20-search-invocation-fallback.md)
- [Search shared-full 统计合同、真实 lineage 与验收边界（阶段 5B，Partial）](reports/2026-09-20-search-shared-full-contract.md)

## 阶段 4B 交付

- [Billboard 配置失配重建收口、资源与完整字段证据](reports/2026-09-20-billboard-config-mismatch-closeout.md)

## 阶段 4A 交付

- [Billboard 单次重建共享事实、性能与等价证据](reports/2026-09-20-billboard-generation-facts.md)

## 阶段 3B 交付

- [Records 单次构建共享事实收口](reports/2026-09-20-records-invocation-facts.md)
- [播放纪录读取与 builder 专项优化、未达标项及对账](reports/2026-09-20-records-read-build-optimization.md)

## 阶段 3A 交付

- [默认播放分析结果快照合同](reference/analysis-result-snapshots.md)
- [阶段 3A 实测与验证](reports/2026-09-19-analysis-result-snapshots.md)

## 阶段 2B 交付

- [Community 与详情非核心请求合同](reference/deferred-read-contract.md)
- [阶段 2B 请求图、事实对账与双端验收](reports/2026-09-19-deferred-community-details.md)

## 阶段 2A 交付

- [Billboard 页面投影合同](reference/billboard-page-projections.md)
- [阶段 2A 实测与语义对账](reports/2026-09-19-billboard-page-projections.md)

## 当前有效参考规则

`reference/` 是当前统计和数据契约的权威入口。代码、测试或部署运行手册若与这里冲突，应先核对实际实现和证据，再更新规则文档。

- [`reference/playback-stats-rules.md`](reference/playback-stats-rules.md)：逻辑播放事件、收听时长、版本合并、专辑项目和 Billboard 统计
- [`reference/backend-test-isolation.md`](reference/backend-test-isolation.md)：Backend pytest 导入前隔离、临时数据库/派生缓存与 fail-closed 规则
- [`reference/track-identity-index-migration.md`](reference/track-identity-index-migration.md)：migration 74 的 fallback 唯一性、原子修复和失败回滚合同
- [`reference/public-snapshot-read-contract.md`](reference/public-snapshot-read-contract.md)：Home / Billboard 公开快照、缺失状态、只读边界及专辑 project GET
- [`reference/homepage-presentation-rules.md`](reference/homepage-presentation-rules.md)：首页 Billboard 状态、长期记忆候选池与刷新随机选择
- [`reference/account-archive-statistics.md`](reference/account-archive-statistics.md)：音乐档案、收藏旅程、回归、发现和其他媒体统计
- [`reference/music-metadata-management.md`](reference/music-metadata-management.md)：版本归并、曲目署名、艺人身份和人工治理
- [`reference/2026-07-04-artist-genre-taxonomy.md`](reference/2026-07-04-artist-genre-taxonomy.md)：流派四轴与消费展示 taxonomy
- [`reference/artist-language-statistics.md`](reference/artist-language-statistics.md)：艺人语言事实、审核和播放语言统计
- [`reference/data-import-and-health.md`](reference/data-import-and-health.md)：导入前检查、导入后健康报告和数据库边界
- [`reference/fullstack-verification.md`](reference/fullstack-verification.md)：完整/局部门禁、阶段状态、耗时报告和证据边界

## 状态口径

当前文档不得用一个“已完成”同时代替实现、验证、提交和部署。计划、报告和问题台账按需要分别记录：

- 实现状态：`PLANNED`、`IN_PROGRESS`、`IMPLEMENTED`；
- 验证状态：`NOT_RUN`、`PARTIAL`、`PASS（注明范围）`；
- 仓库状态：`UNCOMMITTED` 或 `COMMITTED <sha>`；
- 远端状态：`UNPUSHED` 或 `PUSHED <branch/sha>`；
- 部署状态：`NOT_DEPLOYED` 或 `DEPLOYED <environment/sha>`；
- 文档状态：`CURRENT`、`DOC_REVIEW`、`SUPERSEDED`；
- 外部条件：真机、OAuth、生产环境、低干扰计时窗口等另行列出。

issue register 继续使用 `OPEN / IN_PROGRESS / PARTIAL / RESOLVED / NOT_A_BUG`；只有实现、测试及必要的真实数据、浏览器或外部证据闭环后才能标 `RESOLVED`。局部测试、历史报告和本地提交均不自动代表当前 HEAD 的整站 Pass、已 push 或已部署。

## 当前进行中的计划

`plans/` 只保留尚未完成、仍需外部验收或持续维护的路线。已完成计划已经移入 [`archive/06-productization-closeout/`](archive/06-productization-closeout/)。

- [`plans/2026-08-06-appification-pwa-capacitor-plan.md`](plans/2026-08-06-appification-pwa-capacitor-plan.md)：PWA 与服务器工程已有历史证据；当前外部可用性、异机备份、双平台真机、OAuth 和 Capacitor 决策待闭环
- [`plans/2026-08-24-fullstack-gate-duration-optimization-plan.md`](plans/2026-08-24-fullstack-gate-duration-optimization-plan.md)：P0 编排与 P1 首项重复请求去重已完成，待低干扰三次计时验收

## 已确认但仍有实现参考价值的设计

- [`designs/2026-08-31-ai-agent-quality-v4.md`](designs/2026-08-31-ai-agent-quality-v4.md)：Answer Contract、Tool Evidence V2、Constraint Patch V2、Worker lease/SSE 恢复与年度报告硬门禁
- [`designs/2026-08-31-ai-agent-quality-v3.md`](designs/2026-08-31-ai-agent-quality-v3.md)：对照 Pi / DeepSeek Harness 的应用内最小真实 Agent、证据门禁、运行中转向与降级设计
- [`designs/2026-08-31-ai-agent-runtime-v2.md`](designs/2026-08-31-ai-agent-runtime-v2.md)：原生工具调用、Turn/Step 状态机、只读 Tool Runtime、可重放事件日志与 legacy 回退契约
- [`designs/2026-07-04-genre-review-settings-design.md`](designs/2026-07-04-genre-review-settings-design.md)：Settings 流派审核面板
- [`designs/2026-08-12-yearly-review-v2-content-data-contract.md`](designs/2026-08-12-yearly-review-v2-content-data-contract.md)：年度总结 V2 内容与数据契约
- [`designs/2026-08-23-yearly-artifact-key-invalidation-contract.md`](designs/2026-08-23-yearly-artifact-key-invalidation-contract.md)：年度事实等价、受影响年份失效与路径历史 key 契约
- [`designs/2026-08-25-music-detail-year-end-history.md`](designs/2026-08-25-music-detail-year-end-history.md)：歌曲、专辑与艺人详情的年榜投影、榜单 KPI、API 和年度历史展示
- [`designs/mobile-web-m0-prototype/README.md`](designs/mobile-web-m0-prototype/README.md)：移动端 M0 视觉原型

## 交付与验证报告

- [`reports/2026-09-19-billboard-sidecar-safety-closeout.md`](reports/2026-09-19-billboard-sidecar-safety-closeout.md)：阶段 0.5 事故安全收口，重新生成正式 Billboard 快照与测试隔离

- [`reports/2026-09-19-track-identity-index-repair.md`](reports/2026-09-19-track-identity-index-repair.md)：阶段 0.5，旧身份索引 migration、全字段对账和双副本性能复测，Partial

- [`reports/2026-09-19-performance-measurement-contract.md`](reports/2026-09-19-performance-measurement-contract.md)：阶段 0 统一测量合同、六探针、seed/Online Backup 校准，Partial

- [`reports/2026-09-19-public-snapshot-boundary.md`](reports/2026-09-19-public-snapshot-boundary.md)：性能阶段 1，可达专辑详情与公开快照边界，局部验证 Partial

报告按主题和日期保存，完整入口见 [`reports/README.md`](reports/README.md)。报告中的性能、测试数量、数据库数量和生产 SHA 都是带日期的证据快照，不应直接当成当前基线。

- [`reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md`](reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)：等价发行 Album Project、stable work、归属 coverage、L1 风险队列、双副本与孙燕姿同名专辑定向治理证据
- [`reports/2026-08-31-ai-agent-performance-v5-acceptance.md`](reports/2026-08-31-ai-agent-performance-v5-acceptance.md)：最小真实 Agent 的共享年度上下文、分章节 Writer、真实模型性能、崩溃恢复、SSE 和响应式验收证据
- [`reports/2026-08-31-l3-governance-execution-and-acceptance.md`](reports/2026-08-31-l3-governance-execution-and-acceptance.md)：L2/L3 分层语义、歌曲与专辑 composition 自动治理、两份副本演练、真实主库发布、API 与响应式全栈验收证据
- [`reports/2026-08-31-l3-native-album-attribution-execution-and-acceptance.md`](reports/2026-08-31-l3-native-album-attribution-execution-and-acceptance.md)：L3 歌曲到原生专辑唯一归属、Taylor 并集、Live 逐曲回流、双副本确定性、主库守恒和完整全栈验收证据
- [`reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)：聚合 proof、Records parity/参数、6 个子页面/8 个后端模块/51 个列表稳定排序、播放排行 tie-breaker、真实库和响应式验收证据
- [`reports/2026-08-31-billboard-count-duration-semantics-research.md`](reports/2026-08-31-billboard-count-duration-semantics-research.md)：播放次数与全部收听时长双轨语义的调研、后端实施、Online Backup 副本重建、真实 API 与榜单对账证据
- [`reports/2026-08-29-l2-track-album-presentation.md`](reports/2026-08-29-l2-track-album-presentation.md)：L2 歌曲专辑归属、独立封面选择、派生数据失效、真实库与响应式验收证据
- [`reports/2026-08-27-spotify-track-l1-identity-migration.md`](reports/2026-08-27-spotify-track-l1-identity-migration.md)：canonical track 唯一归属、公共 L2/L3、真实库迁移和响应式验收证据（文件名为历史兼容）
- [`reports/2026-08-27-settings-rebuild-and-data-governance-remediation.md`](reports/2026-08-27-settings-rebuild-and-data-governance-remediation.md)：设置重建状态、健康口径、只读预览、导入检查和响应式治理 UI 证据
- [`reports/2026-08-25-music-detail-year-end-history.md`](reports/2026-08-25-music-detail-year-end-history.md)：详情年榜投影、榜单 KPI、真实数据库副本、性能与响应式浏览器验收证据
- [`reports/2026-08-24-home-detail-loading-performance-repair.md`](reports/2026-08-24-home-detail-loading-performance-repair.md)：首页/详情冷加载、实体统计分层、按键并发与子榜错误空态的完整修复证据
- [`reports/2026-08-24-yearly-review-semantic-correction.md`](reports/2026-08-24-yearly-review-semantic-correction.md)：年度里程碑、日极值、首次发现、部分月窗口与跨章节 identity/分母修复证据
- [`reports/2026-08-24-fullstack-gate-repair.md`](reports/2026-08-24-fullstack-gate-repair.md)：真实数据断言、艺人 provider ID、浏览器门禁、社区并发与最终全栈 Pass 证据
- [`reports/2026-08-24-fullstack-gate-duration-optimization.md`](reports/2026-08-24-fullstack-gate-duration-optimization.md)：阶段化、同轮去重、局部反馈、完整计时与性能波动验收证据
- [`reports/2026-08-19-music-detail-performance-delivery.md`](reports/2026-08-19-music-detail-performance-delivery.md)：音乐详情按需加载、旧子页收口与优化前后数据等价性证据
- [`reports/2026-08-23-incremental-import-phase-d2.md`](reports/2026-08-23-incremental-import-phase-d2.md)：同一开放周搜索 snapshot delta、lineage/周账本与真实库等价性证据
- [`reports/2026-08-23-incremental-import-phase-d1.md`](reports/2026-08-23-incremental-import-phase-d1.md)：Billboard 周分区、六套搜索 shared-full 复用和真实库等价性证据
- [`reports/2026-08-23-incremental-import-phase-e.md`](reports/2026-08-23-incremental-import-phase-e.md)：历史修正、事务恢复、局部闭包和真实库副本验收
- [`reports/2026-08-23-incremental-import-final-acceptance.md`](reports/2026-08-23-incremental-import-final-acceptance.md)：真实 92,908 条源指纹 baseline、完整导入矩阵和增量/替换等价性终验

## 历史归档

所有已完成或被取代的计划、设计和实施记录均保留在 [`archive/`](archive/)。

- [`archive/README.md`](archive/README.md)：归档阅读规则与阶段目录
- [`archive/06-productization-closeout/`](archive/06-productization-closeout/)：最近一次产品化收口阶段
- [`archive/06-productization-closeout/2026-09-21-import-processing-governance-remediation-plan.md`](archive/06-productization-closeout/2026-09-21-import-processing-governance-remediation-plan.md)：已完成的数据导入、阶段恢复、任务调度、身份治理与 S6 完整验收规划
- [`archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md`](archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md)：已完成的 L3 歌曲作品、原生专辑唯一归属、Taylor 并集和 Live 逐曲回流实施计划
- [`archive/06-productization-closeout/2026-08-23-incremental-streaming-import-plan.md`](archive/06-productization-closeout/2026-08-23-incremental-streaming-import-plan.md)：已完成的串流增量导入 Phase A–E 规划与实施记录
- [`archive/06-productization-closeout/2026-08-27-spotify-track-identity-l1-migration-plan.md`](archive/06-productization-closeout/2026-08-27-spotify-track-identity-l1-migration-plan.md)：已被最终 canonical track / L2 / L3 方案取代的早期 Spotify-L1 规划
- [`archive/06-productization-closeout/2026-06-23-playback-records-plan.md`](archive/06-productization-closeout/2026-06-23-playback-records-plan.md)：播放记录早期 6 栏规划与当前 5 栏/20 模块实现差异
- [`archive/06-productization-closeout/2026-06-29-ai-agent-harness-quality-roadmap.md`](archive/06-productization-closeout/2026-06-29-ai-agent-harness-quality-roadmap.md)：已落地的 evidence-driven Agent harness 历史实施路线
- [`archive/06-productization-closeout/2026-08-16-music-search-direction-realignment.md`](archive/06-productization-closeout/2026-08-16-music-search-direction-realignment.md)：由后续零停机方案和当前 reference 接管的搜索方向文档
- [`archive/06-productization-closeout/2026-08-26-settings-rebuild-and-data-governance-remediation-plan.md`](archive/06-productization-closeout/2026-08-26-settings-rebuild-and-data-governance-remediation-plan.md)：Settings 重建与数据治理已完成计划
- [`archive/06-productization-closeout/2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md`](archive/06-productization-closeout/2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md)：搜索 LKG、任务竞态与署名增量已完成计划
- [`archive/06-productization-closeout/2026-08-29-billboard-records-consistency-and-ranking-hardening-plan.md`](archive/06-productization-closeout/2026-08-29-billboard-records-consistency-and-ranking-hardening-plan.md)：已完成的 Billboard Records 一致性、全板块稳定排序与播放排行同值裁决计划
- [`archive/06-productization-closeout/2026-08-30-playback-records-correctness-and-ranking-plan.md`](archive/06-productization-closeout/2026-08-30-playback-records-correctness-and-ranking-plan.md)：已完成的播放记录全板块统计正确性和稳定排序计划；后续冷路径与门禁优化由全栈门禁计划接管
- [`archive/06-productization-closeout/2026-09-12-billboard-persistent-snapshot-optimization-plan.md`](archive/06-productization-closeout/2026-09-12-billboard-persistent-snapshot-optimization-plan.md)：已上线的 Billboard 周榜、年榜、总榜持久快照、后台重建与回滚兼容性门禁计划
- [`archive/06-productization-closeout/2026-08-31-l2-l3-identity-and-album-attribution-remediation-plan.md`](archive/06-productization-closeout/2026-08-31-l2-l3-identity-and-album-attribution-remediation-plan.md)：已完成的等价发行、stable work、归属 coverage 与 L1 风险分类实施计划
- [`archive/01-streamlit-mvp/`](archive/01-streamlit-mvp/) 至 [`archive/05-yearly-report-genre/`](archive/05-yearly-report-genre/)：早期开发阶段

## 文档维护规则

- 当前文档必须说明状态、适用范围和替代关系。
- 规则写入 `reference/`，计划写入 `plans/`，设计写入 `designs/`，证据写入 `reports/`。
- 已完成计划不得继续留在 `plans/`；被替代的设计必须标记替代入口。
- 根目录 `AGENTS.md` 与 `CLAUDE.md` 保持一致，详细领域规则通过链接引用。
- 新增或移动文档后运行 `python3 scripts/docs_audit.py`。
