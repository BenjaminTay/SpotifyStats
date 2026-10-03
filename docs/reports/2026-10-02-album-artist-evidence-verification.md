# 专辑艺人稳定 ID 与有序证据：本地验证

> 事项：SS-2026-09-24-002；开始 2026-10-02，最后核验 2026-10-03。
> 基线：`fa683d97`；隔离工作树 `/Users/benjaminlei/Code/202605-SpotifyStats-album-artists`（分支 `codex/album-artist-evidence`）。
> 实现：IMPLEMENTED；验证：PARTIAL（本地专项完成）；仓库：COMMITTED（本次本地提交登记） / UNPUSHED；部署：NOT_DEPLOYED。
> 本任务代码 patch SHA-256：`d0bb43d9229f1b02e009e024c76e0e53fc9aa355692dec5e21b2ea4e5eaf5408`。完整任务 patch 还包含下述文档登记。

## 当前结论

已经实现独立的 Album 有序证据、稳定 ID/canonical 解析、冲突保留、全部发现的写入口和现有消费者修正，并完成增量迁移、数据库副本、单元/合同和文档验证。没有修改前端代码、启动全库 Spotify 采集或执行正式库迁移/回填。此报告不是默认完整全栈 Pass，也不是生产验收。

## 调查：真实样本与理论风险

正式源库以 SQLite `mode=ro` 读取并通过 Online Backup 创建演练副本。源 schema 81，有 3,234 个 Album 元数据记录、10,215 条 Track provider artists 记录。

| 类别 | 当前证据 | 判断边界 |
| --- | --- | --- |
| 名称含逗号 | Album 缓存及真实 API 均有 `Earth, Wind & Fire`、`Tyler, The Creator`；API ID 分别为 `4QQgXkCYTt3BlENzhyNETg`、`4V8LLVI7PbaPR0K2TGSxFF` | 旧逗号拆分会把完整名称拆碎，发行周期/Billboard/Records 名称判断出现确定的假阴性；未声称重算了正式榜单影响总量 |
| 名称与人工本地身份不同 | `Ugly Beauty`（`7HFFEjrwzZNpbee44SJnn9`）Album API 返回 `JOLIN` / `1r9DuPTHiQ7hnRRZ99B8nL`，本地 `Jolin Tsai` / artist 532；现有 canonical map 解析为 532 | 旧名称 token 比较为 false，新解析为 verified_id；这是名称/别名差异，不能据此声称已证明历史改名时间 |
| 多艺人 Album | `Live At The Troubadour` 的有序 Carole King / James Taylor；`A Star Is Born Soundtrack` 的 Lady Gaga / Bradley Cooper；`BREAK MY SOUL (THE QUEENS REMIX)` 的 Beyoncé / Madonna | 已有真实 Album arrays，不从逗号数量推定人数，也不据顺序推定 primary / featured |
| 同名不同 Spotify ID | Track 缓存有 Jacky Cheung、Michael Wong、胡歌三组同名不同 ID | 是当前数据库中的稳定身份风险旁证；未把 Track arrays 冒充 Album arrays，也未证明这三组 Album 实际发生误关联 |
| 同一 ID 对应不同名称 | Track 缓存的 ID→credited_name 分组未发现多名称；JOLIN 样本是来源名称与本地名称差异 | 时序改名作为合成回归场景验证，不虚构真实改名案例 |
| 缺失/无法唯一解析 | 69 个本地艺人缺直接 Spotify ID；有 Album→本地 Jolin Tsai 缺直接 ID 的样本，但可通过 existing external IDs/canonical 唯一解析 | 缺直接投影不等于无法解析。外部 ID 多本地成员的真实样本经 canonical 折叠后，当前歧义 ID 数为 0；未把已治理的别名误报为冲突 |
| 缺失或冲突数组 | 旧库全部 Album 无本任务结构化证据；7 个有界 API 样本无缺失 artist ID 或冲突数组 | 缺失 ID、同 ID 多 canonical、重复 ID、ID 集合冲突等通过合成测试覆盖；不声称在真实 API 样本中发现这些情况 |

缓存中 328 个 Album 名称字符串含逗号，混合了多人署名和单人名称内逗号，不能当成多艺人专辑数量。只读审计未全库联网；API 先取 6 个对象并重复同一有界样本验证幂等，再取 1 个 JOLIN 别名样本。

