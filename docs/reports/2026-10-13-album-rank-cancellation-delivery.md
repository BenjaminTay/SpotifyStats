# 专辑排名取消修复整合与生产交付

2026-10-26按主题合并。按候选审阅、主线整合和生产交付排列。90场景与116API证据、首次安装失败和有界重试保留，整体OOM与手机问题继续独立跟踪。

## 阅读顺序

- [专辑排名取消与 Top250 候选审阅、整合记录](#专辑排名取消与-top250-候选审阅整合记录)
- [专辑排名取消修复的生产交付与首次验收](#专辑排名取消修复的生产交付与首次验收)

## 专辑排名取消与 Top250 候选审阅、整合记录

原记录：`2026-10-13-album-rank-cancellation-integration-review.md`。

日期：2026-10-13。事项：`SS-2026-10-09-001`；关联资源事项：`SS-2026-10-08-001`。

> 后续正式交付：c212修复随c0d699e5已推送发布，CI成功、Release首轮拒绝后attempt2成功；原90首次90/90、116 API/三strict通过。首次延迟子项达标，资源/OOM/手机仍开放，原wrapper1及独立补证保留。以下审阅/整合部分中的“未推送/发布”是当时检查点，具体交付见[正式报告](#专辑排名取消修复的生产交付与首次验收)。

结论：源码审阅未发现阻止整合的问题。七个候选文件已应用到现有 `codex/versus-detail-integration` 工作区，并与通过完整本地门禁的研发源码逐文件一致；整合工作区重点回归 57 项通过。已按后续明确授权形成本地业务提交 **`c21250e3922c6488a65418352243a24541bcac0a`**，来自 `codex/versus-detail-integration`，随后与状态提交`8b1b2405`原样快进进入本地main；尚未推送或部署。生产详情性能保持 OPEN/Partial，整体 OOM 保持 OPEN。

### 1. 基线、补丁与取舍

审阅应用前，main、研发工作树和整合工作树 HEAD 均为 `2bdf0ce5cd0ad306750f82a5c0763dcb2a559016`。该提交为开发协作规则整理，业务基线仍为已发布 `4f3f2ac0436ba6556bc3ca90773860e18cd9dc77`。本轮采用研发候选固定补丁，不合入前端设置、JSON名称传输、艺人范围身份以及两个实体帧实验。

| 文件 | 采用内容 |
| --- | --- |
| `backend/api/music.py` | 专辑名称和 project stats 两个入口监听真实 ASGI 断开；同步统计继续在线程池执行，基础请求保持原结果 |
| `backend/core/request_cancellation.py` | 请求级取消信号与协作检查；等待工作线程退出后再清理连接，保留正常异常类型 |
| `backend/services/entity_stats_service.py` | Top250 使用原有规范字段 loader，完整时长切片只构建一次；请求拥有的昂贵阶段之间检查取消 |
| `backend/tests/unit/test_album_top250_slice_reuse.py` | 三窗口、跨日时长与空计次窗口等价 |
| `backend/tests/unit/test_request_read_cancellation.py` | 取消所有者或等待者、同键/不同键、锁释放、缓存与连接清理 |
| `backend/tests/unit/test_album_rank_cancellation_stages.py` | L2/L3 × 动态/固定配置中的计算阶段停止 |
| `backend/tests/contract/test_album_rank_disconnect_api.py` | 完整中间件下断开、正常响应、503和基础请求合同 |

组合补丁 SHA256：`a37bcf95f05f23ffb957cf228f8bdaec495e2df56b3ca0be3c506e5f65479295`。取消增量补丁 SHA256：`5831bc921afcf9a24e7b455f17eaf9f0f8b5ce49ad4b4b9c42db2ef4be7b51b5`。`git apply --check`、应用及七文件核对通过；完整 backend Python 文件集合亦与研发源码一致。取消增量在临时 Top250 基线上重放后，六个新增或修改文件一致。

审阅时尚未提交，后续用户明确授权提交当前已审阅整合候选。固定组合补丁已映射到本地整合业务提交`c21250e3922c6488a65418352243a24541bcac0a`，父提交为`2bdf0ce5cd0ad306750f82a5c0763dcb2a559016`；提交中16个文件逐一与审阅检查点一致，提交时Ruff、format、mypy、secret hooks全部通过。本地主线随后从`2bdf0ce5`快进到`8b1b2405`，没有冲突、重写或新增业务实现；映射为固定源补丁→`c21250e3922c6488a65418352243a24541bcac0a`（main业务提交），状态提交`8b1b24052dadb798f3de1a60d8de09c318226e59`→同SHA。业务源码与研发full8/整合57项验证版本一致，本轮只做分支整合及文档更新，不另跑full8、性能序列或生产验收，未执行推送/发布。不得把共同旧HEAD当成最终修复提交。README产品入口和统计规则未变化，根 AGENTS/CLAUDE无需新增规则；后端模块地图及交付文档同步新辅助模块。

### 2. 审阅判断

| 审阅项 | 判断与边界 |
| --- | --- |
| 请求所有权 | ContextVar 中仅存本请求 Event；两个无 Body 消费的 GET 独占 receive 监听，避免 BaseHTTPMiddleware 下即时轮询漏掉断开 |
| 共享计算与缓存 | Event不进入参数或revision缓存键；共享 load_plays 等底层 builder 未检查取消。singleflight和LRU容量未改；所有者异常释放锁，另一个有效等待者可重新得到完整结果，异常不缓存半成品 |
| 线程、连接与异常 | 不遗弃运行中的线程，不在连接仍被使用时关闭它；原服务/HTTP异常在任务组外重抛，503语义保持；取消只对已断开请求产生499 |
| 统计合同 | Top250候选ID及多艺人展示行的250边界保留；L2原排名口径、project membership、来源曲目与前序事件边界保留。完整未过滤时长轨先切片，再分别过滤三个窗口，避免跨日时长丢失 |
| 公开读取 | 无新增写入、排队、外部HTTP、缓存容量、迁移、索引或发布格式；既有缺失/来源漂移拒绝合同不变 |
| 范围 | 只修复专辑 stats 请求拥有的计算。当前 Pandas/SQLite 阶段不会被强制中断，取消在下一检查点生效；本次56.5ms不是通用最大停止时限。年度后台生成、其他实体和手机弹层未扩展修改 |

这是本任务负责人对固定候选的源码与证据审阅，不表述为另一独立审阅者验收。没有阻止本地整合的问题；生产资源和首次矩阵仍为发布验收条件。

### 3. 验证分层

| 层级 | 已有或本轮结果 |
| --- | --- |
| 研发专项 | 228项不同用例通过，其中新增取消用例27项；四套默认完整实体统计响应与原版等价，严格读取守恒 |
| 单次自然38→39对照 | 每版同源独立七库副本、同一原版前端/阈值/PWA；9个完整HTTP响应及两边只读守恒通过，没有模拟后端取消或追加回放 |
| 研发默认完整全栈 | run `20261012T152324.012689Z-fff3d57bed12`，默认full模式八必需阶段同轮PASS，实际退出0，耗时1,722,883ms（28分42.883秒） |
| 完整测试数量 | seed3937通过/2跳过、真实副本集成186通过/1跳过；三项后端跳过均为Genius客户端不可用。前端803通过/4跳过；构建、API、路由、交互、控件/长列表和Chromium/Firefox/WebKit通过。optional未运行，未验production preview |
| 首次门禁失败 | 性能测量环境的 `SPOTIFY_STATS_EXTERNAL_COVERS=0` 被沿用到完整门禁，真实副本封面用例404而失败；恢复正常默认1后单项诊断通过，再从头跑默认完整模式通过。原失败、单项控制和第二轮完整记录均保留，产品源码未变 |
| 整合工作区 | 当前七文件及完整backend Python源码与研发门禁版本相同；在整合路径新执行57项重点回归通过。研发full8是相同源码证据，本轮不声称另跑了一次整合full8；16个命名文件的Ruff/format/mypy/secret hooks、240份全部Markdown审计及diff检查均实际退出0；根AGENTS/CLAUDE一致，审阅结束时暂存区为空 |

原始全栈报告的dataset字段为unknown，保持原值；独立备份与安装收据证明输入为既定七库Online Backup来源。不得改写旧报告标签或把本地副本门禁当生产验证。

### 4. 自然序列观察与资源限制

| 指标 | Top250基线 | 加入取消修复 | 解释 |
| --- | ---: | ---: | --- |
| 点击榜单core | 99.5ms | 119.4ms | 增加19.9ms，均通过原门槛 |
| 下一页直达core | 1166.7ms | 537.2ms | 本次减少629.5ms |
| 请求窗口CPU | 2.722秒 | 0.796秒 | 本次减少1.926秒 |
| 已取消排名handler总wall | 2185.9ms | 161.6ms | 基线仍返回200；候选收到真实断开后499退出 |
| 浏览器取消到handler结束 | 2081.5ms | 56.6ms | 候选后端收到断开到结束56.5ms |
| 下一summary开始时仍有旧排名计算 | 是 | 否 | 候选未进入Top250阶段，避免本次跨页面重叠 |

请求生命周期停止有实际ASGI事件、499、阶段调用缺失和后续时序支持。其他 wall 与thread CPU差异不唯一归因于GIL/锁/I/O；单次页面/CPU收益不外推所有设备或生产。

请求起点RSS分别1273.875和896.484MiB，绝对请求峰差约377MiB主要继承起点差异；相对峰增长0和0.297MiB，相对idle变化-457.859和-120.484MiB，不能宣称全面驻留改善。启动全程峰1753.328和1641.500MiB仅为本轮观察；启动维护业务未改，OS缓存、分配器和GC时序未控制。50ms采样最大间隔约61.7/168.1ms，不保证抓到真实瞬时峰；退出时的NoSuchProcess/ZombieProcess原样保留。

Analysis发布语义原始摘要比较仍为false，未追加归一化审计；不声称所有发布行或压缩body字节一致。正确性依据四个完整实体响应、9个HTTP响应和测试；更广发布状态差异按原机器收据保留。

生产未复验：继续沿用10月11日4f3f原FIRST90为89通过/1失败，固定L3专辑直达3125.1ms超过3000ms；116API/三strict通过，原wrapper失败及排序补证保留。整体OOM、预算外驻留、原并发CPU回归和手机弹层分别保持原边界。

### 5. 独立证据与恢复

私有归档ID：`album-rank-cancellation-20261013-20261013T004438Z`。目录：`/Users/benjaminlei/.codex/archives/spotifystats-delivery/album-rank-cancellation-20261013-20261013T004438Z`。包含固定组合/取消补丁、七文件源码、两版运行源、原始对照日志/JSON/采样、四套响应对照、两轮完整门禁与失败记录、共同原版前端（不含node_modules）及数据库副本；不提交播放数据、封面、密钥或原始产物到Git。

关键入口：`archive-receipt.json`、`rank-cancellation/ready-checkpoint.json`、`rank-cancellation/controlled-pair/cancellation-lifecycle-comparison.json`、`rank-cancellation/fullgate-standard-cover-mode/canonical-reports/summary.json`。归档关键收据及七源码已校验一致；原件为复制，未移动或重写。数据库副本保留WAL/SHM；候选runtime已被后续完整门禁使用，不将其归档字节声称为原性能窗口字节状态。

历史脚本/收据保留原绝对路径，`archive-receipt.json`的old→archive映射用于恢复；保留的安装工具符号链接指向原source-baseline，重放前解析映射，不直接运行失效路径。正式数据与环境链接不跟随。恢复代码时，在指定基线先检查组合补丁，再应用；取消增量只适用于已有Top250候选。新整合复核收据位于整合工作区ignored `output/album-rank-cancellation-integration-review/`，审阅检查点保存到归档的 `integration-review-final/`，保持原样；后续本地提交收据、钩子日志、提交后的状态文档及两次提交的Git bundle另存 `local-commit-final/`，用于恢复业务和状态提交，不覆盖旧审阅收据。

当前保留main、唯一研发工作树和一个统一整合工作树。七文件已原样进入main业务提交`c21250e3`，整合树干净同步主线；研发树先按七文件精确保存恢复点，再安全快进，已采用文件内容保持一致、工作区干净，ignored副本/证据未清理。检查未发现从两工作树cwd运行的进程，此检查不证明所有历史路径消费者已结束；研发原副本/安装工具恢复路径和整合rank manifest/发布交付仍需保留。发布交付及这些消费者结束后，按[收尾规则](../reference/development-delivery-workflow.md)处理工作树。本次主线映射、同步日志、恢复点及包含状态提交的Git bundle另存独立归档`main-integration-final/`，旧收据保持原样。

### 6. 本地整合时的下一步（后续交付见第7节）

1. 本地主线整合和SHA映射已完成。下一步先核对远端、正式备份与exact-ready复用合同，再按明确授权推送并跟进CI/发布。[现有发布工作流](../../.github/workflows/production-release.yml)对main的Python改动自动触发验证、镜像和生产部署，因此不能将推送描述为仅运行CI；本轮未推送、手动触发流水线或部署。
2. 发布后使用原90场景、116API及严格只读守恒合同的首次自然窗口，重点核验固定L3专辑深链与切页取消，保留CPU/RSS/idle和失败；不预暖、重启或热重跑替代失败。
3. 详情加载、OOM资源和手机弹层分别判定，不用本地full8或单窗无OOM关闭独立问题。

### 7. 正式交付检查点

三份私密清单及393个证据文件已校验存入独立生产归档。正式版本、90/90场景、116项API、三个strict窗口、安装失败与补证及归档位置统一见下方[生产交付章节](#专辑排名取消修复的生产交付与首次验收)。


## 专辑排名取消修复的生产交付与首次验收

原记录：`2026-10-13-album-rank-cancellation-production-delivery.md`。

日期：2026-10-13。事项：`SS-2026-10-09-001`，关联 `SS-2026-10-08-001`。用户明确确认推送固定版本、跟进自动发布和部署后的首次生产验收。

业务提交 `c21250e3922c6488a65418352243a24541bcac0a` 已随主线 `c0d699e526f9323a95c63b2abf102c97d314eb2d` 推送并发布。原90场景唯一首次窗口 **90/90通过**，原116项API和三个严格只读窗口通过。最后一个旧失败案例已通过原门槛；性能子项达标。资源合同仍为 Partial，整体OOM及手机弹层保持OPEN，本报告不宣称全部资源收口。

### 版本与正式流水线

- 普通推送实际退出0，独立 `ls-remote` 确认精确 `c0d699e5`；没有再次推送产品或新修复提交。
- [日常CI 38335282434](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38335282434)：attempt1成功。日志实际记录2724单元通过/2跳过、571契约通过、803前端通过/4跳过，文档、lint与构建通过。此处与研发3937 seed/186集成的本地full8分开报告。
- [正式发布 38335282427](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38335282427)：attempt1质量、三模式和镜像通过，安装job `115098248838` 失败；仅该失败安装请求重试，attempt2安装job `115103905279` 成功。其他步骤沿用原成功执行，未再跑本地full8。API返回的attempt2 job集合包含复用步骤，不能把其数量称为重新执行的质量检查数。
- 安装遵守Online Backup、source fence、搜索精确复用、四默认排名/详情及Billboard成品、健康与联合回退合同。成功部署为dual，外部入口和私有入口未改。
- 独立八步运行核验实际0：三OCI完整SHA/healthy一致，27个镜像源码文件及3个宿主helper匹配，schema90、rank4/detail4/BB48 ready。

源码仍为已审阅和通过研发完整门禁、整合57项重点回归的版本；本次只补齐交付材料，没有修改产品、测试、统计版本、缓存容量或schema。

### 首次安装失败与有界处理

attempt1已创建Online Backup，搜索续建判定 `source_equivalent_exact_statistics_resume`、四变体预检通过；停服后，阶段副本的详情投影不是exact-ready，目标SHA详情清单也不存在，安装按规则拒绝激活。日志记录没有替换生产库或冷建详情，随后恢复旧版。独立只读核对确认旧 `4f3f2ac0` 三healthy、19组源事实一致，rank4/detail4/BB48仍ready、任务归零。

从当前已发布成品准备三份目标SHA私密清单，全程使用readonly源挂载与规范 `verify/export/validate`，不调用builder、不在正式库补建或排队。使用与正式容器一致的 `/app/data` 命名空间后，九项规范操作实际退出均为0；详情清单对实际 `music-search-resume.db` 的closed-source验证也实际0。三份目标文件权限600、哈希固定，才请求重试失败安装。第二次安装成功，原失败保留。

准备过程中的工具失败分别保留：首次只读挂载使用 `/source` 别名，Billboard文件命名空间不匹配而拒绝；规范命名空间下九项通过，但封存时宿主用户不能chmod容器root创建的文件，封存进程实际1；随后只对三个已生成文件修正属主和600权限，再严格验证并就位，实际0。这些不描述为产品故障或一次全绿准备过程。

证据记录另有缺口：第二次只读前检复用了输出文件名，覆盖了初次完整 `live-readiness.json`/`live-preflight-receipt.json`。初次摘要日志和推送收据仍保留，初次完整JSON不能恢复；后续失败状态核对已单独保存。初次摘要记录19组源事实一致、ready4/4/48、无活动任务、内存及磁盘过门槛。本报告不把后续完整收据冒充初次收据。

没有额外手动重启、预暖或热重跑。attempt1的停服/恢复属于失败安装安全处理；新SHA的首次页面窗口只在attempt2成功后的新进程执行一次。

### 首次页面、功能和只读验收

原五个观察器文件哈希保持，原90案例key/顺序、fresh context、正常PWA及原门槛不变。公开HTTPS浏览器窗口为 `2026-10-13T02:56:53.302364+00:00` 至 `2026-10-13T03:02:07.490946+00:00`。

| 项目 | 实际结果 |
| --- | --- |
| 首次90矩阵 | Chromium42/42、Firefox24/24、WebKit24/24，全90通过；原观察器实际退出0 |
| 原性能门槛 | click core≤2000ms、direct core≤3000ms、all≤2500ms；direct all按shell后计，不放宽 |
| 本轮最大值 | click core1311ms/all1693ms；direct core2125.5ms、shell后all1648ms |
| 原index39 | Chromium1280、fixed、L3、album direct：3125.1→1716.3ms；旧FAIL→本轮PASS |
| 原116 API | 108个200及8个未知404全部通过，完整payload、快照头及既有四字段专辑请求身份规范化合同保持 |
| 三strict v2窗口 | before→browser、browser→API、before→API各实际0；57保护表、37原始表、5队列、全部aux、六sidecar发布、schema/epochs/fence及七库身份守恒，access clocks无变化 |
| 生命周期 | uvicorn PID2304711/startticks168315003贯穿窗口；采样器按绑定token/PID停止，浏览器和自身采集进程已结束，未向后端发送停止信号 |

逐原案例key、顺序和门槛对照：

| 原版本 | 原通过/失败 | 原失败→本轮通过 | 原通过→本轮失败 | 本轮通过 |
| --- | --- | --- | --- | --- |
| 4f3f | 89/1 | 1 | 0 | 90/90 |
| ea93 | 86/4 | 4 | 0 | 90/90 |
| 6dac | 79/11 | 11 | 0 | 90/90 |
| 626 | 83/7 | 7 | 0 | 90/90 |

零达标→失败不表示所有单案例耗时都下降；单轮结果不唯一归因于取消、Top250或网络/调度。四个旧完整首次结果及原失败不改写。

### 原包装器失败与独立身份补证

自然90、116 API、三个strict及后置runtime采集都通过后，原包装器在比较完整容器对象时实际退出1：Backend的 `config_digest` 改变。原执行收据和stderr保持原样，没有重跑页面/API或修改原断言。

独立只读Docker inspect核对：所有其他容器字段、ID、image ID、完整SHA、StartedAt、init PID和后端PID/startticks相同。仅对当前Mounts列表枚举排列即可精确重现前后两个原digest，三容器均通过；Config、HostConfig及Mounts成员没有变化。补证实际0、零个人HTTP请求，支持运行身份连续。这是独立补证，不将原包装器改为退出0或称原执行链全绿。

### 资源窗口与仍有边界

50ms采样包含完整90及结束后10秒idle，6529样本、最大gap51.471ms，whole-window coverage通过。资源与旧4f3f同规模首次分别为：

| 指标 | 4f3f | c0d699e5 |
| --- | ---: | ---: |
| RSS起点MiB | 940.730 | 965.828 |
| RSS峰MiB | 1513.730 | 1160.348 |
| RSS结束后驻留MiB | 1493.691 | 1136.430 |
| PSS峰MiB | 1511.330 | 1158.037 |
| PSS结束后驻留MiB | 1491.291 | 1133.357 |
| 请求窗口进程CPU秒 | 72.72 | 38.65 |

峰/末RSS分别低约353.383/357.262MiB，CPU少34.07秒；起点高25.098MiB，均是两轮记录差异，不是严格单因素对照。当前cgroup全部OOM事件增量0，host oom_kill仍1→1，但结束后仍约1.11GiB驻留。384MiB估算帧缓存预算不是RSS上限；没有逐请求≤64MiB或多轮LRU平台期证明，原资源目标不因本轮无OOM而关闭。`SS-2026-10-09-001`首次延迟子项达标，整体资源合同仍OPEN/Partial；`SS-2026-10-08-001`和`SS-2026-10-11-001`各自OPEN。

### 独立归档与下一步

交付目录：统一整合树ignored `output/versus-personal-acceptance/release-c0d699e526f9323a95c63b2abf102c97d314eb2d/`。独立归档：`/Users/benjaminlei/.codex/archives/spotifystats-delivery/album-rank-cancellation-20261013-20261013T004438Z/production-c0d699e526f9323a95c63b2abf102c97d314eb2d/`，包含attempt1/2、原失败、九项准备及封存收据、成功安装、运行核验、原90/116/三guard/样本/身份补证和四版本离线对照；三个正式私密清单另存600权限文件。副本和数据产物不进入Git或镜像。

`archive-receipt.json`记录old→archive映射及逐文件校验。原脚本和收据保留原路径，恢复时先解析映射；不能直接在已结束的旧目录重跑。当前关闭的只是新SHA首次验收窗口，没有开始新的生产热复验、整轮full8或产品改造。

下一步收敛到资源问题：先依据既有单次窗口和副本证据界定驻留/缓存所有权及资源合同的缺口，再确定有界副本验证范围。手机弹层另行处理；本计划不归档，不追加本轮生产请求或重启。共享状态文档仅由主线统一维护。
