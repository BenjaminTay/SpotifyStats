# Streamlit 应用完整功能清单

> 本文档详尽记录原 Streamlit 应用中每一个页面、每一个功能、每一个算法逻辑。
> 用于与 FastAPI 后端对比，确保新架构不遗漏任何功能。

---

## 1. 总览仪表盘 (`app/main.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 1.1 | KPI 卡片行 | 总播放次数、总收听时长(小时)、独特曲目数、独特艺人数的4个st.metric卡片 |
| 1.2 | 月度趋势图 | Plotly 柱状图，显示每月播放次数趋势（单柱） |
| 1.3 | Top 10 曲目排行 | 按播放次数排序的 Top 10 曲目水平条形图 |
| 1.4 | 平台分布 | 水平条形图显示各平台（ios/android/webplayer等）播放占比 |
| 1.5 | 星期分布 | 柱状图显示周一到周日每天的播放次数分布 |
| 1.6 | 随机曲目推荐 | 从所有曲目中随机选取1首，显示曲名、艺人、播放次数 |
| 1.7 | 首次运行自动导入 | 检测数据库是否为空，为空则自动触发 `import_data()` |
| 1.8 | 侧边栏过滤摘要 | 侧边栏显示当前 `min_ms`、`music_only`、`merge_enabled` 参数状态 |
| 1.9 | 导航定义 | 通过 `st.navigation` + `st.Page` 定义全站导航结构（中文标签/英文文件名） |

### 数据查询
- `load_plays()` 全量加载，应用 `base_filters()` 过滤条件
- 平台分布：`groupby("platform_normalized").size()`
- 星期分布：`groupby("ts_dow").size()`

---

## 2. 播放分析 (`app/pages/02_playback.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 2.1 | 5 Tab wrapper | 通过 `importlib.util.spec_from_file_location()` 动态加载5个子页面 |
| 2.2 | Tab 记忆 | 通过 `st.session_state` 保持当前选中的 Tab |

### 子页面路由
- 时间线 (`02_timeline.py`)
- 排行榜 (`03_leaderboard.py`)
- 行为分析 (`04_behavior.py`)
- 听歌时段 (`07_listening_hours.py`)
- 艺人深潜 (`06_artist_deep.py`)

---

## 3. 时间线 (`app/pages/02_timeline.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 3.1 | 年度汇总 | 表格显示每年播放次数、小时数、独特曲目数、独特艺人数、年度Top曲目 |
| 3.2 | 年度对比柱状图 | Plotly 按年分组的柱状图，可切换显示播放次数或小时数 |
| 3.3 | 月度详情 | 按年分色的月度趋势折线图 + 月份选择器 |
| 3.4 | 月度 Top 5 曲目 | 选中月份时通过 st.metric 卡片展示 Top 5 曲目及播放次数 |
| 3.5 | 周度详情 | 周度趋势折线图 + 周选择器 |
| 3.6 | 周度 Top 5 曲目 | 选中周时通过 st.metric 卡片展示 Top 5 曲目 |

### 算法
- 年度聚合：`groupby(["ts_year"]).agg({plays, hours, unique_tracks, unique_artists})`
- 月度聚合：`groupby(["ts_year", "ts_month"])`
- 周度聚合：按 `ts_week`（ISO周）聚合

---

## 4. 排行榜 (`app/pages/03_leaderboard.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 4.1 | 维度切换 | 3个维度：曲目/艺人/专辑 |
| 4.2 | 时间范围 | 4种：全部时间/今年/本月/自定义年份 |
| 4.3 | 指标切换 | 2种：播放次数/收听小时数 |
| 4.4 | Top N 滑块 | 可调范围 5–100 |
| 4.5 | CSV 导出 | `st.download_button` 导出当前排行数据为 CSV |
| 4.6 | 水平条形图 | Plotly 水平条形图显示排行，数值标签在柱右侧 |

### 数据查询
- 曲目排行：`groupby(["track_name", "artist_name"]).agg({play_count, hours})`
- 艺人排行：`groupby("artist_name").agg({play_count, hours})`
- 专辑排行：`groupby(["album_name", "artist_name"]).agg({play_count, hours})`

---

