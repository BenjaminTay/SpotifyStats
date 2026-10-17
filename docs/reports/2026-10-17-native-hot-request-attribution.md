# 原生热请求成本的有界归因

日期：2026-10-17。事项：`SS-2026-10-08-001`。**两次有界诊断与各批学校资源清理完成；第一轮最小业务候选729a0ed3已本地提交且正确性通过；该第一轮镜像原生对照有效FAIL，热请求145.521/192.171ms仍超100ms；第二轮0ee340cb正确性/审阅/本地提交与实际镜像完成，原生待验，完整准入HOLD。** 未推送、部署或重新验收生产。原R2候选有效FAIL保持不变，见[学校准入报告](2026-10-17-school-native-resource-admission.md)。

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

新实际候选镜像已从提交源码构建，基础digest保持原Python 3.9，540个镜像内源码/requirements文件逐项匹配，45项依赖、Python 3.9.25/glibc 2.41、无私密数据检查通过。运行ENV严格等于旧R0候选；相对R0前baseline仍保留既有`MALLOC_MMAP_THRESHOLD_=131072`差异，不能写成两版ENV完全一致。Mac config ID为`1a125cd20b95d52bf4e26f05489110841b0730f2192ef0c156d57b77a476590e`，导出OCI manifest ID为`447d3de4050f92091d3cbb6b1009beda40c1e9760926ac3748488b6311a4e805`，已在学校load后重新核对实际镜像、源码与运行配置。baseline与新候选镜像包135817037字节，SHA `cc99d5cc13bc2a5f15d29129d914d03abddd404a1755e3c3e0d07c7ef929c314`。

受影响的原冷/热对照已完成，见下节；有单次局部改善，仍未达原热请求门槛。旧诊断probe包装的公共摘要入口及artist map别名与新私有内核不同，不能用于新版本宣称解析次数或性能通过；原R2工具保持无业务probe。原首组累计2023.2123123533092秒永久闭合；新run只能依据固定历史首组/恢复/清理证据进入continued，不重开两批额度，历史宿主先导不算新镜像样本。原R2 FAIL保留。原114矩阵、两版原90浏览器、64MiB/50%/LRU/长期/三次CPU中位数、最终整合CI/full8及生产交付仍按[完整规划](../plans/2026-10-17-oom-resource-closeout-plan.md)执行，R3仍最多两轮有证据整改。

新候选首次准备run `oom-school-20261017-r3fix1-10b06529`尚未到测量：本机先因沿用旧bundle-integrity被拒；官方重封后，远端预检又因沿用已清理的旧source owner路径判INVALID。两次原错误均保留，没有启动测试Backend、创建runtime/archives或开始continued时钟，不能算业务性能FAIL/PASS。完成43份预检元数据CRC及逐文件实际恢复后，按固定preflight-only白名单清理本run/guard/两镜像/proof，原16服务/29镜像保全。失败与清理包`R3-first-candidate-preflight-failure-cleanup.zip`共109文件、1132665字节，SHA `bf3b43d9dc90c478b8b58d2b65add9511e257ee9af889013643c3cadb185f4dd`，不含数据库内容，实际恢复通过。随后新run `oom-school-20261017-r3fix1b-c98ed910`使用显式新root输入路径、无资源继承并重新官方封包，独立核对原合同及所有实际路径后准备；原失败不覆盖、首组预算不重开。

## 第一轮候选的原生对照：有效性能FAIL

新run `oom-school-20261017-r3fix1b-c98ed910`的实际final manifest canonical SHA为`f8d7c0540af131b25b850e5f212c044ba4ca4522f305b2edadf41f4158e7aba1`，实际guard receipt SHA为`46325e1efeaae18cda74f4282dbaf48707029117693c216c78b70a04ceed59b5`。pending bundle保留，与测量final包分列。原首组时钟永久闭合；历史首组恢复胶囊只提供continued的历史准入，不计作新镜像样本。原CLI/worker/client字节不变，原500ms冷/100ms热门槛不变，无业务probe或源码挂载。

