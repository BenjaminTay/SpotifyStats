# Genre Review Settings Panel Design

> 状态：已确认；当前实现和审核规则以 `docs/reference/` 及 Settings 代码为准

## Goal

Add an in-app Genre 数据健康 panel to Settings so artist genre fallback data can be reviewed without terminal commands.

## Placement

The panel lives in `SettingsPage`, near data/import and LLM settings. Genre review is data quality maintenance rather than daily music browsing, so it should not become a Masthead top-level entry yet.

## Backend API

Add a focused metadata router:

- `GET /api/metadata/artist-genres/coverage`
  - Returns the same play-hour coverage report as `scripts/artist_genre_coverage_probe.py`.
- `GET /api/metadata/artist-genres/taxonomy`
  - Returns raw genre count, canonical genre count, noncanonical passthrough count, top canonical genres, and raw-to-canonical mapping examples.
- `GET /api/metadata/artist-genres/reviews?status=open&limit=50`
  - Returns review queue rows joined with suggested source metadata.
- `POST /api/metadata/artist-genres/reviews/{review_id}/approve`
  - Atomically marks an open suggested row as approved.
- `POST /api/metadata/artist-genres/reviews/{review_id}/reject`
  - Atomically marks an open suggested row as rejected.

The API reuses the same functions as `scripts/review_artist_genre_suggestions.py` so terminal and UI behavior stay consistent.

## Frontend UX

Create `GenreDataHealthSection` under settings:

- Coverage summary: known percentage, unknown percentage, source mix.
- Taxonomy audit: raw vs canonical label counts, noncanonical passthrough warning, top canonical genres, and raw -> canonical examples.
- Top missing artists list.
- Open review table with artist, genres, confidence, source, play hours, and evidence summary.
- Approve / reject buttons for each open review row.
- Start small backfill button with conservative defaults: `limit=10`, `min_hours=8`, `include_ai=true`, `approve_high_confidence_external=true`.
- After approve/reject or task completion, invalidate genre review/coverage queries.

## Non-goals

- No bulk approve.
- No freeform genre editing.
- No standalone metadata nav page.
- No automatic approval UI for all missing artists.

## Testing

- Backend contract tests cover coverage, review listing, approve, reject, and stale review error.
- Frontend tests cover rendering coverage/taxonomy/review rows, approve/reject calls, and starting a backfill task.
