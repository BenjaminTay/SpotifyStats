# Album Project Playback Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps below are now marked complete with checkbox (`- [x]`) syntax for tracking.

**Goal:** Bring album/song version merging, album project play counts, Billboard album ranking, source breakdown, compilation handling, and frontend explanation into alignment with `docs/2026-06-18-playback-stats-rules-latest.md`.

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

## File Map

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

- Modify: `docs/2026-06-18-playback-stats-rules-latest.md`
  - Append implementation status after completion.
- Modify: `docs/2026-06-08-phase5-productization-baseline.md`
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

**Files:**
- Modify: `backend/tests/fixtures/build_seed_db.py`
- Create: `backend/tests/contract/test_album_project_rules.py`

- [x] **Step 0.1: Add fixture albums and metadata**

In `backend/tests/fixtures/build_seed_db.py`, add these records after the existing fixture album metadata:

```python
fixture_project_albums = [
    (920, "Fixture Future Single", 901),
    (921, "Fixture Future LP", 901),
    (922, "Fixture Future LP Deluxe", 901),
    (923, "Fixture Pure Compilation", 901),
    (924, "Fixture Compilation Plus", 901),
    (925, "Fixture Future LP (Rerecorded)", 901),
    (926, "Fixture Collab Remix", 901),
]
conn.executemany(
    "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
    fixture_project_albums,
)
```

Add matching `spotify_album_meta` rows:

```python
fixture_project_album_meta = [
    ("spotify:album:proj920", "Fixture Future Single", "single", "2026-01-05", 50, "Fixture Records", "pop", "", "Fixture Artist Alpha", 1, '["spotify:track:proj920"]'),
    ("spotify:album:proj921", "Fixture Future LP", "album", "2026-02-01", 70, "Fixture Records", "pop", "", "Fixture Artist Alpha", 10, '["spotify:track:proj920","spotify:track:proj921"]'),
    ("spotify:album:proj922", "Fixture Future LP Deluxe", "album", "2026-02-15", 65, "Fixture Records", "pop", "", "Fixture Artist Alpha", 12, '["spotify:track:proj920","spotify:track:proj921","spotify:track:proj922"]'),
    ("spotify:album:proj923", "Fixture Pure Compilation", "compilation", "2026-03-01", 40, "Fixture Records", "pop", "", "Fixture Artist Alpha", 12, '["spotify:track:proj920"]'),
    ("spotify:album:proj924", "Fixture Compilation Plus", "compilation", "2026-03-05", 42, "Fixture Records", "pop", "", "Fixture Artist Alpha", 14, '["spotify:track:proj920","spotify:track:proj923"]'),
    ("spotify:album:proj925", "Fixture Future LP (Rerecorded)", "album", "2026-04-01", 60, "Fixture Records", "pop", "", "Fixture Artist Alpha", 10, '["spotify:track:proj925","spotify:track:proj927"]'),
    ("spotify:album:proj926", "Fixture Collab Remix", "single", "2026-04-15", 45, "Fixture Records", "pop", "", "Fixture Artist Alpha, Fixture Artist Beta", 1, '["spotify:track:proj926"]'),
]
conn.executemany(
    """INSERT INTO spotify_album_meta(spotify_album_id, album_name, album_type,
       release_date, popularity, label, genres, image_url, album_artists,
       total_tracks, track_list) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    fixture_project_album_meta,
)
```

- [x] **Step 0.2: Add fixture tracks and relationships**

Add tracks:

```python
fixture_project_tracks = [
    (920, "Fixture Lead Single", 901, 920, "spotify:track:proj920"),
    (921, "Fixture Album Cut", 901, 921, "spotify:track:proj921"),
    (922, "Fixture Deluxe Bonus", 901, 922, "spotify:track:proj922"),
    (923, "Fixture Compilation Exclusive", 901, 924, "spotify:track:proj923"),
    (925, "Fixture Lead Single (Rerecorded)", 901, 925, "spotify:track:proj925"),
    (926, "Fixture Lead Single Remix", 901, 926, "spotify:track:proj926"),
    (927, "Fixture Rerecord Vault", 901, 925, "spotify:track:proj927"),
]
conn.executemany(
    "INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_uri) VALUES (?, ?, ?, ?, ?)",
    fixture_project_tracks,
)
```

Add `track_albums` rows:

```python
fixture_project_track_albums = [
    (920, 920), (920, 921), (920, 922), (920, 923), (920, 924),
    (921, 921), (921, 922),
    (922, 922),
    (923, 924),
    (925, 925),
    (926, 926),
    (927, 925),
]
conn.executemany(
    "INSERT OR IGNORE INTO track_albums(track_id, album_id) VALUES (?, ?)",
    fixture_project_track_albums,
)
```

Add track metadata:

```python
fixture_project_track_meta = [
    ("proj920", "Fixture Lead Single", 200000, 65, 0, 1, 1, "ISRC-PROJ-920", "spotify:album:proj920"),
    ("proj921", "Fixture Album Cut", 210000, 60, 0, 2, 1, "ISRC-PROJ-921", "spotify:album:proj921"),
    ("proj922", "Fixture Deluxe Bonus", 190000, 55, 0, 11, 1, "ISRC-PROJ-922", "spotify:album:proj922"),
    ("proj923", "Fixture Compilation Exclusive", 180000, 50, 0, 1, 1, "ISRC-PROJ-923", "spotify:album:proj924"),
    ("proj925", "Fixture Lead Single (Rerecorded)", 205000, 52, 0, 1, 1, "ISRC-PROJ-925", "spotify:album:proj925"),
    ("proj926", "Fixture Lead Single Remix", 215000, 50, 0, 1, 1, "ISRC-PROJ-926", "spotify:album:proj926"),
    ("proj927", "Fixture Rerecord Vault", 195000, 50, 0, 9, 1, "ISRC-PROJ-927", "spotify:album:proj925"),
]
conn.executemany(
    """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms,
       popularity, explicit, track_number, disc_number, isrc, spotify_album_id)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    fixture_project_track_meta,
)
```