## 5. 行为分析 (`app/pages/04_behavior.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 5.1 | 结束原因分析 | `reason_end` 饼图（trackdone/fwdbtn/backbtn/logout等） |
| 5.2 | 开始原因分析 | `reason_start` 饼图（trackdone/fwdbtn/backbtn/playbtn等） |
| 5.3 | 快进按小时分布 | 折线图显示各小时段快进次数分布 |
| 5.4 | 快进最多曲目 Top 15 | 水平条形图，按 `fwdbtn` 次数排序 |
| 5.5 | 平台月度趋势 | 堆叠面积图，各平台每月播放量变化 |
| 5.6 | 平台×小时热力图 | Plotly 热力图，行=平台，列=小时 |
| 5.7 | 随机播放率 | `shuffle` 比例（百分比 KPI） |
| 5.8 | 随机播放月度趋势 | 折线图显示每月随机播放率变化 |
| 5.9 | 随机播放按平台对比 | 分组柱状图，各平台的随机播放率 |

### 特殊说明
- 使用全量数据（`filtered=False, music_only=False`），保证快进/隐身/随机播放分析准确性

---

## 6. 听歌时段 (`app/pages/07_listening_hours.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 6.1 | 核心热力图 | DOW×Hour 热力图，YlOrBr 色阶，标注 Top 3 高峰时段 |
| 6.2 | 年度趋势 | 多年度逐小时折线图，按年分色 |
| 6.3 | 深夜比例柱状图 | 每年深夜（23:00–5:00）播放占比柱状图 |
| 6.4 | 工作日 vs 周末 | 并排逐小时柱状图（工作日/周末）+ 对比折线 |
| 6.5 | 深夜 KPIs | 深夜时段（23:00–5:00）播放次数/小时数/占比 KPI 卡片 |
| 6.6 | 深夜月度趋势 | 折线图显示每月深夜播放率，含平均值参考线 |
| 6.7 | 深夜逐小时分布 | 柱状图显示深夜各小时播放量 |
| 6.8 | 平台×小时堆叠面积图 | 各平台逐小时播放量的堆叠面积图 |
| 6.9 | 平台×小时归一化比例 | 各平台逐小时归一化为百分比的折线图 |
| 6.10 | 平台高峰标注 | 标注每个平台的高峰时段 |

### 算法
- `ts_dow`: 0=周一 ~ 6=周日（北京时间）
- 深夜定义：`ts_hour >= 23 OR ts_hour < 5`
- 工作日：`ts_dow < 5`（周一至周五），周末：`ts_dow >= 5`

---

## 7. 艺人深潜 (`app/pages/06_artist_deep.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 7.1 | 艺人选择器 | 下拉选择框，按总播放次数降序排列艺人 |
| 7.2 | 统计卡片 | 4个 st.metric：总播放次数/总小时数/独特曲目数/日期范围 |
| 7.3 | 月度活跃图 | 柱状图显示该艺人每月播放次数 |
| 7.4 | Top 20 曲目表 | 该艺人播放最多的20首曲目表格 |
| 7.5 | 专辑分布饼图 | Top 8 专辑的播放占比饼图 + "其他" |
| 7.6 | DOW×Hour 热力图 | 该艺人的星期×小时播放热力图（Blues 色阶） |
| 7.7 | 专辑下钻 | 选择专辑后显示该专辑内曲目排行柱状图 |

### 数据查询
- 艺人列表：`SELECT artist_name, COUNT(*) as cnt FROM plays GROUP BY artist_name ORDER BY cnt DESC`
- 专辑分布：`groupby("album_name").size().nlargest(8)`

---

## 8. 年度回顾 (`app/pages/05_wrapped.py` / `app/pages/03_yearly.py`)

### 8a. 自定义年度总结 (`05_wrapped.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 8a.1 | 年份选择器 | 下拉选择年份 |
| 8a.2 | 总收听分钟 | KPI 卡片 |
| 8a.3 | Top 5 艺人/小时 | 水平条形图 |
| 8a.4 | Top 5 曲目/播放次数 | 水平条形图 |
| 8a.5 | Top 1 专辑/小时 | 卡片展示 |
| 8a.6 | 高峰时段 | 播放次数最多的时段（众数） |
| 8a.7 | 平台分布 | 各平台收听小时数 |
| 8a.8 | 首尾曲目 | 年度第一首和最后一首播放的曲目 |
| 8a.9 | 季节性偏好 | 四季 Top 曲目：春(3-5月)/夏(6-8月)/秋(9-11月)/冬(12,1,2月) |
| 8a.10 | 个性评分体系 | 三维度：探索者(Explorer)/专一者(Loyalist)/狂听者(Binger) |
| 8a.11 | Hero 卡片 | 渐变背景 + CSS 样式卡片展示年度概览 |

### 个性评分算法
- **Explorer（探索者）**: `min(unique_track_ratio / 40 * 100, 100)`
  - unique_track_ratio = 独特曲目数 / 总播放数
- **Loyalist（专一者）**: `min(top_artist_share / 20 * 100, 100)`
  - top_artist_share = Top 艺人播放占比
