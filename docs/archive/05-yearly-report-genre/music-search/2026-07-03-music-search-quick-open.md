# Music Search Quick Open Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

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

## File Structure

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

**Files:**
- Create: `backend/models/music_search.py`
- Create: `backend/services/music_search_service.py`
- Create: `backend/tests/unit/test_music_search_service.py`

- [x] **Step 1: Write the unit test for grouped results and detail links**

Create `backend/tests/unit/test_music_search_service.py` with this content:

```python
from __future__ import annotations

import sqlite3

import pytest

from backend.services.music_search_service import search_music_entities

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );

        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Olivia Rodrigo'),
            (2, 'Taylor Swift');
        INSERT INTO albums(album_id, album_name, artist_id) VALUES
            (10, 'GUTS', 1),
            (20, 'folklore', 2);
        INSERT INTO tracks(track_id, track_name, artist_id, album_id, duration_ms) VALUES
            (100, 'vampire', 1, 10, 219724),
            (101, 'bad idea right?', 1, 10, 184783),
            (200, 'cardigan', 2, 20, 239560);
        INSERT INTO plays(play_id, track_id, ms_played, source_album_id) VALUES
            (1, 100, 200000, NULL),
            (2, 100, 190000, NULL),
            (3, 101, 180000, NULL),
            (4, 200, 210000, NULL);
        """
    )
    return conn


def test_search_music_entities_returns_grouped_results_with_detail_links() -> None:
    result = search_music_entities(_conn(), query="vamp", limit_per_type=5)

    assert result.query == "vamp"
    assert result.total == 1
    assert [item.label for item in result.tracks] == ["vampire"]
    assert result.tracks[0].kind == "track"
    assert result.tracks[0].href == "/music/tracks/100"
    assert result.tracks[0].subtitle == "Olivia Rodrigo · GUTS"
    assert result.tracks[0].play_events == 2
    assert result.tracks[0].total_ms == 390000
    assert result.albums == []
    assert result.artists == []


def test_search_music_entities_searches_all_entity_types() -> None:
    result = search_music_entities(_conn(), query="olivia", limit_per_type=5)

    assert result.total == 1
    assert result.tracks == []
    assert result.albums == []
    assert [item.href for item in result.artists] == ["/music/artists/Olivia%20Rodrigo"]
    assert result.artists[0].subtitle == "3 次播放"


def test_search_music_entities_can_filter_entity_types() -> None:
    result = search_music_entities(_conn(), query="gut", kinds=("album",), limit_per_type=5)

    assert result.total == 1
    assert result.tracks == []
    assert result.artists == []
    assert result.albums[0].href == "/music/albums/GUTS?artist=Olivia%20Rodrigo"
    assert result.albums[0].subtitle == "Olivia Rodrigo"


def test_search_music_entities_returns_empty_for_blank_query_without_db_work() -> None:
    result = search_music_entities(_conn(), query="   ", limit_per_type=5)

    assert result.query == "   "
    assert result.total == 0
    assert result.tracks == []
    assert result.albums == []
    assert result.artists == []


def test_search_music_entities_bounds_limit_per_type() -> None:
    result = search_music_entities(_conn(), query="a", limit_per_type=99)

    assert result.limit_per_type == 10
    assert result.total >= 1
```

- [x] **Step 2: Run the unit test to verify it fails**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_music_search_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.music_search_service'`.

- [x] **Step 3: Add response models**

Create `backend/models/music_search.py`:

```python
"""Response models for local music entity search."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MusicSearchKind = Literal["track", "album", "artist"]


class MusicSearchResult(BaseModel):
    kind: MusicSearchKind
    label: str
    subtitle: str | None = None
    href: str
    play_events: int = 0
    total_ms: int = 0
    track_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None


class MusicSearchResponse(BaseModel):
    query: str
    limit_per_type: int = Field(ge=1, le=10)
    total: int
    tracks: list[MusicSearchResult] = Field(default_factory=list)
    albums: list[MusicSearchResult] = Field(default_factory=list)
    artists: list[MusicSearchResult] = Field(default_factory=list)
```

- [x] **Step 4: Add the service implementation**

Create `backend/services/music_search_service.py`:

```python
"""Local read-only music entity search service."""

from __future__ import annotations

import sqlite3
from typing import Iterable
from urllib.parse import quote

from backend.domains.ai_agent.entity_resolver import EntityType, resolve_entities
from backend.models.music_search import MusicSearchResponse, MusicSearchResult

_ALL_KINDS: tuple[EntityType, ...] = ("track", "album", "artist")


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 10))


def _valid_kinds(kinds: Iterable[str] | None) -> tuple[EntityType, ...]:
    if kinds is None:
        return _ALL_KINDS
    selected = tuple(kind for kind in kinds if kind in _ALL_KINDS)
    return selected or _ALL_KINDS


def _plays_text(play_events: int) -> str:
    return f"{play_events} 次播放"


def _track_result(candidate: dict) -> MusicSearchResult | None:
    track_id = candidate.get("track_id")
    label = candidate.get("track_name") or candidate.get("name")
    if track_id is None or not label:
        return None
    artist_name = candidate.get("artist_name")
    album_name = candidate.get("album_name")
    subtitle_parts = [part for part in (artist_name, album_name) if part]
    return MusicSearchResult(
        kind="track",
        label=str(label),
        subtitle=" · ".join(str(part) for part in subtitle_parts) or None,
        href=f"/music/tracks/{track_id}",
        play_events=int(candidate.get("play_events") or 0),
        total_ms=int(candidate.get("total_ms") or 0),
        track_id=int(track_id),
        album_name=str(album_name) if album_name else None,
        artist_name=str(artist_name) if artist_name else None,
    )


def _album_result(candidate: dict) -> MusicSearchResult | None:
    album_name = candidate.get("album_name") or candidate.get("name")
    if not album_name:
        return None
    artist_name = candidate.get("artist_name")
    href = f"/music/albums/{quote(str(album_name), safe='')}"
    if artist_name:
        href = f"{href}?artist={quote(str(artist_name), safe='')}"
    return MusicSearchResult(
        kind="album",
        label=str(album_name),
        subtitle=str(artist_name) if artist_name else None,
        href=href,
        play_events=int(candidate.get("play_events") or 0),
        total_ms=int(candidate.get("total_ms") or 0),
        album_name=str(album_name),
        artist_name=str(artist_name) if artist_name else None,
    )


def _artist_result(candidate: dict) -> MusicSearchResult | None:
    artist_name = candidate.get("artist_name") or candidate.get("name")
    if not artist_name:
        return None
    play_events = int(candidate.get("play_events") or 0)
    return MusicSearchResult(
        kind="artist",
        label=str(artist_name),
        subtitle=_plays_text(play_events),
        href=f"/music/artists/{quote(str(artist_name), safe='')}",
        play_events=play_events,
        total_ms=int(candidate.get("total_ms") or 0),
        artist_name=str(artist_name),
    )


def _convert(kind: EntityType, candidate: dict) -> MusicSearchResult | None:
    if kind == "track":
        return _track_result(candidate)
    if kind == "album":
        return _album_result(candidate)
    return _artist_result(candidate)


def search_music_entities(
    conn: sqlite3.Connection,
    *,
    query: str,
    kinds: Iterable[str] | None = None,
    limit_per_type: int = 5,
) -> MusicSearchResponse:
    bounded_limit = _bounded_limit(limit_per_type)
    selected_kinds = _valid_kinds(kinds)

    grouped: dict[EntityType, list[MusicSearchResult]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    if not query.strip():
        return MusicSearchResponse(
            query=query,
            limit_per_type=bounded_limit,
            total=0,
            tracks=[],
            albums=[],
            artists=[],
        )

    for kind in selected_kinds:
        resolved = resolve_entities(conn, query=query, entity_type=kind, limit=bounded_limit)
        rows = []
        for candidate in resolved.get("candidates", []):
            item = _convert(kind, candidate)
            if item is not None:
                rows.append(item)
        grouped[kind] = rows

    return MusicSearchResponse(
        query=query,
        limit_per_type=bounded_limit,
        total=sum(len(items) for items in grouped.values()),
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )
```

- [x] **Step 5: Run the unit test to verify it passes**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_music_search_service.py -v
```

Expected: PASS, 5 tests.

- [ ] **Step 6: Commit Task 1 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add backend/models/music_search.py backend/services/music_search_service.py backend/tests/unit/test_music_search_service.py
git commit -m "feat: add local music search service"
```

---

## Task 2: Backend API Contract

**Files:**
- Modify: `backend/api/music.py`
- Create: `backend/tests/contract/test_music_search_api.py`
- Modify if required by local import style: `scripts/api_smoke_probe.py`
- Modify if required by OpenAPI coverage audit: `scripts/openapi_operation_audit.py`

- [x] **Step 1: Write the API contract test**

Create `backend/tests/contract/test_music_search_api.py`:

```python
from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_conn
from backend.main import app

pytestmark = pytest.mark.contract


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );

        INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Olivia Rodrigo');
        INSERT INTO albums(album_id, album_name, artist_id) VALUES (10, 'GUTS', 1);
        INSERT INTO tracks(track_id, track_name, artist_id, album_id, duration_ms) VALUES
            (100, 'vampire', 1, 10, 219724);
        INSERT INTO plays(play_id, track_id, ms_played, source_album_id) VALUES
            (1, 100, 200000, NULL),
            (2, 100, 190000, NULL);
        """
    )
    return conn


@pytest.fixture
def client() -> Iterator[TestClient]:
    conn = _conn()

    def override_get_conn() -> Iterator[sqlite3.Connection]:
        yield conn

    app.dependency_overrides[get_conn] = override_get_conn
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
        conn.close()


def test_music_search_endpoint_returns_grouped_results(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp"})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "vamp"
    assert data["limit_per_type"] == 5
    assert data["total"] == 1
    assert data["tracks"][0]["label"] == "vampire"
    assert data["tracks"][0]["href"] == "/music/tracks/100"
    assert data["albums"] == []
    assert data["artists"] == []
    assert response.headers["x-request-id"]


def test_music_search_endpoint_accepts_kind_filter(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "guts", "kind": "album"})

    assert response.status_code == 200
    data = response.json()
    assert data["tracks"] == []
    assert data["albums"][0]["href"] == "/music/albums/GUTS?artist=Olivia%20Rodrigo"
    assert data["artists"] == []


def test_music_search_endpoint_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp", "limit_per_type": 50})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_music_search_endpoint_rejects_invalid_kind(client: TestClient) -> None:
    response = client.get("/api/music/search", params={"q": "vamp", "kind": "playlist"})

    assert response.status_code == 422
    assert response.headers["x-request-id"]
```

