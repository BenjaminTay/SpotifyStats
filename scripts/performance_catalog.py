"""Current consumers and explicitly classified compatibility endpoints; GET only."""

from urllib.parse import quote


def endpoint_catalog(
    track_id=None,
    project_id=None,
    artist=None,
    year=None,
    entity_key=None,
    job_id=None,
    post_id=None,
):
    rows = []

    def add(path, consumer, usage="current", params=None):
        rows.append(
            {
                "endpoint": path,
                "consumer": consumer,
                "usage": usage,
                "params": params or {},
                "surface": "private-admin"
                if path == "/api/yearly-review/generation-status"
                or path.startswith(
                    (
                        "/api/import",
                        "/api/version-merge",
                        "/api/metadata/",
                        "/api/music-metadata/",
                        "/api/artist-identities",
                    )
                )
                else "public-readonly",
                "configured": "{" not in path
                and all("{" not in str(value) for value in (params or {}).values()),
            }
        )

    for path, consumer in [
        ("/home/overview", "Home"),
        ("/analysis/stats", "播放统计"),
        ("/analysis/charts", "播放排行"),
        ("/analysis/records", "播放记录"),
        ("/analysis/plays", "最近播放记录"),
        ("/analysis/play-dates", "播放日历"),
        ("/billboard/entity-lists", "Versus"),
        ("/billboard/year-end", "Year-end"),
        ("/yearly-review/available-years", "年度总结"),
        ("/yearly-review/generation-status", "年度维护状态"),
        ("/community/feed", "Community"),
        ("/community/trending", "Community"),
        ("/settings", "Settings"),
        ("/import/health", "Settings import health"),
        ("/import/preflight", "Settings import preflight"),
        ("/version-merge/groups", "Settings release groups"),
        ("/version-merge/track-groups", "Settings track groups"),
        ("/version-merge/l3-album-attributions/health", "Settings L3"),
        ("/version-merge/l1-identity-risks/health", "Settings L1"),
        ("/music-metadata/track-credits/status", "Settings credits"),
        ("/artist-identities", "Settings artist identity"),
        ("/artist-identities/events", "Settings artist identity audit"),
        ("/metadata/artist-genres/coverage", "Settings genre"),
        ("/metadata/artist-genres/taxonomy", "Settings genre"),
        ("/metadata/artist-genres/axis-gaps", "Settings genre"),
        ("/metadata/artist-genres/reviews", "Settings genre reviews"),
        ("/metadata/artist-languages/coverage", "Settings language"),
        ("/metadata/artist-languages/reviews", "Settings language reviews"),
    ]:
        add("/api" + path, consumer)
    add(
        "/api/artist-identities/candidates",
        "Settings artist identity candidates",
        params={"q": artist or "love"},
    )
    add("/api/billboard/weekly", "Weekly", params={"projection": "page", "entity": "tracks"})
    add("/api/billboard/all-time", "All-time", params={"projection": "entity", "entity": "tracks"})
    add("/api/billboard/all-time", "Number Ones", params={"projection": "number-ones"})
    add("/api/billboard/records", "Records", params={"projection": "page"})
    add(f"/api/community/post/{post_id or '{post_id}'}", "Community post")
    add("/api/community/feed", "Community account", params={"accounts": "@chartdata", "limit": 20})
    for name in (
        "archive-overview",
        "collection-journey",
        "collection-cohorts",
        "returns",
        "discovery",
        "other-media",
        "library/tracks",
        "library/albums",
        "library/artists",
        "library/playlists",
    ):
        add("/api/account/" + name, "音乐档案")
    add(
        "/api/music/search",
        "Quick Open/Search",
        params={"q": "love", "response_mode": "candidates", "eligibility": "current"},
    )
    add(
        "/api/music/search/context",
        "Search statistics",
        params={"entity_key": entity_key or "{entity_key}"},
    )
    for name in ("weekly", "all-time", "data", "records", "power-scores", "summaries"):
        add("/api/billboard/" + name, "完整兼容响应；页面使用显式 projection", "compatible")
    add("/api/dashboard/full", "旧 Dashboard", "unused")
    add("/api/analysis/overview", "旧聚合", "unused")
    add("/api/health", "服务就绪探针", "probe")
    add(f"/api/yearly-review/{year or '{year}'}", "年度总结")
    add(f"/api/import/status/{job_id or '{job_id}'}", "Settings import/maintenance job")
    track_id = track_id or "{track_id}"
    project_id = project_id or "{project_id}"
    artist = artist or "{artist}"
    identities = [
        ("track/canonical", track_id, f"tracks/l1/{track_id}"),
        ("album-project", project_id, f"album-projects/{project_id}"),
        (
            "artist",
            quote(artist, safe="{}") if artist else None,
            f"artists/{quote(artist, safe='{}')}" if artist else None,
        ),
    ]
    for kind, value, stats_path in identities:
        if value is None:
            continue
        views = ["summary", "overview"] + (
            ["tracks", "project"]
            if kind == "album-project"
            else ["tracks", "albums"]
            if kind == "artist"
            else []
        )
        for view in views:
            add(f"/api/billboard/{kind}/{value}", "音乐详情", params={"view": view})
        for subview in ["stats", "rankings", "plays", "play-dates"]:
            # Track subviews use L1-specific stats and the existing detail route for chart views.
            if kind == "track/canonical" and subview == "rankings":
                continue
            add(
                f"/api/music/{stats_path}/{subview}",
                "音乐详情播放统计/子视图",
                params={"include_rank_context": "false"} if subview == "stats" else None,
            )
        add(
            f"/api/music/{stats_path}/stats",
            "音乐详情延后全局排名",
            params={"include_rank_context": "true"},
        )
    return rows
