# SpotifyStats 开发状态总表

> R3有界归因（2026-10-17）：独立734.634秒诊断正常闭合，14正文与原R2相同、six/103jobs/37来源/strict及恢复通过；A并行168–306ms，B停重采样仍197–213ms，C开采样串行69–81ms。采样有成本，每请求又重复两张1907项artist map及发布上下文，同事务复用候选729a0ed3已本地提交，127定向unit、6 seed公开合同、独立审阅及四hooks通过，新镜像原冷/热门禁待验；不把C当100ms通过。诊断run/guard/两镜像及proof已清理、原16服务/29镜像保全。完整资源HOLD，未推送部署。见[归因报告](reports/2026-10-17-native-hot-request-attribution.md)。

> 收口执行（2026-10-17，R0/R1本地准备完成）：研发c844业务候选与bdcf/ede04验收工具阶段提交仅本地。相同基础/45依赖的实际两镜像构建、正常启动及9容器合成工具链通过；114窗口、两版各原90浏览器合同固定，33纯测试/四hooks与恢复包通过。学校共享宿主及传输已获授权、原生预检READY，R2完整资源合同仍HOLD；未推送或部署。见[R1交付](reports/2026-10-17-oom-images-portable-acceptance.md)及[完整规划](plans/2026-10-17-oom-resource-closeout-plan.md)。

> 原生环境执行（2026-10-17，学校共享宿主已授权）：用户选择限额分批使用原生学校机，七库/ready及两镜像上传核验、shared/UID/guard预检READY。首窗因inode变化实际重建，独立判INVALID_READY_REUSE；第二attempt真实准备通过，但final rank误用无WAL模式而被拒，未启动正式冷进程，均已回传恢复。工具已修复准备/复用、WAL入口和候选阈值范围，135项工具/installer测试及定向审阅通过。用户批准修复后总40分钟；已用向上计583秒，新run基线/候选上限900/917秒、实扣总额不重置，新首组两窗复用/strict/实际恢复及独立审阅通过，累计2023.212秒，工具已本地提交ede04，第一对冷请求候选有效FAIL（hot305/303ms>100ms），R2已停，LRU未启动，三旧run/guard/两镜像及proof暂存清理完成、原16服务/29镜像保全，进入R3有界归因。完整114窗/两版原90及全部资源合同仍待验，未推送/部署。见[学校准入报告](reports/2026-10-17-school-native-resource-admission.md)。

> 收口路线（2026-10-17）：R0候选审阅、R1本地镜像/工具包已完成；学校共享原生环境与列明私密传输已授权，首窗准备/复用/WAL工具缺口已修复并在首个基线验证，首组两启动样本有效，首对冷请求候选热时延失败，R2停止；已清理本次旧资源、原16服务/29镜像保全，先完成R3有界归因，有证据整改后返回原64MiB、多实体50%/LRU、长期并发准入。此后依次为必要整改、最终整合CI/full8、固定发布包批准、唯一首次验收与至少72小时观察。整体OOM仍OPEN，原规划全部门槛继续有效。

> 上一隔离检查点（2026-10-17，有限读取平台验证）：固定空闲/六实体读取各15分钟均进入有限平台：I1先增20.438MiB、M1三轮18请求后RSS470.125MiB稳定，末五分钟中位数跨度/斜率均0。7帧根及203.892MiB估算权重、3+3结果条目稳定复用，18完整正文/六事实/两strict通过。22文件未改，沿用10-16同版本full8；无新增业务修复。原生/default镜像、overview64MiB、长期并发/生产OOM仍OPEN，整合/发布HOLD，暂不提交推送部署。见[本轮验证](reports/2026-10-17-oom-finite-read-platform.md)。

> 上一隔离检查点（2026-10-16，自然启动与累计门禁完成）：日期警告候选A-B-A自然对照，ready低20.719–25.133MiB、idle120低21.492–26.219MiB；27完整响应/六事实/三strict一致。启动峰约994MiB未改善，CPU高3.10–3.32秒信号保留，读取至idle120仍增约83MiB。最终22文件额外hooks及156项fixture回归通过；默认full8同轮PASS/实际0，seed4292/2跳、真实集成186/1跳、前端803/4跳、API157/113与51热基准、三浏览器通过。seed一条AI线程SQLite I/O警告单独保留。整体资源HOLD/Partial，原生/overview64MiB/长期/生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-16-oom-date-warning-startup-validation.md)。

> 磁盘收尾（2026-10-16）：已核验并删除28个实验阶段230个归档重复大文件，合计45.678GiB；可用空间约3→51GiB。正式数据、22候选及Git状态不变，归档与小型证据保留；旧runtime大文件需按清理映射按需恢复。见[清理补记](reports/2026-10-16-oom-arena-paths-and-import-timing.md)。

> 上一隔离检查点（2026-10-16，arena路径与迟载导入/整体Partial）：原288个冻结arena新增109个路径、73个全块可追；外部dict/list缓冲缺失，未全部逐地址还原。新控制窗根图覆盖96.53%高空闲块，确认OpenCC与linecache源码行根。提前导入ready低17.203MiB但峰高16.570MiB，仅实验不入业务。保留日期回填显式dtype候选以消除FutureWarning触发的整份源码缓存；139项、Linux9组27返回/27时长表及七库不变通过，候选完整启动RSS净收益待验。两导入窗18响应/六事实/strict一致。仍22文件，仅本轮2处增改，整体OOM/原生/64MiB/长期OPEN，暂不提交推送部署。见[本轮报告](reports/2026-10-16-oom-arena-paths-and-import-timing.md)。
> 上一隔离检查点（2026-10-16，启动arena持有者与探针校正/整体Partial）：少量分散对象占住大量空闲pool；发现旧逐样本字典探针本身持有时间戳/RSS对象。相同22文件/镜像下改原生缓冲，ready RSS473.914→421.324MiB、arena313→260MiB，仅观测校正且峰值未降。清四个小业务缓存及GC仅释放1MiB；剩余有署名/元数据、迟载模块常量及code缓存帧，仍288个高空闲arena未由受限根图解释。18完整响应/六事实/两strict一致，正式源/业务候选不变。最小修复仅诊断采样器，不新增业务补丁；旧RSS因果收益需按探针自干扰重新限定，整体OOM/原生/64MiB/长期仍OPEN，暂不提交推送部署。见[归因报告](reports/2026-10-16-oom-startup-arena-owner-attribution.md)。

> 上一隔离检查点（2026-10-16，读取驻留归因完成/整体Partial）：原64.785MiB为有界缓存与allocator驻留混合，Python arena总量未增，存活块复用既有空闲池；四个播放表根合计181.076MiB估算，三轮根ID稳定、结果层命中。轻探针有效窗ready481.359→末尾546.652MiB；保留缓存诊断trim下降15.273MiB，定向失效后根及附件全部失活。29项、9份完整响应和两段strict通过，失败首窗保留。未发现需修复的淘汰/未知持有者缺陷，22文件候选字节不变，资源HOLD；下一优先启动Python pool碎片与长期小对象分布/原生资源验收，整体OOM仍OPEN，暂不提交推送部署。见[归因报告](reports/2026-10-16-oom-read-cache-residency-attribution.md)。

