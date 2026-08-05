# 数据导入与健康检查

## 目标

数据导入区只负责两件事：在导入前确认本地 Spotify 数据包可读，在导入后说明数据库、关系、元数据和派生统计是否可继续使用。健康检查是只读的，不会修复、删除或覆盖原始播放事实。

## 与现有导入流程的关系

当前导入流程仍由 Settings 页面触发：

1. 串流数据导入读取 `data/streaming/Streaming_History_Audio_*.json`，写入基础播放、曲目、专辑和艺人数据。
2. 账号数据导入读取 `data/account/` 下的 Account Data JSON，补充收藏、歌单、Wrapped、搜索记录等非播放数据。
3. 串流导入完成后继续执行已有的 Spotify 元数据、Album Project 和 Billboard 聚合维护。
4. 健康报告重新读取数据库状态，帮助判断维护是否完成；它不改变以上导入语义。

## 导入前检查

`GET /api/import/preflight` 只检查本地文件：

- 必需输入：至少一个可解析且非空的 `Streaming_History_Audio_*.json`。
- 可选输入：视频历史和 Account Data 文件。缺失只产生提示，不阻止串流导入。
- Streaming History 会检查顶层数组、`ts` 时间戳、记录数量和 `ms_played` 字段提示。
- JSON 解析失败、必需文件缺失或音频历史为空会标记为 `blocked`。
- 预检还会计算串流文件 SHA-256，识别完全重复文件；同一文件内的完全重复记录会计入 `duplicate_record_count`。
- `date_overlaps` 只表示两个文件的日期区间相交，不直接等同于重复播放；每一对会附带 `shared_record_count`，用于区分“边界日期相交但记录不重复”和“确有共同记录”。
- 完全重复文件会进入 `blockers`；文件内重复记录、日期范围重叠和跨文件共同记录进入 `warnings`。导入时只对完全相同的记录自动去重，保留同一内容在稳定文件顺序中的第一次出现；日期重叠不会被当成重复，也不会自动合并。源 JSON 永远不会被修改。
- `POST /api/import/streaming` 会在后台任务真正创建快照前再次执行这份预检：有 `blockers` 时任务状态为 `blocked`；只有 `warnings` 且未传 `confirm_warnings=true` 时状态为 `needs_confirmation`；确认后才会进入快照和导入流程。

检查不会把文件导入数据库，也不会启动后台 Job。确认文件后，用户仍需显式点击已有的「导入串流数据」或「导入账号数据」。

## 导入后健康报告

`GET /api/import/health` 返回四组信息：

| 区域 | 检查内容 | 用途 |
|------|---------|------|
| `database` | 播放数量、音频/视频数量、有效音频数量、日期范围、空曲目、负时长、SQLite 完整性、外键问题 | 判断基础库是否可读、是否存在明显坏数据 |
| `relationships` | 播放→曲目/专辑、曲目→主艺人和曲目署名关系 | 判断统计链路是否会丢掉有效播放 |
| `metadata` | 最近 90 天的曲目与来源专辑、Spotify 元数据、Album Project 覆盖 | 判断新导入内容是否需要维护 |
| `derived` | 周聚合、Album Project、Billboard 聚合、artist identity/track credit revision | 判断下游页面是否与当前事实同步 |

状态含义：

- `healthy`：没有发现问题。
- `partial`：有历史外键残留、元数据缺口或其它非阻断提醒，但核心播放关系仍可用。
- `stale`：派生统计或治理 revision 尚未同步。
- `blocked`：没有播放数据、SQLite 完整性检查失败，或播放记录引用了不存在的实体。

外键检查会按「子表 → 父表」返回明细。历史元数据孤儿记录不会自动删除，也不会仅凭健康检查改写 `plays`、`tracks`、`track_artists`；后续如需清理，必须单独设计可预览、可回滚的维护任务。

## 可行动问题

健康报告同时返回 `issues`。每个问题包含：

- `severity`：`critical`、`high`、`medium`、`low`；
- `count`：该问题关联的记录数；
- `affected_play_count`：已知直接影响播放事实的记录数；
- `impact`：对当前统计的影响说明；
- `recommended_action`：下一步建议；
- `evidence`：关系拆分、检查日期等证据。

具体关系问题会优先展示，外键总数仍保留在 `database.foreign_key_issue_count`。这样同一批孤儿记录不会在用户界面被重复计算；例如当前真实库外键总数为 7,831，但已去重后的问题列表显示曲目/专辑艺人关系、其他历史任务关系和专辑关系等 6 类问题。

## 当前边界

当前只处理可以被完整记录内容证明的重复，不加入近似重复判断、日期合并或根据歌曲名称猜测重复。也不加入分阶段导入、自动修复、后台导入历史页和新的数据治理 UI。

## 第二轮：导入安全边界

当前串流和账号导入在实际写入前都会尝试创建 SQLite 一致性快照，快照使用 SQLite backup API，能够覆盖 WAL 中已经提交的内容。快照放在 `data/import_backups/`，不会写入 Git，也不会被自动删除。

- 已有数据库：快照创建失败时，导入不会开始；导入或串流导入后的维护失败时，系统尝试恢复导入前快照。
- 并发边界：同一进程内只允许一个数据库导入任务；已有导入运行时，后续任务直接标记为未开始，不创建快照、不修改数据库。
- 导入门禁：串流导入会重新核对最新文件状态，避免用户查看预检后文件又发生变化；账号数据导入不受 Streaming History 文件门禁影响。
- 首次导入：数据库尚不存在时，快照状态为 `skipped`；如果这次首次导入失败，系统会清理本次创建的半成品数据库。
- 导入任务结果：成功结果包含 `database_snapshot`；失败结果包含 `database_snapshot` 和 `rollback`，其中 `rollback.status` 为 `restored` 表示已有数据库已恢复，`removed_new_database` 表示首次导入半成品已清理，`failed` 表示需要停止继续导入并人工检查。
- 串流导入成功结果还包含 `duplicate_records_skipped` 和 `post_import_health`。后者只复核 SQLite 完整性、播放记录数量和播放→曲目/专辑关系；这些硬指标失败会按导入异常进入已有回滚路径，普通元数据缺口仍只显示为 `partial` 提醒。
- 回滚后会清空运行时统计缓存，避免页面继续使用失败导入产生的旧派生结果。

本轮建立“失败可恢复 + 确定重复不重复计数 + 导入后硬指标复核”的最小边界，不改变现有覆盖式导入语义；重复文件仍不会自动删除，日期重叠也不会被擅自合并。

## 相关代码

- 后端文件检查：`backend/domains/imports/source_inspector.py`
- 导入快照与回滚：`backend/domains/imports/database_snapshot.py`
- 后端健康报告：`backend/domains/metadata/import_health.py`
- API：`backend/api/import_.py`
- 前端入口：`frontend/src/features/settings/components/DataImportSection.tsx`
- 前端查询：`frontend/src/hooks/useDataImportHealth.ts`
