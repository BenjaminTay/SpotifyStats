# Playback Stats Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Implement the playback counting, entity attribution, version merge, and Billboard consistency rules defined in `docs/playback-stats/2026-06-12-playback-stats-rules.md`.

**Architecture:** Split playback statistics into three layers: counting policy produces stable valid play events, entity attribution maps those events to tracks/albums/artists, and aggregation/ranking applies version merge and display policy. Use path A from the rules document: `merge_consecutive_plays()` only merges adjacent rows with the same `track_id`; cross-track version merge only affects aggregation keys and never changes valid play events.

**Tech Stack:** FastAPI, SQLite migrations, pandas aggregation, pytest unit/contract/integration tests, React 19 + TanStack Query + TypeScript.

---

## Execution Principles

- Keep each phase independently shippable and testable.
- P0 must preserve current product semantics except for fixing Billboard raw fallback vs pre-aggregation inconsistency.
- P1-P3 may change visible statistics; every visible count change must have a fixture test and a changelog/doc note.
- P4 is intentionally high-risk and must not start until P0-P3 have green tests.
- Do not add `merge_level` to base valid-play-event cache keys under path A.
- After each task, run the narrow tests listed for that task before broad test suites.

---

### Counting Policy

- Modify: `backend/core/db.py`
  - Add `effective_threshold()`.
  - Add optional session boundary parameters to `merge_consecutive_plays()`.
  - Keep `_load_plays_cached()` independent from `merge_level`.
- Create: `backend/domains/playback/counting.py`
  - Thin helpers for threshold, post-merge filtering, week/day boundary decisions.
- Test: `backend/tests/unit/test_playback_counting.py`
  - Unit tests for threshold, merge expansion, gap boundary, week boundary.

### Billboard Raw/Aggregated Consistency

- Modify: `backend/domains/billboard/data_loader.py`
  - Raw fallback loads with `min_ms=0` when merge is enabled, then filters after merge.
  - Artist raw path mirrors track/album raw path.
- Modify: `backend/core/db.py`
  - `build_aggregations()` uses the same counting helper as raw fallback.
  - `_agg_param_hash()` includes only parameters that change weekly entity results.
- Test: `backend/tests/contract/test_billboard_counting_consistency.py`
  - Seed DB tests comparing raw fallback and `agg_weekly_*`.

### Source Album And Release Group Semantics

- Modify: `backend/core/db.py`
  - Add `plays.source_album_id` to `SCHEMA`.
  - Extend `release_groups` schema with `scope` and `parent_group_id`.
- Modify: `backend/core/migrations.py`
  - Add migrations for `source_album_id`, release group rebuild, indexes, and backfill.
- Modify: `backend/core/import_data.py`
  - Write `source_album_id` from `master_metadata_album_album_name`.
- Modify: `backend/services/analysis_stats_service.py`
  - Album charts use source album attribution, then release group canonicalization.
- Modify: `backend/domains/billboard/chart_ranking.py`
  - Album weekly ranking uses source album attribution and release group scope.
- Test: `backend/tests/unit/test_migrations.py`
- Test: `backend/tests/contract/test_source_album_attribution.py`
- Test: `backend/tests/contract/test_album_release_groups.py`

### Album Type Taxonomy

- Create: `backend/domains/playback/album_type.py`
  - Classify LP/EP/compilation/single from Spotify `album_type`, total tracks, and duration.
- Modify: `backend/services/analysis_stats_service.py`
  - Personal album chart exposes `album_category` and filters singles by default.
- Modify: `backend/domains/billboard/data_loader.py`
  - Billboard album metadata uses the same taxonomy helper.
- Test: `backend/tests/unit/test_album_type_taxonomy.py`

### Merge Level And Track Groups

- Modify: `backend/dependencies.py`
  - Add `MergeConfig` or `merge_level` query parameter for affected endpoints.
- Create: `backend/domains/playback/merge_levels.py`
  - Normalize and validate merge levels.
