# 专辑分页与稳定艺人证据：联合集成验收

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 基线 main `7b9a1f4e`；固定输入分页 `4f9a01ff`、艺人 `8f638494`。
> 集成分支 `codex/album-metadata-integration`；未新增集成提交、未推送、未部署。
> 当前状态：IMPLEMENTED / LOCAL_FULLSTACK_PASS；联合副本、默认完整全栈和桌面/手机视口验收完成。
> 后续主分支已新增封面提交 `f139ec4d` / `814ea7cb`；本报告仍只覆盖上述固定基线，不宣称包含这些提交。
> 代码 patch SHA-256：`0f5615f7ba61c06794fd0c5b0c2c300ee7e2326c65963b993cf39d64b59d06b0`；八阶段通过后复核一致。61 个任务文件暂存供审阅，集成未提交。

## 最终合同与范围

共同刷新函数同时接收 Provider/token/outcomes 与 source/source_run_id。完整目录/发行位置和有序 Album artists 分别校验、独立保留上一可靠证据；任一数据库写入错误回滚整批，包括显示和审计。版本补取、发行周期及两份维护 CLI 使用相同边界，封面 UPSERT 不损坏父行。Album 不覆盖 Track 署名，不扩散播放贡献，不恢复隐藏页签。

曲目比较的名称与艺人为二元组：本地 owner 复用有效 Track 署名，非本地只读已有 Track provider evidence。位置单独从与当前目录全部匹配的完整发行证据读取；旧完整目录成员可比较，未验证位置为 null。GET 不联网或写入。自动归并与 Records 保留 canonical artist、不同 canonical song 和人工批准边界。

迁移注册表保持 1..88 连续：86 安装专辑语义 revision，87 创建完整目录/位置证据，88 登记 Album 艺人表。86 复用现有 revision/trigger 实现，不是空占位。受控人工 seed 已重新生成，Various Artists 明确作为测试维度，全部 golden 断言通过。年报内容版本统一为 `yearly_review_v2_19_album_evidence`；准备层 revision 与播放来源专辑的目录、艺人和 external ID 触达依赖同时保留。

OpenAPI 从最终集成后端重新生成，并保留当前 main 的艺人署名链接行为。原快照还缺少主分支既有 V6/封面 schema 更新，生成物一并与实际后端合同同步；没有新增相应 AI 或封面业务。默认 quality 的全量 mypy 发现四个既有测试文件对动态 cache_clear 属性的 8 个类型错误，改为 getattr 检查并调用同一个公共属性，未改产品缓存行为、未跳过类型检查或放宽断言。

## 联合副本与真实消费者

正式默认库仅以 SQLite mode=ro 读取，通过 Online Backup 创建副本。源库仍为 schema 81，当前发布代码 schema 85 的升级路径由当前 main 在副本生成，不冒充远程生产数据库快照。

- 旧 81 与发布代码 85 两条路径升级至 88，重复迁移、连续注册表、证据表/触发器、完整性和外键单独核验。
- 固定有界范围为 60 个 Album，包括 47 个目录缺口、3 个 50 首边界及艺人/发行位置样本，存在目标重叠，不能把分类数量相加。全部完整发布；目录 complete 3,187→3,234，partial 12→0，missing 35→0。没有全库重新抓取。
- 艺人样本 7 个重复观察全部 unchanged；逗号名称和 JOLIN / Jolin Tsai canonical 532 均已解析。其余新证据保留真实未解析状态，不伪造身份。
- Lana 来源发行完整 16 个位置，A&W 为 Disc 1 / Track 4，同名曲 Disc 1 / Track 2；旧证据缺失返回未知。Mimi 本地 album 147/243 保持共享 14、豪华版独占 6，本轮显式请求这两发行后位置可信。
- Glee 完整发行 106 首，本地已听 1 首；发布目录不新增本地 track 或播放。
- 原始 plays 94,760、tracks 10,026、track_artists 10,496，自动署名 8,969、人工覆盖 36、当前有效署名 11,787，以及项目/归并关系和周榜聚合的有序行内容指纹一致。修复新增/补齐的 Spotify provider 曲目元数据属于目录证据，不是新增播放。
- 初次真实消费者 before/after：Records 只有 generated_at 不同；可信原版 membership 集合一致；自动归并无新增候选。一个原先 incomplete_track_list 的项目转为 album_artist_identity_unresolved，继续不自动批准。
- 默认全栈真实 integration 发现 Taylor Swift 无 Album 证据时公开只读发行周期返回空，旧测试期望 >10 个发行；没有恢复请求失败放行。为实际消费者在同一副本定向补入 94 个已有关联发行的 Album artists，5 个有界批请求、94 observed、0 failed/rejected，未补 Track 署名或扩展曲目目录。93 个可验证 Taylor 身份；《Cats》Album 实际署名为 Andrew Lloyd Webber 和剧组，两者本地未解析，继续不把歌曲艺人当成专辑艺人。
- 最终真实消费者再次核对：Records 仍仅 generated_at 不同，原版 membership 不变、自动归并候选仍 0；strong evidence 1,307→1,306，album_artist_identity_unresolved 为 2，incomplete_track_list 1→0。这是补入真实 Album 证据后保留身份审核边界，不执行任何自动批准。

副本证据位于 ignored `output/album-integration/`：`joint-evidence.json`、`final-migration-evidence.json`、`repair-selection.json`、`repair-outcomes.json`、`consumer-diffs.json`、`final-consumer-diffs.json`、Taylor 定向 selection/outcomes/unresolved、before/after 消费者、代码 patch 与任务白名单。数据库、密钥、缓存和截图不进入提交资产；唯一受控数据库变更为仓库测试 seed。

