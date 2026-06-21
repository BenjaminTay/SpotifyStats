# Playback Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

## File Map

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

**Files:**
- Modify: `backend/tests/fixtures/build_seed_db.py`
- Create: `backend/tests/contract/test_playback_rules_baseline.py`
- Create: `backend/tests/contract/test_billboard_counting_consistency.py`

- [x] **Step 0.1: Add named fixture scenarios to seed DB**

Add rows for these scenarios in `backend/tests/fixtures/build_seed_db.py`:

```python
PLAYBACK_RULE_SCENARIOS = {
    "short_fragments_same_track": "two adjacent 20s plays of a 40s track become one valid event",
    "long_track_dynamic_threshold": "30s of a 10min track is invalid after dynamic threshold",
    "multi_artist_fanout": "one play credits two artists in artist aggregation",
    "source_album_single_then_album": "same track name appears under single and LP source albums",
    "release_group_deluxe": "standard and deluxe albums collapse under L2 release merge",
    "track_group_recording": "remaster collapses under L2 track merge",
    "track_group_composition": "acoustic collapses only under L3 track merge",
    "billboard_fragment_boundary": "short fragments around a week boundary do not move weeks incorrectly",
}
```

Implement the fixture as explicit inserts, not generated random data. Use stable IDs starting above current seed IDs, for example `artist_id >= 900`, `album_id >= 900`, `track_id >= 900`, `play_id >= 9000`.

- [x] **Step 0.2: Add baseline tests for current behavior**

Create `backend/tests/contract/test_playback_rules_baseline.py`:

```python
from backend.core.db import load_plays, load_plays_for_artists


def test_current_merge_happens_before_filter(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    row = df[df["track_name"] == "Fixture Fragment Song"]
    assert len(row) == 1
    assert int(row.iloc[0]["ms_played"]) == 40000


def test_artist_fanout_preserves_total_play_events(seed_conn):
    base = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    artists = load_plays_for_artists(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    shared_base = base[base["track_name"] == "Fixture Shared Credit"]
    shared_artists = artists[artists["track_name"] == "Fixture Shared Credit"]
    assert len(shared_base) == 1
    assert len(shared_artists) == 2
```

- [x] **Step 0.3: Run baseline tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_playback_rules_baseline.py -v
```

Expected: tests pass against current code for current semantics.

- [x] **Step 0.4: Commit**

```bash
git add backend/tests/fixtures/build_seed_db.py backend/tests/contract/test_playback_rules_baseline.py
git commit -m "test: add playback statistics baseline fixtures"
```

---

## Task 1: P0 Counting Policy Boundary

**Purpose:** Extract the counting boundary without changing product semantics.

**Files:**
- Create: `backend/domains/playback/counting.py`
- Modify: `backend/core/db.py`
- Test: `backend/tests/unit/test_playback_counting.py`

- [x] **Step 1.1: Write unit tests for current threshold compatibility**

Create `backend/tests/unit/test_playback_counting.py`:

```python
import pandas as pd

from backend.domains.playback.counting import effective_threshold, filter_effective_plays


def test_effective_threshold_keeps_30s_for_typical_pop_song():
    assert effective_threshold(210_000, min_ms=30_000, ratio=0.1) == 30_000


def test_effective_threshold_raises_threshold_for_long_tracks():
    assert effective_threshold(600_000, min_ms=30_000, ratio=0.1) == 60_000


def test_effective_threshold_falls_back_when_duration_missing():
    assert effective_threshold(None, min_ms=30_000, ratio=0.1) == 30_000
    assert effective_threshold(0, min_ms=30_000, ratio=0.1) == 30_000


def test_filter_effective_plays_can_run_in_legacy_mode():
    df = pd.DataFrame(
        [
            {"track_id": 1, "ms_played": 29_999, "duration_ms": 210_000},
            {"track_id": 1, "ms_played": 30_000, "duration_ms": 210_000},
        ]
    )
    result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=False)
    assert result["ms_played"].tolist() == [30_000]
```

- [x] **Step 1.2: Run tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_playback_counting.py -v
```

Expected: fail because `backend.domains.playback.counting` does not exist.

- [x] **Step 1.3: Implement counting helpers**

Create `backend/domains/playback/counting.py`:

```python
from __future__ import annotations

import pandas as pd


def effective_threshold(
    duration_ms: int | float | None,
    min_ms: int = 30_000,
    ratio: float = 0.1,
) -> int:
    if duration_ms is None or pd.isna(duration_ms) or int(duration_ms) <= 0:
        return int(min_ms)
    return int(max(min_ms, int(duration_ms) * ratio))


def filter_effective_plays(
    df: pd.DataFrame,
    min_ms: int = 30_000,
    dynamic_threshold: bool = False,
    ratio: float = 0.1,
) -> pd.DataFrame:
    if df.empty or min_ms <= 0:
        return df
    if not dynamic_threshold:
        return df[df["ms_played"] >= min_ms].copy()
    thresholds = df["duration_ms"].apply(
        lambda duration: effective_threshold(duration, min_ms=min_ms, ratio=ratio)
    )
    return df[df["ms_played"] >= thresholds].copy()
```

