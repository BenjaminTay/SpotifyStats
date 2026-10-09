# SpotifyStats 问题台账

> 状态：持续维护
> 首次建立：2026-08-27
> 最后状态核验：2026-10-09（d2c4afce正式CI/三模式/部署通过；榜单对决首次生产冷请求三项性能失败，继续优化；OOM独立开放）
> 生产最后确认版本：d2c4afce、schema89、dual；三容器SHA及四排名ready一致，公开个人统计数值与计分正确，源19表/完整jobs/全部发布前后守恒。历史日期与OOM证据保留原范围，资源缓解不是代码修复。开发优先级见[开发状态总表](../DEVELOPMENT_STATUS.md)。
> 下文原有数值、环境状态和已解决项证据保留原始日期；9 月 13 日生产、LLM、Spotify 与 HTTPS 记录不自动代表今天的状态。

## 当前事项状态与近期收口

### 2026-10-08 榜单对决个人播放延迟

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-08-002` | 榜单成绩先出现，个人播放次数、时长与排名迟迟补齐 | `OPEN / IN_PROGRESS`；d2c4afce已部署且生产冷请求未达门槛，新CPU版本S4已收口、S5待验 | 历史S4默认完整PASS与CI失败保留；d2c4afce正式质量/三模式/镜像/部署成功、四rank ready。公开首次28样本数值及计分一致、25性能达标，四专辑3.072秒、两艺人2.847秒、四艺人3.596秒失败；源19表/完整jobs/全部发布守恒，未直接观测线上builder计数。新CPU版本默认八阶段PASS（3,669+187后端、787/4skip前端），30独立冷进程/热21/资源130门槛、96 API对账及90浏览器样本通过。 | P1：固定新CPU阶段SHA，正式CI及生产首轮重新验收；私有HTTPS仍待外部入口。见[规划](../plans/2026-10-08-versus-personal-statistics-performance-plan.md)及[验收报告](../reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)第9节；独立OOM不关闭。2026-10-09。 |
| `SS-2026-10-09-001` | 详情榜单成绩首次加载慢，疑似等待个人排名 | `OPEN / IN_PROGRESS`；S0冻结，S1–S3已实现，S4/S5验收中 | 线上浏览器overview在排名结束前发出；暂扣排名响应仍约330ms显示榜单，排除响应依赖。d5ba干净源码/94,760行真实副本首次歌曲3.14秒、专辑5.27秒、艺人1.30秒，热10–13ms；主成本是时间线/项目归属/完整个人统计。另确认project与名称→ID重复请求及错误后持续Skeleton；原始慢访问竞争占比未量化，线上热HTTP不代替冷验收。 | P1：以已发布实体周榜/年榜事实建立独立overview，必要字段最小投影；project目标化、Query复用与失败状态；冷访问/资源/发布分别验收。见[规划与证据基线](../plans/2026-10-09-music-detail-chart-performance-plan.md)、[分层验收](../reports/2026-10-09-music-detail-chart-performance-acceptance.md)。关联OOM及对决任务独立保持；2026-10-09。 |

### 2026-10-08 生产响应与验收阻塞

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-08-001` | 详情与年度准备期间资源耗尽，管理连接失去响应 | `PARTIAL / MITIGATED`；连接恢复，未代码修复 | 内核确认12:22 global OOM终止uvicorn（约2.38GiB RSS，另Python约850MiB）；自动重启后连接恢复，公开浏览器检查后后端RSS再次约2.3GiB。受控backend重启与逐年新进程有界维护完成五年缓存；12:54三healthy、backend约510MiB。首个冷摘要17.98秒，不算性能通过。 | P1：在副本复现详情/趋势冷路径和LRU驻留，量化并行维护贡献并控制叠加，验收冷/热资源及旧结果连续性。只做运维缓解，未重启共享VM、修改外层入口或回滚日期；不能仅凭OOM日志精确定位11:55超时的首个调用。见[证据](../reports/2026-10-08-release-date-production-delivery.md)，2026-10-08。 |

