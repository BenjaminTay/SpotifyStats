# 年度总结 V2 完整重构实施计划

日期：2026-08-12
依据：[`../designs/2026-08-12-yearly-review-v2-content-data-contract.md`](../designs/2026-08-12-yearly-review-v2-content-data-contract.md)
状态：完成（M0–M6 已于 2026-08-12 完成）

## 1. 目标

把 `/yearly-review` 的自定义年度总结从旧模块平铺，重建为一份确定性、可追溯、可下钻的个人音乐年鉴。

完成后，桌面年度总结必须同时包含：

- 报告护照与三条年度头条。
- 播放排行与个人 Billboard 年榜的双视角荣誉。
- 唯一年度赛季时间线。
- 关系故事。
- 收听生活。
- 年度纪录精选。
- 品味迁移。
- 同比、个人历史参照和完整年度索引。

官方 Wrapped、Phone presentation、Power Score 和 AI 年报不属于本次实现范围。

## 2. 交付边界

### 本计划交付

- `YearlyReviewV2` 后端契约和 domain。
- `GET /api/yearly-review/{year}`。
- 必要的 available-years 和分页 records endpoint。
- 完整过滤指纹、coverage、缓存和 revision。
- Desktop/Compact 年度总结 V2 experience。
- 旧 V1 兼容与 Phone 保留。
- 定向测试、contract、真实数据 probe、桌面 browser smoke。
- 文档地图、规则和项目提示同步。

### 本计划不交付

- Official Wrapped 改动。
- Phone V2 设计或实现。
- 分享长图、PDF、社交比较或播放列表。
- LLM 导语或年度长文。
- 新的 Power Score 公式。
- 全球 percentile、社区总体或主流度。

## 3. 总体阶段

| 阶段 | 名称 | 产物 | 完成后状态 |
| --- | --- | --- | --- |
| M0 | 数据与策略冻结 | 真实分布审计、阈值策略、字段清单 | 可安全编码 |
| M1 | 契约与共享上下文 | V2 models、filter context、coverage | 新域骨架成立 |
| M2 | 现有能力适配 | 播放榜、Billboard、records、taste adapters | 数据源统一 |
| M3 | 内容编排 | honors、season、relationships、life、records、taste | 后端报告完整 |
| M4 | API 与缓存 | orchestrator、endpoint、cache、OpenAPI | 后端可消费 |
| M5 | 桌面前端重建 | V2 experience、章节、附录、降级 | 页面内容替换 |
| M6 | 验证与收口 | probes、测试、smoke、文档 | 内容重构完成 |

M1–M5 不允许跨过 M0 的阈值审计直接写解释性故事。

当前状态：**M0–M6 已于 2026-08-12 全部完成。** 全阶段交付、真实数据性能与剩余边界统一见 [`../reports/2026-08-12-yearly-review-v2-delivery.md`](../reports/2026-08-12-yearly-review-v2-delivery.md)。

## 4. M0：数据与策略冻结

### Task 0.1：建立年度真实数据审计脚本

**新增：**

- `scripts/audit_yearly_review_v2.py`

**输出：**

- 2023–2025 每年报告覆盖状态。
- 播放量与时长 Top 50/30/30。
- 个人 Billboard Top 50/30/30 和 honors。
- 播放记录各类别候选数量、分布和重复程度。
- 月度播放、榜首、新发现、回归和行为变化候选。
- 关系故事候选的跨度、活跃月、峰值集中度和榜单差异分布。
- 曲风、scene、语言、年代覆盖和季度差异。
- 可比上年和不可比年份清单。

支持：

```bash
.venv/bin/python scripts/audit_yearly_review_v2.py \
  --years 2023,2024,2025 \
  --merge-level 2 \
  --json-output /tmp/yearly_review_v2_audit.json
```

审计脚本只读，不写数据库。

**执行结果（2026-08-12）：完成。** 三个自然年均有 12 个月和 52/52 Billboard 周；每年可用播放排行实体为歌曲 1,608–2,754、专辑 432–623、艺人 417–457，纪录候选为 2,173–2,268 条。原始审计输出位于 `/tmp/yearly_review_v2_audit.json`，持久摘要见完整交付报告第 3 节。

### Task 0.2：冻结版本化策略

根据审计结果确定：

