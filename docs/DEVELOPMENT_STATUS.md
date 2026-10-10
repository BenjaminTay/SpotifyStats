# SpotifyStats 开发状态总表

> 最后核验：2026-10-10（五前端文件候选及静态资源代理压缩修复本地验证；生产仍d838，原FIRST90仅30/90通过）
> 当前进展：对决`SS-2026-10-08-002`保持S0–S5完成；详情`SS-2026-10-09-001`保持OPEN/Partial。已证实公开静态资源因Caddy的Via与Nginx默认gzip_proxied off交互而未压缩；仅/assets/三配置修复及line+leaf候选完成本地验证，尚未提交/发布。整体OOM未关闭。
> 当前生产：`d838814d5790ad9884fa9c30020801fdcb1044bc`；三OCI完整SHA/healthy，schema90、search4/rank4/detail4/BB48 ready，调用链/host helper精确，启动维护结束。详情116 API和三个完整只读窗口通过，性能30/90达标，混合RSS峰2299.176/末1928.613MiB、OOM增量0。c587对决公开FIRST14/28最大1.669秒及详情39/51历史证据保持；私有入口保持现状。
> 历史日期专项已发布业务代码：`76a4968`；CI attempt2质量/三模式/镜像/部署success，attempt1传输SSH reset保留。
> 历史日期专项生产核验：76a4968、schema89、dual三healthy（12:54）；五年精确年度、两端30次API、两端双视口与最终61表事实守恒通过。连接已恢复，OOM及详情访问后内存增长未代码修复。
> 本文件是开发状态与下一步工作的统一入口；详细规则、方案和原始验收证据继续在各自文档维护。

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
| DONE-09 | 普通备份降为每周、28 天有界轮转，保留导入/发布/恢复保护点 | 已实现；提交 `3e608f22` | [生产备份规则](../deploy/production/README.md)、提交记录 | 脚本已发布；已安装 timer 状态按运维证据另验 | 2026-10-02 |
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
| SS-2026-10-08-001 | 生产OOM与详情访问内存增长 | 内核确认global OOM终止uvicorn；连接恢复，浏览器检查后RSS再至约2.3GiB。受控backend重启、逐年有界维护已缓解，最终healthy；未代码修复 | P1：在副本复现详情/趋势冷路径及缓存驻留，限制重型任务叠加；验证冷/热访问资源，首个摘要17.98秒不算性能Pass | [生产验收与资源证据](reports/2026-10-08-release-date-production-delivery.md)、[台账](issues/2026-08-27-issue-register.md) | 2026-10-08 |
| SS-2026-10-08-002 | 榜单对决个人播放统计延迟 | COMPLETED / RELEASED；c587正式CI/NoDeploy/三模式/镜像/部署及独立runtime通过；原公开FIRST14/28全Pass（最大1.669秒）、420秒完整资源/守恒、96 API与三denial通过。人类明确仅公开HTTPS，S0–S5完成，历史失败保留 | P1：三库准备补修已验证，c587本地固定/hooks与清单九步通过；授权四文件清理/上传/push已完成，原公开入口已通过；私有SSH HTTP48仅为功能证据。本项完成；私有入口保持现状。详情独立首次已完成：39/90性能通过、116功能及完整读取守恒通过，详情与OOM仍开放 | [完整规划](archive/06-productization-closeout/2026-10-08-versus-personal-statistics-performance-plan.md)、[验收报告](reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)第21.9–21.13节、[台账](issues/2026-08-27-issue-register.md) | 2026-10-09 |
| SS-2026-10-09-001 | 音乐详情榜单成绩首次加载与附属计算 | OPEN/Partial；d838原FIRST90仅30/90通过，116 API与strict通过。2026-10-10本地五前端文件line+leaf候选已验证build/lint/128及一例图表交互；受控8按原门槛仅3/8满足，未提交/发布 | P1：审阅line+leaf与仅/assets/代理gzip联合候选；公开主脚本原658419B未压缩，集成本地527193B压缩至194317B，三配置24项通过，仍须正式发布后原FIRST90复验；回退与parallel8预载不推荐，旧20/两轮生产失败保留。高驻留另在副本，OOM不关闭 | [修复规划](plans/2026-10-09-music-detail-chart-performance-plan.md)、[分层验收](reports/2026-10-09-music-detail-chart-performance-acceptance.md)2026-10-10节 | 2026-10-10 |
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
