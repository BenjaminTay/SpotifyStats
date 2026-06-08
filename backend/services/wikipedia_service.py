"""Wikipedia enrichment service — fetch album/artist/track info from Wikipedia."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.core.db import get_db
from backend.providers.wikipedia.client import WikipediaProvider

WIKI_API = "https://en.wikipedia.org/w/api.php"
ZH_WIKI_API = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "SpotifyStats/1.0 (personal analytics; contact@example.com)"

PROXY = None
WIKI_PROVIDER = None


def _get_proxy():
    global PROXY
    if PROXY is not None:
        return PROXY
    from backend.core.config import HTTP_PROXY, HTTPS_PROXY

    PROXY = HTTPS_PROXY or HTTP_PROXY
    return PROXY or None


def _wiki_provider():
    global WIKI_PROVIDER
    if WIKI_PROVIDER is None:
        WIKI_PROVIDER = WikipediaProvider()
    return WIKI_PROVIDER


# ═══════════════════════════════════════════════════════════════════════════
# Wikipedia page search
# ═══════════════════════════════════════════════════════════════════════════


def _search_wiki(query, lang="en"):
    """Search Wikipedia for a page title. Returns (title, pageid) or None."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 3,
        "format": "json",
    }
    try:
        data = _wiki_provider().query(params, lang)
        results = data.get("query", {}).get("search", []) if data else []
        if results:
            return results[0]["title"]
    except Exception:
        pass
    return None


def _wiki_page_url(title, lang="en"):
    return _wiki_provider().page_url(title, lang)


def _fetch_page_data(title, lang="en"):
    """Fetch page summary, description, and thumbnail in ONE combined API call."""
    params = {
        "action": "query",
        "prop": "extracts|description|pageimages",
        "exintro": "1",
        "explaintext": "1",
        "exsectionformat": "plain",
        "piprop": "thumbnail",
        "pithumbsize": "400",
        "titles": title,
        "redirects": "1",
        "format": "json",
    }
    try:
        data = _wiki_provider().query(params, lang)
        pages = data.get("query", {}).get("pages", {}) if data else {}
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            return {
                "title": page.get("title", title),
                "extract": page.get("extract", ""),
                "pageid": page.get("pageid", 0),
                "description": page.get("description", ""),
                "thumbnail": thumb.get("source", ""),
            }
    except Exception:
        pass
    return None


def _fetch_full_extract(title, lang="en"):
    """Fetch full page extract via MediaWiki API."""
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "exsectionformat": "wiki",
        "titles": title,
        "redirects": "1",
        "format": "json",
    }
    try:
        data = _wiki_provider().query(params, lang)
        pages = data.get("query", {}).get("pages", {}) if data else {}
        for page in pages.values():
            return page.get("extract", "")
    except Exception:
        pass
    return ""