- [x] **Step 1.4: Use helper in `backend/core/db.py` without enabling dynamic threshold**

In `_load_plays_cached()` and `_load_plays_for_artists_cached()`, replace:

```python
if min_ms > 0:
    df = df[df["ms_played"] >= min_ms]
```

with:

```python
from backend.domains.playback.counting import filter_effective_plays

df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=False)
```

Keep imports local inside the cached function or module-level if lint remains clean.

- [x] **Step 1.5: Run tests**

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_playback_counting.py backend/tests/contract/test_playback_rules_baseline.py -v
```

Expected: pass.

- [x] **Step 1.6: Commit**

```bash
git add backend/domains/playback/counting.py backend/core/db.py backend/tests/unit/test_playback_counting.py
git commit -m "refactor: extract playback counting policy helpers"
```

---

## Task 2: P0 Billboard Raw Fallback Consistency

**Purpose:** Make Billboard raw fallback use the same merge-then-filter order as pre-aggregation.

**Files:**
- Modify: `backend/domains/billboard/data_loader.py`
- Modify: `backend/core/db.py`
- Test: `backend/tests/contract/test_billboard_counting_consistency.py`

- [x] **Step 2.1: Write raw vs pre-aggregation parity test**

Create `backend/tests/contract/test_billboard_counting_consistency.py`:

```python
from backend.core.db import build_aggregations
from backend.domains.billboard.data_loader import load_billboard_raw, _try_load_from_agg


def test_billboard_raw_fallback_matches_preagg_for_fragmented_play(seed_conn, monkeypatch):
    build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)
    agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(30_000, True, 4, 0)
    raw = load_billboard_raw(30_000, True, 4, 0)

    raw_track = raw[raw["track_name"] == "Fixture Fragment Song"]
    agg_track = agg_tracks[agg_tracks["track_name"] == "Fixture Fragment Song"]

    assert int(raw_track.groupby("billboard_week").size().sum()) == int(
        agg_track["play_count"].sum()
    )
```

- [x] **Step 2.2: Run test and confirm current failure if raw fallback drops short fragments**

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_billboard_counting_consistency.py -v
```

Expected before implementation: failure or mismatch on fragment scenario.

- [x] **Step 2.3: Fix `load_billboard_raw()`**

In `backend/domains/billboard/data_loader.py`, change filter loading:

```python
_f, _fp = base_filters(min_ms=0, music_only=music_only)
```

After `merge_consecutive_plays(df, min_ms)`, apply:

```python
from backend.domains.playback.counting import filter_effective_plays

df = merge_consecutive_plays(df, min_ms)
df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=False)
```

- [x] **Step 2.4: Fix `load_billboard_raw_for_artists()` the same way**

Use `base_filters(min_ms=0, music_only=music_only)` before merge and `filter_effective_plays()` after merge, before joining `track_artists`.

- [x] **Step 2.5: Make `build_aggregations()` use the same helper**

In `backend/core/db.py`, replace:

```python
if min_ms > 0:
    df = df[df["ms_played"] >= min_ms]
```

with:

```python
from backend.domains.playback.counting import filter_effective_plays

df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=False)
```

- [x] **Step 2.6: Run narrow and Billboard tests**

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_billboard_counting_consistency.py backend/tests/integration/test_api.py -k "billboard" -v
```

Expected: pass.

- [x] **Step 2.7: Commit**

```bash
git add backend/domains/billboard/data_loader.py backend/core/db.py backend/tests/contract/test_billboard_counting_consistency.py
git commit -m "fix: align billboard raw fallback counting policy"
```

---

## Task 3: P1 Source Album Schema And Import

**Purpose:** Preserve playback-time album attribution instead of inferring every play from `tracks.album_id`.

**Files:**
- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Modify: `backend/core/import_data.py`
- Test: `backend/tests/unit/test_migrations.py`
- Test: `backend/tests/contract/test_source_album_attribution.py`

- [x] **Step 3.1: Add migration test**

Extend `backend/tests/unit/test_migrations.py`:

```python
def test_plays_has_source_album_id_after_migrations(migrated_conn):
    cols = {row[1] for row in migrated_conn.execute("PRAGMA table_info(plays)").fetchall()}
    assert "source_album_id" in cols
    indexes = {
        row[1]
        for row in migrated_conn.execute("PRAGMA index_list(plays)").fetchall()
    }
    assert "idx_plays_source_album" in indexes
