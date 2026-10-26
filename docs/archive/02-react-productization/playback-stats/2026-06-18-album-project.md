# Album Project Playback Stats Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Bring album/song version merging, album project play counts, Billboard album ranking, source breakdown, compilation handling, and frontend explanation into alignment with `docs/playback-stats/rules.md`.

**Architecture:** Keep the valid-play-event layer unchanged: `load_plays()` still performs music filtering, same-`track_id` consecutive merge, dynamic threshold filtering, and Billboard week boundary handling. Add an album-project attribution layer that maps valid play events to canonical songs, then to a single default album project per canonical song, with source-album breakdown retained as explanation. Replace album ranking entry points so they consume this layer instead of grouping by `source_album_id` or release-group canonical album names directly.

**Tech Stack:** FastAPI, SQLite migrations, pandas, pytest unit/contract tests, React 19, TanStack Query, TypeScript, Vite.

---

## Implementation Status

Status: implemented and accepted on 2026-06-18. All task checkboxes below are marked complete because the album-project counting layer, Billboard album aggregation, album detail payload, version-merge management endpoints, frontend explanation section, seed fixtures, and documentation updates have shipped in the current working tree.

P3 governance closeout completed on 2026-06-18:

- OpenAPI artifacts regenerated from the running FastAPI app with `npm run generate-types -- http://127.0.0.1:8000/openapi.json`.
- Generated contract files now include `album_project`, `/api/version-merge/track-group-candidates/collaboration`, and `/api/version-merge/album-projects/rebuild`.
- Freshness verified with `npm run check-types-fresh`.
- Frontend type/build validation passed with `npm run build`.
- No incomplete checklist items remain in this implementation plan.

Previous semantic verification for this implementation:

- `python backend/tests/fixtures/build_seed_db.py`
- `pytest backend/tests/unit/test_album_project_resolver.py backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_album_release_groups.py backend/tests/contract/test_merge_level_aggregation.py backend/tests/contract/test_billboard_counting_consistency.py -q`
- `pytest -m unit -q`
- `pytest -m contract -q`
- `ruff check backend/`
- `npm test`

---

## Scope And Non-Goals

This plan changes default album statistics in analysis pages, leaderboard-style endpoints, Billboard album rankings, album details, version merge management, and frontend explanation sections.

This plan does not change the valid-play-event definition, the artist fan-out rule, Spotify import semantics, OAuth, enrichment providers, or Streamlit frozen pages.

The implementation should preserve these invariants:

- `merge_level` never changes valid play event count.
- L1 album charts keep physical album container semantics.
- L2/L3 album charts use album project membership semantics.
- The same canonical song contributes at most once to the same album project.
- Source breakdown bucket totals equal album project plays.
- Billboard album charts never include plays before `album_project.release_date`.
- Existing track and artist Billboard semantics remain unchanged except where album detail pages use album-project membership to list album tracks.

---

### New Backend Domain Layer

- Create: `backend/domains/playback/album_projects.py`
  - Own album project schema helpers, project bootstrap from current tables, canonical song ownership, album project aggregation, Billboard release filtering, and source breakdown.
- Create: `backend/tests/contract/test_album_project_rules.py`
  - Contract tests for latest album project rules.
- Create: `backend/tests/unit/test_album_project_resolver.py`
  - Unit tests for resolver behavior on small in-memory DataFrames.

### Database And Migrations

- Modify: `backend/core/db.py`
  - Add `album_projects`, `album_project_albums`, `album_project_tracks`, and optional `agg_weekly_track_sources` tables to `SCHEMA`.
  - Update `build_aggregations()` after the album-project ranking is ready.
- Modify: `backend/core/migrations.py`
  - Add idempotent migrations and indexes for album project tables.
- Modify: `backend/tests/fixtures/build_seed_db.py`
  - Add deterministic fixture albums, tracks, plays, release groups, and metadata for pre-release singles, deluxe albums, pure compilations, compilation-exclusive tracks, and L3 rerecord/collaboration cases.

### Backend Statistics Entry Points

- Modify: `backend/services/analysis_stats_service.py`
  - Replace album branch in `_chart_agg()` / `chart_rows()` with album project aggregation for `merge_level > 1`.
