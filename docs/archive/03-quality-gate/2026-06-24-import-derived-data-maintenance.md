# Import Derived Data Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

## File Map

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
  - Run `import_data(..., build_preaggregations=False)` followed by maintenance.
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

## Design Decisions

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

**Files:**

- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Test: `backend/tests/unit/test_migrations.py`

- [ ] **Step 1.1: Write migration test**

Add this test to `backend/tests/unit/test_migrations.py`:

```python
def test_migration_021_adds_import_maintenance_columns_and_links(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import migrations

    db_path = tmp_path / "spotify_stats.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    db_mod.init_db()
    migrations.run_migrations()

    conn = db_mod.get_db(readonly=True)
    try:
        play_columns = {row["name"] for row in conn.execute("PRAGMA table_info(plays)").fetchall()}
        assert "spotify_track_id_at_play" in play_columns
        assert "spotify_album_id_at_play" in play_columns

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "album_spotify_links" in tables

        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_plays_spotify_track_at_play" in indexes
        assert "idx_plays_spotify_album_at_play" in indexes
        assert "idx_album_spotify_links_album" in indexes
    finally:
        conn.close()
```

- [ ] **Step 1.2: Run the focused test and verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_migrations.py::test_migration_021_adds_import_maintenance_columns_and_links -q
```

Expected: FAIL because the columns/table do not exist yet.

- [ ] **Step 1.3: Update fresh DB schema**

In `backend/core/db.py`, add to the `plays` table definition:

```sql
spotify_track_id_at_play TEXT,
spotify_album_id_at_play TEXT,
```

Add indexes near the existing `plays` indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play ON plays(spotify_track_id_at_play);
CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play ON plays(spotify_album_id_at_play);
```

Add the `album_spotify_links` table and indexes after `spotify_album_meta`.

- [ ] **Step 1.4: Add migration 21**

In `backend/core/migrations.py`, add:

```python
@migration(21, "import_maintenance_play_spotify_ids")
def migrate_021(conn: sqlite3.Connection):
    """Persist play-time Spotify ids and local album to Spotify album evidence."""
    play_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(plays)").fetchall()
    }
    if "spotify_track_id_at_play" not in play_columns:
        conn.execute("ALTER TABLE plays ADD COLUMN spotify_track_id_at_play TEXT")
    if "spotify_album_id_at_play" not in play_columns:
        conn.execute("ALTER TABLE plays ADD COLUMN spotify_album_id_at_play TEXT")
    conn.execute(
        "UPDATE plays SET spotify_track_id_at_play = ("
        "SELECT tracks.spotify_track_id FROM tracks WHERE tracks.track_id = plays.track_id"
        ") WHERE spotify_track_id_at_play IS NULL AND track_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play "
        "ON plays(spotify_track_id_at_play)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play "
        "ON plays(spotify_album_id_at_play)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_spotify_links (
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
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_spotify_links_album "
        "ON album_spotify_links(album_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_spotify_links_spotify_album "
        "ON album_spotify_links(spotify_album_id)"
    )
```

- [ ] **Step 1.5: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_migrations.py::test_migration_021_adds_import_maintenance_columns_and_links -q
```

Expected: PASS.

---

## Task 2: Persist Play-Time Spotify Track IDs During Import

**Files:**

- Modify: `backend/core/import_data.py`
- Test: `backend/tests/unit/test_import_data_flow.py`

- [ ] **Step 2.1: Extend the import test**

In `test_import_data_handles_audio_and_video_records_without_metadata`, change the play query to include `spotify_track_id_at_play`:

```python
rows = conn.execute(
    "SELECT content_type, track_id, source_album_id, spotify_track_id_at_play, "
    "skipped, offline, incognito_mode FROM plays ORDER BY play_id"
).fetchall()
```

Add:

```python
assert rows[0]["spotify_track_id_at_play"] == "signal"
assert rows[1]["spotify_track_id_at_play"] is None
assert rows[2]["spotify_track_id_at_play"] is None
```

- [ ] **Step 2.2: Run focused test and verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py::test_import_data_handles_audio_and_video_records_without_metadata -q
```

Expected: FAIL because the import does not write `spotify_track_id_at_play`.

- [ ] **Step 2.3: Implement extraction helper**

In `backend/core/import_data.py`, add:

```python
def _spotify_track_id_from_uri(uri: str | None) -> str | None:
    if not uri or not uri.startswith("spotify:track:"):
        return None
    return uri.rsplit(":", 1)[-1] or None
```

Use this helper in `_cache_track()` instead of duplicating `replace()`.

- [ ] **Step 2.4: Insert play-time IDs**

In both audio and video import loops, compute:

```python
spotify_track_id_at_play = _spotify_track_id_from_uri(spotify_uri)
```

Add that value to every `plays_batch` tuple. Update both `INSERT INTO plays` statements to include `spotify_track_id_at_play`.

The column list must become:

```sql
INSERT INTO plays(ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
   ts_date, platform, ms_played, conn_country, track_id,
   reason_start, reason_end, shuffle, skipped, offline, incognito_mode,
   content_type, source_album_id, spotify_track_id_at_play)
```

The placeholder list must contain 20 placeholders.

- [ ] **Step 2.5: Add deferred aggregation parameter**

Change the function signature:

```python
def import_data(
    data_dir: str | None = None,
    progress_callback=None,
    agg_min_ms: int = 30000,
    agg_music_only: bool = True,
    agg_week_start_dow: int = 4,
    agg_week_start_hour: int = 0,
    agg_dynamic_threshold: bool = True,
    agg_max_merge_gap_minutes: int | None = None,
    build_preaggregations: bool = True,
) -> dict[str, Any]:
```

Wrap the current `build_aggregations()` block:

```python
if build_preaggregations:
    # existing aggregation code
else:
    agg_results = {}
```

- [ ] **Step 2.6: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py -q
```

Expected: PASS.

---

## Task 3: Add Spotify Metadata Refresh Domain

**Files:**

- Modify: `backend/providers/spotify/client.py`
- Create: `backend/domains/metadata/__init__.py`
- Create: `backend/domains/metadata/spotify_refresh.py`
- Test: `backend/tests/unit/test_spotify_metadata_refresh.py`

- [ ] **Step 3.1: Write unit tests for missing track selection and upsert**

Create `backend/tests/unit/test_spotify_metadata_refresh.py` with:

```python
from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            source_album_id INTEGER,
            ts_date TEXT,
            spotify_track_id_at_play TEXT,
            spotify_album_id_at_play TEXT
        );
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY,
            track_name TEXT,
            duration_ms INTEGER,
            popularity INTEGER,
            explicit INTEGER,
            track_number INTEGER,
            disc_number INTEGER,
            isrc TEXT,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT,
            album_type TEXT,
            release_date TEXT,
            popularity INTEGER,
            label TEXT,
            genres TEXT,
            image_url TEXT,
            album_artists TEXT,
            total_tracks INTEGER,
            track_list TEXT
        );
        CREATE TABLE album_spotify_links(
            album_id INTEGER NOT NULL,
            spotify_album_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            play_count INTEGER NOT NULL DEFAULT 0,
            track_count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(album_id, spotify_album_id, evidence)
        );
        """
    )
    return conn


def test_select_missing_play_track_ids_prefers_play_time_ids():
    from backend.domains.metadata.spotify_refresh import select_missing_track_ids

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'old-track')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'new-track')"
    )

    assert select_missing_track_ids(conn, limit=50) == ["new-track"]


def test_upsert_track_batch_updates_play_album_ids_and_album_links():
    from backend.domains.metadata.spotify_refresh import upsert_track_batch

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'track-a')"
    )

    upsert_track_batch(
        conn,
        [
            {
                "id": "track-a",
                "name": "Track A",
                "duration_ms": 180000,
                "popularity": 42,
                "explicit": False,
                "track_number": 3,
                "disc_number": 1,
                "external_ids": {"isrc": "ISRC-A"},
                "album": {"id": "album-a"},
            }
        ],
    )

    row = conn.execute("SELECT spotify_album_id FROM spotify_track_meta").fetchone()
    assert row["spotify_album_id"] == "album-a"
    play = conn.execute("SELECT spotify_album_id_at_play FROM plays").fetchone()
    assert play["spotify_album_id_at_play"] == "album-a"
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
    assert link["spotify_album_id"] == "album-a"
    assert link["evidence"] == "play_track_api"
```

- [ ] **Step 3.2: Add provider batch helpers**

In `backend/providers/spotify/client.py`, add:

```python
    def get_tracks(self, track_ids: list[str], access_token: str) -> dict | None:
        if not track_ids:
            return {"tracks": []}
        url = f"{self.config.base_url}/tracks?ids={','.join(track_ids)}"
        return self.api_get(url, access_token)

    def get_artists_by_ids(self, artist_ids: list[str], access_token: str) -> dict | None:
        if not artist_ids:
            return {"artists": []}
        url = f"{self.config.base_url}/artists?ids={','.join(artist_ids)}"
        return self.api_get(url, access_token)
```

- [ ] **Step 3.3: Implement metadata refresh helpers**

Create `backend/domains/metadata/spotify_refresh.py` with:

```python
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

TRACK_BATCH_SIZE = 50
ALBUM_BATCH_SIZE = 20


@dataclass(frozen=True)
class MetadataRefreshReport:
    tracks_requested: int = 0
    tracks_updated: int = 0
    albums_requested: int = 0
    albums_updated: int = 0
    provider_available: bool = True
    errors: tuple[str, ...] = ()


def select_missing_track_ids(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT candidate.spotify_track_id
        FROM (
            SELECT spotify_track_id_at_play AS spotify_track_id
            FROM plays
            WHERE spotify_track_id_at_play IS NOT NULL AND spotify_track_id_at_play != ''
            UNION
            SELECT spotify_track_id
            FROM tracks
            WHERE spotify_track_id IS NOT NULL AND spotify_track_id != ''
        ) candidate
        LEFT JOIN spotify_track_meta stm
          ON stm.spotify_track_id = candidate.spotify_track_id
        WHERE stm.spotify_track_id IS NULL
        ORDER BY candidate.spotify_track_id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["spotify_track_id"] for row in rows]


def upsert_track_batch(conn: sqlite3.Connection, tracks: list[dict]) -> int:
    updated = 0
    for track in tracks:
        if not track:
            continue
        album_id = (track.get("album") or {}).get("id")
        conn.execute(
            """INSERT OR REPLACE INTO spotify_track_meta(
                   spotify_track_id, track_name, duration_ms, popularity,
                   explicit, track_number, disc_number, isrc, spotify_album_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                track["id"],
                track.get("name"),
                track.get("duration_ms"),
                track.get("popularity"),
                1 if track.get("explicit") else 0,
                track.get("track_number"),
                track.get("disc_number"),
                (track.get("external_ids") or {}).get("isrc"),
                album_id,
            ),
        )
        if album_id:
            conn.execute(
                """UPDATE plays
                   SET spotify_album_id_at_play = ?
                   WHERE spotify_track_id_at_play = ?""",
                (album_id, track["id"]),
            )
            conn.execute(
                """INSERT OR REPLACE INTO album_spotify_links(
                       album_id, spotify_album_id, evidence, confidence,
                       play_count, track_count, first_seen, last_seen, updated_at)
                   SELECT source_album_id, ?, 'play_track_api', 1.0,
                          COUNT(*), COUNT(DISTINCT track_id), MIN(ts_date), MAX(ts_date),
                          CURRENT_TIMESTAMP
                   FROM plays
                   WHERE spotify_track_id_at_play = ?
                     AND source_album_id IS NOT NULL
                   GROUP BY source_album_id""",
                (album_id, track["id"]),
            )
        updated += 1
    conn.commit()
    return updated


