# Services

Shared backend integrations and infrastructure used by the agents. These modules keep external APIs, persistence, model limits, source checks, and language handling in one place so agents can focus on orchestration.

## Services

- **`bedrock.py`**: The single entry point for Amazon Nova calls. It provides summarisation, chat, tool use, document caching, token/topic limits, and usage logging so every agent follows the same model and grounding rules.
- **`config.py`**: Loads encrypted `/parl/` parameters from AWS SSM into environment variables at startup. It keeps secrets out of agent code and is skipped for local stubs.
- **`storage.py`**: Reads and writes digests and expiring chat sessions in DynamoDB, and raw reports in S3. Local stub mode replaces AWS with in-memory stores for development and tests.
- **`scraper.py`**: Presents a stable topic/report interface to agents. It serves fixture data locally or dispatches to the live SPRS implementation based on `SCRAPER_MODE`.
- **`scraper_sprs.py`**: Implements the SPRS HTTP calls for paginated topic lists and Hansard report content. It is kept behind `scraper.py` so callers do not depend on the site-specific API.
- **`sittings.py`**: Discovers Parliament sitting dates from the YouTube playlist, parses dates, prefers English videos, caches results, and supplies a fallback list when the API is unavailable.
- **`search_service.py`**: Provides one search-agent boundary. It calls the local search agent or an optional remote `SEARCH_AGENT_URL`, returning the same structured evidence shape to query agents.
- **`webscraper.py`**: Searches and fetches official and community pages, extracts metadata, checks applicability and recency, ranks sources, and reports conflicts for policy answers.
- **`google_search.py`**: Optionally discovers candidate URLs through Google Custom Search with domain filters. It fails closed when credentials are missing or the API is unavailable.
- **`verification.py`**: Validates source authority, separates demographic categories, extracts policy facts, and distinguishes current, historical, conflicting, or superseded information.
- **`translation.py`**: Translates user text to and from supported languages using Nova, preserving key intent when converting input to English.
- **`translation_wrapper.py`**: Wraps feature handlers with a language sandwich: translate input to English, run the normal agent, then translate the answer back. English uses a no-op fast path.
- **`meralion.py`**: Handles audio transcription and audio translation for speech input. It keeps MERaLiON-specific HTTP behavior separate from text translation, which uses Bedrock.

## Workflow

1. Application startup loads configuration, then agents receive a request through the API.
2. `translation_wrapper.py` optionally normalises non-English input before the main/query agent runs.
3. Agents call `bedrock.py` for planning, synthesis, grounded chat, or tool use; `storage.py` supplies cached digests, sessions, and reports.
4. Debate flows use `scraper.py`, `scraper_sprs.py`, and `sittings.py`; policy flows use `search_service.py`, `webscraper.py`, and optionally `google_search.py`.
5. `verification.py` checks retrieved evidence before an answer is returned, and translation wraps the final response when needed.
6. Local tests can use fixtures, in-memory storage, and stub settings to avoid live AWS, SPRS, search, and translation calls.
