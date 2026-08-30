"""SPRS scraper — stub.

Interface only for Phase 2. Real implementation lands in Phase 3, where
we sniff the SPRS JSON API from browser DevTools and hit it with `httpx`.
Playwright is a fallback we only add if the plain-HTTP approach fails.

SPRS site: https://sprs.parl.gov.sg/search/#/home
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReportFormat = Literal["pdf", "html"]


@dataclass
class TopicMeta:
    topic_id: str
    title: str
    speakers: list[str]
    source_url: str
    format: ReportFormat


def list_topics(date: str) -> list[TopicMeta]:
    """Return topics debated on `date`. Phase 3 will implement.

    Contract:
    - Return [] if no sitting was held on that date.
    - Each returned topic must have a stable `topic_id` usable as an S3
      cache key suffix.
    """
    raise NotImplementedError("Phase 3 — see AGENTS.md digest agent")


def fetch_report(topic: TopicMeta) -> bytes:
    """Fetch the raw report bytes for a topic. Phase 3 will implement."""
    raise NotImplementedError("Phase 3 — see AGENTS.md digest agent")
