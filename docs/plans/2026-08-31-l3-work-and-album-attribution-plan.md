# L3 作品与原生专辑归属实施计划

> 决策日期：2026-08-31
>
> 规则状态：CONFIRMED
>
> 实现状态：IMPLEMENTED
>
> 验证状态：IN_PROGRESS（代码门禁已通过，真实库与完整全栈待收口）
>
> 仓库状态：UNCOMMITTED
>
> 部署状态：NOT_DEPLOYED

## 1. 目标

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

## 2. 已确认规则

### 2.1 L3 歌曲作品

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

### 2.2 Taylor's Version 与其他重录专辑

原专辑与重录专辑在 L2 保持独立，在 L3 合并成一个专辑作品。L3 专辑曲目采用并集，不要求
一一对应：

- 原版与重录版的对应歌曲先在 L3 歌曲层合并；
- Vault 或重录版新增歌曲即使没有原版对应曲目，也纳入原专辑的 L3 专辑作品；
- 例如 `1989` 与 `1989 (Taylor's Version)` 归入同一个 L3 专辑作品，`Say Don't Go` 也计入
  `1989`。

### 2.3 Live 专辑

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

### 2.4 Remix、Acoustic 与其他版本发行

- 如果版本歌曲已有录音室专辑或基础单曲归属，则 L3 播放回流到该原生项目；
- Remix/Acoustic 单曲包若所有歌曲都已回流，其自身 L3 播放量为 0；
- 如果其中存在没有其他原生项目的独有歌曲，则独有歌曲仍保留在该项目；
- 已在 L2 被识别为同一标准版/豪华版发行项目的 Acoustic Collection 或 Long Pond 组合发行，
  继续保留 L2 项目关系；L3 的逐曲归属不能反向拆坏 L2。

### 2.5 原生专辑判定

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

## 3. 统计不变量

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

## 4. 当前实现差距

当前歌曲 L3 已能以 composition group 归并 Acoustic、Live、Remix 和 Taylor's Version；这部分可
继续复用。当前专辑 L3 仍存在两个结构性差距：

1. `album_composition_auto_merge.py` 把完整 L2 release project 作为不可拆分 child，只适合
   Taylor's Version 这类整张重录关系，无法表达一张巡演 Live 专辑中的歌曲分别回流到多张原专辑。
2. `load_album_project_membership()` 在 L3 canonical song key 上全局排序后
   `drop_duplicates("canonical_song_key")`。它没有持久化“为什么这首歌属于这个项目”的决定，
   可能让共享歌曲的普通项目因排序被静默丢弃。

新实现不能继续通过调高/调低 album overlap 阈值解决这两个问题；需要引入歌曲作品到专辑作品的
显式归属层。

## 5. 目标数据模型

### 5.1 保留现有关系

- `track_groups(scope='composition')`：L3 歌曲作品及其版本成员；
- `album_projects(scope='release')`：L2 标准版/豪华版等发行项目；
- `album_projects(scope='composition')`：Taylor's Version 等完整专辑作品父项目；
- `album_project_tracks`：每个 L2/L3 项目的目录 membership；
- `plays.source_album_id`：真实播放来源。

### 5.2 新增派生归属表

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

### 5.3 新增稳定人工覆盖表

建议新增 `l3_song_album_attribution_overrides`：

- 使用稳定 owner `track_id` 作为歌曲锚点；应用时解析到当前 L3 composition；
- 目标使用稳定 `album_project_id`，并要求指向活动项目；
- 支持 `force_target` 与 `force_keep_source`；
- 保存 reason、before/after 和操作者审计；
- 人工覆盖优先于机器归属，但不得创建一个 L3 歌曲多个 owner。

### 5.4 归属 revision

新增独立 `l3_album_attribution_revision_state`。它必须进入：

- L3 音乐查找 snapshot key；
- Billboard/Year-End 派生 key；
- 专辑详情和播放分析缓存 key；
- 增量导入 source fence。

歌曲关系或 album project revision 改变时必须重建归属。归属 revision 不变时，增量播放可以继续
使用同一映射；归属改变时先采用全量 shadow rebuild，不能把新旧映射混在一套快照里。

