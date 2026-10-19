# 五文件内存修复的生产交付

日期：2026-10-19。事项：SS-2026-10-08-001。**本轮开发与发布正式收口（CLOSED / RELEASED），OOM稳定性保持OPEN / OBSERVING。** 本次沿用[精简计划](../plans/2026-10-19-performance-scope-and-memory-closeout.md)，不再追加优化或实验。

## 版本与采用范围

生产于北京时间15:41完成发布，API、完全版Web和公开Web的实际镜像revision均为 `f1280ac135de37bb730bcec2cdc0fa6bf7d9b428`，三容器healthy。来源映射为：

| 来源或提交 | 主线采用情况 |
| --- | --- |
| c844b98f中的5业务文件、16回归 | 精简提交 `6805fe4ce4151052ec7cb61582cea8495a03ec27`，同SHA快进main |
| `f69681580445ac97d6379686a919dd3bf877dad5` | 发布遇真实WAL阻塞后，把已有闭库与原inode保留步骤前移，补充真实已提交WAL回归 |
| `f1280ac135de37bb730bcec2cdc0fa6bf7d9b428` | 同步既有排名部署顺序断言；五业务文件仍与6805/c844完全一致，最终发布SHA |

仍为schema90、默认分配器；未采用schema91结构、分配器ENV或新的缓存预算。没有前端业务变更。用户后续明确授权推送、必要CI、main整合和现有流程发布后才执行；本地提交阶段原有的“未授权推送/部署”记录保留其历史语境。

## 验证与发布证据

- 337项受影响回归、既有统计对账及10-16相同五业务源码的默认full8直接复用，没有新执行本地full8或全站浏览器矩阵。选择与原生对照见[精简整合报告](2026-10-19-oom-minimal-five-file-integration.md)。
- 实际部署顺序补修另验46项发布/榜单传递、28项生产契约及13项排名部署回归；公共配置、文档审计和四项提交hooks通过。真实WAL用例在旧顺序先失败，新顺序保留原inode、闭合三库WAL并保全已提交事实；busy/checkpoint拒绝及联合恢复约束保持。
- 最终SHA的[main CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39215446238)成功。[正式发布流程](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39215446197)的质量/生产契约、full/showcase/dual配置门禁、同SHA linux/amd64镜像构建和部署全部成功。该流程实际后端unit为3080通过/2跳过，contract为571通过；不将其称为本地全栈验收。
- 既有流程完成TCR发布及digest回拉、Online Backup、搜索四变体精确统计复用、四套详情投影、48份Billboard成品与个人排名exact-ready检查，以及dual运行模式的健康、入口和写隔离核验。三模式是配置门禁，实际生产模式仍为dual。
- 发布保护点为 `/opt/spotify-stats/backups/spotify-stats-pre-release-f1280ac135de-20261019T073609Z.db`。CAS current切换为f128，previous仍为b1260208，既有发布文件清理步骤成功；没有手动绕过成品门禁或在正式库冷建。

## 保留的失败与处理

6805的[首个发布run](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39207356269)两次部署作业均失败，不能按最终成功改标：

1. 首轮复用的旧续建副本搜索统计ready，但三张详情投影表为空；生产库和本轮Online Backup都有四套详情成品。门禁拒绝切换，旧Backend受控恢复healthy，镜像和生产数据库未替换。失败续建副本以原inode保留为 `backups/music-search-resume-failed-6805fe4ce415-attempt1.db`；仅让现有流程从新Online Backup准备续建副本，没有冷建统计或详情。
2. 第二轮详情四变体通过，随后Billboard导出因停服源WAL未闭合被拒。原因是已有checkpoint和原inode保留排在导出后；只将该完整步骤前移。该轮也受控恢复旧Backend，未替换生产数据库。
3. f696的[后续CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39213862320)发现一条漏同步的静态顺序断言，要求rank prepare在preserve之前；该轮测试失败，未进入构建/部署。f128同步为preserve → detail → rank prepare → backup → promote → install → activate，联合恢复断言继续保留。

两次旧Backend停启属于发布失败恢复，不能以Docker RestartCount=0描述成“没有发生过停启”。API日志读取和GitHub查询的临时EOF、最初直接请求Backend被受信网关策略403拒绝的探针错误，也在私密证据中保留，没有修改访问策略或重跑业务实验。

## 线上正常读取与边界

发布前后通过既有完全版loopback网关，各顺序读取health、歌曲157、Midnights专辑L3/fixed、Taylor Swift艺人dynamic统计；三个统计都使用include_rank_context=false。四项均200。表中前值来自旧进程暖状态，后值来自新进程首次读取，**不作时延收益对比**。

