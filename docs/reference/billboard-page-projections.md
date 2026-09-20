# Billboard 页面响应投影

阶段 2A 仅改变 Records、Weekly、All-Time 和 Number Ones 的传输形状与前端消费。排名、完整结束周、L2/L3、精选集、双轨时长及持久快照 builder 均沿用既有实现。

## 请求与兼容性

所有路径以下省略 `/api`。省略 `projection` 时，旧完整 `/billboard/data`、`/billboard/weekly`、`/billboard/records`、`/billboard/all-time` 响应保持可用。

| 页面 | 请求 | 已发布来源 | 页面内容 |
|---|---|---|---|
| Records | `/billboard/records?projection=page` | records + summaries + weekly | 原 records 全部字段、Curiosities 候选、艺人计数候选、去重封面字典 |
| Weekly，真实路由 `/billboard` | `/billboard/weekly?projection=page&entity=tracks|albums|artists&week=YYYY-MM-DD` | weekly | 选中周、上一完整榜单周、周选择器 meta、历史入榜 identity |
| All-Time | `/billboard/all-time?projection=entity&entity=tracks|albums|artists` | all_time | 仅当前实体的全部展示行 |
| Number Ones | `/billboard/all-time?projection=number-ones` | all_time | 三类 rank=1 周记录及对应 power_score |

`week` 省略或不在已发布周列表时，沿用旧页面回到最新完整周的行为；不制造不存在的周。`entity` 和 `projection` 不支持的枚举返回 422。

## 精确消费字段

Records 的六个分类仍使用原有 records 对象，60 个字段不裁减、不截短：冠军圣殿保留冠军/空降/回归/阻挡记录；持久传奇保留在榜、连榜、回榜及艺人生涯；爆发时刻保留同时入榜、跃升跌幅、最快出榜；名人堂保留走势总榜、冠军作品与年代纪录；奇趣纪录保留双榜空降和三榜制霸；每周大盘保留总播放、冠亚军差距和新歌比例。

新增的传输内容仅为：

- `curiosity_tracks`：同名且不同艺人的全部候选，以及最早/最新入榜、UTF-16 歌名长度最大/最小的并列候选；字段为 track_id、track_name、artist_name、可用 artist_names、first_week、peak_position。浏览器继续执行原有 localeCompare、排序及 Top 10 选择，不在服务端改变同名分组的显示次序。
- `artist_track_counts`：一曲成名候选与总上榜曲目数前 20 的候选（包含截止值并列）；字段为 artist_name、total_tracks、top1、total_weeks、weeks_at_no1、best_peak、best_peak_track。浏览器保持原有二级排序和 Top 20。
- `covers`：urls 字典及 track/album/artist 的 `[identity, urlIndex]` 映射，只保留上述事实和 records 引用的 identity。沿用旧 buildCoverMaps 的首次非空封面选择与艺人封面 fallback 顺序；不裁掉可见记录或封面。

Weekly 的 current/previous 保留原周记录的全部字段；current 按 rank 稳定排序，等价于旧 selectCurrentWeekData。historical 只保留当前实体曾在更早已发布周出现的 identity，专用于原 NEW/RE membership 判断。不会用“上一周缺席”推断 NEW。meta 沿用周列表，running_peak/running_wks/running_peak_wks 原样传递。

All-Time 将旧 buildAllTimeRows 的字段组合移至纯投影：三类分别保留全部排名、走势积分/固定名次、峰值/周数、封面、身份和相应曲目/专辑计数。全部排序列、搜索、peak filter、分页及列选择仍在浏览器完成；不以当前可见列裁字段，不以页大小裁掉可访问行。专辑/艺人的周统计、首周冠军与封面选择逐行对账旧实现。它们只遍历已解码快照，不读取播放事实或启动 builder。

Number Ones 保留所有冠军周的完整行与三类冠军实体的 identity + power_score；连续周、累计周、年度选择、统计卡继续由原 buildNumberOnes/filterNumberOnesByYear 生成。

## 快照与只读合同

纯投影 helper `backend/api/billboard/projections.py` 只调用持久快照 reader。private 与 public 的投影读取都启用只读 guard；缺失不会转向 private 同步 builder，显式维护入口保留。

基础 key 仍由 family、既有 builder version、数据库绝对路径、规范化 Billboard 参数和来源 revision 构造。projection/week/entity/page/sort/search 不进入持久 key，不增加 family、持久行或写入。只允许 exact 或同 request-key LKG。读取后原样返回 snapshot freshness/source/target。

Records 用同一完整过滤参数构造三个 family 的 context，并在读取前后复核 context 未漂移；三个 snapshot 的 source revision、target revision、freshness/status 必须一致。builder version 来自同一既有 context builder，reader 要求 row 的版本匹配。缺失、key 异常、来源漂移或混代均返回 503 `snapshot_unavailable`，不猜测兼容性、不混拼事实。

## 前端 Query 与竞态

所有投影使用 TanStack Query 和 `queryKeys.billboard.projection(path, params)`；参数带完整 Billboard context。Weekly 额外包含 week/entity；All-Time 包含 entity/page/page_size/sort/direction/peak_filter/search。All-Time 的这些视图参数不改变实体全集，服务端只用 entity 投影，浏览器保持现有排序/搜索语义。

queryFn 传递 AbortSignal，切周/实体/过滤条件后旧响应不会写入新 key。Weekly 切周或实体时使用上一份投影作为过渡帧，但展示标签始终取自该投影自己的 `entity` / `selected_week`；新结果就绪后再原子替换，不能把旧单曲事实标成专辑榜。当前周的相邻实体和相邻两周会在后台预取，5 分钟内返回已缓存目标不重复请求。

All-Time 仅在实体和全部 Billboard context 相同、只改变本地视图参数时保留上一份相同实体事实，避免搜索输入框卸载和失焦；当前实体就绪后预取同视图的另外两个实体。切过滤条件不沿用旧响应。没有模块级响应 Map、全历史预取或同时发出的旧 full query。

`/billboard` 六个子页面共享一个持久路由外壳，桌面子导航不随子页面 chunk 卸载；导航 hover/focus 预取目标页面 chunk。首次进入仍可显示页面骨架；已有内容后的切换保留上一帧，稳定容器用 `aria-busy` 表达进度，不插入可见提示或整页 skeleton，因此导航、内容和右上区域都不因切换发生布局位移。同语义 LKG 保留旧事实并静默刷新，不再依赖全局 Query Cache 扫描。

## 验证与回滚

后端 projection unit/contract 覆盖排序、历史回榜、exact/LKG/missing、参数不兼容、key 异常、混代和 422；public sentinel 禁止 builder、发布和 JobQueue。使用默认 pytest 临时路径隔离。

`frontend/tests/billboard-projection-parity.test.tsx` 接受 `BILLBOARD_PARITY_DIR` 中保存的 old/new JSON，比较全部周、行、字段、排序/筛选、冠军历史、Curiosities DOM/链接/封面。无捕获数据时显式 skip；常规 hook/组件测试独立运行。实际校准数据保留在交付证据目录，不进 Git。

回滚只需恢复这四页到兼容完整接口及对应 hooks；不需要数据库迁移、重建或删除快照。交付与原始测量索引见[阶段 2A 报告](../reports/2026-09-19-billboard-page-projections.md)。