```

- [x] **Step 3.2: Update schema**

In `backend/core/db.py` `SCHEMA`, add to `plays`:

```sql
source_album_id INTEGER REFERENCES albums(album_id),
```

Add index:

```sql
CREATE INDEX IF NOT EXISTS idx_plays_source_album ON plays(source_album_id);
```

- [x] **Step 3.3: Add migration**

In `backend/core/migrations.py`:

```python
@migration(13, "plays_source_album_id")
def migrate_013(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE plays ADD COLUMN source_album_id INTEGER REFERENCES albums(album_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plays_source_album ON plays(source_album_id)")
    conn.execute(
        "UPDATE plays SET source_album_id = ("
        "SELECT album_id FROM tracks WHERE tracks.track_id = plays.track_id"
        ") WHERE source_album_id IS NULL AND track_id IS NOT NULL"
    )
```

- [x] **Step 3.4: Update import path**

In `backend/core/import_data.py`, when inserting a play row, pass the album ID resolved from the raw `master_metadata_album_album_name` as `source_album_id`. Keep `tracks.album_id` unchanged for canonical/default track dimension.

Use this logic:

```python
source_album_id = _cache_album(conn, album_name, artist_id) if album_name else None
track_id = _cache_track(conn, track_name, artist_id, source_album_id, spotify_track_uri)
```

Then insert `source_album_id` into `plays`.

- [x] **Step 3.5: Add source album attribution contract test**

Create `backend/tests/contract/test_source_album_attribution.py`:

```python
from backend.core.db import load_plays


def test_load_plays_exposes_source_album_when_track_appears_on_multiple_albums(seed_conn):
    df = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    rows = df[df["track_name"] == "Fixture Source Album Song"]
    assert set(rows["album_name"]) == {"Fixture Single", "Fixture LP"}
```

This test expects `load_plays` with `join_albums=True` to expose the playback-time album as `source_album_name`. Keep `album_name` as a compatibility alias only if existing callers still need it.

- [x] **Step 3.6: Run tests**

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_migrations.py backend/tests/contract/test_source_album_attribution.py -v
```

Expected: pass.

- [x] **Step 3.7: Commit**

```bash
git add backend/core/db.py backend/core/migrations.py backend/core/import_data.py backend/tests/unit/test_migrations.py backend/tests/contract/test_source_album_attribution.py
git commit -m "feat: store playback source album attribution"
```

---

## Task 4: P1 Release Group Scope And Canonical Album Aggregation

**Purpose:** Apply release group canonicalization consistently to personal album charts and Billboard album charts.

**Files:**
- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Create: `backend/domains/playback/release_groups.py`
- Modify: `backend/domains/billboard/version_merge.py`
- Modify: `backend/services/analysis_stats_service.py`
- Test: `backend/tests/contract/test_album_release_groups.py`

- [x] **Step 4.1: Add migration test for release group scope**

```python
def test_release_groups_support_scope_and_parent(migrated_conn):
    cols = {row[1] for row in migrated_conn.execute("PRAGMA table_info(release_groups)").fetchall()}
    assert {"scope", "parent_group_id"} <= cols
```

- [x] **Step 4.2: Rebuild release group table in migration**

SQLite cannot drop the old `UNIQUE(canonical_name, artist_id)` constraint in place. Add a table rebuild migration:

```python
@migration(14, "release_groups_scope_parent")
def migrate_014(conn: sqlite3.Connection):
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS release_groups_new (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            artist_id INTEGER REFERENCES artists(artist_id),
            primary_album_id INTEGER REFERENCES albums(album_id),
            scope TEXT NOT NULL DEFAULT 'release' CHECK(scope IN ('release', 'composition')),
            parent_group_id INTEGER REFERENCES release_groups_new(group_id),
            is_manual BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(canonical_name, artist_id, scope)
        )"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO release_groups_new
           (group_id, canonical_name, artist_id, primary_album_id, scope, parent_group_id, is_manual, created_at)
           SELECT group_id, canonical_name, artist_id, primary_album_id, 'release', NULL, is_manual, created_at
           FROM release_groups"""
    )
    conn.execute("DROP TABLE release_groups")
    conn.execute("ALTER TABLE release_groups_new RENAME TO release_groups")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_artist ON release_groups(artist_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_scope ON release_groups(scope)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_parent ON release_groups(parent_group_id)")
    conn.execute("PRAGMA foreign_keys=ON")
```

- [x] **Step 4.3: Create release group resolver**

Create `backend/domains/playback/release_groups.py`:

```python
from __future__ import annotations

import sqlite3

import pandas as pd


def load_album_release_group_map(conn: sqlite3.Connection, merge_level: int = 2) -> pd.DataFrame:
    scope = "composition" if merge_level >= 3 else "release"
    return pd.read_sql_query(
        """SELECT rgm.album_id,
                  rg.group_id AS release_group_id,
                  rg.canonical_name,
                  rg.primary_album_id,
                  rg.scope
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           WHERE rg.scope = ?""",
        conn,
        params=(scope,),
    )
```

- [x] **Step 4.4: Apply resolver in personal album chart**

In `backend/services/analysis_stats_service.py`, change signatures so `merge_level` reaches album aggregation:

```python
def _chart_agg(conn: sqlite3.Connection, df: pd.DataFrame, entity: str, merge_level: int = 2) -> pd.DataFrame:
```

```python
def chart_rows(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    entity: str,
    metric: str,
    limit: int | None = None,
    offset: int = 0,
    merge_level: int = 2,
) -> tuple[int, list[dict]]:
```

Then call:

```python
agg = _chart_agg(conn, df, entity, merge_level=merge_level)
```

Before grouping album rows in `_chart_agg(entity="album")`, merge the release group map and compute:

```python
df["album_agg_id"] = df["release_group_id"].fillna(df["source_album_id"])
df["album_agg_name"] = df["canonical_name"].fillna(df["source_album_name"])
```

Then group by `album_agg_id`, `album_agg_name`, and `artist_name`.

- [x] **Step 4.5: Apply same resolver in Billboard album ranking**

In `backend/domains/billboard/chart_ranking.py`, change:

```python
def compute_album_weekly_rankings(_df, top_n, pre_agg=None):
```

to:

```python
def compute_album_weekly_rankings(_df, top_n, pre_agg=None, merge_level: int = 2):
```

In `backend/domains/billboard/version_merge.py`, update `_apply_album_release_groups()` to accept `merge_level: int = 2`, filter by `scope='release'` for L2 and `scope='composition'` for L3, and leave L1 unchanged.

```python
def _apply_album_release_groups(df, merge_level: int = 2):
    if merge_level <= 1 or df.empty:
        return df
    scope = "composition" if merge_level >= 3 else "release"
    # Load members only for the selected scope, map member album rows to canonical_name,
    # then re-aggregate play_count/total_ms/tracks_count by billboard_week/canonical album.
```

- [x] **Step 4.6: Add contract test**

```python
from backend.core.db import load_plays
from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
from backend.domains.billboard.data_loader import load_billboard_raw
from backend.domains.playback.release_groups import load_album_release_group_map
from backend.services.analysis_stats_service import chart_rows


def test_release_group_scope_maps_standard_and_deluxe(seed_conn):
    mapping = load_album_release_group_map(seed_conn, merge_level=2)
    rows = mapping[mapping["canonical_name"] == "Fixture Release Album"]
    assert set(rows["album_id"]) == {901, 902}
    assert set(rows["scope"]) == {"release"}


def test_personal_album_chart_and_billboard_use_same_release_group(seed_conn):
    df = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    _total, personal_rows = chart_rows(
        seed_conn,
        df,
        entity="album",
        metric="plays",
        limit=100,
        offset=0,
        merge_level=2,
    )
    billboard_raw = load_billboard_raw(30_000, True, 4, 0)
    billboard_rows = compute_album_weekly_rankings(billboard_raw, top_n=100, merge_level=2)

    assert any(row["album_name"] == "Fixture Release Album" for row in personal_rows)
    assert "Fixture Release Album" in set(billboard_rows["album_name"])
```

- [x] **Step 4.7: Run tests**

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_album_release_groups.py backend/tests/integration/test_analysis_api.py -v
```

Expected: pass.

- [x] **Step 4.8: Commit**

```bash
git add backend/core/db.py backend/core/migrations.py backend/domains/playback/release_groups.py backend/domains/billboard/version_merge.py backend/services/analysis_stats_service.py backend/tests/contract/test_album_release_groups.py
git commit -m "feat: canonicalize album charts with release groups"
```

---

## Task 5: P2 Dynamic Threshold And Session Boundaries

**Purpose:** Enable fairer valid-play filtering for long tracks and prevent unrealistic long-gap merges.

**Files:**
- Modify: `backend/domains/playback/counting.py`
- Modify: `backend/core/db.py`
- Modify: `backend/dependencies.py`
- Test: `backend/tests/unit/test_playback_counting.py`
- Test: `backend/tests/contract/test_playback_rules_baseline.py`

- [x] **Step 5.1: Add tests for dynamic threshold**

```python
def test_filter_effective_plays_dynamic_threshold_filters_long_track_snippet():
    df = pd.DataFrame([{"track_id": 1, "ms_played": 30_000, "duration_ms": 600_000}])
    result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=True)
    assert result.empty


def test_filter_effective_plays_dynamic_threshold_keeps_typical_30s_play():
    df = pd.DataFrame([{"track_id": 1, "ms_played": 30_000, "duration_ms": 210_000}])
    result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=True)
    assert len(result) == 1
