"""Simulated X-style music news accounts."""

ACCOUNTS = [
    {
        "handle": "@chartdata",
        "display_name": "chart data",
        "bio": "Billboard Hot 100 weekly updates. Charts, stats, and music news.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #1DB954, #191414)",
            "initials": "CD",
            "icon": "",
        },
        "follower_tier": "megastar",
        "content_tags": ["weekly", "no1", "top10", "debut"],
    },
    {
        "handle": "@billboardcharts",
        "display_name": "billboard charts",
        "bio": "Official Billboard chart summaries. The week's top 10, every week.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #E13300, #B02800)",
            "initials": "BB",
            "icon": "",
        },
        "follower_tier": "megastar",
        "content_tags": ["weekly", "top10", "summary"],
    },
    {
        "handle": "@talkofthecharts",
        "display_name": "Talk of the Charts",
        "bio": "Deep dives into chart statistics, historical analysis, and record tracking.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #4A90D9, #2C5F8A)",
            "initials": "TC",
            "icon": "",
        },
        "follower_tier": "major",
        "content_tags": ["stat", "record", "history", "analysis"],
    },
    {
        "handle": "@popcrave",
        "display_name": "Pop Crave",
        "bio": "Pop music news, artist milestones, and chart achievements.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #E91E63, #880E4F)",
            "initials": "PC",
            "icon": "",
        },
        "follower_tier": "megastar",
        "content_tags": ["milestone", "news", "artist"],
    },
    {
        "handle": "@chartstats",
        "display_name": "ChartStats",
        "bio": "Pure chart statistics. Numbers, rankings, and data visualizations described in text.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #7C4DFF, #4A148C)",
            "initials": "CS",
            "icon": "",
        },
        "follower_tier": "major",
        "content_tags": ["stat", "history", "alltime", "analysis"],
    },
    {
        "handle": "@debutwatch",
        "display_name": "Debut Watch",
        "bio": "Tracking first-week entries and debut achievements on the Hot 100.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #FF9800, #E65100)",
            "initials": "DW",
            "icon": "",
        },
        "follower_tier": "mid",
        "content_tags": ["debut", "new_entry"],
    },
    {
        "handle": "@recordwatch",
        "display_name": "Record Watch",
        "bio": "Monitoring chart records — when they're close to breaking, and when they fall.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #F44336, #B71C1C)",
            "initials": "RW",
            "icon": "",
        },
        "follower_tier": "mid",
        "content_tags": ["record", "milestone", "history"],
    },
    {
        "handle": "@throwbackcharts",
        "display_name": "throwback charts",
        "bio": "On this week in Billboard history. Chart throwbacks and nostalgia.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #795548, #4E342E)",
            "initials": "TB",
            "icon": "",
        },
        "follower_tier": "mid",
        "content_tags": ["history", "throwback", "weekly"],
    },
    {
        "handle": "@spotifystats",
        "display_name": "Spotify Stats",
        "bio": "Your personal listening data, analyzed and narrated. Weekly wraps, monthly reviews, and milestones.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #1DB954, #0D7A3E)",
            "initials": "SS",
            "icon": "",
        },
        "follower_tier": "major",
        "content_tags": ["personal", "weekly", "monthly", "yearly", "milestone"],
    },
    {
        "handle": "@collectionvault",
        "display_name": "Collection Vault",
        "bio": "Saved tracks analysis, library insights, and collection behavior patterns.",
        "avatar": {
            "bg_gradient": "linear-gradient(135deg, #607D8B, #37474F)",
            "initials": "CV",
            "icon": "",
        },
        "follower_tier": "niche",
        "content_tags": ["collection", "insight", "personal"],
    },
]

# Lookup helpers
ACCOUNT_BY_HANDLE = {a["handle"]: a for a in ACCOUNTS}
FOLLOWER_MULTIPLIERS = {
    "megastar": 1.0,
    "major": 0.40,
    "mid": 0.15,
    "niche": 0.04,
}
