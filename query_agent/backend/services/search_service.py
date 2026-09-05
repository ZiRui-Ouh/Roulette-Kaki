"""
Search Agent Integration Service for Query Agent.

Connects the Query Agent to the Search Agent to retrieve updated web data,
official government facts, and unofficial community context.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SEARCH_AGENT_BACKEND = REPO_ROOT / "search_agent" / "backend"


def _load_search_module():
    """Dynamically load search agent module to avoid collision with query agent's agents package."""
    search_file = SEARCH_AGENT_BACKEND / "agents" / "search.py"
    if not search_file.exists():
        raise FileNotFoundError(f"Search agent file not found at {search_file}")

    # Ensure search_agent/backend is temporarily in sys.path so search.py can import services.bedrock / webscraper
    search_backend_str = str(SEARCH_AGENT_BACKEND)
    added_to_path = False
    if search_backend_str not in sys.path:
        sys.path.insert(0, search_backend_str)
        added_to_path = True

    try:
        spec = importlib.util.spec_from_file_location("search_agent_search", str(search_file))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {search_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["search_agent_search"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if added_to_path and search_backend_str in sys.path:
            sys.path.remove(search_backend_str)


_search_module = None


def get_search_module():
    global _search_module
    if _search_module is None:
        _search_module = _load_search_module()
    return _search_module


def fetch_from_search_agent(
    question: str,
    urls: list[str] | None = None,
    provided_sources: list[dict] | None = None,
    conversation_context: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Invoke the Search Agent to gather official and unofficial data.

    Returns:
        dict with keys:
            - official_sources: list[dict]
            - unofficial_sources: list[dict]
            - current_applicable_source: dict | None
            - conflicting_sources: list[dict]
            - official_policy_facts: list[dict]
            - community_insights: list[dict]
            - query_intent: str
            - rewritten_query: str
            - search_summary: str
    """
    # Check if an external HTTP search agent service is configured
    search_agent_url = os.environ.get("SEARCH_AGENT_URL")
    if search_agent_url:
        try:
            import requests

            resp = requests.post(
                f"{search_agent_url.rstrip('/')}/search",
                json={
                    "q": question,
                    "urls": urls or [],
                    "conversation_context": conversation_context or [],
                },
                timeout=25,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "search_summary" in data:
                return data
            return {
                "official_sources": [],
                "unofficial_sources": [],
                "search_summary": data.get("answer", str(data)),
            }
        except Exception as exc:
            log.warning("HTTP call to Search Agent failed (%s), falling back to local module.", exc)

    # In-process call to Search Agent
    try:
        search_mod = get_search_module()
        return search_mod.gather_and_search(
            question=question,
            urls=urls,
            provided_sources=provided_sources,
            conversation_context=conversation_context,
        )
    except Exception as exc:
        log.error("Failed to invoke Search Agent: %s", exc)
        return {
            "official_sources": [],
            "unofficial_sources": [],
            "search_summary": f"Search agent encountered an issue: {exc}",
        }
