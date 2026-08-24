# 全栈总门禁耗时优化交付与验收

日期：2026-08-24 至 2026-08-25

状态：**Partial（P0 与首项 P1 去重完成；25 分钟与三轮稳定目标未达成）**

关联计划：[`../plans/2026-08-24-fullstack-gate-duration-optimization-plan.md`](../plans/2026-08-24-fullstack-gate-duration-optimization-plan.md)

当前规则：[`../reference/fullstack-verification.md`](../reference/fullstack-verification.md)

## 1. 结论

阶段化和确定性去重已经完成，且没有减少默认门禁覆盖：默认命令仍执行 quality、后端全量、API、路由、交互、控件/长列表和 Chromium/Firefox/WebKit。局部命令只能得到 `PARTIAL`，失败和服务前置条件分别记录为 `FAIL`、`BLOCKED`，每次运行都会写出阶段 JSON。

耗时目标没有完成。P0 代码冻结后的两次默认完整门禁分别以 27 分 48 秒和 29 分 7 秒通过，均高于 25 分钟；第三次在 API 性能阶段失败。P1 去重修改后又有一次默认完整门禁以 34 分 8 秒通过，但该轮受到持续共享主机负载干扰。当前累计三次功能覆盖完整的 Full Pass，中间一次性能 Fail 仍保留，因此不能声明“三次连续稳定完整 Pass”，也没有达到 25 分钟目标。

验收拆分如下：

| 范围 | 结果 | 说明 |
| --- | --- | --- |
| P0 阶段化、CLI、状态、JSON | Pass | 默认 Full 与局部 Partial 不混淆 |
| Phase 5 同轮后端去重 | Pass | 总门禁不再追加 unit/contract；独立 Phase 5 保持完整 |
| 局部反馈目标 | Pass | inventory 低于 3 分钟；compat 低于 4 分钟 |
| 默认完整门禁功能覆盖 | Pass × 3 | P0 两次、P1 修改后一次；期间的性能 Fail 不被覆盖 |
| 25 分钟目标 | Fail | 两次完整 Pass 均高于目标 |
| 三次稳定完整运行 | Fail | 第三次 API 热 P95 超阈值 |
| P1 首项重复计算去重 | Pass | `test_api.py` 减少 126.94 秒，断言覆盖保持 |
| 优化计划总体 | Partial | 保留计划，待低干扰环境连续三次计时 |

## 2. 已实施内容

- `scripts/fullstack_verification_check.sh` 提供稳定阶段键、`--list-stages`、`--only`、`--from`、`--dry-run` 和 `--summary-json`；`--only` 与 `--from` 互斥，未知或空阶段以退出码 2 拒绝。
- 阶段状态统一为 `PASS / FAIL / BLOCKED / SKIPPED / NOT_RUN`；只有无阶段选择、无显式兼容跳过且全部必需阶段通过时，整体才是 `PASS`。
- API 和浏览器阶段增加只读健康前置检查；Playwright 只在选中兼容或相关可选阶段时探测。
- `scripts/phase5_check.sh` 新增仅供父门禁使用的 `--skip-backend-tests`。独立默认路径保持文档、CI parity、unit、contract、Ruff、前端测试和 build 完整。
- 默认总门禁先执行 pre-commit，再调用 Phase 5 去重路径，随后只运行一次 `pytest backend/tests/ -q`。pre-commit Ruff 与 Phase 5 Ruff 因版本/参数不等价而都保留。
- 新增当前规则、脚本合同测试和 Phase 5 CLI 测试，并同步 `AGENTS.md`、`CLAUDE.md` 与文档地图。

## 3. 验收中额外发现并修复的问题

第一次完整计时尝试在 `browser-inventory` 发现 `/analysis/charts` 手机视口的紧凑分页按钮只有 52×36px，低于 44×44px 触控目标。此前单跑清单时异步页面状态没有呈现该分页组，因此没有暴露。

`.mobile-pagination-compact-button` 的 `min-height` 已从 36px 改为 44px。修复后的真实清单复核覆盖 40 组页面/视口、1,956 个控件和 353 个主要触控目标，尺寸违规为 0；两次完整 Pass 中同一阶段继续为 0 违规，说明修复在完整执行顺序下稳定生效。

## 4. 合同与局部验收

- 脚本合同与 Phase 5 CLI：`42 passed`。
- 独立 Phase 5 默认路径：unit `1358 passed`、contract `369 passed`、Ruff 通过、前端 `561 passed`、production build 通过。
- `--only quality`：约 44.7 秒，整体 `PARTIAL`；输出明确记录后端 unit/contract 由父门禁后端阶段负责。
- `--only api`：API smoke `128/128`、边界 `111/111`、OpenAPI operation 195 个且 0 未归账、参数义务 0 未归账，整体 `PARTIAL`。
- `--only browser-inventory`：约 2 分 6 秒；修复后的复核约 1 分 22 秒，均低于 3 分钟目标。
- `--only browser-compat`：约 3 分 17 秒，Chromium、Firefox、WebKit 全部通过，低于 4 分钟目标。
- `--from browser-inventory`：只运行 inventory 与 compat，前序阶段均为 `NOT_RUN`，整体 `PARTIAL`。
- 不可达服务：所选阶段为 `BLOCKED` 并写出 JSON；full dry-run 的阶段均为 `NOT_RUN`，整体 `PARTIAL`。

## 5. 默认完整计时

### 5.1 两次完整 Pass

| 阶段 | 第 1 次 | 第 2 次 |
| --- | ---: | ---: |
| quality | 38.569s | 47.243s |
| backend | 481.263s | 529.141s |
| api | 280.998s | 305.371s |
| browser-routes | 476.311s | 475.769s |
| browser-interactions | 90.534s | 91.411s |
| browser-inventory | 88.033s | 84.402s |
| browser-compat | 212.575s | 213.490s |
| 总耗时 | **1668.486s（27:48）** | **1747.083s（29:07）** |

