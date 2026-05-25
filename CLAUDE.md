# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Spotify Extended Streaming History 数据分析 Web 应用。从 Spotify 官方导出的 JSON 播放记录中导入数据到 SQLite，通过 FastAPI + React 提供交互式多维度统计仪表盘。

**架构演进**：已从 Streamlit 单体架构迁移到 FastAPI 后端 + React 前端。后端 56 个 API 端点已全部完成，前端 Dashboard 总览页和 Billboard 周榜页已完成开发。Streamlit 原有应用和后端 API 仍可并行运行。

**UI 主题**：「编辑风 × 液态玻璃」— 杂志式排版（Playfair Display 衬线标题 + Inter 无衬线正文）+ 毛玻璃卡片材质 + 日/夜双皮肤。详细风格指南见 `frontend/UI_STYLE_GUIDE.md`。

## 常用命令

```bash
# 启动 FastAPI 后端（端口 8000，Swagger UI: http://localhost:8000/docs）
source .venv/bin/activate && uvicorn backend.main:app --reload

# 启动前端开发服务器（端口 5173，自动代理 /api → 后端 8000）
cd frontend && npm run dev

# 构建前端生产版本
cd frontend && npm run build

# 添加 shadcn/ui 组件
cd frontend && npx shadcn@latest add <component-name>

# 启动 Streamlit 开发服务器
source .venv/bin/activate && streamlit run app/main.py

# 仅重新导入数据（不启动 UI）
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

# 运行后端测试（使用生产 SQLite 数据库，只读模式）
source .venv/bin/activate && pytest backend/tests/ -v

# 运行单个测试文件
source .venv/bin/activate && pytest backend/tests/test_api.py -v
source .venv/bin/activate && pytest backend/tests/test_services.py -v
```

## 架构

### 数据流

```
JSON 文件 (Spotify导出) ──→ import_data.py ──→ SQLite (spotify_stats.db)
                                    │
JSON 文件 (账号数据)  ──→ import_account_data.py ──┘
                                                        │
                    ┌───────────────────────────────────┘
                    │
                    ├──→ FastAPI backend (backend/)
                    │    ├── api/      路由层 (Depends 依赖注入)
                    │    ├── services/ 计算逻辑层 (lru_cache)
                    │    ├── models/   Pydantic 响应模型
                    │    └── core/     核心工具 (db, utils, cache, json_helpers)
                    │
                    └──→ Streamlit app (app/)
                         st.cache_data 缓存查询结果
```

### 后端架构 (backend/)

FastAPI 后端采用三层分离架构：**路由层 (api/)** → **服务层 (services/)** → **核心工具层 (core/)**。

#### 路由层 (api/)

18 个子路由模块，共 56 个 API 端点。所有路由通过 `backend/api/router.py` 组装，挂载到 `backend/main.py` 的 `/api` 前缀下。

**过滤参数依赖注入** (`backend/dependencies.py`)：
- `PlayFilters` — 标准播放数据过滤（`min_ms`, `music_only`, `merge_enabled`），用于仪表盘、时间线、排行榜、行为分析、听歌时段等端点
- `BillboardFilters` — Billboard 计算过滤（继承播放过滤 + `bb_top_n`, `bb_album_top_n`, `bb_artist_top_n`, `bb_week_start_dow`, `bb_week_start_hour`, `year_start`, `year_end`）
- `get_conn()` — 数据库连接依赖注入（默认只读连接）

端点使用方式：`def endpoint(filters: PlayFilters = Depends(), conn: Connection = Depends(get_conn)):`

**连接管理约定**：
- API 层：通过 `Depends(get_conn)` 注入连接，请求结束时自动关闭
- 非缓存服务：接收 `conn` 参数从 API 层传入
- 缓存服务（`@lru_cache` / `@ttl_cached`）：内部调用 `get_db()` 获取连接（连接对象不可哈希，无法作为缓存键）

