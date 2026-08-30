# 播放记录全板块统计正确性与稳定排序修复交付

> 日期：2026-08-30
> 状态：PARTIAL（代码、自动化测试和真实数据库只读探针已完成；真实 API/页面内容验收受冷计算阻塞）
> 关联规划：[`../plans/2026-08-30-playback-records-correctness-and-ranking-plan.md`](../plans/2026-08-30-playback-records-correctness-and-ranking-plan.md)
> 当前规则：[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)
> 部署状态：未部署；未 push

## 1. 交付结论

本轮已实现播放记录页面的统计口径修复、完整候选集排序、二级/后续排序和前端精确值重排。实现覆盖 5 个可见板块、20 个可见模块，以及未挂载前端的 API-only 模块。

已修复的明确问题：

- standalone 页面在年度/自定义范围下不再用筛选后的事件帧计算 lifetime 播放里程碑。
- 艺人 fan-out 保留 `role`，合作艺人榜只统计 `featured`，避免把 primary 艺人计入合作艺人。
- 单日最长连续播放天数的单日分支使用真实播放次数和毫秒时长，不再固定输出 0 小时。
- 工作日偏好在排序后生成 rank。
- 单日总量时长榜使用原始 `total_ms`，小时仍仅用于一位小数显示。
- 单日/周期冠军、连续记录、发现、合作曲、深夜、平台和行为记录均使用完整候选集与确定性稳定键。

## 2. 实现范围

- 新增 `backend/domains/playback/records_sorting.py`，统一提供 `sort_and_limit` 与 `select_period_winners`。
- 更新 `records_obsession.py`、`records_reigns.py`、`records_longevity.py`、`records_time.py`、`records_discovery.py`、`records_behavior.py` 的统计和排序。
- 更新 `analysis_records_service.py` 的 lifetime 事件帧和排序契约版本；更新 `PlaybackRecordRow` 的 `total_ms` 字段。
- 前端单日总量时长切换使用毫秒值，深夜轨迹最高周期使用精确占比；新增对应组件回归测试。
- 更新当前统计规则、文档地图、实施计划和本交付报告。
- 播放记录页面完成文案收口：标题已经清楚的板块移除冗余 subtitle，其余说明改为用户可理解的统计结果描述，不再暴露 `run`、数据资格判断或缺失字段等内部处理细节。

## 3. 真实数据库只读探针

探针口径：`min_ms=30000`、仅音乐、合并连续播放、动态阈值、`max_merge_gap_minutes=5`、L2、不含精选集。数据库未写入。

```text
有效事件：66,419
日期范围：2022-07-01 — 2026-08-21
有效时长：4,196.14 小时
track / album / artist 帧：66,419 / 66,419 / 70,737
artist role：primary, featured
flat record modules：70，非空 70
behavior_playback_milestones.total_plays：66,419
```

关键输出规模包括：24 个小时冠军/实体类型、月度巅峰每类 50 行、年度巅峰每类 5 行、深夜峰值日 50 行、跨年 2 行、发现日每类 50 行、专辑全碟回放 50 行、合作艺人 50 行、行为模块各自按 Top 50 或完整平台集合输出。单日总量内部保留 `total_ms`；探针初次检查误用了不存在的旧 flat key `obsession_daily_total_record`，因此该一项的首次布尔输出不作为证据，精确字段另由源码、专项测试和 `PlaybackRecordRow` 序列化检查确认。

## 4. 自动化验证

通过：

- 播放记录专项后端回归：`66 passed`（既有相关测试与新增排序契约测试合计）。
- 新增排序契约测试：`10 passed`。
- 前端播放记录测试：`18 passed`。
- 前端生产构建：`npm run build` 通过。
- 后端完整 contract：`403 passed`。
- `ruff`、`compileall` 通过。
- `python3 scripts/docs_audit.py`：76 个当前 Markdown，PASS。

完整 unit 结果为 `1,428 passed, 2 failed`。两个失败均来自工作区中本轮之前已存在的 Billboard 架构 dirty 修改：`backend/domains/billboard/records_longevity.py` 超过既有 260 行阈值、`backend/domains/billboard/records_endurance.py` 超过既有 310 行阈值；不涉及本轮播放记录改动，未擅自修改。

## 5. 真实 API 与浏览器边界

临时实例的 health 已返回 HTTP 200，前端页面壳和播放分析导航可打开；但固定 `/api/analysis/records` 冷请求在 45 秒、随后接近 4 分钟的窗口内仍未返回，后端进程持续高 CPU。现有 8000 进程也存在同样的长时间冷计算子进程。为避免杀掉用户进程或把超时当成空数据，本轮未完成真实 API payload、5 个板块内容、桌面/紧凑/390px 页面内容和横向溢出的最终验收，状态为 `BLOCKED`。

已停止本轮临时启动的 18000 后端和 15173 前端；现有 8000/5173 用户进程未触碰。后续应在预热缓存或低干扰窗口重新请求同一参数，确认 `total_ms` 序列化、所有板块内容和三档视口。

## 6. 提交与回滚

提交前只允许 stage 播放记录源码、测试和文档路径；年度总结、生成 API 文件及其他 dirty 文件必须保持原样。未执行生产部署和 push。回滚不需要恢复原始播放数据，只需回退播放记录代码/规则提交并清理对应进程 LRU 缓存。

## 7. 2026-08-30 页面文案收口（后续补充）

### 7.1 文案原则

- `高光时刻`、`个人王朝`、`长线陪伴`、`时间习惯`、`探索与品味` 等大板块不再重复显示已经由主标题表达的概括性导语。
- `播放里程碑`、`每日冠军次数`、`连续冠军天数` 等标题本身已经足够明确的模块不再添加重复解释。
- 保留的 subtitle 统一使用用户能直接理解的描述，例如“每个月播放次数最高的歌曲、专辑与艺人”“一次连续播放中，连续听同一歌曲、专辑或艺人的最长纪录”。
- 移除“最长 run”“曲目总数可靠”“缺失可靠发行日不参与”等内部算法、数据资格和缺失值说明；这些内容仍由统计规则和测试保证，不放在卡片标题下。

### 7.2 回归与状态

`frontend/src/tests/playback-records-ui.test.tsx` 增加跨 5 个板块的文案回归，检查冗余/技术化文案不再出现，并保留必要的用户化说明。真实 API 和页面内容验收仍受冷计算阻塞，本补充不把局部前端测试或构建结果扩大解释为完整浏览器 Pass。