- Create: `backend/domains/playback/track_groups.py`
  - Resolve L1/L2/L3 track aggregation keys and group members.
- Modify: `backend/core/db.py`
  - Add `track_groups` and `track_group_members` to `SCHEMA`.
- Modify: `backend/core/migrations.py`
  - Add track group schema migration.
- Modify: `backend/core/version_merge.py`
  - Add detection output for track groups after release group work is stable.
- Test: `backend/tests/unit/test_track_groups.py`
- Test: `backend/tests/contract/test_merge_level_aggregation.py`

### Frontend

- Modify: `frontend/src/api/query-keys.ts`
  - Include `mergeLevel` only in affected query keys.
- Modify: `frontend/src/hooks/useBillboard.ts`
  - Pass `merge_level` to Billboard endpoints.
- Modify: `frontend/src/pages/BillboardPage.tsx`
  - Read and write merge level via URL search params.
- Modify: `frontend/src/pages/SettingsPage.tsx`
  - Add global merge strictness control.
- Modify: `frontend/src/features/settings/components/VersionMergeSection.tsx`
  - Separate album release groups from future track groups.
- Modify: `frontend/src/features/music/details/TrackDetailExperience.tsx`
  - Display version group summary when backend response includes it.
- Modify: `frontend/src/features/music/details/AlbumDetailExperience.tsx`
  - Display release group versions with source-album attribution notes.
- Test: `frontend/src/tests/query-hooks.test.tsx`
- Test: `frontend/src/tests/phase5-architecture.test.ts`

### Documentation

- Modify: `docs/playback-stats/2026-06-12-playback-stats-rules.md`
  - Keep as source of truth for semantics.
- Modify: `docs/productization/2026-06-08-phase5-baseline.md`
  - Record implementation status after each shipped phase.
- Modify: `AGENTS.md` and `CLAUDE.md`
  - Update playback-counting guidance when implementation lands.
- Modify: `README.md`
  - Summarize user-facing statistic changes when visible behavior changes.

---

## Task 0: Baseline And Golden Fixtures

**Purpose:** Create repeatable fixtures before changing behavior.

涉及文件：`backend/tests/fixtures/build_seed_db.py`、`backend/tests/contract/test_playback_rules_baseline.py`、`backend/tests/contract/test_billboard_counting_consistency.py`。

- Step 0.1: Add named fixture scenarios to seed DB

Implement the fixture as explicit inserts, not generated random data. Use stable IDs starting above current seed IDs, for example `artist_id >= 900`, `album_id >= 900`, `track_id >= 900`, `play_id >= 9000`.

- Step 0.2: Add baseline tests for current behavior
- Step 0.3: Run baseline tests

- Step 0.4: Commit

---

## Task 1: P0 Counting Policy Boundary

**Purpose:** Extract the counting boundary without changing product semantics.

涉及文件：`backend/domains/playback/counting.py`、`backend/core/db.py`、`backend/tests/unit/test_playback_counting.py`。

- Step 1.1: Write unit tests for current threshold compatibility
- Step 1.2: Run tests and confirm failure
- Step 1.3: Implement counting helpers
- Step 1.4: Use helper in `backend/core/db.py` without enabling dynamic threshold

Keep imports local inside the cached function or module-level if lint remains clean.

- Step 1.5: Run tests
- Step 1.6: Commit

---

## Task 2: P0 Billboard Raw Fallback Consistency

**Purpose:** Make Billboard raw fallback use the same merge-then-filter order as pre-aggregation.

涉及文件：`backend/domains/billboard/data_loader.py`、`backend/core/db.py`、`backend/tests/contract/test_billboard_counting_consistency.py`。

- Step 2.1: Write raw vs pre-aggregation parity test
- Step 2.2: Run test and confirm current failure if raw fallback drops short fragments

Expected before implementation: failure or mismatch on fragment scenario.

- Step 2.3: Fix `load_billboard_raw()`

After `merge_consecutive_plays(df, min_ms)`, apply:

