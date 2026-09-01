"""
Mirror of webscraper service in query_agent backend for direct access and reliability.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure search_agent is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SEARCH_AGENT_BACKEND = REPO_ROOT / "search_agent" / "backend"
if str(SEARCH_AGENT_BACKEND) not in sys.path:
    sys.path.insert(0, str(SEARCH_AGENT_BACKEND))

try:
    from services.webscraper import (  # type: ignore
        build_search_intelligence,
        detect_policy_categories,
        extract_dates,
        extract_effective_dates,
        get_priority_policy_urls,
        match_policy_urls,
        scrape_official_sources,
        scrape_page,
        scrape_sources,
        scrape_unofficial_sources,
        search_web,
    )
except ImportError:
    import importlib.util

    scraper_file = SEARCH_AGENT_BACKEND / "services" / "webscraper.py"
    spec = importlib.util.spec_from_file_location("search_agent_webscraper", str(scraper_file))
    if spec and spec.loader:
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        build_search_intelligence = _mod.build_search_intelligence
        detect_policy_categories = _mod.detect_policy_categories
        extract_dates = _mod.extract_dates
        extract_effective_dates = _mod.extract_effective_dates
        get_priority_policy_urls = _mod.get_priority_policy_urls
        match_policy_urls = _mod.match_policy_urls
        scrape_official_sources = _mod.scrape_official_sources
        scrape_page = _mod.scrape_page
        scrape_sources = _mod.scrape_sources
        scrape_unofficial_sources = _mod.scrape_unofficial_sources
        search_web = _mod.search_web
