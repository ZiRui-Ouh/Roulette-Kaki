"""
Main Agent / Orchestrator for Roulette-Kaki Policy Intelligence.

Responsible for:
1. Intent classification via Amazon Nova
2. Conversation context resolution and elliptical query rewriting
3. Formulating a structured execution plan (search queries, target demographic, time scope)
4. Determining which sub-agents (official_search, community_search, verification) to invoke
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

from schemas import MainAgentPlan, SearchQueries
from services import bedrock

log = logging.getLogger(__name__)

MAIN_AGENT_SYSTEM_PROMPT = """
You are the Main Orchestrator Agent for Singapore Policy and Legislative Intelligence.
Your task is to analyze the user's question, examine previous conversation history, and produce a structured execution plan in STRICT JSON.

==================================================
1. INTENT CLASSIFICATION RULES
==================================================
Classify the user's intent into EXACTLY ONE of:
- "eligibility": Qualifying criteria, household income ceilings, age limits, citizenship requirements, flat ownership rules, MOP.
- "policy_fact": Official government figures, CPF interest rates, payout amounts, statutory parameters, legal schemes.
- "public_opinion": Public sentiment, what people think, feelings, community reactions, forum discussions.
- "user_experience": Personal experiences, typical waiting times, application hurdles, renovation challenges, lived reality.
- "pros_cons": Advantages and disadvantages, benefits and drawbacks, trade-offs of a policy or scheme.
- "comparison": Comparing two or more schemes, flat types, or options (e.g. BTO vs Resale, OA vs SA).
- "process/how_to": Application steps, procedures, how-to guides, document requirements.
- "announcement/update": Recent news releases, policy changes, upcoming sales launches.
- "follow_up": Elliptical follow-up to previous turns (will inherit previous intent/topic).
- "unclear": Vague or ambiguous queries that cannot be resolved.

CRITICAL INTENT DISTINCTIONS:
- "What are people's opinions on BTO?" -> public_opinion
- "What do people think about BTO?" -> public_opinion
- "Are people happy with BTO?" -> public_opinion
- "How long do people usually wait for BTO?" -> user_experience
- "What are the pros and cons of BTO?" -> pros_cons
- "What is the BTO income ceiling?" -> eligibility
- "What is the CPF OA interest rate?" -> policy_fact
- "How do I apply for BTO?" -> process/how_to
- "What is the BTO income ceiling and what do people think about it?" -> eligibility (with both official and community agents invoked)

==================================================
2. CONVERSATION CONTEXT & FOLLOW-UP INHERITANCE
==================================================
If previous conversation turns exist, inspect them carefully!
A short follow-up question (e.g. "What about for couples?", "What about resale?", "And for singles?", "What are the downsides?")
MUST inherit the previous turn's intent and topic unless the user clearly introduces a completely new topic.

EXAMPLES OF CONTEXT INHERITANCE:
- Turn 1: "What are people's opinions on BTO in Singapore?" (intent=public_opinion, topic=BTO)
  Turn 2: "What about for couples?"
  -> intent: "public_opinion"
  -> topic: "BTO"
  -> target: "couples"
  -> resolved_query: "What are couples' opinions and experiences with BTO in Singapore?"
  -> agents_to_invoke: ["community_search", "verification"]
  (DO NOT classify as eligibility merely because "couples" appears!)

- Turn 1: "What is the BTO income ceiling?" (intent=eligibility, topic=BTO)
  Turn 2: "What about for couples?"
  -> intent: "eligibility"
  -> topic: "BTO"
  -> target: "couples"
  -> resolved_query: "What is the BTO income ceiling for couples and families in Singapore?"
  -> agents_to_invoke: ["official_search", "verification"]

- Turn 1: "How long do people usually wait for BTO?" (intent=user_experience, topic=BTO)
  Turn 2: "What about for couples?"
  -> intent: "user_experience"
  -> topic: "BTO"
  -> target: "couples"
  -> resolved_query: "How long do couples usually wait for BTO and what are their experiences in Singapore?"
  -> agents_to_invoke: ["community_search", "verification"]

- Turn 1: "What are the pros and cons of BTO?" (intent=pros_cons, topic=BTO)
  Turn 2: "What about for couples?"
  -> intent: "pros_cons"
  -> topic: "BTO"
  -> target: "couples"
  -> resolved_query: "What are the pros and cons of BTO for couples in Singapore?"
  -> agents_to_invoke: ["community_search", "verification"]

