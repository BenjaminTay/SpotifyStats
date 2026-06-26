# Billboard Year-End Design Spec

Date: 2026-06-26

## Goal

Add a Billboard Year-End section that feels like a personal version of Billboard's official year-end charts. It should rank tracks, albums, and artists by annual chart performance, not by raw annual play count.

## Product Positioning

The feature answers: "Which songs, albums, and artists dominated my personal Billboard chart in a specific year?"

It must not duplicate the existing annual play-count leaderboards. Total plays can appear as context and as a late tie-breaker, but the primary ranking is a year-scoped Billboard score derived from weekly chart behavior.

## Scope

In scope:

- Add a new Billboard subpage at `/billboard/year-end`.
- Add annual track, album, and artist charts.
- Add year selection based on available Billboard weeks.
- Add Year-End Honors that summarize the annual story.
- Reuse the current Billboard counting pipeline, merge settings, album project semantics, and Power Score formula family.

Out of scope for the first version:

- Editing Power Score constants from Settings.
- Replacing the existing All-Time chart.
- Exporting images or share cards.
- LLM-generated year-end prose.

## Scoring Semantics

The Year-End chart uses the same scoring family as the current Billboard Power Score. The difference is the scoring window.

Current All-Time Power Score:

```text
score = cumulative weekly chart performance across the selected full range
```

Year-End Power Score:

```text
score = cumulative weekly chart performance where billboard_week belongs to one selected year
```

The backend must not compute All-Time scores and then filter the result by year. It must filter annual weekly chart rows first, then aggregate annual scores and annual ranks.

The first version should preserve the existing score components:

- weekly rank base score
- weekly competition factor
- weekly individual dominance factor
- peak bonus
- longevity bonus
- weekly #1 bonus for tracks, albums, and artists

Top 5 and Top 10 weeks are exposed as explanation fields and tie-breakers in v1. They should not introduce new weight beyond the existing formula unless the global Power Score formula changes later.

## Unified #1 Bonus Rule

Year-End charts use a unified annual dominance bonus:

```text
no1_bonus = annual weeks_at_no1 × 40
```

This applies to tracks, albums, and artists. A true debut #1 can still be exposed as descriptive metadata for track rows, but it does not add extra Year-End score.

For Year-End track charts, this avoids double-counting a one-week debut event and keeps the ranking focused on annual chart dominance:

```text
track year_end_score = raw_score + longevity_bonus + peak_bonus + no1_bonus
```

Example:

- A track debuts at #1 and spends 1 annual week at #1.
- A prior-year entry also spends 1 annual week at #1 under the same weekly conditions.
- They receive the same #1 bonus in that Year-End chart.

True first chart week remains available for new-entry honors and explanatory UI.

## Entity Sources

Track Year-End chart:

- Source: `weekly`
- Entity key: current merge-level track key represented by `track_id`
- Display fields: `track_id`, `track_name`, `artist_name`, `artist_names`, `cover_url`

Album Year-End chart:

- Source: `weekly_album`
- Entity key: `(album_name, artist_name)`
- Semantics: album project chart semantics
- Constraint: keep existing "no pre-release weekly album credit" rule
- Display fields: `album_name`, `artist_name`, `cover_url`, `release_date`, `album_type`

Artist Year-End chart:

- Source: `weekly_artist`
- Entity key: `artist_name`
- Display fields: `artist_name`, `cover_url`

## API Design

Add:

```text
GET /api/billboard/year-end
```

Query parameters:

- `year`: optional integer. If omitted, use the latest available Billboard year.
- `merge_level`: existing merge config parameter.
- `include_compilations`: existing album chart option.
- Standard Billboard filter settings from `BillboardFilters`, except `year_start` and `year_end` are ignored for this endpoint because `year` is the explicit annual window.
- Year-End chart size is independent from weekly Billboard chart size: tracks use Top 50, albums Top 30, and artists Top 30.

Response shape:

```json
{
  "meta": {
    "year": 2025,
    "available_years": [2023, 2024, 2025],
    "total_weeks": 52,
    "top_n": 50,
    "album_top_n": 30,
    "artist_top_n": 30,
    "week_start_dow": 4,
    "week_start_hour": 0,
    "score_label": "Year-End Score"
  },
  "tracks": [],
  "albums": [],
  "artists": [],
  "honors": {}
}
```

