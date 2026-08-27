# Spotify Track ID 作为 L1 身份的早期修复方案（已取代）

> 状态：已取代（2026-08-27）；本文件只保留当时的分析和迁移思路，不得作为当前规则执行
> 创建日期：2026-08-27
> 适用范围：歌曲导入身份、L1/L2/L3 归并、播放统计、音乐查找、详情页、Billboard、年度总结与设置治理
> 关联规则：[`../../reference/music-metadata-management.md`](../../reference/music-metadata-management.md)、[`../../reference/playback-stats-rules.md`](../../reference/playback-stats-rules.md)
> 交付证据：[`../../reports/2026-08-27-spotify-track-l1-identity-migration.md`](../../reports/2026-08-27-spotify-track-l1-identity-migration.md)

最终决策不再把 Spotify Track ID 本身定义为 L1。当前模型以稳定的本地 canonical track 为基础身份：一个 canonical track 可以拥有多个 Spotify ID，但同一 Spotify ID 只能属于一个 canonical track。公共产品不提供 L1 开关，只提供 L2 同录音和 L3 同作品；基础身份误拆/误合通过单独的受审计治理操作纠正。若下文与当前参考规则冲突，以参考规则和最终交付报告为准。

## 1. 决策与目标

本方案把以下规则提升为歌曲身份系统的硬不变量：

> 对任何合法、非空的 Spotify Track ID，系统中只能存在一个有效 L1 曲目身份。相同 Spotify Track ID 的播放和历史曲目记录无条件收敛；不同 Spotify Track ID 绝不在 L1 收敛，只能通过 L2/L3 版本关系治理。

层级语义固定为：

| 层级 | 身份标准 | 是否需要归并决策 |
|---|---|---|
| 原始记录层 | `play_id`、历史 `track_id`、原始署名和来源专辑 | 不对用户称为版本，完整保留 |
| L1 | `provider + external_track_id`；当前即 `spotify + spotify_track_id` | 相同 ID 确定性收敛，不需要用户确认 |
| L2 `recording` | 两个或更多不同 L1，但属于同一录音/母带 | 自动检测只产候选，或由用户确认 |
| L3 `composition` | 两个或更多不同 L1/L2，属于同一作品 | 由用户确认，覆盖重录、现场、Acoustic、Remix 等 |

本次修复不是把截图中的两个组简单合成一个 L2 组。正确结果是：相同 Spotify ID 的四条历史 `track_id` 先收敛为一个 L1；原有伪 L2 自动组撤销。只有不同 Spotify ID 之间才继续讨论 L2/L3。

## 2. 不变量与边界

### 2.1 必须始终成立

1. 同一 `spotify_track_id` 对应且只对应一个活动 L1 身份。
2. 一条播放的 L1 身份优先取 `plays.spotify_track_id_at_play`，缺失时才回退 `tracks.spotify_track_id`。
3. 标题、简繁、艺人、专辑、封面、ISRC 或本地 `track_id` 冲突只能产生元数据审核项，不能拆分同一 Spotify L1。
4. 不同 Spotify ID 永远是不同 L1。曲名、艺人、ISRC、时长或音频相似度只能支持 L2/L3 候选，不能修改 L1。
5. `track_groups` 只表达跨 L1 的 L2/L3 关系；一个只含单个 L1 的组无效。
6. 一个 L1 在同一 scope 中最多属于一个活动组。
7. 所有人工治理写入覆盖层和审计事件，不改写或删除 `plays`、`tracks`、`track_artists`。
8. 原始播放总行数、原始 `ms_played` 总和和源指纹在迁移前后完全不变。

### 2.2 无 Spotify ID 的记录

- 有本地 `track_id` 但没有 Spotify ID：建立 `local:{track_id}` 未解析 L1，不根据名称自动并入 Spotify L1。
- 连本地 `track_id` 都没有的播放：继续作为未归属原始播放保留，不进入歌曲实体排行。
- 后续找到可靠 Spotify ID 时，通过审计覆盖把未解析 L1 关联到 Spotify L1，不修改原始事实。

