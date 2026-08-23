# 年度总结 artifact key 与增量导入失效契约

> 状态：已确认
> 日期：2026-08-23
> 适用范围：串流导入、年度事实分区、年度总结缓存与增量—全量等价性验收

## 1. 决策

年度总结验收不要求“增量路径”和“最终输入完整替换路径”生成相同的 artifact key。两条路径必须生成相同的年度确定性事实分区；artifact key 继续包含受影响年份的 `impact_revision`，用于记录被接受的事实变更历史并强制旧 artifact 失效。

因此，正式门禁是：

1. 相同最终输入的年度 factual partition（`report_year`、`direct_digest`、记录数和覆盖范围）完全等价；
2. 每次被接受且影响该年份的 append、reconcile 或 replace 都提升 `impact_revision`，并生成不同的 artifact key；
3. `identical` 导入不改变 factual partition、`impact_revision` 或 artifact key；
4. 不受影响年份继续使用原有 revision 和 artifact；
5. 任何依赖、规则或事实 revision 不匹配的缓存都不得作为 ready artifact 发布。

跨路径 artifact key 是否相同只作为诊断字段记录，不参与等价性通过判定。

## 2. 原因

artifact key 同时承担事实依赖标识和缓存失效边界。增量 reconcile 与最终输入完整替换即使收敛到相同事实，也经历了不同数量的已接受变更；若为了追求跨路径 key 相等而移除 `impact_revision`，可能重新命中变更前生成的旧 artifact，削弱“接受变更后必失效”的安全保证。

年度事实等价应由稳定事实分区证明，不应由带审计历史的缓存 key 代替。`prefix_digest`、`impact_revision` 和 `source_generation_id` 仍保留为失效与追踪信息，但不作为跨执行历史的事实相等条件。

## 3. 验收证据

`scripts/incremental_import_end_to_end_acceptance.py` 显式输出 `yearly_artifact_contract`：

- `fact_partition_equal` 比较增量 reconcile 与完整 replace 的最终事实分区；
- 三个 `*_invalidated_impacted_year` 门禁分别验证跨周 append、同周 append 和历史 reconcile；
- 三个 `identical_*_unchanged` 门禁验证重复导入不抖动事实、revision 或 key；
- `yearly_key_interpretation.artifact_keys_equal` 只保留为解释性观测。

以上门禁任一失败，终验脚本整体状态为 `failed`。
