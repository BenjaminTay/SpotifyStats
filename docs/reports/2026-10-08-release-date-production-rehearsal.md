# 日期精度与详情空统计：生产副本演练与发布准备

日期：2026-10-08。对应 `SS-2026-09-24-003` / `SS-2026-10-07-001`。

业务基线为已本地合入的 `7f7185cf`，文档基线 `91736a5f`。本轮另有发布工具补修，已同步到主工作区，尚未提交、推送或部署；目标发布 SHA 尚未固定。本轮是生产来源副本与发布脚本专项验收，不是新补修版本的默认完整全栈 Pass。前一轮完整全栈保持其[原版本和范围](2026-10-07-release-date-stats-integration.md)。

## 新生产来源

生产现场与最终只读复核均为 `2faadc64c73dadbcca0f05b6a53d1a0aebef4611`、schema88、署名 revision38，三容器 healthy，Web 仍只绑定 loopback 3001/3002；未改变外层入口。

新 SQLite Online Backup 于 UTC 2026-10-08 02:37:08 生成，源连接 `mode=ro`，恢复点为 `/opt/spotify-stats/backups/spotify-stats-date-rehearsal-20261008T023708Z.db`。经 SSH 传输后 SHA256 为 `4cf34ba3a1493df5a95beff09d640dca51f345fe5379ec16a7fa237c6ab70db9`，与服务器相同，大小444,588,032 bytes，integrity=ok。封存文件只读，所有迁移、补证及缓存构建都指向独立本地副本。

最终服务器 source marker 与这份 Online Backup 相同，原始/自动/人工/身份/审计和过滤来源未漂移；生产仍没有日期精度列，未迁移或安装日期观测。原始 plays94,760 / tracks10,026 / track_artists10,496 / albums4,030 / projects2,940保持。

## 迁移和有界补证

- 88→89及重复迁移通过；56张受保护表的旧来源列双向EXCEPT均为0。迁移后旧字符串保持，Album/project来源精度全部NULL。
- 从新备份选取全部90个年/月原文，再加Midnights与C,XOXO各一个已缓存Spotify Album ID作day对照，总计92；不发现身份、不获取全库目录。实际来源是本轮既有SpotifyProvider批量响应，仅保留ID/date/precision供重放。
- 默认预览未修改输入副本。92个结果全部accepted，无缺失或冲突；应用只写日期观测/精度及78个非人工项目精度。重复应用92个unchanged、项目变更0，观测仍92行。
- Album来源：89 year / 1 month / 2 day / 3,142 unknown；项目：76 year / 1 month / 1 day / 2,862 unknown。尚未补证的旧日期保持unknown，不能当作确认发行日。
- 日期原文与56张保护表的来源列在全部准备完成后仍守恒；派生状态的active aggregate revision、ready/错误/时间字段单独排除，当前人工revision及事实没有改变。有效署名11,771行，两份副本的规范化摘要相同。
- 四张weekly aggregate逐行双向EXCEPT=0；60,294条既有FK orphan集合完全相同，未清理或批准身份关系。

## 两处发布工具补修

1. `rebase_music_search_preflight.py`原本只补旧搜索schema；遇到生产88、新候选89及预检期间的无关写入，误报source_facts漂移。修复仅升级可丢弃quiescent副本到staged登记的迁移合同，再比较来源；恢复点保持不动，已应用迁移36不重复失效候选。日期观测审计纳入SOURCE_TABLES，审计单独漂移也拒绝。
2. 独立宿主预检器仍写死聚合v4，后端日期合同已升为`billboard_aggregation_v6_legacy_year`，会拒绝正确的新副本。同步当前常量，并让测试夹具消费后端常量；新回归要求接受v6且拒绝v4，不放宽旧结果的资格。

相关101项回归通过，Ruff及所改两个工具的隔离Mypy通过。展开全部导入的Mypy有既有54项/22文件错误；修改前main同样54项，未把隔离检查称为全仓类型检查通过。保留既有LibreSSL和pandas告警。

