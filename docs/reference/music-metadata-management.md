# 音乐源数据管理与曲目署名规则

## 1. 管理入口与边界

Settings 的“音乐源数据管理”是人工音乐事实治理的唯一入口，分为“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块。“归并与版本”先选择“歌曲归并 / 专辑归并”，再共用“自动检测 / 已保存分组 / 手动创建”三类任务。对象切换在三个任务中始终可见；手动创建统一采用“选择成员 → 配置代表版本与层级 → 确认保存”三步流程；用户只选择 L2/L3，不提供 L1 统计开关。专辑自动检测额外提供重叠率，Album Projects 重建归入维护工具，不再以另一套工作台或隐藏的对象入口呈现。单曲详情的“编辑”先展示“归并歌曲版本 / 调整曲目署名 / 管理艺人身份”动作菜单，再以实体参数和返回地址深链到唯一治理入口；专辑和艺人详情同样只提供深链，不能复制写逻辑。

歌曲手动归并必须允许搜索并明确选择两个不同的 owner `track_id`、指定代表版本和生效层级。`tracks.track_id` 是唯一的应用、统计和公开歌曲身份，不再另建 canonical track ID。一个 `track_id` 可以拥有多个 Spotify Track ID；一个 Spotify Track ID 必须且只能归属于一个现有 `track_id`。历史原始 Track ID、兼容 L1 ID、Spotify ID 和名称候选进入治理工作区前必须统一经过 `spotify_track_owners` 解析；不拥有任何 Spotify ID 且已投影到其他 owner 的兼容壳记录不得单独展示或写入分组。新导入记录先按 Spotify owner 命中已有 `track_id`；没有 owner 时才沿用既有“艺人 + 曲名”匹配或创建 track，再登记 owner。日常版本关系只在 L2 `recording`（产品意义上的同一首基础歌曲；内部 scope 名为历史兼容）或 L3 `composition`（同一作品，包括重录、现场、Acoustic、Remix 等）建立。

歌曲与专辑的“已保存分组”必须使用一致的卡片结构与成员操作。歌曲分组以稳定 `track_id` 列出成员，并支持切换代表曲目、移除非代表成员和删除覆盖组；当前活动 L2/L3 关系以 `track_group_l1_members` 为准，其中 `l1_id` 必须等于对应 owner `track_id`，`track_group_members` 只保留旧版兼容数据，不得作为新自动任务的写入或统计来源。每个成员默认折叠其历史来源，展开后显示代表来源、封面、有效艺人和来源冲突。这些操作不得修改原始 `tracks`、`plays` 或署名事实。

播放归属优先使用事件发生时保存的 `plays.spotify_track_id_at_play`，仅在缺失时回退 `tracks.spotify_track_id`，再通过 `spotify_track_owners` 解析到唯一 `track_id`；没有 Spotify ID 时直接使用 `plays.track_id`。已登记 owner 不能因名称、简繁、艺人、专辑、封面、ISRC 或时长变化而自动改写。确定性历史回填按“有播放记录优先、播放行数最多、艺人与专辑元数据更完整、最后取最小稳定 track_id”选择 owner，并保留人工纠错的扩展位。

歌曲详情的摘要统计、最近播放和播放日历必须与全局曲目榜共用同一 L2/L3 分组解析：L2 只取当前活动 `recording` 组，不跟随其 `composition` 父组；L3 才将子录音组和父作品组的成员纳入同一范围。请求分组内任一成员都应返回同一代表 `track_id` 和相同合计；最近播放行仍保留实际来源版本，便于用户理解统计构成。

L2/L3 歌曲的专辑展示不是 Track owner 事实，也不能修改 `tracks.album_id`。统一的
`backend/domains/metadata/track_presentation.py` 只读解析器把以下身份分开：统计歌曲、归属
Album Project、页面展示的具体发行版和提供封面的具体发行版。原版 catalog containment 可以纠正
仅由播放观察造成的 deluxe membership，但只改变展示结果，不回写 Album Project 治理表；胜出的
原版 provider 必须经过项目日期、精确标题、类型和稳定 ID 消歧，禁止把一个 local album 的所有
Spotify links 曲目表做并集。播放明细继续使用 `COALESCE(plays.source_album_id,
tracks.album_id)` 展示实际来源专辑和封面。

