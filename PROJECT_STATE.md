# Project state — Roulette-Kaki

Last updated: 2026-08-30 (Phase 4 complete — research agent + chat endpoint live)

Single source of truth for what's built, what's next, and what's blocked.

---

## Features

| Feature | Status | Notes |
|---|---|---|
| BlogPost — Parliament Debate Digest | **Phase 4 complete — chat endpoint live.** `POST /debates/{date}/chat` wires the research agent: session-state DDB row (TTL 1h), lazy S3 report cache, Nova Pro Converse with document blocks at message 0 for stable prompt caching. Frontend (Phase 5) is next. | See `ARCHITECTURE.md`, `AGENTS.md`, `scripts/README.md`. |
| Chatbot                              | Not started — stub directories only  | `Chatbot/backend`, `Chatbot/frontend` exist but are empty. |
| Translation                          | Not started — empty stub file        | `Translation/main.py` is empty. |

---

## BlogPost — implementation phases

Each phase is demoable on its own. Phase 3.5 (real SPRS scraper) and
Phase 4 (research agent) are next.

- [x] **Phase 0** — Original design captured in `Blog_Summary.txt` (kept for
      reference).
- [x] **Phase 1 — Docs (budget-revised plan).** `ARCHITECTURE.md`,
      `AGENTS.md`, `PROJECT_STATE.md`, `BlogPost/CLAUDE.md` populated;
      region typo in `BlogPost/backend/main.py` fixed.
- [x] **Phase 2 — Backend skeleton.** FastAPI app with three endpoints
      (stub responses). `services/bedrock.py` wraps Nova Converse and
      enforces the 5-topic / 50K-token caps + `cachePoint` block.
      `services/storage.py` wraps DDB + S3 lazily (TTL enforced on
      `put_session`). `services/scraper.py`, `agents/digest.py`,
      `agents/research.py` are stubs pointing at Phase 3 / Phase 4.
      `lambda_handler.py` wraps the app in Mangum for later deploy.
      Uvicorn smoke-test verified locally on 2026-08-30. **Full backend
      state, layout, runbook, and API surface lives in
      [`BlogPost/backend/README.md`](BlogPost/backend/README.md).**
- [x] **Phase 3 — Digest agent + Terraform infra (fixture-first).**
      `services/scraper.py::list_topics` is fixture-backed (reads
      `backend/fixtures/topics_{date}.json`). `agents/digest.py::run_digest`
      is fully implemented: cache check → topic scrape → Nova Lite
      summarize → JSON parse (drops fabricated `topic_id`s) → DDB write.
      `services/storage.py` gains `USE_LOCAL_STUBS=1` short-circuit for
      local dev without AWS creds. `main.py::get_debate` returns real
      digests with an HTTP 404 for no-sitting dates. Terraform module at
      `terraform/` defines `DebateDigests`, `ChatSessions` (TTL on `ttl`),
      and `parl-debate-cache` bucket with public access blocked.
- [🚧] **Phase 3.5 — Real SPRS scraper.** Split across two turns because
      the scraper can't be written blind.
      - [x] **3.5a — Recorder + scaffolding.** Playwright recorder,
        batch pre-populate script, docs.
      - [x] **3.5b — Real SPRS scraper.** `services/scraper_sprs.py`
        talks to SPRS via pure httpx (no runtime Playwright needed —
        the API is clean JSON). Two endpoints in use:
        `POST /search/searchResult` (paginated topic list with maxResult
        gate + advance-by-actual-page-size) and
        `POST /search/getHansardTopic` (per-topic HTML transcript,
        wrapped in a minimal HTML envelope for Nova's `document`
        blocks). `services/scraper.py` dispatches on `SCRAPER_MODE`.
        Sanity-tested against 3 mocked pagination scenarios
        (server-capped small pages, full-page, empty). Rate-limited
        with `SPRS_REQUEST_DELAY` (0.5s default) + one retry on 429/5xx.
      - [ ] **3.5c — Real showcase digests in DDB.** Run
        `scripts/prepopulate_digests.py --dates <5-10 recent sittings>
        --config` with `SCRAPER_MODE=sprs` against real AWS. Not blocking
        Phase 4; a demo-prep task.
- [x] **Phase 4 — Research agent with document blocks.**
      `agents/research.py::run_chat` implements the full flow: load/create
      session → validate `topic_id` against digest → S3 cache hit or
      lazy-scrape → build Nova `document` blocks → Nova Pro Converse
      with docs+cachePoint at **message 0** for cache-stable prefix
      across turns → parse `<grounded>false</grounded>` marker →
      persist chat_history + TTL refresh. `main.py::chat` returns
      HTTP 400 on missing digest and 503 in fixture mode (no report
      bytes). `bedrock.py::chat_with_documents` refactored to place
      docs at message 0 (was: current turn). 7 in-sandbox tests cover
      first turn, follow-up cache-stable prefix, no-topic guardrail
      (no Bedrock call), fabricated topic_id, 5-topic cap, grounded
      marker parse+strip, missing-digest ValueError.
- [ ] **Phase 5 — Frontend.** Vite + React scaffold, blog feed, detail page
      with chat + topic dropdown.
- [ ] **Phase 6 — Package + deploy.** Dockerfile on Lambda Python base image,
      deploy to Lambda Function URL. Frontend to S3 + CloudFront.

---

## Key decisions locked in

- **LLM:** Amazon Nova Lite (digest) and Nova Pro (chat) via Bedrock in
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
[`BlogPost/backend/README.md`](BlogPost/backend/README.md).

**Local, no AWS (fastest for iteration):**

```bash
cd BlogPost/backend
../../.venv/bin/pip install -r requirements.txt
export USE_LOCAL_STUBS=1 SCRAPER_MODE=fixture AWS_REGION=ap-southeast-1
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

`GET /debates/2026-08-05` hits the fixture + Nova Lite for real (needs
Bedrock access), but DDB/S3 are stubbed. ~$0.001 per digest.

**End-to-end against real AWS:**

```bash
cd terraform && terraform init && terraform apply    # one-time
cd ../BlogPost/backend
export AWS_REGION=ap-southeast-1  # unset USE_LOCAL_STUBS
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

First `GET /debates/2026-08-05` scrapes fixture + summarizes + writes to
DDB (~2s). Second call hits the DDB cache (~50ms).

---

## Open questions to resolve during implementation

- ~~Does SPRS expose a plain JSON API?~~ **Answered 2026-08-30:** No
  discoverable REST endpoints via URL guessing — SPA hides the API.
  Phase 3.5 needs an instrumented Playwright run to capture the real
  API traffic before we decide `httpx` vs. Playwright for production.
- What format does SPRS serve reports in — PDF, HTML, both? Determines the
  file extension on the S3 cache key and whether we need any format
  massaging before handing to Nova. Resolves during Phase 3.5.
- Nova Pro's document-block behavior on very long PDFs (>50 pages) —
  confirm quality is acceptable before Phase 4 signoff, otherwise fall back
  to Nova Lite pre-summarization per topic.

---

## Non-goals for the hackathon

- Multi-user auth. Sessions are anonymous UUIDs.
- Cross-language support (Malay / Chinese / Tamil reports). English only.
- Historical backfill of the SPRS archive. Purely lazy on user click.
- A persistent vector index. Explicitly ruled out — see `ARCHITECTURE.md`.