- **Binger（狂听者）**: `min(avg_hours_per_day / 4 * 100, 100)`
  - avg_hours_per_day = 总小时 / 活跃天数

### 8b. Wrapped 2025 官方 (`10_wrapped_hub.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 8b.1 | URI 名称解析 | `_resolve_uri_name()`: artist→spotify_artist_meta→saved_artists, track→tracks→saved_tracks, album→spotify_album_meta→saved_albums |
| 8b.2 | Hero KPIs | 总收听小时、独特艺人、独特曲目、连续听歌天数 |
| 8b.3 | Club 信息卡 | 官方 Wrapped Club 信息展示 |
| 8b.4 | 艺人热度竞赛 | 5艺人1-11月排名折线图，Y轴翻转（1在顶部） |
| 8b.5 | 派对性格雷达图 | Plotly 五维雷达图：Happy/Love/Party/夜间/Explicit |
| 8b.6 | 多语言得分 | 非母语曲目占比 |
| 8b.7 | 混乱度得分 | 曲风流派多样性 |
| 8b.8 | 平均曲目热度 | Spotify 官方 popularity 均值 |
| 8b.9 | 分享次数 | 分享功能使用次数 |
| 8b.10 | 收听天数 | 全年有播放记录的天数 |
| 8b.11 | 发现艺人 | 首次播放的艺人数量 |
| 8b.12 | 收听年龄 | 从第一首到最后一首的时间跨度 |
| 8b.13 | 档案报告 | 5种特殊日期的卡片展示 |
| 8b.14 | 官方排行榜 | 三列布局：Top 5 曲目/艺人/专辑 |

---

## 9. Billboard 周榜 (`app/pages/08_billboard.py` + `app/pages/billboard/` 包)

### 9a. 主路由 (`__init__.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9a.1 | Session state 初始化 | 跨 Tab 导航状态、query params 解析 |
| 9a.2 | Query param 解析 | `bb_nav`, `bb_id`, `bb_name`, `bb_art`, `bb_date`, `bb_tab`, `bb_subtab` |
| 9a.3 | 配置变更检测 | 检测过滤参数变更 → 清除缓存 + 重跑 |
| 9a.4 | 年份范围过滤 | 滑块选择年份范围 |
| 9a.5 | 预聚合表加载 | 尝试从 `agg_weekly_*` 表加载，参数哈希验证 |
| 9a.6 | 核心计算调用 | `compute_weekly_rankings`, `compute_album_weekly_rankings`, `compute_artist_weekly_rankings`, `compute_power_scores`, `compute_album_power_scores`, `compute_artist_power_scores`, `compute_records` |
| 9a.7 | track_summary 构建 | peak_position, weeks_on_chart, weeks_at_peak, first_week, last_week, total_chart_plays, total_plays, weeks_at_no1, first_peak_week |
| 9a.8 | artist_track_counts 构建 | 每位艺人的曲目/专辑统计 |
| 9a.9 | album_track_counts 构建 | 每张专辑的曲目统计 |
| 9a.10 | 版本合并整合 | 专辑 release group 归一化 + tracks_count/albums_count 修正 |
| 9a.11 | 12 Tab 路由 | CSS Tab 栏样式 + 子模块委派 |

### 9b. 公共模块 (`shared.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9b.1 | `load_billboard_raw()` | SQL 查询 + billboard_week 计算（`days_back = (ts_dow - week_start_dow) % 7`, 同日但在开始小时之前的 +7天） |
| 9b.2 | `_try_load_from_agg()` | 预聚合表参数哈希验证与加载 |
| 9b.3 | `load_track_album_map()` | UNION tracks 和 track_albums 表 |
| 9b.4 | `_load_album_metadata()` | 专辑类型（album>compilation>single 优先级）+ 最早发行日期 |
| 9b.5 | `_add_canonical_metadata()` | release_groups 表 canonical 行注入 |
| 9b.6 | `_get_album_canonical_map()` | 专辑名→canonical 映射 |
| 9b.7 | `_normalize_album_column()` | 列值批量替换为 canonical |
| 9b.8 | `_resolve_album_members()` | 解析 release group 所有成员专辑名 |
| 9b.9 | `_apply_album_release_groups()` | 对 DataFrame 应用 release group 合并 |
| 9b.10 | `compute_weekly_rankings()` | 周排名计算，tiebreaker: play_count DESC → total_ms DESC |
| 9b.11 | `compute_album_weekly_rankings()` | 专辑周排名：排除 singles + 排除发行日前周数（`_bb_week + 6 days >= _rel_date`）+ 应用 release groups |
| 9b.12 | `compute_artist_weekly_rankings()` | 艺人周排名 |
| 9b.13 | `compute_power_scores()` | 走势点数公式：基础分×归一化排名 + 播放密度权重 + 峰值/Top5/Top10 加分 |
| 9b.14 | `compute_album_power_scores()` | 专辑走势点数 |
| 9b.15 | `compute_artist_power_scores()` | 艺人走势点数 |
| 9b.16 | `compute_records()` | 14类榜单记录计算 |
| 9b.17 | `_render_bb_table()` | HTML 表格渲染器，含可点击链接 |
| 9b.18 | `_bb_url()` | URL 构建器 |
| 9b.19 | `_render_record_table()` | 记录表格 + 每行导航链接 |