真实副本复现：旧脚本拒绝；新脚本88→89成功，保留预检期间的非搜索写入，4精确变体ready、orphan0、integrity=ok。另改一条播放以及仅增加日期审计的两个探针均拒绝，17张派生表逐表摘要不变。临时探针DB已清理，原备份与两个用途的候选、日志及机器报告保留。

## 快照与只读消费者

搜索维护前后四套当前fingerprint全部精确复用，未冷建全库搜索统计。旧聚合v4不满足当前发布证明；在明确副本重新构建v6（约7.9秒），四张aggregate的事实内容逐行相同。受影响sidecar使用独立绝对路径，不借用其他文件身份的旧精确缓存。

已准备Analysis Stats/Records各三个默认范围、六类音乐档案、治理结果，以及默认过滤下全部可用2022–2026年度确定性报告。年度报告均能从精确持久缓存读取；未调用LLM。

两种运行面的20次TestClient API读取通过，覆盖四实体摘要、Afterlife found=false/null趋势、Midnights真实2,567次、无播放日真实0、Analysis与档案；之后公开读取四摘要及五年度也通过。公开与私有GET未改变source marker或增加后台任务。日期摘要实际为Afterlife2015、Midnights2022、收穫2001（legacy）；C,XOXO为来源确认2024-06-28/day。当前未补证的Midnights不能宣称已经确认发行日。

本轮未重新启动浏览器、未做物理手机或目标OCI镜像运行验收；此前双视口UI通过保留原范围。full/showcase/dual静态门禁通过；本轮不是生产发布或真实线上业务验收。

## 两个候选的用途与正式执行顺序

- `release-resume.db`：只迁移89和准备v6聚合，日期精度仍NULL、观测0。用新schema88备份实际执行prepare_music_search_resume，结果`source_equivalent_exact_statistics_resume`；然后仅复用维护4/4及新独立预检器的数据库合同全部通过。它与生产迁移后的事实等价，可用于正常发布续建。
- `runtime/spotify_stats.db`：已补证92份日期，用于新消费者和影响验证。它的来源已经变化，不能直接冒充与旧正式库同源的搜索续建文件；本轮没有将它安装到生产。

后续执行顺序：

1. 明确授权后，提交本轮发布补修并固定SHA；推送main将自动部署，须保留正式CI、镜像身份/三模式、健康与联合回滚门禁。
2. 发布前刷新Online Backup和source marker，在副本准备该SHA的v6聚合及精确四变体/Year-End。只允许同源的未补证候选进入续建；漂移则重新准备，禁止上传本轮旧候选强行覆盖。数据库不进入Git、镜像或Actions Artifact。
3. 目标版本发布成功后，再取得新备份，按同一92 ID重放/刷新来源、预览和事实对照；经有界事务安装日期及非人工项目精度，保持恢复点、源核对和maintenance.lock。此正式写库步骤本轮未授权执行。
4. 在生产自身文件身份下显式准备受影响Analysis/Archive/Governance/Yearly结果，不能直接复制本地sidecar冒充ready。完成公开/私有API、桌面与手机视口的空态/0/恢复和日期专项；失败按生产合同联合回滚数据、SHA和mode。

## 证据位置

隔离工作区为 `/Users/benjaminlei/.codex/worktrees/release-date-integration/202605-SpotifyStats`；ignored `output/release-date-production-20261008/` 包含provenance、migration、provider/observations、preview/apply/replay、aggregate/read preparation、rebase-probes、read-facts-probes、annual-headers、release-resume-probe、final-facts-after-annual和production-final-check的JSON及脚本/日志。辅助采集或探针试跑失败另保留，只将最终成功结果计入上述结论。

## 后续授权

本报告完成后，用户于2026-10-08明确授权提交本轮补修、推送发布及固定92份日期的正式补证。以上未提交/未授权表述保留演练结束时点；生产执行结果另行登记。
