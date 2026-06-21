# Spotify Stats 增强与优化 — 设计文档

日期: 2026-05-16 | 状态: 待实施

---

## 概述

对 Spotify Extended Streaming History 分析应用进行功能扩展和优化。分为三个梯队逐步实施，涵盖新统计功能、社交分享、性能优化和代码重构。

---

## 第一梯队：高价值 + 低实现成本

### 1. 公共数据加载层

**问题**: 7 个页面各自手写相同的 4 表 JOIN 查询和 `base_filters()` 样板代码，`db.query_plays()` 已有但未被使用。

**方案**: 在 `app/db.py` 新增 `load_plays()` 统一入口函数：

```python
def load_plays(conn, columns="*", extra_where="", extra_params=None,
               min_ms=30000, exclude_skipped=True, music_only=True,
               join_albums=True):
```

- 内部调用 `base_filters()` + 标准 JOIN
- `columns` 参数允许按需选择字段（子集或 `*`）
- `join_albums=False` 可跳过 albums JOIN — 时间报告、时段分析等页面不需要专辑信息，减少 JOIN 开销
- `extra_where`/`extra_params` 支持页面级附加过滤
- 返回 `pd.DataFrame`

**影响文件**: `app/db.py`（新增函数，内部调用 `db.query_plays()` 或重写之）, `app/main.py`, `app/pages/02_timeline.py`, `03_leaderboard.py`, `04_behavior.py`, `05_wrapped.py`, `06_artist_deep.py`, `07_listening_hours.py`, `08_billboard.py`（替换重复代码）

**注意事项**: `db.query_plays()` 当前未被任何页面使用，需验证其逻辑正确性后复用；如不可用则重写

### 2. Billboard 模块拆分

**问题**: `08_billboard.py` 为 96KB 单文件，含 10 个子 Tab，难以维护。

**方案**: 拆分为 `app/pages/billboard/` 包：

```
app/pages/billboard/
├── __init__.py          # 入口页面 + 侧边栏 + Tab 路由 + st.session_state 初始化
├── shared.py            # 共享函数: load_billboard_raw(), load_track_album_map(),
│                        #   compute_power_scores(), compute_records()
├── weekly.py            # Tab 1: 周榜 (排名表格 + Top 10 奖牌卡片)
├── number_ones.py       # Tab 2: 冠单历史 (冠单周数排行、年度冠单、空冠、榜单大盘)
├── track_history.py     # Tab 3: 单曲历史 (summary metric + 排名趋势图)
├── artist_chart.py      # Tab 4: 艺人榜单 (metric + 入榜曲目表 + Peak 对比)
├── album_chart.py       # Tab 5: 专辑榜单 (同艺人结构)
├── all_time.py          # Tab 6-8: 歌曲/艺人/专辑总榜
├── power_score.py       # Power Tab: 歌曲走势总榜 (Power Score)
└── records.py           # Records Tab: 榜单记录 (12 类记录)
```

**约束**: 拆分过程保持功能完全不变，仅移动代码。

**关键风险 — Streamlit 页面发现机制**: Streamlit 只自动发现 `pages/` 下的 `.py` 文件，不会扫描子包。因此 `08_billboard.py` 必须保留作为薄入口（~20行），内部 `from app.pages.billboard import main; main.run()` 委托给包。不能直接删除 `08_billboard.py`。

### 3. 全局搜索

**功能**: 侧边栏顶部搜索框，输入 ≥2 字符触发模糊搜索。

**数据流**:
```
st.text_input → search_music(query) → LIKE %query% 在 artists/tracks/albums
→ Top 10 结果 (按播放次数排序) → 点击 → st.switch_page() 跳转
```

**实现**:
- `app/db.py` 新增 `search_music(conn, query)` — 返回 `{"artists": [...], "tracks": [...], "albums": [...]}`
- `app/styles.py` 新增 `render_search_bar()` — 在侧边栏渲染搜索组件
- 跳转逻辑: 艺人 → `06_artist_deep.py`, 歌曲/专辑 → `08_billboard.py` 单曲历史 Tab