### Power Score 算法
- **基础分**: 排名归一化分 = `(N - rank + 1) / N × 100`
- **播放密度权重**: `1 + min(3, max(0, log2(plays / median_plays)))`
- **加分项**: 峰值 #1 +15, Top 5 +8, Top 10 +5
- **总分**: `Σ(weekly_base_points × play_intensity_weight + bonus_points)`

### 9c. Tab 1: 周榜 (`weekly.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9c.1 | 周选择器 | ◀ 上一周 / 下一周 ▶ 按钮快速切周 |
| 9c.2 | 3 子 Tab | 单曲榜 / 专辑榜 / 艺人榜 |
| 9c.3 | 子 Tab 记忆 | `st.session_state` 记忆当前子 Tab |
| 9c.4 | 单曲周榜 | 排名表含：排名、LW（上期排名）、Peak（截至当周峰值）、Wks（在榜周数）、Pk Wks（峰值周数）、曲名、艺人、播放次数 |
| 9c.5 | 专辑周榜 | 同上结构，复合键 `album_name|||artist_name` |
| 9c.6 | 艺人周榜 | 同上结构 |
| 9c.7 | LW 计算 | 前一周在榜→显示变化箭头；更早周在榜→RE；首次入榜→NEW |
| 9c.8 | 滚动 Peak/Wks/Pk Wks | 截至所选周的累计统计（`running_peak = rank.min()`, `running_pk_wks = weeks_at_running_peak`） |

### 9d. Tab 2: 每周榜首 (`number_ones.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9d.1 | 3 子 Tab | 每周 #1 榜单 / #1 周数排行 / 年度统计 |
| 9d.2 | 每周 #1 表格 | 每行的三榜 #1（单曲/专辑/艺人） |
| 9d.3 | #1 周数排行 | 曲目/专辑/艺人按冠军周数排名 |
| 9d.4 | 排名柱状图 | YlOrRd 色阶水平柱状图 |
| 9d.5 | 年度独特 #1 统计 | 每年有多少不同的 #1 曲目/专辑/艺人 |
| 9d.6 | 空降冠军 | 首次入榜即 #1 的记录（first appearance rank==1） |
| 9d.7 | 最长连续冠军算法 | `_longest_streak()`: 遍历排序周列表，`if (weeks[i] - weeks[i-1]).days == 7` 则继续 streak，否则重置 |

### 9e. Tab 3: 单曲历史 (`track_history.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9e.1 | 搜索过滤 | 文本输入框筛选曲目 |
| 9e.2 | 曲目选择器 | 单选列表选择具体曲目 |
| 9e.3 | 8 指标卡片 | Power Score、入榜峰值、在榜周数、冠军周数、Top 5 周数、总上榜播放、走势总榜排名 |
| 9e.4 | 历史排名表 | 含 Change 列：NEW（首次）/ RE（断档 >8 天回榜）/ ▲n（上升）/ ▼n（下降）/ ─（持平） |
| 9e.5 | 排名趋势图 | 折线图，断档 >9 天处插入 None 造成断线；含 Top N 边界线 + 峰值参考线 |
| 9e.6 | Y 轴翻转 | 排名1在顶部 |

### 算法
- **连续在榜判断**: 相邻两周间隔 ≤ 8 天为连续，> 8 天为断档（RE）
- **升降计算**: 仅在连续两周之间计算（断档后不计算升降，标记 RE）
- **None 插入**: gap > 9 天时在图中插入 None 断线

### 9f. Tab 4: 艺人榜单 (`artist_chart.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9f.1 | 3 子 Tab | 榜单表现 / 周榜历史 / 曲目表现 |
| 9f.2 | 榜单表现 | 艺人总览：入榜峰值、在榜周数、首次/最后入榜、#1 周数、走势点数/排名 |
| 9f.3 | 周榜历史 | 排名表含 Change 列（NEW/RE/▲/▼/─）+ 当周 #1 曲目/专辑链接 |
| 9f.4 | 排名趋势图 | 含最佳单曲排名叠加线（绿色虚线） |
| 9f.5 | 曲目表现 | 该艺人所有入榜曲目排序，含 tiebreaker 选择器（在榜周数/峰值周数） |
| 9f.6 | 专辑表现 | 该艺人所有入榜专辑全表 |