> 上一隔离检查点（2026-10-15，合作署名展开与累计候选审阅/整体Partial）：合作署名先以3/2列键展开，再按行位置取独立完整返回表，原去重键、dtype、索引、字段及源表保持；时长中间表在最后消费点释放局部引用。441项（新增24项）、52次旧builder/144榜/26聚合、231组HEAD实体对账通过；后端3634通过/2跳过，另2项存储门槛失败已在未改动HEAD复现，完整后端Partial。三窗27响应/六事实/strict一致。累计HEAD→最终启动峰1303.668→995.094MiB、末尾893.277→607.395MiB；CPU130.840→131.300秒，仅同源仿真观察。二十二文件保留本地，累计审阅完成、资源HOLD/Partial；读取后仍增64.785MiB，下一转向新增缓存owner与空闲分配器驻留及平台期，不再无界追加启动微优化。原生/默认镜像、64MiB、长期和生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-collaboration-credit-expansion-and-cumulative-review.md)。

> 上一隔离检查点（2026-10-15，CPU归因与专辑时长最后消费点/整体Partial）：CPU正反序与三启动对照完成：同一B镜像CPU150.110→196.170秒证明显著波动，B两轮均高于A的信号保留；本轮A/C为138.440/134.050秒，候选未复现同规模增量，稳定回归未证且未全排除。日期处理后释放album_duration与precision局部引用，歌曲入口无用时长owner失活；417项（新增6项）、231组旧builder/693主表与693时长表一致。三窗27完整响应/六事实/strict通过，启动最高采样A/B/C1009.598/1006.820/991.102MiB；C读取后仍增69.758MiB，驻留与整体OOM未收口。二十一文件仅本地，资源HOLD/Partial。下一核对合作facts署名merge及selected/tracks/albums/时长投影的必要列与最后消费点；原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-startup-cpu-duration-attribution.md)。

> 上一隔离检查点（2026-10-15，专辑日期窄表回填候选/整体Partial）：专辑发行日期右键按专辑名/艺人名归并唯一，隔离源4行无重复；owned专辑表用两列键查询后回填，保留原索引/attrs和统计口径。411项（新增19项）、231组旧builder/693主表与693时长表一致，源表不变。两窗各3次merge输入55→2列、返回复用owned投影，9响应/六事实/strict通过。启动最高采样1009.484→1007.039MiB，启动CPU133.340→150.110秒更高，资源收益未证。二十文件仅本地，资源HOLD/Partial。下一核对歌曲时长merge峰点的存活owner与最后消费点，并定位启动CPU增量；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-album-release-lookup.md)。

> 上一隔离检查点（2026-10-15，快进纪录窄表候选/整体Partial）：_skip_storm在assign前投影分组键、play_id和ms_played，原计数、门槛与排序不变。392项（新增19项）、90组完整旧函数对账通过，源表及attrs守恒；旧函数3个复制检查复现、16个对照通过。两窗各9次assign输入52/56/48→5/5/3列，9响应/六事实/strict一致。启动最高采样1014.605→1008.027MiB、读取669.996→668.586MiB，小幅观察未证稳定OOM收益。十九文件仅本地，资源HOLD/Partial。下一核对实体构建专辑发行日期回填merge的整表复制、键唯一性与所有权；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-skip-storm-projection.md)。

> 上一隔离检查点（2026-10-15，Records展示阶段生命周期候选/整体Partial）：Records计算结束后释放事件、终身历史、时长及实体表局部引用，再解析封面；源表和年度预载表不变，结果引用继续保活。373项（新增28项）通过，旧函数24个滞留案例复现、4个对照通过。两窗9响应/六事实/strict一致；三次封面入口工作表引用8/7/7→0/0/0，主输入weakref5→0，首次入口964.086→750.301MiB。启动最高采样1010.586→1003.230MiB、末尾619.754→600.859MiB；读取后增长仅少2.391MiB，整体OOM未收口。十七文件仅本地，资源HOLD/Partial。下一验证_skip_storm的宽表assign最小列集，并对照合作构建持有关系；读取驻留、原生/默认镜像、64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-records-presentation-lifetime.md)。

> 上一隔离检查点（2026-10-15，实体身份复用候选/整体Partial）：实体构建已有逻辑ID时只读复用输入，缺失时保留原分配；源表不变、三张主返回表独立。300项（新增42项）、156组旧builder/468主表及468时长表对账通过。两窗9响应/六事实/strict一致；启动最高采样1020.035→1017.312MiB、读取661.715→658.613MiB，差异较小，不能证明稳定OOM收益。本轮最高采样均已离开实体构建，运行时入口复用标为NOT_OBSERVED，直接复用证据来自单元检查。十六文件仅本地，资源HOLD/Partial。下一按实体构建、Records计算与展示解析核对owner及最后消费点，再选择修复；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-entity-identity-ownership.md)。

> 上一隔离检查点（2026-10-15，合作aggregate局部候选/总体未改善）：合作aggregate只复制必要事件列和完整时长去重列；258项、52次builder对账（48完整/4同异常）、144旧聚合榜及26直接调用一致。两窗9响应/六事实/strict通过；启动最高采样1025.184→1052.148MiB、读取最高采样657.531→663.789MiB，总体资源未改善。十五文件仅本地局部候选，资源HOLD/Partial。候选最高采样在更早的歌曲时长merge，且两份已具逻辑ID的事件表同时存活。下一验证_build_entity_frames复用已具逻辑ID的只读输入，消除身份重复副本并保持所有返回表独立；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-collaboration-aggregate-projection.md)。

> 上一隔离检查点（2026-10-15，合作events生命周期候选/整体Partial）：补齐启动最高采样同点栈，保存事件总数后在最后消费处释放合作完整events表；231项、52次旧函数对账（48完整/4同异常）及144榜相同。两有效窗9响应/六事实/strict一致；启动最高采样1027.375→1020.602MiB、最终低27.102MiB，读取驻留未证稳定改善。十四文件仅本地，资源HOLD/Partial。修复窗最高采样位于合作艺人时长去重，已无完整events引用；首个探针失败窗单独保留。下一处理合作aggregate必要列与局部生命周期，保留事件/署名/时长去重键；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-collaboration-event-lifetime.md)。

> 上一隔离检查点（2026-10-15，合作select候选/整体Partial）：合作纪录select先转换署名键并筛选，再复制命中行；225项、52次旧函数对账（48完整/4同异常）及144份聚合相同。两窗9响应/六事实/strict一致；启动峰1053.914→1031.418MiB，读取峰仅低1.438MiB，最终低11.840MiB。十三文件仅本地，资源HOLD/Partial。绝对峰未捕获同点栈，不能将1017MiB署名merge栈当作绝对峰归因；CPU及观测开销保留。下一先补1031MiB绝对峰同点ownership证据，再定最小修复；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN，暂不提交推送部署。见[本轮验证](reports/2026-10-15-oom-collaboration-select-projection.md)。

> 上一隔离检查点（2026-10-15，歌曲merge副本候选/整体Partial）：歌曲canonical合并路径移除两份merge前宽表副本；194项、歌曲/实体各39组旧函数对账通过。两窗9响应/六事实/strict一致；启动峰1078.055→1062.219MiB，末尾仅低2.781MiB，CPU与采样差异保留，驻留未收口。十二文件仅本地，资源HOLD/Partial。未提交推送部署。见[本轮验证](reports/2026-10-15-oom-track-merge-ownership.md)。

