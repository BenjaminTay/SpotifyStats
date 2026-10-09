# 榜单对决个人播放统计 S0–S5 性能与正确性验收

创建：2026-10-08；最后核验：2026-10-09。问题：`SS-2026-10-08-002`。对应[实施规划](../archive/06-productization-closeout/2026-10-08-versus-personal-statistics-performance-plan.md)。关联 `SS-2026-10-08-001` 的资源风险，本报告不宣称整站 OOM 或其他详情冷路径已解决。

当前状态：**已完成并发布，固定业务版本 c58775f0；按人类明确调整的公开 HTTPS 范围完成 S0–S5**。正式三流水线与11实际jobs、安装、独立runtime、原首次14/28、完整资源/守恒、公开48＋私有SSH HTTP48及三denial分别通过。私有HTTPS保持原状并明确排除本轮验收；详情独立首次与整体OOM另行跟踪。最终证据见21.9–21.12。

历史状态：**d5ba3094 本地S4、正式CI、三模式及部署通过；S5生产专项Partial，首次公开客户端仍有两项基础性能失败**。d2c4afce历史三项生产失败及各版本证据保留。d5ba3094首次公开28样本数值及计分正确，26项达全部性能门槛、全部个人指标均≤3秒；四专辑2.191秒、两艺人2.283秒超过基础2秒。第11节记录该版本生产；第12节记录新增计次投影工作树，不能沿用d5ba3094完整门禁或以热重跑覆盖首次失败。

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

## 16. R3固定提交与实际正式流水线

阶段提交`9dd7fd9bc649172e16f9ba118075adfe2a4c3cf1`，标题“perf: 复用每日计次减少榜单对决请求竞争”，7份限定路径/466插入14删除，pre-commit Ruff/format/mypy/detect-secrets全部actual Pass。commit blobs与已测13调用链及unit文件逐一hash相等，defaultfullrun仍为上述R3工作树验收，不伪称在旧acdd或clean HEAD直接运行。其它线程的docs地图、新规划以及两份共享文档的SS-2026-10-09-001行/小节完整保留，未纳入提交，证据`release-cycle-aggregate-commit-binding.json`与`r3-unrelated-before-stage.json`。

只对现有maintenance-run2执行verify/export/validate，actual exit均0、ready4/source bb7cb368…/builder entity_rank_context_v2，未build、补写agg_config或使用closed-source；源有零字节WAL时仍不视为closed。新清单765,982字节、digest`0c34d3f78fa978e3c26de5a8cedbbb928b5be4c3f0e923693c0adb5439d37af2`，600权限上传至`/opt/spotify-stats/backups/versus-ranks-9dd7fd9bc649172e16f9ba118075adfe2a4c3cf1.json`，远端SHA核验后原子改名，临时.upload不存在；旧清单保留。回执`release-9dd7fd9bc649172e16f9ba118075adfe2a4c3cf1/manifest-{readiness,upload-receipt}.json`。

root正常push actual exit0（acdd→9dd/main），随后实际发现同完整SHA的CI `37886787174`与ProductionRelease `37886787245`，均in_progress。05:06:46 UTC CI job113678459466、release quality113678460564均Backend unit运行；此时不能记为CI/三模式/镜像/部署通过。沿同run监测，不手动重触发或因观测超时重启。部署当前仍以最后独立实测acdd记录为准，新版本首次公开、私有功能/HTTPS及保护事实尚待实际上线；私有范围授权未收到，不启停外层入口。

05:24:59 UTC同两run已actual completed/success：CI job `113678459466`；release quality `113678460564`、showcase `113681718628`、full `113681718689`、dual `113681718745`、images `113681760303`、deploy `113681964329`均success。独立SSH verify.sh于05:25:55 UTC实际退出0，schema89、search4 strict-ready、rank4 ready及source bb7cb368…通过，三容器完整9dd SHA/healthy；backend实际R3 helper SHA256为`0cac248cc9638a862e67b4b5f36088c50226fef2bdc624978a680af81150bcf2`，精确匹配本地已测文件。启动任务此时仍pending2/running1，不在这一时点启动首次浏览器或个人API；尚不能称生产性能验收通过。

用户要求的私有入口调查追加当前服务器核验：05:25:10 UTC原DNS仍`spotify-stats.tail8916b1.ts.net`，Tailscale BackendState=Stopped、Serve配置为空；3001为private-admin/full，3002为public-readonly/showcase，两个实际capability均完整9dd SHA。只读脚本实际退出0，证据`private-entry-investigation/current-route-state-latest.json`。外层入口没有修改，恢复授权或调整公开验收范围仍待用户答复。

## 17. R3生产首次验收：四专辑达标，两艺人仍有基础延迟

05:28:25 UTC启动自然settled后保存新beforeguards：jobs6,321（done6,283/failed38，pending/running0），20份Analysis发布及4份rank完整元数据，19源表与最初基线逐表相同、plays94,760。新增11个启动任务及派生snapshot变化与浏览器读取分开记录。首次个人请求前启动实际uvicorn PID1,025,801/start_ticks134,660,988的500ms只读采样，首样本05:28:55.908 UTC；没有个人API预暖、缓存清理或额外idle等待。

公开原5驱动14场景28样本全部完成，五driver实际退出0；14/14功能、56个人HTTP200、API/DOM数值、计分及同集合重排均PASS，3对象额外批次、重排请求、legacy、溢出及阻塞console均0。全部28个人样本≤3秒，27/28满足原基础2秒/全部3秒门槛；唯一失败为原Chrome360两艺人基础/全部2,097.71ms。原first六样本基础/排名可见耗时（ms）：track2 633.10/404.81、track4 761.97/626.98、album2 910.69/552.97、album4 1,023.55/741.13、artist2 2,097.71/937.75、artist4 1,523.52/1,112.35。四专辑已达标，原acdd2,385.25ms失败保留，不热重跑或放宽门槛。两艺人stats HTTP1,956.71/server1,917.627ms，identity703.646、SQL730.870、timeline351.143、attribution91.642、source_context14.525；rank实际HTTP763.65/server717.630ms与UI排名计时937.75ms分列。

原始证据目录`output/playwright/versus-personal/production-public-9dd7fd9bc649172e16f9ba118075adfe2a4c3cf1/`。summary SHA256 `d28f7ec407ae2a6ad506cb57165504b8a6c8b7cc04122d779bb78f368148d604`，judgment SHA256 `38e341279ca80ec21095f3851bd39f9c4ec703c572d69af8e650befa9eb01f55`（性能判定实际exit1）；五浏览器driver的exit0只代表各自功能完成，不能据此写全部性能通过。13调用链、probe和实体文件前后不变；旧acdd原始失败、summary/judgment hash守恒。所有owned browser/context关闭后才执行功能API，未新增首次热复验。

浏览器前后7组guard全PASS；随后实际公开HTTPS48和私有SSH loopback HTTP48请求均complete/functional_pass，四filter群各一个rank key、四key不同，capability完整9dd SHA与真实surface/能力位一致。三个公开admin/jobs只读GET按既有隐藏路由合同返回404，API和拒绝探针结束后7组guard再次全PASS。source19、完整jobs、20Analysis发布及4rank元数据守恒。私有SSH是功能HTTP证据，不能替代私有HTTPS；外层入口仍未启用。证据`release-9dd…/{browser,api}-guard-judgment.json`及两份`*-api-functional.json`；guard脚本遗留note写12 API，本次真实输入以14场景/56个人HTTP和另行96功能请求为准。

整页cohort资源535个样本（500ms）：基线RSS972.80MiB，采样峰值1,205.54MiB、新增232.73MiB，CPU增加42.18秒，最小MemAvailable1,822.99MiB。范围包括榜单与发行周期，不能归为单个人请求或宣称OOM/泄漏修复；500ms可能遗漏更短峰值，进程lifetime HWM也不能视为本轮峰值。采样原始SHA256 `a8577637ebebf38f3356f5cebc73f746413f515bf19d278d7c04bd55f7b6fea8`。关闭浏览器后只对本次精确命令的sampler发送SIGTERM15，end marker完整、同SSH实际退出0，后端未终止；首次停止命令因远端引号解析失败退出2且未发信号，修正后完成。

当前S5仍Partial，S4重新进入剩余计算竞争诊断：当前批次发行周期已经等待个人stats/ranks settled；旧周期fetch取消不能证明同步后端已经停止。两艺人榜单响应则仍与个人请求并行，读取exact-ready完整payload后构建全局DataFrame及跨层派生成绩。这两条路径的实际CPU重叠尚未证明，下一步仅在既有精确ready隔离源测量个人单独、与周期目标阶段、与榜单读取后计算三组，不在生产热缓存上复验、不重测已消除的每日全局计次、不补建快照。私有恢复授权或范围调整仍为独立待答条件。

## 18. R4隔离诊断与艺人署名候选等价证明