**端点清单**：
```
GET  /api/health                         健康检查
GET  /api/dashboard/*                    仪表盘（6 端点：summary, monthly-trend, top-tracks, platform-dist, dow-dist, random-track）
GET  /api/timeline/*                     时间线（annual, monthly）
GET  /api/leaderboard                    排行榜（track/artist/album × plays/hours × all/year）
GET  /api/behavior                       行为分析（reason_end, reason_start, fwdbtn, shuffle, platform）
GET  /api/listening-hours/*              听歌时段（heatmap, yearly-heatmap, late-night）
GET  /api/artist/{name}/deep-dive        艺人深度分析
GET  /api/wrapped/{year}                 自定义年度总结
GET  /api/wrapped-hub/*                  Wrapped 2025 官方
GET  /api/library/*                      音乐库
GET  /api/search-history/*               搜索编年史
GET  /api/insights/*                     音乐画像
GET  /api/podcast/*                      播客
GET  /api/video/*                        视频分析
GET  /api/profile                        个人档案
GET  /api/billboard/data                  Billboard 统一数据入口（返回全部 15 个数据结构，~2-5MB JSON）
GET  /api/billboard/release-cycle/*       发行周期分析（artist-list, artist/{name}, artist/{name}/album/{album}, compare）
GET  /api/settings                       设置（GET 读取 / PUT 更新）
GET  /api/version-merge/*                版本合并管理（groups, detect, apply）
POST /api/import/streaming               串流数据导入（异步任务）
POST /api/import/account                 账号数据导入
```

#### 服务层 (services/)

计算逻辑从 Streamlit 页面中提取，不依赖任何 Web 框架。每个服务文件职责单一：

- **`play_service.py`** — 核心播放数据服务。`load_plays()` 封装，通用 groupby 聚合（按年/月/周/小时/平台/艺术家等），仪表盘 KPI、时间线、排行榜、行为分析、听歌时段热力图、年度总结 Wrapped 等所有基于播放数据的端点均调用此服务。Dashboard 相关函数支持可选 `df` 参数，`/dashboard/full` 端点加载一次 plays 后传递给 5 个子函数复用，避免 6 次冗余 SQL 查询
- **`billboard_service.py`** — Billboard 计算管线。`compute_billboard_data()` 一次性计算 15+ 数据结构（周榜 ×3、总榜 ×3、走势总榜 ×3、榜单记录、每周榜首等），`@lru_cache(maxsize=1)` 缓存完整结果。Power Score 只计算一次（原 Streamlit 代码重复计算 ~10 次）
- **`release_cycle_service.py`** — 发行周期分析。艺人发行列表、单曲 Billboard 历史、专辑周期指标（首周排名、峰值、影响力得分、半衰期）、先行曲识别（三级查找：DB → Spotify API → 最早播放日期）、`compare_releases()` 多发行叠加对比。`@ttl_cached` 缓存 Spotify API 令牌（~58 分钟 TTL）
- **`library_service.py`** — 收藏交叉查询（收藏曲目/专辑/艺人与实际收听对比）
- **`search_service.py`** — 搜索历史统计（日搜索量、意图分类、时段热力图）
- **`insights_service.py`** — 粉丝层级分析 + Marquee 推广转化率
- **`podcast_service.py`** / **`video_service.py`** / **`profile_service.py`** / **`wrapped_hub_service.py`** — 账号数据页面服务

#### 核心工具层 (core/)

从 `app/` 目录原样迁移或提取的纯逻辑模块，不含任何 Web 框架依赖：

