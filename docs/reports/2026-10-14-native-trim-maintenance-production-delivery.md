# 维护完成原生回收：生产交付与首次验收

2026-10-14；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。本轮发布固定 `b126020862fabb968db1974d38145b99d119ee86`，业务为同 SHA 合入 main 的 `8f46b3cb9af8ebc2c546727df089d4d97e7f5309` 与此前完整预热回收 `e01a4455`。

本轮已正式发布，独立运行核验、原首次90/90浏览器、116/116 API与三个strict read windows全部通过，原wrapper实际0。维护后闲置 native 页回收的交付范围完成，资源合同仍Partial：末尾RSS较旧窗口低388MiB，但读取增长更大、CPU略高，启动高水位基本不变；整体OOM、构建峰值、逐请求64MiB与多轮平台期继续OPEN。用户明确要求连续完成后续交付，不再逐步等待确认。

## 实现与已有验证

既有 CPU 重型维护成功返回后、任务 done 之前，在原 CPU gate 内调用兼容 Linux/glibc 的 `malloc_trim(0)` helper；full warmup 仍在自身完成点调用，不重复。失败、未知或非重型任务跳过；保留缓存对象，不新增 GET 回收、完整预热、调度器或配置。

三文件业务候选、54 项提交前回归与 hooks、源 SHA 到 main 同 SHA 映射见[提交整合报告](2026-10-14-native-trim-maintenance-submission-review.md)。当前冻结代码默认[完整门禁](2026-10-14-native-trim-maintenance-fullgate.md) 8/8、actual0；[warmup=0 Linux 仿真专项](2026-10-13-native-trim-maintenance-candidate.md)支持 ready/final RSS 低约343/333MiB，但采样峰及读取增长没有改善。本轮不重复本地完整门禁或仿真配对，也不把旧 c0d 首次窗口改称新版本证据。

## 研发推送、CI 与发布输入

研发 `codex/album-rank-cost` 普通精确推送到 b126；此时远端 main 仍 c0d。首轮 Git TLS 查询失败，未执行 push，第二轮成功，原失败保留。研发 [CI 38500883926](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38500883926) attempt1、实际 job115647293828 成功；文档、unit、contract、lint、前端测试与构建全部成功。研发流水线的 production contract step 按原条件 skipped，正式 Release 必须另行实际执行该检查。

发布前核对生产仍 c0d、dual 三容器 healthy、schema90、plays94760、活动任务0、warmup=0。排名与详情成品重新以 b126 绑定导出/规范验证；事实 CLI、builder、schema 和部署脚本在 c0d 到 b126 间未变。导出使用当前已发布镜像、512MiB独立容器、源只读挂载、禁网无端口，无 cold build 或源写入。Billboard 不重复 live export，复用旧规范验证过的48目标清单，当前 live source fence 与 builder 完全一致。

三份成品均600权限，只在私密本地和服务器 backups 保存，未进入 Git、镜像或 CI artifact。服务器正式成品路径分别为 `versus-ranks-b126020862fabb968db1974d38145b99d119ee86.json`、`music-detail-b126020862fabb968db1974d38145b99d119ee86.json`、`billboard-b126020862fabb968db1974d38145b99d119ee86.json`；上传后 SHA256 与规范导出/已有验证一致。源指纹、原容器身份及启动时间仍一致，未改正式数据库或配置。

本地 full/showcase/dual 三项 profile-only 各实际0；上传后 MemAvailable 约1.76GiB、空闲磁盘约6.33GiB。正常发布仍由目标镜像的 Online Backup、源等价复用、rank/detail/Billboard 准入、健康及联合回滚门禁判定，输入准备不能替代正式激活。

## 正式发布

普通精确推送 main c0d→b126，未 force；[main CI 38502500846](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38502500846) attempt1与[正式 Release 38502500843](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38502500843) attempt2均实际success。研发、main与Release质量结果均为unit2742 passed/2 skipped、contract571 passed；前端803 passed/4 skipped并构建成功。正式Release另执行28项生产contract及三模式，均成功；不把attempt2继承的成功job当成重复执行的新验证。

Release attempt1 deploy job115657620105在最初脚本 rsync 的 SSH握手收到 Connection reset，actual255，0 bytes，未进入备份/切换。后置只读核验三c0d容器身份、StartedAt与healthy不变，schema90/plays94760/活动任务0。保留首轮失败，只重试该deploy job；GitHub connector因integration写权限403失败、gh wrapper查询EOF均保留，直接CLI同job rerun成功。attempt2实际deploy job115658306844成功，没有重跑成功的质量检查或镜像构建。

目标两镜像的TCR push/pull、manifest、linux/amd64与revision核验通过。03:07:32Z生成Online Backup `spotify-stats-pre-release-b126020862fa-20261014T030712Z.db`；搜索 `source_equivalent_exact_statistics_resume` 复用，ready_rows12，无statistics冷建；排名4、详情4、Billboard48精确门禁通过。03:13:12Z正式部署完成，dual与既有public展示访问方式保持。独立核验实际三OCI完整b126/healthy、30镜像源码/3helpers、schema90及两个loopback运行面通过；宿主3001/3002只绑定127.0.0.1，没有改私有外部入口或Tailscale。

## 首次验收执行约束

在 main 推送前准备并校验原五份 observer 的冻结哈希；90场景顺序、目标、浏览器/视口、fresh context、PWA 和阈值以及116 API规则均不修改。仅包装脚本绑定新 SHA/新材料目录；Docker Mounts 在配置摘要前规范排序，修正历史相同配置不同枚举顺序导致的假失败，原五工具字节不变。

正式流水线成功后独立核验三 OCI、30份镜像源码、3个服务器 helper、两个 loopback运行面、schema90与search/rank/detail/Billboard ready；等待启动维护自然完成。然后只取新版本的一个自然首次90窗口与资源采样，接原116 API及三个 strict read windows。无额外手动重启、预暖或热重跑，私有外部入口维持现状；原失败完整保留。单窗观察即使改善也不关闭逐请求64MiB、多轮平台期和整体OOM。

## 首次验收与资源结果

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

## 证据、提交与工作树处置

独立恢复入口：`native-trim-maintenance-production-delivery-20261014-20261014T024308Z`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。保存原查询/TLS/API传输失败、实际refs/push、研发和正式job日志、首轮deploy失败/后置身份/仅失败job重试、只读生产基线、规范输入验证、私密成品及上传指纹、三模式、五份不变observer、新版本唯一首次90/116与三strict、资源逐样本与旧窗对照、固定源码、最终协调文档及提交恢复bundle。ZIP CRC、observer与私密输入哈希校验收据独立保存，数据/payload不入Git。

旧c0d首次结果未重跑或改写，继续使用既有独立归档。源业务8f46→main8f46为同SHA快进；发布b126与随后纯文档提交分别记录。本轮协调文档由main统一提交，研发/统一整合树安全同步；不做reset/clean或远端分支删除。OOM问题链仍OPEN，保留唯一`codex/album-rank-cost`研发树与至多一个统一整合树服务同一未关闭合同，当前发布候选不再挂HOLD。服务器只清理已取回且独立保存的本轮owned临时目录，正式成品与回滚备份保留。实际文档HEAD、refs和同步/清理结果见归档最终收据。