- `relationship_policy_version`。
- `highlight_policy_version`。
- 转折点资格和年度阶段边界策略。
- 各类最小样本。
- 正文各类别数量上限。
- 不完整年份降级条件。

要求：

- 阈值必须附数据分布依据。
- 至少检查 3 个完整或可用年份。
- 不以 2025 单年样本拍板。
- 规则写入测试 fixture，不把魔法数字散落在组件中。

**执行结果（2026-08-12）：完成。** 已冻结：

- `relationship_policy_v1`。
- `highlight_policy_v1`。
- `season_stage_v1`。
- 品味覆盖门槛：≥70% 核心结论、40%–69.99% 次要观察、<40% 只提示覆盖不足。
- 非完整年份和不足 90 天报告的关系/阶段降级规则。

完整阈值、候选数量和选择约束以内容数据契约与完整交付报告第 3 节为准。

### Task 0.3：记录现有回归基线

执行并保存摘要：

```bash
git status --short
.venv/bin/pytest backend/tests/integration/test_wrapped_full.py -q
cd frontend && npm test -- --run src/tests/yearly-language-distribution.test.tsx
cd frontend && npm run build
```

记录：

- Official Wrapped 行为。
- Phone V1 年度总结 marker。
- Desktop V1 年度总结 marker。
- 当前 `/wrapped/{year}/full` contract。

**执行结果（2026-08-12）：完成。**

- 后端旧年度集成测试：12 passed。
- 前端年度语言分布测试：5 passed。
- 前端 production build：PASS；仅保留既有大 chunk warning。
- Official Wrapped 仍懒加载并读取 `/wrapped-hub`。
- Phone V1 仍使用 `MobileYearlyChapterNav` + `CustomSummary` Phone 分支。
- Desktop V1 仍使用 `CustomSummary` 非 Phone 分支。
- `/wrapped/{year}/full` 仍声明 `WrappedFullResponse`。

## 5. M1：契约与共享上下文

### Task 1.1：新增 V2 API models

**新增：**

- `backend/models/yearly_review.py`
- `backend/tests/unit/test_yearly_review_models.py`

模型至少包含：

- `YearlyReviewResponse`
- `YearlyReviewFilterContext`
- `YearlyReviewCoverage`
- `YearlyReportPassport`
- `YearlyHeadline`
- `YearlyHonorsChapter`
- `YearlySeasonChapter`
- `YearlyRelationshipStory`
- `YearlyListeningLifeChapter`
- `YearlyFeaturedRecord`
- `YearlyTasteMigrationChapter`
- `YearlyEpilogue`
- `YearlyAppendix`
- `YearlyMethodology`

所有可变列表使用 `Field(default_factory=list)`，不得使用共享可变默认值。

测试锁定：

- `schema_version=yearly_review_v2`。
- 必填 coverage 和 filter context。
- 不完整章节的合法空态。
- JSON schema 中的枚举和 nullable 字段。

**执行结果（2026-08-12）：完成。** 已新增完整 `YearlyReviewResponse` 章节模型，锁定 `schema_version=yearly_review_v2`、必填 context/coverage、五种报告状态、合法空章节和独立可变默认值；5 个模型测试通过。

### Task 1.2：建立统一 Filter Context

**新增：**

- `backend/domains/yearly_review/context.py`
- `backend/tests/unit/test_yearly_review_context.py`

**修改：**

- `backend/dependencies.py`

实现：

- 从一次请求解析全部播放、Billboard 和合并设置。
- 生成稳定 `filter_fingerprint`。
- 暴露给所有 builder，不允许章节自行读取 Settings。
- 包含 taxonomy、artist metadata、track credit、album project revision。

测试：

- 任意语义参数变化都会改变 fingerprint。
- 参数顺序和字典顺序不改变 fingerprint。
- 与现有 Settings 默认值一致。
- Phone V1 仍使用旧 dependency，不受影响。

**执行结果（2026-08-12）：完成。** 已新增 `YearlyReviewFilters` 和 `get_yearly_review_context`，一次解析播放/Billboard/合并设置；fingerprint 纳入 taxonomy、artist metadata/identity、track credit、track group 和 album project revision。16 个测试及真实 SQLite probe 通过，旧 `PlayFilters` 未改。

### Task 1.3：建立 Coverage Passport

**新增：**

- `backend/domains/yearly_review/coverage.py`
- `backend/tests/unit/test_yearly_review_coverage.py`

