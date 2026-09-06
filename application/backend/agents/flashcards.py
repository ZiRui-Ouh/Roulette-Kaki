"""Flashcards agent — Nova Lite condenses Hansard content into
single-sided summary cards.

Two entry points:

- `generate_from_topic(date, topic_id, digest, count=5)` — grounds on the
  raw Hansard transcript for a topic. Reuses the S3 → SPRS → placeholder
  fetch chain from `agents/research._hydrate_topic_doc`, but decodes and
  truncates the bytes to a plain string prompt instead of attaching a
  Bedrock `Document` block.
- `generate_from_chat_reply(date, reply_text, topic_ids=None, count=5)` —
  condenses a Hansard Research Agent assistant reply into cards.

Bounded costs (Nova Lite, ~$0.06/1M input, ~$0.24/1M output):

- `count` clamped to [1, 8]
- `max_tokens=1200` output ceiling
- 12,000-char input truncation

The agent is stateless — no session/DDB writes.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from schemas import Flashcard, FlashcardDeck
from services import bedrock, scraper, storage
from services.scraper import TopicMeta

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a study-card generator for Singapore Parliament debate content.

Given (a) a topic title and speakers plus the debate transcript, OR (b) a
research assistant's reply, produce a small deck of single-sided summary
cards. Each card captures ONE concrete fact, position, or takeaway a
Singaporean citizen should remember from the sitting.

Rules:
- Each card has a `title` (3-8 word noun phrase, no trailing punctuation)
  and a `body` (1-3 short sentences, plain English, no jargon dumps, no
  citations).
- Cover distinct sub-ideas. Do NOT repeat the topic title across cards.
- If the source is thin, produce FEWER cards rather than padding.
- Never invent figures, dates, or attributions absent from the source.
  If unsure, paraphrase generally.
- No Q/A framing ("Question: ..."). No leading emoji. No markdown headings.

Return ONLY a JSON object of the form:
{ "cards": [ { "title": "...", "body": "..." }, ... ] }
Do NOT wrap in markdown fences. Do NOT include any preamble or postscript.
"""


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MAX_TRANSCRIPT_CHARS = 50_000
_MIN_COUNT = 1
_MAX_COUNT = 10


def _extract_json_object(raw_text: str) -> dict:
    """Safely extract and decode a JSON object from a model response."""
    clean_text = (raw_text or "").strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()
    match = _JSON_BLOCK_RE.search(clean_text)
    if not match:
        raise ValueError(f"No JSON object found in flashcards response: {clean_text[:200]}")
    return json.loads(match.group(0))


def _to_topic_meta(meta: dict) -> TopicMeta:
    return TopicMeta(
        topic_id=meta["topic_id"],
        title=meta.get("title") or "",
        speakers=meta.get("speakers") or [],
        source_url=meta.get("source_url") or "",
        format=meta.get("format") or "html",
    )


def _clamp_count(count: int) -> int:
    return max(_MIN_COUNT, min(int(count or _MIN_COUNT), _MAX_COUNT))


def _topic_transcript_text(
    date: str,
    topic_id: str,
    digest: dict,
) -> tuple[str, dict]:
    """S3 → SPRS → metadata placeholder. Returns (decoded_text, topic_meta).

    Mirrors `agents/research._hydrate_topic_doc` but returns a decoded,
    tag-stripped, truncated string instead of a Bedrock `Document`.
    """
    topics_by_id = {t["topic_id"]: t for t in digest.get("topics") or []}
    meta = topics_by_id.get(topic_id)
    if meta is None:
        raise ValueError(f"topic_id {topic_id!r} not found in digest for {date}")

    ext = meta.get("format") or "html"
    bytes_ = storage.get_report(date, topic_id, ext)
    if bytes_ is None:
        log.info("flashcards: fetching report for %s from SPRS", topic_id)
        try:
            bytes_ = scraper.fetch_report(_to_topic_meta(meta))
            storage.put_report(date, topic_id, ext, bytes_)
        except Exception as e:  # noqa: BLE001
            log.info(
                "flashcards: SPRS fetch failed for %s (%s) — using metadata placeholder",
                topic_id,
                e,
            )
            title = meta.get("title") or topic_id
            speakers = ", ".join(meta.get("speakers") or [])
            bytes_ = (
                f"<h1>{title}</h1><p>Speakers: {speakers}</p>"
                f"<p>Full transcript unavailable; only the title and speakers are known.</p>"
            ).encode("utf-8")

    text = bytes_.decode("utf-8", errors="ignore")
    text = _HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_TRANSCRIPT_CHARS], meta


def _mint_cards(
    payload: dict,
    *,
    date: str,
    topic_id: Optional[str],
    source: str,
) -> FlashcardDeck:
    raw_cards = payload.get("cards") if isinstance(payload, dict) else None
    cards: list[Flashcard] = []
    for c in raw_cards or []:
        if not isinstance(c, dict):
            continue
        title = (c.get("title") or "").strip()
        body = (c.get("body") or "").strip()
        if not title or not body:
            continue
        cards.append(Flashcard(id=str(uuid.uuid4()), title=title, body=body))

    return FlashcardDeck(
        date=date,
        topic_id=topic_id,
        source=source,
        cards=cards,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def generate_from_topic(
    date: str,
    topic_id: str,
    digest: dict,
    count: int = 5,
) -> FlashcardDeck:
    """Generate a deck from a raw Hansard topic transcript."""
    if not digest:
        raise ValueError(f"digest for {date} is empty; cannot resolve topic {topic_id}")

    target_count = _clamp_count(count)
    text, meta = _topic_transcript_text(date, topic_id, digest)
    title = meta.get("title") or topic_id
    speakers = ", ".join(meta.get("speakers") or []) or "Members of Parliament"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"TOPIC TITLE: {title}\n"
        f"SPEAKERS: {speakers}\n"
        f"SITTING DATE: {date}\n"
        f"TARGET CARD COUNT: {target_count}\n\n"
        f"TRANSCRIPT (may be truncated):\n{text}\n\n"
        f"Return ONLY the JSON object."
    )

    raw = bedrock.ask_nova(prompt, max_tokens=1200)
    parsed = _extract_json_object(raw)
    deck = _mint_cards(parsed, date=date, topic_id=topic_id, source="topic")
    log.info(
        "flashcards.topic: date=%s topic=%s -> %d cards",
        date,
        topic_id,
        len(deck.cards),
    )
    return deck


def generate_from_chat_reply(
    date: str,
    reply_text: str,
    topic_ids: Optional[list[str]] = None,
    count: int = 5,
) -> FlashcardDeck:
    """Generate a deck from a Hansard Research Agent assistant reply."""
    if not reply_text or not reply_text.strip():
        raise ValueError("reply_text must be non-empty")

    target_count = _clamp_count(count)
    hint = ""
    if topic_ids:
        hint = f"Grounded topic_ids (for context only, do not cite): {list(topic_ids)}\n"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"SITTING DATE: {date}\n"
        f"{hint}"
        f"TARGET CARD COUNT: {target_count}\n\n"
        f"ASSISTANT REPLY TO CONDENSE:\n{reply_text[:_MAX_TRANSCRIPT_CHARS]}\n\n"
        f"Return ONLY the JSON object."
    )

    raw = bedrock.ask_nova(prompt, max_tokens=1200)
    parsed = _extract_json_object(raw)
    deck = _mint_cards(parsed, date=date, topic_id=None, source="chat")
    log.info(
        "flashcards.chat: date=%s topics=%s reply_chars=%d -> %d cards",
        date,
        topic_ids,
        len(reply_text),
        len(deck.cards),
    )
    return deck
