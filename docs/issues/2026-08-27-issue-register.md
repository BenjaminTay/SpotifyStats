# SpotifyStats 问题台账

> R2准备验证检查点（2026-10-18）：原boundary-2两窗PASS，四HTTP200/四完整正文一致，六Analysis/103jobs/default+fixed、原37/strict及限额/退出/CRC恢复/ACK通过，仅2/114；prep-only47纯测/实际pack/独审通过。学校本批清理、原16/29保全，资源HOLD。下一仅两LRU窗各90分钟预算提案待批准，未实现或启用，原1800/7200保持。见[本轮报告](../reports/2026-10-18-track-presentation-publication-candidate.md)。

> R2路径协议检查点（2026-10-18）：首LRU旧canonical统计路径被公开策略拒绝，按INVALID保存并完整恢复清理、原16/29保全；候选未启动，不计性能失败。等价L1路径纠正134项纯测试通过，原合同不变，资源仍HOLD。见[本轮报告](../reports/2026-10-18-track-presentation-publication-candidate.md)。

> 架构A原生受影响对照（2026-10-18）：修正版bfecef52在原1核/2GiB与500/100ms条件下，四次HTTP200，冷97.752/119.510ms、热64.782/58.499ms；八完整正文一致，37来源/strict/六成品103jobs复用/实际限额与退出/采样/CRC实际恢复及精确ACK通过，仅受影响pair Partial。准备RSS峰低22.17%、CPU高43.12%为单样本，非50%/三次中位数证明。两窗686.303/935.233秒，当前run/guard/两镜像/proof和SSH控制已清理，原16/29保全。下一返回原R2矩阵，完整114窗、两版原90、全局64MiB/50%/LRU/长期并发与CPU门禁仍HOLD；Online Backup跨库导入仍R4/R5阻塞。未推送、业务整合或部署。见[本轮报告](../reports/2026-10-18-track-presentation-publication-candidate.md)。

> 架构A首轮原生INVALID（2026-10-18）：19e候选四次503、缺服务计时，不能计性能FAIL/PASS；真实恢复SQL确认schema91/cookie601水印有效，但四详情仍v1且无目标署名事实，正常startup的search-ready快路漏了独立详情升级。本地最小私有维护接线补修与正常lifespan验证中；旧显式准备219 unit/6 contract/正文证据保留，不能覆盖此缺口。两窗完整恢复、本批run/guard/两镜像/proof及SSH控制已清理、原16/29保全。资源HOLD，未整合业务、推送或部署。见[本轮报告](../reports/2026-10-18-track-presentation-publication-candidate.md)。

> 架构A实施（2026-10-18）：用户已选择维护期发布目标署名事实；schema91九表revision/fence和四详情变体目标载荷已实现。219 unit/6 seed contract、两版各8份完整正文及来源守恒、独审和四hooks通过；实际镜像核验通过，原生受影响首组执行中，原R2 FAIL/资源HOLD保持。Online Backup跨库ready导入仍是R4/R5阻塞；今日SSH重试恢复，现场16服务/29镜像与容量核对通过，输入/镜像与live guard已核验，原生基线准备窗执行中。未整合业务、推送或部署，见[本轮报告](../reports/2026-10-18-track-presentation-publication-candidate.md)。

> R3两轮整改闭合（2026-10-17）：729a0ed3热145.521/192.171ms、最终0ee340cb热150.305/163.493ms均为原生有效FAIL；原正文/来源/strict/成品复用/实际容器/采样和完整恢复通过。学校各批run/guard/测试镜像/proof均已精确清理，原16服务/29镜像保全。两轮上限已到，停止微优化，下一为[架构/容量决策](../designs/2026-10-17-detail-resource-architecture-decision.md)，尚未选择/实现；原R2 FAIL和完整资源HOLD不变。见[归因报告](../reports/2026-10-17-native-hot-request-attribution.md)。

> 收口执行（2026-10-17，R0/R1本地准备完成）：c844业务候选、bdcf资源准入工具均仅研发本地阶段提交；main业务未整合。实际两镜像及9容器合成通路、33纯测试/四hooks与恢复包通过，114窗及两版原90固定。该R1检查点当时缺非生产原生amd64、容量与私密通道；后续已获学校共享宿主授权并完成有限原生对照及精确清理，结果见文首和归因报告，R2资源仍HOLD；未推送/部署，正式交付与72小时观察待验。见[R1交付](../reports/2026-10-17-oom-images-portable-acceptance.md)及[完整规划](../plans/2026-10-17-oom-resource-closeout-plan.md)。

> 学校原生执行（2026-10-17）：共享宿主、七库/ready JSON及镜像工具私密传输已授权，原生预检READY。旧首窗因inode变化实际重建；第二attempt准备通过但正式rank入口误用无WAL模式，两次均保留原始结果并完成回传恢复。工具已补同inode准备、analysis六成品复用及WAL入口，135项测试和定向审阅通过。用户批准修复后两批各最多20分钟，旧失败实耗向上计583秒，新两窗限900/917秒、累计不超过2400秒；第三attempt首组两窗已有效恢复，累计2023.212秒，首对候选hot305/303ms超100ms，原FAIL保留、R2停止、LRU未启动；完整合同HOLD，三个run/guard/两镜像和proof暂存已清理、原16/29保全，进入R3有界归因。见[学校准入报告](../reports/2026-10-17-school-native-resource-admission.md)。

> 上一隔离检查点（2026-10-17，有限读取平台验证）：固定空闲/六实体读取各15分钟均进入有限平台：I1先增20.438MiB、M1三轮18请求后RSS470.125MiB稳定，末五分钟中位数跨度/斜率均0。7帧根及203.892MiB估算权重、3+3结果条目稳定复用，18完整正文/六事实/两strict通过。22文件未改，沿用10-16同版本full8；无新增业务修复。原生/default镜像、overview64MiB、长期并发/生产OOM仍OPEN，整合/发布HOLD，暂不提交推送部署。见[本轮验证](../reports/2026-10-17-oom-finite-read-platform.md)。

