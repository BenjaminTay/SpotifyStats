from dataclasses import dataclass, field


@dataclass
class SearchResult:
    id: int
    title: str
    artist: str
    url: str
    lyrics_state: str = "complete"


@dataclass
class Song:
    id: int
    title: str
    artist: str
    lyrics: str
    url: str = ""
    album_name: str = ""
    cover_url: str = ""
    release_date: str = ""


@dataclass
class AlbumInfo:
    id: int
    name: str
    artist: str
    cover_url: str = ""
    release_date: str = ""
    url: str = ""
    tracks: list[Song] = field(default_factory=list)