### 2026-10-07 非榜单详情统计空值

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-07-001` | EntityStatsPanel 在空态判断前读取 nullable 趋势，Afterlife 详情崩溃 | `RESOLVED`；生产专项通过 | 76a4968已发布；私有/公开桌面手机视口均安全空态、真实0及切回正常统计通过，无白屏/异常；两端30次API前后来源与队列不变。原本地32项、前端763/4skip和7f完整八阶段证据保留。 | 本范围收口，资源问题由SS-2026-10-08-001独立跟踪；见[生产验收](../reports/2026-10-08-release-date-production-delivery.md)。2026-10-08。 |

### 2026-10-06 曲目署名重复与标题误拆

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-06-001` | 旧标题署名叠加造成整体占位、完整名误拆及普通with误识别 | `RESOLVED`；S0–S5已完成 | 2faadc64正式发布、CI全success；S4默认八阶段PASS，S5补修94/独立53项、真实17表安装及生产两端API/浏览器通过。15曲目减少18条冗余有效署名，原始事实和34条既有人工覆盖保持。 | 本范围收口；真实补充、改名/拼写/跨ID歧义保留，不批量删除31个差异条目。见[归档计划](../archive/06-productization-closeout/2026-10-06-track-credit-resolution-plan.md)、[验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

### 2026-10-03 播放记录歌曲链接 404

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-004` | Records 将歌曲 ID 字符串化为 `1493.0`，公开详情请求返回 404 | `RESOLVED`；已生产发布 | 新序列化与旧快照响应共用整数 ID 规范化；艺人/专辑身份和统计事实保持。详情入口兼容零小数旧 URL，保留查询/锚点且替换历史项，非法 ID 不发请求。后端专项 110、前端专项 39、生产构建、Ruff/所改模块类型检查通过。真实生产响应副本修正 678 个 ID，非 ID 字段差异 0；公开旧快照测试不写回、不重建、不排队。 | 已随2faadc64发布；生产公开手机点击vampire及旧1493.0参数/锚点规范化通过，见[生产验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

浏览器专项：本地生产构建 `127.0.0.1:15175` 经 SSH 隧道读取生产 public-readonly API；1440×1000 与 390×844 均从 Records 的 vampire 旧链接实际点击到 `/music/tracks/1493`，摘要、统计和榜单页签读取成功。直接打开 `.0` 链接保留 `merge_level` 与锚点；组件回归覆盖零小数、非法小数、查询参数与返回历史。此证据是本地候选前端与生产只读 API 联调，不是生产修复发布、默认完整全栈或物理手机验收。截图与事实对照在 ignored `output/playwright/record-id-fix/`。

### 2026-10-03 公开时间选择

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-003` | 公开播放分析与详情只显示三个时间选项 | `RESOLVED`；已生产发布 | 已移除桌面和手机时间选择器的公开运行面过滤；加载、错误及空结果时保留入口；已准备范围可读取，缺失 Analysis Stats / Records 结果仍明确不可用。见[专项报告](../reports/2026-10-03-public-analysis-time-ranges.md)。 | 已随2faadc64发布；生产公开桌面/手机8选项可见，缺失日范围仍503且保留切换入口，见[生产验收](../reports/2026-10-06-track-credit-resolution-acceptance.md)。2026-10-07。 |

### 2026-10-03 专辑证据集成

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
| --- | --- | --- | --- | --- |
| SS-2026-09-24-001 | 完整曲目分页与发行位置 | `RESOLVED`；daf098ca已正式发布及限定生产维护 | 54份目录/位置及必要缺失provider元数据，Glee106/1、Lana位置、Mimi14共享/6独占、Records保持；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md) | 本范围已收口；不将模拟视口称为物理真机 |
| SS-2026-09-24-002 | 专辑艺人稳定 ID 与有序证据 | `RESOLVED`；daf098ca已正式发布及限定生产维护 | 154份证据/177条有序署名，canonical人工优先、冲突保留，实际发行周期/Records通过；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md) | 13个Album含17条未解析署名保留数据审核；不新增身份批准 |

