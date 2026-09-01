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
    # SPRS report type slug ("oral-answer", "written-answer-na", "bill",
    # "motion", etc.). Populated by scraper_sprs; empty for fixtures.
    # Used by the digest agent to compute category_breakdown server-side
    # (Nova Lite can't count reliably at scale).
    report_type: str = ""


def list_topics(date: str) -> list[TopicMeta]:
    """Topics debated on `date`, or [] if no sitting was held.

    Each returned topic has a stable `topic_id` usable as an S3 cache key
    suffix (Phase 4 lazy report fetch will key S3 objects by this).
    """
    if SCRAPER_MODE == "fixture":
        return _list_topics_from_fixture(date)
    if SCRAPER_MODE == "sprs":
        from services import scraper_sprs  # local import — httpx dep only when needed

        return [TopicMeta(**item) for item in scraper_sprs.list_topics(date)]
    raise ValueError(
        f"unknown SCRAPER_MODE={SCRAPER_MODE!r} — expected 'fixture' or 'sprs'"
    )


def _list_topics_from_fixture(date: str) -> list[TopicMeta]:
    path = FIXTURES_DIR / f"topics_{date}.json"
    if not path.exists():
        return []
    with path.open() as f:
        raw = json.load(f)
    return [TopicMeta(**item) for item in raw]


def fetch_report(topic: TopicMeta) -> bytes:
    """Fetch raw report bytes for a topic. Used by the research agent
    (Phase 4) — reports are scraped lazily on first user mention, not
    up-front at digest time.

    SCRAPER_MODE=fixture still raises — fixtures only include metadata,
    not report bytes. Set SCRAPER_MODE=sprs to actually fetch.
    """
    if SCRAPER_MODE == "sprs":
        from services import scraper_sprs  # local import

        return scraper_sprs.fetch_report(topic)
    if SCRAPER_MODE == "fixture":
        raise NotImplementedError(
            "SCRAPER_MODE=fixture does not include report bodies. "
            "Set SCRAPER_MODE=sprs to fetch transcripts from SPRS."
        )
    raise ValueError(
        f"unknown SCRAPER_MODE={SCRAPER_MODE!r} — expected 'fixture' or 'sprs'"
    )
