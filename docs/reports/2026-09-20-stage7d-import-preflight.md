# 阶段 7D：Import Preflight 复用与最终本地全栈验收（Partial）

> 历史时间点报告。2026-09-21 后续状态：Import 优化已独立提交为 `53dbf90e1af781c79a846ab6eb50c2426e8c4dca`；默认完整门禁已由[阶段 7E](2026-09-21-stage7e-final-fullstack-acceptance.md)通过。下文保留阶段 7D 当时的 Partial、未提交状态和原始样本，不追改历史结果。

## 结论

阶段 7D Partial。默认完整 fullstack 在首个失败阶段停止，未重跑整轮。

**唯一最小剩余阻塞：移动筛选交互的 Analysis stats 503。** `mobile-section-sheet` 请求 `period=custom&start_date=2025-01-01&end_date=2025-12-31`，`mobile-time-filter` 请求 `period=last_4_weeks`，均在 `/api/analysis/stats` 返回 HTTP 503，触发控制台错误断言。未继续排查或修复该范围；后续 browser-inventory / browser-compat 未执行。

阶段 7C Analysis revision 已独立提交为 `410d0b971dfdd8bd9efb750030a4dfeaf7f8a63b`（`perf(analysis): 持久化快照语义版本向量`）。提交前指定 10 项完全匹配，54 项 Analysis/migration 定向测试、docs audit、diff/cached 检查和提交 hooks 全部通过。README 不需改动，AGENTS/CLAUDE 保持一致。

Import 修改尚未提交；7C 已完成提交保留。

## 隔离 profile

复用阶段 7C 的 SQLite Online Backup `/tmp/spotifystats-stage7c/data/main.db` 与完整正式源文件的只读读取。13 个串流文件共 **72,550,071 bytes**，流式解码 **92,975 条原始记录**、去重后输入 **92,908 条**，现有 plays **92,908 条**；9 个账号报告文件共 **795,610 bytes**，另校验 UserAttributes 身份。没有替换为小 fixture、删减文件或响应字段。

当前真实副本的指纹基线为 `missing`，比较状态为 `baseline_missing`；`_load_existing_baseline()` 真实走缺失基线返回，并未装载 9.3 万条完整可比较指纹。没有为性能测量伪造 ready 或补写基线。

| 阶段（ms） | 样本 1 | 样本 2 | 样本 3 |
|---|---:|---:|---:|
| enumerate_stat | 0.284625 | 0.177084 | 0.181042 |
| staging_sqlite_write | 136.852296 | 135.893707 | 136.490257 |
| sha256 | 27.578249 | 28.472002 | 28.598999 |
| json_parse | 1691.233937 | 1686.780081 | 1697.593644 |
| _load_existing_baseline | 7.544125 | 7.720458 | 7.660000 |
| dataset_digest | 379.503042 | 385.782375 | 361.688375 |
| build_import_plan | 492.120541 | 479.291333 | 473.564375 |
| _affected_scope | 56.783292 | 41.090500 | 40.847000 |
| preflight_total | 3947.518000 | 3853.911583 | 3858.194334 |
| response_model_serialization | 0.140667 | 0.112833 | 0.108583 |

JSON 时间只累计生成器推进；SQLite 只写计时包含 DDL/INSERT/UPDATE/commit。dataset_digest 在 build_import_plan 内部，计时有嵌套，不能相加当总耗时。原始先行 profile 保存在 `profile.json`（SQLite 计时包含读写），之后为准确拆出写入成本补测 `profile-write-only.json`；原样本和完整 payload 均未覆盖。

## 真实 HTTP 性能与逐字段等价

三个独立新服务进程冷读（不含启动时间、不清 OS 页缓存），全部 HTTP 200：

4018.563500 ms / 4043.788916 ms / 4062.242916 ms

第一个进程的 21 个 hot 原始值（ms）：

58.504417, 58.708125, 59.718583, 58.456333, 58.446917, 58.309334, 58.218292, 58.223417, 59.352459, 59.747291, 58.891000, 58.379125, 58.093917, 58.076417, 58.356333, 58.090584, 58.050042, 58.298125, 58.219458, 58.363208, 59.009917

hot median **58.363208 ms**，nearest-rank P95 **59.718583 ms ≤500 ms**。24 个响应全部 200，cold/hot 与优化前完整响应逐字段相等，包含 blockers、warnings、文件与重复/overlap、relation、mode、全部记录计数、影响周/年、strategy、comparison status 和 confirmation token。原始 HTTP 数据见 `performance-raw.json`、`performance-summary.json`、24 个 `performance-payload-*.json`。

## 缓存、失效、并发与执行合同