> 上一隔离检查点（2026-10-15，合作纪录键收集候选/整体Partial）：合作纪录键收集消除六次宽表复制，169项/22完整事实及66榜对账通过；两窗9响应/六事实/strict一致。启动采样峰1081.211→1046.914MiB，但不认定全部因果收益；ready/末尾各高约15MiB，读取增长仍约65MiB。十一文件仅本地，资源准入HOLD，整体OOM仍Partial。未提交推送部署。见[本轮验证](reports/2026-10-15-oom-collaboration-credit-keys.md)。

> 上一隔离检查点（2026-10-15，Records启动局部候选/整体Partial）：Records启动生命周期候选保留，150项/39旧函数对账通过；最终启动采样峰1154.004→1097.176MiB，三窗9完整响应/六事实/strict一致。初版异常回退差异已修正并弃用，最终九文件未提交；读取驻留、默认镜像/原生/64MiB/长期及生产OOM仍OPEN。未推送部署。见[本轮验证](reports/2026-10-15-oom-records-working-set.md)。

> 上一隔离检查点（2026-10-15，两项试验不采用/整体Partial）：外层候选134项及35旧函数响应对账通过，但峰值收益未证明，已恢复原八文件。最后一个malloc归因窗ready低204.445MiB，但启动峰高44.379、读取增长高160.105MiB，未改Dockerfile或生产。三窗9响应/六事实/strict一致；启动后空闲pymalloc pool约264.754MiB，下一目标Records启动宽表。未提交推送部署。见[处置与归因](reports/2026-10-15-oom-duration-rejected-allocator-attribution.md)。

> 上一隔离检查点（2026-10-15，艺人专辑中间表局部候选/整体Partial）：研发八文件未提交，专辑子聚合投影与作用域收窄，删除无效全历史副本；120项通过，两窗9完整响应/六事实/strict一致。首次艺人峰增量99.199→69.098MiB，读取峰699.699→678.867；末尾高9.301MiB，arena差异启动后已存在，驻留收益未证明。默认镜像/原生/overview64MiB/长期及生产OOM仍OPEN。见[中间表验证](reports/2026-10-15-oom-artist-album-intermediates.md)。

> 上一隔离检查点（2026-10-15，艺人首次局部候选保留/整体Partial）：研发七文件未提交，新增已发布艺人详情 SQL 前置投影；130项通过，同源两窗9完整响应/六事实/strict一致。首次艺人峰增量126.879→101.590MiB，本轮读取峰724.988→697.523，末尾低8.230MiB；启动峰未改善。默认镜像/原生/overview64MiB/长期及生产OOM仍OPEN，未推送部署。见[艺人首次验证](reports/2026-10-15-oom-artist-first-projection.md)。

> 上一隔离检查点（2026-10-14，局部冷专辑候选保留/整体Partial）：研发六文件保留原mmap+Records启动候选，新增曲目加权六列与Top250切片前八列投影；151项专项/消费、三有效窗33完整响应/六事实/strict通过。冷专辑采样峰增量83/77/107→44/40/69MiB，合法帧预算均321.388MiB；总读取峰/末尾未下降，最高点转至艺人stats首次。未提交推送部署，默认镜像/原生/overview64MiB/长期仍OPEN。见[冷stats投影验证](reports/2026-10-14-oom-cold-stats-track-projection.md)。

> 当前交付（2026-10-14，驻留缓解已发布，整体资源Partial）：固定b1260208已普通推送研发/main；研发及main CI attempt1成功、正式Release attempt2成功，首轮SSH reset保留且仅重试deploy。独立runtime/30源码核验、唯一原首次90/90、116/116 API和三strict/wrapper0通过；RSS起点965.828→396.059、末尾1136.430→748.363MiB，但读取增长与CPU略高、启动高水位基本不变。峰值/64MiB/平台期/OOM继续OPEN；本轮交付、归档与工作树收尾见[正式报告](reports/2026-10-14-native-trim-maintenance-production-delivery.md)。

> 前一本地检查点（2026-10-14，本地INTEGRATED，未推送部署）：业务`8f46b3cb`按授权精确三文件提交，54提交前回归及四项hooks通过；源`8f46b3cb9af8ebc2c546727df089d4d97e7f5309`→main同SHA快进，代码仍等于已通过默认完整8/8的冻结版本。十份协调文档独立提交，三树在本轮安全同步最终HEAD；具体docs SHA与同步收据见[提交映射与恢复入口](reports/2026-10-14-native-trim-maintenance-submission-review.md)。原生资源/OOM继续OPEN、当时发布HOLD；后续授权与实际交付见顶部最新记录。

> 提交前交接（2026-10-14，精确提交审阅READY）：三文件源码与已通过完整门禁的独立归档一致，无阻塞代码发现；main/整合树apply-check实际0，未改目标源码或暂存。地图“新full8未运行”的过时描述已修正；固定研发三文件与main十文档的两份提交草案。下一步等待明确提交指令后执行精确提交/本地整合及SHA映射；不推送部署，资源/OOM继续OPEN、发布HOLD。见[提交整合范围审阅](reports/2026-10-14-native-trim-maintenance-submission-review.md)。

> 提交前核验（2026-10-14，新候选完整门禁READY）：冻结三文件候选默认完整run `20261014T005816.915594Z-9d1a29cefca3` 八阶段同轮PASS/实际0；seed3955、真实集成186、前端803通过，API157/113、51端点1122样本/最高hot P95 267.241ms、三浏览器通过。首轮旧output报告链接preflight失败保留，字节改存snapshot后默认全阶段重跑。源码/旧fixture/原七库不变，owned进程关闭。候选仅研发树未提交/整合，未推送CI或部署；原生峰值/64MiB/平台期/OOM仍OPEN，发布HOLD。完整门禁已通过，后续精确提交范围见最新交接；原始门禁见[当前源码完整门禁](reports/2026-10-14-native-trim-maintenance-fullgate.md)。


> 前一专项检查点（2026-10-13，新队列候选专项READY / Partial）：保持warmup=0，在成功重型维护结束、仍持CPU gate时回收native闲置页。唯一研发树三文件未提交，54定向通过；Linux仿真11次真实回收、9对完整响应（6个200+3个预期404）和两strict通过，ready/final低约343/333MiB，但采样峰高约40MiB、读取增长略大。新full8/CI未运行，main未新增业务整合、未推送部署；原生峰值/OOM仍OPEN。下一步审阅并运行当前源码新门禁，见[维护完成回收候选](reports/2026-10-13-native-trim-maintenance-candidate.md)。

> 上一检查点（2026-10-13，旧6c研发CI通过，发布HOLD）：6c74b9b4仅推送到codex/album-rank-cost，远端main仍为c0d；日常CI attempt1/实际job成功，unit2735、contract571、前端803通过。只读发布准备发现生产warmup=0，e01a4455的full预热回收路径不会触发；三份源fence匹配的私密输入及三模式静态检查已准备，但不推送main、不部署、不调整预热配置。下一步先解决实际启动条件下的调用边界，原生资源/OOM仍开放。见[发布准备与阻塞](reports/2026-10-13-native-trim-release-preparation.md)。

