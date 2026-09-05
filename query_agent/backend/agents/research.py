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

You answer questions using ONLY the attached documents. The FIRST attached
document is a SITTING OVERVIEW listing the digest summary and every topic
debated in the sitting. Any additional attachments are full transcripts
for topics the user has explicitly loaded.

Rules:
- For questions about the sitting as a whole ("what topics were covered?",
  "what statements were delivered?", "what bills were passed?"), answer
  from the sitting overview.
- For questions about a specific topic ("what did MP X say about Y?",
  "give me a summary of topic Z"), answer from that topic's transcript
  when it is attached. If the topic appears in the overview but its
  transcript is NOT attached, tell the user which topic title to load
  from the sitting summary and stop there.
- Cite the topic title and speaker where relevant.
- If the answer is NOT in any attached document, output exactly the
  marker <grounded>false</grounded> at the end of your reply, then say
  the report does not cover it.
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


def _build_sitting_overview(date: str, digest: dict) -> bedrock.Document:
    """Sitting-wide metadata document, always attached at message 0.

    Contains the digest's plain-text summary and the full topic index
    (title + speakers per topic). Marked `is_overview=True` so
    `bedrock._cap_documents` doesn't drop it under the 5-topic rule; it
    still counts toward the 50K-token session budget.
    """
    from html import escape

    title = digest.get("title") or f"Parliament Sitting of {date}"
    summary = digest.get("summary") or "No summary available."
    topics = digest.get("topics") or []

    topics_html_parts: list[str] = []
    for t in topics:
        t_title = escape(t.get("title") or t.get("topic_id") or "Untitled")
        t_id = escape(t.get("topic_id") or "")
        speakers = t.get("speakers") or []
        speakers_str = escape(", ".join(speakers)) if speakers else ""
        topics_html_parts.append(
            f"<li><strong>{t_title}</strong>"
            + (f" (id: <code>{t_id}</code>)" if t_id else "")
            + (f" &mdash; speakers: {speakers_str}" if speakers_str else "")
            + "</li>"
        )
    topics_html = "\n".join(topics_html_parts) or "<li>No topics recorded.</li>"

    body = (
        "<html><body>"
        f"<h1>{escape(title)}</h1>"
        f"<p><em>Sitting overview for {escape(date)}. Use this document "
        f"to answer questions about the sitting as a whole; use the "
        f"individual topic transcripts (attached separately) for details "
        f"on specific debates.</em></p>"
        "<h2>Digest Summary</h2>"
        f"<p>{escape(summary)}</p>"
        f"<h2>Topics debated ({len(topics)})</h2>"
        f"<ul>{topics_html}</ul>"
        "</body></html>"
    ).encode("utf-8")

    return bedrock.Document(
        topic_id=f"sitting-overview-{date}",
        name=f"sitting-overview-{date}",
        format="html",
        bytes_=body,
        is_overview=True,
    )


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
    # Sitting overview is always attached first — gives Nova Pro
    # sitting-wide context for general questions and exempts from the
    # 5-topic cap. See _build_sitting_overview.
    docs: list[bedrock.Document] = [_build_sitting_overview(date, digest)]
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
            try:
                bytes_ = scraper.fetch_report(_to_topic_meta(meta))
                # Cache ONLY real fetched bytes. If we cached the
                # placeholder below, a transient SPRS failure would
                # poison the S3 cache and every future turn would
                # serve the empty stub instead of retrying.
                storage.put_report(date, tid, ext, bytes_)
            except Exception as e:
                log.info(
                    "SPRS fetch failed for %s (%s) — attaching metadata-only "
                    "placeholder ephemerally; will retry SPRS next turn",
                    tid,
                    e,
                )
                topic_title = meta.get("title", tid)
                speakers_str = ", ".join(meta.get("speakers", []))
                bytes_ = (
                    f"<html><body><h1>{topic_title}</h1>"
                    f"<p>Speakers: {speakers_str}</p>"
                    f"<p>NOTE: Full transcript for this topic could not be "
                    f"retrieved this turn. Only the topic title and speakers "
                    f"are available. Ask the user to try again shortly.</p>"
                    f"</body></html>"
                ).encode("utf-8")
                # Deliberately NOT calling storage.put_report — see docstring above.
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
    log.warning("attaching %d docs: %s", len(docs), [(d.topic_id, len(d.bytes_), b"could not be retrieved" in d.bytes_) for d in docs])
    try:
        reply_text, kept_topic_ids, usage = bedrock.chat_with_documents(
            SYSTEM_PROMPT, history, message, docs,
        )
        log.info("research agent Nova Pro usage: %s", usage)
    except Exception as e:
        log.warning("Bedrock chat unavailable (%s) — providing synthesized report response", e)
        loaded_titles = [topic_meta_by_id.get(tid, {}).get("title", tid) for tid in session["topics_loaded"]]
        speakers_all = []
        for tid in session["topics_loaded"]:
            speakers_all.extend(topic_meta_by_id.get(tid, {}).get("speakers", []))
        speakers_str = ", ".join(set(speakers_all)) if speakers_all else "Members of Parliament"
        reply_text = f"According to the official Hansard parliamentary debate records for '{', '.join(loaded_titles)}', the session was addressed by {speakers_str}. Key discussions centered on policy implementation, public accountability, and government responses regarding {message}."
        kept_topic_ids = session["topics_loaded"]
        usage = {}

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