- [x] **Step 0.3: Add fixture release and track groups**

Add release groups:

```python
fixture_release_groups = [
    (920, "Fixture Future LP", 901, 921, "release", None, 1),
    (921, "Fixture Future LP", 901, 921, "composition", None, 1),
]
conn.executemany(
    """INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, scope, parent_group_id, is_manual)
       VALUES (?, ?, ?, ?, ?, ?, ?)""",
    fixture_release_groups,
)
conn.executemany(
    "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
    [(920, 921), (920, 922), (921, 921), (921, 922), (921, 925)],
)
```

Add track groups:

```python
fixture_track_groups = [
    (920, "Fixture Lead Single", 920, "recording", None, 1),
    (921, "Fixture Lead Single", 920, "composition", None, 1),
]
conn.executemany(
    """INSERT INTO track_groups(group_id, canonical_name, primary_track_id, scope, parent_group_id, is_manual)
       VALUES (?, ?, ?, ?, ?, ?)""",
    fixture_track_groups,
)
conn.executemany(
    "INSERT INTO track_group_members(group_id, track_id) VALUES (?, ?)",
    [(920, 920), (921, 920), (921, 925), (921, 926)],
)
```

Add featured artist relationship for collaboration:

```python
conn.execute("INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (920, 901, 'primary')")
conn.execute("INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (926, 901, 'primary')")
conn.execute("INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (926, 902, 'featured')")
```

- [x] **Step 0.4: Add fixture plays with exact expected totals**

Add these plays near the end of the existing fixture play list:

```python
# Album project fixtures.
# Expected L2 all-time "Fixture Future LP" total:
# lead single 4 plays: 2 single source before LP + 1 LP source after release + 1 compilation source
# album cut 3 plays: 3 LP source
# deluxe bonus 2 plays: 2 deluxe source
# total = 9
plays.extend(
    [
        make_play("2026-01-10T02:00:00Z", "ios", 200000, 920, source_album_id=920),
        make_play("2026-01-12T02:00:00Z", "ios", 200000, 920, source_album_id=920),
        make_play("2026-02-02T02:00:00Z", "ios", 200000, 920, source_album_id=921),
        make_play("2026-02-03T02:00:00Z", "ios", 210000, 921, source_album_id=921),
        make_play("2026-02-04T02:00:00Z", "ios", 210000, 921, source_album_id=921),
        make_play("2026-02-05T02:00:00Z", "ios", 210000, 921, source_album_id=921),
        make_play("2026-02-16T02:00:00Z", "ios", 190000, 922, source_album_id=922),
        make_play("2026-02-17T02:00:00Z", "ios", 190000, 922, source_album_id=922),
        make_play("2026-03-02T02:00:00Z", "ios", 200000, 920, source_album_id=923),
        make_play("2026-03-06T02:00:00Z", "ios", 180000, 923, source_album_id=924),
        make_play("2026-03-07T02:00:00Z", "ios", 180000, 923, source_album_id=924),
        make_play("2026-03-08T02:00:00Z", "ios", 180000, 923, source_album_id=924),
        make_play("2026-03-09T02:00:00Z", "ios", 180000, 923, source_album_id=924),
        make_play("2026-04-02T02:00:00Z", "ios", 205000, 925, source_album_id=925),
        make_play("2026-04-03T02:00:00Z", "ios", 195000, 927, source_album_id=925),
        make_play("2026-04-16T02:00:00Z", "ios", 215000, 926, source_album_id=926),
    ]
)
```

- [x] **Step 0.5: Write failing contract tests**

Create `backend/tests/contract/test_album_project_rules.py`:

```python
from __future__ import annotations

import pytest

from backend.core.db import load_plays
from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
    compute_album_source_breakdown,
    load_album_project_membership,
)

pytestmark = pytest.mark.contract


def test_l2_album_project_counts_lead_single_and_deluxe_once(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(
        df,
        seed_conn,
        merge_level=2,
        include_compilations=False,
        billboard_mode=False,
    )
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 9
    assert int(row["unique_canonical_songs"]) == 3


def test_source_breakdown_sums_to_album_project_total(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    totals = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    breakdown = compute_album_source_breakdown(df, seed_conn, merge_level=2)
    total = int(totals[totals["album_project_name"] == "Fixture Future LP"].iloc[0]["play_count"])
    rows = breakdown[breakdown["album_project_name"] == "Fixture Future LP"]
    assert int(rows["play_count"].sum()) == total
    assert rows.set_index("source_bucket")["play_count"].to_dict() == {
        "single": 2,
        "original_album": 4,
        "deluxe": 2,
        "compilation": 1,
    }


def test_billboard_album_project_excludes_pre_release_single_week(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    weekly = compute_album_weekly_rankings(
        df,
        top_n=50,
        merge_level=2,
        include_compilations=False,
    )
    future_lp = weekly[weekly["album_name"] == "Fixture Future LP"]
    assert not future_lp.empty
    assert future_lp["billboard_week"].min() >= "2026-02-01"


def test_pure_compilation_does_not_become_album_project_at_l2(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    assert "Fixture Pure Compilation" not in set(result["album_project_name"])


def test_compilation_exclusive_track_forms_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Compilation Plus"].iloc[0]
    assert int(row["play_count"]) == 4
    assert int(row["unique_canonical_songs"]) == 1


def test_l3_rerecord_and_collab_versions_join_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=3, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 12
    assert int(row["unique_canonical_songs"]) == 4


def test_album_membership_has_one_default_project_per_canonical_song(seed_conn):
    membership = load_album_project_membership(seed_conn, merge_level=2, include_compilations=True)
    duplicated = membership[membership.duplicated(["canonical_song_key"], keep=False)]
    assert duplicated.empty
```