### 2.3 不把内容形态作为身份拆分键

`content_type=audio|video` 表达播放形态，不参与 Spotify L1 唯一键。当前真实库存在同一 Spotify ID 同时出现在 audio 和 video 的情况；它们仍属于同一个歌曲 L1，但来源形态可以继续单独拆分统计。

## 3. 当前真实数据基线

以下是 2026-08-27 的只读快照，仅用于迁移验收，不作为永久常量：

| 项目 | 当前结果 | 迁移含义 |
|---|---:|---|
| 原始播放 | 92,908 | 不得改变 |
| 会进入当前音乐实体统计的播放 | 92,568 | 全部具有播放时 Spotify ID |
| 不同播放时 Spotify ID | 7,843 | 可以完整建立已播放 L1 |
| 非空 Spotify ID 格式异常 | 0 | 当前来源可直接使用 |
| 播放时 ID 缺少本地 Spotify 元数据 | 0 | 展示元数据具备离线落地条件 |
| 历史 `tracks` 中重复 Spotify ID | 5,597 个 ID，5,855 条多余记录 | 说明 `track_id` 不能充当 L1 |
| 一个 `track_id` 承载多个播放时 Spotify ID | 818 个 | L1 必须从事件级 ID 解析 |
| 播放时 ID 与 `tracks.spotify_track_id` 不一致 | 9,755 条播放 | 不能只修 `tracks` 表 |
| 一个播放时 Spotify ID 映射多个 `track_id` | 33 个 | 相同 ID 需要跨本地记录收敛 |
| 当前自动歌曲组 | 24 个 | 23 个迁移后只剩一个 L1，应撤销；1 个需审核 |

按当前 `track_id` 统计，有播放的 L1 表面数量为 6,828；按播放时 Spotify ID 为 7,843。迁移后 L1 数量增加 1,015（约 14.9%），主要原因是旧导入曾把不同 Spotify ID 合进同一个 `track_id`。

在当前 `min_ms=30000`、`max_merge_gap_minutes=5` 下的只读影子计算：

- 当前逻辑播放 66,495 次；新身份解析为 66,492 次，差异 -3（约 -0.0045%）。
- 计入时长差异约 +248,116 ms（约 +4 分 8 秒，约 +0.0016%）。

这说明原始事实稳定，但实体归属、部分排行和历史榜单必须版本化重建。

## 4. 目标数据模型

### 4.1 新增 L1 身份表

建议在下一可用 migration 中增加：

```sql
CREATE TABLE track_l1_identities (
    l1_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    provider                TEXT NOT NULL,
    external_track_id       TEXT,
    fallback_track_id       INTEGER REFERENCES tracks(track_id),
    identity_status         TEXT NOT NULL DEFAULT 'active'
                            CHECK(identity_status IN ('active', 'unresolved', 'superseded')),
    representative_track_id INTEGER REFERENCES tracks(track_id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(
        (provider = 'spotify' AND external_track_id IS NOT NULL AND fallback_track_id IS NULL)
        OR
        (provider = 'local' AND external_track_id IS NULL AND fallback_track_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX idx_track_l1_spotify_identity
    ON track_l1_identities(provider, external_track_id)
    WHERE provider='spotify' AND external_track_id IS NOT NULL;

CREATE UNIQUE INDEX idx_track_l1_local_identity
    ON track_l1_identities(fallback_track_id)
    WHERE provider='local';
```

`representative_track_id` 只用于兼容封面、旧路由和缺省展示，不参与身份唯一性，也不能反向决定播放归属。

### 4.2 新增来源关系表

一个历史 `track_id` 可能关联多个播放时 Spotify ID，因此不能对 `track_id` 加唯一约束：

```sql
CREATE TABLE track_l1_source_links (
    l1_id         INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    track_id      INTEGER NOT NULL REFERENCES tracks(track_id),
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('play_at_time', 'track_projection', 'manual')),
    observed_plays INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at  TEXT,
    PRIMARY KEY(l1_id, track_id, evidence_type)
);
```