> 本轮核验：验收基线13ec3ec1，研发→main业务映射为同一e01a4455；精确四文件提交，钩子全部通过，提交前13项回归通过。默认完整run `20261013T093055.808116Z-598e44fa152c` 八阶段同轮PASS/实际0；3948后端、186真实集成、803前端通过，API157/113、51端点延迟门禁及三浏览器通过。仿真Linux9对完整响应逐字节相同、两側strict通过，ready/最终idle RSS分别低约875/789MiB；不证明原生时延、构建峰值或OOM修复。详见[审阅、映射与独立归档](reports/2026-10-13-native-trim-candidate-review.md)。

> 2026-10-12 仓库整理：冻结的前端、JSON与艺人范围候选以及旧OOM补丁已独立归档；当前仅详情负责人在 `codex/album-rank-cost` 定位 Top 250 统计成本、切页后的排名计算和启动驻留。共享状态文档统一由协调方合入 main；候选功能通过不代表资源准入或生产收口。见[研发收尾规则](reference/development-delivery-workflow.md)与[本轮处置记录](reports/2026-10-12-development-worktree-closeout.md)。

> 最后核验：2026-10-13（c0d699e5已推送并正式发布；CI attempt1成功，Release attempt1安装拒绝后补齐私密清单、attempt2成功；独立八步运行核验及原首次90/90、116 API/三个strict通过。原wrapper实际1保留，Mounts顺序独立补证通过。首次延迟子项达标，资源合同、整体OOM与手机弹层仍开放）
> 当前进展：Top250时长切片复用和真实断开后的排名协作取消已上线。原index39固定L3专辑直达3125.1→1716.3ms，本轮90/90，较4f3f改善1/0新增失败；116 API和三严格守恒通过。RSS965.828→1160.348→1136.430MiB、CPU38.65秒，较旧4f3f峰/末低353.383/357.262MiB、CPU少34.07秒；仅单窗观察，逐请求64MiB和多轮平台期未证明，OOM仍OPEN。见[本轮正式交付](reports/2026-10-13-album-rank-cancellation-production-delivery.md)。对决保持S0–S5完成，手机弹层独立OPEN。
> 历史生产证据（2026-10-11）：`4f3f2ac0436ba6556bc3ca90773860e18cd9dc77`；CI/Release attempt1共7实际jobs及独立8步runtime通过，三OCI完整SHA/healthy、25源码/3helpers、schema90/rank4/detail4/BB48ready。启动维护自然结束，uvicorn118850/startticks154756440连续；原wrapperexit1与Mounts顺序精确置换补证分列保留，无额外手动重启/预暖/热重跑，私有入口未改。旧83/7、79/11、86/4分别保留。
> 历史日期专项已发布业务代码：`76a4968`；CI attempt2质量/三模式/镜像/部署success，attempt1传输SSH reset保留。
> 历史日期专项生产核验：76a4968、schema89、dual三healthy（12:54）；五年精确年度、两端30次API、两端双视口与最终61表事实守恒通过。连接已恢复，OOM及详情访问后内存增长未代码修复。
> 本轮独立问题：`SS-2026-10-11-001` 手机播放统计加载期间打开时间弹层，数据返回后控件重新挂载、弹层消失。已在未改动前端基线受控复现；门禁仅等待初始页面就绪再验证筛选，产品交互尚未修复，OPEN/P2。
> 本文件是开发状态与下一步工作的统一入口；详细规则、方案和原始验收证据继续在各自文档维护。

## 当前研发与分支处置

| 状态 | 分支 / 候选 | 负责人及下一步 |
| --- | --- | --- |
| R0/R1本地准备完成；R2首对候选有效FAIL；R3诊断完成、第一轮本地候选正确性通过并提交729a0ed3，资源HOLD | `codex/album-rank-cost`；SS-2026-10-08-001，关联SS-2026-10-09-001 | c844业务候选、bdcf/ede04验收工具均本地阶段提交；实际两镜像同基础/45依赖、正常启动及独立容器通路通过，114窗口/两版原90固定，33纯测试与恢复包通过。有限平台证据保留；真实原生64MiB/50%/LRU/长期并发、最终整合CI与生产交付未完成。学校共享宿主与传输已授权，原生预检READY；有效首组耗时2023.212秒；首对热305/303ms超100ms，原失败/全部恢复包独立归档，LRU未启动；三旧run/两镜像已清理、原16/29保全；先归因采样竞争/投影重复成本，再凭证据最小整改返回原合同。见[R1交付](reports/2026-10-17-oom-images-portable-acceptance.md)和[完整收口规划](plans/2026-10-17-oom-resource-closeout-plan.md)。 |
| INTEGRATED；同链统一整合保留 | `codex/versus-detail-integration` | b126发布与唯一首次验收完成，原失败及私密成品独立保存；用于同一OPEN资源合同的候选审阅与主线整合，合同结束后归档，不新增第二研发分支；共享文档只在main维护 |
| ARCHIVED | 前端设置加载、JSON名称传输、艺人范围身份三个候选 | 收益或总体资源准入未证明，保存补丁/证据，不进入main业务代码 |
| ARCHIVED | 历史OOM混合补丁 | 已覆盖内容关闭；未采用的串行锁/窄输入等保留归档，只有当前定位证明需要时才提取 |
| CLOSED（本地） | CI挂起诊断分支 | 主要修复已有主线对应，历史提交与差异已保存；远端未删除 |

实现、提交、推送和发布分别记录；[逐项处置与恢复入口](reports/2026-10-12-development-worktree-closeout.md)。

## 当前概况

核心产品已经具备个人音乐头版、播放分析、音乐档案、年度总结、个人 Billboard、音乐查找和实体详情。最近一轮开发集中于持久快照与性能、导入治理、多艺人署名、运行资源和 AI Agent V6。

专辑完整分页与稳定艺人证据已按固定 `daf098ca` 推送、通过CI并正式发布，业务内容与完整本地验收的 `8464ffa6` 一致。生产schema85→88，54份完整目录/位置、154份艺人证据及1,175条必要的缺失简化曲目元数据完成有界安装；35类原始/治理事实保持。封面、合作曲排行及艺人独立链接保留。下面的优先级是排期建议，其余待办与探索记录不表示已经启动实施。

| 状态维度 | 已确认结论 | 证据范围 |
| --- | --- | --- |
| 实现与仓库 | 日期精度98dea609/6edbe051/c5e3314b与空值9c360714已集成为7f7185cf并合入本地main；署名生产交付保留原证据 | [联合验收](reports/2026-10-07-release-date-stats-integration.md)、[署名验收](reports/2026-10-06-track-credit-resolution-acceptance.md) |
| CI | 76a4968 attempt2质量、full/showcase/dual、镜像构建与部署全部success；attempt1传输SSH reset保留 | [正式流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37721980387) |
| 生产发布 | 76a4968、schema89发布完成；92份日期/78项目精度、五年年度、两端30次API/双视口及保护事实通过 | [生产验收](reports/2026-10-08-release-date-production-delivery.md)；当前三healthy，资源OOM单独跟踪，不称生产默认完整全栈Pass |
| 默认完整全栈 | 本地7f7185cf干净版本八阶段同轮PASS，24分22秒；后端3424+186、前端763/4skip、API157+113和三浏览器通过。生产专项保持原版本与范围 | [联合验收](reports/2026-10-07-release-date-stats-integration.md)，run `20261007T150856.854749Z-290c0b989199` |
| 真实模型与终端 | V6 有本地真实模型历史证据；封面及合作曲有实际 HTTPS/桌面手机视口验收 | 生产 LLM、真实 OAuth 与物理手机仍另行验收，不能由发布或模拟视口通过推定 |

