# 榜单对决个人播放统计 S0–S4 性能与正确性验收

创建：2026-10-08；最后核验：2026-10-09。问题：`SS-2026-10-08-002`。对应[实施规划](../plans/2026-10-08-versus-personal-statistics-performance-plan.md)。关联 `SS-2026-10-08-001` 的资源风险，本报告不宣称整站 OOM 或其他详情冷路径已解决。

状态：**d5ba3094 本地S4、正式CI、三模式及部署通过；S5生产专项Partial，首次公开客户端仍有两项基础性能失败**。d2c4afce历史三项生产失败及各版本证据保留。d5ba3094首次公开28样本数值及计分正确，26项达全部性能门槛、全部个人指标均≤3秒；四专辑2.191秒、两艺人2.283秒超过基础2秒。第11节记录该版本生产；第12节记录新增计次投影工作树，不能沿用d5ba3094完整门禁或以热重跑覆盖首次失败。

## 1. 数据、版本与测量合同

源为生产 SQLite Online Backup：`output/versus-personal-acceptance/source.db`，444,588,032 字节、94,760 条播放、schema89。源文件静态且无 WAL sidecar；读取使用 `mode=ro&immutable=1`，只在明确派生副本执行迁移和私有排名维护。性能运行副本为 `output/versus-personal-acceptance/perf-run/main.db`；最终维护及发布对账副本为 `output/versus-personal-acceptance/maintenance-run2/main.db`，各使用独立 `analysis.db`。

测量平台为 macOS 26.6.2 / arm64、10 个逻辑 CPU、Python 3.9.6。两份主报告记录的 HEAD 为 `34f22db94ecc7766608f513908000792a56c7b1b`，同时保存当时 working tree 状态；优化代码包含未提交改动，**该 HEAD 不能单独代表最终交付版本**。基础统计合同为 `versus_personal_v1`，共享排名 builder 为 `entity_rank_context_v2`。

实际 fresh/warm 参数：`min_ms=30000`、`music_only=true`、`merge_enabled=true`、`max_merge_gap_minutes=5`、`dynamic_threshold=true`、`merge_level=2`、`include_compilations=false`。基础统计为 lifetime；排名读取 lifetime、近六个月、近四周，滚动窗口仍按现有有效计次覆盖时间定位。

该参数指纹为 `d0bed118f37835ce646c7a582be102938600954d1e6b1076deb9d317eb415ce2`；源 revision 为 `bb7cb36811f58d12c3f285e9c3861a8c777c70a4c00b5dcb1b81062b4a9feb2e`。全部其他矩阵参数和对应 revision 保存在原始 JSON 中。

四对象队列分别为：歌曲 ID 149、1493、157、4451；专辑 Midnights、THE TORTURED POETS DEPARTMENT、GUTS、光良「回憶裡的瘋狂」巡迴演唱會（均带明确艺人）；艺人 Taylor Swift、Michael Wong、Olivia Rodrigo、Stefanie Sun。两对象场景取队列前两项。有效署名盘点中 Taylor Swift 和 Michael Wong 分别覆盖 62、12 条合作曲，包含规划要求的合作署名场景。

原始证据仅保留在 ignored 输出，不提交数据库、完整响应或私有数据：

| 文件 | 已验证范围 |
| --- | --- |
| `output/versus-personal-acceptance/performance.json` | 44 阶段：准备、旧完整详情并发基线、fresh5、warm21、20 组切换及初轮 oracle |
| `output/versus-personal-acceptance/maintenance-resources-final.json` | 优化后真实维护 handler 四配置串行、资源与源事实守恒 |
| `output/versus-personal-acceptance/published-oracle-final.json` | 优化后实际发布完整名次 map、真实排名 API、基础指标的独立完整对账 |

三个 JSON 最终 `pass=true`。第一份初轮排名 oracle 只比较新排名聚合与完整公开榜单行；第三份已进一步核验**实际 builder 发布的完整 payload**，补齐这一证据边界。

## 2. S0 基线与 S1/S2 实现核对

原请求链在榜单响应成功后逐对象请求完整详情统计，不同对象重复运行全库排名、时长切片和展示序列化。新路径提前独立读取批量基础指标与共享精确排名。基础 service 合并所有目标成员范围，只读取目标 raw source 事件及逻辑重建所需左邻；次数与收听时长保留双轨，专辑按 project/canonical song 归属，艺人按有效署名和 canonical identity 去重。

目标范围按全库一致的 `ts → source_fingerprint → play_id` 次序处理。同时间戳邻居使用精确比较；右邻、跨午夜及轻微重叠 fixture 证明当前区间重建需要左邻，不会由右邻截断目标时长。艺人解析复用本批有效署名，基础时长投影省去对决不消费的逐小时 ISO 字符串与趋势行。缓存上限 128 条，仅保留小聚合响应；source revision、过滤指纹和规范化实体集合共同约束缓存与 singleflight。

排名私有 builder 使用本次连接上的 uncached 窄列全库帧，发布完整三类三期间名次 map。公开基础/排名请求不构建、不发布、不排队；维护结束释放本次帧，不清空其他消费者已有缓存。

旧基线通过真实 FastAPI 路由的 TestClient，用 `ThreadPoolExecutor` 同时启动 2/4 个完整详情请求；将 `_is_primary_connection` 置为 false，绕过已有艺人详情 publication 与实体响应缓存，专门测量**旧完整详情重算成本**。它不是当前生产实时 HTTP 耗时，也不用于声称生产提速倍率。

| 种类 | 2 对象并发 wall | 4 对象并发 wall | 2 对象新增峰值 RSS | 4 对象新增峰值 RSS |
| --- | ---: | ---: | ---: | ---: |
| 歌曲 | 10,127.8ms | 24,433.6ms | 1,052.50MiB | 1,589.98MiB |
| 专辑 | 13,930.2ms | 27,432.0ms | 1,545.97MiB | 2,284.73MiB |
| 艺人 | 14,576.3ms | 28,463.5ms | 1,063.28MiB | 1,760.22MiB |

前期四艺人单次 preflight 曾超过 1.5s 门槛；相关失败样本保留在同目录 `preflight*.json`。最终低干扰 fresh5 测量在署名复用、紧凑时长投影和邻居 SQL 优化完成后进行，没有放宽阈值或用热样本替代 fresh 样本。

## 3. S4 真实副本 API 性能

传输为进程内 FastAPI TestClient，运行真实 router，不执行 lifespan/startup warmup，无 reload 和外部网络。每组 fresh 有 5 个独立 Python 进程，排名发布预先存在；每次记录真实参数、Request ID、响应大小、Server-Timing 和进程资源。每个同进程 case 首次请求之后再采 21 个观测，以最近秩法计算 P95。完整每次观测见 JSON，下面报告 fresh 最大值和 warm P95；5 个 fresh 样本不称 fresh P95。

单位为 ms；基础 fresh 门槛歌曲/专辑 ≤1,000、艺人 ≤1,500；排名 fresh ≤500；基础与排名 warm P95 各 ≤500。

| 种类 | 对象数 | fresh5 基础最大 | fresh5 排名最大 | warm21 基础 P95 | warm21 排名 P95 | 结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 歌曲 | 2 | 180.5 | 19.5 | 13.2 | 14.7 | PASS |
| 歌曲 | 4 | 122.0 | 25.4 | 15.7 | 17.0 | PASS |
| 专辑 | 2 | 305.9 | 114.6 | 108.5 | 115.5 | PASS |
| 专辑 | 4 | 473.0 | 134.1 | 122.0 | 117.5 | PASS |
| 艺人 | 2 | 1,062.7 | 286.9 | 306.5 | 308.8 | PASS |
| 艺人 | 4 | 1,252.4 | 340.1 | 252.0 | 317.9 | PASS |

全部请求为 200。公开路径 builder、publish、enqueue 调用数均为 0；新基础/排名读取后全库一般播放和艺人帧缓存条数均为 0。21 次相同上下文命中基础小响应缓存；20 组不同四对象组合保留 20 个有界条目，队列重排复用实体集合。

以上证明本地后端 API 达标，尚未测量“添加对象到基础行可见/总分完成”的浏览器时间，不能把表中 handler 时间代替用户可见时间或 HTTPS 延迟。

## 4. 读取和维护资源

资源由 psutil 每 20ms 采样，峰值与 GC 后稳态分列；单位统一为 MiB（字节除以 2²⁰）。四对象读取峰值预算相对该测量阶段 idle ≤256MiB；20 组不同组合切换后的稳态预算相对切换前 idle ≤128MiB。

| 种类 | 四对象 fresh/warm 新增峰值最大 | 20 组切换新增稳态 | 阈值结果 |
| --- | ---: | ---: | --- |
| 歌曲 | 22.84MiB | 4.38MiB | PASS |
| 专辑 | 51.80MiB | 7.34MiB | PASS |
| 艺人 | 176.30MiB | 89.72MiB | PASS |

切换为 20 个不同实体组合，并非重复同一队列 20 次；基础与排名均请求并验证 200。没有恢复按对象复制全库 DataFrame 的路径。

### 4.1 真实维护 handler 四组合串行

最终资源探针通过 `handle_rebuild(Job.create(...params_json...))` 实际维护入口，串行运行 L2/L3 × dynamic/fixed 四组合，四次均新发布且 exact。进程首次 idle 为 **179.42MiB**。预算输入 available memory 为 1,348MiB，预留 25% 后允许**新增 RSS ≤1,011MiB**；这是规划准入值下的本地副本比较，未冒充生产机器实际重建测量。

| 配置 | 该轮 idle RSS | absolute peak RSS | 相对进程初始 idle 新增峰值 | GC 后 settled RSS | 相对初始 idle 新增稳态 |
| --- | ---: | ---: | ---: | ---: | ---: |
| L2 dynamic | 180.56 | 597.72 | 418.30 | 493.78 | 314.36 |
| L2 fixed | 493.53 | 599.22 | 419.80 | 516.34 | 336.92 |
| L3 dynamic | 516.09 | 641.66 | 462.23 | 570.23 | 390.81 |
| L3 fixed | 569.98 | 658.70 | 479.28 | 595.08 | 415.66 |

最大新增峰值 **479.28MiB <1,011MiB，PASS**。比较的是对初始 idle 的新增占用，不把 absolute peak 与 available memory 混用。每轮一般/艺人全库帧 LRU 条目均为 0。

