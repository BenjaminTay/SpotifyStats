# 目标歌曲署名事实发布候选

日期：2026-10-18。事项：`SS-2026-10-08-001`。用户已选择[架构方案A](../designs/2026-10-17-detail-resource-architecture-decision.md)。状态：**本地正确性与独立审阅通过，实际镜像核验通过，原生首组执行中；资源HOLD。** 旧两轮R3有效FAIL保持原样，本轮不作为第三次局部微优化。未整合业务到main、推送或部署。

## 实现与失效边界

维护期在原详情实体投影中发布按L1定位的`track_presentation`，字段为`l1_id`、`representative_track_id`、`artist_names`、`primary_artist_name`。沿用现有有效署名、canonical/alias/group/of规则及排序、去重与空署名回退；primary仍来自代表曲目的原primary身份，不从署名首项推断。读取端逐次反序列化，返回对象独立。

新schema 91给九张实际语义依赖表安装事务内revision触发器，发布载荷绑定epoch/revision及schema水印。构建前后、原子发布前后均核对原fence；clone沿用原stamp，不为旧载荷重签。GET只读取目标载荷、同一发布fence与当前singleton revision，保留原exact-ready、filter/context/ledger及digest检查，缺失、损坏、过期或旧版本拒绝，不冷建或修复。未改变全局统计builder版本与统计口径。

详情/search上下文是L2/L3×dynamic/fixed的**四变体**；六套analysis成品另计。真实副本新增40108行（四份10026目标加四个fence），JSON共4921036字节。维护使用隔离七库副本，11张来源表完整行指纹不变。

## 本地验证与审阅

- 219项unit通过：原详情/agent事实67、迁移/快照相关101、目标呈现29、明确`-m unit`选中的revision 20、显式owned-copy CLI 2；6项seed公开边界contract通过。合成seed更新为schema 91、836608字节，golden与完整性核验通过，四hooks通过。
- 从上一轮原生候选归档恢复七库，逐文件核验原SHA；隔离维护后，四份原受影响完整正文与旧原生0ee结果一致。
- 独立进程运行旧0ee实际构建源码及当前候选，分别读取四变体×summary/overview，每版8份完整JSON逐字段一致。基线七文件SHA与候选11张来源表完整行指纹在读取前后不变。
- 新summary呈现核不再构建全局identity/有效署名，使用禁止调用探针验证。原L3 overview版本尾部仍各调用一次identity map（d0/d1）；没有将此结果扩大为整个GET零mapper。
- 独立静态审阅未发现当前业务阻塞。revision测试原缺unit标记已最小闭合；只读WAL初始化失败和过宽sentinel误拦原L3尾部两条测试协议错误均保留，后续只修测试入口，不改业务制造通过。

本地正文/所有权正确性不能证明热请求≤100ms、overview增量≤64MiB、全场景峰值与驻留下降50%、长期并发、完整114窗或两版原90浏览器合同通过。

## 已知发布准备依赖

Online Backup会改变副本schema cookie；显式`--build-on-copy`在owned副本上私有刷新后重建，两个CLI案例已验证。由此产生的副本fence与未刷新原库不同，跨库ready导入按现有合同安全拒绝。**Online Backup→原库ready传输的可交付性仍是R4/R5阻塞**，没有放宽水印、接受旧载荷或在GET修复。逐字节副本正确性不能替代该证明。原生架构门槛通过后才处理这项发布准备依赖。

## 当前检查点与下一步

候选源父提交`0ee340cb76f51d0d1855652d240ffe71f3aed574`，11个明确路径已形成仅本地阶段提交`19e66ab20e13e03d39e400437ac0421bfa027bad`，提交四hooks通过，研发树干净。共享文档由main维护。README/AGENTS/CLAUDE的产品与公开只读规则无需修改。

实际linux/amd64镜像已按精确提交和原Dockerfile构建并核对同基础digest、45项依赖、ENV、源码和无私密数据。现按学校共享宿主原1核/2GiB、500/100ms、保护线和逐窗回传条件，只跑原受影响对照。初批2023.2123123533092秒永久闭合，continued每窗1800秒上限不重置。该架构候选若再次有效FAIL，交付证据和决策后停止继续追加未规划补丁；PASS也只允许返回R2原矩阵。

2026-10-18首次SSH探测和跳板到Linux端口探测超时，原失败保留。用户要求重试后Linux已恢复连通；现场host/engine身份及原16服务/29镜像一致，可用内存约4.86GiB、磁盘38.34GiB，满足原保护线。本次独立run `oom-school-20261018-a-7db13002`已创建，已完成冻结输入逐项恢复和实际native镜像身份核验；原16服务正常，保护进程及最终包核验通过。原生基线窗已开始，按原准备→新冷进程→完整回传核验→候选顺序执行，尚无性能结论。

原始本地证据：研发树`output/oom-closeout-execution-20261018/A-track-presentation/`，核心收据为`candidate-final-correctness-receipt.json`、`local-real-combined-receipt.json`和`candidate-review.txt`。完整正文与数据库仅保留在私有证据目录，不进入Git、镜像或普通源码审阅包；长期独立归档见下节。

## 实际镜像与恢复包

精确提交git archive、原Dockerfile及固定Python3.9基础digest构建成功。候选config为`sha256:d64b21bcd996aef8afc4eb7b11495ece47a3df15baa81414e5a71edbc878c1af`，实际导出OCI为`sha256:a0eff896ceb50e3cbd6b8d21daa3d2643875a46979948d5eb47f501cb87ba52f`。541个backend/scripts及四依赖清单文件逐个等于提交源码；45项依赖、Python3.9.25/glibc2.41和候选ENV与0ee一致；无私密库/密钥，无app lifespan。Mac引擎为ARM，本次仅计镜像身份，不计原生性能。

两镜像实际导出135806794字节，SHA256 `e44f53e88804ceedc342ea5bd213bfed7ea944604bf5e6e81f51fa8077481b39`，OCI→config→source及基线原bc8身份核验通过。metadata主机验证器最初误排scripts/tests并漏计根requirements，随后误把Docker未复制的requirements-dev纳入期待集；两处协议错误留痕，按Docker实际COPY/ignore修正期待集后541逐项核验通过，镜像与业务未变，没有性能重跑。

独立长期归档根为`~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261018/`。源码审阅包`A-track-presentation-source-review.zip`，40文件/274680字节，SHA256 `a320a884302c6fe20be910b5779ebc92a6eb23721d3220bee93b596051293568`，CRC及逐项实际恢复通过；只含源码、合成seed和精简证据。完整正文另存权限受限的`A-local-correctness-private-bodies.zip`，SHA256 `4332cee106ffaf72bb4282cbf5d7b55636132f910a422d4ab8fd47ea97d1b73d`，10文件/18738字节，同样实际恢复通过，不含真实DB载荷。

最终原生包canonical manifest SHA256 `e0ebb3f741d05e5163c01074312acd05582d790e0f7f1e076696353bf91e9e3e`，官方pack的gaps为空；现场guard PID/start ticks/receipt和closed capsule绑定通过，初批new budget=0。独立包审阅发现manifest image_env曾误写为list而原CLI要求dict，已在启动窗前只修两角色清单类型并重封，原pending包留存；冻结CLI/worker/client、coordinator、guard、capsule及判据未改。最终包独立审阅无阻塞。本检查点仅代表原生执行准入，未计任何cold/hot或整体资源PASS。
