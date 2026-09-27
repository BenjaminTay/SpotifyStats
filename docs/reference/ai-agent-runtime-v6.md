# AI Agent V6 运行、恢复与报告发布规则

## 1. 适用范围

本规则适用于 AI 问答、年度报告快照研究和逐章写作。周报、月报保留固定工作流。`AI_AGENT_RUNTIME=v2` 仍是历史配置值；新任务在任务记录中固定 `runtime_version/workflow_version/event_schema_version`，不以批量改名替代协议升级。

## 2. 事实源与模型请求

- V6 追加事件是模型执行事实源。每次模型请求前，从已提交的 model message、工具 observation、约束更新和固定请求资料重新投影上下文。
- 每个 logical call 首次创建不可变 request descriptor，完整保存实际 messages、工具 schema、provider/model 标识、temperature、max token、thinking、prompt/协议版本。恢复必须从该 descriptor 派发；当前 provider/model 不再可用或 descriptor 版本不兼容时明确停止，不能在同一 call ID 下换请求。凭据继续在派发时读取，不进入事件。
- logical call 与真实 dispatch attempt 分开记录。每次 retry/fallback 在网络 I/O 前原子检查任务状态、执行身份和累计额度，并写入 dispatch reservation；该 reservation 是“已派发”早于后续取消 ACK 的审计边界，事务提交后不在网络 I/O 期间持有 SQLite 写锁。
- 工具公开轨迹和模型可见 observation 在同一事务提交。成功调用以任务代次、步骤和 call ID 标识；恢复不再次执行已提交调用。
- Provider 调用不承诺 exactly-once。dispatch 已预留但无法确认是否真正到达 Provider 时按已消费调用和 unknown 用量保守计账；额度允许时可以用新 attempt 重试，响应已提交后不得重发。
- 恢复先区分“请求尚未派发、派发结果未知、响应已提交但工具未完成、部分工具已完成、步骤已结束、最终回答已提交但尚未发布”。只有模型响应要求的工具 observation 已全部提交，或已有明确的 `step_ended/guardrail_retry/clarification_requested`，才能进入下一逻辑步；否则保留原 step 与 logical call ID。最后一个允许步骤同样适用，不能因恢复无条件 `+1` 而丢失。
- 已提交模型响应、工具 observation、研究结果和已审核章节是纯读取事实：恢复必须先查这些事实，再对真正需要的新模型派发或工具执行检查步骤、调用和有效时间预算。已存在 request 在步骤额度刚好耗尽时仍可完成原逻辑步，但新的 request、额外 dispatch 和缺失工具仍受累计额度限制。
- 冻结 request 重试前不消费新 steer/input；新输入保留到原步骤完成后的下一逻辑步。恢复必须核对当前 provider/model 与工具 schema，并实际采用 descriptor 中的 temperature、max token、thinking 等行为参数；不兼容时明确停止。

## 3. 任务代次、租约和预算

- 每个任务有稳定 generation；每次 Worker 接管增加 `lease_generation`。业务写入必须同时匹配 owner 与 lease generation。
- 失去租约的旧 Worker 可以结束在途外部请求，但不能提交模型正文、工具结果、章节或最终任务状态。
- 恢复继承已消费的步骤、工具调用、真实 dispatch、重试和 token 记录；不得把恢复当成新预算。token 仅按 Provider 返回值记录，unknown attempt 单独计数；当前没有独立的累计 token 硬上限，不能把“有 token 记录”表述成 token 限额已执行。
- 取消先持久 ACK。新的模型请求、工具派发、章节提交和发布前都检查任务终态或租约；同步在途调用返回后不再提交业务成果。
- 已提交结果即使在预算耗尽后也可以读取和重建确定性投影，但取消或失租仍会阻止新的提交、章节回调和最终发布；“允许读”不等于“允许旧 Worker 发布”。

## 4. 年报固定上下文与章节

- 年报 context key 由精确快照 key、过滤条件、期间与报告合同共同生成。同一任务只复用 context key、writer 和 validator 版本均兼容的章节。
- 六个稳定 section ID 分别保存顺序、版本、正文、来源、审核、用量、重试和补齐原因。通过审核后立即提交；进程退出不撤销已提交章节。
- 模型章节和确定性补齐都必须通过章节审核。超过 2 章补齐时整份报告不发布，但已审核章节仍可阅读并明确报告未完成。
- 全文审核失败时撤下本代已展示章节并发送失效事实。只有 critic、事实、artifact 和章节门禁全部通过，才保存发布 artifact 并更新成功缓存。

## 5. 查询与 SSE

- `GET /api/ai/tasks/{task_id}/sections` 返回当前已审核章节的权威快照及 generation/sequence 水位；空章节列表同样可以表达较新的审核撤回事实。
- SSE v2 cursor 同时包含 progress、tool、section 和 answer 水位；兼容读取 v1 cursor。未知 cursor 返回 `stream.resync`，客户端重新读取快照，不从头盲目追加。
- 任务状态以 generation/state version 比较，终态不得被旧 running 快照覆盖。章节以 `task_id/generation/section_id/section_version/sequence` 调和；审核撤回递增版本并产生失效事件。刷新或断线遵循“读取权威快照，再应用水位之后事件”，而不是永久优先某一种传输。
- 页面只展示已审核章节；内部 prompt、思维链、lease、revision 和未审核正文不发送前端。

## 6. 兼容与回退

- 旧任务和旧成功缓存可读；缺少 V6 事件的旧任务不声称可恢复。
- 切回旧执行路径只影响新任务。V6 在途任务由理解 V6 schema 的 Worker 完成或明确取消。
- 回退前处置在途任务；不执行破坏性降级迁移。正式发布仍需固定 SHA、备份、三模式门禁和独立线上验收。

## 7. Billboard 工具与搜索封面边界

- `billboard_entity_detail` 未显式携带过滤参数时继承当前项目设置；调用者显式参数优先。单曲 Agent 视图优先读取同一精确 filter/revision/L2-L3 合同下已发布的 summary 与 weekly ledger；`total_chart_plays` 只能汇总该 ledger。只有 ledger 能证明与 summary 的周数、首末周、峰值及峰值周数一致时才走快路径，否则回退完整 builder。
- 单曲 Agent 结果对已上榜、未上榜和零播放实体统一提供 `effective_play_count`；未上榜图表不伪造 `peak_position`。完整 builder 的 L2/L3 `total_plays` 使用版本组聚合，Power 名次使用已发布稳定 `power_rank`，不能按分数再次排序改变并列顺序。
- Agent 快路径保持回答所需的周历史、榜单间断、running 指标和 chart data，但不展开页面展示专用的 `meta.version_group`；这项展示差异不得被描述为事实缺失或逐字段完全相等。
- 音乐搜索只在专辑/艺人具有 `image_path` 或 `image_url` 元数据时发布本地 `/covers/...jpg`。读取旧候选 generation 或 legacy 搜索结果时，按当前结果页至多执行两次元数据查询并将失效本地 URL 清为 `null`；不访问文件系统、不触发封面下载，也不要求同步重建索引。外部/provider URL 原样保留。

## 7. 主分支迁移集成

2026-09-27 合并后保留主分支已使用的 schema 80/81（Spotify 多艺人署名），V6 运行与章节、冻结上下文与预算、模型派发三项迁移依次使用 82/83/84。分支验收期间的 80/81/82 仅是当时隔离副本的编号，历史验收数据库不能直接替换正式数据库；新验收或发布从主分支数据库副本按当前迁移链升级。搜索候选版本为 `music_search_candidate_index_v6_credits_and_covers`，同时包含有效署名与封面可用性。
