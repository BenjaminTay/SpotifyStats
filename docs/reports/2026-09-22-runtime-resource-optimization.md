# 启动、运行资源与长期内存优化实施报告

> 日期：2026-09-22
>
> 最终收口：2026-09-27
>
> 实现状态：`IMPLEMENTED`；本地验证状态：`PASS`；仓库状态：随本报告提交交付（验收时为未提交工作树）；远端状态：`UNPUSHED`；部署状态：`NOT_DEPLOYED`
>
> 隔离分支：`codex/runtime-resource-optimization`；基线 HEAD：`a2467aece19dec10ea5964e1ee49dc2935cda7e8`

## 1. 结论

本轮完成了正常 lifespan 隔离测量入口、本机日常轻量启动、minimal 启动预热、L3 精确启动跳过、重型任务串行修正、定向大型缓存释放、资源探针扩展以及真实 hidden 浏览器长期运行。2026-09-27 的独立复核进一步补齐构建输入清单和最终代码同状态 D/F 页面速度对照：六个独立 E 根目录全部通过资源、页面、exact 与竞争门禁。M/D 必要维护、60 分钟浏览器序列和导入等价沿用已独立核对的原始证据；最终代码的默认完整 fullstack 在本报告第 7 节单列。

资源专项与本地完整功能验收已经闭环：M4/D3 连续 RSS 分别为 1,480.8 / 1,453.8 MiB，低于 1.5 GiB；真实 headed Chrome 的第 2→3 轮稳定 RSS 增量对后端、preview 与浏览器进程树分别为 +2.2 / +2.6 / +48.3 MiB，全部通过长期 RSS 门槛；hidden 窗口每轮 30 个样本均为真实 `visibilityState=hidden` 且无 API 请求。最终代码默认完整 fullstack 运行 `20260927T050220.824591Z-93e325671990` 的八个必需阶段全部 PASS。浏览器 physical footprint 同期从 662 MiB 增至 733 MiB（+71 MiB / +10.7%），略高于同公式阈值 66.2 MiB；该指标是冻结合同之外的诊断残余，保留跟踪，不改写 RSS 验收结论。

## 2. 实现范围

- `scripts/runtime_measurement.py`：用 SQLite Online Backup 准备 E/M/D 副本，重定向主库与六套 sidecar，隔离 Home、封面、导入控制路径，阻断非 loopback 网络，并用正常 lifespan 启动。
- `scripts/runtime_resource_probe.py`：覆盖进程创建前窗口、PID 文件、累计 CPU 秒、时间加权平均、阶段标签、文件尺寸、浏览器进程和稀疏 macOS footprint。
- `scripts/runtime_matrix_run.py` / `runtime_matrix_suite.py`：性能锁、竞争检测、服务所有权、关键任务完成事件、5 分钟空闲与独立根目录交错执行；启动期首次可用和 publication exact 后 fresh-SPA 页面速度使用不同浏览器上下文，避免把后台维护竞争混入页面门槛。
- `scripts/frontend_spa_ready_probe.py` / `runtime_df_compare.py`：在同一 SPA 文档记录 first/transition/revisit DOM+API ready、跨进程 epoch 时间、exact/LKG 和请求终态，并输出 D/F raw、median、门槛与有效性判定。
- `scripts/incremental_import_end_to_end_acceptance.py`：干净验收目录在首次 preflight 前初始化/迁移数据库，使合成 append/reconcile/replace 矩阵可独立重放；既有数据库仍不重复初始化。
- `scripts/start_daily.py`：无 reload 后端 + 既有 Vite preview；受支持构建成功后记录完整输入清单，新增、修改、删除输入均会判 stale；无清单的普通 Vite 产物要求一次托管重建。构建过期、端口冲突和退出信号均 fail-closed。
- `backend/core/config.py`：集中数据库/sidecar 路径、warmup mode、Search startup 和外部封面回退配置。
- `backend/main.py` / `backend/core/warmup.py`：预热纳入 JobQueue；minimal 只恢复 Home 持久结果，full 保留旧策略回退。
- `backend/domains/playback/l3_album_attribution.py`：仅当政策、上游 revision、mapping digest、问题/排除项和行 revision 全部一致时跳过启动 reconcile；任一不一致仍执行原 planner。
- `backend/core/job_queue.py`：实际 `artist_rank_context_rebuild` 与启动预热纳入 critical/CPU-heavy 分类。
- `backend/api/billboard/data.py`：两个 6.7–7.7 MiB 完整兼容响应复用已发布快照的校验结果，以 `pydantic-core` 单次编码，保留 response model、字段与规范化 JSON 哈希，避免重复深度验证。
- `frontend/vite.config.ts`：dev/preview 共用 API 与封面代理，preview 固定 loopback/strict port，并支持 SPA 深链。
- `frontend/vitest.config.ts`：完整套件固定最多两个 worker，避免共享开发机并发任务挤占 jsdom timer 后产生跨模块 5 秒伪超时。

