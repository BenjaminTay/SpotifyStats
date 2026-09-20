# 阶段 5A：Search 四变体配置重建共享收口

> 2026-09-20；基线为 main / faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0 与任务开始时的 dirty worktree。
> 本地副本验收；未 commit、push 或部署。最终测量结果见下方。

## 范围与判断

当前实现确实是 L2/L3 × dynamic/fixed 四变体。正式副本有 92,908 条 plays，全部缺少 source_fingerprint 和 import_generation_id，playback_import_state 没有真实 generation/dataset digest；dependency manifest 完整。没有为该数据补造 lineage。

修改设置 min_ms 30000→30001 的正常维护入口原先进入四次独立 full builder，随后为 Year-End 重新加载四次 ledger。exact-ready 也重复运行 L3 attribution planner。开始时先测量，未以历史 180 秒结果作为基线。

原请求分支 B 的“shared-full 已达标”前提不成立：真实无 lineage 副本的显式 legacy atomic shared-full 探针峰值约 1,621 MiB，并且其 ledger 重建 context 与 full 路径存在语义差异。经用户“继续”确认，本轮仅实现保持 full 语义的 invocation-local fallback 与 exact-ready 快速复用，保留原 shared-full/delta 默认行为；未新增 schema、checkpoint、持久基础事实或导入 lineage。

## 实现

- `backend/domains/music_search/invocation.py`：仅在本次维护调用内加载 dynamic/fixed 的独立主轨与 artist 基础帧。调用现有 canonical logical loader 的未缓存实现，保留原阈值、有效署名、logical event、次数/时长双轨与 interval；投影输入列，避免旧 LRU 和额外宽表复制。
- 已切片的专辑加权事实按身份汇总；weekly 保留日期，不能跨发行日期资格边界汇总。使用现有 album project membership/ranker，L2 与 L3 各自派生，没有复制 L2 结果给 L3。
- `snapshot.py` 的可选 invocation 分支复用现有四变体 owner/source/dependency/candidate fence 和原子发布器。context 使用原 full 的 `_context_rows`，包括零次数但有时长的实体；不走 shared-full 的 ledger→context 重建。weekly ledger 保留 full 的 track/album/artist 顺序，Year-End 直接消费 ledger，无额外 lifetime 加载。
- 快照元数据标记 `build_strategy=invocation_full`；缺少 lineage 时 generation 为空、dataset digest 为 NULL，没有宣称 delta 能力。即使有 lineage，该策略也不进入现有仅接受 shared_full/delta 的增量基线选择器。
- `music_search_maintenance_service.py`：按 DB namespace 串行维护，等待者取得所有权后重新读取当前语义及 ready 集合；共享的只有短期 lock，不共享 connection、DataFrame 或结果。精确四套 ready 且持久 L3 policy/identity/project 依赖当前时跳过重复 planner；依赖不匹配仍走原规划流程。
- 完整原子发布前四套旧 active 继续服务。Year-End 在核心快照提交后独立维护，失败不会撤销核心 Search。没有改候选匹配/排序、GET、UI 或 Billboard 产品 builder。

## 数据与测量方法

正式主库以 `mode=ro` SQLite Online Backup 复制到 `/tmp/spotifystats-stage5a/main.db`，仅副本应用仓库已有 migration 74。开始时原始四套并非全部 ready，先在副本完成恢复，得到统一 `ready.db`；该恢复样本不计入 exact-ready 或性能前后对比。

真实缺失 lineage 的配置变化采用正常维护入口；未强制传 shared-full plan。每次独立进程、独立数据库和 Billboard/yearly/analysis/Home 路径。导入、外网和 JobQueue 的边界由临时 harness 与路径 guard 限制。计时覆盖维护调用到 Year-End 完成，不含模块导入和复制数据库。

无 profiler before/after 按 B1/A1/B2/A2/B3/A3 顺序交错；每次保留 50ms 采样目标的 RSS/CPU、stage、SQL execute/fetch 和 DataFrame copy 事件。RSS 为采样峰值，不是系统独占实验；三次样本只报告原始值和 median。SQL 表统计 execute/fetch（包括迭代取行），不把 executemany 的插入行数混为返回行数；批量发布另有整个 publisher 的 wall/CPU。共享构建的 variant `duration_ms` 是最终装配时间，共享加载/metric/chart 的成本在阶段事件中单列，不能相加当作总耗时。

