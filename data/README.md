# Spotify 数据格式说明

> **目标读者**：数据使用者（导入、查询、或分析播放记录的人）
>
> 本文档说明从 Spotify 官方导出的 Extended Streaming History 及 Account Data 的数据格式、目录结构、JSON 字段含义，以及在本项目中的导入与使用方式。

## 目录

- [获取数据](#获取数据)
- [目录结构](#目录结构)
- [Streaming History JSON 格式](#streaming-history-json-格式)
- [Account Data JSON 格式](#account-data-json-格式)
- [导入流程](#导入流程)
- [运行时文件说明](#运行时文件说明)

## 获取数据

1. 登录 [Spotify 隐私设置](https://www.spotify.com/account/privacy/)
2. 在「下载你的数据」区域，勾选 **Extended Streaming History** 和 **Account Data**
3. 点击「请求数据」，Spotify 会在 1-5 天内邮件通知你下载链接
4. 下载的 ZIP 解压后，将 `Streaming_History_Audio_*.json` 放入 `data/streaming/`，`Account Data` 中所有 JSON 放入 `data/account/`
5. 在应用设置页先执行「导入前检查」，确认必需文件可读后，再执行「导入数据」；导入完成后可查看「数据健康」报告

更完整的检查范围和状态含义见 [`docs/reference/data-import-and-health.md`](../docs/reference/data-import-and-health.md)。

> ⚠️ **隐私提示**：播放历史数据包含 IP 地址和精确时间戳，属于个人隐私数据。`data/streaming/` 和 `data/account/` 已被 `.gitignore` 排除，请勿将原始 JSON 提交到版本控制。

## 目录结构

### 输入文件（需手动放置）

```
data/
├── streaming/                           # ← Extended Streaming History JSON
│   ├── Streaming_History_Audio_000.json  #   音频播放记录（按文件分片）
│   ├── Streaming_History_Audio_001.json
│   ├── ...                              #   可能有多个文件（Spotify 按年分片）
│   └── Streaming_History_Video_*.json   #   视频播放记录（可选）
├── account/                             # ← Account Data JSON
│   ├── Wrapped2025.json                 #   Spotify Wrapped 年度数据
│   ├── YourLibrary.json                 #   音乐库（收藏曲目/专辑/艺人）
│   ├── Playlist1.json                   #   歌单数据
│   ├── SearchQueries.json               #   搜索历史
│   ├── Inferences.json                  #   兴趣画像标签
│   ├── YourSoundCapsule.json            #   Sound Capsule 每日统计
│   ├── Marquee.json                     #   推广展示记录
│   ├── StreamingHistory_podcast_0.json  #   播客收听历史
│   ├── Identity.json                    #   账户身份信息
│   ├── UserAttributes.json              #   用户属性
│   ├── Follow.json                      #   关注/粉丝关系
│   ├── UserPrompts.json                 #   用户提示词
│   ├── Payments.json                    #   支付方式（仅记录方式名）
│   ├── DuoNewFamily.json               #   家庭组地址
│   ├── PodcastInteractivityComments.json # 播客评论
│   ├── PodcastInteractivityRatedShow.json # 播客评分
│   └── PodcastInteractivityVotedPollOption.json  # 播客投票
└── README.md                            # ← 本文档
```

### 运行时生成文件

```
data/
├── spotify_stats.db                     # SQLite 数据库（78MB+，导入后生成）
├── spotify_stats.db-shm / .db-wal       # SQLite WAL 文件（运行时自动管理）
├── import_control/                      # 独立控制库、发布锁与批次锁
├── import_sources/                      # 已发布的活动原始来源版本与指针
├── import_backups/                      # 写入前数据库/旧来源恢复点（本地私有）
├── artist_genre_overrides.seed.json     # 人工审校的艺人流派种子数据（~171KB）
├── *_cache.db                           # Billboard、年度、治理等持久派生 sidecar
└── covers/                              # 封面图片缓存
    ├── albums/                          #   专辑封面（WebP，Spotify API 全量拉取）
    └── artists/                         #   艺人头像
```

## Streaming History JSON 格式

每个 `Streaming_History_Audio_*.json` 是一个 JSON 数组，每一条记录代表一次播放事件。

### 顶层结构

```json
[
  {
    "ts": "2025-01-15T14:23:45Z",
    "ms_played": 214000,
    "master_metadata_track_name": "Bohemian Rhapsody",
    "master_metadata_album_artist_name": "Queen",
    "master_metadata_album_album_name": "A Night at the Opera",
    "spotify_track_uri": "spotify:track:6gdLoQ4N4eozgS9nLo8VfH",
    "platform": "Mac OS X 10_15_7 (x86_64)",
    "conn_country": "CN",
    "reason_start": "trackdone",
    "reason_end": "trackdone",
    "shuffle": false,
    "skipped": false,
    "offline": false,
    "incognito_mode": false
  }
]
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts` | `string` | UTC 时间戳，ISO 8601 格式（如 `2025-01-15T14:23:45Z`）。导入时根据 `conn_country` 转换为本地时间。 |
| `ms_played` | `number` | 本次播放时长（毫秒）。应用默认只统计 ≥ 30,000ms（30秒）的有效播放。 |
| `master_metadata_track_name` | `string \| null` | 曲目名称。为 `null` 时表示无音频元数据（如播客片段混入），导入时跳过。 |
| `master_metadata_album_artist_name` | `string \| null` | 专辑艺人名。用于艺术家维度聚合。 |
| `master_metadata_album_album_name` | `string \| null` | 专辑名。用于专辑维度聚合和 Album Project 统计。 |
| `spotify_track_uri` | `string \| null` | Spotify 曲目 URI（格式：`spotify:track:<base62_id>`）。导入时解析为 `spotify_track_id`。 |
| `platform` | `string` | 播放平台（如 `Mac OS X`、`iOS`、`Android`、`Web Player`、`Windows`）。导入时归类为 `ios` / `android` / `desktop` / `web` / `other`。 |
| `conn_country` | `string` | 连接国家代码（ISO 3166-1 alpha-2，如 `CN`、`US`）。用于时区转换。 |
| `reason_start` | `string` | 播放开始原因（如 `trackdone` 上一曲结束、`clickrow` 手动点击、`playbtn` 播放按钮）。 |
| `reason_end` | `string` | 播放结束原因（如 `trackdone` 正常播完、`fwdbtn` 快进、`backbtn` 返回）。 |
| `shuffle` | `boolean` | 是否随机播放模式。 |
| `skipped` | `boolean` | 是否被跳过（用户点击下一曲）。跳过记录不纳入有效播放统计，但仍入库。 |
| `offline` | `boolean` | 是否离线播放。 |
| `incognito_mode` | `boolean` | 是否隐私模式播放。 |

### 有效播放判定

导入完成后，统计查询使用以下规则判定「有效播放」：

1. **最短时长过滤**：`ms_played >= 30000`（默认值，可通过设置修改）
2. **仅音频**：`content_type = 'audio'`（`music_only=true` 时排除视频记录）
3. **连续播放合并**：相邻的音频播放（同一 track_id + 间隔 ≤ 阈值）合并为一次有效 session，过滤碎片记录
4. **动态阈值**：短播放（< 阈值）若连续出现，视为异常跳过而非有效播放

详见 [`docs/reference/playback-stats-rules.md`](../docs/reference/playback-stats-rules.md)。

### 视频记录

`Streaming_History_Video_*.json` 格式与音频记录一致，导入时 `content_type` 标记为 `'video'`。如果 `music_only=true`（默认），视频记录不参与 Billboard/Stats 统计。

## Account Data JSON 格式

Account Data 涵盖用户的 Spotify 账户全量数据，按主题分散在多个 JSON 文件中。

### Wrapped2025.json

Spotify 年度 Wrapped 数据，包含：

| 区块 | 导入表 | 内容 |
|------|--------|------|
| `topArtists` | `wrapped_top_artists` | 年度 Top 艺人排名 + 铁粉百分比 |
| `topTracks` | `wrapped_top_tracks` | 年度 Top 曲目 + 播放次数/时长 |
| `topAlbums` | `wrapped_top_albums` | 年度 Top 专辑 |
| `topArtistRace` | `wrapped_artist_race` | 艺人月度排名竞速（每月排名变化） |
| `clubs` | `wrapped_clubs` | 分众俱乐部（如 "Taylor Nation Top 2%"） |
| `party` | `wrapped_party` | 派对总结（平均流行度、深夜听歌比例、多语言分数等） |
| `listeningAge` | `wrapped_listening_age` | 听歌年龄 + 年代阶段 |
| `archiveReports` | `wrapped_archive_reports` | 档案报告（如「你是一个旋律猎手」等叙事卡片） |
| `topGenres` | `wrapped_top_genres` | 年度 Top 曲风 |
| `topPodcasts` | `wrapped_top_podcasts` | 年度 Top 播客 |

### YourLibrary.json

用户音乐库数据：

| 区块 | 导入表 | 内容 |
|------|--------|------|
| `tracks` | `saved_tracks` | 收藏曲目（track_uri, track_name, artist_name, album_name） |
| `albums` | `saved_albums` | 收藏专辑 |
| `artists` | `saved_artists` | 关注艺人 |
| `shows` | `saved_shows` | 关注播客节目 |
| `bannedTracks` / `bannedArtists` | `banned_items` | 已隐藏曲目/艺人 |

### Playlist1.json

用户创建和收藏的歌单：

```json
{
  "playlists": [
    {
      "name": "我的歌单",
      "lastModifiedDate": "2025-12-01",
      "numberOfFollowers": 0,
      "items": [
        {
          "track": {
            "trackName": "...",
            "artistName": "...",
            "albumName": "...",
            "trackUri": "spotify:track:..."
          },
          "addedDate": "2025-06-15"
        }
      ]
    }
  ]
}
```

### SearchQueries.json

搜索历史，每条搜索包含：
- `searchQuery` — 搜索关键词
- `searchTime` — 搜索时间（UTC）
- `platform` — 搜索平台
- `searchInteractionURIs` — 搜索结果交互 URI

### Inferences.json

Spotify 推断的用户兴趣标签，按类别分组：

| 前缀 | 类别 | 示例 |
|------|------|------|
| `ArtistAffinity_` | 艺人偏好 | `ArtistAffinity_Pop` |
| `1P_Custom_` | 第一方自定义 | `1P_Custom_Playlist_Discover_Weekly` |
| `2P_` | 第三方标签 | `2P_Demographics_Age_25_34` |
| `Interest \| ` | 兴趣分类 | `Interest \| Pop music` |
| `Custom Audience_` | 广告受众 | `Custom Audience_Lookalike` |

### YourSoundCapsule.json

每日统计和亮点事件：
- `highlights[]` — 亮点事件（首个发现、同类粉丝、连续收听、里程碑、单曲循环等 7 种类型）
- `stats[]` — 每日流媒体播放量（`streamCount`、`secondsPlayed`、Top 曲目/艺人/曲风）

### 其他 Account Data 文件

| 文件 | 导入表 | 说明 |
|------|--------|------|
| `StreamingHistory_podcast_0.json` | `podcast_plays` | 播客收听历史 |
| `PodcastInteractivityComments.json` | `podcast_interactions` | 播客评论 |
| `PodcastInteractivityRatedShow.json` | `podcast_interactions` | 播客星级评分 |
| `PodcastInteractivityVotedPollOption.json` | `podcast_interactions` | 播客投票参与 |
| `Identity.json` | `user_profile` | 账户 displayName、头像 URL、认证状态 |
| `UserAttributes.json` | `user_profile` | 用户名、国家、出生日期、性别 |
| `Follow.json` | `user_follows` | 关注/粉丝/屏蔽列表 |
| `UserPrompts.json` | `user_prompts` | 用户提示词回答 |
| `Payments.json` | `user_profile` | 支付方式（仅存储方式名，不含卡号） |
| `DuoNewFamily.json` | `user_profile` | 家庭组地址 |
| `Marquee.json` | `marquee_impressions` | Spotify Marquee 推广展示记录 |

## 导入流程

### 1. Streaming History 导入

当前 Settings 工作台先把每个文件上传到服务端草稿批次，再执行 `finalize`。冻结批次按文件名、类型、大小和 SHA-256 固化，后续预检与执行只读取该不可变版本；浏览器本地路径不会进入 API、运行记录或报告。

执行流程如下：

1. 预检把输入解析到权限受限的临时 staging，并与活动 `fingerprint_version + dataset_digest + record_count` 基线比较。
2. `baseline_required`、`identical`、`snapshot_superset`、`delta_tail`、`reconciled_snapshot` 与风险关系分别得到明确动作；不能证明时不猜测追加或删除。
3. 写入前创建恢复点，并取得跨线程、跨进程 writer lease。事实、活动代际、dataset digest、ChangeSet 和发布日志在同一事务提交；源目录以不可变版本 + 原子指针发布。
4. `identical` 在备份、事实写入和派生重建前结束；超集或安全尾包只写新增事实；历史增删需要绑定当前输入/基线的确认；完整替换仍保留恢复点。
5. 事实提交后按固定阶段恢复：元数据、身份、Album Project/L3、Billboard、候选索引、关键预热、封面补充、精确快照。阶段有 generation/digest/revision 栅栏，失败从对应阶段重试，不重新插入已经发布的事实。
6. 核心统计与全部精确结果分别发布 `core_ready` / `ready`；旧 LKG 可继续服务时显示 warming，没有可信结果时显示 unavailable 或 failed，不返回虚假 0。
7. 原始事实只由事实事务修改；元数据、身份和治理结果写独立覆盖层、revision 与审计记录。

Spotify 凭据或外部服务不可用时，元数据阶段会留下可恢复的 `partial`/失败证据。已经提交的播放事实不会因此整库回滚；依赖这些元数据的 L3、搜索或封面阶段保持未就绪，待外部条件恢复后定向重试。

若已经导入过一批新数据，但当时派生数据没有正确维护，可运行：

```bash
.venv/bin/python scripts/refresh_import_derived_data.py --json-output /tmp/spotify_import_maintenance.json
```

该脚本会复用同一条后置维护管线，适合修复既有 `data/spotify_stats.db`。

### 2. Account Data 导入

`backend/core/import_account_data.py` → `import_all()`：

每个 JSON 文件有独立的导入函数，遵循 `DELETE + INSERT` 幂等模式（重复导入不会产生重复数据）。按顺序执行 9 个导入器：

```
Wrapped 2025 → 音乐库 → 歌单 → 搜索记录 → 兴趣画像
→ Sound Capsule → 推广记录 → 播客数据 → 个人档案
```

### 3. 触发方式

- **设置页数据导入工作台**：创建批次、上传文件、冻结、预检、确认后执行；可分页查看持久运行历史、阶段证据、报告、重试和重新核对
- **旧目录兼容入口**：`POST /api/import/streaming` 仍可读取配置的本地目录，但共用同一计划、writer lease、发布日志和阶段恢复合同
- **账号数据导入**：继续从 Settings 单独触发；账号原始 JSON 不混入 Streaming History 批次
- **命令行派生数据维护**：运行 `scripts/refresh_import_derived_data.py` 可补齐既有导入数据的元数据、专辑项目和榜单聚合
- **首次启动**：若数据库不存在，应用引导用户导入

## 运行时文件说明

### spotify_stats.db — SQLite 数据库

导入完成后生成的唯一数据源。表结构详见 `backend/core/db.py` 的 `ensure_schema()`。

**关键表**：

| 表 | 行数量级 | 说明 |
|----|---------|------|
| `plays` | 10万+ | 播放事件记录（最核心表） |
| `artists` / `albums` / `tracks` | 千级 | 维度表 |
| `track_artists` / `track_albums` | 千-万级 | 多对多关联 |
| `agg_weekly_tracks` / `_albums` / `_artists` | 千级 | Billboard 预聚合表 |
| `saved_tracks` / `saved_albums` / `saved_artists` | 百-千级 | 音乐库收藏 |
| `playlists` / `playlist_tracks` | 十/千级 | 歌单数据 |
| `wrapped_*` (10 张) | 个位数行 | Wrapped 年度数据 |
| `sound_capsule_*` / `podcast_*` | 百级 | 音囊/播客 |
| `search_queries` | 百级 | 搜索历史 |
| `user_profile` / `user_follows` | 十级 | 个人档案 |
| `chat_sessions` / `chat_messages` | 十-百级 | AI 对话历史 |
| `billboard_weekly_*` | 千级 | Billboard 周榜快照 |
| `schema_migrations` | 十级 | 数据库迁移版本记录 |

### 导入控制库、来源与恢复点

- `import_control/control.sqlite3` 独立保存上传批次、运行、阶段 attempt、错误码、报告和恢复动作；同目录还保存发布锁与批次锁。主库恢复不会抹掉失败尝试。
- `import_sources/<batch-id>/packet/` 中的接收批次在冻结前可继续上传，冻结后内容不可变；发布版本另有 `resolved/` 全量视图。系统只接受约定的 Spotify 导出文件名和来源类型。
- `import_sources/` 保存服务端拥有的来源版本；活动指针只在事实提交和目录发布都满足栅栏时切换。启动恢复会完成可证明的切换，或成套恢复到旧库/旧来源。
- `import_backups/` 是本地私有恢复证据，不进入 Git，也不自动清理。清理策略必须另行确认，不能把磁盘回收与一次导入执行混在一起。
- 运行中会出现 `.lock`、WAL/SHM 和临时目录；应用正常退出或恢复后可回收临时 staging，但活动来源、控制库、备份和失败证据必须保留。

### covers/ — 封面缓存

通过 Spotify API 全量拉取的专辑封面和艺人头像，以 WebP 格式缓存到本地。由 `core/cache_manager.py` 管理缓存失效。

- **命名规则**：`albums/{album_id}.webp`、`artists/{artist_id}.webp`
- **静态服务**：FastAPI 挂载 `/covers` 路由直接提供文件
- **回退策略**：Spotify API → 缓存 → 默认占位图