## 3. E 状态三次启动矩阵

下表为第一轮历史对照：15 个根目录分别从正式库 Online Backup，分别完成自身 lineage 的必要发布后，按 `A1→B1→C1→D1→F1→…` 交错执行。每次包含 300 秒空闲；开始与结束均无 pytest、Playwright、Vitest、Vite build 或 fullstack 竞争。主数据库文件尺寸增量均为 0。它用于说明 A/B/C/D/F 归因，不再作为最终 F 资源数字。

| 组 | health 秒 raw / median | 稳定秒 raw / median | 后端 CPU 秒 raw / median | 后端 RSS MiB raw / median | 稳定空闲总 CPU raw / median |
|---|---|---|---|---|---|
| A reload + dev + full | 4.548 / 4.029 / 4.054 → 4.054 | 34.281 / 18.812 / 19.853 → 19.853 | 66.554 / 46.599 / 41.506 → 46.599 | 1843.1 / 2275.7 / 2514.6 → 2275.7 | 10.082 / 9.368 / 7.247% → 9.368% |
| B no reload + dev + full | 3.768 / 3.651 / 3.652 → 3.652 | 18.580 / 18.444 / 18.458 → 18.458 | 19.220 / 18.433 / 18.010 → 18.433 | 2089.4 / 1959.0 / 2060.1 → 2060.1 | 0.565 / 0.459 / 0.303% → 0.459% |
| C no reload + dev + minimal | 3.666 / 3.677 / 3.915 → 3.677 | 4.193 / 4.201 / 4.444 → 4.201 | 7.241 / 7.048 / 7.029 → 7.048 | 573.9 / 574.0 / 555.6 → 573.9 | 0.438 / 0.410 / 0.328% → 0.410% |
| D no reload + preview + full | 3.776 / 3.666 / 3.873 → 3.776 | 18.601 / 18.444 / 18.648 → 18.601 | 18.590 / 18.065 / 18.104 → 18.104 | 2498.7 / 2247.4 / 2207.9 → 2247.4 | 0.441 / 0.311 / 0.304% → 0.311% |
| F no reload + preview + minimal | 3.866 / 3.691 / 3.679 → 3.691 | 4.385 / 4.211 / 4.198 → 4.211 | 7.395 / 6.897 / 6.822 → 6.897 | 562.7 / 566.7 / 557.5 → 562.7 | 0.406 / 0.323 / 0.284% → 0.323% |

空闲 CPU 从 `idle_start + 5s` 计算，排除跨阶段 CPU 记账但不丢弃其余最大样本。F 的 sampled footprint 为 317 / 325 / 325 MiB，中位数 325 MiB。相对 D 中位数，F 稳定时间降低 77.4%，后端 CPU 秒降低 61.9%，后端 RSS 峰值降低 75.0%；health 没有退步。

中间一轮 F 复测因另一工作树的 fullstack/pytest 竞争按冻结合同排除。矩阵随后把锁目录统一为 `tempfile.gettempdir()`，并在启动服务前 fail-closed 检查外部竞争；竞争环境不再留下半启动样本。

2026-09-27 最终代码在六个新的独立 E 副本上按 `D1→F1→D2→F2→D3→F3` 交错执行。每个根目录均从同一源库 Online Backup，并在计时前以正常 lifespan 完成自己的 inode/lineage publication；不能由前一根替后一根预热。启动期首次可用、必要维护、最终 exact 和 exact 后 fresh-SPA 页面计时分别记录。六次 operation exit 均为 0，publication 与最终首页均 exact，同一 SPA 文档成立，首尾竞争清单为空，主数据库尺寸增量为 0，连续采样有效。