==================================================
3. TIME SCOPE
==================================================
- "current": Asking about prevailing/active rules, e.g. "What is the current BTO income ceiling for singles?"
- "historical": Asking about previous/past rules, e.g. "What was the previous BTO income ceiling for singles?"
- "upcoming": Asking about future schedules, e.g. "When will the next BTO launch take place?"
- "general": General timeless information.

==================================================
4. AGENT ROUTING RULES
==================================================
- If the question asks for policy rules, eligibility, income ceilings, figures, grants, deadlines:
  * agents_to_invoke: ["official_search", "verification"]
  * search_queries.official: Generate 1-2 targeted official queries
  * search_queries.community: [] (leave empty unless public opinions are also asked)

- If the question asks for public opinions, sentiments, user experiences, pros/cons:
  * agents_to_invoke: ["community_search", "verification"]
  * search_queries.community: Generate 1-2 targeted forum/discussion queries (Reddit, HardwareZone)
  * search_queries.official: Optionally add 1 official query if factual background is needed, but community_search MUST be invoked.

- If the question asks for BOTH policy facts and public opinions:
  (e.g. "What is the BTO income ceiling and what do people think about it?")
  * agents_to_invoke: ["official_search", "community_search", "verification"]
  * search_queries.official: [targeted official queries]
  * search_queries.community: [targeted community queries]

==================================================
5. STRICT JSON OUTPUT FORMAT
==================================================
You MUST return ONLY a valid JSON object matching this schema:
{
  "intent": "eligibility" | "policy_fact" | "public_opinion" | "user_experience" | "pros_cons" | "comparison" | "process/how_to" | "announcement/update" | "follow_up" | "unclear",
  "topic": "Primary topic (e.g. BTO, CPF, MediShield)",
  "target": "Target demographic (e.g. singles, couples, families, seniors, general)",
  "location": "Singapore",
  "time_scope": "current" | "historical" | "upcoming" | "general",
  "is_follow_up": true | false,
  "resolved_query": "Standalone unambiguous query incorporating context",
  "agents_to_invoke": ["official_search", "verification"] or ["community_search", "verification"] or ["official_search", "community_search", "verification"],
  "search_queries": {
    "official": ["..."],
    "community": ["..."]
  },
  "reasoning_summary": "Brief explanation of routing rationale"
}

