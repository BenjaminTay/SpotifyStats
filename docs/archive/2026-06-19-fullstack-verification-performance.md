# SpotifyStats Fullstack Verification And Performance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify and improve the FastAPI + React SpotifyStats product line on `codex/playback-logic-update` with measurable evidence for runtime health, semantic correctness, and performance.

**Architecture:** Keep changes inside the current FastAPI `backend/` and React `frontend/` architecture. Treat automated tests, direct API probes, and browser smoke checks as separate evidence streams; green tests alone do not prove playback/Billboard semantics.

**Tech Stack:** Python 3.9-compatible code style, FastAPI, SQLite, pytest markers, ruff, React 19, Vite 8, TanStack Query, Vitest, Playwright or Browser plugin.

---

### Task 1: Branch And Baseline Capture

**Files:**
- Read: `AGENTS.md`
- Read: `CLAUDE.md`
- Read: `backend/CLAUDE.md`
- Read: `frontend/CLAUDE.md`
- Read: `frontend/UI_STYLE_GUIDE.md`
- Modify: `docs/verification/2026-06-19-fullstack-verification.md`

- [ ] **Step 1: Confirm branch and clean worktree**

Run:

```bash
git fetch origin
git status --short --branch
git log --format=fuller -n 5
```

Expected:

```text
## codex/playback-logic-update...origin/codex/playback-logic-update
```

The branch may be ahead if local accepted work has not been pushed.

- [ ] **Step 2: Record initial backend import and startup timing**

Run:

```bash
source .venv/bin/activate
/usr/bin/time -l python -c "import backend.main; print('backend import ok')"
SPOTIFY_STATS_WARMUP=0 /usr/bin/time -l python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning
```

For the uvicorn command, stop it after the app responds to `/openapi.json`, then record elapsed time and maximum resident set size.

- [ ] **Step 3: Record initial frontend build timing and bundle artifacts**

Run:

```bash
cd frontend
/usr/bin/time -l npm run build
npm run analyze
```

Expected: `dist/` exists and Vite build succeeds without TypeScript errors.

- [ ] **Step 4: Create the working report**

Create `docs/verification/2026-06-19-fullstack-verification.md` with sections:

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

**Files:**
- Read: `scripts/phase5_check.sh`
- Test: `backend/tests/`
- Modify only after RED: affected `backend/` module and matching test file.

- [ ] **Step 1: Run focused backend baseline**

Run:

```bash
source .venv/bin/activate
pytest -m unit -q
pytest -m contract -q
```

Expected: all tests pass. If one fails, copy the exact failure into the report before editing code.

- [ ] **Step 2: Run full backend suite**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/ -v
```

Expected: all tests pass. Any failure becomes a bug row in the report.

- [ ] **Step 3: Validate OpenAPI generation and route count**

Run:

```bash
source .venv/bin/activate
python - <<'PY'
from backend.main import app

schema = app.openapi()
paths = schema.get("paths", {})
methods = sum(len(v) for v in paths.values())
print(f"paths={len(paths)} methods={methods}")
for path in sorted(paths):
    print(path, ",".join(sorted(paths[path].keys())))
PY
```

Expected: OpenAPI builds without exception, and the path/method count is recorded in the report.

- [ ] **Step 4: Run backend quality gates**

Run:

```bash
source .venv/bin/activate
ruff check backend/
ruff format --check backend/
```

Expected: both pass.

### Task 3: API Runtime Smoke And Boundary Probes

**Files:**
- Test: temporary probe scripts under `/tmp`, not committed.
- Modify only after RED: affected `backend/api/`, `backend/services/`, or `backend/domains/` module and matching pytest.

- [ ] **Step 1: Start backend without warmup**

Run:

```bash
source .venv/bin/activate
SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info
```

Expected: `GET http://127.0.0.1:8000/openapi.json` returns 200.

- [ ] **Step 2: Probe representative GET endpoints**

Run this from another terminal:

```bash
python - <<'PY'
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
paths = [
    "/api/dashboard/summary",
    "/api/analysis/stats",
    "/api/analysis/charts",
    "/api/billboard/chart?chart_type=track",
    "/api/billboard/records",
    "/api/billboard/all-time?chart_type=track",
    "/api/community/feed",
    "/api/ai-insights/config",
    "/api/settings",
]

for path in paths:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as resp:
            body = resp.read(300)
            print(json.dumps({
                "path": path,
                "status": resp.status,
                "ms": round((time.perf_counter() - start) * 1000, 1),
                "request_id": resp.headers.get("x-request-id"),
                "sample": body.decode("utf-8", "replace")[:120],
            }, ensure_ascii=False))
    except urllib.error.HTTPError as exc:
        print(json.dumps({"path": path, "status": exc.code, "error": exc.read(300).decode("utf-8", "replace")}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"path": path, "error": repr(exc)}, ensure_ascii=False))
PY
```

Expected: all selected endpoints return 2xx or a documented auth/config response, each response includes `X-Request-ID`, and timings are recorded.

- [ ] **Step 3: Add RED tests before fixing any runtime defect**

