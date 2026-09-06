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

## Policy Query Agent and Search

`POST /query` is handled by `agents/query.py`. The flow is:

1. Translate a non-English text question to English with Nova Lite and retain
   key points from the translation.
2. Build a search plan with the main agent and call the `search_policy` tool
   through the Nova Lite Converse tool loop.
3. Retrieve and rank sources through `services/search_service.py`,
   `agents/search.py`, and `services/webscraper.py`.
4. Prefer current applicable official sources (`.gov.sg` and official
   statutory-board domains) for policy rules, figures, eligibility, and dates.
   Community sources are supplementary sentiment and opinion evidence.
5. Verify category boundaries and synthesize a concise answer with official
   citations. A session ID may be supplied to preserve query context.

The search service runs in-process. `SEARCH_AGENT_URL` remains an optional
HTTP fallback for a future split deployment, but it is not required by the
current application.

## Parliament Debate Digest

The digest flow is a sitting feed backed by YouTube metadata and a per-date
digest cache.

```text
GET /sittings
  -> services/sittings.py -> YouTube Data API v3 or curated fallback

GET /debates/{date}
  -> DynamoDB DebateDigests cache
  -> list_topics() from fixture data or SPRS searchResult API on a miss
  -> Nova Lite summary
  -> cached digest response

POST /debates/{date}/chat
  -> ChatSessions state
  -> lazy S3 report lookup/fetch for selected topics
  -> Nova Pro research loop with attached documents
```

`services/scraper.py` selects fixture or SPRS mode. The SPRS implementation
uses HTTP requests and pagination, then fetches a report body lazily through
`getHansardTopic` only when research chat needs it. Raw HTML/report bytes are
shared in S3 under `{date}/{topic_id}.{ext}` so the same topic is not scraped
again for every session.

The digest agent writes a `DebateDigests` item containing the sitting metadata,
summary, category breakdown, interesting topics, and topic metadata. A missing
sitting returns an error and does not create a digest row.

## Hansard Research Agent

The research agent is document-grounded rather than embedding-based. A chat
request can explicitly provide a valid `topic_id`; selected topics are loaded
into the anonymous session and their cached reports are attached to the
Converse request as native Bedrock document blocks.

- Documents and the cache point are placed in message 0 so the prompt-cache
  prefix stays stable across turns.
- The agent returns `reply`, `topics_used`, and a `grounded` flag. Ungrounded
  policy-shaped questions can use the route-layer web fallback, controlled by
  `ENABLE_WEB_FALLBACK`.
- An empty session does not call Bedrock; the user is asked to select a topic.
- `services/bedrock.py` caps the active research context at five topic
  documents and approximately 50,000 document tokens, dropping the oldest
  topic when necessary. This is a context-management rule, not a separate
  session pricing model.
- The research tool loop is bounded at three iterations in `research.py`.

`ChatSessions` has a one-hour DynamoDB TTL refreshed centrally by
`storage.put_session` on every write. The browser separately persists the
visible debate conversation in language-specific localStorage buckets.

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