## 6. 自动归属算法

### 6.1 输入单元

对每个 L3 canonical song 收集：

- composition 内所有 L2 recording/singleton；
- 每个版本的 relation tags：original、rerecord、live、acoustic、remix 等；
- 各成员所在的 L2 release projects、membership role、source bucket 和 release date；
- canonical primary artist；
- 项目类型、是否 compilation、是否人工项目及是否有 composition parent。

### 6.2 候选生成

只从歌曲真实 membership 生成候选，不从名称相似的任意专辑全库搜索：

- 包含无版本标签原始录音的 studio/EP/soundtrack 项目；
- 包含该歌曲、并已明确承接先行单曲的正式专辑项目；
- 独立基础单曲项目；
- 如果歌曲只有 rerecord/vault 成员，则使用重录 child 的 composition parent；
- 如果歌曲只有 live/cover/现场独占成员，则当前 Live 项目作为 residual 候选。
- 现有共享 `TrackPresentation.album_project_id` 只有在其 `resolution_status` 明确成功时才可作为
  baseline owner 证据，不能把 fallback 或歧义结果升级成机器事实。

### 6.3 候选排序与门禁

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

### 6.4 目标项目解析

- 原生 L2 release project 存在活动 composition parent 时，`target_project_id` 指向 parent；
- 不存在 parent 时，指向该 release project 自身；
- Taylor's Version 的普通曲和 Vault 曲都指向原专辑的 composition parent；
- Live 曲目若找到录音室 owner，直接指向该 owner 或其 parent；
- Live residual 曲目指向 Live release project 自身。

## 7. 聚合实现

### 7.1 唯一入口

重构 `backend/domains/playback/album_projects.py`：

- L2 的 `load_album_project_membership()` 和聚合逻辑保持现状；
- L3 新增明确的 `load_l3_song_album_attributions()`；
- `compute_album_project_plays(..., merge_level=3)` 先为事件生成 L3 canonical song key，再与归属表
  一对一连接；
- 删除 L3 依赖全局 `drop_duplicates("canonical_song_key")` 决定 owner 的行为；
- 周聚合、详情、搜索 snapshot 和年份投影共用同一入口。

### 7.2 来源解释

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

### 7.3 详情与 UI

L3 Live 专辑详情需要展示三块互不混淆的数据：

1. 保留在本 Live 项目中的 residual 曲目与播放；
2. 已回流曲目及目标专辑；
3. 完整 source release 曲目清单和实际来源播放。

默认专辑榜只使用 residual 后的 L3 总量。来源发行页可以显示完整 Live 来源播放，但必须明确标注
“来源播放”，不能与榜单归属总量相加。

## 8. 实施阶段

### Phase A：契约测试与基线探针

- 先为当前真实库保存 L2/L3 项目、歌曲和 source breakdown 基线；
- 固化 `1989`、`Speak Now`、`Anti-Hero`、巡演 Live 专辑及当前异常消失项目样本；
- 新增失败中的契约测试，证明现实现无法逐曲回流且存在无解释丢项目。

### Phase B：Schema、resolver 与 dry-run planner

- 增加归属表、覆盖表和 revision migration；
- 实现只读候选生成、唯一 owner resolver、冲突和 evidence 输出；
- planner 支持 dry-run、输入 revision fence、幂等重跑和 policy version；
- 本阶段不切换任何统计消费者。

### Phase C：治理管线接入

- 在歌曲 L3 和 Album Project/L3 album lineage 收敛后运行归属 planner；
- apply 使用 savepoint/事务发布归属与 revision；
- 接入 `scripts/apply_l2_governance.py` 的计划、应用、收敛和审计报告（文件名为历史兼容）；
- L2 relationship digest 必须保持不变。

### Phase D：统一聚合入口

- 切换 `compute_album_project_plays()` 与 weekly 版本；
- 逐个对齐 Billboard、music search、entity stats、analysis、yearly review、Wrapped 和 AI read-only
  tools；
- 禁止消费者再次自行用 album name、source album 或排序去重决定 L3 owner。

### Phase E：详情和治理 UI

