from __future__ import annotations

import logging
import re
from typing import Any
from services.bedrock import ask_nova
from services.webscraper import (
    build_search_intelligence,
    classify_intent,
    match_policy_urls,
    rewrite_query,
    scrape_sources,
    scrape_unofficial_sources,
    understand_user_intent,
)

log = logging.getLogger(__name__)

# Search collects and structures evidence. It does not write the final answer;
# the policy Query Agent uses this evidence after source checks.

SEARCH_SYNTHESIS_PROMPT = """
You are the Search Agent for a Singapore policy intelligence platform.

Your job is to synthesize web research from official Singapore government sources and public community discussions into structured, reliable policy intelligence for the Policy Query Agent.

==================================================
1. SOURCE HIERARCHY & GROUND TRUTH
==================================================

- Official Singapore government websites (.gov.sg, statutory boards, official ministries) are AUTHORITATIVE.
- Unofficial sources (Reddit, HardwareZone, public forums) provide COMMUNITY CONTEXT and SENTIMENT only.
- Unofficial sources must NEVER override or dictate official government policy, eligibility criteria, income ceilings, payout amounts, interest rates, or deadlines.
- Use raw source text as primary evidence. NEVER invent facts, dates, or numbers.

==================================================
2. CATEGORY PRESERVATION (CRITICAL)
==================================================

- Never mix policy categories or demographic groups.
- Maintain absolute separation:
  * SINGLES rules (e.g. 2-room Flexi BTO flat, singles grant) apply ONLY to singles.
  * FAMILIES / COUPLES rules apply ONLY to families/couples.
  * EXECUTIVE CONDOMINIUM (EC) rules apply ONLY to ECs.
  * SENIORS rules apply ONLY to seniors.
- Never transfer figures or income ceilings between categories (e.g. do not apply a family ceiling to a single applicant, or resale rules to new BTO flats).

==================================================
3. RECENCY & POLICY VERSIONING
==================================================

- Government policies and payment amounts evolve over time.
- Identify whether an official source represents the CURRENT active policy or an older, superseded announcement.
- When an official source announces an updated policy or payment quantum for the current year (e.g. 2026 Cost-of-Living Special Payment vs earlier Assurance Package iterations):
  * State the CURRENT applicable policy and figures clearly.
  * State the effective or disbursement date.
  * Note older figures under OLDER/CONFLICTING SOURCES as superseded context.
- Never average, combine, or randomly pick between conflicting figures from different policy periods.

==================================================
4. INSUFFICIENT EVIDENCE
==================================================

- If the retrieved sources do not contain authoritative evidence answering the question, explicitly state under EVIDENCE LIMITATIONS:
  "The available official sources do not provide enough information."
- Do not guess or extrapolate.

==================================================
5. REQUIRED STRUCTURED FORMAT
==================================================

Provide your synthesis strictly in the following structured sections:

CURRENT OFFICIAL POLICY:
[Clear summary of the active, applicable official policy]

IMPORTANT FIGURES:
- [Figure/Ceiling/Amount and exact category/demographic it applies to]

IMPORTANT DATES:
- [Announcement date, effective date, disbursement/payment date, or application period]

CURRENT APPLICABLE SOURCE:
- Title: [Official source title]
- URL: [Official source URL]
- Reason: [Why this source governs the current inquiry]

OLDER/CONFLICTING SOURCES:
[List any superseded announcements or conflicting historical figures, or 'None' if unambiguous]

COMMUNITY INSIGHTS:
[Brief public sentiment, user experiences, or common questions from unofficial sources, or 'None']

EVIDENCE LIMITATIONS:
[Any missing data or limitations in retrieved sources, or 'None']
"""