- Modify: `backend/services/play_service.py`
  - Replace album branch in `get_leaderboard()` and yearly top album calculations that are meant to reflect album statistics.
- Modify: `backend/domains/billboard/chart_ranking.py`
  - Replace `compute_album_weekly_rankings()` implementation with album project weekly aggregation.
- Modify: `backend/domains/billboard/version_merge.py`
  - Stop using release-group row merging as the default album chart engine; keep it as a relationship resolver and compatibility utility.
- Modify: `backend/domains/billboard/details.py`
  - Add album project payload, track set, version list, source breakdown, and Billboard eligibility dates.
- Modify: `backend/api/billboard/details.py`
  - Tighten response models for new album detail fields.
- Modify: `backend/api/version_merge.py`
  - Add album project rebuild endpoint and optional collaboration candidate endpoint.

### Frontend

- Modify: `frontend/src/types/billboard.ts`
  - Add `AlbumProject`, `AlbumProjectTrack`, `AlbumSourceBreakdownItem`, and new fields on `AlbumDetailResponse`.
- Create: `frontend/src/features/music/details/AlbumProjectSection.tsx`
  - Render album project overview, track set, source breakdown, and release eligibility.
- Modify: `frontend/src/features/music/details/AlbumDetailExperience.tsx`
  - Insert `AlbumProjectSection` near the hero/version section.
- Modify: `frontend/src/features/music/details/VersionGroupSection.tsx`
  - Keep release version display, but stop presenting version group plays as the album project total.
- Modify: `frontend/src/tests/phase5-architecture.test.ts`
  - Add guard that album detail project rendering stays in feature components.

### Docs

- Modify: `docs/playback-stats/rules.md`
  - Append implementation status after completion.
- Modify: `docs/productization/2026-06-08-phase5-baseline.md`
  - Record shipped behavior and validation matrix.
- Modify: `AGENTS.md` and `CLAUDE.md`
  - Update album project counting guidance after backend and frontend ship.
- Modify: `README.md`
  - Summarize user-visible album statistics changes.

---

## Implementation Phases

1. Fixture and failing tests.
2. Album project schema and bootstrap.
3. Album project resolver and source breakdown.
4. Personal album charts and leaderboard replacement.
5. Billboard album chart replacement and preaggregation consistency.
6. Album detail API and frontend explanation.
7. Compilation and collaboration management polish.
8. Documentation and full verification.

Each phase should be independently verifiable before continuing.

---

## Task 0: Add Latest-Rule Fixtures And Failing Contract Tests

**Purpose:** Lock the new behavior before touching production code.

涉及文件：`backend/tests/fixtures/build_seed_db.py`、`backend/tests/contract/test_album_project_rules.py`。

- Step 0.1: Add fixture albums and metadata
- Step 0.2: Add fixture tracks and relationships

Add track metadata:

- Step 0.3: Add fixture release and track groups

Add featured artist relationship for collaboration:

- Step 0.4: Add fixture plays with exact expected totals

Add these plays near the end of the existing fixture play list:

- Step 0.5: Write failing contract tests
- Step 0.6: Run the new tests and verify failure

---

## Task 1: Add Album Project Schema And Bootstrap

**Purpose:** Represent album projects explicitly while preserving existing release groups and track groups.

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/domains/playback/album_projects.py`、`backend/tests/unit/test_album_project_resolver.py`。

- Step 1.1: Add schema tables

```sql
CREATE TABLE IF NOT EXISTS album_projects (
    project_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name    TEXT NOT NULL,
    artist_id         INTEGER REFERENCES artists(artist_id),
    primary_album_id  INTEGER REFERENCES albums(album_id),
    release_date      TEXT,
    scope             TEXT NOT NULL DEFAULT 'release',
    project_type      TEXT NOT NULL DEFAULT 'album',
    include_in_charts INTEGER NOT NULL DEFAULT 1,
    is_manual         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(canonical_name, artist_id, scope)
);

CREATE TABLE IF NOT EXISTS album_project_albums (
    project_id    INTEGER NOT NULL REFERENCES album_projects(project_id),
    album_id      INTEGER NOT NULL REFERENCES albums(album_id),
    role          TEXT NOT NULL DEFAULT 'member',
    source_bucket TEXT NOT NULL DEFAULT 'other',
    inferred      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, album_id)
);

