# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线 + Inter 无衬线）+ 毛玻璃卡片材质 + 日/夜双皮肤。详细规范见 `frontend/UI_STYLE_GUIDE.md`。

**架构**：FastAPI 后端 + React 前端（Dashboard、Billboard 周榜和三个详情子页面已完成）。Streamlit 原有应用仍可运行。

## 功能

- **总览仪表盘** — 关键指标卡片、月度播放趋势、Top 10 曲目、平台分布、一周听歌热力图
- **播放分析**（5 个子 Tab）— 时间线（年度/月度/周度报告）、排行榜（曲目/艺人/专辑）、行为分析（快进快退/平台/隐身/随机）、听歌时段热力图、艺人深度分析
- **年度回顾**（2 个子 Tab）— 自定义年度总结（Wrapped 风格卡片叙事、听歌人格识别）、Wrapped 2025 官方官方年度回顾（艺人竞速、收听性格、官方排行榜）
- **Billboard 周榜**（12 个子 Tab）— 周榜（单曲/专辑/艺人，支持快速切周、截至当周滚动统计）、每周榜首、单曲历史（含升降列、断档 RE 标记）、艺人榜单、专辑榜单（含版本合并）、走势总榜（Power Score 三维度）、歌曲/艺人/专辑总榜、榜单记录（12 类）、对决（歌曲/专辑/艺人）、发行周期分析（先行曲识别、单曲榜排名线、艺人总览/专辑下钻/多发行对比）
- **账号中心**（6 个子 Tab）— 音乐库（收藏曲目/专辑/艺人 vs 实际收听）、搜索编年史、音乐画像（粉丝层级分析 + Marquee 推广转化）、播客专区、视频分析（≥30s 有效观看）、个人档案
- **设置** — 集中管理所有参数：数据过滤（最短播放时长/仅音乐/合并连续播放）、Billboard 上榜数量、一键重新导入数据

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
uvicorn backend.main:app --reload

# 启动 React 前端（端口 5173，自动代理 /api → 后端 8000）
cd frontend && npm run dev

# 或启动 Streamlit 前端（端口 8501）
streamlit run app/main.py

# 运行后端测试（需先启动后端或有 SQLite 数据库）
pytest backend/tests/ -v
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

## 技术栈

- **FastAPI** — 后端 API 框架（66 个端点，依赖注入，自动 Swagger 文档）
- **React 19** — 前端 UI 框架（TypeScript 6.0，Vite 8，React Router v7）
- **Tailwind CSS v4** — 原子化 CSS 框架（shadcn/ui v4 组件库，`tw-animate-css` 动画）
- **ECharts 6** — 交互式图表（echarts-for-react）
- **Streamlit** — 原有前端（逐步迁移中）
- **SQLite** — 本地数据库（87,000+ 条记录，WAL 模式，查询毫秒级）
- **Pandas** — 数据聚合处理
- **Pydantic** — API 响应模型与数据校验
- **Pytest** — 后端测试框架（142 个测试，覆盖 API 和 Service 层）

## 项目结构

