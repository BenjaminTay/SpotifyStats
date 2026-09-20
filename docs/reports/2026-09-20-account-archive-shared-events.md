# 阶段 6B：音乐档案共享事件事实与持久结果

日期：2026-09-20。范围：六个音乐档案章节、相关私有维护、状态展示和验证；不含 Community 6A、library 分页改造、Analysis 修复或阶段 6C。

## 结论

结论：**6B Pass（本地范围）**。性能、正确性、只读边界和浏览器门槛均已满足。最终全量测试及文档门禁记录见下文；该结论只代表本地实现与隔离副本验收，不代表正式数据库已迁移或生产已发布。

## 已实现

- `ArchiveEventFacts` 为 cohorts、returns、discovery 在同一次维护调用内共享原有效事件构建，只保留 track/time 事实、分组时间序列及收藏实体。原 SQL、连续合并、有效播放过滤和时间语义保留。overview/journey 不加载全量事件，other-media 保持独立媒体边界。
- 六个 GET 改读压缩 SQLite sidecar。请求身份含数据库 namespace、规范化筛选指纹、family、builder/publication 版本；精确 revision 参与结果身份。active 与 previous 在同一事务内切换、校验 source/config fence 和剪枝，损坏 active 可读 previous，显式重建修复损坏内容。
- 迁移 75 安装写事务内维护的分域 counter。无变化 UPDATE 和回滚不递增；schema marker/counter 缺失 fail closed，显式修复开启新 epoch，不使用 revision 0。GET 只读小型 revision 表，不再扫描 plays 或 track groups。
- 私有启动/导入完成/本地收藏同步/设置及元数据提交后维护默认配置；任务执行时读取最新参数与 revision。singleflight 加跨进程文件锁，在锁内复查 exact。显式入口为 `scripts/rebuild_account_archive.py`。
- TanStack Query 保留原 queryKeys 和进入视口后加载；请求携带 AbortSignal。保留 Desktop/Compact/Phone 路由分流，缺失和失败给出本地重建说明与“重新读取”，LKG 显示旧事实及轻量提示。修复状态页按钮颜色变量的继承，不改变正常档案布局。

详细失效、统计和本地补建合同见 [音乐档案统计规则](../reference/account-archive-statistics.md)。收藏库查询与分页保持原实现。

## 测量环境与真实性

在 92,908 条 plays 的 Online Backup 副本上测量；正式 `data/` 的 4,178 个持久文件在阶段前后按大小和 SHA-256 核验，无变化、无新增（SQLite 瞬态 `-shm` 不纳入内容比较）。所有测试路径在 `/tmp/spotifystats-stage6b`，外部网络由探针禁用；HTTP 只允许 loopback，页面外部请求被阻止。没有访问 Spotify 或调用 LLM。

旧版基线保留阶段开始时的源码：三个新进程分别轮换 cohorts、returns、discovery 作为首个重型调用，每个进程完整调用六个章节；基线时间是 API 所用 service/context 的调用边界，不包含 HTTP 传输。SQL 记录同时计入 execute 与 fetchall，保留查询、次数、取回行数及耗时。未将已有 TTL 命中当成 cold。

补充的旧版真实 public HTTP 测量使用冻结的六章模块和旧 account router、独立副本及每接口新进程：cohorts 37.665 秒、returns 27.334 秒、discovery 25.447 秒，gzip 传输分别为 2,973 / 1,968 / 1,216 bytes（`baseline-http.json`）。该补充观测包含完整 middleware/只读边界，且与部分回归验证时间重叠，不混入下表 service 构建边界的改善率计算。

新版三个冷构建样本分别来自新进程、新 sidecar。读取性能通过真实 FastAPI HTTP、public-readonly surface、gzip 响应测量；每个重型接口每种状态启动三个独立进程，轻型接口各一个；每个 family/state 另有 20 次 warm 样本。HTTP 首次计时从 ready server 的第一个目标请求开始，不包含解释器与服务器启动。

原始证据目录（本机、Git 之外）：

`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bd2d-bc04-7d22-91d0-6feb12f2e21d/spotifystats-stage6b`

## 性能前后对比

| 项目 | 优化前 | 优化后 |
|---|---:|---:|
| 三章联合冷建三次，秒 | 56.431 / 55.099 / 55.820 | 18.521 / 19.453 / 18.645 |
| 三章中位数，秒 | 55.820 | 18.645（改善 66.6%） |
| 全六章构建并发布中位数，秒 | — | 19.895（即使与旧三章比较仍改善 64.4%） |
| 每次联合有效事件构建 | 3 | 1 |
| 新版三个冷构建最大 RSS | — | 320.77 MiB |
| 四并发失效维护 | — | 1 次事件、各相关 family 1 次构建，其他三调用 exact no-op |
| 六章 active + 已有 previous 的实际 DB | 无持久结果 | 45,056 bytes（44 KiB） |

旧版各自作为新进程第一章：cohorts 19.207 秒、returns 18.225 秒、discovery 18.285 秒。旧首轮 cohorts 48 个 SELECT，取回 93,712 行，SQL execute/fetchall 累计 18.504 秒；有效事件自身 18.371 秒。主要成本仍是原播放加载 SQL，不是三个章节末端汇总；本阶段通过共享避免重复两遍，未扩展为 SQL 算法改写。

