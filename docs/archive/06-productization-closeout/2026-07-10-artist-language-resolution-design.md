# 艺人常用语言解析与覆盖率审计设计

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

## 状态与目标

本文给出可以进入实现计划的阶段 A 设计。目标是让 SpotifyStats 的语言统计来自独立、可审核的艺人语言事实，不再从 genre、地区、市场或国籍推断，同时把第一版控制在单人本地应用可以维护的规模。

阶段 A 交付：

- 艺人级常用演唱语言事实、证据和人工审核。
- 按播放时长计算的语言分布与覆盖率。
- Settings 中紧凑的语言数据健康与审核入口。
- 年度回顾删除 genre 到语言的启发式映射，改用真实语言元数据。

## 范围与非目标

- 统计对象是艺人的常用演唱语言估算，不是每首播放歌曲的实际语言。
- genre 与语言是两套独立事实。Spotify genre 是否存在，不影响本地语言事实解析。
- genre、地区、市场和国籍只能作为研究线索，不能成为 approved 语言事实。
- 本地 `track_id` 只用于证明艺人在某首作品中的演唱或器乐身份，不产生曲目级语言结果。
- 阶段 A 不做歌词自动识别、自动外部采集、按专辑或时期覆盖、语言占比拆分、campaign、AI dossier、genre x language 联合矩阵或 AI 年报语义重构。
- `multilingual`、`instrumental` 和 `unknown` 是诚实的终态展示，不会被强行摊入某一种语言。

后续阶段保持独立：阶段 B 才考虑研究档案和补全批次；阶段 C 才计算 genre x language；阶段 D 才改 AI 年报中的 `genre_language_mix` 语义与缓存契约。每个阶段单独规划和发布。

## 当前基线

2026-07-10 按当前数据库重新审计，口径为：

- `min_ms=30000`
- `music_only=true`
- `merge_enabled=true`
- `dynamic_threshold=true`
- `max_merge_gap_minutes=NULL`
- 使用 `tracks.artist_id` 主艺人归属，不通过 `track_artists` fan-out

| 指标 | 当前值 |
| --- | ---: |
| 有有效播放时长的主艺人 | 771 |
| 有效音乐播放时长 | 4,022.5h |
| genre 已知时长 | 4,022.5h (100.0%) |
| legacy 显式语言时长 | 1,966.5h (48.9%) |
| legacy 语言未知时长 | 2,056.0h (51.1%) |
| legacy 语言未知主艺人 | 678 |

这里的 legacy 语言来自现有 genre source/override 字段，只表示可迁移线索，不等于新模型中的 approved 事实。迁移后 coverage 可以下降；下降必须真实展示，不能用 genre 推断补齐。

当前年度页的 `inferLanguageDist(top_genres)` 是 genre 到语言的启发式映射。阶段 A 完成后必须删除该调用。

## 统计语义

### 艺人归属

语言分布按 `plays.track_id -> tracks.artist_id` 归属，每条有效播放只计入一个主艺人并贡献完整 `ms_played`。不得使用 `load_plays_for_artists()`，因为它会把合作曲完整复制给所有署名艺人，导致语言时长膨胀。

无法关联 `track_id` 或主艺人的播放不进入语言分布，单独计为 `excluded_unattributed_hours`。因此：

```text
eligible_hours
= 各单一语言 bucket hours
+ multilingual hours
+ instrumental hours
+ unknown hours
```

默认 `music_only=true` 时，`excluded_unattributed_hours` 通常为 0；若调用方允许非音乐内容，年度 Hero 总时长可以大于 `eligible_hours`，页面必须显示排除说明。

语言统计复用调用方已经应用的 `PlayFilters`。`merge_level` 只影响录音/专辑版本聚合，与艺人语言归属无关，不进入语言 coverage API，也不进入语言缓存键。

### 分类定义