最终 GC 后仍有 **415.66MiB 新增进程驻留**。这个观察与 Python/数据处理 allocator 保留内存相符；探针未证明其全部来自 allocator，也未宣称释放帧即可使 RSS 回到初始值。四轮没有活跃全库帧缓存累计，生产维护仍须遵守单实例串行及与 Search/Billboard 重型任务排他。

### 4.2 保留的旧诊断路径

`performance.json` 准备阶段曾直接连续调用 `ensure` 四次，旧 cached loader 累积全库帧，absolute peak 为 1,095.70 →1,572.89 →1,596.02 →1,621.38MiB。该路径没有真实 handler/CLI 的逐轮清理，**不能据此判定当时生产 worker 同样累积**。原始数据保留；最终准入使用上节真实入口与 uncached builder 的重测。不能以全局 invalidate 清掉其他消费者有效结果来获得资源 Pass。

## 5. 正确性、生命周期边缘与源事实保护

优化后最终对账覆盖 L2/L3、dynamic/fixed、三种实体、基础及 API 的 2/3/4 对象，并对专辑 include_compilations false/true 运行实际相关组合。

| 对账集合 | 数量 | 独立参照 | 差异 | 结果 |
| --- | ---: | --- | ---: | --- |
| 基础指标批次 | 48 | 全库双轨事件/区间、既有 summary/daily 指标、独立专辑 project 解析 | 0 | PASS |
| 实际发布完整名次 map | 48 | 全库 `chart_rows` 完整序列，含 lifetime/近六个月/近四周 | 0 | PASS |
| 真实批量排名 API | 48 | 本次实际发布完整 map，按稳定身份逐实体核对 | 0 | PASS |

基础逐项核对总次数、总小时、活跃天数、日均次数、日均小时、单天最多播放。完整排名未截成 Top 100/250；保留次数、时长和稳定键排序。生产副本本次选中实体的 lifetime 边缘差异为空。

独立 fixture 另证明旧完整详情按计次合格日期裁剪 lifetime 时长会丢失覆盖两端未达计次阈值的收听：旧值 60,000ms /1 个活跃日，新双轨 oracle 为 100,000ms /3 个活跃日。新接口按 R2/R4.1 保留这些区间；不改变计次阈值、不按 UI raw coverage 强裁时长，旧详情 API 兼容边界单独保留。正常副本等价与这项必要边缘修正分列，未隐藏差异。

三份最终证据的 `protected_source_unchanged`、`protected_owned_unchanged` 均为 true。对本次可达的 19 张源/身份/归属/治理表逐行序列化校验 SHA-256 和行数，源前后及派生副本均相同；最终发布 oracle 完成后另复查一次。代表规模为 plays 94,760、tracks 10,026、track_artists 10,496、albums 4,030、artists 1,907、album_projects 2,940、album_project_tracks 7,921、L3 归属 6,642、credit overrides 35。缺失表不会伪报 0 或声称全库审核；完整表集合与 digest 见 JSON。

只读契约测试还覆盖 unknown 身份为 unavailable/null、已知无播放为真实 0、identity 解析中源漂移拒绝、metadata tracking 缺失/源漂移为结构化 503、同批 SQL 无 DDL/DML，以及缓存重排、响应不可篡改、128 条上限和同上下文四线程只做一次 union 读取。

## 6. 本地专项检查与复现

本报告直接验证的后端专项为：

```bash
.venv/bin/pytest backend/tests/unit/test_versus_personal_stats.py backend/tests/contract/test_versus_personal_stats_contract.py -q
.venv/bin/mypy backend/services/versus_personal_stats_service.py --follow-imports=skip
.venv/bin/ruff check backend/services/versus_personal_stats_service.py backend/services/versus_personal_context.py backend/tests/unit/test_versus_personal_stats.py backend/tests/contract/test_versus_personal_stats_contract.py scripts/versus_personal_performance_probe.py
```

结果为 **59 passed**、目标 service mypy 无错误、Ruff 通过，相关 diff 检查及探针 py_compile/format 检查通过。mypy 范围明确使用 `--follow-imports=skip`，不是全项目类型检查结论。专项不能替代当前最终版本的全量后端、前端、hooks 或默认完整全栈。

完整 API 性能/资源复现（必须选尚不存在 `main.db` 的新工作目录）：

```bash
.venv/bin/python scripts/versus_personal_performance_probe.py --database output/versus-personal-acceptance/source.db --work-dir output/versus-personal-acceptance/new-perf-run --json-output output/versus-personal-acceptance/new-performance.json
.venv/bin/python scripts/versus_personal_performance_probe.py --database output/versus-personal-acceptance/source.db --work-dir output/versus-personal-acceptance/new-maintenance-run --json-output output/versus-personal-acceptance/new-maintenance.json --maintenance-only --available-memory-mb 1348
```

当前脚本准备阶段已走真实 handler，最终 oracle 已直接核对实际发布 map 和批量排名 API；既有 `performance.json` 保留原阶段证据，补齐部分以两份 final JSON 为准。源文件必须是明确静态 Online Backup，不能拿生产活库套用 immutable。

文档审计：本报告创建后执行 `python3 scripts/docs_audit.py`，158 份当前 Markdown 检查 PASS；`--include-archive` 检查 238 份 Markdown 同样 PASS。文档地图与开发状态由集成负责人同步。

## 7. 2026-10-09 浏览器收口与后续验收（PARTIAL）

2026-10-09 集成补记：真实浏览器首轮 Chromium /360 /专辑从2对象连续重排并加到4对象时，基础可见6,042ms、排名5,407ms，未达到冻结门槛；相关个人API的 identity 阶段4,859ms、排名总处理5,149ms。请求轨迹确认多个发行周期比较同时重新生成全库周排名，构成CPU竞争。失败证据保存于 `output/playwright/versus-personal/before-release-optimization.json` 和相应截图。前端已增加周期的实体集合key、取消与显示重映射，并在个人请求结束后启动；后端准备链正在收口。不能用延迟探针至idle、只测缓存或调整阈值将本轮写成Pass。

### 7.1 周期冷路径定位与计次语义对账

`releasecycle-compare-profile.json` 只读冷样本总耗时 **3,523.32ms**，其中 `load_billboard_raw` 为 **3,261.34ms /92.56%**，该阶段 CPU 时间为 2,983.15ms。已有周排名读取仅39.63ms，主要负担转移到 raw 冷加载。这个比例是整个 raw loader 的占比，不能把全部3,261ms都归给时长计算；源码核对确认它额外构建全库独立收听区间、第二遍艺人规范化及加权帧，而周期比较实际不消费这些时长帧。现代 attrs wrapper 的 deepcopy 返回自身引用，微型验证也未见嵌套帧复制，因此不把未证实的深拷贝作为确定根因。

周期准备改为一个规范化上下文共享紧凑的全局 daily count tuple，目标艺人使用 S1 范围读取并设置 `include_duration=false`。保留旧周期的 **primary artist、canonical 名称、source album 名称及 source_album 合并边界**，不套用个人艺人的有效署名 fan-out；周期的 total_ms 仍是计次合格事件的 ms_played 求和。短碎片在合并前保留，fixed/dynamic 与 merge 开关沿用原规则；全局重建后按 counted_at 的 Billboard 周及其年份筛选，保持周起始日/小时和跨年边界。

`releasecycle-count-only-oracle.json` 报告4组参数、每组4个年份范围，共 **16 种组合全部 exact**：默认参数、fixed+23时、fixed+周一8时、关闭合并+23时。全局/目标计次分别为67,881/3,846、67,900/3,880、67,900/3,819、67,940/3,878，源事实未变。`production-facts-before.json` 与 `performance.json` 的源事实记录实际均为19张表，本次只读比对逐表 rows/digest **0差异**；这些是计次与源保护证据，不能扩成完整周期所有指标/排名均已等价。

周期周排名现在只读匹配的 **exact 已发布 weekly**，不再同步冷建周榜。它遵守完整结束周合同，覆盖边缘开放周不产榜单名次，但其播放仍保留在周期计次和日基线；这是相对旧边缘排名的必要修正，**不声称原 edge rank 全相等**。前述个人排名48组完整对账也不能替代本项周期边缘对账。

`releasecycle-count-only-profile.json` 新冷单样本总耗时1,966.58ms，warm605.59ms；另一个只读重叠探针 `releasecycle-overlap-readonly.json` 在冷2对象周期与4对象个人请求同跑时，基础671.58ms、排名406.75ms、周期1,987.63ms，全局count只构建一次且源未变。这些单样本有助定位，不能替代真实浏览器门槛或最终版本的fresh5矩阵。

### 7.2 三次真实冷浏览器仍未达标

以下均为 Chromium、360×800、专辑2→4对象的真实API与浏览器记录。冻结基础可见门槛为 **≤1,500ms**，三次报告状态均为 FAIL，失败记录保留：

| 证据文件（`output/playwright/versus-personal/`） | 4对象基础可见 | 排名可见 | 全部个人指标可见 | 结论 |
| --- | ---: | ---: | ---: | --- |
| `after-release-preflight.json` | 6,490.45ms | 5,738.46ms | 6,490.45ms | FAIL |
| `after-release-profile-preflight.json` | 2,677.16ms | 1,892.14ms | 2,677.16ms | FAIL |
| `after-selection-settle-preflight.json` | 1,575.86ms | 932.06ms | 1,575.86ms | FAIL；基础仍超75.86ms |

最后一轮加入 **220ms 对象集合稳定窗口**；浏览器计时从点击添加前开始，该窗口已计入1,575.86ms，没有从预算中扣除。该JSON的11条请求轨迹中9条有完整duration，**3对象请求为0**，重排新增个人请求为0，页面值与真实响应一致、横向溢出0、console空。对应4对象基础API为1,162.06ms，其中identity557.211ms；排名API594.63ms。这些正确性与请求去重观察不能抵销用户可见门槛失败。

身份解析复用后的360专辑冷预检已达标：`after-identity-cache-preflight.json` 两对象887.15ms、四对象1,057.06ms，排名最大802.20ms。这一局部通过仍不能替代完整矩阵。10月8日的隔离API Pass按其版本和测量范围保留，不能自动覆盖这次补修后的整体S4。当前整体继续 **PARTIAL**，不以已有热cache、等待后台idle、缩小计时起点或放宽阈值收口。

### 7.3 最小身份缓存回归与独立 RSS 复核

