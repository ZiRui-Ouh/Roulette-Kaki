"""Digest agent.

Runs once per sitting date. Result cached in DDB `DebateDigests` (no TTL —
sittings don't change).

Flow:
1. `storage.get_digest(date)` — return on cache hit.
2. `scraper.list_topics(date)` — empty ⇒ `{"error": "no_sitting"}`.
3. Read `fixtures/metadata_{date}.json` for {title, youtube_url}
   (Phase 3.5 real SPRS scraping will populate these from the site).
4. Build the summarize prompt over topic titles + speakers.
5. `bedrock.summarize(prompt)` — single Nova Lite call.
6. Extract JSON from the reply (tagged block or bare braces).
7. Server-side: `topic_count = len(topics)`, drop hallucinated
   `interesting_topics.topic_id` values not in the input list.
8. Persist via `storage.put_digest(...)`, return the row.

Reports are NOT fetched at digest time — the research agent (Phase 4)
scrapes lazily when the user first asks about a topic. See AGENTS.md.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from services import bedrock, storage
from services.scraper import TopicMeta, list_topics

log = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

_JSON_BLOCK_RE = re.compile(r"<json>(.*?)</json>", re.DOTALL)


def run_digest(date: str) -> dict:
    """Return the digest for `date`, running the agent on cache miss.

    Returns a digest dict on success, or
    `{"error": "no_sitting", "date": date}` if no sitting was held.
    Never writes a DDB row for no-sitting dates.
    """
    cached = storage.get_digest(date)
    if cached is not None:
        return cached

    topics = list_topics(date)
    if not topics:
        return {"error": "no_sitting", "date": date}

    metadata = _load_metadata(date)

    prompt = _summarize_topics_prompt(date, topics)
    text, usage = bedrock.summarize(prompt)
    log.info("digest agent Nova Lite usage: %s", usage)

    parsed = _parse_digest_json(text, valid_topic_ids={t.topic_id for t in topics})

    digest = {
        "date": date,
        "title": metadata["title"],
        "youtube_url": metadata["youtube_url"],
        "summary": parsed["summary"],
        "topic_count": len(topics),
        "category_breakdown": parsed["category_breakdown"],
        "interesting_topics": parsed["interesting_topics"],
        "topics": [_topic_dict(t) for t in topics],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    storage.put_digest(digest)
    return digest


def _load_metadata(date: str) -> dict:
    path = FIXTURES_DIR / f"metadata_{date}.json"
    if not path.exists():
        # Degrade gracefully. Phase 3.5's real scraper will populate these
        # from the SPRS site itself.
        return {"title": f"Sitting of {date}", "youtube_url": ""}
    with path.open() as f:
        return json.load(f)


def _topic_dict(t: TopicMeta) -> dict:
    return {
        "topic_id": t.topic_id,
        "title": t.title,
        "speakers": t.speakers,
        "source_url": t.source_url,
        "format": t.format,
    }


def _summarize_topics_prompt(date: str, topics: list[TopicMeta]) -> str:
    topic_lines = "\n".join(
        f"- [{t.topic_id}] {t.title} — speakers: {', '.join(t.speakers) or 'unknown'}"
        for t in topics
    )
    return f"""You are summarising a Singapore Parliament sitting.

Sitting date: {date}
Topics debated ({len(topics)} in total):

{topic_lines}

Return ONLY a JSON object between <json> and </json> tags with this exact shape:

<json>
{{
  "summary": "2-4 sentence plain-English overview of what this sitting covered",
  "category_breakdown": {{"CategoryName": count, ...}},
  "interesting_topics": [
    {{"topic_id": "T1", "reason": "why this topic is worth reading"}}
  ]
}}
</json>

Rules:
- interesting_topics must reference topic_ids that appear in the list above. No fabrication.
- category_breakdown counts must sum to exactly {len(topics)}.
- Pick 2-4 interesting_topics — the most consequential or newsworthy.
- Do not include any text outside the <json>...</json> block.
"""


def _parse_digest_json(text: str, valid_topic_ids: set[str]) -> dict:
    """Extract and validate the JSON payload from a Nova Lite reply.

    Tries `<json>...</json>` first, then falls back to the outermost
    `{...}` block. Drops any `interesting_topics` entries whose
    `topic_id` isn't in `valid_topic_ids` — never trust the model to not
    fabricate.
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
    parsed.setdefault("category_breakdown", {})
    parsed.setdefault("summary", "")
    return parsed
