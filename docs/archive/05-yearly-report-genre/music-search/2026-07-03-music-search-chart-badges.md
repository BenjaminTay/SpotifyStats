# Music Search Chart Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add compact personal-Billboard chart metrics to both the full music search page and Masthead quick search while keeping the displayed numbers identical to the existing music detail pages.

**Architecture:** Keep `/api/music/search` as the single local search endpoint. Add an opt-in `include_chart=true` mode that computes the same Billboard summary fields used by the detail pages once per search request, then attaches a normalized optional `chart` object to each result. Both `/music/search` and the Masthead dialog request chart metrics so their visible playback and chart summaries stay consistent.

**Tech Stack:** FastAPI, SQLite, Pydantic, pandas, existing Billboard computation cache, React 19, TypeScript, React Router v7, TanStack Query, Tailwind CSS v4, Vitest, Testing Library, pytest.

---

## Scope And Product Decisions

- Full search page `/music/search` shows chart summaries.
- Masthead search dialog also shows the same compact chart summaries, because users expect the quick search preview to match the full search page.
- Playback count remains aligned with the music stats detail APIs:
  - Track: `/api/music/tracks/{track_id}/stats` → `summary.total_plays`
  - Album: `/api/music/albums/{album_name}/stats?artist=...` → `summary.total_plays`
  - Artist: `/api/music/artists/{artist_name}/stats` → `summary.total_plays`
- Chart badges align with the Billboard detail APIs actually used by the music detail pages:
  - Track chart detail: `/api/billboard/track/{track_id}` → `summary`
  - Album chart detail: `/api/billboard/album/{album_name}?artist_name=...` → `chart_summary`
  - Artist chart detail: `/api/billboard/artist/{artist_name}` → `chart_summary`
- Search chart data follows the same Billboard filters as detail pages:
  - `min_ms`
  - `music_only`
  - `bb_top_n`
  - `bb_album_top_n`
  - `bb_artist_top_n`
  - `bb_week_start_dow`
  - `bb_week_start_hour`
  - `year_start`
  - `year_end`
  - `dynamic_threshold`
  - `max_merge_gap_minutes`
  - `merge_level`
- If an entity exists in listening history but has no Billboard entry under the current chart filter, return `chart: null`; the current UI omits chart text for uncharted quick rows rather than adding a noisy `未入榜` label.
- Do not add a new route or a second search endpoint.
- Update README / AGENTS / CLAUDE only for the durable `include_chart` contract and visible summary policy.
- Do not commit during planning. Commit only when the user explicitly asks after implementation and verification.

## Display Contract

The normalized search result chart object should be:

```ts
export interface MusicSearchChartSummary {
  peak_position: number | null
  peak_weeks: number | null
  weeks_on_chart: number | null
  weeks_at_no1: number | null
  power_score: number | null
  power_rank: number | null
  first_week: string | null
  latest_week: string | null
  first_peak_week: string | null
}
```

Field mapping must preserve detail-page semantics:

| Search field | Track detail source | Album detail source | Artist detail source |
| --- | --- | --- | --- |
| `peak_position` | `summary.peak_position` | `chart_summary.peak_position` | `chart_summary.peak_position` |
| `peak_weeks` | `summary.weeks_at_peak` | `chart_summary.peak_weeks` | `chart_summary.peak_weeks` |
| `weeks_on_chart` | `summary.weeks_on_chart` | `chart_summary.weeks_on_chart` | `chart_summary.weeks_on_chart` |
| `weeks_at_no1` | `summary.weeks_at_no1` | `chart_summary.no1_weeks` | `chart_summary.no1_weeks` |
| `power_score` | `summary.power_score` | `chart_summary.power_score` | `chart_summary.power_score` |
| `power_rank` | `summary.power_rank` | `chart_summary.power_rank` | `chart_summary.power_rank` |
| `first_week` | `summary.first_week` | `chart_summary.first_week` | `chart_summary.first_week` |
| `latest_week` | `summary.last_week` | `chart_summary.latest_week` | `chart_summary.latest_week` |
| `first_peak_week` | `summary.first_peak_week` | `chart_summary.first_peak_week` | `chart_summary.first_peak_week` |

