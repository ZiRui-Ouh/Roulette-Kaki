"""
Mirror of webscraper service in query_agent backend for direct access and reliability.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SEARCH_AGENT_BACKEND = REPO_ROOT / "search_agent" / "backend"
scraper_file = SEARCH_AGENT_BACKEND / "services" / "webscraper.py"

spec = importlib.util.spec_from_file_location("search_agent_webscraper", str(scraper_file))
if spec and spec.loader:
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)

    build_search_intelligence = _mod.build_search_intelligence
    classify_intent = _mod.classify_intent
    detect_policy_categories = _mod.detect_policy_categories
    extract_dates = _mod.extract_dates
    extract_effective_dates = _mod.extract_effective_dates
    extract_granular_dates = _mod.extract_granular_dates
    get_priority_policy_urls = _mod.get_priority_policy_urls
    match_policy_urls = _mod.match_policy_urls
    rank_sources = _mod.rank_sources
    rewrite_query = _mod.rewrite_query
    score_applicability = _mod.score_applicability
    scrape_official_sources = _mod.scrape_official_sources
    scrape_page = _mod.scrape_page
    scrape_sources = _mod.scrape_sources
    scrape_unofficial_sources = _mod.scrape_unofficial_sources
    search_web = _mod.search_web
    understand_user_intent = _mod.understand_user_intent
    is_followup_query = _mod.is_followup_query
    extract_structured_policy_facts = _mod.extract_structured_policy_facts
    SearchAgentDebugTrace = _mod.SearchAgentDebugTrace
    COMMUNITY_SEED_PORTALS = _mod.COMMUNITY_SEED_PORTALS