歌曲详情和新生成的深链统一使用 `/music/tracks/{track_id}`。旧 `/music/tracks/l1/{id}` 与 `/music/tracks/canonical/{id}` 仅作为隐藏兼容重定向，不能再出现在新链接或 OpenAPI。

L1 不作为设置项或人工合并层级，原“高级：基础身份纠错”入口关闭。底层只执行 Spotify ID 单一归属不变量；需要修正 owner 时必须走单独的受审计数据治理流程，不能通过 L2/L3 或公开 canonical merge/split API 生成新歌曲身份。

L2 默认由机器维护。canonical primary artist 相同且 L2 语义规范化歌名相同的 L1 identities 默认自动
进入同一活动 `recording` group；规范化会移除大小写、简繁、Unicode/空白/等价标点以及 Explicit、
Clean、Bonus、Remaster 和 Soundtrack/source context 等发行说明，但保留 Acoustic、Live、Remix、
Radio Edit、Demo、Instrumental、Taylor's Version/重录、Original/Single/Album Version、Extended、
Sped Up/Slowed 和参与艺人变化。普通同艺人同语义标题直接 accepted，不以 ISRC、时长、来源专辑或
零播放/零外部证据否决；这些差异只写入审计 warning。`Intro`、`Outro`、`Interlude`、`Overture`、
`Prelude`、`Prologue`、`Epilogue`、`Theme` 等结构性标题及其编号/副标题形式一律 deterministic
rejected，不进入人工待审队列；只有显式 `force_merge` 才能覆盖。不同规范标题共享 ISRC 时仍保留
艺人、语义版本和兼容时长均一致的保守 fallback。人工审核只处理显式 `force_merge` /
`force_separate` 例外，且 `force_separate` 优先于 `force_merge` 和自动规则。

L3 同样由机器维护，但不会拆散 L2。自动任务把完整活动 `recording` group 和未分组 L1 owner
作为不可拆分输入，用 canonical primary artist 与受控作品基础标题识别 composition。Acoustic、
Live、Remix、Taylor's Version、Radio Edit、Instrumental、Demo、Extended、Sped Up / Slowed、
Karaoke、Acapella、Rehearsal 及允许的 alternate arrangement 在 L2 保持独立，满足 L3 门禁后自动
accepted；L2 的 `semantic_version_conflict` 是层级分流，不是全局 rejected。translation、cover、
mashup、parody、sample、reprise、结构性标题、艺人不相容和歧义证据在 L3 fail closed。ISRC、
时长和 source context 差异只记 warning。人工 `force_merge` / `force_separate` 通过独立覆盖表持久化，
可在 Settings 清除；`force_separate` 始终优先，所有机器与人工决定都记录 scope、policy version、
evidence 和 before/after 审计。

Album Project 同样优先机器归并同名大小写差异和 catalog 证据完整的标准/豪华/expanded 发行。
共享 `album_spotify_links` 不是充分条件，必须同时核对 canonical album artist、发行日期/类型与完整
track list。一个项目可以包含不同 recording key 的 Acoustic、Long Pond 或 rehearsal 额外曲目；
这只改变专辑项目 membership，不会把这些歌曲在 L2 曲目榜合成原版录音。精选集策略未定期间，
自动任务不得改变 compilation project 的现有 membership 或榜单资格。

Album Project 的同家族发现允许移除发行标题中真实出现的艺人名前缀/后缀，以及中文专辑名中的
`同名專輯` / `同名专辑` 标记，但这只用于扩大候选召回，不能单独构成合并证据。机器合并仍必须
满足相同 canonical album artist、完整有序曲目表等价和受控 Remaster/Deluxe/catalog 关系；移除
标记后标题为空、曲目不完整或存在多个可行目标时必须 fail closed。艺人规范名与发行标题语言不同
时，也不得因为无法按规范艺人名剥离前缀而漏掉完整曲目表一致的同名专辑。