该表用于治理审计和 UI 的“来源记录”详情；播放事实的实时归属仍由事件级 ID 决定，避免维护 92,908 行可推导的重复映射。

### 4.3 统一有效身份解析器

新增 `backend/domains/metadata/track_identity.py`，成为唯一身份入口：

```text
normalize_spotify_track_id(value)
ensure_l1_identities(conn, spotify_ids, fallback_track_ids)
resolve_play_l1_sql(play_alias, track_alias)
resolve_track_l1_candidates(conn, track_ids)
select_l1_display_metadata(conn, l1_ids)
get_track_identity_revision(conn)
validate_track_identity_invariants(conn)
```

播放解析优先级固定为：

```sql
COALESCE(NULLIF(p.spotify_track_id_at_play, ''), NULLIF(t.spotify_track_id, ''))
```

只要得到合法 Spotify ID，就连接唯一的 `track_l1_identities` 行；仍为空时才连接 `local:{track_id}`。

### 4.4 展示元数据与身份分离

Spotify L1 的标题、时长、ISRC、专辑和封面优先读取 `spotify_track_meta` / `spotify_album_meta`。有效艺人读取曲目署名和艺人身份治理层。历史 `tracks` 只作为回退和来源证据。

同一 Spotify ID 出现标题或艺人冲突时：

- L1 身份保持一个；
- 记录 `metadata_conflict` 健康项；
- UI 使用 provider 元数据或已审核覆盖；
- 不生成第二个 L1，也不生成自动 L2。

## 5. 导入链路修改

涉及 `backend/core/import_data.py`、增量 change set、Spotify metadata refresh 和 import maintenance。

### 5.1 修正 `_cache_track`

当前逻辑先按 `(artist_id, track_name)`，再只在同一 `artist_id` 内查询 Spotify ID。应改为：

1. 解析合法 Spotify ID。
2. 有 Spotify ID 时，先全局按 Spotify ID 查找或创建来源曲目记录，不再把 `artist_id` 作为 Spotify 身份的一部分。
3. 没有 Spotify ID 时，才使用本地保守 fallback。
4. 无论复用哪个历史 `track_id`，`plays.spotify_track_id_at_play` 都继续写入原始事件。
5. 同事务 `ensure_l1_identities()`，并递增 candidate/identity revision。

这只防止新增污染；历史 818 个混合 `track_id` 不通过改写修复，而由事件级解析器正确拆分。

### 5.2 导入后的硬门禁

在现有 post-import health 上新增：

- 新导入的每个合法 Spotify ID 恰好命中一个 L1。
- 不允许新增长度/字符非法的 Spotify Track ID。
- 不允许相同 Spotify ID 产生第二个 L1。
- 不允许自动组只包含一个 distinct L1。
- 不允许同一 L1 在同 scope 进入多个活动组。
- 外键问题使用“导入前 baseline + 导入后 delta”判断；历史残留可继续列为维护项，但新增残留阻断并回滚。

## 6. 逻辑播放与统计链路修改

### 6.1 逻辑事件必须按 L1 身份连续合并

当前 `reconstruct_logical_plays()` 使用 `track_id` 判断相邻记录是否同曲。改造为支持显式 `identity_column`：

- 默认参数保持测试兼容；生产加载器传入 `l1_id`。
- 保留 `_raw_track_id` 供来源解释。
- 时长连接改为播放时 Spotify ID 对应的 `spotify_track_meta.duration_ms`，不能继续只按 `tracks.spotify_track_id`。
- 相同 Spotify ID 跨不同 `track_id` 的相邻记录允许按现行 gap 规则连续合并。
- 同一个旧 `track_id` 下的不同 Spotify ID 必须切断逻辑事件。

### 6.2 周聚合和 Billboard schema

现有 `agg_weekly_tracks.track_id` 表达的是本地代理键。新增 `l1_id`，并把周聚合唯一粒度改为：

```text
(billboard_week, l1_id)
```

公开统计结果返回 `track_id=l1_id`，原始代表记录另以 `representative_track_id` 返回；内部排序、去重、周账本、榜单资格、年榜投影和详情查询也全部使用 `l1_id`。新聚合版本必须提升 builder/policy version，旧缓存不能被误读为新语义。

