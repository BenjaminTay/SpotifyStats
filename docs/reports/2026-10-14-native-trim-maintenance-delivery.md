# 维护完成回收门禁与生产交付

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。本地完整门禁、提交整合和b1260208生产交付合并。维护后回收与详情加载体验按实际通过范围结项，读取增长、CPU、峰值和整体OOM仍按原报告边界判断。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [维护完成原生回收候选：当前源码默认完整门禁](#维护完成原生回收候选当前源码默认完整门禁)
- [维护完成回收候选：提交与整合范围审阅](#维护完成回收候选提交与整合范围审阅)
- [维护完成原生回收：生产交付与首次验收](#维护完成原生回收生产交付与首次验收)

## 维护完成原生回收候选：当前源码默认完整门禁

原记录：`2026-10-14-native-trim-maintenance-fullgate.md`。

2026-10-14（Asia/Shanghai）；SS-2026-10-08-001，关联SS-2026-10-09-001。

### 结论

**当前未提交三文件候选的本地默认全栈门禁PASS，8/8必需阶段同轮通过，实际退出0。** run `20261014T005816.915594Z-9d1a29cefca3`，总耗时1811.010秒。不是复用旧6c的CI/full8，也不是--from/--only局部结果。

唯一研发树仍基于6c74b9b416dbba47b354b850bdfe678f26ece63a、dirty=true；变更为 `backend/core/job_queue.py`、`backend/tests/unit/test_job_queue.py`、未跟踪的 `backend/tests/unit/test_job_queue_native_memory.py`。实际源码SHA与10-13冻结记录及运行前后均一致，新7用例在完整seed XML中实际执行并通过。产品代码未整合到main；本轮未commit/push/CI/deploy，也无生产API、重启、预暖或配置修改。

发布仍HOLD，资源问题OPEN / Partial。此门禁使用macOS，原生回收helper为no-op；保留[10-13 warmup=0 Linux仿真](2026-10-13-native-trim-review-and-preparation.md#warmup0-重型维护完成边界的原生回收候选)的原范围：11次实际回收保持缓存，9对完整响应/两strict通过，ready/final低343/333MiB，但采样峰高约40MiB、读取增长略大。完整门禁不能把这些资源边界改判为通过。

### 当前完整结果

| 阶段 | 实际状态 | 秒 |
| --- | --- | ---: |
| preflight | PASS | 8.260 |
| quality | PASS | 70.626 |
| backend | PASS | 755.983 |
| api | PASS | 227.708 |
| browser-routes | PASS | 412.950 |
| browser-interactions | PASS | 81.759 |
| browser-inventory | PASS | 46.146 |
| browser-compat | PASS | 207.443 |
| optional | NOT_RUN | 0.000 |

- 质量：pre-commit hooks、文档审计、CI parity、Ruff、frontend test/build通过；前端803 passed/4 skipped。Phase5由父门禁执行，unit/contract的独立marker重复明确跳过，backend阶段负责整个seed和真实集成，符合现有规则。
- 后端：seed 3955 passed/2 skipped；真实数据integration 186 passed/1 skipped，XML无失败。seed约364.52秒，integration约378.41秒；警告原文保留。
- API：smoke157/157、boundary113/113；51端点×22次，共1122样本，500ms阈值未改，slow_count=0，hot P95无null、最高267.241ms。外部进程首次请求不冒充cold，后续warm不推断cache hit。
- 浏览器：路由、重点五视口、桌面/移动交互及图表、控件/长列表、Chromium/Firefox/WebKit全部通过。WebKit是测试引擎，不代表真机Safari；手机初始加载时弹层重挂载问题仍按原独立台账OPEN。
- optional未运行；production preview、真实LLM/OAuth/物理手机、原生amd64资源和生产首次窗口不由本轮推定。

### 数据与运行隔离

复制前确认旧本地fullgate fixture无开放消费者，文件逐一SHA核对，包括已有WAL/SHM。旧fixture已包含年度成品；新运行副本复用其事实，不因生产关闭预热而额外生成年度缓存。排名规范validate/install/verify实际0，安装器在新副本生成自己的file-local lineage。当前服务全程warmup=0，外部封面使用门禁规定default1，端口仅loopback8138/5188。

默认门禁只指向新自有runtime；integration插件另建一份session可写副本。旧fixture与原关闭七文件备份最终字节不变，不打开正式本地数据库。运行结束后后台、Vite与门禁自有进程均关闭，lsof确认runtime无开放消费者；现有WAL/SHM按原字节保存，不为归档额外checkpoint。

存储守卫实际0，peak临时文件1.033GiB、最低可用空间13.137GiB；未触发stop，owned test临时目录已自动清理。独立归档不混入待清理测试目录。

### 首轮失败保留

首轮run `20261014T005719.998507Z-719af7c2b7d7` 为默认模式，preflight实际失败、gate退出1，后续质量/测试未开始。研发树旧 `output/native-trim-fullgate-20261013/fullgate-report.md` 含两个已失效归档链接，被全Markdown审计当作新文档扫描。

按原始证据的存放约定改名为 `.md.snapshot`，原字节/SHA不变，old→new映射、原报告、失败日志/summary均保存；未改产品或 authored docs、未调整门禁与阈值。随后启动新自有服务，复用本轮已完成准备的自有副本，运行第二轮默认全部阶段；没有--from热续跑，也没有重跑Linux性能对照。

### 恢复与下一步

归档ID `native-trim-maintenance-fullgate-20261014-20261014T013012Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。私密 `evidence.zip` 包括精确源码及tracked/new-test补丁、两个默认run原记录、XML/benchmark/浏览器证据、完整关闭runtime和WAL/SHM、规范排名输入、原报告字节与路径变更映射、协调文档快照；逐条内容/SHA独立复核，恢复时解压到新的私密目录。数据库和payload不进入Git、镜像或CI artifact。

当前可进入精确提交与整合审阅；本轮授权只继续验证，未执行提交。之后的新研发CI与发布仍需针对新提交，不能复用6c的旧CI；发布前另核成品fence、目标镜像及维护触发条件。原生峰值、逐请求64MiB、平台期、整体OOM保持OPEN，不为触发回收调整生产warmup配置。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](#维护完成回收候选提交与整合范围审阅)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。

## 维护完成回收候选：提交与整合范围审阅

原记录：`2026-10-14-native-trim-maintenance-submission-review.md`。

2026-10-14；SS-2026-10-08-001，关联SS-2026-10-09-001。

当前交付：业务`8f46b3cb`已按授权提交并进入本地main，同SHA映射；十份文档独立提交及三树同步见本文末节。未推送或部署，资源/OOM仍OPEN。

### 提交前审阅结论

**审阅通过，可交精确提交；未提交、未整合、未推送或部署。** 唯一研发树仍为 `codex/album-rank-cost`，基线 `6c74b9b416dbba47b354b850bdfe678f26ece63a`。三文件原字节与10-13冻结值、10-14完整门禁独立归档中的源码一致，审阅没有修改业务或测试。

代码未发现阻塞项：回收位于成功handler返回后、done前且持已有CPU gate；无额外启动预热、GET回收点、缓存失效或新配置。未列入既有CPU重型job_type集合的任务、未知handler及失败任务跳过，不以resource_class扩展或收缩集合；full预热不重复调用。已有helper的非Linux/非glibc/缺符号/OSError返回False不会改变任务完成，失败重试与后续排队路径保留。七个新增用例覆盖顺序、缓存对象、False返回、类型选择、失败重试及串行边界；原helper/warmup兼容与失败测试、54专项、当前默认全栈8/8实际0均是同一候选证据。

main与现有 `codex/versus-detail-integration` 均在同一6c基线，目标两旧文件字节与基线相同，新测试路径不存在。两处 `git apply --check` 实际0；仅干净可应用性检查，没有改目标源码。三棵树索引均未暂存任何内容。main已有九份未提交协调文档均属于同一问题链，逐份保护后审阅，不将它们复制到研发树。

发现并修正一个文档问题：docs地图/报告索引仍称“新完整门禁未运行”，与同一冻结候选10-14默认full8 Pass冲突。索引改为当前完整门禁已通过、新提交CI尚未运行；旧报告中的10-13检查点和raw receipt保持原范围。新增本报告后文档提交范围为十份文件。

### 两次精确提交草案

第一份仅在研发分支提交以下三个路径，标题 `perf(memory): 在重型维护完成后回收闲置原生页`；中文正文写明完成边界、跳过类型、保留缓存及已有验证，资源仍Partial。

- `backend/core/job_queue.py`
- `backend/tests/unit/test_job_queue.py`
- `backend/tests/unit/test_job_queue_native_memory.py`

第二份为main协调文档提交，标题 `docs: 固定维护回收验证与发布边界`。包含此前仍未提交的同链CI准备、专项/完整门禁报告、当前审阅和状态同步；不包含数据库、清单payload、原始日志、ZIP、covers或任何output。

- `docs/CHANGELOG.md`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/README.md`
- `docs/issues/README.md`
- `docs/reports/2026-10-13-native-trim-review-and-preparation.md`
- `docs/reports/2026-10-13-native-trim-review-and-preparation.md`
- `docs/reports/2026-10-13-native-trim-review-and-preparation.md`
- `docs/reports/2026-10-14-native-trim-maintenance-delivery.md`
- `docs/reports/README.md`
- `docs/reports/2026-10-14-native-trim-maintenance-delivery.md`

完整提交信息与分路径补丁已保存为私有准备材料，尚无staged diff或commit。授权后先精确提交研发三文件并执行项目hooks；再将同一业务commit按当前可快进关系进入本地main，记录实际source SHA→main SHA；main文档统一补上提交/整合事实后独立提交。现有main的dirty文档保留，不做整树reset/clean。整合树同步只在状态与未提交文件保护后进行。

不提前填写尚不存在的提交SHA，也不预先把状态改为INTEGRATED。提交后的新CI及任何远端推送/发布另按明确授权推进，不由本次审阅或过去6c的CI推定。

### 验证与资源边界

[当前默认完整门禁](#维护完成原生回收候选当前源码默认完整门禁) run `20261014T005816.915594Z-9d1a29cefca3`，8/8/actual0；seed3955、真实集成186、前端803、API157/113、三浏览器通过。此次审阅源码未变，不重复测试、完整门禁或Linux性能窗口；只对变更后的协调文档运行审计与diff检查。

[Linux专项](2026-10-13-native-trim-review-and-preparation.md#warmup0-重型维护完成边界的原生回收候选)支持维护后驻留下降343/333MiB，但采样峰高约40MiB、读取增长略大；原生amd64环境缺失，峰值/64MiB/平台期/OOM仍OPEN，发布HOLD。既有生产c0d首次窗口不追加请求、预暖或重启。

### 审阅时证据与停止边界

本轮独立审阅归档 `native-trim-maintenance-submission-review-20261014-20261014T014433Z`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`；包含三文件精确补丁及源码、两处无写入apply-check收据、协调文档保护/最终快照、精确路径提交草案、提交信息与审计结果。完整门禁950文件归档仍是 `native-trim-maintenance-fullgate-20261014-20261014T013012Z`，不改写原材料，不重复复制数据库。

用户本轮“继续”对应审阅与整合范围准备。AGENTS.md明文“未经明确要求不执行 git commit 或 git push”，因此提交仍待明确指令；当前准备工作已完成。

### 2026-10-14 授权后的本地提交与整合

用户已明确授权三文件业务提交、本地main整合及十份协调文档提交，不含推送或部署。业务提交 `8f46b3cb9af8ebc2c546727df089d4d97e7f5309`（`perf(memory): 在重型维护完成后回收闲置原生页`）精确包含三文件，提交前54回归通过，提交时ruff/format/mypy/detect-secrets四项hooks通过。

研发 `codex/album-rank-cost` 源SHA `8f46b3cb9af8ebc2c546727df089d4d97e7f5309` → main业务SHA `8f46b3cb9af8ebc2c546727df089d4d97e7f5309`，采用同一commit快进，没有重写代码。main原有十份dirty文档在快进前后逐份字节保持；本报告与其余九份协调文档由随后独立docs提交保存，实际docs SHA见Git历史和下述归档收据，不预先填写未知SHA。源码仍等于当前默认full8已验版本，没有重新运行完整门禁或Linux对照。

main、研发、统一整合树将在本轮文档提交后安全同步同一最终HEAD；不做reset/clean、不删除问题链工作树。当前保留同一研发/整合树服务后续资源问题与交付，OOM、原生峰值/64MiB/平台期继续OPEN，发布HOLD；未push/新CI/deploy，无生产请求或配置变更。

本轮独立恢复入口：`native-trim-maintenance-local-integration-20261014-20261014T015116Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。包含业务/docs两提交补丁、原文档保护及最终快照、实际commit/hooks与fast-forward记录、source→main映射、三树关闭检查点、文档审计和54回归。数据库与完整旧性能材料不重复打包，继续使用已验证的既有独立归档。原始收据保持原样，执行后的最终HEAD与同步结果由最终收据记录。

## 维护完成原生回收：生产交付与首次验收

原记录：`2026-10-14-native-trim-maintenance-production-delivery.md`。

2026-10-14；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。本轮发布固定 `b126020862fabb968db1974d38145b99d119ee86`，业务为同 SHA 合入 main 的 `8f46b3cb9af8ebc2c546727df089d4d97e7f5309` 与此前完整预热回收 `e01a4455`。

本轮已正式发布，独立运行核验、原首次90/90浏览器、116/116 API与三个strict read windows全部通过，原wrapper实际0。维护后闲置 native 页回收的交付范围完成，资源合同仍Partial：末尾RSS较旧窗口低388MiB，但读取增长更大、CPU略高，启动高水位基本不变；整体OOM、构建峰值、逐请求64MiB与多轮平台期继续OPEN。用户明确要求连续完成后续交付，不再逐步等待确认。

### 实现与已有验证

既有 CPU 重型维护成功返回后、任务 done 之前，在原 CPU gate 内调用兼容 Linux/glibc 的 `malloc_trim(0)` helper；full warmup 仍在自身完成点调用，不重复。失败、未知或非重型任务跳过；保留缓存对象，不新增 GET 回收、完整预热、调度器或配置。

三文件业务候选、54 项提交前回归与 hooks、源 SHA 到 main 同 SHA 映射见[提交整合报告](#维护完成回收候选提交与整合范围审阅)。当前冻结代码默认[完整门禁](#维护完成原生回收候选当前源码默认完整门禁) 8/8、actual0；[warmup=0 Linux 仿真专项](2026-10-13-native-trim-review-and-preparation.md#warmup0-重型维护完成边界的原生回收候选)支持 ready/final RSS 低约343/333MiB，但采样峰及读取增长没有改善。本轮不重复本地完整门禁或仿真配对，也不把旧 c0d 首次窗口改称新版本证据。

### 研发推送、CI 与发布输入

研发 `codex/album-rank-cost` 普通精确推送到 b126；此时远端 main 仍 c0d。首轮 Git TLS 查询失败，未执行 push，第二轮成功，原失败保留。研发 [CI 38500883926](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38500883926) attempt1、实际 job115647293828 成功；文档、unit、contract、lint、前端测试与构建全部成功。研发流水线的 production contract step 按原条件 skipped，正式 Release 必须另行实际执行该检查。

发布前核对生产仍 c0d、dual 三容器 healthy、schema90、plays94760、活动任务0、warmup=0。排名与详情成品重新以 b126 绑定导出/规范验证；事实 CLI、builder、schema 和部署脚本在 c0d 到 b126 间未变。导出使用当前已发布镜像、512MiB独立容器、源只读挂载、禁网无端口，无 cold build 或源写入。Billboard 不重复 live export，复用旧规范验证过的48目标清单，当前 live source fence 与 builder 完全一致。

三份成品均600权限，只在私密本地和服务器 backups 保存，未进入 Git、镜像或 CI artifact。服务器正式成品路径分别为 `versus-ranks-b126020862fabb968db1974d38145b99d119ee86.json`、`music-detail-b126020862fabb968db1974d38145b99d119ee86.json`、`billboard-b126020862fabb968db1974d38145b99d119ee86.json`；上传后 SHA256 与规范导出/已有验证一致。源指纹、原容器身份及启动时间仍一致，未改正式数据库或配置。

本地 full/showcase/dual 三项 profile-only 各实际0；上传后 MemAvailable 约1.76GiB、空闲磁盘约6.33GiB。正常发布仍由目标镜像的 Online Backup、源等价复用、rank/detail/Billboard 准入、健康及联合回滚门禁判定，输入准备不能替代正式激活。

### 正式发布

普通精确推送 main c0d→b126，未 force；[main CI 38502500846](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38502500846) attempt1与[正式 Release 38502500843](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38502500843) attempt2均实际success。研发、main与Release质量结果均为unit2742 passed/2 skipped、contract571 passed；前端803 passed/4 skipped并构建成功。正式Release另执行28项生产contract及三模式，均成功；不把attempt2继承的成功job当成重复执行的新验证。

Release attempt1 deploy job115657620105在最初脚本 rsync 的 SSH握手收到 Connection reset，actual255，0 bytes，未进入备份/切换。后置只读核验三c0d容器身份、StartedAt与healthy不变，schema90/plays94760/活动任务0。保留首轮失败，只重试该deploy job；GitHub connector因integration写权限403失败、gh wrapper查询EOF均保留，直接CLI同job rerun成功。attempt2实际deploy job115658306844成功，没有重跑成功的质量检查或镜像构建。

目标两镜像的TCR push/pull、manifest、linux/amd64与revision核验通过。03:07:32Z生成Online Backup `spotify-stats-pre-release-b126020862fa-20261014T030712Z.db`；搜索 `source_equivalent_exact_statistics_resume` 复用，ready_rows12，无statistics冷建；排名4、详情4、Billboard48精确门禁通过。03:13:12Z正式部署完成，dual与既有public展示访问方式保持。独立核验实际三OCI完整b126/healthy、30镜像源码/3helpers、schema90及两个loopback运行面通过；宿主3001/3002只绑定127.0.0.1，没有改私有外部入口或Tailscale。

### 首次验收执行约束

在 main 推送前准备并校验原五份 observer 的冻结哈希；90场景顺序、目标、浏览器/视口、fresh context、PWA 和阈值以及116 API规则均不修改。仅包装脚本绑定新 SHA/新材料目录；Docker Mounts 在配置摘要前规范排序，修正历史相同配置不同枚举顺序导致的假失败，原五工具字节不变。

正式流水线成功后独立核验三 OCI、30份镜像源码、3个服务器 helper、两个 loopback运行面、schema90与search/rank/detail/Billboard ready；等待启动维护自然完成。然后只取新版本的一个自然首次90窗口与资源采样，接原116 API及三个 strict read windows。无额外手动重启、预暖或热重跑，私有外部入口维持现状；原失败完整保留。单窗观察即使改善也不关闭逐请求64MiB、多轮平台期和整体OOM。

### 首次验收与资源结果

独立八步运行核验实际0；启动维护自然结束后，uvicorn宿主PID3712766/start_ticks177071151从首次前到首次后连续，三容器身份与规范配置摘要不变。原首次wrapper一次执行、实际0；浏览器90/90（Chromium42、Firefox24、WebKit24），116/116 sequential GET API及公开能力边界通过。三个完整read-window对比实际0，七读源、57受保护表/37原始表、队列、发布记录及全部sidecar事实不变，未使用访问时钟放宽。采样覆盖完整浏览器窗口，最大间隔52.75ms；没有额外生产重启、预暖、负载测试或热复验。

90场景键、顺序、fresh context与阈值同旧c0d窗口。点击核心最大1084ms、直达核心最大2368.6ms（均达标）；旧index39固定L3 album直达1716.3→1498ms，但整体直达最大2125.5→2368.6ms，不能概括为所有时延改善。

| 资源指标 | 旧c0d单窗 | 新b126单窗 | 新减旧 |
| --- | ---: | ---: | ---: |
| 窗口起点RSS（MiB） | 965.828 | 396.059 | -569.770 |
| 浏览器窗口峰值RSS（MiB） | 1160.348 | 748.363 | -411.984 |
| 窗口末尾RSS（MiB） | 1136.430 | 748.363 | -388.066 |
| 窗口起点到末尾增长（MiB） | 170.602 | 352.305 | +181.703 |
| 窗口CPU（秒） | 38.650 | 41.590 | +2.940 |
| 首窗前进程历史VmHWM（MiB） | 1193.258 | 1186.516 | -6.742 |

生产是原生amd64，但两次窗口不在同一时间，只支持观察比较，不等于严格原生配对。驻留明显降低，读取时又重新分配了部分页；启动历史高水位几乎不变，CPU和增量增长未改善。因此本次是驻留缓解交付，峰值、逐请求64MiB、多轮平台期与整体OOM仍OPEN，不能凭90/116功能成功关闭资源合同。

新首次窗口cgroup全部memory event delta为0，宿主oom_kill为2→2；旧c0d首次为1→1，二者不是相邻窗口，不能把间隔中的累计增量算作本次首次OOM。另行只读核对2026-10-14 02:25Z起kernel journal无匹配OOM条目（journal查询actual1、No entries），不改写10-13独立工具OOM旧记录。

### 证据、提交与工作树处置

独立恢复入口：`native-trim-maintenance-production-delivery-20261014-20261014T024308Z`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。保存原查询/TLS/API传输失败、实际refs/push、研发和正式job日志、首轮deploy失败/后置身份/仅失败job重试、只读生产基线、规范输入验证、私密成品及上传指纹、三模式、五份不变observer、新版本唯一首次90/116与三strict、资源逐样本与旧窗对照、固定源码、最终协调文档及提交恢复bundle。ZIP CRC、observer与私密输入哈希校验收据独立保存，数据/payload不入Git。

旧c0d首次结果未重跑或改写，继续使用既有独立归档。源业务8f46→main8f46为同SHA快进；发布b126与随后纯文档提交分别记录。本轮协调文档由main统一提交，研发/统一整合树安全同步；不做reset/clean或远端分支删除。OOM问题链仍OPEN，保留唯一`codex/album-rank-cost`研发树与至多一个统一整合树服务同一未关闭合同，当前发布候选不再挂HOLD。服务器只清理已取回且独立保存的本轮owned临时目录，正式成品与回滚备份保留。实际文档HEAD、refs和同步/清理结果见归档最终收据。
