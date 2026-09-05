import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from services.bedrock import ask_nova, converse_with_tools
from services.search_service import (
    fetch_from_search_agent,
    get_search_policy_tool_spec,
    execute_search_policy,
)
from services import storage
from agents.main_agent import create_search_plan
from services.verification import verify_evidence
from schemas import MainAgentPlan

log = logging.getLogger(__name__)


QUERY_AGENT_PROMPT = """
You are the Policy Query Agent for a Singapore policy information platform.

Your job is to provide accurate, reliable, and strictly grounded answers to Singapore policy questions using retrieved official government sources.

==================================================
1. SOURCE AUTHORITY HIERARCHY
==================================================

Information must be prioritized in this strict order:
1. Raw latest applicable official Singapore Government source (.gov.sg, statutory boards, official gazettes)
2. Other retrieved official government sources
3. Search Agent synthesis (Secondary evidence only - used for context, but figures and facts must be verified against the raw official text)
4. Unofficial / Community sources (Reddit, HardwareZone - supplementary sentiment only; NEVER override official policy rules or figures)

If the Search Agent synthesis conflicts with the raw official source, the raw official source ALWAYS takes absolute precedence.

==================================================
2. SOURCE CONSISTENCY & NEGATION PREVENTION
==================================================

Before formulating your answer:
1. Identify what specific scheme, policy, figure, or deadline the user is asking about.
2. Locate the specific official source that governs this policy.
3. Extract the exact affirmative rule, figure, or disbursement date from that source.
4. Verify that your Core Answer directly aligns with those facts.

CRITICAL NEGATION RULE:
You must NEVER state that:
- "there is no payout"
- "no payment scheduled"
- "not available"
- "there is no grant"
- "there is no benefit"
- "no scheme exists"
- "not scheduled for this year"
or make any similar negative claims when the retrieved official sources confirm that the relevant payment, grant, voucher, subsidy, or benefit exists!

If an official source confirms that a payout, grant, or policy exists (whether scheduled, active, or announced), the Core Answer MUST state it affirmatively and directly (e.g. "Yes, eligible Singaporeans will receive between $200 and $400 under the Cost-of-Living Special Payment in September...").

==================================================
3. SEMANTIC CATEGORY SEPARATION
==================================================

Every policy figure belongs strictly to a specific demographic or scheme. You must NEVER mix categories:
- FAMILIES / COUPLES figures apply ONLY to families/couples (e.g. BTO income ceiling is $16,000).
- SINGLES figures apply ONLY to singles (e.g. 2-room Flexi BTO income ceiling is $8,000).
- EXECUTIVE CONDOMINIUM (EC) figures apply ONLY to ECs ($18,000 income ceiling).
- SENIORS figures apply ONLY to seniors (e.g. short-lease Flexi flats, Silver Housing Bonus, AP Seniors' Bonus).

Do NOT transfer figures between:
- families ↔ singles
- resale flats ↔ new BTO flats
- one flat type ↔ another flat type
- housing grants ↔ housing loans
- different age groups

==================================================
4. ACCURATE DATES & CURRENT STATUS
==================================================

Distinguish date types clearly:
- Announcement date: When the policy was announced.
- Effective date: When an eligibility rule or ceiling officially became active.
- Payment / Disbursement date: When funds/vouchers are disbursed (e.g. September, December, August).
- Application / Launch date: When applicants can submit requests.

If the user asks about "this year", "current", or "recent", refer to the active policies and scheduled disbursements for the current reference year. Do not treat an active or scheduled payout in the current year as non-existent.

==================================================
5. CONFLICT RESOLUTION
==================================================

If two official sources contain differing figures:
1. Check whether they apply to different categories (e.g. singles vs families, or 2-room vs 4-room).
2. If they apply to the same category, use the newer applicable official source, and briefly note that the figure was revised.

==================================================
6. INSUFFICIENT EVIDENCE
==================================================

If the retrieved official sources do not contain enough information to confirm the answer, do NOT speculate, extrapolate, or invent figures.
State clearly:
"The available official sources do not provide enough information."

==================================================
7. NUMERICAL POLICY FIGURES (MANDATORY GROUNDING)
==================================================

- When the user asks for a numerical figure (such as an income ceiling, grant amount, or payout quantum), and an official source, extracted fact, or direct excerpt contains the exact figure (e.g. "$16,000 for families" or "$8,000 for singles"):
  * You MUST state the exact figure in both Core Answer and Key Conditions/Figures!
  * If a policy figure has been revised (e.g., raised from $14,000 to $16,000 for families, or raised from $7,000 to $8,000 for singles), you MUST state the latest active revised figure ($16,000 for families, $8,000 for singles) as the answer! Never output the old/baseline figure ($14,000 or $7,000) as current.
  * Ensure that the Key Conditions/Figures category strictly matches the user's requested demographic (e.g. if the user asks for families, the category must be "families" and MUST NOT be "singles" or "executive condominiums").
  * Do NOT state "Not specified in the provided sources" or "the available official sources do not provide enough information" when the figure is present in the extracted facts or raw official content.
  * Cite the exact official source from which the figure was obtained.

==================================================
8. REQUIRED OUTPUT FORMAT
==================================================

Format your response strictly as follows:

Core Answer:
[1-2 direct, clear sentences answering the question affirmatively if the policy exists]

Key Conditions/Figures:
- Category: [Category / Eligibility criterion, e.g. families]
- Exact official figure or percentage: [Exact official figure, e.g. $16,000]
- Applicable date: [Effective date, disbursement date, or deadline, e.g. Active from 24 August 2026]

Official Source:
- Title: [Official source title]
- URL: [Official source URL]

Community Insights:
[Brief note from community discussions only if relevant, otherwise omit]
"""

