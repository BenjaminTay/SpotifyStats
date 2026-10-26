# Import Derived Data Maintenance Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

**Goal:** Make every Streaming History import dynamically maintain the derived backend database layers for newly seen Spotify tracks, albums, artists, album-project membership, covers, and Billboard/analysis aggregations.

**Architecture:** Keep `backend/core/import_data.py` responsible for deterministic local facts from Spotify JSON, then add an explicit post-import maintenance pipeline for online Spotify metadata refresh, local album-to-Spotify-album reconciliation, album project rebuild, preaggregation rebuild, cache invalidation, and import health reporting. Preserve offline import behavior: a missing Spotify API token must leave raw plays usable and produce a clear partial report instead of failing the import.

**Tech Stack:** FastAPI, SQLite migrations, pandas, existing `SpotifyProvider` + shared `HttpClient`, pytest unit/contract tests, existing React Settings import job UI.

---

## Current Failure Mode

The June 2026 data import proves the raw playback layer can ingest new rows, but derived layers drift:

- New play rows exist up to `2026-06-22`.
- Recent audio rows after `2026-05-13`: `2306` plays, `955` distinct tracks, `438` source albums.
- `157` recent tracks have `tracks.spotify_track_id` but no `spotify_track_meta`, so album metadata and covers cannot resolve.
- `145` recent source albums are missing `album_project_albums` membership.
- `Dinner Party` by Niall Horan shows the semantic bug clearly: the local album has 11 local tracks, but name matching hits an old `spotify_album_meta` row with `album_type='single'` and `total_tracks=1`, so album project bootstrap skips it.

The fix must address both classes:

1. Missing online metadata after new JSON import.
2. Incorrect project classification when same artist + album name exists as both a single and a later full album.

---

## Scope And Non-Goals

In scope:

- Persist play-time Spotify identifiers from each JSON row.
- Refresh missing Spotify track, album, and artist metadata through the existing provider stack.
- Reconcile local albums to Spotify album candidates without relying only on album name matching.
- Rebuild album projects after every streaming import and after metadata refresh.
- Rebuild Billboard preaggregations after metadata and album-project maintenance, not before.
- Add a one-shot repair command for the current database.
- Surface partial import state in API job results.
- Add regression tests for missing metadata, same-name single/full-album conflict, and import job orchestration.

Out of scope:

- Redesigning playback counting rules, dynamic threshold, or L1/L2/L3 semantics.
- Changing Streamlit frozen pages except where a shared backend fix automatically benefits them.
- Adding a full manual metadata editor.
- Guaranteeing metadata for tracks Spotify no longer returns; those stay as explicit unresolved rows in the report.

---

### Schema And Import Facts

- Modify: `backend/core/db.py`
  - Add new columns/tables to base schema for fresh DBs.
- Modify: `backend/core/migrations.py`
  - Add migration 21 for existing DBs.
- Modify: `backend/core/import_data.py`
  - Persist play-time `spotify_track_id_at_play`.
  - Allow callers to defer preaggregation until post-import maintenance finishes.
- Modify: `backend/tests/unit/test_import_data_flow.py`
  - Lock import behavior for play-time Spotify identifiers and deferred aggregation.

### Metadata Refresh

- Modify: `backend/providers/spotify/client.py`
  - Add batch `get_tracks()`, `get_artists()`, and one-album helper methods using `SpotifyProvider.api_get()`.
- Create: `backend/domains/metadata/spotify_refresh.py`
  - Query missing track/album/artist metadata.
  - Upsert metadata without losing existing enrichment fields.
  - Populate play-time `spotify_album_id_at_play`.
  - Record local album to Spotify album evidence.
- Create: `backend/tests/unit/test_spotify_metadata_refresh.py`
  - Unit-test DB selection, upsert, partial provider errors, and link evidence.

### Album Project Reconciliation

- Modify: `backend/domains/playback/album_projects.py`
  - Use Spotify album links and local track counts before name-matched metadata.
  - Treat same-name `single` metadata as weak evidence when local album has LP/EP-sized membership.
  - Rebuild inferred projects after import while preserving manual projects.