> 上一隔离检查点（2026-10-16，自然启动与累计门禁完成）：日期警告候选A-B-A自然对照，ready低20.719–25.133MiB、idle120低21.492–26.219MiB；27完整响应/六事实/三strict一致。启动峰约994MiB未改善，CPU高3.10–3.32秒信号保留，读取至idle120仍增约83MiB。最终22文件额外hooks及156项fixture回归通过；默认full8同轮PASS/实际0，seed4292/2跳、真实集成186/1跳、前端803/4跳、API157/113与51热基准、三浏览器通过。seed一条AI线程SQLite I/O警告单独保留。整体资源HOLD/Partial，原生/overview64MiB/长期/生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-16-oom-date-warning-startup-validation.md)。

> 上一隔离检查点（2026-10-16，arena路径与迟载导入/整体Partial）：原288个冻结arena新增109个路径、73个全块可追；外部dict/list缓冲缺失，未全部逐地址还原。新控制窗根图覆盖96.53%高空闲块，确认OpenCC与linecache源码行根。提前导入ready低17.203MiB但峰高16.570MiB，仅实验不入业务。保留日期回填显式dtype候选以消除FutureWarning触发的整份源码缓存；139项、Linux9组27返回/27时长表及七库不变通过，候选完整启动RSS净收益待验。两导入窗18响应/六事实/strict一致。仍22文件，仅本轮2处增改，整体OOM/原生/64MiB/长期OPEN，暂不提交推送部署。见[本轮报告](../reports/2026-10-16-oom-arena-paths-and-import-timing.md)。
> 上一隔离检查点（2026-10-16，启动arena持有者与探针校正/整体Partial）：少量分散对象占住大量空闲pool；发现旧逐样本字典探针本身持有时间戳/RSS对象。相同22文件/镜像下改原生缓冲，ready RSS473.914→421.324MiB、arena313→260MiB，仅观测校正且峰值未降。清四个小业务缓存及GC仅释放1MiB；剩余有署名/元数据、迟载模块常量及code缓存帧，仍288个高空闲arena未由受限根图解释。18完整响应/六事实/两strict一致，正式源/业务候选不变。最小修复仅诊断采样器，不新增业务补丁；旧RSS因果收益需按探针自干扰重新限定，整体OOM/原生/64MiB/长期仍OPEN，暂不提交推送部署。见[归因报告](../reports/2026-10-16-oom-startup-arena-owner-attribution.md)。

> 上一隔离检查点（2026-10-16，读取驻留归因完成/整体Partial）：原64.785MiB为有界缓存与allocator驻留混合，Python arena总量未增，存活块复用既有空闲池；四个播放表根合计181.076MiB估算，三轮根ID稳定、结果层命中。轻探针有效窗ready481.359→末尾546.652MiB；保留缓存诊断trim下降15.273MiB，定向失效后根及附件全部失活。29项、9份完整响应和两段strict通过，失败首窗保留。未发现需修复的淘汰/未知持有者缺陷，22文件候选字节不变，资源HOLD；下一优先启动Python pool碎片与长期小对象分布/原生资源验收，整体OOM仍OPEN，暂不提交推送部署。见[归因报告](../reports/2026-10-16-oom-read-cache-residency-attribution.md)。

> 上一隔离检查点（2026-10-15，合作署名展开与累计候选审阅/整体Partial）：合作署名先以3/2列键展开，再按行位置取独立完整返回表，原去重键、dtype、索引、字段及源表保持；时长中间表在最后消费点释放局部引用。441项（新增24项）、52次旧builder/144榜/26聚合、231组HEAD实体对账通过；后端3634通过/2跳过，另2项存储门槛失败已在未改动HEAD复现，完整后端Partial。三窗27响应/六事实/strict一致。累计HEAD→最终启动峰1303.668→995.094MiB、末尾893.277→607.395MiB；CPU130.840→131.300秒，仅同源仿真观察。二十二文件保留本地，累计审阅完成、资源HOLD/Partial；读取后仍增64.785MiB，下一转向新增缓存owner与空闲分配器驻留及平台期，不再无界追加启动微优化。原生/默认镜像、64MiB、长期和生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-collaboration-credit-expansion-and-cumulative-review.md)。

> 上一隔离检查点（2026-10-15，CPU归因与专辑时长最后消费点/整体Partial）：CPU正反序与三启动对照完成：同一B镜像CPU150.110→196.170秒证明显著波动，B两轮均高于A的信号保留；本轮A/C为138.440/134.050秒，候选未复现同规模增量，稳定回归未证且未全排除。日期处理后释放album_duration与precision局部引用，歌曲入口无用时长owner失活；417项（新增6项）、231组旧builder/693主表与693时长表一致。三窗27完整响应/六事实/strict通过，启动最高采样A/B/C1009.598/1006.820/991.102MiB；C读取后仍增69.758MiB，驻留与整体OOM未收口。二十一文件仅本地，资源HOLD/Partial。下一核对合作facts署名merge及selected/tracks/albums/时长投影的必要列与最后消费点；原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-startup-cpu-duration-attribution.md)。

> 上一隔离检查点（2026-10-15，专辑日期窄表回填候选/整体Partial）：专辑发行日期右键按专辑名/艺人名归并唯一，隔离源4行无重复；owned专辑表用两列键查询后回填，保留原索引/attrs和统计口径。411项（新增19项）、231组旧builder/693主表与693时长表一致，源表不变。两窗各3次merge输入55→2列、返回复用owned投影，9响应/六事实/strict通过。启动最高采样1009.484→1007.039MiB，启动CPU133.340→150.110秒更高，资源收益未证。二十文件仅本地，资源HOLD/Partial。下一核对歌曲时长merge峰点的存活owner与最后消费点，并定位启动CPU增量；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-album-release-lookup.md)。

> 上一隔离检查点（2026-10-15，快进纪录窄表候选/整体Partial）：_skip_storm在assign前投影分组键、play_id和ms_played，原计数、门槛与排序不变。392项（新增19项）、90组完整旧函数对账通过，源表及attrs守恒；旧函数3个复制检查复现、16个对照通过。两窗各9次assign输入52/56/48→5/5/3列，9响应/六事实/strict一致。启动最高采样1014.605→1008.027MiB、读取669.996→668.586MiB，小幅观察未证稳定OOM收益。十九文件仅本地，资源HOLD/Partial。下一核对实体构建专辑发行日期回填merge的整表复制、键唯一性与所有权；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-skip-storm-projection.md)。

