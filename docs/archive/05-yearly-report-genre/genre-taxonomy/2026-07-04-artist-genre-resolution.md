# Artist Genre Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable artist-genre resolution layer so Spotify genre metadata remains the first source, but local curated, open-data, and AI-assisted genres fill gaps without corrupting Spotify raw metadata.

**Architecture:** Keep `spotify_artist_meta.genres` as raw Spotify metadata, add separate source and override tables for non-Spotify genres, and expose a resolver API used by yearly review, AI reports, account insights, and artist detail. A background AI task can propose genre candidates, but statistics only consume approved or trusted records with explicit source, confidence, and evidence.

**Tech Stack:** FastAPI, SQLite migrations, pandas, existing `providers/` + `HttpClient`, existing `ai_task_runs/events/tool_calls`, existing LLM provider config, React Query, Vitest, pytest unit/contract tests.

---

## Current Problem

Current yearly genre statistics read `spotify_artist_meta.genres`. In the local database, many high-play artists have empty Spotify genres, including major artists such as Taylor Swift and Olivia Rodrigo. A quick local probe showed roughly half of all main-artist play hours fall into missing genre rows, so the current "其他流派" bucket is too large and the AI report must over-caveat genre/language claims.

The fix must preserve evidence boundaries:

- Do not overwrite Spotify raw data with AI-generated data.
- Do not treat all genre labels as mutually exclusive categories.
- Do not use a single global genre distribution as proof that an individual artist belongs to a language or regional category.
- Do make every non-Spotify genre auditable by source, confidence, and evidence.

---

## Scope And Non-Goals

In scope:

- Add durable local genre source tables and a resolver.
- Add a focused curated seed file for high-play missing artists.
- Route yearly review, AI reports, account collection insights, artist detail, and Billboard versus metadata through the resolver.
- Add a background AI task to generate suggested genre records for missing high-play artists.
- Add optional providers for Last.fm, MusicBrainz, and Wikidata behind the existing provider layer.
- Add coverage diagnostics so the app can report genre coverage by play hours.

Out of scope for the first implementation:

- A full manual admin UI for editing every artist.
- Track-level genre classification.
- Rewriting playback counting rules, Billboard ranking, or merge-level semantics.
- Treating AI-generated genres as trusted without approval or evidence.
- Backfilling album genres, because current `spotify_album_meta.genres` coverage is effectively empty and artist-level genre is the product's active path.

---

## File Map

### Schema And Domain Layer

- Modify: `backend/core/db.py`
  - Add fresh-DB schema for local artist genre source, override, and review tables.
- Modify: `backend/core/migrations.py`
  - Add migration 23 after `ai_task_runs_events_tool_calls`.
- Create: `backend/domains/metadata/artist_genres.py`
  - Normalize genres, rank sources, resolve final genres, compute coverage diagnostics, and upsert curated/proposed records.
- Create: `backend/tests/unit/test_artist_genre_resolution.py`
  - Lock source priority, fallback behavior, coverage math, and normalization.
- Modify: `backend/tests/unit/test_migrations.py`
  - Verify migration 23 creates required tables and indexes.

### Data Seeds And Maintenance

- Create: `data/artist_genre_overrides.seed.json`
  - Store reviewed high-impact seed records, initially focused on top missing play-hour artists.
- Create: `scripts/import_artist_genre_overrides.py`
  - Import the seed file into SQLite with a dry-run and JSON output mode.
- Create: `scripts/artist_genre_coverage_probe.py`
  - Report missing genre coverage by play hours and top missing artists.
- Modify: `backend/services/import_maintenance_service.py`
  - Include genre coverage in maintenance output after metadata refresh.

### Providers And AI Task

- Create: `backend/providers/lastfm/client.py`
  - Fetch artist top tags through Last.fm when an API key is configured.
- Create: `backend/providers/musicbrainz/client.py`
  - Search artist and fetch genres/tags with polite rate limiting.
- Create: `backend/providers/wikidata/client.py`
  - Query artist genre and occupation-style metadata with SPARQL.
- Modify: `backend/services/ai_task_service.py`
  - Add `artist_genre_backfill` task handler and progress stages.
- Modify: `backend/api/ai_tasks.py`
  - Add POST `/api/ai/tasks/metadata/artist-genres`.
- Modify: `backend/models/ai_tasks.py`
  - Add request/response models for genre backfill.
- Create: `backend/services/artist_genre_backfill_service.py`
  - Select missing high-weight artists, gather evidence, call LLM for suggestions, persist suggestions, and emit tool-call traces.
- Create: `backend/tests/contract/test_artist_genre_backfill_task.py`
  - Verify task status, events, tool calls, and non-destructive writes.

### Consumers

- Modify: `backend/services/wrapped_service.py`
  - Replace direct `spotify_artist_meta.genres` reads with the resolver.
- Modify: `backend/services/ai_insights_service.py`
  - Include `genre_source_summary` and improved caveat in yearly report data.
