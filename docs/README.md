# SpotifyStats 文档地图

- [原生热请求有界归因](reports/2026-10-17-native-hot-request-attribution.md)：14正文/守恒/实际恢复及独立审阅通过，采样成本与并行重复工作分列；学校本次资源已清理，第一轮最小候选729a0ed3已本地提交、正确性通过，新镜像原生收益待验，完整资源HOLD。

- [学校共享宿主原生资源准入](reports/2026-10-17-school-native-resource-admission.md)：共享限额和双批时间已获授权；旧无效窗保留，准备/复用/WAL工具135项验证通过，两版第1次ready样本已恢复，首对热305/303ms超100ms、候选有效FAIL，R2停止转R3，LRU未启动；完整资源HOLD；三旧run及两镜像实际清理、原16/29保全。

- [资源对照镜像与可移植验收包](reports/2026-10-17-oom-images-portable-acceptance.md)：R1本地准备完成，实际两镜像、114窗口与独立客户端/审计/恢复通路通过有界自检；阶段提交bdcf，原生环境与资源准入HOLD。

- [累计资源候选冻结与阶段提交](reports/2026-10-17-oom-candidate-freeze-review.md)：R0独立审阅无阻塞，AI测试线程竞态在HEAD自然复现并最小隔离；23文件本地阶段提交c844，资源准入与发布HOLD。

- [详情资源与OOM完整收口规划](plans/2026-10-17-oom-resource-closeout-plan.md)：R0候选审阅→R1镜像/验证包→R2原生准入→必要整改→整合CI→发布准备→唯一首次→72小时观察与工作树收尾。原64MiB/多实体50%及LRU合同不降标；当前R0/R1推进，本地按完整阶段提交，原生环境与正式发布仍有准入条件。

- [有限多实体读取与空闲平台验证](reports/2026-10-17-oom-finite-read-platform.md)：空闲/六实体读取各15分钟均平台，7帧根与结果缓存稳定复用；18正文/六事实/两strict一致。无新增业务补丁，22文件沿用10-16同版本full8，原生/64MiB/长期并发/生产OOM仍OPEN。

- [日期警告候选自然启动与累计门禁](reports/2026-10-16-oom-date-warning-startup-validation.md)：A-B-A ready低20.719–25.133MiB，27响应/六事实/三strict一致；默认full8与三浏览器通过，AI线程SQLite警告保留。启动峰/CPU/读取增长未收口，22文件仅本地、整体资源HOLD。

- [启动arena路径与迟载导入对照](reports/2026-10-16-oom-arena-paths-and-import-timing.md)：确认OpenCC和linecache根；提前导入ready低17.203MiB、峰未改善。仅保留日期警告最小候选，139项/Linux27返回及27时长表一致；后续自然对照与完整门禁见新报告。

