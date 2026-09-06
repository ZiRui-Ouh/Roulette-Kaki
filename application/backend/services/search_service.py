"""
Search integration service.

Wraps `agents.search.gather_and_search` with an optional HTTP fallback to a
remote deployment (via `SEARCH_AGENT_URL`) for split-service topologies.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agents.search import gather_and_search

log = logging.getLogger(__name__)

# This boundary supports both deployment choices: call a remote Search Agent
# when configured, or use the local search module with the same result shape.

def fetch_from_search_agent(
    question: str,
    urls: list[str] | None = None,
    provided_sources: list[dict] | None = None,
    conversation_context: list[dict] | None = None,
    need_official: bool = True,
    need_community: bool = True,
    official_queries: list[str] | None = None,
    community_queries: list[str] | None = None,
    plan_dict: dict | None = None,
) -> dict[str, Any]:
    """
    Invoke the Search Agent to gather official and unofficial data.

    Returns:
        dict with keys:
            - official_sources: list[dict]
            - unofficial_sources: list[dict]
            - current_applicable_source: dict | None
            - conflicting_sources: list[dict]
            - official_policy_facts: list[dict]
            - community_insights: list[dict]
            - query_intent: str
            - rewritten_query: str
            - search_summary: str
    """
    # Check if an external HTTP search agent service is configured
    search_agent_url = os.environ.get("SEARCH_AGENT_URL")
    if search_agent_url:
        try:
            import requests

            resp = requests.post(
                f"{search_agent_url.rstrip('/')}/search",
                json={
                    "q": question,
                    "urls": urls or [],
                    "conversation_context": conversation_context or [],
                    "need_official": need_official,
                    "need_community": need_community,
                    "official_queries": official_queries or [],
                    "community_queries": community_queries or [],
                    "plan": plan_dict or {},
                },
                timeout=25,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "search_summary" in data:
                return data
            return {
                "official_sources": [],
                "unofficial_sources": [],
                "search_summary": data.get("answer", str(data)),
            }
        except Exception as exc:
            log.warning("HTTP call to Search Agent failed (%s), falling back to local module.", exc)

    # In-process call to the search agent module
    try:
        return gather_and_search(
            question=question,
            urls=urls,
            provided_sources=provided_sources,
            conversation_context=conversation_context,
            need_official=need_official,
            need_community=need_community,
            official_queries=official_queries,
            community_queries=community_queries,
            plan_dict=plan_dict,
        )
    except Exception as exc:
        log.error("Failed to invoke search agent: %s", exc)
        return {
            "official_sources": [],
            "unofficial_sources": [],
            "search_summary": f"Search agent encountered an issue: {exc}",
        }


def get_search_policy_tool_spec() -> dict:
    """Return the Amazon Bedrock Converse tool specification for search_policy."""
    return {
        "toolSpec": {
            "name": "search_policy",
            "description": (
                "Search and gather authoritative Singapore government policy data, official rules, "
                "numerical figures, deadlines, and community sentiment from Reddit/HardwareZone. "
                "Use this tool whenever up-to-date policy facts, figures, or community opinions are needed."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The specific factual or opinion query to search for.",
                        },
                        "target": {
                            "type": "string",
                            "enum": ["singles", "couples", "families", "seniors", "general", "executive_condominiums"],
                            "description": "Target demographic or category.",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Policy topic, e.g. BTO, CPF, MediShield, Cost-of-Living.",
                        },
                        "fact_type": {
                            "type": "string",
                            "enum": ["income_ceiling", "eligibility", "interest_rate", "payout_amount", "claim_limit", "training_allowance", "parental_leave", "parliament_debate", "coe_bidding", "psle_policy", "public_opinion", "pros_cons", "general"],
                            "description": "Type of fact or insight required.",
                        },
                        "housing_type": {
                            "type": "string",
                            "description": "Housing or flat type if applicable, e.g. 2-room Flexi, BTO, resale.",
                        },
                        "time_scope": {
                            "type": "string",
                            "enum": ["current", "historical", "upcoming"],
                            "description": "Time scope: current active rules vs historical.",
                        },
                        "need_official": {
                            "type": "boolean",
                            "description": "Set to True if official government facts, rules, or figures are needed.",
                        },
                        "need_community": {
                            "type": "boolean",
                            "description": "Set to True if public forum sentiment or discussions are needed.",
                        },
                        "official_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Targeted official search query strings.",
                        },
                        "community_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Targeted community search query strings.",
                        },
                    },
                    "required": ["question", "target", "topic", "fact_type", "need_official", "need_community"],
                }
            },
        }
    }


def evaluate_evidence_sufficiency(
    tool_input: dict,
    search_result: dict,
    current_facts: list[dict],
) -> tuple[bool, str | None]:
    """
    Evaluate whether retrieved evidence actually contains the requested fact.
    Identifies cases where a page was retrieved (e.g. HDB singles) but only contains
    irrelevant paragraphs (e.g. core member definitions) without the numerical ceiling.
    """
    fact_type = tool_input.get("fact_type", "general")
    target = tool_input.get("target", "general")
    need_official = tool_input.get("need_official", True)
    need_community = tool_input.get("need_community", False)

    official_sources = search_result.get("official_sources", [])
    unofficial_sources = search_result.get("unofficial_sources", [])
    search_summary = search_result.get("search_summary", "")

    # Check official source requirement
    if need_official and not official_sources:
        return False, "No official government sources were retrieved."

    # Check community requirement
    if need_community and not unofficial_sources and not search_result.get("community_insights"):
        return False, "Insufficient public discussion evidence was found in available community sources."

    # Fact-type specific evaluation
    if fact_type in ("public_opinion", "pros_cons"):
        if not unofficial_sources and not search_result.get("community_insights"):
            return False, "Insufficient public discussion evidence was found in available community sources."
        return True, None

    if fact_type == "income_ceiling":
        # Check if any fact has a dollar value matching the target demographic
        has_matching_figure = False
        for f in current_facts:
            cat = f.get("category", "")
            val = f.get("value", "")
            if "$" in val or "8,000" in val or "16,000" in val or "18,000" in val:
                if target == "singles" and ("single" in cat or "8,000" in val):
                    has_matching_figure = True
                    break
                elif target in ("families", "couples") and ("famil" in cat or "16,000" in val):
                    has_matching_figure = True
                    break
                elif target == "executive_condominiums" and ("ec" in cat or "18,000" in val):
                    has_matching_figure = True
                    break
                elif target == "general":
                    has_matching_figure = True
                    break

        if not has_matching_figure:
            # Check raw source text for numerical income ceiling pattern
            raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
            if target == "singles":
                if "$8,000" in raw_text or "8,000" in raw_text:
                    has_matching_figure = True
            elif target in ("families", "couples"):
                if "$16,000" in raw_text or "16,000" in raw_text:
                    has_matching_figure = True
            elif target == "executive_condominiums":
                if "$18,000" in raw_text or "18,000" in raw_text:
                    has_matching_figure = True

        if not has_matching_figure:
            return (
                False,
                f"Retrieved official source contains eligibility text, but does NOT specify the numerical income ceiling for {target}.",
            )

    elif fact_type == "interest_rate":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not ("2.5%" in raw_text or "4%" in raw_text or "4.0%" in raw_text):
            return False, "No interest rate percentages (e.g. 2.5%, 4.0%) were found in retrieved sources."

    elif fact_type == "payout_amount":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["$", "payout", "payment", "September", "disbursement"]):
            return False, "No payout figures or disbursement schedules were found in retrieved sources."

    elif fact_type == "claim_limit":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["$200,000", "200,000", "claim limit", "$5,140", "$1,630", "MediShield"]):
            return False, "No MediShield claim limit figures were found in retrieved sources."

    elif fact_type == "training_allowance":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["$4,000", "4,000", "$3,000", "3,000", "SkillsFuture", "training allowance"]):
            return False, "No SkillsFuture credit or training allowance figures were found in retrieved sources."

    elif fact_type == "parental_leave":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["10 weeks", "6 weeks", "$2,500", "Shared Parental Leave", "parental leave"]):
            return False, "No shared parental leave weeks or wage cap figures were found in retrieved sources."

    elif fact_type == "parliament_debate":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["Parliament", "Hansard", "Topic", "Motion", "Sitting", "Debate"]):
            return False, "No parliamentary debate records or topics were found in retrieved sources."

    elif fact_type == "coe_bidding":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["Cat A", "Cat B", "Cat C", "Cat E", "Quota Premium", "COE", "bidding"]):
            return False, "No COE quota premium or category bidding results were found in retrieved sources."

    elif fact_type == "psle_policy":
        raw_text = " ".join([s.get("content", "") for s in official_sources]) + " " + search_summary
        if not any(token in raw_text for token in ["AL", "Achievement Level", "Posting Group", "Full SBB", "PSLE", "scoring"]):
            return False, "No PSLE scoring system or secondary posting rules were found in retrieved sources."

    return True, None


def execute_search_policy(
    tool_input: dict,
    conversation_context: list[dict] | None = None,
) -> dict:
    """
    Execute search_policy tool: calls the Search Agent, runs verification,
    evaluates fact sufficiency, and packages a structured evidence result.
    """
    from schemas import MainAgentPlan, SearchQueries
    from services.verification import verify_evidence

    question = tool_input.get("question", "")
    target = tool_input.get("target", "general")
    topic = tool_input.get("topic", "Singapore Policy")
    fact_type = tool_input.get("fact_type", "general")
    time_scope = tool_input.get("time_scope", "current")
    need_official = tool_input.get("need_official", True)
    need_community = tool_input.get("need_community", False)
    official_queries = tool_input.get("official_queries", [])
    community_queries = tool_input.get("community_queries", [])

    # Map tool input into a MainAgentPlan for compatibility with existing verification
    intent = "eligibility" if fact_type == "income_ceiling" else ("public_opinion" if fact_type == "public_opinion" else "policy_fact")
    agents_to_invoke = []
    if need_official:
        agents_to_invoke.append("official_search")
    if need_community:
        agents_to_invoke.append("community_search")
    agents_to_invoke.append("verification")

    plan = MainAgentPlan(
        intent=intent,
        topic=topic,
        target=target,
        location="Singapore",
        time_scope=time_scope,
        is_follow_up=bool(conversation_context),
        resolved_query=question,
        agents_to_invoke=agents_to_invoke,
        search_queries=SearchQueries(official=official_queries, community=community_queries),
        reasoning_summary=f"search_policy tool execution for {topic} ({target})",
    )

    # 1. Dispatch search
    search_result = fetch_from_search_agent(
        question=question,
        conversation_context=conversation_context,
        need_official=need_official,
        need_community=need_community,
        official_queries=official_queries,
        community_queries=community_queries,
        plan_dict=plan.model_dump(),
    )

    official_sources = search_result.get("official_sources", [])
    unofficial_sources = search_result.get("unofficial_sources", [])

    # 2. Run verification
    verification_res = verify_evidence(
        official_sources=official_sources,
        unofficial_sources=unofficial_sources,
        plan=plan,
    )

    facts = (
        verification_res.historical_facts
        if time_scope == "historical"
        else (verification_res.current_facts or verification_res.historical_facts)
    )
    facts_dicts = [f.model_dump() for f in facts]
    if not facts_dicts:
        fallback_facts = search_result.get("official_policy_facts") or search_result.get("extracted_facts", [])
        if fallback_facts:
            facts_dicts = fallback_facts

    # 3. Evaluate sufficiency
    is_sufficient, reason = evaluate_evidence_sufficiency(tool_input, search_result, facts_dicts)

    return {
        "is_sufficient": is_sufficient,
        "insufficiency_reason": reason,
        "target": target,
        "topic": topic,
        "fact_type": fact_type,
        "primary_source": verification_res.primary_source,
        "extracted_facts": facts_dicts,
        "official_sources": official_sources,
        "unofficial_sources": unofficial_sources,
        "conflicts": verification_res.conflicts,
        "community_insights": verification_res.community_insights,
        "search_summary": search_result.get("search_summary", ""),
    }