- **`db.py`** — 从 `app/db.py` 完整迁移。`get_db()`, `base_filters()`, `load_plays()`, `merge_consecutive_plays()`, `ensure_schema()`, `build_aggregations()` 等所有函数
- **`utils.py`** — 从 `app/utils.py` 完整迁移。`convert_to_local_time()`, `classify_platform()`
- **`version_merge.py`** — 从 `app/version_merge.py` 完整迁移。`detect_release_groups()`, `apply_detected_groups()`, `create_group()`, `delete_group()` 等
- **`import_data.py`** / **`import_account_data.py`** — 从 `app/` 迁移，progress_callback 改为 threading.Event + 共享字典
- **`json_helpers.py`** — 消除 3 处重复定义的序列化工具。`py_val()` 将 numpy/pandas 类型转为 JSON 安全的原生 Python 类型；`df_to_json()` 将 DataFrame 转为 dict 列表
- **`cache.py`** — 从 `release_cycle_service.py` 提取。`ttl_cached(ttl_seconds)` 装饰器，用于 Spotify API 等需要时间过期的外部调用缓存

#### 响应模型 (models/)

Pydantic v2 模型定义 API 响应结构，按领域拆分：
- `common.py` — 通用模型（分页、错误响应）
- `dashboard.py` — 仪表盘响应
- `timeline.py` — 时间线 + Wrapped 年度总结响应（`AnnualTimelinePoint`, `MonthlyTimelinePoint`, `YearlyWrapped` 等）
- `leaderboard.py` — 排行榜响应（`LeaderboardEntry`, `LeaderboardResponse`）
- `behavior.py` — 行为分析 + 听歌时段响应（`ReasonDist`, `FwdbtnByHour`, `HeatmapResponse` 等）

#### 测试 (tests/)

测试套件使用生产 SQLite 数据库（只读模式），不创建独立测试数据库。旨在验证计算逻辑对真实数据的正确性。

- **`conftest.py`** — 共享 fixtures：`client`（FastAPI TestClient，module 级复用）、`default_params`（默认过滤参数 session 级共享）
- **`test_api.py`** — API 层测试，74 个用例 24 类。覆盖所有 56 个端点：结构验证、数据自洽性、跨端点交叉校验、边界条件（空数据/不存在实体/参数约束）、过滤器变化影响、HTTP 响应格式
- **`test_services.py`** — Service 层测试，30 个用例 7 类。直接调用服务函数验证计算逻辑：数值断言、numpy 类型安全、JSON 序列化、TTL 缓存行为

测试设计模式：真实数据断言（如 `total_plays > 50000`）而非 mock 返回固定值；交叉校验（如 dashboard 的 total_plays 与 timeline 的 annual 求和一致）；边界条件（不存在的艺人返回空、空年份标记 `empty: true`）。

### 前端架构 (frontend/)

React + Vite + Tailwind CSS v4 + shadcn/ui（样式 `base-nova`，基础色 `neutral`，图标库 `lucide-react`）。TypeScript 6.0 + React 19。

**技术栈**：
- **构建**：Vite 8，开发端口 5173，自动代理 `/api` → `localhost:8000`
- **样式**：Tailwind CSS v4（`@tailwindcss/vite` 插件），`tw-animate-css` 动画库
- **主题**：CSS 变量 + `.dark` class 切换，`oklch()` 色彩空间。结构变量在 `@theme inline`，颜色在 `:root` / `.dark`。`useTheme()` hook 提供 localStorage 持久化 + 系统偏好回退
- **组件**：shadcn/ui v4（base-nova 风格），源码在 `@/components/ui/`
- **路由**：React Router v7，当前两个路由：`/`（DashboardPage）、`/billboard`（BillboardPage）
- **图表**：ECharts 6 + echarts-for-react（月度趋势图）；平台分布使用纯 DOM 进度条
- **字体**：Inter Variable（`@fontsource-variable/inter`）+ Playfair Display（Google Fonts CDN）
- **客户端缓存**：模块级变量缓存 API 响应，页面切换时避免重复请求