## 验证登记

| 验证 | 当前证据 |
| --- | --- |
| 初始相关选择 | 111 passed，属于早期草案 |
| 固定交付相关选择 | 139 passed / 1 fixture failed；历史初跑，不能登记通过 |
| 组合写入与实际只读比较 | 修正必填时间/父证据夹具后 2 passed；独立校验失败与数据库回滚边界 |
| 最终来源艺人/迁移组合 | 49 passed；与其他选择有重叠，不相加为总数 |
| 连续迁移及最终专项 | 99 passed / 14.87s；81/85→88 新副本重复迁移通过，1..88 连续，463 个触发器，原始/项目/周榜事实保持，完整性 ok / 外键 0 |
| Seed | 当前生成器 golden 断言通过，schema 88、同时包含两套证据表 |
| 真实消费者及副本 | 上述有界副本核验通过；不代表生产回填已执行 |
| Hooks | Ruff、ruff-format、mypy、detect-secrets 全文件通过；前端 697 passed / 4 skipped，TypeScript 与 Vite build 通过；最终默认完整门禁另登记 |
| 完整后端 | 最终同轮 seed 3,201 passed / 2 skipped；真实副本 integration 186 passed / 1 skipped；原发行周期断言保持 |
| 默认完整全栈 | `20261003T020011.704402Z-87d26d4d09e5`：full 模式八个必需阶段同轮全部 PASS，1,443,203ms（24分03秒）；API smoke 155/155、边界 113/113、22 轮热请求 500ms 门槛及三浏览器通过 |
| 发行周期真实消费者定向回归 | 定向补证后 7 passed / 14.08s；保留稳定身份门禁与旧断言 |
| 新一轮浏览器 | Chromium 1440×1000 / 390×844；Glee 106/1、Midnights 86、Mimi 14共享/6独占及 Track 2 / Disc 1；两端实际点击 Sabrina Carpenter 并返回，独立链接与中点保留；8 个测量结果横向溢出 0、console warning/error 0，手机对比按钮 62×44px。截图已视觉复核，不代表物理手机验收 |
| 最终事实守恒 | 全栈及专项浏览器后，源库与副本受保护原始/自动/人工/有效署名、项目/归并/周榜行内容指纹仍一致；源 schema 81、副本 88，双方 integrity ok / 外键 0 |
| 文档与交付 | 隔离目录 216 / 主目录 215 份 Markdown（含归档）审计 PASS；工作区及暂存 diff 检查 PASS，AGENTS/CLAUDE 一致；最终文档 Detect secrets PASS，代码 hooks 因仅文档选择而跳过，代码全量 hooks 已在同轮 quality 通过；主目录只更新两事项、相关开发顺序及维护记录，保留同期工作 |

早期 seed 轮记录 5 个 warning，含 AI task 后台线程对测试临时库的 disk I/O error；该线程文件未在本任务修改。最终完整轮 seed 为 4 个 warning（LibreSSL 和 HTTP 422 弃用），integration 为 1 个 LibreSSL warning。最初 runtime 禁用外部封面回退而 integration 临时目录没有本地封面；最终采用项目默认回退设置，并在隔离运行目录使用正式本地封面的 APFS 资产副本，不伪造图片或写正式目录。

早期失败和 BLOCKED 记录独立保留：dataset 参数错误、86 缺口、既有 mypy 错误、未补 Album 证据的发行周期失败，以及两次共享锁阻断，均不拼接为最终 Pass。最终 full 模式命令没有 `--only`、`--from` 或跳过跨浏览器选项；optional 未运行不影响八个必需阶段。阶段耗时依次为 preflight 7,668 / quality 65,106 / backend 517,632 / api 174,450 / routes 400,106 / interactions 80,054 / inventory 45,740 / compat 152,289ms。

持久证据为 ignored `output/album-integration/fullstack-pass.json`（完整 summary 的原样副本）、`fullstack.log`、`final-facts.json` 和 `output/playwright/album-integration/browser-metrics.json`、快照及截图。中断后继续时，原系统临时 run 目录已不存在，单独 benchmark 子 JSON 未保留；上述完整日志及兼容 summary 仍保留同轮状态、计时和请求结果，不重造临时子文件。浏览器最初连接已停止服务出现 connection refused，重启同代码副本服务后完成专项；中点探针因真实换行误判，检查 DOM 后规范化空白重跑通过，未改产品。最终浏览器 session、专项共享锁及本任务临时服务均已关闭。

## 待发布与数据维护

本地整合和验收不授权发布。后续按任务白名单审阅并授权集成提交，取得固定 SHA 后复跑必要检查/CI；生产发布前 Online Backup、schema 85→88、三模式/健康/回滚检查，先有界补目录和被消费发行位置，再按已审核范围补 Album artists，失败/歧义/冲突保留旧值或待审核。记录来源 run ID、成功/拒绝/未解析数量，再验证生产快照与受影响页面，不能无条件全库重抓或擅自修改人工身份。

历史专项：[艺人报告](2026-10-02-album-artist-evidence-verification.md)、[分页报告](2026-10-02-album-track-pagination-acceptance.md)、[分页独立复核](2026-10-03-album-track-pagination-independent-review.md)。当前规则见[元数据规则](../reference/music-metadata-management.md)，范围及文件整合见[集成计划](../archive/06-productization-closeout/2026-10-03-album-metadata-integration-plan.md)。
