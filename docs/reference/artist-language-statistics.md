# 艺人语言事实与统计规则

## 适用范围

本文约束艺人语言事实、播放语言统计、Settings 审核和年度总结消费层。它补充
[`2026-07-04-artist-genre-taxonomy.md`](2026-07-04-artist-genre-taxonomy.md)，语言事实不从 genre、地区、国籍或艺人名称推断。

## 当前规则

- 语言事实以稳定 `artist_id` 为主体，和 genre 解析、展示 taxonomy 分开治理。
- 播放语言统计只按 `tracks.artist_id` 的主艺人归属计算，不对 featured artist 做 fan-out。
- 只有具备证据、审核人和审核说明的 approved fact 才能进入正式统计和年度缓存。
- legacy 数据、LLM 建议和未审核 seed 只能进入 suggested/review 流程，不能自动批准。
- 消费层必须保留 `unknown`、`multilingual`、`instrumental` 和未归属时长，不使用名称启发式补齐。
- Settings 可以展示来源、证据、置信度、覆盖率和审核历史；年度总结只展示普通用户可理解的语言分布。
- 语言事实修订必须进入对应 metadata revision，并使年度报告和相关缓存按完整 revision 失效。

## 相关实现与证据

- 领域实现：`backend/domains/metadata/artist_languages.py`
- 审核实现：`backend/domains/metadata/artist_language_review.py`
- 早期设计与实施过程：`docs/archive/06-productization-closeout/`
- 预审与来源审核：[`../reports/2026-07-15-genre-language-pre-review-execution.md`](../reports/2026-07-15-genre-language-pre-review-execution.md)、[`../reports/2026-07-16-genre-source-quality-audit.md`](../reports/2026-07-16-genre-source-quality-audit.md)