- [启动arena持有者与探针自干扰](reports/2026-10-16-oom-startup-arena-owner-attribution.md)：相同业务代码改原生采样，ready低52.590MiB属于观测校正、峰未降；缓存/模块常量/代码缓存帧路径已定位，18响应/六事实/两strict一致。22文件不变，未新增业务修复，整体资源Partial。
- [读取驻留缓存与分配器归因](reports/2026-10-16-oom-read-cache-residency-attribution.md)：四个181.076MiB估算根三轮稳定、定向失效后全部释放；保留缓存trim下降15.273MiB。29项/9完整响应/两段strict通过，未新增业务修复，22文件候选不变，整体OOM仍Partial。
- [合作署名窄表展开与累计候选审阅](reports/2026-10-15-oom-collaboration-credit-expansion-and-cumulative-review.md)：441项、52旧builder/144榜、231组HEAD实体及三窗守恒通过；后端2项存储门槛失败在HEAD同现，整体Partial。累计启动峰1303.668→995.094MiB、末尾893.277→607.395MiB，二十二文件保留本地，下一读取驻留，资源HOLD。
- [启动CPU归因与专辑时长最后消费点](reports/2026-10-15-oom-startup-cpu-duration-attribution.md)：同一B启动CPU差46.060秒；本轮A/C138.440/134.050秒，稳定回归未证且未全排除。释放无用时长/Series引用，417项/231组对账及三窗守恒通过；C启动最高采样991.102MiB、读取增长69.758MiB，二十一文件仅本地，整体Partial/HOLD。
- [专辑发行日期以两列键查询代替整表合并](reports/2026-10-15-oom-album-release-lookup.md)：右键唯一、源表及统计一致；411项/231组旧builder与两窗守恒通过，merge55→2列、owned返回复用。启动最高采样仅低2.445MiB、CPU更高，二十文件仅本地，整体Partial/HOLD。
- [快进纪录在assign前投影必要列](reports/2026-10-15-oom-skip-storm-projection.md)：392项/90组旧函数及两窗守恒通过，assign输入52/56/48→5/5/3列；启动最高采样1014.605→1008.027MiB，仅局部候选，十九文件未提交，整体OOM仍Partial/HOLD。
- [Records计算结束后释放工作表再处理封面](reports/2026-10-15-oom-records-presentation-lifetime.md)：373项及两窗守恒通过；封面入口工作表引用归零，首次964.086→750.301MiB；整体峰值仍在计算阶段。十七文件仅本地，整体OOM仍Partial/HOLD。
- [实体构建复用已具逻辑身份事件表](reports/2026-10-15-oom-entity-identity-ownership.md)：源表不变、主返回表独立；300项、156组旧builder/468主表及468时长表一致。两窗启动最高采样1020.035→1017.312MiB，小幅差异未证稳定OOM收益；十六文件仅本地，整体Partial/HOLD。
- [合作聚合中间表必要列投影](reports/2026-10-15-oom-collaboration-aggregate-projection.md)：258项、52次builder/144旧聚合榜/26直接调用一致；两窗总体最高采样1025→1052MiB、读取658→664MiB，未改善。十五文件仅本地局部候选，整体OOM仍Partial/HOLD。
- [启动最高采样归因与合作事件表生命周期修复](reports/2026-10-15-oom-collaboration-event-lifetime.md)：231项、52次旧函数对账及144榜相同；两有效窗启动最高采样1027→1021MiB、最终低27.1MiB。十四文件仅本地，驻留及整体OOM仍Partial/HOLD。
- [合作纪录select先筛选后复制](reports/2026-10-15-oom-collaboration-select-projection.md)：225项、52次旧函数对账及144份聚合相同；两窗启动采样峰1054→1031MiB、最终低11.8MiB。十三文件仅本地，驻留及整体OOM仍Partial/HOLD。
- [歌曲canonical合并前宽表副本修复](reports/2026-10-15-oom-track-merge-ownership.md)：194项、歌曲/实体各39组对账通过；两窗启动采样峰1078→1062MiB，末尾仅低2.8MiB；十二文件仅本地，驻留及整体OOM仍Partial/HOLD。

- [合作纪录署名键收集最小候选](reports/2026-10-15-oom-collaboration-credit-keys.md)：169项/22完整事实与66榜对账通过；消除六次宽表复制。两窗启动采样峰1081→1047MiB，因果收益未量化、驻留未改善；十一文件仅本地，整体资源Partial/HOLD。

- [Records启动宽表生命周期修复](reports/2026-10-15-oom-records-working-set.md)：150项/39旧函数对账通过；启动采样峰下降56.828MiB，三窗9响应/六事实/strict一致；九文件仅本地，驻留及整体OOM仍Partial。

