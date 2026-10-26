# OOM投影与生命周期研究汇总

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。十五份同日研究集中为一个候选演进记录。各项正确性、局部峰值观察、撤回候选、CPU波动、无效窗及累计Partial分别保留；后续发现的探针自干扰限制继续适用，不把累计采样差值解释成稳定因果收益或已发布成果。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [艺人统计首次读取内存峰值：载入与署名展开投影](#艺人统计首次读取内存峰值载入与署名展开投影)
- [艺人专辑子聚合：中间表投影与生命周期](#艺人专辑子聚合中间表投影与生命周期)
- [外层时长候选撤回与 Python 分配器归因](#外层时长候选撤回与-python-分配器归因)
- [Records 启动宽表生命周期最小修复](#records-启动宽表生命周期最小修复)
- [合作纪录署名键收集的最小投影候选](#合作纪录署名键收集的最小投影候选)
- [歌曲 canonical 合并前宽表副本的最小修复](#歌曲-canonical-合并前宽表副本的最小修复)
- [合作纪录 select 先筛选后复制的最小修复](#合作纪录-select-先筛选后复制的最小修复)
- [启动最高采样归因与合作纪录事件表生命周期修复](#启动最高采样归因与合作纪录事件表生命周期修复)
- [合作聚合中间表必要列投影的最小修复](#合作聚合中间表必要列投影的最小修复)
- [实体构建复用已具逻辑身份事件表的最小修复](#实体构建复用已具逻辑身份事件表的最小修复)
- [Records 计算结束后释放工作表再处理封面](#records-计算结束后释放工作表再处理封面)
- [快进纪录在 assign 前投影必要列](#快进纪录在-assign-前投影必要列)
- [专辑发行日期以两列键查询代替整表合并](#专辑发行日期以两列键查询代替整表合并)
- [启动 CPU 归因与专辑时长最后消费点](#启动-cpu-归因与专辑时长最后消费点)
- [合作署名窄表展开与累计候选收益审阅](#合作署名窄表展开与累计候选收益审阅)

## 艺人统计首次读取内存峰值：载入与署名展开投影

原记录：`2026-10-15-oom-artist-first-projection.md`。

核验日期：2026-10-15。问题：SS-2026-10-08-001，关联 SS-2026-10-09-001。

### 结论与范围

**本地最小候选保留；整体资源仍 Partial。** 冻结既有 mmap、Records 启动重排及冷专辑投影，只在已发布排名上下文的艺人详情分支新增 SQL 字段投影。130 项相关测试通过；同源两镜像各 9 次读取，完整响应逐字节一致，六份启动业务事实与 strict read window 通过。艺人首次请求采样峰增量 126.879→101.590 MiB，本轮读取窗口峰值低 27.465 MiB，末尾驻留低 8.230 MiB。启动峰值未改善，不关闭 OOM。

代码仅在 `codex/album-rank-cost` 研发工作树；共四个 tracked 修改和三个新测试文件，未暂存、提交、推送、整合或部署。main 仅更新协调文档，整合树保持原样。

### 分段归因

同一首次 Taylor Swift lifetime/dynamic 请求：

1. SQL 返回 27,534 行；原始投影 33 列。范围仍包含目标曲目前一条合格播放，不能删去这段上下文，否则会错误合并被其他曲目打断的播放。
2. 事件重建、有效署名展开与 canonical artist 处理完成后，原路径 RSS 约 623 MiB；署名后事件 21,432 行×48 列，未阈值化时长 30,113 行×41 列。
3. 随后筛选目标艺人与拥有的专辑、展开时长、构建专辑加权表。原路径最高浅栈证据位于 `compute_album_project_plays` 的 membership 关联后：37,387 行×57 列 weighted/events 与 37,387 行×78 列 merged 同时存活；上层还保留 all/current、目标事件、目标时长和 owned album 副本。采样 RSS 724.988 MiB。

因此，SQL/署名展开并非这次最高点；它们携带的多余列被后续多份宽表反复复制，放大了峰值。候选最高 RSS 样本未取得 backend 局部栈；此前样本位于同一专辑聚合段，不能把候选的最高样本精确归到某一内部语句。

### 最小修复

`entity_stats_service::_ARTIST_STATS_PLAY_COLUMNS` 明确已发布艺人详情所需字段，并以 `partial(load_plays_for_artists, columns=...)` 传给现有 scoped loader。复用 SQL 投影与缓存键，载入时就省去国家、播放原因、导入批次等未消费字段；并非展开完后再删除。

保留播放编号、时间及日历字段、platform、时长、track/source album、provider token、source fingerprint、曲目/专辑展示字段和 duration_ms；loader 仍添加 resolved L1/source/representative 身份。最近播放、专辑归属、动态阈值、合并边界与次数/时长轨道保持原消费合同。

| 阶段 | 原路径 | 候选 | 行数 |
| --- | ---: | ---: | ---: |
| SQL 输入列 | 33 | 22 | 27,534 |
| 署名及身份归并后事件列 | 48 | 37 | 21,432 |
| 署名及身份归并后时长列 | 41 | 30 | 30,113 |
| owned album 加权表列 | 57 | 46 | 37,387 |

未更改前序上下文 SQL、排序、逻辑事件编号先于署名展开、canonical identity 去重、有效署名解析、统计过滤或发布版本。未减少缓存预算、清缓存、强制 GC、增加 trim 或向公开 GET 加入写入。无发布上下文及轻量分支仍使用原路径。

### 正确性与镜像验证

- 56 项专项：新增 8 组 merge/dynamic/music 组合，将投影后每列事件与时长逐行对账全宽 loader；4 组完整 published artist payload 对账全宽 scoped loader并核对源/发布文件未写入；既有署名、身份、排名与缓存策略测试通过。
- 74 项相关消费者：既有 track/Top250 投影、Records 生命周期、专辑 published rank、所有收听时长、逻辑次数及艺人 chart loader 通过。共 130 个唯一测试；格式化后重复新增 12 项通过，不重复计数。
- 测试进程恢复全宽 `columns="*"` 后，8 个前置宽度断言均按预期失败；不把它计为业务结果差异。Ruff、格式检查、mypy hook、diff 检查通过。
- 同一封存缓存 runtime，Dockerfile backend 阶段离线构建；无 backend 源码覆盖挂载。两镜像各 518 个 backend/scripts 源文件与冻结上下文逐一一致，Python/依赖相同，mmap ENV 在 Python 启动前存在，代理未进入 runtime ENV。

基线：`sha256:36fd0f4ff920b8bac75455be8123dce7c10b4734a8d3b3ddb4accb379a3d5e56`。
候选：`sha256:c4005c2c108f345ca4f0cec9ac2fea5e8fd6ab47f8009aaf61556a6a3ebefb05`。

### 有界 Linux 对照

每侧新建七库副本，正常启动维护结束后，Midnights 两种 rank 请求各三轮，再 Taylor Swift artist 三轮；共 9 次串行 GET。相同 sampler/浅栈与阶段观察器，不做额外释放。每侧仅运行一次；不与上轮 33 读窗口直接比较。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1144.031 | 1160.723 | +16.691 |
| startup ready | 542.625 | 542.492 | -0.133 |
| 首次 artist 前 | 598.109 | 595.934 | -2.176 |
| 首次 artist 采样峰增量 | 126.879 | 101.590 | -25.289 |
| 本轮读取采样峰 | 724.988 | 697.523 | -27.465 |
| 最终 idle | 618.402 | 610.172 | -8.230 |
| ready 至最终增长 | 75.777 | 67.680 | -8.098 |
| 合法帧预算占用 | 202.910 | 181.076 | -21.834 |

候选三次 artist idle：610.500 / 610.172 / 610.172 MiB。缓存未饱和，有限重复不证明长期平台期或无泄漏。首次 artist 样本数 78/67，最大间隔 0.129/0.118 秒；整个窗口最大间隔 1.226/0.563 秒，记录的是采样峰而非连续真实高水位。

9 份完整响应逐字节一致。latest 三范围 stats/Records 六份业务事实一致，跨构建仅移除 `meta.generated_at`；各自 strict 比较未豁免时钟。37 原始表、保护事实、队列、发布与六 sidecar 读取前后保持；原七文件 SHA 未变。每侧均 8103 done/38 historical failed，failed 任务行相同；容器 exit0/OOMKilled=false。11 次 trim 均为原有真实维护调用，前后 cache roots/LRU 状态一致，没有额外释放。

### 证据、恢复与剩余边界

原始证据：研发树 `output/oom-artist-first-20261015/`。包括 frozen-existing-candidate、selected-candidate、artist-only.patch、两套镜像上下文/清单、130 项日志、原全宽断言失败、完整 body、stage/peak 栈、native 资源、strict 收据及 six-facts 对账。

独立恢复入口：`~/.codex/archives/spotifystats-delivery/oom-artist-first-20261015/`。压缩包 CRC、源码/文档快照、两侧完整 body 和业务事实校验后，按精确容器 ID 清理本轮两个已退出容器；保留镜像、原始输出及正式数据。最终归档/清理结果以该目录的收据为准。

基线 runner 在候选单独调用时覆盖了其汇总 list；没有重跑窗口，基线 live receipt 已核对 exit0，随后从独立 inspect、process-exit、strict 结果恢复保存为 baseline-window-receipt.json。两侧完整原始证据仍在。

当前 ARM Linux 引擎运行 amd64 仿真，使用封存缓存 runtime 替代命名 Python 基底；不构成默认 Python 基镜像、原生 CPU/时延或生产验收。沿用上一轮默认镜像构建 Partial，未重试网络。默认 overview 的 64 MiB 门槛、长期/更广并发、原生 Linux 与生产 OOM 仍 OPEN；本轮统计冷请求不套用 overview 门槛。

剩余峰值仍涉及目标/owned album 时长投影与多个全范围副本的共存。下一项应基于本轮栈证据收窄这些中间表并检查生命周期；不恢复旧混合 OOM 补丁，不因本次局部下降宣布整体收口。

## 艺人专辑子聚合：中间表投影与生命周期

原记录：`2026-10-15-oom-artist-album-intermediates.md`。


### 结果与范围

**保留局部峰值候选，整体资源 Partial。** 冻结上轮艺人 SQL 投影等七文件候选，只收窄 owned album 子聚合并移除无效副本。120 项相关测试通过；同源两镜像各 9 次读取，完整响应逐字节相同、六份统计业务事实相同、strict read window 通过。首次艺人峰增量 99.199→69.098 MiB，本轮读取采样峰低 20.832 MiB；末尾 RSS 高 9.301 MiB，其差异大部分在艺人请求前已存在，驻留收益未证明。

研发树当前四个 tracked 修改、四个新测试，共八文件。未暂存、提交、推送、整合或部署。既有七文件除 entity_stats_service.py 必要增量外，其余六文件逐字节保持；共享文档仅在 main 更新。

### 定位与最小实现

本轮基线仍复现 membership 关联后的最高浅栈：37,387 行×46 列 weighted/events 与 37,387 行×67 列 merged 同时存活，上层还持有全范围、目标及 owned album 多份表。

新增 `_artist_top_albums` 独立承载专辑子聚合：事件先投影 7 列，时长来源最多 8 列（保留 listening intervals），新投影清空自有 attrs。通过原 canonical song keys 和 album project membership 筛选拥有的专辑，继续排除仅客串贡献的他人专辑。

删除 `owned_album_all` 全历史副本：原时长构建已有显式 duration_source，不会读取该事件参数。改传 owned events，独立时长仍在期间过滤前保留完整区间。owned events、duration source、duration slices 在 helper 返回榜单后结束作用域；弱引用测试确认不再被持有，无强制 GC、trim 或缓存清理。

| 首次请求中间表 | 基线列数 | 候选列数 | 行数 |
| --- | ---: | ---: | ---: |
| owned events（加 canonical key/name 后） | 39 | 9 | 15,583 |
| owned duration source（加 key/name 后） | 32 | 10 | 20,820 |
| owned duration slices | 35 | 18 | 21,804 |
| album weighted | 46 | 20 | 37,387 |

没有修改全局 album 聚合器、个人排名入口、最近播放、首次/末次、次数/时长口径、署名身份、期间、排序或发布版本。源表与附属事实不修改；缓存预算和公开 GET 写入边界不变。

### 正确性与封装

- 39 项专项：新增 12 组完整 artist payload（merge/dynamic × lifetime/last_4_weeks/custom）对账全宽子聚合，6 组拥有权/跨日/独立次数与时长/无 interval 兼容和临时对象生命周期验证；其余为既有艺人投影、rank context、独立时长趋势。源与发布文件未写入。
- 81 项消费回归：track/Top250、album published rank、artist identity、versus personal stats、有效署名。合计 120 个唯一测试；Ruff、format、mypy hook、diff check 通过。
- 初轮 6 个失败来自测试观察器把 DataFrame.copy 深拷贝的 attrs 哨兵当作原对象比较；改为保存原 attrs 浅映射后通过，原日志保留。另在独立测试进程恢复全宽投影，6 个前置宽度断言按预期失败；不计为业务结果差异。
- 同一封存缓存 runtime 替代命名 Python 基底，Dockerfile backend 阶段离线构建，无源码覆盖挂载。两镜像各 518 个 backend/scripts 源文件与冻结上下文一致；依赖、mmap ENV 相同，代理未进入 runtime ENV。

基线：`sha256:c4005c2c108f345ca4f0cec9ac2fea5e8fd6ab47f8009aaf61556a6a3ebefb05`。
候选：`sha256:facf443abafa76e0409ab424733b69d22b6458e5447512238ba1ee85d47e3c92`。

### 有界 Linux 对照

每侧一个全新七库副本，正常启动维护完成后，Midnights 两种 rank 各三轮，再 Taylor Swift lifetime/dynamic artist 三轮；共 9 次串行 GET，同一观察器与 probe SHA，无热重跑。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1165.898 | 1154.402 | -11.496 |
| startup ready | 533.922 | 541.633 | +7.711 |
| 首次艺人请求前 | 600.500 | 609.770 | +9.270 |
| 首次艺人峰增量 | 99.199 | 69.098 | -30.102 |
| 本轮读取采样峰 | 699.699 | 678.867 | -20.832 |
| 最终 idle | 615.020 | 624.320 | +9.301 |
| ready 至末尾增长 | 81.098 | 82.688 | +1.590 |
| 最终合法帧预算 | 181.076 | 181.076 | 0 |

候选三轮 artist idle 为 623.879/623.902/624.320 MiB；有限重复不证明长期平台期。首次 artist 样本 64/59、最大间隔 0.108/0.102 秒；全窗最大间隔 0.867/1.306 秒。候选最高样本未取得 backend 局部帧；此前 backend 栈仍在 project 聚合，不能把最高样本精确归到某条语句。

末尾 RSS 差异 +9.301 MiB，艺人请求前已经 +9.270 MiB。从 startup ready 到末尾，两侧 pymalloc arena 数各自恒为 1485/1518，相差 33 个（8.25 MiB）；末尾 allocated blocks 为 198.656/199.068 MiB，仅差 0.413 MiB。glibc free 为 57.205/57.412 MiB，帧预算相同。证据支持启动后内存池布局驻留差异，不能把全部差值视为 helper 导致的回归；也不能声称驻留改善。见 allocator-checkpoints.json。

9 份完整 body 逐字节一致；latest 三范围 stats/Records 六份业务事实一致，跨构建仅移除 meta.generated_at，各自 strict 未放宽时钟。37 原始表、保护事实、队列、发布及六 sidecar 在 GET 前后保持；原七文件 SHA 不变。每侧 8103 done/38 historical failed，failed 行相同，容器 exit0/OOMKilled=false。11 次 trim 均为既有真实维护调用，前后 cache roots/LRU 相同，无额外释放。

### 证据与剩余工作

研发原始输出：`output/oom-artist-album-20261015/`；独立恢复入口：`~/.codex/archives/spotifystats-delivery/oom-artist-album-20261015/`。保存冻结前七文件、最终八文件、album-only.patch、镜像/请求/浅栈/allocator/strict、测试和观察器原失败日志及协调文档快照。归档 CRC、源码/文档快照、两侧 9 body 与 six facts 校验后，仅按精确 ID 清理本轮两个已退出容器；结果以独立目录收据为准。保留镜像、输出及正式数据。

本次为 ARM Linux 引擎上的 amd64 仿真与封存缓存 runtime，属于局部资源证据。默认 Python 基镜像构建仍沿用此前 Partial，未重试网络。未跑新 full8/CI 或生产验收。默认 overview 64MiB、长期/更广并发、原生与生产 OOM 仍 OPEN；本轮统计冷请求不套用 overview 门槛。

剩余目标是外层目标时长切片（仍 33 列）、all/current 副本共存，以及启动维护后 Python arena 高驻留。下一阶段继续按 owner 与生命周期收窄；本轮局部峰值收益不构成整体 OOM 收口。

## 外层时长候选撤回与 Python 分配器归因

原记录：`2026-10-15-oom-duration-rejected-allocator-attribution.md`。


### 处置

**本轮两项试验均不采用，原八文件候选逐字节保留；整体 OOM 仍 Partial。** 外层时长与范围副本候选正确性通过，但未证明峰值收益，已恢复业务源码并将本轮新测试移到隔离证据目录。最后一个窗口只在容器启动环境设置 PYTHONMALLOC=malloc，用于归因，没有修改 Dockerfile、生产配置或部署。未暂存、提交、推送或整合。

### 外层候选及正确性

候选将目标时长来源从 30 列投影为 13 列，切片从 33 列降为 16 列；已发布 lifetime 复用首次只读帧，日期过滤移到目标曲目筛选后，避免重复过滤和副本。日历字段保留无 interval 兼容，未更改最近播放、署名、阈值或统计口径。

134 个唯一相关测试通过（53 专项、81 消费）；其中 14 项新增测试确认独立次数/时长、跨日、无 interval、来源不变，以及已发布请求仅过滤一次目标范围。冻结原构建函数另有 35 次完整响应比较通过。恢复旧实现后，8 个重复过滤和 6 个列宽检查均按预期失败。

初轮冻结函数比较运行器遗漏 Python 3.9 的 postponed annotations，导致 53 项运行器调用失败、0 次业务比较；原日志保存，修正运行器后 39 项通过、35 次业务比较完成。该失败不记为产品回归。Ruff、format、mypy hook 与 diff check 通过。

| MiB | 基线 | 外层候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1153.406 | 1148.551 | -4.855 |
| startup ready | 540.434 | 546.996 | +6.563 |
| 首次艺人请求峰增量 | 57.504 | 65.785 | +8.281 |
| 读取采样峰 | 651.137 | 664.211 | +13.074 |
| 最终 idle | 607.441 | 612.555 | +5.113 |
| ready 至末尾增长 | 67.008 | 65.559 | -1.449 |
| 最终帧预算 | 181.076 | 181.076 | 0 |

列宽及副本减少没有转化为本窗峰值改善；不能把采样差异直接定为回归，也不追加窗口挑选收益。当前已有候选 facf 在上轮与本轮的读取峰也有差异，单窗小幅变化不足以关闭资源问题。源码恢复到本轮前冻结的八文件，未采用源码、补丁、测试与镜像完整保存。

### 分配器归因

默认分配器基线 startup ready：1511 个 arena，共 377.75 MiB；其中活跃分配块 87.086 MiB，空闲 pool 264.754 MiB。末尾 arena 数仍 1511，活跃块升至 198.824 MiB，空闲 pool 约 167 MiB。读取增长不能只看缓存或新 arena 数；启动已留下较大的空闲池驻留。

第三个、最后一个窗口复用完全相同的基线代码和镜像，只在 Python 启动前设置 PYTHONMALLOC=malloc。运行环境、容器 Env 及无 pymalloc arena 统计的 preflight 均核对；WITH_PYMALLOC 仍为编译能力，并非编译时禁用。私有符号 _PyMem_GetAllocatorsName 未导出，未用于判断。

| 指标 | 默认分配器 | malloc 归因窗口 |
| --- | ---: | ---: |
| 启动采样峰 MiB | 1153.406 | 1197.785 |
| startup ready MiB | 540.434 | 335.988 |
| 读取采样峰 MiB | 651.137 | 615.598 |
| 最终 idle MiB | 607.441 | 563.102 |
| ready 至末尾增长 MiB | 67.008 | 227.113 |
| 首次艺人峰增量 MiB | 57.504 | 107.563 |
| 最终帧预算 MiB | 181.076 | 181.076 |
| 启动维护等待秒 | 134.459 | 208.193 |
| ready 时进程 CPU 秒 | 135.30 | 210.13 |

启动后驻留低 204.445 MiB、末尾低 44.340 MiB，支持 pymalloc 池驻留是主要来源之一；但启动峰高 44.379 MiB、读取增长高 160.105 MiB，仿真 CPU 也更高。故只保留归因证据，不把 allocator 开关加入修复。malloc 末尾 glibc free 约 572 MiB 是分配器统计，不等于 RSS，不与其他占用相加。

### 边界、守恒与封装

同一关闭七库来源，三个全新副本各正常启动维护，再执行相同两条有限链各三轮，共 9 次 GET；三侧完整响应逐字节一致，latest 三范围 stats/Records 六份业务事实相同（跨构建仅移除 meta.generated_at），各自 strict 不放宽时钟。37 原始表、保护事实、队列、发布、六 sidecar 读取前后保持，原七文件 SHA 不变；每侧 8103 done/38 historical failed，failed 行相同，exit0/OOMKilled=false。每侧原有维护 trim 均 11 次，前后 cache roots/LRU 不变，无新增 GC、清缓存或 trim。

基线与 malloc 同用镜像 `sha256:facf443abafa76e0409ab424733b69d22b6458e5447512238ba1ee85d47e3c92`；未采用外层镜像 `sha256:18595045744f05cc83c776403048eb8e568cefd4ecf99182ce6c3a035657e903`。两代码镜像各 518 个源文件与冻结上下文相同、依赖相同，无源码覆盖；第三侧仅容器环境覆盖。Dockerfile backend 阶段使用封存缓存 runtime，默认 Python 基镜像仍沿用先前 Partial。

ARM 引擎/amd64 仿真，单窗每变体，采样并非连续高水位；默认/外层/malloc 最大采样间隔约 1.425/0.711/2.058 秒。不把 CPU 或等待差异当作原生基准。默认 overview 64MiB、长期/更广并发、原生资源及生产 OOM 均 OPEN。

### 下一定位目标与恢复

默认启动高水位附近 1140.094 MiB 的浅栈位于 Records `_build_entity_frames`：约 67,881 行事件与 96,301 行时长上，同时持有 event/artist/track/album 及 canonical membership 中间表，多数 45–54 列。原始最高样本 1153.406 MiB 没有同点栈，不据此声称某个单独分配语句为最高点。下一步应优先收窄该启动构建工作集，并检查长期缓存与临时对象的混合分配时序，不继续为微小读取副本变化扩展实验。

原始输出 `output/oom-artist-duration-20261015/`；独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-artist-duration-20261015/`。冻结八文件、未采用九文件、duration-only.patch、测试/原失败、三套运行数据、body/事实/strict、allocator 和最终 retained-disposition 均保存。归档 CRC、源码/文档及三侧 body 校验后，只清理本轮三个已退出容器，保留镜像、输出与正式数据；最终结果以独立收据为准。

## Records 启动宽表生命周期最小修复

原记录：`2026-10-15-oom-records-working-set.md`。


### 结果与范围

**保留局部启动峰值候选，整体 OOM 仍 Partial。** 同源隔离窗口中，启动采样峰 1154.004→1097.176 MiB，下降 56.828 MiB（约 4.9%）；读取峰和末尾RSS分别高 9.410/18.461 MiB，驻留收益未证明，暂不进入整合或发布。源码仍仅在 `codex/album-rank-cost`，共九文件未提交；main 只维护协调文档，整合工作树未新增业务变更。未暂存、提交、推送或部署，未请求生产。

本轮只改 Records `_build_entity_frames` 的临时表生命周期，接续原八文件候选：

- 艺人载入仍先完成。专辑事件与时长逐个构建，成功的 canonical 函数本身已复制输入，省去进入关联前的两份宽表复制；无归属、空输入与异常路径仍返回独立副本。
- 专辑关联放入局部 helper，canonical 与 merge 中间表在返回后释放；专辑对构建完成后才分配歌曲事件与时长对。保留全部返回列、dtype、索引、归属 fan-out 和附属时长，兼容 Records 与 Yearly Review。
- 共用只读 membership、可信发行日期优先级、逻辑事件去重、有效艺人署名及次数/时长规则均维持。没有删除字段、降低缓存预算、增加 GC/trim 或更改分配器配置。

### 正确性与初版处置

最终 **150 个唯一相关测试通过**，其中本轮新增 35 项，覆盖生命周期、L1/L2/L3、重复项目、空事件/时长、below-threshold 时长、重复索引、日期范围、代表曲目与发行日期，以及载入/关联/填充值异常。37 项专项包含在 150 项内，不重复计数。冻结本轮前旧函数做 39 组对账：117 张完整返回表及 117 张附属时长表的字段、dtype、索引、值和行序一致。临时宽表释放测试在旧函数上按预期失败。

补充 nullable project ID 的填充异常发现初版 helper 回退过早：旧时长路径保留关联后的 5 行，初版退回原 3 行。已精确修复该既有异常语义，再通过全部对账；初版镜像与完整窗口保留为未采用过程证据，不能交付。最终窗口是第三个、最后一个窗口，因正确性修复增加，没有追加选择有利资源结果。

初轮新增 fixture 对现有发行回退分支 attrs 与 NaN 的断言假设有误，原失败日志保留；核对旧函数后修正测试预期，未扩展修改既有行为。Ruff、format、项目 mypy hook、diff check 通过；直接使用本地 venv mypy 递归导入时有 23 文件共 59 个类型/存根错误，均未位于本轮两文件，原日志保留，不称全树 mypy 通过。未运行新 full8、CI 或浏览器/生产验收。

### 有界 Linux 对照

同一关闭历史七库来源（原始 94,760 plays），三个全新副本顺序执行：基线、未采用初版、最终修正版。每侧正常启动维护，随后相同两条链各三轮，共 9 次 GET：Midnights L3 fixed 的 stats light/rank 共 6 次，Taylor Swift L2 dynamic 的 artist stats/rank 共 3 次。无额外预热或热重跑，原启动 warmup=0。

| MiB | 基线 | 最终修正版 | 最终减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1154.004 | 1097.176 | -56.828 |
| startup ready | 533.699 | 541.477 | +7.777 |
| 读取采样峰 | 653.988 | 663.398 | +9.410 |
| 第9次读取后 idle3s（观测前） | 599.539 | 608.449 | +8.910 |
| 最终 idle | 599.539 | 618.000 | +18.461 |
| ready 至末尾增长 | 65.840 | 76.523 | +10.684 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

首次艺人请求采样峰增量 69.027→69.113 MiB；它不是本轮修改目标，不据单窗差异声称改善。startup ready 等待 132.561→132.938 秒，ready 进程 CPU 134.15→133.51 秒；均为仿真观察，不作为原生时延基准。

最终侧 artist-round3-idle3s 检查点观测前 608.449 MiB、观测后 618.000 MiB，观测期间增加 9.551 MiB；基线同点没有增长。表中最终 idle 保留原始值，未扣除观测开销。因此既不能把末尾差异全部归于业务驻留回归，也不能声称驻留改善。见 residence-checkpoints.json。

基线 startup ready 空闲 pymalloc pool 约 257.992 MiB，最终修正版约 263.824 MiB；末尾分别约 160.066/167.543 MiB。分配器统计不能与 RSS 或重叠缓存估算相加，宽表峰值缓解不等于池驻留解决。

初版启动峰 1101.297 MiB、ready 539.945、读取峰 661.203、末尾 603.910，单独保存在 comparison-v1.json，不作为最终候选验收。最终数值以上表与 comparison.json 为准。

### 事实守恒、封装与测量边界

三侧 9 份完整响应逐字节一致；三范围 stats/Records 六份业务事实一致，跨构建只排除 meta.generated_at，各自 strict 读取守恒不放宽时钟。37 原始表、保护事实、队列、发布与六 sidecar 前后一致，历史 failed 行相同、无新待运行任务；各侧 8103 done / 38 historical failed、exit0 / OOMKilled=false。原七文件 SHA 不变，每侧仍仅 11 次既有维护回收；cache roots/LRU 名称与预算合同未改。

三个 backend 镜像各 518 个 Python 源文件与冻结上下文匹配，依赖相同、无源码覆盖、无 runtime proxy。沿用已封存缓存 runtime 离线构建，并非默认 Python 基镜像完整构建已通过。基线 `sha256:facf443abafa76e0409ab424733b69d22b6458e5447512238ba1ee85d47e3c92`；最终 `sha256:7cf508099a18510d7c9762950967c00ff86836e96aea942b64c1adadcab36900`；初版未采用 `sha256:164bb8dcf4b2f1f1ae4cd4c3756d93a680346bbfb02af680afa9dde0dde513a1`。

ARM Linux 引擎运行 amd64 仿真，单窗每变体；基线/最终最大采样间隔 1.279/0.645 秒。浅栈是附近见证，不是每个最高样本的同点堆快照；同 ID 的局部别名不重复计为物理内存。原生 amd64 环境目前不可用；默认镜像、overview 64MiB、长期/更广并发与生产 OOM 仍 OPEN。

### 下一步与恢复

下一目标先沿本轮保存的最高浅栈收窄合作纪录的临时署名工作集：`build_collaboration_facts` 的 requested-ID 收集循环为抽取一个署名键，调用 `_credit_key` 复制六张完整事件/时长宽表。先针对该步骤做窄输入最小候选，保持有效署名、逻辑事件及独立时长去重；不要整体裁剪 Records/Yearly 返回帧，也不再扩展 allocator 试验。

原始输出 `output/oom-records-working-set-20261015/`；独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-records-working-set-20261015/`。保留原八文件冻结、最终九文件、两个局部补丁、初版与最终源码/镜像、所有测试/初始失败、三套 runtime、完整 body、事实/strict 和分配器数据。归档完成并验证 CRC、源码/文档、三侧响应与六事实后，只清理本轮三个已退出容器；镜像、输出及正式源保留，以独立收据为准。

## 合作纪录署名键收集的最小投影候选

原记录：`2026-10-15-oom-collaboration-credit-keys.md`。


### 处置与改动

**保留本地最小候选，结构改善已验证，整体资源仍 Partial，整合/发布 HOLD。** 收集署名键不再复制六张完整源表；同源配对观察到启动采样峰 1081.211→1046.914 MiB，低 34.297 MiB。但采样间隔与仿真 CPU 存在差异，不能把这部分全部归因为改动收益。读取增长约 65 MiB，仍未改善。

仅在 `codex/album-rank-cost` 增改两个文件：`backend/domains/playback/records_collaboration.py` 和新测试 `backend/tests/unit/test_collaboration_credit_key_projection.py`。此前九文件逐字节保留，当前共十一文件未提交。main 仅更新协调文档，未整合业务、暂存、提交、推送、部署或请求生产。

实现抽出 `_credit_track_ids`，共用 representative_track_id 优先、缺失不猜测、仅 legacy raw 库允许 track_id 回退及 pd.to_numeric(errors=coerce) 的原规则。requested-ID 收集直接读取键 Series 并去重，不再调用返回完整副本的 `_credit_key`；后续合作版本筛选、有效署名、完整事实表和聚合仍沿用原逻辑。没有裁剪 Records/Yearly 返回列，也没有缓存/分配器/回收配置变更。

### 正确性

169 个唯一相关测试通过，含 19 个新增测试；38 项署名键/合作纪录专项已包含在其中。新增测试覆盖现代与 legacy 边界、代表 ID 优先、空代表 ID 不回退、非法字符串/nullable ID/小数/空输入、重复索引、source 与 attrs 不变，以及仅出现在时长侧的曲目仍进入有效署名查询。

源表复制检查在 provider 查询时验证：仅建立逻辑身份所需的原事件复制存在，键收集不复制事件/歌曲/专辑及三张时长源表；恢复旧实现后按预期失败。冻结旧实现另完成 22 次完整 CollaborationFacts 比较：总事件数与七张完整事实表相同，共 154 张表比较；三个榜共 66 次聚合结果相同，覆盖手工 add/remove、Spotify 自动署名、canonical 艺人别名、L3 实际合作版本、重复项目/逻辑事件、时长切片和预载无连接路径。

Ruff、format、项目 mypy hook 与 diff check 通过。新增测试首轮 import 排序提示已修正；对账运行器初版摘要字段把八个 dataclass 字段误称八张表，已更正为七张表加总事件数，原日志末尾注明，比较循环本身未变。未运行新 full8、CI 或浏览器/生产验收。

### 两个隔离窗口

基线为上一轮已验证的九文件镜像 `sha256:7cf508099a18510d7c9762950967c00ff86836e96aea942b64c1adadcab36900`，候选为 `sha256:06a9d9de5a67fb0cf8c57f1a5b8e56be56d7368da9bd8cca0db654c8700d0445`。均从同一关闭历史七库来源（94,760 原始 plays）复制，全新运行并正常完成启动维护后，执行完全相同两条链三轮、每侧 9 次 GET：Midnights L3 fixed light/rank 六次与 Taylor Swift L2 dynamic rank 三次。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1081.211 | 1046.914 | -34.297 |
| startup ready | 532.801 | 547.887 | +15.086 |
| 读取采样峰 | 654.035 | 664.477 | +10.441 |
| 第9次读取后 idle3s | 598.188 | 613.105 | +14.918 |
| 最终 idle | 598.188 | 613.105 | +14.918 |
| ready 至末尾增长 | 65.387 | 65.219 | -0.168 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

末尾高 14.918 MiB，ready 已高 15.086 MiB；本窗读取增长 65.387→65.219 MiB，仅差 -0.168 MiB，不称改善。双方第9次读取后及末尾观测前后 RSS 都没有额外跳升，原值完整保留在 residence-checkpoints.json。

基线/候选 ready pymalloc arena 数 1481/1541，末尾仍为同一数量，候选多 60 个 arena（15 MiB）；ready 空闲 pool 256.918/270.773 MiB，末尾 160.035/174.207 MiB。这解释了末尾差异为何在读取前已存在，但不证明下一批读取不会继续增长。分配器统计与缓存估算不与 RSS 相加。

启动维护等待 140.427→165.210 秒，ready 进程 CPU 139.60→166.04 秒。候选 CPU 更高；未经过本次键收集路径的首个 Billboard 维护阶段也由 18.50→24.84 CPU 秒，不能把全部差异归因到本次代码，但也没有获得加速证据。进程 CPU 差值不是单 worker 线程 CPU，细分保存在 maintenance-timing-attribution.json。

基线最高采样同点浅栈在更早的 `_build_records_track_frame` 歌曲时长 merge；候选最高浅栈见证 1017.828 MiB 在艺人载入，未取得其实际最高样本1046.914 MiB的同点栈。基线/候选最大采样间隔 0.737/1.745 秒，存在漏过短峰的可能。因而结构性去复制证据与整个进程峰值观察分列，不能将 34.297 MiB 当作已证明的因果收益，也不能直接与上轮相减拼接累计收益。本轮只有两窗，不追加挑选有利结果。

### 守恒与封装

双方9份完整响应逐字节相同；三范围 stats/Records 六份业务事实相同，跨构建仅排除 meta.generated_at，strict 读取守恒不放宽时钟。37 原始表、保护事实、队列、发布及六 sidecar 前后不变；均 8103 done / 38 historical failed，failed 明细相同，无 pending/running、新失败或 OOM，实际 exit0。原七库文件 SHA 未变。

两镜像各 518 个 Python 源文件与冻结上下文相同，Python/glibc/依赖一致，未覆盖源码、未带 runtime proxy。保持 warmup=0 和既有 11 次维护回收，cache roots/LRU 与帧预算合同相同，无额外 GC/trim/cache clear。构建沿用封存缓存 runtime，并非默认基镜像构建已获得通过。

这是 ARM Linux 引擎的 amd64 仿真、每变体单窗；默认镜像、原生 amd64 资源、overview 64MiB、长期/更广并发和生产 OOM 均 OPEN。

### 下一步与恢复

优先围绕本窗基线同点最高栈的歌曲时长 canonical merge 继续缩小临时工作集；先验证能否仅计算聚合键再回填，保持重复键、索引、代表署名和所有输出列一致。读取增长另沿现有缓存 owner、生命周期与空闲 pool 证据继续归因，不能用降低预算或强制清理替代修复。当前十一文件仅作本地候选，资源准入前不整合发布。

原始输出 `output/oom-collaboration-keys-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-keys-20261015/`。保存原九文件、目标原实现、十一文件候选、局部补丁、fixture/旧函数比较、两套 runtime、完整 body/事实/strict、allocator 与时序。归档验证 CRC、源码/文档、双方响应与六事实后，仅删除本轮两个已退出容器，镜像、输出和正式源保留；收据记录最终状态。

## 歌曲 canonical 合并前宽表副本的最小修复

原记录：`2026-10-15-oom-track-merge-ownership.md`。


### 处置与实现

**保留本地最小候选；整体资源 Partial，整合/发布 HOLD。** L2/L3 有分组的 merge 路径省去事件表、时长表进入 merge 前的两份宽表副本，并顺序完成两侧投影。原 merge 继续处理重复键、空键、行展开、排序和 dtype；无分组、L1 和空输入仍返回独立副本。没有新增手写 map/回填算法，没有裁剪输出字段。

仅修改研发树 `backend/services/analysis_records_service.py`，新增 `backend/tests/unit/test_records_track_merge_ownership.py`；此前另外十文件逐字节不变，当前十二文件未提交。原歌曲代表署名、logical event ID、独立时长、专辑/艺人构建与公开 GET 规则不变。main 只维护协调文档，未暂存、提交、整合业务、推送、部署或请求生产。

### 正确性

194 个唯一相关测试通过，含25个新增；62项专项包含在其中。覆盖 L1/L2/L3、分组重复/空键/部分匹配、空事件/时长、重复索引、代表曲目、完整来源列和附属时长，修改返回表不影响源表。

冻结本轮前实现完成两套对账：歌曲构建39组，其中30组完整事件与时长结果相等、9组异常类型/参数相同，包含字段冲突、错误键类型、缺字段和预存canonical列；完整实体构建39组，117张返回表及117张附属时长表字段/dtype/索引/行序相同，覆盖异常回退与发行日期。新 ownership 检查验证两次 merge 接收原只读源表，在旧实现上按预期失败。Ruff、format、项目 mypy hook 与 diff check 通过。

### 同源两个 Linux 窗口

基线为上一轮十一文件镜像 `sha256:06a9d9de5a67fb0cf8c57f1a5b8e56be56d7368da9bd8cca0db654c8700d0445`，候选 `sha256:ac79b7b6c8d1c77b41bb2b51cfb153e4526630fb4c9ec8b5289a643b70371bcd`。同一关闭七库来源（94,760 原始 plays），两个全新副本顺序运行正常启动维护，再执行同一两条链各三轮、每侧9次GET：Midnights L3 fixed light/rank六次，Taylor Swift L2 dynamic rank三次。probe字节相同，未加预热、回收或缓存清理。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1078.055 | 1062.219 | -15.836 |
| startup ready | 543.309 | 552.320 | +9.012 |
| 读取采样峰 | 675.785 | 663.375 | -12.410 |
| 第9次读取后 idle3s | 621.887 | 619.078 | -2.809 |
| 最终 idle | 621.887 | 619.105 | -2.781 |
| ready 至末尾增长 | 78.578 | 66.785 | -11.793 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

只记录配对观察：启动峰低 15.836 MiB，读取峰低 12.410，末尾低 2.781。该改动只在启动 Records 构建中执行，读取差异可能受启动后的分配器状态及采样影响，不能全归因于修复。相同基线镜像在上轮读取增长65.219MiB，本轮为78.578；候选本轮66.785，未证明稳定驻留改善或长期平台期。

基线/候选 ready arena 分别 1524/1559，末尾数量各自未变；候选多35个arena（8.75MiB），与其ready高9.012MiB同阶段出现。ready空闲pool分别 267.141/275.637 MiB，末尾 170.297/179.664 MiB。统计不与RSS或缓存估算相加。第9次及最终观测时双方没有明显RSS跳升，原值见residence-checkpoints.json。

启动等待 145.083→178.325秒，ready进程CPU 144.83→180.45秒。候选明显更高；尚未执行本次改动的首个Billboard维护也由18.39→23.10 CPU秒。保留全部时序，不宣称加速，也不把全部差异定性为本次回归。进程CPU不等于worker线程CPU。

基线最高采样同点栈为歌曲时长merge；候选最高采样同点1062.219MiB已转至合作纪录 `_credit_key` / `select`，该处先复制完整表再筛选合作曲。采样目标50ms，实际最大间隔 0.691/2.013秒，候选可能漏过更短的峰。故去除显式副本的结构证据与峰值差异分列，不以小幅下降关闭OOM，也不跨轮拼接累计收益；本轮只跑两窗。

### 守恒与剩余工作

双方9份完整响应逐字节一致，三范围stats/Records六份业务事实一致；跨构建仅排除meta.generated_at，各自strict读取守恒不放宽时钟。37原始表、保护事实、队列、发布及六sidecar前后相同，均8103 done/38 historical failed，failed明细相同，无pending/running、新失败或OOM，实际exit0；原七库SHA不变。每侧仅既有11次维护回收，cache roots/LRU与181.076MiB帧预算相同，无新增GC、trim、clear或预算下调。

两镜像各518个Python源文件与冻结上下文匹配，Python/glibc/依赖一致，无源码覆盖/runtime proxy。沿用封存缓存runtime离线构建，默认Python基镜像未新验。当前为ARM Linux引擎的amd64仿真，每变体单窗；原生amd64资源、默认镜像、overview64MiB、长期/更广并发及生产OOM仍OPEN。未跑新full8、CI或浏览器/生产验收。

下一目标是合作纪录 `select`：先用共用署名键得到布尔掩码，再仅复制命中行，保留原数值转换dtype、重复索引、独立时长和完整输出列。该处已有本轮高位栈证据，暂不扩展新的allocator设置。读取后驻留仍需沿缓存owner与空闲pool独立归因。

原始输出 `output/oom-track-merge-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-track-merge-20261015/`。冻结原十一文件、十二文件候选、局部补丁、所有测试/旧函数比较、两套runtime、完整body/事实/strict、allocator与时序全部保留。归档验证CRC、源码/文档、双方响应与六事实后，仅删除本轮两个已退出容器，镜像、输出和正式源保留；最终状态见独立收据。

## 合作纪录 select 先筛选后复制的最小修复

原记录：`2026-10-15-oom-collaboration-select-projection.md`。


### 实现和正确性

本轮仅修改研发树 `backend/domains/playback/records_collaboration.py` 的嵌套 `select`：先在完整来源的署名键 Series 上完成原有数值转换与合作集合匹配，再复制命中行，最后附加已转换的键。由此省去每次 select 在筛选前生成完整宽表的中间副本；命中行仍是独立结果，保留全部来源列、列顺序、重复索引和既有 attrs 清空行为。完整来源的无效值仍参与 dtype 推断，避免过滤后重算导致类型漂移。

新增 `backend/tests/unit/test_collaboration_select_projection.py`，31项覆盖数值/字符串/可空整数与浮点键、无效值、全命中/无命中、空表、重复索引、已有署名键、legacy边界、专辑membership重复及独立时长切片。225个唯一相关测试通过，69项专项包含其中；Ruff、format、项目mypy hook、diff check通过。此前另外11个候选文件逐字节不变，当前13文件仅本地未提交。

冻结本轮前函数对账52次调用：48次完整返回相等，包括7张事实表、total_events和144份合作榜聚合，比较字段、dtype、索引与行序；4次缺失可用署名键的异常类型和消息一致。这4项是旧实现的下游merge异常，本轮保持既有边界，未另行修复。新的资源回归测试在旧实现上按预期失败，检出署名查询后5份原始来源的整表复制；候选通过，初始逻辑事件构建的副本不在本轮范围。

### 同源两个 Linux 窗口

基线为本轮前十二文件镜像 `sha256:ac79b7b6c8d1c77b41bb2b51cfb153e4526630fb4c9ec8b5289a643b70371bcd`，候选 `sha256:24d4394212b68e08dfc435ff571ee93a6e5e9c8321291b267b2ccacf04486924`。两个全新七库副本来自相同关闭来源（94,760条原始plays），顺序执行正常启动维护，再执行相同9次公开只读GET：Midnights L3 fixed light/rank各三轮，Taylor Swift L2 dynamic rank三轮。probe逐字节相同，无预热、额外回收、缓存清理或预算下调。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1053.914 | 1031.418 | -22.496 |
| startup ready | 540.293 | 541.984 | +1.691 |
| 读取采样峰 | 665.738 | 664.301 | -1.438 |
| 第9次读取后 idle3s | 618.000 | 608.055 | -9.945 |
| 最终 idle | 619.906 | 608.066 | -11.840 |
| ready 至末尾增长 | 79.613 | 66.082 | -13.531 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

**保留本地最小候选；整体资源仍Partial，整合/发布HOLD。** 结构上已省去合作select的筛选前宽表副本；本对照启动采样峰低22.496MiB、读取峰低1.438MiB、最终低11.840MiB。改动运行于启动Records构建，读取差异可能受启动后分配器状态、仿真及观测影响，不能全部归因于修复。同一基线镜像上一轮读取增长66.785MiB，本轮79.613MiB；候选本轮66.082MiB，尚未证明稳定驻留改善，不跨轮拼接累计收益。

基线/候选ready arena为1511/1518个（377.750/379.500MiB），各自末尾数量未变。ready空闲pool 264.270/265.281MiB，末尾166.266/168.070MiB。预算和cache roots/LRU相同，分配器统计不与RSS或缓存估算相加。ready观测自身RSS分别增加4.809/3.613MiB；第9次idle观测基线增加1.906MiB、候选为0；这些开销均保留于residence-checkpoints.json，不将最终差异视为纯业务分配。

启动等待134.041→169.339秒，ready进程CPU 135.88→170.40秒，候选明显更高。尚未触及本次改动的首个Billboard维护进程CPU也由17.43→21.75秒，全部11项时序保留于pair-summary.json。不宣称加速，也不能把全部耗时差异定性为本次回归；进程CPU并非worker线程CPU。

基线1053.914MiB最高采样同点栈确实落在合作select的 `_credit_key`，当时歌曲源表67,881×52、合作事件结果6,518×49，其他Records宽表仍存活。候选绝对采样峰为1031.418MiB，但没有该采样同点栈：沿用的probe仅在启动高水位增加32MiB时记录栈，最高已保存栈1017.332MiB，早于绝对峰10.820秒，位于 `_load_plays_for_artists_cached` 的时长署名merge。故不能声称绝对峰已经转移到该merge。采样目标50ms，实际最大间隔1.161/0.691秒，短峰可能遗漏。本轮仅两窗，不追加追逐有利数值的实验。

### 守恒、边界和交接

双方9份完整响应逐字节相同，三范围stats/Records六份业务事实相同；跨构建仅排除meta.generated_at，各自strict读取守恒不放宽时钟。37原始表、保护事实、队列、发布及六sidecar读取前后相同；每侧8103 done/38 historical failed，失败明细相同，无pending/running、新失败或OOM，实际exit0。正式七库文件SHA不变。每侧仅原有11次维护回收，无新增GC/trim/clear。

两个镜像各518份Python源文件与冻结构建上下文相同，镜像间仅本轮domain文件不同；Python、glibc、依赖及进程启动前MALLOC_MMAP_THRESHOLD_=131072一致，无源码覆盖或runtime proxy。离线沿用封存runtime构建，默认Python基镜像没有新验。当前仍为ARM Linux引擎上的amd64仿真、每变体单窗；原生amd64、默认镜像、overview64MiB、长期/并发和生产OOM仍OPEN。没有执行新full8、CI或浏览器/生产验收。

本轮选择逻辑修复与有界验证完成，13文件候选留在既有研发树，业务未整合main。1031MiB启动峰和66MiB读取增长仍未解决；下一阶段先补绝对峰的同点ownership证据，再决定初始逻辑事件副本或署名展开是否为最小修复目标，同时将读取后cache owner与空闲pool分开归因。没有因此扩展本轮产品修改或allocator设置。

原始输出 `output/oom-collaboration-select-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-select-20261015/`。冻结原十二文件、十三文件候选、select独立补丁、旧函数比较、所有测试、两套runtime、响应/事实/strict、allocator与时序均保存。归档核对CRC、源码/文档、双方9响应和六事实后，仅清理本轮两个已退出容器；镜像、输出及正式来源保留。归档和清理实际结果见独立收据。本轮未暂存、提交、推送或部署，main仅更新协调文档，其他任务文件保留。

## 启动最高采样归因与合作纪录事件表生命周期修复

原记录：`2026-10-15-oom-collaboration-event-lifetime.md`。


### 归因和最小修复

上轮32MiB阶梯式保存栈会漏掉阶梯内的更高采样值。本轮保持原十三文件镜像，先在新七库副本把探针改为每次刷新最高采样时替换保存栈及有界浅层元数据，再据证据修复。探针仅保存数值、形状、别名和缓冲区根标识，不保留业务表对象，不做全堆扫描或强制回收。

首窗在Pandas构造中遇到尚无`_mgr`的DataFrame，采样线程退出，窗口标无效并手动停止（实际137、OOMKilled=false）；日志及runtime原样保留，不作为峰值或业务回归证据。修正探针跳过未完成构造的DataFrame/Series，并在同一Linux镜像验证对象去重、附属时长和共享NumPy根后，仅修复性重跑一次。有效归因窗最高启动采样1027.375MiB，已保存同次采样UTC/RSS的栈，未触及元数据上限。

该采样栈落在合作艺人名称`groupby(...).agg(list)`，19张去重表中`events`独立为67,881×49，仅由`build_collaboration_facts.events`持有。它的扁平block计20.716MiB，在已观察表根中独占的NumPy存储约19.162MiB；对象字符串等payload可能共享，均不是RSS估算。歌曲、专辑投影已经结束，后续仅返回`len(events)`，完整身份投影因此在后续署名展开和聚合期间多存活了一段。

最高采样到抓栈开始延迟0.021ms，元数据抓取15.591ms，结束RSS为1012.266MiB。读RSS和抓栈并非原子操作，不能把名单聚合认定为全部峰的唯一分配源；当前证据支持的是该大表在高位附近的无用存活。启动79次/读取44次捕获总开销0.221/0.062秒，实际采样最大间隔1.118秒；真实短峰仍可能漏过。

本轮业务仅在研发树`backend/domains/playback/records_collaboration.py`缓存事件总数，并在两次`_event_projection`最后一次消费完成后`del events`，返回使用保存的整数。输入表、合作事件结果、返回列、排序、dtype、时长事实均不裁剪。新增`backend/tests/unit/test_collaboration_event_lifetime.py`的6项检查覆盖部分/全命中/无命中及有无独立时长，确认署名展开前该独立表的weakref已失效。旧实现6项均按预期失败，修复通过，无测试性GC。

231个唯一相关测试通过，56项专项包含其中；冻结旧函数52次调用中48份完整事实及144份聚合相同，4次既有缺失键异常类型/消息相同。Ruff、format、项目mypy hook、diff check通过。此前另外12文件逐字节不变，当前14文件候选仅本地，未提交。

### 同源、同探针配对

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

### 读取后驻留与边界

双方末尾均4个帧预算条目、181.076MiB：3个`db.plays`及1个`db.plays_for_artists`，包含各自附属时长；另有小型canonical map及约3MiB未注册排名响应LRU。owner名称、预算和业务事实一致。重复读取末段条目未继续增加，但这三轮不能证明长期平台期，更不能将全部RSS差额认定为泄漏或未释放缓存。

基线/修复ready pymalloc arena为379.750/374.000MiB，末尾379.000/373.500MiB；ready空闲pool265.750/261.625MiB，末尾168.328/162.926MiB。现有空闲pool仍是重要驻留部分，同时部分空间被读后Python对象复用。统计与帧预算相互覆盖，不与RSS相加。ready观测自身RSS增加6.148/4.902MiB，末尾观测无明显跳升，原数值保留于residence-checkpoints.json。

两侧9份完整响应逐字节一致，stats/Records三范围六份事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同；均8103 done/38历史failed，失败明细一致，无pending/running、新失败或有效窗OOM。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算调整。

当前仍为ARM Linux引擎上的amd64仿真，沿用封存runtime离线构建；原生资源、默认Python基镜像、overview64MiB、长期/并发及生产OOM仍OPEN。本轮没有新增full8、CI或生产请求。下一最小目标是合作aggregate消费者的所需列及局部生命周期：按当前高位栈减少frame/events/display/时长去重之间的冗余宽表，必须保留logical event、署名和interval/slice去重键。读取峰另在艺人Top albums专辑project聚合，不能混同为启动问题。本轮到此固定候选，不扩展额外allocator或全局缓存修改。

原始输出 `output/oom-absolute-peak-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-absolute-peak-20261015/`。原十三文件、当前十四文件、独立lifetime补丁、失败探针与两侧有效probe、所有单元/旧函数对账、三套runtime及完整响应/strict/分配器/采样均保存。归档校验CRC、候选源码/协调文档、双方9响应和六事实后，仅清理本轮三个已退出容器，保留镜像、输出和正式来源；实际收据位于独立归档。本轮未暂存、提交、推送或部署，main只更新协调文档。

## 合作聚合中间表必要列投影的最小修复

原记录：`2026-10-15-oom-collaboration-aggregate-projection.md`。


**处置：保留本地局部列投影候选；总体峰值未改善，资源Partial，整合/发布HOLD。**

### 实现与正确性

上一轮最高采样落在`_feat_lover_artist → aggregate_collaboration → _duration_dedupe`，事件frame/events各15,178×52、display 1,084×51、时长22,913×49。消费者仅需要少量身份、名称、署名列表和时长去重事实，其他来源列被反复携带进copy、sort和drop_duplicates。

本轮仅修改研发树`backend/domains/playback/records_collaboration.py`：聚合事件在复制前选择所需列，附加entity_id后最多8列；时长在复制前选择实体身份和完整去重事实，附加entity_id后最多11列。原9个时长去重字段提为共用tuple，供投影和`_duration_dedupe`同时消费，保留不同interval/slice、逻辑事件、来源play、署名版本及ms_played。列顺序依原来源排列，避免artist名称/专辑名称兼作参数时重复选择同名列。

没有缩窄CollaborationFacts完整返回表，没有重写groupby、排序、署名列表展开或事件计数算法。未增加GC/trim/clear、预算调整、allocator或全局缓存修改。此前另外13个候选文件逐字节不变，新增`backend/tests/unit/test_collaboration_aggregate_projection.py`，当前15文件候选仅本地未提交。

258个唯一相关测试通过，含27项新增，46项专项包含其中。新测试覆盖歌曲/艺人/专辑、名称兼身份、署名列表有无、独立时长与事件回退、重复逻辑事件、低于次数阈值的时长、重复索引、空/缺字段边界及源表/attrs不变，并逐一验证9个时长键的差异能保留独立贡献。复制检查在旧实现按预期失败，候选复制的中间表均不包含未消费的来源列。Ruff、format、项目mypy hook与diff check通过。

冻结本轮前完整模块进行对账：52次builder调用中48份完整7表及total_events一致、4次既有缺失键异常一致；144份榜单使用冻结旧aggregate与新aggregate分别计算后完全一致。另有26组直接aggregate调用比较输出schema、dtype、索引和行序，通过。没有用同一个新聚合器计算两侧结果来代替旧实现对照。

### 同源两个 Linux 窗口

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

### 守恒与剩余边界

双方9份完整响应逐字节一致，stats/Records三范围六事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同，均8103 done/38历史failed，失败明细相同，无pending/running、新失败、采样器错误或OOM，实际exit0。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算下调。

末尾帧预算同为4条/181.076MiB，cache roots/LRU owner相同。基线/候选ready pymalloc arena382.750/376.000MiB，与ready RSS差异量级相同；末尾382.750/375.750MiB，空闲pool171.922/164.855MiB。它们与帧估算相互覆盖，不与RSS相加。ready观测自身RSS增加4.969/5.148MiB，末尾无明显观测跳升。读取最高采样两侧均在艺人Top albums的album project聚合；它与启动宽表重叠分开跟踪。

仍为ARM Linux引擎上的amd64仿真、每侧单窗，离线沿用封存runtime；原生资源、默认Python基镜像、overview64MiB、长期/并发及生产OOM仍OPEN。没有新full8、CI、浏览器或生产请求。本轮正确性通过不代表资源准入通过。

原始输出 `output/oom-collaboration-aggregate-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-aggregate-20261015/`。原十四文件、十五文件候选、独立aggregate补丁、旧函数/新回归与全部测试、两套runtime及完整响应/事实/strict/分配器/最高采样归属均保存。归档校验CRC、源码/协调文档、双方9响应和六事实后，仅清理本轮两个已退出容器；镜像、输出和正式来源保留，实际结果见独立收据。本轮未暂存、提交、推送或部署，main仅更新协调文档。

## 实体构建复用已具逻辑身份事件表的最小修复

原记录：`2026-10-15-oom-entity-identity-ownership.md`。


**处置：保留本地最小候选；源表不变和主返回表独立通过，整体资源仍Partial，整合/发布HOLD。**

### 实现与正确性

上一轮启动最高采样在歌曲时长merge时，`_get_analysis_records_uncached`与`_build_entity_frames`同时持有两份67,881×48事件表，且都已带_logical_event_id。后者的无条件`assign_logical_event_id`仍复制完整表，随后所有实体投影又各自产生独立结果。

本轮业务仅在研发树`backend/services/analysis_records_service.py`的`_build_entity_frames`入口增加列存在条件：已有_logical_event_id时只读复用输入；缺失时继续调用原assign函数。没有改变ID生成/保留语义，已有重复或nullable ID也按旧合同保留，没有改变通用assign函数的独立返回合同。歌曲、专辑及艺人结果仍由原有owned投影或copy回退产生，完整字段保持。此前另14个候选文件逐字节不变，新增`backend/tests/unit/test_records_entity_identity_ownership.py`，当前16文件仅本地未提交。

300个唯一相关测试通过，含42项新增，覆盖L1/L2/L3、专辑membership正常/空/错误/部分填充回退、艺人失败、事件/时长空表、日期范围、重复索引、已有年度ID及legacy artist ID、年度裸时长attrs。修改返回表单元格及attrs后，源事件、源时长和其他主返回表保持原样；可修改时长消费表继续经records_duration_frame默认copy获取，维持既有attrs引用合同。缺身份时仍分配一次，已有身份时不调用assign且两个投影入口接收原只读输入。

冻结本轮前outer builder对账156组：3层级×13场景×4种身份状态（缺失/已有/重复/nullable），468张完整主返回表与468张时长消费表schema、dtype、索引、行序相同，每组源表及attrs守恒。另有年度裸listening_duration_slices附件检查，确保源metadata仍引用原附件且内容不变。旧实现资源回归检查在3个已有身份案例按预期失败，3个缺身份对照仍通过。Ruff、format、项目mypy hook与diff check通过。

### 同源两个 Linux 窗口

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

### 守恒与剩余边界

双方9份完整响应逐字节一致，stats/Records三范围六份业务事实一致；跨构建仅排除meta.generated_at，各自strict不放宽时钟。37原始表、保护事实、队列、发布和六sidecar读取前后相同；均8103 done/38历史failed，失败明细相同，无pending/running、新失败、采样器错误或OOM，实际exit0。正式七库SHA不变，每侧仅原有11次维护回收，无新增GC/trim/clear或预算调整。

末尾均4个帧预算条目、181.076MiB，cache roots/LRU owner一致；读取后的缓存增长与启动副本分开跟踪。基线/候选ready pymalloc arena376.750/376.000MiB，末尾376.750/375.750MiB；末尾空闲pool167.000/163.359MiB。它们与帧估算互相覆盖，不与RSS相加。ready观测自身RSS增加5.195/5.363MiB，末尾观测无明显跳升。

约1GiB总峰仍在Records计算/展示持有多套宽表期间，读取最高采样两侧均在艺人Top albums的album project聚合。后续应先按实体构建、Records计算、展示解析三个阶段核对owner与最后消费点，再选择必要列或生命周期修复，不仅根据某个最高栈继续微调。当前ARM Linux引擎的amd64仿真、封存runtime离线构建和每侧单窗不能替代原生资源验证；默认Python基镜像、overview64MiB、长期/并发和生产OOM仍OPEN。本轮没有新full8、CI、浏览器或生产请求。

原始输出 `output/oom-entity-identity-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-entity-identity-20261015/`。冻结原十五文件、当前十六文件、独立identity补丁、初版与最终所有单元/旧函数对账、两套runtime、完整响应/事实/strict/分配器/最高采样及NOT_OBSERVED记录均保留。归档校验CRC、源码/协调文档、双方9响应和六事实后，仅清理本轮两个已退出容器，保留镜像、输出和正式来源；实际结果见独立收据。本轮未暂存、提交、推送或部署，main仅更新协调文档。

## Records 计算结束后释放工作表再处理封面

原记录：`2026-10-15-oom-records-presentation-lifetime.md`。


**处置：展示阶段生命周期修复保留为本地候选；源表与结果守恒通过，整体资源仍Partial，整合/发布HOLD。**

### 改动与正确性

上一轮同点采样显示，实体构建完成后，`_get_analysis_records_uncached`仍持有事件表、终身历史副本、歌曲/专辑/艺人主表及其时长附件。封面解析只消费`raw_records`，但这些局部引用直到响应返回才释放；其中`range_source`还额外别名持有事件或时长表。上一轮基线最高采样发生在Records封面解析，候选最高点则在较早的时间纪录计算，不能将展示阶段释放直接视为整个峰值已消失。

本轮仅修改研发树`backend/services/analysis_records_service.py`：读取终身范围起止日期后删除`range_source`别名；六族纪录计算返回后删除事件、终身历史、两份时长别名和三类实体主表的局部引用，再执行原有封面解析与序列化。计算调用顺序、参数、完整结果、事件和时长口径不变。没有修改caller的预载表，也没有清空结果或其attrs；如果结果仍引用某个输入，正常引用所有权继续保活。没有增加GC、trim或缓存清理。

新增28项测试：24个资源案例覆盖standalone/Yearly预载、lifetime/仅起点/仅终点/双边custom、正常/事件空/时长空，均在封面入口用weakref验证计算专用表已释放，源表与原时长、年度预载表保持原样；另2个完全空历史早返回和2个结果直接保留输入的序列化对照通过。冻结原函数运行同批测试，24个引用滞留案例按预期失败、4个空表/结果保活对照通过，证明资源检查能区分修复前后。

373项唯一相关测试通过，含28项新增，覆盖Records/时长/合作/排名/年度消费及专辑project合同。Ruff、format、mypy与diff check通过。之前16个候选中另外15个文件不变，当前17文件仅本地未提交；独立补丁与冻结源码均保留。

### 同源 Linux 对照

基线16文件镜像`sha256:ff46a482979723970c2bf40dd6ce89b9dda9041be60a06b5ac5898d7b65f2e22`，候选`sha256:6975a249200376e2db2f4841f8b1347bc937aa269c012498e9daff27b5a51d79`。各518份Python源码与冻结上下文一致，镜像间只有本轮service文件不同；同Python、glibc、依赖、进程启动前mmap阈值。离线封存runtime构建，ARM Linux引擎运行amd64仿真，不替代原生或默认Python基镜像验证。

两个全新七库副本来自同一94,760原始plays来源。相同probe含固定实体构建、纪录计算、封面处理前后边界，仅存浅层元数据与weakref；最高采样仍独立记录。每侧启动后执行相同9次GET：Midnights L3 fixed light/rank六次、Taylor Swift L2 dynamic rank三次，三轮串行。network none、只读root、无端口、4GiB容器/3GiB进程RSS保护、启动600秒及总900秒边界保持。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1010.586 | 1003.230 | -7.355 |
| startup ready | 552.746 | 536.242 | -16.504 |
| 读取最高采样 | 674.258 | 657.426 | -16.832 |
| 第9次后idle3s | 619.750 | 600.844 | -18.906 |
| 最终idle | 619.754 | 600.859 | -18.895 |
| ready至末尾增长 | 67.008 | 64.617 | -2.391 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

### 阶段持有关系

| 启动Records调用次序 | 基线封面入口RSS MiB | 候选封面入口RSS MiB | 基线/候选工作表局部变量数 | 基线/候选主输入weakref存活数 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 964.086 | 750.301 | 8/0 | 5/0 |
| 2 | 778.070 | 726.633 | 7/0 | 5/0 |
| 3 | 794.465 | 730.832 | 7/0 | 5/0 |

候选同一次调用的compute返回至封面入口RSS分别减少212.258、50.535、62.477MiB；基线同边界未下降。跨窗三次入口分别低213.785、51.438、63.633MiB，结合局部引用与weakref证据，支持此处生命周期修复有效。这些是阶段观察，不代表全局启动峰降低同样幅度。

工作表局部变量指事件、终身副本、时长别名、range_source及三类实体表；主输入weakref包括传给compute的事件、实体与milestone表。边界元数据和持有者按完整原样保存；工作表局部引用消失不代表所有底层buffer或结果保留的时长附件均已释放，不把估算块字节与RSS相加。阶段捕获会同步CPython的f_locals缓存，双方使用相同probe。

基线启动最高采样栈为`build_collaboration_facts → compute_discovery_records → compute_playback_records → _get_analysis_records_uncached`；读取最高采样栈见同点收据。峰值捕获开始延迟0.016ms、耗时13.241ms；实际最大采样间隔0.979秒，短峰可能遗漏。固定阶段观察额外耗时0.067秒。启动等待132.220秒，ready进程CPU132.540秒；11项维护任务时序与最高采样观察开销均保留。

候选启动最高采样栈为`_skip_storm → compute_behavior_records → compute_playback_records → _get_analysis_records_uncached`；读取最高采样栈见同点收据。峰值捕获开始延迟0.020ms、耗时1.060ms；实际最大采样间隔0.830秒，短峰可能遗漏。固定阶段观察额外耗时0.337秒。启动等待132.050秒，ready进程CPU132.440秒；11项维护任务时序与最高采样观察开销均保留。

### 守恒、处置与剩余工作

双方9份完整响应逐字节一致，三范围stats/Records六份业务事实一致；跨构建只排除meta.generated_at，各自strict时钟保持。37原始表、保护事实、队列、发布与六sidecar在读取前后不变，8103 done/38历史failed及失败明细一致，无pending/running或新失败；正式七库SHA不变。两窗口exit0，无OOM或采样器错误；每侧仅11次既有维护回收，无新增GC/trim/clear或预算调整。

局部生命周期修复保留；整体资源仍Partial、整合/发布HOLD。此轮每侧仅单窗，阶段RSS与全局峰值分别解释，不把小幅窗口差异认定为稳定OOM或驻留收益。读取最高采样低16.832MiB，接近ready本身低16.504MiB；读取后增长仅少2.391MiB，不能据此认定读取链路已有稳定改善。两侧读取最高点均在艺人Top albums的album project聚合。ready/末尾pymalloc arena基线均389.750MiB、候选均373.750MiB，末尾空闲pool179.812/162.820MiB；合法帧预算均4条、181.076MiB，roots/LRU owner一致，这些估算不与RSS相加。读取驻留继续独立跟踪；overview64MiB、原生/默认镜像、长期/并发和生产OOM继续OPEN。本轮无新full8、CI、浏览器或生产请求。下一优先验证`_skip_storm`给67,881×56专辑宽表assign临时列时的复制，核对分组键、play_id、ms_played与reason_end的最小列集，并对照合作事实构建的同时存活表；以缩小计算工作集作为下一候选，不继续将封面阶段收益当作全局峰值收益。

原始证据`output/oom-records-presentation-lifetime-20261015/`，独立恢复入口`~/.codex/archives/spotifystats-delivery/oom-records-presentation-lifetime-20261015/`，包含冻结16文件、当前17文件、独立补丁、测试/旧实现资源对照、两套runtime、完整响应/六事实/strict、18个阶段边界各一套及最高采样元数据。归档校验CRC、源码/协调文档、双方9响应和六事实后，仅清理本轮两个已退出容器；镜像、原始输出和正式来源保留，实际结果见独立收据。未暂存、提交、推送或部署，main仅更新协调文档。

## 快进纪录在 assign 前投影必要列

原记录：`2026-10-15-oom-skip-storm-projection.md`。


**处置：保留本地最小候选；源表和统计结果一致，整体资源仍 Partial，整合/发布 HOLD。**

### 修复与正确性

上一轮候选启动最高采样位于`_skip_storm`处理67,881×56专辑事件表期间。原函数用`frame.assign(_forward=...)`构造快进标记，先复制包含大量无关字段的实体宽表，再做groupby。实际只消费分组身份/名称、play_id计数、ms_played求和与reason_end快进判定。

本轮仅改研发树`backend/domains/playback/records_behavior.py`的`_skip_storm`：在原assign前用`unique_cols`投影分组键、play_id及ms_played，快进布尔Series仍从只读原reason_end生成。重复的艺人分组列去重，原计数与求和、10次门槛、缺失值规则、完整候选排序与输出字段均保持。源事件、时长附件及attrs不改动，结果仍独立；未扩大到其他行为纪录或修改缓存、分配器、回收策略。此前17个候选文件逐字节不变，新增本轮业务文件和测试后，共19文件仅本地未提交。

392项唯一相关测试通过，包含19项新增：三实体的同率稳定排序、门槛、重复索引、乱序、浮点时长、nullable计数、源表/时长附件不变，以及直接检查assign只收到必要列。冻结旧函数运行同批测试，3个整宽复制检查按预期失败，16个统计/空态对照通过。

独立旧函数对账90组：歌曲/专辑/艺人×15个场景×原列序/反向列序，覆盖nullable ID/时长/原因、categorical及未观测类别、空表、缺reason_end、门槛不足、空分组、重复索引、已有_forward、年度裸时长attrs。完整结果的schema、dtype、索引与行序相同，源事件、源时长和attrs每组守恒。Ruff、format、项目mypy hook与diff check通过。原始检查日志均保留。

### 同源 Linux 对照

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

### 直接列宽与阶段证据

双方各记录9次_skip_storm的直接assign；对应输入行数相同，候选每次仅包含必要列。首个完整范围：

| 实体 | 行数 | assign输入列数 基线→候选 | assign输出列数 基线→候选 |
| --- | ---: | ---: | ---: |
| track | 67881 | 52→5 | 53→6 |
| album | 67881 | 56→5 | 57→6 |
| artist | 76541 | 48→3 | 49→4 |

输入投影发生在assign之前，所以此边界的RSS与耗时不包含投影分配；这些数据用于证明复制列集，不能冒充整个函数峰值。估算块字节不包含完整object payload或attrs，也不与RSS相加。双方三次封面入口工作表局部引用均为0，维持上一轮生命周期修复；阶段表与weakref证据保留。

基线启动最高采样栈`_skip_storm → compute_behavior_records → compute_playback_records → _get_analysis_records_uncached`；读取同点栈见原始证据。最高采样捕获延迟0.021ms，耗时1.060ms；实际最大采样间隔1.361秒，短峰可能遗漏。启动等待133.872秒，ready进程CPU134.130秒；固定Records阶段观察额外0.326秒，9次assign边界观察及11个维护任务时序均保留。

候选启动最高采样栈`_build_entity_frames → _get_analysis_records_uncached`；读取同点栈见原始证据。最高采样捕获延迟0.020ms，耗时1.339ms；实际最大采样间隔0.952秒，短峰可能遗漏。启动等待132.184秒，ready进程CPU133.460秒；固定Records阶段观察额外0.367秒，9次assign边界观察及11个维护任务时序均保留。

### 守恒与处置

双方9份完整响应逐字节相同，三范围stats/Records六份事实相同；跨构建仅排除meta.generated_at，各自strict时钟保持。37原始表、保护事实、队列、发布及六sidecar读取前后不变；8103 done/38历史failed和失败明细相同，无pending/running或新失败。正式七库SHA不变，两窗实际exit0、无OOM或采样器错误。每侧只有原有11次维护回收。帧预算均4条、181.076MiB，cache roots/LRU owner保持；ready及末尾pymalloc arena基线均383.750MiB、候选均385.250MiB，末尾空闲pool173.574/174.812MiB。分配器与自然idle检查原样保留，估算不与RSS相加。

采用必要列投影作为局部修复；整体资源仍Partial，整合/发布HOLD。窄表复制已由直接入口与结果对账证明，单个配对窗口的全局RSS差异仍不能认定为稳定OOM或读取驻留收益。读取后增长、原生/默认镜像、overview64MiB、长期/并发和生产OOM继续OPEN；本轮无新full8、CI、浏览器或生产请求。候选最高点在67,881×55专辑表发行日期回填的merge入口（_build_entity_frames第273行），另有96,301×51专辑时长表及艺人/事件表同时存活；此点早于首个_skip_storm，不能把全局6.578MiB差异全部归因于本轮代码。下一先核对该回填合并是否需要整表复制、其键唯一性和源/返回表所有权，再决定最小候选。读取两侧最高点仍在艺人Top albums的album project聚合，读取后增长69.969→65.828MiB，驻留未收口。

原始证据`output/oom-skip-storm-projection-20261015/`，独立恢复入口`~/.codex/archives/spotifystats-delivery/oom-skip-storm-projection-20261015/`，保留冻结源码、当前19文件、独立补丁、全部检查日志、90组旧函数对账、两套runtime、完整响应/事实/strict、9次assign各一套、阶段及最高采样证据。归档校验CRC、源码/协调文档、双方9响应、六事实与直接列宽证明后，仅清理本轮两个已退出容器，保留镜像、输出和正式来源，实际结果见独立收据。未暂存、提交、推送或部署，main仅更新协调文档。

## 专辑发行日期以两列键查询代替整表合并

原记录：`2026-10-15-oom-album-release-lookup.md`。


**处置：保留本地最小候选；源表与统计结果一致，整体资源仍 Partial，整合/发布 HOLD。**

### 先核对键与所有权

`_load_reliable_album_release_dates`先按原始`(album_name, artist_name)`元组归并证据，再对每个键最多输出一条可信精确日：相同键的重复元数据合并，冲突或无精确日的证据不发布；不同艺人同名专辑保留各自身份。左侧是播放事件，允许重复；右侧必须唯一。隔离七库来源含94,760 plays，实际加载4条可靠日期，重复键0、空键0；内存SQLite测试另覆盖重复本地专辑、同名不同艺人、NULL键、冲突日和仅年份，结果键仍唯一。

`_build_records_album_frame`的成功路径返回owned merge结果，回退路径返回copy；当前函数拥有该专辑投影，原事件表与时长源只读。原发行日期全宽merge和drop又产生新表，既复制无关字段，也重置索引、清空attrs。非空日期回填分支的attrs清除会影响`records_duration_frame`如何读取时长，不能在性能修复中改掉这一既有行为。

### 最小修复与正确性

仅修改研发树`backend/services/analysis_records_service.py`：用专辑名、艺人名两列做窄表left merge，并以many_to_one验证右键；随后在已独立持有的album_frame回填发行日。保留原RangeIndex、列轴名称和清空attrs的合同，仍优先使用项目精确发行日；查询临时表在歌曲投影前释放。完整字段、dtype、行序、缺失值与时长消费方式保持。原事件/时长/lookup表不变，主返回表独立；此前另外18个候选文件逐字节不变，当前20文件仅本地未提交。没有改日期证据规则、分配器、缓存预算或回收策略。

411项唯一相关测试通过，含19项新增，覆盖L1/L2/L3、匹配/无匹配/空日期表、NULL键、重复具名索引/列轴、源表与lookup不变、结果独立，以及窄表输入和查询临时表提前失活。冻结旧函数运行同批测试，3个全宽merge检查按预期失败，16个统计/元数据/加载器对照通过。

冻结旧builder完整对账231组：3层级×11种正常/异常/空表/范围场景×7种lookup和元数据形态，693张主表与693张时长消费表schema、dtype、索引、行序一致，attrs键/时长附件存在性保持，源事件、时长及lookup每组不变。包括nullable键、年度裸时长附件和已有nullable逻辑ID，项目精确日优先、None/NaN语义不变。Ruff、format、项目mypy hook和diff check通过；原始检查日志保留。

### 同源 Linux 对照

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

### 直接键、列宽与所有权证据

双方各3次发行日期回填的右键均无重复，输入和返回行数不变，完整输出列序相同；候选返回专辑表与helper的owned投影是同一对象，使用weakref确认，未持有完整表强引用。

| 调用 | 行数 | merge输入列数 基线→候选 | merge输出列数 基线→候选 | 返回表复用owned投影 基线/候选 |
| --- | ---: | ---: | ---: | --- |
| 1 | 67881 | 55→2 | 56→3 | False/True |
| 2 | 125 | 55→2 | 56→3 | False/True |
| 3 | 7543 | 55→2 | 56→3 | False/True |

双方输出仍为RangeIndex、attrs为空。首个67,881行merge边界RSS增量24.613→1.559MiB、耗时74.418→33.805ms；125行边界耗时3.189→5.211ms，其余时序原样保留，不能据此宣称整条启动链加速。直接merge边界不包含之前的两列投影或之后的fill，其RSS/耗时不能作为完整函数峰值；键/所有权探针不读caller f_locals。此前快进assign仍为5/5/3列，三次封面入口工作表引用均为0。固定阶段与最高采样观测沿用浅层元数据，所有对象存储估算不与RSS相加。

基线启动最高采样栈`build_collaboration_facts → compute_discovery_records → compute_playback_records → _get_analysis_records_uncached`。捕获延迟0.012ms、耗时13.012ms，实际最大采样间隔0.934秒，短峰可能遗漏。启动等待132.106秒，ready进程CPU133.340秒；固定Records阶段观测额外0.347秒，3次merge与11个维护任务时序另有原始记录。

候选启动最高采样栈`_canonical_records_track_frame → _build_records_track_frame → _build_entity_frames → _get_analysis_records_uncached`。捕获延迟0.018ms、耗时1.408ms，实际最大采样间隔0.671秒，短峰可能遗漏。启动等待151.309秒，ready进程CPU150.110秒；固定Records阶段观测额外0.492秒，3次merge与11个维护任务时序另有原始记录。

### 守恒与处置

双方9份完整响应逐字节相同，三范围stats/Records六份事实相同；跨构建仅排除meta.generated_at，各自strict时钟保持。37原始表、保护事实、队列、发布与六sidecar在读取前后不变，8103 done/38历史failed和失败明细相同，无pending/running或新增失败。正式七库SHA不变，两窗实际exit0，无OOM或采样器错误，每侧只有原有11次维护回收；合法帧预算均4条、181.076MiB、roots/LRU owner相同，分配器与idle观测保留。

局部修复保留，整体资源仍Partial、整合/发布HOLD。启动等待132.106→151.309秒、ready进程CPU133.340→150.110秒，候选更高；三个Records任务进程CPU16.640/12.880/14.420→18.580/16.030/17.710秒。前置未改动Billboard任务也由17.540→18.180秒，其他任务同样有波动。单对照尚未分离运行波动与回归，不能宣称加速或通过CPU准入。窄表merge和复用owned返回已由直接证据确认，单个配对窗口的全局RSS差异不能替代稳定OOM或读取驻留验证。读取后增长、原生/默认镜像、overview64MiB、长期/并发和生产OOM继续OPEN；本轮无新full8、CI、浏览器或生产请求。本轮启动最高点基线位于合作事实构建，候选位于歌曲时长canonical merge；不能将不同栈的2.445MiB差异全部判为本次修复收益。读取最高点两侧仍为艺人Top albums的album project聚合。读取增长虽79.043→64.336MiB，但ready已高12.656MiB、最终仅低2.051MiB，驻留未证稳定改善。ready及末尾pymalloc arena基线均380.750MiB、候选均393.750MiB，末尾空闲pool170.539/182.402MiB，这些不与RSS相加。下一先核对歌曲时长merge峰点仍存活的duration/投影owner及最后消费点，并定位启动CPU增量，再选择后续修复。

原始证据`output/oom-album-release-lookup-20261015/`，独立恢复入口`~/.codex/archives/spotifystats-delivery/oom-album-release-lookup-20261015/`，保留冻结19文件、当前20文件、独立补丁、键与所有权审计、所有测试/旧函数对账、两套runtime、完整响应/六事实/strict、直接merge列宽/右键/weakref身份及阶段最高采样。归档校验CRC、源码/协调文档、双方9响应、六事实及所有权证明后，仅清理本轮两个已退出容器，镜像/原始输出/正式来源保留；实际结果见独立收据。未暂存、提交、推送或部署，main仅更新协调文档。

## 启动 CPU 归因与专辑时长最后消费点

原记录：`2026-10-15-oom-startup-cpu-duration-attribution.md`。


**处置：保留本地最小候选；无用引用消除与统计正确性通过。CPU 显著运行波动已证明，候选未复现同规模启动增量；稳定回归未证且未全排除。整体资源 Partial，整合/发布 HOLD。**

### 表所有权与最小修复

歌曲时长 canonical merge 的输入是仍需读取的事件/时长源表；merge 返回独立 owned 表，后续计算需要三张实体主表及其有效时长附件。源缓存与这些有效输出不能仅因出现在峰点就释放。

发现的额外持有者在较早的专辑发行日期处理中：`album_duration` 已交给 `album_frame.attrs`，局部变量仍持有它；`precision` Series 从专辑表派生，也通过 attrs 中的 `ListeningDurationFrameRef` 保留同一时长表。非空来源日期回填会按旧合同清除专辑 attrs，此后两者都无消费点，却一直活到歌曲时长 merge。仅释放 `album_duration` 不足以解决 Series 的引用。

研发树 `backend/services/analysis_records_service.py` 仅在 attach 后 `del album_duration`、日期解析后 `del precision`。无来源日期回填时，返回专辑表仍保有合法时长附件，不能提前回收；有回填时保留原 attrs 清除、日期优先级与统计消费方式。没有改源表、日期规则、merge 字段、缓存预算、分配器或 GC/trim 策略。此前另外 19 个候选文件字节不变，新增一个测试文件，当前共 21 文件仅本地未提交。

6 个新弱引用测试覆盖 L1/L2/L3 × 有/无来源日期回填。修复前 3 个滞留案例失败、3 个合法保活对照通过；修复后全部通过。合计 417 项相关测试通过。冻结上一轮 B builder 对账 231 组，693 张主表、693 张时长消费表的 schema、dtype、索引、行序与数值一致，源事件、时长和 lookup 不变，返回主表独立；Ruff、format、项目 mypy hook 通过。

### CPU 对照方法与范围

A 是日期窄表修复前的 19 文件版本，B 是上一轮 20 文件版本，C 是本轮 21 文件最小候选。同进程从上一轮 B 窗口正常退出后的七库制作封闭副本，直接重算真实 lifetime Records，使用实际默认参数；不走缓存命中。先 A/B/C 各预热一次，再按 A/B/C/C/B/A 计时各两次，记录 thread CPU、process CPU、wall 和实体/计算/封面阶段。九次完整结果仅排除 `meta.generated_at` 后完全相同，七库物理 SHA 保持；不读取调用帧 locals，不新增 GC/trim/clear。九次弱引用检查均证实 A/B 在歌曲入口仍保活，C 已释放无用专辑时长。

| 线程 CPU 秒 | A | B | C |
| --- | ---: | ---: | ---: |
| 第一次 | 18.973 | 18.664 | 18.956 |
| 第二次 | 20.745 | 21.570 | 21.650 |
| 平均 | 19.859 | 20.117 | 20.303 |
| 实体构建两次 | 5.193 / 5.957 | 5.082 / 6.022 | 5.257 / 5.173 |
| 后续计算两次 | 7.236 / 7.912 | 7.231 / 8.332 | 7.300 / 9.867 |

B 对 A 的平均差 0.258 秒（约 1.3%），C 对 B 差 0.186 秒（约 0.9%）；同版本两次差 1.772/2.906/2.694 秒。B/C 专辑结果的内部 block 为 12，A 为 8，均 56 列；布局确有变化，但本组没有复现对应的大幅实体或后续计算 CPU 增量。这个固定 lifetime 参数、各两次计时只能用于有界归因，不能证明所有范围或原生运行无回归，也不能把所有波动具体归于某个操作系统因素。

独立启动使用同一正式七库来源（94,760 plays）各制作全新副本，运行顺序 B→A→C；与上一轮 A→B 使用逐字节相同 probe。每窗自然完成 11 个维护任务，再执行相同 9 次只读 GET，保留全部响应、六份 stats/Records 事实及 strict 守恒。三侧各 518 份 Python 源码和冻结构建上下文匹配；Python/glibc/依赖和启动前 mmap 阈值一致，无源码覆盖。所有运行均为 ARM Linux 引擎的 amd64 仿真，network none、只读 root、无端口、4GiB 容器/3GiB RSS 守卫、启动 600 秒/总 900 秒上限；不替代原生或默认 Python 基镜像验证。

### 独立启动 CPU 结论

| 窗口顺序 | 版本 | ready 进程 CPU 秒 | ready 等待秒 |
| --- | --- | ---: | ---: |
| 上一轮 1 | A | 133.340 | 132.106 |
| 上一轮 2 | B | 150.110 | 151.309 |
| 本轮 1 | B | 196.170 | 200.035 |
| 本轮 2 | A | 138.440 | 138.523 |
| 本轮 3 | C | 134.050 | 134.946 |

1. 同一 B 镜像、七库来源和 probe 的两次启动相差 46.060 秒，超过上一轮 A/B 的 16.770 秒差。显著运行波动已经得到直接证明；本轮所有维护任务顺序一致、观测区间无重叠，三侧均 11 个任务，没有多跑任务解释差值。
2. 增量分布在实体构建、后续计算、封面、艺人排名和音乐档案等阶段。比如 B 两次的 lifetime 计算 8.640→15.400 秒、短范围封面 1.180→2.760 秒；未改动的音乐档案任务 4.100→10.120 秒。三侧 startup 最高采样捕获累计仅 0.203/0.161/0.144 秒，阶段观测另有记录，不能解释数十秒差。没有证据把波动进一步单独归于主机频率、调度、仿真或分配器，不能编造单一根因。
3. B 在两对独立启动中均高于 A，仍是应保留的候选相关信号。固定 lifetime 同进程测试没有复现相同量级；C 保留窄表和 12 块布局，完整启动 CPU 为 134.050 秒，接近 A 的 138.440 秒，三范围实体/计算/封面也回到接近 A 的水平。因此“日期窄表布局必然引入约 17 秒 CPU 回归”不成立，但本轮不是所有参数和原生环境的无回归证明，也不能把 B→C 的 62.120 秒全算成两次 del 的加速收益。

| 本轮三范围阶段 CPU 秒 | A | B | C |
| --- | --- | --- | --- |
| lifetime 实体 / 计算 / 封面 | 6.250 / 7.970 / 1.170 | 7.210 / 15.400 / 1.390 | 5.940 / 7.590 / 1.190 |
| last_4_weeks 实体 / 计算 / 封面 | 5.420 / 0.780 / 1.150 | 7.640 / 1.030 / 2.760 | 5.290 / 0.740 / 0.980 |
| last_6_months 实体 / 计算 / 封面 | 5.500 / 2.030 / 1.100 | 8.470 / 3.790 / 1.740 | 5.420 / 1.920 / 1.100 |

上表是相同 probe 边界内的进程 CPU 差值，包含该区间观测；同进程表使用 thread CPU，口径不可直接混用。CPU 的局部诊断已完成，稳定性能准入仍保留边界，不据此发布或关闭 OOM。

### 资源、最高点与读取驻留

| MiB | A | B | C |
| --- | ---: | ---: | ---: |
| 启动最高采样 | 1009.598 | 1006.820 | 991.102 |
| startup ready | 550.488 | 560.500 | 541.582 |
| 读取最高采样 | 671.406 | 682.223 | 664.172 |
| 最终 idle | 615.891 | 627.195 | 611.340 |
| ready 至末尾增长 | 65.402 | 66.695 | 69.758 |
| 最终帧预算 | 181.076 | 181.076 | 181.076 |

C 的启动最高采样比 A/B 低 18.496/15.719 MiB，最终比 A/B 低 4.551/15.855 MiB；只有各一窗，最高点也不在同一栈，不认定这些差值全部是因果收益。C 的读取后增长反而比 A/B 高 4.355/3.062 MiB，长期驻留没有收口。三侧合法预算都是 4 条、181.076 MiB、相同 roots/LRU owner，预算不等于 RSS。

A 最高采样位于合作 facts 构建 line187，B 位于歌曲时长 canonical merge line82，C 位于合作 facts 的署名 merge line163。三者最高采样与捕获记录时间/RSS 同点且未截断；捕获延迟约 0.013/0.019/0.015ms，捕获耗时约 20.093/1.827/12.150ms。实际最大采样间隔分别 1.089/2.821/1.070 秒，短峰可能漏过。完整 probe 的帧 locals 观察会同步 Python 的 locals 缓存，可能改变引用释放时机；因此歌曲入口时长表已失活的直接证据来自无帧窥探的 6 项单测和 9 次真实数据弱引用检查，不能用不同栈的全局 RSS 差替代所有权证明。

C 最高点仍有合法的事件、时长、三实体表及附件；合作 selected/tracks/albums 分别 6518 行、49/53/57 列，署名右侧 8854 行 5 列。它们成为后续核对的具体范围，本轮不继续改动。三侧读取最高点均为艺人 Top albums 的 album project 聚合。ready/末尾 pymalloc arena 分别保持 A387.750、B397.250、C379.000 MiB；末尾空闲 pools177.570/185.344/169.340 MiB，已保存分配器细目，不与 RSS 相加，也不新增回收试验。

### 守恒、交付边界与恢复

三侧各 9 份完整响应逐字节相同，三范围 stats/Records 六份事实相同；跨构建仅排除 `meta.generated_at`，各自 strict 时钟完整。37 原始表、保护事实、队列、发布及六 sidecar 读取前后不变，8103 done/38 历史 failed 明细一致，无新增失败或 pending/running。正式七库 SHA 不变，微对照副本七库 SHA 也不变；四个 owned 容器均实际 exit0，无 OOM、守卫或采样器错误。每个完整窗口只有原有 11 次维护回收，三次封面入口工作表局部引用及主输入弱引用为 0；此前 skip assign5/5/3 列和日期窄 merge2→3 列、唯一右键、owned 返回复用均保持。

本轮仅研发 service 的两处最后消费点释放和一个测试文件，main 只维护协调文档。未暂存、提交、推送、部署、访问生产或新增 full8/CI/浏览器验收。正确性与有界 CPU/资源证据通过不等于原生性能、默认基镜像、overview64MiB、长期/并发平台期或生产 OOM 关闭；整体继续 Partial/HOLD。下一候选范围是合作 facts 的署名 merge、selected/tracks/albums 与时长投影的必要字段和最后消费点，先核对消费者再缩减，保持完整事实与返回所有权。

镜像：

- image-base：`sha256:7d5b3c414b4c68e90874c8fd1bc2894423941cc4c2933e1108a5ff4a3d19d7e7`
- image-previous：`sha256:1e6afe8450906b26c0e8bee23808c7fa44e296239f50335a380a1456caf91dfb`
- image-candidate：`sha256:42de4914b84ae76148f95a6d4fa9d4a690fed465bee2802d1d738e5f91b905ab`

原始证据 `output/oom-startup-cpu-duration-20261015/`；独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-startup-cpu-duration-20261015/`。归档保存 B 的冻结 20 文件、C 的 21 文件及补丁、21 份协调文档快照、3 套全启动 runtime 和 1 套同进程 runtime、全部测试/反例、231 组对账、CPU 阶段/同版本差值、27 份响应、六事实和 strict 证明。CRC、源码/协调文档字节与响应哈希验证后，仅删除本轮 1 个微对照及 3 个完整窗口的已退出 owned 容器，保留镜像、原始输出和正式来源；实际归档/清理收据单独保存。

## 合作署名窄表展开与累计候选收益审阅

原记录：`2026-10-15-oom-collaboration-credit-expansion-and-cumulative-review.md`。

> 2026-10-16后续补证：已确认逐样本Python字典探针会分散占用arena。本文保留原数值和原始验证，但RSS/空闲pool及累计资源差值包含观测自干扰，不能直接作无探针服务驻留或稳定业务因果收益。统计正确性/读取守恒结论保留；见[启动arena归因与探针校正](2026-10-16-oom-residency-and-arena-research.md#启动-arena-碎片对象持有者与探针自干扰归因)。

核验日期：2026-10-15。SS-2026-10-08-001，关联 SS-2026-10-09-001。研发基线 `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06`；仅隔离副本验证，不提交、推送或部署。

### 必要字段、去重键和所有权

生产代码中 `CollaborationFacts` 由 discovery 的三个合作榜消费。歌曲榜读取规范曲目身份、名称、署名和逻辑事件；专辑榜还读取项目身份、来源专辑身份及艺人名作回退；艺人榜按有效署名后的 artist_id 聚合。另有无连接预载路径复用 facts.artists，需要 representative_track_id 等身份字段。因此本轮保持七张返回表的完整 schema、dtype、列序和行索引，不把它们直接缩成榜单当前需要的几列。

| 步骤 | 必要字段/规则 | 最后消费点 |
| --- | --- | --- |
| 署名右表 | _credit_track_id、artist_id、artist_name、role、_role_order；复合键 (_credit_track_id, artist_id) 唯一，同曲多艺人是合法展开 | 艺人事件/时长展开及曲目 artist_names |
| 艺人事件 merge | _credit_track_id、_logical_event_id、临时行位置 | 用 (_logical_event_id, artist_id) 稳定去重后，按位置取独立完整行 |
| 艺人时长 merge | _credit_track_id、临时行位置 | 按展开结果取独立完整行；这里不新增时长去重 |
| 时长去重 | entity_id 加原 _DURATION_DEDUPE_COLUMNS 全九项，包括逻辑事件、play_id、时间戳、切片/区间起止及毫秒 | aggregate_collaboration，保持原规则，不能只用 play_id |
| frames、循环变量 frame | 只用于三来源时长解析和六来源署名 ID 收集 | requested 收集结束即可释放局部引用 |
| durations 列表 | 三套时长选择 | artist_duration_source 选择完成后释放；源参数或返回附件仍合法持有的表继续存活 |
| artist_duration_source | 艺人时长署名展开 | 展开结束后释放；无附件时与 selected 的合法共享继续由返回 events 保活 |

`_expand_artist_credits` 先对窄键 merge/事件去重，再通过 `take` 取完整匹配行，移除旧艺人字段并以原类型添加有效署名字段。它保留旧 merge 的空键匹配、重复事件稳定选择、索引空洞、列轴名称和 attrs 合同；临时位置名避开已有元数据。额外元数据与署名列重名时沿用原 merge，保留 pandas 的后缀/异常行为。源表只读，结果写入不影响源表。

初版测试发现 `take` 共享列索引元数据，直接设置 columns.name 会改到源表；已改为生成独立列索引。冻结旧实现又发现双空表时 merge 的署名键 dtype 可来自右表；已从窄 merge 结果回填键类型。原始失败和初版完整测试的主动中断均保留，最终版本重新验证。

### 正确性验证

新增 24 项覆盖完整表匹配、空表/双空表、nullable 和 NULL 键、重复索引/逻辑事件、列轴名称、元数据冲突、临时列名冲突、源表/attrs 不变、返回结果独立，以及新时长表释放与借用源表继续保活。冻结本轮前 builder 执行复制/时长失活检查，2 个旧问题失败、1 个合法借用对照通过。

最终 441 项相关测试通过。冻结旧 builder 对账 52 次：48 次七表完整事实与事件总数一致、4 次既有异常类型和消息一致；144 份三合作榜与 26 次直接聚合一致，包含无连接预载、L3 合作版本、重复项目 membership、同名异人和独立时长切片。上述 pytest 子集与 441 项有重叠，不累加为独立用例。

累计复核另将未修改 HEAD 的实体 builder 与最终版本对账 231 组：693 张主表和 693 张时长消费表的 schema、dtype、索引、行序和数值一致，源事件、时长、日期 lookup 和 attrs 不变；覆盖三层级、异常回退、空输入、范围及日期证据形态。

后端 unit/contract 完整选择实际 exit1：3634 passed、2 skipped、2 failed、834 deselected，耗时343.35秒。两项失败均为 fullstack 脚本测试读取不到 summary；同一测试、fullstack/lock/storage_guard 脚本与 HEAD 字节相同，在独立 HEAD 副本复现相同两项失败。直接守卫收据确认 stop_reason=insufficient_free_space，本机可用约7.8–8.1GiB低于12GiB，脚本尚未进入测试目标逻辑。保留原失败与 HEAD 对照，不称完整后端绿灯，也不改存储门槛。Ruff、format 与项目 mypy hook通过。

### 同源 Linux 对照设计

HEAD 为研发树已提交代码，使用原 Dockerfile 默认分配器；Previous 为本轮前 21 文件候选；Final 为本轮 22 文件候选。三者使用同一封存 runtime、依赖与源码构建流程，各 518 份 Python 源码和冻结构建上下文匹配；Previous→Final 仅 records_collaboration.py 改变，其他 20 个既有候选文件字节不变。HEAD→Final 包含五个 Python 文件与既有 MALLOC_MMAP_THRESHOLD_=131072 设置，其累计差值不能归为单个优化收益。

每侧从同一正式七库、94,760 plays 制作全新隔离副本，使用逐字节相同且兼容 HEAD 的 probe，按 HEAD→Previous→Final 串行运行。每窗自然完成启动维护，再执行 9 次相同只读 GET：Midnights L3 fixed light/rank 六次和 Taylor Swift L2 dynamic rank 三次。保留完整响应、六份 stats/Records 事实、读取守恒、最高采样同点栈及各维护任务 CPU。署名 merge 另记录数值元数据，不读取调用者 locals，也不持有业务表强引用。

运行环境仍是 ARM Linux 引擎上的 amd64 仿真，network none、无端口、只读 root、4GiB 容器与 3GiB RSS 守卫、启动 600 秒/总 900 秒上限保持；不新增 GC/trim/cache clear，也不调整预算。本轮是固定来源的有界对照，不替代默认 Python 基镜像、原生 Linux 或生产验收。

### 直接署名展开证据

三范围共 6 次署名 merge：右侧 (_credit_track_id, artist_id) 重复键始终为0，展开行数和七张完整返回表的行数/列序与独立对象身份三侧一致。事件在取完整行前按原两键去重；时长保留全部切片，再由原聚合规则去重。

| 调用 | 输入行数 | 展开行数 | merge 输入列数 HEAD / Previous / Final | merge 输出列数 HEAD / Previous / Final |
| --- | ---: | ---: | --- | --- |
| 1 | 6518 | 15178 | 47 / 47 / 3 | 51 / 51 / 7 |
| 2 | 9831 | 22913 | 44 / 44 / 2 | 48 / 48 / 6 |
| 3 | 12 | 28 | 47 / 47 / 3 | 51 / 51 / 7 |
| 4 | 15 | 39 | 44 / 44 / 2 | 48 / 48 / 6 |
| 5 | 655 | 1493 | 47 / 47 / 3 | 51 / 51 / 7 |
| 6 | 858 | 1945 | 44 / 44 / 2 | 48 / 48 / 6 |

这些是 merge 边界，不包含随后按行位置取完整表的成本，不能当作整个 helper 的峰值证据。最后消费点释放由无帧窥探的弱引用测试确认；完整资源 probe 的浅层帧观察可能同步 Python locals 缓存并改变释放时机。附属的旧日期 merge 探针被新外层 wrapper 隔开，三侧直接 caller 选择均未命中，已明确标记 NOT_OBSERVED；没有为它加跑窗口。日期回填正确性由当前单测、HEAD实体对照及上一轮直接证据支持，本轮 owned 返回身份观察仍保留。

### 本轮增量与累计资源收益

| 指标 | HEAD | Previous21 | Final22 |
| --- | ---: | ---: | ---: |
| 启动最高采样 MiB | 1303.668 | 998.238 | 995.094 |
| ready RSS MiB | 756.508 | 534.516 | 542.609 |
| 读取最高采样 MiB | 964.199 | 661.367 | 663.133 |
| 最终 idle RSS MiB | 893.277 | 604.430 | 607.395 |
| ready 至末尾增长 MiB | 136.770 | 69.914 | 64.785 |
| 末尾帧预算估算 MiB | 202.910 | 181.076 | 181.076 |
| ready 进程 CPU 秒 | 130.840 | 131.160 | 131.300 |
| ready 等待秒 | 130.675 | 131.993 | 130.388 |

固定探针下九次 GET 累计后端计时 HEAD/Previous/Final 为8.744/7.948/7.945秒，首次艺人为3.592/2.903/2.915秒，本窗口未观察到新增读取时延成本；包含探针开销且仅各一窗，不替代原生或浏览器延迟门禁。

**本轮增量**：Previous→Final 启动最高采样低3.145MiB，读取峰和末尾反而高1.766/2.965MiB。ready 已高8.094MiB，因此增长量低5.129MiB不能解读为末尾驻留改善。本轮消除宽表署名 join 的直接证据成立，额外全局资源收益未证明。

**累计收益**：HEAD→Final 启动峰低308.574MiB（23.7%）、读取峰低301.066MiB、末尾低285.883MiB（32.0%），读取增长由136.770降至64.785MiB。本轮CPU130.840/131.160/131.300秒，没有同规模增量；仅各一窗，不称稳定加速或稳定OOM准入。累计窗口同时包含既有分配器设置与代码优化，不能将308.574MiB拆分分配给各个局部修复，也不能把历次局部差值相加。

HEAD 和 Final 的启动最高采样均位于时间模式 `_new_year_eve`，Previous 位于实体专辑构建；当前不继续追逐移动峰点追加微优化。三侧读取最高点仍为艺人 Top albums 的 album project 聚合。最高采样和捕获时间/RSS同点、均未截断；完整栈、帧别名、观测成本与采样间隔原样保存。

| 最高采样观测 | HEAD | Previous21 | Final22 |
| --- | ---: | ---: | ---: |
| 启动捕获延迟 ms | 0.018 | 0.019 | 0.016 |
| 启动捕获耗时 ms | 1.240 | 1.246 | 2.041 |
| 最大采样间隔 秒 | 0.921 | 0.924 | 0.518 |

短峰仍可能漏过，最高采样不是连续的真实高水位。所有对象/块存储与帧预算估算都不与RSS相加。

### 读取增长的实际含义

三侧 ready 帧缓存均为空，读取后均4条；末尾估算202.910/181.076/181.076MiB，预算上限均384MiB没有修改。因此 ready 至末尾增长同时包含首次读取形成的合法缓存，不能全部称为泄漏；缓存估算也不能直接抵扣RSS增长。

| 艺人首次完成 / 第二次 / 第三次 / 最终idle RSS MiB | 数值 |
| --- | --- |
| HEAD | 893.266 / 893.273 / 893.277 / 893.277 |
| Previous21 | 604.406 / 604.418 / 604.422 / 604.430 |
| Final22 | 607.379 / 607.379 / 607.395 / 607.395 |

Final 的首次艺人完成后至第三次仅增加约0.016MiB；这说明本窗口的相同热请求没有持续显著增长，尚不足以验证长期或多实体/并发平台期。ready的同步观察自身使RSS增加约5MiB，读取增量也包含观测影响。下一步应核对新增缓存的实际持有者、复用/淘汰边界和空闲分配器驻留，判断其成本是否适合目标机器，再验证有限多实体序列；不直接清缓存或按预算数猜测泄漏。

三侧 pymalloc arena/pool、root/LRU owner和idle检查点均保留；其估算与缓存预算不能相加为RSS。每窗只有原11次维护回收，没有新增回收试验。27份完整响应逐字节相同，六份业务事实仅跨构建排除meta.generated_at；各自严格读取前后仍保留时钟。37原始表、保护事实、队列、发布和六sidecar不变，8103 done/38历史failed及错误明细一致，pending/running为0、无新增失败；正式七库SHA不变，三容器实际exit0、无OOM/守卫/采样器错误。

### 累计候选逐项处置

| 范围 | 本轮审阅依据 | 处置 |
| --- | --- | --- |
| Dockerfile mmap 阈值 | 既有 Linux 分配器试验与本轮累计窗口；未改业务事实或预算 | 保留本地候选，原生/默认基镜像仍待验；不单独宣称其 RSS 收益 |
| Records 实体构建与工作表生命周期 | 原返回表所有权、异常回退、完整字段、日期/时长 attrs 合同；231 组 HEAD 对照 | 保留；源表只读，仍需的返回附件继续保活 |
| Track chart 与 Top250 前置投影 | 统计双轨、时间边界、规范身份；相关消费测试与完整响应对照 | 保留；字段为实际消费集合 |
| 已发布艺人范围 SQL 与专辑中间表 | 保留重建身份、区间、近期播放展示及项目 membership；省去无消费者的全历史副本 | 保留；不扩展到其他加载入口 |
| 合作 ID 收集、select、聚合与本轮署名展开 | 有效署名、事件/时长去重键和完整返回表；52 次旧 builder 与真实事实对照 | 保留；额外元数据冲突保持旧路径 |
| _skip_storm 必要列投影 | 同索引 reason_end 计算、分组键、play_id 与 ms_played；既有完整旧函数对照与当前专项 | 保留局部简化；不把其小幅窗口差值单独当成稳定收益 |

**处置：22文件保留本地，累计审阅完成；整体资源仍Partial，整合/发布HOLD。** 累计有界收益支持保留当前候选，但本轮新增helper只有直接复制/所有权收益证据，不能把小幅全局差异包装成独立OOM修复。未发现需要在本轮撤回的统计或所有权回归；初版列轴和空表dtype问题已修正并以最终版本验证。完整后端仍有2项与HEAD一致的磁盘门槛失败，不能标绿。

不再无界追加启动微优化。下一范围是读取新增缓存owner、分配器驻留和有限多实体平台期；本机恢复到12GiB存储前置后再补两项门禁，原生/默认Python基镜像、overview64MiB、长期/并发及生产OOM仍OPEN。本轮未新运行full8、CI、浏览器或生产请求，未暂存、提交、推送、部署或将业务改动整合到main；main仅维护协调文档。

原始证据 `output/oom-collaboration-merge-review-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-merge-review-20261015/`。保存21文件冻结源、HEAD六源文件、22文件最终源码/完整和增量补丁、22份协调文档快照、三套runtime、全部最终/初版失败/中断与HEAD环境对照、完整响应/事实/strict、窄表列宽/返回所有权、CPU/分配器与采样记录。归档验证CRC、源码/文档字节和27份响应后，仅删除本轮三个已退出owned容器；镜像、原始输出和正式来源保留，清理与最终三工作区状态另存收据。

镜像：

- image-base：`sha256:9047e7ab90b018b5aae52286fbff29b476aaeaa6cecc21f36c9dffa038b25797`
- image-previous：`sha256:42de4914b84ae76148f95a6d4fa9d4a690fed465bee2802d1d738e5f91b905ab`
- image-candidate：`sha256:37903f982dd3f9913002cc3e63e3c60b0f557ce4a4f79400309a8174f57fac57`
