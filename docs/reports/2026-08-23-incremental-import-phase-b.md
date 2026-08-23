# 增量导入 Phase B 交付报告

> 验收日期：2026-08-23
>
> Phase B 功能状态：Pass
>
> 崩溃恢复与完整增量导入状态：Partial；派生 pending/active、后台任务代际隔离、ChangeSet 维护及历史修订仍待 Phase C–E

## 交付范围

本轮把 Phase A 的只读关系判定接入串流导入执行路径：

- `mode=auto|append|replace` 在真正写库前重新检查输入文件、账号证据和数据集关系；
- 旧库首次导入走完整替换并为每条播放写入版本化源指纹和导入代际；
- `identical` 在创建数据库快照和运行派生维护前结束为 noop；
- 已证明的 `snapshot_superset` 或同账号尾部 `delta_tail` 只插入新播放，复用既有事实和实体；
- append 不清空播放、聚合或曲目—专辑关系，同一事务内完成全部批次写入；
- 证据不足、不同账号、历史删除或修订不能用 append 绕过，风险 replace 必须明确确认；
- 已有播放但没有指纹基线时不会自动覆盖，必须确认输入包可作为完整历史；
- 警告与覆盖确认绑定具体输入和活动基线，文件或数据库变化会使旧确认失效；
- 自动尾部追加要求输入与活动集存在共同记录；零重合包不会借用可能过期的 Account Data 自动判为同账号，可由用户明确请求 fail-closed 尾部验证；
- append 在提交前核对旧基线 digest、实际输入 digest 和实际新增 identity digest，事实与活动状态同事务提交；
- 导入器异常会显式 rollback、关闭写连接，再进入 SQLite 快照恢复；
- 成功、noop 和等待确认写入紧凑运行记录，不保存原始播放 JSON、用户名或单条指纹明细；
- Settings 展示自动判定结果，并只在确需覆盖时提供明确替换确认。

Phase B 只增量化基础事实写入。append 成功后，元数据补齐、Album Project、Billboard、年度缓存和音乐查找仍调用现有完整维护入口，范围收缩属于 Phase C–D。

## 真实数据库副本证据

验证使用 SQLite Online Backup 创建的 `/tmp` 副本；没有对正式本地库执行 POST 导入，临时副本已删除。

| 场景 | 关系 / 策略 | 结果 | 基础写入耗时 |
|------|-------------|------|--------------|
| 首次建立基线 | `baseline_required` / full | 写入并激活 92,908 条 | 5.732 秒 |
| 相同输入 | `identical` / noop | 0 条写入，事实和维表不变 | 关系评估冷读 3.667 秒；终态记录 0.003 秒 |
| 完整快照增加 1 条尾部播放 | `snapshot_superset` / incremental | 新增 1，复用 92,908，活动集 92,909 | 3.529 秒 |
| 同一最终输入完整替换 | replace / full | 活动集 92,909 | 5.843 秒 |

对增量结果和完整替换结果比较 `plays`、`artists`、`albums`、`tracks`、`track_albums`、`track_artists` 的规范化语义哈希，六张表全部一致。append 事务回滚测试还将批次大小压到 1，并在第二批故意抛错；失败后活动事实、代际和导入状态均保持原值。

这些耗时只覆盖关系评估与基础事实写入，没有把 Phase C 尚未实现的完整派生维护计入，因此不能作为当前端到端导入时间承诺。当前最确定的端到端收益是 identical 输入不再创建快照、重写事实或重建派生数据。

## 正式本地库状态

开发后端 auto-reload 已在正式本地库应用 migration 37，但本轮没有替用户启动写入导入。只读检查时正式库仍有 92,908 条旧播放，指纹和导入代际为空；活动状态单例行存在但 generation、版本和 digest 为空，运行记录为 0。

因此下一次由用户在 Settings 触发的 `auto` 导入会要求确认完整替换，再建立一次基线；之后相同输入才能 noop，已证明的尾部新增才能 append。此次交付没有声称正式本地库已经建立基线。

## 自动化验证

- 后端 unit：1,147 passed；
- 后端 contract：366 passed；
- 前端 Vitest：73 个文件、557 项 passed；
- 前端生产构建：passed；
- 本次后端文件 Ruff：passed；
- 本次前端文件 ESLint：passed；
- OpenAPI 类型与运行时快照逐字节一致；
- 文档审计：56 个当前 Markdown，passed。

全量前端 lint 仍有仓库既有、与本轮修改无关的错误；本次涉及的手写前端文件单独通过 ESLint。

## 恢复与一致性边界

- append 的基础事实批次在一个 SQLite 事务内完成，计数或最终 digest 不一致会 fail closed；
- append 的实际输入、新增 identity、事实和活动代际在同一事务内核对并发布；可捕获异常先显式 rollback/close，再使用现有 SQLite 快照回滚；
- 活动事实发布后才运行完整派生维护；硬中止仍可能留下新事实与旧或半完成派生数据；
- 封面与搜索后台任务尚未绑定导入代际，维护后段失败与快照恢复之间仍存在后台副作用竞态；
- 完整 replace 仍沿用旧的分批提交路径。若进程被强制终止，恢复依赖导入前快照，不是跨进程原子切换；
- Phase B 没有新增独立 TEMP SQLite staging，延续现有批次 JSON reader；
- 历史删除、历史修订、时间倒退和不同账号不会自动 reconcile；
- Billboard 受影响周闭包、跨周连续播放边界、搜索快照 delta、年度缓存和封面任务去重仍待 Phase C–D。

## 下一步

Phase C 应从 append 产出的 ChangeSet 开始，只重算受影响实体、日期、年份与开放榜单周，并为每项派生数据建立独立 revision。验收重点是增量维护与完整重建等价，以及旧封闭榜单周不被重复扫描。