**目录结构**：
```
frontend/src/
├── components/
│   ├── ui/          ← shadcn/ui 组件（可随意修改）
│   ├── charts/      ← ECharts 封装 + 纯 DOM 图表
│   ├── layout/      ← 布局（AppLayout, Masthead, ThemeToggle）
│   └── shared/      ← 共享组件（GlassCard, KpiCard, WeekSelector, NoiseOverlay, PageSwitcher）
├── pages/           ← 页面组件
│   ├── DashboardPage.tsx  ← 总览仪表盘
│   └── BillboardPage.tsx  ← Billboard 周榜（3 Tab + 排名表）
├── hooks/           ← 自定义 hooks
│   ├── useTheme.tsx  ← 主题管理（Context + localStorage）
│   ├── useDashboard.ts  ← Dashboard 数据获取 + 缓存
│   └── useBillboard.ts  ← Billboard 数据获取 + 缓存 + 周导航
├── lib/             ← API 客户端、工具函数
│   ├── api.ts       ← fetch 封装，类型定义
│   ├── theme.ts     ← 图表色盘常量 + getChartColors(isDark)
│   └── utils.ts     ← cn() 工具（tailwind-merge + clsx）
├── types/           ← TypeScript 类型定义
│   ├── dashboard.ts ← Dashboard 响应类型
│   └── billboard.ts ← Billboard 响应类型
└── UI_STYLE_GUIDE.md ← 详细 UI 风格指南（新增页面必读）
```

**路径别名**：`@/` → `src/`（Vite resolve.alias + tsconfig paths）。

**shadcn/ui 主题**：CSS 变量定义在 `src/index.css`，`components.json` 记录配置。已安装的组件：button, card, table, tabs, select, slider, separator, skeleton, tooltip, badge, avatar, sheet, collapsible, dropdown-menu, scroll-area。

**UI 风格指南**：`frontend/UI_STYLE_GUIDE.md` 包含完整的颜色系统、字体规格、布局模式、组件 API 和页面模板。新增页面时必须参考此文档。

### Streamlit 应用 (app/)

以下为原有 Streamlit 架构文档，在 React 前端构建完成前仍为主要的用户界面。

#### 核心模块

