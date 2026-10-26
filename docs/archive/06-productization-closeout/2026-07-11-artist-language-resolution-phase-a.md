# Artist Language Resolution Phase A Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

**Goal:** Build an auditable artist-level language metadata workflow, truthful primary-artist language statistics, a Settings review UI, and a yearly-review consumer that no longer infers language from genre.

**Architecture:** Add three SQLite tables through migration 24, then place registry/resolution/statistics in `backend/domains/metadata/artist_languages.py` and review transactions in `artist_language_review.py`. Expose five FastAPI endpoints, reuse `/api/music/search`, integrate a stable language fact revision into Wrapped caching, and keep the frontend language UI isolated in two focused Settings components.

**Tech Stack:** Python 3.12, SQLite, FastAPI, Pydantic v2, pandas, pytest, React 19, TypeScript, TanStack Query, Base UI, Vitest, Playwright-based smoke scripts.

---

## Execution Rules

- Follow TDD inside every task: failing focused test, minimal implementation, focused pass, then broader regression.
- Preserve the existing genre workflow. Language resolution never calls `resolve_artist_genres_map()`.
- Use primary artist attribution from `tracks.artist_id`; never use `load_plays_for_artists()` for language distribution.
- Do not write approved facts directly from legacy data. Legacy import creates suggested reviews only.
- Do not run a production database import until its dry-run JSON has been reviewed.

## File Map

**Backend create:**

- `backend/domains/metadata/language_registry.py` — canonical code/variant registry and labels.
- `backend/domains/metadata/artist_languages.py` — resolver, validator, primary-artist attribution, distribution, fact revision.
- `backend/domains/metadata/artist_language_review.py` — review/source/evidence state transitions and transactions.
- `backend/models/artist_language_metadata.py` — request and response models.
- `backend/api/artist_language_metadata.py` — five language metadata endpoints.
- `scripts/import_artist_language_sources.py` — reviewed seed and legacy-suggestion importer.
- `data/artist_language_sources.seed.json` — reviewed seed payload, initially an empty JSON array until evidence is approved.

**Backend modify:**

- `backend/core/migrations.py` — migration 24.
- `backend/api/router.py` — language router registration.
- `backend/models/music_search.py` — optional `artist_id`.
- `backend/services/music_search_service.py` — populate artist search IDs.
- `backend/models/wrapped.py` — dynamic language distribution models.
- `backend/services/wrapped_service.py` — primary-artist language distribution and metadata cache revision.
- `scripts/api_smoke_probe.py` — safe GET coverage for language metadata.
- `scripts/openapi_operation_audit.py` — targeted evidence for five endpoints.
- `scripts/openapi_parameter_boundary_audit.py` — status, limit, review ID, and filter parameter evidence.

**Frontend create:**

- `frontend/src/types/artist-language-metadata.ts` — UI types.
- `frontend/src/hooks/useArtistLanguageMetadata.ts` — queries and mutations.
- `frontend/src/components/ui/dialog.tsx` — Base UI dialog wrapper matching existing primitives.
- `frontend/src/features/settings/components/ArtistLanguageHealthSection.tsx` — compact health/review list.
- `frontend/src/features/settings/components/ArtistLanguageReviewDialog.tsx` — source and evidence editor.

**Frontend modify:**

- `frontend/src/api/query-keys.ts` — `metadata.artistLanguages` keys.
- `frontend/src/types/music-search.ts` — optional `artist_id`.
- `frontend/src/types/yearly-review.ts` — dynamic distribution type.
- `frontend/src/features/settings/components/GenreDataHealthSection.tsx` — title and child composition only.
- `frontend/src/pages/yearly-review/GenrePanorama.tsx` — render backend buckets independently from genre.
- `frontend/src/lib/genre-regions.ts` — remove `inferLanguageDist()`.
- `frontend/src/api/generated/openapi.json` and `api-types.ts` — regenerated contract.
- `scripts/frontend_interaction_smoke.mjs` — Settings language review smoke.

**Tests create:**