```

- [x] **Step 5.2: Add session boundary tests**

```python
from backend.core.db import merge_consecutive_plays


def test_merge_consecutive_plays_does_not_merge_across_large_gap():
    df = pd.DataFrame(
        [
            {"ts": "2026-01-01T10:00:00", "track_id": 1, "ms_played": 20_000, "duration_ms": 40_000},
            {"ts": "2026-01-01T11:00:00", "track_id": 1, "ms_played": 20_000, "duration_ms": 40_000},
        ]
    )
    result = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=30)
    assert result.empty
```

- [x] **Step 5.3: Extend `merge_consecutive_plays()` signature**

In `backend/core/db.py`:

```python
def merge_consecutive_plays(
    df: pd.DataFrame,
    min_ms: int,
    max_gap_minutes: int | None = None,
    boundary_column: str | None = None,
) -> pd.DataFrame:
```

Group breaks when:

```python
track_changed = df["track_id"] != df["track_id"].shift(1)
gap_changed = False
if max_gap_minutes is not None and "ts" in df.columns:
    ts = pd.to_datetime(df["ts"])
    gap_changed = ts.diff().dt.total_seconds().gt(max_gap_minutes * 60).fillna(False)
boundary_changed = False
if boundary_column and boundary_column in df.columns:
    boundary_changed = df[boundary_column] != df[boundary_column].shift(1)