> 上一隔离检查点（2026-10-15，Records展示阶段生命周期候选/整体Partial）：Records计算结束后释放事件、终身历史、时长及实体表局部引用，再解析封面；源表和年度预载表不变，结果引用继续保活。373项（新增28项）通过，旧函数24个滞留案例复现、4个对照通过。两窗9响应/六事实/strict一致；三次封面入口工作表引用8/7/7→0/0/0，主输入weakref5→0，首次入口964.086→750.301MiB。启动最高采样1010.586→1003.230MiB、末尾619.754→600.859MiB；读取后增长仅少2.391MiB，整体OOM未收口。十七文件仅本地，资源HOLD/Partial。下一验证_skip_storm的宽表assign最小列集，并对照合作构建持有关系；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-records-presentation-lifetime.md)。

> 上一隔离检查点（2026-10-15，实体身份复用候选/整体Partial）：实体构建已有逻辑ID时只读复用输入，缺失时保留原分配；源表不变、三张主返回表独立。300项（新增42项）、156组旧builder/468主表及468时长表对账通过。两窗9响应/六事实/strict一致；启动最高采样1020.035→1017.312MiB、读取661.715→658.613MiB，差异较小，不能证明稳定OOM收益。本轮最高采样均已离开实体构建，运行时入口复用标为NOT_OBSERVED，直接复用证据来自单元检查。十六文件仅本地，资源HOLD/Partial。下一按实体构建、Records计算与展示解析核对owner及最后消费点，再选择修复；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-entity-identity-ownership.md)。

> 上一隔离检查点（2026-10-15，合作aggregate局部候选/总体未改善）：合作aggregate只复制必要事件列和完整时长去重列；258项、52次builder对账（48完整/4同异常）、144旧聚合榜及26直接调用一致。两窗9响应/六事实/strict通过；启动最高采样1025.184→1052.148MiB、读取最高采样657.531→663.789MiB，总体资源未改善。十五文件仅本地局部候选，资源HOLD/Partial。候选最高采样在更早的歌曲时长merge，且两份已具逻辑ID的事件表同时存活。下一验证_build_entity_frames复用已具逻辑ID的只读输入，消除身份重复副本并保持所有返回表独立；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-collaboration-aggregate-projection.md)。

> 上一隔离检查点（2026-10-15，合作events生命周期候选/整体Partial）：补齐启动最高采样同点栈，保存事件总数后在最后消费处释放合作完整events表；231项、52次旧函数对账（48完整/4同异常）及144榜相同。两有效窗9响应/六事实/strict一致；启动最高采样1027.375→1020.602MiB、最终低27.102MiB，读取驻留未证稳定改善。十四文件仅本地，资源HOLD/Partial。修复窗最高采样位于合作艺人时长去重，已无完整events引用；首个探针失败窗单独保留。下一处理合作aggregate必要列与局部生命周期，保留事件/署名/时长去重键；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-collaboration-event-lifetime.md)。

> 上一隔离检查点（2026-10-15，合作select候选/整体Partial）：合作纪录select先转换署名键并筛选，再复制命中行；225项、52次旧函数对账（48完整/4同异常）及144份聚合相同。两窗9响应/六事实/strict一致；启动峰1053.914→1031.418MiB，读取峰仅低1.438MiB，最终低11.840MiB。十三文件仅本地，资源HOLD/Partial。绝对峰未捕获同点栈，不能将1017MiB署名merge栈当作绝对峰归因；CPU及观测开销保留。下一先补1031MiB绝对峰同点ownership证据，再定最小修复；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](../reports/2026-10-15-oom-collaboration-select-projection.md)。

> 上一隔离检查点（2026-10-15，歌曲merge副本候选/整体Partial）：歌曲canonical合并路径移除两份merge前宽表副本；194项、歌曲/实体各39组旧函数对账通过。两窗9响应/六事实/strict一致；启动峰1078.055→1062.219MiB，末尾仅低2.781MiB，CPU与采样差异保留，驻留未收口。十二文件仅本地，资源HOLD/Partial。未提交推送部署。见[本轮验证](../reports/2026-10-15-oom-track-merge-ownership.md)。

> 上一隔离检查点（2026-10-15，合作纪录键收集候选/整体Partial）：合作纪录键收集消除六次宽表复制，169项/22完整事实及66榜对账通过；两窗9响应/六事实/strict一致。启动采样峰1081.211→1046.914MiB，但不认定全部因果收益；ready/末尾各高约15MiB，读取增长仍约65MiB。十一文件仅本地，资源准入HOLD，整体OOM仍Partial。未提交推送部署。见[本轮验证](../reports/2026-10-15-oom-collaboration-credit-keys.md)。

> 上一隔离检查点（2026-10-15，Records启动局部候选/整体Partial）：Records启动生命周期候选保留，150项/39旧函数对账通过；最终启动采样峰1154.004→1097.176MiB，三窗9完整响应/六事实/strict一致。初版异常回退差异已修正并弃用，最终九文件未提交；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN。未推送部署。见[本轮验证](../reports/2026-10-15-oom-records-working-set.md)。

> 上一隔离检查点（2026-10-15，两项试验不采用/整体Partial）：外层候选134项及35旧函数响应对账通过，但峰值收益未证明，已恢复原八文件。最后一个malloc归因窗ready低204.445MiB，但启动峰高44.379、读取增长高160.105MiB，未改Dockerfile或生产。三窗9响应/六事实/strict一致；启动后空闲pymalloc pool约264.754MiB，下一目标Records启动宽表。未提交推送部署。见[处置与归因](../reports/2026-10-15-oom-duration-rejected-allocator-attribution.md)。

> 上一隔离检查点（2026-10-15，艺人专辑中间表局部候选/整体Partial）：研发八文件未提交，专辑子聚合投影与作用域收窄，删除无效全历史副本；120项通过，两窗9完整响应/六事实/strict一致。首次艺人峰增量99.199→69.098MiB，读取峰699.699→678.867；末尾高9.301MiB，arena差异启动后已存在，驻留收益未证明。默认镜像/原生/overview64MiB/长期及生产OOM仍OPEN。见[中间表验证](../reports/2026-10-15-oom-artist-album-intermediates.md)。

