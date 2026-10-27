# 维护与验证工具

面向维护者。日常启动和开发见[开发指南](../CONTRIBUTING.md)，统计与维护规则见[文档地图](../docs/README.md)，本地运行文件见[数据说明](../data/README.md)。

先按用途选择工具，再查看对应CLI帮助。表中“只读源库”允许生成报告；浏览器和API观测可能触发应用已有的派生缓存维护。标为写入、发布安装或在线模型的工具，只在对应任务的明确范围内使用，不能当普通检查命令运行。

## 调用与兼容

- 日常入口继续使用 `python3 scripts/start_daily.py`；源码或静态资源改变后使用 `--build`，不要手工伪造构建清单。
- Python工具从项目根目录用 `.venv/bin/python scripts/<分组>/<工具>.py --help`查看参数；也可用 `-m scripts.<分组>.<工具>`。下表保留根目录的稳定CLI和模块入口，不要求统一迁移。
- Node工具使用 `node scripts/<工具>.mjs --help`，shell入口使用各自说明。共用模块、JSON Schema和本地回调服务不是通用CLI；回调服务不接受 `--help`，直接运行会监听端口。
- `prepare_*`、排名发布、快照重建及治理工具有明确副本、revision与writer lease合同。不要仅凭文件名猜测写入对象，先读参数和对应规则。
- 新增工具按用途放入已有分组。被CI、Docker、部署脚本或Python导入消费的入口改名时，同步检查调用者、根目录定位和共用合同。
- 日常服务日志可重定向到已忽略的 `data/logs/`；任务验收材料按需写入 `output/`，交付时随任务收尾，不让日常入口依赖该目录。

## 常用启动与门禁

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [ci_baseline_parity.py](ci_baseline_parity.py) | CI与本地门禁基线对齐 | 本地静态检查 |
| [docs_audit.py](docs_audit.py) | 文档链接、锚点、索引与指令检查 | 本地静态检查 |
| [fullstack_preflight.py](fullstack_preflight.py) | 完整门禁前的轻量预检 | 观测/验证；可写报告与派生缓存 |
| [fullstack_verification_check.sh](fullstack_verification_check.sh) | 完整全栈门禁编排 | 编排/测试；写临时产物 |
| [fullstack_verification_lock.py](fullstack_verification_lock.py) | 完整门禁共享阶段排他锁 | 观测/验证；可写报告与派生缓存 |
| [phase5_check.sh](phase5_check.sh) | 架构与产品化门禁入口 | 编排/测试；写临时产物 |
| [quickstart_smoke.py](quickstart_smoke.py) | 首次启动与基础使用检查 | 编排/测试；写临时产物 |
| [start_daily.py](start_daily.py) | 本地日常前后端启动与受管构建 | 启动服务；可构建前端/维护派生缓存 |
| [test_storage_guard.py](test_storage_guard.py) | 验证临时文件的归属与清理 | 编排/测试；写临时产物 |
| [validate_container_image.py](validate_container_image.py) | 镜像应用载荷的私有数据库检查 | 本地静态检查 |

## 发布准备与传输

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [closed_publication_source.py](closed_publication_source.py) | 已关闭副本的只读发布适配器 | 共用模块/静态合同 |
| [prepare_billboard_publications.py](prepare_billboard_publications.py) | 副本构建与精确榜单发布转移 | 副本构建/发布安装；按子命令 |
| [prepare_music_detail_projection.py](prepare_music_detail_projection.py) | 副本准备与精确详情投影转移 | 副本构建/发布安装；按子命令 |
| [prepare_music_search_resume.py](prepare_music_search_resume.py) | 搜索快照恢复工作区准备 | 副本构建/发布安装；按子命令 |
| [rebase_music_search_preflight.py](rebase_music_search_preflight.py) | 已验证搜索快照与升级副本对齐 | 副本构建/发布安装；按子命令 |
| [versus_rank_publication.py](versus_rank_publication.py) | 副本排名构建与精确安装 | 副本构建/发布安装；按子命令 |