df["_merge_group"] = (track_changed | gap_changed | boundary_changed).cumsum()
```

- [x] **Step 5.4: Add query parameters with conservative defaults**

In `backend/dependencies.py`, add:

```python
dynamic_threshold: bool = Query(default=False, description="使用动态有效播放阈值")
max_merge_gap_minutes: int | None = Query(default=None, ge=1, le=240, description="连续播放最大合并间隔")
```

Store them on `PlayFilters` and `BillboardFilters`.

- [x] **Step 5.5: Wire dynamic threshold in loaders**

Pass `dynamic_threshold` and `max_merge_gap_minutes` to affected service calls in a follow-up mechanical change. Keep default `False` until UI/doc release is ready.

- [x] **Step 5.6: Run tests**

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_playback_counting.py backend/tests/contract/test_playback_rules_baseline.py -v
```

Expected: pass.

- [x] **Step 5.7: Commit**

```bash
git add backend/domains/playback/counting.py backend/core/db.py backend/dependencies.py backend/tests/unit/test_playback_counting.py backend/tests/contract/test_playback_rules_baseline.py
git commit -m "feat: support dynamic playback thresholds"
```

---

## Task 6: P3 Album Type Taxonomy

**Purpose:** Classify LP/EP/compilation/single consistently across personal and Billboard album charts.

**Files:**
- Create: `backend/domains/playback/album_type.py`
- Modify: `backend/services/analysis_stats_service.py`
- Modify: `backend/domains/billboard/data_loader.py`
- Test: `backend/tests/unit/test_album_type_taxonomy.py`

- [x] **Step 6.1: Add taxonomy tests**

```python
from backend.domains.playback.album_type import classify_album


def test_classify_album_single():
    assert classify_album("single", total_tracks=1, total_ms=180_000) == "single"


def test_classify_album_ep_from_single_type_with_many_tracks():
    assert classify_album("single", total_tracks=5, total_ms=900_000) == "ep"


def test_classify_album_lp_from_album_type():
    assert classify_album("album", total_tracks=12, total_ms=2_400_000) == "lp"


def test_classify_album_compilation():
    assert classify_album("compilation", total_tracks=18, total_ms=3_600_000) == "compilation"
```

- [x] **Step 6.2: Implement taxonomy helper**

```python
from __future__ import annotations


def classify_album(
    spotify_album_type: str | None,
    total_tracks: int | None,
    total_ms: int | None,
) -> str:
    album_type = (spotify_album_type or "").lower()
    tracks = int(total_tracks or 0)
    duration = int(total_ms or 0)
    if album_type == "compilation":
        return "compilation"
    if tracks <= 2:
        return "single"
    if tracks <= 6 and duration < 25 * 60 * 1000:
        return "ep"
    return "lp"
```

- [x] **Step 6.3: Add category to album aggregations**

Personal album chart rows should include:

```python
album_category: "lp" | "ep" | "compilation" | "single"
```

Default filtering:

```python
album_category != "single"
```

- [x] **Step 6.4: Add tests and run**

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_album_type_taxonomy.py backend/tests/integration/test_analysis_api.py -v
```

Expected: pass.

- [x] **Step 6.5: Commit**

```bash
git add backend/domains/playback/album_type.py backend/services/analysis_stats_service.py backend/domains/billboard/data_loader.py backend/tests/unit/test_album_type_taxonomy.py
git commit -m "feat: classify album chart release types"
```

---

## Task 7: P4 Track Groups Schema And Aggregation Keys

**Purpose:** Add L1/L2/L3 track version aggregation without changing valid play events.

**Files:**
- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Create: `backend/domains/playback/merge_levels.py`
- Create: `backend/domains/playback/track_groups.py`
- Modify: `backend/services/analysis_stats_service.py`
- Modify: `backend/domains/billboard/chart_ranking.py`
- Test: `backend/tests/unit/test_track_groups.py`
- Test: `backend/tests/contract/test_merge_level_aggregation.py`

- [x] **Step 7.1: Add migration for track group tables**

Add to `backend/core/db.py` `SCHEMA` and `backend/core/migrations.py`:

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

- [x] **Step 7.2: Implement merge level normalization**

`backend/domains/playback/merge_levels.py`:

```python
from __future__ import annotations


