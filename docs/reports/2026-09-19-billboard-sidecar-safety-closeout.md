# 阶段 0.5 安全收口：Billboard sidecar 重新生成与测试隔离

> 2026-09-19，本地安全收口完成；本次局部回归为 **Partial**，不是完整全栈或生产验收。
> **采用由当前事实重新生成派生快照，不声称恢复了事故前的原始快照或字节。**

## 事故边界与恢复选择

阶段 0.5 首次回归遗漏 sidecar 环境隔离，既有测试调用默认 `clear_persisted_snapshots()` 清理并写入正式本地 Billboard sidecar。事故前行数、family 集和原始字节没有可靠记录，不能推断其已保留。收口开始时仅 1 条 `full_data`，SQLite integrity_check=ok，属于内容不完整而非数据库格式损坏。原始播放事实没有丢失。

已盘点 `/tmp/spotifystats-stage1.hMaxcF/data/billboard.db` 及阶段 1/0.5 测试副本；均未复制到正式目标。Billboard request/source key 包含主数据库绝对路径，即使播放数量相同，临时数据库 namespace 的记录也不能充作正式 exact 快照。选择当前正式主库及当前默认配置重新生成。

开始和替换前均检查 lsof，无应用、测试或维护进程持有正式 sidecar。初始正式 sidecar：11,137,024 bytes；WAL=0 bytes；SHM=32,768 bytes。路径、mtime、完整表/索引 DDL、integrity 和 family 留存于 `before.json`。

## 备份、只读构建与原子发布

主要恢复材料目录：

`/Users/benjaminlei/Code/202605-SpotifyStats/data/recovery/billboard-20260919-211721`

- 受损 SQLite Online Backup：`damaged-online-backup.db`。
- 替换前物理主文件：`damaged-original-main.db`。
- 旧 WAL/SHM：`damaged-original-main.db-wal`、`damaged-original-main.db-shm`。
- 校验成功候选副本：`verified-candidate-copy.db`。

另保留 21:14:18、21:14:57 的早期备份/候选检查目录，未删除任何恢复材料。文件使用现有 Git 忽略的 `.db` / `.db-wal` / `.db-shm` 命名，不进入提交。

正式主库始终使用真实路径，通过 SQLite `mode=ro` 和 `PRAGMA query_only=ON` 双重约束读取；Billboard sidecar 显式绑定临时目标。维护代码有请求可写连接用于历史 lazy schema 的路径，首次受控检查拒绝了 journal_mode 设置；harness 随后统一让这些连接走现有只读 get_db 入口，而非放行主库写入。已有表上的 IF NOT EXISTS 是只读连接允许的 no-op；真实 schema/data 写入仍由 query_only、只读 VFS 和写授权检查拒绝。无 migration、导入、JobQueue 或网络调用。

候选构建后逐行 `_decode_payload()` 校验长度、压缩流和 SHA-256；校验全部 family/request key/source revision/builder version，以及 readiness。以当前正式主库路径和参数重新计算的 **完整 expected key 集合** 与候选集合完全相等，故不是按数据量或字符串猜测 namespace。

临时候选先 checkpoint(TRUNCATE)，再转为 DELETE journal，确认 committed WAL 已合并。同文件系统执行单次 `os.replace(candidate, formal)`，发布前 fsync；旧 WAL/SHM 移入材料目录，不可能附着到新主文件。替换步骤含失败回滚：使用保留的旧主文件及原侧文件恢复旧状态，失败候选也保留。本次原子替换成功，未进入回滚分支。

## 当前正式状态

正式主库：**92,908 plays，MAX(play_id)=2,298,810，schema 73**。没有应用 migration 74。import revision=0（既有 playback_import_state），Billboard revision tuple 为 `[18, 18, 37, 37, 'ready:ready', 11, 7, 3]`。

默认过滤：min_ms=30000、music_only=true、merge_enabled=true、dynamic_threshold=true、gap=5、merge_level=2、include_compilations=false；track/album/artist Top N=30/20/20；周界 dow=4、hour=12，全期。

| family | 恢复前 | 重新生成后 |
|---|---:|---:|
| weekly | 0 | 1 |
| all_time | 0 | 1 |
| full_data | 1 | 1 |
| records | 0 | 1 |
| power_scores | 0 | 1 |
| summaries | 0 | 1 |
| year_end | 0 | 6 |
| 合计 | 1 | **12** |