## 数据合同与代码范围

三张增量表分别保存证据集合、按顺序的 ID/名称成员、追加审计。来源入口、可选 run ID、获取时间和签名在集合层；数组和拒绝原因在事件层。首次缺 ID 可保留 unresolved；后续缺失/冲突保留可靠旧值。重复观察不改事实 revision。解析只使用持久 ID 关联及现有活动 canonical map，Album 不按名称创建/合并艺人，不改人工 external ID 证据。

| 链路 | 本次处理 |
| --- | --- |
| `spotify_refresh.upsert_album_batch` | 接入共同证据保存和显示投影；证据拒绝时不更新旧显示；支持 source run ID |
| `version_merge` Album API 补取 | 保留 Album 原始 artists 对象，写入相同边界；忽略未请求的 Album ID；不实施曲目分页 |
| `release_cycle` 批取/搜索 | 同一写边界；稳定身份验证；请求/token 失败不再放行；搜索同名 Album 时 ID 优先，旧名称只是兼容候选 |
| `fetch_covers` | 同一写边界；REPLACE 改为 UPSERT，保留父记录、证据及其他曲目表字段 |
| Billboard 元数据 | 按 Album 证据和 canonical 判断；无证据的旧行明确走 legacy，整名匹配先于逗号分词 |
| Album Project / import health | 既有按标题找候选的 SQL 共用一次预读 ID/canonical 投影；存在证据时不再以名称子串充当身份判断 |
| 原声带 / Various Artists 残余项目 | 新证据只有唯一单 canonical 时复用身份；不挑数组第一人、不创建拼接多人艺人；legacy 单名称行为保留，歧义名称不任选首行 |
| Album Project 自动归并 | 有证据时 family/fingerprint 与持久 artist key 使用 canonical 集合；未解析跳过；legacy 保留完整曲目证明。policy 为 `spotify_complete_release_v3_album_artist_ids` |
| Records 完整重播原版信任 | 实际 `load_original_memberships()` 读取 ID/canonical；改名不失去可信结果，同名错误 ID 被拒绝；旧 schema 查询数量保持常数且 ≤5 |
| 歌曲归并列表与专辑曲目比较 | 去掉 Album provider/本地专辑艺人对歌曲艺人字段的回退；复用已有 Track 有效署名/Track evidence，缺失时留空，不开发第二套 Track 署名 |
| revision / cache | Analysis、健康依赖加入 Album credits 与 external IDs；Billboard、发行周期内存 cache 纳入身份 revision；年报准备 LRU、持久 prepared-key 及 scoped digest 均纳入依赖，内容版本为 `yearly_review_v2_18_album_artists` |

Album evidence 不进入歌曲有效署名，不新增播放贡献，不恢复发行周期/艺人生涯等隐藏前端入口。人工项目和身份治理优先级保持原规则。

新增 migration 88（未占用分页工作树的 87），只创建表和安装现有 revision 合同；没有从旧字符串伪造稳定 ID。旧库经过 85 的当前 revision 安装时先幂等创建需要的增量表，再由 88 登记正式迁移。新库 SCHEMA 与 seed 已同步。副本回填工具只写 Album 证据/兼容字符串及必要的元数据父行；CLI 强制创建新 Online Backup，不提供正式库写入模式。

## 本地验证证据

使用主仓库现有 `.venv/bin/python` / pytest / ruff 在隔离工作树运行，没有安装新依赖。