早期 `before-fallback-2/3` 与浏览器活动重叠，不纳入最终 median；`paired-*` 为随后交错测量的正式样本。开发中 profile 1/2/3 的内存超标、微型 seed 元数据未齐和 harness 断言/选择器错误均保留原日志，没有延长 timeout 或删去失败记录。

完整 lineage 场景使用另一个五条播放的微型 seed，由真实 Streaming History importer 生成 generation/source fingerprints/dataset digest，正常发布 import state、补充 fixture 专辑元数据、重建 attribution/聚合及候选索引。其结果只证明合法 shared-full 合同，不代表 92,908 条真实数据的同规模性能。真实数据的 legacy atomic 探针与该合法 lineage seed 分开报告。

## 性能结果

| 交错样本 | before wall / CPU s | after wall / CPU s | before / after RSS MiB |
|---|---:|---:|---:|
| 1 | 137.331 / 129.858 | 32.643 / 30.237 | 1858.83 / 615.88 |
| 2 | 127.007 / 121.715 | 30.983 / 29.259 | 1878.39 / 613.98 |
| 3 | 130.982 / 125.787 | 28.381 / 28.169 | 1874.63 / 617.25 |

wall median **130.982→30.983s，下降 76.35%**；CPU median **125.787→29.259s**；最大采样 RSS **1878.39→617.25MiB**。四套全部 exact-ready，全部样本候选 generation 不变。指定配置变化同时达到 ≥40% 改善和 ≤768MiB 两个门槛。

| 维护内操作 | before full | after invocation fallback |
|---|---:|---:|
| canonical 主轨 / artist loader | 8 / 8 | 2 / 2 |
| `_load_filtered_search_frames` | 12 | 0（4 次 invocation frame load） |
| `_metric_maps` / `_shared_metric_maps` | 4 / 0 | 0 / 4 |
| Billboard raw 主轨 / artist | 4 / 4 | 0 / 0 |
| `_load_and_rank_uncached` | 4 | 0 |
| track / album / artist weekly ranking | 8 / 8 / 8 | 4 / 4 / 4 |
| `compute_album_project_plays` | 8 | 8（含空主轨阶段） |
| `load_track_group_keys` | 44 | 24 |
| SQL execute/fetch calls | 14848 | 13170 |
| SQL fetched rows | 3838081 | 1056156 |
| SQL execute/fetch wall median | 14.732s | 3.192s |
| context atomic publish / active switch | 4 / 4 | 1 / 4 |
| Year-End 额外 ledger/full frame build | 4 | 0 |

同一阈值两套变体共用 1 主轨 + 1 artist loader；榜单仍按 L2/L3 分别计算必要身份/项目结果。双阈值各 2 次 `_shared_metric_maps` / `_shared_chart_lookups`，分别处理 artist 与主轨。

cProfile 前后独立样本：137.617→35.615s；DataFrame copy 6048→3172 次，累计复制行数 71,302,053→17,589,679；GC 16→5 次（0.214→0.102s）。after 共享 metric 0.977s、chart 16.832s、一次原子 publisher 1.323s、Year-End 2.213s；L3 规划仍为配置重建必要阶段，约 6.95s。每阶段 wall/CPU、frame shape 和 cache invalidation 时点保存在 profile-attribution 与原始事件中，嵌套阶段不能直接求和。

exact-ready 原基线无 profiler **4.677s**、profiler **6.858s**，loader/build 为 0，耗时几乎全在重复 L3 planner；优化后三次 wall **0.00554 / 0.00527 / 0.00526s**，仍为 0 loader/build，不切换候选或 active。原三次因小于 50ms 未取得周期样本，其 JSON 的 RSS fallback 落在事后 payload 导出阶段，故不作为 exact-ready RSS 证据；起止采样补测另行记录。

shared-full 基线单列：合法 importer 五条 seed **1.118s / 113.63MiB**（profiler），主轨/artist 各 2 次；真实无 lineage 的 legacy atomic 探针 **46.051s / 1620.61MiB**（profiler），不能冒充同规模合法 lineage 样本，也未达到内存门槛。

补测 `exact-ready-bounded-1/2/3` 在计时前后直接采样：wall 0.00512 / 0.00558 / 0.00550s，RSS 110.66 / 111.02 / 110.77MiB，全部 0 loader/build。