既有ignored OWNruntime的main.db/billboard.db真实绝对路径、mode=ro/query_only；未修改持久context key、路径别名或补建快照。九个fresh进程（个人单独/并发周期目标阶段/并发榜单读取后计算，各3次）全部实际exit0，weekly/full_data现成exact-ready均匹配，初始五项应用缓存均0，OS页缓存共享。两艺人六基础指标均精确等于既有96 API oracle；19源表、8调用链hash前后相同，禁止build/publish/enqueue且违反计数0。证据`artist-cold-contention-20261009/{report.json,alone-*,cycle-*,chart-*}`。这些是受控诊断，不是生产首次性能Pass。

个人单独wall497.987–600.644ms/threadCPU496.603–515.042ms；周期并发wall680.480–755.439ms/CPU520.176–565.544ms；榜单并发wall624.627–948.075ms/CPU540.446–566.662ms。identity单独102.83–122.15ms，周期并发254.84–268.00ms，榜单并发209.33–248ms。周期三次均走R3精确聚合命中，无raw全局计次，handler894–943ms/CPU800–818ms；其primary艺人source-ID读取CPU105.6–114.2ms，目标完整计次时间轴CPU292.8–303.2ms。原请求包含4专辑，但隔离metadata仅1张eligible、actual comparisons=1，不能称生产4张指标全部参与。榜单handler111.8–120.3ms/CPU107.9–113.5ms，其中payload decode47.1–48.6ms、全局跨层排名合计约14ms。chart第三样本SQL541.194ms/CPU282.983ms异常保留：chart在SQL开始前148ms已结束、重叠0，不能归因或重跑清除。实验表明竞争可侵蚀97.71ms预算余量，但没有生产任务绝对起止，不能声称解释了全部1,917.627ms服务耗时。

候选纯读取实验：将目标canonical artist展开为raw aliases，从tracks主艺人、track_artists、Spotify自动署名及active人工覆盖四来源读取candidate曲目超集，再调用原get_effective_track_credits完整规则，最后选目标canonical署名。规则中的标题抑制只删除，人工add/remove/set_role及合作署名仍由原解析器处理；没有独立近似署名规则或新增缓存。空candidate显式返回空集合，不能将空列表传入现有“空即全库”的provider。

两个艺人627候选、四艺人889候选（包括rawalias773→canonical Olivia76），L2/L3×dynamic/fixed的2/4对象共8配置、每项3次旧/候选交错测量。全部SelectedEntity dataclass字段精确相等，含credited_track_ids、L1反向source IDs、request/entity/rank keys；两个与过滤无关的署名集另与全库11,771条effective oracle比全部字典字段，目标627/889条精确相等。两对象身份解析平均119.167ms/CPU117.594→25.968/CPU25.681ms，四对象115.865/CPU115.313→31.127/CPU31.013ms。19源及3源码hash守恒，实际exit0；证据`artist-credit-candidate-20261009/{report.json,probe.py,driver.log}`。候选实现与回归已启动，当前尚未完成新业务HTTP/浏览器/完整门禁或生产验收。

### 18.1 最终实现与当前版本冻结

只改`backend/services/versus_personal_context.py`和对应identity单元测试：四来源读取候选，rawalias每块500，candidate每块900调用原provider，按track顺序连接并保留目标canonical署名；不存在的可选表兼容，存在但缺必需列保持原OperationalError，tracks无artist_id仍支持track_artists路径。空candidate不调用“空即全库”接口；统计时间线、SQL、provider公共API、schema、缓存容量与排名合同未改。

最终24个新增fixture覆盖canonical alias、manual add/remove/set_role、Spotify自动及标题产品抑制、主艺人fallback、无primary列、未知/无署名、L1反向多源、2/4排序、1,200别名、坏表缺列及大曲目集。后者新增1,005首目标曲目，在999参数代理内以900/110两block解析，1,009个目标署名的全部字段与全库provider oracle一致。最终相关5模块181 passed/1 warning/19.35s、actual exit0；Ruff、format、mypy（follow-imports=silent）与diff-check均exit0。之前239项较广测试属于最后schema/chunk refinement之前，不能当作最后源码已测结果；中间mypy缺列表注解已修复并复验。证据`artist-credit-candidate-20261009/final-checks.json`及`final-*.log`。

冻结context SHA256 `aaa6588cf84fe3747197a6195006654d729f2818743561c65a5c0e0e14e70466`，unit SHA256 `0fd9e8c8be236272f71adaceb60089735a3248e12feb826f03d763a49f808545`。root独立确认13调用链仅context一份变化，其余12精确等9dd提交，保存`artist-credit-scope-before-binding.json`。旧OWNbackend4067正常Ctrl-C/exit0；新OWNbackend2740/PID1879使用相同runtime主库及六精确sidecar，warmup/search/L3startup均0、无reload，startup complete、health200、Vite5173实际200。首次个人HTTP前放行原45场景90样本矩阵（包含首Chrome360 cold6，不额外重复cold6）；API性能和完整全栈尚未启动，当前源码仍9dd+dirty R4而非新commit。

### 18.2 当前版本本地浏览器与API结果

原三驱动45场景90样本完成，包含首Chrome360 cold6；个人性能与DOM 90/90通过，原局部门槛track/album基础1.5秒、artist基础2秒及全部个人2秒未放宽。cold6基础/排名可见耗时（ms）：track2 428.28/369.64、track4 510.57/437.18、album2 580.95/406.51、album4 714.49/568.63、artist2 1,118.91/458.31、artist4 719.37/558.40；全部个人同基础。220窗口计入，3→4实际间隔48.1/48.5/64.7ms。全部180个人HTTP200、API/DOM误差0、计分和重排PASS；3对象额外请求、重排额外请求、legacy、溢出0。原矩阵功能44/45，driver exits=[0,0,1]：Firefox768artist有一条外链Spotify图片Image corrupt or truncated错误，原case的两个人样本、DOM、计分、性能及重排均通过；不将console错误忽略或写成原45功能全PASS。原始summary SHA256 `4570f7b56226f9c1fb5fbea9b2c1f83e51ad735e3b336373faa91b61b3081bbb`，目录`output/playwright/versus-personal/artist-credit-scope-local/`。

针对该新失败，授权一次独立Firefox768artist窄复验，原probe/预算/console规则不变，actual exit0、console空、DOM/计分/重排/溢出通过。新2/4基础及全部308.98/418.29ms，是自然warm独立观察，不替代cold6或原矩阵、不拼接成原45全PASS，仅证明这一次外链错误未复现；不证明CDN长期稳定或原解码根因。raw SHA256 `a6fc39a9b23c05b4f33fcc0842e918d0e5fa33be9a5eab55f66829541bb56f97`。13调用链、unit、probe/entities前后一致，6个关键UI文件精确等9dd提交且未改，旧9dd首次失败/R3本地PASS全部locked hashes守恒。完成窄复验后所有contexts关闭并释放CPU，才启动API门禁。

新96 API对账实际完成：48基础/48完整排名均与现有独立oracle相等，不重建全库oracle或维护排名；19源/owned源及预期文件不变，13调用链冻结，build/publish/enqueue均0。随后36独立进程（30fresh，各case5；6warm，各endpoint首次后21次）/324常规+120切换请求全部完成，130性能资源门槛全PASS、耗时114.482秒。fresh基础最大track288.12/album372.87/artist853.54ms，fresh rank最大20.04ms；same-process warm P95最大13.25ms，四对象新增采样峰值最大124.55MiB，20队列稳定新增最大6.64MiB；这些均为个人API probe，不能归为整页或发行周期资源。protected source/owned均守恒且相等、13版本前后相同、public builder/publish/enqueue0、保留全局play frame0。证据`artist-credit-scope-oracle/report.json`与`artist-credit-scope-api-run/report.json`。

root顺序门禁wrapper35319仍实际live，96对账和130门槛通过后才进入默认完整全栈run `20261009T060805.832990Z-9a0e06e6253c`。本轮没有--only/--from或跳过必需阶段，当前尚未实际退出、完整Pass待证明；运行时HEAD为9dd+dirty R4，后续固定SHA必须再次核对本次13绑定。线上仍9dd、原首次两艺人2.098秒失败未关闭，私有HTTPS外层恢复/范围调整仍待授权。

### 18.3 R4默认完整门禁收口

同run `20261009T060805.832990Z-9a0e06e6253c` 已actual exit0；selection=full、dry_run=false、overall_status=PASS，八必需阶段同轮全部PASS，总耗时1,435,402ms（23分55.402秒）。阶段ms：preflight8,164、quality72,745、backend521,378、api164,209、browser-routes399,520、browser-interactions79,444、browser-inventory45,922、browser-compat143,894；optional NOT_RUN。摘要`artist-credit-scope-fullstack-summary.json`及同run原始目录保留，没有重启或重复执行。

