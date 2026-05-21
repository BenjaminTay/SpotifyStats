# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用。从 Spotify 官方导出的 JSON 播放记录中导入数据到 SQLite，通过 Streamlit 提供交互式多维度统计仪表盘。

**UI 主题**：「Vinyl Archive」黑胶档案馆 — 暖奶油白底色 + 暗金强调 + 衬线字体 + 噪点纹理，装饰层用复古唱片美学，数据区域保持清晰可读。

## 常用命令

```bash
# 启动开发服务器
source .venv/bin/activate && streamlit run app/main.py

# 仅重新导入数据（不启动UI）
source .venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, '.')
from app.import_data import import_data
result = import_data()
print(result)
"

# 分析每周独特曲目分布（确定 Billboard 默认 Top N）
source .venv/bin/activate && python3 scripts/analyze_weekly_tracks.py

# 清除 Streamlit 缓存后重启
streamlit run app/main.py --server.clearCaches=true

# 安装/更新依赖
source .venv/bin/activate && pip install -r requirements.txt
```

## 架构

### 数据流

```
JSON 文件 (Spotify导出) ──→ import_data.py ──→ SQLite (spotify_stats.db)
                                    │
JSON 文件 (账号数据)  ──→ import_account_data.py ──┘
                                                        │
                         Streamlit pages ────────────────┘
                         (st.cache_data 缓存查询结果)
```

### 核心模块

