# 快进纪录在 assign 前投影必要列

核验日期：2026-10-15。SS-2026-10-08-001，关联 SS-2026-10-09-001。

**处置：保留本地最小候选；源表和统计结果一致，整体资源仍 Partial，整合/发布 HOLD。**

## 修复与正确性

上一轮候选启动最高采样位于`_skip_storm`处理67,881×56专辑事件表期间。原函数用`frame.assign(_forward=...)`构造快进标记，先复制包含大量无关字段的实体宽表，再做groupby。实际只消费分组身份/名称、play_id计数、ms_played求和与reason_end快进判定。

本轮仅改研发树`backend/domains/playback/records_behavior.py`的`_skip_storm`：在原assign前用`unique_cols`投影分组键、play_id及ms_played，快进布尔Series仍从只读原reason_end生成。重复的艺人分组列去重，原计数与求和、10次门槛、缺失值规则、完整候选排序与输出字段均保持。源事件、时长附件及attrs不改动，结果仍独立；未扩大到其他行为纪录或修改缓存、分配器、回收策略。此前17个候选文件逐字节不变，新增本轮业务文件和测试后，共19文件仅本地未提交。

392项唯一相关测试通过，包含19项新增：三实体的同率稳定排序、门槛、重复索引、乱序、浮点时长、nullable计数、源表/时长附件不变，以及直接检查assign只收到必要列。冻结旧函数运行同批测试，3个整宽复制检查按预期失败，16个统计/空态对照通过。

独立旧函数对账90组：歌曲/专辑/艺人×15个场景×原列序/反向列序，覆盖nullable ID/时长/原因、categorical及未观测类别、空表、缺reason_end、门槛不足、空分组、重复索引、已有_forward、年度裸时长attrs。完整结果的schema、dtype、索引与行序相同，源事件、源时长和attrs每组守恒。Ruff、format、项目mypy hook与diff check通过。原始检查日志均保留。

## 同源 Linux 对照

基线17文件镜像`sha256:6975a249200376e2db2f4841f8b1347bc937aa269c012498e9daff27b5a51d79`，候选`sha256:7d5b3c414b4c68e90874c8fd1bc2894423941cc4c2933e1108a5ff4a3d19d7e7`；两侧各518份Python源码与冻结上下文匹配，镜像间只有本轮records_behavior文件不同，Python/glibc/依赖与启动前mmap阈值相同，无源码覆盖。封存runtime离线构建，在ARM Linux引擎运行amd64仿真；单窗不能替代原生与默认Python基镜像验证。

同一94,760原始plays来源各制作全新七库副本，两个有效窗口使用字节相同probe。正常启动后，各执行同样9次GET：Midnights L3 fixed light/rank六次、Taylor Swift L2 dynamic rank三次，三轮串行；network none、只读root、无端口、4GiB容器/3GiB进程RSS守卫、600秒启动与900秒总界限保持。无额外GC/trim/clear或预算变更。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1014.605 | 1008.027 | -6.578 |
| startup ready | 546.629 | 547.941 | +1.312 |
| 读取最高采样 | 669.996 | 668.586 | -1.410 |
| 第9次后idle3s | 616.598 | 613.770 | -2.828 |
| 最终idle | 616.598 | 613.770 | -2.828 |
| ready至末尾增长 | 69.969 | 65.828 | -4.141 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

## 直接列宽与阶段证据

双方各记录9次_skip_storm的直接assign；对应输入行数相同，候选每次仅包含必要列。首个完整范围：

| 实体 | 行数 | assign输入列数 基线→候选 | assign输出列数 基线→候选 |
| --- | ---: | ---: | ---: |
| track | 67881 | 52→5 | 53→6 |
| album | 67881 | 56→5 | 57→6 |
| artist | 76541 | 48→3 | 49→4 |

输入投影发生在assign之前，所以此边界的RSS与耗时不包含投影分配；这些数据用于证明复制列集，不能冒充整个函数峰值。估算块字节不包含完整object payload或attrs，也不与RSS相加。双方三次封面入口工作表局部引用均为0，维持上一轮生命周期修复；阶段表与weakref证据保留。

基线启动最高采样栈`_skip_storm → compute_behavior_records → compute_playback_records → _get_analysis_records_uncached`；读取同点栈见原始证据。最高采样捕获延迟0.021ms，耗时1.060ms；实际最大采样间隔1.361秒，短峰可能遗漏。启动等待133.872秒，ready进程CPU134.130秒；固定Records阶段观察额外0.326秒，9次assign边界观察及11个维护任务时序均保留。

候选启动最高采样栈`_build_entity_frames → _get_analysis_records_uncached`；读取同点栈见原始证据。最高采样捕获延迟0.020ms，耗时1.339ms；实际最大采样间隔0.952秒，短峰可能遗漏。启动等待132.184秒，ready进程CPU133.460秒；固定Records阶段观察额外0.367秒，9次assign边界观察及11个维护任务时序均保留。

## 守恒与处置

双方9份完整响应逐字节相同，三范围stats/Records六份事实相同；跨构建仅排除meta.generated_at，各自strict时钟保持。37原始表、保护事实、队列、发布及六sidecar读取前后不变；8103 done/38历史failed和失败明细相同，无pending/running或新失败。正式七库SHA不变，两窗实际exit0、无OOM或采样器错误。每侧只有原有11次维护回收。帧预算均4条、181.076MiB，cache roots/LRU owner保持；ready及末尾pymalloc arena基线均383.750MiB、候选均385.250MiB，末尾空闲pool173.574/174.812MiB。分配器与自然idle检查原样保留，估算不与RSS相加。

采用必要列投影作为局部修复；整体资源仍Partial，整合/发布HOLD。窄表复制已由直接入口与结果对账证明，单个配对窗口的全局RSS差异仍不能认定为稳定OOM或读取驻留收益。读取后增长、原生/默认镜像、overview64MiB、长期/并发和生产OOM继续OPEN；本轮无新full8、CI、浏览器或生产请求。候选最高点在67,881×55专辑表发行日期回填的merge入口（_build_entity_frames第273行），另有96,301×51专辑时长表及艺人/事件表同时存活；此点早于首个_skip_storm，不能把全局6.578MiB差异全部归因于本轮代码。下一先核对该回填合并是否需要整表复制、其键唯一性和源/返回表所有权，再决定最小候选。读取两侧最高点仍在艺人Top albums的album project聚合，读取后增长69.969→65.828MiB，驻留未收口。

原始证据`output/oom-skip-storm-projection-20261015/`，独立恢复入口`~/.codex/archives/spotifystats-delivery/oom-skip-storm-projection-20261015/`，保留冻结源码、当前19文件、独立补丁、全部检查日志、90组旧函数对账、两套runtime、完整响应/事实/strict、9次assign各一套、阶段及最高采样证据。归档校验CRC、源码/协调文档、双方9响应、六事实与直接列宽证明后，仅清理本轮两个已退出容器，保留镜像、输出和正式来源，实际结果见独立收据。未暂存、提交、推送或部署，main仅更新协调文档。
