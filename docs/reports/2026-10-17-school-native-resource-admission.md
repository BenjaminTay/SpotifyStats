# 学校共享宿主的原生资源准入

日期：2026-10-17。事项：`SS-2026-10-08-001`。当前状态：**首对冷请求候选有效FAIL，R2停止、进入R3有界归因，完整资源准入HOLD**；未推送、未部署或重新验收Spotify生产。

## 范围与授权

用户提供 `school-linux-via-windows`，明确批准SSH传输冻结七库（合计671264768字节）、私密ready JSON、实际两镜像及工具，在共享宿主限额分批执行并在结束后清理本次资源。发现真实准备成本后，用户进一步批准修复后基线、候选各一批：每批最多1200秒、准备计时，两批合计最多2400秒。归档传输不计入活动测试时钟，前窗须本机恢复核验后才能进入下批。

宿主为原生Linux/Docker x86_64、4核、7.755GiB内存，同机有16个既有教发/FastGPT等服务。结果显式标为共享宿主，不声称独立非生产环境或镜像默认USER。Backend固定1CPU/2GiB/无swap、测试UID1000:1000；独立工具最多1CPU/512MiB。保留宿主可用内存至少2GiB、磁盘至少12GiB及本轮新增磁盘至多6GiB，最多同时1个Backend与1个工具容器；外部guard逐秒检查并且只停止本run资源。

两版仍为实际镜像：baseline `dc1cf9ad`，candidate `c844b98f`，相同基础及45项依赖。Docker原生containerd使用OCI manifest digest表示image ID，与Mac导出config ID不同；已按archive index→manifest→config、源码标签、ENV及RootFS逐字核验，没有重建或替换镜像。

## 保留的首轮结果与工具缺口

旧run `oom-school-20261017-bc4b9563` 的基线自然启动正常退出、无OOM，但不能算ready复用：逐窗复制改变main数据库inode，而analysis_stats/records的key与revision绑定设备号/inode；六个真实重建任务因此运行。旧worker的`exact_ready`仅检查搜索成品，漏掉analysis复用正向门禁。原raw PASS保持原样，独立判定为`INVALID_READY_REUSE`，正式ready通过数为0；旧候选窗未启动。

| 首窗必要维护观测 | 结果 |
| --- | ---: |
| 整进程RSS峰 | 1346904064字节 |
| 结束RSS驻留 | 362532864字节 |
| 启动CPU / wall | 434.017 / 441.953秒 |
| 来源37事实、读取strict | 均守恒 |
| 归档实际恢复文件 | 49 |

归档SHA：`7dc1b162a7629d3818ebe1ba3078643209ed69105577eb767c96048df0a24dce`。本机CRC、逐文件实际恢复SHA均通过后才删除远端归档。回传前遇到Mac将远端`/home`当本机symlink误拒，以及默认SFTP下载断开；前者分开本机实际路径检查与远端POSIX词法/远端实际检查，后者用4请求×16KiB、16Mbit/s上限及IPQoS=none完成真实回传。失败脚本、日志、回执及部分下载均保留，不称已证明底层网络故障根因。

## 最小验收修复与新attempt

仅修改研发树三个验收工具/测试文件，没有新增业务补丁。唯一一次复制后，在最终owned inode、同role/image/限额下完成真实正常lifespan准备并保存资源、任务、37事实与退出证据；准备正常退出后再正式安装rank成品，由全新Backend进程测冷启动。准备失败/OOM/触线直接阻止测量，所有阶段共用入口deadline。

独立helper核六个analysis成品真实解压/checksum、key/revision/version/publication_id/sha/created_at与数据库identity；ready启动和普通读取前后须相等，按job ID拒绝新增、运行或曾执行的analysis重建任务。maintenance_overlap仅在明确失效后的维护段允许对应变化；startup仍须复用。114窗口、72核心冷进程、两版原90浏览器及64MiB/50%/LRU/长期/CPU等门槛不变。

98纯测试、自检、格式与diff检查通过；准备、双批policy/guard及运行接线的独立定向审阅无阻塞。这些仅证明工具候选，不替代真实资源准入。

新run `oom-school-20261017-ready2-9bd95fab` 使用独立control/bundle/runtime/archives，以显式resource_adoption复用旧run只读输入和两镜像。包manifest SHA：`285f9b6f319206cafbed257954aa38a7eb459b192986e97bfca6c7632f7bb0d4`，实际原生preflight READY后进入准备。guard在内存中保存按序首次起点与累计时间，不能重置已用批次；首批归档本机恢复、冻结工具完整证据验证及远端释放确认后，才能记录精确SHA进入第二批。