all-files Ruff/format/mypy/detect-secrets、前端787 passed/4 skipped（97文件通过/1跳过）与build通过；后端3,746 passed/5 warnings（289.57秒），真实集成187 passed/2 warnings（219.74秒）。API smoke157/157、boundary113/113、51目标slow_count0；51个warm组最大P95 223.14ms（Billboard data，门槛500ms），不将通用benchmark描述成独立cold进程证据。桌面/移动路由、交互、控件盘点、Chromium/Firefox/WebKit兼容均通过。AI后台线程disk I/O警告与R3同测试/同handler堆栈类型保留在原日志；AI/db源码未改，不扩展本次修复，也不据此宣称无警告。

root再次独立确认13调用链及unit文件与验收前binding完全一致；本次测量仍为9dd+dirty R4工作树，将以新commit blobs逐一绑定。另线程SS-2026-10-09-001规划、docs地图及共享文档行/小节完整保留并排除暂存。R4 S4收口，S5新固定SHA/正式CI/发布及公开首次仍待执行，私有HTTPS仍待授权或明确范围调整。

服务器入口追加只读刷新：06:30:10 UTC实际SSH退出0，Tailscale仍Stopped、原DNS仍spotify-stats.tail8916b1.ts.net、Serve空；3001 private-admin/full与3002 public-readonly/showcase均完整9dd SHA。证据`private-entry-investigation/current-route-state-refresh.json`；未修改Caddy、Tailscale或网关配置。

## 19. R4阶段提交与远端详情优化整合

阶段提交`9377ab8ea22f0113d22c1f3ae1bdc936025f20a2`实际退出0，7路径398插入11删除，hooks全部通过。root确认13调用链及unit commit blobs逐一匹配前述测试绑定，另一线程的主检出dirty内容完整保留。ready4现成清单verify/export/validate及SCP上传、远端摘要核验/原子改名均实际退出0；765,982字节、mode600，whole-file SHA256 `8fa71d972e08dafbe80fe315bbc67b177b32308079b591a09ac21289d9334acc`，源revision仍bb7cb368…、builder entity_rank_context_v2；没有build或补配置。

正常push9377实际退出1，non-fast-forward；未force或重写历史。fetch发现主线已整合详情优化，远端为`47147879287ca8e79cae257bc254b57402380865`。9377的正式CI/发布并未启动，上传清单不能当作已发布。实际471的CI37892112247通过，但ProductionRelease37892112260的deploy失败：详情manifest validated4/imported4后只读校验SQLite unable to open database file，随后恢复旧backend healthy、未替换live DB，清理import_control权限错误也保留；具体补修属于详情线程的安装链路，不冒称本对决已经上线。

root创建独立worktree `versus-detail-integration`、分支`codex/versus-detail-integration`，以9377合并471（--no-commit）。业务代码无冲突，两份共享文档保留本项最新记录和详情项远端记录，主检出dirty未改。R4 context和R3周期helper仍各自冻结hash；远端署名provider、identity、个人计次/时间线和rank合同未改，旧96独立expected可以复用，但须重新实际请求对账。

整合带来schema90（新增详情派生表）和Billboard builder v4；旧schema89/v3的runtime不能充当新版图表exact-ready，发布还需详情投影和全套Billboard成品。正在仅在新OWN副本尝试官方严格迁移/导入既有成品，禁止手工改key、公开冷建或维护其它线程源。整合版15模块相关回归312 passed/1 warning（24.77秒），实际退出0，涵盖本项5模块、详情稳定身份/L3精度、只读边界、发布和联合回退。该局部结果仍为Partial；原9377默认完整通过属于单独R4版本，整合版浏览器、96对账、资源、默认完整及固定发布仍待完成。

### 19.1 整合副本与完整个人专项收口

用户已授权协调两项任务。详情线程交付安装补修阶段提交`abc78d9101f5d097146aaf9c0f73e09cfda41e4f`；本任务统一最终整合、正常主线推送和正式发布，详情线程保留自己的生产90场景与HTTP/资源/联合回退验收。补修仅涉及部署、离线CLI、测试和文档，相对471没有backend业务或frontend差异；本任务在原未提交merge中保全自有文档后重新合并abc，两份共享文档冲突已保留两项最新记录。13个人调用链及unit逐项hash与此前整合版完全一致，证据`integration/deployment-fix-binding.json`；安装专项52 passed/1 warning、actual exit0，与此前312项回归分开记录。

七库Online Backup只生成本任务独立runtime；原OWN源DB/WAL字节、inode、mtime守恒，SHM读取标记变化明确分列。官方schema90迁移/验证、详情4投影与Billboard v4的48目标导入/验证均退出0；search4 strict-ready、四默认排名ready、94,760原始播放及19源表守恒。没有公开冷构建、修改来源、手工改key或维护其它任务源；原静态WAL-free副本guard打开失败保留，immutable只用于已关闭的静态guard，官方导入正常读取。证据`integration/runtime-readiness.json`与`runtime-ready-metadata.json`。

原cold6、Chrome其余场景及Firefox/WebKit驱动顺序完成，actual exits均0，所有context已关闭。整合版45/45场景功能与90/90个人性能通过、180个人HTTP全200；API/DOM事实、计分、重排映射一致，3对象额外批次、同集合重排请求、legacy、异常批次、溢出及阻塞console均0。首次2/4对象基础耗时（ms）：track333.57/495.06、album423.19/553.48、artist743.72/615.08；整轮三类基础最大565.85/667.66/864.23ms，原门槛不变。summary SHA256 `79251537c2b5b772a93be8517d030fcd24f09ac65445bf79b0ac2ebb112dc9ae`，证据`output/playwright/versus-personal/integration-local/`。该矩阵为新runtime真实独立矩阵，不覆盖旧44/45图片失败；teardown pending-task stderr原文保留，也不用于证明后端取消完成。

首次96 API对账中的48基础全部相等，36排名相等，但12项“包含精选集”排名因副本只准备默认四套而返回503。失败报告`integration-oracle/report.json`保留；随后从既有维护成品严格export/validate/install四自定义排名，未build，默认四套与其它发布、19源表、原维护源DB/WAL均守恒。完整重跑原96项、16过滤/实体组全部相等，旧独立expected文件不变，full oracle没有重新计算；公开builder/publish/enqueue均0、版本和源/owned事实守恒。正确报告`integration-oracle/report-after-custom.json`，实际退出0，不能把首次副本准备缺口抹去。

随后36独立进程（每case fresh5与warm21）、324常规和120切换请求完成，130/130性能与资源门槛通过，实际退出0，总108.315秒。fresh基础最大track111.36/album307.48/artist825.77ms；source/owned19表守恒且相等、13调用链前后完全一致，公开builder/publish/enqueue0、保留全局play frame0。证据`integration-api-run/report.json`与`integration-api-run.log`；资源为个人API probe，不能替代整页生产采样或OOM结论。

上述专项收口后才固定整合提交并启动新版本默认完整八阶段门禁；原9377默认完整Pass不能替代本次70余路径整合与安装补修后的完整结果。当前正式线上仍9dd，新的CI、三模式、部署及原首次公开验收尚未完成。私有HTTPS恢复授权/范围调整仍待用户答复；为两个任务提供独立生产首次测量所需的受控backend重启也须在具体发布版本健康后另行获得授权，协调授权不等于重启授权。

### 19.2 真实Billboard发布校验发现事务冲突与补修

整合提交`b4c69d16b0a693134494b44c3db351a4fce2c828`实际退出0，parents9377/abc，74路径；13个人调用链及unit commit blobs逐项与已测值一致，工作区干净。merge hooks仅检查冲突文件，未声称Python全量hook通过；随后默认完整run `20261009T072637.595852Z-3036b3d9dfcc`的preflight与quality通过（前端803 passed/4 skipped，99文件通过/1跳过及build）。发布准备并行发现官方Billboard verify退出1：新CLI适配器普通RO强制BEGIN，与`analysis_snapshot_revision.source_revision`既有“只读取已提交事实”的事务拒绝合同冲突；rank4/detail4三步骤已通过，但BB还未导出，未上传或push。原失败保留`release-b4c…/readiness.json`。

仅对精确匹配该run、8025的OWN test_storage_guard PID16,411发送SIGTERM，由其终止自有子进程组并清理测试临时目录，wrapper80081实际退出1。八阶段摘要overall FAIL，preflight/quality PASS、其它NOT_RUN，不能当作完整Pass或后端测试失败；终止原因和原日志保留`integration/fullstack-interruption.json`、`fullstack-summary.json`、`fullstack.log`。8025后端及5185前端没有停止，正式生产没有变化。

最小补修仅取消CLI适配器强制BEGIN，保留mode=ro/query_only、closed无WAL+immutable及前后dev/inode/size/mtime/ctime封锁，不放宽core revision拒绝/双data_version检查。新增普通活动WAL和闭库WAL header两模式的真实source_revision与真实Billboard context回归，同时证明写入拒绝和主文件摘要守恒；原52相关加新增2项，54 passed/1 warning/0.98秒，actual exit0。最初测试fixture错误移除仍有revision holder的辅助文件导致1项unable-to-open失败，已改为普通模式真实writer、closed模式始终sealed；失败日志另存，不归为新业务故障。

