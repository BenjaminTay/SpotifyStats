# 音乐源数据管理与曲目署名规则

## 1. 管理入口与边界

Settings 的“音乐源数据管理”是人工音乐事实治理的唯一入口，分为“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块。“归并与版本”先选择“歌曲归并 / 专辑归并”，再共用“自动检测 / 已保存分组 / 手动创建”三类任务。对象切换在三个任务中始终可见；手动创建统一采用“选择成员 → 配置代表版本与层级 → 确认保存”三步流程；用户只选择 L2/L3，不提供 L1 统计开关。专辑自动检测额外提供重叠率，Album Projects 重建归入维护工具，不再以另一套工作台或隐藏的对象入口呈现。单曲详情的“编辑”先展示“归并歌曲版本 / 调整曲目署名 / 管理艺人身份”动作菜单，再以实体参数和返回地址深链到唯一治理入口；专辑和艺人详情同样只提供深链，不能复制写逻辑。

歌曲手动归并必须允许搜索并明确选择两个不同的 owner `track_id`、指定代表版本和生效层级。`tracks.track_id` 是唯一的应用、统计和公开歌曲身份，不再另建 canonical track ID。一个 `track_id` 可以拥有多个 Spotify Track ID；一个 Spotify Track ID 必须且只能归属于一个现有 `track_id`。历史原始 Track ID、兼容 L1 ID、Spotify ID 和名称候选进入治理工作区前必须统一经过 `spotify_track_owners` 解析；不拥有任何 Spotify ID 且已投影到其他 owner 的兼容壳记录不得单独展示或写入分组。新导入记录先按 Spotify owner 命中已有 `track_id`；没有 owner 时才沿用既有“艺人 + 曲名”匹配或创建 track，再登记 owner。日常版本关系只在 L2 `recording`（同一录音/母带）或 L3 `composition`（同一作品，包括重录、现场、Acoustic、Remix 等）建立。

歌曲与专辑的“已保存分组”必须使用一致的卡片结构与成员操作。歌曲分组以稳定 `track_id` 列出成员，并支持切换代表曲目、移除非代表成员和删除覆盖组；`track_group_members` 是 L2/L3 的原始治理关系，`track_group_l1_members` 仅作旧消费代码的兼容投影，且其中 `l1_id` 必须等于对应 `track_id`。每个成员默认折叠其历史来源，展开后显示代表来源、封面、有效艺人和来源冲突。这些操作不得修改原始 `tracks`、`plays` 或署名事实。

播放归属优先使用事件发生时保存的 `plays.spotify_track_id_at_play`，仅在缺失时回退 `tracks.spotify_track_id`，再通过 `spotify_track_owners` 解析到唯一 `track_id`；没有 Spotify ID 时直接使用 `plays.track_id`。已登记 owner 不能因名称、简繁、艺人、专辑、封面、ISRC 或时长变化而自动改写。确定性历史回填按“有播放记录优先、播放行数最多、艺人与专辑元数据更完整、最后取最小稳定 track_id”选择 owner，并保留人工纠错的扩展位。

歌曲详情的摘要统计、最近播放和播放日历必须与全局曲目榜共用同一 L2/L3 分组解析：L2 只取当前活动 `recording` 组，不跟随其 `composition` 父组；L3 才将子录音组和父作品组的成员纳入同一范围。请求分组内任一成员都应返回同一代表 `track_id` 和相同合计；最近播放行仍保留实际来源版本，便于用户理解统计构成。

歌曲详情和新生成的深链统一使用 `/music/tracks/{track_id}`。旧 `/music/tracks/l1/{id}` 与 `/music/tracks/canonical/{id}` 仅作为隐藏兼容重定向，不能再出现在新链接或 OpenAPI。

L1 不作为设置项或人工合并层级，原“高级：基础身份纠错”入口关闭。底层只执行 Spotify ID 单一归属不变量；需要修正 owner 时必须走单独的受审计数据治理流程，不能通过 L2/L3 或公开 canonical merge/split API 生成新歌曲身份。

Phone 当前把归并、署名和元数据维护明确归入“高级数据管理 · 电脑端管理”，不能静默显示不完整的移动版操作；后续若开放 Phone 写入，必须直接挂载同一套响应式工作台、API 与 owner 语义，不得复制另一套治理逻辑。

人工治理不得重写或删除 `plays`、`tracks`、`track_artists`。这些表继续表达导入时的原始事实；人工判断存放在独立覆盖层并保留审计链。

## 2. 有效曲目署名

有效署名由 `backend/domains/metadata/track_credits.py` 唯一解析：

1. 读取原始 `track_artists`；旧测试库无该表时才回退到 `tracks.artist_id` 主艺人。
2. 叠加 active `track_credit_overrides`，支持 `add`、`remove`、`set_role`，角色为 `primary` 或 `featured`。
3. 每个成员必须绑定本地稳定 `artist_id`，禁止只保存名称。
4. 通过艺人身份 resolver 投影到 canonical artist；同一曲目上的 alias 重叠只保留一个 canonical credit。
5. artist fan-out 后，同一有效播放事件对同一 canonical artist 至多贡献一次；增加合作艺人不会增加歌曲本身的播放事件数。

语言和 genre 的主艺人归属规则是独立产品语义，仍按各自文档执行，不因曲目 featured fan-out 自动改变。

## 3. 直接编辑、预览与撤销

- `preview` 返回变更前后署名、受影响曲目/艺人/专辑/播放范围、canonical 重复风险和全局消费者范围。
- 单管理员界面只要求选择有效本地实体与角色；`reason`、`evidence_type`、`evidence_source` 均为可选，缺省时后端写入内部的 `user_confirmed`/“个人管理直接修改”标记。同名搜索结果不能代替稳定 ID。
- 普通修改直接应用；跨 provider、canonical 重叠等明显冲突展示一次确认。底层 preview 仍执行，但不把审计字段变成日常表单。
- 事务写入 override 与 append-only event 后递增全局 revision、失效缓存；实时 resolver 立即生效。
- artist weekly aggregates 在临时表中重建并原子切换。重建失败记录 `failed`，允许重试，读取不得混用旧 aggregate。
- undo 本身也是新审计事件和新 revision，不删除历史。

### 3.1 艺人 provider ID 的持久化规则

- `artists.spotify_artist_id` 是本地实体的便捷投影；稳定 provider 身份事实必须同时写入 `artist_identity_external_ids`，不能只留在 `artists` 或 `spotify_artist_meta`。
- 曲目元数据精确同名关联或艺人精确搜索写入本地 Spotify artist ID 时，同一事务补写 `provider=spotify` 的 verified 外部 ID。重复刷新不得降低已有人工作证的 `evidence_type`、`evidence_source`、`confidence` 或 `verified`。
- 艺人身份创建和更新都可携带成员级 external IDs。已核对的不同 provider ID 必须全部保留为冲突事实，再由 `provider_metadata_artist_id` 明确选择展示元数据来源；禁止为了消除冲突删除未被选中的稳定 ID。
- 身份事件的 before/after 快照包含活动成员的 external IDs；undo 恢复对应成员当时的外部 ID 状态，并继续以新事件和新 revision 留痕。
- 候选页发现的 provider ID 会随确认写入治理层。名称只能用于寻找候选，最终关联仍绑定本地 `artist_id + provider + external_id`。

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
- provider 刷新、身份创建、身份更新和 undo 必须覆盖 external-ID 持久化、冲突保留、人工证据不降级和 before/after 对称恢复；真实数据测试只断言跨接口一致性与治理不变量，不硬编码会随合法新播放增长的累计次数。
