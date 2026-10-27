# 项目文件整理与本地材料清理

事项ID：`SS-2026-10-26-001`。执行日期：2026-10-26；补充验收与精简：2026-10-27；源码基线为 `2da50438`，复用main唯一工作目录。当前进度只维护在[开发状态](../DEVELOPMENT_STATUS.md)。

## 范围与结果

用户确认相关开发已收口，并要求完整执行文件整理规划。本轮清理本地历史产物、迁移日常日志、退役无当前应用消费者的前端实现、归类维护脚本。正式主库、原始输入、活动导入来源、封面、依赖环境、凭据、Git恢复引用及stash保留；没有修改后端业务、数据库事实或schema；本地整理阶段未提交、推送或进行生产操作，后续授权Git交付见本文末节。

规划文档的既有未提交修改属于同一事项并继续承接；没有覆盖其他任务修改。文件清理、退役与迁移、最终本地构建及受影响验证完成；实施规划已[归档](../archive/06-productization-closeout/2026-10-26-project-file-organization-plan.md)。

## P0–P2：服务切换与空间清理

执行前没有pending/queued/running后台任务。当前服务的正式主库及六类sidecar都位于保留的data目录，待删目录没有活动数据来源。旧监督入口是output中的一次性 `run_local.py`，前后端与其日志同目录耦合。

正常停止已核验的旧监督入口后，改用现有 `scripts/start_daily.py --build`，保留8000/4173 loopback端口、minimal预热和原有非敏感数据库路径覆盖。旧前端构建没有有效的日常输入清单，因此P1执行一次必要的受管构建；P6在退役源码固定后再构建最终版本。启动脚本源码未修改，没有新增守护程序。

本地常驻日志改到已忽略的 `data/logs/daily.log`。删除前确认旧output及backups没有打开文件，服务健康与前端入口均返回200；随后整体删除，不移到废纸篓，不另存同量归档。

| 删除对象 | 文件数 | 文件内容大小 |
| --- | ---: | ---: |
| `output/` | 3156 | 15.407 GiB |
| `data/backups/` | 4 | 0.828 GiB |
| `.mypy_cache/` | 4617 | 0.085 GiB |
| `.pytest_cache/` | 5 | 0.000 GiB |
| `.ruff_cache/` | 23 | 0.000 GiB |

共删除 17,524,282,675 字节（16.321 GiB）既有内容。P2观测磁盘可用空间从 56.408 GiB 增至 72.781 GiB，净增 **16.373 GiB**；这是当时系统可用空间变化，不是APFS独占块承诺。

保留对象路径与inode逐项核对通过；运行期数据库大小和mtime可以随正常预热变化，不将其当原始事实修改证据。本次没有执行导入、数据批准、全库摘要、VACUUM或完整恢复演练。清理后再次读取现有health成功。

## P3：前端退役与测试承接

静态候选61个逐项处置：删除48个，保留13个。删除旧年度总结15文件及其独占TasteProfile、9个已撤下详情组件、旧移动Dashboard/查询链、7个未使用UI模板及其他无消费者组件/工具。保留当前V2年报、现有详情页签、Home入口及后端兼容接口。

删除文件如下，以仓库路径列出；这些是本次处置事实，不作为当前可打开文件链接：