## 数据维护与治理

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [apply_l2_governance.py](apply_l2_governance.py) | 规划或应用版本身份治理 | 维护写入；按CLI选择预览/应用 |
| [apply_version_governance.py](apply_version_governance.py) | L1/L2/L3治理稳定入口 | 维护写入；按CLI选择预览/应用 |
| [approve_artist_language_long_tail_batch.py](approve_artist_language_long_tail_batch.py) | 长尾艺人语言审核与批准 | 维护写入；按CLI选择预览/应用 |
| [approve_artist_language_second_pass.py](approve_artist_language_second_pass.py) | 既有第二批语言证据批准 | 维护写入；按CLI选择预览/应用 |
| [audit_artist_genre_source_quality_batch.py](maintenance/audit_artist_genre_source_quality_batch.py) | 既有流派来源质量审核及纠正 | 维护写入；按CLI选择预览/应用 |
| [audit_l1_external_identity_risks.py](maintenance/audit_l1_external_identity_risks.py) | L1外部身份风险及拆分模拟 | 只读源库；可写报告 |
| [audit_spotify_track_credits.py](maintenance/audit_spotify_track_credits.py) | Spotify曲目署名证据对比 | 只读源库；可写报告 |
| [audit_track_l1_identity.py](maintenance/audit_track_l1_identity.py) | Canonical与L2/L3身份关系检查 | 只读源库；可写报告 |
| [backfill_cover_thumbnails.py](backfill_cover_thumbnails.py) | 从本地原图生成封面尺寸变体 | 写本地图片缓存 |
| [backfill_spotify_album_artist_credits.py](backfill_spotify_album_artist_credits.py) | 在Online Backup中补专辑艺人证据 | 显式副本/临时环境；有写入 |
| [backfill_spotify_release_dates.py](backfill_spotify_release_dates.py) | 有界发行日期和专辑艺人维护 | 维护写入；按CLI选择预览/应用 |
| [backfill_spotify_track_artist_credits.py](backfill_spotify_track_artist_credits.py) | 可恢复的曲目多艺人证据补全 | 维护写入；按CLI选择预览/应用 |
| [cleanup_historical_fk_debt.py](cleanup_historical_fk_debt.py) | 历史外键债务预览或受控清理 | 维护写入；按CLI选择预览/应用 |
| [fetch_covers.py](fetch_covers.py) | Spotify封面及头像下载维护 | 写本地图片缓存 |
| [fetch_track_durations.py](fetch_track_durations.py) | Spotify曲目和发行元数据维护 | 维护写入；按CLI选择预览/应用 |
| [import_artist_genre_overrides.py](import_artist_genre_overrides.py) | 导入已审流派种子事实 | 维护写入；按CLI选择预览/应用 |
| [import_artist_language_sources.py](import_artist_language_sources.py) | 导入已审语言事实或旧候选 | 维护写入；按CLI选择预览/应用 |
| [import_metadata_pre_review_batch.py](maintenance/import_metadata_pre_review_batch.py) | 既有流派和语言预审批次导入 | 维护写入；按CLI选择预览/应用 |
| [preview_release_evidence.py](maintenance/preview_release_evidence.py) | Online Backup上的发行参照与日期审核预览 | 显式副本/临时环境；有写入 |
| [rebuild_account_archive.py](maintenance/rebuild_account_archive.py) | 显式音乐档案快照维护 | 维护写入；按CLI选择预览/应用 |
| [rebuild_governance.py](rebuild_governance.py) | 显式治理统计快照维护 | 维护写入；按CLI选择预览/应用 |
| [rebuild_music_search_derived_data.py](rebuild_music_search_derived_data.py) | 四变体精确搜索快照维护 | 维护写入；按CLI选择预览/应用 |
| [rebuild_music_search_index.py](rebuild_music_search_index.py) | 搜索候选索引维护 | 维护写入；按CLI选择预览/应用 |
| [refresh_import_derived_data.py](refresh_import_derived_data.py) | 导入后派生数据维护 | 维护写入；按CLI选择预览/应用 |
| [repair_album_tracklists.py](repair_album_tracklists.py) | 专辑完整目录审计及有界修复 | 维护写入；按CLI选择预览/应用 |
| [review_artist_genre_suggestions.py](review_artist_genre_suggestions.py) | 流派候选人工审核入口 | 维护写入；按CLI选择预览/应用 |
| [review_high_impact_metadata_batch.py](review_high_impact_metadata_batch.py) | 既有高影响流派与语言批次审核 | 维护写入；按CLI选择预览/应用 |

