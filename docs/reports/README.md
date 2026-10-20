# 交付与验证报告索引

- [开发分支与工作树清理收口](2026-10-20-development-branch-worktree-closeout.md)：2个本地分支、6个远端分支和1个整合工作树已清理；仅保留main，源码恢复引用和两个历史stash保留，运行证据可恢复性分开记录。

当前本轮开发和发布已正式收口，OOM仅保留正常使用观察，不再追加优化或实验。以下旧报告中的待办与门槛保留历史语境，当前状态以首项生产交付报告为准。

- [五文件内存修复生产交付](2026-10-19-minimal-memory-production-delivery.md)：开发与发布CLOSED / RELEASED，f1280ac1已交付，必要CI及发布门禁通过；OOM为OPEN / OBSERVING。记录失败恢复、正常读取、既有22:37快照、工作树处置及观察退出条件。
- [五业务文件精简整合与原生对照](2026-10-19-oom-minimal-five-file-integration.md)：保存6805精简提交、337项与既有对账/full8复用及原生单组资源证据；后续已正式发布，详情见生产交付报告，OOM继续OPEN。
- [三类结果缓存与分配器有界归因](2026-10-19-result-cache-allocator-attribution.md)：已完成的隔离诊断，记录结果可达大小、清理/GC/trim及arena保留；未采用新增LRU预算或分配器调参，后续五文件修复已交付。原归档路径当前未核实可恢复。

- [原生LRU基线与单候选诊断](2026-10-19-lru-budget-native-acceptance.md)：候选786全200/事实与实际限额有效，但RSS增长69.43MiB，峰/末驻留仅低12.28%/18.64%，未达原8MiB/50%，历史有效FAIL保留。完整恢复、学校精确清理及16/29保全完成；不恢复旧资源矩阵或归因排期。

- [目标歌曲署名事实发布候选](2026-10-18-track-presentation-publication-candidate.md)：10-18准备检查点：prep-only47纯测/实际包/独审与原boundary-2两窗通过，四HTTP200/正文、复用和守恒核合，仅2/114；该批学校资源已清理、原16/29保全。后续LRU授权与实测见10-19报告，完整资源仍HOLD。

- [原生热请求有界归因](2026-10-17-native-hot-request-attribution.md)：两轮候选原生对照均有效FAIL，最终0ee热150.305/163.493ms仍超100ms；正文/来源/复用/采样/恢复有效，学校本批精确清理、原16/29保全。两轮上限已到，下一为架构/容量决策，完整资源HOLD。

- [学校共享宿主原生资源准入](2026-10-17-school-native-resource-admission.md)：共享限额和双批时间已获授权；旧无效窗保留，准备/复用/WAL工具135项验证通过，两版第1次ready样本已恢复，首对热305/303ms超100ms、候选有效FAIL，R2停止转R3，LRU未启动；完整资源HOLD。

- [资源对照镜像与可移植验收包](2026-10-17-oom-images-portable-acceptance.md)：R1本地准备完成，实际两镜像、114窗口及独立容器工具链自检通过；33纯测试与恢复包通过，原生资源仍HOLD。

- [累计资源候选冻结与阶段提交](2026-10-17-oom-candidate-freeze-review.md)：R0独立审阅无阻塞，AI测试线程竞态在HEAD自然复现并最小隔离；23文件本地阶段提交c844，资源准入与发布HOLD。

- [有限多实体读取与空闲平台验证](2026-10-17-oom-finite-read-platform.md)：空闲/六实体读取各15分钟均平台，7帧根与结果缓存稳定复用；18正文/六事实/两strict一致。无新增业务补丁，22文件沿用10-16同版本full8，原生/64MiB/长期并发/生产OOM仍OPEN。

- [日期警告候选自然启动与累计门禁](2026-10-16-oom-date-warning-startup-validation.md)：A-B-A ready低20.719–25.133MiB，27响应/六事实/三strict一致；默认full8与三浏览器通过，AI线程SQLite警告保留。启动峰/CPU/读取增长未收口，22文件仅本地、整体资源HOLD。

