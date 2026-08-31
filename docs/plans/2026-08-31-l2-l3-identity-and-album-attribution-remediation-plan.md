# L2/L3 身份、专辑版本与归属完整性修复规划

> 规划日期：2026-08-31
>
> 规则状态：CONFIRMED
>
> 实现状态：PLANNED
>
> 验证状态：NOT_RUN
>
> 仓库状态：UNCOMMITTED
>
> 部署状态：NOT_DEPLOYED

## 1. 目标与结论

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

本轮规划不授权修改业务代码、正式数据库或生产环境。实施必须另行执行，并始终保持 `plays`、
`tracks`、`track_artists` 等原始事实不被治理规则重写。

## 2. 真实数据基线

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

### 2.1 《孫燕姿同名專輯》定向证据

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

## 3. 不变量与非目标

### 3.1 必须满足的不变量

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

### 3.2 非目标

- 本计划不决定一般精选集是否默认入榜；精选集策略继续冻结。
- 不把不同艺人翻唱合并为一个跨艺人的全球作曲作品。
- 不使用模糊标题相似度或固定百分比直接合并同名专辑。
- 不因为本地只播放过部分曲目，就把局部曲目交集错误升级为完整专辑身份。
- 不降低现有健康阈值或通过忽略 unresolved 让门禁变绿。

## 4. 根因矩阵

| 问题 | 当前根因 | 修复层 |
|---|---|---|
| 原版与 Remastered 未合并 | `spotify_complete_release_v1` 指纹要求相同 Spotify Album ID、精确日期和 Spotify Track ID 哈希 | Album Project 自动合并 v2 |
| L2 歌曲在 L3 专辑层拆开 | `load_l3_song_work_keys()` 无 composition 时直接生成 `l1:<id>` | L3 stable work key v2 |
| `uncovered=0` 但真实缺失 | `plan_l3_album_attributions()` 从 release memberships 出发，缺 membership 的作品未被扫描 | L3 attribution coverage v2 |
| soundtrack/多艺人发行缺 membership | Album Project eligibility/materialization 未覆盖部分真实 album containers | Album Project coverage repair |
| L1 owner 内部录音冲突 | 历史 migration external IDs 可能被挂到同一 owner | L1 owner repair planner |

## 5. Phase 0：可重复基线与发布护栏

优先级：P0。任何正式迁移前必须完成。

### 5.1 新增只读完整性探针

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

### 5.2 数据保护

- 正式重建只允许在 SQLite Online Backup 副本先演练；
- 记录原始事实表行数与内容 digest；
- 记录当前 release groups、track groups、attribution 和 snapshot revision；
- 正式应用前创建可恢复备份，不停服务、不直接在 live SQLite 上做冷构建；
- 所有规划器必须提供 dry-run、确定性 digest 和 stale-plan 校验。

### 5.3 Phase 0 验收

- 同一副本连续两次探针结果完全一致；
- 探针能重现当前 41 个 stable-key split、109 个无归属 work 和 62 个 L1 风险 owner；
- 数据库使用只读 URI 时不会创建 schema、临时治理行或 revision。

## 6. Phase 1：Album Project 等价发行自动合并 v2

优先级：P0。目标 policy：`spotify_release_equivalence_v2`。

### 6.1 保留两条独立证据通道

#### A. Exact release 通道

保留现有相同 Spotify Album ID、完整 track list 和 catalog metadata 的强证据路径，用于大小写、
Unicode、空白和重复来源容器合并。

#### B. Equivalent edition 通道

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

### 6.2 曲目证据规范化

新增专用于发行证据的受控规范化，不直接复用宽松显示标题：

- Unicode NFKC、casefold、空白和标点规范化；
- 简繁归一；
- 仅移除末尾受控版本标签，如 `Remastered`、`Remaster 20xx`；
- Intro、Outro、Interlude、Reprise、Medley 等结构性标签不能被删除；
- 不按时长阈值拒绝同名正常歌曲，但把极端时长差记录为 warning；
- 原始 provider title、ISRC、时长和 track position 全部保留到 evidence。

### 6.3 候选与应用模型

- `AlbumProjectAutoMergeCandidate` 从单一 `spotify_album_id` 扩展为多个 provider release IDs；
- candidate key 由 policy version、参与 album IDs、provider IDs 和证据 digest 组成；
- 每个参与 Spotify Album ID 都写入 `album_project_external_ids`，共同指向合并后的 project；
- canonical project 优先非版本化原版、日期精度更高、目录 membership 更完整的发行；
- release group 保存全部本地 album 成员；
- `version_governance_runs/events` 保存 before/after、relation type、完整证据和 warning；
- Apply 必须单事务、可回滚、可重复；再次规划结果应为 `changed=false`。