### 6.3 消费者统一迁移

所有歌曲消费者必须先读取同一个 L1 解析结果，再应用 L2/L3：

| 消费链 | 主要改动 |
|---|---|
| `backend/core/db.py` | 载入播放时生成 `l1_id`，逻辑事件按 L1 重建 |
| `backend/domains/playback/track_groups.py` | 输入/输出从 raw `track_id` 改为 `l1_id` |
| Billboard ranking/detail/year-end | 聚合、深链和代表实体使用 L1 |
| `play_service` / `analysis_stats_service` / `entity_stats_service` | 歌曲 groupby 和 unique track 使用 L1 |
| music search index/snapshot | 一条文档对应一个 L1，不再一条 `tracks` 行一条结果 |
| home / account archive / wrapped / yearly review | identity key 和缓存 revision 加入 L1 policy version |
| AI read-only tools | 对外只暴露有效 L1/L2/L3，不暴露伪版本 |

不得让每个消费者自行写一份 `COALESCE`；统一 SQL helper/resolver 是发布门禁。

## 7. L2/L3 分组模型修改

### 7.1 成员从 `track_id` 迁移到 `l1_id`

兼容迁移采用新增列/新表，不原地破坏旧表：

```sql
CREATE TABLE track_group_l1_members (
    group_id INTEGER NOT NULL REFERENCES track_groups(group_id),
    l1_id    INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    PRIMARY KEY(group_id, l1_id)
);
```

`track_groups` 增加 `primary_l1_id`。兼容期保留 `primary_track_id` 和旧 `track_group_members` 只读，用于回滚和旧 API；切换完成后停止写旧 membership。

### 7.2 自动组语义重做

当前按 `(spotify_track_id, artist_id)` 创建自动 recording group 的逻辑全部移除。相同 Spotify ID 已在 L1 收敛，不再需要组。

新的自动检测只能扫描两个不同 L1，并满足：

- `spotify_track_id_a != spotify_track_id_b` 是硬前提；
- 曲名规范化、有效 canonical artist、ISRC、时长、发行关系作为候选证据；
- 高置信度也只生成候选，第一阶段不自动写入 L2；
- 艺人/标题冲突不拆分 L1，而进入 metadata conflict；
- L3 不自动写入。

原 `automatic_spotify_track_id`、`automatic_artist_id` 在兼容期保留但不再读取，最终 migration 删除。

### 7.3 历史组迁移分类

对每个现有组先展开其成员关联的 distinct L1：

1. **只剩 1 个 L1**：不是版本组。归档迁移事件并撤销活动组。
2. **包含 2 个以上 L1，且为人工组**：保留 scope、代表身份和名称，去重后迁移。
3. **包含 2 个以上 L1，且为自动组**：不自动保留为事实，转入待审核候选。
4. **同一 L1 在同 scope 落入多个组**：合并前停止迁移并生成冲突报告，不按 group_id 猜测胜者。

当前 24 个自动组预计：23 个归入第 1 类；“純妹妹”相关组归入第 3 类，因为播放时实际出现两个不同 Spotify ID 和不同 ISRC。

### 7.4 写 API 的硬校验

手动确认 L2/L3 时：

- 请求参数改为 `original_l1_id` / `candidate_l1_id`。
- 两个 L1 相同，返回 `same_l1_identity`，提示“它们已经是同一个 Spotify 曲目，不需要归并”。
- 两个 L1 不同才进入 L2/L3。
- 已分别属于同 scope 不同组时，使用现有安全统一流程，但操作对象改为 L1。
- 每次 mutation 写 append-only event、递增 revision 并触发精确缓存失效。

## 8. API、路由与前端修改

### 8.1 API 契约

歌曲搜索、分组成员和详情响应增加：

```text
l1_id
spotify_track_id
identity_kind
source_record_count
representative_track_id       # 兼容字段
metadata_conflict
group_scope
```