同现成完整副本以补修CLI实际执行48目标verify/export/validate，三个步骤均退出0，无closed-source/build/upload；payload digest仍`f738a65517dbd0d7382cb05005d8d280d197e84aa011460c1eca8ddb0c4c21fe`，89,769,316字节清单whole-file SHA256 `c54ff721b3e0aebe46a557bc44c8cbd2c56c83508e9f3ed586a1a0d6469c147a`、mode600。源main/BBsidecar及WAL字节/inode/mtime和CLI前后hash守恒，证据`trial-committed-read/report.json`。本次仍为b4+dirty补修，固定新SHA后才正式准备三manifest并运行新默认完整；本项13个人调用链及前端未改，既有45/96/130专项证据精确绑定复用，不重复预暖或修改阈值。

补修阶段首次固定为`ada5c65dff4c972fa90cd5e78ec3352da6c36d32`，hooks均通过，三manifest九步骤及600/SCP/摘要原子上传均退出0。默认完整run `20261009T074153.613449Z-0ed84e269c4d`实际退出1：preflight/quality PASS，backend在1,647项通过后新fixture的“关闭后必无WAL”断言失败，191.94秒/4 warnings；后续阶段未运行。失败发生在夹具初始准备，尚未调用适配器，不归为CLI/统计故障，也不以局部54通过覆盖该失败。

修正仅测试夹具：直接Online Backup静态portable seed避免其它测试的共享状态，显式checkpoint新自有目标，闭库模式确认零字节WAL后才移除本fixture的辅助文件，此时没有reader/holder打开；普通模式允许WAL存在并保留真实writer。业务、CLI实现、13个人调用链及前端不变；相关54项复验通过。旧ada及其已上传私密清单和失败run保留；尚未push或发布的本地补修阶段提交合入该fixture修正后重固定SHA，不重写远端历史、不forcepush。新完整门禁使用独立summary/log，不能覆盖前两轮失败。

## 20. 最终联合版本本地验收与正式发布启动

最终补修阶段固定为`6430d4de17ad2c909e4e3ba506546e462c3c14d0`（parent b4c），8路径84插入5删除，hooks全部通过。仅fixture/docs相对ada改变，三个离线CLI实现及所有业务源码相同；13个人调用链及unit、6 UI、probe和实体与已测45/96/130绑定完全一致。所有旧SHA、失败run和清单保留；主检出其它任务dirty未改。

该SHA默认完整run `20261009T075213.655349Z-147218655db1` actual exit0、full/non-dry/gitclean、八必需阶段同轮PASS，用时1,532,685ms（25分32.685秒）。阶段ms：preflight7,932、quality74,686、backend541,802、api237,154、browser-routes400,249、browser-interactions79,464、browser-inventory45,720、browser-compat145,548；optional NOT_RUN。后端常规3,829 passed/2 skipped/4 warnings，真实副本186 passed/1 skipped/2 warnings；三项skip均明确为Genius client not available。前端803 passed/4 skipped、99文件通过/1跳过及build。API smoke157/157、boundary113/113、51目标slow_count0、warm P95最大221.643ms（Billboard data、500ms门槛），不冒称独立cold样本。三浏览器兼容、路由/交互/盘点均通过。摘要和原日志`integration/fullstack-sealed-{summary.json,log}`；13+unit/CLI及19源表后核验守恒，证据`fullstack-sealed-binding-after.json`。

详情线程补充实际Linux stage业务复用证据：471现存linux/amd64镜像只读overlay最终相同三个CLI，在新owned副本迁移89→90、详情validate/import/closed verify4、BB validate/import/closed verify48，七阶段均actual0；四只读阶段文件state/SHA不变、三静态原件全state/SHA守恒、owned输出UID1000/GID1001、host cleanup成功、coldbuild0。报告SHA256 `2e736c3600f1de328bec71039b93f8502d4294a2deff1cfb438712ad0a21be83`，root核对三CLI commit SHA均相同；证据`integration/linux-stage-{report-copy,binding}.json`。这是实际FS/脚本兼容证据，不能替代最终6430实际镜像或正式安装。

为避免用旧471详情90冒充包含R4艺人优化后的最终版，在完整门禁结束后仅受控重启OWN8025：原session23405/PID12972精确SIGINT、actual shutdown0，新正常lifespan session58345/PID26687；5185保持，8000/5173/8013等不动。health200、schema90、done6,286/failed38、pending/running0，BB当前跳过构建，offline默认rank4/source bb7/v2验证0；没有个人或overview预暖。此处本地重启不代表生产重启授权。

随后详情root独占自然首轮90于08:27:21–08:30:46 UTC actual exit0、90/90通过（Chromium42/Fx24/WK24），freshcontext/PWA/原1000/2000/1500门槛保持；click core/all最大962.9/1,047.3ms，direct core最大1,295.6ms、shell后all最大525.5ms，pageerror/nonGET0、12项offscreen rank检查。v2 strict前后57来源/原37、五队列、21主发布与六侧全部发布、schema/epochs/fence/inode均守恒，access-clock变化0；所有context关闭。该90是详情矩阵，不能与本项45场景90个人样本混为同一矩阵。root独立读取复制`integration/detail-natural-{summary,guard-judgment}.json`，各SHA256为`c9feb565225183c5402cacf2bde2b6c9895cdd65881b9a9da2865246b3b03e6d`、`0e81dbcf5ee53abcc7f90f558a1003c970a0d9d6dc086e2c5bb2674e9886b6c4`。两项本地S4收口，不据此关闭S5。

最终SHA三manifest官方九步骤及独立600/SCP/远端摘要/atomicrename全部actual0，默认rank4、detail4、BB48，原19源和DB/WAL守恒，无build或源补写。rank whole-file SHA256 `7748598e8b5e872b5e2c380d1a1f6e115184464581fdf4c14bc363dffa18056a`，detail `ff918b224573c59f8e863f2ed3ac5cd702240fa8a9d5a5ac5c06f77d2468df05`，BB `c54ff721b3e0aebe46a557bc44c8cbd2c56c83508e9f3ed586a1a0d6469c147a`；回执`release-6430…/{readiness,upload-receipt,cli-binding}.json`。本地96含custom四套；生产96定义为公开48＋私有SSH48，均只覆盖默认四套，不混淆或额外安装custom。

root fresh fetch确认origin/main仍471，sourcebinding/gitclean/双项本地矩阵和三清单都满足后，正常push actual0（471→6430），未force。08:34:19 UTC正式CI `37905772987`、ProductionRelease `37905772875`、NoDeployContract `37905772855`实际启动，均完整6430 SHA；08:40:05 UTC三个Backend unit step success，进入contract、run仍in_progress。三模式、镜像、部署、独立服务器和生产首次尚未完成，不称生产Pass。沿同实际run继续，不人工重触发。私有HTTPS恢复/范围调整及两项独立生产首次所需额外受控backend重启仍待授权；外层入口不擅自改变。

### 20.1 正式安装失败，独立核验旧版保持

最终CI `37905772987`、NoDeploy `37905772855` actual success；Release `37905772875`质量、三模式、linux/amd64镜像成功，deploy job `113742754780` actual failure。安装日志证明详情validate/import/ready4、Billboard validate/import/ready48、目标个人rank validate4均通过。08:53:05 UTC `backup_versus_rank_release`调用current_tag旧9dd镜像导出旧个人排名供回退使用时，`versus_personal_context.context`在两次重试后仍检测PRAGMA data_version变化，严格拒绝为`Personal statistics source changed during revision collection`；没有替换live主库、安装live sidecar或启动6430版本。日志原文保留`release-6430…/workflows/failed-job-113742754780.log`，不把新详情成品verify前的预期缺失误当终止原因。

08:53:21 UTC旧backend恢复Healthy；独立只读SSH实际退出0，三容器OCI均为完整9dd、healthy，schema89、94,760播放。相对旧9dd beforeguards，19源表、完整background_jobs、全部Analysis和个人排名发布逐项相等，done6,283/failed38/pending/running0；证据`failure-production-receipt.json`和`failure-rollback-guard-comparison.json`。新版未上线，生产首轮、资源和API尚未开始；没有暖重试、手工重跑或额外服务重启。下一步只在新owned副本重现旧rank回退导出的文件/连接边界并修最小部署步骤，保留严格source fence和联合恢复门槛。

### 20.2 旧rank回退读取副本复现与最小部署修正

只在新owned目录复制本次两份已关闭pre-release备份，原备份stat/hash前后相等。真实旧9dd镜像/SQLite3.46.1：闭库noWAL独立布局和同host双alias布局，先因copy新inode不匹配旧key返回unavailable，随后只以官方installer将现成四份排名重绑到OWN sidecar；旧CLI导出均actual0，16次data_version均1，文件state/hash不变。该结果不能把copy lineage缺口归为本次部署ValueError，也未证明alias本身导致失败。