建议新增 `remaster` source bucket，准确解释来源；如不新增枚举，至少必须保留成员发行名并避免把
Remastered 错标为新的 `original_album`。

### 6.4 明确排除

- `孫燕姿STEFANIE同名專輯` 因年份不同、12 首曲目与前两版交集为 0，保持独立；
- Live/Acoustic/Remix 项目不走整张 equivalent-edition 合并；
- Taylor's Version 不在 L2 equivalent-edition 通道合并；
- generic compilation 不因曲目包含关系自动并入录音室专辑。

### 6.5 Phase 1 验收

- album `1302`、`1523` 归入同一 release project；album `1688` 保持独立；
- 合并项目拥有两个 Spotify Album external IDs，且只有一个 primary；
- 项目原始 track membership 为 12 条，L2 canonical song 集合为 10 首；
- 原版和 Remastered 来源播放全部保留，来源桶之和等于项目播放量；
- 全库 false-positive 反例覆盖跨艺人同名、同艺人不同同名专辑、Live、精选集和 soundtrack；
- 规划/apply/rebuild 再规划幂等。

## 7. Phase 2：L3 stable work key v2

优先级：P0。目标 policy：`l3_stable_work_key_v2`。

### 7.1 新解析优先级

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

### 7.2 消费链统一

以下路径必须统一调用 stable work key resolver，不得分别实现 fallback：

- L3 album attribution planner；
- `load_album_project_membership()` 与 `compute_album_project_plays()`；
- 音乐搜索与歌曲/专辑详情；
- Billboard、Year-End、播放分析和来源解释；
- 人工 attribution override 的 anchor 重解析。

现有人工覆盖继续锚定稳定 Track/L1 owner，不直接永久绑定会随治理变化的 key 字符串。key policy
升级后全量重建 attribution，不原地修改旧映射。

### 7.3 Phase 2 验收

- 所有活动 L2 recording group 各自只解析出一个 L3 stable key；
- 当前 41 个 split group 降为 0；
- 《天黑黑》两个 L1 成员共同解析到 `recording:5914`；
- L2 与 L3 歌曲详情从任意成员进入时返回相同代表歌曲、成员范围和统计；
- 没有 recording/composition group 的 singleton 仍稳定回退到 `l1:<id>`；
- composition parent、Taylor's Version、Live 和 Remix 的既有用例不回归。

## 8. Phase 3：L3 Album Attribution coverage v2

优先级：P0。目标 policy：`l3_native_album_attribution_v2`。

### 8.1 改变规划分母

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

### 8.2 修复 Album Project membership 覆盖

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

### 8.3 issue 与治理 UI

- `l3_song_album_attribution_issues` 保存所有 unresolved；
- intentional exclusion 也必须保存稳定 reason code 和计数；
- Settings 健康卡显示总 work、已归属、明确排除、unresolved、受影响播放/时长和 revision；
- 高置信 album/project membership 自动修复，只有真正歧义才进入人工列表；
- 公共 API 不暴露内部调试字段，后台治理 API 保留完整 evidence。

### 8.4 Phase 3 验收

- 当前 6,327 个 active work 全部进入同一可对账全集；
- 当前 109 个无归属 work 全部变为已归属、明确排除或显式 unresolved；
- 默认范围内 224 个事件不再 silent uncovered；
- 健康接口无法在存在 play-bearing unresolved 时返回 `healthy=true`；
- source breakdown、项目总量和全局事件总量守恒；
- 同一 stable key 在 attribution 表最多一行。

## 9. Phase 4：L1 owner 冲突分类与安全修复

优先级：P1，可与前三个 P0 阶段分开发行。目标是分类全部 62 个风险 owner，而不是按 ISRC 或时长
一刀切拆分。

### 9.1 只读拆分规划器

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

### 9.2 应用边界

- 通过新的 L1 identity/alias 关系和审计事件修复，不改写原始 `plays`/`tracks`；
- 播放事件继续通过 source/provider evidence 解析到正确 L1 owner；
- 拆分后递增 track identity revision，并依次重建 L2、L3、Album Project attribution 和快照；
- apply 前后保存 source event 到 L1 的映射对账；
- 同一高置信方案二次运行必须幂等。

### 9.3 Phase 4 验收

- 62 个风险 owner 全部被分类，有 evidence 和 reason；
- 高置信误合并完成机器拆分，歧义项明确留在 review queue；
- 不以“风险 owner 数为 0”作为虚假目标，合法 provider relink 可以保留；
- 原始事件集合、播放次数和时长不变；
- 拆分后的歌曲详情、专辑归属和搜索入口一致。

## 10. Phase 5：编排、revision、缓存与原子发布

