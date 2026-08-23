# 增量串流导入 Phase E 交付与验收

> 状态：Pass
>
> 验证日期：2026-08-23
>
> 范围：历史完整快照对账、连续播放链局部闭包、定向 Album Project、硬中止与启动恢复

## 结论

Phase E 已完成。对于同账号、同时存在新增和移除、且输入时间包络覆盖现有完整范围的未知来源包，系统只会提出需要确认的 `reconciled_snapshot`；确认标识仍绑定输入和当前基线。确认后，旧身份精确删除、新身份插入、最终 count/digest 对账、活动代际、年度分区和 ChangeSet 在同一个 `BEGIN IMMEDIATE` 事务中发布。

历史修正会分别重建旧、新有序事实视图，从 added/removed 位置向前后闭合相同 track/source 的完整连续链，并比较 fixed/dynamic 两套逻辑贡献。只有 timestamp、维度、全局顺序、邻接、完整周、语义依赖、活动代际与 100,000 行成本门禁全部成立时，才从当前事实有界重算受影响完整周并原子替换四张 Billboard 聚合；否则自动全量重建。历史 reconcile 的六套搜索统计继续走 D1 shared-full，不使用未经证明的 snapshot delta。

Spotify 元数据刷新会返回实际更新的 Spotify 曲目/专辑和本地专辑重链范围。无删除且影响闭包精确时，Album Project 只重建相关 release group、standalone 和 compilation closure；manual 与未受影响项目保持不变。存在删除、证据不精确、闭包过大或无法证明时明确全量回退。Spotify 同曲分组也只扫描本次变化或实际刷新到的 Spotify 身份。

## 真实数据库副本验收

验收脚本：`scripts/phase_e_real_db_acceptance.py`。源库始终只读，所有迁移、合成修正、硬中止和恢复探针都在 `/tmp` Online Backup 副本完成；报告不输出数据库路径、实体内容、指纹或播放记录行。

| 项目 | 结果 |
| --- | --- |
| 源播放规模 | 92,908 条 |
| 历史修正影响范围 | 1 个完整榜单周 |
| Billboard 历史周局部替换 | 0.579 秒 |
| 同事实全量重建 | 3.540 秒 |
| 四张聚合双向差异 | 全部 0 |
| 未受影响历史周 | 四表摘要全部不变 |
| replace 在事实发布前 SIGKILL | 退出码 -9；旧事实、聚合、活动状态和关系保持不变；`quick_check=ok` |
| 合法 pending 启动恢复 | 幂等排队 1 个任务 |
| 活动 digest 漂移 | `recovery_blocked / recovery_active_digest_drift` |

机器可读报告位于一次性临时路径 `/tmp/spotifystats-phase-e-real.json`，SHA-256 为 `b19582fe2fcbea692003df85e48829a7a34fcf9354df672ea6f119143823331b`。

当前真实库仍早于 Phase B 指纹基线，因此验收副本使用 `play_id` 生成确定性测试指纹，并明确标记 `validates_source_fingerprints=false`。这可以验证 Phase E 的代际绑定、历史周等价、事务和恢复边界，但不冒充 Spotify 原始记录指纹验收；原始指纹关系仍由 Phase A/B 的真实导入证据负责。

## 故障与压力覆盖

- 全量后端门禁：Unit `1302 passed, 852 deselected`；Contract `369 passed, 1785 deselected`。仅有既存 urllib3/LibreSSL 与 AnyIO HTTP 422 弃用提醒。
- replace 批次中途失败和 finalizer 失败均验证旧事实、聚合、`track_albums` 与活动状态回滚。
- reconcile 验证 stale baseline、精确删除/新增、finalizer 异常回滚，以及与 clean replace 的活动事实等价。
- 20 轮 A/B 历史快照交替 reconcile 后，活动事实始终为 2 条、身份无重复、每轮只新增 1 条并移除 1 条。
- `maintenance_pending` 启动扫描严格反序列化 ChangeSet，并在维护前后核对 generation、fingerprint version、count 和 digest；瞬时维护错误保持 pending，证据漂移才进入 `recovery_blocked`。
- 定向 Album Project 测试覆盖 release-group 跨成员、compilation 传导、manual/未受影响三表整行不变、空影响 no-op、targeted/full 三表一致和四类 full fallback。

## 保留边界

- 删除场景的 Album Project 当前保守全量重建，因为删除后的旧反向链接不足以独立证明项目闭包。
- 历史 reconcile 的搜索快照仍使用 shared-full；D2 snapshot delta 只接受已证明的同周或恰跨一个开放周尾部追加。
- Online Backup 仍是维护阶段失败和跨事务外层事故的恢复边界；SQLite 原子事务负责事实发布前的进程崩溃回滚，启动 recovery 负责事实已发布但派生维护尚未完成的场景。