- Modify: `backend/domains/ai_reports/yearly_contract.py`
  - Carry source quality and coverage caveats.
- Modify: `backend/domains/ai_reports/agentic_tools.py`
  - Make `genre_distribution` expose coverage and source mix.
- Modify: `backend/services/account_service.py`
  - Use resolved genres for collection genre migration.
- Modify: `backend/domains/billboard/details.py`
  - Use resolved genres in artist metadata response.
- Modify: `backend/domains/billboard/versus.py`
  - Use resolved genres in artist comparison metadata.
- Create: `backend/tests/contract/test_artist_genre_consumers.py`
  - Verify wrapped, account, and detail consumers use local fallback when Spotify is empty.

### Frontend And Docs

- Modify: `frontend/src/features/music/details/ArtistCareerSection.tsx`
  - Show genre source quality for artist detail when available.
- Modify: `frontend/src/pages/yearly-review/GenrePanorama.tsx`
  - Add small caveat text for source coverage and non-exclusive labels.
- Modify: `frontend/src/features/ai-tasks/AITaskProgress.tsx`
  - Add labels for genre backfill task stages.
- Modify: `docs/playback-stats/rules.md`
  - Document genre resolution semantics.
- Modify: `data/README.md`
  - Document the seed file and source priority.
- Modify: `README.md`, `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md`, `docs/README.md`, `docs/CHANGELOG.md`
  - Update durable project contracts after implementation.

---

## Data Model

Migration 23 should create three tables:

```sql
CREATE TABLE IF NOT EXISTS artist_genre_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL,
    spotify_artist_id TEXT,
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    raw_genres_json TEXT,
    normalized_genres_json TEXT NOT NULL,
    primary_genre TEXT,
    language TEXT,
    region TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence_url TEXT,
    evidence_summary TEXT,
    status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(artist_name, source, source_key)
);

CREATE INDEX IF NOT EXISTS idx_artist_genre_sources_artist
ON artist_genre_sources(artist_name, status, confidence);

CREATE TABLE IF NOT EXISTS artist_genre_overrides (
    artist_name TEXT PRIMARY KEY,
    normalized_genres_json TEXT NOT NULL,
    primary_genre TEXT,
    language TEXT,
    region TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    note TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artist_genre_review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL,
    play_hours REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    suggested_source_id INTEGER REFERENCES artist_genre_sources(source_id),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Resolution priority:

1. Non-empty Spotify genres from `spotify_artist_meta.genres`.
2. Manual override from `artist_genre_overrides`, used only when Spotify has no genre.
3. Approved local source rows from `artist_genre_sources`, ordered by source priority and confidence.
4. No genre: counted as unknown, then represented as "其他流派" only at aggregate output time.

Source priority within step 3:

```python
SOURCE_PRIORITY = {
    "curated_seed": 95,
    "external_consensus": 85,
    "musicbrainz": 80,
    "lastfm": 75,
    "wikidata": 70,
    "llm": 55,
}
```

AI rows start as `status='suggested'` unless they cite at least two non-LLM evidence sources. Only `approved` rows feed statistics.

---

## Task 1: Add Genre Resolution Schema

**Files:**

- Modify: `backend/core/db.py`
- Modify: `backend/core/migrations.py`
- Modify: `backend/tests/unit/test_migrations.py`

- [ ] **Step 1.1: Write the migration test**

Add this test to `backend/tests/unit/test_migrations.py`:

```python
def test_migration_023_adds_artist_genre_resolution_tables(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import migrations

    db_path = tmp_path / "spotify_stats.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    db_mod.init_db()
    migrations.run_migrations()

    conn = db_mod.get_db(readonly=True)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "artist_genre_sources" in tables
        assert "artist_genre_overrides" in tables
        assert "artist_genre_review_queue" in tables

        source_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(artist_genre_sources)").fetchall()
        }
        assert {
            "artist_name",
            "source",
            "normalized_genres_json",
            "confidence",
            "status",
            "evidence_summary",
        } <= source_columns

        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_artist_genre_sources_artist" in indexes
    finally:
        conn.close()
```

- [ ] **Step 1.2: Run the focused test and verify it fails**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_migrations.py::test_migration_023_adds_artist_genre_resolution_tables -q
```

Expected: FAIL because the tables do not exist.

- [ ] **Step 1.3: Add schema to fresh DBs**

In `backend/core/db.py`, add the three tables and indexes from the "Data Model" section after `spotify_artist_meta`.

- [ ] **Step 1.4: Add migration 23**

In `backend/core/migrations.py`, add:

```python
@migration(23, "artist_genre_resolution")
def migrate_023(conn: sqlite3.Connection):
    """Persist local artist genre sources, overrides, and review queue."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            raw_genres_json TEXT,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_url TEXT,
            evidence_summary TEXT,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_name, source, source_key)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_genre_sources_artist "
        "ON artist_genre_sources(artist_name, status, confidence)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_overrides (
            artist_name TEXT PRIMARY KEY,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_review_queue (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            play_hours REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            suggested_source_id INTEGER REFERENCES artist_genre_sources(source_id),
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
```

