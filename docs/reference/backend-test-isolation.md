# Backend 测试的数据库与派生文件隔离

## 默认入口

直接执行 `.venv/bin/pytest backend/tests/...` 即可。`backend/tests/conftest.py` 在导入应用和收集测试模块前调用 `path_safety.install_test_paths()`，创建本进程专用 `pytest-spotifystats-*` 临时目录：

| 状态 | 测试默认目标 |
|---|---|
| 主数据库、background JobQueue | 临时 `spotify_stats-test.db` |
| Billboard 持久快照 | 临时 `billboard.db` |
| Analysis stats/records 结果快照 | 临时 `analysis.db` |
| Yearly Review artifact | 临时 `yearly.db` |
| Community、Account Archive、Governance | 临时 `community.db`、`archive.db`、`governance.db` |
| Home JSON / LKG | 临时 `home/` |
| 封面读写 | 临时数据库旁的 `covers/` |

unit、contract 和其他普通测试固定从只读 tracked seed 初始化，经 SQLite Online Backup 复制并执行 integrity_check。单独设置 `SPOTIFY_STATS_TEST_SOURCE_DB` 不会改变这些测试的数据源。

`backend/tests/integration` 保留真实数据分布语义，必须在独立 pytest 进程中通过命令级插件显式 opt-in。插件在父 conftest/应用导入之前选定源，只接受 integration 目录内的测试目标；缺少源或混入 unit/contract 路径直接拒绝。进程从既有、正式 `data/` 外的 Online Backup 创建**一个 session-scoped 可写副本**，所有 integration case 共享，不按 case 再复制：

```sh
SPOTIFY_STATS_TEST_SOURCE_DB=/tmp/acceptance/data/main.db \
  .venv/bin/pytest -p backend.tests.real_data_integration backend/tests/integration -q
```

API acceptance 探针继续显式使用同一个既有工作副本：

```sh
python scripts/api_smoke_probe.py --db-path /tmp/acceptance/data/main.db
python scripts/api_boundary_probe.py --db-path /tmp/acceptance/data/main.db
```

fullstack 的 backend 阶段先执行 `backend/tests --ignore=backend/tests/integration`，再执行上述真实 integration 命令；两个 pytest 进程有不同的 run-owned basetemp，并分别保存 backend-seed.xml / backend-integration.xml 的数量与耗时。任一失败则统一 backend FAIL。两部分 collection 并集必须等于原始完整集合、交集为空，不以 marker 过滤遗漏测试。缺少明确真实源不能把 integration 静默改成 seed 或 skip。

Analysis 参数化测试直接复制小型 immutable seed，保留每个写测试的事务/revision 隔离，不复制 session 数据库。backup 源/目标连接显式关闭；每个 case 的自有目录在成功或失败时删除主库、WAL/SHM 和快照。

fullstack 通过 `scripts/test_storage_guard.py` 创建独立 TMPDIR 和 pytest `--basetemp`，成功、命令失败或中断均停止自有子进程并清理自有临时目录。报告保留在原 run 目录。每 200ms 检查逻辑文件字节总量和磁盘可用空间：本轮临时文件超过 2 GiB 或可用空间低于 12 GiB，立即终止，不自动重试。`test-storage.json` 保存峰值、全部采样、退出原因和清理结果；采样峰值不代表采样间隔内的绝对瞬时峰值。默认主机锁与证据目录在改变 TMPDIR 前固定，不因隔离而绕过并发锁。pytest retention 不是本修复的依据。

不再默认读取正式主库。上述六类 `SPOTIFY_STATS_*_CACHE_PATH` 无需运行者 export；若 caller 将它们或测试源设为正式 `data/`，bootstrap 直接失败。安全的既有导出值也会被当前 session 临时目标替代；测试内仍可 monkeypatch 到自己的 `tmp_path`。

## Fail-closed 规则

- 进程级 Python audit hook 检查 SQLite connect 和文件创建、写入、截断、删除、重命名、链接等动作；路径先解析 URI、相对路径和 symlink，正式 `data/` 下的目标拒绝操作。带 `dir_fd` 的清理操作按实际目录句柄解析，避免将临时目录中的同名 `data` 误认成仓库正式目录。
- SQLite ATTACH 额外检查路径。默认连接和 cursor 在每次 execute 时验证显式/绑定目标，避免 SQLite statement cache 跳过检查；不能确定目标的 ATTACH 表达式拒绝执行。自定义连接工厂保留，未能确定目标的 ATTACH 同样拒绝。
- audit guard 从 bootstrap 持续到进程退出，不随单个 fixture teardown 卸载。记录到的正式路径违规使 pytest session 非零退出，即使业务代码捕获了异常。
- 不在 session 结束时恢复模块级路径或环境变量到正式目标。异常、KeyboardInterrupt 后它们仍指向临时目录；atexit 仅清理该进程创建的目录，不停止任何用户服务。
- 此隔离是 Python 测试基础设施，不是任意原生程序的操作系统沙箱。测试调用外部工具时仍必须显式传入临时数据库/目录，不得让原生工具采用正式默认路径。

这些规则覆盖本仓库实际使用的 SQLite、Path/open、Home writer、sidecar writer 和 JobQueue 路径；不修改产品缓存或统计语义。`unit/conftest.py` 不能阻止 pytest 加载父级 conftest，旧注释已更正。

回归使用模拟正式文件 canary，验证 bytes/mtime 不变，不将真实正式文件用作失败测试对象。恢复任务的正式 sidecar 前后摘要属于恢复验收，独立于 pytest。

相关记录：[阶段 0.5 安全收口](../reports/2026-09-19-billboard-sidecar-safety-closeout.md)。