def build_search_synthesis_prompt(
    question: str,
    official_sources: list[dict],
    unofficial_sources: list[dict],
    current_applicable_source: dict | None = None,
    conflicts: list[dict] | None = None,
    intent_type: str = "GENERAL_INFORMATION",
    official_facts: list[dict] | None = None,
) -> str:
    """Build prompt to synthesize scraped search findings with applicability and recency awareness."""
    official_text = ""
    for idx, src in enumerate(official_sources, 1):
        content = src.get("content") or src.get("text") or ""
        snippet = src.get("search_snippet", "")
        excerpt = src.get("relevant_excerpt", "")
        combined_content = f"RELEVANT EXCERPT:\n{excerpt}\n\nFULL CONTENT:\n{content}".strip() if excerpt else content

        published = src.get("published_date") or src.get("publication_date") or "Not specified"
        effective = src.get("effective_date") or "Active"
        payment = src.get("payment_date") or "Not specified"
        app_reason = src.get("applicability_reason", "Applicable official government portal")

        official_text += f"""
[OFFICIAL SOURCE {idx}]
Title: {src.get('title', 'Official Government Source')}
URL: {src.get('url', '')}
Type: {src.get('source_type', 'Official Portal')}
Domain: {src.get('domain', '')}
Published Date: {published}
Effective Date: {effective}
Payment/Disbursement Date: {payment}
Applicability Reason: {app_reason}
Content:
{combined_content[:15000]}
-------------------------
"""

    structured_facts_text = ""
    if official_facts:
        structured_facts_text = "\nEXTRACTED STRUCTURED POLICY FACTS (AUTHORITATIVE FIGURES & RULES):\n"
        for f in official_facts:
            structured_facts_text += (
                f"- Fact: {f.get('fact')} | Category: {f.get('category')} | Value: {f.get('value')} | "
                f"Effective: {f.get('effective_date')} | Source: {f.get('source_title')} ({f.get('source_url')})\n"
                f"  Direct Excerpt: {f.get('relevant_excerpt')}\n"
            )

    unofficial_text = ""
    for idx, src in enumerate(unofficial_sources, 1):
        content = src.get("content") or src.get("text") or ""
        snippet = src.get("search_snippet", "")
        combined_content = f"{snippet}\n\n{content}".strip() if snippet else content
        unofficial_text += f"""
[UNOFFICIAL SOURCE {idx}]
Title: {src.get('title', 'Community Discussion')}
URL: {src.get('url', '')}
Type: {src.get('source_type', 'Community Forum')}
Domain: {src.get('domain', '')}
Content:
{combined_content[:8000]}
-------------------------
"""

    conflict_text = ""
    if conflicts:
        conflict_text = "\nIDENTIFIED POLICY CONFLICTS / SUPERSEDED SOURCES:\n"
        for c in conflicts:
            conflict_text += f"- {c.get('title')} ({c.get('url')}): {c.get('reason')}\n"

    target_source_text = ""
    if current_applicable_source:
        target_source_text = f"\nPRIMARY APPLICABLE SOURCE CANDIDATE:\nTitle: {current_applicable_source.get('title')}\nURL: {current_applicable_source.get('url')}\nReason: {current_applicable_source.get('applicability_reason')}\n"

    opinion_guidelines = ""
    if intent_type in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS"):
        opinion_guidelines = """
==================================================
SECTION 44: COMMUNITY SENTIMENT SYNTHESIS DIRECTIVE:
==================================================
The user is asking for public opinion, community sentiment, or lived experiences.
Synthesize strictly from UNOFFICIAL COMMUNITY SOURCES (Reddit, HardwareZone, forums).

Structure your community synthesis under the following headings:
COMMUNITY SENTIMENT:
- Positive themes: [Supported views, with source title]
- Negative concerns: [Recurring concerns, delays, ballot challenges, with source title]
- Mixed/controversial views: [Trade-offs, e.g. location vs waiting time, with source title]
- Common experiences: [Balloting rounds, marriage milestone timing, with source title]
- Frequently raised questions: [Recurring questions raised in discussions, with source title]

RULES:
1. For every important sentiment, retain the supporting source title/URL.
2. DO NOT turn one user's comment into "Singaporeans think...".
3. Use cautious phrasing: "Some users discussed...", "A recurring concern in the discussions was...", "Several commenters mentioned...", "Views were mixed...".
4. DO NOT substitute an official government page or income ceiling as public sentiment!
5. Official sources may only provide brief factual context if relevant.
==================================================
"""

    return f"""
{SEARCH_SYNTHESIS_PROMPT}

{opinion_guidelines}
{structured_facts_text}
{target_source_text}
{conflict_text}

OFFICIAL GOVERNMENT SOURCES:
{official_text if official_text else "No official sources provided."}

UNOFFICIAL COMMUNITY SOURCES:
{unofficial_text if unofficial_text else "No community forum discussions provided."}

USER QUESTION:
{question}
"""