实现：

- play coverage。
- Billboard coverage adapter。
- comparison coverage。
- taste coverage。
- `complete/year_to_date/observed_range/insufficient/empty` 状态。

必须区分：

- 首末播放日期。
- 自然日跨度。
- 活跃日。
- 已证明的导入覆盖。
- 无法确认的内部缺口。

测试至少包含：

- 完整年度。
- 当年截至某日。
- 年初缺失。
- 年中内部缺口未知。
- 无 Billboard 周。
- 上年不可比。
- genre/language unknown 较高。

**执行结果（2026-08-12）：完成。** 已实现四类 Coverage Passport 和五种顶层状态；完整年、YTD、观察区间、短样本、空数据、已证实内部缺口、Billboard 缺周、不可比基线和 taste coverage gate 共 10 个测试通过。

## 6. M2：现有能力适配

### Task 2.1：播放排行 Adapter

**新增：**

- `backend/domains/yearly_review/play_rankings.py`
- `backend/tests/unit/test_yearly_review_play_rankings.py`

复用：

- `analysis/charts` 对应 domain/service。
- canonical track keys。
- album project identity。
- effective track credits 和 canonical artist identity。

产出：

- track Top 50。
- album Top 30。
- artist Top 30。
- plays、hours、share、active days/months、first/last date。
- plays 与 hours 两种排序所需字段。

不从 HTTP endpoint 内部调用 HTTP；直接复用 domain/service 函数。

**执行结果（2026-08-12）：完成。** 已建立播放次数/有效时长双榜，固定歌曲 Top 50、专辑 Top 30、艺人 Top 30；输出 share、活跃天/月和首末本地日期，并分别沿用 canonical track、album project、有效署名和 canonical artist 归属。真实 2025 数据可用实体为 2,754 / 623 / 440，双榜行数均符合上限。

### Task 2.2：个人 Billboard Adapter

**新增：**

- `backend/domains/yearly_review/billboard_adapter.py`
- `backend/tests/unit/test_yearly_review_billboard_adapter.py`

复用：

- `compute_year_end_staged()`。
- Year-End coverage。
- Year-End honors。
- Billboard records 年度范围计算。

要求：

- 不修改 Power Score。
- 不从年榜 Top N 反推实体存在资格。
- 专辑按 album project identity 对齐播放排行。
- 艺人经过有效署名与 identity canonicalization。
- 记录原始 `semantics_version`。

**执行结果（2026-08-12）：完成。** 已原样复用 `compute_year_end_staged()` 的 `year_end_v3` 计分、coverage 和 honors，并把专辑行补齐为 album project identity；真实 2025 数据为 52/52 周、50/30/30 行，30 个年榜专辑全部解析到 project。年度 Billboard records 已压为 976 个内部候选并归入八个既有 record family。records 源暂不接受 `include_compilations`，adapter 会显式返回 alignment/limitation，不伪装为完整支持。

### Task 2.3：播放记录 Adapter

**新增：**

- `backend/domains/yearly_review/playback_records_adapter.py`
- `backend/tests/unit/test_yearly_review_playback_records_adapter.py`

复用：

- `compute_playback_records()` 或其稳定 service 层。
- 年度 custom range。
- 六大 records family。

要求：

- 只在服务内部使用完整 records 数据。
- 不把约 2,000 行原始记录塞进主响应。
- 转换为统一 `YearlyHighlightCandidate`。
- 保留 source family、record key、原始值、资格和 deep link。

**执行结果（2026-08-12）：完成。** 新增内部 `YearlyHighlightCandidate`，保留稳定 candidate ID、六大 source family、record key、原始值、来源、结构资格、实体引用和下钻链接。真实 2025 年 2,257 条候选全部只停留在 adapter 内部，尚未进入 `YearlyReviewResponse` 主契约。

### Task 2.4：Taste 与时间统计 Adapter

**新增：**

- `backend/domains/yearly_review/stats_adapter.py`
- `backend/tests/unit/test_yearly_review_stats_adapter.py`

复用：

- 日、小时、星期、月分布。
- taste profile。
- `consumer_v1` display taxonomy。
- language distribution。

新增稳定的季度与年初/年末切片，但不复制 genre/language resolver。