- `frontend/src/components/charts/PlatformDistChart.tsx`
- `frontend/src/components/shared/ArtistEnrichmentView.tsx`
- `frontend/src/components/shared/CareerTimeline.tsx`
- `frontend/src/components/shared/PageSwitcher.tsx`
- `frontend/src/components/shared/StatsGrid.tsx`
- `frontend/src/components/shared/TasteProfile.tsx`
- `frontend/src/components/ui/avatar.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/collapsible.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`
- `frontend/src/components/ui/scroll-area.tsx`
- `frontend/src/components/ui/sheet.tsx`
- `frontend/src/components/ui/table.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/PlaybackBillboardMatrix.tsx`
- `frontend/src/features/ai-tasks/AIResultShell.tsx`
- `frontend/src/features/analysis/records/recordsData.ts`
- `frontend/src/features/billboard/records/RecordsSections.tsx`
- `frontend/src/features/mobile/dashboard/MobileDashboard.tsx`
- `frontend/src/features/mobile/yearly-v2/chapters/index.ts`
- `frontend/src/features/mobile/yearly/MobileYearlyChapterNav.tsx`
- `frontend/src/features/music/details/AlbumEraOverviewSection.tsx`
- `frontend/src/features/music/details/AlbumEraSection.tsx`
- `frontend/src/features/music/details/AlbumReleaseCompositionSection.tsx`
- `frontend/src/features/music/details/AlbumReleaseOverflowSection.tsx`
- `frontend/src/features/music/details/AlbumReleaseTimelineSection.tsx`
- `frontend/src/features/music/details/ArtistCareerSection.tsx`
- `frontend/src/features/music/details/ArtistReleaseCycleSection.tsx`
- `frontend/src/features/music/details/ArtistReleasesSection.tsx`
- `frontend/src/features/music/details/track/TrackLyricsSection.tsx`
- `frontend/src/hooks/useBreakpoint.ts`
- `frontend/src/hooks/useDashboard.ts`
- `frontend/src/hooks/useYearlyReview.ts`
- `frontend/src/lib/genre-regions.ts`
- `frontend/src/lib/insights.ts`
- `frontend/src/lib/personality-themes.ts`
- `frontend/src/pages/yearly-review/CustomSummary.tsx`
- `frontend/src/pages/yearly-review/DiscoveryReturns.tsx`
- `frontend/src/pages/yearly-review/GenrePanorama.tsx`
- `frontend/src/pages/yearly-review/HeroSection.tsx`
- `frontend/src/pages/yearly-review/HourClock.tsx`
- `frontend/src/pages/yearly-review/ListeningDepth.tsx`
- `frontend/src/pages/yearly-review/MonthlyDrilldown.tsx`
- `frontend/src/pages/yearly-review/MusicMap.tsx`
- `frontend/src/pages/yearly-review/PersonalityReveal.tsx`
- `frontend/src/pages/yearly-review/SpecialMoments.tsx`
- `frontend/src/pages/yearly-review/TimeStory.tsx`
- `frontend/src/pages/yearly-review/TopCharts.tsx`
- `frontend/src/pages/yearly-review/YearComparison.tsx`

删除69行仅供旧手机年度导航/故事容器使用的CSS；当前 `mobile-yearly-controls` 和V2独立样式保留。没有对全局CSS做重构或重排。

原语言分布5项旧页面测试迁到当前桌面与手机TasteMigration组件，形成10项验证：后端语言桶在无流派覆盖时仍展示、unknown保留在分母中、风格/地区维度独立、覆盖不足不编造分布、消费UI不泄露治理术语。当前V2以占比而非旧页面小时数展示，测试按现有合同承接，不恢复旧页面。

10-26当时以下13个候选因测试或架构约束消费者而保留，没有新增产品入口。10-27复核确认测试是唯一剩余消费者，按用户后续指令迁移有效行为测试后全部退役，具体见本文末节；下表保留当时处置依据：

| 保留文件 | 保留依据 |
| --- | --- |
| `frontend/src/components/charts/MonthlyTrendChart.tsx` | phase5-architecture.test.ts |
| `frontend/src/components/charts/MonthlyTrendEChart.tsx` | phase5-architecture.test.ts |
| `frontend/src/components/charts/ReleaseTimelineChart.tsx` | phase5-architecture.test.ts |
| `frontend/src/components/shared/AlbumEnrichmentView.tsx` | album-enrichment-view.test.tsx |
| `frontend/src/components/shared/ChartBars.tsx` | 仍被测试使用的兼容渲染链共享依赖 |
| `frontend/src/components/shared/FormattedText.tsx` | FormattedText.test.tsx |
| `frontend/src/components/shared/GenreTags.tsx` | 仍被测试使用的兼容渲染链共享依赖 |
| `frontend/src/components/shared/KeyFactsCard.tsx` | 仍被测试使用的兼容渲染链共享依赖 |
| `frontend/src/features/mobile/yearly/YearlyPeriodNotice.tsx` | mobile-m4-pages.test.tsx |
| `frontend/src/features/music/details/AlbumDetailPrimitives.tsx` | 仍被测试使用的兼容渲染链共享依赖 |
| `frontend/src/features/music/details/AlbumEnrichmentSection.tsx` | album-enrichment-view.test.tsx |
| `frontend/src/features/settings/components/ImportPreflightPanel.tsx` | data-import-health.test.tsx |
| `frontend/src/pages/LegacyTrackDetailRedirect.tsx` | legacy-track-detail-redirect.test.tsx |