### 9g. Tab 5: 专辑榜单 (`album_chart.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9g.1 | 2 子 Tab | 榜单表现 / 曲目表现 |
| 9g.2 | 榜单表现 | 专辑总览 + 周榜历史表（含 Change 列） |
| 9g.3 | 排名趋势图 | 含最佳单曲排名叠加线 |
| 9g.4 | 曲目表现 | 专辑内曲目的 Billboard 表现 + Power Score 整合 |
| 9g.5 | 版本合并支持 | release group 归一化 |

### 9h. Tab 6: 走势总榜 (`power_score.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9h.1 | 3 子 Tab | 歌曲 / 专辑 / 艺人走势总榜 |
| 9h.2 | KPI 汇总卡片 | 总榜曲目数/专辑数/艺人数、最高分、平均分 |
| 9h.3 | 完整排名表 | 排序的走势点数排名表 |
| 9h.4 | Top 20 柱状图 | 含透明度渐变效果 |
| 9h.5 | 方法论展开 | 可展开的算法说明文档 |

### 9i. Tab 7: 歌曲总榜 (`all_time_tracks.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9i.1 | 在榜周数排行 | 按在榜周数排序 |
| 9i.2 | 入榜峰值排行 | 按峰值排名排序（含 tiebreaker） |
| 9i.3 | 单周最高播放 | Top 100 单周播放次数排行 |

### 9j. Tab 8: 艺人总榜 (`all_time_artists.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9j.1 | 6 个排行指标 | 在榜周数/入榜峰值/冠军周数/Top 5 周数/入榜曲目数/冠单数量 |
| 9j.2 | Top 100 表 | 完整排行表 |
| 9j.3 | Top 20 柱状图 | 水平柱状图 |

### 9k. Tab 9: 专辑总榜 (`all_time_albums.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9k.1 | 7 个排行指标 | 在榜周数/入榜峰值/冠军周数/入榜曲目数/冠单数量/单曲冠军周数/走势点数 |
| 9k.2 | Top 100 表 | 完整排行表 |
| 9k.3 | Top 20 柱状图 | 水平柱状图 |

### 9l. Tab 10: 榜单记录 (`records.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9l.1 | 高亮里程碑卡片 | 4个关键里程碑卡片 |
| 9l.2 | 艺人统治力 | 最多 #1 艺人、连续冠军、统治周数 |
| 9l.3 | #1 里程碑 | 最多 #1 艺人、空降冠军、回冠记录 |
| 9l.4 | 持久力记录 | 最长在榜、无 Top 10 最长在榜、最长连续在榜 streak |
| 9l.5 | 排名跳跃 | 最大升幅（相邻周排名上升最大）/ 最大降幅 |
| 9l.6 | 专辑统治力 | 专辑 #1 记录 |
| 9l.7 | 综合最强 | 走势点数最高 + 年终 #1 |
| 9l.8 | 双重首冠 | 歌手+单曲同时首次 #1 |
| 9l.9 | 周大盘排行 | 单周总播放量排行 |
| 9l.10 | 版本合并支持 | 专辑记录考虑 release groups |

### 9m. Tab 11: 对决 (`versus.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9m.1 | 3 子 Tab | 歌曲对决 / 专辑对决 / 艺人对决 |
| 9m.2 | 搜索选择器 | `_search_picker()` 模式：文本输入过滤 → radio 选择 |
| 9m.3 | 双线排名趋势图 | `_rank_chart()`: Plotly 双线折线图，A/B 两色对比 |
| 9m.4 | 2列指标对比 | `_metric_grid()`: 并排 st.metric 对比表 |
| 9m.5 | 实体列表构建 | `_build_entity_list()`: 排序去重列表 |
| 9m.6 | 走势点数查询 | `_ps_rank()`: 查走势点数和总排名 |
| 9m.7 | 专辑对决含曲目统计 | 通过 `_resolve_album_members()` 统计专辑内曲目表现 |
| 9m.8 | 艺人对决含专辑统计 | 艺人级别含专辑数、冠专数量、专辑走势点数汇总 |

### 9n. Tab 12: 发行周期 (`release_cycle/`)

#### 主路由 (`__init__.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9n.1 | 艺人搜索 | 文本输入框 + selectbox 选择艺人 |
| 9n.2 | 视图路由 | `rc_view` session_state: artist / album / compare |
| 9n.3 | 艺人切换检测 | 切换艺人时重置视图到总览 |
| 9n.4 | Compare 队列 | `rc_compare_queue` 管理对比队列 |

