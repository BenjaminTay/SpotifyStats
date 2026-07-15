# Genre 与 Language 首轮预审执行报告

日期：2026-07-15

## 本轮目标

- Genre 改为按 `style / scene / context / role` 分轴解析；Spotify 已覆盖的轴优先，缺失轴才使用已批准本地事实。
- Settings 直接展示按播放时长排序的 Style 待补缺口，不再把“Spotify 原始 genre 非空”等同于 Style 已覆盖。
- 为 Genre 与 Language 增加 Codex 首轮预审字段，但保持最终批准权属于用户。
- 将当前高影响缺口导入审核队列，所有建议继续保持 `suggested + open`，不得进入正式统计。

## 真实数据结果

| 范围 | 当前正式统计 | 本轮预审队列 |
| --- | --- | --- |
| Genre Style | 覆盖率 72.6%，未知约 1098.3 小时 | 6 位高影响艺人，合计约 817.1 小时 |
| Language | 覆盖率 95.37%，未知 185.556 小时 | 69 位艺人，54 条建议批准，15 条建议人工复核 |

Settings 当前筛选口径下 Style 待补约为 1099.2 小时；与上表差异来自播放合并间隔设置，不是数据丢失。

## Genre 首批 6 位

| 艺人 | 候选 Style | Codex 建议 |
| --- | --- | --- |
| Michael Wong | pop | 人工复核 |
| Stefanie Sun | pop | 人工复核 |
| A-Mei Chang | pop, rock | 人工复核 |
| Fish Leong | pop | 人工复核 |
| JJ Lin | pop, r&b | 人工复核 |
| G.E.M. | pop, dance pop, r&b | 人工复核 |

若仅在临时数据库中假设批准这 6 条，Style 覆盖率可从 72.6% 升至约 93.0%，未知降至约 281.3 小时。由于它们会显著改变 Pop 分布，首轮统一标记为 `manual_review`，不自动批准。

## Language 首批 69 位

- 54 条证据与候选语言相对单一，Codex 标记为 `recommend_approve`。
- 15 条涉及多语种、合辑/卡司、器乐或边界判断，标记为 `manual_review`。
- 69 条待审核来源共关联 80 条证据记录，证据 URL 缺失数为 0。
- 人工复核名单：Fiona Sit、Wicked Movie Cast、FIFTY FIFTY、Terence Lam、Crowd Lu、Jacky Cheung、BLACKPINK、Karen Mok、Shakira、Rema、Sandy Lam、LISA、Ryuichi Sakamoto、TWICE、Celine Dion。

## 数据边界

- Codex 预审只写入 `pre_review_*` 字段，不改变 `review_status`、`source_status` 或统计 revision。
- 只有用户在 Settings 填写处理说明并最终通过的事实，才进入 Genre 或 Language 正式统计。
- Genre 与 Language 继续独立治理；不得通过 genre、艺人名称或地区启发式推断 language。
- 导入脚本支持 dry-run 和幂等复跑：`scripts/import_metadata_pre_review_batch.py`。

## Language 第二轮证据审核与批准（2026-07-16）

- 对 54 条 `recommend_approve` 候选执行第二轮审核，逐项核对本地稳定 `artist_id`、Spotify 官方艺人 repertoire 页面和播放权重最高的 1 至 2 首代表录音。
- 54 位艺人均符合“长期或主要使用一种演唱语言”的项目口径；The Beatles、Kate Bush、Norah Jones、Gary Chaw、A-Lin 等艺人的零星异语录音已写入审核说明，但不构成持续第二语言目录。
- 正式批准 54 条，审核人为 `codex_second_pass_2026_07_16`，合计播放时长快照 83.258 小时。
- 每位艺人保留艺人级 repertoire 证据和代表录音证据，批准批次共 156 条证据记录。
- 15 条 `manual_review` Language 项和 6 条高影响 Genre 项保持 `open + suggested`，未自动批准。

| Language 指标 | 批准前 | 批准后 | 变化 |
| --- | ---: | ---: | ---: |
| 已分类覆盖率 | 95.37% | 97.45% | +2.08 个百分点 |
| 未分类占比 | 4.63% | 2.55% | -2.08 个百分点 |
| 未分类时长 | 185.56 小时 | 102.30 小时 | -83.26 小时 |

受控批准脚本为 `scripts/approve_artist_language_second_pass.py`，默认只在临时数据库 dry-run；只有传入 `--apply` 才修改真实数据库，并在修改前创建 SQLite backup。本次备份位于 `/tmp/spotify_stats_before_language_second_pass_20260716.db`。
