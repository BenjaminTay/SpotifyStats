# 非榜单详情统计空值修复与本地验收

日期：2026-10-07。问题：SS-2026-10-07-001。基线：main c67d296a。

状态：IMPLEMENTED；目标修复与本地浏览器验收通过；全栈范围 PARTIAL；UNCOMMITTED / UNPUSHED / NOT_DEPLOYED。

## 原因与修复

日期精度任务此前的 Afterlife 浏览器探针失败于 EntityStatsPanel；该任务报告明确未把此页面记为通过。本任务重新检查主线，后端 EntityStatsResponse 允许 found=false 响应的 daily/cumulative、分布、summary、daily_metrics 等字段为 null。前端原来继承完整 AnalysisStatsResponse，并在空态 return 前的 useMemo 直接读取 daily_trend.length；最小 found=false 响应也同样崩溃。

统计响应类型现在保留 nullable/缺省合同；仅 found=true 且本组件消费的总量、均值及六个趋势/分布容器存在时才进入统计计算。found=false 不访问统计字段、不挂载图表或最近记录、不请求 rank context 或个人排行。found=true 的相关 null 字段及缺少 found 明确显示“统计响应不完整”，不补成 0 或完整 ready 数据。请求错误优先，loading 保留 skeleton；合法空数组保持真实总量与空图表。hooks 顺序、共享 Query key、发行日起点、metric/时间 URL 和排名分页/延后请求合同保持。

未修改后端、日期治理、统计规则、元数据、隐藏详情页签。仅对本组件已复现的 null 容器消费做检查，不引入全站响应修复器。

## 验证与证据

修复前新建 8 个有意义用例：6 failed / 2 passed，6 个未捕获 TypeError（null/undefined length），日志在 ignored output/playwright/entity-stats-empty/before.log。修复后新增测试共18项，包含三类实体 found=false+null、最小响应与手机入口、loading→无统计→有效数据→无统计、503 snapshot_unavailable→重试无统计、八个消费容器 null、缺少 found、合法空数组及正常每日/累计起点、metric、时间参数。相关三文件32项通过；全量前端763 passed / 4 skipped，构建通过。全量测试保留既有 act 警告，目标文件无未捕获异常；构建保留既有大 chunk 提示，未放宽断言或吞 console 错误。

真实 Chromium 浏览器验收：1440×1000 桌面与390×844手机视口均完成 Afterlife 和 Midnights 共4个详情场景。Afterlife 以实际 null 响应显示空态；桌面指标/近4周与手机时间 sheet 切换保留 URL，无 rank context 或 rankings 请求。Midnights 首屏为2567次/145小时，基础统计后请求 rank context，个人排行首屏未请求，滚动/进入区域后才加载；手机每日/累计、星期/月度及指标切换正常，桌面近4周为实际3次/0.2小时，回全部恢复2567次/145小时。

手机选择2026-10-07：实际API found=true、summary.total_plays=0、daily/cumulative均为空数组；页面保留真实零总量而非 found=false 空态，回全部恢复统计与累计图。这与Afterlife的实体无统计明确区分。四场景及交互没有console error/warning、page error、白屏、NaN或页面横向溢出（overflow=0）；截图已目视检查，只留ignored输出；累计切换首图为动画过渡帧，另在动画结束后补取stable图，确认正常递增至2567。第一次自动化忘记选择具体日期，应用按钮按规则disabled；随后错误地期待空时间窗口必定found=false，经实际API核对修正验收断言。两次探针错误日志保留，不算通过，不修改产品或吞错误。

局部门禁 run `20261007T141410.770143Z-627317c1c64f`：preflight PASS，overall PARTIAL，含diff检查、环境、文档、OpenAPI操作与参数边界审计。另完成CI脚本基线一致性、Ruff及三个改动前端文件ESLint。最终全量前端763 passed /4 skipped和构建通过。未重跑后端全量、真实integration或默认完整八阶段；本轮不复用日期任务的旧完整Pass，不称默认完整全栈Pass。

## 环境与交付边界

隔离工作树：/Users/benjaminlei/.codex/worktrees/entity-stats-empty/202605-SpotifyStats，分支 codex/entity-stats-empty，HEAD c67d296a，未提交。

主目录 data/spotify_stats.db 以 mode=ro SQLite Online Backup 为本任务副本；来源 schema81，副本由当前代码升至88，未连接日期分支 schema89 副本。Afterlife 在本次来源重新定位为项目44155，实际 GET found=false且统计字段null；正常对照 Midnights 为项目41553，2567次/145小时。本任务后端18817与前端5188，独立主库、明确六个 sidecar、APFS克隆封面均在 ignored output/playwright/entity-stats-empty/runtime；不借用其他会话服务，不补证联网。真实响应、截图及日志仅留ignored输出。

来源/运行副本保护事实的SQL双向EXCEPT均为0：plays94760、tracks10026、track_artists10496、albums4030、album_projects2940；比较完整来源列，包含日期原文，行数相同，runtime integrity=ok。来源仍schema81；迁移只在本任务副本。主目录最终仍干净main c67d296a，日期工作树未修改。

修改文件共9个：EntityStatsPanel.tsx、types/analysis.ts、新增entity-stats-empty.test.tsx；开发状态、问题台账、详情只读合同、docs与reports两个地图、新增本报告。暂存区为空；代码与新测试/报告均保留在该工作树。ignored输出另提供包含全部9个文件的entity-stats-empty.patch，供审阅与后续集成；不将真实数据、缓存、密钥或截图打入补丁。

本轮未提交、推送、合入主线、CI、部署、正式库写入或生产验收。桌面/手机视口不能替代物理手机验收。

## 后续独立提交收口

用户验收后授权继续“独立提交空值修复，再与日期精度分支集成，在合并版本运行完整门禁”。再次独立执行全量前端测试：763 passed / 4 skipped，构建与文档审计通过；不修改上文原验收范围。补充变更日志后精确暂存本任务10个文件，提交结果及合并版本门禁在联合交付报告单列。当前未推送、未部署或修改正式数据库。