### 2026-10-03 生产搜索派生外键遗留

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-002` | 生产搜索派生表引用已缺失 snapshot meta | `OPEN` / P2 | schema85源 Online Backup 已有60,294条 FK orphan：weekly chart context60,270、year-end meta20、year-end projection state4；Album维护后集合不变，当前四精确变体ready及entity context读取门禁另验；[生产报告](../reports/2026-10-03-album-metadata-production-delivery.md)。 | 独立调查快照轮转与派生清理合同，先在副本验证；本轮未修复或删除，最后核验2026-10-03。 |

### 2026-10-03 全站封面优化

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-10-03-001` | 小封面优化未覆盖首页、播放记录、音乐档案和当前年度 V2 | `RESOLVED` | `814ea7cb` 已正式发布；默认八阶段全栈 PASS，生产 8,720 个派生资产补齐，原图 stat/原始播放表数量不变；实际 HTTPS 核心 60 + 四视口 192 样本及必要交互完成。 | S0–S5 闭环；高清 Phone 榜单体积增加与非真机边界见报告，最后核验 2026-10-03。见[已完成方案](../archive/06-productization-closeout/2026-10-03-cover-image-optimization-plan.md)、[报告](../reports/2026-10-03-cover-image-optimization-acceptance.md)。 |

### 2026-10-02 新增元数据问题

两个专辑证据事项的当前状态见上方最终集成登记；日期精度已发布、迁移及有界补证，生产专项已收口，资源OOM另行跟踪。

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 / 最后核验 |
| --- | --- | --- | --- | --- |
| `SS-2026-09-24-003` | 发行日期精度丢失 | `RESOLVED`；生产专项通过 | 76a4968/schema89、92来源/78项目精度已安装；原文、有效署名及事实守恒/幂等通过，最终61表与写后备份双向差集0。五年exact年度、两端API/双视口legacy与confirmed/day展示通过；旧完整全栈保留历史。 | 本范围收口、计划归档；未知精度及冲突继续保持审核边界，不扩大身份或全库补证。见[精度合同](../reference/release-date-precision.md)、[生产验收](../reports/2026-10-08-release-date-production-delivery.md)。2026-10-08。 |

