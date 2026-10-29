# SpotifyStats 开发状态总表

面向维护者与协作Agent，统一记录当前事项、交付边界和下一步。产品介绍见[项目首页](../README.md)，使用方法见[使用指南](user-guide.md)。

文档核对：2026-10-29。文档整理基线为 `509a88f3`；生产结论引用各报告当时的记录，未因文档整理重新采样。实现、本地应用、提交、推送、部署、观察和外部验收分别记录。本轮文档整理已完成本地验收，71312b6a已推送且两条远端CI成功；最新CI及主线整合边界见[CI确认与主线整合](reports/2026-10-25-documentation-cleanup-delivery.md#ci确认与主线整合)。

## 当前概况

核心产品已经具备个人音乐头版、播放分析、音乐档案、年度总结、个人 Billboard、音乐查找和实体详情。最近一轮已完成专辑旗下单曲成绩、发行周期来源/日期、Title归属保护及限定发行参照能力的生产交付，备份规则与分支清理也已单独收尾。

最新应用发布为10-28的 `6a5e3d69`、schema96；排行/艺人读取窄列修复已发布，10-29独立运行门禁与17HTTP通过，14条业务正文与固定基线一致，见[窄列修复交付](reports/2026-10-19-minimal-memory-production-delivery.md#2026-10-29-窄列修复发布与独立验收收尾)。同日先前的c6f8ea73恢复基线重建和发布重试已单独完成，见[恢复与发布验收](reports/2026-10-28-recovery-baseline-and-release-retry.md)。10-24的 `dacdb862` 已交付确认5项目及4参照/2日期；原始记录、项目成员、7015条发布归属、Spotify声明和原六指标UI保持。前批4项日期只在本地应用，生产待审23项、本地19项是两套环境的不同边界；未批准的录音映射和The Moment归属继续暂缓。以下版本、数量和健康结论均归属各报告当时的验证，不冒充本轮生产现场检查。

| 状态维度 | 已确认结论 | 证据范围 |
| --- | --- | --- |
| 实现与仓库 | 业务main/应用发布基线为6a5e3d69，前轮恢复报告e43d9372已推送；本轮文档另行收尾。窄列修复已交付，独立移动端555195c2仍待按当前main提取 | [窄列交付](reports/2026-10-19-minimal-memory-production-delivery.md#2026-10-29-窄列修复发布与独立验收收尾)、[恢复交付](reports/2026-10-28-recovery-baseline-and-release-retry.md) |
| CI | 6a5e3d69质量CI和正式Release均completed/success；3281 unit、578 contract、817前端及构建、28部署契约和三模式门禁通过。此后纯文档提交的CI状态另行核对，不等于应用重新发布 | [质量CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40664122082)、[正式Release](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40664122222) |
| 生产发布 | 6a5e3d69/schema96、dual/public；三容器healthy，10-29独立搜索/排名/详情/Billboard门禁及17HTTP通过，14条业务正文一致；current=6a5e3d69、previous=c6f8ea73，发布容量及恢复门禁通过；既有数据治理范围保持 | [窄列修复交付](reports/2026-10-19-minimal-memory-production-delivery.md#2026-10-29-窄列修复发布与独立验收收尾)；长期内存、私有DNS、模型及真实终端继续独立跟踪 |
| 默认完整全栈 | 已有历史完整门禁按各自源码和输入版本保留；最近发行周期交付为受影响回归、CI及生产专项，不称当前main新跑过默认完整全栈 | [历史联合全栈](reports/2026-10-07-release-date-and-empty-stats-acceptance.md#发行日期精度与详情空统计联合集成验收)、[最新验收范围](reports/2026-10-24-release-cycle-review-and-delivery.md#发行周期共用能力六项目副本验收与五项生产交付) |
| 真实模型、终端与入口 | 最新5项目有桌面/390×844及展示HTTPS额外81HTTP证据；私有网关经SSH隧道验收，私有Tailscale域名DNS直连未通过 | [入口边界](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收)；生产LLM、真实OAuth与物理手机仍单独验收 |

## 尚未完成与待验收

这里只保留尚未交付的修改、明确未完成的生产应用、观察和外部验收。已发布的发行周期、Title及共用能力不再重复列入；剩余数据审核不代表已交付功能重新开放。P1/P2为排期建议，不表示已经启动。

| ID | 事项 | 状态与剩余工作 | 优先级 / 下一步 | 证据或方案 | 最后核验 |
| --- | --- | --- | --- | --- | --- |
| SS-2026-10-23-002（生产范围） | 4项已确认日期的生产应用 | 本地应用与验收已收口；42144、41610、42108、41913四项日期仍未在生产应用，不属于dacdb862确认5项目范围 | 待明确生产交付指令；按生产自身fresh副本及既有保护/快照合同处理，不重复开发已完成能力 | [本地应用](reports/2026-10-23-release-cycle-next-batch-review.md#用户确认后的本地正式应用与验收)、[最新生产边界](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收) | 2026-10-24（报告记录） |
| SS-2026-10-21-005 | 移动端长时间轴排名趋势孤立点不可见 | OPEN / 待主线整合；555195c2历史本地候选随be175498归档，尚未进入main或生产 | P2：按当前main提取RankTrendChart及定向回归，复核后单独交付；不整体恢复混合分支 | [问题台账](archive/06-productization-closeout/2026-10-25-issue-register-history.md#2026-10-21-移动端排名趋势孤立点不可见)、[恢复入口](reports/2026-10-21-versus-release-cycle-repair-acceptance.md#2026-10-25混合研发分支归档清理) | 2026-10-25（源码与待办核对，未重新验收） |
| SS-2026-10-11-001 | 手机播放统计加载时弹层状态丢失 | OPEN；加载中打开时间弹层后，数据返回导致控件重新挂载、弹层关闭，尚未产品修复 | P2：独立保持控件及编辑状态连续性；既有门禁通过不能关闭该产品问题 | [台账](issues/README.md)、[受控复现](reports/2026-10-09-music-detail-chart-performance-acceptance.md) | 2026-10-11（复现证据；本轮未重测） |
| SS-2026-10-08-001 | 后端内存稳定性 | OPEN / OBSERVING；窄列修复6a5e3d69已发布，代码与本轮交付CLOSED。10-29三容器约21小时健康、无OOM/额外重启，独立门禁与17HTTP通过；短时采样与已运行时长不代表长期正常使用覆盖 | P1：仅正常使用观察；不再把已交付补丁列为待提交/待发布，不追加优化或资源矩阵。再次出现具体容量/体验回退时记录现版本与场景再决定 | [本轮发布与验收](reports/2026-10-19-minimal-memory-production-delivery.md#2026-10-29-窄列修复发布与独立验收收尾)、[精简计划](plans/performance-and-memory-closeout.md) | 2026-10-29（已发布验收，长期观察OPEN） |
| SS-2026-08-24-004 | 全栈门禁耗时与重跑成本 | 部分完成；分阶段、preflight、排他锁与去重已交付，三次低干扰稳定验收及安全续跑/分片尚无闭环 | P1：后续有对应需求时根据当前计时和慢测试profile处理；旧单次24分22秒不等于三次稳定收口 | [门禁计划](plans/fullstack-verification-performance.md)、[问题台账](issues/README.md) | 2026-10-07（历史证据，未新增测试） |
| SS-2026-08-06-005 | PWA双平台与真实OAuth | 工程已实现，iPhone/Android安装、键盘、安全区、返回及真实consent回跳仍缺验收闭环 | P1（需要移动发布时）：按目标终端分别验收，不以模拟视口或CI推定 | [PWA路线](plans/appification-and-mobile-distribution.md) | 2026-10-02（文档记录，未真机验收） |
| ACCEPT-01 | 真实模型及私有外部入口 | 生产LLM仍待独立验收；10-24展示HTTPS及SSH隧道页面已通过，但Tailscale私有域名DNS直连未通过 | 分别核查模型与私有域名外部条件；不重开已交付的5项目代码/数据范围 | [最新入口边界](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收)、[验证规则](reference/fullstack-verification.md) | 2026-10-24（入口报告；模型未新增核验） |
| DATA-01 | 存量L1身份歧义审核 | 证据不足项仍需人工审核；历史约600条review、21个冲突不是当前数量，10-20已确认的33首署名阻塞已另行解决 | P2：有新的具体治理需求时先读取现库差异和证据；不重复处理已批准身份/署名决定 | [L1边界](reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)、[后续署名交付](reports/2026-10-21-album-song-performance-attribution.md#最终发布与生产验收) | 2026-10-25（报告对照，未统计现库队列） |
| DATA-03 | Album/艺人身份证据不足项 | 未能唯一解析的身份仍待证据；10-03的13个Album/17条未解析行仅是历史样本，不能直接当作当前余量 | P2：按稳定身份与来源证据审核，不猜canonical或自动批准关系 | [原身份边界](reports/2026-10-03-album-metadata-delivery.md#专辑目录与艺人证据生产交付)、[最新来源/身份边界](reports/2026-10-24-release-cycle-review-and-delivery.md#发行周期共用能力六项目副本验收与五项生产交付) | 2026-10-25（仅文档对照，未重测数据） |

发行周期独立数据治理以10-24最新应用后记录为准：**生产剩23项（粗日期10、来源8、艺人身份5），本地剩19项（粗日期6、来源8、艺人身份5）**。两者差异是上表4项日期尚未在生产应用；Nevermind录音映射未获批准，The Moment日期及两首歌曲归属继续暂缓。其余来源、日期及身份只在新证据或人工决定出现时处理，不将原98/29/24项重新计作未完成开发。见[最新生产报告](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收)。

历史DATA-02 / SS-2026-10-03-002的60,294条搜索派生FK orphan不再作为当前异常数量或主动清理待办：后续发行周期发布预检已记录orphan=0，10-24七库完整性与外键检查通过。旧失败和旧集合证据保留，本次没有执行数据清理或重新核查数据库。见[后续生产预检](reports/2026-10-22-release-cycle-production-delivery.md)、[最新七库核验](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收)。

当前后续：仅推进上述独立待办、明确的生产应用与正常观察。已交付的加载体验、发行周期通用能力、Title修复及确认5项目保持收口；模型/终端/入口验收和数据治理分别排期，不默认重跑应用全量或资源矩阵。

## 可以探索的方向

以下均未登记为在开发项目。启动前先回答收益与资源条件；探索通过后再形成实施计划。

| ID | 方向 | 当前状态 | 价值与启动条件 | 来源 | 最后核验 |
| --- | --- | --- | --- | --- | --- |
| EXPLORE-01 | MusicBrainz 第二署名来源 | 仅规划 | 在隔离样本中证明能发现 Spotify 无法解决的署名/身份冲突；稳定 ID、限流和来源条款明确后再接入 | [元数据路线](plans/multi-source-music-metadata.md) | 2026-10-02 |
| EXPLORE-02 | 歌曲级语言统计 | 仅规划 | 支持多语言艺人的具体录音统计；先明确来源、人工标注样本、混合语言/无歌词/unknown 和消费者范围 | [元数据路线](plans/multi-source-music-metadata.md)、[现有艺人语言规则](reference/artist-language-statistics.md) | 2026-10-02 |
| EXPLORE-03 | Apple Music、Cover Art Archive、Discogs / Wikidata | 延后 | 先证明凭据与维护成本值得；封面替代先有可靠 release 身份，长尾来源优先辅助人工核验 | [元数据路线](plans/multi-source-music-metadata.md) | 2026-10-02 |
| EXPLORE-04 | 缺图兜底的身份准确性 | 待量化 | 已有 ID 时优先按 ID 读取；先统计名称搜索误配率，不凭缺图现象批量替换 | [元数据路线 §10](plans/multi-source-music-metadata.md#10-2026-09-24-spotify-现有字段利用审计后续问题) | 2026-10-02 |
| EXPLORE-05 | 专辑真实时长参与 LP/EP 分类 | 待量化 | 依赖完整曲目表，比较真实总时长与当前估算对分类的影响，再决定是否修改 | [元数据路线](plans/multi-source-music-metadata.md)、[分类消费者](../backend/services/analysis_stats_service.py) | 2026-10-02 |
| EXPLORE-06 | 长期浏览器 physical footprint | 观察项 | 历史资源门禁已通过；保留 footprint 增长诊断，仅在可重复增长或使用影响出现时重新立项 | [资源报告](reports/2026-09-22-runtime-resource-optimization.md) | 2026-10-02（未重新测量） |

## 明确暂缓与需要重新决策的事项

| 方向 | 当前决定与重新启动条件 | 依据 | 最后核验 |
| --- | --- | --- | --- |
| Capacitor / 原生安装包 | 暂缓；先完成 PWA 真机与 OAuth，并明确 App Store 或安装包分发需求 | [PWA 路线](plans/appification-and-mobile-distribution.md) | 2026-10-02 |
| 微信小程序 | 不作为主路线；明确微信分发与平台能力需求后另行评估 | [PWA 路线](plans/appification-and-mobile-distribution.md) | 2026-10-02 |
| 异机备份扩展 | 早期 PWA 计划有此要求，尚无闭环证据；后续已选择简化日常备份，是否继续作为移动发布条件需重新确认 | [PWA 历史要求](plans/appification-and-mobile-distribution.md)、[当前备份手册](../deploy/production/README.md) | 2026-10-02（未检查异机设施） |
| 旧重型 account、歌词/发行档案等详情消费入口 | 当前产品边界不启用；只有新的产品决策才重新立项 | [项目约定](../AGENTS.md)、[元数据规则](reference/music-metadata-management.md) | 2026-10-02 |

## 已完成的主要开发

各项仅代表所列范围的历史交付。完整验证、部署边界和数量见对应报告；整理前的详细表保存在[历史完成记录](archive/06-productization-closeout/2026-10-25-development-status-history.md#已完成的主要开发)。

| ID | 已交付能力 | 状态与证据 |
| --- | --- | --- |
| SS-2026-10-08-001（10-28窄列交付） | 排行与艺人读取内存开销降低 | CLOSED / RELEASED；6a5e3d69已推送、质量CI与发布成功，10-29独立门禁、17HTTP及14条业务正文对照通过；长期正常使用观察单独保留OPEN；[交付](reports/2026-10-19-minimal-memory-production-delivery.md#2026-10-29-窄列修复发布与独立验收收尾) |
| SS-2026-10-28-001 | 清理后新完整恢复基线与生产发布重试 | CLOSED / RELEASED；负责人为当前聊天Codex；新七库/原inode及完整运行资料封存、保留记录修复通过；c6f8ea73发布第2次尝试成功，独立生产门禁、9HTTP及12项桌面/手机页面检查通过；current=c6f8ea73、previous=dacdb862；报告已随e43d9372推送，旧f153历史数据库缺失如实保留；最后核验2026-10-28；[报告](reports/2026-10-28-recovery-baseline-and-release-retry.md) |
| SS-2026-10-26-001 | 本地文件整理、日志迁移与退役代码清理 | CLOSED / INTEGRATED；负责人为当前聊天Codex；完成旧产物清理、18脚本迁移、2工具删除、61前端文件退役及有效测试迁移，补齐两处后端测试导入；源cbf7ef98、1cbd0ad1、16ad95cc原样快进main，文档收尾随main推送；分支CI 40518424036全部成功（3276 unit、578 contract、817前端测试及构建/lint）；main c6f8ea73质量CI及10-28生产发布第2次尝试成功，独立验收见[本轮交付](reports/2026-10-28-recovery-baseline-and-release-retry.md)；最后核验2026-10-28；[主线整合](reports/2026-10-26-project-file-organization.md#分支ci通过与主线快进整合) |
| SS-2026-10-25-001 | 项目文档整理与更新 | CLOSED / LOCAL DOC VERIFIED；读者分工、命名、安装与授权说明、Agent提交入口及全部文档复验通过，正式Markdown保持242份；71312b6a已统一推送，两条CI成功；按[主线整合合同](reports/2026-10-25-documentation-cleanup-delivery.md#ci确认与主线整合)补齐发布忽略路径，并在最新提交CI通过后快进main，不部署；具体版本与远端结果以Git／Actions记录为准 |
| SS-2026-10-24-001 | 目标艺人列名、非占有发行参照、显式日期冲突审核与确认5项目 | CLOSED / RELEASED；schema96与dacdb862已交付；[交付](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收) |
| SS-2026-10-23-002（本地范围） | 4项独立原专辑日期应用 | APPLIED / LOCAL ACCEPTED；本地应用与验收收口；[本地验收](reports/2026-10-23-release-cycle-next-batch-review.md#用户确认后的本地正式应用与验收) |
| SS-2026-10-23-001 | Title原项目日期与逐曲版别证据、既有歌曲归属保护 | CLOSED / RELEASED；f153dc9f已交付；[生产交付](reports/2026-10-23-title-release-attribution-repair.md#用户授权后的提交生产发布与上线验收) |
| SS-2026-10-21-006 | 发行来源类型、稳定身份、独立日期与原表格UI恢复 | CLOSED / RELEASED；2f4b7f26已交付；[生产交付](reports/2026-10-22-release-cycle-production-delivery.md) |
| SS-2026-10-21-004 | 榜单对决发行周期恢复 | CLOSED / RELEASED；P0–P6完成，c741a96f已交付；[最终验收](reports/2026-10-21-versus-release-cycle-repair-acceptance.md) |
| SS-2026-10-21-001 | 专辑旗下单曲成绩归属与稳定项目链接、正式点数排名 | FIXED / RELEASED；五个候选原SHA合入，最终15d96469已交付；[最终发布](reports/2026-10-21-album-song-performance-attribution.md#最终发布与生产验收) |
| SS-2026-10-21-002 / 003 | UTC详情日期边界、逐曲署名增量目标登记 | FIXED / RELEASED；24e2ccf7及15d96469已交付；[交付边界](reports/2026-10-21-album-song-performance-attribution.md#最终发布与生产验收) |
| DONE-01 | 首页、播放分析、音乐档案、年度总结、音乐查找与详情的当前产品结构；共享统计事实的响应式展示 | 已实现；[项目介绍](../README.md) |
| DONE-02 | L2/L3 身份、专辑归属与逻辑事件；次数/时长双轨；播放排行及 Billboard Records 稳定排序 | 已实现；[L2/L3 修复](reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md) |
| DONE-03 | 全应用持久结果与快照、后台构建、旧结果连续展示；搜索共享构建和增量维护 | 已实现；[全应用性能成果](reports/2026-09-21-full-application-performance-optimization-outcome.md) |
| DONE-04 | 持久化导入工作台、来源与指纹基线、原子发布、故障恢复及旧库升级 | 已实现；[导入治理最终验收](reports/2026-09-21-import-incident-and-remediation.md#数据导入处理与治理-s6-最终验收报告) |
| DONE-05 | Spotify Track 有序多艺人证据、自动有效署名投影、身份冲突保留旧结果与人工覆盖优先 | 已实现；提交 `56a23500` / `9eccd00e`；[证据交付](reports/2026-09-24-spotify-track-artists-evidence-delivery.md) |
| DONE-06 | 日常轻量启动、构建输入清单、预热分层、重型任务排他与长期资源优化 | 已实现；提交 `a0df33a4`，集成 `c1acbec6`；[资源专项与完整全栈](reports/2026-09-22-runtime-resource-optimization.md) |
| DONE-07 | V6 统一模型步骤、持久恢复、预算与租约、冻结年报上下文、审核章节渐进交付及 SSE 恢复 | 已实现；提交 `8edcd1c8`，集成 `1f5863a8`；[真实模型及最终全栈](reports/2026-09-22-ai-agent-v6-baseline-and-acceptance.md#ai-agent-v6-统一运行时与渐进报告最终本地验收) |
| DONE-08 | 160/320/640px WebP、按尺寸/DPR 加载、新下载生成、缺失回退及有界补建；CI 浏览器依赖延迟导入 | 已实现；历史 `84168eba` / `194fd113`，扩展 `f139ec4d` / `814ea7cb`；[封面验收](reports/2026-10-03-cover-image-optimization-acceptance.md) |
| DONE-09 | 精简备份：每周压缩一份仅留2份；现有timer每天清理；已完成恢复/临时材料48小时；支持历史清空 | 10月28日脚本与现有timer已单独更新，28项专项及服务器隔离验证通过，首次追补周备份成功。其他会话的恢复基线/发布重试独立进行，本事项不部署应用；[备份规则](../deploy/production/README.md#发布文件收尾)；10-29 03:36:37首次正常日调度退出0，零删除，本周已有备份按规则跳过，观察收口 |
| PLAN-2026-10-02-001 | 合作曲排行按有效署名统一三个榜、全部参与艺人、占比与 L3 实际版本过滤 | S1–S6 已完成；`fa683d97` 已推送；[验收报告](reports/2026-10-02-collaboration-ranking-acceptance.md) |
| SS-2026-09-24-001 | 专辑完整分页、可靠发行位置与只读消费者 | 固定输入4f9a01ff，业务8464ffa6；已实现、完整本地验收；[最终集成](reports/2026-10-03-album-metadata-delivery.md#专辑证据与最新封面主线最终本地集成验收) |
| SS-2026-09-24-002 | Album有序稳定ID、canonical解析、人工优先与冲突保留 | 固定输入8f638494；已实现、完整本地验收；[专项](reports/2026-10-02-album-artist-evidence-verification.md) |
| SS-2026-10-06-001 | 曲目署名来源优先级与标题解析 | S0–S5已完成；人工优先、完整名保护和未知候选防复发；[验收记录](reports/2026-10-06-track-credit-resolution-acceptance.md) |
| SS-2026-09-24-003 | 发行日期来源精度、旧值降级、日期比较与展示 | 已实现并集成为7f7185cf；发布补修76a4968；[精度合同](reference/release-date-precision.md) |
| SS-2026-10-07-001 | 非榜单详情安全空态与真实零播放恢复 | 已实现，9c360714集成为7f7185cf；[联合全栈](reports/2026-10-07-release-date-and-empty-stats-acceptance.md#发行日期精度与详情空统计联合集成验收) |
| SS-2026-10-08-002 | 榜单对决个人播放加载 | COMPLETED / RELEASED；[验收](reports/2026-10-08-versus-personal-statistics-performance-acceptance.md) |
| SS-2026-10-09-001 | 详情榜单成绩首次加载 | COMPLETED / RELEASED（加载体验）；[生产交付](reports/2026-10-14-native-trim-maintenance-delivery.md#维护完成原生回收生产交付与首次验收)，内存与手机弹层另列 |
| SS-2026-10-03-003 / SS-2026-10-03-004 | 公开时间选择与播放记录旧ID兼容 | 已随2faadc64交付；[生产验收](reports/2026-10-06-track-credit-resolution-acceptance.md) |

## 分支和历史入口

10-25既有清理记录为仅main、一个实际工作树、8个本地源码恢复引用和2个历史stash。独立移动端候选555195c2仍待按当前main提取；历史未采用候选不整体合入。本轮文档整理复用当前目录，不创建新分支或工作树。

恢复引用、原SHA与旧运行证据的可恢复边界见[历史分支处置](archive/06-productization-closeout/2026-10-25-development-status-history.md#当前研发与分支处置)、[10-20清理](reports/2026-10-20-development-branch-worktree-closeout.md)和[10-25混合分支归档](reports/2026-10-21-versus-release-cycle-repair-acceptance.md#2026-10-25混合研发分支归档清理)。

## 如何持续维护

开始工作先确认稳定ID、范围和唯一负责人。状态变化只更新对应行、最后核验日期和证据链接；完整经过写报告，规则写reference，未完成路线写plans，完成或取代的方案归档。本表是当前状态、优先级、下一步与最后核验日期的唯一来源；问题台账保存身份、复现与解决依据，文档地图只导航。

文档改动执行文档审计和差异检查；具体开发与分支规则见[交付约定](reference/development-delivery-workflow.md)，验证范围见[验证规则](reference/fullstack-verification.md)。[历史检查点和维护记录](archive/06-productization-closeout/2026-10-25-development-status-history.md)不作为当前待办。