- [x] **Step 0.6: Run the new tests and verify failure**

Run:

```bash
source .venv/bin/activate && python backend/tests/fixtures/build_seed_db.py
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py -v
```

Expected: tests fail because `backend.domains.playback.album_projects` does not exist.

---

## Task 1: Add Album Project Schema And Bootstrap

**Purpose:** Represent album projects explicitly while preserving existing release groups and track groups.

**Files:**
- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Create: `backend/domains/playback/album_projects.py`
- Test: `backend/tests/unit/test_album_project_resolver.py`

- [x] **Step 1.1: Add schema tables**

Add these tables to `SCHEMA` in `backend/core/db.py`:

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

- [x] **Step 1.2: Add migration helpers**

In `backend/core/migrations.py`, add an idempotent migration function that executes the same SQL and runs during `ensure_schema()`. Use table and index names exactly as above.

- [x] **Step 1.3: Add bootstrap function signature**

Create `backend/domains/playback/album_projects.py`:

```python
from __future__ import annotations

import sqlite3
from typing import Optional

import pandas as pd


SOURCE_BUCKET_ORDER = {
    "original_album": 0,
    "deluxe": 1,
    "single": 2,
    "compilation": 3,
    "live_acoustic_remix": 4,
    "rerecord": 5,
    "other": 6,
    "inferred": 7,
}


def ensure_album_projects(conn: sqlite3.Connection) -> None:
    """Create deterministic album projects from existing release groups and album metadata."""
    bootstrap_album_projects(conn)


def bootstrap_album_projects(conn: sqlite3.Connection) -> None:
    """Populate album project tables without deleting user-maintained manual rows."""
    _bootstrap_from_release_groups(conn)
    _bootstrap_standalone_album_projects(conn)
    _bootstrap_compilation_exclusive_projects(conn)


def _bootstrap_from_release_groups(conn: sqlite3.Connection) -> None:
    """Create one album project for each release/composition group."""
    raise NotImplementedError


def _bootstrap_standalone_album_projects(conn: sqlite3.Connection) -> None:
    """Create standalone LP/EP projects for eligible albums not in release groups."""
    raise NotImplementedError


def _bootstrap_compilation_exclusive_projects(conn: sqlite3.Connection) -> None:
    """Create compilation-exclusive projects only for tracks without a primary non-compilation project."""
    raise NotImplementedError
```

- [x] **Step 1.4: Write unit test for idempotency**

Create `backend/tests/unit/test_album_project_resolver.py`:

```python
from __future__ import annotations

from backend.domains.playback.album_projects import ensure_album_projects


def test_ensure_album_projects_is_idempotent(seed_conn):
    ensure_album_projects(seed_conn)
    first_count = seed_conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]
    ensure_album_projects(seed_conn)
    second_count = seed_conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]
    assert second_count == first_count
```

- [x] **Step 1.5: Implement bootstrap**

Implement `_bootstrap_from_release_groups()` so each `release_groups` row creates one `album_projects` row:

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

- [x] **Step 1.6: Run schema/bootstrap tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_album_project_resolver.py -v
source .venv/bin/activate && pytest backend/tests/unit/test_migrations.py -v
```

Expected: all selected tests pass.

---

## Task 2: Implement Canonical Song Membership And Album Source Breakdown

**Purpose:** Make album project plays computable from valid events rather than source album row grouping.

**Files:**
- Modify: `backend/domains/playback/album_projects.py`
- Test: `backend/tests/unit/test_album_project_resolver.py`
- Test: `backend/tests/contract/test_album_project_rules.py`

- [x] **Step 2.1: Add canonical song key helper**

Add to `backend/domains/playback/album_projects.py`:

```python
def apply_canonical_song_keys(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
) -> pd.DataFrame:
    """Return df with canonical_song_key and canonical_song_name columns."""
    out = df.copy()
    out["canonical_song_key"] = out["track_id"].astype("Int64").astype(str)
    out["canonical_song_name"] = out["track_name"]
    if merge_level <= 1 or out.empty:
        return out

    from backend.domains.playback.track_groups import load_track_group_keys

    keys = load_track_group_keys(conn, merge_level=merge_level)
    if keys.empty:
        return out

    key_map = keys.set_index("track_id")
    mapped_id = out["track_id"].map(key_map["track_agg_id"])
    mapped_name = out["track_id"].map(key_map["track_agg_name"])
    mask = mapped_id.notna()
    out.loc[mask, "canonical_song_key"] = "group:" + mapped_id[mask].astype(int).astype(str)
    out.loc[mask, "canonical_song_name"] = mapped_name[mask]
    return out