#### 公共引擎 (`shared.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9n.5 | `load_artist_releases()` | 链式 JOIN: artists→albums→track_albums→tracks→spotify_track_meta→spotify_album_meta |
| 9n.6 | `_verify_album_artists()` | DB 检查 → 批量 Spotify API（20 个/次） |
| 9n.7 | `_fetch_album_artists_from_api()` | Spotify `/v1/albums?ids=` 端点的 artists 字段 |
| 9n.8 | `_filter_release_group_duplicates()` | release groups canonical 映射 + spotify_album_id 去重 |
| 9n.9 | `_ad_hoc_name_grouping()` | `normalize_album_name()` 回退合并（去括号、去版本后缀） |
| 9n.10 | `get_advance_singles()` | 三级查找：DB album_artists → Spotify API → earliest_play_date 启发式 |
| 9n.11 | `compute_release_cycle()` | 精确 7 天窗口聚合：`(ts_date_dt - release_date).dt.days // 7` |
| 9n.12 | `_compute_artist_impact()` | 0.35×volume + 0.35×growth + 0.30×attribution（含清洗基线窗口） |
| 9n.13 | `_compute_market_impact()` | 0.30×market_share + 0.30×volume + 0.40×market_shift |
| 9n.14 | `compute_release_metrics()` | debut_rank, peak_rank, weeks_to_peak, weeks_on_chart, artist_impact, market_impact, half_life（跌至峰值 50% 所需周数） |
| 9n.15 | `detect_catalog_reentries()` | 发行后老歌回榜检测（发行前不活跃、发行后出现） |
| 9n.16 | `_get_spotify_token()` | OAuth client_credentials, TTL ~58 分钟缓存 |
| 9n.17 | `_spotify_search_album()` | DB 先查 → Search API 回退 |
| 9n.18 | 格式化函数 | impact 显示文本（negligible/低/中/高/非常高） |

#### 艺人总览视图 (`artist_view.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9n.19 | KPI 卡片 | 总发行数、影响力总值、平均峰值、最佳发行等 |
| 9n.20 | 排名趋势图 | 时间轴 + 发行事件标记竖线 |
| 9n.21 | 发行卡片流 | 每张发行的卡片：封面、名称、类型、发行日期、影响力指标 |
| 9n.22 | 对比入口 | 选择发行加入对比队列 |

#### 专辑下钻视图 (`album_view.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9n.23 | 周期曲线 | 折线图仅连续周连线（断档处断开） |
| 9n.24 | 先行曲叠加 | 先行曲的单曲榜排名线叠加 |
| 9n.25 | 最佳单曲叠加 | 表现最好的单曲排名线叠加 |
| 9n.26 | 歌曲入榜矩阵 | 热力图/矩阵显示每首歌每周是否在榜 |
| 9n.27 | 老歌回榜 | 发行后重新入榜的老曲目列表 |
| 9n.28 | 加曲来源 | 豪华版/改版新增曲目来源标注 |

#### 多发行对比视图 (`compare_view.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 9n.29 | 叠加排名曲线 | 多条发行周期排名线叠加对比 |
| 9n.30 | 叠加播放量曲线 | 多条发行周期播放量线叠加对比 |
| 9n.31 | 指标对比表 | 多发行的 debut/peak/weeks/impact/half_life 对比 |

---

## 10. 账号中心

### 10a. 音乐库 (`app/pages/11_library.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10a.1 | 3 Tab | 收藏概览 / 播放列表分析 / 被遗忘的宝藏 |
| 10a.2 | 收藏覆盖率 | 有播放记录的收藏曲目占比 |
| 10a.3 | 艺人收藏 vs 实际 | 双柱对比图：收藏艺人数 vs 实际收听艺人数 |
| 10a.4 | 播放列表大小直方图 | 播放列表曲目数分布 |
| 10a.5 | 全部播放列表表 | 所有播放列表的详细信息 |
| 10a.6 | 播放列表下钻 | 选择播放列表显示内部曲目 |
| 10a.7 | Top 10 播放列表重叠矩阵 | 热力图显示最大的10个播放列表之间的曲目重叠 |
| 10a.8 | 被遗忘的宝藏 | 收藏但从未播放 或 超过6个月未播放的曲目 |

### 交叉查询算法
- `saved_tracks.track_uri` → 提取 Spotify ID → `tracks` 表匹配 → LEFT JOIN `plays`

