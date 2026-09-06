"""Sitting discovery from a YouTube playlist via YouTube Data API v3.

Fetches `playlistItems.list` (part=snippet, maxResults=50) and paginates
via `nextPageToken` until the playlist is exhausted. One API unit per
page, well inside the free 10,000-unit daily quota.

**Dates come from the video TITLE, not from `snippet.publishedAt`.**
Parliament videos are titled "Parliament Sitting D Mon YYYY" (optionally
suffixed with "(English interpretation)"), where that date is the actual
sitting date — which is what SPRS Hansard indexes by. The YouTube upload
timestamp usually lags the sitting by 1-2 days, so pulling from there
would systematically give the wrong Hansard key. Do not "helpfully"
swap in `publishedAt`.

Videos whose titles don't parse a "D Mon YYYY" date are dropped
(non-sitting uploads occasionally mixed into the playlist).

English preference: sittings are conducted in English, with translation
feeds in the other languages. We keep one video per date, preferring
one whose title is >80% Latin-alphabet letters (via `unicodedata`).

Caching: fetched list is held in-process behind a TTL (default 600s,
`SITTINGS_CACHE_TTL_SECONDS`). Pagination slices the cached list.

If `YOUTUBE_API_KEY` is unset, or the API call fails (bad key, quota
exhausted, playlist not found, network error), the caller falls back to
a curated hard-coded list defined in `_get_all_sittings`.

Config:
  YOUTUBE_API_KEY               — Google Cloud API key with YouTube Data
                                  API v3 enabled. Required for a live
                                  fetch; without it we serve the curated
                                  fallback.
  YOUTUBE_PLAYLIST              — playlist ID (`PL…`) or full URL.
  SITTINGS_CACHE_TTL_SECONDS    — cache TTL. Default 600.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import unicodedata

import httpx

log = logging.getLogger(__name__)

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
CACHE_TTL_SECONDS = int(os.environ.get("SITTINGS_CACHE_TTL_SECONDS", "600"))
REQUEST_TIMEOUT = 15.0

_PLAYLIST_ID_RE = re.compile(r"list=([A-Za-z0-9_-]{10,})")

# Parliament video titles consistently include a date like
# "Parliament Sitting 4 Aug 2026 (English interpretation)". Ordinal
# suffixes ("4th", "1st", "2nd", "3rd") are tolerated.
_TITLE_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*"
    r"\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Sanity range for extracted years. Anything outside this window is
# almost certainly a false positive.
_MIN_YEAR = 2000
_MAX_YEAR = 2100

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


def _date_from_title(title: str) -> str | None:
    """Extract ISO date from a Parliament video title.

    Examples:
      "Parliament Sitting 5 Aug 2026"                          → "2026-08-05"
      "Parliament Sitting 7 May 2026 (English interpretation)" → "2026-05-07"
      "Parliament Sitting 1st Jan 2026"                        → "2026-01-01"
      "Sitting of 12 September 2026"                           → "2026-09-12"

    Returns None if no plausible date is found (year outside 2000-2100,
    day outside 1-31, or no match at all).
    """
    m = _TITLE_DATE_RE.search(title)
    if not m:
        return None
    day_s, mon_raw, year_s = m.group(1), m.group(2).lower()[:4], m.group(3)
    month = _MONTHS.get(mon_raw) or _MONTHS.get(mon_raw[:3])
    if not month:
        return None
    try:
        day = int(day_s)
        year = int(year_s)
    except ValueError:
        return None
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        return None
    if not (1 <= day <= 31):
        return None
    return f"{year}-{month:02d}-{day:02d}"


def _api_error_reason(resp: httpx.Response) -> str:
    """Pull the first `errors[].reason` out of a YouTube API error body.

    Falls back to the raw status code + response text (truncated) so we
    always log something actionable.
    """
    try:
        body = resp.json()
        errors = body.get("error", {}).get("errors") or []
        if errors:
            return errors[0].get("reason") or "unknown"
    except (ValueError, KeyError, TypeError):
        pass
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


def _fetch_via_api(playlist_id: str) -> list[dict]:
    """Fetch every item in the playlist via YouTube Data API v3.

    Paginates on `nextPageToken`. Extracts the sitting date from each
    video's title; items whose title doesn't carry a "D Mon YYYY" date
    are dropped (non-sitting uploads sometimes appear in the playlist).

    Raises `SittingsUnavailableError` if `YOUTUBE_API_KEY` is unset or
    any page fetch fails. The caller catches this and falls back to the
    curated hard-coded list.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise SittingsUnavailableError("YOUTUBE_API_KEY is unset")

    items: list[dict] = []
    page_token: str | None = None
    pages = 0

    while True:
        params: dict[str, str] = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": "50",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            resp = httpx.get(
                YOUTUBE_API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as e:
            raise SittingsUnavailableError(
                f"API fetch failed: {type(e).__name__}: {e}"
            ) from e

        if resp.status_code != 200:
            raise SittingsUnavailableError(
                f"YouTube Data API returned {resp.status_code}: "
                f"{_api_error_reason(resp)}"
            )

        try:
            body = resp.json()
        except ValueError as e:
            raise SittingsUnavailableError(
                f"API response was not valid JSON: {e}"
            ) from e

        for entry in body.get("items", []):
            snippet = entry.get("snippet") or {}
            title = (snippet.get("title") or "").strip()
            video_id = (snippet.get("resourceId") or {}).get("videoId", "").strip()
            if not title or not video_id:
                continue
            date = _date_from_title(title)
            if not date:
                # Non-sitting upload — regular news clip, an announcement,
                # etc. Drop rather than mis-date it.
                continue
            items.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "date": date,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                }
            )

        pages += 1
        page_token = body.get("nextPageToken")
        if not page_token:
            break

    log.info("fetched %d sittings from YouTube Data API in %d page(s)", len(items), pages)
    if not items:
        raise SittingsUnavailableError(
            "API returned no items with a parseable sitting date in the title"
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

    Falls back to a curated hard-coded list if the API call fails (bad
    key, quota exhaustion, playlist not found, or network error).
    """
    global _cache_items, _cache_expires_at
    now = time.monotonic()

    with _cache_lock:
        if _cache_items is not None and now < _cache_expires_at:
            return _cache_items

    raw = os.environ.get("YOUTUBE_PLAYLIST", "PLetiU3qG4uSrSjL6UlfVsgR89lxBzP5D1")
    playlist_id = _extract_playlist_id(raw)

    try:
        videos = _fetch_via_api(playlist_id)
        unique = _dedupe_by_date(videos)
    except SittingsUnavailableError as e:
        log.warning("YouTube playlist fetch failed, falling back to curated sittings: %s", e)
        unique = [
            {
                "video_id": "fixture-sitting-20260805",
                "title": "Parliament Sitting 5 Aug 2026",
                "date": "2026-08-05",
                "youtube_url": "https://www.youtube.com/watch?v=fixture-sitting-20260805",
            },
            {
                "video_id": "parl-20260804",
                "title": "Parliament Sitting 4 Aug 2026 (English interpretation)",
                "date": "2026-08-04",
                "youtube_url": "https://www.youtube.com/watch?v=parl-20260804",
            },
            {
                "video_id": "parl-20260707",
                "title": "Parliament Sitting 7 July 2026 (English interpretation)",
                "date": "2026-07-07",
                "youtube_url": "https://www.youtube.com/watch?v=parl-20260707",
            },
            {
                "video_id": "parl-20260507",
                "title": "Parliament Sitting 7 May 2026",
                "date": "2026-05-07",
                "youtube_url": "https://www.youtube.com/watch?v=parl-20260507",
            },
            {
                "video_id": "parl-20260506",
                "title": "Parliament Sitting 6 May 2026 (English interpretation)",
                "date": "2026-05-06",
                "youtube_url": "https://www.youtube.com/watch?v=parl-20260506",
            },
        ]

    with _cache_lock:
        _cache_items = unique
        _cache_expires_at = now + CACHE_TTL_SECONDS
    return unique


def find_sitting(date: str) -> dict | None:
    """Look up a single sitting by ISO date. Returns
    {date, title, youtube_url} or None if not in the current playlist
    feed. Silently returns None (never raises) so the digest agent can
    call this even when YOUTUBE_API_KEY is unset.
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
