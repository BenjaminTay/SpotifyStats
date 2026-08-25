# 音乐详情页年榜历史设计

> 状态：已实现。适用于歌曲、L1/L2/L3 专辑与艺人详情的 `overview` 和兼容 `full` 响应；`summary` 保持空年榜默认值。

## 产品结论

详情页“榜单成绩”保留现有周榜 KPI、排名趋势与周榜历史，并在周榜历史下增加独立的“年榜历史”。桌面使用紧凑表格，Phone 使用年度卡片。“年榜最佳”和“年榜入榜”作为榜单成绩页内的同级 KPI，和最高排名、在榜周数、走势点数、在榜跨度并列；“年榜入榜”只保留年度数量，不显示重复解释。年榜历史标题不再附加右侧说明。有年榜摘要时桌面 KPI 使用 3×2 网格，无年榜摘要的四项周榜 KPI 使用单行四列，Phone 继续使用两列。详情 Hero 不展示年榜数据。完整年度不显示冗余状态，起始覆盖不足统一标为“不完整”，进行中的年度标为“进行中”，两者均保持轻量且不换行，不设置独立“覆盖范围”列。所有名次数值沿用现有 Billboard 的 Playfair Display 衬线数字样式。

本次不增加年榜排名趋势图。一个实体通常只有少量离散年度，横轴样本稀疏；把完整年度与阶段年度连线还容易暗示连续、可直接比较的时间序列。表格/卡片已经能同时呈现名次、积分、峰值、在榜周、冠军周数、前五周数、年度上榜播放和必要的阶段状态，信息密度与可解释性更高。历史展示统一按年份从旧到新；API 仍保持按年份降序的稳定契约，由展示组件排序副本。年榜最佳先取最低名次；多年并列时取首次达到该名次的最早年度，不再偏向完整年度或最新年度。年份在 Desktop 使用和年度积分一致的无衬线半粗字重与等宽数字；Phone 恢复 Playfair Display 半粗花体，保留移动卡片的年度头层级。年榜排名和周榜峰值继续使用 Playfair Display。桌面排名与周榜统一为两位 Playfair 数字和相同色阶；排名数字本身不增加底色框，仅在首次 peak 的排名右侧显示一次无边框纯文字 `PEAK`。`PEAK` 与周榜变动的 `RE / NEW` 复用同一组字体、10px 字号、字重、大小写和字距，仅保留年榜强调色。Desktop 文字绝对定位在固定宽度的排名锚点外，并以锚点垂直中线定位，不参与单元格居中计算；Phone 为所有年度保留等宽文字槽并显式垂直居中，确保有无标记时名次均纵向对齐。考虑两种字体的字面视觉重心差异，`PEAK` 在几何居中基础上统一向下做 3px 光学校正。年度上榜播放使用 70px 编辑红视觉条；列头已经表达语义，表格单元格不重复“年 / 分 / 周”单位。年度列缩窄，年榜排名靠近年度，释放的空间分配给后续成绩列。Phone 以“年度头 / 年榜与主要指标 / 四项周成绩”三层卡片呈现，并保留脱离表头后必要的小单位；底部四项周成绩使用统一 24px 数值行并垂直居中，消除 Playfair 排名与无衬线周数行盒不同造成的约 2.5px 下沉。如果未来单实体积累至少 5–6 个完整年度，可再基于用户任务验证是否需要独立可视化。

年度数字是进入公共年榜的上下文链接：单曲详情携带 `tab=tracks`，专辑详情携带 `tab=albums`，艺人详情携带 `tab=artists`，并始终携带当前行的 `year`。公共年榜将 `tab` 纳入 URL 状态，保证从详情页进入后直接落在同实体类型榜单，切换榜单类型时也同步更新 URL；链接保留既有年度字体，仅增加 hover 与键盘焦点反馈。