```
SpotifyStats/
├── backend/                            # FastAPI 后端（新架构）
│   ├── main.py                         # FastAPI 入口 + CORS + lifespan
│   ├── dependencies.py                 # Depends 依赖注入（PlayFilters / BillboardFilters + get_conn）
│   ├── api/
│   │   ├── router.py                   # 顶层路由组装（18 个子路由）
│   │   ├── dashboard.py                # GET /api/dashboard/*（6 端点）
│   │   ├── timeline.py                 # GET /api/timeline/*
│   │   ├── leaderboard.py              # GET /api/leaderboard
│   │   ├── behavior.py                 # GET /api/behavior
│   │   ├── listening_hours.py          # GET /api/listening-hours/*
│   │   ├── artist_deep.py              # GET /api/artist/{name}/deep-dive
│   │   ├── wrapped.py                  # GET /api/wrapped/{year}
│   │   ├── wrapped_hub.py              # GET /api/wrapped-hub/*
│   │   ├── library.py                  # GET /api/library/*
│   │   ├── search.py                   # GET /api/search-history/*
│   │   ├── insights.py                 # GET /api/insights/*
│   │   ├── podcast.py                  # GET /api/podcast/*
│   │   ├── video.py                    # GET /api/video/*
│   │   ├── profile.py                  # GET /api/profile
│   │   ├── settings.py                 # GET/PUT /api/settings
│   │   ├── version_merge.py            # CRUD /api/version-merge/*
│   │   ├── import_.py                  # POST /api/import/*（异步导入）
│   │   └── billboard/
│   │       ├── __init__.py             # 路由组装 + /release-cycle 前缀
│   │       ├── data.py                 # GET /api/billboard/data（统一入口）
│   │       ├── details.py              # GET /api/billboard/{track,artist,album,versus}/*（10 端点）
│   │       └── release_cycle.py        # GET /api/billboard/release-cycle/*（4 端点）
│   ├── services/                       # 计算逻辑层
│   │   ├── play_service.py             # 播放数据 + 周度时间线 + 听歌人格 + 工作日/平台×小时分析
│   │   ├── billboard_service.py        # Billboard 计算管线（排名/走势/记录/全时/详情/对决）
│   │   ├── release_cycle_service.py    # 发行周期分析 + Spotify API + 先行曲识别
│   │   ├── library_service.py          # 收藏交叉查询
│   │   ├── search_service.py           # 搜索历史 + 意图分类
│   │   ├── insights_service.py         # 艺人分级 + Marquee 转化
│   │   ├── podcast_service.py          # 播客统计
│   │   ├── video_service.py            # 视频分析
│   │   ├── profile_service.py          # 个人档案
│   │   └── wrapped_hub_service.py      # Wrapped 2025 官方数据
│   ├── models/                         # Pydantic 响应模型
│   │   ├── common.py                   # 通用模型
│   │   ├── dashboard.py                # 仪表盘
│   │   ├── timeline.py                 # 时间线 + Wrapped
│   │   ├── leaderboard.py              # 排行榜
│   │   └── behavior.py                 # 行为分析 + 听歌时段
│   ├── core/                           # 核心工具（从 app/ 原样迁移）
│   │   ├── db.py                       # SQLite 连接 + base_filters + load_plays + merge_consecutive_plays
│   │   ├── utils.py                    # 时区转换 + 平台分类
│   │   ├── json_helpers.py             # numpy/pandas → JSON 安全序列化
│   │   ├── cache.py                    # TTL 缓存装饰器（Spotify API 等外部调用）
│   │   ├── import_data.py              # 串流数据 ETL
│   │   ├── import_account_data.py      # 账号数据 ETL
│   │   └── version_merge.py            # 专辑版本合并引擎
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                   # 共享 fixtures（TestClient, default_params）
│       ├── test_api.py                   # API 层测试（99 个用例，26 类）
│       └── test_services.py              # Service 层测试（43 个用例，9 类）
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
│   │   │   ├── ui/                      # shadcn/ui 组件
│   │   │   ├── charts/                  # 图表组件（RankTrendChart 等）
│   │   │   ├── layout/                  # 布局（AppLayout, Masthead, ThemeToggle）
│   │   │   └── shared/                  # 共享组件（GlassCard, KpiCard, ChangeCell 等）
│   │   ├── pages/                       # 页面（Dashboard, Billboard, TrackDetail, ArtistDetail, AlbumDetail）
│   │   ├── hooks/                       # 自定义 hooks（数据获取 + 客户端缓存 + 周状态保持）
│   │   ├── lib/                         # API 客户端、工具函数、主题配置
│   │   └── types/                       # TypeScript 类型定义
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
- 账号数据独立存储于 `saved_tracks`/`saved_albums`/`saved_artists`/`playlists`/`search_queries`/`podcast_plays`/`user_profile` 等表中

## License

MIT