- [启动arena路径与迟载导入对照](2026-10-16-oom-arena-paths-and-import-timing.md)：确认OpenCC和linecache根；提前导入ready低17.203MiB、峰未改善。仅保留日期警告最小候选，139项/Linux27返回及27时长表一致；后续自然对照与完整门禁见新报告。

- [启动arena持有者与探针自干扰](2026-10-16-oom-startup-arena-owner-attribution.md)：相同业务代码改原生采样，ready低52.590MiB属于观测校正、峰未降；缓存/模块常量/代码缓存帧路径已定位，18响应/六事实/两strict一致。22文件不变，未新增业务修复，整体资源Partial。
- [读取驻留缓存与分配器归因](2026-10-16-oom-read-cache-residency-attribution.md)：四个181.076MiB估算根三轮稳定、定向失效后全部释放；保留缓存trim下降15.273MiB。29项/9完整响应/两段strict通过，未新增业务修复，22文件候选不变，整体OOM仍Partial。
- [合作署名窄表展开与累计候选审阅](2026-10-15-oom-collaboration-credit-expansion-and-cumulative-review.md)：441项、52旧builder/144榜、231组HEAD实体及三窗守恒通过；后端2项存储门槛失败在HEAD同现，整体Partial。累计启动峰1303.668→995.094MiB、末尾893.277→607.395MiB，二十二文件保留本地，下一读取驻留，资源HOLD。
- [启动CPU归因与专辑时长最后消费点](2026-10-15-oom-startup-cpu-duration-attribution.md)：同一B启动CPU差46.060秒；本轮A/C138.440/134.050秒，稳定回归未证且未全排除。释放无用时长/Series引用，417项/231组对账及三窗守恒通过；C启动最高采样991.102MiB、读取增长69.758MiB，二十一文件仅本地，整体Partial/HOLD。
- [专辑发行日期以两列键查询代替整表合并](2026-10-15-oom-album-release-lookup.md)：右键唯一、源表及统计一致；411项/231组旧builder与两窗守恒通过，merge55→2列、owned返回复用。启动最高采样仅低2.445MiB、CPU更高，二十文件仅本地，整体Partial/HOLD。
- [快进纪录在assign前投影必要列](2026-10-15-oom-skip-storm-projection.md)：392项/90组旧函数及两窗守恒通过，assign输入52/56/48→5/5/3列；启动最高采样1014.605→1008.027MiB，仅局部候选，十九文件未提交，整体OOM仍Partial/HOLD。
- [Records计算结束后释放工作表再处理封面](2026-10-15-oom-records-presentation-lifetime.md)：373项及两窗守恒通过；封面入口工作表引用归零，首次964.086→750.301MiB；整体峰值仍在计算阶段。十七文件仅本地，整体OOM仍Partial/HOLD。
- [实体构建复用已具逻辑身份事件表](2026-10-15-oom-entity-identity-ownership.md)：源表不变、主返回表独立；300项、156组旧builder/468主表及468时长表一致。两窗启动最高采样1020.035→1017.312MiB，小幅差异未证稳定OOM收益；十六文件仅本地，整体Partial/HOLD。
- [合作聚合中间表必要列投影](2026-10-15-oom-collaboration-aggregate-projection.md)：258项、52次builder/144旧聚合榜/26直接调用一致；两窗总体最高采样1025→1052MiB、读取658→664MiB，未改善。十五文件仅本地局部候选，整体OOM仍Partial/HOLD。
- [启动最高采样归因与合作事件表生命周期修复](2026-10-15-oom-collaboration-event-lifetime.md)：231项、52次旧函数对账及144榜相同；两有效窗启动最高采样1027→1021MiB、最终低27.1MiB。十四文件仅本地，驻留及整体OOM仍Partial/HOLD。
- [合作纪录select先筛选后复制](2026-10-15-oom-collaboration-select-projection.md)：225项、52次旧函数对账及144份聚合相同；两窗启动采样峰1054→1031MiB、最终低11.8MiB。十三文件仅本地，驻留及整体OOM仍Partial/HOLD。
- [歌曲canonical合并前宽表副本修复](2026-10-15-oom-track-merge-ownership.md)：194项、歌曲/实体各39组对账通过；两窗启动采样峰1078→1062MiB，末尾仅低2.8MiB；十二文件仅本地，驻留及整体OOM仍Partial/HOLD。

