# Records读取与共享构建验收

2026-10-26按主题合并。按3B、3C排列。保留两个阶段的不同性能样本、读取波动和重建目标未达标的Partial；后续范围通过不改写原失败。

## 阅读顺序

- [阶段 3B：播放纪录快照读取与 builder 专项优化](#阶段-3b播放纪录快照读取与-builder-专项优化)
- [阶段 3C：Records 单次构建共享事实收口](#阶段-3crecords-单次构建共享事实收口)

## 阶段 3B：播放纪录快照读取与 builder 专项优化

原记录：`2026-09-20-records-read-build-optimization.md`。

本批实现和语义验证为 **Partial；两个主要性能目标均未达标**。Records 的有证据热点已局部优化，未改变响应、统计语义或快照合同。最终 exact 五个独立进程经验 P95 **840.21ms**（目标 ≤500ms），默认重建三次中位数 **23.60s**（目标 ≤10s）。Warm P95 **86.20ms**、峰值 RSS **1.29GiB**、四并发 builder=1 通过。停止于本报告，不实施 3C 或通用 C1。

### 范围与可复现基线

- HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty；阶段 0/0.5/1/2A/2B/3A 与安全收口作为未提交基线保留。
- 重新 Online Backup 到 `/tmp/spotifystats-stage3b/main.db`，92,908 plays；仅此副本应用 migration 74。正式库保持 schema 73。
- 修改前完整 Records 及 snapshot 源码保存在证据的 `before-code/`；同一文件 lineage、相同默认 settings：min_ms=30000、music_only=true、merge_enabled=true、gap=5、dynamic=true、lifetime/L2/compilation=false。
- Profiling 与最终性能样本分开。最终性能测量按新进程串行执行；没有 startup warmup，没有增加等待、timeout 或预算。HTTP timeout 30s、浏览器 core-ready 5s 保留。
- 机器上观测到其他 Chrome 活动，无法量化其影响；所有慢样本照录，没有剔除，也不把低负载 profile 或语义对账耗时替代验收数字。经验分位数仅代表本地这批观测，不是生产 SLA。

### 实际修改

| 文件 | 改动及理由 |
|---|---|
| `backend/services/analysis_snapshot_revision.py` | 仅 Records 分支每 512 行批量摘要，cursor 使用 tuple，消除逐行 Row 包装及两次 hash update；输入字节、排序、全部语义列、source fence 与最终 revision 完全相同。Stats 分支继续旧算法。 |
| `backend/domains/playback/records_discovery.py` | 不重复序列只排序所需列、直接遍历 entity Series；保持遇到重复即重置的原规则。完整专辑回放使用一次 build 的批量映射，fallback 总曲目数以一条 SQL 保留原 LIMIT 1 选择。 |
| `backend/domains/playback/records_album_facts.py` | 批量读取原版项目、原版成员、Spotify 候选并一次计算 canonical key；保留主专辑/original_album/standard/min_merge_level、标题/艺人/正式日期、完整 track_list、冲突集合等原信任条件。查询内 MATERIALIZED CTE 避免 REPLACE join 的全表嵌套扫描，不新增数据库索引或 migration。映射随调用结束释放。 |
| `backend/services/analysis_records_service.py` | event/duration album frame 共用本次已读 membership；仍分别处理事件与时长，原 fallback、L2/L3/compilation 与预加载入口保留。 |
| `records_helpers.py`、`records_obsession.py`、`records_time.py` | 只读聚合显式使用 duration view；会修改/attach 的调用仍取得独立 copy；移除先取 copy 再 copy 的重复。 |
| `records_longevity.py` | 日期转换移出逐实体循环；每个实体仍去重并按日期排序，保持 first/last、并列规则与输出顺序。 |
| `backend/tests/unit/test_records_build_optimization.py` | 指纹逐字节等价、512 行边界/文本/NULL/BLOB、序列重置/稳定排序、时长 frame 不污染、1→100 项目查询数不增长、fallback 选择等价。 |

未采用 raw JSON fast path：profile 显示主要成本在 source fingerprint；保留现有 Pydantic 验证、完整响应、JSON encode 与 GZip middleware。request key、builder version `analysis_records_v1`、payload checksum、response model/OpenAPI 均未更改。没有新进程内缓存或跨 API 的 DataFrame/C1。

### 修改前后 rebuild stage profile

以下是带 profiler 的归因数据（秒），不是验收耗时。嵌套阶段不可相加。全部阶段 wall/CPU、DataFrame 行数/copy、SQL 类型/次数/耗时/行数及双方 cProfile self/cumulative top30 见证据 `profile-appendix.md`、`before-detail2-profile.json`、`after-detail2-profile.json`。

| 阶段 | 3A before wall | 3B after wall |
|---|---:|---:|
| source_revision | 0.7753 | 0.3431 |
| load_plays | 2.0694 | 1.7799 |
| lifetime_event_frame_copy | 0.0103 | 0.0096 |
| attach_scoped_records_duration | 6.3300 | 5.9525 |
| track_canonicalization | 0.0551 | 0.0540 |
| apply_canonical_song_keys | 1.0260 | 0.0773 |
| load_album_project_membership | 0.0898 | 0.0475 |
| album_event_join | 0.1215 | 0.1276 |
| album_duration_join | 0.1549 | 0.1102 |
| _load_reliable_album_release_dates | 0.0065 | 0.0069 |
| load_plays_for_artists | 2.1947 | 2.1487 |
| compute_obsession_records | 1.9072 | 1.5726 |
| compute_time_pattern_records | 1.2635 | 1.1208 |
| compute_reign_records | 2.0435 | 1.4910 |
| compute_longevity_records | 8.5762 | 3.1998 |
| compute_discovery_records | 10.9925 | 1.5921 |
| compute_behavior_records | 0.7431 | 0.7248 |
| _add_cover_urls_to_records | 1.0585 | 0.9845 |
| _serialize_records | 0.1742 | 0.1644 |
| publish | 0.0252 | 0.0261 |

整体 profile wall/CPU：38.914/38.302s → 21.823/21.509s；RSS 1.334 → 1.229GiB。

- SQLite 调用 **6,004 → 240**，累计 SQL wall **2.705 → 1.189s**，返回行数（含重复读取）**1,663,900 → 673,524**。pandas SQL **115 → 11**（最终无 profiler rebuild instrumentation）。
- 原项目 helper 调用 1,357 次；其中 primary lookup 1,357、member lookup 1,133、Spotify candidate query 1,117，另有 fallback total 727 次。优化后原版 facts 的基础 SQL 固定三条，加一次 canonical loader；seed 1/100 项目查询数相同。fallback totals 一条 SQL，原单项目 LIMIT 1 仍由相关子查询保留，不冒称其 SQL 内部工作量与项目数无关。
- `_no_repeat_streak` 三类共 **7.329 → 0.100s**；`_album_full_replays` **2.327 → 0.343s**；longevity **8.576 → 3.200s**。同名异曲的头像原来已批量读取，未虚构 N+1。
- duration helper 仍有 57 次调用，但 44 次 group 聚合不再完整复制附着的宽 duration frame；主 copy 明细保留在 profile。event/artist 两次小时切片共约 5.952s，仍是最大剩余阶段；没有修改共享 logical timeline 算法。

### exact 读取分段

单位 ms。before/after 各一次带 profiler 的独立请求，只用于定位；网络验收另见下表。

| 阶段 | before | after |
|---|---:|---:|
| 完整 import/启动准备（请求外） | 2143.96 | 2327.83 |
| source revision | 663.28 | 335.05 |
| sidecar connect/SELECT/row metadata（read 扣 decode） | 0.36 | 0.40 |
| bounded zlib 解压 | 0.486 | 0.520 |
| checksum/长度/对象校验及 codec residual | 0.304 | 0.281 |
| JSON decode | 5.00 | 4.46 |
| Pydantic validate | 4.47 | 4.70 |
| Pydantic serialize | 5.12 | 5.26 |
| HTTP JSON encode | 11.70 | 10.78 |
| GZip write + finish | 7.06 | 7.03 |
| TestClient 总请求（不含 import） | 711.34 | 380.24 |

metadata 本身只是在 read 后动态组装小字典；before cProfile 的 `read_snapshot` self 为 0.0067ms，request key/settings/metadata 合计 residual 约 1ms。上述 SQL/codec residual 由包含计时相减，不伪称硬件独立计时。最终 HTTP 每样本另外记录 server stage delta、headers/body received 与 total；并发 delta 会重叠，只使用单请求样本做分段归因。网络阶段是 loopback 客户端接收，不含公网 RTT；没有本地重压 gzip 估算传输字节。

### 无 profiler API 验收

每组 5 个独立后端进程（健康检查及 settings 不预热 Records），第 5 个进程继续 20 次 warm；第 6 个新进程发 4 并发。全部 HTTP 200，builder/原服务 LRU miss=0。按原始成功样本线性插值经验 P95。

| 轮次/状态 | 原始值或 min / median / P95 / max（ms） | 成功/失败 |
|---|---|---|
| before / cold | 857.816, 421.977, 679.814, 416.158, 668.397 | 5/0 |
| before / warm | 45.745 / 46.716 / 51.487 / 86.969 | 20/0 |
| before / concurrent4 | 549.817, 551.203, 576.439, 577.323 | 4/0 |
| after-read / cold | 623.925, 375.432, 379.467, 522.927, 536.255 | 5/0 |
| after-read / warm | 49.437 / 51.257 / 56.572 / 99.446 | 20/0 |
| after-read / concurrent4 | 552.435, 585.759, 594.77, 595.605 | 4/0 |
| final / cold | 792.995, 508.099, 535.374, 852.02, 561.691 | 5/0 |
| final / warm | 54.321 / 67.317 / 86.202 / 154.466 | 20/0 |
| final / concurrent4 | 1039.351, 1042.291, 1051.409, 1061.944 | 4/0 |

`cold` 在这些历史字段中仅表示 **process cold + snapshot exact**，不是 snapshot missing。after-read 为第一轮局部实现校准，final 是完整实现复测；三组数据都保留，不选择最小值宣称达标。最终 cold P95=840.215ms **未通过**，warm P95=86.202ms **通过**；四并发 exact 全成功且 builder=0。

完整 HTTP 响应 raw **2,096,306 bytes**；实际 HTTP gzip 在相同旧发布下 **126,376 bytes**。重新发布仅 generated_at 改变，业务字段逐项相等，gzip 大小有少量变化；浏览器样本保存实际 Content-Length。单份持久 payload raw **891,887 bytes**、zlib **约125,705 bytes**，单行 sidecar **139,264 bytes**；HTTP 更大来自原 response model 的 optional/null 字段补全，本批未减少字段或行数。两代发布后 sidecar 约270KB，具体轮次保留在文件 manifest。

### 无 profiler rebuild 验收

三个全新进程，各使用新的临时 analysis sidecar；同一源文件与规范默认参数。总 wall 包含 request_context、构建、校验和 publish，进程 import 在计时外。

| 样本 | wall s | CPU s | peak RSS GiB | builder / pandas SQL |
|---|---:|---:|---:|---|
| 1 | 23.596797 | 22.313034 | 1.2253 | 1 / 11 |
| 2 | 22.835066 | 21.919576 | 1.2641 | 1 / 11 |
| 3 | 24.882105 | 23.845647 | 1.2884 | 1 / 11 |
| concurrent | 29.917640 | 28.648424 | 1.2870 | 1 / 11 |

三次 median **23.596797s**，min **22.835066s**，max **24.882105s**，**≤10 秒未通过**。50ms timestamped RSS/CPU 全时窗保留；peak **1.2884GiB** 小于约1.4GiB。并发轮四调用仅一次实际 builder、一份 publish，三个跟随者锁内复查 exact。不同 key、不稳定 source fence、失败保留 LKG 由 unit/contract 回归验证。

### 全字段语义与 Yearly Review

在同一 92,908 plays 副本，分别通过 import hook 加载保存的阶段 3A 源码和本批源码；`datetime.utcnow()` 固定为 `2026-09-20T00:00:00Z`。逐层比较字典键、类型、所有标量和所有列表元素/顺序，不仅比较摘要或哈希；全部十组 `all_fields_equal=true`、`mismatch_paths=[]`：默认 L2、L3、L2 compilation、L3 compilation、fixed threshold、merge disabled、last_6_months、2025 custom、1900 empty、2025 Yearly preloaded。

比较包含 period/meta、六类 records、track/album/artist、排名/并列/日期/次数/时长/caption/secondary unit/cover/entity/深链/null/generated_at。Yearly 组预先构造年度 event/entity frames 后将 `load_plays` 和 `_build_entity_frames` 替换成失败 sentinel，确认计算中不重载全库，原 annual milestone 语义不变。

Seed 的 Records all-duration/ranking/reigns/second-phase、Yearly adapter 和 Album Project contract 继续覆盖短片段、左邻、跨日/周/年、多艺人、L2/L3、compilation、原版/豪华版/来源项目差异、prerelease/正式日期、冲突候选、identity 和同名不同艺人。新增测试同时证明对只读 duration view 的 group 聚合不会污染原 frame。

### 双端 production build 与公开边界

核心条件：路由 `/analysis/records`、Records 分类“高光时刻”、单日巅峰真实实体深链、核心 API 200 且 main 无 error alert。503 的明确不可用态单列，不算 core-ready。每次页面使用新的后端进程和浏览器 target；记录 API 瀑布、headers/body 大小、long task、TBT、LCP/CLS，未把点击或 FID 当 INP。

首次 browser run 的 exact/LKG 四页已成功；追加 decode 观测仍保留首次结果。rebuilding 先做临时目标控制样本，随后 `actual-` 轮让真实 private builder 向 **与 public 相同的临时 sidecar** 发布；事件时间证明浏览器读取发生在 builder start/end 之间。公开进程的 builder、publish、JobQueue 方法装失败 sentinel；文件 before/after 相同。整个过程仅人工改变临时 playback_revision，正式来源未变化。

| 轮次/状态 | presentation | API ready ms | DOM core-ready ms | API 至 core ms | 原生 Response.json body读取+解码 ms | long task / TBT ms | 核心 API 次数 / raw / compressed |
|---|---|---:|---:|---:|---:|---|---|
| exact-desktop | desktop | 1264.03 | 1632.00 | 367.97 | 未单独观测 | 0 / 0.00 | 1 / 2096306 / 126376 |
| exact-mobile | mobile | 1230.21 | 1590.00 | 359.79 | 未单独观测 | 0 / 0.00 | 1 / 2096306 / 126376 |
| lkg-desktop | desktop | 1174.01 | 1532.00 | 357.99 | 未单独观测 | 0 / 0.00 | 1 / 2096316 / 126432 |
| lkg-mobile | mobile | 1187.60 | 1600.00 | 412.40 | 未单独观测 | 0 / 0.00 | 1 / 2096316 / 126432 |
| decode-exact-desktop | desktop | 797.61 | 1145.00 | 347.39 | 6.10 | 0 / 0.00 | 1 / 2096306 / 126378 |
| decode-exact-mobile | mobile | 766.41 | 1108.00 | 341.59 | 6.00 | 0 / 0.00 | 1 / 2096306 / 126378 |
| decode-lkg-desktop | desktop | 768.46 | 1116.00 | 347.54 | 5.90 | 0 / 0.00 | 1 / 2096316 / 126429 |
| decode-lkg-mobile | mobile | 777.04 | 1109.00 | 331.96 | 6.00 | 0 / 0.00 | 1 / 2096316 / 126429 |
| resume-missing-desktop | desktop | 392.57 | unavailable | unavailable | 0.20 | 0 / 0.00 | 1 / 184 / 184 |
| resume-missing-mobile | mobile | 430.60 | unavailable | unavailable | 1.70 | 0 / 0.00 | 1 / 184 / 184 |
| actual-rebuilding-desktop | desktop | 823.91 | 1171.00 | 347.09 | 5.80 | 0 / 0.00 | 1 / 2096316 / 126436 |
| actual-rebuilding-mobile | mobile | 764.33 | 1100.00 | 335.67 | 5.90 | 0 / 0.00 | 1 / 2096316 / 126432 |

原生 `Response.json()` 使用原实现，不改 JSON 解析语义；计时包含尚未读完的 body、UTF-8 decode 和 parse，不能称纯 JSON parser CPU。API end 至 DOM core-ready 为解析/Query 通知/React render/调度的合计上界，含25ms轮询粒度，不冒称 React 独立 render 时间。missing 每页核心 API 一次503、无重复重试、明确 unavailable；不计性能成功。所有截图与采样原文保留。LCP/CLS 的原始条目在各样本 `browser_metrics`；本轮没有输入交互指标。

Public exact/LKG/miss/参数不兼容/key 异常/损坏 payload 的现有 sentinel 测试比对隔离主库 SQL dump 和 analysis/Billboard/Home/yearly 文件 bytes/mtime；GET 不写、不冷建、不 enqueue。source fence、失败 LKG、同 key singleflight、不同 key 不错误合并和 OpenAPI 合同均继续通过。

### 验证与失败记录

- 完整 backend unit：最终 **1,785 passed / 1,085 deselected**，见 `full-unit-final.log`；前一次1,784 passed，随后增加一项 fallback batch 等价测试。
- 定向 Records/Yearly/Album Project/snapshot 初轮 **100 passed**；新增测试初轮 **4 passed**；API/snapshot/batch 后续轮 **39 passed**；最终 affected contract/snapshot **53 passed**，见 `contract-final.log`。
- 受影响前端 **18 passed**；`npm run build` 成功（保留现有大 chunk warning，未放宽阈值）。
- Ruff、compile、docs audit（104份当前文档）和 git diff --check 全部通过，记录见对应日志。未运行约47分钟默认全栈，结论保持 Partial。
- 临时 harness 首次命名 `profile.py` 与 Python 标准库冲突；停止其自有采样进程后重命名。第一次细分源码 profile 缺少 Python3.9 future annotations 标记，修正后重跑；失败日志保留。
- 对账 harness 首轮使用不存在的 `month` period（后端按原规则解析 lifetime），该样本留作 invalid-period；改用 `last_6_months` 后对账。Yearly 首轮漏传 loader conn，补参后重跑，未将失败算通过。
- 一次定向 pytest 命令引用了不存在的测试文件，未执行测试；后续使用真实测试路径。一次浏览器 rebuilding worker 漏 import sqlite3，启动检测到30秒 deadline，公开 exact/LKG四页结果保留，修正后继续；该失败不是产品 API timeout。
- API 性能样本无HTTP失败、无自动重试；所有较慢样本保留。浏览器每次观察独立文件，首次与补测不覆盖。

### 正式数据与工作区

结束时核对 `formal-before.json` / `formal-after.json`：正式主库、Billboard、yearly、7份 Home JSON 的文件集合、SHA-256、大小和 mtime 相同；正式 `analysis_cache.db` 仍不存在。正式主库 schema73，未运行正式 migration74。仅测试 seed/session 临时路径和 Online Backup 副本执行构建；未修改原始播放事实、正式 revision/settings/任务。

本批产品增量仅上表的 Records 文件和 Records 分支的 source digest，另有定向测试与本报告/reference/docs地图/CHANGELOG。Stats builder、API/model/OpenAPI、前端业务和其他域未修改；此前 dirty baseline 保留。没有 commit/push/deploy。

### 是否进入 3C

**值得单独评估，但本轮不实施。** 当前 profile 的小时切片约 **27.3%**、基础 event/artist loader 约 **18.0%**、longevity 约 **14.7%**，三者已占约60%；source digest 在 GET 首读仍占绝大部分。仅继续处理已消除的 SQL N+1 或 JSON 编码无法可靠补足目标。

最小后续范围可先验证 Records 单次调用内的小时切片/artist 时长复用、日 presence/累计事实共用，保持 Yearly 预加载和双轨语义；不需要先建通用持久 C1。若动到共享 logical timeline 或引入来源 manifest，需要独立设计、边界测试与授权，不能用 mtime、MAX(ts) 或未验证的 revision 代替完整来源校验。两个性能目标在当前证据下都应继续标记未达标。

归档整理还修正了报告生成器把 boundary 列表当成 sample 对象，以及系统 Python 缺 psutil 两个工具问题；均未改变测量结果，见 `measurement-limitations.json`。

### 证据位置

原始临时材料：`/tmp/spotifystats-stage3b/`。可长期复核的 JSON、SQL/profile 明细、cProfile 文件、原实现代码、测量 harness、所有日志与截图：

`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage3b/`

数据库副本及 sidecar 只留 `/tmp`，不进入仓库或证据拷贝。当前合同见[分析结果快照](../reference/analysis-result-snapshots.md)。

## 阶段 3C：Records 单次构建共享事实收口

原记录：`2026-09-20-records-invocation-facts.md`。

**Partial；Records 阶段实现到此停止。** 三次独立新进程重建中位数 **17.49s**，较同轮阶段 3B 基线 **22.41s** 下降 **21.9%**，但 **≤10s 未通过**。七次独立进程 exact 首读经验 P95 **469.05ms**，本组 **≤500ms 通过**；本批未修改读取代码，不能据此宣称消除了此前 840ms 的波动。Warm 20 次 P95 **57.72ms** 通过。建议允许进入阶段 4 的独立 Billboard 工作，但必须保留 Records 重建目标未完成的状态；本轮没有开始阶段 4，也不追加 3D。

### 当前基线与范围

- HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty。所有已有未提交阶段作为基线保留；本轮之前的逐文件 SHA 与 Python 源码在 `worktree-before.json` / `before-code/`。
- 先读取 AGENTS/CLAUDE、阶段 3B 报告、Records/播放统计/音乐档案规则，随后完成 `before-detail-profile.json` 才修改产品代码。基线十组 payload 从保存的阶段 3B 源码独立加载；`semantic-before-*.json` 为原始完整结果。
- 正式源通过 SQLite `mode=ro` + Online Backup 复制到 `/tmp/spotifystats-stage3c/main.db`，**92,908 plays**；仅此副本保持阶段 3B 的 migration 74 测量状态。正式主库内容未改变，仍是原 schema 73。全部 sidecar/Home 路径显式指向 `/tmp/spotifystats-stage3c/`；pytest 使用现有 session fail-closed 临时隔离。
- 相同副本路径、默认设置、L2、dynamic threshold、合并开、gap=5、lifetime、compilation=false。没有修改 loader、共享 logical timeline、snapshot/source revision/API/model/frontend/Billboard/Search/Homepage 产品逻辑。

### 已修改及等价性依据

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

### 完整字段语义验证

十组全部 `all_fields_equal=true`、`mismatch_paths=[]`：lifetime L2、L3、L2 compilation、L3 compilation、fixed threshold、merge off、last_6_months、2025 custom、1900 empty、2025 Yearly preloaded。双方同一数据库/配置，generated_at 固定为同一时刻。比较全部字典键、类型、每个标量、所有榜单元素和顺序，包含 period/meta、六类 Records、全部实体、日期、精确时长、并列、深链、cover 和 null；没有只验 Top 1。

Yearly 路径预先构建年度 frame 后给全量 reload 方法安装失败 sentinel，确认没有回到全库重载。Seed 回归覆盖短片段、跨边界、L2/L3 membership、compilation、artist fan-out、原版专辑、过滤及排序合同。三类实体分别建立 facts，没有混合粒度。

所有重建 before/after 的完整 source revision 和 request key 均相同：

- request key：`03ea5900b76803adea6231bfe1b6fd9bbf2ce5dd4fd262082747a80cdd5cb93f`
- source revision：`6a54258b53fee4a7b14b76d75ca82abd892cc0ead45c1ded7aec4f99e8421d11`
- builder version：`analysis_records_v1`

这是临时副本绝对路径下的 key，不能复制到正式 namespace。来源全内容摘要、revision bytes、校验、失效、atomic publish、LKG、singleflight 和 public-readonly 合同均未修改。

### 重建验收：独立新进程、串行交错 before/after

每组独立进程、新 sidecar；wall 包含 request context、完整 builder、验证和 publish，import 不在计时窗口。CPU/RSS 使用50ms时间序列，原始值在每个 `rebuild-*.json`。没有与本轮测试、profile 或前端 build 同时执行；不终止其他应用，不剔除慢样本。

| 对次 | 当前 3B baseline wall s | 3C wall s | 3C CPU s | 3C peak RSS GiB |
|---|---:|---:|---:|---:|
| 1 | 22.407859 | 19.909870 | 19.131661 | 1.2941 |
| 2 | 23.242454 | 16.505497 | 16.352876 | 1.2811 |
| 3 | 19.812653 | 17.489450 | 17.168362 | 1.2855 |

3C min/median/max：**16.505497 / 17.489450 / 19.909870s**，3/3 成功，0失败；≤10s **未通过**。三个样本只报告观测值，不生成稳定 P95。同期基线原始值为 22.407859, 23.242454, 19.812653s。

四并发同 key 维护耗时 **16.887475s**，实际 builder **1**、publish **1**，其余3调用锁内复查 exact；pandas SQL **11**。前后 SQL 总调用均 **240**（profile包括 PRAGMA/执行/读回归因，非全部SELECT），未把 SQL 数未变伪称为 loader 优化。3C 三样本及并发 peak RSS 最大 **1.2941GiB**，低于既有约1.4GiB边界。

### 剩余 profile 与停止依据

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

### exact / warm / 并发 GET

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

#### 七个冷首读分段

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

### Desktop / Phone 真实浏览器

运行production build，loopback服务、独立浏览器profile和每页独立后端进程。CDP请求拦截只允许本地GET/HEAD；public builder/publish/JobQueue安装失败sentinel。首屏条件为路由正确、分类和单日巅峰实体事实出现、Records API200、没有错误alert。5s core预算与30s请求预算不变，没有固定等待。截图已检查，横向overflow=0。

| Presentation | API ready ms | DOM core-ready ms | API至core ms | Records请求/状态 | raw/gzip bytes | 首屏TBT ms |
|---|---:|---:|---:|---|---|---:|
| Desktop 1280×900 | 1132.70 | 1473.00 | 340.30 | 1 / 200 | 2096306 / 126379 | 0.00 |
| Phone 390×844 | 753.96 | 1094.00 | 340.04 | 1 / 200 | 2096306 / 126379 | 0.00 |

两端均通过真实鼠标/触控：次数→时长、专辑、艺人、长线陪伴。断言按钮selected/pressed、实体深链、URL family和四个longevity模块事实出现。筛选过程仍仅1次核心Records GET，无404、重试或错误skeleton；公开主库/analysis/Home/yearly/Billboard文件before/after相同。周期参数的完整字段等价在上述recent/custom/empty和Yearly场景验证；本轮浏览器交互范围是指标/实体/分类，不冒称遍历所有周期UI。

请求瀑布、响应大小、body读取+JSON解码、LCP/CLS/long task及动作DOM分别保存；不把自动点击当INP。首屏与筛选后截图均保留。

### 测试与数据边界

- 新增事实/既有Records/Yearly adapter定向：**27 passed**。
- 完整后端unit：**1,791 passed / 1,085 deselected**。
- Album Project、Records API、analysis snapshot与public boundary：**58 passed**。
- 前端相关5文件：**50 passed**；production build成功。保留既有大chunk warning，没有放宽阈值。
- Ruff、Python compile、docs audit、git diff --check结果见最终日志；没有运行完整约47分钟全栈，交付为 **Partial**。

正式目录前后清单共 **4,180** 个文件（主库/WAL、正式sidecar/snapshot、covers及缓存等，排除无关imports/exports/backups归档）。**全部文件集合、bytes SHA-256、大小相同**；4,179项mtime也相同。唯一metadata差异是 `data/spotify_stats.db-shm` 的mtime在Online Backup时段变化，32,768bytes及SHA-256完全相同。未回写或伪造mtime。正式主库、WAL、所有快照/sidecar/封面/cache的mtime均相同，正式analysis sidecar仍不存在。该SHM元数据观察单列在 `formal-comparison.json`，不写成“所有文件时间戳都未变化”。

正式主库未作为builder/migration/测试连接写入目标；完整主库与WAL内容相同证明业务表、原始播放事实、revision/settings/JobQueue均未被本轮改写。临时源在测量间保持不变；公开边界测试另验证missing/LKG/不兼容参数、key异常、损坏payload不冷建、不发布、不排队。

### 停止与 Git

保留本轮之前全部dirty改动。仅增加上列4个产品文件、1个测试文件及必要文档增量；没有commit/push/deploy。完整增量清单、patch、验证日志及原始测量材料均随证据保存。

**建议下一步可由用户决定进入阶段4 Billboard**：统计/数据安全、全字段等价和回归已闭合，没有需要继续阻塞在Records的正确性问题；Records的≤10s目标仍明确未完成，稳定冷读SLA也未被证明。阶段3C已经停止，不安排新的Records实现或Billboard工作。

原始材料：`/tmp/spotifystats-stage3c/`。持久证据（不含数据库副本/sidecar）：

`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage3c/`
