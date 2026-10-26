# L2与L3身份及专辑归属历史规划

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。身份与专辑归属修复、L3作品与原生归属两份规划合并，保留各自决策和治理条件。当前统计规则与后续交付另有入口，不从旧计划重新运行全量治理。

当前规则与状态见[文档地图](../../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [L2/L3 身份、专辑版本与归属完整性修复规划](#l2l3-身份专辑版本与归属完整性修复规划)
- [L3 作品与原生专辑归属实施计划](#l3-作品与原生专辑归属实施计划)

## L2/L3 身份、专辑版本与归属完整性修复规划

原记录：`2026-08-31-l2-l3-identity-and-album-attribution-remediation-plan.md`。

> 规划日期：2026-08-31
>
> 规则状态：CONFIRMED
>
> 实现状态：IMPLEMENTED
>
> 验证状态：PASS（真实数据、API、响应式与功能门禁；完整全栈状态见交付报告）
>
> 仓库状态：COMMITTED `cd6cf621`、`7fbaf420`；最终证据提交见本轮 Git 历史
>
> 部署状态：NOT_DEPLOYED

### 1. 目标与结论

本规划修复真实数据检查中暴露的四类问题，同时保留已经验证通过的 L2/L3 分层语义：

1. L2 Album Project 只能识别同一 Spotify Album ID，无法自动识别原版与 Remastered、Deluxe、
   Expanded 等不同 Spotify 发行 ID 的等价版本；
2. 没有 composition parent 的 L2 recording group 在 L3 专辑归属中退化为多个 `l1:<id>`，导致
   已经确认是同一首歌的成员重新拆开；
3. L3 专辑归属规划只扫描已有 `album_project_tracks` 的作品，完全缺失 membership 的作品没有进入
   `uncovered` 分母，健康接口可能在存在统计缺口时仍报告 healthy；
4. 少量 L1 owner 内部包含多个强冲突录音，L2/L3 无法修复已经发生在上游身份层的混装。

目标管线为：

```text
原始播放事实（只读）
  -> L1 稳定录音身份
  -> L2 recording group
  -> L2 release Album Project
  -> L3 composition/recording work key
  -> L3 唯一原生专辑归属
  -> 搜索、详情、播放分析、Billboard、Year-End
```

本规划已经获得后续执行授权并完成实施；真实执行始终保持 `plays`、`tracks`、`track_artists` 等
原始事实不被治理规则重写。完整结果见
[`../../reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md`](../../reports/2026-08-31-l2-l3-identity-and-album-attribution-remediation.md)。

### 2. 真实数据基线

以下数字来自 2026-08-31 当前主库的只读检查，实施前必须以同一过滤参数重新生成基线，不能把本节
数字永久硬编码为门禁：

| 检查项 | 当前结果 | 风险 |
|---|---:|---|
| 原始播放 / Track | 92,908 / 9,549 | 数据库完整性与外键检查通过 |
| 默认逻辑播放事件 | 66,419 | `min_ms=30000`、仅音乐、连续播放合并、5 分钟 gap |
| 活跃 L2 recording groups | 46 组 / 93 个 L1 成员 | L2 规划自身已收敛 |
| 没有 composition parent 的 L2 组 | 41 | 当前稳定 L3 key 把这些组重新拆成 L1 key |
| 已产生专辑 owner 拆分/缺失的 L2 组 | 28 | 490 个逻辑事件、约 31.51 小时 |
| 活跃 L3 stable works / 已归属 | 6,327 / 6,218 | 109 个作品没有归属行 |
| 默认统计中无归属作品 | 92 | 224 个逻辑事件、约 12.37 小时 |
| 两类 L3 问题去重影响 | 707 个事件 | 约 43.22 小时，占默认事件 1.06% |
| L1 strong internal identity conflict | 62 个 owner | 涉及 2,688 个默认逻辑事件，需分类而非一律拆分 |

#### 2.1 《孫燕姿同名專輯》定向证据

当前存在三个独立 release Album Project：

| 本地 album | Spotify 发行 | 年份 | 完整曲目 | 判断 |
|---|---|---:|---:|---|
| `1302 / 孫燕姿同名專輯` | `1WFT31Q7VuZAhiO41PKdWO` | 2000-06-09 | 10 | 原版，主项目候选 |
| `1523 / 同名專輯` | `6gbzwSVTIC9VWxViMEixQS` | 2000 | 10 | Remastered，应该与原版合并 |
| `1688 / 孫燕姿STEFANIE同名專輯` | `0yY7xP8LQky8jQwkC5Lu4Y` | 2004-10-26 | 12 | 不同专辑，必须保持独立 |

原版与 Remastered 的完整 Spotify 曲目在移除受控 `Remastered` 标记后：

- 曲名集合 10/10 完全一致；
- 曲序 10/10 完全一致；
- 单曲时长差约 0.03–3.33 秒；
- ISRC 全部不同，属于重制发行的正常差异，只能作为 warning；
- 2004 年专辑与前两版曲目交集为 0，可以稳定排除误合并。

数据库副本模拟将 album `1302`、`1523` 放入同一 release group 后，重建结果为一个稳定项目：主
项目仍是 `42176 / 孫燕姿同名專輯`，包含两个来源发行和 12 条原始 track membership；其中两对
原版/Remastered 曲目由 L2 recording group 去重，因此用户语义仍是 10 首歌。原始来源播放和来源
发行不丢失。

### 3. 不变量与非目标

#### 3.1 必须满足的不变量

1. L1 表达具体录音身份，不做 L2/L3 业务版本合并。
2. L2 相同 recording group 在任何 L3 消费链中只能解析成一个 stable work key。
3. 一个 L3 canonical song 最多一个默认专辑 owner。
4. 一个逻辑播放事件在默认 L3 专辑统计中最多贡献一次。
5. Album Project 合并只改变统计项目和 membership，不改写真实 source album。
6. 原版、Remastered、Deluxe 等来源必须继续出现在版本列表和 source breakdown。
7. Live、Acoustic、Remix 专辑继续逐曲回流，不因整体曲目重叠而被整张挂到某个录音室专辑。
8. Taylor's Version/明确重录专辑继续只在 L3 建立 album composition parent。
9. 规划器的扫描全集必须能对账：`attributed + intentionally_excluded + unresolved = scanned`。
10. 重建前后原始表行数、稳定事件集合、播放次数和播放时长守恒。

#### 3.2 非目标

- 本计划不决定一般精选集是否默认入榜；精选集策略继续冻结。
- 不把不同艺人翻唱合并为一个跨艺人的全球作曲作品。
- 不使用模糊标题相似度或固定百分比直接合并同名专辑。
- 不因为本地只播放过部分曲目，就把局部曲目交集错误升级为完整专辑身份。
- 不降低现有健康阈值或通过忽略 unresolved 让门禁变绿。

### 4. 根因矩阵

| 问题 | 当前根因 | 修复层 |
|---|---|---|
| 原版与 Remastered 未合并 | `spotify_complete_release_v1` 指纹要求相同 Spotify Album ID、精确日期和 Spotify Track ID 哈希 | Album Project 自动合并 v2 |
| L2 歌曲在 L3 专辑层拆开 | `load_l3_song_work_keys()` 无 composition 时直接生成 `l1:<id>` | L3 stable work key v2 |
| `uncovered=0` 但真实缺失 | `plan_l3_album_attributions()` 从 release memberships 出发，缺 membership 的作品未被扫描 | L3 attribution coverage v2 |
| soundtrack/多艺人发行缺 membership | Album Project eligibility/materialization 未覆盖部分真实 album containers | Album Project coverage repair |
| L1 owner 内部录音冲突 | 历史 migration external IDs 可能被挂到同一 owner | L1 owner repair planner |

### 5. Phase 0：可重复基线与发布护栏

优先级：P0。任何正式迁移前必须完成。

#### 5.1 新增只读完整性探针

新增 `scripts/l2_l3_integrity_probe.py`，默认只读连接数据库，并允许指向 Online Backup 副本。输出
JSON 和可读摘要，至少包含：

- 数据库 schema、track identity、album project、L3 attribution revision；
- L2 recording group 数、成员数、重复成员和自动 key 冲突；
- 每个 L2 group 解析出的 L3 stable key 数量；
- 活跃 L3 work 全集、归属、明确排除、unresolved 数量；
- 有播放但无 album membership/attribution 的事件数和时长；
- 一个 work 多 owner、一个事件多项目贡献、来源桶不守恒；
- L1 owner 内部 ISRC、provider ID、时长和版本标签冲突；
- 指定回归样本，包括孙燕姿、Taylor Swift、Showgirl、Long Pond 和 Live residual。

探针必须接受完整统计过滤参数，并把参数、revision 和数据库指纹写入输出。不同轮次只在参数和
revision 一致时比较。

#### 5.2 数据保护

- 正式重建只允许在 SQLite Online Backup 副本先演练；
- 记录原始事实表行数与内容 digest；
- 记录当前 release groups、track groups、attribution 和 snapshot revision；
- 正式应用前创建可恢复备份，不停服务、不直接在 live SQLite 上做冷构建；
- 所有规划器必须提供 dry-run、确定性 digest 和 stale-plan 校验。

#### 5.3 Phase 0 验收

- 同一副本连续两次探针结果完全一致；
- 探针能重现当前 41 个 stable-key split、109 个无归属 work 和 62 个 L1 风险 owner；
- 数据库使用只读 URI 时不会创建 schema、临时治理行或 revision。

### 6. Phase 1：Album Project 等价发行自动合并 v2

优先级：P0。目标 policy：`spotify_release_equivalence_v2`。

#### 6.1 保留两条独立证据通道

##### A. Exact release 通道

保留现有相同 Spotify Album ID、完整 track list 和 catalog metadata 的强证据路径，用于大小写、
Unicode、空白和重复来源容器合并。

##### B. Equivalent edition 通道

允许不同 Spotify Album ID 在强目录证据下归入同一 release Album Project。自动接受只允许以下
确定性关系：

1. `remaster_equivalent`
   - canonical album artist 相同；
   - 两边均为 album/EP，且不是 Live、Remix、Acoustic、Compilation；
   - 发行年份相同或一方只有年份精度；
   - 完整曲目数相同；
   - 移除受控版本标记后，完整曲名序列逐项完全一致；
   - 时长、ISRC 差异只写 warning。
2. `deluxe_superset`
   - canonical album artist 和基础项目名兼容；
   - 标准版完整曲名序列是豪华版的完整有序子序列；
   - 豪华版只增加曲目，不删除或替换标准版曲目；
   - Deluxe、Expanded、Anniversary 等包装标签必须来自受控词表。
3. `catalog_alias_equivalent`
   - 专辑标题不完全相同，但 canonical artist、发行年份和完整有序曲目序列完全一致；
   - 只在 100% 完整曲目证明下允许，用于《孫燕姿同名專輯》/《同名專輯》这类 catalog alias；
   - 不得把“同名专辑”“Greatest Hits”等泛化标题自身作为身份依据。

接近匹配、缺少完整 provider track list、不同年份且无明确 edition lineage、曲目被替换、跨艺人或
候选组件存在多个可能 owner 时全部 fail closed，并写入可审计候选，而不是人工逐条确认高置信
结果。

#### 6.2 曲目证据规范化

新增专用于发行证据的受控规范化，不直接复用宽松显示标题：

- Unicode NFKC、casefold、空白和标点规范化；
- 简繁归一；
- 仅移除末尾受控版本标签，如 `Remastered`、`Remaster 20xx`；
- Intro、Outro、Interlude、Reprise、Medley 等结构性标签不能被删除；
- 不按时长阈值拒绝同名正常歌曲，但把极端时长差记录为 warning；
- 原始 provider title、ISRC、时长和 track position 全部保留到 evidence。

#### 6.3 候选与应用模型

- `AlbumProjectAutoMergeCandidate` 从单一 `spotify_album_id` 扩展为多个 provider release IDs；
- candidate key 由 policy version、参与 album IDs、provider IDs 和证据 digest 组成；
- 每个参与 Spotify Album ID 都写入 `album_project_external_ids`，共同指向合并后的 project；
- canonical project 优先非版本化原版、日期精度更高、目录 membership 更完整的发行；
- release group 保存全部本地 album 成员；
- `version_governance_runs/events` 保存 before/after、relation type、完整证据和 warning；
- Apply 必须单事务、可回滚、可重复；再次规划结果应为 `changed=false`。

建议新增 `remaster` source bucket，准确解释来源；如不新增枚举，至少必须保留成员发行名并避免把
Remastered 错标为新的 `original_album`。

#### 6.4 明确排除

- `孫燕姿STEFANIE同名專輯` 因年份不同、12 首曲目与前两版交集为 0，保持独立；
- Live/Acoustic/Remix 项目不走整张 equivalent-edition 合并；
- Taylor's Version 不在 L2 equivalent-edition 通道合并；
- generic compilation 不因曲目包含关系自动并入录音室专辑。

#### 6.5 Phase 1 验收

- album `1302`、`1523` 归入同一 release project；album `1688` 保持独立；
- 合并项目拥有两个 Spotify Album external IDs，且只有一个 primary；
- 项目原始 track membership 为 12 条，L2 canonical song 集合为 10 首；
- 原版和 Remastered 来源播放全部保留，来源桶之和等于项目播放量；
- 全库 false-positive 反例覆盖跨艺人同名、同艺人不同同名专辑、Live、精选集和 soundtrack；
- 规划/apply/rebuild 再规划幂等。

### 7. Phase 2：L3 stable work key v2

优先级：P0。目标 policy：`l3_stable_work_key_v2`。

#### 7.1 新解析优先级

`load_l3_song_work_keys()` 必须与公共 L3 歌曲 resolver 使用同一关系图：

```text
direct active composition group
  > recording group's active composition parent
  > active recording group
  > singleton active L1 owner
```

稳定 key 分别为：

- `composition:<group_id>`；
- `recording:<group_id>`；
- `l1:<l1_id>`。

同时返回代表 L1、代表 Track、canonical name、scope 和 revision。一个 L1 同时解析到多个活动
composition 或 recording group 时必须报冲突，不按 SQL 顺序选择。

#### 7.2 消费链统一

以下路径必须统一调用 stable work key resolver，不得分别实现 fallback：

- L3 album attribution planner；
- `load_album_project_membership()` 与 `compute_album_project_plays()`；
- 音乐搜索与歌曲/专辑详情；
- Billboard、Year-End、播放分析和来源解释；
- 人工 attribution override 的 anchor 重解析。

现有人工覆盖继续锚定稳定 Track/L1 owner，不直接永久绑定会随治理变化的 key 字符串。key policy
升级后全量重建 attribution，不原地修改旧映射。

#### 7.3 Phase 2 验收

- 所有活动 L2 recording group 各自只解析出一个 L3 stable key；
- 当前 41 个 split group 降为 0；
- 《天黑黑》两个 L1 成员共同解析到 `recording:5914`；
- L2 与 L3 歌曲详情从任意成员进入时返回相同代表歌曲、成员范围和统计；
- 没有 recording/composition group 的 singleton 仍稳定回退到 `l1:<id>`；
- composition parent、Taylor's Version、Live 和 Remix 的既有用例不回归。

### 8. Phase 3：L3 Album Attribution coverage v2

优先级：P0。目标 policy：`l3_native_album_attribution_v2`。

#### 8.1 改变规划分母

规划器不能再从 `_load_release_memberships()` 的内连接结果直接开始。应先建立 `work_universe`：

1. 读取全部 active L3 stable works；
2. 标记是否存在原始播放、默认过滤后的逻辑播放、source album 和 provider metadata；
3. LEFT JOIN Album Project membership；
4. 对每个 work 产生且只产生以下一种状态：
   - `attributed`：唯一 target project；
   - `intentionally_excluded`：规则明确不进入默认专辑统计，但有理由和来源；
   - `unresolved`：缺 membership、冲突、无合法 owner 或覆盖失效。

状态对账必须写入 revision state：

```text
scanned_count
= attributed_count + intentionally_excluded_count + unresolved_count
```

健康接口分别报告 catalog universe 和 play-bearing universe。`ready` 只表示 projection 已发布；
`healthy` 还必须满足：

- 对账恒等式成立；
- 没有一个 work 多 owner；
- 没有默认有效播放落入 silent uncovered；
- 没有冲突或无效 override；
- state revision、mapping digest 与当前发布表一致。

#### 8.2 修复 Album Project membership 覆盖

复用 `resolve_album_project_eligibility()`，对有播放但无 membership 的 source albums 分类：

- 正式 album/EP：机器建立 release project 和 track membership；
- 官方 soundtrack：即使 album artist 为 Various Artists，也按 album artist 和完整 catalog release 建立
  soundtrack project，不能按单曲艺人拆散；
- album-bound single：归入已验证正式专辑，否则建立隐藏基础 single project；
- 独立 single：建立不入专辑榜的稳定 owner，仍允许歌曲归属和来源解释；
- generic compilation：继续遵守冻结策略；能找到原生 album owner 的歌曲回流，无法找到的歌曲
  明确标记 `compilation_policy_frozen` 或 `compilation_exclusive`，不能从分母消失；
- Live/Remix/Acoustic：继续逐曲回流或 residual，不整张强行合并。

针对当前缺口，至少建立 Frozen、Frozen 2、Moana、歌手 2018、Pitch Perfect 2 等 source album 的
分类回归样本；The Beatles `1` 等精选/合辑必须进入明确分类，而不是被健康检查忽略。

#### 8.3 issue 与治理 UI

- `l3_song_album_attribution_issues` 保存所有 unresolved；
- intentional exclusion 也必须保存稳定 reason code 和计数；
- Settings 健康卡显示总 work、已归属、明确排除、unresolved、受影响播放/时长和 revision；
- 高置信 album/project membership 自动修复，只有真正歧义才进入人工列表；
- 公共 API 不暴露内部调试字段，后台治理 API 保留完整 evidence。

#### 8.4 Phase 3 验收

- 当前 6,327 个 active work 全部进入同一可对账全集；
- 当前 109 个无归属 work 全部变为已归属、明确排除或显式 unresolved；
- 默认范围内 224 个事件不再 silent uncovered；
- 健康接口无法在存在 play-bearing unresolved 时返回 `healthy=true`；
- source breakdown、项目总量和全局事件总量守恒；
- 同一 stable key 在 attribution 表最多一行。

### 9. Phase 4：L1 owner 冲突分类与安全修复

优先级：P1，可与前三个 P0 阶段分开发行。目标是分类全部 62 个风险 owner，而不是按 ISRC 或时长
一刀切拆分。

#### 9.1 只读拆分规划器

新增 L1 owner audit/split planner，聚合：

- provider-observed 与 migration external IDs；
- Spotify Track ID、ISRC、标题语义、时长、album container 和首次/末次来源；
- source links 和原始播放引用；
- 当前 L2/L3 group membership。

输出三类决定：

1. `keep_provider_relink`：provider relink 或 reissue，证据证明是同一具体录音；
2. `auto_split_high_confidence`：不同录音/版本证据明确，可机器拆分；
3. `review_required`：证据冲突或不足，保留现状并进入人工审核。

不同 ISRC、时长差本身只产生风险信号。自动拆分至少要求互相支持的 provider ID、版本语义、发行
membership 或目录证据；不能把 remap/relink 误拆。

#### 9.2 应用边界

- 通过新的 L1 identity/alias 关系和审计事件修复，不改写原始 `plays`/`tracks`；
- 播放事件继续通过 source/provider evidence 解析到正确 L1 owner；
- 拆分后递增 track identity revision，并依次重建 L2、L3、Album Project attribution 和快照；
- apply 前后保存 source event 到 L1 的映射对账；
- 同一高置信方案二次运行必须幂等。

#### 9.3 Phase 4 验收

- 62 个风险 owner 全部被分类，有 evidence 和 reason；
- 高置信误合并完成机器拆分，歧义项明确留在 review queue；
- 不以“风险 owner 数为 0”作为虚假目标，合法 provider relink 可以保留；
- 原始事件集合、播放次数和时长不变；
- 拆分后的歌曲详情、专辑归属和搜索入口一致。

### 10. Phase 5：编排、revision、缓存与原子发布

#### 10.1 统一重建顺序

一次治理运行按依赖顺序执行：

```text
可选 L1 owner repair
  -> L2 recording / L3 composition governance
  -> Album Project equivalent-edition merge
  -> rebuild_album_projects
  -> rebuild L3 stable work keys / album attributions
  -> rebuild aggregations
  -> rebuild L2/L3 × dynamic/fixed search snapshots
  -> invalidate/rebuild Billboard and Year-End derived caches
  -> publish revision state
```

任何中间阶段失败都不能发布新 ready state。搜索、详情、Billboard 与 Year-End 不得混用新旧
track/album/attribution revision。

#### 10.2 应用与回滚

1. 主库只读 dry-run，生成计划 digest；
2. Online Backup 副本完成全量 apply、重建和验收；
3. 第二份独立副本重复执行，确认 mapping digest 和统计结果确定；
4. 正式应用前再次校验 source revision，漂移则拒绝使用旧计划；
5. 正式运行采用现有治理 run/event 审计，记录 before/after；
6. 失败时恢复备份及上一套 ready snapshot，不发布半成品；
7. 成功后再次运行规划，必须 `changed=false`。

不得通过降低 snapshot 容量、跳过 unresolved 或直接修改 revision state 绕过门禁。

### 11. API、Settings 与可观测性

#### 11.1 Dry-run/API

扩展现有版本治理接口，至少提供：

- Album Project exact/equivalent candidate 数与 reason breakdown；
- stable-key split group 数及样本；
- attribution scanned/attributed/excluded/unresolved 对账；
- unresolved 影响的逻辑播放数和时长；
- L1 conflict 分类摘要；
- policy/revision/input digest/mapping digest；
- apply job 状态、失败阶段和可重试性。

#### 11.2 Settings

后台默认机器执行强证据候选，人工只处理 fail-closed 项。界面至少展示：

- “可自动合并的等价发行”与证据；
- “L3 stable key 被拆分”作为阻断问题；
- “无专辑 membership/owner”及受影响播放；
- L1 owner 风险分类；
- 最近治理运行、revision 和重建状态。

界面不允许通过项目 ID 大小或 SQL 顺序手工暗示 owner；所有强制合并/分离继续使用稳定实体和审计
覆盖层。

### 12. 测试矩阵

#### 12.1 单元测试

扩展：

- `backend/tests/unit/test_album_project_auto_merge.py`
  - 不同 Spotify Album ID 的 Remastered 10/10 曲序等价；
  - 标准版/Deluxe 有序包含；
  - 同艺人不同同名专辑排除；
  - 跨艺人、Live、Compilation、缺完整目录和歧义候选排除；
  - 多 external IDs、primary 选择、审计和幂等。
- `backend/tests/unit/test_l3_album_attribution.py`
  - recording group fallback；
  - work universe LEFT JOIN coverage；
  - intentional exclusion 与 unresolved 对账；
  - 健康状态不能忽略无 membership 的 play-bearing work。
- 新增 L1 owner split planner 测试：provider relink 保留、高置信版本拆分、歧义 fail closed。

#### 12.2 契约与跨消费测试

- `backend/tests/contract/test_merge_level_aggregation.py`：L2/L3 key、代表歌曲和统计范围一致；
- `backend/tests/contract/test_l3_album_attribution_api.py`：健康分母、issue、override 和 revision；
- `backend/tests/contract/test_album_project_rules.py`：项目播放、来源桶和事件守恒；
- 搜索、详情、Billboard 和 Year-End 对同一 project/work 返回相同稳定 ID；
- 任意成员深链不能退回来源专辑局部统计。

#### 12.3 真实数据库副本验收

至少执行：

1. 当前完整性探针；
2. 两份 Online Backup 副本的确定性 dry-run/apply；
3. 孙燕姿三张标题相似专辑定向验收；
4. Taylor's Version、Showgirl Acoustic、Long Pond、Speak Now Live residual 回归；
5. Frozen/Frozen 2/Moana/歌手 2018/Pitch Perfect 2 coverage；
6. 受影响事件稳定 ID 集合、次数和时长前后对账；
7. source bucket 汇总与项目总量对账；
8. apply 后 planner 收敛检查。

#### 12.4 常规门禁

按风险和实现范围执行：

```bash
.venv/bin/pytest backend/tests/unit/test_album_project_auto_merge.py -q
.venv/bin/pytest backend/tests/unit/test_l3_album_attribution.py -q
.venv/bin/pytest backend/tests/contract/test_album_project_rules.py -q
.venv/bin/pytest backend/tests/contract/test_l3_album_attribution_api.py -q
.venv/bin/pytest backend/tests/contract/test_merge_level_aggregation.py -q
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
cd frontend && npm test
cd frontend && npm run build
python3 scripts/docs_audit.py
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://127.0.0.1:5173
```

局部测试只能标记 Partial；只有默认完整全栈的必需阶段全部通过，才能标记本地全栈 Pass。

### 13. 最终验收门禁

实施完成必须同时满足：

#### 功能正确性

- 《孫燕姿同名專輯》和《同名專輯 (Remastered)》是同一 L2 Album Project；
- 《孫燕姿STEFANIE同名專輯》保持独立；
- 《天黑黑》《愛情證書》的原版/Remastered 在歌曲与专辑统计中均只有一个 owner；
- Taylor's Version、Live 回流、Vault、Acoustic Collection 和 Long Pond 不回归。

#### 全库不变量

- L2 recording group -> L3 stable key 的一对多数量为 0；
- stable work -> 默认专辑 owner 的一对多数量为 0；
- play-bearing silent uncovered 为 0；
- attribution 全集对账恒等式成立；
- 当前已知 707 个受影响事件全部有新的明确归属或明确排除理由；
- 62 个 L1 风险 owner 全部完成机器分类或进入显式 review queue。

#### 数据与发布安全

- 原始事实表 hash 和行数不变；
- 项目总量、来源桶、转入/转出播放次数和时长守恒；
- 两份副本 mapping digest 一致；
- 正式 apply 后 planner `changed=false`；
- 所有消费快照引用同一组 revision；
- 失败演练能恢复上一套 ready 数据。

### 14. 建议实施拆分

为控制回归范围，建议按以下提交/交付批次实施，但未经用户明确授权不执行 Git commit：

1. **P0-A：探针与测试夹具**
   - 只读完整性探针、孙燕姿和 coverage fixtures；
2. **P0-B：Album Project equivalent edition v2**
   - 跨 Spotify release ID 证据、external IDs、source bucket 和审计；
3. **P0-C：L3 stable work key v2**
   - recording fallback、共享 resolver 和 attribution 重建；
4. **P0-D：Attribution coverage v2**
   - work universe、membership 修复、health/API/Settings；
5. **P1：L1 owner repair**
   - 只读分类、机器安全拆分和人工歧义队列；
6. **验收与发布**
   - 双副本、主库 apply、缓存/快照、API/浏览器和完整全栈。

P0-B、P0-C、P0-D 可以分别开发，但正式数据发布必须按第 10 节依赖顺序作为一次完整治理运行，
避免中间 revision 被消费端读取。

### 15. 与既有文档的关系

- 当前统计规则继续以 [`../../reference/playback-stats-rules.md`](../../reference/playback-stats-rules.md) 为准；
- 已完成的 L3 歌曲作品、Taylor's Version 和 Live 逐曲归属方案见
  [`2026-08-31-l3-work-and-album-attribution-plan.md`](#l3-作品与原生专辑归属实施计划)；
- 本计划不否定该方案的已验证部分，只修复真实数据揭示的 stable-key、coverage、等价发行和 L1 上游
  身份完整性缺口；
- 实施完成并通过完整验收后，本计划应移入 `docs/archive/06-productization-closeout/`，同时新增交付
  报告并更新当前规则、问题台账和 CHANGELOG。

## L3 作品与原生专辑归属实施计划

原记录：`2026-08-31-l3-work-and-album-attribution-plan.md`。

> 决策日期：2026-08-31
>
> 规则状态：CONFIRMED
>
> 实现状态：IMPLEMENTED
>
> 验证状态：PASS（两份副本、主库、真实 API/浏览器与默认完整全栈均通过）
>
> 仓库状态：COMMITTED（本轮 3 个阶段提交，见 Git 历史）
>
> 部署状态：NOT_DEPLOYED

### 1. 目标

L3 不再只回答“哪些版本属于同一个组”，而是回答两个连续问题：

1. 这次播放属于哪一个歌曲作品；
2. 这个歌曲作品的播放最终属于哪一个原生专辑作品。

目标管线为：

```text
逻辑播放事件
  -> L2 具体录音
  -> L3 歌曲作品
  -> L3 原生专辑归属
  -> 保留实际版本和 source album 作为来源解释
```

本计划不修改 `plays`、`tracks` 或 `track_artists`。L3 只新增可重建、可审计的关系和统计投影。

### 2. 已确认规则

#### 2.1 L3 歌曲作品

同一艺人体系下的同一歌曲作品，其原版、Taylor's Version/其他重录、Acoustic、Live、Remix、
Radio Edit、Instrumental、Demo、Session、Extended、Sped Up/Slowed 等版本全部归并到一个 L3
歌曲作品。单曲包中的多个 Remix 或 Acoustic 版本也遵循相同规则。

以下关系不得只凭标题自动归并：

- 不同艺人的翻唱；
- Intro、Outro、Interlude、Overture、Prelude、Prologue、Epilogue、Theme 等结构性曲目；
- Medley、Mashup、Parody、Sample、Translation；
- 同名但不是同一歌曲作品的曲目。

不同艺人的翻唱继续作为现场艺人自己的歌曲；除非未来另行建立“全球作曲作品”关系，否则不能把
翻唱播放计入原唱艺人的歌曲或专辑。

#### 2.2 Taylor's Version 与其他重录专辑

原专辑与重录专辑在 L2 保持独立，在 L3 合并成一个专辑作品。L3 专辑曲目采用并集，不要求
一一对应：

- 原版与重录版的对应歌曲先在 L3 歌曲层合并；
- Vault 或重录版新增歌曲即使没有原版对应曲目，也纳入原专辑的 L3 专辑作品；
- 例如 `1989` 与 `1989 (Taylor's Version)` 归入同一个 L3 专辑作品，`Say Don't Go` 也计入
  `1989`。

#### 2.3 Live 专辑

Live 专辑按歌曲逐项投影，不整张强行挂到某一张录音室专辑：

- 现场歌曲如果存在该艺人的原始录音室版本，播放归属到该歌曲作品及其原生专辑；
- 这次播放不再计入 Live 专辑的 L3 播放量；
- 不同艺人的翻唱、现场首次发布的原创歌曲、即兴曲目以及无法可靠找到原生专辑的歌曲，继续归属
  Live 专辑；
- Live 专辑扣除已回流曲目后仍有残余歌曲时，可以作为独立 L3 专辑实体正常入榜；
- Live 专辑所有歌曲都已回流时，其 L3 有效播放量为 0，默认专辑榜不展示，但来源发行视图仍可查询。

因此：

```text
Live 专辑 L3 播放量
= Live 来源中仍以该 Live 项目为原生归属的歌曲播放量
```

这不是从原始事实中删除播放，而是改变 L3 专辑统计归属。

#### 2.4 Remix、Acoustic 与其他版本发行

- 如果版本歌曲已有录音室专辑或基础单曲归属，则 L3 播放回流到该原生项目；
- Remix/Acoustic 单曲包若所有歌曲都已回流，其自身 L3 播放量为 0；
- 如果其中存在没有其他原生项目的独有歌曲，则独有歌曲仍保留在该项目；
- 已在 L2 被识别为同一标准版/豪华版发行项目的 Acoustic Collection 或 Long Pond 组合发行，
  继续保留 L2 项目关系；L3 的逐曲归属不能反向拆坏 L2。

#### 2.5 原生专辑判定

“原生专辑”是歌曲在艺人目录中的作品归属，不是任意再次收录它的 Spotify 容器。自动判定优先级：

1. 人工明确覆盖；
2. 原始录音室专辑的标准曲目；
3. 正式 EP 或原声带中的核心首次归属；
4. 后来进入正式专辑的先行单曲归入该正式专辑；
5. 从未进入专辑/EP/原声带的独立单曲归入其基础单曲项目；
6. 没有其他可靠归属的现场独有曲目、翻唱或即兴曲目留在 Live 项目。

精选集、Greatest Hits、Live、Remix、Acoustic 合集和重录 child 不能仅因再次收录歌曲而抢占
原生专辑。同一作品存在多个正常录音室候选时，优先最早发行的合法原生项目；稳定 ID 只在业务
角色与发行日期完全相同时保证输出确定性。只有目标失效、覆盖冲突或候选缺少必要目录事实时才进入
审计，不把正常的多次收录扩大成人工工作。

### 3. 统计不变量

1. 每个 L3 歌曲作品最多只有一个默认 L3 专辑 owner。
2. 每个逻辑播放事件在默认 L3 专辑统计中最多贡献一次。
3. L3 专辑总量按歌曲 owner 聚合，不按 source album 直接聚合。
4. L2 歌曲、L2 专辑及其 membership 不因 L3 投影改变。
5. 实际版本、实际 source album 和来源桶始终保留。
6. 一个专辑来源桶之和必须等于该专辑的 L3 播放量。
7. L3 归属变化前后，原始三表行数和内容 hash 不变。
8. 没有 composition parent 的普通 L2 release project 仍以自身作为 L3 专辑实体，不得无故消失。
9. 专辑从 L3 榜消失必须能解释为“全部歌曲明确投影到其他 owner”，不能来自任意
   `drop_duplicates()` 的保留顺序。

### 4. 当前实现差距

当前歌曲 L3 已能以 composition group 归并 Acoustic、Live、Remix 和 Taylor's Version；这部分可
继续复用。当前专辑 L3 仍存在两个结构性差距：

1. `album_composition_auto_merge.py` 把完整 L2 release project 作为不可拆分 child，只适合
   Taylor's Version 这类整张重录关系，无法表达一张巡演 Live 专辑中的歌曲分别回流到多张原专辑。
2. `load_album_project_membership()` 在 L3 canonical song key 上全局排序后
   `drop_duplicates("canonical_song_key")`。它没有持久化“为什么这首歌属于这个项目”的决定，
   可能让共享歌曲的普通项目因排序被静默丢弃。

新实现不能继续通过调高/调低 album overlap 阈值解决这两个问题；需要引入歌曲作品到专辑作品的
显式归属层。

### 5. 目标数据模型

#### 5.1 保留现有关系

- `track_groups(scope='composition')`：L3 歌曲作品及其版本成员；
- `album_projects(scope='release')`：L2 标准版/豪华版等发行项目；
- `album_projects(scope='composition')`：Taylor's Version 等完整专辑作品父项目；
- `album_project_tracks`：每个 L2/L3 项目的目录 membership；
- `plays.source_album_id`：真实播放来源。

#### 5.2 新增派生归属表

建议新增 `l3_song_album_attributions`。每个存在可验证目录项目的当前 L3 canonical song key 恰好
一条有效默认归属；无法解析的歌曲不制造 owner，而要进入 coverage/conflict 审计：

| 字段 | 用途 |
|---|---|
| `canonical_song_key` | 当前 revision 下的 `composition:<group_id>` 或 `l1:<owner_track_id>` |
| `canonical_artist_key` | 规范 primary artist 集合的稳定签名，防止跨艺人作品串联 |
| `target_project_id` | 最终接收 L3 播放的 release/composition album project |
| `origin_release_project_id` | 作为原生目录证据的 L2 release project |
| `attribution_kind` | `studio_album`、`ep`、`soundtrack`、`album_single`、`standalone_single`、`rerecord_union`、`live_residual` 等 |
| `decision_source` | `automatic` 或 `manual` |
| `confidence` | 机器决定的可解释置信度，不参与模糊自动放宽 |
| `evidence_json` | 候选、排除项、成员版本、来源项目和理由 |
| `policy_version` | 归属策略版本 |
| `track_identity_revision` | 生成时的歌曲关系 revision |
| `album_project_revision` | 生成时的专辑关系 revision |
| `created_at` / `updated_at` | 审计时间 |

该表是可重建派生关系。`canonical_song_key` 可能随 composition group 重建而变化，因此人工覆盖不能
只绑定该字符串。

#### 5.3 新增稳定人工覆盖表

建议新增 `l3_song_album_attribution_overrides`：

- 使用稳定 owner `track_id` 作为歌曲锚点；应用时解析到当前 L3 composition；
- 目标使用稳定 `album_project_id`，并要求指向活动项目；
- 支持 `force_target` 与 `force_keep_source`；
- 保存 reason、before/after 和操作者审计；
- 人工覆盖优先于机器归属，但不得创建一个 L3 歌曲多个 owner。

#### 5.4 归属 revision

新增独立 `l3_album_attribution_revision_state`。它必须进入：

- L3 音乐查找 snapshot key；
- Billboard/Year-End 派生 key；
- 专辑详情和播放分析缓存 key；
- 增量导入 source fence。

歌曲关系或 album project revision 改变时必须重建归属。归属 revision 不变时，增量播放可以继续
使用同一映射；归属改变时先采用全量 shadow rebuild，不能把新旧映射混在一套快照里。

### 6. 自动归属算法

#### 6.1 输入单元

对每个 L3 canonical song 收集：

- composition 内所有 L2 recording/singleton；
- 每个版本的 relation tags：original、rerecord、live、acoustic、remix 等；
- 各成员所在的 L2 release projects、membership role、source bucket 和 release date；
- canonical primary artist；
- 项目类型、是否 compilation、是否人工项目及是否有 composition parent。

#### 6.2 候选生成

只从歌曲真实 membership 生成候选，不从名称相似的任意专辑全库搜索：

- 包含无版本标签原始录音的 studio/EP/soundtrack 项目；
- 包含该歌曲、并已明确承接先行单曲的正式专辑项目；
- 独立基础单曲项目；
- 如果歌曲只有 rerecord/vault 成员，则使用重录 child 的 composition parent；
- 如果歌曲只有 live/cover/现场独占成员，则当前 Live 项目作为 residual 候选。
- 现有共享 `TrackPresentation.album_project_id` 只有在其 `resolution_status` 明确成功时才可作为
  baseline owner 证据，不能把 fallback 或歧义结果升级成机器事实。

#### 6.3 候选排序与门禁

机器选择必须基于有名称的业务证据，而不是 SQL 行顺序：

```text
manual override
> original studio standard membership
> album-bound pre-release single
> EP/soundtrack core membership
> standalone base single
> rerecord composition parent
> live/alternate residual project
```

同优先级存在多个候选时依次比较：核心 membership、非 compilation、canonical artist 一致、
明确的发行 lineage、发行日期和稳定 ID。正常 studio/EP/single 多收录以最早合法发行自动确定 owner；
稳定 ID 只在上述业务证据完全相同时作为输出稳定器。

fail closed 只处理无法形成合法目标、覆盖目标失效或同一作品出现互斥人工决定等真正异常；它不能
退回到 SQL 行顺序，也不能让同一事件 fan-out 到所有候选项目。

#### 6.4 目标项目解析

- 原生 L2 release project 存在活动 composition parent 时，`target_project_id` 指向 parent；
- 不存在 parent 时，指向该 release project 自身；
- Taylor's Version 的普通曲和 Vault 曲都指向原专辑的 composition parent；
- Live 曲目若找到录音室 owner，直接指向该 owner 或其 parent；
- Live residual 曲目指向 Live release project 自身。

### 7. 聚合实现

#### 7.1 唯一入口

重构 `backend/domains/playback/album_projects.py`：

- L2 的 `load_album_project_membership()` 和聚合逻辑保持现状；
- L3 新增明确的 `load_l3_song_album_attributions()`；
- `compute_album_project_plays(..., merge_level=3)` 先为事件生成 L3 canonical song key，再与归属表
  一对一连接；
- 删除 L3 依赖全局 `drop_duplicates("canonical_song_key")` 决定 owner 的行为；
- 周聚合、详情、搜索 snapshot 和年份投影共用同一入口。

#### 7.2 来源解释

聚合结果同时保留：

- `target_project_id`：统计归属；
- `source_album_id`：实际播放来源；
- `source_track_id` / 版本标签：实际录音来源；
- `attribution_kind`：为什么发生回流。

例如播放 `Love Story (Live)`：

```text
L3 song: Love Story
L3 album: Fearless
source release: 实际 Live 专辑
attribution: live_to_studio_origin
```

#### 7.3 详情与 UI

L3 Live 专辑详情需要展示三块互不混淆的数据：

1. 保留在本 Live 项目中的 residual 曲目与播放；
2. 已回流曲目及目标专辑；
3. 完整 source release 曲目清单和实际来源播放。

默认专辑榜只使用 residual 后的 L3 总量。来源发行页可以显示完整 Live 来源播放，但必须明确标注
“来源播放”，不能与榜单归属总量相加。

### 8. 实施阶段

#### Phase A：契约测试与基线探针

- 先为当前真实库保存 L2/L3 项目、歌曲和 source breakdown 基线；
- 固化 `1989`、`Speak Now`、`Anti-Hero`、巡演 Live 专辑及当前异常消失项目样本；
- 新增失败中的契约测试，证明现实现无法逐曲回流且存在无解释丢项目。

#### Phase B：Schema、resolver 与 dry-run planner

- 增加归属表、覆盖表和 revision migration；
- 实现只读候选生成、唯一 owner resolver、冲突和 evidence 输出；
- planner 支持 dry-run、输入 revision fence、幂等重跑和 policy version；
- 本阶段不切换任何统计消费者。

#### Phase C：治理管线接入

- 在歌曲 L3 和 Album Project/L3 album lineage 收敛后运行归属 planner；
- apply 使用 savepoint/事务发布归属与 revision；
- 接入 `scripts/apply_l2_governance.py` 的计划、应用、收敛和审计报告（文件名为历史兼容）；
- L2 relationship digest 必须保持不变。

#### Phase D：统一聚合入口

- 切换 `compute_album_project_plays()` 与 weekly 版本；
- 逐个对齐 Billboard、music search、entity stats、analysis、yearly review、Wrapped 和 AI read-only
  tools；
- 禁止消费者再次自行用 album name、source album 或排序去重决定 L3 owner。

#### Phase E：详情和治理 UI

- 专辑详情返回 residual、transferred tracks、source breakdown；
- Settings 显示机器归属理由、冲突和人工覆盖；
- Desktop/Phone 使用同一 API 与 resolver；
- 0 residual 项目不进入默认榜，但来源入口和审计入口仍可访问。

#### Phase F：派生数据与增量维护

- 把 attribution revision 纳入四套 L2/L3 × fixed/dynamic 搜索快照和 Year-End 投影；
- 首次切换执行 shared-full shadow rebuild；
- 只有 source fence 完全相同才允许增量复用；
- 失败时保留上一套完整 ready snapshot，不发布半套 L3。

#### Phase G：真实数据库演练与发布

- 先用 SQLite Online Backup 生成至少两份独立副本；
- 在副本执行 migration、dry-run、apply、第二次 dry-run 和完整对账；
- 抽查 Taylor's Version、单曲 Remix、Live 跨专辑回流、Live residual 和不同艺人翻唱；
- 本轮“完整执行所有阶段”的授权覆盖通过两份独立副本后执行本地主库；主库执行前生成 Online
  Backup；
- 该授权不覆盖 push 或部署。

#### 当前阶段状态

| 阶段 | 状态 | 当前证据 |
|---|---|---|
| Phase A | PASS | 真实库 dry-run 基线及 Taylor/Live/cover/多收录契约已固化 |
| Phase B | PASS | migration 68、planner、revision fence、幂等与 evidence 已实现 |
| Phase C | PASS | 联合治理事务、审计、收敛门禁与导入维护已接入 |
| Phase D | PASS | Billboard、搜索、详情、entity stats、年度、Wrapped 与 AI 缓存共用 owner revision |
| Phase E | PASS | Settings 与专辑归属解释已通过 Desktop/390px 及完整浏览器门禁 |
| Phase F | PASS | 四套搜索快照 ready、failed 为 0；Year-End source fence 与导入健康已接入 |
| Phase G | PASS | 两份 Online Backup、副本 apply/复跑、主库、真实 API 与 7 阶段全栈门禁均通过 |

### 9. 测试矩阵

#### 9.1 单元与契约样本

| 场景 | 预期 |
|---|---|
| `Love Story` 原版/TV/Live/Remix | 一个 L3 song，专辑归属 `Fearless` |
| `1989` + Taylor's Version + Vault | 一个 L3 album，曲目并集包含 Vault |
| 巡演 Live 同时包含多张录音室专辑曲目 | 各曲分别回流，不把整张 Live 挂到某一张专辑 |
| Live 中不同艺人翻唱 | 不与原唱自动合并，保留 Live residual |
| Live 中现场首次原创 | 保留 Live residual |
| Live 全部曲目均可回流 | L3 residual 为 0，默认榜不展示，来源视图仍存在 |
| Remix single package | 版本并入同一 L3 song，播放回流原生 album/single |
| `Intro`/`Outro`/`Interlude` | 不因普通同名或版本后缀自动合并 |
| 精选集重复收录 | 不抢占原生 owner；当前精选集产品开关仍按既有冻结策略 |
| 同歌出现在多个候选 studio projects | 按业务角色和最早合法发行自动归属；稳定 ID 只处理完全同证据 tie |

#### 9.2 数量守恒

- L3 track 总播放事件与切换前一致；
- 有 owner 的 L3 album 播放之和等于被归属事件数，不发生 fan-out；
- 每个 album 的 source buckets 之和等于 album total；
- Live source total = 回流事件 + residual 事件；
- Taylor parent total = 原版来源 + 重录来源 + 其他合法来源，且对应歌曲不重复计数；
- L2 全部结果、L2 relationship digest 和原始三表 hash 不变。

#### 9.3 真实数据验收重点

- `1989`、`1989 (Taylor's Version)`、`Say Don't Go`；
- `Speak Now` 与 Taylor's Version；
- `The Show: Live From Madison Square Garden`、`The Show: Live On Tour`；
- `Live from Spotify Studios`；
- 当前 L3 因全局 canonical song 去重而无解释消失的 release projects；
- 至少一个 Remix 单曲包、一个 Acoustic 版本集合和一个不同艺人翻唱。

### 10. 回滚与失败边界

- 新归属表属于派生数据，回滚统计消费者即可恢复旧 L3 口径；原始事实不需要回滚；
- migration 只新增表、索引和 revision，不删除旧关系；
- 新旧统计口径切换必须由 policy/revision 明确区分，不能让缓存混用；
- planner 存在冲突、孤儿目标、重复 owner、revision 漂移或数量不守恒时拒绝发布；
- 正式 apply 与阶段 Git commit 已由本轮完整执行请求授权；push 和部署仍未授权。

### 11. 完成定义

只有同时满足以下条件，才能把本计划标记为 IMPLEMENTED/PASS：

1. 新关系和聚合入口已实现，所有 L3 专辑消费者共用；
2. Taylor's Version 曲目并集和 Live 逐曲回流契约测试通过；
3. 两份真实数据库副本演练收敛且数量守恒；
4. L2 与原始事实完全不变；
5. 四套搜索快照、Year-End、Billboard、详情和来源拆分对账通过；
6. Desktop/Phone 能解释 residual、回流目标和实际来源；
7. 默认完整全栈门禁通过；
8. 实现、验证、提交、push、部署状态分别如实记录。