周榜历史沿用同一类型感知规则：榜单周链接同时携带 `week` 与 `tab`，歌曲、专辑、艺人分别进入对应的单曲榜、专辑榜、艺人榜；Desktop 表格和 Phone 历史列表共用同一 URL builder。单曲详情顶部不再维护独立的无边框 KPI 样式，统一复用专辑/艺人的 `KpiCard`；首次达峰、首次入榜、总播放和走势排名归入对应主指标的副文案，不丢失数据。有年榜摘要时 Desktop 使用 3×2，无年榜摘要时四项周榜 KPI 使用单行四列，Phone 继续两列。

## 数据来源与生命周期

详情 GET 不运行完整 Billboard 或 Year-End builder。migration 46 在精确音乐查找 snapshot 旁新增独立版本的年榜投影：

- `music_search_year_end_projection_state`：记录 builder version、`running/ready/failed`、构建时间和错误。
- `music_search_year_end_meta`：按 snapshot/year 保存覆盖状态、完整年度标识、实际与预期周数和榜单周边界。
- `music_search_entity_year_end`：按 snapshot/family/entity/year 保存年榜名次与行级成绩。

投影只读取 migration 42 的 `music_search_weekly_chart_context` 精确周账本，并复用公共 Year-End metric/scoring/sort 函数。shared-full、同周 delta、跨周 delta 和旧 snapshot 复用最终都经过六变体投影维护；旧 snapshot 缺少账本时，只允许后台维护任务补建。核心搜索 snapshot 与投影分开提交：投影失败会记录并重试，但不会把已经可用的搜索/详情摘要改成 failed。migration 47 负责修复短暂发布过的 v46 覆盖状态 CHECK，已应用旧 v46 的数据库不依赖重跑迁移。

应用启动时的跳过条件同时检查“六套当前精确 snapshot ready”和“六套当前版本年榜投影 ready”。旧数据库即使已经有完整 snapshot，只要投影缺失、失败或版本过期，启动维护仍会幂等排入一个 snapshot-set 后台任务，并先把对应投影标成 `pending`；详情页在任务执行期间读取为 `warming`。任务会在后台补齐旧 snapshot 缺少的精确周账本并生成投影，第二次启动不得重复排队。处理器异常退出时，尚未完成的 `pending` 状态必须转为 `failed`，避免永久伪装成 warming。

核心 snapshot 重新发布同一个 fingerprint 前必须清空旧投影；旧 snapshot pruning 在 SQLite foreign key 未启用时也要显式清理三张投影表，禁止孤儿或过期年榜行被误复用。

## API 契约

三类详情响应统一增加：

- `year_end_status`: `ready | warming | unavailable`。
- `year_end_summary`: 榜单成绩 KPI 使用的最佳/最新年度、名次、完整性与入榜年度数；未入过年榜时为 `null`。
- `year_end_history`: `overview/full` 返回按年份降序的完整行，`summary` 固定为空数组；`summary` 同时不读取年榜投影。

`warming` 表示当前精确 snapshot 的投影已排队或正在后台构建；旧 snapshot 的周账本可以尚待同一维护任务补齐。`failed`、版本不兼容或无精确 snapshot 对外降级为 `unavailable`。`ready + summary=null + history=[]` 表示投影已完成但实体从未进入年榜，不能显示虚假 `#0`。

## 性能与验收门槛

- Summary 不读取年榜投影；不得触发年榜冷构建，冷请求继续遵守 500ms 门禁。进入榜单成绩页后，overview 才读取轻量投影摘要与历史。
- 旧库升级验收必须从“六套 snapshot 已 ready、年榜周账本/投影均为空”的状态启动当前应用，观察单个后台任务完成、六套投影 ready、详情 overview 可读；随后重启并确认不新增任务。
- 年榜投影与公共 Year-End 对共同实体的 rank、score、peak、chart weeks、#1/Top 5/Top 10 weeks 和 chart plays 必须逐字段一致。
- Desktop、390px Phone 均需验证无横向溢出、Hero 中没有年榜内容、年榜 KPI 位于榜单成绩统计组内、周榜历史在上、年榜历史在下、阶段标签可见。
- 年榜历史不挂载 ECharts；现有周榜趋势仍通过 `LazyEChart`/既有图表边界加载。
