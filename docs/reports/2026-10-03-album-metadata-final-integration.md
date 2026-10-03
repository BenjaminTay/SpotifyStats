# 专辑证据与最新封面主线：最终本地集成验收

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 固定输入：分页 `4f9a01ff147f718ca9d697ed46870c41db8f3e5c`、艺人 `8f638494418770097a96bc6c4eb1ad67d447c964`。
> 已提交检查点 `ad9cc3c6`；合入主线输入 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e`，保留其封面提交 `f139ec4d`。
> 验证代码：`8464ffa635745ccb57e08c82002be7d484e10d63`。
> 当前：已实现、已本地提交、LOCAL_FULLSTACK_PASS；已安全合入本地 main。未推送、未部署，正式库未写入。

## 整合范围

业务代码三方自动合并。详情头部同时保留按尺寸/DPR 加载的 `coverDisplayUrl` 与“发行/已听”独立数量；四个动态 cache_clear 测试修复与主线一致，没有重复实现。四处文档冲突逐段保留双方记录，没有整文件选取 ours/theirs。最终后端重新生成 OpenAPI 和前端类型，包含 160/320/640 封面合同与来源 resolver。

专辑两类证据保持主体独立、独立校验与可靠旧结果；数据库异常整批回滚。连续迁移 86/87/88、受控 seed、Track 原始/有效署名守恒和年度 `yearly_review_v2_19_album_evidence` 依赖保持。没有涉及 SS-2026-09-24-003 日期精度。

全局开发状态总表继承另一任务尚未提交的整份内容，只维护两个事项，保留未跟踪文件，不把整份总表或 V6 归档混入本任务提交。两个输入分支和固定 SHA 均保留。主目录同期改动在安全合入前保持原样。

## 本轮证据

- 专项后端 137 passed / 1 LibreSSL warning，覆盖两类证据、身份、迁移、原子回滚、实际对比和封面来源/只读合同。
- 前端受影响四个文件 39 passed，TypeScript/Vite build 通过；现有分块大小提示不是失败。
- 新运行副本使用旧已验证联合副本的 Online Backup，复用有界证据与实际封面资产的 APFS 副本，不重复全库采集或写正式数据。
- 本轮 Online Backup 的 81/85→88 与重复迁移通过；注册表 1..88 连续、463 个触发器，integrity ok / FK 0，受保护原始表行内容一致。运行副本保持 60 份完整目录/位置证据、154 份 Album 艺人证据，复用已审阅的有界选择，未继续 API 采集。
- Records、原版 membership 和自动归并计划与历史已验证副本一致；完整门禁及专项后再次核对，正式源 schema 81 / 副本 88，plays 94,760、tracks 10,026、raw track_artists 10,496、自动署名 8,969、人工覆盖 36、有效署名 11,787，项目/归并/周榜有序行内容指纹均保持。维护不会新增播放贡献或批准身份。
- 搜索当前支持的四个精确变体 ready、repeat-safe；使用 `--statistics-reuse-only` 重新确认，没有冷重建。
- 默认完整全栈 `20261003T070853.211207Z-f917b9718886`：full 模式全部八个必需阶段同轮 PASS，1,360,570ms（22分40秒）；seed 3,231 passed / 2 skipped / 5 warnings，真实 integration 186 passed / 1 skipped / 1 warning；前端全量 726 passed / 4 skipped，API 157/157、边界 113/113，22 轮 500ms 热请求门槛与 Chromium/Firefox/WebKit 通过。没有 `--only`、`--from`、跨浏览器跳过或三次效率验收。八阶段分别 7,518 / 64,093 / 456,196 / 159,274 / 399,976 / 79,866 / 45,928 / 147,594ms。
- summary 的 git_head 为上述代码 SHA；dirty=true 仅因继承未跟踪的开发状态总表，业务 tracked diff 在运行前后均为空。规范 summary、OpenAPI 审计、benchmark、seed/integration JUnit 等 14 个 run 文件在结束时已复制至 ignored `output/album-final/run-artifacts/`，完整日志和兼容 summary 同时保留，不依赖系统临时目录长期存在。
- 实际 Chromium 1440×1000 / 390×844：Glee 106/1、Midnights 86、Mimi 14共享/6独占与 Track 2 / Disc 1，两端实际点击 Sabrina 并返回；嵌套链接 0。8 个测量结果横向溢出 0、console warning/error 0，手机对比按钮 62×44px。桌面 Glee 请求 `.320.webp`、手机请求 `.640.webp`，图片实际正常显示；本运行资产尚未补建这两档，使用合同内的原图回退，不能据此宣称本地变体齐备或图片体积已下降。三档 WebP 读取/回退合同由专项与完整后端覆盖。这两次视口测量 DPR 都为 1，DPR 选择另由封面单元合同覆盖，不冒充物理手机/高 DPI 实机验收。主要截图已视觉复核。
- 专项证据在 ignored `output/playwright/album-final/`；新数据库、资产、缓存、真实截图均不进入 Git。浏览器 session、专项锁和本任务临时服务已关闭。

本轮保留的边界：seed 的 5 warnings 包括 LibreSSL、HTTP 422 弃用，以及 `ai_task_service.py` 后台线程访问测试临时库时出现的 disk I/O warning（与早期历史轮相同）；实际 integration 只有 LibreSSL warning，没有扩大任务修改 AI 运行时。一次辅助迁移脚本引号错误与不支持的 CLI 参数在实际门禁前终止，修正后重新完整执行；专项首次桌面标题定位及手机 presentation 重挂载后的旧候选定位失败，按 fresh snapshot 修正标题/重新检测后重跑，保留失败文件，未改产品代码、未把失败拼为 Pass。

## 真实问题与现有消费者

名称含逗号的实际样本与 JOLIN / Jolin Tsai 人工 canonical 532 暴露了名称拆分/名称验证的不可靠边界；稳定 ID 使顺序、来源名称与身份分离。`_verify_album_artists` 的请求失败放行也在代码和回归中确认并修复。现有发行周期、版本补取/对比、Album Project 归并、Records、Billboard 和元数据健康改为稳定身份及明确 legacy/未解析状态；Album 不替代 Track 艺人。

同名不同 ID 在 Track 缓存有旁证，但本轮没有观察到 Album 实际误关联；同一 ID 历史改名的 Album 实样也未观察到，二者由合成身份测试覆盖。Cats Album 的 Andrew Lloyd Webber/剧组是真实未解析证据，继续待审核，不能用 Taylor 的 Track 署名替代。旧 ID 集合冲突、字段缺失、刷新失败均保留可靠旧证据；名称与顺序变化不意味着角色变化。

旧 `7b9a1f4e` 候选完整八阶段通过仅见[历史联合报告](2026-10-03-album-metadata-integration-verification.md)，不能外推本轮 `814ea7cb` 整合、生产验收或三次效率验收。

## 发布交接边界

取得最终固定 SHA 后，正式发布仍须独立授权。先记录生产现有版本与 schema，Online Backup 并保存 SHA-256/完整性；正常生产 schema 85→88，先在副本迁移并确认连续注册表、幂等、FK 和守恒，失败联合回滚代码与备份。

目录维护 CLI 默认只审计；Album 艺人 CLI 要求明确源库、新输出副本和有界 limit，只在新副本写入。先限定现有缺口/被消费发行位置并预览，再有界补目录及 Album 艺人证据；正式发布数据另走经授权的副本审阅与切换。保存 run ID、成功/拒绝/失败/未解析数量；冲突保留已有可靠证据，身份缺失保持待审核，不全库重抓、不自动批准身份或归并，不修改 plays/tracks/raw track_artists 或 Track 有效署名。正式回填后验证 revision/快照及实际消费者；发布三模式、健康、搜索 ready 快照和回滚门禁另存证据。

## 安全合入窗口

2026-10-03：只读确认“优化榜单页面图片加载速度”会话已完成，提交/推送及验收隧道收尾结束，主目录无仍依赖代码的后端/前端服务。实时 main 为 `85a44cb888272d6229297d883af4f05dfd271e12`；相对 `814ea7cb` 只有封面报告、方案归档与规则/索引增量，业务代码未变化。隔离候选逐段吸收这些文档，保留其归档路径与发布记录；最终业务内容仍等于已完整验收的 `8464ffa6`。main 已 fast-forward 到 `824b2250b4e9fb37f351e9235a5654db52460aab`：五份重叠文档采用精确路径 stash 保护、三方内容恢复，未使用整树 reset/clean 或宽泛 stash。重叠之外的全部已有修改/删除/未跟踪文件及文件模式逐项保持，暂存区为空；只在台账消除本任务两个旧 OPEN 重复行，日期精度 003 保持。完整保护点与恢复 diff 在 ignored `output/album-final/main-preservation-85a/`。主目录 225 / 隔离目录 220 份 Markdown 审计及 diff 检查通过，AGENTS/CLAUDE 一致。后续收口仅更正文档状态，不改变已验收业务代码；本任务的临时保护 stash 在恢复核验后清理，其他已有 stash 保留。
