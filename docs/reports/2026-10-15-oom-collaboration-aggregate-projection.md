# 合作聚合中间表必要列投影的最小修复

核验日期：2026-10-15。SS-2026-10-08-001，关联SS-2026-10-09-001。

**处置：保留本地局部列投影候选；总体峰值未改善，资源Partial，整合/发布HOLD。**

## 实现与正确性

上一轮最高采样落在`_feat_lover_artist → aggregate_collaboration → _duration_dedupe`，事件frame/events各15,178×52、display 1,084×51、时长22,913×49。消费者仅需要少量身份、名称、署名列表和时长去重事实，其他来源列被反复携带进copy、sort和drop_duplicates。

本轮仅修改研发树`backend/domains/playback/records_collaboration.py`：聚合事件在复制前选择所需列，附加entity_id后最多8列；时长在复制前选择实体身份和完整去重事实，附加entity_id后最多11列。原9个时长去重字段提为共用tuple，供投影和`_duration_dedupe`同时消费，保留不同interval/slice、逻辑事件、来源play、署名版本及ms_played。列顺序依原来源排列，避免artist名称/专辑名称兼作参数时重复选择同名列。

没有缩窄CollaborationFacts完整返回表，没有重写groupby、排序、署名列表展开或事件计数算法。未增加GC/trim/clear、预算调整、allocator或全局缓存修改。此前另外13个候选文件逐字节不变，新增`backend/tests/unit/test_collaboration_aggregate_projection.py`，当前15文件候选仅本地未提交。

258个唯一相关测试通过，含27项新增，46项专项包含其中。新测试覆盖歌曲/艺人/专辑、名称兼身份、署名列表有无、独立时长与事件回退、重复逻辑事件、低于次数阈值的时长、重复索引、空/缺字段边界及源表/attrs不变，并逐一验证9个时长键的差异能保留独立贡献。复制检查在旧实现按预期失败，候选复制的中间表均不包含未消费的来源列。Ruff、format、项目mypy hook与diff check通过。

冻结本轮前完整模块进行对账：52次builder调用中48份完整7表及total_events一致、4次既有缺失键异常一致；144份榜单使用冻结旧aggregate与新aggregate分别计算后完全一致。另有26组直接aggregate调用比较输出schema、dtype、索引和行序，通过。没有用同一个新聚合器计算两侧结果来代替旧实现对照。

## 同源两个 Linux 窗口

基线十四文件镜像 `sha256:156aa537b03921fbae3c0cbacbf9c6f727ee8382cb32265825934552f34aebdd`，候选 `sha256:f583c9f400516e00a6364671eb2e4b0e67bbf521767f2fd10a61ce54ff5dc00b`。各518个Python源码与冻结上下文匹配，镜像间仅本轮domain文件不同，Python/glibc/依赖和进程启动前MALLOC_MMAP_THRESHOLD_=131072一致；无源码覆盖或runtime proxy。相同probe字节、两个全新关闭七库副本（94,760原始plays），正常启动维护后各执行同一9次GET：Midnights L3 fixed light/rank六次，Taylor Swift L2 dynamic rank三次，顺序三轮。本轮只跑两个有效窗，无挑选结果的重跑。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1025.184 | 1052.148 | +26.965 |
| startup ready | 545.375 | 538.621 | -6.754 |
| 读取最高采样 | 657.531 | 663.789 | +6.258 |
| 第9次读取后 idle3s | 613.055 | 608.312 | -4.742 |
| 最终 idle | 613.055 | 608.312 | -4.742 |
| ready 至末尾增长 | 67.680 | 69.691 | +2.012 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

总体启动最高采样高26.965MiB，读取最高采样高6.258MiB，读取增长高2.012MiB；最终虽低4.742MiB，但起点已低6.754MiB，不能把末尾差异描述为驻留改善。局部聚合不再复制未消费列由专项检查支持；本轮没有证明全局峰值、驻留或OOM改善。保留小范围、完整语义对账通过的本地候选，资源准入仍HOLD，不进入业务整合或发布。

基线最高采样同点栈在`aggregate_collaboration`时长copy，仍带22,913×48的原时长及15,178×52的frame/events、1,084×51的display；候选最高采样同点栈在更早的`_canonical_records_track_frame → merge/concat`，为96,301×45时长表合并分组键。双方都处于已完成4项维护后的首个Records任务，候选此时尚未进入该任务的合作聚合，不能把其更高采样全归因于本轮投影。

候选峰还同时持有歌曲事件67,881×52、艺人事件76,541×48/时长109,383×44、专辑事件67,881×56/时长96,301×51及lifetime里程碑等宽表。另有两份都已带_logical_event_id的事件帧67,881×48，分别位于`_get_analysis_records_uncached`与`_build_entity_frames`；后者仍无条件调用`assign_logical_event_id`复制。它是下一处已具对象证据的最小目标：只读复用已具身份的输入，缺身份时保留原分配路径，同时验证所有返回表仍独立、源表不变及Yearly Review回退语义。本轮未修改它，不继续追逐合作消费者的小幅调整。

两侧最高RSS与保存栈的采样UTC/RSS完全对应，未触及元数据上限。基线/候选抓栈开始延迟0.029/0.023ms，捕获45.575/21.038ms，结束RSS分别1004.777/1028.172MiB。非原子采样中业务仍可能继续，故同点栈表示采样附近状态，不等于完整分配归因。目标间隔50ms，实际最大1.222/0.659秒；候选可能比基线捕获更多短峰。启动/读取捕获总开销为0.185/0.055秒与0.190/0.048秒，保留于same-sample-peak-proof.json。

启动等待134.331→152.954秒，ready进程CPU135.90→153.29秒；候选更慢，首个尚未触及本轮改动的Billboard任务CPU也由17.91→18.64秒。完整11项时序保留，不宣称加速，也不将全部差异判为代码因果回归；进程CPU不等于worker线程CPU。

## 守恒与剩余边界

双方9份完整响应逐字节一致，stats/Records三范围六事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同，均8103 done/38历史failed，失败明细相同，无pending/running、新失败、采样器错误或OOM，实际exit0。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算下调。

末尾帧预算同为4条/181.076MiB，cache roots/LRU owner相同。基线/候选ready pymalloc arena382.750/376.000MiB，与ready RSS差异量级相同；末尾382.750/375.750MiB，空闲pool171.922/164.855MiB。它们与帧估算相互覆盖，不与RSS相加。ready观测自身RSS增加4.969/5.148MiB，末尾无明显观测跳升。读取最高采样两侧均在艺人Top albums的album project聚合；它与启动宽表重叠分开跟踪。

仍为ARM Linux引擎上的amd64仿真、每侧单窗，离线沿用封存runtime；原生资源、默认Python基镜像、overview64MiB、长期/并发及生产OOM仍OPEN。没有新full8、CI、浏览器或生产请求。本轮正确性通过不代表资源准入通过。

原始输出 `output/oom-collaboration-aggregate-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-aggregate-20261015/`。原十四文件、十五文件候选、独立aggregate补丁、旧函数/新回归与全部测试、两套runtime及完整响应/事实/strict/分配器/最高采样归属均保存。归档校验CRC、源码/协调文档、双方9响应和六事实后，仅清理本轮两个已退出容器；镜像、输出和正式来源保留，实际结果见独立收据。本轮未暂存、提交、推送或部署，main仅更新协调文档。