- `backend/tests/unit/test_artist_language_migration.py`
- `backend/tests/unit/test_language_registry.py`
- `backend/tests/unit/test_artist_language_resolution.py`
- `backend/tests/unit/test_artist_language_review.py`
- `backend/tests/unit/test_artist_language_distribution.py`
- `backend/tests/unit/test_artist_language_seed_import.py`
- `backend/tests/contract/test_artist_language_metadata_api.py`
- `backend/tests/contract/test_artist_language_consumers.py`
- `frontend/src/tests/artist-language-health-section.test.tsx`
- `frontend/src/tests/artist-language-review-dialog.test.tsx`
- `frontend/src/tests/artist-language-hooks.test.tsx`
- `frontend/src/tests/yearly-language-distribution.test.tsx`

## Spec Coverage Map

| Spec requirement | Implementation task |
| --- | --- |
| Three-table schema and invariants | Task 1 |
| Canonical code/variant registry and API models | Task 2 |
| Evidence rules, approved-only resolver, primary-artist conservation, fact revision | Task 3 |
| Review lifecycle, replacement transaction, insufficient evidence | Task 4 |
| Five endpoints, PlayFilters, music-search reuse, error contracts | Task 5 |
| Reviewed seed, legacy suggestions, unresolved/conflicted handling | Task 6 |
| Wrapped dynamic distribution and cache invalidation | Task 7 |
| TanStack Query, generated/manual types, dialog primitive | Task 8 |
| Settings card 06 composition and human review UI | Task 9 |
| Removal of genre-to-language inference in yearly review | Task 10 |
| OpenAPI/API/UI smoke ownership | Task 11 |
| Durable docs, dry-run evidence, browser and release gates | Task 12 |

---

### Task 1: Add Migration 24 and Database Invariants

涉及文件：`backend/core/migrations.py`、`backend/tests/unit/test_artist_language_migration.py`。

- Write migration tests before the migration exists

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_migration.py -v`

- Add `@migration(24, "artist_language_resolution")`

---

- 历史验收要求：both pass; migration 24 is idempotent.

### Task 2: Add the Canonical Language Registry and API Models

涉及文件：`backend/domains/metadata/language_registry.py`、`backend/models/artist_language_metadata.py`、`backend/tests/unit/test_language_registry.py`。

- Write registry tests

Run: `.venv/bin/pytest backend/tests/unit/test_language_registry.py -v`

- Implement the registry as the only label source
- Add typed request/response models

Create Pydantic models with the exact public fields below. Public Settings request models and read-only response models have different provenance boundaries: the public PUT body accepts only language facts and evidence content, while response models expose persisted audit fields. Use `Literal` for classifications, origins, evidence kinds, attributions, review statuses, and actions; use `Field(default_factory=list)` for arrays and `ConfigDict(extra="forbid")` on public PUT input models so clients cannot inject provenance fields.

`ArtistLanguageEvidenceItem` and `ArtistLanguageSourceItem` intentionally retain `evidence_accessed_at`, `origin`, and `source_key`: these are read-only audit fields returned after persistence, not fields accepted from Settings. For every public PUT, the service must persist `origin="manual"`, generate a `manual:<uuid4>` source key for a new candidate, and stamp each evidence row with current UTC. Only the importer may call the internal service payload path with validated `curated_seed`/`legacy_import` provenance, deterministic source keys, and recorded evidence access times.

---

### Task 3: Implement Resolution, Validation, Distribution, and Fact Revision

涉及文件：`backend/domains/metadata/artist_languages.py`、`backend/tests/unit/test_artist_language_resolution.py`、`backend/tests/unit/test_artist_language_distribution.py`。

- Write resolver and revision tests

Create an in-memory fixture with the migration 24 schema, two artists, one approved source, one suggested source, and evidence. Lock these behaviors:

- Write validator tests for all classifications

Test these exact cases: valid single overview; single rejected when only `track_language`; valid multilingual with `en` plus `zh/mandarin`; invalid multilingual with `zh/NULL` plus `zh/mandarin`; valid instrumental overview; invalid instrumental track-only; track evidence rejected when `track_artists` does not credit the artist.

- Write primary-attribution and conservation tests
- Implement the public domain contract

Implement `validate_approved_language_source(conn, artist_id, source_row, evidence_rows)` by normalizing evidence claim sets through `normalize_language_claim()`, checking `track_artists`, and enforcing the exact single/multilingual/instrumental rules from the spec. Return normalized `(source_values, evidence_values)` rather than mutating the database.

Implement `build_primary_artist_ms(conn, plays_df)` by joining only `tracks(track_id, artist_id)`, summing `ms_played` by `artist_id`, and returning excluded milliseconds separately. Put exact bucket allocation in `_compute_language_bucket_ms(conn, artist_ms_by_id)` and let `compute_artist_language_distribution()` format that integer-millisecond result into public hours/percentages. The public dict must not contain private/raw fields.

---

- 历史验收要求：PASS, including no fan-out and exact millisecond conservation.

### Task 4: Implement the Review State Machine

涉及文件：`backend/domains/metadata/artist_language_review.py`、`backend/tests/unit/test_artist_language_review.py`。

- Write state-transition tests

Cover: idempotent open review creation; saving and replacing suggested evidence; approve without evidence fails; reject closes source/review; insufficient review works without a source; approved replacement uses `replaces_source_id`; stale review raises conflict; failure between supersede and approve rolls back.

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_review.py -v`

