# 阶段 4A：Billboard 单次重建共享事实

> 2026-09-20；基线为 `main` / `faa5e4e4` 加开始时已有的未提交阶段成果。
> 本轮仅调整 Billboard 受控全套重建。未 commit、push、部署或访问生产。

## 实际修改

- `backend/domains/billboard/build_context.py`：一次维护调用持有独立 context。过滤参数固定，现有完整 source/key 在每个实际 builder 前后核验；DB namespace 或 revision 漂移即拒绝该次发布。context 不进入 LRU；退出及异常时清空事实。返回独立 frame/容器副本，避免消费者加列污染其他 family。
- `chart_load_rank.py`：分离完整 ranked weekly facts 与 TopN 后的计数/前缀步骤；聚合、canonicalization、album project 规则、排序器和 running metrics 算法不变。
- `chart_staged_cache.py` / `chart_compute.py`：通过显式参数共享 track/artist summaries、album/artist counts、Record inputs、基础 album/artist power 及 Records。`power_scores` family 的 unfiltered album total override 保持局部，不能污染 `full_data`。
- `chart_year_end_cache.py`：复用完整候选 ranked facts 和按原实体/周顺序排列的年榜输入，六次年度输出共用封面和 display enrichment。年榜按年度窗口重新计算 peak、weeks、No.1、Top5/10 与积分，真实首入榜周从完整 TopN 历史求得；不会消费全历史 running 列，因此维护路径不再构建这套未使用的前缀。普通榜仍生成完整 running 前缀；没有把普通 TopN 当成年榜完整候选。
- `chart_staged_api.py` / `chart_year_end_api.py`：内部 context 显式传递给未包装的 builder，外部 GET 参数、持久 key、builder version 和 response model 不变。
- `backend/services/billboard_snapshot_service.py`：以现有 full-data exact key 串行化同 generation 的全套维护，避免并发调用分占不同 family 并重复建事实。继续调用现有 family 发布入口，保留 exact short-circuit、每行原子发布与失败保留旧行。
- `backend/tests/unit/test_billboard_build_context.py`：生命周期/异常释放、消费者修改隔离、参数及 namespace/revision fence、不同 TopN 前缀隔离、小型 seed 六配置全字段对账、年榜不调用未消费前缀的 sentinel。

没有改动 persistent cache、JobQueue、导入/增量聚合、schema、Search、Records 分析、Home 或前端产品代码。宽表 copy 的基线直接成本很小；保留消费者隔离 copy，没有为追求次数而共享可变视图。

## 数据与测量方法

正式主库仅作为 `mode=ro` SQLite Online Backup 源。副本含 92,908 plays；migration 74 只在这份临时副本运行。所有 builder 连接 query-only/只读；Billboard、yearly、analysis、Home 路径显式指向 `/tmp/spotifystats-stage4a`，外部网络和 JobQueue 被 sentinel 禁止。

开始时保存所有 backend Python 源码，以 import hook 在独立进程运行精确的优化前 dirty-worktree 版本；没有用 HEAD 代替阶段 3C 后的实际基线。默认过滤保持原设置：L2、动态阈值、连续合并、30/20/20、周五 12:00、不含 compilation。

验收 before/after 交错顺序，每次独立进程、新 sidecar、同一不变主库副本；验收样本不启用 cProfile，等待本轮测试和浏览器进程退出后运行。额外保留前后 cProfile、50ms RSS/CPU 时间序列、SQL execute/fetch 调用/类型/耗时/返回行、关键 DataFrame copy/rows、family 时间和 publish 计数。嵌套 stage 耗时不能相加；SQL 清单包括结束时读取 sidecar 校验的两条查询。只有三次独立样本，报告原始值和 median，不声称稳定 P95 或生产 SLA。

## 完整字段与投影等价

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

## 性能结果

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

## 浏览器与 public-readonly

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

## 验证与正式数据

- 新 context/维护/架构定向 **33 passed**（包含 context 的 11 个用例）。
- 完整后端 unit **1,802 passed / 1,085 deselected**；Billboard 相关 ranking、duration、year-end、persistent、maintenance 均在内。
- Billboard API/projection/counting/attribution/detail/year-end 与 public boundary 定向 contract **75 passed**。
- 受影响前端 **32 passed / 6 文件**；production build 通过，保留现有大 chunk warning。
- 首轮 seed 缺 L3 归属、空结果既有错误，以及两轮模块行数门禁失败均保留日志。seed L3 在独立测试副本准备，模块组织调整到既有阈值内；没有降低覆盖、放宽预算或改测试阈值。
- Ruff、Python compile、docs audit、git diff --check 通过（最终日志随证据保存）。没有运行默认完整全栈门禁，**全栈结论 Partial**。

正式目录前后 **4,180 个文件**，集合、bytes SHA-256、大小全部相同。主库、WAL、Billboard sidecar、Home/yearly、封面及其他缓存的 mtime 相同；正式 analysis sidecar 仍未被创建。唯一差异是 `spotify_stats.db-shm` 的 mtime 随只读 Online Backup 锁记账变化，32,768 bytes 及 SHA-256 完全相同；未回写 mtime。完整 DB/WAL 不变同时证明原始播放、身份/会员关系、revision、settings 和任务表未被改写。

对比开始时逐文件工作区清单：仅新增/修改本轮 **13 个文件**（8 产品、1 测试、4 文档），无文件删除；未涉及其他旧阶段 hunk。Git 仍在 `main`，HEAD=`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，保持 dirty，无 commit/push/deploy。完整增量路径在 `worktree-delta.json`。

## 剩余热点与停止

主要性能目标（下降 ≥40%、RSS ≤768MiB）与每 key singleflight、完整字段等价、公开只读边界通过；SQL 总调用增加 5.1% 的权衡已单列。完整全栈/生产性能没有在本轮验收。

最终 profile 的最大已标注计算热点仍是普通榜 running metrics **15.842s**，其次 Records **14.066s**；这是带 profiler 的定位值，不能混入上方验收统计。前后 profile 分别 33.165s / 61.958s，机器负载不同，不用其绝对比值判断性能。未使用的年榜前缀已消除，普通榜必需的完整前缀仍保留；source fence 与 JSON 发布也继续有成本。

**目前不需要以持久 checkpoint、新 schema 或全局共享事实作为进入下一阶段的前置条件。可以由用户决定进入阶段 5 Search；阶段 4B 不在本轮追加。** 若未来要求失配场景也达到默认 RSS/耗时目标，应单独设计受预算约束的 raw 重建或 checkpoint，并继续复用既有 aggregation semantic proof/affected-week 维护；本轮未实施这些内容。

阶段 4A 在此停止。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage4a/`。原始临时数据库、sidecar、pytest 工作目录留在 `/tmp/spotifystats-stage4a`，不纳入 Git 或交付目录。
