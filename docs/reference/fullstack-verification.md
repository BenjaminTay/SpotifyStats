# 全栈验证与阶段执行规则

> 更新日期：2026-08-27
> 状态：当前规则
> 适用范围：本地 Phase 5、全栈门禁、局部排障和机器可读验收报告

## 1. 完整门禁

启动开发后端和前端后，标准入口保持不变：

```bash
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

默认完整门禁按以下阶段执行：

1. `quality`：pre-commit；Phase 5 的文档审计、CI parity、Ruff、前端测试和 production build；
2. `backend`：一次 `pytest backend/tests/ -q`，不再由 Phase 5 重跑 unit/contract；
3. `api`：OpenAPI operation/parameter audit、API smoke、boundary 和 1 冷 + 21 热 benchmark；
4. `browser-routes`：完整路由与重点视口矩阵；
5. `browser-interactions`：桌面/移动交互和图表交互；
6. `browser-inventory`：控件盘点与长列表；
7. `browser-compat`：Chromium、Firefox、WebKit。

quickstart、resource snapshot、Web Vitals 和 preview 矩阵仍由原有显式参数启用，记录在 `optional` 阶段。本地完整 Pass 不推断 preview、真实部署或远程发布已经通过。

## 2. 局部排障

稳定阶段键可通过以下命令查看：

```bash
sh scripts/fullstack_verification_check.sh --list-stages
```

只重跑指定阶段：

```bash
sh scripts/fullstack_verification_check.sh \
  --only browser-inventory,browser-compat \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

从指定必需阶段运行到末尾：

```bash
sh scripts/fullstack_verification_check.sh \
  --from browser-inventory \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

`--only` 与 `--from` 互斥。`--dry-run` 只解析命令计划，不执行检查。局部和 dry-run 即使退出码为 0，也只能标为 `PARTIAL`，不能替代默认完整门禁。

## 3. 状态和报告

阶段状态：

- `PASS`：实际执行并通过；
- `FAIL`：实际执行但失败；
- `BLOCKED`：后端、前端或 Playwright 等前置条件缺失；
- `SKIPPED`：由显式参数或父门禁分工跳过；
- `NOT_RUN`：不在本次选择范围。

整体只有在默认完整模式的全部必需阶段通过时才为 `PASS`。局部成功或 `--skip-cross-browser` 为 `PARTIAL`；断言失败为 `FAIL`；前置条件无法满足且没有断言失败为 `BLOCKED`。

脚本默认将结果写入 `/tmp/spotify_fullstack_verification.json`，也可通过 `--summary-json` 指定路径。报告包含：

- selection mode 和实际阶段范围；
- 每个阶段的状态与 `duration_ms`；
- 总耗时、Git HEAD、dirty 标记；
- backend/frontend/preview URL；
- 未执行和跳过阶段。

脚本失败时也必须写出已完成阶段，不能只凭最终退出码判断覆盖。

使用真实数据库副本做验收时，应显式设置 `SPOTIFY_STATS_TEST_SOURCE_DB`：

```bash
SPOTIFY_STATS_TEST_SOURCE_DB=/absolute/path/to/acceptance-copy.db \
sh scripts/fullstack_verification_check.sh \
  --backend-url http://127.0.0.1:8000 \
  --frontend-url http://localhost:5173
```

父门禁会把该路径同时传给 pytest 和两个进程内 API 探针。`api_smoke_probe.py`、`api_boundary_probe.py` 不得在已指定副本时重新打开默认数据库；否则探针触发的 schema/派生缓存写入会污染正式本地库。HTTP benchmark 与浏览器阶段仍以传入的 `backend-url` 为准，因此该后端进程也必须使用同一验收副本启动。

## 4. Phase 5 边界

独立运行 `sh scripts/phase5_check.sh` 时，仍完整执行文档审计、CI parity、unit、contract、Ruff、前端测试和 build。

`--skip-backend-tests` 只供同一次总门禁使用：父门禁的 `backend` 阶段负责一次完整 pytest，Phase 5 不再追加 marker 重跑。pre-commit Ruff 与 Phase 5 Ruff 使用不同版本/参数，因此当前仍各自保留，不把它们误判成等价重复。

## 5. 证据边界

- 默认完整门禁 Pass：可描述为本地开发后端与 Vite 开发前端的项目全栈门禁通过。
- `--only` / `--from` Pass：只能描述所选阶段通过，整体为 Partial。
- `--skip-cross-browser`：不得描述三浏览器通过。
- 未设置 `--preview-url`：不得描述 production preview 通过。
- 本地门禁不代表真实部署、远程生产、备份或发布通过。
- 阶段耗时必须引用当前 JSON；历史报告中的数字只代表当时快照。
