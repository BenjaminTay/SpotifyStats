# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线 + Inter 无衬线）+ 毛玻璃卡片材质 + 日/夜双皮肤。详细规范见 `frontend/UI_STYLE_GUIDE.md`。

**架构**：FastAPI 后端 + React 前端（Dashboard、stats.fm 风格播放统计、Billboard 周榜、每周榜首、总榜、榜单记录、全局音乐实体详情页含个人播放统计 / Billboard 成绩 / Genius 歌词 / Wikipedia 百科、设置页面含 LLM 配置档案持久化管理）。Streamlit 原有应用仍可运行。

**性能优化**：后端启动后后台预热默认 Dashboard/Analysis/Billboard 缓存，大响应启用 gzip，Billboard 全量计算使用 normalized cache key + single-flight 避免重复冷算，播放统计使用参数化结果缓存。前端使用路由级 lazy 分包、共享 in-flight request、延迟预取常用数据；ECharts 与 OpenCC 按需动态加载，减少首次打开页面的静态下载量。

## 功能

- **总览仪表盘** — 关键指标卡片、月度播放趋势、Top 10 曲目、平台分布、一周听歌热力图
- **播放分析** — stats.fm 风格总体播放统计与个人排行榜：支持 lifetime、今天、本周、今年、最近 4 周、最近 6 个月、自定义日期；可按播放次数 / 播放时长查看歌曲、专辑、艺人排行
- **年度回顾**（2 个子 Tab）— 自定义年度总结（Wrapped 风格渐变卡片叙事、听歌人格识别 6 型、Top 5 排行榜、曲风五大洲全景、24 小时时钟图高峰识别、发现与回归三分类、聆听深度金字塔、特殊时刻、月度钻取、年度对比变化率）+ 官方 Wrapped 2025（俱乐部、艺人竞速、收听年龄、排行榜、存档报告）
- **Billboard 周榜**（12 个子 Tab）— 周榜（单曲/专辑/艺人，支持快速切周、截至当周滚动统计）、每周榜首、单曲历史（含升降列、断档 RE 标记）、艺人榜单、专辑榜单（含版本合并）、走势总榜（Power Score 三维度）、歌曲/艺人/专辑总榜、榜单记录（6 大展区 37 项记录，灵感来自 Billboard Chart Beat / Guinness World Records）、对决（歌曲/专辑/艺人）、发行周期分析（先行曲识别、单曲榜排名线、艺人总览/专辑下钻/多发行对比）
- **全局音乐实体详情** — `/music/tracks/*`、`/music/albums/*`、`/music/artists/*` 独立于 Billboard，整合个人播放统计、Billboard 成绩、Genius 歌词、Wikipedia 百科、发行周期等内容；旧 `/billboard/track|album|artist/*` 自动跳转
- **账号中心**（3 个子 Tab）— 数字身份（个人资料 + Spotify Profile + 兴趣推断标签云 + 声音胶囊高光时刻）、音乐人格（听歌人格 6 型 + 年度回顾入口）、收藏分析（收藏浏览器分页搜索 + 生命周期/化学反应/关键词变迁分析 + Spotify OAuth 收藏日期同步）
- **设置** — 集中管理所有参数：Spotify OAuth 连接（10 个 scope 全覆盖：收藏、档案、top 排行、播放历史、关注艺人、播放列表、实时播放状态）+ 数据同步；数据过滤（最短播放时长/仅音乐/合并连续播放/中文简繁转换）、LLM 翻译与百科结构化（多提供商 API Key 配置 + 命名档案保存/切换）、Billboard 上榜数量与统计周期、专辑版本合并（自动检测/手动创建/已保存组管理）、数据导入（异步进度轮询）
- **Spotify Web API 集成** — OAuth PKCE 授权获取用户数据回填和增强：收藏日期回填（`saved_tracks.added_date`）、个人档案（昵称/头像/邮箱/会员类型/国家/粉丝数）、Top 艺人/曲目 × 3 时间窗口（short/medium/long term，含 popularity 和 genres）、最近 50 首播放 + 精确时间戳、32 个播放列表、实时播放状态（当前播放曲目）

## 快速开始

### 前置条件

- Python 3.9+
- 从 Spotify 下载的 Extended Streaming History 数据（JSON 格式）

