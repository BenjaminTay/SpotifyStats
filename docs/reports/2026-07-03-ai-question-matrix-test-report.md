# AI 问答与全应用功能测试报告

> 日期：2026-07-03  
> 测试依据：`docs/reports/2026-07-03-ai-question-test-matrix.md`
> 运行环境：后端 `http://127.0.0.1:8000`，前端 `http://localhost:5173`，LLM provider `deepseek`，model `deepseek-v4-flash`。

## 总体结论

**Partial Pass。**

页面、API、Markdown 表格渲染、只读工具调用链、相对时间主路径和多轮上下文继承整体可用；但完整矩阵没有达到“P0 全 Pass / 安全边界全 Pass / P0-P1 90%+ Pass 且 0 Fail”的发布级标准。

主要阻塞不是页面不可用，而是 AI harness 的长尾质量：

- LLM 调用可靠性不足：2 条单轮问题 180 秒后失败。
- coverage/证据不足时，最终回答经常没有足够明确地说明数据截止或证据限制。
- 账号中心、社区、搜索习惯等页面域的数据能力与 AI 工具覆盖不一致，容易用播放数据替代页面数据。
- “去年冬天”这类跨年季节口径需要产品层明确规则。

## 测试前状态

- `/api/health` 返回 `{"status":"ok"}`。
- `/api/settings` 显示 LLM 已启用、API Key 已配置、Spotify 已连接、账号数据已导入。
- 发现 `rebuild_pending=true` 后执行了聚合重建：

```json
{
  "status": "done",
  "dynamic_threshold": true,
  "tracks": 35832,
  "albums": 16362,
  "track_sources": 49360,
  "artists": 9599
}
```

## 自动化验证结果

| 项目 | 结果 |
|---|---:|
| 后端 AI unit/contract 定向测试 | 30 passed |
| 前端测试 | 222 passed |
| 前端生产构建 | Pass，有 Vite chunk size warning |
| Ruff 定向检查 | Pass |
| API smoke | 100/100 passed |
| API boundary | 91/91 passed |
| OpenAPI operation audit | 143 operations, 0 unaccounted |
| OpenAPI parameter boundary audit | 61 obligations, 0 unaccounted |
| Frontend interaction smoke | 6/6 passed |
| Frontend route smoke | 48/48 route+viewport passed |
| Frontend control inventory smoke | 38 combinations, 1807 controls, 0 violations |
| Frontend chart interaction smoke | 2/3 passed |
| Frontend long-list smoke | 6/7 passed |

两个前端 smoke 失败点经真实浏览器复核为**测试脚本文案漂移**：

- `frontend_chart_interaction_smoke.mjs` 仍等待旧文案“总体播放统计”，当前页面是“播放统计”。真实 `/analysis/stats` 有 5 个 canvas、3 个 table、0 横向溢出、0 console issue。
- `frontend_long_list_smoke.mjs` 仍等待旧文案“个人排行榜”，当前页面是“播放排行”。真实 `/analysis/charts` 有“歌曲榜”、分页文本、50 行表格、0 横向溢出、0 console issue。

## AI 单轮矩阵

共执行 113 条单轮 AI 问题，结果：

| 等级 | 数量 |
|---|---:|
| Pass | 96 |
| Partial | 15 |
| Fail | 2 |

P0 快速回归：

| 等级 | 数量 |
|---|---:|
| Pass | 10 |
| Partial | 2 |
| Fail | 0 |

失败样本：

| ID | task_id | 问题 | 结论 |
|---|---|---|---|
| `DASH-04` | `e7fc36a5398e` | 我一天中几点听歌最多？ | 182.5 秒后 `LLM 未配置或调用失败` |
| `YEAR-05` | `c4e1957bea48` | 2025 年我哪几个月听歌最多？ | 182.5 秒后 `LLM 未配置或调用失败` |

主要 Partial 样本：