CREATE TABLE IF NOT EXISTS album_project_tracks (
    project_id       INTEGER NOT NULL REFERENCES album_projects(project_id),
    track_id         INTEGER NOT NULL REFERENCES tracks(track_id),
    membership_role  TEXT NOT NULL DEFAULT 'standard',
    min_merge_level  INTEGER NOT NULL DEFAULT 2,
    source_album_id  INTEGER REFERENCES albums(album_id),
    is_exclusive     INTEGER NOT NULL DEFAULT 0,
    inferred         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, track_id, min_merge_level)
);

CREATE INDEX IF NOT EXISTS idx_album_projects_artist ON album_projects(artist_id);
CREATE INDEX IF NOT EXISTS idx_album_projects_primary_album ON album_projects(primary_album_id);
CREATE INDEX IF NOT EXISTS idx_album_project_albums_album ON album_project_albums(album_id);
CREATE INDEX IF NOT EXISTS idx_album_project_tracks_track ON album_project_tracks(track_id);
```

- Step 1.2: Add migration helpers

In `backend/core/migrations.py`, add an idempotent migration function that executes the same SQL and runs during `ensure_schema()`. Use table and index names exactly as above.

- Step 1.3: Add bootstrap function signature
- Step 1.4: Write unit test for idempotency
- Step 1.5: Implement bootstrap
- `canonical_name = release_groups.canonical_name`
- `artist_id = release_groups.artist_id`
- `primary_album_id = release_groups.primary_album_id`
- `scope = release_groups.scope`
- `release_date = spotify_album_meta.release_date` for `primary_album_id`
- `project_type = 'album'`
- `include_in_charts = 1`
- members from `release_group_members`

Set source buckets:

- primary album role: `original_album`
- album name containing `deluxe`, `expanded`, `anniversary`, `spilled`, `edition`: `deluxe`
- album name containing `taylor's version`, `rerecorded`, `re-recorded`: `rerecord`
- `spotify_album_meta.album_type = 'single'`: `single`
- `spotify_album_meta.album_type = 'compilation'`: `compilation`
- otherwise: `other`

Implement `_bootstrap_standalone_album_projects()` so eligible LP/EP albums outside release groups create projects when `classify_album()` returns `lp` or `ep`.

Implement `_bootstrap_compilation_exclusive_projects()` so compilation albums only create a project when at least one member track has no non-compilation album project.

- Step 1.6: Run schema/bootstrap tests

---

## Task 2: Implement Canonical Song Membership And Album Source Breakdown

**Purpose:** Make album project plays computable from valid events rather than source album row grouping.

涉及文件：`backend/domains/playback/album_projects.py`、`backend/tests/unit/test_album_project_resolver.py`、`backend/tests/contract/test_album_project_rules.py`。

- Step 2.1: Add canonical song key helper
- Step 2.2: Add album project membership resolver

- Step 2.3: Add album project aggregation

- Step 2.4: Add source breakdown

Implement `_attach_source_album_bucket()` using `source_album_id`, `albums`, and `spotify_album_meta`. If `source_album_id` is null, set `source_bucket = 'inferred'`.

- Step 2.5: Run unit and contract tests

---

## Task 3: Replace Personal Album Chart And Leaderboard Aggregation

**Purpose:** Make `/api/analysis/charts?entity=album` and leaderboard album rows use album project semantics.

涉及文件：`backend/services/analysis_stats_service.py`、`backend/services/play_service.py`、`backend/tests/contract/test_album_project_rules.py`、`backend/tests/contract/test_album_release_groups.py`。

- Step 3.1: Replace album branch in `_chart_agg()`

Keep the existing single/compilation filtering in `chart_rows()` only as a compatibility guard for L1. For `merge_level > 1`, filtering is already handled by `compute_album_project_plays(... include_compilations=include_compilations)`.

- Step 3.2: Pass `include_compilations` into `_chart_agg()`

Change `_chart_agg()` signature to:

- Step 3.3: Update album row payload
- Step 3.4: Replace album branch in `get_leaderboard()`

In `backend/services/play_service.py`, replace the `entity == "album"` branch with the same helper. Keep track and artist branches unchanged.

