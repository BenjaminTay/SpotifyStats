# Music Search Quick Open Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Build a direct local music search experience so users can search tracks, albums, and artists from anywhere, then open the existing music detail pages without first finding the entity in another chart/list.

**Architecture:** Add a read-only `/api/music/search` endpoint backed by the existing local entity resolver, normalize results into detail-page links, expose the endpoint through TanStack Query, then add a global Masthead search dialog and a full `/music/search` page. Keep detail pages unchanged and treat this as a lightweight local entity finder, not an LLM or external Spotify search feature.

**Tech Stack:** FastAPI, SQLite, Pydantic, React 19, TypeScript, React Router v7, TanStack Query, Tailwind CSS v4, lucide-react, Vitest, Testing Library, pytest.

---

## Scope And Product Decisions

- Search scope is local listening-history entities only: tracks, albums, artists.
- Search is deterministic and read-only. It does not call LLM, Spotify Web API, Genius, Wikipedia, or arbitrary SQL from the frontend.
- Results open existing routes:
  - Track: `/music/tracks/:trackId`
  - Album: `/music/albums/:albumName?artist=:artistName`
  - Artist: `/music/artists/:artistName`
- Primary entry is a search icon in `Masthead`, next to theme and settings.
- Secondary full-page entry is `/music/search`, labeled `音乐查找`.
- The playback-analysis secondary nav should not gain another persistent tab in the first implementation, because `AnalysisSubNav` currently has a deliberately fixed set: 播放统计 / 播放排行 / 年度总结 / 播放记录 / 账号中心.
- Do not add a separate search box/button to `播放排行` in the MVP. The Masthead utility button already solves global access, and adding another entry inside one ranking page would make the feature feel duplicated instead of clearer.
- The search dialog can include a `查看全部结果` link to `/music/search?q=...`.
- `Masthead` primary nav remains five destinations. The new search affordance is a utility button, not a sixth top-level nav item.

### Backend

- Create: `backend/models/music_search.py`
  - Owns response models for local music search results.
  - Keeps `backend/api/music.py` from accumulating model noise.

- Create: `backend/services/music_search_service.py`
  - Calls `backend.domains.ai_agent.entity_resolver.resolve_entities()` for each requested entity type.
  - Converts resolver candidates into stable, UI-ready result rows with routes.
  - Handles blank query, optional single-kind filtering, and per-kind limits.

- Modify: `backend/api/music.py`
  - Adds `GET /music/search`.
  - Uses `get_conn()` and Pydantic response model.
  - Keeps existing detail/stat/play endpoints unchanged.

- Create: `backend/tests/unit/test_music_search_service.py`
  - Tests route construction, mixed entity result grouping, blank query behavior, and limit behavior using an in-memory SQLite fixture.

- Create: `backend/tests/contract/test_music_search_api.py`
  - Tests the FastAPI endpoint contract with dependency-overridden SQLite connection.
  - Confirms response shape and validation boundaries.

### Frontend Types And Data

- Create: `frontend/src/types/music-search.ts`
  - Defines `MusicSearchKind`, `MusicSearchResult`, `MusicSearchResponse`.

- Modify: `frontend/src/api/query-keys.ts`
  - Adds `queryKeys.music.search(params)`.

- Modify: `frontend/src/hooks/useAnalysis.ts`
  - Adds `musicSearchApi.search()` and `useMusicSearch()`.
  - Keeps current query-client conventions instead of adding a new data layer.

- Modify: `frontend/src/lib/api.ts`
  - Re-exports music search types for compatibility with existing type export patterns.

### Frontend UI

- Create: `frontend/src/features/music/search/musicSearchUtils.ts`
  - Pure helpers for debouncing thresholds, labels, result hrefs if needed, and grouped counts.

- Create: `frontend/src/features/music/search/MusicSearchResults.tsx`
  - Renders grouped track/album/artist results.
  - Uses accessible links and stable row layout.
  - Does not fetch data.

- Create: `frontend/src/features/music/search/MusicSearchPage.tsx`
  - Full-page search UI at `/music/search`.
  - Reads `q` from URL and keeps it shareable.
  - Shows grouped results and empty states.

- Create: `frontend/src/features/music/search/MusicSearchDialog.tsx`
  - Global command-style dialog used by `Masthead`.
  - Opens via icon button, supports Escape/close, debounced query, grouped results, and a `查看全部结果` link.

