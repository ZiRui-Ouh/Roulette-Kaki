# Architecture - Roulette-Kaki

Roulette-Kaki is a Singapore policy and parliamentary intelligence product.
The active application is a single FastAPI backend in
[`application/backend/`](application/backend/) and a React 19 + Vite SPA in
[`application/frontend/`](application/frontend/). The top-level `BlogPost/`,
`query_agent/`, and `search_agent/` directories are retained repository
artifacts; the consolidated `application/` tree is the runtime source of
truth.

The backend combines four user-facing capabilities in one service:

- Policy questions grounded in current official and community web sources.
- Parliament sitting discovery, digest generation, and Hansard research chat.
- Text and speech translation across English, Chinese, Malay, Tamil, and
  Singlish.
- Flashcard generation from a debate topic or a research-chat response.

---

## System Shape

![Agent architecture: a user query flows through the Main Agent to a Search Orchestration Agent that fans out in parallel to Official and Community search agents. Results feed a DAG multi-agent pipeline (Query Refiner → Web Search → Content Extractor + Relevance Filter → Aggregator), then a Verification & Reasoning stage (Verification Agent → Answer Synthesis Agent) produces the final answer with sources and citations back to the user.](docs/images/agent-architecture.png)

The browser talks to the same FastAPI application for all product features.
In local development Vite serves the SPA and the backend serves API routes.
When `SERVE_STATIC=1`, the backend serves the built SPA from `static/` and
mounts the API router under `/api`; otherwise the historical bare API paths
remain available. `application/backend/main.py` owns route registration,
CORS, translation wrapping, and the boundary between agents and HTTP.

```text
React SPA (Vite)
  |  /query, /sittings, /debates, /translate, /transcribe, /flashcards
  v
FastAPI + Mangum-compatible backend
  |-- Policy Query Agent -> search service -> official/community web sources
  |-- Digest Agent -------> fixture or SPRS scraper -> DynamoDB digest cache
  |-- Research Agent -----> S3 report cache + Bedrock document blocks
  |-- Translation --------> Bedrock text translation or MERaLiON audio API
  |-- Flashcards ----------> Bedrock generation from digest/chat context
  |
  `-- services/bedrock.py, storage.py, scraper*.py, webscraper.py
