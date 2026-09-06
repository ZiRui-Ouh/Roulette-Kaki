# Architecture — Roulette-Kaki

Roulette-Kaki was built for the SimplifyNext / Agentic AI Hackathon. All
features — Parliament Debate Digest, Policy Query Agent, search stack,
translation, flashcards — ship in one FastAPI service under
[`application/backend/`](application/backend/) and one React SPA under
[`application/frontend/`](application/frontend/). The pre-consolidation
folders `BlogPost/`, `Chatbot/`, `Translation/`, and `search_agent/` no
longer exist.

The single hard constraint that shapes every decision: **$30 total spend
across all AWS services and LLM calls for the full hackathon.** If a design
choice makes cost proportional to corpus size instead of user interaction
volume, it's wrong.

---

## Parliament Debate Digest

A blog-style feed where each post represents one Singapore Parliament sitting
day. Users can drill into a date, see an AI-generated digest of what was
debated, and chat with a research agent grounded in the actual report text.

### Data flow at a glance

```
┌──────────┐   GET /debates          ┌──────────────────────────┐
│ Frontend │────────────────────────>│ Lambda (FastAPI+Mangum)  │
│  React   │<──── blog feed ─────────│  behind Function URL     │
└──────────┘                         └──────────────────────────┘
      │                                   │           │
      │ GET /debates/{date}               │           │
      ▼                                   ▼           ▼
┌──────────────┐          ┌────────────────────┐  ┌────────────┐
│ Digest agent │─miss────>│ SPRS scraper       │  │ DynamoDB   │
│ (Nova Lite)  │          │ (JSON API first)   │  │ Digests    │
└──────────────┘          └────────────────────┘  └────────────┘
      │                          │                     ▲
      │ hit                      ▼                     │
      └─────────────────>┌────────────────┐            │
                        │ S3 raw report  │───────────>─┘
                        │ cache (PDF/HTML)│
                        └────────────────┘
                                 ▲
                                 │ POST /debates/{date}/chat
                                 │
                        ┌────────────────┐    ┌──────────────┐
                        │ Research agent │───>│ DynamoDB     │
                        │ (Nova Pro +    │    │ Sessions     │
                        │  document blocks)   │ (TTL=1h)     │
                        └────────────────┘    └──────────────┘
```

### Model tier

| Job | Model | Bedrock ID | Price (in / out per 1M tok) |
|---|---|---|---|
| Digest summarization | Amazon Nova Lite | `apac.amazon.nova-lite-v1:0` | $0.06 / $0.24 |
| Chat / research | Amazon Nova Pro   | `apac.amazon.nova-pro-v1:0`  | $0.80 / $3.20 |
| Embeddings        | **none — deleted from design** | — | $0 |

Region: `ap-southeast-1`. Default to Nova Lite; only escalate to Nova Pro
when a concrete quality problem is observed on Nova Lite.

### Why no embeddings tier

The obvious way to do RAG over parliamentary reports is chunk → embed →
cosine retrieve. We are not doing that. Nova's Converse API accepts
`document` content blocks (PDF / HTML / DOCX / MD / TXT) natively, with a
300K-token context window. So the research agent works by:

1. Caching the raw report bytes in S3 keyed `{date}/{topic_id}.{ext}` —
   populated **lazily** by the research agent on first mention of a
   topic (not proactively at digest time).
2. On each chat turn, attaching the documents the session has "loaded" as
   `document` blocks in the Converse call.
3. Enabling Bedrock prompt caching on those blocks so turns 2..N in the same
   session skip re-billing the document bodies.

This deletes an entire subsystem (chunker + embedder + storage +
retrieval), keeps the Lambda image tiny (~100MB, no `torch`), and
eliminates retrieval-miss failure modes — the model sees the full document.

### Session cost bounds

Per-turn cost is bounded by total loaded-document size. Enforce in
`services/bedrock.py`:

- Cap `topics_loaded` at 5 per session, **or**
- Cap accumulated document tokens at 50K per session (drop-oldest above that).

Sanity math (Nova Pro, one 3K-token topic loaded):

| State                          | Cost / turn |
|--------------------------------|-------------|
| First turn (cache miss)        | ~$0.006     |
| Follow-up (doc cache hit)      | ~$0.002     |
| 5 topics loaded, cache miss    | ~$0.015     |
| 5 topics loaded, cache hit     | ~$0.004     |

At 1,000 demo chat turns, projected LLM spend is well under $10 of the $30
budget. Everything non-LLM sits inside AWS's permanent free tier at
hackathon volume.

