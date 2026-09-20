# 阶段 3C：Records 单次构建共享事实收口

**Partial；Records 阶段实现到此停止。** 三次独立新进程重建中位数 **17.49s**，较同轮阶段 3B 基线 **22.41s** 下降 **21.9%**，但 **≤10s 未通过**。七次独立进程 exact 首读经验 P95 **469.05ms**，本组 **≤500ms 通过**；本批未修改读取代码，不能据此宣称消除了此前 840ms 的波动。Warm 20 次 P95 **57.72ms** 通过。建议允许进入阶段 4 的独立 Billboard 工作，但必须保留 Records 重建目标未完成的状态；本轮没有开始阶段 4，也不追加 3D。

## 当前基线与范围

- HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty。所有已有未提交阶段作为基线保留；本轮之前的逐文件 SHA 与 Python 源码在 `worktree-before.json` / `before-code/`。
- 先读取 AGENTS/CLAUDE、阶段 3B 报告、Records/播放统计/音乐档案规则，随后完成 `before-detail-profile.json` 才修改产品代码。基线十组 payload 从保存的阶段 3B 源码独立加载；`semantic-before-*.json` 为原始完整结果。
- 正式源通过 SQLite `mode=ro` + Online Backup 复制到 `/tmp/spotifystats-stage3c/main.db`，**92,908 plays**；仅此副本保持阶段 3B 的 migration 74 测量状态。正式主库内容未改变，仍是原 schema 73。全部 sidecar/Home 路径显式指向 `/tmp/spotifystats-stage3c/`；pytest 使用现有 session fail-closed 临时隔离。
- 相同副本路径、默认设置、L2、dynamic threshold、合并开、gap=5、lifetime、compilation=false。没有修改 loader、共享 logical timeline、snapshot/source revision/API/model/frontend/Billboard/Search/Homepage 产品逻辑。

## 已修改及等价性依据

| 文件 | 本轮增量 |
|---|---|
| `backend/domains/playback/records_duration_facts.py` | 新增 invocation-local 小型 context。按完整且有序的纳秒区间序列复用小时切片几何，仍调用原 `explode_listening_slices()` 完成切片和取整；不同 source row 从自己的原 frame 取回身份、字段、credit 和顺序。 |
| `backend/domains/playback/records_helpers.py` | 可选显式 context 传入 scoped duration；没有 context 的旧调用保持原路径；已经具有 `slice_start_at` 的 Yearly 预加载 frame 不再 explode。 |
| `backend/services/analysis_records_service.py` | 每次 builder 创建一个 context，event/artist/预加载实体共享；各自进行周期筛选和 attach，实体准备完即释放 context。 |
| `backend/domains/playback/records_longevity.py` | 每类实体只准备一次 presence/日期/累计事实；streak/comeback 读取不可变 tuple；span/month 读取独立 copy 的名称敏感分组。两种粒度、null 排除、并列与 Top 50 全部保留。 |
| `backend/tests/unit/test_records_invocation_facts.py` | 6 项新增回归：跨小时/日/年及小于1ms取整、重复 credit/新增区间、空/无效区间、范围隔离、预切片不重算、双轨累计/名称分组/并列、共享事实不污染。 |

另更新本报告、分析快照 reference、docs 地图和 CHANGELOG。增量文件清单与 patch 相对于本轮开始时 dirty worktree 保存；不把以前阶段改动算成本轮成果。

真实副本的 event duration **90,208** 行与 artist duration **96,471** 行具有完全相同的 **90,190** 组唯一区间序列。复用的是几何，不是 track 的聚合结果：featured/main role、canonical artist、专辑项目和事件数仍来自原粒度。原始 frame 不变，小时切片调用 **2 → 1**；artist 端没有新增区间需要重新切片。其他输入若出现新序列，只为该序列调用原 splitter；单次调用结束后没有保留状态。

Longevity 的 `_duration_totals` / `_event_totals` 调用各 **6 → 3**；实体日期集合准备 **17,358 → 8,679** 次。跨度和月份保留 `(entity, name, artist)` 原分组，不能以仅 entity 的 totals 替代。原四榜排序表达式、日期取整和 total_plays/total_ms/total_hours/name/artist 字段未变。

## 完整字段语义验证

