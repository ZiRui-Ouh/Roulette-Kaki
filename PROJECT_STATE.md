# Project state — Roulette-Kaki

Last updated: 2026-09-06 (Cleanup + backend consolidation complete —
`BlogPost/`, `Chatbot/`, `Translation/`, `search_agent/` deleted;
`query_agent/` renamed to `application/`; search stack merged into
`application/backend/`. Next up: AWS migration + Terraform.)

Single source of truth for what's built, what's next, and what's blocked.

---

## Repository layout

| Folder | Purpose |
|---|---|
| [`application/backend`](application/backend) | FastAPI service — Query Agent + Parliament Debate Digest + web-search stack + translation + flashcards. Single Lambda deploy target. |
| [`application/frontend`](application/frontend) | React 19 + Vite 8 + Tailwind 4 SPA. Chat UI, sitting feed, digest/chat, policy article view, flashcard drawer, i18n. |
| [`terraform`](terraform) | Terraform module for AWS resources (`DebateDigests` + `ChatSessions` DDB tables, `parl-debate-cache` S3 bucket, Lambda + CloudFront next). |
| [`scripts`](scripts) | Batch helpers, notably `prepopulate_digests.py` for warming the DDB cache before demo day. |
| [`scratch`](scratch) | One-off debugging scripts (`trace_opinion_query.py`) — not part of the deploy. |

---

## Features (unified backend)

| Feature | Status | Notes |
|---|---|---|
| Policy Query Agent (`POST /query`) | **Live.** Agentic loop over official + community sources, grounded Nova Lite answer, source citation, no cross-category number bleed. | See `AGENTS.md` § Query Agent. |
| Parliament Debate Digest (`GET /debates/{date}`) | **Live.** Cache-check DDB → fixture/SPRS topics → Nova Lite summarize → cached JSON. 404 on no sitting. | See `AGENTS.md` § Digest. |
| Debate Chat (`POST /debates/{date}/chat`) | **Live.** Nova Pro with attached report documents, prompt-cached, TTL-1h sessions. Web-fallback when ungrounded. | See `AGENTS.md` § Research/Chat. |
| Sitting Feed (`GET /sittings`) | **Live.** YouTube Data API v3 `playlistItems.list` → sitting cards. Curated fallback if API key missing. | Multi-language dedup keeps English preferred. |
| Web-Search Stack (`agents/search.py` + `services/webscraper.py`) | **Live.** Consolidated from former `search_agent/`. In-process `gather_and_search`; retains `SEARCH_AGENT_URL` HTTP fallback for future split. | Ranks official > community, extracts dates + applicability, detects conflicts. |
| Translation (`POST /translate`) | **Live.** Nova + MERaLiON for English/Chinese/Malay/Tamil/Singlish. `TranslatedInput` preserves markdown + key points. | Consolidated from former `Translation/` folder. |
| Audio Transcription (`POST /transcribe`) | **Live.** MERaLiON ASR for Singlish/audio. | |
| Flashcards | **Live.** Generate flashcards from digest content. | `agents/flashcards.py`. |

---

## Implementation phases

- [x] **Phase 0-3** — Original design, backend skeleton, digest agent + Terraform infra (fixture-first).
- [x] **Phase 3.5** — Real SPRS scraper (httpx, no runtime Playwright). Rate-limited with `SPRS_REQUEST_DELAY` + one retry on 429/5xx.
- [ ] **Phase 3.5c** — Real showcase digests in DDB (`scripts/prepopulate_digests.py --dates ...` with `SCRAPER_MODE=sprs`). Demo-prep task, not a blocker.
- [x] **Phase 4** — Research agent with document blocks. Nova Pro Converse with docs+cachePoint at message 0 for cache-stable prefix.
- [x] **Phase 5** — Frontend scaffold (Vite + React + TypeScript + Tailwind), feed + detail pages, localStorage session persistence.
- [x] **Phase 5.1** — YouTube-driven feed with English-preferred dedup.
- [x] **Phase 5.2** — YouTube Data API v3 for full pagination.
- [x] **Phase 5.5** — Backend consolidation. Merged `BlogPost/backend/` and `search_agent/backend/` into `application/backend/`. Reconciled `bedrock.py` (query_agent superset kept), replaced importlib bridges with direct imports, moved 2825-line `webscraper.py` and 382-line `agents/search.py` in place. Deleted `BlogPost/`, `Chatbot/`, `Translation/`, `search_agent/`. Renamed `query_agent/` → `application/`. `application/frontend/src/session.ts` retains the `query_agent:messages` localStorage key for user-history compatibility.
- [ ] **Phase 6 — AWS migration.** Dockerfile on Lambda Python base image, deploy to Lambda Function URL. Frontend to S3 + CloudFront. Terraform module extended with Lambda + CloudFront resources.

---

## Key decisions locked in

- **LLM:** Amazon Nova Lite (digest / query) and Nova Pro (chat) via Bedrock in
  `ap-southeast-1`. See `ARCHITECTURE.md` for cost math.
- **Embeddings:** none — deleted from the design. Documents are attached to
  Nova Converse calls as `document` blocks with prompt caching.
- **Compute:** Lambda container image via Function URL. ECS Fargate as
  fallback if Lambda limits bite.
- **Storage:** DynamoDB (`DebateDigests`, `ChatSessions` with TTL) + S3
  (`parl-debate-cache`).
- **Budget:** $30 total. Session-scope caps (5 topics or 50K tokens) enforced
  in `services/bedrock.py`.

---

## Running the backend locally

Two modes. Full runbook and env-var reference live in
[`application/backend/README.md`](application/backend/README.md).

**Local, no AWS (fastest for iteration):**

```bash
cd application/backend
../../.venv/bin/pip install -r requirements.txt
export USE_LOCAL_STUBS=1 SCRAPER_MODE=fixture AWS_REGION=ap-southeast-1
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

`GET /debates/2026-08-05` hits the fixture + Nova Lite for real (needs
Bedrock access), but DDB/S3 are stubbed. ~$0.001 per digest.

**End-to-end against real AWS:**

```bash
cd terraform && terraform init && terraform apply    # one-time
cd ../application/backend
export AWS_REGION=ap-southeast-1  # unset USE_LOCAL_STUBS
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

First `GET /debates/2026-08-05` scrapes fixture + summarizes + writes to
DDB (~2s). Second call hits the DDB cache (~50ms).

---

## Open questions to resolve during implementation

- What format does SPRS serve reports in — PDF, HTML, both? Determines the
  file extension on the S3 cache key and whether we need any format
  massaging before handing to Nova. Resolves during 3.5c.
- Nova Pro's document-block behavior on very long PDFs (>50 pages) —
  confirm quality is acceptable before Phase 6 signoff, otherwise fall back
  to Nova Lite pre-summarization per topic.

---

## Non-goals for the hackathon

- Multi-user auth. Sessions are anonymous UUIDs.
- Historical backfill of the SPRS archive. Purely lazy on user click.
- A persistent vector index. Explicitly ruled out — see `ARCHITECTURE.md`.
