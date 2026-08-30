"""Digest agent — stub.

Runs once per sitting date. Cached in DynamoDB DebateDigests. Uses Nova
Lite. Real implementation lands in Phase 3.

See AGENTS.md for the full contract.
"""

from __future__ import annotations

from services import storage  # noqa: F401 — used in Phase 3
from services.scraper import list_topics  # noqa: F401 — used in Phase 3


def run_digest(date: str) -> dict:  # noqa: ARG001
    """Return the digest for `date`, running the agent on cache miss.

    Phase 2: raise NotImplementedError immediately. The main.py handler
    catches this and returns a stub payload, keeping the local server
    functional with no AWS calls.

    Phase 3 will replace this with: check `storage.get_digest(date)` →
    cache hit returns it; miss runs `scraper.list_topics(date)` +
    `bedrock.summarize(...)` and writes the result via
    `storage.put_digest(...)`.
    """
    raise NotImplementedError(
        "Phase 3 — scrape + summarize + cache the digest for this date"
    )


def _summarize_topics_prompt(date: str, topics: list) -> str:  # noqa: ARG001
    """Prompt template for the single Nova Lite summarization call.
    Phase 3 will implement.
    """
    raise NotImplementedError("Phase 3")
