# 开发分支、历史补丁与共享文档整理

> 后续处置（2026-10-20）：已结束分支和整合工作树现已清理，本地/远端仅main。本文保留10-12历史记录，当前清单、源码恢复引用及旧归档目录缺失边界见[最新清理报告](2026-10-20-development-branch-worktree-closeout.md)；下文旧归档路径不表示本轮已验证可恢复。

2026-10-12，主线业务基线 `9468bb48`。本轮只整理开发约定、共享状态、历史候选及本地 Git，不合入未通过准入的产品实验。当前生产的最后保存证据仍是 `4f3f2ac0`：详情首次 89/90，整体 OOM 与手机弹层问题开放。

## 整理结果

此前一轮已移除 14 个本地分支、10 个实际工作树并清理一个失效登记，本地 main 同步到 `9468bb48`。其恢复材料位于本机归档 `spotifystats-cleanup/20261012T155400`。随后详情负责人为新定位建立 `album-rank-cost`，本轮开始时共 8 个本地分支、7 个实际工作树。

本轮移除 5 个本地分支、4 个实际工作树，保留以下 3 个分支与 3 个工作树：

| 分支 | 责任与状态 | 下一步 |
| --- | --- | --- |
| `main` | 统一业务基线和共享文档；本轮形成文档整理检查点 | 按用户授权推送；本轮无生产发布 |
| `codex/album-rank-cost` | ACTIVE；「排查详情页榜单成绩加载慢」为唯一研发负责人 | 有界定位 Top 250 统计、切页后的排名计算及启动驻留，当前未证明根因或完整通过 |
| `codex/versus-detail-integration` | 统一整合工作树；对决研发已结束，保留正式验收材料与现成 rank manifest | 供当前研发读取与后续整合，不启动独立对决研发 |

当前研发 runtime 保留原位置。六份跨任务状态文档在 main 统一整合，研发工作树的重复副本由协调方精确同步，后续研发只维护业务补丁和专项材料。

## 已移除分支的处置

| 原分支 | 处置 | 本轮归档 slot |
| --- | --- | --- |
| `codex/detail-backend-contention` | ARCHIVED；前端设置加载候选专项与完整门禁通过，端到端收益未证明，不采用 | `frontend` |
| `codex/album-identity-json-batch` | ARCHIVED；功能通过，受控实验资源准入 NOT_MET，未跑默认完整门禁，不采用 | `json` |
| `codex/album-identity-targeted` | ARCHIVED；功能与结构性收益有证据，整体资源准入 NOT_PROVEN，未跑默认完整门禁，暂不采用 | `targeted` |
| `codex/detail-resource-budget` | ARCHIVED；旧 OOM 混合补丁完成逐文件对照与残余候选提取，不整体合入 | `resource` |
| `codex/diagnose-ci-unit-hang` | ARCHIVED；独有提交的主要修复已进入主线，保留历史与差异后关闭本地分支 | `ci` |

四份 dirty 工作树共 67 个变更文件全部保存为原始状态、tracked/staged binary patch、变更文件副本与未跟踪文件；各 slot 保存原 HEAD 恢复引用。被忽略的 output、构建产物及运行材料使用同文件系统 rename，inode 保留，不跟随环境符号链接。旧失败、原时间和原收据保持原样。

当前消费者的 6 个依赖已逐项迁移验证，`prepare_profile.py` 更新为归档路径；当前工作树的 `output/album-rank-cost-acceptance/archive-locations.json` 保存原路径映射。迁移前负责人确认当前准备完成、剖析后端未启动，暂停旧路径依赖运行；迁移后已通知恢复。

## 提交吸收的明确对应

| 来源 | 主线对应 | 判定依据 |
| --- | --- | --- |
| 分页 `4f9a01ff`、艺人身份 `8f638494` | 联合提交 `ad9cc3c6`，最终验证代码 `8464ffa6` | [专辑联合整合报告](2026-10-03-album-metadata-delivery.md#专辑证据与最新封面主线最终本地集成验收)及提交正文记录固定输入 |
| CI 共享连接修复 `d3400023` | `49bfadfd` | 三个 snapshot service 的该次提交补丁逐字一致 |
| 单测诊断 `06f43628`、契约诊断 `06c4cc28` / `63e0c376` | `e06b2d4d` / `49bfadfd` 与其后主线 | 当前 reusable quality workflow 与旧分支完全一致 |
| Linux 空 WAL `eb5e97d9` | 契约边界 `49bfadfd`；相关持久缓存测试 `e06b2d4d` | 当前测试保留空 WAL 处理并有后续合同扩展；完整差异保存在 CI slot |

CI slot 保存 5 个独有提交的 format-patch、旧分支到当前 main 的相关文件差异和判定收据。没有再次合入同一修复，远端 CI 分支保持原 SHA。

## 历史 OOM 补丁的取舍

旧工作树基线 `34f22db9`，37 个变更路径逐项与 `9468bb48` 比较：2 个文件与当前 main 完全相同，5 个文件当前 main 不存在，30 个文件内容不同。“不同”不等于整份文件应合入。

| 内容 | 处置 |
| --- | --- |
| `cache_manager.py`、Billboard `data_loader.py` | 与 main 完全相同，已覆盖 |
| `frame_cache.py`、loader 接线及旧详情/前端实现 | 当前 main 已有后续缓存预算、目标发布和取消信号实现；旧 frame cache 缺少当前 generation 防回填保护，旧前端缺少当前 AbortSignal 传递，禁止整体覆盖 |
| `resource_budget.py`、job queue / warmup / yearly 接线 | 跨进程重计算串行锁未采用；必须同时审查嵌套构建、singleflight 顺序和年度线程，不单独移入一个锁文件 |
| 年度 `project_entity_input`、records compact 与 analysis/entity 输入裁剪 | 未采用候选；已提取逐文件补丁，当前负责人只有在新驻留定位证明需要时，才按当前 main 提取最小改动 |
| 旧资源测试、规则、报告及共享文档 | 原样归档；旧版本本地通过不代表当前版本或生产通过，不回写旧状态覆盖新主线 |

全部 37 项的内容对照和处置在 `resource/residual-review.json`，产品逐文件补丁在 `resource/residual-patches/`。整体 OOM 仍由原事项 `SS-2026-10-08-001` 跟踪，不另开一套旧资源研发任务。

## 本机恢复与验证

本轮独立归档根：`~/.codex/archives/spotifystats-cleanup/20261012T082400Z`。入口为 `README.md`、`manifest.json`、`path-map.json`、`removal-receipt.json` 与最终 `completion-receipt.json`。原始运行数据不进入 Git。

恢复时从对应 `refs/codex-archive/20261012T082400Z/<slot>` 建立新的隔离工作树，应用该 slot 的 `tracked.patch`，按 `snapshot.json` 恢复未跟踪文件；使用迁移后的证据路径。不要把旧文件整份恢复到当前 main。

本轮验证范围是文档审计、AGENTS/CLAUDE 一致性、diff 检查、项目 hooks，以及补丁/文件保存、依赖位置、Git 分支/工作树与干净主线核验。产品实验没有被本轮合入；其历史完整门禁、专项和资源结果仍分别归属于原候选。
