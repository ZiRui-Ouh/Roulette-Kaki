"""SPRS scraper.

Phase 3 is fixture-backed: `list_topics` reads
`backend/fixtures/topics_{date}.json` and returns the parsed
`TopicMeta` entries. Real SPRS integration is Phase 3.5 — the recon on
2026-08-30 confirmed SPRS is an Angular SPA with no discoverable REST
endpoints, so the real scraper will need an instrumented Playwright run
to capture the actual API surface first.

`SCRAPER_MODE` env var (default `fixture`, alternative `sprs`) selects
the backend. Higher layers only see the `list_topics` / `fetch_report`
signatures.

SPRS site: https://sprs.parl.gov.sg/search/#/home
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ReportFormat = Literal["pdf", "html"]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SCRAPER_MODE = os.environ.get("SCRAPER_MODE", "fixture")


@dataclass
class TopicMeta:
    topic_id: str
    title: str
    speakers: list[str]
    source_url: str
    format: ReportFormat


def list_topics(date: str) -> list[TopicMeta]:
    """Topics debated on `date`, or [] if no sitting was held.

    Each returned topic has a stable `topic_id` usable as an S3 cache key
    suffix (Phase 4 lazy report fetch will key S3 objects by this).
    """
    if SCRAPER_MODE == "fixture":
        return _list_topics_from_fixture(date)
    raise NotImplementedError(
        f"SCRAPER_MODE={SCRAPER_MODE!r} not implemented — Phase 3.5 lands the real SPRS backend"
    )


def _list_topics_from_fixture(date: str) -> list[TopicMeta]:
    path = FIXTURES_DIR / f"topics_{date}.json"
    if not path.exists():
        return []
    with path.open() as f:
        raw = json.load(f)
    return [TopicMeta(**item) for item in raw]


def fetch_report(topic: TopicMeta) -> bytes:
    """Fetch raw report bytes for a topic. Phase 4 (research agent) will
    implement — reports are scraped lazily on first user mention, not
    up-front at digest time.
    """
    raise NotImplementedError("Phase 4 — research agent scrapes on demand")