> 上一隔离检查点（2026-10-15，艺人首次局部候选保留/整体Partial）：研发七文件未提交，新增已发布艺人详情 SQL 前置投影；130项通过，同源两窗9完整响应/六事实/strict一致。首次艺人峰增量126.879→101.590MiB，本轮读取峰724.988→697.523，末尾低8.230MiB；启动峰未改善。默认镜像/原生/overview64MiB/长期及生产OOM仍OPEN，未推送部署。见[艺人首次验证](../reports/2026-10-15-oom-artist-first-projection.md)。

> 上一隔离检查点（2026-10-14）：原启动候选冻结，新增曲目六列加权/Top250八列切片投影；151通过、三窗33完整响应/六事实/strict一致，冷专辑峰低36–39MiB，但总峰/末尾未下降，最高点转至艺人stats首次。六文件未提交推送部署，整体OOM/默认镜像/原生/overview64MiB/长期仍OPEN。见[本轮报告](../reports/2026-10-14-oom-cold-stats-track-projection.md)。

> 本轮交付（2026-10-14）：b126已正式发布，研发/main CI与Release成功；原首次90/90、116/116 API、三个strict和wrapper0通过，末RSS低388MiB。读取增长/CPU未改善、启动高水位基本不变，OOM/峰值/64MiB/平台期继续OPEN，详见[正式交付与恢复入口](../reports/2026-10-14-native-trim-maintenance-production-delivery.md)。

> 状态：持续维护
> 首次建立：2026-08-27
> 历史状态核验：2026-10-13（c0d已发布，CI成功；Release首轮安装拒绝、补齐现成私密成品后attempt2成功；原首次90/90、116 API/三个strict通过。原wrapper1保留，Mounts顺序独立补证通过；资源/OOM/手机仍OPEN）
> 生产最后保存记录：c0d699e526f9323a95c63b2abf102c97d314eb2d、schema90、dual三healthy；原首次90/90，116 API/三个strict通过。原index39为3125.1→1716.3ms，RSS峰/末1160.348/1136.430MiB、CPU38.65秒；整体资源仍Partial/OOM OPEN，历史4f3f89/1及其他原失败保留。详见[本轮正式交付](../reports/2026-10-13-album-rank-cancellation-production-delivery.md)。
> 下文原有数值、环境状态和已解决项证据保留原始日期；9 月 13 日生产、LLM、Spotify 与 HTTPS 记录不自动代表今天的状态。

> 本轮本地资源整合：完整预热后的glibc回收四文件e01a4455已按授权提交并原样进入main，默认Phase5/full8通过；仿真Linux完整响应、strict及驻留对照通过。未推送/部署，原生amd64环境缺失，资源合同/OOM保持OPEN，未新验生产。见[审阅与提交映射](../reports/2026-10-13-native-trim-candidate-review.md)。

> 后续发布准备：6c74b9b4仅研发分支已推送，main未推送；CI38414168750 attempt1/实际job成功。生产warmup=0使full预热回收路径不可达，发布HOLD；私密成品及静态三模式准备不替代触发条件或资源准入。下一步先审阅实际维护完成边界的最小修正，不改生产配置、不部署。见[CI与发布准备](../reports/2026-10-13-native-trim-release-preparation.md)。

## 当前事项状态与近期收口

