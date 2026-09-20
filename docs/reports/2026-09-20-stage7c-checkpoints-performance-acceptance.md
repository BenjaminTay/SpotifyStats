# 阶段 7C：Git 检查点、性能阻塞收口与本地全栈验收（Partial）

## 当前结论

**阶段 7C Partial**。四个已完成阶段的本地检查点提交已保留。Records、Analysis LKG、艺人统计/排名、unavailable、18 项最终故障 UI、四并发及全部标准门禁通过；唯一一次默认完整 fullstack 在 API 基准阶段失败：`/api/import/preflight` hot P95 **5175.24 ms > 500 ms**。四个浏览器阶段均未执行。按本轮停止条件，没有继续修复该接口或重跑整轮。

最小剩余阻塞是 import preflight 的全栈性能门槛，以及该失败后尚未执行的默认浏览器阶段。7C 的新实现与报告保留为未提交改动；不回退四个已完成的本地提交。

## 本地检查点

起点为 `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，初始 274 项状态与 7B 终点逐文件一致。完整归属表、初始 patch、每次 cached patch / name-status / stat / hooks 日志保存在证据目录。共拆为四组；共享 migration、main、job queue、API/消费者和生成类型存在依赖，读模型组统一落地，未为了数量拆成不可构建的中间状态。

| SHA | message | 阶段与范围 |
|---|---|---|
| `8cfb337448eb8b80faaaf941bc85c38c89a46cd5` | perf(infra): 统一性能测量与验证合同 | 阶段 0、7 探针合同、脚本、测试与文档 |
| `8448d2cc316d927c4b1f69dd56d9d41176bc7782` | perf(billboard): 收口公开快照投影与榜单重建 | 阶段 1/2A/4A/4B、7B Home、对应 OpenAPI/TS |
| `60e394a1fc4cd850e20fe5cc291794c04834e379` | perf(search): 共享多变体构建与增量维护 | 阶段 5A/5B/5C、identity no-op、Search 合同 |
| `107594909cab25ce20d87b88522f4ef3c55e1bb6` | perf(read-models): 持久化分析及档案治理读模型 | 0.5/2B/3A–3C/6A–6C/7/7B、migration 74–77/seed、实体与年度 |

全部使用明确路径或可审计的 cached patch，hooks 通过；未 amend、rebase 或 push。组 2 从暂存树生成自己的 OpenAPI 与 TS，并独立通过 tsc 和 27 项定向测试。四组结束时工作区曾完全 clean，当前修改只属于 7C。

提交基线：unit 1914 passed，contract（真实 Online Backup source）437 passed，前端 657 passed / 4 skipped，build、docs audit、diff check 通过。首轮副本 WAL 只读初始化失败、一次误把整个真实副本用于普通 unit 后主动中断，以及 contract 的六条 warning 均保留在原始日志；它们没有被改写为通过记录。

## 性能原始样本

Records 使用三个独立新进程，每次目标 sidecar 不存在：**9.824068583 / 9.512222250 / 10.429251333 秒**，median **9.824068583 秒 ≤10 秒**。第三次超过 10 秒仍保留；门槛作用于 median。三个完整 payload 与当前正确 builder 逐字段相等，仅排除 `meta.generated_at`。本轮没有修改 Records 算法，达到门槛即停止；测量在检查点提交后、revision 迁移前完成。

下表为不带 SQL 观测器的真实 loopback HTTP，新服务进程健康就绪后首个目标请求；不包含启动耗时，不清空操作系统页缓存，不把这三次称为稳定 P95。每次 PID、参数、响应、原始耗时和进程列表均保留。

| 目标 | 三次首读原始值（ms） | 门槛 |
|---|---|---|
| artist-stats | 391.440750000 / 379.677334000 / 376.826666000 | 500 ms，每次通过 |
| artist-rankings | 246.135625000 / 254.198833000 / 248.774000000 | 500 ms，每次通过 |
| stats-lkg | 16.086750000 / 15.997667000 / 15.804083000 | 500 ms，每次通过 |
| stats-config-missing | 8.732834000 / 8.472875000 / 10.696625000 | 300 ms，每次通过 |
| records-config-missing | 10.546625000 / 11.882791000 / 9.556125000 | 300 ms，每次通过 |

艺人读取继续复用已发布 Analysis artist rank context，共享全局排名、Top 250 与最近逻辑事件；本轮未修改艺人统计算法和字段。基础 stats 不自动加载 rank context，缺失/漂移 GET 不补建，相关完整字段和竞赛排名合同由定向测试核验。

## 7C 实现

Analysis source revision 原来逐请求对事实表进行全量读取与 repr 指纹；migration 78 改为持久表级 epoch/counter，由源表 INSERT/DELETE/语义 UPDATE 同事务维护。公开 GET 校验触发器完整 DDL、版本标记、依赖表集合与计数，然后读取版本向量。`PRAGMA data_version` 只作并发提交 fence；文件 device/inode 只作副本命名空间，均不冒充语义 revision。

显示、审计字段、无变化 UPDATE 和未批准的流派/语言记录不使对应事实失效；批准状态转换、真实源值修改、删除均被追踪。触发器丢失、schema 合同改变或计数缺失时拒绝公开读取，由私有 migration/startup 修复并更换 epoch；不在 GET 安装或修复。seed 同步到 78，123 张非跟踪业务表与迁移前相等，integrity_check 为 ok。

exact、LKG、source/config/builder drift、损坏 active、无 LKG、失败不替换 active、事务回滚和并发提交仍按原合同处理；公开 HTTP 另带观测器核验 builder/write/enqueue 均为零；最终定向测试为 72 passed。

## 状态、并发与真实 UI

- 四组同 key 四并发：Records、Community、Archive、Governance 各 **builder_calls=1**。四个调用共用受控 barrier，主机级锁期间无其他本轮测试进程；构建期间公开读取原 LKG，失败未替换 active。原始结果与前后进程列表见 `concurrency.json` 和对应 processes 文件。
- Search config drift 修改隔离副本中的真实默认 `bb_week_start_hour`，候选与 context 均为 **200 + stale / last_known_good statistics**，目标与实际服务的 filter fingerprint 明确不同，不是 422。参数、前后 payload 与零写入观测保留在 `state-final/state7c.json`。
- 对 Home、Stats、Records、Billboard、Search、Community、Archive、Governance、Yearly 注入真实私有 builder 异常，分别检查存在历史发布与空 sidecar。最终 UI 为 8 类 Phone ×2 状态，加桌面 Governance ×2 状态。Yearly 采用严格 exact 发布合同，源漂移即使留有旧产物仍为 404，消费者最终显示“报告加载失败”，没有把它视为 ready 或 LKG。
- Phone Community 的 `Retry` 实际点击，触控区不小于 44×44，再次收到 503 后回到明确错误态；各 Phone 页面 scrollWidth=clientWidth=390。Governance 在桌面真实收合、展开“音乐源数据管理”，再点击“流派与语言”，分别显示上次检查结果及失败提示。
- 所有导航使用 DOMContentLoaded、明确文本/API 或可见控件等待，没有 networkidle。脚本阻断外部连接与写方法，不触发外部服务。截图已核查。

诊断记录没有覆盖：并发脚本的恢复路径被 exec 局部变量覆盖，四组测量已完成，之后单独使用 Online Backup 恢复临时副本；首轮故障注入受恢复后 Governance schema cookie 影响；随后探针恢复旧计数时与此前并发 generation 相撞，Records/Archive 成为 exact，该轮不算漂移通过。最终探针用多次独立源写入推进计数，并先做副本私有 revision 修复。Phone 设置页仅提供“电脑端管理”入口，无法展开桌面治理面板的两条超时保留，桌面补测另存 `governance-final/`。没有重跑已通过的 396 次路由矩阵。

## 最终门禁

| 门禁 | 结果 | 命令墙钟秒数 |
|---|---|---|
| unit | 1916 passed / 1089 deselected | 75.199129 |
| contract | 437 passed / 2568 deselected / 6 warnings | 255.406326 |
| backend-all | 3002 passed / 3 skipped / 8 warnings | 1342.718036 |
| frontend-test | 657 passed / 4 skipped；85 files passed / 1 skipped | 44.885762 |
| frontend-build | Pass | 9.624772 |
| docs | Pass，118 篇当前 Markdown | 0.929322 |
| phase5 | Pass；unit 1914 passed / 2 skipped，contract 437 passed；前端与 build 通过 | 349.473940 |
| diff | Pass | 0.064785 |

命令严格按上述顺序运行；完整 backend 使用 Online Backup source，unit/contract/Phase 5 使用项目默认 seed。完整后端 pytest 自报 1333.07 秒，表中为父命令含退出清理的墙钟耗时。离线环境关闭 `.env` 后，Genius 客户端不可用，触发原有三个条件跳过（两项 unit 文本清理、一项 integration）；这两项 unit 在前面的标准 unit 中已通过。没有修改或放宽用例。

完整后端第一次启动未继承 socket 外网阻断环境，已中断并保留 `final-backend-all.log` 与 `backend-initial-interruption.json`，随后从该阶段继续完整执行；最终日志为 `final-backend-all-offline.log`。warning 涉及 LibreSSL、弃用和测试线程清理/源 fence，均保留，未描述为无 warning。全文件 pre-commit（Ruff/format/mypy/secrets）及新增报告的文件 hooks 均通过。

| 默认完整 fullstack 阶段 | 结果 | duration_ms |
|---|---|---|
| preflight | PASS | 8180 |
| quality | PASS | 69351 |
| backend | PASS | 1117655 |
| api | FAIL | 284243 |
| browser-routes | NOT_RUN | 0 |
| browser-interactions | NOT_RUN | 0 |
| browser-inventory | NOT_RUN | 0 |
| browser-compat | NOT_RUN | 0 |
| optional | NOT_RUN | 0 |

运行 ID：`20260920T123340.940443Z-f146fe5cd6b8`；selection=full，整体 **FAIL**，总耗时 **1479632 ms**，退出码 1。preflight、quality 和完整 backend 通过；该 backend 为 **3002 passed / 3 skipped / 9 warnings，pytest 1107.87 秒**。API smoke 与参数边界通过，基准目录共 51 个目标，唯一慢项为 `/api/import/preflight`。

该接口 22 次均返回 HTTP 200。首个观测请求为 4777.095 ms，进程状态标记 unknown；其后 21 次同进程请求 min 4480.897 ms、median 4763.007 ms、P95 **5175.24 ms**、max 5187.615 ms。阈值保持 500 ms，未降低并发、未放宽用例或 timeout，未增加固定 sleep；未使用 `--only` / `--from`。浏览器阶段因 API 失败未到达，不能声称 Chromium/Firefox/WebKit 本轮默认门禁通过。

所有 22 次原始样本与其余 50 个目标保留在 `fullstack-run/api-benchmark.json`；兼容摘要为 `fullstack-summary.json`，完整 run-scoped 目录已复制到 `fullstack-run/`。只运行了这一轮 fullstack。Docker 不属于本轮门禁。

## Git、数据与证据

最终 HEAD 为 `107594909cab25ce20d87b88522f4ef3c55e1bb6`，相对本地缓存的 origin/main ahead 4 / behind 0；未联网 fetch。最终全栈门禁未通过，因此 7C 实现与报告不满足本轮新增提交条件，全部保留未提交；暂存区为空。

全部真实数据操作限于由 SQLite Online Backup 创建的 `/tmp/spotifystats-stage7c/data/main.db` 及对应临时 sidecar。正式数据 **4183 / 4183 文件 size 与 SHA-256 全部一致**：4172 个应用数据文件、9 个 SQLite 临时文件、2 个 `.DS_Store`；无新增、删除或内容变化。唯一 mtime 变化为 `data/spotify_stats.db-shm`，其大小与 SHA-256 相同，未尝试回写或恢复正式文件。逐文件清单与对账见 `formal-before.json`、`formal-after.json`、`formal-diff.json`。未 push、未部署、未同步正式数据、未执行任何 Docker 操作、未调用 AI/LLM 或 Spotify 等外部服务。

剩余未提交范围共 10 项（9 个已跟踪修改、1 个新增报告），没有无法归属的历史 hunk：

| 路径 | 7C 范围 |
|---|---|
| `backend/core/migrations.py` | migration 78 与注册 |
| `backend/main.py` | 私有启动时安装/修复 Analysis revision |
| `backend/services/analysis_snapshot_revision.py` | 事务触发器、持久版本向量与只读合同检查 |
| `backend/tests/fixtures/seed.db` | seed 同步 schema 78 |
| `backend/tests/unit/test_analysis_snapshots.py` | 语义漂移、rollback、缺损追踪与并发 fence 测试 |
| `docs/reference/analysis-result-snapshots.md` | 当前 revision 合同 |
| `docs/CHANGELOG.md` | 7C 实现与 Partial 状态 |
| `docs/README.md` | 新报告入口 |
| `docs/reports/README.md` | 新报告索引 |
| `docs/reports/2026-09-20-stage7c-checkpoints-performance-acceptance.md` | 本报告 |

README 无需新增入口说明；AGENTS/CLAUDE 仍一致，未修改。全文件 hooks、diff check、status 和 log 已执行，结果保存在对应日志。最终 Git 信息见 `git-final.json`、`git-status-final.txt`、`git-log-final.txt`。本轮创建的 8000 后端与 5173 前端进程已停止；未改变用户的 Docker Desktop 状态。

证据根目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0be86-06d0-7b51-b1ad-8a3f70c1a9ee/spotifystats-stage7c`。主要文件：`baseline.json`、`formal-before.json`、`checkpoint-ownership.md`、`checkpoint-*-cached.patch`、`records-checkpoint-acceptance.json`、`plain-http.json`、`seed-migration-78.json`、`directed-final-tests.log`、`directed-acceptance.json`、`concurrency.json`、`state-final/`、`governance-final/`、`final-gates.json`、`fullstack-summary.json`、`fullstack-run/`、`formal-diff.json`、`git-final.json`。所有原始 payload、日志和临时数据仅保存在本机证据目录，未纳入 Git。
