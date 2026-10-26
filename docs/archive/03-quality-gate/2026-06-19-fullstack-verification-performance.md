# SpotifyStats Fullstack Verification And Performance Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

**Goal:** Verify and improve the FastAPI + React SpotifyStats product line on `codex/playback-logic-update` with measurable evidence for runtime health, semantic correctness, and performance.

**Architecture:** Keep changes inside the current FastAPI `backend/` and React `frontend/` architecture. Treat automated tests, direct API probes, and browser smoke checks as separate evidence streams; green tests alone do not prove playback/Billboard semantics.

**Tech Stack:** Python 3.9-compatible code style, FastAPI, SQLite, pytest markers, ruff, React 19, Vite 8, TanStack Query, Vitest, Playwright or Browser plugin.

---

### Task 1: Branch And Baseline Capture

- Read: `AGENTS.md`
- Read: `CLAUDE.md`
- Read: `backend/CLAUDE.md`
- Read: `frontend/CLAUDE.md`
- Read: `frontend/UI_STYLE_GUIDE.md`
- Modify: `docs/reports/2026-06-19-fullstack-verification.md`
- Confirm branch and clean worktree

```text
## codex/playback-logic-update...origin/codex/playback-logic-update
```

The branch may be ahead if local accepted work has not been pushed.

- Record initial backend import and startup timing

For the uvicorn command, stop it after the app responds to `/openapi.json`, then record elapsed time and maximum resident set size.

- Record initial frontend build timing and bundle artifacts

历史验收预期： `dist/` exists and Vite build succeeds without TypeScript errors.

- Create the working report

```markdown
# Fullstack Verification And Performance Report

## Scope

- Branch: codex/playback-logic-update
- Date: 2026-06-19
- Evidence types: tests, API probes, browser smoke, performance timings

## Initial Baseline

| Metric | Baseline | Notes |
|--------|----------|-------|
| backend import time |  |  |
| backend import max RSS |  |  |
| frontend build time |  |  |
| frontend build max RSS |  |  |
| homepage first render |  |  |
| slowest sampled API |  |  |

## Bugs Found And Fixed

| Severity | Surface | Symptom | Root Cause | Fix | Verification |
|----------|---------|---------|------------|-----|--------------|

## Performance Changes

| Surface | Baseline | After | Change | Implementation | Verification |
|---------|----------|-------|--------|----------------|--------------|

## Final Validation

| Check | Result | Evidence |
|-------|--------|----------|

## Ten Minute Smoke Guide

1. Start backend.
2. Start frontend.
3. Open dashboard.
4. Open analysis stats and charts.
5. Open Billboard, records, all-time, and number-ones.
6. Open one track, album, and artist detail page.
7. Open Community, AI Insights, Account, and Settings.
8. Confirm no console errors and no horizontal overflow at mobile width.
```

### Task 2: Automated Backend And Contract Verification

- Read: `scripts/phase5_check.sh`
- Test: `backend/tests/`
- Modify only after RED: affected `backend/` module and matching test file.
- Validate OpenAPI generation and route count

历史验收预期： OpenAPI builds without exception, and the path/method count is recorded in the report.

- 历史验收要求：all tests pass. If one fails, copy the exact failure into the report before editing code.

### Task 3: API Runtime Smoke And Boundary Probes

涉及文件：`/tmp`。

- Modify only after RED: affected `backend/api/`, `backend/services/`, or `backend/domains/` module and matching pytest.
- Start backend without warmup

历史验收预期： `GET http://127.0.0.1:8000/openapi.json` returns 200.

- Probe representative GET endpoints

历史验收预期： all selected endpoints return 2xx or a documented auth/config response, each response includes `X-Request-ID`, and timings are recorded.

- Add RED tests before fixing any runtime defect

Run the exact test and confirm it fails for the observed reason:

- Implement the minimal backend fix and verify GREEN

### Task 4: Frontend Build, Unit Tests, And Rendered Smoke

涉及文件：`frontend/src/tests/`。

- Modify only after RED: affected `frontend/src/pages/`, `frontend/src/features/`, `frontend/src/hooks/`, or `frontend/src/api/` module and matching test.

- Start backend and frontend dev servers

历史验收预期： frontend is available at `http://127.0.0.1:5173`.

- Browser smoke all primary routes

Check these routes at desktop width and 390px mobile width:

```text
/
/analysis/stats
/analysis/charts
/yearly-review
/billboard
/billboard/number-ones
/billboard/all-time
/billboard/records
/community
/ai-insights
/account
/settings
```

历史验收预期： no white screen, no framework overlay, no relevant console errors, and no mobile horizontal overflow.

- Add RED test before fixing a frontend defect

For each reproducible React defect, add a focused Vitest/Testing Library test. Example pattern:

- Implement the minimal frontend fix and verify GREEN

- 历史实施约束：For each route, collect URL, title, console error count, nonblank DOM proof, and horizontal overflow values.

### Task 5: Performance Profiling And Optimization

- Modify only after measured bottleneck: the smallest backend or frontend module responsible for the measured hotspot.
- Test: matching backend pytest or frontend Vitest test when behavior can regress.
- Report: `docs/reports/2026-06-19-fullstack-verification.md`
- Identify slow sampled APIs

Run the API probe in Task 3 three times against a warm backend. Mark endpoints above 500 ms as performance candidates.

- Profile one backend hotspot at a time

历史验收预期： one concrete root cause is recorded before editing.

- Optimize with before/after data

For each optimization, record:

```text
Surface:
Baseline command:
Baseline p50 or elapsed:
Change:
After command:
After p50 or elapsed:
Delta:
Risk:
```

历史验收预期： the report contains enough data to decide whether the optimization helped.

### Task 6: Documentation, Commit, And Final Handoff

涉及文件：`docs/reports/2026-06-19-fullstack-verification.md`、`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`frontend/CLAUDE.md`。

- Update documentation sources of truth

If behavior, commands, architecture, or performance baselines changed, update the relevant docs in the same pass. If committing code, check `README.md`; for SpotifyStats architecture changes, keep `AGENTS.md` and `CLAUDE.md` consistent.

Commit message body follows the repository format with 4-7 Chinese bullets covering backend/data, frontend/UI, performance/stability, tests, and docs.

- 历史验收要求：all commands pass, or any environment-only blocker is documented with exact output and reproduction.