## P4：脚本目录与入口

原根目录100个文件全部登记：18个迁移、2个删除、80个保留原路径。新增[维护与验证工具说明](../../scripts/README.md)，按用途列出98个仍保留的工具/合同，标注只读、维护写入、副本、传输及模型调用边界。根目录整理后为80个既有文件加1份README。

| 原路径 | 新路径 |
| --- | --- |
| `scripts/account_archive_probe.py` | [account_archive_probe.py](../../scripts/verification/account_archive_probe.py) |
| `scripts/audit_artist_genre_source_quality_batch.py` | [audit_artist_genre_source_quality_batch.py](../../scripts/maintenance/audit_artist_genre_source_quality_batch.py) |
| `scripts/audit_l1_external_identity_risks.py` | [audit_l1_external_identity_risks.py](../../scripts/maintenance/audit_l1_external_identity_risks.py) |
| `scripts/audit_spotify_track_credits.py` | [audit_spotify_track_credits.py](../../scripts/maintenance/audit_spotify_track_credits.py) |
| `scripts/audit_track_l1_identity.py` | [audit_track_l1_identity.py](../../scripts/maintenance/audit_track_l1_identity.py) |
| `scripts/benchmark_ai_agent_compare.py` | [benchmark_ai_agent_compare.py](../../scripts/performance/benchmark_ai_agent_compare.py) |
| `scripts/billboard_year_end_consistency_probe.py` | [billboard_year_end_consistency_probe.py](../../scripts/verification/billboard_year_end_consistency_probe.py) |
| `scripts/cover_image_probe.py` | [cover_image_probe.py](../../scripts/verification/cover_image_probe.py) |
| `scripts/evaluate_ai_agent_v6_freeform.py` | [evaluate_ai_agent_v6_freeform.py](../../scripts/performance/evaluate_ai_agent_v6_freeform.py) |
| `scripts/import_metadata_pre_review_batch.py` | [import_metadata_pre_review_batch.py](../../scripts/maintenance/import_metadata_pre_review_batch.py) |
| `scripts/music_detail_chart_acceptance.py` | [music_detail_chart_acceptance.py](../../scripts/verification/music_detail_chart_acceptance.py) |
| `scripts/music_detail_equivalence_probe.py` | [music_detail_equivalence_probe.py](../../scripts/verification/music_detail_equivalence_probe.py) |
| `scripts/oauth_redirect_server.py` | [oauth_redirect_server.py](../../scripts/dev/oauth_redirect_server.py) |
| `scripts/preview_release_evidence.py` | [preview_release_evidence.py](../../scripts/maintenance/preview_release_evidence.py) |
| `scripts/rebuild_account_archive.py` | [rebuild_account_archive.py](../../scripts/maintenance/rebuild_account_archive.py) |
| `scripts/runtime_df_compare.py` | [runtime_df_compare.py](../../scripts/performance/runtime_df_compare.py) |
| `scripts/verify_collaboration_ranking.py` | [verify_collaboration_ranking.py](../../scripts/verification/verify_collaboration_ranking.py) |
| `scripts/versus_personal_performance_probe.py` | [versus_personal_performance_probe.py](../../scripts/verification/versus_personal_performance_probe.py) |

