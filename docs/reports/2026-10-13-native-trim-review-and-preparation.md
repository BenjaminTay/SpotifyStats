# 原生回收候选审阅与发布准备

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。集中保存完整预热候选、维护完成边界候选及当日发布准备。研发推送和CI不等于main或生产已发布；warmup=0下触发条件不满足的HOLD及隔离收益边界保留。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [完整预热原生内存回收候选：归因、验证与整合审阅](#完整预热原生内存回收候选归因验证与整合审阅)
- [warmup=0 重型维护完成边界的原生回收候选](#warmup0-重型维护完成边界的原生回收候选)
- [原生回收研发分支 CI 与发布准备](#原生回收研发分支-ci-与发布准备)

## 完整预热原生内存回收候选：归因、验证与整合审阅

原记录：`2026-10-13-native-trim-candidate-review.md`。

2026-10-13；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。

后续状态：6c74b9b4仅研发分支已推送，main未推送/部署；发布前只读核对发现生产warmup=0，当前full预热回收不会触发，发布HOLD。原完整预热实验及本地整合证据保留原范围；最新CI与准备见[发布准备报告](#原生回收研发分支-ci-与发布准备)。

**结论：INTEGRATED（本地），未推送或部署。** 最小补丁已实现并审阅，默认 Phase5 与默认完整本地八阶段门禁通过；Linux 仿真对照证明维护完成后的驻留收益及样本响应等价。用户授权后，业务提交 `e01a44550ee0082a71788bd37f2cd939e53542a2` 已原样快进进入 main，整体资源合同与 OOM 保持 Partial/OPEN。

### 基线与精确范围

唯一研发分支为 `codex/album-rank-cost`，工作树为 `/Users/benjaminlei/.codex/worktrees/album-rank-cost/202605-SpotifyStats`。验收基线为 `13ec3ec110886abf91e9da420ca046846c311c4a`，其backend/scripts/frontend与已发布c0d的Git内容相同；当前业务提交为e01a4455，四文件与该基线上的完整门禁候选逐字节一致。

本轮补丁仅含以下四文件；两个新文件原为 untracked，完整恢复补丁已经包含它们。下列 SHA256 是源文件内容指纹，不是提交 SHA。

```text
backend/core/native_memory.py
2513ea7033c72717125a313787db651417569d4c2861b91e2b3823c2eb76aeec
backend/core/warmup.py
9bee03f7a9db5b0e0a9ee7155f4e26e3759dbdc492f6c9fa2c6704dbb6febd4b
backend/tests/unit/test_native_memory.py
4854d95edc024acedd1dd13d083cc7185c3ef366ee12475cf5b9743a3e4f262f
backend/tests/unit/test_warmup.py
aaf23e84afa104cb534ea77d870fa0ff5e137e46a532a161621de10dc72c676d
```

提交映射：研发 `e01a44550ee0082a71788bd37f2cd939e53542a2` → main 同一完整SHA，采用fast-forward，未复制或重写产品补丁。main原有六份未提交文档在快进前独立保存，快进后逐字节保持，再由协调方统一更新为本地整合状态。

提交前精确暂存四文件，cached内容与冻结SHA一致；native/warmup的13项回归通过，ruff、ruff-format、mypy、detect-secrets提交钩子全部通过。业务提交只包含四文件。README、AGENTS/CLAUDE已检查，规则无需变更，AGENTS与CLAUDE一致。

### 归因与最小修复

正常预热及三轮有界请求后的帧缓存仍有合法持有；缓存条目稳定不等于进程 RSS 稳定。初次 Linux 归因在缓存保留时单独调用 trim，RSS 约下降 966MiB，帧预算、被观察帧身份及 Python arena 容量不变。这支持 glibc 空闲页保留是本次窗口驻留的主要可回收部分，不证明全部剩余 RSS 的唯一来源。

最小候选在完整后台预热正常返回、builder 已退出且源连接已关闭后调用一次 `malloc_trim(0)`。只在 Linux 且 glibc/trim 符号可用时执行；非 Linux、缺少符号为 no-op，OSError 记录后返回 False。minimal 预热或提前失败不调用。

复核未发现阻塞项：ctypes 参数/返回类型明确；调用点复用既有后台任务和 CPU gate；不清 LRU、不运行 GC、不新增调度器、环境变量、缓存或逐 GET hook，不恢复旧投影/生命周期混合补丁。false/no-op 不改变维护成功状态。测试覆盖平台与符号兼容、异常、zero-pad、注册 ready 缓存保留、调用次数及 builder/连接完成顺序。

此修改针对**已完成完整预热后的驻留**，未覆盖每次后台维护或 minimal 启动，也没有证据证明它能降低构建期间峰值。

### 本地正确性与默认门禁

四文件内容在定向测试、仿真配对、审阅、默认 Phase5 和本地全栈之间一致。

| 验证 | 结果 | 范围 |
| --- | --- | --- |
| 定向正确性 | 64 passed | warmup/native/年度/队列49项、公开读取与快照边界15项；Ruff、format、diff检查通过 |
| 默认 Phase5 | 实际0，PASS | unit2735/2skip、contract571、前端803/4skip、构建、文档与CI规则检查；不代替 fullstack |
| 默认本地 fullstack | 实际0，八阶段PASS | run `20261013T093055.808116Z-598e44fa152c`，1705.908s；未使用 --only、--from、--skip-cross-browser 或放宽阈值 |
| 后端及真实副本集成 | 3948/2skip；186/1skip | seed 全套与真实数据副本分别报告 |
| API | smoke157/157；boundary113/113 | 延迟51端点×22轮=1122样本，500ms阈值，最高hot P95 228.785ms；无slow端点或空hot P95 |
| 浏览器 | Chromium/Firefox/WebKit PASS | 详情路由、五视口、桌面/手机交互与图表、控件/触控目标、长列表；WebKit引擎不等于真实Safari设备 |

fullstack 八个必需阶段为 preflight、quality、backend、api、browser-routes、browser-interactions、browser-inventory、browser-compat，全部同轮通过。未请求的 optional 行为 NOT_RUN。存储保护峰值1108513392 bytes、最低空闲20097699840 bytes，未触发停止，临时目录已清理。已有 bundle/LibreSSL/弃用警告仍保留。

本地门禁使用原已封存 Online Backup 的七文件独立副本和规范排名清单安装。一次正常完整预热结束后启动标准门禁服务，warmup=off、外部封面开关为文档默认1。默认封面下载与维护可写自有副本，故整个门禁窗口不声明严格GET事实守恒。原始七文件备份 SHA 不变；本轮服务均已关闭，runtime 无 open owners，残留 WAL/SHM 与原始记录一并归档。

本轮 macOS helper 是 no-op；上述门禁证明功能集成，不增加原生 Linux 时延、CPU 或绝对 RSS 证据。API first 样本没有新鲜进程状态证明，本轮不等于生产首次验收。

### 有界 Linux 配对

发布 amd64 镜像运行于 Docker Desktop aarch64 Linux，属于仿真。原版与候选各使用独立关闭备份，同一规范四套排名安装、2CPU/4GiB、禁网、无端口及只读根文件系统；各一次正常 lifespan，两条请求链各三轮。候选仅覆盖固定 helper/warmup 源码。

两边均9个HTTP200、实际exit0/OOMKilled=false。保存的9对完整响应逐字节相等，每侧同类三次响应SHA相同；两侧startup settled后的扩展读取守恒通过，包含源事实、原始37表、队列、主库/六sidecar发布、schema、epoch、fence和文件身份。

实际产品hook调用一次并返回True；缓存信息、帧预算和被观察roots不变，调用期间RSS下降约890.63MiB。观察工具没有额外清缓存、GC或trim。

| 定点 | 原版RSS MiB | 候选RSS MiB | 差值MiB |
| --- | ---: | ---: | ---: |
| startup ready | 1773.89 | 898.73 | -875.16 |
| 最终idle | 1832.81 | 1043.58 | -789.23 |
| 采样峰值 | 1867.72 | 1843.62 | -24.10 |

候选专辑idle1→3仍+1.75MiB，年度+0.016MiB，跨链及最终idle另有数MiB变化；不宣称全进程多轮平台期已证明。采样最大实际gap779.69/926.03ms，不能把采样最大值称精确峰值；单对约24MiB峰值差不证明构建峰值改善。仿真时间只作探索上下文，不用于原生准入。

### 保留的失败和证据缺口

- Linux初次工具collector缺少PYTHONPATH：两边已完成startup，但均在第一个GET前失败，各0GET/实际exit1。失败窗口保存；仅修正工具环境，成功配对从原始备份新建冷副本。
- fullstack初次PERFORMANCE_DATASET误用描述性字符串，在任何检查阶段之前实际退出2；保留原记录。修正为CLI支持的online_backup后，以新服务从头跑默认完整模式并通过，未将后缀重跑称完整通过。
- 旧macOS基本统计SHA与Linux不同，旧响应原文缺失，有界离线检查未得到唯一解释；没有追加请求补成结论。本轮两版Linux完整响应相等。

### 独立证据与恢复

以下均为本地私密归档目录，不包含于Git或镜像。历史收据路径保留原样，用各自archive-receipt解释复制位置。

| 归档ID | 内容 |
| --- | --- |
| resource-ownership-20261013-20261013T051529Z | macOS缓存/帧所有权与有界自然请求诊断 |
| linux-resource-ownership-20261013-20261013T054034Z | glibc/arena/smaps归因与单独trim干预 |
| native-trim-candidate-20261013-20261013T064040Z | 候选固定源文件、64项验证、失败与成功Linux配对、18个完整响应及strict |
| native-trim-review-20261013-20261013T082323Z | 静态审阅、默认Phase5、实际退出与存储保护 |
| native-trim-fullgate-20261013-20261013T100340Z | 默认完整fullstack、首轮配置失败、关闭后的runtime/WAL、四文件补丁、handoff和机器可读结果；779文件逐字节复制校验 |
| native-trim-local-integration-20261013-20261013T135607Z | 本次13项回归、精确暂存/提交钩子、原样快进、六份原文档保护与同步收据；文档快照后缀导致的首次审计失败及路径映射保留 |

共同父目录为 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。fullgate归档的 `current/candidate-complete.patch` 和 `current/candidate-source/` 可恢复四文件候选，`current/attempt2/summary.json` 是成功门禁入口；本地整合归档包含 `current/main-evidence/` 和 `current/source-evidence/`。raw运行记录不依赖活跃工作树。

### 当前决定与下一步

用户明确授权四文件候选及六份文档提交和本地整合，原“暂不提交”限制仅在此范围解除。业务提交已进入main；六份协调文档作为独立状态提交保存，随后安全同步原研发和统一整合工作树。未推送、未部署，不访问或重启生产，不重复生产90或额外仿真轮次。

用户已说明没有非生产原生amd64环境。原生时延/CPU/绝对RSS、逐请求64MiB、多轮进程平台期、构建峰值和整体OOM仍未关闭。下一步是明确固定版本的后续交付与资源验证条件；推送、CI和部署尚未执行。资源门槛若仍不达标，短生命周期builder应作为新的有界阶段单独评估，不扩入当前补丁。现有两工作树保留用于同一资源问题链和统一交付，不新建并行候选。

README、AGENTS/CLAUDE无需改变产品或协作规则；本轮同步开发总表、问题台账、变更日志及文档索引。历史[生产交付](2026-10-13-album-rank-cancellation-delivery.md#专辑排名取消修复的生产交付与首次验收)和[前一整合检查点](2026-10-13-album-rank-cancellation-delivery.md#专辑排名取消与-top250-候选审阅整合记录)继续保留原版本与范围。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-delivery.md#维护完成回收候选提交与整合范围审阅)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。

## warmup=0 重型维护完成边界的原生回收候选

原记录：`2026-10-13-native-trim-maintenance-candidate.md`。

2026-10-13；SS-2026-10-08-001，关联 SS-2026-10-09-001。

### 结论与状态

在唯一研发工作树 `codex/album-rank-cost` 基于 `6c74b9b416dbba47b354b850bdfe678f26ece63a` 实现三文件未提交候选。**专项可审阅 / Partial，发布仍 HOLD。** 关闭预热时实际调用边界已验证，维护后的驻留有收益；峰值、逐请求64MiB、平台期与生产OOM未关闭。

本轮没有提交、整合产品代码、推送、CI或部署，没有调用生产API、改生产配置、重启或预暖。已推送研发分支和其CI仍只对应旧6c；本地main及整合工作树业务代码仍为旧6c。新默认Phase5/full8未运行，旧完整门禁不覆盖当前队列补丁。

### 最小实现与审阅

- `backend/core/job_queue.py`：沿已有 CPU 串行 gate，在成功 handler 返回后、任务标记 done 前调用原生回收；回收结束后才允许下一重型维护进入。异常 handler 仍执行原失败/重试路径，不增加回收。
- `startup_cache_warmup` 排除额外队列回收：原 full 预热继续使用自己的结束调用，minimal 不增加调用。非重型任务、网络任务、未注册 handler 不进入该边界；自定义 critical 资源标签不扩展 CPU 类型集合。
- 保持 `warmup=0`，复用现有 helper 的 Linux/glibc 兼容及失败 no-op；没有新环境配置、计时任务、GC、缓存清空或GET调用点。既有 handler 本身的缓存生命周期不变。
- `backend/tests/unit/test_job_queue_native_memory.py` 新增7例，验证完成顺序、gate占用、缓存对象保留、False结果、失败/重试及两任务的并发阻塞边界；既有 `test_job_queue.py` 注入 allocator no-op，避免合成队列测试触发本机真实回收。

54项定向回归实际0（2.32秒），包括队列、原生兼容、full/minimal预热和公开只读合同；Ruff/lint/格式及diff检查通过。存储守卫实际0、没有触发停止，测试自有临时目录已清理。该范围是定向验证，不称整个后端或全栈通过。README/AGENTS/CLAUDE无新增规则需要同步，后两者当前字节一致；共享状态仅main维护。

### 有界 Linux 对照

ARM Linux引擎、amd64镜像仿真；禁网、无端口、只读根目录，单容器4GiB/2CPU、进程RSS3GiB守卫、每窗900秒上限。基线和候选串行，各在新自有关闭七文件副本完成一次自然启动和读取窗口。原始备份最终SHA保持一致。

基线三文件从固定6c提取；候选只额外改变队列调用点，既有native/warmup模块相同。使用缓存的已发布镜像并挂载精确代码，而非构建或发布目标镜像。两侧通过规范排名validate/install/verify，生成各自文件本地 lineage；没有伪造ready或改事实builder。

启动配置为warmup=0、搜索启动维护=1、L3启动调和=1、外部封面=0，匹配生产关闭预热这一条件；历史副本及其维护目标不冒充当前生产源的精确启动现场。两侧同样执行11项：Billboard1、analysis6、artist rank1、community1、archive1、governance1；本窗均首次完成。备份原有38项failed历史记录逐项保持，不把历史失败算作本窗失败或清除。

公开只读请求为专辑stats含/不含排名各3轮，以及年度cache-only读取3轮。年度没有现成缓存，按接口合同返回404，不为凑200创建年度成品。两侧都是6个200+3个预期404，9对完整响应逐字节一致。两侧strict实际0：原37类来源、保护事实、队列、发布记录、六sidecars、schema90、epochs、fence、文件身份均守恒，无access-clock豁免。

| 观察值 | 固定6c基线 | 队列候选 |
| --- | ---: | ---: |
| 实际队列trim调用 | 0 | 11（均True） |
| 就绪RSS MiB | 1023.086 | 680.020 |
| 最终idle RSS MiB | 1151.000 | 817.750 |
| 采样峰值RSS MiB | 1283.988 | 1323.750 |
| ready→final增长 MiB | 127.914 | 137.730 |
| 最大实际采样间隔 ms | 683.162 | 1088.155 |
| startup就绪等待秒 | 125.972 | 149.723 |
| 容器实际exit / OOMKilled | 0 / false | 0 / false |

候选ready/final分别低343.066/333.250MiB，但采样峰值高39.762MiB，读取后增长高9.816MiB。仅固定窗口，不追加热重跑；采样缺口与仿真限制保留，不能据此证明原生构建峰值或性能准入。启动等待更长也如实保留，不能把单次差异归因成53ms调用开销。

11次回收前后 frame budget 的字节、条目及对象ID、注册LRU cache_info 全部相同；最终两侧合法frame预算同为114.687MiB。回收调用总观察53.113ms，最长12.279ms，单次最大RSS下降379.148MiB。累计调用下降含反复分配/回收，不能与最终驻留收益混用，也不是独立页面总数。证据支持闲置native页这一修复靶点，不证明所有驻留来自单一分配器。

### 原始失败与证据

首轮旧探针沿用了full预热“年度成品已存在”断言：基线6个专辑200后退出1，OOMKilled=false，候选未启动。保留首轮完整记录；探针改为公开年度cache-only真实200/404合同，再用新副本运行上述配对，产品补丁未变，不重启原容器。

首次汇总错误要求整个历史队列表均为done，分析器实际1；随后对原始关闭备份逐项核验38条历史failed，并要求本窗11项首次done。只重新分析已固定的结果，无新增请求/自然窗口，旧分析失败日志保留。

独立归档ID：`native-trim-maintenance-20261013-20261013T152109Z`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。`evidence.zip` 包含三文件冻结源码/补丁、新测试补丁、baseline覆盖源码、输入私密清单、四份自有运行副本、首轮探针失败、修正配对及首次分析失败、完整请求body、采样/回收见证、strict与容器收据、协调文档快照。逐条压缩包内容与SHA独立复核，恢复时解压到新的私密目录。所有数据/清单保持本地私密，不进入Git/镜像/CI artifact。

### 下一步

先审阅当前三文件精确候选，再执行当前源码的质量检查和新默认完整门禁；不能复用旧6c的CI/full8宣布新补丁通过。通过后才进入获授权的提交/整合及研发分支CI阶段。发布继续单独决定：重新核对成品fence、目标镜像和触发条件；保持生产预热关闭，不因本次驻留收益关闭峰值/OOM。原生amd64环境仍缺失，不使用生产做无界分配器实验。

此前[研发CI与发布准备](#原生回收研发分支-ci-与发布准备)、[full预热旧候选](#完整预热原生内存回收候选归因验证与整合审阅)保持其原范围和收据。

### 2026-10-14 后续验证

同一冻结三文件候选的新默认完整门禁八阶段PASS/实际0，见[当前源码完整门禁](2026-10-14-native-trim-maintenance-delivery.md#维护完成原生回收候选当前源码默认完整门禁)。上述“新full8未运行”保留为10-13专项检查点；仍未提交整合/新CI/推送部署，Linux资源及原失败不改判。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-delivery.md#维护完成回收候选提交与整合范围审阅)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。

## 原生回收研发分支 CI 与发布准备

原记录：`2026-10-13-native-trim-release-preparation.md`。

2026-10-13；SS-2026-10-08-001，关联SS-2026-10-09-001。

### 当前结论

用户授权仅推送现有研发分支并检查CI，再完成发布准备；不推送main、不部署。精确 `6c74b9b416dbba47b354b850bdfe678f26ece63a` 已推送到 `codex/album-rank-cost`，远端main仍为c0d699e5。本轮没有触发正式发布。

**发布状态：HOLD，生产触发条件不满足。** 私密输入和静态部署检查已经准备，但只读核对发现当前生产Backend的 `SPOTIFY_STATS_WARMUP=0`。本补丁仅在完整预热结束时调用trim，当前配置不会进入该调用点；本地完整预热驻留收益不能直接代表当前生产启动。

不调整生产配置、不自动启用full预热、不增加生产探针或重启来补成成功。建议下一阶段保持warmup=0，以现有重型维护完成边界为候选触发点，单独审阅最小修正并做匹配实际启动方式的有界验证；本轮未实施该修正。

### 推送与 CI

- 普通精确refspec仅推送 `HEAD:refs/heads/codex/album-rank-cost`，实际退出0，未force-push、未推送其他分支。
- 独立ls-remote确认研发分支为6c74b9b4、main为c0d699e5，与推送前main一致。
- [日常CI 38414168750](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38414168750)：精确head 6c74b9b4，attempt1成功，实际job `115354026493` 成功。原日志记录unit2735 passed/2 skipped、contract571 passed、前端803 passed/4 skipped；文档、lint与构建通过。Production deployment contract checks步骤因inputs=false为skipped，不称部署契约远端通过。
- NoDeploy部署契约workflow的路径条件不匹配本次四backend文件和文档，未触发；production-release仅匹配main或显式dispatch，本轮未触发。三模式静态检查在本地单独执行，不把它称作远端NoDeploy通过。
- 初次GitHub直连长时间无输出，最终HTTP2 framing error/实际128；使用项目既有代理和HTTP/1.1后查询、推送及CI读取成功。保留原失败，不修改Codex或Git全局网络配置。
- CI watch在完成前一次API读取EOF而实际退出1；独立run/job最终API及完整job日志确认attempt1成功。watch工具退出与workflow结论分开保留，不重跑CI。

### 已准备材料

当前c0d与目标6c的backend/scripts/deploy/workflow差异仅四个native/warmup及测试文件，发布事实CLI、builder、schema、统计规则和发布脚本均未改变。

以当前已发布镜像运行规范只读verify/export/validate，数据目录以同一 `/app/data` 命名空间只读挂载。关闭warmup、搜索重建、L3调和及外部封面；工具禁网、无端口、只读根文件系统。输出只写独立私密临时目录，不进入生产数据或backups部署目录。

| 材料或检查 | 结果与范围 |
| --- | --- |
| 四默认个人排名 | verify/export/validate实际0；目标release_sha绑定6c74b9b4 |
| 四默认详情投影 | verify/export/validate实际0；源lineage和治理检查保留 |
| Billboard现成发布 | live verify实际0，48目标；本次live export在512MiB隔离工具内退出137，未产出可用新清单 |
| Billboard复用清单 | 原c0d封存清单字节复用；规范validate在独立关闭七文件副本实际0，48目标；轻量只读live核对确认source fence与builder相同 |
| full/showcase/dual | 本地profile-only三项实际0；仅静态配置，不连接或部署生产 |

三份目标SHA私密JSON已取回并封存为600权限；复制SHA与规范验证记录一致。未提交Git、未进入镜像或CI artifact、未上传服务器部署目录。目标镜像尚未构建，不能把当前镜像事实工具的验证称为目标镜像准入；未来激活前必须重新验证source fence及成品。

本地Billboard验证峰值观察约855MiB，受2GiB/120s有界守卫约束，未停止；原始七文件备份与自有验证副本均保持字节一致。没有builder、import或提高生产内存后重试export。

### 生产只读核对与失败保留

核对时三容器仍为c0d且healthy，schema90、plays94760、活动任务0。Backend StartedAt仍为2026-10-13T02:52:51.869156096Z，当前warmup为0；容器身份、镜像身份、启动时间及源数据库/sidecar/WAL/SHM物理状态在受限导出前后均一致。没有个人统计GET、冷构建、排队、停服或部署。

工具exit137对应内核 `CONSTRAINT_MEMCG`：512MiB独立导出容器中的python被杀，cgroup与生产Backend不同。此为本轮隔离工具OOM，不能隐去或描述成整体窗口无OOM，也不等于生产Backend遭global OOM。失败输出、内核定位和后置身份核对保存。

轻量fence工具前两次错误导入不存在的module而退出1，均保留；改为规范CLI自身cache对象后实际0，未涉及产品修改。服务器自有临时目录完整取回并校验后移除，仅清理本轮工具输出，不动数据库或部署目录。

### 下一阶段与发布条件

1. 本分支精确SHA的实际CI已核对通过，原工具失败保存，不新增CI重跑。
2. 维持main推送与部署暂停，先解决warmup=0条件下的回收调用点；不以开启完整预热来绕过问题，因为新增构建峰值没有准入证据。
3. 最小修正若另获授权，冻结新源码并验证其在warmup=0、minimal/full及维护失败时的调用边界、缓存保留、完整响应和资源收益，再决定新固定版本。
4. 新版本发布前重新绑定排名release_sha并核对所有私密输入与当前源；正常发布仍使用Online Backup、statistics-reuse-only、精确rank/detail/Billboard门禁、健康与联合回滚。当前准备不会替代这些激活门禁。
5. 发布后仅使用正常启动的首个窗口采集，不额外预暖、重启或热重跑；原生CPU/RSS、逐请求64MiB、平台期、构建峰值和整体OOM仍需独立判定。

现有[候选本地整合](#完整预热原生内存回收候选归因验证与整合审阅)及其full8/仿真证据继续有效，但范围明确为完整预热场景。当前生产触发条件新证据改变的是发布决定，不改写旧实验结果。

### 独立恢复入口

归档ID：`native-trim-release-preparation-20261013-20261013T144725Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。材料包含push/远端ref、CI实际job日志、source/容器只读核对、失败导出与kernel记录、本地清单验证、三份私密输入、临时目录清理和后续发布步骤说明；数据库和payload保持私密，不进入Git。

本报告及共享状态为本轮协调文档，当前未新增提交或推送，不影响已检查CI的6c74b9b4源码。

### 后续本地阶段

保持预热关闭的队列完成边界候选已另行实施，见[新三文件专项](#warmup0-重型维护完成边界的原生回收候选)；未提交/整合或新增推送部署。旧6c的CI、私密输入准备和本报告原失败仍保持原范围，新补丁尚无完整门禁/CI。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-delivery.md#维护完成回收候选提交与整合范围审阅)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。
