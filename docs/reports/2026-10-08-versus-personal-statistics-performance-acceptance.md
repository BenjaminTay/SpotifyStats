# 榜单对决个人播放统计 S0–S4 性能与正确性验收

创建：2026-10-08；最后核验：2026-10-09。问题：`SS-2026-10-08-002`。对应[实施规划](../plans/2026-10-08-versus-personal-statistics-performance-plan.md)。关联 `SS-2026-10-08-001` 的资源风险，本报告不宣称整站 OOM 或其他详情冷路径已解决。

状态：**S0–S4本地验收 PASS，S5正式CI失败后的并发补修及默认完整重验 PASS**。目标后端检查、生产 Online Backup 副本上的最终 API 性能、资源和事实对账、真实浏览器矩阵及默认完整全栈保留各自版本证据；补修后238项专项、原顺序冷6样本及八必需阶段通过。新固定SHA的正式CI与生产仍待完成。

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