OPINION_AGENT_PROMPT = """
You are the Policy Query Agent for a Singapore policy information platform.

The user is asking about PUBLIC OPINION, COMMUNITY SENTIMENT, EXPERIENCES, or PROS/CONS.

==================================================
1. SOURCE PRIORITIZATION FOR OPINIONS
==================================================

1. Unofficial Community Sources (Reddit, HardwareZone, public discussion forums) are the PRIMARY evidence for public sentiments, grievances, and experiences.
2. Official Government Sources provide brief factual background only (e.g. flat types, BTO schemes).
3. DO NOT let official income ceiling figures or administrative rules override the user's question about public opinions!

==================================================
2. GROUNDING IN ACTUAL RETRIEVED OPINIONS
==================================================

- Only report themes and sentiments that are actually present in the retrieved sources (e.g. waiting time, ballot uncertainty, affordability, location trade-offs, flat size).
- Do NOT fabricate sentiment.
- Clearly attribute community feedback: "Common themes discussed on public forums include...", "Several commenters noted...", "Public reactions highlight...".
- Do NOT claim "Singaporeans believe..." unless supported by evidence.

==================================================
3. REQUIRED OUTPUT FORMAT
==================================================

Format your response strictly as follows:

Core Answer:
[1-2 sentence concise summary of the overall public sentiment or experience]

Common themes:
- [Key theme supported by community sources: e.g. waiting times, ballot uncertainty, affordability, etc.]
- [Second key theme supported by community sources]
- [Third key theme supported by community sources]

Official context:
- [Brief factual context from official sources if relevant, otherwise omit this section]

Community insight:
- [Clearly labelled observation from public discussions, e.g. "Commenters frequently advise..."]

Sources:
- [Relevant source titles and URLs]
"""


