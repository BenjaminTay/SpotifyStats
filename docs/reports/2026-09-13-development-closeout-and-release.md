# 遗留开发收口、完整门禁与发布报告

> 证据日期：2026-09-13
>
> 实现状态：IMPLEMENTED
>
> 本地验证：PASS
>
> 远端 / 生产：本报告首次提交时待发布，后续证据追加在第 7 节

## 1. 本轮收口结论

本轮从清理后的单一 `main` 基线继续完成了四组遗留工作：

- 文档状态与已完成计划归档，明确 Agent V5、L2/L3、双轨时长和 Billboard 持久快照已经完成，
  不再作为开发中分支重复推进。
- 全栈门禁增加廉价 preflight、跨工作区 `fcntl` 锁、run-id 独立证据目录和兼容 summary，避免
  昂贵阶段前才发现静态错误以及并行工作区相互污染结果。
- 修复未知 Spotify Track ID 的 L1 导入防复发、provider-first 时长解析，以及人工专辑关系确认
  未将关系 mutation 与 Album Project/L3 派生刷新纳入同一事务的问题。
- 对真实数据库重新审计 L1 风险队列；现有证据下 600 项需要 review，但没有一项具备安全自动
  split/relink 条件，因此真实数据库写入为有证据的 no-op，而不是为了清零而放宽归并规则。

阶段提交为：

| 阶段 | 提交 |
|---|---|
| 文档状态与计划归档 | `ddd35f3e` |
| 全栈门禁编排加固 | `8326169f` |
| L1、时长与人工关系事务修复 | `e251148a` |
| 真实数据库治理证据 | `a4b57e75` |
| OpenAPI 与前端类型同步 | `5bcfc5de` |

## 2. 真实数据库治理

通过 SQLite Online Backup 创建本地忽略目录中的发布前副本；副本 `integrity_check=ok`，包含
92,908 条播放。副本与主库分别执行只读 L1 风险模拟，结果完全一致：817 个多 provider owner，
217 keep，600 review，0 个安全自动操作；模拟保持原始播放不变且没有 identity health regression。

详细实现、测试和治理证据见
[`2026-09-13-l1-import-duration-and-manual-merge-closeout.md`](2026-09-13-l1-import-duration-and-manual-merge-closeout.md)。

## 3. 默认完整全栈门禁

在 `5bcfc5deae977c835bf3c25346cb822cdacf981b` 上执行未裁剪的默认命令：

```bash
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://127.0.0.1:5173
```

规范证据：

`/tmp/spotify-fullstack-verification/20260913T090004.085734Z-98d17c52ca82/summary.json`

结果为 `PASS`，运行开始时工作区 clean，总耗时 2,832,355ms。必需阶段全部通过：

| 阶段 | 结果 | 关键证据 |
|---|---|---|
| preflight | PASS | 159 份 Markdown；221 个 OpenAPI operation 和 102 个参数义务均无遗漏 |
| quality | PASS | Ruff、format、mypy、secrets、前端 78 files / 622 tests、production build |
| backend | PASS | 2,767 passed，5 warnings |
| api | PASS | smoke 148/148；boundary 113/113；全部 hot P95 < 500ms |
| browser-routes | PASS | 54 个 desktop/mobile 路由 + 30 个五视口组合，无 console/page/overflow 错误 |
| browser-interactions | PASS | 核心交互全部通过 |
| browser-inventory | PASS | 40 个路由/视口、1,914 个控件、300 个主要触控目标、0 violation；7 个长列表场景通过 |
| browser-compat | PASS | Chromium、Firefox、WebKit 路由与交互均通过 |

一次年度 contract 在临时数据库销毁后曾产生一条后台线程 `disk I/O error` teardown warning；将该
测试单独以 `PytestUnhandledThreadExceptionWarning` 升格为错误复跑后 1 passed，未复现。它不影响本次
断言结果，但若后续重复出现，应另行收集稳定复现而不是隐藏 warning。

## 4. Agent V5 当前实测

当前配置为 `AI_AGENT_RUNTIME=v2`，LLM provider 为 DeepSeek；以下测试只记录 provider/model 名称，
没有读取或输出 API Key。

### 4.1 问答

- 变更门禁 7/7 Pass：相对时间、专辑复杂比较、三年 Markdown 表格、深夜偏好、社区、无数据范围、
  只读删除拒绝；turn P95 46,331ms，tool P95 41,387ms。
- 补充总览、播放纪录、2025 曲风与语言 3/3 Pass；全部为 V2，数值证据覆盖率 100%，无不支持的
  数值 literal，Answer Quality Contract 通过。
- 10 个问答任务全部使用后端注册的只读工具，并具有可重放 `turn_started/turn_ended` 与
  `model_message` 轨迹。

### 4.2 年度报告

2025 年 `visual_yearly_artifact + agent_synthesis_v2` 连续运行两次，2/2 Pass：

| 运行 | 上下文 | 耗时 | 分段 writer | 质量门禁 |
|---|---|---:|---|---|
| `b0fe32c3e28d` | cold，构建 1 次 | 45,581ms | 6 accepted / 0 fallback | 全部通过 |
| `a04c03720405` | exact snapshot hit，构建 0 次 | 32,686ms | 6 accepted / 0 fallback | 全部通过 |

两次的 critic、fact validation、final artifact quality、section checkpoints 均为 true。

### 4.3 SSE 与恢复检查点

任务 `15b0ce9a9a6e` 从中间 cursor `v1:p11395:t2752:a1` 重连后，只收到更晚的 progress
11396–11397、tool 2753–2754、answer chunk 2–3 和 completed；没有重放更早事件或首个答案分片。
同一任务的 45 条持久轨迹包含 turn、step、model request/message、tool call/result 的完整事件类型，
满足当前恢复 checkpoint 的重放前提。

## 5. 仍保留的明确边界

- 默认完整门禁已经在当前提交全绿，但本轮总耗时约 47 分钟，未达到计划中的 25 分钟目标；
  P1-A/P1-B 已完成，耗时剖析、安全并行和严格 manifest 仍由
  `SS-2026-08-24-004` 单独跟踪，不能把覆盖裁剪当作优化。
- L1 的 600 项是缺少唯一目标证据的治理 review queue，不是未完成代码。
- PWA 基线、生产双运行面和私网 HTTPS 工程已经完成；在没有 iPhone/Android 物理设备、真实
  OAuth 回跳和 App Store/安装包分发需求前，本轮决定不引入 Capacitor。App 化路线继续保持
  `PARTIAL / EXTERNAL`，不把桌面浏览器仿真写成真机完成。

## 6. 发布前状态

本节记录首次提交本报告时的事实，供后续时间线对照：本地 `main` 为 `5bcfc5de`，相对
`origin/main=d37e8aaf` ahead 5，生产仍为 `b0d674bd`。代码尚未 push 或部署。

## 7. 远端与生产发布证据

待本轮 push、自动发布和生产独立验收完成后追加；本节不会反向覆盖第 6 节的发布前事实。
