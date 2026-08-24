# 音乐源数据管理与曲目署名规则

## 1. 管理入口与边界

Settings 的“音乐源数据管理”是人工音乐事实治理的唯一入口，分为“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块。“归并与版本”共用唯一一套 L1/L2/L3、自动检测、已保存分组和手动创建入口，并在候选、保存项或编辑上下文中标明歌曲归并与专辑版本；专辑重叠率和发行项目重建只位于专辑版本高级选项。单曲、专辑和艺人详情页只提供带实体参数和返回地址的深链，不能复制写逻辑。

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
- provider 刷新、身份创建、身份更新和 undo 必须覆盖 external-ID 持久化、冲突保留、人工证据不降级和 before/after 对称恢复；真实数据测试只断言跨接口一致性与治理不变量，不硬编码会随合法新播放增长的累计次数。