随后将观察到的post-restore SHM只读复制到闭库OWN主文件旁并创建零字节OWN WAL，明确是构造布局，未捕获失败瞬间SHM/WAL。真实旧CLI普通mode=ro导出actual1，PRAGMA data_version依次5→69、70→134、135→199，复现同`Personal statistics source changed during revision collection`；main/WAL/SHM字节、inode、mtime及SHA均未变，没有并发writer。noWAL immutable布局则导出成功，原严格context/data_version检查未修改。副本复现支持checkpoint/闭库后再执行严格旧成品gate，不声称已确定生产失败瞬间的全部文件状态或外部源写入。

rank-only演练以真实旧镜像运行原main硬链接保留→新inode候选提升→现成四份安装→原inode与完整Analysis Online Backup恢复，旧CLI前后四manifest逐项相等，所有20条Analysis发布完整行/元数据相等；提取本次dirty共同gate的三文件RO/immutable/stat-fence和实际rank4部分，before/after均actual0、无WAL、无builder。Billboard导入及ready调用在该rank-only探针中明确排除，不能据此宣称完整旧BB48恢复。两wrapper均terminal actual0；报告`release-6430…/rank-export-diagnosis/diagnosis-final-report.json`，root独立确认SHA256 `7855c2395a90e2fa8780bc30a4d1e183d3d3dd1a003b36eb8bbfdbbd6e439cf0`，原始returncode/trace/备份保护保留。

最小修正只涉及部署：目标成品校验后先checkpoint/保留原main inode，共同closed gate验证旧Billboard与实际四默认rank；随后完整Analysis备份，缺原inode硬链接即拒绝。移除用于旧“新inode回退”的冗余旧rank export/install；回退恢复原inode和全部旁库后仍共同exact gate，再允许旧镜像activate。目标rank validate/install/verify、core revision/source fence、个人13调用链、unit、前端及三个CLI均未改变。修正初次相关62项actual0/9.20秒，shell语法、diff和155文档审计通过；新增真实rank gate回归与完整owned共同恢复仍在执行，尚未commit、推送或再次发布。

新增实际SQLite/rank回归覆盖原inode＋全Analysis恢复、缺/损rank、同事实新inode和三库空/非空WAL六种拒绝；仅Billboard callback为明确fixture，rank/default/source合同真实执行。首次1 failed/9 passed（本机SQLite3.51 closed-header普通RO备份内部副本无法open）保留。真实6430 Linux镜像SQLite3.46.1对原生产备份Python主体的DELETE/noWAL、closedWAL-header/noWAL、真实4152B committedWAL三个微型样本均actual0、integrity ok、事实11/22/33&34全部齐全，原源stat/hash守恒；没有执行候选生产修补。报告`tiny-offline-backup-report.json`，root确认SHA256 `1f64730d83fdb06d200997fc13b709a151e82ff2bc125a8c4b77bba0f4866b6f`；首次仅owned生成器chmod失败原文另保留，不算备份主体失败。

只在本地测试adapter的内部disposable reader-copy为SQLite>=3.51建立query_only holder，保持原普通RO和真实Online Backup主体，正式fixture源保持closed/noWAL且不改header；Linux3.46不使用该shim，生产备份代码未改。限定10项actual0/8.77秒、模块29项actual0/9.47秒、最终四相关模块72 passed/1 warning/17.55秒 actual0，日志`rollback-actual-ranks/`；Ruff/format/diff/shell和文档审计通过。该结果不代替完整旧BB48共同gate，正在仅新owned副本按冻结真实三hosthelper执行一次完整演练；业务矩阵按逐文件绑定复用，不重复96/130/两项浏览器预暖。

单次完整owned恢复报告随后actual `status=passed`，16个阶段仅在subprocess退出0后记录；真实9dd/6430 linux/amd64镜像、最终三个hosthelper逐项hash匹配，schema89→90、aux4/BB48/rank4、新inode提升与原inode恢复、全部Analysis/BB backup字节及原完整语义行、旧rank4/BB48、37原来源及完整保护事实全部守恒。三个独立旧镜像公开只读overview均200/found=true，主库/旁库字节及行前后不变，旧exact前后true；rank coldbuild0、owned cleanup完成。host最低1,407.758MiB、每阶段OOM delta0。此演练只证明本次自动联合恢复候选协议，不证明成功后manual rollback，也不称下一SHA镜像已构建。

root独立读取报告并逐项断言、复制`integration/owned-joint-automatic-restore-6430-report-copy.json`，SHA256 `848837e6e9a8c61524346c11cc5b4000b908d29ada26626893b5f602e8d59a79`；host三helper匹配与判定`owned-joint-restore-binding.json`。原server报告在`/opt/spotify-stats/backups/owned-joint-automatic-restore-6430-20261009/report.json`。报告生成/cleanup后原SSH未收到EOF，owner只读确认远端没有rehearsal子进程，随后仅终止自己精确匹配的本机SSH传输，session34826最终255；不得写为整SSH wrapper exit0，也不因传输收尾再次演练。数据判定依据为真实报告及已完成16阶段，不把SSH异常覆盖为success。部署补修验证收口，固定阶段提交后运行新SHA必要默认完整并准备同源成品统一正式发布；S5仍待生产首轮与私有范围决定。

## 21. 部署修复固定版本与第二次正式发布

部署修复阶段固定为cb8d05b14813fcc5333e46402fcbcde0089c36be，parent6430，11路径366插入31删除。首轮hook格式化一处测试长行退出1，精确暂存后提交退出0，hooks全部通过。业务与三个CLI不变，原45/90、96、130及详情自然90按commit blobs与实体绑定复用。

唯一必要的新默认完整run `20261009T094929.575812Z-954fd3885f46` 实际退出0，full/non-dry/gitclean、八必需阶段同轮PASS，耗时1,488,756ms。阶段ms：preflight7,609、quality70,514、backend561,654、api172,657、browser-routes400,243、browser-interactions79,675、browser-inventory47,380、browser-compat148,865；optional NOT_RUN。后端3,840 passed/2 skipped/4 warnings，真实副本186 passed/1 skipped/2 warnings；API51目标slow_count0、500ms标准不变，三浏览器通过。摘要SHA256 `7e46849cdaae887c7b32a4d9edeb8130586f634da20c8c5b61c2a31a31e2831a`；证据 `integration/fullstack-rollback-fix*`、`rollback-fix-full-receipt.json`。前后HEAD、21文件、19源表、schema90和jobs计数完全相同，done6,286/failed38、无pending/running；binding前后文件分列。

三现成成品官方九准备步骤全部0，cold build和源写入0，源19表及main/sidecar/WAL字节和身份不变。rank四套真正导出绑定cb8，文件SHA256 `9ecf0e097a7b16378ef3ca7d9d58a611facbb5ab0f210233fb91378186314539`；详情4/BB48字节和payload摘要与6430相同，payload没有release SHA，文件名绑定cb8。私密上传五步骤全部0、600/远程checksum/atomic rename通过，旧成品保留；证据 `release-cb8d05b14813fcc5333e46402fcbcde0089c36be/{readiness,upload-receipt}.json`。

详情线程在push前唯一采集旧9dd/schema89 v2，57保护表/37原表、reader已关闭。服务器起10:16:53.362498UTC、elapsed36.408769秒，结束时间由单调耗时推导。采集subprocess0，receipt对整数执行len导致wrapper1，原错误保留，仅修receipt未重复SQL。capture SHA256 `0654263f7735b02f5a3c7fdb053e6578893ae46b45df848b215d1e8f3ef8fe36`；原pre/post身份相等断言成功与独立post重验分列，不虚写遗失的原metadata，不声称辅助文件stat守恒。

根正常push6430→cb8实际0，新CI37916999633、Release37916999607、NoDeploy37916999587于10:20:34UTC触发。当前检查运行；实际上线、独立核验、生产原首次公开14/28、整页资源与两面API均待完成。私有HTTPS及详情独立首次测量所需额外受控重启待授权，S5不关闭。

### 21.1 正式发布容量预检失败

新CI37916999633、NoDeploy37916999587实际success，Release37916999607的质量、三模式和镜像job均success；deploy113781382823在10:40:33UTC实际failure。Online Backup完成后，音乐搜索副本容量预检拒绝：disk_available1,198MiB小于disk_required1,695MiB，日志明确线上服务与数据库保持原状，尚未停服或安装；不能称旧rank步骤已经生产验证成功。MemAvailable被GitHub遮罩，不推定具体数值。失败原日志/逐job回执完整保留，监控session20207实际1，无盲重跑。

随后根只读独立核验实际三个OCI均旧9dd/healthy、schema89、播放94,760、19源相等、done6,283/failed38、无pending/running。完整jobs、所有Analysis与排名元数据和上次失败后旧9dd guard完全相等，证据 `failure-production-receipt.json`、`failure-original-guard-comparison.json`，采集实际0，个人HTTP0。

