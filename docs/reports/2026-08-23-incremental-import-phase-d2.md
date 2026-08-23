# 增量导入 Phase D2 交付报告

> 状态：Partial（D2a snapshot lineage/周账本 Pass；D2b 同一开放周实体级 delta Pass；D2c 跨完整周账本替换未实现）
>
> 验证日期：2026-08-23；真实数据库证据来自只读源的 SQLite Online Backup 临时副本，活动数据库未被写入

## 本阶段交付

- migration 42 扩展搜索 snapshot meta，持久化稳定策略键、来源事实代际、来源数据集 digest、基础 snapshot、构建策略、依赖 digest 和 ChangeSet digest；旧 ready snapshot 可以继续读取，但没有完整 lineage 时不能作为 delta 基线。
- 新增按 `track:id`、L1 `album:id`、L2/L3 `album_project:id`、`artist:id` 归一化的周榜账本。shared-full 在整组六套上下文原子发布时同步写入账本和 lineage，作为后续增量引导基线。
- 对“精确尾部追加完全落在同一个当前开放榜单周，并且没有影响任何已发布完整周”的保守范围，复制兼容的六套基础上下文和周账本，只从尾部闭包生成有符号逻辑播放差值，更新歌曲、L1 专辑、L2/L3 Album Project 和有效署名艺人的 lifetime 指标。
- delta 构建不调用 lifetime 播放加载器；执行前后复核活动事实、基础 snapshot payload、候选内容、播放规则、聚合语义、身份、署名、曲目组与 Album Project 依赖。六套结果和 lineage 在一个 `BEGIN IMMEDIATE` 中激活，失败或不兼容自动回退 D1 `shared_full_snapshot_rebuild`。
- 固定阈值与动态阈值证明的 Billboard 影响周改为取并集，避免固定阈值完整周已经变化、搜索却误判可以直接复制旧周榜。
- 自动推断 Album Project 按 `(canonical_name, artist_id, scope)` 复用稳定 ID，精确替换 membership 并清理过期推断项目；人工项目保持不变。相同输入重建不再使 L2/L3 搜索实体键漂移。

## 实施中发现并修复的问题

- L1 专辑元数据旧路径仅按规范化专辑名关联 Spotify 元数据，同名但不同 Spotify 专辑可能扇出并污染播放/周榜统计。现在按 `album_spotify_links` 的播放、曲目和置信度证据为每个本地专辑稳定选择一条 Spotify metadata；旧库缺少链接时只允许本地标题与 Spotify 标题都唯一的名称兜底，歧义标题不猜测。
- L2/L3 增量帧可能不带 `artist_name`，与 Album Project membership 合并后列名不会带预期后缀。归一化逻辑现在同时支持带后缀和无后缀的稀疏帧，避免尾部 delta 误报缺列。
- 周账本引导会折叠字节完全相同的重复事实；同一身份若存在冲突事实，则保留确定性行但将基线标为不可复用，避免有歧义的 lineage 进入 delta。

## 自动化与等价性验证

- 定向 D2 回归覆盖 migration、lineage、稳定 Album Project ID、逻辑播放差值、固定/动态影响周、同名专辑隔离、六套 snapshot 原子发布、delta 门禁、shared-full fallback、生产 builder/migration gate 和真实验收脚本：`176 passed, 1 warning`。
- seed 数据库加 1 条同开放周尾部记录：delta 92.754 ms，shared-full 568.682 ms；六套上下文和六套周账本逐列双向 `EXCEPT=0`。
- 完整 Unit：`1244 passed, 833 deselected`；完整 Contract：`368 passed, 1709 deselected`。
- 文档审计、Ruff、格式、mypy、Detect secrets、`git diff --check`：通过；`AGENTS.md` 与 `CLAUDE.md` 保持一致。

## 真实数据库副本

基线为 92,908 条播放、SQLite 文件 387,526,656 bytes；在临时副本建立六套 shared-full lineage 后加入 1 条完全位于同一开放榜单周的精确尾部记录。源库以只读 URI 打开，migration、合成指纹、基线引导、delta 和 shared-full 参照构建只发生在 Online Backup 副本；默认自动删除工作目录。

| 项目 | delta | shared-full 参照 | 结果 |
|---|---:|---:|---|
| 六套搜索 snapshot | 1.111 秒 | 21.824 秒 | 单轮观察约 19.6× |
| 实体上下文 | 49,892 行 | 49,892 行 | 六套全列双向 `EXCEPT=0` |
| 周榜账本 | 90,448 行 | 90,448 行 | 六套全列双向 `EXCEPT=0` |
| ready lineage | 6 套 | 6 套 | 来源代际、数据集、策略与依赖门禁通过 |
| lifetime 播放扫描 | 否 | 是 | delta 报告 `lifetime_scan=false` |

性能数字来自单轮临时副本，不作为稳定基准结论；等价性来自实体上下文和周账本逐列双向 `EXCEPT`。验收报告 SHA-256 为 `4ba439b9ef0fbc06aa6348f806b5b7850bb232e630b0093d1fbebb5d9670dbe3`，报告位于测试机临时目录，不包含数据库路径、歌曲/艺人内容或播放明细。

## 当前边界与下一步

- D2b 只接受同一个当前开放榜单周内的精确 append，并要求 fixed/dynamic 两套阈值都没有影响任何已发布完整周。跨周、历史增删、关闭连续播放合并、超过 10,000 条新增、基础 snapshot/账本缺失、依赖变化或并发代际漂移都会回退 shared-full。
- `lifetime_scan=false` 表示 delta 不加载或扫描完整播放历史来重建 lifetime DataFrame；发布门禁仍会读取并摘要曲目组、Album Project 等较小依赖表。基础 snapshot 并发栅栏目前核对 snapshot 标识、激活时间和实体/账本行数，D2c 可进一步加入持久化 payload digest 或单调发布 revision。
- 当前 delta 复制未变化的开放周账本，并更新 lifetime 指标；它尚未替换受影响完整周账本，也未从紧凑上下文重算 chart summary 和全局 Power rank。因此不能把本报告写成 Phase D2 全部完成。
- D2c 下一步应从受影响完整周的 Billboard 分区重建六套紧凑账本，替换对应周，再用 SQL window 从紧凑上下文重排 Power rank；仍需逐套上下文、逐套账本与 shared-full 双向对账。
- Album Project 仍执行完整 rebuild；本阶段只稳定了推断项目身份，没有实现 ChangeSet 定向项目重建。启动恢复、完整替换的硬中止恢复和历史修正继续留在后续阶段。
