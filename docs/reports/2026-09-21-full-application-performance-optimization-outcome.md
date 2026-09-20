# 全应用性能优化成果与最终验收报告

> 日期：2026-09-21
>
> 基线：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`
>
> 最终本地检查点：`170d944037d7d10663a38cc82efefc2a6f241ff9`
>
> 结论：原审计确定的阶段 0～7 路线已经完成，阶段 7E 默认完整全栈验收 PASS。本报告只代表本地实现与隔离真实数据副本验收；尚未 push、部署或进行生产验收。

## 执行摘要

这轮工作不是简单地给几个接口增加内存缓存，而是将应用的昂贵计算从“页面 GET 即时全量计算”重新组织为“后台构建、精确 revision、持久发布、只读消费、同语义 LKG、失败保留旧代”。同时减少了前端重复请求和超大响应，补齐了独立进程、资源、浏览器及正式数据保护的测量合同。

关键结果：

- Billboard 默认全套重建在配对样本中由 73.115 秒降至 33.142 秒，下降 54.7%；配置失配路径最终为 19.422 秒、最大 RSS 681.64 MiB。
- Search 四变体配置重建由 130.982 秒降至 30.983 秒，下降 76.35%，最大 RSS 由 1878.39 MiB 降至 617.25 MiB；真实增量同周和跨周分别比 shared-full 少 90.81% 和 79.04% 的 wall time。
- Analysis Stats 独立进程读取由约 7～8 秒降至约 0.35 秒；Records 从 30 秒超时变为持久快照读取，最终冷构建中位数达到 9.824 秒。
- Community 冷构建下降 48.10%，Archive 三个重型章节联合冷建下降 66.6%，Genre/Language 治理联合构建下降 98.02%。
- Billboard 四个页面的核心 API raw payload 分别减少约 91%～99%。详情页、Community 和播放分析的非首屏请求改为按视口或交互触发。
- Import Preflight 在完整门禁中的 hot P95 从失败时的 5175.24 ms 降至最终 64.329 ms。
- 最终完整门禁：后端 3036 passed / 3 skipped，前端 659 passed / 4 skipped，51 个 API 目标 slow_count=0，Chromium、Firefox、WebKit 全部通过。
- 正式 `data/` 前后 4183 个文件无新增、删除、内容、大小或 mtime 变化；没有调用生产 AI/LLM、外部服务或 Docker，也没有 push、部署。

## 规划从哪里来

这轮没有使用仓库内某个 `docs/plans/...` 文件作为唯一总规划。总规划来自 Codex 任务“SpotifyStats全应用性能优化-本聊天已收口”中的只读审计，主要规划产物为本机证据文件：

`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-performance-audit/审计报告.md`

该文件标题为《SpotifyStats 全应用性能审计与优化规划》，基于 `faa5e4e4` 对实际可达页面、前端 GET、后端 builder/cache、Billboard/Search 重建、导入维护和现有探针进行只读审计。它交付了：

- 页面 → API → builder/cache 的消费矩阵；
- cold/warm/exact/LKG/missing/rebuilding/concurrency 的测量边界；
- P0/P1/P2 瓶颈；
- C1～C8“空间换时间”候选及 key、revision、失效和 LKG 设计；
- 阶段 0、0.5、1～7 的实施路线、风险、回滚方式与验收指标；
- 已经存在且不得重复实施的能力清单。

这里必须区分“候选”和“承诺”：C1～C8 是设计候选，不要求全部照单实现。实际执行采用每阶段先测量、达到门槛即停止的方式；没有必要的全局事实层、Redis、通用 HTTP 缓存、永久保存所有筛选组合和 Billboard 持久 checkpoint 都没有加入。阶段执行证据则逐步写入本目录的阶段报告，最终由[阶段 7E 验收](2026-09-21-stage7e-final-fullstack-acceptance.md)收口。

## 我们如何完成这轮规划

1. 先建立统一测量合同，区分进程首次读取、持久 exact、同进程 warm、LKG、完全缺失和真实重建，保留所有原始样本与失败。
2. 所有重型测量使用 92,908 条播放的 SQLite Online Backup；主库、Billboard、Home、Yearly、Analysis 等路径全部重定向到临时目录。
3. 每个阶段只处理一个范围，先 profile，再作最小修改，然后执行完整字段/顺序对账、资源测量、并发、失败恢复、public-readonly 和 Desktop/Phone 验证。
4. 局部不达标就标记 Partial，不降低阈值、不增加固定等待、不删慢样本；发现真实边界后拆出 3B/3C、4B、5B/5C、7B～7E 继续收口。
5. 完成大阶段后整理为 7 个本地检查点，最后只运行一次新的默认完整 fullstack，达到 PASS 后停止。

## 实施阶段与主要改变

| 阶段 | 主要问题 | 实际改变 | 最终状态 |
|---|---|---|---|
| 0 | 旧探针把首请求误称 cold、错误页可能被算 ready、资源只看单点 | 统一六个性能/全栈工具、机器 schema、原始样本、核心 DOM/API 终态、完整操作窗口 RSS/CPU | 测量合同完成 |
| 0.5 | 旧数据库 partial index 与当前 JOIN 语义不一致，出现逐行扫描 | migration 74 原子修复 fallback 唯一索引；补齐测试派生路径隔离并重新生成受影响 Billboard sidecar | 索引与安全边界收口 |
| 1 | public GET 仍可能触发冷建；实际 album-project 页面不在公开 allowlist | 放行所需只读项目 API；Billboard/Home 改为 exact/LKG/unavailable，只读 GET 不构建、不排队、不写入 | public-readonly 收口 |
| 2A | Billboard 页面下载完整 4～8 MB payload | 为 Weekly、Records、All-Time、Number Ones 增加已发布快照投影，并切换前端消费 | 页面响应显著瘦身 |
| 2B | Community 在 settings ready 前重复请求；详情非首屏数据提前加载 | Community 请求只发一轮；排名、排行、Recent plays、日期按视口/交互加载；统一 Query key | 请求瀑布与首屏负载收口 |
| 3A | Stats/Records 重启后仍即时全量计算 | 新增 Analysis SQLite sidecar、精确 revision、active/previous、后台维护、只读 GET 和 unavailable 状态 | 默认结果持久化 |
| 3B/3C | Records builder 重复 SQL、日期转换、时长切片和 longevity 事实 | 批量查询、共享小时切片几何、按实体准备不可变事实、单次 builder 共享 | 最终冷建中位数进入 10 秒门槛 |
| 4A/4B | Billboard 一个 generation 内重复加载、排名、Records、年榜和宽帧占用 | invocation-local `BillboardBuildContext`；共享完整排名/summary/power/Records/Year-End 输入；raw fallback 只复制必要列并及时释放 | 默认和配置失配均收口 |
| 5A | Search L2/L3 × dynamic/fixed 四变体分别全量构建 | 每个阈值共享主轨/artist 事实；四变体整组原子发布；Year-End 复用 ledger；exact-ready 快速复用 | full fallback 收口 |
| 5B/5C | shared-full 丢 duration-only、Power 排名不稳定、真实 delta 被无效 identity revision 阻断 | 统一完整统计合同；Album Project 稳定身份；修复 no-op revision churn；候选 generation 内容相同时复用；真实同周/跨周 delta 通过 | Search 阶段 Pass |
| 6A | Community 每次 GET 构建全历史帖子并全量补全 | Community 持久读模型；后台整代发布；GET 先 SQL 筛选分页，再只补全返回集合 | Community Pass |
| 6B | Archive 三个章节分别重建同一批有效事件 | `ArchiveEventFacts` 共享一次事件事实；六章持久发布；分域 revision、exact/LKG/unavailable | Archive Pass |
| 6C | Genre/Language/Import health 页面即时扫描与重复主艺人时长计算 | 共享紧凑 `primary_artist_ms`；五类治理结果持久发布；设置面板按展开加载 | Governance Pass |
| 7～7E | 全路由门禁暴露 Home key、Analysis revision、Import Preflight 和测试磁盘放大 | 稳定 Home key；Analysis 持久语义版本向量；Import staging/preflight 复用；seed/integration 分层；统一 basetemp 与 2 GiB/12 GiB storage guard | 默认完整 fullstack PASS |

## 量化优化成果

### 数据库扫描和读取

| 项目 | 优化前 | 优化后 | 变化 |
|---|---:|---:|---:|
| 主轨身份 SQL 中位数 | 19.416 s | 0.755 s | -96.11% |
| 艺人身份 SQL 中位数 | 19.079 s | 0.627 s | -96.71% |
| Billboard raw loader 中位数 | 37.366 s | 4.300 s | -88.49% |
| Analysis Stats 首次计算中位数 | 40.024 s | 10.360 s | -74.12% |
| Analysis Stats 持久 exact 独立进程 | 7.0～8.2 s | 0.348～0.365 s | 从即时计算改为持久读取 |
| Analysis Records 独立进程 | 30 s 超时 | 0.418～0.597 s | 从超时改为持久读取 |

### 前端与响应体

| 页面核心 API raw payload | 优化前 | 优化后 | 降幅 |
|---|---:|---:|---:|
| Billboard Records | 7.747 MB | 0.340 MB | 95.6% |
| Billboard Weekly | 4.655 MB | 0.027 MB | 99.4% |
| Billboard All-Time（track 首屏） | 6.762 MB | 0.600 MB | 91.1% |
| Billboard Number Ones | 6.762 MB | 0.216 MB | 96.8% |

阶段 2B 的 14 个 Desktop/Phone 主样本中，Community 初始 API 由 6 个降为 4 个，歌曲/艺人详情由 7～8 个降为 4 个，专辑详情由 10 个降为 5 个；排名、完整排行、Recent plays 和日期不再作为非首屏请求提前加载。Community 的 settings 前重复 feed/trending/post 被消除。

### 后台重建与持久读模型

| 重型任务 | 优化前 | 优化后 | 结果 |
|---|---:|---:|---|
| Records 冷 builder | 早期 25.9～35.8 s | 最终 median 9.824 s | 达到 ≤10 s 门槛 |
| Billboard 默认全套重建（配对样本） | median 73.115 s | median 33.142 s | -54.7%；最大 RSS 397.45 MiB |
| Billboard 13:00 配置失配 | 4A 当前代码 RSS 1102.00 MiB | median 19.422 s；RSS 681.64 MiB | RSS -38.1%；时间与内存均达标 |
| Search 四变体配置重建 | median 130.982 s；RSS 1878.39 MiB | median 30.983 s；RSS 617.25 MiB | -76.35%；内存进入 768 MiB 门槛 |
| Search shared-full | median 61.266 s；RSS 最大 1625.11 MiB | median 48.750 s；RSS 最大 649.27 MiB | 时间 -20.4%，主要完成合同与内存收口 |
| Search 同周 delta | shared-full 42.676 s | delta 3.922 s | -90.81% |
| Search 跨周 delta | shared-full 37.588 s | delta 7.879 s | -79.04% |
| Community 冷构建 | median 42.343 s | median 21.974 s | -48.10%；RSS 690.05 MiB |
| Archive 三个重型章节联合构建 | median 55.820 s | median 18.645 s | -66.6%；六章发布 19.895 s |
| Genre + Language 联合构建 | median 34.525 s；RSS 584.41 MiB | median 0.683 s；RSS 189.84 MiB | -98.02% |
| Import Preflight hot P95 | 5175.24 ms（7C 阻塞） | 64.329 ms（最终门禁） | 通过 500 ms 门槛 |

不同阶段的基线、机器竞争和 instrumentation 不完全相同；表中只使用各阶段报告认可的配对或最终验收数字，不把单次历史 profile 当成生产 SLA。

## 正确性和运行边界

- Billboard 六配置共 72 个完整 payload、3954 个页面投影逐字段和顺序一致；4B 另对 48 个完整 payload及 2660 个页面响应/投影完成对账。
- Search 四变体保留次数/时长双轨、L2/L3、Album Project、artist credit、Power 排名和 Year-End；真实同周/跨周 delta 与 corrected full 全字段、全顺序一致。
- Analysis、Archive、Community、Governance 均使用精确 key/revision、active/previous、source fence、失败不替换 active；GET 不同步冷建。
- ready、warming/LKG、failed、unavailable 明确区分，不用空数组或虚假 0 掩盖未发布结果。
- Phone 与 Desktop 保持互斥 presentation；最终三浏览器验证真实路由、交互、后退/前进、移动筛选、44px 主要触控区和无横向溢出。
- 生产端 AI 不在本轮范围：没有调用 LLM、OAuth、Spotify 或其他外部服务，也没有更改生产 AI 配置。

## 最终验收

唯一一次新的默认完整 fullstack run：`20260920T160333.344990Z-20a995560f64`，总耗时 1,317,354 ms，八个必需阶段全部 PASS：

| 门禁 | 最终结果 |
|---|---|
| backend collection | 3039 = seed 2852 + integration 187；无遗漏、重复或交集 |
| backend execution | 3036 passed / 3 skipped |
| frontend | 659 passed / 4 skipped；production build 通过 |
| API | 51 个目标，slow_count=0；Import Preflight hot P95 64.329 ms |
| browser | routes、interactions、inventory、compat 全部 PASS |
| engines | Chromium、Firefox、WebKit 全部 PASS |
| formal data | 4183 → 4183；新增/删除/size/SHA-256/mtime 改变均为 0 |
| test storage | 峰值 626.924 MiB；最低可用 121.738 GiB；退出清理成功 |

测试存储也完成结构性修复：旧 Analysis 参数测试会把约 424 MiB 真实数据库按 case 复制，估算单轮约 12.0 GiB、两轮约 24.4 GiB；现在普通 unit/contract 使用 tracked seed，真实 integration 显式 opt-in，整个 integration 进程只创建一个 session 文件副本。storage guard 对 run-owned 临时目录设置 2 GiB 占用和 12 GiB 可用空间边界。

`optional` 阶段为 NOT_RUN，因为本轮没有请求发布前 Docker/部署验证；这不是本地全栈缺口。完整证据见[阶段 7E 报告](2026-09-21-stage7e-final-fullstack-acceptance.md)。

## Git 检查点

本轮从 `faa5e4e4` 到 `170d944` 共 7 个本地提交：

| SHA | 内容 |
|---|---|
| `8cfb337` | 统一性能测量与验证合同 |
| `8448d2c` | public 快照、Billboard 页面投影与重建 |
| `60e394a` | Search 多变体共享构建与增量维护 |
| `1075949` | Analysis、Community、Archive、Governance 持久读模型 |
| `410d0b9` | Analysis 持久语义版本向量 |
| `53dbf90` | Import Preflight staging 与结果复用 |
| `170d944` | 最终浏览器合同、测试数据分层与存储保护 |

截至本报告编写前，工作区 clean，本地 `main` 相对缓存的 `origin/main` ahead 7 / behind 0。以上提交尚未 push、部署或做生产验收。

## 最终判断

这轮规划已经完成，可以开始新的功能或性能问题。这里的“完成”表示：原审计确定的阶段路线已经实施到最终本地全栈 PASS，并非声称应用未来不会出现新的慢路径，也不表示所有候选缓存设计都已实现。

如果准备发布，应另开发布前任务，重新核对远端状态、提交范围、三种部署模式、Online Backup、健康检查和回滚门禁；push、deploy 与生产验收必须继续分开授权。
