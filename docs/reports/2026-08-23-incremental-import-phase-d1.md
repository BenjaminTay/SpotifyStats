# 增量导入 Phase D1 交付报告

> 状态：Partial（Billboard 周聚合增量 Pass；搜索 shared-full 精确复用 Pass；snapshot delta 未完成）
>
> 验证日期：2026-08-23；真实数据库证据来自只读源的 SQLite Online Backup 临时副本，活动数据库未被写入

## 本阶段交付

- 尾部追加会从新增记录向前扩展完整的同曲、同来源连续播放链，分别构造旧、新局部逻辑帧，并把跨周收听时长切片纳入变化闭包；无法证明闭包、不是尾部追加或受影响完整周超过 25% 时安全回退全量。
- Billboard 从当前四张活动聚合复制到临时影子表，再对受影响周应用有符号贡献差值；单曲、专辑、来源和艺人四表通过唯一性、非负与代际依赖校验后在同一事务发布。
- 聚合有效性绑定 source dataset digest、事实代际、builder、播放策略、身份与署名 revision、曲目时长摘要和有效 canonical credit membership 摘要。Album Project membership 在四张基础周表之后读取，因此不错误地作为这四张表的复用门禁。
- 周榜、Power Score 与相关派生排序增加稳定 identity / 规范化文本裁决键；同播放次数、同收听时长的实体不再依赖数据库或 DataFrame 的偶然行顺序。
- 六套搜索精确上下文新增 `shared_full_snapshot_rebuild`：两个动态阈值作用域分别复用逻辑帧，L1/L2/L3 共用计算；primary 与 artist family 顺序处理并及时释放，且不再构建未消费的 lifetime 时长切片。
- 六个 context 全部计算、校验后才在一个 `BEGIN IMMEDIATE` 中激活；候选 generation、播放代际和语义依赖在构建前后均有稳定栅栏，失败不会留下部分 ready 集合。

## 等价性与自动化验证

- Billboard 覆盖动态/静态阈值、跨周时长、长连续链、已有歌曲新增署名、依赖变化回退、原子发布和稳定并列排序。局部路径与全量路径比较四张聚合表全部行，而不只比较 Top N。
- 搜索覆盖六个 `merge_level × dynamic_threshold` 变体、候选/语义代际栅栏、失败原子性、full fallback 和 shared/ordinary 上下文逐列等价。
- Unit：`1206 passed, 827 deselected`。
- Contract：`368 passed, 1665 deselected`。
- Ruff、格式检查、mypy 定向检查和 `git diff --check`：通过。

## 真实数据库副本

基线为 92,908 条播放、SQLite 文件 387,526,656 bytes；在临时副本加入 1 条精确尾部记录。源库以只读 URI 打开，所有合成指纹、migration 和构建只发生在 Online Backup 副本；默认自动删除工作目录。

| 项目 | 增量 / shared | 全量 / ordinary | 结果 |
|---|---:|---:|---|
| Billboard 四表 | 0.511 秒 | 3.258 秒 | 6.37×；双向 `EXCEPT=0` |
| Billboard 影响范围 | 1 个完整周 | 全部完整周 | 四表共 117,197 行完全一致 |
| 搜索六套 context | 24.935 秒 | 66.046 秒 | 单轮观察 2.649×；双向 `EXCEPT=0` |
| 搜索 payload/meta | 48,242 / 6 行 | 48,242 / 6 行 | 全列双向 `EXCEPT=0` |
| 搜索峰值 RSS | 1267.7 MiB | 约 1139.7 MiB | shared 低于 1280 MiB 门禁，但余量只有约 12.3 MiB |

这些性能数字来自单轮临时副本，不作为稳定基准结论；等价性结论来自逐表、逐列双向 `EXCEPT`。验收报告 SHA-256 为 `0639731a3f1fe16692bcc461df99d1009ec25d8ed18a9227fc4be17451b3ba31`，报告本身位于测试机临时目录，不含歌曲、艺人、文件路径或播放明细。

## 边界与下一步

- 搜索策略名称刻意使用 `shared_full_snapshot_rebuild`。它消除了六个变体各自重复扫描和重复构建，但仍从完整 lifetime 播放事实生成新的六套 snapshot；不能称为 snapshot delta。
- Phase D2 仍需复制兼容的上一 ready snapshot，只更新 ChangeSet 关联的歌曲、Album Project、有效署名艺人与受影响周排名实体；Power rank 需要从紧凑上下文全局重排，而不是重新加载完整播放历史。
- 当前 Billboard 影子发布虽然只重新计算受影响周，仍复制并重写四张活动聚合的全部约 11.7 万行。真实库已明显快于全量计算，但后续可在不破坏原子性的前提下评估更轻的发布方式。
- shared 搜索峰值 RSS 距 1280 MiB 既有冷建门禁较近。D2 除了降低 CPU，还必须给内存留下更稳定的余量；若旧 snapshot 或任何语义依赖不兼容，继续安全回退 shared-full。
