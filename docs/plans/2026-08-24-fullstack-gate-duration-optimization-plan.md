# 全栈总门禁耗时优化规划

> 创建日期：2026-08-24
> 状态：P0 编排与 P1 首项低风险去重已实现；25 分钟稳定验收仍为 Partial
> 适用范围：`scripts/fullstack_verification_check.sh`、`scripts/phase5_check.sh`、本地全栈验收及其脚本合同测试
> 基线证据：[`../reports/2026-08-24-fullstack-gate-repair.md`](../reports/2026-08-24-fullstack-gate-repair.md)

## 0. 决策

有必要优化，但第一轮只做低风险的门禁编排改造：缩短失败反馈、消除同一轮中的确定性重复，同时保留默认完整门禁的全部覆盖和发布口径。

本规划把工作分成两级：

- **P0 必做**：阶段化、耗时记录、局部重跑、Phase 5 去重和状态防误报。
- **P1 条件式**：慢测试 profile、安全并行和跨运行证据复用。只有 P0 完成后仍达不到目标，且隔离证据充分时才实施。

不通过减少浏览器、降低等待阈值、削减性能样本或删除真实数据验收来换速度。

## 1. 当前基线与问题定义

2026-08-24 最终一次完整本地门禁约 27 分钟：

| 阶段 | 当前证据 | 诊断 |
| --- | ---: | --- |
| 后端全量 pytest | `474.91s`，约 7:55 | 最慢单命令 |
| Phase 5 unit + contract | `39.37s + 75.04s` | 已被全量 pytest 覆盖，嵌入总门禁时重复 |
| Phase 5 前端测试 | `33.54s` | 必须保留，另有 build、文档和 parity |
| API 审计与性能 | 约 3 分钟 | 必须保留 21 个热样本 |
| 浏览器验收合计 | 约 13:55 | 最大累计类别，晚失败成本高 |

本轮四次完整尝试的后端全量 pytest 累计约 32 分 10 秒。问题不是最终验收覆盖过多，而是：

1. 控件、长列表、性能和跨浏览器错误位于固定串行链路后段；
2. 修复后没有受控的局部重跑入口，只能再次从头执行；
3. 总门禁先执行全量 pytest，随后 Phase 5 再执行 unit/contract；
4. 当前脚本不产出阶段耗时和覆盖状态，无法稳定比较优化前后，也容易把局部成功误写成完整 Pass。

## 2. 目标和非目标

### 2.1 P0 成功标准

- 默认命令仍执行所有必需检查，并且只有这些检查在同一次运行全部通过时才输出 `PASS`。
- 后端测试只通过一次全量 pytest 覆盖，不再追加 unit/contract marker 重跑。
- 可单独运行一个或多个失败阶段；成功时明确输出 `PARTIAL`，不得更新或覆盖完整门禁 Pass 证据。
- 每次运行生成机器可读的阶段清单、状态、耗时和执行范围。
- 三次稳定完整运行的中位数目标不高于 25 分钟；至少应确定性节省当前重复 unit/contract 的约 1 分 54 秒。
- 控件/长列表或跨浏览器晚失败修复后，可在不重复后端、API 和无关浏览器阶段的情况下重新验证。

### 2.2 非目标

- 不改变后端、前端、API 或浏览器测试的产品断言。
- 不降低 API 性能门禁的 21 个热样本和 500ms 阈值。
- 不删除 Firefox、WebKit、移动视口、控件、长列表或横向溢出验收。
- P0 不启用 pytest-xdist，不并行运行共享 SQLite、缓存、开发服务或性能 benchmark。
- P0 不跨 Git 状态或数据 revision 自动复用旧 Pass。
- 不把 `--only`、`--from`、`--dry-run` 或跳过项的运行描述为项目全栈 Pass。

## 3. 目标门禁结构

默认执行顺序调整为先便宜失败、后昂贵验收，但所有覆盖保持不变：

| 阶段键 | 内容 | 是否完整门禁必需 |
| --- | --- | --- |
| `quality` | pre-commit；Phase 5 的文档审计、CI parity、前端测试与 production build | 是 |
| `backend` | `pytest backend/tests/ -q` | 是 |
| `api` | OpenAPI operation/parameter audit、API smoke、boundary、22 次 benchmark | 是 |
| `browser-routes` | 完整路由与重点视口矩阵 | 是 |
| `browser-interactions` | 桌面/移动交互和图表交互 | 是 |
| `browser-inventory` | 控件盘点与长列表 | 是 |
| `browser-compat` | Chromium、Firefox、WebKit | 是，除非明确使用现有 `--skip-cross-browser` |
| `optional` | quickstart、resource snapshot、Web Vitals、preview 矩阵 | 按现有参数决定 |