**执行结果（2026-08-12）：完成。** 复用播放统计的日/小时/星期/月/行为函数与 `build_consumer_taste_profile()`；统一生成 Q1–Q4、上半年、下半年六个稳定切片，继续使用 `consumer_v1` 和 approved language 解析链。真实 2025 年 12 个月及六个切片均完整生成。

## 7. M3：内容编排

### Task 3.1：报告护照与 Headlines

**新增：**

- `backend/domains/yearly_review/passport.py`
- `backend/tests/unit/test_yearly_review_passport.py`

实现：

- 报告状态和核心 KPI。
- 上年或上年同期总量变化。
- headline 候选生成。
- 固定规则选出最多 3 条不同主题 headline。

禁止：

- 无基线时填 `100%`。
- 把空字段写成零变化。
- 生成没有数值依据的年度人格。

**执行结果（2026-08-12）：完成。** 报告护照统一承载范围、状态与六项核心指标；头条选择固定最多三条且按主题去重。无可比基线时不生成百分比变化，空值不被伪装为零变化。

### Task 3.2：双视角年度荣誉

**新增：**

- `backend/domains/yearly_review/honors.py`
- `backend/tests/unit/test_yearly_review_honors.py`

实现：

- 播放冠军。
- 个人 Billboard 冠军。
- 12 项 Year-End honors 标准化。
- 双榜实体匹配。
- 播放榜与 Billboard 排名差异故事。

测试：

- 同一实体双榜相同，不生成无意义差异故事。
- 播放 #1 与年榜 #1 不同，生成可解释差异。
- 专辑版本归并不产生错误的两条专辑。
- 不完整年榜将“年度冠军”降级为“阶段领先”。

**执行结果（2026-08-12）：完成。** 同时保留播放次数、有效时长与个人 Billboard 三套荣誉视角，标准化 12 项 Year-End honors，并生成双榜一致/分歧事实；不完整年榜统一降级为“阶段领先”。

### Task 3.3：唯一年度赛季时间线

**新增：**

- `backend/domains/yearly_review/season.py`
- `backend/tests/unit/test_yearly_review_season.py`

实现：

- 唯一 12 月事实表。
- 月度播放冠军与个人 Billboard 冠军。
- 月间变化和上年同月对比。
- 转折候选。
- 3–5 个年度阶段。
- 6–10 个最终转折节点。

硬测试：

- 每个月只出现一次。
- `monthly_pulse` 与 `monthly_drilldown` 不再形成两套输出。
- 无数据月份保留空态但不产生虚假转折。
- 榜首易主、探索峰值、回归、专辑时代等事件可复现。
- 阶段边界由确定性规则生成。

**执行结果（2026-08-12）：完成。** 只生成一张 12 月事实表；转折事件按月份、类型和总数去重限额，真实 2025 数据选择出 10 个节点。阶段只有在连续月模式稳定时才生成，未满足条件时合法为空，不强行切段。

### Task 3.4：关系故事

**新增：**

- `backend/domains/yearly_review/relationships.py`
- `backend/domains/yearly_review/policies.py`
- `backend/tests/unit/test_yearly_review_relationships.py`

实现已冻结的：

- 主线艺人。
- 专辑时代。
- 长期陪伴。
- 短期着迷。
- 慢热作品。
- 新关系。
- 旧爱回归。
- 被低估作品。
- 深度专辑聆听。

要求：

- 每条解释性关系至少引用两个独立 A/B 指标。
- 同一实体最多占两个不同关系角色。
- 类别无合格候选时返回空，不用低质量候选填满。
- 专辑完成和完整回放使用可靠 album project track membership。

**执行结果（2026-08-12）：完成。** 已实现九类关系候选及 `relationship_policy_v1`，每条入选故事至少有两个结构化指标，同一实体最多承担两个角色；真实 2025 数据生成 12 条合格关系故事。

### Task 3.5：收听生活

**新增：**

- `backend/domains/yearly_review/listening_life.py`
- `backend/tests/unit/test_yearly_review_listening_life.py`

实现：

- 主要时段。
- 工作日/周末差异。
- 深夜比例与同比。
- 活跃连续期。
- 单曲循环、专辑沉浸、艺人集中度。
- 探索率和复听率。
- 可选平台使用事实。

没有导入 coverage 证据时，不计算或不解释“最长空窗”。

