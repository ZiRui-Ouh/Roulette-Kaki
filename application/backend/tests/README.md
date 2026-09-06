# Tests — Roulette-Kaki

This file documents the backend test suite for the Parliament debate and policy
intelligence flows. The tests validate agent routing, retrieval quality,
grounded research behavior, and API integration while keeping external model and
provider calls isolated behind mocks or stubs.

All tests live under [`application/backend/tests/`](application/backend/tests/)
and focus on deterministic checks for planning, search evidence, session state,
and conversation outcomes.

---

## Test suite structure

The test layer sits on top of the agent and service layers. It verifies that each
module behaves correctly when given controlled inputs and expected downstream
responses, without relying on live AWS, Bedrock, or site scraping calls.

### 1. Agentic pipeline tests

**Primary file:** `test_agentic_pipeline.py`

**Responsibilities:**
- Exercise end-to-end policy scenarios such as eligibility checks, CPF figures,
  follow-up context, public opinion, and payout questions.
- Validate insufficient-evidence handling when the retrieval layer cannot support
  a claim.
- Confirm that research tools retrieve a sitting overview and a topic report for
  grounded chat flow.

**Test pattern:**
- Mock storage access like `get_digest` and `get_report` so the test controls the
  evidence returned to the agent.
- Verify tool execution and answer quality without invoking live model providers.

### 2. Orchestrator and routing tests

**Primary file:** `test_main_agent_orchestrator.py`

**Responsibilities:**
- Confirm that `create_search_plan` classifies intent correctly.
- Preserve follow-up context across turns and route to the correct sub-agent.
- Build official and community queries in the right shape for policy answers.

**Test pattern:**
- Feed sample sources into `services.verification` to confirm current vs historical
  policy facts.
- Validate route selection without depending on real retrieval or live search.

### 3. Opinion and evidence separation tests

**Primary file:** `test_opinion_queries.py`

**Responsibilities:**
- Check that opinion questions route to community sources while factual questions
  prefer official sources.
- Keep official and community evidence types separate when synthesizing the final
  answer.
- Ensure mixed queries do not silently substitute unrelated sources.

**Test pattern:**
- Call `fetch_from_search_agent` directly for the no-community-evidence case.
- Assert that the system returns insufficient evidence rather than inventing a
  source-backed answer.

### 4. API and integration tests

**Primary file:** `test_query_integration.py`

**Responsibilities:**
- Validate prompt construction, agent response behavior, and FastAPI endpoints.
- Confirm multi-turn session history and TTL-related data handling.
- Check health status, validation behavior, and blank-question rejection.

**Test pattern:**
- Use `TestClient` to issue API requests against the app.
- Mock Bedrock and search calls so only API/session behavior is exercised.
- Verify output contracts and error responses rather than live-provider behavior.

---

## Cross-test rules

- **Keep tests deterministic** by replacing remote calls with stubs or mock
  responses where necessary.
- **Test real behavior**, not mock behavior: assert on the actual agent and API
  outputs rather than on the mock call count alone.
- **Prefer controlled evidence** over live network access so failures point to
  logic issues rather than flaky external dependencies.
- **Validate both planning and final output**: route selection, evidence choice,
  and final answer shaping are all part of the contract.

## Workflow

1. The test harness sets up local config or stubbed dependencies before invoking
   an agent, service, or endpoint.
2. Planning tests validate intent classification, target selection, and query
   generation before retrieval occurs.
3. Retrieval tests feed controlled official, community, digest, or report
   evidence and verify grounding and insufficiency handling.
4. Integration tests hit the API layer and verify session persistence, validation,
   and routed responses.
5. Assertions confirm the returned answers, structured plans, tool results, HTTP
   responses, and session state all match the expected contract.