只读空间盘点找到本任务诊断目录的source和dual-data两份444,588,032字节副本，独立inode703091/703105、各单链接、没有fuser报告holder。两文件SHA均e14ca5facafb196dbbc4da17dd9ebbf2c341c9b6b53a203ceb17feee9bcbc851，与保留的正式pre-release-6430备份inode702898字节相同。精确删除这两份可释放848MiB，正式备份和所有日志/报告保留；范围 `disk-cleanup-plan.json`，删除和同SHA失败部署重试的具体授权已询问，尚未执行。S5继续开放。

### 21.2 精确清理完成与授权重试仍受容量拦截

用户在协调聊天明确“确认清理，你帮我指引它们一下”，授权仅原指定两份诊断副本及清理后一次同SHA失败部署重试。根删除前复核普通独立文件、单链接、inode、whole SHA、canonical完整及fuser无holder；精确两文件删除actual0，释放889,176,064B（848MiB），可用空间1,699,594,240→2,588,778,496B，canonical backup完整record不变。其它文件未删，receipt `disk-cleanup-receipt.json`保存。

随后仅一次 `gh run rerun37916999607 --failed` actual0（10:52:26UTC），第二尝试deploy113786212282在10:54:32UTC actualfailure：Online Backup后disk_available1,167MiB<required1,695MiB，仍未停服或安装。原attempt1和attempt2日志/回执各自保存，session52654实际1，无第三次部署。第一次空间估算漏算部署中的额外分配，不能把host当前可用量当作预检点余量。

只读脚本顺序确认预检前至少新Online Backup和cp stage各444,588,032B；实际incoming transport tar另有475,238,400B独立副本，不能依赖下一轮复用。第二具体清理方案仅四文件：471失败备份062616、cb8失败备份104024/105422，与保留6430正式备份whole SHA完全同；cb8 incoming docker-save.tar与保留records tar whole SHA完全同。六文件独立inode、目标单链接、fuser无holder。拟释放1,809,002,496B，按再次新backup+stage+完整tar重建1,364,414,464B扣除后，预检点估计2,014.461MiB，比原1,695门槛多319.461MiB；执行前还须新鲜复核所有文件及至少256MiB预算余量。新范围超出原授权，已请求具体授权，未额外删除或第三次重试。证据 `disk-second-readonly-inventory.json`、`disk-cleanup-second-plan.json`。

### 21.3 第二道门禁与替换阶段预算补充

2,014.461MiB是预检入口余量估计，不能当作全流程剩余空间。复用现有真实6430成功预检JSON确认before444,588,032B、after445,292,544B、exact resume reuse且storage delta0；第二道门槛为4×resume（1,698.656MiB），当前resume实际文件445,292,544B/noWAL。source与CLI冻结，原两道门槛不改；不是新预检Pass。

预算另计resume临时文件与整库WAL重叠、replacement、两份quiescent主库、详情stage增长、完整Analysis备份、BB备份/stage/再次替换，以及新main与保留旧inode同时存在。stage/promotion按同源OWN集成full8最大main659,550,208B规划（详情prepared643,862,528B），BB stage和replacement各64MiB，高于现有35MiB与prepared9MiB，Analysis原1,744,896B。晚期main/BB复制峰值预计约169.301MiB剩余；这是观察值形成的规划余量，不是严格数学最大值或未来通过证明。详细 `disk-full-release-budget.json`。准备脚本删除前新鲜空间重算，入口余量至少原门槛+256MiB、晚期规划余量至少128MiB，否则不删/不重试；四文件范围不变，仍待明确授权。

### 21.4 第二次精确清理实际完成与第三次部署请求

本聊天用户直接“授权清理”，授权第二次指定四文件及清理后一次同SHA失败部署重试。删除前新鲜复核六文件路径、普通文件/非symlink、设备/inode/单链接、完整字节SHA、目标fuser无holder；三个目标失败备份与保留6430正式备份完整SHA相同，目标incoming tar与保留records tar完整SHA相同。入口原门槛外256MiB及晚期规划128MiB余量检查通过，生产门槛未改。

唯一SSH清理session35469实际exit0，2026-10-09T11:34:16.776705Z完成；仅指定四文件删除，释放1,809,002,496B（约1,725MiB），可用1,661,431,808→3,470,450,688B（约3,310MiB）。两份保留文件完整record前后一致，其它备份、报告、镜像及CAS未删除。fresh预计入口2,106,036,224B（约2,008MiB），晚期规划约163MiB；预算通过不是未来部署Pass。证据`disk-cleanup-second-receipt.json`、`disk-cleanup-second-command.json`及更新后的`disk-cleanup-second-plan.json`。

先核对Release37916999607实际attempt2 completed/failure及唯一失败job113786212282，再且仅一次`gh run rerun 37916999607 --failed`。session10657实际exit0，请求11:35:10.265839→11:35:12.296265Z，目标完整cb8 SHA、下一attempt3；证据`deploy-rerun-third-receipt.json`。此时第三次部署结果待核验，未以请求成功声明上线；原两次失败独立保留。独立runtime、生产原首次14/28及资源/两面API仍待实际部署后执行；私有HTTPS及额外受控重启授权仍独立开放。

### 21.5 第三次部署容量通过、旧闭库联合门禁拒绝

Release attempt3 deploy113800562035实际failure，11:40:58UTC完成；monitor实际exit1。原before/after容量与search4预检通过，随后停旧backend。详情4变体和BB48在stage完成validate/import/strictready，rank4 targetvalidate通过。11:40:42UTC preserve旧main inode前联合gate `state()`抛出`Stopped exact gate requires no WAL file`；未promote，未安装新镜像。流程启动原backend，11:40:58UTC日志Healthy，并明确拒绝发布。完整日志和receipt独立保留`workflows/attempt-3/`，不覆写前两轮失败。

根仅一次只读现场采集（无个人HTTP/维护）：11:43:37UTC确认三OCI仍完整9dd、全部healthy、schema89、19源逐表与原基线同，jobs6,283done/38failed/无active。恢复后metadata显示main零字节WAL、BB/Analysis无WAL，但这是恢复后的状态，不能反推失败瞬间具体库或WAL内容；原日志未记录路径。证据`failure-readonly-receipt.json`、`failure-live-file-metadata.json`与完整source guard。

冻结代码存在准备合同缺口：`preserve_live_database_inode`仅checkpoint/处理main副文件，联合严格gate却对main/BB/Analysis三者检查任何WAL（包括空文件）。本地成功fixture与先前owned恢复预先关闭三库，未覆盖此准备状态。此时正在隔离tiny副本及Linux旧镜像复现，尚不认定具体侧库就是生产根因；Online Backup实现只copy来源到内部/tmp再读取，不能称其主动创建正式来源WAL。门禁不放宽，未知非零WAL不删除。本次授权重试已实际用完，不再发布；S5继续开放。

### 21.6 隔离复现与三库闭库准备补修

旧9dd真实Linux镜像/SQLite3.46.1、OWN tiny三库测试实际wrapper0：原RO copy-backup没有改变来源文件，也未生成来源WAL；在真实imports之前instrument SQLite connect，导入至gate捕获前调用数0。不能将生产WAL归因于备份或模块导入。Analysis/BB分别空WAL及真实4,152B已提交WAL共四例，原main-only准备保留侧库WAL，原gate均准确拒绝且文件不变；这是确定的准备缺口，仍未证明生产当时具体库。原报告wholeSHA`a1a7fd3f1a5a2a0b506289a7acba24bb12d7cce4ef7a4573d67676758117e257`。

最小补修仅生产helper：同一TRUNCATE SQL扩展至三个已存在库、mode=rw拒绝新建；全部checkpoint成功且确认无非空WAL后，才处理对应空WAL/SHM、保留旧main inode并进入原严格gate。忙锁或未合并帧拒绝，任何WAL仍阻止immutable读取；报错增具体路径。完整Analysis备份/联合恢复、源fence和原成品门槛保持。相关四模块83 passed/1warn/28.08s；初次误填测试路径exit4、fixture子进程环境4failed/79passed均单列，修正仅隔离env。formatter后五项新增真实回归5passed/29deselected/7.82s。覆盖两侧库×空/崩溃writer真实已提交WAL、完整Analysis与实际rank4、稳定文件状态/原main inode，以及pinned reader busy拒绝和非零WAL保全。

