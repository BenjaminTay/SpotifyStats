# L1 导入防复发、时长解析与人工归并刷新收口

> 证据日期：2026-09-13
>
> 实现状态：IMPLEMENTED（本地提交 `e251148a`）
>
> 真实数据库治理：NO-OP BY EVIDENCE
>
> 完整门禁：PASS；push / 部署见后续发布报告

## 1. 结论

本轮收口了两个独立问题：

- 新出现的 Spotify Track ID 不再仅凭“艺人 + 曲名”永久复用旧 owner；导入会先建立独立 track/L1
  投影，重复出现的同一 provider ID 继续稳定命中同一 owner，之后只允许确定性 L2/L3 治理建立版本
  关系。
- 播放参考时长统一为“事件当时的 provider 版本 → 当前 Track primary provider 版本 → legacy
  `tracks.duration_ms` → unknown”，音乐档案的共享播放适配器和音频/视频统计使用同一 SQL 解析器。
- 人工专辑关系确认把专辑、歌曲关系、Album Project 和 L3 归属放进一个 SQLite 事务；批次结束只刷新
  一次，失败整体回滚。响应会记录 targeted/full、影响数量、fallback reason 和 Billboard 后台 job ID。

## 2. 自动化验证

- 导入、L1/L2、音乐档案、Album Project 与人工关系定向组合：162 passed。
- 更宽的音乐档案与治理组合：126 passed。
- 人工专辑关系专项：20 passed，包含派生刷新失败时专辑和歌曲关系同时回滚。
- Ruff check、Ruff format、mypy、detect-secrets 与 `git diff --check`：PASS。

小型 contract 夹具中，影响闭包超过 25% 安全阈值时会返回
`strategy=full, fallback_reason=closure_too_large`；这属于预期的显式保守回退，不会伪装成 targeted。

## 3. 真实数据库副本复审

对 `data/spotify_stats.db` 使用 SQLite Online Backup 创建：

`data/backups/spotify_stats_20260913_before-l1-review.db`

备份 `PRAGMA integrity_check=ok`，播放记录为 92,908 条。随后在备份和真实数据库上分别以只读模式运行：

```bash
.venv/bin/python scripts/audit_l1_external_identity_risks.py <db> --simulate
```

两次结果的 summary 和 confirmation token 完全一致：

| 项目 | 结果 |
|---|---:|
| 多 Spotify ID owner | 817 |
| keep | 217 |
| review | 600 |
| 可安全 split/relink 操作 | 0 |
| 模拟状态 | pass |
| 原始播放保持 | true |
| identity health regression | 0 |

600 个 review 中仍以缺少唯一目标、缺少独立本地投影和 provider 身份需要独立 owner 为主要 blocker；
现有证据不能证明任何一项可安全自动拆分或 relink。因此本轮没有对真实数据库执行写入，也没有为了
“清零”而放宽规则。代码防复发已完成；存量队列等待未来出现新的 provider/人工证据后再重新分类。

## 4. 发布边界

- 该实现当前已 commit，但本报告生成时尚未 push 或部署。
- Online Backup 保留在本地忽略目录，不进入 Git 或镜像。
- 当前提交的默认完整全栈门禁与本地真实 Agent smoke 已通过；远端和生产状态见
  [`2026-09-13-development-closeout-and-release.md`](2026-09-13-development-closeout-and-release.md)。