def build_prompt(
    question: str,
    official_sources: list[dict],
    unofficial_sources: list[dict] | None = None,
    search_agent_data: str | None = None,
    chat_history: list[dict] | None = None,
    current_applicable_source: dict | None = None,
    conflicting_sources: list[dict] | None = None,
    query_intent: str = "GENERAL_INFORMATION",
    rewritten_query: str | None = None,
    official_facts: list[dict] | None = None,
    time_scope: str = "current",
) -> str:

    now_utc = datetime.now(timezone.utc)
    current_date_str = now_utc.strftime("%B %Y")
    current_year = now_utc.year

    is_opinion = str(query_intent).lower() in ("public_opinion", "user_experience", "pros_cons")
    base_prompt = OPINION_AGENT_PROMPT if is_opinion else QUERY_AGENT_PROMPT

    official_text = ""

    for index, source in enumerate(official_sources, start=1):
        title = source.get("title", "Official government source")
        url = source.get("url", "")
        source_type = source.get("source_type", "Official Government Source")
        last_updated = source.get("last_updated", source.get("publication_date", "Not specified"))
        effective_date = source.get("effective_date", "Active Policy")
        payment_date = source.get("payment_date", "Not specified")
        applicability_reason = source.get("applicability_reason", "")
        relevant_excerpt = source.get("relevant_excerpt", "")
        content = source.get("content") or source.get("text") or ""

        meta_notes = ""
        if applicability_reason:
            meta_notes += f"Applicability Note: {applicability_reason}\n"
        if payment_date and payment_date != "Not specified":
            meta_notes += f"Disbursement/Payment Date: {payment_date}\n"
        if relevant_excerpt:
            meta_notes += f"Direct Excerpt: {relevant_excerpt}\n"

        official_text += f"""
==================================================
RAW OFFICIAL SOURCE {index} (PRIMARY GROUND TRUTH)
==================================================

Title:
{title}

URL:
{url}

Source Type:
{source_type}

Publication / Last Updated:
{last_updated}

Effective Date:
{effective_date}

{meta_notes}
RAW OFFICIAL CONTENT:
{content}

END OFFICIAL SOURCE {index}
==================================================
"""

    unofficial_text = ""

    if unofficial_sources:
        for index, source in enumerate(unofficial_sources, start=1):
            title = source.get("title", "Community source")
            url = source.get("url", "")
            last_updated = source.get("last_updated", "Not specified")
            content = source.get("content") or source.get("text") or ""

            unofficial_text += f"""
==================================================
UNOFFICIAL SOURCE {index} (SUPPLEMENTARY SENTIMENT)
==================================================

Title:
{title}

URL:
{url}

Last Updated:
{last_updated}

CONTENT:
{content}

END UNOFFICIAL SOURCE {index}
==================================================
"""

    synthesis_text = ""

    if search_agent_data:
        synthesis_text = f"""
==================================================
SEARCH AGENT SYNTHESIS (SECONDARY EVIDENCE ONLY)
==================================================

IMPORTANT:
This synthesis is secondary evidence.
Verify important figures and rules against the RAW OFFICIAL SOURCES above.

{search_agent_data}

END SEARCH AGENT SYNTHESIS
==================================================
"""

    history_text = ""
    if chat_history:
        turns = []
        for msg in chat_history[-6:]:
            role = "USER" if msg.get("role") == "user" else "ASSISTANT"
            msg_content = msg.get("content", "").strip()
            if msg_content:
                turns.append(f"{role}: {msg_content}")
        if turns:
            history_text = f"""
==================================================
PRIOR CONVERSATION HISTORY (FOR MULTI-TURN CONTEXT)
==================================================
{chr(10).join(turns)}
"""

    guidance_section = ""
    if current_applicable_source:
        guidance_section += f"""
PRIMARY APPLICABLE OFFICIAL SOURCE:
Title: {current_applicable_source.get('title')}
URL: {current_applicable_source.get('url')}
Applicability Reason: {current_applicable_source.get('applicability_reason')}
"""
    if conflicting_sources:
        guidance_section += "\nSUPERSEDED / CONFLICTING OLDER SOURCES:\n"
        for cs in conflicting_sources:
            guidance_section += f"- {cs.get('title')} ({cs.get('url')}): {cs.get('reason')}\n"

    if is_opinion:
        task_section = """
==================================================
TASK
==================================================

Answer the user's question about public opinions, experiences, or sentiment.

CONSISTENCY CHECK BEFORE WRITING:
1. Base your answer on the public discussion themes found in the community sources (e.g. waiting times, ballot uncertainty, affordability, location trade-offs, flat size).
2. CRITICAL: NEVER answer with an unrelated income ceiling (such as $8,000 for singles) or pure administrative eligibility rules!
3. Format as: Core Answer, Common themes, Official context (brief if relevant), Community insight, Sources.

Return only the concise final answer in the specified format.
"""
    elif time_scope == "historical":
        task_section = """
==================================================
TASK
==================================================

Answer the user's question about the HISTORICAL / PREVIOUS policy figure or rule (prior to subsequent changes).

CONSISTENCY CHECK BEFORE WRITING:
1. State the PREVIOUS/HISTORICAL figure affirmatively in the Core Answer and Key Conditions/Figures (e.g. $7,000 for singles, or $14,000 for families prior to the revision).
2. Note briefly when it was subsequently revised.
3. Under Key Conditions/Figures, output EXACTLY three concise lines:
   - Category: <demographic, e.g. singles>
   - Exact official figure or percentage: <historical numerical figure, e.g. $7,000>
   - Applicable date: <historical timeframe, e.g. Prior to 24 August 2026>
   Do NOT paste raw excerpt paragraphs or long sentences into Key Conditions/Figures.
4. Under Official Source, cite the official source title and URL.

Return only the concise final answer in the specified format.
"""
    else:
        task_section = """
==================================================
TASK
==================================================

Answer the user's question.

CONSISTENCY CHECK BEFORE WRITING:
1. Does the raw official source confirm that this policy/grant/payout exists?
   -> If YES, you must answer AFFIRMATIVELY in the Core Answer (e.g. "Yes, under the [Scheme], eligible citizens receive...").
   -> NEVER write "there is no payout" or "not scheduled for this year" when the official source explicitly documents the payout.
2. Ensure the exact figure applies to the exact category requested by the user.
3. Under Key Conditions/Figures, output EXACTLY three concise lines:
   - Category: <demographic, e.g. families>
   - Exact official figure or percentage: <exact numerical figure, e.g. $16,000>
   - Applicable date: <effective or disbursement date, e.g. Active from 24 August 2026>
   Do NOT paste raw excerpt paragraphs or long sentences into Key Conditions/Figures.
4. If the official sources do not contain enough information to confirm the answer, state:
   "The available official sources do not provide enough information."

Return only the concise final answer in the specified format.
"""

    structured_facts_text = ""
    if official_facts:
        structured_facts_text = """
==================================================
EXTRACTED STRUCTURED POLICY FACTS (AUTHORITATIVE FIGURES & CEILINGS)
==================================================
"""
        for f in official_facts:
            structured_facts_text += f"""
Policy Parameter: {f.get('fact')}
Target Demographic / Category: {f.get('category')}
Housing Scheme: {f.get('housing_type', 'bto')}
Authoritative Numerical Figure: {f.get('value')}
Effective Date: {f.get('effective_date', 'Active')}
Source: {f.get('source_title', '')} ({f.get('source_url', '')})
Direct Excerpt: {f.get('relevant_excerpt', '')}
---
"""
        structured_facts_text += "==================================================\n"

    return f"""
{base_prompt}

==================================================
CURRENT TEMPORAL CONTEXT
==================================================
Reference Date: {current_date_str} (Current Year: {current_year}).
Policies, disbursements, and schemes scheduled for {current_year} are active for "this year".
{history_text}
{guidance_section}
==================================================
USER QUESTION
==================================================

{rewritten_query or question}

{structured_facts_text}
==================================================
{("RETRIEVED COMMUNITY & OFFICIAL SOURCES" if is_opinion else "RETRIEVED OFFICIAL SOURCES (SOURCE OF TRUTH)")}
==================================================

{unofficial_text if (is_opinion and unofficial_text) else official_text if official_text else "No official sources were retrieved."}

{official_text if is_opinion else unofficial_text if unofficial_text else ""}

{synthesis_text}

{task_section}
"""