- **`app/db.py`** — 数据库层。`get_db()` 获取连接（默认只读，WAL模式），`base_filters()` 生成标准 WHERE 条件片段（最短时长 + 仅音乐，已移除不可靠的 skipped 过滤），`load_plays()` 统一数据加载入口（4 表 JOIN + 过滤），`merge_consecutive_plays()` 合并连续同曲目播放为逻辑播放次数（先合并再过滤，避免碎片丢失）。`ensure_schema()` 增量升级 schema（新增表/索引/列安全重复执行），所有统计页面通过此函数统一过滤逻辑。预聚合表 `agg_weekly_{tracks,albums,artists}` + `agg_config` 存储 Billboard 预计算结果，参数变更时通过参数哈希自动失效回退实时计算。`release_groups` + `release_group_members` 表管理专辑版本合并关系；`spotify_album_meta` 新增 `total_tracks` 和 `track_list` 列用于版本合并超集检测。
- **`app/import_data.py`** — 串流数据 ETL 管线。逐文件读取 JSON，UTC→本地时间转换，平台字符串归一化，维度表 upsert（artist/album/track，以 `(artist_id, track_name)` 为 key 合并重复版本），同步写入 `track_albums` 关联表，事实表 5000 行批量插入。
- **`app/import_account_data.py`** — 账号数据 ETL 管线。从 Spotify Account Data 包中导入：搜索历史（`search_queries`）、收藏（`saved_tracks`/`saved_albums`/`saved_artists`）、播客（`podcast_plays`/`podcast_interactions`/`saved_shows`）、播放列表（`playlists`/`playlist_tracks`）、社交（`user_follows`）、个人资料（`user_profile`）、Marquee 推广（`marquee_impressions`）、Wrapped 年度回顾（各种 `wrapped_*` 表）、黑名单（`banned_items`）。
- **`app/utils.py`** — `convert_to_local_time()` 固定使用北京时间（UTC+8），忽略 Spotify 上报的 `conn_country` 字段（因 VPN/网络路由可能导致该字段不准确）；`classify_platform()` 将类似 `iOS 15.5 (iPhone14,5)` 归一化为 `ios`。
- **`app/styles.py`** — 全局 CSS 注入。「Vinyl Archive」暖色主题：CSS 变量（`--gold`/`--bg-page`/`--bg-card` 等）、噪点纹理背景、卡片金左边线、衬线字体、表头暖金底色、侧边栏牛皮纸色。`page_header()` 和 `kpi_row()` 辅助函数供各页面统一使用。`PLOTLY_TEMPLATE` 定义全局 Plotly 图表样式（含 legend title 修复），`COLORS` 定义暖色色盘。
- **`app/version_merge.py`** — 版本合并引擎。`detect_release_groups()` 自动检测同名专辑的不同版本（豪华版、Acoustic版等），通过曲目重叠率（Phase 1）和名称归一化（Phase 2）判定合并候选；`apply_detected_groups()` / `create_group()` / `delete_group()` / `update_group_members()` 管理 release groups；`get_album_track_comparison()` 对比两版本曲目差异（共享/独有/加曲）。- **`app/main.py`** — 入口 + 总览仪表盘。使用 `st.navigation` + `st.Page` 定义全站导航结构（中文侧边栏标签/英文文件名），`dashboard()` 函数包含仪表盘全部内容。在 `st.session_state` 中初始化全局过滤参数（`min_ms`, `music_only`, `merge_enabled`），侧边栏展示当前参数摘要和数据库状态，首次运行时自动触发数据导入。
- **`app/pages/09_settings.py`** — 总设置页。集中管理数据过滤（最短播放时长/仅音乐/合并连续播放）、Billboard 三个榜单独立 Top N（`bb_top_n` 单曲 / `bb_album_top_n` 专辑 / `bb_artist_top_n` 艺人）、统计周期边界（`bb_week_start_dow`/`bb_week_start_hour`）、版本合并管理（自动检测/手动创建/已保存组管理）、数据导入。任何参数变更时自动清除全局缓存并重跑，确保所有页面数据一致。

### 数据库设计