def normalize_merge_level(value: int | str | None) -> int:
    try:
        level = int(value) if value is not None else 2
    except (TypeError, ValueError):
        return 2
    return level if level in {1, 2, 3} else 2
```

- [x] **Step 7.3: Implement track aggregation key resolver**

`backend/domains/playback/track_groups.py`:

```python
from __future__ import annotations

import sqlite3

import pandas as pd


def load_track_group_keys(conn: sqlite3.Connection, merge_level: int) -> pd.DataFrame:
    if merge_level <= 1:
        return pd.DataFrame(columns=["track_id", "track_agg_id", "track_agg_name", "track_group_scope"])
    scope = "composition" if merge_level >= 3 else "recording"
    return pd.read_sql_query(
        """SELECT tgm.track_id,
                  tg.group_id AS track_agg_id,
                  tg.canonical_name AS track_agg_name,
                  tg.scope AS track_group_scope
           FROM track_group_members tgm
           JOIN track_groups tg ON tgm.group_id = tg.group_id
           WHERE tg.scope = ?""",
        conn,
        params=(scope,),
    )
```

- [x] **Step 7.4: Apply resolver only in aggregation layer**

In `backend/services/analysis_stats_service.py`, update `_chart_agg(entity="track")` to use `load_track_group_keys()` and derive:

```python
track_agg_id = group_id if present else track_id
track_agg_name = canonical_name if present else track_name
```

Group by `track_agg_id`, `track_agg_name`, `artist_name`, and `album_name`. Do not pass `merge_level` into `load_plays()` or `_load_plays_cached()`.

In `backend/domains/billboard/chart_ranking.py`, change:

```python
def compute_weekly_rankings(_df, top_n, pre_agg=None):
```

to:

```python
def compute_weekly_rankings(_df, top_n, pre_agg=None, merge_level: int = 2):
```

When `pre_agg is None`, apply track group keys before the weekly groupby. When `pre_agg` is present, build separate pre-aggregation rows per `merge_level` as described in Task 8 instead of re-grouping already-ranked rows.

- [x] **Step 7.5: Add tests**

`backend/tests/contract/test_merge_level_aggregation.py` should assert:

```python
def test_merge_level_does_not_change_valid_play_events(seed_conn):
    df = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    total_events = len(df)
    for level in (1, 2, 3):
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=level,
        )
        assert sum(row["plays"] for row in rows) == total_events


def test_l2_merges_remaster_but_not_acoustic(seed_conn):
    df = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    _total, rows = chart_rows(
        seed_conn,
        df,
        entity="track",
        metric="plays",
        limit=500,
        offset=0,
        merge_level=2,
    )
    names = {row["track_name"]: row["plays"] for row in rows}
    assert names["Fixture Recording Song"] == 2
    assert names["Fixture Recording Song - Acoustic"] == 1


def test_l3_merges_acoustic_but_not_demo(seed_conn):
    df = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    _total, rows = chart_rows(
        seed_conn,
        df,
        entity="track",
        metric="plays",
        limit=500,
        offset=0,
        merge_level=3,
    )
    names = {row["track_name"]: row["plays"] for row in rows}
    assert names["Fixture Composition Song"] == 3
    assert names["Fixture Composition Song - Demo"] == 1
```

- [x] **Step 7.6: Run tests**

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_track_groups.py backend/tests/contract/test_merge_level_aggregation.py -v
```

Expected: pass.

- [x] **Step 7.7: Commit**

```bash
git add backend/core/db.py backend/core/migrations.py backend/domains/playback/merge_levels.py backend/domains/playback/track_groups.py backend/services/analysis_stats_service.py backend/domains/billboard/chart_ranking.py backend/tests/unit/test_track_groups.py backend/tests/contract/test_merge_level_aggregation.py
git commit -m "feat: add track version aggregation levels"
```

---

## Task 8: Merge Level API And Frontend State

**Purpose:** Let users switch strictness without corrupting cache boundaries.

**Files:**
- Modify: `backend/dependencies.py`
- Modify: `backend/api/analysis.py`
- Modify: `backend/api/billboard/data.py`
- Modify: `frontend/src/api/query-keys.ts`
- Modify: `frontend/src/hooks/useBillboard.ts`
- Modify: `frontend/src/pages/BillboardPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Test: `frontend/src/tests/query-hooks.test.tsx`
- Test: `frontend/src/tests/phase5-architecture.test.ts`

- [x] **Step 8.1: Add backend dependency**

In `backend/dependencies.py`:

```python
class MergeConfig:
    def __init__(
        self,
        merge_level: int = Query(default=2, ge=1, le=3, description="版本合并严格度"),
    ):
        self.merge_level = merge_level