- [外层时长候选撤回与Python分配器归因](reports/2026-10-15-oom-duration-rejected-allocator-attribution.md)：外层134项/35响应对账通过但峰值收益未证，恢复原八文件；malloc只归因，驻留下降伴随启动峰/增长/仿真CPU代价。三窗9响应/六事实/strict一致，下一目标Records启动宽表，整体OOM仍Partial。
- [艺人专辑中间表投影与生命周期](reports/2026-10-15-oom-artist-album-intermediates.md)：120通过，两窗9响应/六事实/strict一致；首次峰增量低30.102MiB、读取峰低20.832MiB。末尾高9.301MiB且arena差异启动后已存在，驻留收益未证明；八文件未提交推送部署，整体OOM仍Partial。
- [艺人统计首次载入与署名展开投影](reports/2026-10-15-oom-artist-first-projection.md)：130通过，两窗9完整响应/六事实/strict一致；首次峰增量低25.289MiB、本轮读取峰低27.465MiB、末尾低8.230MiB。七文件未提交推送部署，启动及整体OOM仍Partial。
- [冷个人统计曲目/Top250输入投影](reports/2026-10-14-oom-cold-stats-track-projection.md)：151通过，三窗33完整响应/六事实/strict一致，冷专辑峰低36–39MiB；总峰/末尾未降，下一目标艺人stats首次；六文件未提交推送部署，整体资源Partial。
- [镜像封装、启动重排与有界读取验证](reports/2026-10-14-oom-image-startup-bounded-verification.md)：169通过；封存基底两镜像/33完整响应/六事实/strict一致，启动峰低90MiB，读取略高；默认Python基镜像构建未通过，未提交推送部署，整体资源Partial。
- [OOM启动峰值与读取增长隔离候选](reports/2026-10-14-oom-peak-growth-isolated-candidate.md)：仅Dockerfile固定mmap阈值128KiB；同源采样峰/末尾/增长改善，9完整响应、六统计/Records事实与strict通过；旧代码/arena试验不采用，未提交推送部署，原生资源/生产OOM仍Partial。

- [维护完成原生回收生产交付与首次验收](reports/2026-10-14-native-trim-maintenance-production-delivery.md)：固定b126已正式发布；研发/main CI及Release通过，原首次90/90、116/116 API、三strict与wrapper0；RSS末低388MiB，增长/CPU/峰值/OOM仍Partial，失败与独立恢复入口保留。

- [维护回收候选提交与整合范围审阅](reports/2026-10-14-native-trim-maintenance-submission-review.md)：三文件`8f46b3cb`已按授权本地提交并以同SHA进入main；54回归/四hooks通过，十文档独立提交、三树同步与独立恢复入口；未推送部署。（历史检查点；当前交付见上方10-14生产报告。）
- [维护回收候选当前完整门禁](reports/2026-10-14-native-trim-maintenance-fullgate.md)：10-14当前冻结三文件默认八阶段同轮PASS，3955/186/803、API157/113及三浏览器；首轮历史artifact失败保留；代码随后按同版本`8f46b3cb`本地提交整合，未推送部署，资源仍Partial。（历史检查点；当前交付见上方10-14生产报告。）
- [warmup=0维护完成回收候选](reports/2026-10-13-native-trim-maintenance-candidate.md)：10-13冻结三文件专项，54定向、11次真实调用/9对完整响应/两strict通过；随后同版本`8f46b3cb`本地提交整合；驻留下降但采样峰与增长未改善；同一候选10-14新完整门禁通过，尚无新提交CI，发布HOLD。（历史检查点；当前交付见上方10-14生产报告。）
- [原生回收研发CI与发布准备](reports/2026-10-13-native-trim-release-preparation.md)：仅研发分支已推送，CI attempt1成功，私密成品与静态三模式已准备；生产warmup=0使当前回收路径不可达，发布HOLD，main及部署暂停。（历史检查点；当前交付见上方10-14生产报告。）

- [完整预热原生内存回收审阅与本地整合](reports/2026-10-13-native-trim-candidate-review.md)：e01a4455四文件提交已原样进入main，默认Phase5/full8通过；Linux仿真驻留及完整响应证据保留，未推送/部署，原生资源准入/OOM仍开放。（历史检查点；当前交付见上方10-14生产报告。）

