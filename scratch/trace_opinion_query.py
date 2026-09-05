import os
import sys
from pprint import pprint

# Set router mode to llm to trace the live pipeline
os.environ["ROUTER_MODE"] = "llm"
os.environ["USE_LOCAL_STUBS"] = "1"

# Add paths
sys.path.insert(0, "/Users/jhmacbook/Roulette-Kaki/query_agent/backend")

from agents.main_agent import create_search_plan
from services.search_service import fetch_from_search_agent, execute_search_policy
from agents.query import build_prompt, answer_question

question = "What are public opinions about BTO in Singapore?"
print("=" * 60)
print(f"TRACING: '{question}'")
print("=" * 60)

# 1. Main Agent plan
plan = create_search_plan(question)
print("\n1. MAIN AGENT PLAN:")
print(f"   Intent: {plan.intent}")
print(f"   Topic: {plan.topic}")
print(f"   Target: {plan.target}")
print(f"   Time Scope: {plan.time_scope}")
print(f"   Resolved Query: '{plan.resolved_query}'")

# 2. agents_to_invoke
print(f"\n2. AGENTS TO INVOKE: {plan.agents_to_invoke}")

# 3. official_queries
print(f"\n3. OFFICIAL QUERIES: {plan.search_queries.official}")

# 4. community_queries
print(f"\n4. COMMUNITY QUERIES: {plan.search_queries.community}")

# 5. Search Agent response
need_official = "official_search" in plan.agents_to_invoke
need_community = "community_search" in plan.agents_to_invoke

search_result = fetch_from_search_agent(
    question=plan.resolved_query,
    need_official=need_official,
    need_community=need_community,
    official_queries=plan.search_queries.official,
    community_queries=plan.search_queries.community,
    plan_dict=plan.model_dump(),
)

print("\n5. SEARCH AGENT RESPONSE KEYS:")
print(list(search_result.keys()))
print("\n   Search Summary Preview:")
print(search_result.get("search_summary", "")[:400])

# 6. number of official sources returned
official_sources = search_result.get("official_sources", [])
print(f"\n6. NUMBER OF OFFICIAL SOURCES: {len(official_sources)}")
for s in official_sources:
    print(f"   - {s.get('title')} ({s.get('url')})")

# 7. number of community sources returned
community_sources = search_result.get("unofficial_sources", [])
print(f"\n7. NUMBER OF COMMUNITY SOURCES: {len(community_sources)}")
for s in community_sources:
    print(f"   - {s.get('title')} ({s.get('url')})")

# 8. current_applicable_source
current_applicable = search_result.get("current_applicable_source")
print(f"\n8. CURRENT APPLICABLE SOURCE: {current_applicable.get('title') if current_applicable else 'None'}")

# 9. community_insights
community_insights = search_result.get("community_insights", [])
print(f"\n9. COMMUNITY INSIGHTS: {len(community_insights)} items")
for c in community_insights:
    print(f"   - {c}")

# 10. final Query Agent prompt
final_prompt = build_prompt(
    question=question,
    official_sources=official_sources,
    unofficial_sources=community_sources,
    search_agent_data=search_result.get("search_summary"),
    current_applicable_source=current_applicable,
    query_intent=plan.intent,
    rewritten_query=plan.resolved_query,
)
print("\n10. FINAL QUERY AGENT PROMPT (FIRST 1500 CHARS):")
print(final_prompt[:1500])

print("\n" + "=" * 60)
print("CALLING answer_question():")
print("=" * 60)
ans = answer_question(question)
print("\nFINAL ANSWER:")
print(ans)
