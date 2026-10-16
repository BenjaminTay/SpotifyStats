# 实体构建复用已具逻辑身份事件表的最小修复

核验日期：2026-10-15。SS-2026-10-08-001，关联SS-2026-10-09-001。

**处置：保留本地最小候选；源表不变和主返回表独立通过，整体资源仍Partial，整合/发布HOLD。**

## 实现与正确性

上一轮启动最高采样在歌曲时长merge时，`_get_analysis_records_uncached`与`_build_entity_frames`同时持有两份67,881×48事件表，且都已带_logical_event_id。后者的无条件`assign_logical_event_id`仍复制完整表，随后所有实体投影又各自产生独立结果。

本轮业务仅在研发树`backend/services/analysis_records_service.py`的`_build_entity_frames`入口增加列存在条件：已有_logical_event_id时只读复用输入；缺失时继续调用原assign函数。没有改变ID生成/保留语义，已有重复或nullable ID也按旧合同保留，没有改变通用assign函数的独立返回合同。歌曲、专辑及艺人结果仍由原有owned投影或copy回退产生，完整字段保持。此前另14个候选文件逐字节不变，新增`backend/tests/unit/test_records_entity_identity_ownership.py`，当前16文件仅本地未提交。

300个唯一相关测试通过，含42项新增，覆盖L1/L2/L3、专辑membership正常/空/错误/部分填充回退、艺人失败、事件/时长空表、日期范围、重复索引、已有年度ID及legacy artist ID、年度裸时长attrs。修改返回表单元格及attrs后，源事件、源时长和其他主返回表保持原样；可修改时长消费表继续经records_duration_frame默认copy获取，维持既有attrs引用合同。缺身份时仍分配一次，已有身份时不调用assign且两个投影入口接收原只读输入。

冻结本轮前outer builder对账156组：3层级×13场景×4种身份状态（缺失/已有/重复/nullable），468张完整主返回表与468张时长消费表schema、dtype、索引、行序相同，每组源表及attrs守恒。另有年度裸listening_duration_slices附件检查，确保源metadata仍引用原附件且内容不变。旧实现资源回归检查在3个已有身份案例按预期失败，3个缺身份对照仍通过。Ruff、format、项目mypy hook与diff check通过。

## 同源两个 Linux 窗口

基线十五文件镜像 `sha256:f583c9f400516e00a6364671eb2e4b0e67bbf521767f2fd10a61ce54ff5dc00b`，候选 `sha256:ff46a482979723970c2bf40dd6ce89b9dda9041be60a06b5ac5898d7b65f2e22`。各518份Python源码与冻结上下文匹配，镜像间仅本轮service文件不同；Python/glibc/依赖和启动前MALLOC_MMAP_THRESHOLD_=131072一致，无源码覆盖或runtime proxy。两套全新关闭七库副本来自同一94,760原始plays来源，probe字节一致；正常启动维护后各执行相同9次GET：Midnights L3 fixed light/rank六次、Taylor Swift L2 dynamic rank三次，顺序三轮。本轮仅两个有效窗口。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1020.035 | 1017.312 | -2.723 |
| startup ready | 539.316 | 538.871 | -0.445 |
| 读取最高采样 | 661.715 | 658.613 | -3.102 |
| 第9次读取后 idle3s | 605.500 | 603.039 | -2.461 |
| 最终 idle | 605.500 | 603.039 | -2.461 |
| ready 至末尾增长 | 66.184 | 64.168 | -2.016 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

最高采样启动低2.723MiB、读取低3.102MiB、最终低2.461MiB，均属小幅配对观察，不能当作稳定的OOM或驻留收益。同一基线镜像上一轮启动最高采样1052.148MiB、本轮1020.035MiB，波动大于本轮差异；本轮不跨窗拼接收益，也不追加追逐有利结果的重跑。

源复用的直接证据来自入口资源检查和代码：已有身份时assign零调用，两类实体投影入口接收原对象；缺失时assign一次。**本轮Linux全局最高采样没有同时观察到调用者与实体构建入口，因此该点的运行时复用证明标为NOT_OBSERVED。** 两侧最高采样均已离开_build_entity_frames：基线在Records封面展示的`_album_associations → resolve_track_presentations`，候选在`_late_night_trajectory → compute_time_pattern_records`。不能把这两张栈说成在同一构建点实测消除了约20MiB副本，更不能把栈位置变化直接当作因果改善。

两侧最高RSS与保存栈采样UTC/RSS对应。基线/候选捕获开始延迟0.016/0.015ms，耗时8.716/8.908ms，结束RSS1005.680/1001.832MiB；非原子捕获中业务仍可能继续。目标采样50ms，实际最大间隔1.424/0.840秒，短峰可能遗漏。启动/读取捕获开销0.190/0.049秒与0.191/0.044秒，原元数据和输入归属证明均保存。

启动等待132.840→138.149秒，ready进程CPU134.14→138.89秒；候选更高，尚未执行改动的首个Billboard任务CPU亦由17.62→18.14秒。完整11项时序保留，不宣称加速或把全部差异判为代码因果回归；进程CPU不等于worker线程CPU。

## 守恒与剩余边界

双方9份完整响应逐字节一致，stats/Records三范围六份业务事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同；均8103 done/38历史failed，失败明细相同，无pending/running、新失败、采样器错误或OOM，实际exit0。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算调整。

末尾均4个帧预算条目、181.076MiB，cache roots/LRU owner一致；读取后的缓存增长与启动副本分开跟踪。基线/候选ready pymalloc arena376.750/376.000MiB，末尾376.750/375.750MiB；末尾空闲pool167.000/163.359MiB。它们与帧估算互相覆盖，不与RSS相加。ready观测自身RSS增加5.195/5.363MiB，末尾观测无明显跳升。

约1GiB总峰仍在Records计算/展示持有多套宽表期间，读取最高采样两侧均在艺人Top albums的album project聚合。后续应先按实体构建、Records计算、展示解析三个阶段核对owner与最后消费点，再选择必要列或生命周期修复，不仅根据某个最高栈继续微调。当前ARM Linux引擎的amd64仿真、封存runtime离线构建和每侧单窗不能替代原生资源验证；默认Python基镜像、overview64MiB、长期/并发和生产OOM仍OPEN。本轮没有新full8、CI、浏览器或生产请求。

原始输出 `output/oom-entity-identity-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-entity-identity-20261015/`。冻结原十五文件、当前十六文件、独立identity补丁、初版与最终所有单元/旧函数对账、两套runtime、完整响应/事实/strict/分配器/最高采样及NOT_OBSERVED记录均保留。归档校验CRC、源码/协调文档、双方9响应和六事实后，仅清理本轮两个已退出容器，保留镜像、输出和正式来源；实际结果见独立收据。本轮未暂存、提交、推送或部署，main仅更新协调文档。
