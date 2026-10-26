# 旧年度回顾设计与实施提纲

2026-10-26按主题合并。历史设计保留决策及合同，实施部分只保留目标、分工和验收要求；旧操作步骤不作为当前任务，计划中的Expected不等于实际通过。

## 阅读顺序

- [年度回顾页面重设计 Spec](#年度回顾页面重设计-spec)
- [年度回顾页面迁移 Implementation Plan](#年度回顾页面迁移-implementation-plan)

## 年度回顾页面重设计 Spec

原记录：`2026-05-29-spec.md`。

### 概述

将 Streamlit 的年度回顾功能迁移到 React 前端，设计一个混合视觉风格的年度听歌报告页面。包含两个 Tab：「年度总结」（基于播放数据计算）和「官方 Wrapped」（基于 Spotify 导入的 Wrapped 数据）。

**视觉策略：混合模式** — 顶部关键数据用大视觉卡片（故事感），下方详细数据用 GlassCard 仪表盘布局。

**交互策略：趣味互动版** — 年份切换 + 详情跳转 + 听歌人格动画揭示 + 分享长图。

---

### 页面结构

```
/yearly-review
├── YearlyReviewPage（页面框架 + 年份选择器 + Tab 导航）
│   ├── Tab 1: 年度总结（CustomSummary）
│   └── Tab 2: 官方 Wrapped（OfficialWrapped）
```

**路由：** `/yearly-review`（默认展示最近一个有数据的年份）

---

### Tab 1: 年度总结 — 12 个内容模块

#### 1. Hero 封面区

全宽大视觉卡片，年分数大字 + 渐变背景色（根据主人格主题色），左对齐排列。

数据点：年度总时长（小时）、总播放量、独特曲目数、独特艺人数、听歌天数、日均时长。

视觉：Playfair Display 衬线标题大字（6xl+），Inter 正文，数字 tabular-nums。

#### 2. 听歌人格（动画揭示）

**7 维雷达图：**

| 维度 | 计算口径 | 归一化 |
|---|---|---|
| 探索者 | 独特曲目 / 总播放 × 100 | 上限 40 得 100 分 |
| 专一者 | Top 1 艺人播放占比 × 100 | 上限 20% 得 100 分 |
| 狂听者 | 日均听歌小时 | 上限 4h 得 100 分 |
| 夜猫子 | 凌晨 0-5 点播放占比 × 100 | 上限 50% 得 100 分 |
| 收藏家 | 听完 ≥70% 曲目的专辑数 / 总专辑数 × 100 | 直接百分比 |
| 新潮派 | 当年发行歌曲播放占比 × 100 | 上限 50% 得 100 分 |
| 地球村 | 非华语艺人播放占比 × 100 | 直接百分比 |

**6 种主人格：**

| 人格 | 触发 | 主题色 | 文案 |
|---|---|---|---|
| 环球旅人 | 高探索 + 高地球村 | 深蓝 | "你的播放列表就是一本没有签证的护照" |
| 深度鉴赏家 | 高专一 + 高收藏家 | 琥珀 | "你不听歌，你研究歌。专辑是你的最小单位" |
| 能量引擎 | 高狂热 + 低夜猫 | 橙红 | "音乐是你的日间燃料，从早燃到晚" |
| 午夜诗人 | 高夜猫 + 高探索 | 靛紫 | "凌晨两点，你和耳机里的世界清醒着" |
| 潮流捕手 | 高新潮 + 高探索 | 青绿 | "新歌上线，你是朋友圈第一个听到的人" |
| 忠实灯塔 | 高专一 + 低探索 | 暖金 | "你知道自己要什么，一首歌可以循环一整年" |

**动画流程：** 雷达图逐维展开（每维 ~300ms 延迟），全部展开后弹出主人格大字 + 文案，scale-in + fade-in 过渡。

**替换规则：** 如果多个维度最高分相等，按优先级 探索者 > 狂听者 > 夜猫子 > 新潮派 > 收藏家 > 地球村 > 专一者 选择主人格。

#### 3. Top 榜单

三列布局（桌面端）/ 单列堆叠（移动端）：

- **Top 5 艺人** — 排名编号、封面图（圆形）、艺人名（可点击跳转 `/music/artists/:name`）、播放量、小时数
- **Top 5 曲目** — 排名编号、封面图（方形）、曲目名（可点击跳转 `/music/tracks/:id`）、艺人名、播放量
- **Top 5 专辑** — 排名编号、封面图（方形）、专辑名（可点击跳转 `/music/albums/:name`）、艺人名、时长

封面图规则：优先 `cover_url` 字段，回退到默认占位图。

#### 4. 曲风/流派全景

- **Top 5 流派** — 横向柱状图，流派名 + 播放占比
- **流派进化时间线** — 月度堆叠面积图，展示流派偏好随季节漂移
- **语言分布** — 环形图，分段：中文 / 英文 / 韩文 / 日文 / 纯器乐 / 其他

数据来源：艺人流派信息从 `spotify_artist_meta.genres` 获取，无流派数据时展示"流派数据不足"提示。

#### 5. 时间故事

- **听歌日历** — 年度热力图，12 行（月）× ~30 列（日），颜色深浅表示该日播放量
- **月度脉搏** — 12 个月柱状图，高亮标注最高月和最低月
- **听歌高峰时段** — 24 小时折线/面积图，白天/夜晚双色填充
- **深夜听歌画像** — 凌晨 0-5 点占比 + 深夜最爱曲目 Top 3（含封面）

#### 6. 音乐版图

- **地区分布** — 国旗网格或横向堆叠条，展示艺人国籍/地区播放占比
- **Top 海外艺人** — 封面 + 名称 + 国籍标签

地区判定规则：根据 Spotify 流派推断（K-pop → 韩国、J-pop → 日本、Mandopop → 中国等），无法判定标记"未知"。映射表内置在前端。

#### 7. 发现与回归

- **年度新发现艺人** — 今年第一次播放的艺人中，播放量 Top 3 + 封面 + 发现日期
- **老歌回归** — 发行超过 5 年、今年高频播放歌曲 Top 5 + 封面 + 发行年份
- **最长情单曲** — 单曲最长连续播放跨度（天）+ 曲目 + 封面

#### 8. 收听深度

- **收听年龄** — 最爱歌曲平均发行年份 → "音乐年龄" + 趣味文案
- **专辑完整度** — 听完 ≥70% 曲目的专辑 Top 3 + 封面 + 完成度进度条
- **深度聆听率** — 单曲播放 ≥90% 时长的比例 + 文案解读

#### 9. 特殊时刻

- **年度听歌最多的一天** — 日期 + 播放量 + 当天高频曲目 + 封面
- **年度最早听歌** — 凌晨 X 点 + 曲目 + 封面
- **年度最晚听歌** — 凌晨 X 点 + 曲目 + 封面
- **最长连续听歌天数** — 不间断播放最大天数 + 起止日期

#### 10. 月度下钻

12 张月度卡片流（按月展开/折叠）：

每张卡片：月份标签、Top 3 曲目（含封面）、Top 1 艺人、月度总时长。默认折叠，点击展开。

#### 11. 对比视图

- **今年 vs 去年** — 4 个 KPI 对比卡片，显示 ↑↓ 箭头和百分比变化
- **年度 Top 5 vs 历史总榜** — 标记 ✨ NEW（首次入榜）/ 📀 经典（历史也在 Top 10）

如无去年数据或历史数据不足，显示友好提示。

#### 12. 分享

浮动按钮「生成长图」。点击后使用 `html-to-image` 截取当前视图为长图，弹出预览弹窗供保存/复制。

注意：ECharts 雷达图需要先渲染为 Canvas 才能被 `html-to-image` 捕获，可能需要设置 `useDMA: true`。

---

### Tab 2: 官方 Wrapped

数据来源：`/api/wrapped-hub`（Spotify Wrapped 导入数据）

**Hero KPI：** 收听总时长、独特艺人/曲目数、连续听歌天数

**俱乐部信息：** 俱乐部名称 + 百分位排名 + 角色标签（Leader/Scout/Archivist/Curator/Collector/Recruiter/Loyalist/Supporter/Broadcaster/Specialist）

**艺人竞速图：** 5 位艺人逐月排名变化折线图

**收听性格雷达：** Party 指标可视化（快乐/喜爱/派对/夜间/露骨曲目占比等）

**收听年龄：** 品味跨度年数 + 起始年份 + 年代阶段

**存档报告：** 特殊日子卡片（最大流派日/最大艺人日/播客日/最活跃日）

**官方排行榜：** 三列布局 — Top 5 曲目/艺人/专辑（含封面）

**年份切换器：** 多年官方数据时支持切换

**空状态：** 无数据时引导文案 → "尚未导入 Spotify 官方 Wrapped 数据。前往 设置 > 数据导入 导入你的 Wrapped 数据。"

---

### 后端需求

#### 现有端点

- `GET /api/wrapped/{year}` — 现有自定义 Wrapped（hero、top 5、3 维人格、季节、月度脉搏、平台、高峰时段、首末曲目）
- `GET /api/wrapped-hub` — 现有官方 Wrapped 2025

#### 新增端点

**`GET /api/wrapped/{year}/full`** — 返回 12 模块完整数据的一次性请求。同时保留旧端点兼容。

**新增计算内容：**

| 模块 | 计算内容 | 数据来源 |
|---|---|---|
| 人格 3→7 维 | 夜猫子比、专辑完整度、新歌比、多国比 | plays + spotify_*_meta |
| 流派全景 | Top 流派 + 月度流派变化 | spotify_artist_meta.genres |
| 语言分布 | 流派→语言分类 | 前端映射表 |
| 音乐版图 | 流派→地区分布 | 前端映射表 |
| 听歌日历 | 每日播放量矩阵 365×1 | plays |
| 发现与回归 | 新艺人、老歌回归、最长情 | plays（跨年查询） |
| 收听深度 | 收听年龄、专辑完整度、深度聆听 | plays + spotify_album_meta |
| 特殊时刻 | 最活跃日、最早/最晚听歌、最长连续 | plays |
| 月度下钻 | 每月 Top 3 曲目 + Top 1 艺人 | plays |
| 年度对比 | 今年 vs 去年 + Top 5 标记 | plays（跨年） |

#### 响应模型

新建 `backend/models/wrapped.py`，定义 `WrappedFullResponse` Pydantic 模型。

#### 服务层

在 `backend/services/` 中新建 `wrapped_service.py`，实现 `get_wrapped_full(year, filters)`。

---

### 前端架构

#### 目录结构

```
frontend/src/
├── pages/
│   └── YearlyReviewPage.tsx              ← 页面入口
├── pages/yearly-review/
│   ├── CustomSummary.tsx                 ← Tab 1 主组件
│   ├── OfficialWrapped.tsx               ← Tab 2 主组件
│   ├── HeroSection.tsx                   ← ① Hero 封面
│   ├── PersonalityReveal.tsx             ← ② 听歌人格
│   ├── TopCharts.tsx                     ← ③ Top 榜单
│   ├── GenrePanorama.tsx                 ← ④ 曲风全景
│   ├── TimeStory.tsx                     ← ⑤ 时间故事
│   ├── MusicMap.tsx                      ← ⑥ 音乐版图
│   ├── DiscoveryReturns.tsx              ← ⑦ 发现回归
│   ├── ListeningDepth.tsx                ← ⑧ 收听深度
│   ├── SpecialMoments.tsx                ← ⑨ 特殊时刻
│   ├── MonthlyDrilldown.tsx              ← ⑩ 月度下钻
│   ├── YearComparison.tsx                ← ⑪ 年度对比
│   └── ShareButton.tsx                   ← ⑫ 分享长图
├── hooks/
│   └── useYearlyReview.ts               ← 数据获取 + 缓存
├── lib/
│   ├── genre-regions.ts                  ← 流派→语言/地区映射表
│   └── personality-themes.ts            ← 6 种人格主题色
└── types/
    └── yearly-review.ts                  ← 类型定义
```

#### 路由与导航

- `/yearly-review` → YearlyReviewPage
- `/yearly-review?year=2024` → 指定年份
- Masthead 导航中添加「年度回顾」入口

#### 数据流

1. 页面挂载 → `useYearlyReview(year)` 请求 `/api/wrapped/{year}/full`
2. 切换年份 → 更新 URL searchParams → 重新请求
3. 切换 Tab → 复用已缓存数据
4. 封面图统一通过 `cover_url` 字段，null 时用占位 SVG

---

### 实现阶段

#### Phase 1: 后端扩展
1. `backend/models/wrapped.py` — 完整 Pydantic 响应模型
2. `backend/services/wrapped_service.py` — `get_wrapped_full()` 计算逻辑
3. `backend/api/wrapped.py` — 新增 `/wrapped/{year}/full` 端点
4. 补充测试用例

#### Phase 2: 自定义年度总结前端
1. 类型 + hook + 工具函数
2. 12 个子组件 + CustomSummary 主组件
3. YearlyReviewPage 入口 + 路由 + 导航

#### Phase 3: 官方 Wrapped Tab
1. OfficialWrapped 组件 + 年份切换 + 空状态

#### Phase 4: 分享
1. ShareButton + 长图生成

## 年度回顾页面迁移 Implementation Plan

原记录：`2026-05-29-plan.md`。

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../../README.md)。

**Goal:** 将 Streamlit 年度回顾功能迁移到 React 前端，包含自定义年度总结（12 模块）和官方 Wrapped 两个 Tab。

**Architecture:** Phase 1 先在 `backend/services/wrapped_service.py` 实现 `get_wrapped_full()` 计算逻辑，通过 `backend/api/wrapped.py` 暴露 `/wrapped/{year}/full` 端点。Phase 2-4 在前端构建 YearlyReviewPage 及 14 个子组件，使用 `useYearlyReview` hook 管理数据获取和缓存。

**Tech Stack:** FastAPI + Pydantic v2 + pandas + React 19 + TypeScript + ECharts + html-to-image

---

#### 新建文件

| 文件 | 职责 |
|---|---|
| `backend/models/wrapped.py` | `WrappedFullResponse` Pydantic 模型定义 |
| `backend/services/wrapped_service.py` | `get_wrapped_full()` 12 模块计算逻辑 |
| `backend/tests/test_wrapped_full.py` | 新端点和服务测试 |
| `frontend/src/types/yearly-review.ts` | 前端类型定义 |
| `frontend/src/hooks/useYearlyReview.ts` | 数据获取 + 缓存 hook |
| `frontend/src/lib/genre-regions.ts` | 流派→语言/地区映射表 |
| `frontend/src/lib/personality-themes.ts` | 6 人格主题色 |
| `frontend/src/pages/YearlyReviewPage.tsx` | 页面入口（Tab + 年份选择） |
| `frontend/src/pages/yearly-review/CustomSummary.tsx` | Tab 1 主组件 |
| `frontend/src/pages/yearly-review/OfficialWrapped.tsx` | Tab 2 主组件 |
| `frontend/src/pages/yearly-review/HeroSection.tsx` | ① Hero 封面 |
| `frontend/src/pages/yearly-review/PersonalityReveal.tsx` | ② 听歌人格 |
| `frontend/src/pages/yearly-review/TopCharts.tsx` | ③ Top 榜单 |
| `frontend/src/pages/yearly-review/GenrePanorama.tsx` | ④ 曲风全景 |
| `frontend/src/pages/yearly-review/TimeStory.tsx` | ⑤ 时间故事 |
| `frontend/src/pages/yearly-review/MusicMap.tsx` | ⑥ 音乐版图 |
| `frontend/src/pages/yearly-review/DiscoveryReturns.tsx` | ⑦ 发现回归 |
| `frontend/src/pages/yearly-review/ListeningDepth.tsx` | ⑧ 收听深度 |
| `frontend/src/pages/yearly-review/SpecialMoments.tsx` | ⑨ 特殊时刻 |
| `frontend/src/pages/yearly-review/MonthlyDrilldown.tsx` | ⑩ 月度下钻 |
| `frontend/src/pages/yearly-review/YearComparison.tsx` | ⑪ 年度对比 |
| `frontend/src/pages/yearly-review/ShareButton.tsx` | ⑫ 分享长图 |

#### 修改文件

| 文件 | 改动 |
|---|---|
| `backend/api/wrapped.py` | 新增 `/wrapped/{year}/full` 端点 |
| `frontend/src/App.tsx` | 添加 `/yearly-review` 路由 |
| `frontend/src/components/layout/Masthead.tsx` | 将「年度回顾」从 disabled 改为可用链接 |

---

#### Task 1.1: 创建 WrappedFullResponse Pydantic 模型

涉及文件：`backend/models/wrapped.py`。

- 写入完整模型定义
- 验证模型可导入

#### Task 1.2: 实现 get_wrapped_full() 服务函数

涉及文件：`backend/services/wrapped_service.py`。

- 依赖分析** — 需要哪些数据库查询

先确认 `spotify_album_meta` 和 `spotify_artist_meta` 表结构：

- 写入服务函数骨架 + 数据加载部分

`backend/services/wrapped_service.py`:

- 修复 daily_grid 的日期解析逻辑

daily_grid 中 `pd.to_datetime(year_df["ts_date"]).dt.day` 可能失败（ts_date 是字符串格式 YYYY-MM-DD）。改用字符串切片：

- 检查语法正确性

#### Task 1.3: 新增 /wrapped/{year}/full 端点

涉及文件：`backend/api/wrapped.py`。

- 更新 wrapped.py

注意：`/{year}/full` 必须注册在 `/{year}` 之后，否则 FastAPI 会把 "full" 当作 year 参数。

#### Task 1.4: 验证端点可访问

- 启动后端并测试新端点

验证输出：
- `empty` 为 `false`
- `hero` 有 6 个 key
- `personality` 有 7 个维度
- `top_lists.artists` 有 5 条
- `monthly_drilldown` 有 12 个月
- `special_moments` 含 4 个 key
- 测试空年份

#### Task 1.5: 编写后端测试

涉及文件：`backend/tests/test_wrapped_full.py`。

- 写入测试文件

预期：9 个测试全部通过（依赖真实数据库中有 2024 年数据）。

---

#### Task 2.1: 类型定义 + 工具函数

涉及文件：`frontend/src/types/yearly-review.ts`、`frontend/src/lib/personality-themes.ts`、`frontend/src/lib/genre-regions.ts`。

- 写入类型定义

`frontend/src/types/yearly-review.ts`:

- 写入人格主题色

`frontend/src/lib/personality-themes.ts`:

- 写入流派→地区/语言映射表

#### Task 2.2: 数据获取 hook

涉及文件：`frontend/src/hooks/useYearlyReview.ts`。

- 写入 hook

#### Task 2.3-2.14: 12 个子组件 + CustomSummary 主组件

由于组件数量多，每个遵循相同模式：

```
<GlassCard> / <section>
  <h2>模块标题</h2>
  <模块内容 />
</GlassCard>
```

详情跳转模式：`<Link to={`/music/artists/${encodeURIComponent(name)}`}>`

封面图回退模式：`<img src={cover_url || '/placeholder-cover.svg'} />`

- Task 2.3: HeroSection** — `frontend/src/pages/yearly-review/HeroSection.tsx`
  - 接收 `hero: WrappedFullHero` 和 `theme: PersonalityTheme`
  - 全宽卡片，渐变背景 `bg-gradient-to-br from-[bgStart] to-[bgEnd]`
  - 年分数大字（text-7xl），Playfair Display
  - 6 个 KPI 指标两行排列：总时长 / 总播放 / 独特曲目 / 独特艺人 / 听歌天数 / 日均时长
  - 数字使用 `font-sans tabular-nums`

- Task 2.4: PersonalityReveal** — `frontend/src/pages/yearly-review/PersonalityReveal.tsx`
  - 接收 `personality: PersonalityResult`
  - 雷达图使用 ECharts（动态 import），`echarts/charts` 中的 `radar` 类型
  - 7 维指示器：探索者/专一者/狂听者/夜猫子/收藏家/新潮派/地球村
  - 动画：`useEffect` 中每 300ms 递增一个维度的 data 值（从 0 到实际分数）
  - 全部展开后，下方弹出主人格标签 + 描述文案（fade-in + scale-in，CSS transition）
  - 雷达图配置 `radar.axisName` 使用各维度 label

- Task 2.5: TopCharts** — `frontend/src/pages/yearly-review/TopCharts.tsx`
  - 接收 `topLists: TopLists`
  - 三列 `grid grid-cols-1 md:grid-cols-3 gap-6`
  - 每列：5 个条目垂直排列，每个：排名编号 + 封面 `w-12 h-12 rounded`（艺人用 `rounded-full`）+ 名称 + 统计数字
  - 名称可点击 → `<Link to={...}>`

- Task 2.6: GenrePanorama** — `frontend/src/pages/yearly-review/GenrePanorama.tsx`
  - 接收 `genrePanorama: GenrePanorama`
  - Top 5 流派：横向柱状图（纯 DOM，`div` bar 宽度 = `play_share%`）
  - 流派进化：ECharts 堆叠面积图，12 个月 × Top 5 流派
  - 语言分布：ECharts 环形图 `pie` 类型，`radius: ['50%', '75%']`
  - 无数据时显示占位提示

- Task 2.7: TimeStory** — `frontend/src/pages/yearly-review/TimeStory.tsx`
  - 接收 `timeStory: TimeStory`
  - 听歌日历：12 行 × 31 列方格热力图（纯 DOM），颜色深浅映射 `plays` 值（用 `bg-accent-foreground` 的不同透明度）
  - 月度脉搏：ECharts 柱状图，标注 max/min
  - 高峰时段：ECharts 折线/面积图，24 小时，白天/夜晚双色
  - 深夜画像：占比 KPI + 3 首曲目 mini 列表（含封面）

- Task 2.8: MusicMap** — `frontend/src/pages/yearly-review/MusicMap.tsx`
  - 接收 `genrePanorama: GenrePanorama`
  - 地区分布：横向堆叠条（纯 DOM），每个分段 = 国旗 + 地区名 + 占比
  - Top 海外艺人：如果为空则显示"地区数据将从你的收听流派中推断"

- Task 2.9: DiscoveryReturns** — `frontend/src/pages/yearly-review/DiscoveryReturns.tsx`
  - 接收 `discovery: DiscoveryReturns`
  - 新发现艺人：3 张迷你卡片（封面 + 名称 + 发现日期）
  - 老歌回归：5 行列表（封面 + 曲目 + 播放量 + 发行年份标签）
  - 最长情单曲：横向大卡片（封面 + 曲目名 + "连续播放 X 天"）
  - 无数据时优雅隐藏整个 section

- Task 2.10: ListeningDepth** — `frontend/src/pages/yearly-review/ListeningDepth.tsx`
  - 接收 `listeningDepth: ListeningDepth`
  - 收听年龄：大字展示 `{age} 岁` + 描述文案
  - 专辑完整度：3 张卡片（封面 + 专辑名 + 完成度百分比进度条 `div` 宽度 = `completion_pct%`）
  - 深度聆听率：环形进度图（用 ECharts gauge 或纯 CSS 圆形进度条）

- Task 2.11: SpecialMoments** — `frontend/src/pages/yearly-review/SpecialMoments.tsx`
  - 接收 `specialMoments: SpecialMoments`
  - 4 格网格：最活跃日 / 最早听歌 / 最晚听歌 / 最长连续
  - 每格一个小卡片，含图标 + 数据 + 关联曲目封面（如有）

- Task 2.12: MonthlyDrilldown** — `frontend/src/pages/yearly-review/MonthlyDrilldown.tsx`
  - 接收 `monthlyDrilldown: MonthlyDrillItem[]`
  - 12 张折叠卡片（使用 `Collapsible` 或自定义 `details/summary` 等效）
  - 折叠态：月份 + 总时长
  - 展开态：Top 3 曲目（含封面）+ Top 艺人 + 总时长
  - 默认只展开"峰值月"

- Task 2.13: YearComparison** — `frontend/src/pages/yearly-review/YearComparison.tsx`
  - 接收 `comparison: YearComparison`
  - 今年 vs 去年：4 个 KPI 对比卡片，每个：指标名 + 变化箭头 ↑/↓ + 百分比
  - Top 5 标记：列表，每个曲目名旁 `NEW` / `经典` badge
  - 无去年数据时："暂无去年数据进行对比" 友好提示

- Task 2.14: CustomSummary** — `frontend/src/pages/yearly-review/CustomSummary.tsx`
  - 接收 `data: WrappedFullResponse`
  - 按顺序渲染所有 12 个组件
  - 每个 section 之间 `mb-12` 间距
  - Hero 区根据 `personality.primary_label` 取 `getPersonalityTheme()` 的配色

- Task 2.15: ShareButton** — `frontend/src/pages/yearly-review/ShareButton.tsx`
  - 安装依赖：`cd frontend && npm install html-to-image`
  - 浮动按钮（`fixed bottom-6 right-6`）
  - 点击：用 `html-to-image` 的 `toPng()` 截取整个页面容器
  - 弹窗预览长图 + 右键保存提示
  - 注意：ECharts 实例需设置 `opts: { useDMA: true }` 确保 Canvas 渲染

#### Task 2.16: 页面入口 + 路由 + 导航

- YearlyReviewPage

`frontend/src/pages/YearlyReviewPage.tsx`:

- 添加路由
- 启用导航入口

---

#### Task 3.1: OfficialWrapped 组件

涉及文件：`frontend/src/pages/yearly-review/OfficialWrapped.tsx`。

- 实现组件

组件结构：
- 使用 `GET /api/wrapped-hub` 获取数据
- Hero KPI: 总时长、艺人/曲目数、连续天数
- 俱乐部卡片: 名称 + 百分位 + 角色
- 艺人竞速图: ECharts 折线图，5 条线 × 12 个月
- 性格指标: 从 `party_metrics` 取 5-6 个关键指标，雷达图或横向柱状图
- 收听年龄: 大字 + 年代阶段标签
- 存档报告: 卡片列表
- 排行榜: 三列 Top 5（含封面）
- 空状态: 引导文案 + 跳转设置页链接

```
if (!data || !data.available) → 空状态引导
else if (data.empty) → 空数据提示
else → 完整渲染
```

---

#### Task 4.1: 分享长图完善

- 确保 `html-to-image` 能正确捕获 ECharts（在 ECharts 初始化时传入 `opts: { useDMA: true }`）
- 分享按钮固定在页面右下角，滚动时悬浮
- 生成长图时显示 loading overlay

#### Task 4.2: 完整流程验证

- 启动前后端
- 浏览器测试

1. 访问 `http://localhost:5173/yearly-review`
2. 验证 Hero 区渲染 + 人格动画揭示
3. 验证 Top 榜单封面图加载 + 详情跳转
4. 切换年份
5. 切换到官方 Wrapped Tab
6. 点击分享按钮生成长图
7. 深色/浅色模式切换

- 运行后端测试

---

### 注意事项

- **封面图**: 所有列出歌曲/艺人/专辑的地方必须展示 `cover_url`，fallback 为占位 SVG
- **详情跳转**: 使用 `<Link to={/music/artists/${encodeURIComponent(name)}}>` 等
- **空状态处理**: 每个模块在无数据时优雅降级（隐藏或显示提示），不要全页报错
- **年份范围**: 初始支持 2024-2025，后续可拓展
- **ECharts 动态加载**: 遵循项目现有模式 — 组件内 `import('echarts/...')`
- **深色模式**: 图表色盘使用 `getChartColors(isDark)` 跟随主题