```

All Bedrock calls go through `services/bedrock.py`. Storage access is
centralized in `services/storage.py`; agents do not create their own AWS
clients. Local defaults set `USE_LOCAL_STUBS=1` and `SCRAPER_MODE=fixture` so
the service can run without AWS or live SPRS access.

## Model Tiers

The model IDs below are the defaults in the active implementation. The Nova
Lite ID can be overridden with `BEDROCK_MODEL_ID`; the Nova Pro ID is fixed in
the shared Bedrock service.

| Workload | Model and default ID | Implementation |
|---|---|---|
| Policy Query Agent, search synthesis, digest summaries, text translation, and fallback generation | Amazon Nova Lite - `amazon.nova-lite-v1:0` | `bedrock.ask_nova`, `bedrock.converse_with_tools`, and `bedrock.summarize` |
| Hansard research chat and research tool loop | Amazon Nova Pro - `amazon.nova-pro-v1:0` | `bedrock.chat_with_documents`, `bedrock.chat_with_tools`, and `agents/research.py` |
| Browser speech-to-text and speech translation | MERaLiON - configurable, default `MERaLiON/MERaLiON-3-10B` | `services/meralion.py`, called only for audio paths |
| Embeddings | None | Reports are attached as Bedrock `document` blocks; there is no vector index or embedding service |

Bedrock is configured from `BEDROCK_REGION` or `AWS_REGION`, defaulting to
`us-east-1` in the service code. The Terraform default region is also
`us-east-1`. Model selection is centralized so new calls inherit the same
region, local simulation, document limits, and usage logging behavior.

## Frontend

The SPA starts in `main.tsx`, wraps the router in `LanguageProvider`, and
keeps a shared news header/footer shell in `App.tsx`. The active routes are:

| Route | Page and behavior |
|---|---|
| `/` | Local policy news feed from `data/policies.ts`, with category filters, search, a lead story, trending links, and links into policy chat or Hansard |
| `/policy/:id` | Policy article and executive briefing with an article-scoped Policy Query Agent conversation, Markdown answers, reset/share controls, and voice input |
| `/query` | General Policy Query Agent chat with suggested questions, loading/error states, clear-history control, and per-language local history |
| `/debates` | Paginated sitting archive from `GET /sittings`, including latest-sitting spotlight, YouTube watch links/thumbnails, loading states, and configuration/error states |
| `/debates/:date` | Digest summary, interesting topics, topic list, YouTube watch card, sticky Hansard Research Agent chat, and flashcard drawer |

The catch-all route redirects to `/`. `api.ts` centralizes request decoding
and error handling, with `VITE_QUERY_API_URL`, `VITE_BLOGPOST_API_URL`, and
`VITE_API_URL` overrides and same-origin `/api` defaults.

Frontend state and interactions include:

- A language switcher for English, Chinese, Malay, Tamil, and Singlish. The
  selected language is stored as `roulette-kaki:lang`.
- Policy and debate chats send language information to the backend. Query
  history is stored per language; debate sessions and saved flashcard decks
  are stored per sitting and language.
- Debate topic selection is explicit. The research response controls the
  loaded-topic list shown in the chat panel, including a notice when a topic
  is not retained after the context cap.
- Voice input records browser audio and sends it to `POST /transcribe`, which
  uses MERaLiON and cleans speaker tags before returning text.
- Flashcards can be generated from a selected topic or a research-chat reply,
  then saved and deleted in browser storage.

The frontend is built with React, TypeScript, React Router, Tailwind CSS,
React Markdown, and Lucide icons. The Dockerfile builds the SPA with Node 20
and copies the result into a Python 3.12 runtime image for same-origin
serving.

## Translation and Audio

Text translation stays on the shared Nova Lite path. The translation wrapper
short-circuits English, translates non-English text to English before agent
routing, and translates answers back while preserving Markdown where
possible.

Audio is deliberately separate: `services/meralion.py` calls MERaLiON's
`/audio/transcriptions` and `/audio/translations` endpoints with the configured
API key and model. The backend exposes `POST /transcribe` and
`POST /translate/audio`; ordinary text translation does not create a second
LLM client.

## Storage

- **DynamoDB `DebateDigests`**: per-date digest cache, no TTL.
- **DynamoDB `ChatSessions`**: anonymous research sessions keyed by
  `session_id`, with TTL enabled and refreshed for one hour after each write.
- **S3 report cache**: raw SPRS report bytes keyed by date and topic. The
  default application bucket is `parl-debate-cache-v2` and can be overridden
  with `CACHE_BUCKET`.
- **Browser localStorage**: selected language, query history, debate chat
  display state, and saved flashcard decks. This is separate from server-side
  research-session state.

Terraform currently provisions the two DynamoDB tables and the S3 cache
bucket. It does not yet provision Lambda, CloudFront, or an ECS service.

## Deployment and Boundaries

The repository's current container path is:

1. Build the frontend with `npm ci` and `npm run build`.
2. Copy the built `dist/` into the Python 3.12 runtime image.
3. Run Uvicorn with `SERVE_STATIC=1` so the FastAPI app serves both SPA and
   `/api` routes from one origin.

`lambda_handler.py` keeps a Mangum adapter for a Lambda-compatible runtime,
but the current Dockerfile command is Uvicorn. `docker-compose.yml` supports
local container orchestration. The `deploy/` scripts bootstrap Terraform
state; the AWS application resources remain a separate, unfinished migration
step.

There is no authentication layer. Policy-query and research sessions use
anonymous IDs, and a persistent vector index is intentionally out of scope.
