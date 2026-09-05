"""
Mirror of webscraper service in query_agent backend for direct access and reliability.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SEARCH_AGENT_BACKEND = REPO_ROOT / "search_agent" / "backend"
scraper_file = SEARCH_AGENT_BACKEND / "services" / "webscraper.py"

spec = importlib.util.spec_from_file_location("search_agent_webscraper", str(scraper_file))
if spec and spec.loader:
    search_backend_str = str(SEARCH_AGENT_BACKEND)
    added = False
    if search_backend_str not in sys.path:
        sys.path.insert(0, search_backend_str)
        added = True
    try:
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        for attr in dir(_mod):
            if not attr.startswith("__"):
                globals()[attr] = getattr(_mod, attr)
    finally:
        if added and search_backend_str in sys.path:
            sys.path.remove(search_backend_str)