- [合作纪录署名键收集最小候选](2026-10-15-oom-collaboration-credit-keys.md)：169项/22完整事实与66榜对账通过；消除六次宽表复制。两窗启动采样峰1081→1047MiB，因果收益未量化、驻留未改善；十一文件仅本地，整体资源Partial/HOLD。

- [Records启动宽表生命周期修复](2026-10-15-oom-records-working-set.md)：150项/39旧函数对账通过；启动采样峰下降56.828MiB，三窗9响应/六事实/strict一致；九文件仅本地，驻留及整体OOM仍Partial。

- [外层时长候选撤回与Python分配器归因](2026-10-15-oom-duration-rejected-allocator-attribution.md)：外层134项/35响应对账通过但峰值收益未证，恢复原八文件；malloc只归因，驻留下降伴随启动峰/增长/仿真CPU代价。三窗9响应/六事实/strict一致，下一目标Records启动宽表，整体OOM仍Partial。
- [艺人专辑中间表投影与生命周期](2026-10-15-oom-artist-album-intermediates.md)：120通过，两窗9响应/六事实/strict一致；首次峰增量低30.102MiB、读取峰低20.832MiB。末尾高9.301MiB且arena差异启动后已存在，驻留收益未证明；八文件未提交推送部署，整体OOM仍Partial。
- [艺人统计首次载入与署名展开投影](2026-10-15-oom-artist-first-projection.md)：130通过，两窗9完整响应/六事实/strict一致；首次峰增量低25.289MiB、本轮读取峰低27.465MiB、末尾低8.230MiB。七文件未提交推送部署，启动及整体OOM仍Partial。
- [冷个人统计曲目/Top250输入投影](2026-10-14-oom-cold-stats-track-projection.md)：151通过，三窗33完整响应/六事实/strict一致，冷专辑峰低36–39MiB；总峰/末尾未降，下一目标艺人stats首次；六文件未提交推送部署，整体资源Partial。
- [镜像封装、启动重排与有界读取验证](2026-10-14-oom-image-startup-bounded-verification.md)：169通过；封存基底两镜像/33完整响应/六事实/strict一致，启动峰低90MiB，读取略高；默认Python基镜像构建未通过，未提交推送部署，整体资源Partial。
- [OOM启动峰值与读取增长隔离候选](2026-10-14-oom-peak-growth-isolated-candidate.md)：仅Dockerfile固定mmap阈值128KiB；同源采样峰/末尾/增长改善，9完整响应、六统计/Records事实与strict通过；旧代码/arena试验不采用，未提交推送部署，原生资源/生产OOM仍Partial。

- [维护完成原生回收生产交付与首次验收](2026-10-14-native-trim-maintenance-production-delivery.md)：固定b126已正式发布；研发/main CI及Release通过，原首次90/90、116/116 API、三strict与wrapper0；RSS末低388MiB，增长/CPU/峰值/OOM仍Partial，失败与独立恢复入口保留。

