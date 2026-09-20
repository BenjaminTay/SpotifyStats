# 阶段 3A：默认播放统计与播放纪录持久结果快照

本地实现与局部验证为 **Partial**。两个默认 lifetime family 已通过独立 sidecar 发布、只读 GET、来源 fence、同 key singleflight 和现有 JobQueue 维护。Stats 的 exact/warm 目标通过；Records warm 通过，但独立进程 exact P95 与重建 10 秒目标未通过。没有进入阶段 3B、4、5、6，没有实现 C1 或改变统计算法。

## 基线与证据

- HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，工作区 dirty；阶段 0/0.5/1/2A/2B 和安全收口保留。
- 本轮新做 SQLite Online Backup：`/tmp/spotifystats-stage3a/main.db`，92,908 plays；migration 74 仅应用到这个副本。
- 默认参数读取副本 settings：min_ms=30000、music_only=true、merge_enabled=true、max_merge_gap_minutes=5；沿用前端默认 dynamic_threshold=true；records lifetime/L2/include_compilations=false。
- 原始 JSON、HTTP gzip 字节、100ms timestamped RSS/CPU、builder/loader/SQL instrumentation、浏览器 waterfall/截图、失败日志均保存在 `/tmp/spotifystats-stage3a/`；持久证据副本见文末。没有本地重压 gzip 冒充网络大小。
- HTTP 30 秒、浏览器 core-ready 5 秒预算保持不变。3 个独立进程样本与 20 个有效 warm 样本分开；P95 为这批样本的线性插值经验分位数，不是生产 SLA。失败不参与通过分位数。

## API before / after

单位 ms。cold 明确指独立进程启动后的请求；after 同时具有 exact 持久快照。并发各为同进程 4 个相同请求。

| family / 状态 | before 原始样本或 min / median / P95 / max | after | 成功/失败 before → after |
|---|---|---|---|
| stats / cold | 7934.737, 7008.013, 8179.361 (P95 8154.9) | 364.724, 348.058, 354.109 (P95 363.66) | 3/0 → 3/0 |
| stats / warm | 13.94 / 15.09 / 81.54 / 83.31 | 11.71 / 12.16 / 17.1 / 54.3 | 20/0 → 20/0 |
| stats / concurrent4 | 26915.237, 26917.59, 26931.022, 26932.611 | 394.64, 396.708, 398.578, 400.21 | 4/0 → 4/0 |
| records / cold | 30001.509, 30001.663, 30001.644 | 418.253, 454.895, 596.792 (P95 582.6) | 0/3 → 3/0 |
| records / warm | 131.38 / 145.15 / 180.09 / 312.87 | 64.52 / 66.94 / 73.68 / 133.84 | 20/0 → 20/0 |
| records / concurrent4 | 30004.133, 30002.282, 30003.112, 30004.4 | 683.837, 694.943, 707.641, 719.799 | 0/4 → 4/0 |

Records 的三个 before 独立进程请求均在 30 秒超时，不能将 30 秒当成功耗时或计算通过 P95。before 补测在首次超时后通过 builder 完成信号等待 LRU ready，再测 20 次 warm；没有延长用户 GET timeout。补测期间与 before 浏览器计算有资源重叠，因此 Records before 全构建 109.10 秒不是与 after 无争用条件完全一致的算法速度对比。本轮没有优化 builder 算法。

### Warm 原始样本

- before stats: `[19.229, 14.987, 14.691, 83.312, 15.416, 15.081, 14.803, 13.938, 20.744, 15.463, 15.188, 15.13, 15.011, 14.922, 15.109, 14.221, 14.944, 81.444, 15.284, 14.965]`
- before records: `[152.784, 151.092, 138.908, 140.587, 141.856, 145.303, 142.08, 131.458, 158.732, 167.726, 139.087, 312.866, 148.988, 137.895, 161.024, 131.381, 134.529, 145.0, 168.311, 173.1]`
- after stats: `[12.686, 12.011, 12.087, 12.436, 11.947, 12.124, 12.321, 12.179, 15.141, 12.065, 11.881, 54.301, 12.436, 12.131, 11.919, 11.706, 11.739, 12.238, 12.368, 12.477]`
- after records: `[67.665, 66.998, 70.516, 66.26, 66.875, 65.749, 64.516, 65.767, 66.33, 66.669, 68.299, 68.459, 133.838, 68.982, 68.591, 69.062, 66.042, 65.91, 67.423, 65.442]`

### 大小、CPU、RSS 与实际执行次数

| family | raw bytes before → after | HTTP gzip bytes before → after | before 并发 builder | after exact 并发 builder |
|---|---|---|---|---|
| stats | 205638 → 205985 | 34071 → 34271 | 4 | 0 |
| records | 2095963 → 2096306 | 126174 → 126379 | 4 | 0 |

增加的响应大小来自 freshness/revision/key/version 元数据。Records 仍返回约 2.1 MB JSON；本批未实施瘦响应。after exact 的原始 LRU hits/misses 都为 0，说明读取没有借用旧 builder LRU。