详细背景与其他待量化方向见 [元数据路线 §10](../plans/2026-09-23-multi-source-music-metadata-roadmap.md#10-2026-09-24-spotify-现有字段利用审计后续问题)。

### 原有未闭环事项（保留 2026-09-13 证据）

以下两项继续跟踪；耗时数值与外部服务状态属于历史样本。2026-10-02 只核对剩余事项和当前计划，没有重新计时或检查真机。

| ID | 问题 | 当前状态 | 证据与判断 | 下一步 |
|---|---|---|---|---|
| `SS-2026-08-24-004` | 全栈总门禁时间过长，且并发性能竞争、冷建等待和失败后整轮重跑放大交付成本 | `PARTIAL` · P1-A/P1-B 已完成 | 廉价 preflight、跨工作区 `fcntl` 锁和 run-id 独立 summary 已由提交 `8326169f` 实现。当前 `5bcfc5de` 默认完整门禁全部必需阶段 PASS，但实测总耗时 2,832,355ms（约 47 分钟），其中 backend 约 18.8 分钟、API 约 10.5 分钟、browser routes 约 9.2 分钟；说明正确性已闭环但 25 分钟耗时目标仍未达到。见 [`收口与发布报告`](../reports/2026-09-13-development-closeout-and-release.md)。 | 基于本次 run-id evidence 做 `pytest --durations=100` 与 API/浏览器阶段剖析，再评估不降低覆盖、三浏览器和 500ms 阈值的安全并行；严格 evidence manifest 单独续做。 |
| `SS-2026-08-06-005` | PWA/移动网页完成后，iPhone Safari 与 Android Chrome 真机安装、返回、安全区和 OAuth 验收仍未完成 | `PARTIAL / EXTERNAL` · 本轮决定不实施 Capacitor | `d50f924c` 的 dual 三容器、PWA 文件和 loopback 边界均通过服务器独立验收，但 Tailscale/Serve 当前为 Stopped，Spotify 未连接；只有 OAuth URL 的 callback 配置正确。没有明确原生分发需求且真机前置条件未满足，因此不新增 Capacitor 工程。见 [`appification-pwa-capacitor-plan.md`](../plans/2026-08-06-appification-pwa-capacitor-plan.md)。 | 需要远程使用时先显式恢复受控 HTTPS；再由真实 iPhone/Android 完成安装、键盘、返回、安全区和 Spotify consent 回跳。只有确认 App Store/安装包需求后才重启 Capacitor Phase D。 |

## 排序规则：当前实现

### 播放排行：同次数按时长和稳定实体键排序

播放排行页面是 [`AnalysisChartsPage.tsx`](../../frontend/src/pages/AnalysisChartsPage.tsx)，调用 `/api/analysis/charts`。2026-08-29 修复后的服务端排序逻辑为：

```text
metric=plays  : plays DESC, hours DESC, stable entity key ASC, normalized name ASC
metric=hours  : hours DESC, plays DESC, stable entity key ASC, normalized name ASC
```

歌曲、专辑、艺人均按各自稳定实体键排序；跨越同分组的 offset/limit 也不依赖输入顺序。当前真实接口默认过滤、L2、lifetime 样本中，歌曲榜第 11/12 名同为 180 次，11.9h 的 `drivers license` 排在 8.6h 的 `Midnight Rain` 之前。

### Billboard 周榜：同播放次数会按总收听时长降序

Billboard 周榜的单曲、专辑和艺人排名共用 [`chart_ranking.py`](../../backend/domains/billboard/chart_ranking.py) 的 `_stable_weekly_sort()`，规则是：

```text
billboard_week ASC → play_count DESC → total_ms DESC → 稳定 ID ASC → 标准化名称 ASC
```

所以 Billboard 周榜不是随机的：同周同播放次数时，`total_ms`（总收听毫秒数）更高者排名更前；如果连时长也相同，再用 ID/名称稳定区分。当前真实周榜 `2026-08-14` 的歌曲、专辑和艺人数据均符合这一规则。

> 注：Billboard All-time/Power Score 是另一套累计评分排名，不能简单套用“周榜播放次数 + 时长”的解释；如要核对该页面，应单独记录其评分与 tie-breaker。

### Billboard Records：所有同值列表使用业务二级键

2026-08-30 复核了 `/api/billboard/records` 和 `/api/billboard/data` 的 6 个 Records 子页面、8 个后端记录模块、共 51 个列表。冠军圣殿的冠军名人堂已拆成独立的单曲/专辑候选集：单曲按“冠军单曲数 DESC → 单曲冠军周数 DESC”，专辑按“冠军专辑数 DESC → 专辑冠军周数 DESC”，只有对应数量大于 0 的艺人进入榜单。其他记录列表也按各自的日期、周数、Peak、走势评分、播放差额或实体数量等业务指标补齐二级/后续排序，最后使用稳定实体键；完整规则见 [`playback-stats-rules.md`](../reference/playback-stats-rules.md) 的 R39.1。

排序实现会先对完整候选集排序再截断 Top N，因此 cutoff 同值行不会因为 groupby、缓存重建或输入行顺序变化而交换。固定参数和同一 revision 下，两个 Records 接口各 51 个列表的排序巡检均为 0 个违规；这次补充仍不改变 Billboard 周榜的播放次数/总时长排序规则。

## 已确认解决或不再作为开放问题

以下事项有后续交付证据，因此不应从旧提问清单中再次当作“未解决”提出：

- `SS-2026-08-31-002`：未知 Spotify Track ID 的导入防复发和 provider-first duration resolver 已在本地提交 `e251148a` 完成；Online Backup 与真实数据库只读模拟仍为 217 keep / 600 review / 0 个安全操作。存量 review 因缺少唯一目标而不做写入，等待新证据，不再作为未完成代码。见 [`收口报告`](../reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)。
- `SS-2026-08-31-003`：人工专辑关系现在在同一事务内完成专辑/歌曲 mutation 和派生刷新，批次只刷新一次，失败整体回滚；响应公开 targeted/full、影响范围、fallback reason 与后台 job ID。实现位于本地提交 `e251148a`，完整发布状态待本轮后续门禁和部署回填。见 [`收口报告`](../reports/2026-09-13-l1-import-duration-and-manual-merge-closeout.md)。
- Agent V5：原生工具循环、只读工具注册、证据契约、崩溃恢复、SSE 续传和年度报告共享上下文已完成；集成线已进入 `origin/main` 并随 `b0d674bd` 部署。仓库级门禁尾项由 `SS-2026-08-24-004` 跟踪，不是 Agent V5 核心链路未完成。见 [`Agent V5 验收报告`](../reports/2026-08-31-ai-agent-performance-v5-acceptance.md)。
- L2/L3 身份与专辑归属：L2 活动组成员重叠、无效代表、L3 未覆盖/多 owner 和逻辑事件守恒问题已收口，对应代码已进入 `origin/main` 并随 `b0d674bd` 部署。600 个 L1 review 是另一个开放治理队列，不反向把 L2/L3 标记为未完成。见 [`L2/L3 交付报告`](../reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)。
- Billboard 持久快照：周榜、年榜和总榜 cache-first 持久快照、事件驱动后台重建、LKG 与回滚兼容性门禁已完成生产交付；实施计划已归档。见 [`归档计划`](../archive/06-productization-closeout/2026-09-12-billboard-persistent-snapshot-optimization-plan.md) 与 [`交付报告`](../reports/2026-09-13-billboard-persistent-snapshot-optimization.md)。
- `SS-2026-08-31-001`：Billboard 已实现“阈值只约束 `play_count`、`total_ms` 统计全部有效音乐收听区间”的次数/时长双轨规则。提交 `911256f1` 已进入 `origin/main` 并包含在生产代码版本 `b0d674bd`；真实 Online Backup 副本的聚合、四套搜索快照和 API 对账已通过。详见 [`2026-08-31-billboard-count-duration-semantics-research.md`](../reports/2026-08-31-billboard-count-duration-semantics-research.md)。
- `SS-2026-08-27-001`：播放排行同次数排序已解决。播放次数榜现在按 `plays DESC → hours DESC → stable entity key → normalized name`，播放时长榜保留 `hours DESC → plays DESC` 后追加稳定键；歌曲、专辑、艺人及跨同分分页的乱序输入测试通过，真实 180 次样本为 11.9h 在 8.6h 前。该修复没有修改 Billboard 周榜规则。见 [`2026-08-29-billboard-records-consistency-and-ranking-hardening.md`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- `SS-2026-08-26-002`：设置重建状态、导入健康口径、只读治理预览和导入前比较语义已解决。功能范围、真实主库只读探针、Desktop/390px 浏览器、完整 unit/contract 和前端回归已通过；修复提交 `62f48299` 与后续 `dc7055a7` 已进入 `origin/main` 并包含在生产版本 `b0d674bd`。历史数据实际清理仍是独立授权事项。见 [`交付报告`](../reports/2026-08-27-settings-rebuild-and-data-governance-remediation.md)。
- `SS-2026-06-23-006`：播放记录历史规划与当前实现的文档核对已完成。当前 `/api/analysis/records`、路由容器、TanStack Query、5 个栏目和 20 个模块均已存在，并有 Phase 5、移动端与播放记录专项验收；历史规划已补“最终实现差异”并归档。早期 6 栏方案和未采用 P2 只用于回溯，不自动成为当前缺陷或待办。见 [`归档规划`](../archive/06-productization-closeout/2026-06-23-playback-records-plan.md)。
- `SS-2026-08-10-003`：Billboard 冠军圣殿与艺人详情的冠军单曲数不一致已解决。2026-08-29 的实施与验收基线为 detached HEAD `c21ad22841dcc98b3ce7fa20c9306d4830a1da15`；固定参数和同一 revision 下，Taylor Swift 在 Records、`artist_track_counts.top1`、艺人详情 `info.top1`、详情冠军曲和周榜有效署名中均为 34，301 首上榜歌曲逐行指标差异为 0。后续 51 个 Records 列表的二级排序和冠军专辑独立候选集也已收口；`0b23c442` 与 `46fc7afa` 现已进入 `origin/main` 并包含在生产代码版本 `b0d674bd`。当时未在 `46fc7afa` 单独重跑默认全栈门禁的历史边界仍保留在交付报告。见 [`交付报告`](../reports/2026-08-29-billboard-records-consistency-and-ranking-hardening.md)。
- 年度总结的 `Manchild/1000`、重复“今年听歌最多的一天”、首次发现和跨章节分母/身份语义问题，已在 [`2026-08-24-yearly-review-semantic-correction.md`](../reports/2026-08-24-yearly-review-semantic-correction.md) 标记为年度修复范围 Pass。
- Billboard 周榜同次数排序本身不是随机行为；当前代码和稳定排序单测已经覆盖单曲、专辑、艺人及输入顺序打乱场景。见 [`test_billboard_stable_ranking.py`](../../backend/tests/unit/test_billboard_stable_ranking.py)。
- 音乐详情加载、专辑/艺人子榜错误空态、专辑发行日期版本消歧、艺人专辑排行日期聚合、Billboard 艺人预聚合逻辑事件粒度和搜索候选/统计解耦，都已有对应交付报告或回归证据；后续若再次出现症状，应按当前代码和真实数据重新复核，不直接复用旧结论。

## 更新记录

| 日期 | 变化 |
|---|---|
| 2026-10-02 | 新增三项专辑元数据代码缺口的稳定 ID；接入统一开发状态总表，确认 `194fd113` 发布记录，并明确历史耗时及外部环境不作为当前值。 |
| 2026-09-13 | `d50f924c` 已 push 并以 dual 模式部署；Actions 与服务器 `verify.sh` 通过，三容器 healthy、schema 73、92,908 条播放、搜索四变体 ready。Tailscale/Serve 当前停止，生产未配置 LLM 凭据，Spotify 未连接；这些外部/secret 边界未被部署脚本擅自改变。 |
| 2026-09-13 | 完成 L1 导入防复发、provider-first 时长解析和人工关系单事务/一次刷新；真实库与 Online Backup 复审仍为 600 review、0 个安全操作，因此不修改真实数据。 |
| 2026-09-13 | 同步 `origin/main=d37e8aaf` 与生产代码 `b0d674bd`；将 Agent V5、L2/L3、Billboard Records、双轨时长与持久快照的仓库/部署状态收口，新增 L1 防复发和人工归并性能开放项。 |
| 2026-08-29 | 完成播放记录规划与当前 5 栏/20 模块实现的差异核对并归档，将 `SS-2026-06-23-006` 更新为已解决。 |
| 2026-08-29 | 同步仓库与验证状态：Billboard 修复已本地提交为 `0b23c442`，Settings 修复已提交为 `62f48299`，均未 push；Settings 移入已解决，播放记录文档核对随后完成并归档。 |
| 2026-08-29 | 完成 Billboard B1–B4 与独立播放排行 R1 的实现、完整 backend unit/contract、frontend test/build、真实库副本/主库 proof 和响应式验收；默认完整全栈门禁未在 `0b23c442` 上运行。将 `SS-2026-08-27-001` 更新为已解决。 |
| 2026-08-29 | 为 Billboard 次要一致性问题和独立播放排行 tie-breaker 建立分阶段修复规划。 |
| 2026-08-29 | 将 `SS-2026-08-10-003` 更新为已解决：在实施基线、真实数据库、固定参数与同一 revision 下完成 Records/艺人详情四变体的稳定实体 ID 集合、计数、排序和逐行指标对账，Taylor Swift 均为 34，差集为空。 |
| 2026-08-30 | 复核 6 个 Records 子页面、8 个后端记录模块的全部 51 个列表，补齐业务二级/后续指标和稳定实体键；冠军专辑候选集只保留 `冠军专辑数 > 0` 的艺人，并同步更新当前规则、计划与交付报告。 |
| 2026-08-27 | 首次建立台账；登记历史未闭环项；确认播放排行同次数不按时长排序；确认 Billboard 周榜按 `total_ms` 作为第二排序。 |

### 2026-10-08 日期精度发布准备补记

复用`SS-2026-09-24-003` / `SS-2026-10-07-001`：新生产副本与有界补证/快照/API验收完成。补修schema88→89重基及独立预检v4/v6版本漂移；101项回归与真实副本漂移拒绝通过，补丁未提交。下一步固定提交SHA，授权后推送发布，再安装正式日期证据；仍未写正式库。见[报告](../reports/2026-10-08-release-date-production-rehearsal.md)。
