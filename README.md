# Roulette-Kaki

## Table of Contents

1. [Overview](#1-overview)
2. [Features](#2-features)
3. [Tech Stack](#3-tech-stack)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start](#5-quick-start)
6. [Docker Deployment](#6-docker-deployment)
7. [Configuration](#7-configuration)
8. [API Reference](#8-api-reference)
9. [General Workflow](#9-general-workflow)
10. [Data Sources](#10-data-sources)
11. [Troubleshooting](#11-troubleshooting)
12. [Testing & Utilities](#12-testing--utilities)
13. [Infrastructure Setup (Terraform)](#13-infrastructure-setup-terraform)
14. [Security & Privacy](#14-security--privacy)
15. [Roadmap](#15-roadmap)

## 1. Overview

Roulette-Kaki was created as part of the SimplifyNext Agentic AI Hackathon 2026.

Understanding and following developments in policy is important for individual Singaporeans as policy impacts their day-to-day living.
Unfortunately, policies are often long, dry and complex, requiring significant time and effort to understand.
Additionally, it is difficult to follow proposed changes to policy as these discussions are often hidden under hours of parliamentary debate.
This results in Singaporeans often being more politically apathetic and being unprepared for policy change that they could have known about if they were more in tune with news and debates.

## 2. Features

Roulette-Kaki aims to resolve this issue through two main functions: a policy summariser and a debate summariser.

The **policy summariser** summarises existing policy and presents it in a news-article-like way, pulling and citing information from both official (`.gov.sg`) and unofficial community sources.

The **debate summariser** summarises the content of a parliamentary debate session, with each sitting rendered as a blog-style card users can drill into.

Additional features:

- **AI chat helper** — grounded in the raw parliamentary report bytes attached as Bedrock Converse `document` blocks (no embeddings tier).
- **Multilingual support** — English, Chinese, Malay, Tamil, and Singlish via Nova + MERaLiON.
- **Audio transcription** — via MERaLiON ASR.
- **Flashcard generation** — from any digest topic or chat reply, for study/revision.

## 3. Tech Stack

### Front end

- React 19
- TypeScript
- Tailwind CSS 4
- Vite 8
- React Router 7

### Back end

- FastAPI + Uvicorn
- httpx, BeautifulSoup4 (SPRS scraper stack)
- boto3

#### External APIs

- AWS Bedrock (Amazon Nova Lite + Nova Pro)
- YouTube Data API v3 (sitting feed)
- MERaLiON (Singlish/audio ASR)
- Google Custom Search JSON API
- DuckDuckGo (unauthenticated fallback)

#### AWS

- **Bedrock** — Nova Lite (`amazon.nova-lite-v1:0`) for digest + query, Nova Pro (`amazon.nova-pro-v1:0`) for chat
- **DynamoDB** — `DebateDigests` (cached digests), `ChatSessions` (chat sessions, TTL 1h)
- **S3** — `parl-debate-cache-v2` (raw report PDFs/HTML keyed `{date}/{topic_id}`)

The application itself is no longer hosted on AWS — the Docker image runs wherever you point it (local machine, VM, container host). Only the backing data-plane services above live in AWS, and they are provisioned by Terraform (see [Infrastructure Setup](#13-infrastructure-setup-terraform)).

## 4. Prerequisites

The following are required to run the program locally:

- Python 3.11+
- Node.js 20+ and npm
- (For Docker) Docker Engine 24+ and Docker Compose v2
- (For real-AWS mode) AWS credentials with Bedrock, DynamoDB, and S3 access in `us-east-1`

Python dependencies (pinned in [`application/backend/requirements.txt`](application/backend/requirements.txt)):

- FastAPI 0.115.0 or later
- uvicorn[standard] 0.32.0 or later
- boto3 1.35.0 or later
- pydantic 2.9.0 or later
- requests 2.31.0 or later
- beautifulsoup4 4.12.0 or later
- httpx 0.27.0 or later

## 5. Quick Start

1. Create a virtual environment and install Python dependencies:

    ```bash
    python -m venv .venv && source .venv/bin/activate
    pip install -r application/backend/requirements.txt
    ```

2. Configure credentials and app settings (see [Configuration](#7-configuration)).

3. Run the backend:

    ```bash
    cd application/backend
    export USE_LOCAL_STUBS=1 SCRAPER_MODE=fixture AWS_REGION=us-east-1
    uvicorn main:app --reload --port 8000
    ```

4. Visit `http://127.0.0.1:8000/docs` for interactive API docs.

5. In a second terminal, run the frontend:

    ```bash
    cd application/frontend
    npm install
    npm run dev              # → http://localhost:5173
    ```

`USE_LOCAL_STUBS=1` short-circuits DynamoDB + S3 so you only need Bedrock credentials to iterate on prompts. Drop it (and set `SCRAPER_MODE=sprs`) to hit real AWS after running `terraform apply`.

## 6. Docker Deployment

The repo ships a single multi-stage [`Dockerfile`](Dockerfile) that builds the React frontend, then bakes the compiled bundle into a Python runtime image alongside the FastAPI backend. The backend serves the SPA under `/` and the API under `/api` from the same origin — no separate frontend host needed.

### Build and run with Docker Compose

The included [`docker-compose.yml`](docker-compose.yml) builds the image, loads env vars from `.env`, and mounts your local `~/.aws` credentials so botocore can resolve an SSO profile.

```bash
docker compose up --build
```

The app is served at `http://localhost:8080` (SPA on `/`, API on `/api`, Swagger UI on `/api/docs`).

By default the compose file expects an AWS SSO profile named `hack2026_IsbUsersPS-388562170161`. Change `AWS_PROFILE` in `docker-compose.yml` if you use a different profile, or override at run time:

```bash
AWS_PROFILE=my-profile docker compose up --build
```

The `~/.aws` volume is mounted **read-write** on purpose — a read-only mount breaks SSO token refresh because botocore cannot write the renewed token back to `~/.aws/sso/cache/`.

### Build and run with plain Docker

If you prefer not to use Compose:

```bash
docker build -t roulette-kaki:local .
docker run --rm -p 8080:8080 \
  --env-file .env \
  -e SERVE_STATIC=1 \
  -e USE_LOCAL_STUBS=0 \
  -e AWS_PROFILE=your-sso-profile \
  -v ~/.aws:/root/.aws \
  roulette-kaki:local
```

### What the image contains

| Stage | Base | Purpose |
|---|---|---|
| `frontend-build` | `node:20-alpine` | `npm ci` + `npm run build` under `application/frontend/`. No `VITE_*_API_URL` is set, so `api.ts` falls back to same-origin `/api`. |
| `runtime` | `python:3.12-slim` | Installs `application/backend/requirements.txt`, copies the backend source, and copies the built frontend from the previous stage into `./static`. Runs `uvicorn main:app` on `${PORT}` (defaults to `8080`). |

### Environment inside the container

The image sets `SERVE_STATIC=1` and `PORT=8080` by default. Every other setting comes from your `.env` file (which is git-ignored — see [Security & Privacy](#14-security--privacy)). At minimum you'll want:

```
AWS_REGION=us-east-1
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
DIGESTS_TABLE=DebateDigests
SESSIONS_TABLE=ChatSessions
CACHE_BUCKET=parl-debate-cache-v2
SCRAPER_MODE=sprs
USE_LOCAL_STUBS=0
YOUTUBE_API_KEY=...
```

See [Configuration](#7-configuration) for the full list.

## 7. Configuration

Configuration is loaded from environment variables. Local dev uses a `.env` file at the repo root; the Docker image reads the same file via `env_file:` in compose.

**Never commit `.env`** — it is `.gitignore` and `.dockerignore`. Rotate any key that lands in the repo history.

### Required for real-AWS mode

| Variable | Example | Purpose |
|---|---|---|
| `AWS_REGION` | `us-east-1` | Bedrock + DynamoDB + S3 region. Must match Terraform. |
| `BEDROCK_REGION` | `us-east-1` | Bedrock control-plane region. |
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Default digest/query model. |
| `DIGESTS_TABLE` | `DebateDigests` | DDB table for cached digests. |
| `SESSIONS_TABLE` | `ChatSessions` | DDB table for chat sessions (TTL 1h). |
| `CACHE_BUCKET` | `parl-debate-cache-v2` | S3 bucket for raw report bytes. |
| `SCRAPER_MODE` | `sprs` | `fixture` reads `backend/fixtures/`; `sprs` hits the real SPRS API. |
| `USE_LOCAL_STUBS` | `0` | Set `1` to short-circuit DDB + S3 for local iteration. |

### Optional integrations

| Variable | Purpose |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key. Without it `/sittings` falls back to a curated hard-coded list. |
| `MDDI_YOUTUBE_CHANNEL` | Handle for the parliament livestream channel. |
| `YOUTUBE_PLAYLIST` | Playlist ID or full URL to fetch sittings from. |
| `MERALION_API_KEY` | MERaLiON key for Singlish + audio ASR. |
| `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` | Google Custom Search JSON API credentials. Optional; DuckDuckGo is the fallback. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins allowed by the API. Defaults to Vite dev server. |
| `SPRS_REQUEST_DELAY` | Seconds between SPRS calls. Defaults to `0.5`. |
| `SITTINGS_CACHE_TTL_SECONDS` | TTL for the in-process playlist cache. Defaults to `600`. |
| `SEARCH_AGENT_URL` | If set, `search_service.fetch_from_search_agent` first tries `POST {url}/search` before falling back to the in-process module. |
| `ENABLE_WEB_FALLBACK` | Set to `0` to disable the web-search fallback when the research agent returns `grounded=false`. Defaults to `1`. |

Per-backend runbook and full env-var reference lives in [`application/backend/README.md`](application/backend/README.md).

## 8. API Reference

The API is implemented in [`application/backend/main.py`](application/backend/main.py). When running in API-only mode (`SERVE_STATIC=0`), the endpoints use the paths below. When the built frontend is served by the backend (`SERVE_STATIC=1`, the default in the Docker image), API paths are prefixed with `/api`.

### General

- `GET /` — self-describing endpoint directory.
- `GET /health` — `{"status": "ok", "service": "policy-and-parliament-api"}`.

### Policy query

- `POST /query`
  - Body: `{ question, urls?, session_id?, language? }`
  - Returns: `{ answer, session_id, language }`
- `GET /query/sessions/{session_id}` — returns the stored query session.

### Parliamentary debates

- `GET /sittings?limit=6&offset=0` — available parliamentary sittings (YouTube-driven).
- `GET /debates` — cached debate digests (diagnostic; the frontend feed uses `/sittings`).
- `GET /debates/{date}?refresh=false&language=English` — digest for a sitting. Runs the digest agent on cache miss; HTTP 404 when no sitting held.
- `POST /debates/{date}/chat`
  - Body: `{ session_id?, message, topic_id?, language? }`
  - Returns: `{ session_id, reply, topics_used, grounded }`
- `POST /debates/{date}/flashcards/topic/{topic_id}`
  - Body: `{ count? }` — flashcards from a digest topic.
- `POST /debates/{date}/flashcards/from-chat`
  - Body: `{ reply_text, topic_ids?, count? }` — flashcards from a chat reply.

### Language and audio

- `POST /translate`
  - Body: `{ text, target_language, source_language? }`
  - Returns: `{ translated_text, target_language }`
- `POST /transcribe`
  - Body: `{ audio_b64, mime? }`
  - Returns: `{ text, transcript }`
- `POST /translate/audio`
  - Body: `{ audio_b64, target_language, mime? }`
  - Returns: `{ translated_text, target_language }`

## 9. General Workflow

1. Browse available parliamentary sittings with `GET /sittings`.
2. Fetch a debate digest with `GET /debates/{date}`.
3. Review the summarised topics and select a relevant topic.
4. Ask the AI helper follow-up questions with `POST /debates/{date}/chat`.
5. Generate flashcards from a topic or chat response when useful.
6. Use `POST /query` to search for current policy information from official and unofficial sources.
7. Use translation or transcription endpoints when working with supported languages or audio input.

## 10. Data Sources

- **Singapore Parliament Reports System (SPRS)** — `https://sprs.parl.gov.sg`. Raw parliamentary reports (PDF/HTML) are lazily scraped on first mention of a topic and cached in S3 keyed `{date}/{topic_id}`. Each `(date, topic_id)` pair is scraped exactly once.
- **YouTube (Ministry of Digital Development and Information channel)** — sitting videos are the canonical source of "what sittings happened when". The `/sittings` endpoint reads the configured playlist via YouTube Data API v3 and parses the sitting date from each video title.
- **Official `.gov.sg` policy pages** — ranked highest in the search stack, always retained in results even after deduping.
- **Community forums** — surfaced as unofficial sources with an "unofficial" label. Never allowed to overrule an official number in the grounding prompt.
- **DuckDuckGo / Google Custom Search** — used as generic search plumbing when scraping community sources.
- **MERaLiON** — Singlish + audio ASR for the `POST /transcribe` and Singlish translation paths.

## 11. Troubleshooting

- **`GET /debates/{date}` returns 404** — that date had no parliamentary sitting. Confirm the date against `GET /sittings` or the YouTube playlist.
- **`POST /debates/{date}/chat` returns 503** — you're running in `SCRAPER_MODE=fixture`. Fixtures don't ship report bodies, so the chat agent has nothing to attach as a `document` block. Switch to `SCRAPER_MODE=sprs`.
- **Bedrock calls 404 on the model ID** — check your effective `AWS_REGION`. Nova Lite/Pro require `us-east-1` for the direct foundation-model IDs used in this repo. If your shell already exports `AWS_REGION`, that overrides the app default at runtime.
- **CORS errors from the frontend** — add the frontend origin to `CORS_ALLOWED_ORIGINS`. Vite dev server defaults are already whitelisted.
- **`YOUTUBE_API_KEY` unset / API failure** — `/sittings` silently falls back to a curated hard-coded list. Set the key to get live pagination.
- **SSO token refresh fails inside Docker** — the `~/.aws` volume must be mounted **read-write**. Read-only mounts break botocore's tempfile-based token rotation.
- **Chat feels expensive** — check that `services/bedrock.py` is enforcing the 5-topic / 50K-token session cap and that `cachePoint` is being appended after documents (Bedrock prompt caching must be active on turns 2..N).

## 12. Testing & Utilities

Backend tests live in [`application/backend/tests/`](application/backend/tests/) and cover the query agent, research agent, web-fallback, main-agent orchestrator, opinion queries, search agent, and policy scenarios.

```bash
cd application/backend
python -m pytest tests/
```

Utility scripts under [`scripts/`](scripts/):

- `prepopulate_digests.py` — warms the DDB `DebateDigests` cache before demo day. Pair with `SCRAPER_MODE=sprs` to fetch real showcase digests.
- `record_sprs.py` — captures SPRS payloads under `scripts/captures/` for offline testing.
- `showcase_dates.txt` — curated sitting dates used during demos.

One-off debugging scripts (not part of any deploy) live in [`scratch/`](scratch/).

Terraform module lives in [`terraform/`](terraform/); apply it once before running the backend against real AWS — see [Infrastructure Setup](#13-infrastructure-setup-terraform) for the full walkthrough. Bootstrap scripts for the AWS environment live in [`terrafoorm/deploy/`](terraforn/deploy/).

## 13. Infrastructure Setup (Terraform)

The AWS backing services the backend depends on (Bedrock, DynamoDB tables, S3 cache bucket) are provisioned with Terraform. Terraform state itself lives in a shared S3 bucket with a DynamoDB lock table so the whole team can `plan` / `apply` against a single source of truth without stepping on each other.

### Layout

- [`terraform/main.tf`](terraform/main.tf) — provider config, default tags.
- [`terraform/dynamodb.tf`](terraform/dynamodb.tf) — `DebateDigests` and `ChatSessions` tables.
- [`terraform/s3.tf`](terraform/s3.tf) — `parl-debate-cache-v2` cache bucket.
- [`terraform/backend.tf`](terraform/backend.tf) — declares the S3 remote backend as *partial config*; the bucket / key / lock-table are passed via `-backend-config` on `terraform init` (keeps account IDs out of git).
- [`terraform/variables.tf`](terraform/variables.tf) — knobs for region + resource names.
- [`terraform/deploy/00_bootstrap.sh`](terraform/deploy/00_bootstrap.sh) — one-time script that creates the shared state bucket + lock table.

### One-time bootstrap (run once per AWS account)

Only one teammate needs to do this. The script is idempotent — re-running it against an already-bootstrapped account is a safe no-op.

Prereqs: AWS CLI v2 authenticated (`aws sts get-caller-identity` works) and `jq` installed.

```bash
./terraform/deploy/00_bootstrap.sh
```

The script provisions:

- **S3 bucket** `parl-tfstate-<account-id>` — versioning + AES256 encryption + full public-access block. Holds the shared `terraform.tfstate` object.
- **DynamoDB table** `parl-tf-locks` — `PAY_PER_REQUEST`, hash key `LockID`. Provides state locking so two teammates cannot `apply` concurrently and corrupt state.

Defaults can be overridden with `AWS_REGION`, `TF_STATE_BUCKET`, or `TF_LOCK_TABLE` env vars before invocation.

### Using the shared state

After bootstrap, every teammate (including the one who ran the bootstrap) initialises Terraform against the same remote backend. Fill in your account ID once and reuse the block:

```bash
cd terraform
terraform init \
  -backend-config="bucket=parl-tfstate-<account-id>" \
  -backend-config="key=parl/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=parl-tf-locks"
```

Then plan / apply as usual:

```bash
terraform plan
terraform apply
```

Every command reads and writes the same S3 state object; the DynamoDB lock table serialises concurrent runs, so two developers running `apply` simultaneously will see a lock-acquired error instead of racing to overwrite each other. Always `terraform plan` before `apply` on shared state — the plan reflects the current cluster's real state, not your local memory of it.

### Migrating a stale local state

If you have a leftover local `terraform.tfstate` (e.g. from before the remote backend was added), migrate it once and only once:

```bash
cd terraform
terraform init -reconfigure -migrate-state \
  -backend-config="bucket=parl-tfstate-<account-id>" \
  -backend-config="key=parl/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=parl-tf-locks"
```

Terraform will copy the local state up to S3. After the migration succeeds, delete the local `terraform.tfstate` and `terraform.tfstate.backup` files (they are already `.gitignore`d) — keeping them around invites accidental drift.

### What Terraform provisions

- `DebateDigests` — DynamoDB table caching per-date parliament digests (PK: `date`).
- `ChatSessions` — DynamoDB table storing chat sessions with 1h TTL (PK: `session_id`, TTL attribute: `ttl`).
- `parl-debate-cache-v2` — S3 bucket caching raw SPRS report bytes, keyed `{date}/{topic_id}.{ext}`.

Region defaults to `us-east-1` (required for Nova Lite / Nova Pro). Override with `terraform apply -var=region=...` and match `AWS_REGION` / `BEDROCK_REGION` in your `.env`.

Bedrock model access is not provisioned by Terraform — enable the Nova Lite and Nova Pro model IDs manually in the Bedrock console for the target account and region before running the backend.

## 14. Security & Privacy

- Keep `.env` out of source control (it is git-ignored and Docker-ignored) and rotate AWS credentials + third-party API keys regularly.
- Grant Bedrock permissions only for the specific model IDs and regions the application requires.
- Avoid logging or persisting sensitive user inputs beyond what is necessary to maintain a session — `ChatSessions` rows carry a `ttl = now + 3600s` attribute (refreshed on every write) so long-tail sessions are auto-purged after ~1 hour.
- Sessions are anonymous UUIDs; there is no multi-user auth by design.

## 15. Roadmap

- **Real-time civic-discussion transcription and summarisation** — extend the pipeline to transcribe and summarise long-form live events such as the National Day Rally and Budget speeches as they happen.
- **Text-to-speech output** — surface digests and chat replies as audio so illiterate and visually impaired Singaporeans can access the same content. Pairs with the existing ASR / translation path.
- **Autonomous frontend layout agent** — real-time layout generation performed by a frontend layout agent that populates the "Newspaper UI" without hand-authored templates.
- **Personalised feed** — prioritise information with high impact on the user's demographic, and integrate with a mobile app that pushes notifications on policy updates.
- **Assisted policy-scheme application forms** — pre-populate scheme application forms with verified user criteria, producing a complete draft ready for submission.
- **Discussion portal** — a first-party space where members of the public can share opinions on policies and debates surfaced by the app.
