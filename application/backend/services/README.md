# Services — Roulette-Kaki

This file documents the shared backend service layer used by the agents. See
`ARCHITECTURE.md` for the end-to-end system view and the agent contracts that
call into these modules.

All service modules live under [`application/backend/services/`](application/backend/services/)
and are designed to keep external APIs, persistence, runtime configuration, and
retrieval logic behind a stable interface for the agent layer.

---

## Shared service layer

The service layer is the operating backbone for the app: it owns model access,
AWS storage, scraping, verification, translation, and search orchestration.
Agents call into this layer instead of creating their own clients or relying on
infrastructure-specific code paths.

### 1. Model and runtime configuration

**Core modules:**
- `bedrock.py` — single entry point for Amazon Nova model calls, document handling,
  prompt caching, token/topic caps, and usage tracking.
- `config.py` — loads environment settings from AWS SSM and keeps secrets out of
  agent code. Local development can stub this path when direct configuration is
  easier.

**Responsibilities:**
- Centralize all model calls through one Bedrock wrapper.
- Keep runtime defaults, region config, and prompt constraints consistent across
  all agents.
- Emit token usage data so LLM cost drift can be observed in production metrics.

### 2. Storage and caching

**Core modules:**
- `storage.py` — reads and writes digest rows, chat sessions, and cached reports
  to DynamoDB and S3, with in-memory fallbacks for local/test execution.

**Responsibilities:**
- Store debate digests keyed by sitting date.
- Keep chat session state short-lived with TTL refresh on each turn.
- Cache raw report documents so the same Hansard body is not re-fetched.
- Provide a local stub mode for deterministic developer and test workflows.

### 3. Scraping and page retrieval

**Core modules:**
- `scraper.py` — stable topic/report interface consumed by agents.
- `scraper_sprs.py` — live SPRS API client for paginated topic listings and
  Hansard fetches.
- `sittings.py` — Parliament sitting discovery and date fallback logic using the
  YouTube playlist metadata.

**Responsibilities:**
- Normalize local fixtures and live SPRS responses behind a single interface.
- Fetch missing debate topics and report bodies only when required.
- Keep scraping logic separate from agent reasoning so caller code remains
  consistent across dates and environments.

### 4. Search, ranking, and verification

**Core modules:**
- `search_service.py` — boundary for live search-agent calls and optional remote
  delegation.
- `webscraper.py` — fetches and ranks official and community sources, then
  structures the evidence for policy answers.
- `google_search.py` — optional URL discovery layer for candidate search results.
- `verification.py` — evaluates authority, recency, and policy consistency before
  answers are returned.

**Responsibilities:**
- Retrieve fresh official sources for policy questions.
- Distinguish official and unofficial findings.
- Rank and compare source quality so the answer reflects current and reliable
  information rather than stale or low-authority content.

### 5. Translation and speech handling

**Core modules:**
- `translation.py` — normalizes incoming multilingual requests into a common
  English representation.
- `translation_wrapper.py` — wraps agent calls with language translation in and
  out for multilingual experiences.
- `meralion.py` — handles speech transcription and audio translation flows.

**Responsibilities:**
- Preserve intent while translating user text across Chinese, Malay, Tamil,
  Singlish, and other supported inputs.
- Keep speech-specific code isolated from the text pipeline.
- Avoid embedding or non-service-specific logic inside agent modules.

---

## Cross-service rules (apply throughout the repo)

- **Default to a single Bedrock wrapper** for all model calls. Do not scatter
  boto3 client creation across modules.
- **Keep agents thin** and keep infrastructure concerns in services.
- **Prefer cached data over fresh scraping** when the same digest/report has been
  seen before.
- **Treat retrieval quality as a policy issue**: official and up-to-date sources
  must outrank community speculation.
- **No embedding pipeline** should be introduced into this layer; when retrieval
  is needed, the answer is to attach the relevant document or use a curated
  evidence source, not a vector index.
- **Production safety**: secrets, provider config, and AWS access remain in the
  service layer and are not duplicated in individual agents.

## Workflow

1. Application startup loads configuration, then agents receive requests through
   the API layer.
2. Translation wrappers normalize multilingual input before the main/query agent
   handles it.
3. Agents call services for model inference, storage, retrieval, and verification
   depending on the workflow.
4. Debate flows rely on scraping and cached reports, while policy flows rely on
   search, ranking, and source verification.
5. Final responses are assembled by the agent layer, with services providing the
   evidence, normalization, and operational helpers behind the scenes.