UI summaries on the full search page and Masthead dialog:

- Always show playback count: `280 次播放`.
- If `chart` exists:
  - `PK #1` from `peak_position`.
  - `在榜 12周` from `weeks_on_chart`.
  - `走势 #8` from `power_rank` when present.
  - Do not show `peak_weeks` or champion/no.1 week counts; they made the row feel visually noisy and semantically repetitive beside `PK #1`.
- If `chart` is null:
  - Keep only playback count.
- Keep rows one-line on desktop where possible; badges wrap below title/subtitle on narrow screens.

## File Structure

### Backend

- Modify: `backend/models/music_search.py`
  - Add `MusicSearchChartSummary`.
  - Add `chart: MusicSearchChartSummary | None = None` to `MusicSearchResult`.

- Modify: `backend/services/music_search_service.py`
  - Add `include_chart` and Billboard filter parameters to `search_music_entities`.
  - Add a private chart lookup builder that computes Billboard data once per request.
  - Attach chart summaries to candidate rows after filtered playback-count metrics are computed.
  - Keep `use_filtered_counts=False` for lightweight unit tests.

- Modify: `backend/api/music.py`
  - Add `include_chart: bool = Query(default=False)`.
  - Add `BillboardFilters = Depends()` and `MergeConfig = Depends()` for chart mode.
  - Continue passing `PlayFilters` to playback-count metrics.
  - Pass Billboard filters to the service only when `include_chart` is true.

- Modify: `backend/tests/contract/test_music_search_counting_consistency.py`
  - Add chart-summary contract tests comparing search results against existing Billboard detail endpoints.

- Modify: `backend/tests/unit/test_music_search_service.py`
  - Extend model/unit assertions to confirm `chart` defaults to `None` when `include_chart` is false.

- Modify: `backend/tests/contract/test_music_search_api.py`
  - Add endpoint response shape coverage for `include_chart=true`.

### Frontend

- Modify: `frontend/src/types/music-search.ts`
  - Add `MusicSearchChartSummary`.
  - Add `chart: MusicSearchChartSummary | null` to `MusicSearchResult`.

- Modify: `frontend/src/hooks/useAnalysis.ts`
  - Add an optional `includeChart` parameter to `musicSearchApi.search()` and `useMusicSearch()`.
  - Full page calls `useMusicSearch(query, kind, 5, { includeChart: true })`.
  - Dialog calls `useMusicSearch(debouncedQuery, undefined, 5, { includeChart: true })`.
  - When `includeChart` is true, include current Billboard settings in the query params:
    - `bb_top_n`
    - `bb_album_top_n`
    - `bb_artist_top_n`
    - `bb_week_start_dow`
    - `bb_week_start_hour`
  - Keep existing play filter params in all search requests.

- Modify: `frontend/src/features/music/search/MusicSearchPage.tsx`
  - Request chart metrics for full-page search.

- Modify: `frontend/src/features/music/search/MusicSearchDialog.tsx`
  - Requests chart metrics and keeps the initial active result unset until hover/focus or keyboard movement.

- Modify: `frontend/src/features/music/search/MusicSearchResults.tsx`
  - Add compact chart badges below or beside playback count.
  - Keep layout stable when `chart` is null.
  - Preserve accessible link names and cover rendering.

- Modify: `frontend/src/tests/query-hooks.test.tsx`
  - Assert `include_chart` and Billboard settings are sent when chart summaries are requested.

- Modify: `frontend/src/tests/music-search-components.test.tsx`
  - Assert chart summaries render for charted results and uncharted rows avoid noisy placeholder labels.

- Modify: `frontend/src/tests/music-search-flow.test.tsx`
  - Assert full page and dialog enable chart mode, and the dialog does not preselect the first result.

---

## Task 1: Write Backend RED Tests For Detail-Exact Chart Metrics

**Files:**
- Modify: `backend/tests/contract/test_music_search_counting_consistency.py`

