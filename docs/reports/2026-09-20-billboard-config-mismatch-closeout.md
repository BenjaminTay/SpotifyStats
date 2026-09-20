# 阶段 4B：Billboard 配置失配重建收口

> 2026-09-20；基线为当前 main / faa5e4e4 及开始时的未提交工作区，包含阶段 4A。
> 本地指定 L2 / 13:00 场景验收通过；未 commit、push 或部署。

## 结论与修改原因

4A 已自然消除失配路径的重复 raw 加载：本轮修改前主轨、artist、完整 ranked builder 各只有一次，三次 wall 中位数 **17.540s**。但最大采样 RSS **1102.00MiB**，超过 768MiB，因此进入分支 B。

局部修改后，三次 wall 中位数 **19.422s ≤60s**，最大采样 RSS **681.64MiB ≤768MiB**；四并发峰值 **685.42MiB**，完整事实 builder 1 次，12 个 key 各发布一次。此轮改善的是内存，失配 wall/CPU 中位数没有下降；不将此前 100.031s 的历史单样本当作本轮配对基线。

指定场景无需阶段 4C。建议下一步进入阶段 5 Search，但本任务在 4B 报告后停止，不实施 Search。

## 实现范围

- `build_context.py`：沿用 4A 的完整 ranked facts 与 normal/annual 共享。仅 invocation raw fallback 绕过旧 loader 的进程级 LRU；在已有时间线重建、阈值处理、canonical artist/credit 完成后，给排名消费者独立复制必要列及独立 weighted frame。所有行、顺序、计次/时长权重、identity 和日期输入保留。
- `chart_load_rank.py`：raw 路径先完成主轨/专辑排名与未受发行日限制的 album total，再释放不再消费的 weighted/listening attrs 和临时宽帧；后续 summary/年榜仅保留计次与覆盖日期列，随后加载独立 artist raw。聚合兼容分支的加载与计算顺序保留；未改变 ranker、source credit、project membership 或时间切片算法。
- context 成功退出时补充完整 source 检查，覆盖最后一次 snapshot publish 后的来源漂移；异常和检查失败均通过 finally 清空事实。此前每个 builder 前后、发布前的完整 source/key 检查继续保留。不使用 mtime、MAX(ts) 或行数替代 revision。
- 测试新增 raw LRU 禁入、单次加载、消费者修改隔离、弱引用释放、成功/异常清理、13:00 双轨跨周边界及最后发布后的 namespace/revision 漂移；seed 全字段对账扩展到 13:00、L3/13:00 和 compilation/13:00。

产品改动限两个 Billboard 文件；没有新增 schema、持久 checkpoint、聚合表或全局事实缓存。12 条逐行 atomic publish、失败保留旧行、request/source key 和 builder version 均保持原合同。

## 测量方法与原始样本

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

### 归因与发布

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

## 完整语义对账

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

### 最终 sidecar

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

## 公开读取、正式数据与回归

真实副本 FastAPI TestClient（无 lifespan）共 60 请求，覆盖 12 完整 family/year 响应和 8 页面投影的 exact/LKG/missing。exact/LKG 返回正确事实与 source/target/freshness，missing 返回结构化 503；builder/publish/queue sentinel 全部 0，临时主库/WAL、sidecar/WAL、Home/yearly/analysis 的 bytes、大小、mtime 不变，missing sidecar 未创建。

正式目录前后 4,180 个文件；集合、bytes SHA-256、大小不变。主库/WAL、正式 Billboard、Home/yearly/analysis 和缓存没有变化。唯一差异是主库 SHM 的只读锁记账 mtime（1789839476138409360 → 1789841980263853232 ns）；其大小仍为 32,768 bytes，内容 SHA-256 相同，详见 `formal-comparison.json`。未回写 mtime，未清除正式快照制造 cold case。

- context / maintenance / 架构定向：**41 passed, 1 warning in 28.40s**。
- Billboard 与 public boundary contract：**75 passed, 1 warning in 16.03s**。
- 完整后端 unit：**1810 passed, 1085 deselected, 1 warning in 73.47s (0:01:13)**，涵盖 ranking/count-duration/year-end/persistent/maintenance/projection。
- 受影响前端 6 文件 / 32 tests；production build 通过，沿用既有 chunk warning。
- 全 backend Ruff、Python compile、docs audit、git diff --check 通过。AGENTS.md / CLAUDE.md 仍一致。

第一次 context 回归 13 passed 后，pytest 清理旧临时目录时出现既有 dir_fd 路径误判，正式路径 guard 拒绝该清理；后续使用本轮独立 basetemp，保留日志，没有修改或关闭 guard。补充最后发布后的 source fence 后，两项旧测试仅捕获 builder 内拒绝，未捕获新增的退出拒绝，首次为 2 failed / 39 passed；测试改为同时断言两处拒绝，随后定向和完整 unit 重跑通过。最终代码重新完成性能和后端回归。

本轮是本地受控重建、语义和公开读取验收；全栈结论仍为 Partial，不作为生产性能证据。

## Git 与停止

本轮增量仅两个产品文件、一个测试文件及本报告/两级文档地图/CHANGELOG 共七个文件；其余开始时 dirty 改动保留。`main` / `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，未 commit、push、部署；完整状态与相对本轮起点的增量在 `git-after.txt`、`worktree-delta.json`、`stage4b.patch`。

指定默认 L2/13:00 失配场景满足本轮门槛，无需实施 4C。可另行进入阶段 5 Search；本任务到此停止。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0bae4-29e6-7f30-8bb4-646b97347767/spotifystats-stage4b/`。临时 DB、全部 sidecar 和 pytest 目录留在 `/tmp/spotifystats-stage4b`，不进入 Git。
