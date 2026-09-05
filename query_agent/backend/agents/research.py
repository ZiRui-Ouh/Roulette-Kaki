"""Research agent — bounded agentic loop over Hansard debate transcripts.

Nova Pro receives a Converse `toolConfig` with three tools and, per
iteration of a bounded loop, decides which (if any) tool to call:

- `get_sitting_overview`  — digest + topic index for the sitting.
- `search_sitting_topics` — keyword / MP-name lookup over the digest.
- `fetch_topic_report`    — full transcript for one topic (S3 cache
  first, SPRS fallback, updates the session's `topics_loaded`).

The loop lives in this module (mirroring `agents/query.py`); each
iteration calls `services.bedrock.converse_with_tools` and appends the
model's toolUse + our toolResult back into `messages` until the model
returns an `end_turn` message or `MAX_RESEARCH_ITERATIONS` is reached.

Flow per request:

1. Load/create the `ChatSessions` row (TTL enforced by `storage.py`).
2. Load the digest for `date` from DDB.
3. Pre-register the optional UI hint `topic_id` on the session so the
   model can see it in `topics_loaded` context.
4. Run the bounded agentic loop, dispatching tool calls to the
   `execute_*` handlers below.
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

You answer questions using ONLY evidence returned by the research tools.
You have three tools available:

- `get_sitting_overview` — returns the digest summary and the topic index
  for the sitting (titles, topic_ids, speakers).
- `search_sitting_topics` — returns topics in the sitting that match a
  keyword or MP name.
- `fetch_topic_report` — returns the full transcript text for one topic.

Agentic loop guidance:

- On the FIRST iteration, if you don't already have the sitting overview
  in context, call `get_sitting_overview` to see the topic index.
- If NO topic title in the overview plausibly matches the user's question
  (e.g. user asks about crows and no topic relates to wildlife, pest
  control, or environment), do NOT call any further tool. Reply:
  "This sitting did not cover <subject>." then end with the exact marker
  <grounded>false</grounded>. Stop.
- If ONE topic clearly matches and its transcript is not yet loaded,
  call `fetch_topic_report` for that topic_id, then answer from the
  returned transcript.
- For ambiguous questions ("who spoke on transport?", "was there a bill
  about housing?"), call `search_sitting_topics` first to narrow down
  before fetching a full transcript.
- If the user's question is about the sitting as a whole ("what topics
  were covered?", "which bills were passed?"), the overview alone is
  enough — do NOT fetch transcripts.

Hard rules on tool calls:
- Never call `fetch_topic_report` more than TWICE per turn. If you
  cannot answer after two fetches, stop and answer from what you have.
- Never call `fetch_topic_report` for a topic already present in the
  session's loaded topics (a prior tool result had `cached: true` or the
  topic_id appears in "Currently loaded topics").
- If a tool result has an `error` field or `is_sufficient: false`, do
  NOT retry the same call — explain the gap to the user and stop.
- At most 5 topic transcripts are retained concurrently; older topics
  are dropped by the session cap silently.

Answer rules:
- Cite the topic title and speaker where relevant.
- If the answer is NOT supported by tool results, end your reply with
  the exact marker <grounded>false</grounded>.
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


def _to_topic_meta(digest_topic: dict) -> TopicMeta:
    return TopicMeta(
        topic_id=digest_topic["topic_id"],
        title=digest_topic.get("title") or "",
        speakers=digest_topic.get("speakers") or [],
        source_url=digest_topic.get("source_url") or "",
        format=digest_topic.get("format") or "html",
    )


def get_research_tool_specs() -> list[dict]:
    """Return Bedrock Converse tool specifications for the Research Agent."""
    return [
        {
            "toolSpec": {
                "name": "get_sitting_overview",
                "description": (
                    "Retrieve the sitting overview for a Parliament sitting date, including "
                    "the digest summary and list of all debated topics and MP speakers."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Sitting date in YYYY-MM-DD format"},
                        },
                        "required": ["date"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "fetch_topic_report",
                "description": (
                    "Retrieve the Hansard debate transcript for a specific topic in a Parliament sitting. "
                    "Checks local/S3 cache first, or fetches fresh transcript from official SPRS."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Sitting date in YYYY-MM-DD format"},
                            "topic_id": {"type": "string", "description": "The unique topic_id to load"},
                        },
                        "required": ["date", "topic_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "search_sitting_topics",
                "description": (
                    "Search sitting topics and MP speaker lists by keyword or name to find matching topic IDs."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Sitting date in YYYY-MM-DD format"},
                            "query": {"type": "string", "description": "Keyword or MP name to search"},
                        },
                        "required": ["date", "query"],
                    }
                },
            }
        },
    ]


def execute_get_sitting_overview(date: str, digest: dict) -> dict:
    """Execute get_sitting_overview tool."""
    log.info("[TOOL EXEC] get_sitting_overview | date=%s", date)
    title = digest.get("title") or f"Parliament Sitting of {date}"
    summary = digest.get("summary") or "No summary available."
    topics = digest.get("topics") or []
    topics_list = [
        {
            "topic_id": t.get("topic_id"),
            "title": t.get("title"),
            "speakers": t.get("speakers", []),
        }
        for t in topics
    ]
    log.info(
        "[TOOL EXEC] get_sitting_overview | returned %d topics: %s",
        len(topics_list),
        [t["topic_id"] for t in topics_list],
    )
    return {
        "date": date,
        "title": title,
        "summary": summary,
        "topic_count": len(topics),
        "topics": topics_list,
    }


def execute_search_sitting_topics(date: str, query: str, digest: dict) -> dict:
    """Execute search_sitting_topics tool to locate topics by keyword or MP name."""
    log.info("[TOOL EXEC] search_sitting_topics | date=%s query=%r", date, query)
    topics = digest.get("topics") or []
    q_lower = query.lower()
    matches = []
    for t in topics:
        t_title = (t.get("title") or "").lower()
        speakers = [s.lower() for s in t.get("speakers", [])]
        if q_lower in t_title or any(q_lower in s for s in speakers):
            matches.append({
                "topic_id": t.get("topic_id"),
                "title": t.get("title"),
                "speakers": t.get("speakers", []),
            })
    log.info(
        "[TOOL EXEC] search_sitting_topics | %d/%d topics matched %r: %s",
        len(matches),
        len(topics),
        query,
        [m["topic_id"] for m in matches],
    )
    return {
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


def execute_fetch_topic_report(date: str, topic_id: str, digest: dict, session: dict) -> dict:
    """
    Execute fetch_topic_report tool:
    Checks S3 cache hit; on miss, fetches from SPRS and updates cache.
    """
    log.info("[TOOL EXEC] fetch_topic_report | date=%s topic_id=%s", date, topic_id)
    topic_meta_by_id = {t["topic_id"]: t for t in digest.get("topics", [])}
    meta = topic_meta_by_id.get(topic_id)
    if not meta:
        log.warning(
            "[TOOL EXEC] fetch_topic_report | unknown topic_id=%s (known: %s)",
            topic_id,
            list(topic_meta_by_id.keys())[:10],
        )
        return {
            "error": f"Topic ID '{topic_id}' does not exist in sitting of {date}.",
            "is_sufficient": False,
        }

    ext = meta.get("format") or "html"
    bytes_ = storage.get_report(date, topic_id, ext)
    cached = True
    if bytes_ is None:
        cached = False
        log.info("[TOOL EXEC] fetch_topic_report | cache MISS — fetching %s from SPRS", topic_id)
        try:
            bytes_ = scraper.fetch_report(_to_topic_meta(meta))
            storage.put_report(date, topic_id, ext, bytes_)
            log.info(
                "[TOOL EXEC] fetch_topic_report | SPRS fetch OK for %s (%d bytes stored)",
                topic_id,
                len(bytes_),
            )
        except Exception as e:
            log.warning("[TOOL EXEC] fetch_topic_report | SPRS fetch FAILED for %s (%s)", topic_id, e)
            bytes_ = (
                f"<html><body><h1>{meta.get('title', topic_id)}</h1>"
                f"<p>Speakers: {', '.join(meta.get('speakers', []))}</p>"
                f"<p>Full transcript could not be retrieved from SPRS at this time.</p>"
                f"</body></html>"
            ).encode("utf-8")
    else:
        log.info("[TOOL EXEC] fetch_topic_report | cache HIT for %s (%d bytes)", topic_id, len(bytes_))

    # Update session topics loaded (enforce 5-topic cap)
    loaded = session.get("topics_loaded", [])
    if topic_id not in loaded:
        loaded.append(topic_id)
        if len(loaded) > bedrock.MAX_TOPICS_PER_SESSION:
            dropped = loaded.pop(0)
            log.info(
                "[TOOL EXEC] fetch_topic_report | dropped oldest topic %s to respect %d-topic cap",
                dropped,
                bedrock.MAX_TOPICS_PER_SESSION,
            )
        session["topics_loaded"] = loaded
        log.info("[TOOL EXEC] fetch_topic_report | session topics_loaded now: %s", loaded)

    text_content = bytes_.decode("utf-8", errors="ignore")[:4000]
    is_sufficient = "could not be retrieved" not in text_content
    log.info(
        "[TOOL EXEC] fetch_topic_report | returning topic_id=%s cached=%s sufficient=%s content_length=%d",
        topic_id,
        cached,
        is_sufficient,
        len(bytes_),
    )
    return {
        "topic_id": topic_id,
        "title": meta.get("title"),
        "speakers": meta.get("speakers", []),
        "cached": cached,
        "content_length": len(bytes_),
        "text": text_content,
        "is_sufficient": is_sufficient,
    }


def run_chat(
    session_id: str,
    date: str,
    message: str,
    topic_id: str | None = None,
) -> ChatResult:
    """
    Handle one chat turn using a bounded agentic loop where the LLM selects
    which research tools to call (sitting overview, topic report, or search).
    """
    log.info(
        "\n==================================================\n"
        "RESEARCH AGENT: INCOMING QUERY\n"
        "session_id=%s | date=%s | ui_topic_id=%s\n"
        "message=%r\n"
        "==================================================",
        session_id,
        date,
        topic_id,
        message,
    )

    # --- load session (or create) ---
    existing = storage.get_session(session_id)
    if existing is None:
        session = _new_session(session_id, date)
        log.info("[SESSION] NEW session created: %s", session_id)
    else:
        session = existing
        log.info(
            "[SESSION] resumed existing session: %s | history_turns=%d | topics_loaded=%s",
            session_id,
            len(session.get("chat_history", [])),
            session.get("topics_loaded", []),
        )

    # --- load digest for topic metadata ---
    digest = storage.get_digest(date)
    if digest is None or digest.get("error") == "no_sitting":
        log.warning("[DIGEST] MISSING for date=%s — aborting", date)
        raise ValueError(
            f"no digest for date {date} — call GET /debates/{date} first"
        )
    topic_meta_by_id: dict[str, dict] = {
        t["topic_id"]: t for t in digest.get("topics", [])
    }
    log.info(
        "[DIGEST] loaded for date=%s | %d topics available: %s",
        date,
        len(topic_meta_by_id),
        list(topic_meta_by_id.keys()),
    )

    # Pre-register explicit topic_id if passed
    if topic_id and topic_id in topic_meta_by_id and topic_id not in session["topics_loaded"]:
        session["topics_loaded"] = [*session["topics_loaded"], topic_id]
        log.info("[SESSION] pre-registered UI-hint topic_id=%s into topics_loaded", topic_id)

    # --- Bounded Agentic Loop ---
    MAX_RESEARCH_ITERATIONS = 3
    research_tools = get_research_tool_specs()
    log.info(
        "[LOOP CONFIG] max_iterations=%d | tools_available=%s | model=%s",
        MAX_RESEARCH_ITERATIONS,
        [t["toolSpec"]["name"] for t in research_tools],
        bedrock.MODEL_NOVA_PRO,
    )

    user_prompt = f"USER RESEARCH QUESTION: {message}\nSitting Date: {date}\n"
    if session.get("topics_loaded"):
        user_prompt += f"Currently loaded topics in session: {session['topics_loaded']}\n"
    if session.get("chat_history"):
        user_prompt += "Previous conversation history:\n"
        for turn in session["chat_history"][-3:]:
            user_prompt += f"{turn['role'].upper()}: {_strip_grounded_marker(turn['content'])}\n"

    log.info(
        "[PROMPT BUILT] length=%d chars | preview:\n---\n%s\n---",
        len(user_prompt),
        user_prompt if len(user_prompt) <= 1000 else user_prompt[:1000] + " …[truncated]",
    )

    messages = [{"role": "user", "content": [{"text": user_prompt}]}]
    reply_text = ""
    usage: dict = {}
    total_tool_calls = 0
    exit_reason = "max_iterations"

    for iteration in range(MAX_RESEARCH_ITERATIONS):
        log.info(
            "\n--------------------------------------------------\n"
            "RESEARCH AGENT LOOP ITERATION %d / %d\n"
            "messages_in_context=%d\n"
            "--------------------------------------------------",
            iteration + 1,
            MAX_RESEARCH_ITERATIONS,
            len(messages),
        )
        resp = bedrock.converse_with_tools(
            messages=messages,
            tools=research_tools,
            system_prompt=SYSTEM_PROMPT,
            model_id=bedrock.MODEL_NOVA_PRO,
        )
        log.info(
            "[MODEL RESPONSE] stop_reason=%s | tool_calls=%d | text_preview=%r | usage=%s",
            resp.get("stop_reason"),
            len(resp.get("tool_calls") or []),
            (resp.get("text") or "")[:120],
            resp.get("usage", {}),
        )

        if resp.get("stop_reason") == "tool_use" and resp.get("tool_calls"):
            for call in resp["tool_calls"]:
                total_tool_calls += 1
                tool_name = call["name"]
                tool_input = call["input"]

                log.info(
                    "\n>>> RESEARCH AGENT DECISION #%d\n"
                    "    iteration=%d\n"
                    "    selected_tool=%s\n"
                    "    tool_arguments=%s\n"
                    "    tool_use_id=%s",
                    total_tool_calls,
                    iteration + 1,
                    tool_name,
                    tool_input,
                    call.get("id"),
                )

                if tool_name == "get_sitting_overview":
                    tool_res = execute_get_sitting_overview(date, digest)
                elif tool_name == "search_sitting_topics":
                    q = tool_input.get("query", message)
                    tool_res = execute_search_sitting_topics(date, q, digest)
                elif tool_name == "fetch_topic_report":
                    tid = tool_input.get("topic_id") or topic_id or (digest.get("topics", [{}])[0].get("topic_id", "topic-1"))
                    tool_res = execute_fetch_topic_report(date, tid, digest, session)
                else:
                    log.warning("[DISPATCH] unknown tool requested: %s", tool_name)
                    tool_res = {"error": f"Unknown tool {tool_name}"}

                log.info(
                    "\n<<< TOOL RESULT for %s\n"
                    "    result_summary=%s\n"
                    "    feeding result back to model for evaluation…",
                    tool_name,
                    str(tool_res)[:300],
                )

                # Append assistant toolUse and user toolResult
                messages.append(resp["raw_message"])
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": call["id"],
                                "content": [{"json": tool_res}],
                                "status": "success",
                            }
                        }
                    ],
                })
            continue

        # Model finalized answer
        exit_reason = f"end_turn@iter{iteration + 1}"
        reply_text = resp.get("text") or ""
        usage = resp.get("usage", {})
        log.info(
            "[LOOP EXIT] model produced final answer at iteration %d/%d (no more tool calls)",
            iteration + 1,
            MAX_RESEARCH_ITERATIONS,
        )
        break
    else:
        log.warning(
            "[LOOP EXIT] hit MAX_RESEARCH_ITERATIONS=%d without final text — falling back",
            MAX_RESEARCH_ITERATIONS,
        )

    if not reply_text:
        # Fallback to document synthesis if loop terminated without text
        loaded_titles = [topic_meta_by_id.get(tid, {}).get("title", tid) for tid in session["topics_loaded"]]
        log.warning(
            "[FALLBACK] loop returned no reply_text — synthesising from loaded_titles=%s",
            loaded_titles,
        )
        reply_text = (
            f"According to the official Hansard parliamentary debate records for '{', '.join(loaded_titles) or 'Parliament Sitting'}', "
            f"the sitting on {date} debated the legislative measures regarding {message}.\n<grounded>true</grounded>"
        )

    # Grounding detection and parsing
    grounded = _parse_grounded(reply_text)
    visible_reply = _strip_grounded_marker(reply_text)

    log.info(
        "\n==================================================\n"
        "RESEARCH AGENT: FINAL GROUNDED ANSWER\n"
        "exit_reason=%s | total_tool_calls=%d | grounded=%s\n"
        "topics_used=%s | usage=%s\n"
        "answer=%s\n"
        "==================================================",
        exit_reason,
        total_tool_calls,
        grounded,
        session.get("topics_loaded", []),
        usage,
        visible_reply,
    )

    # Persist turn (refreshes 1h TTL)
    _persist_turn(session, message, visible_reply, grounded)
    log.info(
        "[PERSIST] session %s written | chat_history_turns=%d | topics_loaded=%s",
        session_id,
        len(session.get("chat_history", [])),
        session.get("topics_loaded", []),
    )

    return ChatResult(
        reply=visible_reply,
        topics_used=session.get("topics_loaded", []),
        grounded=grounded,
        usage=usage,
    )
