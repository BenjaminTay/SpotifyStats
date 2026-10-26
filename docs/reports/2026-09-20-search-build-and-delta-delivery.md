# 搜索共享构建与真实增量验收

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。合并5A、5B、5C。5B的Partial和真实lineage问题保留，5C Search范围Pass与范围外Analysis 503分开；四变体、语义指纹和delta可达性按各轮证据读取。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [阶段 5A：Search 四变体配置重建共享收口](#阶段-5asearch-四变体配置重建共享收口)
- [阶段 5B：Search shared-full 统计合同与真实 lineage](#阶段-5bsearch-shared-full-统计合同与真实-lineage)
- [阶段 5C：Search 真实 delta 可达性与 identity revision 精度](#阶段-5csearch-真实-delta-可达性与-identity-revision-精度)

## 阶段 5A：Search 四变体配置重建共享收口

原记录：`2026-09-20-search-invocation-fallback.md`。

> 2026-09-20；基线为 main / faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0 与任务开始时的 dirty worktree。
> 本地副本验收；未 commit、push 或部署。最终测量结果见下方。

### 范围与判断

当前实现确实是 L2/L3 × dynamic/fixed 四变体。正式副本有 92,908 条 plays，全部缺少 source_fingerprint 和 import_generation_id，playback_import_state 没有真实 generation/dataset digest；dependency manifest 完整。没有为该数据补造 lineage。

修改设置 min_ms 30000→30001 的正常维护入口原先进入四次独立 full builder，随后为 Year-End 重新加载四次 ledger。exact-ready 也重复运行 L3 attribution planner。开始时先测量，未以历史 180 秒结果作为基线。

原请求分支 B 的“shared-full 已达标”前提不成立：真实无 lineage 副本的显式 legacy atomic shared-full 探针峰值约 1,621 MiB，并且其 ledger 重建 context 与 full 路径存在语义差异。经用户“继续”确认，本轮仅实现保持 full 语义的 invocation-local fallback 与 exact-ready 快速复用，保留原 shared-full/delta 默认行为；未新增 schema、checkpoint、持久基础事实或导入 lineage。

### 实现

- `backend/domains/music_search/invocation.py`：仅在本次维护调用内加载 dynamic/fixed 的独立主轨与 artist 基础帧。调用现有 canonical logical loader 的未缓存实现，保留原阈值、有效署名、logical event、次数/时长双轨与 interval；投影输入列，避免旧 LRU 和额外宽表复制。
- 已切片的专辑加权事实按身份汇总；weekly 保留日期，不能跨发行日期资格边界汇总。使用现有 album project membership/ranker，L2 与 L3 各自派生，没有复制 L2 结果给 L3。
- `snapshot.py` 的可选 invocation 分支复用现有四变体 owner/source/dependency/candidate fence 和原子发布器。context 使用原 full 的 `_context_rows`，包括零次数但有时长的实体；不走 shared-full 的 ledger→context 重建。weekly ledger 保留 full 的 track/album/artist 顺序，Year-End 直接消费 ledger，无额外 lifetime 加载。
- 快照元数据标记 `build_strategy=invocation_full`；缺少 lineage 时 generation 为空、dataset digest 为 NULL，没有宣称 delta 能力。即使有 lineage，该策略也不进入现有仅接受 shared_full/delta 的增量基线选择器。
- `music_search_maintenance_service.py`：按 DB namespace 串行维护，等待者取得所有权后重新读取当前语义及 ready 集合；共享的只有短期 lock，不共享 connection、DataFrame 或结果。精确四套 ready 且持久 L3 policy/identity/project 依赖当前时跳过重复 planner；依赖不匹配仍走原规划流程。
- 完整原子发布前四套旧 active 继续服务。Year-End 在核心快照提交后独立维护，失败不会撤销核心 Search。没有改候选匹配/排序、GET、UI 或 Billboard 产品 builder。

### 数据与测量方法

正式主库以 `mode=ro` SQLite Online Backup 复制到 `/tmp/spotifystats-stage5a/main.db`，仅副本应用仓库已有 migration 74。开始时原始四套并非全部 ready，先在副本完成恢复，得到统一 `ready.db`；该恢复样本不计入 exact-ready 或性能前后对比。

真实缺失 lineage 的配置变化采用正常维护入口；未强制传 shared-full plan。每次独立进程、独立数据库和 Billboard/yearly/analysis/Home 路径。导入、外网和 JobQueue 的边界由临时 harness 与路径 guard 限制。计时覆盖维护调用到 Year-End 完成，不含模块导入和复制数据库。

无 profiler before/after 按 B1/A1/B2/A2/B3/A3 顺序交错；每次保留 50ms 采样目标的 RSS/CPU、stage、SQL execute/fetch 和 DataFrame copy 事件。RSS 为采样峰值，不是系统独占实验；三次样本只报告原始值和 median。SQL 表统计 execute/fetch（包括迭代取行），不把 executemany 的插入行数混为返回行数；批量发布另有整个 publisher 的 wall/CPU。共享构建的 variant `duration_ms` 是最终装配时间，共享加载/metric/chart 的成本在阶段事件中单列，不能相加当作总耗时。

早期 `before-fallback-2/3` 与浏览器活动重叠，不纳入最终 median；`paired-*` 为随后交错测量的正式样本。开发中 profile 1/2/3 的内存超标、微型 seed 元数据未齐和 harness 断言/选择器错误均保留原日志，没有延长 timeout 或删去失败记录。

完整 lineage 场景使用另一个五条播放的微型 seed，由真实 Streaming History importer 生成 generation/source fingerprints/dataset digest，正常发布 import state、补充 fixture 专辑元数据、重建 attribution/聚合及候选索引。其结果只证明合法 shared-full 合同，不代表 92,908 条真实数据的同规模性能。真实数据的 legacy atomic 探针与该合法 lineage seed 分开报告。

### 性能结果

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

### 完整等价与既有 shared-full 差异

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

### 并发、失败与恢复

独立 importer seed 副本验证：

- 同一进程四个连接并发进入正常维护入口，仅执行 4 次基础加载（每阈值主轨/artist 各一次），四个调用均 ready；随后再次调用不增加 loader 次数；另以新进程打开真实 invocation 成品副本，维护 0.00831s、0 loader/build，确认重启复用。
- 每次 loader 前读取四套 active，整个构建期间均为旧四套；第四套插入失败时原子事务回滚，旧 active 全部保留。
- 设置在第四次加载后变化并建立新 target，旧任务拒绝发布，没有覆盖新 revision。Job handler 遇到失效的 snapshot-set key 时补排当前 semantic base，不能把新 owner 的 Year-End 标成旧任务失败；新增定向测试验证此恢复分支。
- track identity、credit、album project revision 漂移，以及 candidate generation 改变均被 attribution/ledger/source/owner 检查拒绝，旧 active 保留；所有场景退出后 lock registry 为空。
- Year-End 插入故障：核心四套 ready，Year-End aggregate 为 partial、4 个 variant 为 failed；独立可观察，没有把核心结果降级。
- 发布器单元测试同时覆盖原 shared-full 与 invocation 分支的异常、释放和 playback/candidate/semantic fence；dependency 在写锁内复查的原测试继续通过。

上述去重是当前单进程 JobQueue 的维护并发合同。跨进程仍由数据库 owner/source fence 拒绝陈旧发布，不把进程内 lock 描述成跨进程重型计算去重。

### GET 与浏览器

最终代码对 ready、warming、LKG、unavailable、failed 五状态 × private-admin/public-readonly，分别测 candidates 与 context，每组 1 次预热后 30 次样本。context 使用候选返回的最多 5 个 entity key；无候选时用一个合法 key。全部 HTTP 200，最高 warm candidates P95 31.00ms、context P95 9.34ms；plays/aggregate SQL、loader、Billboard builder、snapshot publish、JobQueue sentinel 均 0；测试状态数据库及 WAL bytes/mtime 不变。

Desktop 1280×900 / Phone 390×844 真实 Chromium 共 8 组 ready/warming/failed/unavailable 验收，production build 的 Search 页和桌面 Quick Open 无横向溢出、页面错误或重复 Search URL；24 个 Search 请求均 200。Phone 使用其既有完整 Search 入口。候选名称和实体深链可用，未 ready 的统计显示 `—`，warming 使用 LKG 提示；封面请求替换为本地占位 SVG，未测试外部封面网络。

旧响应竞态通过延迟 Hold 响应、先完成 Love，再释放旧响应验证；切换 track/album 后输入和 URL 仍为 Love，旧 Hold 结果为 0。未延长 timeout。public-readonly 的 unavailable 候选受既有 snapshot membership 隐私规则限制为空；私有 unavailable 仍保留候选入口，没有改写此规则。

浏览器验收发生于本轮维护实现前；UI、Search GET 和相关前端源码没有本轮改动，最终维护代码另做上述 GET 复验。截图、请求和竞态记录保留原时间，不冒充实现后浏览器重跑。

### 回归和正式数据边界

- 完整 backend unit：1,821 passed、1,085 deselected；含 public-readonly、Search snapshot/shared-full/delta/ledger/lineage/credit/Year-End。
- Search API/counting/startup contract：46 passed。
- Search/Quick Open 相关前端：4 文件、44 测试；production build 通过。既有 chunk size warning 保留。
- 新增 invocation 回归；原 shared-full 发布/失败/fence 测试扩展到新分支，没有削弱旧断言。
- Ruff、Python compile、docs audit、git diff check：全部通过，见 `final-gates.log`。

前后完整清单均为 **4,183 个正式文件**，没有新增、删除或 bytes/SHA-256 变化；主库、WAL、Search 派生状态所在数据库及 Billboard/Home/yearly/analysis 缓存内容不变。唯一 mtime 变化为 `data/spotify_stats.db-shm`：仍为 32,768 bytes，SHA-256 前后相同，属于只读 Online Backup 的 SQLite 锁记账；未在正式库迁移、修改设置或重建。

与任务开始保存的逐文件 SHA 比较，本轮只有 6 个原文件变化、3 个新文件、0 删除；所有其他原 dirty 文件的内容保持原样，前端源码无变化。HEAD 仍为 faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0。完整 git status 保存在 git-before.txt / git-after.txt。

### 证据、Git 与后续边界

原始测量、所有失败和修正 harness、profile、数据库副本、完整 payload 均保留在 `/tmp/spotifystats-stage5a/`。可长期复查的报告汇总、脚本、日志、SHA 清单、资源曲线和截图另存于本任务外部证据目录（不进入 Git），具体路径见最终结论。

本轮增量仅含三个 Search 产品文件、两个测试文件，以及本报告、docs 地图/报告索引/CHANGELOG。任务开始时已有的其他 dirty 文件保留；未执行 git add、commit、push 或部署。

本轮实际可达的配置变化 full fallback 已达到时间、内存、四变体完整等价、LKG、并发恢复与 GET 门槛；不需要为该路径引入阶段 5B 的持久 checkpoint/schema 设计。

阶段 5 整体仍标记 **Partial**：原 shared-full 与 full 的既有 context 差异未在此次授权范围内改变，真实数据又没有可用于同规模合法 shared-full 测量的 lineage。进入阶段 6 前，应先单独收口 shared-full 的统计合同与对应真实 lineage 验收；本任务不实施阶段 6，也不把 seed 通过或本轮 fallback 达标写成所有 Search 策略已收口。

长期证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0bb08-5a0a-7c82-9fe7-2b5ef01b8acd/spotifystats-stage5a/`。入口 `final-summary.json`、`profile-attribution.json`、`recovery-after-v2.json`（credit 场景以 `recovery-after-v3-credit.json` 为准）、`public-probe-after.json`、`browser-matrix-v3.json`、`final-inventory.json`。完整数据库和逐实体 payload 保留于临时证据目录，不进入 Git。

## 阶段 5B：Search shared-full 统计合同与真实 lineage

原记录：`2026-09-20-search-shared-full-contract.md`。

> 2026-09-20。已按用户裁定修正稳定 Album Project 身份与 Power 排名，修正后的 full / invocation_full 为基线。阶段 5 结论为 **Partial**，暂不进入阶段 6；不再等待统计合同决策。真实规模 shared-full 已完成等价对账；真实追加均因实际 identity revision 漂移安全回退，尚不能宣称真实 delta 发布通过。

### 1. 根因与修复

播放次数和收听时长继续遵守[双轨统计规则](../reference/playback-stats-rules.md)。三个差异有独立根因：

1. **duration-only**：shared-full 已通过共享 lifetime metrics 得到完整实体全集，随后却用 Top-N weekly ledger 重新构造 context。ledger reducer 的保留条件只有正次数或 chart，漏掉 `play_events=0、total_ms>0`。同周 delta 的 clone/apply 和跨周 delta 的 ledger reducer 也使用该错误条件。
2. **Power 排名**：full 的 `_sorted_power_frame` 对已有稳定 `power_rank` 再按 `power_score` 排序，以 pandas 默认 quicksort 和新索引排名；这会打乱同分顺序。旧 ledger reducer 为避免合并同名不同 ID，用数字身份代替名称聚合，但又将替代名称用于最终 tie-breaker。它与正式 Power builder 的完整排序不一致。duration-only 实体本身没有榜单排名，不能用补齐这些实体解释全部 4,740 处 rank 差异。
3. **L3 Album Project chart summary**：full 原来按 `(album_name, artist display name)` 匹配。候选 canonical artist 显示 `Jolin Tsai`，对应 weekly facts 显示 `JOLIN`，同一个稳定 Album Project 被误判为无成绩。

用户已批准第 3 项修正。以下事实保持，Search 不再将其清空：

| Album Project | 专辑 | 峰值 | 在榜周数 | 影响 |
|---|---|---:|---:|---|
| 42423 | Ugly Beauty | 10 | 6 | L3 dynamic/fixed |
| 42440 | 呸 | 7 | 3 | L3 dynamic/fixed |
| 42477 | Pleasure | 1 | 3 | L3 dynamic/fixed |
| 42517 | 花蝴蝶 | 13 | 1 | L3 dynamic/fixed |
| 42521 | 城堡 | 3 | 2 | L3 dynamic/fixed |

实现位于 Search 范围：

- `snapshot.py` 保留 `_shared_metric_maps` → `_context_rows` 的 lifetime 全集，移除 ledger 对该结果的覆盖。真实数据库共享构建复用 5A 已有 compact invocation loader，仍按 dynamic/fixed 分别加载 artist 与主轨，及时释放帧；未修改 `invocation.py` 或重做 5A 优化。
- `_album_chart_map` 以 `album_project_id` 提供成绩；候选展示名称不再参与事实匹配。旧 Search source-album 消费路径通过既有 project membership 与 canonical artist ID 查找同一成绩，候选匹配、排序、响应结构与链接格式均未修改。没有全局艺人改名、元数据治理或其他实体映射重构。
- full / invocation_full 直接保留 Power builder 的 `power_rank`。ledger reducer 保持稳定 ID 聚合，再恢复实际名称，调用同一个 `_stable_power_rank`，包括规范化文字、原文字和稳定排序；不改 Power builder、weekly ranking 或 Year-End 算法。
- 两条 delta 都保留正时长实体；补齐 `_track_delta_maps` 原先遗漏、但调用方实际需要的 physical/L1 映射。L2/L3 仍独立投影。context 和 ledger 发布顺序对齐 full；候选全集变化明确失败，不能静默过滤。
- delta 在重型工作前捕获 candidate generation，发布时继续核对原 generation；旧 builder baseline 不得进入新合同。full 也记录现有 schema 已支持的 lineage/dependency metadata，并在发布锁内复查。
- builder 升至 `music_search_snapshot_v11_shared_contract`；v10 只允许作为既有形状兼容的 LKG，不能 exact-ready 或作为新 delta baseline。唯一范围外的必要同步是独立生产 preflight 的 Search builder 常量，未执行部署。
- 真实 Year-End 故障注入暴露 shared-full 原先会回滚核心 Search 发布。现在 Year-End 写入在 savepoint 内，失败只回滚该可选投影；四变体核心 context/ledger 仍整组原子发布，由已有 Year-End 维护流程报告失败并重试。没有新增 schema、migration、持久 checkpoint 或长期缓存。

### 2. 原始差异的逐字段收口

使用 5A 保存的原始数据库副本与 payload，单独追踪用户给出的 36,212 / 30,970 行问题；此部分是原问题诊断复现，不作为合法 lineage 性能样本。

| 变体 | 原 full 行数 | 原 shared-full 行数 | duration-only 缺失（前→后） | 原 rank 差异→修正基线差异 |
|---|---:|---:|---:|---:|
| L2 dynamic | 9,304 | 7,960 | 1,344 → 0 | 1,208 → 0 |
| L2 fixed | 9,304 | 7,960 | 1,344 → 0 | 1,219 → 0 |
| L3 dynamic | 8,802 | 7,525 | 1,277 → 0 | 1,143 → 0 |
| L3 fixed | 8,802 | 7,525 | 1,277 → 0 | 1,170 → 0 |
| 合计 | 36,212 | 30,970 | **5,242 → 0** | **4,740 → 0** |

`original-replay.json` 从不变的 weekly facts 独立调用正式 Power builder 与修正后的 Search 映射，再与 ledger reducer 逐字段对账；四变体字段差异和重排后的序列差异均为零。10 条 L3 summary 全部恢复，不通过删除 ledger 成绩制造等价。

还在同一原始副本实际运行修正后的 invocation_full：36,212 行，实体键、次数、时长均未改变，weekly ledger 与 Year-End entity/meta 全字段及原 full 顺序完全相等。相对旧 full，4,121 个 rank 字段得到修正，其中包含上述 10 个原 null rank，其余 4,111 个来自旧 full 的排序错误；相对旧 shared-full，另有 1,334 个数字替代键排序错误得到修正。两组修正有重叠，不能简单相加当作原 4,740 差异数。

旧 shared-full ledger 的物理插入顺序与 full 原来不同；本轮保留 weekly facts 全字段，统一为 full 的 track → album → artist、周与榜位顺序。不是放宽顺序比较。

### 3. 正式 importer 的真实规模 lineage

输入为 `data/streaming/` 的 13 份真实 JSON，只读复制至隔离目录。以既有隔离主库副本保存元数据和治理事实，在新的 `real-import.db` 上调用 `backend.core.import_data.import_data`，事务 finalizer 使用正式 `summarise_current_playback_dataset` / `publish_playback_import_state`；source fingerprint 和 generation 均由 importer 产生，dataset digest 来自实际落库集合。然后使用正式 attribution reconcile、aggregation 和 candidate index builder。

| 项目 | 实际结果 |
|---|---:|
| 输入记录 | 92,975 |
| importer 接受并写入 | **92,908** |
| audio / video | 91,903 / 1,005 |
| 精确重复跳过 | 67 |
| 非法记录拒绝 | 0 |
| active plays | 92,908 |
| 缺少 source fingerprint / import generation | 0 |

`total_skipped=26,802` 是源数据的 Spotify skipped 标志数量，不是拒绝数量。输入范围为 2022-06-30 至 2026-08-21；generation 为 `9c13611a-8f58-4dc4-a9a4-f750890169f1`，实际 dataset digest 为 `d642b9bb924a6dc263e0b0a046035965511e9b366a9212ad54975d1c6791a801`。

正式 importer 的元数据重建后，真实测试库的完整 context 为 36,220 行；相对原副本，`artist:813`、`artist:923` 在四变体中成为可达实体，共多 8 行。该库旧 shared-full 为 30,982 行，duration-only 缺失为 5,238；因此不把这组新库数字冒充原问题的 5,242。每次 before/after 与 full 对账均使用同一个 importer 产物和相同治理事实。

### 4. 四变体完整合同对账

逐行比较 context 的全部 12 项公开事实：`entity_key`、`play_events`、`total_ms`、`peak_position`、`peak_weeks`、`weeks_on_chart`、`weeks_at_no1`、`power_score`、`power_rank`、`first_week`、`latest_week`、`first_peak_week`，另有物理关联列 snapshot_key 通过变体关联核验，共 13 列。九个公开 chart summary 字段没有删除、忽略或容差。

weekly ledger、Year-End entity/meta 比较全部事实字段与完整顺序。metadata 核对 filter fingerprint、source revision、semantic base、dependency digest、source generation/dataset digest、policy key、candidate generation、builder version。构建时间、build_strategy 和 delta 的 base/change-set 来源是不同执行的审计信息，单独保留差异，不当作统计事实相等。

| 数据/配置 | 四变体 context 行数（L2 D/F；L3 D/F） | context / ledger / Year-End / metadata |
|---|---|---|
| 默认：独立 corrected full vs shared-full | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |
| 默认：invocation_full vs shared-full | 同上 | 全字段、全顺序相等 |
| compilation 开启 | 9360 / 9360 / 8855 / 8855 | 全字段、全顺序相等 |
| merge 关闭 | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |
| max_merge_gap_minutes=2 | 9306 / 9306 / 8804 / 8804 | 全字段、全顺序相等 |

默认每个 L2 ledger 为 15,065 行，L3 为 15,074 行；每变体 Year-End entity 550 行、meta 5 行，共 2,200 / 20。L2/L3 的结果不同，未把 L2 复制给 L3。非默认设置与 invocation_full 对账；默认另有独立 full 全流程基线。

空帧、duration-only、稳定 Power ties、L2/L3 独立身份、同周/跨周 delta reducers 与发布路径由定向单元测试覆盖。额外尝试正式空输入 importer 成功生成 0 行真实 lineage，但其后既有 Billboard 空聚合路径报 `cannot start a transaction within a transaction`；没有修改该范围外路径，也没有把它记为完整空库维护成功。

### 5. 同周与跨周追加：真实结果及边界

用真实输入的时间前缀建立初始 shared-full，再依次导入真实累积输入，正式 planner 判定 `snapshot_superset` / `incremental`，而非手填 generation 或 delta 证明。单独的无重叠尾片段被 planner 判为 ambiguous，因此没有强制执行；最终测试采用能证明集合包含关系的累积输入。

| 步骤 | 接受新增 | 已存在跳过 | 文件内重复 | active plays | 开放周 | 实际 Search 策略 |
|---|---:|---:|---:|---:|---|---|
| 前缀 | 92,859 | 0 | 67 | 92,859 | 2026-08-14 | shared-full |
| 同周追加 | 25 | 92,859 | 67 | 92,884 | 2026-08-14 | 安全回退 shared-full |
| 跨一周追加 | 24 | 92,884 | 67 | 92,908 | 2026-08-21 | 安全回退 shared-full |

两次回退原因都是 `incompatible_incremental_snapshot_base`。track identity revision 实际从 185100 → 185126 → 185151，policy/dependency fence 随之变化。核心 importer 的 `ensure_track_projection_identity` 和 `refresh_play_source_links` 会更新身份依据；本任务不通过清空 revision、补写 digest 或放宽 fence 强行进入 delta。

两次真实维护的产物另从治理与候选均已完成维护的同一副本强制运行 corrected full 参考 builder，重建 context、ledger 与 Year-End，两组四变体的 context、ledger、Year-End 和要求的 metadata 全字段、全顺序相等，见 `delta-*-ready-full`。最初在候选/attribution 尚未完成维护的中间副本运行 full，出现缺候选及 L3 dependency 错误；该次明确作废，未混入最终比较。

因此：shared-full 与两条 delta **实现采用同一 duration / identity / Power 合同**；真实同周、跨周的安全回退与最终统计可验证，真正通过全部 fence 的真实 delta 原子发布仍缺证据。后续需取得 importer 追加后 identity、membership、candidate content 均保持兼容的合法基线/追加对，或单独立项审计 importer identity revision 的变更边界；不属于修改本任务的统计语义。

### 6. 性能与资源

使用真实 importer 产物，before 为本轮开始保存的 pre-5B Search 源码（包含既有 5A），after 为修复后源码。每个样本独立进程、独立 SQLite 副本与 sidecar，按 before1 → after1 → before2 → after2 → before3 → after3 交错，均正常请求 atomic shared-full，未强制调用 legacy builder、未伪造 lineage。

最终性能表及阶段明细由 `final-*-*.json` 和 `performance-final-summary.json` 提供。采集 wall、进程 CPU、RSS 采样与进程高水位、SQL execute/executemany 调用和返回行、loader 次数、DataFrame.copy 次数/累计行与单元格数、关键阶段耗时。SQL 调用数把一次 executemany 计为一次批调用，返回行按 fetch/迭代累计；copy 量是逻辑复制工作量，不声称每次都分配相同物理字节。

| 独立进程 | wall s | CPU s | 峰值 RSS MiB | SQL 批调用 / 返回行 | copy 次数 / 累计行 |
|---|---:|---:|---:|---|---|
| final-before-1 | 61.266 | 56.683 | 1531.44 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-1 | 48.750 | 43.770 | 649.27 | 13,140 / 942,750 | 4,018 / 17,586,245 |
| final-before-2 | 57.638 | 54.809 | 1625.11 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-2 | 40.102 | 37.825 | 641.38 | 13,140 / 942,750 | 4,018 / 17,586,245 |
| final-before-3 | 63.897 | 59.075 | 1615.17 | 13,133 / 991,769 | 7,970 / 21,024,751 |
| final-after-3 | 65.158 | 58.061 | 642.44 | 13,140 / 942,750 | 4,018 / 17,586,245 |

wall 中位数 **61.266 → 48.750 s（改善 20.4%）**；CPU 中位数 56.683 → 43.770 s。after 最大 RSS **649.27 MiB < 768 MiB**；满足资源门槛。copy 累计单元格由 780,989,175 降至 246,668,427。

| 关键阶段（每组调用数；wall 中位数） | before | after |
|---|---:|---:|
| 共享 loader | 4；11.236 s | 4；8.141 s |
| lifetime metrics | 4；4.673 s | 4；1.423 s |
| chart/ledger | 4；28.537 s | 4；27.687 s |
| 整组发布（含 Year-End） | 1；3.269 s | 1；3.418 s |

阶段计时含嵌套调用，不能将所有阶段相加。after 仍只有四次必要加载：两个阈值各一次 artist、一次主轨；不恢复逐变体 lifetime 全表扫描。

初轮六样本也完整保留，包括 after3 的较慢样本，没有删除离群值；恢复边界修复后，最终六样本另行重测。统计等价性为前置条件，不用资源改进抵消事实差异。

### 7. 并发、恢复与公共读取

- 四个并发维护调用均 ready，仅一组四次 compact loader、一次整组核心发布。全部重型加载期间仍能读取旧 active LKG；owner 在结束后释放。
- 新独立进程 exact-ready：0 loader、0 context/ledger 构建、0 publish、0 Year-End 重建；仅调用轻量 ensure 检查。保留 ready 成品的重启复用成立。
- 核心 INSERT 故障：事务回滚，四个旧 active 指针全部保持；旧任务/新 revision 竞争拒绝发布。
- Album Project、track identity、credit revision、candidate generation 漂移分别注入，必须拒绝旧任务发布。revision 使用现有变更 helper，candidate 通过正式 index rebuild 产生新 generation。
- source generation 漂移用正式 importer 的实际 append/事务发布产生，最终出现明确 `playback generation changed during shared-full snapshot build`，不是手改 lineage 字段。
- Year-End INSERT 故障：核心四变体仍 ready，Year-End 四个变体明确 failed/partial；移除隔离测试触发器后，仅重建四份 Year-End，0 loader、0 核心重建，最终恢复 ready。
- GET：5 个状态 × private-admin/public-readonly × candidates/context，每组合 30 个计时请求并预热一次，全部 200。ready/warming/failed-LKG 返回真实 items；unavailable 返回空 items 与 unavailable，不伪装计数 0。
- GET 哨兵 loader/Billboard 冷建/发布/排队/plays 或 agg_weekly SQL 均为 0。SQLite 初次只读连接创建 0 字节 WAL/SHM 后，探针期间 DB/WAL 字节与 mtime 不变；所有写 SQL 均由 authorizer 拒绝。
- Search API/model 与前端文件无修改；复核 `useMusicSearch.ts`、`MusicSearchResults.tsx` 和 `types/music-search.ts`，仍以 fingerprint/entity_key 拼接上下文、明确区分缺失与真实 0、消费相同九项 summary。没有重跑全应用 UI。

### 8. 门禁、范围和最终结论

| 验证 | 最终结果 |
|---|---|
| shared-full / duration-only / delta / invocation 定向 | 94 passed |
| Search 消费合同、旧 service 与 preflight 定向 | 32 passed |
| 完整 backend unit：`pytest -m unit -q` | 1,830 passed |
| 完整 contract：`pytest -m contract -q` | 434 passed；2 个既有 analysis 探针失败 |
| `ruff check backend deploy/production/validate-music-search-preflight.py` | PASS |
| Python compile：backend、scripts、preflight | PASS |
| docs audit | PASS，109 份当前 Markdown |
| `git diff --check` | PASS |
| Search GET + 页面消费结构 | 600 个计时 GET 全部 200；无冷建、无 plays/agg_weekly 读取；结构未变 |
| 正式文件 / 其他 dirty 文件 | 4,183 个正式文件 size/SHA 全同；范围外变更 0 |

九组最终全量对账包含独立 full、默认 invocation、三个非默认配置、两次真实追加后回退成品与独立 full、三个 after 性能进程之间的结果，全部统计字段/顺序、要求的 metadata 和 candidate generation 均相等。

完整 contract 中两个既有失败为 analysis stats/records GET 503：`test_api_boundary_probe`、`test_safe_readonly_api_smoke_probe`。在同一 dirty 工作区加载保存的 pre-5B Search 源码再次运行这两个探针，仍为相同 503；不改断言、跳过测试或修复范围外 analysis 路径。扩大 Ruff 到所有 scripts 还发现 11 个既有错误，均位于未修改的旧脚本；backend 与本轮 preflight 文件的 Ruff 通过。

正式 `data/` 的 4,183 个文件 size/SHA 全同；共享 worktree 范围外变更为 0。相对本轮恢复点仅 13 个授权文件发生变化（5 个 Search 源码、3 个测试文件、preflight 常量及 4 个文档）。`invocation.py` 与 maintenance service 的既有 5A 修改保持原 SHA。前后 SHA、初始/最终 git status、变更白名单记录在证据目录。未 git add、commit、push、部署；未开始阶段 6。没有修改正式数据库、缓存、设置、导入状态；没有改动其他任务的功能代码。

阶段 5 为 **Partial**：统计差异已经收口，真实 shared-full 具备正式 importer lineage 和规模验证；但合法真实 delta 成功发布尚未得到证实，完整 contract 仍有已复现的范围外失败，额外空库维护尝试也暴露既有空聚合事务问题。**目前不能进入阶段 6。** 这不是新的待审批统计决策，不应绕过 fence 或扩大为导入/身份治理重构来换取 Pass。

证据临时目录：`/tmp/spotifystats-phase5b/`。脚本、结构化对账、逐次性能结果、故障/GET 和门禁日志的长期副本保存于本任务外部产物目录 `spotifystats-phase5b/`，不将真实输入、数据库或用户播放 payload 提交 Git。

## 阶段 5C：Search 真实 delta 可达性与 identity revision 精度

原记录：`2026-09-20-search-real-delta-reachability.md`。

> 2026-09-20，本地隔离副本验收。Search 阶段 5：**Pass**。两个已知范围外 analysis GET 503 不计为 Search 新增回归；可以另开阶段 6，本任务未开始阶段 6。

### 逐实体根因

原 5B 的真实追加同时包含真实候选变化与 no-op revision churn，不能只选其一解释。

| 原场景 | projection 调用的无效 bump | source link 新增导致的有效 bump | revision |
|---|---:|---:|---|
| 同周 25 条 | 25 | 1 | 185100 → 185126 |
| 跨周 24 条 | 24 | 1 | 185126 → 185151 |

同周新增 `play_at_time` 关系为 track 49213（菊花台）、49214（陽光宅男）、49215（牛仔很忙），候选因此增加 6 个 L2/L3 文档；跨周新增 49216（彩虹）、49217（蒲公英的約定）、49218（無雙）、49219（我不配）、49220（扯）、49221（甜甜的），增加 12 个候选文档。对应 `track_albums` 观察关系分别新增 3/6 行。已有 provider owner、canonical work/group、Album Project membership、artist credit 没有身份内容变化。原两次追加必须保留 shared-full 回退。

`ensure_track_projection_identity` 通过 `conn.total_changes` 判定变化，但 `_ensure_compat_track_identity` 无条件 UPDATE，provider external alias UPSERT 也会写回相同字段和 updated_at。原同周/跨周分别因此多 bump 25/24 次。结束时刷新 source links，只因新增上述映射各 bump 一次；既有链接 observed_plays/last_seen_at 更新不构成身份变化。原 9,549 个 compatibility identity 行的 updated_at，以及 6,798/6,795 个 alias 行的 updated_at 变化，逐实体保存在外部证据；不是 9,549 个身份发生改变。

### 修复范围

- identity 两处 SQL 添加 NULL-safe 实际字段变化条件，相同值影响 0 行。保留已有 revision 类型、生产者和所有消费者语义，没有 schema/migration。
- candidate builder 在发布写锁和来源 fence 之后复用完整内容相同、tokenizer/normalization 相同的 active generation；内容改变仍切换 generation，旧 generation 与全部发布 fence 保留。
- 正常 Search 维护入口在完整 base dependency 证明成立时复用当前 attribution，省去播放历史全量聚合。delta 内部继续重查全部 fence。
- 跨周真实读取暴露 `_rows_share_merge_run` 所需 `l1_id` 缺失；周闭包改为复用 full 的 canonical SQL，并显式提供同一身份字段。真实 SQLite 测试覆盖前后边界、provider alias 与 legacy schema。

### 真实输入与正常发布

基线复用 5B 正式 importer 生成的 92,859 条真实前缀及正常 shared-full 成品。新的累计输入只从原始 Streaming History 尾部选取基线已有播放 provider identity 的记录：同周追加 22 条至 92,881；跨一周再追加 16 条至 92,897。未选的 11 条涉及基线未激活曲目。全部原始记录和所属文件、选择清单、正式 planner、importer 与 ChangeSet 证据保存在隔离目录。

同周开放周为 2026-08-14 → 2026-08-14；跨周为 2026-08-14 → 2026-08-21。正式 planner 判定 incremental / snapshot_superset；由 importer 生成新的 source fingerprint、generation、dataset digest，经正式 aggregation 和 `rebuild_current_music_search_derived_data` 发布四变体。没有直接调用内部 delta builder 作为真实发布入口。

### 逐字段依赖与 lineage

两条合法追加的 track identity revision 均保持 **185100**；Album Project 数值 revision 为 **7**（语义摘要 `d0848ef87f97e1257d27`），credit revision **37**。candidate generation、完整文档内容及摘要完全不变。所有 track/provider owner、canonical L2/L3 group key、Album Project membership、artist credit 字段均相等；同周 22 个、跨周 15 个已有 play source link 仅 observed_plays/last_seen_at 改变。聚合的 identity/credit 时间记账更新不改变 revision，agg_config 仅 data_generation_id/source_dataset_digest 更新。

Search dependency digest 全程为 `0283770e30565ced90290d1bf6eed64c5dfba2d226c37cf960c16f2cda35eeb6`。

| 状态 | source generation | dataset digest |
|---|---|---|
| base | `99f05f38-982e-493c-a234-c22e93ef8467` | `67bebac9d60089c974266d4d7f18f33951136b46a48f0277b7d7b0ceb7e338f9` |
| 同周 | `3479e5c7-dc79-4bef-be55-11d5fa7a18de` | `4bbc254d26b434019b380ef0492e2975ca313450f02eb6be731697257170f257` |
| 跨周 | `b9858f4b-a3d4-47c9-ae9a-a036a49dd91d` | `1f893a29ac0f1774427f05926a9de5a09a1c7c63937e2fd7367e128c7fff5939` |

`prepare.py` 的 importer finalizer 构建真实 ChangeSet 并发布实际落库摘要，Search plan 当场保存。初次脚本未将完整 ChangeSet 序列化；随后使用不变 base、累计输入与实际 generation 行，通过同一个正式 builder 只读恢复完整 ChangeSet，确认所生成 Search plan 与原文件逐字段相等，见 `delta-*-changeset-replay.json`。没有修改任何 lineage/revision/digest 来取得兼容。另一次完整记录 finalizer 输出的独立 importer 复验保存在 `final-same-proof.json`，不与原 generation 的性能样本混用。

逐实体明细为 `old-*-diff.json`、`trace-old-*.json`、`root-cause-summary.json`、`*-identity-diff.json` 与 `dependency-proof.json`。这些文件保留所有改变字段、实体 ID、前后值；摘要未替代逐实体证据。

### 四变体发布与完整对账

两类正常维护入口均返回 `incremental_snapshot_delta`，没有 delta_fallback_reason，四个 active 一次事务切换。持久 build_strategy 为 schema 已支持的 `delta`，原 base_snapshot_key/change_set_digest 保留；维护报告 chart_strategy 分别为 `clone_unchanged_open_week` / `replace_affected_completed_weeks`，明确区分实际类型。

独立 corrected full 在相同最终数据库、候选与依赖状态上重建；每个最终性能进程又分别与 corrected full、同状态 shared-full 对账，共 12 组最终比较。

| 场景 | context（L2 D/F；L3 D/F） | weekly ledger（L2 D/F；L3 D/F） | Year-End entity/meta 合计 |
|---|---|---|---|
| 同周 | 9297 / 9297；8795 / 8795 | 14995 / 14995；15004 / 15004 | 2200 / 20 |
| 跨一周 | 9297 / 9297；8795 / 8795 | 15065 / 15065；15074 / 15074 | 2200 / 20 |

context 的全部公开字段、weekly ledger 全字段、Year-End entity/meta 全字段及完整顺序全部一致。filter fingerprint、source revision、semantic base、dependency digest、source generation/dataset digest、candidate generation、policy key、builder version 全相等。created_at/activated_at、base_snapshot_key、build_strategy、change_set_digest 的真实差异逐项记录在 metadata_all_differences；只按对应变体关联 snapshot_key，不删除统计字段来制造等价。

### 性能与工作量

每类至少三对独立进程，delta/shared-full 交错运行。计时覆盖正常维护入口直到 Year-End 完成；importer、聚合预维护与模块加载在计时外。每个样本独立数据库/缓存目录，最终测量期间没有并行运行回归或 full 参考构建。CPU 为进程 CPU；RSS 取采样与进程高水位的较大值，高水位还保守包含后续 payload 导出。SQL 调用与返回行、DataFrame copy 和嵌套阶段事件完整保存，copy 行数表示逻辑复制量。

| 场景 | delta wall 中位数 | shared-full wall 中位数 | 降低 | CPU 中位数 delta / shared-full | 最大 RSS delta / shared-full |
|---|---:|---:|---:|---:|---:|
| 同周 | 3.922 s | 42.676 s | **90.81%** | 3.733 / 40.806 s | **502.02** / 741.08 MiB |
| 跨一周 | 7.879 s | 37.588 s | **79.04%** | 7.717 / 35.647 s | **504.25** / 751.66 MiB |

同周原始 wall 配对为 4.596/44.600、3.922/42.676、3.738/40.924 s；跨周为 9.438/43.368、7.408/36.962、7.879/37.588 s。跨周最终使用编号 3/4/5；1/2 属于键集查询修复前诊断，完整保留但未混入最终统计。没有删除最终版本的较慢样本。

| 维护内工作量 | 同周 delta / shared-full | 跨周 delta / shared-full |
|---|---:|---:|
| SQL 批调用 | 613 / 13140 | 855 / 13140 |
| SQL 返回行（含已发布上下文/账本） | 398284 / 942430 | 658267 / 942589 |
| DataFrame copy 次数 | 1260 / 4002 | 6346 / 4018 |
| copy 累计行 | 1177994 / 17548177 | 1847016 / 17584623 |
| lifetime/shared-full loader | **0 / 4** | **0 / 4** |
| tail 贡献闭包（每阈值） | 22 raw → 18 logical | 16 raw → 15 logical |
| 完整周 raw 闭包 | 无 | 361 行，1 个完整周 |

同周 delta 核心/Year-End 阶段 wall 中位数 1.653/2.065 s；跨周 6.212/1.668 s，其中完整周替换 0.545 s。shared-full loader/metric/chart/publish 中位数分别为同周 8.024/1.347/21.798/3.388 s、跨周 7.168/1.222/18.321/3.631 s；阶段有嵌套，不能相加代替 wall。

播放事实读取仅按真实 generation 索引、周时间范围和有界相邻页进行。查询计划确认周范围及两端 seek 使用 idx_plays_ts；既有 importer 尾部前驱证明使用时间索引倒序 LIMIT 256，从最新尾部取有界页，并非读取 lifetime 帧。没有完整 plays 聚合或 shared-full loader。delta 仍读取已有 compact context/weekly ledger 来维护全局 Power 与完整 Year-End；其工作量包含已发布事实规模，不宣称所有操作只随新增行数线性增长。原始播放重建闭包为 22/16/361 行，不随整个 92,897 条最终播放历史重扫。

### 并发、LKG、失败与重启

- 两类场景各四个连接并发调用正常维护入口，只有一次 delta 构建（两个阈值各一次贡献加载），四个调用都 ready；构建期间旧四套 active LKG 可读。
- 两类场景第四变体 INSERT 注入失败，delta 事务完整回滚，四个旧 active 全部保留。
- 设置/旧任务、track identity、Album Project、credit、实际 candidate 内容改变分别触发语义、attribution 或 candidate fence；原 old active 保留。identity 修正复验使用真实 alias 注册 helper；初轮 harness 误取 NULL track_id 的失败不计为 fence 证据，保留日志并由 corrected 结果替代。
- 源代际竞争通过正式 importer 再追加真实 cross 输入，旧构建被 `playback generation changed` 拒绝。故障矩阵同时注入 full fallback 不可用，以隔离验证失败任务不能用后续成功 full 发布掩盖旧 active 是否保留；正常无故障发布及对账均未禁用 fallback。
- 旧 Job 携带旧 base key/旧 plan，在已有新跨周 ready 成品上经正式 handler 执行，0 构建，所有核心、账本、Year-End、候选及 active 行原样保留。
- 独立进程重启复用同周/跨周成品：ready，0 lifetime loader、0 delta/full、0 publish、0 Year-End rebuild；只执行轻量 Year-End ensure。

### Search GET 与回归门禁

五状态 ready/warming/LKG/failed/unavailable × private-admin/public-readonly × candidates/context，各预热一次再测 30 次，共 **600 个计时 GET，全部 200**。warming 和 failed-LKG 保留真实实体事实，unavailable 返回空统计；无冷建、Billboard、发布、排队、plays/agg_weekly SQL。SQLite authorizer 拒绝写入，探针 DB/WAL 内容和 mtime 不变。GET 同时运行在回归压力下，候选最高 P95 323.78 ms，不将该探针当作独占延迟基准。

- revision、candidate、同周/跨周、shared-full/invocation、lineage 定向：155 passed；最终 SQL seek 另由完整 unit 验证。
- 最终完整 backend unit：**1832 passed**。
- 最终完整 contract：**434 passed，2 个已知 analysis GET 503 失败**（`test_api_boundary_probe`、`test_safe_readonly_api_smoke_probe`）；与初轮及 5B 既有失败相同，没有新增失败。测试日志还保留原有隔离任务清理期间的线程警告，不修改范围外分析/AI task 路径。
- backend Ruff、compile、docs audit、git diff --check 通过。全 scripts Ruff 的 11 个既有错误保留，相关文件本轮 SHA 不变。

### 范围与结论

正式 `data/` 前后均为 **4183 个文件**，size/SHA 全同，没有新增或删除；正式数据库、缓存、设置、导入状态未修改。相对开始时逐文件 SHA，仅 15 个授权源码/测试/文档文件改变，范围外 dirty 文件变化 **0**；既有 schema/migrations 与 snapshot_lineage fence 文件均保持原 SHA。初始及最终 git status、SHA 清单、HEAD、差异白名单保存在证据目录。未 git add、commit、push、部署。

**Search 阶段 5 最终为 Pass**：两条真实 delta 均通过正式 importer/planner/正常维护入口原子发布，与 corrected full 全字段和顺序一致，性能、RSS、无 lifetime 播放重扫、完整 Year-End、LKG/fence/失败回滚/重启和 Search 读取门禁均通过，没有新增回归。完整仓库 contract 仍有上述两项既有范围外失败，不能把这个 Search 独立结论写成整个仓库全绿。

可以开始单独的阶段 6；本任务没有实施阶段 6。

证据工作目录：`/tmp/spotifystats-phase5c-20260920-121341/`。真实输入、数据库、逐实体 payload 不进入 Git。

长期证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bd04-aab8-7073-aa25-fb2ba6fee97b/spotifystats-phase5c/`。入口 `acceptance-summary.json`；性能见 `performance-summary.json`，恢复见 `recovery-results.json` / `recovery-source.json` / `stale-job.json`，只读探针见 `public-probe-after.json`，范围见 `scope-audit.json`。脚本、全部诊断失败与最终门禁日志一并保留；数据库和真实累计输入仍位于隔离工作目录，不进入 Git。
