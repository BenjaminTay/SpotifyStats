# 阶段 6A：Community 冷计算、持久读模型与分页收口

日期：2026-09-20。结论：**本轮 Community 范围 Pass**。读取、构建、资源、分页与只读门槛均通过。完整 contract 仍有两个既有 analysis 测试失败，因此不声明全仓库或本地全栈 Pass。没有 commit、push、部署，也没有开始阶段 6B。

## 1. 环境与证据

起点 HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，工作区已有大量其他任务修改。开始前保存 status、HEAD、全部非忽略文件 SHA。正式主库与 Billboard sidecar 仅用 `mode=ro` + SQLite Online Backup 读取；测试主库含 92,908 条 plays。主库、Community、Billboard、Home、yearly、analysis 和队列均限定在临时副本/pytest fixture。未调用 LLM、OAuth、外部 API，也未发起外网请求；探针禁用 dotenv 并阻断外网 socket，浏览器阻断非 loopback 请求。

原始证据保留在 `/tmp/spotifystats-stage6a`。日志、JSON、探针代码、profile 与截图另存本机持久证据目录：

`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bd2d-bc04-7d22-91d0-6feb12f2e21d/spotifystats-stage6a`

数据库和真实帖子 payload 不进入 Git 或镜像。结果适用于这份真实数据副本与本机环境，不代表生产已发布。性能参数固定为 min_ms=30000、music_only=true、merge_enabled=true、dynamic_threshold=true、merge_level=2、include_compilations=false、TopN=30/20/20、周五 00:00、max_merge_gap_minutes=5、不限年份；没有把此组测量称为所有配置的性能证明。

## 2. 修改前冷路径归因

三个独立新进程的首次 feed（每个随后测 trending、post、第二页、复合筛选）：

| 样本 | wall 秒 | CPU 秒 | 峰值 RSS MiB |
| --- | ---: | ---: | ---: |
| before1 | 42.343 | 41.475 | 909.34 |
| before2 | 42.088 | 41.404 | 1014.28 |
| before3 | 43.238 | 42.601 | 1012.56 |

中位数 **42.343 秒**。before1 的 chart 数据阶段 41.55 秒，主轨 raw 20.293 秒、艺人 raw 20.20 秒，两次完整重建占绝大多数时间；三种 weekly ranking 各一次，约 0.411/0.529/0.095 秒；个人周统计约 0.064 秒。原来覆盖 217 个周标签、2728 条帖子。

五次接口调用累计 collection/cover map 各加载 5 次，封面和模拟 metrics 各处理 **13,640 条帖子**。DataFrame copy 741 次、累计 5,447,231 行。SQL SELECT 105 次、累计返回 290,359 行、计时约 35.85 秒。详细 SQL 分类、各 post type 数、阶段计时见 `before1.json`，完整 profiler 见 `before-profile.prof` / `before-profile.json`（profile 本身使 wall 增至 53.607 秒，不纳入无 profile 中位数）。

独立的 trending 冷读 42.264 秒；post miss 冷读 61.710 秒，说明不存在的 ID 也先构建全历史。存在的详情在同进程后续调用验证。同 key feed/trending/post 并发样本约 75.22–75.26 秒，旧 singleflight 避免重复 core，但不能避免冷等待及每请求全量展示补全。TCP feed/trending 在原 30 秒 timeout 下均 ReadTimeout，失败样本保存在 `before-http.json`。这些诊断场景未混入三个 feed 基准样本。

原直接函数探针保存了 JSON raw bytes；没有 HTTP 编码的调用，其 encoded bytes 明确为 null，不用估算 gzip 冒充实测传输字节。

## 3. 持久模型、失效与发布

实现位置：`backend/domains/community/snapshot_store.py`、`snapshot_revision.py`、`backend/services/community_snapshot_service.py`。详细合同见 [Community 快照规则](../reference/community-snapshots.md)。