```

Use it only in endpoints that return affected track/album/Billboard aggregations.

- [x] **Step 8.2: Add frontend query key parameter**

In `frontend/src/api/query-keys.ts`, keep the existing object parameter pattern:

```ts
weekly: (params: Record<string, unknown> = {}) => ['billboard', 'weekly', params] as const,
```

Ensure callers include:

```ts
{ merge_level: mergeLevel }
```

- [x] **Step 8.3: Add URL state to Billboard page**

In `frontend/src/pages/BillboardPage.tsx`, read:

```ts
const mergeLevel = Number(searchParams.get('merge_level') ?? '2')
```

Write on change:

```ts
setSearchParams((next) => {
  next.set('merge_level', String(value))
  return next
})
```

- [x] **Step 8.4: Add tests**

In `frontend/src/tests/query-hooks.test.tsx`, assert the query key differs for L1/L2:

```ts
expect(queryKeys.billboard.weekly({ merge_level: 1 })).not.toEqual(
  queryKeys.billboard.weekly({ merge_level: 2 }),
)
```

- [x] **Step 8.5: Run frontend tests**

```bash
cd frontend && npm test -- query-hooks.test.tsx phase5-architecture.test.ts
```

Expected: pass.

- [x] **Step 8.6: Commit**

```bash
git add backend/dependencies.py backend/api/analysis.py backend/api/billboard/data.py frontend/src/api/query-keys.ts frontend/src/hooks/useBillboard.ts frontend/src/pages/BillboardPage.tsx frontend/src/pages/SettingsPage.tsx frontend/src/tests/query-hooks.test.tsx frontend/src/tests/phase5-architecture.test.ts
git commit -m "feat: expose playback merge strictness"
```

---

## Task 9: Version Detail Displays

**Purpose:** Make merged entities explainable in track and album detail pages.

**Files:**
- Modify: `backend/domains/billboard/details.py`
- Modify: `backend/api/billboard/details.py`
- Modify: `frontend/src/types/billboard.ts`
- Modify: `frontend/src/features/music/details/TrackDetailExperience.tsx`
- Modify: `frontend/src/features/music/details/AlbumDetailExperience.tsx`
- Create: `frontend/src/features/music/details/VersionGroupSection.tsx`
- Test: `frontend/src/tests/phase5-architecture.test.ts`

- [x] **Step 9.1: Add backend response fields**

Track detail responses should include:

```python
"version_group": {
    "scope": "recording",
    "canonical_name": "Fixture Song",
    "versions": [
        {"track_id": 1, "track_name": "Fixture Song", "plays": 10, "total_ms": 1800000, "album_name": "Fixture LP", "is_primary": True}
    ],
}
```

Album detail responses should include:

```python
"release_group": {
    "scope": "release",
    "canonical_name": "Fixture Album",
    "versions": [
        {"album_id": 1, "album_name": "Fixture Album", "plays": 30, "unique_tracks": 12, "is_primary": True}
    ],
}
```

- [x] **Step 9.2: Add shared frontend section**

Create `frontend/src/features/music/details/VersionGroupSection.tsx` as a presentational component. It receives normalized rows and renders a compact table/list. It must not fetch data.

- [x] **Step 9.3: Wire into detail experiences**

In track and album detail experiences, render the section only when group data exists and has at least two versions.

- [x] **Step 9.4: Run build/tests**

```bash
cd frontend && npm run build
cd frontend && npm test -- phase5-architecture.test.ts
```

Expected: pass.

- [x] **Step 9.5: Commit**

```bash
git add backend/domains/billboard/details.py backend/api/billboard/details.py frontend/src/types/billboard.ts frontend/src/features/music/details/TrackDetailExperience.tsx frontend/src/features/music/details/AlbumDetailExperience.tsx frontend/src/features/music/details/VersionGroupSection.tsx frontend/src/tests/phase5-architecture.test.ts
git commit -m "feat: show merged entity version details"
```

---

## Task 10: Consistency Test Matrix And Documentation

**Purpose:** Lock the semantics so future changes cannot silently drift.

**Files:**
- Create: `backend/tests/contract/test_playback_invariants.py`
- Modify: `docs/playback-stats/2026-06-12-playback-stats-rules.md`
- Modify: `docs/productization/2026-06-08-phase5-baseline.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [x] **Step 10.1: Add invariant tests**

Create `backend/tests/contract/test_playback_invariants.py`:

```python
from backend.core.db import load_plays, load_plays_for_artists


def test_artist_fanout_sum_is_at_least_valid_events(seed_conn):
    valid = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    artists = load_plays_for_artists(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    assert len(artists) >= len(valid)


def test_track_aggregation_preserves_valid_event_count(seed_conn):
    valid = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    grouped = valid.groupby("track_id").size().sum()
    assert int(grouped) == len(valid)
```

In the same file, add these invariants after implementing Tasks 3 and 4:

```python
def test_source_album_sum_is_close_to_valid_events(seed_conn):
    valid = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    source_album_events = valid[valid["source_album_id"].notna()]
    assert len(source_album_events) <= len(valid)
    assert len(valid) - len(source_album_events) == 0


def test_unmerged_tracks_still_count_under_track_group_aggregation(seed_conn):
    valid = load_plays(seed_conn, min_ms=30_000, music_only=True, merge_enabled=True)
    _total, rows = chart_rows(
        seed_conn,
        valid,
        entity="track",
        metric="plays",
        limit=500,
        offset=0,
        merge_level=3,
    )
    assert sum(row["plays"] for row in rows) == len(valid)
```

