# Spotify Track `artists[]` 证据交付与隔离验收

> 日期：2026-09-24<br>
> 实现状态：IMPLEMENTED（仅 provider evidence、覆盖与只读差异审计）<br>
> 验证状态：PASS（本地 unit/contract 与隔离数据库副本真实 API；未做完整全栈或生产验收）<br>
> 仓库/远端/部署状态（隔离验收时）：UNCOMMITTED / UNPUSHED / NOT_DEPLOYED<br>
> 规划归档：[Spotify Track `artists[]` 多艺人署名证据接入完整实施规划](../archive/06-productization-closeout/2026-09-23-spotify-track-artists-evidence-plan.md)

## 交付范围与边界

- migration 80 新增 `spotify_track_credit_sets`、`spotify_track_artist_credits`、`spotify_track_credit_events`。每个合法 Track 的 artist ID、credited name 和数组顺序原样保存；首次观察与变化追加事件，重复内容不追加事件。非法响应保留上一可用证据。
- 现有 Spotify metadata refresh 会选择本次导入相关和有界历史证据缺口，输出 requested / observed / changed / unchanged / failed / LKG / missing 计数。缺凭据或部分响应仍是可重试的 metadata partial，不把已发布的播放事实回滚。健康读取只使用数据库状态，不联网。
- 新增默认 dry-run、仅允许隔离副本 `--apply` 的显式回填脚本，以及只读 owner/artist identity 差异报告脚本。没有自动创建本地艺人、自动写入 override、推断 `primary` / `featured` 或重建下游统计。
- 其他待处理 Spotify 字段、第二数据源和曲目语言问题仍在[多源元数据路线记录](../plans/2026-09-23-multi-source-music-metadata-roadmap.md)，未作为本次实现。

## 隔离真实数据/API 验收

正式 `data/spotify_stats.db` 只用于 SQLite Online Backup 读取；所有迁移、回填和审计均在 `/tmp/spotifystats-track-credit-uiVhQK/spotify_stats.db` 副本执行。另保留独立、未迁移的 `/tmp/spotifystats-track-credit-uiVhQK/source-baseline.db` 对照快照，大小 444,588,032 bytes，SHA-256 为 `2c412107ef9e237fea8623139f52c781e62f76017a6c85b939687a568835653a`，schema 79。隔离工作副本升级到 schema 80；两个副本的 `quick_check` 均为 `ok`，`foreign_key_check` 均为 0。

| 运行 | 请求 | 首次保存 | 变化 | 无变化 | 失败 | 回填后覆盖 |
|---|---:|---:|---:|---:|---:|---:|
| 首轮小样本 | 10 | 10 | 0 | 0 | 0 | 10 / 8,320 |
| 剩余全量回填 | 8,310 | 8,310 | 0 | 0 | 0 | 8,320 / 8,320 |
| 同一 8,320 条再次获取 | 8,320 | 0 | 0 | 8,320 | 0 | 8,320 / 8,320 |

运行 JSON 与按曲目差异明细保存在同一 `/tmp/spotifystats-track-credit-uiVhQK/` 目录：`full-backfill.json`、`repeat-backfill.json`、`credit-audit.json`、`credit-audit-repeat.json`。复跑前后分类分布完全一致。最终有序 credit 子行 10,215 条，`artist_count` 与子行计数不一致的 Track 为 0；provider 事件恰好 8,320 条 `observed`，没有 `changed` 事件。

只读差异报告按唯一 Spotify Track ID 守恒：

| 互斥主分类 | 数量 |
|---|---:|
| 与当前有效署名成员一致 | 3,157 |
| Spotify 多出已解析艺人 | 35 |
| 当前本地署名独有成员 | 2 |
| Spotify 艺人 ID 尚未解析到本地稳定身份 | 5,126 |
| 合计 | 8,320 |

