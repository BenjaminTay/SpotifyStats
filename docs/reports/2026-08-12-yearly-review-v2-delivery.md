# 年度总结 V2 完整重构交付报告

日期：2026-08-12
状态：**PASS，内容重构与 M0–M6 验收全部完成**
实施依据：[`../designs/2026-08-12-yearly-review-v2-content-data-contract.md`](../designs/2026-08-12-yearly-review-v2-content-data-contract.md)
执行计划：[`../plans/2026-08-12-yearly-review-v2-rebuild-plan.md`](../plans/2026-08-12-yearly-review-v2-rebuild-plan.md)

## 1. 最终结论

`/yearly-review` 的 Desktop/Compact 自定义年度总结已由旧模块平铺重建为确定性的八章个人音乐年鉴。新报告包含：

1. 报告护照与年度头条。
2. 播放次数、有效时长与个人 Billboard 双视角荣誉。
3. 唯一年度赛季时间线与可展开十二月事实账本。
4. 陪伴、沉迷、深听、发现与回归关系。
5. 收听生活与行为事实。
6. 年度纪录精选与完整分页目录。
7. 主曲风、地区流行、语言和发行年代迁移。
8. 同比、个人历史参照、完整年度索引与方法说明。

所有解释性内容都由结构化事实、coverage 与版本化策略生成，不调用 LLM。Phone presentation 继续使用 V1，官方 Wrapped 继续读取官方导入数据；两条保留链路均未被 V2 替换或改写。

## 2. 范围与不变量

### 已交付

- `YearlyReviewV2` Pydantic 契约、统一过滤上下文与 Coverage Passport。
- 播放双榜、个人 Billboard、两类纪录、时间与品味适配器。
- 八章确定性内容 builder 和共享 Orchestrator。
- 修订感知缓存、三条只读 API 和完整纪录服务端分页。
- Desktop/Compact 年鉴体验、长加载、错误/空态和附录下钻。
- API/OpenAPI、真实数据、五档视口和 Chromium/Firefox/WebKit 门禁。

### 明确未改

- Phone V1 年度总结。
- 官方 Wrapped。
- AI 年报与 Power Score。
- 原始 `plays`、`tracks`、`track_artists` 或数据库 schema。
- 分享长图/PDF、年度播放列表、全球 percentile 与跨用户比较。

## 3. M0：真实数据审计与策略冻结

### 3.1 审计口径

审计命令：

```bash
.venv/bin/python scripts/audit_yearly_review_v2.py \
  --years 2023,2024,2025 \
  --merge-level 2 \
  --json-output /tmp/yearly_review_v2_audit.json
```

统一参数：`min_ms=30000`、`music_only=true`、连续播放合并、动态阈值、L2、排除精选集、Billboard 周五 12:00 起算、歌曲/专辑/艺人 Top N 为 30/20/20。脚本只读复用现有有效播放、canonical track、album project、有效艺人署名、Year-End、播放纪录和 consumer taste taxonomy。

### 3.2 三年内容容量

| 年份 | 有效播放 | 有效时长 | 活跃日 | 歌曲 | 专辑项目 | 艺人 | Billboard |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2023 | 13,085 | 784.50h | 359 | 1,608 | 432 | 417 | 52/52，complete |
| 2024 | 18,360 | 1,201.19h | 355 | 2,507 | 540 | 457 | 52/52，complete |
| 2025 | 17,567 | 1,134.97h | 364 | 2,754 | 623 | 440 | 52/52，complete |

三年均能稳定提供播放榜 50/30/30、个人 Billboard 50/30/30 和 12 项 Year-End honors。播放榜与 Year-End 的匹配歌曲名次差中位数为 5–8、P75 为 10–13；因此双榜差异门槛冻结为歌曲至少 10 名、专辑/艺人至少 5 名。

播放纪录每年有 69–70 个非空叶节点和 2,173–2,268 个候选，问题不是内容不足，而是必须去重和限制垄断。三年都有完整十二个月；榜首易主正文最多三个，每月最多一个节点，只有持续至少两个月的变化才形成阶段边界。

