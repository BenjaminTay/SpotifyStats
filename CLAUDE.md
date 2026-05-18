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
                         Streamlit pages ────────────────┘
                         (st.cache_data 缓存查询结果)
```

### 核心模块

- **`app/db.py`** — 数据库层。`get_db()` 获取连接（默认只读，WAL模式），`base_filters()` 生成标准 WHERE 条件片段（排除跳过 + 最短时长 + 仅音乐），`load_plays()` 统一数据加载入口（4 表 JOIN + 过滤），`ensure_schema()` 增量升级 schema（新增表/索引安全重复执行），所有统计页面通过此函数统一过滤逻辑。预聚合表 `agg_weekly_{tracks,albums,artists}` + `agg_config` 存储 Billboard 预计算结果，参数变更时通过参数哈希自动失效回退实时计算。
- **`app/import_data.py`** — ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track，以 `(artist_id, track_name)` 为 key 合并重复版本），同步写入 `track_albums` 关联表，事实表 5000 行批量插入。
- **`app/utils.py`** — `convert_to_local_time()` 固定使用北京时间（UTC+8），忽略 Spotify 上报的 `conn_country` 字段（因 VPN/网络路由可能导致该字段不准确）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/styles.py`** — 全局 CSS 注入。「Vinyl Archive」暖色主题：CSS 变量（`--gold`/`--bg-page`/`--bg-card` 等）、噪点纹理背景、卡片金左边线、衬线字体、表头暖金底色、侧边栏牛皮纸色。`page_header()` 和 `kpi_row()` 和 `filter_badge()` 辅助函数供各页面统一使用。
- **`app/main.py`** — 入口 + 总览仪表盘。使用 `st.navigation` + `st.Page` 定义全站导航结构（中文侧边栏标签/英文文件名），`dashboard()` 函数包含仪表盘全部内容。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `exclude_skipped`, `music_only`），侧边栏仅展示当前参数摘要和数据库状态，首次运行时自动触发数据导入。定义暖色 Plotly 图表模板（`PLOTLY_TEMPLATE`）和色盘（`COLORS`），供各页面复用。
- **`app/pages/09_settings.py`** — 总设置页。集中管理数据过滤（最短播放时长/排除跳过/仅音乐）、Billboard 三个榜单独立 Top N（`bb_top_n` 单曲 / `bb_album_top_n` 专辑 / `bb_artist_top_n` 艺人）、统计周期边界（`bb_week_start_dow`/`bb_week_start_hour`）、数据导入。任何参数变更时自动清除全局缓存并重跑，确保所有页面数据一致。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。`track_albums` 关联表处理同一歌曲（同艺人+同曲名）出现在多张专辑的情况，`_cache_track` 以 `(artist_id, track_name)` 为唯一标识合并重复版本。

`plays` 表预计算了时间字段（`ts_year`, `ts_month`, `ts_week`, `ts_dow`, `ts_hour`, `ts_date`），均为本地时间（固定北京时间 UTC+8）。所有 `boolean` 字段用 INTEGER 0/1 存储。

### 页面结构

使用 `st.navigation` + `st.Page` 统一管理侧边栏导航，文件名保持英文（兼容性），侧边栏显示中文标签。`main.py` 为入口，定义所有页面的导航结构和中文标题；每个页面文件作为独立的 MPA 脚本运行。

`09_settings.py` 为总设置页，集中管理所有参数：数据过滤（`min_ms`/`exclude_skipped`/`music_only`）、Billboard 三个榜单独立 Top N（`bb_top_n`/`bb_album_top_n`/`bb_artist_top_n`）、统计周期边界（`bb_week_start_dow`/`bb_week_start_hour`）、数据导入。`main.py` 侧边栏展示当前过滤参数摘要、Billboard 三个 Top N 徽章和数据库状态。

`08_billboard.py` 为薄入口（15 行），委派至 `app/pages/billboard/` 模块化包（13 个文件，~3,900 行）：

```
app/pages/billboard/
├── __init__.py          # 主路由 + session_state 初始化 + query_params 处理
├── shared.py            # 公共数据加载 + 排名计算 + _bb_url + _render_bb_table
├── weekly.py            # Tab 1: 周榜（单曲/专辑/艺人 3 子 Tab）
├── number_ones.py       # Tab 2: 每周榜首 + 冠单排行 + 空冠 + 大盘
├── track_history.py     # Tab 3: 单曲历史
├── artist_chart.py      # Tab 4: 艺人榜单 + 艺人周榜历史
├── album_chart.py       # Tab 5: 专辑榜单 + 专辑周榜历史
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

两个层级：
- **硬过滤**（排行榜/时长统计）：`skipped=0 AND ms_played >= 30000`（30秒可调），默认启用
- **全量数据**（行为分析页）：跳过率、快进行为等分析需要完整数据，页面标注当前数据范围

`base_filters()` 是唯一的过滤入口，修改此函数即可影响所有统计页面。

## 技术约束

- Python 3.9 — 使用 `Optional[X]` 而非 `X | None`，`dict[str, int]` 可用
- `sys.path.insert(0, ...)` 在每个文件顶部，因为 Streamlit 运行时项目根目录不在 path 中
- SQLite 数据库文件位于项目根目录 `spotify_stats.db`，由 `.gitignore` 排除
- 数据文件夹 `Spotify Extended Streaming History - 251029/` 需手动放置