新helper固定SHA`71e03de656a3a006a028e9dbab5ac8c84841f70ceb95e911dcfef36c82abdbab`的LinuxOWN tiny真实checkpoint/preserve四正例actual0、提交行保留、三库inode不换、hardlink同inode、最终无WAL。Analysis真实pinned reader负例actual1且路径明确，main/非零WAL的inode/size/mtime/hash保持、未gate/link，SHM的SQLite bookkeeping变化单列；reader释放actual0，wrapper41363最终actual0。新reportSHA`15837e101a1215754269a1bac88e98f5b418cee7f4d2b5b5c17254ba2d2bbc5f`，同目录原字节/退出记录齐备。这仅新准备/封闭读取前置验证，不冒称完整BB/rank ready或新镜像验收。业务13链、4CLI及6UI与cb8完整门禁绑定相同；新patch没有新的默认full8，旧cb8full8只复用其原业务边界。未再次推送/部署。

第三次失败新增main备份444,588,032B、incoming tar475,238,400B及BB备份35,139,584B，已只读确认分别与保留6430正式main/BB备份、cb8 records tar完整SHA一致、普通单链接无holder。拟三文件范围约910.727MiB；仅两文件的晚期估计126.602MiB不满足128MiB，方案已标superseded而未执行。三文件fresh估计入口约2,004.53MiB、晚期约159.371MiB，仍须执行前重算，原生产门禁不变，不称未来Pass。精确三文件及新修补版一次发布仍需新授权，不额外删除或重试。

### 21.7 c587本地固定、新SHA成品准备与完整新范围

本地阶段提交`c58775f0df53ec05d2524a06b84f3b9945b6d024`（parent cb8），8明确文件225/18，ruff/format/mypy/detect-secrets hooks全通过，提交后工作树clean。未push/未deploy。新SHA三份原成品verify/export/validate九步actual0，rank4/detail4/BB48，source19与原同、四输入DB/WAL字节/身份保持；总清单153,432,401B。rankSHA`198bd602956b1246f7841509ed446e19a03f424dce30874687bcf86b7294d0a2`；detail/BB payload与cb8同，新文件完整SHA分别ff918…/c54ff…。未上传，`release-c587…/prepared-local-release-receipt.json`。

新SHA预算另计清单153,432,401B及64MiB新CAS/镜像规划余量，此前只按同版重试预算形成的三文件方案不足，标superseded、不执行；两文件/三文件所有历史估计保留，不降低余量标准。唯一额外候选是已不用的历史OWN详情准备源`spotify-stats-music-detail-108a5f41-preparation-20261009.db`，444,588,032B/inode702701/600；普通读取PermissionError记录，后续仅sudo -n只读完整hash/metadata，无chmod/写入。SHA`a54d117c34c3cee230dcddf2715e1cda969fef6904810fbc8224283b891262c4`，与根独立核验的本地完整`production-preparation/current-runtime/source.db`相同，详情任务确认不再是S5必要输入，既有原报告保留。不能称它与当前正式库字节相同，清理依据是历史OWN可由同SHA本地完整副本恢复。

新审阅方案仅第三次失败main备份、incoming tar、第三次失败BB备份和上述历史OWN四文件，共1,399,554,048B（1,334.719MiB）。前三个保留对应正式server文件，第四保留完整local源。最新观测可用2,509,742,080B；计入前述新SHA额外分配后，预计入口2,216.664MiB、晚期371.504MiB；执行前fresh核验文件/保留副本/holder及原after门槛+256MiB和晚期128MiB，否则不删。实际新CAS/镜像若超64MiB需重新核算；规划不称严格最大值或未来Pass。ignored `RELEASE_APPROVAL.md`和`exact-four-cleanup-and-release-plan.json`提供精确路径及身份。

此前“授权清理”四文件及同cb8一次重试均实际完成；新增四文件和c587新发布是另一范围，仍待具体人类授权。授权后最多一次新固定SHA正式发布；额外重启与Tailscale/私有HTTPS范围独立保持，不把局部新helper验证或SSH HTTP称完整生产验收。

### 21.8 人类确认后四文件精确完成及单次c587发布启动

根通过read_thread核实协调聊天真实userMessage“可以，继续下一步”（turn01a12096-8624-7e01-b014-5576e638df3f）及其上一条具体RELEASE_APPROVAL.md提案：仅新增四文件、保留对应server备份/record及本地同SHA源，再正常推送c587并正式发布一次。额外backend重启/Tailscale/私有范围不在授权内。

唯一sudo Python精确清理session19237 actual0，12:17:11.479969UTC。新鲜核验目标/三server保留文件路径、普通独立单链接、inode/设备/字节/模式/SHA、四目标fuser无holder，local源wholeSHA/身份清理前后相同。只删原四文件，释放1,399,554,048B（1,334.719MiB）；available2,507,964,416→3,907,534,848B，server保留完整record全同。含新manifest+64MiB余量后的入口估计2,322,579,119B、晚期387,788,463B，fresh原规划余量通过；不称未来Pass。`cleanup-command.json`、`cleanup-receipt.json`与更新授权状态计划保留，未清其它备份/报告/CAS/images。

私密清单上传五步actual0：三个文件600、完整SHA匹配后原子rename，旧清单保留、staging不存在。root正常fetch确认origin/main仍cb8，source/helper和未暂存四docs白名单检查后，正常push cb8→c587 actual0（12:20:18.297189→12:20:21.210780UTC），未force、未新增碎片提交。新CI37929372415、Release37929372279、NoDeploy37929372233于12:20:24UTC真实启动，均完整c587 SHA，沿本轮attempt1，不盲目rerun。此时实际安装/独立runtime及原首次验收尚未完成，S5开放。

c587原14/28FIRST计划哈希3303d8553553fd1c9745a0d6454ccbc3a30a053f7b636845d6b612d23294e1dd已离线冻结；PRIMARY API执行器新SHA绑定/原96expecteds/guards/500ms及未来420秒资源冻结，旧所有证据保持。任何生产UI/个人API/采样尚未执行，先实际所有jobs成功、三OCI/host三helper精确hash、合法surface/SHA、4/4/48ready及startup settled，再按before/采样第一点/原UI顺序开始。

### 21.9 c587正式安装与独立只读核验

本次单一attempt1三workflow实际全部completed/success：CI37929372415、Release37929372279、NoDeploy37929372233，11实际jobs全success；deploy113822444726，完整workflow回执captured12:45:30.660398UTC。质量、三模式、镜像及实际安装分别成功，不以CI替代生产。固定c587版本准备后三库checkpoint进入原严格联合门禁并完成安装，未降低容量、无WAL或源fence门槛；部署过程初始旧详情exact探测unavailable后按既定成品安装，最终detail4/BB48/rank4复核均ready。完整deploy log 89,896B及600回执独立保留，不覆盖cb8三次失败。

冻结verifier SHA5127e1413abb286946240ac2665222c6c75fa0bf9f585909bcdd6175b0376666唯一执行session99676 terminal0、全部8步骤0。三OCI完整c587且healthy；实际3001 full/private-admin及3002 showcase/public-readonly releaseSHA相同、只监听loopback。宿主三部署helper及容器13调用链/4CLI共17文件hash全匹配；schema90、search4、rank4/source bb7cb36811f58d12c3f285e9c3861a8c777c70a4c00b5dcb1b81062b4a9feb2e、detail4、BB48/v4均ready。production-verification.json wholeSHA40ca5829b92e3af6cfed7f6739b3a4a2c94c27610ecfbbe071046d8bf6b337b9，业务个人请求0，无预暖/维护/重启。

初始12:46:43UTC jobs done6292/failed38/running1，治理快照启动维护仍在运行；此时不准入浏览器。根12:47:43.897570UTC仅复查jobs/schema，done6293/failed38、无pending/running，维护自然结束；原初始证据保留，未清队列或改状态。准入本任务独立browser-before完整guard、实际uvicorn PID/startticks及420秒/500ms整页sampler，必须首条sample真实落盘后才开启原公开FIRST14/28；本节尚不声明浏览器、资源或96 API通过。私有HTTPS及详情独立首次所需额外受控重启仍待具体授权。

### 21.10 c587原公开首次与自然完整资源窗口

原公开同源HTTPS FIRST14场景/28个人样本，实际UTC12:50:01.754819→12:52:23.198556，五driver真实exit[0,0,0,0,0]，所有contexts/browser关闭，随后不再UI访问。原六cold样本Chrome360、歌曲2/4→专辑2/4→艺人2/4；随后十一场景自然warm，360/390/430/768/1280与Chromium/Firefox/WebKit原矩阵不减。无额外idle、预暖、私有转发或warm重测。独立纯离线原base≤2s/allpersonal≤3s判定actual0：14/14功能、28/28性能PASS。原cold6 base/allpersonal ms分别歌曲584.12/745.48、专辑786.76/1090.43、艺人1668.73/1180.19，包含220ms选择稳定窗，third/fourth gap47.9/47.9/46.7ms。