- 默认独立 `community_cache.db`；可由 `SPOTIFY_STATS_COMMUNITY_CACHE_PATH` 指定。正式主库不新增 Community 业务表。
- 完整发布身份为 **semantic request key + exact source revision**：key 含数据库 file-lineage namespace、完整 Billboard 参数、builder 与 content policy；revision 对真实播放字段、identity/有效署名、Album Project/L3 membership、聚合配置、收藏求精确摘要。`data_version` 只是摘要失效提示，TTL、mtime、MAX(ts)、行数均不充当 revision。
- account、tag、日期、搜索、post type、significance、highlights 是同代 SQL 投影。改变 Billboard 参数产生独立 key，不借用其他参数的 LKG。
- generations/active/posts/tags/entities 分离，posts 存稳定 ordinal、事实 JSON 和筛选列，实体/标签与 post ID 建索引。模拟 metrics 和封面不持久化。
- staging 行、source/config fence、active/previous 切换和 pruning 在同一事务；失败不切 active。每 key 保留 active/previous 两代；旧代 DELETE 后空闲页复用，不承诺文件立即缩小。
- 使用 rollback journal、只读连接 `mode=ro` + `query_only` + 读事务。初版 WAL 在刚备份的新文件并发初始化时出现只读 I/O 错误，最终改用 DELETE journal 后重新完成并发、冷构建和 exact/LKG HTTP 矩阵。
- 构建期以文件锁及 singleflight 防重复。实际来源或配置在构建中变化会拒绝发布；队列重试重新读取最新目标，默认任务重新解析当前设置。失败耗尽后 private refresh 可再排队。
- 启动、导入/identity/credit/Billboard 任务成功后，以及已提交的设置、元数据和收藏同步写入后维护默认投影。Community 排队异常独立处理；不依赖 analysis 排队成功。收藏同步仅接入既有操作完成后的本地维护钩子，未修改 OAuth 或发起同步。
- 封面/display URL 和管理时间戳不影响核心事实 revision；返回页每次读取当前封面。重复 exact ensure 不重建、不改变已发布文案。

实际单代 SQLite 文件约 **3.94 MiB**，低于 20 MiB 目标。实现还有 20 MiB payload/search 逻辑预算；这不等于通用物理文件硬上限。GET 没有进程内全帖索引（0 MiB）；真实投影探针新增 Python 分配峰值 **1,039,371 bytes**、保留约 62.6 KB，低于 32 MiB 目标。此分配值不是整个 FastAPI 进程 RSS，也不包含 SQLite 的原生页缓存。

## 4. Billboard 复用结论与生成/展示分离

**没有复用已发布 Billboard JSON 成品。** 检查现有 `BillboardBuildContext`、weekly/full_data 等持久 family 后，完整候选排名属于 invocation 内事实，持久成品不能无损提供 Community 所需的全部个人历史与候选输入。不能用普通 TopN 冒充这些输入。

后台复用现有 compact raw loader、预聚合兼容校验及三种 ranking 函数。一次 raw 加载保留次数与独立时长贡献，从同一贡献行派生有效署名/canonical artist 输入，省去第二次完整 loader。真实艺人排名 **4265 行全部字段相等**（`artist-compare.log`）。没有修改 Billboard/Search/Records 的实现。

同一维护 invocation 内共享个人历史、collection、历史 state；生成一次事实文案并持久化。动态阈值、merge_enabled、合并间隔都显式传入兼容校验。旧内部 `generate_all_posts()` 保留导入/调用兼容，未调用内部 AI 工具。

GET 已完全脱离全历史 builder：

| 接口 | 读取方式 | 展示补全 |
| --- | --- | --- |
| feed | SQL 筛选/count 后 LIMIT/OFFSET，只解码返回页 | 返回 50 条只补全 50 条；复合筛选返回 3 条只补全 3 条 |
| trending | entities GROUP BY 与最新 no1/debut 专用投影 | 0 条；不读取全历史帖子 JSON |
| post | 索引定位目标、同日共有实体的其他账号候选，最多四回复 | 目标 + 最终回复；实测目标为 2 条合计 |

`total_all` 保留“其他筛选已应用、未加 highlights 限制”的语义；实体计数平票、latest debut 的既有类型匹配、回复账号去重/次序不变。每请求模拟互动结构与范围沿用原函数，不成为真实互动事实。

## 5. 正确性与 time-capsule

未校正的旧结果 2728 条，新结果 2717 条，**不是无条件宣称与旧缺陷完全相同**：旧结果有 11 条来自最新播放所在开放边缘周（发布时间 2026-08-28），现在依项目完整周规则排除；年度/时代总结相应校正。保留全部已完整结束的 216 周，没有削减有效历史、字段、文案变体或有效帖子来达成性能目标。