- [x] **Step 2: Run the contract test to verify it fails**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_music_search_api.py -v
```

Expected: FAIL with 404 for `/api/music/search`.

- [x] **Step 3: Add the API endpoint**

Modify `backend/api/music.py`:

```python
from backend.models.music_search import MusicSearchResponse
from backend.services.music_search_service import search_music_entities
from typing import Literal
```

Add the route after `PlayDateEntry` and before `/tracks/{track_id}/stats` so the static route is registered before dynamic music routes:

```python
@router.get("/search", response_model=MusicSearchResponse)
def music_search(
    q: str = Query(default="", max_length=120, description="Local track, album, or artist query"),
    kind: Literal["track", "album", "artist"] | None = Query(
        default=None,
        description="Optional entity kind filter",
    ),
    limit_per_type: int = Query(default=5, ge=1, le=10),
    conn: Connection = Depends(get_conn),
):
    return search_music_entities(
        conn,
        query=q,
        kinds=(kind,) if kind else None,
        limit_per_type=limit_per_type,
    )
```

- [x] **Step 4: Run the contract test to verify it passes**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/contract/test_music_search_api.py -v
```

Expected: PASS, 4 tests.

- [x] **Step 5: Check OpenAPI operation/accounting impact**

Run:

```bash
source .venv/bin/activate && .venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json
```

Expected: either PASS with 0 unaccounted operations, or a clear unaccounted entry for `/api/music/search`.

If the audit reports `/api/music/search` as unaccounted, add it to the safe GET smoke list using the existing pattern in `scripts/api_smoke_probe.py` and the operation audit mapping. The smoke request should use:

```text
/api/music/search?q=a&limit_per_type=3
```

- [x] **Step 6: Add and run API smoke for the new route**

Add the new case to `DEFAULT_SAFE_GET_CASES` in `scripts/api_smoke_probe.py` near the existing music cases:

```python
SmokeCase("music_search", "/api/music/search", {"q": "a", "limit_per_type": 3}),
```

Then run the full smoke script:

```bash
source .venv/bin/activate && .venv/bin/python scripts/api_smoke_probe.py
```

Expected: PASS for all safe GET cases, including `music_search`, and OpenAPI GET coverage remains 0 unaccounted.

- [ ] **Step 7: Commit Task 2 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add backend/api/music.py backend/tests/contract/test_music_search_api.py scripts/api_smoke_probe.py scripts/openapi_operation_audit.py
git commit -m "feat: expose local music search api"
```

---

## Task 3: Frontend Data Layer And Types

**Files:**
- Create: `frontend/src/types/music-search.ts`
- Modify: `frontend/src/api/query-keys.ts`
- Modify: `frontend/src/hooks/useAnalysis.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/tests/music-search-data.test.tsx`

- [x] **Step 1: Write frontend data-layer tests**

Create `frontend/src/tests/music-search-data.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/api/query-keys'
import { useMusicSearch } from '@/hooks/useAnalysis'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    get: (...args: unknown[]) => mocks.get(...args),
  },
}))

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('music search data layer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('builds stable query keys for music search', () => {
    expect(queryKeys.music.search({ q: 'vamp', kind: 'track', limit_per_type: 5 })).toEqual([
      'music',
      'search',
      { q: 'vamp', kind: 'track', limit_per_type: 5 },
    ])
  })

  it('does not request for short blank input', () => {
    const client = createClient()

    const { result } = renderHook(() => useMusicSearch(' ', { limitPerType: 5 }), {
      wrapper: wrapperFor(client),
    })

    expect(result.current.data).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it('fetches /music/search with trimmed query and limit', async () => {
    mocks.get.mockResolvedValue({
      query: 'vamp',
      limit_per_type: 5,
      total: 1,
      tracks: [{ kind: 'track', label: 'vampire', href: '/music/tracks/100' }],
      albums: [],
      artists: [],
    })
    const client = createClient()

    const { result } = renderHook(() => useMusicSearch('  vamp  ', { limitPerType: 5 }), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.data?.total).toBe(1))
    expect(mocks.get).toHaveBeenCalledWith('/music/search', {
      q: 'vamp',
      limit_per_type: 5,
    })
  })

  it('passes a single kind filter to the API client', async () => {
    mocks.get.mockResolvedValue({
      query: 'guts',
      limit_per_type: 5,
      total: 1,
      tracks: [],
      albums: [{ kind: 'album', label: 'GUTS', href: '/music/albums/GUTS?artist=Olivia%20Rodrigo' }],
      artists: [],
    })
    const client = createClient()

    renderHook(() => useMusicSearch('guts', { kind: 'album', limitPerType: 5 }), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(mocks.get).toHaveBeenCalledWith('/music/search', {
      q: 'guts',
      kind: 'album',
      limit_per_type: 5,
    })
  })
})
```

- [x] **Step 2: Run the frontend test to verify it fails**

Run:

```bash
cd frontend && npm test -- music-search-data.test.tsx
```

Expected: FAIL because `queryKeys.music.search` and `useMusicSearch` do not exist.

- [x] **Step 3: Add frontend types**

Create `frontend/src/types/music-search.ts`:

```ts
export type MusicSearchKind = 'track' | 'album' | 'artist'