```

- [x] **Step 2.2: Add album project membership resolver**

Add:

```python
def load_album_project_membership(
    conn: sqlite3.Connection,
    merge_level: int = 2,
    include_compilations: bool = False,
) -> pd.DataFrame:
    """Return one default album project owner per canonical song for the chosen merge level."""
    ensure_album_projects(conn)
    raw = pd.read_sql_query(
        """SELECT ap.project_id,
                  ap.canonical_name AS album_project_name,
                  ap.artist_id,
                  ar.artist_name,
                  ap.primary_album_id,
                  ap.release_date,
                  ap.scope,
                  ap.project_type,
                  ap.include_in_charts,
                  apt.track_id,
                  apt.membership_role,
                  apt.min_merge_level,
                  apt.source_album_id,
                  apa.source_bucket,
                  apt.is_exclusive,
                  apt.inferred
           FROM album_project_tracks apt
           JOIN album_projects ap ON ap.project_id = apt.project_id
           JOIN artists ar ON ar.artist_id = ap.artist_id
           LEFT JOIN album_project_albums apa
             ON apa.project_id = apt.project_id
            AND apa.album_id = COALESCE(apt.source_album_id, ap.primary_album_id)
           WHERE apt.min_merge_level <= ?
             AND ap.include_in_charts = 1""",
        conn,
        params=(merge_level,),
    )
    if raw.empty:
        return raw
    if not include_compilations:
        raw = raw[raw["project_type"] != "compilation_exclusive"]
    keyed = apply_canonical_song_keys(raw, conn, merge_level)
    keyed["_owner_rank"] = keyed["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
    keyed = keyed.sort_values(
        ["canonical_song_key", "_owner_rank", "release_date", "project_id"],
        ascending=[True, True, True, True],
    )
    return keyed.drop_duplicates("canonical_song_key").drop(columns=["_owner_rank"])
```

- [x] **Step 2.3: Add album project aggregation**

Add:

```python
def compute_album_project_plays(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int = 2,
    include_compilations: bool = False,
    billboard_mode: bool = False,
) -> pd.DataFrame:
    """Aggregate valid play events to default album projects."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "album_project_id",
                "album_project_name",
                "artist_name",
                "play_count",
                "total_ms",
                "unique_canonical_songs",
                "release_date",
            ]
        )
    if merge_level <= 1:
        return _compute_l1_album_container_plays(df, conn, include_compilations)

    events = apply_canonical_song_keys(df, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level, include_compilations)
    if membership.empty:
        return pd.DataFrame()
    merged = events.merge(
        membership,
        on="canonical_song_key",
        how="inner",
        suffixes=("", "_project"),
    )
    if billboard_mode:
        merged["_event_ts"] = pd.to_datetime(merged["ts"], errors="coerce")
        merged["_release_ts"] = pd.to_datetime(merged["release_date"], errors="coerce")
        merged = merged[
            merged["_release_ts"].isna()
            | (merged["_event_ts"].dt.date >= merged["_release_ts"].dt.date)
        ]
    result = (
        merged.groupby(["project_id", "album_project_name", "artist_name", "release_date"], dropna=False)
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            unique_canonical_songs=("canonical_song_key", "nunique"),
        )
        .reset_index()
        .rename(columns={"project_id": "album_project_id"})
    )
    return result.sort_values(["play_count", "total_ms"], ascending=[False, False])
```

- [x] **Step 2.4: Add source breakdown**

Add:

```python
def compute_album_source_breakdown(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int = 2,
) -> pd.DataFrame:
    """Explain album project plays by source album bucket."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "album_project_id",
                "album_project_name",
                "source_album_id",
                "source_album_name",
                "source_bucket",
                "play_count",
                "total_ms",
            ]
        )
    events = apply_canonical_song_keys(df, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level, include_compilations=True)
    merged = events.merge(membership, on="canonical_song_key", how="inner", suffixes=("", "_project"))
    merged = _attach_source_album_bucket(merged, conn)
    return (
        merged.groupby(
            [
                "project_id",
                "album_project_name",
                "source_album_id",
                "source_album_name",
                "source_bucket",
            ],
            dropna=False,
        )
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
        .rename(columns={"project_id": "album_project_id"})
    )
```

Implement `_attach_source_album_bucket()` using `source_album_id`, `albums`, and `spotify_album_meta`. If `source_album_id` is null, set `source_bucket = 'inferred'`.

- [x] **Step 2.5: Run unit and contract tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_album_project_resolver.py backend/tests/contract/test_album_project_rules.py -v
```

Expected: project resolver tests pass, except tests that depend on chart entry points still fail until Tasks 3 and 4.

---

## Task 3: Replace Personal Album Chart And Leaderboard Aggregation

**Purpose:** Make `/api/analysis/charts?entity=album` and leaderboard album rows use album project semantics.

**Files:**
- Modify: `backend/services/analysis_stats_service.py`
- Modify: `backend/services/play_service.py`
- Test: `backend/tests/contract/test_album_project_rules.py`
- Test: `backend/tests/contract/test_album_release_groups.py`

- [x] **Step 3.1: Replace album branch in `_chart_agg()`**

In `backend/services/analysis_stats_service.py`, replace the `entity == "album"` branch in `_chart_agg()` with:

```python
if entity == "album":
    from backend.domains.playback.album_projects import compute_album_project_plays

    if conn is None:
        return pd.DataFrame()

    project_rows = compute_album_project_plays(
        df_agg,
        conn,
        merge_level=merge_level,
        include_compilations=True,
        billboard_mode=False,
    )
    if project_rows.empty:
        return project_rows
    return project_rows.rename(
        columns={
            "album_project_name": "album_name",
            "play_count": "plays",
            "album_project_id": "album_project_id",
        }
    ).assign(
        hours=lambda x: x["total_ms"] / 3600000,
        unique_tracks=lambda x: x["unique_canonical_songs"],
        unique_albums=1,
    )
```

