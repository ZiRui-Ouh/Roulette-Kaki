"""Research agent — Bedrock tool-use loop over Hansard debate transcripts.

Nova Pro receives a Converse `toolConfig` with two tools and decides, per
turn, whether the sitting overview alone answers the user's question or
whether to pull a specific topic transcript via `fetch_topic_transcript`.
The tool-use loop lives in `services/bedrock.chat_with_tools`; this
module owns the tool schemas, the closure-based tool handler, session
state, and grounding-marker parsing.

Flow:

1. Load/create the `ChatSessions` row (TTL enforced by `storage.py`).
2. Load the digest for `date` from DDB; build `{topic_id → topic_meta}`.
3. Build the sitting-overview `Document` and pre-hydrate any topics
   already in `session["topics_loaded"]` (plus the optional UI hint
   `topic_id` on this request) via `_hydrate_topic_doc`.
4. Call `bedrock.chat_with_tools` with the tool handler defined here.
   The handler mutates a closure-captured `loaded` dict as the model
   pulls transcripts. Cap policy: evict-and-inform (oldest FIFO).
5. Parse `<grounded>false</grounded>`; strip the marker from the visible
   reply. Persist the turn (refreshes 1h TTL). Return
   `ChatResult(reply, topics_used, grounded, usage)`.
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
for topics that have been loaded.

BEFORE calling any tool, silently scan the sitting overview's topic index.

- If NO topic title in the overview plausibly matches the user's question
  (e.g. user asks about crows and no topic in the overview relates to
  wildlife, pest control, or environment), do NOT call any tool. Reply:
  "This sitting did not cover <subject>." then end with the exact marker
  <grounded>false</grounded>. Stop.

- If ONE topic in the overview clearly matches the user's question and
  its transcript is NOT already attached, call `fetch_topic_transcript`
  ONCE for that topic_id, then answer from the returned transcript.

- If the user's question is about the sitting as a whole ("what topics
  were covered?", "which bills were passed?", "who spoke on transport?"),
  answer from the sitting overview WITHOUT calling any tool.

- For "who spoke on topic X?" questions specifically, prefer
  `list_speakers_for_topic` over fetching the full transcript.

Hard rules on tool calls:
- Never call `fetch_topic_transcript` more than TWICE per turn. If you
  cannot answer after two fetches, stop and answer from what you have.
- Never call `fetch_topic_transcript` for a topic that is already
  attached (a prior tool result said `already_attached` or `status: ok`).
- If a tool result has `status: error` or `note: transcript body
  unavailable`, do NOT retry — explain to the user and stop.
- At most 5 topic transcripts are attached concurrently. If a tool
  result contains `"evicted": <id>`, the oldest was dropped — do not
  re-fetch it this turn.

Answer rules:
- Cite the topic title and speaker where relevant.
- If the answer is NOT in any attached document, end your reply with the
  exact marker <grounded>false</grounded>.
- Do not answer from general knowledge. Do not speculate.

Style and length:
- Default reply length: 2-4 short sentences, or a tight bulleted list of
  at most 5 items when the user asked for multiple items.
- Never restate the user's question. Never open with "Certainly", "Sure",
  "Here is", or similar filler.
- Never emit XML or HTML tags in your reply except the exact
  <grounded>false</grounded> marker when the answer is not covered.
- Do NOT narrate your reasoning. No "<thinking>...</thinking>",
  "Let me check...", "Looking at the transcript...", "First I will...".
  Just answer.
- Use bold/headings ONLY when the answer is a genuine list of >3
  distinct sub-items. For 1-3 items, use prose.
- If the transcript is long, prefer summarising over exhaustive quoting.
  Aim for the crux in 100-200 words unless the user explicitly asks for
  "full details" or "everything".
"""


TOOL_SPECS: list[dict] = [
    {
        "toolSpec": {
            "name": "fetch_topic_transcript",
            "description": (
                "Fetch the full transcript for one topic in this sitting and "
                "attach it to the conversation. Only call when the user asks "
                "about a specific topic whose transcript is NOT already "
                "attached. topic_id must appear in the sitting overview's "
                "topic index."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "topic_id": {
                            "type": "string",
                            "description": (
                                "Topic id exactly as it appears in the "
                                "sitting overview's topic index."
                            ),
                        }
                    },
                    "required": ["topic_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "list_speakers_for_topic",
            "description": (
                "Cheap lookup: title + speakers for one topic id from digest "
                "metadata only (no S3 or SPRS fetch). Use to disambiguate "
                "before pulling a transcript."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"topic_id": {"type": "string"}},
                    "required": ["topic_id"],
                }
            },
        }
    },
]