> **获取数据**：登录 [Spotify 账户隐私页面](https://www.spotify.com/account/privacy/)，分别请求下载「Extended Streaming History」和「Account Data」数据包。解压后将串流数据放入 `data/streaming/`，账号数据放入 `data/account/`。详见 `data/README.md`。

### 安装与运行

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..

# 启动 FastAPI 后端（端口 8000，Swagger UI: http://localhost:8000/docs）
# 开发时只监听 backend/，避免 --reload 扫描 .venv、frontend/node_modules、data 导致 CPU 持续偏高
uvicorn backend.main:app --reload --reload-dir backend

# 调试冷启动或暂时不需要预热缓存时，可关闭启动预热
SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend

# 启动 React 前端（端口 5173，自动代理 /api → 后端 8000）
cd frontend && npm run dev

# 或启动 Streamlit 前端（端口 8501）
streamlit run app/main.py

# Spotify OAuth 功能需要 HTTPS 回调 URL，开发环境使用 ngrok 隧道
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

# 运行后端测试（使用 SQLite 数据库，只读模式）
pytest backend/tests/ -v

# 快速验证测试耗时与慢点
pytest backend/tests/ --durations=20 -q
```

浏览器打开 `http://localhost:5173` 使用 React 界面，或 `http://localhost:8000/docs` 查看 API 文档。首次启动会自动将 JSON 数据导入 SQLite 数据库（约需 10-20 秒），后续启动直接读取。

### 数据过滤

所有过滤参数集中在「⚙️ 设置」页面管理，修改后自动清除全局缓存，保证各页面数据一致性：

| 过滤项 | 默认值 | 说明 |
|--------|--------|------|
| 最短播放时长 | 30 秒 | 过滤误触和快速切歌 |
| 仅音乐 | 开启 | 排除播客和有声书 |
| 合并连续播放 | 开启 | 将连续同曲目播放拼接为逻辑播放次数，再按最短时长过滤 |

行为分析页面使用全量数据以保证分析准确性。视频分析页面仅统计 ≥30s 的播放以排除滑动自动预览的噪音。

## 性能与缓存

- 后端默认预热 `load_plays()`、播放统计默认页和 `compute_billboard_data()`，启动后短时间 CPU 占用较高属于正常现象；预热后 Dashboard/Analysis/Billboard 首次访问通常接近热缓存响应。如需调试冷启动，可设置 `SPOTIFY_STATS_WARMUP=0`。
- 开发模式使用 `uvicorn --reload --reload-dir backend`，只监听后端代码变更；不要让 reloader 扫描整个仓库，否则 `.venv`、`frontend/node_modules`、`data` 等大目录会导致 CPU 持续偏高。
- Billboard 全量数据使用规范化参数缓存，位置参数和关键字参数会命中同一个 cache key；`singleflight()` 避免预热和用户请求并发时重复计算。
- `/api/billboard/entity-lists` 直接复用已计算好的 summary/power score 数据生成选择器列表，避免从大 weekly JSON 重建 DataFrame。
- 前端页面按路由分包，Dashboard/Billboard/Analysis 使用共享 in-flight request 或参数化缓存；布局渲染后延迟预取常用数据，减少页面第一次点击等待。
- ECharts 和 OpenCC 是独立动态 chunk：图表出现时加载 ECharts，用户切换简/繁中文时才加载 OpenCC 字典。

## 技术栈

- **FastAPI** — 后端 API 框架（85+ 个端点，依赖注入，自动 Swagger 文档，lifespan 后台缓存预热，gzip 大响应压缩）
- **React 19** — 前端 UI 框架（TypeScript 6.0，Vite 8，React Router v7，路由级 lazy 分包）
- **Tailwind CSS v4** — 原子化 CSS 框架（shadcn/ui v4 组件库，`tw-animate-css` 动画）
- **ECharts 6** — 交互式图表（echarts-for-react，组件内动态加载）
- **Streamlit** — 原有前端（逐步迁移中）
- **SQLite** — 本地数据库（87,000+ 条记录，WAL 模式，查询毫秒级）
- **Pandas** — 数据聚合处理
- **Pydantic** — API 响应模型与数据校验
- **Pytest** — 后端测试框架（183 个测试，覆盖 API 和 Service 层，session 级缓存预热减少重复冷算）

## 项目结构

```
SpotifyStats/
├── backend/                            # FastAPI 后端（新架构）
│   ├── main.py                         # FastAPI 入口 + CORS + gzip + lifespan 缓存预热
│   ├── dependencies.py                 # Depends 依赖注入（PlayFilters / BillboardFilters + get_conn）
│   ├── api/
│   │   ├── router.py                   # 顶层路由组装
│   │   ├── analysis.py                 # GET /api/analysis/{overview,stats,charts}
│   │   ├── music.py                    # GET /api/music/{tracks,albums,artists}/*/stats|plays
│   │   ├── dashboard.py                # GET /api/dashboard/*（6 端点）
│   │   ├── timeline.py                 # GET /api/timeline/*
│   │   ├── leaderboard.py              # GET /api/leaderboard
│   │   ├── behavior.py                 # GET /api/behavior
│   │   ├── listening_hours.py          # GET /api/listening-hours/*
│   │   ├── artist_deep.py              # GET /api/artist/{name}/deep-dive
│   │   ├── wrapped.py                  # GET /api/wrapped/{available-years,{year}/full}（自定义年度总结）
│   │   ├── wrapped_hub.py              # GET /api/wrapped-hub/*
│   │   ├── library.py                  # GET /api/library/*
│   │   ├── search.py                   # GET /api/search-history/*
│   │   ├── insights.py                 # GET /api/insights/*
│   │   ├── podcast.py                  # GET /api/podcast/*
│   │   ├── video.py                    # GET /api/video/*
│   │   ├── profile.py                  # GET /api/profile
│   │   ├── settings.py                 # GET/PUT /api/settings
│   │   ├── lyrics.py                   # GET /api/lyrics/{track_id}（Genius 歌词获取 + 缓存）
│   │   ├── spotify_auth.py              # Spotify OAuth PKCE + 数据同步（login/callback/status/disconnect/sync/data/playing/sync-all，8 端点）
│   │   ├── version_merge.py            # CRUD /api/version-merge/*
│   │   ├── import_.py                  # POST /api/import/*（异步导入）
│   │   └── billboard/
│   │       ├── __init__.py             # 路由组装 + /release-cycle + /enrichment 前缀
│   │       ├── data.py                 # GET /api/billboard/data（统一入口）
│   │       ├── details.py              # GET /api/billboard/{track,artist,album,versus}/*（10 端点）
│   │       ├── release_cycle.py        # GET /api/billboard/release-cycle/*（4 端点）
│   │       └── enrichment.py           # GET /api/billboard/enrichment/{album,artist,track}/*（3 端点）
│   ├── services/                       # 计算逻辑层
│   │   ├── analysis_stats_service.py   # 总体播放统计 + 个人排行榜 + 时间范围解析
│   │   ├── entity_stats_service.py     # 歌曲/专辑/艺人个人播放统计
│   │   ├── play_service.py             # 播放数据 + 周度时间线 + 听歌人格 + 工作日/平台×小时分析
│   │   ├── wrapped_service.py          # 自定义年度总结完整数据构建（英雄区/Top榜/曲风全景/时间故事/发现回归/聆听深度/特殊时刻/月度钻取/年度对比）
│   │   ├── billboard_service.py        # Billboard 计算管线（排名/走势/记录/全时/详情/对决）
│   │   ├── release_cycle_service.py    # 发行周期分析 + Spotify API + 先行曲识别
│   │   ├── library_service.py          # 收藏交叉查询
│   │   ├── search_service.py           # 搜索历史 + 意图分类
│   │   ├── insights_service.py         # 艺人分级 + Marquee 转化
│   │   ├── podcast_service.py          # 播客统计
│   │   ├── video_service.py            # 视频分析
│   │   ├── profile_service.py          # 个人档案
│   │   ├── genius_service.py           # Genius 歌词获取 + SQLite 缓存
│   │   ├── wikipedia_service.py         # Wikipedia 百科扩展（搜索/提取/缓存/翻译/LLM 结构化）
│   │   ├── llm_translator.py            # LLM 翻译与结构化服务（多提供商 + 代理支持）
│   │   ├── spotify_auth.py              # Spotify OAuth PKCE 授权 + 全量数据同步
│   │   ├── account_service.py           # 账号中心聚合服务（identity/habits/collection）
│   │   └── wrapped_hub_service.py      # Wrapped 2025 官方数据
│   ├── models/                         # Pydantic 响应模型
│   │   ├── common.py                   # 通用模型
│   │   ├── dashboard.py                # 仪表盘
│   │   ├── timeline.py                 # 时间线 + Wrapped
│   │   ├── leaderboard.py              # 排行榜
│   │   ├── behavior.py                 # 行为分析 + 听歌时段
│   │   └── wrapped.py                  # 年度总结完整响应模型
│   ├── core/                           # 核心工具（从 app/ 原样迁移）
│   │   ├── db.py                       # SQLite 连接 + base_filters + load_plays + merge_consecutive_plays
│   │   ├── utils.py                    # 时区转换 + 平台分类
│   │   ├── json_helpers.py             # numpy/pandas → JSON 安全序列化
│   │   ├── cache.py                    # TTL 缓存装饰器 + single-flight
│   │   ├── spotify_utils.py             # Spotify Web API 核心工具（PKCE + Token 持久化 + 自动刷新 + 10 scope 全覆盖数据拉取 + 全量同步）
│   │   ├── warmup.py                   # 后端启动缓存预热（Dashboard/Analysis/Billboard）
│   │   ├── genius/                     # Genius API 客户端（lyricsgenius 封装 + 歌词清洗）
│   │   ├── import_data.py              # 串流数据 ETL
│   │   ├── import_account_data.py      # 账号数据 ETL
│   │   └── version_merge.py            # 专辑版本合并引擎
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                   # 共享 fixtures（TestClient, default_params, warm_default_caches）
│       ├── test_api.py                   # API 层测试
│       ├── test_services.py              # Service 层测试
│       └── test_wrapped_full.py          # 年度总结服务专项测试
├── app/                                # Streamlit 前端（原架构，逐步替换）
│   ├── main.py                         # 入口 + 总览仪表盘
│   ├── db.py                           # 数据库层
│   ├── utils.py                        # 工具函数
│   ├── styles.py                       # 全局 CSS + Plotly 模板
│   ├── import_data.py                  # 串流数据 ETL
│   ├── import_account_data.py          # 账号数据 ETL
│   ├── version_merge.py               # 版本合并引擎
│   └── pages/
│       ├── 02_playback.py              # 播放分析（5 Tab wrapper）
│       ├── 03_yearly.py                # 年度回顾（2 Tab wrapper）
│       ├── 04_account.py               # 账号中心（6 Tab wrapper）
│       ├── 08_billboard.py             # Billboard 周榜（薄入口 → billboard/ 包）
│       ├── 09_settings.py              # 设置
│       └── billboard/                  # Billboard 模块化包（18 文件，~9,000 行）
│           ├── __init__.py              # 主路由 + session_state
│           ├── shared.py               # 公共计算 + 排名 + 版本合并
│           ├── weekly.py               # Tab 1: 周榜
│           ├── number_ones.py          # Tab 2: 每周榜首
│           ├── track_history.py        # Tab 3: 单曲历史
│           ├── artist_chart.py         # Tab 4: 艺人榜单
│           ├── album_chart.py          # Tab 5: 专辑榜单
│           ├── power_score.py          # Tab 6: 走势总榜
│           ├── all_time_tracks.py     # Tab 7: 歌曲总榜
│           ├── all_time_artists.py    # Tab 8: 艺人总榜
│           ├── all_time_albums.py     # Tab 9: 专辑总榜
│           ├── records.py             # Tab 10: 榜单记录
│           ├── versus.py              # Tab 11: 对决
│           └── release_cycle/          # Tab 12: 发行周期分析
│               ├── __init__.py
│               ├── shared.py
│               ├── artist_view.py
│               ├── album_view.py
│               └── compare_view.py
├── data/
│   ├── spotify_stats.db                # SQLite 数据库
│   ├── streaming/                      # 长期串流播放记录（JSON）
│   └── account/                        # 账号数据（JSON）
├── frontend/                            # React 前端（新架构）
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                      # shadcn/ui 组件（含 calendar, popover）
│   │   │   ├── charts/                  # 图表组件（ECharts 动态加载，RankTrendChart, ReleaseTimelineChart 等）
│   │   │   ├── layout/                  # 布局（AppLayout, Masthead, ThemeToggle）
│   │   │   └── shared/                  # 共享组件（GlassCard, KpiCard, WeekSelector 含日历弹窗, ChangeCell, CoverCell, ArtistEnrichmentView, AlbumEnrichmentView, KeyFactsCard, StatsGrid, CareerTimeline, GenreTags, ChartBars, FormattedText）
│   │   ├── pages/                       # 页面（Dashboard, YearlyReview, Billboard, NumberOnes, AllTimeCharts, Records, TrackDetail, ArtistDetail, AlbumDetail, AccountCenter, Settings）
│   │   │   ├── yearly-review/           # 年度回顾子组件
│   │   │   └── account/                 # 账号中心子组件（IdentityTab, HabitsTab, CollectionTab）
│   │   ├── hooks/                       # 自定义 hooks（数据获取 + in-flight 缓存 + Spotify OAuth 连接/同步 + 账号中心数据 + 异步导入轮询）
│   │   ├── lib/                         # API 客户端、工具函数、主题配置、OpenCC 动态中文转换、听歌人格主题、曲风地理映射
│   │   └── types/                       # TypeScript 类型定义（dashboard, billboard, settings, account, yearly-review）
│   ├── UI_STYLE_GUIDE.md                # 详细 UI 风格指南
│   ├── index.html
│   └── package.json
├── scripts/
│   ├── analyze_weekly_tracks.py        # 每周独特曲目数分析
│   └── fetch_covers.py                 # Spotify API 封面批量下载
├── .streamlit/config.toml              # Streamlit 主题配置
├── requirements.txt
└── README.md
```

## 数据库设计

```
artists ──< albums ──< tracks ──< plays
```

- 维度表仅保留核心识别字段（名称、URI），Spotify API 元数据（专辑类型、发行日期、热度、厂牌、曲风、封面图等）独立存储在 `spotify_album_meta` / `spotify_artist_meta` / `spotify_track_meta` 三张表中，通过 `spotify_track_uri` 链式关联。`spotify_album_meta` 还存储 `total_tracks` 和 `track_list`（JSON）用于版本合并超集检测。
- `release_groups` / `release_group_members` 表管理专辑版本合并（豪华版、Acoustic版等合并为 canonical 名称统计）。
- `plays` 表预计算了本地时间字段（year/month/week/dow/hour/date），避免每次查询解析 ISO 8601 时间戳
- 时区固定使用北京时间 UTC+8（忽略 Spotify 上报的 `conn_country` 字段，避免 VPN/网络路由导致该字段不准确）
- 布尔字段用 INTEGER 0/1 存储（SQLite 无原生 boolean）
- `track_albums` 关联表处理同一歌曲出现在多张专辑的情况（以 `(artist_id, track_name)` 为唯一标识合并重复版本）
- Billboard 专辑榜自动排除 `album_type = 'single'` 的发行（单曲不是专辑）
- `albums` / `artists` 表新增 `image_url`（Spotify CDN URL）和 `image_path`（本地缓存路径）列，封面通过智能端点 `/covers/{type}/{id}.jpg` 三级回退（本地缓存 → CDN 重定向 + 后台下载 → 404）
- `track_lyrics` 表缓存 Genius 歌词（`track_id` PRIMARY KEY，`lyrics_text` / `genius_url` / `genius_song_id`），按需获取、永久有效
- `settings` 表（KV 存储）持久化应用设置、LLM 配置档案，以及 Spotify OAuth Token + 用户档案（`spotify_user_token` / `spotify_user_profile` JSON blob）+ Top 艺人/曲目 × 6（`spotify_top_*`）+ 最近播放（`spotify_recently_played`）+ 关注艺人（`spotify_followed_artists`）+ 播放列表（`spotify_playlists`），服务重启后自动恢复
- `wikipedia_cache` 表缓存 Wikipedia 百科扩展数据，避免重复 API 调用
- 账号数据独立存储于 `saved_tracks`/`saved_albums`/`saved_artists`/`playlists`/`search_queries`/`podcast_plays`/`user_profile` 等表中

## License

MIT