`comparison.json` 保存全部删除 ID、23 处 content 差异及 1 处 posted_at 差异，原因包含开放周事实校正和受控随机调用序列变化。对旧 builder 输入相同的完整周 frames、校正时代总结发布时间，并用模块局部 `Random(627)`：**2717 条的 ID、数量、稳定顺序、account、posted_at、content、type、tags、significance、attached_list、linked_entities 全部一致**，见 `corrected-comparison.json`。没有修改全局 RNG。

阶段末汇总现在标记最后完整周结束之后；周边界晚于 12:00 时发布时间也不得早于边界（23:00 单测）。周序 HistoricalState 继续按当周演进。collection 当前摘要仍在生成日发布，既有规则保留；本次真实副本没有生成 collection 帖子，其 revision/漂移由隔离 fixture 覆盖。

`projection-comparison.json` 进一步用保存的旧 API 算法对同一发布事实核对：

- 23 组 feed 过滤（所有实际账号、第二页、末页、复合过滤、日期、中文、大小写、字面 `%_`）、total/total_all、整页事实完全相等。
- 3 组 trending（全量、日期段、无结果）的 artists/tracks/count/latest_no1/latest_debut 完全相等。
- 全部 **2717 个 post ID** 的目标选择与回复 ID/次序一致。
- ready 重复读取内容稳定；metrics 只核对既有范围/结构及补全数量，不要求随机值相等。

## 6. 性能门槛

最终存储方案三个独立新进程、各自缺失 sidecar 的完整后台构建：

| 样本 | wall 秒 | CPU 秒 | 峰值 RSS MiB |
| --- | ---: | ---: | ---: |
| build-delete1 | 22.028 | 21.883 | 688.86 |
| build-delete2 | 21.973 | 21.895 | 686.23 |
| build-delete3 | 21.974 | 21.907 | 690.05 |

中位数 **21.974 秒**，相对修改前降低 **48.10%**（要求 ≥40%）；最高峰值 **690.05 MiB**（要求 ≤768 MiB）。profile 的主 raw 阶段仍约 20.65 秒，是剩余主成本；艺人派生约 0.495 秒，三种 ranking 共约 0.69 秒。collection 一次、构建期封面/metrics 零补全。profile 的 SELECT 148 次/338,425 行/18.107 秒，包含精确 revision 扫描；copy 725 次/4,758,812 行。新 profile 是维护 invocation，旧指标是五接口矩阵，不能把两者 SELECT 总次数直接解释为回退。SQL execute/executemany 的记录范围见探针源代码。

早期慢样本全部保留：初版 28.24 秒但 RSS 907 MiB；compact 三次约 23.42/34.98/34.12 秒；中间方案三次 29.77/34.79/31.65 秒，中位数改善仅 25.2%，当时判为 Partial。最终是在存储并发修复后重新进行独立进程测量，**不把整段 wall 差异全部归因于 journal**，也不删除早期失败来掩盖环境波动。最终去除重复 raw 加载的收益有 profile 支撑。

以下每格均为 **三个独立新服务进程的首次 HTTP 请求**，单位 ms；gzip bytes 来自实际原始响应体，timeout 保持 30 秒：

| 状态 | feed | trending | post | 判定 |
| --- | --- | --- | --- | --- |
| exact/200 | 111.764 / 110.154 / 111.928 | 109.976 / 109.264 / 111.524 | 109.320 / 108.437 / 106.643 | 全部 ≤500 |
| source 改变、LKG/200 | 116.581 / 116.467 / 112.657 | 113.438 / 113.333 / 114.366 | 110.403 / 110.018 / 111.072 | 全部 ≤500 |
| 完全缺失/503 | 14.189 / 5.107 / 5.295 | 5.188 / 4.719 / 6.857 | 5.107 / 4.423 / 5.234 | 全部 ≤300 |

exact feed raw 31,306–31,316 B / encoded 7,227–7,247 B；trending 959/959 B（未压缩）；post 1,645–1,646 B / 795–797 B。LKG 与缺失完整 bytes 见 `performance-summary.json`。

三个独立进程内的第二页后续请求 9.141/10.396/8.547 ms，复合过滤 8.201/3.532/4.800 ms；各自零 builder/写入/排队。它们是进程内后续调用，不冒充首次冷读。早期与回归测试并行的压力诊断曾有 879 ms 冷读，保留 `read-*.json`，未混入最终串行首次 HTTP 门槛矩阵。不报告 warm P95（没有 20 个同状态样本）。

