# 启动最高采样归因与合作纪录事件表生命周期修复

核验日期：2026-10-15。SS-2026-10-08-001，关联SS-2026-10-09-001。

## 归因和最小修复

上轮32MiB阶梯式保存栈会漏掉阶梯内的更高采样值。本轮保持原十三文件镜像，先在新七库副本把探针改为每次刷新最高采样时替换保存栈及有界浅层元数据，再据证据修复。探针仅保存数值、形状、别名和缓冲区根标识，不保留业务表对象，不做全堆扫描或强制回收。

首窗在Pandas构造中遇到尚无`_mgr`的DataFrame，采样线程退出，窗口标无效并手动停止（实际137、OOMKilled=false）；日志及runtime原样保留，不作为峰值或业务回归证据。修正探针跳过未完成构造的DataFrame/Series，并在同一Linux镜像验证对象去重、附属时长和共享NumPy根后，仅修复性重跑一次。有效归因窗最高启动采样1027.375MiB，已保存同次采样UTC/RSS的栈，未触及元数据上限。

该采样栈落在合作艺人名称`groupby(...).agg(list)`，19张去重表中`events`独立为67,881×49，仅由`build_collaboration_facts.events`持有。它的扁平block计20.716MiB，在已观察表根中独占的NumPy存储约19.162MiB；对象字符串等payload可能共享，均不是RSS估算。歌曲、专辑投影已经结束，后续仅返回`len(events)`，完整身份投影因此在后续署名展开和聚合期间多存活了一段。

最高采样到抓栈开始延迟0.021ms，元数据抓取15.591ms，结束RSS为1012.266MiB。读RSS和抓栈并非原子操作，不能把名单聚合认定为全部峰的唯一分配源；当前证据支持的是该大表在高位附近的无用存活。启动79次/读取44次捕获总开销0.221/0.062秒，实际采样最大间隔1.118秒；真实短峰仍可能漏过。

本轮业务仅在研发树`backend/domains/playback/records_collaboration.py`缓存事件总数，并在两次`_event_projection`最后一次消费完成后`del events`，返回使用保存的整数。输入表、合作事件结果、返回列、排序、dtype、时长事实均不裁剪。新增`backend/tests/unit/test_collaboration_event_lifetime.py`的6项检查覆盖部分/全命中/无命中及有无独立时长，确认署名展开前该独立表的weakref已失效。旧实现6项均按预期失败，修复通过，无测试性GC。

231个唯一相关测试通过，56项专项包含其中；冻结旧函数52次调用中48份完整事实及144份聚合相同，4次既有缺失键异常类型/消息相同。Ruff、format、项目mypy hook、diff check通过。此前另外12文件逐字节不变，当前14文件候选仅本地，未提交。

## 同源、同探针配对

有效基线 `sha256:24d4394212b68e08dfc435ff571ee93a6e5e9c8321291b267b2ccacf04486924`，修复镜像 `sha256:156aa537b03921fbae3c0cbacbf9c6f727ee8382cb32265825934552f34aebdd`；各518份Python源码与冻结上下文相同，镜像间仅本轮domain文件不同。Python/glibc/依赖、MALLOC_MMAP_THRESHOLD_=131072一致。两侧使用相同probe字节，各自全新七库关闭来源（94,760原始plays），正常启动后执行Midnights L3 fixed light/rank六次及Taylor Swift L2 dynamic rank三次，顺序三轮。本轮共三个容器调用，只有两个有效窗口组成比较，首个无效窗口独立保存。

| MiB | 基线 | 修复 | 修复减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1027.375 | 1020.602 | -6.773 |
| startup ready | 542.285 | 536.531 | -5.754 |
| 读取最高采样 | 678.859 | 657.203 | -21.656 |
| 第9次读取后 idle3s | 627.316 | 600.215 | -27.102 |
| 最终 idle | 627.320 | 600.219 | -27.102 |
| ready 至末尾增长 | 85.035 | 63.688 | -21.348 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

**保留本地最小候选；整体资源Partial，整合/发布HOLD。** 此配对启动最高采样低6.773MiB、读取最高采样低21.656MiB、最终低27.102MiB。生命周期缩短由weakref与局部别名证据支持；RSS差异仅是本配对观测。改动在启动Records中执行，不能把读取后的全部差异归因于它。同一基线镜像上一轮读取增长66.082MiB，本次85.035MiB；当前修复63.688MiB，尚未证明稳定驻留收益，不跨轮累计改善。

两侧最高RSS和保存栈的采样UTC/RSS完全对应，均未触及元数据上限。修复后1020.602MiB最高采样的栈位于`_feat_lover_artist → aggregate_collaboration → _duration_dedupe → drop_duplicates/factorize`，其中时长表22,913×49，内部frame/events各15,178×52，display 1,084×51；没有原完整events身份投影的引用。调用者仍持有事件、独立时长、歌曲/专辑/艺人和lifetime里程碑等宽表。同点捕获开始延迟0.018ms、耗时9.133ms，结束RSS1005.348MiB；两侧都不能把抓栈期间的状态当作原子快照。修复侧启动80次/读取41次捕获总开销0.160/0.062秒，实际最大采样间隔1.201秒。

启动等待155.407→132.184秒、ready进程CPU158.67→134.41秒，首个尚未触及改动的Billboard任务CPU17.65→17.52秒。完整11项时序均保留；单次仿真观察不作稳定加速结论，进程CPU不等于worker线程CPU。

## 读取后驻留与边界

双方末尾均4个帧预算条目、181.076MiB：3个`db.plays`及1个`db.plays_for_artists`，包含各自附属时长；另有小型canonical map及约3MiB未注册排名响应LRU。owner名称、预算和业务事实一致。重复读取末段条目未继续增加，但这三轮不能证明长期平台期，更不能将全部RSS差额认定为泄漏或未释放缓存。

基线/修复ready pymalloc arena为379.750/374.000MiB，末尾379.000/373.500MiB；ready空闲pool265.750/261.625MiB，末尾168.328/162.926MiB。现有空闲pool仍是重要驻留部分，同时部分空间被读后Python对象复用。统计与帧预算相互覆盖，不与RSS相加。ready观测自身RSS增加6.148/4.902MiB，末尾观测无明显跳升，原数值保留于residence-checkpoints.json。

两侧9份完整响应逐字节一致，stats/Records三范围六份事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同；均8103 done/38历史failed，失败明细一致，无pending/running、新失败或有效窗OOM。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算调整。

当前仍为ARM Linux引擎上的amd64仿真，沿用封存runtime离线构建；原生资源、默认Python基镜像、overview64MiB、长期/并发及生产OOM仍OPEN。本轮没有新增full8、CI或生产请求。下一最小目标是合作aggregate消费者的所需列及局部生命周期：按当前高位栈减少frame/events/display/时长去重之间的冗余宽表，必须保留logical event、署名和interval/slice去重键。读取峰另在艺人Top albums专辑project聚合，不能混同为启动问题。本轮到此固定候选，不扩展额外allocator或全局缓存修改。

原始输出 `output/oom-absolute-peak-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-absolute-peak-20261015/`。原十三文件、当前十四文件、独立lifetime补丁、失败探针与两侧有效probe、所有单元/旧函数对账、三套runtime及完整响应/strict/分配器/采样均保存。归档校验CRC、候选源码/协调文档、双方9响应和六事实后，仅清理本轮三个已退出容器，保留镜像、输出和正式来源；实际收据位于独立归档。本轮未暂存、提交、推送或部署，main只更新协调文档。