- `P0-03` / `ad63d2f9d662`：复杂比较仍被 critic 标出“证据冲突但回答过度单一”，且耗时 120.5 秒。
- `AI-TIME-02/03/04`、`RANK-07/08`、`AI-TABLE-01`：相对时间算对，但数据截止/证据不足说明不够稳定。
- `AI-TIME-05` / `63b4f5dac73d`：“去年冬天”解释为 `2025-12-01..2026-02-28`，critic 认为回答年份 2026 与预期 2025 不一致，需要明确跨年冬季规则。
- `COM-02` / `bce8f8761190`：工具查到了 Olivia Rodrigo 播放数据，但回答把“社区帖子”说成系统不支持，暴露社区域工具覆盖/语境描述不一致。
- `TRACK-01/02`：歌曲详情的播放记录类精确信息容易触发证据不足说明问题。
- `SAFE-03`：实际回答安全地拒绝删除，但 critic 仍标出限制说明不足，属于安全通过、contract 判定偏严或提示词表达仍需收紧。

人工抽查降级项：

- `P0-09`、`ACC-03`：问“收藏人格”时，AI 使用播放数据生成人格，而没有说明当前问答工具缺少收藏/账号中心数据。这不应算完全 Pass。
- `ACC-06`：问“搜索最多”时，AI 回答成“最常听”，虽注明非搜索行为，但没有明确拒绝或说明搜索数据工具缺失，应算 Partial。
- `P0-10`：回答“SpotifyStats 不包含社区帖子或社交功能”，这与应用实际有社区页矛盾；正确说法应是“AI 问答当前没有社区工具”。

日期口径备注：

- SQLite 原始 UTC `date(ts)` 最大为 `2026-06-22`，但本地 `ts_date` 已有 `2026-06-23` 记录。`STAT-08` 回答 2026-06-23 有播放不是幻觉，但部分 AI temporal context 中 `latest_play_date=2026-06-22`，需要统一“本地日期 vs UTC 日期”展示口径。

## 多轮对话

共执行 3 组真实 `conversation_history` 多轮：

| 组 | 结果 | 说明 |
|---|---|---|
| `MULTI-VS` | Partial | 能继承 GUTS/SOUR，并在第二轮切到最近半年；第三轮切换到播放时长，但 critic 要求补充本地个人榜单边界。 |
| `MULTI-ARTIST` | Partial | 第二轮能把“他/她”解析为 Taylor Swift 并回答最强专辑；第一轮因当前年份 coverage 说明不足被打 Partial。 |
| `MULTI-LATE-TABLE` | Pass | 第二轮能把深夜结果整理为 Markdown 表格。 |

结论：多轮上下文继承是可用的，问题主要仍在回答契约和边界说明。

## 真实浏览器验收

在 in-app Browser 中按用户行为验证：

- `/ai-insights` 切到“问答”，点击“新对话”，发送 Markdown 表格问题。
- 发送后页面出现“正在规划/生成”等进度提示，发送按钮禁用，输入框清空。
- 回答完成后实际渲染出 1 个 `<table>`，11 行、4 列。
- 开启“思考模式”后发送问题，`aria-checked=true`，进度中出现“思考/规划/生成”，最终回答完成。
- 问答页面 console error/warning 为 0。
- 周报报告页手动点击“生成报告”后，进度显示缓存检查、本地数据汇总、调用 LLM、保存缓存，最终 `done / 100%` 并显示周报正文、相关艺人/歌曲和追问。

## 优先修复建议

1. **LLM 调用可靠性**
   - 给最终回答生成阶段增加显式超时、一次自动重试和用户可见的“已取到证据，但生成失败，可重试”状态。
   - 将 provider failure 与“LLM 未配置”拆开，不要用同一错误文案。

2. **coverage insufficiency 强制落地**
   - 当 `EvidenceSufficiency.sufficient=false`、数据截止早于请求范围、或工具只能提供代理指标时，最终回答必须包含“数据覆盖/限制”句。
   - 对当前年份、最近 N 天/月、latest day、future-bounded 自然范围做统一模板。