### 10b. 搜索编年史 (`app/pages/12_search.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10b.1 | 3 Tab | 搜索趋势 / 热搜排行 / 搜索意图 |
| 10b.2 | 搜索趋势折线图 | 每日搜索次数折线图 |
| 10b.3 | DOW×Hour 热力图 | 搜索的星期×小时分布 |
| 10b.4 | 热搜排行 | Top 30 搜索词水平柱状图 |
| 10b.5 | 搜索意图分类 | `classify_intent()` 算法 + 饼图 + 各类别 Top 5 示例 |

### 搜索意图分类算法
- 精确匹配艺人名 → "艺人查找"
- 精确匹配曲目名 → "歌曲搜索"
- 关键词匹配（billboard/hot100/排行/top/排行榜/歌单/playlist）→ "排行榜/歌单"
- 其余 → "未分类"

### 10c. 音乐画像 (`app/pages/13_insights.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10c.1 | 粉丝层级分析 | `classify_tier()`: rank 0-4→super, 5-14→regular, 15+→casual |
| 10c.2 | 层级分布 | 环形图 + 柱状图 |
| 10c.3 | 超级粉丝卡片 | 每位超级粉丝的艺人卡片 |
| 10c.4 | 常规粉丝柱状图 | 水平柱状图 |
| 10c.5 | Marquee 推广 | impressions JOIN plays（artist_name→tracks 链） |
| 10c.6 | 转化率 KPI | 有转化的展示占比 |
| 10c.7 | 推广艺人×层级图 | 按粉丝层级分色的柱状图 |
| 10c.8 | 完整详情表 | 含转化状态的完整推广详情 |

### 粉丝层级算法
- `classify_tier(rank)`: 按该艺人在用户播放次数排名中分类
  - rank 0-4 → "super"（超级粉丝）
  - rank 5-14 → "regular"（常规粉丝）
  - rank 15+ → "casual"（路人粉）

### 10d. 播客专区 (`app/pages/14_podcast.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10d.1 | 2 Tab | 总览 / 互动 |
| 10d.2 | 播客 KPIs | 播放次数/小时/独特节目/收藏节目数 |
| 10d.3 | Top 15 节目柱状图 | 水平柱状图 |
| 10d.4 | 月度趋势 | 折线图 |
| 10d.5 | 收藏节目表 | 所有收藏节目的详细信息 |
| 10d.6 | 互动展示 | 评论/评分/投票，含 JSON 内容解析 |

### 10e. 视频分析 (`app/pages/15_video.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10e.1 | 特殊过滤 | `ms_played >= 30000`（排除滑动自动预览噪音，~87%视频<5s） |
| 10e.2 | 视频 KPIs | 视频播放次数/小时/音乐视频数/音频对比 |
| 10e.3 | 2 Tab | 趋势对比 / 视频排行 |
| 10e.4 | 音频 vs 视频年度对比 | 分组柱状图 |
| 10e.5 | 平台饼图 | 视频播放平台分布 |
| 10e.6 | 平均播放秒数 | 视频平均播放时长 |
| 10e.7 | Top 30 音乐视频 | 视频 vs 音频播放对比柱状图 |
| 10e.8 | 最近 20 条视频 | 视频播放记录表格 |

### SQL 算法
- `SUM(CASE content_type='video' AND ms_played>=30000)` vs `SUM(CASE content_type='audio')`
- 视频类专门过滤以区分音乐视频和短视频/其他视频内容

### 10f. 个人档案 (`app/pages/16_profile.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 10f.1 | 身份卡片 | display_name、头像 120px、国家、生日、性别 |
| 10f.2 | 账户 KPIs | 总播放、首次播放日期、关注数/粉丝数 |
| 10f.3 | 里程碑时间线 | 首次播放、收听年龄、订阅、地址 |
| 10f.4 | 社交网络 | 关注列表、粉丝列表 |
| 10f.5 | 趣味角落 | 黑名单、AI 提示词、Wrapped Club |

---

## 11. 设置 (`app/pages/09_settings.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 11.1 | 最短播放时长 | `min_ms` 滑块（默认 30s），过滤过短播放 |
| 11.2 | 仅音乐 | `music_only` 开关，排除播客/有声书 |
| 11.3 | 合并连续播放 | `merge_enabled` 开关（默认开启），先合并再过滤 |
| 11.4 | Billboard Top N | 三个独立参数：单曲 `bb_top_n` / 专辑 `bb_album_top_n` / 艺人 `bb_artist_top_n` |
| 11.5 | 统计周边界 | `bb_week_start_dow`（周几开始）+ `bb_week_start_hour`（几点开始） |
| 11.6 | 版本合并管理 | 自动检测 + 手动创建 + 已保存组管理 |
| 11.7 | 数据导入 | 触发 `import_data()` |
| 11.8 | 参数变更自动刷新 | 任何参数变更 → `st.cache_data.clear()` + `st.rerun()` |