删除 `scripts/analyze_weekly_tracks.py`（仍引用不存在的app.db）和 `scripts/split_feed_generator.py`（已完成的一次性源码拆分工具）；两者没有其他当前消费者。

迁移前逐项检查仓库代码及文档引用。18个工具无活跃代码调用者；受CI、Docker、部署、测试或同级模块导入约束的80个根文件保留，避免制造兼容包装层。尤其保留apply_version_governance→apply_l2_governance、发布准备、性能共用合同和全栈编排关系。

迁移同步修正 `__file__` 根目录定位；两个原本需模块方式启动的评测工具补齐直接CLI根路径。现行参考命令与历史报告的真实Markdown文件链接跟随迁移；历史命令正文不批量重写，由此表解释old→new关系。18个工具均通过从仓库外工作目录执行的CLI帮助或模块加载检查，未创建被指定的测试目标数据库。回调转发服务只验证加载，不用 `--help`误启动监听。

迁移文件首次Ruff检查有3处既有import排序问题，已在两个文件中修正，最终18文件检查通过；没有修改工具业务流程或执行数据写入。

## P5：文档及已删除历史证据

开发指南新增可选日志重定向方式；data说明补充日志与少量维护收据；前端说明移除旧入口和已删除模块引用，文档地图接入脚本说明。根README无需改变使用者入口，根AGENTS/CLAUDE保持一致，依赖与锁文件保留。

以下旧output子目录按用户决定删除。关联报告的文字、原SHA、历史失败和当时验收结论继续保留；原始数据库副本、恢复点、完整清单、日志、截图已经不存在，不承诺通过历史路径恢复，也没有另存副本。下表报告只列与该路径有直接引用的文件：

