# 目标歌曲署名事实发布候选

日期：2026-10-18。事项：`SS-2026-10-08-001`。用户已选择[架构方案A](../designs/2026-10-17-detail-resource-architecture-decision.md)。状态：**修正版bfecef52原生受影响pair通过，仅Partial；首版INVALID保留，当前学校资源已清理，下一返回原R2，完整资源HOLD。** 旧两轮R3有效FAIL保持原样，本轮不作为第三次局部微优化。未整合业务到main、推送或部署。

## 实现与失效边界

维护期在原详情实体投影中发布按L1定位的`track_presentation`，字段为`l1_id`、`representative_track_id`、`artist_names`、`primary_artist_name`。沿用现有有效署名、canonical/alias/group/of规则及排序、去重与空署名回退；primary仍来自代表曲目的原primary身份，不从署名首项推断。读取端逐次反序列化，返回对象独立。

新schema 91给九张实际语义依赖表安装事务内revision触发器，发布载荷绑定epoch/revision及schema水印。构建前后、原子发布前后均核对原fence；clone沿用原stamp，不为旧载荷重签。GET只读取目标载荷、同一发布fence与当前singleton revision，保留原exact-ready、filter/context/ledger及digest检查，缺失、损坏、过期或旧版本拒绝，不冷建或修复。未改变全局统计builder版本与统计口径。

详情/search上下文是L2/L3×dynamic/fixed的**四变体**；六套analysis成品另计。真实副本新增40108行（四份10026目标加四个fence），JSON共4921036字节。维护使用隔离七库副本，11张来源表完整行指纹不变。

## 首版19e的本地验证与审阅（显式准备、无lifespan）

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

## 首版原生INVALID与精确清理

固定两窗已完整回传，基线688.177454秒、候选712.058948秒，均低于每窗1800秒；原初批永久闭合、没有增加initial额度。基线冷243.626/298.348ms、热177.981/232.310ms仅为参考。候选四请求均HTTP503 `snapshot_unavailable`，没有`detail_service`计时：worker为INVALID，window raw FAIL/actual2，coordinator actual1停止；**不能计为性能FAIL或PASS**。测量容器退出2、无OOM；来源37表、strict、六analysis成品/103jobs复用、采样及完整恢复证据有效，不能用这些证据覆盖HTTP不可用。

已在候选ZIP SHA `81af676dd31b635053900f07cb84f4e170748bd0c52e6cd056b9edc70f6fc4e5`的逐字节私有恢复副本做SQL只读核对：schema91、schema cookie601、presentation与governance水印601一致；四条详情projection state仍是`music_detail_v1`，没有任何`track_presentation`或fence行。根因是正常startup的search exact-ready快路只看搜索统计/Year-End，不维护独立详情版本。GET拒绝正确。首版本地测试显式调用backfill且不运行lifespan，未覆盖这条旧ready升级路径。

修复限于私有维护：独立检查详情版本与canonical fence/digest；search ready而detail旧时排现有维护job，不将搜索统计降级或全量重算；普通维护复用search后调用现有四变体原子backfill；`statistics_reuse_only`缺详情在候选写入/构建前拒绝。GET、全局builder版本、原生验收工具和指标不改。该检查点补修尚未提交，随后已以临时SQLite和本次原生恢复七库验证正常lifespan升级、第二个全新进程复用及完整正文/来源守恒，再审阅、固定镜像和重回原受影响对照；保留这次无效窗，不作为第三轮R3性能修补。

本批学校run/guard/两镜像及proof已按原清理器精确清理，清理回执SHA `5bd2928c74b10f5c4bca19a6f0cc0162975e0b165523b70fdad51b6b5adaa1d9`：COMPLETE、原16服务/29镜像保全、owned residue zero；私有SSH控制连接已关闭、socket目录移除。没有学校本批资源遗留。