- [ ] **Step 1: Add a track chart comparison test**

Add this test:

```python
def test_music_search_track_chart_matches_billboard_detail(client):
    params = {
        "q": "Fixture Long Track",
        "kind": "track",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": False,
        "merge_level": 2,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get("/api/billboard/track/902", params=params).json()

    assert detail["found"] is True
    chart = search["tracks"][0]["chart"]
    assert chart["peak_position"] == detail["summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["summary"]["weeks_at_peak"]
    assert chart["weeks_on_chart"] == detail["summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["summary"]["weeks_at_no1"]
    assert chart["power_score"] == detail["summary"]["power_score"]
    assert chart["power_rank"] == detail["summary"]["power_rank"]
    assert chart["first_week"] == detail["summary"]["first_week"]
    assert chart["latest_week"] == detail["summary"]["last_week"]
    assert chart["first_peak_week"] == detail["summary"]["first_peak_week"]
```

- [ ] **Step 2: Add album and artist chart comparison tests**

Add these tests:

```python
def test_music_search_album_chart_matches_billboard_detail(client):
    params = {
        "q": "Fixture Future LP",
        "kind": "album",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": True,
        "merge_level": 2,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get(
        "/api/billboard/album/Fixture Future LP",
        params={**params, "artist_name": "Fixture Artist Alpha"},
    ).json()

    assert detail["found"] is True
    chart = search["albums"][0]["chart"]
    assert chart["peak_position"] == detail["chart_summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["chart_summary"]["peak_weeks"]
    assert chart["weeks_on_chart"] == detail["chart_summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["chart_summary"]["no1_weeks"]
    assert chart["power_score"] == detail["chart_summary"]["power_score"]
    assert chart["power_rank"] == detail["chart_summary"]["power_rank"]
    assert chart["first_week"] == detail["chart_summary"]["first_week"]
    assert chart["latest_week"] == detail["chart_summary"]["latest_week"]
    assert chart["first_peak_week"] == detail["chart_summary"]["first_peak_week"]


def test_music_search_artist_chart_matches_billboard_detail(client):
    params = {
        "q": "Fixture Artist Alpha",
        "kind": "artist",
        "limit_per_type": 5,
        "include_chart": True,
        "min_ms": 30000,
        "music_only": True,
        "dynamic_threshold": True,
        "merge_level": 2,
    }

    search = client.get("/api/music/search", params=params).json()
    detail = client.get("/api/billboard/artist/Fixture Artist Alpha", params=params).json()

    assert detail["found"] is True
    chart = search["artists"][0]["chart"]
    assert chart["peak_position"] == detail["chart_summary"]["peak_position"]
    assert chart["peak_weeks"] == detail["chart_summary"]["peak_weeks"]
    assert chart["weeks_on_chart"] == detail["chart_summary"]["weeks_on_chart"]
    assert chart["weeks_at_no1"] == detail["chart_summary"]["no1_weeks"]
    assert chart["power_score"] == detail["chart_summary"]["power_score"]
    assert chart["power_rank"] == detail["chart_summary"]["power_rank"]
    assert chart["first_week"] == detail["chart_summary"]["first_week"]
    assert chart["latest_week"] == detail["chart_summary"]["latest_week"]
    assert chart["first_peak_week"] == detail["chart_summary"]["first_peak_week"]
```

- [ ] **Step 3: Verify the tests fail for the right reason**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_music_search_counting_consistency.py -q
```

Expected: the new tests fail because `chart` is missing from search results.

---

## Task 2: Add Backend Chart Summary Models And Search Service Support

**Files:**
- Modify: `backend/models/music_search.py`
- Modify: `backend/services/music_search_service.py`
- Modify: `backend/api/music.py`
- Modify: `backend/tests/unit/test_music_search_service.py`
- Modify: `backend/tests/contract/test_music_search_api.py`

- [ ] **Step 1: Add Pydantic model fields**

Update `backend/models/music_search.py`:

```python
class MusicSearchChartSummary(BaseModel):
    peak_position: int | None = None
    peak_weeks: int | None = None
    weeks_on_chart: int | None = None
    weeks_at_no1: int | None = None
    power_score: int | None = None
    power_rank: int | None = None
    first_week: str | None = None
    latest_week: str | None = None
    first_peak_week: str | None = None
