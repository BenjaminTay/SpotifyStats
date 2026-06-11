#!/usr/bin/env python3
"""Split feed_generator.py into sub-modules based on function domain.

Usage:
    python scripts/split_feed_generator.py
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path("backend/domains/community")

# Map: target_file -> list of function names
FN_MAP = {
    "feed_helpers.py": [
        "_make_id",
        "_fmt_ordinal",
        "_fmt_number",
        "_week_end_date",
        "_pick",
        "_generate_metrics",
        "_row_to_dict",
        "_entries_for_week",
        "_album_entries_for_week",
        "_artist_entries_for_week",
    ],
    "feed_data.py": [
        "_load_chart_data",
        "_compute_personal_weekly",
        "_load_collection_data",
    ],
    "feed_weekly.py": [
        "_gen_no1_posts",
        "_gen_top10_summary",
        "_gen_debut_posts",
        "_gen_biggest_jump_post",
        "_gen_biggest_drop_post",
        "_gen_artist_first_top10",
        "_gen_top5_debut",
    ],
    "feed_records.py": [
        "_gen_record_posts",
        "_gen_album_record_posts",
        "_gen_artist_chart_record_posts",
        "_gen_milestone_posts",
        "_gen_record_tied_posts",
        "_gen_record_watch_posts",
        "_gen_record_self_replacement",
        "_gen_record_triple_no1",
        "_gen_record_concurrent_entries",
    ],
    "feed_personal.py": [
        "_gen_weekly_personal",
        "_gen_monthly_personal",
        "_gen_quarterly_personal",
        "_gen_yearly_personal",
        "_gen_playback_milestone",
        "_gen_collection_posts",
        "_gen_collection_milestone",
        "_gen_throwback_post",
        "_gen_decade_comparison",
    ],
    "feed_talk.py": [
        "_gen_talk_weekly_race",
        "_gen_talk_market_overview",
        "_gen_talk_longevity_alert",
    ],
    "feed_ranking.py": [
        "_base_score",
        "_comp_factor",
        "_indiv_factor",
        "_compute_real_power_score",
        "_make_alltime_ranking",
        "_gen_alltime_ranking_posts",
        "_gen_alltime_ranking_summary",
        "_gen_album_no1_post",
        "_gen_artist_no1_post",
        "_gen_alltime_stats",
    ],
    "feed_images.py": [
        "_load_cover_maps",
        "_enrich_post_images",
    ],
}

# Imports needed by each sub-module (in addition to any from the base)
MODULE_IMPORTS: dict[str, list[str]] = {
    "feed_helpers.py": [
        "import hashlib",
        "import random",
        "from datetime import datetime, timedelta",
        "",
        "import pandas as pd",
        "",
        "from backend.domains.community.accounts import FOLLOWER_MULTIPLIERS",
        "from backend.domains.community.post_types import PostMetrics",
    ],
    "feed_data.py": [
        "import pandas as pd",
        "",
        "from backend.domains.billboard.chart_ranking import (",
        "    compute_album_weekly_rankings,",
        "    compute_artist_weekly_rankings,",
        "    compute_weekly_rankings,",
        ")",
        "from backend.domains.billboard.data_loader import (",
        "    _try_load_from_agg,",
        "    load_billboard_raw,",
        "    load_billboard_raw_for_artists,",
        ")",
    ],
    "feed_weekly.py": [
        "from backend.domains.community.feed_helpers import (",
        "    _entries_for_week,",
        "    _make_id,",
        "    _pick,",
        "    _fmt_ordinal,",
        ")",
        "from backend.domains.community.historical_state import HistoricalState",
        "from backend.domains.community.post_types import (",
        "    POST_SIGNIFICANCE,",
        "    POST_TAGS,",
        "    CommunityPost,",
        "    PostType,",
        ")",
    ],
    "feed_records.py": [
        "from backend.domains.community.feed_helpers import (",
        "    _entries_for_week,",
        "    _make_id,",
        "    _pick,",
        "    _fmt_ordinal,",
        "    _fmt_number,",
        ")",
        "from backend.domains.community.historical_state import HistoricalState",
        "from backend.domains.community.post_types import (",
        "    POST_SIGNIFICANCE,",
        "    POST_TAGS,",
        "    CommunityPost,",
        "    PostType,",
        ")",
    ],
    "feed_personal.py": [
        "import math",
        "",
        "import pandas as pd",
        "",
        "from backend.domains.community.feed_helpers import (",
        "    _make_id,",
        "    _pick,",
        "    _fmt_number,",
        "    _fmt_ordinal,",
        "    _entries_for_week,",
        ")",
        "from backend.domains.community.historical_state import HistoricalState",
        "from backend.domains.community.post_types import (",
        "    POST_SIGNIFICANCE,",
        "    POST_TAGS,",
        "    CommunityPost,",
        "    PostType,",
        ")",
    ],
    "feed_talk.py": [
        "from backend.domains.community.feed_helpers import (",
        "    _make_id,",
        "    _pick,",
        "    _fmt_number,",
        "    _fmt_ordinal,",
        ")",
        "from backend.domains.community.historical_state import HistoricalState",
        "from backend.domains.community.post_types import (",
        "    POST_SIGNIFICANCE,",
        "    POST_TAGS,",
        "    CommunityPost,",
        "    PostType,",
        ")",
    ],
    "feed_ranking.py": [
        "import math",
        "from datetime import datetime",
        "",
        "import pandas as pd",
        "",
        "from backend.domains.billboard.chart_power_score import (",
        "    _BASE_DECAY,",
        "    _COMP_RANGE,",
        "    _DEBUT_NO1_BONUS,",
        "    _INDIV_GAP_RANGE,",
        "    _INDIV_RANGE,",
        "    _LONGEVITY_FACTOR,",
        "    _PEAK_BONUS,",
        "    _RANK1_BASE,",
        "    _TOP5_BONUS,",
        "    _TOP10_BONUS,",
        ")",
        "from backend.domains.community.feed_helpers import (",
        "    _album_entries_for_week,",
        "    _artist_entries_for_week,",
        "    _entries_for_week,",
        "    _make_id,",
        "    _pick,",
        "    _fmt_number,",
        "    _fmt_ordinal,",
        ")",
        "from backend.domains.community.historical_state import HistoricalState",
        "from backend.domains.community.post_types import (",
        "    POST_SIGNIFICANCE,",
        "    POST_TAGS,",
        "    CommunityPost,",
        "    PostType,",
        ")",
    ],
    "feed_images.py": [
        "from backend.domains.community.post_types import CommunityPost",
    ],
}

# Modules that need `from __future__ import annotations` (any with `list[dict] | None` etc.)
NEEDS_FUTURE = {
    "feed_weekly.py",
    "feed_records.py",
    "feed_personal.py",
    "feed_talk.py",
    "feed_ranking.py",
    "feed_images.py",
}


def get_functions(source: str) -> dict[str, tuple[int, int]]:
    """Extract function names and (start_line, end_line) from source."""
    lines = source.split("\n")
    funcs = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^def\s+(\w+)", lines[i])
        if m:
            name = m.group(1)
            start = i  # 0-indexed line
            # Find end: next top-level def or end of file
            j = i + 1
            while j < len(lines):
                if re.match(r"^(def\s+|@ttl_cached)", lines[j]):
                    break
                j += 1
            # If next line is @ttl_cached, skip it and find the actual def
            if j < len(lines) and lines[j].startswith("@ttl_cached"):
                j += 1  # skip decorator
                while j < len(lines):
                    if re.match(r"^def\s+", lines[j]):
                        break
                    j += 1
            funcs[name] = (start + 1, j)  # convert to 1-indexed, end exclusive
            i = j
        else:
            i += 1
    return funcs


def build_module(target: str, fnames: list[str], source: str) -> str:
    """Build a sub-module file from source extracting listed function names."""
    lines = source.split("\n")
    funcs = get_functions(source)

    # Collect line ranges for the functions in this module
    ranges = []
    for fname in fnames:
        if fname in funcs:
            start, end = funcs[fname]
            ranges.append((start, end))
        else:
            print(f"  WARNING: {fname} not found in source")

    if not ranges:
        return ""

    ranges.sort()

    # Build module content
    parts = []

    # Module docstring
    domain_name = target.replace("feed_", "").replace(".py", "")
    if domain_name == "helpers":
        desc = "Helper utilities for feed generation."
    elif domain_name == "data":
        desc = "Data loading for community feed generation."
    elif domain_name == "weekly":
        desc = "Weekly dispatch posts — #1 announcements, top 10, debuts, jumps/drops."
    elif domain_name == "records":
        desc = "Record and milestone posts — broken/tied/watch, self-replacement, triple #1."
    elif domain_name == "personal":
        desc = "Personal playback and collection posts."
    elif domain_name == "talk":
        desc = "@talkofthecharts deep analysis posts."
    elif domain_name == "ranking":
        desc = "All-time ranking and Power Score posts."
    elif domain_name == "images":
        desc = "Cover image loading and post enrichment."
    else:
        desc = "Feed generator sub-module."

    parts.append(f'"""Community feed — {desc}"""')
    parts.append("")

    if target in NEEDS_FUTURE:
        parts.append("from __future__ import annotations")
        parts.append("")

    # Add module-specific imports
    if target in MODULE_IMPORTS:
        for line in MODULE_IMPORTS[target]:
            parts.append(line)
        parts.append("")

    parts.append("")
    parts.append("# ──────────────────────────────────────────────")
    parts.append("")

    # Extract functions
    for start, end in ranges:
        func_lines = lines[start - 1 : end - 1]  # 1-indexed to 0-indexed, end exclusive
        parts.extend(func_lines)
        parts.append("")
        parts.append("")

    return "\n".join(parts)


def main():
    src_path = BASE / "feed_generator.py"
    source = src_path.read_text(encoding="utf-8")

    # Verify all functions are accounted for
    all_funcs = set(get_functions(source).keys())
    mapped_funcs = set()
    for fnames in FN_MAP.values():
        mapped_funcs.update(fnames)

    unmapped = all_funcs - mapped_funcs
    if unmapped:
        print(f"Unmapped functions (will stay in main file): {unmapped}")
    missing = mapped_funcs - all_funcs
    if missing:
        print(f"Functions in map but not in source: {missing}")

    # Create each sub-module
    for target, fnames in FN_MAP.items():
        content = build_module(target, fnames, source)
        if content:
            out_path = BASE / target
            out_path.write_text(content, encoding="utf-8")
            line_count = len(content.split("\n"))
            print(f"  Wrote {target} ({line_count} lines, {len(fnames)} functions)")
        else:
            print(f"  SKIPPED {target} (no functions found)")

    print(f"\nDone. Sub-modules written to {BASE.resolve()}/")
    print("Next: update feed_generator.py to import from sub-modules.")


if __name__ == "__main__":
    main()
