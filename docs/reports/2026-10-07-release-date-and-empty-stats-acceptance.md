# 日期精度与详情空统计本地验收

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。两项补丁和联合版本的本地证据集中记录。日期与空统计各自测试范围、提交SHA和7f7185cf联合完整门禁保持；10月7日未部署的边界不由后续成功覆盖。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [发行日期精度本地交付与验收](#发行日期精度本地交付与验收)
- [非榜单详情统计空值修复与本地验收](#非榜单详情统计空值修复与本地验收)
- [发行日期精度与详情空统计联合集成验收](#发行日期精度与详情空统计联合集成验收)

## 发行日期精度本地交付与验收

原记录：`2026-10-07-release-date-precision-acceptance.md`。

任务 `SS-2026-09-24-003`；2026-10-07；原交付基线 `c67d296a`、独立复验修复基线 `98dea609`；隔离分支 `codex/release-date-precision`。本报告的生产信息只来自只读核对和明确标记的历史副本，本次没有正式迁移、推送、合入 main 或部署。

### 真实发现与样本

- 主工作区开始时干净，HEAD `c67d296a`；其他 SpotifyStats 会话空闲。新工作树位于 `/Users/benjaminlei/.codex/worktrees/release-date-precision/202605-SpotifyStats`。生产 Backend 的 OCI revision 现场读取为 `2faadc64c73dadbcca0f05b6a53d1a0aebef4611`，三容器 healthy；未将历史 CI/业务验收重标为本次通过。
- 本地正式库只读 Online Backup 为 schema81：3,234 个 Album，89 年、1 月、3,144 完整日期形式；2,940 个项目，82 年、1 月、2,857 完整日期形式。所有日期均合法，但没有来源 precision；完整形式不等于真实 day 证据。
- 本机已存的生产来源副本为 2026-10-03 17:06 的历史 schema85 文件，同样为 89/1/3,144；不代表当前生产数量，不对历史文件执行迁移。
- 现有 Spotify Provider 有界读取 92 个 Album，全部成功：89 year、1 month、2 day；92 个原始字符串与旧值一致，没有来源冲突。年月样本是 A Jolly Christmas From Frank Sinatra（1957-09）；年份样本包括 The Emancipation of Mimi（2005）、时光, 漫步（2002）。未进行全库重新抓取。
- 真实旧路径问题：当前 pandas 混合格式批量转换会丢弃这 90 条粗日期；单值转换仍会把年/月补成首日。候选比较原来使用原文相等，Records 原来只检查完整字符串形式。未证实这批样本已经错误归并或出现错误的日级生产结果；风险复现、真实来源观测与合成测试分开记录。

### 实现与合同

统一规则见[发行日期证据与精度](../reference/release-date-precision.md)。schema89 新增 Album、项目 precision 和日期观测；旧字符串不改、precision 为 NULL，明确 legacy。来源精度只在合法一致、兼容范围内发布；冲突/倒退/缺失/异常保留旧值并审计，刷新重复不制造新语义结果。

比较区分 same、compatible、conflict、unknown：只有来源确认的相同 day 才是确定同日。跨 ID catalog alias 不能靠粗日期兼容成为强候选；既有目录、稳定身份、人工批准和 membership 合同保持。同 ID 的强证据来自稳定 Album 身份与完整目录，证据码不再把旧字符串称为日期强匹配。

写入覆盖专辑刷新、封面脚本（Track 简化 Album、名称搜索、批量 Album）、时长补取和发行周期简化写入；时长补取不再 REPLACE 整行、丢弃可靠旧证据。独立日期维护仅处理显式 ID 与日期，不重抓目录、不重建关系。

消费者覆盖专辑详情和版本列表、音乐档案年份/展示、兼容 Wrapped 年份、日期排序、自动归并规划、可信原版目录、L1/L2/L3 发行后范围过滤、Records 日级里程碑和发行周期/提前单曲/七日对齐。合法粗日期支持有依据的范围分析；日级计算要求已确认 day，未知时降级。当前桌面/手机日期只按可证明精度显示，图表发行日起点也要求 day；隐藏页签未恢复。

Analysis、Archive、治理、Billboard 进程与持久快照、年度 prepared/scoped artifact 和聚合 builder 纳入字段/规则 revision。拒绝观测不使语义缓存失效；公开 GET 不联网、补证、冷建、写库或排队。

### 副本前后对照

隔离 schema81→89 并安装 92 份来源日期：89 year、1 month、2 day、3,142 unknown；78 个非人工项目的精度得到唯一来源确认，人工项目未变。原始 Album/project 日期字符串全部保持，异常日期为 0；归并候选安装前后均为 0，没有新增批准或身份。

19 类受保护事实（18 表及有效署名投影）前后逐行摘要一致，包括 94,760 条播放、10,026 首歌曲、10,496 条原始署名及人工覆盖、艺人身份、release group、project membership 和 L3 人工覆盖。完整验收后再次核对来源副本与运行副本，守恒且 integrity check 为 ok。

真实旧 HEAD 与新规则归并候选为 0→0；83 个粗日期项目的原始播放资格行为 3,969→3,969，增删均为 0。这是资格行对照，不是逻辑事件总数。Records 发行日映射输入为 1,540→1：1,539 个无来源 day 证据的旧值退出日级计算；这不是最终里程碑条目数量。项目完整日期形式 2,857 个，而本次确认的项目 day 为 1 个。保守范围过滤不新增播放贡献，没有静默批准归并或身份。

这份本地旧库副本的 Taylor Swift 发行周期，旧 HEAD 与新规则均为 0 行（Album 艺人证据表为空），不能把旧集成断言失败单独归因于日期规则，也不能声称生产周期从可用变为不可用。缺证降级通过合成合同和真实 API 核验，实际生产日级受影响结果仍需新副本复核。

原始对照保存在工作树 ignored `output/release-date/`，真实 DB、来源响应、缓存、资产与截图不提交。

### 验证记录

- 日期及相关专项初轮 128 passed；后续边界、维护、revision/公开读取专项 96 passed，相关回归 72 passed，最终发行周期/API 缺证分支 46 passed。各组有重叠，不累加为总测试数。
- 前端全量：745 passed / 4 skipped；构建通过，保留既有大 chunk 提示。
- 默认完整门禁最终 run `20261007T072409.052401Z-cf41a9a21dae`：八个必需阶段同轮 PASS，22 分 55 秒；隔离 Online Backup、sidecar、克隆封面、18807/5187 端口，重型阶段使用共享锁。受控后端 3,390 passed / 2 skipped；真实副本 integration 186 passed / 1 skipped；API 157/157 安全 GET、参数边界及热点 22 样本 P95≤500ms 通过。
- 桌面/手机完整路由、七视口核心矩阵、有效交互、控件清单通过；Chromium、Firefox、Playwright WebKit 均 PASS。日期专项另在 1440×1000、390×844 验证 year、month、day、legacy 四个真实项目，共 8 个场景：1995、1957-09、1998-11-17、旧 B'Day 日期只显示 2006；无伪造首日、NaN 或横向溢出。截图人工检查后仅留 ignored 输出，模拟视口不等于物理手机验收。
- 前两轮完整门禁分别在旧 Taylor Swift 数量断言、未预备语言/导入健康治理快照处失败。集成合同改为独立检查来源日证据；显式隔离探针在 GET 前准备必要快照，公开读取保持只读。API 局部修复 run `20261007T071819.647830Z-f7aba043cadd` 仅记 Partial，最终上述默认完整 run 才记本地全栈 Pass。
- 文档审计、Ruff/格式、mypy、敏感信息 hooks、任务白名单及 staged diff 检查通过。schema/seed、旧库升级、刷新失败/幂等、合法闰年与非法/不一致输入、匹配/排序/归并候选/发行对齐、缓存失效均包含在专项和默认门禁中。
- 单元、真实副本、完整本地全栈、浏览器视口与生产验收各自分开；模拟手机视口不等于物理手机验收。

### 独立复验后的 legacy 比较修复

基线 `98dea609f81b89dd8fa3d5dd15e66f57b8606068` 的独立复验发现合成边界：旧 `2024-01-01 / NULL` 显示 2024、没有 exact day，但与来源 `2024-02-29 / day` 刷新被判 conflict。旧版目标探针确实返回 conflict 并保留旧 pair；9 个格式/比较/纠正联合用例在旧版证据范围断言处失败。修复后目标返回 accepted，pair 为 `2024-02-29 / day`，审计保留旧 `2024-01-01 / NULL`，重复输入 unchanged。这不代表已发生真实生产错误。

修复只将可证明的比较范围与字符串形式范围分开。合法 legacy 按年比较，同年来源 year/month/day 可原子纠正；旧 pair 留在审计中，不识别首日猜精度。已确认冲突、年份冲突、倒退和坏输入仍保旧。项目精度须以拟安装的确认 pair 校验其他来源，人工日期保持；显示排序、legacy 兼容 cutoff 和非榜单统计不随年级比较扩大而改变。日期 policy、归并策略和受影响 Records/Billboard builder/cache 版本同步升级，公开 GET 行为保持。

真实旧副本对照：5,015 对项目/来源比较中 382 对从 conflict 降为 compatible，不能据此宣称同日或批准关系；归并候选仍 0→0。117,522 行原始播放/project 资格输入中，榜单过滤前后均为 113,029，增删为 0（不是逻辑事件总数）。复用 92 份已取得的来源响应，Album pair 全部 unchanged；非人工 C,XOXO 项目 42311 从未知变为来源确认 day，原文 2024-06-28 不变，重复维护变化为 0。Records 日期映射输入 1→3，新增的是 C,XOXO 的两个既有 album/artist 名称键（Camila Cabello、Drake），共用同一来源日；这不是新增身份或最终里程碑数量。3,234 条 Album 原文、2,940 条项目原文与全部人工项目行保持，19 类事实守恒，integrity 为 ok。

新增目标及相关验收 175 passed，覆盖首日/非首日/年月旧值纠正、保护边界、幂等、事务回滚、项目确认、revision、发行对齐和公开快照合同。原完整门禁为上述基线的历史证据。修复版首次默认 run `20261007T091313.941038Z-fcafb905b410` 的 preflight/quality 通过，但同期日期专项持有共享锁，backend 被门禁正确 BLOCKED，不能记 Pass；后续按顺序执行。

修复版默认完整 run `20261007T091710.908605Z-b797669bd7c4`：八个必需阶段同轮 PASS，24 分 32 秒。受控后端 3,413 passed / 2 skipped，真实副本 integration 186 passed / 1 skipped，前端 745 passed / 4 skipped 和构建通过；API 157/157 安全 GET、参数边界和 22 样本热点 P95≤500ms 通过。完整路由、七视口、交互、控件清单及 Chromium/Firefox/WebKit 均 PASS。C,XOXO 新精度的 1440×1000 桌面 / 390×844 手机日期专项另行通过，分别显示 28 Jun 2024 / 2024-06-28，无 NaN/横向溢出；已人工检查截图，仅存 ignored 输出，不代表物理手机验收。

完整门禁后再次核对运行副本与来源副本的保护事实及原文，守恒且 integrity 为 ok。文档审计、白名单 staged diff 和最终 hooks 通过。修复以 `fix: 按年份证据比较未确认的旧发行日期` 新增本地提交，不改写 98dea609，完整 SHA 见最终交付/Git；仅 15 个修复文件，无 seed/schema 形状、API 类型或 UI 代码变更。完整门禁时 HEAD 为 98dea609、修复改动在工作树；此后只收尾文档，业务代码保持一致。

### 独立复验后的详情精度传递修复

基线 `6edbe051971074840f15137f06ea56b0e1ca142d`：项目及候选均已确认 day，项目 2024-08-23、Deluxe 2024-11-14，同年候选比较丢掉精度而选择播放更多的 Deluxe Label/17 首/90 热度，再拼入项目日期。目标失败回归已记录；修复后返回 Original Label/12 首/80 热度与项目确认日期。另一个已证明的同类合成缺陷是 Records 原版目录忽略精度：同年冲突的完整目录令可信原版集合变成 None，修复后为正确的两曲集合。这些合成复现不代表已证实生产错误。

详情比较传入实际精度，排除明确冲突；同日和兼容均参与可用选择，保留来源/名称/类型约束，在身份条件相同后以日期证据优先于播放量。无日期证据时仍是 unknown/legacy，不恢复旧字符串 day 假定；无可用来源则只返回项目事实，不混拼厂牌、曲目数等。项目、歌曲、署名和关系不写回。详情 LRU revision 增加规则版本，summary 现场读取元数据，不持久缓存代表字段；Records 读取两侧精度并升级 sort/builder。读取旧 schema 的固定两次列检查与数据查询保持有界，1/100 项目数据查询预算仍 ≤5，没有 N+1。

真实只读副本对照覆盖 2,940 项目：5 个项目仅有不同年份来源，旧选择会拼接来源元数据，现返回缺省来源字段。Afterlife：2015 项目/2016 Somewhere over My Head；Defying Gravity：2007/2013 Wicked；What Was I Made For?：2025/2023 Live；收穫：2001/2000 我等你；有你在身旁：1997/2006 十光年精選輯。两侧仍是 legacy，未据此自动纠正项目日期，也不声称已确认正确来源或生产错误。其余详情保持；可信原版目录 1,413→1,413，集合差异 0，日期原文及受保护事实保持。

目标、详情、日期、目录/归并、缓存/公开快照及 Records 相关 195 项通过。收穫 / C,XOXO 的桌面 1440×1000、手机 390×844 四个实际页面场景通过，分别仅显示 2001 和已确认发行日，冲突来源厂牌/11 首不再显示，无 NaN/横向溢出，截图仅在 ignored 输出。第一次 Afterlife 页面探针因 EntityStatsPanel 对 found=false 响应的 null daily_trend 读取 length 失败；这是非榜单统计空值消费路径，未在本任务扩展修改，不把该页面记为通过。新默认完整 run `20261007T114740.969274Z-3e3eaadfc05b` 八个必需阶段同轮 PASS，23 分 5 秒：受控后端 3,424 passed / 2 skipped、真实副本 integration 186 passed / 1 skipped、前端 745 passed / 4 skipped 和构建通过；API 157/157 安全 GET、参数边界、22 样本热点 P95≤500ms，通过完整路由/七视口、有效交互、控件清单及 Chromium/Firefox/WebKit。前两次完整 Pass 保留历史，不替代本轮证据。

完整门禁后，来源及运行副本的 19 类保护事实均保持、integrity 为 ok；3,234 条 Album 与 2,940 条项目日期原文、人工项目行保持。文档审计、任务白名单和最终 hooks 通过后，以 `fix: 按来源精度选择专辑详情元数据` 新增独立本地提交，完整 SHA 见最终交付/Git；保留 98dea609 / 6edbe051，不改写历史。仅 14 个白名单文件，不改 schema/seed、API 类型或 UI 代码。完整门禁时 HEAD 为 6edbe051、任务修复在工作树；此后仅收尾文档，业务代码保持一致。

### 原交付与后续

原本地实现与验收完成，以 `fix: 保留发行日期来源精度并限制日级计算` 独立提交；完整 SHA 与提交后工作树状态见最终交付和 Git 记录。README/AGENTS/CLAUDE 产品与执行边界适用且无须修改，AGENTS 与 CLAUDE 保持一致。本次提交仅 59 个任务白名单文件，唯一数据库文件是合成 seed；不推送、不合入 main、不部署、不写正式数据库。运行门禁时 HEAD 仍为基线且任务改动已在工作树，提交前只收尾文档，业务代码与最终完整门禁一致。

主线集成、正式 Online Backup/迁移、有界来源补证、同源快照准备及生产验收步骤见[实施与集成计划](../archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)。本地来源数量不能用于确定生产补证范围；生产需新副本重新量化和审阅冲突。

## 非榜单详情统计空值修复与本地验收

原记录：`2026-10-07-entity-stats-empty-acceptance.md`。

日期：2026-10-07。问题：SS-2026-10-07-001。基线：main c67d296a。

状态：IMPLEMENTED；目标修复与本地浏览器验收通过；全栈范围 PARTIAL；UNCOMMITTED / UNPUSHED / NOT_DEPLOYED。

### 原因与修复

日期精度任务此前的 Afterlife 浏览器探针失败于 EntityStatsPanel；该任务报告明确未把此页面记为通过。本任务重新检查主线，后端 EntityStatsResponse 允许 found=false 响应的 daily/cumulative、分布、summary、daily_metrics 等字段为 null。前端原来继承完整 AnalysisStatsResponse，并在空态 return 前的 useMemo 直接读取 daily_trend.length；最小 found=false 响应也同样崩溃。

统计响应类型现在保留 nullable/缺省合同；仅 found=true 且本组件消费的总量、均值及六个趋势/分布容器存在时才进入统计计算。found=false 不访问统计字段、不挂载图表或最近记录、不请求 rank context 或个人排行。found=true 的相关 null 字段及缺少 found 明确显示“统计响应不完整”，不补成 0 或完整 ready 数据。请求错误优先，loading 保留 skeleton；合法空数组保持真实总量与空图表。hooks 顺序、共享 Query key、发行日起点、metric/时间 URL 和排名分页/延后请求合同保持。

未修改后端、日期治理、统计规则、元数据、隐藏详情页签。仅对本组件已复现的 null 容器消费做检查，不引入全站响应修复器。

### 验证与证据

修复前新建 8 个有意义用例：6 failed / 2 passed，6 个未捕获 TypeError（null/undefined length），日志在 ignored output/playwright/entity-stats-empty/before.log。修复后新增测试共18项，包含三类实体 found=false+null、最小响应与手机入口、loading→无统计→有效数据→无统计、503 snapshot_unavailable→重试无统计、八个消费容器 null、缺少 found、合法空数组及正常每日/累计起点、metric、时间参数。相关三文件32项通过；全量前端763 passed / 4 skipped，构建通过。全量测试保留既有 act 警告，目标文件无未捕获异常；构建保留既有大 chunk 提示，未放宽断言或吞 console 错误。

真实 Chromium 浏览器验收：1440×1000 桌面与390×844手机视口均完成 Afterlife 和 Midnights 共4个详情场景。Afterlife 以实际 null 响应显示空态；桌面指标/近4周与手机时间 sheet 切换保留 URL，无 rank context 或 rankings 请求。Midnights 首屏为2567次/145小时，基础统计后请求 rank context，个人排行首屏未请求，滚动/进入区域后才加载；手机每日/累计、星期/月度及指标切换正常，桌面近4周为实际3次/0.2小时，回全部恢复2567次/145小时。

手机选择2026-10-07：实际API found=true、summary.total_plays=0、daily/cumulative均为空数组；页面保留真实零总量而非 found=false 空态，回全部恢复统计与累计图。这与Afterlife的实体无统计明确区分。四场景及交互没有console error/warning、page error、白屏、NaN或页面横向溢出（overflow=0）；截图已目视检查，只留ignored输出；累计切换首图为动画过渡帧，另在动画结束后补取stable图，确认正常递增至2567。第一次自动化忘记选择具体日期，应用按钮按规则disabled；随后错误地期待空时间窗口必定found=false，经实际API核对修正验收断言。两次探针错误日志保留，不算通过，不修改产品或吞错误。

局部门禁 run `20261007T141410.770143Z-627317c1c64f`：preflight PASS，overall PARTIAL，含diff检查、环境、文档、OpenAPI操作与参数边界审计。另完成CI脚本基线一致性、Ruff及三个改动前端文件ESLint。最终全量前端763 passed /4 skipped和构建通过。未重跑后端全量、真实integration或默认完整八阶段；本轮不复用日期任务的旧完整Pass，不称默认完整全栈Pass。

### 环境与交付边界

隔离工作树：/Users/benjaminlei/.codex/worktrees/entity-stats-empty/202605-SpotifyStats，分支 codex/entity-stats-empty，HEAD c67d296a，未提交。

主目录 data/spotify_stats.db 以 mode=ro SQLite Online Backup 为本任务副本；来源 schema81，副本由当前代码升至88，未连接日期分支 schema89 副本。Afterlife 在本次来源重新定位为项目44155，实际 GET found=false且统计字段null；正常对照 Midnights 为项目41553，2567次/145小时。本任务后端18817与前端5188，独立主库、明确六个 sidecar、APFS克隆封面均在 ignored output/playwright/entity-stats-empty/runtime；不借用其他会话服务，不补证联网。真实响应、截图及日志仅留ignored输出。

来源/运行副本保护事实的SQL双向EXCEPT均为0：plays94760、tracks10026、track_artists10496、albums4030、album_projects2940；比较完整来源列，包含日期原文，行数相同，runtime integrity=ok。来源仍schema81；迁移只在本任务副本。主目录最终仍干净main c67d296a，日期工作树未修改。

修改文件共9个：EntityStatsPanel.tsx、types/analysis.ts、新增entity-stats-empty.test.tsx；开发状态、问题台账、详情只读合同、docs与reports两个地图、新增本报告。暂存区为空；代码与新测试/报告均保留在该工作树。ignored输出另提供包含全部9个文件的entity-stats-empty.patch，供审阅与后续集成；不将真实数据、缓存、密钥或截图打入补丁。

本轮未提交、推送、合入主线、CI、部署、正式库写入或生产验收。桌面/手机视口不能替代物理手机验收。

### 后续独立提交收口

用户验收后授权继续“独立提交空值修复，再与日期精度分支集成，在合并版本运行完整门禁”。再次独立执行全量前端测试：763 passed / 4 skipped，构建与文档审计通过；不修改上文原验收范围。补充变更日志后精确暂存本任务10个文件，提交结果及合并版本门禁在联合交付报告单列。当前未推送、未部署或修改正式数据库。

## 发行日期精度与详情空统计联合集成验收

原记录：`2026-10-07-release-date-stats-integration.md`。

日期：2026-10-07。问题：SS-2026-09-24-003、SS-2026-10-07-001。

状态：LOCAL_INTEGRATED / FULLSTACK_PASS / UNPUSHED / NOT_DEPLOYED。两项代码已本地收口；正式数据库迁移、有界来源补证、CI和生产发布尚未执行。

### 固定交付与集成

用户在验收后授权继续独立提交空值修复、与日期精度集成并运行合并版本完整门禁。空值补丁以10个明确文件独立提交为 `9c360714`，提交钩子通过。日期固定输入为 `98dea609`、`6edbe051`、`c5e3314b`。合并提交 `7f7185cfddb8320fa13090a7f44fdc749098cd6f` 保留两个分支的业务行为，四处冲突仅在变更日志、开发状态和文档地图，已同时保留两项证据。

新版本在独立工作树 `codex/release-date-integration` 验收，随后主目录由干净 `c67d296a` fast-forward 到 `7f7185cf`。后续本报告、状态表与地图收尾仅修改文档，不改变已验收业务。来源工作树保持干净的 `9c360714` 和 `c5e3314b`。

### 新默认完整门禁

成功 run：`20261007T150856.854749Z-290c0b989199`。selection=full；运行HEAD `7f7185cf`、dirty=false；八个必需阶段全部同轮PASS，总耗时 `1,461,832ms`，约24分22秒。optional未启用，不代表preview或额外性能探针通过。

| 阶段 | 状态 | duration_ms |
| --- | --- | ---: |
| preflight | PASS | 7639 |
| quality | PASS | 65946 |
| backend | PASS | 537770 |
| api | PASS | 175420 |
| browser-routes | PASS | 400037 |
| browser-interactions | PASS | 79938 |
| browser-inventory | PASS | 46200 |
| browser-compat | PASS | 148756 |

- 后端seed全量：3424 passed / 2 skipped；独立真实数据integration：186 passed / 1 skipped。两进程按父门禁分工执行，没有再追加marker重跑。
- 前端全量：763 passed / 4 skipped，production build通过；pre-commit、Ruff、mypy、密钥扫描、文档与静态API覆盖通过。既有act、LibreSSL/pandas与大chunk提示保留，没有吞错误或放宽断言。
- API契约157/157、边界113/113通过。51个benchmark组合共1122个样本，失败0；每组合21个有效warm样本，最大warm P95为313.73ms，500ms门槛通过。外部服务首个请求不称cold，warm不推断为cache hit。
- 默认完整路由、360/390/430/768/1280px宽度矩阵、桌面/手机交互、图表、控件和长列表通过；Chromium、Firefox、Playwright WebKit全部通过。WebKit不等同于物理Safari/iPhone验收。
- 存储保护退出0并清理自己的临时目录；峰值890222644 bytes，未触发2GiB预算。使用默认主机阶段排他锁。

规范结果位于 `/tmp/spotify-fullstack-verification/20261007T150856.854749Z-290c0b989199/summary.json`。两轮完整报告、XML和benchmark已另存本任务ignored输出，避免仅依赖latest指针。

### 日期与空统计联合专项

在同一合并版本与运行副本上，Chromium分别检查1440×1000桌面和390×844手机：Afterlife（44155）、Midnights（41553）、收穫（42141）、C,XOXO（42311），共8个场景；另检查手机2026-10-07真实零总量，以及实际操作时间sheet切回全部时间并切换累计图。

Afterlife实际API `found=false`、趋势为null，正常展示“暂无个人播放统计”，不挂载统计KPI。Midnights全部时间保持2567次；单日API `found=true`、总量0、每日和累计数组为空，页面保持真实零统计，切回全部恢复2567次。收穫只展示2001，不混入冲突来源的Rock Records厂牌或发行11首；C,XOXO按确认day展示2024-06-28（桌面日期格式28 Jun 2024）。没有console error/warning、page error、NaN或横向溢出。空态、零总量、年份和day截图已目视检查。

专项CLI会话中途关闭，未将该轮算完整通过；改用独立Playwright进程重新执行。首次独立脚本把日期文字当作时间按钮aria-label，定位超时；按实际“当前按日”标签修正验证脚本后，9场景与零→有效统计交互全部通过。产品代码和断言范围未改，失败日志保留。

### 副本、准备失败与事实守恒

独立环境位于 `/Users/benjaminlei/.codex/worktrees/release-date-integration/202605-SpotifyStats/output/playwright/date-stats-integration/`。主库和六个sidecar以SQLite Online Backup复制先前已准备的schema89日期验收副本，封面和cache使用独立APFS克隆；后端18827、前端5197均为本轮独立进程。原始本地schema81来源另以只读Online Backup保存作对照，未把应用或迁移指向正式库。

首次默认run `20261007T144527.374104Z-8ca56745c84f` 为FAIL：preflight、quality、backend和157/113契约检查通过，但HTTP benchmark多族503 `snapshot_unavailable`，浏览器阶段未执行。原因是准备环境遗漏：Analysis快照绑定device/inode，其他发布键也含数据库路径，复制旧sidecar不能证明新副本可消费。失败不是有效性能样本，也没有算成Pass。

随后仅在本轮副本、共享排他锁内通过正常后台维护重新准备默认快照；等待任务结束后以同一文件身份重启prepared runtime，使用正常应用lifespan，关闭重复预热/搜索/L3启动维护，并按既有隔离方式抑制重复默认队列。主要接口实际恢复200；之后重新执行上述成功的默认完整门禁，没有修改业务或门禁脚本、放宽预算、使用旧完整Pass或改写正式快照。副本仍保留3142条来源精度未知、89条year、1条month和2条day，不把未知变成确认day。

最终19个保护表按来源完整列双向EXCEPT均为0，包含原始播放/歌曲/署名、Album/project原关系、身份与人工覆盖；Album与project日期原文两组也完全保持。plays94760、tracks10026、track_artists10496、albums4030、album_projects2940保持；有效曲目署名投影11770行的规范摘要相同；runtime integrity=ok。正式来源前后Online Backup同样逐项保持，schema仍81。冻结的无writer备份以immutable只读打开，活动runtime使用正常只读连接。

真实数据、来源响应、缓存、封面、截图与日志只留ignored输出，没有进入Git。验收完成已停止本轮后端、前端与浏览器。

### 下一步

代码部分已收口。下一步先从新生产Online Backup做schema88→89演练，仅选择必要Album ID获取来源证据，预览冲突、精度变化与日级消费者降级；按同源证明准备受影响快照，再推进三模式门禁、CI、联合回滚及生产只读/API与桌面手机展示验收。不全库补取，不批准身份/归并，不以本地Pass替代正式迁移、生产模型/OAuth或真机验收。

本轮24分22秒只是该版本单次门禁计时，不能据此关闭三次低干扰稳定验收或安全续跑/分片待办。原两任务历史范围保持：[日期专项](#发行日期精度本地交付与验收)、[空值专项](#非榜单详情统计空值修复与本地验收)；后续排期见[开发状态](../DEVELOPMENT_STATUS.md)和[日期计划](../archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)。
