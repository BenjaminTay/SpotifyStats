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
- **`app/import_data.py`** — ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track），事实表 5000 行批量插入。
- **`app/utils.py`** — `convert_to_local_time()` 按国家代码查表转本地时间（CN=UTC+8）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/main.py`** — 入口 + 总览仪表盘。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `exclude_skipped`, `music_only`），侧边栏渲染过滤控件，首次运行时自动触发数据导入。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。

`plays` 表预计算了时间字段（`ts_year`, `ts_month`, `ts_week`, `ts_dow`, `ts_hour`, `ts_date`），均为本地时间。所有 `boolean` 字段用 INTEGER 0/1 存储。

### 页面结构

Streamlit 原生多页：`main.py` 为首页，`pages/` 下 6 个分析页自动发现。每个页面独立加载数据，使用 `@st.cache_data(ttl=3600)` 缓存查询结果。页面间通过 `st.session_state` 共享过滤参数。

### 数据过滤策略

两个层级：
- **硬过滤**（排行榜/时长统计）：`skipped=0 AND ms_played >= 30000`（30秒可调），默认启用
- **全量数据**（行为分析页）：跳过率、快进行为等分析需要完整数据，页面标注当前数据范围

`base_filters()` 是唯一的过滤入口，修改此函数即可影响所有统计页面。

## 技术约束

- Python 3.9 — 使用 `Optional[X]` 而非 `X | None`，`dict[str, int]` 可用
- `sys.path.insert(0, ...)` 在每个文件顶部，因为 Streamlit 运行时项目根目录不在 path 中
- SQLite 数据库文件位于项目根目录 `spotify_stats.db`，由 `.gitignore` 排除
- 数据文件夹 `Spotify Extended Streaming History - 251029/` 需手动放置