关系候选按年内有效播放至少 10 次建立。正式规则要求：新关系在报告年首次出现，至少 10 次、3 个活跃日和 30 天跨度；真正回归在报告年前已有播放，沉寂至少 180 天，回归后至少 10 次和 3 个活跃日。三年均有充足候选。

### 3.3 品味覆盖与策略版本

| 年份 | 主曲风已知 | 地区流行已知 | 语言已分类 | 发行年代已知 |
| --- | ---: | ---: | ---: | ---: |
| 2023 | 92.43% | 8.77% | 98.01% | 100.00% |
| 2024 | 92.47% | 42.49% | 98.71% | 100.00% |
| 2025 | 92.29% | 48.12% | 98.65% | 99.77% |

coverage gate 冻结为：至少 70% 可生成核心结论，40%–69.99% 只能辅助观察，低于 40% 不生成迁移结论。版本化策略为：

- `relationship_policy_v1`：关系资格、证据与角色配额。
- `highlight_policy_v1`：纪录去重、评分与多样性。
- `season_stage_v1`：6–10 个转折节点、3–5 个可成立阶段及降级。

## 4. M1：契约、过滤上下文与 Coverage Passport

`backend/models/yearly_review.py` 定义 `schema_version=yearly_review_v2` 的固定顶层响应，包含 `complete/year_to_date/observed_range/insufficient/empty` 五种状态、A/B/C 证据等级、充分/有限/不可用 coverage 和全部章节的合法空态。

一次请求由 `YearlyReviewFilterContext` 统一解析：

- 有效阈值、音乐过滤、连续播放合并、动态阈值。
- L1/L2/L3、精选集设置。
- 三类 Billboard Top N 与周边界。
- display taxonomy、艺人元数据、artist identity、有效署名 revision。
- track group 与 album project 内容 revision。

fingerprint 使用版本化、排序稳定的 canonical JSON + SHA-256；任一语义参数或 revision 改变都会分流缓存，字典插入顺序不影响结果。

Coverage Passport 分开记录：

- Play 首末日期、自然日跨度、活跃日、导入覆盖和内部缺口。
- Billboard 直接适配 Year-End meta，不重猜周完整性。
- Comparison 检查上一年是否覆盖同一对齐窗口，不可比时给原因而非伪 `0%`。
- Taste 使用 M0 冻结门槛。

即使自然年首末日期完整，`internal_gap_status=unknown` 也独立保留，不能生成“最长未听歌空窗”等不可核验结论。

## 5. M2：现有数据能力适配

### 5.1 播放双榜

- 歌曲沿用 canonical track key。
- 专辑沿用 album project identity。
- 艺人沿用 effective track credits fan-out 与 canonical artist identity。
- 每类同时输出 `by_plays` 和 `by_hours`，保留播放、时长、份额、活跃日/月、本地首末日期与详情链接。
- 正文候选上限为歌曲 50、专辑 30、艺人 30，并保留完整可用实体数。

### 5.2 个人 Billboard 与两类纪录

Year-End 不修改 Score 或 Power Score，原样保留 `semantics_version`、coverage、honors 与年榜事实。专辑用 canonical name + artist 对齐 album project；无法对齐时保留显式 fallback identity。Billboard records 固定使用整数年份范围 `[year, year]`。

两类纪录统一为 `YearlyHighlightCandidate`：稳定 ID、来源、family、record key、category、fact type、实体、primary metric、JSON-safe 原始值、evidence grade、source refs 和 deep link。播放记录保留六族，Billboard records 归入 championship、longevity、endurance、movement、hall_of_fame、self_replacement_blocker、market、quirky 八族。

### 5.3 时间与品味

日、小时、星期、月、累计与行为事实复用播放统计 service；taste 只调用 `build_consumer_taste_profile()`，不复制 genre/language resolver。切片固定为 Q1–Q4、上半年、下半年，空季度也保留合法空态。

真实 2025 探针得到 2,754 首歌曲、623 个专辑项目、440 位艺人；Year-End 为 `year_end_v3`、52/52 周、50/30/30 行，专辑 project 对齐 30/30；Billboard/播放纪录内部候选分别为 976/2,257。

## 6. M3：确定性内容编排

