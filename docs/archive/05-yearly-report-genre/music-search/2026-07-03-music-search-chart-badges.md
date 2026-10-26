# Music Search Chart Badges Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

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

Field mapping must preserve detail-page semantics.

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

涉及文件：`backend/tests/contract/test_music_search_counting_consistency.py`。

- Add a track chart comparison test
- Add album and artist chart comparison tests

Add these tests:

- Verify the tests fail for the right reason

---

## Task 2: Add Backend Chart Summary Models And Search Service Support

涉及文件：`backend/models/music_search.py`、`backend/services/music_search_service.py`、`backend/api/music.py`、`backend/tests/unit/test_music_search_service.py`、`backend/tests/contract/test_music_search_api.py`。

- Add Pydantic model fields

Then add this field to `MusicSearchResult`:

- Add chart lookup helpers

The three map helpers must intentionally mirror the detail-page mapping table above. For album and artist, compute `peak_weeks`, `weeks_at_no1`, first/latest/first-peak weeks from `weekly_album` / `weekly_artist`, and compute `power_rank` from `album_power_scores` / `artist_power_scores` sorted by `power_score` descending, matching `backend/domains/billboard/details.py`.

- Attach chart summaries to results

Then pass `chart=chart` into `MusicSearchResult(...)`.

- Add service parameters

Build `chart_lookup` only when `include_chart` is true and the query is non-blank.

- Add API query params

Pass chart params into `search_music_entities`. Keep `merge_level=merge_cfg.merge_level`.

- Verify backend green

---

## Task 3: Add Frontend Types, Query Params, And Hook Behavior

涉及文件：`frontend/src/types/music-search.ts`、`frontend/src/hooks/useAnalysis.ts`、`frontend/src/tests/query-hooks.test.tsx`。

- Write RED hook tests

Also add a lightweight default case:

- Add TypeScript chart type

to `MusicSearchResult`.

- Add hook options

Keep query keys parameterized by the full params object so chart and non-chart search caches do not collide.

- Verify frontend hook tests

---

- 历史验收要求：query hook tests pass.

## Task 4: Render Chart Badges In Full Search Results

涉及文件：`frontend/src/features/music/search/MusicSearchPage.tsx`、`frontend/src/features/music/search/MusicSearchDialog.tsx`、`frontend/src/features/music/search/MusicSearchResults.tsx`、`frontend/src/tests/music-search-components.test.tsx`、`frontend/src/tests/music-search-flow.test.tsx`。

- Write component RED tests

Assert:

- Make full page request chart mode
- Enable chart mode in the dialog without default active selection

Keep `activeIndex` at `-1` when results load or change. Only `onMouseEnter`, `onFocus`, `ArrowDown`, or `ArrowUp` should set an active result.

- Add badge formatter helpers

Do not render peak-week or champion-week badges in search rows; those details remain available on the detail pages.

- Verify frontend component tests

---

## Task 5: Verification And Self-Acceptance

- No new product files unless tests reveal a missing contract.
- Backend focused verification

- Frontend focused verification

- Build verification

- API contract probes
- API smoke passes all existing probes.
- API boundary probe passes.
- OpenAPI parameter boundary audit reports `0 unaccounted obligations`.
- Live DB spot check

历史验收预期： each printed chart object is either `None` or contains the same values as the corresponding Billboard detail endpoint under the same params.

- Workspace hygiene

## Self-Review

- Spec coverage: backend response contract, detail-page metric parity, full-page and dialog chart display, keyboard active-state behavior, frontend rendering, and verification are covered.
- Scan: no unfinished markers remain.
- Type consistency: `MusicSearchChartSummary` is used consistently across backend model, frontend type, and UI.
- Risk callout: if tests reveal that an existing Billboard detail endpoint ignores a filter that the frontend passes, prefer making search match the currently rendered detail output first. A separate follow-up can then fix the detail endpoint filter propagation with its own regression tests.
