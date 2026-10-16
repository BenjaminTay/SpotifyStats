# 启动 arena 碎片：对象持有者与探针自干扰归因

> 后续补证：见[arena路径与迟载导入对照](2026-10-16-oom-arena-paths-and-import-timing.md)。补充外部容器、OpenCC及linecache根，原288未全部逐地址还原；提前导入未改善启动峰，保留日期警告最小候选，独立启动净收益待验。

核验日期：2026-10-16。SS-2026-10-08-001，关联 SS-2026-10-09-001。研发仍为 `codex/album-rank-cost` / `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06`。22文件业务候选字节不变；最小修复仅在本地诊断采样器，不提交、推送、部署或改生产配置。总体资源保持 OPEN / Partial、发布 HOLD。

## 结果与处置

启动遗留 arena 确有“大量空闲pool被少量分散对象占住”的形态，但旧采样器自身也是持有者，不能把全部残留归为业务缓存或实际服务泄漏。已将逐样本Python字典列表改为固定容量原生缓冲区，并保留旧探针与对照。小业务缓存、延迟导入模块的代码/常量及Python3.9缓存帧都有直接持有证据；尚未找到删除后能稳定释放主要残留的无用业务根，因此本轮不新增业务修复。

## 有界测量与解析校验

运行两次完整启动：A使用原逐样本字典采样器；B使用原生缓冲区采样器，应用镜像和全部22文件相同。另有一次探针在应用lifespan开始前因自定义类型的module属性不是字符串而失败，未执行启动任务；原目录、脚本、exit1与错误保留。计入该失败共三个owned进程容器，本轮不追加启动窗口。

两次有效窗从同一正式七库、94,760 plays制作全新副本，使用已封存镜像 `sha256:37903f982dd3f9913002cc3e63e3c60b0f557ce4a4f79400309a8174f57fac57`。ARM Linux引擎上的amd64仿真，4GiB容器/3GiB父进程RSS守卫、2CPU、network none、只读root、无端口，启动600秒/全程900秒；实际窗不增加权限或调整allocator。两窗均保留原11次维护trim，诊断操作只在自然启动ready封存之后执行。

解析严格限定实际Python3.9.25/x86_64 release runtime：核对本地libpython ELF导出函数指令签名，只读定位arena表；父进程通过持GIL的fwrite导出arena字节，立即恢复线程切换间隔。fork子进程读取快照、解析pool空闲链和对象头，不替换allocator、不修改业务对象、不读取f_locals、不把疑似地址强转为Python对象。子进程CPU45秒/55秒alarm，显式根每组最多20万节点、单模块常量最多2万；实际解析约2秒。

初步的跨进程调试方式在仿真环境不可用，即使单独能力预检也失败，已弃用；实际窗口仅用只读快照。预检与首窗版本偏移/类型descriptor错误均保留。A ready解析1252个arena与`_debugmallocstats`完全相同；分配块字节仅相差89,472字节、空闲pool相差8192字节，来自两检查点间少量诊断元数据。父快照循环分配块净变化A为11个、B为17个；逐pool活跃块数、空闲链、size class及每arena的used+free=64均校验。raw/freelist块不一定是活Python对象，未识别类型不作业务归因。

## 碎片形态与小缓存排除

导入后基线为320个arena、80MiB容量，约78.2MiB分配块，尚无高空闲arena。A自然启动ready为1252个arena、313MiB容量；817个arena各有至少48/64个pool空闲，共204.25MiB容量，仅约2.700MiB分配块；615个arena分配块不足4KiB。arena总容量、pool空闲字节和RSS是不同计量层，不作相加。

四个小缓存的显式根图包括键、值、列表和DataFrame现有对象单元格；不物化数字标量，不追函数globals。下面arena数包含共享，不能累加；图不含所有容器底层C缓冲区。

| A ready持有者 | 已遍历节点 | 涉及arena | 涉及高空闲arena |
| --- | ---: | ---: | ---: |
| db.track_artist_names_map | 21921 | 245 | 106 |
| db.track_all_artists_map | 2240 | 115 | 41 |
| billboard.album_meta | 9988 | 258 | 129 |
| billboard.canonical_map | 15173 | 224 | 111 |

自然启动封存后，按上述名称逐项失效：前两项arena数不变，album_meta减少1个、canonical_map再减少2个，随后GC再减少1个，总计只释放4个arena/1MiB。分配块约85.857→81.662MiB，空闲pool反而更多，说明这些合法小缓存是分散持有者之一，但清它们不能释放大部分arena。本轮不将该定向清理加入业务代码。

## 探针自身的持有与最小修复

A采样器每100毫秒把utc_ns、rss_bytes、cpu_seconds字典追加到Python列表，并保留至窗口结束。原始allocator快照中1289个整数精确匹配同窗采样的唯一时间戳，分布于233个arena，其中150个是高空闲arena；采样RSS数值亦命中288个arena，合并命中316个高空闲arena。RSS数值可能与其他元数据重复，仅唯一时间戳用作直接持有证据；触及arena不代表该arena仅由探针占用。

B使用预先分配的12000×3个uint64槽位，总288000字节，保存时间戳、RSS及纳秒化CPU；逐样本Python参数字典只短暂存在，完整JSON在观测窗口结束后生成。容量超限明确失败，不静默截断。原1781条记录回放：时间戳和RSS完全一致，CPU浮点最大差2.85e-14秒，顺序/容量边界通过。它是诊断脚本修复，未加入22文件业务候选。