兼容读取入口可以继续接收旧 `track_id`，但 canonical 响应中的 `track_id` 表示 L1，历史原始 ID 另以 `representative_track_id` 返回。前端不得继续把原始 ID 显示为版本身份。

### 8.2 详情路由

新增 canonical 路由，例如：

```text
/music/tracks/l1/{l1_id}
```

旧 `/music/tracks/{track_id}`：

- 只对应一个 L1 时，重定向 canonical 路由；
- 对应多个 L1 时，展示选择页，不能随意选择播放最多的一项；
- 新生成的年度、榜单、搜索和社区链接全部使用 L1 路由。

### 8.3 设置页“归并与版本”

- 搜索结果一行代表一个 L1，不代表一条历史 `track_id`。
- 同一 Spotify ID 的多条来源记录折叠为“1 个 Spotify 曲目 · N 条历史来源记录”。
- 来源记录默认收起，只在技术详情显示标题、旧艺人、旧专辑和本地 ID。
- 自动检测只展示不同 Spotify ID 的 L2/L3 候选。
- 已保存分组成员数表示 distinct L1 数量。
- 原有伪自动组迁移后不再显示。
- 手动选择同一 L1 两次时禁用确认，并说明无需归并。
- L1 说明改为“每个 Spotify Track ID 独立；相同 ID 已在身份层自动收敛”。
- Desktop 1440px 与 Phone 390px 共享同一响应式工作台和 API。

## 9. 缓存、revision 与后台重建

新增独立 `track_identity_revision`，身份表、来源关系或 L1/L2/L3 mutation 成功后递增。以下缓存键必须包含该 revision 和 `spotify_l1_v1` policy version：

- 六套音乐搜索精确 snapshot；
- Billboard 周聚合、详情和 Year-End 投影；
- 首页摘要；
- 歌曲/专辑/艺人详情；
- 年度总结、Wrapped、音乐档案和播放记录；
- AI 报告缓存。

迁移发布时采用后台 shadow rebuild + 原子切换。旧快照可以在 warming 期间继续提供旧版本事实，但响应必须标明 policy version；不得把旧、新身份结果混在一次响应中，也不得因打开页面同步冷建。

## 10. 分阶段实施顺序

| 阶段 | 优先级 | 交付物 | 完成门禁 |
|---|---|---|---|
| Phase 0：契约冻结与基线 | P0 | 文档规则、真实库审计脚本、raw facts hash、旧/新影子统计 | 可重复得到本方案基线 |
| Phase 1：L1 schema 与 resolver | P0 | 身份表、来源关系、revision、事件级解析、只读 API | 每个合法 Spotify ID 恰好一个 L1 |
| Phase 2：导入止血 | P0 | `_cache_track` Spotify-first、增量 ensure、post-import delta 门禁 | 重复/增量/替换导入不再新增身份污染 |
| Phase 3：逻辑事件与聚合 | P0 | L1 连续播放、周聚合 vNext、Billboard shadow rebuild | raw facts 不变，影子结果可解释 |
| Phase 4：L2/L3 schema 与迁移 | P0 | L1 membership、历史组分类、自动候选重做、审计事件 | 单 L1 组归零，同 scope 唯一 |
| Phase 5：API、路由与 UI | P1 | L1 搜索/详情/归并、兼容重定向、来源记录折叠 | 用户不再把本地记录误认成版本 |
| Phase 6：全消费者切换 | P1 | search/home/detail/yearly/archive/AI 统一 identity | 所有歌曲入口同一 L1 事实 |
| Phase 7：外键与历史治理 | P1/P2 | 新写入 FK、legacy baseline、孤儿详情与受控修复 | 新增外键问题为 0；历史问题不再污染 UI |
| Phase 8：终验与切换 | P0 | 数据库副本、完整门禁、浏览器验收、报告和回滚包 | 全部完成定义通过后原子启用 |

Phase 1–4 应作为同一语义修复批次设计，但可以拆分提交。Phase 5 不得在 Phase 3/4 尚未闭合时仅靠 UI 隐藏旧组。

## 11. 历史数据迁移与回滚