| 指标 | baseline dc1cf9ad | 候选729a0ed3 |
| --- | ---: | ---: |
| 冷summary / overview（ms） | 259.539 / 291.697 | 223.767 / 277.018 |
| 热summary / overview（ms） | 249.577 / 310.349 | **145.521 / 192.171** |
| 准备采样RSS峰（字节） | 1291587584 | 1015681024 |
| 准备CPU（秒） | 406.534086638 | 431.187742917 |
| 测量采样RSS峰 / 末驻留（字节） | 228425728 / 228163584 | 216375296 / 216297472 |
| 测量启动CPU（秒） | 14.511514222 | 14.605187025 |
| 冷overview采样RSS增量（字节） | 9699328 | 9560064 |

baseline原raw PASS/实际exit0只作有效参考；候选原raw FAIL/实际exit2、invalid为空，只有两条热请求超100ms，normal_lifespan_exit=true。独立审阅核对八份实际完整正文与旧R2指纹相同，五barrier的37来源事实、strict、六成品/103历史任务/main inode复用、原采样与容量均有效。每版13个helper及prepare/measure Backend的实际镜像、1核/内存/swap/UID/network和终态已保存，candidate measure按原失败退出2，其他正常退出，无OOM或既有服务变化。

两窗含真实准备分别耗680.0402414482087和705.5551124280319秒，各自只arm一次1800秒clock；宿主guard记录最低可用3865448448字节、最高新增3288989696字节；准备worker采样的最低可用为3715268608字节，两种口径均高于2GiB，保护线未触发。单次准备峰约低21.4%，准备CPU约高6.1%；不是三次中位数或全场景50%收益，不据此关闭启动CPU与OOM。R2原矩阵继续STOP/HOLD，LRU和后续浏览器未启动。这是R3第一轮业务整改；下一步适配当前源码的第二次有界诊断，只在剩余主要开销有证据时做第二轮最小修复，仍最多两轮业务整改。

两窗原生ZIP SHA分别为`1268a3883a65fe0fc6e25f30388552abbe098b0a7dac3fdde7e12c4bc1b02513`和`79b571187d2509bcec950857af83b3c8c5f9e4366bbf2538f3894e91a5c51ed9`，均完整回传、CRC及逐文件实际恢复通过。baseline按完整恢复写精确ACK，候选FAIL仅恢复，不写PASS ACK。审阅结束后mirror原子迁到独立归档`R3-first-fix-native-mirror`，168文件/286152163字节，原回执不变，另存路径映射。374文件工具/元数据/清理包`R3-first-fix-native-results-cleanup.zip`为1815494字节、SHA `881e44f50f98a14ae678ebdbf6cd7cac06012b9c8e1f5ab844e388c7848e7f6e`，CRC及实际恢复通过，不含数据库内容。

本批193份清理元数据回传并实际恢复后，原通用cleanup按精确白名单执行。guard PID782236/start_ticks346187102实际STOPPED、两张测试镜像和新run根删除，原16服务/29镜像保全、owned残留零；回读cleanup receipt SHA `b0b38517a5108ccb3801b8b1320cb4d24456c1b18d5147c1bb6920c5e6e7be78`。proof三文件回读SHA相同后仅删本批proof目录；清后磁盘可用41210753024字节。任务私有SSH socket已不存在、空父目录已删除，不声称又终止活连接。

## 当前729源码的第二次有界诊断

独立run `oom-school-20261017-r3hot2-a336621d`，实际final manifest canonical SHA `70021d9a85948c9ddedf1de9ae9ea04a5f854d34edd9f24ce84d5fd35fded5f1`，parent是上述实际`f8d7…`原生对照而非旧c844样本。guard PID909263/start_ticks346494226，receipt SHA `efc7d1064dfebc4fa5c82067ef8f5dd9ce4ed3edcf7756be094a15bed3001529`。新probe绑定729私有summary内核及三个身份映射alias，只新增固定stage的线程CPU/次数与长度标量；35项纯mock及独立接线审阅通过，不把旧public wrapper用于新版本。