原始168文件/286200842字节独立保存在长期归档`A-first-invalid-native-mirror/`，全部复制后读回SHA核验。元数据与清理ZIP `A-first-invalid-native-metadata-cleanup.zip`，439文件/2568879字节，SHA `45322a3f15aabacd3970795fb75e2c067253c8796892e391cf84cfc411f70314`，CRC和逐文件实际恢复通过，不含真实DB载荷；私密数据库归档只在raw mirror中。

## 正常启动接线补修验证

相对19e仅补两处业务接线：新增详情publication version/canonical fence/digest的只读current检查；私有schedule/enqueue在search+Year-End已ready、detail旧时仍排现有job，不将search标pending；普通rebuild沿用四search统计后，调用原backfill四详情原子发布并复核；reuse-only在candidate/planner/backfill前拒绝缺失详情。GET实现、统计builder版本和原生工具不改。

累计backend unit `-m unit -q --maxfail=5`已完整跑到100%，实际exit0：3275通过、2跳过、1411 deselected，仅原LibreSSL警告。新增接线专项及既有维护/startup组成67 unit（包含在前述累计数内），6项真实seed startup contract通过；首次71过/2旧手写fixture失败留存，修正fixture的真实L3 ready/schema及canonical详情fence后定向73项全过，没有mock新readiness为True。

对本次原生INVALID归档再逐字节恢复完整runtime七库及控制文件，在两个独立本地进程执行真实lifespan：第一进程只补建一次四context详情，新增一个search维护job；第二个全新进程零backfill、零新search job。两进程各四份完整正文等于本次原生基线，search_snapshot_meta完整行及11来源表在全程不变；禁止调用search统计全量builder与candidate重建。首进程因恢复后新inode合法重建Analysis/Billboard，不能将这项本地正确性写为六analysis原生复用或资源通过。

独立业务窄审无阻塞，另核首轮INVALID分类与学校精确清理。源补修已形成仅本地提交`bfecef520535d25f1adb06a912280fd89d3e0431`，新actual image已核验，接下来仍按原1核/2GiB、500/100ms、1800秒与逐窗完整恢复执行原受影响对照；首轮无效及旧FAIL保持。Online Backup跨库ready导入仍为R4/R5阻塞。

## 补修冻结与新原生包

补修五路径已本地提交`bfecef520535d25f1adb06a912280fd89d3e0431`，四提交hooks通过，研发树干净。公开只读边界另6项contract通过，合计6 startup+6 public contract；67定向unit包含在3275累计unit内，不重复计数。补修源码审阅恢复包`A-startup-publication-fix-source-review.zip`，26文件/352804字节，SHA `3396cefe43965e77e60bd7236bce3e881a5f164c51640e0dec24584c2de2eff9`，CRC与逐文件实际恢复通过，不含真实数据库或完整正文载荷。

新镜像config `sha256:cc2280d6f24a3a1d3e112ab193bfabcf101981a94240b438f69d777bfd10e292`，actual OCI `sha256:5ad74e6baa95b25faa8dcbd37ff9d1ee5c9f06cf362978825c1963fc16a16e67`，541源码/依赖清单和45项依赖逐项核验，与19e同基础digest/Python3.9.25/glibc2.41/ENV，无私密数据或密钥。两镜像实际导出135816741字节，SHA `3ec7f2600ec95f0aa8ec8f5cedcfa7fc3d4a274fb5717500344fb5bb61188189`。

新run `oom-school-20261018-afix-9ec62f30`已准备独立包，现重新执行现场host/engine/原16服务29镜像/容量核对与限速上传。仍用原coordinator、guard/capsule、CLI/worker/client、采样和原两cold窗口；原初批永久闭合、新initial预算0、每窗1800秒和1核/2GiB不变。本轮修复的是首轮不可测的正常startup升级缺口，未增加性能微优化或覆盖无效原窗。最终live guard重封与实际原生结果待补记，资源HOLD。

## 修正版原生受影响对照与清理