- Step 3.5: Update old release-group tests
- Keep `test_fixture_single_excluded_from_default_album_chart`.
- Add assertion that `Fixture Future Single` does not appear as standalone in L2.
- Add assertion that `Fixture Future LP` appears with 9 plays in L2.
- Keep release group map tests unchanged because release groups still exist.
- Step 3.6: Run chart tests

---

## Task 4: Replace Billboard Album Ranking

**Purpose:** Make weekly album charts use album project plays and enforce release-date eligibility.

涉及文件：`backend/domains/billboard/chart_ranking.py`、`backend/domains/billboard/version_merge.py`、`backend/tests/contract/test_album_project_rules.py`、`backend/tests/contract/test_billboard_attribution.py`。

- Step 4.1: Replace `compute_album_weekly_rankings()` raw path
- Step 4.2: Add helper for preagg compatibility
- `billboard_week`
- `track_id`
- `source_album_id`
- `play_count`
- `total_ms`
- `ts`
- `track_name`
- `artist_name`
- `album_name`

This is a correctness bridge. Task 5 replaces it with a base-grain preaggregation table so large datasets do not expand rows.

- Step 4.3: Stop applying release-group row merge after project aggregation

Remove `_apply_album_release_groups()` from the album weekly path. Keep `backend/domains/billboard/version_merge.py` for legacy utilities and detail version display.

- Step 4.4: Run Billboard contract tests

---

- 历史验收要求：Billboard album project tests pass. If an old test asserts source album grouping, update it to assert album project grouping.

- 历史实施约束：It should expand `play_count` into minimal event-like rows for aggregation.

## Task 5: Add Base-Grain Preaggregation For Album Project Billboard

**Purpose:** Avoid row expansion and keep raw fallback and preaggregation consistent.

涉及文件：`backend/core/db.py`、`backend/domains/billboard/data_loader.py`、`backend/domains/billboard/chart_ranking.py`、`backend/tests/contract/test_billboard_counting_consistency.py`。

- Step 5.1: Add `agg_weekly_track_sources` table

```sql
CREATE TABLE IF NOT EXISTS agg_weekly_track_sources (
    billboard_week TEXT NOT NULL,
    play_date TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    source_album_id INTEGER,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, play_date, track_id, source_album_id)
);

CREATE INDEX IF NOT EXISTS idx_agg_wts_week ON agg_weekly_track_sources(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_wts_track ON agg_weekly_track_sources(track_id);
CREATE INDEX IF NOT EXISTS idx_agg_wts_source_album ON agg_weekly_track_sources(source_album_id);
```

`play_date` is required because an album can release mid-week and Billboard album eligibility must filter `play_date >= release_date`.

- Step 5.2: Populate track-source preaggregation

Write rows into `agg_weekly_track_sources`.

- Step 5.3: Load preaggregation with names
- Step 5.4: Wire Billboard data loader

In `backend/domains/billboard/data_loader.py`, load `agg_weekly_track_sources` for album rankings instead of `agg_weekly_albums` when the table exists and row count is positive.

- Step 5.5: Add raw vs preagg consistency test
- Step 5.6: Run consistency tests

历史验收预期： raw and preaggregation album charts match.

---

## Task 6: Add Album Project Detail Payload And Frontend Section

**Purpose:** Explain the new album statistics in album detail pages.

涉及文件：`backend/domains/billboard/details.py`、`backend/api/billboard/details.py`、`frontend/src/types/billboard.ts`、`frontend/src/features/music/details/AlbumProjectSection.tsx`、`frontend/src/features/music/details/AlbumDetailExperience.tsx`、`frontend/src/tests/phase5-architecture.test.ts`。

- Step 6.1: Add backend detail helper
- Step 6.2: Add response model fields
- Step 6.3: Add payload to album detail return

Use the same valid-play DataFrame that feeds `compute_billboard_data()` when available. If `compute_billboard_data()` does not expose it, load it with the same filters and pass the same `dynamic_threshold` / `max_merge_gap_minutes` values.

- Step 6.4: Add frontend types

Extend `AlbumDetailResponse`:

- Step 6.5: Create frontend section
- Step 6.6: Insert section into album detail

Render near the top:

- Step 6.7: Run frontend checks

---

## Task 7: Add Compilation And Collaboration Management Support

**Purpose:** Make the data-management surface able to maintain the new relationships safely.

