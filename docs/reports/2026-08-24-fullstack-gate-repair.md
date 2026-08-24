# 项目全栈总门禁修复与验收报告

日期：2026-08-24
状态：**PASS（本地项目全栈总门禁）**
关联报告：[`2026-08-24-yearly-review-semantic-correction.md`](2026-08-24-yearly-review-semantic-correction.md)

## 1. Partial 的实际组成

年度总结语义修复本身已经通过，但当时全量后端仍有 8 项失败，因此项目口径只能标为 Partial。逐项复核后确认它们不是同一种问题：

- 真实数据测试硬编码了会随合法导入增长的播放数、周数和旧 provider-conflict 状态，数据更新后断言自然漂移。
- Album Project 单元夹具只建立项目关系，没有插入当前规则要求的有效播放/source album，实际测试到的是“非活动项目”。
- 艺人元数据刷新只写 `artists.spotify_artist_id`，没有同步稳定治理表 `artist_identity_external_ids`；Jolin 身份组因此丢失两个不同 Spotify ID 的冲突证据。
- 浏览器门禁仍使用旧页面标记、旧年度交互选择器和固定短等待；Settings smoke 还会修改服务端设置并触发搜索重建，导致后续页面在 warming 状态互相干扰。
- 继续执行完整门禁后又发现三项门禁缺口：详情页最近播放的两个图标分页按钮缺少可访问名称；社区相同冷请求并发穿透 TTL 缓存，重复重算完整历史；性能门禁只有两个热样本，所谓 P95 实际等于单次最大值。

## 2. 已完成修复

- 艺人身份创建、更新、刷新与 undo 全链支持 external IDs；Spotify 精确关联会同步 verified provider ID，且不会降低已有人工作证。不同稳定 ID 被保留为冲突事实，由 `provider_metadata_artist_id` 单独决定展示来源。
- 真实数据测试改为从当前数据推导预期数量并断言跨接口一致性；Billboard 周数同样动态核对。Album Project 夹具补齐有效播放事实，不放宽产品规则。
- 四套浏览器脚本更新当前路由标记、年度章节交互和冷数据等待；服务端 Settings 控件改为只读可用性检查，避免验收本身改变统计 revision。全控件与长列表脚本只在明确业务内容就绪后断言。
- 最近播放桌面分页按钮补齐 `type`、`aria-label` 和装饰图标 `aria-hidden`。
- 社区核心历史生成在 TTL 缓存外增加按参数 singleflight。相同冷态 feed/trending 并发实测约 20.5 秒同时返回，没有再把后端拖入重复构建。
- 核心 API benchmark 默认改为 1 次冷请求加 21 次热请求，共 22 次；P95 不再由两个热样本冒充。

## 3. 真实数据治理修复

本地库通过治理接口补齐 Jolin 身份组的稳定外部 ID：

- revision：`18`，active aggregate revision：`18`，状态：`ready`。
- raw artist `765 / JOLIN`：Spotify `1r9DuPTHiQ7hnRRZ99B8nL`，verified。
- raw artist `768 / JOLIN蔡依林`：Spotify `12vIkyEuT8OimFl9i5yCXo`，verified。
- 审计事件：`artist_identity_events.event_id=17`；重建任务 `96b3b890-1ea` 为 `done`。
- 六套当前音乐查找变体均为 `ready`；SQLite `PRAGMA integrity_check=ok`。

边界说明：执行前尝试创建 Online Backup 时，因 `data/backups/` 当时不存在而失败，随后治理 mutation 已经提交；因此没有成功的 mutation 前备份文件。事件 17 的 `before_json` 保留修改前身份快照，修改后已创建忽略 Git 的 `data/backups/spotify_stats.after-jolin-external-id-20260824.db`，完整性为 `ok`。这不影响当前事实正确性，但不应把它描述成完整的修改前备份链。

## 4. 年度总结成品复核

当前 `/api/yearly-review/2026` 返回 `year_to_date`：

- 播放里程碑为 `Sign of the Times / 60,000 次`，不存在 `Manchild / 1,000 次`里程碑。
- `Manchild` 仅出现在榜单附录中。
- 时间线没有 6 月 13 日与 7 月 25 日各自宣称“今年听歌最多的一天”；当前唯一最高级与并列规则由确定性数据和 validator 约束。

## 5. 最终门禁证据

正式执行：

