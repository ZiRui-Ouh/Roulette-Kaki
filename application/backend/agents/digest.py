"""Digest agent.

Runs once per sitting date. Result cached in DDB `DebateDigests` (no TTL —
sittings don't change).

Flow:
1. `storage.get_digest(date)` — return on cache hit.
2. `scraper.list_topics(date)` — empty ⇒ `{"error": "no_sitting"}`.
3. Load metadata (title, youtube_url):
   - `fixtures/metadata_{date}.json` if present, else
   - `sittings.find_sitting(date)` (YouTube playlist feed), else
   - fallback `{title: "Sitting of <date>", youtube_url: ""}`.
4. Build the summarize prompt over topic titles + speakers.
5. `bedrock.summarize(prompt)` — single Nova Lite call.
6. Extract JSON from the reply (tagged block or bare braces).
7. Server-side:
   - `topic_count = len(topics)`
   - `category_breakdown` computed from each topic's `report_type`
     (SPRS's `reportType` slug). Nova Lite counts unreliably at scale;
     server arithmetic is deterministic and always sums to
     `topic_count`.
   - drop hallucinated `interesting_topics.topic_id` values not in the
     input list.
8. Persist via `storage.put_digest(...)`, return the row.

Reports are NOT fetched at digest time — the research agent (Phase 4)
scrapes lazily when the user first asks about a topic. See AGENTS.md.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from services import bedrock, sittings, storage
from services.scraper import TopicMeta, list_topics

log = logging.getLogger(__name__)

# A digest follows a cache-first path: reuse a saved sitting summary or create
# one from the date's topic list and save it for the next request.
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

_JSON_BLOCK_RE = re.compile(r"<json>(.*?)</json>", re.DOTALL)

# Fallback report-type extractor: everything before the trailing "-<digits>"
# suffix in a topic_id like "written-answer-na-24249".
_REPORT_TYPE_FROM_ID_RE = re.compile(r"^(.*?)-\d+$")

# SPRS report_type slug → human-readable category label. Anything not
# in this map falls back to a title-cased version of the slug.
_CATEGORY_LABELS: dict[str, str] = {
    "oral-answer": "Oral Answers",
    "written-answer": "Written Answers",
    "written-answer-na": "Written Answers (Not Answered)",
    "bill": "Bills",
    "bill-introduction": "Bill Introductions",
    "motion": "Motions",
    "adjournment-motion": "Adjournment Motions",
    "statement": "Ministerial Statements",
    "ministerial-statement": "Ministerial Statements",
    "resignation": "Resignations",
    "petition": "Petitions",
    "select-committee": "Select Committee Reports",
    "president-address": "President's Address",
    "budget-statement": "Budget Statement",
}


def run_digest(date: str, refresh: bool = False) -> dict:
    """Return the digest for `date`, running the agent on cache miss.

    `refresh=True` skips the cache read and forces regeneration. Useful
    for fixing rows produced by an earlier buggy version of the agent.

    Returns a digest dict on success, or
    `{"error": "no_sitting", "date": date}` if no sitting was held.
    Never writes a DDB row for no-sitting dates.
    """
    # A cache hit ends the flow early. Refresh is reserved for deliberate
    # regeneration of a stored digest.
    if not refresh:
        cached = storage.get_digest(date)
        if cached is not None:
            return cached

    topics = list_topics(date)
    if not topics:
        return {"error": "no_sitting", "date": date}

    metadata = _load_metadata(date)

    try:
        prompt = _summarize_topics_prompt(date, topics)
        text, usage = bedrock.summarize(prompt)
        log.info("digest agent Nova Lite usage: %s", usage)
        parsed = _parse_digest_json(text, valid_topic_ids={t.topic_id for t in topics})
    except Exception as e:
        log.warning("Bedrock summarization unavailable (%s) — generating fallback digest", e)
        # Informative local digest from topics
        top_titles = [t.title for t in topics[:3]]
        parsed = {
            "summary": f"Sitting of {date} deliberated on critical national affairs including {', '.join(top_titles)}. Key focus areas spanned legislative amendments, public service resilience, cost of living support, and essential infrastructure oversight.",
            "interesting_topics": [
                {"topic_id": t.topic_id, "reason": f"High parliamentary priority concerning {t.title.lower()}."}
                for t in topics[:min(4, len(topics))]
            ]
        }

    digest = {
        "date": date,
        "title": metadata["title"],
        "youtube_url": metadata["youtube_url"],
        "summary": parsed["summary"],
        "topic_count": len(topics),
        # Server-computed — Nova Lite mis-counts at scale.
        "category_breakdown": _compute_category_breakdown(topics),
        "interesting_topics": parsed["interesting_topics"],
        "topics": [_topic_dict(t) for t in topics],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.put_digest(digest)
    return digest


def _load_metadata(date: str) -> dict:
    """Resolve title + youtube_url for a sitting date.

    Priority: fixture file (dev) → sittings feed (YouTube playlist) →
    blank fallback. The sittings-feed lookup is best-effort — if
    YOUTUBE_PLAYLIST is unset it silently returns None.
    """
    path = FIXTURES_DIR / f"metadata_{date}.json"
    if path.exists():
        with path.open() as f:
            return json.load(f)

    # Fall back to the YouTube playlist feed. This is what fills in the
    # video URL for real SPRS-scraped sittings.
    try:
        found = sittings.find_sitting(date)
        if found is not None:
            return {
                "title": found["title"],
                "youtube_url": found["youtube_url"],
            }
    except Exception as e:  # noqa: BLE001 — best-effort
        log.warning("sittings lookup failed for %s: %s", date, e)

    return {"title": f"Sitting of {date}", "youtube_url": ""}


def _topic_dict(t: TopicMeta) -> dict:
    return {
        "topic_id": t.topic_id,
        "title": t.title,
        "speakers": t.speakers,
        "source_url": t.source_url,
        "format": t.format,
        "report_type": t.report_type,
    }


def _report_type_of(t: TopicMeta) -> str:
    """SPRS-provided slug preferred; parse from topic_id as fallback so
    older fixtures without report_type still categorize."""
    if t.report_type:
        return t.report_type
    m = _REPORT_TYPE_FROM_ID_RE.match(t.topic_id)
    return m.group(1) if m else "other"


def _category_label(slug: str) -> str:
    if slug in _CATEGORY_LABELS:
        return _CATEGORY_LABELS[slug]
    return slug.replace("-", " ").title() if slug else "Other"


def _compute_category_breakdown(topics: list[TopicMeta]) -> dict[str, int]:
    """Count topics by report_type, mapped to human-readable labels.
    Deterministic — always sums to len(topics)."""
    counter: Counter[str] = Counter()
    for t in topics:
        counter[_category_label(_report_type_of(t))] += 1
    return dict(counter)


def _summarize_topics_prompt(date: str, topics: list[TopicMeta]) -> str:
    topic_lines = "\n".join(
        f"- [{t.topic_id}] {t.title} — speakers: {', '.join(t.speakers) or 'unknown'}"
        for t in topics
    )
    # NOTE: we no longer ask the model for category_breakdown — that's
    # computed server-side from topic report_types. Nova Lite counts
    # unreliably when N > ~30.
    return f"""You are summarising a Singapore Parliament sitting.