后续现场结果：ready2的真实prepare正常退出、同inode、六成品exact、37事实与采样通过；随后final rank的`--closed-source`在遇到合法WAL时提前拒绝，尚未进入正式源校验、未创建measured进程。该窗判INVALID且完整回传，候选未运行。工具最小修复为初始无WAL副本仍closed-source、prepare后的正式三步骤改用既有mode=ro含WAL路径，保留逻辑source fence；不删除WAL/SHM或改inode。同时将500/100ms及overview64MiB明确用于候选，baseline超目标保留观测、两版正确性/采样/容量硬门禁不变。117工具单元及18正式installer单元共135项通过，定向审阅无阻塞；小SQLite WAL用例不冒充真实七库通过。

新run `oom-school-20261017-ready3-c3f35764` 的包SHA为`36a4e2b76dd6387af9d3b6395c1a45703a2b74efd6227173e54d14075e910e74`，原生preflight READY，首组两窗已有效恢复。ready2守护实计582.036771秒，向上按583秒从已批准2400秒总额扣除；新两窗缩为900/917秒，共1817秒，守护启动时核旧receipt SHA、live PID、实际idle phase、5秒内新鲜status与已闭合时钟，累计含旧失败不超过2400秒。三个明确run均复用唯一只读source-owner，最终共同清理；原失败不覆盖。

## 第一组有效ready启动对照

ready3基线完成同inode真实准备、正式含WAL的rank三步骤与全新冷进程。冻结验收器及独立审阅均通过：六份analysis身份逐项相同，测量段无新增/运行重建任务，准备期37项来源与测量期strict守恒；两进程实际exit0、无OOM，UID和限额一致。准备允许正常维护更新队列和派生成品，测量期核对严格只读。候选随后也完成相同验证并通过独立审阅。两版第1次观测分列如下：

| 阶段 / 指标 | 基线 | 候选 |
| --- | ---: | ---: |
| 准备：全进程采样RSS峰（字节） | 1287475200 | 1012547584 |
| 准备：cgroup峰（字节） | 1270517760 | 992731136 |
| 准备：结束RSS（字节） | 368001024 | 370614272 |
| 准备：启动CPU（秒） | 423.664 | 442.870 |
| ready冷进程：全进程采样RSS峰（字节） | 217120768 | 210915328 |
| ready冷进程：cgroup峰（字节） | 209334272 | 208723968 |
| ready冷进程：结束RSS（字节） | 217108480 | 204976128 |
| ready冷进程：启动CPU（秒） | 14.812 | 14.932 |

单次准备RSS峰下降21.35%，但结束RSS增加0.71%、CPU增加4.53%；ready冷进程峰下降2.86%、末尾下降5.59%、CPU增加0.81%。保留全部方向，尚不能判定三次CPU中位数或50%多实体合同。

两窗读取请求数均为0，不能用于500/100ms或64MiB结论。74文件ZIP为141019658字节，SHA `9d6ac28df3649bf31abdbd7df0bcfd4642a78f21d906245ac4163690d52f586a`；本机CRC/逐文件实际恢复完成，remote archive释放及精确ACK已确认。SFTP与普通SSH下载均在下一artifact的新连接阶段被关闭，原失败保留；通过任务私有ControlPath复用单SSH连接后完成回传，不改全局SSH/宿主服务配置，不将传输成功当作网络根因证明。

候选同为74文件ZIP，SHA `333494c9207ccf51d943506b2c2e0485b9c83735e69b32a4abec1b9cd21bd0f0`；本机恢复、远端释放及精确ACK均已完成。guard最终闭合基线709.181193秒、候选731.031119秒，含旧失败583秒合2023.212312秒，小于批准2400秒；两窗分别低于900/917秒上限，未重跑基线或重置预算。首组只贡献原114窗中的两个ready启动样本，完整R2合同继续HOLD。

工具三文件已形成研发阶段提交 `ede04ab8052b8139c20772760e820117d4b89af9`，提交四hooks通过，源码与受审冻结包一致。main尚未整合本轮业务或工具，不存在源SHA到main的业务映射；未推送/部署。随后按原授权进入`cold-track-l2-d0-1-baseline/candidate`固定对，四请求/窗，保持同包、同输入、1800秒原单窗上限及逐窗恢复核验；该固定对已完整恢复；候选因热请求门槛失败停止，未自动重跑。

## 第一对冷请求的有效失败与R3边界

两版各按原固定四请求完成：summary/overview并行冷读，再并行热读。候选cold服务时间332.610/379.656ms，均低于500ms；hot为305.175/303.222ms，均高于100ms，因此原raw FAIL、worker/container实际exit2和唯一性能failure保持原样，invalid为空。基线cold为294.730/353.762ms，hot为309.146/296.270ms；其raw PASS仅表示有效参考，热目标超限已保留，不表示达标。

