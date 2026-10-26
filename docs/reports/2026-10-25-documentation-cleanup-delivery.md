# 项目文档整理交付报告

日期：2026-10-25，最后核验：2026-10-26。事项：SS-2026-10-25-001。**P0–P5、四轮整理、验收补修、读者分工及使用说明与安装授权前提补修完成，LOCAL DOC VERIFIED**；整理基线509a88f3，本轮统一Git交付见[提交与推送](#统一提交与推送)。各阶段“未提交／未推送”保留原检查时点含义。

## 结果与范围

已纠正skipped和动态阈值说明，建立搜索与年度总结合同，精简文档地图、开发状态和问题台账，整理计划与设计生命周期，按主题索引报告，按月保存原变更历史。业务代码、配置值、原始数据、正式数据库和生产状态不变。

## 规则来源与承接

| 内容 | 当前依据 | 整理结果 |
| --- | --- | --- |
| skipped与有效计次 | [counting](../../backend/domains/playback/counting.py)、[统计规则](../reference/playback-stats-rules.md) | 数据格式说明不再维护另一套统计解释 |
| 搜索候选和context | [服务端路由](../../backend/api/music.py)、[变体注册表](../../backend/domains/music_search/variants.py)、[前端hooks](../../frontend/src/features/music/search/useMusicSearch.ts)、[输入控制](../../frontend/src/features/music/search/searchInputController.ts)、[候选API](../../frontend/src/features/music/search/api.ts) | 提炼为[搜索合同](../reference/music-search.md)，补修明确当前四套及L1兼容边界 |
| 年度内容、key和失效 | [服务](../../backend/services/yearly_review_service.py)、[generation](../../backend/services/yearly_review_generation.py)、[artifact](../../backend/domains/yearly_review/artifact_cache.py)及原统计/设计合同 | 提炼为[年度规则](../reference/yearly-review.md)；实际内容版本由versions定义，避免旧v16或模型默认值被误作服务版本 |
| 详情年榜 | 原设计的展示、API及维护合同 | 当前内容在[UI](../../frontend/UI_STYLE_GUIDE.md#详情年榜展示)和[发布读取](../reference/public-snapshot-read-contract.md#详情年榜附属投影)承接，原设计归档 |
| AI继承和配置 | [config](../../backend/core/config.py)、[V6合同](../reference/ai-agent-runtime-v6.md)及交付报告 | 旧V2/V3/V4的分支和memory默认值仅为历史 |
| 验证入口 | [验证范围](../reference/fullstack-verification.md)、[测试隔离](../reference/backend-test-isolation.md) | 去掉架构文档中的无日期数量，集中工具用途 |

原统计规则R1–R42及业务示例保留。历史实现数量与性能样本由原报告承接。两份环境示例与实际配置/Compose用途核对，未修改示例或默认值；生产手册保持当前备份和网关合同。AGENTS与CLAUDE保留必要红线和领域链接，本次补修仅同步当前搜索变体集合与兼容边界。

## 当前状态与已有修改保护

执行前已有开发状态总表的未提交更新，以及本会话规划和三处入口登记。完整恢复副本、初始diff和清单保存在 `/Users/benjaminlei/.codex/tmp/spotifystats-documentation-cleanup-20261025/`。原总表中的当前版本、交付和未完成边界在新总表继续保留，迁出的历史检查点和详细完成记录在[历史状态](../archive/06-productization-closeout/2026-10-25-development-status-history.md)；原台账全文在[历史台账](../archive/06-productization-closeout/2026-10-25-issue-register-history.md)。

独立待办仍包括四日期生产应用、移动端孤立点、手机弹层、OOM正常使用观察、门禁成本、PWA/OAuth、生产模型和私有入口、周备份实际调度、L1及Album身份证据。10-24报告的本地19与生产23分别保留；旧60,294派生FK不再冒充当前待清理数量。没有恢复历史资源矩阵或自动关闭观察。

## 文件迁移映射

旧路径按执行前记录保留；Markdown和资源引用随去向更新。

| 原路径 | 当前路径 |
| --- | --- |
| docs/plans/2026-10-09-music-detail-chart-performance-plan.md | [2026-10-09-music-detail-chart-performance-plan.md](../archive/06-productization-closeout/2026-10-09-music-detail-chart-performance-plan.md) |
| docs/plans/2026-10-17-oom-resource-closeout-plan.md | [2026-10-17-oom-resource-closeout-plan.md](../archive/06-productization-closeout/2026-10-17-oom-resource-closeout-plan.md) |
| docs/plans/2026-10-25-documentation-cleanup-and-update-plan.md | [2026-10-25-documentation-cleanup-and-update-plan.md](../archive/06-productization-closeout/2026-10-25-documentation-cleanup-and-update-plan.md) |
| docs/designs/2026-07-04-genre-review-settings-design.md | [2026-07-04-genre-review-settings-design.md](../archive/06-productization-closeout/2026-07-04-genre-review-settings-design.md) |
| docs/designs/2026-08-12-yearly-review-v2-content-data-contract.md | [2026-08-12-yearly-review-v2-content-data-contract.md](../archive/06-productization-closeout/2026-08-12-yearly-review-v2-design-and-plan.md#年度总结-v2-内容与数据契约设计) |
| docs/designs/2026-08-23-yearly-artifact-key-invalidation-contract.md | [2026-08-23-yearly-artifact-key-invalidation-contract.md](../archive/06-productization-closeout/2026-08-23-yearly-artifact-key-invalidation-contract.md) |
| docs/designs/2026-08-25-music-detail-year-end-history.md | [2026-08-25-music-detail-year-end-history.md](../archive/06-productization-closeout/2026-08-25-music-detail-year-end-history.md) |
| docs/designs/2026-08-31-ai-agent-quality-v3.md | [2026-08-31-ai-agent-quality-v3.md](../archive/06-productization-closeout/2026-08-31-ai-agent-v2-v4-design.md#ai-agent-quality-v3-设计与实施说明) |
| docs/designs/2026-08-31-ai-agent-quality-v4.md | [2026-08-31-ai-agent-quality-v4.md](../archive/06-productization-closeout/2026-08-31-ai-agent-v2-v4-design.md#ai-agent-quality-v4-完整优化方案与实施说明) |
| docs/designs/2026-08-31-ai-agent-runtime-v2.md | [2026-08-31-ai-agent-runtime-v2.md](../archive/06-productization-closeout/2026-08-31-ai-agent-v2-v4-design.md#ai-agent-runtime-v2-架构与运行契约) |
| docs/designs/2026-10-17-detail-resource-architecture-decision.md | [2026-10-17-detail-resource-architecture-decision.md](../archive/06-productization-closeout/2026-10-17-detail-resource-architecture-decision.md) |
| docs/designs/mobile-web-m0-prototype/README.md | [README.md](../archive/06-productization-closeout/mobile-web-m0-prototype/README.md) |
| docs/designs/mobile-web-m0-prototype/index.html | [index.html](../archive/06-productization-closeout/mobile-web-m0-prototype/index.html) |
| docs/designs/mobile-web-m0-prototype/prototype.css | [prototype.css](../archive/06-productization-closeout/mobile-web-m0-prototype/prototype.css) |
| docs/designs/mobile-web-m0-prototype/prototype.js | [prototype.js](../archive/06-productization-closeout/mobile-web-m0-prototype/prototype.js) |
| frontend/design-demos/a-dark-immersive.html | [a-dark-immersive.html](../archive/02-react-productization/design-demos/a-dark-immersive.html) |
| frontend/design-demos/b-editorial.html | [b-editorial.html](../archive/02-react-productization/design-demos/b-editorial.html) |
| frontend/design-demos/billboard-a-dark.html | [billboard-a-dark.html](../archive/02-react-productization/design-demos/billboard-a-dark.html) |
| frontend/design-demos/billboard-b-editorial.html | [billboard-b-editorial.html](../archive/02-react-productization/design-demos/billboard-b-editorial.html) |
| frontend/design-demos/billboard-c-calm.html | [billboard-c-calm.html](../archive/02-react-productization/design-demos/billboard-c-calm.html) |
| frontend/design-demos/billboard-d-glass.html | [billboard-d-glass.html](../archive/02-react-productization/design-demos/billboard-d-glass.html) |
| frontend/design-demos/billboard-e-brutalist.html | [billboard-e-brutalist.html](../archive/02-react-productization/design-demos/billboard-e-brutalist.html) |
| frontend/design-demos/c-calm-tech.html | [c-calm-tech.html](../archive/02-react-productization/design-demos/c-calm-tech.html) |
| frontend/design-demos/d-liquid-glass.html | [d-liquid-glass.html](../archive/02-react-productization/design-demos/d-liquid-glass.html) |
| frontend/design-demos/e-neo-brutalist.html | [e-neo-brutalist.html](../archive/02-react-productization/design-demos/e-neo-brutalist.html) |
| frontend/design-demos/final-b-plus-d.html | [final-b-plus-d.html](../archive/02-react-productization/design-demos/final-b-plus-d.html) |
| frontend/design-demos/index.html | [index.html](../archive/02-react-productization/design-demos/index.html) |
| docs/reports/2026-06-19-fullstack-verification-performance.md | [2026-06-19-fullstack-verification-performance.md](../archive/03-quality-gate/2026-06-19-fullstack-verification-performance.md) |
| docs/assets/dashboard.png | [dashboard.png](../archive/02-react-productization/dashboard.png) |

另保存[10-19完整历史决定](../archive/06-productization-closeout/2026-10-19-performance-scope-and-memory-decision.md)，原计划缩为当前观察入口。五份保留计划分别明确外部验收、未完成成本目标、暂缓探索、正常观察和剩余日期/身份治理，不把已交付工程继续列为正在开发。

## 素材与删除决定

- 删除原6行发行周期规划指引：没有仓库内消费者，完整规划与主要入口已直接指向归档。
- 旧Dashboard截图归档到React产品化阶段，保留历史页面形态；没有因未引用就删除唯一视觉证据。
- 12份HTML方向稿整体归档，探索方案各有独有视觉内容，保留全部方向及最终稿。
- 移动原型的HTML、CSS、JS整体归档；本机data封面引用换成自带SVG占位，favicon路径随目录修正。静态样例不作为当前事实。
- 5个月的原CHANGELOG内容按原时点保存，9–10月当前入口只留主要交付。初轮保留原报告路径；第三轮才按下方清单合并，失败与版本证据仍保留。

## 初轮验证与仓库状态（历史结果）

| 验证 | 结果 |
| --- | --- |
| 含归档Markdown审计 | PASS，320份；其中308份为本轮正式文档集合，另12份是原有ignored运行记录 |
| 差异与新增文件空白 | PASS；同时检查未跟踪的新文档和迁移文件 |
| 本地Markdown标题锚点 | PASS，未发现缺失目标标题 |
| 报告索引 | 159份非索引报告全部覆盖，含原11份漏列及本次报告 |
| 归档索引 | 100份非README的Markdown全部可由归档索引到达，阶段与原型README同时可达 |
| 既有状态和ID | 原状态52个、原台账40个稳定ID有当前或历史承接；10条非文档待办在链接归一化后逐行保持 |
| 变更历史 | 206个原条目在Markdown链接目标归一化后逐条原文保持，分为6–10月五份历史 |
| 工作约定 | 初轮整理未改；补修同步四套发布集合与L1兼容边界，AGENTS与CLAUDE仍完全一致 |
| 静态演示 | 12份HTML均HTTP200且有正文，页面脚本错误0、本地资源失败0；远程字体和图片用占位响应，不把远程可用性计作通过 |
| 移动原型 | 六画板可切换；360宽度与夜间主题状态核对，当前图片全部可读、字体加载完成；原型HTML/CSS/JS和favicon路径可用 |

浏览器中发现归档后Inter字体相对路径偏移，已修正并复验。原型仍复用前端安装依赖中的Inter字体，说明中注明；个人封面已改自带占位。截图与一次性验证材料位于ignored `output/playwright/documentation-cleanup/`，浏览器session与仅开放归档/字体的loopback临时服务均已关闭。

本轮只验证文档和迁移的静态原型，没有运行应用全量、Phase 5、默认完整全栈、真实数据库或生产验收。当前没有Git提交、推送或发布。


## 阶段收尾

P0保护执行前工作区；P1纠正规则并核对配置拥有者；P2精简入口并提炼两份当前合同；P3完成8份原计划和9份原设计的逐项处置；P4补齐报告/归档索引并分月承接历史；P5完成候选处置、静态浏览、内容保全和文档验收。执行规划已[归档](../archive/06-productization-closeout/2026-10-25-documentation-cleanup-and-update-plan.md)，事项SS-2026-10-25-001在总表和台账标为本地文档完成。

## 二轮验收补修

2026-10-25独立验收确认结构、导航和内容保全通过，但发现两项内容问题，因此当时结论为部分通过。初轮文档审计只能证明路径存在，未能发现这两项语义错误；初轮的完整内容验收判断过早。

1. 搜索合同将当前发布集合误写为L1/L2/L3六套。依据[实际注册表](../../backend/domains/music_search/variants.py)及[导入合同](../reference/data-import-and-health.md)，已修正为L2/L3 × 动态/固定阈值四套，并明确L1仅保留兼容或陈旧证据，不属于当前必须发布集合。AGENTS与CLAUDE中的两处旧说明同步修正，保护原有冷建副本、ready复用和GET只读边界。
2. 搜索合同的API源码链接误指向搜索历史接口，已改到[真正的音乐路由](../../backend/api/music.py)，其中定义 `/music` 前缀及 `/search`、`/search/context` 两个GET。

补修后通过静态AST核对注册表四个组合和实际路由定义，确认搜索合同及两份工作约定没有旧六套表述，AGENTS与CLAUDE逐字节一致。含归档320份Markdown审计和差异检查通过；新增搜索合同与报告同时检查空白。两项已知验收问题已关闭，文档整理结论更新为补修后本地验收通过。

本次仅修改说明、工作约定及对应交付状态，不改业务实现、配置或数据；原迁移、内容保全和静态原型结果继续复用，不重跑应用或生产验收。未提交或推送。


## 第三轮同日同题合并

2026-10-26完成。上轮主要精简入口，独立报告仍有159份。本轮把72份同日同题材料合成19份，直接删除53个原文件，没有再复制到归档：报告减少46份，历史设计与计划减少7份。独立主题继续单独保存。

合并文档先给主题结论和阅读顺序，原阶段放入章节，保留原文件名供检索。不同源码版本、数据样本、撤回或无效窗口、失败及局部通过保留原范围；旧文件链接和深链更新到对应章节。没有用统一的最终Pass覆盖早期Partial或FAIL。

| 同日主题 | 原文件数 | 合并后 |
| --- | ---: | --- |
| 2026-08-13 音乐档案后端与多端交付 | 5 | [1份主题文档](2026-08-13-account-archive-delivery.md) |
| 2026-08-23 增量导入阶段与最终验收 | 7 | [1份主题文档](2026-08-23-incremental-import-delivery.md) |
| 2026-08-31 AI Agent V3至V5实施验收 | 3 | [1份主题文档](2026-08-31-ai-agent-v3-v5-acceptance.md) |
| 2026-09-20 Billboard共享构建与配置失配修复 | 2 | [1份主题文档](2026-09-20-billboard-build-delivery.md) |
| 2026-09-20 搜索共享构建与真实增量验收 | 3 | [1份主题文档](2026-09-20-search-build-and-delta-delivery.md) |
| 2026-09-20 阶段7至7D性能验收检查点 | 4 | [1份主题文档](2026-09-20-stage7-performance-checkpoints.md) |
| 2026-10-03 专辑证据审阅集成与生产交付 | 4 | [1份主题文档](2026-10-03-album-metadata-delivery.md) |
| 2026-10-07 日期精度与详情空统计本地验收 | 3 | [1份主题文档](2026-10-07-release-date-and-empty-stats-acceptance.md) |
| 2026-10-08 日期精度发布准备与生产验收 | 2 | [1份主题文档](2026-10-08-release-date-production-acceptance.md) |
| 2026-10-13 原生回收候选审阅与发布准备 | 3 | [1份主题文档](2026-10-13-native-trim-review-and-preparation.md) |
| 2026-10-14 维护完成回收门禁与生产交付 | 3 | [1份主题文档](2026-10-14-native-trim-maintenance-delivery.md) |
| 2026-10-15 OOM投影与生命周期研究汇总 | 15 | [1份主题文档](2026-10-15-oom-projections-and-lifetimes.md) |
| 2026-10-16 OOM驻留与arena归因研究 | 4 | [1份主题文档](2026-10-16-oom-residency-and-arena-research.md) |
| 2026-10-24 发行周期剩余项调查与五项交付 | 2 | [1份主题文档](2026-10-24-release-cycle-review-and-delivery.md) |
| 2026-08-05 移动网页设计冻结与实施规划 | 2 | [1份主题文档](../archive/06-productization-closeout/2026-08-05-mobile-web-design-and-plan.md) |
| 2026-08-12 年度总结V2内容设计与实施规划 | 2 | [1份主题文档](../archive/06-productization-closeout/2026-08-12-yearly-review-v2-design-and-plan.md) |
| 2026-08-16 音乐查找方向与性能修复规划 | 3 | [1份主题文档](../archive/06-productization-closeout/2026-08-16-music-search-design-and-remediation.md) |
| 2026-08-31 AI Agent V2至V4历史设计 | 3 | [1份主题文档](../archive/06-productization-closeout/2026-08-31-ai-agent-v2-v4-design.md) |
| 2026-08-31 L2与L3身份及专辑归属历史规划 | 2 | [1份主题文档](../archive/06-productization-closeout/2026-08-31-l2-l3-identity-and-attribution-plan.md) |

本轮移除16行重复日期和共同问题链元数据，并将音乐档案四处已完成的后续清单收束到实际交付章节。技术决策、测试计数、统计表格、原始版本及失败数据大多属于独有证据，继续保留在章节中；本轮主要减少文件碎片，不声称全文字数同比例下降。

整理前的完整工作区文档、初始差异和状态保存在 `/Users/benjaminlei/.codex/tmp/spotifystats-theme-consolidation-20261025/`；逐源章节及深链映射和验证材料在ignored `output/documentation-consolidation-20261025/`。正文每章保留原文件名，正式仓库不增加原文副本或空壳重定向。

本轮验收通过：正式Markdown从308份降至255份，非索引报告从159份降至113份；93份归档正文及113份报告均被索引覆盖，全部正式文档可从README到达。1030个原章节锚点已映射，2411个原文段落逐项核对，除上述明确精简项外未发现内容丢失，本地链接及标题锚点无缺失。含归档文档审计通过267份（含12份既有ignored运行记录），差异空白检查通过，AGENTS与CLAUDE完全一致。

后续按[证据与清理规则](../reference/development-delivery-workflow.md#证据与清理)优先追加主题文档，不为每次检查另建报告。前两轮的320份文档、159份报告等计数保留为历史结果。业务代码、正式数据、生产状态和独立待办不变；本轮只进行文档验证，未提交或推送。


## 第四轮正文精简与维护去重

2026-10-26完成初次整理。第三轮后的255份正式Markdown、113份报告为本轮基线。本轮按用户确认的五项优化执行，不另建规划或交付报告；后续独立验收及补修见[针对性复验](#验收补修与针对性复验)。

- 当前状态、优先级、下一步和最后核验日期统一由开发总表维护。台账10项改为问题身份、现象与复现／判断依据，移除重复进度及自链接；两处维护规则同步。
- 28份旧模板计划精简为历史实施提纲：删去已过时的Python／TypeScript／Shell实现和测试草稿、重复运行命令、红绿测试与提交编排；保留设计决定、任务目标、SQL结构、JSON接口、公式、图示、语义要求及实际验收记录。不会把旧Expected改成实际通过，也不把旧任务重新登记为当前待办。
- 六组报告14份合为6份，七组历史设计／计划14份合为7份，净减少15个文件。七份设计的478个正文段落保留；14份报告的360个正文段落核对，仅将专辑排名审阅中的一处重复生产摘要收束到同文完整生产章节。
- 修正报告索引中内存交付与专辑成绩的归类，每个合并文件只列一次；统计规则增加按问题查找的目录，R1–R42及其余正文逐字保持。
- 常规文档审计加入章节锚点和报告／归档索引覆盖检查，支持同文链接、重名标题、中文编码路径、显式锚点、Setext标题和代码围栏。8项定向回归在Python3.9下通过，Ruff检查通过；现有CI文档步骤接入同一回归，尚未提交或触发远端CI。

| 主题 | 原文件数 | 合并后 |
| --- | ---: | --- |
| 私有云与双运行面部署交付 | 2 | [1份主题文档](2026-08-13-private-cloud-and-deployment-delivery.md) |
| 音乐查找基线与完整交付 | 2 | [1份主题文档](2026-08-16-music-search-baseline-and-delivery.md) |
| Records读取与共享构建验收 | 2 | [1份主题文档](2026-09-20-records-read-and-build-delivery.md) |
| 导入事故复盘与治理修复验收 | 4 | [1份主题文档](2026-09-21-import-incident-and-remediation.md) |
| AI V6固定基线与最终本地验收 | 2 | [1份主题文档](2026-09-22-ai-agent-v6-baseline-and-acceptance.md) |
| 专辑排名取消修复整合与生产交付 | 2 | [1份主题文档](2026-10-13-album-rank-cancellation-delivery.md) |
| 旧账号中心设计与实施提纲 | 2 | [1份主题文档](../archive/01-streamlit-mvp/features/account-center/2026-05-30-account-center-design-and-plan.md) |
| 旧发行周期设计与实施提纲 | 2 | [1份主题文档](../archive/01-streamlit-mvp/features/release-cycle/2026-05-22-release-cycle-design-and-plan.md) |
| 旧年度回顾设计与实施提纲 | 2 | [1份主题文档](../archive/01-streamlit-mvp/features/yearly-review/2026-05-29-yearly-review-design-and-plan.md) |
| Billboard年榜设计与实施记录 | 2 | [1份主题文档](../archive/03-quality-gate/2026-06-26-billboard-year-end-design-and-plan.md) |
| 早期AI可观测编排设计与实施提纲 | 2 | [1份主题文档](../archive/04-ai-agent-harness/2026-06-28-ai-observable-agent-design-and-plan.md) |
| 早期AI分析框架设计与实施提纲 | 2 | [1份主题文档](../archive/04-ai-agent-harness/2026-06-29-ai-analytical-harness-design-and-plan.md) |
| AI项目上下文设计与实施提纲 | 2 | [1份主题文档](../archive/04-ai-agent-harness/2026-06-29-ai-project-context-design-and-plan.md) |

本轮规模：正式Markdown **255→240**，独立报告 **113→105**，归档正文 **93→86**；`docs/`总行数 **94452→62846**，归档 **70951→39214**。行数包含空行与代码，不等同于自然语言字数。

含归档审计通过252份（240份正式文档及12份既有ignored运行记录），791个原标题映射、所有正式文档的README可达性、索引与章节链接通过。原统计正文、总表非本事项的业务状态行及本轮无关的仓库文档保持；Git差异和新增文件空白检查通过。

本轮修改文档、审计脚本、8项定向回归与CI文档步骤；没有运行应用全量、数据库或生产验收。正式数据、应用实现、生产状态和独立业务待办不变，未提交或推送。整理前的完整工作区文档及脚本副本在 `/Users/benjaminlei/.codex/tmp/spotifystats-documentation-refinement-20261026/`；合并、精简清单和核验材料在ignored `output/documentation-refinement-20261026/`，正式仓库不另存全文副本。

## 验收补修与针对性复验

2026-10-26独立验收确认文件去向、索引和本地链接通过，但内容精简仅部分通过：通用过滤删除了有业务含义的历史验收条件，删代码后遗留悬空引导语；一处被视为重复的生产摘要含唯一归档计数；另发现既有外链紧贴中文导致错误解析。第四轮初次整理对“语义要求均保留”的判断过早，链接审计和工具回归通过不代表这项内容判断通过。

按用户明确指令完成三项补修：

1. 对28份旧实施提纲复核同类删减，补回17份中的36条实质历史验收要求，并保留7条可独立表达的实施约束。恢复跨年季节不误报年份冲突的条件及 `2025-12-01..2026-02-28` 样例，补回2026部分年度的 `截至 2026-06-23` 与2025完整年度措辞边界；最终可见质量门禁、修复字符串列表和图表文案改成完整说明。清理悬空的 Add／with／After 等代码引导语，不恢复大段实现草稿，不把历史要求改写为实际通过。
2. 在专辑排名交付检查点补回“三份私密清单及393个证据文件已校验存入独立生产归档”。原生产交付章节保持不变，其他重复摘要继续通过章节链接承接。
3. 将旧性能报告中的公开地址改为显式Markdown链接 `[公开入口](https://stats.benjaminlei.site)`，独立Markdown解析确认URL精确止于域名，未将后续中文并入网址；这是格式与解析复验，不代表重新验收生产服务。

针对性复验通过：36条恢复要求逐条核对；28份提纲的Markdown结构复查未发现悬空引导语或空的叶级标题；归档计数与原记录一致；791个原标题映射、240份正式文档的链接及报告／归档索引覆盖通过。七组合并材料中的历史设计正文及正式生产交付正文保持，原统计规则未改。含归档审计252份、8项审计工具回归及差异空白检查通过。三项验收问题关闭，文档整理结论更新为补修后本地通过；不把此前的部分通过改写为初次即通过。

本次只修改文档，正式文档数量保持240份，未提交或推送。补修前相关33份文档副本在 `/Users/benjaminlei/.codex/tmp/spotifystats-doc-acceptance-fixes-20261026/`；逐项恢复与清理清单、语义断言和独立解析结果在ignored `output/documentation-acceptance-fixes-20261026/`。


## 读者分工与命名更新

2026-10-26完成并验收。按使用者、维护者和Agent三类入口组织文档，再按操作、开发、运维、规范与证据的用途区分内容。沿用本事项与报告，不另建执行规划或验收报告。

| 文档职责 | 本轮结果 |
| --- | --- |
| GitHub项目首页 | README重写为产品介绍、功能、截图、开始使用、隐私与帮助；开发测试、技术栈、目录、内部版本和请求实现细节迁出。只保留日常使用所需的启动命令。 |
| 普通使用 | 新增[使用指南](../user-guide.md)，承接安装、播放历史上传、账号资料目录导入、日常更新、AI配置、跨设备查看和常见问题。 |
| 开发维护 | 新增[开发指南](../../CONTRIBUTING.md)与[后端README](../../backend/README.md)，整合[前端README](../../frontend/README.md)。开发者从人类开发文档查架构，Agent局部文件只保留执行约定与选读入口。 |
| 运维与技术参考 | 生产手册增加操作导航；数据说明明确为技术参考；当前规则标明共用读者，入口不再按旧实施阶段组织。技术约束继续只维护一份。 |
| 台账与路线 | 台账合入原issues入口；五份滚动路线和流派规则去掉日期文件名前缀。滚动路线区分原记录日期、修订日期与历史规划基线，当前状态仍以总表为准。 |
| 变化与历史 | CHANGELOG改为使用者可感知变化；工程版本、计数及分支收尾由现有报告和月度历史承接。流派规则两份历史数据快照转入对应既有报告，当前消费规则继续在参考文档维护。 |

### 长期路径映射

| 原路径 | 当前入口 |
| --- | --- |
| docs/issues/2026-08-27-issue-register.md | [README.md](../issues/README.md) |
| docs/reference/2026-07-04-artist-genre-taxonomy.md | [artist-genre-taxonomy.md](../reference/artist-genre-taxonomy.md) |
| docs/plans/2026-08-06-appification-pwa-capacitor-plan.md | [appification-and-mobile-distribution.md](../plans/appification-and-mobile-distribution.md) |
| docs/plans/2026-08-24-fullstack-gate-duration-optimization-plan.md | [fullstack-verification-performance.md](../plans/fullstack-verification-performance.md) |
| docs/plans/2026-09-23-multi-source-music-metadata-roadmap.md | [multi-source-music-metadata.md](../plans/multi-source-music-metadata.md) |
| docs/plans/2026-10-19-performance-scope-and-memory-closeout.md | [performance-and-memory-closeout.md](../plans/performance-and-memory-closeout.md) |
| docs/plans/2026-10-24-release-cycle-remaining24-resolution.md | [release-cycle-data-governance.md](../plans/release-cycle-data-governance.md) |

日期保留在冻结方案、验收／发布报告和归档文件名中；有实际合同含义的V6版本标识继续保留。没有为“人类版”和“Agent版”复制一套统计或缓存规则。新增3份有独立用途的入口文档，合并1份中转台账，正式Markdown由240份变为242份。

### 本轮验收

| 检查项 | 结果 |
| --- | --- |
| 读者与表述 | PASS；首页无开发测试、架构目录、内部版本、Query／revision等实现说明；使用指南围绕操作结果，维护与运维文档保留必要技术细节，Agent入口只约束执行并链接共同规范。 |
| 操作说明 | PASS（源码核对）；启动参数和端口对照start_daily，上传与账号目录导入对照Settings工作台，LLM配置名称和用途对照配置组件。本轮没有新机安装、启动应用或实际导入数据。 |
| 命名 | PASS；当前reference／plans／issues无日期前缀文件，冻结报告和归档文件保留日期，台账不再有独立中转页。 |
| 内容承接 | PASS；后端架构、根Agent硬约束、前端关键约束、47行计划表格、统计规则正文及数据／运维参考保持；16921个历史证据段落在路径归一化后保留，两份流派历史快照全文承接。 |
| 导航与链接 | PASS；210个旧入口标题有承接，正式242份文档均可从首页到达，本地链接及图片引用无缺失；含归档文档审计254份通过，其中12份为既有ignored运行记录。 |
| 差异与范围 | PASS；Git差异和新增／迁移文件空白检查通过，AGENTS与CLAUDE完全一致；本轮未改变既有非Markdown差异、业务实现或正式数据。 |

验收范围为文档定位、内容迁移、命名和链接，不将静态核对表述为新安装、应用全栈或生产验收。独立Markdown解析结果、逐项内容对照与旧标题映射在ignored `output/documentation-audience-20261026/`。本轮前240份完整工作区文档、初始差异和状态在 `/Users/benjaminlei/.codex/tmp/spotifystats-documentation-audience-20261026/`，保护已有未提交工作；未提交、推送或发布。


## 使用指南与Agent提交入口补修

2026-10-26独立复查确认首页定位、文件命名、核心Agent约束和本地链接通过，但使用指南仍有两项操作缺口：推荐日常入口4173，授权默认回调却仍为5173；更新只写构建命令，未交代依赖变更与停止旧入口。Agent提交信息规范已在人类开发指南维护，但提交前必读链未明确指向该节。原操作说明的源码核对未覆盖这些条件，本节记录补修后的结论。

按用户指令完成三项修复：

1. 使用指南补齐Spotify应用登记、Client ID／Secret、显式 `.env` 回调和重启步骤。日常本机入口登记并配置 `http://127.0.0.1:4173/api/spotify/auth/callback`；自定义端口／远程入口按实际地址同步配置。本机使用IP而非localhost，远程入口使用HTTPS，依据[Spotify官方回调规则](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)。只更新说明，没有修改程序默认配置、个人 `.env` 或执行真实授权。
2. 更新步骤改为停止自己启动的旧入口、保留个人资料与配置、按文件变化更新Python／前端依赖、构建并启动。明确 `--build` 不安装依赖，`--check` 不关闭已有服务；相应FAQ链接到完整步骤。
3. 根AGENTS／CLAUDE同步明确：只有用户要求提交时，先阅读并遵循[协作与提交规范](../../CONTRIBUTING.md#协作与提交)。中文Conventional Commits与复杂正文要求继续只在开发指南维护，其他Agent约束保持。

针对性复验通过：

| 复验 | 结果与边界 |
| --- | --- |
| 回调与配置 | 从真实配置getter、授权URL构造函数和回调返回表达式提取纯逻辑，验证文档URI覆盖旧默认值、进入授权请求，并返回日常入口的 `/settings?spotify_connected=true`；前端preview的 `/api` 代理与后端路径匹配。未导入应用服务、读取个人 `.env` 或操作数据库。 |
| 更新与命令 | 模拟日常脚本的 `--build --check`，确认只调用 `npm run build`，没有安装依赖或启动进程；指南顺序覆盖停止、按需安装与构建，7个bash命令块通过语法检查。没有实际执行安装或构建。 |
| Agent提交入口 | 提交前必读链接及目标章节有效；Conventional Commits、中文摘要和复杂正文规范可达；AGENTS与CLAUDE完全一致，除该入口外的原约束保持。 |
| 文档与范围 | 含归档254份审计通过；242份正式文档均可从首页到达，本地链接和7个图片引用无缺失；差异与本轮文档空白检查通过，已有非Markdown差异保持。 |

三项问题完成补修并通过上述针对性复验；不将纯逻辑和模拟验证描述为真实Spotify授权、新机安装、应用全栈或生产验收。正式文档数量保持242份，未提交或推送。补修前六份相关文档与初始差异保存在 `/Users/benjaminlei/.codex/tmp/spotifystats-documentation-usage-fixes-20261026/`；纯逻辑、命令语法及独立链接检查结果在ignored `output/documentation-usage-fixes-20261026/`。

## 安装版本依赖更新与Spotify授权前提补修

2026-10-26再次独立验收发现，上一节验证覆盖了命令顺序、回调与Agent入口，但没有覆盖Node.js次版本约束、Python分拆依赖清单及Spotify平台访问条件。按用户指令修复三项遗漏，并同步[使用指南](../user-guide.md)、[开发指南](../../CONTRIBUTING.md)、总表和问题台账；继续复用本报告，不新增独立验收文档。

1. 安装环境明确推荐Node.js 22.x，最低22.13.0，建议使用该系列最新维护版本。该最低版本依据当前[锁定依赖](../../frontend/package-lock.json)的全部Node版本约束，而非只看Vite；使用指南和开发指南保持一致。
2. Python更新条件涵盖根 `requirements.txt` 及其引用的任意子清单，列明当前四份 `requirements-*.txt`；统一执行根清单安装。不确定变更范围时也执行依赖安装，并在更新前核对环境版本。保留停止旧入口、安装依赖、构建并启动的顺序。
3. Spotify连接补充开发模式应用所有者的有效Premium订阅要求；非所有者账号先在Users Management通过Add new user加入允许名单，再执行授权。说明未获准账号可能完成登录，但API请求返回403，并增加FAQ入口。这些条件仅属于Spotify在线服务，不作为本地播放历史导入与统计的前提。平台依据为[Spotify官方开发模式与用户访问规则](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)，核对日期为2026-10-26；原4173回调与重启步骤保留。

针对性复验：

| 项目 | 结果与边界 |
| --- | --- |
| 安装版本 | 读取当前锁定文件中442项Node版本约束，使用npm自带semver核对：22.0.0有45项不兼容，22.12.0有16项不兼容，22.13.0全部满足；两份指南版本表述一致。此结果验证依赖声明，不代表已在这些Node版本上实际安装或构建。 |
| 依赖更新 | 从根清单递归解析四份子清单，确认全部包含在指南的更新条件中；停止／Python安装／前端安装／构建顺序正确，7个bash块通过语法检查。没有实际重装依赖。 |
| 授权前提 | 对照上述官方规则核对Premium、实际登录账号、允许名单设置入口和403行为；确认既有4173回调、显式配置与重启步骤保留。没有使用真实账号授权、访问个人配置或操作数据库。 |
| 入口与链接 | Agent提交规范入口可达且根AGENTS／CLAUDE完全一致；含归档文档审计、独立Markdown章节链接与可达性检查、Git差异检查通过。正式文档保持242份，无新增失效链接。 |

本轮五份文档变更，已有非Markdown差异保持。修复前副本与初始差异保存于 `/Users/benjaminlei/.codex/tmp/spotifystats-documentation-prerequisites-20261026/`，针对性检查结果位于ignored `output/documentation-prerequisites-20261026/`。结论为本地文档复验通过；未提交、推送或部署。

## 统一提交与推送

2026-10-26用户授权统一提交并推送本会话的文档整理和修复。交付分支为 `codex/documentation-cleanup-20261026`，整理基线为 `509a88f3`；本节随统一提交保存，具体提交SHA和远端同步结果以该分支Git记录为准。

提交范围包括项目／模块文档、当前规则与历史证据的整理合并、稳定文件名与入链修复、使用指南和Agent提交入口补修，以及文档审计脚本、8项回归和对应CI检查步骤。HTML方向稿、移动原型及旧截图的归档迁移属于同一范围。已逐项核对310个新增／修改／删除路径；不包含业务实现、个人配置、密钥、数据库、运行数据或ignored验证产物。原开发状态更新随本轮结构整理承接，业务事项和环境边界保持。

提交前复用独立验收的安装／授权结论，并执行8项文档审计回归、含归档文档审计、独立Markdown章节与可达性检查及Git差异检查；项目pre-commit hooks由提交过程执行。文档数量保持242份，安装依赖、真实OAuth、应用全栈与生产检查没有因Git交付重新执行。

当前生产工作流只对main推送触发，但其忽略列表未覆盖本次迁移的HTML／图片及审计脚本；因此本次仅推送上述交付分支，不合并main、不执行生产部署。main后续整合与发布另行处理；不把推送成功描述为远端CI或生产验收通过。