- Create or modify: `backend/tests/contract/test_album_project_import_maintenance.py`
  - Contract-test Niall-style same-name single/full-album fixtures.

### Import Pipeline

- Create: `backend/services/import_maintenance_service.py`
  - Orchestrate metadata refresh, project rebuild, preaggregation rebuild, cache invalidation, and health summary.
- Modify: `backend/api/import_.py`
  - Report maintenance details in import job status.
- Create: `scripts/refresh_import_derived_data.py`
  - Repair the current DB without re-importing JSON.
  - Supports `--offline`, `--dry-run`, and `--json-output`.
- Modify: `backend/tests/contract/test_import_api_jobs.py`
  - Assert the import API calls maintenance and exposes partial results.

### Diagnostics And Docs

- Create: `backend/domains/metadata/import_health.py`
  - Build a deterministic report of missing metadata/project coverage.
- Modify: `data/README.md`
  - Document base import versus derived maintenance.
- Modify: `docs/playback-stats/rules.md`
  - Document album project maintenance after import.
- Modify: `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md`
  - Update the project prompt files after implementation.

---

### Decision 1: Preserve Play-Time Spotify IDs

`tracks` remains canonicalized by `(artist_id, track_name)` for current statistics, but `plays` must retain the Spotify track id from the raw JSON row. This avoids losing evidence when the same song appears first as a single and later inside an album with a different Spotify track id.

New columns:

```sql
ALTER TABLE plays ADD COLUMN spotify_track_id_at_play TEXT;
ALTER TABLE plays ADD COLUMN spotify_album_id_at_play TEXT;
CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play ON plays(spotify_track_id_at_play);
CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play ON plays(spotify_album_id_at_play);
```

`spotify_album_id_at_play` is populated after `/v1/tracks` metadata resolves the play-time track id.

### Decision 2: Add Album Link Evidence Instead Of Overloading `albums`

The local `albums` table is keyed by `(album_name, artist_id)`, so it cannot distinguish a same-name single and album by itself. Add a separate table:

```sql
CREATE TABLE IF NOT EXISTS album_spotify_links (
    album_id INTEGER NOT NULL REFERENCES albums(album_id),
    spotify_album_id TEXT NOT NULL REFERENCES spotify_album_meta(spotify_album_id),
    evidence TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    play_count INTEGER NOT NULL DEFAULT 0,
    track_count INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(album_id, spotify_album_id, evidence)
);
CREATE INDEX IF NOT EXISTS idx_album_spotify_links_album ON album_spotify_links(album_id);
CREATE INDEX IF NOT EXISTS idx_album_spotify_links_spotify_album ON album_spotify_links(spotify_album_id);
```

Evidence values are exact strings:

- `play_track_api`: derived from `plays.spotify_track_id_at_play -> Spotify /tracks -> album.id`.
- `track_meta`: derived from `tracks.spotify_track_id -> spotify_track_meta.spotify_album_id`.
- `name_search`: derived from Spotify album search and used only as fallback.

### Decision 3: Metadata Refresh Is Best Effort

If Spotify credentials are missing or the provider returns failures, the import job should complete with `maintenance_status='partial'`, not `error`, because raw play data is still valid. The job is an error only when the base JSON import fails or SQLite writes fail.

### Decision 4: Aggregations Run After Maintenance

`build_aggregations()` uses `spotify_track_meta.duration_ms` for dynamic threshold and feeds Billboard derived tables. Running it before metadata refresh leaves new tracks with missing durations and stale album project source rows. The import API should defer aggregation until maintenance finishes.

---

