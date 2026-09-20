# 阶段 1：可达专辑详情与 public-readonly 快照边界

> 日期：2026-09-19；基线：本地 main / origin/main `faa5e4e4`。
> 状态：四项实现及定向验证完成；全栈结论 **Partial**。未 commit、push、部署或访问生产。
> 当前合同：[Home / Billboard 公开快照读取合同](../reference/public-snapshot-read-contract.md)。

## 实现结果与文件范围

| 项目 | 实现结果 | 主要文件 |
|---|---|---|
| 专辑项目公开 GET | allowlist 增加整数 project_id 的 Billboard 专辑项目 view，以及 music stats/rankings/plays/play-dates；public/private flags 不变，写接口不开放 | `backend/core/access_surface.py` |
| Billboard 发布读取 | public 分支先于 lock、force 和 builder；exact / 同 request-key LKG 返回事实及 freshness/source/target；缺失、参数不兼容、key 异常返回结构化 503，不冷建、不排队、不发布 | `backend/domains/billboard/persistent_cache.py` |
| Billboard 非 staged GET | 详情、project-only 和旧 release-cycle GET 在进入原有 view 前验证相同过滤的 full_data 已发布；响应头标明发布状态 | `backend/api/billboard/__init__.py` |
| Home 文件读取 | public 跳过 private 计算 LRU，只读已发布 exact/语义 LKG；文件 writer 和 thread starter 同时设公开边界；private 发布保存来源 metadata，保留原子替换与旧 LKG | `backend/services/home_service.py` |
| 默认维护 family | readiness 与 rebuild 覆盖 weekly、all_time、full_data、records、power_scores、summaries、year_end；all_time 已存在时也明确确保独立 family 发布 | `backend/services/billboard_snapshot_service.py` |
| 响应与前端 | 可选 snapshot 元数据、503 schema、独立 unavailable 错误且不自动重试；Home 缺失与空数据区分；已观察 Query 的 LKG 显示旧发布提示并保留事实 | `backend/models/{snapshot,home}.py`、`backend/api/home.py`、`backend/api/billboard/{data,year_end}.py`；前端 `api/{client,errors,query-client}.ts`、`components/shared/SnapshotStatusNotice.tsx`、`components/layout/AppLayout.tsx`、`features/home/HomeStates.tsx`、`pages/DashboardPage.tsx`、生成类型 |

额外 API dependency 是关闭实际绕过 staged cache 的 GET 所必需的范围；没有更改详情算法。新增 public 路径是既有专辑只读语义，不开放治理、导入、设置修改或重建。Records 页面目前仍消费 full_data；本轮未切换为瘦响应，默认维护额外发布专用 records，保证其 GET 也能直接消费。

缓存 key、来源 revision、builder-version、统计计算和每行 atomic publish 均沿用既有实现。LKG 必须 request-key/语义兼容；key 构造异常不猜测兼容性。warming 表示目标尚未发布而有旧事实，不表示 public 请求已经启动任务。旧 Home LKG 未存来源时明确为 null。

## 定向验证

| 验证 | 结果 |
|---|---|
| 受影响 backend unit + contract | **87 passed**，31.61 秒；1 条既有 LibreSSL/urllib3 环境 warning |
| 前端相关测试 | **85 passed，12 文件**：首批 43、Billboard/详情回归 40、新增 Desktop/Phone 名称路由用例 2；最终专辑测试文件共 12 passed |
| production build | `tsc -b && vite build` 通过；沿用现有大 chunk warning，未放宽阈值 |
| 定向 Ruff / frontend ESLint | 通过 |
| 文档与补丁检查 | `python3 scripts/docs_audit.py`、`git diff --check` 均通过 |
| 全栈 | **Partial**；本次未运行默认约 47 分钟的完整全栈门禁 |

新增 `backend/tests/unit/test_home_publication_boundary.py`、`backend/tests/contract/test_public_snapshot_boundary.py`、`frontend/src/tests/snapshot-status.test.tsx`；扩展 Billboard persistent / maintenance、Home cache readiness、public surface、API errors、music uncharted detail 测试。