**执行结果（2026-08-12）：完成。** 收听生活输出 14 项结构化指标和 7 条可解释观察，覆盖时段、工作日/周末、深夜、集中度、复听、探索和平台；没有导入连续性证据时不推断沉默期。

### Task 3.6：年度纪录筛选器

**新增：**

- `backend/domains/yearly_review/records.py`
- `backend/tests/unit/test_yearly_review_records.py`

实现：

- 多来源候选合并。
- eligibility filter。
- semantic deduplication。
- noteworthiness scoring。
- category/entity diversity caps。
- 8–12 条最终精选。

测试 fixture 必须覆盖：

- 同一事实从 special moment 和 playback records 重复出现。
- 同一艺人占据多个类别。
- 极值很大但样本不足。
- 个人历史纪录与单年极值冲突。
- 不完整年份无法生成特定纪录。
- 无候选时保持空态。

**执行结果（2026-08-12）：完成。** `highlight_policy_v1` 已实现资格过滤、语义去重、分量归一化评分、类别/实体/指标配额和 8–12 条选择；真实 2025 候选池 3,233 条，去重后 2,364 条，最终精选 12 条且无类别或实体垄断。

### Task 3.7：品味迁移

**新增：**

- `backend/domains/yearly_review/taste_migration.py`
- `backend/tests/unit/test_yearly_review_taste_migration.py`

实现：

- style、scene、language、release era 四个独立维度。
- 季度或年初/年末变化。
- 上年同期变化。
- 变化驱动艺人/作品。
- unknown 和 coverage。
- 单一艺人驱动与结构性迁移区分。

禁止：

- 恢复 Music Map heuristic。
- 将 `context/role` 放入消费主图。
- genre 推断 language。
- 低覆盖时输出强确定迁移结论。

**执行结果（2026-08-12）：完成。** style、scene、language、release era 独立计算覆盖与迁移，并用受治理艺人事实或作品发行年定位驱动。真实 2025 中 style 92.29%、language 98.65%、release era 99.77% 可形成结论；scene 仅 48.12%，因此只展示“样本有限”，不生成强迁移叙事。

### Task 3.8：终章与完整索引

**新增：**

- `backend/domains/yearly_review/epilogue.py`
- `backend/domains/yearly_review/appendix.py`
- `backend/tests/unit/test_yearly_review_appendix.py`

实现：

- 三项最重要变化。
- 新进入个人历史 Top 的实体。
- 有下一年数据时的延续实体。
- 播放榜 50/30/30。
- 个人 Billboard 年榜 50/30/30。
- 月度冠军表。
- records catalog counts 和深链。

**执行结果（2026-08-12）：完成。** 终章固定选择三项不同主题结论，并保留个人历史新高与下一年延续实体；附录完整输出播放双榜 50/30/30、个人 Billboard 50/30/30、12 月冠军表和纪录目录计数。

## 8. M4：Orchestrator、API 与缓存

### Task 4.1：共享加载与 Orchestrator

**新增：**

- `backend/domains/yearly_review/orchestrator.py`
- `backend/services/yearly_review_service.py`
- `backend/tests/unit/test_yearly_review_orchestrator.py`

要求：

- 单次请求复用同一有效播放 frame。
- 艺人 fan-out 只加载一次。
- album project membership 只加载一次或复用缓存。
- 同一 Billboard staged result 供 honors、season 和 appendix 复用。
- 各 builder 使用相同 context 和 coverage。
- 章节失败可分类降级，核心契约不因非关键章节单点失败而 500。

**执行结果（2026-08-12）：完成。** 单次报告只加载一份有效播放 frame、构建一组三类实体 frame，并让同一 Billboard source 同时服务 honors、season、records 和 appendix。统计/coverage 为核心主干；非关键章节异常会记录 `section_unavailable:*` limitation 并返回对应合法空章。空年份绕过实体、Billboard 和纪录重算，真实 2099 空报告冷态约 765 ms。

### Task 4.2：缓存与失效

**新增或修改：**

- `backend/core/cache.py`
- `backend/services/yearly_review_service.py`

缓存键至少包含：

- year。
- schema version。
- filter fingerprint。
- relationship/highlight policy version。
- Billboard semantics version。
- display taxonomy version。
- artist metadata revision。
- language revision。
- track credit revision。
- album project revision。
- database revision。

提供 cache clear registration，并纳入导入、元数据审核和归并修改后的失效路径。