- [维护回收候选提交与整合范围审阅](2026-10-14-native-trim-maintenance-submission-review.md)：三文件`8f46b3cb`已按授权本地提交并以同SHA进入main；54回归/四hooks通过，十文档独立提交、三树同步与独立恢复入口；未推送部署。（历史检查点；当前交付见上方10-14生产报告。）
- [维护回收候选当前完整门禁](2026-10-14-native-trim-maintenance-fullgate.md)：10-14当前冻结三文件默认八阶段同轮PASS，3955/186/803、API157/113及三浏览器；首轮历史artifact失败保留；代码随后按同版本`8f46b3cb`本地提交整合，未推送部署，资源仍Partial。（历史检查点；当前交付见上方10-14生产报告。）
- [warmup=0维护完成回收候选](2026-10-13-native-trim-maintenance-candidate.md)：10-13冻结三文件专项，54定向、11次真实调用/9对完整响应/两strict通过；随后同版本`8f46b3cb`本地提交整合；驻留下降但采样峰与增长未改善；同一候选10-14新完整门禁通过，尚无新提交CI，发布HOLD。（历史检查点；当前交付见上方10-14生产报告。）
- [原生回收研发CI与发布准备](2026-10-13-native-trim-release-preparation.md)：6c74b9b4仅研发分支已推送，CI attempt1成功；源fence匹配私密输入和静态三模式，生产warmup=0触发阻塞、隔离导出OOM与原失败保留；不推main/不部署。（历史检查点；当前交付见上方10-14生产报告。）

- [完整预热原生内存回收审阅与本地整合](2026-10-13-native-trim-candidate-review.md)：四文件e01a4455已原样进入main，未推送/部署；默认Phase5/full8、Linux仿真9对完整响应及驻留收益、提交映射与独立恢复入口；原生资源/OOM未关闭。（历史检查点；当前交付见上方10-14生产报告。）

- [2026-10-13 专辑排名取消生产交付](2026-10-13-album-rank-cancellation-production-delivery.md)：c0d发布、原首次90/90、116 API/三strict；资源仍Partial，原失败与证据缺口保留。

- [专辑排名取消与Top250候选审阅、整合](2026-10-13-album-rank-cancellation-integration-review.md)：固定补丁审阅、原自然38→39对照、完整本地full8证据、整合工作区57项复核及独立归档；描述本地整合时的边界，后续正式交付见上方新报告。

- [开发分支、历史补丁与共享文档整理](2026-10-12-development-worktree-closeout.md)：候选取舍、主线提交映射、残余资源补丁与恢复入口。

- [榜单对决个人播放性能与正确性验收](2026-10-08-versus-personal-statistics-performance-acceptance.md)：真实副本 API、资源与完整发布对账通过；浏览器、完整全栈与生产专项正在收口。

- [日期精度与详情空统计生产专项验收、OOM资源跟踪](2026-10-08-release-date-production-delivery.md)

- [日期精度生产副本演练与发布准备](2026-10-08-release-date-production-rehearsal.md)

- [发行日期精度与详情空统计联合集成验收](2026-10-07-release-date-stats-integration.md)

- [非榜单详情统计空值修复与本地验收](2026-10-07-entity-stats-empty-acceptance.md)

- [发行日期精度本地交付与验收](2026-10-07-release-date-precision-acceptance.md)

- [曲目署名覆盖与标题解析生产验收](2026-10-06-track-credit-resolution-acceptance.md)

- [公开展示版完整时间选择修复](2026-10-03-public-analysis-time-ranges.md)

- [专辑目录与艺人证据生产交付](2026-10-03-album-metadata-production-delivery.md)

- [专辑证据与最新封面主线最终集成验收](2026-10-03-album-metadata-final-integration.md)

- [专辑分页与艺人证据联合集成验收](2026-10-03-album-metadata-integration-verification.md)

- [专辑艺人稳定 ID 与有序证据专项](2026-10-02-album-artist-evidence-verification.md)
- [专辑完整分页交付](2026-10-02-album-track-pagination-acceptance.md)
- [专辑分页第二轮独立复核](2026-10-03-album-track-pagination-independent-review.md)

- [全站封面优化实施与验收](2026-10-03-cover-image-optimization-acceptance.md)：`814ea7cb` 已发布，完整本地全栈与实际 HTTPS 四视口验收完成。

- [合作曲排行实施与验收](2026-10-02-collaboration-ranking-acceptance.md)