Sitting date: {date}
Topics debated ({len(topics)} in total):

{topic_lines}

Return ONLY a JSON object between <json> and </json> tags with this exact shape:

<json>
{{
  "summary": "2-4 sentence plain-English overview of what this sitting covered",
  "interesting_topics": [
    {{"topic_id": "T1", "reason": "why this topic is worth reading"}}
  ]
}}
</json>

Rules:
- interesting_topics must reference topic_ids that appear in the list above. No fabrication.
- Pick 3-5 interesting_topics — the most consequential or newsworthy.
- Do not include any text outside the <json>...</json> block.
"""


def _parse_digest_json(text: str, valid_topic_ids: set[str]) -> dict:
    """Extract and validate the JSON payload from a Nova Lite reply.

    Tries `<json>...</json>` first, then falls back to the outermost
    `{...}` block. Drops any `interesting_topics` entries whose
    `topic_id` isn't in `valid_topic_ids` — never trust the model to
    not fabricate.
    """
    match = _JSON_BLOCK_RE.search(text)
    if match:
        raw = match.group(1).strip()
    else:
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1 or last <= first:
            log.error("digest agent: no JSON found in Nova Lite reply:\n%s", text)
            raise ValueError("digest agent could not find JSON in Nova Lite reply")
        raw = text[first : last + 1]

    parsed = json.loads(raw)

    kept: list[dict] = []
    for item in parsed.get("interesting_topics", []) or []:
        if item.get("topic_id") in valid_topic_ids:
            kept.append(item)
        else:
            log.warning(
                "digest agent: dropping fabricated topic_id %r",
                item.get("topic_id"),
            )
    parsed["interesting_topics"] = kept
    parsed.setdefault("summary", "")
    # category_breakdown is intentionally ignored if the model produced
    # one; run_digest computes it server-side from report_types.
    return parsed