- Implement explicit service exceptions and public functions

Implement `get_review()`, `list_reviews()`, `save_review_source()`, and `decide_review()` in the same module. Every mutation uses `immediate_transaction()`. The helper owns commit/rollback only when the caller has not already opened a transaction, so the importer can wrap an entire batch in one outer `BEGIN IMMEDIATE`. `save_review_source()` may edit only an open review and suggested source. Its public Settings path accepts only fact/evidence content, forces `origin="manual"`, generates `manual:<uuid4>` for a new candidate, stamps current UTC `evidence_accessed_at`, normalizes code/variant values, and replaces evidence rows in one transaction. Keep importer provenance in a separate internal payload/helper that may accept only validated `curated_seed`/`legacy_import` origin, deterministic `source_key`, and recorded `evidence_accessed_at`; never expose those fields through the FastAPI request model. `decide_review()` re-reads the review, calls `validate_approved_language_source()` for approve, sets any existing approved source to superseded, approves the candidate, and closes the review before the transaction exits. Reject and insufficient-evidence decisions set any attached suggested source to rejected; terminal rows cannot be edited through the service.

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_review.py -v`

---

### Task 5: Expose Five FastAPI Endpoints and Reuse Music Search

涉及文件：`backend/api/artist_language_metadata.py`、`backend/api/router.py`、`backend/models/music_search.py`、`backend/services/music_search_service.py`、`backend/tests/contract/test_artist_language_metadata_api.py`、`backend/tests/contract/test_playback_filter_parameter_propagation.py`。

Add explicit 404, 409, and 422 assertions, review status/limit listing, and insufficient-evidence without source. Also assert that public PUT rejects `origin`, `source_key`, and evidence `evidence_accessed_at` as extra fields, while a successful Settings save returns server-generated `origin="manual"`, a `manual:` UUID source key, and a server-stamped evidence access time.

Run: `.venv/bin/pytest backend/tests/contract/test_artist_language_metadata_api.py -v`

- Implement the router with existing dependencies

Create a router with prefix `/metadata/artist-languages`. Use `PlayFilters = Depends()` on coverage and review creation. Coverage calls `load_plays()` with all five filter fields, then `build_primary_artist_ms()` and `compute_artist_language_distribution()`.

Call `_filtered_plays(conn, filters)` with the request connection. `load_plays()` uses the repository cache internally but does not retain or close the request connection. Map service exceptions to 404/409 and validation errors to 422 with `{code, message}` detail.

For PUT source saves, pass only the validated fact/evidence request to the public Settings service path; do not derive provenance from request JSON. For PATCH decisions, ignore any client-supplied actor field: pass `reviewed_by="local_user"` and let the service set current UTC `reviewed_at`. The request model contains only `action` and `resolution_note`.

- Register the router and expose `artist_id` from music search
- Lock filter propagation

Add a test to `test_playback_filter_parameter_propagation.py` that creates a short dynamic-threshold play and asserts the language coverage differs between `dynamic_threshold=false` and `true`. Also assert `max_merge_gap_minutes` reaches the endpoint dependency.

---

### Task 6: Add Reviewed Seed and Legacy-Suggestion Import

涉及文件：`scripts/import_artist_language_sources.py`、`data/artist_language_sources.seed.json`、`backend/tests/unit/test_artist_language_seed_import.py`。

- Write importer tests

Test dry-run/no writes, reviewed approved seed through the same approve service, idempotency, existing-approved conflict, unresolved artist, normalized-identical legacy merge, conflicting legacy skip, and rollback after a simulated second-row failure.

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_seed_import.py -v`