报告保留各自日期和代码版本；后续实现、推送及发布状态统一见 [开发状态总表](../DEVELOPMENT_STATUS.md)。

- [AI Agent V6 本地提交与主分支集成](2026-09-27-ai-agent-v6-local-integration.md)

- [AI Agent V6 统一运行时与渐进报告最终本地验收](2026-09-22-ai-agent-v6-final-acceptance.md)

- [AI Agent V6 S0 基线与固定评测合同](2026-09-22-ai-agent-v6-s0-baseline.md)

- [启动、运行资源与长期内存优化实施报告（含 2026-09-27 独立复核收口）](2026-09-22-runtime-resource-optimization.md)

- [Spotify Track `artists[]` 证据交付与隔离验收](2026-09-24-spotify-track-artists-evidence-delivery.md)

- [数据导入处理与治理 S6 最终验收](2026-09-21-import-governance-final-acceptance.md)

- [数据导入处理与治理 S1–S5 实施报告](2026-09-21-import-remediation-s1-s5.md)

- [阶段 S0：导入事故修复与测量基线](2026-09-21-import-remediation-s0-baseline.md)

- [阶段 8：快照可用性与 Billboard 交互连续性收口](2026-09-21-stage8-snapshot-and-billboard-ux-closeout.md)

- [全应用性能优化成果与最终验收报告](2026-09-21-full-application-performance-optimization-outcome.md)

- [阶段 7E：最终本地全栈 Pass 与测试存储收口](2026-09-21-stage7e-final-fullstack-acceptance.md)

- [阶段 7D：Import Preflight 优化与历史验收](2026-09-20-stage7d-import-preflight.md)

- [阶段 7C：Git 检查点与剩余性能收口（Partial）](2026-09-20-stage7c-checkpoints-performance-acceptance.md)

- [阶段 7B：验收阻塞修复与本地收口（Partial）](2026-09-20-stage7b-performance-closeout.md)

- [阶段 7：全路由性能验收与本地收口（Partial）](2026-09-20-stage7-local-performance-acceptance.md)

- [阶段 6C：治理 Coverage / Health 共享事实与持久结果](2026-09-20-governance-coverage-health.md)

- [阶段 6B：音乐档案共享事件与持久结果](2026-09-20-account-archive-shared-events.md)

- [2026-09-20 阶段 5C：Search 真实 delta 可达性与 identity revision 精度](2026-09-20-search-real-delta-reachability.md)

- [2026-09-20 阶段 5B：Search shared-full 统计合同与真实 lineage（Partial）](2026-09-20-search-shared-full-contract.md)

- [2026-09-20 阶段 5A：Search 四变体配置重建共享收口](2026-09-20-search-invocation-fallback.md)

- [2026-09-20 阶段 4B：Billboard 配置失配重建收口](2026-09-20-billboard-config-mismatch-closeout.md)

- [2026-09-20 阶段 4A：Billboard 单次重建共享事实](2026-09-20-billboard-generation-facts.md)

- [2026-09-20 阶段 3C：Records 单次构建共享事实收口](2026-09-20-records-invocation-facts.md)
- [2026-09-20 阶段 3B：播放纪录读取与 builder 专项优化（性能目标未达标）](2026-09-20-records-read-build-optimization.md)

- [2026-09-19 阶段 3A：默认播放统计与播放纪录结果快照](2026-09-19-analysis-result-snapshots.md)


这里保存一次性实施、验收、审计、真实性能和生产发布证据。报告不是当前规则的唯一来源；当前统计和数据契约以 [`../reference/`](../reference/) 为准，当前部署操作以 [`../../deploy/production/README.md`](../../deploy/production/README.md) 为准。

## 阶段 6A Community

- [Community 冷计算、持久读模型与分页](2026-09-20-community-read-model.md)

## 最近交付

- [2026-09-19：阶段 2B Community 请求去重与详情非核心按需读取](2026-09-19-deferred-community-details.md)

### 播放统计与详情