Do NOT wrap in markdown fences (```json), do not include any preamble, commentary, or postscript.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(raw_text: str) -> dict:
    """Safely extract and decode a JSON object from text."""
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()

    match = _JSON_BLOCK_RE.search(clean_text)
    if not match:
        raise ValueError(f"No JSON object found in response: {clean_text[:200]}")
    return json.loads(match.group(0))


def _build_context_prompt(question: str, conversation_context: list[dict] | None = None) -> str:
    """Format prompt with previous turns and current query for the Main Agent."""
    history_str = "None (first turn in session)"
    if conversation_context:
        formatted_turns = []
        for msg in conversation_context[-6:]:
            role = "USER" if msg.get("role") == "user" else "ASSISTANT"
            content = msg.get("content", "").strip()
            if content:
                # Truncate assistant turns to avoid overloading the context window
                truncated_content = content[:300] + "..." if len(content) > 300 else content
                formatted_turns.append(f"{role}: {truncated_content}")
        if formatted_turns:
            history_str = "\n".join(formatted_turns)

    return f"""{MAIN_AGENT_SYSTEM_PROMPT}

==================================================
CONVERSATION CONTEXT (PREVIOUS TURNS)
==================================================
{history_str}

==================================================
CURRENT USER QUESTION
==================================================
{question}

Return ONLY the JSON execution plan.
"""


def _safe_fallback_plan(question: str, conversation_context: list[dict] | None = None) -> MainAgentPlan:
    """Deterministic fallback plan if LLM parsing completely fails."""
    log.warning("Main Agent using safe fallback plan for question: %s", question)
    curr_q = question.strip()
    curr_q_lower = curr_q.lower()

    history_text = ""
    if conversation_context:
        history_text = " ".join(msg.get("content", "") for msg in conversation_context).lower()
    has_history = bool(conversation_context)

    # Target demographic detection
    target = "general"
    if "single" in curr_q_lower:
        target = "singles"
    elif "couple" in curr_q_lower:
        target = "couples"
    elif "famil" in curr_q_lower:
        target = "families"
    elif "senior" in curr_q_lower:
        target = "seniors"
    elif "ec" in curr_q_lower or "executive" in curr_q_lower:
        target = "executive_condominiums"

    # Topic detection
    topic = "BTO" if ("bto" in curr_q_lower or "bto" in history_text) else "Singapore Policy"
    if "cpf" in curr_q_lower or "cpf" in history_text:
        topic = "CPF"

    # Temporal scope
    time_scope = "historical" if any(w in curr_q_lower for w in ["previous", "past", "prior", "before", "history", "was the"]) else "current"

    # Follow-up detection
    is_followup = has_history and (any(curr_q_lower.startswith(w) for w in ["what about", "how about", "and for", "what of", "what if"]) or len(curr_q.split()) <= 5)

    # Intent resolution
    intent = "policy_fact"
    if is_followup:
        if any(w in history_text for w in ["opinion", "think", "feel", "sentiment"]):
            intent = "public_opinion"
        elif any(w in history_text for w in ["pros and cons", "pros & cons", "advantages", "disadvantages"]):
            intent = "pros_cons"
        elif any(w in history_text for w in ["how long", "wait", "waiting time"]):
            intent = "user_experience"
        elif any(w in history_text for w in ["income ceiling", "ceiling", "eligibility", "criteria", "qualify"]):
            intent = "eligibility"
    else:
        has_opinion_words = any(w in curr_q_lower for w in ["opinion", "think", "feel", "sentiment"])
        has_pros_cons = any(w in curr_q_lower for w in ["pros and cons", "pros & cons"])
        has_experience = any(w in curr_q_lower for w in ["how long", "waiting time", "experience"])
        has_policy_words = any(w in curr_q_lower for w in ["income ceiling", "ceiling", "grant", "rate", "eligib", "criteria", "qualify"])

        if has_opinion_words:
            intent = "public_opinion"
        elif has_pros_cons:
            intent = "pros_cons"
        elif has_experience:
            intent = "user_experience"
        elif has_policy_words:
            intent = "eligibility" if ("ceiling" in curr_q_lower or "eligib" in curr_q_lower) else "policy_fact"

    # Dual query check
    has_both = (any(w in curr_q_lower for w in ["opinion", "think"]) and any(w in curr_q_lower for w in ["income ceiling", "ceiling"]))

    # Agents to invoke
    if has_both:
        agents = ["official_search", "community_search", "verification"]
        official_queries = [f"{topic} income ceiling {target} gov.sg"]
        community_queries = [f"{topic} {target} opinions reddit singapore"]
    elif intent in ("public_opinion", "user_experience", "pros_cons"):
        agents = ["community_search", "verification"]
        official_queries = []
        community_queries = [f"{curr_q} reddit singapore hardwarezone"]
    else:
        agents = ["official_search", "verification"]
        official_queries = [f"{topic} {curr_q} site:gov.sg"]
        community_queries = []

    # Resolved query
    if is_followup:
        if intent == "public_opinion":
            resolved = f"What are {target}' opinions and experiences with {topic} in Singapore?"
        elif intent == "pros_cons":
            resolved = f"What are the pros and cons of {topic} for {target} in Singapore?"
        elif intent == "user_experience":
            resolved = f"What are {target}' waiting times and experiences with {topic} in Singapore?"
        else:
            resolved = f"What is the {topic} income ceiling and eligibility for {target} in Singapore?"
    else:
        resolved = curr_q

    return MainAgentPlan(
        intent=intent,
        topic=topic,
        target=target,
        location="Singapore",
        time_scope=time_scope,
        is_follow_up=is_followup,
        resolved_query=resolved,
        agents_to_invoke=agents,
        search_queries=SearchQueries(
            official=official_queries,
            community=community_queries,
        ),
        reasoning_summary=f"Safe fallback plan: Orchestrated {intent} plan regarding {topic} ({target}).",
    )


def create_search_plan(
    question: str,
    conversation_context: list[dict] | None = None,
) -> MainAgentPlan:
    """
    Main Agent entrypoint: analyze question & conversation context via Amazon Nova
    and produce a validated MainAgentPlan.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    prompt = _build_context_prompt(question, conversation_context)

    try:
        raw_output = bedrock.ask_nova(prompt, max_tokens=1024)
        parsed_dict = _extract_json_object(raw_output)
        plan = MainAgentPlan.model_validate(parsed_dict)
        log.info(
            "Main Agent resolved plan: intent=%s, topic=%s, target=%s, agents=%s, resolved_query=%s",
            plan.intent,
            plan.topic,
            plan.target,
            plan.agents_to_invoke,
            plan.resolved_query,
        )
        return plan
    except Exception as exc:
        log.warning("Main Agent planning failed (%s). Falling back to safe default plan.", exc)
        return _safe_fallback_plan(question, conversation_context)
