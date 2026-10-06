"""Title credit candidates, resolved only against identities supplied by callers.

This module never searches, creates artists, or reads a database. Punctuation
inside a trusted complete name is preserved, and competing complete parses are
treated as ambiguity rather than resolved by longest-name preference.
"""

# Python 3.9 is also the CI runtime; retain Optional despite postponed-annotation
# pyupgrade recommendations (the importer accepts these types at runtime too).
# ruff: noqa: UP045

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Optional, Union


@dataclass(frozen=True)
class TitleCreditBlock:
    marker: str
    text: str
    start: int
    end: int


_BRACKETS = {"(": ")", "[": "]", "（": "）", "［": "］", "【": "】"}
_MARKER = re.compile(r"(?P<marker>featuring|feat|ft|with)(?:\.\s*|\s+)", re.I)
_CONNECTOR = re.compile(
    r"\s*(?:(?:[,，&＆]\s*(?:and\s+)?|and\s+)"
    r"(?:(?:featuring|feat|ft|with)(?:\.\s*|\s+))?|"
    r"(?:featuring|feat|ft|with)(?:\.\s*|\s+))",
    re.I,
)

# Deliberately unchanged historical expressions, including order and truncation
# at nested closing brackets. Only these can establish old parser provenance.
_LEGACY_NON_ARTIST = re.compile(
    r"(?:re)?mix|live|version|edit|acoustic|instrumental|demo|"
    r"remaster(?:ed)?|radio\s*edit|single\s*edit|"
    r"Taylor's\s*Version|From\s*The\s*Vault|bonus\s*track|"
    r"deluxe|extended|original\s*mix|club\s*mix|"
    r"cover|tribute|reprise|interlude|intro|outro|"
    r"solo|stripped|acapella|a\s*cappella|"
    r"orchestral|symphonic|unplugged",
    re.I,
)
_LEGACY_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\(feat\.?\s+([^)]+)\)",
        r"\(ft\.?\s+([^)]+)\)",
        r"\(with\s+([^)]+)\)",
        r"\[feat\.?\s+([^\]]+)\]",
        r"\[ft\.?\s+([^\]]+)\]",
        r"\[with\s+([^\]]+)\]",
    )
)


def legacy_title_names(track_name: Optional[str]) -> list[str]:
    """Exactly reproduce the historical parser; never use for new acceptance."""
    if not track_name:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for pattern in _LEGACY_PATTERNS:
        for match in pattern.findall(track_name):
            for part in re.split(r"\s*[,&]\s*", match):
                part = part.strip()
                if part and not _LEGACY_NON_ARTIST.fullmatch(part) and part.lower() not in seen:
                    seen.add(part.lower())
                    names.append(part)
    return names


def extract_title_credit_blocks(track_name: Optional[str]) -> tuple[TitleCreditBlock, ...]:
    """Extract balanced credit brackets, retaining nested brackets in names."""
    if not track_name:
        return ()
    stack: list[tuple[str, int]] = []
    candidates: list[tuple[TitleCreditBlock, int]] = []
    completed_roots: set[int] = set()
    for pos, char in enumerate(track_name):
        if char in _BRACKETS:
            stack.append((char, pos))
        elif char in _BRACKETS.values():
            if not stack or _BRACKETS[stack[-1][0]] != char:
                stack.clear()
                continue
            root_start = stack[0][1]
            _opening, start = stack.pop()
            if not stack:
                completed_roots.add(root_start)
            content = track_name[start + 1 : pos].strip()
            match = _MARKER.match(content)
            if match and content[match.end() :].strip():
                marker = "with" if match.group("marker").lower() == "with" else "feat"
                candidates.append(
                    (
                        TitleCreditBlock(marker, content[match.end() :].strip(), start, pos + 1),
                        root_start,
                    )
                )
    # Nested credit-like text remains part of its outer block. Otherwise it could
    # bypass an unresolved outer candidate and create only a partial relationship.
    blocks = [block for block, root in candidates if root in completed_roots]
    return tuple(
        block
        for block in sorted(blocks, key=lambda b: b.start)
        if not any(other.start < block.start and block.end < other.end for other in blocks)
    )


def legacy_names_for_block(block: TitleCreditBlock, track_name: str) -> list[str]:
    """Return old parser products within one exact original bracket span."""
    return legacy_title_names(track_name[block.start : block.end])


def normalize_credit_name(name: str) -> str:
    """Normalize case/whitespace, preserving identity-significant symbols."""
    return " ".join(name.split()).casefold()


def resolve_block_entities(
    block: TitleCreditBlock,
    trusted_names: Mapping[str, Union[int, Iterable[int]]],
    *,
    supported_artist_ids: Optional[Iterable[int]] = None,
) -> Optional[tuple[int, ...]]:
    """Return a unique complete identity interpretation, or None.

    ``trusted_names`` must contain actual trusted names/aliases, not search
    guesses. ``with`` requires supplied participation evidence on this track.
    Same-name IDs and complete-name-versus-multiple-name parses remain ambiguous.
    """
    names: dict[str, set[int]] = {}
    for name, values in trusted_names.items():
        key = normalize_credit_name(name)
        if key:
            names.setdefault(key, set()).update((values,) if isinstance(values, int) else values)
    text = normalize_credit_name(block.text)
    supported = frozenset(supported_artist_ids or ())

    @cache
    def parse(pos: int, needs_support: bool) -> frozenset[tuple[int, ...]]:
        results: set[tuple[int, ...]] = set()
        for name, ids in names.items():
            if not text.startswith(name, pos):
                continue
            end = pos + len(name)
            suffixes: set[tuple[int, ...]] = set()
            if end == len(text):
                suffixes.add(())
            else:
                connector = _CONNECTOR.match(text, end)
                if connector:
                    token = connector.group().strip()
                    suffixes.update(
                        parse(connector.end(), needs_support or bool(re.search(r"\bwith\b", token)))
                    )
                # An affiliation is descriptive: recognise its full name, but
                # do not add the band. A Spotify band object is preserved by the
                # caller's separate structural credit list.
                if text.startswith(" of ", end):
                    affiliation_start = end + 4
                    # A plain affiliation is description, not a second
                    # credited identity. Unknown affiliation names need no
                    # entity creation. A separator-bearing tail still requires
                    # a trusted complete name to avoid swallowing collaborators.
                    if affiliation_start < len(text) and not _CONNECTOR.search(
                        text, affiliation_start
                    ):
                        suffixes.add(())
                    for affiliation in names:
                        if not text.startswith(affiliation, affiliation_start):
                            continue
                        affiliation_end = affiliation_start + len(affiliation)
                        if affiliation_end == len(text):
                            suffixes.add(())
                        else:
                            connector = _CONNECTOR.match(text, affiliation_end)
                            if connector:
                                suffixes.update(
                                    parse(
                                        connector.end(),
                                        needs_support
                                        or bool(re.search(r"\bwith\b", connector.group())),
                                    )
                                )
            for artist_id in ids:
                if not needs_support or artist_id in supported:
                    results.update((artist_id,) + suffix for suffix in suffixes)
            # Two distinct complete interpretations already establish ambiguity.
            if len(results) > 1:
                return frozenset(results)
        return frozenset(results)

    alternatives = parse(0, block.marker == "with")
    if len(alternatives) != 1:
        return None
    return tuple(dict.fromkeys(next(iter(alternatives))))