Desktop 三次全新后端进程/浏览器 profile 的 core-ready：**590/537/536 ms**；Phone：**538/543/544 ms**，全部 ≤1.5 秒。使用已有 web-vitals 探针的页面核心就绪规则，不以 DOMContentLoaded 冒充事实渲染完成。

## 7. 并发、恢复与 public 边界

- 真实副本四个同 key ensure：**1 次 builder、1 次 publish、3 次 exact no-op**。构建期间 public 返回旧 active 的 warming/LKG（3.723 ms），完成后 ready；见 `concurrent.json`。
- SQL 触发器注入核心 INSERT 故障，旧 active 保留；source/config/identity/collection 漂移拒绝旧发布，下一 ensure 恢复；active/previous pruning、失败 LKG、重复 ensure 内容稳定均有测试。
- 展示补全失败返回明确错误，已发布核心与 trending 保持可读。失败任务可重新入队；默认 handler 读取最新配置。共享 JobQueue 的重试测试在完整 unit 中覆盖。
- public exact/LKG/missing 探针 builder=0、enqueue=0、SQLite authorizer 写入=0。新建独立只读检查目录，读前/读后都只有同 SHA 的 `community.db`，未创建 WAL/SHM/journal/lock。HTTP 矩阵主库与 Community 持久文件 SHA 也不变。
- public miss 不先计算 revision、不创建目录；不兼容 key 明确 unavailable。private GET 同样不构建，维护仅由后台或 private refresh 触发。

## 8. 页面与回归

真实 Chromium 在 Desktop/Phone 验证主页、account、post、账号/实体深链、Taylor 搜索与 2025 日期筛选、真实滚动第二页（两页 ID 无重复）、ready/LKG/unavailable。Phone 无横向溢出，筛选抽屉可打开关闭。unavailable 用真实后端不兼容参数制造，不用空数组或模拟 payload，主页/account/post 均显示“当前筛选的数据尚未发布”；账号头部仍保留既有计数占位，不将其当作成功空结果。截图和可见文本保留在证据目录。

settings-ready、Query key、signal 继续沿用；共享 SnapshotStatusNotice 新增 infinite pages 与 failed-LKG 消费。前端测试覆盖迟到筛选/账号/分页响应隔离与状态展示。

| 检查 | 结果 |
| --- | --- |
| Community + public/snapshot 定向 unit/contract/integration | 62 passed |
| 完整 backend unit | 1851 passed，1088 deselected（`unit-last.log`） |
| 完整 contract | 435 passed，2 failed，2502 deselected（`contract-last.log`） |
| Community 前端定向 | 36 passed |
| 完整 frontend test | 650 passed，4 skipped（83 文件通过、1 文件跳过） |
| production build | 通过（保留既有大 chunk 提示） |
| Ruff / Python compile / ESLint | 通过 |
| docs audit / git diff --check | 通过（112 份当前文档） |

两个 contract 失败是 `test_api_boundary_probe` 与 `test_safe_readonly_api_smoke_probe`；失败路径仅为 `/api/analysis/stats`、`/api/analysis/records` 的既有 503，**没有 Community 新增失败**。初轮这两个测试还包含未预发布 Community 的 503，已为测试增加隔离预发布 fixture 后全量重跑确认。保留三个 warning，包括既有 LibreSSL 兼容提示与测试结束后 AI task 后台线程的临时库 I/O 异常；未触发模型或修改 AI 模块。

## 9. 数据、工作区与下一步

`formal-audit.json` 对开始前记录的 **4178 个正式持久文件**核对 SHA/size/清单，全部相同，无新增/删除。SQLite `-shm` 是瞬时共享内存文件，最初基线就排除，不能据此声称其字节也不变；正式主库、WAL、现有 sidecar 和 data/cache 均在核对范围。

`scope-audit.json` 记录相对起点的精确改动清单。改动限于 Community、必要配置/队列/已提交写操作钩子、共享状态提示、Community OpenAPI 契约、测试及文档；原有范围外 dirty 文件保持 SHA。AGENTS/CLAUDE 保持一致，HEAD 不变。未执行 git add/commit/push 或生产部署。

下一步可进入 **阶段 6B Archive**；本轮指定 Community 门槛没有剩余阻塞。更大数据量的 revision 扫描成本、更多配置的性能矩阵和多 key 文件总量仍是使用边界，不把本机样本外推成无限规模保证。本报告完成后停止，不启动阶段 6B。