内容 builder 将结构化事实编排为八章，且不重新计算另一套榜单、元数据或纪录：

- 护照只陈述观察范围、状态与核心指标；头条最多三条并按主题去重。
- 播放次数、有效时长和个人 Billboard 并列；不完整年榜只称“阶段领先”。
- 每个月在正文事实表中只出现一次；转折受月份唯一、事件配额和总量约束。
- 每条解释性关系至少有两个指标，同一实体最多承担两个角色。
- 收听生活使用归一化工作日/周末、时段、复听、探索、集中度和平台事实。
- 纪录先资格过滤与语义去重，再按幅度、持续性、历史稀有度、比较、具体性和证据质量评分。
- style、scene、language、release era 独立处理；unknown 进入分母，迁移需同时满足份额变化与具名驱动证据。

真实 2025 报告生成 6 项护照指标、3 条头条、12 项 Year-End honors、6 条双榜分歧、12 个月事实、10 个转折节点、12 条关系、14 项生活指标和 12 条精选纪录。3,233 条纪录输入经资格/去重后保留 2,364 条公开目录候选。

品味方面，style 92.29%、language 98.65%、release era 99.77% 可形成核心观察；scene 48.12% 只作辅助。最终只生成有驱动证据的 Pop 与 2010s 份额变化，不用覆盖不足的 scene 编故事。

## 7. M4：共享编排、API 与缓存

### 7.1 共享加载与降级

每份报告只加载一次完整有效播放 frame，只构建一次 track/album/artist entity frames，并从共享结果切出本年、上年和半年窗口。一个 Billboard source 同时服务 honors、season、records 与 appendix。

核心统计主干失败正常暴露；非关键章节单点失败写入 `methodology.limitations` 并降级为合法空章。空年份不会计算全历史实体、Billboard 或纪录；真实 2099 空报告冷态约 765ms。

### 7.2 缓存与失效

`yearly_review` 命名空间缓存内部 artifact，主报告和完整公开纪录目录共用。缓存键包含：年份、filter fingerprint、三项策略版本、`year_end_v3`、display taxonomy、艺人/语言/身份/署名/track group/album project revisions 及 SQLite main/WAL revision。

导入、身份/署名 rebuild、统计设置、版本归并、album project 重建、genre approve 与 language review decision 都会使年度缓存失效。

### 7.3 API

```text
GET /api/yearly-review/available-years
GET /api/yearly-review/{year}
GET /api/yearly-review/{year}/records?page=1&page_size=50
```

三条 endpoint 均有 Pydantic response model；年份 2000–2100，页大小 1–100。主响应只含精选纪录和目录计数，完整纪录由相同过滤指纹下的服务端分页接口提供。空年份返回合法 `empty` payload，`X-Request-ID` 继续由全局 middleware 处理。

## 8. M5：Desktop/Compact 年鉴体验

### 8.1 数据链路

前端新增 V2 类型、query hook、章节 feature 和编辑部年鉴样式。Query 参数完整继承分析设置，query key 使用稳定过滤上下文，后端 `filter_fingerprint` 作为报告身份与组件重置边界。

主报告和完整纪录 timeout 为 120 秒；首次生成显示阶段性等待文案与已等待秒数，不伪造百分比。切换年份不会把上一年 placeholder 错显为当前年。

### 8.2 展示与边界

Desktop/Compact 使用暖奶油纸张、深色唱片封面、期刊编号和不对称编辑排版。没有恢复旧“听歌人格”，完整附录每页 10 行，完整纪录每页 20 条。

`YearlyReviewPage` 互斥启用：

- `<768px`：V1 available years、`/wrapped/{year}/full` 与 `CustomSummary`。
- `>=768px`：V2 available years、`/yearly-review/{year}` 与 V2 experience。
- Official tab：`/wrapped-hub/available-years` 与原 `OfficialWrapped`。

年份保留在 URL，切换 presentation/tab 时投影到目标数据源的合法年份。

### 8.3 浏览器阶段修复

- 消除 Records/Appendix 重复 React key。
- 去除可点击纪录卡与实体深链的嵌套 `<a>`。
- 纪录目录数量改用 `input_total`，不再把重叠 family counts 相加。
- Spotify 封面失败时显示实体首字母占位。

