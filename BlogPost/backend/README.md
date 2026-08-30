# BlogPost Backend

Current state, layout, and local runbook for the Parliament Debate Digest
backend. Phase tracking lives in [`../../PROJECT_STATE.md`](../../PROJECT_STATE.md);
design rationale is in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md);
per-agent contracts in [`../../AGENTS.md`](../../AGENTS.md); repo rules for
future Claude sessions in [`../CLAUDE.md`](../CLAUDE.md).

---

## Status — Phase 3 complete

- **`GET /debates/{date}` is live.** Full flow: DDB cache check →
  fixture-backed topic list → Nova Lite summarize → JSON parse (drops
  fabricated `topic_id`s server-side) → DDB write → return. HTTP 404
  when a date had no sitting; no DDB row created for those.
- **`POST /debates/{date}/chat` still stubs** — Phase 4 wires the research
  agent.
- **AWS resources land via Terraform, not code.** The Terraform module at
  `../../terraform/` defines `DebateDigests` + `ChatSessions` (TTL on
  `ttl`) + `parl-debate-cache` bucket. Run `terraform apply` once before
  the first end-to-end test.
- **Local dev without AWS still works.** Set `USE_LOCAL_STUBS=1` to
  short-circuit DDB + S3 (they log and no-op). Bedrock still runs — the
  digest call costs ~$0.001.
- Phase 3 sanity checks (fixture load, prompt build, JSON parse
  including fabrication filter, no-sitting path) all pass. Uvicorn
  end-to-end smoke test is the user's responsibility since pypi is
  blocked in the sandbox.

---

## File layout

```
backend/
├── main.py                 FastAPI app + routes (digest wired, chat stubbed)
├── lambda_handler.py       Mangum wrapper (for Phase 6 Lambda deploy)
├── requirements.txt        Python deps — no torch, no sentence-transformers
├── fixtures/
│   ├── topics_2026-08-05.json      Hand-crafted sample sitting, 6 topics
│   └── metadata_2026-08-05.json    Title + youtube_url for the fixture date
├── services/
│   ├── bedrock.py          Nova Converse wrapper + session caps + cachePoint
│   ├── storage.py          DDB + S3 lazy wrappers + TTL + USE_LOCAL_STUBS
│   ├── scraper.py          SCRAPER_MODE dispatch (fixture / sprs)
│   └── scraper_sprs.py     Real SPRS httpx client (Phase 3.5b, LIVE)
└── agents/
    ├── digest.py           Digest agent (LIVE, fixture-backed)
    └── research.py         Research agent (stub — Phase 4)
```

| File | Role |
|---|---|
| [`main.py`](main.py) | FastAPI app. Four routes: `/`, `/health`, `/debates`, `/debates/{date}`, `/debates/{date}/chat`. `NotImplementedError` from the agents is caught here and converted to a stub payload so the API is fully callable in Phase 2. |
| [`lambda_handler.py`](lambda_handler.py) | Mangum ASGI-to-Lambda adapter. Used only when we ship the container image in Phase 6. |
| [`services/bedrock.py`](services/bedrock.py) | Sole owner of the `bedrock-runtime` client. `summarize()` for Nova Lite one-shots, `chat_with_documents()` for Nova Pro multi-turn with attached documents. **Enforces `MAX_TOPICS_PER_SESSION = 5` and `MAX_DOC_TOKENS_PER_SESSION = 50_000` drop-oldest**, and appends a `cachePoint` block after documents so Bedrock prompt caching kicks in. |
| [`services/storage.py`](services/storage.py) | DDB + S3 access. `put_session()` unconditionally refreshes `ttl` to `now + 3600s` — no upstream caller can forget it. `get_report()` swallows `NoSuchKey` → `None` so S3 misses are ergonomic. |
| [`services/scraper.py`](services/scraper.py) | Dispatch on `SCRAPER_MODE`. `fixture` reads `fixtures/topics_{date}.json` (metadata only, no report bytes). `sprs` delegates to `scraper_sprs.py` for both `list_topics` and `fetch_report`. |
| [`services/scraper_sprs.py`](services/scraper_sprs.py) | Real SPRS scraper. `POST /search/searchResult` for topic lists (paginated, advances by actual page size, terminates on `maxResult` or empty response). `POST /search/getHansardTopic` for per-topic HTML transcripts (wrapped in a minimal HTML envelope with title + speakers). httpx client with browser-like User-Agent, `SPRS_REQUEST_DELAY` throttle (0.5s default), single retry on 429/5xx. |
| [`agents/digest.py`](agents/digest.py) | `run_digest(date)` **live**. Cache check → topic list → prompt build → `bedrock.summarize` → JSON parse → strip fabricated topic_ids → `storage.put_digest` → return. Returns `{"error": "no_sitting"}` (and skips DDB write) if the date has no fixture / no sitting. |
| [`agents/research.py`](agents/research.py) | `run_chat(session_id, date, message, topic_id)` — raises `NotImplementedError` in Phase 2. Ships with the finalized `SYSTEM_PROMPT` and the `<grounded>false</grounded>` marker parser so Phase 4 only needs to wire the flow. |

---

## Run locally

The parent Python venv at `Roulette-Kaki/.venv` already has boto3. Install
the rest, then start uvicorn.

**Local mode (no DDB / S3, Bedrock still real):**

```bash
cd BlogPost/backend
../../.venv/bin/pip install -r requirements.txt
export USE_LOCAL_STUBS=1 SCRAPER_MODE=fixture AWS_REGION=ap-southeast-1
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

`GET /debates/2026-08-05` will hit Nova Lite for real (~$0.001) but
skip DDB/S3. Ideal for iterating on the digest prompt.

**Against real AWS (after `terraform apply`):**

```bash
cd ../../terraform && terraform init && terraform apply
cd ../BlogPost/backend
export AWS_REGION=ap-southeast-1     # unset USE_LOCAL_STUBS
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