```

Then add this field to `MusicSearchResult`:

```python
chart: MusicSearchChartSummary | None = None
```

- [ ] **Step 2: Add chart lookup helpers**

In `backend/services/music_search_service.py`, add helpers that compute a single Billboard payload and build per-entity maps:

```python
def _none_if_empty(value: Any) -> Any | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value)
    return text if text else None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
```

Then add one chart-index builder:

```python
def _build_chart_lookup(
    *,
    min_ms: int,
    music_only: bool,
    bb_top_n: int,
    bb_album_top_n: int,
    bb_artist_top_n: int,
    bb_week_start_dow: int,
    bb_week_start_hour: int,
    year_start: int | None,
    year_end: int | None,
    merge_level: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
) -> dict[str, dict[Any, MusicSearchChartSummary]]:
    data = compute_billboard_data(
        min_ms=min_ms,
        music_only=music_only,
        bb_top_n=bb_top_n,
        bb_album_top_n=bb_album_top_n,
        bb_artist_top_n=bb_artist_top_n,
        bb_week_start_dow=bb_week_start_dow,
        bb_week_start_hour=bb_week_start_hour,
        year_start=year_start,
        year_end=year_end,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    return {
        "track": _track_chart_map(data),
        "album": _album_chart_map(data),
        "artist": _artist_chart_map(data),
    }
```

The three map helpers must intentionally mirror the detail-page mapping table above. For album and artist, compute `peak_weeks`, `weeks_at_no1`, first/latest/first-peak weeks from `weekly_album` / `weekly_artist`, and compute `power_rank` from `album_power_scores` / `artist_power_scores` sorted by `power_score` descending, matching `backend/domains/billboard/details.py`.

- [ ] **Step 3: Attach chart summaries to results**

Update `_track_result`, `_album_result`, `_artist_result`, and `_convert` to accept:

```python
chart: MusicSearchChartSummary | None = None
```

Then pass `chart=chart` into `MusicSearchResult(...)`.

- [ ] **Step 4: Add service parameters**

Extend `search_music_entities(...)` with:

```python
include_chart: bool = False
bb_top_n: int = 30
bb_album_top_n: int = 20
bb_artist_top_n: int = 20
bb_week_start_dow: int = 4
bb_week_start_hour: int = 0
year_start: int | None = None
year_end: int | None = None
```

Build `chart_lookup` only when `include_chart` is true and the query is non-blank.

- [ ] **Step 5: Add API query params**

Update `backend/api/music.py`:

```python
from backend.dependencies import BillboardFilters, MergeConfig, PlayFilters
```

Then update the endpoint signature:

```python
include_chart: bool = Query(default=False, description="Include personal Billboard chart summary"),
filters: PlayFilters = Depends(),
billboard_filters: BillboardFilters = Depends(),
merge_cfg: MergeConfig = Depends(),
```

Pass chart params into `search_music_entities`. Keep `merge_level=merge_cfg.merge_level`.

- [ ] **Step 6: Verify backend green**

Run:

```bash
source .venv/bin/activate && pytest \
  backend/tests/unit/test_music_search_service.py \
  backend/tests/contract/test_music_search_api.py \
  backend/tests/contract/test_music_search_counting_consistency.py \
  -q
```

Expected: all selected backend music-search tests pass.

---

## Task 3: Add Frontend Types, Query Params, And Hook Behavior

**Files:**
- Modify: `frontend/src/types/music-search.ts`
- Modify: `frontend/src/hooks/useAnalysis.ts`
- Modify: `frontend/src/tests/query-hooks.test.tsx`

- [ ] **Step 1: Write RED hook tests**

In `frontend/src/tests/query-hooks.test.tsx`, extend the existing music search test with chart params:

```ts
const filters = {
  min_ms: 45000,
  music_only: true,
  merge_enabled: false,
  dynamic_threshold: false,
  max_merge_gap_minutes: undefined,
  merge_level: 2,
  include_compilations: false,
}

await musicSearchApi.search(filters, ' love ', 'track', 3, { includeChart: true })

expect(api.get).toHaveBeenCalledWith('/music/search', expect.objectContaining({
  q: 'love',
  kind: 'track',
  limit_per_type: 3,
  include_chart: true,
  merge_level: 2,
}))
```

Also add a lightweight default case:

```ts
await musicSearchApi.search(filters, ' love ', undefined, 5)
expect(api.get).toHaveBeenCalledWith('/music/search', expect.not.objectContaining({
  include_chart: true,
}))
```

- [ ] **Step 2: Add TypeScript chart type**

Update `frontend/src/types/music-search.ts`:

```ts
export interface MusicSearchChartSummary {
  peak_position: number | null
  peak_weeks: number | null
  weeks_on_chart: number | null
  weeks_at_no1: number | null
  power_score: number | null
  power_rank: number | null
  first_week: string | null
  latest_week: string | null
  first_peak_week: string | null
}
```

Then add:

```ts
chart: MusicSearchChartSummary | null
```

to `MusicSearchResult`.

- [ ] **Step 3: Add hook options**

Change the search helper signatures:

```ts
type MusicSearchOptions = {
  includeChart?: boolean
}

search: (
  filters: AnalysisFilters,
  query: string,
  kind?: MusicSearchKind,
  limitPerType = 5,
  options: MusicSearchOptions = {},
) => { ... }
```

When `options.includeChart` is true, add:

```ts
params.include_chart = true
```

Keep query keys parameterized by the full params object so chart and non-chart search caches do not collide.

- [ ] **Step 4: Verify frontend hook tests**

Run:

```bash
cd frontend && npm test -- --run src/tests/query-hooks.test.tsx
```

Expected: query hook tests pass.

---

## Task 4: Render Chart Badges In Full Search Results

**Files:**
- Modify: `frontend/src/features/music/search/MusicSearchPage.tsx`
- Modify: `frontend/src/features/music/search/MusicSearchDialog.tsx`
- Modify: `frontend/src/features/music/search/MusicSearchResults.tsx`
- Modify: `frontend/src/tests/music-search-components.test.tsx`
- Modify: `frontend/src/tests/music-search-flow.test.tsx`

- [ ] **Step 1: Write component RED tests**

Update sample results in `frontend/src/tests/music-search-components.test.tsx`:

```ts
chart: {
  peak_position: 1,
  peak_weeks: 2,
  weeks_on_chart: 12,
  weeks_at_no1: 3,
  power_score: 1234,
  power_rank: 8,
  first_week: '2026-01-02',
  latest_week: '2026-03-20',
  first_peak_week: '2026-01-09',
},
```

Assert:

```ts
expect(within(trackGroup).getByText('PK #1')).toBeInTheDocument()
expect(within(trackGroup).getByText('在榜 12周')).toBeInTheDocument()
expect(within(trackGroup).getByText('走势 #8')).toBeInTheDocument()
expect(screen.queryByText('2wks')).not.toBeInTheDocument()
expect(screen.queryByText('冠军 3 周')).not.toBeInTheDocument()
expect(screen.queryByText('未入榜')).not.toBeInTheDocument()
```

- [ ] **Step 2: Make full page request chart mode**

Update `frontend/src/features/music/search/MusicSearchPage.tsx`:

```ts
const { data, loading, error } = useMusicSearch(query, kindParam, 5, { includeChart: true })
```

- [ ] **Step 3: Enable chart mode in the dialog without default active selection**

Update `frontend/src/features/music/search/MusicSearchDialog.tsx`:

```ts
const { data, loading, error } = useMusicSearch(debouncedQuery, undefined, 5, { includeChart: true })
```

Keep `activeIndex` at `-1` when results load or change. Only `onMouseEnter`, `onFocus`, `ArrowDown`, or `ArrowUp` should set an active result.

- [ ] **Step 4: Add badge formatter helpers**

In `MusicSearchResults.tsx`, add helpers:

```tsx
function chartBadges(item: MusicSearchResult): string[] {
  const chart = item.chart
  if (!chart || !chart.peak_position || !chart.weeks_on_chart) return []
  const badges = [`PK #${chart.peak_position}`, `在榜 ${chart.weeks_on_chart}周`]
  if (chart.power_rank) badges.push(`走势 #${chart.power_rank}`)
  return badges
}
```

Render badges near the playback count with small, wrapping pills:

```tsx
<span className="mt-1 flex flex-wrap items-center gap-1.5">
  <span className="text-xs tabular-nums text-muted-foreground">
    {formatPlayEvents(item.play_events)}
  </span>
  {chartBadges(item).map((badge) => (
    <span key={badge} className="rounded-md border border-border bg-muted/45 px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
      {badge}
    </span>
  ))}
</span>
```

Do not render peak-week or champion-week badges in search rows; those details remain available on the detail pages.

- [ ] **Step 5: Verify frontend component tests**

Run:

```bash
cd frontend && npm test -- --run \
  src/tests/music-search-components.test.tsx \
  src/tests/music-search-flow.test.tsx
```

Expected: all selected frontend search tests pass.

---

## Task 5: Verification And Self-Acceptance

**Files:**
- No new product files unless tests reveal a missing contract.

- [ ] **Step 1: Backend focused verification**

Run:

```bash
source .venv/bin/activate && pytest \
  backend/tests/unit/test_music_search_service.py \
  backend/tests/contract/test_music_search_api.py \
  backend/tests/contract/test_music_search_counting_consistency.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Frontend focused verification**

Run:

```bash
cd frontend && npm test -- --run \
  src/tests/query-hooks.test.tsx \
  src/tests/music-search-components.test.tsx \
  src/tests/music-search-flow.test.tsx
```

Expected: all selected tests pass.

- [ ] **Step 3: Build verification**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and production build pass.

- [ ] **Step 4: API contract probes**

Run:

```bash
source .venv/bin/activate && .venv/bin/python scripts/api_smoke_probe.py --json-output /tmp/spotify_api_smoke_music_search_chart_badges.json
source .venv/bin/activate && .venv/bin/python scripts/api_boundary_probe.py --json-output /tmp/spotify_api_boundary_music_search_chart_badges.json
source .venv/bin/activate && .venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit_music_search_chart_badges.json
```

Expected:

- API smoke passes all existing probes.
- API boundary probe passes.
- OpenAPI parameter boundary audit reports `0 unaccounted obligations`.

- [ ] **Step 5: Live DB spot check**

Run a short script using `TestClient`:

```bash
source .venv/bin/activate && python - <<'PY'
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
params = {
    "q": "the",
    "limit_per_type": 1,
    "include_chart": True,
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "dynamic_threshold": True,
    "merge_level": 2,
}
search = client.get("/api/music/search", params=params).json()
print(search["tracks"][0]["label"], search["tracks"][0]["chart"])
print(search["albums"][0]["label"], search["albums"][0]["chart"])
print(search["artists"][0]["label"], search["artists"][0]["chart"])
PY
```

Expected: each printed chart object is either `None` or contains the same values as the corresponding Billboard detail endpoint under the same params.

- [ ] **Step 6: Workspace hygiene**

Run:

```bash
git status --short
```

Expected: only files touched by this implementation are newly modified in addition to any pre-existing unrelated dirty files. Do not revert unrelated dirty files.

## Self-Review

- Spec coverage: backend response contract, detail-page metric parity, full-page and dialog chart display, keyboard active-state behavior, frontend rendering, and verification are covered.
- Scan: no unfinished markers remain.
- Type consistency: `MusicSearchChartSummary` is used consistently across backend model, frontend type, and UI.
- Risk callout: if tests reveal that an existing Billboard detail endpoint ignores a filter that the frontend passes, prefer making search match the currently rendered detail output first. A separate follow-up can then fix the detail endpoint filter propagation with its own regression tests.