## 验证与浏览器

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [account_archive_probe.py](verification/account_archive_probe.py) | 音乐档案覆盖与概览检查 | 只读源库；可写报告 |
| [api_boundary_probe.py](api_boundary_probe.py) | API参数和只读边界检查 | 观测/验证；可写报告与派生缓存 |
| [api_smoke_probe.py](api_smoke_probe.py) | API读取冒烟检查 | 观测/验证；可写报告与派生缓存 |
| [artist_genre_coverage_probe.py](artist_genre_coverage_probe.py) | 按播放时长检查流派覆盖 | 只读源库；可写报告 |
| [audit_yearly_review_v2.py](audit_yearly_review_v2.py) | 年度V2确定性证据检查 | 观测/验证；可写报告与派生缓存 |
| [billboard_year_end_consistency_probe.py](verification/billboard_year_end_consistency_probe.py) | 年榜与周榜聚合一致性检查 | 观测/验证；可写报告与派生缓存 |
| [correct_project_release.py](correct_project_release.py) | 在隔离副本预演项目日期纠正 | 显式副本/临时环境；有写入 |
| [cover_image_probe.py](verification/cover_image_probe.py) | 真实浏览器封面覆盖与缓存观测 | 观测/验证；可写报告与派生缓存 |
| [frontend_chart_interaction_smoke.mjs](frontend_chart_interaction_smoke.mjs) | 图表交互浏览器检查 | 观测/验证；可写报告与派生缓存 |
| [frontend_control_inventory_smoke.mjs](frontend_control_inventory_smoke.mjs) | 控件清单及交互检查 | 观测/验证；可写报告与派生缓存 |
| [frontend_cross_browser_smoke.mjs](frontend_cross_browser_smoke.mjs) | 跨浏览器检查 | 观测/验证；可写报告与派生缓存 |
| [frontend_interaction_smoke.mjs](frontend_interaction_smoke.mjs) | 业务交互检查 | 观测/验证；可写报告与派生缓存 |
| [frontend_long_list_smoke.mjs](frontend_long_list_smoke.mjs) | 长列表与分页检查 | 观测/验证；可写报告与派生缓存 |
| [frontend_route_smoke.mjs](frontend_route_smoke.mjs) | 路由与视口检查 | 观测/验证；可写报告与派生缓存 |
| [govern_album_release_dates.py](govern_album_release_dates.py) | 副本上的独立日期登记和审核 | 显式副本/临时环境；有写入 |
| [import_governance_real_acceptance.py](import_governance_real_acceptance.py) | 真实来源的隔离导入治理验收 | 显式副本/临时环境；有写入 |
| [incremental_import_end_to_end_acceptance.py](incremental_import_end_to_end_acceptance.py) | 合成数据增量导入矩阵 | 显式副本/临时环境；有写入 |
| [l2_l3_integrity_probe.py](l2_l3_integrity_probe.py) | 身份及专辑归属完整性检查 | 只读源库；可写报告 |
| [music_detail_chart_acceptance.py](verification/music_detail_chart_acceptance.py) | 隔离副本上的详情正确性与资源验收 | 显式副本/临时环境；有写入 |
| [music_detail_equivalence_probe.py](verification/music_detail_equivalence_probe.py) | 详情摘要与子视图等价性检查 | 观测/验证；可写报告与派生缓存 |
| [openapi_operation_audit.py](openapi_operation_audit.py) | OpenAPI操作覆盖检查 | 观测/验证；可写报告与派生缓存 |
| [openapi_parameter_boundary_audit.py](openapi_parameter_boundary_audit.py) | OpenAPI参数边界覆盖检查 | 观测/验证；可写报告与派生缓存 |
| [phase_d2_search_delta_acceptance.py](phase_d2_search_delta_acceptance.py) | 隔离真实副本的搜索增量验收 | 显式副本/临时环境；有写入 |
| [phase_d_real_db_acceptance.py](phase_d_real_db_acceptance.py) | 隔离真实副本的派生维护验收 | 显式副本/临时环境；有写入 |
| [phase_e_real_db_acceptance.py](phase_e_real_db_acceptance.py) | 隔离真实副本的故障恢复验收 | 显式副本/临时环境；有写入 |
| [probe_agentic_yearly_report.py](probe_agentic_yearly_report.py) | 真实AI年度任务质量检查 | 含显式在线模型/任务请求 |
| [probe_ai_yearly_report_quality.py](probe_ai_yearly_report_quality.py) | 年报确定性输入合同检查 | 观测/验证；可写报告与派生缓存 |
| [probe_ai_yearly_report_text_quality.py](probe_ai_yearly_report_text_quality.py) | 年报文本质量检查 | 默认读取缓存；`--force`会生成报告并可能调用模型 |
| [probe_visual_yearly_report_artifact.py](probe_visual_yearly_report_artifact.py) | 视觉年报任务及产物检查 | 含显式在线模型/任务请求 |
| [verify_collaboration_ranking.py](verification/verify_collaboration_ranking.py) | 显式副本上的合作曲排行对照 | 显式副本/临时环境；有写入 |
| [versus_personal_browser_probe.py](versus_personal_browser_probe.py) | 真实浏览器榜单对决验收 | 观测/验证；可写报告与派生缓存 |
| [versus_personal_performance_probe.py](verification/versus_personal_performance_probe.py) | 隔离副本的榜单对决正确性与资源验收 | 显式副本/临时环境；有写入 |
| [yearly_review_v2_probe.py](yearly_review_v2_probe.py) | 年度V2真实数据合同与读取观测 | 观测/验证；可写报告与派生缓存 |