- Implement one CLI with two input modes

Reviewed seed rows contain `artist_name`, optional `spotify_artist_id`, source fields, evidence list, status, `reviewed_by`, and `resolution_note`. Resolve `artist_id` before writing. The importer owns a separate internal payload schema that may carry validated `origin`, deterministic `source_key`, and evidence `evidence_accessed_at`; these fields must never be reused as the public PUT request model. The importer opens one outer `BEGIN IMMEDIATE` for the batch, then approved seed rows call `get_or_create_review()`, the internal provenance-aware save path, and `decide_review()` rather than issuing direct approved INSERTs. Those services detect the outer transaction through `immediate_transaction()` and therefore cannot partially commit the batch. Dry-run must execute the same structural and foreign-key validation as the write path, so accepted dry-run rows cannot fail only when persisted.

Legacy mode reads approved rows from `artist_genre_sources` and all `artist_genre_overrides` with non-empty language. Normalize per artist; merge identical claims; emit `conflicted` without writes for disagreeing claims; create suggested source/review only for one unambiguous claim. Never fabricate evidence.

- Create the production seed file as valid empty JSON

```json
[]
```

The repository must not ship invented evidence. Reviewed entries can be added later through the same schema.

- Stop before writing production legacy suggestions

Review `/tmp/artist-language-legacy-dry-run.json`. The actual command without `--dry-run` is a separate, explicit deployment action after user approval.

---

- 历史验收要求：tests pass; seed dry-run reports zero rows; legacy dry-run reports suggested/unresolved/conflicted without changing `data/spotify_stats.db`.

### Task 7: Integrate Language Distribution into Wrapped and Cache Revision

涉及文件：`backend/models/wrapped.py`、`backend/services/wrapped_service.py`、`backend/tests/contract/test_artist_language_consumers.py`、`backend/tests/unit/test_wrapped_genre_panorama.py`。

- Write consumer and cache tests

Lock these behaviors: backend returns dynamic buckets; language uses primary artist while genre keeps fan-out semantics; bucket milliseconds conserve the year frame; language renders even when genre list is empty; approving a fact invalidates Wrapped LRU; editing suggested evidence does not.

- Replace fixed language fields with dynamic response models

Set `GenrePanorama.language_dist: LanguageDistribution | None` and retain existing genre `coverage` and `caveat` fields.

- Compose a combined metadata revision

Rename `_artist_genre_revision()` to `_artist_metadata_revision()` and append `artist_language_fact_revision(conn)` to the existing genre revision. Rename the cached argument to `artist_metadata_revision`; no other cache signature changes.

- Build language distribution before the genre empty return

Inside `_build_genre_panorama(conn, year_df, artist_agg)`, call `build_primary_artist_ms(conn, year_df[["track_id", "ms_played"]])` and `compute_artist_language_distribution()`. The function must return this value both when genres are empty and when they are present. Do not use `artist_agg` for language.

---

- 历史验收要求：existing genre behavior remains unchanged.

### Task 8: Add Frontend Types, Query Keys, Hooks, and Dialog Primitive

涉及文件：`frontend/src/types/artist-language-metadata.ts`、`frontend/src/hooks/useArtistLanguageMetadata.ts`、`frontend/src/components/ui/dialog.tsx`、`frontend/src/api/query-keys.ts`、`frontend/src/types/music-search.ts`、`frontend/src/tests/artist-language-hooks.test.tsx`。

- Write hook tests with mocked API calls

Assert coverage query includes current play filters, review list keys include status/limit, start review POSTs `artist_id`, save source uses PUT, decision uses PATCH, and successful mutations invalidate only language metadata and yearly review keys.

Run: `cd frontend && npm test -- --run src/tests/artist-language-hooks.test.tsx`

- Add exact query keys and UI types