### 10.1 统一重建顺序

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

### 10.2 应用与回滚

1. 主库只读 dry-run，生成计划 digest；
2. Online Backup 副本完成全量 apply、重建和验收；
3. 第二份独立副本重复执行，确认 mapping digest 和统计结果确定；
4. 正式应用前再次校验 source revision，漂移则拒绝使用旧计划；
5. 正式运行采用现有治理 run/event 审计，记录 before/after；
6. 失败时恢复备份及上一套 ready snapshot，不发布半成品；
7. 成功后再次运行规划，必须 `changed=false`。

不得通过降低 snapshot 容量、跳过 unresolved 或直接修改 revision state 绕过门禁。

## 11. API、Settings 与可观测性

### 11.1 Dry-run/API

扩展现有版本治理接口，至少提供：

- Album Project exact/equivalent candidate 数与 reason breakdown；
- stable-key split group 数及样本；
- attribution scanned/attributed/excluded/unresolved 对账；
- unresolved 影响的逻辑播放数和时长；
- L1 conflict 分类摘要；
- policy/revision/input digest/mapping digest；
- apply job 状态、失败阶段和可重试性。

### 11.2 Settings

后台默认机器执行强证据候选，人工只处理 fail-closed 项。界面至少展示：

- “可自动合并的等价发行”与证据；
- “L3 stable key 被拆分”作为阻断问题；
- “无专辑 membership/owner”及受影响播放；
- L1 owner 风险分类；
- 最近治理运行、revision 和重建状态。

界面不允许通过项目 ID 大小或 SQL 顺序手工暗示 owner；所有强制合并/分离继续使用稳定实体和审计
覆盖层。

## 12. 测试矩阵

### 12.1 单元测试

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

### 12.2 契约与跨消费测试

- `backend/tests/contract/test_merge_level_aggregation.py`：L2/L3 key、代表歌曲和统计范围一致；
- `backend/tests/contract/test_l3_album_attribution_api.py`：健康分母、issue、override 和 revision；
- `backend/tests/contract/test_album_project_rules.py`：项目播放、来源桶和事件守恒；
- 搜索、详情、Billboard 和 Year-End 对同一 project/work 返回相同稳定 ID；
- 任意成员深链不能退回来源专辑局部统计。

### 12.3 真实数据库副本验收

至少执行：

1. 当前完整性探针；
2. 两份 Online Backup 副本的确定性 dry-run/apply；
3. 孙燕姿三张标题相似专辑定向验收；
4. Taylor's Version、Showgirl Acoustic、Long Pond、Speak Now Live residual 回归；
5. Frozen/Frozen 2/Moana/歌手 2018/Pitch Perfect 2 coverage；
6. 受影响事件稳定 ID 集合、次数和时长前后对账；
7. source bucket 汇总与项目总量对账；
8. apply 后 planner 收敛检查。

### 12.4 常规门禁

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

## 13. 最终验收门禁

实施完成必须同时满足：

### 功能正确性

- 《孫燕姿同名專輯》和《同名專輯 (Remastered)》是同一 L2 Album Project；
- 《孫燕姿STEFANIE同名專輯》保持独立；
- 《天黑黑》《愛情證書》的原版/Remastered 在歌曲与专辑统计中均只有一个 owner；
- Taylor's Version、Live 回流、Vault、Acoustic Collection 和 Long Pond 不回归。

### 全库不变量

- L2 recording group -> L3 stable key 的一对多数量为 0；
- stable work -> 默认专辑 owner 的一对多数量为 0；
- play-bearing silent uncovered 为 0；
- attribution 全集对账恒等式成立；
- 当前已知 707 个受影响事件全部有新的明确归属或明确排除理由；
- 62 个 L1 风险 owner 全部完成机器分类或进入显式 review queue。

### 数据与发布安全

- 原始事实表 hash 和行数不变；
- 项目总量、来源桶、转入/转出播放次数和时长守恒；
- 两份副本 mapping digest 一致；
- 正式 apply 后 planner `changed=false`；
- 所有消费快照引用同一组 revision；
- 失败演练能恢复上一套 ready 数据。

## 14. 建议实施拆分

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

## 15. 与既有文档的关系

- 当前统计规则继续以 [`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md) 为准；
- 已完成的 L3 歌曲作品、Taylor's Version 和 Live 逐曲归属方案见
  [`../archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md`](../archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md)；
- 本计划不否定该方案的已验证部分，只修复真实数据揭示的 stable-key、coverage、等价发行和 L1 上游
  身份完整性缺口；
- 实施完成并通过完整验收后，本计划应移入 `docs/archive/06-productization-closeout/`，同时新增交付
  报告并更新当前规则、问题台账和 CHANGELOG。