- [ ] **Step 1.5: Run the migration test**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_migrations.py::test_migration_023_adds_artist_genre_resolution_tables -q
```

Expected: PASS.

- [ ] **Step 1.6: Commit**

```bash
git add backend/core/db.py backend/core/migrations.py backend/tests/unit/test_migrations.py
git commit -m "feat: add artist genre resolution schema"
```

---

## Task 2: Implement The Resolver

**Files:**

- Create: `backend/domains/metadata/artist_genres.py`
- Create: `backend/tests/unit/test_artist_genre_resolution.py`

- [ ] **Step 2.1: Write resolver tests**

Create `backend/tests/unit/test_artist_genre_resolution.py`:

```python
import json
import sqlite3

from backend.domains.metadata.artist_genres import (
    compute_genre_coverage,
    normalize_genres,
    resolve_artist_genres,
    resolve_artist_genres_map,
    upsert_genre_source,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE spotify_artist_meta (
            spotify_artist_id TEXT PRIMARY KEY,
            artist_name TEXT NOT NULL,
            popularity INTEGER,
            followers INTEGER,
            genres TEXT,
            image_url TEXT
        );
        CREATE TABLE artist_genre_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            raw_genres_json TEXT,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_url TEXT,
            evidence_summary TEXT,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_name, source, source_key)
        );
        CREATE TABLE artist_genre_overrides (
            artist_name TEXT PRIMARY KEY,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    return conn


def test_normalize_genres_dedupes_and_keeps_order():
    assert normalize_genres(["Pop", "pop", "Singer-Songwriter", "", None]) == [
        "pop",
        "singer-songwriter",
    ]


def test_resolver_prefers_manual_override_then_spotify_then_local_source():
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Taylor Swift", json.dumps(["pop"], ensure_ascii=False)),
    )
    conn.execute(
        """INSERT INTO artist_genre_overrides
           (artist_name, normalized_genres_json, primary_genre, language, region, confidence, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "Taylor Swift",
            json.dumps(["pop", "country pop"], ensure_ascii=False),
            "pop",
            "english",
            "美国",
            1.0,
            "manual seed",
        ),
    )
    conn.commit()

    resolved = resolve_artist_genres(conn, "Taylor Swift")

    assert resolved.genres == ["pop", "country pop"]
    assert resolved.source == "manual_override"
    assert resolved.confidence == 1.0


def test_resolver_uses_approved_local_source_when_spotify_empty():
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp2", "Olivia Rodrigo", ""),
    )
    upsert_genre_source(
        conn,
        artist_name="Olivia Rodrigo",
        spotify_artist_id="sp2",
        source="curated_seed",
        source_key="seed:olivia-rodrigo",
        raw_genres=["pop", "alt z"],
        normalized_genres=["pop", "alt z"],
        primary_genre="pop",
        language="english",
        region="美国",
        confidence=0.95,
        evidence_url="https://example.test/olivia",
        evidence_summary="Curated from artist profile.",
        status="approved",
    )

    resolved = resolve_artist_genres(conn, "Olivia Rodrigo")

    assert resolved.genres == ["pop", "alt z"]
    assert resolved.source == "curated_seed"
    assert resolved.is_fallback is True


def test_suggested_llm_rows_do_not_feed_statistics():
    conn = _conn()
    upsert_genre_source(
        conn,
        artist_name="Unknown Artist",
        spotify_artist_id=None,
        source="llm",
        source_key="llm:unknown",
        raw_genres=["pop"],
        normalized_genres=["pop"],
        primary_genre="pop",
        language="english",
        region="全球",
        confidence=0.70,
        evidence_url=None,
        evidence_summary="LLM suggestion only.",
        status="suggested",
    )

    resolved = resolve_artist_genres(conn, "Unknown Artist")

    assert resolved.genres == []
    assert resolved.source == "unknown"


def test_resolve_artist_genres_map_batches_names():
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Known", json.dumps(["rock"], ensure_ascii=False)),
    )
    result = resolve_artist_genres_map(conn, ["Known", "Missing"])
    assert result["Known"].genres == ["rock"]
    assert result["Missing"].genres == []


def test_compute_genre_coverage_by_play_hours():
    conn = _conn()
    conn.execute(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, genres) VALUES (?, ?, ?)",
        ("sp1", "Known", json.dumps(["rock"], ensure_ascii=False)),
    )
    coverage = compute_genre_coverage(conn, {"Known": 10.0, "Missing": 30.0})
    assert coverage["known_hours"] == 10.0
    assert coverage["unknown_hours"] == 30.0
    assert coverage["known_pct"] == 25.0
    assert coverage["top_missing"][0]["artist_name"] == "Missing"
```

- [ ] **Step 2.2: Run the tests and verify they fail**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_resolution.py -q
```

Expected: FAIL because `backend.domains.metadata.artist_genres` does not exist.

- [ ] **Step 2.3: Implement resolver module**

Create `backend/domains/metadata/artist_genres.py` with:

```python
"""Artist genre resolution across Spotify, curated, external, and AI sources."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

SOURCE_PRIORITY = {
    "curated_seed": 95,
    "musicbrainz": 80,
    "lastfm": 75,
    "wikidata": 70,
    "llm": 55,
}


@dataclass(frozen=True)
class ResolvedArtistGenres:
    artist_name: str
    genres: list[str]
    primary_genre: str | None
    language: str | None
    region: str | None
    source: str
    confidence: float
    evidence_url: str | None = None
    evidence_summary: str | None = None
    is_fallback: bool = False


def normalize_genres(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = [part.strip() for part in str(raw).split(",")]
    return normalize_genres(value if isinstance(value, list) else [])


def upsert_genre_source(
    conn: sqlite3.Connection,
    *,
    artist_name: str,
    spotify_artist_id: str | None,
    source: str,
    source_key: str,
    raw_genres: list[str],
    normalized_genres: list[str],
    primary_genre: str | None,
    language: str | None,
    region: str | None,
    confidence: float,
    evidence_url: str | None,
    evidence_summary: str | None,
    status: str = "approved",
) -> None:
    conn.execute(
        """INSERT INTO artist_genre_sources(
               artist_name, spotify_artist_id, source, source_key,
               raw_genres_json, normalized_genres_json, primary_genre,
               language, region, confidence, evidence_url, evidence_summary,
               status, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(artist_name, source, source_key) DO UPDATE SET
               spotify_artist_id = excluded.spotify_artist_id,
               raw_genres_json = excluded.raw_genres_json,
               normalized_genres_json = excluded.normalized_genres_json,
               primary_genre = excluded.primary_genre,
               language = excluded.language,
               region = excluded.region,
               confidence = excluded.confidence,
               evidence_url = excluded.evidence_url,
               evidence_summary = excluded.evidence_summary,
               status = excluded.status,
               updated_at = datetime('now')""",
        (
            artist_name,
            spotify_artist_id,
            source,
            source_key,
            json.dumps(raw_genres, ensure_ascii=False),
            json.dumps(normalize_genres(normalized_genres), ensure_ascii=False),
            primary_genre,
            language,
            region,
            float(confidence),
            evidence_url,
            evidence_summary,
            status,
        ),
    )
    conn.commit()


def resolve_artist_genres(conn: sqlite3.Connection, artist_name: str) -> ResolvedArtistGenres:
    override = conn.execute(
        "SELECT * FROM artist_genre_overrides WHERE artist_name = ?",
        (artist_name,),
    ).fetchone()
    if override:
        genres = _loads_list(override["normalized_genres_json"])
        return ResolvedArtistGenres(
            artist_name=artist_name,
            genres=genres,
            primary_genre=override["primary_genre"] or (genres[0] if genres else None),
            language=override["language"],
            region=override["region"],
            source="manual_override",
            confidence=float(override["confidence"] or 1.0),
            evidence_summary=override["note"],
            is_fallback=False,
        )

    spotify = conn.execute(
        "SELECT spotify_artist_id, genres FROM spotify_artist_meta WHERE artist_name = ? LIMIT 1",
        (artist_name,),
    ).fetchone()
    spotify_genres = _loads_list(spotify["genres"] if spotify else None)
    if spotify_genres:
        return ResolvedArtistGenres(
            artist_name=artist_name,
            genres=spotify_genres,
            primary_genre=spotify_genres[0],
            language=None,
            region=None,
            source="spotify",
            confidence=1.0,
            is_fallback=False,
        )

    rows = conn.execute(
        """SELECT *
           FROM artist_genre_sources
           WHERE artist_name = ? AND status = 'approved'
           ORDER BY confidence DESC, source_id DESC""",
        (artist_name,),
    ).fetchall()
    if rows:
        best = sorted(
            rows,
            key=lambda row: (SOURCE_PRIORITY.get(row["source"], 0), float(row["confidence"] or 0)),
            reverse=True,
        )[0]
        genres = _loads_list(best["normalized_genres_json"])
        return ResolvedArtistGenres(
            artist_name=artist_name,
            genres=genres,
            primary_genre=best["primary_genre"] or (genres[0] if genres else None),
            language=best["language"],
            region=best["region"],
            source=best["source"],
            confidence=float(best["confidence"] or 0),
            evidence_url=best["evidence_url"],
            evidence_summary=best["evidence_summary"],
            is_fallback=True,
        )

    return ResolvedArtistGenres(
        artist_name=artist_name,
        genres=[],
        primary_genre=None,
        language=None,
        region=None,
        source="unknown",
        confidence=0.0,
        is_fallback=True,
    )


def resolve_artist_genres_map(
    conn: sqlite3.Connection,
    artist_names: list[str],
) -> dict[str, ResolvedArtistGenres]:
    return {name: resolve_artist_genres(conn, name) for name in dict.fromkeys(artist_names)}


def compute_genre_coverage(conn: sqlite3.Connection, artist_hours: dict[str, float]) -> dict[str, Any]:
    resolved = resolve_artist_genres_map(conn, list(artist_hours))
    known_hours = 0.0
    unknown_hours = 0.0
    top_missing: list[dict[str, Any]] = []
    source_hours: dict[str, float] = {}
    for artist_name, hours in artist_hours.items():
        item = resolved[artist_name]
        if item.genres:
            known_hours += float(hours)
            source_hours[item.source] = source_hours.get(item.source, 0.0) + float(hours)
        else:
            unknown_hours += float(hours)
            top_missing.append({"artist_name": artist_name, "hours": round(float(hours), 1)})
    total = known_hours + unknown_hours
    top_missing.sort(key=lambda row: row["hours"], reverse=True)
    return {
        "known_hours": round(known_hours, 1),
        "unknown_hours": round(unknown_hours, 1),
        "known_pct": round(known_hours / total * 100, 1) if total else 0.0,
        "unknown_pct": round(unknown_hours / total * 100, 1) if total else 0.0,
        "source_hours": {key: round(value, 1) for key, value in source_hours.items()},
        "top_missing": top_missing[:20],
    }
```

- [ ] **Step 2.4: Run resolver tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_resolution.py -q
```

Expected: PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/domains/metadata/artist_genres.py backend/tests/unit/test_artist_genre_resolution.py
git commit -m "feat: resolve artist genres from trusted sources"
```

---

## Task 3: Add Seed Import And Coverage Probe

**Files:**

- Create: `data/artist_genre_overrides.seed.json`
- Create: `scripts/import_artist_genre_overrides.py`
- Create: `scripts/artist_genre_coverage_probe.py`
- Test: `backend/tests/unit/test_artist_genre_seed_import.py`

- [ ] **Step 3.1: Create seed file**

Create `data/artist_genre_overrides.seed.json` with a small high-impact seed. Keep it conservative:

```json
[
  {
    "artist_name": "Taylor Swift",
    "spotify_artist_id": null,
    "source": "curated_seed",
    "source_key": "seed:taylor-swift",
    "genres": ["pop", "country pop", "singer-songwriter"],
    "primary_genre": "pop",
    "language": "english",
    "region": "美国",
    "confidence": 0.95,
    "evidence_url": "https://en.wikipedia.org/wiki/Taylor_Swift",
    "evidence_summary": "High-play artist with empty Spotify genres in local DB; seed uses broad public artist profile genres.",
    "status": "approved"
  },
  {
    "artist_name": "Olivia Rodrigo",
    "spotify_artist_id": null,
    "source": "curated_seed",
    "source_key": "seed:olivia-rodrigo",
    "genres": ["pop", "pop rock", "alt z"],
    "primary_genre": "pop",
    "language": "english",
    "region": "美国",
    "confidence": 0.90,
    "evidence_url": "https://en.wikipedia.org/wiki/Olivia_Rodrigo",
    "evidence_summary": "High-play artist with empty Spotify genres in local DB; seed uses broad public artist profile genres.",
    "status": "approved"
  }
]
```

- [ ] **Step 3.2: Write seed import tests**

Create `backend/tests/unit/test_artist_genre_seed_import.py` to exercise the script with a temp database and assert inserted source rows can be resolved.

- [ ] **Step 3.3: Implement import script**

Create `scripts/import_artist_genre_overrides.py` with:

- `--seed data/artist_genre_overrides.seed.json`
- `--dry-run`
- `--json-output /tmp/artist_genre_seed_import.json`
- imports rows through `upsert_genre_source()`
- prints counts: `loaded`, `approved`, `suggested`, `dry_run`

- [ ] **Step 3.4: Implement coverage probe**

Create `scripts/artist_genre_coverage_probe.py` that:

- loads play hours by artist using the same main-artist join as the current rough probe
- calls `compute_genre_coverage()`
- writes JSON when `--json-output` is supplied
- exits non-zero only when `--max-unknown-pct` is supplied and exceeded

Command:

```bash
source .venv/bin/activate && .venv/bin/python scripts/artist_genre_coverage_probe.py --json-output /tmp/spotify_artist_genre_coverage.json
```

Expected JSON keys: `known_pct`, `unknown_pct`, `source_hours`, `top_missing`.

- [ ] **Step 3.5: Run tests and dry-run**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_seed_import.py backend/tests/unit/test_artist_genre_resolution.py -q
source .venv/bin/activate && .venv/bin/python scripts/import_artist_genre_overrides.py --dry-run --json-output /tmp/artist_genre_seed_import.json
source .venv/bin/activate && .venv/bin/python scripts/artist_genre_coverage_probe.py --json-output /tmp/spotify_artist_genre_coverage.json
```

Expected: pytest PASS, dry-run writes JSON with `dry_run: true`, coverage probe reports current unknown percentage.

- [ ] **Step 3.6: Commit**

```bash
git add data/artist_genre_overrides.seed.json scripts/import_artist_genre_overrides.py scripts/artist_genre_coverage_probe.py backend/tests/unit/test_artist_genre_seed_import.py
git commit -m "feat: add artist genre seed import and coverage probe"
```

---

## Task 4: Route Statistics Through The Resolver

**Files:**

- Modify: `backend/services/wrapped_service.py`
- Modify: `backend/services/account_service.py`
- Modify: `backend/domains/billboard/details.py`
- Modify: `backend/domains/billboard/versus.py`
- Create: `backend/tests/contract/test_artist_genre_consumers.py`

- [ ] **Step 4.1: Write consumer tests**

Create contract tests that seed:

- one artist with Spotify genre
- one artist with empty Spotify genre and approved curated fallback
- one artist with no genre

Assert:

- `get_wrapped_full(...).genre_panorama.top_genres` includes the curated fallback label.
- `get_wrapped_full(...).genre_panorama` still counts the unknown artist as "其他流派".
- artist detail metadata returns `genre_source` and `genre_confidence` when resolved through fallback.
- account collection genre migration uses fallback rows.

- [ ] **Step 4.2: Update `wrapped_service.py`**

Replace the direct batch query in `_build_genre_panorama()`, `_build_monthly_genres()`, `_calc_globetrotter_score()`, and `_build_music_map()` with `resolve_artist_genres_map()`.

Implementation rule:

```python
from backend.domains.metadata.artist_genres import compute_genre_coverage, resolve_artist_genres_map
```

When returning `genre_panorama`, include:

```python
"coverage": compute_genre_coverage(
    conn,
    {artist_name: float(row["hours"]) for artist_name, row in artist_agg.iterrows()},
),
"caveat": "Spotify 与本地补全流派标签可能重叠，百分比不互斥。",
```

- [ ] **Step 4.3: Update detail and versus metadata**

In `backend/domains/billboard/details.py` and `backend/domains/billboard/versus.py`, keep existing Spotify popularity/follower reads, but replace raw genre parsing with `resolve_artist_genres()`. Return:

```python
meta["genres"] = resolved.genres
meta["genre_source"] = resolved.source
meta["genre_confidence"] = resolved.confidence
```

- [ ] **Step 4.4: Update account service**

In `backend/services/account_service.py`, replace the direct join to `spotify_artist_meta.sam.genres` in genre migration with a two-step flow:

1. aggregate saved-track counts by year and artist
2. resolve artist genres in Python and accumulate counts

This keeps the resolver as the single source of truth.

- [ ] **Step 4.5: Run consumer tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_artist_genre_consumers.py -q
```

Expected: PASS.

- [ ] **Step 4.6: Run related wrapped tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/integration/test_wrapped_full.py backend/tests/unit/test_ai_insights_yearly_quality.py -q
```

Expected: PASS, with updated expected coverage/caveat keys where needed.

- [ ] **Step 4.7: Commit**

```bash
git add backend/services/wrapped_service.py backend/services/account_service.py backend/domains/billboard/details.py backend/domains/billboard/versus.py backend/tests/contract/test_artist_genre_consumers.py backend/tests/integration/test_wrapped_full.py backend/tests/unit/test_ai_insights_yearly_quality.py
git commit -m "feat: use resolved artist genres in statistics"
```

---

## Task 5: Add External Providers

**Files:**

- Create: `backend/providers/lastfm/client.py`
- Create: `backend/providers/musicbrainz/client.py`
- Create: `backend/providers/wikidata/client.py`
- Create: `backend/tests/unit/test_artist_genre_external_providers.py`

- [ ] **Step 5.1: Write provider tests with fake HTTP clients**

Tests should assert:

- Last.fm extracts top tag names from `artist.getinfo`.
- MusicBrainz extracts `genres` first, then falls back to counted `tags`.
- Wikidata extracts genre labels from SPARQL bindings.
- 429 and 5xx provider responses become structured provider failures or empty results without crashing the caller.

- [ ] **Step 5.2: Implement Last.fm provider**

Provider contract:

```python
class LastFmProvider(BaseProvider):
    def get_artist_tags(self, artist_name: str, api_key: str, limit: int = 8) -> list[dict[str, Any]]:
        ...
```

Do not add a settings UI in this task. Read `LASTFM_API_KEY` from environment first; the backfill service can skip Last.fm when absent.

- [ ] **Step 5.3: Implement MusicBrainz provider**

Provider contract:

```python
class MusicBrainzProvider(BaseProvider):
    def search_artist(self, artist_name: str, limit: int = 3) -> list[dict[str, Any]]:
        ...

    def get_artist_genres(self, mbid: str) -> dict[str, Any] | None:
        ...
```

Set a clear User-Agent through `HttpClient` headers if the shared client supports per-request headers; otherwise add a small method-level header path matching existing provider style.

- [ ] **Step 5.4: Implement Wikidata provider**

Provider contract:

```python
class WikidataProvider(BaseProvider):
    def get_artist_genres(self, artist_name: str, limit: int = 8) -> list[dict[str, Any]]:
        ...
```

Use SPARQL only for artist-name lookup and genre labels. Store the Wikidata entity URL as evidence URL.

- [ ] **Step 5.5: Run provider tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_external_providers.py -q
```

Expected: PASS.

- [ ] **Step 5.6: Commit**

```bash
git add backend/providers/lastfm backend/providers/musicbrainz backend/providers/wikidata backend/tests/unit/test_artist_genre_external_providers.py
git commit -m "feat: add artist genre external providers"
```

---

## Task 6: Add AI-Assisted Backfill Task

**Files:**

- Create: `backend/services/artist_genre_backfill_service.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/api/ai_tasks.py`
- Modify: `backend/models/ai_tasks.py`
- Create: `backend/tests/contract/test_artist_genre_backfill_task.py`

- [ ] **Step 6.1: Write task contract tests**

Use monkeypatches for providers and `_llm_chat()` so tests do not call the network or a real LLM.

Assertions:

- task type is `artist_genre_backfill`
- stages include `selecting_artists`, `fetching_external_data`, `calling_llm`, `saving_suggestions`, `done`
- tool calls record provider summaries
- rows from LLM are inserted with `status='suggested'`
- rows with two matching non-LLM sources can be inserted as `status='approved'`
- existing Spotify genres are skipped by default

- [ ] **Step 6.2: Implement selection logic**

Create a function:

```python
def select_missing_genre_artists(conn, *, limit: int = 50, min_hours: float = 1.0) -> list[dict[str, Any]]:
    ...
```

It should order by play hours descending and skip artists where `resolve_artist_genres()` already has genres.

- [ ] **Step 6.3: Implement evidence gathering**

Create:

```python
def gather_genre_evidence(artist_name: str) -> dict[str, Any]:
    ...
```

It should return keys `lastfm`, `musicbrainz`, `wikidata`, and `wikipedia_summary`. Missing provider config should return an empty list, not an error.

- [ ] **Step 6.4: Implement LLM suggestion parser**

LLM output must be strict JSON:

```json
{
  "genres": ["pop", "singer-songwriter"],
  "primary_genre": "pop",
  "language": "english",
  "region": "美国",
  "confidence": 0.82,
  "evidence_summary": "Last.fm and MusicBrainz both point to pop and singer-songwriter."
}
```

Reject rows when:

- `genres` is empty
- `confidence < 0.6`
- `evidence_summary` is empty
- output is not valid JSON

- [ ] **Step 6.5: Add ai task service entry**

Add to `backend/services/ai_task_service.py`:

```python
def start_artist_genre_backfill_task(request: dict[str, Any]) -> dict[str, Any]:
    from backend.services.artist_genre_backfill_service import run_artist_genre_backfill_task

    return create_task(
        task_type="artist_genre_backfill",
        stage="selecting_artists",
        message="准备补全艺人流派标签",
        request=request,
        handler=run_artist_genre_backfill_task,
    )
```

- [ ] **Step 6.6: Add API and models**

Add a request model:

```python
class ArtistGenreBackfillTaskRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    min_hours: float = Field(default=1.0, ge=0)
    include_ai: bool = True
    approve_high_confidence_external: bool = True
```

Add route:

```python
@router.post(
    "/metadata/artist-genres",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_artist_genre_backfill_task(body: ArtistGenreBackfillTaskRequest):
    return start_artist_genre_backfill_task(body.model_dump())
```

- [ ] **Step 6.7: Run task tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_artist_genre_backfill_task.py -q
```

Expected: PASS.

- [ ] **Step 6.8: Commit**

```bash
git add backend/services/artist_genre_backfill_service.py backend/services/ai_task_service.py backend/api/ai_tasks.py backend/models/ai_tasks.py backend/tests/contract/test_artist_genre_backfill_task.py
git commit -m "feat: add AI-assisted artist genre backfill task"
```

---

## Task 7: Surface Genre Coverage In Reports And UI

**Files:**

- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/domains/ai_reports/yearly_contract.py`
- Modify: `backend/domains/ai_reports/agentic_tools.py`
- Modify: `backend/domains/ai_reports/visual_chart_data.py`
- Modify: `frontend/src/pages/yearly-review/GenrePanorama.tsx`
- Modify: `frontend/src/features/music/details/ArtistCareerSection.tsx`
- Modify: `frontend/src/features/ai-tasks/AITaskProgress.tsx`
- Modify tests under `backend/tests/unit/` and `frontend/src/tests/`

- [ ] **Step 7.1: Backend report tests**

Extend yearly report tests to assert:

- `genre_summary.coverage.known_pct` exists
- caveat says local fallback may be included
- AI prompt constraints forbid treating genre percentages as mutually exclusive

- [ ] **Step 7.2: Frontend tests**

Extend yearly report and artist detail tests to assert:

- source/caveat text renders when coverage exists
- existing UI still works when older API payload lacks `coverage`
- task progress has a Chinese label for `artist_genre_backfill`

- [ ] **Step 7.3: Implement backend payload updates**

In `summarize_genres()`, accept optional coverage:

```python
def summarize_genres(items: list[dict[str, Any]], limit: int = 5, coverage: dict[str, Any] | None = None) -> dict[str, Any]:
    ...
    result["coverage"] = coverage or {}
    result["caveat"] = "Spotify 与本地补全 genre 标签可能重叠，百分比不应被解释为互斥类别。"
```

- [ ] **Step 7.4: Implement frontend copy**

Use compact copy:

```tsx
<p className="mt-3 text-[12px] leading-5 text-muted-foreground">
  流派标签来自 Spotify 与本地补全来源，标签可能重叠，百分比不互斥。
</p>
```

Do not add a new settings page in this task.

- [ ] **Step 7.5: Run tests**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_ai_insights_yearly_quality.py backend/tests/unit/test_agentic_yearly_report_tools.py -q
cd frontend && npm test -- yearly-review visual-yearly-report ai-task-components
```

Expected: PASS.

- [ ] **Step 7.6: Commit**

```bash
git add backend/services/ai_insights_service.py backend/domains/ai_reports/yearly_contract.py backend/domains/ai_reports/agentic_tools.py backend/domains/ai_reports/visual_chart_data.py frontend/src/pages/yearly-review/GenrePanorama.tsx frontend/src/features/music/details/ArtistCareerSection.tsx frontend/src/features/ai-tasks/AITaskProgress.tsx backend/tests frontend/src/tests
git commit -m "feat: show artist genre coverage in reports"
```

---

## Task 8: Documentation And Verification

**Files:**

- Modify: `docs/playback-stats/rules.md`
- Modify: `data/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 8.1: Document source priority**

Add this wording to `docs/playback-stats/rules.md`:

```markdown
### 艺人流派解析

艺人流派统计优先使用 Spotify 原始 `spotify_artist_meta.genres`。当 Spotify 未提供流派时，系统可使用本地已审核来源补全，包括 curated seed、MusicBrainz、Last.fm、Wikidata 与 AI 辅助建议。AI 建议默认不直接进入统计，除非被审核或有足够外部证据支持。流派标签是重叠标签，不是互斥分类。
```

- [ ] **Step 8.2: Document seed workflow**

Add to `data/README.md`:

```markdown
| `artist_genre_overrides.seed.json` | `artist_genre_sources` | 高播放权重艺人的本地流派补全种子；不覆盖 Spotify 原始 metadata |
```

- [ ] **Step 8.3: Update durable agent docs**

Update `README.md`, `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md` with the source priority and the rule that new genre consumers must use `backend.domains.metadata.artist_genres` instead of direct `spotify_artist_meta.genres` reads.

- [ ] **Step 8.4: Run verification**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/unit/test_artist_genre_seed_import.py backend/tests/unit/test_artist_genre_external_providers.py backend/tests/contract/test_artist_genre_consumers.py backend/tests/contract/test_artist_genre_backfill_task.py -q
source .venv/bin/activate && .venv/bin/python scripts/import_artist_genre_overrides.py --dry-run --json-output /tmp/artist_genre_seed_import.json
source .venv/bin/activate && .venv/bin/python scripts/artist_genre_coverage_probe.py --json-output /tmp/spotify_artist_genre_coverage.json
ruff check backend/
ruff format --check backend/
cd frontend && npm test -- yearly-review visual-yearly-report ai-task-components
cd frontend && npm run build
```

Expected: all commands PASS. Coverage JSON should show a lower unknown percentage after importing curated seed rows into a test or local writable DB.

- [ ] **Step 8.5: Commit**

```bash
git add docs/playback-stats/rules.md data/README.md README.md AGENTS.md CLAUDE.md backend/CLAUDE.md docs/README.md docs/CHANGELOG.md
git commit -m "docs: document artist genre resolution"
```

---

## Rollout Notes

Recommended rollout order:

1. Implement Tasks 1-4 first. This creates the resolver and improves statistics with curated seeds.
2. Run `scripts/artist_genre_coverage_probe.py` before and after importing seeds to quantify improvement.
3. Implement Tasks 5-6 when the deterministic resolver is stable. External providers and AI suggestions are additive.
4. Only enable AI auto-approval for rows with external corroboration. Pure LLM rows should remain `suggested`.
5. Add a small manual review UI later if the review queue grows; it is not required for the first useful release.

Acceptance criteria:

- Spotify raw genre fields remain unchanged.
- High-play artists with empty Spotify genres can be resolved through approved local data.
- Yearly genre distribution includes coverage and caveat metadata.
- AI reports no longer have to say there is no structured genre evidence when approved fallback data exists.
- Unknown genre play-hour share is measurable and can be used as a regression gate.
- All third-party calls stay inside `backend/providers/` and never appear directly in business services.