**性能注意**: `track_name` 和 `album_name` 列目前无独立索引。在 ~10万级数据量下 LIKE 查询仍可控，但建议加 `idx_tracks_name ON tracks(track_name)` 和 `idx_albums_name ON albums(album_name)` 为搜索优化。

### 4. 歌曲对决

**功能**: Billboard 新增 Tab「⚔️ 歌曲对决」,选两首歌并排对比。

**对比维度**:
- 榜单走势叠加折线图 (同坐标系，不同颜色)
- 播放时段对比 (两张迷你热力图并排)
- 关键指标对比表: Peak / 在榜周数 / 总播放 / 冠单周数 / 跳过率

**实现**: 复用 `shared.py` 中的 Billboard 数据，纯前端渲染，无需新查询。

### 5. 地理分析 (音乐足迹)

**功能**: 利用 `plays.conn_country` 字段，新增页面 `app/pages/10_geo.py`。

**包含**:
- **世界地图**: Plotly choropleth，按国家着色播放次数
- **各国 Top 艺人/歌曲**: 下拉选择国家，展示该地区排行
- **旅行音乐日志**: 按时间排列国家切换记录

**实现**:
- `app/utils.py` 新增 `COUNTRY_CODE_TO_NAME` 映射表 (ISO 3166-1 alpha-2)
- Plotly `px.choropleth` 原生支持，无需额外依赖
- 按 `conn_country` 分组聚合
- **NULL 处理**: `conn_country` 可能为 NULL 或空字符串（旧数据/离线播放），单独统计为「未知地区」并在页面上标注比例

### 6. 首页「回忆推荐」

**功能**: 总览仪表盘新增一个小模块，每次刷新随机推荐一首历史歌曲。

**展示**: 卡片形式展示歌曲名、艺人、专辑、上次播放日期、总播放次数，带「去 Billboard 看看」跳转链接。

**实现**: 简单 SQL — `SELECT ... FROM plays ... ORDER BY RANDOM() LIMIT 1`，几乎零成本。

### 7. 数据导出

**功能**: 排行榜和 Billboard 页面增加「导出 CSV」按钮。

**实现**: `st.download_button` + `df.to_csv(index=False)`，Streamlit 原生支持。

### 8. Billboard 配置持久化

**问题**: `bb_top_n`、`bb_week_start_dow`、`bb_week_start_hour` 存在 `st.session_state`，应用重启后恢复默认值，用户需重新设置。

**方案**: 利用 Streamlit 的 `st.query_params` 将配置持久化到 URL 参数中。页面加载时从 URL 读取，无 URL 参数时回退 session_state 默认值。

**实现**: 在 `09_settings.py` 配置变更时同步写入 `st.query_params`；在 `08_billboard.py` 入口处从 `st.query_params` 恢复配置。

### 9. 数据库预聚合表

**问题**: Billboard 每次加载在 pandas 中实时分组计算周榜排名。

**方案**: 在数据导入完成后自动写预聚合表：

```sql
CREATE TABLE agg_weekly_tracks (
    billboard_week TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, track_id)
);
```

- 在 `import_data.py` 导入完成后触发聚合写入
- `load_billboard_raw()` 优先查此表，检查与当前过滤参数是否匹配，不匹配或不存在时回退实时计算
- 设置页「重新导入」时自动重建
- **staleness 处理**: 聚合表存储时记录 `min_ms`/`exclude_skipped`/`music_only` 参数哈希，查询时对比当前参数，不匹配则走实时路径。避免参数变更后返回过期数据。

---

## 第二梯队：高价值 + 中等成本

### 10. 分享卡片生成器

**功能**: Wrapped 和 Billboard 页面增加「生成分享卡片」按钮。

**模板**: 三套 Vinyl Archive 风格卡片:
1. 黑胶唱片 — 圆形封面 + 统计铭文
2. 榜单海报 — 竖版 Top 5 排名
3. 极简统计 — 大字数据 + 金线分隔

**实现**: 纯 Python/Pillow 渲染，预设计模板 + 动态填充数据。输出 PNG 下载。