**执行结果（2026-08-12）：完成。** 新增 `yearly_review` LRU 命名空间与 singleflight；缓存键包含年份、schema、过滤指纹、三类政策版本、Billboard `year_end_v3`、display taxonomy、artist/language/identity/credit/group/project 修订和 SQLite main/WAL 修订。导入既有 `invalidate_all()` 自动覆盖；Settings、版本归并、album project 重建、genre approve 和 language review decision 已显式失效年度缓存。

### Task 4.3：API Router 与 Contract

**新增：**

- `backend/api/yearly_review.py`
- `backend/tests/contract/test_yearly_review_v2_contract.py`

**修改：**

- `backend/main.py`

Endpoints：

```text
GET /api/yearly-review/available-years
GET /api/yearly-review/{year}
GET /api/yearly-review/{year}/records
```

要求：

- 所有 endpoint 有 response model。
- 非法年份返回结构化 422。
- 空年份返回合法 empty payload。
- 主响应记录精选与 catalog count。
- 完整 records endpoint 服务端分页。
- `X-Request-ID` 正常透传。

**执行结果（2026-08-12）：完成。** 三条只读 endpoint 均有 response model；主响应保留精选与目录计数，完整 records 以 1–100 条服务端分页；年份限定 2000–2100，非法年份/页码/页大小返回结构化 422，空年份返回合法 `empty` V2 payload，Request ID contract 通过。

### Task 4.4：真实数据 Contract Probe

**新增：**

- `scripts/yearly_review_v2_probe.py`

验证：

- 2023–2026 可用年份。
- 完整年、YTD、partial range。
- 章节必填字段和数量上限。
- 同一过滤指纹。
- 双榜 canonical entity 对齐。
- 8–12 条精选纪录。
- 6–10 个转折节点。
- unknown/coverage 守恒。
- 主响应 JSON 大小与热缓存响应时间。

**执行结果（2026-08-12）：完成。** `scripts/yearly_review_v2_probe.py` 已对真实 2023–2026 全量执行：2023–2025 为 `complete`，2026 为 `year_to_date`；四年共享同一过滤指纹，均为 12 个月、7–10 个转折、12 条精选纪录，无 identity 重复、unknown 丢失或覆盖守恒问题。响应 226,609–243,453 bytes，热缓存 2.73–3.24 ms；冷构建 56.6–74.8 秒，作为 M5 加载体验与后续性能优化的显式边界。

## 9. M5：桌面前端重建

### Task 5.1：类型、Query Key 和 Hook

**新增：**

- `frontend/src/types/yearly-review-v2.ts`
- `frontend/src/hooks/useYearlyReviewV2.ts`
- `frontend/src/features/yearly-review/yearlyReviewData.ts`

**修改：**

- `frontend/src/api/query-keys.ts`

要求：

- 类型与 OpenAPI contract 对齐。
- query key 包含完整 filter fingerprint。
- hook 接收 `useAnalysisFilters()` 已解析上下文。
- V1 `useYearlyReview()` 保留。
- Desktop 才启用 V2 query；Phone 不产生不必要 V2 请求。

### Task 5.2：Desktop Experience Shell

**新增：**

- `frontend/src/features/yearly-review/YearlyReviewDesktopExperience.tsx`
- `frontend/src/features/yearly-review/YearlyReviewLoadingState.tsx`
- `frontend/src/features/yearly-review/YearlyReviewErrorState.tsx`
- `frontend/src/features/yearly-review/YearlyReviewEmptyState.tsx`

**修改：**

- `frontend/src/pages/YearlyReviewPage.tsx`

行为：

- Desktop/Compact 自定义总结挂载 V2。
- Phone 自定义总结继续挂载 V1 `CustomSummary`。
- Official Wrapped 继续懒加载原组件。
- 年份选择保持 URL 状态。
- 报告状态和 filter context 改变时正确刷新。

### Task 5.3：章节组件

**新增目录：**

```text
frontend/src/features/yearly-review/
├── passport/
├── honors/
├── season/
├── relationships/
├── listening-life/
├── records/
├── taste-migration/
├── epilogue/
└── appendix/
```

组件职责：

