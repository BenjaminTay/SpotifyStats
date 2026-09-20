# 阶段 2A：Billboard 页面响应投影与消费切换

> 2026-09-19；HEAD faa5e4e4，dirty。**Partial：本地定向验证与真实副本校准**。阶段 0/0.5/1 和安全收口作为未提交基线保留。

## 交付范围

Records、Weekly、All-Time、Number Ones 已切换到已发布快照上的纯投影。保留所有兼容完整接口、七个 family、原 revision/builder version、默认 readiness、atomic publish 和 private maintenance。没有新增快照、修改重建算法或应用正式库迁移。实现合同见[页面投影参考](../reference/billboard-page-projections.md)。

## 本轮 before / after

使用本轮新建的 92,908 plays Online Backup `/tmp/spotifystats-stage2a/main.db`，在该副本 namespace 重新发布 12 条默认快照。没有读取或复制正式 sidecar 行作为测量快照。before/after 共用这份 DB、sidecar 和默认过滤配置（L2、min_ms=30000、动态阈值、merge gap=5、Top-N=30/20/20、周五12时、不含精选集）。

before 是改动前 production build 的本轮实测；after-controlled 在最终 build、排序修复和输入焦点回归后独立运行，未同时运行本任务测试或交互浏览器。每页每 presentation 各一个样本；进程状态 unknown、snapshot exact。以下耗时是 observed values，不报告稳定 P95，不称 process cold 或生产 SLA。KB 按 1000 B。

| 页面 | presentation | API raw before → after | 实际编码 body before → after | core-ready ms before → after | 结果 |
|---|---|---:|---:|---:|---|
| /billboard/records | Desktop | 7746.520 → 339.524 KB | 822.816 → 57.119 KB | 1063 → 623 | Pass |
| /billboard/records | Phone | 7746.520 → 339.524 KB | 822.816 → 57.119 KB | 1020 → 547 | Pass |
| /billboard | Desktop | 4654.992 → 27.149 KB | 403.724 → 5.522 KB | 705 → 473 | Pass |
| /billboard | Phone | 4654.992 → 27.149 KB | 403.724 → 5.522 KB | 774 → 486 | Pass |
| /billboard/all-time | Desktop | 6762.467 → 599.530 KB | 698.145 → 88.192 KB | 862 → 551 | Pass |
| /billboard/all-time | Phone | 6762.467 → 599.530 KB | 698.145 → 88.192 KB | 923 → 494 | Pass |
| /billboard/number-ones | Desktop | 6761.997 → 216.244 KB | 697.675 → 29.436 KB | 851 → 490 | Pass |
| /billboard/number-ones | Phone | 6761.997 → 216.244 KB | 697.675 → 29.436 KB | 954 → 477 | Pass |

全部 API raw 合计包含 runtime/capabilities 和 settings。Records **339,524 B ≤350,000 B**；Weekly **27,149 B ≤150,000 B**；Number Ones **216,244 B ≤500,000 B**。All-Time 首屏只传 tracks，599,530 B，较 before 页面 API 总量下降约 91.1%。

### 请求图与每条响应

- Records before：capabilities 与 settings 读取，filters ready 后 `/billboard/data`；after：相同 settings 链路后 `/billboard/records?projection=page`。
- Weekly before：settings 后完整 `/billboard/weekly`；after：settings 后 `/billboard/weekly?projection=page&entity=tracks`。切周只请求目标 week 的当前实体、上一完整周和历史 identity。真实入口是 `/billboard`，仓库没有 `/billboard/weekly` 页面。
- All-Time before：settings 后完整 `/billboard/all-time`；after：settings 后 `projection=entity&entity=tracks`，albums/artists 在切 tab 后才请求。query key 还包含 page/page_size/sort/direction/peak_filter/search。
- Number Ones before：capabilities 与完整 `/billboard/all-time?merge_level=2&include_compilations=false`；after：settings ready 后 `projection=number-ones`，显式传完整 Billboard context。沿用 all-time 路径，但返回冠军投影，不请求完整 all_time/data。