- [x] **Step 10.2: Run minimum backend matrix**

```bash
source .venv/bin/activate && pytest -m unit -v
source .venv/bin/activate && pytest -m contract -v
```

Expected: pass.

- [x] **Step 10.3: Run frontend matrix**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: pass.

- [x] **Step 10.4: Update docs**

Add an implementation-status table to `docs/playback-stats/2026-06-12-playback-stats-rules.md`:

```markdown
## Implementation Status

| Phase | Status | Verification |
|---|---|---|
| P0 counting policy consistency | Done | `pytest backend/tests/contract/test_billboard_counting_consistency.py -v` |
| P1 source album + release groups | Done | `pytest backend/tests/contract/test_source_album_attribution.py backend/tests/contract/test_album_release_groups.py -v` |
| P2 dynamic threshold | Done | `pytest backend/tests/unit/test_playback_counting.py -v` |
```

Only mark phases as `Done` after tests pass.

- [x] **Step 10.5: Keep AGENTS and CLAUDE synchronized**

After editing `AGENTS.md`, copy the same playback-statistics guidance into `CLAUDE.md` and run:

```bash
cmp -s AGENTS.md CLAUDE.md
```

Expected: exit code 0.

- [x] **Step 10.6: Commit**

```bash
git add backend/tests/contract/test_playback_invariants.py docs/playback-stats/2026-06-12-playback-stats-rules.md docs/productization/2026-06-08-phase5-baseline.md README.md AGENTS.md CLAUDE.md
git commit -m "docs: record playback statistics implementation status"
```

---

## Recommended Phase Boundaries

### Phase A: Safe Semantics Baseline ✅

Tasks: 0, 1, 2 — **已完成 2026-06-12**

Expected behavior change: Billboard raw fallback no longer drops short fragments before merge. Other stats should remain effectively unchanged.

Verification:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_playback_counting.py backend/tests/contract/test_playback_rules_baseline.py backend/tests/contract/test_billboard_counting_consistency.py -v
```

### Phase B: Album Attribution And Release Canonicalization ✅

Tasks: 3, 4, 6 — **已完成 2026-06-12**

Expected behavior change: album charts become source-album based, canonical album merging becomes consistent, singles are excluded from album charts by default.

Verification:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_migrations.py backend/tests/contract/test_source_album_attribution.py backend/tests/contract/test_album_release_groups.py backend/tests/unit/test_album_type_taxonomy.py -v
```

### Phase C: Dynamic Counting Policy ✅

Tasks: 5 — **已完成 2026-06-12**

Expected behavior change: long-track snippets below 10% duration no longer count when dynamic threshold is enabled. Keep default disabled until UI and release note are ready; enable default in a separate commit after reviewing visible metric deltas.

Verification:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_playback_counting.py backend/tests/contract/test_playback_rules_baseline.py -v
```

### Phase D: Track Version Merge ✅

Tasks: 7, 8, 9 — **已完成 2026-06-12**

Expected behavior change: track and album rankings can switch L1/L2/L3 merge levels; valid play events remain unchanged.

Verification:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_track_groups.py backend/tests/contract/test_merge_level_aggregation.py -v
cd frontend && npm test -- query-hooks.test.tsx phase5-architecture.test.ts
cd frontend && npm run build
```

### Phase E: Final Guardrails ✅

Tasks: 10 — **已完成 2026-06-12**

Expected behavior change: none; this phase locks documentation and regression checks.

Verification:

```bash
sh scripts/phase5_check.sh
```

---

## Open Implementation Decisions

1. Dynamic threshold default should remain `False` until the app can show before/after metric deltas.
2. `source_album_id` historical backfill should be explicitly labeled as inferred data.
3. Catalog membership view should remain separate from default album chart and should not ship before source album chart is stable.
4. Track group auto-detection should not auto-merge low-confidence Acoustic/Live/Remix candidates; it should create review candidates first.
5. If path B is ever adopted, it requires a new plan because it changes valid play events, cache keys, pre-aggregation hash, and user-facing totals.

---

## Completion Checklist

- [x] P0 raw and pre-aggregated Billboard outputs match on seed fixtures.
- [x] Source album is persisted on new imports and backfilled for historical data.
- [x] Personal album chart, album detail, and Billboard album chart use the same release group resolver.
- [x] Album type taxonomy is shared between personal and Billboard album charts.
- [x] `merge_level` affects only version-sensitive entity aggregations.
- [x] Track group L2/L3 aggregation does not alter valid play events.
- [x] Version detail sections explain what was merged.
- [x] Contract tests cover the invariants from R24b.
- [x] README, AGENTS, CLAUDE, and phase baseline docs are synchronized.