L3 Album composition parent 只用于原专辑与 Taylor's Version/其他明确重录专辑的完整作品
lineage；标准版/Deluxe 继续由 L2 处理。重录 parent 的曲目采用 child 并集，Vault/重录独有歌曲
也纳入原专辑作品。Live、Tour、venue、Remix、Acoustic 等项目不得仅按标题或整体重叠作为不可拆分
child 挂到一张录音室专辑，而要在 L3 歌曲 composition 完成后逐曲确定原生专辑 owner：有原始
studio/EP/soundtrack/基础单曲归属的版本播放回流到该项目或其 composition parent；不同艺人翻唱、
现场独有原创、即兴和无法唯一找到其他 owner 的歌曲保留为版本项目 residual。一个 L3 canonical
song 最多一个默认专辑 owner，一个逻辑播放事件最多贡献给一个 L3 专辑。

机器归属必须持久化目标、候选、排除项、policy/revision 和 evidence，不能依靠
`drop_duplicates(canonical_song_key)` 的 SQL 排序决定。人工覆盖使用稳定 Track owner 和
Album Project 身份，并优先于机器结果。精选集策略继续冻结，不因这次 Live/重录规则确认而自动
扩大处理范围。Settings 的专辑自动治理页显示归属健康、机器理由、来源发行和人工覆盖；每次覆盖
创建或撤销后必须在同一事务重建完整归属，并使搜索、Billboard、年度和详情缓存失效。实现阶段、
schema 和验收门禁见
[`docs/archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md`](../archive/06-productization-closeout/2026-08-31-l3-work-and-album-attribution-plan.md)。

Album Project 的规范项目名、所有成员发行名及其 Unicode/大小写/空白等价形式都是同一项目的只读
别名，但项目身份始终是稳定 `album_project_id`。新搜索结果和详情深链必须使用
`/music/album-projects/{album_project_id}`；旧名称入口解析后替换为稳定地址。别名解析必须以
canonical album artist 消歧，L2 优先 `release`、L3 优先 `composition`，歧义时 fail closed；详情
摘要、排行、播放明细、日历和 Billboard 不得各自实现名称匹配，也不得因为从成员发行名进入就退回
具体来源专辑的局部统计。

Phone 深链与 Desktop 直接挂载同一套响应式治理工作台、API 和 owner 语义，不复制移动端写逻辑。
390px 视口下对象切换、任务标签、分组卡片和完整 policy version 必须可读并在容器内换行，不能横向
裁切；同一操作在 Desktop 与 Phone 上产生完全相同的 scope、覆盖记录和审计事件。

人工治理不得重写或删除 `plays`、`tracks`、`track_artists`。这些表继续表达导入时的原始事实；人工判断存放在独立覆盖层并保留审计链。

L1 owner 完整性检查是治理前置风险分类，不是公开归并层级。机器只执行能够证明安全的 provider
relink 或 split；无法在不改变用户歌曲身份的前提下确定拆分边界时，必须进入显式 review queue，
并在健康接口中与 hard issue 分开报告。review queue 非空不阻断已经满足守恒和唯一归属门禁的
L2/L3 发布，但不得伪装成已自动修复。

## 2. 有效曲目署名

有效署名由 `backend/domains/metadata/track_credits.py` 唯一解析：

1. 读取原始 `track_artists`；旧测试库无该表时才回退到 `tracks.artist_id` 主艺人。原始标题识别的合作艺人保留为兜底，不因 Spotify 漏列而自动删除。
2. 对权威 owner、有合法 Track `artists[]`、且主艺人与身份无冲突的曲目，叠加 `spotify_auto_track_credits`。本地同一艺人优先按 Spotify artist ID 解析；缺 ID 时只用唯一、无冲突的规范化同名关联，否则新建带 provider ID 的本地艺人。无法安全解析的曲目保留上一可用自动署名，不生成逐条审核任务。
3. 最后叠加 active `track_credit_overrides`，支持 `add`、`remove`、`set_role`；人工操作始终优先于自动署名，角色为 `primary` 或 `featured`。
4. 每个成员必须绑定本地稳定 `artist_id`，禁止只保存名称。
5. 通过艺人身份 resolver 投影到 canonical artist；同一曲目上的 alias 重叠只保留一个 canonical credit。
6. artist fan-out 后，同一有效播放事件对同一 canonical artist 至多贡献一次；增加合作艺人不会增加歌曲本身的播放事件数。