两个阶段的主测量样本均无 API 404、失败、取消或同 URL 重复请求；并发/串行起止时刻和完整参数保存在 waterfall。after 没有无 projection 的 full endpoints。所有 Billboard 数据响应均 HTTP 200 / exact。编码大小直接取 HTTP Content-Length；gzip 与 identity 分别注明，不进行本地重压缩。

| 页面阶段 | 请求（Billboard 参数见原始样本） | raw B | HTTP encoded B | 编码 |
|---|---|---:|---:|---|
| before /billboard/records | `runtime/capabilities` | 362 | 362 | identity |
| before /billboard/records | `settings` | 470 | 470 | identity |
| before /billboard/records | `billboard/data?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5` | 7745688 | 821984 | gzip |
| before /billboard | `runtime/capabilities` | 362 | 362 | identity |
| before /billboard | `settings` | 470 | 470 | identity |
| before /billboard | `billboard/weekly?merge_level=2&include_compilations=false` | 4654160 | 402892 | gzip |
| before /billboard/all-time | `runtime/capabilities` | 362 | 362 | identity |
| before /billboard/all-time | `settings` | 470 | 470 | identity |
| before /billboard/all-time | `billboard/all-time?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5` | 6761635 | 697313 | gzip |
| before /billboard/number-ones | `runtime/capabilities` | 362 | 362 | identity |
| before /billboard/number-ones | `billboard/all-time?merge_level=2&include_compilations=false` | 6761635 | 697313 | gzip |
| after /billboard/records | `runtime/capabilities` | 362 | 362 | identity |
| after /billboard/records | `settings` | 470 | 470 | identity |
| after /billboard/records | `billboard/records?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5&projection=page` | 338692 | 56287 | gzip |
| after /billboard | `runtime/capabilities` | 362 | 362 | identity |
| after /billboard | `settings` | 470 | 470 | identity |
| after /billboard | `billboard/weekly?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5&projection=page&entity=tracks` | 26317 | 4690 | gzip |
| after /billboard/all-time | `runtime/capabilities` | 362 | 362 | identity |
| after /billboard/all-time | `settings` | 470 | 470 | identity |
| after /billboard/all-time | `billboard/all-time?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5&entity=tracks&page=1&page_size=50&sort=power_score&direction=desc&peak_filter=all&search=&projection=entity` | 598698 | 87360 | gzip |
| after /billboard/number-ones | `runtime/capabilities` | 362 | 362 | identity |
| after /billboard/number-ones | `settings` | 470 | 470 | identity |
| after /billboard/number-ones | `billboard/all-time?min_ms=30000&music_only=true&merge_enabled=true&dynamic_threshold=true&merge_level=2&include_compilations=false&bb_top_n=30&bb_album_top_n=20&bb_artist_top_n=20&bb_week_start_dow=4&bb_week_start_hour=12&max_merge_gap_minutes=5&projection=number-ones` | 215412 | 28604 | gzip |

### All-Time 各实体

全部行可访问，保留旧排序/列选择/搜索/peak filter/分页语义。响应不包含其他实体的数组。

| 实体 | raw B | 实际 encoded B | 对完整 all-time raw 降幅 |
|---|---:|---:|---:|
| tracks | 598698 | 87360 | 91.15% |
| albums | 225521 | 29579 | 96.66% |
| artists | 179785 | 18474 | 97.34% |

## 语义与浏览器证据

- seed（117 plays）及真实副本都生成了旧完整响应与新投影事实集；同一前端对账测试每套 **4 passed**。All-Time 比较所有行、所有列排序、五种 peak filter 与搜索；Weekly 遍历全部已发布周和三类实体，比 current/previous、NEW/RE、摘要和 rank 顺序；Number Ones 比完整冠军历史、power、连冠、累计与所有可用年份；Records 的全部60个字段保持相等，Curiosities 另比较渲染文本/链接/封面。
- production build Chromium，Desktop 1280×900、Phone 390×844。前后共 **64 个页面/tab/历史周状态**与 **32 个附加操作状态**；最终两个交互报告均零失败、零可见事实差异，覆盖六个 Records tab、其他页面三类 tab、历史周、连续搜索与2025年度选择。保存八张截图；核心状态截图无横向溢出。既有组件测试继续覆盖排序、列选择、筛选和分页。
- Query 测试验证参数隔离、切周/切 tab 取消、迟到旧响应不能覆盖、返回缓存命中；All-Time 仅对同实体同 Billboard context 的本地视图变化保留相同实体行，输入框连续输入不失焦。