- [专辑排名取消修复正式交付与首次验收](reports/2026-10-13-album-rank-cancellation-production-delivery.md)：c0d已发布，原90/90、116 API/三strict通过，旧index39为3125.1→1716.3ms；资源合同/OOM/手机仍开放，安装首轮、wrapper失败及独立补证分列保留。

- [专辑排名取消与Top250候选审阅、整合](reports/2026-10-13-album-rank-cancellation-integration-review.md)：本地审阅与主线映射检查点，源码等同研发full8通过版本，整合重点57项通过；后续c0d正式发布及首次90/90见上方最新交付。

- [开发、整合与工作树收尾规则](reference/development-delivery-workflow.md)：唯一研发负责人、共享文档、检查点、提交映射与证据归档。
- [2026-10-12 分支与历史补丁处置](reports/2026-10-12-development-worktree-closeout.md)：只保留main、当前排名/驻留研发与统一整合工作树，前三轮候选及旧OOM补丁已归档。
- [详情性能与资源验收](reports/2026-10-09-music-detail-chart-performance-acceptance.md)：保存历次首次结果和原失败；c0d已发布、原首次90/90、116 API/三strict通过，资源合同/OOM/手机仍开放。

- [榜单对决个人播放统计已完成规划](archive/06-productization-closeout/2026-10-08-versus-personal-statistics-performance-plan.md)：S0–S5完成，c58775f0已发布，原公开HTTPS首次14/28及资源/完整守恒通过；人类明确私有入口保持现状
- [`plans/2026-10-09-music-detail-chart-performance-plan.md`](plans/2026-10-09-music-detail-chart-performance-plan.md)：`SS-2026-10-09-001` 已完成只读诊断并形成修复规划；独立overview、已发布事实复用、project目标化、请求与错误状态、冷访问和资源验收，S0已冻结；S1–S3已实现，S4/S5验收中

- [榜单对决个人播放性能与正确性验收](reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)：c587正式部署/独立runtime、原首次14/28、420秒资源、96API及三denial通过；历史失败保留，详情首次与OOM独立

- [日期精度与详情空统计生产专项验收、OOM资源跟踪](reports/2026-10-08-release-date-production-delivery.md)

- [日期精度生产副本演练与发布准备](reports/2026-10-08-release-date-production-rehearsal.md)

- [发行日期精度与详情空统计联合集成验收](reports/2026-10-07-release-date-stats-integration.md)

- [非榜单详情统计空值修复与本地验收](reports/2026-10-07-entity-stats-empty-acceptance.md)

- [发行日期证据与精度](reference/release-date-precision.md)
- [发行日期精度已完成实施与集成计划](archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)
- [发行日期精度本地交付与验收](reports/2026-10-07-release-date-precision-acceptance.md)


- [公开展示版完整时间选择修复](reports/2026-10-03-public-analysis-time-ranges.md)

- [专辑目录与艺人证据生产交付](reports/2026-10-03-album-metadata-production-delivery.md)

- [专辑证据与最新封面主线最终集成验收](reports/2026-10-03-album-metadata-final-integration.md)

- [专辑分页与艺人证据联合集成验收](reports/2026-10-03-album-metadata-integration-verification.md)

- [专辑分页与艺人证据已完成集成方案](archive/06-productization-closeout/2026-10-03-album-metadata-integration-plan.md)
- [专辑艺人已完成实施方案](archive/06-productization-closeout/2026-10-02-album-artist-evidence-plan.md)与[专项报告](reports/2026-10-02-album-artist-evidence-verification.md)
- [专辑分页交付报告](reports/2026-10-02-album-track-pagination-acceptance.md)与[第二轮独立复核](reports/2026-10-03-album-track-pagination-independent-review.md)

- [全站封面优化已完成方案](archive/06-productization-closeout/2026-10-03-cover-image-optimization-plan.md)
- [音乐封面传输规则](reference/cover-artwork-delivery.md)
- [全站封面优化实施与验收](reports/2026-10-03-cover-image-optimization-acceptance.md)

