# Artist Genre Resolution Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

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

AI rows start as `status='suggested'` unless they cite at least two non-LLM evidence sources. Only `approved` rows feed statistics.

---

## Task 1: Add Genre Resolution Schema

涉及文件：`backend/core/db.py`、`backend/core/migrations.py`、`backend/tests/unit/test_migrations.py`。

- Step 1.1: Write the migration test
- Step 1.2: Run the focused test and verify it fails
- Step 1.3: Add schema to fresh DBs

In `backend/core/db.py`, add the three tables and indexes from the "Data Model" section after `spotify_artist_meta`.

- Step 1.4: Add migration 23
- Step 1.5: Run the migration test
- Step 1.6: Commit

---

## Task 2: Implement The Resolver

涉及文件：`backend/domains/metadata/artist_genres.py`、`backend/tests/unit/test_artist_genre_resolution.py`。

- Step 2.1: Write resolver tests
- Step 2.2: Run the tests and verify they fail
- Step 2.3: Implement resolver module
- Step 2.4: Run resolver tests
- Step 2.5: Commit

---

## Task 3: Add Seed Import And Coverage Probe

涉及文件：`data/artist_genre_overrides.seed.json`、`scripts/import_artist_genre_overrides.py`、`scripts/artist_genre_coverage_probe.py`、`backend/tests/unit/test_artist_genre_seed_import.py`。

- Step 3.1: Create seed file

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

- Step 3.2: Write seed import tests

Create `backend/tests/unit/test_artist_genre_seed_import.py` to exercise the script with a temp database and assert inserted source rows can be resolved.

- Step 3.3: Implement import script
- `--seed data/artist_genre_overrides.seed.json`
- `--dry-run`
- `--json-output /tmp/artist_genre_seed_import.json`
- imports rows through `upsert_genre_source()`
- prints counts: `loaded`, `approved`, `suggested`, `dry_run`
- Step 3.4: Implement coverage probe
- loads play hours by artist using the same main-artist join as the current rough probe
- calls `compute_genre_coverage()`
- writes JSON when `--json-output` is supplied
- exits non-zero only when `--max-unknown-pct` is supplied and exceeded

Expected JSON keys: `known_pct`, `unknown_pct`, `source_hours`, `top_missing`.

- Step 3.5: Run tests and dry-run

- Step 3.6: Commit

---

- 历史验收要求：pytest PASS, dry-run writes JSON with `dry_run: true`, coverage probe reports current unknown percentage.

## Task 4: Route Statistics Through The Resolver

涉及文件：`backend/services/wrapped_service.py`、`backend/services/account_service.py`、`backend/domains/billboard/details.py`、`backend/domains/billboard/versus.py`、`backend/tests/contract/test_artist_genre_consumers.py`。

- Step 4.1: Write consumer tests

Create contract tests that seed:

- one artist with Spotify genre
- one artist with empty Spotify genre and approved curated fallback
- one artist with no genre

Assert:

- `get_wrapped_full(...).genre_panorama.top_genres` includes the curated fallback label.
- `get_wrapped_full(...).genre_panorama` still counts the unknown artist as "其他流派".
- artist detail metadata returns `genre_source` and `genre_confidence` when resolved through fallback.
- account collection genre migration uses fallback rows.
- Step 4.2: Update `wrapped_service.py`

Replace the direct batch query in `_build_genre_panorama()`, `_build_monthly_genres()`, `_calc_globetrotter_score()`, and `_build_music_map()` with `resolve_artist_genres_map()`.

When returning `genre_panorama`, include:

- Step 4.3: Update detail and versus metadata
- Step 4.4: Update account service

1. aggregate saved-track counts by year and artist
2. resolve artist genres in Python and accumulate counts

This keeps the resolver as the single source of truth.

- Step 4.5: Run consumer tests
- Step 4.6: Run related wrapped tests
- Step 4.7: Commit

---

## Task 5: Add External Providers

涉及文件：`backend/providers/lastfm/client.py`、`backend/providers/musicbrainz/client.py`、`backend/providers/wikidata/client.py`、`backend/tests/unit/test_artist_genre_external_providers.py`。

- Step 5.1: Write provider tests with fake HTTP clients

Tests should assert:

- Last.fm extracts top tag names from `artist.getinfo`.
- MusicBrainz extracts `genres` first, then falls back to counted `tags`.
- Wikidata extracts genre labels from SPARQL bindings.
- 429 and 5xx provider responses become structured provider failures or empty results without crashing the caller.
- Step 5.2: Implement Last.fm provider