- `passport`：报告状态、KPI、三条 headline。
- `honors`：播放冠军、个人 Billboard 冠军、双榜差异、年度荣誉。
- `season`：阶段、转折点、唯一月度展开。
- `relationships`：关系故事和证据摘要。
- `listening-life`：时段与行为对比。
- `records`：8–12 条年度精选。
- `taste-migration`：四维迁移与 coverage。
- `epilogue`：三项总结变化。
- `appendix`：分页或按需挂载完整榜单。

约束：

- 章节标题与问题所有权一致。
- 不恢复旧“听歌人格”。
- 不同时挂载月度脉搏和月度回顾。
- 每个故事提供实体或日期下钻。
- 无数据章节按契约隐藏或显示解释性空态。
- 完整长表分页，避免 500+ DOM 行。

### Task 5.4：移除桌面 V1 组合

Desktop V2 验收后，桌面不再挂载：

- `PersonalityReveal`
- `TopCharts`
- `TimeStory`
- `DiscoveryReturns`
- `ListeningDepth`
- `SpecialMoments`
- `MonthlyDrilldown`
- `YearComparison`

这些文件本阶段不删除，因为 Phone V1 仍在使用。

### Task 5.5：Smoke Markers 与可访问性

**修改：**

- `scripts/frontend_route_smoke.mjs`
- `scripts/frontend_control_inventory_smoke.mjs`
- 必要的 interaction smoke。

更新 `/yearly-review` desktop marker，不能继续要求“听歌人格”。

检查：

- 年份按钮。
- 年度总结/官方 Wrapped tabs。
- 章节导航或折叠控件。
- Entity tabs。
- 附录分页。
- 所有图表和按钮的可访问名称。

**执行结果（2026-08-12）：完成。** Desktop/Compact 已互斥挂载 V2，Phone 继续 V1，Official Wrapped 原样保留；八章年鉴、120 秒冷构建等待态、错误/空态、服务端纪录分页和客户端附录分页均已落地。真实浏览器在 Desktop/Tablet/Mobile 下均为 0 console error/warning、0px 横向溢出，control inventory 165 controls / 0 violation。完整交付与视觉验收见统一交付报告第 8 节。

## 10. M6：测试与验收

### Task 6.1：后端定向测试

至少覆盖：

```bash
.venv/bin/pytest \
  backend/tests/unit/test_yearly_review_models.py \
  backend/tests/unit/test_yearly_review_context.py \
  backend/tests/unit/test_yearly_review_coverage.py \
  backend/tests/unit/test_yearly_review_play_rankings.py \
  backend/tests/unit/test_yearly_review_billboard_adapter.py \
  backend/tests/unit/test_yearly_review_season.py \
  backend/tests/unit/test_yearly_review_relationships.py \
  backend/tests/unit/test_yearly_review_listening_life.py \
  backend/tests/unit/test_yearly_review_records.py \
  backend/tests/unit/test_yearly_review_taste_migration.py \
  backend/tests/unit/test_yearly_review_orchestrator.py \
  backend/tests/contract/test_yearly_review_v2_contract.py -q
```

并回归：

```bash
.venv/bin/pytest \
  backend/tests/integration/test_wrapped_full.py \
  backend/tests/contract/test_billboard_year_end_contract.py \
  backend/tests/unit/test_playback_records_second_phase.py -q
```

### Task 6.2：前端定向测试

**新增建议：**

- `frontend/src/tests/yearly-review-v2-contract.test.ts`
- `frontend/src/tests/yearly-review-v2-experience.test.tsx`
- `frontend/src/tests/yearly-review-v2-honors.test.tsx`
- `frontend/src/tests/yearly-review-v2-season.test.tsx`
- `frontend/src/tests/yearly-review-v2-records.test.tsx`
- `frontend/src/tests/yearly-review-v2-appendix.test.tsx`
- `frontend/src/tests/yearly-review-v2-scope.test.tsx`

验证：

- Desktop V2 / Phone V1 互斥挂载。
- Official Wrapped 不回归。
- 双榜语义标签正确。
- 月度只出现一套。
- 空态、partial、YTD 正确。
- query key 包含过滤指纹。
- 记录与完整榜单分页。

执行：

```bash
cd frontend
npm test -- --run src/tests/yearly-review-v2-*.test.tsx src/tests/yearly-review-v2-contract.test.ts
npm run build
```

### Task 6.3：真实浏览器验收

至少执行：

```bash
node scripts/frontend_route_smoke.mjs \
  --routes /yearly-review \
  --viewport desktop \
  --max-scroll-overflow 0

node scripts/frontend_control_inventory_smoke.mjs \
  --routes /yearly-review \
  --viewport desktop
```