原14请求与三组A/B/C顺序、原采样、1核/2GiB/无swap及宿主保护线保留；无源码挂载或GET构建。实际单窗总耗712.847153861秒，prepare与measure不同容器均正常exit0；14份实际正文、五barrier来源37、strict、six/103jobs同inode复用、原采样与容量守恒，完整恢复后的分析器与独立审阅通过。guard记录最低宿主可用4190203904字节、最高新增3287691264字节。始终仅DIAGNOSTIC/admission=false，不增加R2通过数。

| 组 | summary服务计时（ms） | overview服务计时（ms） | sampler线程CPU（ms） | cgroup节流（ms） |
| --- | --- | --- | ---: | ---: |
| A：开重采样、并行 | 183.509 / 185.510 | 198.849 / 200.470 | 410.312 | 449.381 |
| B：暂停重采样、并行 | 141.166 / 200.231 | 151.518 / 193.254 | 14.434 | 289.552 |
| C：开重采样、串行 | 51.958 / 51.889 | 55.652 / 56.669 | 747.365 | 0.000 |

每请求现在确实只有一张1907项identity map、一次私有summary内核，credits均复用该map。C组线程CPU中，filter context约8.65–9.91ms、active document约8.15–8.60ms、ledger fence约7.26–8.45ms、identity map约9.51–10.10ms、有效署名约12.31–13.41ms；后者包含标题署名抑制约7.76–8.69ms、raw-name前缀约3.52–3.76ms。ledger fence与target ledger是同一次父子调用，不能相加；history重读仅约0.32–0.83ms，overview source-facts实际0次，版本/年度尾部很小。当前证据不支持优先改ledger重读或宽source-facts尾部。

新增stage是inclusive线程CPU，嵌套不能求和；raw-name前缀含分派成本，并非纯SQL。新增计数器的完整扰动未单独计量，不从service计时扣除。一次固定顺序诊断不能证明唯一原因或100ms达标；A/B仍超原目标。

对原冻结main仅做一次有界`mode=ro&immutable=1`、query_only SQL核对，无app import或新HTTP：L1及代表track均1493，原署名仅artist8/primary，automatic也是artist8/order0，无非primary原署名且标题无feature/of。结合源码，当前抑制逻辑仍建了没有最后消费者的全量名称、affiliation与alias索引。第二轮唯一候选据此限定为“确有遗留非primary署名且标题有可处理block时，才构建原完整消歧索引；显示名确需未解析identity回退时，才读原全艺人名称”。保留全局别名/of消歧闭包、人工覆盖和Spotify顺序；不改identity provider、ledger、tail或跨请求缓存。第二轮三文件候选已独立审阅并仅研发本地提交`0ee340cb76f51d0d1855652d240ffe71f3aed574`（父729a0ed3）：一个业务文件、两个unit文件，其中旧标题测试只同步一个访问计数期望及说明。44项署名/标题unit与117项详情/身份/revision unit共161项通过，6项seed公开快照合同、四hooks及diff检查通过；不重复运行稳定用例。完整的源/返回/Mapping、missing/None/False、未知ID、legacy groups/aliases/of歧义、manual/Spotify顺序与空scope/generator原语义覆盖保留。资源收益仍待原合同验证。

原生ZIP SHA `5903f8164964ccfc92b54e3cfc4606f615d93bf4be351ff53567d64505e76ea7`，唯一transfer `f80a3f66c097404d9b063d16f762ed01`为COMPLETE、CRC及逐文件实际恢复通过，远端ZIP/metadata package释放。mirror原子迁至独立归档`R3-second-hot-diagnostic-mirror`，146文件/143417494字节，原回执不变，另存路径映射。工具/元数据包`R3-second-native-hot-diagnostic-tools-metadata.zip`共120文件、1917124字节，SHA `8e555e1a4714acb82f5308ed693df63f70ccd719be9bdb9190da5cbaa1dcef53`，不含数据库内容，CRC及逐文件实际恢复通过。175份清理元数据实际恢复ACK后，guard实际STOPPED，测试run/两镜像/proof清零；原16服务/29镜像保全，cleanup receipt SHA `04fd63c2380c4ceeb76a8959b3ad17910e79a5c92d5662c300cbe638264cc3e6`，清后可用41209147392字节。任务私有SSH socket已不存在、空父目录已移除。