- `single_language`：可靠证据表明艺人长期或主要使用一种演唱语言；一次性翻唱、合作或零星发行不触发多语分类。
- `multilingual`：可靠证据表明艺人经常使用至少两种不同语言或语言变体演唱。
- `instrumental`：艺人整体或主导作品以器乐为主；单首器乐曲或少量器乐发行不满足条件。
- `unknown`：没有 approved source。unknown 不写入 source 表，由 resolver 缺省产生。

## 语言代码

阶段 A 使用应用内部 canonical code registry，不宣称完整兼容 BCP 47。`backend/domains/metadata/language_registry.py` 是唯一注册表，包含：

- `LANGUAGE_REGISTRY_VERSION`
- canonical code、中文显示名和允许的 variant
- 别名规范化，例如 `english -> en`、`chinese -> zh`

初版用 `zh`、`en`、`ko`、`ja` 等稳定统计代码；`mandarin`、`cantonese` 等放在 variant。默认统计按 canonical code 聚合，因此普通话与粤语都属于中文；若二者都是艺人的常用演唱语言，则两个不同的 `(code, variant)` 证据仍可支持 `multilingual`。未注册 code/variant 不能批准，新增值只需扩展注册表和测试，不需要改数据库 schema。

前端不维护第二份语言映射；API 直接返回显示名。

## 阶段 A 数据模型

只新增三张表：事实 source、证据 evidence、审核 review。审计依靠保留的 source/review 历史和 replacement 链，不引入 event sourcing、campaign 表或工作流 trigger。

```sql
CREATE TABLE artist_language_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    classification TEXT NOT NULL,
    primary_language_code TEXT,
    language_variant TEXT,
    raw_language TEXT,
    origin TEXT NOT NULL,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'suggested',
    replaces_source_id INTEGER REFERENCES artist_language_sources(source_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(artist_id, origin, source_key),
    CHECK (classification IN ('single_language', 'multilingual', 'instrumental')),
    CHECK (
        (classification = 'single_language' AND primary_language_code IS NOT NULL) OR
        (classification IN ('multilingual', 'instrumental') AND primary_language_code IS NULL)
    ),
    CHECK (classification = 'single_language' OR language_variant IS NULL),
    CHECK (origin IN ('manual', 'curated_seed', 'legacy_import')),
    CHECK (status IN ('suggested', 'approved', 'rejected', 'superseded')),
    CHECK (replaces_source_id IS NULL OR replaces_source_id != source_id)
);

CREATE UNIQUE INDEX uq_artist_language_one_approved
ON artist_language_sources(artist_id)
WHERE status = 'approved';

CREATE INDEX idx_artist_language_sources_artist
ON artist_language_sources(artist_id, status);

CREATE TABLE artist_language_evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES artist_language_sources(source_id),
    local_track_id INTEGER REFERENCES tracks(track_id),
    claimed_language_code TEXT,
    claimed_language_variant TEXT,
    evidence_kind TEXT NOT NULL,
    performer_attribution TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    evidence_title TEXT NOT NULL,
    evidence_accessed_at TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (evidence_kind IN (
        'artist_profile', 'artist_repertoire', 'editorial_source',
        'track_credit', 'track_language'
    )),
    CHECK (performer_attribution IN (
        'artist_vocal_confirmed', 'artist_instrumental_confirmed',
        'track_language_only', 'not_applicable'
    )),
    CHECK (claimed_language_variant IS NULL OR claimed_language_code IS NOT NULL),
    CHECK (evidence_url LIKE 'https://%'),
    CHECK (length(trim(evidence_title)) > 0),
    CHECK (length(trim(evidence_accessed_at)) > 0),
    CHECK (length(trim(evidence_summary)) > 0)
);

CREATE INDEX idx_artist_language_evidence_source
ON artist_language_evidence(source_id, local_track_id);

CREATE TABLE artist_language_review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    suggested_source_id INTEGER REFERENCES artist_language_sources(source_id),
    play_hours_snapshot REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolution_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (play_hours_snapshot >= 0),
    CHECK (length(trim(reason)) > 0),
    CHECK (status IN ('open', 'approved', 'rejected', 'insufficient_evidence')),
    CHECK (
        status = 'open' OR (
            reviewed_by IS NOT NULL AND
            reviewed_at IS NOT NULL AND
            resolution_note IS NOT NULL AND
            length(trim(reviewed_by)) > 0 AND
            length(trim(reviewed_at)) > 0 AND
            length(trim(resolution_note)) > 0
        )
    ),
    CHECK (
        status NOT IN ('approved', 'rejected') OR suggested_source_id IS NOT NULL
    )
);

CREATE UNIQUE INDEX uq_artist_language_one_open_review
ON artist_language_review_queue(artist_id)
WHERE status = 'open';

CREATE UNIQUE INDEX uq_artist_language_source_review
ON artist_language_review_queue(suggested_source_id)
WHERE suggested_source_id IS NOT NULL;

CREATE INDEX idx_artist_language_reviews_status
ON artist_language_review_queue(status, play_hours_snapshot DESC);
```

