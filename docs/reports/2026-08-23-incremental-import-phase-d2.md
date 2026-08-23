# 增量导入 Phase D2 交付报告

> 状态：Pass（D2a snapshot lineage/周账本、D2b 同一开放周实体级 delta、D2c 跨周账本替换均已完成）
>
> 验证日期：2026-08-23；真实数据库证据来自只读源的 SQLite Online Backup 临时副本，活动数据库未被写入

## 本阶段交付

- migration 42 扩展搜索 snapshot meta，持久化稳定策略键、来源事实代际、来源数据集 digest、基础 snapshot、构建策略、依赖 digest 和 ChangeSet digest；旧 ready snapshot 可以继续读取，但没有完整 lineage 时不能作为 delta 基线。
- 新增按 `track:id`、L1 `album:id`、L2/L3 `album_project:id`、`artist:id` 归一化的周榜账本。shared-full 在整组六套上下文原子发布时同步写入账本和 lineage，作为后续增量引导基线。
- 对“精确尾部追加完全落在同一个当前开放榜单周，并且没有影响任何已发布完整周”的保守范围，复制兼容的六套基础上下文和周账本，只从尾部闭包生成有符号逻辑播放差值，更新歌曲、L1 专辑、L2/L3 Album Project 和有效署名艺人的 lifetime 指标。
- delta 构建不调用 lifetime 播放加载器；执行前后复核活动事实、基础 snapshot payload、候选内容、播放规则、聚合语义、身份、署名、曲目组与 Album Project 依赖。六套结果和 lineage 在一个 `BEGIN IMMEDIATE` 中激活，失败或不兼容自动回退 D1 `shared_full_snapshot_rebuild`。
- 固定阈值与动态阈值证明的 Billboard 影响周改为取并集，避免固定阈值完整周已经变化、搜索却误判可以直接复制旧周榜。
- 自动推断 Album Project 按 `(canonical_name, artist_id, scope)` 复用稳定 ID，精确替换 membership 并清理过期推断项目；人工项目保持不变。相同输入重建不再使 L2/L3 搜索实体键漂移。
- 对恰好跨越一个开放周的精确尾部追加，只读取新完成周及其前后连续播放链闭包，重建 fixed/dynamic、L1/L2/L3 的歌曲、专辑和艺人 Top-N 周账本；旧历史周直接复用，新的开放周仍不发布。
- 合并完整周账本后，按稳定实体 ID 全局重算 peak、在榜周数和 Power score/rank。shared-full 同步使用相同的账本重算语义，同名但不同 ID 的专辑或艺人不再因显示名称相同而合并。

## 实施中发现并修复的问题

- L1 专辑元数据旧路径仅按规范化专辑名关联 Spotify 元数据，同名但不同 Spotify 专辑可能扇出并污染播放/周榜统计。现在按 `album_spotify_links` 的播放、曲目和置信度证据为每个本地专辑稳定选择一条 Spotify metadata；旧库缺少链接时只允许本地标题与 Spotify 标题都唯一的名称兜底，歧义标题不猜测。
- L2/L3 增量帧可能不带 `artist_name`，与 Album Project membership 合并后列名不会带预期后缀。归一化逻辑现在同时支持带后缀和无后缀的稀疏帧，避免尾部 delta 误报缺列。
- 周账本引导会折叠字节完全相同的重复事实；同一身份若存在冲突事实，则保留确定性行但将基线标为不可复用，避免有歧义的 lineage 进入 delta。
- 第一版跨周 helper 使用了不存在的 pandas `Timestamp.add()`，且 artist fan-out 与已规范化帧的 `raw_artist_id` 列发生碰撞；两项均由真实跨周验收暴露并修复，补充了周边界单测。
- 初次对账中六套周账本已完全一致，但约 1,300 个实体的榜单摘要不同。根因是旧 shared-full 按显示名称归组专辑/艺人，delta 按稳定 ID 归组；统一为稳定 ID 后六套上下文全列一致。

## 自动化与等价性验证

- D2c 定向回归覆盖增量计划门禁、跨周发布、账本严格校验、同名实体 ID 隔离、Power 全局传导、受影响周闭包、开放周排除和验收报告隐私：`72 passed, 1 warning`。
- 真实数据库副本的同周与跨周场景均通过六套上下文和六套周账本逐列双向 `EXCEPT=0`；跨周额外证明旧历史周不变、新完成周已发布、当前开放周仍排除。
- 完整 Unit：`1252 passed, 851 deselected`；完整 Contract：`368 passed, 1735 deselected`。
- 文档审计、Ruff、格式、mypy、Detect secrets、`git diff --check`：通过；`AGENTS.md` 与 `CLAUDE.md` 保持一致。

## 真实数据库副本

基线为 92,908 条播放、SQLite 文件 387,526,656 bytes；分别在临时副本加入 1 条同开放周尾部记录，或加入 1 条完整落在下一开放周的记录。源库以只读 URI 打开，migration、合成指纹、基线引导、delta 和 shared-full 参照构建只发生在 Online Backup 副本；默认自动删除工作目录。

| 场景 | delta | shared-full 参照 | 结果 |
|---|---:|---:|---|
| 同一开放周 | 1.093 秒 | 26.416 秒 | 单轮观察约 24.2×；复制周账本 |
| 恰好跨一个开放周 | 6.500 秒 | 26.339 秒 | 单轮观察约 4.1×；替换 1 个新完成周 |
| 六套实体上下文 | 49,892 行基线 | 49,892 行基线 | 两场景全列双向 `EXCEPT=0` |
| 六套周榜账本 | 90,448 行基线 | 90,448 行基线 | 两场景全列双向 `EXCEPT=0` |
| ready lineage | 6 套 | 6 套 | 来源代际、数据集、策略与依赖门禁通过 |
| lifetime 播放扫描 | 否 | 是 | delta 报告 `lifetime_scan=false` |

性能数字来自单轮临时副本，不作为稳定基准结论；等价性来自实体上下文和周账本逐列双向 `EXCEPT`。同周、跨周验收报告 SHA-256 分别为 `24a31c196d5476b0c47e404d85e2bd9db37a7f31b35fcc7eab3f8bd6b95029b0`、`9b81a7d7b9e885ab9d164b498a806ec2a7247e00607833ae85dfa982eb2e400c`，报告位于测试机临时目录，不包含数据库路径、周边界值、歌曲/艺人内容或播放明细。

## 当前边界与下一步

- D2 delta 只接受同周或恰好跨一个开放周的精确尾部 append，并要求 fixed/dynamic 两套阈值的影响范围都被 ChangeSet 覆盖。多周跳跃、历史增删、关闭连续播放合并、超过 10,000 条新增、基础 snapshot/账本缺失、依赖变化、闭包超过 100,000 行或并发代际漂移都会回退 shared-full。
- `lifetime_scan=false` 表示 delta 不加载或扫描完整播放历史来重建 lifetime DataFrame；跨周路径仍会读取新完成周和必要的前后连续播放链，并读取、摘要曲目组与 Album Project 等较小依赖表。基础 snapshot 并发栅栏目前核对 snapshot 标识、激活时间和实体/账本行数，后续可再加入持久化 payload digest 或单调发布 revision。
- Album Project 仍执行完整 rebuild；本阶段只稳定了推断项目身份，没有实现 ChangeSet 定向项目重建。启动恢复、完整替换的硬中止恢复和历史修正继续留在后续阶段。