provider artist entry 共 10,215 个，其中通过稳定外部 ID 解析 3,777 个，尚未解析 6,438 个。受非一致或未解析状态影响的唯一 owner 为 4,622 个，原始播放行 44,877 条、原始 `ms_played` 合计 7,321,222,527 ms；均按 owner 去重，不是多艺人 fan-out 总量。`unresolved` 不等于错误署名，只表示目前缺少可靠 artist identity 链接。报告只通过 external ID 作确定匹配，名称相同只列候选。人工核对样本包括 `Under Pressure - Remastered 2011`（Queen / David Bowie）及 `We Found Love`（Rihanna / Calvin Harris）：标题未写 `feat`，但 provider 返回两名艺人；它们只进入待治理差异，不自动更改有效署名。

审计字段勘误：原 `credit-audit.json` 在身份未解析时仍计算 `local_only_artist_ids`，其中 4,923 条未解析记录带有非空值；该值不能证明本地署名独有。修正后，仅在 owner 明确且所有 provider 艺人身份唯一解析时计算双方独有成员，其余返回 `null`。同一隔离副本的只读重审计保存在 `credit-audit-member-diff-fixed.json`；8,320 条主分类及上述统计全部不变，5,126 条 `unresolved_provider_artist` 的双方独有成员字段均为 `null`，35 条已确认 `provider_additions` 仍有明确的 provider 独有 ID。例如 Spotify 和本地均显示 Katy Perry 的未解析记录现在只保留名称匹配候选，不再声称本地艺人独有。新旧报告除生成时间和这些未解析记录的两个辅助字段外完全一致；未重新请求 Spotify 或改写证据。

## 不变性与测试

独立未迁移快照与回填后副本按主键顺序导出的 SHA-256 完全一致：

| 表 | 行数 | SHA-256 |
|---|---:|---|
| `plays` | 94,760 | `d8235bc06f128cfd2ffc286cb8168c2f30afa43666639cf6142a685743acdd00` |
| `tracks` | 10,026 | `27b6cca20f20e8cdf0999cd1ac92941389949cfcba231b8fa2cc3fa53a334257` |
| `track_artists` | 10,496 | `3f5e88b0f6ee41fce7aa668686fa580ad53bf736330f5135a55320480d052c0d` |

`track_credit_overrides`、正式 `track_credit_events`、`track_credit_state` 与 `background_jobs` 的全行摘要也分别与未迁移快照一致；正式 track-credit revision 保持 37。回填只写 provider evidence 及缺少时的 `spotify_track_meta` 父行，没有生成下游重建任务。日常 metadata refresh 原有的专辑链接/播放来源维护行为未被本次改写，不能把此回填不变性外推为整个导入流程不写原始表。

- 审计字段勘误后重新执行 `.venv/bin/pytest -m 'unit or contract' -q`：2,435 passed，712 deselected，2 warnings；这是本地 backend unit/contract 范围，不是 fullstack Pass。
- 原交付阶段专项测试 28 passed，覆盖迁移重复执行、数组顺序、变化事件、数据库失败原子回滚、坏响应 LKG、重复回填、无凭据、批次部分 `null`、身份名称候选不自动匹配及现有刷新回归。本次勘误新增未解析、身份冲突、缺少 owner/证据及完整解析的回归断言；修复后单独运行证据测试文件为 13 passed，且已包含在上述全量 unit/contract 复跑中。
- `ruff check`、`ruff format --check` 对改动 Python 文件通过；`python3 scripts/docs_audit.py` 为 PASS；`git diff --check` 无问题。

## 剩余边界与发布

隔离验收时正式数据库仍是 schema 79，尚未在生产迁移或回填；当时本地代码修改也尚未提交、推送或部署。生产应按规划单独审批、Online Backup、分步迁移和验收。本次隔离审计的 5,126 个 unresolved Track 需要后续身份治理或第二来源核验；35 个 provider additions 只是候选，不应直接当成合作艺人自动晋升。语言、封面和其他 Spotify 字段问题继续留在后续路线中。