- Create: `frontend/src/pages/MusicSearchPage.tsx`
  - Thin route container that renders `MusicSearchPage` feature.

- Modify: `frontend/src/App.tsx`
  - Lazy-loads `MusicSearchPage`.
  - Adds route `/music/search` before the dynamic `/music/...` detail routes.

- Modify: `frontend/src/components/layout/Masthead.tsx`
  - Adds icon-only search utility button with accessible name `搜索音乐详情`.
  - Mounts `MusicSearchDialog`.
  - Keeps five primary nav links unchanged.

- Modify: `frontend/src/components/layout/routeContext.ts`
  - Maps `/music/search` to `activeNavTo: null`, `contextSegments: ['音乐查找']`, `title: null`.
  - Keeps existing music detail routes as detail context.

### Frontend Tests And Smoke Coverage

- Create: `frontend/src/tests/music-search-components.test.tsx`
  - Tests grouped result rendering and links.

- Create: `frontend/src/tests/music-search-flow.test.tsx`
  - Tests page/dialog query behavior with mocked hook/API responses.

- Modify: `frontend/src/tests/masthead-navigation.test.tsx`
  - Confirms five primary destinations remain unchanged.
  - Confirms search utility button exists and settings link remains.

- Modify: `frontend/src/tests/masthead-route-context.test.ts`
  - Adds `/music/search` context expectation.

- Modify: `frontend/src/tests/phase5-architecture.test.ts`
  - Adds guardrail that `frontend/src/pages/MusicSearchPage.tsx` is a thin route container.

- Modify: `scripts/frontend_route_smoke.mjs`
  - Adds `/music/search` to default route marker coverage.

- Modify: `scripts/frontend_interaction_smoke.mjs`
  - Adds a non-destructive scenario that opens Masthead search, types a query from local sample data, and verifies visible grouped results or a stable empty state.

### Documentation

- Modify: `README.md`
  - Add a short note under frontend/navigation capabilities: direct music entity search opens detail pages.

- Modify: `AGENTS.md`
  - Add the new route/API to the project overview after implementation.

- Modify: `CLAUDE.md`
  - Keep facts aligned with `AGENTS.md` if it has an equivalent navigation/API summary.

- Modify: `docs/README.md` or `docs/CHANGELOG.md`
  - Add a release-note style line after implementation.

---

## Task 1: Backend Music Search Service

涉及文件：`backend/models/music_search.py`、`backend/services/music_search_service.py`、`backend/tests/unit/test_music_search_service.py`。

- Add response models
- Add the service implementation

---

## Task 2: Backend API Contract

涉及文件：`backend/api/music.py`、`backend/tests/contract/test_music_search_api.py`、`scripts/api_smoke_probe.py`、`scripts/openapi_operation_audit.py`。

- Write the API contract test
- Add the API endpoint
- Check OpenAPI operation/accounting impact

If the audit reports `/api/music/search` as unaccounted, add it to the safe GET smoke list using the existing pattern in `scripts/api_smoke_probe.py` and the operation audit mapping. The smoke request should use:

```text
/api/music/search?q=a&limit_per_type=3
```

- Add and run API smoke for the new route

---

- 历史验收要求：either PASS with 0 unaccounted operations, or a clear unaccounted entry for `/api/music/search`.
- 历史验收要求：PASS for all safe GET cases, including `music_search`, and OpenAPI GET coverage remains 0 unaccounted.

## Task 3: Frontend Data Layer And Types

涉及文件：`frontend/src/types/music-search.ts`、`frontend/src/api/query-keys.ts`、`frontend/src/hooks/useAnalysis.ts`、`frontend/src/lib/api.ts`、`frontend/src/tests/music-search-data.test.tsx`。

- Write frontend data-layer tests
- Add frontend types
- Add the query key

Place it before `artistDetail` so search appears before detail-specific keys.

- Add the hook
- Re-export types

---

## Task 4: Full Music Search Page

涉及文件：`frontend/src/features/music/search/musicSearchUtils.ts`、`frontend/src/features/music/search/MusicSearchResults.tsx`、`frontend/src/features/music/search/MusicSearchPage.tsx`、`frontend/src/pages/MusicSearchPage.tsx`、`frontend/src/App.tsx`、`frontend/src/components/layout/routeContext.ts`、`frontend/src/tests/music-search-components.test.tsx`、`frontend/src/tests/masthead-route-context.test.ts`、`frontend/src/tests/phase5-architecture.test.ts`。