def _fetch_wikitext(title, lang="en"):
    """Fetch raw wikitext via action=parse API for infobox parsing."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
        "redirects": "1",
    }
    try:
        data = _wiki_provider().query(params, lang)
        return data.get("parse", {}).get("wikitext", {}).get("*", "") if data else ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# Wikipedia page search
# ═══════════════════════════════════════════════════════════════════════════


def find_album_page(album_name, artist_name):
    """Find Wikipedia page for an album. Tries English first, then Chinese."""
    # Strategy 1: "{Album} (album)" with artist
    for lang in ("en", "zh"):
        result = _search_wiki(f"{album_name} {artist_name} album", lang)
        if result:
            return result, lang
        result = _search_wiki(f"{album_name} album", lang)
        if result:
            return result, lang
    return None, None


def find_artist_page(artist_name):
    """Find Wikipedia page for an artist."""
    for lang in ("en", "zh"):
        # Try exact name first, then with qualifiers
        for query in (artist_name, f"{artist_name} singer", f"{artist_name} musician"):
            result = _search_wiki(query, lang)
            if result:
                # Reject clearly off-topic pages
                if _is_valid_artist_page(result, artist_name):
                    return result, lang
    return None, None


def _is_valid_artist_page(title, artist_name):
    """Reject Wikipedia pages that are about controversies, disputes, etc. rather than the artist."""
    bad_patterns = [
        "controversy",
        "dispute",
        "incident",
        "deepfake",
        "pornography",
        "sexual",
        "death of",
        "murder of",
        "killing of",
        "discography",
        "videography",
        "filmography",
        "albums",
        "singles",
        "tours",
    ]
    title_lower = title.lower()
    for pattern in bad_patterns:
        if pattern in title_lower:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Infobox parsing
# ═══════════════════════════════════════════════════════════════════════════


def _parse_infobox(wikitext):
    """Parse infobox from wikitext. Returns dict of key-value pairs."""
    if not wikitext:
        return {}

    # Find the infobox block (album, single, or musical artist)
    match = re.search(
        r"\{\{(Infobox (?:album|song|single|musical artist|[Mm]usical artist))\b.*?\n\}\}",
        wikitext,
        re.DOTALL,
    )
    if not match:
        match = re.search(r"\{\{(Infobox\s+album.*?)\n\s*\n", wikitext, re.DOTALL)
    if not match:
        return {}

    infobox = match.group(0)
    result = {}

    # Parse simple key-value pairs: | key = value
    for m in re.finditer(
        r"^\s*\|\s*(\w+(?:\s+\w+)*)\s*=\s*(.+?)(?=\n\s*[\|\}])", infobox, re.MULTILINE | re.DOTALL
    ):
        key = m.group(1).strip().lower().replace(" ", "_")
        value = _clean_wiki_value(m.group(2))
        if value:
            result[key] = value

    # Parse singles from {{Singles}} template inside misc
    singles = _parse_singles_template(infobox)
    if singles:
        result["singles"] = singles

    return result


def _parse_singles_template(wikitext):
    """Extract singles list with dates from {{Singles}} template."""
    singles = []
    # Find {{Singles ... }} block
    match = re.search(r"\{\{Singles\s*\n(.*?)\n\s*\}\}", wikitext, re.DOTALL)
    if not match:
        return singles

    block = match.group(1)
    # Parse singleN = name, singleNdate = date entries
    i = 1
    while True:
        name_match = re.search(rf"\|\s*single{i}\s*=\s*(.+)", block)
        if not name_match:
            break
        name = _clean_wiki_value(name_match.group(1))
        date_match = re.search(rf"\|\s*single{i}date\s*=\s*(.+)", block)
        date = _clean_wiki_value(date_match.group(1)) if date_match else None

        if name:
            singles.append({"name": name, "date": date})
        i += 1

    # Also try format: single1 = "Name" / "Date"
    if not singles:
        for m in re.finditer(r"\|\s*single(\d+)\s*=\s*(.+)", block):
            parts = m.group(2).split("/")
            if len(parts) == 2:
                name = _clean_wiki_value(parts[0])
                date = _clean_wiki_value(parts[1])
                singles.append({"name": name, "date": date})

    return singles


def _clean_wiki_value(value):
    """Remove wiki markup from a value string, preserving meaningful content."""
    value = value.strip()
    # Extract dates from common templates before removing them
    # {{Start date|YYYY|MM|DD}} or {{Start date and age|YYYY|MM|DD}} (case-insensitive)
    date_match = re.search(
        r"\{\{(?:[Ss]tart\s*date(?:\s*and\s*age)?)\|(\d{4})\|(\d{1,2})\|(\d{1,2})\}\}", value
    )
    if date_match:
        y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
        value = f"{y}年{m}月{d}日"
    # {{Plainlist|...}} → extract list items
    plainlist_match = re.search(r"\{\{Plainlist\s*\|\s*(.*?)\}\}", value, re.DOTALL)
    if plainlist_match:
        items = re.findall(r"\*\s*(.+)", plainlist_match.group(1))
        if items:
            value = " · ".join(_clean_wiki_value(item) for item in items)
    # Remove <ref>...</ref>
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref[^/]*?/>", "", value)
    # Remove {{...}} templates (nested - but not date templates which were handled above)
    value = re.sub(r"\{\{.*?\}\}", "", value, flags=re.DOTALL)
    # Remove [[...]] links, keep text
    value = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+?)\]\]", r"\1", value)
    # Remove '''bold''' and ''italic''
    value = re.sub(r"'''(.+?)'''", r"\1", value)
    value = re.sub(r"''(.+?)''", r"\1", value)
    # Remove HTML tags
    value = re.sub(r"<[^>]+>", "", value)
    # Remove &nbsp;
    value = value.replace("&nbsp;", " ")
    # Collapse whitespace
    value = re.sub(r"\s+", " ", value).strip()
    return value


# ═══════════════════════════════════════════════════════════════════════════
# Section extraction
# ═══════════════════════════════════════════════════════════════════════════


def _extract_section_from_text(text, title_pattern):
    """Find a section in plain text extracts by heading pattern and return its content."""
    if not text:
        return ""
    # Wikipedia plain text extracts use == Section == format
    # Match from a section heading through its content until the next heading or end
    pattern = rf"==+\s*[^=]*?(?:{title_pattern})[^=]*?==+\s*\n+(.+?)(?=\n==+\s+|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()[:3000]
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# Database cache
# ═══════════════════════════════════════════════════════════════════════════


def _ensure_cache_table():
    conn = get_db(readonly=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wikipedia_cache (
            cache_key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            fetched_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _cache_get(key):
    """Get cached Wikipedia data. Returns dict or None."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT data, fetched_at FROM wikipedia_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row["data"])
    except sqlite3.OperationalError:
        pass
    return None