| 阶段 | wall 秒 | CPU 秒 | peak RSS GiB | SQL / loader / builder 毫秒 |
|---|---|---|---|---|
| before stats 独立进程首例 | 7.940 | 7.571 | 1.934 | 956.0 / 1921.9 / 7915.2 |
| after stats exact 首例 | 0.369 | 0.362 | 0.178 | builder SQL/loader 均 0；另有来源指纹 SQL |
| after stats 完整 rebuild（4并发一次实际构建） | 10.677 | 10.164 | 1.914 | 736.4 / 1653.0 / 9818.0 |
| before records 独立进程首例（30秒截断） | 30.221 | 29.887 | 1.399 | 1852.9 / 2296.4 / 未完成 |
| after records exact 首例 | 0.433 | 0.408 | 0.202 | builder SQL/loader 均 0；另有来源指纹 SQL |
| after records 完整 rebuild（4并发一次实际构建） | 35.807 | 35.456 | 1.335 | 1604.2 / 1586.8 / 34983.7 |

完整 rebuild 表采用最终来源指纹的测量；Stats 该次与 seed contract 验证有短暂重叠。较早两轮同算法观测为 Stats 8.16 秒、Records 27.34 秒；真实 JobQueue 轮次 builder 为 Stats 9.43 秒、Records 25.90 秒。所有轮次保留，不选最快一轮宣称达标。Records 默认 rebuild **未达到 ≤10 秒**。

RSS：before stats 非并发上界 2.038 GiB、records 上界 1.399 GiB；after rebuild 分别 1.914 / 1.335 GiB，未超过各自 before 观测上界。全操作 time series 与每次测量 CPU/SQL/loader 详见原始 JSON。SQL instrumentation 包装 `pandas.read_sql_query`，不声称覆盖来源指纹的 sqlite3.execute；其耗时已计入总 wall/CPU。

## exact / LKG / miss / rebuilding

- exact：两族各 3 个新进程 + 20 warm + 4 并发成功，builder=0。
- LKG：在临时主库增加 playback_revision，维持同参数；两个 public GET 分别 359.17 / 443.06ms，200、last_known_good，文件 bytes/mtime 不变，builder=0。仅 observed values，不报告 P95。
- missing：仅重命名临时 sidecar，两个 public GET 为 3.70 / 3.56ms，503 snapshot_unavailable，不建空库、不排队。最终实现还在 sidecar 不存在时直接返回，不扫描来源事实。
- 参数不兼容、key 异常、校验失败、构建期间 source 漂移与写入失败均有定向回归；不借其他 filter/L2/L3/compilation 的 LKG。
- rebuilding：真实临时 JobQueue 完成两项任务，各 family builder=1；浏览器同时读取 LKG。队列事件与开始/结束时间保留在 `maintenance-series.json`。

## Desktop / Phone production build

核心条件同时包含真实路由、核心 API 200 与真实统计 DOM；Records 使用记录分类及单日巅峰实体链接，Stats 使用统计 KPI。错误/暂不可用不是 core-ready。没有增加等待预算。

| 状态 | Desktop stats / records core-ready ms | Phone stats / records core-ready ms |
|---|---|---|
| before-corrected | 未达5秒预算 / 未达5秒预算 | 682 / 未达5秒预算 |
| exact-restart | 1571 / 2133 | 527 / 944 |
| lkg | 462 / 759 | 396 / 748 |
| missing | unavailable（503） / unavailable（503） | unavailable（503） / unavailable（503） |
| rebuilding | 1124 / 1557 | 450 / 1276 |

exact-restart 在后端新进程读取已发布快照；同轮各页面依序打开，不将后续页面伪称为又一个独立进程。before-corrected 的 API/service 在独立临时 harness 中加载本轮修改前的 HEAD 版本（这些文件在 2B 基线没有未提交修改），前端为保存的 2B production dist。LKG/rebuilding 均保留旧事实并展示既有全局发布状态提示；missing 四种页面均有明确 alert、没有假零或错误 skeleton。

## 语义与只读边界

真实 92,908 plays 副本：stats before/after 去除 snapshot metadata 后全字段相等；两个 family 的持久 payload 与原始即时 builder 全字段相等。Records 对账把 `generated_at` 的生成时钟固定为该发布的时间，未删除任何业务字段。结果摘要在 `semantic-real.json`，包含原始/持久 JSON 摘要。

Seed 覆盖默认、近期、custom、L2/L3、compilation true/false、dynamic/fixed、merge enabled/disabled、无数据范围，以及新增跨日/周/年、短片段、左邻连续播放和多艺人 fixture。逐字段保留所有 section、列表顺序、排名、cover/deep-link identity、空值。非 lifetime 使用原 builder/存储 codec 对账，不冒充已经提供自动维护的非默认 API。

public sentinel 对两类原 builder、publisher、JobQueue 设置失败哨兵；比对隔离主库完整 SQL dump 以及临时 analysis/Billboard/Home/yearly 所在目录的文件 bytes/mtime，忽略 SQLite SHM 锁记账文件。exact/LKG/miss/参数不兼容/key 异常均零写入。测试导入前设置 SPOTIFY_STATS_ANALYSIS_CACHE_PATH，复用既有 fail-closed 正式 data/ 边界。