| 样本 | 首次业务可用秒 | 最终 exact 秒 | exact 后 first / revisit ready | 启动后端 CPU 秒 | 启动后端 RSS / footprint 峰值 | 5 分钟空闲应用 CPU |
|---|---:|---:|---:|---:|---:|---:|
| D1 full | 7.167 | 20.000 | 717.1 / 172.7 ms | 15.349 | 1532.5 / 1477 MiB | 0.346% |
| F1 minimal | 5.510 | 10.352 | 609.0 / 49.7 ms | 6.215 | 594.6 / 435 MiB | 0.321% |
| D2 full | 4.563 | 19.786 | 637.3 / 29.7 ms | 15.148 | 1518.1 / 1454 MiB | 0.312% |
| F2 minimal | 5.305 | 10.266 | 682.5 / 56.4 ms | 6.119 | 576.9 / 447 MiB | 0.323% |
| D3 full | 4.433 | 19.284 | 679.4 / 30.2 ms | 14.753 | 1532.4 / 1464 MiB | 0.321% |
| F3 minimal | 5.087 | 9.717 | 642.6 / 51.9 ms | 6.174 | 594.5 / 432 MiB | 0.323% |

D/F 中位数的 first ready 为 679.4 / 642.6 ms，F 低于 `D + max(100ms, D×10%) = 779.4ms`；revisit 为 30.2 / 51.9 ms，F 低于 130.2ms。页面数字来自最终代码的严格 DOM 复核：目标 URL、目标页独有内容、API 终态、exact、同一文档和首尾零竞争必须同时成立；它替代了会在 URL 已切换但旧页 DOM 尚未卸载时过早计时的初版判据。F 启动 CPU 6.174 秒，相对 D 的 15.148 秒降低 59.2%；F 后端 RSS 594.5 MiB，相对 D 的 1532.4 MiB 降低 61.2%；F footprint 435 MiB，低于 768 MiB；空闲 CPU 0.323%，低于 1%。机器可读资源比较和最终页面比较均为 PASS。

旧报告的约 7.836 秒是第二次 exact 核验结束，不能冒充唯一的首次可用或页面自身 ready；上表以最终代码重新拆分三类时间。资源、启动和空闲正式证据位于 `/tmp/spotify-runtime-df-20260927-v5/formal/`，严格页面复核位于 `/tmp/spotify-runtime-df-20260927-v5/final-code-spa-v3/`。另有多次因其他工作树 fullstack/Playwright 竞争而在启动前或结束时排除的目录，均未进入 raw/median。

## 4. M/D 必要维护与 R3/R4 收口

### 4.1 原失败基线

| 状态 | 结果 | 必要维护时间 | 后端 CPU 秒 | 后端 RSS 峰值 | sampled footprint 峰值 |
|---|---|---:|---:|---:|---:|
| M：Analysis/Home 缺失，新 lineage | 必要发布全部完成 | 65.110s | 63.359 | 1720.2 MiB | 1066 MiB |
| D：Billboard 配置漂移，新 lineage | 必要发布全部完成 | 100.273s | 94.925 | 1830.9 MiB | 991 MiB |

修正前，错误的 rank context job type 让其与 Billboard 重叠，M 峰值为 2,081.3 MiB、稳定 68.215 秒。首次串行修正后峰值降至 1,720.2 MiB，但仍高于 1.5 GiB。随后按任务全清 `db` / Analysis / Billboard 重对象的受控实验使第二个 Analysis 重新分配，峰值升至 1,797.1 MiB、稳定时间增至 88.075 秒；该实验已撤回，未用全清抖动换取结束点数字。

### 4.2 保留对象归因与定向实现

- 普通 lifetime 事件帧为 67,881 行、48 列，深内存约 122.1 MiB；其 hour slice 为 91,928 行、约 136.0 MiB。艺人帧为 72,469 行、48 列，深内存约 129.3 MiB；其 slice 为 98,461 行、约 143.4 MiB。
- 两个 loader 的 LRU 都有 `maxsize=16`。新增 17 个合法过滤组合回归，确认容量始终为 16，且最早项会被淘汰；问题不是字典无界，而是启动维护的最终消费者完成后仍同时保留两个宽帧。
- Analysis Stats 改为只加载事件帧一次，并只投影 listening intervals、track、album、artist 四列后统一展开一份 duration frame；summary/hour/day/weekday/month/year 共用该投影。lifetime snapshot 可在内部只读路径复用未过滤事件帧，默认交互调用仍保留独立副本合同。全 payload 等价回归通过，独立单次 stats 构建最大 RSS 为 667,156,480 bytes（约 636 MiB）。
- rank context 是启动序列中两个宽帧的最后消费者。任务无论成功或失败都会在关闭连接后只清除 `db.plays` 与 `db.plays_for_artists` 两个命名项；Community、Archive、Governance 使用持久投影或窄 SQL，小型 presentation/result 缓存不受影响。该策略避免了逐任务全清造成的重算。
- Search 成功发布会改变治理依赖 revision，因此现在会重新入队 Governance；最终 readiness 不再把 Search 之后已经陈旧的 import health 误判为完成。

