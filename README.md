# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**UI 主题**：「Vinyl Archive」黑胶档案馆 — 暖奶油白底色、暗金强调色、Georgia 衬线字体、噪点纹理，以复古唱片美学为装饰层，数据区域保持清晰可读。

## 功能

- **总览仪表盘** — 关键指标卡片、月度播放趋势、Top 10 曲目、平台分布、一周听歌热力图
- **播放分析**（5 个子 Tab）— 时间线（年度/月度/周度报告）、排行榜（曲目/艺人/专辑）、行为分析（快进快退/平台/隐身/随机）、听歌时段热力图、艺人深度分析
- **年度回顾**（2 个子 Tab）— 自定义年度总结（Wrapped 风格卡片叙事、听歌人格识别）、Wrapped 2025 官方官方年度回顾（艺人竞速、收听性格、官方排行榜）
- **Billboard 周榜**（11 个子 Tab）— 周榜（单曲/专辑/艺人，支持快速切周、截至当周滚动统计）、每周榜首、单曲历史（含升降列）、艺人榜单、专辑榜单、走势总榜（Power Score 三维度）、歌曲/艺人/专辑总榜、榜单记录、对决
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

# 安装依赖
pip install -r requirements.txt

# 启动应用
streamlit run app/main.py
```

浏览器打开 `http://localhost:8501` 即可使用。首次启动会自动将 JSON 数据导入 SQLite 数据库（约需 10-20 秒），后续启动直接读取。

### 数据过滤

所有过滤参数集中在「⚙️ 设置」页面管理，修改后自动清除全局缓存，保证各页面数据一致性：

| 过滤项 | 默认值 | 说明 |
|--------|--------|------|
| 最短播放时长 | 30 秒 | 过滤误触和快速切歌 |
| 仅音乐 | 开启 | 排除播客和有声书 |
| 合并连续播放 | 开启 | 将连续同曲目播放拼接为逻辑播放次数，再按最短时长过滤 |

行为分析页面使用全量数据以保证分析准确性。视频分析页面仅统计 ≥30s 的播放以排除滑动自动预览的噪音。

## 技术栈

- **Streamlit** — Web 应用框架
- **SQLite** — 本地数据库（86,000+ 条记录，查询毫秒级）
- **Plotly** — 交互式图表（暖色色盘）
- **Pandas** — 数据聚合处理
- **CSS** — 「Vinyl Archive」黑胶档案馆暖色主题（自定义全局 CSS 注入）

## 项目结构

```
SpotifyStats/
├── app/
│   ├── main.py                       # 入口 + 总览仪表盘（st.navigation 导航）
│   ├── db.py                         # 数据库层（建表/查询/过滤/预聚合表/合并连续播放）
│   ├── import_data.py                # 串流数据 JSON → SQLite 导入管线
│   ├── import_account_data.py        # 账号数据 JSON → SQLite 导入管线
│   ├── utils.py                      # 工具函数（固定北京时间 UTC+8 / 平台归一化）
│   ├── styles.py                     # 全局 CSS + Plotly 模板 + 辅助函数
│   └── pages/
│       ├── 02_playback.py            # 播放分析（5 Tab wrapper）
│       ├── 02_timeline.py            #   ├─ 时间线
│       ├── 03_leaderboard.py         #   ├─ 排行榜
│       ├── 04_behavior.py            #   ├─ 行为分析
│       ├── 07_listening_hours.py     #   ├─ 听歌时段
│       ├── 06_artist_deep.py         #   └─ 艺人深潜
│       ├── 03_yearly.py              # 年度回顾（2 Tab wrapper）
│       ├── 05_wrapped.py             #   ├─ 自定义年度总结
│       ├── 10_wrapped_hub.py         #   └─ Wrapped 2025 官方
│       ├── 04_account.py             # 账号中心（6 Tab wrapper）
│       ├── 11_library.py             #   ├─ 音乐库
│       ├── 12_search.py              #   ├─ 搜索编年史
│       ├── 13_insights.py            #   ├─ 音乐画像（粉丝层级+推广）
│       ├── 14_podcast.py             #   ├─ 播客专区
│       ├── 15_video.py               #   ├─ 视频分析（≥30s）
│       ├── 16_profile.py             #   └─ 个人档案
│       ├── 08_billboard.py           # Billboard 周榜（薄入口，委派至 billboard/ 包）
│       ├── 09_settings.py            # 设置（数据过滤 + Billboard 配置 + 数据导入）
│       └── billboard/                # Billboard 模块化包（11 个子 Tab）
│           ├── __init__.py            # 主路由 + session_state 初始化
│           ├── shared.py              # 公共数据加载 + 排名计算
│           ├── weekly.py              # 周榜（单曲/专辑/艺人）
│           ├── number_ones.py         # 每周榜首 + 冠单排行
│           ├── track_history.py       # 单曲历史
│           ├── artist_chart.py        # 艺人榜单
│           ├── album_chart.py         # 专辑榜单
│           ├── power_score.py         # 走势总榜（Power Score）
│           ├── all_time_tracks.py     # 歌曲总榜
│           ├── all_time_artists.py    # 艺人总榜
│           ├── all_time_albums.py     # 专辑总榜
│           ├── records.py             # 榜单记录
│           └── versus.py              # 对决
├── data/
│   ├── README.md                     # 数据使用指引
│   ├── spotify_stats.db              # SQLite 数据库
│   ├── streaming/                    # 长期串流播放记录（JSON）
│   └── account/                      # 账号数据（JSON）
├── scripts/
│   └── analyze_weekly_tracks.py      # 每周独特曲目数分析
├── .streamlit/config.toml            # 主题配置（暖色 + 衬线字体）
├── requirements.txt
└── README.md
```

## 数据库设计

```
artists ──< albums ──< tracks ──< plays
```

- 维度表仅保留核心识别字段（名称、URI），Spotify API 元数据（专辑类型、发行日期、热度、厂牌、曲风、封面图等）独立存储在 `spotify_album_meta` / `spotify_artist_meta` / `spotify_track_meta` 三张表中，通过 `spotify_track_uri` 链式关联
- `plays` 表预计算了本地时间字段（year/month/week/dow/hour/date），避免每次查询解析 ISO 8601 时间戳
- 时区固定使用北京时间 UTC+8（忽略 Spotify 上报的 `conn_country` 字段，避免 VPN/网络路由导致该字段不准确）
- 布尔字段用 INTEGER 0/1 存储（SQLite 无原生 boolean）
- `track_albums` 关联表处理同一歌曲出现在多张专辑的情况（以 `(artist_id, track_name)` 为唯一标识合并重复版本）
- Billboard 专辑榜自动排除 `album_type = 'single'` 的发行（单曲不是专辑）
- 账号数据独立存储于 `saved_tracks`/`saved_albums`/`saved_artists`/`playlists`/`search_queries`/`podcast_plays`/`user_profile` 等表中

## License

MIT
