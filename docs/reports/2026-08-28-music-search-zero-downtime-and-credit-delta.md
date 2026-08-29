# 音乐查找零停机与曲目署名增量维护交付报告

> 状态：已实施并验证
> 证据日期：2026-08-28 至 2026-08-29
> 范围：Quick Open、`/music/search`、候选索引、四套精确统计、曲目署名任务、设置维护状态与 public-readonly
> 本地提交：`dc7055a7e97b01474022af04624497d4b2ee6064`
> 仓库状态：已在本地 `main` 提交，尚未 push
> 部署状态：本修复未生产部署；下述“已实施并验证”限定为本地代码、真实数据库副本、真实浏览器和默认完整全栈门禁范围

## 结论

本轮已经消除“修改署名后，统计重建期间整个搜索不可用”的产品故障。candidate 与统计现在分别维护
上一成功成品：新 candidate 使用 shadow generation 构建，新统计按变体构建；任何构建开始、失败或
较旧任务晚完成都不能覆盖 active pointer。用户在此期间仍可搜索名称、打开详情，并在有合格 LKG 时
看到明确标注的上一版本播放统计。

署名维护不再默认承担全局 lifetime 重算。角色修改只更新候选展示并轻量 re-key 已验证统计；成员
增删和 undo 优先按 canonical track/artist 闭包、两档阈值和受影响完整周执行 signed delta。旧历史
snapshot 缺少 playback/policy lineage 时会显式进入 shared-full fallback，这是安全门禁命中，不是
增量成功；回退期间 active 成品仍持续服务。

## 已实现范围

- migration 60：candidate serving 与 maintenance state 分离。
- migration 61：四变体 active/target pointer 与逐变体 LKG。
- migration 62：曲目署名 canonical before/after change set。
- migration 63：删除、撤销展示资格与隐私影响的即时 deny overlay。
- candidate 与 shared-full/single snapshot 均有 target owner、revision/source、candidate generation 和
  dependency fence；失败写回也只允许修改自己的 target。
- revision-specific queue key、防 superseded 发布、启动 orphan 恢复、设置页人工恢复入口。
- mutation revision 原子 CAS；create/undo 的 idempotent replay 不再重复 dirty/queue。
- Year-End 投影与核心 candidate/context 成败解耦。
- public-readonly 限制为安全 membership，隐藏 target fingerprint、job 与内部错误，GET 不排队、不写库。

## 真实数据库与运行探针

真实主库已应用 additive schema 63，检查时 `track_credit current=35 / active=35`、candidate ready、四个
active snapshot pointer 完整、deny overlay 为空。主库 ready 状态下 25 次 `Hold` candidate 请求
P95 为 10.659ms；两实体 context 25 次 P95 为 15.920ms。

在 424MiB Online Backup 副本上构造 target revision 漂移：

| 状态 | Candidate | Statistics | 结果 |
|---|---|---|---|
| building | `ready / last_known_good` | `warming / last_known_good` | 12 个单曲候选，`Hold Me Closer` 仍可打开并显示 35 次与榜单摘要 |
| failed | `ready / last_known_good` | `failed / last_known_good` | private/public 均继续返回 12 个候选；public 不返回 target fingerprint |
| candidate shadow build | active generation 保持旧值 | maintenance=`building` | API 持续返回 12 个候选 |
| candidate cutover | 新 generation 原子成为 active | 旧 active 成为 previous | 数据库只保留 active + previous 两代，响应恢复 `candidate_freshness=current` |

副本上连续 20 组 candidate/context GET 前后比较 index state、maintenance state、variant pointer、job、
snapshot 与 deny 表，结果 `GET_SIDE_EFFECTS=0`。candidate shadow 重建发布 19,443 个文档、75,883 条
n-gram；构建期间和切换后都没有空窗。

## 浏览器验收

真实浏览器使用指向副本 API 的本地前端完成 Desktop 1440×1000、Compact 820×900 和 Phone
390×844 验收：

- Quick Open 在 LKG 状态显示 13 个结果和“搜索索引正在更新”，结果带“上一版本”且可点击；
- 完整搜索页在 failed/warming 状态均保留歌曲、专辑结果，不出现“搜索暂不可用”；
- `Hold Me Closer` 显示 `Britney Spears · Elton John`、35 次、`PK #1` 和走势摘要；
- Desktop 设置的曲目署名面板分别显示“搜索候选 · 已同步”“播放统计 · 上一版本可用”和
  `服务 revision → 目标 revision`；
- 1440/820/390 三档均为 `scrollWidth=clientWidth`，控制台 0 error / 0 warning。

## 自动化验证

- 定向后端：177 passed；另一次合并范围回归 148 passed。
- 定向前端：46 passed；TypeScript 与 production build 通过。
- 完整 unit：1417 passed；完整 contract：392 passed；全量 backend：2324 passed。
- 前端全量：75 files / 594 tests passed；production build 通过。
- Phase 5、文档审计、pre-commit（Ruff、format、mypy、secrets）与 `git diff --check`：通过。
- 默认完整全栈门禁：PASS。API smoke 138/138、boundary 112/112；206 个 OpenAPI operation 与
  97 个参数边界 obligation 均为 0 未覆盖。
- 最终性能门禁使用无 reload 的专用后端，全部热 P95 低于 500ms；`/api/billboard/data` 为
  310ms，`/api/billboard/all-time` 为 280ms。开发 `--reload` 进程曾出现一次 505.7ms 的临界抖动，
  已按失败处理并用同规格、无文件监控干扰的默认完整模式重新验证。
- 浏览器路由、五档响应式、交互、图表、长列表、控件清单均 PASS；Chromium、Firefox、WebKit
  三引擎通过。控件清单覆盖 40 个页面/视口组合、1991 个控件与 395 个主要触控目标，违规为 0。

## 回滚与边界

60–63 均为 additive migration，旧代码可以忽略新表；回滚应用版本时不得先删除 active/LKG pointer、
change set 或 deny overlay。历史真实库 snapshot lineage 为空时，首次署名成员变更会安全回退完整构建，
之后由带完整 lineage 的新 snapshot 获得增量资格。生产发布与主库业务 mutation 不在本轮自动执行范围；
本轮主库写入仅为应用启动的 additive migration 63，所有故障注入均在 `/tmp` Online Backup 副本完成。
本地提交 `dc7055a7` 尚未 push，也没有对应生产 SHA、生产迁移或生产浏览器验收证据。