基础/排名共用最多8条不可变 `SelectedEntity` tuple 的身份缓存，按数据库 lineage（device/inode）、source revision、全部7项规范化过滤条件、种类及排序后的请求实体集合区分，并通过 singleflight 共享同上下文工作。缓存不保留frame或连接；hit/miss两条路径均检查source fence，漂移仍返回结构化503，没有跳过一致性检查。

集成负责人报告两批专项分别 **103 passed、96 passed**，其中6项重叠，合计 **193个独立回归用例通过**，不重复记为199项。本轮没有为补写报告重跑CPU测试。周期边缘回归 `test_release_cycle_comparison_data.py::test_coverage_edge_retains_playback_but_only_complete_week_ranks` 明确验证：selected保留开放边缘周计次，daily总和等于旧raw全部事件数，weekly_artist/weekly_album仅有严格早于开放边缘的周。其周排名oracle以 `keep_complete_billboard_weeks` 过滤旧输入后比较，继续不宣称旧开放周名次等价。

三份 `output/versus-personal-acceptance/identity-cache-switch-{track,album,artist}.json` 已逐项核对。每类初次基础/排名2请求，再对20个不同四对象队列各请求基础与排名，共 **42个HTTP全部200**；三类合计126请求。每类19张源保护表守恒，builder/publish/enqueue均0，一般及艺人全库播放帧缓存均0；身份缓存最终size=8/maxsize=8、`identity_cache_only_immutable_scalars=true`。

下面是**20组切换相对切换前idle**的RSS增量，不混用首次请求峰值或进程absolute RSS：

| 种类 | 切换新增峰值 RSS | 切换后新增稳态 RSS | 256MiB峰值 /128MiB稳态预算 |
| --- | ---: | ---: | --- |
| 歌曲 | 14.969MiB | 6.375MiB | PASS |
| 专辑 | 26.203MiB | 17.391MiB | PASS |
| 艺人 | 93.563MiB | 81.375MiB | PASS |

三份证据均记录 `external_guard_running=true`、`latency_claim=false`。因此这轮只用于RSS、缓存容量、请求结果和源守恒复核，**其耗时不作为性能Pass**。最终浏览器、低干扰耗时、完整全栈与生产验收仍待完成。

### 7.4 完整浏览器矩阵失败与艺人冗余映射补修

`matrix-before-primary-projection.json` 保留补修前的45个场景、90个两/四对象样本（Chromium/Firefox/WebKit ×360/390/430/768/1280 ×歌曲/专辑/艺人）。89个样本达标，仅首次Chromium360艺人四对象基础可见 **2,034.72ms**，超2,000ms门槛34.72ms；矩阵整体为 **FAIL**。歌曲最大609.36ms、专辑781.13ms、艺人2,034.72ms；三类重排新增个人请求最大0、横向溢出最大0。Firefox/WebKit恢复运行仅修复探针decoded-header转发，原Chromium失败未以热重跑替换。该失败四对象基础HTTP为1,690.72ms，其中identity360.015ms、目标SQL719.075ms、timeline352.431ms、attribution205.266ms。

最小只读profile确认艺人基础路径在 `_load_target_timeline` 先对主艺人列映射两次，随后 `_artist_frames` 丢弃这些列并按已解析有效曲目署名重建归属。`artist4-primary-projection-before.json` 的两次映射分别处理33,617条计次与46,733条收听区间，共88.20ms。补修新增 keyword-only `canonicalize_artists=True`，只在艺人基础的计时/普通两条分支传False；歌曲、专辑和发行周期保留默认True，没有改SQL、过滤阈值、双轨时长或缓存合同。

`artist4-primary-projection-after.json` 同线程cProfile为1,128.58ms，目标SQL375.47ms、timeline250.13ms、attribution148.34ms，primary映射调用0，19张保护表不变、公开builder/publish/enqueue均0。它含profile开销，**不作为HTTP或浏览器Pass**。另一个fresh实际HTTP诊断为1,000.87ms（`artist-primary-projection-oracle.json`），补修前同类单样本1,109.56ms；timeline分别228.55ms与316.15ms。这些单样本仅支持热点判断，不替代最终fresh5或冷浏览器验收。

补修验证范围如下：

- 四个独立fixture组合覆盖canonical alias、featured署名、人工remove/add与即时/已解析有效credits；主署名原始alias实际投影到canonical，再分别比较跳过前后的事件/时长行及全部基础指标。六个合同用例覆盖三类 ×计时/普通路径，确认只有艺人基础跳过映射。
- 真实生产副本 **24组艺人基础对账全部通过**：L2/L3 ×fixed/dynamic ×include_compilations false/true ×2/3/4对象。独立全库有效署名loader提供六项指标oracle，24个真实HTTP响应逐项相等；源副本与派生副本各19张保护表均守恒，primary映射0、公开builder/publish/enqueue0。这里只复核本次改变的艺人基础路径；保留第6节原48基础/48已发布完整名次map/48排名API证据，没有重算未变的排名builder或旧完整详情基线。
- 原193个独立回归，加新增10项及publication/deployment原有26项，单次运行 **229 passed，25.23s**。范围为个人identity/stats/API、rank context/publication/deployment、release cycle/date precision、Billboard过滤默认与remaining JSON响应合同。Ruff检查和格式检查通过；stats service的mypy `--follow-imports=skip` 通过，该结果不扩大为全项目mypy通过。

代码补修已稳定，最终API与冷浏览器复测结果见下节；完整全栈、CI与生产仍待独立完成，整体继续 **PARTIAL**。

### 7.5 最终版本隔离 API fresh5 /warm21 复测

在最终冷浏览器退出后、集成负责人暂停其他CPU测试及文件/HEAD修改期间，`final-api-retest-driver.py --run` 顺序执行既有探针的 **36个worker进程**：三类 ×2/4对象各5个独立fresh，再每组1个warm（每endpoint初次请求后21次观察）。复用 `perf-run` 数据库与inventory，没有重建准备、旧完整详情基线、维护job或未改变的排名oracle。

`output/versus-personal-acceptance/final-api-run/report.json` 最终 `pass=true`，130项门槛全部通过，实际运行134.09s。fresh共60个真实HTTP；warm含6组初次各2请求与252个计入P95的HTTP，共264请求。既有四对象warm worker还执行三类 ×20个不同四对象队列 ×基础/排名，共120请求；总 **444个HTTP全部200**。fresh每组确有5个独立进程，warm每组每endpoint确有21个后续观察，没有用热样本替代fresh。

| 种类 | 对象 | 基础fresh5逐次耗时（ms） | 基础fresh最大 | 排名fresh最大 | 基础warm P95 | 排名warm P95 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 歌曲 | 2 | 118.345 /86.076 /84.873 /84.201 /86.989 | 118.345 | 17.339 | 11.896 | 13.247 |
| 歌曲 | 4 | 119.207 /110.820 /109.582 /107.832 /111.387 | 119.207 | 17.129 | 11.745 | 13.307 |
| 专辑 | 2 | 284.422 /266.707 /268.652 /269.702 /270.436 | 284.422 | 17.257 | 16.221 | 14.410 |
| 专辑 | 4 | 362.961 /364.530 /357.078 /361.389 /360.854 | 364.530 | 17.226 | 11.802 | 13.299 |
| 艺人 | 2 | 789.493 /752.994 /807.693 /753.226 /758.119 | 807.693 | 17.532 | 11.654 | 12.876 |
| 艺人 | 4 | 939.371 /928.113 /935.402 /931.141 /929.233 | 939.371 | 17.619 | 11.629 | 13.157 |

原阈值不变：歌曲/专辑基础fresh每次≤1,000ms、艺人≤1,500ms、排名每次≤500ms、warm P95≤500ms；5个fresh只逐次判断，不称fresh P95。各排名fresh5完整值、原始请求耗时及Server-Timing保存在36份worker JSON与日志中。

| 种类 | 四对象fresh/warm新增峰值最大 | 20组切换新增峰值 | 切换后新增稳态 | 256MiB峰值 /128MiB稳态预算 |
| --- | ---: | ---: | ---: | --- |
| 歌曲 | 23.047MiB | 12.844MiB | 4.234MiB | PASS |
| 专辑 | 51.453MiB | 21.375MiB | 12.594MiB | PASS |
| 艺人 | 172.234MiB | 63.562MiB | 32.016MiB | PASS |

源与派生副本各19张保护表的前后digest/rows相等，两副本彼此也一致；公开builder/publish/enqueue均0，每个进程结束时一般/艺人全库播放帧缓存均0。实际filters、selection与前文冻结参数相同。

版本fence保存测量前后相同的HEAD `34f22db94ecc7766608f513908000792a56c7b1b` 以及8个直接测量源码文件的SHA256；该HEAD仍不能代表未提交的优化。stats service hash为 `8e0aafce808bb3e8804192c06488bbb0fa1f0bbadb624a985b769251e7ff449d`，identity context为 `9f268f325766cd7951e17901dd6eb14dbfd45e21bb039a60d2fde98948204d8b`。完整8文件hash保存于JSON的 `version_before/version_after`，`version_unchanged=true`，不把这个局部版本fence扩大为全仓库校验。

### 7.6 最终真实浏览器矩阵与额外冷顺序复测

`output/playwright/versus-personal/matrix-final.json` 为 **45场景/90样本全部PASS**，覆盖三种浏览器 ×五个视口 ×三类 ×两/四对象。另一次全新冷后端、全新Chromium360按歌曲→专辑→艺人原cold顺序执行，`matrix-final-cold-sequence.json` 的3场景/6样本也全部PASS，避免只用跨场景已热缓存解释艺人结果。

| 种类 | 完整矩阵基础可见最大 | 完整矩阵排名可见最大 | 额外冷顺序基础可见最大 | 额外冷顺序排名可见最大 |
| --- | ---: | ---: | ---: | ---: |
| 歌曲 | 656.12ms | 488.28ms | 545.06ms | 419.71ms |
| 专辑 | 1,069.01ms | 767.20ms | 1,144.07ms | 843.11ms |
| 艺人 | 559.17ms | 436.77ms | 1,652.71ms | 733.65ms |

原用户可见基础门槛保持歌曲/专辑≤1,500ms、艺人≤2,000ms；浏览器探针同时要求全部个人指标≤2,000ms，排名和完整总分时间单独记录。点击起点与220ms集合稳定窗口没有缩减。两份最终报告三类横向溢出最大0、重排新增个人请求最大0；补修前矩阵失败及三个预检失败仍保留，最终Pass不覆盖或删除失败证据。本地真实客户端验收通过不等于生产HTTPS已部署或验收。