涉及文件：`backend/core/version_merge.py`、`backend/api/version_merge.py`、`frontend/src/features/settings/components/VersionMergeSection.tsx`、`backend/tests/contract/test_album_project_rules.py`。

- Step 7.1: Add collaboration candidate detector

This endpoint produces candidates only; applying them still requires user confirmation.

- Step 7.2: Expose collaboration candidates
- Step 7.3: Add rebuild endpoint
- Step 7.4: Update settings UI
- Rebuild Album Projects: `POST /version-merge/album-projects/rebuild`
- Collaboration Candidates: `GET /version-merge/track-group-candidates/collaboration`

Use existing API client and existing card layout. Do not add a new page.

- Step 7.5: Run backend tests

历史验收预期： L3 collaboration fixture remains merged through confirmed `track_groups`; candidate endpoint does not affect counts by itself.

---

## Task 8: Documentation, Regression Matrix, And Final Verification

**Purpose:** Make the new rules durable and easy to verify later.

涉及文件：`docs/playback-stats/rules.md`、`docs/productization/2026-06-08-phase5-baseline.md`、`AGENTS.md`、`CLAUDE.md`、`README.md`。

- Step 8.1: Update rules doc status

```markdown
## 17. Implementation Status

As of 2026-06-18, album statistics use album project semantics in analysis charts, leaderboards, Billboard album charts, and album detail pages.

Key implemented invariants:

- Valid play events are independent from `merge_level`.
- L2/L3 album statistics use album project track membership.
- Pre-release singles count toward all-time album project totals.
- Billboard album charts exclude plays before the album project release date.
- Source breakdown buckets sum to album project plays.
- Pure existing-song compilations do not become standalone non-L1 album projects.
- Compilation-exclusive tracks can form a compilation-exclusive project.
```

- Step 8.2: Update Phase 5 baseline
- album project tables
- album project resolver
- analysis chart replacement
- Billboard album chart replacement
- source breakdown frontend
- validation commands and results
- Step 8.3: Update assistant guidance docs

```markdown
- L2/L3 album statistics must use album project track membership, not source album row grouping.
- Source album attribution is explanatory only and appears through source breakdown.
- Billboard album charts must filter album project plays by `play_ts >= album_project.release_date`.
- Existing release groups describe album-version relationships; they are not the final album play-count aggregation layer.
```

- Step 8.4: Update README

Add a user-facing note:

```markdown
Album statistics now use album project semantics: standard/deluxe versions, included lead singles, and confirmed project versions are counted together according to the selected merge level. Album detail pages include a source breakdown so the total can be traced back to original album, deluxe, single, compilation, and inferred sources.
```

- Step 8.5: Run focused backend verification

- Step 8.6: Run broader verification

- Step 8.7: Manual seed probes
- `fixture_future_lp[0].play_count == 9`
- breakdown play counts sum to 9
- first Billboard week is on or after `2026-02-01`

---

## Risk Register

- **High:** Album project membership may undercount songs that appear on multiple legitimate projects. Mitigation: default mode enforces one owner per canonical song; add catalog membership view later if multi-project membership is needed.
- **High:** Billboard album preaggregation cannot enforce mid-week release dates without `play_date`. Mitigation: add `agg_weekly_track_sources` with `play_date`.
- **Medium:** Existing release-group tests encode old source-album behavior. Mitigation: preserve release group resolver tests, update chart-output tests to album project semantics.
- **Medium:** Album detail currently derives album tracks from charting tracks. Mitigation: use album project membership for detail track set, and keep charting metrics as separate fields.
- **Medium:** Compilation-exclusive detection may require manual correction. Mitigation: bootstrap only obvious cases and keep rebuild endpoint idempotent.
- **Low:** Frontend users may be surprised that album total exceeds source album plays. Mitigation: always show source breakdown near album project total.

---

## Recommended Commit Boundaries

1. `test: add album project playback fixtures`
2. `feat: add album project schema and resolver`
3. `feat: use album project totals in analysis charts`
4. `feat: rank Billboard albums by album project plays`
5. `perf: add track-source preaggregation for album charts`
6. `feat: explain album project totals in album detail`
7. `feat: expose album project rebuild and collaboration candidates`
8. `docs: document album project playback semantics`

Do not commit automatically unless the user explicitly asks for commits.
