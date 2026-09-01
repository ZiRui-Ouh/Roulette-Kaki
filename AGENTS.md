# Agents — Roulette-Kaki

This file documents the AI agents used across the repo's features. See
`ARCHITECTURE.md` for how they fit into the overall system.

Currently populated for **BlogPost** only. **Chatbot** and **Translation**
agents will be added when those features begin implementation.

---

## BlogPost — Parliament Debate Digest

Two independent agents, sharing one cache tier (S3 raw reports). Neither
agent uses embeddings — this is a deliberate budget decision, see
`ARCHITECTURE.md`.

### 1. Digest agent

Runs once per unique sitting date. Result is cached in DynamoDB
`DebateDigests` (no TTL — sittings don't change) and never regenerated.

**Model:** Amazon Nova Lite (`apac.amazon.nova-lite-v1:0`). Cheap, high
throughput, plenty of quality for summarization.

**Tools:**

- `list_topics(date: str) -> list[TopicMeta]`  (in `services/scraper.py`)
  - `SCRAPER_MODE=fixture`: reads `backend/fixtures/topics_{date}.json`.
    Returns `[]` if no sitting.
  - `SCRAPER_MODE=sprs`: dispatches to `services/scraper_sprs.py`, which
    calls `POST https://sprs.parl.gov.sg/search/searchResult` with the
    date range and paginates until all reports are collected.
  - Returns topic titles, source URLs, and format hint (`"html"`).
    **`speakers` is always `[]`** at this layer — SPRS's search endpoint
    doesn't include speaker names in the list view. The research agent
    fetches speakers via `getHansardTopic` when it fetches the report
    body (Phase 4 lazy-scrape).
  - **Does NOT fetch report bodies.** Report HTML is scraped lazily by
    the research agent (see below), keyed by the same `topic_id` for
    the S3 cache.

- `bedrock.summarize(prompt)`  (in `services/bedrock.py`)
  - Single Nova Lite call over topic titles + speakers.
  - Returns `{ summary, category_breakdown, interesting_topics }` inside
    a `<json>...</json>` block. Server-side wraps the response with
    `topic_count = len(topics)` and strips hallucinated `topic_id`s.

**Output written to** DynamoDB `DebateDigests` (PK `date`).

**Guardrails:**

- Never proactively scrape multiple dates in a batch — only on user request
  for a specific date.
- If the date had no sitting, return `{ error: "no_sitting" }` and do not
  write a digest row.
- The `interesting_topics` field must reference `topic_id` values that
  actually appear in `topics`. `agents/digest.py::_parse_digest_json`
  enforces this by filtering — fabricated IDs are dropped and logged.

### 2. Research agent

Runs per chat message. Session state is stored in DynamoDB `ChatSessions`
with a TTL of ~1 hour (refreshed on each message), so AWS auto-deletes
inactive sessions.

**Model:** Amazon Nova Pro (`apac.amazon.nova-pro-v1:0`) by default. Only
escalate from Nova Lite when the digest agent's output quality is
inadequate on Nova Lite for interactive Q&A.

**Contract — no embeddings, document blocks instead:**

1. Load session from DDB (`storage.get_session`) or create a fresh row
   in memory if none exists.
2. Load the digest for `date` (`storage.get_digest`). If missing or
   `error: "no_sitting"`, raise `ValueError` — the caller must
   `GET /debates/{date}` first. Build `{topic_id → topic_meta}` from
   `digest.topics`.
3. If the request's `topic_id` is present in the digest and not already
   in `topics_loaded`, append it. Unknown `topic_id`s are logged and
   ignored (no session pollution).
4. For each topic in `topics_loaded`: fetch report bytes from
   `storage.get_report(date, topic_id, ext)`. On miss, call
   `scraper.fetch_report(topic)` (SPRS `POST /search/getHansardTopic`)
   and `storage.put_report(...)` to cache. This is the **lazy-scrape**
   step — reports are fetched only when the user first asks about the
   topic.
5. Empty-doc guardrail: if no docs are attached (empty session, no
   valid `topic_id`), return a "pick a topic" reply **without calling
   Bedrock**. Log the turn to session and return.
6. Call `bedrock.chat_with_documents(SYSTEM_PROMPT, history, message, docs)`.
   `history` is plain-text `[{role, content: str}]`; `bedrock.py` places
   docs + `cachePoint` at **message 0** (see cache placement below), so
   the intra-session prompt cache reliably hits after turn 1.
7. Parse the `<grounded>false</grounded>` marker in the reply. Strip
   the marker from the visible reply (both the returned reply and what
   gets persisted to chat_history).
8. Mirror `bedrock`'s returned `kept_topic_ids` into
   `session.topics_loaded` (bedrock may have dropped the oldest topic
   if the 5/50K cap kicked in). Append user + assistant messages to
   `chat_history`. Write via `storage.put_session` (refreshes TTL).

**System prompt shape:**

```
You are a research assistant for Singapore Parliament debates. You will
answer questions using ONLY the attached debate report documents.

Rules:
- If the answer is present in the documents, cite the topic title and
  speaker where relevant.
- If the answer is NOT in the documents, output exactly the marker
  <grounded>false</grounded> at the end of your reply and say the report
  does not cover it.
- Do not answer from general knowledge. Do not speculate.
```

**Guardrails:**

- **`topics_loaded` cap: 5 topics OR 50K accumulated document tokens.**
  Whichever hits first triggers drop-oldest. Enforced in
  `services/bedrock.py`, not in the agent itself, so the cap is impossible
  to bypass from higher-level code.
- **Prompt caching MUST be enabled on all `document` blocks, and
  docs+cachePoint MUST live at message 0.** Placing them on the current
  turn's user message would rotate the cache prefix every turn and
  defeat the point. `bedrock.py::chat_with_documents` enforces the
  message-0 layout; `research.py` passes plain-text history in.
- **No shared / persistent vector index anywhere.** If a future feature
  needs cross-session retrieval, it goes through the S3 cache tier, not a
  vector store.
- **TTL is non-negotiable.** Any code path that writes a `ChatSessions`
  row must set/refresh `ttl` to `now + 3600`. No exceptions.
- If retrieval yields nothing (all `topics_loaded` empty on turn 1 because
  the user didn't pick a topic), return a helpful reply asking them to
  pick one — do not answer from general knowledge.

---

## Cross-agent rules (apply everywhere in the repo)

- **Default to Nova Lite** for any new LLM call. Escalate to Nova Pro only
  when a concrete quality issue is observed.
- **Never introduce an embedding step** — no `sentence-transformers`, no
  `torch`, no Bedrock Titan/Cohere embed model IDs. If retrieval feels
  necessary, the answer is "attach the document instead."
- **Every LLM call goes through `services/bedrock.py`.** No `boto3` client
  creation scattered across agent files — the caps, caching, and region
  config live in one place.
- **Log token usage** for every call (Bedrock's response includes it).
  Aggregate in CloudWatch so we can see cost drift.
