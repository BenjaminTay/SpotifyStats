"""Deterministic L3 composition title identity.

L2 deliberately keeps alternate recordings separate.  This module provides
an independent, conservative title parser for the next governance step: it
removes only recognised trailing recording/source wrappers so a planner can
relate acoustic, live, remix and rerecorded releases to one composition.

Unknown suffixes remain part of ``base_title``.  In particular, this module
does not implement a generic "strip anything ending in Version" rule.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from opencc import OpenCC

COMPOSITION_TITLE_IDENTITY_POLICY_VERSION = "nfkc_t2s_composition_relation_v2"

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

_RELATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rerecord",
        re.compile(
            r"(?:taylor\s*'?s\s+version|from\s+the\s+vault|re[ -]?record(?:ed|ing)?|"
            r"\b(?:19|20)\d{2}\s+version\b|重录(?:版)?|重錄(?:版)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "radio_edit",
        re.compile(r"(?:\bradio\s+(?:edit|version|mix)\b|电台版|電台版)", re.IGNORECASE),
    ),
    (
        "single_version",
        re.compile(r"(?:\bsingle\s+(?:version|edit|mix)\b|单曲版|單曲版)", re.IGNORECASE),
    ),
    (
        "album_version",
        re.compile(r"(?:\balbum\s+version\b|专辑版|專輯版)", re.IGNORECASE),
    ),
    (
        "original_version",
        re.compile(r"(?:\boriginal\s+version\b|原版|原始版)", re.IGNORECASE),
    ),
    (
        "extended",
        re.compile(
            r"(?:\bextended(?:\s+(?:version|mix|edit))?\b|"
            r"\b(?:ten|10)[ -]?minute\s+version\b|加长版|加長版)",
            re.IGNORECASE,
        ),
    ),
    (
        "sped_up",
        re.compile(r"(?:\bsped[ -]?up(?:\s+version)?\b|加速版)", re.IGNORECASE),
    ),
    (
        "slowed",
        re.compile(
            r"(?:\bslowed(?:\s+(?:down|version))?\b|慢速版|减速版|減速版)",
            re.IGNORECASE,
        ),
    ),
    (
        "acoustic",
        re.compile(
            r"(?:\bacoustic(?:\s+version)?\b|\bunplugged\b|不插电|不插電|原声版|原聲版)",
            re.IGNORECASE,
        ),
    ),
    (
        "live",
        re.compile(
            r"(?:(?<![a-z0-9])live(?![a-z0-9])|\bin\s+concert\b|\bconcert\s+version\b|"
            r"\b(?:studio|live)\s+sessions?\b|\blong\s+pond\s+studio\s+sessions?\b|"
            r"现场(?:版|录音)?|現場(?:版|錄音)?|演唱会版|演唱會版)",
            re.IGNORECASE,
        ),
    ),
    (
        "remix",
        re.compile(
            r"(?:\bremix\b|\b(?:club|dance|pop|rock|radio|single|album)\s+mix\b|"
            r"\b(?:radio|single|club)\s+edit\b|\bedited\s+version\b|"
            r"remix\s*版|混音(?:版)?)",
            re.IGNORECASE,
        ),
    ),
    ("instrumental", re.compile(r"(?:\binstrumental\b|伴奏(?:版)?|纯音乐|純音樂)", re.I)),
    ("karaoke", re.compile(r"(?:\bkaraoke\b|卡拉ok(?:版)?)", re.IGNORECASE)),
    (
        "acapella",
        re.compile(r"(?:\ba\s*cappella\b|\bacapella\b|清唱(?:版)?|无伴奏|無伴奏)", re.I),
    ),
    (
        "demo",
        re.compile(r"(?:\bdemo(?:\s*\d+)?\b|样带(?:版)?|樣帶(?:版)?|试听版|試聽版)", re.I),
    ),
    (
        "rehearsal",
        re.compile(r"(?:\brehearsal(?:\s+version)?\b|排练(?:版|录音)?|排練(?:版|錄音)?)", re.I),
    ),
    (
        "alternate_arrangement",
        re.compile(
            r"(?:\b(?:sad\s+girl\s+autumn|lonely\s+witch|cabin\s+in\s+candlelight|"
            r"old[ -]?timey|country\s+road|so\s+glamorous\s+cabaret|ballad|piano|"
            r"piano\s+trio|orchestral|strings?|symphonic|acoustic\s+piano|pop|rock|"
            r"film|studio|singback|twin|idol|end\s+credit|day|night|us)\s+"
            r"(?:version|arrangement|mix)\b|"
            r"秋日伤感版|秋日傷感版|钢琴版|鋼琴版|管弦乐版|管弦樂版|交响版|交響版)",
            re.IGNORECASE,
        ),
    ),
    (
        "collaboration_variant",
        re.compile(
            r"(?:\bfeat(?:uring)?\.?\s*.+|\bft\.?\s*.+|\bwith\s+.+|"
            r"\bduet(?:\s+(?:version|with\s+.+))?\b|\bsolo\s+version\b|合作版|合唱版)",
            re.IGNORECASE,
        ),
    ),
)

_BLOCKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "translation",
        re.compile(
            r"(?:\b(?:english|spanish|french|german|italian|portuguese|japanese|korean|"
            r"mandarin|cantonese|chinese|latin)\b(?:\s+(?:acoustic|live|radio|album|"
            r"single|extended|demo|instrumental))?\s+version\b|\ben\s+espa(?:n|ñ)ol\b|"
            r"\bversion\s+fran(?:c|ç)aise\b|英文版|英语版|英語版|西班牙语版|"
            r"西班牙語版|法语版|法語版|德语版|德語版|日语版|日語版|韩语版|"
            r"韓語版|国语版|國語版|粤语版|粵語版|中文版|翻译版|翻譯版)",
            re.IGNORECASE,
        ),
    ),
    ("cover", re.compile(r"(?:\bcover(?:\s+version)?\b|翻唱(?:版)?)", re.IGNORECASE)),
    ("mashup", re.compile(r"(?:\bmash[ -]?up\b|串烧|串燒|混搭(?:版)?)", re.IGNORECASE)),
    ("medley", re.compile(r"(?:\bmedley\b|串烧|串燒|组曲|組曲)", re.IGNORECASE)),
    ("parody", re.compile(r"(?:\bparody\b|恶搞(?:版)?|惡搞(?:版)?)", re.IGNORECASE)),
    (
        "sample",
        re.compile(
            r"(?:\bsampl(?:e|ed|ing)\b|\binterpolat(?:e|ed|ion)\b|采样|採樣|插值)",
            re.IGNORECASE,
        ),
    ),
    ("reprise", re.compile(r"(?:\breprise\b|再现(?:版)?|再現(?:版)?)", re.IGNORECASE)),
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
    re.compile(r"\boriginal\s+motion\s+picture\s+soundtrack\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+.+\s+the\s+album\b", re.IGNORECASE),
    re.compile(r"\brecorded(?:\s+live)?\s+at\s+.+", re.IGNORECASE),
    re.compile(r"\bfeatured\s+in\s+.+", re.IGNORECASE),
    re.compile(r"\bfrom\s+(?:audible|spotify|apple\s+music)\b.+", re.IGNORECASE),
    re.compile(r"\bspotify\s+best\s+new\s+artist\b", re.IGNORECASE),
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

_STRUCTURAL_TITLE_PATTERN = re.compile(
    r"^(?:(?:the)\s+)?(?:intro|outro|interlude|overture|ouverture|prelude|"
    r"prologue|epilogue|theme|序曲|间奏|間奏|前奏|尾声|尾聲|主题|主題)(?:\s|$)",
    re.IGNORECASE,
)

_BRACKET_SUFFIX = re.compile(r"\s*[\(\[]([^\(\)\[\]]+)[\)\]]\s*$")
_DELIMITED_SUFFIX = re.compile(r"\s+(?:-|:)\s+(.+?)\s*$")
_PIPE_SUFFIX = re.compile(r"\s+\|\s+(.+?)\s*$")

# Bare suffix support is deliberately a closed list.  It handles titles such
# as ``S&M Remix`` while retaining an unknown ``Anniversary Version`` in the
# composition base title.
_BARE_SUFFIX_PATTERNS = (
    re.compile(r"\s+(taylor\s*'?s\s+version)\s*$", re.IGNORECASE),
    re.compile(r"\s+((?:19|20)\d{2}\s+version)\s*$", re.IGNORECASE),
    re.compile(r"\s+((?:ten|10)[ -]?minute\s+version)\s*$", re.IGNORECASE),
    re.compile(
        r"\s+((?:sad\s+girl\s+autumn|lonely\s+witch|cabin\s+in\s+candlelight|"
        r"old[ -]?timey|country\s+road|so\s+glamorous\s+cabaret|ballad|piano|piano\s+trio|"
        r"orchestral|strings?|symphonic|pop|rock|film|studio|singback|twin|idol|"
        r"end\s+credit|day|night|us)\s+version)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s+((?:radio|single|album|original)\s+(?:edit|mix|version))\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s+((?:extended|sped[ -]?up|slowed(?:\s+down)?|acoustic|unplugged|live|"
        r"instrumental|karaoke|a\s*cappella|acapella|demo(?:\s*\d+)?|rehearsal)"
        r"(?:\s+version)?|live(?:\s*演唱)?\s*版|remix(?:\s*版)?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s+((?:english|spanish|french|german|italian|portuguese|japanese|korean|"
        r"mandarin|cantonese|chinese|latin)\s+version)\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"\s+((?:cover(?:\s+version)?|mash[ -]?up|parody|reprise))\s*$", re.I),
    re.compile(
        r"\s+((?:feat(?:uring)?\.?|ft\.?)\s*.+|(?:solo|duet)\s+version)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\s+((?:(?:19|20)\d{2}\s+)?remaster(?:ed)?(?:\s+(?:19|20)\d{2})?|"
        r"clean(?:\s+version)?|explicit(?:\s+version)?|bonus\s+track(?:\s+version)?)\s*$",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class CompositionTitleIdentity:
    """Stable composition-title components without changing display metadata."""

    original: str
    base_title: str
    relation_tags: tuple[str, ...]
    recording_variant_key: str
    blocker_tags: tuple[str, ...]
    source_context_tags: tuple[str, ...]
    policy_version: str = COMPOSITION_TITLE_IDENTITY_POLICY_VERSION

    @property
    def key(self) -> str:
        """Return the composition-title key used with a canonical artist key."""

        return self.base_title


@lru_cache(maxsize=1)
def _traditional_to_simplified() -> OpenCC:
    return OpenCC("t2s")


def _prepare_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).translate(_PUNCTUATION_TRANSLATION)
    return _traditional_to_simplified().convert(text).casefold().strip()


def _canonical_text(value: str) -> str:
    text = "".join(character if character.isalnum() else " " for character in value)
    return " ".join(text.split())


def _matched_tags(
    fragment: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]
) -> tuple[str, ...]:
    return tuple(sorted(name for name, pattern in patterns if pattern.search(fragment)))


def _is_packaging_fragment(fragment: str) -> bool:
    text = fragment.strip().strip("()[] ")
    return bool(text) and any(pattern.search(text) for pattern in _PACKAGING_PATTERNS)


def _source_context(fragment: str) -> tuple[str, ...]:
    text = fragment.strip().strip("()[] ")
    if not text or not any(pattern.search(text) for pattern in _SOURCE_CONTEXT_PATTERNS):
        return ()
    return (_canonical_text(text),)


def _fragment_semantics(
    fragment: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    relation_tags = _matched_tags(fragment, _RELATION_PATTERNS)
    blocker_tags = _matched_tags(fragment, _BLOCKER_PATTERNS)
    source_context_tags = _source_context(fragment)
    # A named wrapper such as ``dancing witch version`` is a legitimate L3
    # alternate when it is isolated by brackets or a title delimiter.  Keep
    # bare titles such as ``Song Anniversary Version`` conservative: they are
    # not split by ``_trailing_fragment`` and therefore never reach this rule.
    if (
        not relation_tags
        and not blocker_tags
        and not source_context_tags
        and re.search(r"\bversion\s*$", fragment, re.IGNORECASE)
    ):
        relation_tags = ("alternate_arrangement",)
    return relation_tags, blocker_tags, source_context_tags


def _trailing_fragment(text: str) -> tuple[int, str] | None:
    for pattern in (_BRACKET_SUFFIX, _DELIMITED_SUFFIX, _PIPE_SUFFIX, *_BARE_SUFFIX_PATTERNS):
        match = pattern.search(text)
        if match is not None:
            return match.start(), match.group(1).strip()
    return None


def normalize_composition_track_title(name: str) -> CompositionTitleIdentity:
    """Return a conservative L3 composition identity for one display title.

    Only recognised trailing relation, blocker, source-context and packaging
    fragments are removed. Unknown suffixes remain part of ``base_title``.
    """

    if not isinstance(name, str):
        raise TypeError("track title must be a string")

    original = name
    text = _prepare_text(name)
    relation_tags: set[str] = set()
    blocker_tags: set[str] = set()
    source_context_tags: set[str] = set()
    variant_fragments: set[str] = set()

    changed = True
    while text and changed:
        changed = False
        match = _trailing_fragment(text)
        if match is None:
            break
        start, fragment = match
        relations, blockers, contexts = _fragment_semantics(fragment)
        if relations or blockers:
            relation_tags.update(relations)
            blocker_tags.update(blockers)
            variant_fragments.add(_canonical_text(fragment))
        elif contexts:
            source_context_tags.update(contexts)
        elif not _is_packaging_fragment(fragment):
            break
        stripped = text[:start].strip()
        if not stripped:
            break
        text = stripped
        changed = True

    base_title = _canonical_text(text)
    if not base_title:
        # Keep malformed titles distinct instead of manufacturing one empty key.
        base_title = _canonical_text(_prepare_text(original))
    if _STRUCTURAL_TITLE_PATTERN.search(base_title):
        blocker_tags.add("structural")

    return CompositionTitleIdentity(
        original=original,
        base_title=base_title,
        relation_tags=tuple(sorted(relation_tags)),
        recording_variant_key="|".join(
            sorted(fragment for fragment in variant_fragments if fragment)
        ),
        blocker_tags=tuple(sorted(blocker_tags)),
        source_context_tags=tuple(sorted(source_context_tags)),
    )


# Keep the L3-oriented spelling as a small convenience for planners without
# coupling this module to any existing L2 implementation.
normalize_l3_track_title = normalize_composition_track_title