覆盖 exact、同 key LKG、完全缺失、参数不兼容、key 异常、损坏发布、误传 force-rebuild、私有失败保留旧发布及 committed WAL 可见性。seed contract 遍历公开 allowlist 中所有 Billboard GET，在缺失/key 异常下给昂贵 builder 设置立即失败 sentinel；Home 同时封锁 private LRU、文件 writer、线程 starter。验证 public/private 专辑项目 summary/project/stats/rankings/plays/play-dates 合同。没有减少测试覆盖、增加 timeout 或固定等待来达标。

## Online Backup 副本与零应用写入证据

真实测量基于 92,908 条 plays 的临时 SQLite Online Backup。应用 DB_PATH、Billboard sidecar、Home JSON、yearly cache 均指向临时目录；禁用 dotenv 和启动维护，测量入口禁止外网。正式 `data/spotify_stats.db` 仅用作只读 backup 源。缺失状态切换到临时不存在路径；LKG 用临时 revision 注入；不清除正式快照。

副本先由 private 维护发布：Billboard **22.148 秒**、Home **36.992 秒**。Billboard 返回 7 个 family，year_end 覆盖 2022–2026，`default_ready=true`；随后 public Records exact 读取成功。该耗时用于证明维护发布，不代表重建算法已优化。

5 状态 × 8 API × 3 次 public 请求共 120 次。Home exact 另测 3 次。builder/锁/writer/thread/JobQueue sentinel 无触发；请求前后 DB/WAL 与 Home JSON 内容及 mtime 相同，相关表（background_jobs、settings、搜索 revision/variant、playback_import_state）和内存队列相同。seed contract 还对比全部表内容。

**SQLite 边界：**正常 WAL 只读连接可能创建或更新 `-shm` read-mark 锁共享内存，因此不声称操作系统层所有文件完全零变化。数据库/WAL 内容、JSON 与任务队列零变更已有证据。保留 committed WAL 可见性测试，未用 immutable 模式忽略 WAL，也未在本轮改变日志/存储机制。

## public 响应实测

单位 ms；每格 3 次，median / max；这是本地副本样本，不是 P95 或生产 SLA。下表所有缺失和 LKG 响应最大值低于 300 ms。现有 Home preview revision 含进程状态，重启后的首组实际命中 LKG，按响应 metadata 标为 restart LKG，不误报 exact。单独 private 发布后的 Home exact 为 **211.35 / 215.09 ms**，3 次均 current 且文件无变化。

| API | 状态 | HTTP | median ms | max ms |
|---|---|---:|---:|---:|
| /api/home/overview | restart LKG | 200 | 58.48 | 225.14 |
| /api/billboard/weekly | exact | 200 | 132.29 | 163.67 |
| /api/billboard/all-time | exact | 200 | 163.95 | 213.21 |
| /api/billboard/data | exact | 200 | 230.62 | 233.44 |
| /api/billboard/records | exact | 200 | 17.25 | 17.89 |
| /api/billboard/power-scores | exact | 200 | 27.53 | 27.75 |
| /api/billboard/summaries | exact | 200 | 44.92 | 45.77 |
| /api/billboard/year-end | exact | 200 | 11.43 | 12.50 |
| /api/home/overview | lkg | 200 | 68.97 | 69.03 |
| /api/billboard/weekly | lkg | 200 | 150.86 | 154.27 |
| /api/billboard/all-time | lkg | 200 | 174.10 | 203.64 |
| /api/billboard/data | lkg | 200 | 185.66 | 237.41 |
| /api/billboard/records | lkg | 200 | 17.64 | 17.77 |
| /api/billboard/power-scores | lkg | 200 | 29.37 | 68.52 |
| /api/billboard/summaries | lkg | 200 | 45.07 | 46.11 |
| /api/billboard/year-end | lkg | 200 | 11.87 | 11.97 |
| /api/home/overview | incompatible | 503 | 58.67 | 218.29 |
| /api/billboard/weekly | incompatible | 503 | 10.14 | 10.72 |
| /api/billboard/all-time | incompatible | 503 | 9.96 | 10.01 |
| /api/billboard/data | incompatible | 503 | 9.60 | 10.19 |
| /api/billboard/records | incompatible | 503 | 10.28 | 10.79 |
| /api/billboard/power-scores | incompatible | 503 | 9.44 | 9.94 |
| /api/billboard/summaries | incompatible | 503 | 9.76 | 9.95 |
| /api/billboard/year-end | incompatible | 503 | 9.32 | 9.76 |
| /api/home/overview | missing | 503 | 57.39 | 58.16 |
| /api/billboard/weekly | missing | 503 | 9.29 | 9.39 |
| /api/billboard/all-time | missing | 503 | 9.19 | 9.60 |
| /api/billboard/data | missing | 503 | 9.30 | 9.74 |
| /api/billboard/records | missing | 503 | 9.27 | 9.46 |
| /api/billboard/power-scores | missing | 503 | 9.36 | 9.57 |
| /api/billboard/summaries | missing | 503 | 9.25 | 9.56 |
| /api/billboard/year-end | missing | 503 | 9.16 | 9.40 |
| /api/home/overview | key_error | 503 | 45.27 | 46.88 |
| /api/billboard/weekly | key_error | 503 | 3.28 | 4.29 |
| /api/billboard/all-time | key_error | 503 | 2.81 | 3.01 |
| /api/billboard/data | key_error | 503 | 2.69 | 2.70 |
| /api/billboard/records | key_error | 503 | 2.76 | 2.97 |
| /api/billboard/power-scores | key_error | 503 | 2.68 | 2.73 |
| /api/billboard/summaries | key_error | 503 | 2.70 | 2.89 |
| /api/billboard/year-end | key_error | 503 | 2.63 | 2.69 |