### 2026-10-08 榜单对决个人播放延迟

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-08-002` | 榜单成绩先出现，个人播放次数、时长与排名迟迟补齐 | `RESOLVED / RELEASED`；c587正式三workflow/11jobs及实际安装/独立runtime通过，原公开FIRST14/28全PASS（最大1.669秒）、420秒资源/全守恒、96 API与三denial通过；人类明确仅公开HTTPS，S0–S5完成，旧首次失败保留 | 本地45/90、96、130及详情自然90通过；部署72回归/Linux备份/owned共同恢复与cb8 full8通过，所有旧失败分列 | P1：三库准备最小补修83回归/Linux隔离通过，c587本地固定/hooks与清单九步通过；授权四文件清理/上传/push实际0，新c587三流水线及实际安装success，独立runtime确认3完整SHA/healthy和schema90/4rank/4detail/48BBready；启动维护自然结束，原首次公开14/28、840连续资源sample及两面96 API/三denial全通过，不预暖或放宽门槛。本项公开范围已由人类决定并完成；私有保持现状。详情独立唯一额外重启已完成，原90性能39通过/51失败，116功能及完整读取守恒通过，详情和OOM仍开放。见[规划](../archive/06-productization-closeout/2026-10-08-versus-personal-statistics-performance-plan.md)、[验收报告](../reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)第21.9–21.13节。2026-10-09。 |
| `SS-2026-10-09-001` | 详情榜单成绩首次加载慢，疑似等待个人排名 | 首次延迟子项PASS；整体`OPEN / Partial`（资源未收口）。b126新首次90/90、116/116 API/三strict及wrapper0通过；c0d原首次与原失败保留 | 点击核心最大1084ms、直达最大2368.6ms均达标；原index39 L3专辑直达1716.3→1498ms。末RSS低388MiB，但读取增长与CPU未改善、启动高水位基本不变 | P1：资源归SS-2026-10-08-001统一推进，手机弹层另行处理；不追加生产热复验。见[新生产交付](../reports/2026-10-14-native-trim-maintenance-production-delivery.md)。2026-10-14。 |

`SS-2026-10-09-001` 2026-10-13本地整合检查点（后续交付见上表）：组合补丁SHA256 `a37bcf95f05f23ffb957cf228f8bdaec495e2df56b3ca0be3c506e5f65479295`；七文件在2bdf基线现有统一整合工作区应用，完整backend Python源码等同研发full8版本。研发run `20261012T152324.012689Z-fff3d57bed12` 默认完整八阶段PASS/实际0（3937 seed/186集成/803前端通过，三浏览器）；第一次禁外部封面模式失败与正常模式完整重跑保留。整合57重点复核通过，没有另跑整合full8或生产。源七文件已原样进入main业务提交`c21250e3`，状态提交`8b1b2405`亦快进进入main；研发/整合树安全同步，恢复点独立保存，未推送/发布；原RSS起点差、raw Analysis发布摘要false均保留，OOM独立OPEN。详见[审阅报告](../reports/2026-10-13-album-rank-cancellation-integration-review.md)。

`SS-2026-10-09-001` 发布前本地候选验证记录（本轮生产结论见上表）：最终run `20261011T073600.905084Z-f1483ad94de8` 默认完整八阶段同轮PASS/实际0；后端3876/2skip、真实副本186/1skip、前端803/4skip、API157/113与51热基准、三浏览器通过。首轮文档编辑触发hook修改判定、第二轮手机加载竞态失败全部保留；已加载页面筛选门禁补充初始响应/UI就绪后从头验收，没有改超时或最终断言。协调独立验收通过后，候选已按授权提交并统一发布；该次ea93生产86/4、旧6dac79/11和62683/7分别保留，历史AI失败保持，OOM独立OPEN。

`SS-2026-10-09-001` 发布前分段定位记录（2026-10-11）：离线复核及同源ready副本32→33、38→39各一次已完成，原fresh/PWA/门槛保持，缓存API转发烟测和57/37/六侧库完整strict通过。深链自身没有完整排名请求，但上一场景取消排名的后端仍计算3.4–4.5秒并覆盖下一summary/overview；有效曲目数来源读取最高491ms，身份解析9–115ms、序列化≤5.65ms、singleflight等待0。副本深链2.28/1.76秒达标，未复现生产失败，非CPU时间的GIL/调度/I/O归因尚未证明。产品改动0、生产请求0；下一步固定同事务、同membership/source-check的有界计数读取合同，减少完整DataFrame和逐行往返，再决定候选及专项，不直接改前端并发、不重跑full8。新原始证据保存在忽略目录`album-direct-critical-path-diagnosis/`，见[验收](../reports/2026-10-09-music-detail-chart-performance-acceptance.md)ea93同源副本四场景节；生产86/4、整体OOM和手机弹层继续分别OPEN。

`SS-2026-10-09-001` 发布前实施验证记录：已实现计数轻量批量读取，保持原membership/source-check与metadata join合同，无新缓存/迁移/发布格式。98重点回归与最终42计数投影测试、同源60完整响应（54正常/6既有503）及20计数oracle、原四场景双版本与四strict通过。候选深链0.73/0.64秒，点击38和全窗口CPU增加如实记录；生产根因/OOM未关闭。新run20261011T102216.614157Z-bc0c921c926f默认完整full8同轮PASS/实际0、2092445ms，1455源码起止一致。发布前串行对照未复现原并发大幅rank CPU增加，6响应/两strict通过、rank frame与调用次数相同。协调验收通过并批准本轮10路径提交，未新推送/发布。

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-11-001` | 手机播放统计加载时打开时间范围弹层，数据返回后弹层消失 | `OPEN / P2`；基线已有，未产品修复 | 未改动前端基线中暂扣真实200响应：加载中弹层可见，释放后出现KPI、原触发按钮断开、弹层消失；控件从加载分支迁入已加载内容导致重新挂载。此受控复现不作性能数据。新专辑候选未改这些前端文件。 | 独立修复加载转换时的控件/编辑状态连续性。本轮只让“已加载页面筛选”门禁等待初始响应与对应UI就绪，保持30秒数据等待和原应用后断言；不把该门禁修正描述成产品竞态修复。见[验收报告](../reports/2026-10-09-music-detail-chart-performance-acceptance.md)本地专辑候选节；2026-10-11。 |

### 2026-10-08 生产响应与验收阻塞

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-08-001` | 详情与年度准备期间资源耗尽，管理连接失去响应 | `OPEN / Partial`；原生LRU基线有效FAIL，候选未启动；完整资源HOLD | 基线68分38秒完成786次全200、259目标重访稳定，原37/strict/九项淘汰/采样/限额有效；三轮RSS714.51→757.80→789.05MiB，增长74.54MiB超原8MiB容差，帧权重仅增102字节 | P1：完整恢复及学校清理完成，现有16/原29保全。下一候选单窗90分钟诊断需批准调整停止规则，阈值不降、不发失败基线ACK。完整114/原90、64MiB/50%/长期、三次CPU、整合CI/full8、跨库ready发布及72小时观察待验。见[本轮报告](../reports/2026-10-19-lru-budget-native-acceptance.md)、[规划](../plans/2026-10-17-oom-resource-closeout-plan.md)；2026-10-19，未推送、业务整合或部署。 |

### 2026-10-07 非榜单详情统计空值

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-07-001` | EntityStatsPanel 在空态判断前读取 nullable 趋势，Afterlife 详情崩溃 | `RESOLVED`；生产专项通过 | 76a4968已发布；私有/公开桌面手机视口均安全空态、真实0及切回正常统计通过，无白屏/异常；两端30次API前后来源与队列不变。原本地32项、前端763/4skip和7f完整八阶段证据保留。 | 本范围收口，资源问题由SS-2026-10-08-001独立跟踪；见[生产验收](../reports/2026-10-08-release-date-production-delivery.md)。2026-10-08。 |