---

## 12. 版本合并引擎 (`app/version_merge.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 12.1 | `detect_release_groups()` | Phase 1: 曲目重叠率（同名专辑不同版本判定）；Phase 2: 名称归一化（去括号/去版本后缀） |
| 12.2 | `apply_detected_groups()` | 应用检测到的合并组 |
| 12.3 | `create_group()` | 手动创建 release group |
| 12.4 | `delete_group()` | 删除 release group |
| 12.5 | `update_group_members()` | 更新组成员 |
| 12.6 | `get_album_track_comparison()` | 对比两版本曲目差异（共享/独有/加曲） |

---

## 13. 数据导入 (`app/import_data.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 13.1 | 逐文件读取 JSON | 遍历 streaming 目录 |
| 13.2 | UTC→本地时间 | 固定北京时间 UTC+8 |
| 13.3 | 平台归一化 | `iOS 15.5 (iPhone14,5)` → `ios` |
| 13.4 | 维度表 upsert | artist/album/track 的 INSERT OR IGNORE + 重复版本合并 |
| 13.5 | track_albums 关联 | 曲目-专辑多对多关系 |
| 13.6 | 5000 行批量插入 | 事实表批量写入 |

---

## 14. 账号数据导入 (`app/import_account_data.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 14.1 | 搜索历史 | `search_queries` 表 |
| 14.2 | 收藏 | `saved_tracks` / `saved_albums` / `saved_artists` |
| 14.3 | 播客 | `podcast_plays` / `podcast_interactions` / `saved_shows` |
| 14.4 | 播放列表 | `playlists` / `playlist_tracks` |
| 14.5 | 社交 | `user_follows` |
| 14.6 | 个人资料 | `user_profile` |
| 14.7 | Marquee | `marquee_impressions` |
| 14.8 | Wrapped | 各种 `wrapped_*` 表 |
| 14.9 | 黑名单 | `banned_items` |

---

## 15. 数据库层 (`app/db.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 15.1 | `get_db()` | 获取连接（默认只读，WAL 模式） |
| 15.2 | `base_filters()` | 标准 WHERE 条件（min_ms + music_only），唯一过滤入口 |
| 15.3 | `load_plays()` | 4 表 JOIN + 过滤，统一数据加载入口 |
| 15.4 | `merge_consecutive_plays()` | 合并连续同曲目播放为逻辑播放次数 |
| 15.5 | `ensure_schema()` | 增量升级 schema（新增表/索引/列安全重复执行） |
| 15.6 | `build_aggregations()` | 预聚合表构建 |

---

## 16. 工具函数 (`app/utils.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 16.1 | `convert_to_local_time()` | 固定北京时间 UTC+8，忽略 Spotify `conn_country` 字段 |
| 16.2 | `classify_platform()` | 平台字符串归一化 |

---

## 17. 样式系统 (`app/styles.py`)

### 功能清单
| # | 功能 | 描述 |
|---|------|------|
| 17.1 | CSS 变量系统 | `--gold`, `--bg-page`, `--bg-card` 等暖色主题变量 |
| 17.2 | 噪点纹理背景 | CSS 伪元素噪点覆盖层 |
| 17.3 | 卡片金左边线 | 卡片左侧金色装饰线 |
| 17.4 | 衬线字体 | Palatino/Book Antiqua 衬线字体 |
| 17.5 | 表头暖金底色 | 表格表头暖金色背景 |
| 17.6 | 侧边栏牛皮纸色 | 侧边栏牛皮纸纹理色调 |
| 17.7 | `page_header()` | 统一页面标题组件 |
| 17.8 | `kpi_row()` | 统一 KPI 行组件 |
| 17.9 | `PLOTLY_TEMPLATE` | 全局 Plotly 图表样式模板 |
| 17.10 | `COLORS` | 暖色色盘常量 |

---

## 18. 导航与页面路由

### 侧边栏结构（6 入口）
```
├── 总览仪表盘 (main.py, default)
├── 播放分析 (02_playback.py)       ← 5 Tab
├── 年度回顾 (03_yearly.py)         ← 2 Tab
├── Billboard 周榜 (08_billboard.py) ← 12 Tab
├── 账号中心 (04_account.py)        ← 6 Tab
└── 设置 (09_settings.py)
```

### 动态加载机制
- 数字前缀文件通过 `importlib.util.spec_from_file_location()` 加载
- `st.navigation` + `st.Page` 定义导航
- 文件名英文，侧边栏中文标签
