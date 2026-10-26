# OOM 剩余启动峰值与读取增长：隔离归因和最小候选

2026-10-14；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。唯一研发分支 `codex/album-rank-cost`，基线 `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06`；线上仍为此前发布的 b126。本轮已获本地最小修复与隔离验证授权，暂不部署；未新增 commit/push、生产请求、生产配置或数据变更。

**本地候选 READY / 资源 Partial。** 仅修改研发树 Dockerfile 的 backend stage，设置 `MALLOC_MMAP_THRESHOLD_=131072`，在进程初始化前固定 glibc mmap 阈值。启动采样峰值、读取峰值、末尾驻留与读取增量均有同源观察收益；9份完整响应和六份统计/记录事实一致，严格读取守恒通过。测试环境仍为 ARM Linux 引擎运行 amd64 仿真镜像，不能据此关闭原生CPU/时延、逐请求64MiB、整体构建峰值或生产OOM。

## 归因结果

此前[生产首次窗口](2026-10-14-native-trim-maintenance-delivery.md#维护完成原生回收生产交付与首次验收)显示，维护结束 trim 后起点RSS低，但启动历史高水位约1.19GiB、读取又增加约352MiB。此次沿实际 warmup=0 的维护队列和实体 stats 链追踪，没有复跑生产窗口。

1. 启动最高采样点邻近 analysis snapshot maintenance；峰值前栈中的 `_build_entity_frames` 同时持有事件、时长、track/album结果及专辑归并中间表，数万行、约45–56列。宽表和切片的瞬时持有是工作集的一部分，维护结束回收不能降低构建时的全部活对象峰值。
2. 自然启动就绪后帧预算接近0；两条读取链使预算增至202.910MiB。同一键各重复三轮后没有持续增长，只支持这个有限序列内的平台观察，不说明全站长期稳定。
3. 基线结束时 glibc arena约612MiB，其中空闲约518.526MiB；Python arena容量362.75MiB、已分配块约208.032MiB。RSS不能全部当作活缓存或泄漏。固定阈值后，glibc空闲约54.355MiB，Python已分配块仍约208.058MiB、帧预算完全相同，支持原生大块临时分配保留是可减少部分。

[GNU libc 手册](https://sourceware.org/glibc/manual/latest/html_node/Malloc-Tunable-Parameters.html)说明，mmap threshold默认128KiB并会动态调整；显式设置会关闭这一动态调整，大于阈值的分配可在释放时归还系统。此候选固定文档默认值，未同时改变arena数、trim阈值、GC、缓存容量或GET调度。

## 四个有效窗口及候选取舍

采用已有历史封存的关闭七文件输入，每个变体使用新的自有副本；不是本轮最新生产数据备份，不宣称精确生产启动现场等价。排名清单经规范validate/install/verify绑定各自本地lineage；禁止联网、无端口、只读根目录，容器4GiB/2CPU、进程3GiB守卫、每窗900秒。一次正常启动，专辑L3 fixed含/不含排名各三轮，艺人L2 dynamic含排名三轮，共9次公开只读ASGI GET。年度cache miss不再充当读取增长样本。

所有有效变体均正常完成相同维护范围并退出0、OOMKilled=false，历史38条failed保持；四个strict read windows通过。原始七文件备份SHA保持。

| MiB | 基线 | 两文件代码试验 | arena=2试验 | 固定mmap128KiB |
| --- | ---: | ---: | ---: | ---: |
| 启动采样峰值 | 1316.258 | 1331.473 | 1294.336 | 1200.273 |
| 就绪RSS | 731.148 | 623.449 | 861.527 | 532.504 |
| 读取采样峰值 | 928.180 | 796.609 | 1070.332 | 719.895 |
| 最终idle RSS | 865.332 | 758.477 | 1014.988 | 610.551 |
| 就绪→最终增长 | 134.184 | 135.027 | 153.461 | 78.047 |
| 最终合法帧预算 | 202.910 | 202.910 | 202.910 | 202.910 |

选中设置较基线：启动采样峰低115.984MiB、读取峰低208.285MiB、末尾低254.781MiB、增量少56.137MiB。未通过清空缓存或少返回事实获得收益。

两文件代码试验消除了六处重复表复制，并在Records展开艺人前释放专辑中间表；77既有专项、5新增所有权用例与124消费回归通过，原基线所有权用例1 fail/4 pass而候选5 pass。完整响应和事实一致，但启动峰高15MiB、读取增量基本不变；保存补丁/测试后精确恢复该两文件，未采用。arena=2仅降低启动峰约22MiB，却提高末尾和增长，未采用。不是将这些验证合计冒充最终ENV候选的代码测试。

选中方案仅一文件两行：

```dockerfile
# Keep large temporary arrays mmap-backed rather than retained in glibc arenas.
ENV MALLOC_MMAP_THRESHOLD_=131072
```

实际隔离容器Config.Env已核对131072在Python初始化前生效；基线backend源码不变，最终合法帧预算相同。研发Dockerfile值与测试值一致，包装/生产部署静态合同12项通过。当前没有构建新目标镜像，已测的是固定已有镜像+精确backend源覆盖+启动ENV，后续镜像准入与发布不由本轮替代。

## 正确性、采样与原失败

四变体各9次200完整body逐字节一致。每侧最新lifetime/last4weeks/last6months的analysis stats及records共六份发布业务事实完整一致；只在跨构建业务oracle中排除`meta.generated_at`，原read-window严格比较未放宽任何时钟。源表、治理、队列、发布及六sidecar在读取窗口内保持。

最大实际采样间隔：基线654ms、代码758ms、选中932ms，仿真调度与现有后台队列顺序会影响绝对峰/CPU。报告使用“采样峰值”，没有新增热重跑选择较好结果或宣称每请求64MiB达标。

首轮control的采样线程因变量清理UnboundLocalError中断，保留原容器/日志并只停止该自有容器，不采用其峰值；修正探针后新control-v2从原七文件创建。另保留：基线插件首次缺future annotations、一次不存在的测试路径、system Python缺dotenv、跨构建oracle未按publication_id排序而误选旧日期LKG、类型检查导入模式导致的差异。修正工具只重分析固定事实或执行所需测试，没有改统计oracle值。直接mypy原候选/基线各59个既有错误，错误集合相同；项目mypy hook通过。代码试验新增测试import排序已修正，最终Ruff/format通过。

## 状态、证据与下一步

唯一研发树保留未提交Dockerfile候选；业务源码恢复dc1，试验与测试独立保存，共享文档仅main维护。未整合产品到main、未提交/推送/部署，不改变线上b126。

恢复入口：`oom-peak-growth-20261014`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。包含四有效窗及首轮失败的采样/阶段/原生分配器/弱引用/源码/输入副本/完整body/strict/容器收据、六事实oracle、选中Dockerfile补丁、未采用代码试验及测试、所有工具失败与修正、包装检查及协调文档快照。数据和payload不进入Git或镜像。当前原材料在研发树 ignored `output/oom-peak-growth-20261014`，长期恢复不依赖此路径；归档校验与自有容器清理结果独立保存。

本轮定位与最小候选验证已完成。整体资源合同仍OPEN：需要目标镜像核验、原生amd64 CPU/时延和并发资源准入，以及更广范围的逐请求预算/长期平台证据；启动活对象高水位仍约1.2GiB采样，不能由本次收益宣布生产OOM修复。不自动推进发布，也不重启/预暖/重跑现有生产窗口。