两次均为默认完整模式，后端 `2222 passed`，前端 `561 passed`，API smoke `128/128`、边界 `111/111`，路由、交互、图表、控件、长列表和三浏览器均通过。两次完整 Pass 的中点约 28 分 28 秒，仅作为两次样本摘要；它不是规划要求的三次中位数。

### 5.2 第三次失败

第三次在进入浏览器阶段前失败：quality 50.830s、backend 545.045s 均通过，api 361.759s 失败。`/api/billboard/all-time` 的 21 个热样本中出现 0.887s、0.581s、0.549s 等尾部尖峰，热 P95 为 581.4ms，超过 500ms 门槛。脚本正确输出 `FAIL`、退出非零，并把后续浏览器阶段记录为 `NOT_RUN`。

失败时主机上同时存在不属于本门禁当前阶段的 Playwright/Chrome 和 Metal 编译 CPU 负载。相同 API 阶段随后完整局部复核通过，`/api/billboard/all-time` 热 P95 约 340ms；该复核整体为 `PARTIAL`，只说明尖峰未立即复现。由于性能门禁在共享主机负载下确实越线，三轮稳定性仍判 Fail，不调整样本数或 500ms 阈值。

## 6. 瓶颈与 P1 决策

确定性 unit/contract 重复已从总门禁中消除，按基线每轮至少节省约 1 分 54 秒；当前独立 Phase 5 中这两段实测约 2 分 2 秒。完整门禁仍超过 25 分钟，主要由以下三段构成：

1. 后端全量约 8–9 分钟，且三次都在测试进度约 19%–22% 出现持续数分钟的稳定慢段；
2. 浏览器路由约 7 分 56 秒，两轮波动小，是第二大稳定阶段；
3. API 约 4 分 41 秒到 6 分 2 秒，并受共享主机负载影响出现性能尾部尖峰。

前端 Vitest 在前两次低干扰运行中约 20–25 秒，quality 整体低于 1 分钟，不是主要瓶颈。P1 的顺序因此确定为：

1. 运行 `pytest --durations=50`，定位后端慢段中的具体用例、夹具、建库和 builder；先消除重复工作，再评估 xdist。
2. 为性能报告补充运行前主机负载和热样本分布证据，避免把共享负载尖峰误判成稳定产品回归，也不通过自动重试掩盖真实失败。
3. profile 证明隔离安全后，才评估纯测试子集并行；SQLite、缓存、端口、真实数据与性能 benchmark 继续串行。
4. 浏览器路由只在不减少页面、视口、等待条件和 console/overflow 断言的前提下优化；三浏览器兼容仍保留。

## 7. P1 首项实施与复验

`pytest backend/tests/ -q --durations=50` 精确复现了约 19%–22% 的慢段。进一步定向 profile `backend/tests/integration/test_api.py` 得到：

- `TestReleaseCycle::test_artist_overview`：160.67s；
- `TestReleaseCycle::test_artist_overview_release_covers_resolve`：165.30s；
- 两个测试请求完全相同的 Taylor Swift overview URL 和参数，只分别断言结构/指标与封面可解析；
- `test_album_detail` 为 20.97s，其余单项显著更低。

两个 overview 测试现共享 module-scoped 只读响应。第一个测试仍完整断言艺人、发行、趋势、summary、cycles 和三类 cover URL；第二个测试仍从响应定位 `THE TORTURED POETS DEPARTMENT` 并真实请求本地 cover endpoint。因此删除的是相同计算，不是产品断言。

定向结果：

| 范围 | 修改前 | 修改后 | 结果 |
| --- | ---: | ---: | --- |
| 两个 overview 测试 | 160.67s + 165.30s | 唯一 setup 149.27s + 第二个 call 0.01s | 确定性消除一次昂贵请求 |
| `test_api.py` 109 项 | 405.73s | 278.79s | 109/109 Pass，减少 126.94s |

修改后的默认完整门禁再次 Full Pass，阶段如下：

| 阶段 | 耗时 |
| --- | ---: |
| quality | 82.851s |
| backend | 660.136s |
| api | 363.178s |
| browser-routes | 507.564s |
| browser-interactions | 95.877s |
| browser-inventory | 108.453s |
| browser-compat | 229.888s |
| 总耗时 | **2048.253s（34:08）** |

该轮运行期间存在持续的外部 Chrome/Playwright、WindowServer、GPU 和桌面应用 CPU 负载；前端测试由低干扰轮次的 20–25 秒升到 50.12 秒，API 由 281–305 秒升到 363 秒，路由也增加约 31 秒，说明整机负载同时影响各阶段。后端虽然已确定性少执行一次 overview，仍由 481–529 秒升到 660 秒。因此这轮用于证明 P1 功能回归 Full Pass，不用于宣称低负载总时长改善或达到 25 分钟。

API 性能在该轮通过：`/api/billboard/all-time` 热 P95 约 400ms，未复现此前 581.4ms 失败；仍保持 21 个热样本和 500ms 阈值。

## 8. 证据边界

- 当前可确认 P0 编排、局部排障能力和 P1 首项重复请求去重已完成，但优化计划整体是 Partial。
- P0 计时中有两次完整 Pass、一次性能 Fail；P1 修改后又有一次完整 Pass。失败记录不被后续成功覆盖，三次连续稳定和 25 分钟中位数仍未证明。
- 未执行 `--preview-url`、production preview、真实部署、远程发布、备份或回滚验收。
- `/tmp` JSON 是本次机器可读证据，未提交到 Git；本文保留其关键数字与状态。
