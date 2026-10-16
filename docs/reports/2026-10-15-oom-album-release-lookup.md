# 专辑发行日期以两列键查询代替整表合并

核验日期：2026-10-15。SS-2026-10-08-001，关联 SS-2026-10-09-001。

**处置：保留本地最小候选；源表与统计结果一致，整体资源仍 Partial，整合/发布 HOLD。**

## 先核对键与所有权

`_load_reliable_album_release_dates`先按原始`(album_name, artist_name)`元组归并证据，再对每个键最多输出一条可信精确日：相同键的重复元数据合并，冲突或无精确日的证据不发布；不同艺人同名专辑保留各自身份。左侧是播放事件，允许重复；右侧必须唯一。隔离七库来源含94,760 plays，实际加载4条可靠日期，重复键0、空键0；内存SQLite测试另覆盖重复本地专辑、同名不同艺人、NULL键、冲突日和仅年份，结果键仍唯一。

`_build_records_album_frame`的成功路径返回owned merge结果，回退路径返回copy；当前函数拥有该专辑投影，原事件表与时长源只读。原发行日期全宽merge和drop又产生新表，既复制无关字段，也重置索引、清空attrs。非空日期回填分支的attrs清除会影响`records_duration_frame`如何读取时长，不能在性能修复中改掉这一既有行为。

## 最小修复与正确性

仅修改研发树`backend/services/analysis_records_service.py`：用专辑名、艺人名两列做窄表left merge，并以many_to_one验证右键；随后在已独立持有的album_frame回填发行日。保留原RangeIndex、列轴名称和清空attrs的合同，仍优先使用项目精确发行日；查询临时表在歌曲投影前释放。完整字段、dtype、行序、缺失值与时长消费方式保持。原事件/时长/lookup表不变，主返回表独立；此前另外18个候选文件逐字节不变，当前20文件仅本地未提交。没有改日期证据规则、分配器、缓存预算或回收策略。

411项唯一相关测试通过，含19项新增，覆盖L1/L2/L3、匹配/无匹配/空日期表、NULL键、重复具名索引/列轴、源表与lookup不变、结果独立，以及窄表输入和查询临时表提前失活。冻结旧函数运行同批测试，3个全宽merge检查按预期失败，16个统计/元数据/加载器对照通过。

冻结旧builder完整对账231组：3层级×11种正常/异常/空表/范围场景×7种lookup和元数据形态，693张主表与693张时长消费表schema、dtype、索引、行序一致，attrs键/时长附件存在性保持，源事件、时长及lookup每组不变。包括nullable键、年度裸时长附件和已有nullable逻辑ID，项目精确日优先、None/NaN语义不变。Ruff、format、项目mypy hook和diff check通过；原始检查日志保留。

## 同源 Linux 对照

基线19文件镜像`sha256:7d5b3c414b4c68e90874c8fd1bc2894423941cc4c2933e1108a5ff4a3d19d7e7`，候选`sha256:1e6afe8450906b26c0e8bee23808c7fa44e296239f50335a380a1456caf91dfb`；每侧518份Python源码与冻结上下文匹配，镜像间只差本轮service文件，Python/glibc/依赖及启动前mmap阈值相同，无源码覆盖。封存runtime离线构建，在ARM Linux引擎运行amd64仿真，不替代原生或默认Python基镜像验证。

从同一94,760原始plays来源各制作全新七库副本；两个有效窗口使用相同probe，分别正常启动，再执行相同9次GET：Midnights L3 fixed light/rank六次、Taylor Swift L2 dynamic rank三次，三轮串行。network none、只读root、无端口、4GiB容器与3GiB RSS守卫、启动600秒/总900秒边界保持，无新增GC/trim/clear或预算调整。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1009.484 | 1007.039 | -2.445 |
| startup ready | 543.738 | 556.395 | +12.656 |
| 读取最高采样 | 678.820 | 675.746 | -3.074 |
| 第9次后idle3s | 622.781 | 620.723 | -2.059 |
| 最终idle | 622.781 | 620.730 | -2.051 |
| ready至末尾增长 | 79.043 | 64.336 | -14.707 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

## 直接键、列宽与所有权证据

双方各3次发行日期回填的右键均无重复，输入和返回行数不变，完整输出列序相同；候选返回专辑表与helper的owned投影是同一对象，使用weakref确认，未持有完整表强引用。