- [合作曲排行实施与验收](reports/2026-10-02-collaboration-ranking-acceptance.md)

- [合作曲排行已完成规划（归档）](archive/06-productization-closeout/2026-10-02-collaboration-ranking-plan.md)
- [曲目署名覆盖与标题解析生产验收](reports/2026-10-06-track-credit-resolution-acceptance.md)

当前开发总览与排期从 [开发状态总表](DEVELOPMENT_STATUS.md) 开始：集中查看已完成、尚未完成、可探索和明确暂缓事项。详细方案与历史证据继续由本地图索引。

- [AI Agent V6 本地提交与主分支集成](reports/2026-09-27-ai-agent-v6-local-integration.md)

- [AI Agent V6 已完成规划（归档）](archive/06-productization-closeout/2026-09-22-ai-agent-v6-optimization-plan.md)

- [AI Agent V6 统一运行时与渐进报告最终本地验收](reports/2026-09-22-ai-agent-v6-final-acceptance.md)

- [AI Agent V6 当前运行规则](reference/ai-agent-runtime-v6.md)

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
| 查看开发进度、剩余事项与探索方向 | [`DEVELOPMENT_STATUS.md`](DEVELOPMENT_STATUS.md) |
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

- [`reference/ai-agent-runtime-v6.md`](reference/ai-agent-runtime-v6.md)：AI 问答与年度报告的事件事实源、任务代次、租约、逐章恢复、发布和 SSE v2 当前规则
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

当前状态摘要统一维护在 [`DEVELOPMENT_STATUS.md`](DEVELOPMENT_STATUS.md)；各计划和交付报告保留其原始日期、版本与验证范围。

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

- [`reports/2026-10-06-track-credit-resolution-acceptance.md`](reports/2026-10-06-track-credit-resolution-acceptance.md)：真实生产副本前后对照、原始事实守恒、人工兼容与分阶段验收记录
- [`plans/2026-09-23-multi-source-music-metadata-roadmap.md`](plans/2026-09-23-multi-source-music-metadata-roadmap.md)：MusicBrainz、Apple Music、曲目语言与封面替代等后续方向的分析记录和重新启动门槛；当前延后
- [`plans/2026-08-06-appification-pwa-capacitor-plan.md`](plans/2026-08-06-appification-pwa-capacitor-plan.md)：PWA 与服务器工程已有历史证据；当前外部可用性、异机备份、双平台真机、OAuth 和 Capacitor 决策待闭环
- [`plans/2026-08-24-fullstack-gate-duration-optimization-plan.md`](plans/2026-08-24-fullstack-gate-duration-optimization-plan.md)：P0 编排与 P1 首项重复请求去重已完成，待低干扰三次计时验收

## 已完成资源优化的测量合同

- [`archive/06-productization-closeout/2026-09-22-runtime-resource-optimization-plan.md`](archive/06-productization-closeout/2026-09-22-runtime-resource-optimization-plan.md)：启动、空闲、必要维护与长期浏览器资源优化；含 2026-09-27 最终代码 D/F 页面与资源独立复核

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

- [`reports/2026-09-22-runtime-resource-optimization.md`](reports/2026-09-22-runtime-resource-optimization.md)：日常轻量入口、构建清单、最终代码 D/F、M/D 峰值、真实 hidden 60 分钟 soak 与默认完整 fullstack 证据

- [`reports/2026-09-24-spotify-track-artists-evidence-delivery.md`](reports/2026-09-24-spotify-track-artists-evidence-delivery.md)：Spotify Track `artists[]` 证据持久化、隔离副本全量回填、复跑幂等和差异审计；[实施规划归档](archive/06-productization-closeout/2026-09-23-spotify-track-artists-evidence-plan.md)

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
- [`archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md`](archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)：署名S0–S5已完成；2faadc64正式发布、实际生产署名和独立链接验收通过
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