## Task 1: Add Schema For Play-Time Spotify IDs And Album Link Evidence

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/tests/unit/test_migrations.py`。

- Step 1.1: Write migration test
- Step 1.2: Run the focused test and verify it fails
- Step 1.3: Update fresh DB schema

```sql
spotify_track_id_at_play TEXT,
spotify_album_id_at_play TEXT,
```

```sql
CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play ON plays(spotify_track_id_at_play);
CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play ON plays(spotify_album_id_at_play);
```

Add the `album_spotify_links` table and indexes after `spotify_album_meta`.

- Step 1.4: Add migration 21
- Step 1.5: Verify

---

## Task 2: Persist Play-Time Spotify Track IDs During Import

涉及文件：`backend/core/import_data.py`、`backend/tests/unit/test_import_data_flow.py`。

- Step 2.1: Extend the import test

- Step 2.2: Run focused test and verify it fails
- Step 2.3: Implement extraction helper

Use this helper in `_cache_track()` instead of duplicating `replace()`.

- Step 2.4: Insert play-time IDs

Add that value to every `plays_batch` tuple. Update both `INSERT INTO plays` statements to include `spotify_track_id_at_play`.

The column list must become:

```sql
INSERT INTO plays(ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
   ts_date, platform, ms_played, conn_country, track_id,
   reason_start, reason_end, shuffle, skipped, offline, incognito_mode,
   content_type, source_album_id, spotify_track_id_at_play)
```

The placeholder list must contain 20 placeholders.

- Step 2.5: Add deferred aggregation parameter

Wrap the current `build_aggregations()` block:

- Step 2.6: Verify

---

## Task 3: Add Spotify Metadata Refresh Domain

涉及文件：`backend/providers/spotify/client.py`、`backend/domains/metadata/__init__.py`、`backend/domains/metadata/spotify_refresh.py`、`backend/tests/unit/test_spotify_metadata_refresh.py`。

- Step 3.1: Write unit tests for missing track selection and upsert
- Step 3.2: Add provider batch helpers
- Step 3.3: Implement metadata refresh helpers
- Step 3.4: Add online orchestration

In the same file, add:

- Step 3.5: Verify

---

## Task 4: Make Album Project Bootstrap Use Link Evidence Before Name Match

涉及文件：`backend/domains/playback/album_projects.py`、`backend/tests/contract/test_album_project_import_maintenance.py`。

- Step 4.1: Write same-name single/full-album contract test
- Step 4.2: Run the test and verify it fails
- Step 4.3: Add candidate query helper
- Step 4.4: Use linked metadata in standalone bootstrap

Use `release_date` in `_upsert_project()`.

This guard is intentionally conservative: it only overrides a same-name single when local membership proves the container is EP/LP-sized.

- Step 4.5: Verify

---

## Task 5: Add Import Maintenance Service

涉及文件：`backend/services/import_maintenance_service.py`、`backend/api/import_.py`、`backend/tests/contract/test_import_api_jobs.py`。

- Step 5.1: Write API orchestration test
- Step 5.2: Create the service
- Step 5.3: Wire Import API

Set result:

- Step 5.4: Verify

---

## Task 6: Add Import Health Report

涉及文件：`backend/domains/metadata/import_health.py`、`backend/tests/unit/test_import_health.py`。

- Step 6.1: Write report test
- Step 6.2: Implement report
- Step 6.3: Verify

---

## Task 7: Add Repair Script For Current Database

涉及文件：`scripts/refresh_import_derived_data.py`、`backend/tests/unit/test_refresh_import_derived_data_script.py`。

- Step 7.1: Write CLI smoke test
- Step 7.2: Implement CLI
- Step 7.3: Verify script

---

- 历史验收要求：test PASS; script emits JSON. On a machine without Spotify credentials, `maintenance_status` may be `partial` but the script should not crash.

## Task 8: Frontend Settings Import Result Surface

涉及文件：`frontend/src/features/settings/components/DataImportSection.tsx`、`frontend/src/types/generated`。

- Step 8.1: Display maintenance status from import result

When the import job result contains `maintenance_status`, render:

- `ok`: `派生数据已同步`
- `partial`: `播放数据已导入，部分 Spotify 元数据待补全`
- `error`: `派生数据维护失败`

Render counts for:

- `tracks_metadata_updated`
- `albums_metadata_updated`
- `unresolved_recent_tracks`
- `unresolved_recent_albums`
- Step 8.2: Avoid hard failure copy for partial metadata

Use copy that distinguishes raw import success from derived metadata gaps:

- Step 8.3: Verify frontend

---

## Task 9: Documentation Sync

涉及文件：`data/README.md`、`docs/playback-stats/rules.md`、`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`。

- Step 9.1: Update `data/README.md` import flow

Replace the current Streaming History import steps with:

```markdown
6. 刷新 Spotify 派生元数据：
   - 缺失的 `spotify_track_meta`
   - 缺失或不完整的 `spotify_album_meta`
   - `plays.spotify_album_id_at_play`
   - `album_spotify_links`