| 已删除目录 | 关联历史报告 |
| --- | --- |
| `output/documentation-acceptance-fixes-20261026/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/documentation-audience-20261026/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/documentation-cleanup-20261025/` | 没有直接路径引用；归属当时本地验收材料 |
| `output/documentation-consolidation-20261025/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/documentation-git-delivery-20261026/` | 没有直接路径引用；归属当时本地验收材料 |
| `output/documentation-main-integration-20261026/` | 没有直接路径引用；归属当时本地验收材料 |
| `output/documentation-prerequisites-20261026/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/documentation-refinement-20261026/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/documentation-usage-fixes-20261026/` | [2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md) |
| `output/playwright/` | [2026-09-22-ai-agent-v6-baseline-and-acceptance.md](2026-09-22-ai-agent-v6-baseline-and-acceptance.md)、[2026-08-27-spotify-track-l1-identity-migration.md](2026-08-27-spotify-track-l1-identity-migration.md)、[2026-08-24-yearly-review-semantic-correction.md](2026-08-24-yearly-review-semantic-correction.md)、[2026-10-03-public-analysis-time-ranges.md](2026-10-03-public-analysis-time-ranges.md)、[2026-10-23-release-cycle-next-batch-review.md](2026-10-23-release-cycle-next-batch-review.md)、[2026-10-09-music-detail-chart-performance-acceptance.md](2026-10-09-music-detail-chart-performance-acceptance.md)、[2026-10-23-title-release-attribution-repair.md](2026-10-23-title-release-attribution-repair.md)、[2026-08-16-music-search-baseline-and-delivery.md](2026-08-16-music-search-baseline-and-delivery.md)、[2026-10-24-release-cycle-review-and-delivery.md](2026-10-24-release-cycle-review-and-delivery.md)、[2026-10-21-versus-release-cycle-repair-acceptance.md](2026-10-21-versus-release-cycle-repair-acceptance.md)、[2026-10-03-cover-image-optimization-acceptance.md](2026-10-03-cover-image-optimization-acceptance.md)、[2026-10-02-collaboration-ranking-acceptance.md](2026-10-02-collaboration-ranking-acceptance.md)、[2026-10-08-versus-personal-statistics-performance-acceptance.md](2026-10-08-versus-personal-statistics-performance-acceptance.md)、[2026-08-30-l2-governance-execution-and-acceptance.md](2026-08-30-l2-governance-execution-and-acceptance.md)、[2026-10-25-documentation-cleanup-delivery.md](2026-10-25-documentation-cleanup-delivery.md)、[2026-10-07-release-date-and-empty-stats-acceptance.md](2026-10-07-release-date-and-empty-stats-acceptance.md)、[2026-10-03-album-metadata-delivery.md](2026-10-03-album-metadata-delivery.md)、[2026-10-21-release-cycle-remaining-review.md](2026-10-21-release-cycle-remaining-review.md)、[2026-10-06-track-credit-resolution-acceptance.md](2026-10-06-track-credit-resolution-acceptance.md) |
| `output/title-attribution-diagnosis-20261023/` | [2026-10-23-title-release-attribution-repair.md](2026-10-23-title-release-attribution-repair.md) |
| `output/title-attribution-repair-20261023/` | [2026-10-23-title-release-attribution-repair.md](2026-10-23-title-release-attribution-repair.md) |
| `output/versus-release-cycle-20261021/` | [2026-10-21-versus-release-cycle-repair-acceptance.md](2026-10-21-versus-release-cycle-repair-acceptance.md)、[2026-10-21-release-cycle-remaining-review.md](2026-10-21-release-cycle-remaining-review.md) |
| `output/versus-release-cycle-20261022-closeout/` | [2026-10-21-release-cycle-remaining-review.md](2026-10-21-release-cycle-remaining-review.md) |
| `output/versus-release-cycle-20261022-production/` | [2026-10-22-release-cycle-production-delivery.md](2026-10-22-release-cycle-production-delivery.md) |
| `output/versus-release-cycle-20261022-ui-rollback/` | [2026-10-21-release-cycle-remaining-review.md](2026-10-21-release-cycle-remaining-review.md) |
| `output/versus-release-cycle-20261023-review28/` | [2026-10-23-release-cycle-next-batch-review.md](2026-10-23-release-cycle-next-batch-review.md) |
| `output/versus-release-cycle-20261024-review24/` | [2026-10-24-release-cycle-review-and-delivery.md](2026-10-24-release-cycle-review-and-delivery.md) |
| `output/versus-release-cycle-20261024-shared-capabilities/` | [2026-10-24-release-cycle-review-and-delivery.md](2026-10-24-release-cycle-review-and-delivery.md) |

`data/backups/`内两份2026-09-27旧清理/预演库及附属WAL/SHM同样已删除。这项本地决定不影响生产服务器的备份轮转，也不禁止未来受控导入或维护创建新的恢复点。

## P6：验证

| 范围 | 结果 |
| --- | --- |
| 前端定向 | 9文件、141测试通过，包含当前V2桌面/手机、语言、退休深链、Home和架构护栏 |
| 前端ESLint | 修改的语言分布测试通过 |
| 迁移脚本 | 18工具CLI/加载检查通过；不创建测试目标库 |
| 迁移脚本Ruff | 18文件最终通过 |
| 最终受管构建 | TypeScript与Vite构建成功，日常输入清单有效，按原配置恢复本地服务 |
| 真实浏览器 | Chromium，1280×900及390×844；首页、年度总结、歌曲/专辑/艺人详情共10组合均200、页面级溢出0，未捕获控制台/页面/HTTP错误 |
| 文档及差异 | 含归档246份Markdown审计、Git差异及21个新文件空白检查通过，根AGENTS/CLAUDE一致 |

验证结果与源码补丁保存在本地ignored `data/maintenance/project-file-organization-20261026/`。10-26浏览器截图当时保存于 `output/playwright/project-file-organization/`，10-27按用户补充清理决定删除；结果JSON、交互记录和原失败日志保留，图片已不再可恢复。结果不冒称默认完整全栈、生产验收或真机验收；没有运行真实模型、资源压力或生产发布。