def select_missing_album_ids(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT spotify_album_id
        FROM (
            SELECT spotify_album_id_at_play AS spotify_album_id
            FROM plays
            WHERE spotify_album_id_at_play IS NOT NULL AND spotify_album_id_at_play != ''
            UNION
            SELECT spotify_album_id
            FROM spotify_track_meta
            WHERE spotify_album_id IS NOT NULL AND spotify_album_id != ''
            UNION
            SELECT spotify_album_id
            FROM album_spotify_links
            WHERE spotify_album_id IS NOT NULL AND spotify_album_id != ''
        ) candidate
        LEFT JOIN spotify_album_meta sam
          ON sam.spotify_album_id = candidate.spotify_album_id
        WHERE sam.spotify_album_id IS NULL
           OR sam.image_url IS NULL
           OR sam.image_url = ''
           OR sam.total_tracks IS NULL
        ORDER BY candidate.spotify_album_id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["spotify_album_id"] for row in rows]


def upsert_album_batch(conn: sqlite3.Connection, albums: list[dict]) -> int:
    updated = 0
    for album in albums:
        if not album:
            continue
        images = album.get("images") or []
        artists = ", ".join(a.get("name", "") for a in album.get("artists", []) if a.get("name"))
        tracks = album.get("tracks", {}).get("items", [])
        track_ids = [item.get("id") for item in tracks if item.get("id")]
        genres = json.dumps(album.get("genres", []), ensure_ascii=False) if album.get("genres") else None
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   popularity, label, genres, image_url, album_artists,
                   total_tracks, track_list)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(spotify_album_id) DO UPDATE SET
                   album_name = excluded.album_name,
                   album_type = excluded.album_type,
                   release_date = excluded.release_date,
                   popularity = excluded.popularity,
                   label = excluded.label,
                   genres = COALESCE(excluded.genres, spotify_album_meta.genres),
                   image_url = COALESCE(excluded.image_url, spotify_album_meta.image_url),
                   album_artists = COALESCE(excluded.album_artists, spotify_album_meta.album_artists),
                   total_tracks = COALESCE(excluded.total_tracks, spotify_album_meta.total_tracks),
                   track_list = COALESCE(excluded.track_list, spotify_album_meta.track_list)""",
            (
                album["id"],
                album.get("name"),
                album.get("album_type"),
                album.get("release_date"),
                album.get("popularity"),
                album.get("label"),
                genres,
                images[0].get("url") if images else None,
                artists or None,
                album.get("total_tracks"),
                json.dumps(track_ids, ensure_ascii=False) if track_ids else None,
            ),
        )
        updated += 1
    conn.commit()
    return updated
```

- [ ] **Step 3.4: Add online orchestration**

In the same file, add:

```python
def refresh_missing_spotify_metadata(
    conn: sqlite3.Connection,
    provider,
    access_token: str | None,
    progress_callback=None,
) -> MetadataRefreshReport:
    if not access_token:
        return MetadataRefreshReport(provider_available=False, errors=("spotify_credentials_missing",))

    errors: list[str] = []
    track_ids = select_missing_track_ids(conn)
    tracks_updated = 0
    album_ids_seen: set[str] = set()

    for offset in range(0, len(track_ids), TRACK_BATCH_SIZE):
        batch = track_ids[offset : offset + TRACK_BATCH_SIZE]
        if progress_callback:
            progress_callback(f"刷新 Spotify 曲目元数据 {offset + len(batch)} / {len(track_ids)}", 0.0)
        data = provider.get_tracks(batch, access_token)
        if data is None:
            errors.append("tracks_batch_failed")
            continue
        tracks = data.get("tracks", [])
        tracks_updated += upsert_track_batch(conn, tracks)
        for track in tracks:
            if track and track.get("album", {}).get("id"):
                album_ids_seen.add(track["album"]["id"])

    album_ids = list(dict.fromkeys([*album_ids_seen, *select_missing_album_ids(conn)]))
    albums_updated = 0
    for offset in range(0, len(album_ids), ALBUM_BATCH_SIZE):
        batch = album_ids[offset : offset + ALBUM_BATCH_SIZE]
        if progress_callback:
            progress_callback(f"刷新 Spotify 专辑元数据 {offset + len(batch)} / {len(album_ids)}", 0.0)
        data = provider.get_albums(batch, access_token)
        if data is None:
            errors.append("albums_batch_failed")
            continue
        albums_updated += upsert_album_batch(conn, data.get("albums", []))

    return MetadataRefreshReport(
        tracks_requested=len(track_ids),
        tracks_updated=tracks_updated,
        albums_requested=len(album_ids),
        albums_updated=albums_updated,
        provider_available=True,
        errors=tuple(errors),
    )
```

- [ ] **Step 3.5: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_spotify_metadata_refresh.py -q
```

Expected: PASS.

---

## Task 4: Make Album Project Bootstrap Use Link Evidence Before Name Match

**Files:**

- Modify: `backend/domains/playback/album_projects.py`
- Test: `backend/tests/contract/test_album_project_import_maintenance.py`

- [ ] **Step 4.1: Write same-name single/full-album contract test**

Create `backend/tests/contract/test_album_project_import_maintenance.py`:

```python
from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.contract


def test_album_project_rebuild_uses_local_tracks_when_name_match_points_to_single(isolated_seed_db):
    from backend.domains.playback.album_projects import rebuild_album_projects

    conn = sqlite3.connect(isolated_seed_db)
    conn.row_factory = sqlite3.Row
    try:
        artist_id = conn.execute(
            "INSERT INTO artists(artist_name) VALUES ('Fixture Import Artist')"
        ).lastrowid
        album_id = conn.execute(
            "INSERT INTO albums(album_name, artist_id) VALUES ('Dinner Party Fixture', ?)",
            (artist_id,),
        ).lastrowid

        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks, image_url)
               VALUES ('single-id', 'Dinner Party Fixture', 'single', '2026-03-20',
                       'Fixture Import Artist', 1, 'single.jpg')"""
        )
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks, image_url)
               VALUES ('album-id', 'Dinner Party Fixture', 'album', '2026-06-01',
                       'Fixture Import Artist', 11, 'album.jpg')"""
        )
        conn.execute(
            """INSERT INTO album_spotify_links(
                   album_id, spotify_album_id, evidence, confidence, play_count,
                   track_count, first_seen, last_seen)
               VALUES (?, 'album-id', 'play_track_api', 1.0, 11, 11, '2026-06-01', '2026-06-02')""",
            (album_id,),
        )
        for idx in range(11):
            track_id = 9000 + idx
            conn.execute(
                "INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (track_id, f"Fixture Track {idx}", artist_id, album_id, f"track-{idx}"),
            )
            conn.execute(
                "INSERT INTO track_albums(track_id, album_id) VALUES (?, ?)",
                (track_id, album_id),
            )
        conn.commit()

        rebuild_album_projects(conn)

        row = conn.execute(
            """SELECT ap.project_id, ap.release_date, COUNT(apt.track_id) AS tracks
               FROM album_projects ap
               JOIN album_project_albums apa ON apa.project_id = ap.project_id
               JOIN album_project_tracks apt ON apt.project_id = ap.project_id
               WHERE apa.album_id = ?
               GROUP BY ap.project_id""",
            (album_id,),
        ).fetchone()
        assert row is not None
        assert row["release_date"] == "2026-06-01"
        assert row["tracks"] == 11
    finally:
        conn.close()
```

- [ ] **Step 4.2: Run the test and verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_album_project_import_maintenance.py::test_album_project_rebuild_uses_local_tracks_when_name_match_points_to_single -q
```

Expected: FAIL or no project row, because current bootstrap trusts the same-name single metadata too much.

- [ ] **Step 4.3: Add candidate query helper**

In `backend/domains/playback/album_projects.py`, add:

```python
def _best_spotify_album_for_local_album(conn: sqlite3.Connection, album_id: int):
    rows = conn.execute(
        """SELECT sam.spotify_album_id, sam.album_type, sam.total_tracks, sam.release_date,
                  sam.album_artists, sam.image_url,
                  MAX(asl.confidence) AS confidence,
                  SUM(asl.play_count) AS play_count,
                  MAX(asl.track_count) AS link_track_count
           FROM album_spotify_links asl
           JOIN spotify_album_meta sam ON sam.spotify_album_id = asl.spotify_album_id
           WHERE asl.album_id = ?
           GROUP BY sam.spotify_album_id
           ORDER BY
             CASE sam.album_type WHEN 'album' THEN 0 WHEN 'single' THEN 1 ELSE 2 END,
             COALESCE(sam.total_tracks, 0) DESC,
             COALESCE(play_count, 0) DESC,
             confidence DESC
           LIMIT 1""",
        (album_id,),
    ).fetchone()
    return rows
```

- [ ] **Step 4.4: Use linked metadata in standalone bootstrap**

In `_bootstrap_standalone_album_projects()`, after `spotify_type`, `spotify_tracks`, and `local_tracks` are computed, fetch:

```python
linked = _best_spotify_album_for_local_album(conn, int(album["album_id"]))
if linked:
    spotify_type = linked["album_type"] or spotify_type
    spotify_tracks = linked["total_tracks"] if linked["total_tracks"] is not None else spotify_tracks
    release_date = linked["release_date"] or album["release_date"]
else:
    release_date = album["release_date"]
```

Use `release_date` in `_upsert_project()`.

Then add the guard:

```python
if (spotify_type or "").lower() == "single" and local_tracks >= 7:
    spotify_type = "album"
    spotify_tracks = max(int(spotify_tracks or 0), local_tracks)
elif (spotify_type or "").lower() == "single" and 3 <= local_tracks <= 6:
    spotify_tracks = max(int(spotify_tracks or 0), local_tracks)
```

This guard is intentionally conservative: it only overrides a same-name single when local membership proves the container is EP/LP-sized.

- [ ] **Step 4.5: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_album_project_import_maintenance.py -q
.venv/bin/pytest backend/tests/contract/test_album_project_rules.py backend/tests/unit/test_album_project_resolver.py -q
```

Expected: PASS.

---

## Task 5: Add Import Maintenance Service

**Files:**

- Create: `backend/services/import_maintenance_service.py`
- Modify: `backend/api/import_.py`
- Test: `backend/tests/contract/test_import_api_jobs.py`

- [ ] **Step 5.1: Write API orchestration test**

Add to `backend/tests/contract/test_import_api_jobs.py`:

```python
def test_streaming_import_job_runs_derived_maintenance_before_done(client, monkeypatch):
    from backend.api import import_ as import_api

    events = []

    def fake_import_data(progress_callback, build_preaggregations=True):
        events.append(("import", build_preaggregations))
        progress_callback("导入基础播放", 0.5)
        return {"total_records": 3, "unique_artists": 1, "unique_albums": 1, "unique_tracks": 1}

    def fake_maintenance(progress_callback):
        events.append(("maintenance", None))
        progress_callback("维护派生数据", 0.9)
        return {
            "maintenance_status": "ok",
            "tracks_metadata_updated": 2,
            "albums_metadata_updated": 1,
            "album_projects_rebuilt": True,
            "agg_track_wks": 3,
            "agg_album_wks": 2,
            "unresolved_recent_tracks": 0,
            "unresolved_recent_albums": 0,
        }

    monkeypatch.setattr(import_api.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(import_api, "import_data", fake_import_data)
    monkeypatch.setattr(import_api, "run_post_streaming_import_maintenance", fake_maintenance)

    response = client.post("/api/import/streaming")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/api/import/status/{job_id}").json()
    assert events == [("import", False), ("maintenance", None)]
    assert status["status"] == "done"
    assert status["result"]["maintenance_status"] == "ok"
    assert status["result"]["album_projects_rebuilt"] is True
```

- [ ] **Step 5.2: Create the service**

Create `backend/services/import_maintenance_service.py`:

```python
from __future__ import annotations

from typing import Any

from backend.core.cache_manager import invalidate_all
from backend.core.db import build_aggregations, get_db
from backend.domains.metadata.import_health import build_import_health_report
from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata
from backend.domains.playback.album_projects import rebuild_album_projects
from backend.providers.spotify.client import SpotifyProvider


def _scaled_progress(progress_callback, message: str, pct: float) -> None:
    if progress_callback:
        progress_callback(message, pct)


def run_post_streaming_import_maintenance(progress_callback=None) -> dict[str, Any]:
    conn = get_db(readonly=False)
    try:
        provider = SpotifyProvider()
        token = provider.get_cc_token()

        _scaled_progress(progress_callback, "刷新 Spotify 元数据...", 0.72)
        metadata_report = refresh_missing_spotify_metadata(
            conn,
            provider=provider,
            access_token=token,
            progress_callback=lambda msg, _pct: _scaled_progress(progress_callback, msg, 0.76),
        )

        _scaled_progress(progress_callback, "重建 album projects...", 0.84)
        rebuild_album_projects(conn)

        _scaled_progress(progress_callback, "重建 Billboard 预聚合...", 0.9)
        agg_results = build_aggregations(
            min_ms=30000,
            music_only=True,
            week_start_dow=4,
            week_start_hour=0,
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
        )

        _scaled_progress(progress_callback, "核验导入派生数据...", 0.96)
        health = build_import_health_report(conn)
        invalidate_all()

        status = "ok"
        if not metadata_report.provider_available or metadata_report.errors:
            status = "partial"
        if health["unresolved_recent_tracks"] or health["unresolved_recent_albums"]:
            status = "partial"

        return {
            "maintenance_status": status,
            "tracks_metadata_requested": metadata_report.tracks_requested,
            "tracks_metadata_updated": metadata_report.tracks_updated,
            "albums_metadata_requested": metadata_report.albums_requested,
            "albums_metadata_updated": metadata_report.albums_updated,
            "metadata_errors": list(metadata_report.errors),
            "album_projects_rebuilt": True,
            "agg_track_wks": agg_results.get("tracks", 0),
            "agg_album_wks": agg_results.get("albums", 0),
            "agg_artist_wks": agg_results.get("artists", 0),
            **health,
        }
    finally:
        conn.close()
```

- [ ] **Step 5.3: Wire Import API**

In `backend/api/import_.py`, import:

```python
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance
```

Change streaming import run block:

```python
result = import_data(progress_callback=cb, build_preaggregations=False)
maintenance = run_post_streaming_import_maintenance(progress_callback=cb)
```

Set result:

```python
_jobs[job_id]["result"] = {
    "records": result.get("total_records", result.get("records", 0)),
    "artists": result.get("unique_artists", result.get("artists", 0)),
    "albums": result.get("unique_albums", result.get("albums", 0)),
    "tracks": result.get("unique_tracks", result.get("tracks", 0)),
    "files": result.get("files_imported", result.get("files", 0)),
    **maintenance,
}
```

- [ ] **Step 5.4: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_import_api_jobs.py -q
```

Expected: PASS.

---

## Task 6: Add Import Health Report

**Files:**

- Create: `backend/domains/metadata/import_health.py`
- Test: `backend/tests/unit/test_import_health.py`

- [ ] **Step 6.1: Write report test**

Create `backend/tests/unit/test_import_health.py` with a minimal in-memory DB asserting the report returns stable keys:

```python
from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def test_import_health_report_counts_recent_missing_metadata():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(play_id INTEGER PRIMARY KEY, ts_date TEXT, content_type TEXT,
                           track_id INTEGER, source_album_id INTEGER);
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY, spotify_album_id TEXT);
        CREATE TABLE spotify_album_meta(spotify_album_id TEXT PRIMARY KEY, image_url TEXT);
        CREATE TABLE album_project_tracks(track_id INTEGER);
        CREATE TABLE album_project_albums(album_id INTEGER);
        INSERT INTO plays VALUES (1, '2026-06-01', 'audio', 1, 10);
        INSERT INTO tracks VALUES (1, 'track-a');
        """
    )

    report = build_import_health_report(conn, since_date="2026-05-13")

    assert report["recent_tracks"] == 1
    assert report["recent_source_albums"] == 1
    assert report["unresolved_recent_tracks"] == 1
    assert report["unresolved_recent_albums"] == 1