播放记录的合作曲排行消费上述有效署名：至少两位不同 canonical artist 即构成合作曲，三个排行共用实际合作事件；参与艺人榜包括 primary 和 featured。角色不参与合作资格判断，别名重叠不计为多人。原始标题识别继续作为署名补充兜底，排行本身不重复解析标题；人工移除合作艺人后，标题不能把该曲重新纳入。

语言和 genre 的主艺人归属规则是独立产品语义，仍按各自文档执行，不因曲目 featured fan-out 自动改变。

### 2.1 Spotify Track `artists[]` 证据

Spotify Track API 返回的完整 `artists[]` 以原始顺序保存到 `spotify_track_credit_sets`、`spotify_track_artist_credits`；首次观察或成员、顺序、署名名称变化记入 `spotify_track_credit_events`。这三张表仍只表示 provider evidence，不表示 `primary` / `featured` 角色；独立的 `spotify_auto_track_credits` 才是可用于有效署名的自动投影。除原始主艺人外的 Spotify 成员在现有双角色模型中使用技术性 `featured`，不代表 Spotify 声称其为 feat.。重复且内容相同的刷新只更新时间，不新增事件或署名 revision；空数组、缺失/重复艺人 ID 等非法响应保留上一可用证据和自动署名并报告失败。

日常 Spotify 元数据刷新会优先补本次导入关联曲目的证据缺口，并有界重试历史缺口；成功获取后自动同步有效署名，并通过同一 track-credit revision 触发统计与搜索维护。全库历史补采使用 `scripts/backfill_spotify_track_artist_credits.py --apply`；已有证据可用 `--sync-existing` 离线同步。默认只预览；写正式应用数据库必须显式给出 `--allow-primary --backup-path`，脚本先做 SQLite Online Backup。失败或中断后可再次运行，已保存的证据不会重复拉取。`scripts/audit_spotify_track_credits.py` 仍是只读差异诊断，不是人工审批队列；历史报告中的待核对状态不能当作当前有效署名状态。

## 3. 直接编辑、预览与撤销

- `preview` 返回变更前后署名、受影响曲目/艺人/专辑/播放范围、canonical 重复风险和全局消费者范围。
- 单管理员界面只要求选择有效本地实体与角色；`reason`、`evidence_type`、`evidence_source` 均为可选，缺省时后端写入内部的 `user_confirmed`/“个人管理直接修改”标记。同名搜索结果不能代替稳定 ID。
- 普通修改直接应用；跨 provider、canonical 重叠等明显冲突展示一次确认。底层 preview 仍执行，但不把审计字段变成日常表单。
- 事务写入 override 与 append-only event 后递增全局 revision、失效缓存；实时 resolver 立即生效。
- 每次 mutation 在同一事务记录 canonical before/after change set。只调整
  `primary/featured` 时，艺人成员集合不变，不重建 aggregate、四套搜索统计或 Year-End；只维护候选
  展示。添加、移除与 undo 优先按受影响歌曲闭包、艺人和 Billboard 周执行 signed delta，证明不足时
  才进入有原因记录的 full fallback。
- 维护使用 revision-specific 持久任务；旧 revision 不得吞掉随后发生的新 revision。设置页分别展示
  实时署名、候选索引和精确统计状态，`pending` 无任务或 `failed` 时可幂等恢复当前 target。
- undo 本身也是新审计事件和新 revision，不删除历史。

### 3.1 搜索与统计的上一可用版本

- `music_search_index_state` 只表示正在服务的 candidate generation；下一代的
  pending/building/failed 位于独立 maintenance state。新 generation 始终在影子表完成并通过 revision
  fence 后原子切换，失败不会改坏 active/previous。
