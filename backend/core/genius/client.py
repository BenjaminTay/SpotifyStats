from __future__ import annotations

import re
import time

import lyricsgenius

from .models import AlbumInfo, SearchResult, Song


class GeniusClient:
    def __init__(
        self,
        access_token: str,
        proxy: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self.genius = lyricsgenius.Genius(
            access_token=access_token,
            timeout=timeout,
            sleep_time=0.5,
            retries=3,
            remove_section_headers=False,
            proxy=proxy,
        )

    # ── 搜索 ──────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """搜索歌曲，返回匹配结果列表。"""
        results = []
        for page in range(1, (limit // 5) + 2):
            resp = self.genius.search_songs(query, per_page=5, page=page)
            hits = (resp.get("response") or resp).get("hits", [])
            if not hits:
                break
            for hit in hits:
                item = hit.get("result", {})
                if not item.get("title"):
                    continue
                results.append(
                    SearchResult(
                        id=item.get("id", 0),
                        title=item.get("title", ""),
                        artist=item.get("primary_artist", {}).get("name", ""),
                        url=item.get("url", ""),
                        lyrics_state=item.get("lyrics_state", "complete"),
                    )
                )
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
            time.sleep(0.3)
        return results

    def search_lyrics(self, query: str, limit: int = 10) -> list[SearchResult]:
        """按歌词内容搜索。"""
        results = []
        for page in range(1, (limit // 5) + 2):
            resp = self.genius.search_lyrics(query, per_page=5, page=page)
            # search_lyrics 返回 {"sections": [{"type": "lyric", "hits": [...]}]}
            all_hits = []
            for section in resp.get("sections", []):
                if section.get("type") == "lyric":
                    all_hits.extend(section.get("hits", []))
            if not all_hits:
                break
            for hit in all_hits:
                item = hit.get("result", {})
                if not item.get("title"):
                    continue
                results.append(
                    SearchResult(
                        id=item.get("id", 0),
                        title=item.get("title", ""),
                        artist=item.get("primary_artist", {}).get("name", ""),
                        url=item.get("url", ""),
                        lyrics_state=item.get("lyrics_state", "complete"),
                    )
                )
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
            time.sleep(0.3)
        return results

    # ── 单首歌曲 ──────────────────────────────────────────

    def get_song(self, title: str, artist: str = "") -> Song | None:
        """根据歌名和歌手获取完整歌词。"""
        gs = self.genius.search_song(title=title, artist=artist)
        if gs is None:
            return None
        return self._song_from_genius(gs)

    def get_song_by_id(self, song_id: int) -> Song | None:
        """根据 Genius song ID 获取完整歌词。"""
        gs = self.genius.search_song(song_id=song_id)
        if gs is None:
            return None
        return self._song_from_genius(gs)

    def _song_from_genius(self, gs) -> Song:
        """将 lyricsgenius Song 转为自有 Song 模型。"""
        lyrics = self._clean_lyrics(gs.lyrics)
        album = gs.album

        # Handle both dict and object album types from different lyricsgenius versions
        def _alb(key, default=""):
            if album is None:
                return default
            if isinstance(album, dict):
                return album.get(key, default)
            return getattr(album, key, default)

        cover = gs.song_art_image_url or gs.header_image_url or _alb("cover_art_url", "")
        release = ""
        rdc = _alb("release_date_components", None)
        if rdc:
            if isinstance(rdc, dict):
                release = f"{rdc.get('year', '')}-{rdc.get('month', '')}-{rdc.get('day', '')}"
            else:
                release = f"{getattr(rdc, 'year', '')}-{getattr(rdc, 'month', '')}-{getattr(rdc, 'day', '')}"
        return Song(
            id=gs._body.get("id", 0) if isinstance(gs._body, dict) else gs.id,
            title=gs.title,
            artist=gs.artist,
            lyrics=lyrics,
            url=gs.url or "",
            album_name=_alb("name", ""),
            cover_url=cover or "",
            release_date=release,
        )

    # ── 专辑 ──────────────────────────────────────────────

    def search_album(self, name: str, artist: str = "") -> AlbumInfo | None:
        """搜索专辑并获取全部曲目歌词。"""
        album = self.genius.search_album(name=name, artist=artist)
        if album is None:
            return None
        tracks = []
        for num, gs in album.tracks:
            if gs is None:
                continue
            tracks.append(self._song_from_genius(gs))
        return AlbumInfo(
            id=album._body.get("id", 0),
            name=album.name,
            artist=album.artist.get("name", ""),
            cover_url=album.cover_art_url or "",
            release_date=str(album.release_date_components or ""),
            url=album.url or "",
            tracks=tracks,
        )

    # ── 艺人 ──────────────────────────────────────────────

    def get_artist_songs(
        self,
        artist_name: str,
        max_songs: int | None = None,
        sort: str = "popularity",
        include_features: bool = False,
    ) -> list[Song]:
        """获取艺人的歌曲列表（含歌词）。"""
        artist = self.genius.search_artist(
            artist_name=artist_name,
            max_songs=max_songs,
            sort=sort,
            include_features=include_features,
        )
        if artist is None:
            return []
        return [self._song_from_genius(gs) for gs in artist.songs]

    # ── 排行榜 ────────────────────────────────────────────

    def get_chart_list(
        self,
        genre: str = "all",
        period: str = "day",
        count: int = 20,
    ) -> list[SearchResult]:
        """获取排行榜歌曲列表（不含歌词）。"""
        try:
            resp = self.genius.charts(
                type_="songs",
                chart_genre=genre,
                time_period=period,
                per_page=min(count, 50),
            )
        except Exception:
            try:
                resp = self.genius.leaderboard(time_period=period, per_page=min(count, 50))
            except Exception:
                return []

        entries = resp.get("chart_items", []) or resp.get("leaderboard", [])
        results = []
        for entry in entries:
            song_data = entry.get("song") or entry.get("item", {})
            artist = song_data.get("primary_artist") or song_data.get("artist", {})
            results.append(
                SearchResult(
                    id=song_data.get("id", 0),
                    title=song_data.get("title", ""),
                    artist=artist.get("name", "") if isinstance(artist, dict) else "",
                    url=song_data.get("url", ""),
                    lyrics_state=song_data.get("lyrics_state", "complete"),
                )
            )
            if len(results) >= count:
                break
        return results

    # ── 封面图 ────────────────────────────────────────────

    def download_cover(self, url: str, filepath: str) -> bool:
        """下载封面图片，保存到 filepath。"""
        if not url:
            return False
        try:
            resp = self.genius._session.get(url, timeout=30)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
        except Exception:
            return False

    # ── 清理 ──────────────────────────────────────────────

    SECTION_RE = re.compile(r"\[([A-Z][^\]]*)\]")

    def _clean_lyrics(self, lyrics: str) -> str:
        lines = lyrics.strip().split("\n")
        cleaned = []
        in_header = True

        for line in lines:
            stripped = line.rstrip()

            # Skip embed markers
            if stripped.endswith("Embed") and stripped[:-5].strip().isdigit():
                continue
            # Skip long numeric IDs (but not short numbers)
            if stripped.isdigit() and len(stripped) > 4:
                continue

            # Metadata lines: skip but extract the last embedded section tag
            # (section header always appears after the description text)
            if any(
                kw in stripped for kw in ("Contributors", "Translations", "You Might Also Like")
            ):
                matches = self.SECTION_RE.findall(stripped)
                if matches:
                    cleaned.append(f"[{matches[-1]}]")
                    in_header = False
                continue

            if in_header:
                if stripped.startswith("["):
                    in_header = False
                elif any(kw in stripped.lower() for kw in ("lyrics", "read more")):
                    # May still contain a section tag at the end (e.g. "…Read More [Verse 1]")
                    m = self.SECTION_RE.search(stripped)
                    if m:
                        cleaned.append(f"[{m.group(1)}]")
                        in_header = False
                    continue
                elif len(stripped) > 30:
                    # Looks like actual lyric content
                    in_header = False
                else:
                    continue

            cleaned.append(stripped)

        # Normalize spacing: exactly one blank line before each section header
        # and collapse consecutive blank lines
        result = []
        for line in cleaned:
            is_section = line.startswith("[")
            if is_section and result and result[-1] != "":
                result.append("")
            if line == "" and result and result[-1] == "":
                continue
            result.append(line)

        return "\n".join(result).strip()
