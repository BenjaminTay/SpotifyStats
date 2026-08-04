"""Artist genre resolution across Spotify, curated, external, and AI sources."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

SOURCE_PRIORITY = {
    "curated_seed": 95,
    "external_consensus": 85,
    "musicbrainz": 80,
    "lastfm": 75,
    "wikidata": 70,
    "llm": 55,
}
SOURCE_CONFIDENCE_WEIGHT = {
    "spotify": 1.0,
    "manual_override": 0.95,
    "curated_seed": 0.95,
    "external_consensus": 0.9,
    "musicbrainz": 0.8,
    "lastfm": 0.75,
    "wikidata": 0.7,
    "llm": 0.45,
    "unknown": 0.0,
}
SOURCE_DISPLAY_LABELS = {
    "spotify": "Spotify",
    "manual_override": "manual override",
    "curated_seed": "curated seed",
    "external_consensus": "external consensus",
    "musicbrainz": "MusicBrainz",
    "lastfm": "Last.fm",
    "wikidata": "Wikidata",
    "llm": "LLM",
    "unknown": "unknown",
}
AXIS_METADATA = {
    "style": {
        "label": "风格",
        "interpretation": "声音/风格偏好，可作为主要流派分析。",
    },
    "scene": {
        "label": "场景",
        "interpretation": "语言、地区或音乐市场场景，不等同于声音风格。",
    },
    "context": {
        "label": "语境",
        "interpretation": "播放内容的使用场景或媒介语境，不等同于声音风格。",
    },
    "role": {
        "label": "身份",
        "interpretation": "创作或表演身份标签，不等同于声音风格。",
    },
}
AXIS_ORDER = ("style", "scene", "context", "role")
STATISTICAL_GENRE_CAVEAT = (
    "流派统计使用标准化统计标签，并按 style/scene/context/role 分轴解释；"
    "scene、context、role 不等同于声音风格。Spotify 与本地原始标签保留用于审计，"
    "播放时长只在同一轴的多标签间分摊，各轴独立保留未知；"
    "单一高播放艺人或低可信来源主导的标签需降置信解读。"
)
LOCAL_TABLES = {
    "artist_genre_overrides",
    "artist_genre_sources",
}

STATISTICAL_GENRE_MAP: dict[str, tuple[str, ...]] = {
    "c-pop": ("c-pop",),
    "c pop": ("c-pop",),
    "chinese": ("c-pop",),
    "chinese pop": ("c-pop",),
    "mandopop": ("c-pop",),
    "cantopop": ("c-pop",),
    "hk-pop": ("c-pop",),
    "hong kong pop": ("c-pop",),
    "taiwan pop": ("c-pop",),
    "taiwanese pop": ("c-pop",),
    "hokkien pop": ("c-pop",),
    # Spotify's "malay pop" is too noisy in this library to infer either C-Pop
    # or Southeast Asian Pop. Keep the raw tag for audit, but do not count it.
    "malay pop": (),
    "chinese r&b": ("c-pop", "r&b/soul"),
    "chinese hip hop": ("c-pop", "hip hop/rap"),
    "chinese rock": ("c-pop", "rock/alternative"),
    "chinese indie": ("c-pop", "indie/alternative"),
    "taiwanese indie": ("c-pop", "indie/alternative"),
    "gufeng": ("c-pop",),
    "k-pop": ("k-pop",),
    "korean": ("k-pop",),
    "k-rap": ("k-pop", "hip hop/rap"),
    "k-r&b": ("k-pop", "r&b/soul"),
    "k-indie": ("k-pop", "indie/alternative"),
    "k-ballad": ("k-pop", "pop"),
    "j-pop": ("j-pop",),
    "japanese": ("j-pop",),
    "anime": ("soundtrack/stage",),
    "anison": ("soundtrack/stage",),
    # Vocaloid describes a production/vocal-synthesis ecosystem rather than a
    # reliable sound style or market scene.
    "vocaloid": (),
    "j-r&b": ("j-pop", "r&b/soul"),
    "j-rock": ("j-pop", "rock/alternative"),
    "j-indie": ("j-pop", "indie/alternative"),
    "pop": ("pop",),
    "alt z": ("pop",),
    "art pop": ("pop",),
    "alternative pop": ("pop",),
    "alt-pop": ("pop",),
    "baroque pop": ("pop",),
    "bedroom pop": ("pop",),
    "chamber pop": ("pop",),
    "dance pop": ("pop", "electronic/dance"),
    "dance-pop": ("pop", "electronic/dance"),
    "dark pop": ("pop",),
    "dream pop": ("pop",),
    "electropop": ("pop", "electronic/dance"),
    "europop": ("pop",),
    "french pop": ("pop",),
    "hyperpop": ("pop", "electronic/dance"),
    "indie pop": ("pop", "indie/alternative"),
    "jazz pop": ("pop", "jazz/blues"),
    "latin pop": ("latin", "pop"),
    "pop country": ("pop", "country"),
    "country pop": ("pop", "country"),
    "pop rock": ("pop", "rock/alternative"),
    "pop singer-songwriter": ("pop", "singer-songwriter"),
    "soft pop": ("pop",),
    "swedish pop": ("pop",),
    "teen pop": ("pop",),
    "synth pop": ("electronic/dance",),
    "synth-pop": ("electronic/dance",),
    "synthpop": ("electronic/dance",),
    "singer-songwriter": ("singer-songwriter",),
    "italian singer-songwriter": ("singer-songwriter",),
    "southern gothic": ("folk",),
    "slowcore": ("indie/alternative",),
    "folk": ("folk",),
    "folk pop": ("pop", "folk"),
    "folk rock": ("rock/alternative", "folk"),
    "indie folk": ("indie/alternative", "folk"),
    "ambient folk": ("folk",),
    "country": ("country",),
    "acoustic country": ("country",),
    "americana": ("americana/roots",),
    "bluegrass": ("folk", "americana/roots"),
    "classic country": ("country",),
    "country rock": ("country", "rock/alternative"),
    "honky tonk": ("country",),
    "outlaw country": ("country",),
    "red dirt": ("americana/roots", "country"),
    "texas country": ("country",),
    "traditional country": ("country",),
    "rock": ("rock/alternative",),
    "alt-rock": ("rock/alternative",),
    "alternative rock": ("rock/alternative",),
    "art rock": ("rock/alternative",),
    "blues rock": ("rock/alternative", "jazz/blues"),
    "classic rock": ("rock/alternative",),
    "emo": ("rock/alternative",),
    "garage rock": ("rock/alternative",),
    "grunge": ("rock/alternative",),
    "hard rock": ("rock/alternative",),
    "indie rock": ("rock/alternative", "indie/alternative"),
    "midwest emo": ("rock/alternative",),
    "neo-psychedelic": ("rock/alternative",),
    "post-grunge": ("rock/alternative",),
    "post-punk": ("rock/alternative",),
    "post-punk revival": ("rock/alternative",),
    "psychedelic rock": ("rock/alternative",),
    "punk": ("rock/alternative",),
    "pop punk": ("rock/alternative", "pop"),
    "roots rock": ("rock/alternative", "americana/roots"),
    "shoegaze": ("rock/alternative",),
    "soft rock": ("rock/alternative",),
    "southern rock": ("rock/alternative", "country"),
    "surf rock": ("rock/alternative",),
    "yacht rock": ("rock/alternative",),
    "alternative metal": ("rock/alternative",),
    "heavy metal": ("rock/alternative",),
    "metal": ("rock/alternative",),
    "metalcore": ("rock/alternative",),
    "nu metal": ("rock/alternative", "hip hop/rap"),
    "rap metal": ("rock/alternative", "hip hop/rap"),
    "r&b": ("r&b/soul",),
    "afro r&b": ("r&b/soul", "afrobeats/afropop"),
    "alternative r&b": ("r&b/soul",),
    "christian r&b": ("r&b/soul", "gospel/christian"),
    "contemporary r&b": ("r&b/soul",),
    "classic soul": ("r&b/soul",),
    "disco": ("r&b/soul", "electronic/dance"),
    "funk": ("r&b/soul",),
    "motown": ("r&b/soul",),
    "neo soul": ("r&b/soul",),
    "new jack swing": ("r&b/soul",),
    "northern soul": ("r&b/soul",),
    "philly soul": ("r&b/soul",),
    "pop soul": ("r&b/soul", "pop"),
    "quiet storm": ("r&b/soul",),
    "retro soul": ("r&b/soul",),
    "soul": ("r&b/soul",),
    "trap soul": ("r&b/soul", "hip hop/rap"),
    "hip hop": ("hip hop/rap",),
    "alternative hip hop": ("hip hop/rap",),
    "argentine trap": ("hip hop/rap", "latin"),
    "boom bap": ("hip hop/rap",),
    "chicago drill": ("hip hop/rap",),
    "conscious hip hop": ("hip hop/rap",),
    "drill": ("hip hop/rap",),
    "east coast hip hop": ("hip hop/rap",),
    "gangsta rap": ("hip hop/rap",),
    "grime": ("hip hop/rap",),
    "jazz rap": ("hip hop/rap", "jazz/blues"),
    "melodic rap": ("hip hop/rap",),
    "old school hip hop": ("hip hop/rap",),
    "pop rap": ("hip hop/rap", "pop"),
    "rage rap": ("hip hop/rap",),
    "rap": ("hip hop/rap",),
    "sexy drill": ("hip hop/rap",),
    "southern hip hop": ("hip hop/rap",),
    "trap": ("hip hop/rap",),
    "west coast hip hop": ("hip hop/rap",),
    "dance": ("electronic/dance",),
    "alternative dance": ("electronic/dance", "indie/alternative"),
    "ambient": ("electronic/dance",),
    "bass house": ("electronic/dance",),
    "downtempo": ("electronic/dance",),
    "edm": ("electronic/dance",),
    "edm trap": ("electronic/dance", "hip hop/rap"),
    "electronic": ("electronic/dance",),
    "eurodance": ("electronic/dance",),
    "future bass": ("electronic/dance",),
    "hi-nrg": ("electronic/dance",),
    "house": ("electronic/dance",),
    "italo disco": ("electronic/dance",),
    "melodic bass": ("electronic/dance",),
    "new rave": ("electronic/dance",),
    "slap house": ("electronic/dance",),
    "techno": ("electronic/dance",),
    "tropical house": ("electronic/dance",),
    "trip hop": ("electronic/dance", "hip hop/rap"),
    "musicals": ("soundtrack/stage",),
    "musical theatre": ("soundtrack/stage",),
    "score": ("soundtrack/stage",),
    "soundtrack": ("soundtrack/stage",),
    "show tunes": ("soundtrack/stage",),
    "christmas": ("holiday",),
    "villancicos": ("holiday",),
    "variété française": ("pop",),
    "vallenato": ("latin",),
    "jazz": ("jazz/blues",),
    "acid jazz": ("jazz/blues",),
    "adult standards": ("jazz/blues",),
    "big band": ("jazz/blues",),
    "blues": ("jazz/blues",),
    "classic blues": ("jazz/blues",),
    "cool jazz": ("jazz/blues",),
    "delta blues": ("jazz/blues",),
    "french jazz": ("jazz/blues",),
    "fusion": ("jazz/blues",),
    "indie jazz": ("jazz/blues", "indie/alternative"),
    "jazz funk": ("jazz/blues", "r&b/soul"),
    "jazz fusion": ("jazz/blues",),
    "modern blues": ("jazz/blues",),
    "nu jazz": ("jazz/blues",),
    "smooth jazz": ("jazz/blues",),
    "soul jazz": ("jazz/blues", "r&b/soul"),
    "swing music": ("jazz/blues",),
    "vocal jazz": ("jazz/blues",),
    "baroque": ("classical/instrumental",),
    "chamber music": ("classical/instrumental",),
    "choral": ("classical/instrumental",),
    "classical": ("classical/instrumental",),
    "classical crossover": ("classical/instrumental",),
    "classical piano": ("classical/instrumental",),
    "concerto": ("classical/instrumental",),
    "early music": ("classical/instrumental",),
    "instrumental": ("classical/instrumental",),
    "japanese classical": ("classical/instrumental",),
    "enka": ("j-pop", "traditional/folk"),
    "kayōkyoku": ("j-pop", "traditional/folk"),
    "lo-fi": ("electronic/dance",),
    "new age": ("classical/instrumental",),
    "opera": ("classical/instrumental",),
    "orchestral": ("classical/instrumental",),
    "post-rock instrumental": ("classical/instrumental", "rock/alternative"),
    "latin": ("latin",),
    "bachata": ("latin",),
    "banda": ("latin",),
    "bolero": ("latin",),
    "chanson": ("pop",),
    "colombian pop": ("latin", "pop"),
    "corrido": ("latin",),
    "corridos bélicos": ("latin",),
    "corridos tumbados": ("latin",),
    "cumbia norteña": ("latin",),
    "dembow": ("latin",),
    "grupera": ("latin",),
    "latin hip hop": ("latin", "hip hop/rap"),
    "latin rock": ("latin", "rock/alternative"),
    "mariachi": ("latin",),
    "música mexicana": ("latin",),
    "norteño": ("latin",),
    "ranchera": ("latin",),
    "reggaeton": ("latin",),
    "sad sierreño": ("latin",),
    "salsa": ("latin",),
    "sierreño": ("latin",),
    "tejano": ("latin",),
    "trap latino": ("latin", "hip hop/rap"),
    "urbano latino": ("latin", "hip hop/rap"),
    "afrobeat": ("afrobeats/afropop",),
    "afrobeats": ("afrobeats/afropop",),
    "afro house": ("afrobeats/afropop", "electronic/dance"),
    "afro soul": ("afrobeats/afropop", "r&b/soul"),
    "afropiano": ("afrobeats/afropop",),
    "afropop": ("afrobeats/afropop",),
    "afroswing": ("afrobeats/afropop",),
    "alté": ("afrobeats/afropop",),
    "highlife": ("afrobeats/afropop",),
    "calypso": ("caribbean",),
    "dancehall": ("caribbean",),
    "reggae": ("caribbean",),
    "soca": ("caribbean",),
    "samba": ("brazilian",),
    "pagode": ("brazilian",),
    "mpb": ("brazilian",),
    "bossa nova": ("brazilian",),
    "thai pop": ("southeast asian pop",),
    "t-pop": ("southeast asian pop",),
    "v-pop": ("southeast asian pop",),
    "vietnamese hip hop": ("southeast asian pop", "hip hop/rap"),
    "malaysian pop": ("southeast asian pop",),
    "christian": ("gospel/christian",),
    "christian edm": ("gospel/christian", "electronic/dance"),
    "christian pop": ("gospel/christian", "pop"),
    "ccm": ("gospel/christian",),
    "gospel": ("gospel/christian",),
    "hymns": ("gospel/christian",),
    "pop worship": ("gospel/christian", "pop"),
    "worship": ("gospel/christian",),
    "children's music": ("children/family",),
    "lullaby": ("children/family",),
    "comedy": ("comedy/spoken",),
    "traditional/folk": ("traditional/folk",),
    "traditional": ("traditional/folk",),
    "world": ("world/traditional",),
    "world fusion": ("world/traditional",),
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
    axis_genres: dict[str, list[str]] = field(default_factory=dict)
    axis_sources: dict[str, str] = field(default_factory=dict)
    axis_confidences: dict[str, float] = field(default_factory=dict)
    axis_evidence_urls: dict[str, str | None] = field(default_factory=dict)


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


def canonicalize_genres_for_statistics(values: list[Any]) -> list[str]:
    """Collapse overlapping source tags into stable high-level statistic labels."""
    seen: set[str] = set()
    canonical: list[str] = []
    for genre in normalize_genres(values):
        mapped_genres = STATISTICAL_GENRE_MAP.get(genre)
        if mapped_genres is None:
            mapped_genres = _infer_statistical_genres(genre)
        for mapped in mapped_genres:
            if mapped in seen:
                continue
            seen.add(mapped)
            canonical.append(mapped)
    return canonical


STATISTICAL_GENRE_METADATA: dict[str, dict[str, str]] = {
    "pop": {"axis": "style", "label": "Pop"},
    "rock/alternative": {"axis": "style", "label": "Rock / Alternative"},
    "indie/alternative": {"axis": "style", "label": "Indie / Alternative"},
    "r&b/soul": {"axis": "style", "label": "R&B / Soul"},
    "hip hop/rap": {"axis": "style", "label": "Hip Hop / Rap"},
    "electronic/dance": {"axis": "style", "label": "Electronic / Ambient / Dance"},
    "singer-songwriter": {"axis": "role", "label": "Singer-Songwriter"},
    "folk": {"axis": "style", "label": "Folk"},
    "country": {"axis": "style", "label": "Country"},
    "americana/roots": {"axis": "style", "label": "Americana / Roots"},
    "c-pop": {"axis": "scene", "label": "C-Pop"},
    "k-pop": {"axis": "scene", "label": "K-Pop"},
    "j-pop": {"axis": "scene", "label": "J-Pop"},
    "latin": {"axis": "scene", "label": "Latin"},
    "afrobeats/afropop": {"axis": "scene", "label": "Afrobeats / Afropop"},
    "southeast asian pop": {"axis": "scene", "label": "Southeast Asian Pop"},
    "brazilian": {"axis": "scene", "label": "Brazilian"},
    "caribbean": {"axis": "scene", "label": "Caribbean"},
    "jazz/blues": {"axis": "style", "label": "Jazz / Blues"},
    "classical/instrumental": {"axis": "style", "label": "Classical / Instrumental"},
    "traditional/folk": {"axis": "style", "label": "Traditional / Folk"},
    "world/traditional": {"axis": "style", "label": "World / Traditional"},
    "soundtrack/stage": {"axis": "context", "label": "Soundtrack / Stage"},
    "holiday": {"axis": "context", "label": "Holiday"},
    "children/family": {"axis": "context", "label": "Children / Family"},
    "comedy/spoken": {"axis": "context", "label": "Comedy / Spoken"},
    "gospel/christian": {"axis": "context", "label": "Gospel / Christian"},
}


def statistical_genre_labels() -> set[str]:
    labels: set[str] = set()
    for mapped_genres in STATISTICAL_GENRE_MAP.values():
        labels.update(mapped_genres)
    return labels


def statistical_genre_label_metadata() -> dict[str, dict[str, str]]:
    return STATISTICAL_GENRE_METADATA


def _axis_metadata(axis: str) -> dict[str, str]:
    return AXIS_METADATA.get(
        axis,
        {"label": axis, "interpretation": "标准化统计标签，需结合原始来源审计解释。"},
    )


def _source_confidence_tier(source_mix: list[dict[str, Any]], hours: float) -> str:
    if hours <= 0 or not source_mix:
        return "low"
    score = 0.0
    for row in source_mix:
        source = str(row.get("source") or "unknown")
        source_hours = float(row.get("hours") or 0)
        row_confidence = min(max(float(row.get("confidence") or 0.0), 0.0), 1.0)
        score += SOURCE_CONFIDENCE_WEIGHT.get(source, 0.55) * row_confidence * source_hours
    weighted_score = score / hours
    if weighted_score >= 0.85:
        return "high"
    if weighted_score >= 0.6:
        return "medium"
    return "low"


def _source_confidence_risk(
    source_mix: list[dict[str, Any]], confidence_tier: str
) -> dict[str, str] | None:
    if confidence_tier == "high" or not source_mix:
        return None
    top_source = max(source_mix, key=lambda row: float(row.get("share_pct") or 0))
    source = str(top_source.get("source") or "unknown")
    source_label = SOURCE_DISPLAY_LABELS.get(source, source)
    share_pct = float(top_source.get("share_pct") or 0)
    severity = "high" if confidence_tier == "low" else "medium"
    return {
        "code": "source_confidence",
        "severity": severity,
        "message": (
            f"{source_label} 占该标签 {share_pct:.1f}%，当前只能按 {confidence_tier} 置信度解读"
        ),
    }


def _infer_statistical_genres(genre: str) -> tuple[str, ...]:
    inferred: list[str] = []
    if any(token in genre for token in ("chinese", "mandopop", "cantopop", "taiwan", "gufeng")):
        inferred.append("c-pop")
    if any(token in genre for token in ("korean", "k-pop", "k-")):
        inferred.append("k-pop")
    if any(token in genre for token in ("japanese", "j-pop")) and "classical" not in genre:
        inferred.append("j-pop")
    if "anime" in genre or "anison" in genre:
        inferred.append("soundtrack/stage")
    if any(token in genre for token in ("latin", "reggaeton", "corrido", "música mexicana")):
        inferred.append("latin")
    if "afro" in genre or "afrobeats" in genre:
        inferred.append("afrobeats/afropop")

    if "r&b" in genre or "soul" in genre or "funk" in genre:
        inferred.append("r&b/soul")
    if "hip hop" in genre or "rap" in genre or "trap" in genre or "drill" in genre:
        inferred.append("hip hop/rap")
    if "country" in genre:
        inferred.append("country")
    if "americana" in genre or "red dirt" in genre or "bluegrass" in genre:
        inferred.append("americana/roots")
    if "singer-songwriter" in genre:
        inferred.append("singer-songwriter")
    if "folk" in genre:
        inferred.append("folk")
    if "rock" in genre or "punk" in genre or "emo" in genre or "metal" in genre:
        inferred.append("rock/alternative")
    if "indie" in genre or "alternative" in genre:
        inferred.append("indie/alternative")
    if "pop" in genre:
        inferred.append("pop")
    if any(token in genre for token in ("dance", "edm", "electro", "house", "techno", "bass")):
        inferred.append("electronic/dance")
    if any(token in genre for token in ("jazz", "blues", "swing")):
        inferred.append("jazz/blues")
    if any(token in genre for token in ("classical", "orchestral", "opera", "baroque", "concerto")):
        inferred.append("classical/instrumental")
    if any(token in genre for token in ("soundtrack", "score", "musical", "show tune")):
        inferred.append("soundtrack/stage")
    if any(token in genre for token in ("christmas", "villancicos")):
        inferred.append("holiday")
    return tuple(dict.fromkeys(inferred)) or (genre,)


def _loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        value = [part.strip() for part in str(raw).split(",")]
    return normalize_genres(value if isinstance(value, list) else [])


def _placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _existing_tables(conn: sqlite3.Connection, table_names: set[str]) -> set[str]:
    if not table_names:
        return set()
    rows = conn.execute(
        f"""SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ({_placeholders(list(table_names))})""",
        list(table_names),
    ).fetchall()
    return {row["name"] for row in rows}


def _unknown_result(artist_name: str) -> ResolvedArtistGenres:
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


def _source_sort_key(row: sqlite3.Row) -> tuple[int, float, int]:
    return (
        SOURCE_PRIORITY.get(row["source"], 0),
        float(row["confidence"] or 0),
        int(row["source_id"] or 0),
    )


def _canonical_genres_by_axis(genres: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for genre in canonicalize_genres_for_statistics(genres):
        axis = STATISTICAL_GENRE_METADATA.get(genre, {}).get("axis", "style")
        grouped[axis].append(genre)
    return dict(grouped)


def _with_axis_resolution(
    base: ResolvedArtistGenres,
    candidates: list[dict[str, Any]],
) -> ResolvedArtistGenres:
    axis_genres: dict[str, list[str]] = {}
    axis_sources: dict[str, str] = {}
    axis_confidences: dict[str, float] = {}
    axis_evidence_urls: dict[str, str | None] = {}
    for candidate in candidates:
        source = str(candidate["source"])
        confidence = min(max(float(candidate.get("confidence") or 0.0), 0.0), 1.0)
        evidence_url = candidate.get("evidence_url")
        for axis, genres in _canonical_genres_by_axis(candidate["genres"]).items():
            if axis in axis_genres or not genres:
                continue
            axis_genres[axis] = genres
            axis_sources[axis] = source
            axis_confidences[axis] = confidence
            axis_evidence_urls[axis] = evidence_url
    return ResolvedArtistGenres(
        artist_name=base.artist_name,
        genres=base.genres,
        primary_genre=base.primary_genre,
        language=base.language,
        region=base.region,
        source=base.source,
        confidence=base.confidence,
        evidence_url=base.evidence_url,
        evidence_summary=base.evidence_summary,
        is_fallback=base.is_fallback,
        axis_genres=axis_genres,
        axis_sources=axis_sources,
        axis_confidences=axis_confidences,
        axis_evidence_urls=axis_evidence_urls,
    )


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


def resolve_artist_genres(
    conn: sqlite3.Connection,
    artist_name: str,
) -> ResolvedArtistGenres:
    return resolve_artist_genres_map(conn, [artist_name])[artist_name]


def resolve_artist_genres_map(
    conn: sqlite3.Connection,
    artist_names: list[str],
) -> dict[str, ResolvedArtistGenres]:
    names = list(dict.fromkeys(name for name in artist_names if name))
    resolved = {name: _unknown_result(name) for name in names}
    if not names:
        return {}

    tables = _existing_tables(conn, LOCAL_TABLES | {"spotify_artist_meta"})

    spotify_candidates: dict[str, dict[str, Any]] = {}
    override_candidates: dict[str, dict[str, Any]] = {}
    approved_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)

    if "spotify_artist_meta" in tables:
        rows = conn.execute(
            f"""SELECT artist_name, spotify_artist_id, genres
                FROM spotify_artist_meta
                WHERE artist_name IN ({_placeholders(names)})""",
            names,
        ).fetchall()
        for row in rows:
            genres = _loads_list(row["genres"])
            if not genres:
                continue
            artist_name = row["artist_name"]
            spotify_candidates[artist_name] = {
                "genres": genres,
                "source": "spotify",
                "confidence": 1.0,
                "evidence_url": None,
            }
            resolved[artist_name] = ResolvedArtistGenres(
                artist_name=artist_name,
                genres=genres,
                primary_genre=genres[0],
                language=None,
                region=None,
                source="spotify",
                confidence=1.0,
                is_fallback=False,
            )

    if "artist_genre_overrides" in tables:
        rows = conn.execute(
            f"""SELECT *
                FROM artist_genre_overrides
                WHERE artist_name IN ({_placeholders(names)})""",
            names,
        ).fetchall()
        for row in rows:
            genres = _loads_list(row["normalized_genres_json"])
            if not genres:
                continue
            artist_name = row["artist_name"]
            override_candidates[artist_name] = {
                "genres": genres,
                "source": "manual_override",
                "confidence": float(row["confidence"] or 1.0),
                "evidence_url": None,
            }
            if not resolved[artist_name].genres:
                resolved[artist_name] = ResolvedArtistGenres(
                    artist_name=artist_name,
                    genres=genres,
                    primary_genre=row["primary_genre"] or genres[0],
                    language=row["language"],
                    region=row["region"],
                    source="manual_override",
                    confidence=float(row["confidence"] or 1.0),
                    evidence_summary=row["note"],
                    is_fallback=True,
                )

    if "artist_genre_sources" in tables:
        rows = conn.execute(
            f"""SELECT *
                FROM artist_genre_sources
                WHERE artist_name IN ({_placeholders(names)})
                  AND status = 'approved'""",
            names,
        ).fetchall()
        by_artist: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            if not _loads_list(row["normalized_genres_json"]):
                continue
            by_artist.setdefault(row["artist_name"], []).append(row)
        for artist_name, source_rows in by_artist.items():
            sorted_rows = sorted(source_rows, key=_source_sort_key, reverse=True)
            for source_row in sorted_rows:
                approved_candidates[artist_name].append(
                    {
                        "genres": _loads_list(source_row["normalized_genres_json"]),
                        "source": source_row["source"],
                        "confidence": float(source_row["confidence"] or 0),
                        "evidence_url": source_row["evidence_url"],
                    }
                )
            best = sorted_rows[0]
            genres = _loads_list(best["normalized_genres_json"])
            if not resolved[artist_name].genres:
                resolved[artist_name] = ResolvedArtistGenres(
                    artist_name=artist_name,
                    genres=genres,
                    primary_genre=best["primary_genre"] or genres[0],
                    language=best["language"],
                    region=best["region"],
                    source=best["source"],
                    confidence=float(best["confidence"] or 0),
                    evidence_url=best["evidence_url"],
                    evidence_summary=best["evidence_summary"],
                    is_fallback=True,
                )

    for artist_name in names:
        candidates: list[dict[str, Any]] = []
        if artist_name in spotify_candidates:
            candidates.append(spotify_candidates[artist_name])
        if artist_name in override_candidates:
            candidates.append(override_candidates[artist_name])
        candidates.extend(approved_candidates.get(artist_name, []))
        resolved[artist_name] = _with_axis_resolution(resolved[artist_name], candidates)

    return resolved


def compute_genre_coverage(
    conn: sqlite3.Connection,
    artist_hours: dict[str, float],
) -> dict[str, Any]:
    resolved = resolve_artist_genres_map(conn, list(artist_hours))
    known_hours = 0.0
    unknown_hours = 0.0
    top_missing: list[dict[str, Any]] = []
    source_hours: dict[str, float] = {}
    for artist_name, hours in artist_hours.items():
        item = resolved[artist_name]
        artist_hour = float(hours)
        if item.genres:
            known_hours += artist_hour
            source_hours[item.source] = source_hours.get(item.source, 0.0) + artist_hour
        else:
            unknown_hours += artist_hour
            top_missing.append({"artist_name": artist_name, "hours": round(artist_hour, 1)})
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


def compute_genre_axis_gaps(
    conn: sqlite3.Connection,
    artist_hours: dict[str, float],
    *,
    axis: str,
) -> list[dict[str, Any]]:
    if axis not in AXIS_ORDER:
        raise ValueError(f"unsupported genre axis: {axis}")
    resolved = resolve_artist_genres_map(conn, list(artist_hours))
    gaps: list[dict[str, Any]] = []
    for artist_name, hours_value in artist_hours.items():
        item = resolved[artist_name]
        if item.axis_genres.get(axis):
            continue
        gaps.append(
            {
                "artist_name": artist_name,
                "hours": round(float(hours_value), 1),
                "axis": axis,
                "raw_genres": item.genres,
                "raw_source": item.source,
                "resolved_axes": item.axis_genres,
            }
        )
    return sorted(gaps, key=lambda row: (-float(row["hours"]), row["artist_name"]))


def compute_genre_taxonomy_audit(
    conn: sqlite3.Connection,
    artist_hours: dict[str, float],
) -> dict[str, Any]:
    resolved = resolve_artist_genres_map(conn, list(artist_hours))
    canonical_labels = statistical_genre_labels()
    raw_hours: dict[str, float] = defaultdict(float)
    raw_artist_count: Counter[str] = Counter()
    canonical_hours: dict[str, float] = defaultdict(float)
    canonical_source_hours: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    canonical_source_confidence_hours: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    canonical_source_evidence_hours: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    canonical_artist_hours: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    noncanonical_passthrough: dict[str, float] = defaultdict(float)
    raw_canonical_examples: dict[str, list[str]] = {}
    raw_sources: dict[str, set[str]] = defaultdict(set)
    artist_raw_genres: dict[str, list[str]] = {}
    artist_sources: dict[str, str] = {}
    axis_hours: dict[str, float] = defaultdict(float)
    axis_canonical_counts: Counter[str] = Counter()
    unknown_hours = 0.0

    for artist_name, hours_value in artist_hours.items():
        hours = float(hours_value)
        item = resolved.get(artist_name)
        raw_genres = item.genres if item else []
        if not raw_genres:
            unknown_hours += hours
            continue

        genres_by_axis = item.axis_genres or _canonical_genres_by_axis(raw_genres)

        for axis, axis_genres in genres_by_axis.items():
            axis_source = item.axis_sources.get(axis, item.source)
            axis_confidence = item.axis_confidences.get(axis, item.confidence)
            axis_evidence_url = item.axis_evidence_urls.get(axis, item.evidence_url)
            share = hours / len(axis_genres)
            for genre in axis_genres:
                canonical_hours[genre] += share
                canonical_source_hours[genre][axis_source] += share
                canonical_source_confidence_hours[genre][axis_source] += share * min(
                    max(float(axis_confidence), 0.0), 1.0
                )
                if axis_source in {"spotify", "manual_override"} or axis_evidence_url:
                    canonical_source_evidence_hours[genre][axis_source] += share
                canonical_artist_hours[genre][artist_name] += share
                artist_raw_genres[artist_name] = raw_genres
                artist_sources[artist_name] = axis_source

        for raw_genre in raw_genres:
            raw_hours[raw_genre] += hours
            raw_artist_count[raw_genre] += 1
            raw_sources[raw_genre].add(item.source)
            raw_canonical = canonicalize_genres_for_statistics([raw_genre])
            raw_canonical_examples[raw_genre] = raw_canonical
            if raw_canonical == [raw_genre] and raw_genre not in canonical_labels:
                noncanonical_passthrough[raw_genre] += hours

    total_hours = sum(float(value) for value in artist_hours.values())

    def raw_row(raw_genre: str, hours: float) -> dict[str, Any]:
        return {
            "raw_genre": raw_genre,
            "canonical_genres": raw_canonical_examples.get(raw_genre, []),
            "hours": round(float(hours), 1),
            "artist_count": int(raw_artist_count[raw_genre]),
            "sources": sorted(raw_sources.get(raw_genre, set())),
        }

    metadata = statistical_genre_label_metadata()

    def sorted_hours_items(
        values: dict[str, float], limit: int | None = None
    ) -> list[tuple[str, float]]:
        items = sorted(values.items(), key=lambda item: item[1], reverse=True)
        return items[:limit] if limit is not None else items

    def source_mix_rows(genre: str, hours: float) -> list[dict[str, Any]]:
        if hours <= 0:
            return []
        rows: list[dict[str, Any]] = []
        for source, source_hours in sorted_hours_items(canonical_source_hours[genre]):
            source_hours_float = float(source_hours)
            confidence_hours = canonical_source_confidence_hours[genre][source]
            evidence_hours = canonical_source_evidence_hours[genre][source]
            rows.append(
                {
                    "source": source,
                    "hours": round(source_hours_float, 1),
                    "share_pct": round(source_hours_float / hours * 100, 1),
                    "confidence": round(confidence_hours / source_hours_float, 3),
                    "evidence_pct": round(evidence_hours / source_hours_float * 100, 1),
                }
            )
        return rows

    def top_artist_rows(genre: str, hours: float) -> list[dict[str, Any]]:
        if hours <= 0:
            return []
        return [
            {
                "artist_name": artist,
                "hours": round(float(artist_hours), 1),
                "share_pct": round(float(artist_hours) / hours * 100, 1),
                "source": artist_sources.get(artist, "unknown"),
                "raw_genres": artist_raw_genres.get(artist, []),
            }
            for artist, artist_hours in sorted_hours_items(canonical_artist_hours[genre], limit=5)
        ]

    def dominance_warning(genre: str, hours: float) -> str | None:
        top_artists = sorted_hours_items(canonical_artist_hours[genre], limit=1)
        if not top_artists or hours <= 0:
            return None
        artist, artist_hours = top_artists[0]
        share_pct = float(artist_hours) / hours * 100
        if share_pct >= 70:
            return f"{artist} 贡献了该标签 {share_pct:.1f}% 的播放时长，存在单一艺人主导"
        return None

    def risk_flags(
        genre: str, hours: float, source_mix: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        flags: list[dict[str, str]] = []
        warning = dominance_warning(genre, hours)
        if warning:
            flags.append(
                {
                    "code": "single_artist_dominance",
                    "severity": "medium",
                    "message": warning,
                }
            )
        evidence_pct = (
            sum(float(row["hours"]) * float(row.get("evidence_pct") or 0) for row in source_mix)
            / hours
            if hours > 0
            else 0.0
        )
        if evidence_pct < 99.95:
            flags.append(
                {
                    "code": "missing_evidence_url",
                    "severity": "medium",
                    "message": f"该标签有 {100 - evidence_pct:.1f}% 的来源缺少可复核证据链接",
                }
            )
        llm_share = next(
            (float(row.get("share_pct") or 0) for row in source_mix if row.get("source") == "llm"),
            0.0,
        )
        if llm_share > 50:
            flags.append(
                {
                    "code": "llm_majority",
                    "severity": "high",
                    "message": f"LLM 占该标签 {llm_share:.1f}%，建议补充人工证据后再做强结论",
                }
            )
        source_risk = _source_confidence_risk(
            source_mix, _source_confidence_tier(source_mix, hours)
        )
        if source_risk:
            flags.append(source_risk)
        return flags

    for genre, hours in canonical_hours.items():
        axis = metadata.get(genre, {}).get("axis", "style")
        axis_hours[axis] += float(hours)
        axis_canonical_counts[axis] += 1

    axis_sort_index = {axis: index for index, axis in enumerate(AXIS_ORDER)}

    def axis_row(axis: str, hours: float) -> dict[str, Any]:
        axis_meta = _axis_metadata(axis)
        return {
            "axis": axis,
            "label": axis_meta["label"],
            "hours": round(float(hours), 1),
            "share_pct": round(float(hours) / total_hours * 100, 1) if total_hours else 0.0,
            "coverage_pct": round(float(hours) / total_hours * 100, 1) if total_hours else 0.0,
            "unknown_hours": round(max(total_hours - float(hours), 0.0), 1),
            "unknown_pct": (
                round(max(total_hours - float(hours), 0.0) / total_hours * 100, 1)
                if total_hours
                else 0.0
            ),
            "canonical_count": int(axis_canonical_counts[axis]),
            "interpretation": axis_meta["interpretation"],
        }

    mapping_examples = [
        raw_row(genre, hours)
        for genre, hours in sorted_hours_items(raw_hours, limit=30)
        if raw_canonical_examples.get(genre)
    ][:12]

    from backend.domains.metadata.genre_display_taxonomy import GENRE_DISPLAY_TAXONOMY_VERSION

    return {
        "display_taxonomy_version": GENRE_DISPLAY_TAXONOMY_VERSION,
        "raw_genre_count": len(raw_hours),
        "canonical_genre_count": len(canonical_hours),
        "noncanonical_passthrough_count": len(noncanonical_passthrough),
        "unknown_hours": round(unknown_hours, 1),
        "axis_summary": [
            axis_row(axis, axis_hours.get(axis, 0.0))
            for axis in sorted(AXIS_ORDER, key=lambda value: axis_sort_index[value])
        ],
        "top_canonical_genres": _canonical_genre_rows(
            canonical_hours,
            metadata,
            total_hours,
            axis_hours,
            source_mix_rows,
            top_artist_rows,
            dominance_warning,
            risk_flags,
        ),
        "top_raw_genres": [
            raw_row(genre, hours) for genre, hours in sorted_hours_items(raw_hours, limit=20)
        ],
        "mapping_examples": mapping_examples,
        "noncanonical_passthrough": [
            {"raw_genre": genre, "hours": round(float(hours), 1)}
            for genre, hours in sorted_hours_items(noncanonical_passthrough, limit=20)
        ],
        "caveat": STATISTICAL_GENRE_CAVEAT,
    }


def compute_artist_genre_distribution(
    conn: sqlite3.Connection,
    artist_hours: dict[str, float],
) -> dict[str, Any]:
    """Build independent style/scene/context/role distributions for consumers."""
    audit = compute_genre_taxonomy_audit(conn, artist_hours)
    canonical_rows = audit["top_canonical_genres"]
    axes = []
    for summary in audit["axis_summary"]:
        axis = summary["axis"]
        buckets = [row for row in canonical_rows if row["axis"] == axis]
        axes.append({**summary, "buckets": buckets})

    style = next((item for item in axes if item["axis"] == "style"), None)
    top_genres = []
    if style:
        top_genres = [
            {
                "name": row["name"],
                "label": row["label"],
                "play_share": row["share_pct"],
                "hours": row["hours"],
                "confidence_tier": row["confidence_tier"],
                "top_artists": row["top_artists"],
                "risk_flags": row["risk_flags"],
            }
            for row in style["buckets"][:10]
        ]

    return {
        "top_genres": top_genres,
        "axes": axes,
        "coverage": compute_genre_coverage(conn, artist_hours),
        "caveat": audit["caveat"],
    }


def _canonical_genre_rows(
    canonical_hours: dict[str, float],
    metadata: dict[str, dict[str, str]],
    total_hours: float,
    axis_hours: dict[str, float],
    source_mix_rows,
    top_artist_rows,
    dominance_warning,
    risk_flags,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for genre, hours in sorted(canonical_hours.items(), key=lambda item: item[1], reverse=True):
        hours_float = float(hours)
        axis = metadata.get(genre, {}).get("axis", "style")
        source_mix = source_mix_rows(genre, hours_float)
        confidence_tier = _source_confidence_tier(source_mix, hours_float)
        genre_risks = risk_flags(genre, hours_float, source_mix)
        if confidence_tier == "high" and any(
            flag["code"] in {"single_artist_dominance", "missing_evidence_url"}
            for flag in genre_risks
        ):
            confidence_tier = "medium"
        axis_total = float(axis_hours.get(axis) or 0.0)
        rows.append(
            {
                "name": genre,
                "axis": axis,
                "label": metadata.get(genre, {}).get("label", genre),
                "interpretation": _axis_metadata(axis)["interpretation"],
                "confidence_tier": confidence_tier,
                "hours": round(hours_float, 1),
                "share_pct": round(hours_float / axis_total * 100, 1) if axis_total else 0.0,
                "overall_share_pct": (
                    round(hours_float / total_hours * 100, 1) if total_hours else 0.0
                ),
                "source_mix": source_mix,
                "top_artists": top_artist_rows(genre, hours_float),
                "dominance_warning": dominance_warning(genre, hours_float),
                "risk_flags": genre_risks,
            }
        )
    return rows