### 11.1 迁移前

1. 使用 SQLite Online Backup 创建带时间戳副本并验证可打开。
2. 记录 `plays`、`tracks`、`track_artists` 的行数与稳定 hash。
3. 导出所有 track groups、members、parent 关系和代表版本。
4. 生成旧/新 L1 对照、冲突组清单、受影响年份和榜单实体清单。
5. 在数据库副本完成全部 migration 和 shadow rebuild。

### 11.2 迁移执行

- 新表 backfill 和旧组分类在一个受控事务中完成。
- 不删除原始表或原始行。
- 被撤销的自动组写迁移事件，记录 before/after 和原因 `collapsed_to_single_spotify_l1`。
- 无法确定的跨 L1 自动组转候选，不静默保留或删除判断。
- 所有新聚合先写 shadow 表，通过断言后原子切换 revision。

### 11.3 回滚

- 功能开关只允许在完整 policy version 间切换，不能混读。
- 回滚时恢复旧聚合 revision 和旧 group membership 读取，不需要还原原始事实。
- migration 后旧表/旧列至少保留一个发布周期；验收完成前不执行 DROP。
- 任一 raw hash、播放总量、外键 delta 或 group invariant 失败，整批停止并恢复数据库备份。

## 12. 测试矩阵

### 12.1 身份单元测试

- 同一 Spotify ID、不同简繁标题、不同本地 artist/album/track ID：一个 L1。
- 同一 Spotify ID 同时来自 audio/video：一个 L1，来源形态仍可拆分。
- 同一旧 `track_id` 出现两个 Spotify ID：两个 L1，逻辑事件按 ID 切断。
- 两个 `track_id` 出现同一 Spotify ID：一个 L1，可跨记录连续合并。
- 不同 Spotify ID、相同曲名和艺人：两个 L1，只能成为候选。
- Spotify ID 缺失：本地 unresolved L1，不按名称自动归并。
- 非法 ID：导入警告/阻断按来源规则执行，不创建 Spotify L1。

### 12.2 分组测试

- 相同 L1 不能创建 L2/L3，返回稳定错误码。
- L2/L3 成员必须是两个以上 distinct L1。
- 一个 L1 在同 scope 最多一个组。
- 已有组确认时安全统一，不丢失成员或 parent。
- 单 L1 历史自动组迁移后撤销并有审计事件。
- 跨 L1 自动组转候选，不直接保留事实。
- L3 parent chain 在 L2 保持分开、在 L3 正确聚合。

### 12.3 导入与恢复测试

- append、replace、reconcile 对同一数据包产生同一 L1 集合。
- 重复导入不增加 L1、来源链接或活动组。
- 导入失败回滚 L1/revision/聚合，不破坏已有 baseline。
- metadata refresh 不因标题/艺人变化拆分 L1。
- post-import health 拦截新增孤儿和身份重复，但不把既有 legacy baseline 伪装成新失败。

### 12.4 消费契约测试

- L1/L2/L3 排行、详情、Billboard、Year-End、搜索、年度总结和音乐档案使用相同 entity key。
- URL 深链、Query cache 和 API response model 同步。
- 旧 track 路由唯一时重定向；歧义时显示选择，不猜测。
- raw facts hash 在人工归并、撤销和身份迁移前后不变。

### 12.5 真实数据库副本验收

- 92,908 条 raw plays、原始时长和 source fingerprint 不变。
- 7,843 个已播放 Spotify ID 对应 7,843 个 Spotify L1。
- 818 个混合 `track_id` 按播放时 ID 正确拆分。
- 5,597 个重复 Spotify ID 不再生成重复搜索结果或伪版本。
- 当前 23 个单 L1 自动组撤销；剩余跨 L1 组进入审核。
- “假如我们还爱着”只显示一个 L1，不显示两个 L2 组或“四个版本”。
- 新旧逻辑播放和时长差异与影子报告一致，超出预期即阻塞。

## 13. 浏览器与用户体验验收

至少覆盖 Desktop 1440×900 和 Phone 390×844：