## public 边界与正式数据保护

- seed contract 和真实副本都启用昂贵 builder、snapshot writer、JobQueue sentinel。exact、同 request-key LKG 正常读取；缺失、不兼容参数、key 异常、Records 混代返回503。读取前后主库/sidecar/WAL/Home/yearly状态不变（SQLite SHM 读锁元数据不作业务写入）。
- 本轮正式主库只用于 Online Backup 源与文件完整性核验；测试/后端服务使用临时主库、sidecar、Home/yearly路径，无 lifespan/background jobs。公开静态封面只读使用既有本地封面文件；浏览器与后端阻断外部网络。
- 正式 `data/spotify_stats.db`、`data/billboard_cache.db`、存在的 yearly cache 和 Home JSON 的 **SHA-256、size、mtime_ns 全部与本轮 before 相等**，见 formal-before.json / formal-after.json。正式 sidecar 内容相等也保证安全收口后的7 family/12 snapshot未变化；没有查询或改写其行来制造状态。正式 schema73未应用migration74。
- 所有 pytest 通过现有 session bootstrap / fail-closed 隔离。副本重建只用于准备校准状态，未改变任何重建实现。

## 修改文件

- `backend/api/billboard/data.py`：可选投影参数及 response model；新增 `backend/api/billboard/projections.py`：只读发布读取、同代校验、纯投影。
- `frontend/src/pages/{RecordsPage,BillboardPage,AllTimeChartsPage}.tsx`、`features/billboard/records/recordsData.ts`、`features/billboard/number-ones/{NumberOnesExperience,numberOnesData}.tsx/ts`：四页消费切换及封面解码；保留既有 presentation 与统计 helper。
- `frontend/src/hooks/useBillboard.ts`、`api/query-keys.ts`、`types/billboard.ts`、生成 `api-types.ts/openapi.json`；新 projection hooks 不改变旧 hooks 的其他调用者。
- 新 backend projection unit/contract、frontend hook与离线事实对账测试；更新既有 compilation setting 页面测试。
- 必要的工具配套：`scripts/lib/performance_browser_contract.mjs` 修正 Weekly 双端共同 DOM marker、Number Ones 原本误写的 API，以及 Records 新核心 API；`scripts/openapi_parameter_boundary_audit.py` 登记新 entity/projection 枚举的422 contract证据。未改预算或timeout。
- 本 reference/report、docs地图、CHANGELOG。

## 验证结果与失败留存

- 完整 backend unit：**1754 passed**（1085 deselected），现有 LibreSSL warning。
- projection/public snapshot/persistent/default maintenance 定向回归：**36 passed**。新增参数枚举门禁另随完整 unit 通过。
- 受影响 frontend 与真实数据语义对账：**154 passed / 10 files**；seed对账另 **4 passed**。
- `npm run build` 通过，保留既有大 chunk 提示；没有调整阈值。Python Ruff/format、编译检查、Node probe contract（4 passed）、文档审计（99 文件）与 git diff --check 全部通过。
- 开发失败记录全部保留：Python3.9运行时Union写法、测试fixture导入/同名收集、Node测试类型作用域、Curiosities漏字段、Weekly未按rank排序、临时浏览器selector在Phone/初始空DOM不适用均已修正；旧失败日志不计入通过。before/after/after-final/after-verified等中间测量也保留；最终表使用after-controlled。完整请求和取消记录不择优覆盖。

## 边界与停止点

投影仍要解码既有完整 family；本轮降低网络体积和浏览器消费负担，不宣称减少快照重建成本。All-Time 使用实体全集投影，本地视图切换的新 query 可能再次取该实体；没有引入服务端分页或缓存优化。Records 的339.5KB是当前副本观测，未来记录量增长可能超过目标；未通过丢行控制大小。

未运行约47分钟默认完整全栈，结论为 Partial；未访问生产、未commit/push/部署。完成阶段2A后停止，不开始阶段2B或其他缓存/重建优化。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage2a`；数据库副本、sidecar和浏览器profile留在/tmp，不复制进Git或交付目录。