## 性能与模型评测

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [benchmark_ai_agent_compare.py](performance/benchmark_ai_agent_compare.py) | 只读实体比较工具冷暖测量 | 观测/验证；可写报告与派生缓存 |
| [benchmark_api.py](benchmark_api.py) | HTTP请求观测与耗时测量 | 观测/验证；可写报告与派生缓存 |
| [evaluate_ai_agent_harness.py](evaluate_ai_agent_harness.py) | AI问答离线黄金问题评估 | 离线评估；写报告 |
| [evaluate_ai_agent_v6_freeform.py](performance/evaluate_ai_agent_v6_freeform.py) | V6固定自由问答清单评测 | 含显式在线模型/任务请求 |
| [evaluate_ai_question_matrix.py](evaluate_ai_question_matrix.py) | 问答矩阵静态校验及显式在线评估 | 含显式在线模型/任务请求 |
| [evaluate_ai_report_performance.py](evaluate_ai_report_performance.py) | AI年报质量与耗时评测 | 含显式在线模型/任务请求 |
| [frontend_runtime_soak.mjs](frontend_runtime_soak.mjs) | 浏览器长期运行观测 | 观测/验证；可写报告与派生缓存 |
| [frontend_spa_ready_probe.py](frontend_spa_ready_probe.py) | 首页首入及同页返回就绪测量 | 观测/验证；可写报告与派生缓存 |
| [frontend_web_vitals_probe.mjs](frontend_web_vitals_probe.mjs) | 浏览器页面加载指标观测 | 观测/验证；可写报告与派生缓存 |
| [loading_performance_probe.py](loading_performance_probe.py) | 首页及详情加载观测 | 观测/验证；可写报告与派生缓存 |
| [music_search_performance_probe.py](music_search_performance_probe.py) | 搜索接口与读取性能观测 | 观测/验证；可写报告与派生缓存 |
| [performance-report.schema.json](performance-report.schema.json) | 性能报告JSON Schema | 共用模块/静态合同 |
| [performance_catalog.py](performance_catalog.py) | 性能观测消费者分类表 | 共用模块/静态合同 |
| [performance_contract.py](performance_contract.py) | 共用观测数据合同 | 共用模块/静态合同 |
| [performance_server.py](performance_server.py) | 隔离副本的独立服务进程工具 | 观测/验证；可写报告与派生缓存 |
| [runtime_df_compare.py](performance/runtime_df_compare.py) | 已有D/F运行记录离线汇总 | 读取既有记录；写汇总 |
| [runtime_matrix_run.py](runtime_matrix_run.py) | 隔离环境的单组启动矩阵 | 显式副本/临时环境；有写入 |
| [runtime_matrix_suite.py](runtime_matrix_suite.py) | 隔离启动矩阵编排 | 显式副本/临时环境；有写入 |
| [runtime_measurement.py](runtime_measurement.py) | 隔离副本及正常生命周期测量 | 显式副本/临时环境；有写入 |
| [runtime_resource_probe.py](runtime_resource_probe.py) | 既有服务进程资源观测 | 观测/验证；可写报告与派生缓存 |

## 开发辅助

| 工具 | 用途 | 运行边界 |
| --- | --- | --- |
| [oauth_redirect_server.py](dev/oauth_redirect_server.py) | 本地8888到8000的OAuth回调转发 | 启动本地回调服务 |
| [spotify_oauth_external_probe.py](spotify_oauth_external_probe.py) | 显式Spotify与ngrok入口检查 | 显式外部网络检查 |

## 共用辅助与工具测试

- [Chrome定位辅助](lib/chrome_executable.mjs)：供浏览器工具复用可执行文件定位。
- [浏览器性能合同](lib/performance_browser_contract.mjs)：复用路由就绪和观测边界。
- [文档审计回归](tests/test_docs_audit.py)：使用 `.venv/bin/python -m unittest scripts.tests.test_docs_audit`。
- [浏览器性能合同回归](tests/performance_browser_contract.test.mjs)：使用 `node --test scripts/tests/performance_browser_contract.test.mjs`。

## 迁移与历史

2026-10-26整理将18个低耦合工具按用途迁移，删除旧每周曲目分析和一次性源码拆分工具。完整旧路径到新路径、保留理由和验证见[整理交付报告](../docs/reports/2026-10-26-project-file-organization.md)。历史命令以对应记录时点为准，实际调用使用本页路径。
