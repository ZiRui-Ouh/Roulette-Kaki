# CLAUDE.md — BlogPost feature

Repo-level rules for future Claude sessions working in this feature. Read
`../ARCHITECTURE.md`, `../AGENTS.md`, and `../PROJECT_STATE.md` for the
full design; the rules below are the load-bearing bits you must not violate.

**Current progress and per-file runbook live in
[`backend/README.md`](backend/README.md) — read it before editing anything
under `backend/`.** It's the source of truth for which phase is done, which
files are still stubs, and what the next concrete step is.

## Hard budget rule

**$30 total spend across the entire hackathon** — Bedrock, Lambda, S3,
DynamoDB, everything. Every design decision is subordinate to this.

If a suggestion increases cost proportional to *corpus size* rather than
*user interaction volume*, it's wrong. Push back on it.

## Model choices

- **Digest work → Amazon Nova Lite** (`apac.amazon.nova-lite-v1:0`).
- **Interactive chat → Amazon Nova Pro** (`apac.amazon.nova-pro-v1:0`).
- **Default to Nova Lite for anything new.** Only reach for Nova Pro when a
  concrete quality problem is observed on Nova Lite for that specific
  workload.
- Region is **`ap-southeast-1`** (Singapore). The original stub had a typo
  `uap-southeast-1` — fixed.

## Do NOT introduce an embeddings tier

The chat agent works via Bedrock Converse `document` content blocks, not
retrieval-augmented generation over a vector index. This is a deliberate,
approved decision.

- No `sentence-transformers`.
- No `torch`.
- No Bedrock Titan / Cohere embedding model IDs.
- No pgvector / OpenSearch / Chroma / FAISS.

If you find yourself reaching for retrieval, the correct answer is "attach
the raw document as a `document` block instead." The 300K-token context
window handles it.

## Session-scope caps (must be enforced in `services/bedrock.py`)

To keep per-turn chat cost bounded:

- **Cap `topics_loaded` at 5 topics per session**, OR
- **Cap accumulated document tokens at 50K per session** — whichever hits
  first, drop-oldest above that.

The cap lives in `services/bedrock.py`, not in the agent code, so it
cannot be bypassed from higher layers.

## Other non-negotiables

- **`ChatSessions` DDB rows must have a `ttl` attribute set** to
  `now + 3600`, refreshed on every message. This is what stops runaway
  storage from long-tail sessions.
- **Bedrock prompt caching MUST be enabled on `document` blocks.** This is
  what makes Nova Pro affordable across multi-turn sessions.
- **Never bulk-scrape** the SPRS archive. Scraping happens lazily, on user
  click, and the S3 cache keyed `{date}/{topic_id}` ensures each pair is
  scraped exactly once.
- **All LLM calls go through `services/bedrock.py`.** No scattered `boto3`
  client creation.

## When in doubt

Consult `Blog_Summary.txt` at the project root for the original design
brief, and `../ARCHITECTURE.md` for the current design. The revised plan
lives at `~/.claude/plans/linked-giggling-lampson.md`.
