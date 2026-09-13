# 遗留开发收口、完整门禁与发布报告

> 证据日期：2026-09-13
>
> 实现状态：IMPLEMENTED
>
> 本地验证：PASS
>
> 代码发布基线：PUSHED `d50f924c`；最终证据以 docs-only 后续提交进入 `origin/main`
>
> 生产代码：DEPLOYED `d50f924c` / dual
>
> 外部入口：PARTIAL / EXTERNAL

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

本节是第 6 节之后的时间线追加，不反向覆盖发布前事实。

### 7.1 Git 与 GitHub Actions

- push 前 `main...origin/main = 6/0`，确认远端没有本地未包含的提交；随后将
  `d37e8aaf..d50f924c` 推送到 `origin/main`。
- 常规 CI run
  [`34751006416`](https://github.com/BenjaminTay/SpotifyStats/actions/runs/34751006416) success。
- 正式发布 run
  [`34751006279`](https://github.com/BenjaminTay/SpotifyStats/actions/runs/34751006279) success：共享质量与生产
  契约 6m24s，三种 profile 全部通过，镜像/CAS 1m30s，服务器部署 4m12s。
- Actions 的 Node.js 20 被 runner 强制升级到 24 仍有弃用注解，但没有失败步骤。

### 7.2 发布与回滚证据

- 发布前 Online Backup：
  `spotify-stats-pre-release-d50f924c854f-20260913T101713Z.db`，444,588,032 bytes。
- 搜索预检精确复用已有统计，`reused=true`，预检报告：
  `music-search-preflight-d50f924c854f-20260913T101713Z.json`。
- 目标镜像中的预检通过：migration 69，4/4 统计变体，search builder v10、Billboard v4、
  orphan=0；上线后的 runtime gate 为 migration 73，exact/fuzzy/CJK/short CJK 全部通过，语义 smoke
  约 242ms。
- CAS retention 已将 `d50f924c` 设为 current，`b0d674bd` 作为 previous，可按既有流程联合回滚。

### 7.3 服务器独立验收

部署完成后通过既有 SSH 主机连接重新执行服务器 `./verify.sh`，结果 PASS：

- 模式为 `dual`，简化版访问为 `public`；Backend、private web、public web 三个容器均 healthy。
- 三个容器的镜像 revision 均为完整
  `d50f924c854fa5ca2b88a89ea36ebce73fb57e17`。
- Backend 没有宿主端口；private/public 分别只绑定 `127.0.0.1:3001/3002`。
- private 为 `private-admin/full`，public 为 `public-readonly/showcase`；两边 release SHA 相同，公共面
  AI、设置、导入、编辑和 OAuth 等能力均关闭。
- SQLite `integrity_check=ok`，schema 73，92,908 条播放，时间范围为
  `2022-06-30T17:28:51Z..2026-08-21T15:39:05Z`。
- 服务器每日 Online Backup timer 为 enabled + active。
- `manifest.webmanifest`、`sw.js`、`offline.html` 均返回 200，manifest MIME 正确。

### 7.4 Agent、HTTPS、OAuth 与真机边界

- 生产私有面设置保留 `llm_enabled=true` 和 DeepSeek provider/model，但服务器没有 LLM 凭据；真实
  Agent smoke 任务 `4f0fa6a95aa8` 立即安全失败为“LLM 未配置”，未调用工具或生成答案。生产基线
  原本就刻意移除了 LLM Key，本轮没有把本机密钥擅自复制到服务器。若要在线使用 Agent，需要用户
  单独授权并通过生产设置或服务器 secret 配置凭据。
- 服务器 Tailscale 当前为 `Stopped`，Serve 未配置；因此历史私网 HTTPS 域名当前不在线。发布脚本
  按设计没有启动或修改外层入口。
- Spotify 当前未连接；OAuth login 能生成授权 URL，callback 仍精确指向
  `https://spotify-stats.tail8916b1.ts.net/api/spotify/auth/callback`，但外层 HTTPS 关闭且没有人工 consent，
  所以不能声称真实 OAuth 回跳通过。
- iPhone Safari、Android Chrome 安装、standalone、安全区、软键盘与返回链路仍需物理设备。当前不
  实施 Capacitor 的决策不改变这一 `PARTIAL / EXTERNAL` 状态。

最终证据文档提交只修改 Markdown，不触发生产发布；因此远端 `main` 可以领先生产代码
`d50f924c` 一个 docs-only 提交，这不表示生产缺少业务代码。