- 从歌曲详情进入“归并歌曲版本”，定位到正确 L1。
- 搜索同一 Spotify ID 的简繁历史记录只返回一个候选。
- 技术详情可展开查看来源记录，但默认不干扰版本选择。
- 选择相同 L1 时明确提示“已经是同一个 Spotify 曲目”。
- 不同 Spotify ID 可以继续选择 L2/L3、代表版本和保存。
- 已保存分组只展示真实跨 L1 关系，成员封面和有效艺人完整。
- 默认归并级别说明与新 L1 语义一致。
- 页面无横向溢出、遮挡、滚动丢失，主要触控目标至少 44×44px。

## 14. 工程验证入口

按局部到完整执行：

```bash
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py -q
.venv/bin/pytest backend/tests/unit/test_import_maintenance_scoping.py -q
.venv/bin/pytest backend/tests/contract/test_version_merge_confirm_workflow.py -q
.venv/bin/pytest backend/tests/contract/test_merge_level_aggregation.py -q
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
cd frontend && npm test
cd frontend && npm run build
python3 scripts/docs_audit.py
sh scripts/phase5_check.sh
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
```

局部通过只能标记为 Partial；数据库副本、完整全栈门禁和真实浏览器验收全部通过后才是 Pass。

## 15. 文件级改动地图

| 领域 | 主要文件/模块 |
|---|---|
| Schema/migration | `backend/core/db.py`、`backend/core/migrations.py` |
| L1 resolver | 新增 `backend/domains/metadata/track_identity.py` |
| 导入 | `backend/core/import_data.py`、`backend/domains/imports/change_set.py`、`backend/services/import_maintenance_service.py` |
| Spotify metadata | `backend/domains/metadata/spotify_refresh.py` |
| 逻辑事件/聚合 | `backend/domains/playback/logical_timeline.py`、`backend/core/db.py` |
| L2/L3 | `backend/domains/playback/track_groups.py`、`backend/core/version_merge.py`、`backend/api/version_merge.py` |
| 搜索/详情 | `backend/domains/music_search/`、`backend/services/music_search_service.py`、`backend/services/entity_stats_service.py` |
| Billboard/年度 | `backend/domains/billboard/`、`backend/services/yearly_review_service.py`、`backend/services/wrapped_service.py` |
| 前端 API/types | `frontend/src/lib/api.ts`、`frontend/src/types/settings.ts`、query keys |
| 前端归并 | `frontend/src/features/settings/components/VersionMergeSection.tsx` |
| 前端详情/路由 | `frontend/src/features/music/details/`、路由配置及年度深链消费者 |
| 当前规则 | `docs/reference/music-metadata-management.md`、`docs/reference/playback-stats-rules.md` |
| 交付证据 | `docs/reports/` 下新增身份迁移验收报告 |

当前这些路径已有未提交修改，实施必须逐 hunk 合并，禁止覆盖或重置既有工作。

## 16. 完成定义

只有同时满足以下条件，Spotify L1 修复才算完成：

1. 生产读取链中，相同合法 Spotify ID 永远只产生一个 L1。
2. 不同 Spotify ID 在 L1 永远分开，L2/L3 只能通过明确关系建立。
3. 所有逻辑播放、排行、搜索、详情、Billboard、年度和 AI 消费同一身份解析器。
4. `track_groups` 中不存在只含一个 distinct L1 的活动组。
5. 同一 L1 在同 scope 不存在多组映射。
6. 原始播放、原始时长、指纹和原始元数据行未被人工治理改写或删除。
7. 当前真实问题歌曲只显示一个 Spotify L1，艺人和封面正确。
8. append/replace/reconcile 重复执行保持幂等，不再产生同类污染。
9. 新增外键或身份完整性问题为 0；历史残留有明确 baseline、影响和后续治理路径。
10. 完整测试、数据库副本、Desktop/Phone 浏览器和全栈门禁均通过。

本方案完成后，原来“以 `track_id` 作为 L1”的说明必须从当前规则和 UI 中删除；`track_id` 只保留为内部历史来源记录和兼容引用。
