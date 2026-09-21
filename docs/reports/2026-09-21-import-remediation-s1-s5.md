# 导入处理与治理修复 S1–S5 实施报告

> 日期：2026-09-21
> 范围：持久批次、事实/来源发布、阶段恢复、任务调度、身份治理与 Settings 工作台
> 实现状态：IMPLEMENTED
> 验证状态：PASS（后端完整测试 + 前端测试/build + 定向故障矩阵；最终真实副本/浏览器/fullstack 另见 S6 报告）
> Git：`d37c9af`、`37c8431`；UNPUSHED
> 部署：NOT_DEPLOYED

## 结论

S1–S5 已按规划实现并提交。串流导入不再依赖浏览器路径或进程内任务字典：服务端拥有不可变批次，独立控制库持久保存运行、阶段、发布日志和报告；事实、来源和恢复均有 generation/digest/revision 栅栏。事实提交后的派生失败从对应阶段重试，不再默认整库回滚。Settings 在 Phone、Compact、Desktop 共用同一持久状态源，可上传、预检、确认、执行、查看历史/报告、重试和重新核对。

## S1：批次一致性与基线生命周期

- 新增服务端 `snapshot` / `delta` 批次，流式上传计算大小和 SHA-256；finalize 在批次锁内复核并原子冻结，重复 manifest 幂等复用。
- `import_control/control.sqlite3` 与活动主库分离；`import_sources/<batch-id>/packet|resolved` 保存不可变来源及完整解析视图。API/报告不返回服务端绝对路径或原始身份。
- 发布日志覆盖准备、快照、事实提交、来源准备、指针切换、完成与恢复；活动指针使用 compare-and-swap，启动恢复拒绝来源漂移和后来提交。
- writer lease 同时覆盖线程与进程；应用写连接和七个维护脚本接入共享/独占协调。上传、冻结、事实事务与恢复具有各自明确锁边界。
- noop 在快照、事实写入和派生构建前结束；append/reconcile/replace 在同一事务发布事实、基线、年度分区和 ChangeSet。

## S2：阶段恢复与错误诊断

- 固定阶段为 `metadata → identity_merge → album_project_l3 → billboard_aggregates → candidate_index → critical_prewarm → cover_supplemental → exact_snapshots`。
- 每次 attempt 保存 generation/digest、依赖 revision 向量、输入/输出证据、错误码、trace 摘要和 retryable；重试从失败阶段继续，不重新执行事实 ETL。
- 阶段前后双重事实 fence 与依赖 fence 阻止旧任务覆盖新事实。元数据 provider 不可用或有 errors 时为 `partial`，不会伪装为成功。
- readiness 区分 `facts_committed`、`core_ready`、`ready`、`warming`、`unavailable` 和 `failed`；无 LKG 时不返回虚假 ready/0。
- 发布前硬中止可成套恢复旧库/旧来源；事实提交后的可恢复阶段失败保留新事实。控制库不随主库恢复，失败历史仍可查询。

## S3：关键任务调度与定向处理

- JobQueue 持久保存 priority、resource lane、logical target、generation/revision fence、attempt 和有限重试。
- 关键 CPU、网络与 supplemental lane 分离并保留关键执行能力；重启保持优先级和目标，旧 target 不会吞掉新 generation。
- Billboard、Album Project、候选和四套精确搜索继续以 ChangeSet 证明闭包；不能证明时带原因安全 full fallback。L2/L3 × fixed/dynamic 是当前四套必需公开集合，L1 仅作兼容陈旧证据。
- 1,204 封面排队的确定性测试证明：依赖满足的关键 job 无需等待封面队列排空，低优先级仍能推进。

## S4：兼容身份与未匹配记录治理

- played L3 使用硬门禁，不能因缩小作用域排除真实播放问题；全量零播放/兼容别名进入独立治理账本。
- 33 个全量 identity 样本和 238 条未匹配音频都有唯一主分类或明确 unknown，并保存样本引用、影响播放数/时长、证据与处理状态。
- 当前 238 条拆分为 podcast 222、audiobook 1、unknown 15；原始事实 238 条 / 138,421,062 ms 保持不变。played 范围 6,642 个身份、0 个问题；全量 6,675 个身份、33 个治理项。
- 重复扫描/导入按稳定 issue key 幂等，不重复创建问题；人工覆盖、旧深链和别名解析仍有效。

## S5：设置页、运行历史与报告

- 新 `DataImportWorkspace` 与 `useDataImport` 统一 raw File/FormData 上传、批次/运行 query key、轮询、分页历史、报告、retry/recheck。
- Phone、Compact、Desktop 使用互斥 presentation，但共用 URL、Query 和持久后端事实；主操作触控目标按 44×44px 设计。
- 页面分别呈现数据更新、统计准备和质量事项；展示 baseline missing、noop、增量/协调、输入漂移、失败恢复、warming、无 LKG 和 provider 缺失，不用一个“完成”掩盖阶段状态。
- 旧健康检查、治理预览和账号导入仍保留；刷新或重启后运行历史来自控制库，不依赖组件本地定时器或模块级缓存。

## 验证

- Backend 完整测试：`2416 passed, 680 deselected`；3 个 warning 均另行记录，没有导入范围失败。
- OpenAPI 审计：234 operations，0 unaccounted；参数合同审计：110 obligations，0 unaccounted。
- Frontend Vitest：86 files passed、1 skipped；667 tests passed、4 skipped。
- Frontend production build：PASS；变更文件 scoped ESLint：PASS。
- 全仓 ESLint 仍有 184 个范围外既有问题；正式项目门禁是前端测试与 build，本轮没有借机清理旧债。
- `git diff --check` 与提交 hooks：PASS。

## 明确边界

- 本报告不把 S1–S5 局部证据写成最终 S6 Pass；真实 92,908→94,760 副本、三次可比样本、浏览器和默认完整 fullstack 由最终验收报告单列。
- 没有向 Spotify 发出验收网络请求；冻结 provider 响应与真实外部服务结果分开报告。
- 没有 push、部署或再次写入正式播放事实；本地开发服务曾因 `--reload` 被动应用 migration 79，正式 `plays` 仍为 94,760，未触发导入。
