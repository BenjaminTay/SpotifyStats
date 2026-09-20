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

默认数据来自只读的受控 seed，经 SQLite Online Backup 复制；保留 integrity_check。真实分布测试须显式提供位于仓库 `data/` **之外**的 Online Backup：

```sh
SPOTIFY_STATS_TEST_SOURCE_DB=/tmp/my-test-copy.db .venv/bin/pytest backend/tests/integration/
```

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
