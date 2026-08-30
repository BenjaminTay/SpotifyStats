"""Deterministic L2 title identity without changing display metadata.

L2 answers the product question "is this the same song recording?".  The
canonical artist is resolved elsewhere; this module turns the visible title
into a stable base title plus semantic recording tags. Packaging labels such
as remaster, clean/explicit and bonus-track disappear from the L2 key.
Soundtrack source text is retained separately as an evidence gate. Alternate
recordings keep a tag and therefore remain separate until L3.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from opencc import OpenCC

L2_TITLE_IDENTITY_POLICY_VERSION = "nfkc_t2s_title_semantic_source_v4"

_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\uff07": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\uff02": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\uff0d": "-",
        "\uff08": "(",
        "\uff09": ")",
        "\uff3b": "[",
        "\uff3d": "]",
        "\uff1a": ":",
    }
)

# Order matters: a radio edit is not reduced to the generic remix tag, and a
# Taylor's Version containing "version" remains a rerecord.
_SEMANTIC_TAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rerecord",
        re.compile(
            r"(?:taylor\s*'?s\s+version|from\s+the\s+vault|re[ -]?record(?:ed|ing)?|"
            r"重录(?:版)?|重錄(?:版)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "radio_edit",
        re.compile(r"(?:radio\s+(?:edit|version)|电台版|電台版)", re.IGNORECASE),
    ),
    (
        "original_version",
        re.compile(r"(?:\boriginal\s+version\b|原版|原始版)", re.IGNORECASE),
    ),
    (
        "single_version",
        re.compile(r"(?:\bsingle\s+version\b|单曲版|單曲版)", re.IGNORECASE),
    ),
    (
        "album_version",
        re.compile(r"(?:\balbum\s+version\b|专辑版|專輯版)", re.IGNORECASE),
    ),
    (
        "extended",
        re.compile(r"(?:\bextended(?:\s+(?:version|mix|edit))?\b|加长版|加長版)", re.IGNORECASE),
    ),
    (
        "sped_up",
        re.compile(r"(?:\bsped[ -]?up(?:\s+version)?\b|加速版)", re.IGNORECASE),
    ),
    (
        "slowed",
        re.compile(r"(?:\bslowed(?:\s+(?:down|version))?\b|慢速版|减速版|減速版)", re.IGNORECASE),
    ),
    (
        "acoustic",
        re.compile(r"(?:acoustic|unplugged|不插电|不插電|原声版|原聲版)", re.IGNORECASE),
    ),
    (
        "live",
        re.compile(
            r"(?:\blive\b|in\s+concert|concert\s+version|现场(?:版|录音)?|"
            r"現場(?:版|錄音)?|演唱会版|演唱會版)",
            re.IGNORECASE,
        ),
    ),
    (
        "remix",
        re.compile(r"(?:\bremix\b|radio\s+mix|混音(?:版)?)", re.IGNORECASE),
    ),
    ("demo", re.compile(r"(?:\bdemo\b|样带版|樣帶版|试听版|試聽版)", re.IGNORECASE)),
    (
        "instrumental",
        re.compile(r"(?:instrumental|karaoke|伴奏(?:版)?|纯音乐|純音樂)", re.IGNORECASE),
    ),
    (
        "collaboration_variant",
        re.compile(
            r"(?:\bfeat(?:uring)?\.?\b|\bft\.?\b|^with\s+|duet|合作版|合唱版)",
            re.IGNORECASE,
        ),
    ),
)

_PACKAGING_PATTERNS = (
    re.compile(r"(?:\b(?:19|20)\d{2}\s*)?\bremaster(?:ed)?\b", re.IGNORECASE),
    re.compile(r"(?:重制|重製)(?:版)?", re.IGNORECASE),
    re.compile(r"\b(?:clean|explicit)(?:\s+version)?\b", re.IGNORECASE),
    re.compile(r"\bbonus\s+track(?:\s+version)?\b", re.IGNORECASE),
    re.compile(r"^(?:19|20)\d{2}\s*版$", re.IGNORECASE),
)

_SOURCE_CONTEXT_PATTERNS = (
    re.compile(
        r"\bfrom\s+.+?(?:soundtrack|motion\s+picture|series|film)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bmusic\s+from\s+.+", re.IGNORECASE),
    re.compile(
        r"(?:电影|电视剧|剧集|动画|动漫|游戏|综艺|影视|電視劇|劇集|動畫|動漫|遊戲|綜藝|影視)"
        r".+(?:主题曲|插曲|片尾曲|片头曲|原声|主題曲|片尾曲|片頭曲|原聲)",
        re.IGNORECASE,
    ),
    re.compile(
        r"《.+》.*(?:主题曲|插曲|片尾曲|片头曲|原声|主題曲|片尾曲|片頭曲|原聲)",
        re.IGNORECASE,
    ),
)

_TRAILING_PACKAGING_PATTERNS = (
    re.compile(
        r"\s*(?:-|:)?\s*(?:\(?\s*)?(?:(?:19|20)\d{2}\s+)?remaster(?:ed)?"
        r"(?:\s+(?:19|20)\d{2})?\s*\)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"\s*(?:-|:)?\s*\(?\s*(?:重制|重製)(?:版)?\s*\)?\s*$", re.IGNORECASE),
    re.compile(
        r"\s*(?:-|:)?\s*\(?\s*(?:clean|explicit|bonus\s+track)"
        r"(?:\s+version)?\s*\)?\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"\s*(?:-|:)?\s*(?:19|20)\d{2}\s*版\s*$", re.IGNORECASE),
)

_BRACKET_SUFFIX = re.compile(r"\s*[\(\[]([^\(\)\[\]]+)[\)\]]\s*$")
_DELIMITED_SUFFIX = re.compile(r"\s+(?:-|:)\s+(.+?)\s*$")


@dataclass(frozen=True)
class L2TrackTitleIdentity:
    """Stable L2 title components without changing presentation metadata."""

    original: str
    base_title: str
    semantic_version_tags: tuple[str, ...]
    source_context_tags: tuple[str, ...]
    policy_version: str = L2_TITLE_IDENTITY_POLICY_VERSION

    @property
    def key(self) -> tuple[str, tuple[str, ...]]:
        return self.base_title, self.semantic_version_tags


@lru_cache(maxsize=1)
def _traditional_to_simplified() -> OpenCC:
    return OpenCC("t2s")


def _prepare_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).translate(_PUNCTUATION_TRANSLATION)
    return _traditional_to_simplified().convert(text).casefold().strip()


def _semantic_tags(fragment: str) -> tuple[str, ...]:
    """Return category plus the complete normalized semantic suffix.

    The suffix is essential: ``A Remix`` and ``B Remix`` are different L2
    titles even though both are remixes.  Packaging punctuation and case still
    normalize to one deterministic key.
    """

    suffix = _canonical_base_title(fragment)
    return tuple(
        f"{tag}:{suffix}" for tag, pattern in _SEMANTIC_TAG_PATTERNS if pattern.search(fragment)
    )


def _is_packaging_fragment(fragment: str) -> bool:
    text = fragment.strip().strip("()[] ")
    return bool(text) and any(pattern.search(text) for pattern in _PACKAGING_PATTERNS)


def _source_context(fragment: str) -> tuple[str, ...]:
    text = fragment.strip().strip("()[] ")
    if not text or not any(pattern.search(text) for pattern in _SOURCE_CONTEXT_PATTERNS):
        return ()
    return (_canonical_base_title(text),)


def _canonical_base_title(value: str) -> str:
    # NFKC/casefold removes presentation-only differences. Diacritics remain:
    # they can be meaningful parts of an actual title and are not mere case.
    text = "".join(character if character.isalnum() else " " for character in value)
    return " ".join(text.split())


def normalize_l2_track_title(name: str) -> L2TrackTitleIdentity:
    """Return the deterministic L2 title identity for one display title.

    Only recognised trailing wrappers are removed.  Unknown suffixes remain in
    the base title, which keeps machine merging deterministic and avoids a
    generic "anything called version" rule.
    """

    if not isinstance(name, str):
        raise TypeError("track title must be a string")
    original = name
    text = _prepare_text(name)
    tags: set[str] = set()
    source_contexts: set[str] = set()

    changed = True
    while text and changed:
        changed = False
        for pattern in (_BRACKET_SUFFIX, _DELIMITED_SUFFIX):
            match = pattern.search(text)
            if match is None:
                continue
            fragment = match.group(1).strip()
            fragment_tags = _semantic_tags(fragment)
            if fragment_tags:
                tags.update(fragment_tags)
                text = text[: match.start()].strip()
                changed = True
                break
            fragment_source_contexts = _source_context(fragment)
            if fragment_source_contexts:
                source_contexts.update(fragment_source_contexts)
                text = text[: match.start()].strip()
                changed = True
                break
            if _is_packaging_fragment(fragment):
                text = text[: match.start()].strip()
                changed = True
                break

    # Also accept packaging labels without a dash or bracket, a common Spotify
    # spelling for remasters and explicit/clean variants.
    changed = True
    while text and changed:
        changed = False
        for pattern in _TRAILING_PACKAGING_PATTERNS:
            stripped = pattern.sub("", text).strip()
            if stripped != text and stripped:
                text = stripped
                changed = True
                break

    base_title = _canonical_base_title(text)
    if not base_title:
        # Never manufacture the same empty key for unrelated malformed titles.
        base_title = _canonical_base_title(_prepare_text(original))
    return L2TrackTitleIdentity(
        original=original,
        base_title=base_title,
        semantic_version_tags=tuple(sorted(tags)),
        source_context_tags=tuple(sorted(source_contexts)),
    )
