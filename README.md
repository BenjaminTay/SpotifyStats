# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 数据中导入播放记录，提供多维度交互式统计分析仪表盘。

## 功能

- **总览仪表盘** — 关键指标卡片、月度播放趋势、Top 10 曲目、平台分布、一周听歌热力图
- **时间维度报告** — 年度汇总、月度分组柱状图（可下钻到 Top 5）、周度趋势
- **排行榜** — 曲目/艺人/专辑排行，支持自定义时间范围、排行指标（播放次数/总时长）、Top N
- **播放行为分析** — 跳过率分析、快进/快退习惯、平台使用、隐身模式、随机播放
- **Spotify Wrapped 风格年度报告** — 卡片式叙事布局，听歌人格识别（Explorer / Loyalist / Binger / Skipper）
- **艺人深度分析** — 选择任意艺人查看完整数据画像，包含月度趋势、Top 曲目、专辑分布、时段热力图
- **听歌时段分析** — 周几×小时热力图、逐年趋势对比、周末 vs 工作日、深夜听歌比例
- **Billboard 周榜** — Billboard Hot 100 风格周榜（周五12:00为界），8 个子 Tab：周榜/冠单历史/单曲历史/艺人榜单/专辑榜单/歌曲总榜/艺人总榜/专辑总榜。支持排名升降、实时 Peak 周数、空冠歌曲、年度冠单统计、榜单大盘排名、歌曲周播放 Top 100、艺人/专辑每周入榜概况、侧边栏年份过滤、搜索艺人/专辑、跨 Tab 曲目导航
- **设置** — 集中管理所有参数：数据过滤（最短播放时长/排除跳过/仅音乐）、Billboard 上榜数量、一键重新导入数据。参数变更自动清除缓存，保证各页面数据一致性

## 快速开始

### 前置条件

- Python 3.9+
- 从 Spotify 下载的 Extended Streaming History 数据（JSON 格式）

> **获取数据**：登录 [Spotify 账户隐私页面](https://www.spotify.com/account/privacy/)，请求下载「Extended Streaming History」数据包。解压后将整个文件夹命名为 `Spotify Extended Streaming History - 251029/` 放到项目根目录。

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
| 排除已跳过 | 开启 | 主动跳过的播放不计入排行 |
| 仅音乐 | 开启 | 排除播客和有声书 |

行为分析页面使用全量数据以保证分析准确性，并在页面上标注当前数据范围。

## 技术栈

- **Streamlit** — Web 应用框架
- **SQLite** — 本地数据库（74,000+ 条记录，查询毫秒级）
- **Plotly** — 交互式图表
- **Pandas** — 数据聚合处理

## 项目结构

```
SpotifyStats/
├── app/
│   ├── main.py                     # 入口 + 总览仪表盘
│   ├── db.py                       # 数据库层（建表/查询/过滤）
│   ├── import_data.py              # JSON → SQLite 导入管线
│   ├── utils.py                    # 工具函数（时区转换/平台归一化）
│   └── pages/
│       ├── 02_timeline.py          # 年度/月度/周度报告
│       ├── 03_leaderboard.py       # 排行榜
│       ├── 04_behavior.py          # 播放行为分析
│       ├── 05_wrapped.py           # Wrapped 年度报告
│       ├── 06_artist_deep.py       # 艺人/专辑深度分析
│       ├── 07_listening_hours.py   # 听歌时段热力图
│       ├── 08_billboard.py         # Billboard 周榜（8 个子页面）
│       └── 09_settings.py          # 设置（集中管理所有参数）
├── scripts/
│   └── analyze_weekly_tracks.py    # 每周独特曲目数分析（确定默认 Top N）
├── .streamlit/config.toml          # 主题配置
├── requirements.txt
└── README.md
```

## 数据库设计

```
artists ──< albums ──< tracks ──< plays
```

- `plays` 表预计算了本地时间字段（year/month/week/dow/hour/date），避免每次查询解析 ISO 8601 时间戳
- 时区转换基于 `conn_country` 字段，CN → UTC+8
- 布尔字段用 INTEGER 0/1 存储（SQLite 无原生 boolean）
- `track_albums` 关联表处理同一歌曲出现在多张专辑的情况（以 `(artist_id, track_name)` 为唯一标识合并重复版本）

## License

MIT
