from __future__ import annotations

import pytest

from backend.domains.metadata.track_composition_identity import (
    COMPOSITION_TITLE_IDENTITY_POLICY_VERSION,
    normalize_composition_track_title,
    normalize_l3_track_title,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("title", "base_title", "relation_tag"),
    [
        ("Song (Acoustic Version)", "song", "acoustic"),
        ("Song - Unplugged", "song", "acoustic"),
        ("Song - Live at Wembley", "song", "live"),
        ("会呼吸的痛(Live演唱版)", "会呼吸的痛", "live"),
        ("字字句句 - Live版", "字字句句", "live"),
        ("Song - Kungs Remix", "song", "remix"),
        ("Song (Taylor's Version)", "song", "rerecord"),
        ("Song (From The Vault)", "song", "rerecord"),
        ("Song - Radio Edit", "song", "radio_edit"),
        ("Song - Single Version", "song", "single_version"),
        ("Song - Album Version", "song", "album_version"),
        ("Song - Original Version", "song", "original_version"),
        ("Song - Extended Mix", "song", "extended"),
        ("All Too Well (10 Minute Version)", "all too well", "extended"),
        ("Song - Instrumental", "song", "instrumental"),
        ("Song - Karaoke Version", "song", "karaoke"),
        ("Song - A Cappella", "song", "acapella"),
        ("Song - Demo", "song", "demo"),
        ("Song - Sped Up Version", "song", "sped_up"),
        ("Song - Slowed Down", "song", "slowed"),
        ("Song - Rehearsal Version", "song", "rehearsal"),
        ("on the road - Demo2", "on the road", "demo"),
        ("Song (Sad Girl Autumn Version)", "song", "alternate_arrangement"),
        ("Song - Cabin in Candlelight Version", "song", "alternate_arrangement"),
        ("Cupid - Twin Version", "cupid", "alternate_arrangement"),
        ("Song (feat. Guest)", "song", "collaboration_variant"),
        ("Girl, so confusing featuring lorde", "girl so confusing", "collaboration_variant"),
        ("不灭(feat.张悬)", "不灭", "collaboration_variant"),
        ("Song - Duet Version", "song", "collaboration_variant"),
    ],
)
def test_recognised_recording_relations_share_a_stable_base_title(
    title: str, base_title: str, relation_tag: str
) -> None:
    identity = normalize_composition_track_title(title)

    assert identity.base_title == base_title
    assert relation_tag in identity.relation_tags
    assert identity.recording_variant_key
    assert identity.blocker_tags == ()
    assert identity.policy_version == COMPOSITION_TITLE_IDENTITY_POLICY_VERSION


def test_nested_relation_wrappers_are_combined_deterministically() -> None:
    identity = normalize_composition_track_title(
        "All Too Well (10 Minute Version) (Taylor's Version) (From The Vault)"
    )

    assert identity.base_title == "all too well"
    assert identity.relation_tags == ("extended", "rerecord")
    assert identity.recording_variant_key == ("10 minute version|from the vault|taylor s version")


def test_bare_closed_list_suffix_is_supported_without_generic_version_stripping() -> None:
    assert normalize_composition_track_title("S&M Remix").base_title == "s m"
    assert normalize_composition_track_title("Song Acoustic Version").base_title == "song"
    assert normalize_composition_track_title("Song 2018 Remastered").base_title == "song"
    unknown = normalize_composition_track_title("Song Anniversary Version")
    assert unknown.base_title == "song anniversary version"
    assert unknown.relation_tags == ()
    assert unknown.recording_variant_key == ""


@pytest.mark.parametrize(
    ("title", "blocker_tag"),
    [
        ("Song - Spanish Version", "translation"),
        ("Song (Cover Version)", "cover"),
        ("Song - Mashup", "mashup"),
        ("Song - Parody", "parody"),
        ("Song - Sampled Version", "sample"),
        ("Song (Reprise)", "reprise"),
        ("Intro", "structural"),
        ("Outro - Live", "structural"),
        ("Interlude (Acoustic Version)", "structural"),
        ("Prelude: Live", "structural"),
    ],
)
def test_unsafe_or_structural_relations_are_explicit_blockers(title: str, blocker_tag: str) -> None:
    identity = normalize_composition_track_title(title)

    assert blocker_tag in identity.blocker_tags


def test_relation_and_blocker_can_coexist_for_fail_closed_planning() -> None:
    identity = normalize_composition_track_title("Song - Spanish Acoustic Version")

    assert identity.base_title == "song"
    assert identity.relation_tags == ("acoustic",)
    assert identity.blocker_tags == ("translation",)


def test_source_context_and_packaging_are_not_recording_relations() -> None:
    soundtrack = normalize_composition_track_title('City Of Stars - From "La La Land" Soundtrack')
    remaster = normalize_composition_track_title("Song - 2018 Remastered")
    long_pond = normalize_composition_track_title(
        "All Too Well (Sad Girl Autumn Version) - Recorded at Long Pond Studios"
    )
    album_source = normalize_composition_track_title(
        "Barbie Dreams (feat. Kaliii) [From Barbie The Album]"
    )

    assert soundtrack.base_title == "city of stars"
    assert soundtrack.source_context_tags == ("from la la land soundtrack",)
    assert soundtrack.relation_tags == ()
    assert soundtrack.recording_variant_key == ""
    assert remaster.base_title == "song"
    assert remaster.relation_tags == ()
    assert remaster.recording_variant_key == ""
    assert long_pond.base_title == "all too well"
    assert long_pond.relation_tags == ("alternate_arrangement",)
    assert long_pond.source_context_tags == ("recorded at long pond studios",)
    assert album_source.base_title == "barbie dreams"
    assert album_source.relation_tags == ("collaboration_variant",)
    assert album_source.source_context_tags == ("from barbie the album",)


def test_long_pond_session_is_a_live_relation() -> None:
    identity = normalize_composition_track_title(
        "exile (feat. Bon Iver) - the long pond studio sessions"
    )

    assert identity.base_title == "exile"
    assert identity.relation_tags == ("collaboration_variant", "live")


def test_nfkc_traditional_chinese_and_punctuation_normalise_stably() -> None:
    traditional = normalize_composition_track_title("歌曲（現場版）")
    simplified = normalize_composition_track_title("歌曲 (现场版)")

    assert traditional.base_title == simplified.base_title == "歌曲"
    assert traditional.relation_tags == simplified.relation_tags == ("live",)
    assert traditional.recording_variant_key == simplified.recording_variant_key == "现场版"


def test_alias_and_type_validation() -> None:
    assert normalize_l3_track_title("Song - Demo") == normalize_composition_track_title(
        "Song - Demo"
    )
    with pytest.raises(TypeError, match="track title must be a string"):
        normalize_composition_track_title(None)  # type: ignore[arg-type]