- 四套搜索统计各自维护 active snapshot 与 target fingerprint。target 正在构建或失败时，候选仍可
  查询；context 默认返回通过 builder/payload 校验的 active snapshot，并明确标记
  `statistics_freshness=last_known_good`。没有 LKG 时只隐藏统计，不回退到 GET 冷建或虚假 0。
- candidate 与 context 响应分别声明 status、freshness、served fingerprint 和 target fingerprint；前端
  只能在 candidate unavailable 且确实没有结果时显示阻塞空态。公开只读响应不暴露 target revision、
  job 或内部错误。
- 删除实体、撤销展示资格或隐私相关修改必须与业务 mutation 同事务写入
  `music_search_entity_deny_overlay`。private/public 查询都会在 active/LKG generation 上即时排除目标；
  只有新 generation 已激活且可证明不含目标实体时才清理 deny 行。

### 3.2 艺人 provider ID 的持久化规则

- `artists.spotify_artist_id` 是本地实体的便捷投影；稳定 provider 身份事实必须同时写入 `artist_identity_external_ids`，不能只留在 `artists` 或 `spotify_artist_meta`。
- 曲目元数据精确同名关联或艺人精确搜索写入本地 Spotify artist ID 时，同一事务补写 `provider=spotify` 的 verified 外部 ID。重复刷新不得降低已有人工作证的 `evidence_type`、`evidence_source`、`confidence` 或 `verified`。
- 艺人身份创建和更新都可携带成员级 external IDs。已核对的不同 provider ID 必须全部保留为冲突事实，再由 `provider_metadata_artist_id` 明确选择展示元数据来源；禁止为了消除冲突删除未被选中的稳定 ID。
- 身份事件的 before/after 快照包含活动成员的 external IDs；undo 恢复对应成员当时的外部 ID 状态，并继续以新事件和新 revision 留痕。
- 候选页发现的 provider ID 会随确认写入治理层。名称只能用于寻找候选，最终关联仍绑定本地 `artist_id + provider + external_id`。

### 3.3 Spotify Album `artists[]` 与专辑身份

SS-2026-09-24-002 的本地实现（migration 88）独立于 Track evidence；实施与验证范围见 [专辑艺人报告](../reports/2026-10-02-album-artist-evidence-verification.md)。

