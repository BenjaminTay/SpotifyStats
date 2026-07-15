"""Resolve, validate, and aggregate reviewed artist language metadata."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.domains.metadata.language_registry import (
    LANGUAGE_REGISTRY_VERSION,
    language_label,
    normalize_language_claim,
)

_ARTIST_LEVEL_EVIDENCE_KINDS = {
    "artist_profile",
    "artist_repertoire",
    "editorial_source",
}
_SPECIAL_BUCKETS = {
    "multilingual": ("多语言", "multilingual"),
    "instrumental": ("器乐", "instrumental"),
    "unknown": ("未知", "unknown"),
}
_MS_PER_HOUR = 3_600_000


@dataclass(frozen=True)
class ResolvedArtistLanguage:
    artist_id: int
    classification: str
    primary_language_code: str | None
    language_variant: str | None
    origin: str
    source_id: int | None


class ArtistLanguageValidationError(ValueError):
    """Raised when a suggested language fact lacks approval-grade evidence."""


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "keys"):
        return {key: value[key] for key in value.keys()}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"unsupported language metadata value: {type(value)!r}")


def _unknown_language(artist_id: int) -> ResolvedArtistLanguage:
    return ResolvedArtistLanguage(
        artist_id=artist_id,
        classification="unknown",
        primary_language_code=None,
        language_variant=None,
        origin="unknown",
        source_id=None,
    )


def resolve_artist_languages_map(
    conn: sqlite3.Connection,
    artist_ids: Sequence[int],
) -> dict[int, ResolvedArtistLanguage]:
    """Resolve requested artists from approved facts only."""
    requested = list(dict.fromkeys(int(value) for value in artist_ids))
    resolved = {artist_id: _unknown_language(artist_id) for artist_id in requested}

    for offset in range(0, len(requested), 500):
        chunk = requested[offset : offset + 500]
        if not chunk:
            continue
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT source_id, artist_id, classification,
                       primary_language_code, language_variant, origin
                FROM artist_language_sources
                WHERE status='approved' AND artist_id IN ({placeholders})""",
            chunk,
        ).fetchall()
        for raw_row in rows:
            row = _as_dict(raw_row)
            artist_id = int(row["artist_id"])
            resolved[artist_id] = ResolvedArtistLanguage(
                artist_id=artist_id,
                classification=str(row["classification"]),
                primary_language_code=row["primary_language_code"],
                language_variant=row["language_variant"],
                origin=str(row["origin"]),
                source_id=int(row["source_id"]),
            )
    return resolved


def _normalize_claim(
    code: object,
    variant: object,
    *,
    context: str,
) -> tuple[str, str | None]:
    if code is None or not str(code).strip():
        raise ArtistLanguageValidationError(f"{context} requires a language code")
    try:
        return normalize_language_claim(
            str(code),
            str(variant) if variant is not None else None,
        )
    except ValueError as exc:
        raise ArtistLanguageValidationError(str(exc)) from exc


def _validate_track_attribution(
    conn: sqlite3.Connection,
    artist_id: int,
    evidence: Sequence[dict[str, Any]],
) -> None:
    track_ids = sorted(
        {int(item["local_track_id"]) for item in evidence if item.get("local_track_id") is not None}
    )
    for offset in range(0, len(track_ids), 500):
        chunk = track_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        credited = {
            int(row[0])
            for row in conn.execute(
                f"""SELECT track_id
                    FROM track_artists
                    WHERE artist_id=? AND track_id IN ({placeholders})""",
                [artist_id, *chunk],
            ).fetchall()
        }
        missing = set(chunk) - credited
        if missing:
            missing_text = ", ".join(str(value) for value in sorted(missing))
            raise ArtistLanguageValidationError(
                f"track_artists does not credit artist {artist_id} on track(s): {missing_text}"
            )


def _canonical_vocal_claim_count(claims: set[tuple[str, str | None]]) -> int:
    variants_by_code: dict[str, set[str | None]] = defaultdict(set)
    for code, variant in claims:
        variants_by_code[code].add(variant)

    count = 0
    for variants in variants_by_code.values():
        specific_variants = {variant for variant in variants if variant is not None}
        count += len(specific_variants) if len(specific_variants) >= 2 else 1
    return count


