"""Research agent — chat with document blocks.

Flow (see AGENTS.md and the Phase 4 plan):

1. Load or create a `ChatSessions` row (TTL enforced by `storage.py`).
2. Update `topics_loaded` — append the request's `topic_id` if it's a
   valid digest topic and not already loaded.
3. Load the digest for `date` from DDB; build `{topic_id → topic_meta}`.
4. For each loaded topic: fetch report bytes from S3 (cache hit) or
   lazy-scrape from SPRS via `scraper.fetch_report` on miss.
5. Empty-doc guardrail — if no docs are attached, return a "pick a
   topic" reply without burning Bedrock tokens.
6. Call `bedrock.chat_with_documents`. Plain-text history in; docs get
   placed at message 0 inside `bedrock.py` for stable cache prefix.
7. Parse the `<grounded>false</grounded>` marker; strip it from the
   visible reply.
8. Persist the exchange back to the session; `storage.put_session`
   refreshes the 1h TTL.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from services import bedrock, scraper, storage
from services.scraper import TopicMeta

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a research assistant for Singapore Parliament debates.
You will answer questions using ONLY the attached debate report documents.

Rules:
- If the answer is present in the documents, cite the topic title and
  speaker where relevant.
- If the answer is NOT in the documents, output exactly the marker
  <grounded>false</grounded> at the end of your reply, then say the report
  does not cover it.
- Do not answer from general knowledge. Do not speculate.
"""

# Detection: `grounded=False` only when the model emits the literal
# `<grounded>false</grounded>` marker. `<grounded>true</grounded>` is
# also considered grounded (True), same as no marker.
_GROUNDED_FALSE_RE = re.compile(
    r"<grounded>\s*false\s*</grounded>", re.IGNORECASE
)

# Stripping: remove any <grounded>true|false</grounded> tag before we
# hand the reply back to the client or persist it. The model sometimes
# mirrors the marker pattern with "true" to signal it did use the docs;
# that's cosmetic noise in the visible reply. We consume preceding
# whitespace so "answer <grounded>true</grounded>" → "answer", not
# "answer " with a trailing space. Trailing whitespace is preserved so
# an inline marker doesn't glue two words together.
_GROUNDED_ANY_RE = re.compile(
    r"\s*<grounded>\s*(?:true|false)\s*</grounded>", re.IGNORECASE
)


@dataclass
class ChatResult:
    reply: str
    topics_used: list[str]
    grounded: bool
    usage: dict


def _parse_grounded(reply: str) -> bool:
    """False iff the model emitted <grounded>false</grounded>. Otherwise True."""
    return _GROUNDED_FALSE_RE.search(reply) is None


def _strip_grounded_marker(reply: str) -> str:
    return _GROUNDED_ANY_RE.sub("", reply).strip()


def _new_session(session_id: str, date: str) -> dict:
    return {
        "session_id": session_id,
        "date": date,
        "topics_loaded": [],
        "chat_history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _persist_turn(
    session: dict,
    user_message: str,
    assistant_reply: str,
    grounded: bool,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    session["chat_history"] = [
        *session.get("chat_history", []),
        {"role": "user", "content": user_message, "timestamp": ts},
        {
            "role": "assistant",
            "content": assistant_reply,
            "timestamp": ts,
            "grounded": grounded,
        },
    ]
    storage.put_session(session)  # refreshes TTL to now + 3600


def _to_topic_meta(digest_topic: dict) -> TopicMeta:
    """Rehydrate a TopicMeta dataclass from the dict stored inside the
    digest row's `topics` list. Used to hand off to
    `scraper.fetch_report` on cache miss.
    """
    return TopicMeta(
        topic_id=digest_topic["topic_id"],
        title=digest_topic.get("title") or "",
        speakers=digest_topic.get("speakers") or [],
        source_url=digest_topic.get("source_url") or "",
        format=digest_topic.get("format") or "html",
    )


def run_chat(
    session_id: str,
    date: str,
    message: str,
    topic_id: str | None = None,
) -> ChatResult:
    """Handle one chat turn. See module docstring for the flow."""
    # --- load session (or create) ---------------------------------------
    session = storage.get_session(session_id) or _new_session(session_id, date)

    # --- load digest for topic metadata ---------------------------------
    digest = storage.get_digest(date)
    if digest is None or digest.get("error") == "no_sitting":
        raise ValueError(
            f"no digest for date {date} — call GET /debates/{date} first"
        )
    topic_meta_by_id: dict[str, dict] = {
        t["topic_id"]: t for t in digest.get("topics", [])
    }

    # --- add topic_id to session (with digest-membership validation) ----
    if topic_id:
        if topic_id in topic_meta_by_id:
            if topic_id not in session["topics_loaded"]:
                session["topics_loaded"] = [*session["topics_loaded"], topic_id]
        else:
            log.warning(
                "chat: ignoring unknown topic_id %r for date %s", topic_id, date
            )

    # --- hydrate report bytes for every loaded topic --------------------
    docs: list[bedrock.Document] = []
    for tid in session["topics_loaded"]:
        meta = topic_meta_by_id.get(tid)
        if meta is None:
            log.warning(
                "chat: session %s has stale topic_id %s (not in digest) — skipping",
                session_id,
                tid,
            )
            continue
        ext = meta.get("format") or "html"
        bytes_ = storage.get_report(date, tid, ext)
        if bytes_ is None:
            log.info("chat: fetching report for %s from SPRS", tid)
            bytes_ = scraper.fetch_report(_to_topic_meta(meta))
            storage.put_report(date, tid, ext, bytes_)
        docs.append(
            bedrock.Document(
                topic_id=tid,
                name=tid,
                format=ext,
                bytes_=bytes_,
            )
        )

    # --- empty-doc guardrail (no Bedrock call) --------------------------
    if not docs:
        reply = (
            "I don't have any topics loaded yet. Pick a topic from the "
            "sitting summary and try again."
        )
        _persist_turn(session, message, reply, grounded=False)
        return ChatResult(
            reply=reply, topics_used=[], grounded=False, usage={}
        )

    # --- call Bedrock ---------------------------------------------------
    # Prior history in plain-text form. Strip any leftover grounded
    # markers so they don't leak into the model's next-turn context.
    history = [
        {
            "role": m["role"],
            "content": _strip_grounded_marker(m["content"]),
        }
        for m in session.get("chat_history", [])
    ]
    reply_text, kept_topic_ids, usage = bedrock.chat_with_documents(
        SYSTEM_PROMPT, history, message, docs,
    )
    log.info("research agent Nova Pro usage: %s", usage)

    # Mirror bedrock's cap into session state — bedrock may have dropped
    # oldest topics if we went over 5 / 50K tokens.
    session["topics_loaded"] = kept_topic_ids

    # --- parse and persist ----------------------------------------------
    grounded = _parse_grounded(reply_text)
    visible_reply = _strip_grounded_marker(reply_text)
    _persist_turn(session, message, visible_reply, grounded)

    return ChatResult(
        reply=visible_reply,
        topics_used=kept_topic_ids,
        grounded=grounded,
        usage=usage,
    )