- `spotify_album_credit_sets` 保存 Album ID、数量、内容签名、获取时间、来源入口及可选 run ID；`spotify_album_artist_credits` 按 `credit_order` 保存 Spotify artist ID 和原始 `credited_name`。ID 缺失允许首次保存为 NULL / unresolved，不能按名称猜补 ID；`album_artists` 只是兼容显示投影，不能反向生成稳定身份。
- `spotify_album_credit_events` 追加 observed / changed / rejected 事件及前后 JSON、原因、来源、run ID 与时间。相同数组只更新时间，不追加成功事件或改变事实 revision；重复拒绝同一观察也不重复追加事件。
- 名称与顺序变化不改变 ID 身份。同一完整 ID 集合可以更新名称/顺序；已保存的已知 ID 消失、完整集合新增/替换 ID、重复 ID、缺失数组或非法名称时，保留上一可靠数组和显示字符串，在 rejected 事件中保存待审核观察。部分未解析数组可以在保留所有已知 ID 的前提下补全。网络失败不写入新观察，更不能将失败视为身份验证成功。
- 本地关联只查 `artists.spotify_artist_id` 与已有 `artist_identity_external_ids(provider=spotify)`，随后使用当前活动人工 canonical map。多个本地成员已被人工合并为同一 canonical 时可以唯一解析；仍指向多个 canonical 时为 ambiguous，零个为 unresolved。Album 刷新不创建、按名称合并艺人，不改写既有人工作证的 external IDs。Provider 名称与人工显示名称分别保留；人工 canonical 选择即时优先。
- `AlbumArtistResolver.match()` 的 `verified_id` 仅用于所有数组成员均唯一解析且包含目标 canonical 的结果；id_mismatch / ambiguous / unresolved / unresolved_target 都不回退名称。同名不同 ID 不能通过名称得到身份验证。目标为旧名称参数时，必须唯一解析到本地 canonical，再做 ID 判断。
- 无结构化证据的旧行仍可读取。Billboard 类型/日期、Album Project/健康候选、Records 可信原版及完整曲目自动归并保留明确的 legacy 名称兼容路径；整名匹配先于逗号分词，JSON 名称数组仍兼容。这只是 `legacy_name_match` 候选，残留歧义不能当成 ID 已验证。发行周期的严格 `_verify_album_artists()` 只接受 verified_id；公开请求不联网，未回填的旧行可能暂不进入发行周期结果。
- 新证据的自动归并 family/fingerprint 和 `album_artist_key` 使用 canonical 集合，名称只用于标题包装和展示；legacy 自动归并仍须满足完整曲目表及既有关系门禁。原声带/Various Artists 残余项目存在新证据时，不选择数组第一人作为 primary，不创建多人拼接艺人；只有全部唯一解析到同一个 canonical 才复用该项目艺人，其他情况保留待解析。人工项目优先级不变。
- 歌曲归并列表不再从 Album provider 或本地专辑艺人回退歌曲艺人；专辑曲目比较的歌曲艺人字段复用本地 owner 的有效 Track 署名；非本地歌曲只能读取已有 Track provider evidence，缺失时留空，不能读取 Album artists 字符串代替歌曲署名。
- 数组顺序不是 primary / featured。Album evidence 不提供 Track 艺人的替代来源，不参与有效曲目署名投影，不为 Album 未播放成员新增播放贡献；项目成员仍来自既有本地歌曲/播放关联。
- 主刷新、版本归并补取、发行周期批取/搜索、封面脚本共用 `persist_album_artists()`；封面脚本使用 UPSERT，不能通过 REPLACE 删除证据父行或丢失曲目表。Simplified Album 的艺人证据可保存，但不据此声称曲目表完整。
- Analysis/Records 与健康 revision 纳入 Album credits 和外部身份字段；Billboard 与发行周期内部缓存按证据/身份 revision 读取，年报的准备 LRU、持久 prepared-key 和内容 digest 同步受 revision 约束。拒绝事件、获取时间和 run ID 不使事实缓存失效。刷新成功后通过现有 cache manager 释放相关内存缓存。Album 语义变化可能使既有年报准备 key 失效，不能复用未纳入证据依赖的旧准备结果。
- migration 88 只增表，不拆分旧字符串回填 ID，不修改原始 plays / tracks / track_artists。81→88 过程中，migration 85 安装当前 revision 合同时先幂等创建新增证据表；最终安装完整触发器。当前联合集成由 migration 86 安装专辑语义修订合同，同时保留分页 migration 87 与艺人 migration 88；编号连续。

副本演练入口：`scripts/backfill_spotify_album_artist_credits.py --source-db <只读源> --output-db <不存在的新副本> --limit 20 [--ids ...]`。该 CLI 先用 Online Backup 创建副本并迁移，再最多处理 1..100 个明确有界 Album；输出目标必须是新文件，禁止直接执行正式库回填。它只写 Album 证据/兼容显示和必要的最小元数据父行，不写 Track 元数据或任何署名。正式库全量回填、冲突审批和发布需要另行授权及验证。

## 4. API

统一前缀为 `/api/music-metadata/track-credits`：

- `GET /status`、`GET /tracks`、`GET /artist-candidates`、`GET /tracks/{track_id}`、`GET /manual-changes`、`GET /events`
- `POST /preview`、`POST /overrides`
- `PUT /overrides/{override_id}`、`POST /overrides/{override_id}/remove`
- `POST /events/{event_id}/undo`、`POST /rebuild`

写端点需要本地认证；OpenAPI、前端生成类型、safe GET smoke 与 operation/parameter audit 必须同步维护。

## 5. 当前真实样本