For each reproducible backend defect, add a focused test in the nearest existing test module. Example pattern:

```python
def test_endpoint_returns_request_id_on_error(client):
    response = client.get("/api/example?bad_param=%00")
    assert "x-request-id" in response.headers
    assert response.status_code in {400, 422}
```

Run the exact test and confirm it fails for the observed reason:

```bash
source .venv/bin/activate
pytest backend/tests/path/to/test_file.py::test_name -q
```

- [ ] **Step 4: Implement the minimal backend fix and verify GREEN**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/path/to/test_file.py::test_name -q
pytest -m unit -q
pytest -m contract -q
```

Expected: the new regression test and existing focused suites pass.

### Task 4: Frontend Build, Unit Tests, And Rendered Smoke

**Files:**
- Test: `frontend/src/tests/`
- Modify only after RED: affected `frontend/src/pages/`, `frontend/src/features/`, `frontend/src/hooks/`, or `frontend/src/api/` module and matching test.

- [ ] **Step 1: Run frontend tests and build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: Vitest and Vite build pass.

- [ ] **Step 2: Start backend and frontend dev servers**

Run backend:

```bash
source .venv/bin/activate
SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning
```

Run frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected: frontend is available at `http://127.0.0.1:5173`.

- [ ] **Step 3: Browser smoke all primary routes**

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

For each route, collect URL, title, console error count, nonblank DOM proof, and horizontal overflow values:

```javascript
({
  url: location.href,
  title: document.title,
  bodyScrollWidth: document.body.scrollWidth,
  htmlScrollWidth: document.documentElement.scrollWidth,
  viewportWidth: window.innerWidth,
  text: document.body.innerText.slice(0, 300)
})
```

Expected: no white screen, no framework overlay, no relevant console errors, and no mobile horizontal overflow.

- [ ] **Step 4: Add RED test before fixing a frontend defect**

For each reproducible React defect, add a focused Vitest/Testing Library test. Example pattern:

```tsx
it("keeps the settings page renderable with missing config", async () => {
  render(<SettingsPage />)
  expect(await screen.findByText(/设置/)).toBeInTheDocument()
})
```

Run:

```bash
cd frontend
npm test -- src/tests/name.test.tsx
```

Expected: the test fails for the observed user-facing defect.

- [ ] **Step 5: Implement the minimal frontend fix and verify GREEN**

Run:

```bash
cd frontend
npm test -- src/tests/name.test.tsx
npm test
npm run build
```

Expected: the focused regression test, full frontend tests, and build pass.

### Task 5: Performance Profiling And Optimization

**Files:**
- Modify only after measured bottleneck: the smallest backend or frontend module responsible for the measured hotspot.
- Test: matching backend pytest or frontend Vitest test when behavior can regress.
- Report: `docs/verification/2026-06-19-fullstack-verification.md`

- [ ] **Step 1: Identify slow sampled APIs**

Run the API probe in Task 3 three times against a warm backend. Mark endpoints above 500 ms as performance candidates.

- [ ] **Step 2: Profile one backend hotspot at a time**

Use `cProfile` around the specific service/helper call behind the slow endpoint. Example shape:

```bash
source .venv/bin/activate
python -m cProfile -o /tmp/spotifystats.prof /tmp/profile_target.py
python - <<'PY'
import pstats
stats = pstats.Stats("/tmp/spotifystats.prof")
stats.strip_dirs().sort_stats("cumtime").print_stats(30)
PY
```

Expected: one concrete root cause is recorded before editing.

- [ ] **Step 3: Optimize with before/after data**

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

Expected: the report contains enough data to decide whether the optimization helped.

- [ ] **Step 4: Run the Phase 5 minimum validation matrix**

Run:

```bash
sh scripts/phase5_check.sh
```

Expected: unit, contract, ruff, frontend tests, and build all pass.

### Task 6: Documentation, Commit, And Final Handoff

**Files:**
- Modify: `docs/verification/2026-06-19-fullstack-verification.md`
- Modify if needed: `README.md`
- Modify if needed: `AGENTS.md`
- Modify if needed: `CLAUDE.md`
- Modify if needed: `backend/CLAUDE.md`
- Modify if needed: `frontend/CLAUDE.md`

- [ ] **Step 1: Update documentation sources of truth**

If behavior, commands, architecture, or performance baselines changed, update the relevant docs in the same pass. If committing code, check `README.md`; for SpotifyStats architecture changes, keep `AGENTS.md` and `CLAUDE.md` consistent.

- [ ] **Step 2: Run final validation**

Run:

```bash
source .venv/bin/activate
pytest backend/tests/ -v
ruff check backend/
ruff format --check backend/
pre-commit run --all-files
sh scripts/phase5_check.sh
cd frontend && npm run build
```

Expected: all commands pass, or any environment-only blocker is documented with exact output and reproduction.

- [ ] **Step 3: Commit only after final evidence is complete**

Run:

```bash
git status --short
git log --format=fuller -n 5
git add <changed-files>
git commit
```

Commit message body follows the repository format with 4-7 Chinese bullets covering backend/data, frontend/UI, performance/stability, tests, and docs.
