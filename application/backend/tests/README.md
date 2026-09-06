# Tests

Backend unit, integration, and acceptance tests for policy queries, agent routing, search behavior, and Hansard research. They use `unittest`; external model, search, and storage calls are mocked where deterministic behavior is required.

## Test Modules

- **`test_agentic_pipeline.py`**: Exercises end-to-end policy scenarios such as eligibility figures, follow-up context, public opinion, payouts, and CPF rates. It also checks insufficient-evidence handling and research tools: `execute_get_sitting_overview` reads the digest, while `execute_fetch_topic_report` loads a report for grounded chat. Storage calls such as `get_digest` and `get_report` are mocked so the test controls the evidence returned to `run_chat`.
- **`test_main_agent_orchestrator.py`**: Verifies that `create_search_plan` classifies intent, preserves follow-up context, selects the correct agents, and creates official/community queries. It calls `services.verification` with sample sources to confirm current versus historical policy facts without relying on live retrieval.
- **`test_opinion_queries.py`**: Confirms that opinion questions use community search, factual questions use official sources, and mixed queries keep those evidence types separate. It calls `fetch_from_search_agent` directly for the no-community-evidence case to ensure the result reports insufficient evidence instead of substituting an unrelated official page.
- **`test_query_integration.py`**: Tests prompt construction, the query agent, and the FastAPI endpoints. `TestClient` sends API requests, while `fetch_from_search_agent` and `ask_nova` are mocked to isolate API/session behavior from live search and model calls. It also verifies multi-turn session history, TTL data, health status, and blank-question validation.

## Workflow

1. Tests configure local router or stub settings, then call an agent, service, tool handler, or API endpoint.
2. Planning tests validate intent, targets, time scope, and selected sub-agents before retrieval occurs.
3. Retrieval tests provide controlled official, community, digest, or report evidence and verify grounding, source separation, and insufficiency handling.
4. Integration tests replace live Bedrock, search, and storage dependencies with mocks so only the behavior under test is evaluated.
5. Assertions check returned answers, structured plans, tool results, HTTP responses, and persisted session behavior.
