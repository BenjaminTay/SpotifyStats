# 已结束分支与工作树清理收口

日期：2026-10-20。用户明确授权清理已经合并或明确不采用的本地、远端分支及多余工作树，保留必要恢复引用与历史stash，并同步文档。

## 结果与范围

清理基线为main `f284d7d06f0a9eb59f963f85f2243d059ec78216`。删除2个本地分支、6个远端分支和1个多余工作树后，本地与远端仅保留main，实际工作树仅保留 `/Users/benjaminlei/Code/202605-SpotifyStats`。清理完成时main的HEAD未改变，文档修改当时尚未提交；用户后续明确授权将7份清理文档提交、推送并确认CI，本报告随该文档提交保存，交付SHA和CI结果按实际Git/GitHub记录核对。

没有合入旧实验、修改业务代码、执行应用测试或生产操作。OOM事项SS-2026-10-08-001继续OPEN / OBSERVING，按[精简计划](../plans/2026-10-19-performance-scope-and-memory-closeout.md)仅保留正常使用观察；分支清理不代表稳定性观察完成。

## 分支逐项处置

下表中的名称均省略 `codex/` 前缀。完整SHA用于按需恢复分支；已合入的提交继续由main历史保留。

| 位置 / 分支 | 删除前HEAD | 判定与恢复来源 |
| --- | --- | --- |
| 本地 `album-rank-cost` | `bfecef520535d25f1adb06a912280fd89d3e0431` | 采用的5业务文件、16回归文件与main逐文件完全一致，经c844→6805精简吸收；schema91、分配器环境、实验工具等明确未采用。新增专用恢复引用保留全部已提交源码 |
| 本地 `versus-detail-integration` | `66ad5e600b0cc4b09ac8c3886fdfeaa88da91768` | 已是main祖先，没有独有提交，只落后一笔文档提交；由main历史恢复 |
| 远端 `album-production-delivery` | `daf098ca035b5c587bb544a0ef0fb6c572514a98` | 已是main祖先 |
| 远端 `album-rank-cost` | `b126020862fabb968db1974d38145b99d119ee86` | 远端仍是早期已交付版本，已是main祖先；较新本地候选另有恢复引用 |
| 远端 `diagnose-ci-unit-hang` | `63e0c376cb9ac18cf7851d9ffb4122b7e7ae6299` | 5个独有提交的修复已吸收或被后续实现覆盖，不整体合并；复用既有CI恢复引用 |
| 远端 `music-detail-chart-performance` | `47147879287ca8e79cae257bc254b57402380865` | 已是main祖先 |
| 远端 `track-credit-resolution` | `e4929e812f90cfc5dfa9e42ef731b11b5897ff75` | 已是main祖先 |
| 远端 `versus-detail-integration` | `6805fe4ce4151052ec7cb61582cea8495a03ec27` | 已是main祖先 |

CI分支再次核对：`ci-quality.yml`和`reusable-quality-checks.yml`与当前main一致；d3400023中三个snapshot service的连接修复与主线49bfadfd对应补丁的稳定patch-id均为 `309f219041b4846faa3b1928e3ab0d28d8c18502`；当前公开快照契约仍保留空WAL排除。其他发布workflow已有后续变化，不用旧分支覆盖。历史逐项取舍见[10-12整理报告](2026-10-12-development-worktree-closeout.md)。

远端删除使用一次原子push，为六条分支分别指定删除前完整SHA的force-with-lease，避免删除检查后又被更新的分支；成功后通过 `git ls-remote --heads origin` 确认仅main。没有推送归档引用，也没有触发应用发布。

## 工作树处置

移除 `/Users/benjaminlei/.codex/worktrees/versus-detail-integration/202605-SpotifyStats` 前确认tracked、staged和untracked变更均为空，未发现引用该路径的运行进程或进程工作目录。ignored内容仅为 `.mypy_cache/`、`.pytest_cache/`、`.ruff_cache/`、`frontend/dist/`及两个环境符号链接；没有output、数据库或待保存报告。

使用普通 `git worktree remove` 移除工作树；`.venv`和`frontend/node_modules`仅为指向主目录的符号链接，没有跟随删除目标，移除后主目录两项依赖仍存在。删除本地整合分支时，`git branch -d`因其upstream落后而拒绝；再次确认该分支是main祖先后，使用 `-D` 删除。研发分支则在恢复引用验证完成后删除。

## 恢复引用与stash

新增本地引用：

```text
refs/codex-archive/20261020-closeout/album-rank-cost
  -> bfecef520535d25f1adb06a912280fd89d3e0431
```

保留原5个 `refs/codex-archive/20261012T082400Z/` 引用：`ci`→63e0c376，`frontend`、`json`、`targeted`→9468bb48，`resource`→34f22db9。六个恢复引用仍在本仓库，不属于活跃开发分支，也不是异机备份。

如需查看未采用的研发源码，可从恢复引用创建隔离工作树，不要整体覆盖main：

```bash
git worktree add --detach ../SpotifyStats-archived-source \
  refs/codex-archive/20261020-closeout/album-rank-cost
```

本轮没有执行恢复或重新启动实验。其他已合入分支可使用上表SHA建立新的分支。

两个历史stash的顺序、对象SHA及说明保持原样：

- `stash@{0}`：`e2f955df86f419d65af991f7975f91b193b6e2a6`，`preserve-v6-original-plan-before-local-integration-20260927`。
- `stash@{1}`：`8508d7e3be097948049ca4d243438b11f3fe2cce`，`preserve-local-fix-changes-before-playback-branch-split`。

**源码恢复与运行证据分开判断。** 历史报告记载的 `~/.codex/archives/spotifystats-cleanup/`、`~/.codex/archives/spotifystats-delivery/`目前不存在；本轮未删除或重建这些目录。Git恢复引用只保证对应已提交源码仍有引用，不能恢复缺失的dirty补丁、未跟踪文件、数据库或ignored运行材料。本次被移除工作树没有这些待保存材料；更早归档的当前位置和可恢复性仍未核实，不将其描述为本轮已验证可恢复。

## 核验

- 清理完成时本地仅main、实际工作树仅主目录；远端heads仅main，SHA均为f284d7d0。后续文档提交不改变上述分支和工作树数量。
- 21个采用的业务/回归路径与源候选一致；已合入分支祖先关系、CI吸收依据、源码恢复引用及两个stash逐项核对。
- 上次文档提交f284d7d0的[CI](https://github.com/BenjaminTay/SpotifyStats/actions/runs/39279338893)已成功，文档审计、后端unit/contract、lint及前端测试/构建均success；不将其作为本轮新文档的CI。
- 本轮281份Markdown文档审计、AGENTS/CLAUDE一致性及diff检查通过；恢复引用、stash、唯一分支/工作树、主目录依赖和暂存区为空的核验通过。不重复应用测试或资源实验。