### 7.7 d41264前的收口记录与历史待补表

S0–S3 实现及专项证据于 `aacf9b98655fab71a8b2655cd602229f2e599525` 提交，当时尚未推送；其后随d41264一并推送，见第8节。提交前核对第7.5节8个测量源码文件的hash与提交内容一致；全部文件hooks（Ruff、format、mypy和secret检查）、文档审计及生成类型检查通过。

该提交上的首次默认完整全栈 run `20261008T172809.434908Z-dbb9ea43778b` 为 **FAIL**：preflight和quality通过，quality再次运行前端787 passed/4 skipped及build；backend_seed为2,484 passed/1 failed。失败在旧部署静态测试仍要求写死主库WAL/SHM文件名，而双库备份函数已使用受限数据库名参数，后续必需阶段未运行。原日志 `output/versus-personal-acceptance/fullstack-final-aacf9b98.log` 与summary保留。

本轮仅同步该测试合同，并增加实际部署备份函数的SQLite WAL验证：主库/Analysis库均保留只存在于已提交WAL的第二行，源main/WAL/SHM字节不变；非法库名与路径穿越拒绝后清除四种部分输出。相关四文件58项回归以及full/showcase/dual配置门禁通过，部署业务代码未改变。修补两个测试后执行了下述第二轮默认完整全栈，结果不能由58项局部通过替代。

第二轮默认完整 run `20261008T174455.760076Z-6e6035b819ae` 的preflight/quality通过，backend seed **3,592 passed**；真实数据integration **70 passed/1 failed**，`TestReleaseCycle.test_compare_releases` 请求返回503。该fixture尚未显式准备发行周期新只读路径要求的精确weekly发布，正在检查发布参数/源context；保留原200及结果断言，不通过恢复HTTP冷建或接受503来获得Pass。本轮整体仍 **FAIL**，后续API及浏览器必需阶段未运行；原日志 `fullstack-after-backup-contract.log` 保留。

独立真实分布副本复现该compare单项503后，只在integration fixture显式准备真实weekly发布：服务端configured过滤与本次请求参数合并，使用API的L2/不含精选集默认值，在POST前构建并核验exact weekly artist/album事实。原请求200及全部结果断言保留，`TestReleaseCycle`完整类 **7 passed**；不修改HTTP读取策略、源统计合同或共享全局warm行为。该局部结果仍不能替代下一轮默认完整门禁。

发布前再次只读核对生产19张可达事实表（`production-facts-before-release-readonly.json`），与最初`production-facts-before.json`及上述Online Backup逐表digest/行数相同，plays仍94,760；三容器image revision标签、镜像tag和部署.env均为76a4968，均healthy。可用内存快照1,338MiB。full/showcase/dual三种静态配置门禁已通过，不能代替目标SHA的CI或部署。公开HTTPS `stats.benjaminlei.site` 可达且为public-readonly；原私有Tailscale域名目前不可达，服务器Tailscale处于Stopped，外层入口未被本项修改。

| 范围 | 当时状态 | 当时待补证据 |
| --- | --- | --- |
| 最终固定 SHA、提交/推送 | 实现aacf9b98已提交，未推送 | 本节与四测试文件修补同次提交后固定发布SHA |
| 全量后端、前端 test/build、hooks | 3,592常规+187真实集成、前端787/4skip、build和全部文件hooks通过 | 同轮日志见第7.8节，警告单列 |
| 默认完整本地全栈 | 第三轮八必需阶段同轮PASS | run 20261008T175717.453395Z-a31484e3798c；前两轮失败保留 |
| 真实冷浏览器 | 最终45场景/90样本与额外冷顺序6样本PASS | 原门槛及历史失败已保留；生产真实客户端另行验收 |
| 周期边缘排名与补修回归 | 部分已核验 | 完整结束周修正单列；最终周期输入、输出与源保护对账，不冒称旧edge rank全等价 |
| CI、三模式与镜像门禁 | 待完成 | 对应最终 SHA 的实际运行 |
| 生产私有/公开 HTTPS | 待完成 | 安装与源 fence、双入口真实请求、视口、网络及 Server-Timing、资源与保护事实 |

本地S4已完成；S5尚未完成，不能据此宣称生产已优化。

### 7.8 默认完整全栈最终通过

默认完整命令未使用`--only`、`--from`或`--skip-cross-browser`。使用项目venv、`SPOTIFY_STATS_TEST_SOURCE_DB`及`PERFORMANCE_DB_PATH`明确指向独立runtime/main.db，数据集标记为`online_backup`，实际localhost后端与Vite前端运行。run `20261008T175717.453395Z-a31484e3798c` 的summary为`selection.mode=full`、`overall_status=PASS`，退出码0；八个必需阶段均PASS，optional未请求并不计入必需阶段。

| 必需阶段 | 结果 | 实际耗时 |
| --- | --- | ---: |
| preflight | 文档审计、OpenAPI操作/参数边界及diff检查通过 | 8.097s |
| quality | all-files hooks、前端787 passed/4 skipped及build通过 | 64.987s |
| backend | 3,592常规测试+187真实数据集成通过 | 519.266s |
| api | 157/157 smoke、113/113 boundary；51性能目标最大hot P95 301.60ms，门槛500ms | 253.745s |
| browser-routes | 桌面/手机完整路由及五视口核心页面通过 | 399.929s |
| browser-interactions | 核心、手机及图表交互通过 | 79.410s |
| browser-inventory | 控件清单和长列表分页通过 | 45.966s |
| browser-compat | Chromium、Firefox、WebKit通过 | 143.582s |

完整日志为`output/versus-personal-acceptance/fullstack-after-real-weekly-fixture.log`；summary与API性能原始数据位于对应run目录。版本记录为业务实现`aacf9b98655fab71a8b2655cd602229f2e599525`、`dirty=true`：本轮未提交范围仅四个备份/真实集成测试文件及本验收文档，业务源码未变。后续固定发布SHA需独立登记，不把dirty运行伪称为clean HEAD运行。

常规测试含5条警告：已有LibreSSL/urllib3和422弃用警告，另有年度AI任务后台线程在fixture退出附近出现`sqlite3.OperationalError: disk I/O error`。保留原trace，不描述为零警告，也不把它归因于个人统计或声称该独立AI线程边界已修复。真实集成2条警告保留于日志。本项不扩大为该AI任务的修复。

### 8. S5首次CI失败与并发补修

S4测试与证据在`d41264cac5b6f7bc286434b2342833e6d23fba73`阶段提交，hooks通过，已推送main。正式发布前再次采集生产19事实表，与原baseline逐表全等，plays94,760；jobs基线6,277（done6,239/failed38，pending/running0），不删除既有失败任务。四份既有ready仅verify/export/validate，未重新build；绑定d41264的manifest为765,982 bytes、`versus_rank_publication_v1`/`entity_rank_context_v2`，单source bb7cb368…，私密路径权限600、父目录700，SCP暂存校验SHA256后原子改名。digest为`e1687d504ba4a7277d7f56d7f58a40c4c3ff36041fb899048fdcc9a28f6e4e84`，回执保存在ignored输出。

对应SHA三次正式workflow均为**FAIL**：生产发布[37824675027](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37824675027)、质量[37824675026](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37824675026)、三模式合同[37824675075](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37824675075)。逐个失败日志确认同一后端unit失败：`test_concurrent_comparisons_decode_exact_projection_once_and_never_rank`期望一次exact快照解码，实际两次；均2,429 passed/1 failed/2 skipped/1,347 deselected。release的profiles/images/deploy被依赖门禁跳过，生产仍旧76a4968，不能把main推送或manifest上传写成已部署。

初诊为SQLite真实mode=ro读取产生零字节WAL，其presence/mtime被`_publication_state`误计入缓存键，使同一publication的并发请求拆成不同singleflight key。确定性复现与最小修补见下文；保留一次decode断言、非空WAL、文件替换和source变化的失效能力。d41264本地PASS和本次CI失败均保留版本边界。

平台复现边界：本机SQLite对完全无WAL/SHM的WAL-header只读备份会报unable-open，因此不声称已在本机复现Linux的“首次RO创建空WAL”。本地确定性测试使用实际已发布SQLite及真实RO读取，协调零字节WAL物理mtime变化，核对无内容变化仍拆key；另协调empty WAL删除期间的stat竞态。Linux行为以正式CI失败及修补后的实际CI为证据。

### 8.1 最小WAL竞态修补与回归

仅修改发行周期`_publication_state`：零字节WAL等同无内容；WAL stat一次采样，FileNotFoundError仅令wal_state为空、保留main的inode/size/mtime，其他OSError保留原fallback；非空WAL保留inode/mtime/size。没有修改原singleflight、容量4、source fence或HTTP只读合同。

新增5个有意义回归：真实RO读取时协调空WAL mtime变化，修前严格一次decode断言失败（实际2）、修后通过；真实unlink竞态保留main身份；同context真实非空WAL发布在main bytes/inode/size/mtime不变时读到新rank；同size/mtime的main原子替换触发新decode；真实源ms_played变化拒绝旧projection503且不重建counts。原三线程一次decode断言保留。相关两模块18项通过，12模块单次合集 **238 passed/24.40s**（18包含在238内，不重复累计）；非空WAL断言去除读取会改变的atime后仅该例重验通过。Ruff/格式/diff检查通过。修前/修后日志、最终XML保存在`empty-wal-race-before.log`、`empty-wal-race-after.log`、`wal-race-related.log`及专项输出中。

个人基础/排名测量的8个源码文件逐个SHA256与第7.5节相同（`api-source-reuse-after-wal-fix.json`），本次cycle service不属于该独立API测量调用链，因此保留原444 HTTP/130门槛、资源与oracle证据；不将8文件相等扩大为全仓库相等或声称重跑36worker。

### 8.2 修补后原冷顺序真实客户端

关闭前一隔离后端并启动修补版本、全部sidecar显式指向runtime验收副本后，未预暖个人API，实际Chromium360按track→album→artist连续执行。`matrix-after-wal-fix-cold-sequence.json` 的3场景/6样本全部PASS，220ms稳定窗口计入点击时间，没有额外idle。

