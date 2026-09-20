# 阶段 3B：播放纪录快照读取与 builder 专项优化

本批实现和语义验证为 **Partial；两个主要性能目标均未达标**。Records 的有证据热点已局部优化，未改变响应、统计语义或快照合同。最终 exact 五个独立进程经验 P95 **840.21ms**（目标 ≤500ms），默认重建三次中位数 **23.60s**（目标 ≤10s）。Warm P95 **86.20ms**、峰值 RSS **1.29GiB**、四并发 builder=1 通过。停止于本报告，不实施 3C 或通用 C1。

## 范围与可复现基线

- HEAD `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，dirty；阶段 0/0.5/1/2A/2B/3A 与安全收口作为未提交基线保留。
- 重新 Online Backup 到 `/tmp/spotifystats-stage3b/main.db`，92,908 plays；仅此副本应用 migration 74。正式库保持 schema 73。
- 修改前完整 Records 及 snapshot 源码保存在证据的 `before-code/`；同一文件 lineage、相同默认 settings：min_ms=30000、music_only=true、merge_enabled=true、gap=5、dynamic=true、lifetime/L2/compilation=false。
- Profiling 与最终性能样本分开。最终性能测量按新进程串行执行；没有 startup warmup，没有增加等待、timeout 或预算。HTTP timeout 30s、浏览器 core-ready 5s 保留。
- 机器上观测到其他 Chrome 活动，无法量化其影响；所有慢样本照录，没有剔除，也不把低负载 profile 或语义对账耗时替代验收数字。经验分位数仅代表本地这批观测，不是生产 SLA。

## 实际修改

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

## 修改前后 rebuild stage profile

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

## exact 读取分段

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

## 无 profiler API 验收

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

## 无 profiler rebuild 验收

三个全新进程，各使用新的临时 analysis sidecar；同一源文件与规范默认参数。总 wall 包含 request_context、构建、校验和 publish，进程 import 在计时外。

| 样本 | wall s | CPU s | peak RSS GiB | builder / pandas SQL |
|---|---:|---:|---:|---|
| 1 | 23.596797 | 22.313034 | 1.2253 | 1 / 11 |
| 2 | 22.835066 | 21.919576 | 1.2641 | 1 / 11 |
| 3 | 24.882105 | 23.845647 | 1.2884 | 1 / 11 |
| concurrent | 29.917640 | 28.648424 | 1.2870 | 1 / 11 |

三次 median **23.596797s**，min **22.835066s**，max **24.882105s**，**≤10 秒未通过**。50ms timestamped RSS/CPU 全时窗保留；peak **1.2884GiB** 小于约1.4GiB。并发轮四调用仅一次实际 builder、一份 publish，三个跟随者锁内复查 exact。不同 key、不稳定 source fence、失败保留 LKG 由 unit/contract 回归验证。

## 全字段语义与 Yearly Review

在同一 92,908 plays 副本，分别通过 import hook 加载保存的阶段 3A 源码和本批源码；`datetime.utcnow()` 固定为 `2026-09-20T00:00:00Z`。逐层比较字典键、类型、所有标量和所有列表元素/顺序，不仅比较摘要或哈希；全部十组 `all_fields_equal=true`、`mismatch_paths=[]`：默认 L2、L3、L2 compilation、L3 compilation、fixed threshold、merge disabled、last_6_months、2025 custom、1900 empty、2025 Yearly preloaded。

比较包含 period/meta、六类 records、track/album/artist、排名/并列/日期/次数/时长/caption/secondary unit/cover/entity/深链/null/generated_at。Yearly 组预先构造年度 event/entity frames 后将 `load_plays` 和 `_build_entity_frames` 替换成失败 sentinel，确认计算中不重载全库，原 annual milestone 语义不变。

Seed 的 Records all-duration/ranking/reigns/second-phase、Yearly adapter 和 Album Project contract 继续覆盖短片段、左邻、跨日/周/年、多艺人、L2/L3、compilation、原版/豪华版/来源项目差异、prerelease/正式日期、冲突候选、identity 和同名不同艺人。新增测试同时证明对只读 duration view 的 group 聚合不会污染原 frame。

## 双端 production build 与公开边界

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

## 验证与失败记录

- 完整 backend unit：最终 **1,785 passed / 1,085 deselected**，见 `full-unit-final.log`；前一次1,784 passed，随后增加一项 fallback batch 等价测试。
- 定向 Records/Yearly/Album Project/snapshot 初轮 **100 passed**；新增测试初轮 **4 passed**；API/snapshot/batch 后续轮 **39 passed**；最终 affected contract/snapshot **53 passed**，见 `contract-final.log`。
- 受影响前端 **18 passed**；`npm run build` 成功（保留现有大 chunk warning，未放宽阈值）。
- Ruff、compile、docs audit（104份当前文档）和 git diff --check 全部通过，记录见对应日志。未运行约47分钟默认全栈，结论保持 Partial。
- 临时 harness 首次命名 `profile.py` 与 Python 标准库冲突；停止其自有采样进程后重命名。第一次细分源码 profile 缺少 Python3.9 future annotations 标记，修正后重跑；失败日志保留。
- 对账 harness 首轮使用不存在的 `month` period（后端按原规则解析 lifetime），该样本留作 invalid-period；改用 `last_6_months` 后对账。Yearly 首轮漏传 loader conn，补参后重跑，未将失败算通过。
- 一次定向 pytest 命令引用了不存在的测试文件，未执行测试；后续使用真实测试路径。一次浏览器 rebuilding worker 漏 import sqlite3，启动检测到30秒 deadline，公开 exact/LKG四页结果保留，修正后继续；该失败不是产品 API timeout。
- API 性能样本无HTTP失败、无自动重试；所有较慢样本保留。浏览器每次观察独立文件，首次与补测不覆盖。

## 正式数据与工作区

结束时核对 `formal-before.json` / `formal-after.json`：正式主库、Billboard、yearly、7份 Home JSON 的文件集合、SHA-256、大小和 mtime 相同；正式 `analysis_cache.db` 仍不存在。正式主库 schema73，未运行正式 migration74。仅测试 seed/session 临时路径和 Online Backup 副本执行构建；未修改原始播放事实、正式 revision/settings/任务。

本批产品增量仅上表的 Records 文件和 Records 分支的 source digest，另有定向测试与本报告/reference/docs地图/CHANGELOG。Stats builder、API/model/OpenAPI、前端业务和其他域未修改；此前 dirty baseline 保留。没有 commit/push/deploy。

## 是否进入 3C

**值得单独评估，但本轮不实施。** 当前 profile 的小时切片约 **27.3%**、基础 event/artist loader 约 **18.0%**、longevity 约 **14.7%**，三者已占约60%；source digest 在 GET 首读仍占绝大部分。仅继续处理已消除的 SQL N+1 或 JSON 编码无法可靠补足目标。

最小后续范围可先验证 Records 单次调用内的小时切片/artist 时长复用、日 presence/累计事实共用，保持 Yearly 预加载和双轨语义；不需要先建通用持久 C1。若动到共享 logical timeline 或引入来源 manifest，需要独立设计、边界测试与授权，不能用 mtime、MAX(ts) 或未验证的 revision 代替完整来源校验。两个性能目标在当前证据下都应继续标记未达标。

归档整理还修正了报告生成器把 boundary 列表当成 sample 对象，以及系统 Python 缺 psutil 两个工具问题；均未改变测量结果，见 `measurement-limitations.json`。

## 证据位置

原始临时材料：`/tmp/spotifystats-stage3b/`。可长期复核的 JSON、SQL/profile 明细、cProfile 文件、原实现代码、测量 harness、所有日志与截图：

`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage3b/`

数据库副本及 sidecar 只留 `/tmp`，不进入仓库或证据拷贝。当前合同见[分析结果快照](../reference/analysis-result-snapshots.md)。