维度表 `artists` → `albums` → `tracks`，事实表 `plays` 通过 `track_id` 关联。`track_albums` 关联表处理同一歌曲（同艺人+同曲名）出现在多张专辑的情况，`_cache_track` 以 `(artist_id, track_name)` 为唯一标识合并重复版本。维度表仅保留核心识别字段，Spotify API 元数据（专辑类型、发行日期、热度、厂牌、曲风、封面图、总曲目数 `total_tracks`、曲目列表 `track_list` 等）独立存储在 `spotify_album_meta`/`spotify_artist_meta`/`spotify_track_meta` 三张表中，通过 `spotify_track_uri` 链式关联。`release_groups` + `release_group_members` 两张表管理专辑版本合并（豪华版、Acoustic版等合并为 canonical 名称），`version_merge.py` 提供自动检测和手动管理功能。

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
├── Billboard 周榜 (08_billboard.py) ← 12 Tab，委派至 billboard/ 包
├── 账号中心 (04_account.py)        ← 6 Tab: 音乐库 / 搜索编年史 / 音乐画像 / 播客专区 / 视频分析 / 个人档案
└── 设置 (09_settings.py)
```

每个原始页面暴露 `render()` 函数，由 wrapper 在对应 Tab 内调用。`st.stop()` 均改为 `return`，避免 Tab 内警告波及整个 wrapper。

`08_billboard.py` 为薄入口（15 行），委派至 `app/pages/billboard/` 模块化包（18 个文件，~9,000 行）：

```
app/pages/billboard/
├── __init__.py          # 主路由 + session_state 初始化 + query_params 处理
├── shared.py            # 公共数据加载 + 排名计算 + 版本合并（_normalize_album_column / _apply_album_release_groups / _resolve_album_members / _add_canonical_metadata）+ _bb_url + _render_bb_table
├── weekly.py            # Tab 1: 周榜（单曲/专辑/艺人 3 子 Tab）+ ◀▶ 快速切周 + 截至当周滚动 Peak/Wks/Pk Wks
├── number_ones.py       # Tab 2: 每周榜首 + 冠单排行 + 空冠 + 大盘
├── track_history.py     # Tab 3: 单曲历史 + 升降列（断档 >8 天显示 RE，连续在榜正常计算升降）
├── artist_chart.py      # Tab 4: 艺人榜单 + 艺人周榜历史（含升降列，断档显示 RE）
├── album_chart.py       # Tab 5: 专辑榜单 + 专辑周榜历史（含升降列，断档显示 RE，支持版本合并）
├── power_score.py       # Tab 6: 走势总榜（歌曲/专辑/艺人 Power Score）
├── all_time_tracks.py   # Tab 7: 歌曲总榜
├── all_time_artists.py  # Tab 8: 艺人总榜
├── all_time_albums.py   # Tab 9: 专辑总榜
├── records.py           # Tab 10: 榜单记录（12 类，含版本合并支持）
├── versus.py            # Tab 11: 对决（歌曲/专辑/艺人对决对比，支持版本合并）
└── release_cycle/       # Tab 12: 发行周期分析
    ├── __init__.py       # 主路由 + 艺人选择器 + 三个视图切换（st.session_state）
    ├── shared.py         # 数据加载（load_artist_releases / _ad_hoc_name_grouping / _filter_release_group_duplicates）+ 指标计算 + 先行曲识别（三级查找：DB → Spotify API → 最早播放日期）+ Spotify API 集成
    ├── artist_view.py    # 视图①：艺人总览（KPI 卡片、排名趋势图 + 发行事件标记、发行卡片流、对比入口）
    ├── album_view.py     # 视图②：专辑下钻（周期曲线仅连续周连线、先行曲/最佳单曲单曲榜排名线、歌曲入榜矩阵、老歌回榜、加曲来源）
    └── compare_view.py   # 视图③：多发行周期叠加对比（排名/播放量曲线 + 指标对比表）
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
- Billboard 专辑榜（`billboard/shared.py`）：通过 `_load_album_metadata()` 从 `spotify_album_meta` 获取类型和发行日期，排除 `album_type = 'single'` 的发行，以及专辑发行日之前的周数（同一专辑的单曲提前发行不计入专辑榜）
- 播客专区、音乐画像等账号数据页面：直接查询各自独立的账号数据表，不经过 `base_filters()`

## 技术约束

- Python 3.9 — 使用 `Optional[X]` 而非 `X | None`，`dict[str, int]` 可用
- **后端**：使用标准 Python 绝对导入（`from backend.core.db import get_db`），uvicorn 自动处理模块路径
- **Streamlit**：`sys.path.insert(0, ...)` 在每个文件顶部，因为 Streamlit 运行时项目根目录不在 path 中
- SQLite 数据库文件位于 `data/spotify_stats.db`，由 `.gitignore` 排除
- 数据文件夹结构：`data/streaming/`（长期串流记录）、`data/account/`（账号数据），详见 `data/README.md`
- 数字前缀文件名（如 `02_timeline.py`）通过 `importlib.util.spec_from_file_location()` 动态加载，不要在 wrapper 中直接 `import`
- FastAPI `:path` 参数是贪婪匹配的，含子路径的路由（如 `/artist/{name:path}/album/{album_name:path}`）必须注册在更泛化的路由之前
- `backend/core/json_helpers.py` 是所有 numpy/pandas → JSON 序列化的唯一入口，不要在 service 层重复定义 `_py_val` / `_df_to_json`
- 缓存服务函数使用 `@lru_cache` 时，内部必须调用 `get_db()` 获取连接（连接对象不可哈希）；非缓存服务从 API 层接收 `conn` 参数
