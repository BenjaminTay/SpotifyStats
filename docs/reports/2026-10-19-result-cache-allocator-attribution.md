# 三类结果缓存与分配器的有界归因

> 状态：本归因阶段已结束，以下容量快照、候选选择和将来时态保留当时语境。后续五文件修复已随f1280ac1交付，本轮开发与发布CLOSED / RELEASED，SS-2026-10-08-001仅保留OPEN / OBSERVING；当前决定见[生产交付](2026-10-19-minimal-memory-production-delivery.md)，不再追加优化或实验。

## 结论与修复决定

2026-10-19本轮归因已完成。三类结果缓存满载时约41.52MiB，结束时约41.82MiB；没有发现其可达对象持续膨胀到足以解释几十MiB增长的证据。清空全部结果后RSS只下降7MiB，GC不再降低RSS；保留帧缓存的诊断trim另下降17.85MiB。之后Python仍保留412.50MiB arena，其中约247.27MiB为空闲块/未用池。**当前主要残余空闲容量位于Python arena，glibc也有可回收页；尚未逐个确认其它存活对象的arena持有路径。**这不是已定位某个业务泄漏，也不能把旧原生69.43MiB逐字节归因于本窗。

本轮决定不新增三类LRU预算、JSON存储、每请求GC/trim或分配器调参补丁。大幅清空结果仅回收7MiB arena，不支持靠改结果载体解决主要剩余驻留。业务源码继续保留`bfecef52`，新增工具只用于隔离诊断。历史失败原样保留；后续改按[精简收口计划](../plans/2026-10-19-performance-scope-and-memory-closeout.md)，不补旧114/90矩阵或以8MiB/50%组合指标决定交付。两个加载体验任务已经结项，SS-2026-10-08-001内存稳定性仍OPEN。

## 实际范围与有效性

本机ARM引擎复用原候选amd64镜像`cc2280d6f24a`，实际CPython3.9.25/glibc2.41、原allocator ENV。恢复已回传七库及WAL到新私有目录，Backend限1核/2GiB/无swap，只读根文件系统、独立网络/loopback，正文解析在独立256MiB客户端中完成。只运行真实HTTP读取，不运行lifespan或后台启动维护；本窗不代表原生绝对性能、正常启动或最终容量验证。

首窗歌曲/专辑196次请求原始正文一致，在第一个艺人请求遇到503后停止，保留为`INVALID_REQUIRED_ARTIST_PUBLICATION_READINESS`；运行340.057秒，未计资源FAIL。源码核对艺人GET依赖独立`artist_rank_context`；只在独立准备进程为恢复副本的新文件身份调用现有私有ensure/read，16.445秒完成三个period的READY读回，主源库只读。不是修改GET绕过成品边界或改写旧失败。

第二窗从总2700秒预算扣除首窗时间，宿主最多2359秒；实际2003.716秒，两窗合计2343.772秒，即39分04秒。自然读取在软上限后封存：**521次请求、覆盖259目标，第一轮完整，第二轮艺人部分未完成，第三轮未执行**；另3次释放后重新读取，合计524次全200、原始正文及规范正文全部与原生记录一致。不能称三轮平台期验证通过，也不为此重跑。

主源main/WAL及七库读取前后全部字节摘要不变，readonly连接限制覆盖自然读取和释放诊断。原输入归档、首窗失败工具和记录均保留。学校机未访问；没有应用新业务补丁、推送或部署。

## 深层对象与释放结果

只沿三个已知CPython LRU的直接key/value入口遍历，按对象ID去重，单次最多100万个节点/256MiB，不支持的结构明确NOT_MEASURED；不扫描全堆。大遍历在短命fork子进程中退出，固定native缓冲保存1Hz样本，不累计Python样本字典。11项检查在实际候选Python3.9环境通过，覆盖共享对象、循环引用、边界拒绝、LRU命中/淘汰次序不变和观察引用释放；相关ruff通过。首次导入检查点父进程遍历前后RSS增量为2.113MiB，其余测量点均0，不能说探针完全没有开销。

| 首轮完整缓存 | 条数 | 单类结果可达大小 MiB |
| --- | ---: | ---: |
| 歌曲 | 128 | 15.220 |
| 专辑 | 64 | 11.818 |
| 艺人 | 64 | 14.422 |

三类合并按ID去重并计入key/容器/节点后约41.516MiB，结果图393483节点；结束时约41.822MiB、396550节点。结束工作集因第二轮未完成而略有不同，不能把这0.306MiB当同一工作集的持续增长。图内均为普通容器及标量，没有DataFrame被结果间接带住。可达大小包含其它root共享的子对象，不等于独占可释放字节，各单类大小不能直接相加当总占用。