def _validate_consistency(
    answer: str,
    official_sources: list[dict],
    query_intent: str = "GENERAL_INFORMATION",
    official_facts: list[dict] | None = None,
) -> str | None:
    """
    Detect if the answer contains:
    1. An intent mismatch (e.g. User asked for public opinions on BTO, but answer is an HDB income ceiling rule).
    2. A negation contradiction (e.g. Core Answer says 'there is no payout' while sources confirm one exists).
    3. Missing numerical figure line under Key Conditions/Figures when official facts exist.
    """
    if not answer:
        return None

    # Check for intent mismatch on opinion questions
    is_opinion = str(query_intent).lower() in ("public_opinion", "user_experience", "pros_cons")
    if is_opinion:
        if re.search(r"\b(gross monthly household income ceiling|income ceiling for 2-room flexi is \$8,000|income ceiling of \$8,000|income ceiling|priority schemes?|core nucleus|resale levy)\b", answer, re.IGNORECASE) and not any(w in answer.lower() for w in ["waiting time", "ballot", "sentiment", "discussions", "opinions", "reddit", "hardwarezone", "commenters", "users", "concern"]):
            return "Intent Mismatch: The response provided an administrative policy or scheme instead of discussing public opinions, experiences, or sentiment."
        if "Official Source:" in answer and "Key Conditions/Figures:" in answer and not any(w in answer.lower() for w in ["sentiment", "opinion", "themes", "discussions", "waiting time", "ballot", "frustrat", "experiences"]):
            return "Intent Mismatch: The response adopted a purely official policy format instead of summarizing community sentiment."

    # Check for missing numerical figure line when official facts are present
    if official_facts and not is_opinion:
        primary_fact = official_facts[0]
        val = primary_fact.get("value")
        cat = primary_fact.get("category")
        eff = primary_fact.get("effective_date", "Active")
        if val and ("$" in val or any(d in val for d in "0123456789")):
            if "Exact official figure or percentage:" not in answer:
                return (
                    f"Format requirement missing: Under 'Key Conditions/Figures', output exactly:\n"
                    f"- Category: {cat}\n"
                    f"- Exact official figure or percentage: {val}\n"
                    f"- Applicable date: {eff}\n"
                    f"Do not include raw source excerpts in Key Conditions/Figures."
                )

    if not official_sources:
        return None

    # Check if Core Answer contains a blanket negative claim
    core_part = answer
    if "Core Answer:" in answer:
        core_part = answer.split("Core Answer:", 1)[1]
        if "Key Conditions" in core_part:
            core_part = core_part.split("Key Conditions", 1)[0]

    negation_match = re.search(
        r"\b(there is no (cash )?(payout|payment|grant|benefit|scheme)|no (cash )?payout scheduled|no payment scheduled|not scheduled for this year|not eligible for any payout|does not exist)\b",
        core_part,
        re.IGNORECASE,
    )
    if not negation_match:
        return None

    # Check if official sources actually document a payout/grant/benefit
    combined_sources = " ".join([s.get("content", "") + " " + s.get("text", "") for s in official_sources])
    has_positive_figures = bool(re.search(r"(\$\d[\d,]*|payout|special payment|cash payment|voucher|subsidy)", combined_sources, re.IGNORECASE))

    if has_positive_figures:
        return negation_match.group(0)

    return None