| 调用 | 行数 | merge输入列数 基线→候选 | merge输出列数 基线→候选 | 返回表复用owned投影 基线/候选 |
| --- | ---: | ---: | ---: | --- |
| 1 | 67881 | 55→2 | 56→3 | False/True |
| 2 | 125 | 55→2 | 56→3 | False/True |
| 3 | 7543 | 55→2 | 56→3 | False/True |

双方输出仍为RangeIndex、attrs为空。首个67,881行merge边界RSS增量24.613→1.559MiB、耗时74.418→33.805ms；125行边界耗时3.189→5.211ms，其余时序原样保留，不能据此宣称整条启动链加速。直接merge边界不包含之前的两列投影或之后的fill，其RSS/耗时不能作为完整函数峰值；键/所有权探针不读caller f_locals。此前快进assign仍为5/5/3列，三次封面入口工作表引用均为0。固定阶段与最高采样观测沿用浅层元数据，所有对象存储估算不与RSS相加。

基线启动最高采样栈`build_collaboration_facts → compute_discovery_records → compute_playback_records → _get_analysis_records_uncached`。捕获延迟0.012ms、耗时13.012ms，实际最大采样间隔0.934秒，短峰可能遗漏。启动等待132.106秒，ready进程CPU133.340秒；固定Records阶段观测额外0.347秒，3次merge与11个维护任务时序另有原始记录。

候选启动最高采样栈`_canonical_records_track_frame → _build_records_track_frame → _build_entity_frames → _get_analysis_records_uncached`。捕获延迟0.018ms、耗时1.408ms，实际最大采样间隔0.671秒，短峰可能遗漏。启动等待151.309秒，ready进程CPU150.110秒；固定Records阶段观测额外0.492秒，3次merge与11个维护任务时序另有原始记录。

## 守恒与处置

双方9份完整响应逐字节相同，三范围stats/Records六份事实相同；跨构建仅排除meta.generated_at，各自strict时钟保持。37原始表、保护事实、队列、发布与六sidecar在读取前后不变，8103 done/38历史failed和失败明细相同，无pending/running或新增失败。正式七库SHA不变，两窗实际exit0，无OOM或采样器错误，每侧只有原有11次维护回收；合法帧预算均4条、181.076MiB、roots/LRU owner相同，分配器与idle观测保留。

局部修复保留，整体资源仍Partial、整合/发布HOLD。启动等待132.106→151.309秒、ready进程CPU133.340→150.110秒，候选更高；三个Records任务进程CPU16.640/12.880/14.420→18.580/16.030/17.710秒。前置未改动Billboard任务也由17.540→18.180秒，其他任务同样有波动。单对照尚未分离运行波动与回归，不能宣称加速或通过CPU准入。窄表merge和复用owned返回已由直接证据确认，单个配对窗口的全局RSS差异不能替代稳定OOM或读取驻留验证。读取后增长、原生/默认镜像、overview64MiB、长期/并发和生产OOM继续OPEN；本轮无新full8、CI、浏览器或生产请求。本轮启动最高点基线位于合作事实构建，候选位于歌曲时长canonical merge；不能将不同栈的2.445MiB差异全部判为本次修复收益。读取最高点两侧仍为艺人Top albums的album project聚合。读取增长虽79.043→64.336MiB，但ready已高12.656MiB、最终仅低2.051MiB，驻留未证稳定改善。ready及末尾pymalloc arena基线均380.750MiB、候选均393.750MiB，末尾空闲pool170.539/182.402MiB，这些不与RSS相加。下一先核对歌曲时长merge峰点仍存活的duration/投影owner及最后消费点，并定位启动CPU增量，再选择后续修复。

原始证据`output/oom-album-release-lookup-20261015/`，独立恢复入口`~/.codex/archives/spotifystats-delivery/oom-album-release-lookup-20261015/`，保留冻结19文件、当前20文件、独立补丁、键与所有权审计、所有测试/旧函数对账、两套runtime、完整响应/六事实/strict、直接merge列宽/右键/weakref身份及阶段最高采样。归档校验CRC、源码/协调文档、双方9响应、六事实及所有权证明后，仅清理本轮两个已退出容器，镜像/原始输出/正式来源保留；实际结果见独立收据。未暂存、提交、推送或部署，main仅更新协调文档。