十组全部 `all_fields_equal=true`、`mismatch_paths=[]`：lifetime L2、L3、L2 compilation、L3 compilation、fixed threshold、merge off、last_6_months、2025 custom、1900 empty、2025 Yearly preloaded。双方同一数据库/配置，generated_at 固定为同一时刻。比较全部字典键、类型、每个标量、所有榜单元素和顺序，包含 period/meta、六类 Records、全部实体、日期、精确时长、并列、深链、cover 和 null；没有只验 Top 1。

Yearly 路径预先构建年度 frame 后给全量 reload 方法安装失败 sentinel，确认没有回到全库重载。Seed 回归覆盖短片段、跨边界、L2/L3 membership、compilation、artist fan-out、原版专辑、过滤及排序合同。三类实体分别建立 facts，没有混合粒度。

所有重建 before/after 的完整 source revision 和 request key 均相同：

- request key：`03ea5900b76803adea6231bfe1b6fd9bbf2ce5dd4fd262082747a80cdd5cb93f`
- source revision：`6a54258b53fee4a7b14b76d75ca82abd892cc0ead45c1ded7aec4f99e8421d11`
- builder version：`analysis_records_v1`

这是临时副本绝对路径下的 key，不能复制到正式 namespace。来源全内容摘要、revision bytes、校验、失效、atomic publish、LKG、singleflight 和 public-readonly 合同均未修改。

## 重建验收：独立新进程、串行交错 before/after

每组独立进程、新 sidecar；wall 包含 request context、完整 builder、验证和 publish，import 不在计时窗口。CPU/RSS 使用50ms时间序列，原始值在每个 `rebuild-*.json`。没有与本轮测试、profile 或前端 build 同时执行；不终止其他应用，不剔除慢样本。

| 对次 | 当前 3B baseline wall s | 3C wall s | 3C CPU s | 3C peak RSS GiB |
|---|---:|---:|---:|---:|
| 1 | 22.407859 | 19.909870 | 19.131661 | 1.2941 |
| 2 | 23.242454 | 16.505497 | 16.352876 | 1.2811 |
| 3 | 19.812653 | 17.489450 | 17.168362 | 1.2855 |

3C min/median/max：**16.505497 / 17.489450 / 19.909870s**，3/3 成功，0失败；≤10s **未通过**。三个样本只报告观测值，不生成稳定 P95。同期基线原始值为 22.407859, 23.242454, 19.812653s。

四并发同 key 维护耗时 **16.887475s**，实际 builder **1**、publish **1**，其余3调用锁内复查 exact；pandas SQL **11**。前后 SQL 总调用均 **240**（profile包括 PRAGMA/执行/读回归因，非全部SELECT），未把 SQL 数未变伪称为 loader 优化。3C 三样本及并发 peak RSS 最大 **1.2941GiB**，低于既有约1.4GiB边界。

## 剩余 profile 与停止依据

当前 revision before profile wall/CPU 为 21.344/20.894s；最终 after profile 为 20.685/19.692s。中途 `after-detail-profile.json` 28.245s 的较慢结果同样保留，不覆盖。profile 是归因，不替代上面的无 profiler 验收；不使用不同负载下的 profile 差值计算优化收益。各阶段存在包含关系，不能相加。

| 阶段 | before profile s | final profile s |
|---|---:|---:|
| `source_revision` | 0.337 | 0.729 |
| `load_plays` | 1.684 | 1.797 |
| `attach_scoped_records_duration` | 5.887 | 4.250 |
| `load_plays_for_artists` | 2.166 | 2.409 |
| `compute_obsession_records` | 1.243 | 1.292 |
| `compute_time_pattern_records` | 0.869 | 1.099 |
| `compute_reign_records` | 1.481 | 1.700 |
| `compute_longevity_records` | 3.197 | 2.550 |
| `compute_discovery_records` | 1.653 | 1.713 |
| `compute_behavior_records` | 0.729 | 0.732 |
| `_add_cover_urls_to_records` | 1.165 | 1.207 |
| `_serialize_records` | 0.164 | 0.165 |
| `publish` | 0.024 | 0.025 |