Define TypeScript interfaces matching Task 2, including dynamic `LanguageBucket`, `ArtistLanguageCoverage`, evidence/source/review inputs, and mutation responses. The Settings evidence/source input interfaces contain only fact and evidence content: they must not expose `evidence_accessed_at`, `origin`, or `source_key`; read-only response interfaces retain those audit fields. Add `artist_id: number | null` to `MusicSearchResult`.

- Implement hooks around the five endpoints

Use `api.get/post/put/patch`. The save-source PUT must serialize only the public fact/evidence input and must not synthesize provenance in the browser. After successful mutation invalidate only `queryKeys.metadata.artistLanguages.all` and `queryKeys.yearlyReview.all`.

- Add a Base UI dialog wrapper

Create `dialog.tsx` using `Dialog as DialogPrimitive` from `@base-ui/react/dialog`, following the focus trap, backdrop, title, description, close button, and `max-h-[90vh] overflow-y-auto` patterns already used by `sheet.tsx`. Export `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`, and `DialogClose`.

---

### Task 9: Build the Settings Language Health and Review Experience

涉及文件：`frontend/src/features/settings/components/ArtistLanguageHealthSection.tsx`、`frontend/src/features/settings/components/ArtistLanguageReviewDialog.tsx`、`frontend/src/features/settings/components/GenreDataHealthSection.tsx`、`frontend/src/tests/artist-language-health-section.test.tsx`、`frontend/src/tests/artist-language-review-dialog.test.tsx`、`frontend/src/tests/genre-data-health-section.test.tsx`。

- Write health-section interaction tests

Assert the collapsed summary shows classified/unknown/open counts; expanding renders Top unknown; clicking “开始审核” starts/reuses a review and opens the dialog; the status menu can show terminal history; no campaign or AI controls appear.

- Write review-dialog tests

Cover single language and variant selection, multiple evidence rows, artist/track search selection, approve/reject/insufficient actions, structured 422 display, replacement-chain display, accessible labels, and closing without mutation.

- Implement `ArtistLanguageHealthSection` as an unframed subsection

Use a local `CollapsibleSection` without a number, a three-value summary row, a compact unknown list, a standard status select, and text/icon buttons. Do not wrap it in `GlassCard`; the parent already owns the card. Limit visible unknown rows to 10 and let the API limit review history to 50.

- Implement the review dialog

Use the new dialog primitive, existing Select and Button components, native labeled inputs/textareas, plus/minus icon buttons for evidence rows, and `useMusicSearch(..., 'artist')` / `useMusicSearch(..., 'track')`. Classification controls determine which language fields are visible. The approve button stays disabled until the client-side minimum shape is present, while the backend remains authoritative.

- Compose it into the existing card without restructuring genre

Change the outer title to `流派与语言数据健康`, update the description, and render `<ArtistLanguageHealthSection />` after the existing genre panel content. Keep card number 6 and all current genre panel states/tests.

---

- 历史验收要求：PASS with no nested cards or changed Settings numbering.

### Task 10: Replace Yearly Genre Inference with Backend Language Buckets

涉及文件：`frontend/src/types/yearly-review.ts`、`frontend/src/pages/yearly-review/GenrePanorama.tsx`、`frontend/src/lib/genre-regions.ts`、`frontend/src/tests/yearly-language-distribution.test.tsx`。

- Write yearly rendering tests

Test dynamic buckets, classified/unknown copy, excluded-hours caveat, genre-empty/language-present rendering, and complete absence of `inferLanguageDist` imports.

Run: `cd frontend && npm test -- --run src/tests/yearly-language-distribution.test.tsx`

- Replace the fixed interface and render backend buckets

Define `LanguageDistribution` using the Task 8 types. Remove `useMemo`, `inferLanguageDist`, fixed label/color maps, and the genre-only early return. Render the genre card only when `top_genres.length > 0`; render the language card whenever `language_dist.buckets.length > 0`; render the section-level empty state only when both are absent.

- Delete the unused inference function

Remove `inferLanguageDist()` and any constants used only by it from `frontend/src/lib/genre-regions.ts`. Verify repository search returns no production references.

---

### Task 11: Regenerate OpenAPI Types and Extend Verification Ownership