export interface MusicSearchResult {
  kind: MusicSearchKind
  label: string
  subtitle?: string | null
  href: string
  play_events: number
  total_ms: number
  track_id?: number | null
  album_name?: string | null
  artist_name?: string | null
  cover_url?: string | null
}

export interface MusicSearchResponse {
  query: string
  limit_per_type: number
  total: number
  tracks: MusicSearchResult[]
  albums: MusicSearchResult[]
  artists: MusicSearchResult[]
}
```

- [x] **Step 4: Add the query key**

Modify the `music` namespace in `frontend/src/api/query-keys.ts`:

```ts
search: (params: Record<string, unknown>) => ['music', 'search', params] as const,
```

Place it before `artistDetail` so search appears before detail-specific keys.

- [x] **Step 5: Add the hook**

Modify imports in `frontend/src/hooks/useAnalysis.ts`:

```ts
import type { MusicSearchKind, MusicSearchResponse } from '@/types/music-search'
```

Add this helper near other API helpers:

```ts
function musicSearchParams(
  query: string,
  options: { kind?: MusicSearchKind; limitPerType?: number } = {},
): Record<string, string | number> {
  const params: Record<string, string | number> = {
    q: query.trim(),
    limit_per_type: options.limitPerType ?? 5,
  }
  if (options.kind) {
    params.kind = options.kind
  }
  return params
}
```

Add this hook near other exported query hooks:

```ts
export function useMusicSearch(
  query: string,
  options: { kind?: MusicSearchKind; limitPerType?: number } = {},
) {
  const trimmed = query.trim()
  const params = musicSearchParams(trimmed, options)
  const enabled = trimmed.length >= 1
  const searchQuery = useQuery({
    queryKey: queryKeys.music.search(params),
    queryFn: () => api.get<MusicSearchResponse>('/music/search', params),
    enabled,
  })

  return {
    data: searchQuery.data ?? null,
    loading: enabled ? searchQuery.isLoading : false,
    error: errorMessage(searchQuery.error),
    refetch: () => void searchQuery.refetch(),
  }
}
```

Add this object for direct calls from future code that prefers promise APIs:

```ts
export const musicSearchApi = {
  search: (
    query: string,
    options: { kind?: MusicSearchKind; limitPerType?: number } = {},
  ) => {
    const params = musicSearchParams(query, options)
    return queryClient.ensureQueryData({
      queryKey: queryKeys.music.search(params),
      queryFn: () => api.get<MusicSearchResponse>('/music/search', params),
    })
  },
}
```

- [x] **Step 6: Re-export types**

Modify `frontend/src/lib/api.ts`:

```ts
export type { MusicSearchKind, MusicSearchResult, MusicSearchResponse } from '@/types/music-search'
```

- [x] **Step 7: Run frontend data-layer tests**

Run:

```bash
cd frontend && npm test -- music-search-data.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add frontend/src/types/music-search.ts frontend/src/api/query-keys.ts frontend/src/hooks/useAnalysis.ts frontend/src/lib/api.ts frontend/src/tests/music-search-data.test.tsx
git commit -m "feat: add music search query layer"
```

---

## Task 4: Full Music Search Page

**Files:**
- Create: `frontend/src/features/music/search/musicSearchUtils.ts`
- Create: `frontend/src/features/music/search/MusicSearchResults.tsx`
- Create: `frontend/src/features/music/search/MusicSearchPage.tsx`
- Create: `frontend/src/pages/MusicSearchPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/routeContext.ts`
- Create: `frontend/src/tests/music-search-components.test.tsx`
- Modify: `frontend/src/tests/masthead-route-context.test.ts`
- Modify: `frontend/src/tests/phase5-architecture.test.ts`

- [x] **Step 1: Write component tests for grouped results**

Create `frontend/src/tests/music-search-components.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { MusicSearchResults } from '@/features/music/search/MusicSearchResults'
import type { MusicSearchResponse } from '@/types/music-search'

const response: MusicSearchResponse = {
  query: 'vamp',
  limit_per_type: 5,
  total: 3,
  tracks: [
    {
      kind: 'track',
      label: 'vampire',
      subtitle: 'Olivia Rodrigo · GUTS',
      href: '/music/tracks/100',
      play_events: 2,
      total_ms: 390000,
      track_id: 100,
      album_name: 'GUTS',
      artist_name: 'Olivia Rodrigo',
    },
  ],
  albums: [
    {
      kind: 'album',
      label: 'GUTS',
      subtitle: 'Olivia Rodrigo',
      href: '/music/albums/GUTS?artist=Olivia%20Rodrigo',
      play_events: 3,
      total_ms: 570000,
      album_name: 'GUTS',
      artist_name: 'Olivia Rodrigo',
    },
  ],
  artists: [
    {
      kind: 'artist',
      label: 'Olivia Rodrigo',
      subtitle: '3 次播放',
      href: '/music/artists/Olivia%20Rodrigo',
      play_events: 3,
      total_ms: 570000,
      artist_name: 'Olivia Rodrigo',
    },
  ],
}