def _cache_set(key, data):
    """Cache Wikipedia data."""
    _ensure_cache_table()
    conn = get_db(readonly=False)
    conn.execute(
        "INSERT OR REPLACE INTO wikipedia_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
        (key, json.dumps(data, ensure_ascii=False), time.time()),
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Translation (Google Translate — free endpoint, uses existing proxy)
# ═══════════════════════════════════════════════════════════════════════════


def _get_translator():
    """Get a GoogleTranslator instance with proxy support."""
    proxy = _get_proxy()
    proxies = {"https": proxy, "http": proxy} if proxy else None
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="en", target="zh-CN", proxies=proxies)
    except ImportError:
        return None


def _translate_text(text):
    """Translate text via deep-translator (Google Translate). Returns translated string or ''."""
    if not text or not text.strip():
        return ""
    text = text.strip()
    translator = _get_translator()
    if not translator:
        return ""
    # Chunk long texts at ~4500 chars (deep-translator limit)
    if len(text) <= 4500:
        try:
            return translator.translate(text)
        except Exception:
            return ""
    # Split at sentence boundaries for long texts
    chunks = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(current) + len(sentence) < 4500:
            current += (" " + sentence) if current else sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    # Translate chunks sequentially (deep-translator instances are not thread-safe)
    results = []
    for chunk in chunks:
        try:
            results.append(translator.translate(chunk))
        except Exception:
            results.append("")
    return "".join(results)


def _add_translations(result):
    """Add _zh translated fields. Per-field: LLM first, then deep-translator fallback."""
    if not result or result.get("lang") != "en":
        return result

    fields_to_translate = []

    if result.get("summary"):
        fields_to_translate.append(("summary", result["summary"]))
    if result.get("description"):
        fields_to_translate.append(("description", result["description"]))

    sections = result.get("sections", {})
    for key in sections:
        if sections[key]:
            fields_to_translate.append((f"sections.{key}", sections[key]))

    if not fields_to_translate:
        return result

    # Resolve translators
    try:
        from backend.services.llm_translator import translate_with_llm

        _llm_translate = translate_with_llm
    except Exception:
        _llm_translate = None

    _deep_translator = _get_translator()

    for field_key, text in fields_to_translate:
        translated = ""
        # Try LLM first
        if _llm_translate:
            try:
                translated = _llm_translate(text)
            except Exception:
                pass
        # Fallback to deep-translator
        if not translated and _deep_translator:
            try:
                translated = _deep_translator.translate(text)
            except Exception:
                pass

        if translated:
            if field_key.startswith("sections."):
                section_key = field_key[len("sections.") :]
                result.setdefault("sections_zh", {})[section_key] = translated
            else:
                result[f"{field_key}_zh"] = translated

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def get_album_wiki(album_name, artist_name):
    """Get Wikipedia enrichment for an album. Returns dict or None."""
    cache_key = f"album:{artist_name}:{album_name}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    title, lang = find_album_page(album_name, artist_name)
    if not title:
        _cache_set(cache_key, None)
        return None

    # Fetch page_data, full_text, and wikitext in parallel
    page_data = None
    full_text = ""
    wikitext = ""

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fetch_page_data, title, lang): "page_data",
            executor.submit(_fetch_full_extract, title, lang): "full_text",
            executor.submit(_fetch_wikitext, title, lang): "wikitext",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == "page_data":
                    page_data = future.result()
                elif key == "full_text":
                    full_text = future.result() or ""
                elif key == "wikitext":
                    wikitext = future.result() or ""
            except Exception:
                pass

    infobox = _parse_infobox(wikitext)
    background = _extract_section_from_text(full_text, r"background|composition|recording|writing")
    reception = _extract_section_from_text(
        full_text, r"critical\s*reception|reception|reviews|accolades"
    )
    commercial = _extract_section_from_text(
        full_text, r"commercial\s*performance|chart\s*performance|sales"
    )

    result = {
        "title": title,
        "lang": lang,
        "url": _wiki_page_url(title, lang),
        "summary": page_data.get("extract", "") if page_data else "",
        "description": page_data.get("description", "") if page_data else "",
        "thumbnail": page_data.get("thumbnail", "") if page_data else "",
        "infobox": {
            "release_date": infobox.get("released", ""),
            "recorded": infobox.get("recorded", ""),
            "studio": infobox.get("studio", ""),
            "genre": infobox.get("genre", ""),
            "length": infobox.get("length", ""),
            "label": infobox.get("label", ""),
            "producer": infobox.get("producer", ""),
            "singles": infobox.get("singles", []),
        },
        "sections": {
            "background": background,
            "reception": reception,
            "commercial": commercial,
        },
    }

    result = _add_translations(result)

    # Structured enrichment via LLM (full article -> JSON)
    if full_text:
        try:
            from backend.services.llm_translator import enrich_with_llm

            structured = enrich_with_llm(full_text, "album")
            if structured:
                result["structured"] = structured
        except Exception:
            pass

    _cache_set(cache_key, result)
    return result


