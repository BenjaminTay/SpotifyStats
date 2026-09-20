# 阶段 7：全路由性能验收与本地收口

**结论：Partial，未达到“阶段7本地全栈 Pass”。** 本报告只记录本轮当前 dirty worktree 的独立证据。此前阶段报告仅用于确定合同和预算，不作为本轮通过依据。

- HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`。未 add、commit、push、部署或同步正式数据。
- 证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bdd8-b911-7b33-b062-c94e7b068598/spotifystats-stage7`；数据库副本和隔离 sidecar 位于 `/tmp/spotifystats-stage7`。证据含真实响应/截图，保存在本机，不纳入 Git。
- 真实数据经 SQLite Online Backup 得到 92,908 条播放；副本迁移至 schema 76。默认过滤为 min_ms=30000、music_only=true、merge_enabled=true、gap=5、dynamic=true、L2、compilation=false；Billboard TopN=30/20/20、周五 12:00，Asia/Shanghai。
- 后端为 loopback、无 reload、lifespan=off 的测量服务；解释器启动和健康检查不计入请求时间。进程重启读不等于正常 lifespan 调度验收；后者仍有完整套件中的启动失败待解决。Python socket 禁止外部连接；浏览器专项拦截外网、写请求和 AI 请求。

## 已实现的必要修复

| 症状 | 根因与最小改动 | 当前证据 |
|---|---|---|
| 两个完整 contract 的 Analysis 503 | 默认 fixture 未私有发布；未知/空 period 在 reader 中提前拒绝，偏离原 builder lifetime 语义。增加真实发布 fixture，恢复规范化；GET 保持只读，未将默认 200 改成 503 | 原失败、28 项定向通过；完整 contract 437 passed |
| preflight schema 版本失败、CLI 假设已迁移 | 最新常量 75 落后于 migration 76；Archive/Governance CLI 先运行 run_migrations | preflight 通过；旧 seed CLI 两项回归通过 |
| 测试清理误报及 sidecar 环境继承 | dir_fd 相对路径误用 cwd；新增三类 sidecar 未加入 session 重定向 | 目录句柄 canary 与六类路径验证；正式数据另行核对 |
| 性能目录空跑 | 用字典字符串中的花括号判断未配置，所有目标被排除；改为检查参数值，并拒绝零目标 | 探针 11 项通过；真实 HTTP 矩阵 |
| 性能目录不符当前消费者 | Billboard 改为当前 projection；补齐治理/档案/帖子；私有治理与年度维护状态使用其实际 surface | 原 404 与 artist candidate 漏 q 的 422 保留；修正 surface/必需参数后重测 200 |
| 完整 quality 失败 | hook 格式化 21 文件；3 文件的4个 mypy 类型错误 | 第二轮 quality PASS；格式类增量有 AST 对账 |

## 基线、竞争和计量范围

- 起点全部 tracked/untracked 文件与正式 data 清单、大小、SHA-256、Git 暂存内容、端口/进程均保存在 `*-before.*`。`routes.txt`、`api-consumers.txt`、`maintenance.txt` 由当前源码 rg 重新生成。OpenAPI 222 operations 和 104 参数义务均无未归类项；这表示审计覆盖登记完整，不等于每项真实部署通过。
- 使用 `/tmp/spotify-fullstack-verification.lock` 主机锁，完整门禁使用同一显式锁路径。其他项目普通 pytest/Vitest/类型检查不遵守此锁；16:32:03 起发现教师导航任务竞争，暂停自有 API 测量，结束后重测受影响目标。`contention.json` 与进程清单保留竞争窗口；原样本不删除、不用于达标。其他项目的 idle Vite/uvicorn 保留原状。
- `api-matrix.json`、`cold-matrix.json`、`api-corrections.json` 保存原样本；`api-performance.normalized.json` 只补齐测量合同 metadata，不更改任何耗时/失败。SQL rows 为 cursor 返回行数，不是物理扫描页数。RSS 为服务器进程累计峰值，不是某一个接口的独占内存。builder/enqueue 仅针对探针注册的函数观测，不能把未注册函数宣称为零。

## 默认维护与持久读取

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

## 后端实际消费者矩阵

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

### 独立进程首次读取

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

## 状态与统计语义

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

## 浏览器全路由

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

### 补充交互与并发结果

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

## 部署、安全与标准门禁

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

## 正式数据、磁盘与 Git

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
| `docs/reports/2026-09-20-stage7-local-performance-acceptance.md` | added |
| `docs/reports/README.md` | changed |
| `scripts/benchmark_api.py` | changed |
| `scripts/performance_catalog.py` | changed |
| `scripts/rebuild_account_archive.py` | changed |
| `scripts/rebuild_governance.py` | changed |

本轮专用 8000/5173 服务已停止，性能锁已释放；其他项目服务未终止。未实现的全 family 故障、正常 lifespan 重启、全部复杂面板和 Docker 运行态验证是验收阻塞，不列为非阻塞尾项。原有 urllib3/后台线程警告保留原日志；没有以告警清理扩大本轮范围。

完整起点与终点清单、SHA、暂存内容、精确阶段7 patch 位于证据目录。保留原 dirty worktree；hook 的格式增量与逻辑改动分开记录。

## 剩余阻塞与下一步

本轮不能收口为 Pass。剩余阻塞以最终 fullstack、浏览器和状态文件为准；Home 重启 key、Records 重建预算、Analysis stats LKG 冷读超时、Firefox 后退检查、触控目标尺寸、年度维护状态/艺人排名的 warm 延迟及三模式容器运行态缺口已经确认。完整矩阵中的未覆盖状态不得视作通过；data/.DS_Store 的内容变化还使全目录严格不变证明未成立。

下一条修复 Prompt：

> 仅修复阶段7报告列出的失败：先处理最终完整套件的 Analysis 集成契约与真实私有发布缺口、seed/schema 版本同步和六个 Archive 启动 revision 失败，保留原 builder 空范围语义对账并验证前端 unavailable；修复 Home 持久 key 的进程内 revision 依赖；针对已保留的性能/浏览器失败做最小修复。使用同一真实 Online Backup、独占性能时窗和三浏览器三视口，补齐缺失状态矩阵与本地三部署模式运行证据，最后运行一次默认完整 fullstack。不得放宽预算、恢复 GET 冷建或把错误页算 ready，不改正式 data；测量期间不改变 HEAD。验收完成后仅对归属明确、可独立构建测试的完成成果按补充授权进行本地 scoped commit，禁止 push/部署/数据同步。

本地结果不代表生产验收。测量结束时收到补充授权：大阶段完成且归属可靠后可做本地 scoped commit，仍禁止 push/部署/数据同步。本轮 HEAD 全程未变；阶段7失败项及跨阶段 hunk 归属尚未收口，因此本次不提交未完成状态。交付本报告后停止。