`quality` 阶段调用 Phase 5 的复用模式，但 Phase 5 单独运行时默认行为完全不变：

```text
fullstack parent
  ├─ pre-commit：Ruff / format / Mypy / secrets
  ├─ phase5 --skip-backend-tests
  │    └─ docs audit / CI parity / Ruff / frontend test / frontend build
  └─ backend：一次完整 pytest

standalone phase5
  └─ docs / parity / unit / contract / Ruff / frontend test / build
```

跳过参数必须打印 `SKIPPED` 及父门禁分工原因。`ci_baseline_parity.py` 继续核对 Phase 5 默认路径包含 GitHub Actions 的完整命令，不因条件分支失去基线保障。pre-commit Ruff 与 Phase 5 Ruff 使用不同版本/参数，不能证明等价，因此本轮保留两者，不为几秒钟收益降低 lint 覆盖。

## 4. CLI 与状态契约

### 4.1 新增入口

建议在同一个脚本增加：

```bash
# 查看稳定阶段键和顺序
sh scripts/fullstack_verification_check.sh --list-stages

# 只重跑一个或多个阶段
sh scripts/fullstack_verification_check.sh \
  --only browser-inventory,browser-compat \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173

# 从指定阶段开始执行其后的必需阶段
sh scripts/fullstack_verification_check.sh \
  --from browser-inventory \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173

# 只检查解析结果和命令计划，不执行检查
sh scripts/fullstack_verification_check.sh --dry-run
```

规则：

- `--only` 与 `--from` 互斥；未知阶段、空列表和重复冲突参数以退出码 2 失败。
- 默认不传阶段参数时，执行完整门禁。
- `--skip-cross-browser` 保持现有兼容行为，并在汇总中记录显式豁免。
- Playwright Python 只在所选阶段包含 `browser-compat` 时探测，局部运行后端或 API 不因缺少 Playwright 被阻断。
- API 和浏览器阶段运行前执行只读服务健康检查；服务未启动标记为 `BLOCKED`，不伪装成测试失败或 Pass。

### 4.2 结果状态

阶段状态统一为：

- `PASS`：所选阶段实际执行并通过；
- `FAIL`：检查执行但断言失败；
- `BLOCKED`：服务或运行时前置条件不满足；
- `SKIPPED`：由显式参数或父门禁的同轮覆盖跳过；
- `NOT_RUN`：不在本次选择范围内。

整体状态：

- `PASS`：当前默认完整运行的全部必需阶段通过；
- `PARTIAL`：局部选择全部通过，或存在允许的显式跳过；
- `FAIL`：任一所选阶段失败；
- `BLOCKED`：所选阶段无法开始且没有测试失败。

### 4.3 阶段报告

新增 `--summary-json`，默认写入 `/tmp/spotify_fullstack_verification.json`。最小字段：

```json
{
  "schema_version": 1,
  "overall_status": "PASS|PARTIAL|FAIL|BLOCKED",
  "selection": {"mode": "full|only|from", "stages": []},
  "started_at": "ISO-8601",
  "duration_ms": 0,
  "git_head": "commit SHA",
  "dirty": false,
  "services": {"backend_url": "...", "frontend_url": "..."},
  "stages": [
    {"name": "backend", "status": "PASS", "duration_ms": 0}
  ]
}
```

报告必须通过 `trap` 或等价收口在失败时也落盘，保留已通过、失败和未执行阶段。P0 只记录当前运行，不读取旧报告决定跳过。

## 5. 实施任务

### Task 1：先固定阶段和状态合同

修改：

- `backend/tests/unit/test_fullstack_verification_check_script.py`
- `backend/tests/unit/test_phase5_architecture.py`，必要时新增专用 Phase 5 CLI 测试文件

先添加失败测试，覆盖：

- `--list-stages` 顺序和稳定阶段键；
- `--only`、`--from` 的互斥与非法输入；
- 默认模式仍包含当前全部命令；
- 局部模式只能得到 `PARTIAL`；
- 不选择兼容阶段时不探测 Playwright；
- Phase 5 默认完整，skip 模式只跳过指定命令；
- JSON 中 `PASS/FAIL/BLOCKED/SKIPPED/NOT_RUN` 的语义。