正式主库、Billboard/yearly/Home 前后 SHA-256、大小、mtime 全部一致；正式 analysis_cache.db 前后均不存在。正式主库仍 schema 73，未应用 migration 74；没有修改正式播放事实、revision、settings 或导入表。文件级证明见 `formal-before.json` / `formal-after.json`。

## 设计、维护与文件范围

精确 key、来源依赖、状态、容量及失效规则见[默认分析快照合同](../reference/analysis-result-snapshots.md)。没有 generation/dataset digest 的旧库使用真实完整内容指纹；管理事件计数与语义投影区分，纯显示名称/封面不触发事实重建。来源 watcher 只读且有 4 个连接上限；数据提交竞争时最多三次完整采集，不能缓存跨提交拼接结果。

主要文件：

- `backend/services/analysis_snapshot_store.py`、`analysis_snapshot_revision.py`、`analysis_snapshot_service.py`：独立存储、真实依赖、只读读取和维护。
- `backend/services/analysis_stats_service.py`、`analysis_records_service.py`：原 builder 不改，singleflight 移到 primitive LRU wrapper。
- `backend/api/analysis.py`、`backend/models/analysis.py`：两个 GET 读快照、503 与 metadata contract。
- `backend/core/config.py`、`job_queue.py`、`backend/main.py`：路径、重型执行槽、注册、private 成功提交后检查/排队。不同维护调用原因不再绕过同 key enqueue 锁；durable pending/running 在锁内复查。
- `backend/tests/path_safety.py`、新快照测试与 `contract/test_api_contract.py`：导入前隔离；原有内容断言保留，只增加显式维护准备。
- `frontend/src/hooks/useAnalysis.ts`、`pages/AnalysisStatsPage.tsx`、`pages/AnalysisRecordsPage.tsx`、生成类型、状态测试：复用全局 freshness，区分 unavailable/error。Records 的错误分支实际位于 route container，所以对该文件作直接必要扩展；没有改业务 section。
- `scripts/performance_server.py`：owned harness 显式重定向新的 analysis sidecar；reference/report、测试隔离、文档地图、CHANGELOG。

当前临时 sidecar：471,040 bytes，integrity_check=ok，两个 family、每族一个 key/两代，共四行。压缩 payload 共 319,163 bytes，未压缩合计 2,195,050 bytes；按需解码 JSON，没有序列化 DataFrame。最多 16 key、每 key 两代、每行 raw ≤32MiB，物理文件可复用空闲页。没有创建正式 sidecar。

## 验证与失败记录

- `.venv/bin/pytest -m unit -q`：1779 passed；随后新增来源提交竞争回归在下项通过。
- 最新快照/公开边界/原有 Records API contract：40 passed。
- 前端全量 `npm test -- --maxWorkers=2`：649 passed，4 个既有 optional skipped。
- production build：通过；沿用现有大 chunk warning，未调整预算或拆包。
- Python Ruff / compile：通过；`python3 scripts/docs_audit.py` PASS（103 文档）；`git diff --check` 通过。最终快照专项 26 passed。
- 未跑默认约 47 分钟全栈，因此仅 Partial。

保留的失败：首次测量 harness 把 context 作为错误的位置参数传递；首次 Records cold+warm 中多个 timeout 后仍有计算，关闭进程超时导致该轮 JSON 未完整落盘，原日志保留，不能声称该失败轮原始样本完全可还原。后续补测保留三个独立进程 timeout、20 个有效 warm 和四并发失败。首次浏览器 Records selector 命中了外层 tablist，错误 deadline 保存为 `browser-exact-first-selector-failure.json`，改为具体核心 DOM 后重新验收，没有增加等待。临时 JobQueue 首次恢复到副本中原有其他类型 pending job，未注册 handler，记录为 failed；没有执行 Search/Billboard/外部调用，正式 JobQueue 未被访问。

## 剩余边界与停止点

1. Records exact 独立进程经验 P95=582.60ms，未达到 500ms；warm P95=73.68ms。Stats 分别为 363.66 / 17.10ms。保留慢样本，未重试挑选达标轮。
2. Records rebuild 25.90–35.81 秒等实测仍高于 10 秒。旧库来源完整校验也占用冷读取时间。后续若授权阶段 3B，应先依据这些阶段耗时定位；本批不做算法重构或 C1。
3. 自动维护仅当前设置下 lifetime stats/L2 records；非 lifetime 返回明确 unavailable，提示切换全部时间。任意历史 scope/L3 不自动预建。
4. 复用既有单进程 JobQueue；构建与排队的 per-key 去重是同进程保证，不宣称跨 host 分布式锁。多进程 GET 只读现有 exact，不会构建。
5. 展示名称/封面保留发布时值；纯展示更新不重建事实。文件 lineage 防止跨数据库误借 LKG，也意味着换库必须重新发布。

本批只增加阶段 3A 必需修改，未 commit、push、部署或访问生产。完成报告后停止。

持久证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage3a`（仅报告、日志、脚本和截图，不含数据库副本）。
