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

## 高影响 Genre 与 Language 最终审核（2026-07-16）

本轮由 Codex 作为审核人执行证据核验，审核标识为
`codex_evidence_audit_2026_07_16`。正式写库前先在临时 SQLite 副本运行完整
dry-run，并通过 review state machine、证据 validator、外键检查和
`PRAGMA integrity_check`。

### Genre 结论

| 艺人 | 最终 Style | 审核说明 |
| --- | --- | --- |
| Michael Wong | pop | Apple Music 支持稳定 pop/ballad 风格；C-Pop 保留在 scene 轴 |
| Stefanie Sun | pop | 采用稳定 pop 风格，不把宽泛 alternative 影响扩张到全生涯 |
| A-Mei Chang | pop, rock | 台湾文化部同时支持 pop diva 与 Amit rock persona；保留 era caveat |
| Fish Leong | pop | Apple Music 明确描述 pop-ballad 目录 |
| JJ Lin | pop, r&b | AllMusic 支持长期 R&B-influenced Mandopop |
| G.E.M. | pop | 原多标签候选收紧为 pop，避免证据不足的次级风格被等比例放大 |

6 条全部批准后，Style 覆盖率从 72.6% 提升至 93.0%，taxonomy 轴汇总的未知
时长从 1098.4 小时降至 281.3 小时；Settings 的逐艺人缺口列表为 282.1 小时，
约 0.8 小时差异来自该接口先把每位艺人时长舍入到 0.1 小时后再求和。Pop 占
已知 Style 的 63.4%；Top artist 为
Taylor Swift 21.6%、Michael Wong 18.4%，没有触发单艺人 70% dominance
warning。A-Mei 对 Rock / Alternative 的贡献为 35.3 小时，JJ Lin 对
R&B / Soul 的贡献为 20.0 小时，均保留来源与 artist-level/era 限制说明。

### 15 条高风险 Language 结论

- 批准 14 条：Fiona Sit、Wicked Movie Cast、FIFTY FIFTY、Terence Lam、
  Crowd Lu、Jacky Cheung、BLACKPINK、Karen Mok、Shakira、Sandy Lam、LISA、
  Ryuichi Sakamoto、TWICE、Céline Dion。
- Karen Mok 在原粤语、国语候选上补充英语正式目录证据。
- TWICE 在原韩语、日语候选上补充正式英语录音证据。
- Rema 的英语单语候选不予批准：代表目录持续使用 Nigerian Pidgin，直接
  降级为 `en` 会产生假精度，旧 review 以 `insufficient_evidence` 结案。
- `artist-language-v3` 新增 ISO 639-3 `pcm` 后，为 Rema 建立新的
  `en + pcm` 多语言事实并通过同一 validator 批准。

### Language 高播放长尾

继续审核下一批高播放未知艺人。31 位中批准 29 位，包括单语、多语言和器乐
事实；Kristen Anderson-Lopez 与安沐凡因主艺人行混合作曲者、demo、人声、
伴奏或器乐归属，以 `insufficient_evidence` 结案，不强行标为英语或器乐。

Language 最终覆盖率从本轮开始前的 97.45% 提升至 98.46%，未知时长从
102.30 小时降至 61.86 小时。最终动态 buckets 为：英文 2609.77 小时、
中文 882.01 小时、多语言 451.48 小时、器乐 2.69 小时、意大利文 1.72
小时、泰文 1.42 小时、未知 61.86 小时。Genre 与 Language 的 open review
队列均为 0。

### 可恢复性

- 高影响审核前备份：`/tmp/spotify_stats_before_high_impact_metadata_audit_20260716.db`
- Language 长尾审核前备份：`/tmp/spotify_stats_before_language_long_tail_audit_20260716.db`
- 受控脚本：`scripts/review_high_impact_metadata_batch.py`、
  `scripts/approve_artist_language_long_tail_batch.py`
- 两个脚本默认 dry-run；只有显式 `--apply` 才写正式数据库。