- 复用现有 staging 缓存，最多 3 份、15 分钟；报告、只读数据库观察连接、staging 校验摘要与临时目录共用生命周期。淘汰/过期/退出关闭连接并删除目录，POST 取用时转移所有权并取消过期计时器，导入结束负责关闭。没有新增通用缓存框架。
- key 包含 auto/append/replace、builder/contract 与 fingerprint version、streaming/account 绝对路径、每个相关文件存在性/size/mtime/SHA-256、数据库路径和实例身份、active generation/account identity/fingerprint version/dataset digest/record count。三个 mode 即使 confirmation token 相同仍保存独立报告。
- 每个 GET 校验源文件完整 SHA-256，检测新增/删除、大小/mtime/内容改变，也检测同 size 且还原 mtime 的修改；账号报告文件与 UserAttributes 同样进入校验。数据库观察连接的 data_version 对所有已提交更改保守失效，覆盖没有更新活动状态的事实修改及设置变化；它不是持久语义 revision。
- 同一 staging 生命周期锁串行化验证和冷构建，四个同 key 并发只完整构建一次。命中返回深拷贝，不共享可变 payload；冷构建前后复核源与数据库栅栏，不发布混合状态。显式传入事务连接的内部调用仍完整计算，不缓存未提交事实。
- staging 文件丢失、损坏、过期、版本变化均失效，命中核对 staging 全文件 SHA-256；TTL 不代替事实校验。GET 不写主库、不启动导入、不排维护任务。
- POST 继续重新评估活动基线与确认计划，ETL 前和事实提交前仍核对 source manifest/SHA-256。已保留 staging 检测到源漂移时，即使新 JSON 解析结果相同，也拒绝本次旧确认。token 算法和响应字段保持原样。

## 验证

- Analysis/migration 提交前：54 passed。
- Import plan、API jobs、streaming staging、执行与端到端导入：93 passed；补齐非语义源漂移确认边界后，cache/API jobs 定向复验 49 passed（新增 cache 测试共 24 项）。日志中的 LibreSSL 和既有测试线程清理 warning 保留。
- 前端 data-import-health：5 passed。
- docs audit、diff check、Ruff/format/mypy/secrets hooks 通过；初次 mypy 的列表类型推断错误已修复，原日志保留。
- 独立 API smoke 与参数边界通过。唯一一次 `--only api` 局部阶段 PASS / 整体 PARTIAL：51 个目标、22 次请求各、slow_count=0，preflight hot P95 63.20 ms，未改变 500 ms 门槛。

## 唯一一次默认完整 fullstack

run ID：`20260920T134245.048885Z-9d74ae98a67f`；selection=`full`；overall=`FAIL`；总耗时 **1639763 ms**。命令使用 8000 后端、5173 前端、NO_PROXY/no_proxy 和同一 Online Backup source，未传 --only/--from、未跳过浏览器、未改变样本数/并发/timeout。

| 阶段 | 状态 | duration_ms |
|---|---|---:|
| preflight | PASS | 7598 |
| quality | PASS | 40748 |
| backend | PASS | 976945 |
| api | PASS | 168292 |
| browser-routes | PASS | 401984 |
| browser-interactions | FAIL | 43982 |
| browser-inventory | NOT_RUN | 0 |
| browser-compat | NOT_RUN | 0 |
| optional | NOT_RUN | 0 |

完整后端 **3026 passed / 3 skipped / 8 warnings，970.65 秒**；前端 **657 passed / 4 skipped**，build 通过。API 51 个测量目标全部通过，slow_count=0，preflight hot P95 **63.386 ms**。browser-routes 完整路由与重点视口矩阵通过；browser-interactions 桌面场景通过，两个移动场景失败。

完整日志与规范 run-scoped 报告保存在 `fullstack.log`、`fullstack-summary.json`、`fullstack-run/`。四个 browser 阶段单列如上，不以 API 局部成功替代浏览器验收。

## 正式数据与 Git 边界

正式数据逐文件核对：4183 → 4183 个文件；新增 0、删除 0、size/SHA-256 改变 0。mtime-only 变化见 `formal-diff.json`，未回写正式文件。完整清单保留在 `formal-before.json` / `formal-after.json`。

未 fetch；ahead/behind 仅比较本地缓存 origin/main。未 push、未部署、未运行或打开 Docker、未调用 AI/LLM 或 Spotify 等外部服务，未同步正式数据。原始数据库、导入文件和临时 staging 均未进入 Git。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0be86-06d0-7b51-b1ad-8a3f70c1a9ee/spotifystats-stage7d`。

## 停止时 Git 状态

当前 HEAD / 7C commit：`410d0b971dfdd8bd9efb750030a4dfeaf7f8a63b`；7D commit：无。相对缓存 origin/main **ahead 5 / behind 0**，未 fetch。暂存区为空，`git diff --check` 通过。

剩余未提交路径仅为：

- `backend/api/import_.py`
- `backend/domains/imports/streaming_staging.py`
- `backend/services/import_plan_service.py`
- `docs/reference/data-import-and-health.md`
- `backend/tests/unit/test_import_preflight_cache.py`

新增 7D 仓库报告/索引与更新 7C 后续状态的条件是默认完整 fullstack Pass，本轮未满足，因此只在本机证据目录保存本报告。8000/5173 本轮服务已停止。
