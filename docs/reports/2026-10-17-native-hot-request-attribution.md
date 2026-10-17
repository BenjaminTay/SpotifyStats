# 原生热请求成本的有界归因

日期：2026-10-17。事项：`SS-2026-10-08-001`。**单次诊断与本次学校资源清理完成；第一轮最小业务候选已本地提交，正确性通过，新镜像原生资源仍待验，完整准入HOLD。** 未推送、部署或重新验收生产。原R2候选有效FAIL保持不变，见[学校准入报告](2026-10-17-school-native-resource-admission.md)。

## 诊断身份与事实

独立run `oom-school-20261017-r3hot-f4831d3c`，manifest canonical SHA `a8a9a01ba6c27f4e33faff1ccc35f14afb92398965f0fbee59aa1dd98371cf5e`，参照原S3 manifest `36a4e2b76dd6387af9d3b6395c1a45703a2b74efd6227173e54d14075e910e74`。使用同一实际c844候选镜像和冻结七库/ready，不挂业务源码。原三验收工具字节不变，独立诊断worker、controller、guard绑定精确哈希。

仍为学校共享宿主：Backend 1CPU/2GiB/swap0、UID1000:1000，独立helper最多1CPU/512MiB；同时最多各一个，宿主可用内存至少2GiB、磁盘至少12GiB、新增至多6GiB。新guard只允许唯一诊断ID，首次复制之前arm一次，copy、初rank、真实准备、含WAL正式rank、新冷进程、归档及运行副本回收沿同一1800秒clock，不能改起点。实耗734.634148秒，真实prepare及measure均正常退出、无失败/无效项，controller实际exit0。

固定14请求：显式warmup 2次；A重采样开启并行4次、B暂停重采样并行4次、C重采样开启串行4次。B先获得重采样暂停ACK和轻量安全检查ACK，保留原0.8B/宿主/OOM/磁盘/deadline保护；实际one调用为0、light检查45次。重采样有意暂停约2.66秒，原始最大gap2.730秒、扣除该有意区间后的最大gap0.409秒；B不声称有RSS/PSS轨迹。

14份实际正文（summary/overview各7）SHA均等于原R2对应完整正文；9个client批次实际exit0。准备及三个测量barrier的六成品、103历史任务、main inode相同，无测量重建；五barrier原37来源事实相同，读取strict守恒。离线分析器及独立只读审阅均通过。测量全进程采样RSS峰217767936字节、cgroup峰207745024字节，不能据此推断多实体或长期收益。

## 观测结果与解释

以下均为原`detail_service`服务计时，组内summary与overview各两次：

| 组 | summary（ms） | overview（ms） | Backend进程CPU（ms） | sampler线程CPU（ms） | 配额节流时间（ms） |
| --- | --- | --- | ---: | ---: | ---: |
| A：开重采样、并行 | 283.014 / 221.240 | 305.811 / 167.938 | 1130.139 | 463.308 | 516.682 |
| B：暂停重采样、并行 | 196.959 / 206.253 | 208.068 / 213.194 | 754.278 | 16.329 | 484.976 |
| C：开重采样、串行 | 71.662 / 80.639 | 73.455 / 68.784 | 1213.122 | 758.342 | 13.763 |

采样有明显CPU成本；但B仍超过原100ms目标，不能把失败全部归为观察者。C串行显著更快，A/B存在实际quota throttling，支持继续处理单核并发下的重复CPU工作；固定顺序的一次对照不能证明GIL、节流或sampler是唯一根因。组wall包含helper启动和等待，不能当成纯业务CPU；不从服务计时中扣除估计的工具成本。

请求内分段记录还表明：每次请求都构建两张1907项的完整artist identity map。C组两次map合计约16.96–18.45ms线程CPU，请求内published函数合计约67.60–74.57ms线程CPU；其fence阶段约26.8–35.1ms，公共summary阶段约39.7–43.8ms。源码核对确认同一SQLite事务内重复解析filter context、exact key、document及context row。数据支持在事务内复用这些已解析事实，没有证明新补丁已经达标。

## 第一轮最小候选与验收边界

唯一假设为“同请求、同事务内避免重复解析”。保留exact-ready、revision、context checksum和ledger checksum实际检查；只对实测track summary/overview链，将已解析的上下文传给私有summary内核，独立summary入口继续自行解析。artist map在同事务只构建一次，显式传给有效署名及primary解析；不引入跨请求缓存、全局锁或公开`validated=True`绕过参数，不改变别名和人工署名规则。