不在 source/review 中重复保存 `artist_name` 或 Spotify artist ID；展示时 JOIN `artists`，导入时先解析为本地 `artist_id`。`source_key` 用于 seed/legacy 幂等导入，手动创建时由服务端生成 UUID。

## 证据与审核规则

所有批准动作共用 `validate_approved_language_source()`：

- 所有 evidence 的 code/variant 必须能被 registry 规范化。
- Settings 保存 evidence 时由服务端写当前 UTC `evidence_accessed_at`；reviewed seed 可以携带已记录的访问时间。UI 不要求用户手填时间戳。
- `local_track_id` 如存在，目标艺人必须出现在该曲目的 `track_artists` 中。
- `single_language` 至少有一条 `artist_profile`、`artist_repertoire` 或 `editorial_source` 类型、与 source code 相同且 `performer_attribution=artist_vocal_confirmed` 的艺人级证据；source 指定 variant 时 evidence 也必须匹配，source 未指定 variant 时允许更具体的同 code evidence 支持该宽口径结论。单首 track 证据不能单独证明艺人的长期语言。
- `multilingual` 至少有两个不同的 canonical 艺人级演唱主张，且各自来自 `artist_profile`、`artist_repertoire` 或 `editorial_source` 并标记为 `artist_vocal_confirmed`。code 不同时视为不同语言；code 相同时只有两个不同的非空 variant 才算两个主张，`(zh, NULL)` 与 `(zh, mandarin)` 不能重复计数。同一份权威艺人资料明确列出两种语言时，允许使用同一 URL 建立两条语言主张，不强制两个独立网站。validator 按规范化后的 claim set 去重，重复行不能凑足门槛。
- `instrumental` 至少有一条 `artist_profile`、`artist_repertoire` 或 `editorial_source` 证据，并标记 `artist_instrumental_confirmed`；单条曲目证据不能单独支持。
- `track_language_only` 只能作为线索，不能单独满足 single 或 multilingual 的批准条件。
- URL 可访问性不是自动批准条件；证据可信度由审核者结合来源标题和摘要判断，不使用主观的 0-1 confidence 分数。

证据来源优先参考艺人/厂牌官方资料、正式 credits 或完整作品目录，其次使用可靠数据库和编辑资料。没有官方来源时可以采用可靠非官方来源，但必须在摘要中说明其具体支持了什么结论。LLM 可以协助起草候选和查找线索，不能成为 evidence URL，也不能自动批准。

状态转换固定为：

| 当前 source | 允许动作 | 结果 |
| --- | --- | --- |
| `suggested` | 编辑事实和 evidence | 保持 `suggested` |
| `suggested` | approve | `approved` |
| `suggested` | reject | `rejected` |
| `suggested` | insufficient evidence | source `rejected`，review `insufficient_evidence` |
| `approved` | 用新 candidate 替换 | 旧 source `superseded`，新 source `approved` |
| `rejected` / `superseded` | 无 | 终态，只读 |