当前剩余主要阶段：scoped/hour duration **4.25s**、两个 loader 合计 **4.21s**、longevity **2.55s**，另有 reigns **1.70s**、discovery **1.71s** 和 cover lookup **1.21s**。所有 SQL、DataFrame copy、函数 self/cumulative、RSS/CPU序列均在 profile JSON / `.prof`。

只把现有切片结果共享不能消除第一次90k区间的逐边界处理；继续压缩这一阶段可能需要共享 logical timeline 算法变化。两个 loader 的主要基础步骤类似，但保留不同 credit/canonicalization 和过滤路径；未证明可在当前范围以局部复用替代整个基础加载合同，因此没有改 loader。longevity 已共享准备，剩余仍包括每实体遍历和名字粒度聚合。要从17.49s进一步减少约7.49s，已超出本轮重复事实收口可保证的收益；不制定或开始 3D，不擅改 core/schema/语义。

## exact / warm / 并发 GET

公开 GET，7个独立后端进程各首读一次；第7个进程继续20次warm，第8个独立进程发4并发。31/31 HTTP200，builder=0，snapshot exact。新进程没有启动预热，健康和settings不预热 Records。压缩大小取实际HTTP响应，不重新gzip估算。

| 状态 | 原始值或 min / median / P95 / max（ms） | 结果 |
|---|---|---|
| process cold + exact（7） | 原始：485.389, 384.708, 395.222, 430.916, 401.569, 406.139, 421.514 | 7成功/0失败 |
| process cold + exact 汇总 | 384.708 / 406.139 / **469.047** / 485.389 | 本组经验≤500ms通过 |
| warm exact（20） | 48.254 / 49.425 / **57.719** / 94.419 | 通过 |
| concurrent4 exact | 835.478, 868.667, 845.502, 870.083 | 4成功，builder0 |

上表 P95 使用阶段3B报告的线性插值口径。阶段0统一合同使用 nearest-rank：warm P95 **55.787ms**；冷读仅7个样本，合同仍标为 `observed_values_only`，按用户要求另外报告经验线性P95 **469.047ms**（nearest-rank **485.389ms**），不称稳定P95或生产SLA。两种算法不改变本组目标判断。20个warm原始值为：50.952, 52.182, 50.96, 51.007, 55.787, 49.392, 49.038, 50.259, 48.987, 48.684, 49.951, 48.549, 48.851, 94.419, 48.968, 49.17, 49.093, 48.254, 49.457, 50.082。

旧 harness 把 `new_process` 写成非合同枚举、未给并发填 group，导致默认汇总错误混组。本次保留原始 `final-api.json`，以进程PID与operation证据生成 `final-api-normalized.json`，明确cold/exact与concurrent4；没有删改任何耗时、失败、重试或样本。未修改仓库探针，不把schema修正当性能优化。

完整HTTP raw **2,096,306 bytes**，本批实际gzip **126,379 bytes**；snapshot raw **891,887 bytes**、zlib约125.7KB、单行sidecar139,264bytes。没有瘦响应或raw JSON快路径。

### 七个冷首读分段

单位ms。sidecar列为read减decode；codec包含JSON decode、解压、checksum/长度/对象校验。Pydantic、JSON、gzip全部保留。HTTP总时间与server阶段计时边界不同，残差包含路由/线程/网络接收/调度；不强行相加或当独立CPU。

| 样本 | HTTP总 | source revision | sidecar residual | codec | validate | serialize | JSON encode | gzip write |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 485.389 | 432.083 | 0.362 | 5.612 | 5.124 | 5.517 | 12.069 | 6.890 |
| 2 | 384.708 | 335.243 | 0.317 | 5.455 | 4.690 | 5.004 | 10.881 | 6.181 |
| 3 | 395.222 | 342.096 | 0.337 | 5.511 | 4.929 | 5.265 | 11.709 | 6.919 |
| 4 | 430.916 | 374.054 | 0.373 | 6.006 | 5.275 | 5.773 | 13.055 | 7.454 |
| 5 | 401.569 | 349.145 | 0.352 | 5.648 | 4.858 | 5.210 | 12.053 | 6.628 |
| 6 | 406.139 | 351.096 | 0.382 | 5.926 | 4.950 | 5.366 | 12.349 | 7.331 |
| 7 | 421.514 | 366.886 | 0.343 | 5.931 | 4.992 | 5.364 | 12.614 | 7.158 |