研发隔离树六文件候选已独立审阅并本地提交`729a0ed3f04431e881296b616fc4babe2e196774`（父`ede04ab8`）：四个业务文件、两个unit文件。127项定向unit（新增19例）、6项seed公开快照contract、四项提交hooks及diff检查通过。真实临时SQLite覆盖同事务解析次数、源库字节不变、返回对象独立、11种损坏/过期/revision拒绝、独立摘要兼容、别名和人工署名；只读Mapping可显式复用，未传时沿原解析入口。seed合同使用无lifespan的临时副本和进程内TestClient，不能替代真实七库或启动验收。

新实际候选镜像已从提交源码构建，基础digest保持原Python 3.9，540个镜像内源码/requirements文件逐项匹配，45项依赖、Python 3.9.25/glibc 2.41、无私密数据检查通过。运行ENV严格等于旧R0候选；相对R0前baseline仍保留既有`MALLOC_MMAP_THRESHOLD_=131072`差异，不能写成两版ENV完全一致。Mac config ID为`1a125cd20b95d52bf4e26f05489110841b0730f2192ef0c156d57b77a476590e`，导出OCI manifest ID为`447d3de4050f92091d3cbb6b1009beda40c1e9760926ac3748488b6311a4e805`，须在学校load后重新核对。baseline与新候选镜像包135817037字节，SHA `cc99d5cc13bc2a5f15d29129d914d03abddd404a1755e3c3e0d07c7ef929c314`。

下一步重过受影响的原冷/热对照，尚无改后时延、CPU或内存收益结论。旧诊断probe包装的公共摘要入口及artist map别名与新私有内核不同，不能用于新版本宣称解析次数或性能通过；原R2工具保持无业务probe。原首组累计2023.2123123533092秒永久闭合；新run只能依据固定历史首组/恢复/清理证据进入continued，不重开两批额度，历史宿主先导不算新镜像样本。原R2 FAIL保留。原114矩阵、两版原90浏览器、64MiB/50%/LRU/长期/三次CPU中位数、最终整合CI/full8及生产交付仍按[完整规划](../plans/2026-10-17-oom-resource-closeout-plan.md)执行，R3仍最多两轮有证据整改。

## 恢复、清理与证据边界

152文件原生ZIP为141089287字节，SHA `b6154b1a3fe554d4f5e46047feedf1d22173a4280b10b31fec9112cdbce2a3c3`。远端和Mac均完成CRC及逐文件实际恢复SHA，唯一transfer为COMPLETE，远端ZIP和collector metadata已释放。三次SSH失败原日志保留，确认原窗已闭合后才恢复回传，没有重新发请求或重置测试clock。

本次guard原PID/start_ticks确认退出，独立run根、两张测试镜像、cleanup proof暂存均实际删除，owned残留零；原16服务ID/运行/健康/重启/OOM状态与原29镜像保全。清后宿主磁盘可用41214877696字节（约38.39GiB）。未global prune或改既有服务配置。本机任务私有SSH socket已不存在，空的owned ControlPath目录已删除；退出请求返回“socket不存在”，不描述成又终止了一个活连接。

完整mirror在审阅结束后同文件系统原子迁至`~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261017/R3-hot-diagnostic-mirror`，146文件/143431882字节，原回执不改，另存`R3-hot-diagnostic-path-mapping.json`。独立工具/元数据包`R3-native-hot-diagnostic-tools-metadata.zip`为1151789字节、89文件，SHA `eac0040078c18175d2e5c119a76311a89bcdd04fcf09898a5ff4e02d70bffe31`，CRC及逐文件实际恢复通过，不含数据库内容。研发原始报告在`output/oom-closeout-execution-20261017/R3-hot-attribution/`，其中`hot-attribution-analysis.*`、`r3-native-diagnostic-review.txt`和`cleanup-execution/`分别记录分析、独立审阅和实际清理。

测量cgroup限额有Backend自读证据、准备有实际inspect；本controller没有持久化测量完整image inspect或helper完整HostConfig，不能把这部分写成独立保存的完整现场证据。运行期guard/controller确有相应核对，其源码身份和退出结果保留；本次始终只记DIAGNOSTIC、resource_admission=false，不增加任何原R2通过数。