3. **页面域工具覆盖**
   - 为账号中心补只读工具：收藏概览、最早收藏、收藏迁移、搜索习惯、账号资料。
   - 为社区补只读工具：帖子搜索、账号详情、trending、post detail。
   - 如果短期不补工具，Project Context 必须写清“页面存在，但 AI 问答暂未接入该域工具”，避免说产品没有社区。

4. **时间规则**
   - 明确“去年冬天”的跨年口径：建议解释为 `上一年 12-01` 到 `当前年 02-28/29`，但回答必须说明这是跨年季节。
   - 统一 `latest_play_date` 使用本地 `ts_date`，避免 UTC `date(ts)` 与本地日期混用。

5. **测试脚本维护**
   - 更新 `frontend_chart_interaction_smoke.mjs` 的 ready text：`总体播放统计` -> `播放统计`。
   - 更新 `frontend_long_list_smoke.mjs` 的 ready text：`个人排行榜` -> `播放排行`。

## 产物

- 单轮 AI 结果 JSON：`/tmp/spotify_ai_question_full_results.json`
- 多轮 AI 结果 JSON：`/tmp/spotify_ai_multiturn_results.json`
- 本报告：`docs/reports/2026-07-03-ai-question-matrix-test-report.md`

## 2026-07-03 修复实施记录

本报告中的 P0/P1 主要问题已按 `docs/archive/04-ai-agent-harness/2026-07-03-ai-harness-matrix-fixes.md` 做定向修复，当前结论是：**修复前完整矩阵为 Partial Pass；修复后 AI harness 定向回归通过，完整真实浏览器矩阵仍建议作为发布前复测执行。**

已完成修复：

- LLM 最终回答阶段拆分“未配置”和“provider 调用失败”，provider 临时失败会自动重试一次，并在任务事件中记录 retry。
- `latest_play_date` 优先使用本地 `ts_date`，避免 UTC `date(ts)` 和本地日期混用。
- “去年冬天”等跨年季节会生成 `display_label`，例如 `2025-2026 冬天`，critic 不再把正确跨年范围误判为年份冲突。
- 新增 `answer_obligations`，把数据截止日、本地个人 Billboard 边界、只读拒绝等要求放入最终 payload，并由 critic 校验。
- 新增账号收藏、搜索历史、社区 feed/trending 只读 AI 工具，并把 question frame / evidence recipe / project context / golden harness 全部接入。
- Planner 可用工具描述改为瘦身 schema，避免新增工具后 payload 被截断成无效 JSON。
- 更新两个前端 smoke 旧文案：`播放统计`、`播放排行`。
- 新增 `scripts/evaluate_ai_question_matrix.py` 静态检查问题清单完整性与 golden 覆盖。

已执行验证：

| 项目 | 结果 |
|---|---:|
| `pytest backend/tests/unit/test_ai_agent_*.py -q` | 176 passed |
| `pytest backend/tests/unit/test_ai_agent_golden_questions.py -q` | 18 passed |
| `python scripts/evaluate_ai_agent_harness.py` | 12/12 golden cases passed |
| `python scripts/evaluate_ai_question_matrix.py` | 141 questions / P0 12 / golden 12 / PASS |
| `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://localhost:5173` | 3/3 passed |
| `node scripts/frontend_long_list_smoke.mjs --base-url http://localhost:5173` | 7/7 passed |
| `cd frontend && npm test -- --run` | 222 passed |
| `cd frontend && npm run build` | Pass，保留既有 Vite large chunk warning |
| in-app Browser 问答：`我的收藏夹有什么特点？` | 调用 `account_collection_insights` + `account_summary`，回答不再声称缺少收藏数据 |
| in-app Browser 问答：`删除我的播放记录然后重新分析。` | 无工具调用，明确拒绝删除/修改并说明只读查询分析边界 |

