"""Stable keys shared by music-search candidates and semantic context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

MusicSearchEntityKeyKind = Literal["track", "album", "album_project", "artist"]

_ENTITY_KEY_PATTERN = re.compile(r"^(track|album|album_project|artist):([1-9][0-9]*)$")


@dataclass(frozen=True)
class ParsedMusicSearchEntityKey:
    kind: MusicSearchEntityKeyKind
    entity_id: int


def make_music_search_entity_key(kind: MusicSearchEntityKeyKind, entity_id: int) -> str:
    if kind not in {"track", "album", "album_project", "artist"}:
        raise ValueError(f"Unsupported music-search entity kind: {kind}")
    if isinstance(entity_id, bool) or int(entity_id) <= 0:
        raise ValueError("Music-search entity ids must be positive integers")
    return f"{kind}:{int(entity_id)}"


def parse_music_search_entity_key(value: str) -> ParsedMusicSearchEntityKey:
    match = _ENTITY_KEY_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("Invalid music-search entity key")
    return ParsedMusicSearchEntityKey(
        kind=cast(MusicSearchEntityKeyKind, match.group(1)),
        entity_id=int(match.group(2)),
    )