```

- [ ] **Step 6.2: Implement report**

Create `backend/domains/metadata/import_health.py`:

```python
from __future__ import annotations

import sqlite3


def build_import_health_report(
    conn: sqlite3.Connection,
    since_date: str = "2026-05-13",
) -> dict[str, int]:
    row = conn.execute(
        """
        WITH recent_plays AS (
          SELECT p.play_id, p.track_id, p.source_album_id
          FROM plays p
          WHERE p.ts_date > ?
            AND p.content_type = 'audio'
            AND p.track_id IS NOT NULL
        ),
        recent_tracks AS (
          SELECT DISTINCT track_id FROM recent_plays
        ),
        recent_albums AS (
          SELECT DISTINCT source_album_id AS album_id
          FROM recent_plays
          WHERE source_album_id IS NOT NULL
        )
        SELECT
          (SELECT COUNT(*) FROM recent_plays) AS recent_plays,
          (SELECT COUNT(*) FROM recent_tracks) AS recent_tracks,
          (SELECT COUNT(*) FROM recent_albums) AS recent_source_albums,
          (SELECT COUNT(*)
             FROM recent_tracks rt
             JOIN tracks t ON t.track_id = rt.track_id
             LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = t.spotify_track_id
             LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = stm.spotify_album_id
            WHERE stm.spotify_track_id IS NULL OR sam.spotify_album_id IS NULL
               OR COALESCE(sam.image_url, '') = '') AS unresolved_recent_tracks,
          (SELECT COUNT(*)
             FROM recent_albums ra
             LEFT JOIN album_project_albums apa ON apa.album_id = ra.album_id
            WHERE apa.album_id IS NULL) AS unresolved_recent_albums
        """,
        (since_date,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}
```

- [ ] **Step 6.3: Verify**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_import_health.py -q
```

Expected: PASS.

---

## Task 7: Add Repair Script For Current Database

**Files:**

- Create: `scripts/refresh_import_derived_data.py`
- Test: `backend/tests/unit/test_refresh_import_derived_data_script.py`

- [ ] **Step 7.1: Write CLI smoke test**

Create `backend/tests/unit/test_refresh_import_derived_data_script.py`:

```python
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_refresh_import_derived_data_writes_json_report(tmp_path, monkeypatch):
    from scripts import refresh_import_derived_data as script

    output = tmp_path / "report.json"

    monkeypatch.setattr(
        script,
        "run_post_streaming_import_maintenance",
        lambda progress_callback=None: {"maintenance_status": "ok", "unresolved_recent_tracks": 0},
    )

    exit_code = script.main(["--json-output", str(output)])

    assert exit_code == 0
    assert json.loads(output.read_text())["maintenance_status"] == "ok"
```

- [ ] **Step 7.2: Implement CLI**

Create `scripts/refresh_import_derived_data.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.import_maintenance_service import run_post_streaming_import_maintenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh derived data after Spotify import")
    parser.add_argument("--json-output", help="Write machine-readable report")
    args = parser.parse_args(argv)

    report = run_post_streaming_import_maintenance(
        progress_callback=lambda message, pct: print(f"[{pct:.0%}] {message}")
    )
    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("maintenance_status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7.3: Verify script**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_refresh_import_derived_data_script.py -q
.venv/bin/python scripts/refresh_import_derived_data.py --json-output /tmp/spotify_import_maintenance.json
```

Expected: test PASS; script emits JSON. On a machine without Spotify credentials, `maintenance_status` may be `partial` but the script should not crash.

---

## Task 8: Frontend Settings Import Result Surface

**Files:**

- Modify: `frontend/src/features/settings/components/DataImportSection.tsx` or the current import panel component
- Modify: `frontend/src/types/generated` only if OpenAPI generation is part of the workflow
- Test: existing Settings tests if present

- [ ] **Step 8.1: Display maintenance status from import result**

When the import job result contains `maintenance_status`, render:

- `ok`: `派生数据已同步`
- `partial`: `播放数据已导入，部分 Spotify 元数据待补全`
- `error`: `派生数据维护失败`

Render counts for:

- `tracks_metadata_updated`
- `albums_metadata_updated`
- `unresolved_recent_tracks`
- `unresolved_recent_albums`

- [ ] **Step 8.2: Avoid hard failure copy for partial metadata**

Use copy that distinguishes raw import success from derived metadata gaps:

```tsx
const maintenanceText =
  result.maintenance_status === 'partial'
    ? '播放记录已可用于基础统计；部分新歌/新专辑的封面或 album project 关系仍待补全。'
    : '播放记录、元数据和派生统计已完成同步。'
```

- [ ] **Step 8.3: Verify frontend**

Run:

```bash
cd frontend && npm test -- --run
cd frontend && npm run build
```

Expected: PASS.

---

## Task 9: Documentation Sync

**Files:**

- Modify: `data/README.md`
- Modify: `docs/playback-stats/rules.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `backend/CLAUDE.md`

- [ ] **Step 9.1: Update `data/README.md` import flow**

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

- [ ] **Step 9.2: Update rules docs**

Add a short section to `docs/playback-stats/rules.md`:

```markdown
### Import-Time Derived Data Maintenance

Streaming import writes raw playback facts first. A post-import maintenance pass then refreshes missing Spotify metadata, records play-time Spotify album ids, rebuilds album projects, and rebuilds Billboard preaggregations. Album project bootstrap must prefer play-time Spotify album evidence over name-only album metadata, so a same-name single cannot prevent a later full album from entering album statistics.
```

- [ ] **Step 9.3: Update prompt files**

Add the same fact to `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md`: import completion now means raw play import plus derived maintenance, with partial status when external Spotify metadata is unavailable.

---

## Task 10: Current Database Repair And Verification

**Files:**

- No code changes if earlier tasks are complete.
- Output: `/tmp/spotify_import_maintenance.json`

- [ ] **Step 10.1: Back up the DB**

Run:

```bash
cp data/spotify_stats.db /tmp/spotify_stats_before_import_maintenance_2026-06-24.db
```

- [ ] **Step 10.2: Re-import full Streaming History if migration cannot backfill play-time IDs**

Because old `plays` rows do not contain exact play-time Spotify track ids, the strongest repair is to re-run import from the full JSON folder after Task 2 ships.

Run through the Settings UI or:

```bash
.venv/bin/python - <<'PY'
from backend.core.import_data import import_data
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance

import_data(build_preaggregations=False)
print(run_post_streaming_import_maintenance())
PY
```

- [ ] **Step 10.3: Run health probes**

Run:

```bash
sqlite3 data/spotify_stats.db <<'SQL'
.headers on
.mode column
WITH recent_plays AS (
  SELECT p.play_id, p.track_id, p.source_album_id
  FROM plays p
  WHERE p.ts_date > '2026-05-13' AND p.content_type = 'audio' AND p.track_id IS NOT NULL
),
recent_tracks AS (
  SELECT DISTINCT track_id FROM recent_plays
),
recent_albums AS (
  SELECT DISTINCT source_album_id AS album_id FROM recent_plays WHERE source_album_id IS NOT NULL
)
SELECT
  (SELECT COUNT(*) FROM recent_tracks) AS recent_tracks,
  (SELECT COUNT(*) FROM recent_tracks rt JOIN tracks t ON t.track_id = rt.track_id LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = t.spotify_track_id WHERE stm.spotify_track_id IS NULL) AS missing_track_meta,
  (SELECT COUNT(*) FROM recent_tracks rt JOIN tracks t ON t.track_id = rt.track_id LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = t.spotify_track_id LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = stm.spotify_album_id WHERE COALESCE(sam.image_url, '') = '') AS missing_cover,
  (SELECT COUNT(*) FROM recent_albums ra LEFT JOIN album_project_albums apa ON apa.album_id = ra.album_id WHERE apa.album_id IS NULL) AS missing_album_projects;
SQL
```

Expected after successful online maintenance:

- `missing_track_meta = 0`, except tracks Spotify no longer returns.
- `missing_cover = 0`, except albums Spotify returns without images.
- `missing_album_projects` should drop materially from the current `145` and should not include LP/EP-sized local albums like `Dinner Party`.

- [ ] **Step 10.4: Run backend verification**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py backend/tests/unit/test_spotify_metadata_refresh.py backend/tests/unit/test_import_health.py backend/tests/unit/test_migrations.py -q
.venv/bin/pytest backend/tests/contract/test_import_api_jobs.py backend/tests/contract/test_album_project_import_maintenance.py backend/tests/contract/test_album_project_rules.py -q
ruff check backend/
```

Expected: PASS.

- [ ] **Step 10.5: Run product verification**

Run:

```bash
.venv/bin/python scripts/api_smoke_probe.py
.venv/bin/python scripts/api_boundary_probe.py
cd frontend && npm run build
```

Expected: PASS.

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