describe('MusicSearchResults', () => {
  it('renders grouped track album and artist links', () => {
    render(
      <MemoryRouter>
        <MusicSearchResults data={response} />
      </MemoryRouter>,
    )

    const tracks = screen.getByRole('region', { name: '歌曲结果' })
    expect(within(tracks).getByRole('link', { name: /vampire/ })).toHaveAttribute('href', '/music/tracks/100')

    const albums = screen.getByRole('region', { name: '专辑结果' })
    expect(within(albums).getByRole('link', { name: /GUTS/ })).toHaveAttribute(
      'href',
      '/music/albums/GUTS?artist=Olivia%20Rodrigo',
    )

    const artists = screen.getByRole('region', { name: '艺人结果' })
    expect(within(artists).getByRole('link', { name: /Olivia Rodrigo/ })).toHaveAttribute(
      'href',
      '/music/artists/Olivia%20Rodrigo',
    )
  })

  it('renders a stable empty state', () => {
    render(
      <MemoryRouter>
        <MusicSearchResults
          data={{ query: 'missing', limit_per_type: 5, total: 0, tracks: [], albums: [], artists: [] }}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('没有找到匹配的本地音乐记录')).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Write route context and architecture tests**

Modify `frontend/src/tests/masthead-route-context.test.ts`:

```ts
it('maps music search as a standalone utility context', () => {
  expect(getMastheadRouteContext('/music/search', '?q=vamp')).toEqual({
    activeNavTo: null,
    contextSegments: ['音乐查找'],
    title: null,
    showMobileContext: false,
  })
})
```

Modify `frontend/src/tests/phase5-architecture.test.ts` with an assertion near other route-container checks:

```ts
const musicSearchPageSource = fs.readFileSync(path.join(root, 'src/pages/MusicSearchPage.tsx'), 'utf8')

it('keeps MusicSearchPage as a thin route container', () => {
  expect(musicSearchPageSource.split('\n').length).toBeLessThanOrEqual(30)
})
```

- [x] **Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- music-search-components.test.tsx masthead-route-context.test.ts phase5-architecture.test.ts
```

Expected: FAIL because search components/page and route context do not exist yet.

- [x] **Step 4: Add search UI helpers**

Create `frontend/src/features/music/search/musicSearchUtils.ts`:

```ts
import type { MusicSearchKind, MusicSearchResponse, MusicSearchResult } from '@/types/music-search'

export const MUSIC_SEARCH_KIND_LABEL: Record<MusicSearchKind, string> = {
  track: '歌曲',
  album: '专辑',
  artist: '艺人',
}

export const MUSIC_SEARCH_GROUP_LABEL: Record<MusicSearchKind, string> = {
  track: '歌曲结果',
  album: '专辑结果',
  artist: '艺人结果',
}

export function musicSearchGroups(data: MusicSearchResponse): Array<{
  kind: MusicSearchKind
  label: string
  items: MusicSearchResult[]
}> {
  return [
    { kind: 'track', label: MUSIC_SEARCH_GROUP_LABEL.track, items: data.tracks },
    { kind: 'album', label: MUSIC_SEARCH_GROUP_LABEL.album, items: data.albums },
    { kind: 'artist', label: MUSIC_SEARCH_GROUP_LABEL.artist, items: data.artists },
  ]
}

export function compactPlayCount(item: MusicSearchResult): string {
  return `${new Intl.NumberFormat('zh-CN').format(item.play_events)} 次`
}
```

- [x] **Step 5: Add grouped results component**

Create `frontend/src/features/music/search/MusicSearchResults.tsx`:

```tsx
import { Link } from 'react-router-dom'
import { Disc3, Mic2, Music2 } from 'lucide-react'

import { displayName } from '@/lib/chinese'
import type { MusicSearchKind, MusicSearchResponse, MusicSearchResult } from '@/types/music-search'
import { compactPlayCount, musicSearchGroups } from './musicSearchUtils'

function iconFor(kind: MusicSearchKind) {
  if (kind === 'track') return <Music2 className="h-4 w-4" aria-hidden="true" />
  if (kind === 'album') return <Disc3 className="h-4 w-4" aria-hidden="true" />
  return <Mic2 className="h-4 w-4" aria-hidden="true" />
}

function ResultRow({ item }: { item: MusicSearchResult }) {
  return (
    <Link
      to={item.href}
      className="group flex min-h-[58px] items-center gap-3 border-b border-border/60 px-1 py-3 transition-colors last:border-b-0 hover:text-accent-foreground"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-[8px] border border-border bg-muted/40 text-muted-foreground transition-colors group-hover:text-accent-foreground">
        {iconFor(item.kind)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-sans text-[14px] font-semibold">
          {displayName(item.label)}
        </span>
        {item.subtitle ? (
          <span className="block truncate font-sans text-[12px] text-muted-foreground">
            {displayName(item.subtitle)}
          </span>
        ) : null}
      </span>
      <span className="shrink-0 font-sans text-[11px] tabular-nums text-muted-foreground">
        {compactPlayCount(item)}
      </span>
    </Link>
  )
}

export function MusicSearchResults({ data }: { data: MusicSearchResponse }) {
  if (data.total === 0) {
    return (
      <div className="rounded-[8px] border border-dashed border-border px-4 py-8 text-center font-sans text-[13px] text-muted-foreground">
        没有找到匹配的本地音乐记录
      </div>
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {musicSearchGroups(data).map((group) => (
        <section
          key={group.kind}
          aria-label={group.label}
          className="min-w-0 rounded-[8px] border border-border bg-card/60 p-4"
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-serif text-xl font-semibold">{group.label.replace('结果', '')}</h2>
            <span className="font-sans text-[11px] tabular-nums text-muted-foreground">
              {group.items.length}
            </span>
          </div>
          {group.items.length > 0 ? (
            <div>
              {group.items.map((item) => (
                <ResultRow key={`${item.kind}-${item.href}`} item={item} />
              ))}
            </div>
          ) : (
            <p className="py-5 font-sans text-[13px] text-muted-foreground">暂无匹配</p>
          )}
        </section>
      ))}
    </div>
  )
}
```

- [x] **Step 6: Add the full page feature**

Create `frontend/src/features/music/search/MusicSearchPage.tsx`:

```tsx
import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { GlassCard } from '@/components/shared/GlassCard'
import { Skeleton } from '@/components/ui/skeleton'
import { useMusicSearch } from '@/hooks/useAnalysis'
import { MusicSearchResults } from './MusicSearchResults'

export function MusicSearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') ?? ''
  const [query, setQuery] = useState(initialQuery)
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery)
  const { data, loading, error } = useMusicSearch(debouncedQuery, { limitPerType: 10 })

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = query.trim()
      setDebouncedQuery(next)
      const params = new URLSearchParams()
      if (next) params.set('q', next)
      setSearchParams(params, { replace: true })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [query, setSearchParams])

  return (
    <div className="space-y-7">
      <div>
        <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">
          Music Finder
        </p>
        <h1 className="font-serif text-[40px] font-bold leading-tight">音乐查找</h1>
      </div>

      <GlassCard className="p-5">
        <label htmlFor="music-search-page-input" className="sr-only">
          搜索歌曲、专辑或艺人
        </label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            id="music-search-page-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索歌曲、专辑或艺人"
            className="h-11 w-full rounded-[8px] border border-border bg-background pl-10 pr-3 font-sans text-[14px] outline-none transition-colors focus:border-accent-foreground"
          />
        </div>
      </GlassCard>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-[280px] rounded-[8px]" />
          <Skeleton className="h-[280px] rounded-[8px]" />
          <Skeleton className="h-[280px] rounded-[8px]" />
        </div>
      ) : error ? (
        <div className="rounded-[8px] border border-destructive/30 bg-destructive/5 px-4 py-3 font-sans text-[13px] text-destructive">
          {error}
        </div>
      ) : data ? (
        <MusicSearchResults data={data} />
      ) : (
        <div className="rounded-[8px] border border-dashed border-border px-4 py-8 text-center font-sans text-[13px] text-muted-foreground">
          输入关键词后查看本地音乐记录
        </div>
      )}
    </div>
  )
}
```

- [x] **Step 7: Add route container**

Create `frontend/src/pages/MusicSearchPage.tsx`:

```tsx
import { MusicSearchPage as MusicSearchExperience } from '@/features/music/search/MusicSearchPage'

export function MusicSearchPage() {
  return <MusicSearchExperience />
}
```

- [x] **Step 8: Wire the route before dynamic music detail routes**

Modify `frontend/src/App.tsx`:

```tsx
const MusicSearchPage = lazy(() => import('@/pages/MusicSearchPage').then((m) => ({ default: m.MusicSearchPage })))
```

Add the route before `/music/tracks/:trackId`:

```tsx
<Route path="/music/search" element={<Suspense fallback={<RouteFallback />}><MusicSearchPage /></Suspense>} />
```

- [x] **Step 9: Add route context**

Modify `frontend/src/components/layout/routeContext.ts` before detail-route checks:

```ts
if (pathname === '/music/search') {
  return {
    activeNavTo: null,
    contextSegments: ['音乐查找'],
    title: null,
    showMobileContext: false,
  }
}
```

- [x] **Step 10: Run page tests**

Run:

```bash
cd frontend && npm test -- music-search-components.test.tsx masthead-route-context.test.ts phase5-architecture.test.ts
```

Expected: PASS.

- [ ] **Step 11: Commit Task 4 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add frontend/src/features/music/search frontend/src/pages/MusicSearchPage.tsx frontend/src/App.tsx frontend/src/components/layout/routeContext.ts frontend/src/tests/music-search-components.test.tsx frontend/src/tests/masthead-route-context.test.ts frontend/src/tests/phase5-architecture.test.ts
git commit -m "feat: add music search page"
```

---

## Task 5: Masthead Global Search Dialog

**Files:**
- Create: `frontend/src/features/music/search/MusicSearchDialog.tsx`
- Modify: `frontend/src/components/layout/Masthead.tsx`
- Modify: `frontend/src/tests/masthead-navigation.test.tsx`
- Create: `frontend/src/tests/music-search-flow.test.tsx`

- [x] **Step 1: Write Masthead and dialog tests**

Modify `frontend/src/tests/masthead-navigation.test.tsx`:

```tsx
expect(screen.getByRole('button', { name: '搜索音乐详情' })).toBeInTheDocument()
expect(screen.getByRole('link', { name: '偏好设置' })).toHaveAttribute('href', '/settings')
```

Keep the existing expectation that primary nav has five destinations.

Create `frontend/src/tests/music-search-flow.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MusicSearchDialog } from '@/features/music/search/MusicSearchDialog'

const mocks = vi.hoisted(() => ({
  useMusicSearch: vi.fn(),
}))

vi.mock('@/hooks/useAnalysis', () => ({
  useMusicSearch: (...args: unknown[]) => mocks.useMusicSearch(...args),
}))

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    )
  }
}

describe('MusicSearchDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.useMusicSearch.mockReturnValue({
      data: null,
      loading: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('opens from the utility button and focuses the search field', async () => {
    const user = userEvent.setup()

    render(<MusicSearchDialog />, { wrapper: wrapper() })

    await user.click(screen.getByRole('button', { name: '搜索音乐详情' }))

    expect(screen.getByRole('dialog', { name: '搜索音乐详情' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '搜索歌曲、专辑或艺人' })).toHaveFocus()
  })

  it('renders grouped results and full result link', async () => {
    const user = userEvent.setup()
    mocks.useMusicSearch.mockReturnValue({
      data: {
        query: 'vamp',
        limit_per_type: 5,
        total: 1,
        tracks: [
          {
            kind: 'track',
            label: 'vampire',
            subtitle: 'Olivia Rodrigo · GUTS',
            href: '/music/tracks/100',
            play_events: 2,
            total_ms: 390000,
          },
        ],
        albums: [],
        artists: [],
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<MusicSearchDialog />, { wrapper: wrapper() })

    await user.click(screen.getByRole('button', { name: '搜索音乐详情' }))
    await user.type(screen.getByRole('textbox', { name: '搜索歌曲、专辑或艺人' }), 'vamp')

    await waitFor(() => expect(screen.getByRole('link', { name: /vampire/ })).toHaveAttribute('href', '/music/tracks/100'))
    expect(screen.getByRole('link', { name: '查看全部结果' })).toHaveAttribute('href', '/music/search?q=vamp')
  })
})
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- masthead-navigation.test.tsx music-search-flow.test.tsx
```

Expected: FAIL because `MusicSearchDialog` does not exist and Masthead has no search button.

- [x] **Step 3: Add the dialog component**

Create `frontend/src/features/music/search/MusicSearchDialog.tsx`:

```tsx
import { Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useMusicSearch } from '@/hooks/useAnalysis'
import { cn } from '@/lib/utils'
import { MusicSearchResults } from './MusicSearchResults'

export function MusicSearchDialog({ className }: { className?: string }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const { data, loading, error } = useMusicSearch(debouncedQuery, { limitPerType: 5 })

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 180)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(timer)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  return (
    <>
      <button
        type="button"
        aria-label="搜索音乐详情"
        onClick={() => setOpen(true)}
        className={cn(
          'inline-flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors duration-200 hover:bg-muted/70 hover:text-foreground',
          className,
        )}
      >
        <Search className="h-4.5 w-4.5" aria-hidden="true" />
      </button>

      {open ? (
        <div className="fixed inset-0 z-[80] bg-background/70 px-4 py-16 backdrop-blur-sm sm:px-8" role="presentation">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="搜索音乐详情"
            className="mx-auto flex max-h-[78vh] w-full max-w-[820px] flex-col overflow-hidden rounded-[8px] border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center gap-3 border-b border-border px-4 py-3">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <label htmlFor="music-search-dialog-input" className="sr-only">
                搜索歌曲、专辑或艺人
              </label>
              <input
                ref={inputRef}
                id="music-search-dialog-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索歌曲、专辑或艺人"
                className="h-10 min-w-0 flex-1 bg-transparent font-sans text-[15px] outline-none"
              />
              <Button type="button" variant="ghost" size="icon" aria-label="关闭搜索" onClick={() => setOpen(false)}>
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>

            <div className="min-h-0 overflow-y-auto p-4">
              {loading ? (
                <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">正在搜索</p>
              ) : error ? (
                <p className="rounded-[8px] border border-destructive/30 bg-destructive/5 px-4 py-3 font-sans text-[13px] text-destructive">
                  {error}
                </p>
              ) : data ? (
                <MusicSearchResults data={data} />
              ) : (
                <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">
                  输入关键词后快速打开歌曲、专辑或艺人详情
                </p>
              )}
            </div>

            <div className="flex items-center justify-end border-t border-border px-4 py-3">
              <Link
                to={`/music/search${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''}`}
                className="font-sans text-[13px] font-semibold text-accent-foreground"
                onClick={() => setOpen(false)}
              >
                查看全部结果
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
```

- [x] **Step 4: Mount the dialog in Masthead**

Modify `frontend/src/components/layout/Masthead.tsx`:

```tsx
import { MusicSearchDialog } from '@/features/music/search/MusicSearchDialog'
```

Render it before `ThemeToggle`:

```tsx
<MusicSearchDialog />
<ThemeToggle />
```

- [x] **Step 5: Run dialog and navigation tests**

Run:

```bash
cd frontend && npm test -- masthead-navigation.test.tsx music-search-flow.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add frontend/src/features/music/search/MusicSearchDialog.tsx frontend/src/components/layout/Masthead.tsx frontend/src/tests/masthead-navigation.test.tsx frontend/src/tests/music-search-flow.test.tsx
git commit -m "feat: add global music search quick open"
```

---

## Task 6: Smoke Tests, Documentation, And Verification

**Files:**
- Modify: `scripts/frontend_route_smoke.mjs`
- Modify: `scripts/frontend_interaction_smoke.mjs`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: Add route smoke coverage**

Modify the default route list in `scripts/frontend_route_smoke.mjs` to include:

```js
'/music/search',
```

The marker check for `/music/search` should accept visible text `音乐查找`.

- [x] **Step 2: Add interaction smoke scenario**

Modify `scripts/frontend_interaction_smoke.mjs` by adding a scenario named `music-search-quick-open`:

Add it to `DEFAULT_SCENARIOS` after `settings-data-import`:

```js
'music-search-quick-open',
```

Add it to the help text scenario list:

```text
  music-search-quick-open  Open Masthead music search and verify the quick-open dialog
```

Add this helper near `clickText()`:

```js
async function clickByAriaLabel(client, label, waitMs) {
  const clicked = await evaluate(client, `
    (() => {
      const label = ${JSON.stringify(label)};
      const el = Array.from(document.querySelectorAll('button, a, [role="button"]'))
        .find((item) => item.getAttribute('aria-label') === label);
      if (!el) return false;
      el.scrollIntoView({ block: 'center', inline: 'center' });
      el.click();
      return true;
    })();
  `)
  if (!clicked) throw new Error(`Clickable aria-label not found: ${label}`)
  await sleep(Math.min(250, waitMs))
}
```

Add the scenario to `SCENARIOS`:

```js
'music-search-quick-open': async ({ client, baseUrl, waitMs }) => {
  await navigate(client, baseUrl, '/', waitMs)
  await clickByAriaLabel(client, '搜索音乐详情', waitMs)
  await waitForText(client, '输入关键词后快速打开歌曲、专辑或艺人详情', waitMs)
  const filled = await evaluate(client, `
    (() => {
      const input = document.querySelector('#music-search-dialog-input');
      if (!input) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, 'a');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    })();
  `)
  if (!filled) throw new Error('Music search input not found')
  await waitForText(client, '查看全部结果', waitMs)
},
```