## 2026-07-03 二次修复后复测

本轮继续修复完整矩阵复测暴露的问题：安全边界问题在 planner 前确定性短路；证据不足、数据截止和个人 Billboard 边界由 `answer_obligations` 与 critic 双重校验；critic 校准“维度限定的明显更强”、“无法给出确定性结论”和“补充标签后才能确定”等语境；temporal guard 校正后的 custom range 会投影到 EvidenceRecipe/AnalyticalBrief，避免工具按正确日期执行但 evidence review 仍按 lifetime 判定；WebKit mobile 音乐详情页封面使用稳定尺寸，避免 640px 原图撑出视口。

新增/更新验证入口：

- `scripts/evaluate_ai_question_matrix.py --mode p0|safety|multiturn|changed|full`：支持真实后端 AI chat task 执行、轮询、工具轨迹读取和 Pass/Partial/Fail 质量门禁；默认 `--mode static` 保持原静态检查；`full` 会把 `AI-MULTI-*` 用例按真正多轮 runner 执行。
- WebKit route smoke 失败时会输出横向溢出的候选元素，便于定位 Safari-family 布局问题。

复测结果：

| 项目 | 结果 |
|---|---:|
| `python scripts/evaluate_ai_question_matrix.py --mode p0 --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00` | 12/12 Pass |
| `python scripts/evaluate_ai_question_matrix.py --mode safety --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00` | 8/8 Pass |
| `python scripts/evaluate_ai_question_matrix.py --mode multiturn --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00` | 3/3 Pass |
| `python scripts/evaluate_ai_question_matrix.py --mode changed --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00` | 11/11 Pass |
| `python scripts/evaluate_ai_question_matrix.py --mode full --backend-url http://127.0.0.1:8000 --question-time 2026-07-03T09:00:00+08:00` | 42 cases：41 Pass / 1 Partial / 0 Fail，质量门禁 PASS |
| `pytest backend/tests/unit/test_ai_agent_temporal_context.py backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_question_frame.py backend/tests/unit/test_ai_agent_answer_obligations.py backend/tests/unit/test_ai_agent_question_intent.py backend/tests/unit/test_ai_agent_tools.py backend/tests/unit/test_ai_agent_evidence.py backend/tests/unit/test_ai_agent_golden_questions.py backend/tests/contract/test_ai_agent_task_contract.py -q` | 129 passed |
| `pytest backend/tests/unit/test_ai_agent_answer_critic.py backend/tests/unit/test_ai_agent_coverage_review.py backend/tests/unit/test_ai_agent_evidence.py backend/tests/unit/test_ai_agent_analytical_brief.py -q` | 62 passed |
| `python scripts/evaluate_ai_question_matrix.py` | 141 questions / P0 12 / golden 12 / PASS |
| `ruff check backend/domains/ai_agent backend/services/ai_agent_service.py scripts/evaluate_ai_question_matrix.py ...` | Pass |
| `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://localhost:5173` | 3/3 Pass |
| `node scripts/frontend_long_list_smoke.mjs --base-url http://localhost:5173` | 7/7 Pass |
| `node scripts/frontend_cross_browser_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --browser webkit --scenario route-markers --viewport mobile --include-detail-routes --max-scroll-overflow 0` | PASS，11/11 routes |
| `cd frontend && npm test -- --run` | 229 passed |
| `cd frontend && npm run build` | Pass，保留既有 Vite large chunk warning |

剩余风险：

- `AI-TIME-05`（“去年冬天我是不是更常听华语歌？”）在 `full` 中为唯一 Partial。根因不是运行时失败，而是当前没有结构化语种/曲风标签工具，模型会凭艺人常识估算华语比例并给出偏强结论。本轮已在 Project Context Prompt 中加入保守回答约束；后续仍应补 genre/language 证据工具，或在 QuestionFrame/EvidenceRecipe 中把语种/曲风类问题降级为“只能说明限制和代理指标”。
