# 艺人专辑子聚合：中间表投影与生命周期

核验日期：2026-10-15。SS-2026-10-08-001，关联 SS-2026-10-09-001。

## 结果与范围

**保留局部峰值候选，整体资源 Partial。** 冻结上轮艺人 SQL 投影等七文件候选，只收窄 owned album 子聚合并移除无效副本。120 项相关测试通过；同源两镜像各 9 次读取，完整响应逐字节相同、六份统计业务事实相同、strict read window 通过。首次艺人峰增量 99.199→69.098 MiB，本轮读取采样峰低 20.832 MiB；末尾 RSS 高 9.301 MiB，其差异大部分在艺人请求前已存在，驻留收益未证明。

研发树当前四个 tracked 修改、四个新测试，共八文件。未暂存、提交、推送、整合或部署。既有七文件除 entity_stats_service.py 必要增量外，其余六文件逐字节保持；共享文档仅在 main 更新。

## 定位与最小实现

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

## 正确性与封装

- 39 项专项：新增 12 组完整 artist payload（merge/dynamic × lifetime/last_4_weeks/custom）对账全宽子聚合，6 组拥有权/跨日/独立次数与时长/无 interval 兼容和临时对象生命周期验证；其余为既有艺人投影、rank context、独立时长趋势。源与发布文件未写入。
- 81 项消费回归：track/Top250、album published rank、artist identity、versus personal stats、有效署名。合计 120 个唯一测试；Ruff、format、mypy hook、diff check 通过。
- 初轮 6 个失败来自测试观察器把 DataFrame.copy 深拷贝的 attrs 哨兵当作原对象比较；改为保存原 attrs 浅映射后通过，原日志保留。另在独立测试进程恢复全宽投影，6 个前置宽度断言按预期失败；不计为业务结果差异。
- 同一封存缓存 runtime 替代命名 Python 基底，Dockerfile backend 阶段离线构建，无源码覆盖挂载。两镜像各 518 个 backend/scripts 源文件与冻结上下文一致；依赖、mmap ENV 相同，代理未进入 runtime ENV。

基线：`sha256:c4005c2c108f345ca4f0cec9ac2fea5e8fd6ab47f8009aaf61556a6a3ebefb05`。
候选：`sha256:facf443abafa76e0409ab424733b69d22b6458e5447512238ba1ee85d47e3c92`。

## 有界 Linux 对照

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

## 证据与剩余工作

研发原始输出：`output/oom-artist-album-20261015/`；独立恢复入口：`~/.codex/archives/spotifystats-delivery/oom-artist-album-20261015/`。保存冻结前七文件、最终八文件、album-only.patch、镜像/请求/浅栈/allocator/strict、测试和观察器原失败日志及协调文档快照。归档 CRC、源码/文档快照、两侧 9 body 与 six facts 校验后，仅按精确 ID 清理本轮两个已退出容器；结果以独立目录收据为准。保留镜像、输出及正式数据。

本次为 ARM Linux 引擎上的 amd64 仿真与封存缓存 runtime，属于局部资源证据。默认 Python 基镜像构建仍沿用此前 Partial，未重试网络。未跑新 full8/CI 或生产验收。默认 overview 64MiB、长期/更广并发、原生与生产 OOM 仍 OPEN；本轮统计冷请求不套用 overview 门槛。

剩余目标是外层目标时长切片（仍 33 列）、all/current 副本共存，以及启动维护后 Python arena 高驻留。下一阶段继续按 owner 与生命周期收窄；本轮局部峰值收益不构成整体 OOM 收口。