- [x] **Step 3: Update documentation**

Add this capability note to `README.md`:

```markdown
- 音乐详情可通过全局“搜索音乐详情”入口直接查找本地歌曲、专辑和艺人，搜索结果会跳转到既有 `/music/tracks/*`、`/music/albums/*`、`/music/artists/*` 详情页。
```

Add this implementation note to `AGENTS.md` and `CLAUDE.md` near the navigation/detail-page summary:

```markdown
**音乐查找入口**：`/music/search` 与 Masthead 搜索按钮提供本地歌曲/专辑/艺人直接查找，后端使用只读 `/api/music/search`，结果只来自本地播放记录并跳转到既有音乐详情页。
```

Add this changelog entry to `docs/CHANGELOG.md`:

```markdown
- 新增本地音乐查找入口：Masthead 可直接搜索歌曲、专辑、艺人并打开音乐详情页，同时提供 `/music/search` 全页结果。
```

Add a matching index note in `docs/README.md` if it contains a feature index.

- [x] **Step 4: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_music_search_service.py backend/tests/contract/test_music_search_api.py -v
```

Expected: PASS.

- [x] **Step 5: Run focused frontend verification**

Run:

```bash
cd frontend && npm test -- music-search-data.test.tsx music-search-components.test.tsx music-search-flow.test.tsx masthead-navigation.test.tsx masthead-route-context.test.ts phase5-architecture.test.ts
```

Expected: PASS.

- [x] **Step 6: Run production build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS with no TypeScript errors.

- [x] **Step 7: Run lint and formatting checks**

Note: `ruff check backend/` passed. Full `ruff format --check backend/` is blocked by three pre-existing unrelated files (`backend/domains/billboard/year_end.py`, `backend/domains/playback/records_output.py`, `backend/domains/playback/records_time.py`); the touched backend files pass targeted `ruff format --check`.

Run:

```bash
source .venv/bin/activate && ruff check backend/
source .venv/bin/activate && ruff format --check backend/
git diff --check
```

Expected: PASS.

- [x] **Step 8: Run app-level smoke when local servers are available**

Start services if not already running:

```bash
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --reload --reload-dir backend
cd frontend && npm run dev
```

Then run:

```bash
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
```

Expected: PASS. Confirm `/music/search` has no horizontal overflow at 390px and the search dialog does not overlap Masthead controls incoherently.

- [ ] **Step 9: Optional full gate before release**

Run:

```bash
sh scripts/phase5_check.sh
```

Expected: PASS.

For release-quality validation with already-running backend/frontend/preview:

```bash
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173
```

Expected: PASS.

- [ ] **Step 10: Commit Task 6 when committing is allowed**

Run only after the user confirms commits are desired:

```bash
git add scripts/frontend_route_smoke.mjs scripts/frontend_interaction_smoke.mjs README.md AGENTS.md CLAUDE.md docs/README.md docs/CHANGELOG.md
git commit -m "docs: document music search quick open"
```

---

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
