"""Sitting discovery from a YouTube playlist RSS feed.

Source: `https://www.youtube.com/feeds/videos.xml?playlist_id=<ID>` —
YouTube's public Atom feed for any playlist. No API key required.

Cap: RSS returns the last 15 items. With Singapore Parliament's
one-video-per-language convention (EN/MS/ZH/TA), that dedupes to
roughly 3-4 unique sittings. Phase 5.2 can swap in YouTube Data API v3
for full pagination; the public interface of this module won't change.

English preference: sittings are conducted in English, with translation
feeds in the other languages. We keep one video per date, preferring
one whose title is >80% Latin-alphabet letters (via `unicodedata`).

Caching: fetched list is held in-process behind a TTL (default 600s,
`SITTINGS_CACHE_TTL_SECONDS`). Pagination slices the cached list.

Config:
  YOUTUBE_PLAYLIST              — playlist ID (`PL…`) or full URL. Required.
  SITTINGS_CACHE_TTL_SECONDS    — cache TTL. Default 600.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET

import httpx

log = logging.getLogger(__name__)

RSS_URL_TEMPLATE = (
    "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
)
CACHE_TTL_SECONDS = int(os.environ.get("SITTINGS_CACHE_TTL_SECONDS", "600"))
REQUEST_TIMEOUT = 15.0

# YouTube Atom feed XML namespaces.
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

_PLAYLIST_ID_RE = re.compile(r"list=([A-Za-z0-9_-]{10,})")

_cache_lock = threading.Lock()
_cache_items: list[dict] | None = None
_cache_expires_at: float = 0.0


class SittingsUnavailableError(Exception):
    """Config missing or upstream fetch failed."""


def _extract_playlist_id(raw: str) -> str:
    """Accept a raw playlist ID or a full YouTube URL, return just the ID."""
    m = _PLAYLIST_ID_RE.search(raw)
    if m:
        return m.group(1)
    return raw.strip()


def _looks_english(title: str) -> bool:
    """True iff >80% of the alphabetic characters in `title` are
    Latin-alphabet. Detects CJK / Tamil / Jawi as non-English.
    Empty / no-letter titles return False.
    """
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return False
    latin_count = sum(
        1 for c in letters if unicodedata.name(c, "").startswith("LATIN")
    )
    return latin_count / len(letters) > 0.8


def _fetch_and_parse(playlist_id: str) -> list[dict]:
    """Fetch playlist Atom feed and parse into a list of video dicts.

    Returns items in playlist order (typically most-recent first). No
    dedup here — that happens downstream.
    """
    url = RSS_URL_TEMPLATE.format(playlist_id=playlist_id)
    log.info("fetching sittings from %s", url)
    try:
        resp = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "RouletteKaki-BlogPost/0.1 (hackathon)",
                "Accept": "application/atom+xml, application/xml, text/xml",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SittingsUnavailableError(
            f"failed to fetch playlist RSS: {type(e).__name__}: {e}"
        ) from e

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise SittingsUnavailableError(f"failed to parse Atom feed: {e}") from e

    items: list[dict] = []
    for entry in root.findall("atom:entry", _NS):
        video_id_el = entry.find("yt:videoId", _NS)
        title_el = entry.find("atom:title", _NS)
        published_el = entry.find("atom:published", _NS)
        if video_id_el is None or title_el is None or published_el is None:
            continue
        video_id = (video_id_el.text or "").strip()
        title = (title_el.text or "").strip()
        published = (published_el.text or "").strip()
        if not video_id or not title or not published:
            continue
        items.append(
            {
                "video_id": video_id,
                "title": title,
                "date": published[:10],
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return items


def _dedupe_by_date(items: list[dict]) -> list[dict]:
    """Keep one item per date. First seen wins; a later English-titled
    item replaces a non-English pick for the same date. Result is
    sorted date-desc.
    """
    picked: dict[str, dict] = {}
    for item in items:
        date = item["date"]
        if date not in picked:
            picked[date] = item
            continue
        curr = picked[date]
        if _looks_english(item["title"]) and not _looks_english(curr["title"]):
            picked[date] = item
    return sorted(picked.values(), key=lambda x: x["date"], reverse=True)


def _get_all_sittings() -> list[dict]:
    """Cached fetch + dedup. Returns unique sittings sorted date-desc.

    Raises SittingsUnavailableError if YOUTUBE_PLAYLIST is unset or the
    upstream fetch fails.
    """
    global _cache_items, _cache_expires_at
    now = time.monotonic()

    with _cache_lock:
        if _cache_items is not None and now < _cache_expires_at:
            return _cache_items

    raw = os.environ.get("YOUTUBE_PLAYLIST")
    if not raw:
        raise SittingsUnavailableError(
            "YOUTUBE_PLAYLIST env var is not set. Set it to a playlist ID "
            "(e.g. PLetiU3qG4uSrSjL6UlfVsgR89lxBzP5D1) or a playlist URL."
        )
    playlist_id = _extract_playlist_id(raw)

    videos = _fetch_and_parse(playlist_id)
    unique = _dedupe_by_date(videos)

    with _cache_lock:
        _cache_items = unique
        _cache_expires_at = now + CACHE_TTL_SECONDS
    return unique


def find_sitting(date: str) -> dict | None:
    """Look up a single sitting by ISO date. Returns
    {date, title, youtube_url} or None if not in the current playlist
    feed. Silently returns None (never raises) so the digest agent can
    call this even when YOUTUBE_PLAYLIST is unset.
    """
    try:
        all_ = _get_all_sittings()
    except SittingsUnavailableError:
        return None
    for s in all_:
        if s["date"] == date:
            return {
                "date": s["date"],
                "title": s["title"],
                "youtube_url": s["youtube_url"],
            }
    return None


def list_sittings(limit: int = 5, offset: int = 0) -> dict:
    """Paginated sitting list.

    Returns {sittings, total, has_more}. `sittings` items expose only
    the fields the frontend needs (date, title, youtube_url) — video_id
    is stripped.
    """
    all_ = _get_all_sittings()
    total = len(all_)
    slice_ = all_[offset : offset + limit]
    return {
        "sittings": [
            {
                "date": s["date"],
                "title": s["title"],
                "youtube_url": s["youtube_url"],
            }
            for s in slice_
        ],
        "total": total,
        "has_more": offset + limit < total,
    }


def _reset_cache() -> None:
    """Test-only: clear the cache."""
    global _cache_items, _cache_expires_at
    with _cache_lock:
        _cache_items = None
        _cache_expires_at = 0.0