浏览器工具初版用“所有animate-pulse消失”作为就绪条件，因按需子区块仍保留占位而在专辑页超时；第二版把并非每类详情都有的“有效播放”尾注作为条件，在歌曲页超时。改为当前首屏真实指标后完成6组合，手机年报因嵌套main触发工具strict定位错误；改为外层main，仅补齐余下4组合。原失败日志保留，均为验收工具假设问题，没有修改产品来迎合工具，也不把本轮描述为首轮全通过。

额外完成手机艺人详情“榜单”栏目切换，实际排名趋势/周榜/年榜标题可见；首页“最近一章”滚动进入视口后内容可见、横向溢出0。浏览器session已经正常关闭，仅保留日常服务。

本次浏览器范围为实际首屏、现有详情栏目及页面横向布局；截图可能包含未进入视口的按需区块占位，不以此声称所有图表、列表与后台功能已完整验收。

## P7与后续边界

实施规划已归档，总表与台账按本轮交付更新。最终确认受管构建未过期、8000健康与4173页面正常、所属进程标准输出均指向data/logs且无本轮已删除文件占用。10-26正式文件集合从1,860份变为1,813份（当时未提交的文件集合，包含迁移与新增文档）；未修改依赖锁文件。大型业务文件拆分保留为后续建议，不阻止本次结项；独立业务待办不变。本轮未提交、推送或生产部署，代码恢复依赖Git基线与精确工作区差异，已删除的ignored证据和旧库不能由Git恢复。


## 2026-10-27 补充验收与精简

用户要求验收后确认继续修正和清理。本轮沿用同一事项与主题报告，补正脚本边界说明，继续精简仅由测试引用的前端链，并删除已验收的小量浏览器材料；不扩大到正式数据、依赖、生产或大型业务重构。

### 补正说明与导航

脚本说明现在明确：`probe_ai_yearly_report_text_quality.py`默认读取报告缓存，`--force`会进入生成流程并可能调用模型；没有为了验证该说明实际执行生成。脚本README补充两个lib辅助模块和两个工具测试入口，保留98个业务工具/合同的原调用路径与用途分组。

### 退役剩余13文件并承接有效测试

复核当前静态应用入口后，原保留13文件均只有测试消费者，共58,300字节。测试不再作为保留失去产品入口实现的理由，13文件全部删除；与旧YearlyPeriodNotice关联的46行专属CSS一并删除。当前V2、导入工作台、Markdown组件和已注册路由的业务源码没有改变。

| 原消费者/测试 | 本轮处理 |
| --- | --- |
| 月度趋势、发行时间线架构测试 | 移除对3个退役图表源码的检查，现有Analysis/RankTrend/Versus等活跃图表的LazyEChart护栏保留 |
| FormattedText测试 | 退役旧组件与专属测试文件，安全HTML净化、强调与危险链接验证迁到实际使用的AiMarkdown；旧段落className策略不再保留 |
| 专辑enrichment测试 | 旧单曲封面展示与映射仅服务已撤下的发行档案，退役两项专属展示测试及测试文件；不改后端enrichment兼容接口 |
| YearlyPeriodNotice测试 | 截止日期与完整年度隐藏范围说明迁到当前MobileYearlyCover，继续覆盖年度进行中和完整年度两种状态 |
| ImportPreflightPanel测试 | 增量计数、只读计划查看、歧义输入模式选择和阻断执行迁到当前DataImportWorkspace；DataHealthSummary原有检查保留 |
| LegacyTrackDetailRedirect测试 | 旧测试构造的legacy-track路由没有在App注册；移除该独立组件，改为测试App中实际注册的Billboard/canonical/l1三类旧路径，保留查询参数跳转到现有详情页；后端身份解析未改 |

累计退役61个候选前端文件；另有2个纯退役组件测试文件删除。正式文件集合最终为1,798份（相对本轮基线净少62份，包含新增文档及脚本迁移），依赖及锁文件不变。

### 已验收材料清理

- `output/playwright/project-file-organization/`：删除11个文件、7,644,948字节。
- `.playwright-cli/`：删除189个文件、968,236字节。