| 请求 | 发布前秒 | 发布后秒 | 正文核验 |
| --- | ---: | ---: | --- |
| health | 0.005 | 0.015 | 前后逐字节一致 |
| 歌曲统计 | 0.825 | 1.513 | 前后及既有原生旧版/候选逐字节一致 |
| 专辑统计 | 0.149 | 8.731 | 新正文与既有原生旧版/候选逐字节一致；旧暖响应指纹差异保留 |
| 艺人统计 | 0.374 | 6.049 | 前后及既有原生旧版/候选逐字节一致 |

专辑发布前暖响应为42804字节，发布后为42828字节，顶层数值与字段集相同，但原始正文SHA不同。为核对仅补一次正常专辑GET获取完整正文：新正文SHA为 `3abfd5b81acb3620734c4b674a92d8423d81e0175fcce0806980acf60ae5edba`，与已保存原生旧版和候选的同请求正文完全相同。发布前只保存指纹而未保存完整正文，无法事后定位24字节；不宣称此项前后字节相同，也不据此新增修复或启动实验。

本次不重新验收摘要首屏或浏览器交互；它们复用此前已交付的加载证据。完整统计首次冷计算开销保留，不能把暖/冷差当作性能回归或加速证明。

发布后快照：Backend实际uvicorn进程RSS485.266MiB、VmHWM997.203MiB，宿主MemAvailable约2.381GiB、磁盘可用约9.219GiB；三容器OOMKilled=false、RestartCount=0，采集的启动后日志无error/traceback行。生产Backend仍没有Docker内存/CPU硬限额，warmup=0、Search启动补建=0，未改配置。这只是当前正常读取快照，不代表长期无OOM。

隔离原生单组的峰值1191.102→981.051MiB、空闲582.469→513.332MiB（低69.137MiB）继续有效，但不把该比例套到线上快照；其启动CPU高0.439%、墙钟高3.058%及完整统计冷开销也保留。

## 证据、工作树与剩余观察

本次发布日志、两次失败、修复前后回归、CI、运行身份、响应指纹和差异核验存于独立归档 `~/.codex/archives/spotifystats-delivery/oom-minimal-release-20261019/`。原本地6805源码包/bundle与原生证据继续保留在 `oom-minimal-integration-20261019/`，不覆盖历史回执。

原研发bfecef52工作树已通过Codex可恢复归档；完整ignored output经同文件系统rename保全至 `~/.codex/archives/spotifystats-delivery/oom-source-closeout-20261019/ignored-output/`，目录inode保持，没有复制或删除其中数据库、日志和失败证据。恢复该工作树后，把output链接回该目录即可复用原路径；内部历史绝对symlink原样保留，不自动重跑旧实验。学校本次资源清理及16服务/29镜像保全证据直接复用，未再次占用学校或启动本机Docker。

2026-10-19提交准备核对：上述ignored output目录当前不存在；前段保留当时保全与恢复方式的记录，本轮未核实归档现位置及可恢复性。

发布提交未混入main原两份未提交文档；本轮文档收口在状态总表上增补当前决定，归因过程及独立归因报告按历史阶段保留。统一整合树与main同步，无活跃开发，仅供观察文档与证据同步暂留，OOM结项后归档；远端开发分支保持冻结，没有删除。

## 正式收口决定

2026-10-19用户明确要求本轮开发和发布正式收口，OOM保留为观察中，不再追加优化或实验。业务生产版本保持f1280ac1；交付文档提交为 `66ad5e600b0cc4b09ac8c3886fdfeaa88da91768`，其[文档CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39219368463)成功。本节及状态、计划入口更新只复用已有证据，没有新增生产采样、业务请求或资源实验。

收口前已有的北京时间22:37:19只读快照显示：三容器仍为f128且healthy，RestartCount=0、OOMKilled=false；uvicorn RSS530.348MiB、VmHWM997.203MiB，宿主MemAvailable约2.331GiB，采集日志无error/traceback。与16:11:30的RSS530.172MiB相比，约6小时26分后仅高0.176MiB。期间全部正常访问与后台工作未穷尽审计，两次近持平快照只提供短期信号，不能作为空闲趋势、长期稳定或无泄漏证明。

SS-2026-10-08-001保持OPEN / OBSERVING，仅在约1–3天实际正常使用及自然发生的相关维护中观察增长、宿主余量与意外重启/OOM。相同工作集增长有界、实际容量足够、统计与体验正常，且无归因于本链的新OOM/意外重启后，再关闭该观察事项。没有实际使用的时间不算使用验证；不新建周期任务或注入压力流量。只有具体新失败才记录并决定是否重开开发，未采用候选、旧矩阵及已保留差异均不转为新的开发欠账。
