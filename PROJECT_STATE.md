# Project state — Roulette-Kaki

Last updated: 2026-08-30 (Phase 2 complete)

Single source of truth for what's built, what's next, and what's blocked.

---

## Features

| Feature | Status | Notes |
|---|---|---|
| BlogPost — Parliament Debate Digest | **Phase 2 complete — backend skeleton in place, no AWS resources created yet** | See `ARCHITECTURE.md`, `AGENTS.md`. Budget-revised plan approved. |
| Chatbot                              | Not started — stub directories only  | `Chatbot/backend`, `Chatbot/frontend` exist but are empty. |
| Translation                          | Not started — empty stub file        | `Translation/main.py` is empty. |

---

## BlogPost — implementation phases

Each phase is demoable on its own. Phase 3 is next.

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
- [ ] **Phase 3 — Digest agent + SPRS scraper.** `scrape_debate_list`,
      `summarize_and_stats`, S3 write of raw report bytes per topic, DDB
      write of the digest. Test locally against real DDB + S3.
- [ ] **Phase 4 — Research agent with document blocks.** Load
      `topics_loaded` documents from S3, attach as Converse `document`
      blocks with prompt-cache flags, call Nova Pro, parse `grounded`
      marker, persist chat history + TTL refresh.
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

```bash
cd BlogPost/backend
../../.venv/bin/pip install -r requirements.txt
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Then:
- `GET http://localhost:8000/health` → `{"status": "ok", "phase": 2}`
- `GET http://localhost:8000/debates` → stub list of one debate
- `GET http://localhost:8000/debates/2026-08-05` → stub digest
- `POST http://localhost:8000/debates/2026-08-05/chat` with body
  `{"message": "hi"}` → stub echo reply

None of these hit AWS in Phase 2 — the agents raise `NotImplementedError`
and the handlers return stub payloads.

---

## Open questions to resolve during implementation

- Does SPRS expose a plain JSON API that returns per-topic report text? If
  yes, Playwright is not needed. If no, add Playwright to the Lambda
  container (image size roughly doubles but still fits).
- What format does SPRS serve reports in — PDF, HTML, both? Determines the
  file extension on the S3 cache key and whether we need any format
  massaging before handing to Nova.
- Nova Pro's document-block behavior on very long PDFs (>50 pages) —
  confirm quality is acceptable before Phase 4 signoff, otherwise fall back
  to Nova Lite pre-summarization per topic.

---

## Non-goals for the hackathon

- Multi-user auth. Sessions are anonymous UUIDs.
- Cross-language support (Malay / Chinese / Tamil reports). English only.
- Historical backfill of the SPRS archive. Purely lazy on user click.
- A persistent vector index. Explicitly ruled out — see `ARCHITECTURE.md`.