Rows should use explicit year-end naming to avoid confusing them with All-Time rows:

- `year_end_score`
- `year_end_rank`
- `peak_position`
- `weeks_on_chart`
- `weeks_at_no1`
- `weeks_top5`
- `weeks_top10`
- `weeks_at_peak`
- `chart_plays`
- `first_week`
- `last_week`
- `is_true_debut_no1`

Tie-breaker order:

```text
year_end_score desc
weeks_at_no1 desc
peak_position asc
weeks_top10 desc
chart_plays desc
```

## Year-End Honors

The page should include honors generated from the annual rows. Honors are explanatory and should not affect the main ranking.

Required honors:

- `year_end_no1_track`
- `year_end_no1_album`
- `year_end_no1_artist`
- `longest_charting_track`
- `longest_charting_album`
- `longest_charting_artist`
- `biggest_no1_run_track`
- `biggest_no1_run_album`
- `biggest_no1_run_artist`
- `top_new_entry_track`
- `breakthrough_artist`
- `album_era_of_the_year`

Honor definitions:

- Year-End #1: first row in each annual chart.
- Longest charting: highest `weeks_on_chart`, then score tie-breaker.
- Biggest #1 run: highest `weeks_at_no1`, then score tie-breaker.
- Top new entry track: highest-ranked track whose true first chart week belongs to the selected year.
- Breakthrough artist: highest-ranked artist whose first artist-chart week belongs to the selected year.
- Album era of the year: highest-ranked album, with secondary emphasis on `weeks_at_no1` and charting tracks.

## Frontend Experience

Route:

```text
/billboard/year-end
```

The page structure:

- Billboard subnav with active item `year-end`.
- Header: `Billboard 年榜`.
- Year selector with available years from API meta.
- Entity tabs: `年度单曲榜`, `年度专辑榜`, `年度艺人榜`.
- Honors section.
- Paginated annual table.

The table should preserve the dense Billboard style used by All-Time charts:

- 50 rows per page.
- Sortable columns.
- Stable column widths.
- Cover thumbnails with lazy loading.
- Entity links to existing music detail routes.
- No nested cards.
- No page-level horizontal overflow at 390px.

## Architecture

Backend:

- Create a focused domain module for annual chart aggregation.
- Add a staged cached wrapper so annual computation reuses `_load_and_rank_cached`.
- Add a small API router with response models.
- Include the router under the existing `/api/billboard` router.

Frontend:

- Create a thin route container.
- Create feature-first components under `frontend/src/features/billboard/year-end/`.
- Add types to `frontend/src/types/billboard.ts`.
- Add TanStack Query key and hook.
- Add route, subnav item, smoke markers, and long-list coverage.

## Error Handling

- If no Billboard weeks exist, return empty arrays, `available_years: []`, and `year: null`.
- If `year` is outside available years, return 422 with a clear validation detail.
- The route must return `X-Request-ID` through the existing middleware.
- The API must declare a `response_model`.

## Testing

Backend tests:

- Unit tests for annual score windowing.
- Unit test that track Year-End score uses annual #1 weeks instead of debut #1 bonus.
- Unit tests for tie-breaker ordering.
- Contract test for `/api/billboard/year-end` response model and OpenAPI schema.
- Parameter boundary test for invalid `year`.

Frontend tests:

- Type/data builder tests for table rows and honors.
- Architecture guard for route container size and feature split.
- Long-list pagination test for the Year-End table.
- Route smoke marker for `/billboard/year-end`.
- Control inventory smoke should cover the year selector and entity tabs through the existing scripts.

## Documentation

Update:

- `README.md` Billboard feature summary.
- `AGENTS.md` and `CLAUDE.md` only if implementation changes architecture or verification commands.
- `docs/playback-stats/rules.md` with a short Year-End rule section.

## Acceptance Criteria

- `/api/billboard/year-end` returns annual tracks, albums, artists, and honors for the latest available year.
- Selecting another available year changes all charts and honors.
- Annual #1s can differ from All-Time #1s because the scoring window is annual.
- Track, album, and artist Year-End scores all use annual #1 weeks as the dominance bonus.
- Album Year-End chart uses album project semantics.
- Frontend route renders desktop and 390px mobile without console errors or horizontal overflow.
- `npm run build`, backend targeted tests, and frontend targeted tests pass.