- 专辑详情返回 residual、transferred tracks、source breakdown；
- Settings 显示机器归属理由、冲突和人工覆盖；
- Desktop/Phone 使用同一 API 与 resolver；
- 0 residual 项目不进入默认榜，但来源入口和审计入口仍可访问。

### Phase F：派生数据与增量维护

- 把 attribution revision 纳入四套 L2/L3 × fixed/dynamic 搜索快照和 Year-End 投影；
- 首次切换执行 shared-full shadow rebuild；
- 只有 source fence 完全相同才允许增量复用；
- 失败时保留上一套完整 ready snapshot，不发布半套 L3。

### Phase G：真实数据库演练与发布

- 先用 SQLite Online Backup 生成至少两份独立副本；
- 在副本执行 migration、dry-run、apply、第二次 dry-run 和完整对账；
- 抽查 Taylor's Version、单曲 Remix、Live 跨专辑回流、Live residual 和不同艺人翻唱；
- 本轮“完整执行所有阶段”的授权覆盖通过两份独立副本后执行本地主库；主库执行前生成 Online
  Backup；
- 该授权不覆盖 push 或部署。

### 当前阶段状态

| 阶段 | 状态 | 当前证据 |
|---|---|---|
| Phase A | PASS | 真实库 dry-run 基线及 Taylor/Live/cover/多收录契约已固化 |
| Phase B | PASS | migration 68、planner、revision fence、幂等与 evidence 已实现 |
| Phase C | PASS | 联合治理事务、审计、收敛门禁与导入维护已接入 |
| Phase D | PASS | Billboard、搜索、详情、entity stats、年度、Wrapped 与 AI 缓存共用 owner revision |
| Phase E | PASS（代码） | Settings 治理快照/覆盖及 residual/transferred/source 详情已实现 |
| Phase F | PASS（代码） | 四套搜索/Year-End source fence 与导入健康已接入 |
| Phase G | IN_PROGRESS | 两份 Online Backup、副本 apply、主库和完整全栈待执行 |

## 9. 测试矩阵

### 9.1 单元与契约样本

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

### 9.2 数量守恒

- L3 track 总播放事件与切换前一致；
- 有 owner 的 L3 album 播放之和等于被归属事件数，不发生 fan-out；
- 每个 album 的 source buckets 之和等于 album total；
- Live source total = 回流事件 + residual 事件；
- Taylor parent total = 原版来源 + 重录来源 + 其他合法来源，且对应歌曲不重复计数；
- L2 全部结果、L2 relationship digest 和原始三表 hash 不变。

### 9.3 真实数据验收重点

- `1989`、`1989 (Taylor's Version)`、`Say Don't Go`；
- `Speak Now` 与 Taylor's Version；
- `The Show: Live From Madison Square Garden`、`The Show: Live On Tour`；
- `Live from Spotify Studios`；
- 当前 L3 因全局 canonical song 去重而无解释消失的 release projects；
- 至少一个 Remix 单曲包、一个 Acoustic 版本集合和一个不同艺人翻唱。

## 10. 回滚与失败边界

- 新归属表属于派生数据，回滚统计消费者即可恢复旧 L3 口径；原始事实不需要回滚；
- migration 只新增表、索引和 revision，不删除旧关系；
- 新旧统计口径切换必须由 policy/revision 明确区分，不能让缓存混用；
- planner 存在冲突、孤儿目标、重复 owner、revision 漂移或数量不守恒时拒绝发布；
- 正式 apply 与阶段 Git commit 已由本轮完整执行请求授权；push 和部署仍未授权。

## 11. 完成定义

只有同时满足以下条件，才能把本计划标记为 IMPLEMENTED/PASS：

1. 新关系和聚合入口已实现，所有 L3 专辑消费者共用；
2. Taylor's Version 曲目并集和 Live 逐曲回流契约测试通过；
3. 两份真实数据库副本演练收敛且数量守恒；
4. L2 与原始事实完全不变；
5. 四套搜索快照、Year-End、Billboard、详情和来源拆分对账通过；
6. Desktop/Phone 能解释 residual、回流目标和实际来源；
7. 默认完整全栈门禁通过；
8. 实现、验证、提交、push、部署状态分别如实记录。