涉及文件：`frontend/src/api/generated/openapi.json`、`frontend/src/api/generated/api-types.ts`、`scripts/api_smoke_probe.py`、`scripts/openapi_operation_audit.py`、`scripts/openapi_parameter_boundary_audit.py`、`backend/tests/unit/test_openapi_operation_audit_script.py`、`backend/tests/unit/test_openapi_parameter_boundary_audit_script.py`、`scripts/frontend_interaction_smoke.mjs`、`backend/tests/unit/test_frontend_interaction_smoke_script.py`。

- Add audit tests before audit mappings

Assert all five operations resolve to `targeted_contract` evidence in `test_artist_language_metadata_api.py`, and language `review_id`, `status`, `limit`, plus PlayFilters parameters have explicit ownership.

- Add safe GET cases and targeted operation mappings

Add all five endpoint keys to `TARGETED_OPERATION_EVIDENCE`, pointing at `backend/tests/contract/test_artist_language_metadata_api.py`. Add boundary evidence for `review_id`, `status`, and `limit`; reuse the existing playback propagation contract for PlayFilters.

- Regenerate types from a running backend

Start the backend with warmup disabled, then generate:

- Extend Settings interaction smoke without creating reviews

The smoke must open Settings, expand “语言数据”, verify Top unknown or empty state, and verify the “开始审核” command is accessible. If an open review already exists, it may open that existing review dialog and close it; otherwise it must not click “开始审核”, because creating an open review is a database write. Component and contract tests cover the full mutation path.

历史验收预期： zero unaccounted operations and parameters.

---

### Task 12: Documentation, Production Dry-Run, and Release Gate

涉及文件：`README.md`、`AGENTS.md`、`CLAUDE.md`、`docs/CHANGELOG.md`。

- Review: `docs/README.md`
- Include: `docs/superpowers/specs/2026-07-10-artist-language-resolution-design.md`
- Include: `docs/superpowers/plans/2026-07-11-artist-language-resolution-phase-a.md`
- Update durable documentation

Document these stable rules in AGENTS/CLAUDE: language resolution is artist-ID based and independent from genre; statistics use primary artist attribution; legacy/LLM data cannot auto-approve; unknown/multilingual/instrumental remain visible. Add user-facing Settings and yearly behavior to README and a dated implementation entry to CHANGELOG. Add links to `docs/README.md` only if its current indexing policy includes active superpowers specs/plans.

- Start services and run non-destructive full-stack checks

历史验收预期： zero API coverage gaps, zero unnamed controls, zero horizontal overflow, and no console warning/error.

Record suggested/unresolved/conflicted counts and affected play hours in the final implementation report. Do not remove `--dry-run` without explicit approval.

- Perform real browser acceptance against a disposable database

Start the backend with `SPOTIFY_STATS_DB_PATH` or the repository's supported DB-path override pointed at a temporary database copy. Verify desktop and 390px Settings: card 06 title, existing genre panels, language collapsible summary, Top unknown, start review, artist search, evidence rows, terminal-history filter, dialog close, and no overflow. Exercise one approve and one insufficient-evidence path, then discard the temporary database. Verify a yearly page: backend buckets render, classified/unknown copy is accurate, genre and language render independently, and no heuristic language result remains. If the repository does not yet support a DB-path environment override, monkeypatch `backend.core.db.DB_PATH` in a dedicated browser harness rather than adding a production configuration feature to this scope.

- Final commit checkpoint after authorization

If `docs/README.md` did not require a change, omit it from `git add`.

---

## Completion Checklist

- Three tables and migration 24 are present and idempotent.
- Five API endpoints have response models, contract coverage, and audit ownership.
- Resolver reads only approved facts by artist ID.
- Single/multilingual/instrumental evidence rules are enforced centrally.
- Language distribution uses primary artist attribution and conserves eligible milliseconds.
- Legacy import creates suggestions only and has a reviewed dry-run report.
- Wrapped cache changes on approved language facts, not suggested edits.
- Settings preserves card number 06 and adds no new top-level card/tab.
- Yearly review has no production reference to `inferLanguageDist()`.
- Generated OpenAPI types, manual frontend types, docs, tests, and browser smoke agree.
