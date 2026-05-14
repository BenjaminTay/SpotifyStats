# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用。从 Spotify 官方导出的 JSON 播放记录中导入数据到 SQLite，通过 Streamlit 提供交互式多维度统计仪表盘。

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

- **`app/db.py`** — 数据库层。`get_db()` 获取连接（默认只读，WAL模式），`base_filters()` 生成标准 WHERE 条件片段（排除跳过 + 最短时长 + 仅音乐），所有统计页面通过此函数统一过滤逻辑。
- **`app/import_data.py`** — ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track，以 `(artist_id, track_name)` 为 key 合并重复版本），同步写入 `track_albums` 关联表，事实表 5000 行批量插入。
- **`app/utils.py`** — `convert_to_local_time()` 按国家代码查表转本地时间（CN=UTC+8）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/main.py`** — 入口 + 总览仪表盘。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `exclude_skipped`, `music_only`），侧边栏仅展示当前参数摘要和数据库状态，首次运行时自动触发数据导入。
- **`app/pages/09_settings.py`** — 总设置页。集中管理数据过滤（最短播放时长/排除跳过/仅音乐）、Billboard 上榜数量（`bb_top_n`）、数据导入。任何参数变更时自动清除全局缓存并重跑，确保所有页面数据一致。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。`track_albums` 关联表处理同一歌曲（同艺人+同曲名）出现在多张专辑的情况，`_cache_track` 以 `(artist_id, track_name)` 为唯一标识合并重复版本。

`plays` 表预计算了时间字段（`ts_year`, `ts_month`, `ts_week`, `ts_dow`, `ts_hour`, `ts_date`），均为本地时间。所有 `boolean` 字段用 INTEGER 0/1 存储。

### 页面结构

Streamlit 原生多页：`main.py` 为首页，`pages/` 下 8 个分析页自动发现。每个页面独立加载数据，使用 `@st.cache_data(ttl=3600)` 缓存查询结果。页面间通过 `st.session_state` 共享过滤参数。

`09_settings.py` 为总设置页，集中管理所有参数：数据过滤（`min_ms`/`exclude_skipped`/`music_only`）、Billboard 上榜数量（`bb_top_n`）、数据导入。`main.py` 侧边栏仅展示当前参数摘要和数据库状态。

`08_billboard.py` 包含 8 个子 Tab：周榜、冠单历史、单曲历史、艺人榜单、专辑榜单、歌曲总榜、艺人总榜、专辑总榜。Billboard 周以周五 12:00 为界，排名 tiebreaker 为总收听时长。侧边栏仅提供年份范围过滤，数据过滤（最短播放时长/排除跳过/仅音乐）统一遵从「设置」页全局参数。周榜支持实时 Peak 周数（`running_peak_wks`），冠单历史含年度冠单统计和空冠歌曲列表，歌曲总榜含歌曲周播放 Top 100，艺人/专辑榜单含搜索和每周入榜概况。`st.session_state.bb_selected_track_id` 实现跨 Tab 曲目导航，`st.session_state.bb_week_selector` 记忆周选择器位置，`st.session_state.bb_top_n` 控制每周上榜数量。

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