Year-end 包含默认 year=None，以及 **2022、2023、2024、2025、2026** 全部 available years。builder=`billboard_persistent_snapshot_v1`，readiness=true，全部 payload 校验成功，integrity_check=ok。正式新文件 2,260,992 bytes。

Source revision：

- `87b9b25ab5b354fb6b6c5ff6d8d5aa4a0f66738182057794d70de664cc44ab71`：8 行。
- `ea721c59cbad0e8a220ae19b067392c70299bd734ee3b106a464b3aa9c5c8bc8`：4 行。

历史年度不含当前开放周时间依赖，因此两个 revision 是既有 key 合同的正常结果。每条完整 request/cache key 与 source revision 见 `candidate.json`。

候选和发布后各进行一次真实 FastAPI TestClient（无 lifespan）公开 GET；设置昂贵 builder、sidecar store 和 JobQueue sentinel，同时主库/sidecar SQLite 连接都强制只读。weekly、all-time、data、records、year-end 均 HTTP 200，snapshot.status=ready、freshness=current。默认 top_n+1 与不存在的 1900 年明确 HTTP 503；没有恢复请求内冷建或虚假空统计。所有 expected key 另以 allow_lkg=false 校验。

## 主库零业务内容变化与测试后正式文件不变

恢复前、构建后、最终回归后，主库 **125 张表**按稳定键逐行计算内容摘要并比较，全部相同，包括原始事实、身份、L2/L3、专辑项目、revision、settings、任务与导入表；不输出歌曲、艺人或播放明细。主数据库文件和 WAL 的 SHA-256 也完全相同。SHM 是读锁共享元数据，另记状态，不把其元数据变化解释为业务写入。

正式 sidecar 在发布后公开 GET 与最终 pytest 前后，bytes/SHA-256、mtime、family 数量、snapshot 数量均一致：

- SHA-256：`37443ec5fef0735ee2518bc1950adae37a33816ffe3fb28040a14384d3309605`。
- mtime_ns：`1789823863611885196`。
- 7 个 family、12 条 snapshot；integrity_check=ok。

证据：`final-state.json`、`verify-candidate.json`、`verify-published.json`。测试自身只使用模拟 canary，没有把正式文件作为故障注入对象。

## 测试隔离与验证

本轮测试基础设施改动：

- `backend/tests/conftest.py`：应用导入前 bootstrap；session 不恢复正式路径；记录到的违规即使被业务代码吞掉也令最终退出码失败；封面路径绑定临时目录。
- `backend/tests/path_safety.py`：提前建立 session 临时主库/缓存；readonly Online Backup seed；路径解析与进程级写入/connect guard；ATTACH 校验；退出只清理自己创建的目录。
- `backend/tests/unit/conftest.py`：更正“子 conftest 阻止父 fixture”的错误注释。
- `backend/tests/unit/test_derived_cache_isolation.py`：12 项隔离回归，覆盖默认 clear/rebuild、yearly/Home/JobQueue、canary bytes/mtime、失败/KeyboardInterrupt、symlink、捕获违规仍失败、SQL ATTACH。

默认 backend unit/contract/integration 均不再依赖运行者 export。缺省用 seed；真实分布 integration 应显式提供 `data/` 外的 Online Backup。已有 monkeypatch 临时路径仍可用。测试约定见 [Backend 隔离规则](../reference/backend-test-isolation.md)。这是 Python 测试层的保护；调用原生子进程仍须传入明确临时目标。

最终普通 pytest 命令覆盖上述隔离用例，以及 Billboard counting/persistent/default maintenance、Home/yearly、public snapshot boundary、migration 74 与历史周替换 ATTACH 兼容测试；最终 **89 passed（15.70s，1 条既有 LibreSSL warning）**，记录于 `verified-regression.log`。Python Ruff / py_compile、docs_audit（97 文件）与 git diff --check 全部通过。没有修改阶段 0/1/0.5 产品实现、探针或算法；事故旧报告仅追加本次收口链接，保留原始事实。

## 停止点与阶段 2

**本次安全前置条件已满足，可以在另行授权后进入阶段 2。**正式 Billboard 默认快照集已重新生成，测试默认路径隔离和 fail-closed 回归已建立；正式主库 schema 仍为 73，不将副本上的 migration 74 性能收益写成正式库已应用。

本轮仅完成本地恢复和测试隔离，未开始阶段 2、未访问生产、未配置 AI/OAuth/外部访问，未 commit、push 或部署。

安全证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-safety-closeout`；恢复数据库材料保留在上述本地 data/recovery 目录，不放入报告证据或 Git。