UI 和 seed importer 之外没有 DELETE 入口。source/evidence 在 suggested 阶段可编辑；进入 approved、rejected 或 superseded 后由 service 拒绝修改。原始 SQL 不属于受支持的写入接口。

批准或替换使用一个 `BEGIN IMMEDIATE` 事务。若艺人已有 approved source，新 candidate 的 `replaces_source_id` 必须指向该同艺人的 source；事务依次 supersede 旧 source、approve candidate、关闭 review。任一步失败全部回滚。唯一 approved 索引负责最后一道并发保护。

`insufficient_evidence` 是 review 终态：可以没有 source，但必须写 resolution note，艺人在统计中继续属于 unknown。拒绝只否定具体候选，不表示该艺人永久无法分类；以后允许建立新 review。

Settings 的终态 mutation 由服务端写 `reviewed_by=local_user` 和 UTC `reviewed_at`；客户端只提交 action 与 resolution note。seed importer 使用 seed 中明确提供的 reviewer 信息。

source/review 本身已经记录候选、决定、审核人、时间、说明和 replacement 链，足以满足阶段 A 的单用户审计，不再新增 review event 表。

## 解析与统计返回

`resolve_artist_languages_map(conn, artist_ids)` 只批量读取 approved source，返回：

- `artist_id`
- `classification`
- `primary_language_code`
- `language_variant`
- `origin`
- `source_id`

没有 approved source 时返回 unknown 结果，不查询 genre resolver。

`compute_artist_language_distribution(conn, artist_hours_by_id, excluded_hours=0)` 返回：

```text
eligible_hours
excluded_unattributed_hours
classified_hours
unknown_hours
classified_pct
unknown_pct
buckets[]: key, label, classification, hours, share_pct, artist_count
source_hours
top_missing[]: artist_id, artist_name, hours
caveat
```

single artist 进入其 canonical language bucket；multilingual、instrumental、unknown 各自进入同名 bucket。variant 进入审计详情但不拆分默认 bucket。API 返回所有非零 bucket，不使用固定的 chinese/english/korean/japanese/other 字段。

计算先使用未四舍五入的毫秒，最后才格式化 hours/share。门禁以毫秒守恒为准，不要求四舍五入后的百分比恰好等于 100.0。

## 后端与 API

阶段 A 新增：

- `backend/domains/metadata/language_registry.py`
- `backend/domains/metadata/artist_languages.py`
- `backend/domains/metadata/artist_language_review.py`
- `backend/models/artist_language_metadata.py`
- `backend/api/artist_language_metadata.py`
- 一次离线 schema migration
- `data/artist_language_sources.seed.json`
- `scripts/import_artist_language_sources.py`

语言专用 API 只有五个端点：

- `GET /api/metadata/artist-languages/coverage`：接收现有 `PlayFilters`，返回 distribution/coverage 和动态 Top unknown；不接收 `MergeConfig`。
- `GET /api/metadata/artist-languages/reviews?status=open&limit=50`：返回 review、candidate 和 evidence。
- `POST /api/metadata/artist-languages/reviews`：按 `artist_id` 开始或返回现有 open review，并使用与 coverage 相同的 `PlayFilters` 记录 `play_hours_snapshot`。
- `PUT /api/metadata/artist-languages/reviews/{review_id}/source`：创建或编辑该 review 的 suggested source/evidence。
- `PATCH /api/metadata/artist-languages/reviews/{review_id}`：请求体 action 仅允许 `approve`、`reject`、`insufficient_evidence`，终态操作必须带 `resolution_note`。

所有 mutation 使用写连接；不存在独立 source CRUD 或 DELETE API。不存在的资源返回 404，已关闭或并发冲突返回 409，证据校验失败返回结构化 422。

