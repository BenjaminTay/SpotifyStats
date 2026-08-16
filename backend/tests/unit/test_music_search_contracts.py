from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domains.music_search.contracts import (
    make_music_search_entity_key,
    parse_music_search_entity_key,
)
from backend.models.music_search import (
    MusicSearchCandidateResponse,
    MusicSearchCandidateResult,
    MusicSearchContextItem,
    MusicSearchContextResponse,
    MusicSearchKindTotals,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("kind", "entity_id", "expected"),
    [
        ("track", 42, "track:42"),
        ("album", 7, "album:7"),
        ("album_project", 9, "album_project:9"),
        ("artist", 3, "artist:3"),
    ],
)
def test_music_search_entity_key_round_trip(kind, entity_id, expected) -> None:
    entity_key = make_music_search_entity_key(kind, entity_id)
    parsed = parse_music_search_entity_key(entity_key)

    assert entity_key == expected
    assert parsed.kind == kind
    assert parsed.entity_id == entity_id


@pytest.mark.parametrize(
    "value",
    ["", "track", "track:0", "track:-1", "playlist:1", "track:01", " track:1"],
)
def test_music_search_entity_key_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid music-search entity key"):
        parse_music_search_entity_key(value)


def test_candidate_and_context_contracts_are_versioned_and_bounded() -> None:
    candidate = MusicSearchCandidateResult(
        entity_key="album_project:12",
        kind="album",
        label="Example Album",
        href="/music/albums/Example%20Album?artist=Example",
        match_field="label",
        match_quality="exact",
    )
    response = MusicSearchCandidateResponse(
        query="Example Album",
        normalized_query="example album",
        snapshot_status="ready",
        filter_fingerprint="fingerprint",
        total=1,
        total_by_kind=MusicSearchKindTotals(album=1),
        albums=[candidate],
    )
    context = MusicSearchContextResponse(
        snapshot_status="ready",
        filter_fingerprint="fingerprint",
        items={"album_project:12": MusicSearchContextItem(play_events=8, total_ms=120_000)},
    )

    assert response.response_version == "music_search_v2"
    assert response.total_by_kind.album == 1
    assert context.response_version == "music_search_context_v1"
    assert context.items["album_project:12"].play_events == 8


def test_context_contract_rejects_invalid_entity_keys() -> None:
    with pytest.raises(ValidationError):
        MusicSearchContextResponse(
            snapshot_status="ready",
            items={"not-an-entity": MusicSearchContextItem(play_events=0, total_ms=0)},
        )


def test_candidate_contract_rejects_mismatched_entity_key_kind() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        MusicSearchCandidateResult(
            entity_key="artist:12",
            kind="album",
            label="Example Album",
            href="/music/albums/Example%20Album",
            match_field="label",
            match_quality="exact",
        )
