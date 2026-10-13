# 专辑排名取消修复的生产交付与首次验收

日期：2026-10-13。事项：`SS-2026-10-09-001`，关联 `SS-2026-10-08-001`。用户明确确认推送固定版本、跟进自动发布和部署后的首次生产验收。

业务提交 `c21250e3922c6488a65418352243a24541bcac0a` 已随主线 `c0d699e526f9323a95c63b2abf102c97d314eb2d` 推送并发布。原90场景唯一首次窗口 **90/90通过**，原116项API和三个严格只读窗口通过。最后一个旧失败案例已通过原门槛；性能子项达标。资源合同仍为 Partial，整体OOM及手机弹层保持OPEN，本报告不宣称全部资源收口。

## 版本与正式流水线

- 普通推送实际退出0，独立 `ls-remote` 确认精确 `c0d699e5`；没有再次推送产品或新修复提交。
- [日常CI 38335282434](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38335282434)：attempt1成功。日志实际记录2724单元通过/2跳过、571契约通过、803前端通过/4跳过，文档、lint与构建通过。此处与研发3937 seed/186集成的本地full8分开报告。
- [正式发布 38335282427](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38335282427)：attempt1质量、三模式和镜像通过，安装job `115098248838` 失败；仅该失败安装请求重试，attempt2安装job `115103905279` 成功。其他步骤沿用原成功执行，未再跑本地full8。API返回的attempt2 job集合包含复用步骤，不能把其数量称为重新执行的质量检查数。
- 安装遵守Online Backup、source fence、搜索精确复用、四默认排名/详情及Billboard成品、健康与联合回退合同。成功部署为dual，外部入口和私有入口未改。
- 独立八步运行核验实际0：三OCI完整SHA/healthy一致，27个镜像源码文件及3个宿主helper匹配，schema90、rank4/detail4/BB48 ready。

源码仍为已审阅和通过研发完整门禁、整合57项重点回归的版本；本次只补齐交付材料，没有修改产品、测试、统计版本、缓存容量或schema。

## 首次安装失败与有界处理

attempt1已创建Online Backup，搜索续建判定 `source_equivalent_exact_statistics_resume`、四变体预检通过；停服后，阶段副本的详情投影不是exact-ready，目标SHA详情清单也不存在，安装按规则拒绝激活。日志记录没有替换生产库或冷建详情，随后恢复旧版。独立只读核对确认旧 `4f3f2ac0` 三healthy、19组源事实一致，rank4/detail4/BB48仍ready、任务归零。

从当前已发布成品准备三份目标SHA私密清单，全程使用readonly源挂载与规范 `verify/export/validate`，不调用builder、不在正式库补建或排队。使用与正式容器一致的 `/app/data` 命名空间后，九项规范操作实际退出均为0；详情清单对实际 `music-search-resume.db` 的closed-source验证也实际0。三份目标文件权限600、哈希固定，才请求重试失败安装。第二次安装成功，原失败保留。

准备过程中的工具失败分别保留：首次只读挂载使用 `/source` 别名，Billboard文件命名空间不匹配而拒绝；规范命名空间下九项通过，但封存时宿主用户不能chmod容器root创建的文件，封存进程实际1；随后只对三个已生成文件修正属主和600权限，再严格验证并就位，实际0。这些不描述为产品故障或一次全绿准备过程。

证据记录另有缺口：第二次只读前检复用了输出文件名，覆盖了初次完整 `live-readiness.json`/`live-preflight-receipt.json`。初次摘要日志和推送收据仍保留，初次完整JSON不能恢复；后续失败状态核对已单独保存。初次摘要记录19组源事实一致、ready4/4/48、无活动任务、内存及磁盘过门槛。本报告不把后续完整收据冒充初次收据。

没有额外手动重启、预暖或热重跑。attempt1的停服/恢复属于失败安装安全处理；新SHA的首次页面窗口只在attempt2成功后的新进程执行一次。

## 首次页面、功能和只读验收

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

## 原包装器失败与独立身份补证

自然90、116 API、三个strict及后置runtime采集都通过后，原包装器在比较完整容器对象时实际退出1：Backend的 `config_digest` 改变。原执行收据和stderr保持原样，没有重跑页面/API或修改原断言。

独立只读Docker inspect核对：所有其他容器字段、ID、image ID、完整SHA、StartedAt、init PID和后端PID/startticks相同。仅对当前Mounts列表枚举排列即可精确重现前后两个原digest，三容器均通过；Config、HostConfig及Mounts成员没有变化。补证实际0、零个人HTTP请求，支持运行身份连续。这是独立补证，不将原包装器改为退出0或称原执行链全绿。

## 资源窗口与仍有边界

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

## 独立归档与下一步

交付目录：统一整合树ignored `output/versus-personal-acceptance/release-c0d699e526f9323a95c63b2abf102c97d314eb2d/`。独立归档：`/Users/benjaminlei/.codex/archives/spotifystats-delivery/album-rank-cancellation-20261013-20261013T004438Z/production-c0d699e526f9323a95c63b2abf102c97d314eb2d/`，包含attempt1/2、原失败、九项准备及封存收据、成功安装、运行核验、原90/116/三guard/样本/身份补证和四版本离线对照；三个正式私密清单另存600权限文件。副本和数据产物不进入Git或镜像。

`archive-receipt.json`记录old→archive映射及逐文件校验。原脚本和收据保留原路径，恢复时先解析映射；不能直接在已结束的旧目录重跑。当前关闭的只是新SHA首次验收窗口，没有开始新的生产热复验、整轮full8或产品改造。

下一步收敛到资源问题：先依据既有单次窗口和副本证据界定驻留/缓存所有权及资源合同的缺口，再确定有界副本验证范围。手机弹层另行处理；本计划不归档，不追加本轮生产请求或重启。共享状态文档仅由主线统一维护。