艺人和曲目选择复用现有 `/api/music/search`。只给 `MusicSearchResult` 增加可选 `artist_id` 字段；Settings 搜艺人使用 `kind=artist&include_chart=false`，搜代表曲目使用 `kind=track`。不新增第二套 artist search API。

## 缓存与失效

`artist_language_fact_revision` 使用排序后的 approved fact 元组
`(artist_id, source_id, classification, primary_language_code, language_variant, origin)`
与 `LANGUAGE_REGISTRY_VERSION` 计算稳定 SHA-256 摘要。它不依赖秒级时间戳，也不需要 revision 表。

Wrapped 现有 `_artist_genre_revision()` 扩展为组合的 `_artist_metadata_revision()`，将 genre revision 与 language revision 一起传入 `_get_wrapped_full_cached()`。review/evidence 展示由 TanStack Query mutation 后失效；只有 approved fact 改变时才需要让年度结果缓存失效。阶段 A 不修改 AI 报告持久缓存，相关契约留到阶段 D。

## Seed 与 legacy 数据

schema migration 只建表和索引，绝不联网或迁移事实。

`scripts/import_artist_language_sources.py` 遵循现有 genre seed importer 的 CLI 习惯，支持 `--seed`、`--dry-run`、`--json-output` 和 `--legacy-suggestions`：

- reviewed seed 先解析本地 artist ID，再走同一个 validator。证据完整且显式标记 approved 的行还必须提供真实的 `reviewed_by` 与 `resolution_note`；importer 在同一事务中先建立 suggested source/review，再调用与 UI 相同的 approve service 写成 terminal review，脚本名不冒充审核人。
- seed importer 永不自动替换现有 approved source；冲突写入报告，交给人工 review。
- `--legacy-suggestions` 只把现有 genre source/override 的 language 字段复制为 suggested candidate/open review；无论 URL 是否可访问都不能自动 approved。
- 同一艺人的多个 legacy 值规范化后若一致，只生成一个 candidate；若互相冲突，则不替 importer 选择，报告为 `conflicted` 并留在动态 Top unknown，等待人工开始 review。
- 无法唯一匹配本地 artist 的行不写库，报告为 unresolved。已有 genre 数据不删除、不改写。
- `source_key` 保证重复运行幂等；整批写入失败时回滚。

这样可以复用现有 93 个 legacy 语言线索，又不会把未经语言专项审核的数据包装成新事实。AI 逐个补全时产出同一 seed schema，仍需人工检查证据后才能把状态设为 approved。

## 消费端

### 年度回顾

`wrapped_service._build_genre_panorama()` 保留 genre 计算，并另外从同一已经过滤、限定年份的非 fan-out `year_df` 按 `tracks.artist_id` 构造语言 artist hours。返回的 `genre_panorama.language_dist` 改为动态 `LanguageDistribution`，同时保留既有 genre `coverage` 和 genre `caveat`。

前端：

- 删除 `inferLanguageDist()` 调用和固定 `LanguageDist` 字段。
- 直接渲染 API buckets，并显示“艺人级估算”。
- genre 与语言分别判断是否有数据；即使 top genres 为空，也不能因此隐藏有效语言分布。
- 显示 classified/unknown 百分比；存在 `excluded_unattributed_hours` 时显示排除说明。

### Settings

不增加新的 Settings 顶级卡片、编号或 tab。现有卡片保持原位置和编号，标题从“Genre 数据健康”改为“流派与语言数据健康”；语言健康区作为卡片内部的一个 `CollapsibleSection`，折叠摘要只显示 classified、unknown 和 open review 数量，展开后显示 Top unknown 与“开始审核”按钮。