## 完整等价与既有 shared-full 差异

所有比较均包含四变体的 entity_key、play_events、total_ms、peak_position、peak_weeks、weeks_on_chart、weeks_at_no1、power_score、power_rank、first_week、latest_week、first_peak_week，未只比较聚合 totals。

| 场景（均含四变体） | context 行 | weekly ledger 行 | Year-End entity / meta 行 | 字段及顺序 |
|---|---:|---:|---:|---|
| min_ms 30001，三组独立前后比较 | 36212 | 60270 | 2200 / 20 | 全部相等 |
| compilation 开启 | 36422 | 60270 | 2200 / 20 | 全部相等 |
| merge 关闭 | 36212 | 60266 | 2200 / 20 | 全部相等 |
| gap 输入 0（现有 context 规范化为 5） | 36212 | 60270 | 2200 / 20 | 全部相等 |
| importer seed，gap=2，full→invocation | 12 | 24 | 12 / 4 | 全部相等 |
| importer seed，原 shared-full 前后 | 12 | 24 | 12 / 4 | 全部相等 |

默认四变体 context 分别为 L2 dynamic 9304、L3 dynamic 8802、L2 fixed 9304、L3 fixed 8802。空帧、零次数正时长、身份/署名/项目 revision、失败与小 seed 另有 unit/故障注入覆盖。真实历史 ledger 与 20 条 Year-End meta 跨年对账；微型 seed 包含周边界与低于次数阈值的短片段。

额外真实副本场景的单次 before/after wall：compilation 156.458→43.069s（after 520.73MiB），merge-off 201.302→41.493s（572.14MiB），gap=0 规范化边界 170.171→36.803s（619.13MiB）。这些是语义覆盖单样本，不作为 median 或稳定性能结论。合法 lineage seed 原 shared-full 0.840→0.826s，完整字段/顺序无变化。

metadata 中 filter fingerprint、source revision、semantic base、四变体身份和 builder version 必须相等；created_at/activated_at 是运行时间，policy_key、build_strategy、dependency_digest、空 generation 等记录新构建策略。完整 metadata 差异逐项保留在机器可读结果，未通过删除统计字段制造等价。

既有 legacy atomic shared-full 与 full 的差异在本轮修改前已实测：full 36,212 条 context，shared-full 30,970 条，缺失 5,242 条零次数但正时长实体；匹配行的 power_rank 有 4,740 处不同，另有 10 条 L3 实体的 chart summary 字段不同。对应 ledger 全字段相等，Year-End 全字段相等。新 fallback 保留 full 结果；没有扩大本轮范围去决定或更改 shared-full/delta 的身份和排序合同。

## 并发、失败与恢复

独立 importer seed 副本验证：

- 同一进程四个连接并发进入正常维护入口，仅执行 4 次基础加载（每阈值主轨/artist 各一次），四个调用均 ready；随后再次调用不增加 loader 次数；另以新进程打开真实 invocation 成品副本，维护 0.00831s、0 loader/build，确认重启复用。
- 每次 loader 前读取四套 active，整个构建期间均为旧四套；第四套插入失败时原子事务回滚，旧 active 全部保留。
- 设置在第四次加载后变化并建立新 target，旧任务拒绝发布，没有覆盖新 revision。Job handler 遇到失效的 snapshot-set key 时补排当前 semantic base，不能把新 owner 的 Year-End 标成旧任务失败；新增定向测试验证此恢复分支。
- track identity、credit、album project revision 漂移，以及 candidate generation 改变均被 attribution/ledger/source/owner 检查拒绝，旧 active 保留；所有场景退出后 lock registry 为空。
- Year-End 插入故障：核心四套 ready，Year-End aggregate 为 partial、4 个 variant 为 failed；独立可观察，没有把核心结果降级。
- 发布器单元测试同时覆盖原 shared-full 与 invocation 分支的异常、释放和 playback/candidate/semantic fence；dependency 在写锁内复查的原测试继续通过。

上述去重是当前单进程 JobQueue 的维护并发合同。跨进程仍由数据库 owner/source fence 拒绝陈旧发布，不把进程内 lock 描述成跨进程重型计算去重。

## GET 与浏览器

