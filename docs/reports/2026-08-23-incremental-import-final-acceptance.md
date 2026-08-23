# 串流数据增量导入最终闭环验收

> 日期：2026-08-23
> 结论：**Pass**
> 验收脚本：`scripts/incremental_import_end_to_end_acceptance.py`
> 结构化结果：`/tmp/spotifystats-import-e2e-final.json`
> SHA-256：`6350979f4095ed088f15d40f2e1de3bc554a7bc841fd71f8222b640a394f18de`

## 1. 验收边界

本轮补齐从原始 Spotify JSON 到生产 `import_data` 的闭环证据。终验脚本内的所有数据库写入、迁移、派生维护和对照计算都发生在 `/tmp` 新建的隔离目录；当前真实数据库在终验运行中只以 SQLite `mode=ro` 打开，原始导出文件只读。开发后端热重载触发的本地迁移单独记录在第 7 节。

临时 staging 使用分块 JSON array decoder 和每 1,000 条一次的 SQLite 批量写入，不读取或保留完整源文件；专项测试以 2,505 条单文件并禁止 `Path.read_bytes()` 验证真实流式路径。首次 staging 还会保守清理超过 24 小时、受控前缀、当前用户且保持 `0700` 的崩溃孤儿目录，任何边界不明确项都不会删除。

脚本包含两层验收：

1. 真实 13 个导出文件、92,908 条记录导入 `/tmp` 空库，建立真实源指纹基线，完整构建 Album Project、Billboard、六套搜索和首页，再执行 identical 计划；
2. 受控合成包执行 baseline → identical → 跨周 append → 同周 append → 历史 reconcile，并与“最终输入从空库完整重建”的 replace 比较全部要求的语义投影。

## 2. 真实源基线结果

- 真实库：92,908 条播放，migration 45，`PRAGMA quick_check=ok`；验收前后文件大小、mtime 和 inode 不变。
- 原始导出：13 个文件；验收前后 size/mtime manifest 不变。
- 空库 baseline：活动记录 92,908，输入 digest 与活动数据集 digest 相同。
- baseline staging + 计划：5,514.742 ms。
- 事实写入与活动状态发布：7,503.206 ms，其中事务内 finalizer 2,074.458 ms。
- Track Group full：3.166 ms；Album Project full：118.378 ms；Billboard 四表 full：3,869.784 ms；Billboard 消费 payload：5,533.333 ms。
- 六套搜索 full：73,947.015 ms，6 个 variant 全部 ready；首页服务层首响：7,050.656 ms。
- 第二次 identical staging + 计划：6,903.600 ms；关系为 `identical`，数据库无写入。
- 真实全链总时间：110,457.056 ms；消费侧共发布 216 个完整 Billboard 周。
- `validates_source_fingerprints=true`。这项证据不再依赖对旧库 play_id 生成的合成指纹。

## 3. 增量策略与时间

合成矩阵使用 12 个历史榜单周、4 首曲目、1 个跨周追加和 1 个同开放周追加，再把一首曲目的旧专辑关系纠正为新专辑。

| 阶段 | staging + 计划 | 事实发布 | Billboard | 搜索 | 端到端 | 实际策略 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 跨周 append | 4.761 ms | 33.519 ms | 28.386 ms | 894.204 ms | 967.670 ms | Billboard `partition`；首次建立 `shared_full_snapshot_rebuild` 基线 |
| 同周 append | 6.860 ms | 33.440 ms | 26.253 ms | 136.204 ms | 208.842 ms | Billboard `partition`；六套 `incremental_snapshot_delta` |
| 历史 reconcile | 8.269 ms | 74.665 ms | 33.098 ms | 1,728.930 ms | 1,852.023 ms | Billboard `historical_partition`；Album Project 因删除语义安全回退 full；搜索 full |
| 空库完整 replace 对照 | 3.494 ms | 38.459 ms | 28.954 ms | 2,170.555 ms | 2,243.170 ms | Billboard full；搜索 full |