| 种类 | 两对象基础/排名 | 四对象基础/排名 | 四对象全部个人 |
| --- | ---: | ---: | ---: |
| 歌曲 | 334.87/334.87ms | 481.58/412.79ms | 482.42ms |
| 专辑 | 552.23/430.23ms | 1,054.31/702.45ms | 1,055.20ms |
| 艺人 | 1,149.79/558.80ms | 1,494.69/721.89ms | 1,495.61ms |

每类真实API/DOM及最终计分2/2匹配，控制台/横向溢出/重排新请求/中间三对象POST均0，旧完整stats请求0；picker第三至第四对象间隔47.7/48.4/47.4ms。四艺人stats HTTP1,171.36ms、服务端total1,159.292ms，rank HTTP409.77ms。探针内部route wrapper stderr warning单列且页面console0。浏览器退出后再执行默认完整全栈；该冷复验不代替新版本完整门禁、Linux CI或生产HTTPS。

### 8.3 并发补修后的默认完整门禁

run `20261008T185707.659770Z-44ace7878d97` 退出0，最终summary为`selection.mode=full`、`overall_status=PASS`。仍使用94,760播放Online Backup的隔离runtime，无`--only`/`--from`/跳过跨浏览器；八必需阶段全部通过，optional未请求。完整日志`fullstack-after-empty-wal-fix.log`与对应run目录保存。

| 必需阶段 | 结果 | 实际耗时 |
| --- | --- | ---: |
| preflight | 文档、OpenAPI及diff检查通过 | 8.193s |
| quality | all-files hooks、前端787/4skip及build通过 | 65.064s |
| backend | 3,597常规、187真实集成通过 | 522.980s |
| api | 157/157 smoke、113/113 boundary；51目标最大warm P95 308.293ms，门槛500ms | 170.944s |
| browser-routes | 桌面/手机路由及五视口通过 | 399.827s |
| browser-interactions | 核心、手机及图表交互通过 | 79.431s |
| browser-inventory | 控件清单及分页通过 | 45.665s |
| browser-compat | Chromium/Firefox/WebKit通过 | 143.675s |

版本为`d41264cac5b6f7bc286434b2342833e6d23fba73`加本次发行周期service/测试补修及五份文档，`dirty=true`；常规5条、集成2条警告仍保留（含前述AI线程独立边界）。本轮不覆盖旧CI失败或证明生产已发布。

完整门禁结束后，仅调整新unlink回归的fixture连接生命周期：显式保持maintenance holder到实际空WAL unlink、main身份及字节守恒断言结束后再close，避免Linux最后连接close删除sidecar。所有原断言、真实unlink与业务service均不变；该单例独立 **1 passed/0.23s**，Ruff/format/diff通过，`wal-holder-portability.log/.xml`保存。不声称这项测试setup变动已包含在上面的完整运行，新固定SHA的CI将另行验证。

### 8.4 Linux路径审计的测试重入补修

上述业务与本地收口于`14267e836a2330485d164fe03d1ccbe57c00e259`提交并推送；all-files及提交hooks通过。四现有精确发布仅重新verify/export/validate，未build，私密清单765,982 bytes，digest `b97ffda7c735341af13875f649b589a693fc320ffb0a94e42e4333c96ed00345`；权限600、上传校验后原子改名。生产19事实表仍与原baseline全等，plays94,760；jobs仍6,277（done6,239/failed38，pending/running0）。d41264旧清单与失败回执保留。

14267e的[Production Release 37832258677](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37832258677)及[CI Quality 37832261800](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37832261800)均**FAIL**：原并发解码检查通过，新unlink回归发生`RecursionError`，均2,434 passed/1 failed/2 skipped/1,347 deselected。路径为测试`stat→wal.unlink→path_safety audit_guard→Path.resolve→stat`；Linux Python3.9.25在resolve末尾重新stat，而删除标记尚未设置。三模式、镜像、部署均skipped，生产仍76a4968；没有独立production-contract run，不能把缺运行写成通过。逐job与准确失败日志存`workflow-14267e…/`。

只修测试协调：在实际unlink前标记已进入删除，仍执行真实unlink、FileNotFound及main identity/bytes全部断言；正式`path_safety`不变。在该测试增加两个参数，其中一个仅在作用域内委托原路径解析后真实stat（保留None与FileNotFound语义），模拟Linux重入。旧顺序确定性复现1 failed及同链teardown 1 error；修后整模块 **16 passed/3.73s**，包含原一次decode并发测试，Ruff/format/diff通过。日志`linux-unlink-recursion-before.log`、`linux-unlink-recursion-after.log/.xml`与checks保留。16与之前238存在覆盖，不累计。

本次差异仅测试及文档，应用源码与第8.3节默认完整运行完全相同；不声称重跑全部238或八阶段。新固定SHA的真实Linux CI、三模式、镜像、部署及双入口生产专项继续执行。

### 9. d2c4afce 实际部署与首次生产客户端

`d2c4afce8e04cf9c805de201995e6fb5dee54f08` 已提交、推送并实际部署。正式 [CI Quality 37833933166](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37833933166) 和 [Production Release 37833933155](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37833933155) 全部实际 job 成功，包含共享质量、showcase/full/dual 合同、镜像及 deploy。该 SHA 没有独立 production-contract workflow，三模式证据来自 release 内真实 job。四份既有 ready 仅 verify/export/validate，未重建；765,982 bytes 清单 digest 为 `0e2a9c2d2ea0370c22458840ca65b823f0a7eefcc2f1e5fc58e3b7846831b4fc`，私密原子上传回执保留。

正式 verify.sh 退出0，三个运行容器 OCI 标签均为上述完整 SHA。四排名组合 `entity_rank_context_v2` ready 且 source revision 为 bb7cb368…；搜索 schema89 四变体 exact/fuzzy/cjk/short-cjk 通过、orphans0。只监听 loopback3001/3002，3000/8000未开放。正常启动新增11项其他维护任务，全部结束后 jobs6,288（done6,250/failed38、pending/running0），versus rank rebuild 总任务0；保留既有38失败，不声称部署没有新增其他任务。

公开 HTTPS 首次 Chromium360 按歌曲→专辑→艺人连续选2→4，随后覆盖其余视口与 Firefox/WebKit；没有个人接口预暖、额外 idle 或人工 Surface header。14场景/28样本实际指标与排名、DOM及最终计分一致，56个人 HTTP 全200；重排新增请求、中间三对象请求、旧完整 stats 请求和溢出均0。生产冻结门槛仍为基础可见≤2,000ms、全部个人≤3,000ms，25/28达标，首轮以下失败原样保留：

| 首次对象组 | 基础可见 | 全部个人 | stats 服务端 total | 主要耗时 |
| --- | ---: | ---: | ---: | --- |
| 四专辑 | 3,071.75ms | 3,071.75ms | 2,481.624ms | identity1,590.123ms；SQL246.316ms、timeline330.384ms |
| 两艺人 | 2,847.13ms | 未超过3,000ms | 2,681.216ms | 冷身份与目标时间线 |
| 四艺人 | 3,596.36ms | 3,596.36ms | 3,221.249ms | identity1,089.190ms；SQL936.053ms、timeline686.097ms、attribution445.718ms |

rank 请求同批等待 selection singleflight，不将身份等待解释为排名重建。后续热样本不能替代这些失败。WebKit三场景另保留原始脚本 FAIL：只有已知 preload 未及时使用提示，业务数值及性能均通过，无 API/page error；该诊断与项目跨浏览器脚本已有精确忽略规则一致，后续探针分类将保留 raw diagnostics 并单列。不会放宽耗时门槛或重写旧报告。

首次客户端前后 schema、19源表、完整 jobs、全部 Analysis publications 和 rank metadata 七组保护对照全 PASS；new job IDs0。源码与本地禁止 builder 测试、线上队列/发布前后守恒共同支持公开读取边界，未独立观测线上直接 builder 调用计数。原始 evidence 为 `production-public-d2c4afce/production-summary.json`、`offline-threshold-judgment.json` 和 `d2c4afce-public-browser-guard-comparison.json`。

私有 SSH loopback 的真实 capability 已确认 private-admin/full 及同 SHA；仅属于 HTTP 经 SSH 的功能路径，尚未完成48请求功能组，不等于私有 HTTPS 验收。配置私有 HTTPS 的 Tailscale 当前 Stopped，未擅自启用。公开首轮性能失败后重新进入有界 CPU 优化：共享署名/名称身份映射、选中项目成员读取、两轨 canonical key 复用、日期索引边缘与唯一日期格式化；保持原统计事实、exact-ready 和缓存容量。新业务版本验收前本项仍 IN_PROGRESS。

### 10. 生产冷失败后的有界 CPU 优化与当前验证

本轮六个业务文件有改动，当前工作树尚未提交，不能用 d2c4afce 表示新代码。API 测量固定12个调用链文件的 before/after SHA256；业务冻结后完整性能运行中这些 hash 保持一致。没有变更统计合同、builder/policy 版本、公开读取权限或缓存容量。

- 有效署名解析共享一次 identity map 与原始艺人名；预索引 canonical aliases/raw primary affiliations，每批标题不再反复遍历全艺人。覆盖优先顺序和 ambiguity suppression 保持；11,771条真实完整署名前后字节相等。138项治理/parser专项通过，独立模块证据不与后续209项叠加计数。
- 同批专辑共享名称视图及规范化结果，先解析项目再读取选中成员；L2一次 canonical key 映射复用。L3只读 readiness helper由原完整loader和选中项目读取共享，保留全部状态、policy及双revision拒绝。艺人名称共享map，完整有效署名一次分组。真实12组 SelectedEntity 全字段相等，129项专项通过；mypy仍报告 imported L3旧行11项pandas-stub错误，新修改区无错误，未扩大修复。
- lifetime覆盖首尾使用既有日期索引 LIMIT1边缘查询，NULL/music_only语义与MIN/MAX相等；每个唯一当地日期只格式化一次。39,396真实收听区间的完整frame（index、columns、dtype、ms和日期）精确相等；NaT、跨午夜、多日也相等。album4 L2/L3 canonical keys逐行相等，其余原列保持。上述局部 helper 报告先于下一项缓存复用，不能冒充全部新service hash的最终证明。
- 原128条小payload缓存内查找同lineage/source/filter/kind的已完成实体；2→4只计算未完成对象，其他子集可组合精确小指标，仍无额外缓存或frame驻留。12组三类/L2/L3/dynamic/fixed seed验证2→4结果与独立完整批次相等、仅读新增source IDs；另验证五项key隔离与返回深拷贝。合并10模块单次 **209 passed/9.49s**，包含上述相关subset，不累计。