### Storage

- **DynamoDB `DebateDigests`** (PK `date`, no TTL). Cached digest per sitting.
  ```
  { date, title, youtube_url, summary, topic_count,
    category_breakdown, interesting_topics,
    topics: [{ topic_id, title, speakers, source_url, s3_key }, ...],
    scraped_at }
  ```

- **DynamoDB `ChatSessions`** (PK `session_id`, TTL enabled, ~1h, refreshed
  on each message). Shrunk vs. the original plan — no chunks, no embeddings:
  ```
  { session_id, date, topics_loaded: [topic_id, ...],
    chat_history: [{ role, content, timestamp }, ...],
    created_at, ttl }
  ```

- **S3 bucket `parl-debate-cache`** — raw report bytes keyed
  `{date}/{topic_id}.{pdf|html}`. Shared across sessions. This is the tier
  that stops us re-scraping SPRS for the same topic twice.

### Compute

- **Primary: Lambda container image.** Python 3.11 base
  (`public.ecr.aws/lambda/python:3.11`) + FastAPI + Mangum + `httpx` +
  `boto3`. Exposed via a **Lambda Function URL** — no API Gateway.
- **Fallback: ECS Fargate task** running the same image if Lambda's 15-min
  hard limit becomes an issue (e.g. first-scrape of an unusually large
  sitting) or if we want an always-warm endpoint for the demo.

### Scraping

SPRS (https://sprs.parl.gov.sg/search/#/home) is an Angular SPA with hash
routing. Two-tier approach:

1. **First choice:** sniff the browser's Network tab, find the JSON API, hit
   it with `httpx`. Cheap and reliable.
2. **Fallback only:** Playwright inside the Lambda container image (or a
   Fargate task). Add only if the JSON approach fails.

Rate-limit, descriptive User-Agent, respect `robots.txt`. Not costly to
be a good citizen because each `(date, topic)` scrapes exactly once thanks
to the S3 cache.

### API contracts

- `GET /debates` — paginated blog feed.
- `GET /debates/{date}` — full digest for one date. Cache-through: runs
  digest agent on miss; returns `{ error: "no_sitting" }` if none held.
- `POST /debates/{date}/chat` — body `{ session_id, message, topic_id? }`;
  response `{ session_id, reply, topics_used, grounded }`. `grounded: false`
  means retrieval / the attached documents don't contain the answer, so
  don't trust the reply.

### Frontend

Vite + React, static-built, hosted on S3 + CloudFront (free tier). Two
views:

1. **Feed** — one card per sitting date: YouTube livestream embed + title.
2. **Detail** — full digest + chat panel. Chat panel has a topic dropdown
   sourced from the digest's `topics` list so the user tells us which report
   to attach (avoids an extra LLM classifier round-trip).

---

## Policy Query Agent + Search Stack

See [`AGENTS.md`](AGENTS.md) for full agent contracts. Data flow:

```
┌──────────┐   POST /query           ┌──────────────────────────┐
│ Frontend │────────────────────────>│ Lambda (FastAPI+Mangum)  │
│  React   │<──── grounded answer ───│  behind Function URL     │
└──────────┘                         └──────────────────────────┘
                                          │
                                          ▼
                                   ┌──────────────────┐
                                   │ agents/query.py  │
                                   │ (agentic loop,   │
                                   │  Nova Lite tools)│
                                   └──────────────────┘
                                          │  search_policy tool call
                                          ▼
                                   ┌──────────────────────────────┐
                                   │ services/search_service.py   │
                                   │   → agents/search.py         │
                                   │   → services/webscraper.py   │
                                   │      (rank, verify, dedupe)  │
                                   └──────────────────────────────┘
                                          │
                                          ▼
                                   Official .gov.sg + community forums
```

The Policy Query Agent runs on Nova Lite (`converse_with_tools`), the
search stack synthesizes with the same model, and results feed the final
grounded answer with strict category separation (Singles vs Families,
BTO vs Resale, current vs historical).

## Translation + Flashcards

- `services/translation.py::translate_to_english` normalizes incoming
  Chinese/Malay/Tamil/Singlish questions to English before Query Agent
  routing. Uses Nova Lite plus MERaLiON for Singlish/audio.
- `services/meralion.py` provides ASR for the `POST /transcribe` route.
- `agents/flashcards.py` generates study flashcards from digest content.

All three sit inside the same FastAPI app — no separate deploys, no
cross-service network hops.