# Detection: `grounded=False` only when the model emits the literal
# `<grounded>false</grounded>` marker. `<grounded>true</grounded>` is
# also considered grounded (True), same as no marker.
_GROUNDED_FALSE_RE = re.compile(
    r"<grounded>\s*false\s*</grounded>", re.IGNORECASE
)

# Stripping: remove any <grounded>true|false</grounded> tag before we
# hand the reply back to the client or persist it.
_GROUNDED_ANY_RE = re.compile(
    r"\s*<grounded>\s*(?:true|false)\s*</grounded>", re.IGNORECASE
)

# Nova Pro occasionally leaks a reasoning preamble even when the system
# prompt forbids it. Strip these tag pairs defensively so they never
# reach the user.
_REASONING_TAG_RE = re.compile(
    r"<(?:thinking|thought|reasoning|scratchpad|reflection|inner_monologue)>"
    r".*?"
    r"</(?:thinking|thought|reasoning|scratchpad|reflection|inner_monologue)>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ChatResult:
    reply: str
    topics_used: list[str]
    grounded: bool
    usage: dict


def _parse_grounded(reply: str) -> bool:
    return _GROUNDED_FALSE_RE.search(reply) is None


def _strip_grounded_marker(reply: str) -> str:
    """Strip both the grounded marker and any reasoning-tag preamble.
    Applied before storing history and before returning the reply, so
    neither surface leaks to the user or contaminates the next turn's
    history context."""
    cleaned = _REASONING_TAG_RE.sub("", reply)
    cleaned = _GROUNDED_ANY_RE.sub("", cleaned)
    return cleaned.strip()


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
    """Sitting-wide metadata document, always attached at message 0."""
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
        f"to answer questions about the sitting as a whole; call "
        f"fetch_topic_transcript for details on a specific topic.</em></p>"
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
    return TopicMeta(
        topic_id=digest_topic["topic_id"],
        title=digest_topic.get("title") or "",
        speakers=digest_topic.get("speakers") or [],
        source_url=digest_topic.get("source_url") or "",
        format=digest_topic.get("format") or "html",
    )


def _hydrate_topic_doc(
    date: str,
    topic_id: str,
    topic_meta_by_id: dict[str, dict],
) -> bedrock.Document | None:
    """S3 hit → cached bytes. S3 miss → scraper.fetch_report +
    storage.put_report. Scrape failure → metadata-only HTML placeholder
    (NOT cached, so a transient SPRS outage can't poison S3).

    Returns None only if `topic_id` isn't in `topic_meta_by_id`.
    """
    meta = topic_meta_by_id.get(topic_id)
    if meta is None:
        return None
    ext = meta.get("format") or "html"
    bytes_ = storage.get_report(date, topic_id, ext)
    if bytes_ is None:
        log.info("chat: fetching report for %s from SPRS", topic_id)
        try:
            bytes_ = scraper.fetch_report(_to_topic_meta(meta))
            storage.put_report(date, topic_id, ext, bytes_)
        except Exception as e:  # noqa: BLE001
            log.info(
                "SPRS fetch failed for %s (%s) — attaching metadata-only "
                "placeholder ephemerally; will retry SPRS next turn",
                topic_id,
                e,
            )
            topic_title = meta.get("title", topic_id)
            speakers_str = ", ".join(meta.get("speakers", []))
            bytes_ = (
                f"<html><body><h1>{topic_title}</h1>"
                f"<p>Speakers: {speakers_str}</p>"
                f"<p>NOTE: Full transcript for this topic could not be "
                f"retrieved this turn. Only the topic title and speakers "
                f"are available. Ask the user to try again shortly.</p>"
                f"</body></html>"
            ).encode("utf-8")
            # Deliberately NOT calling storage.put_report on the placeholder.
    return bedrock.Document(
        topic_id=topic_id,
        name=topic_id,
        format=ext,
        bytes_=bytes_,
    )


def run_chat(
    session_id: str,
    date: str,
    message: str,
    topic_id: str | None = None,
) -> ChatResult:
    """Handle one chat turn via the Bedrock tool-use loop."""
    # --- load session and digest ---------------------------------------
    session = storage.get_session(session_id) or _new_session(session_id, date)
    digest = storage.get_digest(date)
    if digest is None or digest.get("error") == "no_sitting":
        raise ValueError(
            f"no digest for date {date} — call GET /debates/{date} first"
        )
    topic_meta_by_id: dict[str, dict] = {
        t["topic_id"]: t for t in digest.get("topics", [])
    }

    # --- pre-hydrate loaded docs (insertion-order = FIFO eviction) -----
    overview_doc = _build_sitting_overview(date, digest)
    loaded: dict[str, bedrock.Document] = {}
    for tid in session.get("topics_loaded", []):
        if tid not in topic_meta_by_id:
            log.warning(
                "chat: session %s has stale topic_id %s (not in digest) — skipping",
                session_id, tid,
            )
            continue
        doc = _hydrate_topic_doc(date, tid, topic_meta_by_id)
        if doc is not None:
            loaded[tid] = doc

    # UI hint — user clicked a topic chip. Pre-hydrate so the model
    # doesn't waste a tool call on the obvious selection. Unknown ids
    # are ignored (never trust the frontend).
    if topic_id and topic_id in topic_meta_by_id and topic_id not in loaded:
        doc = _hydrate_topic_doc(date, topic_id, topic_meta_by_id)
        if doc is not None:
            loaded[topic_id] = doc

    # --- tool handler (closure over `loaded` and digest metadata) ------
    def _handle_tool(name: str, args: dict) -> tuple[dict, list[bedrock.Document]]:
        tid = args.get("topic_id")
        if not isinstance(tid, str) or not tid:
            return (
                {"status": "error", "error": "missing_topic_id"},
                [],
            )
        meta = topic_meta_by_id.get(tid)
        if meta is None:
            known = [t["topic_id"] for t in digest.get("topics", [])][:10]
            return (
                {
                    "status": "error",
                    "error": "unknown_topic_id",
                    "known_ids": known,
                },
                [],
            )

        if name == "list_speakers_for_topic":
            return (
                {
                    "status": "ok",
                    "title": meta.get("title") or tid,
                    "speakers": meta.get("speakers") or [],
                },
                [],
            )

        if name == "fetch_topic_transcript":
            if tid in loaded:
                return (
                    {
                        "status": "already_attached",
                        "title": meta.get("title") or tid,
                    },
                    [],
                )
            evicted: str | None = None
            if len(loaded) >= bedrock.MAX_TOPICS_PER_SESSION:
                evicted = next(iter(loaded))
                del loaded[evicted]
                log.info("handler: evicted %s (5-topic cap)", evicted)
            doc = _hydrate_topic_doc(date, tid, topic_meta_by_id)
            if doc is None:
                return ({"status": "error", "error": "fetch_failed"}, [])
            loaded[tid] = doc
            # Signal the "unavailable transcript" case to the model so
            # it can degrade gracefully instead of over-extrapolating.
            note_marker = b"could not be retrieved"
            result: dict = {
                "status": "ok",
                "title": meta.get("title") or tid,
                "speakers": meta.get("speakers") or [],
            }
            if note_marker in doc.bytes_:
                result["note"] = (
                    "transcript body unavailable this turn; only metadata "
                    "attached"
                )
            if evicted:
                result["evicted"] = evicted
            log.info("handler: attached %s", tid)
            return (result, [doc])

        return ({"status": "error", "error": f"unknown_tool:{name}"}, [])

    # --- history (plain text; strip any leftover grounded markers) -----
    history = [
        {
            "role": m["role"],
            "content": _strip_grounded_marker(m["content"]),
        }
        for m in session.get("chat_history", [])
    ]

    initial_docs: list[bedrock.Document] = [overview_doc, *loaded.values()]
    log.info(
        "chat_with_tools: starting with %d initial doc(s): %s",
        len(initial_docs),
        [d.topic_id for d in initial_docs],
    )

    # --- Bedrock tool-use loop ----------------------------------------
    try:
        reply_text, final_docs, usage = bedrock.chat_with_tools(
            system=SYSTEM_PROMPT,
            history=history,
            user_message=message,
            initial_docs=initial_docs,
            tool_specs=TOOL_SPECS,
            tool_handler=_handle_tool,
            max_tokens=700,  # caps runaway prose; ~500 English words
        )
        log.info("research agent Nova Pro usage: %s", usage)
    except Exception as e:  # noqa: BLE001
        # Honest failure — do not fabricate Hansard content. Frontend
        # renders a warning banner via grounded=False. Keep session
        # topics_loaded in sync with what the ChatResult claims,
        # otherwise the frontend chip list and the persisted state drift.
        log.warning("Bedrock chat unavailable (%s)", e)
        reply = (
            "I couldn't reach the language model just now. Please retry in "
            "a moment."
        )
        session["topics_loaded"] = list(loaded.keys())
        _persist_turn(session, message, reply, grounded=False)
        return ChatResult(
            reply=reply,
            topics_used=list(loaded.keys()),
            grounded=False,
            usage={},
        )

    # Derive topics_used from what actually ended up attached. The
    # overview doc is internal and never leaks into the response.
    kept_topic_ids = [d.topic_id for d in final_docs if not d.is_overview]
    session["topics_loaded"] = kept_topic_ids

    grounded = _parse_grounded(reply_text)
    visible_reply = _strip_grounded_marker(reply_text)
    _persist_turn(session, message, visible_reply, grounded)

    return ChatResult(
        reply=visible_reply,
        topics_used=kept_topic_ids,
        grounded=grounded,
        usage=usage,
    )