| 阶段 | RSS MiB | 已知LRU MiB | Python arena MiB | Python空闲块/池 MiB | glibc空闲块 MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 自然读取结束 | 631.367 | 41.822 | 419.50 | 217.095 | 22.504 |
| 只清歌曲结果 | 631.367 | 26.560 | 419.50 | 229.611 | 26.398 |
| 再清专辑结果 | 626.867 | 14.758 | 415.00 | 235.263 | 28.893 |
| 再清艺人结果 | 624.367 | 0.001 | 412.50 | 245.235 | 31.933 |
| 单独GC | 624.367 | 0.001 | 412.50 | 247.285 | 32.016 |
| 单独malloc_trim | 606.520 | 0.001 | 412.50 | 247.268 | 31.891 |

三个结果缓存清空后，已知值图节点为0，表中的0.001MiB仅为空容器/wrapper；Python allocated blocks减少约34.50MiB，但arena只归还7MiB。GC另减少约2.02MiB allocated blocks而arena/RSS不变。trim时Python arena不变而RSS另降17.848MiB，支持glibc空闲页回收这一独立来源。所有干预保持同一23个帧root/附件及129.187MiB权重不变，随后三类真实请求重新构建的正文仍一致。

原始_debugmallocstats分项和、arena计数/大小及glibc arena=uordblks+fordblks逐点核合，原始malloc_info/smaps齐全。Python allocated blocks也包含解释器free list，glibc空闲块也可能已不驻留，arena及其空闲容量不是独立RSS；这些层不能直接相加。仍有其它root保活arena，不把全部247MiB都归给帧或某个元数据缓存。本轮到此停止持有者扩查。

## 生产只读容量核对与最小候选

按新规划仅作一次被动容量核对，并补读一次业务子进程以区分docker-init；没有HTTP请求、数据库读取、缓存清理、重启或配置变更。2026-10-19 04:05 UTC，生产仍为`b126020862fabb968db1974d38145b99d119ee86`，Backend healthy，10-14启动以来RestartCount=0、OOMKilled=false、当前cgroup oom/oom_kill均0。近14天可读kernel记录中保留10-08真实uvicorn全局OOM及10-13独立工具memcg OOM；本次读到的最新匹配为10-13，不能改写为历史从未OOM。

| 实际容量字段 | 当前只读快照 |
| --- | --- |
| 宿主 | 4核、约3.636GiB内存，9个运行容器 |
| MemAvailable / 磁盘可用 | 约2.039GiB / 11.08GiB |
| Backend硬限额 | memory.max=max、cpu.max=max；学校2GiB/1核不是生产配置 |
| Backend cgroup当前内存 / swap | 约874.7MiB / 1017.0MiB |
| Backend cgroup历史memory.peak | 约2166.6MiB，自当前容器创建以来，并非仅启动峰 |
| 实际uvicorn VmRSS / VmSwap / VmHWM | 约578.5 / 1007.3 / 1588.3MiB；docker-init的704KiB不能冒充业务RSS |

现有空闲RAM尚未给新增2GiB副本核定安全余量，因此不在生产开测试副本。约1GiB swap可能是之前压力下留下的闲置页；单次快照既不能当持续增长证明，也不能凭低RSS判风险消除。当前实际容量需连同swap和维护峰处理，不直接套学校限额。

交付准备选择已有`c844b98f260b85b92ae298e9d135fdab6cb05de2`中五个业务文件的宽表/生命周期修复及16个对应unit回归：records_behavior、records_collaboration、analysis_records_service、analysis_stats_service、entity_stats_service。这五文件在实测bfecef52中逐字节相同，复用[R0审阅与原有效正确性证据](2026-10-17-oom-candidate-freeze-review.md)。本轮已保存21文件具名patch，对当前main的apply-check为0，尚未应用。

暂存schema91发布架构、通用验收工具链、Docker的MALLOC_MMAP_THRESHOLD_新配置及无关AI契约测试改动。选择五文件用于缩小交付范围，不声称该最小组合已经在最终采用的allocator配置下完成容量对照。接下来只在最终采用范围固定、选定实际预算后补确有必要的一组受影响资源/正确性验证；不因旧100ms/64MiB/50%/8MiB未达而重开加载任务或自动追加矩阵。

## 证据与清理

私密工作目录为`/Users/benjaminlei/.codex/worktrees/album-rank-cost/202605-SpotifyStats/output/oom-result-cache-allocator-20261019/`。`attempt1/`保留失败首窗；`run/`保存有效归因、逐点allocator原文和524条请求记录；`bounded-attribution-summary.json`核合分项；`candidate-selection/`保存21文件patch和选择回执；两份production-readonly结果保留容量核对。业务源、原始数据库和统计结果保持。

本次容器已精确删除、owned residue zero，既有镜像保留，学校无本轮资源。必要原始证据已独立保存于私密`~/.codex/archives/spotifystats-delivery/oom-result-cache-allocator-20261019/attribution-evidence.zip`，不含数据库，CRC及实际恢复后逐文件核合。随后只删除本轮`run/runtime`；清理回执和最终报告另存同档案目录。数据库载荷复用此前私密原始归档，不再复制一套长期大包。报告与共享规划由各自负责人维护，其他会话的未提交文档不打包提交。

2026-10-19提交准备核对：上述归档目录及原研发工作树路径当前不存在；本节保存的是当时归档记录，本轮未核实归档现位置及可恢复性。