最终代码对 ready、warming、LKG、unavailable、failed 五状态 × private-admin/public-readonly，分别测 candidates 与 context，每组 1 次预热后 30 次样本。context 使用候选返回的最多 5 个 entity key；无候选时用一个合法 key。全部 HTTP 200，最高 warm candidates P95 31.00ms、context P95 9.34ms；plays/aggregate SQL、loader、Billboard builder、snapshot publish、JobQueue sentinel 均 0；测试状态数据库及 WAL bytes/mtime 不变。

Desktop 1280×900 / Phone 390×844 真实 Chromium 共 8 组 ready/warming/failed/unavailable 验收，production build 的 Search 页和桌面 Quick Open 无横向溢出、页面错误或重复 Search URL；24 个 Search 请求均 200。Phone 使用其既有完整 Search 入口。候选名称和实体深链可用，未 ready 的统计显示 `—`，warming 使用 LKG 提示；封面请求替换为本地占位 SVG，未测试外部封面网络。

旧响应竞态通过延迟 Hold 响应、先完成 Love，再释放旧响应验证；切换 track/album 后输入和 URL 仍为 Love，旧 Hold 结果为 0。未延长 timeout。public-readonly 的 unavailable 候选受既有 snapshot membership 隐私规则限制为空；私有 unavailable 仍保留候选入口，没有改写此规则。

浏览器验收发生于本轮维护实现前；UI、Search GET 和相关前端源码没有本轮改动，最终维护代码另做上述 GET 复验。截图、请求和竞态记录保留原时间，不冒充实现后浏览器重跑。

## 回归和正式数据边界

- 完整 backend unit：1,821 passed、1,085 deselected；含 public-readonly、Search snapshot/shared-full/delta/ledger/lineage/credit/Year-End。
- Search API/counting/startup contract：46 passed。
- Search/Quick Open 相关前端：4 文件、44 测试；production build 通过。既有 chunk size warning 保留。
- 新增 invocation 回归；原 shared-full 发布/失败/fence 测试扩展到新分支，没有削弱旧断言。
- Ruff、Python compile、docs audit、git diff check：全部通过，见 `final-gates.log`。

前后完整清单均为 **4,183 个正式文件**，没有新增、删除或 bytes/SHA-256 变化；主库、WAL、Search 派生状态所在数据库及 Billboard/Home/yearly/analysis 缓存内容不变。唯一 mtime 变化为 `data/spotify_stats.db-shm`：仍为 32,768 bytes，SHA-256 前后相同，属于只读 Online Backup 的 SQLite 锁记账；未在正式库迁移、修改设置或重建。

与任务开始保存的逐文件 SHA 比较，本轮只有 6 个原文件变化、3 个新文件、0 删除；所有其他原 dirty 文件的内容保持原样，前端源码无变化。HEAD 仍为 faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0。完整 git status 保存在 git-before.txt / git-after.txt。

## 证据、Git 与后续边界

原始测量、所有失败和修正 harness、profile、数据库副本、完整 payload 均保留在 `/tmp/spotifystats-stage5a/`。可长期复查的报告汇总、脚本、日志、SHA 清单、资源曲线和截图另存于本任务外部证据目录（不进入 Git），具体路径见最终结论。

本轮增量仅含三个 Search 产品文件、两个测试文件，以及本报告、docs 地图/报告索引/CHANGELOG。任务开始时已有的其他 dirty 文件保留；未执行 git add、commit、push 或部署。

本轮实际可达的配置变化 full fallback 已达到时间、内存、四变体完整等价、LKG、并发恢复与 GET 门槛；不需要为该路径引入阶段 5B 的持久 checkpoint/schema 设计。

阶段 5 整体仍标记 **Partial**：原 shared-full 与 full 的既有 context 差异未在此次授权范围内改变，真实数据又没有可用于同规模合法 shared-full 测量的 lineage。进入阶段 6 前，应先单独收口 shared-full 的统计合同与对应真实 lineage 验收；本任务不实施阶段 6，也不把 seed 通过或本轮 fallback 达标写成所有 Search 策略已收口。

长期证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0bb08-5a0a-7c82-9fe7-2b5ef01b8acd/spotifystats-stage5a/`。入口 `final-summary.json`、`profile-attribution.json`、`recovery-after-v2.json`（credit 场景以 `recovery-after-v3-credit.json` 为准）、`public-probe-after.json`、`browser-matrix-v3.json`、`final-inventory.json`。完整数据库和逐实体 payload 保留于临时证据目录，不进入 Git。