两处合计删除8,613,184字节（约8.21 MiB）；删除前没有打开文件，没有移动到其他目录留副本。当前运行日志与源码补丁收据保留。原浏览器结果和历史失败JSON/日志继续可读，本轮不再另建图片或快照。

### 验证与结束范围

- 9个定向前端文件、128项测试通过；实际修改的6个测试文件ESLint通过。覆盖架构、手机年度、Markdown、数据健康/导入工作台、旧路径、退休详情与语言分布。
- 最终受管TypeScript/Vite构建、8000健康与4173入口检查通过，新进程日志仍写入data/logs，构建清单有效。
- 活跃业务实现未改，10-26实际10个页面/视口组合结果保留为当时验收，不重复执行全站浏览器或虚构本轮新截图验收。
- 文档审计与跟踪/新增文件空白检查通过；补充源码差异纳入含新增文件的完整补丁，保留10-26检查点。

本轮未提交、推送或生产部署。未提交源码补丁继续保留至后续Git交付，已删除图片与旧CLI快照不由Git恢复。

## 2026-10-27 脚本导入遗漏修复与最终复验

补充只读验收发现：`runtime_df_compare.py`已迁到`scripts/performance/`，但`backend/tests/unit/test_runtime_measurement_script.py`仍从`scripts`根模块导入，实际复现`ImportError`。此前18个迁移脚本的CLI/加载验证与前端测试没有覆盖这个后端测试消费者；此前通过的局部结果保留，但不足以证明所有脚本消费者均已同步。

用户授权修复、相关测试、更新报告和再次验收，并明确暂不提交或推送。本轮只将该测试的导入改为`from scripts.performance import runtime_df_compare`，不新增旧路径兼容壳，不改脚本行为或应用业务。

验证结果：

- `.venv/bin/pytest backend/tests/unit/test_runtime_measurement_script.py -q -p no:cacheprovider`：23项通过，耗时5.87秒。使用项目默认测试隔离和临时库，不运行正式数据库探针。出现1项当前Python环境的urllib3/LibreSSL兼容警告，未造成测试失败。
- `.venv/bin/ruff check --no-cache backend/tests/unit/test_runtime_measurement_script.py`：通过。
- 对`backend/`与`scripts/`的Python AST检查：18个迁移脚本的旧根模块导入残留为0；当前规则与源码中的旧CLI路径同时复核。
- 最终文档审计246份通过，跟踪与21个新增文件的空白检查通过，根AGENTS/CLAUDE一致。受管构建仍未过期，8000健康与4173入口均200；保留数据、凭据和依赖目录的路径/inode核对通过。
- 既有128项前端测试、受管构建和10个页面/视口组合证据沿用各自记录，不将它们描述为本轮重新执行的结果。本轮未修改前端源码，无需重复构建或浏览器矩阵。

本轮受影响测试和迁移引用复验通过，关闭这处验收遗漏；不据此声称全量后端、完整全栈或远端CI已通过。日志保存在本地ignored `data/maintenance/project-file-organization-20261026/import-fix-backend-tests.log`，完整恢复补丁继续纳入当前改动。没有继续清理缓存或数据，没有提交、推送或生产发布。

## 2026-10-27 Git交付

用户在最终只读验收后授权提交并推送。本阶段使用唯一现有工作树，在`codex/project-file-organization-20261027`分支交付；直接推送main会因本轮源码路径触发Production Release，因此不推送main、不修改发布触发规则，不执行部署。

提交范围以本地`git-delivery-scope.json`登记的129个精确路径为准，包含21个新增路径；脚本移动需将原路径删除与新路径一起交付。README、根AGENTS/CLAUDE和面向使用者的CHANGELOG经核对不需要额外变更；开发、前端、数据、脚本入口与文档地图已经同步。正式数据、日志、补丁与验收收据不进入Git。

前文未提交/未推送的陈述是各验收阶段当时的边界。本阶段交付结果如下：

