"""Real SPRS scraper implementation (Phase 3.5b).

API surface, discovered by the Playwright recon on 2026-08-30:

    POST https://sprs.parl.gov.sg/search/searchResult
        body: JSON with fromday/frommonth/fromyear, today/tomonth/toyear,
              dateRange="custom", startIndex, endIndex, and a bunch of
              default-empty filters (portfolio, mpName, ministrySelected).
        returns: JSON array of report dicts. Each has reportId (opaque
                 string, ends with '#'), title, reportType (oral-answer,
                 written-answer-na, motion, bill, ...), sittingDate, sno,
                 and maxResult (total count for the query, echoed on
                 every item — used for pagination).

    POST https://sprs.parl.gov.sg/search/getHansardTopic
        body: {"id": "<reportId without trailing '#'>"}
        returns: {"resultHTML": {"title", "content" (HTML string with the
                 full transcript), "mpNames" (comma-separated), ...}}

No auth, no CSRF token. Site is behind Imperva/Incapsula — a browser-like
User-Agent is enough for now. If that stops working we escalate to
Playwright fallback, but Phase 4 does not need it yet.

Rate limit: 0.5s between calls by default (SPRS_REQUEST_DELAY env var).
Retry once on 429 / 5xx with a 2s backoff.

Callers reach this module only via services/scraper.py's dispatch on
SCRAPER_MODE=sprs. Do not import it directly.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from html import escape

import httpx

BASE = "https://sprs.parl.gov.sg/search"
SEARCH_ENDPOINT = f"{BASE}/searchResult"
TOPIC_ENDPOINT = f"{BASE}/getHansardTopic"

# PAGE_SIZE is the endIndex delta we request. SPRS may cap page size
# server-side (recon on 2026-08-30 saw the Angular app requesting only
# 20 at a time, hinting at a small server cap). Pagination advances
# by the ACTUAL number of items returned, not by PAGE_SIZE — so this
# value doesn't affect correctness, only round-trip count if SPRS
# actually honors it.
PAGE_SIZE = 100
REQUEST_DELAY = float(os.environ.get("SPRS_REQUEST_DELAY", "0.5"))
REQUEST_TIMEOUT = 30.0

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 "
    "RouletteKaki-BlogPost/0.1 (hackathon)"
)

log = logging.getLogger(__name__)

_client_singleton: httpx.Client | None = None
_client_lock = threading.Lock()
_last_call_ts = 0.0


def _client() -> httpx.Client:
    global _client_singleton
    if _client_singleton is None:
        with _client_lock:
            if _client_singleton is None:
                _client_singleton = httpx.Client(
                    timeout=REQUEST_TIMEOUT,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json, text/plain, */*",
                        "Content-Type": "application/json",
                        "Origin": "https://sprs.parl.gov.sg",
                        "Referer": "https://sprs.parl.gov.sg/search/",
                    },
                )
    return _client_singleton


def _throttle() -> None:
    """Sleep so we honor SPRS_REQUEST_DELAY between calls."""
    global _last_call_ts
    now = time.monotonic()
    wait = REQUEST_DELAY - (now - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.monotonic()


def _post_json(url: str, payload: dict) -> httpx.Response:
    """POST with one retry on 429 / 5xx."""
    for attempt in (1, 2):
        _throttle()
        resp = _client().post(url, json=payload)
        if resp.status_code < 500 and resp.status_code != 429:
            return resp
        if attempt == 1:
            log.warning(
                "SPRS %s returned %s — retrying once after 2s",
                url,
                resp.status_code,
            )
            time.sleep(2.0)
    return resp  # returns the failed second-attempt response so caller sees .status_code


def _search_payload(date: str, start: int, end: int) -> dict:
    y, m, d = date.split("-")
    return {
        "keyword": "",
        "fromday": d,
        "frommonth": m,
        "fromyear": y,
        "today": d,
        "tomonth": m,
        "toyear": y,
        "dateRange": "custom",
        "reportContent": "with all the words",
        "parliamentNo": "",
        "selectedSort": "date_dt desc",
        "portfolio": [],
        "mpName": "",
        "rsSelected": "",
        "lang": "",
        "startIndex": str(start),
        "endIndex": str(end),
        "titleChecked": "false",
        "footNoteChecked": "false",
        "ministrySelected": [],
    }


def list_topics(date: str) -> list[dict]:
    """Return topic metadata for `date`. Paginates through /searchResult
    until all reports for that date are collected.

    Returns list of dicts shaped for TopicMeta construction. Callers
    (services/scraper.py) wrap these into TopicMeta instances.

    Empty list means no sitting on that date (SPRS returns [] for dates
    without a sitting).
    """
    all_items: list[dict] = []
    max_result = -1
    start = 0

    while True:
        end = start + PAGE_SIZE - 1
        log.info("SPRS searchResult page: start=%d end=%d date=%s", start, end, date)
        resp = _post_json(SEARCH_ENDPOINT, _search_payload(date, start, end))
        resp.raise_for_status()
        page = resp.json()
        if not isinstance(page, list) or not page:
            break

        for item in page:
            all_items.append(_normalize_topic(item, date))

        # Every item echoes maxResult — grab it from the first item.
        if max_result < 0:
            try:
                max_result = int(page[0].get("maxResult") or 0)
            except (TypeError, ValueError):
                max_result = 0

        if max_result <= 0 or len(all_items) >= max_result:
            break

        # Advance by actual response size, not by PAGE_SIZE — SPRS may
        # cap the page server-side, and stepping by PAGE_SIZE would skip
        # items between actual-received-count and PAGE_SIZE.
        start += len(page)

    # Dedup by topic_id. SPRS pagination has been observed to return
    # overlapping pages, which downstream causes React key collisions
    # on the frontend (list stops updating on filter input).
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in all_items:
        tid = item.get("topic_id") or ""
        if not tid or tid in seen:
            continue
        seen.add(tid)
        deduped.append(item)
    if len(deduped) != len(all_items):
        log.warning(
            "SPRS list_topics(%s): dropped %d duplicate topic_id(s)",
            date,
            len(all_items) - len(deduped),
        )

    log.info("SPRS list_topics(%s) → %d topics", date, len(deduped))
    return deduped


def _normalize_topic(raw: dict, date: str) -> dict:  # noqa: ARG001 — date reserved for future variants
    """Shape a /searchResult item into TopicMeta-compatible dict.

    `speakers` is intentionally empty — mpNames is null in search results.
    The research agent fetches speakers per topic during chat (Phase 4).

    `source_url` points at SPRS's deep-linkable topic route,
    `#/sprs3topic?reportid=<id>`. This is the correct SPA route for a
    single topic — it reads `reportid` from URL params on fresh load
    (unlike the post-navigation URL seen in the recon capture, which
    dropped the query because state was already in memory).

    `report_type` echoes SPRS's `reportType` slug (`"oral-answer"`,
    `"written-answer-na"`, `"bill"`, `"motion"`, ...). The digest agent
    uses this to compute `category_breakdown` server-side (Nova Lite
    counts unreliably at 100+ topics).
    """
    report_id = (raw.get("reportId") or "").rstrip("#")
    return {
        "topic_id": report_id,
        "title": raw.get("title") or "(untitled)",
        "speakers": [],
        "source_url": f"https://sprs.parl.gov.sg/search/#/sprs3topic?reportid={report_id}",
        "format": "html",
        "report_type": (raw.get("reportType") or "").strip(),
    }


def fetch_report(topic: dict) -> bytes:
    """Fetch the transcript for one topic. Returns UTF-8 HTML bytes ready
    to attach as a Nova `document` block (format='html').

    `topic` may be a TopicMeta dataclass instance or a dict with a
    `topic_id` key. We only use `topic_id`.
    """
    topic_id = getattr(topic, "topic_id", None) or topic.get("topic_id")
    if not topic_id:
        raise ValueError("fetch_report: topic missing topic_id")

    log.info("SPRS getHansardTopic id=%s", topic_id)
    resp = _post_json(TOPIC_ENDPOINT, {"id": topic_id})
    resp.raise_for_status()
    payload = resp.json()

    result_html = payload.get("resultHTML") or {}
    title = result_html.get("title") or "(untitled)"
    content = result_html.get("content") or ""
    mp_names = result_html.get("mpNames") or ""
    sitting_date = result_html.get("sittingDate") or ""

    # Wrap the raw HTML in a minimal envelope so Nova can see the title
    # and speakers as context.
    doc = (
        f"<!doctype html><html><head>"
        f"<meta charset='utf-8'><title>{escape(title)}</title></head><body>"
        f"<h1>{escape(title)}</h1>"
        f"<p><em>Sitting:</em> {escape(sitting_date)}<br>"
        f"<em>Speakers:</em> {escape(mp_names)}</p>"
        f"{content}"
        f"</body></html>"
    )
    return doc.encode("utf-8")
