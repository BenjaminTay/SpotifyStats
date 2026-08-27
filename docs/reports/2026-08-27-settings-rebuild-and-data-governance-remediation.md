# 设置重建状态与数据治理修复交付

> 状态：**Pass（功能范围）**
> 证据日期：2026-08-27
> 范围：设置重建状态、导入健康口径与呈现、只读治理预览、导入前检查、Desktop/Phone 设置页。

## 交付结论

- 重建完成后，后端响应返回持久化的 `rebuild_pending=false`、核心聚合状态和完成时间；前端把结果写入 settings query cache，再重新读取后端校验。页面局部 `rebuildPendingOverride` 已删除，离开设置页再返回不会复用旧 pending。
- Album Project 健康检查与实际构建器复用同一个资格判定。明确的 single / compilation 属于“按规则无需建立项目”，不再被算成治理问题；真实 album 缺 membership 的正例仍由单元测试覆盖。
- 健康 API 增加产品层 `summary`，问题项拆出影响范围、用户状态、可读解释和动作。页面先回答“核心统计能否正常使用”，再分别展示需要处理、历史建议、说明与折叠的技术详情。
- `POST /api/import/governance/cleanup-preview` 只读返回当前修订、预览令牌、有界样例和预计动作；契约测试锁定调用前后播放数量不变，并覆盖 `sample_limit` 的 1–100 边界。
- 导入前检查增加 `comparison_status` 与 `record_delta_comparable`。缺少旧指纹基线时隐藏新增/移除 KPI，改为解释首次建立识别基线；日期相交但共同记录为 0 时显示中性“边界相交”，真实重复单独提示。
- Desktop 导入区改为三步流程和分组文件详情；Phone 显示核心统计同步状态，并明确样例查看与治理操作需要电脑端完成。

## 真实数据库只读证据

当前主库探针全程使用只读连接：

| 检查 | 结果 |
|---|---:|
| 播放记录 | 92,908 |
| 产品结论 | 数据状态良好，核心统计可以正常使用 |
| `safe_to_use` | `true` |
| 缺少 Album Project 的近期合格专辑 | 0 |
| 近期合格专辑 | 501 |
| 按规则无需项目的近期专辑 | 233 |
| 当前外键残留 | 0 |
| 说明项 | 237 条音频记录缺少曲目实体 |

237 条记录保留为原始来源说明，不进入自动整理候选。外键残留已经由同日另一项独立授权任务清理；本轮没有对主库执行删除、导入或治理写入。只读清理预览返回空目标组及 `writes_performed=false`。

当前 preflight 返回 `comparison_status=baseline_missing`、`record_delta_comparable=false` 和 `detected_relation=baseline_required`。输入包含 92,908 条记录，但该数字不再被解释为真实新增；5 组日期重叠均为 `boundary_only`，共同记录数为 0。

## 浏览器验收

使用独立启动的当前代码与真实本地数据验收：

- 1440×900 Desktop：数据区显示绿色“数据状态良好，核心统计可以正常使用”，当前问题 0、历史建议 0、说明 1；运行检查后显示首次建立基线说明，未展示不可比较的新增/移除 KPI。
- 真实重复 67 条使用琥珀提示；5 组只有日期边界相交的文件显示为中性“未发现相同记录”；13 个串流文件和 9 个账号文件按组折叠。
- 390×844 Phone：显示“核心统计已经同步”和 92,908 条播放，明确完整健康详情与历史样例在电脑端查看。
- 两个视口均满足 `documentElement.scrollWidth === innerWidth`，无横向溢出；浏览器控制台 0 error、0 warning。

## 自动化验证

- 修复定向后端：45 passed；新增 OpenAPI 操作与参数审计回归：37 passed。
- 前端完整回归：75 files / 583 tests passed。
- 前端生产构建：Pass。
- 完整后端 unit/contract：1,760 passed；完整套件启动后新增的重建持久状态契约另行定向运行 1 passed。首次运行的 4 个失败均为新接口缺少 OpenAPI 操作/参数证据登记，补齐正式契约覆盖后归零。
- Ruff、文档审计和 `git diff --check` 纳入本次收口。

未运行默认完整 `fullstack_verification_check.sh`，因此本报告只标记功能范围 Pass，不声称项目级默认全栈 Pass。未执行 commit 或 push。
