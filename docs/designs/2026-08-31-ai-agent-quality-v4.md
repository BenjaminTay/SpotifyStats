# AI Agent Quality V4 完整优化方案与实施说明

状态：`IMPLEMENTED`
功能质量：`PASS`
交互性能：`PARTIAL`
分支：`codex/ai-agent-quality-v4`
代码提交：`6437bdea`、`bc75a1ce`
远端：`UNPUSHED`
部署：`NOT_DEPLOYED`

## 目标与结论

V4 的目标不是扩建通用 Agent 平台，而是让 SpotifyStats 的 AI 问答和年度报告成为一个最小、真实、可恢复、可验收的本地数据 Agent。成立标准不再是“接口存在”或“模型能调用一次工具”，而是一次任务必须完成：模型决策、只读工具、结构化观察、约束更新、证据追溯、答案门禁、持久事件、失败恢复和真实 UI 呈现。

对照 Pi Agent 与 DeepSeek Harness，V4 继续使用 Pi 式小核心循环，不引入重型工作流图；同时吸收 Harness 的 Turn/Step、append-only 事件、Inbox、lease 和 replay。SpotifyStats 的差异化部分是确定性统计事实：模型负责选择与解释，builder/validator 负责数字、时间和榜单口径。

## V4 架构

```text
Question / Inbox steering
        │
        ▼
Constraint Patch V2 ──► Session State / Temporal Guard
        │
        ▼
Agent Profile ──► Native Model/Tool/Observation Loop
        │                         │
        │                         ▼
        │              Read-only Tool Runtime
        │              + tool_evidence_v2
        │                         │
        └─────────────────────────┘
                    │
                    ▼
Fact Catalog ─► Evidence Coverage ─► Claim Ledger
                    │                    │
                    ├─ bounded补查       ├─ 无数据回答
                    ├─ 证据失效          └─ grounded fallback
                    ▼
          Answer Quality Contract
                    │
                    ▼
Durable Task + Event Log + Lease Heartbeat + SSE Replay
```

## 完整优化项

### 1. 答案质量契约

新增五维 Answer Quality Contract：`directness`、`informativeness`、`constraint_fidelity`、`evidence_traceability`、`uncertainty_honesty`。真实问题矩阵只有五维全部通过、没有 validation issue、证据覆盖达标时才判 Pass。

空时间窗不再被“工具调用成功”误认为证据充分；没有记录时必须明确回答无数据，不能生成虚假排行。社区检索必须列出真实命中的主体或活动，只有查询条数不算有信息量。

### 2. 统一证据协议

Chat 与年度报告统一输出 `tool_evidence_v2`。每份证据包含工具、调用身份、状态、source range、事实、限制和 constraint fingerprint。约束替换后，旧 fingerprint 下的证据显式失效，不能进入最终 Fact Catalog 或报告章节。

报告增加逐章节 checkpoint。每节独立检查标题、正文长度、图表引用、工具引用和不可追溯数字；失败章节只允许一次有界模型修复，剩余不支持数字由确定性安全网移除。

### 3. Constraint Patch V2

运行中补充要求采用版本化 patch，支持 `replace`、`append`、`exclude` 与 metric 更新。requested range 与按本地数据截止日裁剪后的 effective range 分开保存。实体、时间、指标、Billboard 排除和过滤条件在 Session State、Question Frame、Evidence Recipe 与工具参数间保持同一语义。

### 4. 工具性能与语义

- 新增 `taste_profile`，用一次专用读取回答曲风/语言偏好，避免通用分析工具重复扫描。
- 社区文本检索优先走 music-search 候选索引与已发布周榜上下文，真实工具耗时由约 227 秒降至约 0.1–0.2 秒；结果明确标注 scoped snapshot、LKG freshness 和不能覆盖完整社区正文的限制。
- 年度、排行与图表工具统一 `empty` 状态，避免无数据误判。
- 工具缓存、去重、并行和 revision 指纹继续保持只读与 fail-closed。

### 5. 年度报告闭环

年度报告研究复用真实 Agent loop，图表和统计事实仍由确定性后端生成。V4 修复了“要求 2800 字但模型输出上限只有 2048 token”的冲突：写作上限提高到 6144 token，同一研究证据内最多重写一次，不再因为写作格式失败重复整套研究工具。

若模型初稿未达到结构门槛，系统使用相同确定性上下文生成长篇回退稿，再经过 `tool_evidence_v2`、逐节 checkpoint、图表观察、critic、事实校验和最终 artifact 门禁。任一硬门禁失败时任务标记 `error` 且不缓存，不能再以 HTTP 任务 `done` 掩盖不合格报告。

### 6. 可恢复运行时与 SSE

- Worker lease 从 900 秒改为 90 秒，独立心跳每 30 秒续租；长工具或模型调用不会被误接管，崩溃后最迟在短租约到期后可恢复。
- 启动恢复读取 append-only trajectory，从 `run_resumed.next_step` 继续；已完成工具调用身份不重复执行。
- SSE 使用进度、工具、答案三通道组合 cursor。浏览器通过 `Last-Event-ID` 重连时只收到 cursor 之后的事件和答案分片。
- 当前保证是单机 SQLite + lease 的至少一次任务执行和已完成工具去重，不宣称跨主机分布式 exactly-once。

### 7. 前端可用性

AI 页面展示进行中阶段、当前约束、答案和工具轨迹。桌面与 390px 共享任务事实和 SSE cursor。移动端思考模式与发送按钮均调整为至少 44×44px，不产生页面级横向溢出。

## 分层验收标准

| 层级 | Pass 条件 |
|---|---|
| 静态 | 问题矩阵、P0 和黄金问题完整，schema/version 可解析 |
| 自动化 | Agent/report/task unit、contract、前端测试与 build 通过 |
| 真实问答 | 当前模型 + Online Backup 副本；契约、V2 证据、约束和答案均通过 |
| 恢复 | 杀进程后 stale lease 接管；attempt 增加；已完成工具不重复 |
| 流式 | 组合 cursor 断线续传，无旧进度/工具/答案分片重复 |
| 报告 | critic、事实、最终 artifact、全部章节 checkpoint 通过后才缓存 |
| UI | Desktop 与 390px 真实浏览器，无横向溢出、控制台错误，触控目标达标 |

## 当前边界与下一阶段

1. 年度报告冷构建约 11 分钟，交互性能为 Fail。下一阶段必须把同 filter/revision 的年度确定性上下文做成持久 ready snapshot，并让报告工具共享一次构建结果。
2. 当前 DeepSeek writer 两次返回空内容，最终报告依赖确定性写作回退；研究 Agent、证据与质量闭环成立，但纯模型写作状态为 Partial。需记录 Provider finish reason/usage，并将写作输入拆成分节小上下文。
3. 问答 changed 集 11/11 通过，但复杂跨年和深夜分析仍为约 49–50 秒；需要真实 P50/P95 延迟门禁，而不是只设 180 秒超时。
4. 社区 scoped snapshot 只覆盖候选索引和周榜活动，不等同完整 Feed 帖子搜索；UI 必须保留限制说明。
5. 不扩大到任意 SQL、任意 URL、写设置、导入、歌单、多 Agent、Shell 或长期自治；这些不是“让当前 Agent 变聪明”的必要条件。