### 2026-10-06 曲目署名重复与标题误拆

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-06-001` | 旧标题署名叠加造成整体占位、完整名误拆及普通with误识别 | `RESOLVED`；S0–S5已完成 | 2faadc64正式发布、CI全success；S4默认八阶段PASS，S5补修94/独立53项、真实17表安装及生产两端API/浏览器通过。15曲目减少18条冗余有效署名，原始事实和34条既有人工覆盖保持。 | 本范围收口；真实补充、改名/拼写/跨ID歧义保留，不批量删除31个差异条目。见[归档计划](../archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)、[验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

### 2026-10-03 播放记录歌曲链接 404

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-004` | Records 将歌曲 ID 字符串化为 `1493.0`，公开详情请求返回 404 | `RESOLVED`；已生产发布 | 新序列化与旧快照响应共用整数 ID 规范化；艺人/专辑身份和统计事实保持。详情入口兼容零小数旧 URL，保留查询/锚点且替换历史项，非法 ID 不发请求。后端专项 110、前端专项 39、生产构建、Ruff/所改模块类型检查通过。真实生产响应副本修正 678 个 ID，非 ID 字段差异 0；公开旧快照测试不写回、不重建、不排队。 | 已随2faadc64发布；生产公开手机点击vampire及旧1493.0参数/锚点规范化通过，见[生产验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

浏览器专项：本地生产构建 `127.0.0.1:15175` 经 SSH 隧道读取生产 public-readonly API；1440×1000 与 390×844 均从 Records 的 vampire 旧链接实际点击到 `/music/tracks/1493`，摘要、统计和榜单页签读取成功。直接打开 `.0` 链接保留 `merge_level` 与锚点；组件回归覆盖零小数、非法小数、查询参数与返回历史。此证据是本地候选前端与生产只读 API 联调，不是生产修复发布、默认完整全栈或物理手机验收。截图与事实对照在 ignored `output/playwright/record-id-fix/`。

### 2026-10-03 公开时间选择

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-003` | 公开播放分析与详情只显示三个时间选项 | `RESOLVED`；已生产发布 | 已移除桌面和手机时间选择器的公开运行面过滤；加载、错误及空结果时保留入口；已准备范围可读取，缺失 Analysis Stats / Records 结果仍明确不可用。见[专项报告](../reports/2026-10-03-public-analysis-time-ranges.md)。 | 已随2faadc64发布；生产公开桌面/手机8选项可见，缺失日范围仍503且保留切换入口，见[生产验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

### 2026-10-03 专辑证据集成

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
| --- | --- | --- | --- | --- |
| SS-2026-09-24-001 | 完整曲目分页与发行位置 | `RESOLVED`；daf098ca已正式发布及限定生产维护 | 54份目录/位置及必要缺失provider元数据，Glee106/1、Lana位置、Mimi14共享/6独占、Records保持；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md) | 本范围已收口；不将模拟视口称为物理真机 |
| SS-2026-09-24-002 | 专辑艺人稳定 ID 与有序证据 | `RESOLVED`；daf098ca已正式发布及限定生产维护 | 154份证据/177条有序署名，canonical人工优先、冲突保留，实际发行周期/Records通过；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md) | 13个Album含17条未解析署名保留数据审核；不新增身份批准 |

### 2026-10-03 生产搜索派生外键遗留

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-002` | 生产搜索派生表引用已缺失 snapshot meta | `OPEN` / P2 | schema85源 Online Backup 已有60,294条 FK orphan：weekly chart context60,270、year-end meta20、year-end projection state4；Album维护后集合不变，当前四精确变体ready及entity context读取门禁另验；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md)。 | 独立调查快照轮转与派生清理合同，先在副本验证；本轮未修复或删除，最后核验2026-10-03。 |

### 2026-10-03 全站封面优化

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-001` | 小封面优化未覆盖首页、播放记录、音乐档案和当前年度 V2 | `RESOLVED` | `814ea7cb` 已正式发布；默认八阶段全栈 PASS，生产 8,720 个派生资产补齐，原图 stat/原始播放表数量不变；实际 HTTPS 核心 60 + 四视口 192 样本及必要交互完成。 | S0–S5 闭环；高清 Phone 榜单体积增加与非真机边界见报告，最后核验 2026-10-03。见[已完成方案](../archive/06-productization-closeout/2026-10-03-cover-image-optimization-plan.md)、[报告](../reports/2026-10-03-cover-image-optimization-acceptance.md)。 |

### 2026-10-02 新增元数据问题

两个专辑证据事项的当前状态见上方最终集成登记；日期精度已发布、迁移及有界补证，生产专项已收口，资源OOM另行跟踪。

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-09-24-003` | 发行日期精度丢失 | `RESOLVED`；生产专项通过 | 76a4968/schema89、92来源/78项目精度已安装；原文、有效署名及事实守恒/幂等通过，最终61表与写后备份双向差集0。五年exact年度、两端API/双视口legacy与confirmed/day展示通过；旧完整全栈保留历史。 | 本范围收口、计划归档；未知精度及冲突继续保持审核边界，不扩大身份或全库补证。见[精度合同](../reference/release-date-precision.md)、[生产验收](../reports/2026-10-08-release-date-production-delivery.md)。2026-10-08。 |

