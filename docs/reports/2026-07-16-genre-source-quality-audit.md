# Genre 来源可信度审核报告（2026-07-16）

## 目标

在 Genre Style 覆盖率已达到 93.0% 后，停止追求 100% 覆盖，优先处理
Settings 分类审计中由无链接 LLM 来源主导的标签。本轮只审核已有 Style
事实的来源和范围，不为未知艺人强行补标签。

审核人：`codex_genre_quality_audit_2026_07_16`

受控脚本：`scripts/audit_artist_genre_source_quality_batch.py`

## 选择方法

按当前 Settings 播放过滤口径计算 canonical Style 的 source mix，并优先选择
Electronic / Dance 与 Hip-Hop / Rap 中播放贡献最高的 LLM 来源艺人。15 位艺人
累计覆盖这两个标签的大部分无证据 LLM 时长。

所有结论必须满足：

- 使用 Apple Music、AllMusic、Recording Academy 等可复核 HTTPS 资料；
- 只保留资料支持的持续 artist-level 风格；
- 不把一次合作、单首歌曲或跨界流行度提升为长期 Style；
- 通过 `artist_genre_review_queue` 和既有 review state machine 批准；
- 脚本默认只在临时数据库 dry-run，显式 `--apply` 才修改正式数据库。

## 审核结论

| 艺人 | 批准的 artist-level genres | 关键处理 |
| --- | --- | --- |
| Chappell Roan | pop, dance-pop | 用可靠资料确认持续 dance-pop，而非无链接 LLM 判断 |
| Kesha | pop, dance-pop, electropop | 保留长期 electro/dance-pop 主线 |
| Beyoncé | pop, r&b, dance-pop | 移除 artist-level hip hop；跨界合作不等于长期 Hip-Hop 分类 |
| Troye Sivan | pop, synth-pop | Apple Music 支持 pop 与持续 synth-pop 目录 |
| Halsey | pop, electronic, alternative rock | 保留资料明确支持的三类跨风格主线 |
| Selena Gomez | pop, dance-pop | 移除缺乏稳定 artist-level 依据的 R&B |
| Rihanna | pop, r&b, dance-pop | 三类均有长期目录依据 |
| RAYE | pop, dance-pop | 移除当前资料不足以支持为同等长期分类的 R&B |
| Carly Rae Jepsen | pop, dance-pop | 用已审计 dance-pop 取代无链接 synth/electropop 来源 |
| Nicki Minaj | hip hop, pop | 同时保留长期 Rap 身份与明确 pop crossover |
| Doja Cat | hip hop, pop, r&b | 三类均有长期目录和 rap roots 依据 |
| Lil Nas X | pop rap | 不再使用无法表达其跨界目录的 hip-hop-only 标签 |
| Lizzo | hip hop, r&b, pop | 保留长期 rap、R&B/soul 与 pop crossover |
| Cardi B | hip hop | 移除仅因 crossover 流行度产生的 generic pop 标签 |
| Ice Spice | hip hop, drill | 使用明确 Bronx drill / Rap 分类 |

## Before / After

| 指标 | Before | After |
| --- | ---: | ---: |
| Style 覆盖率 | 93.0% | 93.0% |
| Electronic / Dance 置信层级 | low | medium |
| Electronic / Dance 的 LLM 占比 | 91.0% | 10.8% |
| Electronic / Dance 缺少证据占比 | 95.4% | 14.8% |
| Hip-Hop / Rap 置信层级 | low | medium |
| Hip-Hop / Rap 的 LLM 占比 | 69.2% | 20.6% |
| Hip-Hop / Rap 缺少证据占比 | 73.8% | 25.9% |

两个标签的 `llm_majority` 高风险告警均已消失。Electronic / Dance 时长从
68.9 小时调整为 72.7 小时，Hip-Hop / Rap 从 47.3 小时调整为 40.1 小时；
变化来自保守修正 artist-level 标签范围，而不是播放记录变化。

## 数据安全与可恢复性

- 审核前备份：`/tmp/spotify_stats_before_genre_quality_audit_20260716.db`
- dry-run：15 条可批准、0 条遗留 open review、`PRAGMA integrity_check=ok`
- 正式写入：15 条 approved，全部记录审核人和 HTTPS 证据
- 幂等复跑：0 条新增批准、0 条重复来源、0 条遗留 open review

## 剩余边界

本轮后两个目标标签仍为 medium，而不是 high。原因是统计系统有意把
external consensus 作为需保守解释的来源层；这不是待补数据错误。剩余无链接
LLM 时长已降至较低水平，后续仅在单个艺人播放时长明显上升或 Settings 再次
出现 `llm_majority` 时继续审核，不应为消除所有 warning 无限扩张人工标签。