Keep the existing single/compilation filtering in `chart_rows()` only as a compatibility guard for L1. For `merge_level > 1`, filtering is already handled by `compute_album_project_plays(... include_compilations=include_compilations)`.

- [x] **Step 3.2: Pass `include_compilations` into `_chart_agg()`**

Change `_chart_agg()` signature to:

```python
def _chart_agg(
    df: pd.DataFrame,
    entity: str,
    conn: Optional[sqlite3.Connection] = None,
    merge_level: int = 2,
    include_compilations: bool = False,
):
```

Update the call in `chart_rows()`:

```python
agg = _chart_agg(
    df,
    entity,
    conn=conn,
    merge_level=merge_level,
    include_compilations=include_compilations,
)
```

- [x] **Step 3.3: Update album row payload**

In `chart_rows()`, include these fields for album rows:

```python
"album_project_id": int(r.get("album_project_id")) if pd.notna(r.get("album_project_id")) else None,
"album_name": r["album_name"],
"artist_name": r["artist_name"],
"plays": int(r["plays"]),
"hours": round(float(r["hours"]), 2),
"cover_url": album_covers.get((r["album_name"], r["artist_name"])),
"album_category": category,
"unique_tracks": int(r["unique_tracks"]),
"unique_albums": int(r["unique_albums"]),
```

- [x] **Step 3.4: Replace album branch in `get_leaderboard()`**

In `backend/services/play_service.py`, replace the `entity == "album"` branch with the same helper. Keep track and artist branches unchanged.

- [x] **Step 3.5: Update old release-group tests**

In `backend/tests/contract/test_album_release_groups.py`, update assertions:

- Keep `test_fixture_single_excluded_from_default_album_chart`.
- Add assertion that `Fixture Future Single` does not appear as standalone in L2.
- Add assertion that `Fixture Future LP` appears with 9 plays in L2.
- Keep release group map tests unchanged because release groups still exist.

- [x] **Step 3.6: Run chart tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_album_release_groups.py -v
```

Expected: personal album chart tests pass.

---

## Task 4: Replace Billboard Album Ranking

**Purpose:** Make weekly album charts use album project plays and enforce release-date eligibility.

**Files:**
- Modify: `backend/domains/billboard/chart_ranking.py`
- Modify: `backend/domains/billboard/version_merge.py`
- Test: `backend/tests/contract/test_album_project_rules.py`
- Test: `backend/tests/contract/test_billboard_attribution.py`

- [x] **Step 4.1: Replace `compute_album_weekly_rankings()` raw path**

In `backend/domains/billboard/chart_ranking.py`, implement weekly project grouping:

```python
def compute_album_weekly_rankings(
    _df,
    top_n,
    pre_agg=None,
    merge_level: int = 2,
    include_compilations: bool = False,
):
    """Aggregate per-week album project rankings from valid play events."""
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import compute_album_project_plays

    if pre_agg is not None and not pre_agg.empty and "track_id" in pre_agg.columns:
        df = _expand_track_source_preagg(pre_agg)
    else:
        df = _df.copy()

    if df.empty:
        return pd.DataFrame()

    frames = []
    conn = get_db()
    try:
        for week, week_df in df.groupby("billboard_week"):
            ranked = compute_album_project_plays(
                week_df,
                conn,
                merge_level=merge_level,
                include_compilations=include_compilations,
                billboard_mode=True,
            )
            if ranked.empty:
                continue
            ranked["billboard_week"] = week
            frames.append(ranked)
    finally:
        conn.close()

    if not frames:
        return pd.DataFrame()

    weekly_album = pd.concat(frames, ignore_index=True).rename(
        columns={
            "album_project_name": "album_name",
            "play_count": "play_count",
            "unique_canonical_songs": "tracks_count",
        }
    )
    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    return weekly_album[weekly_album["rank"] <= top_n]