### Task 2：让 Phase 5 支持显式同轮去重

修改 `scripts/phase5_check.sh`：

- 增加 `--skip-backend-tests`；
- 默认路径仍运行 unit、contract 和 Ruff；
- 跳过时输出结构化原因，不允许静默跳过；
- 保持 docs audit、CI parity、前端 test/build 不变；
- 保持 `.github/workflows/reusable-quality-checks.yml` 无需因本地编排优化而改变。

验收重点：单独执行 `sh scripts/phase5_check.sh` 仍与 CI baseline 完全一致。

### Task 3：将总门禁拆为可选择阶段

修改 `scripts/fullstack_verification_check.sh`：

- 将现有命令映射到第 3 节的稳定阶段；
- 新增参数解析、阶段选择和健康前置检查；
- 默认完整模式调用 Phase 5 去重参数；
- 每阶段记录开始、结束、状态和耗时；
- 失败后保持 fail-fast，但先写出阶段报告；
- 现有 preview、Web Vitals、resource 和 quickstart 参数继续工作。

不把命令拆到大量新 shell 文件；优先在当前脚本内建立少量明确函数，避免为优化编排引入新的维护层。

### Task 4：补齐用户入口和报告

实施完成后更新：

- 在 `docs/reference/` 新增全栈验证规则文档，说明默认命令、局部排障命令、状态和证据边界；
- `AGENTS.md` 与 `CLAUDE.md` 同步引用新的当前规则；
- `docs/README.md`、`docs/CHANGELOG.md`；
- 将本计划移入 `docs/archive/06-productization-closeout/`，并新建交付报告记录真实耗时。

## 6. P0 验收矩阵

### 6.1 合同与局部验证

```bash
.venv/bin/pytest \
  backend/tests/unit/test_fullstack_verification_check_script.py \
  backend/tests/unit/test_phase5_architecture.py -q

sh scripts/fullstack_verification_check.sh --list-stages
sh scripts/fullstack_verification_check.sh --dry-run
sh scripts/phase5_check.sh
```

还需在运行中的开发服务上分别执行：

- `--only api`
- `--only browser-inventory`
- `--only browser-compat`
- `--from browser-inventory`

逐项核对命令范围、退出码、整体 `PARTIAL`、阶段 JSON 和未执行项，不以 `exit=0` 代替覆盖判断。

### 6.2 完整语义验收

执行无阶段参数的标准命令，要求：

- 后端、前端、OpenAPI、API、性能、路由、交互、图表、控件、长列表和三浏览器结果不低于当前覆盖；
- 后端只执行一次全量 pytest，不再单独重跑 unit/contract；两条不同配置的 Ruff 均保留；
- 最终输出 `PASS` 和完整阶段 JSON；
- 所有失败场景仍返回非零退出码；
- `python3 scripts/docs_audit.py --include-archive`、`git diff --check` 和项目 hooks 通过。

### 6.3 耗时验收

代码冻结后连续执行三次默认完整门禁，使用阶段 JSON 计算中位数：

- 完整门禁目标：不高于 25 分钟；
- `quality` 中不再出现 unit/contract 重复耗时；Ruff 差异单独记录；
- `browser-inventory` 局部反馈目标：不高于 3 分钟；
- `browser-compat` 局部反馈目标：不高于 4 分钟；
- 三次不得出现因并发、共享状态或固定短等待导致的新偶发失败。

若完整门禁没有达到 25 分钟，但已消除确定性重复且局部反馈达标，优化计划验收应标记为 `Partial` 并进入 P1 profile；完整门禁本身仍按实际检查结果报告 Pass/Fail，不继续通过删覆盖追数字。

## 7. P1 条件式优化

只有 P0 三次计时证明仍有必要时才执行：

1. 用 `pytest --durations=50` 记录慢测试、夹具建立和真实库读取成本；先优化重复建库或重复 builder，再评估并行。
2. 仅对无 SQLite 写入、全局缓存、环境变量、端口和进程共享状态的单元测试试用 pytest-xdist；串行集合显式打 marker。
3. CI 可把 Chromium 主矩阵与 Firefox/WebKit 兼容矩阵拆为相同 SHA 的独立 job；本地默认仍串行，避免争用开发服务造成假性能回归。
4. 如确有跨运行续跑需求，再设计带 Git HEAD、dirty diff digest、依赖锁摘要、数据 revision 和服务配置的 evidence manifest。任何指纹不一致均拒绝复用；复用后的聚合结论必须明确是组合证据，不是单次完整运行。