- **`app/db.py`** — 数据库层。`get_db()` 获取连接（默认只读，WAL模式），`base_filters()` 生成标准 WHERE 条件片段（最短时长 + 仅音乐，已移除不可靠的 skipped 过滤），`load_plays()` 统一数据加载入口（4 表 JOIN + 过滤），`merge_consecutive_plays()` 合并连续同曲目播放为逻辑播放次数（先合并再过滤，避免碎片丢失）。`ensure_schema()` 增量升级 schema（新增表/索引安全重复执行），所有统计页面通过此函数统一过滤逻辑。预聚合表 `agg_weekly_{tracks,albums,artists}` + `agg_config` 存储 Billboard 预计算结果，参数变更时通过参数哈希自动失效回退实时计算。
- **`app/import_data.py`** — 串流数据 ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track，以 `(artist_id, track_name)` 为 key 合并重复版本），同步写入 `track_albums` 关联表，事实表 5000 行批量插入。
- **`app/import_account_data.py`** — 账号数据 ETL 管线。从 Spotify Account Data 包中导入：搜索历史（`search_queries`）、收藏（`saved_tracks`/`saved_albums`/`saved_artists`）、播客（`podcast_plays`/`podcast_interactions`/`saved_shows`）、播放列表（`playlists`/`playlist_tracks`）、社交（`user_follows`）、个人资料（`user_profile`）、Marquee 推广（`marquee_impressions`）、Wrapped 年度回顾（各种 `wrapped_*` 表）、黑名单（`banned_items`）。
- **`app/utils.py`** — `convert_to_local_time()` 固定使用北京时间（UTC+8），忽略 Spotify 上报的 `conn_country` 字段（因 VPN/网络路由可能导致该字段不准确）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/styles.py`** — 全局 CSS 注入。「Vinyl Archive」暖色主题：CSS 变量（`--gold`/`--bg-page`/`--bg-card` 等）、噪点纹理背景、卡片金左边线、衬线字体、表头暖金底色、侧边栏牛皮纸色。`page_header()` 和 `kpi_row()` 和 `filter_badge()` 辅助函数供各页面统一使用。`PLOTLY_TEMPLATE` 定义全局 Plotly 图表样式（含 legend title 修复），`COLORS` 定义暖色色盘。
- **`app/main.py`** — 入口 + 总览仪表盘。使用 `st.navigation` + `st.Page` 定义全站导航结构（中文侧边栏标签/英文文件名），`dashboard()` 函数包含仪表盘全部内容。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `music_only`, `merge_enabled`），侧边栏展示当前参数摘要和数据库状态，首次运行时自动触发数据导入。
- **`app/pages/09_settings.py`** — 总设置页。集中管理数据过滤（最短播放时长/仅音乐/合并连续播放）、Billboard 三个榜单独立 Top N（`bb_top_n` 单曲 / `bb_album_top_n` 专辑 / `bb_artist_top_n` 艺人）、统计周期边界（`bb_week_start_dow`/`bb_week_start_hour`）、数据导入。任何参数变更时自动清除全局缓存并重跑，确保所有页面数据一致。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。`track_albums` 关联表处理同一歌曲（同艺人+同曲名）出现在多张专辑的情况，`_cache_track` 以 `(artist_id, track_name)` 为唯一标识合并重复版本。维度表仅保留核心识别字段，Spotify API 元数据（专辑类型、发行日期、热度、厂牌、曲风、封面图等）独立存储在 `spotify_album_meta`/`spotify_artist_meta`/`spotify_track_meta` 三张表中，通过 `spotify_track_uri` 链式关联。

`plays` 表预计算了时间字段（`ts_year`, `ts_month`, `ts_week`, `ts_dow`, `ts_hour`, `ts_date`），均为本地时间（固定北京时间 UTC+8）。所有 `boolean` 字段用 INTEGER 0/1 存储。

账号数据表独立于串流事实表：`saved_tracks`/`saved_albums`/`saved_artists`（收藏）、`playlists`/`playlist_tracks`（播放列表）、`search_queries`（搜索历史）、`podcast_plays`/`podcast_interactions`/`saved_shows`（播客）、`user_follows`/`user_profile`（社交与个人资料）、`marquee_impressions`（推广展示）、`wrapped_*`（官方 Wrapped 数据）、`banned_items`（黑名单）。

### 页面结构

使用 `st.navigation` + `st.Page` 统一管理侧边栏导航，文件名保持英文（兼容性），侧边栏显示中文标签。`main.py` 为入口，定义所有页面的导航结构和中文标题；每个页面文件作为独立的 MPA 脚本运行。

侧边栏共 6 个入口（3 个 wrapper + Billboard + 设置 + 首页），Wrapper 页面使用 `importlib.util.spec_from_file_location()` 动态加载数字前缀命名的原始页面模块：

```
侧边栏:
├── 总览仪表盘 (main.py, default)
├── 播放分析 (02_playback.py)       ← 5 Tab: 时间线 / 排行榜 / 行为分析 / 听歌时段 / 艺人深潜
├── 年度回顾 (03_yearly.py)         ← 2 Tab: 自定义年度总结 / Wrapped 2025 官方
├── Billboard 周榜 (08_billboard.py) ← 11 Tab，委派至 billboard/ 包
├── 账号中心 (04_account.py)        ← 6 Tab: 音乐库 / 搜索编年史 / 音乐画像 / 播客专区 / 视频分析 / 个人档案
└── 设置 (09_settings.py)
```

每个原始页面暴露 `render()` 函数，由 wrapper 在对应 Tab 内调用。`st.stop()` 均改为 `return`，避免 Tab 内警告波及整个 wrapper。

`08_billboard.py` 为薄入口（15 行），委派至 `app/pages/billboard/` 模块化包（13 个文件，~3,900 行）：

```
app/pages/billboard/
├── __init__.py          # 主路由 + session_state 初始化 + query_params 处理
├── shared.py            # 公共数据加载 + 排名计算 + _bb_url + _render_bb_table
├── weekly.py            # Tab 1: 周榜（单曲/专辑/艺人 3 子 Tab）+ ◀▶ 快速切周 + 截至当周滚动 Peak/Wks/Pk Wks
├── number_ones.py       # Tab 2: 每周榜首 + 冠单排行 + 空冠 + 大盘
├── track_history.py     # Tab 3: 单曲历史 + 升降列（断档 >8 天显示 RE，连续在榜正常计算升降）
├── artist_chart.py      # Tab 4: 艺人榜单 + 艺人周榜历史（含升降列，断档显示 RE）
├── album_chart.py       # Tab 5: 专辑榜单 + 专辑周榜历史（含升降列，断档显示 RE）
├── power_score.py       # Tab 6: 走势总榜（歌曲/专辑/艺人 Power Score）
├── all_time_tracks.py   # Tab 7: 歌曲总榜
├── all_time_artists.py  # Tab 8: 艺人总榜
├── all_time_albums.py   # Tab 9: 专辑总榜
├── records.py           # Tab 10: 榜单记录（12 类）
└── versus.py            # Tab 11: 对决（歌曲/专辑/艺人对决对比）
```

每个模块暴露 `render(df, weekly, ...)` 函数，由 `__init__.py` 传递所需数据。`st.session_state` 实现跨 Tab 导航、子 Tab 记忆、周选择器位置记忆。

### 数据过滤策略

通过「⚙️ 设置」页面集中管理，参数存入 `st.session_state` 供所有页面读取。变更时自动 `st.cache_data.clear()` + `st.rerun()`，确保 Billboard 等页面拿到全新数据。

两个过滤条件：
- **`ms_played >= min_ms`**（默认 30s）：过滤过短的播放，仅此一个硬过滤条件
- **`music_only`**：排除播客/有声书（`track_id IS NOT NULL`）
- 已移除 `skipped` 过滤——`skipped` 和 `reason_end` 字段反映按钮行为而非收听行为，不可靠

合并连续播放（`merge_enabled`，默认开启）：先合并再过滤，将连续同曲目记录拼接为逻辑播放次数，避免碎片化片段被误丢弃。可关闭以保留原始逐条计数。

`base_filters()` 是唯一的过滤入口，修改此函数即可影响所有统计页面。

**特殊页面过滤策略：**
- 行为分析（`04_behavior.py`）：使用全量数据（`filtered=False, music_only=False`），保证快进/隐身/随机播放等分析准确性
- 视频分析（`15_video.py`）：额外过滤 `ms_played >= 30000`（30 秒），排除滑动时自动预览的噪音（约 87% 视频播放 < 5s）
- Billboard 专辑榜（`billboard/shared.py`）：排除 `album_type = 'single'` 的发行（单曲不是专辑），通过 `load_album_type_map()` 从 `spotify_album_meta` 获取类型信息
- 播客专区、音乐画像等账号数据页面：直接查询各自独立的账号数据表，不经过 `base_filters()`

## 技术约束

- Python 3.9 — 使用 `Optional[X]` 而非 `X | None`，`dict[str, int]` 可用
- `sys.path.insert(0, ...)` 在每个文件顶部，因为 Streamlit 运行时项目根目录不在 path 中
- SQLite 数据库文件位于 `data/spotify_stats.db`，由 `.gitignore` 排除
- 数据文件夹结构：`data/streaming/`（长期串流记录）、`data/account/`（账号数据），详见 `data/README.md`
- 数字前缀文件名（如 `02_timeline.py`）通过 `importlib.util.spec_from_file_location()` 动态加载，不要在 wrapper 中直接 `import`
