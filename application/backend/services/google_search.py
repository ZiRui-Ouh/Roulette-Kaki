"""
google_search.py - Dynamic web discovery using Google Custom Search JSON API.

Provides structured URL discovery across official Singapore government domains
and community discussion forums.
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

def google_search(
    query: str,
    domains: Optional[list[str]] = None,
    num: int = 5,
    timeout: float = 4.0
) -> list[dict]:
    """
    Execute a query against Google Custom Search API.

    Args:
        query: Search string.
        domains: Optional list of domains to filter by (e.g., ['lta.gov.sg', 'onemotoring.lta.gov.sg']).
        num: Number of results to return (max 10).
        timeout: Network timeout in seconds.

    Returns:
        List of dicts: [{'title': str, 'url': str, 'snippet': str, 'domain': str}]
        Empty list if API key is not configured, rate limited, or on error.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        logger.info("[GOOGLE SEARCH] GOOGLE_API_KEY or GOOGLE_CSE_ID not set; skipping Google Search API.")
        return []

    # Build search query with site filters if domains are specified
    search_q = query
    if domains:
        site_filter = " OR ".join([f"site:{d}" for d in domains])
        search_q = f"({site_filter}) {query}"

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": search_q,
        "num": min(max(num, 1), 10),
    }

    try:
        logger.info(f"[GOOGLE SEARCH] Querying Google CSE: '{search_q[:80]}' (num={params['num']})")
        resp = requests.get(GOOGLE_SEARCH_ENDPOINT, params=params, timeout=timeout)

        if resp.status_code != 200:
            logger.warning(f"[GOOGLE SEARCH] API returned status {resp.status_code}: {resp.text[:150]}")
            return []

        data = resp.json()
        items = data.get("items", [])
        results = []

        for item in items:
            link = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            # Extract domain
            domain = ""
            try:
                from urllib.parse import urlparse
                domain = urlparse(link).netloc.lower()
            except Exception:
                pass

            results.append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "domain": domain
            })

        logger.info(f"[GOOGLE SEARCH] Discovered {len(results)} candidate URLs for '{query[:50]}'")
        return results

    except requests.exceptions.Timeout:
        logger.warning(f"[GOOGLE SEARCH] Timed out after {timeout}s for '{query[:50]}'")
        return []
    except Exception as e:
        logger.warning(f"[GOOGLE SEARCH] Error querying Google CSE: {e}")
        return []