审核使用一个 dialog：选择分类、语言/variant、填写一条或多条证据，并执行批准、拒绝或“证据不足”。同一展开区用普通筛选菜单查看 open review 与最近 terminal review，dialog 可以查看 evidence 和 replacement 链；不增加审计 tab。不嵌套卡片，不加入 campaign、批次进度、AI dossier 或第二套 tab switch。桌面和 390px 移动端都必须无横向滚动。

现有 `GenreDataHealthSection.tsx` 已较大，语言逻辑放入独立的 `ArtistLanguageHealthSection.tsx`，审核表单再拆为 `ArtistLanguageReviewDialog.tsx`；父组件只负责组合和标题，不顺带重构既有 genre 面板。

mutation 只失效 `queryKeys.metadata.artistLanguages` 和 `queryKeys.yearlyReview`；阶段 A 不无谓刷新 Billboard、账号或 genre taxonomy。

后端模型变化后运行 `cd frontend && npm run generate-types`，同步生成的 OpenAPI types；同时更新 `frontend/src/types/yearly-review.ts` 的手写展示类型，不能只改其中一份。

## 失败与降级

- 没有证据或证据不足：保持 unknown，必要时以 `insufficient_evidence` 关闭 review。
- legacy 候选缺 URL/标题/摘要：保留 suggested，不允许批准。
- 外部网站暂时不可访问：不影响 schema migration 和应用启动；审核者仍可基于已记录摘要决定是否稍后复查。
- 多语或器乐证据不满足规则：422，不自动降为 single。
- stale review 或并发批准：409；事务回滚，不留下零个或两个 approved source。
- 无可归属艺人的播放：进入 `excluded_unattributed_hours`，不伪装成 unknown artist。
- 无任何 eligible play：返回 0 值 distribution 和空 buckets，前端显示数据不足。

## 实施边界与发布门禁

阶段 A 是一个实现计划，包含 migration、resolver/statistics、review API、seed/legacy importer、Wrapped 消费和 Settings/年度 UI。它不依赖阶段 B-D，也不要求先补完全部 678 位 unknown 艺人。

最低测试矩阵：

- Migration：新库/旧库重复运行；三表、索引、CHECK 和 foreign key 正确。
- Registry/validator：别名、variant、single/multilingual/instrumental、track attribution 和无效证据。
- Resolver：只认 approved、按 artist ID 批量查询、unknown、replacement。
- 状态流：一位艺人最多一个 open review 和一个 approved source；approve/reject/insufficient/supersede；失败与并发回滚。
- 统计：主艺人归属、不使用 fan-out、毫秒守恒、excluded 时长、动态 bucket、Top unknown、PlayFilters 参数传播。
- Seed/legacy：dry-run、幂等、整批回滚、unresolved/conflicted、legacy 永不自动批准、不得覆盖 approved。
- Cache：approved fact 或 registry 变化后 Wrapped LRU 不命中；仅编辑 suggested 不失效年度结果。
- API contract：五个端点、404/409/422、`X-Request-ID`、OpenAPI response model。
- 前端：删除未再使用的 `inferLanguageDist()`；genre 空而 language 有值时仍渲染；Settings 审核流程和 390px 布局；生成类型与 OpenAPI 保持一致。

实际发布门禁：语言聚焦 pytest、现有 playback filter propagation tests、`npm test`、`npm run build`、OpenAPI operation/parameter audit、Settings interaction/control inventory smoke，以及年度页和 Settings 的真实浏览器验收。

## 阶段 A 完成判据

- 年度页彻底删除 genre 到语言的推断路径。
- 所有 adopted 语言事实都能从 artist -> approved source -> evidence -> review 再现。
- 语言 bucket 毫秒总和与 `eligible_hours` 守恒；multi/instrumental/unknown 不被重分配。
- Settings 可以完成开始审核、编辑证据、批准、拒绝和证据不足，无需终端命令。
- legacy 数据不会因存在旧 language 字段或 URL 可访问而被自动视为 approved。
- spec 中定义的 Phase A 不依赖自动联网研究、全量人工补齐或后续阶段才能正常工作。
