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
  - Phase 3: reads `backend/fixtures/topics_{date}.json`. Returns `[]` if
    no sitting.
  - Phase 3.5: swaps in real SPRS. Recon on 2026-08-30 showed SPRS is an
    Angular SPA with no discoverable REST endpoints — first pass will use
    Playwright instrumented with `page.on("request")` to capture the real
    API traffic, then decide whether to fall back to `httpx`.
  - Returns topic titles, speakers, source URLs, and format hint.
  - **Does NOT fetch report bodies.** Report PDFs/HTML are scraped
    lazily by the research agent (see below), keyed by the same
    `topic_id` for the S3 cache.

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

1. Read the session's `topics_loaded` list from DynamoDB.
2. If the current message has a `topic_id` field and it isn't already in
   `topics_loaded`, append it (subject to the caps below).
3. For each topic in `topics_loaded`, fetch its cached report bytes from
   S3 via `storage.get_report(date, topic_id, ext)`. On miss, call
   `scraper.fetch_report(topic)` to pull the report from SPRS, then
   `storage.put_report(...)` to cache it under `{date}/{topic_id}.{ext}`
   before proceeding. This is the **lazy-scrape** step — reports are
   fetched only when the user actually asks about the topic, not
   proactively at digest time.
4. Call Bedrock Converse with:
   - `system` — grounding prompt (see below).
   - `messages` — prior `chat_history` + current user message.
   - `document` blocks — one per topic in `topics_loaded`, marked as
     cacheable via Bedrock's prompt cache flags.
5. Parse the response:
   - Extract `reply` (assistant text).
   - Extract `grounded: bool` — the model is instructed to output a
     structured marker (e.g. an XML tag) when the answer isn't in the
     attached documents; parse that marker.
   - `topics_used` = the `topics_loaded` list at the time of the call.
6. Append user + assistant messages to `chat_history`, refresh TTL, write
   back to DynamoDB.

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
- **Prompt caching MUST be enabled on all `document` blocks.** This is
  what keeps Nova Pro affordable across a multi-turn session.
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