人工桌面验收矩阵：

- 完整历史年份。
- 当前 YTD 年份。
- 无上年比较年份。
- 元数据覆盖不足年份。
- 无 Billboard 周或阶段榜年份。
- 年度总结与官方 Wrapped 切换。
- 前进/后退和年份 URL 状态。
- Entity 深链与返回。
- 附录分页和折叠状态。

### Task 6.4：性能门禁

目标：

- 单次请求不重复加载完整播放 frame。
- 主响应不包含全部 2,000+ records 行。
- 完整榜单按需渲染。
- 冷响应和热响应纳入 probe 输出。
- 主响应 gzip 后体积设定明确预算，实施时基于 probe 冻结。
- 桌面首屏不预挂载所有附录表格和重图表。

### Task 6.5：文档与项目上下文

实现完成后更新：

- `docs/README.md`
- `docs/CHANGELOG.md`
- `docs/reference/playback-stats-rules.md`
- `README.md` 的年度总结功能说明
- `AGENTS.md`
- `CLAUDE.md`
- API smoke、OpenAPI operation/parameter audit 归属

设计/计划完成但代码未实现时，不提前把 AGENTS/README 写成“已完成”。

### M6 执行结果（2026-08-12）

- 后端 Yearly V2 定向 79 passed，旧 Wrapped/Billboard Year-End/播放纪录回归 28 passed，全量 unit 1,043 passed、contract 329 passed。
- API smoke 119/119，OpenAPI 185 operations 与 85 parameter obligations 均为 0 unaccounted。
- 2023–2026 四年真实 probe 全通过；主 JSON 226–243 KiB、热响应 2.64–3.44ms，满足 512 KiB / 250ms 冻结预算。
- 前端 62 files / 475 tests、production build、变更文件 ESLint、年度五视口 route matrix、30 组 control inventory 和 Chromium/Firefox/WebKit 均通过。
- 冷态报告仍需 76–88 秒，作为后续性能债记录；不通过忽略本地 API 超时来冒充已优化。
- 完整证据与验收中修复见统一交付报告。

## 11. 发布与回滚

### 发布策略

V2 默认只对 Desktop/Compact 生效。

M6 验收后不再引入短期 feature flag，避免稳定交付后继续维护两套桌面组合。V2 只在现有 Desktop/Compact presentation 分支挂载，Phone V1 与 Official Wrapped 仍是天然隔离边界。

### 回滚边界

- 如需回滚，只恢复 `YearlyReviewPage` 的桌面 V1 presentation 分支；不触碰 Phone V1 或 Official Wrapped。
- V2 新 endpoint 和 domain 可保留，不影响旧 `/wrapped`。
- 不做数据库 destructive migration。
- 不重写原始 plays、tracks、track_artists 或 Billboard 聚合表。

## 12. 完成门禁

### P0：新骨架完成

- [x] M0 审计与策略冻结。
- [x] V2 models、filter context、coverage。
- [x] 双榜荣誉。
- [x] 唯一年度赛季时间线。
- [x] 年度纪录精选。
- [x] 完整年度索引。
- [x] V2 API、缓存和 probe。
- [x] Desktop 新骨架。

### P1：深度内容完成

- [x] 关系故事。
- [x] 收听生活。
- [x] 品味迁移。
- [x] 同比与个人历史参照。
- [x] 章节下钻、空态和 coverage 文案。
- [x] 全部定向、回归、browser 和性能门禁。

只有 P0 + P1 全部完成，才将本计划状态改为“完成”，并把旧桌面 V1 组合视为已替代。

### P2：后续独立计划

- AI 编辑导语。
- 分享卡和 PDF。
- 年度播放列表。
- 跨多年音乐生涯。
- Phone V2 presentation。

P2 不阻塞本次内容重构完成。

## 13. Git 边界

- 每个阶段先核对 dirty worktree，保护用户已有修改。
- 默认不自动提交；只有用户明确要求时才 commit。
- 提交时按“契约/后端编排/前端体验/验证文档”组织清晰批次。
- 不把临时审计 JSON、截图或 `/tmp` probe 产物加入 Git。
- 计划实施中如发现年度语义与现有规则冲突，先更新 spec 并确认，再继续编码。
