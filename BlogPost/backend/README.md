# BlogPost Backend

Current state, layout, and local runbook for the Parliament Debate Digest
backend. Phase tracking lives in [`../../PROJECT_STATE.md`](../../PROJECT_STATE.md);
design rationale is in [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md);
per-agent contracts in [`../../AGENTS.md`](../../AGENTS.md); repo rules for
future Claude sessions in [`../CLAUDE.md`](../CLAUDE.md).

---

## Status — Phase 2 complete

- All three endpoints (`GET /debates`, `GET /debates/{date}`,
  `POST /debates/{date}/chat`) respond with **stub payloads**.
- **Zero AWS resources created** — every `boto3` client is lazily built
  inside a function, and no `.converse` / `.put_item` / `.put_object` call
  has ever run. `agents/digest.py::run_digest` raises `NotImplementedError`
  before touching DynamoDB, so hitting `/debates/{date}` locally works
  without AWS credentials.
- Uvicorn `--reload` local dev loop is verified working (user smoke-tested
  2026-08-30).

---

## File layout

```
backend/
├── main.py                 FastAPI app + routes + stub responses
├── lambda_handler.py       Mangum wrapper (for Phase 6 Lambda deploy)
├── requirements.txt        Python deps — no torch, no sentence-transformers
├── services/
│   ├── bedrock.py          Nova Converse wrapper + session caps + cachePoint
│   ├── storage.py          DDB + S3 lazy wrappers + TTL enforcement
│   └── scraper.py          SPRS interface (stub — Phase 3)
└── agents/
    ├── digest.py           Digest agent (stub — Phase 3)
    └── research.py         Research agent (stub — Phase 4)
```

| File | Role |
|---|---|
| [`main.py`](main.py) | FastAPI app. Four routes: `/`, `/health`, `/debates`, `/debates/{date}`, `/debates/{date}/chat`. `NotImplementedError` from the agents is caught here and converted to a stub payload so the API is fully callable in Phase 2. |
| [`lambda_handler.py`](lambda_handler.py) | Mangum ASGI-to-Lambda adapter. Used only when we ship the container image in Phase 6. |
| [`services/bedrock.py`](services/bedrock.py) | Sole owner of the `bedrock-runtime` client. `summarize()` for Nova Lite one-shots, `chat_with_documents()` for Nova Pro multi-turn with attached documents. **Enforces `MAX_TOPICS_PER_SESSION = 5` and `MAX_DOC_TOKENS_PER_SESSION = 50_000` drop-oldest**, and appends a `cachePoint` block after documents so Bedrock prompt caching kicks in. |
| [`services/storage.py`](services/storage.py) | DDB + S3 access. `put_session()` unconditionally refreshes `ttl` to `now + 3600s` — no upstream caller can forget it. `get_report()` swallows `NoSuchKey` → `None` so S3 misses are ergonomic. |
| [`services/scraper.py`](services/scraper.py) | Types + function signatures only. `list_topics()` and `fetch_report()` raise `NotImplementedError`. Phase 3 lands the SPRS JSON API sniff + Playwright fallback. |
| [`agents/digest.py`](agents/digest.py) | `run_digest(date)` — raises `NotImplementedError` in Phase 2. Phase 3 will implement cache-check → scrape → Nova Lite summarize → DDB write. |
| [`agents/research.py`](agents/research.py) | `run_chat(session_id, date, message, topic_id)` — raises `NotImplementedError` in Phase 2. Ships with the finalized `SYSTEM_PROMPT` and the `<grounded>false</grounded>` marker parser so Phase 4 only needs to wire the flow. |

---

## Run locally

The parent Python venv at `Roulette-Kaki/.venv` already has boto3. Install
the rest, then start uvicorn:

```bash
cd BlogPost/backend
../../.venv/bin/pip install -r requirements.txt
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```

Interactive Swagger UI: **http://localhost:8000/docs** (easiest way to
exercise the POST endpoint).

---

## API surface (Phase 2)

| Method | Path | Returns |
|---|---|---|
| `GET`  | `/`                          | Endpoint directory (self-describing) |
| `GET`  | `/health`                    | `{"status": "ok", "phase": 2}` |
| `GET`  | `/debates`                   | Stub list with one debate summary |
| `GET`  | `/debates/{date}`            | Stub digest. **`date` must be ISO `YYYY-MM-DD`** — e.g. `2026-08-05`. |
| `POST` | `/debates/{date}/chat`       | Stub echo reply. Body: `{"message": "...", "session_id"?, "topic_id"?}`. Returns `{"session_id", "reply", "topics_used", "grounded": false}`. |

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

## What Phase 2 is deliberately NOT

- No embeddings. No `sentence-transformers`, no `torch`, no vector store.
  See [`../CLAUDE.md`](../CLAUDE.md) — this is a hard constraint carried
  by design.
- No real scraping — `services/scraper.py` is a signature-only stub.
- No real LLM calls — the agents raise before touching Bedrock.
- No AWS resource provisioning — the DDB tables and S3 bucket do not exist
  yet. Phase 3 creates them.

---

## Environment variables (all optional)

| Var | Default | Meaning |
|---|---|---|
| `AWS_REGION` | `ap-southeast-1` | Bedrock + DDB + S3 region. Lambda injects this automatically at deploy time. |
| `DIGESTS_TABLE` | `DebateDigests` | DDB table for cached digests. |
| `SESSIONS_TABLE` | `ChatSessions` | DDB table for chat sessions (TTL). |
| `CACHE_BUCKET` | `parl-debate-cache` | S3 bucket for raw report bytes. |

Note: if your shell has `AWS_REGION=us-east-1` set, that overrides the
default at runtime and Bedrock calls will 404 on the Singapore model IDs.
`export AWS_REGION=ap-southeast-1` before running against real AWS.

---

## What's next — Phase 3

Replace the `NotImplementedError` in `agents/digest.py::run_digest` with:

1. `storage.get_digest(date)` → return on hit.
2. `scraper.list_topics(date)` — try SPRS JSON API via `httpx`; fall back
   to Playwright only if that fails.
3. For each topic, `scraper.fetch_report(topic)` → `storage.put_report()`
   into S3.
4. `bedrock.summarize(prompt)` → single Nova Lite call over the topic
   titles + speakers.
5. Write the assembled digest via `storage.put_digest(...)`.

Phase 3 is the first phase that creates AWS resources — two DynamoDB
tables (`DebateDigests` + `ChatSessions`) and an S3 bucket
(`parl-debate-cache`). It's also the first phase to spend Bedrock tokens.
Verify AWS credentials aren't expired (`aws sts get-caller-identity`)
before starting.