- Write component tests for grouped results
- Write route context and architecture tests
- Add search UI helpers
- Add grouped results component
- Add the full page feature
- Add route container
- Wire the route before dynamic music detail routes
- Add route context

---

## Task 5: Masthead Global Search Dialog

涉及文件：`frontend/src/features/music/search/MusicSearchDialog.tsx`、`frontend/src/components/layout/Masthead.tsx`、`frontend/src/tests/masthead-navigation.test.tsx`、`frontend/src/tests/music-search-flow.test.tsx`。

- Write Masthead and dialog tests

Keep the existing expectation that primary nav has five destinations.

- Add the dialog component
- Mount the dialog in Masthead

---

## Task 6: Smoke Tests, Documentation, And Verification

涉及文件：`scripts/frontend_route_smoke.mjs`、`scripts/frontend_interaction_smoke.mjs`、`README.md`、`AGENTS.md`、`CLAUDE.md`、`docs/README.md`、`docs/CHANGELOG.md`。

- Add route smoke coverage

The marker check for `/music/search` should accept visible text `音乐查找`.

- Add interaction smoke scenario

Add it to the help text scenario list:

```text
  music-search-quick-open  Open Masthead music search and verify the quick-open dialog
```

- Update documentation

```markdown
- 音乐详情可通过全局“搜索音乐详情”入口直接查找本地歌曲、专辑和艺人，搜索结果会跳转到既有 `/music/tracks/*`、`/music/albums/*`、`/music/artists/*` 详情页。
```

```markdown
**音乐查找入口**：`/music/search` 与 Masthead 搜索按钮提供本地歌曲/专辑/艺人直接查找，后端使用只读 `/api/music/search`，结果只来自本地播放记录并跳转到既有音乐详情页。
```

```markdown
- 新增本地音乐查找入口：Masthead 可直接搜索歌曲、专辑、艺人并打开音乐详情页，同时提供 `/music/search` 全页结果。
```

Add a matching index note in `docs/README.md` if it contains a feature index.

Note: `ruff check backend/` passed. Full `ruff format --check backend/` is blocked by three pre-existing unrelated files (`backend/domains/billboard/year_end.py`, `backend/domains/playback/records_output.py`, `backend/domains/playback/records_time.py`); the touched backend files pass targeted `ruff format --check`.

Start services if not already running:

- Optional full gate before release

---

- 历史验收要求：Confirm `/music/search` has no horizontal overflow at 390px and the search dialog does not overlap Masthead controls incoherently.

## Execution Order

1. Task 1 builds the backend service with unit coverage.
2. Task 2 exposes and verifies the API contract.
3. Task 3 adds frontend types/query layer.
4. Task 4 adds the full `/music/search` page.
5. Task 5 adds the Masthead quick-open dialog.
6. Task 6 updates smoke coverage and documentation.

This order keeps every step independently testable. The app becomes useful after Task 4, and becomes globally convenient after Task 5.

## Acceptance Criteria

- `/api/music/search?q=<keyword>` returns grouped local results for tracks, albums, and artists.
- Search results never call LLM or external provider APIs.
- Track results link to `/music/tracks/:trackId`.
- Album results link to `/music/albums/:albumName?artist=:artistName`.
- Artist results link to `/music/artists/:artistName`.
- `/music/search` is shareable with `?q=...`.
- Masthead still has exactly five primary destinations.
- Masthead utility area includes an accessible `搜索音乐详情` button.
- Dialog and full page work on desktop and 390px mobile without horizontal overflow.
- Frontend GET data flows through TanStack Query and `queryKeys`.
- Route container guardrails remain intact.
- Focused backend tests, focused frontend tests, and `npm run build` pass.

## Self-Review

- Spec coverage: The plan covers backend search, frontend data, full page, global Masthead entry, routing context, smoke tests, and docs.
- Placeholder scan: No task depends on undefined behavior. Each code-changing task includes concrete files, code blocks, commands, and expected outcomes.
- Type consistency: Backend `MusicSearchResponse` fields match frontend `MusicSearchResponse`; route fields use `href` consistently; entity kind values are `track`, `album`, `artist` across Python and TypeScript.
- Scope check: The plan intentionally excludes external Spotify search, fuzzy pinyin search, keyboard shortcut command palette, and recent-search persistence. Those can be separate enhancements after the local quick-open baseline is stable.