SQL 单一候选仅在隔离副本实验：去掉早于目标timestamp的嵌套查找，完整47,833行raw相等，但交错三次均值298.29→298.82ms无收益，按停止条件放弃；原SQL不变，无新索引或迁移。

冻结后 `post-production-cpu-api-run/report.json` 为 PASS：30独立冷进程、6热进程，共444真实HTTP及130门槛全通过，12调用链hash前后不变，source/owned各19表相等且守恒。冷基础最大歌曲109.76ms、专辑243.22ms、艺人1,022.83ms；排名22.56ms。各kind/count/endpoint 21热观测P95均≤17.28ms；四对象新增峰值最大171.55MiB（门槛256），20不同队列稳态增量最大11.52MiB（门槛128）。builder/publish/enqueue均0、全局播放frames驻留0。原 `final-api-run` 报告未覆盖。

新后端使用独立runtime主库和全部sidecar启动，未预暖个人接口；原顺序冷6样本 PASS：歌曲2/4基础362.78/481.71ms、专辑476.19/710.11ms、艺人921.90/743.18ms。220ms窗口计入四对象点击耗时，新增对象复用小事实结果。冷6加自然暖42共45唯一场景/90样本全部达到原local门槛，真实指标/排名/计分、重排映射一致；中间三对象请求、重排新增请求、旧完整stats和溢出均0。基础/全部个人最大歌曲500.96ms、专辑710.11ms、艺人921.90ms；最终计分可见最大502.03/711.09/923.04ms。周期deferred可在离页取消，full_visible包括个人/榜单/计分，不冒称周期完整加载。

本轮probe原32场景业务样本均PASS，但关闭WebKit context时 `Response has been disposed` 引起driver exit1；原文件保留。仅在明确closing阶段接受两条完整已知disposed/closed短语，live请求错误及其他诊断仍阻塞；17项边界测试通过。新probe e33de4c7…补剩13，不重复已完成或冷样本；两新driver exit0。少量pending route task关闭stderr单列，不冒称无驱动诊断。probe变动仅关闭及console分类，12条API业务hash与上述性能运行一致。汇总 `post-production-cpu-local/summary.json` digest为916b9d20…，旧异常与生产失败未覆盖。

`post-production-cpu-oracle/report.json` 退出0/PASS：16group连续2→3→4的48基础+48排名API全部与旧独立full oracle逐项一致，所有metadata/实体数/status守恒；未重算全库oracle或重建rank。source/owned各19表与旧expected一致且前后守恒，builder/publish/enqueue0，12源码、HEAD、probe、oracle driver及旧JSON前后hash相同。耗时11.70s、报告digest736a0ad4…；旧报告保留自身版本，不冒称旧发布全集重新build。

新默认完整首轮 run `20261008T205628.696307Z-0fcdc94b0661` 在quality FAIL：preflight PASS，mypy报新增测试旧算法oracle中 `by_track` 的两个int(object)类型错误，其余后续阶段未运行。只将该测试容器标注与实际自动署名形状一致为dict[str,Any]，未变测试逻辑或业务源码；专项单模块26项复验通过。原 `fullstack-post-production-cpu.log` 保留。

修补后的默认完整 run `20261008T205855.815078Z-38cb6461d4f2` 为 **PASS**，selection=full，八个必需阶段同轮完成，用时1,426,837ms（23分46.837秒）。preflight 7,672ms、quality 64,529ms、backend 520,975ms、API 164,169ms、browser-routes 399,372ms、browser-interactions 79,390ms、browser-inventory 45,634ms、browser-compat 144,952ms。quality实际all-files hooks的ruff/format/mypy/detect-secrets、前端787 passed/4 skipped及build通过；后端常规3,669 passed/4 warnings、真实集成187 passed/2 warnings，警告不写成零。API及51目标性能通过，Chromium/Firefox/WebKit通过。

完整日志为 `output/versus-personal-acceptance/fullstack-post-production-cpu-after-type-fix.log`；summary及API原始结果另存 `post-production-cpu-fullstack/`。运行记录为d2c4afce+dirty工作树；最终12调用链SHA256仍与上述性能及oracle运行相等，不能描述为旧d2c4afce clean HEAD验收。新业务S4已收口，固定SHA、正式CI及新生产首轮仍待执行，S5继续Partial。

### 11. d5ba3094 实际发布、首次生产复验及剩余瓶颈

完整CPU阶段提交 `d5ba3094f2c843fe903078b7306d930deba5e27d` 已正常推送；提交中的12调用链blob与第10节实测SHA256相等，提交hooks通过。四份既有ready只verify/export/validate，未重建；manifest绑定完整SHA、765,982 bytes，digest `0369ebc0633065b64d90a98a54b3718076764858f11aa8495ff6a957d3997b9a`，原子SCP暂存校验改名、文件600/目录700，回执保留。

实际CI run `37846780581` / job `113549503794` success；正式release run `37846780536`全部success：quality `113549504170`、full `113553770651`、dual `113553770718`、showcase `113553770753`、images `113553847145`、deploy `113554271747`。实际部署日志validated4→installed4→ready4→上线后ready4，builder v2/source bb7cb368…不变。逐job/step与deploy原log位于 `workflow-d5ba3094f2c843fe903078b7306d930deba5e27d/`，不声称另有独立production-contract run。

独立SSH verify.sh退出0，三容器OCI完整SHA+healthy、migration89、搜索4变体与rank4 ready通过，端口边界保持。正式源19表与发布前逐表全等；正常启动新增11项其他任务，已settled为6,299（done6,261/failed38、pending/running0），不删除历史失败。guard脚本的schema字段是PRAGMA user_version=0，前后守恒；schema89证据来自schema_migrations及runtime gate，不能混淆这两个来源。

首次公开HTTPS保持Chromium360歌曲→专辑→艺人原顺序、2/4对象、220ms计入、无个人预暖/额外idle/人工role或API redirect；14场景28样本功能PASS、性能26/28 PASS。唯一失败为Chromium360四专辑基础2,191.15ms及两艺人2,282.70ms；28/28全部个人≤3秒。首次四专辑stats HTTP1,885.67ms/server1,617.205ms，identity1,218.803、source_context117.509、SQL100.668、timeline139.396ms；首次两艺人HTTP2,152.46ms/server2,133.295ms，identity562.689、SQL734.485、timeline652.495、attribution114.994ms。其余11场景未热补首次，均达到原门槛。56 personal HTTP全部200，DOM指标、exact ranks、最终计分及重排映射一致，3对象POST、新重排请求、旧stats、溢出和blocking console均0；一条WebKit exact preload warning原文保留并单列accepted。五driver退出0、contexts关闭，旧d2九份报告hash全部保持。汇总 `production-public-d5ba3094f2c843fe903078b7306d930deba5e27d/production-summary.json` digest a67c0d7d…；offline原门槛判定exit1，digest50e5c9b8…。

浏览器前后guard七项全部PASS：19源表、完整jobs、所有Analysis发布及rank metadata守恒；cap-before/after为真实公开surface/showcase/完整SHA。纯/proc采样实际uvicorn PID570534/start131890819，445条、间隔0.5秒、UTC21:46:06.622–21:49:48.622身份稳定。整个页面cohort RSS基线880.95MiB、采样最大及末值1,172.70MiB、增量291.74MiB，CPU增量43.78秒、最小MemAvailable1,801.67MiB；HWM1,238.03MiB是自进程启动峰值。此cohort同时包含榜单、周期和多个个人队列，不能归为单个四对象个人统计增量，采样也不能覆盖短于0.5秒的峰值；不依据本地171.55MiB掩盖这一生产内存观察。所有浏览器关闭后root主动Ctrl-C结束自有SSH采样，SSH255属受控采样退出，无end marker，不表示后端失败。

另行实际API功能对账：公开HTTPS48请求及私有SSH loopback HTTP48请求全部PASS，四filter群各单rank key、四key不同、capability完整SHA/真实surface一致；96请求前后七项guard再次PASS。私有原forward因长时间闲置timeout，capability preflight未发个人POST；该失败保留，恢复自有loopback forward后执行一次完整功能组，不能称私有HTTPS或其性能通过。公开admin/jobs三GET实际404拒绝；探针原预期403错误保留，按既有Nginx隐藏路由404合同离线纠正，不重发请求。线上builder直接调用计数未观测；只读源码、本地forbid及生产完整队列/发布守恒分别构成证据，不能声称直接测得其0次。

当前S5继续Partial。静态核对发现已取消的发行周期同步计算可能与后续个人请求竞争；首次daily baseline仍全库计次重建，尚需时间线证明其在上述失败中的占比。下一步在隔离副本细分timeline、日期与阈值成本，验证已有精确source聚合可否限定复用；不加预暖/等待idle、不放宽门槛、不混用覆盖边缘周或旧source。私有HTTPS仍为外部待确认条件；独立OOM事项保持开放。

## 12. 计次投影整合：当前工作树完整门禁通过

本轮仅在对决基础路径启用计次投影与共享时间解析；完整详情、排名builder及其他调用维持默认完整输出。局部真实帧交替测量包含解析成本：两艺人160.055→91.006ms，四艺人203.724→123.169ms。默认完整帧、消费字段、过滤事件和收听帧精确相等，19张事实表、source context及主库/WAL保持，SHM内容保持但mtime被只读连接触碰；不称所有物理属性不变。

整合后的六个unit/contract模块共198项通过（9.96秒，1项既有LibreSSL警告）；四文件Ruff及格式检查通过，timeline与service的mypy检查通过。真实API复核96个请求对旧独立oracle逐字段一致，builder/publish/enqueue均0，源与副本19表守恒、旧预期文件及测量调用链hash保持。证据：`output/versus-personal-acceptance/count-projection-oracle.json`；没有重新准备数据库或构建排名。

独立冷启动、重复读取及资源测量已通过：36个进程（每类2/4对象各5个独立首次进程和1个重复读取进程）、130项门槛全部通过；基础首次最大歌曲175.02ms、专辑309.71ms、艺人929.25ms，排名首次最大20.91ms。各接口21个重复观测P95最大19.23ms；四对象读取新增峰值最大128.48MiB，20组切换稳态新增最大6.25MiB。builder/publish/enqueue均0、无全库frame驻留，源/副本19表与测量调用链保持。报告为`output/versus-personal-acceptance/count-projection-api-run/report.json`，旧版本报告保留。本节专项测量时业务工作树尚未提交，后续固定版本见第14节；上述专项与下述默认完整全栈共同构成S4证据，生产浏览器尚未复验，不能视为S5完成。