7. 重建 album project membership。
8. 构建预聚合表（`agg_weekly_*`，用于 Billboard 快速查询）。
9. 清理后端内存缓存并返回导入健康报告。
```

- Step 9.2: Update rules docs

```markdown
### Import-Time Derived Data Maintenance

Streaming import writes raw playback facts first. A post-import maintenance pass then refreshes missing Spotify metadata, records play-time Spotify album ids, rebuilds album projects, and rebuilds Billboard preaggregations. Album project bootstrap must prefer play-time Spotify album evidence over name-only album metadata, so a same-name single cannot prevent a later full album from entering album statistics.
```

- Step 9.3: Update prompt files

Add the same fact to `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md`: import completion now means raw play import plus derived maintenance, with partial status when external Spotify metadata is unavailable.

---

## Task 10: Current Database Repair And Verification

- No code changes if earlier tasks are complete.
- Output: `/tmp/spotify_import_maintenance.json`
- Step 10.1: Back up the DB
- Step 10.2: Re-import full Streaming History if migration cannot backfill play-time IDs

Because old `plays` rows do not contain exact play-time Spotify track ids, the strongest repair is to re-run import from the full JSON folder after Task 2 ships.

Run through the Settings UI or:

- Step 10.3: Run health probes

Expected after successful online maintenance:

- `missing_track_meta = 0`, except tracks Spotify no longer returns.
- `missing_cover = 0`, except albums Spotify returns without images.
- `missing_album_projects` should drop materially from the current `145` and should not include LP/EP-sized local albums like `Dinner Party`.
- Step 10.4: Run backend verification
- Step 10.5: Run product verification

---

## Rollout Strategy

1. Implement Tasks 1-6 in a feature branch.
2. Run unit and contract tests before touching the real DB.
3. Run Task 7 script against a copied DB in `/tmp`.
4. If the copied DB health report is good, run the repair against `data/spotify_stats.db`.
5. Only after the current data is repaired, update Settings UI and docs.
6. Do not commit unless the user explicitly asks; if committing, use the repo's Chinese conventional commit style and include validation commands in the body.

---

## Acceptance Criteria

This fix is complete when all are true:

- A streaming import writes `plays.spotify_track_id_at_play`.
- Import API runs post-import maintenance before marking the job `done`.
- Missing Spotify metadata for newly imported tracks/albums is fetched when credentials are configured.
- Missing credentials produce `maintenance_status='partial'`, not a failed raw import.
- Album project rebuild happens after metadata refresh.
- Same-name single/full-album conflicts no longer exclude LP/EP-sized local albums from album projects.
- `Dinner Party`-style fixtures pass.
- Recent missing metadata/project health counts are reported.
- Current DB repair can be run from one documented command.
- `pytest` focused unit/contract tests, `ruff check backend/`, API probes, and frontend build pass.

---

## Self-Review

- Spec coverage: covers raw import facts, Spotify metadata, album project semantics, import API lifecycle, current DB repair, docs, and frontend status copy.
- Placeholder scan: no `TBD` or open-ended "handle edge cases" items remain; unresolved Spotify provider failures are represented as explicit partial status.
- Type consistency: report keys use snake_case consistently across service, API result, script, and frontend display.
- Scope check: this is one subsystem: import-derived-data maintenance. It does not refactor unrelated playback counting or UI layout.