| 自然启动ready指标 | A 字典列表采样 | B 原生缓冲采样 |
| --- | ---: | ---: |
| RSS MiB | 473.914 | 421.324 |
| arena数 / 容量MiB | 1252 / 313.000 | 1040 / 260.000 |
| 高空闲arena数 | 817 | 606 |
| 分配块MiB | 85.857 | 85.433 |
| 空闲pool MiB | 207.570 | 159.109 |
| 启动采样峰MiB | 991.125 | 995.082 |
| ready CPU秒 | 126.230 | 127.320 |

B ready RSS低52.590MiB、arena容量低53MiB，支持旧采样器放大碎片；只有每种一次完整窗，执行顺序与线程调度也会影响布局，不能把全部差值当成稳定因果量，更不能算作业务修复收益。启动采样峰仍约995MiB，没有下降；这是观测校正，不是OOM收口。

B封存自然启动后保留全部业务缓存，仅释放探针EVENTS/POINTS/TRIMS列表；arena1040→1033，随后诊断GC→1028（合计3MiB）。这时缓存仍在，持有者图显示其余探针根已空。与A清业务缓存的尾段操作不同，二者读取后RSS不能作为自然性能A/B对照。

## 剩余对象的具体持有路径

B释放其余探针根并GC后仍有1028个arena/257MiB，其中604个高空闲arena包含约2.496MiB分配块。主要类型为字符串14513、列表10093、raw/freelist块4773、整数3284、元组802及零refcount帧598；这里是这些高空闲arena内的分配块数量，不是全进程对象总数。

- 署名与元数据根：四个业务缓存的显式节点仍触及159个高空闲arena，包括署名字符串/列表、canonical映射与专辑类型/日期事实。它们有明确复用/修订失效/LRU边界，上一轮已证明定向失效后播放表及其时长附件可正常释放。
- 模块和代码常量：54个启动期新增模块的受限根图触及222个高空闲arena，典型为account_archive.discovery/cohorts/other_media、community.feed_records/feed_ranking/feed_weekly及playback.song_work_keys。逐对象反向边另在114个只有一个活跃块的目标中，找到29个经tuple/list直接连到代码常量的路径；records_album_facts.py占8个，feed_data.py占4个，feed_records.py占3个。这些常量由模块函数的code/tuple长期合法持有。
- Python3.9帧缓存：只读核对code.co_zombieframe指针和静态PyFrame_Type，B确认4196个处于pymalloc中的零refcount缓存帧；其中43个高空闲arena含此类帧，仅5个arena/1.25MiB完全由它们占住。不能把“触及43个”当作可独立释放10.75MiB，也不能把缓存帧当成仍在执行或保留原业务locals的调用栈。
- 容器底层块与未解释项：小列表内部指针缓冲区分布于480个arena，属于原先只数Python对象根容易漏掉的分配；当前未全部连接到业务根。604个高空闲arena中，受限缓存/新增模块图合并触及316个，另288个尚未由这两类根图解释；它们与上述帧/内部缓冲区有重叠，不能标为全部已归因或泄漏。

本轮没有发现可以安全删除、又能释放主要残留的业务对象。模块代码是必要常驻，不能靠卸载模块、私自改co_zombieframe、减缓存预算或请求后GC来凑RSS下降。若继续业务候选，应先在更轻采样器下验证“把确定的迟载模块放到重型数据创建前导入”能否减少分散，或补足未解释根；当前不提前实现导入/预热策略。

实现机制依据实际版本的[CPython3.9.25 obmalloc](https://github.com/python/cpython/blob/v3.9.25/Objects/obmalloc.c)与[frameobject](https://github.com/python/cpython/blob/v3.9.25/Objects/frameobject.c)：arena需所有pool可回收才释放，解释器也可保留一个全空备用arena；frame_dealloc先清局部对象引用，再把帧存入code缓存。因此一个全空arena和零refcount缓存帧均不能直接作为泄漏证据。

## 正确性与旧证据解释修正

两窗共18份完整GET响应与上一轮最终22文件窗口逐字节相同；六份stats/Records事实跨构建完全一致，仅比较时省略meta.generated_at，读取strict本身未省略任何字段。两窗自然启动后到诊断/九次读取结束的37来源、保护数据、队列/发布与六sidecar严格守恒通过；done8103/历史failed38集合相同，无pending/running、新失败或OOM；正式七库SHA、22文件候选、三个Git HEAD、空暂存区和main五份无关改动保持。

原arena/采样探针预检与原生采样回放通过；未改业务代码，不重复上一轮完整后端或full8。既有完整后端3634通过/2跳过、2项存储门槛失败在HEAD同现的Partial结论保持；本轮不能作为原生Linux、默认基镜像、单请求64MiB或长期平台验收。本次只读arena导出会暂停采样约数秒，A/B最大采样间隔4.007/3.523秒包含导出/子进程诊断期，不能用它做短峰或延迟门禁。

此前各窗约213MiB空闲pool、约64.8MiB读取增长及累计RSS差值仍保留原值，但它们包含观测对象对allocator布局的影响，不能直接当作无探针服务的真实驻留或稳定业务因果收益；即使双方使用相同探针也不能保证此偏差抵消。统计正确性和源表守恒证据不因此失效。旧报告增加后续补证链接，不覆盖原失败和原数值。

证据：研发树 `output/oom-startup-arena-owners-20261016`；独立归档 `~/.codex/archives/spotifystats-delivery/oom-startup-arena-owners-20261016/evidence.zip`。快照含本地业务数据，仅本地保存、不入Git；归档包含全部分配器数字/原始arena快照、显式持有路径、原失败、18响应、六事实、两strict、22候选及协调文档。归档核验后仅移除本轮三个已停止owned容器，正式七库、镜像和原始output保留。