`Hold Me Closer` 使用本地 `track_id=175`：保留 `Elton John (artist_id=42)` 的原始 primary credit，并人工增加 `Britney Spears (artist_id=53)` featured credit。证据绑定 Spotify track `72yP0DUlWPyH8P7IoxskwN`；Britney 的候选元数据可显示 Spotify artist ID `26dSoYclwsYLMAKD3tpOr4`。原始播放事件与原始署名行不因该决策改写。

## 6. 回归检查

- raw facts hash 在一次 override/undo 前后不变；事件与 revision 只追加。
- 实时 artist fan-out 与 `agg_weekly_artists` 在相同过滤参数下按周一致。
- 搜索、音乐详情、Billboard、对决、播放记录、合作曲、账号、Wrapped、社区和 AI 报告读取同一有效署名；缓存键包含 track-credit revision 或在 mutation 后精准失效。
- Settings 在 1440px 与 390px 下可完成搜索、稳定 ID 选择、直接应用、轻量人工修改列表、撤销和失败重试，且无页面级横向溢出。append-only 事件仍保留在后端，但不作为默认工作流展示。
- 详情页链接必须包含 `metadata` 目标、实体参数、`return_to` 与 `#music-metadata-management`，Settings 自动定位、展开并预填对应模块。
- 歌曲手动归并必须覆盖：任意 Track/Spotify ID 与来源名称搜索、详情页 ID 预填、按 owner 去重、两个不同 owner `track_id` 选择、代表版本切换、同一 owner 不可归并提示、L2/L3 写入，以及已有同 scope 分组的安全统一。
- 相同合法 Spotify ID 必须恰好命中一个 `track_id` owner；一个 owner 可以拥有多个 Spotify ID。L2/L3 活动组至少包含两个 distinct `track_id`，同一 `track_id` 在同 scope 至多属于一个活动组。
- 活动分组成员、代表版本和 pending 候选必须都是 owner Track ID 或无法解析 Spotify 身份的本地 fallback；相同 owner 的候选不得进入用户界面。owner 本身即使遗留 `tracks.spotify_track_id` 指向另一 owner，也不能被反向覆盖，因为播放时 Spotify ID 证据优先。
- 身份迁移、人工归并和撤销前后，`plays`、`tracks`、`track_artists` 行数与稳定 hash 不变；已有外键问题按 baseline/delta 报告，新增问题必须为 0。
- 搜索、详情、播放记录和榜单统一使用同一 `track_id`；不得重新暴露 synthetic L1/canonical track ID 命名空间。
- 搜索、详情、榜单、首页、年度总结、Wrapped 和播放纪录中的歌曲归属/封面必须来自同一
  TrackPresentation；标准曲、deluxe-only、精选集独占、独立单曲/EP、URI/裸 Spotify ID、ISRC
  等价和错误 cross-link 均有回归覆盖。播放事件行与 source breakdown 仍保留实际来源。
- provider 刷新、身份创建、身份更新和 undo 必须覆盖 external-ID 持久化、冲突保留、人工证据不降级和 before/after 对称恢复；真实数据测试只断言跨接口一致性与治理不变量，不硬编码会随合法新播放增长的累计次数。

## 专辑完整曲目表