## 已完成的主要开发

本节的“已完成”表示相应开发范围已经实现并有验证证据。各行原始验证的日期与版本见链接；部署列指业务代码已包含在当前发布中，不表示逐项重新完成生产业务验收。

| ID | 方向与已交付能力 | 实现 | 验证证据 | 部署 | 最后核验 |
| --- | --- | --- | --- | --- | --- |
| DONE-01 | 首页、播放分析、音乐档案、年度总结、音乐查找与详情的当前产品结构；共享统计事实的响应式展示 | 已实现 | [项目介绍](../README.md)、[问题台账已解决项](issues/2026-08-27-issue-register.md)、[报告索引](reports/README.md) | 代码已发布 | 2026-10-02 |
| DONE-02 | L2/L3 身份、专辑归属与逻辑事件；次数/时长双轨；播放排行及 Billboard Records 稳定排序 | 已实现 | [L2/L3 修复](reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)、[双轨语义](reports/2026-08-31-billboard-count-duration-semantics-research.md)、[榜单一致性](reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md) | 代码已发布 | 2026-10-02 |
| DONE-03 | 全应用持久结果与快照、后台构建、旧结果连续展示；搜索共享构建和增量维护 | 已实现 | [全应用性能成果](reports/2026-09-21-full-application-performance-optimization-outcome.md)、[交互收口](reports/2026-09-21-stage8-snapshot-and-billboard-ux-closeout.md) | 代码已发布 | 2026-10-02 |
| DONE-04 | 持久化导入工作台、来源与指纹基线、原子发布、故障恢复及旧库升级 | 已实现 | [导入治理最终验收](reports/2026-09-21-import-governance-final-acceptance.md) | 代码已发布 | 2026-10-02 |
| DONE-05 | Spotify Track 有序多艺人证据、自动有效署名投影、身份冲突保留旧结果与人工覆盖优先 | 已实现；提交 `56a23500` / `9eccd00e` | [证据交付](reports/2026-09-24-spotify-track-artists-evidence-delivery.md)、[自动署名记录](CHANGELOG.md#2026-09-27spotify-track-多艺人自动署名) | 代码已发布；本地正式库回填有历史记录，生产回填量未重测 | 2026-10-02 |
| DONE-06 | 日常轻量启动、构建输入清单、预热分层、重型任务排他与长期资源优化 | 已实现；提交 `a0df33a4`，集成 `c1acbec6` | [资源专项与完整全栈](reports/2026-09-22-runtime-resource-optimization.md) | 代码已发布 | 2026-10-02 |
| DONE-07 | V6 统一模型步骤、持久恢复、预算与租约、冻结年报上下文、审核章节渐进交付及 SSE 恢复 | 已实现；提交 `8edcd1c8`，集成 `1f5863a8` | [真实模型及最终全栈](reports/2026-09-22-ai-agent-v6-final-acceptance.md)、[集成与 81→84 升级](reports/2026-09-27-ai-agent-v6-local-integration.md) | 代码已发布；生产模型可用性待核验 | 2026-10-02 |
| DONE-08 | 160/320/640px WebP、按尺寸/DPR 加载、新下载生成、缺失回退及有界补建；CI 浏览器依赖延迟导入 | 已实现；历史 `84168eba` / `194fd113`，扩展 `f139ec4d` / `814ea7cb` | [封面验收](reports/2026-10-03-cover-image-optimization-acceptance.md)、[资产规则](reference/cover-artwork-delivery.md) | `814ea7cb` 已发布；生产三档各 4,360 current，新增 8,720 个派生文件，原图 stat 不变 | 2026-10-03 |
| DONE-09 | 普通备份每周/28天；发布恢复材料保留最近4版（含current/previous），48小时缓冲 | 周备份 `3e608f22` 已生效；本批次提交自动收尾工具与正式workflow接入，23项专项通过 | [生产备份与收尾规则](../deploy/production/README.md)；10月15日腾讯云清理释放约6.58GiB，根盘86%降至68% | 工具已用于本轮服务器清理；后续成功发布由workflow自动执行，本批次不触发应用重新部署 | 2026-10-15 |
| PLAN-2026-10-02-001 | 合作曲排行按有效署名统一三个榜、全部参与艺人、占比与 L3 实际版本过滤 | S1–S6 已完成；`fa683d97` 已推送 | [验收报告](reports/2026-10-02-collaboration-ranking-acceptance.md)、[已完成规划](archive/06-productization-closeout/2026-10-02-collaboration-ranking-plan.md)；后端 unit 2,104、contract 443，前端 690 passed / 4 skipped，五视口与生产两端通过 | 已正式发布，默认三范围与 L3 ready；6,518 次 / 9.6%，原始数据及其他 Records 不变 | 2026-10-02 |
| SS-2026-09-24-001 | 专辑完整分页、可靠发行位置与只读消费者 | 固定输入4f9a01ff，业务8464ffa6；已实现、完整本地验收 | [最终集成](reports/2026-10-03-album-metadata-final-integration.md)、[生产交付](reports/2026-10-03-album-metadata-production-delivery.md) | daf098ca已发布；生产有界54份目录/位置和缺失简化曲目元数据已补齐 | 2026-10-03 |
| SS-2026-09-24-002 | Album有序稳定ID、canonical解析、人工优先与冲突保留 | 固定输入8f638494；已实现、完整本地验收 | [专项](reports/2026-10-02-album-artist-evidence-verification.md)、[生产交付](reports/2026-10-03-album-metadata-production-delivery.md) | daf098ca已发布；154份艺人证据/177条署名已安装，13个Album含17条未解析行保留审核 | 2026-10-03 |
| SS-2026-10-06-001 | 曲目署名来源优先级与标题解析 | S0–S5已完成；人工优先、完整名保护和未知候选防复发 | [验收记录](reports/2026-10-06-track-credit-resolution-acceptance.md)、[归档计划](archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)；S4八阶段PASS、S5专项与实际生产通过 | 2faadc64已发布；Safe3位、Holidays完整乐队、合作曲6518/9.6%，事实与人工决定守恒 | 2026-10-07 |
| SS-2026-09-24-003 | 发行日期来源精度、旧值降级、日期比较与展示 | 已实现并集成为7f7185cf；发布补修76a4968 | [精度合同](reference/release-date-precision.md)、[生产验收](reports/2026-10-08-release-date-production-delivery.md)、[归档计划](archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md) | 76a4968/schema89；92来源与78项目精度、五年年度、两端API/双视口及事实守恒通过 | 2026-10-08 |
| SS-2026-10-07-001 | 非榜单详情安全空态与真实零播放恢复 | 已实现，9c360714集成为7f7185cf | [联合全栈](reports/2026-10-07-release-date-stats-integration.md)、[生产验收](reports/2026-10-08-release-date-production-delivery.md) | 76a4968；Afterlife空态、Midnights真实0及切回正常统计，两端API/双视口通过 | 2026-10-08 |

## 近期生产收口

`SS-2026-10-06-001` 已完成：生产2faadc64正式发布并完成两端API与桌面/手机视口验收，15曲目减少18条错误/冗余有效署名；My Heart仅覆盖层单条纠正，revision38 ready，原始事实及34条既有人工覆盖保持。失败发布和17表仅复用补修证据保留；别名歧义与真实补充继续独立维护，不新增全库审核。见[归档计划](archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)及[验收记录](reports/2026-10-06-track-credit-resolution-acceptance.md)。最后核验2026-10-07。

`SS-2026-10-03-004` 已随2faadc64发布：Records歌曲ID统一整数，兼容1493.0并保留查询/锚点，不改统计或写回公开快照。生产公开手机实际点击vampire和旧URL规范化通过；原本地110/39项专项保持原日期。见[生产验收](reports/2026-10-06-track-credit-resolution-acceptance.md)，最后核验2026-10-07。

`SS-2026-10-03-003` 已随2faadc64发布：公开桌面与手机8个时间选项可见，缺失日范围仍snapshot_unavailable/503并保留入口；公开GET不冷建。原[本地专项](reports/2026-10-03-public-analysis-time-ranges.md)保留历史范围，[生产验收](reports/2026-10-06-track-credit-resolution-acceptance.md)另列，最后核验2026-10-07。

`SS-2026-10-03-001` 全站封面优化：S0–S5 已完成；业务版本 `814ea7cb` 已提交、推送并正式发布。默认八阶段同轮全栈 PASS，前端 722/4skip、后端 3178+187、API 157+113、三浏览器通过。生产三容器 healthy，8,720 个派生文件补齐，三档各 4,360 current；原图 stat 和原始播放表数量不变。实际 HTTPS 核心 60 + 四视口 192 样本及 15 项有效交互完成；高清 Phone 榜单体积与非真机边界单列。最后核验 2026-10-03。见[已完成方案](archive/06-productization-closeout/2026-10-03-cover-image-optimization-plan.md)、[报告](reports/2026-10-03-cover-image-optimization-acceptance.md)。

## 尚未完成与待验收

P1 表示建议优先推进，P2 表示后续排期。尚未实现的修改也尚未验证和发布；部分完成项只按已交付范围记录。`外部待验收` 与 `数据审核` 不是尚未编写代码的同义词；历史数量和环境状态未经本次现场重测，不作为当前值。

| ID | 事项 | 状态与剩余工作 | 优先级 / 下一步 | 证据或方案 | 最后核验 |
| --- | --- | --- | --- | --- | --- |
| SS-2026-10-08-001 | 详情与年度维护资源 | OPEN / Partial：R0/R1本地准备完成，学校原生首批暴露工具缺口，资源HOLD | P1：共享宿主/列明传输及限额分批已授权，native预检READY；准备/六成品复用/WAL工具修复已通过135项测试，首组正在原生执行；旧失败按583秒扣入总40分钟。首组有效后执行64MiB/50%/LRU/长期准入，原始失败保留，最终整合CI/full8、发布及72小时观察仍待完成。 | [R1交付](reports/2026-10-17-oom-images-portable-acceptance.md)、[完整规划](plans/2026-10-17-oom-resource-closeout-plan.md) | 2026-10-17（隔离；未新验Spotify生产） |
| SS-2026-10-08-002 | 榜单对决个人播放统计延迟 | COMPLETED / RELEASED；c587正式CI/NoDeploy/三模式/镜像/部署及独立runtime通过；原公开FIRST14/28全Pass（最大1.669秒）、420秒完整资源/守恒、96 API与三denial通过。人类明确仅公开HTTPS，S0–S5完成，历史失败保留 | P1：三库准备补修已验证，c587本地固定/hooks与清单九步通过；授权四文件清理/上传/push已完成，原公开入口已通过；私有SSH HTTP48仅为功能证据。本项完成；私有入口保持现状。详情独立首次已完成：39/90性能通过、116功能及完整读取守恒通过，详情与OOM仍开放 | [完整规划](archive/06-productization-closeout/2026-10-08-versus-personal-statistics-performance-plan.md)、[验收报告](reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)第21.9–21.13节、[台账](issues/2026-08-27-issue-register.md) | 2026-10-09 |
| SS-2026-10-09-001 | 音乐详情榜单成绩首次加载与附属计算 | 首次延迟子项PASS；整体OPEN/Partial（资源未收口）。b126新首次90/90、116/116 API/三strict及wrapper0，旧c0d90/116与旧失败保留 | P1：时延子项已达标；资源归SS-2026-10-08-001同链维护。当前窗口不热重跑，手机弹层另行处理 | [新生产交付](reports/2026-10-14-native-trim-maintenance-production-delivery.md)、[规划](plans/2026-10-09-music-detail-chart-performance-plan.md) | 2026-10-14 |
| SS-2026-10-11-001 | 手机播放统计加载时弹层状态丢失 | OPEN/P2；未改动前端基线受控复现，加载中打开时间弹层后，数据到达导致控件重新挂载并关闭弹层；尚未产品修复 | P2：独立保持控件/编辑状态连续性；本轮门禁只等待初始页面就绪，保留原超时与应用后断言，不用门禁Pass关闭产品问题 | [台账](issues/2026-08-27-issue-register.md)、[受控复现](reports/2026-10-09-music-detail-chart-performance-acceptance.md)本地专辑候选节 | 2026-10-11 |
| SS-2026-08-24-004 | 全栈门禁耗时与重跑成本 | 部分完成：分阶段、preflight、排他锁与去重已做；25 分钟及三次低干扰稳定验收未闭环，安全证据续跑/分片未交付；本轮单次24分22秒 | P1：保存当前版本阶段计时与慢测试 profile，依新证据优化重复计算 | [门禁计划](plans/2026-08-24-fullstack-gate-duration-optimization-plan.md)、[问题台账](issues/2026-08-27-issue-register.md) | 2026-10-07（单次计时，不代表三次稳定收口） |
| SS-2026-08-06-005 | PWA 双平台与 OAuth | 外部待验收：PWA 工程已完成，iPhone/Android 安装、键盘、安全区、返回及真实 consent 回跳缺闭环证据 | P1（需要移动使用时）：先核验受控 HTTPS，再完成真机矩阵 | [PWA 路线](plans/2026-08-06-appification-pwa-capacitor-plan.md)；9 月 13 日环境记录只是历史快照 | 2026-10-02（文档核对，未真机验收） |
| ACCEPT-01 | 当前版本业务验收 | 专辑、封面与合作曲生产专项已闭环；真实AI、OAuth和物理手机仍待验收 | P1：生产真实AI与目标终端分开登记，不以模拟视口推定 | [专辑生产报告](reports/2026-10-03-album-metadata-production-delivery.md)、[验证规则](reference/fullstack-verification.md) | 2026-10-03 |
| DATA-01 | 存量 L1 身份歧义与自动署名冲突 | 数据审核：缺少唯一目标或可信身份时保留 review；不把审核队列清零作为开发完成条件 | P2：先刷新只读差异与数量，按新证据人工处理；历史约 600 条 L1 review 和 21 个署名冲突不是当前数量 | [L1 收口](reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)、[署名记录](CHANGELOG.md) | 2026-10-02（未重测数据） |
| DATA-02 / SS-2026-10-03-002 | 生产搜索派生外键遗留 | 已有60,294条FK orphan，Album维护前后集合不变；当前四精确变体读取门禁通过 | P2：先在副本调查轮转/清理合同；本轮未删除或修复 | [生产报告](reports/2026-10-03-album-metadata-production-delivery.md)、[台账](issues/2026-08-27-issue-register.md) | 2026-10-03 |
| DATA-03 | Album未解析身份审核 | 13个Album的24条艺人行中17条未解析，保持来源证据；不猜测canonical，不批准关系 | P2：取得唯一稳定身份后人工治理；不是代码交付失败 | [生产报告](reports/2026-10-03-album-metadata-production-delivery.md) | 2026-10-03 |

建议开发顺序：优先解决已取得生产证据的OOM与详情内存增长，再推进真实模型/终端验收和门禁效率。日期精度、详情空统计及其生产专项已收口；资源缓解不等于代码问题解决。身份歧义、FK清理继续独立维护。

对决个人统计优化与详情优化由本任务统一整合发布。业务S4已通过，6430发布失败保留；部署修复cb8d05b1 hooks、新默认完整八阶段和成品准备上传通过，正常推送后CI/NoDeploy与Release质量/三模式/镜像通过，但三次deploy均失败、旧9dd恢复健康。新三库准备补修已通过相关回归及Linux隔离验证；新范围已获真实人类确认，四文件精确清理、上传及正常push c587均实际完成。c587单次正式CI/NoDeploy/Release及11实际jobs均success，实际三OCI完整SHA/healthy、schema90/search4/rank4/detail4/BB48ready。独立只读核验0、启动维护自然结束；原公开FIRST14/28及420秒整页资源窗口/完整守恒、两面96 API和三denial均通过。人类明确只验公开HTTPS，私有保持停止现状；对决完成。一次另行授权重启后的详情原90只有39通过，116功能及三个完整读取窗口通过；冷页面与高驻留继续修复，整站OOM未关闭。

## 可以探索的方向

以下均未登记为在开发项目。启动前先回答收益与资源条件；探索通过后再形成实施计划。

| ID | 方向 | 当前状态 | 价值与启动条件 | 来源 | 最后核验 |
| --- | --- | --- | --- | --- | --- |
| EXPLORE-01 | MusicBrainz 第二署名来源 | 仅规划 | 在隔离样本中证明能发现 Spotify 无法解决的署名/身份冲突；稳定 ID、限流和来源条款明确后再接入 | [元数据路线](plans/2026-09-23-multi-source-music-metadata-roadmap.md) | 2026-10-02 |
| EXPLORE-02 | 歌曲级语言统计 | 仅规划 | 支持多语言艺人的具体录音统计；先明确来源、人工标注样本、混合语言/无歌词/unknown 和消费者范围 | [元数据路线](plans/2026-09-23-multi-source-music-metadata-roadmap.md)、[现有艺人语言规则](reference/artist-language-statistics.md) | 2026-10-02 |
| EXPLORE-03 | Apple Music、Cover Art Archive、Discogs / Wikidata | 延后 | 先证明凭据与维护成本值得；封面替代先有可靠 release 身份，长尾来源优先辅助人工核验 | [元数据路线](plans/2026-09-23-multi-source-music-metadata-roadmap.md) | 2026-10-02 |
| EXPLORE-04 | 缺图兜底的身份准确性 | 待量化 | 已有 ID 时优先按 ID 读取；先统计名称搜索误配率，不凭缺图现象批量替换 | [元数据路线 §10](plans/2026-09-23-multi-source-music-metadata-roadmap.md#10-2026-09-24-spotify-现有字段利用审计后续问题) | 2026-10-02 |
| EXPLORE-05 | 专辑真实时长参与 LP/EP 分类 | 待量化 | 依赖完整曲目表，比较真实总时长与当前估算对分类的影响，再决定是否修改 | [元数据路线](plans/2026-09-23-multi-source-music-metadata-roadmap.md)、[分类消费者](../backend/services/analysis_stats_service.py) | 2026-10-02 |
| EXPLORE-06 | 长期浏览器 physical footprint | 观察项 | 历史资源门禁已通过；保留 footprint 增长诊断，仅在可重复增长或使用影响出现时重新立项 | [资源报告](reports/2026-09-22-runtime-resource-optimization.md) | 2026-10-02（未重新测量） |

## 明确暂缓与需要重新决策的事项

| 方向 | 当前决定与重新启动条件 | 依据 | 最后核验 |
| --- | --- | --- | --- |
| Capacitor / 原生安装包 | 暂缓；先完成 PWA 真机与 OAuth，并明确 App Store 或安装包分发需求 | [PWA 路线](plans/2026-08-06-appification-pwa-capacitor-plan.md) | 2026-10-02 |
| 微信小程序 | 不作为主路线；明确微信分发与平台能力需求后另行评估 | [PWA 路线](plans/2026-08-06-appification-pwa-capacitor-plan.md) | 2026-10-02 |
| 异机备份扩展 | 早期 PWA 计划有此要求，尚无闭环证据；后续已选择简化日常备份，是否继续作为移动发布条件需重新确认 | [PWA 历史要求](plans/2026-08-06-appification-pwa-capacitor-plan.md)、[当前备份手册](../deploy/production/README.md) | 2026-10-02（未检查异机设施） |
| 旧重型 account、歌词/发行档案等详情消费入口 | 当前产品边界不启用；只有新的产品决策才重新立项 | [项目约定](../AGENTS.md)、[元数据规则](reference/music-metadata-management.md) | 2026-10-02 |

## 如何持续维护

1. 开始开发前查本表，复用已有 ID；实际开始实现后标为“进行中”，填写当前阶段与下一步。提议、授权和实施状态分开记录。
2. 一项开发完成、验收变化、提交/推送/发布或决定暂缓时，在同一工作范围更新对应行与最后核验日期。只做代码修改时不能把验证或部署一起标为完成。
3. 新发现的问题先在[问题台账](issues/2026-08-27-issue-register.md)保留稳定 ID、复现与证据，再在本表维护简要结论和优先级；探索方向先登记来源与启动条件。
4. `reference/` 管规则，`plans/` 管未完成方案，`reports/` 管带版本和日期的交付证据，`archive/` 保存完成或取代的计划。本表只保存当前摘要与链接，不复制完整历史。
5. 历史报告中的“未提交/未部署”描述其当时范围。后续状态在本表注明新 SHA 和证据，不把旧报告改写为曾经验证了新版本。
6. 每次更新运行 `python3 scripts/docs_audit.py --include-archive` 和 `git diff --check`；若改变共同工作约定，保持 `AGENTS.md` 与 `CLAUDE.md` 完全一致。

### 本次核验与维护记录

2026-10-13 研发分支CI与发布准备：按授权仅推送现有研发分支6c74b9b4，远端main仍c0d；CI38414168750 attempt1、实际job115354026493成功，unit2735/contract571/前端803通过。以readonly源及规范成品工具准备三份私密输入、本地验证三模式；512MiB隔离Billboard导出工具OOM失败保留，改为本地关闭副本规范验证现成清单并比对live fence。生产身份、启动时间和源物理状态未变；发现warmup=0使当前回收路径不可达，发布HOLD，不改配置、不推main、不部署。当前协调文档未新增提交，详见[准备报告](reports/2026-10-13-native-trim-release-preparation.md)。

2026-10-13 资源候选审阅、本地提交与整合：在13ec3ec1基线核对四文件冻结SHA、独立归档和默认Phase5/full8；用户授权后精确提交e01a4455，13项回归及提交钩子通过。业务提交原样快进进入main，六份原文档逐字节保护后统一更新状态及映射；文档作为独立状态提交保存，安全同步既有研发/整合树。仿真驻留收益与本地功能通过分列，原生资源、64MiB、平台期、峰值和OOM仍开放；不追加运行副本、仿真配对、生产请求、推送或发布。

2026-10-02：核对主分支与 GitHub、近期提交、计划/问题/报告及专辑元数据消费代码；读取 `194fd113` 成功发布记录。新增总表与维护入口，归档已完成 V6 计划，并更正元数据路线中的过时署名状态。共享工作区中同期出现合作曲排行计划与配套代码，按进行中观察登记，未修改该任务的代码或计划。未重新执行应用全栈、真实模型、生产现场或真机验收。

2026-10-02 合作曲收口补记：`fa683d97` 完成正式发布，S1–S6 全部验收；迁移仅更新派生修订机制，服务器原始数据不变，默认快照及 L3 当前，实际桌面和手机视口验证通过。未执行默认完整全栈或物理手机验收；本总表原有其他文档工作仍单独保留，不混入合作曲业务提交。

2026-10-03 `PLAN-2026-10-02-001` 署名交互补修：歌曲/专辑单元格复用榜单艺人链接，多艺人用 ` · ` 分隔，独立点击进入对应艺人详情；本地专项 25、前端全量 693 passed / 4 skipped、构建与五视口/桌面手机实际跳转通过。补修 `3a4e6310` 已提交、推送并[正式发布](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37033411857)，CI 全部 success；服务器三容器 healthy、独立生产门禁通过，线上桌面/手机实际点击与完整长署名通过。本次修复已收口，无迁移或统计重算需求；未改变外部入口。详见[补修验收](reports/2026-10-02-collaboration-ranking-acceptance.md#2026-10-03署名链接补修)。

2026-10-03 `SS-2026-09-24-001/002` 联合本地收口：基线 `7b9a1f4e`、固定输入 `4f9a01ff` / `8f638494`，隔离分支 `codex/album-metadata-integration`。默认完整 run `20261003T020011.704402Z-87d26d4d09e5` 八阶段同轮 PASS；seed 3,201、真实 integration 186、前端 697 passed（各自 skip 单列于报告），三浏览器及 1440/390 两视口专项通过。源库仍 schema 81，迁移/补证只在副本，原始事实及有效 Track 署名指纹不变。联合报告保存在 `/Users/benjaminlei/Code/202605-SpotifyStats-album-integration/docs/reports/2026-10-03-album-metadata-integration-verification.md`。61 文件候选已暂存供审阅，未新增集成提交/推送/部署；后续 main `f139ec4d` / `814ea7cb` 尚未纳入该验收范围。正式迁移、Album 回填、身份审核与生产验收仍待授权和固定合入版本。

2026-10-03 最终集成提交（合入前历史记录）：`ad9cc3c6` 保存本任务，`8464ffa6` 整合封面主线 `814ea7cb`，`3da5a3ec` 登记最终验收；新默认完整 run `20261003T070853.211207Z-f917b9718886` 八阶段同轮 PASS（22分40秒），seed 3,231 / integration 186 / 前端 726 passed，两视口专项和最终守恒完成。最终报告位于 `/Users/benjaminlei/Code/202605-SpotifyStats-album-integration/docs/reports/2026-10-03-album-metadata-final-integration.md`。主目录封面会话当时仍在验收，main 尚未合入；全局总表与 V6 归档保留未提交。未推送本任务、未部署、未写正式数据库。

2026-10-03 安全合入收口：确认封面会话完成后吸收其收口 `85a44cb8`，主目录已 fast-forward 到 `fe99756b93f64754d8f8cb21e8bd52be894e3729`；业务内容等于上述已完整验收的 `8464ffa6`。两次合入只对重叠文档做精确路径保护和三方恢复，其他已有修改、删除、未跟踪文件及模式逐项保持，暂存区为空；保护点在隔离目录 ignored `output/album-final/main-preservation-85a/` 与 `main-preservation-824-reviewed/`，本任务临时 stash 恢复核验后清理，其他 stash 保留。主目录现有源库仍 schema 81，未写正式数据；正式迁移、Album 有界回填、身份审核、CI 与生产验收仍须外部授权。代码与任务专有文档已本地提交；本总表和继承的全局文档/V6 归档继续保留未提交。未推送本任务、未部署。证据见[最终报告](reports/2026-10-03-album-metadata-final-integration.md)。

2026-10-03 统筹文档收口与生产授权：用户同意先提交本 session 的开发状态文档，再由现有艺人证据 session 负责固定版本推送/CI、备份迁移、限定 Album 证据回填和生产验收。总表顶部已区分本地 `fe99756b` 与已发布 `814ea7cb`；维护路线 §10 和历史归档链接，保留既有任务证据。此次文档提交不改变业务代码或正式数据，生产交付结果由执行 session 后续登记；发行日期精度尚未启动。

2026-10-03 专辑生产交付：按已核实授权固定推送daf098ca，CI质量/三模式及发布attempt2全部success，完成生产Online Backup、85→88及有界维护。初次增量遗漏的简化曲目元数据经新副本验证后仅插入1,175条缺失行，原始歌曲/署名和35类治理事实保持。生产实际消费者、精确年度缓存和HTTPS专项完成；独立登记13个Album未解析与60,294条既有搜索派生FK。原本地完整门禁报告保持其历史边界；本轮专项不称生产默认完整全栈。已完成两份方案归档，详见[生产报告](reports/2026-10-03-album-metadata-production-delivery.md)。

2026-10-08 发布准备：新生产Online Backup与最终source marker一致；副本88→89及92来源/78项目补证通过，56表/有效署名与四aggregate事实守恒。修复重基缺89和独立预检v4/v6版本漂移，101项回归、真实重基/漂移拒绝、两种运行面API和同源仅复用候选通过；2022–2026确定性年度等独立快照已准备。补修已同步主工作区但未提交，未推送/部署/写正式库；原完整全栈范围保持，见[本轮报告](reports/2026-10-08-release-date-production-rehearsal.md)。

2026-10-08 生产执行授权：用户明确授权提交发布补修、推送main并完成正式发布，再执行固定92份日期来源补证、生产快照准备及专项验收；当前进入执行阶段，结果待后续证据登记。

2026-10-08 生产专项收口：76a4968正式CI attempt2及部署通过，schema89、固定92来源/78项目精度安装及幂等完成。连接恢复后取得global OOM日志，受控backend重启并逐年有界准备五年exact年度；两端30次API、私有/公开双视口与最终61表事实守恒通过，12:54三healthy。日期/详情空统计任务收口、计划归档；OOM及详情访问后内存增长保留SS-2026-10-08-001，运维缓解不算代码修复。本轮是生产专项，原完整全栈保持其版本，详见[报告](reports/2026-10-08-release-date-production-delivery.md)。