- 整理提交为`cbf7ef98ab919cb5973c0d9f14d4356d7fd4a870`，标题为`chore: 整理项目文件并退役无消费者代码`；129个原始路径与白名单完全相同，Git识别18组重命名后显示111个变更文件。没有夹带其他工作区内容。
- 文档审计246份、staged差异检查、Ruff、ruff format、mypy和Detect secrets全部通过，提交时项目hooks再次通过。已有受影响测试及浏览器证据按原版本复用。
- 已推送到`origin/codex/project-file-organization-20261027`，远端分支SHA与整理提交一致。main仍为`2da50438f6631eb36964daaf0aa9a70116081681`，没有合入或推送main。
- 首次远端观察：[质量CI 40516397309](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40516397309)为`queued`，尚不能标记远端CI成功。同SHA的Production Release运行列表为空；No Deploy工作流的路径条件未命中，没有相应运行。
- 本节及状态总表作为随后独立文档收尾提交推送，最新分支SHA与CI状态以Git远端和Actions为准；这次文档提交不改变已验收源码。没有创建PR、修改工作流或执行生产部署。


## 2026-10-27 主线整合与CI补修

用户随后授权合并。main在`2da50438`，分支可快进整合；合并推送main会按现有Production Release规则自动启动生产发布，本聊天已明确告知该影响。先等分支质量CI通过，再整合，不更改或跳过质量/发布工作流。

分支首次完整质量检查[40516549378](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40516549378)在后端unit阶段失败：3275通过、1失败、2跳过、1441未选，耗时430.36秒；契约、后端lint及前端阶段因该失败未执行。失败来自`test_snapshot_rebuild_cli.py`用`importlib.import_module(f"scripts.rebuild_{kind}")`动态构造旧路径，其中account_archive工具已经迁到maintenance。此前静态Import/ImportFrom检查没有覆盖动态模块名，旧局部验收不足以宣称所有消费者迁移完整；保留该次失败，不改写为通过。

修复将两种CLI的实际模块路径作为显式测试参数，account_archive使用`scripts.maintenance.rebuild_account_archive`，governance维持`scripts.rebuild_governance`；原旧库升级、维护顺序与播放记录保留断言不变。额外检查backend测试与脚本中的importlib/runpy动态加载入口，未见其他相同迁移遗漏。本次增加一个必要测试文件到原交付范围，不新增业务逻辑或兼容壳。

本地定向`test_snapshot_rebuild_cli.py`两项通过（0.06秒），环境仍有同一urllib3/LibreSSL警告。日志保存于`data/maintenance/project-file-organization-20261026/merge-dynamic-import-tests.log`；原远端完整作业日志保存在同目录`merge-ci-job.log`。该修复提交时仍等待远端质量结果，尚未合并main或触发生产发布；后续结果见下节。


### 分支CI通过与主线快进整合

修复提交`16ad95cc4ef0661793287c8d18a5988c96c4ce4d`的[质量CI 40518424036](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40518424036)最终为`completed/success`：后端unit 3276通过、2跳过，contract 578通过，后端lint通过，前端98个测试文件通过、1跳过，817项测试通过、4跳过，TypeScript/Vite构建通过。文档审计与其8项工具回归通过；没有把前次失败或跳过改记为通过。完整成功日志与元数据分别保存在本地`merge-ci-success.log`和`merge-ci-success.json`。

确认远端main仍是`2da50438`、工作区干净且分支为其后代后，将本地main快进至`16ad95cc`并切回main。源提交`cbf7ef98`（整理）、`1cbd0ad1`（交付文档）、`16ad95cc`（动态导入测试修复）均以原完整SHA保留，无冲突、无重写；后续本节及状态表的收尾提交仅改文档，随main推送。

main推送会按既有规则触发独立质量CI和自动Production Release。分支CI成功不表示main新SHA的CI或生产发布已经成功，也不表示生产现场验收完成；不改工作流，不使用跳过CI或发布的提交标记。源分支收尾在main包含性与推送核对后处理本地引用；远端源分支保留为已合并引用，本次不额外删除远端分支。
