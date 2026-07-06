# Billboard Year-End Implementation Plan

Date: 2026-06-26

## Goal

Add a personal Billboard Year-End section with annual track, album, and artist charts plus selected annual honors.

The feature should feel like a personal version of Billboard's official year-end charts: it ranks annual chart performance instead of raw annual play count.

## Final Decisions

- Route: `/billboard/year-end`.
- API: `GET /api/billboard/year-end`.
- Year selector uses available Billboard years from the API response.
- Main tabs: `单曲榜`, `专辑榜`, `艺人榜`.
- Year-End chart size is independent from weekly Billboard chart size:
  - tracks: Top 50
  - albums: Top 30
  - artists: Top 30
- Score window: filter weekly Billboard rows to one selected `billboard_week.year` before aggregating.
- Unified annual dominance bonus:

```text
no1_bonus = annual weeks_at_no1 * 40
```

- Track, album, and artist Year-End charts all use:

```text
year_end_score = raw_score + longevity_bonus + peak_bonus + no1_bonus
```

- `is_true_debut_no1` remains a descriptive track fact, but it does not add Year-End score.
- Tie-breakers:

```text
year_end_score desc
weeks_at_no1 desc
peak_position asc
weeks_top10 desc
chart_plays desc
```

## Implementation Checklist

- [x] Add backend Year-End domain scoring and honors module.
- [x] Add staged cached computation and service re-export.
- [x] Add `/api/billboard/year-end` response-model endpoint.
- [x] Add frontend route, TanStack Query hook, year prefetching, tabs, honors, and paginated table.
- [x] Align Billboard subnav and inner tab labels.
- [x] Keep Year-End UI consistent with other Billboard pages.
- [x] Add route smoke and long-list smoke coverage.
- [x] Add backend unit and contract tests.
- [x] Add frontend UI, architecture, and pagination guard tests.
- [x] Update README and playback rules documentation.

## Verification

Targeted commands run during implementation:

```bash
pytest backend/tests/unit/test_billboard_year_end.py backend/tests/contract/test_billboard_year_end_contract.py -q
cd frontend && npm test -- --run
cd frontend && npm run build
node scripts/frontend_route_smoke.mjs --routes /billboard/year-end --viewport both --max-scroll-overflow 0 --fail-on-console-warning
git diff --check
```

The latest focused backend validation passed with 9 tests, and the latest frontend validation passed with 174 tests plus production build and route smoke.
