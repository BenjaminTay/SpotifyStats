# 增量导入 Phase A 交付报告

> 验收日期：2026-08-23
>
> Phase A 状态：Pass
>
> 完整增量导入状态：Partial；Phase B–E 尚未实施

## 交付范围

本轮只交付持久化结构和只读关系判定，不改变现有串流导入的覆盖式写入语义：

- migration 37 新增播放源指纹、指纹版本、导入代际、单例活动状态和导入运行记录结构；
- 源文件检查器生成按音频/视频隔离的只读 staging manifest；
- dataset digest 不依赖文件名、文件顺序或重新分包，并按精确记录去重；
- ImportPlan 判定 `baseline_required`、`identical`、`snapshot_superset`、`delta_tail`、`reconciled_snapshot`、`truncated_or_regressive`、`different_account` 和 `ambiguous`；
- Settings 预检展示关系、预计策略、记录变化、日期范围和受影响周/年；
- Account Data 用户名只生成带命名空间的不可逆 SHA-256，不进入 API 或日志。

`POST /api/import/streaming` 仍使用原有文件门禁、快照、覆盖式导入和回滚路径。安全 noop、append-only、指纹基线填充和 ChangeSet 执行属于 Phase B 之后的工作。

## 真实数据库证据

先使用 SQLite Online Backup 创建真实库副本，在副本上应用 migration 37 并执行只读预检：

| 指标 | 结果 |
|------|------|
| 现有播放 | 92,908 |
| 输入记录 | 92,908 |
| 关系 | `baseline_required` |
| 基线状态 | `missing` |
| 预计策略 | `full` |
| 预计影响 | 218 个榜单周、5 个年度范围 |
| 预检耗时 | 1.757 秒 |
| 预检前后副本 SHA-256 | 完全一致 |
| `playback_import_runs` | 0 |

源码变更期间已有本地开发后端因 auto-reload 自动在正式本地库应用 migration 37。随后只读检查确认：92,908 条旧播放的 `source_fingerprint` 和 `import_generation_id` 均为空，活动状态没有 generation、fingerprint version 或 digest，运行记录为 0。即 schema 已升级，但旧事实未被反推、重写或导入。

运行中后端的 `GET /api/import/preflight` 返回同样的 `baseline_required/full` 结论，且 OpenAPI 快照与运行时接口逐字节一致。

## 自动化验证

- 后端 unit：1,121 passed；
- 后端 contract：358 passed；
- 前端 Vitest：73 个文件、550 项 passed；
- 前端生产构建：passed；
- 本次后端文件 Ruff：passed；
- 本次前端文件 ESLint：passed；
- OpenAPI 类型新鲜度：passed；
- 文档审计：54 个当前 Markdown，passed。

全量前端 `npm run lint` 仍被仓库既有、与本次修改无关的错误阻断；本次涉及的三个手写前端文件已单独通过 ESLint。首次完整 unit 回归还发现搜索 rebase 测试把最新 migration 版本硬编码为 36，本轮已更新为 37 并补充活动状态表断言，重跑后全绿。

## 未完成边界

- 还没有完整基线导入写入源记录指纹；
- 还没有 identical 的执行级 noop；
- 还没有 append-only 基础事实写入和活动代际原子发布；
- Billboard 周分区、搜索快照、年度缓存、元数据和封面仍未由 ChangeSet 定向维护；
- 尚未执行 Phase B 的增量—全量逐表等价性测试。

因此当前可以使用只读计划判断输入关系，但点击导入仍会执行现有完整导入。