当前工作树本地三浏览器、五视口45场景90个人样本已实际完成，90个样本的数值、排名、DOM及最终计分、性能门槛全部通过；180个个人HTTP全200，重排新增请求、三对象中间批次、旧完整stats和溢出均0。原顺序Chromium360无个人预暖、220ms计入：四歌曲基础501.98ms、四专辑584.25ms、两艺人1,018.73ms、四艺人908.47ms。全矩阵歌曲/专辑/艺人基础及全部个人最大697.48/708.95/1,018.73ms，12调用链、probe、实体清单和HEAD前后相等。

原45场景整体仍记录44/45功能PASS、overall FAIL：Firefox768艺人出现外部Spotify图片`Image corrupt or truncated` console error，该场景个人2/4指标、DOM、计分和性能正常。旧d5同场景与当前提供相同封面URL，旧日志没有外链HTTP状态，不能证明外部响应无差异。仅一次独立fresh Firefox768艺人复验通过、console及stderr无错误，基础/全部个人303.37与420.57ms；这只证明该错误没有重复，不能证明外链根因或长期稳定。原45矩阵和失败保留，不拼接为首次45全PASS。证据目录`output/playwright/versus-personal/count-projection-local/`：原summary digest6337c6ec…，独立04复验digestb85960b1…；owned浏览器及context均已关闭。

默认完整run `20261009T025926.864416Z-acc84dac10e3` 已实际退出0，selection=full、八个必需阶段同轮 **PASS**，耗时1,561,616ms（26分1.616秒）。各阶段依次为preflight 8,654ms、quality 77,028ms、backend 558,683ms、API 216,307ms、browser-routes 402,967ms、browser-interactions 82,644ms、browser-inventory 50,307ms、browser-compat 164,822ms。all-files Ruff/format/mypy/detect-secrets、前端787 passed/4 skipped及build通过；后端常规3,694 passed/4 warnings、真实集成187 passed/2 warnings；API smoke157/157、boundary113/113、51性能目标slow_count0，warm P95最大381.272ms（门槛500ms），三浏览器兼容均通过。日志`output/versus-personal-acceptance/fullstack-count-projection.log`，兼容summary `count-projection-fullstack-summary.json`，原始API/XML及锁记录保存在同run目录。运行记录为d5ba3094+dirty；最终12调用链hash逐一仍与本次API性能测量相等，不能称旧d5 clean HEAD验收。另一个线程的音乐详情规划未纳入本次提交；新增计次投影S4收口，固定SHA、正式CI、生产首次与私有HTTPS仍待完成。生产只读准备确认三容器仍d5ba3094/healthy，19源表与最初baseline相同，完整jobs和全部发布与d5验收后相同，pending/running0。Tailscale当前Stopped且serve配置为空，未修改外层入口，私有HTTPS仍为独立外部依赖。

## 13. 私有入口只读调查：历史接法与当前服务器

用户说明一直使用`https://stats.benjaminlei.site`，并要求核对旧私有入口。实际GET capabilities确认该域名仍为public-readonly/showcase/d5ba3094；未把它视为私有HTTPS、未自行调整S5双入口范围。

历史交付报告`2026-08-13-private-cloud-pwa-delivery.md`记录私有URL`https://spotify-stats.tail8916b1.ts.net`：Tailscale Serve tailnet-only HTTPS→127.0.0.1:3001完全版网关，需同tailnet授权设备，无Funnel；当时HTTPS/PWA及TLS证书曾验收通过。同日后续双运行面报告记录Tailscale保持Stopped，自动部署不恢复外层入口。

当前服务器只读核验：原节点DNSName仍相同，tailscaled systemd active/running/enabled；prefs WantRunning=false、LoggedOut=false，BackendState=Stopped，Serve配置为空。近期重启日志继承关闭意愿，无法确定最初停止时间或操作者。完全版网关3001实际GET capabilities为200/private-admin/full、完整SHA d5ba3094，三容器健康；应用本身可用不等于私有HTTPS可访问。公开域名由宿主Caddy `/etc/caddy/Caddyfile` reverse_proxy到127.0.0.1:3002，不是宿主Nginx；未发现该站点auth directive，仍由公共运行面限制能力。

配置入口是现有`deploy/production/configure-tailscale.sh`：读取APP_GATEWAY_PORT（默认3001）、检查loopback健康，再执行Tailscale Serve后台HTTPS转发。恢复需要另行确认启用原tailnet节点、重新设置Serve→3001并从同tailnet授权客户端验证；仅启用节点不能补回空Serve。调查不执行这些变更，也不更改Caddy、Funnel、端口或防火墙。sanitized证据保存在ignored `output/versus-personal-acceptance/private-entry-investigation/`，目录700/文件600，无密钥、环境文件原文或节点状态原文。

2026-10-09 04:22:50 UTC再通过SSH只读核实，原节点DNS仍为`spotify-stats.tail8916b1.ts.net`，BackendState=Stopped、Serve配置为空；3001/3002的实际capability分别为private-admin/full与public-readonly/showcase，完整SHA均为acdd0d0ddb10170acacffdaedeba03b17ae70519。证据`private-entry-investigation/current-route-state.json`；本次不启用节点、设置Serve或改公开路由。

## 14. acdd0d0d 实际发布及首次生产：一项基础性能仍失败

计次投影阶段已提交 `acdd0d0ddb10170acacffdaedeba03b17ae70519` 并正常推送main；提交hooks的Ruff、format、mypy、detect-secrets通过。12调用链commit blob的SHA256逐项与第12节实测一致，绑定回执`count-projection-commit-binding.json`。另一个任务的音乐详情规划、地图以及SS-2026-10-09-001共享文档新增hunks均留在工作树，没有混入九文件提交。

四份既有ready只verify→export→validate，三个实际退出均0，没有build/install。manifest绑定完整SHA、builder v2、source revision bb7cb368…，765,982 bytes、digest `a6eeaf5f56da2a1912de3fc74ac862286416c264821c2bb4e3e51fcae7b4186c`；600暂存文件经远端digest校验后原子改名，`.upload`已不存在。新上传前生产guard与最初19表及本阶段before一致，完整jobs6,299（done6,261/failed38、pending/running0）、22发布及4rank元数据守恒。私密上传回执`acdd0d0ddb10170acacffdaedeba03b17ae70519-manifest-upload-receipt.json`保留。

正式CI run `37879579278` / job `113655927858` 已实际success；Production Release run `37879579463` 的quality job `113655928638` 后端unit已success、contract仍运行。截至2026-10-09 03:40:43 UTC，尚无三模式、镜像或部署通过结论，生产仍d5ba3094。后续继续真实部署、独立verify、原顺序首次公开浏览器、API矩阵及源/任务/发布保护，私有HTTPS仍单独待外部条件；不把新CI success描述成已上线。

正式release现已actual success：quality `113655928638`，full `113659614808`、showcase `113659614820`、dual `113659615063`，images `113659652776`、deploy `113660011476`。独立SSH verify.sh退出0，search schema89四变体/semantic/orphans0及rank4 ready通过。2026-10-09 03:55:34 UTC runtime记录三运行容器OCI完整SHA均acdd0d0d且healthy；3001 private-admin/full、3002 public-readonly/showcase同完整SHA，backend无宿主映射、两Web仅loopback。Tailscale仍Stopped，未改外层入口。启动维护当时尚有pending2/running1，不在这一时点启动首次cohort；source19上线后guard及浏览器/API验收仍待完成。证据 `release-acdd0d0ddb10170acacffdaedeba03b17ae70519/production-verify.{json,log}` 和 `production-runtime.json`。

启动维护自然结束后，beforeguard（03:57:18 UTC）为jobs6,310（done6,272/failed38、pending/running0）、20项Analysis发布、4份rank/source bb7cb368…。相对发布前新增11个正常维护任务、22→20项派生发布变化分别保留；19源表与初始及发布前逐表相同。实际公网capability确认为public-readonly/showcase/完整acdd SHA。无个人预暖、额外idle、人工role或API重定向，随后纯/proc采样启动并放行首次公开浏览器。

公开14场景/28样本功能全PASS，56 personal HTTP200，DOM值、exact ranks、最终计分及重排映射一致；三对象中间批次、重排新增请求、旧完整stats、overflow及blocking console均0，五driver退出0且全部contexts关闭。原2s/3s门槛为27/28达标，唯一首次Chromium360四专辑基础/全部个人2,385.25ms、排名2,109.34ms，超过基础2秒；28/28全部个人≤3秒，原失败未热补。首六组基础/排名依次为：歌曲2个744.99/253.82ms、4个732.41/617.55ms；专辑2个798.73/462.04ms、4个2,385.25/2,109.34ms；艺人2个1,925.64/784.83ms、4个1,535.69/1,201.22ms。后11场景全部达标，不能替代原四专辑失败。

首次四专辑stats HTTP2,035.36ms/server1,641.346ms（identity1,192.630/source_context218.117/SQL98.084/timeline94.643/attribution24.277ms），rank HTTP1,815.19ms/server1,418.161ms可包含共享selection等待，不能解释为重建排名。两艺人stats HTTP1,792.50/server1,748.252ms（identity540.387/SQL736.500/timeline319.321ms），相比旧d5首次已达原基础门槛。旧d5五raw及summary的hash、当前12调用链/HEAD/probe/entities均保持。`production-public-acdd…/production-summary.json` digest `09a8883e5ac1403baa3028c0f2cefde324103f359a459f893afc3379e822de29`，offline judgment digest `0c77c65ff46cc9513fade545203fb4376eac5950a674faac4b1ee341242d2c22`、exit1；原失败保留。