First `GET /debates/2026-08-05` runs the full pipeline (~2s); second call
hits the DDB cache (~50ms).

Interactive Swagger UI: **http://localhost:8000/docs**.

---

## API surface (Phase 3)

| Method | Path | Returns |
|---|---|---|
| `GET`  | `/`                          | Endpoint directory (self-describing) |
| `GET`  | `/health`                    | `{"status": "ok", "phase": 3}` |
| `GET`  | `/debates`                   | Stub list; Phase 5+ will scan DDB. |
| `GET`  | `/debates/{date}`            | **Live digest.** `date` = `YYYY-MM-DD` (e.g. `2026-08-05`). Runs digest agent on cache miss; returns HTTP 404 `{"detail":{"error":"no_sitting", ...}}` when no fixture / no sitting exists. |
| `POST` | `/debates/{date}/chat`       | Still stub echo reply. Body: `{"message": "...", "session_id"?, "topic_id"?}`. Phase 4 wires the research agent. |

Sample:

```bash
curl -X GET  'http://127.0.0.1:8000/debates/2026-08-05'
curl -X POST 'http://127.0.0.1:8000/debates/2026-08-05/chat' \
  -H 'Content-Type: application/json' \
  -d '{"message": "hello"}'
```

---

## Guardrails enforced in code

These live in `services/*.py` so higher layers can't bypass them:

- **Session-scope caps** — `services/bedrock.py` drops oldest documents at
  5 topics or 50K accumulated document tokens (whichever hits first). Cost
  ceiling per turn is set here.
- **DDB TTL** — `services/storage.py::put_session` always writes
  `ttl = now + 3600`, refreshed on every message write. No code path can
  create a session row without a TTL.
- **Prompt caching** — `services/bedrock.py::chat_with_documents` appends
  a `cachePoint` block after documents. Repeat turns within a session hit
  the cache instead of paying full input-token price for the document body.
- **Lazy AWS clients** — all `boto3.client(...)` / `boto3.resource(...)`
  calls sit inside `_client()` / `_ddb()` / `_s3()` singletons, so importing
  a module never talks to AWS.
- **Single Bedrock client** — nothing outside `services/bedrock.py` may
  build a `bedrock-runtime` client. This is how the caps + caching stay
  enforceable.

---

## What Phase 3 is deliberately NOT

- No embeddings. No `sentence-transformers`, no `torch`, no vector store.
  See [`../CLAUDE.md`](../CLAUDE.md) — hard constraint by design.
- **No real SPRS scraping yet.** `SCRAPER_MODE=fixture` reads from disk;
  Phase 3.5 will implement `SCRAPER_MODE=sprs` after an instrumented
  Playwright run captures the site's actual API surface.
- **No lazy report fetching yet.** `scraper.fetch_report()` still raises
  — that's a Phase 4 concern, since only the research agent needs report
  bytes.
- No frontend integration — that's Phase 5.
- Not deployed — code runs locally; Phase 6 packages the Lambda image.

---

## Environment variables (all optional)

| Var | Default | Meaning |
|---|---|---|
| `AWS_REGION` | `ap-southeast-1` | Bedrock + DDB + S3 region. Lambda injects this automatically at deploy time. |
| `DIGESTS_TABLE` | `DebateDigests` | DDB table for cached digests. |
| `SESSIONS_TABLE` | `ChatSessions` | DDB table for chat sessions (TTL). |
| `CACHE_BUCKET` | `parl-debate-cache` | S3 bucket for raw report bytes. |
| `SCRAPER_MODE` | `fixture` | `fixture` reads `backend/fixtures/topics_{date}.json`. `sprs` uses the real SPRS API (see `services/scraper_sprs.py`). |
| `SPRS_REQUEST_DELAY` | `0.5` | Minimum seconds between SPRS calls (throttle). Only matters when `SCRAPER_MODE=sprs`. |
| `USE_LOCAL_STUBS` | *unset* | Set to `1` to short-circuit DDB + S3 (they log and no-op). Bedrock still runs. Use for iterating without AWS resources. |

Note: if your shell has `AWS_REGION=us-east-1` set, that overrides the
default at runtime and Bedrock calls will 404 on the Singapore model IDs.
`export AWS_REGION=ap-southeast-1` before running against real AWS.

---

## What's next — Phase 3.5c (pre-populate demo digests) or Phase 4 (research agent)

Independent — do either or both.

**Phase 3.5c — one-time demo prep.** Now that `SCRAPER_MODE=sprs` works,
warm the DDB cache with 5-10 real sitting digests so demo day doesn't
depend on live scraping. Full runbook in
[`../../scripts/README.md`](../../scripts/README.md). TL;DR:

```bash
cd terraform && terraform apply         # if not already done
cd ../scripts
export AWS_REGION=<your region> SCRAPER_MODE=sprs
../.venv/bin/python prepopulate_digests.py --dates 2026-08-05 2026-07-15 ...
```

Cost: ~$0.001 per date. First real hit against SPRS also verifies the
scraper end-to-end (whether Imperva accepts our User-Agent, etc.).

**Phase 4 — research agent.** See AGENTS.md → Research agent contract.
Everything upstream is in place — `services/bedrock.py::chat_with_documents`
enforces caps + prompt caching, `services/storage.py::{get,put}_session`
handles TTL, `services/scraper.py::fetch_report` returns HTML bytes for
Nova `document` blocks. Just wire the flow in `agents/research.py`.