`final-exact-profile.json` 另保存带profiler的解压/checksum/JSON/Pydantic/GZip分段。完整 source revision 仍是冷读主成本；本批没有改变任何读取实现，所以相对3B历史840ms的差异不能归因于本轮builder优化。浏览器并行请求下 Desktop source阶段约633ms，四并发GET为835–870ms，进一步说明低干扰七样本不构成所有负载下≤500ms的保证。若未来要求稳定边界，需要可信写路径revision或持久source manifest的独立设计与授权；不能用mtime、MAX(ts)、row count等替代完整校验。

## Desktop / Phone 真实浏览器

运行production build，loopback服务、独立浏览器profile和每页独立后端进程。CDP请求拦截只允许本地GET/HEAD；public builder/publish/JobQueue安装失败sentinel。首屏条件为路由正确、分类和单日巅峰实体事实出现、Records API200、没有错误alert。5s core预算与30s请求预算不变，没有固定等待。截图已检查，横向overflow=0。

| Presentation | API ready ms | DOM core-ready ms | API至core ms | Records请求/状态 | raw/gzip bytes | 首屏TBT ms |
|---|---:|---:|---:|---|---|---:|
| Desktop 1280×900 | 1132.70 | 1473.00 | 340.30 | 1 / 200 | 2096306 / 126379 | 0.00 |
| Phone 390×844 | 753.96 | 1094.00 | 340.04 | 1 / 200 | 2096306 / 126379 | 0.00 |

两端均通过真实鼠标/触控：次数→时长、专辑、艺人、长线陪伴。断言按钮selected/pressed、实体深链、URL family和四个longevity模块事实出现。筛选过程仍仅1次核心Records GET，无404、重试或错误skeleton；公开主库/analysis/Home/yearly/Billboard文件before/after相同。周期参数的完整字段等价在上述recent/custom/empty和Yearly场景验证；本轮浏览器交互范围是指标/实体/分类，不冒称遍历所有周期UI。

请求瀑布、响应大小、body读取+JSON解码、LCP/CLS/long task及动作DOM分别保存；不把自动点击当INP。首屏与筛选后截图均保留。

## 测试与数据边界

- 新增事实/既有Records/Yearly adapter定向：**27 passed**。
- 完整后端unit：**1,791 passed / 1,085 deselected**。
- Album Project、Records API、analysis snapshot与public boundary：**58 passed**。
- 前端相关5文件：**50 passed**；production build成功。保留既有大chunk warning，没有放宽阈值。
- Ruff、Python compile、docs audit、git diff --check结果见最终日志；没有运行完整约47分钟全栈，交付为 **Partial**。

正式目录前后清单共 **4,180** 个文件（主库/WAL、正式sidecar/snapshot、covers及缓存等，排除无关imports/exports/backups归档）。**全部文件集合、bytes SHA-256、大小相同**；4,179项mtime也相同。唯一metadata差异是 `data/spotify_stats.db-shm` 的mtime在Online Backup时段变化，32,768bytes及SHA-256完全相同。未回写或伪造mtime。正式主库、WAL、所有快照/sidecar/封面/cache的mtime均相同，正式analysis sidecar仍不存在。该SHM元数据观察单列在 `formal-comparison.json`，不写成“所有文件时间戳都未变化”。

正式主库未作为builder/migration/测试连接写入目标；完整主库与WAL内容相同证明业务表、原始播放事实、revision/settings/JobQueue均未被本轮改写。临时源在测量间保持不变；公开边界测试另验证missing/LKG/不兼容参数、key异常、损坏payload不冷建、不发布、不排队。

## 停止与 Git

保留本轮之前全部dirty改动。仅增加上列4个产品文件、1个测试文件及必要文档增量；没有commit/push/deploy。完整增量清单、patch、验证日志及原始测量材料均随证据保存。

**建议下一步可由用户决定进入阶段4 Billboard**：统计/数据安全、全字段等价和回归已闭合，没有需要继续阻塞在Records的正确性问题；Records的≤10s目标仍明确未完成，稳定冷读SLA也未被证明。阶段3C已经停止，不安排新的Records实现或Billboard工作。

原始材料：`/tmp/spotifystats-stage3c/`。持久证据（不含数据库副本/sidecar）：

`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage3c/`