Do not add a settings UI in this task. Read `LASTFM_API_KEY` from environment first; the backfill service can skip Last.fm when absent.

- Step 5.3: Implement MusicBrainz provider

Set a clear User-Agent through `HttpClient` headers if the shared client supports per-request headers; otherwise add a small method-level header path matching existing provider style.

- Step 5.4: Implement Wikidata provider

Use SPARQL only for artist-name lookup and genre labels. Store the Wikidata entity URL as evidence URL.

- Step 5.5: Run provider tests
- Step 5.6: Commit

---

## Task 6: Add AI-Assisted Backfill Task

涉及文件：`backend/services/artist_genre_backfill_service.py`、`backend/services/ai_task_service.py`、`backend/api/ai_tasks.py`、`backend/models/ai_tasks.py`、`backend/tests/contract/test_artist_genre_backfill_task.py`。

- Step 6.1: Write task contract tests

Use monkeypatches for providers and `_llm_chat()` so tests do not call the network or a real LLM.

Assertions:

- task type is `artist_genre_backfill`
- stages include `selecting_artists`, `fetching_external_data`, `calling_llm`, `saving_suggestions`, `done`
- tool calls record provider summaries
- rows from LLM are inserted with `status='suggested'`
- rows with two matching non-LLM sources can be inserted as `status='approved'`
- existing Spotify genres are skipped by default
- Step 6.2: Implement selection logic

It should order by play hours descending and skip artists where `resolve_artist_genres()` already has genres.

- Step 6.3: Implement evidence gathering

It should return keys `lastfm`, `musicbrainz`, `wikidata`, and `wikipedia_summary`. Missing provider config should return an empty list, not an error.

- Step 6.4: Implement LLM suggestion parser

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
- Step 6.5: Add ai task service entry
- Step 6.6: Add API and models

Add route:

- Step 6.7: Run task tests
- Step 6.8: Commit

---

## Task 7: Surface Genre Coverage In Reports And UI

涉及文件：`backend/services/ai_insights_service.py`、`backend/domains/ai_reports/yearly_contract.py`、`backend/domains/ai_reports/agentic_tools.py`、`backend/domains/ai_reports/visual_chart_data.py`、`frontend/src/pages/yearly-review/GenrePanorama.tsx`、`frontend/src/features/music/details/ArtistCareerSection.tsx`、`frontend/src/features/ai-tasks/AITaskProgress.tsx`。

- Modify tests under `backend/tests/unit/` and `frontend/src/tests/`
- Step 7.1: Backend report tests

Extend yearly report tests to assert:

- `genre_summary.coverage.known_pct` exists
- caveat says local fallback may be included
- AI prompt constraints forbid treating genre percentages as mutually exclusive
- Step 7.2: Frontend tests

Extend yearly report and artist detail tests to assert:

- source/caveat text renders when coverage exists
- existing UI still works when older API payload lacks `coverage`
- task progress has a Chinese label for `artist_genre_backfill`
- Step 7.3: Implement backend payload updates
- Step 7.4: Implement frontend copy

Do not add a new settings page in this task.

- Step 7.5: Run tests
- Step 7.6: Commit

---

## Task 8: Documentation And Verification

涉及文件：`docs/playback-stats/rules.md`、`data/README.md`、`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`docs/README.md`、`docs/CHANGELOG.md`。

- Step 8.1: Document source priority

```markdown
### 艺人流派解析

艺人流派统计优先使用 Spotify 原始 `spotify_artist_meta.genres`。当 Spotify 未提供流派时，系统可使用本地已审核来源补全，包括 curated seed、MusicBrainz、Last.fm、Wikidata 与 AI 辅助建议。AI 建议默认不直接进入统计，除非被审核或有足够外部证据支持。流派标签是重叠标签，不是互斥分类。
```

- Step 8.2: Document seed workflow

```markdown
| `artist_genre_overrides.seed.json` | `artist_genre_sources` | 高播放权重艺人的本地流派补全种子；不覆盖 Spotify 原始 metadata |
```

- Step 8.3: Update durable agent docs

Update `README.md`, `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md` with the source priority and the rule that new genre consumers must use `backend.domains.metadata.artist_genres` instead of direct `spotify_artist_meta.genres` reads.

- Step 8.4: Run verification

- Step 8.5: Commit

---

- 历史验收要求：all commands PASS. Coverage JSON should show a lower unknown percentage after importing curated seed rows into a test or local writable DB.

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