- Step 2.4: Fix `load_billboard_raw_for_artists()` the same way

Use `base_filters(min_ms=0, music_only=music_only)` before merge and `filter_effective_plays()` after merge, before joining `track_artists`.

- Step 2.5: Make `build_aggregations()` use the same helper

- Step 2.6: Run narrow and Billboard tests
- Step 2.7: Commit

---

## Task 3: P1 Source Album Schema And Import

**Purpose:** Preserve playback-time album attribution instead of inferring every play from `tracks.album_id`.

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/core/import_data.py`、`backend/tests/unit/test_migrations.py`、`backend/tests/contract/test_source_album_attribution.py`。

- Step 3.1: Add migration test

Extend `backend/tests/unit/test_migrations.py`:

- Step 3.2: Update schema

```sql
source_album_id INTEGER REFERENCES albums(album_id),
```

Add index:

```sql
CREATE INDEX IF NOT EXISTS idx_plays_source_album ON plays(source_album_id);
```

- Step 3.3: Add migration
- Step 3.4: Update import path

In `backend/core/import_data.py`, when inserting a play row, pass the album ID resolved from the raw `master_metadata_album_album_name` as `source_album_id`. Keep `tracks.album_id` unchanged for canonical/default track dimension.

Then insert `source_album_id` into `plays`.

- Step 3.5: Add source album attribution contract test

This test expects `load_plays` with `join_albums=True` to expose the playback-time album as `source_album_name`. Keep `album_name` as a compatibility alias only if existing callers still need it.

- Step 3.6: Run tests
- Step 3.7: Commit

---

## Task 4: P1 Release Group Scope And Canonical Album Aggregation

**Purpose:** Apply release group canonicalization consistently to personal album charts and Billboard album charts.

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/domains/playback/release_groups.py`、`backend/domains/billboard/version_merge.py`、`backend/services/analysis_stats_service.py`、`backend/tests/contract/test_album_release_groups.py`。

- Step 4.1: Add migration test for release group scope
- Step 4.2: Rebuild release group table in migration

SQLite cannot drop the old `UNIQUE(canonical_name, artist_id)` constraint in place. Add a table rebuild migration:

- Step 4.3: Create release group resolver
- Step 4.4: Apply resolver in personal album chart

Then group by `album_agg_id`, `album_agg_name`, and `artist_name`.

- Step 4.5: Apply same resolver in Billboard album ranking

In `backend/domains/billboard/version_merge.py`, update `_apply_album_release_groups()` to accept `merge_level: int = 2`, filter by `scope='release'` for L2 and `scope='composition'` for L3, and leave L1 unchanged.

- Step 4.6: Add contract test
- Step 4.7: Run tests
- Step 4.8: Commit

---

## Task 5: P2 Dynamic Threshold And Session Boundaries

**Purpose:** Enable fairer valid-play filtering for long tracks and prevent unrealistic long-gap merges.

涉及文件：`backend/domains/playback/counting.py`、`backend/core/db.py`、`backend/dependencies.py`、`backend/tests/unit/test_playback_counting.py`、`backend/tests/contract/test_playback_rules_baseline.py`。

- Step 5.1: Add tests for dynamic threshold
- Step 5.2: Add session boundary tests
- Step 5.3: Extend `merge_consecutive_plays()` signature

Group breaks when:

- Step 5.4: Add query parameters with conservative defaults

Store them on `PlayFilters` and `BillboardFilters`.

- Step 5.5: Wire dynamic threshold in loaders

Pass `dynamic_threshold` and `max_merge_gap_minutes` to affected service calls in a follow-up mechanical change. Keep default `False` until UI/doc release is ready.

- Step 5.6: Run tests
- Step 5.7: Commit

---

## Task 6: P3 Album Type Taxonomy

**Purpose:** Classify LP/EP/compilation/single consistently across personal and Billboard album charts.

