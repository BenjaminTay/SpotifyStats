# 阶段7至7D性能验收检查点

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。四份检查点统一排列，保留各轮Partial、性能门槛失败、已通过范围和停止位置。次日7E通过由原7D补记链接承接，不把旧轮改写为Pass。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [阶段 7：全路由性能验收与本地收口](#阶段-7全路由性能验收与本地收口)
- [阶段 7B：验收阻塞修复与本地收口（Partial）](#阶段-7b验收阻塞修复与本地收口partial)
- [阶段 7C：Git 检查点、性能阻塞收口与本地全栈验收（Partial）](#阶段-7cgit-检查点性能阻塞收口与本地全栈验收partial)
- [阶段 7D：Import Preflight 复用与最终本地全栈验收（Partial）](#阶段-7dimport-preflight-复用与最终本地全栈验收partial)

## 阶段 7：全路由性能验收与本地收口

原记录：`2026-09-20-stage7-local-performance-acceptance.md`。

**结论：Partial，未达到“阶段7本地全栈 Pass”。** 本报告只记录本轮当前 dirty worktree 的独立证据。此前阶段报告仅用于确定合同和预算，不作为本轮通过依据。

- HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`。未 add、commit、push、部署或同步正式数据。
- 证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bdd8-b911-7b33-b062-c94e7b068598/spotifystats-stage7`；数据库副本和隔离 sidecar 位于 `/tmp/spotifystats-stage7`。证据含真实响应/截图，保存在本机，不纳入 Git。
- 真实数据经 SQLite Online Backup 得到 92,908 条播放；副本迁移至 schema 76。默认过滤为 min_ms=30000、music_only=true、merge_enabled=true、gap=5、dynamic=true、L2、compilation=false；Billboard TopN=30/20/20、周五 12:00，Asia/Shanghai。
- 后端为 loopback、无 reload、lifespan=off 的测量服务；解释器启动和健康检查不计入请求时间。进程重启读不等于正常 lifespan 调度验收；后者仍有完整套件中的启动失败待解决。Python socket 禁止外部连接；浏览器专项拦截外网、写请求和 AI 请求。

### 已实现的必要修复

| 症状 | 根因与最小改动 | 当前证据 |
|---|---|---|
| 两个完整 contract 的 Analysis 503 | 默认 fixture 未私有发布；未知/空 period 在 reader 中提前拒绝，偏离原 builder lifetime 语义。增加真实发布 fixture，恢复规范化；GET 保持只读，未将默认 200 改成 503 | 原失败、28 项定向通过；完整 contract 437 passed |
| preflight schema 版本失败、CLI 假设已迁移 | 最新常量 75 落后于 migration 76；Archive/Governance CLI 先运行 run_migrations | preflight 通过；旧 seed CLI 两项回归通过 |
| 测试清理误报及 sidecar 环境继承 | dir_fd 相对路径误用 cwd；新增三类 sidecar 未加入 session 重定向 | 目录句柄 canary 与六类路径验证；正式数据另行核对 |
| 性能目录空跑 | 用字典字符串中的花括号判断未配置，所有目标被排除；改为检查参数值，并拒绝零目标 | 探针 11 项通过；真实 HTTP 矩阵 |
| 性能目录不符当前消费者 | Billboard 改为当前 projection；补齐治理/档案/帖子；私有治理与年度维护状态使用其实际 surface | 原 404 与 artist candidate 漏 q 的 422 保留；修正 surface/必需参数后重测 200 |
| 完整 quality 失败 | hook 格式化 21 文件；3 文件的4个 mypy 类型错误 | 第二轮 quality PASS；格式类增量有 AST 对账 |

### 基线、竞争和计量范围

- 起点全部 tracked/untracked 文件与正式 data 清单、大小、SHA-256、Git 暂存内容、端口/进程均保存在 `*-before.*`。`routes.txt`、`api-consumers.txt`、`maintenance.txt` 由当前源码 rg 重新生成。OpenAPI 222 operations 和 104 参数义务均无未归类项；这表示审计覆盖登记完整，不等于每项真实部署通过。
- 使用 `/tmp/spotify-fullstack-verification.lock` 主机锁，完整门禁使用同一显式锁路径。其他项目普通 pytest/Vitest/类型检查不遵守此锁；16:32:03 起发现教师导航任务竞争，暂停自有 API 测量，结束后重测受影响目标。`contention.json` 与进程清单保留竞争窗口；原样本不删除、不用于达标。其他项目的 idle Vite/uvicorn 保留原状。
- `api-matrix.json`、`cold-matrix.json`、`api-corrections.json` 保存原样本；`api-performance.normalized.json` 只补齐测量合同 metadata，不更改任何耗时/失败。SQL rows 为 cursor 返回行数，不是物理扫描页数。RSS 为服务器进程累计峰值，不是某一个接口的独占内存。builder/enqueue 仅针对探针注册的函数观测，不能把未注册函数宣称为零。

### 默认维护与持久读取

| 私有操作 | 联合进程 wall 秒 | 说明 |
|---|---:|---|
| prepare-analysis_records | 12.773 | 正式 service 私有入口，真实副本 |
| prepare-analysis_stats | 6.135 | 正式 service 私有入口，真实副本 |
| prepare-archive | 1.761 | 正式 service 私有入口，真实副本 |
| prepare-billboard | 8.839 | 正式 service 私有入口，真实副本 |
| prepare-community | 4.874 | 正式 service 私有入口，真实副本 |
| prepare-governance | 5.085 | 正式 service 私有入口，真实副本 |
| prepare-home | 6.840 | 正式 service 私有入口，真实副本 |
| prepare-search | 26.973 | 正式 service 私有入口，真实副本 |
| prepare-yearly-2022 | 39.310 | 正式 service 私有入口，真实副本 |
| prepare-yearly-2023 | 46.903 | 正式 service 私有入口，真实副本 |
| prepare-yearly-2024 | 49.752 | 正式 service 私有入口，真实副本 |
| prepare-yearly-2025 | 49.461 | 正式 service 私有入口，真实副本 |
| prepare-yearly-2026 | 47.943 | 正式 service 私有入口，真实副本 |

- Search 为当前 L2/L3 × dynamic/fixed 四变体；Archive 六章、Governance 结果与共享事实、Analysis 两 family、Community 一代、Billboard 默认 family、2022–2026 年度均完成私有准备。无任意筛选穷举。
- **Home 重启 exact 未通过**：初次准备后新进程只能读 LKG；`_cache_parts` 仍包含进程内 `latest_snapshot_revision`，重启归零导致持久 key 变化。旧事实仍可读，但不能算 exact 恢复。
- Records 联合维护 12.773 秒仍高于既有 ≤10 秒目标；该轮复用同进程已有依赖，不能冒充独立 cold builder 三次中位数。未增加缓存框架来追逐数字。

### 后端实际消费者矩阵

当前 dirty worktree 的结果是本轮独立基线；没有同机、同源、同配置的阶段优化前路由样本，因此不填写未经证明的相对改善比例。每行保留一次首次请求和至少20个 warm 样本。下表首次为系列首次，只有后续独立进程表才可称 process-cold。手动 Import preflight 的本地文件扫描另列成本；不能把它说成首页阻塞，也不能绕过标准 benchmark 的失败。细分 SQL、读取行、snapshot/source revision、raw/wire、RSS 见对应 JSON。

| 接口 / projection | 消费者 | HTTP | 首次 ms | warm P95 ms | raw / wire B |
|---|---|---:|---:|---:|---:|
| `/api/home/overview`  | Home (current) | 200 | 239.55 | 70.756 | 9981 / 2345 |
| `/api/analysis/stats`  | 播放统计 (current) | 200 | 403.87 | 14.922 | 205985 / 34272 |
| `/api/analysis/charts`  | 播放排行 (current) | 200 | 4884.86 | 5.752 | 40036 / 6824 |
| `/api/analysis/records`  | 播放记录 (current) | 200 | 445.12 | 94.545 | 2096306 / 126373 |
| `/api/analysis/plays`  | 最近播放记录 (current) | 200 | 62.94 | 120.671 | 14429 / 2630 |
| `/api/analysis/play-dates`  | 播放日历 (current) | 200 | 21.07 | 33.672 | 49326 / 6545 |
| `/api/billboard/entity-lists`  | Versus (current) | 200 | 156.21 | 219.997 | 191634 / 48223 |
| `/api/billboard/year-end`  | Year-end (current) | 200 | 17.53 | 15.86 | 56149 / 7315 |
| `/api/yearly-review/available-years`  | 年度总结 (current) | 200 | 7.08 | 6.301 | 55 / 55 |
| `/api/yearly-review/generation-status`  | 年度维护状态 (current) | 200 | 1242.35 | 2101.739 | 810 / 810 |
| `/api/community/feed`  | Community (current) | 200 | 183.34 | 11.042 | 31545 / 7268 |
| `/api/community/trending`  | Community (current) | 200 | 11.53 | 9.383 | 971 / 971 |
| `/api/settings`  | Settings (current) | 200 | 6.82 | 5.757 | 470 / 470 |
| `/api/import/health`  | Settings import health (current) | 200 | 7.10 | 5.412 | 9153 / 2340 |
| `/api/import/preflight`  | Settings import preflight (current) | 200 | 4542.56 | 7882.998 | 8171 / 1670 |
| `/api/version-merge/groups`  | Settings release groups (current) | 200 | 7.79 | 5.76 | 15855 / 2610 |
| `/api/version-merge/track-groups`  | Settings track groups (current) | 200 | 31.30 | 22.531 | 202542 / 25720 |
| `/api/version-merge/l3-album-attributions/health`  | Settings L3 (current) | 200 | 6.26 | 4.463 | 615 / 615 |
| `/api/version-merge/l1-identity-risks/health`  | Settings L1 (current) | 200 | 6.02 | 3.515 | 881 / 881 |
| `/api/music-metadata/track-credits/status`  | Settings credits (current) | 200 | 5.13 | 3.781 | 2092 / 576 |
| `/api/metadata/artist-genres/coverage`  | Settings genre (current) | 200 | 8.55 | 6.451 | 2150 / 784 |
| `/api/metadata/artist-genres/taxonomy`  | Settings genre (current) | 200 | 10.90 | 9.191 | 41865 / 6762 |
| `/api/metadata/artist-genres/axis-gaps`  | Settings genre (current) | 200 | 13.01 | 66.386 | 13034 / 1613 |
| `/api/metadata/artist-genres/reviews`  | Settings genre reviews (current) | 200 | 5.18 | 4.806 | 22 / 22 |
| `/api/metadata/artist-languages/coverage`  | Settings language (current) | 200 | 7.90 | 6.686 | 6095 / 2047 |
| `/api/metadata/artist-languages/reviews`  | Settings language reviews (current) | 200 | 4.24 | 3.212 | 22 / 22 |
| `/api/billboard/weekly` projection=page; entity=tracks | Weekly (current) | 200 | 60.65 | 103.266 | 26317 / 4691 |
| `/api/billboard/all-time` projection=entity; entity=tracks | All-time (current) | 200 | 88.43 | 136.26 | 598698 / 87359 |
| `/api/billboard/all-time` projection=number-ones | Number Ones (current) | 200 | 76.24 | 129.133 | 215412 / 28608 |
| `/api/billboard/records` projection=page | Records (current) | 200 | 122.49 | 192.6 | 338692 / 56287 |
| `/api/community/post/{post_id}`  | Community post (current) | 200 | 15.79 | 13.923 | 2706 / 1067 |
| `/api/community/feed` accounts=@chartdata; limit=20 | Community account (current) | 200 | 18.21 | 10.055 | 10548 / 2364 |
| `/api/account/archive-overview`  | 音乐档案 (current) | 200 | 6.37 | 4.94 | 2351 / 965 |
| `/api/account/collection-journey`  | 音乐档案 (current) | 200 | 6.61 | 6.036 | 4171 / 1266 |
| `/api/account/collection-cohorts`  | 音乐档案 (current) | 200 | 6.62 | 5.809 | 11808 / 3131 |
| `/api/account/returns`  | 音乐档案 (current) | 200 | 5.39 | 5.364 | 6410 / 2130 |
| `/api/account/discovery`  | 音乐档案 (current) | 200 | 6.33 | 5.263 | 3329 / 1378 |
| `/api/account/other-media`  | 音乐档案 (current) | 200 | 4.97 | 5.506 | 2826 / 1220 |
| `/api/account/library/tracks`  | 音乐档案 (current) | 200 | 35.31 | 27.582 | 5329 / 1460 |
| `/api/account/library/albums`  | 音乐档案 (current) | 200 | 64.80 | 68.243 | 4792 / 1315 |
| `/api/account/library/artists`  | 音乐档案 (current) | 200 | 13.37 | 16.674 | 3782 / 912 |
| `/api/account/library/playlists`  | 音乐档案 (current) | 200 | 47.66 | 14.077 | 8013 / 1984 |
| `/api/music/search` q=love; response_mode=candidates; eligibility=current | Quick Open/Search (current) | 200 | 47.95 | 18.942 | 4680 / 1198 |
| `/api/music/search/context` entity_key=track:1325 | Search statistics (current) | 200 | 9.33 | 9.509 | 421 / 421 |
| `/api/billboard/weekly`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 171.56 | 220.963 | 4654160 / 402895 |
| `/api/billboard/all-time`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 273.98 | 303.641 | 6761635 / 697316 |
| `/api/billboard/data`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 308.45 | 330.116 | 7745688 / 821989 |
| `/api/billboard/records`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 25.06 | 24.855 | 289171 / 43920 |
| `/api/billboard/power-scores`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 41.73 | 38.376 | 632555 / 94594 |
| `/api/billboard/summaries`  | 完整兼容响应；页面使用显式 projection (compatible) | 200 | 59.46 | 109.425 | 1475366 / 199283 |
| `/api/yearly-review/2026`  | 年度总结 (current) | 200 | 71.79 | 70.04 | 254891 / 31481 |
| `/api/billboard/track/canonical/{track_id}` view=summary | 音乐详情 (current) | 200 | 104.40 | 186.013 | 830 / 830 |
| `/api/billboard/track/canonical/{track_id}` view=overview | 音乐详情 (current) | 200 | 3585.10 | 127.167 | 882 / 882 |
| `/api/music/tracks/l1/{track_id}/stats` include_rank_context=false | 音乐详情播放统计/子视图 (current) | 200 | 7.67 | 7.47 | 3283 / 874 |
| `/api/music/tracks/l1/{track_id}/plays`  | 音乐详情播放统计/子视图 (current) | 200 | 21.04 | 24.997 | 1126 / 352 |
| `/api/music/tracks/l1/{track_id}/play-dates`  | 音乐详情播放统计/子视图 (current) | 200 | 14.38 | 12.31 | 97 / 97 |
| `/api/music/tracks/l1/{track_id}/stats` include_rank_context=true | 音乐详情延后全局排名 (current) | 200 | 10014.98 | 6.452 | 4334 / 1022 |
| `/api/billboard/album-project/{project_id}` view=summary | 音乐详情 (current) | 200 | 82.84 | 132.269 | 1091 / 506 |
| `/api/billboard/album-project/{project_id}` view=overview | 音乐详情 (current) | 200 | 1966.58 | 135.451 | 2091 / 725 |
| `/api/billboard/album-project/{project_id}` view=tracks | 音乐详情 (current) | 200 | 79.46 | 129.12 | 1567 / 638 |
| `/api/billboard/album-project/{project_id}` view=project | 音乐详情 (current) | 200 | 1907.18 | 148.039 | 4947 / 791 |
| `/api/music/album-projects/{project_id}/stats` include_rank_context=false | 音乐详情播放统计/子视图 (current) | 200 | 171.55 | 6.99 | 8152 / 1462 |
| `/api/music/album-projects/{project_id}/rankings`  | 音乐详情播放统计/子视图 (current) | 200 | 258.47 | 390.041 | 2784 / 774 |
| `/api/music/album-projects/{project_id}/plays`  | 音乐详情播放统计/子视图 (current) | 200 | 283.70 | 289.624 | 12099 / 1226 |
| `/api/music/album-projects/{project_id}/play-dates`  | 音乐详情播放统计/子视图 (current) | 200 | 176.01 | 262.238 | 801 / 801 |
| `/api/music/album-projects/{project_id}/stats` include_rank_context=true | 音乐详情延后全局排名 (current) | 200 | 20655.14 | 7.749 | 22086 / 2721 |
| `/api/billboard/artist/{artist}` view=summary | 音乐详情 (current) | 200 | 95.95 | 133.923 | 755 / 755 |
| `/api/billboard/artist/{artist}` view=overview | 音乐详情 (current) | 200 | 605.70 | 153.716 | 47709 / 6627 |
| `/api/billboard/artist/{artist}` view=tracks | 音乐详情 (current) | 200 | 78.70 | 130.053 | 12680 / 2361 |
| `/api/billboard/artist/{artist}` view=albums | 音乐详情 (current) | 200 | 139.33 | 152.627 | 2988 / 970 |
| `/api/music/artists/{artist}/stats` include_rank_context=false | 音乐详情播放统计/子视图 (current) | 200 | 10.94 | 11.4 | 52804 / 6992 |
| `/api/music/artists/{artist}/rankings`  | 音乐详情播放统计/子视图 (current) | 200 | 4275.89 | 880.57 | 7723 / 1614 |
| `/api/music/artists/{artist}/plays`  | 音乐详情播放统计/子视图 (current) | 200 | 290.74 | 393.781 | 18879 / 2511 |
| `/api/music/artists/{artist}/play-dates`  | 音乐详情播放统计/子视图 (current) | 200 | 188.98 | 186.744 | 10979 / 1362 |
| `/api/music/artists/{artist}/stats` include_rank_context=true | 音乐详情延后全局排名 (current) | 200 | 32705.99 | 22.384 | 84541 / 11860 |
| `/api/artist-identities`  | Settings artist identity (current) | 200 | 7.24 | 20.536 | 18104 / 2594 |
| `/api/artist-identities/candidates`  | Settings artist identity candidates (current) | 422 | 11.68 | 不足 | 87 / 87 |
| `/api/artist-identities/events`  | Settings artist identity audit (current) | 200 | 6.43 | 4.569 | 5488 / 1711 |
| `/api/artist-identities/candidates` q=Lana Del Rey | Settings artist identity candidates (current) | 200 | 335.98 | 135.26 | 1072 / 442 |

#### 独立进程首次读取

| 目标 | snapshot 状态 | 三次 ms | 既有门槛 |
|---|---|---|---|
| `/api/home/overview` | LKG | 341.581 / 239.69 / 242.888 | ≤500ms |
| `/api/analysis/stats` | exact | 438.181 / 447.478 / 419.877 | ≤500ms |
| `/api/analysis/records` | exact | 394.193 / 392.865 / 392.764 | ≤500ms |
| `/api/community/feed` | exact | 128.854 / 121.645 / 113.856 | ≤500ms |
| `/api/import/health` | exact | 9.921 / 7.939 / 9.753 | ≤500ms |
| `/api/metadata/artist-genres/coverage` | exact | 10.772 / 10.052 / 19.195 | ≤500ms |
| `/api/billboard/weekly` | exact | 98.527 / 75.362 / 73.629 | ≤500ms |
| `/api/community/feed` | exact | 122.405 / 114.571 / 114.238 | ≤500ms |
| `/api/account/collection-cohorts` | exact | 8.949 / 8.889 / 7.815 | ≤500ms |
| `/api/music/search` | unknown | 98.708 / 24.141 / 25.667 | ≤150ms |
| `/api/music/search/context` | unknown | 13.521 / 12.134 / 18.799 | ≤100ms |

### 状态与统计语义

- 标准 unit/contract 当前重跑覆盖发布只读、same-key singleflight、源 fence、previous 损坏/失败保留、空数据、unknown、上海跨日、连续同曲左邻、L2/L3、阈值与合并间隔、collection/search/genre/language 精确失效。具体测试函数登记在 `current-test-inventory.json`。原 builder 的逐字段比较保留在 Records invocation、Archive snapshot、Governance snapshot、Search shared contract/week delta 测试中；不是只验 payload hash 或总数。
- 这些 fixture 回归不能替代全部 family × 全部故障状态的真实进程测量。真实状态注入、缺失目录是否新建，以及测量缺口见下表；未覆盖项不标 Pass。

| 注入状态 | 目标 | HTTP | 首次 ms | 返回状态 |
|---|---|---|---|---|
| source-drift | `/api/home/overview` | 200 | 402.177 / 231.424 / 240.592 | LKG |
| source-drift | `/api/analysis/stats` | 200 | 523.639 / 398.151 / 398.329 | LKG |
| source-drift | `/api/analysis/records` | 200 | 389.7 / 381.444 / 391.828 | LKG |
| source-drift | `/api/community/feed` | 200 | 123.714 / 111.807 / 112.158 | LKG |
| source-drift | `/api/import/health` | 200 | 8.719 / 6.844 / 5.898 | LKG |
| source-drift | `/api/metadata/artist-genres/coverage` | 200 | 8.384 / 8.031 / 7.93 | LKG |
| source-drift | `/api/billboard/weekly` | 200 | 85.201 / 70.311 / 68.679 | LKG |
| source-drift | `/api/account/collection-cohorts` | 200 | 8.102 / 6.519 / 5.871 | LKG |
| missing | `/api/home/overview` | 503 | 232.167 / 232.347 / 234.6 | missing |
| missing | `/api/analysis/stats` | 503 | 5.604 / 8.541 / 6.152 | missing |
| missing | `/api/analysis/records` | 503 | 11.515 / 5.84 / 5.231 | missing |
| missing | `/api/community/feed` | 503 | 5.976 / 6.886 / 6.462 | missing |
| missing | `/api/import/health` | 503 | 3.671 / 3.019 / 2.958 | missing |
| missing | `/api/metadata/artist-genres/coverage` | 503 | 5.291 / 5.443 / 5.684 | missing |
| missing | `/api/billboard/weekly` | 503 | 72.017 / 37.841 / 37.249 | missing |
| missing | `/api/account/collection-cohorts` | 503 | 4.615 / 3.466 / 3.344 | missing |

| 状态 | 本轮证据边界 |
|---|---|
| exact / LKG / missing / source drift / 进程重启 | 真实 HTTP 样本见上述矩阵；Home 重启只有 LKG。Search 缺失状态未纳入 sidecar 目录注入，因为其存储在主库。 |
| failed with LKG / failed without LKG / config drift / builder version drift | 本轮 fixture 套件有相关回归；没有完成所有核心 family 的真实进程故障计时，不标全覆盖。 |
| active 损坏且 previous 可用 / 双代损坏 | 本轮 Analysis/Archive 等 fixture 回归；真实副本全 family 故障计时未完成。 |
| 重建中 GET / 同 key 四并发 | 真实四 family 结果见 concurrency.json；其他 family 仅相应 fixture 回归。 |
| 不同 key 并发 | 未完成跨 family 的真实副本并发验收。 |

### 浏览器全路由

浏览器版本：`{"chromium": "123.0.6312.4", "firefox": "123.0", "webkit": "17.4"}`。Desktop 1440×1000 / Compact 768×1024 / Phone 390×844；每页使用独立 context，按 API 成功和实际事实标记等待，不增加固定 sleep。截图与完整请求日志见 `screenshots/` 和 `browser-matrix.json`。core_ready 仅表示在观测窗口内见到真实内容，不是新增的性能达标预算。12 秒为观察上限。开发服务器的页面基线包含模块加载，API 独立计时不含 Vite 编译。INP 未测；LCP/CLS/long-task 等浏览器支持的观测保留，不能用未测值填零。

| 浏览器 / 视口 | 核心 ready / 访问 | overflow | pageerror |
|---|---:|---:|---:|
| chromium / desktop | 43 / 44 | 0 | 0 |
| chromium / compact | 43 / 44 | 0 | 0 |
| chromium / phone | 43 / 44 | 0 | 0 |
| firefox / desktop | 43 / 44 | 0 | 0 |
| firefox / compact | 43 / 44 | 0 | 0 |
| firefox / phone | 43 / 44 | 0 | 0 |
| webkit / desktop | 43 / 44 | 0 | 0 |
| webkit / compact | 43 / 44 | 0 | 0 |
| webkit / phone | 43 / 44 | 0 | 0 |

未将 HTTP 404/503、错误提示或 skeleton 算作核心 ready；NotFound 的期望错误视图单独解释。触控目标候选、重复 URL、失败/取消、最大响应和 Resource Timing 在每页 JSON 中保留；自动候选不足以证明所有主要目标44×44或所有 presentation 互斥。

| 路由 | ready / 访问 | ready 最小–最大 ms | API 数范围 | 最大 raw 响应 B |
|---|---:|---:|---:|---:|
| `/` | 9 / 9 | 716.4–2186.2 | 7–7 | 9981 |
| `/analysis/stats` | 9 / 9 | 621.1–2879.1 | 7–7 | 205985 |
| `/analysis/charts` | 9 / 9 | 645.1–1689.8 | 7–7 | 100850 |
| `/analysis/records` | 9 / 9 | 683.1–2353.0 | 7–7 | 2096306 |
| `/billboard` | 9 / 9 | 742.4–1632.6 | 7–7 | 26317 |
| `/billboard/all-time` | 9 / 9 | 858.2–2080.4 | 7–7 | 598698 |
| `/billboard/number-ones` | 9 / 9 | 874.8–1739.2 | 7–7 | 215412 |
| `/billboard/year-end` | 9 / 9 | 788.0–1658.2 | 7–7 | 55943 |
| `/billboard/records` | 9 / 9 | 1037.1–1868.0 | 7–7 | 338692 |
| `/billboard/versus` | 9 / 9 | 781.8–1178.3 | 7–7 | 191634 |
| `/music/search?q=love` | 9 / 9 | 701.4–1931.0 | 8–8 | 4742 |
| `/yearly-review` | 9 / 9 | 839.0–2557.3 | 10–10 | 254891 |
| `/account` | 9 / 9 | 613.6–2372.6 | 9–11 | 11808 |
| `/community` | 9 / 9 | 627.9–1634.7 | 8–8 | 27140 |
| `/community/account/%40chartdata` | 9 / 9 | 619.7–1313.4 | 8–8 | 25430 |
| `/community/post/{post_id}` | 9 / 9 | 660.3–1401.8 | 8–8 | 2708 |
| `/settings` | 9 / 9 | 669.7–1086.1 | 6–7 | 989 |
| `/not-found-stage7` | 0 / 9 | 不适用 | 5–5 | 344 |
| `/music/tracks/{track_id}` | 9 / 9 | 713.3–1370.1 | 8–8 | 3283 |
| `/music/album-projects/{project_id}` | 9 / 9 | 701.7–1587.0 | 9–9 | 8152 |
| `/music/artists/{artist}` | 9 / 9 | 663.1–1977.0 | 8–8 | 52804 |
| `/account?section=journey` | 9 / 9 | 718.3–1750.3 | 11–13 | 11808 |
| `/account?section=cohorts` | 9 / 9 | 688.4–2990.7 | 12–13 | 11808 |
| `/account?section=relationships` | 9 / 9 | 701.3–2283.8 | 9–13 | 11808 |
| `/account?section=returns` | 9 / 9 | 735.4–1843.9 | 12–14 | 11808 |
| `/account?section=discovery` | 9 / 9 | 710.0–2292.6 | 12–14 | 11808 |
| `/account?section=library` | 9 / 9 | 732.3–1642.2 | 11–13 | 11808 |
| `/account?section=other-media` | 9 / 9 | 695.9–1723.7 | 11–13 | 11808 |
| `/analysis` | 9 / 9 | 967.0–1797.5 | 7–7 | 205985 |
| `/analysis/timeline` | 9 / 9 | 674.1–1724.9 | 7–7 | 205985 |
| `/analysis/leaderboard` | 9 / 9 | 734.2–1984.2 | 7–7 | 100850 |
| `/analysis/behavior` | 9 / 9 | 698.7–2822.9 | 7–7 | 205985 |
| `/analysis/listening-hours` | 9 / 9 | 713.7–2058.0 | 7–7 | 205985 |
| `/analysis/artists` | 9 / 9 | 787.1–7904.4 | 7–7 | 88278 |
| `/music/tracks/canonical/{track_id}` | 9 / 9 | 829.6–2295.2 | 8–8 | 3283 |
| `/music/tracks/l1/{track_id}` | 9 / 9 | 756.1–1455.8 | 8–8 | 3283 |
| `/billboard/track/{track_id}` | 9 / 9 | 745.8–1711.1 | 8–8 | 3283 |
| `/billboard/artist/{artist}` | 9 / 9 | 770.4–1645.3 | 8–8 | 52804 |
| `/settings?metadata=genre-language` | 9 / 9 | 744.6–2086.0 | 6–14 | 41865 |
| `/settings?metadata=track-credits` | 9 / 9 | 704.8–1599.8 | 6–10 | 26221 |
| `/settings?metadata=artist-identities` | 9 / 9 | 657.0–1424.1 | 6–9 | 18104 |
| `/settings?metadata=merge` | 9 / 9 | 944.4–1278.9 | 6–7 | 989 |
| `/music/albums/Lust%20For%20Life` | 9 / 9 | 679.2–2173.6 | 12–12 | 8188 |
| `/billboard/album/Lust%20For%20Life` | 9 / 9 | 741.0–1655.2 | 12–12 | 8188 |

API 数量按 started_requests 统计，包含被拦截的 POST；raw/wire 仅统计取得响应的请求。最大的单响应为播放记录约 2.10 MB；此处提供实测，未临时添加预算。原始探针的对决文字、Settings 归并首屏、Phone 搜索/年度/档案标题不匹配实际 presentation；仅修正探针并保留原记录。修正后的数据见 browser-corrections.json；Firefox Compact 竞争影响后整组复测见 browser-firefox-compact-retest.json。最初 Chromium Desktop 播放排行加载超时保留为瞬时失败，复测不等于产品已修复。
Phone 社区可见交互目标检出 40×40 头像及高度 16–20px 的链接/交互项；44×44 主触控验收未通过。年度页自动 prewarm POST 被只读拦截；本轮没有让其执行。无 AI 或外网调用的结论以 blocked/request 日志和外网 socket guard 为边界。
缺少完整控制清单、所有按需面板、完整 INP 及所有 presentation 互斥断言；专项浏览器不能替代未执行的默认完整 browser 阶段。

#### 补充交互与并发结果

| 浏览器 / 视口 | 完成检查数 | 错误 |
|---|---:|---|
| chromium / desktop | 5 / 5 | 无 |
| chromium / compact | 5 / 5 | 无 |
| chromium / phone | 5 / 5 | 无 |
| firefox / desktop | 3 / 5 | Timeout 12000ms exceeded. |
| firefox / compact | 3 / 5 | Timeout 12000ms exceeded. |
| firefox / phone | 3 / 5 | Timeout 12000ms exceeded. |
| webkit / desktop | 5 / 5 | 无 |
| webkit / compact | 5 / 5 | 无 |
| webkit / phone | 5 / 5 | 无 |

交互依次检查 Home LKG、详情页签、页签深链刷新、replace 历史下后退、自定义 period unavailable。Chromium/WebKit 六组合完成；Firefox 三组合停在后退检查，未伪装为通过。所选歌曲未入榜，页签验证的是有播放但无榜单成绩的真实空状态；不能替代所有实体的重型页签验收。

| 同 key 四并发 family | builder 次数 | 构建中 GET | 错误 |
|---|---:|---|---|
| analysis_records | 1 | {'status': 200, 'snapshot': {'status': 'warming', 'freshness': 'last_known_good', 'source_revision': '9aa35517d50a476dea41773a36373d2ffa52fb49d0731d5fd5a86f23a6e94a60', 'target_revision': '506fba0ae40e4f218d143c9d81564ea4f4de5e81bb3feee1eed65c675610594b', 'builder_version': 'analysis_records_v1', 'request_key': '418d5b567c6653f36af84f4f7ed870d3d7215a0d7d18866676b622c625c4e937'}} | 无 <!-- pragma: allowlist secret: published revision fingerprints --> |
| community | 1 | {'status': 200, 'snapshot': {'status': 'warming', 'freshness': 'last_known_good', 'source_revision': '75394da9e96945f23b47c38bd031a02d0f2618bb2e9d63b38e3678553cee04c2', 'target_revision': '9e3a087a7a58a7e01b0e6337c88fca5f94f9e6f69eff982101ec9d4ff93ea42d', 'request_key': '6df6668f7e88457a3277f26420494f59d23871edab65df09399f29caa2fe19db', 'builder_version': 'community_rows_v1', 'build_status': 'pending'}} | 无 <!-- pragma: allowlist secret: published revision fingerprints --> |
| archive | 1 | {'status': 200, 'snapshot': {'status': 'warming', 'freshness': 'last_known_good', 'source_revision': '374229a8b565aaaa0d1e59ffeccde5f8e96d922141f0a2951ee5afc307b6e2cd', 'target_revision': 'c227e2d1547475373d06b78adf4d20b9899376fbe36149a3b4f0865c49e8f649', 'request_key': '29320c4de9a7410ea61487e56a3aaaa3159eba8e8ba4d8d625a76aaf7c211e9e', 'builder_version': 'archive_shared_events_v1', 'build_status': 'pending'}} | 无 <!-- pragma: allowlist secret: published revision fingerprints --> |
| governance | 1 | {'status': 200, 'snapshot': {'family': 'genre_coverage', 'filter_fingerprint': '87232064c31543f88f22cc1741c38789c93ed1ef5613e30f6cc7bdb07d2fd96b', 'source_revision_vector': {'aliases': '399390aa021d4fa98b1f8009db009dbd:1', 'artists': '399390aa021d4fa98b1f8009db009dbd:1', 'attribution': '399390aa021d4fa98b1f8009db009dbd:1', 'duration': '399390aa021d4fa98b1f8009db009dbd:1', 'external_ids': '399390aa021d4fa98b1f8009db009dbd:1', 'genre_override': '399390aa021d4fa98b1f8009db009dbd:1', 'genre_sources': '399390aa021d4fa98b1f8009db009dbd:1', 'genre_spotify': '399390aa021d4fa98b1f8009db009dbd:1', 'identity': '399390aa021d4fa98b1f8009db009dbd:1', 'plays': '399390aa021d4fa98b1f8009db009dbd:1', 'tracks': '399390aa021d4fa98b1f8009db009dbd:1'}, 'rule_version': 'governance_health_coverage_v1', 'builder_version': 'governance_shared_duration_v1', 'publication_version': 'governance_result_v1', 'status': 'warming', 'freshness': 'last_known_good', 'source_revision': 'aafdf0e5d9afea52e380b1ecf0a4c496b4548ee5d1f77f0e4ecde5a7cee08728', 'target_revision': '3f7211c106509cda2dbffcc08d975ac219c174555512aaa0c1e8ff573879f201', 'checked_revision': 'aafdf0e5d9afea52e380b1ecf0a4c496b4548ee5d1f77f0e4ecde5a7cee08728', 'checked_at': '2026-09-20T08:21:53.949673+00:00', 'build_status': 'pending'}} | 无 <!-- pragma: allowlist secret: published revision fingerprints --> |

**状态预算未全过**：source drift 下 Analysis stats 的一次 LKG 首次读取为 523.639ms，超过 500ms，保留失败。第三次外部 Vitest 竞争的起始时刻无法精确定位，因此 missing 末段及四并发耗时保守不用于性能达标；其功能状态仍有效。48 次独立进程状态组、368 个样本保留在 state-http-matrix.json；缺失缓存目录最终未创建。
末尾目录/隔离修正的26项定向回归通过；这不覆盖、也不取消前面完整后端的10个失败。

### 部署、安全与标准门禁

- `bash deploy/production/validate-deployment-config.sh all` 通过 full/showcase/dual 的配置矩阵；Backend 无 ports，网关限定 loopback。Docker daemon 未运行，三模式容器运行态未验收。没有启动或修改域名、Tailscale、OAuth 或生产入口。
.dockerignore/镜像校验与 public allowlist/DB guard 由本轮 unit 验证；配置检查不替代实际构建镜像的内容验收。

| 标准命令 | 结果 | 时长秒 |
|---|---|---:|
| `.venv/bin/python scripts/fullstack_preflight.py` | PASS | 1.24 |
| `.venv/bin/pytest -m unit -q` | PASS | 159.12 |
| `.venv/bin/pytest -m contract -q` | PASS | 187.40 |
| `npm test` | PASS | 24.86 |
| `npm run build` | PASS | 8.33 |
| `python3 scripts/docs_audit.py` | PASS | 0.61 |
| `sh scripts/phase5_check.sh` | PASS | 267.38 |
| `git diff --check` | PASS | 0.06 |

首轮 unit 1902 passed，Phase 5 的 unit 1904 passed；完整 contract 437 passed；默认 npm test 657 passed / 4 skipped，85文件 passed / 1 skipped。定向修复另有15项隔离/CLI及11项探针回归。标准套件中的原有 skip 未删除或扩大。contract 的后台线程警告保留在日志，不伪装成零警告。

| 默认完整轮次 | 阶段 | 结果 | 秒 |
|---|---|---|---:|
| fullstack-attempt1-summary.json | preflight | PASS | 15.680 |
| fullstack-attempt1-summary.json | quality | FAIL | 38.475 |
| fullstack-attempt1-summary.json | backend | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | api | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | browser-routes | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | browser-interactions | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | browser-inventory | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | browser-compat | NOT_RUN | 0.000 |
| fullstack-attempt1-summary.json | optional | NOT_RUN | 0.000 |
| fullstack-summary.json | preflight | PASS | 8.360 |
| fullstack-summary.json | quality | PASS | 76.214 |
| fullstack-summary.json | backend | FAIL | 1279.791 |
| fullstack-summary.json | api | NOT_RUN | 0.000 |
| fullstack-summary.json | browser-routes | NOT_RUN | 0.000 |
| fullstack-summary.json | browser-interactions | NOT_RUN | 0.000 |
| fullstack-summary.json | browser-inventory | NOT_RUN | 0.000 |
| fullstack-summary.json | browser-compat | NOT_RUN | 0.000 |
| fullstack-summary.json | optional | NOT_RUN | 0.000 |

原始 summary、run-id、阶段日志和命令保存在证据目录。第一轮 quality 失败后完成必要格式/类型修复才运行第二轮；第二轮后端失败后未再重复完整门禁。

默认完整后端结果：**10 failed, 2981 passed, 3 skipped**（1266.84 秒）。失败包括 Analysis lifetime 未私有发布、custom period 的旧 200 断言；tracked seed 缺 migration 75/76；Search migration 测试硬编码 74；六个启动维护测试因 Archive revision schema 不再匹配而失败。标准 `-m unit` 并未包含这些全部位于 unit 目录下的测试，不能用前面的 1904 passed 抹去完整套件失败。详见 `fullstack.log`。

### 正式数据、磁盘与 Git

完整后端待修复测试：

- `backend/tests/integration/test_analysis_api.py::TestAnalysisStats::test_stats_lifetime_structure`
- `backend/tests/integration/test_analysis_api.py::TestAnalysisStats::test_stats_custom_empty_range_returns_zero_shape`
- `backend/tests/unit/test_migrations.py::test_tracked_seed_matches_current_schema_contract`
- `backend/tests/unit/test_music_search_incremental_migration.py::test_latest_schema_version_matches_registered_migrations`
- `backend/tests/unit/test_music_search_startup.py::test_import_maintenance_recovery_is_registered_and_scanned_before_search_startup[False-False]`
- `backend/tests/unit/test_music_search_startup.py::test_import_maintenance_recovery_is_registered_and_scanned_before_search_startup[True-True]`
- `backend/tests/unit/test_music_search_startup.py::test_track_credit_startup_recovery_targets_latest_revision[credit_state0-True]`
- `backend/tests/unit/test_music_search_startup.py::test_track_credit_startup_recovery_targets_latest_revision[credit_state1-True]`
- `backend/tests/unit/test_music_search_startup.py::test_track_credit_startup_recovery_targets_latest_revision[credit_state2-True]`
- `backend/tests/unit/test_music_search_startup.py::test_track_credit_startup_recovery_targets_latest_revision[credit_state3-False]`

**严格的整个 data 目录完全不变证明未成立。** 4,183 个文件总大小 1,501,840,662 B 未变；只有 `data/.DS_Store` 内容 SHA 改变（mtime 为 16:31:34），未确认写入者，未写回恢复。`data/spotify_stats.db-shm` 仅 mtime 改变、内容 SHA 相同。其余 4,182 个文件，包括主库和正式 sidecar，内容 SHA 全部相同。完整逐文件证据见 formal-before.json / formal-after.json / formal-comparison.json。

正式侧存只读清单（原 SHA 与终 SHA 一致后，以 immutable 只读补取结构状态；不是新增维护）：

| 正式文件 | 字节 |
|---|---:|
| `data/billboard_cache.db` | 2260992 |
| `data/yearly_review_cache.db` | 4218880 |
| `data/cache/home-overview/` | 63837 |

隔离副本的 sidecar/Home 合计 **11,381,831 B**；含 fullstack 探针的 Home 镜像目录。主库单列，不计入 sidecar 总量。active/previous 指针、raw/stored 字节、SQLite freelist 见 sidecars-final.json。

| 隔离文件 | 字节 |
|---|---:|
| `data/analysis.db` | 307200 |
| `data/archive.build.lock` | 0 |
| `data/archive.db` | 45056 |
| `data/billboard.db` | 2351104 |
| `data/billboard.db-shm` | 32768 |
| `data/billboard.db-wal` | 0 |
| `data/cache/home-overview/14d811432b85a0c02be5823f1359069776deac961e7194c1089847f3fac83af5.json` | 9969 |
| `data/cache/home-overview/lkg-home-facts-v4-f4f9377ee76616039acbd6b9440de0bb01249ccfbaa78e9637d9de6f8d10250f.json` | 9969 |
| `data/community.build.lock` | 0 |
| `data/community.db` | 8253440 |
| `data/governance.build.lock` | 0 |
| `data/governance.db` | 167936 |
| `data/home/14d811432b85a0c02be5823f1359069776deac961e7194c1089847f3fac83af5.json` | 9969 |
| `data/home/d89fe8b2bfafb8f1855c83081e86157ec6214dce357919e16f58fa4b7c163d37.json` | 9146 |
| `data/home/lkg-home-facts-v4-f4f9377ee76616039acbd6b9440de0bb01249ccfbaa78e9637d9de6f8d10250f.json` | 9146 |
| `data/main.db` | 444588032 |
| `data/main.db-shm` | 32768 |
| `data/main.db-wal` | 0 |
| `data/yearly_review_cache.db` | 176128 |

起点到终点的仓库文件增量共 42 项，HEAD 未变，暂存区为空。stage7.patch 以本轮开始的 dirty 文件内容为基准，不以 HEAD 代替起点；changed-python-ast.json 分离纯格式变化。

| 文件 | 增量类型 |
|---|---|
| `backend/api/analysis.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/api/import_.py` | changed |
| `backend/core/job_queue.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/core/migrations.py` | changed |
| `backend/domains/account_archive/overview.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/domains/music_search/snapshot_delta.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/main.py` | changed |
| `backend/models/analysis.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/services/analysis_snapshot_service.py` | changed |
| `backend/services/music_search_maintenance_service.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/conftest.py` | changed |
| `backend/tests/contract/test_api_boundary_probe.py` | changed |
| `backend/tests/contract/test_api_contract.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/contract/test_api_smoke_probe.py` | changed |
| `backend/tests/contract/test_artist_genre_metadata_api.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/contract/test_artist_language_metadata_api.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/contract/test_import_api_jobs.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/integration/test_community_api.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/path_safety.py` | changed |
| `backend/tests/unit/test_account_archive_discovery.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/unit/test_account_archive_other_media.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/unit/test_account_archive_relationships.py` | changed |
| `backend/tests/unit/test_analysis_snapshots.py` | changed |
| `backend/tests/unit/test_derived_cache_isolation.py` | changed |
| `backend/tests/unit/test_feed_generator.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/unit/test_frontend_web_vitals_probe_script.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/unit/test_music_search_snapshot.py` | 纯格式，AST 与阶段7起点相同 |
| `backend/tests/unit/test_music_search_snapshot_week_delta.py` | changed |
| `backend/tests/unit/test_performance_contract.py` | changed |
| `backend/tests/unit/test_snapshot_rebuild_cli.py` | added |
| `backend/tests/unit/test_track_identity.py` | 纯格式，AST 与阶段7起点相同 |
| `docs/README.md` | changed |
| `docs/reference/analysis-result-snapshots.md` | changed |
| `docs/reference/backend-test-isolation.md` | changed |
| `docs/reference/fullstack-verification.md` | changed |
| `docs/reference/public-snapshot-read-contract.md` | changed |
| `docs/reports/2026-09-20-stage7-performance-checkpoints.md` | added |
| `docs/reports/README.md` | changed |
| `scripts/benchmark_api.py` | changed |
| `scripts/performance_catalog.py` | changed |
| `scripts/rebuild_account_archive.py` | changed |
| `scripts/rebuild_governance.py` | changed |

本轮专用 8000/5173 服务已停止，性能锁已释放；其他项目服务未终止。未实现的全 family 故障、正常 lifespan 重启、全部复杂面板和 Docker 运行态验证是验收阻塞，不列为非阻塞尾项。原有 urllib3/后台线程警告保留原日志；没有以告警清理扩大本轮范围。

完整起点与终点清单、SHA、暂存内容、精确阶段7 patch 位于证据目录。保留原 dirty worktree；hook 的格式增量与逻辑改动分开记录。

### 剩余阻塞与下一步

本轮不能收口为 Pass。剩余阻塞以最终 fullstack、浏览器和状态文件为准；Home 重启 key、Records 重建预算、Analysis stats LKG 冷读超时、Firefox 后退检查、触控目标尺寸、年度维护状态/艺人排名的 warm 延迟及三模式容器运行态缺口已经确认。完整矩阵中的未覆盖状态不得视作通过；data/.DS_Store 的内容变化还使全目录严格不变证明未成立。

下一条修复 Prompt：

> 仅修复阶段7报告列出的失败：先处理最终完整套件的 Analysis 集成契约与真实私有发布缺口、seed/schema 版本同步和六个 Archive 启动 revision 失败，保留原 builder 空范围语义对账并验证前端 unavailable；修复 Home 持久 key 的进程内 revision 依赖；针对已保留的性能/浏览器失败做最小修复。使用同一真实 Online Backup、独占性能时窗和三浏览器三视口，补齐缺失状态矩阵与本地三部署模式运行证据，最后运行一次默认完整 fullstack。不得放宽预算、恢复 GET 冷建或把错误页算 ready，不改正式 data；测量期间不改变 HEAD。验收完成后仅对归属明确、可独立构建测试的完成成果按补充授权进行本地 scoped commit，禁止 push/部署/数据同步。

本地结果不代表生产验收。测量结束时收到补充授权：大阶段完成且归属可靠后可做本地 scoped commit，仍禁止 push/部署/数据同步。本轮 HEAD 全程未变；阶段7失败项及跨阶段 hunk 归属尚未收口，因此本次不提交未完成状态。交付本报告后停止。

## 阶段 7B：验收阻塞修复与本地收口（Partial）

原记录：`2026-09-20-stage7b-performance-closeout.md`。

### 结论与边界

本轮结论为 **Partial**。Records 最终三个独立进程的 cold builder 为 10.110869、9.652281、12.245321 秒，中位数 **10.110869 秒**，没有达到 ≤10 秒门槛。三次完整 payload 与优化前一致，仅排除 `meta.generated_at`。不能将 10.111 秒取整为 10 秒并判 Pass。Analysis LKG、艺人冷读取和未发布配置的返回耗时也尚未全部达标，故障 UI 与实际并发矩阵仍有缺口。

定向门禁尚未全通过，因此没有启动本轮标准全量测试序列、最终默认完整 fullstack 或 Git 提交。阶段 7 的完整后端失败不能凭本轮定向测试改写为“完整后端 0 failed”。未 push、未部署、未同步正式数据。

按本轮追加指示，Docker full/showcase/dual 运行态验收移至独立的发布前任务，**不属于 7B Pass 门禁，也不作为本轮 Blocked 或产品缺陷**。撤出之前执行过 `open -a Docker`、`docker info` 和只读镜像列表；没有启动 SpotifyStats 容器。收到指示后没有继续 Docker 构建、拉取、Compose、创建或删除操作，也没有关闭 Docker Desktop 或改动既有对象。

起点 HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`。起点工作区与阶段 7 结束状态逐文件一致，已暂存区为空。既有约 270 个阶段文件继续保留；本轮只在该基础上修复已确认阻塞。

### 证据位置

本轮证据根目录：

`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bdd8-b911-7b33-b062-c94e7b068598/spotifystats-stage7b`

隔离数据库和运行脚本位于 `/tmp/spotifystats-stage7b`。正式数据库经 SQLite Online Backup 生成副本；性能样本使用新的 Python 进程及独立空目标 sidecar。性能任务使用同一个主机文件锁，但其他项目没有共同使用该锁，因此进程证据是判定样本有效性的必要部分。

复用 [阶段 7 报告](#阶段-7全路由性能验收与本地收口) 的有效 396 次路由访问及既有合同证据，没有重跑该整套矩阵。阶段 7 的 fullstack 结果仍为历史结果。

### 已实现的修复

- Archive tracking marker 改为自身合同版本与触发器定义指纹，migration 77 负责升级。无关 DDL 不再让 Archive 失效；缺失 marker/trigger 的私有修复更新 epoch，事务回滚保留原数据。正常 lifespan 在迁移后检查 tracking。
- tracked seed 通过正式 migration 从 74 升至 77；源事实表逐表对账不变，完整 migration 序列及 integrity check 保存在 `seed-upgrade.json`。Search 测试移除 schema 74 硬编码。
- Analysis lifetime 集成测试通过真实私有 fixture 发布快照。未发布 custom GET 保持 503，并单独调用私有 builder 验证真实空范围的零值结构。
- Home exact key 使用 Billboard `full_data` 持久发布的 cache-key 与内容摘要，移除进程内 preview 计数依赖。
- Records 优化小时区间切片、longevity 连续区间计算、重复 feat 名称判断、skip 分组聚合，以及只添加列时的数据表复制；保留事件/时长双轨、原排序和 L2/L3 归属。
- 年度 artifact 私有发布保存 preparation-key 元数据；generation-status 优先只读查 key，避免重复收集每年的完整 scoped digest。旧 sidecar 的元数据补齐仍属于私有维护。
- 艺人 rank context 复用既有 Analysis store 的私有发布；全局竞赛排名、Top 250 和最近 50 个逻辑事件只维护一次。实体详情和榜单按目标艺人装载事实，保留完整字段；缺失/漂移返回 unavailable，GET 不补建。
- Phone Community 头像与主要操作扩大到 44px 点击区；年度总结五个筛选按钮从 40px 调整为 44px。

曾尝试缩小 Records 封面解析集合，完整对账发现一条每日纪录的封面发生变化，因此已撤掉该项优化。失败样本和差异证据保留，最终三次对账均为完整相等。

### 定向测试

| 范围 | 结果 | 日志 |
|---|---:|---|
| 阶段 7 原十个失败 ID，真实数据副本 | 10 passed | `original-ten.log` |
| Archive / Governance revision | 54 passed | `revision-tests.log` |
| migration / startup / Home | 56 passed | `migration-home-tests.log` |
| Records / yearly 首轮定向 | 59 passed | `records-yearly-tests.log` |
| rank / yearly / startup 后续回归 | 66 passed | `rank-yearly-tests.log` |
| Search 合同与受影响边界 | 94 passed | `changed-contracts.log` |
| 最终 Records 等定向与 Analysis 集成组合 | 86 passed、3 failed | `records-analysis-final-tests.log` |
| 上述 Analysis 集成改用真实 Online Backup 副本 | 10 passed | `analysis-integration-real-copy.log` |
| 最终 rank revision / CLI / Home / yearly / Records 定向 | 60 passed | `final-directed.log` |

组合测试中的三项失败源于误用小型 seed：数据规模断言要求超过 50,000 次播放，seed 只有 118 个有效事件。未降低断言；随后指定 `SPOTIFY_STATS_TEST_SOURCE_DB` 为隔离真实副本，整个 Analysis 集成文件通过。原失败日志保留。

一次早期组合定向进程在 59 个进度点后退出 139（Python segmentation fault），保存在 `directed-backend.log`；后续拆分定向组通过。另一次 snapshot 队列测试发现 rank job 被耦合进两类 Analysis 的 enqueue，已改为 main 启动/已提交变更处独立排队，后续 66 项通过。以上都没有被记为最终完整后端通过。

### 性能证据

| 项目 | 本轮有效结论 |
|---|---|
| Home restart exact | 三个新进程均为相同 exact generation：96.867 / 91.574 / 92.356ms；见 `cold-http.json` |
| Records cold builder | before median 13.348972 秒；最终 median 10.110869 秒，**不通过**；见 `records-final-acceptance.json` |
| 年度 generation-status | 最终三个新进程冷读取 299.637 / 346.752 / 336.041ms，热读取 287.315 / 274.045 / 274.615ms，全部 ≤500ms；见 `final-http.json` |
| 艺人 stats + rank context / rankings | 完整字段相等；不带观测器的 stats 冷读取 696.993 / 609.539 / 742.297ms；rankings 480.590 / 533.825 / 555.466ms，未全部 ≤500ms |
| Analysis LKG / 真实故障读取 | 不带观测器的 LKG 首读 579.676 / 445.240 / 450.916ms，未全部 ≤500ms；未发布参数 Stats / Records 冷读 439.988 / 440.579ms，超过 300ms |

观测器本身会影响时延，最终另以不带 SQL/row 计数器的真实 HTTP 进程交叉验证，数据保存在 `plain-http.json`，没有把纯 service 时长替代 HTTP。上述未达标项在不带观测器时仍存在；公开只读行为使用带观测器及 sentinel 的独立证据验证。Stats LKG profile 的 491.450ms 中，source revision 收集占 486ms，sidecar 读取约 3ms；Pydantic 验证 2.216ms、序列化 1.339ms，主要成本仍是 28 张依赖表的完整指纹读取。见 `stats-lkg-final-profile.json` / `.txt`。

`records-final-acceptance.json` 与 `records-isolated-{1,2,3}-processes-{before,after}.txt` 保存最终 Records 原始样本和进程环境；`records-*-profile-profile.txt` 保存 profile。空目标 sidecar 不等于 SQLite 页缓存或操作系统磁盘缓存为空，本轮没有清理全机缓存。

外部资源竞争已直接观测到另一项目 pytest、Vitest、vue-tsc 和后续 Playwright workers。`records-quiet` 只是运行标签，其开始/结束仍有该项目 worker，不能当作独占证据。`performance-exclusion.json` 列出排除范围，失败数据未删除。外部 Playwright 总进程结束后才采集最终 `records-isolated` 三次样本。

### 真实浏览器与状态

Firefox 的历史断点来自本机 Playwright/Firefox 的协议 reload：`page.reload()` 新增同 URL 历史项且丢失 `history.state`，没有观察到应用额外 push。使用浏览器原生 `location.reload()` 后保留历史；三种引擎统一采用相同原生刷新流程。

Chromium / Firefox / WebKit × Desktop / Compact / Phone 的 9 组交互均完成：从首页真实实体链接进入详情、非默认页签 replace、深链刷新、后退回首页、前进恢复页签与内容，以及未发布 custom 范围错误消费。没有通过跳过引擎或只断言 URL 取得通过。原协议失败、诊断和最终完整流程分别保存在 `browser-interactions-protocol.json`、`firefox-history-diagnostic.json`、`browser-interactions.json`。

Phone 390×844 的 Community、Analysis stats、Archive、Search、Yearly Review、Home 可见主要按钮/页签/导航几何检查均无小于 44px 的目标，无横向溢出。真实点击包括头像入口、社区时间筛选、年度章节选择和完整榜单翻页。证据为 `phone-controls.json`、`phone-actions.json` 与 screenshots；正文内联链接未机械放大。

追加状态证据见 `state-http-additional.json`、`state-http-remainder.json` 及对应 browser/payload 文件。Home、Stats、Records、Billboard、Search、Community、Archive、Governance、Yearly 使用各自真实读取路径。Yearly 未发布返回原合同的 404，Search 可返回 200 + unavailable/failed statistics metadata；这些均不算 ready。

矩阵的初次 Search config 探针错误传入 candidates 不支持的 `min_ms`，422 只证明参数拒绝，不算 config drift。初次 Search source drift 没同步 import-owned Search counter，ready 也不算漂移证明；纠正记录见 `search-source-fault-correction.json`。初次 fault UI 采用全站 networkidle，被年度维护状态轮询阻塞；该轮不算完整 UI 通过。追加探针显式区分 public/private surface，保留这些失败，不覆盖为通过。

正常 lifespan 已运行并重启两次，启用 L3 启动检查，关闭外部 warmup / Search 自动重建；隔离副本中继承的 pending/running/failed 外部任务及失败封面重试标记先移出本轮运行，详情见 `lifespan-private-copy-preparation.json`。两次 health、Home、Stats、Archive 均返回 200，Home 为同一 exact generation。第一次因测试恢复数据库引起 Governance 全局 schema cookie 变化，启动修复后后台维护 Governance；第二次没有待运行任务。第一次 Stats 读取与后台维护重叠为 1544.683ms，不算独占性能通过。见 `lifespan.json`。

追加故障 HTTP 20 项全部完成，观测的 builder/write/enqueue 均为零。故障 UI 证据仍不完整：首轮 networkidle 被轮询阻塞；后续通用文本长度等待既捕获过未完成的 Search/Yearly 加载画面，又在短错误文案页面超时。这些截图只作诊断，不证明对应消费者通过。Phone 重试点击、治理面板实际展开、Search 真正 config drift 和未污染的实际四并发样本仍需补齐。

### 正式数据、Git 与剩余门禁

正式数据最终对账：**4172 个 application 文件大小与 SHA-256 全部不变，元数据也不变**；9 个 SQLite 瞬态文件内容不变，仅 `data/spotify_stats.db-shm` 的 mtime 变化；2 个 OS 元数据文件内容与元数据均不变。汇总见 `formal-summary.json`。

正式文件按照 application、sqlite_transient、os_metadata 三类建立 `formal-before.json` / `formal-after.json`。主库、sidecar、备份、封面、缓存和清单按大小与 SHA-256 对账；WAL/SHM/journal 与 `.DS_Store` 单列。没有主动改写、删除或恢复 `.DS_Store`。

最终 Git：仍在 `main`，HEAD 保持 `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`；相对本地缓存的 `origin/main` 为 ahead 0 / behind 0（本轮未联网 fetch）。staged 为空，工作区 274 项状态；相对 7B 起点变化 40 个文件，逐文件与 patch 见 `stage7b-changes.json` / `stage7b.patch`。本轮启动的 8000 后端与 5173 前端已停止；Docker Desktop 保持用户要求的现状。

文档审计 PASS（117 个当前 Markdown），受影响代码 Ruff 检查、`git diff --check` 与空 staged 的 `git diff --cached --check` 通过。这些局部质量检查不替代标准完整门禁。

本轮没有 commit，阶段归属提交表尚未进入执行；未达到 Pass 时不得为凑齐 4–7 个提交而暂存或提交。最终 HEAD、staged 状态、完整剩余文件和 origin ahead/behind 见 `git-final.json`、`status-final.txt`。README 无产品入口变化；AGENTS 与 CLAUDE 保持一致；本轮更新规则、变更日志与文档地图。

最终仍需先关闭 Records ≤10 秒与其他未通过的定向性能/状态门槛，再按用户指定顺序执行标准 unit、contract、完整后端、默认 npm test、build、docs audit、phase5、diff check 和一次默认完整 fullstack。只有全部通过后才整理大阶段本地提交及 all-files hooks。Docker 三模式验收独立留给未来发布前任务。

## 阶段 7C：Git 检查点、性能阻塞收口与本地全栈验收（Partial）

原记录：`2026-09-20-stage7c-checkpoints-performance-acceptance.md`。

### 当前结论

**阶段 7C Partial**。四个已完成阶段的本地检查点提交已保留。Records、Analysis LKG、艺人统计/排名、unavailable、18 项最终故障 UI、四并发及全部标准门禁通过；唯一一次默认完整 fullstack 在 API 基准阶段失败：`/api/import/preflight` hot P95 **5175.24 ms > 500 ms**。四个浏览器阶段均未执行。按本轮停止条件，没有继续修复该接口或重跑整轮。

最小剩余阻塞是 import preflight 的全栈性能门槛，以及该失败后尚未执行的默认浏览器阶段。7C 的新实现与报告保留为未提交改动；不回退四个已完成的本地提交。

### 本地检查点

起点为 `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`，初始 274 项状态与 7B 终点逐文件一致。完整归属表、初始 patch、每次 cached patch / name-status / stat / hooks 日志保存在证据目录。共拆为四组；共享 migration、main、job queue、API/消费者和生成类型存在依赖，读模型组统一落地，未为了数量拆成不可构建的中间状态。

| SHA | message | 阶段与范围 |
|---|---|---|
| `8cfb337448eb8b80faaaf941bc85c38c89a46cd5` | perf(infra): 统一性能测量与验证合同 | 阶段 0、7 探针合同、脚本、测试与文档 |
| `8448d2cc316d927c4b1f69dd56d9d41176bc7782` | perf(billboard): 收口公开快照投影与榜单重建 | 阶段 1/2A/4A/4B、7B Home、对应 OpenAPI/TS |
| `60e394a1fc4cd850e20fe5cc291794c04834e379` | perf(search): 共享多变体构建与增量维护 | 阶段 5A/5B/5C、identity no-op、Search 合同 |
| `107594909cab25ce20d87b88522f4ef3c55e1bb6` | perf(read-models): 持久化分析及档案治理读模型 | 0.5/2B/3A–3C/6A–6C/7/7B、migration 74–77/seed、实体与年度 |

全部使用明确路径或可审计的 cached patch，hooks 通过；未 amend、rebase 或 push。组 2 从暂存树生成自己的 OpenAPI 与 TS，并独立通过 tsc 和 27 项定向测试。四组结束时工作区曾完全 clean，当前修改只属于 7C。

提交基线：unit 1914 passed，contract（真实 Online Backup source）437 passed，前端 657 passed / 4 skipped，build、docs audit、diff check 通过。首轮副本 WAL 只读初始化失败、一次误把整个真实副本用于普通 unit 后主动中断，以及 contract 的六条 warning 均保留在原始日志；它们没有被改写为通过记录。

### 性能原始样本

Records 使用三个独立新进程，每次目标 sidecar 不存在：**9.824068583 / 9.512222250 / 10.429251333 秒**，median **9.824068583 秒 ≤10 秒**。第三次超过 10 秒仍保留；门槛作用于 median。三个完整 payload 与当前正确 builder 逐字段相等，仅排除 `meta.generated_at`。本轮没有修改 Records 算法，达到门槛即停止；测量在检查点提交后、revision 迁移前完成。

下表为不带 SQL 观测器的真实 loopback HTTP，新服务进程健康就绪后首个目标请求；不包含启动耗时，不清空操作系统页缓存，不把这三次称为稳定 P95。每次 PID、参数、响应、原始耗时和进程列表均保留。

| 目标 | 三次首读原始值（ms） | 门槛 |
|---|---|---|
| artist-stats | 391.440750000 / 379.677334000 / 376.826666000 | 500 ms，每次通过 |
| artist-rankings | 246.135625000 / 254.198833000 / 248.774000000 | 500 ms，每次通过 |
| stats-lkg | 16.086750000 / 15.997667000 / 15.804083000 | 500 ms，每次通过 |
| stats-config-missing | 8.732834000 / 8.472875000 / 10.696625000 | 300 ms，每次通过 |
| records-config-missing | 10.546625000 / 11.882791000 / 9.556125000 | 300 ms，每次通过 |

艺人读取继续复用已发布 Analysis artist rank context，共享全局排名、Top 250 与最近逻辑事件；本轮未修改艺人统计算法和字段。基础 stats 不自动加载 rank context，缺失/漂移 GET 不补建，相关完整字段和竞赛排名合同由定向测试核验。

### 7C 实现

Analysis source revision 原来逐请求对事实表进行全量读取与 repr 指纹；migration 78 改为持久表级 epoch/counter，由源表 INSERT/DELETE/语义 UPDATE 同事务维护。公开 GET 校验触发器完整 DDL、版本标记、依赖表集合与计数，然后读取版本向量。`PRAGMA data_version` 只作并发提交 fence；文件 device/inode 只作副本命名空间，均不冒充语义 revision。

显示、审计字段、无变化 UPDATE 和未批准的流派/语言记录不使对应事实失效；批准状态转换、真实源值修改、删除均被追踪。触发器丢失、schema 合同改变或计数缺失时拒绝公开读取，由私有 migration/startup 修复并更换 epoch；不在 GET 安装或修复。seed 同步到 78，123 张非跟踪业务表与迁移前相等，integrity_check 为 ok。

exact、LKG、source/config/builder drift、损坏 active、无 LKG、失败不替换 active、事务回滚和并发提交仍按原合同处理；公开 HTTP 另带观测器核验 builder/write/enqueue 均为零；最终定向测试为 72 passed。

### 状态、并发与真实 UI

- 四组同 key 四并发：Records、Community、Archive、Governance 各 **builder_calls=1**。四个调用共用受控 barrier，主机级锁期间无其他本轮测试进程；构建期间公开读取原 LKG，失败未替换 active。原始结果与前后进程列表见 `concurrency.json` 和对应 processes 文件。
- Search config drift 修改隔离副本中的真实默认 `bb_week_start_hour`，候选与 context 均为 **200 + stale / last_known_good statistics**，目标与实际服务的 filter fingerprint 明确不同，不是 422。参数、前后 payload 与零写入观测保留在 `state-final/state7c.json`。
- 对 Home、Stats、Records、Billboard、Search、Community、Archive、Governance、Yearly 注入真实私有 builder 异常，分别检查存在历史发布与空 sidecar。最终 UI 为 8 类 Phone ×2 状态，加桌面 Governance ×2 状态。Yearly 采用严格 exact 发布合同，源漂移即使留有旧产物仍为 404，消费者最终显示“报告加载失败”，没有把它视为 ready 或 LKG。
- Phone Community 的 `Retry` 实际点击，触控区不小于 44×44，再次收到 503 后回到明确错误态；各 Phone 页面 scrollWidth=clientWidth=390。Governance 在桌面真实收合、展开“音乐源数据管理”，再点击“流派与语言”，分别显示上次检查结果及失败提示。
- 所有导航使用 DOMContentLoaded、明确文本/API 或可见控件等待，没有 networkidle。脚本阻断外部连接与写方法，不触发外部服务。截图已核查。

诊断记录没有覆盖：并发脚本的恢复路径被 exec 局部变量覆盖，四组测量已完成，之后单独使用 Online Backup 恢复临时副本；首轮故障注入受恢复后 Governance schema cookie 影响；随后探针恢复旧计数时与此前并发 generation 相撞，Records/Archive 成为 exact，该轮不算漂移通过。最终探针用多次独立源写入推进计数，并先做副本私有 revision 修复。Phone 设置页仅提供“电脑端管理”入口，无法展开桌面治理面板的两条超时保留，桌面补测另存 `governance-final/`。没有重跑已通过的 396 次路由矩阵。

### 最终门禁

| 门禁 | 结果 | 命令墙钟秒数 |
|---|---|---|
| unit | 1916 passed / 1089 deselected | 75.199129 |
| contract | 437 passed / 2568 deselected / 6 warnings | 255.406326 |
| backend-all | 3002 passed / 3 skipped / 8 warnings | 1342.718036 |
| frontend-test | 657 passed / 4 skipped；85 files passed / 1 skipped | 44.885762 |
| frontend-build | Pass | 9.624772 |
| docs | Pass，118 篇当前 Markdown | 0.929322 |
| phase5 | Pass；unit 1914 passed / 2 skipped，contract 437 passed；前端与 build 通过 | 349.473940 |
| diff | Pass | 0.064785 |

命令严格按上述顺序运行；完整 backend 使用 Online Backup source，unit/contract/Phase 5 使用项目默认 seed。完整后端 pytest 自报 1333.07 秒，表中为父命令含退出清理的墙钟耗时。离线环境关闭 `.env` 后，Genius 客户端不可用，触发原有三个条件跳过（两项 unit 文本清理、一项 integration）；这两项 unit 在前面的标准 unit 中已通过。没有修改或放宽用例。

完整后端第一次启动未继承 socket 外网阻断环境，已中断并保留 `final-backend-all.log` 与 `backend-initial-interruption.json`，随后从该阶段继续完整执行；最终日志为 `final-backend-all-offline.log`。warning 涉及 LibreSSL、弃用和测试线程清理/源 fence，均保留，未描述为无 warning。全文件 pre-commit（Ruff/format/mypy/secrets）及新增报告的文件 hooks 均通过。

| 默认完整 fullstack 阶段 | 结果 | duration_ms |
|---|---|---|
| preflight | PASS | 8180 |
| quality | PASS | 69351 |
| backend | PASS | 1117655 |
| api | FAIL | 284243 |
| browser-routes | NOT_RUN | 0 |
| browser-interactions | NOT_RUN | 0 |
| browser-inventory | NOT_RUN | 0 |
| browser-compat | NOT_RUN | 0 |
| optional | NOT_RUN | 0 |

运行 ID：`20260920T123340.940443Z-f146fe5cd6b8`；selection=full，整体 **FAIL**，总耗时 **1479632 ms**，退出码 1。preflight、quality 和完整 backend 通过；该 backend 为 **3002 passed / 3 skipped / 9 warnings，pytest 1107.87 秒**。API smoke 与参数边界通过，基准目录共 51 个目标，唯一慢项为 `/api/import/preflight`。

该接口 22 次均返回 HTTP 200。首个观测请求为 4777.095 ms，进程状态标记 unknown；其后 21 次同进程请求 min 4480.897 ms、median 4763.007 ms、P95 **5175.24 ms**、max 5187.615 ms。阈值保持 500 ms，未降低并发、未放宽用例或 timeout，未增加固定 sleep；未使用 `--only` / `--from`。浏览器阶段因 API 失败未到达，不能声称 Chromium/Firefox/WebKit 本轮默认门禁通过。

所有 22 次原始样本与其余 50 个目标保留在 `fullstack-run/api-benchmark.json`；兼容摘要为 `fullstack-summary.json`，完整 run-scoped 目录已复制到 `fullstack-run/`。只运行了这一轮 fullstack。Docker 不属于本轮门禁。

### Git、数据与证据

最终 HEAD 为 `107594909cab25ce20d87b88522f4ef3c55e1bb6`，相对本地缓存的 origin/main ahead 4 / behind 0；未联网 fetch。最终全栈门禁未通过，因此 7C 实现与报告不满足本轮新增提交条件，全部保留未提交；暂存区为空。

全部真实数据操作限于由 SQLite Online Backup 创建的 `/tmp/spotifystats-stage7c/data/main.db` 及对应临时 sidecar。正式数据 **4183 / 4183 文件 size 与 SHA-256 全部一致**：4172 个应用数据文件、9 个 SQLite 临时文件、2 个 `.DS_Store`；无新增、删除或内容变化。唯一 mtime 变化为 `data/spotify_stats.db-shm`，其大小与 SHA-256 相同，未尝试回写或恢复正式文件。逐文件清单与对账见 `formal-before.json`、`formal-after.json`、`formal-diff.json`。未 push、未部署、未同步正式数据、未执行任何 Docker 操作、未调用 AI/LLM 或 Spotify 等外部服务。

剩余未提交范围共 10 项（9 个已跟踪修改、1 个新增报告），没有无法归属的历史 hunk：

| 路径 | 7C 范围 |
|---|---|
| `backend/core/migrations.py` | migration 78 与注册 |
| `backend/main.py` | 私有启动时安装/修复 Analysis revision |
| `backend/services/analysis_snapshot_revision.py` | 事务触发器、持久版本向量与只读合同检查 |
| `backend/tests/fixtures/seed.db` | seed 同步 schema 78 |
| `backend/tests/unit/test_analysis_snapshots.py` | 语义漂移、rollback、缺损追踪与并发 fence 测试 |
| `docs/reference/analysis-result-snapshots.md` | 当前 revision 合同 |
| `docs/CHANGELOG.md` | 7C 实现与 Partial 状态 |
| `docs/README.md` | 新报告入口 |
| `docs/reports/README.md` | 新报告索引 |
| `docs/reports/2026-09-20-stage7-performance-checkpoints.md` | 本报告 |

README 无需新增入口说明；AGENTS/CLAUDE 仍一致，未修改。全文件 hooks、diff check、status 和 log 已执行，结果保存在对应日志。最终 Git 信息见 `git-final.json`、`git-status-final.txt`、`git-log-final.txt`。本轮创建的 8000 后端与 5173 前端进程已停止；未改变用户的 Docker Desktop 状态。

证据根目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0be86-06d0-7b51-b1ad-8a3f70c1a9ee/spotifystats-stage7c`。主要文件：`baseline.json`、`formal-before.json`、`checkpoint-ownership.md`、`checkpoint-*-cached.patch`、`records-checkpoint-acceptance.json`、`plain-http.json`、`seed-migration-78.json`、`directed-final-tests.log`、`directed-acceptance.json`、`concurrency.json`、`state-final/`、`governance-final/`、`final-gates.json`、`fullstack-summary.json`、`fullstack-run/`、`formal-diff.json`、`git-final.json`。所有原始 payload、日志和临时数据仅保存在本机证据目录，未纳入 Git。

## 阶段 7D：Import Preflight 复用与最终本地全栈验收（Partial）

原记录：`2026-09-20-stage7d-import-preflight.md`。

> 历史时间点报告。2026-09-21 后续状态：Import 优化已独立提交为 `53dbf90e1af781c79a846ab6eb50c2426e8c4dca`；默认完整门禁已由[阶段 7E](2026-09-21-stage7e-final-fullstack-acceptance.md)通过。下文保留阶段 7D 当时的 Partial、未提交状态和原始样本，不追改历史结果。

### 结论

阶段 7D Partial。默认完整 fullstack 在首个失败阶段停止，未重跑整轮。

**唯一最小剩余阻塞：移动筛选交互的 Analysis stats 503。** `mobile-section-sheet` 请求 `period=custom&start_date=2025-01-01&end_date=2025-12-31`，`mobile-time-filter` 请求 `period=last_4_weeks`，均在 `/api/analysis/stats` 返回 HTTP 503，触发控制台错误断言。未继续排查或修复该范围；后续 browser-inventory / browser-compat 未执行。

阶段 7C Analysis revision 已独立提交为 `410d0b971dfdd8bd9efb750030a4dfeaf7f8a63b`（`perf(analysis): 持久化快照语义版本向量`）。提交前指定 10 项完全匹配，54 项 Analysis/migration 定向测试、docs audit、diff/cached 检查和提交 hooks 全部通过。README 不需改动，AGENTS/CLAUDE 保持一致。

Import 修改尚未提交；7C 已完成提交保留。

### 隔离 profile

复用阶段 7C 的 SQLite Online Backup `/tmp/spotifystats-stage7c/data/main.db` 与完整正式源文件的只读读取。13 个串流文件共 **72,550,071 bytes**，流式解码 **92,975 条原始记录**、去重后输入 **92,908 条**，现有 plays **92,908 条**；9 个账号报告文件共 **795,610 bytes**，另校验 UserAttributes 身份。没有替换为小 fixture、删减文件或响应字段。

当前真实副本的指纹基线为 `missing`，比较状态为 `baseline_missing`；`_load_existing_baseline()` 真实走缺失基线返回，并未装载 9.3 万条完整可比较指纹。没有为性能测量伪造 ready 或补写基线。

| 阶段（ms） | 样本 1 | 样本 2 | 样本 3 |
|---|---:|---:|---:|
| enumerate_stat | 0.284625 | 0.177084 | 0.181042 |
| staging_sqlite_write | 136.852296 | 135.893707 | 136.490257 |
| sha256 | 27.578249 | 28.472002 | 28.598999 |
| json_parse | 1691.233937 | 1686.780081 | 1697.593644 |
| _load_existing_baseline | 7.544125 | 7.720458 | 7.660000 |
| dataset_digest | 379.503042 | 385.782375 | 361.688375 |
| build_import_plan | 492.120541 | 479.291333 | 473.564375 |
| _affected_scope | 56.783292 | 41.090500 | 40.847000 |
| preflight_total | 3947.518000 | 3853.911583 | 3858.194334 |
| response_model_serialization | 0.140667 | 0.112833 | 0.108583 |

JSON 时间只累计生成器推进；SQLite 只写计时包含 DDL/INSERT/UPDATE/commit。dataset_digest 在 build_import_plan 内部，计时有嵌套，不能相加当总耗时。原始先行 profile 保存在 `profile.json`（SQLite 计时包含读写），之后为准确拆出写入成本补测 `profile-write-only.json`；原样本和完整 payload 均未覆盖。

### 真实 HTTP 性能与逐字段等价

三个独立新服务进程冷读（不含启动时间、不清 OS 页缓存），全部 HTTP 200：

4018.563500 ms / 4043.788916 ms / 4062.242916 ms

第一个进程的 21 个 hot 原始值（ms）：

58.504417, 58.708125, 59.718583, 58.456333, 58.446917, 58.309334, 58.218292, 58.223417, 59.352459, 59.747291, 58.891000, 58.379125, 58.093917, 58.076417, 58.356333, 58.090584, 58.050042, 58.298125, 58.219458, 58.363208, 59.009917

hot median **58.363208 ms**，nearest-rank P95 **59.718583 ms ≤500 ms**。24 个响应全部 200，cold/hot 与优化前完整响应逐字段相等，包含 blockers、warnings、文件与重复/overlap、relation、mode、全部记录计数、影响周/年、strategy、comparison status 和 confirmation token。原始 HTTP 数据见 `performance-raw.json`、`performance-summary.json`、24 个 `performance-payload-*.json`。

### 缓存、失效、并发与执行合同

- 复用现有 staging 缓存，最多 3 份、15 分钟；报告、只读数据库观察连接、staging 校验摘要与临时目录共用生命周期。淘汰/过期/退出关闭连接并删除目录，POST 取用时转移所有权并取消过期计时器，导入结束负责关闭。没有新增通用缓存框架。
- key 包含 auto/append/replace、builder/contract 与 fingerprint version、streaming/account 绝对路径、每个相关文件存在性/size/mtime/SHA-256、数据库路径和实例身份、active generation/account identity/fingerprint version/dataset digest/record count。三个 mode 即使 confirmation token 相同仍保存独立报告。
- 每个 GET 校验源文件完整 SHA-256，检测新增/删除、大小/mtime/内容改变，也检测同 size 且还原 mtime 的修改；账号报告文件与 UserAttributes 同样进入校验。数据库观察连接的 data_version 对所有已提交更改保守失效，覆盖没有更新活动状态的事实修改及设置变化；它不是持久语义 revision。
- 同一 staging 生命周期锁串行化验证和冷构建，四个同 key 并发只完整构建一次。命中返回深拷贝，不共享可变 payload；冷构建前后复核源与数据库栅栏，不发布混合状态。显式传入事务连接的内部调用仍完整计算，不缓存未提交事实。
- staging 文件丢失、损坏、过期、版本变化均失效，命中核对 staging 全文件 SHA-256；TTL 不代替事实校验。GET 不写主库、不启动导入、不排维护任务。
- POST 继续重新评估活动基线与确认计划，ETL 前和事实提交前仍核对 source manifest/SHA-256。已保留 staging 检测到源漂移时，即使新 JSON 解析结果相同，也拒绝本次旧确认。token 算法和响应字段保持原样。

### 验证

- Analysis/migration 提交前：54 passed。
- Import plan、API jobs、streaming staging、执行与端到端导入：93 passed；补齐非语义源漂移确认边界后，cache/API jobs 定向复验 49 passed（新增 cache 测试共 24 项）。日志中的 LibreSSL 和既有测试线程清理 warning 保留。
- 前端 data-import-health：5 passed。
- docs audit、diff check、Ruff/format/mypy/secrets hooks 通过；初次 mypy 的列表类型推断错误已修复，原日志保留。
- 独立 API smoke 与参数边界通过。唯一一次 `--only api` 局部阶段 PASS / 整体 PARTIAL：51 个目标、22 次请求各、slow_count=0，preflight hot P95 63.20 ms，未改变 500 ms 门槛。

### 唯一一次默认完整 fullstack

run ID：`20260920T134245.048885Z-9d74ae98a67f`；selection=`full`；overall=`FAIL`；总耗时 **1639763 ms**。命令使用 8000 后端、5173 前端、NO_PROXY/no_proxy 和同一 Online Backup source，未传 --only/--from、未跳过浏览器、未改变样本数/并发/timeout。

| 阶段 | 状态 | duration_ms |
|---|---|---:|
| preflight | PASS | 7598 |
| quality | PASS | 40748 |
| backend | PASS | 976945 |
| api | PASS | 168292 |
| browser-routes | PASS | 401984 |
| browser-interactions | FAIL | 43982 |
| browser-inventory | NOT_RUN | 0 |
| browser-compat | NOT_RUN | 0 |
| optional | NOT_RUN | 0 |

完整后端 **3026 passed / 3 skipped / 8 warnings，970.65 秒**；前端 **657 passed / 4 skipped**，build 通过。API 51 个测量目标全部通过，slow_count=0，preflight hot P95 **63.386 ms**。browser-routes 完整路由与重点视口矩阵通过；browser-interactions 桌面场景通过，两个移动场景失败。

完整日志与规范 run-scoped 报告保存在 `fullstack.log`、`fullstack-summary.json`、`fullstack-run/`。四个 browser 阶段单列如上，不以 API 局部成功替代浏览器验收。

### 正式数据与 Git 边界

正式数据逐文件核对：4183 → 4183 个文件；新增 0、删除 0、size/SHA-256 改变 0。mtime-only 变化见 `formal-diff.json`，未回写正式文件。完整清单保留在 `formal-before.json` / `formal-after.json`。

未 fetch；ahead/behind 仅比较本地缓存 origin/main。未 push、未部署、未运行或打开 Docker、未调用 AI/LLM 或 Spotify 等外部服务，未同步正式数据。原始数据库、导入文件和临时 staging 均未进入 Git。

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0be86-06d0-7b51-b1ad-8a3f70c1a9ee/spotifystats-stage7d`。

### 停止时 Git 状态

当前 HEAD / 7C commit：`410d0b971dfdd8bd9efb750030a4dfeaf7f8a63b`；7D commit：无。相对缓存 origin/main **ahead 5 / behind 0**，未 fetch。暂存区为空，`git diff --check` 通过。

剩余未提交路径仅为：

- `backend/api/import_.py`
- `backend/domains/imports/streaming_staging.py`
- `backend/services/import_plan_service.py`
- `docs/reference/data-import-and-health.md`
- `backend/tests/unit/test_import_preflight_cache.py`

新增 7D 仓库报告/索引与更新 7C 后续状态的条件是默认完整 fullstack Pass，本轮未满足，因此只在本机证据目录保存本报告。8000/5173 本轮服务已停止。