最终候选实际镜像从固定0ee提交构建，同一基础digest、Python 3.9.25/glibc 2.41、45依赖和729运行ENV保持；540源码/requirements逐项匹配，无私密数据或密钥。Mac config ID `a44530dd4efaae438541c8dd64b8c9bfd226616cab9e6c154b7431d0710ee690`，导出OCI manifest ID `1d5b1f1614e27b0c6736f4756251728c30f215168feed6357cdcf04d3e74e29f`；原baseline与新候选包135809489字节，SHA `2ac683094eb6f12eb3a83c11da9ab688be1213adf4de6e785c04e23801ea1d10`。来源/审阅包`R3-final-local-candidate-source-review.zip`共34文件、90494字节，SHA `4088031217bc628c31110b5de4e5a98e34e5277e2b2caba513985ce630cbbe52`，不含数据库或完整镜像，CRC及实际恢复通过。新run `oom-school-20261017-r3fix2-50f9535a`已准备官方pending包，尚无该镜像的原生窗口结果；仍仅恢复原两cold窗、不重开initial预算。这是第二且最后一轮业务整改，若仍失败，按规划保持HOLD并提交明确设计/容量决策，不继续无界微优化。

本轮两处执行工具错误均保留：首个内联启动wrapper因换行转义SyntaxError退出，确认没有controller child/Backend/runtime/archive/clock后，独立wrapper经合成检查和窄审只启动一次真实controller；原job/log不覆盖、原时钟未重开。清理plan首次因提前创建了空proof目录被原工具拒绝；核对仅为空的本批目录后移除，沿原prepare生成新plan，未覆盖旧清理证据或更改删除范围。两者不算业务性能样本。

## 恢复、清理与证据边界

152文件原生ZIP为141089287字节，SHA `b6154b1a3fe554d4f5e46047feedf1d22173a4280b10b31fec9112cdbce2a3c3`。远端和Mac均完成CRC及逐文件实际恢复SHA，唯一transfer为COMPLETE，远端ZIP和collector metadata已释放。三次SSH失败原日志保留，确认原窗已闭合后才恢复回传，没有重新发请求或重置测试clock。

本次guard原PID/start_ticks确认退出，独立run根、两张测试镜像、cleanup proof暂存均实际删除，owned残留零；原16服务ID/运行/健康/重启/OOM状态与原29镜像保全。清后宿主磁盘可用41214877696字节（约38.39GiB）。未global prune或改既有服务配置。本机任务私有SSH socket已不存在，空的owned ControlPath目录已删除；退出请求返回“socket不存在”，不描述成又终止了一个活连接。

完整mirror在审阅结束后同文件系统原子迁至`~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261017/R3-hot-diagnostic-mirror`，146文件/143431882字节，原回执不改，另存`R3-hot-diagnostic-path-mapping.json`。独立工具/元数据包`R3-native-hot-diagnostic-tools-metadata.zip`为1151789字节、89文件，SHA `eac0040078c18175d2e5c119a76311a89bcdd04fcf09898a5ff4e02d70bffe31`，CRC及逐文件实际恢复通过，不含数据库内容。研发原始报告在`output/oom-closeout-execution-20261017/R3-hot-attribution/`，其中`hot-attribution-analysis.*`、`r3-native-diagnostic-review.txt`和`cleanup-execution/`分别记录分析、独立审阅和实际清理。

测量cgroup限额有Backend自读证据、准备有实际inspect；本controller没有持久化测量完整image inspect或helper完整HostConfig，不能把这部分写成独立保存的完整现场证据。运行期guard/controller确有相应核对，其源码身份和退出结果保留；本次始终只记DIAGNOSTIC、resource_admission=false，不增加任何原R2通过数。