def validate_approved_language_source(
    conn: sqlite3.Connection,
    artist_id: int,
    source_row: Any,
    evidence_rows: Sequence[Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize a candidate and enforce the approval evidence contract."""
    source = _as_dict(source_row)
    evidence = [_as_dict(row) for row in evidence_rows]
    classification = str(source.get("classification") or "")

    if classification == "single_language":
        code, variant = _normalize_claim(
            source.get("primary_language_code"),
            source.get("language_variant"),
            context="single_language source",
        )
        source["primary_language_code"] = code
        source["language_variant"] = variant
    elif classification in {"multilingual", "instrumental"}:
        if (
            source.get("primary_language_code") is not None
            or source.get("language_variant") is not None
        ):
            raise ArtistLanguageValidationError(
                f"{classification} source cannot define a primary language"
            )
        source["primary_language_code"] = None
        source["language_variant"] = None
    else:
        raise ArtistLanguageValidationError(
            f"unsupported language classification: {classification}"
        )

    for item in evidence:
        code = item.get("claimed_language_code")
        variant = item.get("claimed_language_variant")
        if code is None and variant is None:
            continue
        normalized_code, normalized_variant = _normalize_claim(
            code,
            variant,
            context="evidence",
        )
        item["claimed_language_code"] = normalized_code
        item["claimed_language_variant"] = normalized_variant

    _validate_track_attribution(conn, artist_id, evidence)

    artist_vocal_claims = {
        (str(item["claimed_language_code"]), item.get("claimed_language_variant"))
        for item in evidence
        if item.get("evidence_kind") in _ARTIST_LEVEL_EVIDENCE_KINDS
        and item.get("performer_attribution") == "artist_vocal_confirmed"
        and item.get("claimed_language_code") is not None
    }

    if classification == "single_language":
        source_claim = (
            str(source["primary_language_code"]),
            source.get("language_variant"),
        )
        is_supported = any(
            claim_code == source_claim[0]
            and (source_claim[1] is None or claim_variant == source_claim[1])
            for claim_code, claim_variant in artist_vocal_claims
        )
        if not is_supported:
            raise ArtistLanguageValidationError(
                "single_language requires matching artist-level vocal evidence"
            )
    elif classification == "multilingual":
        if _canonical_vocal_claim_count(artist_vocal_claims) < 2:
            raise ArtistLanguageValidationError(
                "multilingual requires two distinct artist-level vocal claims"
            )
    else:
        is_supported = any(
            item.get("evidence_kind") in _ARTIST_LEVEL_EVIDENCE_KINDS
            and item.get("performer_attribution") == "artist_instrumental_confirmed"
            for item in evidence
        )
        if not is_supported:
            raise ArtistLanguageValidationError(
                "instrumental requires artist-level instrumental evidence"
            )

    return source, evidence


def artist_language_fact_revision(conn: sqlite3.Connection) -> str:
    """Return a stable revision that changes only with approved facts."""
    rows = conn.execute(
        """SELECT artist_id, source_id, classification,
                  primary_language_code, language_variant, origin
           FROM artist_language_sources
           WHERE status='approved'
           ORDER BY artist_id, source_id"""
    ).fetchall()
    payload = {
        "registry": LANGUAGE_REGISTRY_VERSION,
        "facts": [tuple(row) for row in rows],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def build_primary_artist_ms(
    conn: sqlite3.Connection,
    plays_df: pd.DataFrame,
) -> tuple[dict[int, int], int]:
    """Aggregate play milliseconds by tracks.artist_id without collaborator fan-out."""
    if plays_df.empty:
        return {}, 0
    required = {"track_id", "ms_played"}
    missing_columns = required - set(plays_df.columns)
    if missing_columns:
        raise ValueError(f"plays_df missing columns: {sorted(missing_columns)}")

    plays = plays_df.loc[:, ["track_id", "ms_played"]].copy()
    plays["ms_played"] = (
        pd.to_numeric(plays["ms_played"], errors="coerce").fillna(0).astype("int64")
    )
    total_ms = int(plays["ms_played"].sum())
    with_track = plays.loc[plays["track_id"].notna()].copy()
    if with_track.empty:
        return {}, total_ms
    with_track["track_id"] = with_track["track_id"].astype("int64")
    track_ms = {
        int(track_id): int(ms)
        for track_id, ms in with_track.groupby("track_id", sort=False)["ms_played"].sum().items()
    }

    track_to_artist: dict[int, int] = {}
    track_ids = list(track_ms)
    for offset in range(0, len(track_ids), 500):
        chunk = track_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT track_id, artist_id
                FROM tracks
                WHERE track_id IN ({placeholders}) AND artist_id IS NOT NULL""",
            chunk,
        ).fetchall()
        track_to_artist.update({int(row[0]): int(row[1]) for row in rows})

    artist_ms: dict[int, int] = defaultdict(int)
    attributed_ms = 0
    for track_id, ms in track_ms.items():
        artist_id = track_to_artist.get(track_id)
        if artist_id is None:
            continue
        artist_ms[artist_id] += ms
        attributed_ms += ms
    return dict(artist_ms), total_ms - attributed_ms


def _normalized_bucket_key(resolved: ResolvedArtistLanguage) -> str:
    if resolved.classification != "single_language":
        return resolved.classification
    try:
        code, _ = normalize_language_claim(
            resolved.primary_language_code or "",
            resolved.language_variant,
        )
    except ValueError:
        return "unknown"
    return code


def _compute_language_bucket_ms(
    conn: sqlite3.Connection,
    artist_ms_by_id: Mapping[int, int],
) -> dict[str, int]:
    """Allocate each primary artist's integer milliseconds to exactly one bucket."""
    normalized_ms = {
        int(artist_id): int(ms) for artist_id, ms in artist_ms_by_id.items() if int(ms) != 0
    }
    resolved = resolve_artist_languages_map(conn, list(normalized_ms))
    bucket_ms: dict[str, int] = defaultdict(int)
    for artist_id, ms in normalized_ms.items():
        bucket_ms[_normalized_bucket_key(resolved[artist_id])] += ms
    return dict(bucket_ms)


def _artist_names(conn: sqlite3.Connection, artist_ids: Sequence[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    for offset in range(0, len(artist_ids), 500):
        chunk = artist_ids[offset : offset + 500]
        if not chunk:
            continue
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT artist_id, artist_name FROM artists WHERE artist_id IN ({placeholders})",
            chunk,
        ).fetchall()
        names.update({int(row[0]): str(row[1]) for row in rows})
    return names


def compute_artist_language_distribution(
    conn: sqlite3.Connection,
    artist_ms_by_id: Mapping[int, int],
    *,
    excluded_ms: int = 0,
) -> dict[str, Any]:
    """Format an exact artist allocation into the public coverage response shape."""
    normalized_ms = {
        int(artist_id): int(ms) for artist_id, ms in artist_ms_by_id.items() if int(ms) != 0
    }
    eligible_ms = sum(normalized_ms.values())
    resolved = resolve_artist_languages_map(conn, list(normalized_ms))
    bucket_ms = _compute_language_bucket_ms(conn, normalized_ms)

    bucket_artist_counts: dict[str, int] = defaultdict(int)
    source_ms: dict[str, int] = defaultdict(int)
    missing_ids: list[int] = []
    for artist_id, ms in normalized_ms.items():
        fact = resolved[artist_id]
        key = _normalized_bucket_key(fact)
        bucket_artist_counts[key] += 1
        if key == "unknown":
            missing_ids.append(artist_id)
        else:
            source_ms[fact.origin] += ms

    buckets = []
    for key, ms in sorted(bucket_ms.items(), key=lambda item: (-item[1], item[0])):
        if ms <= 0:
            continue
        if key in _SPECIAL_BUCKETS:
            label, classification = _SPECIAL_BUCKETS[key]
        else:
            label = language_label(key)
            classification = "single_language"
        buckets.append(
            {
                "key": key,
                "label": label,
                "classification": classification,
                "hours": ms / _MS_PER_HOUR,
                "share_pct": round(ms / eligible_ms * 100, 2) if eligible_ms else 0.0,
                "artist_count": bucket_artist_counts[key],
            }
        )

    unknown_ms = bucket_ms.get("unknown", 0)
    classified_ms = eligible_ms - unknown_ms
    names = _artist_names(conn, missing_ids)
    top_missing = [
        {
            "artist_id": artist_id,
            "artist_name": names.get(artist_id, f"Artist #{artist_id}"),
            "hours": normalized_ms[artist_id] / _MS_PER_HOUR,
        }
        for artist_id in sorted(missing_ids, key=lambda value: (-normalized_ms[value], value))[:50]
    ]

    return {
        "eligible_hours": eligible_ms / _MS_PER_HOUR,
        "excluded_unattributed_hours": int(excluded_ms) / _MS_PER_HOUR,
        "classified_hours": classified_ms / _MS_PER_HOUR,
        "unknown_hours": unknown_ms / _MS_PER_HOUR,
        "classified_pct": round(classified_ms / eligible_ms * 100, 2) if eligible_ms else 0.0,
        "unknown_pct": round(unknown_ms / eligible_ms * 100, 2) if eligible_ms else 0.0,
        "buckets": buckets,
        "source_hours": {
            origin: ms / _MS_PER_HOUR for origin, ms in sorted(source_ms.items()) if ms > 0
        },
        "top_missing": top_missing,
        "caveat": (
            "仅使用已审核通过的艺人语言事实，并按 tracks.artist_id 主艺人归属统计；"
            "多语言、器乐与未知不会重分配到单一语言。"
        ),
    }