新run `oom-school-20261018-afix-9ec62f30`已完成，final canonical manifest为`2356c54f000b68e48fdcaf3c54cf4eb4bc5a3595854d6f7fc1da3cee1eed6533`；独立现场审阅核合actual OCI/source/config/rootfs、原guard PID3178376/ticks354211781/receipt及完整重封。原CLI/worker/client、coordinator、guard/capsule、114矩阵、500/100ms、原采样及限额未改。初批2023.212312秒永久闭合、新initial预算0；两continued窗各1800秒上限。

| 指标 | 本批基线dc1cf9ad | 修正版bfecef52 |
| --- | ---: | ---: |
| 冷summary / overview（ms） | 324.854 / 332.156 | 97.752 / 119.510 |
| 热summary / overview（ms） | 242.456 / 258.065 | 64.782 / 58.499 |
| 准备采样RSS峰（MiB） | 1239.316 | 964.543 |
| 准备CPU（秒） | 418.243 | 598.592 |
| 测量采样RSS峰 / 末尾（MiB） | 218.207 / 218.207 | 203.449 / 203.664 |
| 此冷overview采样RSS增量（MiB） | 9.555 | 6.750 |
| 关窗耗时（秒） | 686.303 | 935.233 |

四次请求均HTTP200，worker/window均PASS/actual0，coordinator actual0；两版八份完整正文逐字段相同。37来源五capture一致，读取strict通过；准备后六analysis成品与103jobs完整对象同inode复用，测量无新analysis；每窗实际2 Backend/13 helper的镜像/UID/网络/1核及2GiB或512MiB限额、所有终态exit0/无OOM核合，原采样有效。不得以基线高于100ms为由调整候选标准。

每窗77个非DB归档文件SHA和完整DB归档CRC/逐项实际恢复核合；精确ACK后才续下一窗。基线archive SHA `e0f9472e0a69a3d8a61c7a1a825cc05b31a18add56aca5699b9f0cd9aaf694ee`，候选`0ec14237f07cb998c5aed0aa2bd5fd22cd0b0bd7cae2648af9b39dc8dd8233a4`。保护进程记录宿主可用内存最低4004388864字节、新增磁盘最高3329036288字节，未触保护线。

分类为`AFFECTED_ORIGINAL_PAIR_PASS_PARTIAL`，resource_admission仍false。本批准备峰低22.17%、CPU高43.12%只是一组样本；本批包含首次目标事实发布，尚未做分段CPU归因，不能把全部增量直接归给署名发布，也不据此声称稳定CPU回归已证或已排除。此一overview的6.750MiB不代表全部overview≤64MiB；也没有完成50%峰值/驻留、LRU/长期并发、三次启动CPU、完整114窗或两版原90浏览器门槛。

原清理器完成plan→Mac元数据CRC实际恢复ACK→execute→proof。清理回执SHA `4f7b247525e9d794dbe2876865ed5f97f6c4e2de165366a71b1697009c024146`：COMPLETE、原16服务/29镜像保全、owned residue zero，guard STOPPED；run/两镜像/proof全部移除，SSH控制连接及目录已关闭清理。本批元数据191文件、SHA `f95644bd784e99e020609d7e3084ee1b2563817ad0e65fccd24c74ec2bce1209`已实际恢复核验。

本地权威收据为研发树`output/oom-closeout-execution-20261018/A-startup-native/final-native-pair-analysis.json`；原始结果/失败历史不改。下一先准备原R2有界续跑与磁盘预算，不能直接将当前只允许两ID的guard用于其他窗口，也不能把不同manifest的历史pair冒充新114全部通过。Online Backup跨库ready交付、最终整合CI/full8、发布批准和生产观察仍未完成。

独立审阅核合候选及清理后，168个原始文件/293132657字节已复制到长期归档`A-startup-fixed-native-mirror/`并逐文件读回SHA。元数据/工具/审阅/清理包`A-startup-fixed-native-metadata-cleanup.zip`，640文件/3498241字节，SHA `9fdffbc9081e8a961be4d2537e3eedbbb7d720fcdfaca50c508cdcc5b1c82626`；ZIP CRC及逐项实际恢复通过，不含真实DB载荷。完整DB归档只在私有raw mirror；独立归档根沿用本报告前述2026-10-18长期目录。