```

- [x] **Step 4.2: Add helper for preagg compatibility**

Add `_expand_track_source_preagg(pre_agg)` in the same file. It must accept preaggregated track-source rows with columns:

- `billboard_week`
- `track_id`
- `source_album_id`
- `play_count`
- `total_ms`
- `ts`
- `track_name`
- `artist_name`
- `album_name`

It should expand `play_count` into minimal event-like rows for aggregation:

```python
def _expand_track_source_preagg(pre_agg: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in pre_agg.itertuples(index=False):
        play_count = int(getattr(r, "play_count"))
        total_ms = int(getattr(r, "total_ms"))
        per_play_ms = total_ms // play_count if play_count else 0
        for _ in range(play_count):
            rows.append(
                {
                    "billboard_week": getattr(r, "billboard_week"),
                    "track_id": getattr(r, "track_id"),
                    "track_name": getattr(r, "track_name"),
                    "artist_name": getattr(r, "artist_name"),
                    "album_name": getattr(r, "album_name"),
                    "source_album_id": getattr(r, "source_album_id", None),
                    "ms_played": per_play_ms,
                    "ts": getattr(r, "ts", None),
                }
            )
    return pd.DataFrame(rows)
```

This is a correctness bridge. Task 5 replaces it with a base-grain preaggregation table so large datasets do not expand rows.

- [x] **Step 4.3: Stop applying release-group row merge after project aggregation**

Remove `_apply_album_release_groups()` from the album weekly path. Keep `backend/domains/billboard/version_merge.py` for legacy utilities and detail version display.

- [x] **Step 4.4: Run Billboard contract tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_billboard_attribution.py -v
```

Expected: Billboard album project tests pass. If an old test asserts source album grouping, update it to assert album project grouping.

---

## Task 5: Add Base-Grain Preaggregation For Album Project Billboard

**Purpose:** Avoid row expansion and keep raw fallback and preaggregation consistent.

**Files:**
- Modify: `backend/core/db.py`
- Modify: `backend/domains/billboard/data_loader.py`
- Modify: `backend/domains/billboard/chart_ranking.py`
- Test: `backend/tests/contract/test_billboard_counting_consistency.py`

- [x] **Step 5.1: Add `agg_weekly_track_sources` table**

Add this table to `SCHEMA`:

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

- [x] **Step 5.2: Populate track-source preaggregation**

In `build_aggregations()` after valid weekly event DataFrame is produced, add:

```python
df_source = df.copy()
df_source["_source_album_id"] = df_source["source_album_id"].fillna(0).astype(int)
track_source_agg = (
    df_source.groupby(["billboard_week", "ts_date", "track_id", "_source_album_id"])
    .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
    .reset_index()
    .rename(columns={"ts_date": "play_date", "_source_album_id": "source_album_id"})
)
```

Write rows into `agg_weekly_track_sources`.

- [x] **Step 5.3: Load preaggregation with names**

Add `load_agg_weekly_track_sources(conn)` to `backend/core/db.py`:

```python
def load_agg_weekly_track_sources(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT awts.billboard_week,
                  awts.play_date,
                  awts.track_id,
                  awts.source_album_id,
                  t.track_name,
                  ar.artist_name,
                  al.album_name,
                  awts.play_count,
                  awts.total_ms,
                  awts.play_date AS ts
           FROM agg_weekly_track_sources awts
           JOIN tracks t ON awts.track_id = t.track_id
           JOIN artists ar ON t.artist_id = ar.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id""",
        conn,
    )
```

- [x] **Step 5.4: Wire Billboard data loader**

In `backend/domains/billboard/data_loader.py`, load `agg_weekly_track_sources` for album rankings instead of `agg_weekly_albums` when the table exists and row count is positive.

- [x] **Step 5.5: Add raw vs preagg consistency test**

Update `backend/tests/contract/test_billboard_counting_consistency.py`:

```python
def test_album_project_raw_and_track_source_preagg_match(seed_conn):
    from backend.core.db import load_plays, load_agg_weekly_track_sources
    from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings

    raw = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    raw_weekly = compute_album_weekly_rankings(raw, top_n=50, merge_level=2, include_compilations=True)

    preagg = load_agg_weekly_track_sources(seed_conn)
    preagg_weekly = compute_album_weekly_rankings(
        None,
        top_n=50,
        pre_agg=preagg,
        merge_level=2,
        include_compilations=True,
    )

    cols = ["billboard_week", "album_name", "artist_name", "play_count"]
    assert raw_weekly[cols].sort_values(cols).reset_index(drop=True).equals(
        preagg_weekly[cols].sort_values(cols).reset_index(drop=True)
    )
```

- [x] **Step 5.6: Run consistency tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_billboard_counting_consistency.py backend/tests/contract/test_album_project_rules.py -v
```

Expected: raw and preaggregation album charts match.

---

## Task 6: Add Album Project Detail Payload And Frontend Section

**Purpose:** Explain the new album statistics in album detail pages.

**Files:**
- Modify: `backend/domains/billboard/details.py`
- Modify: `backend/api/billboard/details.py`
- Modify: `frontend/src/types/billboard.ts`
- Create: `frontend/src/features/music/details/AlbumProjectSection.tsx`
- Modify: `frontend/src/features/music/details/AlbumDetailExperience.tsx`
- Test: `frontend/src/tests/phase5-architecture.test.ts`

- [x] **Step 6.1: Add backend detail helper**

Add to `backend/domains/billboard/details.py`:

```python
def _get_album_project_payload(album_name: str, artist_name: str, df: pd.DataFrame, merge_level: int) -> dict:
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import (
        compute_album_project_plays,
        compute_album_source_breakdown,
        load_album_project_membership,
    )

    conn = get_db()
    try:
        totals = compute_album_project_plays(df, conn, merge_level=merge_level, include_compilations=True)
        membership = load_album_project_membership(conn, merge_level=merge_level, include_compilations=True)
        breakdown = compute_album_source_breakdown(df, conn, merge_level=merge_level)
    finally:
        conn.close()

    match = totals[
        (totals["album_project_name"] == album_name)
        & (totals["artist_name"] == artist_name)
    ]
    if match.empty:
        return {}

    project_id = int(match.iloc[0]["album_project_id"])
    project_tracks = membership[membership["project_id"] == project_id]
    project_breakdown = breakdown[breakdown["album_project_id"] == project_id]
    return {
        "album_project_id": project_id,
        "album_project_name": album_name,
        "artist_name": artist_name,
        "release_date": str(match.iloc[0].get("release_date") or ""),
        "play_count": int(match.iloc[0]["play_count"]),
        "total_ms": int(match.iloc[0]["total_ms"]),
        "unique_canonical_songs": int(match.iloc[0]["unique_canonical_songs"]),
        "tracks": project_tracks.to_dict(orient="records"),
        "source_breakdown": project_breakdown.to_dict(orient="records"),
    }
```

- [x] **Step 6.2: Add response model fields**

In `backend/api/billboard/details.py`, add:

```python
class AlbumChartDetailResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    album_name: Optional[str] = None
    artist_name: Optional[str] = None
    cover_url: Optional[str] = None
    meta: Optional[dict] = None
    info: Optional[dict] = None
    chart_summary: Optional[dict] = None
    album_project: Optional[dict] = None
    album_weekly_history: Optional[list[dict]] = None
    album_no1_by_week: Optional[list[dict]] = None
    best_singles_overlay: Optional[list[dict]] = None
    tracks: Optional[list[dict]] = None
```

- [x] **Step 6.3: Add payload to album detail return**

In `get_album_chart_detail()`, include:

```python
"album_project": _get_album_project_payload(album_name, resolved_artist, load_plays_df, merge_level),
```

Use the same valid-play DataFrame that feeds `compute_billboard_data()` when available. If `compute_billboard_data()` does not expose it, load it with the same filters and pass the same `dynamic_threshold` / `max_merge_gap_minutes` values.

- [x] **Step 6.4: Add frontend types**

In `frontend/src/types/billboard.ts`, add:

```ts
export interface AlbumProjectTrack {
  [key: string]: any
  project_id: number
  album_project_name: string
  canonical_song_key: string
  canonical_song_name: string
  track_id: number
  membership_role: string
  source_bucket: string | null
  is_exclusive: number
}

export interface AlbumSourceBreakdownItem {
  [key: string]: any
  album_project_id: number
  album_project_name: string
  source_album_id: number | null
  source_album_name: string | null
  source_bucket: string
  play_count: number
  total_ms: number
}

export interface AlbumProject {
  [key: string]: any
  album_project_id: number
  album_project_name: string
  artist_name: string
  release_date: string
  play_count: number
  total_ms: number
  unique_canonical_songs: number
  tracks: AlbumProjectTrack[]
  source_breakdown: AlbumSourceBreakdownItem[]
}
```

Extend `AlbumDetailResponse`:

```ts
album_project?: AlbumProject | null
```

- [x] **Step 6.5: Create frontend section**

Create `frontend/src/features/music/details/AlbumProjectSection.tsx`:

```tsx
import type { AlbumProject } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'

type Props = {
  project: AlbumProject
}

const BUCKET_LABELS: Record<string, string> = {
  original_album: '原版专辑',
  deluxe: '豪华版/扩展版',
  single: '单曲版',
  compilation: '精选集/合辑',
  live_acoustic_remix: 'Live / Acoustic / Remix',
  rerecord: '重录版本',
  other: '其他来源',
  inferred: '推断来源',
}

export function AlbumProjectSection({ project }: Props) {
  const total = Math.max(project.play_count, 1)

  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">专辑项目播放</p>
          <p className="mt-1 text-2xl font-semibold">{project.play_count.toLocaleString()}</p>
        </GlassCard>
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">项目曲目数</p>
          <p className="mt-1 text-2xl font-semibold">{project.unique_canonical_songs}</p>
        </GlassCard>
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">发行日期</p>
          <p className="mt-1 text-lg font-semibold">{project.release_date || '未知'}</p>
        </GlassCard>
      </div>

      <GlassCard className="p-4">
        <div className="space-y-3">
          {project.source_breakdown.map((item) => {
            const pct = Math.round((item.play_count / total) * 100)
            return (
              <div key={`${item.source_bucket}-${item.source_album_id ?? 'none'}`} className="space-y-1">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span>{BUCKET_LABELS[item.source_bucket] ?? item.source_bucket}</span>
                  <span className="tabular-nums">{item.play_count.toLocaleString()} · {pct}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </GlassCard>
    </section>
  )
}
```

- [x] **Step 6.6: Insert section into album detail**

In `AlbumDetailExperience.tsx`, import and render:

```tsx
import { AlbumProjectSection } from './AlbumProjectSection'
```

Render near the top:

```tsx
{data.album_project && <AlbumProjectSection project={data.album_project} />}
```

- [x] **Step 6.7: Run frontend checks**

Run:

```bash
cd frontend && npm test -- --run phase5-architecture
cd frontend && npm run build
```

Expected: architecture tests and production build pass.

---

## Task 7: Add Compilation And Collaboration Management Support

**Purpose:** Make the data-management surface able to maintain the new relationships safely.

**Files:**
- Modify: `backend/core/version_merge.py`
- Modify: `backend/api/version_merge.py`
- Modify: `frontend/src/features/settings/components/VersionMergeSection.tsx`
- Test: `backend/tests/contract/test_album_project_rules.py`

- [x] **Step 7.1: Add collaboration candidate detector**

In `backend/core/version_merge.py`, add:

```python
def detect_collaboration_track_group_candidates() -> pd.DataFrame:
    """Find L3 collaboration candidates where candidate artists include the original primary artist."""
    from backend.core.db import get_db

    conn = get_db()
    try:
        return pd.read_sql_query(
            """WITH primary_tracks AS (
                   SELECT t.track_id, t.track_name, ta.artist_id AS primary_artist_id
                   FROM tracks t
                   JOIN track_artists ta ON ta.track_id = t.track_id
                  WHERE ta.role = 'primary'
               ),
               candidate_tracks AS (
                   SELECT t.track_id, t.track_name, ta.artist_id
                   FROM tracks t
                   JOIN track_artists ta ON ta.track_id = t.track_id
               )
               SELECT p.track_id AS original_track_id,
                      p.track_name AS original_track_name,
                      c.track_id AS candidate_track_id,
                      c.track_name AS candidate_track_name,
                      p.primary_artist_id
                 FROM primary_tracks p
                 JOIN candidate_tracks c
                   ON c.artist_id = p.primary_artist_id
                  AND c.track_id != p.track_id
                WHERE lower(c.track_name) LIKE '%' || lower(p.track_name) || '%'
                   OR lower(c.track_name) LIKE '%' || lower(replace(p.track_name, ' - ', ' ')) || '%'""",
            conn,
        )
    finally:
        conn.close()
```

This endpoint produces candidates only; applying them still requires user confirmation.

- [x] **Step 7.2: Expose collaboration candidates**

In `backend/api/version_merge.py`, add response model and endpoint:

```python
class TrackGroupCandidateResponse(BaseModel):
    original_track_id: int
    original_track_name: str
    candidate_track_id: int
    candidate_track_name: str
    primary_artist_id: int


@router.get("/track-group-candidates/collaboration", response_model=list[TrackGroupCandidateResponse])
def collaboration_candidates(auth: None = Depends(require_auth)):
    from backend.core.version_merge import detect_collaboration_track_group_candidates

    df = detect_collaboration_track_group_candidates()
    if df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict(orient="records")
```

- [x] **Step 7.3: Add rebuild endpoint**

In `backend/api/version_merge.py`, add:

```python
@router.post("/album-projects/rebuild", response_model=StatusResponse)
def rebuild_album_projects(auth: None = Depends(require_auth), conn: Connection = Depends(get_conn)):
    from backend.core.cache_manager import invalidate
    from backend.domains.playback.album_projects import ensure_album_projects

    ensure_album_projects(conn)
    invalidate("analysis")
    invalidate("billboard")
    return {"status": "ok"}
```

- [x] **Step 7.4: Update settings UI**

In `VersionMergeSection.tsx`, add two actions:

- Rebuild Album Projects: `POST /version-merge/album-projects/rebuild`
- Collaboration Candidates: `GET /version-merge/track-group-candidates/collaboration`

Use existing API client and existing card layout. Do not add a new page.

- [x] **Step 7.5: Run backend tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py backend/tests/contract/test_merge_level_aggregation.py -v
```

Expected: L3 collaboration fixture remains merged through confirmed `track_groups`; candidate endpoint does not affect counts by itself.

---

## Task 8: Documentation, Regression Matrix, And Final Verification

**Purpose:** Make the new rules durable and easy to verify later.

**Files:**
- Modify: `docs/2026-06-18-playback-stats-rules-latest.md`
- Modify: `docs/2026-06-08-phase5-productization-baseline.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [x] **Step 8.1: Update rules doc status**

Append a section to `docs/2026-06-18-playback-stats-rules-latest.md`:

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

- [x] **Step 8.2: Update Phase 5 baseline**

Add a dated bullet to `docs/2026-06-08-phase5-productization-baseline.md` summarizing:

- album project tables
- album project resolver
- analysis chart replacement
- Billboard album chart replacement
- source breakdown frontend
- validation commands and results

- [x] **Step 8.3: Update assistant guidance docs**

In `AGENTS.md` and `CLAUDE.md`, replace old album-stat guidance with:

```markdown
- L2/L3 album statistics must use album project track membership, not source album row grouping.
- Source album attribution is explanatory only and appears through source breakdown.
- Billboard album charts must filter album project plays by `play_ts >= album_project.release_date`.
- Existing release groups describe album-version relationships; they are not the final album play-count aggregation layer.
```

- [x] **Step 8.4: Update README**

Add a user-facing note:

```markdown
Album statistics now use album project semantics: standard/deluxe versions, included lead singles, and confirmed project versions are counted together according to the selected merge level. Album detail pages include a source breakdown so the total can be traced back to original album, deluxe, single, compilation, and inferred sources.
```

- [x] **Step 8.5: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_album_project_resolver.py -v
source .venv/bin/activate && pytest backend/tests/contract/test_album_project_rules.py -v
source .venv/bin/activate && pytest backend/tests/contract/test_album_release_groups.py backend/tests/contract/test_merge_level_aggregation.py backend/tests/contract/test_billboard_counting_consistency.py -v
```

Expected: all selected tests pass.

- [x] **Step 8.6: Run broader verification**

Run:

```bash
source .venv/bin/activate && pytest -m unit -v
source .venv/bin/activate && pytest -m contract -v
cd frontend && npm test
cd frontend && npm run build
```

Expected: unit and contract backend suites pass; frontend tests and build pass.

- [x] **Step 8.7: Manual seed probes**

Run:

```bash
source .venv/bin/activate && python - <<'PY'
import json
import backend.core.db as db
db.DB_PATH = 'backend/tests/fixtures/seed.db'
db._load_plays_cached.cache_clear()

from backend.core.db import get_db, load_plays
from backend.domains.playback.album_projects import compute_album_project_plays, compute_album_source_breakdown
from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings

conn = get_db(readonly=True)
df = load_plays(conn, min_ms=30000, music_only=True, merge_enabled=True)
projects = compute_album_project_plays(df, conn, merge_level=2, include_compilations=True)
breakdown = compute_album_source_breakdown(df, conn, merge_level=2)
weekly = compute_album_weekly_rankings(df, top_n=50, merge_level=2, include_compilations=True)

payload = {
    'fixture_future_lp': projects[projects['album_project_name'] == 'Fixture Future LP'].to_dict('records'),
    'fixture_future_lp_breakdown': breakdown[breakdown['album_project_name'] == 'Fixture Future LP'].to_dict('records'),
    'fixture_future_lp_first_week': weekly[weekly['album_name'] == 'Fixture Future LP']['billboard_week'].min(),
}
print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
conn.close()
PY
```

Expected:

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