八份实际HTTP正文逐一重算SHA，跨版及冷热对应相同：summary为`7e9abd17030cfb7047252176abe0751eb7636e908e8bc9e2572b17a2b2a1b816`，overview为`b2dcb55f1e706464563aaec1d85d448f7c58a89b4f74403b0dc9606a81ec932a`。两版六analysis成品四barrier/103历史任务不变、测量无重建，37来源与strict守恒；准备与测量的UID/cgroups、实际退出、采样和容量均有效。overview单请求采样RSS增量约9.48/9.58MiB，仅此场景低于64MiB，不代表矩阵通过。两版92项归档均已实际恢复及远端释放，SHA分别为`9a44438dab634f86792cc4d01e220d55d99b5765454772d9b195f982eb63c229`、`ab43a3841773e057f531eff903a21ed306bf57066f83888bcce9a3ac87ddd149`。

当前run共3个raw PASS（两个启动样本和一个基线有效参考）及1个有效候选FAIL；第一对controller明确STOP，LRU从未启动，其余110矩阵窗及两版原90浏览器未验。原失败不改为INVALID或PASS，不放宽100ms，完整资源准入保持HOLD。

只读源码核对发现投影链内重复解析上下文/快照与艺人身份映射，但实际耗时尚无证据；50ms进程内采样线程也可能与1CPU下并行请求竞争，现有样本缺少线程CPU与完整throttling字段，不能认定为根因。下一阶段R3固定最多14请求：2个诊断warmup后，重采样开启并行、重采样暂停并行、重采样开启串行各4请求；始终保留独立容量/宿主/OOM/磁盘/deadline保护。补充分组cpu.stat、sampler自身成本及两个必要业务阶段计时，明确DIAGNOSTIC且不计作R2通过。先归因再决定最小业务补丁，最多两轮有证据整改，原始合同不变。

## 证据、剩余工作与清理

原始证据在研发树 `output/oom-closeout-execution-20261017/R2-school-admission/`、`R2-school-ready-attempt2/`及`R2-school-ready-attempt3/`；首轮判定见`first-attempt-assessment.json`，工具与审阅见`tool-ready-report.txt`、`tool-initial-batches-report.txt`、`tool-rank-wal-report.txt`、`threshold-scope-fix-review.txt`及第三attempt的`budget-carry-preflight-review.txt`、`rank-wal-fix-review.txt`。工具、原始失败及已完成首组元数据已独立保存至`~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261017/R2-initial-native-tools-metadata.zip`：2414795字节、528文件，SHA `80047be66cd008056fdb2ae93bdabb328f47b648b3d1286aa2421296c782c500`，CRC及逐文件读回通过。相邻receipt记录范围与工具commit；三份完整私密mirror已在审阅结束后同文件系统原子迁入该独立archive目录，保留目录inode及原回执，`R2-school-mirror-path-mapping.json`记录旧路径到`R2-school-original-mirror`、`R2-school-ready2-mirror`、`R2-school-ready3-mirror`的映射；未复制第二套数据库ZIP；该2.3MiB包不含真实七库，不能作为私密运行库恢复包。

首组真实ready及第一对冷请求已完成，候选热时延失败；原矩阵其余110窗与两版浏览器合同、R3归因整改及最终整合CI/full8仍待完成；发布另需固定包批准，唯一首次验收与至少72小时生产观察仍未执行。当前不能关闭OOM。

学校三旧run及清理proof暂存已实际清理完成。三个guard的原PID/start_ticks均确认退出，ready3→ready2→旧source-owner三根目录与两张测试镜像删除，owned容器/镜像/根残留为零；原16容器ID/运行/健康/重启/OOM状态相同，原29镜像保留。清后宿主磁盘可用41216741376字节（约38.39GiB）；清理前后回执已回传读回验证，proof暂存随后按八文件精确白名单删除，无global prune或既有服务配置变更。

清理预检曾因原29镜像完整ID/tag行顺序不同拒绝；最小工具修复为等长与完整行集合比较，顺序置换接受、改变ID/标签/缺失/额外/重复均在变更前拒绝，原单/双/三根纯mock及独立审阅通过。plan输出时SSH断开，先确认远端计划已落盘再回传核验，未重复plan/execute。完整CRC及逐文件实际恢复ACK后才执行清理，最终receipt为COMPLETE。

首对失败、只读归因报告和实际清理证据另存独立`R2-native-first-cold-and-cleanup.zip`：2393302字节、98文件，SHA `ed12e60f2c323d44829e17c6912897165579043afe4b62b2e996bfa0a7dd431a`，CRC及逐文件实际恢复核验通过；该包不含数据库内容，六窗私密恢复ZIP由前述三份mirror保存。下一R3使用独立新run及单诊断窗，原run和原累计时钟不复活、不重置。

后续独立R3已闭合：14请求/734.634秒，B停重采样并行仍197–213ms，C开采样串行69–81ms；完整正文和守恒/恢复核验通过，不增加R2通过数。其新run及全部学校测试资源也已再次清理，原16/29保全；第一轮同事务复用候选729a0ed3已本地提交、正确性通过，新镜像原生收益待验。见[原生热请求归因](2026-10-17-native-hot-request-attribution.md)。