P1 不在 P0 中预先实现，避免为了节省约两分钟先引入复杂缓存和证据失效风险。

## 8. 风险与回退条件

- **覆盖被隐藏**：默认命令清单与当前门禁逐项对账；任何必需命令未执行即 Fail。
- **局部成功被误报完整 Pass**：状态模型和单元测试双重约束；报告必须列出 `NOT_RUN`。
- **Phase 5 与 CI 漂移**：保留默认自包含路径和 `ci_baseline_parity.py`。
- **阶段顺序影响缓存或性能**：benchmark 不与 CPU 密集测试或浏览器并行；比较冷/热阶段数据。
- **脚本复杂度反而增加维护成本**：P0 不做跨运行缓存、不引入工作流引擎；参数和阶段表保持单一来源。
- **耗时优化无实际收益**：若三次中位数节省不足 90 秒且局部反馈没有明显改善，回退编排改动，只保留阶段计时报告。

## 9. 完成定义

只有同时满足以下条件，本规划才能从 `plans/` 归档：

- P0 合同、默认完整门禁和局部阶段矩阵全部通过；
- 三次计时报告可复核，明确区分完整 Pass 与局部 Partial；
- 当前规则、文档地图、CHANGELOG、AGENTS/CLAUDE 同步；
- 没有通过减少覆盖、降低阈值或放宽等待条件获得耗时改善；
- 交付报告记录实际节省、未达目标项和是否需要 P1。

## 10. 2026-08-24 P0 实施结果

P0 的阶段化、同轮去重、局部重跑、前置条件状态和 JSON 报告均已实现；独立 Phase 5 默认路径仍完整执行 unit、contract、Ruff、前端测试与 build。总门禁只在同一轮中跳过 Phase 5 的 unit/contract，并由一次全量 `pytest backend/tests/ -q` 负责后端覆盖。pre-commit 与 Phase 5 的 Ruff 因版本和参数不等价而继续保留。

局部验收达到目标：`browser-inventory` 实测约 1 分 22 秒，`browser-compat` 实测约 3 分 17 秒；`--only`、`--from`、`--dry-run`、服务 `BLOCKED` 和失败 JSON 均符合状态合同。默认完整门禁两次通过，分别为 27 分 48 秒和 29 分 7 秒，已高于 25 分钟目标。第三次在 API 性能阶段因 `/api/billboard/all-time` 热 P95 为 581.4ms 超过 500ms 而失败；随后相同 API 局部复核为 340ms 并通过，但局部结果不能覆盖完整失败，也不能补成第三次完整 Pass。

因此 P0 编排功能验收为 Pass，耗时与三轮稳定性验收为 Partial，本计划不归档。P1 首先对后端全量测试约 19%–22% 的稳定长耗时区间运行 `pytest --durations=50`，同时记录 API benchmark 的主机负载和样本分布；在隔离证据完成前不启用 xdist、不并行性能测试，也不放宽 500ms 阈值。完整证据见 [`../reports/2026-08-24-fullstack-gate-duration-optimization.md`](../reports/2026-08-24-fullstack-gate-duration-optimization.md)。

2026-08-25 已完成首轮 P1 profile：`test_api.py` 的两个测试用相同参数重复请求 Taylor Swift 发行周期 overview，单次分别为 160.67s 和 165.30s。两者只对同一个只读响应做不同字段断言，并不验证重复请求缓存，因此改为 module-scoped 响应夹具；封面 URL 仍继续真实 GET。定向复验中唯一构建 149.27s，第二个测试 0.01s；整个文件由 405.73s 降到 278.79s，即使后一次主机负载更高仍减少 126.94s。

修改后的默认完整门禁再次 Full Pass，但在持续外部 CPU/浏览器负载下为 34 分 8 秒，后端、API、前端和浏览器阶段均同时变慢，不能作为 25 分钟干净基线。当前已证明重复计算被消除、覆盖未减少和完整功能回归通过；尚未证明低干扰环境下三次中位数不高于 25 分钟，因此计划继续保留。下一步只需在可控负载窗口重新执行三次默认计时；除非新的 profile 提供隔离证据，不继续引入 xdist 或自动性能重试。