**新增文件**: `app/share_card.py` — 卡片渲染模块

**潜在风险 — 中文字体**: Pillow 默认不含中文字体。macOS 可用系统字体 (`/System/Library/Fonts/PingFang.ttc` 或 `/System/Library/Fonts/STHeiti Light.ttc`)，Linux/Windows 需额外处理。建议:
1. 优先尝试加载系统字体
2. 回退时使用 Pillow 默认字体（仅英文数字），中文用拼音替代
3. 或在项目中 bundle 一个开源中文字体（如 Noto Sans SC）

### 11. Spotify API 集成

**功能**: 通过 Spotify Web API 获取元数据丰富分析维度。

**新增数据**:
- 专辑封面 URL → 排行榜/艺人页展示缩略图
- 音频特征: danceability / energy / valence / tempo / acousticness
- 艺人 genre → 曲风分布分析

**实现**:
- 依赖 `spotipy` 库
- 设置页新增 Spotify API 配置区 (Client ID / Secret)
- 所有 API 结果用 `@st.cache_data(ttl=86400)` 长期缓存

**新增/影响文件**: `app/spotify_api.py`, `09_settings.py`, 多个展示页面

### 12. Wrapped 增强

**功能**: 在现有 `05_wrapped.py` 增加三个新视图:

1. **年际对比**: 选两年并排展示所有指标对比
2. **冷门宝藏**: `GROUP BY track_id` 中全局播放占比低但个人播放次数高的歌曲
3. **时间胶囊**: 选某年某月，生成迷你月度报告

**实现**: 全在 `05_wrapped.py` 内扩展，复用现有数据加载。

---

## 第三梯队：高成本或需外部依赖

### 13. 榜单时间线动画

**功能**: Billboard 增加动画模式，选定时间范围后自动播放每周 Top 10 排名变化。

**技术**: 需 Plotly 动画帧 或 JS 前端动画。Streamlit 内实现复杂，考虑独立 HTML 页面嵌入。

### 14. 月度 Digest

**功能**: 每月自动生成音乐月报。需要定时触发机制或手动触发。

### 15. 移动端适配

**功能**: 响应式优化。Streamlit 原生移动支持有限，主要在 CSS 层面优化。

---

## 优化清单 (贯穿所有梯队)

| 项目 | 说明 | 梯队 |
|---|---|---|
| 统一数据加载 | `load_plays()` 替换 7 处重复 JOIN，支持 `join_albums` 按需开关 | 1 |
| Billboard 拆分 | 96KB → 10 个模块 + `08_billboard.py` 薄入口 | 1 |
| 预聚合表 | `agg_weekly_tracks` 减少实时分组，含参数哈希防 staleness | 1 |
| 复合索引 | `plays(ts_year, skipped, track_id, ms_played)` 覆盖过滤+排序 | 1 |
| 搜索索引 | `tracks(track_name)`, `albums(album_name)` 加速 LIKE 查询 | 1 |
| Billboard 配置持久化 | `bb_top_n`/`bb_week_start_*` 存到 `st.query_params` 或 settings 表，重启不丢失 | 2 |
| 加载骨架屏 | 数据加载时显示占位骨架 | 2 |
| 错误边界 | 各页面 try/except 友好报错 | 2 |
| `db.query_plays()` 清理 | 如可用则复用，否则移除减少混淆 | 1 |
| 数据导入进度条 | `import_data.py` 增加 `st.progress` 显示导入进度 | 2 |

---

## 验证方式

1. 启动应用: `streamlit run app/main.py`
2. 检查所有现有页面功能是否保持正常（拆分和重构不能引入回归）
3. 逐项验证第一梯队 (9项): 搜索 → 歌曲对决 → 地理分析 → 回忆推荐 → 数据导出 → 预聚合表 → 配置持久化 → 公共数据层 → Billboard 拆分
4. 验证预聚合表 staleness 检测：修改过滤参数后确认数据刷新
5. 验证 Billboard 配置持久化：设置非默认值 → 重启应用 → 确认配置保留
6. 第二、三梯队按实施进度验证