详细背景与其他待量化方向见 [元数据路线 §10](../plans/2026-09-23-multi-source-music-metadata-roadmap.md#10-2026-09-24-spotify-现有字段利用审计后续问题)。

### 原有未闭环事项（保留 2026-09-13 证据）

以下两项继续跟踪；耗时数值与外部服务状态属于历史样本。2026-10-02 只核对剩余事项和当前计划，没有重新计时或检查真机。

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
|---|---|---|---|---|
| `SS-2026-08-24-004` | 全栈总门禁时间过长，且并发性能竞争、冷建等待和失败后整轮重跑放大交付成本 | `PARTIAL` · P1-A/P1-B 已完成 | 廉价 preflight、跨工作区 `fcntl` 锁和 run-id 独立 summary 已由提交 `8326169f` 实现。当前 `5bcfc5de` 默认完整门禁全部必需阶段 PASS，但实测总耗时 2,832,355ms（约 47 分钟），其中 backend 约 18.8 分钟、API 约 10.5 分钟、browser routes 约 9.2 分钟；说明正确性已闭环但 25 分钟耗时目标仍未达到。见 [`收口与发布报告`](../reports/2026-09-13-development-closeout-and-release.md)。 | 基于本次 run-id evidence 做 `pytest --durations=100` 与 API/浏览器阶段剖析，再评估不降低覆盖、三浏览器和 500ms 阈值的安全并行；严格 evidence manifest 单独续做。 |
| `SS-2026-08-06-005` | PWA/移动网页完成后，iPhone Safari 与 Android Chrome 真机安装、返回、安全区和 OAuth 验收仍未完成 | `PARTIAL / EXTERNAL` · 本轮决定不实施 Capacitor | `d50f924c` 的 dual 三容器、PWA 文件和 loopback 边界均通过服务器独立验收，但 Tailscale/Serve 当前为 Stopped，Spotify 未连接；只有 OAuth URL 的 callback 配置正确。没有明确原生分发需求且真机前置条件未满足，因此不新增 Capacitor 工程。见 [`appification-pwa-capacitor-plan.md`](../plans/2026-08-06-appification-pwa-capacitor-plan.md)。 | 需要远程使用时先显式恢复受控 HTTPS；再由真实 iPhone/Android 完成安装、键盘、返回、安全区和 Spotify consent 回跳。只有确认 App Store/安装包需求后才重启 Capacitor Phase D。 |

## 排序规则：当前实现

### 播放排行：同次数按时长和稳定实体键排序

播放排行页面是 [`AnalysisChartsPage.tsx`](../../frontend/src/pages/AnalysisChartsPage.tsx)，调用 `/api/analysis/charts`。2026-08-29 修复后的服务端排序逻辑为：

```text
metric=plays  : plays DESC, hours DESC, stable entity key ASC, normalized name ASC
metric=hours  : hours DESC, plays DESC, stable entity key ASC, normalized name ASC
```

歌曲、专辑、艺人均按各自稳定实体键排序；跨越同分组的 offset/limit 也不依赖输入顺序。当前真实接口默认过滤、L2、lifetime 样本中，歌曲榜第 11/12 名同为 180 次，11.9h 的 `drivers license` 排在 8.6h 的 `Midnight Rain` 之前。

### Billboard 周榜：同播放次数会按总收听时长降序

Billboard 周榜的单曲、专辑和艺人排名共用 [`chart_ranking.py`](../../backend/domains/billboard/chart_ranking.py) 的 `_stable_weekly_sort()`，规则是：

```text
billboard_week ASC → play_count DESC → total_ms DESC → 稳定 ID ASC → 标准化名称 ASC
```

所以 Billboard 周榜不是随机的：同周同播放次数时，`total_ms`（总收听毫秒数）更高者排名更前；如果连时长也相同，再用 ID/名称稳定区分。当前真实周榜 `2026-08-14` 的歌曲、专辑和艺人数据均符合这一规则。

> 注：Billboard All-time/Power Score 是另一套累计评分排名，不能简单套用“周榜播放次数 + 时长”的解释；如要核对该页面，应单独记录其评分与 tie-breaker。

### Billboard Records：所有同值列表使用业务二级键

2026-08-30 复核了 `/api/billboard/records` 和 `/api/billboard/data` 的 6 个 Records 子页面、8 个后端记录模块、共 51 个列表。冠军圣殿的冠军名人堂已拆成独立的单曲/专辑候选集：单曲按“冠军单曲数 DESC → 单曲冠军周数 DESC”，专辑按“冠军专辑数 DESC → 专辑冠军周数 DESC”，只有对应数量大于 0 的艺人进入榜单。其他记录列表也按各自的日期、周数、Peak、走势评分、播放差额或实体数量等业务指标补齐二级/后续排序，最后使用稳定实体键；完整规则见 [`playback-stats-rules.md`](../reference/playback-stats-rules.md) 的 R39.1。

排序实现会先对完整候选集排序再截断 Top N，因此 cutoff 同值行不会因为 groupby、缓存重建或输入行顺序变化而交换。固定参数和同一 revision 下，两个 Records 接口各 51 个列表的排序巡检均为 0 个违规；这次补充仍不改变 Billboard 周榜的播放次数/总时长排序规则。

## 已确认解决或不再作为开放问题

以下事项有后续交付证据，因此不应从旧提问清单中再次当作“未解决”提出：

- `SS-2026-08-31-002`：未知 Spotify Track ID 的导入防复发和 provider-first duration resolver 已在本地提交 `e251148a` 完成；Online Backup 与真实数据库只读模拟仍为 217 keep / 600 review / 0 个安全操作。存量 review 因缺少唯一目标而不做写入，等待新证据，不再作为未完成代码。见 [`收口报告`](../reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)。
- `SS-2026-08-31-003`：人工专辑关系现在在同一事务内完成专辑/歌曲 mutation 和派生刷新，批次只刷新一次，失败整体回滚；响应公开 targeted/full、影响范围、fallback reason 与后台 job ID。实现位于本地提交 `e251148a`，完整发布状态待本轮后续门禁和部署回填。见 [`收口报告`](../reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)。
- Agent V5：原生工具循环、只读工具注册、证据契约、崩溃恢复、SSE 续传和年度报告共享上下文已完成；集成线已进入 `origin/main` 并随 `b0d674bd` 部署。仓库级门禁尾项由 `SS-2026-08-24-004` 跟踪，不是 Agent V5 核心链路未完成。见 [`Agent V5 验收报告`](../reports/2026-08-31-ai-agent-performance-v5-acceptance.md)。
- L2/L3 身份与专辑归属：L2 活动组成员重叠、无效代表、L3 未覆盖/多 owner 和逻辑事件守恒问题已收口，对应代码已进入 `origin/main` 并随 `b0d674bd` 部署。600 个 L1 review 是另一个开放治理队列，不反向把 L2/L3 标记为未完成。见 [`L2/L3 交付报告`](../reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)。
- Billboard 持久快照：周榜、年榜和总榜 cache-first 持久快照、事件驱动后台重建、LKG 与回滚兼容性门禁已完成生产交付；实施计划已归档。见 [`归档计划`](../archive/06-productization-closeout/2026-09-12-billboard-persistent-snapshot-optimization-plan.md) 与 [`交付报告`](../reports/2026-09-13-billboard-persistent-snapshot-optimization.md)。
- `SS-2026-08-31-001`：Billboard 已实现“阈值只约束 `play_count`、`total_ms` 统计全部有效音乐收听区间”的次数/时长双轨规则。提交 `911256f1` 已进入 `origin/main` 并包含在生产代码版本 `b0d674bd`；真实 Online Backup 副本的聚合、四套搜索快照和 API 对账已通过。详见 [`2026-08-31-billboard-count-duration-semantics-research.md`](../reports/2026-08-31-billboard-count-duration-semantics-research.md)。
- `SS-2026-08-27-001`：播放排行同次数排序已解决。播放次数榜现在按 `plays DESC → hours DESC → stable entity key → normalized name`，播放时长榜保留 `hours DESC → plays DESC` 后追加稳定键；歌曲、专辑、艺人及跨同分分页的乱序输入测试通过，真实 180 次样本为 11.9h 在 8.6h 前。该修复没有修改 Billboard 周榜规则。见 [`2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- `SS-2026-08-26-002`：设置重建状态、导入健康口径、只读治理预览和导入前比较语义已解决。功能范围、真实主库只读探针、Desktop/390px 浏览器、完整 unit/contract 和前端回归已通过；修复提交 `62f48299` 与后续 `dc7055a7` 已进入 `origin/main` 并包含在生产版本 `b0d674bd`。历史数据实际清理仍是独立授权事项。见 [`交付报告`](../reports/2026-08-27-settings-rebuild-and-data-governance-remediation.md)。
- `SS-2026-06-23-006`：播放记录历史规划与当前实现的文档核对已完成。当前 `/api/analysis/records`、路由容器、TanStack Query、5 个栏目和 20 个模块均已存在，并有 Phase 5、移动端与播放记录专项验收；历史规划已补“最终实现差异”并归档。早期 6 栏方案和未采用 P2 只用于回溯，不自动成为当前缺陷或待办。见 [`归档规划`](../archive/06-productization-closeout/2026-06-23-playback-records-plan.md)。
- `SS-2026-08-10-003`：Billboard 冠军圣殿与艺人详情的冠军单曲数不一致已解决。2026-08-29 的实施与验收基线为 detached HEAD `c21ad22841dcc98b3ce7fa20c9306d4830a1da15`；固定参数和同一 revision 下，Taylor Swift 在 Records、`artist_track_counts.top1`、艺人详情 `info.top1`、详情冠军曲和周榜有效署名中均为 34，301 首上榜歌曲逐行指标差异为 0。后续 51 个 Records 列表的二级排序和冠军专辑独立候选集也已收口；`0b23c442` 与 `46fc7afa` 现已进入 `origin/main` 并包含在生产代码版本 `b0d674bd`。当时未在 `46fc7afa` 单独重跑默认全栈门禁的历史边界仍保留在交付报告。见 [`交付报告`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- 年度总结的 `Manchild/1000`、重复“今年听歌最多的一天”、首次发现和跨章节分母/身份语义问题，已在 [`2026-08-24-yearly-review-semantic-correction.md`](../reports/2026-08-24-yearly-review-semantic-correction.md) 标记为年度修复范围 Pass。
- Billboard 周榜同次数排序本身不是随机行为；当前代码和稳定排序单测已经覆盖单曲、专辑、艺人及输入顺序打乱场景。见 [`test_billboard_stable_ranking.py`](../../backend/tests/unit/test_billboard_stable_ranking.py)。
- 音乐详情加载、专辑/艺人子榜错误空态、专辑发行日期版本消歧、艺人专辑排行日期聚合、Billboard 艺人预聚合逻辑事件粒度和搜索候选/统计解耦，都已有对应交付报告或回归证据；后续若再次出现症状，应按当前代码和真实数据重新复核，不直接复用旧结论。

## 更新记录

| 日期 | 变化 |
|---|---|
| 2026-10-02 | 新增三项专辑元数据代码缺口的稳定 ID；接入统一开发状态总表，确认 `194fd113` 发布记录，并明确历史耗时及外部环境不作为当前值。 |
| 2026-09-13 | `d50f924c` 已 push 并以 dual 模式部署；Actions 与服务器 `verify.sh` 通过，三容器 healthy、schema 73、92,908 条播放、搜索四变体 ready。Tailscale/Serve 当前停止，生产未配置 LLM 凭据，Spotify 未连接；这些外部/secret 边界未被部署脚本擅自改变。 |
| 2026-09-13 | 完成 L1 导入防复发、provider-first 时长解析和人工关系单事务/一次刷新；真实库与 Online Backup 复审仍为 600 review、0 个安全操作，因此不修改真实数据。 |
| 2026-09-13 | 同步 `origin/main=d37e8aaf` 与生产代码 `b0d674bd`；将 Agent V5、L2/L3、Billboard Records、双轨时长与持久快照的仓库/部署状态收口，新增 L1 防复发和人工归并性能开放项。 |
| 2026-08-29 | 完成播放记录规划与当前 5 栏/20 模块实现的差异核对并归档，将 `SS-2026-06-23-006` 更新为已解决。 |
| 2026-08-29 | 同步仓库与验证状态：Billboard 修复已本地提交为 `0b23c442`，Settings 修复已提交为 `62f48299`，均未 push；Settings 移入已解决，播放记录文档核对随后完成并归档。 |
| 2026-08-29 | 完成 Billboard B1–B4 与独立播放排行 R1 的实现、完整 backend unit/contract、frontend test/build、真实库副本/主库 proof 和响应式验收；默认完整全栈门禁未在 `0b23c442` 上运行。将 `SS-2026-08-27-001` 更新为已解决。 |
| 2026-08-29 | 为 Billboard 次要一致性问题和独立播放排行 tie-breaker 建立分阶段修复规划。 |
| 2026-08-29 | 将 `SS-2026-08-10-003` 更新为已解决：在实施基线、真实数据库、固定参数与同一 revision 下完成 Records/艺人详情四变体的稳定实体 ID 集合、计数、排序和逐行指标对账，Taylor Swift 均为 34，差集为空。 |
| 2026-08-30 | 复核 6 个 Records 子页面、8 个后端记录模块的全部 51 个列表，补齐业务二级/后续指标和稳定实体键；冠军专辑候选集只保留 `冠军专辑数 > 0` 的艺人，并同步更新当前规则、计划与交付报告。 |
| 2026-08-27 | 首次建立台账；登记历史未闭环项；确认播放排行同次数不按时长排序；确认 Billboard 周榜按 `total_ms` 作为第二排序。 |

### 2026-10-08 日期精度发布准备补记

复用`SS-2026-09-24-003` / `SS-2026-10-07-001`：新生产副本与有界补证/快照/API验收完成。补修schema88→89重基及独立预检v4/v6版本漂移；101项回归与真实副本漂移拒绝通过，补丁未提交。下一步固定提交SHA，授权后推送发布，再安装正式日期证据；仍未写正式库。见[报告](../reports/2026-10-08-release-date-production-rehearsal.md)。