- [`2026-09-19-public-snapshot-boundary.md`](2026-09-19-public-snapshot-boundary.md)

- [`2026-09-13-billboard-persistent-snapshot-optimization.md`](2026-09-13-billboard-persistent-snapshot-optimization.md)
- [`2026-08-29-l2-track-album-presentation.md`](2026-08-29-l2-track-album-presentation.md)
- [`2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](2026-08-29-billboard-records-consistency-and-ranking-hardening.md)
- [`2026-08-31-billboard-count-duration-semantics-research.md`](2026-08-31-billboard-count-duration-semantics-research.md)
- [`2026-08-30-playback-records-correctness-and-ranking.md`](2026-08-30-playback-records-correctness-and-ranking.md)
- [`2026-08-25-music-detail-year-end-history.md`](2026-08-25-music-detail-year-end-history.md)
- [`2026-08-24-home-detail-loading-performance-repair.md`](2026-08-24-home-detail-loading-performance-repair.md)
- [`2026-08-23-incremental-import-final-acceptance.md`](2026-08-23-incremental-import-final-acceptance.md)
- [`2026-08-23-incremental-import-phase-e.md`](2026-08-23-incremental-import-phase-e.md)
- [`2026-08-23-incremental-import-phase-d2.md`](2026-08-23-incremental-import-phase-d2.md)
- [`2026-08-23-incremental-import-phase-d1.md`](2026-08-23-incremental-import-phase-d1.md)
- [`2026-08-23-incremental-import-phase-c.md`](2026-08-23-incremental-import-phase-c.md)
- [`2026-08-23-incremental-import-phase-b.md`](2026-08-23-incremental-import-phase-b.md)
- [`2026-08-23-incremental-import-phase-a.md`](2026-08-23-incremental-import-phase-a.md)
- [`2026-08-23-cover-cache-and-post-import-performance.md`](2026-08-23-cover-cache-and-post-import-performance.md)
- [`2026-08-23-import-and-complete-billboard-week-fix.md`](2026-08-23-import-and-complete-billboard-week-fix.md)
- [`2026-08-19-music-detail-performance-delivery.md`](2026-08-19-music-detail-performance-delivery.md)
- [`2026-08-17-music-detail-statistics-fix-delivery.md`](2026-08-17-music-detail-statistics-fix-delivery.md)
- [`2026-08-15-playback-logical-timeline-v2-delivery.md`](2026-08-15-playback-logical-timeline-v2-delivery.md)
- [`2026-08-13-billboard-artist-aggregate-fix.md`](2026-08-13-billboard-artist-aggregate-fix.md)

### 音乐查找

- [`2026-08-28-music-search-zero-downtime-and-credit-delta.md`](2026-08-28-music-search-zero-downtime-and-credit-delta.md)
- [`2026-08-16-music-search-optimization-delivery.md`](2026-08-16-music-search-optimization-delivery.md)
- [`2026-08-16-music-search-m0-baseline.md`](2026-08-16-music-search-m0-baseline.md)

### 音乐档案与年度总结

- [`2026-08-30-yearly-review-common-period-comparison.md`](2026-08-30-yearly-review-common-period-comparison.md)
- [`2026-08-24-yearly-review-semantic-correction.md`](2026-08-24-yearly-review-semantic-correction.md)
- [`2026-08-13-account-archive-phase-0-delivery.md`](2026-08-13-account-archive-phase-0-delivery.md)
- [`2026-08-13-account-archive-journey-cohorts-delivery.md`](2026-08-13-account-archive-journey-cohorts-delivery.md)
- [`2026-08-13-account-archive-desktop-delivery.md`](2026-08-13-account-archive-desktop-delivery.md)
- [`2026-08-13-account-archive-phone-delivery.md`](2026-08-13-account-archive-phone-delivery.md)
- [`2026-08-13-account-archive-phase-4-delivery.md`](2026-08-13-account-archive-phase-4-delivery.md)
- [`2026-08-12-yearly-review-v2-delivery.md`](2026-08-12-yearly-review-v2-delivery.md)

### 移动端、PWA 与部署

- [`2026-08-13-dual-deployment-profile-delivery.md`](2026-08-13-dual-deployment-profile-delivery.md)
- [`2026-08-13-private-cloud-pwa-delivery.md`](2026-08-13-private-cloud-pwa-delivery.md)
- [`2026-08-06-mobile-web-and-pwa-delivery.md`](2026-08-06-mobile-web-and-pwa-delivery.md)

### 元数据、AI 与质量门禁

- [`2026-09-13-development-closeout-and-release.md`](2026-09-13-development-closeout-and-release.md)
- [`2026-09-13-l1-import-duration-and-manual-merge-closeout.md`](2026-09-13-l1-import-duration-and-manual-merge-closeout.md)
- [`2026-08-31-l2-l3-identity-and-album-attribution-remediation.md`](2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)
- [`2026-08-31-ai-agent-performance-v5-acceptance.md`](2026-08-31-ai-agent-performance-v5-acceptance.md)
- [`2026-08-31-ai-agent-quality-v4-acceptance.md`](2026-08-31-ai-agent-quality-v4-acceptance.md)
- [`2026-08-31-ai-agent-quality-v3-acceptance.md`](2026-08-31-ai-agent-quality-v3-acceptance.md)
- [`2026-08-31-l3-native-album-attribution-execution-and-acceptance.md`](2026-08-31-l3-native-album-attribution-execution-and-acceptance.md)
- [`2026-08-31-l3-governance-execution-and-acceptance.md`](2026-08-31-l3-governance-execution-and-acceptance.md)
- [`2026-08-30-l2-governance-execution-and-acceptance.md`](2026-08-30-l2-governance-execution-and-acceptance.md)
- [`2026-08-27-settings-rebuild-and-data-governance-remediation.md`](2026-08-27-settings-rebuild-and-data-governance-remediation.md)
- [`2026-08-27-spotify-track-l1-identity-migration.md`](2026-08-27-spotify-track-l1-identity-migration.md)
- [`2026-08-24-fullstack-gate-duration-optimization.md`](2026-08-24-fullstack-gate-duration-optimization.md)
- [`2026-08-24-fullstack-gate-repair.md`](2026-08-24-fullstack-gate-repair.md)
- [`2026-07-16-genre-source-quality-audit.md`](2026-07-16-genre-source-quality-audit.md)
- [`2026-07-15-genre-language-pre-review-execution.md`](2026-07-15-genre-language-pre-review-execution.md)
- [`2026-07-05-artist-genre-seed-audit.md`](2026-07-05-artist-genre-seed-audit.md)
- [`2026-07-03-ai-question-matrix-test-report.md`](2026-07-03-ai-question-matrix-test-report.md)
- [`2026-06-22-phase5-delivery-report.md`](2026-06-22-phase5-delivery-report.md)
- [`2026-06-20-fix-branch-follow-up.md`](2026-06-20-fix-branch-follow-up.md)
- [`2026-06-19-fullstack-verification.md`](2026-06-19-fullstack-verification.md)
- [`2026-06-19-fullstack-verification-performance.md`](2026-06-19-fullstack-verification-performance.md)

## 报告阅读规则

- 先看报告开头的状态、范围和证据日期。
- 真实数据库数量、性能数字和测试数量都是快照，不自动代表当前状态。
- 发现规则冲突时，优先检查当前代码、测试和 `docs/reference/`。
- 报告中引用的旧路径只代表当时的目录，不应复制到新文档。
- “已实现”“验证 Pass”“已 commit”“已 push”“已部署”是五个不同事实；报告应分别记录，不能合并成含义不清的“发布状态”。
- 后续 commit、门禁或部署状态使用明确的后续补充保留时间线，不反向改写报告生成时的真实过程。
- 局部或功能范围 Pass 必须注明范围；只有当前提交的默认完整门禁全部必需阶段通过，才能写当前本地全栈 Pass。