`SS-2026-09-24-001` 的当前合同：日常 Spotify 元数据刷新和显式版本归并补取共用
`SpotifyProvider` / `HttpClient` 的完整专辑读取。首个 Album 分页对象经校验后可复用；后续只请求
固定 `GET /v1/albums/{id}/tracks?limit=50&offset=...`，不执行 `next` URL。
接口合同于 2026-10-02 核对 [Spotify 官方文档](https://developer.spotify.com/documentation/web-api/reference/get-an-albums-tracks)。

- `total_tracks` 是来源声明的发行位置总数；`track_list` 是按发行顺序保存的 ID 列表，允许相同 ID
  出现在不同位置。完整性校验比较位置数量，不比较不同 ID 数量；必要 ID、分页 offset、分页总数、
  页长度、结束状态、重复页及有序碟号/曲号均须通过校验。
- additive migration 87 增加 `spotify_album_tracklist_evidence`，保存发行级的完整曲目对象、有序
  `disc_number` / `track_number`、已验证总数及最近尝试状态/总数/错误。避免同一 recording ID 的
  全局元数据行覆盖另一发行位置。列表、位置证据和必要简化曲目元数据在同一事务提交。
- 中途请求失败、总数变化或证据不足时不写入半份列表，保留上一完整列表及其来源总数；最近尝试的
  新声明写入 `attempted_total`。既有完整缓存可继续读取；旧缺页、缺 ID 或无声明总数的非空列表
  不能参与完整性判断。旧完整列表兼容读取，默认不重抓全库。
- 版本对比优先按本地专辑名称及来源链接的置信度/播放证据选择具体发行；未有来源链接时沿原链路
  回退。保留目录顺序；相同 track ID 和归一化歌曲名各只展示首次位置。目录或必要名称未齐时返回
  `incomplete_album_ids`，前端提示先维护元数据，不能把未知差异显示成独占曲目。
- 目录完整性与发行位置完整性分别判断。精确碟号/曲号只取自与当前 `track_list` 的有序 ID、
  `total_tracks` 完全匹配且名称、位置有效的整份发行证据；缺失、错配或损坏时所有位置返回 `null`，
  `position_incomplete_album_ids` 标记对应本地专辑。曲目异同仍可比较，前端明确显示“位置未知”。
  禁止从 recording 的全局父发行借用位置，也不推断 Disc 1 或以数组下标伪造 Track。旧目录未核验
  顺序时只保持缓存顺序；显式补齐后恢复来源发行顺序。最近尝试失败不否定仍与目录匹配的上一完整证据。
- 整专辑收听分母是可信发行中不同 canonical song 的集合。重复 ID 的位置不会增加歌曲数、逻辑
  播放、听过曲目或入榜曲目；曲目专辑展示归属也只使用完整目录证据。专辑详情分别标注“发行 N 首”
  与“已听 M 首”，未知发行总数不再用本地歌曲数量伪装。
- Records 沿用专辑元数据的语义 revision；治理健康把 `track_list` 纳入依赖。年度内容版本为
  `yearly_review_v2_19_album_evidence`，年度指纹覆盖播放来源链接触达的专辑，防止 recording 的当前父专辑不同
  时漏掉曲目表变化。修复不批准新归并、不改项目 membership、不重建完整 Billboard。
- 页面 GET 只读缓存，不完整时通过显式刷新/维护或
  [`repair_album_tracklists.py`](../../scripts/repair_album_tracklists.py) 修复。脚本必须指定数据库，
  默认只审计；`--apply` 默认最多 50 个目标，硬上限 200，支持重复 `--album-id` 和
  `--verify-boundary-50`。默认队列只处理目录缺口；`--include-position-evidence` 显式加入与实际播放
  相连、目录完整但位置缺失/错配的有界目标，不将所有旧缓存加入日常刷新。审计模式也输出选中范围，
  不请求 Spotify。自动选择会跳过已完整的目标；明确 `--album-id` 可复查指定发行，重复成功写入不改变
  曲目事实。位置补齐沿用同一原子事务、来源修订跟踪与维护缓存失效；对比 GET 直接读取，位置不加入
  不消费它的 Records/年度事实依赖，不启动全量重建。生产应用仍需单独授权、Online Backup
  和正式发布门禁。

实施与隔离副本证据见 [分页交付报告](../reports/2026-10-02-album-track-pagination-acceptance.md)。


## 专辑证据联合更新边界

完整目录/发行位置与 Album artists 分别校验；来源校验失败只阻止对应证据发布，不清空可靠旧证据。分页失败时可信艺人仍可更新；艺人 ID 冲突时可信完整目录/位置仍可更新。任一数据库写入失败回滚整批显示、两类证据和审计。共同写入支持 Provider/token/outcomes 和 source/source_run_id；不改原始播放、歌曲、原始/有效歌曲署名或人工批准关系。当前联合年度内容版本为 `yearly_review_v2_19_album_evidence`，准备层 revision 和播放来源专辑触达依赖均保留。