## Desktop / Phone 真实路由

使用 production build、本地真实副本后端和 headless Chromium；阻断非本地请求及写请求。入口为 `/music/albums/The%20Life%20of%20a%20Showgirl?artist=Taylor%20Swift`，两端均解析为 `/music/album-projects/41476?artist=Taylor+Swift`。核心 ready 定义为 project URL 已落地且真实“总播放次数”卡片出现，无加载失败提示。

| presentation | 视口 | 核心 ready | 核心事实 | API 请求 | 404 / 重复 project 请求 |
|---|---|---:|---|---:|---|
| Desktop | 1280×900 | 1,780.79 ms | 1,663 次 / 97.7 h | 12 | 0 / 0 |
| Phone | 390×844 | 3,047.26 ms | 1,663 次 / 97.7 h | 12 | 0 / 0 |

Desktop 非核心 `include_rank_context=true` 全局排名仍触发现有 30 秒请求超时（`net::ERR_ABORTED`），其余有 HTTP 响应的 API 均 200；播放记录/日历/排行也仍有约 22 秒的冷请求。Phone 随后全局排名请求 200，约 6.6 秒。核心可达修复已经通过，**不把本次结果描述为全部详情数据快速就绪**。该即时统计开销属于后续性能阶段，本轮保留。

## 证据与剩余边界

本地证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage1`。包括 `public-measurements.json`（原始响应状态、耗时、前后快照）、`home-exact.json`、`maintenance.json`、`browser-routes.json`、Desktop/Phone 截图、backend/build 日志与临时测量 harness。数据库副本不纳入仓库或交付目录。

- public snapshot miss 不冷建；已发布 full_data 存在时，原有详情投影仍可计算，本轮未实现详情全量持久化。
- Home 重启后可因既有 preview revision 变化读取 LKG，public 不主动重建，等待 private 受控维护发布。
- 同参数 LKG 保留旧事实；跨参数不会借用。不同 family 继续逐行发布，不是全套 family 单事务；失败保留旧行的既有合同继续适用。
- Desktop 全局排名延迟和既有 bundle 大小尚未优化；阶段 0.5 索引迁移、阶段 2 瘦响应、Search/Billboard 算法及其他持久缓存均未开始。
- 未修改原始播放事实、L2/L3、双轨时长、性能探针或生产环境。工作区为本批次代码、测试、生成类型及必要文档，保留未提交状态。

本轮在阶段 1 实现、定向验证和文档交付后停止。