### 4.3 当前代码 M/D 复测

| 状态 | 必要发布 | 最后必要 job | 含最终浏览器精确核验 | 后端 CPU 秒 | 后端 RSS 峰值 | sampled / lifetime footprint 峰值 |
|---|---|---:|---:|---:|---:|---:|
| M4 | 全部 exact | 63.643s | 66.802s | 62.310 | 1480.8 MiB | 1393 / 1410 MiB |
| D3 | 全部 exact；Search 后 Governance 再追赶一次 | 109.211s | 112.812s | 105.756 | 1453.8 MiB | 1376 / 1436 MiB |

两次连续采样的最大墙钟间隙分别为 1.321 秒和 1.322 秒，均无休眠或采样中断；核心首页最终通过真实 DOM、API terminal state 与 exact revision 检查。相对原样本，M RSS 降 239.4 MiB（13.9%），D 降 377.1 MiB（20.6%），均低于 1.5 GiB。M 最后必要 job 比旧完整时间更快；D 因补上 Search 后必须执行的 Governance 多一次正确维护，最后必要 job 比旧样本增加 8.9%，仍在 `max(1s, 10%)` 门槛内。最终页面核验的额外约 3.6 秒单列报告，不冒充后台 job 时间。

D2 虽曾得到更低的 1441.8 MiB，但主机休眠造成相邻样本 954.816 秒墙钟断层，已从时间结论排除。资源探针现会优先检查墙钟采样间隙，超过 `max(5s, 10×interval)` 即退出失败；不再让此类污染样本进入正式结论。

## 5. 长期浏览器运行

最终 soak 使用系统 headed Chrome 和同一个应用 target，在隔离 E 副本上执行 3 轮、每轮 20 分钟。每轮 30 次访问覆盖 Home、Analysis、Search、歌曲/专辑项目/艺人详情、Billboard、Community、音乐档案与指定年度页；脚本阻断所有非 GET/HEAD 请求，因此 6 次年度 prewarm POST 被明确列为 intentional blocked mutation，不计入 API 失败。216 次应用 API observation 无意外失败，控制台错误为 0。

每轮交互后真实执行 visible→hidden→visible：30 个稳定样本全部报告 `visibilityState=hidden`，同一页面 `timeOrigin` 不变、navigation entry 始终为 1，hidden 5 分钟内 API 请求增量均为 0，恢复 visible 成功。

| 指标 | 第 1 轮稳定中位数 | 第 2 轮稳定中位数 | 第 3 轮稳定中位数 |
|---|---:|---:|---:|
| JS used heap | 18,473,608 B | 16,967,262 B | 21,962,334 B |
| DOM nodes | 891 | 534 | 895 |
| event listeners | 427 | 190 | 438 |
| resource entries | 250 | 250 | 250 |

| 进程 | 第 2 轮稳定 RSS | 第 3 轮稳定 RSS | 增量 | 冻结 RSS 门槛 |
|---|---:|---:|---:|---|
| 后端 | 587.3 MiB | 589.5 MiB | +2.2 MiB | PASS |
| 前端 preview | 164.9 MiB | 167.5 MiB | +2.6 MiB | PASS |
| Chrome 进程树 | 1,421.5 MiB | 1,469.8 MiB | +48.3 MiB | PASS（≤50 MiB） |

physical footprint 作为并列诊断：后端从 507 降至 497 MiB，preview 从 79 增至 81 MiB，浏览器从 662 增至 733 MiB。浏览器 +71 MiB / +10.7% 略高于按同公式计算的 66.2 MiB，因此保留为后续观察项；本轮冻结验收指标是进程树 RSS，不能把 footprint 残余隐藏，也不能据此把已通过的 RSS 门槛改写为失败。

整个窗口资源探针退出码为 0、budget failures 为空、主数据库文件尺寸增量为 0；2,628 个样本的最大墙钟间隙为 1.954 秒。后端峰值 RSS 1,235.6 MiB、sampled/lifetime footprint 991/1,075 MiB、累计 CPU 43.701 秒；浏览器峰值 RSS 1,577.1 MiB、sampled/lifetime footprint 1,034/1,125 MiB、累计 CPU 73.144 秒；preview 峰值 RSS 181.0 MiB。