| 重型 API | exact 首次最大 ms | LKG 首次最大 ms | 缺失首次最大 ms | exact warm P95 ms | LKG warm P95 ms |
|---|---:|---:|---:|---:|---:|
| collection-cohorts | 9.25 | 8.95 | 5.08 | 4.07 | 4.32 |
| returns | 8.52 | 9.34 | 3.06 | 4.20 | 4.11 |
| discovery | 9.77 | 9.00 | 3.34 | 8.35 | 4.32 |

每个 P95 使用该 family 的 20 个 warm 请求按 nearest-rank 计算。六章完整数值和真实 gzip 传输字节保存在 `http-exact.json`、`http-lkg.json`、`http-missing.json` 及 `summary.json`。LKG 来自隔离源真实 ms_played 变化后的旧发布结果，不是伪造前端响应。失效四并发耗时 19.649 秒、RSS 312.86 MiB，期间 GET 仍读取 LKG。

`concurrent.json` 保留 active/previous generation 和各压缩 payload 大小；总计十个有效 generation（四个失效 family 有 previous，两个未变 family 只有首次 active）。SQLite 为 DELETE journal，静止时无 WAL/journal 伴随文件；文件锁不含事实。不是用压缩 JSON 大小代替实际文件占用。发布 guard 按分配页限制整个 sidecar ≤30 MiB。

## 正确性与边界证明

`correctness.json` 记录 17 个场景 × 六个 family，共 102 组对阶段开始时冻结的旧 builder 的完整字典相等比较，包含列表顺序、日期、空值、计数、时长、分群和版本字段的 SHA-256。双方注入相同的新 revision/context，避免把有意更换的 opaque revision 编码误认作统计变动；不忽略任何业务字段。原有效事件 loader 未改。

场景包括真实 Online Backup 默认配置、合并开关、支持的 L2/L3、min_ms=0、固定 150 秒阈值、动态默认阈值、1/60 分钟合并间隔、连续同曲、上海跨日、无法关联的收藏 identity/缺失 group、收藏日期变化、仅搜索变化、仅 group 及 membership 变化、空收藏、空搜索、无播放。Archive 的现有参数模型只接受 merge_level 2/3，本阶段没有扩展为 L1。

新增单测进一步覆盖：

- search 只失效 discovery；collection 失效五章但不失效 other-media；group 只失效三个关系章节。
- 同值更新、回滚、缺失 trigger/schema marker 修复；revision 不静默使用 0。
- 构建时源漂移拒绝发布；SQL 失败与大小超限保留 LKG 并标记 failed；没有 LKG 的失败返回明确 503。
- previous 回退、损坏 active 修复、多次发布最多两代、四并发去重。
- public guard、SQLite authorizer、builder/enqueue spy：六章读取为零 builder、零写入、零 enqueue；缺失 sidecar 不创建目录或文件。`public-boundaries.json` 含实际命中的 SQL，未出现源 plays/group 扫描。

`migration.json` 证明隔离副本完整迁移至 75 后，plays/tracks/track_artists 内容哈希不变，重复迁移 revision 不变。`cli-exact.log` 证明单独新进程运行 rebuild CLI 复用精确结果，返回 `published=[] / event_builds=0`。

## 浏览器证据

Production build + 本机 preview + 隔离 FastAPI；Playwright 真实浏览器使用 Desktop 1440×1000、Phone 390×844。`browser-ready.json`、`browser-states.json`、`browser-failed.json` 及对应 PNG 保存请求和状态证据。

- `/account` 首屏展示真实 800 首收藏、250 张专辑、59 位艺人、27 个歌单。首屏没有同时请求三个重型章节；近视口的章节按既有预取距离加载，滚动后补齐章节。
- Desktop 仅挂载 desktop DOM，Phone 仅挂载 phone DOM；两者首屏、滚动和错误状态均无横向溢出，无 pageerror。
- LKG 保留与 ready 相同的收藏事实；构建失败保留旧事实，页面显示失败提示；无快照展示重建说明与可见重试按钮，不展示“档案柜还是空的”，不无限 loading。
- 未恢复旧 account/profile 路由、旧人格功能，未加入新 OAuth/AI 请求。

## 最终门禁

- Archive 定向：19 个新增快照专项测试通过；此前六章相关定向 54 项通过，新增后全量 unit 覆盖。
- 后端 unit：1870 passed。
- 后端 contract：435 passed / 2 failed；阶段前 `baseline-contract.log` 已复现同两个 Analysis 503 测试失败，最终失败项与基线完全一致，无新增失败。
- 前端：653 passed / 4 skipped；生产 build 通过（保留既有大 chunk 提示）。状态页 CSS 修复后重新 build 并浏览器复验。
- Ruff：通过。docs audit（113 份当前 Markdown）与 diff check：通过。

全量 contract 的两个测试为 `test_api_boundary_probe` 与 `test_safe_readonly_api_smoke_probe`，涉及 `/api/analysis/stats` 和 `/api/analysis/records` 的未发布 503。没有修改 Analysis 实现或掩盖既有失败，不能将完整 contract 称为全绿。

## 依赖、边界与 Git

无外部服务依赖。正式数据库未迁移、未重建；以后实际使用新版本需通过私有启动维护或明确本地 rebuild 发布所需配置。未发布的非默认筛选需要显式补建。源关联 SQL 单次仍约 18 秒，属于冷维护成本；公开读取不承担它。

HEAD 保持 `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`。共享 worktree 开始即包含其他阶段修改；本轮只修改 Archive 及必要注册、迁移、契约、测试与文档，没有覆盖 Community 源码。未执行 git add、commit、push、部署、正式数据同步或外部入口调整。6B 完成后停止，不开始 6C。