全部28基础/全部个人最大1668.73ms，排名最大944.74ms；歌曲/专辑/艺人最大745.48/1090.43/1668.73ms。56/56个人HTTP200、API/DOM/最终计分/重排映射与ready/current精确source匹配；batch异常、中间3对象请求、重排新个人POST、legacy详情stats、document overflow、blocking/accepted console均0。13调用链+unit/6UI/probe/entities/HEAD前后冻结与计划同；旧9dd首轮失败证据完整且不变。原始timings、日志、28截图、UTC边界、五退出与afterbinding分别保存。production-summary SHA9f23e81b89812ed4eeee4e80894e4cc3a3dc25b1638b0b7cfcaca430c212cdc2，阈值judgment SHA4dc0ef457ed3a2da1fe38af50fb55f152d90eb06cd4b81729589d2bf2d797df0。

整页资源原500ms/420秒SSH采样session2040自然exit0，end duration_complete/420.00009秒/no signal，840sample sequence0–839连续，stderr空；unique uvicorn PID1488259/start_ticks137303694前后和每样本一致。sample UTC12:49:16.785→12:56:16.285、end12:56:16.785，完整覆盖上述实际UI窗口。RSS首950.711→峰/末1144.0625MiB，新增193.3515625MiB，末20sample稳定；CPU新增41.94秒、MemAvailable最小1853.117MiB。数值属于整个页面及资源窗口（含榜单/发行周期和窗口余时），不归单个个人API、不以lifetime VmHWM充cohort峰值、不据此关闭整体OOM或冒称物理真机/P95。500ms采样可能遗漏更短峰值。

process-after及browser-after完整capture均0，guard judgment12check全true：schema90、19源表/94760播放与9dd完整digests相等，所有jobs字段/全部Analysis payload+metadata/rank metadata前后相同。JSONL SHA f0d0f7890cdc9c80cdb7330b8bde79147dd02ac81677d4540b3087856c09757a。primary release-c587目录原before/after/guard/resource完整保存；没有提前kill采样。资源/本项公开FIRST已通过后，才准入独立公开48、私有合法SSH HTTP48和三denial，各自完整before/after守恒；结果仍待实际执行。私有HTTPS与详情独立首次仍未获准入。

### 21.11 c587两面功能、公开拒绝与剩余边界

在本版原公开FIRST/自然资源窗及完整守恒全部通过后，才顺序执行原公开48、合法私有SSH HTTP48、独立三public-denial。两入口原完整七参数/四filters×三类×2/4对象×stats/ranks共96请求，实际各execute0、96/96HTTP200；原六基础指标/三范围排名、versus_personal_v1/context/source bb7完整值、实体顺序及每filter一个精确rank key/共四distinct keys全部PASS。没有重算oracle、改原expecteds、暖retry或维护。公开guard bracket12:58:46.659514→12:59:43.943965UTC；私有request13:00:39.831337→13:00:46.474934、guard13:00:26.907397→13:01:28.128294UTC，bracket不能冒称单个HTTP时间。功能测量不算fresh进程/P95/独立私有浏览器性能。

私有只经本任务owned127.0.0.1:19000 SSH→远端合法127.0.0.1:3001 full/private-admin网关，capabilities前后完整c587/surface/policy全部正确，无造可信header/直连backend。唯一forward create0、control-close0，13:01:44.729958UTC关闭，仅结束owned SSH、没有后端signal。该证据为private-via-ssh-loopback-http，明确不是私有HTTPS。

随后唯一public-denial三GET：/api/admin/cache-stats、/api/jobs、/api/jobs/__versus_probe__/status，实际原状态404/404/404，execute0；前后capabilities完整c587/public门禁通过，requestUTC13:02:15.273745→13:02:15.773266、独立guard13:02:07.651041→13:02:25.246568。三个cohort before/after capture及judge各0、各12check全true：schema90、94760播放和19源digests与原同，所有jobs行/全部Analysis payload+metadata/rank发布元数据完全守恒。三judge同wholeSHA47c38d0ac019a3cb8130e9f32999dc0fda5172226e23b1d09910ecae1bd934f1。它们证明零观测持久副作用，不是内部builder调用计数器；本轮未调用维护/build/publish/enqueue端点，函数禁止fallback的代码/专项回归证据单列复用。

PRIMARY新release汇总api-denial-acceptance-summary.json SHA cc613072d7e5b14ef00c72534d23d8258d2aadc05ca7e79585a7e72dfbb2b4ab，公开functional SHAab70569545fcd214a49c43346bbbf67005f0d497d2bb1c1d3923d54023de28bc，私有functional SHA6c7a55054b163f510fdafe1baa78bbc875e61c5f80adc4ef18bd78ce09f79e44，denialfunctional SHA1981221e1febbb44b307658da7b9d9e68677f1d7c517772e4e3984914f7b63c5。原脚本hash仍same、sourceoracle不改，所有原raw/UTC/exit/guard齐备；本任务生产访问已停止。

13:01:15.068061UTC根仅SSH只读再次确认Tailscale BackendState Stopped、WantRunning false、Serve配置{}，Self DNS spotify-stats.tail8916b1.ts.net.；命令均0，没有服务或配置修改。原私有HTTPS https://spotify-stats.tail8916b1.ts.net 的历史入口经Serve到full3001，当前尚不可用/未验。本项公开HTTPS已验证，原计划双HTTPS S5仍Partial，不能由SSH HTTP替代；本轮范围调整或恢复Tailscale须真实人类决定。详情独立原FIRST90所需额外一次受控backend重启按其规划5.2另行授权，在根上述全部窗口结束后才可执行，不把正常部署重启重复借为独立first。两项实现、正式发布、各自首次与整体OOM分别登记；不将本项193.35MiB整页RSS变动推论为整站OOM修复。

### 21.12 人类公开范围决定与唯一详情受控重启交接

本聊天真实用户对call_41e1314e381d4ec9b4dcacf1e4b14698明确选择“仅验收公开 HTTPS，保留私有入口现状”及“授权这一次受控重启并继续详情验收”。本项验收范围正式从原双HTTPS调整为只验公开HTTPS，私有不启动、不改Serve、也不虚写其Pass；原私有SSH48仅作为补充功能证据。对决SS-2026-10-08-002的S0–S5至此完成，完成规划移入archive/06-productization-closeout/，原失败、各版本与范围调整历史完整保留。详情SS-2026-10-09-001的独立首次及整体OOM不随本项关闭。

独立详情首次的一次受控重启已有具体计划，target仅spotify-stats-production-backend-1，docker restart --timeout 30。前两wrapper分别在jobs-before、identity-before的SSH握手关闭/reset时退出255，restart_attempts均0、尚未发restart；两份receipt与脚本原样保留，不能称发生两次重启。按项目network-proxy-retry skill三层排障及现有7897 SOCKS ProxyCommand，小ssh true验证0；仅传输出口适配，未改用户网络/SSH全局配置。v3 wrapper session3639 terminal0，唯一实际restart命令exit0（root本地UTC13:13:57.152447→13:13:57.954707），restart_attempts1，无第二次重启。

重启前后全部三容器同container ID/image ID/完整c587 OCI/config+HostConfig+mounts digest，web/public-web init PID不变、全部healthy。后端宿主uvicorn1488259/start_ticks137303694→1520161/start_ticks137481646；后者服务端13:14:10.003UTC独立确认。13:14:10.683189UTC schema90、done6293/failed38/noactive，正常启动维护自然结束；合法3001/3002 capabilities完整c587/surface同。没有summary/overview/stats预暖、源维护、清cache/queue或外层入口修改。正式detail-controlled-restart-execution-v3.json SHA f0880b4dd0ec3087460f8610f3b72e1181ee72f8207a5041c1a057bb812c1c9e；真实人类授权和独立计划另存。

根将实际新进程及收口receipt明确HANDOFF_READY交接详情任务，对https://stats.benjaminlei.site执行其独立自然90、whole-window资源、116全字段HTTPS与完整源/治理/发布守恒；本报告不预记详情结果。本项原28首次窗口发生在这次独立重启前，时间/进程边界不混用。详情接手首SSH检查握手关闭，未开始before/采样/90/116，仍零业务请求；仅恢复传输，不再次restart或用warm测代首次。

### 21.13 详情独立首次已结束，性能失败不影响对决独立结论

详情原90场景在13:20:22.302760–13:31:36.522309UTC完整结束：39通过、51性能失败，45深链全部超过3秒、6点击超过2秒（其中2项全部可见超过2.5秒）。原116接口功能对账通过，浏览器、API及总窗口三次strict读取守恒通过；全部浏览器、读连接、采样与请求已结束，没有再次重启或发布。14,098个50ms资源样本完整覆盖详情窗口，RSS峰2095.602MiB、末1724.961MiB，OOM增量0，仍有高驻留观察；不能据此关闭详情或OOM。

独立详情首轮结果、原始SHA、实际退出与下一步详见[详情专项报告](2026-10-09-music-detail-chart-performance-acceptance.md)。目前本地另准备完整图表renderer按需加载候选，候选尚未发布；详情事项继续Partial。对决原公开28样本发生在另一进程窗口，全部通过，完成状态保持；不把两个矩阵合并，也不以本地候选覆盖生产51项失败。