## 6. 正确性、安全与导入试验

- 正式数据库只读；所有准备使用 Online Backup，所有发布与运行元数据写入 `/tmp/spotify-runtime-evidence-20260922/` 的实验副本。
- 测量后端阻断外网；封面使用隔离本地副本，缺失时不回退 CDN。
- `api_smoke_probe.py` 与 `api_boundary_probe.py` 在显式 `--db-path` 下同时绑定主库及六套 sibling sidecar，避免主库来自副本而 Analysis/Billboard/Community/Archive/Governance/Yearly 仍误读工作树默认路径；对应隔离回归通过。
- E 精确状态仍执行导入恢复、身份/署名、Search、Billboard、Analysis、Community、Archive、Governance readiness；minimal 不关闭必要发布。
- R6 合成导入矩阵在一次验收入口初始化顺序修复后通过：12 个历史周 baseline → 跨周 append → 同周 append → 历史 reconcile → 空库完整 replace。14 项事实、署名、Album Project、Track Group、Billboard、Power、Records、Year-End、四套 Search、年度分区和 Home/Archive 投影全部等价；正式源库以只读方式打开且前后未变。
- 同周/跨周均完成必要 revision 失效和四套 Search ready；增量门禁不能证明兼容时明确使用 `shared_full_snapshot_rebuild`，历史修正的 Album Project 以 `deletion_semantics` 安全 full fallback，没有伪装成 delta。
- 日常静态入口已用 Desktop 和 390×844 Phone 实际访问：API、封面、深链与 SPA 路由均成功，Phone 无横向溢出且控制台无错误/警告。最终 fullstack 控件清点覆盖 40 个页面/视口组合、1,976 个控件和 307 个主要触控目标，未发现小于 44px 的主要触控目标。

## 7. 测试与完整门禁

- 定向资源/启动与探针隔离测试持续通过；最终 API probe 隔离与 runtime measurement 组合为 23 passed，pre-commit 的 Ruff、format、mypy 与 detect-secrets 全部通过。
- 默认完整 fullstack 使用一次性 Online Backup 数据副本，运行 ID `20260927T050220.824591Z-93e325671990`，模式为 `full`，总耗时 1,669.043 秒；八个必需阶段全部 PASS，不用局部运行拼接结论。
- backend seed：2,998 passed、2 skipped；真实 integration：186 passed、1 skipped。页面探针目标 DOM 回归、构建清单删除输入回归和 Billboard 兼容响应合同均纳入该完整运行。
- 前端：86 个文件通过、1 个跳过；670 passed、4 skipped；生产 build 通过，仅保留既有大 chunk warning。
- API smoke 153/153、API boundary 113/113；22 轮热路径全部成功，完整兼容 `/api/billboard/all-time` / `/api/billboard/data` P95 为 253.566 / 270.884ms，最慢热 P95 270.884ms，低于 500ms。
- 浏览器：54 个 Desktop/Mobile 路由和 30 个五视口矩阵检查均为 0 console error、0 warning、0 overflow；交互、图表、7 个长列表场景通过；40 个控件清点组合无违规；Chromium、Firefox、WebKit 全部通过。
- 文档/OpenAPI：199 个含 archive Markdown、234 个 OpenAPI operation 与 110 个参数义务均无未覆盖项。
- API probe 会在自己的实验副本执行正常 lifespan，因此该 disposable `spotify_stats.db` 与 yearly sidecar 可产生运行时写入；其余五套 sidecar 前后不变。该行为不影响正式库只读结论，也不能描述为“全部实验文件零写入”。

## 8. 状态边界

- 已实现并验证：R0 正常 lifespan 测量与 fail-closed 竞争检查、R1 日常入口、R2 minimal 预热、R3 定向对象生命周期、R4 重型分类、R5 真实 hidden soak、R6 导入等价与默认完整 fullstack。
- 资源门槛：最终 F 三样本、空闲 CPU、M4/D3 ≤1.5 GiB、长期 RSS 增长与隐藏页零请求均 PASS。
- 诊断残余：长期浏览器 physical footprint 第 2→3 轮 +71 MiB / +10.7%，略高于同公式阈值 66.2 MiB；不阻断冻结 RSS 门槛，但保留后续版本复测。
- 验收完成后已获本地提交与合并授权；集成结果另行记录。未执行 push、部署或生产验收；AI Agent V6 与真实模型调用不在本轮范围。