## 9. M6：最终验证与性能

### 9.1 后端与 API

| 门禁 | 结果 |
| --- | --- |
| Yearly V2 unit + contract | 79 passed |
| Wrapped / Year-End / playback records 回归 | 28 passed |
| 全量 unit | 1,043 passed |
| 全量 contract | 329 passed |
| OpenAPI operation audit | 185 operations，0 unaccounted |
| OpenAPI parameter audit | 85 obligations，0 unaccounted |
| API smoke | 119/119；118 GET covered + 13 excluded；0 unaccounted |

API smoke 已纳入 available-years、空年份主报告与分页 records；真实年份由专用 probe 负责，避免广域 smoke 重复触发高成本计算。

### 9.2 四年真实数据与预算

| 年份 | 状态 | 冷响应 | 热响应 | JSON | 完整纪录目录 |
| --- | --- | ---: | ---: | ---: | ---: |
| 2023 | complete | 79.62s | 2.73ms | 236,380 B | 3,140 |
| 2024 | complete | 82.47s | 2.64ms | 243,453 B | 3,246 |
| 2025 | complete | 80.94s | 3.44ms | 241,111 B | 3,233 |
| 2026 | year_to_date | 76.27s | 2.78ms | 226,609 B | 2,979 |

冻结预算为未压缩主 JSON 不超过 512 KiB、热响应不超过 250ms；四年全部通过。2026 响应 gzip 为 27,805 B。

冷态 76–82.5 秒，设置变更后一次预热 88.33 秒，仍是明确性能债。它可能触发 WebKit/开发代理首请求超时；跨浏览器功能验收使用预热缓存和 `--api-base-url` 直连后端。下一阶段应通过共享中间结果、阶段缓存或后台预计算解决，不能放宽 API 错误门禁冒充优化。

### 9.3 前端门禁

| 门禁 | 结果 |
| --- | --- |
| Vitest | 62 files / 475 tests passed |
| TypeScript + Vite production build | PASS |
| 本次变更文件 ESLint | PASS |
| 年度 route matrix | 360/390/430/768/1280，5/5 PASS，0 overflow/error |
| control inventory | 15 routes × desktop/mobile；1,533 controls；283 touch targets；0 violation |
| Chromium / Firefox / WebKit | route markers + 七组 core interactions 全部 PASS |

年度交互覆盖荣誉 Tab、十二月账本、品味轴切换、纪录/附录分页、Official Wrapped 隔离、实体详情深链与浏览器返回。全仓 `npm run lint` 仍有 181 个既有错误，主要位于旧 Billboard 类型、AI、Settings 与共享 UI；本次年度文件定向 ESLint 为 0 error。

## 10. 交付文件地图

核心后端：

- `backend/models/yearly_review.py`
- `backend/domains/yearly_review/`
- `backend/services/yearly_review_service.py`
- `backend/api/yearly_review.py`

核心前端：

- `frontend/src/types/yearly-review-v2.ts`
- `frontend/src/hooks/useYearlyReviewV2.ts`
- `frontend/src/features/yearly-review/`
- `frontend/src/pages/YearlyReviewPage.tsx`

审计与验证：

- `scripts/audit_yearly_review_v2.py`
- `scripts/yearly_review_v2_probe.py`
- `backend/tests/unit/test_yearly_review_*.py`
- `backend/tests/contract/test_yearly_review_v2_contract.py`
- `frontend/src/tests/yearly-review-v2.test.ts`

## 11. 发布、回滚与后续

M6 后不建立长期 feature flag 双轨。V2 只在 Desktop/Compact presentation 分支挂载；如需回滚，只恢复 `YearlyReviewPage` 的桌面 V1 分支，V2 只读 API/domain 可以保留，不触碰 Phone V1、Official Wrapped 或数据库。

后续独立方向按优先级为：

1. 冷态性能剖析、阶段缓存与后台预热。
2. 真实内容人工复核。
3. Phone V2 presentation。
4. 分享/PDF、年度播放列表和 AI 编辑导语。

其中只有冷态性能是当前明确的产品体验债；其余均不影响本次内容重构完成。