涉及文件：`backend/domains/playback/album_type.py`、`backend/services/analysis_stats_service.py`、`backend/domains/billboard/data_loader.py`、`backend/tests/unit/test_album_type_taxonomy.py`。

- Step 6.1: Add taxonomy tests
- Step 6.2: Implement taxonomy helper
- Step 6.3: Add category to album aggregations

Default filtering:

- Step 6.4: Add tests and run
- Step 6.5: Commit

---

## Task 7: P4 Track Groups Schema And Aggregation Keys

**Purpose:** Add L1/L2/L3 track version aggregation without changing valid play events.

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/domains/playback/merge_levels.py`、`backend/domains/playback/track_groups.py`、`backend/services/analysis_stats_service.py`、`backend/domains/billboard/chart_ranking.py`、`backend/tests/unit/test_track_groups.py`、`backend/tests/contract/test_merge_level_aggregation.py`。

- Step 7.1: Add migration for track group tables

```sql
CREATE TABLE IF NOT EXISTS track_groups (
    group_id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    primary_track_id INTEGER REFERENCES tracks(track_id),
    scope TEXT NOT NULL CHECK(scope IN ('recording', 'composition')),
    parent_group_id INTEGER REFERENCES track_groups(group_id),
    is_manual BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_group_members (
    group_id INTEGER REFERENCES track_groups(group_id),
    track_id INTEGER REFERENCES tracks(track_id),
    UNIQUE(group_id, track_id)
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_track_groups_scope ON track_groups(scope);
CREATE INDEX IF NOT EXISTS idx_track_groups_parent ON track_groups(parent_group_id);
CREATE INDEX IF NOT EXISTS idx_track_group_members_track ON track_group_members(track_id);
```

- Step 7.2: Implement merge level normalization

`backend/domains/playback/merge_levels.py`:

- Step 7.3: Implement track aggregation key resolver

`backend/domains/playback/track_groups.py`:

- Step 7.4: Apply resolver only in aggregation layer

Group by `track_agg_id`, `track_agg_name`, `artist_name`, and `album_name`. Do not pass `merge_level` into `load_plays()` or `_load_plays_cached()`.

When `pre_agg is None`, apply track group keys before the weekly groupby. When `pre_agg` is present, build separate pre-aggregation rows per `merge_level` as described in Task 8 instead of re-grouping already-ranked rows.

- Step 7.5: Add tests

`backend/tests/contract/test_merge_level_aggregation.py` should assert:

- Step 7.6: Run tests
- Step 7.7: Commit

---

## Task 8: Merge Level API And Frontend State

**Purpose:** Let users switch strictness without corrupting cache boundaries.

涉及文件：`backend/dependencies.py`、`backend/api/analysis.py`、`backend/api/billboard/data.py`、`frontend/src/api/query-keys.ts`、`frontend/src/hooks/useBillboard.ts`、`frontend/src/pages/BillboardPage.tsx`、`frontend/src/pages/SettingsPage.tsx`、`frontend/src/tests/query-hooks.test.tsx`、`frontend/src/tests/phase5-architecture.test.ts`。

- Step 8.1: Add backend dependency

Use it only in endpoints that return affected track/album/Billboard aggregations.

- Step 8.2: Add frontend query key parameter

Ensure callers include:

- Step 8.3: Add URL state to Billboard page

Write on change:

- Step 8.4: Add tests
- Step 8.5: Run frontend tests
- Step 8.6: Commit

---

## Task 9: Version Detail Displays

**Purpose:** Make merged entities explainable in track and album detail pages.

涉及文件：`backend/domains/billboard/details.py`、`backend/api/billboard/details.py`、`frontend/src/types/billboard.ts`、`frontend/src/features/music/details/TrackDetailExperience.tsx`、`frontend/src/features/music/details/AlbumDetailExperience.tsx`、`frontend/src/features/music/details/VersionGroupSection.tsx`、`frontend/src/tests/phase5-architecture.test.ts`。

- Step 9.1: Add backend response fields

Album detail responses should include:

- Step 9.2: Add shared frontend section

Create `frontend/src/features/music/details/VersionGroupSection.tsx` as a presentational component. It receives normalized rows and renders a compact table/list. It must not fetch data.

- Step 9.3: Wire into detail experiences

In track and album detail experiences, render the section only when group data exists and has at least two versions.

- Step 9.4: Run build/tests
- Step 9.5: Commit

---

## Task 10: Consistency Test Matrix And Documentation

**Purpose:** Lock the semantics so future changes cannot silently drift.

涉及文件：`backend/tests/contract/test_playback_invariants.py`、`docs/playback-stats/2026-06-12-playback-stats-rules.md`、`docs/productization/2026-06-08-phase5-baseline.md`、`README.md`、`AGENTS.md`、`CLAUDE.md`。

- Step 10.1: Add invariant tests

In the same file, add these invariants after implementing Tasks 3 and 4:

- Step 10.2: Run minimum backend matrix
- Step 10.3: Run frontend matrix
- Step 10.4: Update docs

```markdown
## Implementation Status

| Phase | Status | Verification |
|---|---|---|
| P0 counting policy consistency | Done | `pytest backend/tests/contract/test_billboard_counting_consistency.py -v` |
| P1 source album + release groups | Done | `pytest backend/tests/contract/test_source_album_attribution.py backend/tests/contract/test_album_release_groups.py -v` |
| P2 dynamic threshold | Done | `pytest backend/tests/unit/test_playback_counting.py -v` |
```

Only mark phases as `Done` after tests pass.

- Step 10.5: Keep AGENTS and CLAUDE synchronized

历史验收预期： exit code 0.

- Step 10.6: Commit

---

### Phase A: Safe Semantics Baseline ✅

Tasks: 0, 1, 2 — **已完成 2026-06-12**

Expected behavior change: Billboard raw fallback no longer drops short fragments before merge. Other stats should remain effectively unchanged.

### Phase B: Album Attribution And Release Canonicalization ✅

Tasks: 3, 4, 6 — **已完成 2026-06-12**

Expected behavior change: album charts become source-album based, canonical album merging becomes consistent, singles are excluded from album charts by default.

### Phase C: Dynamic Counting Policy ✅

Tasks: 5 — **已完成 2026-06-12**

Expected behavior change: long-track snippets below 10% duration no longer count when dynamic threshold is enabled. Keep default disabled until UI and release note are ready; enable default in a separate commit after reviewing visible metric deltas.

### Phase D: Track Version Merge ✅

Tasks: 7, 8, 9 — **已完成 2026-06-12**

Expected behavior change: track and album rankings can switch L1/L2/L3 merge levels; valid play events remain unchanged.

### Phase E: Final Guardrails ✅

Tasks: 10 — **已完成 2026-06-12**

Expected behavior change: none; this phase locks documentation and regression checks.

---

## Open Implementation Decisions

1. Dynamic threshold default should remain `False` until the app can show before/after metric deltas.
2. `source_album_id` historical backfill should be explicitly labeled as inferred data.
3. Catalog membership view should remain separate from default album chart and should not ship before source album chart is stable.
4. Track group auto-detection should not auto-merge low-confidence Acoustic/Live/Remix candidates; it should create review candidates first.
5. If path B is ever adopted, it requires a new plan because it changes valid play events, cache keys, pre-aggregation hash, and user-facing totals.

---

## Completion Checklist

- P0 raw and pre-aggregated Billboard outputs match on seed fixtures.
- Source album is persisted on new imports and backfilled for historical data.
- Personal album chart, album detail, and Billboard album chart use the same release group resolver.
- Album type taxonomy is shared between personal and Billboard album charts.
- `merge_level` affects only version-sensitive entity aggregations.
- Track group L2/L3 aggregation does not alter valid play events.
- Version detail sections explain what was merged.
- Contract tests cover the invariants from R24b.
- README, AGENTS, CLAUDE, and phase baseline docs are synchronized.
