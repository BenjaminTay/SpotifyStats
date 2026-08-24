# 年度总结统计语义修复报告

日期：2026-08-24
状态：**PASS（年度总结修复范围）；项目全栈门禁为 Partial，8 个无关既有/真实数据漂移失败另列**
适用内容版本：`yearly_review_v2_14`
当前规则：[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)
设计契约：[`../designs/2026-08-12-yearly-review-v2-content-data-contract.md`](../designs/2026-08-12-yearly-review-v2-content-data-contract.md)

## 1. 问题与根因

2026 年报告出现两类可见错误：

1. `Manchild` 被描述为“个人历史累计播放在今年达到 1,000 次”，但个人历史累计早已远高于该阈值。
2. 6 月和 7 月分别被描述为“今年听歌最多的一天”，形成互相排斥的唯一结论。

这不是单条数据损坏，而是候选事实丢失统计语义造成的系统性问题：

- 里程碑在年度切片内重新从 1 累计，却使用了“个人历史”文案。
- 每日纪录把“播放次数 Top N”和“收听时长 Top N”合并枚举，并把列表序号当作名次；精选与时间线也没有要求唯一极值必须是对应指标的第一名。
- discovery 在年度切片内计算首次出现，可能把旧实体误写成第一次听到。
- 月度环比允许把当前未完整月与上一个完整月直接比较。
- 年报不同章节分别用原始 `track_id` 与 canonical track 计数；艺人占比使用 fan-out 后艺人表行数作分母。

## 2. 修复范围

- 里程碑：完整历史累计后筛选跨阈值日期，保留真实曲目 ID 与详情深链。
- 日极值：播放次数、收听时长分别 dense rank；第一名、并列第一和非第一名使用不同文案。
- 首次发现：完整历史确定歌曲、album project、canonical artist 的真实首播日期。
- 月度比较：当前未完整月的环比与同比只使用上月同期、上年同期等长窗口，并保存两侧起止日期。
- 身份与分母：歌曲类指标统一 canonical track；艺人占比改为“包含该艺人的逻辑播放数 / 年度逻辑播放总数”。
- 发布门禁：候选携带 `scope`、`rank`、`rank_basis`、并列状态、窗口与分母语义；精选、时间线和跨章节校验不再从自然语言猜测事实。
- 缓存：内容版本提升到 `yearly_review_v2_14`，策略提升到 `highlight_policy_v3` / `season_stage_v2`，旧精确键不可被新报告复用。

## 3. 自动化验证

年度总结聚焦单元、契约与里程碑兼容测试最终复验：`152 passed`。新增覆盖包括：

- 年内跨越个人历史 1,000 次阈值，且此前历史累计从 1 开始保留。
- 年度内没有跨越的旧里程碑不会重新出现。
- 日播放第一与日时长第一可落在不同日期，且各自只有第一名能使用极值文案。
- 年度切片内首次出现但历史已有的实体不会进入 discovery。
- 报告年歌曲数、新歌数、复听率与 Passport 使用相同 canonical identity。
- 未完整月份的观察窗口与比较窗口天数相等。
- 跨章节歌曲 identity 或艺人占比分母不一致时拒绝生成成品。

## 4. 真实数据与页面验收

### 4.1 四年真实重算与缓存

probe v6 使用当前默认过滤指纹对 2023–2026 绕过旧持久命中重算，四年均为 `issues=[]`：

| 年份 | 状态 | 真实重算 | 同进程热响应 | JSON |
| --- | --- | ---: | ---: | ---: |
| 2023 | complete | 21.61s | 97.07ms | 250,229 B |
| 2024 | complete | 19.97s | 74.79ms | 262,993 B |
| 2025 | complete | 23.82s | 51.13ms | 259,166 B |
| 2026 | year_to_date | 18.11s | 7.22ms | 248,258 B |

新的独立进程随后以 persistent 模式命中同一组语义指纹：首个报告 229.25ms，其余 129.67–141.17ms，同进程热响应 6.76–16.60ms，全部在 250ms 热预算内。sidecar 保留旧 v2.13 行，同时存在 2023–2026 的 v2.14 精确行；没有删除历史缓存，也没有让新报告命中旧 key。

### 4.2 2026 逐字段复算

- 报告截止日为 2026-08-21，共 10,631 次逻辑播放。
- Passport 与收听生活均为 2,807 首 canonical tracks。
- 新歌 1,166 首，`1,166 / 2,807 = 41.5%`；复听率 `(10,631 - 2,807) / 10,631 = 73.6%`。
- 头号艺人包含播放 1,340 次，`1,340 / 10,631 = 12.6%`，不再使用 fan-out 后艺人表总行数。
- 8 月截至 21 日比 7 月 1–21 日少 6.9%；较 2025 年 8 月 1–21 日多 58.0%。两条 metric 均保存 21 天等长窗口，不再标成完整月比较。
- 播放里程碑为：“听到 Sign of the Times 时，你的个人历史总播放数在今年跨过了 60,000 次”，详情深链为 `/music/tracks/1585`；没有 `Manchild` 1,000 次错误。
- 时间线为 7 个互斥月份节点，没有 6 月 13 日或 7 月 25 日两条“今年听歌最多的一天”；唯一极值与并列语义由 probe v6 复核为 0 issue。

### 4.3 自动化与浏览器

- 后端：unit `1,342 passed`，contract `369 passed`。
- 前端：73 个文件、`559 passed`；TypeScript + Vite production build 通过。
- API：安全 GET smoke `128/128 passed`，边界探针 `111/111 passed`；OpenAPI 195 个操作与 95 项参数边界均有证据归属，`unaccounted=0`。
- Phase 5：文档、workflow/local CI 声明、unit、contract、ruff、前端测试和 production build 全部通过。
- 完整 pre-commit：Ruff、Ruff format、Mypy、Detect secrets 全部通过。
- Desktop 1440px、Compact 768px、Phone 390px/360px 真实 Chromium 页面均无横向溢出；390px 不挂载桌面宽表，768px 不挂载移动底栏。
- Desktop 与 Phone 都可见 60,000 次里程碑，不存在 Manchild 1,000 或两条冲突日极值文案；控制台 0 error、0 warning。截图保存在本地忽略目录 `output/playwright/`，不进入 Git。

### 4.4 项目全栈边界

`fullstack_verification_check.sh` 的第一阶段全量后端得到 `2,196 passed, 9 failed`。其中本轮唯一回归是旧 Playback Records 仍要求里程碑行保留 `entity_id`；已恢复该兼容字段并由相关 17 项测试及最终 152 项年度测试复验通过。

余下 8 项不属于年度总结改动：

- 4 项 Album Project rebuild/resolver 失败，与本轮开始前已知基线一致。
- 3 项真实艺人身份测试仍硬编码旧播放数量或旧 provider conflict 状态，数据更新后分别出现 SZA 1,127 vs 1,109、Jolin Tsai 308 vs 307、conflict 状态变化。
- 1 项真实 Billboard 专辑详情仍硬编码 2 个在榜周，当前数据为 3 周。

因此年度修复范围为 Pass；仓库全栈总门禁保持 Partial。没有为了让无关旧断言变绿而篡改当前数据或扩大本次实现范围。

## 5. 边界

- 未修改原始 `plays`、`tracks`、`track_artists` 或数据库 schema。
- 未修改个人 Billboard、Power Score、官方 Wrapped 只读兼容语义。
- 本次只重建可再生年度 artifact，不删除历史缓存。
- 未执行生产发布，也未提交或推送 Git。