跨周 append 后，消费者可见榜单包含刚刚结束的 `previous_open_week`，不包含新的 `current_open_week`；`complete_week_gate=true`。这里验收的是实际 Billboard 消费 payload，而不是内部聚合暂存行。

## 4. reconcile 与 replace 等价性

以下投影逐行比较全部通过：

- 活动播放事实闭包：41 行；
- 有效 credits：5 行，包含 primary 与 featured；
- 活动 `track_albums` 闭包：4 行；旧专辑关系不进入活动消费者；
- 自动 Track Group：1 个组、2 个成员；增量路径与空库完整重建的稳定身份、主曲、艺人和成员完全一致；
- Album Project identity、album membership、track membership；
- 四张 Billboard 聚合表；
- Billboard 完整 payload、Power、records；
- Year-End 输入与 payload；
- 音乐查找候选文档；
- L1/L2/L3 × dynamic on/off 六套精确 snapshot；
- 年度 partition 的 factual direct digest、记录数与覆盖范围；
- 首页 archive 事实。

搜索最终为 6 个 ready variant、44 条 entity context；候选索引为 17 条文档。增量 reconcile 与空库完整 replace 的候选和六套精确快照 digest 完全一致。共 14 项语义投影全部通过。

## 5. 年度与首页

- 年度 partition factual digest 在增量与 replace 间一致。
- `yearly_artifact_contract` 已成为终验硬门禁：跨周 append、同周 append 与历史 reconcile 均须提升受影响年份的 `impact_revision` 并更换 artifact key；identical 必须保持事实 partition、revision 与 key 不变。
- 年度 artifact key 不要求跨执行历史相同：`impact_revision` 会记录被接受的变更次数，因此同一最终事实经过不同导入路径时 prefix revision 与 cache key 可以不同；这属于预期失效语义，不是事实差异。正式决策见 [`../designs/2026-08-23-yearly-artifact-key-invalidation-contract.md`](../designs/2026-08-23-yearly-artifact-key-invalidation-contract.md)。
- 在隔离小库上，确定性首页 builder 首次响应为 171.067 ms；这是服务层首响，不是浏览器/HTTP/生产网络时延。
- 同一隔离库的 Billboard 完整 payload 为 653.901 ms，Year-End payload 为 212.060 ms。

## 6. 未扩大结论

- 真实 92,908 条数据已验证原始源解析、真实指纹 baseline、事务事实发布、Album Project、Billboard、六套搜索、首页首响和 identical no-op；历史 reconcile 与空库 replace 的逐项等价矩阵使用受控合成原始 JSON，真实副本上的增量和硬中断恢复仍由 Phase D/E 的独立报告覆盖。
- 本报告不代表生产部署、浏览器视觉验收或外部 Spotify 元数据网络成功。
- `/tmp` JSON 是本次可复核结果；默认脚本结束会清理所有隔离数据库，不保留私人播放明细。

## 7. 开发库迁移说明

开发后端以 `uvicorn --reload` 运行，migration 43 文件保存后触发了自动重启，因此真实本地库在本轮开发过程中实际完成了 Track Group identity 迁移。过渡 schema 先后由 migration 44、45 修复；两次均先在 SQLite Online Backup 副本预演。最终真实库为 migration 45，`track_groups` 24 行、`track_group_members` 48 行，迁移前后数量不变；Track Group 外键检查为空，`PRAGMA integrity_check=ok`。这属于本地开发库迁移，不代表远程生产发布。

## 8. 提交前门禁

- 后端 Unit：1,337 passed；Contract：369 passed。
- 前端：73 个测试文件、557 项测试通过；生产构建通过，仅有既存的大 chunk 提示。
- 全仓 pre-commit：Ruff、Ruff format、mypy、Detect secrets 全部通过。
- `scripts/docs_audit.py` 与 `git diff --check` 通过。
