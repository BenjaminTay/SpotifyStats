# 旧数据库身份 fallback 索引一致性

## 语义和目标 DDL

`track_l1_identities.provider` 是兼容投影字段，不是 fallback 身份的限定条件。非空 `fallback_track_id` 在整个表内唯一，包括非 local provider 与 superseded 行。Spotify external owner 优先解析；没有 Spotify token 时使用未 superseded 的 fallback；找不到有效身份时保留原始 track ID。索引修复不能改变这些 JOIN 条件。

当前 schema 和 migration 48 的 canonical DDL：

```sql
CREATE UNIQUE INDEX idx_track_l1_local_identity
ON track_l1_identities(fallback_track_id)
WHERE fallback_track_id IS NOT NULL;
```

历史数据库可能实际安装的是 `WHERE provider='local'`。同名 `CREATE INDEX IF NOT EXISTS` 不会替换它；检查必须读取 `sqlite_master.sql`，不能仅看索引名或 migration 48 已完成。该历史谓词不被 loader JOIN 蕴含，会导致 `SCAN li_local LEFT-JOIN`。

## Migration 74 合同

- 通过正常版本化 migration 入口执行；新建和历史升级数据库收敛到相同索引。
- 检查实际 DDL；已是 canonical 定义时不 DROP/CREATE，不改变 schema cookie。
- 对需要替换/补建的索引先检查所有非空 fallback 是否重复，包括非 local 和 superseded 行；重复时抛出 `sqlite3.IntegrityError`，不更改身份、不自动删除或合并数据、不记录成功版本。
- 检查、DROP、CREATE 包含在同一 SAVEPOINT；创建失败恢复原索引。没有外层事务时显式 BEGIN，让 runner 的版本账本写入和索引修改一起提交；账本失败并关闭连接时两者一起回滚。直接调用 migration 的维护调用者负责 commit。调用者已有事务时不会提交调用者事务；外部读者不会观察到中间缺失索引。
- 不更改 `plays`、`tracks`、署名、身份、source link、external owner、L2/L3、专辑项目或时长数据，也不递增事实 revision 或触发快照重建。
- migration 成功后可重复调用；正确索引不重建。仓库 seed 仅同步版本账本，无需重新生成播放 fixture。

如果 migration 被重复数据阻止，保留现有数据库与索引，停止升级；需要按身份治理规则另行处理冲突后再重试，不在此 migration 自动修复事实。

## 验证与回滚

在 Online Backup 副本核对完整 DDL、数据分布和实际 loader SQL 的 EXPLAIN。主播放、artist 与 Billboard raw 的 `li_local` 应通过目标索引 SEARCH。查询字段、过滤、排序和 JOIN 均保持不变，不使用 `INDEXED BY`。

升级失败由 SAVEPOINT 原子回滚。已成功升级时，旧应用仍可使用该 canonical 索引，无需为代码回滚恢复低覆盖的历史索引；若确需撤销整个数据库升级，应恢复升级前 Online Backup，而不是手工改写身份或删除索引。

本地双副本对账、查询计划和无 profiler 独立进程测量见 [阶段 0.5 交付报告](../reports/2026-09-19-track-identity-index-repair.md)。性能合同见 [全栈验证参考](fullstack-verification.md#7-统一性能测量合同阶段-0)。