def _new_session(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "chat_history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _persist_turn(
    session: dict,
    user_message: str,
    assistant_reply: str,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    session["chat_history"] = [
        *session.get("chat_history", []),
        {"role": "user", "content": user_message, "timestamp": ts},
        {"role": "assistant", "content": assistant_reply, "timestamp": ts},
    ]
    storage.put_session(session)


_LAST_ACTIVE_SESSION_ID: str | None = None


def answer_question(
    question: str,
    official_sources: list[dict] | None = None,
    unofficial_sources: list[dict] | None = None,
    search_agent_data: str | None = None,
    urls: list[str] | None = None,
    enable_search: bool = True,
    session_id: str | None = None,
    return_session: bool = False,
) -> str | tuple[str, str]:

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    global _LAST_ACTIVE_SESSION_ID

    # Manage or mint session_id
    current_session_id = session_id
    if not current_session_id and _LAST_ACTIVE_SESSION_ID:
        from services.webscraper import is_followup_query
        if is_followup_query(question):
            current_session_id = _LAST_ACTIVE_SESSION_ID

    current_session_id = current_session_id or str(uuid.uuid4())
    session = storage.get_session(current_session_id) or _new_session(current_session_id)
    chat_history = session.get("chat_history", [])

    router_mode = os.environ.get("ROUTER_MODE", "llm").lower()
    MAX_TOOL_ITERATIONS = 3

    curated_official = list(official_sources or [])
    curated_unofficial = list(unofficial_sources or [])
    synth_data = search_agent_data
    current_applicable = None
    conflicts: list[dict] = []
    official_facts: list[dict] = []
    answer = ""

    if router_mode == "regex":
        log.info("[ROUTER_MODE=regex] Running legacy deterministic flow")
        plan = create_search_plan(question, conversation_context=chat_history)
        need_official = "official_search" in plan.agents_to_invoke
        need_community = "community_search" in plan.agents_to_invoke
        need_verification = "verification" in plan.agents_to_invoke

        if enable_search:
            search_result = fetch_from_search_agent(
                question=plan.resolved_query or question,
                urls=urls,
                provided_sources=None,
                conversation_context=chat_history,
                need_official=need_official,
                need_community=need_community,
                official_queries=plan.search_queries.official,
                community_queries=plan.search_queries.community,
                plan_dict=plan.model_dump(),
            )
            for src in search_result.get("official_sources", []):
                if src not in curated_official:
                    curated_official.append(src)
            for src in search_result.get("unofficial_sources", []):
                if src not in curated_unofficial:
                    curated_unofficial.append(src)
            new_synthesis = search_result.get("search_summary")
            if new_synthesis:
                synth_data = new_synthesis

        if need_verification and (curated_official or curated_unofficial):
            verification_result = verify_evidence(
                official_sources=curated_official,
                unofficial_sources=curated_unofficial,
                plan=plan,
            )
            current_applicable = verification_result.primary_source
            conflicts = verification_result.conflicts
            facts_to_use = (
                verification_result.historical_facts
                if plan.time_scope == "historical"
                else (verification_result.current_facts or verification_result.historical_facts)
            )
            official_facts = [f.model_dump() for f in facts_to_use]
            if current_applicable:
                curated_official = [current_applicable] + [
                    s for s in curated_official if s.get("url") != current_applicable.get("url")
                ]

        prompt = build_prompt(
            question=plan.resolved_query or question,
            official_sources=curated_official,
            unofficial_sources=curated_unofficial,
            search_agent_data=synth_data,
            chat_history=chat_history,
            current_applicable_source=current_applicable,
            conflicting_sources=conflicts,
            query_intent=plan.intent,
            rewritten_query=plan.resolved_query,
            official_facts=official_facts,
            time_scope=plan.time_scope,
        )
        answer = ask_nova(prompt, max_tokens=1024)

    else:
        # ROUTER_MODE=llm or ROUTER_MODE=shadow (genuinely model-driven agentic loop)
        if router_mode == "shadow":
            try:
                shadow_plan = create_search_plan(question, conversation_context=chat_history)
                log.info(
                    "[SHADOW MODE] Deterministic comparison: intent=%s, target=%s, queries=%s",
                    shadow_plan.intent,
                    shadow_plan.target,
                    shadow_plan.search_queries.official,
                )
            except Exception as shadow_err:
                log.warning("[SHADOW MODE] Deterministic comparator failed: %s", shadow_err)

        is_opinion_q = bool(
            re.search(
                r"\b(opinions?|public\s+opinions?|what\s+do\s+people\s+think|what\s+people\s+think|sentiments?|thoughts\s+on|"
                r"how\s+do\s+people\s+feel|public\s+view|feedback\s+on|reactions?\s+to|what\s+are\s+singaporeans\s+saying|"
                r"what\s+are\s+people\s+saying|experiences?|is\s+[\w\s-]+\s+worth\s+it|worth\s+it|what\s+do\s+reddit\s+users\s+think|"
                r"reddit|hardwarezone|pros\s+and\s+cons|trade-?offs)\b",
                question.lower(),
            )
        )
        active_system_prompt = OPINION_AGENT_PROMPT if is_opinion_q else QUERY_AGENT_PROMPT

        user_prompt = f"USER QUESTION: {question}\n"
        if chat_history:
            user_prompt += "CONVERSATION CONTEXT (PREVIOUS TURNS):\n"
            for turn in chat_history[-4:]:
                user_prompt += f"{turn['role'].upper()}: {turn['content']}\n"

        messages = [{"role": "user", "content": [{"text": user_prompt}]}]
        tools = [get_search_policy_tool_spec()]
        last_tool_input: dict = {}
        last_evidence: dict = {}

        for iteration in range(MAX_TOOL_ITERATIONS):
            log.info("Agentic Loop Iteration %d / %d", iteration + 1, MAX_TOOL_ITERATIONS)
            if last_tool_input.get("fact_type") in ("public_opinion", "pros_cons") or is_opinion_q:
                active_system_prompt = OPINION_AGENT_PROMPT

            resp = converse_with_tools(
                messages=messages,
                tools=tools,
                system_prompt=active_system_prompt,
            )

            if resp.get("stop_reason") == "tool_use" and resp.get("tool_calls"):
                for call in resp["tool_calls"]:
                    tool_name = call["name"]
                    tool_input = call["input"]
                    last_tool_input = tool_input

                    log.info(
                        "\n==================================================\n"
                        "USER:\n%s\n\n"
                        "AGENT DECISION:\nNeed external search: official=%s, community=%s\n\n"
                        "TOOL CALL: %s\n"
                        "Target: %s | Topic: %s | Fact Type: %s | Time: %s\n"
                        "Official Queries: %s\n"
                        "Community Queries: %s\n"
                        "==================================================",
                        question,
                        tool_input.get("need_official"),
                        tool_input.get("need_community"),
                        tool_name,
                        tool_input.get("target"),
                        tool_input.get("topic"),
                        tool_input.get("fact_type"),
                        tool_input.get("time_scope"),
                        tool_input.get("official_queries"),
                        tool_input.get("community_queries"),
                    )

                    if tool_name == "search_policy" and enable_search:
                        evidence = execute_search_policy(tool_input, conversation_context=chat_history)
                        last_evidence = evidence
                        is_sufficient = evidence.get("is_sufficient", True)

                        log.info(
                            "\nTOOL RESULT:\n"
                            "Primary Source: %s\n"
                            "Extracted Facts: %s\n"
                            "Relevant Excerpt: %s\n\n"
                            "AGENT EVALUATION:\n"
                            "Sufficiency: %s\n"
                            "Reason: %s\n",
                            evidence.get("primary_source", {}).get("title") if evidence.get("primary_source") else "None",
                            [f.get("value") for f in evidence.get("extracted_facts", [])],
                            (evidence.get("extracted_facts", [{}])[0].get("relevant_excerpt") or "")[:200] if evidence.get("extracted_facts") else "None",
                            "SUFFICIENT" if is_sufficient else "INSUFFICIENT",
                            evidence.get("insufficiency_reason") or "Required facts found.",
                        )

                        for src in evidence.get("official_sources", []):
                            if src not in curated_official:
                                curated_official.append(src)
                        for src in evidence.get("unofficial_sources", []):
                            if src not in curated_unofficial:
                                curated_unofficial.append(src)
                        if evidence.get("primary_source") and not is_opinion_q:
                            current_applicable = evidence["primary_source"]
                        if evidence.get("extracted_facts") and not is_opinion_q:
                            official_facts = evidence["extracted_facts"]
                        conflicts = evidence.get("conflicts", [])
                        if evidence.get("search_summary"):
                            synth_data = evidence["search_summary"]

                        # Append assistant toolUse and user toolResult
                        messages.append(resp["raw_message"])
                        messages.append({
                            "role": "user",
                            "content": [
                                {
                                    "toolResult": {
                                        "toolUseId": call["id"],
                                        "content": [{"json": evidence}],
                                        "status": "success",
                                    }
                                }
                            ],
                        })
                continue

            # Model produced final answer
            answer = resp.get("text") or ""
            break

        if not answer:
            # Fallback generation if iterations were exhausted
            fallback_intent = last_tool_input.get("fact_type") or ("public_opinion" if is_opinion_q else "policy_fact")
            prompt = build_prompt(
                question=question,
                official_sources=curated_official,
                unofficial_sources=curated_unofficial,
                search_agent_data=synth_data,
                chat_history=chat_history,
                current_applicable_source=current_applicable if not is_opinion_q else None,
                conflicting_sources=conflicts,
                query_intent=fallback_intent,
                rewritten_query=question,
                official_facts=official_facts if not is_opinion_q else [],
                time_scope=last_tool_input.get("time_scope", "current"),
            )
            answer = ask_nova(prompt, max_tokens=1024)

    resolved_intent = plan.intent if router_mode == "regex" else (last_tool_input.get("fact_type") or ("public_opinion" if is_opinion_q else "policy_fact"))
    resolved_q = plan.resolved_query if router_mode == "regex" else question

    # STEP 5: Consistency Validation & Negation Prevention
    contradiction = _validate_consistency(
        answer,
        curated_official,
        query_intent=resolved_intent,
        official_facts=official_facts,
    )
    if contradiction:
        log.warning("Detected consistency issue in Query Agent response: %s", contradiction)
        repair_prompt = f"""
USER QUESTION: {question}

CURRENT ANSWER:
{answer}

==================================================
CORRECTION REQUIRED
==================================================
Your previous draft response contained an issue:
"{contradiction}"

Please rewrite your response to strictly address the user's intent and required format:
- If this is an opinion inquiry, summarize actual community discussion themes (waiting times, affordability, ballot uncertainty) and do NOT provide an income ceiling.
- If this is a policy inquiry with an active payout or grant, ensure the answer is affirmative and grounded in the official source.
- Under 'Key Conditions/Figures', provide exactly:
  - Category: <demographic, e.g. families or singles>
  - Exact official figure or percentage: <exact numerical figure, e.g. $16,000, $8,000, or $7,000>
  - Applicable date: <effective date or historical timeframe>
  Do NOT paste raw excerpt paragraphs or long sentences into Key Conditions/Figures.
"""
        answer = ask_nova(repair_prompt, max_tokens=1024)

    # STEP 6: Structured Debug Trace Output
    log.info(
        "\n==================================================\n"
        "MAIN AGENT ORCHESTRATION DEBUG TRACE\n"
        "==================================================\n"
        "1. Original Query: %s\n"
        "2. Resolved Query: %s\n"
        "3. Router Mode: %s\n"
        "4. Official Search Sources: %d retrieved\n"
        "5. Community Search Sources: %d retrieved\n"
        "6. Verification Decisions:\n"
        "   - Primary Source: %s\n"
        "   - Conflicts/Superseded: %s\n"
        "   - Grounded Policy Facts: %s\n"
        "7. Final Answer:\n%s\n"
        "==================================================",
        question,
        resolved_q,
        router_mode,
        len(curated_official),
        len(curated_unofficial),
        current_applicable.get("title") if current_applicable else "None",
        [c.get("reason") for c in conflicts],
        [f.get("value") for f in official_facts],
        answer,
    )

    # STEP 7: Persist turn in session
    try:
        _persist_turn(session, question, answer)
        _LAST_ACTIVE_SESSION_ID = current_session_id
    except Exception as e:
        log.warning("Failed to persist session turn for %s: %s", current_session_id, e)

    if return_session:
        return answer, current_session_id
    return answer