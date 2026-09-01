from __future__ import annotations

import re
from services.bedrock import ask_nova
from services.webscraper import (
    match_policy_urls,
    scrape_sources,
    scrape_unofficial_sources,
)


SEARCH_SYNTHESIS_PROMPT = """
You are the Search Agent for a Singapore policy intelligence platform.

Your job is to retrieve and synthesize the MOST CURRENT information about Singapore government policies.

You receive web search results from official government websites and public discussion platforms.

IMPORTANT:
Your output will be passed directly to a Policy Query Agent.
The Query Agent must be able to clearly determine the CURRENT policy and must NOT accidentally use outdated figures.

==================================================
1. SOURCE PRIORITY
==================================================

Use this priority order:

1. Most recent official Singapore Government source
2. Older official Singapore Government source
3. Reputable secondary source
4. Public discussion / Reddit / HardwareZone

Official sources include:
- HDB
- CPF Board
- MOM
- IRAS
- MOF
- MSF
- MOH
- MND
- Gov.sg
- Singapore Statutes Online

Never allow an unofficial source to override an official government source.

==================================================
2. RECENCY IS CRITICAL
==================================================

For EVERY policy figure, rule, eligibility requirement or deadline:

- Check the publication/update date.
- Identify whether the information is CURRENT or HISTORICAL.
- Prefer the newest official announcement or guideline.
- If a newer official source changes an older figure, use ONLY the newer figure as the CURRENT figure.

Example:

Old official source:
Income ceiling = $14,000
Effective: 1 April 2023

New official source:
Income ceiling = $16,000
Effective: 24 August 2026

Output:

CURRENT:
Income ceiling = $16,000

HISTORICAL:
$14,000 applied before 24 August 2026.

Do NOT present $14,000 as a current figure.

==================================================
3. CONFLICT RESOLUTION
==================================================

When two official sources contain different figures:

1. Compare their publication dates.
2. Check the effective date of each policy.
3. Determine whether the newer source explicitly changes the older policy.
4. Use the newest applicable figure as CURRENT.
5. Clearly label the older figure as HISTORICAL.

Never simply list conflicting figures without explaining which one is currently applicable.

==================================================
4. DIRECT OFFICIAL SOURCES
==================================================

When the user asks about a specific policy, prioritize the official page that directly governs that policy.

For example, for BTO / HDB eligibility, prioritize:

HDB Couples and Families:
https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families

HDB Singles:
https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles

HDB Seniors:
https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/seniors

Also prioritize newer HDB press releases or announcements if they modify the figures on these pages.

==================================================
5. SEARCH FOR POLICY UPDATES
==================================================

Do NOT rely only on the dedicated policy page.

For questions containing words such as:

- current
- latest
- today
- now
- updated
- new
- revised
- recently

also search for recent official announcements that may have changed the policy.

For example:

"current BTO income ceiling"

should search for:

- current HDB income ceiling
- latest HDB income ceiling
- HDB income ceiling 2026
- site:hdb.gov.sg income ceiling HDB
- recent HDB income ceiling announcement

==================================================
6. OUTPUT FORMAT
==================================================

Return information in this structure:

CURRENT POLICY:
[The current rule / figure]

EFFECTIVE DATE:
[When it became effective]

POLICY CATEGORY:
[Families / Singles / Seniors / CPF / etc.]

OFFICIAL SOURCE:
[Title]
[URL]

IMPORTANT HISTORICAL INFORMATION:
[Only include older figures if necessary to explain the change.]

COMMUNITY INSIGHTS:
[Only include public discussion if relevant.]

==================================================
7. NEVER INVENT INFORMATION
==================================================

Never guess a number.

Never assume an old figure is still current.

Never combine figures from different policy periods.

If the current figure cannot be determined from the retrieved sources, say:

"Current figure could not be confirmed from the retrieved official sources."

==================================================
8. FINAL RULE
==================================================

The MOST RECENT APPLICABLE OFFICIAL POLICY ALWAYS OVERRIDES OLDER POLICY INFORMATION.

Your primary objective is:

CURRENT + OFFICIAL + VERIFIED + DATE-AWARE

not simply:

MOST SEARCHED RESULT.
"""


def build_search_synthesis_prompt(
    question: str,
    official_sources: list[dict],
    unofficial_sources: list[dict],
) -> str:
    """Build prompt to synthesize scraped search findings with recency awareness."""
    official_text = ""
    for idx, src in enumerate(official_sources, 1):
        official_text += f"""
[OFFICIAL SOURCE {idx}]
Title: {src.get('title', 'Official Government Source')}
URL: {src.get('url', '')}
Type: {src.get('source_type', 'Official Portal')}
Last Updated: {src.get('last_updated', 'Not specified')}
Content:
{src.get('content', '')}
-------------------------
"""

    unofficial_text = ""
    for idx, src in enumerate(unofficial_sources, 1):
        unofficial_text += f"""
[UNOFFICIAL SOURCE {idx}]
Title: {src.get('title', 'Community Discussion')}
URL: {src.get('url', '')}
Type: {src.get('source_type', 'Unofficial Forum')}
Last Updated: {src.get('last_updated', 'Not specified')}
Content:
{src.get('content', '')}
-------------------------
"""

    return f"""
{SEARCH_SYNTHESIS_PROMPT}

OFFICIAL GOVERNMENT SOURCES:
{official_text if official_text else "No specific official web pages provided."}

UNOFFICIAL PUBLIC DISCUSSION SOURCES:
{unofficial_text if unofficial_text else "No unofficial forum discussions provided."}

USER QUERY:
{question}
"""


def gather_and_search(
    question: str,
    urls: list[str] | None = None,
    provided_sources: list[dict] | None = None,
) -> dict:
    """
    Search, scrape, and structure data from official Singapore government sources
    and community discussion platforms.

    Returns:
        dict with keys:
            - official_sources: list[dict]
            - unofficial_sources: list[dict]
            - search_summary: str
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    all_sources: list[dict] = []

    if provided_sources:
        all_sources.extend(provided_sources)

    target_urls = list(urls or [])

    # If no explicit URLs provided, intelligently match across multi-agency knowledge map
    if not target_urls and not provided_sources:
        official_urls, community_urls = match_policy_urls(question)
        target_urls.extend(official_urls + community_urls)

    if target_urls:
        scraped = scrape_sources(target_urls)
        all_sources.extend(scraped)

    official_sources = [s for s in all_sources if s.get("is_official", False)]
    unofficial_sources = [s for s in all_sources if not s.get("is_official", False)]

    # If no sources gathered at all
    if not official_sources and not unofficial_sources:
        return {
            "official_sources": [],
            "unofficial_sources": [],
            "search_summary": "No live sources found or specified for this query.",
        }

    prompt = build_search_synthesis_prompt(
        question=question,
        official_sources=official_sources,
        unofficial_sources=unofficial_sources,
    )

    try:
        search_summary = ask_nova(prompt, max_tokens=1500)
    except Exception as exc:
        search_summary = f"Search summary generated from sources: {len(official_sources)} official and {len(unofficial_sources)} unofficial sources scraped. (Bedrock notice: {exc})"

    return {
        "official_sources": official_sources,
        "unofficial_sources": unofficial_sources,
        "search_summary": search_summary,
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
        unofficial_sources = scrape_unofficial_sources(urls)

    prompt = build_search_synthesis_prompt(
        question=question,
        official_sources=[],
        unofficial_sources=unofficial_sources,
    )
    return ask_nova(prompt)