def get_artist_wiki(artist_name):
    """Get Wikipedia enrichment for an artist. Returns dict or None."""
    cache_key = f"artist:{artist_name}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    title, lang = find_artist_page(artist_name)
    if not title:
        _cache_set(cache_key, None)
        return None

    page_data = None
    full_text = ""

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_fetch_page_data, title, lang): "page_data",
            executor.submit(_fetch_full_extract, title, lang): "full_text",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == "page_data":
                    page_data = future.result()
                elif key == "full_text":
                    full_text = future.result() or ""
            except Exception:
                pass

    early_life = _extract_section_from_text(
        full_text, r"early\s*life|biography|career|life\s*and\s*career"
    )
    discography_text = _extract_section_from_text(full_text, r"discography|albums|musical\s*style")

    result = {
        "title": title,
        "lang": lang,
        "url": _wiki_page_url(title, lang),
        "summary": page_data.get("extract", "") if page_data else "",
        "description": page_data.get("description", "") if page_data else "",
        "thumbnail": page_data.get("thumbnail", "") if page_data else "",
        "sections": {
            "early_life": early_life,
            "discography": discography_text,
        },
    }

    result = _add_translations(result)

    # Structured enrichment via LLM (full article -> JSON)
    if full_text:
        try:
            from backend.services.llm_translator import enrich_with_llm

            structured = enrich_with_llm(full_text, "artist")
            if structured:
                result["structured"] = structured
        except Exception:
            pass

    _cache_set(cache_key, result)
    return result


def get_track_wiki(track_name, artist_name):
    """Get Wikipedia enrichment for a track. Returns dict or None."""
    cache_key = f"track:{artist_name}:{track_name}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    for lang in ("en", "zh"):
        result = _search_wiki(f"{track_name} {artist_name} song", lang)
        if not result:
            continue

        page_data = None
        full_text = ""

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(_fetch_page_data, result, lang): "page_data",
                executor.submit(_fetch_full_extract, result, lang): "full_text",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    if key == "page_data":
                        page_data = future.result()
                    elif key == "full_text":
                        full_text = future.result() or ""
                except Exception:
                    pass

        background = _extract_section_from_text(
            full_text, r"background|composition|release|recording"
        )

        data = {
            "title": result,
            "lang": lang,
            "url": _wiki_page_url(result, lang),
            "summary": page_data.get("extract", "") if page_data else "",
            "description": page_data.get("description", "") if page_data else "",
            "sections": {"background": background},
        }
        data = _add_translations(data)
        _cache_set(cache_key, data)
        return data

    _cache_set(cache_key, None)
    return None
