# Billboard共享构建与配置失配修复

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。合并阶段4A共享事实和4B配置失配路径。两阶段是本地受控重建的实现与测量，不替代全项目或生产验收；原始统计、周边界和发布语义保持各自合同。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [阶段 4A：Billboard 单次重建共享事实](#阶段-4abillboard-单次重建共享事实)
- [阶段 4B：Billboard 配置失配重建收口](#阶段-4bbillboard-配置失配重建收口)

## 阶段 4A：Billboard 单次重建共享事实

原记录：`2026-09-20-billboard-generation-facts.md`。

> 2026-09-20；基线为 `main` / `faa5e4e4` 加开始时已有的未提交阶段成果。
> 本轮仅调整 Billboard 受控全套重建。未 commit、push、部署或访问生产。

### 实际修改

- `backend/domains/billboard/build_context.py`：一次维护调用持有独立 context。过滤参数固定，现有完整 source/key 在每个实际 builder 前后核验；DB namespace 或 revision 漂移即拒绝该次发布。context 不进入 LRU；退出及异常时清空事实。返回独立 frame/容器副本，避免消费者加列污染其他 family。
- `chart_load_rank.py`：分离完整 ranked weekly facts 与 TopN 后的计数/前缀步骤；聚合、canonicalization、album project 规则、排序器和 running metrics 算法不变。
- `chart_staged_cache.py` / `chart_compute.py`：通过显式参数共享 track/artist summaries、album/artist counts、Record inputs、基础 album/artist power 及 Records。`power_scores` family 的 unfiltered album total override 保持局部，不能污染 `full_data`。
- `chart_year_end_cache.py`：复用完整候选 ranked facts 和按原实体/周顺序排列的年榜输入，六次年度输出共用封面和 display enrichment。年榜按年度窗口重新计算 peak、weeks、No.1、Top5/10 与积分，真实首入榜周从完整 TopN 历史求得；不会消费全历史 running 列，因此维护路径不再构建这套未使用的前缀。普通榜仍生成完整 running 前缀；没有把普通 TopN 当成年榜完整候选。
- `chart_staged_api.py` / `chart_year_end_api.py`：内部 context 显式传递给未包装的 builder，外部 GET 参数、持久 key、builder version 和 response model 不变。
- `backend/services/billboard_snapshot_service.py`：以现有 full-data exact key 串行化同 generation 的全套维护，避免并发调用分占不同 family 并重复建事实。继续调用现有 family 发布入口，保留 exact short-circuit、每行原子发布与失败保留旧行。
- `backend/tests/unit/test_billboard_build_context.py`：生命周期/异常释放、消费者修改隔离、参数及 namespace/revision fence、不同 TopN 前缀隔离、小型 seed 六配置全字段对账、年榜不调用未消费前缀的 sentinel。

没有改动 persistent cache、JobQueue、导入/增量聚合、schema、Search、Records 分析、Home 或前端产品代码。宽表 copy 的基线直接成本很小；保留消费者隔离 copy，没有为追求次数而共享可变视图。

### 数据与测量方法

正式主库仅作为 `mode=ro` SQLite Online Backup 源。副本含 92,908 plays；migration 74 只在这份临时副本运行。所有 builder 连接 query-only/只读；Billboard、yearly、analysis、Home 路径显式指向 `/tmp/spotifystats-stage4a`，外部网络和 JobQueue 被 sentinel 禁止。

开始时保存所有 backend Python 源码，以 import hook 在独立进程运行精确的优化前 dirty-worktree 版本；没有用 HEAD 代替阶段 3C 后的实际基线。默认过滤保持原设置：L2、动态阈值、连续合并、30/20/20、周五 12:00、不含 compilation。

验收 before/after 交错顺序，每次独立进程、新 sidecar、同一不变主库副本；验收样本不启用 cProfile，等待本轮测试和浏览器进程退出后运行。额外保留前后 cProfile、50ms RSS/CPU 时间序列、SQL execute/fetch 调用/类型/耗时/返回行、关键 DataFrame copy/rows、family 时间和 publish 计数。嵌套 stage 耗时不能相加；SQL 清单包括结束时读取 sidecar 校验的两条查询。只有三次独立样本，报告原始值和 median，不声称稳定 P95 或生产 SLA。

### 完整字段与投影等价

| 场景 | 快照数 | 比较的标量值 | 阶段 2A 投影数 |
|---|---:|---:|---:|
| 默认 L2、compilation off | 12 | 972,409 | 659 |
| L3 | 12 | 951,641 | 659 |
| compilation on | 12 | 972,584 | 659 |
| TopN 10/7/5 | 12 | 399,639 | 659 |
| fixed threshold | 12 | 927,271 | 659 |
| merge disabled | 12 | 927,078 | 659 |

六组共 72 个完整 payload：weekly、all_time、full_data、records、power_scores、summaries、year_end 默认及 2022–2026。递归比较每个字段、类型、列表元素和顺序，无字段排除；同时逐条比较 family/cache key/request key/source revision/builder version。不是只比较哈希或 Top1。

投影比较覆盖三个实体、每个已发布周及默认周、三种 all-time entity、number-ones 和 Records，共 3,954 个投影，字段/顺序和相同序列化方式下字节数一致。2022 覆盖不足、完整中间年度和 2026 进行中状态均在全 payload 对账范围。

seed 六配置独立 builder 与共享 context 全字段对账，准备 L3 仅写每个测试自己的 seed 副本。原始代码在超高固定阈值完全空结果下已有 `KeyError: billboard_week`，优化后仍同样失败；没有伪造成功 payload，亦没有在本轮扩大为空结果产品修复。用户要求的“空结果或极小 seed”以 seed 成功路径验证。

Records 共享依据：hall-of-fame/self-replacement 只选择 power frame 中的 identity、peak、weeks、power_score；cross-level enrichment 增加的列不参与 Records。年度积分和真实首入榜从原始周序列计算；普通前缀没有被替代。完整字段对账及既有 count/duration、跨周、credit、L2/L3、完整周、稳定排序与年榜合同共同守住统计边界。

### 性能结果

| 交错样本 | before wall / CPU 秒 | after wall / CPU 秒 | before / after peak RSS MiB |
|---|---:|---:|---:|
| 1 | 76.680 / 51.562 | 22.631 / 20.591 | 472.95 / 391.95 |
| 2 | 73.115 / 63.461 | 41.561 / 32.305 | 467.67 / 397.45 |
| 3 | 68.525 / 61.125 | 33.142 / 27.468 | 470.09 / 394.06 |

**wall median 73.115 → 33.142s，下降 54.7%，通过 ≥40% 目标。** CPU median 61.125 → 27.468s。after 三次峰值最大 397.45 MiB，通过 ≤768MiB 目标。

本机同时存在用户其他进程活动，不能宣称独占机器或稳定低干扰 SLA。本轮自己的测试/浏览器已结束；before/after 顺序交错，三组全部保留。早期探索默认 before 22.158s、初版 after 16.439s，最终代码探索值 15.599s；这些不同负载下的单次值不混入验收 median。

| generation 内阶段（含嵌套，median 秒） | before | after |
|---|---:|---:|
| weekly | 12.932 | 12.341 |
| all_time | 4.029 | 3.122 |
| full_data | 9.177 | 10.844 |
| records | 6.215 | 0.257 |
| power_scores | 1.929 | 2.167 |
| summaries | 1.783 | 0.631 |
| year_end | 35.687 | 5.492 |

full_data 首次计算 Records，后续独立 records family 复用结果；shared work 的归属随构建顺序移动，不能把某个 family 的计时变化单独当作 GET 回退。

| 实际操作次数 / generation | before | after |
|---|---:|---:|
| `_load_and_rank_uncached` | 2 | 1 |
| `_try_load_from_agg` | 2 | 1 |
| `compute_weekly_rankings` | 2 | 1 |
| `compute_album_weekly_rankings` | 2 | 1 |
| `compute_artist_weekly_rankings` | 2 | 1 |
| `_add_running_metrics` | 6 | 3 |
| `compute_track_summary` | 4 | 1 |
| `compute_artist_summary` | 3 | 1 |
| `compute_album_track_counts` | 3 | 1 |
| `compute_artist_track_counts` | 2 | 1 |
| `compute_album_power_scores` | 3 | 1 |
| `compute_artist_power_scores` | 3 | 1 |
| `compute_power_scores` | 27 | 14 |
| `compute_records` | 2 | 1 |
| `_add_cover_urls` | 8 | 3 |
| `enrich_track_artist_names` | 13 | 6 |
| `store_persisted_snapshot` | 12 | 12 |

`compute_power_scores` 包含 Records 的年度/年代子榜；保留的 14 次不是 14 次相同全时计算。封面仍保留 weekly、full_data、year_end 三个独立输入语义，尤其 L3 下既有展示参数差异没有被擅自统一。

| SQL 类型 | before | after |
|---|---:|---:|
| SELECT | 803 | 725 |
| WITH | 10 | 4 |
| PRAGMA | 381 | 526 |
| INSERT | 12 | 12 |

总调用 **1,206 → 1,267（+5.1%）**，其中 SELECT/WITH **813 → 729（−10.3%）**。额外 source fence 增加连接及 PRAGMA；没有放松完整 revision 校验来减少查询。SQL execute/fetch 累计耗时 median **6.097 → 3.959s**。这是小幅总调用增加、实际读取减少的权衡；不能宣称 SQL 总次数下降，若按严格零增长口径验收则该项未通过。

**同 key 四并发：**完整 ranked facts builder 1 次、Records builder 1 次，12 个 snapshot key 各发布一次；最终 12 行、7 family、5 年份（2022–2026）加默认年榜，integrity_check=ok。wall 31.542s，peak RSS 399.30MiB。沿用逐行 atomic publish，**不是整套 12 行合成一次 INSERT/一个事务**；不能把每 key singleflight 写成全套只有一个行发布。

after 默认 sidecar 2,260,992 bytes，与 before 2,260,992 bytes 相同；每条 payload 解码、长度及 checksum 校验通过。

**B：周起点 13:00 失配**（优化前当前 revision，诊断观测，非独占机器）：wall 100.031s / CPU 82.986s / peak 1165.02MiB，超过默认场景 RSS 目标。预聚合加载两次均未取得兼容帧；raw 主轨及 artist 各加载两次，`_load_and_rank_uncached` 累计 60.657s；SQL 1178 次、返回 1,193,510 行。按参数失配进入原始事实重建是既有正确性边界，本轮不改 aggregation proof、重写增量聚合或为该场景制造兼容命中。没有将这一诊断样本与默认受控交错样本合并。

### 浏览器与 public-readonly

production build、Chromium Desktop 1280×900 / Phone 390×844，周榜、每周榜首、年榜、总榜、榜单记录五页面，各覆盖 exact、同 request-key LKG、missing，共 30 次。核心就绪要求实际实体深链/DOM 事实、正确路由和成功 API；missing 要求明确未发布提示及结构化 503。全部无意外 404、重复 API、错误 skeleton、横向溢出。每页仅 capabilities、settings、一个核心 Billboard GET；继续使用 `projection=page/entity/number-ones`，未恢复 `/data`。

LKG 通过测试进程的 source dependency 注入实现，不修改数据库。所有请求前后临时主库/WAL、sidecar/WAL、Home/yearly/analysis bytes、大小和 mtime 相同，builder/publish/queue sentinel 均为零。响应保留 current / last_known_good、source/target 和 unavailable 状态。

封面请求由浏览器 harness 截获为本地占位图，禁止 CDN 及下载任务；封面 URL 字段和实体 deep link 通过完整 payload/DOM 比较，未将本轮描述成封面网络下载验收。首轮 harness 误把 LKG freshness 当作 warming，并使用了不符现有文案的 missing 条件；失败 attempt 完整保存，修正测量断言后复验，未修改产品文案、超时或等待预算。

本轮单次观测值，单位 ms；不是 P95。HTTP gzip bytes 直接取响应 Content-Length。

| 页面 | exact Desktop / Phone | LKG Desktop / Phone | missing Desktop / Phone | exact raw / gzip bytes |
|---|---:|---:|---:|---:|
| weekly | 646 / 647 | 678 / 666 | 657 / 508 | 26,317 / 4,691 |
| number-ones | 574 / 629 | 673 / 623 | 542 / 513 | 215,412 / 28,606 |
| year-end | 483 / 540 | 515 / 533 | 476 / 485 | 56,149 / 7,313 |
| all-time | 696 / 688 | 683 / 740 | 520 / 518 | 598,698 / 87,360 |
| records | 773 / 757 | 744 / 827 | 637 / 607 | 338,692 / 56,288 |

### 验证与正式数据

- 新 context/维护/架构定向 **33 passed**（包含 context 的 11 个用例）。
- 完整后端 unit **1,802 passed / 1,085 deselected**；Billboard 相关 ranking、duration、year-end、persistent、maintenance 均在内。
- Billboard API/projection/counting/attribution/detail/year-end 与 public boundary 定向 contract **75 passed**。
- 受影响前端 **32 passed / 6 文件**；production build 通过，保留现有大 chunk warning。
- 首轮 seed 缺 L3 归属、空结果既有错误，以及两轮模块行数门禁失败均保留日志。seed L3 在独立测试副本准备，模块组织调整到既有阈值内；没有降低覆盖、放宽预算或改测试阈值。
- Ruff、Python compile、docs audit、git diff --check 通过（最终日志随证据保存）。没有运行默认完整全栈门禁，**全栈结论 Partial**。

正式目录前后 **4,180 个文件**，集合、bytes SHA-256、大小全部相同。主库、WAL、Billboard sidecar、Home/yearly、封面及其他缓存的 mtime 相同；正式 analysis sidecar 仍未被创建。唯一差异是 `spotify_stats.db-shm` 的 mtime 随只读 Online Backup 锁记账变化，32,768 bytes 及 SHA-256 完全相同；未回写 mtime。完整 DB/WAL 不变同时证明原始播放、身份/会员关系、revision、settings 和任务表未被改写。

对比开始时逐文件工作区清单：仅新增/修改本轮 **13 个文件**（8 产品、1 测试、4 文档），无文件删除；未涉及其他旧阶段 hunk。Git 仍在 `main`，HEAD=`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，保持 dirty，无 commit/push/deploy。完整增量路径在 `worktree-delta.json`。

### 剩余热点与停止

主要性能目标（下降 ≥40%、RSS ≤768MiB）与每 key singleflight、完整字段等价、公开只读边界通过；SQL 总调用增加 5.1% 的权衡已单列。完整全栈/生产性能没有在本轮验收。

最终 profile 的最大已标注计算热点仍是普通榜 running metrics **15.842s**，其次 Records **14.066s**；这是带 profiler 的定位值，不能混入上方验收统计。前后 profile 分别 33.165s / 61.958s，机器负载不同，不用其绝对比值判断性能。未使用的年榜前缀已消除，普通榜必需的完整前缀仍保留；source fence 与 JSON 发布也继续有成本。

**目前不需要以持久 checkpoint、新 schema 或全局共享事实作为进入下一阶段的前置条件。可以由用户决定进入阶段 5 Search；阶段 4B 不在本轮追加。** 若未来要求失配场景也达到默认 RSS/耗时目标，应单独设计受预算约束的 raw 重建或 checkpoint，并继续复用既有 aggregation semantic proof/affected-week 维护；本轮未实施这些内容。

阶段 4A 在此停止。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage4a/`。原始临时数据库、sidecar、pytest 工作目录留在 `/tmp/spotifystats-stage4a`，不纳入 Git 或交付目录。

## 阶段 4B：Billboard 配置失配重建收口

原记录：`2026-09-20-billboard-config-mismatch-closeout.md`。

> 2026-09-20；基线为当前 main / faa5e4e4 及开始时的未提交工作区，包含阶段 4A。
> 本地指定 L2 / 13:00 场景验收通过；未 commit、push 或部署。

### 结论与修改原因

4A 已自然消除失配路径的重复 raw 加载：本轮修改前主轨、artist、完整 ranked builder 各只有一次，三次 wall 中位数 **17.540s**。但最大采样 RSS **1102.00MiB**，超过 768MiB，因此进入分支 B。

局部修改后，三次 wall 中位数 **19.422s ≤60s**，最大采样 RSS **681.64MiB ≤768MiB**；四并发峰值 **685.42MiB**，完整事实 builder 1 次，12 个 key 各发布一次。此轮改善的是内存，失配 wall/CPU 中位数没有下降；不将此前 100.031s 的历史单样本当作本轮配对基线。

指定场景无需阶段 4C。建议下一步进入阶段 5 Search，但本任务在 4B 报告后停止，不实施 Search。

### 实现范围

- `build_context.py`：沿用 4A 的完整 ranked facts 与 normal/annual 共享。仅 invocation raw fallback 绕过旧 loader 的进程级 LRU；在已有时间线重建、阈值处理、canonical artist/credit 完成后，给排名消费者独立复制必要列及独立 weighted frame。所有行、顺序、计次/时长权重、identity 和日期输入保留。
- `chart_load_rank.py`：raw 路径先完成主轨/专辑排名与未受发行日限制的 album total，再释放不再消费的 weighted/listening attrs 和临时宽帧；后续 summary/年榜仅保留计次与覆盖日期列，随后加载独立 artist raw。聚合兼容分支的加载与计算顺序保留；未改变 ranker、source credit、project membership 或时间切片算法。
- context 成功退出时补充完整 source 检查，覆盖最后一次 snapshot publish 后的来源漂移；异常和检查失败均通过 finally 清空事实。此前每个 builder 前后、发布前的完整 source/key 检查继续保留。不使用 mtime、MAX(ts) 或行数替代 revision。
- 测试新增 raw LRU 禁入、单次加载、消费者修改隔离、弱引用释放、成功/异常清理、13:00 双轨跨周边界及最后发布后的 namespace/revision 漂移；seed 全字段对账扩展到 13:00、L3/13:00 和 compilation/13:00。

产品改动限两个 Billboard 文件；没有新增 schema、持久 checkpoint、聚合表或全局事实缓存。12 条逐行 atomic publish、失败保留旧行、request/source key 和 builder version 均保持原合同。

### 测量方法与原始样本

正式主库仅以 `mode=ro` SQLite Online Backup 复制到 `/tmp/spotifystats-stage4b/main.db`。92,908 plays；与 4A 一致，仅在副本应用仓库已有 migration 74 索引。此轮没有新增 migration，正式主库没有迁移。构建主库连接强制只读，Billboard/Home/yearly/analysis 显式隔离，正式路径 guard、外网和 JobQueue sentinel 启用。

配置保持默认 min_ms=30000、music_only=true、L2、dynamic_threshold=true、merge_enabled=true、gap=5、TopN=30/20/20、周五、不含 compilation；**唯一失配条件是 hour 12→13**。正常预聚合返回帧 48,226 / 67,566 / 13,344 行，13:00 semantic proof 返回三个 None，实际进入 raw。

before/after 各三次独立新进程、新 sidecar，无 cProfile；所有样本、50ms 目标采样间隔的 RSS/CPU 时间序列、SQL execute/fetch、DataFrame copy、阶段和发布事件均保留。peak 为时间序列的采样峰值。宿主不是独占机器，样本顺序和命名可追溯，不报告稳定 P95。计时从维护调用开始到全套发布结束，不含 Python 模块导入。

| 样本 | 4A 当前代码 wall / CPU s | 4B 最终 wall / CPU s | before / after RSS MiB |
|---|---:|---:|---:|
| 1 | 17.059 / 16.681 | 26.283 / 24.395 | 1078.45 / 674.30 |
| 2 | 18.099 / 17.635 | 19.422 / 18.761 | 1102.00 / 655.31 |
| 3 | 17.540 / 17.276 | 14.753 / 14.725 | 1090.08 / 681.64 |

wall median **17.540 → 19.422s**；CPU median **17.276 → 18.761s**。最大 RSS **1102.00 → 681.64MiB**，下降 38.1%。

默认兼容聚合三次最终 wall：9.599s, 9.480s, 9.360s；中位数 **9.480s**。本轮修改前默认中位数 18.662s，4A 报告中位数 33.142s；未出现 >10% 回退。默认峰值最大 390.53MiB，raw loader 0 次，完整 ranked builder 1 次。不同负载下的下降不单独归因为本轮 raw 修改。

#### 归因与发布

| generation 内操作 | before | after |
|---|---:|---:|
| 主轨 raw / artist raw | 1 / 1 | 1 / 1 |
| `_load_and_rank_uncached` / `_try_load_from_agg` | 1 / 1 | 1 / 1 |
| track / album / artist weekly ranking | 1 / 1 / 1 | 1 / 1 / 1 |
| running metrics | 3 | 3 |
| Records builder | 1 | 1 |
| snapshot publish | 12 | 12 |

| family 累计耗时 median s（含嵌套，不可相加） | before | after |
|---|---:|---:|
| weekly | 11.709 | 14.294 |
| all_time | 1.119 | 0.994 |
| full_data | 2.936 | 2.634 |
| records | 0.089 | 0.075 |
| power_scores | 0.749 | 0.668 |
| summaries | 0.245 | 0.220 |
| year_end | 1.529 | 1.311 |

带 profiler 的 before / after wall 为 27.509 / 20.226s，单独用于阶段归因，不混入上面的验收中位数。raw 输入分别 66,419 / 70,808 逻辑事件；完整 ranked 候选 37,808 / 13,114 / 10,239 行。normal TopN 和六份年榜直接共享这些完整候选，没有各自重载。

关键 weighted copy 最大 167,630 行，宽度从 38 列降至 13 列；事件过滤副本从最多 31 列降至 11 列，最终 summary/coverage raw 输入为 5 列。新增四次必要列复制不共享可变 DataFrame；移除的是后续不再使用的重建对象和重复宽列，不减少候选、输出字段或切片。

SQL execute/fetch before 每次 1271 次、返回 614,128 行；after 每次 1293 次、返回 614,155 行。类型计数 before `{'PRAGMA': 532, 'SELECT': 723, 'WITH': 4, 'INSERT': 12}`，after `{'PRAGMA': 542, 'SELECT': 735, 'WITH': 4, 'INSERT': 12}`。累计 SQL wall median 1.591 → 1.988s。完整语句、stage、CPU、fetch 返回行在样本 JSON；此口径为 cursor execute/fetch，含结束时 sidecar 校验查询，不含 SQLite 隐式事务和 `_connect` 的 executescript DDL。新增成功退出 fence 的查询成本保留，没有放松 revision 检查。

四并发最终 wall / CPU **15.929 / 15.944s**，RSS **685.42MiB**；完整事实 builder 和 Records builder 各 1 次，12 次行发布，最终 7 family / 12 row / integrity_check=ok。逐 key 原子发布保持原样，不声称整套 12 行是一个事务。

初版只提前释放仍为 1,023.13MiB；第二版必要列复制的四并发为 768.33MiB，未作为最终通过样本。随后释放主轨剩余不消费列，并补足退出 source fence；所有中间样本和失败诊断均留存，不择优替换。

### 完整语义对账

| 场景 | 完整 payload | 比较标量值 | 页面响应/投影 |
|---|---:|---:|---:|
| mismatch | 12 | 927,582 | 665 |
| default | 12 | 972,409 | 665 |
| mismatch-l3 | 12 | 907,169 | 665 |
| mismatch-compilations | 12 | 927,757 | 665 |

共 **48 个完整 payload、2,660 个页面响应/投影**，逐字段、类型、列表元素及顺序相等，无 payload 字段排除。每组覆盖 weekly、all_time、full_data、records、power_scores、summaries、默认 year_end 和 2022–2026；页面比较遍历 217 周及默认周 × 三实体、三实体 all-time、number-ones、records 和六份 year-end。Year-End 没有新增投影层，比较其既有完整页面响应。最终失配重复样本、profile 和四并发也与基线逐字段比较。

每行 family/cache key/request key/source revision/builder version、payload 字节长度和 checksum 全部一致；不是只比较哈希、行数或 Top1。L3 与 compilation 额外实库样本用于语义，不并入指定 L2 性能门槛：L3 单次 before/after wall 29.816/102.085s、after CPU 45.279s、RSS 518.48MiB；compilation 单次 wall 25.933/36.661s。L3 的该墙钟观测未满足 60s，不外推所有配置均达标，也不扩展优化范围。

证据覆盖：

- 实际 hour=13、预聚合拒绝匹配，周榜事实与 12:00 输出不同；新增 12:59:30–13:00:30 测试验证计次归新周，时长前后各 30 秒，零计次时长行保留且不能独立入榜。
- 已发布 217 个完整周，最后一周 2026-08-14；2026-08-21 覆盖边缘周不发布。现有 complete-week、历史周维护及跨周切片回归继续通过。
- 完整 payload/投影与相关回归共同覆盖 L2/L3、effective artist credit、album project、compilation、NEW/RE、peak、weeks、No.1、Top5/10、annual_plays/chart_plays、tie-break、列表顺序、封面与实体深链。
- 9 个 seed 配置与独立 builder 全字段对账；原始 raw weighted 帧与必要列副本的双轨排名一致，修改消费者副本不影响基础事实，正常/异常退出均释放 context。

#### 最终 sidecar

最终默认失配 sidecar **2,211,840 bytes**，与 before 相同；各行解压、字节长度与 checksum 校验成功。完整 request key/source revision/builder version 见 `final-snapshots.json`。

| family | 请求年 | 未压缩 payload bytes | SHA-256 |
|---|---|---:|---|
| all_time | 默认/全期 | 6,464,217 | `d25542df38bcf8f90b26f1d9abec5f3db01f531dd0bb4464f064598e9c6b304c` |
| full_data | 默认/全期 | 7,446,168 | `2a450d445c18279ec3b59768d66d137ea7159df66035bb98e5e4522e18c3d0f8` |
| power_scores | 默认/全期 | 632,438 | `bb69c53256b09611ae79a8285297b187d4fc265be1eab11a31ed591f241005ca` |
| records | 默认/全期 | 284,255 | `d75e911ed71a9aff0bed78d2a7c28eb0fa45d235c8a74d57102b0ec6c41656d2` |
| summaries | 默认/全期 | 1,479,237 | `14166d80b619b26b083496728fc45a999fa3b5d4620f792f913b13067982496e` |
| weekly | 默认/全期 | 4,352,544 | `c636c9bd6471534615c6075a58c0c61e7620268fdf1819b0a871d44fa218c527` |
| year_end | 2024 | 56,249 | `8f0ce09c4570fade398980482be0976ebf1b462bb0ae69bea9293c119b0a7825` |
| year_end | 2023 | 55,333 | `b54a672e758fc50c7c3f38ddd7327c044f648351bcf17982bffa6c785f7bc9d2` |
| year_end | 2025 | 56,006 | `7a7141321d3c9e8327424bf14ec4074163e3044beb9e1108ea7ffca600b1a986` |
| year_end | 2026 | 55,348 | `c041e5389a280dce91cda7814cd00d1ae6d0ea841cfdb1db0d29e645cdfd870f` |
| year_end | 2022 | 54,889 | `56a5cca7b43b00ab87f25408863bd8b1eec195c63a3bafae79f7610578182091` |
| year_end | 默认/全期 | 55,348 | `c041e5389a280dce91cda7814cd00d1ae6d0ea841cfdb1db0d29e645cdfd870f` |

### 公开读取、正式数据与回归

真实副本 FastAPI TestClient（无 lifespan）共 60 请求，覆盖 12 完整 family/year 响应和 8 页面投影的 exact/LKG/missing。exact/LKG 返回正确事实与 source/target/freshness，missing 返回结构化 503；builder/publish/queue sentinel 全部 0，临时主库/WAL、sidecar/WAL、Home/yearly/analysis 的 bytes、大小、mtime 不变，missing sidecar 未创建。

正式目录前后 4,180 个文件；集合、bytes SHA-256、大小不变。主库/WAL、正式 Billboard、Home/yearly/analysis 和缓存没有变化。唯一差异是主库 SHM 的只读锁记账 mtime（1789839476138409360 → 1789841980263853232 ns）；其大小仍为 32,768 bytes，内容 SHA-256 相同，详见 `formal-comparison.json`。未回写 mtime，未清除正式快照制造 cold case。

- context / maintenance / 架构定向：**41 passed, 1 warning in 28.40s**。
- Billboard 与 public boundary contract：**75 passed, 1 warning in 16.03s**。
- 完整后端 unit：**1810 passed, 1085 deselected, 1 warning in 73.47s (0:01:13)**，涵盖 ranking/count-duration/year-end/persistent/maintenance/projection。
- 受影响前端 6 文件 / 32 tests；production build 通过，沿用既有 chunk warning。
- 全 backend Ruff、Python compile、docs audit、git diff --check 通过。AGENTS.md / CLAUDE.md 仍一致。

第一次 context 回归 13 passed 后，pytest 清理旧临时目录时出现既有 dir_fd 路径误判，正式路径 guard 拒绝该清理；后续使用本轮独立 basetemp，保留日志，没有修改或关闭 guard。补充最后发布后的 source fence 后，两项旧测试仅捕获 builder 内拒绝，未捕获新增的退出拒绝，首次为 2 failed / 39 passed；测试改为同时断言两处拒绝，随后定向和完整 unit 重跑通过。最终代码重新完成性能和后端回归。

本轮是本地受控重建、语义和公开读取验收；全栈结论仍为 Partial，不作为生产性能证据。

### Git 与停止

本轮增量仅两个产品文件、一个测试文件及本报告/两级文档地图/CHANGELOG 共七个文件；其余开始时 dirty 改动保留。`main` / `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，未 commit、push、部署；完整状态与相对本轮起点的增量在 `git-after.txt`、`worktree-delta.json`、`stage4b.patch`。

指定默认 L2/13:00 失配场景满足本轮门槛，无需实施 4C。可另行进入阶段 5 Search；本任务到此停止。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0bae4-29e6-7f30-8bb4-646b97347767/spotifystats-stage4b/`。临时 DB、全部 sidecar 和 pytest 目录留在 `/tmp/spotifystats-stage4b`，不进入 Git。