| 验证 | 结果与范围 |
| --- | --- |
| 专项 `test_spotify_album_credit_evidence.py` | 最终 21 passed：有序、来源、幂等、同名不同 ID、改名/逗号、缺失/冲突、canonical 与 undo、strict/legacy、真实消费者、缓存 revision、失败与回滚、原始/有效署名不变、全部补取写入口、歌曲显示不回退 Album |
| 相关后端选择 | 250 passed / 23.66s；包括当时 19 项专项和 231 项 metadata refresh、release cycle、album auto/targeted rebuild、Records、migrations、import health、governance、yearly/analysis/community snapshots、Album Project/Billboard contract。后补测试与版本比较改动独立复验 |
| 最终歌曲比较与治理合同选择 | 33 passed / 8.88s（最终 21 项专项 + 12 项 `test_version_merge_confirm_workflow.py`）；与上行有重叠，不能相加当作测试总数 |
| Seed 重建 | golden assertions 全部通过，schema 88，现有 seed 数据可读；迁移注册/seed contract 测试通过 |
| 真实副本迁移 | source schema 81 → copy schema 88；重复迁移/旧数据显示兼容均已验证 |
| 真实 API 有界证据 | 首轮 6 observed / 0 failed；复轮 6 unchanged / 0 changed；补充 JOLIN 1 observed / 0 failed；最终副本 7 sets，全部唯一解析 |
| 完整性与外键 | copy `integrity_check=ok`，外键 baseline 0，最终 0，新增 0 |
| 原始与有效事实 | 下表行数与稳定 hash 均不变；最终副本和正式只读源分别与初始副本基线一致 |
| 提交前复验（2026-10-03） | 类型问题修正后专项、歌曲比较合同与自动归并选择共 45 passed / 9.32s；提交 hooks 的 ruff、ruff format、mypy、detect-secrets 全通过；暂存快照 139 份当前 Markdown 文档审计和 staged diff 检查通过 |
| 静态与文档 | 变更代码 ruff、`git diff --check`、`python3 scripts/docs_audit.py` 通过；开发状态、台账、路线、规则、索引及 CHANGELOG 已登记 |

| 受保护事实 | 行数 |
| --- | ---: |
| plays | 94,760 |
| tracks | 10,026 |
| track_artists | 10,496 |
| spotify_auto_track_credits | 8,969 |
| track_credit_overrides | 36 |
| 当前 effective_track_credits 投影 | 11,787 |

pytest 输出有现有 Python/LibreSSL 的 urllib3 warning，没有测试失败。未运行全部 backend unit/contract、Phase 5 或默认完整全栈；没有前端代码/DOM 改动，未安排浏览器验收。

机器证据保存在本工作树的 ignored `output/album-artist-evidence/`：`readonly-audit.json`、`copy-verification.json`、`alias-sample.json`、`final-invariants.json`、演练副本 `real-copy.db`、`code-only.patch` 和 `task-only.patch`。它们不进入 Git；正式数据及密钥未被复制为提交资产。报告中的版本、数量和样本只代表本轮核验。

## 并行边界与尚待完成

主工作区已有未提交文档；分页工作树已有同名文件和 migration 87 修改。桌面 managed worktree 创建未完成，因此采用 Git 创建独立 detached worktree，未覆盖其他会话。主目录的当时文档状态完整复制作为隔离文档基线，继承差异不属于本任务代码；`task-only.patch` 的文档 hunk 相对该冻结基线生成，排除 AGENTS/CLAUDE/README、归档移动和合作曲等其他任务改动。工作区文档审计同时修复了该基线中两个合作曲方案归档链接，只改目标路径；这些关联其他任务的链接与归档未纳入本次提交。提交中的开发状态新文件只登记本事项，工作区的完整总表保留其他任务条目，合入时须整合。提交后的提交号以 Git 记录为准。

待后续整合：`spotify_refresh.py`、`version_merge.py`、db/migrations、revision 和自动归并/Records 等共享文件需逐段合入，保留分页完整性字段/原子发布；migration 88 与 87 均应保留，LATEST_SCHEMA_VERSION / seed 按合入状态重新生成；年报内容版本需统一为覆盖双方改动的版本。该依赖是文件整合与验收依赖，本实现没有调用分页任务的新接口。

本任务范围内的实现、只读调查、副本验证与文档登记已经完成。主工作区未合入，本事项改动已本地提交，未推送/部署。正式源库仍是 schema 81，无 Album evidence；旧名兼容仍存在，strict 发行周期对未回填旧行不声称 ID 验证。正式库迁移、分批回填、冲突审批以及生产快照/消费者验收，需要后续明确授权。不会从此报告推定已完成正式回填或生产验收。

参考：[实施方案](../archive/06-productization-closeout/2026-10-02-album-artist-evidence-plan.md)、[最终规则](../reference/music-metadata-management.md#33-spotify-album-artists-与专辑身份)、[开发状态](../DEVELOPMENT_STATUS.md)、[问题台账](../issues/2026-08-27-issue-register.md)。