def gather_and_search(
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
    Search, scrape, and structure intelligence from official Singapore government sources
    and community discussion platforms.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    all_official: list[dict] = []
    all_unofficial: list[dict] = []
    current_applicable: dict | None = None
    conflicts: list[dict] = []
    official_facts: list[dict] = []
    community_insights: list[dict] = []
    query_intent: str = "GENERAL_INFORMATION"
    rewritten_query: str = question
    debug_trace = None

    if provided_sources is not None:
        for s in provided_sources:
            if s.get("is_official", True):
                if need_official:
                    all_official.append(s)
            else:
                if need_community:
                    all_unofficial.append(s)
        query_intent = (plan_dict.get("intent") if plan_dict else None) or classify_intent(question)
    elif urls:
        scraped = scrape_sources(urls)
        for s in scraped:
            if s.get("is_official", True):
                if need_official and s not in all_official:
                    all_official.append(s)
            else:
                if need_community and s not in all_unofficial:
                    all_unofficial.append(s)
        query_intent = (plan_dict.get("intent") if plan_dict else None) or classify_intent(question)
    else:
        effective_query = (plan_dict.get("resolved_query") if plan_dict else None) or question
        intel = build_search_intelligence(
            effective_query,
            conversation_context=conversation_context,
            include_official=need_official,
            include_unofficial=need_community,
        )
        if need_official:
            all_official.extend(intel.get("official_sources", []))
            current_applicable = intel.get("current_applicable_source")
            conflicts = intel.get("conflicting_sources", [])
            official_facts = intel.get("official_policy_facts", [])
        if need_community:
            all_unofficial.extend(intel.get("unofficial_sources", []))
            community_insights = intel.get("community_insights", [])

        query_intent = intel.get("query_intent", "GENERAL_INFORMATION")
        rewritten_query = intel.get("rewritten_query", question)
        debug_trace = intel.get("debug_trace")

    plan_intent = plan_dict.get("intent") if plan_dict else None
    if plan_intent in ("policy_fact", "eligibility") or (need_official and not need_community):
        is_opinion = False
    else:
        is_opinion = query_intent in ("PUBLIC_OPINION", "USER_EXPERIENCE", "PROS_CONS")

    if not current_applicable and all_official and not is_opinion:
        current_applicable = all_official[0]

    # Section 39 & 43: If user has opinion intent and no community sources were found,
    # DO NOT fall back to an unrelated official government policy page
    if is_opinion and not all_unofficial:
        fallback_res = {
            "query_intent": query_intent,
            "rewritten_query": rewritten_query,
            "official_sources": all_official if need_official else [],
            "unofficial_sources": [],
            "current_applicable_source": None,
            "conflicting_sources": [],
            "official_policy_facts": [],
            "community_insights": [],
            "search_summary": "Insufficient public discussion evidence was found in available community sources.",
            "debug_trace": debug_trace,
        }
        if debug_trace:
            debug_trace.emit()
        return fallback_res

    # If no sources gathered at all
    if not all_official and not all_unofficial:
        fallback_res = {
            "query_intent": query_intent,
            "rewritten_query": rewritten_query,
            "official_sources": [],
            "unofficial_sources": [],
            "current_applicable_source": None,
            "conflicting_sources": [],
            "official_policy_facts": [],
            "community_insights": [],
            "search_summary": "The available official sources do not provide enough information.",
            "debug_trace": debug_trace,
        }
        if debug_trace:
            debug_trace.emit()
        return fallback_res

    prompt = build_search_synthesis_prompt(
        question=rewritten_query or question,
        official_sources=all_official,
        unofficial_sources=all_unofficial,
        current_applicable_source=current_applicable,
        conflicts=conflicts,
        intent_type=query_intent,
        official_facts=official_facts,
    )

    try:
        search_summary = ask_nova(prompt, max_tokens=600)
    except Exception as exc:
        log.warning("Bedrock synthesis call failed: %s", exc)
        search_summary = (
            f"Search intelligence gathered from {len(all_official)} official and "
            f"{len(all_unofficial)} community sources. (Bedrock notice: {exc})"
        )

    if debug_trace:
        debug_trace.search_agent_synthesis = search_summary
        debug_trace.emit()

    return {
        "query_intent": query_intent,
        "rewritten_query": rewritten_query,
        "official_sources": all_official,
        "unofficial_sources": all_unofficial,
        "current_applicable_source": current_applicable,
        "conflicting_sources": conflicts,
        "official_policy_facts": official_facts,
        "community_insights": community_insights,
        "search_summary": search_summary,
        "debug_trace": debug_trace,
    }


def answer_question(
    question: str,
    urls: list[str] | None = None,
    unofficial_sources: list[dict] | None = None,
) -> str:
    """
    Legacy method for answering purely from unofficial public forum sentiment.
    """
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if unofficial_sources is None:
        if not urls:
            raise ValueError("At least one unofficial source URL is required.")
        unofficial_sources = scrape_unofficial_sources(question)

    prompt = build_search_synthesis_prompt(
        question=question,
        official_sources=[],
        unofficial_sources=unofficial_sources,
    )
    return ask_nova(prompt)