浏览器前后7组guard全部PASS；后续公开HTTPS48及私有SSH loopback HTTP48个功能请求均complete/functional_pass，四过滤群各一个rank key、四key不同，真实surface和完整SHA一致。三个实际公开admin/jobs GET均按既有隐藏路由合同返回404。96请求及拒绝检查后7组guard再次PASS，19源、完整jobs、20Analysis发布和4rank元数据守恒。既有SSH forward17379仍live且capability正确，未因观测超时重启forward。私有SSH是功能HTTP证据，仍不等于私有HTTPS验收。guard脚本遗留note写12请求，本节的实际输入边界是前述14场景及另行96功能请求，以raw驱动/两个前后快照为准；不据旧note缩小或扩大证据范围。首个本地guard comparison在capture句柄69809尚未完成时误读空输出而JSONDecodeError；等待同一次capture实际exit0后重做离线比较，没有重复网络capture，最终七项一致。

资源采样固定实际uvicorn PID932715/start134114984，524样本/0.5s、UTC03:58:06.421–04:02:27.921，所有样本身份相同。整个页面cohort及afterguard RSS基线910.05MiB、最大/末值1,117.41MiB、增量207.36MiB；CPU增量43.35秒，最小MemAvailable1,869.09MiB。HWM1,295.30MiB属进程启动以来、包含启动维护，不能作本cohort峰值。浏览器关闭后root Ctrl-C结束自有纯只读SSH采样（255、无end marker），未给backend信号或重启；每0.5s采样不能捕捉更短峰值，整页含榜单/周期，不能归单个个人API或证明OOM已解决。报告`release-acdd…/resources/public-cohort-summary.json`及原JSONL保留，未用本地128.48MiB替代线上观察。

当前S5仍Partial；下一步按规划R3只针对同期发行周期的全库计次基线进行精确事实复用，先隔离证明竞争与日级事实等价，不扩大身份缓存或放宽门槛。私有HTTPS配置仍未改变。

## 15. 剩余四专辑延迟：隔离竞争与R3候选证据

固定acdd源码和隔离schema89副本：album2→4身份准备单独三次19.346/19.377/20.067ms，自身thread CPU19.343–20.062ms；与global raw读取同起点仅30.229–31.150ms，不能据此解释生产1.19秒。精确协调到原global logical merge入口后，同一SelectedEntity事实不变，身份墙钟变246.219/203.086/213.810ms，但自身CPU仅41.639/25.491/25.662ms；global merge CPU269.140–309.765ms、完整global计次659.939–789.925ms。这证明同期Python计次可显著拉长身份墙钟；生产raw缺服务端绝对起止和取消完成，仍不声称已解释线上全部1.19秒。

现有`agg_weekly_track_sources`完整versioned有效性检查104.804ms、按Billboard week year/play_date汇总计次15.822ms；1,527个元组、67,881次逻辑播放与原global计次逐项相等、missing/extra0。不得用artist fanout、周榜rank或裁掉覆盖边缘。候选仅在merge/music均开启且完整参数、当前generation/source/dataset/policy/duration/identity/credits/必要表证明匹配时使用；无builder的旧fixture兼容分支不得准入，不匹配保持原计算，不prepare/build/写正式DB，不改变现有4条compact tuple缓存。尚须实现与回归，不能将单一真实参数相等描述成所有边界已完成。

19表事实、context、8调用链hash及main/WAL的inode/size/mtime/sha均保持；SHM内容保持、mtime被只读连接触碰，all_physical=False明确保留。原完整daily oracle已保存，后续无需重算排名。证据`output/versus-personal-acceptance/album-identity-cycle-isolation-20261009/{report.json,phase-report.json}`及profile/log；本节测量时业务文件未修改。R3最小实现已准入，root负责整合与新版本接口/浏览器/完整门禁及生产首次闭环。

### 15.1 R3实现与隔离回归：已冻结，HTTP与完整门禁待验

仅修改`release_cycle_comparison_service.py`与原unit模块。现有4条singleflight/LRU compact tuple miss优先尝试只读日计次聚合；merge/music、参数hash、当前generation/dataset及全部计次必要versioned proof匹配才复用，源revision和connection data_version前后双重检查；缺失、不可读、失配或漂移回退原计次。不得进入无builder的旧兼容分支，不维护/重建/写聚合、不扩大缓存。

精确依赖边界与已有增量维护一致：Album Project membership在source聚合读时应用，没有烘焙进source-track计次，因此只排除`album_project_revision`，其它proof键全部比较。最初严格全键检查真实副本因此拒绝，原失败日志`r3-after-proof-mismatch.log`保留；未补写配置或重建以制造通过。新增真实删除project membership后两条日计次路径完整相等的测试，参数/身份/署名/时长/政策/source不匹配仍回退。

114项相关unit/contract通过（comparison44、其它70，9.66秒），Ruff/format、service mypy与diff检查通过。边界包含真实参数失配、proof期间外部ms修改、不可读聚合、nullable representative、跨年Billboard归属、覆盖边缘、仅时长零计次以及完整周期结果。真实helper三次174.050/181.424/195.481ms，实际_daily_projection冷miss三次202.265/204.033/206.551ms；1,527个年/日/计次元组、67,881次播放完整exact，forbid原_count_events证明没有回退或用热命中替代。新cold baseline同期album4 identity40.645/43.556/41.126ms、自身CPU24.503–27.234ms；旧精确merge竞争203.086–246.219ms，不能据此宣称线上已达门槛。

19事实表、source、源码和main/WAL stat/hash守恒；SHM内容守恒而mtime变化，all_physical=False。最终`r3-after-report.json`与`r3-final-*`保留。源码hash service `0cac248cc9638a862e67b4b5f36088c50226fef2bdc624978a680af81150bcf2`、test `abee57ecc63d97e195d2eefbacbb2b54135047bc0943170ac708ed47b9103864`。root扩展13条整体调用链冻结：原12个人调用链仍与acdd commit blobs一致，新增周期service必须纳入本轮前后绑定；旧个人API报告仅描述未变的12文件，不冒充新整体验收。

本地仅重启root拥有的backend会话53873（正常exit0），新会话4067/PID79826，仍用原runtime/main及analysis/billboard/community/archive/yearly/governance六精确sidecar，warmup/search/L3 startup均0，无reload。startup完成、health200后首次个人请求交浏览器原cold6，再执行三浏览器五视口；尚未跑API预暖。当前S4再次待新版本HTTP、浏览器及默认八阶段，S5仍保留acdd原四专辑失败和私有HTTPS外部条件。

### 15.2 当前R3本地浏览器与接口对账

原首次Chromium360六样本全部功能/性能PASS，基础/排名ms依次为track2 430.39/308.58、track4 561.39/427.07、album2 576.06/392.48、album4 781.17/594.13、artist2 929.41/470.34、artist4 770.04/631.43，220ms等待已计入，真实3→4 gap47.7–48.6ms。随后自然暖42场景，三浏览器五宽唯一45/45功能、90/90个人性能全部PASS，180 personal HTTP200，API/DOM误差0；各kind基础及all最大632.85/870.23/929.41ms，最终score可见最大633.87/871.83/930.59ms。三driver actual exit0、全部contexts关闭，无应用console错误、overflow、legacy、重排新增或中间三对象批次；无窄复验或额外预暖，未覆写旧本地/生产FAIL。

13条调用链前后与root before-binding完全相等，probe e33de4c7…和entities429a87fc…未改。关闭期Page._on_route pending stderr与deferredcycle取消保留driverlogs，不能推断服务端已停止或量化其CPU。summary `output/playwright/versus-personal/release-cycle-aggregate-local/summary.json` sha256 `6f983543e8d288c26589d79d33805f1c0c3a758c2456e13293b33cfa6fd19440`。

浏览器释放CPU后，当前版本按现成独立完整oracle执行48基础+48排名API，对账96/96通过、19源/派生事实守恒，builder/publish/enqueue均0、四精确排名复用；完整oracle未重算、独立期望文件未变，13源码前后冻结。`release-cycle-aggregate-oracle/report.json`实际exit0/12.882秒。个人fresh5/warm21/资源36 worker已actual exit0，122.867秒、324常规+120切换HTTP共444，130门槛全部PASS。三kind fresh基础最大266.76/488.73/972.75ms，rank fresh最大52.25ms，warm21 P95最大34.01ms；四对象新增峰值最大128.72MiB，20不同队列稳定增量最大5.59MiB。19源及派生事实与独立source匹配并守恒、13 hash冻结、global frame0、builder/publish/enqueue0；不重新prepare/维护。新默认完整全栈已实际完成并退出0，八必需阶段同轮PASS，见下节；固定提交和新版本生产仍待完成。

该run中间核验：quality PASS（92,584ms），常规3,722 passed/5 warnings（297.85秒），真实集成187 passed/2 warnings（226.61秒），随后完成API和浏览器阶段。常规新增一个AI后台线程警告：`test_yearly_review_v2_contract.py::test_available_years_has_response_model_and_request_id`期间`ai_task_service._run_handler_safely`打开数据库时PRAGMA journal_mode=WAL报disk I/O error；trace与原始日志保留。AI service与db源码未修改，不将此警告描述成旧acdd同样存在，该警告不计作测试失败，但需随本轮原始证据保留。

### 15.3 R3默认完整门禁收口

默认完整run `20261009T043213.567518Z-22473bd44432` actual exit0，selection=full、dry_run=false、overall_status=PASS；八个必需阶段同轮PASS，总耗时1,480,781ms（24分40.781秒）。阶段ms依次为preflight9,654、quality92,584、backend537,518、api169,229、browser-routes400,051、browser-interactions80,221、browser-inventory46,494、browser-compat144,892；optional NOT_RUN，不冒称可选阶段已验。

all-files Ruff/format/mypy/detect-secrets、前端787 passed/4 skipped（97 files passed/1 skipped）与build通过；后端3,722 passed/5 warnings、真实集成187 passed/2 warnings。API smoke157/157、boundary113/113，51性能目标slow_count0，51个warm组最大P95 225.94ms（Billboard data，门槛500ms）。桌面/移动路由、真实交互、控件清单以及Chromium/Firefox/WebKit兼容全部通过。摘要`release-cycle-aggregate-fullstack-summary.json`，原API/XML/locks位于同run目录，日志`fullstack-release-cycle-aggregate.log`。

运行记录为acdd0d0d+dirty R3工作树；验收前后13调用链与unit文件hash完全相同，不能把新helper验收写成旧acdd clean HEAD。另一个线程的SS-2026-10-09-001规划及docs地图不属于本次提交范围，源代码冻结仍有效。S4 R3收口，S5固定SHA、实际CI/发布/首次生产与私有HTTPS验收尚未完成；已向用户请求明确授权恢复原私有入口或调整仅公开验收，未擅自启用Tailscale。