```bash
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

最终退出码为 `0`，并输出 `Full-stack verification matrix completed.`：

- 后端全量：`2212 passed`；unit `1348 passed`；contract `369 passed`。
- 前端：73 个测试文件、`561 passed`；TypeScript/Vite production build 通过。
- pre-commit：Ruff、Ruff format、Mypy、Detect secrets 全部通过。
- OpenAPI：195 个 operation、95 类参数义务均 `unaccounted=0`；安全 GET `128/128`，边界探针 `111/111`。
- 21 个热样本的核心 API 性能门禁无慢端点；最大 hot P95 约 300ms，阈值 500ms。
- 浏览器：52 组完整路由、30 组重点视口、桌面/移动交互与图表交互全部通过，0 console error、0 warning、0 page error、0px 横向溢出。
- 控件盘点：40 组、1,967 个控件、360 个主要触控目标，0 violation；长列表 7/7 通过。
- Chromium、Firefox、WebKit 路由与核心交互全部通过。

## 6. 验收边界

- 本报告确认本地开发后端与 Vite 开发前端的项目标准全栈门禁为 Pass。
- production build 已通过，但本次没有执行可选 `--preview-url` 生产预览矩阵、真实生产部署或远程发布；这些不能由本地 Pass 推断。
- LibreSSL/urllib3 与 HTTP 422 名称弃用提示为已知 warning，不是测试失败。

## 7. 本轮耗时诊断

### 7.1 结论

最终一次从头执行并通过的标准全栈门禁约为 27 分钟。按单个命令计算，最大瓶颈是后端全量测试：`2212 passed in 474.91s`，约 7 分 55 秒；按阶段类别累计，浏览器验收更大，从性能报告写出到跨浏览器结束约 13 分 55 秒，包含两套路由、桌面/移动交互、图表、控件、长列表及 Chromium/Firefox/WebKit。

因此，“测试时间过长”只解释了一部分：最终门禁本身大部分时间确实花在自动化验证上，但本轮总耗时被放大的主要原因是失败发现较晚、修复后又从头运行整套串行门禁，而不是年度数据修复计算本身。

### 7.2 计时口径与主要阶段

以下时间来自最终门禁终端计时、pytest 汇总以及 `/tmp` 报告生成时间；浏览器阶段是同一串行区间的近似值，不能当作单脚本精确 benchmark。

| 阶段 | 最终一次耗时/证据 | 判断 |
| --- | ---: | --- |
| 后端全量测试 | `474.91s`，约 7:55 | 最慢的单个命令 |
| Phase 5 后端 unit + contract | `39.37s + 75.04s`，约 1:54 | 在全量 pytest 已通过后重复覆盖同一后端集合 |
| Phase 5 前端测试 | `33.54s` | 另有 production build、静态检查和 hooks |
| API 审计、smoke、边界与 21 热样本 benchmark | 约 3 分钟 | 数据规模和 22 次请求使结果可信，但不是最大项 |
| 全部浏览器验收 | 约 13:55 | 累计最慢类别；脚本按共享服务状态串行运行 |
| 最终一次完整门禁 | 约 27 分钟 | 本地开发服务口径，不含 preview/部署 |

排障过程中先后在控件可访问名称、长列表冷等待和性能样本口径处晚失败，随后才获得最终 Pass。四次完整尝试中的后端全量测试分别为 `620.95s`、`409.57s`、`424.81s`、`474.91s`，仅这一项重复执行就累计 `1930.24s`，即约 32 分 10 秒；每次晚失败前还重复执行了 hooks、Phase 5、API 或部分浏览器步骤。这是“整轮时间”显著高于“最终一次 27 分钟”的主要来源。

### 7.3 为什么失败发现得晚

- 总门禁采用固定串行顺序：全量后端、hooks、Phase 5、API、浏览器。控件、长列表和跨浏览器问题位于尾部，前置成功步骤无法复用。
- `phase5_check.sh` 在全量 `pytest backend/tests/ -q` 后再次执行 unit 与 contract；这是独立门禁的合理自包含设计，但嵌入总门禁时形成重复测试。
- 浏览器脚本覆盖真实数据、多个视口和三个浏览器引擎，且部分页面需要等待冷数据；为避免共享 SQLite、缓存和服务 revision 互相干扰，目前串行执行是保守选择。
- 本轮旧 Settings smoke 会改变服务端配置并触发搜索重建，社区相同冷请求又会并发穿透缓存；它们放大了等待和波动，现已分别改为只读验收与 singleflight。

## 8. 缩短测试时间的实施建议

### P0：先缩短失败反馈和重复执行

1. 为总门禁增加显式阶段参数，例如 `--only backend|api|browser` 和带 Git SHA、worktree diff、数据 revision 指纹的 `--resume-from`。排障时只重跑失败阶段；最终提交前仍完整跑一次，不把旧证据冒充当前 Pass。
2. 增加开发期快速门禁：先运行改动相关单元测试、脚本合同测试、控件/长列表/性能等高风险目标，再进入完整门禁。这样本轮三个晚失败都能在数分钟内发现。
3. 让总门禁在已经成功执行全量后端 pytest 时，以同一代码和依赖指纹向 Phase 5 传入 `--skip-backend-tests`；单独运行 Phase 5 时仍保持自包含。按本次数据，每个完整运行可直接减少约 1 分 54 秒。

### P1：在不降低语义覆盖的前提下优化执行

1. 先运行 `pytest --durations=50` 建立慢测试清单，再只对无真实库写入、无全局缓存和无进程共享状态的 unit/contract 使用 `pytest-xdist`；SQLite、缓存和真实数据集测试继续串行隔离。
2. 将静态检查、文档审计和前端纯单元测试并行化，但不要让 CPU 密集后端测试与性能 benchmark 或浏览器计时并行，以免缩短总时长却制造假性能失败。
3. 将浏览器验收拆成 Chromium 主矩阵和 Firefox/WebKit 兼容矩阵，按相同只读数据指纹分别产出证据；可在 CI 独立 job 并行，本地最终聚合只读取当次 SHA 的结果。
4. 对真实冷数据页面保留业务就绪条件和上限超时，记录实际等待时间；不要通过统一增加固定 sleep 换稳定性。这样可继续定位真正慢的 builder，而不是让每条快路由一起等待。

按本轮数据估算，P0 可使晚阶段修复后的单次反馈从十几分钟降到约 2–5 分钟，并避免三次重跑产生的 20–30 分钟以上前置重复；完整干净门禁在实现证据复用后可先从约 27 分钟降到约 24–25 分钟。若 P1 的并行隔离经 profile 证明安全，目标可进一步收敛到约 16–20 分钟。以上是基于本轮阶段数据的工程估算，实施后仍需用三次冷/热运行重新量化，不能预先视为已达成。
